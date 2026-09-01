# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module containing a pass that adds noise to IR formed of the stim and deltakit-stim dialects."""

import warnings
from abc import ABC
from collections import defaultdict
from collections.abc import Sequence
from typing import cast

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import Float64Type, FloatAttr, ModuleOp, f64
from xdsl.ir import SSAValue
from xdsl.pattern_rewriter import (
    GreedyRewritePatternApplier,
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.rewriter import InsertPoint

from deltakit_compile.dialects.deltakit_stim import HeraldLeakageEventOp
from deltakit_compile.dialects.stim import (
    CliffordGateOp,
    GateOp,
    MeasurementGateOp,
    MultiPauliProductMeasurementOp,
    NoiseOp,
    QubitAllocOp,
    ResetGateOp,
    TickAnnotationOp,
)
from deltakit_compile.noise_models.noise_factory import NoiseConfig, noise_param_factory
from deltakit_compile.noise_models.noise_parameters import (
    DEFAULT_QUBIT_ID,
    BaseIdleNoise,
    BasePauliNoise,
    GateNoise,
    GateNoiseDict,
    IdleTracker,
    IdMeasurement,
    MeasurementNoise,
    MeasurementNoiseSpec,
    SingleQubitIdGate,
    TwoQubitIdGate,
)
from deltakit_compile.passes.common.pipeline import (
    ConfigurablePass,
    Configuration,
    NamedConfigurations,
    configurable_pass,
)
from deltakit_compile.shared.deltakit_stim.gates import (
    MeasurementEnum,
    MPPEnum,
    ResetEnum,
    SingleQubitUnitaryEnum,
    TwoQubitUnitaryEnum,
)
from deltakit_compile.utilities.gatesets import DeltakitStimQuantumGatesetKey
from deltakit_compile.utilities.traverse_from_ssa import get_qubit_id


class _AddOpNoisePattern(RewritePattern, ABC):
    """Base class for rewrite patterns that add noise for a specific op type."""

    @classmethod
    def _insert_gate_noise(
        cls, gate_noise: GateNoise, targets: Sequence[SSAValue], rewriter: PatternRewriter
    ) -> None:
        """Insert gate noise before and after an op."""
        rewriter.insert_op(
            [noise.to_stim_op(targets) for noise in gate_noise.before],
            InsertPoint.before(rewriter.current_operation),
        )
        rewriter.insert_op(
            [noise.to_stim_op(targets) for noise in gate_noise.after],
            InsertPoint.after(rewriter.current_operation),
        )


class _AddInitNoisePattern(_AddOpNoisePattern):
    """Add initialisation noise before any gates."""

    def __init__(
        self, init_noise: dict[int, list[BasePauliNoise]], all_qubits: set[SSAValue]
    ) -> None:
        self.init_noise = init_noise
        self._all_qubits = all_qubits
        self._applied = len(self.init_noise) == 0

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: GateOp, rewriter: PatternRewriter) -> None:
        if self._applied:
            return
        self._applied = True
        generic_init_noise = self.init_noise.get(DEFAULT_QUBIT_ID)
        unprocessed_qubits: dict[int, SSAValue] = {}
        for qubit in self._all_qubits:
            qubit_id = get_qubit_id(qubit)
            if (target_init_noise := self.init_noise.get(qubit_id)) is not None and len(
                target_init_noise
            ) > 0:
                rewriter.insert_op(
                    [noise.to_stim_op([qubit]) for noise in target_init_noise],
                    InsertPoint.before(rewriter.current_operation),
                )
            else:
                unprocessed_qubits[qubit_id] = qubit
        if not generic_init_noise:
            return
        # sort for deterministic behaviour
        for _, qubit in sorted(unprocessed_qubits.items()):
            if len(generic_init_noise) > 0:
                rewriter.insert_op(
                    [noise.to_stim_op([qubit]) for noise in generic_init_noise],
                    InsertPoint.before(rewriter.current_operation),
                )


