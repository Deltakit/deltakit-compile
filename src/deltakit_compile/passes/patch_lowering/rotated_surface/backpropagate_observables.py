# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Implementation of the :class:`.BackpropagateObservables` pass.

This module implements a minimum viable pass to back-propagate observables through
``log_asm.meas_stab`` operations and declare them at ``log_asm.measure`` operations.

The implementation will have to be substantially reworked to handle programs beyond a simple
memory experiment.
"""

from dataclasses import dataclass

from typing_extensions import override
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Operation
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    GreedyRewritePatternApplier,
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.rewriter import InsertPoint

from deltakit_compile.dialects.logical_assembly import (
    MeasStabOp,
    MeasureOp,
    PatchDeclarationOp,
    PrepareOp,
)
from deltakit_compile.dialects.sobs import DecUnplacedObservableOp, LocateUnplacedObservableOp
from deltakit_compile.exceptions import CompilerPassCheckError


class _MeasureOpPattern(RewritePattern):
    """Annotate an unplaced observable on the patch operated on by the measure operation.

    This pass will also insert a new ``DecUnplacedObservableOp`` at the beginning of the block
    containing the measure operation. The resulting observable SSA will be used in the locate
    operation on the input of the measure operation.
    """

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: MeasureOp, rewriter: PatternRewriter) -> None:
        # We only need to annotate the observable if it is not already annotated
        if any(
            isinstance(locate_op := uses.operation, LocateUnplacedObservableOp)
            and locate_op.patches == (op.patch,)
            for uses in op.patch.uses
        ):
            return
        # Declare the observable in the block containing the current operation.
        parent_block = op.parent_block()
        assert parent_block is not None
        declaration_op = DecUnplacedObservableOp()
        rewriter.insert_op(declaration_op, InsertPoint.at_start(parent_block))
        # Insert a sobs.locate_unplaced_observable operation.
        rewriter.insert_op(
            LocateUnplacedObservableOp([op.basis], declaration_op.result, [op.patch]),
            InsertPoint.before(rewriter.current_operation),
        )


class _MeasureStabiliserOpPattern(RewritePattern):
    """Copy all the unplaced observable annotations on the output patch to the input patch.

    This pass goes through each operation applied on the output patch of the matched ``meas_stab``
    operation. For each operation ``op`` that is a ``LocateUnplacedObservableOp`` it will:

    1. Check if there is already a matching ``LocateUnplacedObservableOp`` on the ``meas_stab``
       input, and if so early exit.
    2. If no matching ``LocateUnplacedObservableOp`` is found, it will insert a new operation on the
       input patch by:
       1. Inserting a new ``LocateUnplacedObservableOp`` operation on the input patch, with the same
          observable basis and the same input observable as ``op``.
       2. Replacing the input observable of ``op`` by the output observable of the newly inserted
          ``LocateUnplacedObservableOp`` operation to make sure that both operations are chained.
    """

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: MeasStabOp, rewriter: PatternRewriter) -> None:
        input_located_obs = frozenset(
            lop.result
            for uses in op.patch.uses
            if isinstance(lop := uses.operation, LocateUnplacedObservableOp)
        )
        for uses in op.res.uses:
            # We only care about locate operations on the resulting patch.
            if not isinstance(locate_op := uses.operation, LocateUnplacedObservableOp):
                continue
            # If there is already an observable annotation on the input patch, continue.
            if locate_op.obs in input_located_obs:
                continue
            # Insert a new LocateUnplacedObservableOp operation
            new_op_to_insert = LocateUnplacedObservableOp(
                locate_op.bases, locate_op.obs, [op.patch]
            )
            rewriter.insert_op(new_op_to_insert, InsertPoint.before(op))
            # Change the matched locate_op to be applied on the output of the newly inserted
            # operation.
            replacement_op = LocateUnplacedObservableOp(
                locate_op.bases, new_op_to_insert.result, [op.res]
            )
            rewriter.replace_op(locate_op, replacement_op)


@dataclass(frozen=True)
class _UnsupportedOpPattern(RewritePattern):
    """Raise a ``NotImplementedError`` on ``log_asm`` operations not matched by other patterns.

    This pattern will raise on any ``log_asm`` operation encountered. It can be used as the last
    pattern in a ``GreedyRewritePatternApplier`` to catch any operation that is not yet implemented
    and avoid silent failure.

    Attributes:
        supported_operations: a sequence of the supported operation types. Only operations that are
            defined in the ``log_asm`` dialect and not present in this sequence will raise.
    """

    supported_operations: tuple[type[Operation], ...] = (
        PatchDeclarationOp,
        PrepareOp,
        MeasStabOp,
        MeasureOp,
    )

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: Operation, rewriter: PatternRewriter) -> None:
        if op.dialect_name() == "log_asm" and not isinstance(op, self.supported_operations):
            msg = f"{type(op).__name__} is not yet supported."
            raise NotImplementedError(msg)


def _check_no_invalid_observable_on_prepare_output(op: ModuleOp) -> None:
    """Check that any ``sobs.locate_unplaced_observable`` operation on a patch output by a
    ``log_asm.prepare`` operation is in the prepare basis (else, that is a non-deterministic
    observable)."""
    for opn in op.walk():
        if not isinstance(opn, PrepareOp):
            continue
        basis, patch = opn.basis, opn.res
        for uses in patch.uses:
            if not isinstance(locate_op := uses.operation, LocateUnplacedObservableOp):
                continue
            locate_op_basis = locate_op.basis_on(patch)
            if locate_op_basis != basis:
                msg = (
                    f"Expected an observable in the basis {basis} on the patch due to the "
                    f"presence of a log_asm.prepare<{basis}> operation applied on that patch but "
                    f"got an observable in the basis {locate_op_basis}."
                )
                raise CompilerPassCheckError(msg)


@dataclass(frozen=True)
class BackpropagateObservables(ModulePass):
    """Backpropagate unplaced observables from logical measurements.

    Warning:
        This pass currently only supports simple memory experiments (``prepare`` -> ``meas_stab``
        -> ``measure``) with deterministic observable. Any other logical assembly operation is not
        handled by this pass and will fail.
    """

    name = "backpropagate-observables"

    @override
    def apply(self, ctx, op: ModuleOp) -> None:
        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [_MeasureOpPattern(), _MeasureStabiliserOpPattern(), _UnsupportedOpPattern()]
            ),
            walk_reverse=True,
        ).rewrite_region(op.body)
        _check_no_invalid_observable_on_prepare_output(op)
