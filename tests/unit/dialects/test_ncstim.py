"""Tests for the ncstim extension dialect for stim."""

import pytest
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.utils.exceptions import VerifyException

from deltakit_compile.dialects.ncstim import (
    NonCliffordGateEnum,
    NonCliffordGateOp,
    RotationGateOp,
    U3GateOp,
)
from deltakit_compile.dialects.stim import PauliAttr, PauliOperatorEnum, QubitAllocOp, to_stim
from tests.unit.dialects.conftest import check_asm_roundtrip


@pytest.fixture
def qubit_allocs() -> list[QubitAllocOp]:
    """Fresh qubit allocations for a single test. These are built per test, rather than shared as
    module-level SSA values, so that usage recorded on them (e.g. `SSAValue.uses`) by one test's
    gate ops can never leak into another test."""
    return [QubitAllocOp(i) for i in range(3)]


@pytest.mark.parametrize(
    "program",
    [
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n ncstim.non_clifford T(%0)",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n ncstim.non_clifford T_DAG(%0)",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n "
        "%1 = stim.qubit_alloc 1 -> !stim.qubit\n "
        "%2 = stim.qubit_alloc 2 -> !stim.qubit\n ncstim.non_clifford CCZ(%0, %1, %2)",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n "
        "%1 = stim.qubit_alloc 1 -> !stim.qubit\n ncstim.non_clifford CH(%0, %1)",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n ncstim.rotation X<0.5> (%0)",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n ncstim.rotation Y<0.25> (%0)",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n ncstim.rotation Z<1.0> (%0)",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n "
        "%1 = stim.qubit_alloc 1 -> !stim.qubit\n ncstim.rotation XX<0.5> (%0, %1)",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n "
        "%1 = stim.qubit_alloc 1 -> !stim.qubit\n ncstim.rotation XY<0.75> (%0, %1)",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n ncstim.u3<0.5, -0.5, 0.5> (%0)",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n ncstim.u3<0.0, 0.0, 0.0> (%0)",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n "
        "%1 = stim.qubit_alloc 1 -> !stim.qubit\n ncstim.u3<0.5, -0.5, 0.5> (%0, %1)",
    ],
)
def test_asm_ncstim_roundtrip(program: str, xdsl_context: Context) -> None:
    """Test that ncstim operations can be parsed from and printed to MLIR assembly."""
    check_asm_roundtrip(program, xdsl_context)


@pytest.mark.parametrize(
    ("gate_type", "target_indices", "expected"),
    [
        (NonCliffordGateEnum.T, (0,), "T 0"),
        (NonCliffordGateEnum.T_DAG, (0,), "T_DAG 0"),
        (NonCliffordGateEnum.CH, (0, 1), "CH 0 1"),
    ],
)
def test_non_clifford_gate_op_print_stim(
    gate_type: NonCliffordGateEnum,
    target_indices: tuple[int, ...],
    expected: str,
    qubit_allocs: list[QubitAllocOp],
) -> None:
    """Test that NonCliffordGateOp prints as the expected tsim/clifft instruction."""
    used_allocs = [qubit_allocs[i] for i in sorted(set(target_indices))]
    targets = [qubit_allocs[i].results[0] for i in target_indices]
    gate = NonCliffordGateOp(gate_type, targets)
    module_op = ModuleOp([*used_allocs, gate])
    assert to_stim(module_op) == "\n" + expected


@pytest.mark.parametrize(
    ("pauli_modifiers", "angle", "target_indices", "expected"),
    [
        # Case 1: matches a plain axis rotation - takes priority even at a "special" angle.
        ([PauliAttr(PauliOperatorEnum.X)], 0.5, (0,), "R_X(0.5) 0"),
        ([PauliAttr(PauliOperatorEnum.Y)], 0.25, (0,), "R_Y(0.25) 0"),
        ([PauliAttr(PauliOperatorEnum.Z)], 0.5, (0,), "R_Z(0.5) 0"),
        (
            [PauliAttr(PauliOperatorEnum.X), PauliAttr(PauliOperatorEnum.X)],
            0.5,
            (0, 1),
            "R_XX(0.5) 0 1",
        ),
        # Case 2: not an axis rotation, but the angle is one of the four special values.
        (
            [PauliAttr(PauliOperatorEnum.X), PauliAttr(PauliOperatorEnum.Y)],
            0.5,
            (0, 1),
            "SPP X0*Y1",
        ),
        (
            [PauliAttr(PauliOperatorEnum.X), PauliAttr(PauliOperatorEnum.Y)],
            -0.5,
            (0, 1),
            "SPP_DAG X0*Y1",
        ),
        (
            [PauliAttr(PauliOperatorEnum.X), PauliAttr(PauliOperatorEnum.Y)],
            0.25,
            (0, 1),
            "TPP X0*Y1",
        ),
        (
            [PauliAttr(PauliOperatorEnum.X), PauliAttr(PauliOperatorEnum.Y)],
            -0.25,
            (0, 1),
            "TPP_DAG X0*Y1",
        ),
        (
            [
                PauliAttr(PauliOperatorEnum.X),
                PauliAttr(PauliOperatorEnum.Y),
                PauliAttr(PauliOperatorEnum.Z),
            ],
            0.25,
            (0, 1, 2),
            "TPP X0*Y1*Z2",
        ),
        # Case 3: neither - generic R_PAULI fallback.
        (
            [PauliAttr(PauliOperatorEnum.X), PauliAttr(PauliOperatorEnum.Y)],
            0.75,
            (0, 1),
            "R_PAULI(0.75) X0*Y1",
        ),
    ],
)
def test_rotation_gate_op_print_stim(
    pauli_modifiers: list[PauliAttr],
    angle: float,
    target_indices: tuple[int, ...],
    expected: str,
    qubit_allocs: list[QubitAllocOp],
) -> None:
    """Test that RotationGateOp prints as the expected tsim/clifft instruction, respecting the
    documented precedence between the axis-rotation, special-angle, and generic R_PAULI forms."""
    used_allocs = [qubit_allocs[i] for i in sorted(set(target_indices))]
    targets = [qubit_allocs[i].results[0] for i in target_indices]
    rot = RotationGateOp(pauli_modifiers, angle, targets)
    module_op = ModuleOp([*used_allocs, rot])
    assert to_stim(module_op) == "\n" + expected


