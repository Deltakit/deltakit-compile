# (c) Copyright Riverlane 2025-2026. All rights reserved.
from typing_extensions import override
from xdsl.pattern_rewriter import PatternRewriter, RewritePattern, op_type_rewrite_pattern

from deltakit_compile.dialects import qcore
from deltakit_compile.dialects.qref import GateOp


class IdentityGateElimination(RewritePattern):
    """Removes GateOps that apply the IdentityGate."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: GateOp, rewriter: PatternRewriter) -> None:
        if op.gate == qcore.IdentityGateAttr():
            rewriter.erase_op(op)
