# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""This module implements utilities for qubit placement.

The main function implemented by this module is :func:`patch_type_to_coordinates` that translates
any rotated surface code patch into coordinates of qubits that are used to implement that patch.

For the moment, this function is used as the source of truth and common convention for qubit order
and placement for a patch. Eventually, we want that function and the order it implements to become
an implementation detail. This can be done by annotating qubit coordinates on patch and qubit types
for example.
"""

from deltakit_compile.dialects.logical_assembly import RotatedPlanarPatchType
from deltakit_compile.shared.patch.exceptions import UnplacedPatchError


def _patch_properties_to_data_qubit_coordinates(
    width: int, height: int, offx: float, offy: float
) -> list[tuple[float, float]]:
    r"""Return the coordinates of data-qubits.

    The coordinates returned correspond to the qubits marked with ``x`` below::

            .
           / \
          x---x---x\
          | . | . | .
         /x---x---x/
        . | . | . |
         \x---x---x
               \ /
                .

    Args:
        width: width of the patch.
        height: height of the patch.
        offx: offset in the X-axis of the patch w.r.t the origin ``(0, 0)``.
        offy: offset in the Y-axis of the patch w.r.t the origin ``(0, 0)``.

    Returns:
        a list of 2-dimensional coordinates representing the qubit coordinates. The order in which
        coordinates are returned is guaranteed to be constant.
    """
    return [(x + 0.5 + offx, y + 0.5 + offy) for x in range(width) for y in range(height)]


def _patch_properties_to_inner_ancilla_qubit_coordinates(
    width: int, height: int, offx: float, offy: float
) -> list[tuple[float, float]]:
    r"""Return the coordinates of ancilla-qubits located in the bulk.

    The coordinates returned correspond to the qubits marked with ``x`` below::

            .
           / \
          .---.---.\
          | x | x | .
         /.---.---./
        . | x | x |
         \.---.---.
               \ /
                .

    Args:
        width: width of the patch.
        height: height of the patch.
        offx: offset in the X-axis of the patch w.r.t the origin ``(0, 0)``.
        offy: offset in the Y-axis of the patch w.r.t the origin ``(0, 0)``.

    Returns:
        a list of 2-dimensional coordinates representing the qubit coordinates. The order in which
        coordinates are returned is guaranteed to be constant.
    """
    # Special case there is no weight-2 stabiliser on the top boundary.
    if width == 1:
        return []
    return [(x + offx, y + offy) for x in range(1, width) for y in range(1, height)]


def _patch_properties_to_outer_ancilla_qubit_coordinates(
    width: int, height: int, offx: float, offy: float, parity: bool = True
) -> list[tuple[float, float]]:
    r"""Return the coordinates of ancilla-qubits located on the boundaries.

    The coordinates returned correspond to the qubits marked with ``x`` below::

            x
           / \
          .---.---.\
          | . | . | x
         /.---.---./
        x | . | . |
         \.---.---.
               \ /
                x

    Args:
        width: width of the patch.
        height: height of the patch.
        offx: offset in the X-axis of the patch w.r.t the origin ``(0, 0)``.
        offy: offset in the Y-axis of the patch w.r.t the origin ``(0, 0)``.
        parity: if ``True``, the left-most weight-2 stabiliser on the top boundary is populated.
            Else, it is not populated (and so its direct right neighbour is). This is a temporary
            parameter until that information is encoded on the patch type. When the width (``X``
            dimension) of the patch is exactly ``1``, ``True`` means that the top weight-2
            stabiliser on the right boundary is included in the patch. Patches with a height of
            ``1`` follow the general rule.

    Returns:
        a list of 2-dimensional coordinates representing the qubit coordinates. The order in which
        coordinates are returned is guaranteed to be constant.
    """
    # Special case there is no weight-2 stabiliser on the top boundary.
    if width == 1:
        return (
            [(offx, y + offy) for y in range(height - (2 if parity else 1), 0, -2)]  # LEFT
            + [(1 + offx, y + offy) for y in range(height - (1 if parity else 2), 0, -2)]  # RIGHT
        )
    # Generate a list of size 2 * (width + height - 2), alternating between True and False,
    # starting with parity and representing whether the corresponding ancilla is used or
    # not. It is ``width + height - 2`` because there are ``width - 1`` (resp. ``height - 1``)
    # valid ancilla positions on horizontal (resp. vertical) sides.
    is_outer_ancilla_used = [(i % 2 == 0) == parity for i in range(2 * (width + height - 2))]
    # Build a list of all the possible ancilla, in clock-wise order, starting from the left of
    # the top boundary.
    all_outer_ancilla_qubits = [
        *((x + 1 + offx, height + offy) for x in range(width - 1)),  # TOP
        *((width + offx, y + 1 + offy) for y in reversed(range(height - 1))),  # RIGHT
        *((x + 1 + offx, offy) for x in reversed(range(width - 1))),  # BOTTOM
        *((offx, y + 1 + offy) for y in range(height - 1)),  # LEFT
    ]
    return [
        q for q, used in zip(all_outer_ancilla_qubits, is_outer_ancilla_used, strict=True) if used
    ]


def patch_properties_to_coordinates(
    width: int, height: int, offx: float, offy: float, parity: bool = True
) -> list[tuple[float, float]]:
    r"""Return the coordinates of qubits composing the provided ``patch_type``.

    Illustration of the effect of the ``parity`` parameter when it is ``True``::

              .
             / \
            .---.---.\
            |   |   | .
           /.---.---./
          . |   |   |
           \.---.---.
                 \ /
                  .

    and when it is ``False``::

                  .
                 / \
           /.---.---.
          . |   |   |
           \.---.---.\
            |   |   | .
            .---.---./
             \ /
              .


    Illustration of the effect of the ``parity`` on patches that have a width of ``1`` when
    it is ``True``::

          .\
          | .
         /./
        . |
         \.

    and when it is ``False``::

         /.
        . |
         \.\
          | .
          ./

    Args:
        width: width of the patch.
        height: height of the patch.
        offx: offset in the X-axis of the patch w.r.t the origin ``(0, 0)``.
        offy: offset in the Y-axis of the patch w.r.t the origin ``(0, 0)``.
        parity: if ``True``, the left-most weight-2 stabiliser on the top boundary is populated.
            Else, it is not populated (and so its direct right neighbour is). This is a temporary
            parameter until that information is encoded on the patch type. When the width (``X``
            dimension) of the patch is exactly ``1``, ``True`` means that the top weight-2
            stabiliser on the right boundary is included in the patch. Patches with a height of
            ``1`` follow the general rule.

    Returns:
        a list of 2-dimensional coordinates representing the qubit coordinates. The order in which
        coordinates are returned is guaranteed to be constant.
    """
    return (
        _patch_properties_to_data_qubit_coordinates(width, height, offx, offy)
        + _patch_properties_to_inner_ancilla_qubit_coordinates(width, height, offx, offy)
        + _patch_properties_to_outer_ancilla_qubit_coordinates(width, height, offx, offy, parity)
    )


def patch_type_to_coordinates(
    patch_type: RotatedPlanarPatchType, parity: bool = True
) -> list[tuple[float, float]]:
    r"""Return the coordinates of qubits composing the provided ``patch_type``.

    Illustration of the effect of the ``boundary_parity`` parameter when it is ``True``::

              .
             / \
            .---.---.\
            |   |   | .
           /.---.---./
          . |   |   |
           \.---.---.
                 \ /
                  .

    and when it is ``False``::

                  .
                 / \
           /.---.---.
          . |   |   |
           \.---.---.\
            |   |   | .
            .---.---./
             \ /
              .


    Illustration of the effect of the ``boundary_parity`` on patches that have a width of ``1`` when
    it is ``True``::

          .\
          | .
         /./
        . |
         \.

    and when it is ``False``::

         /.
        . |
         \.\
          | .
          ./


    Arguments:
        patch_type: type of the patch to translate to qubit coordinates.
        parity: if ``True``, the left-most weight-2 stabiliser on the top boundary is populated.
            Else, it is not populated (and so its direct right neighbour is). This is a temporary
            parameter until that information is encoded on the patch type. When the width (``X``
            dimension) of the patch is exactly ``1``, ``True`` means that the top weight-2
            stabiliser on the right boundary is included in the patch. Patches with a height of
            ``1`` follow the general rule.

    Returns:
        A list of coordinates on which physical qubits should be located for the provided
        ``patch_type``. The coordinates are offset by the patch location.

    Raises:
        RuntimeError: if the provided ``patch_type`` does not have placement data (i.e., if its
            placement attribute is ``None``)
    """
    if patch_type.placement_data is None:
        msg = (
            f"Cannot get qubit coordinates from a patch type ({patch_type}) that does not have "
            "a location attribute."
        )
        raise UnplacedPatchError(msg)
    return patch_properties_to_coordinates(
        *patch_type.size_data, *patch_type.placement_data, parity
    )


def get_data_qubits_indices(patch_type: RotatedPlanarPatchType) -> tuple[int, ...]:
    """Return the indices of the data-qubits of the given patch.

    This function can be used to find the coordinates corresponding to data qubits in the provided
    patch. Note that it does not depend on the boundary parity of the patch as the parity only
    impacts the **position** (and not the number) of syndrome qubits.

    Args:
        patch_type: patch to get the data-qubit indices for.

    Returns:
        a tuple containing the indices of each data-qubit in the provided ``patch_type``. The
        coordinates of each data-qubit in the patch can be obtained by also using
        ``patch_type_to_coordinates``::

            patch_type: RotatedPlanarPatchType = ...
            parity: bool = ...
            all_coordinates = patch_type_to_coordinates(patch_type, parity)
            data_qubit_coordinates = [
                all_coordinates[i] for i in get_data_qubits_indices(patch_type)
            ]
    """
    width, height = patch_type.size_data
    return tuple(range(width * height))


def get_data_qubits_indices_placement(patch_type: RotatedPlanarPatchType) -> list[list[int]]:
    """Return the indices of the data-qubits of the given patch on a grid.

    This function can be used to find the index corresponding to specific data qubits in the
    provided patch. Note that it does not depend on the boundary parity of the patch as the parity
    only impacts the **position** (and not the number) of syndrome qubits.

    Args:
        patch_type: patch to get the data-qubit indices for.

    Returns:
        a grid (list of list) containing indices of data qubits such as::

            [
                [0, 3, 6],
                [1, 4, 7],
                [2, 5, 8],
            ]

        Note that ``ret[0][0]`` is considered to be the bottom-left data-qubit of the patch and
        ``ret[-1][-1]`` the top-right data-qubit, which is not what appears when printing the nested
        list. Also, the return value is indexed as ``ret[y][x]``.
    """
    width, height = patch_type.size_data
    return [[x * height + y for x in range(width)] for y in range(height)]
