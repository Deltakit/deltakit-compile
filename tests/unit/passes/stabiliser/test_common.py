"""Tests for the stabiliser dialect common file."""

import re
from collections.abc import Iterable, Sequence
from typing import Literal, cast

import numpy as np
import pytest
from xdsl.dialects import test
from xdsl.dialects.builtin import I1, ArrayAttr, IntegerType, ModuleOp, Signedness, i1
from xdsl.ir import Attribute, Block, Operation, Region, SSAValue
from xdsl.pattern_rewriter import PatternRewriter

from deltakit_compile.dialects import qcore, qec, qref, qstruct
from deltakit_compile.dialects.stabiliser import (
    CircuitOp,
    FlowAttr,
    StateCastOp,
    StateMakeOp,
    StatePermuteOp,
    StateType,
    YieldOp,
)
from deltakit_compile.exceptions import BadUserFlowError
from deltakit_compile.passes.stabiliser._common import (
    CalculateFlows,
    CircuitFlowData,
    CliffordFlows,
    CurrentState,
    CurrentStates,
    FlowChainInfo,
    FlowInSpanStatus,
    MatchFlows,
    MMTResults,
    WriteFlows,
    apply_flow,
    backpropagate_observable,
    check_row_in_span,
    get_reduced_flow_state,
    update_state_type_adjacent_ops,
)
from tests.unit.conftest import DEFAULT_UINT_SIZE


@pytest.mark.parametrize(
    ("num_qubits", "flow_state_list", "symplectic_form"),
    [
        (2, [[("X", 0)]], np.array([[1, 0, 0, 0]], dtype=int)),
        (2, [[("X", 0), ("Y", 1)]], np.array([[1, 1, 0, 1]], dtype=int)),
        (
            3,
            [[("X", 0)], [("Z", 1), ("Y", 2)]],
            np.array([[1, 0, 0, 0, 0, 0], [0, 0, 1, 0, 1, 1]], dtype=int),
        ),
        # Empty identity stabiliser on 1 qubit -> zero row
        (1, [[]], np.array([[0, 0]], dtype=int)),
        # Mixed positions on 3 qubits: Z0 + X2 -> X-bits [0,0,1], Z-bits [1,0,0]
        (
            3,
            [[("Z", 0), ("X", 2)]],
            np.array([[0, 0, 1, 1, 0, 0]], dtype=int),
        ),
        # Multiple rows including Y on different positions
        (
            3,
            [[("Y", 0)], [("X", 1)], [("Z", 2)]],
            np.array([[1, 0, 0, 1, 0, 0], [0, 1, 0, 0, 0, 0], [0, 0, 0, 0, 0, 1]], dtype=int),
        ),
    ],
)
def test_symplectic_form(num_qubits, flow_state_list, symplectic_form):
    """Test symplectic form computation."""
    computed = MatchFlows.flow_state_symplectic(
        num_qubits, [qcore.PauliStringAttr(qs, num_qubits) for qs in flow_state_list]
    )
    # Convert GF2 to numpy int array for comparison
    computed_np = np.asarray(computed, dtype=int)
    assert np.array_equal(computed_np, symplectic_form)


@pytest.mark.parametrize(
    ("old_flow_states", "new_flow_states", "expected_transform", "not_in_span"),
    [
        (
            [qcore.PauliStringAttr([("X", 1)], 2), qcore.PauliStringAttr([("Y", 1)], 2)],
            [qcore.PauliStringAttr([("Z", 1)], 2)],
            [[1, 1]],
            [],
        ),
        (
            [qcore.PauliStringAttr([("X", 1)], 2), qcore.PauliStringAttr([("X", 0), ("X", 1)], 2)],
            [qcore.PauliStringAttr([("Z", 1)], 2)],
            [[0, 0]],
            [0],
        ),
        (
            [qcore.PauliStringAttr([("X", 1)], 2), qcore.PauliStringAttr([("X", 0), ("X", 1)], 2)],
            [qcore.PauliStringAttr([("X", 0)], 1), qcore.PauliStringAttr([("Z", 1)], 2)],
            [[1, 1], [0, 0]],
            [1],
        ),
        # Identity transform: old equals new
        (
            [qcore.PauliStringAttr([("X", 0)], 1)],
            [qcore.PauliStringAttr([("X", 0)], 1)],
            [[1]],
            [],
        ),
        # New is sum (mod 2) of olds on the same qubit: X + Z -> Y
        (
            [qcore.PauliStringAttr([("X", 0)], 1), qcore.PauliStringAttr([("Z", 0)], 1)],
            [qcore.PauliStringAttr([("Y", 0)], 1)],
            [[1, 1]],
            [],
        ),
        # Multiple new rows: some in span, some not
        (
            [qcore.PauliStringAttr([("X", 1)], 2), qcore.PauliStringAttr([("Z", 1)], 2)],
            [
                qcore.PauliStringAttr([("X", 1)], 2),
                qcore.PauliStringAttr([("Y", 1)], 2),
                qcore.PauliStringAttr([("X", 0)], 1),
            ],
            [[1, 0], [1, 1], [0, 0]],
            [2],
        ),
        # Basis on two qubits; express combined new flows
        (
            [qcore.PauliStringAttr([("X", 0)], 1), qcore.PauliStringAttr([("Z", 1)], 2)],
            [qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2), qcore.PauliStringAttr([("X", 0)], 1)],
            [[1, 1], [1, 0]],
            [],
        ),
    ],
)
def test_linear_transform(old_flow_states, new_flow_states, expected_transform, not_in_span):
    """Test linear transform between old and new flow state sets."""
    expected_transform_np = np.array(expected_transform, dtype=int)
    computed = MatchFlows.find_linear_transform(old_flow_states, new_flow_states)
    assert np.array_equal(computed[0], expected_transform_np)
    assert computed[1] == not_in_span


@pytest.mark.parametrize(
    ("old_flow_states", "new_flow_states", "err_msg"),
    [
        ([], [], "Both lists of flow states provided must be non-empty."),
        (
            [],
            [qcore.PauliStringAttr([("X", 0)], 1)],
            "Both lists of flow states provided must be non-empty.",
        ),
        (
            [qcore.PauliStringAttr([("X", 0)], 1)],
            [],
            "Both lists of flow states provided must be non-empty.",
        ),
        (
            [qcore.PauliStringAttr.identity(1)],
            [qcore.PauliStringAttr([("X", 0)], 1)],
            "Old flow states should not contain the identity.",
        ),
        (
            [qcore.PauliStringAttr.identity(1), qcore.PauliStringAttr([("X", 0)], 1)],
            [qcore.PauliStringAttr([("X", 0)], 1)],
            "Old flow states should not contain the identity.",
        ),
    ],
)
def test_linear_transform_err_msg(old_flow_states, new_flow_states, err_msg):
    """Test empty lists input produce an error message."""
    with pytest.raises(ValueError, match=err_msg):
        MatchFlows.find_linear_transform(old_flow_states, new_flow_states)


def test_check_row_in_span_dimension_mismatch():
    """Dimension mismatch should raise ValueError."""
    basis = MatchFlows.flow_state_symplectic(2, [qcore.PauliStringAttr([("X", 0)], 2)])  # width 4
    row = MatchFlows.flow_state_symplectic(
        1,
        [qcore.PauliStringAttr([("X", 0)], 1)],
    )[0, :]  # width 2
    with pytest.raises(
        ValueError, match=re.escape("Row and basis matrix given have different row lengths.")
    ):
        check_row_in_span(basis, row)


@pytest.mark.parametrize(
    ("num_qubits", "basis_specs", "row_specs", "expected_coeffs"),
    [
        # Row is in span: Y0 is X0 + Z0 in 1-qubit symplectic space
        (
            1,
            [[("X", 0)], [("Z", 0)]],
            [("Y", 0)],
            [1, 1],
        ),
        # Row not in span: Z0 not in span of {X0}
        (
            1,
            [[("X", 0)]],
            [("Z", 0)],
            None,
        ),
        # Row equals one of basis rows -> unit coefficient vector
        (
            2,
            [[("X", 0)], [("Z", 0)], [("X", 1)]],
            [("X", 1)],
            [0, 0, 1],
        ),
        # Empty basis with zero row -> empty coefficient vector
        (
            1,
            [],
            [],
            [],
        ),
        # Row is identity flow, no linear dependencies in basis
        (2, [[("X", 0)], [("Z", 1)]], [], [0, 0]),
        # Row is identity flow but there are linear dependencies in basis
        (1, [[("X", 0)], [("X", 0)]], [], [0, 0]),
        # Linear dependencies in basis but row is not identity
        (
            2,
            [[("X", 0)], [("X", 1)], [("X", 0), ("X", 1)]],
            [("X", 0), ("X", 1)],
            [1, 1, 0],
        ),
        # Linear dependencies in basis in different order but row is not identity
        # expect different result
        (
            2,
            [
                [("X", 0), ("X", 1)],
                [("X", 0)],
                [("X", 1)],
            ],
            [("X", 0), ("X", 1)],
            [1, 0, 0],
        ),
    ],
)
def test_check_row_in_span(num_qubits, basis_specs, row_specs, expected_coeffs):
    """Parametrized tests for check_row_in_span without error conditions."""
    basis_states = [qcore.PauliStringAttr(spec, num_qubits) for spec in basis_specs]
    row_state = qcore.PauliStringAttr(row_specs, num_qubits)
    basis = MatchFlows.flow_state_symplectic(num_qubits, basis_states)
    row = MatchFlows.flow_state_symplectic(num_qubits, [row_state])[0, :]

    coeffs = check_row_in_span(basis, row)
    if expected_coeffs is None:
        assert coeffs is None
    else:
        assert coeffs is not None
        # expected_coeffs may be empty (length 0)
        assert np.array_equal(np.asarray(coeffs, dtype=int), np.array(expected_coeffs, dtype=int))


@pytest.mark.parametrize(
    ("flow_states", "flag_idx"),
    [
        # Linearly independent. Expect no removable unflagged states and no dependency witnesses.
        (
            [
                qcore.PauliStringAttr([("X", 0)], 1),
                qcore.PauliStringAttr([("X", 1)], 2),
                qcore.PauliStringAttr([("X", 2)], 3),
            ],
            3,
        ),
        (
            [
                qcore.PauliStringAttr([("X", 0)], 1),
                qcore.PauliStringAttr([("X", 1)], 2),
                qcore.PauliStringAttr([("X", 2)], 3),
            ],
            0,
        ),
        (
            [
                qcore.PauliStringAttr([("X", 0)], 1),
                qcore.PauliStringAttr([("X", 1)], 2),
                qcore.PauliStringAttr([("X", 2)], 3),
            ],
            1,
        ),
        ([], 0),  # Should not error on empty input
    ],
)
def test_find_linearly_dependent_flow_states_with_flags_independent(flow_states, flag_idx):
    """Independent input sets should not produce removable states or dependency witnesses."""
    lin_dep = MatchFlows.find_linearly_dependent_flow_states_with_flags(
        flow_states=flow_states, flag_idx=flag_idx
    )
    assert lin_dep.flow_states == set()
    assert lin_dep.lin_dependencies == set()


@pytest.mark.parametrize(
    (
        "flow_states",
        "flag_idx",
        "expected_removable",
        "expected_required_witnesses",
    ),
    [
        # Dependency: X0 * X1 * (X0X1) = I.
        # With all states unflagged, the smallest index in the dependency is removable.
        (
            [
                qcore.PauliStringAttr([("X", 0)], 1),
                qcore.PauliStringAttr([("X", 1)], 2),
                qcore.PauliStringAttr([("X", 0), ("X", 1)], 2),
                qcore.PauliStringAttr([("Z", 1)], 2),
            ],
            4,
            {qcore.PauliStringAttr([("X", 0)], 1)},
            {
                frozenset(
                    {
                        qcore.PauliStringAttr([("X", 0)], 1),
                        qcore.PauliStringAttr([("X", 1)], 2),
                        qcore.PauliStringAttr([("X", 0), ("X", 1)], 2),
                    }
                )
            },
        ),
        # Same list, but everything flagged -> we should still see the witness,
        # but no unflagged removable state.
        (
            [
                qcore.PauliStringAttr([("X", 0)], 1),
                qcore.PauliStringAttr([("X", 1)], 2),
                qcore.PauliStringAttr([("X", 0), ("X", 1)], 2),
                qcore.PauliStringAttr([("Z", 1)], 2),
            ],
            0,
            set(),
            {
                frozenset(
                    {
                        qcore.PauliStringAttr([("X", 0)], 1),
                        qcore.PauliStringAttr([("X", 1)], 2),
                        qcore.PauliStringAttr([("X", 0), ("X", 1)], 2),
                    }
                )
            },
        ),
        # Reordered: place (X0X1) first, so it's the smallest index in the dependency.
        # With only element 0 unflagged, we should remove (X0X1).
        (
            [
                qcore.PauliStringAttr([("X", 0), ("X", 1)], 2),
                qcore.PauliStringAttr([("X", 0)], 1),
                qcore.PauliStringAttr([("X", 1)], 2),
                qcore.PauliStringAttr([("Z", 1)], 2),
            ],
            1,
            {qcore.PauliStringAttr([("X", 0), ("X", 1)], 2)},
            {
                frozenset(
                    {
                        qcore.PauliStringAttr([("X", 0), ("X", 1)], 2),
                        qcore.PauliStringAttr([("X", 0)], 1),
                        qcore.PauliStringAttr([("X", 1)], 2),
                    }
                )
            },
        ),
        # Same reorder, but smallest-index state is flagged now.
        (
            [
                qcore.PauliStringAttr([("X", 0), ("X", 1)], 2),
                qcore.PauliStringAttr([("X", 0)], 1),
                qcore.PauliStringAttr([("X", 1)], 2),
                qcore.PauliStringAttr([("Z", 1)], 2),
            ],
            0,
            set(),
            {
                frozenset(
                    {
                        qcore.PauliStringAttr([("X", 0), ("X", 1)], 2),
                        qcore.PauliStringAttr([("X", 0)], 1),
                        qcore.PauliStringAttr([("X", 1)], 2),
                    }
                )
            },
        ),
    ],
)
def test_find_linearly_dependent_flow_states_with_flags_dependent(
    flow_states,
    flag_idx,
    expected_removable,
    expected_required_witnesses,
):
    """Dependent inputs should yield at least the expected witness, and the expected removable
    (unflagged) flow state when applicable.
    """
    lin_dep = MatchFlows.find_linearly_dependent_flow_states_with_flags(
        flow_states=flow_states, flag_idx=flag_idx
    )
    assert lin_dep.flow_states == expected_removable
    # Row-reduction may produce additional dependencies; require at least the expected witness.
    assert expected_required_witnesses == lin_dep.lin_dependencies


def test_find_linearly_dependent_flow_states_with_flags_error():
    """The correct error should be raised if any flow state is identity."""
    with pytest.raises(
        ValueError,
        match=re.escape("Flow state list given contains an identity state which is not supported."),
    ):
        MatchFlows.find_linearly_dependent_flow_states_with_flags(
            flow_states=[qcore.PauliStringAttr.identity(1), qcore.PauliStringAttr([("X", 0)], 1)],
            flag_idx=0,
        )


@pytest.mark.parametrize(
    ("flow", "idx_list", "expected"),
    [
        (
            qcore.PauliStringAttr([("X", 0), ("Y", 1), ("Z", 2)], 3),
            [1, 2],
            qcore.PauliStringAttr([("Y", 1), ("Z", 2)], 3),
        ),
        (
            qcore.PauliStringAttr([("X", 0), ("Y", 1), ("Z", 2)], 3),
            [2],
            qcore.PauliStringAttr([("Z", 2)], 3),
        ),
        (qcore.PauliStringAttr([("X", 0), ("Y", 1)], 2), [], qcore.PauliStringAttr.identity(2)),
        (qcore.PauliStringAttr([("X", 0), ("Y", 1)], 2), [3, 4], qcore.PauliStringAttr.identity(2)),
        (qcore.PauliStringAttr.identity(2), [0, 1], qcore.PauliStringAttr.identity(2)),
    ],
)
def test_get_reduced_flow_state(flow, idx_list, expected):
    """Parametrized tests for get_reduced_flow_state; identity when no indices overlap."""
    reduced = get_reduced_flow_state(flow, idx_list)
    assert reduced == expected


def test_apply_flow_clifford_h_maps_x_to_z():
    """H on local X0 should map to Z0 and relabel appropriately."""
    # Build a single-qubit gate over a block arg (to provide indices)
    body = Block(arg_types=[qcore.QubitType()])
    (q0,) = body.args
    gate = qref.GateOp(qcore.HGateAttr(), [q0])
    result = apply_flow(gate, body.args, qcore.PauliStringAttr([("X", 0)], 1))
    assert result == [(qcore.PauliStringAttr([("Z", 0)], 1), None)]


def test_apply_flow_clifford_s_maps_x_to_y():
    """S on local X0 should map to Y0."""
    body = Block(arg_types=[qcore.QubitType()])
    (q0,) = body.args
    gate = qref.GateOp(qcore.SGateAttr(), [q0])
    result = apply_flow(gate, body.args, qcore.PauliStringAttr([("X", 0)], 1))
    assert result == [(qcore.PauliStringAttr([("Y", 0)], 1), None)]


def test_apply_flow_two_qubit_cx_maps_x1_to_x1():
    """CX with targets [q0,q1] keeps local X on target unchanged (generator mapping)."""
    body = Block(arg_types=[qcore.QubitType(), qcore.QubitType()])
    q0, q1 = body.args
    gate = qref.GateOp(qcore.CXGateAttr(), [q0, q1])
    result = apply_flow(gate, body.args, qcore.PauliStringAttr([("X", 1)], 2))
    assert result == [(qcore.PauliStringAttr([("X", 1)], 2), None)]


def test_apply_flow_swap_maps_z0_to_z1():
    """SWAP should exchange indices of single-qubit local flows."""
    body = Block(arg_types=[qcore.QubitType(), qcore.QubitType()])
    q0, q1 = body.args
    gate = qref.GateOp(qcore.SWAPGateAttr(), [q0, q1])
    result = apply_flow(gate, body.args, qcore.PauliStringAttr([("Z", 0)], 2))
    assert result == [(qcore.PauliStringAttr([("Z", 1)], 2), None)]


def test_apply_flow_iswap_maps_z1_to_z0():
    """ISWAP should map local Z on index 1 to Z on index 0 per table."""
    body = Block(arg_types=[qcore.QubitType(), qcore.QubitType()])
    q0, q1 = body.args
    gate = qref.GateOp(qcore.ISWAPGateAttr(), [q0, q1])
    result = apply_flow(gate, body.args, qcore.PauliStringAttr([("Z", 1)], 2))
    assert result == [(qcore.PauliStringAttr([("Z", 0)], 2), None)]


def test_apply_flow_clifford_on_identity_returns_identity():
    """Applying any Clifford to the identity flow should return identity with no record."""
    body = Block(arg_types=[qcore.QubitType()])
    (q0,) = body.args
    gate = qref.GateOp(qcore.HGateAttr(), [q0])
    result = apply_flow(gate, body.args, qcore.PauliStringAttr.identity(1))
    assert result == [(qcore.PauliStringAttr.identity(1), None)]


def test_apply_flow_measurement_blocked_x_measured_z_returns_empty():
    """Measuring Z on a qubit with X flow blocks propagation for that branch."""
    body = Block(arg_types=[qcore.QubitType(), qcore.QubitType()])
    q1 = body.args[1]
    gate = qref.MeasureOp("Z", [q1])
    flow = qcore.PauliStringAttr([("Z", 0), ("X", 1)], 2)
    branches = apply_flow(gate, body.args, flow)
    assert isinstance(branches, list)
    assert not branches


