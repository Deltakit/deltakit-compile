import pytest
from xdsl.dialects.builtin import ArrayAttr, IntAttr

from deltakit_compile.dialects.logical_assembly import (
    OrientationEnum,
    PlacementAttr,
    RotatedPlanarPatchType,
)
from deltakit_compile.dialects.qcore import PauliStringAttr
from deltakit_compile.shared.patch.rotated_planar._stabilisers import (
    _ID,
    _XX,
    _XXXX,
    _ZZ,
    _ZZZZ,
    _increase_to_parity,
    global_stabilisers_for_memory_on_patch,
    local_stabilisers_for_memory_on_patch,
)


def make_size(x: int, y: int) -> ArrayAttr[IntAttr]:
    return ArrayAttr([IntAttr(x), IntAttr(y)])


@pytest.mark.parametrize(
    ("start", "parity", "result"),
    [(0, True, 0), (1, True, 2), (0, False, 1), (1, False, 1), (13, True, 14)],
)
def test_increase_to_parity(start: int, parity: bool, result: int) -> None:
    assert _increase_to_parity(start, parity) == result


class TestGetStabilisers:
    @pytest.mark.parametrize(
        ("size", "orientation", "parity", "expected_stabilisers"),
        [
            (
                (2, 2),
                OrientationEnum.VERTICAL_Z,
                True,
                [
                    [_ID, _ZZ, _ID],
                    [_ID, _XXXX, _ID],
                    [_ID, _ZZ, _ID],
                ],
            ),
            (
                (2, 2),
                OrientationEnum.HORIZONTAL_Z,
                True,
                [
                    [_ID, _XX, _ID],
                    [_ID, _ZZZZ, _ID],
                    [_ID, _XX, _ID],
                ],
            ),
            (
                (2, 2),
                OrientationEnum.VERTICAL_Z,
                False,
                [
                    [_ID, _ID, _ID],
                    [_XX, _ZZZZ, _XX],
                    [_ID, _ID, _ID],
                ],
            ),
            (
                (2, 2),
                OrientationEnum.HORIZONTAL_Z,
                False,
                [
                    [_ID, _ID, _ID],
                    [_ZZ, _XXXX, _ZZ],
                    [_ID, _ID, _ID],
                ],
            ),
            (
                (1, 2),
                OrientationEnum.VERTICAL_Z,
                True,
                [
                    [_ID, _ID],
                    [_ID, _XX],
                    [_ID, _ID],
                ],
            ),
            (
                (1, 2),
                OrientationEnum.HORIZONTAL_Z,
                True,
                [
                    [_ID, _ID],
                    [_ID, _ZZ],
                    [_ID, _ID],
                ],
            ),
            (
                (1, 2),
                OrientationEnum.HORIZONTAL_Z,
                False,
                [
                    [_ID, _ID],
                    [_ZZ, _ID],
                    [_ID, _ID],
                ],
            ),
            (
                (1, 2),
                OrientationEnum.VERTICAL_Z,
                False,
                [
                    [_ID, _ID],
                    [_XX, _ID],
                    [_ID, _ID],
                ],
            ),
            (
                (2, 1),
                OrientationEnum.HORIZONTAL_Z,
                True,
                [
                    [_ID, _XX, _ID],
                    [_ID, _ID, _ID],
                ],
            ),
            (
                (2, 1),
                OrientationEnum.VERTICAL_Z,
                True,
                [
                    [_ID, _ZZ, _ID],
                    [_ID, _ID, _ID],
                ],
            ),
            (
                (2, 1),
                OrientationEnum.HORIZONTAL_Z,
                False,
                [
                    [_ID, _ID, _ID],
                    [_ID, _XX, _ID],
                ],
            ),
            (
                (2, 1),
                OrientationEnum.VERTICAL_Z,
                False,
                [
                    [_ID, _ID, _ID],
                    [_ID, _ZZ, _ID],
                ],
            ),
            (
                (1, 3),
                OrientationEnum.VERTICAL_Z,
                True,
                [
                    [_ID, _ID],
                    [_ID, _XX],
                    [_XX, _ID],
                    [_ID, _ID],
                ],
            ),
            (
                (1, 3),
                OrientationEnum.HORIZONTAL_Z,
                False,
                [
                    [_ID, _ID],
                    [_ZZ, _ID],
                    [_ID, _ZZ],
                    [_ID, _ID],
                ],
            ),
            (
                (3, 1),
                OrientationEnum.VERTICAL_Z,
                True,
                [
                    [_ID, _ZZ, _ID, _ID],
                    [_ID, _ID, _ZZ, _ID],
                ],
            ),
            (
                (3, 1),
                OrientationEnum.HORIZONTAL_Z,
                False,
                [
                    [_ID, _ID, _XX, _ID],
                    [_ID, _XX, _ID, _ID],
                ],
            ),
        ],
    )
    def test_get_local_stabilisers_edge_case(
        self,
        size: tuple[int, int],
        orientation: OrientationEnum,
        parity: bool,
        expected_stabilisers: list[list[PauliStringAttr]],
    ) -> None:
        patch_type = RotatedPlanarPatchType(make_size(*size), PlacementAttr((0, 0), orientation))
        stabilisers = local_stabilisers_for_memory_on_patch(patch_type, parity=parity)
        # Note that ``expected_stabilisers`` is in reading form (origin considered at the top-left)
        # because that's more convenient to read/write for humans. To match the "origin at the
        # bottom-left" convention, it should be reversed here.
        assert stabilisers == expected_stabilisers[::-1]

    @pytest.mark.parametrize("parity", [True, False])
    @pytest.mark.parametrize("size", [(3, 3), (10, 11), (4, 4), (5, 6)])
    @pytest.mark.parametrize("orientation", OrientationEnum)
    def test_get_local_stabilisers(
        self, parity: bool, size: tuple[int, int], orientation: OrientationEnum
    ) -> None:
        """Test get_stabilisers with different parity values."""
        width, height = size
        patch_type = RotatedPlanarPatchType(
            make_size(width, height), PlacementAttr((0, 0), orientation)
        )
        stabilisers = local_stabilisers_for_memory_on_patch(patch_type, parity=parity)
        assert len(stabilisers) == height + 1
        assert len(stabilisers[0]) == width + 1
        top = _ZZ if orientation == OrientationEnum.VERTICAL_Z else _XX
        top4 = _ZZZZ if orientation == OrientationEnum.VERTICAL_Z else _XXXX
        if parity:
            assert stabilisers[-1][1] == top
            assert stabilisers[-1][2] == _ID
            assert stabilisers[-2][1] == top4.flipped()
            assert stabilisers[-2][2] == top4
        else:
            assert stabilisers[-1][1] == _ID
            assert stabilisers[-1][2] == top
            assert stabilisers[-2][1] == top4
            assert stabilisers[-2][2] == top4.flipped()

    @pytest.mark.parametrize(
        ("size", "orientation", "parity", "expected_stabilisers"),
        [
            (
                (2, 2),
                OrientationEnum.VERTICAL_Z,
                True,
                [
                    PauliStringAttr((("Z", 0), ("Z", 2)), length=7),
                    PauliStringAttr((("X", 0), ("X", 1), ("X", 2), ("X", 3)), length=7),
                    PauliStringAttr((("Z", 1), ("Z", 3)), length=7),
                ],
            ),
            (
                (2, 2),
                OrientationEnum.HORIZONTAL_Z,
                True,
                [
                    PauliStringAttr((("X", 0), ("X", 2)), length=7),
                    PauliStringAttr((("Z", 0), ("Z", 1), ("Z", 2), ("Z", 3)), length=7),
                    PauliStringAttr((("X", 1), ("X", 3)), length=7),
                ],
            ),
            (
                (2, 2),
                OrientationEnum.VERTICAL_Z,
                False,
                [
                    PauliStringAttr((("X", 0), ("X", 1)), length=7),
                    PauliStringAttr((("Z", 0), ("Z", 1), ("Z", 2), ("Z", 3)), length=7),
                    PauliStringAttr((("X", 2), ("X", 3)), length=7),
                ],
            ),
            (
                (2, 2),
                OrientationEnum.HORIZONTAL_Z,
                False,
                [
                    PauliStringAttr((("Z", 0), ("Z", 1)), length=7),
                    PauliStringAttr((("X", 0), ("X", 1), ("X", 2), ("X", 3)), length=7),
                    PauliStringAttr((("Z", 2), ("Z", 3)), length=7),
                ],
            ),
        ],
    )
    def test_get_global_stabilisers_edge_case(
        self,
        size: tuple[int, int],
        orientation: OrientationEnum,
        parity: bool,
        expected_stabilisers: list[PauliStringAttr],
    ) -> None:
        patch_type = RotatedPlanarPatchType(make_size(*size), PlacementAttr((0, 0), orientation))
        stabilisers = global_stabilisers_for_memory_on_patch(patch_type, parity)
        # Note that ``expected_stabilisers`` is in reading form (origin considered at the top-left)
        # because that's more convenient to read/write for humans. To match the "origin at the
        # bottom-left" convention, it should be reversed here.
        assert stabilisers == expected_stabilisers
