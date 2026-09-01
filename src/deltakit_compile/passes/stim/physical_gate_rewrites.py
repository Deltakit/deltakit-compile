# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Shared rewrite patterns for lowering physical operations to Stim dialect."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final, Literal, overload

from typing_extensions import override
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Operation, SSAValue, SSAValues
from xdsl.pattern_rewriter import PatternRewriter, RewritePattern, op_type_rewrite_pattern
from xdsl.rewriter import InsertPoint

from deltakit_compile.dialects import qcore, qref, qstruct, stim
from deltakit_compile.dialects.ncstim import (
    NonCliffordGateEnum,
    NonCliffordGateOp,
    RotationGateOp,
    U3GateOp,
)
from deltakit_compile.exceptions import StimUnsupportedGate
from deltakit_compile.passes.stim._common import copy_stim_tag, warn_stim_tag_lost
from deltakit_compile.shared.deltakit_stim.gates import (
    DeltakitStimGateEnum,
    SingleQubitUnitaryEnum,
    TwoQubitUnitaryEnum,
)

_QCORE_PAULI_TO_STIM_PAULI: Final[dict[qcore.PauliAttr, stim.PauliOperatorEnum]] = {
    qcore.PauliAttr.X(): stim.PauliOperatorEnum.X,
    qcore.PauliAttr.Y(): stim.PauliOperatorEnum.Y,
    qcore.PauliAttr.Z(): stim.PauliOperatorEnum.Z,
}

# Mapping from (gate_type, options_tuple) to Deltakit-Stim gate enum
_QCORE_TO_STIM_GATE_MAPPING: Final[dict[qcore.GateAttribute, DeltakitStimGateEnum]] = {
    qcore.IdentityGateAttr(): SingleQubitUnitaryEnum.IDENTITY,
    qcore.XGateAttr(): SingleQubitUnitaryEnum.X,
    qcore.XGateAttr.sqrt(): SingleQubitUnitaryEnum.SQRT_X,
    qcore.XGateAttr.sqrt_dag(): SingleQubitUnitaryEnum.SQRT_X_DAG,
    qcore.YGateAttr(): SingleQubitUnitaryEnum.Y,
    qcore.YGateAttr.sqrt(): SingleQubitUnitaryEnum.SQRT_Y,
    qcore.YGateAttr.sqrt_dag(): SingleQubitUnitaryEnum.SQRT_Y_DAG,
    qcore.ZGateAttr(): SingleQubitUnitaryEnum.Z,
    qcore.HGateAttr(): SingleQubitUnitaryEnum.H,
    qcore.SGateAttr(): SingleQubitUnitaryEnum.S,
    qcore.SGateAttr.dag(): SingleQubitUnitaryEnum.S_DAG,
    qcore.SqrtXXGateAttr(): TwoQubitUnitaryEnum.SQRT_XX,
    qcore.SqrtXXGateAttr.dag(): TwoQubitUnitaryEnum.SQRT_XX_DAG,
    qcore.SqrtYYGateAttr(): TwoQubitUnitaryEnum.SQRT_YY,
    qcore.SqrtYYGateAttr.dag(): TwoQubitUnitaryEnum.SQRT_YY_DAG,
    qcore.SqrtZZGateAttr(): TwoQubitUnitaryEnum.SQRT_ZZ,
    qcore.SqrtZZGateAttr.dag(): TwoQubitUnitaryEnum.SQRT_ZZ_DAG,
    qcore.CXGateAttr(): TwoQubitUnitaryEnum.CNOT,
    qcore.CYGateAttr(): TwoQubitUnitaryEnum.CY,
    qcore.CZGateAttr(): TwoQubitUnitaryEnum.CZ,
    qcore.SWAPGateAttr(): TwoQubitUnitaryEnum.SWAP,
    qcore.ISWAPGateAttr(): TwoQubitUnitaryEnum.ISWAP,
    qcore.ISWAPGateAttr.dag(): TwoQubitUnitaryEnum.ISWAP_DAG,
}


# Cannot return None if raise_on_unsupported is True
@overload
def qcore_gate_to_deltakit_stim_enum(
    gate: qcore.GateAttribute, raise_on_unsupported: Literal[True] = True
) -> DeltakitStimGateEnum: ...


@overload
def qcore_gate_to_deltakit_stim_enum(
    gate: qcore.GateAttribute, raise_on_unsupported: bool = True
) -> DeltakitStimGateEnum | None: ...


