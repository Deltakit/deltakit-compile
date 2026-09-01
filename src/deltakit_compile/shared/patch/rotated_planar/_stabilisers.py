# This file contains information which is proprietary to Riverlane Limited
# ("Riverlane") and is Riverlane Confidential Information.
# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Utilities for listing all the stabilisers that need to be measured for specific operations."""

from typing import Final

import numpy as np
from xdsl.dialects.builtin import NoneAttr

from deltakit_compile.dialects.logical_assembly import OrientationEnum, RotatedPlanarPatchType
from deltakit_compile.dialects.qcore import PauliStringAttr
from deltakit_compile.shared.patch.rotated_planar._placement import (
    get_data_qubits_indices_placement,
)

_ID: Final = PauliStringAttr.identity(4)
_XX: Final = PauliStringAttr((("X", 0), ("X", 1)), 2)
_ZZ: Final = PauliStringAttr((("Z", 0), ("Z", 1)), 2)
_XXXX: Final = PauliStringAttr((("X", 0), ("X", 1), ("X", 2), ("X", 3)), 4)
_ZZZZ: Final = PauliStringAttr((("Z", 0), ("Z", 1), ("Z", 2), ("Z", 3)), 4)


def _increase_to_parity(inclusive_start: int, parity: bool) -> int:
    """Return ``inclusive_start`` or ``inclusive_start + 1`` depending on whether it is odd or
    even and on ``parity``.

    When building the "1-dimensional string" that will wrap around the bulk to form boundaries,
    it is convenient to be able to get the next index at which a non-trivial stabiliser will
    appear. This function computes that index.

    Args:
        inclusive_start: index from which to start.
        parity: desired parity.

    Returns:
        If ``parity`` is ``True`` (resp. ``False``), returns ``inclusive_start`` if it is even
        (resp. odd), else returns ``inclusive_start + 1``.
    """
    is_even = inclusive_start % 2 == 0
    return inclusive_start if parity == is_even else inclusive_start + 1


def local_stabilisers_for_memory_on_patch(
    patch_type: RotatedPlanarPatchType, parity: bool
) -> list[list[PauliStringAttr]]:
    r"""Computes the stabilisers that should be measured on the provided patch to perform a
    ``meas_stab`` operation.

    This method uses ``numpy`` arrays with values corresponding to :class:`PauliStringAttr` values
    because ``numpy`` indexing is very handy in this context.

    It builds 2 different numpy arrays:
    1. ``stabilisers`` which is a 2-dimensional numpy array containing indices that index into an
       internal data-structure containing the values this function will return.
    2. ``boundary_stabs`` which is a 1-dimensional numpy array used to build the correct
        boundary stabilisers. Think of it as a string (1-dimensional) whose first end (index 0)
        will be glued to the top-left corner of the bulk, and will wrap the bulk in clock-wise
        order. Also note that there are ``width - 1`` possible stabilisers on the top/bottom and
        ``height - 1`` on the left/right sides.

    The ``boundary_stabs`` entries are illustrated on the drawing of a distance-5 patch below.
    Note that this drawing only includes bulk plaquettes, as boundary plaquettes are represented
    by the entries of ``boundary_stabs``. The ``boundary_stabs`` entry are represented by their
    index in the ``boundary_stabs`` array::

             0   1   2   3
           .---.---.---.---.
        15 |   |   |   |   | 4
           .---.---.---.---.
        14 |   |   |   |   | 5
           .---.---.---.---.
        13 |   |   |   |   | 6
           .---.---.---.---.
        12 |   |   |   |   | 7
           .---.---.---.---.
             11  10  9   8

    Note that the right (resp. bottom) boundary have indices increasing in the -Y (resp. -X)
    direction, which is taken into account in the implementation of this method.

    Warning:
        The returned array follows the usual convention for patches: the origin is considered to
        be at the bottom-left corner. So that means that ``retval[0][0]`` is considered to be
        the bottom-left corner of the patch and ``retval[-1][-1]`` the top-right corner.

        This is not how arrays are usually printed on screen (where ``retval[0][0]`` would be
        printed as the first (left-most) value of the first (top-most) line).

    Arguments:
        patch_type: patch to generate stabilisers for. The returned array is of shape
            ``(height + 1, width + 1)``.
        parity: position of the left-most stabiliser of the top boundary.

    Returns:
        A 2-dimensional array of **local** stabilisers that needs to be measured. Returned
        stabilisers are locally defined, so a weight-2 stabiliser will be applied on qubit indices
        ``0`` and ``1``. If you want global indexing, call
        ``global_stabilisers_for_memory_on_patch``. See warning about array indexing.
    """
    assert not isinstance(patch_type.placement, NoneAttr), "Should be guaranteed by caller."
    width, height = patch_type.size_data
    # Note: stabilisers will be built with the origin on the top-left corner (i.e., "top"
    # boundary is the line of index ``0``) and will be reversed at the very end to match the
    # convention that the origin of patches is at the bottom-left corner.
    # So throughout this method, ``stabilisers[0, 0]`` is the top-left-most plaquette.
    stabilisers = np.zeros((height + 1, width + 1), dtype=np.int8)

    # We will be filling the ``stabilisers`` array with integers and replace it with a list of
    # objects at the end.
    z_is_vertical = patch_type.placement.orientation.data == OrientationEnum.VERTICAL_Z
    top = bottom = _ZZ if z_is_vertical else _XX
    left = right = top.flipped()
    top_left_bulk = _XXXX if z_is_vertical == parity else _ZZZZ
    # The entries in this array should match the indices below ("tsi", etc.). 0 is the identity
    # because ``stabilisers`` is full of zeros at the beginning.
    stabiliser_mapping: tuple[PauliStringAttr, ...] = (
        _ID,
        top,
        bottom,
        left,
        right,
        top_left_bulk,
        top_left_bulk.flipped(),
    )
    # First letter is for [t]op/[b]ottom/[l]eft/[r]ight/[b]ulk
    # "si" stands for stabiliser index.
    # "tli" stands for "top left index" (the top-left plaquette of the bulk).
    # "oti" stands for "other index" (the other type of bulk plaquette).
    tsi, bsi, lsi, rsi, btli, boti = 1, 2, 3, 4, 5, 6

    # Setting the boundary stabilisers by specifying their supporting qubits in a "1-dimensional
    # string" wrapping clockwise around the patch.
    boundary_stabs = np.zeros((2 * (width + height - 2),), dtype=np.int8)
    # Build the 1-dimensional string. In order: top, right, bottom, left
    boundary_stabs[_increase_to_parity(0, parity) : width - 1 : 2] = tsi
    boundary_stabs[_increase_to_parity(width - 1, parity) : width + height - 2 : 2] = rsi
    boundary_stabs[_increase_to_parity(width + height - 2, parity) : 2 * width + height - 3 : 2] = (
        bsi
    )
    boundary_stabs[_increase_to_parity(2 * width + height - 3, parity) :: 2] = lsi
    # Wrap the string around the bulk, note that right and bottom are reversed because the
    # string direction is opposite to the axis direction.
    stabilisers[0, 1:-1] = boundary_stabs[: width - 1]
    stabilisers[1:-1, -1] = boundary_stabs[width - 1 : width + height - 2]
    stabilisers[-1, 1:-1] = boundary_stabs[width + height - 2 : 2 * width + height - 3][::-1]
    stabilisers[1:-1, 0] = boundary_stabs[2 * width + height - 3 :][::-1]
    # Setting the bulk stabilisers
    stabilisers[1:-1:2, 1:-1:2] = btli
    stabilisers[2:-1:2, 2:-1:2] = btli
    stabilisers[1:-1:2, 2:-1:2] = boti
    stabilisers[2:-1:2, 1:-1:2] = boti
    # Note: reversing ``stabilisers`` to follow "origin at the bottom-left corner" convention.
    return [[stabiliser_mapping[i] for i in row] for row in stabilisers[::-1]]