def test_apply_flow_reset_on_identity_branches():
    """Reset on identity now branches: I -> Z0 and I -> I (no measurements)."""
    body = Block(arg_types=[qcore.QubitType()])
    (q0,) = body.args
    gate = qref.ResetOp("Z", [q0])
    branches = apply_flow(gate, body.args, qcore.PauliStringAttr.identity(1))
    states = {fs for (fs, _) in branches}
    assert states == {qcore.PauliStringAttr([("Z", 0)], 1), qcore.PauliStringAttr.identity(1)}
    # No measurement records on resets
    assert all(mmt is None for (_, mmt) in branches)


def test_apply_flow_reset_blocked_when_overlap():
    """Reset should be blocked when the flow overlaps the reset target."""
    body = Block(arg_types=[qcore.QubitType()])
    (q0,) = body.args
    gate = qref.ResetOp("Z", [q0])
    # Overlapping X on the same qubit => local flow not empty, so reset is blocked
    result = apply_flow(gate, body.args, qcore.PauliStringAttr([("X", 0)], 1))
    assert not result


def test_apply_flow_reset_appending_z_on_targets():
    """Reset: keep original flow and add Z on identity-local targets."""
    body = Block(arg_types=[qcore.QubitType(), qcore.QubitType(), qcore.QubitType()])
    _, _, q2 = body.args
    gate = qref.ResetOp("Z", [q2])
    flow = qcore.PauliStringAttr([("X", 0), ("X", 1)], 3)
    branches = apply_flow(gate, body.args, flow)
    states = {fs for (fs, _) in branches}
    assert states == {
        qcore.PauliStringAttr([("X", 0), ("X", 1)], 3),
        qcore.PauliStringAttr([("X", 0), ("X", 1), ("Z", 2)], 3),
    }
    assert all(mmt is None for (_, mmt) in branches)


def test_apply_flow_multi_qubit_reset_errors():
    """Test that a multi-qubit reset raises an error because it is not supported."""
    body = Block(arg_types=[qcore.QubitType(), qcore.QubitType()])
    q0, q1 = body.args
    gate = qref.ResetOp("Z", [q0, q1])
    with pytest.raises(
        NotImplementedError,
        match=re.escape("Flow propagation does not support multi-qubit reset gates!"),
    ):
        apply_flow(gate, body.args, qcore.PauliStringAttr.identity(2))


def test_apply_flow_measurement_x_on_x_branches_with_flags():
    """Measuring X on local X returns two branches: keep X (no record) and identity (record)."""
    body = Block(arg_types=[qcore.QubitType()])
    (q0,) = body.args
    gate = qref.MeasureOp("X", [q0])
    flow = qcore.PauliStringAttr([("X", 0)], 1)
    branches = apply_flow(gate, body.args, flow)
    assert isinstance(branches, list)
    # Expect exactly two branches
    assert len(branches) == 2
    states = {b[0] for b in branches}
    assert qcore.PauliStringAttr([("X", 0)], 1) in states
    assert qcore.PauliStringAttr.identity(1) in states
    # One branch records (True), the other does not (False)
    assert None in (b[1] for b in branches)
    assert set(gate.measurements) in (b[1] for b in branches)


@pytest.mark.parametrize(
    ("flow", "mmt"),
    [
        (qcore.PauliStringAttr([("X", 0)], 4), MMTResults()),
        (qcore.PauliStringAttr([("Z", 2)], 4), None),
        (qcore.PauliStringAttr([("Y", 1), ("Z", 3)], 4), MMTResults()),
    ],
)
def test_current_state_multiplication_self_trivial(flow, mmt):
    """Multiplying a CurrentState by itself yields identity flow and trivial measurement history."""
    cs = CurrentState(flow, mmt)
    prod = cs * cs
    assert prod.flow_state == qcore.PauliStringAttr.identity(4)
    # If both inputs had None, result stays None; if sets, symmetric difference yields empty set
    if mmt is None:
        assert prod.mmt_ssa is None
    else:
        assert prod.mmt_ssa == MMTResults()


@pytest.mark.parametrize(
    ("flow1_spec", "mmt1", "flow2_spec", "mmt2", "expected_flow_spec", "expected_mmt"),
    [
        # Disjoint flows; sets symmetric difference
        ([("X", 0)], {"a"}, [("Z", 1)], {"b"}, [("X", 0), ("Z", 1)], {"a", "b"}),
        # Overlap same Pauli cancels; empty vs non-empty adopts non-empty
        ([("Z", 0)], set(), [("Z", 0)], {"a"}, [], {"a"}),
        # Overlap different Pauli -> third; None vs non-empty adopts non-empty
        ([("X", 0)], None, [("Z", 0)], {"b"}, [("Y", 0)], {"b"}),
        # Both non-empty with shared element -> symmetric difference keeps the non-shared
        ([("X", 0)], {"a"}, [("Z", 0)], {"a", "b"}, [("Y", 0)], {"b"}),
        # None vs empty set -> empty set
        ([("X", 0)], None, [("Z", 1)], set(), [("X", 0), ("Z", 1)], set()),
    ],
)
def test_current_state_multiplication_varied_cases(
    flow1_spec, mmt1, flow2_spec, mmt2, expected_flow_spec, expected_mmt
):
    """Non-trivial multiplication cases covering disjoint/overlapping flows
    and measurement history semantics."""
    test_ssa_a = test.TestOp(result_types=[I1]).results[0]
    test_ssa_b = test.TestOp(result_types=[I1]).results[0]
    names_to_ssa = {"a": test_ssa_a, "b": test_ssa_b}

    mmt_ssa1 = MMTResults(names_to_ssa[name] for name in mmt1) if mmt1 is not None else None
    mmt_ssa2 = MMTResults(names_to_ssa[name] for name in mmt2) if mmt2 is not None else None
    expected_ssa = MMTResults(names_to_ssa[name] for name in expected_mmt)

    cs1 = CurrentState(qcore.PauliStringAttr(flow1_spec, 2), mmt_ssa1)
    cs2 = CurrentState(qcore.PauliStringAttr(flow2_spec, 2), mmt_ssa2)

    prod = cs1 * cs2
    assert prod.flow_state == qcore.PauliStringAttr(expected_flow_spec, 2)
    assert prod.mmt_ssa == expected_ssa


@pytest.mark.parametrize(
    ("mmt_gate_pauli", "flow", "is_blocked", "expected_other_pauli"),
    [
        (
            "XX",
            qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 2),
            False,
            qcore.PauliStringAttr([("Y", 0), ("Y", 1)], 2),
        ),
        ("XZ", qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 2), True, None),
        (
            "XZ",
            qcore.PauliStringAttr([("Y", 0), ("X", 1)], 2),
            False,
            qcore.PauliStringAttr([("Z", 0), ("Y", 1)], 2),
        ),
        ("YY", qcore.PauliStringAttr([("Y", 0)], 2), False, qcore.PauliStringAttr([("Y", 1)], 2)),
    ],
)
def test_multi_pauli_measurement_op(mmt_gate_pauli, flow, is_blocked, expected_other_pauli):
    """Tests for MultiPauliProductMeasurementOp (2 qubit gates)."""
    body = Block(arg_types=[qcore.QubitType(), qcore.QubitType()])
    q0, q1 = body.args
    gate = qref.MeasureOp(paulis=mmt_gate_pauli, qubits=[q0, q1])
    branches = apply_flow(gate, body.args, flow)
    if is_blocked:
        assert not branches
    elif not is_blocked:
        assert (flow, None) in branches
        assert (expected_other_pauli, {gate.measurement}) in branches


@pytest.mark.parametrize(
    ("mmt_gate_pauli", "flow", "is_blocked", "expected_other_pauli"),
    [
        (
            "XXZ",
            qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 3),
            False,
            qcore.PauliStringAttr([("Y", 0), ("Y", 1), ("Z", 2)], 3),
        ),
        ("XXX", qcore.PauliStringAttr([("Z", 0), ("Z", 1), ("Z", 2)], 3), True, None),
    ],
)
def test_multi_pauli_measurement_op_3_qubits(
    mmt_gate_pauli, flow, is_blocked, expected_other_pauli
):
    """Tests for MultiPauliProductMeasurementOp on 3 qubits"""
    body = Block(arg_types=[qcore.QubitType(), qcore.QubitType(), qcore.QubitType()])
    q0, q1, q2 = body.args
    gate = qref.MeasureOp(paulis=mmt_gate_pauli, qubits=[q0, q1, q2])
    branches = apply_flow(gate, body.args, flow)
    if is_blocked:
        assert not branches
    elif not is_blocked:
        assert (flow, None) in branches
        assert (expected_other_pauli, {gate.measurement}) in branches


def test_current_states_checks_num_qubits():
    """Test that CurrentStates checks num_qubits consistency."""
    with pytest.raises(
        ValueError,
        match=re.escape("All flow states in the input basis must have `num_qubits` qubits."),
    ):
        CurrentStates(
            input_flow_basis=[FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1))],
            num_qubits=2,
        )


@pytest.fixture
def example_mmts() -> list[SSAValue]:
    (q0,) = Block(arg_types=[qcore.QubitType()]).args
    measurements: list[SSAValue] = []
    for i in range(5):
        meas = qref.MeasureOp("Z", [q0]).results[0]
        meas.name_hint = f"m{i}"
        measurements.append(meas)
    return measurements


@pytest.fixture
def m0(example_mmts) -> SSAValue:
    return example_mmts[0]


@pytest.fixture
def m1(example_mmts) -> SSAValue:
    return example_mmts[1]


@pytest.fixture
def m2(example_mmts) -> SSAValue:
    return example_mmts[2]


def make_state(
    flow_spec: list[tuple[Literal["X", "Y", "Z"], int]],
    num_qubits: int,
    measurements: Iterable[SSAValue[I1]] | None = None,
    extending_combination: set[int] | None = None,  # defaulting to {0} for convenience!
    newly_created: bool | None = None,
    is_annotated_flow: bool = False,
) -> CurrentState:
    """Convenience constructor for CurrentState. For readability, if newly_created is specified, set
    extending_combination to be empty if newly_created is True, or {0} if newly_created is False."""
    if newly_created is not None:
        assert extending_combination is None
        extending_combination = set() if newly_created else {0}
    return CurrentState(
        qcore.PauliStringAttr(flow_spec, num_qubits),
        MMTResults(list(measurements or [])),
        extending_combination=frozenset(
            extending_combination if extending_combination is not None else {0}
        ),
        is_annotated_flow=is_annotated_flow,
    )


