import re

import pytest
from xdsl.dialects import test as _test
from xdsl.dialects.builtin import DYNAMIC_INDEX, IntegerType, TensorType

from deltakit_compile.dialects.qcore import QubitType
from deltakit_compile.frontend.common._builder import OperationBuilder
from deltakit_compile.frontend.common._exceptions import (
    DifferentBuildersError,
    InvalidSizeError,
    MissingLocationError,
    ObjectNotAttachedError,
)
from deltakit_compile.frontend.common._measurements import MeasurementReg
from deltakit_compile.frontend.common._qubit_reg import Qubit, QubitReg, number_of_qubits
from deltakit_compile.frontend.common._vector import Vector
from deltakit_compile.shared.patch.exceptions import UnplacedPatchError
from tests.unit.frontend.conftest import add_to_builder_with_fake_ssa


def test_initialisation() -> None:
    assert QubitReg().num_qubits is None
    assert QubitReg(10).num_qubits == 10
    qreg = QubitReg(qubit_locations=[Vector(i, i) for i in range(10)])
    assert qreg.qubit_locations is not None
    assert len(qreg.qubit_locations) == 10


def test_invalid_initialisation() -> None:
    msg = r"Invalid number of qubit: 0. Expected a strictly positive \(> 0\) number."
    with pytest.raises(InvalidSizeError, match=msg):
        QubitReg(0)
    msg = r"Invalid number of qubit: -1. Expected a strictly positive \(> 0\) number."
    with pytest.raises(InvalidSizeError, match=msg):
        QubitReg(-1)
    msg = "When provided, qubit_locations should be non-empty."
    with pytest.raises(ValueError, match=msg):
        QubitReg(qubit_locations=[])
    msg = "Got num_qubits=2 but 10 locations. They should be equal."
    with pytest.raises(InvalidSizeError, match=msg):
        QubitReg(num_qubits=2, qubit_locations=[Vector(i, i) for i in range(10)])


def test_qubit_reg_qubit_count() -> None:
    qubit_locations = [Vector(i, i) for i in range(10)]
    reg = QubitReg(qubit_locations=qubit_locations)
    assert reg.num_qubits == 10


def test_qubit_reg_len() -> None:
    qubit_locations = [Vector(i, i) for i in range(10)]
    reg = QubitReg(qubit_locations=qubit_locations)
    assert len(reg) == 10

    msg = "Cannot get the length of an unsized QubitReg."
    with pytest.raises(InvalidSizeError, match=msg):
        len(QubitReg())


def test_qubit_len() -> None:
    assert len(Qubit()) == 1


def test_qubit_reg_qubit_locations() -> None:
    qubit_locations = tuple(Vector(i, i) for i in range(10))
    reg = QubitReg(qubit_locations=qubit_locations)
    assert reg.qubit_locations == qubit_locations

    new_qubit_locations = tuple(Vector(-i, i) for i in range(10))
    reg.qubit_locations = new_qubit_locations
    assert reg.qubit_locations == new_qubit_locations

    msg = "Got 12 qubit locations for a register of size 10. Both sizes should match."
    with pytest.raises(InvalidSizeError, match=msg):
        reg.qubit_locations = [Vector(-i, i) for i in range(12)]

    msg = "Cannot set qubit locations for an unsized register."
    unsized_reg = QubitReg()
    with pytest.raises(InvalidSizeError, match=msg):
        unsized_reg.qubit_locations = [Vector(-i, i) for i in range(12)]


def test_qubit_reg_type_info() -> None:
    reg = QubitReg()
    assert reg._type_info == TensorType(QubitType(), (DYNAMIC_INDEX,))

    reg = QubitReg(10)
    assert reg._type_info == TensorType(QubitType(), (10,))

    qubit_locations = [Vector(i, i) for i in range(3)]
    reg = QubitReg(qubit_locations=qubit_locations)
    assert reg._type_info == TensorType(QubitType(), (3,))


