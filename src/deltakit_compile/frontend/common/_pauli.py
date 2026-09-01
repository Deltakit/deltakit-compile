# (c) Copyright Riverlane 2025-2026. All rights reserved.
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from enum import IntEnum
from typing import Literal

from deltakit_compile.dialects.qcore import PauliAttr
from deltakit_compile.frontend.common._exceptions import (
    DuplicatedIdentifiersError,
    ObjectNotAttachedError,
)
from deltakit_compile.frontend.common._measurements import MeasurementBit, MeasurementReg
from deltakit_compile.frontend.common._qubit_reg import Qubit


class Pauli(IntEnum):
    """Represents a Pauli character.

    Attributes:
        X: Pauli X.
        Y: Pauli Y.
        Z: Pauli Z.
    """

    X = 0b01
    Y = 0b11
    Z = 0b10

    def to_qcore_attr(self) -> PauliAttr:
        match self:
            case Pauli.X:
                return PauliAttr.X()
            case Pauli.Y:
                return PauliAttr.Y()
            case Pauli.Z:
                return PauliAttr.Z()

    @staticmethod
    def coerce(value: PauliType) -> Pauli:
        if isinstance(value, Pauli):
            return value

        if isinstance(value, PauliAttr):
            value = value.to_string()
        match value:
            case "X":
                return Pauli.X
            case "Y":
                return Pauli.Y
            case "Z":
                return Pauli.Z


PauliType = Pauli | PauliAttr | Literal["X", "Y", "Z"]


class PauliString:
    """Represents an immutable Pauli string.

    Args:
        pauli_string: a mapping from ``Qubit`` instances to the type of Pauli that is supported on
            this qubit.

    Raises:
        ObjectNotAttachedError: if any of the provided ``Qubit`` does not have a builder.
    """

    def __init__(self, pauli_string: Mapping[Qubit, PauliType]) -> None:
        for qubit in pauli_string:
            if not qubit._is_attached:
                raise ObjectNotAttachedError()
        self._string: dict[Qubit, Pauli] = {
            reg: Pauli.coerce(pauli) for reg, pauli in pauli_string.items()
        }

    def __len__(self) -> int:
        return len(self._string)

    def __getitem__(self, index: Qubit) -> Pauli:
        if not index._is_attached:
            raise ObjectNotAttachedError()
        return self._string[index]

    def get(self, index: Qubit, /, default: Pauli | None = None) -> Pauli | None:
        if not index._is_attached:
            raise ObjectNotAttachedError()
        return self._string.get(index, default)

    def items(self) -> Iterable[tuple[Qubit, Pauli]]:
        return self._string.items()


class PauliFlow:
    """An immutable representation of a Pauli flow.

    A Pauli flow represents the propagation of Pauli information through quantum instructions. As
    such it maps an ``inputs`` Pauli string to an ``outputs`` Pauli string, potentially mediated by
    some ``measurements``. Finally, the Pauli flow might have a sign.

    Args:
        inputs: input Pauli string that would propagate to ``outputs`` mediated by
            ``measurements`` if propagated through a quantum circuit supporting this flow.
        outputs: output Pauli string that would be propagated from ``inputs`` mediated by
            ``measurements``.
        measurements: measurements mediating the flow (i.e., results returned by measurements
            operations that commutes with a non-trivial part of the flow and collapses its
            state).
        sign: ``True`` if the flow has a ``+`` sign, else ``False``.
    """

    def __init__(
        self,
        inputs: PauliString,
        outputs: PauliString,
        measurements: Iterable[MeasurementBit] | MeasurementReg,
        sign: bool = True,
    ) -> None:
        self._inputs = inputs
        self._outputs = outputs
        self._measurements = (
            measurements.unpack()
            if isinstance(measurements, MeasurementReg)
            else tuple(measurements)
        )
        self._sign = sign
        # Check that all the measurements are unique.
        counter = Counter(m.identifier for m in self._measurements)
        if duplicates := {k for k, v in counter.items() if v > 1}:
            raise DuplicatedIdentifiersError(duplicates)

    @property
    def measurements(self) -> tuple[MeasurementBit, ...]:
        return self._measurements

    @property
    def inputs(self) -> PauliString:
        return self._inputs

    @property
    def outputs(self) -> PauliString:
        return self._outputs

    @property
    def sign(self) -> bool:
        return self._sign
