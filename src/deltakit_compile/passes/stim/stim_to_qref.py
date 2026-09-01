# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Lowers Stim dialect to qref dialect."""

import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp, UnrealizedConversionCastOp
from xdsl.ir import SSAValue
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    GreedyRewritePatternApplier,
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.utils.hints import isa

from deltakit_compile.dialects import qcore, qref, stim
from deltakit_compile.dialects.qcore import (
    CXGateAttr,
    CYGateAttr,
    CZGateAttr,
    GateAttribute,
    HGateAttr,
    IdentityGateAttr,
    ISWAPGateAttr,
    SGateAttr,
    SqrtXXGateAttr,
    SqrtYYGateAttr,
    SqrtZZGateAttr,
    SWAPGateAttr,
    XGateAttr,
    YGateAttr,
    ZGateAttr,
)
from deltakit_compile.dialects.stim import TAG_ATTR
from deltakit_compile.exceptions import LostStimTagWarning
from deltakit_compile.passes.stim._common import copy_stim_tag
from deltakit_compile.shared.deltakit_stim.gates import (
    DeltakitStimGateEnum,
    SingleQubitUnitaryEnum,
    TwoQubitUnitaryEnum,
)

# Mapping from Stim gate enum to qcore gate attribute
_STIM_TO_QCORE_GATE_MAPPING: Final[dict[DeltakitStimGateEnum, GateAttribute]] = {
    SingleQubitUnitaryEnum.IDENTITY: IdentityGateAttr(),
    SingleQubitUnitaryEnum.X: XGateAttr(),
    SingleQubitUnitaryEnum.SQRT_X: XGateAttr.sqrt(),
    SingleQubitUnitaryEnum.SQRT_X_DAG: XGateAttr.sqrt_dag(),
    SingleQubitUnitaryEnum.Y: YGateAttr(),
    SingleQubitUnitaryEnum.SQRT_Y: YGateAttr.sqrt(),
    SingleQubitUnitaryEnum.SQRT_Y_DAG: YGateAttr.sqrt_dag(),
    SingleQubitUnitaryEnum.Z: ZGateAttr(),
    SingleQubitUnitaryEnum.H: HGateAttr(),
    SingleQubitUnitaryEnum.S: SGateAttr(),
    SingleQubitUnitaryEnum.S_DAG: SGateAttr.dag(),
    TwoQubitUnitaryEnum.SQRT_XX: SqrtXXGateAttr(),
    TwoQubitUnitaryEnum.SQRT_XX_DAG: SqrtXXGateAttr.dag(),
    TwoQubitUnitaryEnum.SQRT_YY: SqrtYYGateAttr(),
    TwoQubitUnitaryEnum.SQRT_YY_DAG: SqrtYYGateAttr.dag(),
    TwoQubitUnitaryEnum.SQRT_ZZ: SqrtZZGateAttr(),
    TwoQubitUnitaryEnum.SQRT_ZZ_DAG: SqrtZZGateAttr.dag(),
    TwoQubitUnitaryEnum.CNOT: CXGateAttr(),
    TwoQubitUnitaryEnum.CY: CYGateAttr(),
    TwoQubitUnitaryEnum.CZ: CZGateAttr(),
    TwoQubitUnitaryEnum.SWAP: SWAPGateAttr(),
    TwoQubitUnitaryEnum.ISWAP: ISWAPGateAttr(),
    TwoQubitUnitaryEnum.ISWAP_DAG: ISWAPGateAttr.dag(),
    TwoQubitUnitaryEnum.CX: CXGateAttr(),
}

_STIM_PAULI_TO_QCORE_PAULI: Final[dict[stim.PauliOperatorEnum, qcore.PauliAttr]] = {
    stim.PauliOperatorEnum.X: qcore.PauliAttr.X(),
    stim.PauliOperatorEnum.Y: qcore.PauliAttr.Y(),
    stim.PauliOperatorEnum.Z: qcore.PauliAttr.Z(),
}


def _stim_enum_to_qcore_gate(
    gate: DeltakitStimGateEnum,
) -> GateAttribute:
    """Map a Stim gate enum to its corresponding qcore gate attribute."""
    if gate in _STIM_TO_QCORE_GATE_MAPPING:
        return _STIM_TO_QCORE_GATE_MAPPING[gate]

    msg = f"Unsupported stim gate enum: {gate}. Cannot convert to qcore gate."
    raise NotImplementedError(msg)


