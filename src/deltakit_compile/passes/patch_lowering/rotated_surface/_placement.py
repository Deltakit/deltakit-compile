# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""This module implements utilities for qubit placement.

The main function implemented by this module is :func:`patch_type_to_coordinates` that translates
any rotated surface code patch into coordinates of qubits that are used to implement that patch.

For the moment, this function is used as the source of truth and common convention for qubit order
and placement for a patch. Eventually, we want that function and the order it implements to become
an implementation detail.
"""

from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from math import isclose
from typing import Protocol

from typing_extensions import override
from xdsl.dialects.builtin import NoneAttr

from deltakit_compile.dialects.logical_assembly import OrientationEnum, RotatedPlanarPatchType
from deltakit_compile.dialects.qcore import PauliAttr
from deltakit_compile.shared.patch.rotated_planar._placement import patch_type_to_coordinates


class ObservablePlacement(Enum):
    """Place on the surface code patch where the observable can be located."""

    MIN = auto()
    """Observable is located on the left-most or bottom-most qubits."""
    MIDDLE = auto()
    """Observable is located on the middle line of data-qubits."""
    MAX = auto()
    """Observable is located on the right-most or top-most qubits."""


class BaseObservablePlacementStrategy(Protocol):
    @abstractmethod
    def place_on_patch(
        self, patch_type: RotatedPlanarPatchType, basis: PauliAttr
    ) -> tuple[int, ...]:
        """Returns indices of qubits on which the observable should be placed.

        Parameters:
            patch_type: type of the patch to place an observable on.
            basis: basis of the observable to place.

        Returns:
            The indices of qubits from the patch that should be included in the observable.
        """


@dataclass(frozen=True)
class PreDefinedObservablePlacementStrategy(BaseObservablePlacementStrategy):
    """Default implementation of the ``BaseObservablePlacementStrategy`` protocol for the rotated
    surface code and some usual placements of the observable."""

    horizontal: ObservablePlacement = ObservablePlacement.MAX
    """Defaults to an horizontal observable located on the top-most qubits."""
    vertical: ObservablePlacement = ObservablePlacement.MIN
    """Default to a vertical observable located on the left-most qubits."""

    @override
    def place_on_patch(
        self, patch_type: RotatedPlanarPatchType, basis: PauliAttr
    ) -> tuple[int, ...]:
        if isinstance(patch_type.placement, NoneAttr):
            msg = "Cannot place an observable on a patch without a location."
            raise RuntimeError(msg)
        if basis == PauliAttr.Y():
            msg = "Observables in the Y basis are not supported yet."
            raise NotImplementedError(msg)

        orientation = patch_type.placement.orientation
        is_horizontal: bool = orientation.data == (
            OrientationEnum.VERTICAL_Z if basis == PauliAttr.X() else OrientationEnum.HORIZONTAL_Z
        )

        observable_placement = self.horizontal if is_horizontal else self.vertical

        width, height = patch_type.size_data
        data_qubits_count = width * height
        data_qubits_coords = patch_type_to_coordinates(patch_type)[:data_qubits_count]

        x_coords = sorted({coord[0] for coord in data_qubits_coords})
        y_coords = sorted({coord[1] for coord in data_qubits_coords})

        if is_horizontal:
            match observable_placement:
                case ObservablePlacement.MAX:
                    target_y = y_coords[-1]
                case ObservablePlacement.MIN:
                    target_y = y_coords[0]
                case ObservablePlacement.MIDDLE:
                    target_y = y_coords[len(y_coords) // 2]
            return tuple(
                idx for idx, coord in enumerate(data_qubits_coords) if isclose(coord[1], target_y)
            )

        match observable_placement:
            case ObservablePlacement.MIN:
                target_x = x_coords[0]
            case ObservablePlacement.MAX:
                target_x = x_coords[-1]
            case ObservablePlacement.MIDDLE:
                target_x = x_coords[len(x_coords) // 2]
        return tuple(
            idx for idx, coord in enumerate(data_qubits_coords) if isclose(coord[0], target_x)
        )


class ObservablePlacementStrategy(Enum):
    """Exhaustive enumeration of all the placement strategies that are currently implemented."""

    PRE_DEFINED_TOP_LEFT = PreDefinedObservablePlacementStrategy(
        ObservablePlacement.MAX, ObservablePlacement.MIN
    )
    """Place observable on the top-most or left-most data-qubits."""

    PRE_DEFINED_TOP_CENTER = PreDefinedObservablePlacementStrategy(
        ObservablePlacement.MAX, ObservablePlacement.MIDDLE
    )
    """Place observable on the top-most or vertically centered data-qubits."""

    PRE_DEFINED_TOP_RIGHT = PreDefinedObservablePlacementStrategy(
        ObservablePlacement.MAX, ObservablePlacement.MAX
    )
    """Place observable on the top-most or right-most data-qubits."""

    PRE_DEFINED_CENTER_LEFT = PreDefinedObservablePlacementStrategy(
        ObservablePlacement.MIDDLE, ObservablePlacement.MIN
    )
    """Place observable on the horizontally-centered or left-most data-qubits."""

    PRE_DEFINED_CENTER_CENTER = PreDefinedObservablePlacementStrategy(
        ObservablePlacement.MIDDLE, ObservablePlacement.MIDDLE
    )
    """Place observable on the horizontally-centered or vertically-centered data-qubits."""

    PRE_DEFINED_CENTER_RIGHT = PreDefinedObservablePlacementStrategy(
        ObservablePlacement.MIDDLE, ObservablePlacement.MAX
    )
    """Place observable on the horizontally-centered or right-most data-qubits."""

    PRE_DEFINED_BOTTOM_LEFT = PreDefinedObservablePlacementStrategy(
        ObservablePlacement.MIN, ObservablePlacement.MIN
    )
    """Place observable on the bottom-most or left-most data-qubits."""

    PRE_DEFINED_BOTTOM_CENTER = PreDefinedObservablePlacementStrategy(
        ObservablePlacement.MIN, ObservablePlacement.MIDDLE
    )
    """Place observable on the bottom-most or vertically-centered data-qubits."""

    PRE_DEFINED_BOTTOM_RIGHT = PreDefinedObservablePlacementStrategy(
        ObservablePlacement.MIN, ObservablePlacement.MAX
    )
    """Place observable on the bottom-most or right-most data-qubits."""
