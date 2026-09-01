"""Tests for the logical assembly API"""

import re
from copy import deepcopy
from typing import Any

import pytest
from xdsl.builder import Builder
from xdsl.dialects import test as t
from xdsl.dialects.builtin import I1, IntegerType, ModuleOp, NoneAttr, TensorType, i1, i32, i64
from xdsl.dialects.func import FuncOp
from xdsl.ir import BlockArgument
from xdsl.traits import SymbolTable
from xdsl.utils.hints import isa

from deltakit_compile.dialects import func
from deltakit_compile.dialects import log_asm_api as api
from deltakit_compile.dialects.logical_assembly import (
    GrowOp,
    MeasStabOp,
    MeasureOp,
    MoveOp,
    OrientationEnum,
    PatchDeclarationOp,
    PlacementAttr,
    PrepareOp,
    RotatedPlanarPatchType,
    RotateOp,
    ShrinkOp,
    StepOp,
)
from deltakit_compile.dialects.qcore import QubitType
from deltakit_compile.dialects.qstruct import OutputOp
from deltakit_compile.frontend.common._builder import OperationBuilder
from deltakit_compile.frontend.common._circuit import CircuitBuilder
from deltakit_compile.frontend.common._classical_expr import Result
from deltakit_compile.frontend.common._exceptions import (
    ArgumentError,
    DifferentBuildersError,
    IdentifierConflictError,
    InvalidSizeError,
    UnsupportedReturnTypeError,
)
from deltakit_compile.frontend.common._measurements import MeasurementReg
from deltakit_compile.frontend.common._pauli import Pauli
from deltakit_compile.frontend.common._qubit_reg import Qubit, QubitReg
from deltakit_compile.frontend.common._vector import Vector
from deltakit_compile.frontend.logasm import (
    InstantiatedLogAsmSubroutine,
    LogAsmBuilder,
    LogAsmProgram,
    LogAsmSubroutine,
    RotatedPlanarPatch,
)
from deltakit_compile.shared.patch.exceptions import UnplacedPatchError
from tests.unit.frontend.conftest import (
    add_to_builder_with_fake_ssa,
    number_of_operations_of_type_in_block,
)

# region: API example tests from confluence page

# TODO: All of these tests are simply based on the examples of API usage and should be
# Cleaned up and made to more thoroughly test all the feature of the API once it is more stable.


@pytest.mark.xfail(
    reason="Features using context-managers ('with ...:') are not yet implemented in the API."
)
def test_ex1():
    """Test based on API Examples document"""
    d = 5
    builder = LogAsmBuilder()
    p0 = builder.declare_patch(RotatedPlanarPatch(d, d))
    p1 = builder.declare_patch(RotatedPlanarPatch(d, d))

    p0.prepare("Z")
    p1.prepare("Z")
    p0.measure_stabilisers(8 * d)
    p1.measure_stabilisers(8 * d)

    b0 = p0.measure("Z")
    with builder.if_(b0 == 1):
        p1.transversal("X")

    _b1 = p1.measure("Z")

    program = builder.build_program()
    assert isinstance(program, LogAsmProgram)


@pytest.mark.xfail(
    reason="Features using context-managers ('with ...:') are not yet implemented in the API."
)
def test_ex1_subroutine():
    """Test based on API Examples document"""
    d = 5
    builder = LogAsmBuilder()
    p0 = builder.add_arg(RotatedPlanarPatch(d, d))
    p1 = builder.add_arg(RotatedPlanarPatch(d, d))

    p0.prepare("Z")
    p1.prepare("Z")
    p0.measure_stabilisers(8 * d)
    p1.measure_stabilisers(8 * d)

    b0 = p0.measure("Z")
    with builder.if_(b0 == 1):
        p1.transversal("X")

    _b1 = p1.measure("Z")

    subroutine = builder.build_subroutine("memory_then_transversal")
    assert isinstance(subroutine, LogAsmSubroutine)


def test_example_patches():
    """Test based on API Examples document"""
    builder = LogAsmBuilder()
    # QubitReg (base type for patches) does not have any patch methods
    _qubits = builder.add_arg(QubitReg(3))

    # More specific patch types will have more specific methods available
    patch = builder.add_arg(RotatedPlanarPatch(3, 3, vertical_z=True))
    patch.prepare("Z")
    patch.measure_stabilisers(5)
    patch.measure("Z")

    assert isinstance(patch[2], Qubit)
    assert isinstance(patch[2:5], QubitReg)
    assert len(patch[2:5]) == 3

    builder.build_subroutine("memory_Z")


def test_example_patch_location():
    """Test based on API Examples document"""
    builder = LogAsmBuilder()

    patch = builder.add_arg(RotatedPlanarPatch(3, 3, location=(5, 5)))
    assert patch.location == (5, 5)

    # Set the location of the patch using a specific qubit as the origin
    patch2 = builder.add_arg(RotatedPlanarPatch(3, 3, location=(5, 6), origin=Vector(0, 1)))
    assert patch2.location == patch.location

    patch3 = builder.add_arg(QubitReg(2, qubit_locations=[(1, 1), (1, 2)]))
    assert patch3.num_qubits == 2
    assert patch3.qubit_locations is not None
    assert patch3.qubit_locations == ((1, 1), (1, 2))

    patch = builder.add_arg(RotatedPlanarPatch(3, 3, location=(5, 5)))
    # These will be come out as the same qubit at compile time
    qubit = patch.at_location(6, 6)
    rel_qubit = patch.at_relative_location(1, 1)
    assert isinstance(qubit, Qubit)
    assert isinstance(rel_qubit, Qubit)
    assert qubit.location == rel_qubit.location

    builder.build_subroutine("test")


def test_example_patch_operations_core():
    """Test based on API Examples document"""
    builder = LogAsmBuilder()
    patch = builder.declare_patch(RotatedPlanarPatch(5, 5, location=(3, 4)))

    patch.prepare(basis="Z")
    patch.measure_stabilisers(min_rounds=5)
    _corrected_logical = patch.measure(basis="Z")
    patch.transversal("X")

    builder.build_subroutine("test")


def test_example_patch_operations_multi_patch():
    """Test based on API Examples document"""
    builder = LogAsmBuilder()

    lp0 = builder.declare_patch(RotatedPlanarPatch(3, 3, location=(0, 0)))
    lp1 = builder.declare_patch(RotatedPlanarPatch(3, 3, location=(4, 0)))

    lp0.prepare("Z")
    lp1.prepare("Z")

    _xx_logical = builder.multi_pauli_measure([lp0, lp1], pauli_bases=["X", "X"])

    bridge = builder.declare_patch(RotatedPlanarPatch(1, 3, location=(3, 0)))
    _xx_logical2 = builder.multi_pauli_measure(
        [lp0, lp1], [bridge], rounds=3, pauli_bases=["X", "X"]
    )

    lp2 = builder.declare_patch(RotatedPlanarPatch(3, 3, location=(-4, 0)))
    lp2.prepare("Z")

    bridge1 = builder.declare_patch(RotatedPlanarPatch(1, 3, location=(-1, 0)))
    _xxx_logical = builder.multi_pauli_measure(
        [lp0, lp1, lp2], [bridge, bridge1], pauli_bases=["X", "X", "X"]
    )

    builder.transversal("CX", [lp0, lp1])

    builder.build_subroutine("test")


