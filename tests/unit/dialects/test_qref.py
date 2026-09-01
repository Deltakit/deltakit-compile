import re
from collections.abc import Callable, Sequence
from typing import Literal

import numpy as np
import pytest
from xdsl.context import Context
from xdsl.dialects import test as t
from xdsl.dialects.builtin import ArrayAttr, Float16Type, Float64Type, FloatAttr, i1
from xdsl.ir import Attribute, VerifyException

from deltakit_compile.dialects import qcore, qref
from tests.unit.dialects.conftest import check_ir_roundtrip


@pytest.mark.parametrize(
    ("basis", "operands", "exp_error", "exp_is_broadcast"),
    [
        ("X", [qcore.QubitType()], None, False),
        ("X", [qcore.QubitType()] * 5, None, True),
        (qcore.PauliAttr.X(), [qcore.QubitType()] * 4, None, True),
        ("Y", [qcore.QubitType()] * 2, None, True),
        (qcore.PauliAttr.Z(), [qcore.QubitType()] * 500, None, True),
        (
            "X",
            [qcore.QubitType()] * 0,
            re.escape(
                "operand 'qubits' expected at position 0 does not verify:\n"
                "incorrect length for range variable:\n"
                "expected integer >= 1, got 0"
            ),
            None,
        ),
        (
            "X",
            [qcore.QubitRegType(2)] * 1,
            re.escape(
                "operand 'qubits' at position 0 does not verify:\n"
                "!qcore.qubit_reg<2> should be of base attribute qcore.qubit"
            ),
            None,
        ),
    ],
)
def test_reset(
    basis: qcore.Pauli,
    operands: Sequence[Attribute],
    exp_error: str | None,
    exp_is_broadcast: bool | None,
    xdsl_context: Context,
):
    """Test that reset op verifies types and inits arguments correctly."""

    test_op = t.TestOp(result_types=operands)
    reset_op = qref.ResetOp.create(
        operands=list(test_op.res), properties={"basis": qcore.PauliAttr.coerce(basis)}
    )
    reset_op2 = qref.ResetOp(basis, test_op.res)
    assert reset_op.is_structurally_equivalent(reset_op2)
    assert reset_op.basis == qcore.PauliAttr.coerce(basis)
    if exp_is_broadcast is not None:
        assert reset_op.is_broadcast() == exp_is_broadcast
        if not exp_is_broadcast:
            assert list(reset_op.qubit_operand_group) == list(test_op.res)

    assert list(map(list, reset_op.qubit_operand_groups)) == [[qubit] for qubit in test_op.res]

    if exp_error is None:
        reset_op.verify()
        check_ir_roundtrip([test_op, reset_op], xdsl_context)
    else:
        with pytest.raises(VerifyException, match=exp_error):
            reset_op.verify()


def test_reset_broadcast_error():
    """Test the errors given when using properties specific to non-broadcast ops on a broadcast
    reset op."""
    test_op = t.TestOp(result_types=[qcore.QubitType()] * 4)
    reset_op = qref.ResetOp("X", test_op.res)
    with pytest.raises(
        ValueError,
        match=re.escape(
            "The 'qubit_operand_group' property is not available for broadcast operations."
        ),
    ):
        _ = reset_op.qubit_operand_group