def _cast_stim_qubits(qubits: Sequence[SSAValue], rewriter: PatternRewriter) -> list[SSAValue]:
    """Cast a sequence of !stim.qubit SSAValues to !qcore.qubit via unrealized conversion casts."""
    result: list[SSAValue] = []
    for qubit in qubits:
        if not isa(qubit.owner, UnrealizedConversionCastOp):
            cast_op, _ = UnrealizedConversionCastOp.cast_one(qubit, qcore.QubitType())
            rewriter.insert_op(cast_op)
            result.append(cast_op.results[0])
        else:
            result.append(qubit.owner.inputs[0])
    return result


class _GatePattern(RewritePattern):
    """Convert stim.CliffordGateOp to qref.GateOp."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stim.CliffordGateOp, rewriter: PatternRewriter) -> None:
        """Handle gate operations."""
        gate = _stim_enum_to_qcore_gate(op.gate_type.data)

        rewriter.replace_op(
            op,
            new_op := qref.GateOp(
                gate,
                _cast_stim_qubits(op.targets, rewriter),
            ),
        )
        copy_stim_tag(op, new_op)


class _ResetPattern(RewritePattern):
    """Convert stim.ResetGateOp to qref.ResetOp."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stim.ResetGateOp, rewriter: PatternRewriter) -> None:
        """Handle reset operations."""
        rewriter.replace_op(
            op,
            new_op := qref.ResetOp(
                _STIM_PAULI_TO_QCORE_PAULI[op.pauli_modifier.data],
                _cast_stim_qubits(op.targets, rewriter),
            ),
        )
        copy_stim_tag(op, new_op)


class _MeasurePattern(RewritePattern):
    """Convert stim.MeasurementGateOp to qref.MeasureOp."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stim.MeasurementGateOp, rewriter: PatternRewriter) -> None:
        """Handle measurement operations."""
        pauli = _STIM_PAULI_TO_QCORE_PAULI[op.pauli_modifier.data]
        noise = op.noise.value.data if op.noise else 0.0
        rewriter.replace_op(
            op,
            new_op := qref.MeasureOp(pauli, _cast_stim_qubits(op.targets, rewriter), noise),
        )
        copy_stim_tag(op, new_op)


class _MultiPauliMeasurePattern(RewritePattern):
    """Convert stim.MultiPauliProductMeasurementOp to qref.MultiPauliMeasureOp."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(
        self, op: stim.MultiPauliProductMeasurementOp, rewriter: PatternRewriter
    ) -> None:
        """Handle multi-qubit Pauli measurement operations."""
        paulis = [_STIM_PAULI_TO_QCORE_PAULI[pauli.data] for pauli in op.pauli_modifiers.data]
        noise = op.noise.value.data if op.noise else 0.0
        rewriter.replace_op(
            op,
            new_op := qref.MeasureOp(paulis, _cast_stim_qubits(op.targets, rewriter), noise),
        )
        copy_stim_tag(op, new_op)


class _Depolarize1Pattern(RewritePattern):
    """Convert stim.Depolarize1Op to qref.PauliNoiseOp with uniform 1-qubit depolarizing noise."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stim.Depolarize1Op, rewriter: PatternRewriter) -> None:
        """Handle single-qubit depolarization operations."""
        rewriter.replace_op(
            op,
            new_op := qref.PauliNoiseOp(
                qcore.PauliNoiseParametersAttr.depolarise(1, op.probability.data),
                _cast_stim_qubits(op.targets, rewriter),
            ),
        )
        copy_stim_tag(op, new_op)


class _Depolarize2Pattern(RewritePattern):
    """Convert stim.Depolarize2Op to qref.PauliNoiseOp with uniform 2-qubit depolarizing noise."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stim.Depolarize2Op, rewriter: PatternRewriter) -> None:
        """Handle two-qubit depolarization operations."""
        rewriter.replace_op(
            op,
            new_op := qref.PauliNoiseOp(
                qcore.PauliNoiseParametersAttr.depolarise(2, op.probability.data),
                _cast_stim_qubits(op.targets, rewriter),
            ),
        )
        copy_stim_tag(op, new_op)