def test_example_size_and_location():
    """Test based on API Examples document"""
    builder = LogAsmBuilder()

    p0 = builder.declare_patch(RotatedPlanarPatch(3, 3, location=(0, 0)))
    p0.prepare("Z")

    p0.grow(top=1, right=1)  # Grows the patch by distance 1
    assert p0._width == 4
    assert p0._height == 4
    assert p0.location == (0, 0)
    assert p0._vertical_z

    p0.shrink(bottom=1)  # Push the bottom patch up by 1 to make it rectangular
    assert p0._width == 4
    assert p0._height == 3
    assert p0.location == (0, 1)
    assert p0._vertical_z

    # Move the patch horizontally by 4 using an automatically defined straight bridge
    p0.move(offset=(4, 0))
    assert p0._width == 4
    assert p0._height == 3
    assert p0.location == (4, 1)
    assert p0._vertical_z
    # Move back
    p0.move(offset=(-4, 0))
    assert p0._width == 4
    assert p0._height == 3
    assert p0.location == (0, 1)
    assert p0._vertical_z

    # The same move with an explicitly declared bridge
    bridge = builder.declare_patch(RotatedPlanarPatch(1, 3, location=(4, 1)))
    p0.move(offset=(5, 0), bridges=[bridge])
    assert p0._width == 4
    assert p0._height == 3
    assert p0.location == (5, 1)
    assert p0._vertical_z

    p0.step(offset=(1, 0))
    assert p0._width == 4
    assert p0._height == 3
    assert p0.location == (6, 1)
    assert p0._vertical_z

    p0.rotate(offset=(0, 3))  # Rotate this d3 90 degrees, moving it upwards
    assert p0._width == 3
    assert p0._height == 4
    assert p0.location == (6, 4)
    assert not p0._vertical_z

    builder.build_subroutine("test")


def test_example_parallelism():
    """Test based on API Examples document"""
    builder = LogAsmBuilder()

    lp0 = builder.declare_patch(RotatedPlanarPatch(3, 3, location=(0, 0)))
    lp1 = builder.declare_patch(RotatedPlanarPatch(3, 3, location=(4, 0)))

    lp0.prepare("X")
    builder.barrier(lp0, lp1)  # prevent ops using lp0 or lp1 from crossing this barrier
    lp1.prepare("X")

    builder.transversal("CX", [lp0, lp1])

    # These are put in parallel
    lp0.measure_stabilisers(min_rounds=5)  # This will be lengthened to 10
    lp1.measure_stabilisers(min_rounds=10)

    builder.transversal("CX", [lp0, lp1])

    builder.build_subroutine("test")


@pytest.mark.xfail(
    reason="Features using context-managers ('with ...:') are not yet implemented in the API."
)
def test_example_control_flow():
    """Test based on API Examples document"""
    builder = LogAsmBuilder()
    lp0 = builder.declare_patch(RotatedPlanarPatch(3, 3, location=(0, 0)))
    lp1 = builder.declare_patch(RotatedPlanarPatch(3, 3, location=(4, 0)))

    zz = builder.multi_pauli_measure([lp0, lp1], pauli_bases=["Z", "Z"])
    with builder.if_(zz == 1):
        lp1.transversal("H")
    with builder.else_():
        lp1.transversal("X")

    log0 = lp0.measure("X")
    with builder.while_(log0 != 0):
        log0 = lp0.measure("X")

    with builder.for_(0, 10, 2):  # start, exclusive stop, step
        log0 = lp0.measure("X")

    builder.build_subroutine("test")


@pytest.mark.xfail(
    reason="Features using context-managers ('with ...:') are not yet implemented in the API."
)
def test_example_control_flow_optimised():
    """Test based on API Examples document"""
    builder = LogAsmBuilder()
    lp0 = builder.declare_patch(RotatedPlanarPatch(3, 3, location=(0, 0)))
    log0 = lp0.measure("X")

    # This control flow will be entirely optimised away as both if and else will
    # be empty from the compiler's point of view
    with builder.if_(log0 == 0):
        var = 0
    with builder.else_():
        var = 10

    assert var == 10  # Prints 10 when running this Python file


@pytest.mark.xfail(reason="Use of unsized patches is not supported.")
def test_example_subroutines():
    """Test based on API Examples document"""
    # Build a subroutine
    builder = LogAsmBuilder()
    patch = builder.add_arg(RotatedPlanarPatch())
    patch.measure_stabilisers(5)
    my_subroutine = builder.build_subroutine("test")

    # Build a program that calls the subroutine
    builder = LogAsmBuilder()
    patch = builder.declare_patch(RotatedPlanarPatch(3, 3))
    builder.call_subroutine(my_subroutine(patch))
    _main_program = builder.build_program()


def test_example_subroutine_multiple_args():
    """Test based on API Examples document"""
    builder = LogAsmBuilder()
    patch, log = builder.add_arg(RotatedPlanarPatch(5, 5)), builder.add_arg(Result)

    log2 = patch.measure("Z")
    builder.add_return(log2)
    my_subroutine = builder.build_subroutine("subroutine")

    builder = LogAsmBuilder()
    patch = builder.declare_patch(RotatedPlanarPatch(5, 5))

    log = patch.measure("Z")
    _returned_log2 = builder.call_subroutine(my_subroutine(patch, log))
    _main_program = builder.build_subroutine("main")


def test_example_subroutine_multiple_specific_args():
    """Test based on API Examples document"""
    builder = LogAsmBuilder()
    # Will accept any patch
    _patch = builder.add_arg(QubitReg())

    # Will only accept a 3x3 rotated planar patch
    _patch = builder.add_arg(RotatedPlanarPatch(3, 3))

    _sub_routine = builder.build_subroutine("subroutine")


def test_example_subroutine_custom_function():
    """Test based on API Examples document"""

    def build_z_memory(distance: int) -> LogAsmSubroutine[[RotatedPlanarPatch], tuple[()]]:
        """Build a subroutine that executes qmem on a rotated planar patch of the
        provided distance."""
        builder = LogAsmBuilder()
        patch = builder.add_arg(RotatedPlanarPatch(distance, distance))
        patch.prepare("Z")
        patch.measure_stabilisers(3 * distance)
        patch.measure("Z")
        return builder.build_subroutine("z_memory")

    builder = LogAsmBuilder()
    patch = builder.add_arg(RotatedPlanarPatch(99, 99))
    routine = build_z_memory(99)
    builder.call_subroutine(routine(patch))
    builder.build_subroutine("main")


def test_example_program_returns() -> None:
    d = 5
    builder = LogAsmBuilder()
    p0 = builder.declare_patch(RotatedPlanarPatch(d, d, location=(0, 0)))
    p1 = builder.declare_patch(RotatedPlanarPatch(d, d, location=(d + 1, 0)))
    p0.prepare("Z")
    p1.prepare("Z")
    b0 = p1.measure("Z")
    b1 = p1.measure("Z")
    builder.add_return(b0)
    builder.add_return(b1)
    program = builder.build_program()
    assert isinstance(program, LogAsmProgram)


# endregion

# region Patch / Register


def test_declare_register() -> None:
    builder = LogAsmBuilder()

    qreg = builder.declare_patch(QubitReg(10))
    assert qreg.num_qubits == 10
    assert qreg.qubit_locations is None

    locs = tuple(Vector(i, i) for i in range(10))
    qreg = builder.declare_patch(QubitReg(10, qubit_locations=locs))
    assert qreg.num_qubits == 10
    assert qreg.qubit_locations is not None
    assert qreg.qubit_locations == locs

    msg = re.escape("Cannot declare an unsized register in a LogASM context.")
    with pytest.raises(InvalidSizeError, match=msg):
        builder.declare_patch(QubitReg())


def test_declare_rotated_patch() -> None:
    builder = LogAsmBuilder()

    patch = builder.declare_patch(RotatedPlanarPatch(5, 5))
    assert patch._width == 5
    assert patch._height == 5
    assert patch.num_qubits == 2 * 5 * 5 - 1
    assert patch.qubit_locations is None