class TestFlowPropagation:
    """Tests for CurrentStates and CalculateFlows propagation and reduction methods."""

    def test_current_states_filter_duplicate_propagating_flows(self, m0, m1) -> None:
        """Test that CurrentStates._filter_duplicate_propagating_flows removes duplicates by
        multiplying out pairs of duplicates."""
        current_states = CurrentStates.from_flows(
            1,
            [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1))],
            propagating_flows=[
                make_state([("Z", 0)], 1),
                make_state([("X", 0)], 1, [m0, m1], newly_created=True),
                make_state([("X", 0)], 1, [m0]),
                make_state([("Z", 0)], 1, [m0]),
                make_state([("X", 0)], 1, [m1]),
                make_state([("X", 0)], 1, [m1]),
                make_state([("Y", 0)], 1),
            ],
            auto_reduce=False,
        )
        current_states._filter_duplicate_propagating_flows()

        # The youngest occurrence of each flow is kept, otherwise fewest measurements, then first
        assert current_states.propagating_flows == [
            make_state([("Z", 0)], 1),
            make_state([("X", 0)], 1, [m0, m1], newly_created=True),
            make_state([("Y", 0)], 1),
        ]
        # Adjacent flows are multiplied out and destruction flows/detectors are sorted properly
        assert current_states.destruction_flows == [
            # (I -> X0 (m0, m1)) * (X0 -> X0 (m0)) = X0 -> I (m1)
            make_state([], 1, [m1]),
        ]
        assert current_states.detectors == [
            MMTResults([m0]),  # (X0 -> Z0) * (X0 -> Z0 (m0)) = I -> I (m0)
            MMTResults([m0, m1]),  # (X0 -> X0 (m0)) * (X0 -> X0 (m1)) = I -> I (m0, m1)
        ]

    def test_current_states_filter_duplicate_propagating_flows_age(self, m0, m1, m2) -> None:
        """Test that _filter_duplicate_propagating_flows keeps the youngest flow and multiplies
        adjacent flows sorted by age and number of measurements."""
        current_states = CurrentStates.from_flows(
            1,
            [
                FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1), age=1),
                FlowChainInfo(qcore.PauliStringAttr([("Y", 0)], 1), age=2),
                FlowChainInfo(qcore.PauliStringAttr([("Z", 0)], 1), age=3),
            ],
            propagating_flows=[
                make_state([("X", 0)], 1, [m0], extending_combination={0}),
                make_state([("X", 0)], 1, [m1], newly_created=True),
                make_state([("X", 0)], 1, [m2], extending_combination={1}),
                make_state([("X", 0)], 1, [m0, m1], extending_combination={2}),
                make_state([("X", 0)], 1, [m1, m2], extending_combination={0, 1}),  # age 2 (from 1)
                make_state([("X", 0)], 1, [], extending_combination={2}),
            ],
            auto_reduce=False,
        )
        current_states._filter_duplicate_propagating_flows()

        # The youngest is kept
        assert current_states.propagating_flows == [
            make_state([("X", 0)], 1, [m1], newly_created=True),
        ]
        # Adjacent flows (sorted by (age, mmts), otherwise stable) are multiplied out
        assert current_states.destruction_flows == [
            make_state([], 1, [m0, m1], extending_combination={0}),
            make_state([], 1, [m0, m2], extending_combination={0, 1}),
            make_state([], 1, [m1], extending_combination={0}),
            make_state([], 1, [m1, m2], extending_combination={0, 1, 2}),
        ]
        assert current_states.detectors == [
            MMTResults([m0, m1]),  # (Z0 -> X0) * (Z0 -> X0 (m0, m1)) = I -> I (m0, m1)
        ]

    # Tests for user flows with _filter_duplicate_propagating_flows - in most of the following tests
    # there is one user flow and one non-user flow.

    def test_current_states_filter_duplicate_propagating_flows_user_flow_kept_removing(
        self, m0
    ) -> None:
        """When removing=True and the user flow is kept (its last_user_flow_age < non-user age),
        the youngest non-user flow is dropped as conflicting with the user flow rather than
        multiplied."""
        current_states = CurrentStates.from_flows(
            1,
            [
                FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1), age=1),
                FlowChainInfo(qcore.PauliStringAttr([("Y", 0)], 1), age=2, last_user_flow_age=0),
            ],
            propagating_flows=[
                make_state([("X", 0)], 1, [m0], extending_combination={0}),
                make_state([("X", 0)], 1, extending_combination={1}),
            ],
            auto_reduce=False,
        )
        current_states._filter_duplicate_propagating_flows(removing=True)

        # User flow (chain 1) is kept; non-user (chain 0) is dropped
        assert current_states.propagating_flows == [
            make_state([("X", 0)], 1, extending_combination={1}),
        ]
        assert current_states.destruction_flows == []
        assert current_states.detectors == []

    def test_current_states_filter_duplicate_propagating_flows_user_flow_kept_not_removing(
        self, m0
    ) -> None:
        """When removing=False and the user flow is kept (its last_user_flow_age < non-user age),
        the youngest non-user flow is multiplied with the user flow (which violates the user flow
        age constraint) - in the algorithm this is fixed later in
        _reduce_all_extension_combinations."""
        current_states = CurrentStates.from_flows(
            1,
            [
                FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1), age=1),
                FlowChainInfo(qcore.PauliStringAttr([("Y", 0)], 1), age=2, last_user_flow_age=0),
            ],
            propagating_flows=[
                make_state([("X", 0)], 1, [m0], extending_combination={0}),
                make_state([("X", 0)], 1, extending_combination={1}),
            ],
            auto_reduce=False,
        )
        current_states._filter_duplicate_propagating_flows(removing=False)

        assert current_states.propagating_flows == [
            make_state([("X", 0)], 1, extending_combination={1}),
        ]
        # Non-user multiplied with kept user flow: destruction flow extending {0, 1}
        assert current_states.destruction_flows == [
            make_state([], 1, [m0], extending_combination={0, 1}),
        ]

    def test_current_states_filter_duplicate_propagating_flows_non_user_kept_not_removing(
        self, m0
    ) -> None:
        """When the non-user flow is younger and kept (age <= last_user_flow_age), the user flow is
        multiplied with the non-user flow."""
        current_states = CurrentStates.from_flows(
            1,
            [
                FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1), age=1),
                FlowChainInfo(qcore.PauliStringAttr([("Y", 0)], 1), age=2, last_user_flow_age=1),
            ],
            propagating_flows=[
                make_state([("X", 0)], 1, [m0], extending_combination={0}),
                make_state([("X", 0)], 1, extending_combination={1}),
            ],
            auto_reduce=False,
        )
        current_states._filter_duplicate_propagating_flows(removing=False)

        # Non-user (age 1) kept; user multiplied with the non-user (age 1 <= last_user_flow_age 1)
        assert current_states.propagating_flows == [
            make_state([("X", 0)], 1, [m0], extending_combination={0}),
        ]
        assert current_states.destruction_flows == [
            make_state([], 1, [m0], extending_combination={0, 1}),
        ]

    def test_current_states_filter_duplicate_propagating_flows_two_user_flows_conflict_removing(
        self, m0
    ) -> None:
        """Two user flows with the same end state and no younger flow to multiply with should
        raise BadUserFlowError when removing=True."""
        current_states = CurrentStates.from_flows(
            1,
            [
                FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1), age=1, last_user_flow_age=0),
                FlowChainInfo(qcore.PauliStringAttr([("Y", 0)], 1), age=2, last_user_flow_age=0),
            ],
            propagating_flows=[
                make_state([("X", 0)], 1, [m0], extending_combination={0}),
                make_state([("X", 0)], 1, extending_combination={1}),
            ],
            auto_reduce=False,
        )
        with pytest.raises(
            BadUserFlowError,
            match=re.escape(
                "User flow-derived chain ending with X0 is in an unresolvable conflict with "
                "user flow-derived chain ending with X0."
            ),
        ):
            current_states._filter_duplicate_propagating_flows(removing=True)

    def test_current_states_filter_duplicate_propagating_flows_two_user_flows_conflict_not_removing(
        self, m0
    ) -> None:
        """Two user flows in conflict with removing=False: the older user flow is multiplied
        with the younger, violating the age constraint - in the algorithm this is fixed later
        in _reduce_all_extension_combinations."""
        current_states = CurrentStates.from_flows(
            1,
            [
                FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1), age=1, last_user_flow_age=0),
                FlowChainInfo(qcore.PauliStringAttr([("Y", 0)], 1), age=2, last_user_flow_age=0),
            ],
            propagating_flows=[
                make_state([("X", 0)], 1, [m0], extending_combination={0}),
                make_state([("X", 0)], 1, extending_combination={1}),
            ],
            auto_reduce=False,
        )
        current_states._filter_duplicate_propagating_flows(removing=False)

        # Youngest user flow (chain 0) kept; other multiplied with it despite age constraint
        assert current_states.propagating_flows == [
            make_state([("X", 0)], 1, [m0], extending_combination={0}),
        ]
        assert current_states.destruction_flows == [
            make_state([], 1, [m0], extending_combination={0, 1}),
        ]

    def test_current_states_filter_duplicate_propagating_flows_annotated_flow(self, m0) -> None:
        """An annotated flow is treated as the youngest user flow and kept even if the other flow is
        younger by age."""
        current_states = CurrentStates.from_flows(
            1,
            [
                FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1), age=1),
                FlowChainInfo(qcore.PauliStringAttr([("Y", 0)], 1), age=3),
            ],
            propagating_flows=[
                # Non-user flow (younger by age)
                make_state([("X", 0)], 1, [m0], extending_combination={0}),
                # Annotated flow (older by age but treated as user with last_user_flow_age=-1)
                make_state([("X", 0)], 1, extending_combination={1}, is_annotated_flow=True),
            ],
            auto_reduce=False,
        )
        current_states._filter_duplicate_propagating_flows()

        # Annotated flow kept (last_user_flow_age=-1 < age of non-user=1)
        assert current_states.propagating_flows == [
            make_state([("X", 0)], 1, extending_combination={1}, is_annotated_flow=True),
        ]
        assert current_states.destruction_flows == [
            make_state([], 1, [m0], extending_combination={0, 1}),
        ]

    def test_current_states_reduce_unique_propagating_flows_simple(self, m0) -> None:
        """Test that CurrentStates._reduce_unique_propagating_flows reduces properly (simple)."""
        current_states = CurrentStates.from_flows(
            2,
            [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 2))],
            propagating_flows=[
                make_state([("X", 0)], 2),
                make_state([("X", 0), ("X", 1)], 2, [m0]),
                make_state([("X", 1)], 2, newly_created=True),
            ],
            auto_reduce=False,
        )
        current_states._reduce_unique_propagating_flows()

        # The basis with the fewest measurements is kept (sort to avoid comparing order)
        assert sorted(
            current_states.propagating_flows, key=lambda cs: cs.flow_state.sort_key()
        ) == [
            make_state([("X", 0)], 2),
            make_state([("X", 1)], 2, newly_created=True),
        ]
        # The remaining flow is (X0 -> X0) * (X0 -> X0X1 (m0)) * (I -> X1) = I -> I (m0)
        assert current_states.destruction_flows == []
        assert current_states.detectors == [MMTResults([m0])]

    def test_current_states_reduce_unique_propagating_flows_complex(self, m0, m1) -> None:
        current_states = CurrentStates.from_flows(
            4,
            [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 4))],
            propagating_flows=[
                make_state([("X", 0), ("X", 1)], 4, [m0], newly_created=True),
                make_state([("X", 1), ("X", 2)], 4, [m0, m1]),
                make_state([("X", 2), ("X", 3)], 4),
                make_state([("X", 0), ("X", 3)], 4, [m1]),
            ],
            auto_reduce=False,
        )
        current_states._reduce_unique_propagating_flows()

        # The basis with the fewest measurements is kept (sort to avoid comparing order)
        assert sorted(
            current_states.propagating_flows, key=lambda cs: cs.flow_state.sort_key()
        ) == [
            make_state([("X", 0), ("X", 1)], 4, [m0], newly_created=True),
            make_state([("X", 0), ("X", 3)], 4, [m1]),
            make_state([("X", 2), ("X", 3)], 4),
        ]
        # The remaining flow is:
        # (I -> X0X1 (m0)) * (X0 -> X1X2 (m0, m1)) * (X0 -> X2X3) * (X0 -> X0X3 (m1)) = X0 -> I
        assert current_states.destruction_flows == [
            make_state([], 4),
        ]
        assert current_states.detectors == []

    def test_current_states_reduce_unique_propagating_flows_age_heuristic(self, m0, m1) -> None:
        """Test that _reduce_unique_propagating_flows prefers to keep younger flows."""
        current_states = CurrentStates.from_flows(
            1,
            [
                FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1), age=1),
                FlowChainInfo(qcore.PauliStringAttr([("Z", 0)], 1), age=2),
            ],
            propagating_flows=[
                make_state([("X", 0)], 1, [m0], extending_combination={0}),
                make_state([("Y", 0)], 1, [m1], extending_combination={0}),
                make_state([("Z", 0)], 1, [], extending_combination={1}),
            ],
            auto_reduce=False,
        )
        current_states._reduce_unique_propagating_flows()

        # The younger two are kept even though the older has fewer measurements
        assert sorted(
            current_states.propagating_flows, key=lambda cs: cs.flow_state.sort_key()
        ) == [
            make_state([("X", 0)], 1, [m0], extending_combination={0}),
            make_state([("Y", 0)], 1, [m1], extending_combination={0}),
        ]
        assert current_states.destruction_flows == [
            make_state([], 1, [m0, m1], extending_combination={1}),
        ]
        assert current_states.detectors == []

    def test_current_states_reduce_unique_propagating_flows_only_independent_detectors(
        self, m0, m1
    ) -> None:
        """Test that _reduce_unique_propagating_flows doesn't add redundant detectors it finds."""
        current_states = CurrentStates.from_flows(
            2,
            [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 2))],
            propagating_flows=[
                make_state([("X", 0)], 2),
                make_state([("X", 0), ("X", 1)], 2, [m0]),
                make_state([("X", 1)], 2, [m1], newly_created=True),
            ],
            detectors=[MMTResults([m0]), MMTResults([m1])],  # Already has these detectors
            auto_reduce=False,
        )
        current_states._reduce_unique_propagating_flows()

        # The basis with the fewest measurements, and then weight, is kept
        assert sorted(
            current_states.propagating_flows, key=lambda cs: cs.flow_state.sort_key()
        ) == [
            make_state([("X", 0)], 2),
            make_state([("X", 1)], 2, [m1], newly_created=True),
        ]
        # The [m0, m1] detector shouldn't be added because it's not linearly independent
        assert current_states.destruction_flows == []
        assert current_states.detectors == [MMTResults([m0]), MMTResults([m1])]

    def test_current_states_reduce_unique_propagating_flows_annotated_not_eliminated(
        self, m0, m1
    ) -> None:
        """Annotated flows are flagged and never eliminated even if linearly dependent."""
        current_states = CurrentStates.from_flows(
            2,
            [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 2))],
            propagating_flows=[
                make_state([("X", 0)], 2, [m0], is_annotated_flow=True),
                make_state([("X", 1)], 2, [m1], newly_created=True, is_annotated_flow=True),
                make_state([("X", 0), ("X", 1)], 2, [m0, m1], is_annotated_flow=True),
            ],
            auto_reduce=False,
        )
        current_states._reduce_unique_propagating_flows()

        # All are annotated so all are kept
        assert sorted(
            current_states.propagating_flows, key=lambda cs: cs.flow_state.sort_key()
        ) == [
            make_state([("X", 0), ("X", 1)], 2, [m0, m1], is_annotated_flow=True),
            make_state([("X", 0)], 2, [m0], is_annotated_flow=True),
            make_state([("X", 1)], 2, [m1], newly_created=True, is_annotated_flow=True),
        ]
        assert current_states.destruction_flows == []
        assert current_states.detectors == []

    def test_current_states_reduce_unique_propagating_flows_user_flow_preservation(self) -> None:
        """With enforce_user_flow_preservation=True, user flows are not eliminated when they are the
        oldest flow in a dependent set and multiplying out the dependent set would require violating
        the last user flow age constraint."""
        current_states = CurrentStates.from_flows(
            2,
            [
                FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 2), last_user_flow_age=1, age=3),
                FlowChainInfo(qcore.PauliStringAttr([("Y", 0)], 2), age=2),
                FlowChainInfo(qcore.PauliStringAttr([("Z", 0)], 2), age=2),
            ],
            propagating_flows=[
                make_state([("X", 0), ("X", 1)], 2, extending_combination={0}),
                make_state([("X", 0)], 2, extending_combination={1}),
                make_state([("X", 1)], 2, extending_combination={2}),
            ],
            auto_reduce=False,
        )
        current_states._reduce_unique_propagating_flows(enforce_user_flow_preservation=True)

        # User flow is kept even though it's the oldest in its dependent set, but we do multiply out
        # the dependent set to a destruction flow.
        assert sorted(
            current_states.propagating_flows, key=lambda cs: cs.flow_state.sort_key()
        ) == [
            make_state([("X", 0), ("X", 1)], 2, extending_combination={0}),
            make_state([("X", 0)], 2, extending_combination={1}),
            make_state([("X", 1)], 2, extending_combination={2}),
        ]
        assert current_states.destruction_flows == [
            make_state([], 2, extending_combination={0, 1, 2}),
        ]
        assert current_states.detectors == []

    def test_current_states_reduce_unique_propagating_flows_user_flow_preservation_not_enforced(
        self,
    ) -> None:
        """With enforce_user_flow_preservation=True, user flows *are* eliminated even when they are
        the oldest flow in a dependent set, when we can multiply out the dependent set without
        violating the last user flow age constraint."""
        current_states = CurrentStates.from_flows(
            2,
            [
                FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 2), last_user_flow_age=2, age=3),
                FlowChainInfo(qcore.PauliStringAttr([("Y", 0)], 2), age=2),
                FlowChainInfo(qcore.PauliStringAttr([("Z", 0)], 2), age=2),
            ],
            propagating_flows=[
                make_state([("X", 0), ("X", 1)], 2, extending_combination={0}),
                make_state([("X", 0)], 2, extending_combination={1}),
                make_state([("X", 1)], 2, extending_combination={2}),
            ],
            auto_reduce=False,
        )
        current_states._reduce_unique_propagating_flows(enforce_user_flow_preservation=True)

        # User flow is not kept this time and the dependent set is multiplied out
        assert sorted(
            current_states.propagating_flows, key=lambda cs: cs.flow_state.sort_key()
        ) == [
            make_state([("X", 0)], 2, extending_combination={1}),
            make_state([("X", 1)], 2, extending_combination={2}),
        ]
        assert current_states.destruction_flows == [
            make_state([], 2, extending_combination={0, 1, 2}),
        ]
        assert current_states.detectors == []

    def test_current_states_reduce_destruction_flows(self, m0, m1) -> None:
        """Test that _reduce_destruction_flows reduces extending combinations properly."""
        current_states = CurrentStates.from_flows(
            1,
            [
                FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1), age=1),
                FlowChainInfo(qcore.PauliStringAttr([("Y", 0)], 1), age=2),
            ],
            destruction_flows=[
                make_state([], 1, [m0], extending_combination={0}),
                make_state([], 1, [m1], extending_combination={1}),
                make_state([], 1, [], extending_combination={0, 1}),
            ],
            auto_reduce=False,
        )
        current_states._reduce_destruction_flows()

        # Finds the detector and keeps the youngest and then the one with fewest measurements
        assert current_states.propagating_flows == []
        assert current_states.destruction_flows == [
            make_state([], 1, [m0], extending_combination={0}),
            make_state([], 1, [], extending_combination={0, 1}),
        ]
        assert current_states.detectors == [MMTResults([m0, m1])]

    def test_current_states_reduce_and_full_reduce_comprehensive(self, m0, m1) -> None:
        """Overall test for CurrentStates.reduce() and CurrentStates.full_reduce()."""
        current_states = CurrentStates.from_flows(
            3,
            [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 3))],
            propagating_flows=[
                make_state([("X", 0)], 3),
                make_state([("X", 1)], 3),
                make_state([("X", 2)], 3, [m0]),
                make_state([("X", 0), ("X", 1)], 3, [m1]),
                make_state([("X", 0), ("X", 2)], 3, [m0, m1], newly_created=True),
                make_state([("X", 1), ("X", 2)], 3, [m0]),
                make_state([("X", 0), ("X", 1), ("X", 2)], 3, [m1]),
            ],
            destruction_flows=[
                make_state([], 3, [m0]),
            ],
        )
        current_states.reduce()

        # With just reduction, the propagating flows are not all reduced to creation flows yet.
        assert sorted(
            current_states.propagating_flows, key=lambda cs: cs.flow_state.sort_key()
        ) == [
            make_state([("X", 0), ("X", 2)], 3, [m0, m1], newly_created=True),
            make_state([("X", 0)], 3),
            make_state([("X", 1)], 3),
        ]
        assert current_states.destruction_flows == [
            make_state([], 3, [m1]),
        ]
        # Which two detectors are chosen depends on the implementation of the Gaussian elimination
        # but there should be exactly two.
        assert len(current_states.detectors) == 2

        # With full reduction, the propagating flows are reduced to creation flows and we rearrange
        # the basis to have the fewest measurements.
        current_states.full_reduce()
        assert sorted(
            current_states.propagating_flows, key=lambda cs: cs.flow_state.sort_key()
        ) == [
            make_state([("X", 0), ("X", 1)], 3, [], newly_created=True),
            make_state([("X", 0), ("X", 2)], 3, [m0, m1], newly_created=True),
            make_state([("X", 1)], 3, [m1], newly_created=True),
        ]
        assert current_states.destruction_flows == [
            make_state([], 3, [m1]),
        ]
        assert len(current_states.detectors) == 2

    def test_current_states_reduce_all_extension_combinations(self, m0) -> None:
        """Test that _reduce_all_extension_combinations reduces propagating flows' extension
        combinations correctly in the presence of destruction flows."""
        current_states = CurrentStates.from_flows(
            1,
            [
                FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1), age=1),
                FlowChainInfo(qcore.PauliStringAttr([("Y", 0)], 1), age=2),
            ],
            propagating_flows=[
                make_state([("X", 0)], 1, [m0], extending_combination={0}),
                make_state([("Y", 0)], 1, [], extending_combination={1}),
            ],
            destruction_flows=[
                make_state([], 1, [], extending_combination={0, 1}),
            ],
            auto_reduce=False,
        )
        current_states._reduce_all_extension_combinations()

        # Finds the creation flow, keeping youngest and the destruction flow
        assert current_states.propagating_flows == [
            make_state([("X", 0)], 1, [m0], extending_combination={0}),
            make_state([("Z", 0)], 1, [m0], newly_created=True),
        ]
        assert current_states.destruction_flows == [
            make_state([], 1, [], extending_combination={0, 1}),
        ]
        assert current_states.detectors == []

    def test_current_states_reduce_all_extension_combinations_fix_user_age_constraint(
        self, m0
    ) -> None:
        """Test that _reduce_all_extension_combinations fixes violations of the user flow age
        constraint: user chain 0 with last_user_flow_age=0, non-user chain 1 with age=1,
        propagating flows with extending combinations {0, 1} and {1}. Multiplied out to {0} and
        {1}."""
        current_states = CurrentStates.from_flows(
            1,
            [
                FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1), age=2, last_user_flow_age=0),
                FlowChainInfo(qcore.PauliStringAttr([("Y", 0)], 1), age=1),
            ],
            propagating_flows=[
                # Violates age constraint: user chain 0 mixed with non-user chain 1 (age 1 > 0)
                make_state([("X", 0)], 1, extending_combination={0, 1}),
                make_state([("Y", 0)], 1, [m0], extending_combination={1}),
            ],
            auto_reduce=False,
        )
        current_states._reduce_all_extension_combinations()

        assert sorted(
            current_states.propagating_flows, key=lambda cs: cs.flow_state.sort_key()
        ) == [
            make_state([("Y", 0)], 1, [m0], extending_combination={1}),
            make_state([("Z", 0)], 1, [m0], extending_combination={0}),
        ]
        assert current_states.destruction_flows == []
        assert current_states.detectors == []

    def test_current_states_reduce_all_extension_combinations_fix_age_constraint(self, m0) -> None:
        """Test that _reduce_all_extension_combinations fixes violations of the age constraint:
        chain 0 with age=2, chain 1 with age=1, propagating flows with extending combinations {0, 1}
        and {1}. Multiplied out to {0} and {1}."""
        current_states = CurrentStates.from_flows(
            1,
            [
                FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1), age=2),
                FlowChainInfo(qcore.PauliStringAttr([("Y", 0)], 1), age=1),
            ],
            propagating_flows=[
                make_state([("X", 0)], 1, extending_combination={0, 1}),
                make_state([("Y", 0)], 1, [m0], extending_combination={1}),
            ],
            auto_reduce=False,
        )
        current_states._reduce_all_extension_combinations()

        assert current_states.propagating_flows == [
            make_state([("Z", 0)], 1, [m0], extending_combination={0}),
            make_state([("Y", 0)], 1, [m0], extending_combination={1}),
        ]
        assert current_states.destruction_flows == []
        assert current_states.detectors == []

    def test_current_states_check_in_span_only_detectors(self, m0, m1, m2) -> None:
        """Test CurrentStates.check_in_span() with only detectors present."""
        current_states = CurrentStates.from_flows(
            1,
            [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1))],
            detectors=[MMTResults([m0]), MMTResults([m1])],
        )
        # Check some detectors in the span
        assert (
            current_states.check_in_span(CurrentState.detector(MMTResults([m0]), 1)).status
            == FlowInSpanStatus.IN_SPAN
        )
        assert (
            current_states.check_in_span(CurrentState.detector(MMTResults([m1]), 1)).status
            == FlowInSpanStatus.IN_SPAN
        )
        assert (
            current_states.check_in_span(CurrentState.detector(MMTResults([m0, m1]), 1)).status
            == FlowInSpanStatus.IN_SPAN
        )
        # The identity flow is always in the span
        assert (
            current_states.check_in_span(CurrentState.identity(1)).status
            == FlowInSpanStatus.IN_SPAN
        )
        # A detector not in the span should return MEASUREMENTS_NOT_IN_SPAN
        assert (
            current_states.check_in_span(CurrentState.detector(MMTResults([m2]), 1)).status
            == FlowInSpanStatus.MEASUREMENTS_NOT_IN_SPAN
        )
        # Non-detectors should return FLOW_STATE_NOT_IN_SPAN
        assert (
            current_states.check_in_span(make_state([("X", 0)], 1)).status
            == FlowInSpanStatus.FLOW_STATE_NOT_IN_SPAN
        )
        assert (
            current_states.check_in_span(make_state([("Z", 0)], 1, [m0], newly_created=True)).status
            == FlowInSpanStatus.FLOW_STATE_NOT_IN_SPAN
        )

    def test_current_states_check_in_span_with_propagating_flows(self, m0, m1) -> None:
        """Test CurrentStates.check_in_span() with propagating flows present."""
        current_states = CurrentStates.from_flows(
            2,
            [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 2))],
            propagating_flows=[
                make_state([("X", 0)], 2),
                make_state([("Z", 0)], 2, [m0]),
                make_state([("Y", 0)], 2, [m1], newly_created=True),
            ],
        )
        # Check some flows in the span
        assert (
            current_states.check_in_span(make_state([("X", 0)], 2)).status
            == FlowInSpanStatus.IN_SPAN
        )
        assert (
            current_states.check_in_span(make_state([("Z", 0)], 2, [m0])).status
            == FlowInSpanStatus.IN_SPAN
        )
        assert (
            # (X0 -> X0) * (X0 -> Z0 (m0)) = (I -> Y0 (m0))
            current_states.check_in_span(make_state([("Y", 0)], 2, [m0], newly_created=True)).status
            == FlowInSpanStatus.IN_SPAN
        )
        assert (
            current_states.check_in_span(CurrentState.detector(MMTResults([m0, m1]), 2)).status
            == FlowInSpanStatus.IN_SPAN
        )
        # Check some flows not in the span
        assert (
            current_states.check_in_span(make_state([("Z", 1)], 2)).status
            == FlowInSpanStatus.FLOW_STATE_NOT_IN_SPAN
        )
        assert (
            # X0 -> Y0 is not in the span
            current_states.check_in_span(make_state([("Y", 0)], 2)).status
            == FlowInSpanStatus.FLOW_STATE_NOT_IN_SPAN
        )
        assert (
            # I -> Y0 with no measurements is not in the span
            current_states.check_in_span(make_state([("Y", 0)], 2, newly_created=True)).status
            == FlowInSpanStatus.MEASUREMENTS_NOT_IN_SPAN
        )
        assert (
            # X0 -> I is not in the span
            current_states.check_in_span(make_state([], 2)).status
            == FlowInSpanStatus.FLOW_STATE_NOT_IN_SPAN
        )

    def test_current_states_check_in_span_with_propagating_and_destruction_flows(
        self, m0, m1
    ) -> None:
        """Test CurrentStates.check_in_span() with both propagating and destruction flows."""
        current_states = CurrentStates.from_flows(
            2,
            [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 2))],
            propagating_flows=[
                make_state([("X", 0)], 2),
                make_state([("Z", 0)], 2, [m0]),
            ],
            destruction_flows=[
                make_state([], 2, [m1]),
            ],
        )
        assert (
            current_states.check_in_span(make_state([("X", 0)], 2)).status
            == FlowInSpanStatus.IN_SPAN
        )
        assert (
            current_states.check_in_span(make_state([], 2, [m1])).status == FlowInSpanStatus.IN_SPAN
        )
        assert (
            # I -> X0 is also in the span because of the destruction flow
            current_states.check_in_span(make_state([("X", 0)], 2, [m1], newly_created=True)).status
            == FlowInSpanStatus.IN_SPAN
        )
        assert (
            # X0 -> Y0 is in the span because of the destruction flow
            current_states.check_in_span(make_state([("Y", 0)], 2, [m0, m1])).status
            == FlowInSpanStatus.IN_SPAN
        )
        assert (
            # X0 -> I with wrong measurements is not in the span
            current_states.check_in_span(make_state([], 2)).status
            == FlowInSpanStatus.MEASUREMENTS_NOT_IN_SPAN
        )

    def test_current_states_check_in_span_extending_combination(self, m0, m1) -> None:
        """Test CurrentStates.check_in_span() with extending multiple chains."""
        current_states = CurrentStates.from_flows(
            2,
            [
                FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 2), age=1),
                FlowChainInfo(qcore.PauliStringAttr([("Z", 0)], 2), age=2),
            ],
            propagating_flows=[
                make_state([("X", 0)], 2, [m0], extending_combination={0}),
                make_state([("Z", 0)], 2, [m1], extending_combination={1}),
            ],
        )
        assert (
            current_states.check_in_span(
                make_state([("X", 0)], 2, [m0], extending_combination={0})
            ).status
            == FlowInSpanStatus.IN_SPAN
        )
        assert (
            current_states.check_in_span(
                make_state([("Z", 0)], 2, [m1], extending_combination={1})
            ).status
            == FlowInSpanStatus.IN_SPAN
        )
        assert (
            current_states.check_in_span(
                make_state([("Y", 0)], 2, [m0, m1], extending_combination={0, 1})
            ).status
            == FlowInSpanStatus.IN_SPAN
        )
        # Check a flow with a different extending combination is not in the span
        assert (
            current_states.check_in_span(
                make_state([("X", 0)], 2, [m0], extending_combination={1})
            ).status
            == FlowInSpanStatus.FLOW_STATE_NOT_IN_SPAN
        )

    def test_current_states_check_in_span_extending_combination_and_destruction_flows(
        self, m0, m1
    ) -> None:
        """Test CurrentStates.check_in_span() with extending multiple chains and destruction
        flows."""
        current_states = CurrentStates.from_flows(
            2,
            [
                FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 2), age=1),
                FlowChainInfo(qcore.PauliStringAttr([("Z", 0)], 2), age=2),
            ],
            propagating_flows=[
                make_state([("X", 0)], 2, [m0], extending_combination={0}),
                make_state([("Z", 0)], 2, [m1], extending_combination={1}),
            ],
            destruction_flows=[
                make_state([], 2, [m0, m1], extending_combination={0, 1}),
            ],
        )
        assert (
            current_states.check_in_span(
                make_state([("Y", 0)], 2, [m0, m1], extending_combination={0, 1})
            ).status
            == FlowInSpanStatus.IN_SPAN
        )
        assert (
            current_states.check_in_span(make_state([("Y", 0)], 2, [], newly_created=True)).status
            == FlowInSpanStatus.IN_SPAN
        )
        assert (
            current_states.check_in_span(
                make_state([("Y", 0)], 2, [m0, m1], extending_combination={0})
            ).status
            == FlowInSpanStatus.FLOW_STATE_NOT_IN_SPAN
        )

    def test_current_states_unblock_two_anticommuting_states_blocked_by_mz(self) -> None:
        """Two states X0 and Y0 both anticommute with M_Z. Their product Z0 commutes,
        so unblocking should produce branches from propagating Z0 through M_Z."""
        body = Block(arg_types=[qcore.QubitType()])
        (q0,) = body.args
        m_gate = qref.MeasureOp("Z", [q0])
        current_states = CurrentStates.from_flows(
            1, [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1))], auto_reduce=False
        )

        blocked = [
            make_state([("X", 0)], 1),
            make_state([("Y", 0)], 1),
        ]

        unblocked = current_states._try_unblock(blocked, m_gate, body.args)

        # Product X0*Y0 = Z0 commutes with M_Z, giving branches: Z0->Z0 and Z0->I (with mmt)
        assert len(unblocked) == 2
        flow_states = {cs.flow_state for cs in unblocked}
        assert qcore.PauliStringAttr([("Z", 0)], 1) in flow_states
        assert qcore.PauliStringAttr.identity(1) in flow_states
        # The identity branch should record the measurement
        identity_branch = next(cs for cs in unblocked if cs.flow_state.is_identity())
        assert identity_branch.mmt_ssa is not None
        assert MMTResults(m_gate.measurements).issubset(identity_branch.mmt_ssa)

    def test_current_states_unblock_single_blocked_state_returns_empty(self) -> None:
        """A single blocked state cannot form any pairs, so nothing is unblocked."""
        body = Block(arg_types=[qcore.QubitType()])
        (q0,) = body.args
        m_gate = qref.MeasureOp("Z", [q0])
        current_states = CurrentStates.from_flows(
            1, [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1))], auto_reduce=False
        )

        blocked = [make_state([("X", 0)], 1)]

        unblocked = current_states._try_unblock(blocked, m_gate, body.args)
        assert unblocked == []

    def test_current_states_unblock_three_blocked_states_produces_two_products(self) -> None:
        """Three blocked states [X0, Y0, X0Y1] produce two pairwise products via itertools.pairwise:
        (X0*Y0)=Z0 and (Y0*(X0Y1))=Z0Y1. Both commute with M_Z."""
        body = Block(arg_types=[qcore.QubitType(), qcore.QubitType()])
        q0, _ = body.args
        m_gate = qref.MeasureOp("Z", [q0])
        current_states = CurrentStates.from_flows(
            2, [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 2))], auto_reduce=False
        )

        blocked = [
            make_state([("X", 0)], 2),
            make_state([("Y", 0)], 2),
            make_state([("X", 0), ("Y", 1)], 2),
        ]

        unblocked = current_states._try_unblock(blocked, m_gate, body.args)

        # Two pairs: (X0,Y0) -> Z0, (Y0,X0Y1) -> Z0Y1. Each gives 2 branches = 4 total
        assert len(unblocked) == 4
        flow_states = {cs.flow_state for cs in unblocked}
        assert qcore.PauliStringAttr([("Z", 0)], 2) in flow_states
        assert qcore.PauliStringAttr([("Z", 0), ("Y", 1)], 2) in flow_states
        assert qcore.PauliStringAttr.identity(2) in flow_states
        assert qcore.PauliStringAttr([("Y", 1)], 2) in flow_states

    def test_current_states_unblock_extending_combinations(self, m0, m1) -> None:
        """Unblocking on measurements multiplies adjacent flows with the same extending combinations
        and multiplies the ones with the fewest measurements from each extending combination in age
        order."""
        body = Block(arg_types=[qcore.QubitType(), qcore.QubitType()])
        q0, _ = body.args
        m_gate = qref.MeasureOp("Z", [q0])
        current_states = CurrentStates.from_flows(
            2,
            [
                FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 2), age=1),
                FlowChainInfo(qcore.PauliStringAttr([("X", 1)], 2), age=2),
                FlowChainInfo(qcore.PauliStringAttr([("Z", 0)], 2), age=2),
                FlowChainInfo(qcore.PauliStringAttr([("Z", 1)], 2), age=3),
            ],
            auto_reduce=False,
        )

        blocked = [
            make_state([("Y", 0), ("Z", 1)], 2, [m0, m1], extending_combination={3}),
            make_state([("X", 0)], 2, [m0], extending_combination={0}),
            make_state([("Y", 0), ("Y", 1)], 2, [], extending_combination={2}),
            make_state([("X", 0), ("X", 1)], 2, [], extending_combination={0}),
            make_state([("Y", 0)], 2, [m1], extending_combination={1}),
        ]

        unblocked = current_states._try_unblock(blocked, m_gate, body.args)

        # Results of unblocking are: X0*X0X1 = X1 from extending combination {0}, and then from
        # combining representatives sorted by age:
        # X0X1*Y0Y1 = Z0Z1, Y0*Y0Y1 = Y1, and Y0*Y0Z1 = Z1. Each gives 2 branches.
        assert len(unblocked) == 8
        flow_states = {cs.flow_state for cs in unblocked}
        assert qcore.PauliStringAttr([("X", 1)], 2) in flow_states
        assert qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 2) in flow_states
        assert qcore.PauliStringAttr([("Y", 1)], 2) in flow_states
        assert qcore.PauliStringAttr([("Z", 1)], 2) in flow_states
        assert qcore.PauliStringAttr([("Z", 0), ("X", 1)], 2) in flow_states
        assert qcore.PauliStringAttr([("Z", 1)], 2) in flow_states
        assert qcore.PauliStringAttr([("Z", 0), ("Y", 1)], 2) in flow_states
        assert qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 2) in flow_states

    def test_current_states_unblock_blocked_by_reset_different_paulis_returns_empty(self) -> None:
        """Reset unblocking fails when blocked flows have different Paulis on reset target.
        X0*Y0 = Z0 which is still non-identity on the reset target, so product is still blocked."""
        body = Block(arg_types=[qcore.QubitType()])
        (q0,) = body.args
        r_gate = qref.ResetOp("Z", [q0])

        current_states = CurrentStates.from_flows(
            1, [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1))], auto_reduce=False
        )
        blocked = [
            make_state([("X", 0)], 1),
            make_state([("Y", 0)], 1),
        ]

        unblocked = current_states._try_unblock(blocked, r_gate, body.args)
        assert unblocked == []

    def test_current_states_unblock_blocked_by_reset_same_pauli_unblocks(self) -> None:
        """Reset unblocking succeeds when both blocked flows have the same Pauli on reset target.
        X0*X0Y1 = Y1 which is identity on the reset target, so the product passes through the
        reset."""
        body = Block(arg_types=[qcore.QubitType(), qcore.QubitType()])
        q0, _ = body.args
        r_gate = qref.ResetOp("Z", [q0])
        current_states = CurrentStates.from_flows(
            2, [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 2))], auto_reduce=False
        )

        # Two states with same Pauli on reset target but different measurement histories
        mmt_a = cast(SSAValue[I1], test.TestOp(result_types=[i1]).results[0])
        blocked = [
            make_state([("X", 0)], 2),
            make_state([("X", 0), ("Y", 1)], 2, [mmt_a]),
        ]

        unblocked = current_states._try_unblock(blocked, r_gate, body.args)

        # Product has identity flow state: reset branches to Z0Y1 and Y1
        assert len(unblocked) == 2
        flow_states = {cs.flow_state for cs in unblocked}
        assert qcore.PauliStringAttr([("Z", 0), ("Y", 1)], 2) in flow_states
        assert qcore.PauliStringAttr([("Y", 1)], 2) in flow_states

    def test_current_states_unblock_blocked_by_reset_xyz_unblocks(self) -> None:
        """Reset unblocking succeeds when there's one blocked flow of each Pauli on the reset target
        by multiplying them together: X0*Y0*Z0Z1 = Z1 which is identity on the reset target."""
        body = Block(arg_types=[qcore.QubitType(), qcore.QubitType()])
        q0, _ = body.args
        r_gate = qref.ResetOp("Z", [q0])
        current_states = CurrentStates.from_flows(
            2, [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 2))], auto_reduce=False
        )

        blocked = [
            make_state([("X", 0)], 2),
            make_state([("Y", 0)], 2),
            make_state([("Z", 0), ("Z", 1)], 2),
        ]

        unblocked = current_states._try_unblock(blocked, r_gate, body.args)

        # Product has identity flow state: reset branches to Z1 and Z0Z1
        assert len(unblocked) == 2
        flow_states = {cs.flow_state for cs in unblocked}
        assert qcore.PauliStringAttr([("Z", 1)], 2) in flow_states
        assert qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 2) in flow_states

    def test_current_states_unblock_blocked_by_reset_xx_yy_zz(self, m0) -> None:
        """Reset unblocking succeeds on two blocked flows of each Pauli on the reset target.
        Each pair of blocked flows with the same Pauli is multiplied together and the XYZ product
        of flows with the fewest measurements is kept."""
        body = Block(arg_types=[qcore.QubitType(), qcore.QubitType(), qcore.QubitType()])
        q0, _, _ = body.args
        r_gate = qref.ResetOp("Z", [q0])
        current_states = CurrentStates.from_flows(
            3, [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 3))], auto_reduce=False
        )

        blocked = [
            make_state([("X", 0)], 3, [m0]),
            make_state([("X", 0), ("Y", 1)], 3),
            make_state([("Y", 0)], 3),
            make_state([("Z", 0), ("X", 1), ("X", 2)], 3),
            make_state([("Y", 0), ("Z", 1)], 3, [m0]),
            make_state([("Z", 0)], 3, [m0]),
        ]

        unblocked = current_states._try_unblock(blocked, r_gate, body.args)

        # Products are Y1, Z1, X1X2, and X0Y1 * Y0 * Z0X1X2 = Z1X2, since that's the XYZ triple with
        # the fewest measurements. Reset branches each to I and Z0 on the 0th qubit.
        assert len(unblocked) == 8
        flow_states = {cs.flow_state for cs in unblocked}
        assert qcore.PauliStringAttr([("Y", 1)], 3) in flow_states
        assert qcore.PauliStringAttr([("Z", 1)], 3) in flow_states
        assert qcore.PauliStringAttr([("X", 1), ("X", 2)], 3) in flow_states
        assert qcore.PauliStringAttr([("Z", 1), ("X", 2)], 3) in flow_states
        assert qcore.PauliStringAttr([("Z", 0), ("Y", 1)], 3) in flow_states
        assert qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 3) in flow_states
        assert qcore.PauliStringAttr([("Z", 0), ("X", 1), ("X", 2)], 3) in flow_states
        assert qcore.PauliStringAttr([("Z", 0), ("Z", 1), ("X", 2)], 3) in flow_states

    def test_current_states_unblock_blocked_by_reset_youngest(self, m0) -> None:
        """Reset unblocking chooses the youngest flow of each Pauli to multiply for XYZ = I, even
        when this isn't the flow with the fewest measurements."""
        body = Block(arg_types=[qcore.QubitType(), qcore.QubitType(), qcore.QubitType()])
        q0, _, _ = body.args
        r_gate = qref.ResetOp("Z", [q0])
        current_states = CurrentStates.from_flows(
            3,
            [
                FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 3), age=1),
                FlowChainInfo(qcore.PauliStringAttr([("Y", 0)], 3), age=2),
                FlowChainInfo(qcore.PauliStringAttr([("X", 0), ("Y", 1)], 3), age=3),
            ],
            auto_reduce=False,
        )

        blocked = [
            make_state([("X", 0)], 3, [m0], extending_combination={0}),
            make_state([("X", 0), ("Y", 1)], 3, extending_combination={1}),
            make_state([("Y", 0)], 3, extending_combination={2}),
            make_state([("Z", 0), ("X", 1), ("X", 2)], 3, extending_combination={0, 1}),
            make_state([("Y", 0), ("Z", 1)], 3, [m0], newly_created=True),
            make_state([("Z", 0)], 3, [m0], extending_combination={2}),
        ]

        unblocked = current_states._try_unblock(blocked, r_gate, body.args)

        # Products are Y1, Z1, X1X2, and X0 * Y0Z1 * Z0X1 = Y1, since that's the youngest XYZ
        # triple. Reset branches each to I and Z0 on the 0th qubit.
        assert len(unblocked) == 8
        flow_states = {cs.flow_state for cs in unblocked}
        assert qcore.PauliStringAttr([("Y", 1)], 3) in flow_states
        assert qcore.PauliStringAttr([("Z", 1)], 3) in flow_states
        assert qcore.PauliStringAttr([("X", 1), ("X", 2)], 3) in flow_states
        assert qcore.PauliStringAttr([("Y", 1)], 3) in flow_states
        assert qcore.PauliStringAttr([("Z", 0), ("Y", 1)], 3) in flow_states
        assert qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 3) in flow_states
        assert qcore.PauliStringAttr([("Z", 0), ("X", 1), ("X", 2)], 3) in flow_states
        assert qcore.PauliStringAttr([("Z", 0), ("Y", 1)], 3) in flow_states

    def test_current_states_unblock_preserves_measurement_history(self) -> None:
        """Unblocking correctly XORs measurement histories from the two blocked states."""
        body = Block(arg_types=[qcore.QubitType()])
        (q0,) = body.args
        m_gate = qref.MeasureOp("Z", [q0])
        current_states = CurrentStates.from_flows(
            1, [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1))], auto_reduce=False
        )

        # Create distinct prior measurement SSAs
        prior_mmt_a = cast(SSAValue[I1], test.TestOp(result_types=[i1]).results[0])
        prior_mmt_b = cast(SSAValue[I1], test.TestOp(result_types=[i1]).results[0])

        blocked = [
            make_state([("X", 0)], 1, [prior_mmt_a]),
            make_state([("Y", 0)], 1, [prior_mmt_b]),
        ]

        unblocked = current_states._try_unblock(blocked, m_gate, body.args)

        # Product has mmt_ssa = {a} XOR {b} = {a, b}
        assert len(unblocked) == 2
        # The branch that doesn't record the new measurement should have exactly {a, b}
        non_recording = next(
            cs for cs in unblocked if cs.flow_state == qcore.PauliStringAttr([("Z", 0)], 1)
        )
        assert non_recording.mmt_ssa is not None
        assert prior_mmt_a in non_recording.mmt_ssa
        assert prior_mmt_b in non_recording.mmt_ssa

    def test_current_states_apply_clifford_and_measurement_history(self) -> None:
        """Clifford preserves history; measurement may add gate readout to history."""
        # Clifford
        body = Block(arg_types=[qcore.QubitType()])
        (q0,) = body.args
        h_gate = qref.GateOp(qcore.HGateAttr(), [q0])
        current = CurrentStates.from_flows(
            1,
            [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1))],
            propagating_flows=[make_state([("X", 0)], 1)],
            auto_reduce=False,
        )
        current.propagate([h_gate], body.args)
        all_states = list(current.get_all_states())
        assert len(all_states) == 1
        assert all_states[0].flow_state == qcore.PauliStringAttr([("Z", 0)], 1)
        assert all_states[0].mmt_ssa == MMTResults()

        # Measurement on identity may add readout to history for dependent branch
        # Also, CurrentStates pushes through the identity when the propagating gate is the identity
        m_gate = qref.MeasureOp("Z", [q0])
        current_id = CurrentStates([FlowChainInfo(qcore.PauliStringAttr.identity(1))], num_qubits=1)
        current_id.propagate([m_gate], body.args)
        # At least one branch should include the measurement readout in history
        all_states = list(current_id.get_all_states())
        assert any(
            MMTResults(m_gate.measurements).issubset(cs.mmt_ssa)
            for cs in all_states
            if cs.mmt_ssa is not None
        )

    def test_calculate_flows_propagate_sequence_h_s(self) -> None:
        """Sequence H then S on X0 should yield Z0 overall (H: X->Z, S: Z->Z)."""
        body = Block(arg_types=[qcore.QubitType()])
        (q0,) = body.args
        h_gate = qref.GateOp(qcore.HGateAttr(), [q0])
        s_gate = qref.GateOp(qcore.SGateAttr(), [q0])
        res = CalculateFlows.propagate_input_flow_basis(
            input_flow_info=[FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1))],
            qubits=body.args,
            ops=[h_gate, s_gate],
        )
        states = list(res.get_all_states())
        assert len(states) == 1
        assert states[0].flow_state == qcore.PauliStringAttr([("Z", 0)], 1)
        assert states[0].mmt_ssa == MMTResults()

    def test_calculate_flows_error_on_noise(self) -> None:
        """Test that propagate_input_flow errors on noise operations."""
        body = Block(arg_types=[qcore.QubitType()])
        (q0,) = body.args
        noise_gate = qref.PauliNoiseOp(qcore.PauliNoiseParametersAttr.depolarise(1, 0.3), [q0])

        with pytest.raises(
            ValueError, match=re.escape("Propagating flows through noise ops is not supported.")
        ):
            CalculateFlows.propagate_input_flow_basis(
                input_flow_info=[FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1))],
                qubits=body.args,
                ops=[noise_gate],
            )

    def test_calculate_flows_error_on_unknown_op(self) -> None:
        """Test that propagate_input_flows errors on unknown operations."""
        body = Block(arg_types=[qcore.QubitType()])
        (q0,) = body.args
        unknown_op = test.TestOp(operands=[q0])

        with pytest.raises(
            ValueError,
            match=r"Propagating flows over unknown operation TestOp\(.*\) is not supported\.",
        ):
            CalculateFlows.propagate_input_flow_basis(
                input_flow_info=[FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1))],
                qubits=body.args,
                ops=[unknown_op],
            )

    def test_calculate_flows_ignores_detectors(self) -> None:
        """Test that propagate_input_flows ignores detectors."""
        body = Block(arg_types=[qcore.QubitType()])
        (q0,) = body.args
        detector = qec.DetectorOp([q0])
        res = CalculateFlows.propagate_input_flow_basis(
            input_flow_info=[FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1))],
            qubits=body.args,
            ops=[detector],
        )
        all_states = list(res.get_all_states())
        assert len(all_states) == 1
        assert all_states[0].flow_state == qcore.PauliStringAttr([("X", 0)], 1)
        assert all_states[0].mmt_ssa == MMTResults()

    def test_current_states_propagate_clifford_h_on_three_qubits_via_sequence(self) -> None:
        """Apply H sequentially on q0, q1, q2 and ensure flow updates across all three.

        Start with X0 + Y1 + Z2.
        After H on q0: Z0 + Y1 + Z2; H on q1 leaves Y1; H on q2 maps Z2->X2.
        """
        body = Block(arg_types=[qcore.QubitType(), qcore.QubitType(), qcore.QubitType()])
        q0, q1, q2 = body.args
        h0 = qref.GateOp(qcore.HGateAttr(), [q0])
        h1 = qref.GateOp(qcore.HGateAttr(), [q1])
        h2 = qref.GateOp(qcore.HGateAttr(), [q2])
        current = CurrentStates(
            [FlowChainInfo(qcore.PauliStringAttr([("X", 0), ("Y", 1), ("Z", 2)], 3))],
            num_qubits=3,
            auto_reduce=False,
        )
        current.propagate([h0], body.args)
        all_states = list(current.get_all_states())
        assert len(all_states) == 1
        assert all_states[0].flow_state == qcore.PauliStringAttr([("Z", 0), ("Y", 1), ("Z", 2)], 3)
        current.propagate([h1], body.args)
        all_states = list(current.get_all_states())
        assert len(all_states) == 1
        assert all_states[0].flow_state == qcore.PauliStringAttr([("Z", 0), ("Y", 1), ("Z", 2)], 3)
        current.propagate([h2], body.args)
        all_states = list(current.get_all_states())
        assert len(all_states) == 1
        assert all_states[0].flow_state == qcore.PauliStringAttr([("Z", 0), ("Y", 1), ("X", 2)], 3)

    # --- Tests for propagate with unblocking ---

    def test_current_states_propagate_all_blocked_unblocks_via_product(self) -> None:
        """When all input states are blocked by M_Z, unblocking forms products that propagate."""
        body = Block(arg_types=[qcore.QubitType()])
        (q0,) = body.args
        m_gate = qref.MeasureOp("Z", [q0])

        # Both X0 and Y0 anticommute with M_Z -> both blocked
        current = CurrentStates.from_flows(
            1,
            [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1))],
            propagating_flows=[
                make_state([("X", 0)], 1),
                make_state([("Y", 0)], 1),
            ],
            auto_reduce=False,
        )

        current.propagate([m_gate], body.args)

        # Unblocking recovers Z0 from the product
        all_states = list(current.get_all_states())
        # Expected states: I -> Z0, I -> Z0 (mmt), I -> I (mmt)
        assert sorted(
            all_states, key=lambda cs: (cs.flow_state.sort_key(), cs.num_measurements)
        ) == [
            make_state([], 1, m_gate.measurements, newly_created=True),
            make_state([("Z", 0)], 1, newly_created=True),
            make_state([("Z", 0)], 1, m_gate.measurements, newly_created=True),
        ]

    def test_current_states_propagate_one_blocked_no_unblock(self) -> None:
        """When only one state is blocked (no pairs), only the non-blocked states propagate."""
        body = Block(arg_types=[qcore.QubitType()])
        (q0,) = body.args
        m_gate = qref.MeasureOp("Z", [q0])

        # X0 anticommutes (blocked), Z0 commutes (propagates)
        current = CurrentStates.from_flows(
            1,
            [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1))],
            propagating_flows=[
                make_state([("X", 0)], 1),
                make_state([("Z", 0)], 1),
            ],
            auto_reduce=False,
        )

        current.propagate([m_gate], body.args)

        all_states = list(current.get_all_states())
        # Expected flows: X0 -> Z0, X0 -> I (mmt), I -> Z0 (mmt)
        assert sorted(
            all_states, key=lambda cs: (cs.flow_state.sort_key(), cs.num_measurements)
        ) == [
            make_state([], 1, m_gate.measurements),
            make_state([("Z", 0)], 1),
            make_state([("Z", 0)], 1, m_gate.measurements, newly_created=True),
        ]

    def test_current_states_propagate_mixed_blocked_and_propagated(self) -> None:
        """Two blocked + one propagated: unblocking adds extra branches alongside normal ones."""
        body = Block(arg_types=[qcore.QubitType(), qcore.QubitType()])
        q0, _ = body.args
        m_gate = qref.MeasureOp("Z", [q0])

        # X0, Y0 anticommute (blocked); Z0Z1 commutes (propagates)
        current = CurrentStates.from_flows(
            2,
            [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 2))],
            propagating_flows=[
                make_state([("X", 0)], 2),
                make_state([("Y", 0)], 2),
                make_state([("Z", 0), ("Z", 1)], 2),
            ],
            auto_reduce=False,
        )

        current.propagate([m_gate], body.args)

        all_states = list(current.get_all_states())
        # Expected flows: X0 -> Z0Z1, X0 -> Z1 (mmt), I -> Z0, I -> I (mmt), I -> Z0 (mmt),
        # where I -> Z0 and I -> I are from the product X0*Y0 = Z0
        assert sorted(
            all_states, key=lambda cs: (cs.flow_state.sort_key(), cs.num_measurements)
        ) == [
            make_state([], 2, m_gate.measurements, newly_created=True),
            make_state([("Z", 0), ("Z", 1)], 2),
            make_state([("Z", 0)], 2, newly_created=True),
            make_state([("Z", 0)], 2, m_gate.measurements, newly_created=True),
            make_state([("Z", 1)], 2, m_gate.measurements),
        ]

    def test_current_states_propagate_all_blocked_by_reset_different_paulis_stays_blocked(
        self,
    ) -> None:
        """Reset blocking with different Paulis cannot be unblocked, so all-blocked stays
        blocked."""
        body = Block(arg_types=[qcore.QubitType()])
        (q0,) = body.args
        r_gate = qref.ResetOp("Z", [q0])

        # X0 and Y0 are blocked by reset; product Z0 is still blocked
        current = CurrentStates.from_flows(
            1,
            [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1))],
            propagating_flows=[
                make_state([("X", 0)], 1),
                make_state([("Y", 0)], 1),
            ],
            auto_reduce=False,
        )

        current.propagate([r_gate], body.args)

        # States should be just the reset gate I -> Z0, as the rest are blocked
        all_states = list(current.get_all_states())
        assert sorted(
            all_states, key=lambda cs: (cs.flow_state.sort_key(), cs.num_measurements)
        ) == [
            make_state([("Z", 0)], 1, newly_created=True),
        ]

    def test_current_states_propagate_all_blocked_by_reset_same_pauli_unblocks(self) -> None:
        """Reset blocking with same Paulis can be unblocked (product is identity on target)."""
        body = Block(arg_types=[qcore.QubitType(), qcore.QubitType()])
        q0, _ = body.args
        r_gate = qref.ResetOp("Z", [q0])

        # X0 and X0X1 blocked by reset; product X1 passes through reset (branches: I->Z0X1, I->X1)
        current = CurrentStates.from_flows(
            2,
            [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 2))],
            propagating_flows=[
                make_state([("X", 0)], 2),
                make_state([("X", 0), ("X", 1)], 2),
            ],
            auto_reduce=False,
        )

        current.propagate([r_gate], body.args)

        all_states = list(current.get_all_states())
        # Expected flows: I -> Z0X1, I -> X1, I -> Z0
        assert sorted(
            all_states, key=lambda cs: (cs.flow_state.sort_key(), cs.num_measurements)
        ) == [
            make_state([("Z", 0), ("X", 1)], 2, newly_created=True),
            make_state([("Z", 0)], 2, newly_created=True),
            make_state([("X", 1)], 2, newly_created=True),
        ]

    def test_current_states_propagate_reset_more_complex_unblock(self) -> None:
        """Reset unblocking with several Paulis of different kinds unblocks maximally."""
        body = Block(arg_types=[qcore.QubitType(), qcore.QubitType(), qcore.QubitType()])
        q0, _, _ = body.args
        r_gate = qref.ResetOp("Z", [q0])

        current = CurrentStates.from_flows(
            3,
            [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 3))],
            propagating_flows=[
                make_state([("X", 0)], 3),
                make_state([("Y", 0), ("Y", 1), ("X", 2)], 3, newly_created=True),
                make_state([("X", 0), ("Z", 1)], 3, newly_created=True),
                make_state([("Y", 0)], 3),
                make_state([("Z", 0)], 3),
                make_state([("Z", 0), ("X", 1)], 3, newly_created=True),
            ],
            auto_reduce=False,
        )

        current.propagate([r_gate], body.args)

        all_states = list(current.get_all_states())
        # Expected flows:
        # from unblocking X: X0 -> Z1, X0 -> Z0Z1
        # from unblocking Y: X0 -> Y1X2, X0 -> Z0Y1X2
        # from unblocking Z: X0 -> X1, X0 -> Z0X1
        # from multiplying youngest XYZ chain: I -> X2, I -> Z0X2
        # from identity: I -> Z0
        assert sorted(
            all_states, key=lambda cs: (cs.flow_state.sort_key(), cs.num_measurements)
        ) == [
            make_state([("Z", 0), ("Y", 1), ("X", 2)], 3),
            make_state([("Z", 0), ("X", 1)], 3),
            make_state([("Z", 0), ("Z", 1)], 3),
            make_state([("Z", 0), ("X", 2)], 3, newly_created=True),
            make_state([("Z", 0)], 3, newly_created=True),
            make_state([("Y", 1), ("X", 2)], 3),
            make_state([("X", 1)], 3),
            make_state([("Z", 1)], 3),
            make_state([("X", 2)], 3, newly_created=True),
        ]

    def test_current_states_propagate_unblocking_extending_combinations(self) -> None:
        """Test that propagate's unblocking works correctly with flows of different ages and
        extending combinations."""
        body = Block(arg_types=[qcore.QubitType()])
        (q0,) = body.args
        m_gate = qref.MeasureOp("Z", [q0])

        current = CurrentStates.from_flows(
            1,
            [
                FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 1), age=1),
                FlowChainInfo(qcore.PauliStringAttr([("Y", 0)], 1), age=2),
            ],
            propagating_flows=[
                make_state([("X", 0)], 1, extending_combination={0}),
                make_state([("Y", 0)], 1, extending_combination={1}),
            ],
            auto_reduce=False,
        )

        current.propagate([m_gate], body.args)

        all_states = list(current.get_all_states())
        # Expected flows: Z0 -> Z0, Z0 -> I (mmt) (from product of X and Y), I -> Z0 (mmt)
        assert sorted(
            all_states, key=lambda cs: (cs.flow_state.sort_key(), cs.num_measurements)
        ) == [
            make_state([], 1, m_gate.measurements, extending_combination={0, 1}),
            make_state([("Z", 0)], 1, extending_combination={0, 1}),
            make_state([("Z", 0)], 1, m_gate.measurements, newly_created=True),
        ]

    def test_current_states_propagate_parallel_single_branch_delegates_to_branch(self) -> None:
        """Propagating a parallel op with a single region should behave like that branch alone."""
        body = Block(arg_types=[qcore.QubitType()])
        (q0,) = body.args
        m_gate = qref.MeasureOp("Z", [q0])
        region = Region(Block([m_gate]))
        par = qstruct.ParallelOp(result_types=[], par_regions=[region])

        current = CurrentStates(
            [FlowChainInfo(qcore.PauliStringAttr([("Z", 0)], 1))], num_qubits=1, auto_reduce=False
        )
        current.propagate([par], body.args)
        # Expect the same two branches as the single-branch measurement case
        assert any(
            cs.flow_state == qcore.PauliStringAttr([("Z", 0)], 1) and cs.mmt_ssa == MMTResults()
            for cs in current.get_all_states()
        )
        assert any(
            cs.flow_state == qcore.PauliStringAttr.identity(1)
            and MMTResults(m_gate.measurements).issubset(cs.mmt_ssa or MMTResults())
            for cs in current.get_all_states()
        )

    def test_current_states_propagate_parallel_ignores_unused_qubits(self) -> None:
        """Flows on qubits not mentioned in any parallel region should be passed through
        untouched."""
        body = Block(arg_types=[qcore.QubitType(), qcore.QubitType()])
        q0, _ = body.args
        m_gate = qref.MeasureOp("Z", [q0])
        region = Region(Block([m_gate]))
        par = qstruct.ParallelOp(result_types=[], par_regions=[region])

        current = CurrentStates(
            [FlowChainInfo(qcore.PauliStringAttr([("X", 1)], 2))], num_qubits=2, auto_reduce=False
        )
        current.propagate([par], body.args)
        # Expect two branches: keep X1 (no record) and create Z0 X1 with record
        assert any(
            cs.flow_state == qcore.PauliStringAttr([("X", 1)], 2) and cs.mmt_ssa == MMTResults()
            for cs in current.get_all_states()
        )
        assert any(
            cs.flow_state == qcore.PauliStringAttr([("Z", 0), ("X", 1)], 2)
            and MMTResults(m_gate.measurements).issubset(cs.mmt_ssa or MMTResults())
            for cs in current.get_all_states()
        )

    def test_current_states_propagate_parallel_two_regions_sequential(self) -> None:
        """Two regions in parallel: H on q0 and M_Z on q1; start X0 Z1.
        Expect outputs containing Z0 Z1 (no record) and Z0 (record of q1's measurement), just as if
        they were in sequence."""
        body = Block(arg_types=[qcore.QubitType(), qcore.QubitType()])
        q0, q1 = body.args

        h0 = qref.GateOp(qcore.HGateAttr(), [q0])
        m1 = qref.MeasureOp("Z", [q1])
        par = qstruct.ParallelOp(
            result_types=[], par_regions=[Region(Block([h0])), Region(Block([m1]))]
        )

        current = CurrentStates(
            [FlowChainInfo(qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2))],
            num_qubits=2,
            auto_reduce=False,
        )
        current.propagate([par], body.args)

        # At least one branch keeps Z1 and maps X0->Z0; another records and removes Z1
        assert any(
            cs.flow_state == qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 2)
            for cs in current.get_all_states()
        )
        assert any(
            cs.flow_state == qcore.PauliStringAttr([("Z", 0)], 2)
            and MMTResults(m1.measurements).issubset(cs.mmt_ssa or MMTResults())
            for cs in current.get_all_states()
        )

    def test_current_states_propagate_nested_parallel(self) -> None:
        """One region has an inner parallel {H0}{H1} followed by M_Z on q0;
        the other region has M_Z on q2. Starting from X0 X1, expected flow state
        outputs are Z0 Z1, Z1, Z0 Z1 Z2, Z1 Z2 (since reduction is not done yet),
        plus I -> Z0, I -> Z2, I -> Z0 Z2.
        """
        body = Block(arg_types=[qcore.QubitType(), qcore.QubitType(), qcore.QubitType()])
        q0, q1, q2 = body.args

        # Inner parallel with H on q0 and H on q1
        h0 = qref.GateOp(qcore.HGateAttr(), [q0])
        h1 = qref.GateOp(qcore.HGateAttr(), [q1])
        inner_par = qstruct.ParallelOp(
            result_types=[], par_regions=[Region(Block([h0])), Region(Block([h1]))]
        )

        # Then measure Z on q0 in the same outer region
        m0 = qref.MeasureOp("Z", [q0])
        region_a = Region(Block([inner_par, m0]))

        # Other outer region: measure Z on q2
        m2 = qref.MeasureOp("Z", [q2])
        region_b = Region(Block([m2]))

        # Outer parallel op with two regions
        par = qstruct.ParallelOp(result_types=[], par_regions=[region_a, region_b])

        current = CurrentStates(
            [FlowChainInfo(qcore.PauliStringAttr([("X", 0), ("X", 1)], 3))],
            num_qubits=3,
            auto_reduce=False,
        )
        current.propagate([par], body.args)

        all_states = list(current.get_all_states())
        assert sorted(
            all_states, key=lambda cs: (cs.flow_state.sort_key(), cs.num_measurements)
        ) == [
            make_state([("Z", 0), ("Z", 1), ("Z", 2)], 3, m2.measurements),
            make_state([("Z", 0), ("Z", 1)], 3),
            make_state(
                [("Z", 0), ("Z", 2)], 3, m0.measurements + m2.measurements, newly_created=True
            ),
            make_state([("Z", 0)], 3, m0.measurements, newly_created=True),
            make_state([("Z", 1), ("Z", 2)], 3, m0.measurements + m2.measurements),
            make_state([("Z", 1)], 3, m0.measurements),
            make_state([("Z", 2)], 3, m2.measurements, newly_created=True),
        ]

    def test_current_states_propagate_sequential_resets_reduces(self) -> None:
        """Sequential RZ on qubits 0..3, expect to reduce to branches I -> {I, Z0, Z1, Z2, Z3}
        starting from I, and blocked on RZ 0 starting from X0."""
        body = Block(
            arg_types=[qcore.QubitType(), qcore.QubitType(), qcore.QubitType(), qcore.QubitType()]
        )
        q0, q1, q2, q3 = body.args

        r0 = qref.ResetOp("Z", [q0])
        r1 = qref.ResetOp("Z", [q1])
        r2 = qref.ResetOp("Z", [q2])
        r3 = qref.ResetOp("Z", [q3])

        # Starting from identity
        current = CurrentStates(
            [FlowChainInfo(qcore.PauliStringAttr.identity(4))], num_qubits=4, auto_reduce=False
        )
        current.propagate([r0, r1, r2, r3], body.args)
        current.reduce()

        got = {cs.flow_state for cs in current.get_all_states()}
        assert got == {
            qcore.PauliStringAttr.identity(4),
            qcore.PauliStringAttr([("Z", 0)], 4),
            qcore.PauliStringAttr([("Z", 1)], 4),
            qcore.PauliStringAttr([("Z", 2)], 4),
            qcore.PauliStringAttr([("Z", 3)], 4),
        }

        # Starting from X0
        current = CurrentStates(
            [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 4))], num_qubits=4, auto_reduce=False
        )
        current.propagate([r0, r1, r2, r3], body.args)
        current.reduce()

        # X0 should be blocked - flow states are I -> {Z0, Z1, Z2, Z3}, nothing starting with X0
        got = {cs.flow_state for cs in current.get_all_states()}
        assert got == {
            qcore.PauliStringAttr([("Z", 0)], 4),
            qcore.PauliStringAttr([("Z", 1)], 4),
            qcore.PauliStringAttr([("Z", 2)], 4),
            qcore.PauliStringAttr([("Z", 3)], 4),
        }

    def test_current_states_propagate_parallel_resets_reduces(self) -> None:
        """The same happens when the resets are in a parallel op instead of sequential."""
        body = Block(
            arg_types=[qcore.QubitType(), qcore.QubitType(), qcore.QubitType(), qcore.QubitType()]
        )
        q0, q1, q2, q3 = body.args

        r0 = qref.ResetOp("Z", [q0])
        r1 = qref.ResetOp("Z", [q1])
        r2 = qref.ResetOp("Z", [q2])
        r3 = qref.ResetOp("Z", [q3])
        par = qstruct.ParallelOp(
            result_types=[],
            par_regions=[Region(Block([r])) for r in [r0, r1, r2, r3]],
        )

        # Starting from identity
        current = CurrentStates(
            [FlowChainInfo(qcore.PauliStringAttr.identity(4))], num_qubits=4, auto_reduce=False
        )
        current.propagate([par], body.args)
        current.reduce()

        got = {cs.flow_state for cs in current.get_all_states()}
        assert got == {
            qcore.PauliStringAttr.identity(4),
            qcore.PauliStringAttr([("Z", 0)], 4),
            qcore.PauliStringAttr([("Z", 1)], 4),
            qcore.PauliStringAttr([("Z", 2)], 4),
            qcore.PauliStringAttr([("Z", 3)], 4),
        }

        # Starting from X0
        current = CurrentStates(
            [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 4))], num_qubits=4, auto_reduce=False
        )
        current.propagate([par], body.args)
        current.reduce()

        got = {cs.flow_state for cs in current.get_all_states()}
        assert got == {
            qcore.PauliStringAttr([("Z", 0)], 4),
            qcore.PauliStringAttr([("Z", 1)], 4),
            qcore.PauliStringAttr([("Z", 2)], 4),
            qcore.PauliStringAttr([("Z", 3)], 4),
        }

    def test_current_states_propagate_sequential_measurements_reduces(self) -> None:
        """Sequential MZ on qubits 0..3, expect to reduce to I -> {I, Z0, Z1, Z2, Z3} with
        measurement histories starting from I, to Z0 -> {I, Z0} and I -> {Z1, Z2, Z3} with
        measurement histories starting from Z0, and blocked on MZ 0 starting from X0."""
        body = Block(arg_types=[qcore.QubitType() for _ in range(4)])
        q0, q1, q2, q3 = body.args

        m0 = qref.MeasureOp("Z", [q0])
        m1 = qref.MeasureOp("Z", [q1])
        m2 = qref.MeasureOp("Z", [q2])
        m3 = qref.MeasureOp("Z", [q3])

        # Starting from identity
        current = CurrentStates(
            [FlowChainInfo(qcore.PauliStringAttr.identity(4))], num_qubits=4, auto_reduce=False
        )
        current.propagate([m0, m1, m2, m3], body.args)
        current.reduce()  # reduce manually to ensure it's done here
        got = {cs.flow_state for cs in current.get_all_states()}
        assert got == {
            qcore.PauliStringAttr.identity(4),
            qcore.PauliStringAttr([("Z", 0)], 4),
            qcore.PauliStringAttr([("Z", 1)], 4),
            qcore.PauliStringAttr([("Z", 2)], 4),
            qcore.PauliStringAttr([("Z", 3)], 4),
        }
        assert all(
            any(
                MMTResults(m.measurements).issubset(cs.mmt_ssa or MMTResults())
                for cs in current.get_all_states()
            )
            for m in [m0, m1, m2, m3]
        )

        # Starting from Z0
        current = CurrentStates(
            [FlowChainInfo(qcore.PauliStringAttr([("Z", 0)], 4))], num_qubits=4, auto_reduce=False
        )
        current.propagate([m0, m1, m2, m3], body.args)
        current.reduce()
        got = {cs.flow_state for cs in current.get_all_states()}
        assert got == {
            qcore.PauliStringAttr.identity(4),
            qcore.PauliStringAttr([("Z", 0)], 4),
            qcore.PauliStringAttr([("Z", 1)], 4),
            qcore.PauliStringAttr([("Z", 2)], 4),
            qcore.PauliStringAttr([("Z", 3)], 4),
        }
        assert all(
            any(
                MMTResults(m.measurements).issubset(cs.mmt_ssa or MMTResults())
                for cs in current.get_all_states()
            )
            for m in [m0, m1, m2, m3]
        )

        # Starting from X0
        current = CurrentStates(
            [FlowChainInfo(qcore.PauliStringAttr([("X", 0)], 4))], num_qubits=4, auto_reduce=False
        )
        current.propagate([m0, m1, m2, m3], body.args)
        current.reduce()

        # Blocked on X0, so nothing starting from X0 again
        got = {cs.flow_state for cs in current.get_all_states()}
        assert got == {
            qcore.PauliStringAttr([("Z", 0)], 4),
            qcore.PauliStringAttr([("Z", 1)], 4),
            qcore.PauliStringAttr([("Z", 2)], 4),
            qcore.PauliStringAttr([("Z", 3)], 4),
        }


