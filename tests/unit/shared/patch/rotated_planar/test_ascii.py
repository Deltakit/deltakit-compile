import re

import pytest

from deltakit_compile.frontend.logasm import RotatedPlanarPatch
from deltakit_compile.shared.patch.exceptions import UnsizedPatchError
from deltakit_compile.shared.patch.rotated_planar._ascii import render_rotated_planar_patch_ascii

# 2x2 patch with axes
_2_2_0_0_axes = r"""
2 |     5
  | 1-------3
1 | |   4   |
  | 0-------2
0 |     6
  +----------
        1"""

# 2x2 patch without axes
_2_2_0_0_noaxes = r"""
    5
  /   \
1-------3
|       |
|   4   |
|       |
0-------2
  \   /
    6"""

# 1x1 patch (single data qubit)
_1_1_0_0_noaxes = """
0"""

# 1x2 patch (2 rows, 1 column)
_1_2_0_0_noaxes = r"""
1
| \
|   2
| /
0"""

# 2x1 patch (1 row, 2 columns)
_2_1_0_0_noaxes = r"""
    2
  /   \
0-------1"""

# 3x2 patch without axes (3 columns, 2 rows)
_3_2_0_0_noaxes = r"""
     8
   /   \
 1-------3-------5
 |       |       | \
 |   6   |   7   |   9
 |       |       | /
 0-------2-------4
   \   /
    10"""

# 3x3 patch without axes
_3_3_0_0_noaxes = r"""
        13
       /   \
     2-------5-------8
     |       |       | \
     |  10   |  12   |  14
     |       |       | /
     1-------4-------7
   / |       |       |
16   |   9   |  11   |
   \ |       |       |
     0-------3-------6
               \   /
                15"""

# 4x4 patch without axes - larger patch
_4_4_0_0_noaxes = r"""
        25              26
       /   \           /   \
     3-------7------11------15
     |       |       |       |
     |  18   |  21   |  24   |
     |       |       |       |
     2-------6------10------14
   / |       |       |       | \
30   |  17   |  20   |  23   |  27
   \ |       |       |       | /
     1-------5-------9------13
     |       |       |       |
     |  16   |  19   |  22   |
     |       |       |       |
     0-------4-------8------12
       \   /           \   /
        29              28"""

# 5x1 patch (1 row, 5 columns) - wide patch
_5_1_0_0_noaxes = r"""
    5               6
  /   \           /   \
0-------1-------2-------3-------4
          \   /           \   /
            8               7"""

# 1x5 patch (5 rows, 1 column) - tall patch
_1_5_0_0_noaxes = r"""
    4
    | \
    |   7
    | /
    3
  / |
5   |
  \ |
    2
    | \
    |   8
    | /
    1
  / |
6   |
  \ |
    0"""

# 2x2 patch with non-zero offset and axes
_2_2_1_1_axes = r"""
3 |     5
  | 1-------3
2 | |   4   |
  | 0-------2
1 |     6
  +----------
        2"""

# 2x2 patch with negative offset and axes
_2_2_minus_1_minus_1_axes = r"""
 1 |     5
   | 1-------3
 0 | |   4   |
   | 0-------2
-1 |     6
   +----------
         0"""

_3_digits_qubit_indices = r"""
467 |             137                     138                     139
    |       10----------21----------32----------43----------54----------65----------76
466 |        |    86     |    96     |    106    |    116    |    126    |    136    |    140
    |        9----------20----------31----------42----------53----------64----------75
465 | 152    |    85     |    95     |    105    |    115    |    125    |    135    |
    |        8----------19----------30----------41----------52----------63----------74
464 |        |    84     |    94     |    104    |    114    |    124    |    134    |    141
    |        7----------18----------29----------40----------51----------62----------73
463 | 151    |    83     |    93     |    103    |    113    |    123    |    133    |
    |        6----------17----------28----------39----------50----------61----------72
462 |        |    82     |    92     |    102    |    112    |    122    |    132    |    142
    |        5----------16----------27----------38----------49----------60----------71
461 | 150    |    81     |    91     |    101    |    111    |    121    |    131    |
    |        4----------15----------26----------37----------48----------59----------70
460 |        |    80     |    90     |    100    |    110    |    120    |    130    |    143
    |        3----------14----------25----------36----------47----------58----------69
459 | 149    |    79     |    89     |    99     |    109    |    119    |    129    |
    |        2----------13----------24----------35----------46----------57----------68
458 |        |    78     |    88     |    98     |    108    |    118    |    128    |    144
    |        1----------12----------23----------34----------45----------56----------67
457 | 148    |    77     |    87     |    97     |    107    |    117    |    127    |
    |        0----------11----------22----------33----------44----------55----------66
456 |                         147                     146                     145
    +----------------------------------------------------------------------------------------
      100         101         102         103         104         105         106         107"""


