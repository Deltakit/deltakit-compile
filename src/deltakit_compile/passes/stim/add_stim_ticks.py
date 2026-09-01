# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module containing a pass that adds stim ticks."""

from dataclasses import dataclass

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Block, Operation, Region
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
)
from xdsl.rewriter import InsertPoint

from deltakit_compile.dialects.qref import GateOp, MeasureOp, ResetOp
from deltakit_compile.dialects.qstruct import ParallelOp
from deltakit_compile.dialects.stim import TickAnnotationOp


class _NonRecursiveParallelWalker(PatternRewriteWalker):
    """Walker that does not recurse into ParallelOp regions."""

    @override
    def _populate_worklist(self, op: Operation | Region | Block) -> None:
        """Populate the worklist, but skip ParallelOp regions."""
        if isinstance(op, Operation):
            # Add the operation itself to the worklist
            self._worklist.push(op)

            # Only walk into regions if this is NOT a ParallelOp
            if not isinstance(op, ParallelOp):
                for region in op.regions:
                    self._populate_worklist(region)
        elif isinstance(op, Region):
            for block in reversed(op.blocks) if self.walk_reverse else op.blocks:
                self._populate_worklist(block)
        elif isinstance(op, Block):
            for sub_op in reversed(op.ops) if self.walk_reverse else op.ops:
                self._populate_worklist(sub_op)


def _contains_quantum_effects(op: Operation) -> bool:
    """Does an op contain a Gate, Reset or Measure op?"""
    for region in op.regions:
        for block in region.blocks:
            for opn in block.ops:
                if isinstance(opn, (GateOp, ResetOp, MeasureOp)):
                    return True
                if _contains_quantum_effects(opn):
                    return True
    return False


class _AddStimTicksPattern(RewritePattern):
    """Add stim ticks to the circuit."""

    @override
    def match_and_rewrite(self, op: Operation, rewriter: PatternRewriter) -> None:
        if isinstance(op, ParallelOp):
            if _contains_quantum_effects(op):
                rewriter.insert_op(
                    TickAnnotationOp(), InsertPoint.after(rewriter.current_operation)
                )
            return

        if isinstance(op, (GateOp, ResetOp, MeasureOp)):
            rewriter.insert_op(TickAnnotationOp(), InsertPoint.after(rewriter.current_operation))
        return


@dataclass(frozen=True)
class AddStimTicks(ModulePass):
    """Pass that adds stim ticks to the circuit.

    Adds ticks after:
        - Individual qref.gate, qref.reset, and qref.measure operations
        - qstruct.parallel operations containing quantum effects (recursively checked)

    Does not recurse into parallel regions; treats each parallel as a single unit."""

    name = "add-stim-ticks"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        _NonRecursiveParallelWalker(_AddStimTicksPattern(), apply_recursively=False).rewrite_module(
            op
        )
