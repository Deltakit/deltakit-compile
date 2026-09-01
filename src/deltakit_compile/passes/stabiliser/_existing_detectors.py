# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Common functionality for tracking the existing detectors in a circuit and determining whether
sets of measurements are linearly independent of them, when interpreted as vectors mod 2."""

from collections import defaultdict
from collections.abc import Iterable

import numpy as np
from xdsl.ir import BlockArgument, OpResult, SSAValue

from deltakit_compile.dialects import qec, qstruct
from deltakit_compile.dialects import stabiliser as stab


class ExistingDetectors:
    """A representation of the existing detectors in a CircuitOp.

    This class keeps track of a set of detectors, represented as vectors over GF(2) (i.e., mod 2) in
    which each position corresponds to a measurement SSA value, and the value at that position is 1
    if the measurement is present in the detector. We can then use linear algebra to determine
    whether a new detector is a linear combination of existing detectors and is therefore redundant.

    An incremental row echelon form (RREF) is maintained using plain numpy boolean arrays so that
    ``in_span`` checks are O(basis_size * num_cols) instead of requiring a full matrix row reduction
    on every call.

    Since different measurement SSA values may represent the same measurement, we attempt to
    canonicalise measurement SSAs by tracing through stab.CircuitOps and qstruct.ParallelOps.
    We don't attempt to trace through control flow since one SSA value after control flow might
    represent multiple possible measurements. Thus it's not completely guaranteed that all
    semantically redundant detectors will be caught.

    We also do not handle arith.xori ops and treat their results as distinct measurements.

    Args:
        op: If not None, the tracked detectors will be initialised with the detectors in this
            circuit op.
    """

    def __init__(self, op: stab.CircuitOp | None = None) -> None:
        # Cache for the canonical measurement SSA for each measurement
        self._canonical_measurements: dict[SSAValue, SSAValue] = {}

        # The column index in the detector matrix corresponding to each measurement SSA value
        self._meas_to_column: dict[SSAValue, int] = {}
        self._num_cols = 0

        # Incremental row echelon form: list of (pivot_column, boolean_row) pairs.
        # Each row is a numpy bool array of length _num_cols.
        self._basis: list[tuple[int, np.ndarray]] = []

        detectors: list[tuple[SSAValue, ...]] = []
        if op is not None:
            for child_op in op.walk():
                if isinstance(child_op, qec.DetectorOp):
                    detector = tuple(self._dereference_measurements(child_op.measurements))
                    self._add_measurements(detector)
                    detectors.append(detector)

        # Build the incremental basis from existing detectors
        for detector in detectors:
            vector = self._make_bool_vector(detector)
            self._add_to_basis(vector)

    def _dereference_measurement(self, meas: SSAValue) -> SSAValue:
        """Find the canonical SSA value for the measurement represented by the given SSA value by
        tracing through input and output args of CircuitOps and ParallelOps."""
        if meas in self._canonical_measurements:
            return self._canonical_measurements[meas]

        if isinstance(meas, BlockArgument) and isinstance(
            circuit := meas.owner.parent_op(), stab.CircuitOp
        ):
            # Dereference block args of circuits to input args
            canonical = self._dereference_measurement(circuit.block_arg_to_input_arg(meas))
        elif isinstance(meas, OpResult) and isinstance(circuit := meas.owner, stab.CircuitOp):
            # Dereference output args of circuits to yield args
            canonical = self._dereference_measurement(circuit.output_arg_to_yield_arg(meas))
        elif isinstance(meas, OpResult) and isinstance(parallel := meas.owner, qstruct.ParallelOp):
            # Dereference results of parallel ops to yield args
            canonical = self._dereference_measurement(parallel.result_to_yield_arg(meas))
        else:
            # Treat any other source of a measurement as canonical (measure, control flow, etc.)
            canonical = meas

        self._canonical_measurements[meas] = canonical
        return canonical

    def _dereference_measurements(self, measurements: Iterable[SSAValue]) -> Iterable[SSAValue]:
        """Find canonical SSA values for a collection of measurement SSA values."""
        for meas in measurements:
            yield self._dereference_measurement(meas)

    def _add_measurements(self, measurements: Iterable[SSAValue]) -> None:
        """Add any new measurements to the measurement-to-column mapping, assuming all are
        dereferenced."""
        for meas in measurements:
            if meas not in self._meas_to_column:
                self._meas_to_column[meas] = self._num_cols
                self._num_cols += 1

    def _make_bool_vector(self, measurements: Iterable[SSAValue]) -> np.ndarray:
        """Make a boolean vector from the given measurement SSA values, assuming all are known and
        dereferenced.

        Uses numpy bool arrays for fast GF(2) arithmetic via XOR.
        """
        vector = np.zeros(self._num_cols, dtype=np.bool_)
        for meas in measurements:
            idx = self._meas_to_column[meas]
            vector[idx] = ~vector[idx]  # XOR (addition mod 2)
        return vector

    def _try_reduce(self, row: np.ndarray) -> np.ndarray:
        """Reduce a row in-place against the current RREF basis using GF(2) arithmetic.

        Args:
            row: A boolean vector to reduce. Modified in place.

        Returns:
            The same array after reduction.
        """
        for pivot_col, basis_row in self._basis:
            if row[pivot_col]:
                row ^= basis_row
        return row

    def _add_to_basis(self, vector: np.ndarray) -> None:
        """Add a vector to the incremental RREF basis if it is linearly independent."""
        reduced = self._try_reduce(vector)
        if np.any(reduced):
            # since the vector is just 0 and 1, argmax returns the index of the leftmost 1
            pivot = int(np.argmax(reduced))
            self._basis.append((pivot, reduced))

    def in_span(self, measurements: Iterable[SSAValue]) -> bool:
        """Check whether the given measurement vector is in the span of the existing detectors, i.e.
        whether the given set of measurements can be expressed as a linear combination of the
        existing detectors (mod 2)."""
        known_measurements: list[SSAValue] = []
        new_measurements: list[SSAValue] = []

        for measurement in self._dereference_measurements(measurements):
            if measurement in self._meas_to_column:
                known_measurements.append(measurement)
            else:
                new_measurements.append(measurement)

        # Any new measurement values must cancel (appear an even number of times)
        if new_measurements:
            new_counts: dict[SSAValue, int] = defaultdict(int)
            for meas in new_measurements:
                new_counts[meas] += 1
            if any(count % 2 == 1 for count in new_counts.values()):
                # Some new measurement values left over: not in the span.
                return False

        # All the unknown measurements cancelled out, so we can just check the known ones.
        vector = self._make_bool_vector(known_measurements)
        reduced = self._try_reduce(vector)
        return not np.any(reduced)

    def difference_in_span(
        self, measurements1: Iterable[SSAValue], measurements2: Iterable[SSAValue]
    ) -> bool:
        """Check whether the XOR (i.e. symmetric difference) of the given measurement vectors is in
        the span of the existing detectors.

        This differs from just taking the symmetric difference before calling `in_span` because we
        dereference all measurements to their canonical SSA values before checking, so measurements
        in both iterables representing the same measurement will cancel out.
        """
        return self.in_span([*measurements1, *measurements2])

    def add_detector(self, measurements: Iterable[SSAValue]) -> None:
        """Add a new detector with the given measurements to the existing detectors."""
        previous_num_cols = self._num_cols
        measurements = list(self._dereference_measurements(measurements))
        self._add_measurements(measurements)

        # Extend existing basis rows with zeros for new columns
        num_new_measurements = self._num_cols - previous_num_cols
        if num_new_measurements > 0:
            for i, (pivot_col, row) in enumerate(self._basis):
                extended = np.zeros(self._num_cols, dtype=np.bool_)
                extended[:previous_num_cols] = row
                self._basis[i] = (pivot_col, extended)

        # Add the new detector to the incremental basis
        vector = self._make_bool_vector(measurements)
        self._add_to_basis(vector)


def add_detectors_if_independent(
    circuit: stab.CircuitOp, detectors: list[qec.DetectorOp]
) -> list[qec.DetectorOp]:
    """Add detectors to the end of the circuit if they are not in the span of the circuit's existing
    detectors, and therefore redundant.

    Args:
        circuit: The circuit to add detectors to.
        detectors: The detectors to add if they are not redundant.

    Returns:
        A list of the redundant detectors that were not added.
    """
    if not detectors:
        return []

    existing_detectors = ExistingDetectors(circuit)
    redundant_detectors = list[qec.DetectorOp]()
    for detector in detectors:
        if existing_detectors.in_span(detector.measurements):
            redundant_detectors.append(detector)
        else:
            # Not in span - add detector
            # TODO: Infer detector round
            circuit.body.block.insert_op_before(detector, circuit.yield_op)
            existing_detectors.add_detector(detector.measurements)

    return redundant_detectors
