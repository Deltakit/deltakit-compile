# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module containing classes used to capture native gate sets and gate times of a QPU."""

from deltakit_compile.noise_models.noise_parameters import DeltakitStimQuantumGatesetKey
from deltakit_compile.shared.deltakit_stim.gates import (
    MeasurementEnum,
    MPPEnum,
    ResetEnum,
    SingleQubitUnitaryEnum,
    TwoQubitUnitaryEnum,
)

DEFAULT_GATES: set[DeltakitStimQuantumGatesetKey] = {
    SingleQubitUnitaryEnum.X,
    SingleQubitUnitaryEnum.Y,
    SingleQubitUnitaryEnum.Z,
    SingleQubitUnitaryEnum.H,
    SingleQubitUnitaryEnum.S,
    TwoQubitUnitaryEnum.CX,
    MeasurementEnum.MZ,
    ResetEnum.RZ,
}


EXHAUSTIVE_GATESET: set[DeltakitStimQuantumGatesetKey] = (
    set[DeltakitStimQuantumGatesetKey](SingleQubitUnitaryEnum)
    .union(set(TwoQubitUnitaryEnum))
    .union(set(MeasurementEnum))
    .union(set(ResetEnum))
    .union(set(MPPEnum))
)


class NativeGateSetAndTimes:
    """
    Class for capturing native gate sets of a quantum computer and times of
    gate execution (in seconds).

    Args:
        native_gates:
            Dictionary of the gates available on the quantum computer and the associated times.
            By default, the gates are those in DEFAULT_GATES with times all equal to 1.0.

    Raises:
        ValueError: If any supplied gate is not a valid gate (i.e. one-qubit, two-qubit,
            reset, measurement, or Pauli product gate), or if any time is not a positive float.
    """

    def __init__(
        self,
        native_gates: dict[DeltakitStimQuantumGatesetKey, float] | None = None,
    ):

        self.native_gates = (
            dict.fromkeys(DEFAULT_GATES, 1.0) if native_gates is None else native_gates
        )

        invalid_gates = set(self.native_gates) - EXHAUSTIVE_GATESET
        if invalid_gates:
            msg = f"{invalid_gates} are not valid gates in the native gate set."
            raise ValueError(msg)

        for gate, time in self.native_gates.items():
            self._check_time(gate, time)

    @staticmethod
    def _check_time(gate: DeltakitStimQuantumGatesetKey, time: float) -> None:
        if time < 0.0:
            msg = f"A gate time must be a non-negative float but that for {gate} is {time}."
            raise ValueError(msg)

    def add_gate(self, gate: DeltakitStimQuantumGatesetKey, time: float = 1.0) -> None:
        """
        Add a gate and associated time to the native gate set.

        Args:
            gate:
                Gate to be added.
            time:
                Time of the gate to be added. By default, 1.0.
        Raises:
            ValueError: If any supplied gate is not a valid gate (i.e. one-qubit, two-qubit,
                reset, measurement, or Pauli product gate).
        """
        self._check_time(gate, time)
        if gate in EXHAUSTIVE_GATESET:
            self.native_gates[gate] = time
        else:
            msg = f"Unknown gate {gate} supplied."
            raise ValueError(msg)


class NativeGateSet(NativeGateSetAndTimes):
    """
    Class for capturing native gate sets of a quantum computer.

    Args:
        native_gates:
            Set of the gates available on the quantum computer. By default,
            the gates are those in DEFAULT_GATES.
    """

    def __init__(
        self,
        native_gates: set[DeltakitStimQuantumGatesetKey] | None = None,
    ):
        native_gates_and_times = (
            dict.fromkeys(native_gates, 1.0) if native_gates is not None else None
        )

        super().__init__(
            native_gates=native_gates_and_times,
        )


class ExhaustiveGateSet(NativeGateSet):
    """
    Class for capturing gateset of a quantum computer that can perform all gates
    natively.
    """

    def __init__(
        self,
    ):
        super().__init__(
            native_gates=EXHAUSTIVE_GATESET,
        )
