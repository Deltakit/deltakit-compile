"""Test that the noise parameter factory can produce noise parameters of each type."""

from collections import defaultdict

import pytest

from deltakit_compile.exceptions import NoiseWarning
from deltakit_compile.noise_models.gate_noise import GateNoiseConfig
from deltakit_compile.noise_models.idle_noise import DecayIdleNoise, DecoherenceTime
from deltakit_compile.noise_models.no_noise import NoNoiseConfig
from deltakit_compile.noise_models.noise_factory import noise_param_factory
from deltakit_compile.noise_models.noise_parameters import (
    GateNoise,
    IdMeasurement,
    LeakageNoise,
    MeasurementNoise,
    OneQubitDepolarisingNoise,
    OneQubitPauliNoise,
    RelaxNoise,
    SingleQubitIdGate,
    TwoQubitDepolarisingNoise,
    TwoQubitIdGate,
)
from deltakit_compile.noise_models.phenomenological_noise import (
    PhenomenologicalNoiseConfig,
    ToyPhenomenologicalNoiseConfig,
)
from deltakit_compile.noise_models.sd6_noise import SD6NoiseConfig
from deltakit_compile.noise_models.si1000_noise import (
    SI1000NoiseConfig,
    SI1000NoResetNoiseConfig,
    SI1000NoResetWithGateTimingsNoiseConfig,
    SI1000WithGateTimingsNoiseConfig,
)
from deltakit_compile.shared.deltakit_stim.gates import (
    MeasurementEnum,
    ResetEnum,
    SingleQubitUnitaryEnum,
    TwoQubitUnitaryEnum,
)


@pytest.mark.parametrize(
    ("noise_config"),
    [
        (NoNoiseConfig()),
        (PhenomenologicalNoiseConfig()),
        (ToyPhenomenologicalNoiseConfig()),
    ],
)
def test_no_noise(
    noise_config: (NoNoiseConfig | PhenomenologicalNoiseConfig | ToyPhenomenologicalNoiseConfig),
):
    """Test that the noise parameter factory can produce noise parameters that add no noise."""
    params = noise_param_factory(noise_config)
    assert params.gates[SingleQubitUnitaryEnum.X] == GateNoise()
    assert params.gates[TwoQubitUnitaryEnum.CX] == GateNoise()
    assert params.gates[ResetEnum.R] == GateNoise()
    assert "john" not in params.gates
    assert len(params.idle.from_executed_ops({ResetEnum.R: []})) == 0
    assert params.measurement == MeasurementNoise()


@pytest.mark.parametrize(
    "si1000_config_class",
    [SI1000NoiseConfig, SI1000WithGateTimingsNoiseConfig],
)
def test_si1000_noise(si1000_config_class):
    """Test that the noise parameter factory can produce SI1000 noise parameters."""
    params = noise_param_factory(si1000_config_class(p=0.01))
    assert params.gates[SingleQubitUnitaryEnum.X] == GateNoise(
        after=[OneQubitDepolarisingNoise(p=0.001)]
    )
    assert params.gates[TwoQubitUnitaryEnum.CX] == GateNoise(
        after=[TwoQubitDepolarisingNoise(p=0.01)]
    )
    assert "john" not in params.gates
    assert params.gates[ResetEnum.R] == GateNoise(after=[OneQubitPauliNoise(x=0.02, y=0, z=0)])
    assert params.gates[ResetEnum.RX] == GateNoise(after=[OneQubitPauliNoise(x=0, y=0, z=0.02)])
    assert params.idle.from_executed_ops({SingleQubitUnitaryEnum.SQRT_X}) == [
        OneQubitDepolarisingNoise(p=0.001)
    ]
    assert params.idle.from_executed_ops({MeasurementEnum.M}) == [
        OneQubitDepolarisingNoise(p=0.001)
    ]
    assert params.resonant_idle.from_executed_ops({MeasurementEnum.M}) == [
        OneQubitDepolarisingNoise(p=0.02)
    ]
    assert params.idle.from_executed_ops({SingleQubitUnitaryEnum.SQRT_X, ResetEnum.R}) == [
        OneQubitDepolarisingNoise(p=0.001)
    ]
    assert params.resonant_idle.from_executed_ops({SingleQubitUnitaryEnum.SQRT_X, ResetEnum.R}) == [
        OneQubitDepolarisingNoise(p=0.02)
    ]
    assert params.initialisation == {}
    assert params.measurement == MeasurementNoise(bit_flip_p=0.05)


