import re

import pytest
from xdsl.builder import Builder
from xdsl.context import Context
from xdsl.dialects import test as t
from xdsl.dialects.builtin import Builtin, ModuleOp, TensorType, i1, i32, i64
from xdsl.ir import Attribute, Block, BlockArgument, Operation, SSAValue
from xdsl.traits import SymbolTable
from xdsl.transforms.canonicalize import CanonicalizePass

from deltakit_compile.dialects.arith import Arith
from deltakit_compile.dialects.log_asm_api import (
    CallOp,
    CastOp,
    CircuitDeclarationOp,
    LogAsmApi,
    ReturnOp,
    UnsizedGateOp,
    UnsizedResetOp,
)
from deltakit_compile.dialects.qcore import CXGateAttr, PauliAttr, QCore, QubitType, XGateAttr
from deltakit_compile.dialects.qec import ObservableType
from deltakit_compile.dialects.qref import QRef
from deltakit_compile.dialects.qstruct import ParallelOp, QStruct, YieldOp
from deltakit_compile.dialects.stabiliser import ConcreteFlowArrayAttr, ConcreteFlowAttr
from deltakit_compile.dialects.tensor import Tensor
from deltakit_compile.frontend.circuit import CircuitBuilder
from deltakit_compile.frontend.common._annotations import Observable
from deltakit_compile.frontend.common._builder import OperationBuilder
from deltakit_compile.frontend.common._circuit import (
    Circuit,
    ParallelAlignment,
)
from deltakit_compile.frontend.common._classical_expr import Result
from deltakit_compile.frontend.common._exceptions import (
    ArgumentError,
    ArgumentSizeError,
    ArgumentTypeMismatchError,
    DifferentBuildersError,
    DuplicatedIdentifiersError,
    IdentifierConflictError,
    InvalidSizeError,
    ObjectNotAttachedError,
    UnsupportedArgumentTypeError,
    UnsupportedReturnTypeError,
)
from deltakit_compile.frontend.common._gates import GATE_MAPPING
from deltakit_compile.frontend.common._measurements import MeasurementBit, MeasurementReg
from deltakit_compile.frontend.common._pauli import Pauli
from deltakit_compile.frontend.common._qubit_reg import QubitReg
from deltakit_compile.frontend.common._vector import Vector
from tests.unit.frontend.conftest import add_to_builder_with_fake_ssa, number_of_operations


def test_circuit_builder_instantiation() -> None:
    CircuitBuilder()


# region Private helper methods
def test_check_register_is_correctly_attached() -> None:
    builder = CircuitBuilder()
    register = builder.add_arg(QubitReg())

    # The following should not raise because the register is attached
    builder._check_all_are_in_scope(register)

    # The following should raise, because the register is not attached.
    with pytest.raises(ObjectNotAttachedError):
        builder._check_all_are_in_scope(QubitReg())


# region Arguments and returns


def test_add_arg() -> None:
    builder = CircuitBuilder()

    register = builder.add_arg(QubitReg())
    assert register._num_qubits is None
    assert register.num_qubits is None
    assert register.qubit_locations is None
    assert register.identifier is not None
    assert register._is_attached

    sized_register = builder.add_arg(QubitReg(45))
    assert sized_register._num_qubits == 45
    assert sized_register.num_qubits == 45
    assert sized_register.qubit_locations is None
    assert sized_register.identifier is not None
    assert sized_register._is_attached

    regs = []
    for i in range(1, 10):
        regs.append(builder.add_arg(QubitReg(i)))
    assert len(regs) == 9
    assert all(r.num_qubits == i + 1 for i, r in enumerate(regs))
    assert all(r.qubit_locations is None for r in regs)
    assert all(r._is_attached for r in regs)

    qreg = builder.add_arg(QubitReg())
    creg = builder.add_arg(MeasurementReg(4))
    res = builder.add_arg(Result())
    obs = builder.add_arg(Observable())
    assert isinstance(qreg, QubitReg)
    assert isinstance(creg, MeasurementReg)
    assert isinstance(res, Result)
    assert isinstance(obs, Observable)


def test_add_arg_raises() -> None:
    builder = CircuitBuilder()
    msg = "Incompatible argument type provided: int."
    with pytest.raises(UnsupportedArgumentTypeError, match=msg):
        builder.add_arg(1)  # type: ignore[type-var]


def test_add_returns() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg(1))
    builder.gate("X", reg)
    ro = builder.measure(Pauli.Z, reg)
    builder.add_return(ro)
    circuit = builder.build("x_gate")
    assert isinstance(circuit._module.body.block.first_op, CircuitDeclarationOp)
    assert circuit._module.body.block.first_op.sym_name.data == "x_gate"
    assert len(circuit._arguments) == 1
    assert isinstance(circuit._arguments[0], QubitReg)
    assert len(circuit._result_type) == 1


# region Applying operations
def test_gate() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg(10))
    builder.gate("X", reg[0])
    assert isinstance(builder._builder.last_op, UnsizedGateOp)
    assert isinstance(builder._builder.last_op.gate, XGateAttr)
    builder.gate("X", [reg[1], reg[3]])
    assert isinstance(builder._builder.last_op, UnsizedGateOp)
    assert isinstance(builder._builder.last_op.gate, XGateAttr)
    builder.gate("CX", reg)
    assert isinstance(builder._builder.last_op, UnsizedGateOp)
    assert isinstance(builder._builder.last_op.gate, CXGateAttr)

    num_ops_before = len(builder._builder.block.ops)
    with pytest.raises(IndexError, match="Gate 'G' is not yet supported"):
        builder.gate("G", reg)
    num_ops_after = len(builder._builder.block.ops)
    assert num_ops_before == num_ops_after

    num_ops_before = len(builder._builder.block.ops)
    other_builder = OperationBuilder()
    oreg = add_to_builder_with_fake_ssa(other_builder, QubitReg(10))
    with pytest.raises(DifferentBuildersError):
        builder.gate("X", oreg)
    num_ops_after = len(builder._builder.block.ops)
    assert num_ops_before == num_ops_after

    assert number_of_operations(builder._builder, lambda op: not isinstance(op, UnsizedGateOp)) == 3

    circuit = builder.build("test")
    assert isinstance(circuit._module.body.block.first_op, CircuitDeclarationOp)
    assert circuit._module.body.block.first_op.sym_name.data == "test"
    assert len(circuit._arguments) == 1
    assert isinstance(circuit._arguments[0], QubitReg)

    msg = "Cannot apply gate on empty operand."
    with pytest.raises(InvalidSizeError, match=msg):
        builder.gate("X", [])