def qcore_gate_to_deltakit_stim_enum(
    gate: qcore.GateAttribute, raise_on_unsupported: bool = True
) -> DeltakitStimGateEnum | None:
    """Map a qcore gate attribute to its corresponding Deltakit-Stim gate enum.

    Args:
        gate: A StandardGateAttribute representing a qcore gate.
        raise_on_unsupported: If True (the default), raises StimUnsupportedGate if the gate cannot
            be mapped to a Deltakit-Stim enum. If False, returns None for unsupported gates.


    Returns:
        The corresponding Deltakit-Stim gate enum value OR None if the gate is unsupported and
        `raise_on_unsupported` is False.

    Raises:
        StimUnsupportedGate: If the gate cannot be mapped to a Deltakit-Stim enum and
            `raise_on_unsupported` is True.
    """
    if gate in _QCORE_TO_STIM_GATE_MAPPING:
        return _QCORE_TO_STIM_GATE_MAPPING[gate]

    if raise_on_unsupported:
        msg = f"Cannot map qcore gate {gate.short_str()} to Deltakit-Stim enum"
        raise StimUnsupportedGate(msg)
    return None


# Named qcore gates with a dedicated, fixed-identity ncstim opcode that stim itself has no
# equivalent for (unlike e.g. X or CX, T/T_DAG/CCX/CCZ/CH are non-Clifford, so they're never in
# qcore_gate_to_lestim_enum's gate set).
_STANDARD_GATE_TO_NON_CLIFFORD: Final[dict[qcore.GateAttribute, NonCliffordGateEnum]] = {
    qcore.TGateAttr(): NonCliffordGateEnum.T,
    qcore.TGateAttr.dag(): NonCliffordGateEnum.T_DAG,
    qcore.CCXGateAttr(): NonCliffordGateEnum.CCX,
    qcore.CCZGateAttr(): NonCliffordGateEnum.CCZ,
    qcore.CHGateAttr(): NonCliffordGateEnum.CH,
}


_NCSTIM_OP = stim.CliffordGateOp | NonCliffordGateOp | RotationGateOp | U3GateOp


# Cannot return None if raise_on_unsupported is True
@overload
def qcore_gate_to_ncstim_op(
    gate: qcore.GateAttribute,
    qubits: Sequence[SSAValue],
    raise_on_unsupported: Literal[True] = True,
) -> _NCSTIM_OP: ...


@overload
def qcore_gate_to_ncstim_op(
    gate: qcore.GateAttribute,
    qubits: Sequence[SSAValue],
    raise_on_unsupported: bool = True,
) -> _NCSTIM_OP | None: ...


def qcore_gate_to_ncstim_op(
    gate: qcore.GateAttribute,
    qubits: Sequence[SSAValue],
    raise_on_unsupported: bool = True,
) -> _NCSTIM_OP | None:
    """Map a qcore gate attribute to a physical operation, covering the lestim plus ncstim
    instructions to pass to ``GatePattern``.

    Gates already representable in plain stim (X, H, S, CX, SWAP, ...) are tried first, via
    ``qcore_gate_to_lestim_enum``: an X gate should always come out as a plain lestim ``X``, never
    as an ncstim rotation, even though the latter is also a valid representation. Only gates lestim
    can't represent progress through ncstim's own forms, tried in increasing generality (most
    specific first):

    1. Named non-Clifford gates with a dedicated, fixed-identity ncstim opcode (T, T_DAG, CCX,
       CCZ, CH) map to ``NonCliffordGateOp`` via ``_STANDARD_GATE_TO_NON_CLIFFORD``.
    2. ``qcore.RotationGateAttr`` (an arbitrary Pauli-string + angle with no fixed identity of its
       own) maps directly to ``RotationGateOp``, both settled on the same shape.
    3. Any remaining single-qubit gate maps to ``U3GateOp`` via a matrix decomposition (see
       ``qcore.UnitaryGateAttr.matrix_to_u3_angles``), since U3's three angles can represent any
       single-qubit unitary.

    Args:
        gate: A qcore gate attribute.
        qubits: The target qubit(s) the gate acts on.
        raise_on_unsupported: If True (default), raises StimUnsupportedGate if the gate cannot
            be mapped to a tsim/clifft instruction. If False, returns None for unsupported gates.

    Returns:
        An operation equivalent to ``gate``, or ``None`` if there is no tsim/clifft equivalent and
        `raise_on_unsupported` is False.

    Raises:
        StimUnsupportedGate: If the gate cannot be mapped to a tsim/clifft instruction (e.g.
            arbitrary multi-qubit unitary synthesis) and `raise_on_unsupported` is True.
    """
    if (
        lestim_enum := qcore_gate_to_deltakit_stim_enum(gate, raise_on_unsupported=False)
    ) is not None:
        return stim.CliffordGateOp(lestim_enum, qubits)

    if (non_clifford_gate := _STANDARD_GATE_TO_NON_CLIFFORD.get(gate)) is not None:
        return NonCliffordGateOp(non_clifford_gate, qubits)

    if isinstance(gate, qcore.RotationGateAttr):
        pauli_modifiers = [
            stim.PauliAttr(_QCORE_PAULI_TO_STIM_PAULI[pauli]) for pauli in gate.pauli_string
        ]
        return RotationGateOp(pauli_modifiers, gate.angle, qubits)

    if gate.get_qubit_count() == 1:
        theta, phi, lam = qcore.UnitaryGateAttr.matrix_to_u3_angles(gate.get_unitary_matrix())
        return U3GateOp(theta, phi, lam, qubits)

    if raise_on_unsupported:
        msg = f"Cannot map qcore gate {gate.short_str()} to a tsim/clifft instruction"
        raise StimUnsupportedGate(msg)
    return None


