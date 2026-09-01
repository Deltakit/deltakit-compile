# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for the logical assembly xDSL dialect."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import ClassVar, TypeVar, cast

from typing_extensions import Self, override
from xdsl.dialects.builtin import (
    ArrayAttr,
    ArrayOfConstraint,
    Float64Type,
    FloatAttr,
    IntAttr,
    NoneAttr,
    i1,
)
from xdsl.ir import Attribute, Dialect, ParametrizedAttribute, SSAValue, TypeAttribute
from xdsl.irdl import traits_def
from xdsl.irdl.attributes import base, irdl_attr_definition, param_def
from xdsl.irdl.constraints import (
    AnyOf,
    AtLeast,
    AttrConstraint,
    EqIntConstraint,
    IntConstraint,
    IntVarConstraint,
    MessageConstraint,
    ParamAttrConstraint,
    RangeConstraint,
    RangeOf,
    RangeVarConstraint,
    VarConstraint,
)
from xdsl.irdl.operations import (
    AttrSizedOperandSegments,
    IRDLOperation,
    irdl_op_definition,
    operand_def,
    prop_def,
    result_def,
    var_operand_def,
    var_result_def,
)
from xdsl.parser import AttrParser
from xdsl.pattern_rewriter import RewritePattern
from xdsl.printer import Printer
from xdsl.traits import HasCanonicalizationPatternsTrait, Pure
from xdsl.utils.exceptions import VerifyException

from deltakit_compile.dialects.common.attributes import (
    AnyEnumAttribute,
    PlainIntAttr,
    float64_to_string,
    parse_float64,
)
from deltakit_compile.dialects.common.constraints import BaseVarConstraint
from deltakit_compile.dialects.qcore import NoQuantumEffect, PauliAttr, QubitRegType
from deltakit_compile.shared.patch.bounding_box import BoundingBox
from deltakit_compile.utilities.base_enums import BetterStrEnum

# region Attributes


class OrientationEnum(BetterStrEnum):
    """Orientation of the patch, defined by the direction of the Z logical (i.e., if Z is vertical
    that means X is horizontal)."""

    VERTICAL_Z = "v_z"
    HORIZONTAL_Z = "h_z"

    def rotate(self) -> OrientationEnum:
        """Get the other possible orientation, e.g., what the orientation would be after a
        log_asm.rotate"""
        return (
            OrientationEnum.HORIZONTAL_Z
            if self == OrientationEnum.VERTICAL_Z
            else OrientationEnum.VERTICAL_Z
        )


@irdl_attr_definition
class OrientationAttr(AnyEnumAttribute[OrientationEnum], use_values=True):
    """Patch orientation as an attribute."""

    name = "log_asm.orientation"

    def rotate(self) -> OrientationAttr:
        """Get the other possible orientation."""
        return OrientationAttr(self.data.rotate())


class GateTypeEnum(BetterStrEnum):
    """The types of gates with built-in support in this dialect."""

    X = "X"
    Z = "Z"
    H = "H"
    CX = "CX"


@irdl_attr_definition
class GateTypeAttr(AnyEnumAttribute[GateTypeEnum], use_values=True):
    """Gate type as an attribute."""

    name = "log_asm.gate_type"


@irdl_attr_definition
class PlacementAttr(ParametrizedAttribute):
    """An attribute for storing a patch's location and orientation.
    The placement is defined in 2D since this is sufficient for current use cases.
    """

    name = "log_asm.placement"

    location: ArrayAttr[FloatAttr[Float64Type]] = param_def(
        MessageConstraint(
            ArrayAttr.constr(RangeOf(base(FloatAttr[Float64Type])).of_length(EqIntConstraint(2))),
            "Patch location must be a 2D coordinate stored as an ArrayAttr of 2 FloatAttrs.",
        )
    )
    orientation: OrientationAttr

    def __init__(
        self,
        location: ArrayAttr[FloatAttr] | Sequence[FloatAttr | float | int],
        orientation: OrientationAttr | OrientationEnum,
    ) -> None:
        super().__init__(
            ArrayAttr.get(
                tuple(FloatAttr(f, 64) if isinstance(f, (int, float)) else f for f in location)
            ),
            OrientationAttr.get(orientation),
        )

    @classmethod
    @override
    def parse_parameters(
        cls, parser: AttrParser
    ) -> tuple[ArrayAttr[FloatAttr[Float64Type]], OrientationAttr]:
        """Parse the attribute parameters."""
        with parser.in_angle_brackets():
            location = ArrayAttr(
                parser.parse_comma_separated_list(
                    delimiter=parser.Delimiter.SQUARE,
                    parse=lambda: FloatAttr(parse_float64(parser), Float64Type()),
                )
            )
            parser.parse_punctuation(",")
            orientation = parser.parse_attribute()
            assert isinstance(orientation, OrientationAttr)
        return location, orientation

    @override
    def print_parameters(self, printer: Printer) -> None:
        """Print the attribute parameters."""
        with printer.in_angle_brackets():
            with printer.in_square_brackets():
                printer.print_list(
                    self.location, lambda f: printer.print_string(float64_to_string(f))
                )
            printer.print_string(", ")
            printer.print_attribute(self.orientation)

    def with_offset(self, offset: tuple[int, ...]) -> PlacementAttr:
        """Return a new offset ``PlacementAttr`` instance.

        Args:
            offset: Offset to apply to each location.

        Raises:
            RuntimeError: if the provided ``offset`` is not of the correct dimension. Currently,
                only 2-dimensional offsets are supported.

        Returns:
            A new ``PlacementAttr`` instance that is a copy of ``self`` with the provided offset.
        """
        if len(offset) != 2:
            msg = (
                f"Cannot offset a 2-dimensional placement with a {len(offset)}-dimensional offset."
            )
            raise RuntimeError(msg)
        return PlacementAttr(
            [b.value.data + o for b, o in zip(self.location.data, offset, strict=True)],
            self.orientation,
        )

    def rotated(self) -> PlacementAttr:
        """Return a new ``PlacementAttr`` instance with its orientation rotated."""
        return PlacementAttr(self.location, self.orientation.rotate())


