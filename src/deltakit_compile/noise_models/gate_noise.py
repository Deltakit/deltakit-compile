# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for the implementation of the gate-based device-specific noise model"""

from dataclasses import field
from typing import cast

from pydantic import field_validator

from deltakit_compile.noise_models.idle_noise import DecayIdleNoise, DecoherenceTime
from deltakit_compile.noise_models.no_noise import no_noise_factory
from deltakit_compile.noise_models.noise_parameters import (
    BasePauliNoise,
    DeltakitStimGateKey,
    DeltakitStimQuantumGatesetKey,
    GateNoise,
    IdMeasurement,
    MeasurementEnum,
    MeasurementKey,
    MeasurementNoise,
    MeasurementNoiseDict,
    NoiseParameters,
    OneQubitDepolarisingNoise,
    OneQubitPauliNoise,
    ResetEnum,
    SingleQubitIdGate,
    TwoQubitDepolarisingNoise,
    TwoQubitIdGate,
    TwoQubitPauliNoise,
)
from deltakit_compile.passes.common.pipeline import NamedConfiguration
from deltakit_compile.shared.deltakit_stim.gates import (
    SingleQubitUnitaryEnum,
    TwoQubitUnitaryEnum,
)


class GateNoiseConfig(NamedConfiguration, frozen=True, extra="forbid"):
    """Configurations for a gate-based noise model."""

    initialisation: dict[int, list[BasePauliNoise]] = field(default_factory=dict)
    gates: dict[DeltakitStimGateKey, GateNoise] = field(default_factory=dict)
    measurement: MeasurementNoise | dict[MeasurementKey, MeasurementNoise] = field(
        default_factory=MeasurementNoise
    )
    decay: DecoherenceTime | dict[int, DecoherenceTime] = field(default_factory=DecoherenceTime)
    operation_times: dict[DeltakitStimQuantumGatesetKey, float] = field(default_factory=dict)

    @staticmethod
    def _parse_gate_name(gate_name: str) -> DeltakitStimGateKey:
        """The name should be "<gate> <target1> <target2>..."""
        gate_name_sep = gate_name.split(" ")
        gate_name_str = gate_name_sep[0]

        gate: DeltakitStimGateKey
        if SingleQubitUnitaryEnum.contains(gate_name_str):
            gate = SingleQubitUnitaryEnum[gate_name_str]
        elif TwoQubitUnitaryEnum.contains(gate_name_str):
            gate = TwoQubitUnitaryEnum[gate_name_str]
        elif ResetEnum.contains(gate_name_str):
            gate = ResetEnum[gate_name_str]
        else:
            msg = f"Unrecognised gate name: {gate_name}"
            raise ValueError(msg)

        if len(gate_name_sep) == 1:
            return gate
        if len(gate_name_sep) == 2:
            # check if a single qubit gate
            if not isinstance(gate, SingleQubitUnitaryEnum) and not isinstance(gate, ResetEnum):
                msg = f"Unrecognised gate name: {gate_name}"
                raise ValueError(msg)
            return SingleQubitIdGate(gate, int(gate_name_sep[1]))
        return TwoQubitIdGate(
            cast(TwoQubitUnitaryEnum, gate), (int(gate_name_sep[1]), int(gate_name_sep[2]))
        )

    @staticmethod
    def _parse_measurement_name(measurement_name: str) -> MeasurementKey:
        """The name should be "<gate> <target1> <target2>..."""
        measurement_name_sep = measurement_name.split(" ")
        measurement_str = measurement_name_sep[0]
        if not MeasurementEnum.contains(measurement_str):
            msg = f"Unrecognised measurement name: {measurement_name}"
            raise ValueError(msg)
        measurement = MeasurementEnum[measurement_str]
        if len(measurement_name_sep) == 1:
            return measurement
        if len(measurement_name_sep) == 2:
            return IdMeasurement(measurement, int(measurement_name_sep[1]))
        msg = f"Unrecognised measurement name: {measurement_name}"
        raise ValueError(msg)

    @staticmethod
    def _parse_pauli_noise(pauli_noises: list[str]) -> list[BasePauliNoise]:
        result: list[BasePauliNoise] = []
        for noise in pauli_noises:
            noise_split = noise.split(" ")
            noise_name = noise_split[0]
            parameters = (float(v) for v in noise_split[1:])
            match noise_name:
                case "OneQubitDepolarisingNoise":
                    result.append(OneQubitDepolarisingNoise(*parameters))
                case "TwoQubitDepolarisingNoise":
                    result.append(TwoQubitDepolarisingNoise(*parameters))
                case "OneQubitPauliNoise":
                    result.append(OneQubitPauliNoise(*parameters))
                case "TwoQubitPauliNoise":
                    result.append(TwoQubitPauliNoise(*parameters))
                case _:
                    msg = f"Unrecognised noise: {noise_name}"
                    raise ValueError(msg)
        return result

    @staticmethod
    def _parse_gate_noise(gate_noise: dict[str, list[str]]) -> GateNoise:
        before, after = [], []
        if (pauli_noise := gate_noise.get("before")) is not None:
            before = GateNoiseConfig._parse_pauli_noise(pauli_noise)
        if (pauli_noise := gate_noise.get("after")) is not None:
            after = GateNoiseConfig._parse_pauli_noise(pauli_noise)
        return GateNoise(before=before, after=after)

    @staticmethod
    def _parse_measurement_noise(gate_noise_dict: dict) -> MeasurementNoise:
        bit_flip_p = float(gate_noise_dict.get("bit_flip_p", 0.0))
        gate_noise = GateNoiseConfig._parse_gate_noise(gate_noise_dict)
        return MeasurementNoise(
            before=gate_noise.before, after=gate_noise.after, bit_flip_p=bit_flip_p
        )

    @field_validator("initialisation", mode="before")
    @classmethod
    def parse_initialisation(
        cls,
        value: dict[int, list[BasePauliNoise]] | dict[int, list[str]],
    ) -> dict[int, list[BasePauliNoise]]:
        """Parse input initialisation noise strings into the correct types."""
        if all(
            isinstance(pauli_noises, list)
            and all(isinstance(pauli_noise, BasePauliNoise) for pauli_noise in pauli_noises)
            for pauli_noises in value.values()
        ) and all(isinstance(k, int) for k in value):
            return cast(dict[int, list[BasePauliNoise]], value)
        value = cast(dict[int, list[str]], value)
        initialisation_noise: dict[int, list[BasePauliNoise]] = {}
        for qubit_id, pauli_noises in value.items():
            initialisation_noise[qubit_id] = GateNoiseConfig._parse_pauli_noise(pauli_noises)
        return initialisation_noise

    @field_validator("gates", mode="before")
    @classmethod
    def parse_gates(
        cls, value: dict[DeltakitStimGateKey, GateNoise] | dict[str, dict[str, list[str]]]
    ) -> dict[DeltakitStimGateKey, GateNoise]:
        """Parse input gate noise strings into the correct types."""
        if all(isinstance(g, GateNoise) for g in value.values()):
            return cast(dict[DeltakitStimGateKey, GateNoise], value)
        value = cast(dict[str, dict[str, list[str]]], value)
        # assumes gates are in a stringified format
        gates = {}
        for gate_name, noise in value.items():
            gate = GateNoiseConfig._parse_gate_name(gate_name)
            gates[gate] = GateNoiseConfig._parse_gate_noise(noise)
        return gates

    @field_validator("measurement", mode="before")
    @classmethod
    def parse_measurement(
        cls,
        value: MeasurementNoise
        | dict[MeasurementKey, MeasurementNoise]
        | dict[str, dict[str, list[str]]],
    ) -> dict[MeasurementKey, MeasurementNoise]:
        """Parse input measurement noise strings into the correct types."""
        if isinstance(value, MeasurementNoise) or all(
            isinstance(g, MeasurementNoise) for g in value.values()
        ):
            return cast(dict[MeasurementKey, MeasurementNoise], value)
        value = cast(dict[str, dict[str, list[str]]], value)
        measurement_dict = {}
        for measurement_name, noise in value.items():
            measurement = GateNoiseConfig._parse_measurement_name(measurement_name)
            measurement_dict[measurement] = GateNoiseConfig._parse_measurement_noise(noise)
        return measurement_dict

    @staticmethod
    def _parse_operation_name(op_name: str) -> DeltakitStimGateKey | MeasurementKey:
        """Parse the operation name to a DeltakitStimGateKey or MeasurementKey."""
        try:
            return GateNoiseConfig._parse_gate_name(op_name)
        except ValueError:
            pass
        try:
            return GateNoiseConfig._parse_measurement_name(op_name)
        except ValueError:
            pass
        msg = f"Unrecognised operation name: {op_name}"
        raise ValueError(msg)

    @field_validator("operation_times", mode="before")
    @classmethod
    def parse_operation_times(
        cls, value: dict[DeltakitStimQuantumGatesetKey, float] | dict[str, float]
    ) -> dict[DeltakitStimQuantumGatesetKey, float]:
        """Associate operation times with the correct operation type enums."""
        if all(
            isinstance(gate, DeltakitStimQuantumGatesetKey) and isinstance(time, float)
            for gate, time in value.items()
        ):
            return cast(dict[DeltakitStimQuantumGatesetKey, float], value)
        value = cast(dict[str, float], value)
        return {
            GateNoiseConfig._parse_operation_name(op_name): time for op_name, time in value.items()
        }


def gate_noise_factory(noise_config: GateNoiseConfig) -> NoiseParameters:
    """Generate noise parameters from a gate noise configuration."""
    # unspecified gates and measurements are set to no noise
    noise = no_noise_factory()
    gates = noise.gates
    if noise_config.gates is not None:
        gates.update(noise_config.gates)
    measurement: MeasurementNoise | MeasurementNoiseDict
    match noise_config.measurement:
        case MeasurementNoise():
            measurement = noise_config.measurement
        case None:
            measurement = noise.measurement
        case _:
            measurement = MeasurementNoiseDict()
            measurement.update({mmt_name: MeasurementNoise() for mmt_name in MeasurementEnum})
            measurement.update(noise_config.measurement)
    idle_noise = DecayIdleNoise(
        decay_spec=noise_config.decay, operation_times=noise_config.operation_times
    )
    return NoiseParameters(
        initialisation=noise_config.initialisation,
        gates=gates,
        measurement=measurement,
        idle=idle_noise,
    )