def test_qubit_reg_at_location() -> None:
    unregistered_reg = QubitReg()

    msg = "QubitReg instance does not contain any location information\\."
    with pytest.raises(UnplacedPatchError, match=msg):
        unregistered_reg.at_location(Vector(0, 0))

    builder = OperationBuilder()
    unsized_reg = add_to_builder_with_fake_ssa(builder, QubitReg())
    sized_reg_without_locations = add_to_builder_with_fake_ssa(builder, QubitReg(10))
    msg = "QubitReg instance does not contain any location information."
    for reg in (unsized_reg, sized_reg_without_locations):
        with pytest.raises(UnplacedPatchError, match=msg):
            reg.at_location(Vector(0, 0))

    sized_reg_with_locations = add_to_builder_with_fake_ssa(
        builder, QubitReg(10, qubit_locations=[Vector(i, -i) for i in range(10)])
    )

    qubit = sized_reg_with_locations.at_location(Vector(0, 0))
    assert qubit.location is not None
    assert qubit.location == Vector(0, 0)

    qubit = sized_reg_with_locations.at_location((0, 0))
    assert qubit.location is not None
    assert qubit.location == Vector(0, 0)

    qubit = sized_reg_with_locations.at_location(0, 0)
    assert qubit.location is not None
    assert qubit.location == Vector(0, 0)


def test_qubit_reg_builder_extract_object_from_index() -> None:
    builder = OperationBuilder()
    unsized_reg = add_to_builder_with_fake_ssa(builder, QubitReg())

    extracted_reg = unsized_reg._extract_object_from_index(slice(10))
    assert extracted_reg._num_qubits is None
    assert extracted_reg.qubit_locations is None

    sized_reg_with_locations = add_to_builder_with_fake_ssa(
        builder, QubitReg(20, qubit_locations=[Vector(i, i) for i in range(20)])
    )
    extracted_reg = sized_reg_with_locations._extract_object_from_index(slice(1, 18, 2))
    assert extracted_reg._num_qubits == 9
    assert extracted_reg.qubit_locations == tuple(Vector(i, i) for i in range(1, 18, 2))

    unmanaged_register = QubitReg()
    with pytest.raises(ObjectNotAttachedError):
        unmanaged_register._extract_object_from_index(0)


def test_qubit_reg_getitem() -> None:
    builder = OperationBuilder()
    unsized_reg = add_to_builder_with_fake_ssa(builder, QubitReg())

    qubit = unsized_reg[1]
    assert isinstance(qubit, Qubit)
    assert qubit.location is None

    qubit = unsized_reg[-1]
    assert isinstance(qubit, Qubit)
    assert qubit.location is None

    sized_reg_with_locations = add_to_builder_with_fake_ssa(
        builder, QubitReg(20, qubit_locations=[Vector(i, i) for i in range(20)])
    )

    qubit = sized_reg_with_locations[-1]
    assert isinstance(qubit, Qubit)
    assert qubit.location == Vector(19, 19)

    qubit = sized_reg_with_locations[10]
    assert isinstance(qubit, Qubit)
    assert qubit.location == Vector(10, 10)


def test_qubit_reg_getitem_slice() -> None:
    builder = OperationBuilder()
    unsized_reg = add_to_builder_with_fake_ssa(builder, QubitReg())

    qreg = unsized_reg[1:6:2]
    assert isinstance(qreg, QubitReg)
    assert qreg.num_qubits is None
    assert qreg.qubit_locations is None

    qreg = unsized_reg[-3:0:-2]
    assert isinstance(qreg, QubitReg)
    assert qreg.num_qubits is None
    assert qreg.qubit_locations is None

    sized_reg_with_locations = add_to_builder_with_fake_ssa(
        builder, QubitReg(20, qubit_locations=[Vector(i, i) for i in range(20)])
    )

    qreg = sized_reg_with_locations[1:6:2]
    assert isinstance(qreg, QubitReg)
    assert qreg.num_qubits == 3
    assert qreg.qubit_locations == (Vector(1, 1), Vector(3, 3), Vector(5, 5))

    qreg = sized_reg_with_locations[-3:0:-2]
    assert isinstance(qreg, QubitReg)
    assert qreg.num_qubits == 9
    assert qreg.qubit_locations == tuple(Vector(i, i) for i in range(17, 0, -2))


def test_qubit_reg_getitem_raises() -> None:
    unattached_reg = QubitReg(20, qubit_locations=[Vector(i, i) for i in range(20)])
    with pytest.raises(ObjectNotAttachedError):
        unattached_reg[0]

    builder = OperationBuilder()
    reg = add_to_builder_with_fake_ssa(builder, QubitReg(20))
    with pytest.raises(IndexError, match=r"Index 20 is out of range for a QubitReg of length 20."):
        reg[20]


def test_qubit_reg_iteration() -> None:
    builder = OperationBuilder()
    reg = add_to_builder_with_fake_ssa(builder, QubitReg(10))
    assert all(isinstance(q, Qubit) for q in reg)
    assert len(list(reg)) == 10  # uses __iter__

    unsized_reg = add_to_builder_with_fake_ssa(builder, QubitReg())
    with pytest.raises(InvalidSizeError, match=r"Cannot iterate through an unsized QubitReg."):
        [q.identifier for q in unsized_reg]


