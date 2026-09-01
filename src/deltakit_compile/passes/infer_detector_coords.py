# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Pass to fill in missing detector spatial coordinates based on coordinates of measured qubits."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import SSAValue
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)

from deltakit_compile.dialects import qec
from deltakit_compile.passes._qubit_measurement_tracker import QubitMeasurementCoordinateTracker


def _average_coords(coords: Iterable[tuple[float, ...] | None]) -> tuple[float, ...] | None:
    """Return the average of coordinate tuples of the same length."""
    present_coords = [coord for coord in coords if coord is not None]
    if not present_coords:
        return None

    dimension = len(present_coords[0])
    if not all(len(coord) == dimension for coord in present_coords):
        msg = "All qubit coordinates must have the same dimension."
        raise ValueError(msg)

    return tuple(
        sum(coord[i] for coord in present_coords) / len(present_coords) for i in range(dimension)
    )


def _infer_detector_coords(
    measurements: Iterable[SSAValue], tracker: QubitMeasurementCoordinateTracker
) -> tuple[float, ...] | None:
    """Infer coordinates for a detector given its measurements."""
    measurement_possible_coords = [
        tracker.get_possible_measurement_coords(meas_ssa) for meas_ssa in measurements
    ]
    measurement_average_coords = [
        _average_coords(coord.data for coord in possible_coords)
        for possible_coords in measurement_possible_coords
    ]
    return _average_coords(measurement_average_coords)


class _InferDetectorCoordsPass(RewritePattern):
    """Insert detector coordinates based on the coords given by the tracker."""

    def __init__(self, qubit_tracker: QubitMeasurementCoordinateTracker):
        super().__init__()
        self._qubit_tracker = qubit_tracker

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qec.DetectorOp, rewriter: PatternRewriter) -> None:
        if op.coords is not None:
            return

        inferred_coords = _infer_detector_coords(op.measurements, self._qubit_tracker)
        if inferred_coords is None:
            return

        new_detector = qec.DetectorOp(measurements=op.measurements, coordinates=inferred_coords)
        rewriter.replace_op(op, new_detector)


@dataclass(frozen=True)
class InferDetectorCoords(ModulePass):
    """Pass to fill in missing detector spatial coords based on coords of measured qubits."""

    name = "infer-detector-coords"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        tracker = QubitMeasurementCoordinateTracker.walk_module(op)
        PatternRewriteWalker(
            _InferDetectorCoordsPass(tracker),
            apply_recursively=False,
        ).rewrite_module(op)
