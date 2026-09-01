"""Tests for noise model parameter classes."""

import pytest

from deltakit_compile.dialects.stim import QubitAllocOp
from deltakit_compile.noise_models.noise_parameters import (
    BasePauliNoise,
    GateNoiseDict,
    LeakageNoise,
    OneQubitDepolarisingNoise,
    OneQubitPauliNoise,
    RelaxNoise,
    TwoQubitDepolarisingNoise,
    TwoQubitPauliNoise,
)
from deltakit_compile.shared.deltakit_stim.gates import TwoQubitUnitaryEnum

qubit = QubitAllocOp(0).res


@pytest.mark.parametrize(
    ("noise", "exp_stim_str"),
    [
        (OneQubitDepolarisingNoise(p=0.001), "DEPOLARIZE1(0.001)"),
        (TwoQubitDepolarisingNoise(p=0.002), "DEPOLARIZE2(0.002)"),
        (OneQubitPauliNoise(x=0.1, y=0.2, z=0.3), "PAULI_CHANNEL_1(0.1, 0.2, 0.3)"),
        (OneQubitPauliNoise(x=0.1), "X_ERROR(0.1)"),
        (OneQubitPauliNoise(y=0.2), "Y_ERROR(0.2)"),
        (OneQubitPauliNoise(z=0.3), "Z_ERROR(0.3)"),
        (
            TwoQubitPauliNoise(*(i * 0.001 for i in range(15))),
            "PAULI_CHANNEL_2(0, 0.001, 0.002, 0.003, 0.004, 0.005, 0.006, 0.007, "
            "0.008, 0.009, 0.01, 0.011, 0.012, 0.013, 0.014)",
        ),
    ],
)
def test_pauli_noise_to_stim(noise: BasePauliNoise, exp_stim_str: str):
    """Test that pauli noise classes can convert themselves to stim instructions."""
    assert str(noise.to_stim([0, 2, 4, 5])) == exp_stim_str + " 0 2 4 5"


@pytest.mark.parametrize(
    ("noise", "exp_stim_str"),
    [
        (LeakageNoise(p=0.1), "LEAKAGE(0.1)"),
        (RelaxNoise(p=0.1), "RELAX(0.1)"),
    ],
)
def test_leakage_noise_to_stim(noise: BasePauliNoise, exp_stim_str: str):
    """Test that pauli noise classes can convert themselves to stim instructions."""
    assert str(noise.to_stim([0, 2, 4, 5])) == exp_stim_str + " 0 2 4 5"


@pytest.mark.parametrize(
    ("noise", "exp_op_str"),
    [
        (OneQubitDepolarisingNoise(p=0.001), "stim.depolarize1 <0.001> (%0, %0)"),
        (TwoQubitDepolarisingNoise(p=0.002), "stim.depolarize2 <0.002> (%0, %0)"),
        (OneQubitPauliNoise(x=0.1, y=0.2, z=0.3), "stim.pauli_channel_1 <0.1, 0.2, 0.3> (%0, %0)"),
        (
            TwoQubitPauliNoise(*(i * 0.001 for i in range(15))),
            "stim.pauli_channel_2 <0.0, 0.001, 0.002, 0.003, 0.004, 0.005, 0.006, 0.007, "
            "0.008, 0.009000000000000001, 0.01, 0.011, 0.012, 0.013000000000000001, 0.014> "
            "(%0, %0)",
        ),
    ],
)
def test_pauli_noise_to_stim_op(noise: BasePauliNoise, exp_op_str: str):
    """Test that pauli noise classes can convert themselves to stim instructions."""
    assert str(noise.to_stim_op([qubit, qubit])) == exp_op_str


@pytest.mark.parametrize(
    ("noise", "exp_op_str"),
    [
        (LeakageNoise(p=0.1), "deltakit_stim.leakage <0.1> (%0, %0)"),
        (RelaxNoise(p=0.1), "deltakit_stim.relax <0.1> (%0, %0)"),
    ],
)
def test_leakage_noise_to_stim_op(noise: BasePauliNoise, exp_op_str: str):
    """Test that pauli noise classes can convert themselves to stim instructions."""
    assert str(noise.to_stim_op([qubit, qubit])) == exp_op_str


def test_gate_noise_dict_key_error():
    """Test that GateNoiseDict throws a custom key error message."""
    with pytest.raises(KeyError, match="Noise parameters have not been defined for CX gates"):
        _ = GateNoiseDict()[TwoQubitUnitaryEnum.CX]
