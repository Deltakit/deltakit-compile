# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module that contains the realign qec detectors pass."""

from dataclasses import dataclass
from typing import TypeVar

from typing_extensions import override
from xdsl.dialects.builtin import IntAttr, ModuleOp
from xdsl.ir import Block, BlockArgument, Operation, OpResult, SSAValue
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.rewriter import InsertPoint, Rewriter

from deltakit_compile.dialects import qec, qstruct

_MOVE_DETECTOR_OP_ID_TAG = "realign_qec.move_detectors_id"


def _assign_id_prepass(op: ModuleOp, tag_name: str) -> None:
    """Prepass to assign a monotonically increasing ID to each operation in the module,
    based on an in order traversal. All operations share the same counter so
    IDs are comparable across operations."""
    for i, child_op in enumerate(op.walk()):
        child_op.attributes[tag_name] = IntAttr(i)


T = TypeVar("T", bound=Operation)


def _find_op_that_uses_ssa_or_ssa_owner(
    ssa: SSAValue, operation_type: type[T]
) -> T | Block | qstruct.RepeatOp:
    """Given an SSA value, find the operation that uses the SSA and has the provided operation
    type, or the block or repeat op that produces the SSA if no operation is found.

    Either the SSA is used by an operation of type operation_type, in which case we can move the
    SSA to just after that operation, or the SSA is produced by a qstruct.RepeatOp or a block
    argument, in which case we can move the SSA to just after the RepeatOp or to the start of the
    block, respectively."""
    for use in ssa.uses:
        op = use.operation
        if isinstance(op, operation_type):
            return op

    if isinstance(ssa, BlockArgument):
        return ssa.block

    assert isinstance(ssa, OpResult), f"Expected SSA to be an OpResult, but got {type(ssa)}"
    assert isinstance(ssa.op, qstruct.RepeatOp), (
        "Expected SSA to be produced by a qstruct.RepeatOp since measurement SSAs cannot be "
        f"produced by any other op, but got {type(ssa.op)}"
    )

    return ssa.op


def _find_insertion_op_or_block_for_detector_op(
    det_op: qec.DetectorOp,
) -> qec.MeasurementRoundOp | Block | qstruct.RepeatOp | None:
    """Find the operation or block that the provided detector op can be moved after, based on the
    measurement rounds that it targets.

    Returns None if the detector does not target any measurements."""
    last_round_id = -1
    last_round_op_or_block: qec.MeasurementRoundOp | Block | qstruct.RepeatOp | None = None
    for target in det_op.measurements:
        insertion_point = _find_op_that_uses_ssa_or_ssa_owner(target, qec.MeasurementRoundOp)

        if isinstance(insertion_point, Block):
            parent_op = insertion_point.parent_op()
            assert parent_op is not None, "Expected block to have a parent operation"
            assert parent_op == det_op.parent_op(), (
                "Expected parent operation of block to be the same as parent operation of "
                "detector op"
            )
            round_id_attr = parent_op.attributes[_MOVE_DETECTOR_OP_ID_TAG]
        else:
            round_id_attr = insertion_point.attributes[_MOVE_DETECTOR_OP_ID_TAG]
        assert isinstance(round_id_attr, IntAttr), (
            f"Expected {_MOVE_DETECTOR_OP_ID_TAG} attribute to be an IntAttr"
        )
        round_id = round_id_attr.data

        if round_id > last_round_id:
            last_round_id = round_id
            last_round_op_or_block = insertion_point

    return last_round_op_or_block