@pytest.mark.parametrize(
    ("paulis", "operands", "noise", "return_types", "exp_error"),
    [
        ([["X"]] * 10, [qcore.QubitType()] * 10, 0.1, [i1] * 10, None),
        ([["X", "X"]], [qcore.QubitType()] * 2, 0.0, [i1], None),
        ([["X", "Y"]] * 2, [qcore.QubitType()] * 4, 0.25, [i1] * 2, None),
        ([["X", "Y"], ["Z", "Y"]], [qcore.QubitType()] * 4, 0.25, [i1] * 2, None),
        (
            [["X", "Y"], [], ["Z", "Y"]],
            [qcore.QubitType()] * 4,
            0.25,
            [i1] * 3,
            re.escape("Pauli strings must have at least one Pauli."),
        ),
        (
            [["Z", "Y", "Z"]] * 3,
            [qcore.QubitType()] * 10,
            0.25,
            [i1] * 3,
            re.escape(
                "Incorrect sum over range that produced values "
                "'[#qcore.pauli<Z>, #qcore.pauli<Y>, #qcore.pauli<Z>]' (3) "
                "+ '[#qcore.pauli<Z>, #qcore.pauli<Y>, #qcore.pauli<Z>]' (3) "
                "+ '[#qcore.pauli<Z>, #qcore.pauli<Y>, #qcore.pauli<Z>]' (3) = 9:\n"
                "The number of qubit operands must equal the total number of Paulis across each "
                "Pauli string.\n"
                "Underlying verification failure: "
                "integer 10 expected from int variable 'Qubits', but got 9"
            ),
        ),
        (
            ["XXX"],
            [qcore.QubitType()] * 2,
            0.25,
            [i1],
            re.escape(
                "Incorrect sum over range that produced values "
                "'[#qcore.pauli<X>, #qcore.pauli<X>, #qcore.pauli<X>]' (3) = 3:\n"
                "The number of qubit operands must equal the total number of Paulis across each "
                "Pauli string.\n"
                "Underlying verification failure: "
                "integer 2 expected from int variable 'Qubits', but got 3"
            ),
        ),
        (
            ["XXX"],
            [qcore.QubitType()] * 3,
            0.25,
            [i1] * 2,
            re.escape(
                "incorrect length for range variable:\n"
                "The number of measurement results must equal the number of Pauli strings.\n"
                "Underlying verification failure: "
                "integer 2 expected from int variable 'Results', but got 1"
            ),
        ),
        (
            ["XXX"],
            [qcore.QubitType()] * 3,
            FloatAttr(0.1, Float16Type()),
            [i1],
            re.escape("f16 should be of base attribute f64"),
        ),
    ],
)
def test_measure_verifies(
    paulis: list[Sequence[Literal["X", "Y", "Z"]]],
    operands: Sequence[Attribute],
    noise: FloatAttr[Float64Type] | float,
    return_types: list[Attribute],
    exp_error: str | None,
    xdsl_context: Context,
):
    """Test that measure op verifies the number of qubits for the paulis, and results"""
    paulis_attr = ArrayAttr([ArrayAttr([qcore.PauliAttr.coerce(p) for p in ps]) for ps in paulis])
    if isinstance(noise, float):
        noise = FloatAttr(noise, Float64Type())
    test_op = t.TestOp(result_types=operands)
    meas_op = qref.MeasureOp.create(
        operands=test_op.res,
        properties={"paulis": paulis_attr, "noise": noise},
        result_types=return_types,
    )
    if exp_error is None:
        meas_op.verify()
        check_ir_roundtrip([test_op, meas_op], xdsl_context)
    else:
        with pytest.raises(VerifyException, match=exp_error):
            meas_op.verify()


@pytest.mark.parametrize(
    ("paulis_arg", "qubit_types", "noise_arg", "exp_error", "exp_str", "exp_is_broadcast"),
    [
        ("X", [qcore.QubitType()], None, None, "<X>", False),
        ("X", [qcore.QubitType()] * 4, None, None, "<X>", True),
        ("X", [qcore.QubitType()] * 4, None, None, "i1, i1, i1, i1", True),
        ("X", [qcore.QubitType()] * 4, 0.1, None, "<X, 0.1>", True),
        ("X", [qcore.QubitType()] * 4, 0.0, None, "<X>", True),
        ("X", [qcore.QubitType()] * 4, 0, None, "<X>", True),
        (
            "x",
            [qcore.QubitType()] * 4,
            0,
            re.escape(
                "Cannot convert 'x' into a Pauli string. Expected only 'X's, 'Y's, and 'Z's."
            ),
            None,
            None,
        ),
        (
            "XXy",
            [qcore.QubitType()] * 4,
            0,
            re.escape(
                "Cannot convert 'XXy' into a Pauli string. Expected only 'X's, 'Y's, and 'Z's."
            ),
            None,
            None,
        ),
        (
            "XXX",
            [qcore.QubitType()] * 4,
            0,
            None,
            re.escape("%0 = qref.measure<XXX> (%1, %2, %3, %4) -> i1"),
            None,
        ),
        (
            "",
            [qcore.QubitType()],
            0,
            "Cannot convert an empty sequence into qref.measure Pauli string.",
            None,
            None,
        ),
        (
            qcore.PauliAttr.Y(),
            [qcore.QubitType()],
            0.0003,
            None,
            "<Y, 0.0003>",
            False,
        ),
        (
            [qcore.PauliAttr.Y()],
            [qcore.QubitType()] * 56,
            0.00000003,
            None,
            "<Y, 3.0e-08>",
            True,
        ),
        (
            [qcore.PauliAttr.Y()] * 2,
            [qcore.QubitType()] * 2,
            0.00000003,
            None,
            "<YY, 3.0e-08>",
            False,
        ),
    ],
)
def test_measure_init(
    paulis_arg: ArrayAttr[ArrayAttr[qcore.PauliAttr]]
    | qcore.Pauli
    | Sequence[qcore.PauliAttr]
    | str,
    qubit_types: Sequence[Attribute],
    noise_arg: FloatAttr[Float64Type] | float | None,
    exp_error: str | None,
    exp_str: str | None,
    exp_is_broadcast: bool | None,
    xdsl_context: Context,
):
    test_op = t.TestOp(result_types=qubit_types)
    kw_args = {"noise": noise_arg} if noise_arg is not None else {}
    if exp_error is None:
        op = qref.MeasureOp(paulis_arg, test_op.res, **kw_args)
        if exp_str is not None:
            assert re.search(exp_str, str(op)) is not None

        verifies = False
        try:
            op.verify()
            verifies = True
        except VerifyException:
            pass
        if verifies:
            parts = list(op.get_operand_segments())
            assert len(parts) == len(op.measurements)
            assert [qubit for qubits in parts for qubit in qubits] == list(op.qubits)
            assert list(map(list, op.qubit_operand_groups)) == list(map(list, parts))
            if exp_is_broadcast is not None:
                assert op.is_broadcast() == exp_is_broadcast
                if not exp_is_broadcast:
                    assert list(op.qubit_operand_group) == list(test_op.res)
                    assert list(op.pauli) == list(next(iter(op.paulis)))
                    assert op.measurement == op.results[0]
            check_ir_roundtrip([test_op, op], xdsl_context)
    else:
        with pytest.raises(ValueError, match=exp_error):
            qref.MeasureOp(paulis_arg, test_op.res, **kw_args)


