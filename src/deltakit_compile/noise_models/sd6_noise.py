# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for the implementation of the SD6 noise model: https://arxiv.org/abs/2108.10457"""

from collections.abc import Mapping

from typing_extensions import override

from deltakit_compile.noise_models.noise_parameters import (
    BaseIdleNoise,
    BasePauliNoise,
    GateNoise,
    GateNoiseDict,
    MeasurementNoise,
    NoiseParameters,
    OneQubitDepolarisingNoise,
    OneQubitPauliNoise,
    ResetEnum,
    TwoQubitDepolarisingNoise,
)
from deltakit_compile.passes.common.pipeline import NamedConfiguration
from deltakit_compile.shared.deltakit_stim.gates import (
    DeltakitStimQuantumOpEnum,
    SingleQubitUnitaryEnum,
    TwoQubitUnitaryEnum,
)


class SD6NoiseConfig(NamedConfiguration, frozen=True, extra="forbid"):
    """Configurations for an SD6 noise model."""

    p: float
    """Physical error rate (all noise is derived from this number)."""


class SD6IdleNoise(BaseIdleNoise):
    """Defines static idle noise based on a single parameter."""

    def __init__(self, probability: float) -> None:
        self.probability = probability

    @override
    def from_executed_ops(
        self,
        executed_ops: Mapping[DeltakitStimQuantumOpEnum, list[int]],
        idle_qubit: int | None = None,
    ) -> list[BasePauliNoise]:
        return [OneQubitDepolarisingNoise(p=self.probability)]


def sd6_noise_factory(noise_config: SD6NoiseConfig) -> NoiseParameters:
    """Generate noise parameters from an SD6 configuration."""
    gates = GateNoiseDict(
        {
            gate_name: GateNoise(after=[OneQubitDepolarisingNoise(p=noise_config.p)])
            for gate_name in SingleQubitUnitaryEnum
        }
    )
    gates.update(
        {
            gate_name: GateNoise(after=[TwoQubitDepolarisingNoise(p=noise_config.p)])
            for gate_name in TwoQubitUnitaryEnum
        }
    )
    gates.update(
        {
            gate_name: GateNoise(after=[OneQubitPauliNoise(x=noise_config.p)])
            for gate_name in ResetEnum
        }
    )
    return NoiseParameters(
        gates=gates,
        measurement=MeasurementNoise(bit_flip_p=noise_config.p),
        idle=SD6IdleNoise(probability=noise_config.p),
    )