class PlacementConstraint(ParamAttrConstraint[PlacementAttr]):
    """A constraint for PlacementAttrs that can also constrain the location and orientation."""

    def __init__(
        self,
        *,
        location: AttrConstraint[ArrayAttr] | None = None,
        orientation: AttrConstraint[OrientationAttr] | None = None,
    ):
        if location is None:
            location = base(ArrayAttr)
        if orientation is None:
            orientation = base(OrientationAttr)
        super().__init__(
            PlacementAttr,
            (
                MessageConstraint(
                    location,
                    "The location does not meet the requirements.",
                ),
                MessageConstraint(
                    orientation,
                    "The orientation does not meet the requirements.",
                ),
            ),
        )


@dataclass(frozen=True, init=False)
class BasePatch(ParametrizedAttribute, TypeAttribute):
    """Base class for all Patch types, whether we know anything about it or not."""

    name = "log_asm.patch.???"

    @classmethod
    def constr(cls) -> AttrConstraint:
        """Gets a constraint that constrains an Attribute to one of this type."""
        return base(cls)

    @classmethod
    @abstractmethod
    def defines_valid_logical(cls, patches: Iterable[Self], bridges: Iterable[Self]) -> bool:
        """Returns True iff the collection of patches and bridge patches defines a single logical
        patch with effective size no less than the smallest patch in patches."""

    @property
    @abstractmethod
    def num_qubits(self) -> int:
        pass