def test_measure_broadcast_error():
    """Test the errors given when using properties specific to non-broadcast ops on a broadcast
    measure op."""
    test_op = t.TestOp(result_types=[qcore.QubitType()] * 4)
    measure_op = qref.MeasureOp("X", test_op.res)

    with pytest.raises(
        ValueError,
        match=re.escape(
            "The 'qubit_operand_group' property is not available for broadcast operations."
        ),
    ):
        _ = measure_op.qubit_operand_group

    with pytest.raises(
        ValueError,
        match=re.escape("The 'pauli' property is not available for broadcast operations."),
    ):
        _ = measure_op.pauli

    with pytest.raises(
        ValueError,
        match=re.escape("The 'measurement' property is not available for broadcast operations."),
    ):
        _ = measure_op.measurement


@pytest.mark.parametrize(
    ("gate_func", "operands", "exp_error", "exp_is_broadcast"),
    [
        (qcore.XGateAttr, [qcore.QubitType()], None, False),
        (qcore.SWAPGateAttr, [qcore.QubitType()] * 2, None, False),
        (qcore.XGateAttr, [qcore.QubitType()] * 5, None, True),
        (
            qcore.XGateAttr,
            [qcore.QubitType()] * 0,
            re.escape(
                "operand 'qubits' expected at position 0 does not verify:\n"
                "incorrect length for range variable:\n"
                "expected integer >= 1, got 0"
            ),
            None,
        ),
        (qcore.SWAPGateAttr, [qcore.QubitType()] * 6, None, True),
        (
            qcore.SWAPGateAttr,
            [qcore.QubitType()] * 5,
            re.escape(
                "The number of qubit operands must be a multiple of the number that the given "
                "gate operates on."
            ),
            None,
        ),
        (
            lambda: qcore.UnitaryGateAttr.from_ndarray(np.identity(2**7)),
            [qcore.QubitType()] * 6,
            re.escape(
                "The number of qubit operands must be a multiple of the number that the given "
                "gate operates on."
            ),
            None,
        ),
        (
            lambda: qcore.UnitaryGateAttr.from_ndarray(np.identity(2**7)),
            [qcore.QubitType()] * 24,
            re.escape(
                "The number of qubit operands must be a multiple of the number that the given "
                "gate operates on."
            ),
            None,
        ),
        (
            lambda: qcore.UnitaryGateAttr.from_ndarray(np.identity(2**7)),
            [qcore.QubitType()] * 28,
            None,
            True,
        ),
        (
            qcore.SWAPGateAttr,
            [qcore.QubitType()] * 59,
            re.escape(
                "The number of qubit operands must be a multiple of the number that the given "
                "gate operates on."
            ),
            None,
        ),
    ],
)
def test_gate(
    gate_func: Callable[[], qcore.GateAttribute],
    operands: Sequence[Attribute],
    exp_error: str | None,
    exp_is_broadcast: bool | None,
    xdsl_context: Context,
):
    """Test that gate op verifies the number of qubits for the gate"""

    test_op = t.TestOp(result_types=operands)
    gate = gate_func()
    gate_op = qref.GateOp.create(operands=list(test_op.res), properties={"gate": gate})
    gate_op2 = qref.GateOp(gate, test_op.res)
    assert gate_op.is_structurally_equivalent(gate_op2)
    assert gate_op.gate == gate

    if exp_error is None:
        gate_op.verify()
        parts = list(gate_op.get_operand_segments())
        assert all(len(part) == gate.get_qubit_count() for part in parts)
        assert [qubit for qubits in parts for qubit in qubits] == list(gate_op.qubits)
        assert list(map(list, gate_op.qubit_operand_groups)) == list(map(list, parts))
        if exp_is_broadcast is not None:
            assert gate_op.is_broadcast() == exp_is_broadcast
            if not exp_is_broadcast:
                assert list(gate_op.qubit_operand_group) == list(test_op.res)
        check_ir_roundtrip([test_op, gate_op], xdsl_context)
    else:
        with pytest.raises(VerifyException, match=exp_error):
            gate_op.verify()


