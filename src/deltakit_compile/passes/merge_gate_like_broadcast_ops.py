# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Pass to merge qstruct.parallel ops into broadcast qref gate-like ops if possible.

Style mirrors the split pass: a helper to extract per-region gate, then one
rewrite pattern per gate type that attempts the merge.
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ArrayAttr, Float64Type, FloatAttr, ModuleOp
from xdsl.ir import Operation, SSAValue
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    GreedyRewritePatternApplier,
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.utils.hints import isa

from deltakit_compile.dialects import qcore, qref, qstruct
from deltakit_compile.passes.stim._common import (
    copy_stim_tag_from_ops,
)


def _extract_parallel_ops(
    op: qstruct.ParallelOp,
) -> list[qref.GateLikeOp] | None:
    """Extract gate ops from each `qstruct.parallel` region.

    Returns None if any region does not contain exactly a qref gate-like op followed by the
    qstruct.yield terminator.
    """
    extracted: list[qref.GateLikeOp] = []
    for r in op.par_regions:
        ops_in_block = r.block.ops
        if len(ops_in_block) != 2:
            return None
        # Second op must be the yield terminator by verification in the dialect
        gate, _ = ops_in_block
        if not isinstance(gate, qref.GateLikeOp):
            return None
        extracted.append(gate)
    return extracted


def _make_parallel_op_rewrite(
    regions: list[qref.GateLikeOp],
    op: Operation,
    ssa_map: list[SSAValue],
    rewriter: PatternRewriter,
) -> None:
    """Helper to convert a list of gate ops into a parallel op ensuring
    ops are detached from any existing parent before re-use."""
    for child in regions:
        if child.parent_op() is not None:
            child.detach()
    if len(regions) == 1:
        rewriter.replace_op(op, regions[0], ssa_map)
    else:
        parallel_op = qstruct.make_parallel_from_ops(regions)
        for result in parallel_op.res:
            if (arg := parallel_op.result_to_yield_arg(result)) in ssa_map:
                ssa_map[ssa_map.index(arg)] = result
        rewriter.replace_op(op, parallel_op, ssa_map)


def _get_all_qubits(gates: Iterable[qref.GateLikeOp]) -> list[SSAValue[qcore.QubitType]]:
    """Helper to extract all qubits from a list of gates."""
    return [
        qubit
        for gate in gates
        for qubit_group in gate.qubit_operand_groups
        for qubit in qubit_group
    ]


KeyT = TypeVar("KeyT")


class _MergePattern(RewritePattern, ABC, Generic[KeyT]):
    """A generic RewritePattern that merges qstruct.parallel regions of gates if possible.

    Parallel regions containing single gates with the same key (as determined by `_extract_key`) are
    merged using `_make_broadcast_gate`. Other regions are left as-is.
    """

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.ParallelOp, rewriter: PatternRewriter) -> None:
        """If possible, rewrite `op` by merging identical regions into a broadcast gate, or grouped
        `qstruct.parallel` regions when multiple gate groups remain. Otherwise, no rewrite is
        performed."""
        gate_dict = defaultdict[KeyT, list[qref.GateLikeOp]](list)
        regions: list[qref.GateLikeOp] = []
        ssa_map: list[SSAValue] = [op.result_to_yield_arg(result) for result in op.res]
        """Map each result to the op it came from, maintaining the index order of op."""

        extracted = _extract_parallel_ops(op)
        if extracted is None:
            return

        for gate in extracted:
            # The key must match exactly for gates to be merged
            if (key := self._extract_key(gate)) is not None:
                gate_dict[key].append(gate)
            else:
                regions.append(gate)

        has_gates_to_merge: bool = False
        for key, gates in gate_dict.items():
            if len(gates) > 1:
                output_indices = [
                    (ssa_map.index(result) if result in ssa_map else None)
                    for op in gates
                    for result in op.results
                ]
                merged = self._make_broadcast_gate(key, gates)
                for output_index, result in zip(output_indices, merged.results, strict=True):
                    if output_index is not None:
                        ssa_map[output_index] = result
                copy_stim_tag_from_ops(
                    gates,
                    merged,
                    "Multiple gates are merged into one broadcast gate, so only one stim tag can "
                    "be preserved",
                )
                regions.append(merged)
                has_gates_to_merge = True
            else:
                # Keep single gate as-is
                regions.append(gates[0])

        if has_gates_to_merge:
            _make_parallel_op_rewrite(regions, op, ssa_map, rewriter)

    @abstractmethod
    def _extract_key(self, gate: qref.GateLikeOp) -> KeyT | None:
        """Extract the key for merging gates of this type into a single broadcast gates, or None if
        the gate should not be merged (e.g. it is of the wrong type)."""

    @abstractmethod
    def _make_broadcast_gate(self, key: KeyT, gates: list[qref.GateLikeOp]) -> qref.GateLikeOp:
        """Create a broadcast gate combining the given gates, all of which have the same key."""