@dataclass(frozen=True, init=False)
class SurfaceCodeBasePatch(BasePatch):
    """A base class for surface code patches."""

    # xDSL requires param_def(...) to be used directly as a class attribute, which triggers RUF009.
    # This is not a true dataclass default, so we suppress the warning for compatibility with xDSL.
    size: ArrayAttr[IntAttr] = param_def(  # noqa: RUF009
        MessageConstraint(
            ArrayAttr.constr(RangeOf(IntAttr.constr(AtLeast(1))).of_length(EqIntConstraint(2))),
            "Patch size must be 2D stored as an ArrayAttr of 2 positive value IntAttrs.",
        )
    )
    """The size of the surface code patch. This is the nominal spatial size of the patch that
    corresponds to the upper-bound of the distance."""

    placement: PlacementAttr | NoneAttr = param_def(base(PlacementAttr) | base(NoneAttr))  # noqa: RUF009
    """The placement of a surface code patch defines its location in space and orientation. It may
    be a NoneAttr to represent patches in QPUs that do not have a fixed lattice of qubits."""

    def __init__(
        self,
        size: ArrayAttr[IntAttr] | tuple[int | IntAttr, int | IntAttr],
        placement: PlacementAttr | NoneAttr | None,
    ) -> None:
        super().__init__(
            ArrayAttr.get(tuple(IntAttr.get(i) for i in size)),
            NoneAttr() if placement is None else placement,
        )

    def with_new_placement(self, placement: PlacementAttr) -> Self:
        """Get a copy of this surface code patch type but with a new placement attribute."""
        return self.new([self.size, placement])

    @classmethod
    @override
    def defines_valid_logical(cls, patches: Iterable[Self], bridges: Iterable[Self]) -> bool:
        """Returns True iff the collection of patches and bridge patches defines a single logical
        patch with effective distance no less than the smallest patch in patches."""
        return True  # TODO Implement verification

    @classmethod
    @override
    def parse_parameters(cls, parser: AttrParser) -> Sequence[Attribute]:
        """Parse surface code patch:
        log_asm.patch.???`<`
            `size` `=` `(` $size.width `,` $size.height `)`
            (   `,`
                `location` `=` `(` $placement.x^ `,` $placement.y `)` `,`
                `orient` `=` $placement.orientation
            )?
        `>`
        """
        with parser.in_angle_brackets():
            parser.parse_keyword("size")
            parser.parse_punctuation("=")
            size = ArrayAttr(
                parser.parse_comma_separated_list(
                    delimiter=parser.Delimiter.PAREN,
                    parse=lambda: IntAttr(
                        parser.parse_integer(allow_boolean=False, allow_negative=False)
                    ),
                )
            )
            if parser.parse_optional_punctuation(","):
                placement: PlacementAttr | NoneAttr
                parser.parse_keyword("location")
                parser.parse_punctuation("=")
                location = ArrayAttr(
                    parser.parse_comma_separated_list(
                        delimiter=parser.Delimiter.PAREN,
                        parse=lambda: FloatAttr(parse_float64(parser), 64),
                    )
                )
                parser.parse_punctuation(",")

                parser.parse_keyword("orient")
                parser.parse_punctuation("=")
                orientation = OrientationAttr(parser.parse_str_enum(OrientationEnum))
                placement = PlacementAttr(location, orientation)
            else:
                placement = NoneAttr()

        return [size, placement]

    @override
    def print_parameters(self, printer: Printer) -> None:
        with printer.in_angle_brackets():
            printer.print_string("size=(")
            printer.print_list(self.size, lambda i: printer.print_int(i.data))
            printer.print_string(")")

            if not isinstance(self.placement, NoneAttr):
                printer.print_string(", ")
                printer.print_string("location=(")
                printer.print_list(
                    self.placement.location, lambda f: printer.print_string(float64_to_string(f))
                )
                printer.print_string("), ")

                printer.print_string("orient=")
                self.placement.orientation.print_inner(printer)

    @staticmethod
    def _consistent_placement_constr(
        *,
        same_has_placement: bool = False,
        has_placement: bool = False,
        placement: AttrConstraint[PlacementAttr | NoneAttr] | None = None,
        same_location: bool = False,
        location: AttrConstraint[ArrayAttr[FloatAttr]] | None = None,
        same_orientation: bool = False,
        orientation: AttrConstraint[OrientationAttr] | None = None,
        prefix: str = "",
    ) -> AttrConstraint[NoneAttr | PlacementAttr]:
        """Returns an attribute constraint that constrains each use of
        SurfaceCodeBasePatch.placement attributes based on the given parameters.

        See consistent_constr() for argument details.
        """
        location = location or base(ArrayAttr[FloatAttr])
        if same_location:
            location = VarConstraint(f"{prefix}PatchLocation", location)

        orientation = orientation or base(OrientationAttr)
        if same_orientation:
            orientation = VarConstraint(f"{prefix}PatchOrientation", orientation)

        placement_inner: AttrConstraint[NoneAttr | PlacementAttr] = PlacementConstraint(
            location=location, orientation=orientation
        )
        if not has_placement:
            placement_inner = AnyOf((base(NoneAttr), placement_inner))

        placement = placement_inner if placement is None else placement & placement_inner

        if same_has_placement and not has_placement:
            placement = BaseVarConstraint(f"{prefix}PatchPlacement", placement)

        return placement

    @staticmethod
    def consistent_constr(
        *,
        same_type: bool = False,
        same_size: bool = False,
        size: AttrConstraint[ArrayAttr] | None = None,
        same_has_placement: bool = False,
        has_placement: bool = False,
        placement: AttrConstraint[PlacementAttr | NoneAttr] | None = None,
        same_location: bool = False,
        location: AttrConstraint[ArrayAttr[FloatAttr]] | None = None,
        same_orientation: bool = False,
        orientation: AttrConstraint[OrientationAttr] | None = None,
        prefix: str = "",
    ) -> AttrConstraint[SurfaceCodeBasePatch]:
        """Returns an attribute constraint that constrains operand and result patch types to ensure
        they have consistent values according to the given parameters.

        Args:
            same_type: Every constrained patch must have the same attribute base type (the same type
                of surface code patch)
            same_size: Every constrained patch must have the same patch size.
            size: Every constrained patch's size is constrained by this constraint.
            same_has_placement: All constrained patches either all have a PlacementAttr or all have
                a NoneAttr placement. This does not constrain anything else about each patch's
                placement, if they have them.
            has_placement:Every constrained patch must have a PlacementAttr placement - not
                a NoneAttr.
            placement:Every constrained patch's placement parameter is also constrained by this
                constraint.
            same_location: Every patch that has a PlacementAttr must have the same location
                Attribute.
            location: Applies the given constraint to the location parameter of every patch that has
                a PlacementAttr.
            same_orientation: Every patch that has a PlacementAttr must have the same orientation
                Attribute.
            orientation: Applies the given constraint to the orientation parameter of every patch
                that has a PlacementAttr.
            prefix: All the arguments that start with ``same_`` use a constraint context variable to
                match up the correct types and values across the different uses of the constraint.
                If these options are used in making multiple constraints within one operation
                (constraint context) then a unique prefix needs to be given to each invocation of
                constraint_constr to avoid naming conflicts within the constraint context. Note that
                the prefixed variable names appear as part of the VerifyException given when the
                constraints do not hold.

        Returns:
            An attribute constraint that ensures consistent values for the specified parameters.

        """
        size = size or base(ArrayAttr)
        if same_size:
            size = VarConstraint(f"{prefix}PatchSize", size)

        constr: AttrConstraint[SurfaceCodeBasePatch] = SurfaceCodePatchConstraint(
            size=size,
            placement=SurfaceCodeBasePatch._consistent_placement_constr(
                same_has_placement=same_has_placement,
                has_placement=has_placement,
                placement=placement,
                same_location=same_location,
                location=location,
                same_orientation=same_orientation,
                orientation=orientation,
            ),
        )
        if same_type:
            constr = BaseVarConstraint("PatchType", constr)

        return constr

    @property
    def placement_data(self) -> tuple[float, float] | None:
        """Returns the location of the patch as a tuple of floats."""
        if isinstance(self.placement, NoneAttr):
            return None

        return (
            self.placement.location.data[0].value.data,
            self.placement.location.data[1].value.data,
        )

    @property
    def size_data(self) -> tuple[int, int]:
        """Returns the size of the patch as a tuple of integers."""
        return (self.size.data[0].data, self.size.data[1].data)

    @property
    def orientation_data(self) -> OrientationEnum | None:
        """Returns the orientation of the Z-observable on the patch."""
        if isinstance(self.placement, NoneAttr):
            return None
        return self.placement.orientation.data

    @property
    def bounding_box(self) -> BoundingBox | None:
        """Return the bottom-left and top-right coordinates defining the bounding box of self."""
        if (placement := self.placement_data) is None:
            return None
        size = self.size_data
        return BoundingBox(
            placement[0], placement[1], placement[0] + size[0], placement[1] + size[1]
        )

    def with_flipped_observable(self) -> Self:
        placement = self.placement
        if not isinstance(placement, NoneAttr):
            placement = placement.rotated()
        return type(self).new((self.size, placement))

    def with_offset_size(self, offset: tuple[int, ...]) -> Self:
        if len(offset) != 2:
            msg = (
                f"Cannot offset a 2-dimensional placement with a {len(offset)}-dimensional offset."
            )
            raise RuntimeError(msg)
        return type(self).new(
            (
                ArrayAttr(IntAttr(s.data + o) for s, o in zip(self.size, offset, strict=True)),
                self.placement,
            )
        )