# --- backpropagate_observable tests for Clifford gates ---


def _make_block(num_qubits: int) -> Block:
    return Block(arg_types=[qcore.QubitType() for _ in range(num_qubits)])


def test_backpropagate_h_full_overlap():
    body = _make_block(1)
    (q0,) = body.args
    gate = qref.GateOp(qcore.HGateAttr(), [q0])
    obs = qcore.PauliStringAttr([("X", 0)], 1)
    out = backpropagate_observable(gate, obs, body.args)
    assert out == qcore.PauliStringAttr([("Z", 0)], 1)


def test_backpropagate_h_partial_overlap():
    body = _make_block(2)
    q0, _ = body.args
    gate = qref.GateOp(qcore.HGateAttr(), [q0])
    obs = qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2)
    out = backpropagate_observable(gate, obs, body.args)
    assert out == qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 2)


def test_backpropagate_x_full_overlap():
    body = _make_block(1)
    (q0,) = body.args
    gate = qref.GateOp(qcore.XGateAttr(), [q0])
    obs = qcore.PauliStringAttr([("Z", 0)], 1)
    out = backpropagate_observable(gate, obs, body.args)
    assert out == qcore.PauliStringAttr([("Z", 0)], 1)


def test_backpropagate_x_partial_overlap():
    body = _make_block(2)
    q0, _ = body.args
    gate = qref.GateOp(qcore.XGateAttr(), [q0])
    obs = qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2)
    out = backpropagate_observable(gate, obs, body.args)
    assert out == qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2)


