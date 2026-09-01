"""Tests for common utilities in rotated surface patch lowering."""

import pytest
from xdsl.dialects.builtin import ArrayAttr, IntAttr, NoneAttr

from deltakit_compile.dialects.logical_assembly import (
    OrientationEnum,
    PlacementAttr,
    RotatedPlanarPatchType,
)
from deltakit_compile.shared.patch.exceptions import UnplacedPatchError
from deltakit_compile.shared.patch.rotated_planar._placement import (
    _patch_properties_to_data_qubit_coordinates,
    _patch_properties_to_inner_ancilla_qubit_coordinates,
    _patch_properties_to_outer_ancilla_qubit_coordinates,
    get_data_qubits_indices_placement,
    patch_properties_to_coordinates,
    patch_type_to_coordinates,
)


class TestPatchPropertiesToCoordinates:
    """Tests for coordinate generation in patch_properties_to_coordinates."""

    def test_data_qubits_generation(self) -> None:
        """Test that data qubits are generated correctly with half-integer coordinates."""
        coordinates = _patch_properties_to_data_qubit_coordinates(2, 2, 0, 0)
        data_qubits = {(0.5, 0.5), (0.5, 1.5), (1.5, 0.5), (1.5, 1.5)}
        assert set(coordinates) == data_qubits

    def test_inner_ancilla_qubits_generation(self) -> None:
        """Test that inner ancilla qubits are generated correctly."""
        coordinates = _patch_properties_to_inner_ancilla_qubit_coordinates(3, 3, 0, 0)
        inner_ancillas = {(1, 1), (1, 2), (2, 1), (2, 2)}
        assert set(coordinates) == inner_ancillas

    @pytest.mark.parametrize(
        ("parity", "expected"),
        [(True, {(1, 3), (3, 2), (2, 0), (0, 1)}), (False, {(2, 3), (3, 1), (1, 0), (0, 2)})],
    )
    def test_outer_ancilla_qubits_parity_true(
        self, parity: bool, expected: set[tuple[int, int]]
    ) -> None:
        """Test outer ancilla qubit positions when parity is True."""
        coordinates = _patch_properties_to_outer_ancilla_qubit_coordinates(3, 3, 0, 0, parity)
        assert set(coordinates) == expected

    @pytest.mark.parametrize(("width", "height"), [(2, 2), (3, 3), (3, 17), (10, 10)])
    def test_coordinate_count_small_patch(self, width: int, height: int) -> None:
        """Test the total number of coordinates for a small patch."""
        coordinates = patch_properties_to_coordinates(width, height, 0, 0, parity=True)
        assert len(coordinates) == 2 * width * height - 1

    def test_parity_changes_coordinate_positions(self) -> None:
        """Test that parity affects which coordinates are selected."""
        coords_true = patch_properties_to_coordinates(3, 3, 0, 0, parity=True)
        coords_false = patch_properties_to_coordinates(3, 3, 0, 0, parity=False)

        # Same number of coordinates but different positions
        assert len(coords_true) == len(coords_false)
        assert len(set(coords_true) ^ set(coords_false)) == 8

    @pytest.mark.parametrize(("x", "y"), [(0, 0), (1, 1), (0.5, 6), (-10, 42)])
    def test_location_offsets_coordinates(self, x: float, y: float) -> None:
        coords = patch_properties_to_coordinates(3, 3, 0, 0)
        offset_coords = patch_properties_to_coordinates(3, 3, x, y)
        assert set(offset_coords) == {(a + x, b + y) for a, b in coords}

    @pytest.mark.parametrize(
        ("size", "offset", "expected_coordinates"),
        [
            (
                (2, 2),
                (0, 0),
                {(0.5, 0.5), (0.5, 1.5), (1.5, 0.5), (1.5, 1.5), (1, 0), (1, 1), (1, 2)},
            ),
            ((1, 2), (0, 0), {(0.5, 0.5), (0.5, 1.5), (1, 1)}),
            ((2, 1), (0, 0), {(0.5, 0.5), (1.5, 0.5), (1, 1)}),
        ],
    )
    def test_qubits_coordinates_generation(
        self,
        size: tuple[int, int],
        offset: tuple[float, float],
        expected_coordinates: set[tuple[float, float]],
    ) -> None:
        """Test that data qubits are generated correctly with half-integer coordinates."""
        coordinates = patch_properties_to_coordinates(*size, *offset)
        assert set(coordinates) == expected_coordinates