SurfaceCodeBasePatchT = TypeVar("SurfaceCodeBasePatchT", bound=SurfaceCodeBasePatch)


class SurfaceCodePatchConstraint(ParamAttrConstraint[SurfaceCodeBasePatch]):
    """Constraint an attribute to a SurfaceCodeBasePatch."""

    def __init__(
        self,
        *,
        size: AttrConstraint[ArrayAttr] | None = None,
        placement: AttrConstraint[PlacementAttr | NoneAttr] | None = None,
    ):
        if size is None:
            size = base(ArrayAttr)
        if placement is None:
            placement = base(NoneAttr) | base(PlacementAttr)
        super().__init__(
            SurfaceCodeBasePatch,
            (
                MessageConstraint(
                    size,
                    "The size of the patch does not meet the requirements.",
                ),
                MessageConstraint(
                    placement,
                    "The placement of the patch does not meet the requirements.",
                ),
            ),
        )


@irdl_attr_definition
class RotatedPlanarPatchType(SurfaceCodeBasePatch):
    """A patch type representing a rotated planar patch."""

    name = "log_asm.patch.rot_planar"

    def __init__(
        self,
        size: ArrayAttr[IntAttr] | tuple[int | IntAttr, int | IntAttr],
        placement: PlacementAttr | NoneAttr | None,
    ) -> None:
        # Overriding because type mypy does not correctly infer the inherited __init__
        super().__init__(size, placement)

    @property
    @override
    def num_qubits(self) -> int:
        d1, d2 = self.size_data
        return 2 * d1 * d2 - 1


@irdl_attr_definition
class UnrotatedPlanarPatchType(SurfaceCodeBasePatch):
    """A patch type representing an unrotated planar patch."""

    name = "log_asm.patch.unrot_planar"

    def __init__(
        self,
        size: ArrayAttr[IntAttr] | tuple[int | IntAttr, int | IntAttr],
        placement: PlacementAttr | NoneAttr | None,
    ) -> None:
        # Overriding because type mypy does not correctly infer the inherited __init__
        super().__init__(size, placement)

    @property
    @override
    def num_qubits(self) -> int:
        d1, d2 = self.size_data
        return (2 * d1 - 1) * (2 * d2 - 1)


# endregion

# region Declaration Operations


class BaseLogicalAssemblyOp(IRDLOperation, ABC):
    """Abstract base class for all Logical Assembly operations."""


@irdl_op_definition
class PatchDeclarationOp(BaseLogicalAssemblyOp, IRDLOperation):
    """Declare a new patch. The properties of the patch are entirely defined by the patch type
    provided."""

    name = "log_asm.patch_dec"

    res = result_def(BasePatch.constr())

    assembly_format = " attr-dict `->` type($res)"

    def __init__(self, patch_type: BasePatch):
        super().__init__(result_types=[patch_type])


# endregion


# region Resize & Movement Operations