class _AddGateNoisePattern(_AddOpNoisePattern):
    """Add noise before and after gates."""

    def __init__(
        self,
        gate_noise_dict: GateNoiseDict,
        idle_noise: BaseIdleNoise,
        idle_tracker: IdleTracker,
    ) -> None:
        self.gate_noise_dict = gate_noise_dict
        self.idle_noise = idle_noise
        self.idle_tracker = idle_tracker

    def _apply_single_qubit_noise(
        self,
        gate_type: SingleQubitUnitaryEnum | ResetEnum,
        targets: Sequence[SSAValue],
        rewriter: PatternRewriter,
    ) -> None:
        remaining_targets = []
        for target in targets:
            target_id = get_qubit_id(target)
            if (
                gate_noise := self.gate_noise_dict.get(SingleQubitIdGate(gate_type, target_id))
            ) is not None:
                self._insert_gate_noise(gate_noise, [target], rewriter)
            else:
                remaining_targets.append(target)
        if remaining_targets:
            gate_noise = self.gate_noise_dict[gate_type]
            self._insert_gate_noise(gate_noise, remaining_targets, rewriter)

    def _apply_two_qubit_noise(
        self, gate_type: TwoQubitUnitaryEnum, targets: Sequence[SSAValue], rewriter: PatternRewriter
    ) -> None:
        remaining_targets = []
        for target1, target2 in zip(targets[::2], targets[1::2], strict=False):
            id1, id2 = get_qubit_id(target1), get_qubit_id(target2)
            if (
                gate_noise := self.gate_noise_dict.get(TwoQubitIdGate(gate_type, (id1, id2)))
            ) is not None:
                self._insert_gate_noise(gate_noise, [target1, target2], rewriter)
            # check if symmetric channel defined - prefer that one over generic
            elif (
                gate_noise := self.gate_noise_dict.get(TwoQubitIdGate(gate_type, (id2, id1)))
            ) is not None:
                self._insert_gate_noise(gate_noise, [target2, target1], rewriter)
            else:
                remaining_targets.append(target1)
                remaining_targets.append(target2)
        if remaining_targets:
            gate_noise = self.gate_noise_dict[gate_type]
            self._insert_gate_noise(gate_noise, remaining_targets, rewriter)

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: CliffordGateOp, rewriter: PatternRewriter) -> None:
        gate_type = op.gate_type.data
        match gate_type:
            case SingleQubitUnitaryEnum():
                self._apply_single_qubit_noise(gate_type, op.targets, rewriter)
            case TwoQubitUnitaryEnum():
                self._apply_two_qubit_noise(gate_type, op.targets, rewriter)
        self.idle_noise.record_op(self.idle_tracker, gate_type, op.targets)


class _AddResetNoisePattern(_AddGateNoisePattern):
    """Add noise before and after reset gates."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: ResetGateOp, rewriter: PatternRewriter) -> None:
        reset_name = ResetEnum["R" + op.pauli_modifier.data]
        self._apply_single_qubit_noise(reset_name, op.targets, rewriter)
        self.idle_noise.record_op(self.idle_tracker, reset_name, op.targets)


class _BaseMeasurementNoisePattern(_AddOpNoisePattern):
    """Base class for measurement noise rewrite patterns.

    Args:
        meas_noise: Measurement noise specification (uniform or per-qubit/measurement).
        idle_noise: Idle noise model for recording executed ops, idle and resonant idle qubits.
        idle_tracker: Tracker for idle and resonant idle qubits and executed operations.
    """

    def __init__(
        self,
        meas_noise: MeasurementNoiseSpec,
        idle_noise: BaseIdleNoise,
        idle_tracker: IdleTracker,
    ) -> None:
        self.meas_noise = meas_noise
        self.idle_noise = idle_noise
        self.idle_tracker = idle_tracker
        self.replacement_warning_thrown = False

    def _warn_if_overwriting(self, op) -> None:
        if op.noise is not None and not self.replacement_warning_thrown:
            warnings.warn(
                "Adding measurement noise to measurements that are already noisy",
                UserWarning,
                stacklevel=2,
            )
            self.replacement_warning_thrown = True

    def _get_meas_noise(self, mmt_name: MeasurementEnum, target: SSAValue) -> MeasurementNoise:
        if isinstance(self.meas_noise, MeasurementNoise):
            return self.meas_noise
        return (
            self.meas_noise.get(IdMeasurement(mmt_name, get_qubit_id(target)))
            or self.meas_noise[mmt_name]
        )

    @staticmethod
    def _noise_attr(bit_flip_p: float) -> FloatAttr[Float64Type] | None:
        return (
            cast(FloatAttr[Float64Type], FloatAttr(bit_flip_p, f64)) if bit_flip_p != 0.0 else None
        )

    @staticmethod
    def _get_xor_of_independent_bit_flips(bit_flip_ps: Sequence[float]) -> float:
        # The XOR of independent bit flips satisfies \prod_i (1 - 2*p_i) = 1 - 2*p_eff.
        # Rearranging gives p_eff = (1 - \prod_i (1 - 2*p_i)) / 2.
        if not bit_flip_ps:
            return 0.0
        prod_term = 1.0
        for p in bit_flip_ps:
            prod_term *= 1.0 - 2.0 * p
        return (1.0 - prod_term) / 2.0


class _AddMeasurementNoisePattern(_BaseMeasurementNoisePattern):
    """Add noise before and after measurements and bit flip probability."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: MeasurementGateOp, rewriter: PatternRewriter) -> None:
        self._warn_if_overwriting(op)

        mmt_name = MeasurementEnum["M" + op.pauli_modifier.data]

        # Uniform noise
        if isinstance(self.meas_noise, MeasurementNoise):
            self._insert_gate_noise(self.meas_noise, op.targets, rewriter)
            new_op = MeasurementGateOp(
                targets=op.targets,
                pauli_modifier=op.pauli_modifier,
                noise=self._noise_attr(self.meas_noise.bit_flip_p),
            )
            rewriter.replace_op(op, new_op, new_op.results)
            self.idle_noise.record_op(self.idle_tracker, mmt_name, op.targets)
            return

        # Dict-based noise → split per target
        new_ops = []
        new_results: list[SSAValue] = []

        for target in op.targets:
            meas_noise = self._get_meas_noise(mmt_name, target)
            self._insert_gate_noise(meas_noise, [target], rewriter)
            mmt_op = MeasurementGateOp(
                targets=[target],
                pauli_modifier=op.pauli_modifier,
                noise=self._noise_attr(meas_noise.bit_flip_p),
            )

            new_results.extend(mmt_op.results)
            new_ops.append(mmt_op)

        rewriter.replace_op(op, new_ops, new_results)
        self.idle_noise.record_op(self.idle_tracker, mmt_name, op.targets)