def test_declare_rotated_patch_with_one_even_dimension() -> None:
    builder = LogAsmBuilder()
    patch = builder.declare_patch(RotatedPlanarPatch(23, 90, location=Vector(3, 5)))
    assert patch._width == 23
    assert patch._height == 90
    assert patch.num_qubits == 2 * 23 * 90 - 1
    assert patch.qubit_locations is not None
    assert len(patch.qubit_locations) == 2 * 23 * 90 - 1
    assert patch.location == Vector(3, 5)


def test_declare_unsized_rotated_patch() -> None:
    builder = LogAsmBuilder()
    with pytest.raises(
        NotImplementedError, match="Unsized patches are not supported yet in the LogASM API"
    ):
        builder.declare_patch(RotatedPlanarPatch())


@pytest.mark.xfail(reason="Unsized patches are not supported")
def test_unsized_rotated_patch_location() -> None:
    unsized_patch = RotatedPlanarPatch()
    with pytest.raises(ValueError, match="Unsized patches cannot have a location"):
        _ = unsized_patch.location


def test_rotated_patch_location() -> None:
    unlocated_patch = RotatedPlanarPatch(3, 3)
    located_patch = RotatedPlanarPatch(3, 3, location=Vector(0, 0))
    with pytest.raises(
        UnplacedPatchError,
        match=re.escape("Patch has no location. Provide a location at patch construction."),
    ):
        _ = unlocated_patch.location

    assert located_patch.location == Vector(0, 0)


def test_rotated_patch_at_location() -> None:
    builder = OperationBuilder()
    loc = Vector(3, 5)
    patch = add_to_builder_with_fake_ssa(builder, RotatedPlanarPatch(3, 3, location=loc))
    assert patch.location == loc

    offset = Vector(1, 1)
    qloc = loc + offset
    qubit = patch.at_location(qloc)
    assert qubit.location == qloc

    rel_qubit = patch.at_relative_location(offset)
    assert rel_qubit.location == qloc

    unlocated_patch = add_to_builder_with_fake_ssa(builder, RotatedPlanarPatch(3, 3))
    with pytest.raises(
        UnplacedPatchError,
        match=re.escape("Patch has no location. Provide a location at patch construction."),
    ):
        _ = unlocated_patch.location
    with pytest.raises(
        UnplacedPatchError,
        match="RotatedPlanarPatch instance does not contain any location information",
    ):
        _ = unlocated_patch.at_location(qloc)
    with pytest.raises(UnplacedPatchError, match=re.escape("Patch does not have location data.")):
        _ = unlocated_patch.at_relative_location(offset)


# endregion


# region Add arguments


def test_add_arg() -> None:
    builder = LogAsmBuilder()
    patch = builder.add_arg(RotatedPlanarPatch(5, 5))
    patch.prepare("X")
    patch.measure_stabilisers(5)
    meas = patch.measure("X")
    builder.add_return(meas)

    circuit = builder.build_subroutine("measure_X")
    assert len(circuit._arguments) == 1
    assert isinstance(circuit._results, Result)


def test_add_arg_already_attached() -> None:
    builder = LogAsmBuilder()
    patch = builder.add_arg(RotatedPlanarPatch(5, 5))

    other_builder = LogAsmBuilder()
    msg = f"Cannot use an already used {RotatedPlanarPatch.__name__} as an argument"
    with pytest.raises(ValueError, match=msg):
        other_builder.add_arg(patch)


def test_add_multiple_args() -> None:
    builder = LogAsmBuilder()
    patch = builder.add_arg(RotatedPlanarPatch(5, 5))
    res = builder.add_arg(Result)
    patch.prepare("X")
    patch.measure_stabilisers(5)
    meas = patch.measure("X")

    builder.add_return(meas)
    builder.add_return(res)

    circuit = builder.build_subroutine("measure_X")
    assert len(circuit._arguments) == 2
    assert isinstance(circuit._arguments[0], RotatedPlanarPatch)
    assert isinstance(circuit._arguments[1], Result)
    assert len(circuit._results) == 2
    assert isinstance(circuit._results[0], Result)
    assert isinstance(circuit._results[1], Result)


@pytest.mark.xfail(reason="Use of unsized patches is not supported.")
def test_add_unsized_patch_arg() -> None:
    builder = LogAsmBuilder()
    patch = builder.add_arg(RotatedPlanarPatch())
    patch.prepare("X")
    patch.measure_stabilisers(5)
    meas = patch.measure("X")
    builder.add_return(meas)

    circuit = builder.build_subroutine("measure_X")
    assert len(circuit._arguments) == 1
    assert isinstance(circuit._results, Result)


def test_add_already_attached_args() -> None:
    b = LogAsmBuilder()
    attached_qreg = b.add_arg(QubitReg(10))

    builder = LogAsmBuilder()
    msg = re.escape("Cannot use an already used QubitReg as an argument.")
    with pytest.raises(ValueError, match=msg):
        builder.add_arg(attached_qreg)


def test_add_arg_to_module_level_fails():
    d = 5
    builder = LogAsmBuilder()
    _p0 = builder.add_arg(RotatedPlanarPatch(d, d))
    with pytest.raises(RuntimeError, match=re.escape("Top level programs cannot have arguments.")):
        builder.build_program()


def test_rotated_patch_from_attribute() -> None:
    patch = RotatedPlanarPatch.from_attribute(
        RotatedPlanarPatchType((3, 3), PlacementAttr((0, 0), OrientationEnum.VERTICAL_Z))
    )
    assert patch.is_sized
    assert patch.location == (0, 0)
    assert patch._vertical_z

    msg = re.escape(
        "Cannot create a RotatedPlanarPatch instance from a RotatedPlanarPatchType that does not "
        "have an observable orientation."
    )
    with pytest.raises(RuntimeError, match=msg):
        RotatedPlanarPatch.from_attribute(RotatedPlanarPatchType((3, 3), placement=None))


# endregion

# region Return values


def test_returns_one_bit() -> None:
    builder = LogAsmBuilder()
    patch = builder.declare_patch(RotatedPlanarPatch(5, 5))
    patch.prepare("X")
    patch.measure_stabilisers(5)
    meas = patch.measure("X")
    builder.add_return(meas)

    circuit = builder.build_subroutine("returns_one_bit")
    assert len(circuit._arguments) == 0
    assert isinstance(circuit._results, Result)


def test_add_qubit_returns_to_module_level_fails():
    d = 5
    builder = LogAsmBuilder()
    _p0 = builder.declare_patch(RotatedPlanarPatch(d, d))
    msg = "Incompatible return type provided: RotatedPlanarPatch."
    with pytest.raises(UnsupportedReturnTypeError, match=msg):
        builder.add_return(_p0)


def test_add_classical_bit_returns():
    cbuilder = CircuitBuilder()
    qreg = cbuilder.add_arg(QubitReg(17))
    mreg = cbuilder.measure("Z", qreg)
    cbuilder.add_return(mreg)
    circuit = cbuilder.build("returns_bits")

    builder = LogAsmBuilder()
    p0 = builder.declare_patch(RotatedPlanarPatch(3, 3))
    bits = builder.call_circuit(circuit(p0))
    assert isinstance(bits, MeasurementReg)
    assert bits.num_bits == 17
    builder.add_return(bits)
    builder.add_return(bits[0])

    subroutine = builder.build_subroutine("subroutine_returns_bits")
    outputs = subroutine.func_op.function_type.outputs.data
    assert len(outputs) == 2
    mreg, bit = outputs
    assert TensorType.constr(element_type=i1).verifies(mreg)
    shape = mreg.get_shape()
    assert shape == (17,)
    assert bit == IntegerType(1)

    program = builder.build_program()
    outputs = next(op for op in program.module.ops if isinstance(op, OutputOp)).arguments
    assert len(outputs) == 18
    assert all(isa(out.type, I1) for out in outputs)


