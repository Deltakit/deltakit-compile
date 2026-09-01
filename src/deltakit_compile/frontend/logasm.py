# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""
Module for building logical assembly quantum circuits.

This module provides the Logical Assembly (LogASM) dialect API. It allows users to create
LogASM programs within Python.
"""

from __future__ import annotations

import functools
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Generic, Literal, ParamSpec, TypeAlias, TypeGuard, TypeVar, cast, overload

from typing_extensions import override
from xdsl.dialects.builtin import ArrayAttr, IntAttr, ModuleOp, NoneAttr, TensorType
from xdsl.ir import Attribute, Block, Region, SSAValue, StringIO
from xdsl.parser import FloatAttr
from xdsl.printer import Printer
from xdsl.traits import SymbolTable
from xdsl.utils.hints import isa

from deltakit_compile.dialects import func
from deltakit_compile.dialects import log_asm_api as api
from deltakit_compile.dialects.logical_assembly import (
    GateTypeEnum,
    GrowOp,
    MeasStabOp,
    MeasureOp,
    MoveOp,
    MultiPauliMeasOp,
    OrientationEnum,
    PatchDeclarationOp,
    PlacementAttr,
    PrepareOp,
    RotatedPlanarPatchType,
    RotateOp,
    ShrinkOp,
    StepOp,
    SurfaceCodeBasePatch,
    TransversalGateOp,
)
from deltakit_compile.dialects.qcore import PauliAttr, QubitType
from deltakit_compile.frontend.common._builder import (
    BaseAPIObject,
    OperationBuilder,
    SubCallablesBuilder,
    all_objects_managed_by_same_builder,
)
from deltakit_compile.frontend.common._classical_expr import ClassicalExpression, Result
from deltakit_compile.frontend.common._exceptions import (
    ArgumentError,
    DifferentBuildersError,
    IdentifierConflictError,
    InvalidSizeError,
    MissingLocationError,
)
from deltakit_compile.frontend.common._pauli import Pauli, PauliType
from deltakit_compile.frontend.common._program_builder import (
    Program,
    ProgramBuilder,
    ProgramReturnType,
)
from deltakit_compile.frontend.common._qubit_reg import Qubit, QubitReg
from deltakit_compile.frontend.common._sequence import does_not_contain_none_values
from deltakit_compile.frontend.common._vector import Vector, VectorLike
from deltakit_compile.shared.patch.exceptions import UnplacedPatchError, UnsizedPatchError
from deltakit_compile.shared.patch.rotated_planar._ascii import render_rotated_planar_patch_ascii
from deltakit_compile.shared.patch.rotated_planar._placement import patch_properties_to_coordinates

GateType: TypeAlias = Literal["X", "Z", "H"]


def _is_collection_of_patch_types(
    obj: Collection[Any],
) -> TypeGuard[Collection[RotatedPlanarPatchType]]:
    return all(isinstance(p, RotatedPlanarPatchType) for p in obj)


def _find_bridges_basis(
    patch: SurfaceCodeBasePatch, bridges: Collection[SurfaceCodeBasePatch]
) -> PauliAttr:
    """Compute the initialisation / measurement basis of the bridge(s).

    Args:
        patch: a patch connected with exactly one bridge in ``bridges``.
        bridges: a collection of bridges containing a single bridge connected to ``patch``.

    Raises:
        RuntimeError: if ``patch`` does not have an orientation or if no bridge in ``bridges`` is
            connected to ``patch``.

    Returns:
        The basis in which each bridge should be reset and measured.
    """
    if patch.orientation_data is None:
        msg = "Cannot find bridge basis from unoriented patch."
        raise MissingLocationError(msg)

    # Computing the initialisation / measurement basis of the bridge(s). This basis depends on
    # where the bridge connects to one of the the other patches, and is the same for all bridges in
    # a given operation of 2 logical patches. So we only need to find one bridge that connects to
    # the provided patch and devise the reset/measurement basis from that patch.
    basis: PauliAttr | None = None
    bbox = patch.bounding_box
    vertical_z = patch.orientation_data == OrientationEnum.VERTICAL_Z
    assert bbox is not None, "Patch should be located as checked in pre-conditions."
    tl, br = bbox.top_left, bbox.bottom_right

    for bridge in bridges:
        bridge_bbox = bridge.bounding_box
        assert bridge_bbox is not None, "Bridge should be located as checked in pre-conditions."
        # bbl, btr: bridge bottom-left, bridge top-right
        bbl, btr = bridge_bbox.bottom_left, bridge_bbox.top_right
        if bbl == br or btr == tl:
            # Bridge is in the horizontal direction.
            basis = PauliAttr.X() if vertical_z else PauliAttr.Z()
        elif bbl == tl or btr == br:
            # Bridge is in the vertical direction
            basis = PauliAttr.Z() if vertical_z else PauliAttr.X()
        else:
            # Bridge is not connected.
            continue
    if basis is None:
        msg = "Could not find a bridge connecting the moved patch."
        raise RuntimeError(msg)
    return basis


class RotatedPlanarPatch(QubitReg):
    """A QubitReg organised into a rotated planar surface code.

    Args:
        width: width of the patch to create.
        height: height for the patch to create.
        location: location of the origin of the patch. Defaults to ``None`` which translates into an
            unlocated patch.
        origin: origin on the patch, in patch-coordinates. Defaults to ``None`` which corresponds to
            the bottom-left-most qubit in the patch footprint.
        vertical_z: If ``True``, the ``Z`` observable is vertical. Else, it is horizontal. Defaults
            to True.
    """

    @overload
    def __init__(
        self,
        width: int,
        height: int,
        *,
        location: VectorLike[float] | None = None,
        origin: VectorLike[float] | None = None,
        vertical_z: bool = True,
    ): ...
    @overload
    def __init__(self): ...

    def __init__(
        self,
        width: int | None = None,
        height: int | None = None,
        *,
        location: VectorLike[float] | None = None,
        origin: VectorLike[float] | None = None,
        vertical_z: bool = True,
    ):
        self._width = width
        self._height = height
        self._location: Vector[float] | None = (
            Vector.as_vector(location) if location is not None else None
        )
        self._vertical_z = vertical_z
        if width is None or height is None:
            qubit_count = None
            qubit_locations = None
            # TODO: Unsized patch in logasm_api dialect
            msg = "Unsized patches are not supported yet in the LogASM API."
            raise NotImplementedError(msg)
        local_locations = self.local_structure(width, height)
        qubit_count = len(local_locations)
        if location is None:
            qubit_locations = None
        else:
            shift = Vector[float].as_vector(location)
            if origin is not None:
                shift -= Vector[float].as_vector(origin)
            qubit_locations = [loc + shift for loc in local_locations]
        super().__init__(num_qubits=qubit_count, qubit_locations=qubit_locations)

    @staticmethod
    def from_attribute(attr: RotatedPlanarPatchType) -> RotatedPlanarPatch:
        if attr.orientation_data is None:
            msg = (
                f"Cannot create a {RotatedPlanarPatch.__name__} instance from a "
                f"{RotatedPlanarPatchType.__name__} that does not have an observable orientation."
            )
            raise RuntimeError(msg)
        vertical_z = attr.orientation_data == OrientationEnum.VERTICAL_Z
        return RotatedPlanarPatch(
            *attr.size_data, location=attr.placement_data, vertical_z=vertical_z
        )

    @property
    @override
    def _type_info(self) -> Attribute:
        assert self._width is not None, "Unsized patches are not supported yet"
        assert self._height is not None, "Unsized patches are not supported yet"
        size = ArrayAttr([IntAttr(self._width), IntAttr(self._height)])
        orientation = (
            OrientationEnum.VERTICAL_Z if self._vertical_z else OrientationEnum.HORIZONTAL_Z
        )
        placement: PlacementAttr | NoneAttr = NoneAttr()
        if self._qubit_locations is not None:
            placement = PlacementAttr(list(self.location), orientation)
        return RotatedPlanarPatchType(size, placement)

    @staticmethod
    def _best_effort_bridges(patches: Collection[Attribute]) -> tuple[RotatedPlanarPatchType, ...]:
        """Try to find bridges that connect the given ``patches``.

        This method works on a best-effort basis: it handles some cases considered trivial, and will
        return an empty list of bridges as soon as the provided ``patches`` do not fit within these
        trivial cases.

        For the moment, this function only handles 2 patches aligned on one axis (same position and
        same size on that axis).

        Args:
            patches: collection of patches that should be connected with bridges.

        Returns:
            an empty tuple if the provided ``patches`` do not fit the supported cases, else a tuple
            containing the patch type of bridges that connect the provided ``patches``.
        """
        if len(patches) != 2 or not _is_collection_of_patch_types(patches):
            return ()
        p1, p2 = patches
        if (
            p1.placement_data is None
            or p2.placement_data is None
            or p1.orientation_data is None
            or p2.orientation_data is None
            or p1.orientation_data != p2.orientation_data
        ):
            return ()
        orientation = p1.orientation_data
        p1x, p1y, p2x, p2y = *p1.placement_data, *p2.placement_data
        s1x, s1y, s2x, s2y = *p1.size_data, *p2.size_data

        origin: tuple[float, float]
        size: tuple[int, int]
        # Vertical bridging case: same x-position and width.
        if p1x == p2x and s1x == s2x:
            y_gap_start = min(p1y + s1y, p2y + s2y)
            y_gap_size = max(p1y, p2y) - y_gap_start
            if abs(round(y_gap_size) - y_gap_size) > 1e-6:
                msg = (
                    f"Expected an integer-valued size but computed a bridge of size {y_gap_size} "
                    "to bridge two patches."
                )
                raise InvalidSizeError(msg)
            origin = (p1x, y_gap_start)
            size = (s1x, round(y_gap_size))
        # Horizontal bridging case: same y-position and height.
        elif p1y == p2y and s1y == s2y:
            x_gap_start = min(p1x + s1x, p2x + s2x)
            x_gap_size = max(p1x, p2x) - x_gap_start
            if abs(round(x_gap_size) - x_gap_size) > 1e-6:
                msg = (
                    f"Expected an integer-valued size but computed a bridge of size {x_gap_size} "
                    "to bridge two patches."
                )
                raise InvalidSizeError(msg)
            origin = (x_gap_start, p1y)
            size = (round(x_gap_size), s1y)
        else:
            # Not aligned on one axis with matching size on that axis.
            return ()

        if any(s <= 0 for s in size):
            # Bridge is empty, so there is no need to add a bridge.
            return ()
        size_attr = ArrayAttr[IntAttr].get(tuple(map(IntAttr, size)))
        placement = PlacementAttr(
            ArrayAttr[FloatAttr].get(tuple(FloatAttr(v, 64) for v in origin)), orientation
        )
        return (RotatedPlanarPatchType(size_attr, placement),)

    @property
    def location(self) -> Vector[float]:
        """Returns the location of the patch defined as the bottom left-most corner of the
        rectangular boundary that includes the outer most ancilla qubits."""
        if self._height is None or self._width is None:
            msg = "Unsized patches cannot have a location."
            raise ValueError(msg)
        if self.qubit_locations is None:
            msg = "Patch has no location. Provide a location at patch construction."
            raise UnplacedPatchError(msg)
        return self.qubit_locations[0] - self.local_structure(self._height, self._width)[0]

    @overload
    def at_relative_location(self, location: VectorLike[float]) -> Qubit: ...
    @overload
    def at_relative_location(self, location: float, y: float) -> Qubit: ...

    def at_relative_location(
        self, location: VectorLike[float] | float, y: float | None = None
    ) -> Qubit:
        """If the qubits represented by this QubitReg have a location, return a QubitReg
        representing the qubits at the given location that are a subset of the qubits in this
        QubitReg."""
        if isinstance(location, (float, int)):
            assert y is not None
            location = Vector(location, y)
        else:
            location = Vector.as_vector(location)
        if self.qubit_locations is None:
            msg = "Patch does not have location data."
            raise UnplacedPatchError(msg)
        origin = self.location
        return self.at_location(location + origin)

    def prepare(self, basis: PauliType) -> None:
        """Prepare this patch in a particular Pauli basis."""
        basis = basis.to_qcore_attr() if isinstance(basis, Pauli) else PauliAttr.coerce(basis)
        self._builder.append_op_and_update_ssas(PrepareOp(self.ssa, basis), self)

    def measure(self, basis: PauliType) -> Result:
        """Measure the logical qubit given by this patch, and return an expression for the
        corrected logical result."""
        basis = basis.to_qcore_attr() if isinstance(basis, Pauli) else PauliAttr.coerce(basis)
        return self._builder.append_op_and_update_ssas(MeasureOp(self.ssa, basis), Result())

    def measure_stabilisers(self, min_rounds: int | None = None) -> None:
        """
        Measure stabilisers for this code.

        If min_rounds is not given, a suitable minimum is chosen at compile time for the size of the
        patch.
        """
        if min_rounds is None:
            distances: set[int] = cast(set[int], {self._width, self._height} - {None})
            min_rounds = min(distances, default=1)  # TODO: Double check default here.
        self._builder.append_op_and_update_ssas(MeasStabOp(self.ssa, min_rounds), self)

    def move(
        self,
        offset: VectorLike[int],
        bridges: Sequence[RotatedPlanarPatch] | None = None,
        rounds: int | None = None,
    ) -> None:
        """
        Perform a move operation on this patch.

        If given, the bridges must connect the current position of the patch to it's new position.
        If not given, the compiler will attempt to calculate a path.
        """
        if self._width is None or self._height is None:
            msg = "Cannot move a patch without both of width and height. Please provide both."
            raise InvalidSizeError(msg)
        if self._location is None or (
            bridges is not None and any(bridge._location is None for bridge in bridges)
        ):
            msg = "All patches and bridges involved in a move need to be located."
            raise MissingLocationError(msg)

        offset = Vector.as_vector(offset)
        input_type = cast(RotatedPlanarPatchType, self.ssa.type)
        new_placement = (
            input_type.placement.with_offset(tuple(offset))
            if not isinstance(input_type.placement, NoneAttr)
            else NoneAttr()
        )
        moved_patch = RotatedPlanarPatchType(size=input_type.size, placement=new_placement)
        if bridges is None:
            bridge_types = RotatedPlanarPatch._best_effort_bridges((input_type, moved_patch))
            # Declaring the bridges
            bridges = [
                self._builder.append_op_and_update_ssas(
                    PatchDeclarationOp(btype), RotatedPlanarPatch.from_attribute(btype)
                )
                for btype in bridge_types
            ]

        # Preparing the bridges in the correct basis.
        if bridges:
            basis = _find_bridges_basis(
                input_type, [cast(SurfaceCodeBasePatch, bridge.ssa.type) for bridge in bridges]
            )
            bridges = [
                self._builder.append_op_and_update_ssas(PrepareOp(bridge.ssa, basis), bridge)
                for bridge in bridges
            ]

        if rounds is None:
            rounds = min(self._width, self._height)
        op = MoveOp(
            self.ssa,
            rounds,
            [b.ssa for b in bridges],
            RotatedPlanarPatchType(size=input_type.size, placement=new_placement),
        )
        self._builder.append_op_and_update_ssas(op, self)
        if self.qubit_locations:
            self.qubit_locations = [loc + offset for loc in self.qubit_locations]

        # Measuring the bridges in the correct basis.
        if bridges:
            for bridge in bridges:
                self._builder.append_ops_ignoring_ssas(MeasureOp(bridge.ssa, basis))

    def step(self, offset: VectorLike[int]) -> None:
        """Step the code by the given offset, where no bridges are required because the offset is
        small."""
        offset = Vector.as_vector(offset)
        input_type = cast(RotatedPlanarPatchType, self.ssa.type)
        new_placement = (
            input_type.placement.with_offset(tuple(offset))
            if not isinstance(input_type.placement, NoneAttr)
            else NoneAttr()
        )
        op = StepOp(self.ssa, RotatedPlanarPatchType(size=input_type.size, placement=new_placement))
        self._builder.append_op_and_update_ssas(op, self)
        if self.qubit_locations:
            self.qubit_locations = [loc + offset for loc in self.qubit_locations]

    def rotate(
        self,
        offset: VectorLike[int],
        rounds: int | None = None,
        bridges: Sequence[RotatedPlanarPatch] | None = None,
    ) -> None:
        """Rotate this patch 90 degrees, with the given offset."""
        if self._width is None or self._height is None:
            msg = "Cannot rotate a patch without both of width and height. Please provide both."
            raise InvalidSizeError(msg)
        if bridges is None:
            bridges = ()

        offset = Vector.as_vector(offset)
        input_type = cast(RotatedPlanarPatchType, self.ssa.type)
        new_placement = (
            input_type.placement.with_offset(tuple(offset)).rotated()
            if not isinstance(input_type.placement, NoneAttr)
            else NoneAttr()
        )

        op = RotateOp(
            cast(SSAValue[SurfaceCodeBasePatch], self.ssa),
            # TODO: check validity of the below number of rounds.
            rounds if rounds is not None else min(self._width, self._height),
            RotatedPlanarPatchType(size=input_type.size, placement=new_placement),
            bridges=[cast(SSAValue[SurfaceCodeBasePatch], bridge.ssa) for bridge in bridges],
        )
        self._builder.append_op_and_update_ssas(op, self)
        if self.qubit_locations:
            self.qubit_locations = [loc + offset for loc in self.qubit_locations]
        self._vertical_z = not self._vertical_z
        self._width, self._height = self._height, self._width

    def grow(
        self,
        *,
        top: int = 0,
        bottom: int = 0,
        left: int = 0,
        right: int = 0,
        rounds: int | None = None,
    ) -> None:
        """Grow this patch in each direction by the given amounts."""
        self._resize(top, bottom, left, right)
        input_type = cast(RotatedPlanarPatchType, self.ssa.type)
        new_type = input_type.with_offset_size((right + left, top + bottom))
        if not isinstance(input_type.placement, NoneAttr):
            new_type = new_type.with_new_placement(
                input_type.placement.with_offset((-left, -bottom))
            )
        # TODO: check validity of the below number of rounds.
        op = GrowOp(self.ssa, rounds if rounds is not None else 1, new_type)
        self._builder.append_op_and_update_ssas(op, self)

    def shrink(
        self,
        *,
        top: int = 0,
        bottom: int = 0,
        left: int = 0,
        right: int = 0,
        rounds: int | None = None,
    ) -> None:
        """Shrink this patch in each direction by the given amounts."""
        self._resize(-top, -bottom, -left, -right)
        input_type = cast(RotatedPlanarPatchType, self.ssa.type)

        new_type = input_type.with_offset_size((-right - left, -top - bottom))
        if not isinstance(input_type.placement, NoneAttr):
            new_type = new_type.with_new_placement(
                input_type.placement.with_offset((+left, +bottom))
            )
        # TODO: check validity of the below number of rounds.
        op = ShrinkOp(self.ssa, rounds if rounds is not None else 1, new_type)
        self._builder.append_op_and_update_ssas(op, self)

    def _resize(self, top: int, bottom: int, left: int, right: int) -> None:
        """Helper method to recalculate the patch's size."""
        if self._width is None or self._height is None:
            msg = "Cannot resize a patch without width or height. Please provide both."
            raise InvalidSizeError(msg)
        new_width = self._width + left + right
        new_height = self._height + top + bottom
        if new_width <= 0:
            msg = f"Cannot resize a patch to a negative or zero width: {new_width}"
            raise InvalidSizeError(msg)
        if new_height <= 0:
            msg = f"Cannot resize a patch to a negative or zero height: {new_height}"
            raise InvalidSizeError(msg)
        self._width = new_width
        self._height = new_height
        unshifted_locations: list[Vector[float]] = self.local_structure(new_width, new_height)
        new_locations: list[Vector[float]] | None = None
        if self.qubit_locations is not None:
            old_lx, old_ly = self.location
            new_lx, new_ly = old_lx - left, old_ly - bottom
            new_locations = [Vector(x + new_lx, y + new_ly) for x, y in unshifted_locations]
        self._set_num_qubits_and_locations(len(unshifted_locations), new_locations)

    @classmethod
    def local_structure(cls, width: int, height: int) -> list[Vector[float]]:
        """The internal qubit structure of this rotated planar code."""
        return list(map(Vector, patch_properties_to_coordinates(width, height, 0, 0)))

    def transversal(self, gate: Literal["X", "Z", "H"]) -> None:
        """Apply a gate transversally across all qubits in the RotatedPlanarPatch."""
        op = TransversalGateOp([self.ssa], GateTypeEnum(gate))
        self._builder.append_op_and_update_ssas(op, self)

    @override
    def _declare_in_builder(self, builder: OperationBuilder) -> None:
        builder.append_op_and_update_ssas(
            PatchDeclarationOp(cast(RotatedPlanarPatchType, self._type_info)), self
        )

    def to_ascii(self, axes: bool = True) -> str:
        """Return an ASCII representation of the patch.

        Args:
            axes: if ``True`` and ``self`` has a location, will print axes around the patch to show
                coordinates.

        Returns:
            an ASCII representation of the patch.
        """
        if self._width is None or self._height is None:
            msg = "Cannot get the ASCII representation of unsized patches."
            raise UnsizedPatchError(msg)

        location = None
        if self.qubit_locations is not None:
            location_x, location_y = self.location
            location = (float(location_x), float(location_y))

        return render_rotated_planar_patch_ascii(
            width=self._width,
            height=self._height,
            points=self.local_structure(self._width, self._height),
            location=location,
            axes=axes,
        )


