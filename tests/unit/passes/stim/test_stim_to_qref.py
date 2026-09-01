# This file contains information which is proprietary to Riverlane Limited
# ("Riverlane") and is Riverlane Confidential Information.

# (c) Copyright Riverlane 2026. All rights reserved.
"""Tests for the StimToQrefPass."""

import pytest
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp, NoneAttr

from deltakit_compile.dialects import stim
from deltakit_compile.exceptions import LostStimTagWarning
from deltakit_compile.passes.stim.stim_to_qref import StimToQref
from deltakit_compile.shared.deltakit_stim.gates import SingleQubitUnitaryEnum

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _apply(ctx: Context, *ops: object) -> ModuleOp:
    """Wrap *ops in a ModuleOp, run StimToQref, and return the module.

    The module is NOT verified; qref ops placed at module level violate
    HasCircuitAncestor, and qubits remain as stim.QubitType until
    StimToQcore is run.  We only care that the correct op types were
    produced with the correct properties.
    """
    module = ModuleOp(list(ops))  # type: ignore[arg-type]
    StimToQref().apply(ctx, module)
    return module


def test_unknown_gate_raises(xdsl_context: Context) -> None:
    q = stim.QubitAllocOp(0)
    gate_op = stim.CliffordGateOp(SingleQubitUnitaryEnum.HXY, [q.res])
    with pytest.raises(NotImplementedError, match="Unsupported stim gate enum"):
        _apply(xdsl_context, q, gate_op)


def test_dropped_tag_warns(xdsl_context: Context) -> None:
    q1 = stim.QubitAllocOp(0)
    q2 = stim.QubitAllocOp(0)
    q3 = stim.QubitAllocOp(0)
    else_op = stim.CorrelatedErrorOp(
        [q1.res, q2.res], [stim.PauliOperatorEnum.Z, stim.PauliOperatorEnum.X], 0.1
    )
    else_op2 = stim.ElseCorrelatedErrorOp(
        [q3.res, q2.res, q1.res],
        [stim.PauliOperatorEnum.X, stim.PauliOperatorEnum.X, stim.PauliOperatorEnum.Y],
        0.2222222222222222,
    )
    else_op2.attributes["stim.tag"] = (
        NoneAttr()
    )  # Explicitly set to NoneAttr to trigger the warning

    with pytest.warns(
        match=(
            "One or more CorrelatedErrorOps in this chain have stim tags. They have not been copied"
            " to the resulting qref.PauliNoiseOp and have been dropped."
        ),
        expected_warning=LostStimTagWarning,
    ):
        _apply(xdsl_context, q1, q2, q3, else_op, else_op2)
