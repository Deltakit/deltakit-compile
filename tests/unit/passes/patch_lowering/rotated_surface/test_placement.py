"""Tests for common utilities in rotated surface patch lowering."""

import pytest
from numpy.testing import assert_allclose
from xdsl.dialects.builtin import ArrayAttr, IntAttr, NoneAttr

from deltakit_compile.dialects.logical_assembly import (
    OrientationEnum,
    PlacementAttr,
    RotatedPlanarPatchType,
)
from deltakit_compile.dialects.qcore import PauliAttr
from deltakit_compile.passes.patch_lowering.rotated_surface._placement import (
    BaseObservablePlacementStrategy,
    ObservablePlacement,
    PreDefinedObservablePlacementStrategy,
)
from deltakit_compile.shared.patch.rotated_planar._placement import patch_type_to_coordinates


def create_patch_with_placement(
    width: int,
    height: int,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    orientation: OrientationEnum = OrientationEnum.HORIZONTAL_Z,
) -> RotatedPlanarPatchType:
    """Helper to create a RotatedPlanarPatchType with placement."""
    size = ArrayAttr([IntAttr.new(width), IntAttr.new(height)])
    placement = PlacementAttr([offset_x, offset_y], orientation)
    return RotatedPlanarPatchType(size, placement)


def create_patch_without_placement(width: int, height: int) -> RotatedPlanarPatchType:
    """Helper to create a RotatedPlanarPatchType without placement."""
    size = ArrayAttr([IntAttr.new(width), IntAttr.new(height)])
    return RotatedPlanarPatchType(size, NoneAttr())


class TestPreDefinedObservablePlacementStrategy:
    """Tests for ``PreDefinedObservablePlacementStrategy.place_on_patch`` method."""

    @pytest.mark.parametrize(
        ("z_orientation", "strategy", "size", "offset", "expected_coordinates"),
        [
            (
                OrientationEnum.HORIZONTAL_Z,
                PreDefinedObservablePlacementStrategy(horizontal=ObservablePlacement.MAX),
                (3, 3),
                (0, 0),
                ((0.5, 2.5), (1.5, 2.5), (2.5, 2.5)),
            ),
            (
                OrientationEnum.HORIZONTAL_Z,
                PreDefinedObservablePlacementStrategy(horizontal=ObservablePlacement.MIDDLE),
                (3, 3),
                (0, 0),
                ((0.5, 1.5), (1.5, 1.5), (2.5, 1.5)),
            ),
            (
                OrientationEnum.HORIZONTAL_Z,
                PreDefinedObservablePlacementStrategy(horizontal=ObservablePlacement.MIN),
                (3, 3),
                (0, 0),
                ((0.5, 0.5), (1.5, 0.5), (2.5, 0.5)),
            ),
            (
                OrientationEnum.VERTICAL_Z,
                PreDefinedObservablePlacementStrategy(vertical=ObservablePlacement.MIN),
                (3, 3),
                (0, 0),
                ((0.5, 0.5), (0.5, 1.5), (0.5, 2.5)),
            ),
            (
                OrientationEnum.VERTICAL_Z,
                PreDefinedObservablePlacementStrategy(vertical=ObservablePlacement.MIDDLE),
                (3, 3),
                (0, 0),
                ((1.5, 0.5), (1.5, 1.5), (1.5, 2.5)),
            ),
            (
                OrientationEnum.VERTICAL_Z,
                PreDefinedObservablePlacementStrategy(vertical=ObservablePlacement.MAX),
                (3, 3),
                (0, 0),
                ((2.5, 0.5), (2.5, 1.5), (2.5, 2.5)),
            ),
            (
                OrientationEnum.HORIZONTAL_Z,
                PreDefinedObservablePlacementStrategy(horizontal=ObservablePlacement.MIDDLE),
                (3, 5),
                (0, 0),
                ((0.5, 2.5), (1.5, 2.5), (2.5, 2.5)),
            ),
            (
                OrientationEnum.VERTICAL_Z,
                PreDefinedObservablePlacementStrategy(vertical=ObservablePlacement.MAX),
                (3, 3),
                (-3.5, 6.5),
                ((-1, 7), (-1, 8), (-1, 9)),
            ),
        ],
    )
    def test_predefined_observable_placement_strategy(
        self,
        z_orientation: OrientationEnum,
        strategy: BaseObservablePlacementStrategy,
        size: tuple[int, int],
        offset: tuple[float, float],
        expected_coordinates: tuple[tuple[float, float], ...],
    ) -> None:
        patch = create_patch_with_placement(*size, *offset, orientation=z_orientation)
        indices = strategy.place_on_patch(patch, PauliAttr.Z())
        coordinates = patch_type_to_coordinates(patch)
        assert_allclose(sorted([coordinates[i] for i in indices]), expected_coordinates)

    def test_predefined_observable_placement_strategy_x_basis(self) -> None:
        patch = create_patch_with_placement(3, 3, orientation=OrientationEnum.VERTICAL_Z)
        strategy = PreDefinedObservablePlacementStrategy(horizontal=ObservablePlacement.MAX)
        indices = strategy.place_on_patch(patch, PauliAttr.X())
        coordinates = patch_type_to_coordinates(patch)
        assert_allclose(
            sorted([coordinates[i] for i in indices]), ((0.5, 2.5), (1.5, 2.5), (2.5, 2.5))
        )

    def test_raises_for_patch_without_placement(self) -> None:
        """Raises RuntimeError when patch has no placement."""
        patch = create_patch_without_placement(3, 3)
        strategy = PreDefinedObservablePlacementStrategy()

        with pytest.raises(
            RuntimeError, match="Cannot place an observable on a patch without a location"
        ):
            strategy.place_on_patch(patch, PauliAttr.Z())

    def test_raises_for_y_basis(self) -> None:
        """Raises NotImplementedError for Y basis."""
        patch = create_patch_with_placement(3, 3)
        strategy = PreDefinedObservablePlacementStrategy()

        with pytest.raises(
            NotImplementedError, match="Observables in the Y basis are not supported yet"
        ):
            strategy.place_on_patch(patch, PauliAttr.Y())

    def test_7x7_patch_horizontal_placements(self) -> None:
        patch = create_patch_with_placement(7, 7)

        strategy_top = PreDefinedObservablePlacementStrategy(horizontal=ObservablePlacement.MAX)
        indices_top = strategy_top.place_on_patch(patch, PauliAttr.Z())

        strategy_bottom = PreDefinedObservablePlacementStrategy(horizontal=ObservablePlacement.MIN)
        indices_bottom = strategy_bottom.place_on_patch(patch, PauliAttr.Z())

        strategy_middle = PreDefinedObservablePlacementStrategy(
            horizontal=ObservablePlacement.MIDDLE
        )
        indices_middle = strategy_middle.place_on_patch(patch, PauliAttr.Z())

        # All should have length 7 (7 qubits in each row)
        assert len(indices_top) == 7
        assert len(indices_bottom) == 7
        assert len(indices_middle) == 7

        # All should be different
        assert set(indices_top) != set(indices_bottom)
        assert set(indices_top) != set(indices_middle)
        assert set(indices_bottom) != set(indices_middle)
