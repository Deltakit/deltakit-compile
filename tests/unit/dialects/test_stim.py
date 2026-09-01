"""Tests for the Stim xDSL dialect"""

import pytest
import xdsl.dialects.test as t
from xdsl.context import Context
from xdsl.dialects.builtin import ArrayAttr, FloatData, IntAttr, ModuleOp, StringAttr
from xdsl.ir import Block, Operation
from xdsl.parser import Parser
from xdsl.utils.exceptions import ParseError, VerifyException

from deltakit_compile.dialects.stim import (
    CliffordGateOp,
    CorrelatedErrorOp,
    Depolarize1Op,
    Depolarize2Op,
    ElseCorrelatedErrorOp,
    MeasurementGateOp,
    MultiPauliProductMeasurementOp,
    ObservableIdAttr,
    PauliAttr,
    PauliChannel1Op,
    PauliChannel2Op,
    PauliOperatorEnum,
    QubitAllocOp,
    QubitMappingAttr,
    QubitType,
    RepeatOp,
    YieldOp,
    to_stim,
)
from deltakit_compile.shared.deltakit_stim.gates import TwoQubitUnitaryEnum
from tests.unit.dialects.conftest import check_asm_roundtrip, check_stim_roundtrip

qubit = QubitAllocOp(0).results[0]
ro = MeasurementGateOp([qubit]).results[0]


class TestObservableIdAttr:
    def test_get_returns_none_when_unset(self):
        op = t.TestOp()
        assert ObservableIdAttr.get(op) is None

    def test_set_and_get_int(self):
        op = t.TestOp()
        ObservableIdAttr.set(op, 5)
        assert ObservableIdAttr.get(op) == 5
        assert isinstance(op.attributes["stim.obs_id"], IntAttr)

    def test_set_accepts_int_attr(self):
        op = t.TestOp()
        ObservableIdAttr.set(op, IntAttr(7))
        assert ObservableIdAttr.get(op) == 7

    def test_get_raises_on_wrong_type(self):
        """Test get raises TypeError when the attribute has an unexpected type."""
        op = t.TestOp()
        op.attributes["stim.obs_id"] = StringAttr("not_an_int")
        with pytest.raises(TypeError, match=r"Expected 'stim.obs_id' to be an IntAttr"):
            ObservableIdAttr.get(op)


@pytest.mark.parametrize(
    "program",
    [
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n "
        "%1 = stim.qubit_alloc 1 -> !stim.qubit\n stim.reset X (%0, %1)",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n %1 = stim.measure Y <0.01> (%0) -> i1",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n "
        "%1 = stim.qubit_alloc 1 -> !stim.qubit\n "
        "%2, %3 = stim.measure Z (%0, %1) -> i1, i1",
    ],
)
def test_asm_stabiliser_roundtrip(program: str, xdsl_context: Context):
    """Test that stabiliser operations can be parsed and printed to/from MLIR assembly."""
    check_asm_roundtrip(program, xdsl_context)


@pytest.mark.parametrize(
    "program",
    [
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n stim.clifford SQRT_X (%0)",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n "
        "%1 = stim.qubit_alloc 1 -> !stim.qubit\n stim.clifford CZ (%0, %1)",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n "
        "%1 = stim.qubit_alloc 1 -> !stim.qubit\n stim.clifford ISWAP_DAG (%0, %1)",
    ],
)
def test_asm_gate_roundtrip(program: str, xdsl_context: Context):
    """Test that gate operations can be parsed and printed to/from MLIR assembly."""
    check_asm_roundtrip(program, xdsl_context)


@pytest.mark.parametrize(
    "program",
    [
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n "
        "%1 = stim.qubit_alloc 1 -> !stim.qubit\n "
        "%2 = stim.mpp[X, Z] (%0, %1) -> i1",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n "
        "%1 = stim.qubit_alloc 1 -> !stim.qubit\n "
        "%2 = stim.mpp[Y] <0.01> (%0) -> i1",
    ],
)
def test_asm_mpp_roundtrip(program: str, xdsl_context: Context):
    """Test that MPP operation can be parsed and printed to/from MLIR assembly."""
    check_asm_roundtrip(program, xdsl_context)