@dataclass(frozen=True)
class InlineCircuitPattern(RewritePattern):
    """Inline the body of a qstruct.circuit op, replacing the circuit's results with the results of
    the YieldOp in the inlined body."""

    pass_name_context: str = ""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.CircuitOp, rewriter: PatternRewriter) -> None:
        warn_stim_tag_lost(
            op,
            (
                f"{self.pass_name_context + ': ' if self.pass_name_context else ''}"
                "Stim tag on qstruct.circuit was lost because it was inlined."
            ),
        )
        yield_op = op.body.block.last_op
        assert isinstance(yield_op, qstruct.YieldOp)
        rewriter.inline_block(op.body.block, InsertPoint.before(op), op.args)
        rewriter.replace_op(op, [], yield_op.arguments)
        rewriter.erase_op(yield_op)


def get_existing_qubit_ids(module: ModuleOp) -> set[int]:
    """Get the set of existing qubit IDs in the module, to avoid assigning duplicate ids when
    lowering qubit allocs."""
    existing_ids: set[int] = set()
    for op in module.walk():
        if isinstance(op, qcore.AllocQubitOp) and op.ids is not None:
            for qubit_id in op.ids:
                if qubit_id.data in existing_ids:
                    msg = (
                        f"Duplicate qubit id {qubit_id.data} found. "
                        "Please ensure that all qubits have unique ids."
                    )
                    op.emit_error(msg, ValueError(msg))
                existing_ids.add(qubit_id.data)

    return existing_ids


class AllocQubitPattern(RewritePattern):
    """Lower qcore.AllocQubitOp to stim operations.

    Requires a set of used qubit ids to avoid assigning duplicate ids when lowering qubit allocs.
    You can use `get_existing_qubit_ids` to identify which ids are already in use."""

    def __init__(self, used_qubit_ids: set[int]) -> None:
        self._used_qubit_ids = used_qubit_ids
        self._last_free_qubit_id: int = -1

    def _get_next_free_qubit_id(self) -> int:
        self._last_free_qubit_id += 1
        while self._last_free_qubit_id in self._used_qubit_ids:
            self._last_free_qubit_id += 1
        return self._last_free_qubit_id

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qcore.AllocQubitOp, rewriter: PatternRewriter) -> None:
        """Handle allocation of qubits."""
        if any(isinstance(result.type, qcore.QubitRegType) for result in op.results):
            msg = "Rewriting `qcore.AllocQubitOp`s which produce qubit registers is not supported."
            raise NotImplementedError(msg)

        new_allocs: list[SSAValue] = []
        for i in range(op.qubit_count()):
            stim_alloc = rewriter.insert_op(
                stim.QubitAllocOp(
                    op.ids.data[i] if op.ids else self._get_next_free_qubit_id(),
                ),
                InsertPoint.before(op),
            )
            rewriter.replace_all_uses_with(op.result[i], stim_alloc.res)
            copy_stim_tag(op, stim_alloc)
            new_allocs.append(stim_alloc.res)
        if op.coords:
            for coord, qubit in zip(op.coords.data, new_allocs, strict=True):
                rewriter.insert_op(
                    stim.QubitCoordsOp(
                        [qubit],
                        stim.QubitMappingAttr(list(coord.data)),
                    ),
                    InsertPoint.before(op),
                )

        rewriter.erase_op(op)


