# (c) Copyright Riverlane 2025-2026. All rights reserved.
from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import overload

from typing_extensions import override
from xdsl.dialects.builtin import IntegerAttr, IntegerType, TensorType
from xdsl.ir import Attribute, SSAValue

from deltakit_compile.dialects import arith, tensor
from deltakit_compile.frontend.common._builder import (
    BaseAPIObject,
    IndexedAPIObject,
    ParentRegInformation,
    TerminalIndexedAPIObject,
)
from deltakit_compile.frontend.common._exceptions import (
    DifferentBuildersError,
    InvalidMeasurementError,
    InvalidSizeError,
    ObjectNotAttachedError,
)
from deltakit_compile.frontend.common._sequence import _slice_len


class MeasurementBit(TerminalIndexedAPIObject["MeasurementReg"]):
    """A single bit obtained from a measurement."""

    def __init__(
        self,
        *,
        _parent_information: ParentRegInformation[MeasurementReg] | None = None,
    ) -> None:
        super().__init__(_parent_information=_parent_information)
        self._cached_ssa: SSAValue | None = None
        self._cached_source_ssa: SSAValue | None = None

    @property
    @override
    def _identifier_prefix(self) -> str:
        return "b"

    @property
    @override
    def _type_info(self) -> Attribute:
        return IntegerType(1)

    @override
    def __len__(self) -> int:
        return 1

    @override
    @property
    def ssa(self) -> SSAValue:
        # If self does not have a parent register, just use the regular SSA.
        if self.is_root_parent:
            return super().ssa
        # The source SSA value changes when the source escapes a nested region (see
        # ``ParallelScope``), in which case the cached extraction is stale and has to be redone.
        source_ssa = self.source.ssa
        if self._cached_ssa is None or self._cached_source_ssa != source_ssa:
            # Else, only do the qubit extraction directly from the source here.
            source = self.source
            assert isinstance(source, MeasurementReg), (
                "Invariant broken: a bit with a parent should have a register source."
            )
            index = self.resolve_index()
            assert index is not None, "Expected an non-None index because self does have a parent."
            # And get the bit
            const_op = arith.ConstantOp(IntegerAttr.from_index_int_value(index))
            extract_bit_op = tensor.ExtractOp(source.ssa, const_op.result, IntegerType(1))
            self._builder.append_ops_ignoring_ssas(const_op)
            # Note: we do not update ``self._ssa`` here, because it will not be used anyway.
            self._builder.append_ops_ignoring_ssas(extract_bit_op)
            self._cached_ssa = extract_bit_op.result
            self._cached_source_ssa = source_ssa
        return self._cached_ssa