@pytest.mark.parametrize(
    "program",
    [
        "stim.tick",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n "
        "stim.assign_qubit_coord <4.0, 2.0> (%0 : !stim.qubit)",
        "stim.shift_coord <[0.0, 1.0, 2.0]>",
        "%0 = arith.constant false\n stim.detector (%0 : i1)",
        "%0 = arith.constant false\n stim.detector <[1.0, 0.0, 0.0]> (%0 : i1)",
        "%0 = arith.constant true\n stim.observable_include <0> (%0 : i1)",
    ],
)
def test_asm_annotation_roundtrip(program: str, xdsl_context: Context):
    """Test that annotation operations can be parsed and printed to/from MLIR assembly."""
    check_asm_roundtrip(program, xdsl_context)


@pytest.mark.parametrize(
    "program",
    [
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n stim.depolarize1 <0.01> (%0)",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n stim.depolarize2 <0.01> (%0, %0)",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n stim.pauli_channel_1 <0.01, 0.02, 0.03> (%0)",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n "
        "stim.pauli_channel_2 <0.01, 0.02, 0.03, 0.04, 0.05, 0.01, 0.02, 0.03, 0.04, 0.05, "
        "0.01, 0.02, 0.03, 0.04, 0.05> (%0, %0)",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n "
        "stim.correlated_error <0.01> [X, Y, Z] (%0, %0, %0)",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n "
        "stim.correlated_error <0.01> [X, Y, Z] (%0, %0, %0)\n "
        "stim.else_correlated_error <0.02> [Z, X, X] (%0, %0, %0)",
    ],
)
def test_asm_noise_roundtrip(program: str, xdsl_context: Context):
    """Test that noise operations can be parsed and printed to/from MLIR assembly."""
    check_asm_roundtrip(program, xdsl_context)


def test_asm_repeat_roundtrip(xdsl_context: Context):
    """Test that repeat operations can be parsed and printed to/from MLIR assembly."""
    check_asm_roundtrip(
        "%0 = stim.empty -> i1\n %1 = stim.repeat 26 (%0 : i1) -> i1 {\n"
        "^body(%2: i1):\n  stim.yield %2 : i1\n}",
        xdsl_context,
    )


def _tag_tests(
    tests: list[tuple[str, str | None]] | list[tuple[str, None]], tag: str | None
) -> list[tuple[str, str | None]]:
    if tag:
        tag = "[" + tag + "]"
    return [
        (
            in_str.format(tag=tag or ""),
            out_str.format(tag=tag or "") if out_str is not None else None,
        )
        for in_str, out_str in tests
    ]


stim_stabiliser_roundtrip_tests = [
    ("R{tag} 0 1", None),
    ("RX{tag} 0 1", None),
    ("RY{tag} 0 1", None),
    ("RZ{tag} 0 1", "R{tag} 0 1"),
    ("M{tag} 0 1", None),
    ("MX{tag} 0 1", None),
    ("MY{tag}(0.01) 0 1", None),
    ("MZ{tag} 0 1", "M{tag} 0 1"),
    ("MR{tag} 0 1", "M{tag} 0 1\nR{tag} 0 1"),
    ("MRX{tag}(0.001) 0 1", "MX{tag}(0.001) 0 1\nRX{tag} 0 1"),
    ("MRY{tag} 0 1", "MY{tag} 0 1\nRY{tag} 0 1"),
    ("MRZ{tag} 0 1", "M{tag} 0 1\nR{tag} 0 1"),
]