def test_backpropagate_cnot_full_overlap():
    body = _make_block(2)
    q0, q1 = body.args
    gate = qref.GateOp(qcore.CXGateAttr(), [q0, q1])
    obs = qcore.PauliStringAttr([("X", 0), ("X", 1)], 2)
    out = backpropagate_observable(gate, obs, body.args)
    assert out == qcore.PauliStringAttr([("X", 0)], 2)


def test_backpropagate_cnot_partial_overlap():
    body = _make_block(3)
    q0, q1, _ = body.args
    gate = qref.GateOp(qcore.CXGateAttr(), [q0, q1])
    obs = qcore.PauliStringAttr([("X", 1), ("Z", 2)], 3)
    out = backpropagate_observable(gate, obs, body.args)
    assert out == qcore.PauliStringAttr([("X", 1), ("Z", 2)], 3)


def test_backpropagate_iswap_full_overlap():
    body = _make_block(2)
    q0, q1 = body.args
    gate = qref.GateOp(qcore.ISWAPGateAttr(), [q0, q1])
    obs = qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2)
    out = backpropagate_observable(gate, obs, body.args)
    assert out == qcore.PauliStringAttr([("Y", 1)], 2)


def test_backpropagate_iswap_partial_overlap():
    body = _make_block(3)
    q0, q1, _ = body.args
    gate = qref.GateOp(qcore.ISWAPGateAttr(), [q0, q1])
    obs = qcore.PauliStringAttr([("Z", 1), ("X", 2)], 3)
    out = backpropagate_observable(gate, obs, body.args)
    assert out == qcore.PauliStringAttr([("Z", 0), ("X", 2)], 3)


