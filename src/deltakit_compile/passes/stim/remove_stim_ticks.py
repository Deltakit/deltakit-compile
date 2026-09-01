# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module containing a pass that removes stim ticks."""

from dataclasses import dataclass

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)

from deltakit_compile.dialects.stim import TickAnnotationOp


class _RemoveStimTicksPattern(RewritePattern):
    """Removes stim ticks from the circuit."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: TickAnnotationOp, rewriter: PatternRewriter) -> None:
        rewriter.erase_op(op)


@dataclass(frozen=True)
class RemoveStimTicks(ModulePass):
    """Pass that removes stim ticks from the circuit."""

    name = "remove-stim-ticks"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        PatternRewriteWalker(_RemoveStimTicksPattern(), apply_recursively=False).rewrite_module(op)