@pytest.mark.parametrize(
    ("stim_str", "exp_stim_str"),
    [
        *_tag_tests(stim_stabiliser_roundtrip_tests, tag=None),
        *_tag_tests(stim_stabiliser_roundtrip_tests, tag="my_tag"),
    ],
)
def test_stim_stabiliser_roundtrip(stim_str: str, exp_stim_str: str | None):
    """Test that stabiliser operations can be parsed and printed to/from Stim."""
    check_stim_roundtrip(stim_str, exp_stim_str)


stim_1q_gate_roundtrip_tests = [
    ("I{tag} 0 1", None),
    ("X{tag} 0 1", None),
    ("Y{tag} 0 1", None),
    ("Z{tag} 0 1", None),
    ("H{tag} 0 1", None),
    ("H_XZ{tag} 0 1", "H{tag} 0 1"),
    ("H_XY{tag} 0 1", None),
    ("H_YZ{tag} 0 1", None),
    ("SQRT_X{tag} 0 1", None),
    ("SQRT_Y{tag} 0 1", None),
    ("SQRT_Z{tag} 0 1", "S{tag} 0 1"),
    ("SQRT_X_DAG{tag} 0 1", None),
    ("SQRT_Y_DAG{tag} 0 1", None),
    ("SQRT_Z_DAG{tag} 0 1", "S_DAG{tag} 0 1"),
    ("S{tag} 0 1", None),
    ("S_DAG{tag} 0 1", None),
]


@pytest.mark.parametrize(
    ("stim_str", "exp_stim_str"),
    [
        *_tag_tests(stim_1q_gate_roundtrip_tests, tag=None),
        *_tag_tests(stim_1q_gate_roundtrip_tests, tag="my_tag"),
    ],
)
def test_stim_1q_gate_roundtrip(stim_str: str, exp_stim_str: str | None):
    """Test that one qubit gate operations can be parsed and printed to/from Stim."""
    check_stim_roundtrip(stim_str, exp_stim_str)


stim_mpp_roundtrip_tests = [
    ("MPP{tag} X0*Z1", None),
    ("MPP{tag}(0.01) Y2", None),
    ("MPP{tag} X0*Y1*Z2", None),
    ("MPP{tag}(0.25) X1", None),
    ("MPP{tag} Z5", None),
    ("MPP{tag} !X0*Y1*Z2", "MPP{tag} X0*Y1*Z2"),
    ("MPP{tag} !X0*Y1*Z2*X1", "MPP{tag} X0*Y1*Z2*X1"),
    ("MPP{tag} X0*Y1 Z2*X1", "MPP{tag} X0*Y1" + "\n" + "MPP{tag} Z2*X1"),
    (
        "MPP{tag} X0*Y1 Z2*X1*Z3 Z0",
        "MPP{tag} X0*Y1" + "\n" + "MPP{tag} Z2*X1*Z3" + "\n" + "MPP{tag} Z0",
    ),
]


@pytest.mark.parametrize(
    ("stim_str", "exp_stim_str"),
    [
        *_tag_tests(stim_mpp_roundtrip_tests, tag=None),
        *_tag_tests(stim_mpp_roundtrip_tests, tag="my_tag"),
    ],
)
def test_stim_mpp_roundtrip(stim_str: str, exp_stim_str: str | None):
    """Test that MPP operations can be parsed and printed to/from Stim."""
    check_stim_roundtrip(stim_str, exp_stim_str)


