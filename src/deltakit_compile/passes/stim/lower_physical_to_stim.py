# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Lowers IR to stim dialect."""

from dataclasses import dataclass
from typing import Final

from typing_extensions import override
from xdsl.dialects.builtin import (
    I1,
    ArrayAttr,
    Float64Type,
    FloatAttr,
    IntegerAttr,
    IntegerType,
    ModuleOp,
)
from xdsl.ir import BlockArgument, Operation, OpResult, SSAValue
from xdsl.pattern_rewriter import (
    GreedyRewritePatternApplier,
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.rewriter import InsertPoint
from xdsl.utils.hints import isa

from deltakit_compile.dialects import deltakit_stim as deltakit_stim_dialect
from deltakit_compile.dialects import qcore, qec, qstruct, scf, stim
from deltakit_compile.exceptions import (
    CompilerPassCheckError,
    StimUnsupportedInstruction,
)
from deltakit_compile.passes.common.pipeline import (
    ConfigurablePass,
    Configuration,
    configurable_pass,
)
from deltakit_compile.passes.stim._common import copy_stim_tag, warn_stim_tag_lost
from deltakit_compile.passes.stim.physical_gate_rewrites import (
    InlineCircuitPattern,
    get_existing_qubit_ids,
    get_physical_gate_rewrite_patterns,
)

Loop_Types = qstruct.RepeatOp | scf.ForOp | scf.WhileOp

_ROUND_NUM_ATTR: Final[str] = "lower_physical_to_stim.round_num"
_SEEN_ATTR: Final[str] = "lower_physical_to_stim.seen"
_SHIFT_ATTR: Final[str] = "lower_physical_to_stim.shift"


@dataclass
class _DetectorPattern(RewritePattern):
    """Replaces qec.DetectorOp with stim operations, adding round information as an attribute to the
    detector."""

    empty_detectors_get_deleted: bool

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qec.DetectorOp, rewriter: PatternRewriter) -> None:
        """Handle detector reference operations."""
        # Check if this op is safe to remove
        if op.result.first_use:
            return

        if not op.measurements and self.empty_detectors_get_deleted:
            rewriter.erase_op(op)
            return

        coords = list(op.coords.data) if op.coords else []

        round_num = op.attributes.get(_ROUND_NUM_ATTR)
        if round_num is not None:
            assert isa(round_num, IntegerAttr)
            coords.append(FloatAttr(round_num.value.data, Float64Type()))

        # Create the stim detector operation with round as final coordinate
        rewriter.replace_op(
            op,
            new_op := stim.DetectorOp(
                op.measurements,
                ArrayAttr(coords) if coords else None,
            ),
            new_results=[None],
        )
        copy_stim_tag(op, new_op)