def test_backpropagate_cnot():
    body = _make_block(2)
    q0, q1 = body.args
    gate = qref.GateOp(qcore.CXGateAttr(), [q0, q1])
    obs = qcore.PauliStringAttr([("X", 1)], 2)
    out = backpropagate_observable(gate, obs, body.args)
    assert out == qcore.PauliStringAttr([("X", 1)], 2)


def test_backpropagate_iswap():
    body = _make_block(2)
    q0, q1 = body.args
    gate = qref.GateOp(qcore.ISWAPGateAttr(), [q0, q1])
    obs = qcore.PauliStringAttr([("Z", 1)], 2)
    out = backpropagate_observable(gate, obs, body.args)
    assert out == qcore.PauliStringAttr([("Z", 0)], 2)


# --- backpropagate_observable tests for measurement gates ---


def test_backpropagate_measurement_1q_observable_none():
    body = _make_block(1)
    (q0,) = body.args
    gate = qref.MeasureOp("Z", [q0])
    obs = qcore.PauliStringAttr.identity(1)
    out = backpropagate_observable(gate, obs, body.args)
    assert out == qcore.PauliStringAttr.identity(1)


def test_backpropagate_measurement_1q_commuting():
    body = _make_block(1)
    (q0,) = body.args
    gate = qref.MeasureOp("Z", [q0])
    obs = qcore.PauliStringAttr([("Z", 0)], 1)
    out = backpropagate_observable(gate, obs, body.args)
    assert out == qcore.PauliStringAttr([("Z", 0)], 1)


def test_backpropagate_measurement_1q_anticommuting():
    body = _make_block(1)
    (q0,) = body.args
    gate = qref.MeasureOp("Z", [q0])
    obs = qcore.PauliStringAttr([("X", 0)], 1)
    out = backpropagate_observable(gate, obs, body.args)
    assert out == qcore.PauliStringAttr.identity(1)


# --- backpropagate_observable tests for reset gates ---


def test_backpropagate_reset_1q_empty_flow():
    body = _make_block(1)
    (q0,) = body.args
    gate = qref.ResetOp("Z", [q0])
    obs = qcore.PauliStringAttr.identity(1)
    out = backpropagate_observable(gate, obs, body.args)
    assert out == qcore.PauliStringAttr.identity(1)


@pytest.mark.parametrize(
    ("gate_op", "indices"),
    [
        # Single-qubit gate but >1 index
        (qcore.HGateAttr(), [0, 1]),
        # Two-qubit gate but >2 indices
        (qcore.CXGateAttr(), [0, 1, 2, 3]),
    ],
)
def test_apply_clifford_raises_on_broadcast(gate_op, indices):
    """apply_clifford should raise ValueError when flow is not local for the gate arity."""
    flow_state = qcore.PauliStringAttr([("X", 0), ("Z", 1), ("Y", 2)], 4)
    with pytest.raises(ValueError, match=r"Expected \d+ indices for .*, but got \d+\."):
        CliffordFlows.apply_clifford(gate_op, indices, flow_state)


def test_apply_clifford_raises_on_non_clifford():
    """apply_clifford should raise NotImplementedError when given a non-Clifford gate."""
    flow_state = qcore.PauliStringAttr([("X", 0)], 1)
    with pytest.raises(NotImplementedError, match=r"Gate .* not implemented yet or not Clifford\."):
        CliffordFlows.apply_clifford(qcore.TGateAttr(), [0], flow_state)


@pytest.mark.parametrize(
    "gate_type",
    [
        qcore.IdentityGateAttr(),
        qcore.XGateAttr(),
        qcore.YGateAttr(),
        qcore.ZGateAttr(),
        qcore.HGateAttr(),
        qcore.SGateAttr(),
        qcore.SGateAttr(dag=True),
    ],
)
def test_apply_clifford_supported_one_qubit_gates(gate_type):
    """apply_clifford supports all supported one-qubit Clifford gates."""
    flow_state = qcore.PauliStringAttr([("X", 0)], 1)
    out = CliffordFlows.apply_clifford(gate_type, [0], flow_state)
    assert not out.is_identity()


@pytest.mark.parametrize(
    "gate_type",
    [
        qcore.CXGateAttr(),
        qcore.CYGateAttr(),
        qcore.CZGateAttr(),
        qcore.SWAPGateAttr(),
        qcore.ISWAPGateAttr(),
        qcore.ISWAPGateAttr(dag=True),
        qcore.SqrtXXGateAttr(),
        qcore.SqrtYYGateAttr(),
        qcore.SqrtZZGateAttr(),
        qcore.SqrtXXGateAttr(dag=True),
        qcore.SqrtYYGateAttr(dag=True),
        qcore.SqrtZZGateAttr(dag=True),
    ],
)
def test_apply_clifford_supported_two_qubit_gates(gate_type):
    """apply_clifford supports all supported two-qubit Clifford gates."""
    flow_state = qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2)
    out = CliffordFlows.apply_clifford(gate_type, [0, 1], flow_state)
    assert not out.is_identity()


ALL_ONE_QUBIT_PAULIS = [
    qcore.PauliStringAttr.identity(1),
    qcore.PauliStringAttr([("X", 0)], 1),
    qcore.PauliStringAttr([("Y", 0)], 1),
    qcore.PauliStringAttr([("Z", 0)], 1),
]

ALL_TWO_QUBIT_PAULIS = [
    qcore.PauliStringAttr.identity(2),
    qcore.PauliStringAttr([("X", 0)], 2),
    qcore.PauliStringAttr([("Y", 0)], 2),
    qcore.PauliStringAttr([("Z", 0)], 2),
    qcore.PauliStringAttr([("X", 1)], 2),
    qcore.PauliStringAttr([("Y", 1)], 2),
    qcore.PauliStringAttr([("Z", 1)], 2),
    qcore.PauliStringAttr([("X", 0), ("X", 1)], 2),
    qcore.PauliStringAttr([("Y", 0), ("X", 1)], 2),
    qcore.PauliStringAttr([("Z", 0), ("X", 1)], 2),
    qcore.PauliStringAttr([("X", 0), ("Y", 1)], 2),
    qcore.PauliStringAttr([("Y", 0), ("Y", 1)], 2),
    qcore.PauliStringAttr([("Z", 0), ("Y", 1)], 2),
    qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2),
    qcore.PauliStringAttr([("Y", 0), ("Z", 1)], 2),
    qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 2),
]


@pytest.mark.parametrize(
    ("gate_type", "inv_gate_type"),
    [
        (qcore.XGateAttr(), qcore.XGateAttr()),
        (qcore.YGateAttr(), qcore.YGateAttr()),
        (qcore.ZGateAttr(), qcore.ZGateAttr()),
        (qcore.HGateAttr(), qcore.HGateAttr()),
        (qcore.SGateAttr(), qcore.SGateAttr(dag=True)),
        (qcore.SGateAttr(dag=True), qcore.SGateAttr()),
    ],
)
@pytest.mark.parametrize("flow_state", ALL_ONE_QUBIT_PAULIS)
def test_apply_clifford_single_qubit_inverses(gate_type, inv_gate_type, flow_state):
    """Sanity check that applying a gate and its inverse returns the original flow state."""
    out = CliffordFlows.apply_clifford(gate_type, [0], flow_state)
    out_inv = CliffordFlows.apply_clifford(inv_gate_type, [0], out)
    assert out_inv == flow_state


@pytest.mark.parametrize(
    ("gate_type", "inv_gate_type"),
    [
        (qcore.CXGateAttr(), qcore.CXGateAttr()),
        (qcore.CYGateAttr(), qcore.CYGateAttr()),
        (qcore.CZGateAttr(), qcore.CZGateAttr()),
        (qcore.SWAPGateAttr(), qcore.SWAPGateAttr()),
        (qcore.ISWAPGateAttr(), qcore.ISWAPGateAttr(dag=True)),
        (qcore.ISWAPGateAttr(dag=True), qcore.ISWAPGateAttr()),
        (qcore.SqrtXXGateAttr(), qcore.SqrtXXGateAttr(dag=True)),
        (qcore.SqrtYYGateAttr(), qcore.SqrtYYGateAttr(dag=True)),
        (qcore.SqrtZZGateAttr(), qcore.SqrtZZGateAttr(dag=True)),
        (qcore.SqrtXXGateAttr(dag=True), qcore.SqrtXXGateAttr()),
        (qcore.SqrtYYGateAttr(dag=True), qcore.SqrtYYGateAttr()),
        (qcore.SqrtZZGateAttr(dag=True), qcore.SqrtZZGateAttr()),
    ],
)
@pytest.mark.parametrize("flow_state", ALL_TWO_QUBIT_PAULIS)
def test_apply_clifford_two_qubit_inverses(gate_type, inv_gate_type, flow_state):
    """Sanity check that applying a gate and its inverse returns the original flow state."""
    out = CliffordFlows.apply_clifford(gate_type, [0, 1], flow_state)
    out_inv = CliffordFlows.apply_clifford(inv_gate_type, [0, 1], out)
    assert out_inv == flow_state