def test_qubit_reg_builder_merge_objects() -> None:
    builder = OperationBuilder()
    unsized_reg = add_to_builder_with_fake_ssa(builder, QubitReg())
    sized_reg_with_locations = add_to_builder_with_fake_ssa(
        builder, QubitReg(20, qubit_locations=[Vector(i, i) for i in range(20)])
    )
    other_sized_reg_with_locations = add_to_builder_with_fake_ssa(
        builder, QubitReg(10, qubit_locations=[Vector(i, -i) for i in range(10)])
    )

    merged_no_size = unsized_reg + sized_reg_with_locations
    assert merged_no_size.num_qubits is None
    assert merged_no_size.qubit_locations is None

    merged_sized = sized_reg_with_locations + other_sized_reg_with_locations
    assert merged_sized.num_qubits == 30
    assert merged_sized.qubit_locations == (
        *(Vector(i, i) for i in range(20)),
        *(Vector(i, -i) for i in range(10)),
    )

    with pytest.raises(DifferentBuildersError):
        _ = merged_no_size + QubitReg()
    with pytest.raises(DifferentBuildersError):
        _ = merged_no_size + [Qubit()]  # noqa: RUF005
    meas = add_to_builder_with_fake_ssa(builder, MeasurementReg(2))
    msg = re.escape("Expected either a Sequence[Qubit] or a QubitReg but got MeasurementReg.")
    with pytest.raises(TypeError, match=msg):
        merged_no_size + meas  # type: ignore[operator]
    msg = re.escape("Expected either a Sequence[Qubit] or a QubitReg but got tuple[int].")
    with pytest.raises(TypeError, match=msg):
        merged_no_size + (1, 3, 5)  # type: ignore[operator]  # noqa: RUF005


def test_qubit_reg_add() -> None:
    with pytest.raises(ObjectNotAttachedError):
        _ = QubitReg() + QubitReg(1)

    builder = OperationBuilder()
    qubit_locations = [Vector(i, i) for i in range(20)]
    unsized_reg = add_to_builder_with_fake_ssa(builder, QubitReg())
    sized_reg_with_locations = add_to_builder_with_fake_ssa(
        builder, QubitReg(20, qubit_locations=qubit_locations)
    )
    sized_reg_without_locations = add_to_builder_with_fake_ssa(builder, QubitReg(10))

    unsized_expected = unsized_reg + sized_reg_with_locations
    assert unsized_expected.num_qubits is None
    assert unsized_expected.qubit_locations is None

    sized_without_locations_expected = sized_reg_with_locations + sized_reg_without_locations
    assert sized_without_locations_expected.num_qubits == 30
    assert sized_without_locations_expected.qubit_locations is None

    sized_with_locations_expected = sized_reg_with_locations + sized_reg_with_locations
    assert sized_with_locations_expected.num_qubits == 40
    assert sized_with_locations_expected.qubit_locations == (*qubit_locations, *qubit_locations)

    q0, q1 = sized_reg_with_locations[0], sized_reg_with_locations[1]
    merged_with_qubits_no_location = sized_reg_without_locations + (q0, q1)  # noqa: RUF005
    assert merged_with_qubits_no_location.num_qubits == 12
    assert merged_with_qubits_no_location.qubit_locations is None

    merged_with_qubits_location = sized_reg_with_locations + (q0, q1)  # noqa: RUF005
    assert merged_with_qubits_location.num_qubits == 22
    assert merged_with_qubits_location.qubit_locations is not None
    assert len(merged_with_qubits_location) == 22


def test_qubit_reg_equality_and_hash() -> None:
    builder = OperationBuilder()
    unsized_reg = add_to_builder_with_fake_ssa(builder, QubitReg())
    sized_reg_without_locations = add_to_builder_with_fake_ssa(builder, QubitReg(10))

    assert unsized_reg != 1
    assert unsized_reg == unsized_reg  # noqa: PLR0124
    assert not (unsized_reg == sized_reg_without_locations)  # noqa: SIM201
    assert hash(unsized_reg) == hash(unsized_reg)


def test_qubit_reg_builder_is_managing() -> None:
    builder = OperationBuilder()
    unsized_reg = add_to_builder_with_fake_ssa(builder, QubitReg())

    assert builder.is_managing(unsized_reg)