class _MeasurementRoundPattern(RewritePattern):
    """Removes qec.MeasurementRoundOp, as Deltakit-Stim does not have an equivalent concept."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qec.MeasurementRoundOp, rewriter: PatternRewriter) -> None:
        """Handle measurement round operations."""
        warn_stim_tag_lost(
            op,
            "Lower physical to stim: Deltakit-Stim tag on qec.MeasurementRoundOp was "
            "lost because Deltakit-Stim has no equivalent concept.",
        )
        rewriter.erase_op(op)


class _DetectorRoundPattern(RewritePattern):
    """Assign round numbers to detectors within a detector round. Removes detector round if all
    detectors can be assigned round numbers."""

    def __init__(self) -> None:
        self.block_arg_to_round_number: dict[BlockArgument[qec.DetectorRefType], IntegerAttr] = {}

    def _handle_op_result(
        self, detector: SSAValue[qec.DetectorRefType], round_num: IntegerAttr
    ) -> SSAValue[qec.DetectorRefType] | None:
        assert isinstance(detector, OpResult)
        owner = detector.owner
        if isinstance(owner, qec.DetectorOp):
            # Check if already assigned a round number
            if owner.attributes.get(_ROUND_NUM_ATTR) is not None:
                if owner.attributes[_ROUND_NUM_ATTR] != round_num:
                    msg = (
                        "Detector is used in multiple rounds, which is not supported in "
                        "Deltakit-Stim. "
                        f"The detector defined in operation {owner} was seen with round number "
                        f"{owner.attributes[_ROUND_NUM_ATTR]} and "
                        f"{round_num.value.data}."
                    )
                    owner.emit_error(msg, StimUnsupportedInstruction(msg))
                return None
            # Assign the round number
            owner.attributes[_ROUND_NUM_ATTR] = round_num
            return None
        if isinstance(owner, qstruct.RepeatOp):
            # Detector comes from a repeat result - traverse to yielded value
            index = detector.index
            yield_op = owner.body.block.last_op
            assert isinstance(yield_op, qstruct.YieldOp)
            shift = yield_op.attributes.get(_SHIFT_ATTR, IntegerAttr(0, IntegerType(64)))
            assert isinstance(shift, IntegerAttr)
            new_round_num = IntegerAttr(round_num.value.data + shift.value.data, IntegerType(64))
            new_detector_ssa = yield_op.operands[index]
            assert isa(new_detector_ssa, SSAValue[qec.DetectorRefType])
            return self._add_round_to_detector(new_detector_ssa, new_round_num)
        # Unsupported operation
        return detector

    def _handle_block_arg(
        self,
        detector: BlockArgument[qec.DetectorRefType],
        round_num: IntegerAttr,
    ) -> SSAValue[qec.DetectorRefType] | None:
        owner = detector.owner
        # Originates from a block argument
        parent_op = owner.parent_op()
        if isinstance(parent_op, qstruct.RepeatOp):
            # If the detector originates from a block argument of a repeat block, there
            # are 2 places it can originate from - the iter_args of the repeat, or the
            # operands of the yield op in the body of the repeat block.
            if (detector_round_num := self.block_arg_to_round_number.get(detector)) is not None:
                if detector_round_num != round_num:
                    msg = (
                        "During traversal of a repeat operation, the same block argument was "
                        "encountered with different round numbers. "
                        "This is not supported in Deltakit-Stim because it means that the detector "
                        "is being used in multiple rounds."
                        f" The block argument in position {detector.index} was seen with "
                        f"round number {detector_round_num.value.data} and "
                        f"{round_num.value.data}."
                    )
                    parent_op.emit_error(msg, StimUnsupportedInstruction(msg))
                return None

            self.block_arg_to_round_number[detector] = round_num

            # Iter arg case
            index = detector.index
            detector_iter_arg = parent_op.iter_args[index]
            assert isa(detector_iter_arg, SSAValue[qec.DetectorRefType])
            if self._add_round_to_detector(detector_iter_arg, round_num):
                return detector

            # Yield op case
            yield_op = parent_op.body.block.last_op
            assert isinstance(yield_op, qstruct.YieldOp)

            shift = yield_op.attributes.get(_SHIFT_ATTR)
            assert isinstance(shift, IntegerAttr)
            new_round_num = IntegerAttr(round_num.value.data + shift.value.data, IntegerType(64))
            new_detector_ssa = yield_op.operands[index]
            assert isa(new_detector_ssa, SSAValue[qec.DetectorRefType])
            if self._add_round_to_detector(
                new_detector_ssa,
                new_round_num,
            ):
                return detector

            return None

        # Unsupported operation
        return detector

    def _add_round_to_detector(
        self,
        detector: SSAValue[qec.DetectorRefType],
        round_num: IntegerAttr,
    ) -> SSAValue[qec.DetectorRefType] | None:
        """Traverses a detector reference and adds the round number as an attribute.

        Returns True if successful, False if the detector originates from an unsupported operation.
        """

        if isinstance(detector, OpResult):
            return self._handle_op_result(detector, round_num)

        if isinstance(detector, BlockArgument):
            return self._handle_block_arg(detector, round_num)

        msg = (
            "Unknown SSA value type for detector reference. Expected OpResult or BlockArgument, "
            f"got {type(detector)}"
        )
        raise ValueError(msg)

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qec.DetectorRoundOp, rewriter: PatternRewriter) -> None:
        """Assign round numbers to detectors that can be replaced, keep others in the round."""
        round_num = op.attributes.get(_ROUND_NUM_ATTR)
        assert isa(round_num, IntegerAttr), "Expected 'round' attribute to be an IntegerAttr"
        # Track which detectors couldn't be replaced
        unreplaced_detectors = []

        for detector in op.detectors:
            assert isa(detector, SSAValue[qec.DetectorRefType])
            try:
                if dec := self._add_round_to_detector(detector, round_num):
                    # Keep this detector if it couldn't be replaced
                    unreplaced_detectors.append(dec)
            except ValueError as e:
                op.emit_error(str(e), ValueError(str(e)))

        # If there are detectors that couldn't be replaced, keep them in a new detector round
        if unreplaced_detectors:
            if len(unreplaced_detectors) < len(op.detectors):
                new_detector_round = qec.DetectorRoundOp(unreplaced_detectors)
                # Preserve the round attribute
                new_detector_round.attributes[_ROUND_NUM_ATTR] = round_num
                rewriter.replace_op(op, new_detector_round)
        else:
            # All detectors were successfully handled, erase the detector round op
            rewriter.erase_op(op)


def _get_existing_observable_ids(module: ModuleOp) -> dict[int, int]:
    """Get the set of existing observable ids in the module, to avoid assigning duplicate ids when
    lowering observables."""
    id_block_start_to_end: dict[int, int] = {}
    id_block_end_to_start: dict[int, int] = {}
    existing_ids = set()

    for op in module.walk():
        if isinstance(op, qec.DecObservableOp):
            obs_id = stim.ObservableIdAttr.get(op)
            if obs_id is not None:
                if obs_id in existing_ids:
                    msg = (
                        f"Duplicate observable id {obs_id} found. "
                        "Observable ids must be unique. Please ensure that all observables have "
                        f"unique ids, or remove the {stim.ObservableIdAttr.KEY} attribute to "
                        "allow the pass to assign new ids."
                    )
                    op.emit_error(msg, ValueError(msg))

                existing_ids.add(obs_id)
                assert obs_id not in id_block_start_to_end, (
                    "Unexpected observable id conflict in _get_existing_observable_ids."
                    "This likely indicates a bug in the pass - please report this to"
                    "the developers."
                )
                next_id = obs_id + 1
                assert next_id not in id_block_end_to_start, (
                    "Unexpected observable id conflict in _get_existing_observable_ids."
                    "This likely indicates a bug in the pass - please report this to"
                    "the developers."
                )
                id_block_start_to_end[obs_id] = next_id
                id_block_end_to_start[next_id] = obs_id

                if next_id in id_block_start_to_end:
                    id_block_start_to_end[obs_id] = id_block_start_to_end[next_id]
                    id_block_end_to_start[id_block_start_to_end.pop(next_id)] = obs_id

                if obs_id in id_block_end_to_start:
                    id_block_end_to_start[id_block_start_to_end[obs_id]] = id_block_end_to_start[
                        obs_id
                    ]
                    id_block_start_to_end[id_block_end_to_start.pop(obs_id)] = (
                        id_block_start_to_end.pop(obs_id)
                    )

    return id_block_start_to_end


class _ObservablePattern(RewritePattern):
    """Replaces qec.DecObservableOp and qec.ObservableIncludeOp with stim operations.

    Tracks observable SSAs through qstruct.repeats and observable includes to ensure that they are
    with the correct observable id. Erases any observable include operations it finds."""

    def __init__(self, id_to_next_available: dict[int, int]) -> None:
        self.obs_id = 0
        self.id_to_next_available = id_to_next_available
        self.block_arg_to_obs_number: dict[BlockArgument[qec.ObservableType], IntegerAttr] = {}

    def _replace_all_uses_with_observable_ref(
        self,
        obs: SSAValue[qec.ObservableType],
        obs_id: int,
        rewriter: PatternRewriter,
    ) -> None:
        """Replace all uses of the given observable SSA with a reference to the observable id."""
        for use in obs.uses:
            op = use.operation
            index = use.index
            if isinstance(op, qec.ObservableIncludeOp):
                rewriter.insert_op(
                    new_op := stim.ObservableIncludeOp(
                        op.measurements,
                        obs_id,
                    ),
                    InsertPoint.before(op),
                )
                copy_stim_tag(op, new_op)
                self._replace_all_uses_with_observable_ref(op.out_obs, obs_id, rewriter)
                rewriter.replace_all_uses_with(op.out_obs, obs)
                rewriter.erase_op(op)
            elif isinstance(op, qstruct.RepeatOp):
                arg = op.body.block.args[index]
                assert isa(arg, SSAValue[qec.ObservableType])
                assert isinstance(arg, BlockArgument)
                self.block_arg_to_obs_number[arg] = IntegerAttr(obs_id, IntegerType(32))
                self._replace_all_uses_with_observable_ref(arg, obs_id, rewriter)
            elif isinstance(op, qstruct.YieldOp):
                parent_op = op.parent_op()
                if isinstance(parent_op, qstruct.RepeatOp):
                    operand = parent_op.res[index]
                    assert isa(operand, SSAValue[qec.ObservableType])
                    self._replace_all_uses_with_observable_ref(operand, obs_id, rewriter)
                    block_arg = parent_op.body.block.args[index]
                    assert isa(block_arg, SSAValue[qec.ObservableType])
                    assert isinstance(block_arg, BlockArgument)
                    if block_arg not in self.block_arg_to_obs_number:
                        self._replace_all_uses_with_observable_ref(block_arg, obs_id, rewriter)
                    elif self.block_arg_to_obs_number[block_arg].value.data != obs_id:
                        msg = (
                            "Lower physical to stim: "
                            "An observable was yielded in a repeat block and the "
                            "corresponding block argument was used with a different "
                            "observable. This is not supported in Deltakit-Stim because it means "
                            "that the same block argument is being used to refer to different "
                            "observables across iterations of the repeat."
                            f" The block argument in position {block_arg.index} was seen with "
                            f"observable id {self.block_arg_to_obs_number[block_arg].value.data} "
                            f"and {obs_id}."
                        )
                        op.emit_error(msg, StimUnsupportedInstruction(msg))

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qec.DecObservableOp, rewriter: PatternRewriter) -> None:
        """Handle observable operations."""

        if (obs_id := stim.ObservableIdAttr.get(op)) is None:
            if self.obs_id in self.id_to_next_available:
                self.obs_id = self.id_to_next_available[self.obs_id]
            obs_id = self.obs_id
            stim.ObservableIdAttr.set(op, obs_id)
            self.obs_id += 1

        parent = op.parent_op()
        while parent:
            if isinstance(parent, Loop_Types):
                msg = (
                    "Defining an observable inside a loop block is not supported in Deltakit-Stim. "
                    "The reason for this is because there is no `shift_observable` operation in "
                    "Deltakit-Stim, which means that observables cannot be shifted across repeat "
                    "iterations. "
                )
                op.emit_error(msg, StimUnsupportedInstruction(msg))
            parent = parent.parent_op()

        self._replace_all_uses_with_observable_ref(op.result, obs_id, rewriter)


class _QStructOutputPattern(RewritePattern):
    """Lower qstruct.OutputOp to stim operations."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.OutputOp, rewriter: PatternRewriter) -> None:
        """Handle qstruct output operations."""
        warn_stim_tag_lost(
            op,
            "Lower physical to stim: Stim tag on qstruct.OutputOp was lost "
            "because Stim has no equivalent concept for output operations.",
        )
        if not isinstance(op.parent_op(), ModuleOp):
            parent = op.parent_op()
            assert parent is not None
            msg = (
                f"{LowerPhysicalToStim.name} pass can only lower {op.name} ops"
                f" that are in the top level of the module but {op.name} was"
                f" found it inside a {parent.name}"
            )
            raise CompilerPassCheckError(msg)
        rewriter.erase_op(op)


