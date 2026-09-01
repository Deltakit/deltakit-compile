import re
from collections.abc import Sequence
from typing import cast

import pytest
from xdsl.dialects import test
from xdsl.dialects.builtin import DYNAMIC_INDEX, BoolAttr, IntegerType, ModuleOp, TensorType
from xdsl.dialects.func import FuncOp
from xdsl.ir import Attribute, Block, Region, SSAValue
from xdsl.utils.exceptions import VerifyException

from deltakit_compile.dialects.arith import ConstantOp
from deltakit_compile.dialects.log_asm_api import (
    BarrierOp,
    CallOp,
    CastOp,
    CircuitDeclarationOp,
    ReturnOp,
    UnsizedGateOp,
    UnsizedResetOp,
)
from deltakit_compile.dialects.logical_assembly import (
    OrientationEnum,
    PlacementAttr,
    RotatedPlanarPatchType,
    SurfaceCodeBasePatch,
    UnrotatedPlanarPatchType,
)
from deltakit_compile.dialects.qcore import (
    ConcatenateOp,
    CXGateAttr,
    GateAttribute,
    Pauli,
    PauliAttr,
    QubitRegType,
    QubitType,
    SplitOp,
    XGateAttr,
    ZGateAttr,
    qubit_count,
)


def get_identity_circuit_declaration_op(
    name: str, inout: Sequence[Attribute]
) -> CircuitDeclarationOp:
    block = Block([], arg_types=inout)
    block.add_op(ReturnOp(*block.args))
    return CircuitDeclarationOp(name, (inout, inout), body=Region(block))


@pytest.mark.parametrize(
    ("basis", "qubits_type", "err_msg"),
    [
        ("X", TensorType(QubitType(), (1,)), None),
        (PauliAttr.X(), TensorType(QubitType(), (1,)), None),
        ("Z", TensorType(IntegerType(1), (1,)), "Expected attribute !qcore.qubit but got i1"),
        (
            "Z",
            TensorType(QubitRegType(1), (1,)),
            re.escape("Expected attribute !qcore.qubit but got !qcore.qubit_reg<1>"),
        ),
        (
            "Y",
            TensorType(QubitType(), (0,)),
            re.escape("Invalid value 0, expected a strictly positive integer or DYNAMIC_INDEX"),
        ),
        (
            "Y",
            TensorType(QubitType(), (-9834,)),
            re.escape("Invalid value -9834, expected a strictly positive integer or DYNAMIC_INDEX"),
        ),
    ],
)
def test_unsized_reset_op(basis: Pauli, qubits_type: Attribute, err_msg: str | None) -> None:
    qubits = test.TestOp(result_types=[qubits_type]).res[0]
    if err_msg is not None:
        with pytest.raises(VerifyException, match=err_msg):
            UnsizedResetOp(basis, qubits).verify()
    else:
        UnsizedResetOp(basis, qubits).verify()


@pytest.mark.parametrize(
    ("gate", "qubits_type", "err_msg"),
    [
        (XGateAttr(), TensorType(QubitType(), (1,)), None),
        (XGateAttr(sqrt=True), TensorType(QubitType(), (10,)), None),
        (CXGateAttr(), TensorType(QubitType(), (10,)), None),
        (
            CXGateAttr(),
            TensorType(QubitType(), (11,)),
            re.escape(
                "Invalid broadcast of qcore.gate.cx: expected the gate to be applied on a "
                "number of qubits that is a multiple of 2 but got 11."
            ),
        ),
        (
            ZGateAttr(),
            TensorType(IntegerType(1), (1,)),
            "Expected attribute !qcore.qubit but got i1",
        ),
        (
            ZGateAttr(),
            TensorType(QubitRegType(1), (1,)),
            re.escape("Expected attribute !qcore.qubit but got !qcore.qubit_reg<1>"),
        ),
        (
            ZGateAttr(),
            TensorType(QubitType(), (0,)),
            re.escape("Invalid value 0, expected a strictly positive integer or DYNAMIC_INDEX"),
        ),
        (
            ZGateAttr(),
            TensorType(QubitType(), (-9834,)),
            re.escape("Invalid value -9834, expected a strictly positive integer or DYNAMIC_INDEX"),
        ),
    ],
)
def test_unsized_gate_op(gate: GateAttribute, qubits_type: Attribute, err_msg: str | None) -> None:
    qubits = test.TestOp(result_types=[qubits_type]).res[0]
    if err_msg is not None:
        with pytest.raises(VerifyException, match=err_msg):
            UnsizedGateOp(gate, qubits).verify()
    else:
        UnsizedGateOp(gate, qubits).verify()