class _MoveDetectorOpsPattern(RewritePattern):
    """Rewrite pattern that moves each `qec.detector` op to immediately after its latest
    referenced measurement round or repeat op.

    **Placement rules**

    For each measurement SSA targeted by the detector, the insertion point is resolved as
    follows (in priority order):

    1. If the SSA is consumed by a `qec.MeasurementRoundOp` in the same scope, that round op is
       the candidate insertion point.
    2. If the SSA is a block argument, the enclosing block is the candidate insertion point
       (the detector will be placed at the start of that block).
    3. If the SSA is produced by a `qstruct.RepeatOp`, the repeat op is the candidate
       insertion point.

    Among all candidates, the one with the highest prepass-assigned ID (i.e. the latest in
    program order) is selected.  If the winning candidate belongs to a different parent op than
    the detector, the detector falls back to the start of its own parent block.

    **Infinite-loop guard**

    The pattern is a no-op when the detector is already in the correct position:
    - For a block target: the detector is already the first op in that block.
    - For an op target: the detector immediately follows that op (`prev_op` identity check).
    """

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qec.DetectorOp, rewriter: PatternRewriter):
        insertion_op_or_block = _find_insertion_op_or_block_for_detector_op(op)

        if insertion_op_or_block is None:
            return

        # this will fail to hold when a detector uses a measurement that was defined in an
        # outside scope, but this should never happen in the stim import pipeline
        assert insertion_op_or_block.parent_op() == op.parent_op(), (
            "Expected insertion point to be in the same parent operation as the detector op"
        )

        # Guard: skip if already in the correct position to avoid infinite rewrite loops.
        if isinstance(insertion_op_or_block, Block):
            if op.parent is insertion_op_or_block and op.prev_op is None:
                return
        elif op.prev_op is insertion_op_or_block:
            return

        op.detach()
        if isinstance(insertion_op_or_block, qec.MeasurementRoundOp):
            rewriter.insert_op(op, InsertPoint.after(insertion_op_or_block))
        elif isinstance(insertion_op_or_block, Block):
            # can move to the start of the block
            rewriter.insert_op(op, InsertPoint.at_start(insertion_op_or_block))
        else:
            assert isinstance(insertion_op_or_block, qstruct.RepeatOp)
            # can move just after the repeat
            rewriter.insert_op(op, InsertPoint.after(insertion_op_or_block))


def _find_insertion_op_or_block_for_detector_round_op(
    round_op: qec.DetectorRoundOp,
) -> qec.DetectorOp | Block | qstruct.RepeatOp | None:
    """Find the operation or block that the provided detector round op can be moved after, based on
    the detectors it targets.

    For each detector SSA operand of the round op, walks *backward* to the producing op:

    - If produced by a `qec.DetectorOp`: that op is the candidate insertion point.
    - If produced by a `qstruct.RepeatOp` (detector was yielded from a repeat body): that
      repeat op is the candidate insertion point.
    - If a `BlockArgument` (detector ref passed as a repeat iter-arg): the enclosing block
      is the candidate (round will be placed at the start of that block).
    - If detector round is empty (no detector operands), returns None

    Among all candidates the one with the highest prepass-assigned ID is selected."""
    last_detector_id = -1
    last_detector_op_or_block: qec.DetectorOp | Block | qstruct.RepeatOp | None = None
    for target in round_op.detectors:
        if isinstance(target, BlockArgument):
            block = target.block
            parent_op = block.parent_op()
            assert parent_op is not None, "Expected block to have a parent operation"
            detector_id_attr = parent_op.attributes[_MOVE_DETECTOR_OP_ID_TAG]
            insertion_point: qec.DetectorOp | Block | qstruct.RepeatOp = block
        else:
            assert isinstance(target, OpResult)
            producing_op = target.op
            assert isinstance(producing_op, (qec.DetectorOp, qstruct.RepeatOp)), (
                "Expected detector ref to be produced by a DetectorOp or RepeatOp, "
                f"but got {type(producing_op)}"
            )
            detector_id_attr = producing_op.attributes[_MOVE_DETECTOR_OP_ID_TAG]
            insertion_point = producing_op

        assert isinstance(detector_id_attr, IntAttr), (
            f"Expected {_MOVE_DETECTOR_OP_ID_TAG} attribute to be an IntAttr"
        )
        detector_id = detector_id_attr.data

        if detector_id > last_detector_id:
            last_detector_id = detector_id
            last_detector_op_or_block = insertion_point

    return last_detector_op_or_block