class _DetectorShiftPattern(RewritePattern):
    """Adds stim.ShiftCoordsOp after each detector round to shift the coordinates."""

    def __init__(self, length: int) -> None:
        self.length = max(length, 0)

    @override
    def match_and_rewrite(self, op: Operation, rewriter: PatternRewriter) -> None:
        if _SHIFT_ATTR in op.attributes:
            shift = op.attributes[_SHIFT_ATTR]
            if not isinstance(shift, IntegerAttr):
                msg = (
                    "The 'shift' attribute is expected to be an IntegerAttr, "
                    f"but found: \n{shift}\n of type {type(shift)}"
                )
                op.emit_error(msg, ValueError(msg))
            if shift.value.data != 0:
                new_op = stim.ShiftCoordsOp([0] * self.length + [shift.value.data])
                rewriter.insert_op(new_op, InsertPoint.before(op))
                copy_stim_tag(op, new_op)

            del op.attributes[_SHIFT_ATTR]


class _RepeatPattern(RewritePattern):
    """Lower qstruct.RepeatOp to stim operations."""

    def __init__(
        self,
        detector_block_args: dict[BlockArgument[qec.DetectorRefType], IntegerAttr],
        observable_block_args: dict[BlockArgument[qec.ObservableType], IntegerAttr],
    ) -> None:
        self.detector_block_args = detector_block_args
        self.observable_block_args = observable_block_args

    def _rewrite_yield(self, op: qstruct.YieldOp, rewriter: PatternRewriter) -> None:
        """Handle yield operations."""
        new_yield = stim.YieldOp(*[operand for operand in op.operands if isa(operand.type, I1)])
        if _SHIFT_ATTR in op.attributes:
            new_yield.attributes[_SHIFT_ATTR] = op.attributes[_SHIFT_ATTR]
        rewriter.replace_op(op, new_yield)

    def _replace_qcore_qubit_block_args(
        self, op: qstruct.RepeatOp, rewriter: PatternRewriter
    ) -> None:
        """Replace qcore.qubit block arguments with stim.qubit block arguments."""
        for arg in op.body.block.args:
            if isinstance(arg.type, qcore.QubitType):
                rewriter.replace_value_with_new_type(arg, stim.QubitType())

    def _check_if_rewritable(self, op: qstruct.RepeatOp) -> bool:
        """Check if the repeat operation can be rewritten to a stim repeat operation.

        An op is rewritable if:
        - There are no operands of type `qcore.QubitType`, ie they must have been converted to
        stim qubit references in a previous pass. This is to ensure proper replacement inside
        the body of the repeat.
        - Any operand of type `qec.DetectorRefType` or `qec.ObservableType` has at most one use.
        - For any operand of type `qcore.QubitType`, it cannot be used in a `qstruct.repeat`,
        AND it is yielded out with the same index as the operand in the iter_args
        of the repeat. This is to ensure that the operand refers to the same qubit reference
        across iterations of the repeat.
        """

        last_op = op.yield_op
        assert isinstance(last_op, qstruct.YieldOp), (
            "Expected last operation in repeat block to be a YieldOp"
        )

        def _handle_qec_type(val: BlockArgument) -> bool:
            return (val.has_one_use() or (not bool(val.uses))) and (
                val in self.detector_block_args or val in self.observable_block_args
            )

        def _handle_qubit_type(val: BlockArgument) -> bool:
            for use in val.uses:
                user_op = use.operation
                if user_op == last_op:
                    return use.index == val.index
            return False

        if any(isinstance(arg.type, qcore.QubitType) for arg in op.iter_args):
            return False

        for arg in op.body.block.args:
            if isa(arg.type, I1):
                continue
            if isinstance(arg.type, (qec.DetectorRefType, qec.ObservableType)):
                if not _handle_qec_type(arg):
                    return False
            elif isinstance(arg.type, stim.QubitType):
                if not _handle_qubit_type(arg):
                    return False
            else:
                return False
        return True

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.RepeatOp, rewriter: PatternRewriter) -> None:
        """Handle repeat operations."""

        self._replace_qcore_qubit_block_args(op, rewriter)
        if not self._check_if_rewritable(op):
            return

        block = rewriter.move_region_contents_to_new_regions(op.body).detach_block(0)
        yield_op = block.last_op
        assert isinstance(yield_op, qstruct.YieldOp), (
            "Expected last operation in repeat block to be a YieldOp"
        )
        # Modify block arguments in place, iterating in reverse to avoid index issues
        for i in reversed(range(len(block.args))):
            arg = block.args[i]
            if not isa(arg.type, I1):
                rewriter.replace_all_uses_with(arg, op.iter_args[i])

                rewriter.replace_all_uses_with(op.res[i], yield_op.operands[i])

                rewriter.erase_block_argument(arg)

        self._rewrite_yield(yield_op, rewriter)

        # Create the new stim repeat operation with the modified block
        new_repeat = stim.RepeatOp(
            op.repetitions,
            block,
            [arg for arg in op.iter_args if isa(arg.type, I1)],
        )

        # Map old results to new results
        new_results: list[SSAValue | None] = []
        new_result_idx = 0
        for old_result in op.results:
            if isa(old_result.type, I1):
                new_results.append(new_repeat.results[new_result_idx])
                new_result_idx += 1
            else:
                new_results.append(None)
        rewriter.replace_op(op, new_repeat, new_results)
        copy_stim_tag(op, new_repeat)