class _MergeGateOpsPattern(_MergePattern[qcore.GateAttribute]):
    """RewritePattern that merges qstruct.parallel regions of qref.gate ops."""

    @override
    def _extract_key(self, gate: qref.GateLikeOp) -> qcore.GateAttribute | None:
        if isinstance(gate, qref.GateOp):
            return gate.gate
        return None

    @override
    def _make_broadcast_gate(
        self, key: qcore.GateAttribute, gates: list[qref.GateLikeOp]
    ) -> qref.GateLikeOp:
        return qref.GateOp(gate=key, qubits=_get_all_qubits(gates))


class _MergeMeasurementOpsPattern(_MergePattern[FloatAttr[Float64Type]]):
    """RewritePattern that merges qstruct.parallel regions of qref.measure ops based on the noise.

    Measurements with different Pauli bases are merged.
    """

    @override
    def _extract_key(self, gate: qref.GateLikeOp) -> FloatAttr[Float64Type] | None:
        if isinstance(gate, qref.MeasureOp):
            return gate.noise
        return None

    @override
    def _make_broadcast_gate(
        self,
        key: FloatAttr[Float64Type],
        gates: list[qref.GateLikeOp],
    ) -> qref.GateLikeOp:
        assert isa(gates, list[qref.MeasureOp])
        paulis = self._extract_paulis(gates)
        paulis_attr = ArrayAttr(ArrayAttr(pauli_string) for pauli_string in paulis)
        return qref.MeasureOp(paulis=paulis_attr, qubits=_get_all_qubits(gates), noise=key)

    def _extract_paulis(self, gates: list[qref.MeasureOp]) -> list[Sequence[qcore.PauliAttr]]:
        """Helper to extract the Pauli bases from a list of measurement gates."""
        return [pauli.data for gate in gates for pauli in gate.paulis]


class _MergeResetOpsPattern(_MergePattern[qcore.PauliAttr]):
    """RewritePattern that merges qstruct.parallel regions of qref.reset ops."""

    @override
    def _extract_key(self, gate: qref.GateLikeOp) -> qcore.PauliAttr | None:
        if isinstance(gate, qref.ResetOp):
            return gate.basis
        return None

    @override
    def _make_broadcast_gate(
        self, key: qcore.PauliAttr, gates: list[qref.GateLikeOp]
    ) -> qref.GateLikeOp:
        return qref.ResetOp(basis=key, qubits=_get_all_qubits(gates))


@dataclass(frozen=True)
class MergeGateLikeBroadcastOps(ModulePass):
    """Pass that converts qstruct.ParallelOp regions into broadcast gates if possible."""

    name = "merge-gate-like-broadcast-ops"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [
                    _MergeGateOpsPattern(),
                    _MergeMeasurementOpsPattern(),
                    _MergeResetOpsPattern(),
                ]
            ),
            apply_recursively=True,
        ).rewrite_module(op)