def test_reset_gate() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg(10))
    builder.gate("R", reg[0])
    assert isinstance(builder._builder.last_op, UnsizedResetOp)
    assert builder._builder.last_op.basis == PauliAttr.Z()
    assert isinstance(builder._builder.last_op.qubits.type, TensorType)
    assert builder._builder.last_op.qubits.type.shape.data[0].data == 1
    builder.gate("RX", reg[0:3])
    assert isinstance(builder._builder.last_op, UnsizedResetOp)
    assert builder._builder.last_op.basis == PauliAttr.X()
    assert isinstance(builder._builder.last_op.qubits.type, TensorType)
    assert builder._builder.last_op.qubits.type.shape.data[0].data == 3


@pytest.mark.parametrize(("gate"), ["I", "X", "Y", "Z", "H", "S", "T"])
def test_all_one_qubit_gates(gate: str) -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg(10))
    builder.gate(gate, reg[0])
    assert isinstance(builder._builder.last_op, UnsizedGateOp)
    assert isinstance(builder._builder.last_op.gate, GATE_MAPPING[gate].__class__)
    assert isinstance(builder._builder.last_op.qubits.type, TensorType)
    assert builder._builder.last_op.qubits.type.shape.data[0].data == 1
    builder.gate(gate, reg[0:3])
    assert isinstance(builder._builder.last_op, UnsizedGateOp)
    assert isinstance(builder._builder.last_op.gate, GATE_MAPPING[gate].__class__)
    assert isinstance(builder._builder.last_op.qubits.type, TensorType)
    assert builder._builder.last_op.qubits.type.shape.data[0].data == 3


@pytest.mark.parametrize(
    ("gate"), ["CX", "CY", "CZ", "SWAP", "iSWAP", "SQRTXX", "SQRTYY", "SQRTZZ"]
)
def test_all_two_qubit_gates(gate: str) -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg(10))
    builder.gate(gate, (reg[0], reg[1]))
    assert isinstance(builder._builder.last_op, UnsizedGateOp)
    assert isinstance(builder._builder.last_op.gate, GATE_MAPPING[gate].__class__)
    assert isinstance(builder._builder.last_op.qubits.type, TensorType)
    assert builder._builder.last_op.qubits.type.shape.data[0].data == 2
    builder.gate(gate, reg[0:4])
    assert isinstance(builder._builder.last_op, UnsizedGateOp)
    assert isinstance(builder._builder.last_op.gate, GATE_MAPPING[gate].__class__)
    assert isinstance(builder._builder.last_op.qubits.type, TensorType)
    assert builder._builder.last_op.qubits.type.shape.data[0].data == 4


def test_measure() -> None:
    builder = CircuitBuilder()
    sized_reg = builder.add_arg(QubitReg(10))

    single_bit_expected = builder.measure(Pauli.X, sized_reg[5])
    assert isinstance(single_bit_expected, MeasurementBit)
    assert single_bit_expected._is_attached

    three_bits_expected = builder.measure("Z", sized_reg[3:6])
    assert three_bits_expected.num_bits == 3
    assert three_bits_expected._is_attached

    unsized_reg = builder.add_arg(QubitReg())
    with pytest.raises(InvalidSizeError, match=re.escape("Cannot measure an unsized register.")):
        builder.measure(Pauli.X, unsized_reg)

    five_bits_expected = builder.measure(PauliAttr.Y(), [unsized_reg[i] for i in range(3, 8)])
    assert five_bits_expected.num_bits == 5
    assert five_bits_expected._is_attached

    msg = "Cannot apply measurement on empty register."
    with pytest.raises(InvalidSizeError, match=msg):
        builder.measure(Pauli.X, [])


def test_mpp() -> None:
    builder = CircuitBuilder()
    sized_reg = builder.add_arg(QubitReg(10))

    single_bit_expected = builder.mpp([Pauli.X], sized_reg[5])
    assert isinstance(single_bit_expected, MeasurementBit)
    assert single_bit_expected._is_attached

    three_bits_expected = builder.mpp(["Z", Pauli.X, PauliAttr.Y()], sized_reg[0:9])
    assert isinstance(three_bits_expected, MeasurementReg)
    assert three_bits_expected.num_bits == 3
    assert three_bits_expected._is_attached

    unsized_reg = builder.add_arg(QubitReg())
    with pytest.raises(InvalidSizeError, match=re.escape("Cannot measure an unsized register.")):
        builder.mpp([Pauli.X], unsized_reg)

    one_bit_expected = builder.mpp(
        [Pauli.X, "Y", PauliAttr.Z(), Pauli.X, Pauli.Y], [unsized_reg[i] for i in range(3, 8)]
    )
    assert isinstance(one_bit_expected, MeasurementBit)
    assert one_bit_expected._is_attached

    msg = "Cannot apply measurement on empty register."
    with pytest.raises(InvalidSizeError, match=msg):
        builder.mpp([Pauli.X], [])

    msg = (
        "Number of qubits in the provided register (2) should be a multiple of the number of "
        "provided bases (3)."
    )
    with pytest.raises(InvalidSizeError, match=re.escape(msg)):
        builder.mpp([Pauli.X, Pauli.Y, Pauli.Z], sized_reg[3:5])


# region Declaring structures
def test_declare_record() -> None:
    builder = CircuitBuilder()
    record = builder.declare_record()
    reg = builder.add_arg(QubitReg())

    record.append(builder.measure(Pauli.Z, reg[0]))
    record.append(builder.measure(Pauli.X, reg[4]))

    assert len(record) == 2
    assert isinstance(record[0], MeasurementBit)
    assert record[0]._is_attached
    assert isinstance(record[1], MeasurementBit)
    assert record[1]._is_attached


def test_declare_measurement_round() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg(1000))

    builder.measurement_round(
        builder.measure(Pauli.X, reg),
        builder.measure(Pauli.Z, reg[0]),
        builder.measure(Pauli.X, reg[2:100:2]),
        builder.mpp([Pauli.X, Pauli.Y], [reg[1], reg[3], reg[9], reg[7]]),
    )

    with pytest.raises(InvalidSizeError, match="Need at least one object in a measurement round"):
        builder.measurement_round()

    measurement = builder.measure(Pauli.X, reg)
    msg = f".*{{'{measurement.identifier}'}}.*"
    with pytest.raises(DuplicatedIdentifiersError, match=msg):
        builder.measurement_round(measurement, measurement)