@pytest.mark.parametrize(
    "si1000_config_class",
    [SI1000NoResetNoiseConfig, SI1000NoResetWithGateTimingsNoiseConfig],
)
def test_si1000_no_reset_noise(si1000_config_class):
    """Test that the noise parameter factory can produce SI1000 noise parameters without reset."""
    params = noise_param_factory(si1000_config_class(p=0.01))
    assert params.gates[SingleQubitUnitaryEnum.X] == GateNoise(
        after=[OneQubitDepolarisingNoise(p=0.001)]
    )
    assert params.gates[TwoQubitUnitaryEnum.CX] == GateNoise(
        after=[TwoQubitDepolarisingNoise(p=0.01)]
    )
    assert "john" not in params.gates
    assert params.gates[ResetEnum.R] == GateNoise(after=[OneQubitPauliNoise(x=0.02, y=0, z=0)])
    assert params.gates[ResetEnum.RX] == GateNoise(after=[OneQubitPauliNoise(x=0, y=0, z=0.02)])
    assert params.idle.from_executed_ops({SingleQubitUnitaryEnum.SQRT_X}) == [
        OneQubitDepolarisingNoise(p=0.001)
    ]
    assert params.idle.from_executed_ops({MeasurementEnum.M}) == [
        OneQubitDepolarisingNoise(p=0.001)
    ]
    assert params.resonant_idle.from_executed_ops({MeasurementEnum.M}) == [
        OneQubitDepolarisingNoise(p=0.02)
    ]
    assert params.idle.from_executed_ops({SingleQubitUnitaryEnum.SQRT_X, ResetEnum.R}) == [
        OneQubitDepolarisingNoise(p=0.001)
    ]
    assert params.resonant_idle.from_executed_ops({SingleQubitUnitaryEnum.SQRT_X, ResetEnum.R}) == [
        OneQubitDepolarisingNoise(p=0.02)
    ]
    assert params.initialisation == {}
    assert params.measurement[MeasurementEnum.M] == MeasurementNoise(
        before=[OneQubitPauliNoise(x=0.04 / 0.98)], bit_flip_p=0.01
    )
    assert params.measurement[MeasurementEnum.MX] == MeasurementNoise(
        before=[OneQubitPauliNoise(z=0.04 / 0.98)], bit_flip_p=0.01
    )


@pytest.mark.parametrize(
    "si1000_config_class",
    [SI1000NoiseConfig, SI1000WithGateTimingsNoiseConfig],
)
def test_si1000_leakage_noise(si1000_config_class):
    """Test that the noise parameter factory can produce SI1000 with leakage noise parameters."""
    params = noise_param_factory(si1000_config_class(p=0.01, pL=0.003))
    assert params.gates[SingleQubitUnitaryEnum.X] == GateNoise(
        after=[OneQubitDepolarisingNoise(p=0.001), RelaxNoise(p=0.002)]
    )
    assert params.gates[TwoQubitUnitaryEnum.CX] == GateNoise(
        after=[TwoQubitDepolarisingNoise(p=0.01), LeakageNoise(p=0.003), RelaxNoise(p=0.003)]
    )
    assert "john" not in params.gates
    assert params.gates[ResetEnum.R] == GateNoise(
        after=[OneQubitPauliNoise(x=0.02, y=0, z=0), LeakageNoise(p=0.003)]
    )
    assert params.idle.from_executed_ops({SingleQubitUnitaryEnum.SQRT_X}) == [
        OneQubitDepolarisingNoise(p=0.001),
        RelaxNoise(p=0.002),
    ]
    assert params.idle.from_executed_ops({MeasurementEnum.M}) == [
        OneQubitDepolarisingNoise(p=0.001),
        RelaxNoise(p=0.002),
    ]
    assert params.resonant_idle.from_executed_ops({MeasurementEnum.M}) == [
        OneQubitDepolarisingNoise(p=0.02),
        RelaxNoise(p=0.04),
    ]
    assert params.idle.from_executed_ops({SingleQubitUnitaryEnum.SQRT_X, ResetEnum.R}) == [
        OneQubitDepolarisingNoise(p=0.001),
        RelaxNoise(p=0.002),
    ]
    assert params.resonant_idle.from_executed_ops({SingleQubitUnitaryEnum.SQRT_X, ResetEnum.R}) == [
        OneQubitDepolarisingNoise(p=0.02),
        RelaxNoise(p=0.04),
    ]
    assert params.initialisation == {}
    assert params.measurement == MeasurementNoise(bit_flip_p=0.05)
    assert params.leakage_herald == 0.05