class _AddMPPNoisePattern(_BaseMeasurementNoisePattern):
    """Add noise before and after MPP measurements and bit flip probability."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(
        self, op: MultiPauliProductMeasurementOp, rewriter: PatternRewriter
    ) -> None:
        self._warn_if_overwriting(op)

        # Add the MPP operation to the idle tracker.
        self.idle_noise.record_op(self.idle_tracker, MPPEnum.MPP, op.targets)

        bit_flip_ps: list[float] = []

        # Noise is added to each target qubit before/after the MPP
        # based on the measurement performed on that qubit.
        for pauli, target in zip(op.pauli_modifiers, op.targets, strict=True):
            mmt_name = MeasurementEnum["M" + pauli.data]
            meas_noise_final = self._get_meas_noise(mmt_name, target)

            self._insert_gate_noise(meas_noise_final, [target], rewriter)
            bit_flip_ps.append(meas_noise_final.bit_flip_p)

        # Classical measurement flip probability of the MPP is
        # the classical measurement flip probability of a measurement
        # if there is uniform bit flip probability for all measurements.
        if len(set(bit_flip_ps)) == 1:
            new_op = MultiPauliProductMeasurementOp(
                targets=op.targets,
                pauli_modifiers=op.pauli_modifiers.data,
                noise=self._noise_attr(bit_flip_ps[0]),
            )
            rewriter.replace_op(op, new_op, [new_op.readout])
            return

        # The classical measurement flip probability of the MPP is
        # the XOR of the individual measurement flip probabilities
        # if there is non-uniform noise across measurements.
        eff_bit_flip = self._get_xor_of_independent_bit_flips(bit_flip_ps)
        new_op = MultiPauliProductMeasurementOp(
            targets=op.targets,
            pauli_modifiers=op.pauli_modifiers.data,
            noise=self._noise_attr(eff_bit_flip),
        )
        rewriter.replace_op(op, new_op, [new_op.readout])


class _AddHeraldsNoisePattern(RewritePattern):
    """Add noise to a herald leakage event."""

    def __init__(self, leakage_herald_noise: float) -> None:
        self.leakage_herald_noise = leakage_herald_noise

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(
        self,
        op: HeraldLeakageEventOp,
        rewriter: PatternRewriter,
    ) -> None:
        herald_op = HeraldLeakageEventOp(op.targets, self.leakage_herald_noise)
        rewriter.replace_op(op, herald_op)


class _AddIdleNoisePattern(RewritePattern):
    """Add idle noise on every time step."""

    def __init__(
        self,
        idle_noise: BaseIdleNoise,
        resonant_idle_noise: BaseIdleNoise,
        idle_tracker: IdleTracker,
    ) -> None:
        self.idle_noise = idle_noise
        self.resonant_idle_noise = resonant_idle_noise
        self.idle_tracker = idle_tracker

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: TickAnnotationOp, rewriter: PatternRewriter) -> None:
        if len(self.idle_tracker.idle_qubits) + len(self.idle_tracker.resonant_idle_qubits) == 0:
            self.idle_noise.reset(self.idle_tracker)
            return
        noise_ops: defaultdict[BasePauliNoise, list[SSAValue]] = defaultdict(list)
        for target in self.idle_tracker.all_idle_qubits:
            target_noise_ops: list[BasePauliNoise] = []
            if target in self.idle_tracker.resonant_idle_qubits:
                target_noise_ops.extend(
                    self.resonant_idle_noise.from_executed_ops(
                        self.idle_tracker.executed_ops, idle_qubit=get_qubit_id(target)
                    )
                )
            if target in self.idle_tracker.idle_qubits:
                target_noise_ops.extend(
                    self.idle_noise.from_executed_ops(
                        self.idle_tracker.executed_ops, idle_qubit=get_qubit_id(target)
                    )
                )
            # try to concatenate idle noises to be multi-target
            for target_noise_op in target_noise_ops:
                if (noise_op := noise_ops.get(target_noise_op)) is None:
                    noise_ops[target_noise_op] = [target]
                else:
                    noise_op.append(target)

        rewriter.insert_op(
            [noise.to_stim_op(targets) for noise, targets in noise_ops.items()],
            InsertPoint.before(rewriter.current_operation),
        )
        self.idle_noise.reset(self.idle_tracker)


class _CheckExistingNoisePattern(RewritePattern):
    """Throw a warning if noise was already present in the circuit before adding any."""

    def __init__(self) -> None:
        self.warning_thrown = False

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: NoiseOp, rewriter: PatternRewriter) -> None:
        if not self.warning_thrown:
            warnings.warn(
                "Adding noise to a circuit that already contains noise", UserWarning, stacklevel=1
            )
            self.warning_thrown = True


class AddNoiseConfig(Configuration, frozen=True):
    noise_model: NamedConfigurations[NoiseConfig]
    native_gateset: (
        dict[DeltakitStimQuantumGatesetKey, float] | list[DeltakitStimQuantumGatesetKey] | None
    ) = None


@configurable_pass
class AddNoise(ConfigurablePass[AddNoiseConfig]):
    """Pass for adding noise to IR formed of the stim and deltakit-stim dialects.
    When adding noise to multi-Pauli product measurements, we do the following:
    1. Assume the noise on each target is what it would be if they were measured separately.
    2. Take the XOR of the individual bit flip probabilities as the MPP bit flip probability.
    """

    name = "add-noise"
    noise_model: str | NamedConfigurations[NoiseConfig]
    native_gateset: (
        dict[DeltakitStimQuantumGatesetKey, float] | list[DeltakitStimQuantumGatesetKey] | None
    ) = None
    # The native_gateset can either or be given as a list of gates,
    # a dictionary of gates and their times, or not given at all (None).

    @classmethod
    def _get_all_qubits(cls, module_op: ModuleOp) -> set[SSAValue]:
        """Get all declared qubits in the circuit."""
        qubits: set[SSAValue] = set()
        for opn in module_op.walk():
            if isinstance(opn, QubitAllocOp):
                qubits.add(opn.res)

        return qubits

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        assert not isinstance(self.noise_model, str)  # Guaranteed by ConfigurablePass
        noise_parameters = noise_param_factory(self.noise_model)
        all_qubits = self._get_all_qubits(op)
        idle_tracker = IdleTracker(all_qubits, self.native_gateset)

        # separate pass for the init noise
        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [
                    _CheckExistingNoisePattern(),
                    _AddInitNoisePattern(noise_parameters.initialisation, all_qubits),
                ]
            ),
            apply_recursively=False,
        ).rewrite_module(op)
        # all other noise
        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [
                    _AddGateNoisePattern(
                        noise_parameters.gates, noise_parameters.idle, idle_tracker
                    ),
                    _AddResetNoisePattern(
                        noise_parameters.gates, noise_parameters.idle, idle_tracker
                    ),
                    _AddMeasurementNoisePattern(
                        noise_parameters.measurement, noise_parameters.idle, idle_tracker
                    ),
                    _AddMPPNoisePattern(
                        noise_parameters.measurement, noise_parameters.idle, idle_tracker
                    ),
                    _AddIdleNoisePattern(
                        noise_parameters.idle, noise_parameters.resonant_idle, idle_tracker
                    ),
                    _AddHeraldsNoisePattern(noise_parameters.leakage_herald),
                ]
            ),
            apply_recursively=False,
        ).rewrite_module(op)
