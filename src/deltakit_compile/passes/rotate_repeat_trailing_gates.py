# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module containing a pass that rotates self-inverse trailing gates out of repeat bodies."""

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Block, BlockArgument, SSAValue
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.rewriter import InsertPoint

from deltakit_compile.dialects import qcore
from deltakit_compile.dialects import stabiliser as stab
from deltakit_compile.dialects.qref import GateOp, ResetOp
from deltakit_compile.dialects.qstruct import RepeatOp

_SELF_INVERSING_GATES = (
    qcore.IdentityGateAttr(),
    qcore.XGateAttr(),
    qcore.YGateAttr(),
    qcore.ZGateAttr(),
    qcore.HGateAttr(),
)
"""Gates that are their own inverse, so that applying one twice is the identity.

Deliberately a list of named gates rather than a property of the attribute: the rotation below is
only sound for gates where G G = I, and getting that wrong changes the circuit silently. Comparing
by equality also excludes a gate carrying options, such as a square root X, since those are not
equal to the plain gate.
"""


def _is_self_inverse(gate: qcore.GateAttribute) -> bool:
    return gate in _SELF_INVERSING_GATES


def _reset_follows_rotation(block: Block, trailing: GateOp) -> bool:
    """Whether the gate, once rotated to the start of the body, sits directly before a reset.

    The rotation only pays off when the copy at the start of the body can then be removed.
    Otherwise it turns N gates into N + 2. This is the same condition `remove-dead-gates` uses:
    the first operation in the body touching any qubit of the gate must be a single reset covering
    all of them. Operations carrying a region or a qubit register stop the search, since what they
    touch is not visible in their operands.
    """
    targets = set(trailing.qubits)
    for current in block.ops:
        if current is trailing or current.regions:
            return False
        if any(isinstance(operand.type, qcore.QubitRegType) for operand in current.operands):
            return False
        touched = {
            operand for operand in current.operands if isinstance(operand.type, qcore.QubitType)
        }
        if touched & targets:
            return isinstance(current, ResetOp) and targets <= touched
    return False


class _RotateTrailingGatePattern(RewritePattern):
    """Moves a self-inverse trailing gate from the end of a repeat body to its start.

    A round of syndrome extraction compiles to a body ending in the basis change that undoes the
    one before the measurement. Written out, the body is `B G` and the loop runs it N times:

        (B G)^N

    Since `G G = I`, that is the same circuit as

        G (G B)^N G

    which is a copy of `G` before the loop, a body starting with `G` instead of ending with it, and
    a copy of `G` after the loop. The gate count goes from N to 2, and the one now at the start of
    the body sits directly before the reset that opens the round, where `DeadGateBeforeReset`
    removes it.

    The two copies left outside the loop are dead in the same sense but are not removed here, since
    that needs a pattern that looks across the loop boundary.

    The rotation is only applied when the gate would land directly before such a reset. Without
    that, the body keeps its N copies and the loop gains two more.

    When the gate acts on a qubit the loop carries as a block argument, the copies use the matching
    iter arg and result instead, which name the same qubit outside the body. A gate acting on a
    value produced inside the body cannot be lifted out and is left where it is.
    """

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: RepeatOp, rewriter: PatternRewriter) -> None:
        block = op.body.block
        trailing = op.yield_op.prev_op

        if not isinstance(trailing, GateOp):
            return
        if not _is_self_inverse(trailing.gate):
            return
        if not all(len(group) == 1 for group in trailing.qubit_operand_groups):
            return
        if not _reset_follows_rotation(block, trailing):
            return

        # The copies go before and after the loop, where the body's own block arguments do not
        # exist. A block argument stands for a qubit threaded through the loop, so at that index the
        # same qubit is the iter arg feeding the loop (before) and the result leaving it (after);
        # RepeatOp keeps those in positional correspondence. Following the index lets the copies
        # name the qubit at each point.
        #
        # A value produced inside the body, on the other hand, exists nowhere outside it, so a gate
        # touching one cannot be lifted out at all.
        before_qubits: list[SSAValue] = []
        after_qubits: list[SSAValue] = []
        for operand in trailing.qubits:
            if isinstance(operand, BlockArgument) and operand.owner is block:
                before_qubits.append(op.iter_args[operand.index])
                after_qubits.append(op.res[operand.index])
            elif op.is_ancestor(operand.owner):
                return
            else:
                before_qubits.append(operand)
                after_qubits.append(operand)

        before = GateOp(trailing.gate, before_qubits)
        after = GateOp(trailing.gate, after_qubits)

        trailing.detach()
        rewriter.insert_op(trailing, InsertPoint.at_start(block))
        rewriter.insert_op(before, InsertPoint.before(op))
        rewriter.insert_op(after, InsertPoint.after(op))

        # The rotation changes which gates the circuit applies, so any flow information computed
        # earlier and cached on the circuit no longer describes it. Drop it rather than let a later
        # pass trust a stale copy; recomputing it is that pass's job.
        circuit = qcore.HasCircuitAncestor.get_circuit_ancestor(op)
        if circuit is not None and stab.ConcreteFlowArrayAttr.get(circuit) is not None:
            del circuit.attributes[stab.ConcreteFlowArrayAttr.KEY]
            rewriter.notify_op_modified(circuit)


class RotateRepeatTrailingGates(ModulePass):
    """Rotate self-inverse gates at the end of a repeat body to the start of the body.

    Implements the transformation described in Deltakit/deltakit#286. The gate at the end of a
    syndrome extraction round is dead, but it cannot be removed where it stands because the last
    iteration flows into whatever follows the loop. Rotating it to the start of the body puts it
    directly before the round's reset, where a dead gate removal pass can drop it.

    This must run before noise is added. A noise channel attached to a gate that is later removed
    describes a gate that no longer exists.
    """

    name = "rotate-repeat-trailing-gates"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        PatternRewriteWalker(
            _RotateTrailingGatePattern(),
            apply_recursively=False,
        ).rewrite_module(op)