class _MoveDetectorRoundPass:
    """Moves each `qec.detector_round` op to immediately after the latest `qec.detector` op
    that produced one of its operands, while preserving the relative order of all
    `qec.detector_round` ops.

    **Algorithm overview**

    A prepass assigns a monotonically increasing integer ID to every op in the module via
    `_assign_id_prepass`.  The pattern then proceeds in three stages:

    1. **Mapping** (`_populate_operation_to_rounds_mapping`): Work out which
        operation/block to move each detector round after.

    2. **Ordering** (`_populate_detector_round_numbers`): Collect all detector round IDs in
       reverse order into a list, so that popping from the list always yields the next round to
       place in program order.

    3. **Placement** (`rewrite_module`): Move the detector rounds to their target locations
        whilst preserving the relative order."""

    def __init__(self) -> None:
        self.operation_to_rounds: dict[Operation | Block | None, list[qec.DetectorRoundOp]] = {}
        self.pending_rounds: dict[int, qec.DetectorRoundOp] = {}
        self.detector_round_numbers: list[int] = []

    def _populate_operation_to_rounds_mapping(self, module: ModuleOp) -> None:
        """Populates the `self.operation_to_rounds` mapping.

        The `self.operation_to_rounds` mapping is a dict from an operation or block to a list of
        `qec.detector_round` ops that should be placed immediately after that operation or at
        the start of that block."""
        for round_op in module.walk():
            if not isinstance(round_op, qec.DetectorRoundOp):
                continue
            insertion_op_or_block = _find_insertion_op_or_block_for_detector_round_op(round_op)

            if insertion_op_or_block is None:
                target_block = round_op.parent_block()
                assert target_block is not None, "Expected round op to have a parent block"
                insertion_op_or_block = target_block
            elif isinstance(insertion_op_or_block, Block):
                target_block = insertion_op_or_block
            else:
                target_block = insertion_op_or_block.parent_block()

            assert target_block is not None, "Expected insertion op or block to have a parent block"
            # If the target is in a different scope, fall back to the start of the round op's block.
            assert target_block == round_op.parent_block(), (
                "Expected target block to be the same as round op's parent block it is "
                "expected that detectors will not be referenced across scopes in the stim"
                " import pipeline"
            )

            target: Operation | Block = insertion_op_or_block
            if target not in self.operation_to_rounds:
                self.operation_to_rounds[target] = []
            self.operation_to_rounds[target].append(round_op)

    def _populate_detector_round_numbers(self, module: ModuleOp) -> None:
        """Collects the prepass-assigned IDs of all detector rounds ops in reverse order.

        The prepass will assign a monotonically increasing integer ID to every op in the module,
        and this method simply collects the IDs of all detector rounds in reverse order into
        `self.detector_round_numbers`. The resulting list can then be used as a stack as popping
        from the list always yields the next round to place in program order."""
        rounds_to_move: set[qec.DetectorRoundOp] = {
            round_op for round_list in self.operation_to_rounds.values() for round_op in round_list
        }
        for child_op in module.walk(reverse=True):
            if isinstance(child_op, qec.DetectorRoundOp) and child_op in rounds_to_move:
                round_num = child_op.attributes.get(_MOVE_DETECTOR_OP_ID_TAG)
                assert isinstance(round_num, IntAttr)
                self.detector_round_numbers.append(round_num.data)

    def _try_place_pending_rounds(self, insert_point: InsertPoint) -> None:
        """Attempts any pending detector rounds that are ready to be inserted at `insert_point`.

        A `pending` detector round is a detector round op that is ready to be placed as we have
        seen its target operation or block in the module walk. However, in order to preserve
        detector round ordering, a pending round can only be placed if all previous rounds
        have already been placed.

        Therefore, this method will check the last round in `self.detector_round_numbers`
        (the next round to place in program order) and attempt to place it at the current
        `insert_point`. If the round is in a different block than the current insert point, it
        cannot be placed yet and the method will return. Otherwise, the round is moved to the
        current insert point and removed from `self.pending_rounds` and
        `self.detector_round_numbers`. The method will continue to attempt to place rounds
        until there are no more rounds to place or the next round cannot be placed."""
        while (
            self.detector_round_numbers and self.detector_round_numbers[-1] in self.pending_rounds
        ):
            next_round_id = self.detector_round_numbers[-1]
            next_round_op = self.pending_rounds[next_round_id]
            # we cannot move a detector round into a different block than it is already in,
            # so if the next round is in a different block than the current insert point, we
            # cannot place it yet and must wait until we are back in that block
            if next_round_op.parent_block() != insert_point.block:
                break

            if insert_point.insert_before is next_round_op:
                # The round is already at the target position; advance past it without moving.
                insert_point = InsertPoint(insert_point.block, next_round_op.next_op)
                del self.pending_rounds[next_round_id]
                self.detector_round_numbers.pop()
                continue

            next_round_op.detach()
            Rewriter.insert_op(next_round_op, insert_point)
            del self.pending_rounds[next_round_id]
            self.detector_round_numbers.pop()

    def rewrite_module(self, module: ModuleOp) -> None:
        self._populate_operation_to_rounds_mapping(module)
        self._populate_detector_round_numbers(module)
        prev_block: None | Block = None
        for op in module.walk():
            parent_block = op.parent_block()
            if parent_block is None:
                assert isinstance(op, ModuleOp), (
                    "Expected only the module op to have no parent block"
                )
                continue
            # have we entered a new block?
            if prev_block != parent_block:
                prev_block = parent_block
                for round_op in self.operation_to_rounds.get(parent_block, []):
                    round_id_attr = round_op.attributes.get(_MOVE_DETECTOR_OP_ID_TAG)
                    assert isinstance(round_id_attr, IntAttr)
                    round_id = round_id_attr.data
                    if self.detector_round_numbers and round_id >= self.detector_round_numbers[-1]:
                        self.pending_rounds[round_id] = round_op
                self._try_place_pending_rounds(InsertPoint.before(op))

            if op in self.operation_to_rounds:
                for round_op in self.operation_to_rounds[op]:
                    round_id_attr = round_op.attributes.get(_MOVE_DETECTOR_OP_ID_TAG)
                    assert isinstance(round_id_attr, IntAttr)
                    round_id = round_id_attr.data
                    if self.detector_round_numbers and round_id >= self.detector_round_numbers[-1]:
                        self.pending_rounds[round_id] = round_op

            # check if we can place any pending rounds
            self._try_place_pending_rounds(InsertPoint(parent_block, op.next_op))

        if len(self.pending_rounds) > 0:
            msg = (
                "realign qec detectors: some detector rounds could not be moved and are still "
                "pending after walking the whole module, which indicates a bug in the pass "
                "since all rounds should have been placed by the time we exit their parent block. "
                "rounds still pending after module walk: "
                f"{list(self.pending_rounds.keys())}"
            )
            raise RuntimeError(msg)


@dataclass(frozen=True)
class RealignQecDetectors(ModulePass):
    """Pass that realigns qec detectors for optimal processing."""

    name = "realign-qec-detectors"

    @override
    def apply(self, ctx, op: ModuleOp) -> None:
        _assign_id_prepass(op, _MOVE_DETECTOR_OP_ID_TAG)
        PatternRewriteWalker(
            _MoveDetectorOpsPattern(), apply_recursively=False, walk_reverse=True
        ).rewrite_module(op)
        _assign_id_prepass(op, _MOVE_DETECTOR_OP_ID_TAG)
        _MoveDetectorRoundPass().rewrite_module(op)
        for child_op in op.walk():
            child_op.attributes.pop(_MOVE_DETECTOR_OP_ID_TAG, None)