def test_add_returns_results_of_a_called_circuit_with_multiple_returns() -> None:
    """The results of ``call_circuit`` can be forwarded to ``add_return`` in one call."""
    cbuilder = CircuitBuilder()
    qreg = cbuilder.add_arg(QubitReg(2))
    cbuilder.add_return(cbuilder.measure("Z", qreg[0]))
    cbuilder.add_return(cbuilder.measure("Z", qreg[1]))
    circuit = cbuilder.build("two_returns")

    builder = LogAsmBuilder()
    patch = builder.declare_patch(QubitReg(2))
    results = builder.call_circuit(circuit(patch))
    assert isinstance(results, tuple)
    assert len(results) == 2
    builder.add_return(results)

    program = builder.build_program()
    outputs = next(op for op in program.module.ops if isinstance(op, OutputOp)).arguments
    assert len(outputs) == 2
    assert all(isa(out.type, I1) for out in outputs)


def test_add_returns_raises_on_wrong_type() -> None:
    builder = LogAsmBuilder()
    msg = "Incompatible return type provided: int."
    with pytest.raises(UnsupportedReturnTypeError, match=msg):
        builder.add_return(1)  # type: ignore[arg-type]
    with pytest.raises(UnsupportedReturnTypeError, match=msg):
        builder.add_return([1])  # type: ignore[list-item]
    # Nothing should have been registered as a return value.
    assert not builder._builder.returns


# endregion

# region Measure stabilisers


def test_measure_stabiliser() -> None:
    builder = LogAsmBuilder()
    p0 = builder.declare_patch(RotatedPlanarPatch(5, 5, location=Vector(0, 0)))

    p0.measure_stabilisers()
    meas_stab_op = builder._builder.last_op
    assert isinstance(meas_stab_op, MeasStabOp)
    assert meas_stab_op.min_rounds.data == 5

    for mr in [0, 1, 2, 10, 100]:
        p0.measure_stabilisers(mr)
        meas_stab_op = builder._builder.last_op
        assert isinstance(meas_stab_op, MeasStabOp)
        assert meas_stab_op.min_rounds.data == mr


# endregion

# region Move


def test_move() -> None:
    builder = LogAsmBuilder()
    p0 = builder.declare_patch(RotatedPlanarPatch(5, 5, location=Vector(0, 0)))

    p0_before_move = deepcopy(p0)
    p0.move((0, 0))
    move_op = builder._builder.last_op
    assert isinstance(move_op, MoveOp)
    assert not move_op.bridge_patches
    assert len(move_op.result_types) == 1
    assert p0._type_info == p0_before_move._type_info
    assert move_op.result_types[0] == p0._type_info


def test_move_with_bridge() -> None:
    builder = LogAsmBuilder()
    p0 = builder.declare_patch(RotatedPlanarPatch(5, 5, location=Vector(0, 0)))
    bridge = builder.declare_patch(RotatedPlanarPatch(2, 5, location=Vector(5, 0)))

    p0.prepare("X")
    p0.move((7, 0), bridges=[bridge])

    # Check the move operation
    move_ops = [op for op in builder._builder.block.ops if isinstance(op, MoveOp)]
    assert len(move_ops) == 1
    move_op = move_ops[0]
    assert len(move_op.bridge_patches) == 1
    assert len(move_op.result_types) == 1

    # Check that the bridge is not re-declared, but is correctly prepared and measured.
    declare_ops = [op for op in builder._builder.block.ops if isinstance(op, PatchDeclarationOp)]
    prepare_ops = [op for op in builder._builder.block.ops if isinstance(op, PrepareOp)]
    measure_ops = [op for op in builder._builder.block.ops if isinstance(op, MeasureOp)]
    assert len(declare_ops) == 2  # patch & bridge declared only once.
    assert len(prepare_ops) == 2  # patch & bridge both prepared.
    assert len(measure_ops) == 1


def test_move_with_several_bridges() -> None:
    builder = LogAsmBuilder()
    p0 = builder.declare_patch(RotatedPlanarPatch(5, 5, location=Vector(0, 0)))
    hbridge = builder.declare_patch(RotatedPlanarPatch(5, 5, location=Vector(5, 0)))
    vbridge = builder.declare_patch(RotatedPlanarPatch(5, 1, location=Vector(5, 5)))

    p0.prepare("X")
    p0.move((5, 6), bridges=[hbridge, vbridge])

    # Check the move operation
    move_ops = [op for op in builder._builder.block.ops if isinstance(op, MoveOp)]
    assert len(move_ops) == 1
    move_op = move_ops[0]
    assert len(move_op.bridge_patches) == 2
    assert len(move_op.result_types) == 1

    # Check that the bridges are not re-declared, but are correctly prepared and measured.
    declare_ops = [op for op in builder._builder.block.ops if isinstance(op, PatchDeclarationOp)]
    prepare_ops = [op for op in builder._builder.block.ops if isinstance(op, PrepareOp)]
    measure_ops = [op for op in builder._builder.block.ops if isinstance(op, MeasureOp)]
    assert len(declare_ops) == 3  # patch & bridges declared only once.
    assert len(prepare_ops) == 3  # patch & bridges prepared.
    assert len(measure_ops) == 2


@pytest.mark.xfail(reason="Unsized patches are not supported")
def test_move_operation_on_unsized_patch_raises() -> None:
    builder = LogAsmBuilder()
    p0 = builder.add_arg(RotatedPlanarPatch())
    with pytest.raises(InvalidSizeError):
        p0.move((0, 0))


def test_move_operation_with_unconnected_bridge_raises() -> None:
    builder = LogAsmBuilder()
    p0 = builder.declare_patch(RotatedPlanarPatch(5, 5, location=Vector(0, 0)))
    disconnected_bridge = builder.declare_patch(RotatedPlanarPatch(5, 5, location=Vector(10, 0)))
    msg = "Could not find a bridge connecting the moved patch."
    with pytest.raises(RuntimeError, match=msg):
        p0.move((5, 0), bridges=[disconnected_bridge])


# endregion

# region Step operation


@pytest.mark.parametrize("offset", [Vector(0, 0), Vector(-1, -1), Vector(1, 1)])
def test_step_operation(offset: Vector[int]) -> None:
    builder = LogAsmBuilder()
    p0 = builder.declare_patch(RotatedPlanarPatch(5, 5, location=Vector(0.0, 0.0)))

    p0.step(offset)
    step_op = builder._builder.last_op
    assert isinstance(step_op, StepOp)
    assert len(step_op.result_types) == 1
    assert isinstance(step_op.result_types[0], RotatedPlanarPatchType)
    assert not isinstance(step_op.result_types[0].placement, NoneAttr)
    res_location = [loc.value.data for loc in step_op.result_types[0].placement.location.data]
    assert pytest.approx(res_location) == offset


# endregion

# region Rotate operation


