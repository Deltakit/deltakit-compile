# (c) Copyright Riverlane 2025-2026. All rights reserved.
from __future__ import annotations

import itertools
from collections.abc import Iterable, Iterator, Sequence
from typing import cast, overload

from typing_extensions import override
from xdsl.dialects.builtin import (
    DYNAMIC_INDEX,
    IntegerAttr,
    TensorType,
)
from xdsl.ir import Attribute, SSAValue
from xdsl.utils.hints import isa

from deltakit_compile.dialects import arith, logical_assembly, tensor
from deltakit_compile.dialects.log_asm_api import CastOp, TensorMergeOp, TensorSliceOp
from deltakit_compile.dialects.qcore import AllocQubitOp, QubitRegType, QubitType
from deltakit_compile.frontend.common._builder import (
    IndexedAPIObject,
    OperationBuilder,
    ParentRegInformation,
    TerminalIndexedAPIObject,
)
from deltakit_compile.frontend.common._exceptions import (
    DifferentBuildersError,
    InvalidSizeError,
    MissingLocationError,
    ObjectNotAttachedError,
)
from deltakit_compile.frontend.common._sequence import (
    _slice_len,
    does_not_contain_none_values,
    is_sequence,
    is_sequence_of,
)
from deltakit_compile.frontend.common._vector import Vector, VectorLike
from deltakit_compile.shared.patch.exceptions import UnplacedPatchError


class Qubit(TerminalIndexedAPIObject["QubitReg"]):
    """A single qubit.

    Args:
        location: Optional location of the single qubit represented. Defaults to no location.
        _parent_information: internal-only argument that should be provided when the object is
            obtained through an indexing.
    """

    def __init__(
        self,
        location: VectorLike[float] | None = None,
        *,
        _parent_information: ParentRegInformation[QubitReg] | None = None,
    ) -> None:
        super().__init__(_parent_information=_parent_information)
        self._location = Vector.as_vector(location) if location is not None else location
        self._cached_slice_op: TensorSliceOp | None = None
        self._cached_ssa: SSAValue | None = None
        self._cached_source_ssa: SSAValue | None = None

    @property
    @override
    def _identifier_prefix(self) -> str:
        return "q"

    @property
    @override
    def _type_info(self) -> Attribute:
        return QubitType()

    @property
    def location(self) -> Vector[float] | None:
        return self._location

    @override
    def __len__(self) -> int:
        return 1

    @property
    @override
    def ssa(self) -> SSAValue:
        if self.is_root_parent:
            return super().ssa
        source_ssa = self.source.ssa
        if (
            self._cached_ssa is None
            or self._cached_slice_op is None
            or self._cached_source_ssa != source_ssa
        ):
            parent = self.parent
            assert isinstance(parent, QubitReg), (
                "Invariant broken: a qubit with a parent should have a register source."
            )
            parent_ssa = parent.ssa  # Get the SSAValue for the parent (potentially adding new ops)
            if not isa(parent_ssa, SSAValue[TensorType]):
                tensor_type = TensorType(
                    QubitType(),
                    (parent.num_qubits if parent.num_qubits is not None else DYNAMIC_INDEX,),
                )
                cast_op = CastOp(parent_ssa, tensor_type)
                self._builder.append_ops_ignoring_ssas(cast_op)
                parent_ssa = cast(SSAValue[TensorType], cast_op.result)

            index = self.index
            assert isinstance(index, int), (
                "Invariant broken: a qubit with a parent should be obtained from an int index."
            )
            idx_slice = slice(index, index + 1, 1) if index >= 0 else slice(index, index - 1, -1)
            new_reg_size = 1
            if (parent_size := parent_ssa.type.get_shape()[0]) != DYNAMIC_INDEX:
                leftover_size = parent_size - new_reg_size
            else:
                leftover_size = DYNAMIC_INDEX

            slice_op = TensorSliceOp(
                parent_ssa,
                TensorType(QubitType(), (new_reg_size,)),
                TensorType(QubitType(), (leftover_size,)),
                start=idx_slice.start,
                stop=idx_slice.stop,
                step=idx_slice.step,
            )
            const_op = arith.ConstantOp(IntegerAttr.from_index_int_value(0))
            extract_qubit_op = tensor.ExtractOp(slice_op.slice, const_op.result, QubitType())
            self._builder.append_ops_ignoring_ssas(slice_op, const_op, extract_qubit_op)
            self._cached_slice_op = slice_op
            self._cached_source_ssa = source_ssa
            self._cached_ssa = extract_qubit_op.result
        return self._cached_ssa

    @override
    def _update_ssa_value(self, ssa: SSAValue) -> None:
        """Update the SSA value of ``self``.
        If ``self`` comes from indexing a parent ``QubitReg``, update the parent's SSA value by
        generating a new parent value that includes ``ssa`` instead of the old value and recursively
        updating parent ``QubitReg`` API objects up to the root ``QubitReg`` API object."""
        if self.is_root_parent:
            super()._update_ssa_value(ssa)
            return

        # Getting the ssa result will ensure there is a valid cached version of the slice op
        _old_ssa = self.ssa
        slice_op = self._cached_slice_op
        assert slice_op is not None, (
            "getting the ssa value should ensure there is a cached slice op"
        )

        index = self.index
        assert isinstance(index, int), (
            "Invariant broken: a qubit with a parent should be obtained from an int index."
        )
        idx_slice = slice(index, index + 1, 1) if index >= 0 else slice(index, index - 1, -1)

        from_elems_op = tensor.FromElementsOp(ssa, result_type=TensorType(QubitType(), (1,)))
        merge_op = TensorMergeOp(
            from_elems_op.result,
            slice_op.leftovers,
            slice_op.input.type,
            start=idx_slice.start,
            stop=idx_slice.stop,
            step=idx_slice.step,
        )
        self._builder.append_ops_ignoring_ssas(from_elems_op, merge_op)

        parent = self.parent
        assert isinstance(parent, QubitReg), (
            "Invariant broken: a qubit's parent must be a QubitReg."
        )
        parent._update_ssa_value(merge_op.result)


