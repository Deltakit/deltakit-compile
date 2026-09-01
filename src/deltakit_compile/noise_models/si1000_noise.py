# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for the implementation of the SI1000 noise model:
https://arxiv.org/abs/2108.10457 and its variants."""

from collections.abc import Mapping, Sequence

from typing_extensions import override
from xdsl.ir import SSAValue

from deltakit_compile.noise_models.idle_noise import DecayIdleNoise
from deltakit_compile.noise_models.noise_parameters import (
    BaseIdleNoise,
    BasePauliNoise,
    GateNoise,
    GateNoiseDict,
    IdleTracker,
    LeakageNoise,
    MeasurementNoise,
    MeasurementNoiseDict,
    NoiseParameters,
    OneQubitDepolarisingNoise,
    OneQubitPauliNoise,
    RelaxNoise,
    TwoQubitDepolarisingNoise,
)
from deltakit_compile.passes.common.pipeline import NamedConfiguration
from deltakit_compile.shared.deltakit_stim.gates import (
    DeltakitStimQuantumOpEnum,
    MeasurementEnum,
    MPPEnum,
    ResetEnum,
    SingleQubitUnitaryEnum,
    TwoQubitUnitaryEnum,
)
from deltakit_compile.utilities.gatesets import (
    DeltakitStimQuantumGatesetKey,
    ExhaustiveGateSet,
    NativeGateSet,
)
from deltakit_compile.utilities.traverse_from_ssa import get_qubit_id


class BaseSI1000NoiseConfig(NamedConfiguration, frozen=True, extra="forbid"):
    """Base configuration for SI1000 noise model variants."""

    p: float
    """Physical error rate (all non-leakage noise is derived from this number)."""
    pL: float = 0.0  # noqa: N815
    """Leakage probability. If > 0 this noise model is extended to include the
    leakage and relaxation channels, and leakage herald error noise from the
    "SI1000 with leakage" model defined in: https://arxiv.org/pdf/2411.10343"""


class SI1000NoiseConfig(BaseSI1000NoiseConfig, frozen=True, extra="forbid"):
    """Configurations for an SI1000 noise model as given in https://arxiv.org/abs/2108.10457."""


class SI1000NoResetNoiseConfig(BaseSI1000NoiseConfig, frozen=True, extra="forbid"):
    """Configurations for an SI1000 noise model as given in
    https://arxiv.org/abs/2108.10457 but without resets after measurements.
    The before measurement noise has been split between qubit flip and classical
    measurement noise where measurement flip is happening with probability p
    and a qubit is flipped before the measurement with probability 4p/(1-2p).
    Together, these should combine to 5p probability of a measurement error."""


class SI1000WithGateTimingsNoiseConfig(BaseSI1000NoiseConfig, frozen=True, extra="forbid"):
    """Configurations for an SI1000 noise model that uses gate timings to calculate idle noise.
    This model extends the SI1000 noise model, as given in https://arxiv.org/abs/2108.10457,
    by using gate timings to find the inactive qubits to apply idle noise to at each timestep.
    """


class SI1000NoResetWithGateTimingsNoiseConfig(BaseSI1000NoiseConfig, frozen=True, extra="forbid"):
    """Configurations for an SI1000NoReset noise model that uses gate timings to calculate
    idle noise. This model extends the SI1000NoReset noise model, as given in
    https://arxiv.org/abs/2108.10457 but without resets after measurements, by using
    gate timings to find the inactive qubits to apply idle noise to at each timestep."""


class SI1000IdleNoise(BaseIdleNoise):
    """Defines idle noise based on a probability and whether any qubits were not active
    during the time step."""

    def __init__(self, p: float, pL: float) -> None:  # noqa: N803
        self.p = p
        self.pL = pL

    @override
    def from_executed_ops(
        self,
        executed_ops: Mapping[DeltakitStimQuantumOpEnum, list[int]],
        idle_qubit: int | None = None,
    ) -> list[BasePauliNoise]:
        noise: list[BasePauliNoise] = [OneQubitDepolarisingNoise(p=self.p / 10)]
        if self.pL > 0:
            noise.append(RelaxNoise(p=self.p / 5))

        return noise