@pytest.mark.parametrize("offset", [Vector(0, 0), Vector(-1, -1), Vector(1, 1), Vector(5, 0)])
def test_rotate_operation(offset: Vector[int]) -> None:
    builder = LogAsmBuilder()
    p0 = builder.declare_patch(RotatedPlanarPatch(5, 5, location=Vector(0, 0), vertical_z=True))

    p0.rotate(offset)
    assert not p0._vertical_z
    rotate_op = builder._builder.last_op
    assert isinstance(rotate_op, RotateOp)
    assert rotate_op.rounds.data == 5
    assert len(rotate_op.result_types) == 1
    res = rotate_op.result_types[0]
    assert isinstance(res, RotatedPlanarPatchType)
    assert not isinstance(res.placement, NoneAttr)
    res_location = [loc.value.data for loc in res.placement.location.data]
    assert pytest.approx(res_location) == offset
    assert rotate_op.res == p0.ssa


@pytest.mark.parametrize("offset", [Vector(0, 0), Vector(-1, -1), Vector(1, 1), Vector(5, 0)])
def test_rotate_operation_with_bridge(offset: Vector[int]) -> None:
    builder = LogAsmBuilder()
    p0 = builder.declare_patch(RotatedPlanarPatch(5, 5, location=Vector(0, 0), vertical_z=False))
    b0 = builder.declare_patch(RotatedPlanarPatch(5, 5, location=Vector(5, 0)))

    p0.rotate(offset, bridges=[b0])
    assert p0._vertical_z
    rotate_op = builder._builder.last_op
    assert isinstance(rotate_op, RotateOp)
    assert rotate_op.rounds.data == 5
    assert len(rotate_op.result_types) == 1
    assert len(rotate_op.bridge_patches) == 1
    assert rotate_op.bridge_patches[0] == b0.ssa
    assert isinstance(rotate_op.result_types[0], RotatedPlanarPatchType)
    assert not isinstance(rotate_op.result_types[0].placement, NoneAttr)
    res_location = [loc.value.data for loc in rotate_op.result_types[0].placement.location.data]
    assert pytest.approx(res_location) == offset
    assert rotate_op.res == p0.ssa


@pytest.mark.xfail(reason="Unsized patches are not supported")
def test_rotate_operation_on_unsized_patch_raises() -> None:
    builder = LogAsmBuilder()
    p0 = builder.add_arg(RotatedPlanarPatch())
    with pytest.raises(InvalidSizeError):
        p0.rotate((0, 0))


# endregion

# region Grow operation


def test_grow_operation() -> None:
    builder = LogAsmBuilder()
    location = Vector(0, 0)
    p0 = builder.add_arg(RotatedPlanarPatch(5, 5, location=location))

    p0.grow(top=5, right=5)
    grow_op = builder._builder.last_op
    assert isinstance(grow_op, GrowOp)
    assert len(grow_op.result_types) == 1
    res_type = grow_op.result_types[0]
    assert isinstance(res_type, RotatedPlanarPatchType)
    assert not isinstance(res_type.placement, NoneAttr)

    assert pytest.approx([loc.value.data for loc in res_type.placement.location.data]) == location
    assert grow_op.res == p0.ssa


@pytest.mark.xfail(reason="Unsized patches are not supported")
def test_grow_operation_on_unsized_patch_raises() -> None:
    builder = LogAsmBuilder()
    p0 = builder.add_arg(RotatedPlanarPatch())
    with pytest.raises(InvalidSizeError):
        p0.grow(top=2, right=2)


# endregion

# region Shrink operation


def test_shrink_operation() -> None:
    builder = LogAsmBuilder()
    location = Vector(0, 0)
    p0 = builder.add_arg(RotatedPlanarPatch(5, 5, location=location))

    p0.shrink(top=2, right=3)
    shrink_op = builder._builder.last_op
    assert isinstance(shrink_op, ShrinkOp)
    assert len(shrink_op.result_types) == 1
    res_type = shrink_op.result_types[0]
    assert isinstance(res_type, RotatedPlanarPatchType)
    assert not isinstance(res_type.placement, NoneAttr)

    assert Vector([loc.value.data for loc in res_type.placement.location.data]) == location
    assert shrink_op.res == p0.ssa


def test_shrink_to_nothingness_fails() -> None:
    builder = LogAsmBuilder()
    p0 = builder.add_arg(RotatedPlanarPatch(5, 5, location=Vector(0, 0)))

    msg = "Cannot resize a patch to a negative or zero width"
    with pytest.raises(InvalidSizeError, match=msg):
        p0.shrink(left=5)
    with pytest.raises(InvalidSizeError, match=msg):
        p0.shrink(right=5)
    with pytest.raises(InvalidSizeError, match=msg):
        p0.shrink(right=80)
    with pytest.raises(InvalidSizeError, match=msg):
        p0.shrink(right=2, left=3)

    msg = "Cannot resize a patch to a negative or zero height"
    with pytest.raises(InvalidSizeError, match=msg):
        p0.shrink(top=5)
    with pytest.raises(InvalidSizeError, match=msg):
        p0.shrink(bottom=5)
    with pytest.raises(InvalidSizeError, match=msg):
        p0.shrink(bottom=80)
    with pytest.raises(InvalidSizeError, match=msg):
        p0.shrink(bottom=2, top=3)


@pytest.mark.xfail(reason="Unsized patches are not supported")
def test_shrink_operation_on_unsized_patch_raises() -> None:
    builder = LogAsmBuilder()
    p0 = builder.add_arg(RotatedPlanarPatch())
    with pytest.raises(InvalidSizeError):
        p0.shrink(top=2, right=2)


# endregion


# region Transversal gates


def test_single_qubit_transversal() -> None:
    builder = LogAsmBuilder()
    p0 = builder.declare_patch(RotatedPlanarPatch(5, 5, location=Vector(0, 0), vertical_z=True))

    builder.transversal("X", [p0])
    assert p0._width == 5
    assert p0._height == 5
    assert p0.location == Vector(0, 0)
    assert p0._vertical_z

    builder.transversal("Z", [p0])
    assert p0._width == 5
    assert p0._height == 5
    assert p0.location == Vector(0, 0)
    assert p0._vertical_z

    builder.transversal("H", [p0])
    assert p0._width == 5
    assert p0._height == 5
    assert p0.location == Vector(0, 0)
    assert not p0._vertical_z

    builder.transversal("Z", [p0])
    assert p0._width == 5
    assert p0._height == 5
    assert p0.location == Vector(0, 0)
    assert not p0._vertical_z


def test_two_qubit_transversal() -> None:
    builder = LogAsmBuilder()
    p0 = builder.declare_patch(RotatedPlanarPatch(5, 5, location=Vector(0, 0), vertical_z=True))
    p1 = builder.declare_patch(RotatedPlanarPatch(5, 5, location=Vector(0, 0), vertical_z=True))

    builder.transversal("CX", [p0, p1])
    for p in (p0, p1):
        assert p._width == 5
        assert p._height == 5
        assert p.location == Vector(0, 0)
        assert p._vertical_z


# endregion


# region Multi-pauli measurement


def test_multi_pauli_measurement_no_bridge() -> None:
    builder = LogAsmBuilder()
    p0 = builder.declare_patch(RotatedPlanarPatch(5, 5, location=Vector(0, 0)))
    p1 = builder.declare_patch(RotatedPlanarPatch(5, 5, location=Vector(6, 0)))
    res = builder.multi_pauli_measure([p0, p1], pauli_bases=["X", "X"])
    builder.add_return(res)

    circuit = builder.build_subroutine("mpp")
    assert not circuit._arguments
    assert isinstance(circuit._results, Result)


def test_multi_pauli_measurement_with_bridge() -> None:
    builder = LogAsmBuilder()
    p0 = builder.declare_patch(RotatedPlanarPatch(5, 5, location=Vector(0, 0)))
    p1 = builder.declare_patch(RotatedPlanarPatch(5, 5, location=Vector(6, 0)))
    b0 = builder.declare_patch(RotatedPlanarPatch(1, 5, location=Vector(5, 0)))
    res = builder.multi_pauli_measure([p0, p1], [b0], pauli_bases=["X", "X"])
    builder.add_return(res)

    circuit = builder.build_subroutine("mpp")
    assert not circuit._arguments
    assert isinstance(circuit._results, Result)