def test_add_flows() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg(10))
    q0, q2, q5 = reg[0], reg[2], reg[5]

    builder.add_flow({q0: Pauli.X, reg[9]: Pauli.Z}, {q2: Pauli.X}, [])
    assert len(builder._flows) == 1
    flow = builder._flows[0]
    assert len(flow.inputs) == 2
    assert flow.inputs.get(q0) == Pauli.X
    assert len(flow.outputs) == 1
    assert flow.outputs.get(q2) == Pauli.X
    assert len(flow.measurements) == 0

    builder.add_creation_flow({q5: Pauli.Z}, [])
    assert len(builder._flows) == 2
    cflow = builder._flows[1]
    assert len(cflow.inputs) == 0
    assert len(cflow.outputs) == 1
    assert len(cflow.measurements) == 0
    assert cflow.outputs.get(q5) == Pauli.Z

    builder.add_destruction_flow({q0: Pauli.X, reg[9]: Pauli.Z}, [])
    assert len(builder._flows) == 3
    dflow = builder._flows[2]
    assert len(dflow.inputs) == 2
    assert len(dflow.outputs) == 0
    assert len(dflow.measurements) == 0
    assert dflow.inputs.get(q0) == Pauli.X

    ro = builder.measure(Pauli.X, reg[5])
    builder.add_return(ro)
    builder.add_flow({q0: "X"}, {}, [ro])
    assert len(builder._flows) == 4
    mflow = builder._flows[3]
    assert len(mflow.inputs) == 1
    assert len(mflow.outputs) == 0
    assert len(mflow.measurements) == 1
    assert mflow.measurements[0] == ro

    # Test that the flows are present in the circuit declaration.
    circuit = builder.build("circuit_with_flows")
    declaration_op = SymbolTable.lookup_symbol(circuit._module, circuit._entry_point_identifier)
    assert isinstance(declaration_op, CircuitDeclarationOp)
    assert ConcreteFlowArrayAttr.KEY in declaration_op.attributes
    concrete_flow_array_attr = declaration_op.attributes[ConcreteFlowArrayAttr.KEY]
    assert isinstance(concrete_flow_array_attr, ConcreteFlowArrayAttr)
    concrete_flows = concrete_flow_array_attr.flows.data
    assert concrete_flows == (
        ConcreteFlowAttr("+", [], "I : 10", "Z5 : 10"),
        ConcreteFlowAttr("+", [], "X0 Z9 : 10", "I : 10"),
        ConcreteFlowAttr("+", [], "X0 Z9 : 10", "X2 : 10"),
        ConcreteFlowAttr("+", [0], "X0 : 10", "I : 10"),
    )


def test_add_empty_flow_fails() -> None:
    builder = CircuitBuilder()
    with pytest.raises(ObjectNotAttachedError):
        builder.add_flow({}, {}, [MeasurementBit()])


def test_add_flow_when_unsized_argument_fails() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg())
    msg = "Cannot define flows on circuits with unsized register."
    with pytest.raises(InvalidSizeError, match=msg):
        builder.add_flow({reg[0]: Pauli.X, reg[2]: Pauli.Z}, {reg[1]: Pauli.X}, [])


def test_add_unsized_argument_when_non_empty_flow_fails() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg(3))
    builder.add_flow({reg[0]: Pauli.X, reg[2]: Pauli.Z}, {reg[1]: Pauli.X}, [])

    msg = (
        "Flow annotations and unsized registers are incompatible. Cannot add an unsized "
        "register as argument to a circuit that already contains some flow annotation."
    )
    with pytest.raises(InvalidSizeError, match=msg):
        builder.add_arg(QubitReg())


def test_add_flow_on_non_returned_measurement_fails() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg(3))
    meas = builder.measure("X", reg)
    msg = (
        "Measurements used in flow annotations should be marked as returned first by "
        "calling CircuitBuilder.add_return. Found a measurement that was not returned."
    )
    with pytest.raises(RuntimeError, match=msg):
        builder.add_flow({reg[0]: Pauli.X, reg[2]: Pauli.Z}, {reg[1]: Pauli.X}, [meas[0]])


def test_add_detector() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg())

    ro = builder.measure(Pauli.X, reg[0])
    detector = builder.detector([ro])
    assert detector.identifier is not None
    assert len(detector.measurements) == 1
    assert detector.measurements[0].identifier == ro.identifier
    assert detector.coordinates is None

    ro = builder.measure(Pauli.X, reg[0])
    detector = builder.detector([ro], (1, 1, 34))
    assert detector.identifier is not None
    assert len(detector.measurements) == 1
    assert detector.measurements[0].identifier == ro.identifier
    assert detector.coordinates == Vector(1, 1, 34)

    ros = builder.measure(Pauli.X, [reg[i] for i in range(10)])
    detector = builder.detector(ros.unpack())
    assert len(detector.measurements) == 10
    assert detector.coordinates is None


def test_detector_round() -> None:
    builder = CircuitBuilder()
    with pytest.raises(InvalidSizeError, match="Need at least one object in a detector round"):
        builder.detector_round([])

    reg = builder.add_arg(QubitReg())
    ro = builder.measure(Pauli.X, reg[0])
    detector = builder.detector([ro])
    match = f".*{{'{detector.identifier}'}}.*"
    with pytest.raises(DuplicatedIdentifiersError, match=match):
        builder.detector_round(detector, detector)

    other_measurement = builder.measure(Pauli.Z, reg[45])
    other_detector = builder.detector([ro, other_measurement])

    builder.detector_round(detector, other_detector)

    builder2 = CircuitBuilder()
    qreg2 = builder2.add_arg(QubitReg(3))
    mreg2 = builder2.measure(Pauli.X, qreg2)
    detector2 = builder2.detector(mreg2.unpack())

    with pytest.raises(DifferentBuildersError):
        builder.detector_round([detector, detector2])


def test_declare_observable_without_support() -> None:
    builder = CircuitBuilder()
    obs = builder.declare_observable()
    assert obs._is_attached
    assert obs._builder is builder._builder
    assert not obs._support


def test_declare_observable_with_support() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg(10))
    obs_on_support = builder.declare_observable(reg)
    assert obs_on_support._is_attached
    assert obs_on_support._builder is builder._builder
    assert len(obs_on_support._support) == 10

    with pytest.raises(ObjectNotAttachedError):
        builder.declare_observable(QubitReg(5))

    other_builder = CircuitBuilder()
    other_reg = other_builder.add_arg(QubitReg(4))
    with pytest.raises(DifferentBuildersError):
        builder.declare_observable(other_reg)

    unsized_reg = builder.add_arg(QubitReg())
    msg = "Cannot declare an observable on a unsized qubit register"
    with pytest.raises(InvalidSizeError, match=msg):
        builder.declare_observable(unsized_reg)