stim_2q_gate_roundtrip = [
    ("CX{tag} 0 1 2 3", None),
    ("ZCX{tag} 0 1 2 3", "CX{tag} 0 1 2 3"),
    ("CNOT{tag} 0 1 2 3", "CX{tag} 0 1 2 3"),
    ("CY{tag} 0 1 2 3", None),
    ("ZCY{tag} 0 1 2 3", "CY{tag} 0 1 2 3"),
    ("CZ{tag} 0 1 2 3", None),
    ("ZCZ{tag} 0 1 2 3", "CZ{tag} 0 1 2 3"),
    ("XCX{tag} 0 1 2 3", None),
    ("XCY{tag} 0 1 2 3", None),
    ("XCZ{tag} 0 1 2 3", None),
    ("YCX{tag} 0 1 2 3", None),
    ("YCY{tag} 0 1 2 3", None),
    ("YCZ{tag} 0 1 2 3", None),
    ("SQRT_XX{tag} 0 1 2 3", None),
    ("SQRT_YY{tag} 0 1 2 3", None),
    ("SQRT_ZZ{tag} 0 1 2 3", None),
    ("SQRT_XX_DAG{tag} 0 1 2 3", None),
    ("SQRT_YY_DAG{tag} 0 1 2 3", None),
    ("SQRT_ZZ_DAG{tag} 0 1 2 3", None),
    ("ISWAP{tag} 0 1 2 3", None),
    ("ISWAP_DAG{tag} 0 1 2 3", None),
    ("SWAP{tag} 0 1 2 3", None),
]


@pytest.mark.parametrize(
    ("stim_str", "exp_stim_str"),
    [
        *_tag_tests(stim_2q_gate_roundtrip, tag=None),
        *_tag_tests(stim_2q_gate_roundtrip, tag="my_tag"),
    ],
)
def test_stim_2q_gate_roundtrip(stim_str: str, exp_stim_str: str | None):
    """Test that two qubit gate operations can be parsed and printed to/from Stim."""
    check_stim_roundtrip(stim_str, exp_stim_str)


stim_annotation_roundtrip_test = [
    ("TICK{tag}", None),
    ("QUBIT_COORDS{tag}(3.0, 0.5) 3", None),
    ("SHIFT_COORDS{tag}(2.0, 0.0, -1.0)", None),
    ("DETECTOR{tag}", None),
    ("M{tag} 0 1\nDETECTOR{tag} rec[-2] rec[-1]", None),
    ("M{tag} 0 1\nDETECTOR{tag}(1.0, 0.0, 0.0) rec[-2] rec[-1]", None),
    ("OBSERVABLE_INCLUDE{tag}(0)", None),
    ("M{tag} 0 1\nOBSERVABLE_INCLUDE{tag}(1) rec[-1] rec[-2]", None),
]


@pytest.mark.parametrize(
    ("stim_str", "exp_stim_str"),
    [
        *_tag_tests(stim_annotation_roundtrip_test, tag=None),
        *_tag_tests(stim_annotation_roundtrip_test, tag="my_tag"),
    ],
)
def test_stim_annotation_roundtrip(stim_str: str, exp_stim_str: str | None):
    """Test that annotation operations can be parsed and printed to/from Stim."""
    check_stim_roundtrip(stim_str, exp_stim_str)


stim_noise_roundtrip_test = [
    ("DEPOLARIZE1{tag}(0.01) 2 4", None),
    ("DEPOLARIZE2{tag}(0.1) 2 4 3 5", None),
    ("PAULI_CHANNEL_1{tag}(0.1, 0.2, 0.3) 2 4", None),
    (
        "PAULI_CHANNEL_2{tag}(0.01, 0.02, 0.03, 0.04, 0.05, 0.01, 0.02, "
        "0.03, 0.04, 0.05, 0.01, 0.02, 0.03, 0.04, 0.05) 2 4 3 5",
        None,
    ),
    ("X_ERROR{tag}(0.1) 0 3", None),
    ("Y_ERROR{tag}(0.1) 0 3", None),
    ("Z_ERROR{tag}(0.1) 0 3", None),
    ("PAULI_CHANNEL_1{tag}(0.1, 0, 0) 0", "X_ERROR{tag}(0.1) 0"),
    ("PAULI_CHANNEL_1{tag}(0, 0.1, 0) 0", "Y_ERROR{tag}(0.1) 0"),
    ("PAULI_CHANNEL_1{tag}(0, 0, 0.1) 0", "Z_ERROR{tag}(0.1) 0"),
    ("CORRELATED_ERROR{tag}(0.1) X0 Y1", None),
    ("CORRELATED_ERROR{tag}(0.02) X0 Y1 X2 Z5 Z3", None),
    ("CORRELATED_ERROR{tag}(0.1) X0", None),
    ("CORRELATED_ERROR{tag}(0.1) X0\nELSE_CORRELATED_ERROR{tag}(0.1) X0 Y1", None),
    ("CORRELATED_ERROR{tag}(0.1) X0\nELSE_CORRELATED_ERROR{tag}(0.02) X0 Y1 X2 Z5 Z3", None),
    ("CORRELATED_ERROR{tag}(0.1) X0\nELSE_CORRELATED_ERROR{tag}(0.1) X0", None),
    ("E{tag}(0.1) X0 Y1", "CORRELATED_ERROR{tag}(0.1) X0 Y1"),
    ("E{tag}(0.02) X0 Y1 X2 Z5 Z3", "CORRELATED_ERROR{tag}(0.02) X0 Y1 X2 Z5 Z3"),
]


