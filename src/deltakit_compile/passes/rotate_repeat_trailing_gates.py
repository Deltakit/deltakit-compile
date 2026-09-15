# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module containing a pass that rotates self-inverse trailing gates out of repeat bodies."""

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Block
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.rewriter import InsertPoint

from deltakit_compile.dialects import qcore
from deltakit_compile.dialects.qref import GateOp
from deltakit_compile.dialects.qstruct import RepeatOp

_SELF_INVERSE = (
    qcore.IdentityGateAttr,
    qcore.XGateAttr,
    qcore.YGateAttr,
    qcore.ZGateAttr,
    qcore.HGateAttr,
)
"""Gates that are their own inverse, so that applying one twice is the identity.

Deliberately a list of named gates rather than a property of the attribute: the rotation below is
only sound for gates where G G = I, and getting that wrong changes the circuit silently. A gate
carrying options is excluded even when its base is on this list, since the options may change the
matrix.
"""


def _is_self_inverse(gate: qcore.GateAttribute) -> bool:
    return isinstance(gate, _SELF_INVERSE) and not gate.options.data


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

        # The copies placed outside the loop use the same values, so every operand has to be
        # defined outside the body. A value produced inside it, or carried by the loop as a block
        # argument, does not exist at the points where the copies go.
        defined_inside = set(op.body.walk())
        for operand in trailing.operands:
            owner = operand.owner
            if isinstance(owner, Block):
                if owner is block:
                    return
            elif owner in defined_inside:
                return

        before = trailing.clone()
        after = trailing.clone()

        trailing.detach()
        rewriter.insert_op(trailing, InsertPoint.at_start(block))
        rewriter.insert_op(before, InsertPoint.before(op))
        rewriter.insert_op(after, InsertPoint.after(op))


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