# region Context managers
@pytest.mark.skip(reason="Repeat blocks are not yet correctly implemented.")
def test_repeat() -> None:
    builder = CircuitBuilder()

    msg = r"Cannot have a negative number of repetitions. Got -1."
    with pytest.raises(InvalidSizeError, match=msg):  # noqa: SIM117
        with builder.repeat(-1):
            pass
    msg = (
        r"Cannot have a number of repetitions equal to 0 as that might "
        r"create ambiguous situations."
    )
    with pytest.raises(InvalidSizeError, match=msg):  # noqa: SIM117
        with builder.repeat(0):
            pass

    reg = builder.add_arg(QubitReg())
    builder.gate("X", reg)
    with builder.repeat(10):
        builder.gate("Z", reg[0])


@pytest.mark.skip(reason="Parallel blocks are not yet correctly implemented.")
def test_parallel() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg())
    builder.gate("X", reg)
    with builder.parallel(ParallelAlignment.BOTTOM):
        builder.gate("Z", reg[0])
        builder.gate("Z", reg[1])
        builder.gate("Z", reg[2])


def _parallel_op_of(builder: CircuitBuilder) -> ParallelOp:
    """Return the single ``qstruct.ParallelOp`` added to ``builder``."""
    parallel_ops = [op for op in builder._builder.block.ops if isinstance(op, ParallelOp)]
    assert len(parallel_ops) == 1
    return parallel_ops[0]


def _defining_op(value: SSAValue) -> Operation:
    """Return the operation defining ``value``."""
    owner = value.owner
    assert isinstance(owner, Operation)
    return owner


def _yielded_types(parallel_op: ParallelOp) -> list[list[Attribute]]:
    """Return the types yielded by each region of ``parallel_op``."""
    yields: list[list[Attribute]] = []
    for region in parallel_op.par_regions:
        yield_op = region.block.last_op
        assert isinstance(yield_op, YieldOp)
        yields.append([operand.type for operand in yield_op.operands])
    return yields


def test_parallel_measurement_escapes_its_region() -> None:
    """A value created in a region is usable after the parallel without returning it inside.

    Regions are built with a transient child builder, so anything created inside one has to be
    yielded out of it and transferred to the enclosing builder to stay usable.
    """
    builder = CircuitBuilder()
    qubits = builder.add_arg(QubitReg(2))

    with builder.parallel() as p:
        with p():
            builder.gate("H", qubits[0])
            builder.gate("X", qubits[0])
        with p():
            ro = builder.measure(Pauli.X, qubits[1])

    # ``ro`` has been transferred to the builder of the circuit, so it can be returned.
    assert builder._builder.is_managing(ro)
    builder.add_return(ro)

    parallel_op = _parallel_op_of(builder)
    # Only the measurement escapes: the temporary registers created to apply the two gates are
    # qubits, which are passed by reference and never need to leave their region.
    assert _yielded_types(parallel_op) == [[], [i1]]
    assert [res.type for res in parallel_op.res] == [i1]
    assert ro.ssa is parallel_op.res[0]

    circuit = builder.build("escaping_measurement")
    assert isinstance(circuit._result_type, MeasurementBit)


def test_parallel_does_not_yield_qubits() -> None:
    """Regions only applying gates yield nothing, as qubits are passed by reference."""
    builder = CircuitBuilder()
    p1 = builder.add_arg(QubitReg(2))
    p2 = builder.add_arg(QubitReg(2))

    with builder.parallel(ParallelAlignment.LOCKSTEP) as p:
        with p():
            builder.gate("X", p1)
            builder.gate("H", p1)
        with p():
            builder.gate("Z", p2)

    parallel_op = _parallel_op_of(builder)
    assert _yielded_types(parallel_op) == [[], []]
    assert not parallel_op.res
    builder.build("gates_only")


def test_parallel_yields_every_candidate_of_a_register_measurement() -> None:
    """Whether the user still holds a value cannot be known, so all candidates are yielded.

    A register measurement creates one ``MeasurementBit`` per measured qubit plus the register
    holding them. All of them are yielded even though only the register is handed back, and the
    redundant results are removed by the canonicalisation of ``qstruct.ParallelOp``.
    """
    builder = CircuitBuilder()
    qubits = builder.add_arg(QubitReg(3))

    with builder.parallel() as p, p():
        meas = builder.measure(Pauli.Z, qubits[0:3])

    parallel_op = _parallel_op_of(builder)
    bits_and_register = [i1, i1, i1, TensorType(i1, (3,))]
    assert _yielded_types(parallel_op) == [bits_and_register]
    assert [res.type for res in parallel_op.res] == bits_and_register
    assert meas.ssa is parallel_op.res[3]
    builder.add_return(meas)
    builder.build("register_measurement")


def test_parallel_result_can_be_indexed_after_the_parallel() -> None:
    """Indexing a value that escaped a region resolves against the parallel result."""
    builder = CircuitBuilder()
    qubits = builder.add_arg(QubitReg(2))

    with builder.parallel() as p, p():
        meas = builder.measure(Pauli.Z, qubits[0:2])

    parallel_op = _parallel_op_of(builder)
    bit = meas[0]
    # The extraction is added after the parallel, and reads the parallel result rather than the
    # value defined inside the now-closed region.
    extraction = _defining_op(bit.ssa)
    assert extraction.parent_block() is builder._builder.block
    assert extraction.operands[0] is parallel_op.res[2]
    builder.add_return(bit)
    builder.build("indexed_after")


def test_parallel_view_created_inside_a_region_is_remapped() -> None:
    """A lazily-evaluated view materialised inside a region is re-materialised outside of it.

    ``reg[0]`` does not own an SSA value: it caches the extraction it needs. When the register it
    was taken from escapes its region the cached extraction becomes stale, so it has to be redone
    against the result of the parallel operation.
    """
    builder = CircuitBuilder()
    qubits = builder.add_arg(QubitReg(2))

    with builder.parallel() as p, p():
        meas = builder.measure(Pauli.Z, qubits[0:2])
        bit = meas[0]
        stale_ssa = bit.ssa  # Materialised inside the region.

    parallel_op = _parallel_op_of(builder)
    assert bit.ssa is not stale_ssa
    extraction = _defining_op(bit.ssa)
    assert extraction.parent_block() is builder._builder.block
    assert extraction.operands[0] is parallel_op.res[2]
    builder.add_return(bit)
    builder.build("remapped_view")