@pytest.mark.parametrize(
    ("stim_str", "exp_stim_str"),
    [
        *_tag_tests(stim_noise_roundtrip_test, tag=None),
        *_tag_tests(stim_noise_roundtrip_test, tag="my_tag"),
    ],
)
def test_stim_noise_roundtrip(stim_str: str, exp_stim_str: str | None):
    """Test that annotation operations can be parsed and printed to/from Stim."""
    check_stim_roundtrip(stim_str, exp_stim_str)


@pytest.mark.parametrize(
    ("stim_str", "exp_stim_str"),
    [
        ("REPEAT 20 {\n    R 0 1\n}", None),
        ("M 0\nREPEAT 2 {\n    M 0\n}\nDETECTOR(0.0, 0.0) rec[-2]", None),
        ("REPEAT[my_tag] 20 {\n    R[my_tag] 0 1\n}", None),
        ("M[tag1] 0\nREPEAT[tag2] 2 {\n    M[tag3] 0\n}\nDETECTOR[tag4](0.0, 0.0) rec[-2]", None),
    ],
)
def test_stim_repeat_roundtrip(stim_str: str, exp_stim_str: str | None):
    """Test that annotation operations can be parsed and printed to/from Stim."""
    check_stim_roundtrip(stim_str, exp_stim_str)


def test_stim_printing_invalid_op():
    """Test attempt to print a non-stim dialect op as stim throws an error."""
    with pytest.raises(TypeError, match="Cannot print operation as Stim"):
        to_stim(ModuleOp([t.TestOp(result_types=[])]))


@pytest.mark.parametrize(
    "opn",
    [
        CliffordGateOp(gate_type=TwoQubitUnitaryEnum.SWAP, targets=[qubit]),
        Depolarize2Op([qubit], 0.01),
        PauliChannel2Op([qubit], [0.0] * 15),
    ],
)
def test_invalid_two_qubit_target_num(opn: Operation):
    """Test that a two qubit gate with an odd number of targets throws an error on verification."""
    with pytest.raises(VerifyException, match="Two qubit gates expect an even number of targets"):
        opn.verify()


def test_invalid_gate_type_parsing(xdsl_context: Context):
    """Test that parsing assembly with an invalid gate_type throws an error."""
    program = "stim.clifford HXY (%0, %1)"
    parser = Parser(xdsl_context, program)
    with pytest.raises(
        ParseError,
        match="Expected a gate name of either SingleQubitGateAttr or TwoQubitGateAttr "
        "for stim\\.clifford",
    ):
        parser.parse_optional_operation()