@pytest.mark.parametrize(
    ("target_indices", "expected"),
    [
        ((0,), "U3(0.5, -0.5, 0.5) 0"),
        ((0, 1), "U3(0.5, -0.5, 0.5) 0 1"),
    ],
)
def test_u3_gate_op_print_stim(
    target_indices: tuple[int, ...], expected: str, qubit_allocs: list[QubitAllocOp]
) -> None:
    """Test that U3GateOp prints as the expected tsim U3 instruction, including the broadcast
    case where the same gate is applied independently to multiple target qubits."""
    used_allocs = [qubit_allocs[i] for i in sorted(set(target_indices))]
    targets = [qubit_allocs[i].results[0] for i in target_indices]
    u3 = U3GateOp(0.5, -0.5, 0.5, targets)
    module_op = ModuleOp([*used_allocs, u3])
    assert to_stim(module_op) == "\n" + expected


def test_non_clifford_gate_op_verification() -> None:
    """Test that NonCliffordGateOp inherits GateOp's non-zero-qubit-target constraint."""
    with pytest.raises(VerifyException, match="expected integer >= 1, got 0"):
        NonCliffordGateOp(NonCliffordGateEnum.T, []).verify()


def test_non_clifford_gate_op_rejects_duplicate_targets(
    qubit_allocs: list[QubitAllocOp],
) -> None:
    """Test that NonCliffordGateOp rejects targeting the same qubit more than once, mirroring
    tsim/clifft's own rejection of e.g. `CH 3 3` at parse time."""
    qubit = qubit_allocs[0].results[0]
    with pytest.raises(VerifyException, match="targets the same qubit more than once"):
        NonCliffordGateOp(NonCliffordGateEnum.CH, [qubit, qubit]).verify()


def test_rotation_gate_op_verification() -> None:
    """Test that RotationGateOp inherits GateOp's non-zero-qubit-target constraint."""
    with pytest.raises(VerifyException, match="expected integer >= 1, got 0"):
        RotationGateOp([PauliAttr(PauliOperatorEnum.X)], 0.5, []).verify()


def test_rotation_gate_op_rejects_duplicate_targets(qubit_allocs: list[QubitAllocOp]) -> None:
    """Test that RotationGateOp rejects targeting the same qubit more than once, mirroring
    tsim/clifft's own rejection of e.g. `R_XX(0.5) 3 3` at parse time."""
    qubit = qubit_allocs[0].results[0]
    with pytest.raises(VerifyException, match="targets the same qubit more than once"):
        RotationGateOp(
            [PauliAttr(PauliOperatorEnum.X), PauliAttr(PauliOperatorEnum.X)],
            0.5,
            [qubit, qubit],
        ).verify()


def test_rotation_gate_op_pauli_modifiers_length_mismatch(
    qubit_allocs: list[QubitAllocOp],
) -> None:
    """Test that RotationGateOp requires exactly one pauli modifier per targeted qubit."""
    qubit = qubit_allocs[0].results[0]
    with pytest.raises(
        VerifyException,
        match="A rotation gate must have the same number of pauli modifiers as targeted qubits",
    ):
        RotationGateOp([PauliAttr(PauliOperatorEnum.X)], 0.5, [qubit, qubit]).verify()


def test_u3_gate_op_verification() -> None:
    """Test that U3GateOp inherits GateOp's non-zero-qubit-target constraint."""
    with pytest.raises(VerifyException, match="expected integer >= 1, got 0"):
        U3GateOp(0.5, -0.5, 0.5, []).verify()
