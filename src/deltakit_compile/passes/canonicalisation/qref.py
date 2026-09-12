# (c) Copyright Riverlane 2025-2026. All rights reserved.
from typing_extensions import override
from xdsl.pattern_rewriter import PatternRewriter, RewritePattern, op_type_rewrite_pattern

from deltakit_compile.dialects import qcore
from deltakit_compile.dialects.qref import GateOp, ResetOp


class IdentityGateElimination(RewritePattern):
    """Removes GateOps that apply the IdentityGate."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: GateOp, rewriter: PatternRewriter) -> None:
        if op.gate == qcore.IdentityGateAttr():
            rewriter.erase_op(op)


class DeadGateBeforeReset(RewritePattern):
    """Removes single-qubit gates whose only effect is undone by an immediately following reset.

    The compiler lowers a measurement in a non-computational basis into a basis change, the
    measurement, and a basis change back. That trailing basis change is dead whenever the qubit is
    reset before anything else touches it, which is the common case in a syndrome extraction round.

    Only gates whose qubits are *all* being reset are removed, and only when nothing between the
    gate and the reset uses those qubits. Detectors and observables refer to measurement records
    rather than qubits, so they do not count as a use and do not block the removal.

    Broadcast gates are removed as a unit or not at all: a gate covering both reset and non-reset
    qubits is left alone rather than split, which keeps this pattern to a single decision.
    """

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: ResetOp, rewriter: PatternRewriter) -> None:
        clean = {qubit for group in op.qubit_operand_groups for qubit in group}
        if not clean:
            return

        previous = op.prev_op
        while previous is not None and clean:
            # An operation carrying a region uses the qubits it captures from the enclosing scope
            # without listing them as operands, so its operands say nothing about what it touches.
            # A repeat body that measures the qubit would otherwise be walked straight past.
            if previous.regions:
                return

            # A register operand may alias any of its qubits, and this pattern does not track
            # that, so it stops rather than guess.
            if any(isinstance(operand.type, qcore.QubitRegType) for operand in previous.operands):
                return

            touched = {
                operand
                for operand in previous.operands
                if isinstance(operand.type, qcore.QubitType)
            }

            if (
                isinstance(previous, GateOp)
                and touched
                and touched <= clean
                and all(len(group) == 1 for group in previous.qubit_operand_groups)
            ):
                rewriter.erase_op(previous)
                return

            clean -= touched
            previous = previous.prev_op
