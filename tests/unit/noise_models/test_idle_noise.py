"""Test decay idle noise behaviour."""

import pytest

from deltakit_compile.noise_models.idle_noise import DecayIdleNoise, DecoherenceTime
from deltakit_compile.noise_models.noise_parameters import OneQubitPauliNoise
from deltakit_compile.shared.deltakit_stim.gates import (
    MPPEnum,
    SingleQubitUnitaryEnum,
    TwoQubitUnitaryEnum,
)


def test_decay_idle_noise_throws_exception_if_gate_not_defined():
    with pytest.raises(
        KeyError, match="Operation X does not have a defined time in the noise model\\."
    ):
        DecayIdleNoise(
            decay_spec=DecoherenceTime(t1_time=1.0, t2_time=1.0), operation_times={}
        ).executed_ops_total_time({"X": [0]})


def test_decay_idle_noise_calculates_correct_pauli_noise():
    idle_noise = DecayIdleNoise(
        decay_spec={0: DecoherenceTime(t1_time=2.0, t2_time=1.0)}, operation_times={"X": 1}
    )
    noise = idle_noise.from_executed_ops({"X": [1]}, idle_qubit=0)
    assert len(noise) == 1
    assert isinstance(noise[0], OneQubitPauliNoise)
    assert noise[0].x == noise[0].y
    assert noise[0].z > noise[0].x


def test_executed_ops_times_calculated_correctly():
    idle_noise = DecayIdleNoise(
        decay_spec={0: DecoherenceTime(t1_time=2.0, t2_time=1.0)},
        operation_times={
            SingleQubitUnitaryEnum.X: 1.0,
            TwoQubitUnitaryEnum.CX: 2.0,
            MPPEnum.MPP: 3.0,
        },
    )
    x_time = idle_noise.executed_ops_total_time({SingleQubitUnitaryEnum.X: [0]})
    assert x_time == 1.0
    cx_time = idle_noise.executed_ops_total_time({TwoQubitUnitaryEnum.CX: [0, 1]})
    assert cx_time == 2.0
    mpp_time = idle_noise.executed_ops_total_time({MPPEnum.MPP: [0, 1, 2]})
    assert mpp_time == 3.0

    system_1_time = idle_noise.executed_ops_total_time(
        {
            SingleQubitUnitaryEnum.X: [0],
            TwoQubitUnitaryEnum.CX: [1, 2],
            MPPEnum.MPP: [3, 4, 5],
        }
    )
    assert system_1_time == 3.0


def test_decay_idle_noise_throws_exception_if_idle_qubit_unspecified():
    with pytest.raises(
        ValueError, match="Idle qubit must be specified when T1 and T2 are given per qubit\\."
    ):
        DecayIdleNoise(
            decay_spec={0: DecoherenceTime(t1_time=1.0, t2_time=1.0)}, operation_times={"X": 0}
        ).from_executed_ops({"X": [1]})


def test_decay_idle_noise_calculates_no_noise_for_zero_total_time():
    idle_noise = DecayIdleNoise(
        decay_spec={0: DecoherenceTime(t1_time=2.0, t2_time=1.0)}, operation_times={"X": 1}
    )
    noise = idle_noise.from_executed_ops({}, idle_qubit=0)
    assert not noise
