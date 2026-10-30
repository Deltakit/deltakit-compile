# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module containing a pass that removes gates whose effect no later operation can observe."""

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

from deltakit_compile.dialects import qcore
from deltakit_compile.dialects.qref import GateOp, ResetOp


class _DeadGateBeforeResetPattern(RewritePattern):
    """Removes gates whose only effect is undone by an immediately following reset.

    The compiler lowers a measurement in a non-computational basis into a basis change, the
    measurement, and a basis change back. That trailing basis change is dead whenever the qubit is
    reset before anything else touches it, which is the common case in a syndrome extraction round.

    Only gates whose qubits are *all* being reset are removed, and only when nothing between the
    gate and the reset uses those qubits. That subset test is what makes the arity irrelevant: a
    gate acts on nothing beyond its own operands, so a two-qubit gate with both operands reset and
    untouched in between is as dead as a basis change. Detectors and observables refer to
    measurement records rather than qubits, so they do not count as a use and do not block the
    removal.

    Gates are removed as a unit or not at all: one covering both reset and non-reset qubits fails
    the subset test and is left alone rather than split.
    """

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: ResetOp, rewriter: PatternRewriter) -> None:
        clean = set(op.qubits)

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

            if isinstance(previous, GateOp) and touched and touched <= clean:
                rewriter.erase_op(previous)
                return

            clean -= touched
            previous = previous.prev_op


class RemoveDeadGates(ModulePass):
    """Remove gates whose effect no later operation in the circuit can observe.

    Currently one pattern: a gate immediately before a reset of every qubit it touches. The
    intent is that further cases, such as gates on qubits that are never measured, become patterns
    in this pass rather than separate ones.

    This is deliberately not a canonicalisation of the `qref` dialect. There a gate is a thing that
    occupies time and carries noise, so removing one does not normalise the representation of a
    circuit — it changes which circuit is described. That makes it an optimisation, and one the
    caller opts into.

    For the same reason it must run before noise is added: a noise channel attached to a gate that
    is later removed describes a gate that no longer exists. See Deltakit/deltakit#286.
    """

    name = "remove-dead-gates"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        # Recursive because erasing a gate can expose the one behind it: a body ending in two dead
        # basis changes needs a second look at the same reset. Each application erases an op, so
        # the walk terminates.
        PatternRewriteWalker(
            _DeadGateBeforeResetPattern(),
            apply_recursively=True,
        ).rewrite_module(op)