class SI1000WithGateTimingsIdleNoise(BaseIdleNoise):
    """Defines idle noise based on a probability and whether any qubits were not active
    during the time step."""

    def __init__(self, p: float, pL: float) -> None:  # noqa: N803
        self.p = p
        self.pL = pL

    def _initialise_decay_idle_noise(
        self,
        native_gateset: dict[DeltakitStimQuantumGatesetKey, float]
        | list[DeltakitStimQuantumGatesetKey]
        | None,
    ) -> DecayIdleNoise:
        """Initialise DecayIdleNoise for noise models that require gate timings."""
        if isinstance(native_gateset, dict):
            # If gates and gate times are specified, use that gate set and timings.
            return DecayIdleNoise(operation_times=native_gateset)
        if isinstance(native_gateset, list):
            # If only gates are specified, use that gate set with uniform timings.
            return DecayIdleNoise(operation_times=NativeGateSet(set(native_gateset)).native_gates)
        # If no gate set information is specified,
        # use the exhaustive gate set with uniform timings.
        return DecayIdleNoise(operation_times=ExhaustiveGateSet().native_gates)

    @override
    def record_op(
        self,
        idle_tracker: IdleTracker,
        op_type: DeltakitStimQuantumOpEnum,
        targets: Sequence[SSAValue],
    ) -> None:
        """Record how the execution of an op affects idle and resonator idle qubits."""
        for target in targets:
            idle_tracker.executed_ops[op_type].append(get_qubit_id(target))
            if isinstance(op_type, (ResetEnum, MeasurementEnum, MPPEnum)):
                idle_tracker.discard_resonant_idle_qubit(target)

        decay_idle_noise = self._initialise_decay_idle_noise(
            native_gateset=idle_tracker.native_gateset
        )
        total_layer_time = decay_idle_noise.executed_ops_total_time(idle_tracker.executed_ops)
        for target in idle_tracker.all_qubits:
            qubit_total_time = decay_idle_noise.qubit_total_time(
                idle_tracker.executed_ops, get_qubit_id(target)
            )
            if total_layer_time > qubit_total_time:
                idle_tracker.add_idle_qubit(target)
            else:
                idle_tracker.discard_idle_qubit(target)

    @override
    def from_executed_ops(
        self,
        executed_ops: Mapping[DeltakitStimQuantumOpEnum, list[int]],
        idle_qubit: int | None = None,
    ) -> list[BasePauliNoise]:
        noise: list[BasePauliNoise] = [OneQubitDepolarisingNoise(p=self.p / 10)]
        if self.pL > 0:
            noise.append(RelaxNoise(p=self.p / 5))

        return noise


class SI1000ResonantIdleNoise(BaseIdleNoise):
    """Defines resonant idle noise based on a probability and whether a reset or measure were
    executed during the time step."""

    def __init__(self, p: float, pL: float) -> None:  # noqa: N803
        self.p = p
        self.pL = pL

    @override
    def from_executed_ops(
        self,
        executed_ops: Mapping[DeltakitStimQuantumOpEnum, list[int]],
        idle_qubit: int | None = None,
    ) -> list[BasePauliNoise]:
        noise: list[BasePauliNoise] = []

        if (
            any(e in executed_ops for e in ResetEnum)
            or any(e in executed_ops for e in MeasurementEnum)
            or any(e in executed_ops for e in MPPEnum)
        ):
            noise.append(OneQubitDepolarisingNoise(p=2 * self.p))
            if self.pL > 0:
                noise.append(RelaxNoise(p=4 * self.p))

        return noise


def _si1000_base_gates(p: float, pL: float) -> tuple[GateNoiseDict, float]:  # noqa: N803
    """Build the gate noise and leakage herald probability shared by all SI1000 noise models."""
    one_qubit_noise: list[BasePauliNoise] = [OneQubitDepolarisingNoise(p=p / 10)]
    two_qubit_noise: list[BasePauliNoise] = [TwoQubitDepolarisingNoise(p=p)]
    reset_x_noise: list[BasePauliNoise] = [OneQubitPauliNoise(x=2 * p)]
    reset_z_noise: list[BasePauliNoise] = [OneQubitPauliNoise(z=2 * p)]
    if pL > 0:
        one_qubit_noise.append(RelaxNoise(p=p / 5))
        two_qubit_noise.extend([LeakageNoise(p=pL), RelaxNoise(p=pL)])
        reset_x_noise.append(LeakageNoise(p=pL))
        reset_z_noise.append(LeakageNoise(p=pL))

    gates = GateNoiseDict(
        {gate_name: GateNoise(after=one_qubit_noise) for gate_name in SingleQubitUnitaryEnum}
    )
    gates.update({gate_name: GateNoise(after=two_qubit_noise) for gate_name in TwoQubitUnitaryEnum})
    gates.update({gate_name: GateNoise(after=reset_x_noise) for gate_name in ResetEnum})
    gates.update({ResetEnum.RX: GateNoise(after=reset_z_noise)})
    leakage_herald_probability = 5 * p if pL > 0 else 0.0
    return gates, leakage_herald_probability