@pytest.mark.xfail(reason="Unsized patches are not supported")
def test_multi_pauli_measurement_operation_on_unsized_patch_raises() -> None:
    builder = LogAsmBuilder()
    p0 = builder.add_arg(RotatedPlanarPatch())
    p1 = builder.add_arg(RotatedPlanarPatch(3, 3, location=(0, 0)))
    msg = "All patches involved in a multi-pauli measurement must have a size."
    with pytest.raises(InvalidSizeError, match=msg):
        builder.multi_pauli_measure((p0, p1), pauli_bases=("X", "X"))


# endregion


# region Barrier


def test_barrier_explicit_args() -> None:
    builder = LogAsmBuilder()
    p0 = builder.declare_patch(RotatedPlanarPatch(5, 5))
    p1 = builder.declare_patch(RotatedPlanarPatch(5, 5))
    p0_ssa0 = p0.ssa
    p1_ssa0 = p1.ssa

    builder.barrier(p0)
    barrier_op = builder._builder.last_op
    assert isinstance(barrier_op, api.BarrierOp)
    assert len(barrier_op.arguments) == 1

    p0_ssa1 = p0.ssa
    assert p0_ssa0 != p0_ssa1

    builder.barrier(p0, p1)
    barrier_op = builder._builder.last_op
    assert isinstance(barrier_op, api.BarrierOp)
    assert len(barrier_op.arguments) == 2
    assert p0.ssa != p0_ssa1
    assert p0.ssa != p0_ssa0
    assert p1.ssa != p1_ssa0


def test_barrier_no_args() -> None:
    builder = LogAsmBuilder()
    p0 = builder.declare_patch(RotatedPlanarPatch(5, 5))
    p0_ssa0 = p0.ssa

    builder.barrier()
    barrier_op = builder._builder.last_op
    assert isinstance(barrier_op, api.BarrierOp)
    assert len(barrier_op.arguments) == 1

    p0_ssa1 = p0.ssa
    assert p0_ssa0 != p0_ssa1

    p1 = builder.declare_patch(RotatedPlanarPatch(5, 5))
    p1_ssa0 = p1.ssa
    builder.barrier()
    barrier_op = builder._builder.last_op
    assert isinstance(barrier_op, api.BarrierOp)
    assert len(barrier_op.arguments) == 3
    assert p0.ssa != p0_ssa1
    assert p0.ssa != p0_ssa0
    assert p1.ssa != p1_ssa0


# endregion

# region Calling subroutine


def test_example_subroutines_from_spec():
    # Build a subroutine
    builder = LogAsmBuilder()
    patch = builder.add_arg(RotatedPlanarPatch(3, 3))
    patch.measure_stabilisers(5)
    my_subroutine = builder.build_subroutine("test")

    assert my_subroutine.identifier == "test"
    assert len(my_subroutine._arguments) == 1
    assert isinstance(my_subroutine._arguments[0], RotatedPlanarPatch)
    assert not my_subroutine._results

    # Build a program that calls the subroutine
    builder = LogAsmBuilder()
    patch = builder.declare_patch(RotatedPlanarPatch(3, 3))
    results = builder.call_subroutine(my_subroutine(patch))
    assert results is None


def test_call_subroutine_with_a_single_measurement_reg_result() -> None:
    """A subroutine with one non-``Result`` result is not wrapped into a one-element tuple."""
    cbuilder = CircuitBuilder()
    qreg = cbuilder.add_arg(QubitReg(3))
    cbuilder.add_return(cbuilder.measure("Z", qreg))
    circuit = cbuilder.build("meas_reg")

    sub_builder = LogAsmBuilder()
    sub_reg = sub_builder.add_arg(QubitReg(3))
    sub_builder.add_return(sub_builder.call_circuit(circuit(sub_reg)))
    subroutine = sub_builder.build_subroutine("returns_one_reg")
    assert isinstance(subroutine._results, MeasurementReg)

    builder = LogAsmBuilder()
    reg = builder.declare_patch(QubitReg(3))
    results = builder.call_subroutine(subroutine(reg))
    assert isinstance(results, MeasurementReg)
    assert results.num_bits == 3


def test_call_subroutine_with_wrong_parameters():
    # Build a subroutine
    builder = LogAsmBuilder()
    patch = builder.add_arg(RotatedPlanarPatch(5, 5))
    patch.measure_stabilisers(5)
    my_subroutine = builder.build_subroutine("test")

    # Wrong type
    builder = LogAsmBuilder()
    classical_argument = builder.add_arg(Result)
    msg = (
        "Expected a parameter of type RotatedPlanarPatch for the 0-th parameter .* but got an "
        "instance of Result which is not a subclass of RotatedPlanarPatch"
    )
    with pytest.raises(TypeError, match=msg):
        my_subroutine(classical_argument)

    # Wrong number
    rpatch1 = builder.add_arg(RotatedPlanarPatch(5, 5))
    rpatch2 = builder.add_arg(RotatedPlanarPatch(5, 5))
    with pytest.raises(InvalidSizeError, match=r"Expected 1 arguments .* but got 2"):
        my_subroutine(rpatch1, rpatch2)

    # Different builders
    builder0 = LogAsmBuilder()
    _ = builder0.add_arg(RotatedPlanarPatch(5, 5)), builder0.add_arg(RotatedPlanarPatch(5, 5))
    my_subroutine = builder0.build_subroutine("test")

    builder1, builder2 = LogAsmBuilder(), LogAsmBuilder()
    arg1, arg2 = (
        builder1.add_arg(RotatedPlanarPatch(5, 5)),
        builder2.add_arg(RotatedPlanarPatch(5, 5)),
    )
    msg = "Expected all arguments given to a subroutine call to be managed by the same builder."
    with pytest.raises(DifferentBuildersError, match=msg):
        my_subroutine(arg1, arg2)


def test_call_subroutine_with_invalid_instantiated_circuit() -> None:

    builder = LogAsmBuilder()
    patch = builder.add_arg(RotatedPlanarPatch(5, 5))
    patch.measure_stabilisers(5)
    my_subroutine = builder.build_subroutine("test")

    builder = LogAsmBuilder()
    res = builder.add_arg(Result)
    bad_routine: InstantiatedLogAsmSubroutine[Any, None] = InstantiatedLogAsmSubroutine(
        my_subroutine.module, "test", my_subroutine._results, res
    )
    with pytest.raises(
        TypeError,
        match=re.escape(
            "Cannot call test with expression of type i1, "
            "expected a !log_asm.patch.rot_planar<size=(5, 5)>"
        ),
    ):
        builder.call_subroutine(bad_routine)


def test_example_subroutine_multiple_args_and_call():
    """Test based on API Examples document"""
    builder = LogAsmBuilder()
    patch, log = builder.add_arg(RotatedPlanarPatch(5, 5)), builder.add_arg(Result)
    log2 = patch.measure("Z")
    builder.add_return(log2)
    my_subroutine = builder.build_subroutine("subroutine")

    assert my_subroutine.identifier == "subroutine"
    assert len(my_subroutine._arguments) == 2
    assert isinstance(my_subroutine._results, Result)

    builder = LogAsmBuilder()
    patch = builder.declare_patch(RotatedPlanarPatch(5, 5))
    log = patch.measure("Z")
    instantiated_subroutine = my_subroutine(patch, log)
    assert instantiated_subroutine.identifier == my_subroutine.identifier
    assert instantiated_subroutine.outer_arguments == (patch, log)
    assert isinstance(instantiated_subroutine._results, Result)
    results = builder.call_subroutine(instantiated_subroutine)
    assert isinstance(results, Result)


