# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Pass to split gate-like broadcast ops using qstruct.parallel."""

from dataclasses import dataclass

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    GreedyRewritePatternApplier,
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)

from deltakit_compile.dialects import qref, qstruct


class _SplitGateOpsPattern(RewritePattern):
    """RewritePattern that replaces broadcast qref.gate ops with qstruct.ParallelOp."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qref.GateOp, rewriter: PatternRewriter) -> None:
        if op.is_broadcast():
            rewriter.replace_op(
                op,
                qstruct.make_parallel_from_ops(
                    [qref.GateOp(op.gate, qubit_group) for qubit_group in op.get_operand_segments()]
                ),
            )


class _SplitMeasurementGateOpsPattern(RewritePattern):
    """RewritePattern that replaces broadcast qref.measure ops with qstruct.ParallelOp."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qref.MeasureOp, rewriter: PatternRewriter) -> None:
        if op.is_broadcast():
            # There are the same number of paulis and qubit groups by verification in the dialect
            rewriter.replace_op(
                op,
                qstruct.make_parallel_from_ops(
                    [
                        qref.MeasureOp(pauli.data, qubit_group, noise=op.noise)
                        for pauli, qubit_group in zip(
                            op.paulis, op.get_operand_segments(), strict=True
                        )
                    ]
                ),
            )


class _SplitResetGateOpsPattern(RewritePattern):
    """RewritePattern that replaces broadcast qref.reset ops with qstruct.ParallelOp."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qref.ResetOp, rewriter: PatternRewriter) -> None:
        if op.is_broadcast():
            rewriter.replace_op(
                op,
                qstruct.make_parallel_from_ops(
                    [qref.ResetOp(op.basis, qubit) for qubit in op.qubit_operand_groups]
                ),
            )


@dataclass(frozen=True)
class SplitGateLikeBroadcastOps(ModulePass):
    """Pass that splits broadcast qref gate-like ops into qstruct.ParallelOp regions.

    Walks a module and replaces any qref gate-like operation with the result of
    `convert_to_parallel_op`.
    """

    name = "split-gate-like-broadcast-ops"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [
                    _SplitGateOpsPattern(),
                    _SplitMeasurementGateOpsPattern(),
                    _SplitResetGateOpsPattern(),
                ]
            ),
            apply_recursively=False,
        ).rewrite_module(op)