def _make_clifford_gate_op(
    gate: qcore.GateAttribute, qubits: SSAValues[SSAValue]
) -> stim.CliffordGateOp:
    """Create a `stim.CliffordGateOp` from a supported `qcore.GateAttribute` and a list of operand
    qubits."""
    return stim.CliffordGateOp(qcore_gate_to_deltakit_stim_enum(gate), qubits)


CONVERSION_FUNC_TYPE = Callable[[qcore.GateAttribute, SSAValues[SSAValue]], Operation | None]


@dataclass(frozen=True)
class GatePattern(RewritePattern):
    """Lower `qref.GateOp` to Deltakit-Stim-like-string printable operations
    (e.g., `stim.CliffordGateOp`).

    Attributes:
        conversion_func: A custom gate conversion function (taking a `qcore.GateAttribute` and qubit
            SSAs to operate on) which returns an `Operation` to replace `qref.GateOp`s. Can
            raise on unsupported gates, or return `None` to mean that no rewrite should be
            performed. Defaults to converting supported gates to `stim.CliffordGateOp`, raising
            `StimUnsupportedGate` if a gate is not supported in Deltakit-Stim.
    """

    conversion_func: CONVERSION_FUNC_TYPE = _make_clifford_gate_op

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qref.GateOp, rewriter: PatternRewriter) -> None:
        """Handle gate operations."""
        if (new_op := self.conversion_func(op.gate, op.qubits)) is not None:
            rewriter.replace_op(op, new_op)
            copy_stim_tag(op, new_op)


class ResetPattern(RewritePattern):
    """Lower qref.ResetOp to stim operations."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qref.ResetOp, rewriter: PatternRewriter) -> None:
        """Handle reset operations."""
        rewriter.replace_op(
            op,
            new_op := stim.ResetGateOp(op.qubits, _QCORE_PAULI_TO_STIM_PAULI[op.basis]),
        )
        copy_stim_tag(op, new_op)


class MeasurePattern(RewritePattern):
    """Lower qref.MeasureOp to stim operations."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qref.MeasureOp, rewriter: PatternRewriter) -> None:
        """Handle measurement operations."""
        new_ops: list[stim.MeasurementGateOp | stim.MultiPauliProductMeasurementOp] = []

        # Maps single-qubit Paulis to a tuple of (qubits, indices in results) for measurements
        single_qubit_measures: dict[qcore.PauliAttr, tuple[list[SSAValue], list[int]]] = {
            qcore.PauliAttr.X(): ([], []),
            qcore.PauliAttr.Y(): ([], []),
            qcore.PauliAttr.Z(): ([], []),
        }

        new_results: list[SSAValue | None] = [None] * len(op.results)

        for i, (paulis, qubit_group) in enumerate(
            zip(op.paulis, op.qubit_operand_groups, strict=True)
        ):
            if len(paulis) == 1:
                qubits, indices = single_qubit_measures[paulis.data[0]]
                qubits.extend(qubit_group)
                indices.append(i)
            else:
                stim_paulis = [_QCORE_PAULI_TO_STIM_PAULI[p] for p in paulis.data]
                new_ops.append(
                    new_mpp_op := stim.MultiPauliProductMeasurementOp(
                        qubit_group,
                        stim_paulis,
                        op.noise if op.noise.value.data != 0.0 else None,
                    )
                )
                new_results[i] = new_mpp_op.readout

        for pauli, (qubits, indices) in single_qubit_measures.items():
            if qubits:
                new_ops.append(
                    new_m_op := stim.MeasurementGateOp(
                        qubits,
                        _QCORE_PAULI_TO_STIM_PAULI[pauli],
                        op.noise if op.noise.value.data != 0.0 else None,
                    )
                )
                for i, res in zip(indices, new_m_op.readouts, strict=True):
                    new_results[i] = res
        rewriter.replace_op(op, new_ops, new_results)
        for new_op in new_ops:
            copy_stim_tag(op, new_op)