LogASMArgumentType: TypeAlias = QubitReg | Result
_LogASMArgumentType = TypeVar("_LogASMArgumentType", bound=LogASMArgumentType)
LogASMPatchType = TypeVar("LogASMPatchType", bound=QubitReg)
P = ParamSpec("P")
LogASMResultsType: TypeAlias = ProgramReturnType | tuple[ProgramReturnType, ...] | None
LogASMOutputType = TypeVar("LogASMOutputType", bound=LogASMResultsType)


@overload
def _is_logasm_argument_sequence(value: list[Any]) -> TypeGuard[list[LogASMArgumentType]]: ...
@overload
def _is_logasm_argument_sequence(
    value: tuple[Any, ...],
) -> TypeGuard[tuple[LogASMArgumentType, ...]]: ...
def _is_logasm_argument_sequence(value: Sequence[Any]) -> TypeGuard[Sequence[LogASMArgumentType]]:
    return all(isinstance(v, LogASMArgumentType) for v in value)


class InstantiatedLogAsmSubroutine(Generic[P, LogASMOutputType]):
    """
    A wrapper to represent a ``LogAsmSubroutine`` instance that has been instantiated with specific
    inputs.

    The only way to produce an instance of this class is to call ``LogAsmSubroutine.__call__``.

    Arguments:
        module: ``builtin.module`` operation containing a ``func.func`` operation named
            entry_point_identifier, and all other function and subroutines it depends on.
            This is specifically the same ``builtin.module`` operation instance from the
            ``LogAsmSubroutine``.
        entry_point_identifier: The name of the entry point function in ``module``
        results: Python type of the results returned by the instantiated ``LogAsmSubroutine``.
        *args: an arbitrary number of inputs to give to the represented subroutine. The number and
            order of provided inputs should exactly match the number and order of arguments
            required by the subroutine.
        **kwargs: an empty collection. This will raise if any kwargs is provided.
    """

    def __init__(
        self,
        module: ModuleOp,
        entry_point_identifier: str,
        results: LogASMOutputType,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        assert not kwargs, "Should be guaranteed by caller."
        assert _is_logasm_argument_sequence(args), "Should be guaranteed by caller."
        self._module = module
        self._entry_point_identifier = entry_point_identifier
        self._results = results
        self._arguments = args

    @property
    def module(self) -> ModuleOp:
        return self._module

    @property
    def entry_point_identifier(self) -> str:
        return self._entry_point_identifier

    @functools.cached_property
    def func_op(self) -> func.FuncOp:
        op = SymbolTable.lookup_symbol(self.module, self.entry_point_identifier)
        assert isinstance(op, func.FuncOp)
        return op

    @functools.cached_property
    def called_subroutines(self) -> Mapping[str, func.FuncOp | api.CircuitDeclarationOp]:
        return {
            op.sym_name.data: op
            for op in self.module.ops
            if isinstance(op, func.FuncOp | api.CircuitDeclarationOp)
            and op.sym_name.data != self.entry_point_identifier
        }

    @property
    def outer_arguments(self) -> tuple[BaseAPIObject, ...]:
        return self._arguments

    @property
    def identifier(self) -> str:
        return self.entry_point_identifier

    @property
    def results_tuple(self) -> tuple[ProgramReturnType, ...]:
        if self._results is None:
            return ()
        if isinstance(self._results, ProgramReturnType):
            return (self._results,)
        return self._results


class LogAsmSubroutine(Generic[P, LogASMOutputType]):
    """An immutable Logical Assembly subroutine that can be called from a LogAsmBuilder.

    Arguments:
        module: A ModuleOp containing a ``func.func`` operation named by ``entry_point_identifier``,
            as well as all the other functions or circuits it depends on.
        entry_point_identifier: The name of the entry point function in ``module``
        results: Python type of the results returned by the instantiated ``LogAsmSubroutine``.
        *args: an arbitrary number of inputs to give to the represented subroutine. The number and
            order of provided inputs should exactly match the number and order of arguments
            required by the subroutine.
        **kwargs: an empty collection. This will raise if any kwargs is provided.
    """

    def __init__(
        self,
        module: ModuleOp,
        entry_point_identifier: str,
        results: LogASMOutputType,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        if kwargs:
            kwargs_keys = ", ".join(f"'{k}'" for k in kwargs)
            msg = (
                f"Cannot instantiate a {LogAsmSubroutine.__name__} with keyword arguments (kwargs)."
                f" The following keyword arguments were found: {kwargs_keys}."
            )
            raise RuntimeError(msg)
        if not _is_logasm_argument_sequence(args):
            sargs = ", ".join(map(str, args))
            msg = f"The provided arguments '({sargs})' contains at least one invalid argument type."
            raise ArgumentError(msg)
        self._module = module
        self._entry_point_identifier = entry_point_identifier
        self._results = results
        self._arguments = args

    @property
    def module(self) -> ModuleOp:
        return self._module

    @property
    def entry_point_identifier(self) -> str:
        return self._entry_point_identifier

    @functools.cached_property
    def func_op(self) -> func.FuncOp:
        op = SymbolTable.lookup_symbol(self.module, self.entry_point_identifier)
        assert isinstance(op, func.FuncOp)
        return op

    @functools.cached_property
    def called_subroutines(self) -> Mapping[str, func.FuncOp | api.CircuitDeclarationOp]:
        return {
            op.sym_name.data: op
            for op in self.module.ops
            if isinstance(op, func.FuncOp | api.CircuitDeclarationOp)
            and op.sym_name.data != self.entry_point_identifier
        }

    def __call__(
        self, *args: P.args, **kwargs: P.kwargs
    ) -> InstantiatedLogAsmSubroutine[P, LogASMOutputType]:
        if kwargs:
            msg = f"Cannot call a {LogAsmSubroutine.__name__} with keyword arguments (kwargs)."
            raise RuntimeError(msg)
        operands = cast(Iterable[Any], args)
        argument_ssa_type = self.func_op.function_type.inputs
        argument_types = cast(Iterable[Any], self._arguments)
        if len(args) != len(self._arguments):
            msg = (
                f"Expected {len(self._arguments)} arguments for {self.identifier} but "
                f"got {len(args)}."
            )
            raise InvalidSizeError(msg)
        for i, (arg, arg_type, arg_ssa_type) in enumerate(
            zip(operands, argument_types, argument_ssa_type, strict=True)
        ):
            typ = type(arg_type)
            if not isinstance(arg, typ):
                msg = (
                    f"Expected a parameter of type {typ.__name__} for the {i}-th parameter to "
                    f"the subroutine but got an instance of {type(arg).__name__} which is not a "
                    f"subclass of {typ.__name__}."
                )
                raise TypeError(msg)
            if isinstance(arg, QubitReg):
                assert isinstance(arg_type, QubitReg)
                expected: int | None
                if isa(arg_ssa_type, TensorType[QubitType]):
                    expected = (
                        arg_ssa_type.get_shape()[0] if arg_ssa_type.has_static_shape() else None
                    )
                elif isa(arg_ssa_type, SurfaceCodeBasePatch):
                    expected = arg_ssa_type.num_qubits
                else:
                    msg = "Subroutine expected argument type does not match implementation."
                    raise ValueError(msg)

                # Check the register sizes
                given = arg._num_qubits
                if expected is not None and given is not None and expected != given:
                    msg = (
                        f"Expected a register of size {expected} but got a register of size "
                        f"{given} for parameter {i}."
                    )
                    raise ValueError(msg)
            elif not isinstance(arg, ClassicalExpression | int | bool):
                msg = f"Cannot call a LogAsmSubroutine as a subroutine with argument: {arg}"
                raise TypeError(msg)

        if not all_objects_managed_by_same_builder(cast(Sequence[BaseAPIObject], args)):
            msg = (
                "Expected all arguments given to a subroutine call to be managed by the same "
                f"builder. This is not the case for the provided arguments: {args}."
            )
            raise DifferentBuildersError(msg)

        return InstantiatedLogAsmSubroutine[P, LogASMOutputType](
            self._module, self._entry_point_identifier, self._results, *args, **kwargs
        )

    @override
    def __str__(self) -> str:
        res = StringIO()
        printer = Printer(stream=res)
        printer.print_string(f"{type(self).__name__}('{self.identifier}' ")

        # Rely on the block args and yield to show the contents of self.arguments and self.results
        # without having to print them directly
        printer.print_region(self.func_op.body)

        if subroutines := self.called_subroutines:
            printer.print_string(" which calls ")
            with printer.in_braces():
                with printer.indented():
                    for i, (name, op) in enumerate(subroutines.items()):
                        if i:
                            printer.print_string(",")
                        printer.print_string(f"\n'{name}' ")
                        printer.print_region(op.body)
                printer.print_string("\n")
        printer.print_string(")")
        return res.getvalue()

    @property
    def identifier(self) -> str:
        return self.entry_point_identifier


@dataclass(frozen=True)
class LogAsmProgram(Program):
    """An immutable Logical Assembly program that can be compiled into a physical circuit."""


class LogAsmBuilder(ProgramBuilder[LogAsmProgram]):
    """
    Builder class for the Logical Assembly API.

    Used to create logical assembly circuits and subroutines.
    """

    def __init__(self) -> None:
        # Internal state management.
        super().__init__()
        self._called = SubCallablesBuilder[func.FuncOp | api.CircuitDeclarationOp](
            "Logical Assembly program",
        )

    @staticmethod
    def _is_valid_return_type(
        return_types: tuple[BaseAPIObject, ...],
    ) -> TypeGuard[tuple[ProgramReturnType, ...]]:
        return all(isinstance(res, ProgramReturnType) for res in return_types)

    @override
    def build_program(self) -> LogAsmProgram:
        """Generate a ``LogAsmProgram`` from this builder."""
        return LogAsmProgram(self._build_module())

    def build_subroutine(self, identifier: str) -> LogAsmSubroutine[..., Any]:
        """Generate a ``LogAsmSubroutine`` from this builder.

        Args:
            identifier: name used to identify the subroutine in the IR and when calling it.

        Returns:
            An immutable representation of the subroutine being built at the moment of calling. The
            results of the returned subroutine are only known at runtime (they are defined by the
            calls to ``add_return`` made before building), so they are typed as ``Any``. Annotate
            the variable holding the result with the expected ``LogAsmSubroutine[[...], ...]`` type
            to get static checking of the arguments and results of that subroutine.
        """
        if identifier in self._called.callables:
            msg = (
                f"Cannot build the subroutine with identifier '{identifier}' as it already calls a "
                "subroutine with that identifier."
            )
            raise IdentifierConflictError(msg)
        returns = self._builder.returns
        assert LogAsmBuilder._is_valid_return_type(returns), (
            "Internal builder error: expected valid return types."
        )
        # Note that the `.ssa` property is lazy for some API objects, so we need to call it here
        # **before** clonging the region, else we might clone a region in which the SSA value never
        # existed, which will result in an error later.
        results_ssas = [ret.ssa for ret in returns]
        # Appending the return operation to a copy of the current state of the builder.
        new_region = Region()
        value_mapper: dict[SSAValue, SSAValue] = {}
        self._builder.region.clone_into(new_region, value_mapper=value_mapper)
        return_results = [value_mapper[ret] for ret in results_ssas]
        # Add the qubits and patches taken in by reference as results to enforce patches
        # by value in the IR
        return_results += [
            value_mapper[arg.ssa]
            for arg in self._builder.arguments
            if self._called.is_quantum_type(arg.ssa.type)
        ]
        return_op = func.ReturnOp(*return_results)
        new_region.block.add_op(return_op)
        # Creating the func operation.
        func_op = func.FuncOp(
            identifier,
            function_type=(
                self._builder.block.arg_types,
                tuple(ret.type for ret in return_results),
            ),
            region=new_region,
        )
        module = ModuleOp(Region([Block([func_op])]))
        module.body.block.add_ops(
            [op.clone(value_mapper=value_mapper) for op in self._called.callables.values()]
        )

        module.verify()
        # Adapting returns (which is currently a tuple) to the expected return type:
        subroutine_returns: LogASMResultsType
        if len(returns) == 0:
            subroutine_returns = None
        elif len(returns) == 1:
            subroutine_returns = returns[0]
        else:
            subroutine_returns = returns
        return LogAsmSubroutine(
            module, func_op.sym_name.data, subroutine_returns, *self._builder.arguments
        )

    @overload
    def add_arg(self, reg: _LogASMArgumentType) -> _LogASMArgumentType: ...
    @overload
    def add_arg(self, reg: type[Result]) -> Result: ...

    def add_arg(self, reg: _LogASMArgumentType | type[Result]) -> _LogASMArgumentType | Result:
        """Add an argument to this subroutine.

        Args:
            reg: either a ``QubitReg`` instance or the ``Result`` type if this argument is supposed
                to be a classical bit resulting from previous computations. If a ``QubitReg``
                instance is provided, it should be a new instance that was never used with another
                builder.

        Raises:
            ValueError: if the provided ``reg`` is a ``QubitReg`` instance and it was already used
                with a builder (either ``self`` or any other builder).

        Returns:
            If an instance of ``QubitReg`` is provided, this method modifies internal data in it and
            returns the instance. If a ``Result`` type is provided, this method returns a
            new ``ClassicalExpression`` instance that represents the argument.
        """
        if isinstance(reg, type) and issubclass(reg, Result):
            return self._builder.append_argument(Result())

        # Else, we have a ``QubitReg`` instance.
        if reg._is_attached:
            msg = f"Cannot use an already used {type(reg).__name__} as an argument."
            raise ValueError(msg)
        return self._builder.append_argument(reg)

    def declare_patch(self, reg: LogASMPatchType) -> LogASMPatchType:
        """Declare a new QubitReg as part of this builder's program. This will attached the
        QubitReg to this builder, after which it can be used to perform operations that become part
        of this builder's program."""
        reg._declare_in_builder(self._builder)
        return reg

    def multi_pauli_measure(
        self,
        operand_patches: Sequence[RotatedPlanarPatch],
        bridges: Sequence[RotatedPlanarPatch] | None = None,
        *,
        pauli_bases: Sequence[PauliType],
        rounds: int | None = None,
    ) -> Result:
        """Perform a multi-pauli-measure of multiple patches, and return the measured bit."""
        if len(operand_patches) < 2:
            msg = "A multi Pauli measurement requires at least 2 patches."
            raise InvalidSizeError(msg)

        if bridges is None:
            patch_types = [p._type_info for p in operand_patches]
            bridge_types = RotatedPlanarPatch._best_effort_bridges(patch_types)
            # Declaring the bridges and preparing them in the correct basis.
            bridges = [
                self._builder.append_op_and_update_ssas(
                    PatchDeclarationOp(btype), RotatedPlanarPatch.from_attribute(btype)
                )
                for btype in bridge_types
            ]
        # Preparing the bridges in the correct basis.
        if bridges:
            first_patch_type = cast(SurfaceCodeBasePatch, operand_patches[0].ssa.type)
            bridge_types = tuple(
                cast(RotatedPlanarPatchType, bridge.ssa.type) for bridge in bridges
            )
            basis = _find_bridges_basis(first_patch_type, bridge_types)
            bridges = [
                self._builder.append_op_and_update_ssas(PrepareOp(bridge.ssa, basis), bridge)
                for bridge in bridges
            ]

        widths_and_heights = [
            *(p._width for p in operand_patches),
            *(p._height for p in operand_patches),
        ]
        if not does_not_contain_none_values(widths_and_heights):
            msg = "All patches involved in a multi-pauli measurement must have a size."
            raise InvalidSizeError(msg)
        min_rounds = rounds if rounds is not None else min(widths_and_heights)
        op = MultiPauliMeasOp(
            min_rounds,
            (
                b.to_qcore_attr() if isinstance(b, Pauli) else PauliAttr.coerce(b)
                for b in pauli_bases
            ),
            [p.ssa for p in operand_patches],
            [b.ssa for b in bridges],
        )
        res, *_ = self._builder.append_op_and_update_ssas(op, (Result(), *operand_patches))

        if bridges:
            # Measuring the bridges in the correct basis.
            for bridge in bridges:
                self._builder.append_ops_ignoring_ssas(MeasureOp(bridge.ssa, basis))

        # The following assert is here because there is currently no way to have correct typing on
        # append_op_and_update_ssas, so ``res`` is typed as just a ``BuilderObject`` instead of the
        # more precise ``Result``. This is supposed to be an invariant of append_op_and_update_ssas
        # so we assert here both to double-check the invariant and make the type checker happy.
        assert isinstance(res, Result), (
            "Internal invariant broken: the builder did not return the expected type."
        )
        return res

    def transversal(
        self,
        gate: GateTypeEnum | Literal["X", "Z", "H", "CX"],
        operand_patches: Sequence[RotatedPlanarPatch],
    ) -> None:
        """Perform a multi-patch transversal gate operation."""
        if isinstance(gate, str):
            gate = GateTypeEnum(gate)

        # A transversal H flips the logical observable.
        if gate == GateTypeEnum.H:
            for patch in operand_patches:
                patch._vertical_z = not patch._vertical_z

        result_types: list[RotatedPlanarPatchType] = [
            (
                cast(RotatedPlanarPatchType, patch.ssa.type).with_flipped_observable()
                if gate == GateTypeEnum.H
                else cast(RotatedPlanarPatchType, patch.ssa.type)
            )
            for patch in operand_patches
        ]
        op = TransversalGateOp([patch.ssa for patch in operand_patches], gate, result_types)
        self._builder.append_op_and_update_ssas(op, operand_patches)

    def barrier(self, *registers: QubitReg) -> None:
        """Add a parallelism barrier to the program, on the given registers."""
        if not registers:
            registers = tuple(self._builder.all_managed_objects_of_type(QubitReg))
        self._builder.append_op_and_update_ssas(
            api.BarrierOp([patch.ssa for patch in registers]), registers
        )

    def call_subroutine(
        self, subroutine: InstantiatedLogAsmSubroutine[P, LogASMOutputType]
    ) -> LogASMOutputType:
        """Call a Logical Assembly subroutine from this this program. The expected usage:
        classical_result = builder.call_subroutine(my_subroutine(patch_arg_or_classical_arg, ...))
        """
        # Check that the provided outer arguments (i.e., the arguments provided when instantiating
        # the Circuit) have been created in this builder.
        self._check_args_are_managed(subroutine.outer_arguments)

        # Register the circuit in this builder
        self._called.add_callable(
            subroutine.identifier, subroutine.func_op, subroutine.called_subroutines
        )

        pre_call_ops: list[api.CastOp] = []
        call_args = [
            self._called.coerce_operand_from_arg(
                outer_arg.ssa,
                inner_type,
                op_list=pre_call_ops,
                callable_ident=subroutine.identifier,
            )
            for inner_type, outer_arg in zip(
                subroutine.func_op.function_type.inputs, subroutine.outer_arguments, strict=True
            )
        ]

        # Make the call
        call_op = func.CallOp(
            subroutine.identifier, call_args, tuple(subroutine.func_op.function_type.outputs)
        )

        # Collect which API objects are quantum args to implement pass-by-reference
        post_call_ops, quantum_args, quantum_results = self._called.recast_quantum_results(
            subroutine.outer_arguments, call_op.res
        )

        # Add all the ops to the builder and update the API objects with the new ssa values
        explicit_returns = [res._get_unattached_deepcopy() for res in subroutine.results_tuple]
        ret = self._builder.append_ops_and_update_ssas(
            (*pre_call_ops, call_op, *post_call_ops),
            list(call_op.res[: len(subroutine.results_tuple)]) + quantum_results,
            explicit_returns + quantum_args,
        )
        ret = ret[: len(subroutine.results_tuple)]

        # The below casts are valid because we adapt the type of the return here to the type of the
        # expected result from ``circuit`` dynamically.
        if subroutine._results is None:
            return cast(LogASMOutputType, None)
        if isinstance(subroutine._results, ProgramReturnType):
            return cast(LogASMOutputType, ret[0])
        return cast(LogASMOutputType, tuple(ret))
