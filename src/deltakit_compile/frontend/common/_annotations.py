# (c) Copyright Riverlane 2025-2026. All rights reserved.
from __future__ import annotations

import itertools
from collections.abc import Collection, Sequence

from typing_extensions import override
from xdsl.ir import Attribute

from deltakit_compile.dialects.qec import (
    DetectorRefType,
    GetCorrectedOp,
    GetCorrectionOp,
    GetUncorrectedOp,
    IsCorrectionReadyOp,
    ObservableIncludeOp,
    ObservableType,
)
from deltakit_compile.dialects.sobs import MoveObservableOp
from deltakit_compile.frontend.common._builder import (
    BaseAPIObject,
    all_objects_managed_by_same_builder,
    find_duplicated_identifiers,
)
from deltakit_compile.frontend.common._classical_expr import (
    ClassicalExpression,
    CorrectedObservableExpression,
    ObservableCorrectionExpression,
    ObservableCorrectionIsReadyExpression,
    UncorrectedObservableExpression,
)
from deltakit_compile.frontend.common._exceptions import (
    DifferentBuildersError,
    DuplicatedIdentifiersError,
    NoMeasurementProvidedError,
    ObservableError,
)
from deltakit_compile.frontend.common._measurements import MeasurementBit, MeasurementReg
from deltakit_compile.frontend.common._qubit_reg import Qubit
from deltakit_compile.frontend.common._vector import Vector


class Detector(BaseAPIObject):
    """Represents a detector as a collection of measurement results.

    Args:
        measurements: a non-empty collection of 1-qubit raw measurements.
        coordinates: an optional sequence of coordinates.

    Raises:
        NoMeasurementProvidedError: if no measurement is provided.
        DifferentBuildersError: if the provided ``measurements`` are attached to different builders.
        DuplicatedIdentifiersError: if any measurement is provided twice or more.
    """

    def __init__(
        self, measurements: Collection[MeasurementBit], coordinates: Vector[float] | None = None
    ) -> None:
        # Check that at least one measurement is provided.
        if not measurements:
            raise NoMeasurementProvidedError(Detector)
        # Check that the measurements are all attached to the same builder.
        if not all_objects_managed_by_same_builder(measurements):
            raise DifferentBuildersError()
        # Check that there are no duplicates:
        if duplicates := find_duplicated_identifiers(measurements):
            raise DuplicatedIdentifiersError(duplicates)
        super().__init__()
        self._measurements = tuple(measurements)
        self._coordinates = coordinates

    @property
    @override
    def _identifier_prefix(self) -> str:
        return "det"

    @property
    @override
    def _type_info(self) -> Attribute:
        return DetectorRefType()

    @property
    def measurements(self) -> tuple[MeasurementBit, ...]:
        return self._measurements

    @property
    def coordinates(self) -> Vector[float] | None:
        return self._coordinates