@pytest.mark.parametrize(
    ("attrs", "err_msg"),
    [
        ([QubitRegType(10)], None),
        ([QubitRegType(i) for i in range(1, 10)], None),
        (
            [RotatedPlanarPatchType((3, 3), PlacementAttr((0, 0), OrientationEnum.HORIZONTAL_Z))],
            None,
        ),
        (
            [
                UnrotatedPlanarPatchType(
                    (5, 5), PlacementAttr((i, i), OrientationEnum.HORIZONTAL_Z)
                )
                for i in range(0, 100, 5)
            ],
            None,
        ),
    ],
)
def test_barrier_op(attrs: Sequence[Attribute], err_msg: str | None) -> None:
    ssas = test.TestOp(result_types=attrs).res
    if err_msg is not None:
        with pytest.raises(VerifyException, match=err_msg):
            BarrierOp(ssas).verify()
    else:
        BarrierOp(ssas).verify()


@pytest.mark.parametrize(
    ("from_", "to", "err_msg"),
    [
        # Valid casts with the same types
        (QubitRegType(10), QubitRegType(10), None),
        (QubitRegType(38), QubitRegType(38), None),
        (RotatedPlanarPatchType((3, 3), None), RotatedPlanarPatchType((3, 3), None), None),
        (UnrotatedPlanarPatchType((3, 3), None), UnrotatedPlanarPatchType((3, 3), None), None),
        (TensorType(IntegerType(1), (1,)), TensorType(IntegerType(1), (1,)), None),
        (TensorType(QubitType(), (1,)), TensorType(QubitType(), (1,)), None),
        (TensorType(QubitRegType(5), (1,)), TensorType(QubitRegType(5), (1,)), None),
        # Valid casts with different types
        (QubitRegType(17), RotatedPlanarPatchType((3, 3), None), None),
        (QubitRegType(29), RotatedPlanarPatchType((3, 5), None), None),
        (QubitRegType(25), UnrotatedPlanarPatchType((3, 3), None), None),
        (QubitRegType(45), UnrotatedPlanarPatchType((5, 3), None), None),
        (QubitRegType(346), TensorType(QubitType(), shape=(346,)), None),
        # Tensor type with dynamic size involved but same type.
        (TensorType(QubitRegType(5), (1,)), TensorType(QubitRegType(5), (DYNAMIC_INDEX,)), None),
        (
            TensorType(QubitRegType(5), (DYNAMIC_INDEX,)),
            TensorType(QubitRegType(5), (DYNAMIC_INDEX,)),
            None,
        ),
        (TensorType(QubitRegType(5), (DYNAMIC_INDEX,)), TensorType(QubitRegType(5), (4,)), None),
        # Invalid casts due to types being different.
        (
            QubitRegType(3),
            TensorType(IntegerType(1), (3,)),
            re.escape(
                "Cannot cast an object of type !qcore.qubit_reg<3> into tensor<3xi1>: "
                "types are incompatible."
            ),
        ),
        (
            TensorType(IntegerType(1), (3,)),
            TensorType(QubitType(), (3,)),
            re.escape(
                "Cannot cast an object of type tensor<3xi1> into tensor<3x!qcore.qubit>: "
                "types are incompatible."
            ),
        ),
        (
            TensorType(IntegerType(1), (DYNAMIC_INDEX,)),
            TensorType(QubitType(), (3,)),
            re.escape(
                "Cannot cast an object of type tensor<?xi1> into tensor<3x!qcore.qubit>: types "
                "are incompatible."
            ),
        ),
        # Invalid casts due to size being different.
        (
            UnrotatedPlanarPatchType((3, 3), None),
            RotatedPlanarPatchType((3, 3), None),
            re.escape(
                "Cannot cast an object of type !log_asm.patch.unrot_planar<size=(3, 3)> (of size "
                "25) into !log_asm.patch.rot_planar<size=(3, 3)> (of size 17) due to differing "
                "sizes."
            ),
        ),
        (
            QubitRegType(3),
            QubitRegType(5),
            re.escape(
                "Cannot cast an object of type !qcore.qubit_reg<3> (of size 3) into "
                "!qcore.qubit_reg<5> (of size 5) due to differing sizes."
            ),
        ),
        (
            RotatedPlanarPatchType((3, 3), None),
            RotatedPlanarPatchType((4, 3), None),
            re.escape(
                "Cannot cast an object of type !log_asm.patch.rot_planar<size=(3, 3)> (of size 17) "
                "into !log_asm.patch.rot_planar<size=(4, 3)> (of size 23) due to differing sizes."
            ),
        ),
        (
            TensorType(IntegerType(1), (4,)),
            TensorType(IntegerType(1), (3,)),
            re.escape(
                "Cannot cast an object of type tensor<4xi1> (of size 4) into tensor<3xi1> "
                "(of size 3) due to differing sizes."
            ),
        ),
    ],
)
def test_cast_op(
    from_: QubitRegType | SurfaceCodeBasePatch | TensorType,
    to: QubitRegType | SurfaceCodeBasePatch | TensorType,
    err_msg: str | None,
) -> None:
    ssas = cast(
        SSAValue[QubitRegType | SurfaceCodeBasePatch | TensorType],
        test.TestOp(result_types=[from_]).res,
    )
    if err_msg is not None:
        with pytest.raises(VerifyException, match=err_msg):
            CastOp(ssas, to).verify()
    else:
        CastOp(ssas, to).verify()