def test_parallel_view_of_a_non_escaping_source_is_not_reattached() -> None:
    """A view whose source cannot escape its region is left behind with it.

    Only valid circuit results escape a region, so the temporary registers created to apply an
    operation stay on the discarded builder. A view taken from one of them cannot be resolved any
    more, so it is deliberately not transferred to the enclosing builder: leaving it behind makes
    any later use of it raise instead of silently reading a value defined in a closed region.
    """
    builder = CircuitBuilder()
    qubits = builder.add_arg(QubitReg(2))

    with builder.parallel() as p, p():
        # A ``QubitReg`` is not a valid circuit result, so this temporary cannot leave the region.
        temporary = builder._as_qubit_register([qubits[0], qubits[1]])
        builder.gate("H", temporary)
        stranded = temporary[0]

    parallel_op = _parallel_op_of(builder)
    # Qubits are passed by reference, so the temporary has nothing to yield.
    assert not parallel_op.res
    # Neither the temporary nor the view derived from it is usable after the parallel.
    assert not builder._builder.has_in_scope(temporary)
    assert not builder._builder.has_in_scope(stranded)
    builder.build("non_escaping_source")


def test_parallel_regions_do_not_observe_each_other() -> None:
    """A value created in a region is not usable from a sibling region of the same parallel."""
    builder = CircuitBuilder()
    qubits = builder.add_arg(QubitReg(2))

    def use_measurement_of_a_sibling_region() -> None:
        with builder.parallel() as p:
            with p():
                first = builder.measure(Pauli.Z, qubits[0])
            with p():
                builder.add_return(first)

    msg = "Cannot add as return a value that is managed by another builder."
    with pytest.raises(DifferentBuildersError, match=msg):
        use_measurement_of_a_sibling_region()


def test_parallel_sibling_values_are_rejected_by_scope_checks() -> None:
    """Sibling-region values are rejected by methods going through scope checks too."""
    builder = CircuitBuilder()
    qubits = builder.add_arg(QubitReg(2))

    def use_measurement_of_a_sibling_region() -> None:
        with builder.parallel() as p:
            with p():
                first = builder.measure(Pauli.Z, qubits[0])
            with p():
                builder.measurement_round(first)

    msg = "is not attached to the correct builder"
    with pytest.raises(DifferentBuildersError, match=msg):
        use_measurement_of_a_sibling_region()


def test_parallel_add_return_within_a_region_returns_from_the_circuit() -> None:
    """``add_return`` registers a return of the circuit, wherever it is called from.

    Returns are recorded on the builder that is active when ``add_return`` is called, so the ones
    declared within a region have to be handed over to the enclosing builder when it closes.
    """
    builder = CircuitBuilder()
    qubits = builder.add_arg(QubitReg(2))

    with builder.parallel() as p, p():
        ro = builder.add_return(builder.measure(Pauli.Z, qubits[0]))

    assert builder._builder.returns == (ro,)
    circuit = builder.build("returned_within_region")
    assert isinstance(circuit._result_type, MeasurementBit)


def test_parallel_observable_escapes_its_region() -> None:
    """Observables are valid circuit results, so they escape their region like measurements do."""
    builder = CircuitBuilder()
    builder.add_arg(QubitReg(2))

    with builder.parallel() as p, p():
        observable = builder.declare_observable()

    parallel_op = _parallel_op_of(builder)
    assert _yielded_types(parallel_op) == [[ObservableType()]]
    assert observable.ssa is parallel_op.res[0]
    builder.add_return(observable)
    builder.build("escaping_observable")


def test_parallel_yields_an_updated_object_only_once() -> None:
    """An object re-registered by each of its updates is only yielded once out of its region.

    The managed objects of a builder hold one entry per attachment, so an object updated in place
    (e.g., an observable including new measurements) is registered again by every update. Yielding
    one result per entry would add results carrying an already yielded SSA value to the parallel.
    """
    builder = CircuitBuilder()
    qubits = builder.add_arg(QubitReg(2))

    with builder.parallel() as p, p():
        observable = builder.declare_observable()
        observable.include([builder.measure(Pauli.Z, qubits[0])])
        observable.include([builder.measure(Pauli.Z, qubits[1])])

    parallel_op = _parallel_op_of(builder)
    # The observable is yielded once, at the position of its first attachment, even though it has
    # been registered three times: once at its declaration and once per ``include``.
    assert _yielded_types(parallel_op) == [[ObservableType(), i1, i1]]
    assert observable.ssa is parallel_op.res[0]
    builder.add_return(observable)
    builder.build("updated_observable")


def test_parallel_measurement_record_created_inside_a_region_is_usable() -> None:
    """API-only objects do not need to be yielded, but still have to be re-attached."""
    builder = CircuitBuilder()
    qubits = builder.add_arg(QubitReg(2))

    with builder.parallel() as p, p():
        record = builder.declare_record()
        first = builder.measure(Pauli.Z, qubits[0])

    assert builder._builder.is_managing(record)
    # Both the record and the measurement now belong to the builder of the circuit, so the
    # measurement can still be appended to the record.
    record.append(first)
    assert len(record) == 1


def test_parallel_flow_annotation_on_a_measurement_from_a_region() -> None:
    """A measurement that escaped a region can be used in a flow annotation."""
    builder = CircuitBuilder()
    qubits = builder.add_arg(QubitReg(2))
    builder.gate("H", qubits[0])

    with builder.parallel() as p, p():
        ro = builder.measure(Pauli.Z, qubits[0])

    builder.add_return(ro)
    builder.add_creation_flow({qubits[0]: Pauli.Z}, [ro])
    circuit = builder.build("flow_from_region")
    circuit_op = circuit._module.body.block.first_op
    assert isinstance(circuit_op, CircuitDeclarationOp)
    flows = ConcreteFlowArrayAttr.get(circuit_op)
    assert flows is not None
    assert len(flows.flows) == 1