def test_gate_broadcast_error():
    """Test the errors given when using properties specific to non-broadcast ops on a broadcast gate
    op."""
    test_op = t.TestOp(result_types=[qcore.QubitType()] * 4)
    gate_op = qref.GateOp(qcore.XGateAttr(), test_op.res)

    with pytest.raises(
        ValueError,
        match=re.escape(
            "The 'qubit_operand_group' property is not available for broadcast operations."
        ),
    ):
        _ = gate_op.qubit_operand_group


@pytest.mark.parametrize(
    ("noise", "operands", "exp_error"),
    [
        (qcore.PauliNoiseParametersAttr.depolarise(5, 0.3), [qcore.QubitType()] * 5, None),
        (
            qcore.PauliNoiseParametersAttr.uniform(1),
            [qcore.QubitType()] * 0,
            re.escape(
                "operand 'qubits' expected at position 0 does not verify:\n"
                "incorrect length for range variable:\n"
                "expected integer >= 1, got 0"
            ),
        ),
        (qcore.PauliNoiseParametersAttr.uniform(2), [qcore.QubitType()] * 6, None),
        (
            qcore.PauliNoiseParametersAttr.uniform(2),
            [qcore.QubitType()] * 5,
            re.escape(
                "Tried to verify 5 % 2 = 1. "
                "The number of qubit operands must be a multiple of the number that the given "
                "qcore.pauli_noise_parameters Attribute operates on.\n"
                "Underlying verification failure: Invalid value 1, expected 0"
            ),
        ),
        (
            qcore.PauliNoiseParametersAttr.depolarise(7, 0.0),
            [qcore.QubitType()] * 6,
            re.escape(
                "Tried to verify 6 % 7 = 6. "
                "The number of qubit operands must be a multiple of the number that the given "
                "qcore.pauli_noise_parameters Attribute operates on.\n"
                "Underlying verification failure: Invalid value 6, expected 0"
            ),
        ),
        (
            qcore.PauliNoiseParametersAttr.depolarise(7, 0.0),
            [qcore.QubitType()] * 24,
            re.escape(
                "Tried to verify 24 % 7 = 3. "
                "The number of qubit operands must be a multiple of the number that the given "
                "qcore.pauli_noise_parameters Attribute operates on.\n"
                "Underlying verification failure: Invalid value 3, expected 0"
            ),
        ),
        (
            qcore.PauliNoiseParametersAttr.depolarise(7, 0.0),
            [qcore.QubitType()] * 28,
            None,
        ),
        (
            qcore.PauliNoiseParametersAttr.depolarise(2, 0.0),
            [qcore.QubitType()] * 59,
            re.escape(
                "Tried to verify 59 % 2 = 1. "
                "The number of qubit operands must be a multiple of the number that the given "
                "qcore.pauli_noise_parameters Attribute operates on.\n"
                "Underlying verification failure: Invalid value 1, expected 0"
            ),
        ),
    ],
)
def test_pauli_noise(
    noise: qcore.PauliNoiseParametersAttr,
    operands: Sequence[Attribute],
    exp_error: str | None,
    xdsl_context: Context,
):
    """Test that gate op verifies the number of qubits for the gate"""

    test_op = t.TestOp(result_types=operands)
    noise_op = qref.PauliNoiseOp.create(
        operands=list(test_op.res), properties={"probabilities": noise}
    )
    noise_op2 = qref.PauliNoiseOp(noise, test_op.res)
    assert noise_op.is_structurally_equivalent(noise_op2)
    assert noise_op.probabilities == noise

    if exp_error is None:
        noise_op.verify()
        check_ir_roundtrip([test_op, noise_op], xdsl_context)
    else:
        with pytest.raises(VerifyException, match=exp_error):
            noise_op.verify()