def test_meas_op_verification():
    """Test the verification for measurement ops."""
    with pytest.raises(VerifyException, match="expected integer >= 1, got 0"):
        MeasurementGateOp([]).verify()

    with pytest.raises(
        VerifyException,
        match="expected from int variable 'Targets'",
    ):
        MeasurementGateOp.create(
            operands=[qubit],
            properties={"pauli_modifier": PauliAttr(PauliOperatorEnum.X)},
        ).verify()


@pytest.mark.parametrize(
    "noise_op",
    [
        Depolarize1Op([], 1.1),
        Depolarize2Op([], 1.1),
        PauliChannel1Op([], [1.1] * 3),
        PauliChannel2Op([], [1.1] * 15),
    ],
)
def test_depolarize_invalid_probability(noise_op: Operation):
    """Test that noise with an invalid probability throws an error."""
    with pytest.raises(
        VerifyException, match=r"Noise probability \(1\.1\) must be between 0 and 1"
    ):
        noise_op.verify()


@pytest.mark.parametrize(
    "noise_op",
    [
        PauliChannel1Op([], [0.5] * 3),
        PauliChannel2Op([], [0.1] * 15),
    ],
)
def test_depolarize_invalid_probability_sum(noise_op: Operation):
    """Test that noise probabilities that sum to an invalid probability throws an error."""
    with pytest.raises(
        VerifyException, match=r"Noise probabilities \(.*\) must sum to between 0 and 1"
    ):
        noise_op.verify()


def test_else_correlated_error_invalid_position():
    op = ElseCorrelatedErrorOp([], [], 0.1)
    ModuleOp([op])
    with pytest.raises(
        VerifyException,
        match=r"stim.else_correlated_error must follow either another "
        r"stim.else_correlated_error op or a stim.correlated_error op.",
    ):
        op.verify()


@pytest.mark.parametrize("error_op_type", [CorrelatedErrorOp, ElseCorrelatedErrorOp])
def test_correlated_error_pauli_target_mismatch(
    error_op_type: type[CorrelatedErrorOp | ElseCorrelatedErrorOp],
):
    op = error_op_type([], [PauliOperatorEnum.X], 0.1)
    with pytest.raises(
        VerifyException,
        match=r"Expected one Pauli per target but got: 1 Pauli for 0 targets.",
    ):
        op.verify()


@pytest.mark.parametrize(
    ("op_type", "probabilities", "exp_error"),
    [
        (PauliChannel1Op, [1, 2, 3], None),
        (PauliChannel1Op, [1, 2, 3, 4], "PAULI_CHANNEL_1 expects 3 probabilities"),
        (PauliChannel1Op, [1, 2], "PAULI_CHANNEL_1 expects 3 probabilities"),
        (PauliChannel2Op, [1, 2, 3, 4], "PAULI_CHANNEL_2 expects 15 probabilities"),
        (PauliChannel2Op, list(range(14)), "PAULI_CHANNEL_2 expects 15 probabilities"),
        (PauliChannel2Op, list(range(15)), None),
        (PauliChannel2Op, list(range(16)), "PAULI_CHANNEL_2 expects 15 probabilities"),
    ],
)
def test_pauli_channel_init_errors(
    op_type: type[PauliChannel1Op | PauliChannel2Op],
    probabilities: list[float] | list[FloatData],
    exp_error: str | None,
):
    qubits = t.TestOp(result_types=[QubitType()] * 4).res
    if exp_error is not None:
        with pytest.raises(ValueError, match=exp_error):
            op_type(qubits, probabilities)
    else:
        op_type(qubits, probabilities)


@pytest.mark.parametrize(
    ("repeat_op", "error_str"),
    [
        (RepeatOp(0, Block([YieldOp()])), "repetitions must be > 0"),
        (
            RepeatOp(1, Block([YieldOp(ro)]), [ro, ro]),
            "The number of iter_args \\(2\\), the number of block arguments in the repeat body "
            "\\(0\\), the number of values yielded from the repeat body \\(1\\), and the number of "
            "results returned \\(2\\) must all match",
        ),
        (
            RepeatOp(1, Block([YieldOp(ro)], arg_types=[qubit.type]), [ro]),
            "The iter arg type i1, block arg type !stim.qubit, yielded value type i1, "
            "and result type i1 must all match",
        ),
    ],
)
def test_repeat_verification(repeat_op: RepeatOp, error_str):
    """Test the verification for the repeat op."""
    with pytest.raises(VerifyException, match=error_str):
        repeat_op.verify()