def global_stabilisers_for_memory_on_patch(
    patch_type: RotatedPlanarPatchType, parity: bool
) -> list[PauliStringAttr]:
    """Return the stabilisers that need to be measured on the provided ``patch_type`` to perform a
    syndrome extraction round.

    The returned stabilisers directly index qubits from the patch instead of being local to the
    plaquette. In particular, they will all be defined on ``patch_type.num_qubits`` qubits.

    Args:
        patch_type: patch type we want the stabilisers of.
        parity: whether the left-most qubit of the top boundary is involved in a weight-2 stabiliser
            on the top-boundary or not.

    Returns:
        global stabilisers that need to be measured on the provided ``patch_type`` to perform a
        syndrome extraction round.
    """
    local_stabilisers = local_stabilisers_for_memory_on_patch(patch_type, parity)
    data_qubit_indices = get_data_qubits_indices_placement(patch_type)
    num_qubits = patch_type.num_qubits
    width, height = patch_type.size_data
    global_stabilisers = list[PauliStringAttr]()
    for y, line in enumerate(local_stabilisers):
        for x, stabiliser in enumerate(line):
            mapping: dict[int, int]
            if stabiliser.is_identity():
                continue
            if (x, y) in [(0, 0), (width, 0), (0, height), (width, height)]:
                msg = "Non-identity stabilisers on the corner are not handled yet."
                raise NotImplementedError(msg)
            if x == 0:  # Left boundary
                mapping = {0: data_qubit_indices[y - 1][0], 1: data_qubit_indices[y][0]}
            elif x == width:  # Right boundary
                mapping = {0: data_qubit_indices[y - 1][-1], 1: data_qubit_indices[y][-1]}
            elif y == 0:  # Bottom boundary
                mapping = {0: data_qubit_indices[0][x - 1], 1: data_qubit_indices[0][x]}
            elif y == height:  # Top boundary
                mapping = {0: data_qubit_indices[-1][x - 1], 1: data_qubit_indices[-1][x]}
            else:  # General case
                mapping = {
                    0: data_qubit_indices[y - 1][x - 1],
                    1: data_qubit_indices[y][x - 1],
                    2: data_qubit_indices[y - 1][x],
                    3: data_qubit_indices[y][x],
                }
            global_stabilisers.append(stabiliser.map_indices(mapping, num_qubits))

    return global_stabilisers