@pytest.mark.parametrize(
    ("conj1", "conj2", "conj1_dag", "conj2_dag", "gate", "result_gate"),
    [
        (
            qcore.IdentityGateAttr(),
            qcore.HGateAttr(),
            qcore.IdentityGateAttr(),
            qcore.HGateAttr(),
            qcore.CXGateAttr(),
            qcore.CZGateAttr(),
        ),
        (
            qcore.IdentityGateAttr(),
            qcore.HGateAttr(),
            qcore.IdentityGateAttr(),
            qcore.HGateAttr(),
            qcore.CZGateAttr(),
            qcore.CXGateAttr(),
        ),
        (
            qcore.IdentityGateAttr(),
            qcore.HGateAttr(),
            qcore.IdentityGateAttr(),
            qcore.HGateAttr(),
            qcore.CYGateAttr(),
            qcore.CYGateAttr(),
        ),
        (
            qcore.IdentityGateAttr(),
            qcore.SGateAttr(),
            qcore.IdentityGateAttr(),
            qcore.SGateAttr(dag=True),
            qcore.CXGateAttr(),
            qcore.CYGateAttr(),
        ),
        (
            qcore.IdentityGateAttr(),
            qcore.SGateAttr(),
            qcore.IdentityGateAttr(),
            qcore.SGateAttr(dag=True),
            qcore.CYGateAttr(),
            qcore.CXGateAttr(),
        ),
        (
            qcore.IdentityGateAttr(),
            qcore.SGateAttr(),
            qcore.IdentityGateAttr(),
            qcore.SGateAttr(dag=True),
            qcore.CZGateAttr(),
            qcore.CZGateAttr(),
        ),
        (
            qcore.HGateAttr(),
            qcore.HGateAttr(),
            qcore.HGateAttr(),
            qcore.HGateAttr(),
            qcore.SqrtXXGateAttr(),
            qcore.SqrtZZGateAttr(),
        ),
        (
            qcore.HGateAttr(),
            qcore.HGateAttr(),
            qcore.HGateAttr(),
            qcore.HGateAttr(),
            qcore.SqrtZZGateAttr(),
            qcore.SqrtXXGateAttr(),
        ),
        (
            qcore.HGateAttr(),
            qcore.HGateAttr(),
            qcore.HGateAttr(),
            qcore.HGateAttr(),
            qcore.SqrtYYGateAttr(),
            qcore.SqrtYYGateAttr(),
        ),
        (
            qcore.SGateAttr(),
            qcore.SGateAttr(),
            qcore.SGateAttr(dag=True),
            qcore.SGateAttr(dag=True),
            qcore.SqrtXXGateAttr(),
            qcore.SqrtYYGateAttr(),
        ),
        (
            qcore.SGateAttr(),
            qcore.SGateAttr(),
            qcore.SGateAttr(dag=True),
            qcore.SGateAttr(dag=True),
            qcore.SqrtYYGateAttr(),
            qcore.SqrtXXGateAttr(),
        ),
        (
            qcore.SGateAttr(),
            qcore.SGateAttr(),
            qcore.SGateAttr(dag=True),
            qcore.SGateAttr(dag=True),
            qcore.SqrtZZGateAttr(),
            qcore.SqrtZZGateAttr(),
        ),
        (
            qcore.HGateAttr(),
            qcore.HGateAttr(),
            qcore.HGateAttr(),
            qcore.HGateAttr(),
            qcore.SqrtXXGateAttr(dag=True),
            qcore.SqrtZZGateAttr(dag=True),
        ),
        (
            qcore.HGateAttr(),
            qcore.HGateAttr(),
            qcore.HGateAttr(),
            qcore.HGateAttr(),
            qcore.SqrtZZGateAttr(dag=True),
            qcore.SqrtXXGateAttr(dag=True),
        ),
        (
            qcore.HGateAttr(),
            qcore.HGateAttr(),
            qcore.HGateAttr(),
            qcore.HGateAttr(),
            qcore.SqrtYYGateAttr(dag=True),
            qcore.SqrtYYGateAttr(dag=True),
        ),
        (
            qcore.SGateAttr(),
            qcore.SGateAttr(),
            qcore.SGateAttr(dag=True),
            qcore.SGateAttr(dag=True),
            qcore.SqrtXXGateAttr(dag=True),
            qcore.SqrtYYGateAttr(dag=True),
        ),
        (
            qcore.SGateAttr(),
            qcore.SGateAttr(),
            qcore.SGateAttr(dag=True),
            qcore.SGateAttr(dag=True),
            qcore.SqrtYYGateAttr(dag=True),
            qcore.SqrtXXGateAttr(dag=True),
        ),
        (
            qcore.SGateAttr(),
            qcore.SGateAttr(),
            qcore.SGateAttr(dag=True),
            qcore.SGateAttr(dag=True),
            qcore.SqrtZZGateAttr(dag=True),
            qcore.SqrtZZGateAttr(dag=True),
        ),
    ],
)
@pytest.mark.parametrize("flow_state", ALL_TWO_QUBIT_PAULIS)
def test_apply_clifford_conjugate_identities(
    conj1, conj2, conj1_dag, conj2_dag, gate, result_gate, flow_state
):
    """Check that the following identity holds for all flow states:
    (conj1_dag ⊗ conj2_dag) * gate * (conj1 ⊗ conj2) = result_gate
    """
    out = CliffordFlows.apply_clifford(conj1, [0], flow_state)
    out2 = CliffordFlows.apply_clifford(conj2, [1], out)
    out3 = CliffordFlows.apply_clifford(gate, [0, 1], out2)
    out4 = CliffordFlows.apply_clifford(conj1_dag, [0], out3)
    out5 = CliffordFlows.apply_clifford(conj2_dag, [1], out4)
    out_result = CliffordFlows.apply_clifford(result_gate, [0, 1], flow_state)
    assert out5 == out_result


def test_backpropagate_reset_1q_full_overlap():
    body = _make_block(1)
    (q0,) = body.args
    gate = qref.ResetOp("Z", [q0])
    obs = qcore.PauliStringAttr([("X", 0)], 1)
    out = backpropagate_observable(gate, obs, body.args)
    assert out == qcore.PauliStringAttr.identity(1)


def test_backpropagate_reset_2q_partial_overlap():
    body = _make_block(2)
    q0, _ = body.args
    gate = qref.ResetOp("Z", [q0])
    obs = qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2)
    out = backpropagate_observable(gate, obs, body.args)
    assert out == qcore.PauliStringAttr([("Z", 1)], 2)


def test_backpropagate_reset_2q_targets_empty_flow():
    body = _make_block(2)
    q0, q1 = body.args
    gate = qref.ResetOp("Z", [q0, q1])
    obs = qcore.PauliStringAttr.identity(2)
    out = backpropagate_observable(gate, obs, body.args)
    assert out == qcore.PauliStringAttr.identity(2)


def test_backpropagate_reset_2q_targets_with_flow():
    body = _make_block(2)
    q0, q1 = body.args
    gate = qref.ResetOp("Z", [q0, q1])
    obs = qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 2)
    out = backpropagate_observable(gate, obs, body.args)
    assert out == qcore.PauliStringAttr.identity(2)


# Tests of rewrite circuit op methods


def _get_test_body(
    args: Sequence[Attribute],
    qubits: int,
    qubit_type: Attribute,
    measures: int,
    returns_op: test.TestOp | None,
    in_parallel: bool = False,
) -> Region:
    """Construct a single-block circuit region for testing.

    This helper builds a block with the given number of qubit-typed block
    arguments followed by any additional input ``args`` types. It optionally
    inserts a provided ``returns_op`` whose results become the yield arguments,
    then appends a measurement op producing ``measures`` boolean-like results
    and a final ``stab.yield`` that yields those measurements and any
    ``returns_op`` results.

    Args:
        args: Additional non-qubit argument types to append after the qubit
            block arguments.
        qubits: Number of qubit block arguments to create.
        qubit_type: The attribute/type used for each qubit block argument.
        measures: Number of 1-bit measurement results to produce and yield.
        returns_op: Optional op whose results are appended as yield arguments;
            if ``None``, no extra yield arguments are produced.
        in_parallel: If true, the measurements are wrapped in a parallel.

    Returns:
        Region: A region containing a single block with the constructed ops
        and a terminating ``stab.yield``.
    """
    ops: list[Operation] = []
    if returns_op is None:
        outputs = []
    else:
        ops.append(returns_op)
        outputs = list(returns_op.res)
    measurements = test.TestOp(result_types=[_uint_type(1)] * measures)
    if in_parallel:
        region = Region(Block([measurements, qstruct.YieldOp(*measurements.results)]))
        par = qstruct.ParallelOp(result_types=measurements.result_types, par_regions=[region])
        ops.append(par)
        to_yield = par.res
    else:
        ops.append(measurements)
        to_yield = measurements.res
    yield_op = YieldOp.build(operands=[to_yield, outputs])
    ops.append(yield_op)
    block = Block(arg_types=[qubit_type] * qubits + list(args), ops=ops)
    return Region(block)


def _uint_type(size: int | None = None) -> IntegerType:
    """Create an unsigned integer type of the given bit-width.

    Args:
        size: Bit-width for the unsigned integer. When ``None``, the
            repository default (``DEFAULT_UINT_SIZE``) is used.

    Returns:
        IntegerType: An unsigned integer type with the specified bit-width.
    """
    size = DEFAULT_UINT_SIZE if size is None else size
    return IntegerType(size, Signedness.UNSIGNED)


def test_update_state_type_adjacent_ops_relabels_flows() -> None:
    """Verify that updating the shared interface :class:`StateType` between two
    adjacent circuits inserts new flow states and consistently relabels the
    pre-existing flow indices on both sides.

    Pre-existing setup:
    - The interface state on the c1 -> c2 boundary has flow states ``[X0]`` and
      ``[Z1]`` (3-qubit context).
    - c1 emits two creation flows to the interface:
      * ``I -> X0`` labeled by measurement index ``[0]``.
      * ``I -> Z1`` labeled by measurement index ``[1]``.
    - c2 consumes two destruction flows from the interface:
      * ``X0 -> I`` (no measurements).
      * ``Z1 -> I`` (no measurements).

    Action:
    - Insert a new commuting two-qubit flow state ``[X0 Z1]`` into the shared
      interface via ``update_state_type_adjacent_ops(c1.output, [X0 Z1])``.
    - Canonical ordering (sorted by qubit indices, then Pauli codes) becomes
      ``[X0 Z1, X0, Z1]``.

    Expected relabeling:
    - Both circuits' interface types reflect the new canonical ordering.
    - c1's output-side flow state indices shift to match the insertion:
      * ``I -> X0``: index ``0`` becomes ``1``.
      * ``I -> Z1``: index ``1`` becomes ``2``.
    - c2's input-side flow state indices shift similarly:
      * ``X0 -> I``: index ``0`` becomes ``1``.
      * ``Z1 -> I``: index ``1`` becomes ``2``.
    Only the flow state indices change; measurement indices and signs are preserved.
    """
    # Common qubit/type context
    qtype = test.TestType("q")

    # Initial interface state type used between circuits: [X0], [Z1] with 3 qubits
    interface_type = StateType(3, qtype, [[("X", 0)], [("Z", 1)]])

    # c1 input (arbitrary), body yields 2 measurements
    c1_input = test.TestOp(result_types=[StateType(3, qtype, [])]).res[0]
    c1_body = _get_test_body([], 3, qtype, 2, None)

    # c1 flows: creation flows to the interface states
    c1_flows = [
        FlowAttr("+", [0], qcore.I_STATE_INDEX, 0),  # I -> X0
        FlowAttr("+", [1], qcore.I_STATE_INDEX, 1),  # I -> Z1
    ]

    c1 = CircuitOp(
        c1_input,
        interface_type,
        input_args=[],
        body=c1_body,
        flows=c1_flows,
    )

    # c2 consumes the shared interface state as input; body yields 0 measurements
    c2_body = _get_test_body([], 3, qtype, 0, None)
    c2_output_type = StateType(3, qtype, [])

    # c2 flows: destruction flows from the interface states
    c2_flows = [
        FlowAttr("-", [], 0, qcore.I_STATE_INDEX),  # X0 -> I
        FlowAttr("-", [], 1, qcore.I_STATE_INDEX),  # Z1 -> I
    ]

    c2 = CircuitOp(
        c1.output,  # shared SSA value from c1
        c2_output_type,
        input_args=[],
        body=c2_body,
        flows=c2_flows,
    )

    # Sanity: initial flows labels
    assert [f.output_state_index for f in cast(ArrayAttr[FlowAttr], c1.flows)] == [0, 1]
    assert [f.input_state_index for f in cast(ArrayAttr[FlowAttr], c2.flows)] == [0, 1]

    # Act: add a new commuting flow state X0 Z1 at the shared interface;
    # canonical order becomes [X0 Z1, X0, Z1]
    new_flows = [qcore.PauliStringAttr([("X", 0), ("Z", 1)], 3)]
    update_state_type_adjacent_ops(
        cast(SSAValue[StateType], c1.output), new_flows, PatternRewriter(c1.yield_op)
    )

    # Assert: interface type for both circuits updated canonically.
    # Sorting orders by indices first, then pauli codes; the two-qubit state comes first.
    exp_states = [
        qcore.PauliStringAttr([("X", 0), ("Z", 1)], 3),
        qcore.PauliStringAttr([("X", 0)], 3),
        qcore.PauliStringAttr([("Z", 1)], 3),
    ]
    assert list(c1.output_flows) == exp_states
    assert list(c2.input_flows) == exp_states

    # c1 flows relabeled on output side: I->X0 shifts to 1, I->Z1 shifts to 2
    assert [f.output_state_index for f in cast(ArrayAttr[FlowAttr], c1.flows)] == [1, 2]

    # c2 flows relabeled on input side: X0->I shifts to 1, Z1->I shifts to 2
    c2_flows_arr = cast(ArrayAttr[FlowAttr], c2.flows)
    assert [f.input_state_index for f in c2_flows_arr] == [1, 2]


def test_update_state_type_adjacent_ops_with_permute() -> None:
    """Test update_state_type_adjacent_ops with a StatePermuteOp between circuits.

    Setup: c1 -> permute(swap qubits 0,1) -> c2 on 2 qubits.
    - c1 output has [X0, Z1], c1 emits I->X0 and I->Z1.
    - Permute maps X0->X1, Z1->Z0; so permute output has [Z0, X1].
    - c2 consumes Z0->I and X1->I.

    Actions:
    1. Insert Z0X1 into permute.output; verify permute output changes but not input,
       and c2 flows re-index.
    2. Insert X0Z1 (the un-permuted Z0X1) into c1.output; verify c1 output changes
       and c1 flows re-index, but permute output doesn't change again.
    """
    qtype = test.TestType("q")

    # c1 outputs [X0, Z1]
    c1_input = test.TestOp(result_types=[StateType(2, qtype, [])]).res[0]
    c1_output_type = StateType(2, qtype, [[("X", 0)], [("Z", 1)]])
    c1_body = _get_test_body([], 2, qtype, 2, None)
    c1_flows = [
        FlowAttr("+", [0], qcore.I_STATE_INDEX, 0),  # I -> X0
        FlowAttr("+", [1], qcore.I_STATE_INDEX, 1),  # I -> Z1
    ]
    c1 = CircuitOp(c1_input, c1_output_type, input_args=[], body=c1_body, flows=c1_flows)

    # Permute swaps qubits 0 and 1: X0->X1, Z1->Z0; output has [Z0, X1]
    permute = StatePermuteOp(c1.output, permutation=[1, 0])

    # c2 consumes [Z0, X1]
    c2_body = _get_test_body([], 2, qtype, 0, None)
    c2_output_type = StateType(2, qtype, [])
    c2_flows = [
        FlowAttr("+", [], 0, qcore.I_STATE_INDEX),  # Z0 -> I
        FlowAttr("+", [], 1, qcore.I_STATE_INDEX),  # X1 -> I
    ]
    c2 = CircuitOp(permute.output, c2_output_type, input_args=[], body=c2_body, flows=c2_flows)

    # Sanity checks: initial flows and labels
    assert list(c1.output_flows) == [
        qcore.PauliStringAttr([("X", 0)], 2),
        qcore.PauliStringAttr([("Z", 1)], 2),
    ]
    assert list(permute.output.type.states) == [
        qcore.PauliStringAttr([("Z", 0)], 2),
        qcore.PauliStringAttr([("X", 1)], 2),
    ]
    assert [f.input_state_index for f in cast(ArrayAttr[FlowAttr], c2.flows)] == [0, 1]

    # Action 1: Insert Z0X1 into permute.output
    update_state_type_adjacent_ops(
        cast(SSAValue[StateType], permute.output),
        [qcore.PauliStringAttr([("Z", 0), ("X", 1)], 2)],
        PatternRewriter(c1.yield_op),
    )

    # Permute input unchanged, but output has [Z0X1, Z0, X1] (sorted canonically)
    assert list(cast(StateType, permute.input.type).states) == [
        qcore.PauliStringAttr([("X", 0)], 2),
        qcore.PauliStringAttr([("Z", 1)], 2),
    ]
    assert list(permute.output.type.states) == [
        qcore.PauliStringAttr([("Z", 0), ("X", 1)], 2),
        qcore.PauliStringAttr([("Z", 0)], 2),
        qcore.PauliStringAttr([("X", 1)], 2),
    ]
    # c2 flows re-indexed: Z0 at 1, X1 at 2
    assert [f.input_state_index for f in cast(ArrayAttr[FlowAttr], c2.flows)] == [1, 2]

    # Action 2: Insert X0Z1 (un-permuted Z0X1) into c1.output
    update_state_type_adjacent_ops(
        cast(SSAValue[StateType], c1.output),
        [qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2)],
        PatternRewriter(c1.yield_op),
    )

    # c1 output now has [X0Z1, X0, Z1]; c1 flows re-indexed: X0 at 1, Z1 at 2
    assert list(c1.output_flows) == [
        qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2),
        qcore.PauliStringAttr([("X", 0)], 2),
        qcore.PauliStringAttr([("Z", 1)], 2),
    ]
    assert [f.output_state_index for f in cast(ArrayAttr[FlowAttr], c1.flows)] == [1, 2]

    # Permute output unchanged (X0Z1 permutes to Z0X1 which was already there)
    assert list(permute.output.type.states) == [
        qcore.PauliStringAttr([("Z", 0), ("X", 1)], 2),
        qcore.PauliStringAttr([("Z", 0)], 2),
        qcore.PauliStringAttr([("X", 1)], 2),
    ]


def test_update_state_type_noop_when_no_flows_to_add() -> None:
    """No-op when no flow states are provided.

    Ensures interface types and existing flows remain unchanged when
    ``flows_to_add`` is empty.
    """
    qtype = test.TestType("q")

    input_state = test.TestOp(result_types=[StateType(2, qtype, [])]).res[0]
    output_state_type = StateType(2, qtype, [[("X", 0)], [("Z", 1)]])
    body = _get_test_body([], 2, qtype, 1, None)

    flows = [FlowAttr("+", [0], qcore.I_STATE_INDEX, 0), FlowAttr("-", [], 1, qcore.I_STATE_INDEX)]
    c1 = CircuitOp(input_state, output_state_type, input_args=[], body=body, flows=flows)

    c2_output_type = StateType(2, qtype, [])
    c2_body = _get_test_body([], 2, qtype, 0, None)
    c2 = CircuitOp(c1.output, c2_output_type, input_args=[], body=c2_body, flows=[])

    # Snapshot before
    before_c1_states = list(c1.output_flows)
    before_c2_states = list(c2.input_flows)
    assert c1.flows is not None
    assert c2.flows is not None
    before_c1_flows = list(cast(ArrayAttr[FlowAttr], c1.flows))
    before_c2_flows = list(cast(ArrayAttr[FlowAttr], c2.flows))

    # Act: empty additions
    update_state_type_adjacent_ops(
        cast(SSAValue[StateType], c1.output), [], PatternRewriter(c1.yield_op)
    )

    # Assert unchanged
    assert list(c1.output_flows) == before_c1_states
    assert list(c2.input_flows) == before_c2_states
    assert list(cast(ArrayAttr[FlowAttr], c1.flows)) == before_c1_flows
    assert list(cast(ArrayAttr[FlowAttr], c2.flows)) == before_c2_flows


def test_update_state_type_invalid_owner_raises() -> None:
    """Owner must be a CircuitOp or StateMakeOp."""
    qtype = test.TestType("q")
    # Produce a StateType via a generic TestOp (invalid owner)
    state_ssa = test.TestOp(result_types=[StateType(2, qtype, [])]).res[0]

    # Create a single consumer so unique use is satisfied
    body = _get_test_body([], 2, qtype, 0, None)
    consumer = CircuitOp(state_ssa, StateType(2, qtype, []), input_args=[], body=body, flows=[])

    with pytest.raises(
        ValueError,
        match=re.escape(
            "The input SSA value must result from a stab.CircuitOp, stab.StatePermuteOp, "
            "qstruct.ParallelOp, or stab.StateMakeOp."
        ),
    ):
        update_state_type_adjacent_ops(
            cast(SSAValue[StateType], state_ssa),
            [qcore.PauliStringAttr([("X", 0)], 2)],
            PatternRewriter(consumer.yield_op),
        )