def _detector_round_prepass(module: ModuleOp) -> int:
    """Prepass that assigns an id to each detector round and keeps track of shifts. Returns
    rank of the detector coordinates.

    The way this works is you need to assign a unique number to each detector round. Without
    repeats, this is very simple - just walk through every op and if it's a DetectorRoundOp
    and assign an id, and then just increment the internal counter. With repeats, this doesn't
    work anymore. Similar to how you have shift_detectors in stim, you need a similar thing here.
    In this case, the shift is equal to the number of DetectorRoundOps that are direct children
    of the the repeat (not all children so this will work with nested repeats).

    To do this, a stack of ids is used and the last value on the stack is pushed back onto the stack
    every time you enter a new region, and pop when you leave.

    With some thought, every time you leave a region, the difference between the last value and
    the second last value of the stack is the number of DetectorRoundOps that are a direct children
    of that region. Therefore we can add a shift attribute which will be turned into an actual
    shift operation in a later pattern.

    A question is why am I pushing the last value of stack rather than 0? By pushing the
    last value on the stack, it correctly keeps track of id I need to assign to the next
    DetectorRoundOp I see. In other words, the last value of the stack is the next id assigned to
    the next DetectorRoundOp seen To make this clearer, here is an example.

    ```
    DetectorRoundOp() ->id: 0
    stack = [1]
    Repeat 3x:
    DetectorRoundOp() -> id: 1
    DetectorRoundOp() -> id: 2
    DetectorRoundOp() -> id: 3
            stack = [1,4]
    Shift 3 DetectorRounds
    DetectorRoundOp() -> id : 1
    ```

    When you take into account the shift instruction, you should hopefully be able to see that the
    id assigned to the last DetectorRoundOp is consistent
    """
    detector_round_stack = [0]  # Stack for detector rounds
    length: int | None = None
    for op in module.walk(region_first=True):
        block = op.parent_block()
        if not block:
            continue
        if block.first_op == op and isinstance(block.parent_op(), qstruct.RepeatOp):
            detector_round_stack.append(detector_round_stack[-1])

        if isinstance(op, qec.DetectorRoundOp):
            op.attributes[_ROUND_NUM_ATTR] = IntegerAttr(detector_round_stack[-1], IntegerType(64))
            detector_round_stack[-1] += 1
        elif isinstance(op, qec.DetectorOp):
            if op.coords is None:
                continue
            coord_length = len(op.coords.data)
            if length is None:
                length = coord_length
            elif coord_length != length:
                msg = (
                    "All detectors must have the same number of coordinates for the shift"
                    " logic in the _detector_round_prepass to work. Found a detector with "
                    f"{coord_length} coordinates, expected {length}."
                )
                op.emit_error(msg, StimUnsupportedInstruction(msg))

        if block.last_op == op and isinstance(block.parent_op(), qstruct.RepeatOp):
            op.attributes[_SHIFT_ATTR] = IntegerAttr(
                detector_round_stack[-1] - detector_round_stack[-2], IntegerType(64)
            )
            detector_round_stack.pop()

    return length or 0


