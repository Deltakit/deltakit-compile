# (c) Copyright Riverlane 2025-2026. All rights reserved.
r"""ASCII rendering utilities for rotated planar surface code patches.

Overall strategy:
    1. Convert qubit coordinates to a doubled integer lattice so integer and half-integer
       coordinates can be rendered on a single character grid.
    2. Classify points as data, inner ancilla, or outer ancilla from declaration order.
    3. Render the patch body by placing qubit indices and then drawing connectors with simple
       local rules (data-data for horizontal/vertical links, data-outer for boundary diagonals).
    4. Optionally frame the body with integer-only axes using the patch location as offset.

This module separates low-level drawing helpers from the high-level orchestrator
``render_rotated_planar_patch_ascii`` so callers can render with a single function call.


As an example, the following code

.. code-block:: python

    from deltakit_compile.frontend.logasm import RotatedPlanarPatch

    patch = RotatedPlanarPatch(3, 5, location=(2, -3))
    print(patch.to_ascii())

outputs::

     2 |         23
       |      4-------9------14
     1 |      |  18   |  22   |  24
       |      3-------8------13
     0 | 28   |  17   |  21   |
       |      2-------7------12
    -1 |      |  16   |  20   |  25
       |      1-------6------11
    -2 | 27   |  15   |  19   |
       |      0-------5------10
    -3 |                 26
       +---------------------------
          2       3       4       5

and

.. code-block:: python

    from deltakit_compile.frontend.logasm import RotatedPlanarPatch

    patch = RotatedPlanarPatch(3, 5, location=(2, -3))
    print(patch.to_ascii(axes=False))

outputs::

            23
           /   \
         4-------9------14
         |       |       | \
         |  18   |  22   |  24
         |       |       | /
         3-------8------13
       / |       |       |
    28   |  17   |  21   |
       \ |       |       |
         2-------7------12
         |       |       | \
         |  16   |  20   |  25
         |       |       | /
         1-------6------11
       / |       |       |
    27   |  15   |  19   |
       \ |       |       |
         0-------5------10
                   \   /
                    26

"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from deltakit_compile.frontend.common._vector import Vector
from deltakit_compile.shared.patch.exceptions import UnsizedPatchError

_PointKind = Literal["data", "inner", "outer"]


def _row_of(y: int, max_y: int, vertical_step: int) -> int:
    """Map a doubled-y coordinate to a canvas row index.

    Args:
        y: doubled y-coordinate in patch space.
        max_y: maximum doubled y-coordinate present in patch space.
        vertical_step: number of canvas rows per doubled y-unit.

    Returns:
        Canvas row index, with larger y mapped toward the top.
    """
    return (max_y - y) * vertical_step


def _col_of(x: int, min_x: int, horizontal_step: int, index_width: int) -> int:
    """Map a doubled-x coordinate to the label-centred canvas column.

    Args:
        x: doubled x-coordinate in patch space.
        min_x: minimum doubled x-coordinate present in patch space.
        horizontal_step: number of canvas columns per doubled x-unit.
        index_width: width allocated to printed qubit indices.

    Returns:
        Canvas column index near the center of the qubit label slot.
    """
    return (x - min_x) * horizontal_step + index_width // 2


def _put_if_empty(canvas: list[list[str]], row: int, col: int, char: str) -> None:
    """Write one character into the canvas only if the target cell is blank.

    Args:
        canvas: mutable 2D character buffer.
        row: target row index.
        col: target column index.
        char: character to write.
    """
    row_count = len(canvas)
    col_count = len(canvas[0]) if row_count > 0 else 0
    if 0 <= row < row_count and 0 <= col < col_count and canvas[row][col] == " ":
        canvas[row][col] = char


def _integer_tick_label(value: float) -> str | None:
    """Format an axis tick only when its value is (approximately) an integer.

    Args:
        value: coordinate value to test and format.

    Returns:
        String label for integer values, else ``None``.
    """
    rounded = round(value)
    return str(int(rounded)) if abs(value - rounded) < 1e-9 else None


def point_kind_map(
    doubled_points: list[tuple[int, int]],
    num_data: int,
    num_inner_ancilla: int,
) -> dict[tuple[int, int], _PointKind]:
    """Classify each doubled-grid point by qubit kind.

    Args:
        doubled_points: qubit coordinates on the doubled lattice in declaration order.
        num_data: number of leading points corresponding to data qubits.
        num_inner_ancilla: number of points after data corresponding to inner ancillas.

    Returns:
        Mapping from doubled-grid coordinate to ``"data"``, ``"inner"``, or ``"outer"``.
    """
    point_to_kind: dict[tuple[int, int], _PointKind] = {}
    for idx, point in enumerate(doubled_points):
        if idx < num_data:
            point_to_kind[point] = "data"
        elif idx < num_data + num_inner_ancilla:
            point_to_kind[point] = "inner"
        else:
            point_to_kind[point] = "outer"
    return point_to_kind


def render_patch(
    point_to_index: dict[tuple[int, int], int],
    point_to_kind: dict[tuple[int, int], _PointKind],
) -> tuple[list[str], int, int, int, int, int, int, int]:
    """Render the patch body (labels and links) onto a plain-text canvas.

    Args:
        point_to_index: mapping from doubled-grid coordinates to displayed qubit indices.
        point_to_kind: mapping from doubled-grid coordinates to qubit kind.

    Returns:
        Tuple of rendered rows and layout metadata:
        ``(rows, min_x, max_x, min_y, max_y, horizontal_step, vertical_step, index_width)``.
    """
    xs = [x for x, _ in point_to_index]
    ys = [y for _, y in point_to_index]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    index_width = len(str(max(point_to_index.values())))
    horizontal_step = max(4, index_width + 2)
    if horizontal_step % 2:
        horizontal_step += 1
    vertical_step = 2

    rows = (max_y - min_y) * vertical_step + 1
    cols = (max_x - min_x) * horizontal_step + index_width
    canvas = [[" " for _ in range(cols)] for _ in range(rows)]

    points = set(point_to_index)
    for x, y in points:
        row = _row_of(y, max_y, vertical_step)
        col = _col_of(x, min_x, horizontal_step, index_width)
        point_kind = point_to_kind[(x, y)]

        right = (x + 2, y)
        if right in points and point_kind == "data" and point_to_kind[right] == "data":
            right_col = _col_of(x + 2, min_x, horizontal_step, index_width)
            for c in range(col + 1, right_col):
                _put_if_empty(canvas, row, c, "-")

        up = (x, y + 2)
        if up in points and point_kind == "data" and point_to_kind[up] == "data":
            up_row = _row_of(y + 2, max_y, vertical_step)
            for r in range(up_row + 1, row):
                _put_if_empty(canvas, r, col, "|")

        up_right = (x + 1, y + 1)
        if up_right in points and {point_kind, point_to_kind[up_right]} == {"data", "outer"}:
            _put_if_empty(canvas, row - 1, col + horizontal_step // 2, "/")

        down_right = (x + 1, y - 1)
        if down_right in points and {point_kind, point_to_kind[down_right]} == {"data", "outer"}:
            _put_if_empty(canvas, row + 1, col + horizontal_step // 2, "\\")

    for (x, y), index in point_to_index.items():
        label = str(index)
        row = _row_of(y, max_y, vertical_step)
        center = _col_of(x, min_x, horizontal_step, index_width)
        start = max(0, center - len(label) // 2)
        end = min(cols, start + len(label))
        canvas[row][start:end] = list(label[: end - start])

    patch_rows = ["".join(row).rstrip() for row in canvas]
    return patch_rows, min_x, max_x, min_y, max_y, horizontal_step, vertical_step, index_width


def add_axes(
    patch_rows: list[str],
    *,
    min_x: int,
    max_x: int,
    min_y: int,
    max_y: int,
    horizontal_step: int,
    vertical_step: int,
    index_width: int,
    offset_x: float,
    offset_y: float,
) -> list[str]:
    """Add integer-labeled y (left) and x (bottom) axes to rendered patch rows.

    Args:
        patch_rows: rendered patch body rows.
        min_x: minimum doubled x-coordinate in patch space.
        max_x: maximum doubled x-coordinate in patch space.
        min_y: minimum doubled y-coordinate in patch space.
        max_y: maximum doubled y-coordinate in patch space.
        horizontal_step: number of canvas columns per doubled x-unit.
        vertical_step: number of canvas rows per doubled y-unit.
        index_width: width allocated to printed qubit indices.
        offset_x: real-space x offset of the patch origin.
        offset_y: real-space y offset of the patch origin.

    Returns:
        Framed rows with axes appended.
    """
    y_labels: dict[int, str] = {}
    for y in range(min_y, max_y + 1):
        label = _integer_tick_label(y / 2 + offset_y)
        if label is not None:
            y_labels[y] = label

    y_label_width = max((len(label) for label in y_labels.values()), default=1)
    framed_rows: list[str] = []
    for y in range(max_y, min_y - 1, -1):
        y_label = y_labels.get(y, "")
        patch_row = patch_rows[_row_of(y, max_y, vertical_step)]
        framed_rows.append(f"{y_label.rjust(y_label_width)} | {patch_row}")

    patch_width = max((len(row) for row in patch_rows), default=0)
    axis_prefix = " " * y_label_width
    framed_rows.append(f"{axis_prefix} +" + "-" * (patch_width + 1))

    x_axis_chars = [" " for _ in range(patch_width)]
    for x in range(min_x, max_x + 1):
        x_label = _integer_tick_label(x / 2 + offset_x)
        if x_label is None:
            continue
        center = _col_of(x, min_x, horizontal_step, index_width)
        start = max(0, min(patch_width - len(x_label), center - len(x_label) // 2))
        for i, char in enumerate(x_label):
            x_axis_chars[start + i] = char
    framed_rows.append(f"{axis_prefix}   " + "".join(x_axis_chars).rstrip())
    return framed_rows


def render_rotated_planar_patch_ascii(
    *,
    width: int | None,
    height: int | None,
    points: Sequence[Vector[float]],
    location: tuple[float, float] | None,
    axes: bool,
) -> str:
    """Render a rotated planar patch to ASCII in one high-level call.

    Args:
        width: patch width in data-qubit units, or ``None`` for unsized patches.
        height: patch height in data-qubit units, or ``None`` for unsized patches.
        points: qubit coordinates.
        location: real-space patch origin for axis labelling, or ``None`` if unknown.
        axes: whether axes should be included when ``location`` is available.

    Returns:
        Multiline ASCII rendering of the patch.

    Raises:
        NotImplementedError: if the patch is unsized.
    """
    if width is None or height is None:
        msg = "Cannot get the ASCII representation of unsized patches."
        raise UnsizedPatchError(msg)

    doubled_points = [(round(2 * pt[0]), round(2 * pt[1])) for pt in points]
    point_to_index = {point: idx for idx, point in enumerate(doubled_points)}

    num_data = width * height
    num_inner_ancilla = max(width - 1, 0) * max(height - 1, 0)
    point_to_kind = point_kind_map(doubled_points, num_data, num_inner_ancilla)
    (
        patch_rows,
        min_x,
        max_x,
        min_y,
        max_y,
        horizontal_step,
        vertical_step,
        index_width,
    ) = render_patch(point_to_index, point_to_kind)

    if not axes or location is None:
        return "\n".join(patch_rows)

    location_x, location_y = location
    framed_rows = add_axes(
        patch_rows,
        min_x=min_x,
        max_x=max_x,
        min_y=min_y,
        max_y=max_y,
        horizontal_step=horizontal_step,
        vertical_step=vertical_step,
        index_width=index_width,
        offset_x=location_x,
        offset_y=location_y,
    )
    return "\n".join(framed_rows)