# region Calling subroutines


def test_subroutine_calling() -> None:
    builder1 = LogAsmBuilder()
    _ = builder1.add_arg(QubitReg())
    subroutine = builder1.build_subroutine("empty_subroutine")

    lbuilder = LogAsmBuilder()
    qreg = lbuilder.add_arg(QubitReg(10))
    lbuilder.call_subroutine(subroutine(qreg))
    logasm_program = lbuilder.build_subroutine("example_logasm")
    assert "empty_subroutine" in lbuilder._called.callables
    assert isinstance(lbuilder._called.callables["empty_subroutine"], func.FuncOp)
    assert len(logasm_program.func_op.regions) == 1
    region = logasm_program.func_op.regions[0]
    assert len(region.blocks) == 1
    block = region.block
    assert len(block.ops) == 4
    assert number_of_operations_of_type_in_block(block, api.CastOp) == 2
    assert number_of_operations_of_type_in_block(block, func.CallOp) == 1
    assert number_of_operations_of_type_in_block(block, func.ReturnOp) == 1
    call_op = next(op for op in block.ops if isinstance(op, func.CallOp))
    assert isinstance(call_op, func.CallOp)
    assert call_op.callee.string_value() == "empty_subroutine"


def test_subroutine_calling_common_subroutines() -> None:
    builder1 = LogAsmBuilder()
    _ = builder1.add_arg(QubitReg())
    common_subroutine = builder1.build_subroutine("empty_subroutine")

    builder2 = LogAsmBuilder()
    qreg = builder2.add_arg(QubitReg(10))
    builder2.call_subroutine(common_subroutine(qreg))
    subroutine2 = builder2.build_subroutine("subroutine2")

    builder3 = LogAsmBuilder()
    qreg = builder3.add_arg(QubitReg(5))
    builder3.call_subroutine(common_subroutine(qreg))
    subroutine3 = builder3.build_subroutine("subroutine3")

    prog_builder = LogAsmBuilder()
    p1 = prog_builder.declare_patch(QubitReg(10))
    p2 = prog_builder.declare_patch(QubitReg(5))
    prog_builder.call_subroutine(subroutine2(p1))
    prog_builder.call_subroutine(subroutine3(p2))
    program = prog_builder.build_program()
    module = program.module

    assert SymbolTable.lookup_symbol(module, "empty_subroutine")
    assert SymbolTable.lookup_symbol(module, "subroutine2")
    assert SymbolTable.lookup_symbol(module, "subroutine3")
    assert len([op.sym_name.data for op in module.ops if isinstance(op, FuncOp)]) == 3


def test_subroutine_calling_wrong_qubit_number() -> None:
    builder1 = LogAsmBuilder()
    _ = builder1.add_arg(QubitReg(3))
    subroutine = builder1.build_subroutine("empty_subroutine")

    lbuilder = LogAsmBuilder()
    qreg = lbuilder.add_arg(QubitReg(2))
    msg = "Expected a register of size 3 but got a register of size 2 for parameter 0"
    with pytest.raises(ValueError, match=msg):
        lbuilder.call_subroutine(subroutine(qreg))


def test_subroutine_with_multiple_returns() -> None:
    builder1 = LogAsmBuilder()
    patch = builder1.add_arg(RotatedPlanarPatch(3, 3, location=(0, 0)))
    m0 = patch.measure("X")
    patch.prepare("X")
    m1 = patch.measure("Z")
    builder1.add_return(m0)
    builder1.add_return(m1)
    subroutine = builder1.build_subroutine("multi_return")

    assert len(subroutine._results) == 2

    builder2 = LogAsmBuilder()
    patch = builder2.add_arg(RotatedPlanarPatch(3, 3, location=(0, 0)))
    res0, res1 = builder2.call_subroutine(subroutine(patch))
    assert isinstance(res0, Result)
    assert isinstance(res1, Result)
    builder2.build_subroutine(identifier="calls_multi_return")


def test_subroutine_calling_fails_on_duplicate_identifier() -> None:
    builder1 = LogAsmBuilder()
    _ = builder1.add_arg(QubitReg())
    subroutine = builder1.build_subroutine("subroutine")

    builder2 = LogAsmBuilder()
    patch = builder2.add_arg(RotatedPlanarPatch(3, 3))
    builder2.transversal("X", [patch])
    subroutine2 = builder2.build_subroutine("subroutine")

    lbuilder = LogAsmBuilder()
    qreg = lbuilder.add_arg(QubitReg(10))
    patch = lbuilder.add_arg(RotatedPlanarPatch(3, 3))
    lbuilder.call_subroutine(subroutine(qreg))
    msg = (
        "Could not call the subroutine with identifier 'subroutine': a different subroutine with "
        "the same identifier has already been used and the two different definitions would clash."
    )
    with pytest.raises(IdentifierConflictError, match=msg):
        lbuilder.call_subroutine(subroutine2(patch))


def test_nested_subroutines_with_same_identifiers_fails() -> None:
    builder1 = LogAsmBuilder()
    _ = builder1.add_arg(QubitReg())
    subroutine = builder1.build_subroutine("subroutine")

    builder2 = LogAsmBuilder()
    qreg = builder2.add_arg(QubitReg())
    builder2.call_subroutine(subroutine(qreg))
    msg = (
        "Cannot build the subroutine with identifier 'subroutine' as it already calls a "
        "subroutine with that identifier."
    )
    with pytest.raises(IdentifierConflictError, match=msg):
        builder2.build_subroutine("subroutine")


def test_subroutine_calling_fails_on_nested_duplicate_identifier() -> None:
    builder1 = LogAsmBuilder()
    _ = builder1.add_arg(QubitReg())
    subroutine = builder1.build_subroutine("subroutine")

    builder2 = LogAsmBuilder()
    patch = builder2.add_arg(RotatedPlanarPatch(3, 3))
    builder2.transversal("X", [patch])
    subroutine2 = builder2.build_subroutine("subroutine")

    builder3 = LogAsmBuilder()
    patch = builder3.add_arg(RotatedPlanarPatch(3, 3))
    builder3.call_subroutine(subroutine2(patch))
    subroutine3 = builder3.build_subroutine("calling_subroutine")

    lbuilder = LogAsmBuilder()
    qreg = lbuilder.add_arg(QubitReg(10))
    patch = lbuilder.add_arg(RotatedPlanarPatch(3, 3))
    lbuilder.call_subroutine(subroutine(qreg))
    msg = (
        "Could not call the subroutine with identifier 'calling_subroutine' because it uses a "
        "declaration for 'subroutine' that does not match with the declaration already present in "
        "the Logical Assembly program currently being built."
    )
    with pytest.raises(IdentifierConflictError, match=msg):
        lbuilder.call_subroutine(subroutine3(patch))


def test_subroutine_raises_when_instantiated_with_kwargs() -> None:
    msg = re.escape(
        "Cannot instantiate a LogAsmSubroutine with keyword arguments (kwargs). "
        "The following keyword arguments were found: 'hello'."
    )
    with pytest.raises(RuntimeError, match=msg):
        LogAsmSubroutine(ModuleOp([]), "subroutine", (), hello="world")


def test_subroutine_raises_when_instantiated_with_invalid_types() -> None:
    msg = re.escape(
        "The provided arguments '(!qcore.qubit)' contains at least one invalid argument type."
    )
    with pytest.raises(ArgumentError, match=msg):
        LogAsmSubroutine(ModuleOp([]), "subroutine", (), QubitType())


