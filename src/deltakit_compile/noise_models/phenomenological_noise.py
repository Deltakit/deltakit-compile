# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for the implementation of the phenomenological noise model.
`PhenomenologicalNoise` adds noise to `I` gates.
`ToyPhenomenologicalNoise` specifies this noise to be Depolarise1,
and adds measurement flip noise."""

from typing import cast

from pydantic import field_validator

from deltakit_compile.noise_models.no_noise import NoIdleNoise
from deltakit_compile.noise_models.noise_parameters import (
    BasePauliNoise,
    GateNoise,
    GateNoiseDict,
    LeakageNoise,
    MeasurementNoise,
    NoiseParameters,
    OneQubitDepolarisingNoise,
    OneQubitPauliNoise,
    RelaxNoise,
    SingleQubitIdGate,
)
from deltakit_compile.passes.common.pipeline import NamedConfiguration
from deltakit_compile.shared.deltakit_stim.gates import (
    ResetEnum,
    SingleQubitUnitaryEnum,
    TwoQubitUnitaryEnum,
)

OneQubitNoiseChannel = OneQubitDepolarisingNoise | OneQubitPauliNoise | RelaxNoise | LeakageNoise


class PhenomenologicalNoiseConfig(NamedConfiguration, frozen=True, extra="forbid"):
    """Configurations for the Riverlane phenomenological noise model.
    Specifies noise that is applied to identity gates only. The noise can be
    provided as a single OneQubitNoiseChannel applied uniformly to all
    qubits, or as a dictionary mapping individual qubit IDs to a specific
    noise channel. If no noise is provided, no noise is applied to any gates.
    """

    phenomenological_noise: dict[int, OneQubitNoiseChannel] | OneQubitNoiseChannel | None = None
    """Phenomenological noise. This can be a dictionary specifying
    one qubit noise channels for each qubit, or a single one qubit
    noise channel which applies to all qubits. By default, no noise."""

    @staticmethod
    def _parse_noise_string(noise_str: str) -> OneQubitNoiseChannel:
        """Parse a noise string (e.g., 'OneQubitDepolarisingNoise 0.01') into a noise channel."""
        noise_split = noise_str.split()
        noise_name = noise_split[0]
        params = [float(v) for v in noise_split[1:]]

        match noise_name:
            case "OneQubitDepolarisingNoise":
                if len(params) != 1:
                    msg = f"Expected 1 param for OneQubitDepolarisingNoise, got {len(params)}"
                    raise ValueError(msg)
                return OneQubitDepolarisingNoise(*params)
            case "OneQubitPauliNoise":
                if len(params) not in {1, 2, 3}:
                    msg = f"Expected 1, 2 or 3 params for OneQubitPauliNoise, got {len(params)}"
                    raise ValueError(msg)
                return OneQubitPauliNoise(*params)
            case "RelaxNoise":
                if len(params) != 1:
                    msg = f"Expected 1 param for RelaxNoise, got {len(params)}"
                    raise ValueError(msg)
                return RelaxNoise(*params)
            case "LeakageNoise":
                if len(params) != 1:
                    msg = f"Expected 1 param for LeakageNoise, got {len(params)}"
                    raise ValueError(msg)
                return LeakageNoise(*params)
            case _:
                msg = f"Unrecognised noise: {noise_name}"
                raise ValueError(msg)

    @field_validator("phenomenological_noise", mode="before")
    @classmethod
    def parse_phenomenological_noise(
        cls,
        value: dict[int, OneQubitNoiseChannel] | dict[int, str] | OneQubitNoiseChannel | None,
    ) -> dict[int, OneQubitNoiseChannel] | OneQubitNoiseChannel | None:
        """Parse input phenomenological noise strings into the correct types."""
        if value is None:
            return None

        if isinstance(value, OneQubitNoiseChannel):
            return value

        if isinstance(value, dict) and all(isinstance(k, int) for k in value):
            if all(isinstance(v, OneQubitNoiseChannel) for v in value.values()):
                return cast(dict[int, OneQubitNoiseChannel], value)

            if all(isinstance(v, str) for v in value.values()):
                value = cast(dict[int, str], value)
                parsed_noise: dict[int, OneQubitNoiseChannel] = {}
                for qubit_id, noise_data in value.items():
                    parsed_noise[qubit_id] = cls._parse_noise_string(noise_data)
                return parsed_noise

        msg = f"Unrecognised phenomenological_noise format: {value}"
        raise ValueError(msg)


class ToyPhenomenologicalNoiseConfig(NamedConfiguration, frozen=True, extra="forbid"):
    """Configurations for the Riverlane toy phenomenological noise model.
    Applies OneQubitDepolarisingNoise with error rate p to all identity gates,
    and a classical bit-flip noise with probability p_measurement_flip to all
    measurements. If p_measurement_flip is not provided, it defaults to p.
    If neither parameter is set, no noise is applied.
    """

    p: float = 0.0
    """The depolarising error rate for phenomenological noise. By default, 0.0."""
    p_measurement_flip: float | None = None
    """The probability of obtaining an incorrect measurement result. By default, this
        has the same value as p."""


def _default_gate_noise_dict() -> GateNoiseDict:
    return GateNoiseDict(
        {
            gate_name: GateNoise()
            for gate_name in [*SingleQubitUnitaryEnum, *TwoQubitUnitaryEnum, *ResetEnum]
        }
    )


def phenomenological_noise_factory(noise_config: PhenomenologicalNoiseConfig) -> NoiseParameters:
    """Generate noise parameters from a phenomenological noise configuration."""
    gates = _default_gate_noise_dict()

    if isinstance(noise_config.phenomenological_noise, dict):
        for qubit, noise in noise_config.phenomenological_noise.items():
            gates.update(
                {
                    SingleQubitIdGate(SingleQubitUnitaryEnum.IDENTITY, qubit): GateNoise(
                        after=[noise]
                    )
                }
            )
    elif isinstance(noise_config.phenomenological_noise, OneQubitNoiseChannel):
        gates.update(
            {
                SingleQubitUnitaryEnum.IDENTITY: GateNoise(
                    after=[noise_config.phenomenological_noise]
                )
            }
        )

    return NoiseParameters(
        gates=gates,
        measurement=MeasurementNoise(),
        idle=NoIdleNoise(),
    )


def toy_phenomenological_noise_factory(
    noise_config: ToyPhenomenologicalNoiseConfig,
) -> NoiseParameters:
    """Generate noise parameters from a toy phenomenological noise configuration."""
    gates = _default_gate_noise_dict()

    one_qubit_noise: list[BasePauliNoise] = [OneQubitDepolarisingNoise(p=noise_config.p)]
    gates.update({SingleQubitUnitaryEnum.IDENTITY: GateNoise(after=one_qubit_noise)})

    bit_flip_p = (
        noise_config.p_measurement_flip
        if noise_config.p_measurement_flip is not None
        else noise_config.p
    )

    return NoiseParameters(
        gates=gates,
        measurement=MeasurementNoise(bit_flip_p=bit_flip_p),
        idle=NoIdleNoise(),
    )
