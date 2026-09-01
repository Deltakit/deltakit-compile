# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for an idle noise model that finds times of operations
on given qubits and applies a decay noise based on T1 and T2 times."""

from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np
from typing_extensions import override

from deltakit_compile.noise_models.noise_parameters import (
    BaseIdleNoise,
    BasePauliNoise,
    IdMeasurement,
    IdMPP,
    MeasurementEnum,
    OneQubitDepolarisingNoise,
    OneQubitPauliNoise,
    ResetEnum,
    SingleQubitIdGate,
    TwoQubitIdGate,
)
from deltakit_compile.shared.deltakit_stim.gates import (
    DeltakitStimQuantumOpEnum,
    MPPEnum,
    SingleQubitUnitaryEnum,
    TwoQubitUnitaryEnum,
)
from deltakit_compile.utilities.gatesets import DeltakitStimQuantumGatesetKey


@dataclass(frozen=True)
class DecoherenceTime:
    """T1 and T2 times for a qubit in seconds."""

    t1_time: float = 0
    t2_time: float = 0


@dataclass(frozen=True)
class DecayIdleNoise(BaseIdleNoise):
    """Idle noise model that applies a decay noise based on T1 and T2 times.
    It assumes all operations between time steps are happening in parallel.
    """

    decay_spec: DecoherenceTime | dict[int, DecoherenceTime] = field(
        default_factory=DecoherenceTime
    )
    """Idle noise model that applies a decay noise based on T1 and T2 times."""
    operation_times: dict[DeltakitStimQuantumGatesetKey, float] = field(default_factory=dict)
    """Dictionary of operation times for each gate or measurement type in seconds.
    If a gate is not present, it is assumed to have zero time."""

    @staticmethod
    def idle_noise_from_t1_t2(time: float, t1_time: float, t2_time: float) -> BasePauliNoise:
        """
        Return a function that calculates idle noise as a function of T1 and T2
        times. See `Ghosh et al. <https://arxiv.org/abs/1210.0.5799>`_ for the
        derivation, with the final result in equation (10).

        Args:
            time:
                Total time in s.
            t1_time:
                T1 time in s.
            t2_time:
                T2 time in s.

        Returns:
            A OneQubitPauliNoise or OneQubitDepolarisingNoise depending on if T1 = T2.
        """

        if t1_time == t2_time:
            return OneQubitDepolarisingNoise(p=max(0.75 * (1.0 - np.exp(-time / t1_time)), 0))
        return OneQubitPauliNoise(
            max(0.25 * (1.0 - np.exp(-time / t1_time)), 0),
            max(0.25 * (1.0 - np.exp(-time / t1_time)), 0),
            max(
                0.5 * (1.0 - np.exp(-time / t2_time)) - 0.25 * (1.0 - np.exp(-time / t1_time)),
                0,
            ),
        )

    def _generic_operation_time(self, op: DeltakitStimQuantumGatesetKey) -> float:
        """Return the time for a given (untargeted) operation."""
        try:
            return self.operation_times[op]
        except KeyError as exp:
            msg = f"Operation {op} does not have a defined time in the noise model."
            raise KeyError(msg) from exp

    def _one_qubit_operation_times(
        self, op: SingleQubitUnitaryEnum | ResetEnum | MeasurementEnum, targets: list[int]
    ) -> list[float]:
        operation_times = []
        for target in targets:
            # check if the targeted operation is defined
            targeted_op = (
                IdMeasurement(op, target)
                if isinstance(op, MeasurementEnum)
                else SingleQubitIdGate(op, target)
            )
            if (time := self.operation_times.get(targeted_op)) is None:
                # if not, use the untargeted operation time
                time = self._generic_operation_time(op)
            operation_times.append(time)
        return operation_times

    def _two_qubit_operation_times(
        self, op: TwoQubitUnitaryEnum, targets: list[int]
    ) -> list[float]:
        operation_times = []
        # iterate over pairs of qubits involved in an operation
        for target1, target2 in zip(targets[0::2], targets[1::2], strict=False):
            # check if the targeted operation is defined
            if (time := self.operation_times.get(TwoQubitIdGate(op, (target1, target2)))) is None:
                # if not, use the untargeted operation time
                time = self._generic_operation_time(op)
            operation_times.append(time)
        return operation_times

    def _multi_qubit_operation_times(self, op: MPPEnum, targets: list[int]) -> list[float]:
        """Calculates the operation time of a multi-qubit MPP operation,
        where all the target qubits are part of the same MPP product measurement."""
        # check if the targeted operation is defined
        if (time := self.operation_times.get(IdMPP(op, tuple(targets)))) is None:
            # if not, use the untargeted operation time
            time = self._generic_operation_time(op)
        return [time]

    def qubit_total_time(
        self, executed_ops: Mapping[DeltakitStimQuantumOpEnum, list[int]], qubit_id: int
    ) -> float:
        """Calculate the total time for which a qubit is active based on the executed operations."""
        total_time = 0.0
        for op, targets in executed_ops.items():
            if isinstance(op, TwoQubitUnitaryEnum):
                op_times = self._two_qubit_operation_times(op, targets)
                # iterate over pairs of qubits involved in an operation
                for (target1, target2), time in zip(
                    zip(targets[0::2], targets[1::2], strict=False), op_times, strict=False
                ):
                    # add the time of the operation if it involves the target qubit
                    if qubit_id in (target1, target2):
                        total_time += time
            elif isinstance(op, MPPEnum):
                op_time = self._multi_qubit_operation_times(op, targets)[0]
                for target in targets:
                    if target == qubit_id:
                        total_time += op_time
            else:
                op_times = self._one_qubit_operation_times(op, targets)
                for target, time in zip(targets, op_times, strict=False):
                    if target == qubit_id:
                        total_time += time
        return total_time

    def executed_ops_total_time(
        self, executed_ops: Mapping[DeltakitStimQuantumOpEnum, list[int]]
    ) -> float:
        """Calculate the total time taken for the executed operations. Different qubits
        can be used in the same operation and the same qubit can be used in multiple
        operations, so the total time taken is the maximum active time across all qubits."""
        unique_targets = set()
        total_time = 0.0
        for targets in executed_ops.values():
            unique_targets.update(targets)
        for target in unique_targets:
            total_time = max(self.qubit_total_time(executed_ops, target), total_time)
        return total_time

    @override
    def from_executed_ops(
        self,
        executed_ops: Mapping[DeltakitStimQuantumOpEnum, list[int]],
        idle_qubit: int | None = None,
    ) -> list[BasePauliNoise]:
        if isinstance(self.decay_spec, DecoherenceTime):
            decay_spec = self.decay_spec
        else:
            if idle_qubit is None:
                msg = "Idle qubit must be specified when T1 and T2 are given per qubit."
                raise ValueError(msg)
            decay_spec = self.decay_spec.get(idle_qubit, DecoherenceTime())
        t1_time = decay_spec.t1_time
        t2_time = decay_spec.t2_time
        if t1_time == 0 and t2_time == 0:
            return []
        # calculate the total time of the executed operations
        total_time = self.executed_ops_total_time(executed_ops)
        if total_time == 0:
            return []
        return [self.idle_noise_from_t1_t2(total_time, t1_time, t2_time)]
