# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for a factory that generates noise parameters from a noise model config."""

from deltakit_compile.noise_models.gate_noise import GateNoiseConfig, gate_noise_factory
from deltakit_compile.noise_models.no_noise import NoNoiseConfig, no_noise_factory
from deltakit_compile.noise_models.noise_parameters import NoiseParameters
from deltakit_compile.noise_models.phenomenological_noise import (
    PhenomenologicalNoiseConfig,
    ToyPhenomenologicalNoiseConfig,
    phenomenological_noise_factory,
    toy_phenomenological_noise_factory,
)
from deltakit_compile.noise_models.sd6_noise import SD6NoiseConfig, sd6_noise_factory
from deltakit_compile.noise_models.si1000_noise import (
    SI1000NoiseConfig,
    SI1000NoResetNoiseConfig,
    SI1000NoResetWithGateTimingsNoiseConfig,
    SI1000WithGateTimingsNoiseConfig,
    si1000_no_reset_noise_factory,
    si1000_no_reset_with_gate_timings_noise_factory,
    si1000_noise_factory,
    si1000_with_gate_timings_noise_factory,
)

NoiseConfig = (
    SI1000NoiseConfig
    | SI1000NoResetNoiseConfig
    | SI1000WithGateTimingsNoiseConfig
    | SI1000NoResetWithGateTimingsNoiseConfig
    | SD6NoiseConfig
    | PhenomenologicalNoiseConfig
    | ToyPhenomenologicalNoiseConfig
    | NoNoiseConfig
    | GateNoiseConfig
)
"""Union of noise model config types."""


def noise_param_factory(noise_config: NoiseConfig) -> NoiseParameters:  # noqa: PLR0911
    """Construct noise parameters from a noise config."""
    match noise_config:
        case SI1000NoiseConfig():
            return si1000_noise_factory(noise_config)
        case SI1000WithGateTimingsNoiseConfig():
            return si1000_with_gate_timings_noise_factory(noise_config)
        case SI1000NoResetNoiseConfig():
            return si1000_no_reset_noise_factory(noise_config)
        case SI1000NoResetWithGateTimingsNoiseConfig():
            return si1000_no_reset_with_gate_timings_noise_factory(noise_config)
        case SD6NoiseConfig():
            return sd6_noise_factory(noise_config)
        case NoNoiseConfig():
            return no_noise_factory()
        case GateNoiseConfig():
            return gate_noise_factory(noise_config)
        case PhenomenologicalNoiseConfig():
            return phenomenological_noise_factory(noise_config)
        case ToyPhenomenologicalNoiseConfig():
            return toy_phenomenological_noise_factory(noise_config)
    msg = "No noise factory found for given config."
    raise TypeError(msg)