def test_update_state_type_consumer_not_supported_raises() -> None:
    """Consumer must be a supported op."""
    qtype = test.TestType("q")
    input_state = test.TestOp(result_types=[StateType(2, qtype, [])]).res[0]
    body = _get_test_body([], 2, qtype, 1, None)
    c1 = CircuitOp(
        input_state,
        StateType(2, qtype, [[("X", 0)]]),
        input_args=[],
        body=body,
        flows=[],
    )

    # Consume with a StateCastOp (not supported)
    StateCastOp(c1.output, StateType(2, qtype, []))

    with pytest.raises(
        ValueError,
        match=re.escape(
            "The input SSA value must be used by a stab.CircuitOp, stab.StatePermuteOp, or "
            "qstruct.YieldOp."
        ),
    ):
        update_state_type_adjacent_ops(
            cast(SSAValue[StateType], c1.output),
            [qcore.PauliStringAttr([("Z", 1)], 2)],
            PatternRewriter(c1.yield_op),
        )


def test_update_state_type_consumer_yield_not_of_parallel_raises() -> None:
    """If consumer is a YieldOp, it must be from a parallel region."""
    qtype = test.TestType("q")
    input_state = test.TestOp(result_types=[StateType(2, qtype, [])]).res[0]
    body = _get_test_body([], 2, qtype, 1, None)
    c1 = CircuitOp(
        input_state,
        StateType(2, qtype, [[("X", 0)]]),
        input_args=[],
        body=body,
        flows=[],
    )

    # Create a qstruct.YieldOp that isn't in a parallel region
    yield_op = qstruct.YieldOp(c1.output)
    qstruct.RepeatOp(5, Block([yield_op]))

    with pytest.raises(
        ValueError,
        match=re.escape(
            "The input SSA value may only be used by a qstruct.YieldOp if it is the yield of a "
            "qstruct.ParallelOp."
        ),
    ):
        update_state_type_adjacent_ops(
            cast(SSAValue[StateType], c1.output),
            [qcore.PauliStringAttr([("Z", 1)], 2)],
            PatternRewriter(c1.yield_op),
        )


def test_update_state_type_when_only_identity_flow_to_add() -> None:
    """Test that the I flow state is allowed as input but must not be added to the StateType."""
    qtype = test.TestType("q")

    input_state = test.TestOp(result_types=[StateType(2, qtype, [])]).res[0]
    output_state_type = StateType(2, qtype, [[("X", 0)]])
    body = _get_test_body([], 2, qtype, 0, None)

    flows = [FlowAttr("+", [], qcore.I_STATE_INDEX, 0)]
    c1 = CircuitOp(input_state, output_state_type, input_args=[], body=body, flows=flows)
    c2_body = _get_test_body([], 2, qtype, 0, None)
    c2 = CircuitOp(c1.output, StateType(2, qtype, []), input_args=[], body=c2_body, flows=[])

    before_states = list(c1.output_flows)
    before_c1_flows = list(cast(ArrayAttr[FlowAttr], c1.flows))
    before_c2_flows = list(cast(ArrayAttr[FlowAttr], c2.flows))

    update_state_type_adjacent_ops(
        cast(SSAValue[StateType], c1.output),
        [qcore.PauliStringAttr.identity(2)],
        PatternRewriter(c1.yield_op),
    )

    assert list(c1.output_flows) == before_states
    assert list(c2.input_flows) == before_states
    assert list(cast(ArrayAttr[FlowAttr], c1.flows)) == before_c1_flows
    assert list(cast(ArrayAttr[FlowAttr], c2.flows)) == before_c2_flows


def test_update_state_type_updates_when_no_consumer_circuit() -> None:
    """If there's no consumer circuit, we still update the producer interface type.

    This covers the c2=None branch.
    """
    qtype = test.TestType("q")

    input_state = test.TestOp(result_types=[StateType(2, qtype, [])]).res[0]
    interface_type = StateType(2, qtype, [[("X", 0)]])
    body = _get_test_body([], 2, qtype, 0, None)

    flows = [FlowAttr("+", [], qcore.I_STATE_INDEX, 0)]
    c1 = CircuitOp(input_state, interface_type, input_args=[], body=body, flows=flows)

    new_states = [qcore.PauliStringAttr([("Z", 1)], 2)]
    update_state_type_adjacent_ops(
        cast(SSAValue[StateType], c1.output),
        new_states,
        PatternRewriter(c1.yield_op),
    )

    # Canonical ordering puts X0 then Z1 for this simple case.
    assert list(c1.output_flows) == [
        qcore.PauliStringAttr([("X", 0)], 2),
        qcore.PauliStringAttr([("Z", 1)], 2),
    ]
    # Flow indices should still point at the original X0, now index 0.
    assert [f.output_state_index for f in cast(ArrayAttr[FlowAttr], c1.flows)] == [0]


def test_update_state_type_state_make_output_cant_add_flows() -> None:
    """StateMakeOp outputs must not be extended with flow states."""
    qtype = test.TestType("q")

    # Build a StateMakeOp and try to add a non-identity flow state.
    # StateMakeOp takes the qubit SSAValues as operands; the op itself doesn't care where they
    # come from for this unit test.
    q0, q1 = test.TestOp(result_types=[qtype, qtype]).res
    sm = StateMakeOp([q0, q1], StateType(2, qtype, []))
    # Ensure the SSAValue has a unique consumer so we don't fail earlier.
    body = _get_test_body([], 2, qtype, 0, None)
    consumer = CircuitOp(sm.output, StateType(2, qtype, []), input_args=[], body=body, flows=[])

    with pytest.raises(
        ValueError,
        match=re.escape(
            "The SSAValue is the output of a stab.StateMakeOp which can't have any flow states."
        ),
    ):
        update_state_type_adjacent_ops(
            cast(SSAValue[StateType], sm.output),
            [qcore.PauliStringAttr([("X", 0)], 2)],
            PatternRewriter(consumer.yield_op),
        )


@pytest.mark.parametrize("input_side", [True, False])
def test_write_flows_relabel_flows_for_state_type_change(input_side: bool) -> None:
    """Relabel retained states on either side of a circuit interface and preserve identity."""
    x0 = qcore.PauliStringAttr([("X", 0)], 2)
    z1 = qcore.PauliStringAttr([("Z", 1)], 2)
    flows = ArrayAttr(
        [
            FlowAttr("+", [2], qcore.I_STATE_INDEX, 1),
            FlowAttr("-", [3], 1, qcore.I_STATE_INDEX),
        ]
    )

    relabelled = WriteFlows._relabel_flows_for_state_type_change(
        flows=flows,
        old_flow_states=[x0, z1],
        new_flow_states=[z1],
        input_side=input_side,
    )

    assert relabelled is not None
    if input_side:
        assert list(relabelled) == [
            FlowAttr("+", [2], qcore.I_STATE_INDEX, 1),
            FlowAttr("-", [3], 0, qcore.I_STATE_INDEX),
        ]
    else:
        assert list(relabelled) == [
            FlowAttr("+", [2], qcore.I_STATE_INDEX, 0),
            FlowAttr("-", [3], 1, qcore.I_STATE_INDEX),
        ]


@pytest.mark.parametrize("input_side", [True, False])
def test_write_flows_relabel_flows_rejects_removed_state_in_flow(input_side: bool) -> None:
    """Relabelling raises when a flow still references a removed state."""
    x0 = qcore.PauliStringAttr([("X", 0)], 2)
    z1 = qcore.PauliStringAttr([("Z", 1)], 2)
    flow = FlowAttr(
        "+",
        [],
        0 if input_side else qcore.I_STATE_INDEX,
        qcore.I_STATE_INDEX if input_side else 0,
    )

    with pytest.raises(ValueError, match=re.escape("Cannot remove flow state")):
        WriteFlows._relabel_flows_for_state_type_change(
            ArrayAttr([flow]),
            [x0, z1],
            [z1],
            input_side=input_side,
        )


def test_write_flows_remove_flow_states_from_output_updates_consumer() -> None:
    """Removing an output state relabels the producer and its direct circuit consumer."""
    qtype = test.TestType("q")
    x0 = qcore.PauliStringAttr([("X", 0)], 2)
    z1 = qcore.PauliStringAttr([("Z", 1)], 2)
    input_state = test.TestOp(result_types=[StateType(2, qtype, [])]).res[0]
    body = _get_test_body([], 2, qtype, 0, None)
    producer = CircuitOp(
        input_state,
        StateType(2, qtype, [x0, z1]),
        input_args=[],
        body=body,
        flows=[FlowAttr("+", [], qcore.I_STATE_INDEX, 1)],
    )
    consumer_one = CircuitOp(
        producer.output,
        StateType(2, qtype, []),
        input_args=[],
        body=_get_test_body([], 2, qtype, 0, None),
        flows=[FlowAttr("-", [], 1, qcore.I_STATE_INDEX)],
    )
    WriteFlows.remove_flow_states_from_output(producer, [x0], PatternRewriter(producer.yield_op))

    assert list(producer.output_flows) == [z1]
    assert list(consumer_one.input_flows) == [z1]
    assert producer.flows is not None
    assert list(producer.flows) == [FlowAttr("+", [], qcore.I_STATE_INDEX, 0)]
    assert consumer_one.flows is not None
    assert list(consumer_one.flows) == [FlowAttr("-", [], 0, qcore.I_STATE_INDEX)]


def test_write_flows_remove_flow_states_from_output_without_removals() -> None:
    """An empty removal list leaves the circuit unchanged."""
    qtype = test.TestType("q")
    x0 = qcore.PauliStringAttr([("X", 0)], 2)
    input_state = test.TestOp(result_types=[StateType(2, qtype, [])]).res[0]
    circuit = CircuitOp(
        input_state,
        StateType(2, qtype, [x0]),
        input_args=[],
        body=_get_test_body([], 2, qtype, 0, None),
        flows=[FlowAttr("+", [], qcore.I_STATE_INDEX, 0)],
    )

    WriteFlows.remove_flow_states_from_output(circuit, [], PatternRewriter(circuit.yield_op))

    assert list(circuit.output_flows) == [x0]
    assert circuit.flows is not None
    assert list(circuit.flows) == [FlowAttr("+", [], qcore.I_STATE_INDEX, 0)]


def test_write_flows_remove_flow_states_from_output_removes_empty_flows() -> None:
    """Removing the only output state removes flows from both adjacent circuits."""
    qtype = test.TestType("q")
    x0 = qcore.PauliStringAttr([("X", 0)], 2)
    input_state = test.TestOp(result_types=[StateType(2, qtype, [])]).res[0]
    producer = CircuitOp(
        input_state,
        StateType(2, qtype, [x0]),
        input_args=[],
        body=_get_test_body([], 2, qtype, 0, None),
        flows=ArrayAttr([]),
    )
    consumer = CircuitOp(
        producer.output,
        StateType(2, qtype, []),
        input_args=[],
        body=_get_test_body([], 2, qtype, 0, None),
        flows=ArrayAttr([]),
    )

    WriteFlows.remove_flow_states_from_output(producer, [x0], PatternRewriter(producer.yield_op))

    assert producer.flows is None
    assert consumer.flows is None


def test_write_flows_construct_new_flows_adds_simple_flow():
    """construct_new_flows_and_detectors creates a new FlowAttr when none exists."""
    x0 = qcore.PauliStringAttr([("X", 0)], 1)

    test_op = test.TestOp(result_types=[qcore.QubitType()])
    q0 = test_op.res[0]
    state_make = StateMakeOp([q0], StateType(1, qcore.QubitType(), [x0]))
    body = _get_test_body([], 1, qcore.QubitType(), 0, None)
    circuit = CircuitOp(
        state_make.output, StateType(1, qcore.QubitType(), [x0]), input_args=[], body=body, flows=[]
    )
    ModuleOp([test_op, state_make, circuit])
    additions, detectors = WriteFlows.construct_new_flows_and_detectors(
        flows=[CircuitFlowData(x0, x0, MMTResults())],
        circuit=circuit,
        rewriter=PatternRewriter(circuit),
    )

    assert detectors == []
    assert len(additions) == 1
    assert additions[0].is_plus
    assert additions[0].measurements.data == ()
    # We don't hard-code indices; just ensure they're not the identity index.
    assert additions[0].input_state.data != qcore.I_STATE_INDEX
    assert additions[0].output_state.data != qcore.I_STATE_INDEX


def test_write_flows_construct_new_flows_identity_to_identity_creates_detector_only():
    """I->I flows aren't written; differing measurement sets become detectors."""

    test_op = test.TestOp(result_types=[qcore.QubitType()])
    q0 = test_op.res[0]
    state_make = StateMakeOp(
        [q0], StateType(1, qcore.QubitType(), [qcore.PauliStringAttr([("X", 0)], 1)])
    )
    body = _get_test_body([], 1, qcore.QubitType(), 1, None)
    circuit = CircuitOp(
        state_make.output,
        StateType(1, qcore.QubitType(), [qcore.PauliStringAttr([("X", 0)], 1)]),
        input_args=[],
        body=body,
        flows=[],
    )
    ModuleOp([test_op, state_make, circuit])

    m1 = circuit.yield_op.measurements[0]

    additions, detectors = WriteFlows.construct_new_flows_and_detectors(
        flows=[
            CircuitFlowData(
                qcore.PauliStringAttr.identity(1),
                qcore.PauliStringAttr.identity(1),
                MMTResults([m1]),
            )
        ],
        circuit=circuit,
        rewriter=PatternRewriter(circuit),
    )

    assert additions == []
    assert len(detectors) == 1
    assert set(detectors[0].measurements) == {m1}


def test_write_flows_construct_new_flows_identity_to_identity_creates_detector_only_parallel():
    """Like above, but the measurement is inside a parallel region."""

    test_op = test.TestOp(result_types=[qcore.QubitType()])
    q0 = test_op.res[0]
    state_make = StateMakeOp(
        [q0], StateType(1, qcore.QubitType(), [qcore.PauliStringAttr([("X", 0)], 1)])
    )
    body = _get_test_body([], 1, qcore.QubitType(), 1, None, in_parallel=True)
    circuit = CircuitOp(
        state_make.output,
        StateType(1, qcore.QubitType(), [qcore.PauliStringAttr([("X", 0)], 1)]),
        input_args=[],
        body=body,
        flows=[],
    )
    ModuleOp([test_op, state_make, circuit])

    m1 = circuit.yield_op.measurements[0]
    parallel = next(op for op in circuit.body.block.ops if isinstance(op, qstruct.ParallelOp))
    meas_op = next(op for op in parallel.par_regions[0].block.ops if isinstance(op, test.TestOp))
    m1_par = meas_op.res[0]

    additions, detectors = WriteFlows.construct_new_flows_and_detectors(
        flows=[
            CircuitFlowData(
                qcore.PauliStringAttr.identity(1),
                qcore.PauliStringAttr.identity(1),
                MMTResults([m1_par]),
            )
        ],
        circuit=circuit,
        rewriter=PatternRewriter(circuit),
    )

    assert additions == []
    assert len(detectors) == 1
    assert set(detectors[0].measurements) == {m1}


def test_write_flows_construct_new_flows_existing_flow_measurement_diff_creates_detector():
    """If a flow already exists, a measurement symmetric-diff produces a detector."""
    x0 = qcore.PauliStringAttr([("X", 0)], 1)

    test_op = test.TestOp(result_types=[qcore.QubitType()])
    q0 = test_op.res[0]
    state_make = StateMakeOp([q0], StateType(1, qcore.QubitType(), [x0]))
    body = _get_test_body([], 1, qcore.QubitType(), 2, None)
    circuit = CircuitOp(
        state_make.output, StateType(1, qcore.QubitType(), [x0]), input_args=[], body=body, flows=[]
    )
    ModuleOp([test_op, state_make, circuit])

    # Use the two measurements yielded by the circuit body.
    m1 = circuit.yield_op.measurements[0]
    m2 = circuit.yield_op.measurements[1]
    circuit.flows = ArrayAttr(
        [
            FlowAttr(
                sign="+",
                measurements=[0],
                input_state=cast(int, circuit._find_input_flow_state(x0)),
                output_state=cast(int, circuit._find_output_flow_state(x0)),
            )
        ]
    )

    additions, detectors = WriteFlows.construct_new_flows_and_detectors(
        flows=[CircuitFlowData(x0, x0, MMTResults([m2]))],
        circuit=circuit,
        rewriter=PatternRewriter(circuit),
    )

    assert additions == []
    assert len(detectors) == 1
    # Detector should include both measurements (symmetric difference).
    assert set(detectors[0].measurements) == {m1, m2}


def test_write_flows_construct_new_flows_existing_flow_measurement_diff_creates_detector_parallel():
    """Like above, but measurement is inside a parallel op."""
    x0 = qcore.PauliStringAttr([("X", 0)], 1)

    test_op = test.TestOp(result_types=[qcore.QubitType()])
    q0 = test_op.res[0]
    state_make = StateMakeOp([q0], StateType(1, qcore.QubitType(), [x0]))
    body = _get_test_body([], 1, qcore.QubitType(), 2, None, in_parallel=True)
    circuit = CircuitOp(
        state_make.output, StateType(1, qcore.QubitType(), [x0]), input_args=[], body=body, flows=[]
    )
    ModuleOp([test_op, state_make, circuit])

    # Use the measurements yielded by the circuit body and also their aliases in the parallel.
    m2 = circuit.yield_op.measurements[1]
    parallel = next(op for op in circuit.body.block.ops if isinstance(op, qstruct.ParallelOp))
    meas_op = next(op for op in parallel.par_regions[0].block.ops if isinstance(op, test.TestOp))
    m1_par, m2_par = meas_op.res
    circuit.flows = ArrayAttr(
        [
            FlowAttr(
                sign="+",
                measurements=[0],
                input_state=cast(int, circuit._find_input_flow_state(x0)),
                output_state=cast(int, circuit._find_output_flow_state(x0)),
            )
        ]
    )

    additions, detectors = WriteFlows.construct_new_flows_and_detectors(
        flows=[CircuitFlowData(x0, x0, MMTResults([m1_par, m2_par]))],
        circuit=circuit,
        rewriter=PatternRewriter(circuit),
    )

    assert additions == []
    assert len(detectors) == 1
    # Detector should include just measurement 2 (symmetric difference).
    assert set(detectors[0].measurements) == {m2}


def test_write_flows_update_circuit_op_appends_flows_and_measurements():
    """update_circuit_op updates annotations and yield measurements."""
    x0 = qcore.PauliStringAttr([("X", 0)], 1)

    # Build a CircuitOp -> CircuitOp interface
    q0 = test.TestOp(result_types=[qcore.QubitType()]).res[0]
    state_make = StateMakeOp([q0], StateType(1, qcore.QubitType(), [x0]))

    producer_body = _get_test_body([], 1, qcore.QubitType(), 0, None)
    producer = CircuitOp(
        state_make.output,
        StateType(1, qcore.QubitType(), [x0]),
        input_args=[],
        body=producer_body,
        flows=[],
    )

    adapter_body = _get_test_body([], 1, qcore.QubitType(), 0, None)
    adapter = CircuitOp(
        producer.output,
        StateType(1, qcore.QubitType(), [x0]),
        input_args=[],
        body=adapter_body,
        flows=[],
    )

    circuit_body = _get_test_body([], 1, qcore.QubitType(), 1, None)
    circuit = CircuitOp(
        adapter.output,
        StateType(1, qcore.QubitType(), [x0]),
        input_args=[],
        body=circuit_body,
        flows=[],
    )

    m1 = circuit.yield_op.measurements[0]

    rewriter = PatternRewriter(circuit.yield_op)

    WriteFlows.update_circuit_op(
        flows=[CircuitFlowData(x0, x0, MMTResults([m1]))],
        circuit=circuit,
        rewriter=rewriter,
    )

    assert circuit.flows is not None
    assert len(cast(ArrayAttr[FlowAttr], circuit.flows).data) == 1
    flow = cast(ArrayAttr[FlowAttr], circuit.flows).data[0]
    assert flow.measurement_indices == [0]
