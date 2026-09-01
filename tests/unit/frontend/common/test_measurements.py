import pytest
from xdsl.dialects.builtin import IntegerType
from xdsl.ir import Operation

from deltakit_compile.frontend.common._builder import OperationBuilder
from deltakit_compile.frontend.common._exceptions import (
    DifferentBuildersError,
    InvalidMeasurementError,
    InvalidSizeError,
    ObjectNotAttachedError,
)
from deltakit_compile.frontend.common._measurements import (
    MeasurementBit,
    MeasurementRecord,
    MeasurementReg,
)
from tests.unit.frontend.conftest import add_to_builder_with_fake_ssa


def test_raw_measurement_reg_instantiation() -> None:
    MeasurementReg(1)
    MeasurementReg(439857)

    msg = "Got an invalid non-positive number of bits: -1."
    with pytest.raises(InvalidSizeError, match=msg):
        MeasurementReg(-1)

    msg = "Got an invalid non-positive number of bits: 0."
    with pytest.raises(InvalidSizeError, match=msg):
        MeasurementReg(0)


def test_raw_measurement_len() -> None:
    assert MeasurementReg(10).num_bits == 10
    assert len(MeasurementReg(10)) == 10
    assert len(MeasurementBit()) == 1


def test_raw_measurement_reg_hasheq() -> None:
    builder = OperationBuilder()
    mreg = add_to_builder_with_fake_ssa(builder, MeasurementReg(10))
    assert MeasurementReg(10) == MeasurementReg(10)
    assert mreg != MeasurementReg(10)
    assert hash(MeasurementReg(1)) == hash(MeasurementReg(1))
    assert mreg == mreg  # noqa: PLR0124
    assert hash(mreg) == hash(mreg)


def test_raw_measurement_reg_builder_merge() -> None:
    builder = OperationBuilder()
    mreg_sized = add_to_builder_with_fake_ssa(builder, MeasurementReg(3))
    mreg_sized2 = add_to_builder_with_fake_ssa(builder, MeasurementReg(4))

    merged_reg_sized = mreg_sized + mreg_sized2
    assert merged_reg_sized.num_bits == 7

    merged_twice_reg_sizes = mreg_sized + mreg_sized
    assert merged_twice_reg_sizes.num_bits == 6

    merge_of_merge = merged_twice_reg_sizes + merged_reg_sized
    assert merge_of_merge.num_bits == 13

    builder2 = OperationBuilder()
    mreg_other = add_to_builder_with_fake_ssa(builder2, MeasurementReg(3))

    with pytest.raises(DifferentBuildersError):
        _ = mreg_sized + mreg_other


def test_raw_measurement_reg_builder_extract() -> None:
    builder = OperationBuilder()
    mreg_sized = add_to_builder_with_fake_ssa(builder, MeasurementReg(3))

    one_qubit_from_sized = mreg_sized[0]
    assert isinstance(one_qubit_from_sized, MeasurementBit)

    sliced_negative_from_sized = mreg_sized[:-1]
    assert sliced_negative_from_sized.num_bits == 2


def test_raw_measurement_builder_getitem() -> None:
    builder = OperationBuilder()

    sized_reg = add_to_builder_with_fake_ssa(builder, MeasurementReg(10))
    reg = sized_reg[:5]
    assert reg.num_bits == 5
    reg = sized_reg[5:-2]
    assert reg.num_bits == 3

    with pytest.raises(ObjectNotAttachedError):
        MeasurementReg(10)[1]

    with pytest.raises(
        IndexError, match=r"Index 10 is out of range for a MeasurementReg of length 10."
    ):
        sized_reg[10]


def test_raw_measurement_builder_iteration() -> None:
    builder = OperationBuilder()
    sized_reg = add_to_builder_with_fake_ssa(builder, MeasurementReg(10))
    assert all(isinstance(m, MeasurementBit) for m in sized_reg)
    assert len(list(sized_reg)) == 10  # uses __iter__


def test_measurement_bit_type_info() -> None:
    assert MeasurementBit()._type_info == IntegerType(1)


@pytest.mark.parametrize("index", [0, slice(0, 2)])
def test_raw_measurement_ssa_is_recomputed_when_its_source_changes(index: int | slice) -> None:
    """Indexed measurements re-derive their SSA value when their source gets a new one.

    Their SSA value is an extraction from the source, which is cached to avoid adding the same
    operation several times. The cache has to be dropped when the source is given a new SSA value,
    which happens when it escapes a nested region (see ``ParallelScope``).
    """
    builder = OperationBuilder()
    mreg = add_to_builder_with_fake_ssa(builder, MeasurementReg(3))
    indexed = mreg[index]

    first_ssa = indexed.ssa
    # Asking twice does not add a second extraction.
    assert indexed.ssa is first_ssa

    # Give the source a new SSA value, as remapping it onto a parallel result would.
    add_to_builder_with_fake_ssa(builder, mreg)
    assert indexed.ssa is not first_ssa
    extraction = indexed.ssa.owner
    assert isinstance(extraction, Operation)
    assert extraction.operands[0] is mreg.ssa


def test_measurement_record() -> None:
    builder = OperationBuilder()
    mreg = add_to_builder_with_fake_ssa(builder, MeasurementReg(10))
    rec = builder.add_without_ssa(MeasurementRecord())
    for i in range(10):
        rec.append(mreg[i])
        assert len(rec) == i + 1

    with pytest.raises(InvalidMeasurementError):
        rec.append(MeasurementBit())
