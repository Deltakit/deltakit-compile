# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for the Rewrite patterns that canonicalise parts of the qcore dialect."""

from typing_extensions import override
from xdsl.pattern_rewriter import PatternRewriter, RewritePattern, op_type_rewrite_pattern

from deltakit_compile.dialects import qcore


class RemoveRedundantConcatenate(RewritePattern):
    """Removes ConcatenateOps that don't actually concatenate anything."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qcore.ConcatenateOp, rewriter: PatternRewriter) -> None:
        if len(op.in_regs) == 1:
            rewriter.replace_op(op, [], op.in_regs)


class RemoveRedundantConcatenateAfterSplit(RewritePattern):
    """Removes ConcatenateOps that return registers that were just split."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qcore.ConcatenateOp, rewriter: PatternRewriter) -> None:
        if (
            len(owners := {reg.owner for reg in op.in_regs}) == 1  # all inputs are from the same op
            and isinstance(split := owners.pop(), qcore.SplitOp)  # and that op is a qcore.split
            and split.out_regs == op.in_regs  # and the results/arguments match perfectly
        ):
            assert split.in_reg.type == op.out_reg.type
            rewriter.replace_op(op, [], [split.in_reg])


class RemoveRedundantSplit(RewritePattern):
    """Removes SplitOps that don't actually split anything."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qcore.SplitOp, rewriter: PatternRewriter) -> None:
        if len(op.out_regs) == 1:
            rewriter.replace_op(op, [], [op.in_reg])


class RemoveRedundantSplitAfterConcatenate(RewritePattern):
    """Removes SplitOps that return registers that were just concatenated."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qcore.SplitOp, rewriter: PatternRewriter) -> None:
        if (
            isinstance(op.in_reg.owner, qcore.ConcatenateOp)
            and op.in_reg.owner.in_regs.types == op.out_regs.types
        ):
            rewriter.replace_op(op, [], op.in_reg.owner.in_regs)


class RemoveRedundantUnpackAfterPack(RewritePattern):
    """Removes UnpackQubitRegOps that returns qubits that were just packed."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qcore.UnpackQubitRegOp, rewriter: PatternRewriter) -> None:
        if isinstance(op.reg.owner, qcore.PackQubitRegOp):
            # If the operand is defined by a PackQubitRegOp, we can replace the UnpackQubitRegOp
            # results directly with the PackQubitRegOp operands (the individual qubits)
            rewriter.replace_op(op, [], op.reg.owner.qubits)


class RemoveRedundantPackAfterUnpack(RewritePattern):
    """Removes PackQubitRegOps that returns a qubit reg that was just unpacked."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qcore.PackQubitRegOp, rewriter: PatternRewriter) -> None:
        owner = op.qubits[0].owner
        if isinstance(owner, qcore.UnpackQubitRegOp) and op.qubits == owner.qubits:
            # If the operands are an exact copy of the results of an UnpackQubitRegOp, we can
            # replace the PackQubitRegOp directly with the UnpackQubitRegOp operand qubit reg
            rewriter.replace_op(op, [], (owner.reg,))