def test_nested_parallel_measurements_escape_every_region() -> None:
    """A value created in a nested parallel escapes each of the regions enclosing it."""
    builder = CircuitBuilder()
    qubits = builder.add_arg(QubitReg(3))

    with builder.parallel() as outer:
        with outer():
            builder.gate("H", qubits[0])
        with outer(), builder.parallel() as inner:
            with inner():
                first = builder.measure(Pauli.Z, qubits[1])
            with inner():
                second = builder.measure(Pauli.Z, qubits[2])

    outer_op = _parallel_op_of(builder)
    # Both measurements are yielded out of the inner parallel, then out of the region holding it.
    assert _yielded_types(outer_op) == [[], [i1, i1]]
    inner_ops = [op for op in outer_op.par_regions[1].block.ops if isinstance(op, ParallelOp)]
    assert len(inner_ops) == 1
    assert _yielded_types(inner_ops[0]) == [[i1], [i1]]

    assert first.ssa is outer_op.res[0]
    assert second.ssa is outer_op.res[1]
    builder.add_return([first, second])
    circuit = builder.build("nested_parallels")
    assert len(circuit._result_type) == 2


def test_parallel_canonicalisation_removes_the_redundant_results() -> None:
    """The results yielded for values the user does not hold are removed by canonicalisation."""
    builder = CircuitBuilder()
    qubits = builder.add_arg(QubitReg(3))

    with builder.parallel() as p:
        with p():
            builder.gate("H", qubits[0])
        with p():
            meas = builder.measure(Pauli.Z, qubits[1:3])
    builder.add_return(meas)
    module = builder.build("canonicalised")._module

    ctx = Context()
    for dialect in (Builtin, Arith, LogAsmApi, QCore, QRef, QStruct, Tensor):
        ctx.load_dialect(dialect)
    CanonicalizePass().apply(ctx, module)

    circuit_op = module.body.block.first_op
    assert isinstance(circuit_op, CircuitDeclarationOp)
    parallel_ops = [op for op in circuit_op.body.block.ops if isinstance(op, ParallelOp)]
    assert len(parallel_ops) == 1
    # Only the measurement register is used, so the two bits backing it are no longer results.
    assert [res.type for res in parallel_ops[0].res] == [TensorType(i1, (2,))]


# endregion

# region Calls and builds


def test_build_circuit() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg(10))
    builder.gate("X", reg)
    meas = builder.measure(Pauli.Z, reg)
    builder.add_return(meas)

    circuit = builder.build("x_gate")
    assert isinstance(circuit._module.body.block.first_op, CircuitDeclarationOp)
    assert circuit._module.body.block.first_op.sym_name.data == "x_gate"
    assert len(circuit._arguments) == 1
    assert isinstance(circuit._arguments[0], QubitReg)
    assert isinstance(circuit._result_type, MeasurementReg)


def test_build_circuit_multiple_returns() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg(10))
    builder.gate("X", reg)
    meas = builder.measure(Pauli.Z, reg)
    for m in range(10):
        builder.add_return(meas[m])

    circuit = builder.build("x_gate")
    assert isinstance(circuit._module.body.block.first_op, CircuitDeclarationOp)
    assert circuit._module.body.block.first_op.sym_name.data == "x_gate"
    assert len(circuit._arguments) == 1
    assert len(circuit._result_type) == 10
    assert all(isinstance(res, MeasurementBit) for res in circuit._result_type)


def test_call_circuit() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg(10))
    builder.gate("X", reg)
    meas = builder.measure(Pauli.Z, reg)
    builder.add_return(meas)
    circuit = builder.build("x_gate")

    calling_builder = CircuitBuilder()
    sized_reg = calling_builder.add_arg(QubitReg(10))
    returns = calling_builder.call_circuit(circuit(sized_reg))
    assert isinstance(returns, MeasurementReg)
    assert returns._is_attached

    msg = re.escape("Wrong number of arguments provided. Expected 1 but got 0.")
    with pytest.raises(ArgumentSizeError, match=msg):
        circuit()

    msg = re.escape(
        "Argument 0 was declared as being of type QubitReg but got an instance of MeasurementReg."
    )
    with pytest.raises(ArgumentTypeMismatchError, match=msg):
        circuit(returns)


def test_call_circuit_no_return() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg(10))
    builder.gate("X", reg)
    circuit = builder.build("x_gate")

    calling_builder = CircuitBuilder()
    sized_reg = calling_builder.add_arg(QubitReg(10))
    returns = calling_builder.call_circuit(circuit(sized_reg))
    assert returns is None


def test_call_circuit_multiple_times() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg(10))
    builder.gate("X", reg)
    meas = builder.measure(Pauli.Z, reg)
    builder.add_return(meas)
    circuit = builder.build("x_gate")

    calling_builder = CircuitBuilder()
    sized_reg = calling_builder.add_arg(QubitReg(10))
    ret = calling_builder.call_circuit(circuit(sized_reg))
    assert isinstance(ret, MeasurementReg)
    ret2 = calling_builder.call_circuit(circuit(sized_reg))
    assert isinstance(ret2, MeasurementReg)
    calling_builder.build("multiple_x_gates")


def test_call_circuit_different_types() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg())
    builder.gate("X", reg)
    circuit = builder.build("x_gate")

    calling_builder = CircuitBuilder()
    sized_reg = calling_builder.add_arg(QubitReg(10))
    calling_builder.call_circuit(circuit(sized_reg))
    calling_builder.call_circuit(circuit(sized_reg[1:4]))
    calling_builder.call_circuit(circuit(sized_reg[5:10]))
    main_circuit = calling_builder.build("multiple_x_gates")
    circuit_op = SymbolTable.lookup_symbol(main_circuit._module, "multiple_x_gates")
    assert isinstance(circuit_op, CircuitDeclarationOp)
    # 6 casts - one before and one after each of these calls.
    assert len([op for op in circuit_op.body.block.ops if isinstance(op, CastOp)]) == 6


def test_build_circuit_with_same_name_fails() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg(10))
    builder.gate("X", reg)
    meas = builder.measure(Pauli.Z, reg)
    builder.add_return(meas)
    circuit = builder.build("x_gate")

    calling_builder = CircuitBuilder()
    sized_reg = calling_builder.add_arg(QubitReg(10))
    calling_builder.call_circuit(circuit(sized_reg))
    msg = (
        "Cannot build the circuit with identifier 'x_gate' as it already calls a circuit with "
        "that identifier."
    )
    with pytest.raises(IdentifierConflictError, match=msg):
        calling_builder.build("x_gate")