def test_qubit_reg_identifier() -> None:
    reg = QubitReg()
    with pytest.raises(ObjectNotAttachedError):
        _ = reg.identifier

    builder = OperationBuilder()
    add_to_builder_with_fake_ssa(builder, reg)
    assert isinstance(reg.identifier, str)


def test_set_num_qubits_and_locations() -> None:
    qreg_unsized = QubitReg(None)
    qreg_located = QubitReg(10, [(i, i) for i in range(10)])

    qreg_unsized._set_num_qubits_and_locations(2, [(0, 0), (1, 1)])
    assert qreg_unsized.num_qubits == 2
    assert qreg_unsized.qubit_locations == ((0, 0), (1, 1))

    with pytest.raises(MissingLocationError):
        qreg_located._set_num_qubits_and_locations(10, None)
    with pytest.raises(InvalidSizeError):
        qreg_unsized._set_num_qubits_and_locations(1, [(0, 0), (1, 1)])


def test_qubit_type_info() -> None:
    assert Qubit()._type_info == QubitType()


@pytest.mark.parametrize(
    ("reg", "expected"), [(QubitReg(), False), (QubitReg(1), True), (QubitReg(34), True)]
)
def test_qubit_reg_is_sized(reg: QubitReg, expected: bool) -> None:
    assert reg.is_sized == expected


@pytest.mark.parametrize(
    ("reg", "expected"), [(QubitReg(), True), (QubitReg(1), False), (QubitReg(34), False)]
)
def test_qubit_reg_is_unsized(reg: QubitReg, expected: bool) -> None:
    assert reg.is_unsized == expected


def test_qubit_equality() -> None:
    builder = OperationBuilder()
    ureg1 = add_to_builder_with_fake_ssa(builder, QubitReg())
    ureg2 = add_to_builder_with_fake_ssa(builder, QubitReg())
    assert ureg1[0] == ureg1[0]
    assert ureg1[45] != ureg2[45]


def test_qubit_in_dictionary() -> None:
    builder = OperationBuilder()
    reg = add_to_builder_with_fake_ssa(builder, QubitReg(10))
    subreg = reg[:5]

    mapping = {subreg[0]: 1, reg[1]: 2}
    assert mapping[subreg[0]] == 1
    assert mapping[reg[0]] == 1
    assert mapping[subreg[1]] == 2
    assert mapping[reg[1]] == 2
    assert reg[4] not in mapping


@pytest.mark.parametrize(
    ("obj", "expected"),
    [(Qubit(), 1), (QubitReg(), None), (QubitReg(1), 1), (QubitReg(93847), 93847)],
)
def test_number_of_qubits(obj: Qubit | QubitReg, expected: int | None) -> None:
    assert number_of_qubits(obj) == expected


def test_qubit_reg_ssa_is_lazy() -> None:
    builder = OperationBuilder()
    reg = add_to_builder_with_fake_ssa(builder, QubitReg(10))
    assert len(builder.region.block.ops) == 1
    reg[0], reg[1], reg[3]
    assert len(builder.region.block.ops) == 1
    bit = reg[0]
    ssa = bit.ssa
    num_ops = len(builder.region.block.ops)
    assert num_ops > 1
    ssa2 = bit.ssa
    assert ssa is ssa2
    assert len(builder.region.block.ops) == num_ops


def test_qubit_ssa_uses_attribute_when_argument() -> None:
    builder = OperationBuilder()
    qubit = add_to_builder_with_fake_ssa(builder, Qubit())
    assert len(builder.region.block.ops) == 1
    assert qubit.ssa is qubit._ssa


def test_qubit_reg_update_ssa_value_raises_on_unexpected_type() -> None:
    """Test that _update_ssa_value raises RuntimeError when SSA has unexpected type."""
    builder = OperationBuilder()
    # Create a QubitReg with an incorrect SSA type
    # (i32 instead of QubitRegType/TensorType/SurfaceCodeBasePatch)
    reg = builder.append_op_and_update_ssas(
        _test.TestOp(result_types=[IntegerType(32)]), QubitReg(3)
    )
    assert reg.ssa.type == IntegerType(32)

    # Get an different ssa value to replace it with
    new_op = _test.TestOp(result_types=[TensorType(QubitType(), (3,))])
    builder.append_ops_ignoring_ssas(new_op)

    # Fail to auto cast when updating the value:
    msg = (
        r"QubitReg has unexpected ssa type: i32, "
        r"expected a qubit register, surface code patch, or qubit tensor"
    )
    with pytest.raises(RuntimeError, match=msg):
        reg._update_ssa_value(new_op.results[0])
