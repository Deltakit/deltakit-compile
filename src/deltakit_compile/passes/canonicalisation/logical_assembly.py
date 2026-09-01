# (c) Copyright Riverlane 2025-2026. All rights reserved.
from typing_extensions import override
from xdsl.pattern_rewriter import PatternRewriter, RewritePattern, op_type_rewrite_pattern

from deltakit_compile.dialects.logical_assembly import CastOp


class RemoveIdentityCasts(RewritePattern):
    """Removes ``log_asm.CastOp`` that don't actually change the type."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: CastOp, rewriter: PatternRewriter) -> None:
        if op.in_.type == op.out.type:
            rewriter.replace_op(op, (), (op.in_,))


class RemoveRedundantCasts(RewritePattern):
    """Removes ``log_asm.CastOp`` that performs ``B -> A`` just after another ``log_asm.CastOp``
    doing ``A -> B``."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: CastOp, rewriter: PatternRewriter) -> None:
        if isinstance(prev_op := op.in_.owner, CastOp) and prev_op.in_.type == op.out.type:
            rewriter.replace_op(op, (), (prev_op.in_,))