def _delete_existing_attributes(module: ModuleOp) -> None:
    """Deletes any existing attributes that are added by this pass to ensure a clean slate for the
    pass to run on."""
    for op in module.walk():
        if _ROUND_NUM_ATTR in op.attributes:
            del op.attributes[_ROUND_NUM_ATTR]
        if _SEEN_ATTR in op.attributes:
            del op.attributes[_SEEN_ATTR]
        if _SHIFT_ATTR in op.attributes:
            del op.attributes[_SHIFT_ATTR]


def _verify_all_stim(module: ModuleOp) -> None:
    """Pattern to verify all ops are in the (le)stim dialect after the lowering pass."""
    for op in module.walk():
        if op.dialect_name() not in [
            stim.Stim.name,
            deltakit_stim_dialect.DeltakitStim.name,
        ] and not isa(op, ModuleOp):
            if isinstance(op, qec.DetectorOp):
                assert op.result.first_use, (
                    "Detector op has no uses, but should have been removed in this case"
                )
                msg = (
                    f"A detector op was not removed. It was not removed because it is still used "
                    f"in operation {op.result.first_use.operation.name}."
                )
            elif isinstance(op, qstruct.RepeatOp):
                msg = (
                    "A repeat op was not removed. This means that it is not classified as "
                    "rewritable by the _RepeatPattern. For further details, see the docstring of"
                    " `_check_if_rewritable` and the checks it performs to determine if a repeat "
                    "is rewritable."
                )
            else:
                msg = (
                    "Non-stim operation found. It is likely that this operation performs "
                    "non-trivial functionality, so was not DCE'd when qstruct.output was removed."
                )
            op.emit_error(msg, StimUnsupportedInstruction(msg))