class MeasurementReg(IndexedAPIObject["MeasurementReg"]):
    """A register containing measurement result(s).

    This class represents a "bag of bits" of a given size.

    Args:
        num_bits: number of bits contained in the classical register. Should be strictly
            positive.
        _parent_information: internal-only argument that should be provided when the object is
            obtained through an indexing.

    Raises:
        InvalidSizeError: if ``num_bits`` is not strictly positive.
    """

    def __init__(
        self,
        num_bits: int,
        *,
        _parent_information: ParentRegInformation[MeasurementReg] | None = None,
    ) -> None:
        if num_bits < 1:
            msg = f"Got an invalid non-positive number of bits: {num_bits}."
            raise InvalidSizeError(msg)
        super().__init__(_parent_information=_parent_information)
        self._num_bits = num_bits
        self._cached_ssa: SSAValue | None = None
        self._cached_source_ssa: SSAValue | None = None

    @property
    def num_bits(self) -> int:
        return self._num_bits

    @property
    @override
    def _identifier_prefix(self) -> str:
        return "meas"

    @property
    @override
    def _type_info(self) -> Attribute:
        return TensorType(IntegerType(1), (self._num_bits,))

    @override
    def __len__(self) -> int:
        return self._num_bits

    @override
    @property
    def ssa(self) -> SSAValue:
        if self.is_root_parent:
            return super().ssa
        # See the note in ``MeasurementBit.ssa`` about why the cache has to be invalidated.
        source_ssa = self.source.ssa
        if self._cached_ssa is None or self._cached_source_ssa != source_ssa:
            source = self.source
            assert isinstance(source, MeasurementReg), (
                "Invariant broken: a register with a parent should have a register source."
            )
            index = self.index
            assert isinstance(index, slice), (
                "Invariant broken: a register with a parent should be obtained from a slice."
            )
            extract_register_op = tensor.ExtractSliceOp.from_static_parameters(
                source.ssa,
                offsets=[index.start if index.start is not None else 0],
                sizes=[self._num_bits],
                strides=[index.step if index.step is not None else 1],
            )
            self._builder.append_ops_ignoring_ssas(extract_register_op)
            self._cached_ssa = extract_register_op.result
            self._cached_source_ssa = source_ssa
        return self._cached_ssa

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MeasurementReg):
            return NotImplemented
        return super().__eq__(other) and self._num_bits == other._num_bits

    @override
    def __hash__(self) -> int:
        return hash((super().__hash__(), self._num_bits))

    def __iter__(self) -> Iterator[MeasurementBit]:
        for index in range(self.num_bits):
            yield self[index]

    @overload
    def __getitem__(self, index: int) -> MeasurementBit: ...
    @overload
    def __getitem__(self, index: slice) -> MeasurementReg: ...
    def __getitem__(self, index: int | slice) -> MeasurementBit | MeasurementReg:
        """Get a new instance representing a subset of ``self``.

        Args:
            index: which item(s) to return.

        Raises:
            ObjectNotAttachedError: if ``self`` is not attached to any builder.

        Returns:
            A new instance representing the indexed items.
        """
        if not self._is_attached:
            raise ObjectNotAttachedError()

        if isinstance(index, int):
            if index >= self.num_bits:
                msg = (
                    f"Index {index} is out of range for a MeasurementReg of length {self.num_bits}."
                )
                raise IndexError(msg)

            return self._builder.add_without_ssa(
                MeasurementBit(_parent_information=ParentRegInformation(self, index))
            )

        size = _slice_len(index, self._num_bits)
        return self._builder.add_without_ssa(
            MeasurementReg(size, _parent_information=ParentRegInformation(self, index)),
        )

    def __add__(self, others: MeasurementReg | Sequence[MeasurementBit]) -> MeasurementReg:
        builder_objects_sequence = (others,) if not isinstance(others, Sequence) else others

        if any(not self._builder.is_managing(obj) for obj in builder_objects_sequence):
            raise DifferentBuildersError()

        merged_size: int = sum(
            [
                self.num_bits,
                others.num_bits if isinstance(others, MeasurementReg) else len(others),
            ]
        )
        # Returning a new object of that size.
        return self._builder.append_op_and_update_ssas(
            tensor.ConcatOp(
                [self.ssa, *(oth.ssa for oth in builder_objects_sequence)],
                IntegerAttr.from_index_int_value(0),
                TensorType(IntegerType(1), (merged_size,)),
            ),
            MeasurementReg(merged_size),
        )

    __radd__ = __add__

    def unpack(self) -> tuple[MeasurementBit, ...]:
        """Unpacks the register into its constituent bits."""
        return tuple(self[i] for i in range(self.num_bits))


class MeasurementRecord(BaseAPIObject):
    """A record of an arbitrary number of measurements.

    This class holds an arbitrary number of measurements and allows to access them via indexing.
    A single measurement can be in several records without any issue.

    Args:
        measurements: a sequence of measurement that will be added to the record before retuning it.
    """

    def __init__(self, measurements: Sequence[MeasurementBit] | None = None) -> None:
        super().__init__()
        self._measurements = [] if measurements is None else list(measurements)

    def _is_valid_measurement(self, measurement: MeasurementBit) -> bool:
        return isinstance(measurement, MeasurementBit) and self._builder.is_managing(measurement)

    def append(self, measurement: MeasurementBit) -> None:
        """Append a measurement to the record.

        Args:
            measurement: the measurement to append to the record.

        Raises:
            InvalidMeasurementError: if the the provided measurement is not managed by the correct
                builder or if it has a size different from ``1``.
        """
        if not self._is_valid_measurement(measurement):
            raise InvalidMeasurementError()
        self._measurements.append(measurement)

    def __getitem__(self, index: int) -> MeasurementBit:
        return self._measurements[index]

    def __len__(self) -> int:
        return len(self._measurements)

    @property
    @override
    def _identifier_prefix(self) -> str:
        return "rec"