class _PauliChannel1Pattern(RewritePattern):
    """Convert stim.PauliChannel1Op to qref.PauliNoiseOp."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stim.PauliChannel1Op, rewriter: PatternRewriter) -> None:
        """Handle single-qubit Pauli channel operations."""
        rewriter.replace_op(
            op,
            new_op := qref.PauliNoiseOp(
                qcore.PauliNoiseParametersAttr.single_pauli(
                    op.probability_x.data,
                    op.probability_y.data,
                    op.probability_z.data,
                ),
                _cast_stim_qubits(op.targets, rewriter),
            ),
        )
        copy_stim_tag(op, new_op)


class _PauliChannel2Pattern(RewritePattern):
    """Convert stim.PauliChannel2Op to qref.PauliNoiseOp."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stim.PauliChannel2Op, rewriter: PatternRewriter) -> None:
        """Handle two-qubit Pauli channel operations."""
        rewriter.replace_op(
            op,
            new_op := qref.PauliNoiseOp(
                qcore.PauliNoiseParametersAttr.two_pauli(*op.get_probabilities()),
                _cast_stim_qubits(op.targets, rewriter),
            ),
        )
        copy_stim_tag(op, new_op)


class _CorrelatedErrorPattern(RewritePattern):
    """Convert a stim.CorrelatedErrorOp chain (with any following ElseCorrelatedErrorOps)
    to a single qref.PauliNoiseOp.

    The forward pass (qref→stim) encodes absolute probabilities as conditional probabilities:
        cond_prob_n = abs_prob_n / probability_left_n
    So the inverse recovers:
        abs_prob_n = cond_prob_n * probability_left_n
        probability_left_{n+1} = probability_left_n - abs_prob_n
    """

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stim.CorrelatedErrorOp, rewriter: PatternRewriter) -> None:
        """Handle a CorrelatedErrorOp and any following ElseCorrelatedErrorOps as one unit."""
        # Collect the full chain: CorrelatedErrorOp + consecutive ElseCorrelatedErrorOps
        chain: list[stim.CorrelatedErrorBaseOp] = [op]
        next_op = op.next_op
        while isinstance(next_op, stim.ElseCorrelatedErrorOp):
            chain.append(next_op)
            next_op = next_op.next_op

        # Collect all unique qubits across the chain, preserving order of first appearance
        seen: set[SSAValue] = set()
        all_qubits = []
        for chain_op in chain:
            for qubit in chain_op.targets:
                if qubit not in seen:
                    seen.add(qubit)
                    all_qubits.append(qubit)

        qubit_to_idx = {q: i for i, q in enumerate(all_qubits)}

        # Reconstruct absolute probabilities from conditional probabilities
        pauli_strings_dict: dict[Sequence[qcore.PauliAttr | None], float] = {}
        probability_left = 1.0
        for chain_op in chain:
            abs_prob = chain_op.probability.data * probability_left
            probability_left -= abs_prob
            # Build the full Pauli string; qubits absent from this op are identity (None)
            pauli_string: list[qcore.PauliAttr | None] = [None] * len(all_qubits)
            for pauli_attr, qubit in zip(chain_op.paulis.data, chain_op.targets, strict=True):
                pauli_string[qubit_to_idx[qubit]] = _STIM_PAULI_TO_QCORE_PAULI[pauli_attr.data]
            pauli_strings_dict[tuple(pauli_string)] = abs_prob

        noise_params = qcore.PauliNoiseParametersAttr.from_pauli_strings_dict(pauli_strings_dict)

        # Erase the consumed ElseCorrelatedErrorOps (in reverse to avoid ordering issues)
        for else_op in reversed(chain[1:]):
            rewriter.erase_op(else_op)

        rewriter.replace_op(
            op, new_op := qref.PauliNoiseOp(noise_params, _cast_stim_qubits(all_qubits, rewriter))
        )
        copy_stim_tag(op, new_op)

        if any(else_op.attributes.get(TAG_ATTR) is not None for else_op in chain[1:]):
            warnings.warn(
                "One or more CorrelatedErrorOps in this chain have stim tags. They have not been "
                "copied to the resulting qref.PauliNoiseOp and have been dropped.",
                LostStimTagWarning,
                stacklevel=2,
            )


@dataclass(frozen=True)
class StimToQref(ModulePass):
    """Pass that lowers Stim dialect operations to the qref dialect.

    It converts Stim gate, reset, measurement and noise operations to their qref equivalents.
    Qubit allocation (stim.QubitAllocOp → qcore.AllocQubitOp) is handled separately
    by the StimToQcore pass and should be run before this pass.
    """

    name = "stim-to-qref"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [
                    _GatePattern(),
                    _ResetPattern(),
                    _MeasurePattern(),
                    _MultiPauliMeasurePattern(),
                    _Depolarize1Pattern(),
                    _Depolarize2Pattern(),
                    _PauliChannel1Pattern(),
                    _PauliChannel2Pattern(),
                    _CorrelatedErrorPattern(),
                ],
                dce_enabled=True,
            )
        ).rewrite_module(op)
