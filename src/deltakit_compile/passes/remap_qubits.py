# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module containing a pass that remaps physical qubits."""

from collections.abc import Sequence
from dataclasses import dataclass
from math import cos, radians, sin
from typing import NamedTuple

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import IntAttr, ModuleOp
from xdsl.ir import SSAValue
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)

from deltakit_compile.dialects.stim import QubitAllocOp, QubitCoordsOp, QubitMappingAttr
from deltakit_compile.exceptions import InvalidPassConfigurationException


class RotationConfig(NamedTuple):
    """Configuration for rotating qubits around a point."""

    angle: float
    """Angle to rotate qubits, in degrees. Rotation is anticlockwise."""
    center: tuple[float, float]
    """Coordinates of the point to rotate. These correspond to the first two dimensions of the qubit
    coordinates. The remaining dimensions are not modified."""


def _rotate(coords: Sequence[float], rotation_config: RotationConfig) -> list[float]:
    """Performs a rotation on the first 2 dimensions of a point.

    Rotate a point in the anticlockwise around a center point by a given angle in
    degrees. Will only rotate the first two dimensions."""
    if len(coords) < 2:
        msg = (
            f"Cannot apply rotation to qubits with less than 2 dimensions. "
            f"Qubit with coordinates {coords} cannot be rotated."
        )
        raise ValueError(msg)
    cx, cy = rotation_config.center
    angle = rotation_config.angle
    x, y = coords[:2]
    # Translate point to origin
    translated_x = x - cx
    translated_y = y - cy
    # Rotate point
    rotated_x = translated_x * cos(radians(angle)) - translated_y * sin(radians(angle))
    rotated_y = translated_x * sin(radians(angle)) + translated_y * cos(radians(angle))
    # Translate point back
    return [
        rotated_x + cx,
        rotated_y + cy,
        *coords[2:],
    ]


def _translate(coords: Sequence[float], offset: Sequence[float]) -> list[float]:
    """Translate a point by a given offset."""
    if len(coords) != len(offset):
        msg = (
            f"qubit_coord_offset ({offset}) length doesn't "
            f"match a qubit's coordinates ({coords}) length"
        )
        raise ValueError(msg)
    return [c + o for c, o in zip(coords, offset, strict=True)]


class _UpdateQubitCoordsPattern(RewritePattern):
    """Update qubit coords and qubit_ssa_coord_map with their new locations."""

    def __init__(
        self,
        qubit_coord_offset: list[float] | None,
        qubit_ssa_coord_map: dict[SSAValue, QubitMappingAttr],
        qubit_rotation_config: RotationConfig | None,
        decimal_places: int,
    ) -> None:
        self.qubit_coord_offset = qubit_coord_offset
        self.qubit_ssa_coord_map = qubit_ssa_coord_map
        self.qubit_rotation_config = qubit_rotation_config
        self.decimal_places = decimal_places

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: QubitCoordsOp, rewriter: PatternRewriter) -> None:
        coords = op.qubitcoord.coords.data
        new_coords: list[float] = [coord.data for coord in coords]

        if self.qubit_rotation_config is not None:
            new_coords = _rotate(
                new_coords,
                self.qubit_rotation_config,
            )

        if self.qubit_coord_offset is not None:
            new_coords = _translate(
                new_coords,
                self.qubit_coord_offset,
            )

        new_coords = [round(coord, self.decimal_places) for coord in new_coords]
        op.qubitcoord = QubitMappingAttr(coords=new_coords)
        rewriter.notify_op_modified(op)

        self.qubit_ssa_coord_map[op.operands[0]] = op.qubitcoord


class _UpdateQubitIDPattern(RewritePattern):
    """Update qubit IDs to match those used by the control system."""

    def __init__(
        self,
        coord_qubit_id_map: dict[tuple[float, ...], int],
        qubit_ssa_coord_map: dict[SSAValue, QubitMappingAttr],
    ) -> None:
        self.coord_qubit_id_map = coord_qubit_id_map
        self.qubit_ssa_coord_map = qubit_ssa_coord_map

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: QubitAllocOp, rewriter: PatternRewriter) -> None:
        if op.res not in self.qubit_ssa_coord_map:
            msg = f"Qubit {op.id.data} used without assigning it QUBIT_COORDS"
            raise ValueError(msg)

        coords_key = tuple(e.data for e in self.qubit_ssa_coord_map[op.res].coords.data)
        if coords_key not in self.coord_qubit_id_map:
            msg = (
                f"A qubit with coordinates {coords_key} is used in the program, but "
                "there is no qubit with those coordinates in the qubit_mapping. "
                "If you are rotating/translating, this may be a precision issue. Check if there "
                "is a qubit in the qubit_mapping with coordinates close to the above coordinates. "
                "You can decrease the 'decimal_places' parameter in the remap-qubits pass to "
                "fix this issue."
            )
            raise ValueError(msg)

        op.id = IntAttr(self.coord_qubit_id_map[coords_key])
        rewriter.notify_op_modified(op)


@dataclass(frozen=True)
class RemapQubits(ModulePass):
    """Pass for transforming the qubit coordinates and remapping the IDs of all physical qubits to
    the provided configuration.

    Translation is performed after rotation, so the qubits are first rotated around the specified
    point and then translated by the given offset. To avoid precision issues when matching the new
    coordinates to the qubit mapping, the coordinates in the qubit mapping and the calculated
    coordinates are always rounded, regardless of whether any modification to the coordinates is
    applied. This means that even if no rotation or translation is applied, the coordinates will
    still be rounded."""

    name = "remap-qubits"

    qubit_coord_offset: list[float] | None
    """Offset to apply to each qubit coordinate dimension."""
    qubit_mapping: dict[int, list[float]] | None
    """Mapping between qubit ID in the control system and its coordinate."""
    qubit_rotation_config: RotationConfig | tuple[float, tuple[float, float]] | None = None
    """Configuration for rotating qubits around a point. Specify a rotation angle in degrees
    (+ve is anticlockwise) and center. Only modifies the first two dimensions. If None,
    no rotation is applied."""
    decimal_places: int = 5
    """Number of decimal places to round the coordinates to. This is to avoid precision issues when
    matching rotated coordinates to the qubit_mapping."""

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        if self.qubit_mapping is None:
            msg = f"Cannot apply '{self.name}' transformation unless 'qubit_mapping' is provided."
            raise InvalidPassConfigurationException(msg)

        qubit_ssa_coord_map: dict[SSAValue, QubitMappingAttr] = {}
        coord_qubit_id_map = {
            tuple(round(coordinate, self.decimal_places) for coordinate in v): int(k)
            for k, v in self.qubit_mapping.items()
        }

        qubit_rotation_config = (
            RotationConfig(*self.qubit_rotation_config)
            if isinstance(self.qubit_rotation_config, tuple)
            else self.qubit_rotation_config
        )

        PatternRewriteWalker(
            _UpdateQubitCoordsPattern(
                self.qubit_coord_offset,
                qubit_ssa_coord_map,
                qubit_rotation_config,
                self.decimal_places,
            ),
            apply_recursively=False,
        ).rewrite_module(op)

        PatternRewriteWalker(
            _UpdateQubitIDPattern(coord_qubit_id_map, qubit_ssa_coord_map),
            apply_recursively=False,
        ).rewrite_module(op)