class LowerPhysicalToStimConfig(Configuration, frozen=True):
    """Configuration for the LowerPhysicalToStim pass.

    Attributes:
        empty_detectors_get_deleted (bool): If True, empty detectors will be deleted. If
            False, they will be kept.
        verify_all_stim (bool): If True, all operations will be verified to be in the stim dialect
            after the lowering pass. If False, this verification is skipped.
    """

    empty_detectors_get_deleted: bool = True
    verify_all_stim: bool = False


@configurable_pass
class LowerPhysicalToStim(ConfigurablePass[LowerPhysicalToStimConfig]):
    """Pass that lowers physical circuit operations to stim operations."""

    name = "lower-physical-to-stim"
    empty_detectors_get_deleted: bool = True
    verify_all_stim: bool = False

    @override
    def apply(self, ctx, op: ModuleOp) -> None:
        # Delete any existing attributes added by this pass to ensure a clean slate
        _delete_existing_attributes(op)

        # Detector round prepass to assign round numbers and shifts
        length = _detector_round_prepass(op)

        # Get ids that already exist
        seen_qubit_ids = get_existing_qubit_ids(op)
        seen_obs_ids = _get_existing_observable_ids(op)

        # First inline circuits, remove qref ops and handle detector rounds
        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [
                    InlineCircuitPattern("Lower physical to stim"),
                    *get_physical_gate_rewrite_patterns(used_qubit_ids=seen_qubit_ids),
                    obs_pattern := _ObservablePattern(seen_obs_ids),
                    _MeasurementRoundPattern(),
                ],
                dce_enabled=True,
            )
        ).rewrite_module(op)

        # Removing qstruct.output is the only pattern that can have side effects on operations
        # that it does not directly traverse - it can trigger DCE, whereas the others cannot.
        # Therefore, the _ObservablePattern must be run again as it
        # will only remove ops if their results are not used, and it is possible that some results
        # are only unused after qstruct.output is removed and the resulting DCE is performed.
        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [
                    det_round_pattern := _DetectorRoundPattern(),
                    obs_pattern,
                    _QStructOutputPattern(),
                ],
                dce_enabled=True,
            )
        ).rewrite_module(op)

        # Replace detectors and repeats, add shift coordinates
        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [
                    _DetectorShiftPattern(length),
                    _DetectorPattern(self.empty_detectors_get_deleted),
                    _RepeatPattern(
                        det_round_pattern.block_arg_to_round_number,
                        obs_pattern.block_arg_to_obs_number,
                    ),
                ],
                dce_enabled=True,
            )
        ).rewrite_module(op)

        if self.verify_all_stim:
            _verify_all_stim(op)