@pytest.mark.parametrize(
    ("ins", "outs"),
    [
        ([], []),
        ([QubitRegType(4)], [QubitRegType(4)]),
        ([QubitRegType(2), QubitRegType(1), QubitRegType(1)], [QubitRegType(4)]),
        (
            [QubitRegType(10), QubitRegType(11)],
            [QubitRegType(1), QubitRegType(10), QubitRegType(4), QubitRegType(6)],
        ),
    ],
)
def test_circuit_declaration_success(ins: list[Attribute], outs: list[Attribute]) -> None:
    block = Block([], arg_types=ins)
    # Making sure that the return type is correct if ins and outs are different
    if ins != outs:
        assert all(isinstance(arg.type, QubitRegType) for arg in block.args)
        block.add_op(ConcatenateOp(cast(Sequence[SSAValue[QubitRegType]], block.args)))
        assert block.last_op is not None
        assert len(block.last_op.result_types) == 1
        assert isinstance(block.last_op.result_types[0], QubitRegType)
        assert all(isinstance(reg, QubitRegType) for reg in outs)
        block.add_op(
            SplitOp(
                cast(SSAValue[QubitRegType], block.last_op.results[0]),
                [qubit_count(cast(QubitRegType, reg)) for reg in outs],
            )
        )
        assert block.last_op is not None
        assert all(isinstance(rest, QubitRegType) for rest in block.last_op.result_types)
        block.add_op(ReturnOp(*block.last_op.results))
    else:
        block.add_op(ReturnOp(*block.args))
    CircuitDeclarationOp("circuit", (ins, outs), body=Region(block)).verify()


@pytest.mark.parametrize(
    ("ins", "outs", "ins_qubits", "outs_qubits"),
    [
        ([], [QubitType()], 0, 1),
        ([QubitRegType(2)], [QubitRegType(4)], 2, 4),
        ([QubitRegType(2), QubitType()], [QubitRegType(4)], 3, 4),
    ],
)
def test_circuit_declaration_failing(
    ins: list[Attribute], outs: list[Attribute], ins_qubits: int, outs_qubits: int
) -> None:
    error_msg = (
        f".*integer {ins_qubits} expected from int variable 'Qubits', but got {outs_qubits}.*"
    )
    with pytest.raises(VerifyException, match=error_msg):
        CircuitDeclarationOp("circuit", (ins, outs), [ReturnOp()]).verify()


def test_unmatched_function_type_and_block_args() -> None:
    region = Region(Block(ops=[ReturnOp()], arg_types=[QubitType()]))
    msg = re.escape(
        "attributes ('!qcore.qubit',) expected from range variable 'Arguments', "
        "but got ('!qcore.qubit_reg<1>',)"
    )
    with pytest.raises(VerifyException, match=msg):
        CircuitDeclarationOp("circuit", function_type=([QubitRegType(1)], []), body=region).verify()