@pytest.mark.parametrize(
    "si1000_config_class",
    [SI1000NoResetNoiseConfig, SI1000NoResetWithGateTimingsNoiseConfig],
)
def test_si1000_no_reset_leakage_noise(si1000_config_class):
    """Test that the noise parameter factory can produce SI1000 with leakage noise parameters."""
    params = noise_param_factory(si1000_config_class(p=0.01, pL=0.003))
    assert params.gates[SingleQubitUnitaryEnum.X] == GateNoise(
        after=[OneQubitDepolarisingNoise(p=0.001), RelaxNoise(p=0.002)]
    )
    assert params.gates[TwoQubitUnitaryEnum.CX] == GateNoise(
        after=[TwoQubitDepolarisingNoise(p=0.01), LeakageNoise(p=0.003), RelaxNoise(p=0.003)]
    )
    assert "john" not in params.gates
    assert params.gates[ResetEnum.R] == GateNoise(
        after=[OneQubitPauliNoise(x=0.02, y=0, z=0), LeakageNoise(p=0.003)]
    )
    assert params.idle.from_executed_ops({SingleQubitUnitaryEnum.SQRT_X}) == [
        OneQubitDepolarisingNoise(p=0.001),
        RelaxNoise(p=0.002),
    ]
    assert params.idle.from_executed_ops({MeasurementEnum.M}) == [
        OneQubitDepolarisingNoise(p=0.001),
        RelaxNoise(p=0.002),
    ]
    assert params.resonant_idle.from_executed_ops({MeasurementEnum.M}) == [
        OneQubitDepolarisingNoise(p=0.02),
        RelaxNoise(p=0.04),
    ]
    assert params.idle.from_executed_ops({SingleQubitUnitaryEnum.SQRT_X, ResetEnum.R}) == [
        OneQubitDepolarisingNoise(p=0.001),
        RelaxNoise(p=0.002),
    ]
    assert params.resonant_idle.from_executed_ops({SingleQubitUnitaryEnum.SQRT_X, ResetEnum.R}) == [
        OneQubitDepolarisingNoise(p=0.02),
        RelaxNoise(p=0.04),
    ]
    assert params.initialisation == {}
    assert params.measurement[MeasurementEnum.M] == MeasurementNoise(
        before=[OneQubitPauliNoise(x=0.04 / 0.98)], bit_flip_p=0.01
    )
    assert params.measurement[MeasurementEnum.MX] == MeasurementNoise(
        before=[OneQubitPauliNoise(z=0.04 / 0.98)], bit_flip_p=0.01
    )


@pytest.mark.parametrize(
    "si1000_config_class",
    [SI1000NoiseConfig, SI1000WithGateTimingsNoiseConfig],
)
def test_si1000_noise_bitflip_cap(si1000_config_class):
    """
    Test that the noise parameter factory will not produce bit flip prob higher than 1 and
    that a warning is thrown
    """
    with pytest.warns(
        NoiseWarning,
        match="Bit flip noise probability was 1.25, values greater than 1 are capped to 1.0",
    ):
        params = noise_param_factory(si1000_config_class(p=0.25))
    assert params.measurement == MeasurementNoise(bit_flip_p=1.0)


def test_sd6_noise():
    """Test that the noise parameter factory can produce SD6 noise parameters."""
    params = noise_param_factory(SD6NoiseConfig(p=0.01))
    assert params.gates[SingleQubitUnitaryEnum.X] == GateNoise(
        after=[OneQubitDepolarisingNoise(p=0.01)]
    )
    assert params.gates[TwoQubitUnitaryEnum.CX] == GateNoise(
        after=[TwoQubitDepolarisingNoise(p=0.01)]
    )
    assert "dave" not in params.gates
    assert params.gates[ResetEnum.R] == GateNoise(after=[OneQubitPauliNoise(x=0.01, y=0, z=0)])
    assert params.idle.from_executed_ops({SingleQubitUnitaryEnum.SQRT_X}) == [
        OneQubitDepolarisingNoise(p=0.01)
    ]
    assert params.idle.from_executed_ops({MeasurementEnum.M}) == [OneQubitDepolarisingNoise(p=0.01)]
    assert params.initialisation == {}
    assert params.measurement == MeasurementNoise(bit_flip_p=0.01)