def si1000_noise_factory(
    noise_config: SI1000NoiseConfig,
) -> NoiseParameters:
    """Generate noise parameters from an SI1000 configuration."""
    gates, leakage_herald_probability = _si1000_base_gates(noise_config.p, noise_config.pL)
    return NoiseParameters(
        gates=gates,
        measurement=MeasurementNoise(bit_flip_p=5 * noise_config.p),
        resonant_idle=SI1000ResonantIdleNoise(p=noise_config.p, pL=noise_config.pL),
        idle=SI1000IdleNoise(p=noise_config.p, pL=noise_config.pL),
        leakage_herald=leakage_herald_probability,
    )


def si1000_with_gate_timings_noise_factory(
    noise_config: SI1000WithGateTimingsNoiseConfig,
) -> NoiseParameters:
    """Generate noise parameters from an SI1000WithGateTimingsconfiguration."""
    gates, leakage_herald_probability = _si1000_base_gates(noise_config.p, noise_config.pL)
    return NoiseParameters(
        gates=gates,
        measurement=MeasurementNoise(bit_flip_p=5 * noise_config.p),
        resonant_idle=SI1000ResonantIdleNoise(p=noise_config.p, pL=noise_config.pL),
        idle=SI1000WithGateTimingsIdleNoise(p=noise_config.p, pL=noise_config.pL),
        leakage_herald=leakage_herald_probability,
    )


def si1000_no_reset_noise_factory(
    noise_config: SI1000NoResetNoiseConfig,
) -> NoiseParameters:
    """Generate noise parameters from an SI1000NoReset configuration."""
    gates, leakage_herald_probability = _si1000_base_gates(noise_config.p, noise_config.pL)
    pre_measurement_noise_probability = 4 * noise_config.p / (1 - 2 * noise_config.p)
    mmt_x_noise: list[BasePauliNoise] = [OneQubitPauliNoise(x=pre_measurement_noise_probability)]
    mmt_z_noise: list[BasePauliNoise] = [OneQubitPauliNoise(z=pre_measurement_noise_probability)]

    measurements = MeasurementNoiseDict(
        {
            gate_name: MeasurementNoise(before=mmt_x_noise, bit_flip_p=noise_config.p)
            for gate_name in MeasurementEnum
        }
    )
    measurements.update(
        {
            mx_type: MeasurementNoise(before=mmt_z_noise, bit_flip_p=noise_config.p)
            for mx_type in (MeasurementEnum.MX, MeasurementEnum.MRX)
        }
    )
    return NoiseParameters(
        gates=gates,
        measurement=measurements,
        resonant_idle=SI1000ResonantIdleNoise(p=noise_config.p, pL=noise_config.pL),
        idle=SI1000IdleNoise(p=noise_config.p, pL=noise_config.pL),
        leakage_herald=leakage_herald_probability,
    )


def si1000_no_reset_with_gate_timings_noise_factory(
    noise_config: SI1000NoResetWithGateTimingsNoiseConfig,
) -> NoiseParameters:
    """Generate noise parameters from an SI1000NoResetWithGateTimings configuration."""
    gates, leakage_herald_probability = _si1000_base_gates(noise_config.p, noise_config.pL)
    pre_measurement_noise_probability = 4 * noise_config.p / (1 - 2 * noise_config.p)
    mmt_x_noise: list[BasePauliNoise] = [OneQubitPauliNoise(x=pre_measurement_noise_probability)]
    mmt_z_noise: list[BasePauliNoise] = [OneQubitPauliNoise(z=pre_measurement_noise_probability)]

    measurements = MeasurementNoiseDict(
        {
            gate_name: MeasurementNoise(before=mmt_x_noise, bit_flip_p=noise_config.p)
            for gate_name in MeasurementEnum
        }
    )
    measurements.update(
        {
            mx_type: MeasurementNoise(before=mmt_z_noise, bit_flip_p=noise_config.p)
            for mx_type in (MeasurementEnum.MX, MeasurementEnum.MRX)
        }
    )
    return NoiseParameters(
        gates=gates,
        measurement=measurements,
        resonant_idle=SI1000ResonantIdleNoise(p=noise_config.p, pL=noise_config.pL),
        idle=SI1000WithGateTimingsIdleNoise(p=noise_config.p, pL=noise_config.pL),
        leakage_herald=leakage_herald_probability,
    )