def test_number_of_return_types_disagreeing() -> None:
    region = Region(Block(ops=[ReturnOp()], arg_types=[QubitType()]))
    msg = re.escape(
        "The number of variables returned from the circuit declaration (1) doesn't match "
        "the number of variables the inner block returns (0)."
    )
    with pytest.raises(VerifyException, match=msg):
        CircuitDeclarationOp(
            "circuit", function_type=([QubitType()], [QubitType()]), body=region
        ).verify()


def test_return_types_disagreeing() -> None:
    block = Block(arg_types=[QubitRegType(2), QubitRegType(3)])
    block.add_op(ReturnOp(*block.args))
    region = Region(block)
    msg = re.escape(
        "The type of the 1-th variable returned from the circuit declaration "
        "(!qcore.qubit_reg<3>) doesn't match the type of the corresponding variable the "
        "inner block returns (!qcore.qubit_reg<2>)."
    )
    with pytest.raises(VerifyException, match=msg):
        CircuitDeclarationOp(
            "circuit",
            function_type=([QubitRegType(2), QubitRegType(3)], [QubitRegType(3), QubitRegType(2)]),
            body=region,
        ).verify()


def test_call_op_on_empty_function() -> None:
    block = Block([get_identity_circuit_declaration_op("empty", []), CallOp("empty", [], [])])
    module_op = ModuleOp(Region(block))
    module_op.verify()


def test_call_op_without_symbol_table() -> None:
    block = Block([get_identity_circuit_declaration_op("empty", []), CallOp("empty", [], [])])
    with pytest.raises(ValueError, match="has no SymbolTable ancestor"):
        block.verify()


def test_call_op_without_corresponding_symbol() -> None:
    const_op = ConstantOp(BoolAttr.from_bool(False))
    block = Block(
        [
            const_op,
            get_identity_circuit_declaration_op("bar", []),
            CallOp("foo", [const_op.results[0]], []),
        ]
    )
    module_op = ModuleOp(Region(block))
    with pytest.raises(
        VerifyException, match=re.escape("'@foo' could not be found in symbol table")
    ):
        module_op.verify()


def test_call_op_with_incorrect_corresponding_symbol() -> None:
    const_op = ConstantOp(BoolAttr.from_bool(False))
    block = Block(
        [
            const_op,
            FuncOp.external("empty", [], []),
            CallOp("empty", [const_op.results[0]], []),
        ]
    )
    module_op = ModuleOp(Region(block))
    with pytest.raises(
        VerifyException, match=re.escape("'@empty' does not reference a valid circuit declaration")
    ):
        module_op.verify()


def test_call_op_on_empty_function_with_inputs() -> None:
    const_op = ConstantOp(BoolAttr.from_bool(False))
    block = Block(
        [
            const_op,
            get_identity_circuit_declaration_op("empty", []),
            CallOp("empty", [const_op.results[0]], []),
        ]
    )
    module_op = ModuleOp(Region(block))
    with pytest.raises(VerifyException, match="Incorrect number of operands for callee"):
        module_op.verify()


def test_call_op_on_empty_function_with_expected_outputs() -> None:
    const_op = ConstantOp(BoolAttr.from_bool(False))
    block = Block(
        [
            const_op,
            get_identity_circuit_declaration_op("empty", []),
            CallOp("empty", [], [IntegerType(1)]),
        ]
    )
    module_op = ModuleOp(Region(block))
    with pytest.raises(VerifyException, match="Incorrect number of results for callee"):
        module_op.verify()


def test_call_op_on_wrong_input_types() -> None:
    const_op = ConstantOp(BoolAttr.from_bool(False))
    block = Block(
        [
            const_op,
            get_identity_circuit_declaration_op("empty", [QubitType()]),
            CallOp("empty", [const_op.results[0]], [QubitType()]),
        ]
    )
    module_op = ModuleOp(Region(block))
    with pytest.raises(
        VerifyException,
        match=re.escape("expected operand type !qcore.qubit, but provided i1 for operand number 0"),
    ):
        module_op.verify()


def test_call_op_on_wrong_output_types() -> None:
    const_op = ConstantOp(BoolAttr.from_bool(False))
    block = Block(
        [
            const_op,
            get_identity_circuit_declaration_op("empty", [IntegerType(1)]),
            CallOp("empty", [const_op.results[0]], [QubitType()]),
        ]
    )
    module_op = ModuleOp(Region(block))
    with pytest.raises(
        VerifyException,
        match=re.escape("expected result type i1, but provided !qcore.qubit for result number 0"),
    ):
        module_op.verify()