class BaseMovementOp(BaseLogicalAssemblyOp, ABC):
    """Base class for ops that move patches (either explicitly or as part of how they work
    internally)."""


@irdl_op_definition
class RotateOp(BaseMovementOp, IRDLOperation):
    """Rotate a patch's logicals 90 degrees. There are only two possible rotational states (Z is
    horizontal and X is vertical or Z is vertical and X is horizontal) so rotate flips from one to
    the other, which may involve moving the patch."""

    name = "log_asm.rotate"

    _PT: ClassVar[AttrConstraint[SurfaceCodeBasePatch]] = SurfaceCodeBasePatch.consistent_constr(
        same_type=True, has_placement=True
    )  # PatchType constraint
    _LP: ClassVar[AttrConstraint[SurfaceCodeBasePatch]] = SurfaceCodeBasePatch.consistent_constr(
        same_size=True
    )  # LogicalPatch constraint

    patch = operand_def(_PT & _LP)
    bridge_patches = var_operand_def(RangeOf(_PT))
    rounds = prop_def(IntAttr.constr(AtLeast(0)))
    res = result_def(_PT & _LP)

    assembly_format = (
        f"`<` {PlainIntAttr.use('$rounds')} `>` `(` $patch `:` type($patch) `)` "
        "(`(` $bridge_patches^ `:` type($bridge_patches) `)`)? attr-dict `->` type($res)"
    )

    custom_directives = (PlainIntAttr,)

    def __init__(
        self,
        patch: SSAValue[SurfaceCodeBasePatchT],
        rounds: IntAttr | int,
        result_type: SurfaceCodeBasePatchT,
        *,
        bridges: Sequence[SSAValue[SurfaceCodeBasePatchT]] | None = None,
    ):
        super().__init__(
            operands=[patch, bridges],
            result_types=[result_type],
            properties={"rounds": IntAttr.get(rounds)},
        )

    @override
    def verify_(self) -> None:
        """Verify that the modification to the patch is valid for this op."""
        in_patch = cast(SurfaceCodeBasePatch, self.patch.type)
        in_placement = in_patch.placement
        assert not isinstance(in_placement, NoneAttr)  # Caught by constraints.
        assert isinstance(self.res.type, SurfaceCodeBasePatch)
        actual_res_type = self.res.type
        out_placement = actual_res_type.placement
        assert not isinstance(out_placement, NoneAttr)  # Caught by constraints.
        if in_placement.orientation.rotate() != out_placement.orientation:
            msg = f"{self.name} expects the orientation of the input and output to be different."
            raise VerifyException(msg)
        if not in_patch.defines_valid_logical(
            [in_patch, self.res.type],
            [cast(SurfaceCodeBasePatch, bridge.type) for bridge in self.bridge_patches],
        ):
            msg = f"{self.name} has operands and result patches that do not form a valid logical."
            raise VerifyException(msg)


@irdl_op_definition
class MoveOp(BaseMovementOp):
    """Move a patch to a new location via a series of bridge patches. This will destroy the original
    patch and bridges, allowing the area on the QPU lattice that they occupied to be reused.
    """

    name = "log_asm.move"

    _PT: ClassVar[AttrConstraint[SurfaceCodeBasePatch]] = SurfaceCodeBasePatch.consistent_constr(
        same_type=True, has_placement=True, same_orientation=True
    )  # PatchType constraint
    _LP: ClassVar[AttrConstraint[SurfaceCodeBasePatch]] = SurfaceCodeBasePatch.consistent_constr(
        same_size=True,
    )  # LogicalPatch constraint

    patch = operand_def(_PT & _LP)
    bridge_patches = var_operand_def(RangeOf(_PT))
    rounds = prop_def(IntAttr.constr(AtLeast(0)))
    res = result_def(_PT & _LP)

    assembly_format = (
        f"`<` {PlainIntAttr.use('$rounds')} `>` `(` $patch `:` type($patch) `)` "
        "`(` $bridge_patches `:` type($bridge_patches) `)` attr-dict `->` type($res)"
    )

    custom_directives = (PlainIntAttr,)

    def __init__(
        self,
        patch: SSAValue,
        rounds: IntAttr | int,
        bridge_patches: list[SSAValue],
        new_patch: SurfaceCodeBasePatch,
    ):
        super().__init__(
            operands=[patch, bridge_patches],
            result_types=[new_patch],
            properties={"rounds": IntAttr.get(rounds)},
        )

    @override
    def verify_(self) -> None:
        """Verify that the modification to the patch is valid for this op."""
        in_patch = cast(SurfaceCodeBasePatch, self.patch.type)
        if not in_patch.defines_valid_logical(
            [in_patch, self.res.type],
            [cast(SurfaceCodeBasePatch, bridge.type) for bridge in self.bridge_patches],
        ):
            msg = f"{self.name} has operands and result patches that do not form a valid logical."
            raise VerifyException(msg)
        # TODO: Check orientation is correct for movement


