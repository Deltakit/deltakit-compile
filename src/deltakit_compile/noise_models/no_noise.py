# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for the implementation of a noise model that adds no noise."""

from deltakit_compile.noise_models.noise_parameters import (
    GateNoise,
    GateNoiseDict,
    MeasurementNoise,
    NoIdleNoise,
    NoiseParameters,
)
from deltakit_compile.passes.common.pipeline import NamedConfiguration
from deltakit_compile.shared.deltakit_stim.gates import (
    ResetEnum,
    SingleQubitUnitaryEnum,
    TwoQubitUnitaryEnum,
)


class NoNoiseConfig(NamedConfiguration, frozen=True, extra="forbid"):
    """Configurations for a noise model that adds no noise."""


def no_noise_factory() -> NoiseParameters:
    """Generate noise parameters from a no noise configuration."""
    gates = GateNoiseDict({gate_name: GateNoise() for gate_name in SingleQubitUnitaryEnum})
    gates.update({gate_name: GateNoise() for gate_name in TwoQubitUnitaryEnum})
    gates.update({gate_name: GateNoise() for gate_name in ResetEnum})
    return NoiseParameters(
        gates=gates,
        measurement=MeasurementNoise(),
        idle=NoIdleNoise(),
    )