def test_identifier_clashing_fails() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg(10))
    builder.gate("X", reg)
    meas = builder.measure(Pauli.Z, reg)
    builder.add_return(meas)
    circuit = builder.build("x_gate")

    builder2 = CircuitBuilder()
    reg2 = builder2.add_arg(QubitReg(10))
    builder2.gate("Z", reg2)  # << Different gate
    meas2 = builder2.measure(Pauli.Z, reg2)
    builder2.add_return(meas2)
    circuit2 = builder2.build("x_gate")

    calling_builder = CircuitBuilder()
    sized_reg = calling_builder.add_arg(QubitReg(10))
    calling_builder.call_circuit(circuit(sized_reg))
    msg = (
        "Could not call the circuit with identifier 'x_gate': a different circuit with the same "
        "identifier has already been used and the two different definitions would clash."
    )
    with pytest.raises(IdentifierConflictError, match=msg):
        calling_builder.call_circuit(circuit2(sized_reg))


def test_identifier_clashing_with_called_subroutine_fails() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg(10))
    builder.gate("X", reg)
    meas = builder.measure(Pauli.Z, reg)
    builder.add_return(meas)
    x_gate_circuit = builder.build("x_gate")

    builder2 = CircuitBuilder()
    reg2 = builder2.add_arg(QubitReg(10))
    builder2.gate("Z", reg2)  # << Different gate
    meas2 = builder2.measure(Pauli.Z, reg2)
    builder2.add_return(meas2)
    x_gate_circuit2 = builder2.build("x_gate")

    calling_builder = CircuitBuilder()
    sized_reg = calling_builder.add_arg(QubitReg(10))
    calling_builder.call_circuit(x_gate_circuit(sized_reg))
    circuit = calling_builder.build("circuit")

    builder = CircuitBuilder()
    sized_reg = builder.add_arg(QubitReg(10))
    builder.call_circuit(x_gate_circuit2(sized_reg))
    msg = (
        "Could not call the circuit with identifier 'circuit' because it uses a declaration for "
        "'x_gate' that does not match with the declaration already present in the circuit "
        "currently being built."
    )
    with pytest.raises(IdentifierConflictError, match=msg):
        builder.call_circuit(circuit(sized_reg))


def test_call_circuit_on_wrong_registers() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg())
    builder.gate("X", reg)
    meas = builder.measure(Pauli.Z, reg[1])
    builder.add_return(meas)
    circuit = builder.build("x_gate")

    calling_builder = CircuitBuilder()
    # Note that the "reg" used in the line below comes from "builder" and not from
    # "calling_builder."
    with pytest.raises(DifferentBuildersError):
        calling_builder.call_circuit(circuit(reg))


def test_add_returns_raises_on_wrong_type() -> None:
    builder = CircuitBuilder()
    with pytest.raises(UnsupportedReturnTypeError):
        builder.add_return(1)  # type: ignore[call-overload]


def test_add_returns_sequence_of_values() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg(2))
    meas = builder.measure(Pauli.Z, reg)
    returned = builder.add_return([meas[0], meas[1]])
    assert returned == (meas[0], meas[1])
    circuit = builder.build("two_returns")
    assert len(circuit._result_type) == 2
    assert all(isinstance(res, MeasurementBit) for res in circuit._result_type)


def test_add_returns_results_of_a_called_circuit_with_multiple_returns() -> None:
    """The results of ``call_circuit`` can be forwarded to ``add_return`` in one call."""
    inner_builder = CircuitBuilder()
    inner_reg = inner_builder.add_arg(QubitReg(2))
    inner_builder.add_return(inner_builder.measure(Pauli.Z, inner_reg[0]))
    inner_builder.add_return(inner_builder.measure(Pauli.Z, inner_reg[1]))
    inner_circuit = inner_builder.build("two_returns")

    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg(2))
    results = builder.call_circuit(inner_circuit(reg))
    assert isinstance(results, tuple)
    builder.add_return(results)
    circuit = builder.build("forwards_two_returns")
    assert len(circuit._result_type) == 2


def test_add_returns_raises_on_wrong_type_in_sequence() -> None:
    builder = CircuitBuilder()
    reg = builder.add_arg(QubitReg(1))
    meas = builder.measure(Pauli.Z, reg)
    msg = "Incompatible return type provided: int."
    with pytest.raises(UnsupportedReturnTypeError, match=msg):
        builder.add_return([meas, 1])  # type: ignore[type-var]
    # Nothing should have been registered as a return value.
    assert not builder._builder.returns


def test_add_returns_raises_on_wrong_builder() -> None:
    builder = CircuitBuilder()
    other_builder = CircuitBuilder()

    qreg = builder.add_arg(QubitReg(10))
    mreg = builder.measure(Pauli.X, qreg)
    msg = "Cannot add as return a value that is managed by another builder."
    with pytest.raises(DifferentBuildersError, match=msg):
        other_builder.add_return(mreg)


def test_circuit_pre_conditions() -> None:
    circuit = Circuit[[], tuple[()]](
        ModuleOp([CircuitDeclarationOp("test", ([], []), [Block()])]), "test", ()
    )
    assert not circuit._arguments
    assert not circuit._result_type
    assert len(circuit._module.ops) == 1
    assert circuit._entry_point_identifier == "test"
    assert isinstance(circuit._module.body.block.first_op, CircuitDeclarationOp)
    assert circuit._module.body.block.first_op.sym_name.data == "test"
    assert len(circuit._module.body.block.first_op.body.blocks) == 1

    msg = re.escape("The provided arguments '(1)' contains at least one invalid argument type.")
    with pytest.raises(ArgumentError, match=msg):
        Circuit(ModuleOp([CircuitDeclarationOp("test", ([], []), [Block()])]), "test", (), 1)


def test_circuit_calling() -> None:
    circuit = Circuit[[], tuple[()]](
        ModuleOp([CircuitDeclarationOp("test", ([], []), [Block()])]), "test", ()
    )
    icirc = circuit()
    assert not icirc.called_circuits
    assert not icirc.arguments
    assert icirc.identifier == "test"
    assert icirc.declaration_op == circuit._module.body.block.first_op


def test_circuit_calling_returning_measurements() -> None:
    builder = CircuitBuilder()
    qreg = builder.add_arg(QubitReg(10))
    mreg = builder.measure(Pauli.X, qreg)
    builder.add_return(mreg[:5])
    circuit = builder.build("measure")

    builder = CircuitBuilder()
    qreg = builder.add_arg(QubitReg(10))
    _ = builder.call_circuit(circuit(qreg))
    circuit = builder.build("call_measure")

    call_measure = SymbolTable.lookup_symbol(circuit._module, "measure")
    assert isinstance(call_measure, CircuitDeclarationOp)
    assert tuple(call_measure.function_type.outputs.data) == (
        TensorType(i1, (5,)),
        TensorType(QubitType(), (10,)),
    )