@pytest.mark.parametrize(
    ("width", "height", "offx", "offy", "axes", "expected"),
    [
        # Basic 2x2 cases with and without axes
        pytest.param(2, 2, 0, 0, True, _2_2_0_0_axes, id="2x2_with_axes"),
        pytest.param(2, 2, 0, 0, False, _2_2_0_0_noaxes, id="2x2_without_axes"),
        # Edge cases - minimum sizes
        pytest.param(1, 1, 0, 0, False, _1_1_0_0_noaxes, id="1x1_minimum_single_qubit"),
        # Rectangular patches - different aspect ratios
        pytest.param(1, 2, 0, 0, False, _1_2_0_0_noaxes, id="1x2_single_column"),
        pytest.param(2, 1, 0, 0, False, _2_1_0_0_noaxes, id="2x1_single_row"),
        pytest.param(3, 2, 0, 0, False, _3_2_0_0_noaxes, id="3x2_rectangular"),
        # Larger patches
        pytest.param(3, 3, 0, 0, False, _3_3_0_0_noaxes, id="3x3_medium_square"),
        pytest.param(4, 4, 0, 0, False, _4_4_0_0_noaxes, id="4x4_large_square"),
        # Very wide and very tall patches
        pytest.param(5, 1, 0, 0, False, _5_1_0_0_noaxes, id="5x1_very_wide"),
        pytest.param(1, 5, 0, 0, False, _1_5_0_0_noaxes, id="1x5_very_tall"),
        # With non-zero offsets
        pytest.param(2, 2, 1, 1, True, _2_2_1_1_axes, id="2x2_positive_offset_with_axes"),
        pytest.param(
            2, 2, -1, -1, True, _2_2_minus_1_minus_1_axes, id="2x2_negative_offset_with_axes"
        ),
        # 3-digit qubit indices
        pytest.param(7, 11, 100, 456, True, _3_digits_qubit_indices, id="3_digits_qubit_indices"),
    ],
)
def test_ascii_representation(
    width: int, height: int, offx: int, offy: int, axes: bool, expected: str
) -> None:
    """Test ASCII representation of RotatedPlanarPatch for various configurations.

    This test covers:
    - Basic patch sizes with and without axes
    - Edge cases (1x1 minimum size)
    - Rectangular patches with different aspect ratios
    - Larger patches
    - Extreme dimensions (very wide/tall)
    - Positive and negative offsets

    Args:
        width: Patch width in data qubits
        height: Patch height in data qubits
        offx: X offset (location)
        offy: Y offset (location)
        axes: Whether to include coordinate axes
        expected: Expected ASCII output
    """
    patch = RotatedPlanarPatch(width, height, location=(offx, offy))
    ascii_repr = patch.to_ascii(axes=axes)
    # Remove the leading newline that has been inserted in parameters to make them
    # human readable.
    assert ascii_repr == expected.lstrip("\n")


@pytest.mark.xfail(reason="Unsized Patches are not supported")
def test_patch_to_ascii_raises_on_unsized_patch() -> None:
    msg = re.escape("Cannot get the ASCII representation of unsized patches.")
    with pytest.raises(UnsizedPatchError, match=msg):
        RotatedPlanarPatch().to_ascii()


@pytest.mark.parametrize(("width", "height"), [(None, 3), (3, None), (None, None)])
def test_render_rotated_planar_patch_ascii_raises_on_unsized_patch(
    width: int | None, height: int | None
) -> None:
    msg = re.escape("Cannot get the ASCII representation of unsized patches.")
    with pytest.raises(UnsizedPatchError, match=msg):
        render_rotated_planar_patch_ascii(
            width=width, height=height, points=[], location=None, axes=False
        )