def make_size(x: int, y: int) -> ArrayAttr[IntAttr]:
    """Create a properly typed ArrayAttr[IntAttr] for patch size."""
    return ArrayAttr([IntAttr(x), IntAttr(y)])


def make_placement(
    x: float, y: float, orientation: OrientationEnum = OrientationEnum.VERTICAL_Z
) -> PlacementAttr:
    return PlacementAttr((x, y), orientation)


class TestPatchTypeToCoordinates:
    """Tests for coordinate generation in patch_type_to_coordinates."""

    @pytest.mark.parametrize(("width", "height"), [(2, 2), (3, 3), (3, 17), (10, 10)])
    def test_coordinate_count_small_patch(self, width: int, height: int) -> None:
        """Test the total number of coordinates for a small patch."""
        patch_type = RotatedPlanarPatchType(make_size(width, height), make_placement(0, 0))
        coordinates = patch_type_to_coordinates(patch_type, parity=True)
        assert len(coordinates) == 2 * width * height - 1

    def test_parity_changes_coordinate_positions(self) -> None:
        """Test that parity affects which coordinates are selected."""
        patch_type = RotatedPlanarPatchType(make_size(3, 3), make_placement(0, 0))

        coords_true = patch_type_to_coordinates(patch_type, parity=True)
        coords_false = patch_type_to_coordinates(patch_type, parity=False)

        # Same number of coordinates but different positions
        assert len(coords_true) == len(coords_false)
        assert len(set(coords_true) ^ set(coords_false)) == 8

    @pytest.mark.parametrize(("x", "y"), [(0, 0), (1, 1), (0.5, 6), (-10, 42)])
    def test_location_offsets_coordinates(self, x: float, y: float) -> None:
        patch_type = RotatedPlanarPatchType(make_size(3, 3), make_placement(0, 0))
        offset_patch_type = RotatedPlanarPatchType(
            make_size(3, 3), PlacementAttr((x, y), OrientationEnum.VERTICAL_Z)
        )
        coords = patch_type_to_coordinates(patch_type)
        offset_coords = patch_type_to_coordinates(offset_patch_type)
        assert set(offset_coords) == {(a + x, b + y) for a, b in coords}

    @pytest.mark.parametrize(
        ("size", "offset", "expected_coordinates"),
        [
            (
                (2, 2),
                (0, 0),
                {(0.5, 0.5), (0.5, 1.5), (1.5, 0.5), (1.5, 1.5), (1, 0), (1, 1), (1, 2)},
            ),
            ((1, 2), (0, 0), {(0.5, 0.5), (0.5, 1.5), (1, 1)}),
            ((2, 1), (0, 0), {(0.5, 0.5), (1.5, 0.5), (1, 1)}),
        ],
    )
    def test_qubits_coordinates_generation(
        self,
        size: tuple[int, int],
        offset: tuple[float, float],
        expected_coordinates: set[tuple[float, float]],
    ) -> None:
        """Test that data qubits are generated correctly with half-integer coordinates."""
        patch_type = RotatedPlanarPatchType(make_size(*size), make_placement(*offset))
        coordinates = patch_type_to_coordinates(patch_type)
        assert set(coordinates) == expected_coordinates

    def test_qubit_coordinates_generation_fails_on_patch_without_placement(self) -> None:
        msg = (
            r"Cannot get qubit coordinates from a patch type .* that does not have "
            "a location attribute"
        )
        with pytest.raises(UnplacedPatchError, match=msg):
            patch_type_to_coordinates(RotatedPlanarPatchType(make_size(2, 2), NoneAttr()))


@pytest.mark.parametrize(
    ("patch_type", "expected_placement"),
    [
        (RotatedPlanarPatchType((2, 2), None), [[0, 2], [1, 3]]),
        (RotatedPlanarPatchType((3, 3), None), ([[0, 3, 6], [1, 4, 7], [2, 5, 8]])),
        (RotatedPlanarPatchType((2, 3), None), ([[0, 3], [1, 4], [2, 5]])),
        (RotatedPlanarPatchType((1, 1), None), ([[0]])),
        (RotatedPlanarPatchType((10, 1), None), ([list(range(10))])),
        (RotatedPlanarPatchType((1, 10), None), ([[i] for i in range(10)])),
    ],
)
def test_get_data_qubits_indices_placement(
    patch_type: RotatedPlanarPatchType, expected_placement: list[list[int]]
) -> None:
    placement = get_data_qubits_indices_placement(patch_type)
    assert placement == expected_placement