def test_phenomenological_noise():
    """Test that the noise parameter factory can produce phenomenological noise parameters."""
    params = noise_param_factory(
        PhenomenologicalNoiseConfig(
            phenomenological_noise={
                0: OneQubitDepolarisingNoise(p=0.01),
                1: OneQubitPauliNoise(x=0.02),
                2: OneQubitPauliNoise(y=0.03),
                3: OneQubitPauliNoise(z=0.04),
            }
        )
    )
    assert params.gates[SingleQubitIdGate(SingleQubitUnitaryEnum.IDENTITY, 0)] == GateNoise(
        after=[OneQubitDepolarisingNoise(p=0.01)]
    )
    assert params.gates[SingleQubitIdGate(SingleQubitUnitaryEnum.IDENTITY, 1)] == GateNoise(
        after=[OneQubitPauliNoise(x=0.02)]
    )
    assert params.gates[SingleQubitIdGate(SingleQubitUnitaryEnum.IDENTITY, 2)] == GateNoise(
        after=[OneQubitPauliNoise(y=0.03)]
    )
    assert params.gates[SingleQubitIdGate(SingleQubitUnitaryEnum.IDENTITY, 3)] == GateNoise(
        after=[OneQubitPauliNoise(z=0.04)]
    )
    assert params.gates[SingleQubitUnitaryEnum.X] == GateNoise(after=[])
    assert params.gates[TwoQubitUnitaryEnum.CX] == GateNoise(after=[])
    assert params.gates[ResetEnum.R] == GateNoise(after=[])
    assert "john" not in params.gates
    assert len(params.idle.from_executed_ops({SingleQubitUnitaryEnum.X})) == 0
    assert len(params.idle.from_executed_ops({ResetEnum.R})) == 0
    assert params.initialisation == {}
    assert params.measurement == MeasurementNoise()


def test_uniform_phenomenological_noise():
    """Test that the noise parameter factory can produce
    uniform phenomenological noise parameters."""
    params = noise_param_factory(
        PhenomenologicalNoiseConfig(phenomenological_noise=OneQubitDepolarisingNoise(p=0.01))
    )
    assert params.gates[SingleQubitUnitaryEnum.IDENTITY] == GateNoise(
        after=[OneQubitDepolarisingNoise(p=0.01)]
    )
    assert params.gates[SingleQubitUnitaryEnum.X] == GateNoise(after=[])
    assert params.gates[TwoQubitUnitaryEnum.CX] == GateNoise(after=[])
    assert params.gates[ResetEnum.R] == GateNoise(after=[])
    assert "john" not in params.gates
    assert len(params.idle.from_executed_ops({SingleQubitUnitaryEnum.X})) == 0
    assert len(params.idle.from_executed_ops({ResetEnum.R})) == 0
    assert params.initialisation == {}
    assert params.measurement == MeasurementNoise()


def test_toy_phenomenological_noise():
    """Test that the noise parameter factory can produce toy phenomenological noise parameters."""
    params = noise_param_factory(ToyPhenomenologicalNoiseConfig(p=0.01, p_measurement_flip=0.02))
    assert params.gates[SingleQubitUnitaryEnum.IDENTITY] == GateNoise(
        after=[OneQubitDepolarisingNoise(p=0.01)]
    )
    assert params.gates[SingleQubitUnitaryEnum.X] == GateNoise(after=[])
    assert params.gates[TwoQubitUnitaryEnum.CX] == GateNoise(after=[])
    assert params.gates[ResetEnum.R] == GateNoise(after=[])
    assert "john" not in params.gates
    assert len(params.idle.from_executed_ops({SingleQubitUnitaryEnum.X})) == 0
    assert len(params.idle.from_executed_ops({ResetEnum.R})) == 0
    assert params.initialisation == {}
    assert params.measurement == MeasurementNoise(bit_flip_p=0.02)