class QubitReg(IndexedAPIObject["QubitReg"]):
    """A bare-bone register of qubits.

    This is the base class for all the patches in the LogASM dialect. At its core, this class
    represents a "bag of qubits". Depending on user input, we might know more about the
    represented "bag of qubits":

    - ``QubitReg()`` is a "bag of qubits": it has no idea of the number of qubits contained, no
        particular ordering, it just contains an unknown strictly positive number of qubits.
    - ``QubitReg(num_qubits=<integer>)`` is a list of qubits: we know how many qubits are
        contained in the data-structure, and each qubit is associated with an index.
    - ``QubitReg(qubit_locations=<locations>)`` is also a list of qubits, with a known length
        and an ordering. Additionally, each qubit is assigned to a position.
    - ``QubitReg(num_qubits=<integer>, qubit_locations=<locations>)`` is equivalent to
        ``QubitReg(qubit_locations=<locations>)``.

    So in general, we cannot assume that a ``QubitReg`` is more than a "bag of qubits" with an
    arbitrary strictly positive number of qubits and no particular ordering.

    Args:
        num_qubits: number of qubits contained in the register. If provided, it should be
            strictly positive. If ``qubit_locations`` is also provided, ``len(qubit_locations)``
            should be exactly ``qubit_numbers``.
        qubit_locations: location of each qubit contained in the register. If provided, should
            be non-empty. If ``num_qubits`` is also provided, ``len(qubit_locations)`` should
            be exactly ``num_qubits``.
        _parent_information: internal-only argument that should be provided when the object is
            obtained through an indexing.

    Raises:
        ValueError: if ``qubit_locations`` is provided but is an empty sequence.
        InvalidSizeError: if the provided ``num_qubits`` is not strictly positive or does not match
            with the provided ``qubit_locations`` if the later is also provided.
    """

    def __init__(
        self,
        num_qubits: int | None = None,
        qubit_locations: Sequence[VectorLike[float]] | None = None,
        *,
        _parent_information: ParentRegInformation[QubitReg] | None = None,
    ) -> None:
        if qubit_locations is not None and not qubit_locations:
            msg = "When provided, qubit_locations should be non-empty."
            raise ValueError(msg)
        if num_qubits is not None and num_qubits <= 0:
            msg = (
                f"Invalid number of qubit: {num_qubits}. Expected a strictly positive (> 0) number."
            )
            raise InvalidSizeError(msg)
        if (
            num_qubits is not None
            and qubit_locations is not None
            and num_qubits != len(qubit_locations)
        ):
            msg = f"Got {num_qubits=} but {len(qubit_locations)} locations. They should be equal."
            raise InvalidSizeError(msg)

        super().__init__(_parent_information=_parent_information)

        self._num_qubits: int | None = num_qubits
        if num_qubits is None and qubit_locations is not None:
            self._num_qubits = len(qubit_locations)

        self._qubit_locations: tuple[Vector[float], ...] | None = None
        if qubit_locations is not None:
            self._qubit_locations = tuple(map(Vector.as_vector, qubit_locations))
        self._cached_slice_op: TensorSliceOp | None = None
        self._cached_source_ssa: SSAValue | None = None

    @property
    @override
    def _identifier_prefix(self) -> str:
        return "qreg"

    @property
    def qubit_locations(self) -> tuple[Vector[float], ...] | None:
        return self._qubit_locations

    @qubit_locations.setter
    def qubit_locations(self, new_qubit_locations: Sequence[Vector[float]]) -> None:
        if self.num_qubits is None:
            msg = "Cannot set qubit locations for an unsized register."
            raise InvalidSizeError(msg)
        if len(new_qubit_locations) != self.num_qubits:
            msg = (
                f"Got {len(new_qubit_locations)} qubit locations for a register of "
                f"size {self.num_qubits}. Both sizes should match."
            )
            raise InvalidSizeError(msg)
        self._qubit_locations = tuple(new_qubit_locations)

    @property
    def num_qubits(self) -> int | None:
        return self._num_qubits

    @property
    def is_sized(self) -> bool:
        return self._num_qubits is not None

    @property
    def is_unsized(self) -> bool:
        return not self.is_sized

    @property
    @override
    def _type_info(self) -> Attribute:
        """Get the type information of this instance.

        Returns:
            A string capturing the effective type of the measurement register state this
            ``QubitReg`` refers to.
        """
        return TensorType(
            QubitType(), (DYNAMIC_INDEX if self._num_qubits is None else self._num_qubits,)
        )

    @override
    @property
    def ssa(self) -> SSAValue:
        if self.is_root_parent:
            return super().ssa
        source_ssa = self.source.ssa
        if self._cached_slice_op is None or self._cached_source_ssa != source_ssa:
            parent = self.parent
            assert isinstance(parent, QubitReg), (
                "Invariant broken: a register's parent must be a QubitReg."
            )
            parent_ssa = parent.ssa  # Get the SSAValue for the parent (potentially adding new ops)
            if not isa(parent_ssa, SSAValue[TensorType]):
                tensor_type = TensorType(
                    QubitType(),
                    (parent.num_qubits if parent.num_qubits is not None else DYNAMIC_INDEX,),
                )
                cast_op = CastOp(parent_ssa, tensor_type)
                self._builder.append_ops_ignoring_ssas(cast_op)
                parent_ssa = cast(SSAValue[TensorType], cast_op.result)

            index = self.index
            assert isinstance(index, slice), (
                "Invariant broken: a register with a parent should be obtained from a slice."
            )

            if (parent_size := parent_ssa.type.get_shape()[0]) != DYNAMIC_INDEX:
                new_size = len(range(parent_size)[index])
                leftover_size = parent_size - new_size
            else:
                new_size = DYNAMIC_INDEX
                leftover_size = DYNAMIC_INDEX

            slice_op = TensorSliceOp(
                parent_ssa,
                TensorType(QubitType(), (new_size,)),
                TensorType(QubitType(), (leftover_size,)),
                start=index.start,
                stop=index.stop,
                step=index.step,
            )
            self._builder.append_ops_ignoring_ssas(slice_op)
            self._cached_slice_op = slice_op
            self._cached_source_ssa = source_ssa
        return self._cached_slice_op.slice

    @override
    def _update_ssa_value(self, ssa: SSAValue) -> None:
        """Updates the root parent's ssa value by generating a new ssa value for the parent if it
        exists using the parent information, and only capturing a direct ssa value in the API object
        for root level qubit registers."""
        if self.is_root_parent:
            if self._ssa:
                original_type = self.ssa.type
                if not isa(
                    original_type,
                    QubitRegType | logical_assembly.SurfaceCodeBasePatch | TensorType[QubitType],
                ):
                    msg = (
                        f"QubitReg has unexpected ssa type: {original_type}, "
                        f"expected a qubit register, surface code patch, or qubit tensor"
                    )
                    raise RuntimeError(msg)

                if isa(ssa.type, TensorType[QubitType]) and original_type != ssa.type:
                    cast_op = CastOp(ssa, original_type)
                    self._builder.append_ops_ignoring_ssas(cast_op)
                    ssa = cast_op.result
            super()._update_ssa_value(ssa)
            return

        # Getting the ssa result will ensure there is a valid cached version of the slice op
        _old_ssa = self.ssa
        slice_op = self._cached_slice_op
        assert slice_op is not None, (
            "getting the ssa value should ensure there is a cached slice op"
        )

        index = self.index
        assert isinstance(index, slice), (
            "Invariant broken: a register with a parent should be obtained from a slice."
        )
        merge_op = TensorMergeOp(
            ssa,
            slice_op.leftovers,
            slice_op.input.type,
            start=index.start,
            stop=index.stop,
            step=index.step,
        )
        self._builder.append_ops_ignoring_ssas(merge_op)

        parent = self.parent
        assert isinstance(parent, QubitReg), (
            "Invariant broken: a register's parent must be a QubitReg."
        )
        parent._update_ssa_value(merge_op.result)

    @overload
    def at_location(self, location: Vector[float] | Iterable[float]) -> Qubit: ...
    @overload
    def at_location(self, location: float, *remaining_coords: float) -> Qubit: ...

    def at_location(self, location: VectorLike[float], *remaining_coords: float) -> Qubit:
        """Get the qubit at the provided location.

        Args:
            location: location of the qubit to return.
            *remaining_coords: if ``location`` is a ``float``, contains the remaining coordinates to
                make the full location.

        Raises:
            ValueError: if ``self`` does not contain any location information.

        Returns:
            If the qubits represented by this ``QubitReg`` have a location, return a ``Qubit``
            representing the qubit at the given location that is one of the qubits in this
            ``QubitReg``.
        """
        if isinstance(location, (float, int)):
            location = Vector((location, *remaining_coords))
        location = Vector.as_vector(location)
        if self.qubit_locations is None:
            msg = f"{self.__class__.__name__} instance does not contain any location information."
            raise UnplacedPatchError(msg)
        return self._extract_object_from_index(self.qubit_locations.index(location))

    @override
    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, QubitReg):
            return NotImplemented
        return super().__eq__(value) and self._qubit_locations == value._qubit_locations

    @override
    def __hash__(self) -> int:
        return hash((super().__hash__(), self._qubit_locations))

    @override
    def __len__(self) -> int:
        if self.num_qubits is None:
            msg = f"Cannot get the length of an unsized {QubitReg.__name__}."
            raise InvalidSizeError(msg)
        return self.num_qubits

    def __iter__(self) -> Iterator[Qubit]:
        if self.num_qubits is None:
            msg = f"Cannot iterate through an unsized {QubitReg.__name__}."
            raise InvalidSizeError(msg)
        for index in range(self.num_qubits):
            yield self._extract_object_from_index(index)

    @overload
    def __getitem__(self, index: int) -> Qubit: ...
    @overload
    def __getitem__(self, index: slice) -> QubitReg: ...
    def __getitem__(self, index: int | slice) -> Qubit | QubitReg:
        if not self._is_attached:
            raise ObjectNotAttachedError()
        return self._extract_object_from_index(index)

    @overload
    def _extract_object_from_index(self, index: int) -> Qubit: ...
    @overload
    def _extract_object_from_index(self, index: slice) -> QubitReg: ...
    def _extract_object_from_index(self, index: int | slice) -> Qubit | QubitReg:
        # Getting the size of the new object
        size: int | None = None
        if isinstance(index, int):
            size = 1
            if self.num_qubits is not None and index >= self.num_qubits:
                msg = f"Index {index} is out of range for a QubitReg of length {self.num_qubits}."
                raise IndexError(msg)
        elif isinstance(index, slice) and self.num_qubits is not None:
            size = _slice_len(index, self.num_qubits)
        # Returning a new object of that size.
        new_qubit_locations: tuple[Vector[float], ...] | None = None
        if self.qubit_locations is not None:
            new_qubit_locations = (
                (self.qubit_locations[index],)
                if isinstance(index, int)
                else self.qubit_locations[index]
            )
        if isinstance(index, int):
            # Qubits behave slightly differently than other API objects: they keep a reference to
            # their parent register, and only add operations when the SSA value is explicitly asked
            # by the user.
            return self._builder.add_without_ssa(
                Qubit(
                    new_qubit_locations[0] if new_qubit_locations is not None else None,
                    _parent_information=ParentRegInformation(self, index),
                ),
            )
        return self._builder.add_without_ssa(
            QubitReg(
                size,
                new_qubit_locations,
                _parent_information=ParentRegInformation(self, index),
            ),
        )

    def __add__(self, others: QubitReg | Sequence[Qubit]) -> QubitReg:
        # Checking input type
        if not isinstance(others, QubitReg) and not is_sequence_of(others, Qubit):
            provided_type_str = type(others).__name__
            if is_sequence(others):
                all_types = {type(obj) for obj in others}
                provided_type_str = (
                    f"{type(others).__name__}[{'|'.join(t.__name__ for t in all_types)}]"
                )
            msg = (
                f"Expected either a Sequence[{Qubit.__name__}] or a {QubitReg.__name__} but "
                f"got {provided_type_str}."
            )
            raise TypeError(msg)
        # Checking that the input have the same builder
        if isinstance(others, QubitReg):
            if not self._builder.is_managing(others):
                raise DifferentBuildersError()
        elif any(not self._builder.is_managing(obj) for obj in others):
            raise DifferentBuildersError()

        # Compute the resulting size
        merged_size: int | None = None
        sizes = [
            self.num_qubits,
            others.num_qubits if isinstance(others, QubitReg) else len(others),
        ]
        if does_not_contain_none_values(sizes):
            merged_size = sum(sizes)

        # Compute the resulting location
        old_qubit_locations = [self.qubit_locations]
        if isinstance(others, QubitReg):
            old_qubit_locations.append(others.qubit_locations)
        else:
            old_qubit_locations.extend(
                [(q.location,) if q.location is not None else None for q in others]
            )
        new_qubit_locations: tuple[Vector, ...] | None = None
        if does_not_contain_none_values(old_qubit_locations):
            new_qubit_locations = tuple(itertools.chain.from_iterable(old_qubit_locations))

        return self._builder.append_op_and_update_ssas(
            tensor.ConcatOp(
                [others.ssa] if isinstance(others, QubitReg) else [oth.ssa for oth in others],
                IntegerAttr.from_index_int_value(0),
                TensorType(
                    QubitType(), (merged_size if merged_size is not None else DYNAMIC_INDEX,)
                ),
            ),
            QubitReg(merged_size, new_qubit_locations),
        )

    __radd__ = __add__

    def _set_num_qubits_and_locations(
        self,
        num_qubits: int,
        qubit_locations: Sequence[VectorLike[float]] | None = None,
    ) -> None:
        if qubit_locations is None:
            # If ``self`` has some qubit locations, ``qubit_locations`` should be provided.
            if self._qubit_locations is not None:
                msg = (
                    "Locations of the new qubits should be provided when resizing a register "
                    "with locations."
                )
                raise MissingLocationError(msg)
        else:
            # Ensuring that the provided qubit_locations is a tuple[Vector, ...] | None
            qubit_locations = tuple(Vector.as_vector(entry) for entry in qubit_locations)
            # If ``qubit_locations`` is provided, it should match the ``num_qubits``.
            if len(qubit_locations) != num_qubits:
                msg = f"Expected {num_qubits} locations but only {len(qubit_locations)} provided."
                raise InvalidSizeError(msg)
        self._num_qubits = num_qubits
        self._qubit_locations = qubit_locations

    def _declare_in_builder(self, builder: OperationBuilder) -> None:
        """Method used by the LogASM API to create a new qubit register / patch value.

        Note:
            This method is supposed to only be used in LogASM API, where unsized registers are not
            allowed. This is why it raises if ``self`` represents an unsized register.

        Args:
            builder: builder to add the declaration operation(s) to.

        Raises:
            InvalidSizeError: if ``self`` represents an unsized register (see note).
        """
        if self.num_qubits is None:
            msg = "Cannot declare an unsized register in a LogASM context."
            raise InvalidSizeError(msg)
        alloc_op = AllocQubitOp([QubitRegType(self.num_qubits)], coordinates=self._qubit_locations)
        cast_op = CastOp(alloc_op.result[0], TensorType(QubitType(), (self.num_qubits,)))
        builder.append_ops_and_update_ssas((alloc_op, cast_op), (cast_op.result,), (self,))


def number_of_qubits(obj: Qubit | QubitReg) -> int | None:
    """Get the number of qubits represented by ``obj``.

    Args:
        obj: the qubit or register of qubits to return the size of.

    Returns:
        ``1`` if a ``Qubit`` instance is given. ``None`` if an unsized ``QubitReg`` instance is
        given. Else, the size of the provided ``QubitReg`` instance.
    """
    return 1 if isinstance(obj, Qubit) else obj._num_qubits