class Observable(BaseAPIObject):
    """Represent an observable that can be queried for (un)corrected result and correction.

    This class can be used in two main ways:

    1. By providing a ``support``, you can then move the observable to another set of qubits by
        using the ``Observable.move`` method.
    2. It is also possible to not provide any ``support`` and to update an observable like in
        ``stim``, by including measurements into the observable with ``Observable.include``.

    Both ways are incompatible, so the method ``Observable.include`` will raise if the instance
    has a been declared on a non-empty ``support``, and calling ``Observable.move`` will fail
    if the instance has been declared on an empty ``support``.

    Args:
        support: if provided, the qubits on which the observable is supported at the time of
            creation.
    """

    def __init__(self, support: Sequence[Qubit] | None = None) -> None:
        super().__init__()
        if support is None:
            support = ()

        self._measurements: list[MeasurementBit] = []
        self._support: tuple[Qubit, ...]
        self._set_support(support)

    @property
    @override
    def _identifier_prefix(self) -> str:
        return "obs"

    def _check_support(self, support: Sequence[Qubit]) -> None:
        # Check that all the provided registers have a builder
        if any(not qubit._is_attached for qubit in support):
            msg = "Cannot define an observable on non-attached qubits."
            raise ObservableError(msg)
        # Check that all the provided registers have the same builder and, if self is attached to a
        # builder, that it is also attached to the same builder.
        objects_with_same_builder_expected = list[BaseAPIObject](
            itertools.chain(support, self._measurements)
        )
        if self._is_attached:
            objects_with_same_builder_expected.append(self)
        if not all_objects_managed_by_same_builder(objects_with_same_builder_expected):
            raise DifferentBuildersError()

    def _set_support(self, support: Sequence[Qubit]) -> None:
        self._check_support(support)
        self._support = tuple(support)

    @property
    @override
    def _type_info(self) -> Attribute:
        return ObservableType()

    def include(self, measurements: MeasurementReg | Sequence[MeasurementBit]) -> None:
        """Include the provided ``measurements`` in the observable definition.

        This method is equivalent to using an ``OBSERVABLE_INCLUDE`` instruction in ``stim``. It
        will fail if ``self`` has been declared on a ``support``.

        Args:
            measurements: all measurements that should be included in the observable definition.

        Raises:
            ObservableError: if you used this method on an observable that is not correctly attached
                to a builder or with a non-empty support.
            DifferentBuildersError: if the provided measurements are not managed by the same
                builder.
        """
        if not self._is_attached:
            msg = "Cannot call Observable.include on an observable that is not attached."
            raise ObservableError(msg)
        if self._support:
            msg = "Cannot use the include method when the observable is declared on a support."
            raise ObservableError(msg)

        if isinstance(measurements, MeasurementReg):
            measurements = measurements.unpack()
        if not all_objects_managed_by_same_builder([*measurements, self]):
            raise DifferentBuildersError()
        self._measurements.extend(measurements)
        self._builder.append_op_and_update_ssas(
            ObservableIncludeOp(self.ssa, [meas.ssa for meas in measurements]), self
        )

    def move(
        self, new_support: Sequence[Qubit], measurements: MeasurementReg | Sequence[MeasurementBit]
    ) -> None:
        """Move the observable on new supporting qubits by using the provided measurements.

        This method will include the provided ``measurements`` in the observable definition and
        override the qubits the observable was defined on to replace them with ``new_support``.

        Args:
            new_support: new set of qubits the observable is now supported on.
            measurements: all measurements that should be included in the observable definition.

        Raises:
            ObservableError: if you used this method on an observable that is not correctly attached
                to a builder or with an empty support.
        """
        if not self._is_attached:
            msg = "Cannot call Observable.move on an observable that is not attached."
            raise ObservableError(msg)
        if not self._support:
            msg = (
                "Cannot use the move method when the observable has not been declared as being "
                "supported on qubits."
            )
            raise ObservableError(msg)

        if isinstance(measurements, MeasurementReg):
            measurements = measurements.unpack()
        self._measurements.extend(measurements)
        self._set_support(new_support)
        self._builder.append_op_and_update_ssas(
            MoveObservableOp(self.ssa, [q.ssa for q in new_support], [m.ssa for m in measurements]),
            self,
        )

    def get_uncorrected(self) -> ClassicalExpression:
        """Returns a classical expression representing the uncorrected value of the observable.

        Returns:
            An object representing the uncorrected value.
        """
        return self._builder.append_op_and_update_ssas(
            GetUncorrectedOp(self.ssa), UncorrectedObservableExpression(self)
        )

    def get_correction(self) -> ClassicalExpression:
        """Returns the correction required to correct the observable, as computed by a decoder.

        Returns:
            An object representing the correction.
        """
        return self._builder.append_op_and_update_ssas(
            GetCorrectionOp(self.ssa), ObservableCorrectionExpression(self)
        )

    def correction_ready(self) -> ClassicalExpression:
        """Returns a classical expression representing whether or not the correction is ready.

        This method immediately returns whether or not the correction is ready.

        Returns:
            An object representing whether or not the correction is ready.
        """
        return self._builder.append_op_and_update_ssas(
            IsCorrectionReadyOp(self.ssa), ObservableCorrectionIsReadyExpression(self)
        )

    def get_corrected(self) -> ClassicalExpression:
        """Returns the corrected value of the observable.

        Returns:
            An object representing the corrected value.
        """
        return self._builder.append_op_and_update_ssas(
            GetCorrectedOp(self.ssa), CorrectedObservableExpression(self)
        )