def test_uniform_toy_phenomenological_noise():
    """Test that the noise parameter factory can produce
    uniform toy phenomenological noise parameters."""
    params = noise_param_factory(ToyPhenomenologicalNoiseConfig(p=0.01))
    assert params.gates[SingleQubitUnitaryEnum.IDENTITY] == GateNoise(
        after=[OneQubitDepolarisingNoise(p=0.01)]
    )
    assert params.gates[SingleQubitUnitaryEnum.X] == GateNoise(after=[])
    assert params.gates[TwoQubitUnitaryEnum.CX] == GateNoise(after=[])
    assert params.gates[ResetEnum.R] == GateNoise(after=[])
    assert "john" not in params.gates
    assert len(params.idle.from_executed_ops({SingleQubitUnitaryEnum.X})) == 0
    assert len(params.idle.from_executed_ops({ResetEnum.R})) == 0
    assert params.initialisation == {}
    assert params.measurement == MeasurementNoise(bit_flip_p=0.01)


def test_generalised_noise():
    """Test that the noise parameter factory can produce generalised noise parameters."""
    noise_model = GateNoiseConfig(
        gates={
            SingleQubitUnitaryEnum.H: GateNoise(after=[OneQubitDepolarisingNoise(p=2e-3)]),
            SingleQubitIdGate(SingleQubitUnitaryEnum.H, 1): GateNoise(
                after=[OneQubitDepolarisingNoise(p=3e-3)]
            ),
            TwoQubitUnitaryEnum.CX: GateNoise(after=[TwoQubitDepolarisingNoise(p=4e-3)]),
            TwoQubitIdGate(TwoQubitUnitaryEnum.CX, (0, 1)): GateNoise(
                after=[TwoQubitDepolarisingNoise(p=5e-3)]
            ),
        },
        measurement={
            MeasurementEnum.MZ: MeasurementNoise(
                before=[OneQubitDepolarisingNoise(p=4e-3)], bit_flip_p=1e-2
            ),
            IdMeasurement(MeasurementEnum.MZ, 0): MeasurementNoise(
                before=[OneQubitDepolarisingNoise(p=5e-3)]
            ),
        },
        decay=DecoherenceTime(t1_time=1.0, t2_time=2.0),
        operation_times={
            SingleQubitUnitaryEnum.H: 0.1,
            SingleQubitIdGate(SingleQubitUnitaryEnum.H, 1): 0.2,
            TwoQubitUnitaryEnum.CX: 0.3,
            TwoQubitIdGate(TwoQubitUnitaryEnum.CX, (0, 1)): 0.4,
            MeasurementEnum.MZ: 0.5,
            IdMeasurement(MeasurementEnum.MZ, 0): 0.6,
        },
        initialisation=defaultdict(lambda: OneQubitPauliNoise(x=1e-3)),
    )
    params = noise_param_factory(noise_model)
    assert params.gates[SingleQubitUnitaryEnum.H] == GateNoise(
        after=[OneQubitDepolarisingNoise(p=2e-3)]
    )
    assert params.gates[SingleQubitIdGate(SingleQubitUnitaryEnum.H, 1)] == GateNoise(
        after=[OneQubitDepolarisingNoise(p=3e-3)]
    )
    assert params.gates[TwoQubitUnitaryEnum.CX] == GateNoise(
        after=[TwoQubitDepolarisingNoise(p=4e-3)]
    )
    assert params.gates[TwoQubitIdGate(TwoQubitUnitaryEnum.CX, (0, 1))] == GateNoise(
        after=[TwoQubitDepolarisingNoise(p=5e-3)]
    )
    assert params.measurement[MeasurementEnum.MZ] == MeasurementNoise(
        before=[OneQubitDepolarisingNoise(p=4e-3)], bit_flip_p=1e-2
    )
    assert params.measurement[IdMeasurement(MeasurementEnum.MZ, 0)] == MeasurementNoise(
        before=[OneQubitDepolarisingNoise(p=5e-3)]
    )
    assert params.idle == DecayIdleNoise(
        decay_spec=DecoherenceTime(t1_time=1.0, t2_time=2.0),
        operation_times={
            SingleQubitUnitaryEnum.H: 0.1,
            SingleQubitIdGate(SingleQubitUnitaryEnum.H, 1): 0.2,
            TwoQubitUnitaryEnum.CX: 0.3,
            TwoQubitIdGate(TwoQubitUnitaryEnum.CX, (0, 1)): 0.4,
            MeasurementEnum.MZ: 0.5,
            IdMeasurement(MeasurementEnum.MZ, 0): 0.6,
        },
    )
    assert params.initialisation == defaultdict(lambda: OneQubitPauliNoise(x=1e-3))