@irdl_op_definition
class GrowOp(BaseMovementOp):
    """Grow the size of a patch."""

    name = "log_asm.grow"

    _PT: ClassVar[AttrConstraint[SurfaceCodeBasePatch]] = SurfaceCodeBasePatch.consistent_constr(
        same_type=True, same_orientation=True
    )  # PatchType constraint
    patch = operand_def(_PT)
    rounds = prop_def(IntAttr.constr(AtLeast(0)))
    res = result_def(_PT)

    assembly_format = (
        f"`<` {PlainIntAttr.use('$rounds')} `>` `(` $patch `:` type($patch) `)` "
        "attr-dict `->` type($res)"
    )

    custom_directives = (PlainIntAttr,)

    def __init__(self, patch: SSAValue, rounds: IntAttr | int, new_type: SurfaceCodeBasePatch):
        super().__init__(
            operands=[patch],
            result_types=[new_type],
            properties={"rounds": IntAttr.get(rounds)},
        )

    @override
    def verify_(self) -> None:
        """Verify that the resulting patch type is valid given the input patch."""
        # TODO verify resize size and location/orientation (if any) make sense.


@irdl_op_definition
class ShrinkOp(BaseMovementOp):
    """Shrink the size of a patch. The area on the QPU lattice no longer occupied by the patch is
    now free to be reused."""

    name = "log_asm.shrink"

    _PT: ClassVar[AttrConstraint[SurfaceCodeBasePatch]] = SurfaceCodeBasePatch.consistent_constr(
        same_type=True, same_orientation=True
    )  # PatchType constraint
    patch = operand_def(_PT)
    rounds = prop_def(IntAttr.constr(AtLeast(0)))
    res = result_def(_PT)

    assembly_format = (
        f"`<` {PlainIntAttr.use('$rounds')} `>` `(` $patch `:` type($patch) `)` "
        "attr-dict `->` type($res)"
    )

    custom_directives = (PlainIntAttr,)

    def __init__(self, patch: SSAValue, rounds: IntAttr | int, new_type: SurfaceCodeBasePatch):
        super().__init__(
            operands=[patch],
            result_types=[new_type],
            properties={"rounds": IntAttr.get(rounds)},
        )

    @override
    def verify_(self) -> None:
        """Verify that the resulting patch type is valid given the input patch."""
        # TODO verify resize size and location/orientation (if any) make sense.


@irdl_op_definition
class StepOp(BaseMovementOp):
    """Step a patch a single qubit in a chosen direction without changing anything about its shape.
    The area on the QPU lattice no longer occupied by the patch is now free to be reused.
    """

    name = "log_asm.step"

    _PT: ClassVar[AttrConstraint[SurfaceCodeBasePatch]] = SurfaceCodeBasePatch.consistent_constr(
        same_type=True, same_size=True, has_placement=True, same_orientation=True
    )  # PatchType constraint

    patch = operand_def(_PT)
    res = result_def(_PT)

    assembly_format = "`(` $patch `:` type($patch) `)` attr-dict `->` type($res)"

    def __init__(self, patch: SSAValue, new_type: SurfaceCodeBasePatch):
        super().__init__(operands=[patch], result_types=[new_type])


# endregion

# region Prep & Measurement Operations


@irdl_op_definition
class PrepareOp(BaseLogicalAssemblyOp, IRDLOperation):
    """Prepare a patch in the provided basis (typically reset all the qubits).
    This consumes the patch SSA value and returns a new patch (with exactly the same type)
    representing the prepared patch."""

    name = "log_asm.prepare"

    _PT: ClassVar[AttrConstraint[SurfaceCodeBasePatch]] = VarConstraint(
        "PatchType", SurfaceCodePatchConstraint()
    )  # PatchType constraint

    patch = operand_def(_PT)
    basis = prop_def(PauliAttr)
    res = result_def(_PT)

    assembly_format = (
        f"`<` {PauliAttr.plain_directive('$basis')} `>` `(` $patch `:` type($patch) `)` attr-dict"
    )

    custom_directives = (PauliAttr.plain_directive(),)

    def __init__(self, patch: SSAValue, basis: PauliAttr):
        super().__init__(operands=[patch], result_types=[patch.type], properties={"basis": basis})


@irdl_op_definition
class MeasureOp(BaseLogicalAssemblyOp, IRDLOperation):
    """Measure a patch in a basis, returning a single logical bit. This will destroy the patch,
    allowing the area on the QPU lattice that it occupied to be reused."""

    name = "log_asm.measure"

    _PT: ClassVar[AttrConstraint[SurfaceCodeBasePatch]] = VarConstraint(
        "PatchType", SurfaceCodePatchConstraint()
    )  # PatchType constraint

    patch = operand_def(_PT)
    basis = prop_def(PauliAttr)
    measurement = result_def(i1)

    assembly_format = (
        f"`<` {PauliAttr.plain_directive('$basis')} `>`"
        "`(` $patch `:` type($patch) `)` attr-dict `->` type($measurement)"
    )
    custom_directives = (PauliAttr.plain_directive(),)

    def __init__(self, patch: SSAValue, basis: PauliAttr):
        super().__init__(
            operands=[patch],
            result_types=[i1],
            properties={"basis": basis},
        )


