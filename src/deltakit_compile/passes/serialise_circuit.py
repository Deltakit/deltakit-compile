# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module containing a pass that serialises quantum operations."""

from dataclasses import dataclass

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Operation, SSAValue
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)

from deltakit_compile.dialects.qstruct import ParallelOp, YieldOp


class _SerialiseParallelsPattern(RewritePattern):
    """Replace each parallel op with the contents of its regions, inlined one after the other."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: ParallelOp, rewriter: PatternRewriter) -> None:
        # Gather containing ops and the SSAs yielded by each region
        contained_ops: list[Operation] = []
        yielded_ssas: list[SSAValue] = []
        for region in op.regions:
            for opn in region.block.ops:
                if isinstance(opn, YieldOp):
                    yielded_ssas.extend(opn.operands)
                else:
                    contained_ops.append(opn)
                    opn.detach()

        rewriter.replace_op(op, contained_ops, new_results=yielded_ssas)


@dataclass(frozen=True)
class SerialiseCircuit(ModulePass):
    """Pass that serialises quantum operations, removing all qstruct.parallel ops from the program.
    The parallel regions are serialised in the order they are listed."""

    name = "serialise-circuit"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        PatternRewriteWalker(_SerialiseParallelsPattern()).rewrite_module(op)