def test_circuit_calling_wrong_number_of_args() -> None:
    circuit = Circuit[[], tuple[()]](
        ModuleOp([CircuitDeclarationOp("test", ([], []), [Block()])]), "Test", ()
    )
    with pytest.raises(ArgumentSizeError):
        circuit(1)  # type: ignore[call-arg]


def test_circuit_calling_wrong_args_types() -> None:
    circuit = Circuit(
        ModuleOp([CircuitDeclarationOp("test", ([], []), [Block()])]), "test", (), QubitReg(1)
    )
    msg = re.escape("The provided arguments '(1)' contains at least one invalid argument type.")
    with pytest.raises(ArgumentError, match=msg):
        circuit(1)  # type: ignore[arg-type]


EXP_CIRCUIT_STR = """Circuit('namey mcnameface' {
^bb0(%0: i64):
  %1 = "test.op"(%0) : (i64) -> i32
  log_asm_api.return %1 : i32
})"""


def test_circuit_str() -> None:
    @Builder.implicit_region([i64])
    def body(args: tuple[BlockArgument, ...]):
        i = t.TestOp(operands=[args[0]], result_types=[i32])
        ReturnOp(i)

    func_op = CircuitDeclarationOp("namey mcnameface", ([i64], [i64]), body)
    # Don't need arguments or results as block handles printing that information
    assert str(Circuit(ModuleOp([func_op]), "namey mcnameface", ())) == EXP_CIRCUIT_STR


EXP_CIRCUIT_WITH_FLOWS_STR = """Circuit('namey mcnameface' {
^bb0(%0: !qcore.qubit):
  %1 = "test.op"(%0) : (!qcore.qubit) -> !qcore.qubit
  log_asm_api.return %1 : !qcore.qubit
} with flows {
  <+:>{X0 -> X0 : 1},
  <+:>{Z0 -> Z0 : 1}
})"""


def test_circuit_with_flows_str() -> None:
    @Builder.implicit_region([QubitType()])
    def body(args: tuple[BlockArgument, ...]):
        q = t.TestOp(operands=[args[0]], result_types=[QubitType()])
        ReturnOp(q)

    func_op = CircuitDeclarationOp("namey mcnameface", ([QubitType()], [QubitType()]), body)
    func_op.attributes[ConcreteFlowArrayAttr.KEY] = ConcreteFlowArrayAttr(
        [ConcreteFlowAttr(True, [], "X0:1", "X0:1"), ConcreteFlowAttr(True, [], "Z0:1", "Z0:1")]
    )
    # Don't need arguments or results as block handles printing that information
    assert str(Circuit(ModuleOp([func_op]), "namey mcnameface", ())) == EXP_CIRCUIT_WITH_FLOWS_STR


EXP_NESTED_SUBROUTINE_STR = """Circuit('namey mcnameface1' {
^bb0(%0: i64):
  %1, %2 = "test.op"(%0) : (i64) -> (i32, i64)
  %3 = log_asm_api.call @"namey mcnameface2"(%2) : (i64) -> i32
  %4 = log_asm_api.call @"namey mcnameface3"(%2) : (i64) -> i32
  log_asm_api.return %1 : i32
} which calls {
  'namey mcnameface2' {
  ^bb1(%5: i64):
    %6 = "test.op"(%5) : (i64) -> i32
    log_asm_api.return %6 : i32
  },
  'namey mcnameface3' {
  ^bb2(%7: i64):
    %8 = "test.op"(%7) : (i64) -> i32
    %9 = log_asm_api.call @"namey mcnameface2"(%7) : (i64) -> i32
    log_asm_api.return %8 : i32
  }
})"""


def test_nested_circuit_str() -> None:
    @Builder.implicit_region([i64])
    def body1(args: tuple[BlockArgument, ...]):
        i = t.TestOp(operands=[args[0]], result_types=[i32, i64])
        CallOp("namey mcnameface2", (i.res[1],), (i32,))
        CallOp("namey mcnameface3", (i.res[1],), (i32,))
        ReturnOp(i.res[0])

    @Builder.implicit_region([i64])
    def body2(args: tuple[BlockArgument, ...]):
        i = t.TestOp(operands=[args[0]], result_types=[i32])
        ReturnOp(i)

    @Builder.implicit_region([i64])
    def body3(args: tuple[BlockArgument, ...]):
        i = t.TestOp(operands=[args[0]], result_types=[i32])
        CallOp("namey mcnameface2", args, (i32,))
        ReturnOp(i)

    func_op1 = CircuitDeclarationOp("namey mcnameface1", ([i64], [i64]), body1)
    func_op2 = CircuitDeclarationOp("namey mcnameface2", ([i64], [i64]), body2)
    func_op3 = CircuitDeclarationOp("namey mcnameface3", ([i64], [i64]), body3)
    # Don't need arguments or results as block handles printing that information
    assert (
        str(Circuit(ModuleOp([func_op1, func_op2, func_op3]), "namey mcnameface1", ()))
        == EXP_NESTED_SUBROUTINE_STR
    )


def test_circuit_instantiation_with_kwargs() -> None:
    @Builder.implicit_region([i64])
    def body(args: tuple[BlockArgument, ...]):
        i = t.TestOp(operands=[args[0]], result_types=[i32])
        ReturnOp(i)

    func_op = CircuitDeclarationOp("namey mcnameface", ([i64], [i64]), body)
    msg = re.escape(
        "Cannot instantiate a Circuit with keyword arguments (kwargs). "
        "The following keyword arguments were found: 'hello'."
    )
    with pytest.raises(RuntimeError, match=msg):
        Circuit(ModuleOp([func_op]), "namey mcnameface", (), hello="world")


def test_circuit_calling_with_kwargs() -> None:
    @Builder.implicit_region([i64])
    def body(args: tuple[BlockArgument, ...]):
        i = t.TestOp(operands=[args[0]], result_types=[i32])
        ReturnOp(i)

    func_op = CircuitDeclarationOp("namey mcnameface", ([i64], [i64]), body)
    circuit = Circuit(ModuleOp([func_op]), "namey mcnameface", ())
    msg = re.escape(
        "Cannot call a Circuit with keyword arguments (kwargs). "
        "The following keyword arguments were found: 'hello'."
    )
    with pytest.raises(RuntimeError, match=msg):
        circuit(hello="world")  # type: ignore[call-arg]