@irdl_op_definition
class MeasStabOp(BaseLogicalAssemblyOp, IRDLOperation):
    """Measure the stabilisers of a patch. This will automatically expand to the correct number of
    rounds required to correctly line up the next operation in the timeline, if required.
    This consumes the patch SSA value and returns a new patch (with exactly the same type)
    representing the prepared patch."""

    name = "log_asm.meas_stab"

    _PT: ClassVar[AttrConstraint[SurfaceCodeBasePatch]] = VarConstraint(
        "PatchType", SurfaceCodePatchConstraint()
    )  # PatchType constraint

    patch = operand_def(_PT)
    min_rounds = prop_def(IntAttr.constr(AtLeast(0)))
    res = result_def(_PT)

    assembly_format = (
        f"`<` {PlainIntAttr.use('$min_rounds')} `>` `(` $patch `:` type($patch) `)` attr-dict"
    )
    custom_directives = (PlainIntAttr,)

    def __init__(self, patch: SSAValue, min_rounds: IntAttr | int):
        super().__init__(
            operands=[patch],
            result_types=[patch.type],
            properties={"min_rounds": IntAttr.get(min_rounds)},
        )


@irdl_op_definition
class MultiPauliMeasOp(BaseLogicalAssemblyOp, IRDLOperation):
    """Do a multi-Pauli measurement from a set of patches. This involves a merge and split between
    the logical patches using bridge patches to cover the gap. The new states for the logical
    patches are returned as new SSA values while the bridge patches are destroyed by this operation,
    allowing the area on the QPU lattice that they occupied to be reused."""

    name = "log_asm.multi_pauli_meas"

    _PT: ClassVar[AttrConstraint[SurfaceCodeBasePatch]] = SurfaceCodeBasePatch.consistent_constr(
        same_type=True, same_has_placement=True
    )  # PatchType constraint

    _IP: ClassVar[IntConstraint] = IntVarConstraint(
        "InputPatches", AtLeast(2)
    )  # Number of inputs constraint, must be at least 2 patches.

    _LP: ClassVar[RangeConstraint[SurfaceCodeBasePatch]] = RangeVarConstraint(
        "LogicalPatches", RangeOf(_PT).of_length(_IP)
    )  # Exact number and types of logical patches constraint

    logical_patches = var_operand_def(_LP)
    bridge_patches = var_operand_def(RangeOf(_PT))
    rounds = prop_def(IntAttr.constr(AtLeast(0)))
    basis = prop_def(ArrayOfConstraint(RangeOf(base(PauliAttr)).of_length(_IP)))

    measurement = result_def(i1)
    res = var_result_def(_LP)

    assembly_format = (
        f"`<` {PlainIntAttr.use('$rounds')} `,` "
        f"{PauliAttr.plain_array_of_directive('$basis', '(', ')')} `>` "
        "`(` $logical_patches `:` type($logical_patches) `)` "
        "`(` $bridge_patches `:` type($bridge_patches) `)` "
        "attr-dict `->` type($measurement)"
    )
    custom_directives = (PlainIntAttr, PauliAttr.plain_array_of_directive())

    irdl_options = (AttrSizedOperandSegments(as_property=True),)

    def __init__(
        self,
        rounds: IntAttr | int,
        basis: Iterable[PauliAttr],
        logical_patches: Sequence[SSAValue],
        bridge_patches: Sequence[SSAValue],
    ):
        super().__init__(
            operands=[logical_patches, bridge_patches],
            result_types=[i1, [patch.type for patch in logical_patches]],
            properties={
                "rounds": IntAttr.get(rounds),
                "basis": ArrayAttr(basis),
            },
        )

    @override
    def verify_(self) -> None:
        """Verify this is a valid multi pauli."""
        patch_type = type(self.res[0].type)
        if not patch_type.defines_valid_logical(
            [cast(SurfaceCodeBasePatch, patch.type) for patch in self.logical_patches],
            [cast(SurfaceCodeBasePatch, patch.type) for patch in self.bridge_patches],
        ):  # All this casting is safe because the op constraints enforce it.
            msg = f"{self.name} has logical and bridge patches that do not form a valid logical."
            raise VerifyException(msg)

    def get_logical_patch_types(self) -> list[SurfaceCodeBasePatch]:
        """Return the logical patches as a list of attributes."""
        return [cast(SurfaceCodeBasePatch, patch.type) for patch in self.logical_patches]

    def get_bridge_patch_types(self) -> list[SurfaceCodeBasePatch]:
        """Return the bridge patches as a list of attributes"""
        return [cast(SurfaceCodeBasePatch, patch.type) for patch in self.bridge_patches]


# endregion

# region Gate Operations