def test_subroutine_calling_fails_with_kwargs() -> None:
    builder1 = LogAsmBuilder()
    _ = builder1.add_arg(QubitReg())
    subroutine = builder1.build_subroutine("subroutine")
    msg = re.escape("Cannot call a LogAsmSubroutine with keyword arguments (kwargs).")
    with pytest.raises(RuntimeError, match=msg):
        subroutine(hello="world")


# endregion


# region Calling circuits


def test_circuit_calling() -> None:
    cbuilder = CircuitBuilder()
    qreg_arg = cbuilder.add_arg(QubitReg())
    cbuilder.gate("X", qreg_arg)
    cbuilder.gate("Z", qreg_arg[4])
    circuit = cbuilder.build("example_circuit")

    lbuilder = LogAsmBuilder()
    qreg = lbuilder.add_arg(QubitReg(10))
    lbuilder.call_circuit(circuit(qreg))
    logasm_program = lbuilder.build_subroutine("example_logasm")

    assert "example_circuit" in lbuilder._called.callables
    assert isinstance(lbuilder._called.callables["example_circuit"], api.CircuitDeclarationOp)
    assert len(logasm_program.func_op.regions) == 1
    region = logasm_program.func_op.regions[0]
    assert len(region.blocks) == 1
    block = region.block

    assert len(block.ops) == 4
    assert number_of_operations_of_type_in_block(block, api.CallOp) == 1
    assert number_of_operations_of_type_in_block(block, func.ReturnOp) == 1
    assert number_of_operations_of_type_in_block(block, api.CastOp) == 2
    call_op = next(op for op in block.ops if isinstance(op, api.CallOp))
    assert isinstance(call_op, api.CallOp)
    assert call_op.callee.string_value() == "example_circuit"


def test_circuits_with_multiple_returns() -> None:
    cbuilder = CircuitBuilder()
    r0 = cbuilder.add_arg(QubitReg(5))
    r1 = cbuilder.add_arg(QubitReg(10))
    m0 = cbuilder.measure(Pauli.X, r0)
    m1 = cbuilder.measure(Pauli.Z, r1)
    cbuilder.add_return(m0)
    cbuilder.add_return(m1)
    circuit = cbuilder.build("multi_return")

    builder = LogAsmBuilder()
    reg1 = builder.declare_patch(QubitReg(5))
    reg2 = builder.declare_patch(QubitReg(10))
    res0, res1 = builder.call_circuit(circuit(reg1, reg2))
    assert isinstance(res0, MeasurementReg)
    assert isinstance(res1, MeasurementReg)
    builder.build_program()


# region String methods


EXP_SUBROUTINE_STR = """LogAsmSubroutine('namey mcnameface' {
^bb0(%0: i64):
  %1 = "test.op"(%0) : (i64) -> i32
  func.return %1 : i32
})"""


def test_subroutine_str() -> None:
    @Builder.implicit_region([i64])
    def body(args: tuple[BlockArgument, ...]):
        i = t.TestOp(operands=[args[0]], result_types=[i32])
        func.ReturnOp(i)

    func_op = FuncOp("namey mcnameface", ([i64], [i64]), body)
    # Don't need arguments or results as block handles printing that information
    assert str(LogAsmSubroutine(ModuleOp([func_op]), "namey mcnameface", ())) == EXP_SUBROUTINE_STR


EXP_NESTED_SUBROUTINE_STR = """LogAsmSubroutine('namey mcnameface1' {
^bb0(%0: i64):
  %1, %2 = "test.op"(%0) : (i64) -> (i32, i64)
  %3 = func.call @"namey mcnameface2"(%2) : (i64) -> i32
  %4 = func.call @"namey mcnameface3"(%2) : (i64) -> i32
  func.return %1 : i32
} which calls {
  'namey mcnameface2' {
  ^bb1(%5: i64):
    %6 = "test.op"(%5) : (i64) -> i32
    func.return %6 : i32
  },
  'namey mcnameface3' {
  ^bb2(%7: i64):
    %8 = "test.op"(%7) : (i64) -> i32
    %9 = func.call @"namey mcnameface2"(%7) : (i64) -> i32
    func.return %8 : i32
  }
})"""


def test_nested_subroutine_str() -> None:
    @Builder.implicit_region([i64])
    def body1(args: tuple[BlockArgument, ...]):
        i = t.TestOp(operands=[args[0]], result_types=[i32, i64])
        func.CallOp("namey mcnameface2", (i.res[1],), (i32,))
        func.CallOp("namey mcnameface3", (i.res[1],), (i32,))
        func.ReturnOp(i.res[0])

    @Builder.implicit_region([i64])
    def body2(args: tuple[BlockArgument, ...]):
        i = t.TestOp(operands=[args[0]], result_types=[i32])
        func.ReturnOp(i)

    @Builder.implicit_region([i64])
    def body3(args: tuple[BlockArgument, ...]):
        i = t.TestOp(operands=[args[0]], result_types=[i32])
        func.CallOp("namey mcnameface2", args, (i32,))
        func.ReturnOp(i)

    func_op1 = FuncOp("namey mcnameface1", ([i64], [i64]), body1)
    func_op2 = FuncOp("namey mcnameface2", ([i64], [i64]), body2)
    func_op3 = FuncOp("namey mcnameface3", ([i64], [i64]), body3)
    # Don't need arguments or results as block handles printing that information
    assert (
        str(LogAsmSubroutine(ModuleOp([func_op1, func_op2, func_op3]), "namey mcnameface1", ()))
        == EXP_NESTED_SUBROUTINE_STR
    )


def test_full_program_str() -> None:
    c_builder = CircuitBuilder()
    qreg1 = c_builder.add_arg(QubitReg())
    c_builder.gate("X", qreg1)
    x_circuit = c_builder.build("x_gate")

    builder1 = LogAsmBuilder()
    qreg = builder1.add_arg(QubitReg())
    builder1.call_circuit(x_circuit(qreg))
    builder1.call_circuit(x_circuit(qreg[:5]))
    subroutine1 = builder1.build_subroutine("subroutine1")

    builder2 = LogAsmBuilder()
    qreg = builder2.add_arg(QubitReg(15))
    builder2.call_subroutine(subroutine1(qreg[:10]))
    builder2.call_circuit(x_circuit(qreg[0:2]))
    subroutine2 = builder2.build_subroutine("subroutine2")

    prog_builder = LogAsmBuilder()
    p1 = prog_builder.declare_patch(QubitReg(10))
    p2 = prog_builder.declare_patch(QubitReg(15))
    prog_builder.call_subroutine(subroutine1(p1))
    prog_builder.call_subroutine(subroutine2(p2))
    program = prog_builder.build_program()
    pattern = (
        r"LogAsmProgram\(\{.*"
        r"alloc_qubit.*call @subroutine1.*call @subroutine2.*"
        r"func @subroutine1.*circuit_dec @x_gate.*func @subroutine2.*\}\)"
    )
    assert re.match(pattern, str(program), re.DOTALL)


def test_log_asm_program_module_copies_inner() -> None:
    """Tests that a LogAsmProgram's module exposed by cloning so that modifications do not effect
    the original."""
    program = LogAsmBuilder().build_program()
    assert program.module != program.module
    assert isinstance(program.module, ModuleOp)
    exp_string = str(program)
    program.module.body.block.add_op(t.TestOp())
    assert str(program) == exp_string
    assert next((op for op in program.module.ops if isinstance(op, t.TestOp)), None) is None


# endregion