class PauliNoisePattern(RewritePattern):
    """Lower qref.PauliNoiseOp to stim operations."""

    def _handle_rank1_noise(self, op: qref.PauliNoiseOp, rewriter: PatternRewriter) -> None:
        """Handle rank 1 noise (single qubit noise)."""
        probs = op.probabilities.tensor.get_values()[1:]
        # Check if all non-identity probabilities are equal (depolarizing channel)
        new_op: stim.Depolarize1Op | stim.PauliChannel1Op
        if len(set(probs)) == 1:
            # Depolarizing channel: p_total = p_X + p_Y + p_Z = 3 * p_X
            rewriter.replace_op(
                op,
                new_op := stim.Depolarize1Op(op.qubits, sum(probs)),
            )
        else:
            rewriter.replace_op(
                op,
                new_op := stim.PauliChannel1Op(
                    op.qubits,
                    probs,
                ),
            )
        copy_stim_tag(op, new_op)

    def _handle_rank2_noise(self, op: qref.PauliNoiseOp, rewriter: PatternRewriter) -> None:
        """Handle rank 2 noise (two qubit noise)."""
        probs = op.probabilities.tensor.get_values()[1:]
        # Check if all non-identity probabilities are equal (depolarizing channel)
        new_op: stim.Depolarize2Op | stim.PauliChannel2Op
        if len(set(probs)) == 1:
            # Depolarizing channel: p_total = p_IX + p_IY + p_IZ + p_XI + p_XX + ... = 15 * p_IX
            rewriter.replace_op(
                op,
                new_op := stim.Depolarize2Op(op.qubits, sum(probs)),
            )
        else:
            rewriter.replace_op(
                op,
                new_op := stim.PauliChannel2Op(
                    op.qubits,
                    probs,
                ),
            )
        copy_stim_tag(op, new_op)

    def _handle_higher_rank_noise(self, op: qref.PauliNoiseOp, rewriter: PatternRewriter) -> None:
        """Handle noise of rank > 2 (correlated noise)."""
        noise: type[stim.CorrelatedErrorOp | stim.ElseCorrelatedErrorOp] = stim.CorrelatedErrorOp
        new_ops: list[stim.CorrelatedErrorOp | stim.ElseCorrelatedErrorOp] = []
        pauli_map = op.probabilities.get_pauli_map()
        rank = op.probabilities.qubit_count()
        qubit_count = len(op.qubits)

        identity = tuple(None for _ in range(rank))
        if identity in pauli_map:
            del pauli_map[identity]

        for start_idx in range(0, qubit_count, rank):
            noise = stim.CorrelatedErrorOp
            probability_left = 1.0
            for paulis, prob in pauli_map.items():
                qubits = [op.qubits[start_idx + i] for i in range(rank) if paulis[i]]
                pauli_arr = [_QCORE_PAULI_TO_STIM_PAULI[pauli] for pauli in paulis if pauli]
                new_ops.append(
                    noise(
                        qubits,
                        pauli_arr,
                        prob / probability_left,
                    )
                )
                probability_left -= prob
                noise = stim.ElseCorrelatedErrorOp

        rewriter.replace_op(op, new_ops)
        for new_op in new_ops:
            copy_stim_tag(op, new_op)

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qref.PauliNoiseOp, rewriter: PatternRewriter) -> None:
        """Handle Pauli noise operations."""
        rank = op.probabilities.qubit_count()
        if rank == 1:
            self._handle_rank1_noise(op, rewriter)
        elif rank == 2:
            self._handle_rank2_noise(op, rewriter)
        else:
            self._handle_higher_rank_noise(op, rewriter)


def get_physical_gate_rewrite_patterns(
    used_qubit_ids: set[int],
    gate_conversion_func: CONVERSION_FUNC_TYPE = _make_clifford_gate_op,
) -> list[RewritePattern]:
    """Get the rewrite patterns for lowering physical operations (mainly qref, e.g. gates, noise,
    resets) to stim dialect.

    Args:
        used_qubit_ids: The set of IDs that have already been assigned to qubits, so shouldn't be
            used when assigning IDs to qubits without them. You can use `get_existing_qubit_ids`.
        gate_conversion_func: See `GatePattern` above.

    Returns:
        A list of rewrite patterns for lowering physical operations to stim dialect.
    """
    return [
        AllocQubitPattern(used_qubit_ids),
        GatePattern(gate_conversion_func),
        ResetPattern(),
        MeasurePattern(),
        PauliNoisePattern(),
    ]