@pytest.mark.parametrize(
    ("qubit_mapping_attr", "exp_coordinates"),
    [
        (QubitMappingAttr([]), ()),
        (QubitMappingAttr([1.0]), (1.0,)),
        (QubitMappingAttr([0.0, 0.5, 1.25]), (0.0, 0.5, 1.25)),
        (QubitMappingAttr(ArrayAttr([])), ()),
        (QubitMappingAttr(ArrayAttr([FloatData(1.0)])), (1.0,)),
        (
            QubitMappingAttr(ArrayAttr([FloatData(0.0), FloatData(0.5), FloatData(1.25)])),
            (0.0, 0.5, 1.25),
        ),
    ],
)
def test_qubit_mapping_coordinates(qubit_mapping_attr: QubitMappingAttr, exp_coordinates):
    """Test the coordinates property of QubitMappingAttr."""
    assert qubit_mapping_attr.coordinates == exp_coordinates


def test_mpp_verification_empty_targets():
    """MultiPauliProductMeasurementOp must verify non-empty targets."""
    with pytest.raises(VerifyException, match="expected integer >= 1, got 0"):
        MultiPauliProductMeasurementOp([], [PauliOperatorEnum.X]).verify()


def test_mpp_verification_mismatched_modifiers():
    """MultiPauliProductMeasurementOp must verify modifiers align with targets."""
    with pytest.raises(
        VerifyException,
        match=(
            r"A multi-pauli product measurement operation must have the same number of "
            r"pauli modifiers as targeted qubits."
        ),
    ):
        MultiPauliProductMeasurementOp([qubit], [PauliOperatorEnum.X, PauliOperatorEnum.Y]).verify()


@pytest.mark.parametrize(
    ("stim_str", "exp_stim_str"),
    [
        ("R[] 0 1", "R 0 1"),
        ("R[compile_pass:stim_to_qref] 0 1", None),
        ('R[{"stage":"lowering","round":7}] 0 1', None),
        ("R[phase 1] 0 1", None),
        ("R[  phase_1] 0 1", None),
        ("R[phase_1  ] 0 1", None),
        (r"R[\n] 0 1", None),
        (r"R[\r] 0 1", None),
        (r"R[\B] 0 1", None),
        (r"R[\C] 0 1", None),
        (r"R[[\r\n\B\C] 0 1", None),
        (
            'R[{"basis": "Z", "my_int": 1, "my_bool": true, "my_float": 0.2, "my_none": null}]'
            + " 0 1",
            None,
        ),
        ('R[{"array": ["#Z", 1, "#1", {"key": null}\\C}] 0 1', None),
        ("R[{\22my_type\22: \22#!test.type<\5C\22test\5C\22>\22}] 0 1", None),
    ],
)
def test_tag_roundtrip(stim_str: str, exp_stim_str: str | None):
    """Test that practical and escaped tag texts survive Stim roundtrip unchanged."""
    check_stim_roundtrip(stim_str, exp_stim_str)


@pytest.mark.parametrize(
    "stim_str",
    [
        r"R[\"] 0 1",
        r"R[\x] 0 1",
        r"R[\q] 0 1",
        r"R[\\] 0 1",
    ],
)
def test_tag_roundtrip_unknown_escape_fails(stim_str: str):
    """Unknown tag escapes are rejected by Stim parsing."""
    with pytest.raises(ValueError, match=r"Unrecognized escape sequence"):
        check_stim_roundtrip(stim_str, None)