@irdl_op_definition
class TransversalGateOp(BaseLogicalAssemblyOp, IRDLOperation):
    """Apply a gate transversally across one or more patches."""

    name = "log_asm.transversal"

    _LP: ClassVar[RangeConstraint[SurfaceCodeBasePatch]] = RangeOf(
        SurfaceCodeBasePatch.consistent_constr(
            same_type=True, same_has_placement=True, same_size=True
        )
    ).of_length(
        IntVarConstraint("InputPatches", AtLeast(1))
    )  # Exact number and types of logical patches constraint

    patches = var_operand_def(_LP)
    gate_type = prop_def(GateTypeAttr)  # TODO use qcore gates
    res = var_result_def(_LP)

    assembly_format = (
        f"`<` {GateTypeAttr.plain_directive('$gate_type')} `>` "
        "`(` $patches `:` type($patches) `)` attr-dict `->` type($res)"
    )
    custom_directives = (GateTypeAttr.plain_directive(),)

    def __init__(
        self,
        patches: Sequence[SSAValue] | SSAValue,
        gate_type: GateTypeAttr | GateTypeEnum,
        result_types: (Sequence[SurfaceCodeBasePatch] | SurfaceCodeBasePatch | None) = None,
    ):
        if isinstance(patches, SSAValue):
            patches = (patches,)
        if isinstance(result_types, SurfaceCodeBasePatch):
            result_types = (result_types,)
        super().__init__(
            operands=[patches],
            result_types=[
                ([patch.type for patch in patches] if result_types is None else result_types)
            ],
            properties={"gate_type": GateTypeAttr.from_argument(gate_type)},
        )

    @override
    def verify_(self) -> None:
        """Verify the location of each patch is not changed between `patches` and `res`."""
        if isinstance(self.res[0].type.placement, NoneAttr):
            # The _LP constraint enforces that if this is true for self.res[0].type then it
            # holds for all patch types in self.patches and self.res
            return  # If there is no placement - there is nothing more to verify

        for i, (in_patch, out_patch) in enumerate(zip(self.patches, self.res, strict=True)):
            in_type = cast(SurfaceCodeBasePatch, in_patch.type)
            in_placement = cast(PlacementAttr, in_type.placement)
            out_placement = cast(PlacementAttr, out_patch.type.placement)
            if in_placement.location != out_placement.location:
                msg = (
                    f"Operand patches cannot move during a {self.name} operation. "
                    f"Operand patch {i} has location: "
                    f"{tuple(val.value.data for val in in_placement.location)}, "
                    f"but has location {tuple(val.value.data for val in out_placement.location)} "
                    "in the result."
                )
                raise VerifyException(msg)
        # TODO Verify number of operands correlates with gate type


class _CastOpHasCanonicalizationPatternsTrait(HasCanonicalizationPatternsTrait):
    @override
    @classmethod
    def get_canonicalization_patterns(cls) -> tuple[RewritePattern, ...]:
        from deltakit_compile.passes.canonicalisation.logical_assembly import (  # noqa: PLC0415
            RemoveIdentityCasts,
            RemoveRedundantCasts,
        )  # Imported here to avoid circular imports.

        return (RemoveIdentityCasts(), RemoveRedundantCasts())


@irdl_op_definition
class CastOp(BaseLogicalAssemblyOp, IRDLOperation):
    """Cast between ``!log_asm.patch`` and ``!qcore.qubit_reg`` types."""

    name = "log_asm.cast"

    in_ = operand_def(base(BasePatch) | base(QubitRegType))
    out = result_def(base(BasePatch) | base(QubitRegType))

    assembly_format = "`(` $in_ `:` type($in_) `)` attr-dict `->` type($out)"

    traits = traits_def(Pure(), NoQuantumEffect(), _CastOpHasCanonicalizationPatternsTrait())

    def __init__(self, from_: SSAValue, to: BasePatch | QubitRegType) -> None:
        super().__init__(operands=[from_], result_types=[to])

    @override
    def verify_(self) -> None:
        assert isinstance(self.in_.type, (BasePatch, QubitRegType)), "Checked in constraints"
        assert isinstance(self.out.type, (BasePatch, QubitRegType)), "Checked in constraints"
        in_qubit_number = CastOp._qubit_number(self.in_.type)
        out_qubit_number = CastOp._qubit_number(self.out.type)
        if in_qubit_number != out_qubit_number:
            msg = (
                f"Cannot cast from {self.in_.type} ({in_qubit_number} qubits) to {self.out.type} "
                f"({out_qubit_number} qubits): the types represent a different number of qubits."
            )
            raise VerifyException(msg)

    @staticmethod
    def _qubit_number(patch_or_reg: BasePatch | QubitRegType) -> int:
        return (
            patch_or_reg.num_qubits
            if isinstance(patch_or_reg, BasePatch)
            else patch_or_reg.size.data
        )


# endregion

LogicalAsm = Dialect(
    "log_asm",
    [
        PatchDeclarationOp,
        RotateOp,
        MoveOp,
        GrowOp,
        ShrinkOp,
        StepOp,
        PrepareOp,
        MeasureOp,
        MeasStabOp,
        MultiPauliMeasOp,
        TransversalGateOp,
        CastOp,
    ],
    [
        OrientationAttr,
        GateTypeAttr,
        PlacementAttr,
        RotatedPlanarPatchType,
        UnrotatedPlanarPatchType,
    ],
)
