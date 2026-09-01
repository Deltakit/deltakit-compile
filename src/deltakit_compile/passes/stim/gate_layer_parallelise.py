# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module containing a pass that attempts to parallelise gate layers in a deltakit-stim program"""

from collections.abc import Callable

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Attribute, Block, SSAValue, dataclass
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.rewriter import InsertPoint

from deltakit_compile.dialects.qref import (
    GateLikeOp,
    PauliNoiseOp,
)
from deltakit_compile.dialects.qstruct import CircuitOp, ParallelOp, YieldOp


@dataclass
class _GateLayer:
    """Class that stores noise and gate-like operations that will be in the same parallel region."""

    gate_first: bool
    before_noise_op: PauliNoiseOp | None
    gate_op: GateLikeOp | None = None
    after_noise_op: PauliNoiseOp | None = None

    def __post_init__(self) -> None:
        self.add_op_fn: Callable[[GateLikeOp | PauliNoiseOp], bool] = (
            self._add_op_gate_first if self.gate_first else self._add_op_noise_first
        )

    def get_yield_op(self) -> YieldOp:
        return YieldOp(*self.gate_op.results) if self.gate_op else YieldOp()

    def get_return_types(self) -> list[Attribute]:
        return list(self.gate_op.result_types) if self.gate_op is not None else []

    def get_ops(self) -> list[GateLikeOp | PauliNoiseOp | YieldOp]:
        ops: list[GateLikeOp | PauliNoiseOp | YieldOp] = (
            [self.before_noise_op] if self.before_noise_op is not None else []
        )
        if self.gate_op is not None:
            ops.append(self.gate_op)
        if self.after_noise_op is not None:
            ops.append(self.after_noise_op)
        ops.append(self.get_yield_op())
        return ops

    def _add_op_gate_first(self, op: GateLikeOp | PauliNoiseOp) -> bool:
        if isinstance(op, GateLikeOp):
            if self.gate_op is not None:
                return False
            self.gate_op = op
            return True
        if self.after_noise_op is not None:
            return False
        self.after_noise_op = op
        return True

    def _add_op_noise_first(self, op: GateLikeOp | PauliNoiseOp) -> bool:
        if isinstance(op, GateLikeOp):
            if self.gate_op is not None:
                return False
            self.gate_op = op
            return True
        if self.gate_op is None:
            return False
        if self.after_noise_op is not None:
            return False
        self.after_noise_op = op
        return True

    def add_op(self, op: GateLikeOp | PauliNoiseOp) -> bool:
        return self.add_op_fn(op)

    def get_qubits(self) -> set[SSAValue]:
        assert self.before_noise_op or self.gate_op, (
            "Expected at least a gate or noise operation in a layer"
        )
        if self.before_noise_op:
            return set(self.before_noise_op.operands)
        assert self.gate_op is not None
        return set(self.gate_op.operands)


class _CircuitWalker:
    """Helper class to walk through a circuit and parallelises the circuit"""

    def __init__(self) -> None:
        self.layers_to_parallelise: list[_GateLayer] = []
        self.qubits_seen: set[SSAValue] = set()

    def _add_parallel_op_for_layer(
        self, insert_point: InsertPoint, rewriter: PatternRewriter
    ) -> None:
        """Adds an operation to the current layer of operations to parallelise, and updates
        the set of seen qubits."""
        if len(self.layers_to_parallelise) == 0:
            return
        if len(self.layers_to_parallelise) == 1:
            ops = self.layers_to_parallelise[0].get_ops()
            for op in ops[:-1]:
                rewriter.insert_op(op, insert_point)
            if len(ops) > 0:
                rewriter.erase_op(ops[-1])
        else:
            rewriter.insert_op(
                par_op := ParallelOp(
                    result_types=[
                        operand_type
                        for layer in self.layers_to_parallelise
                        for operand_type in layer.get_return_types()
                    ],
                    par_regions=[Block(layer.get_ops()) for layer in self.layers_to_parallelise],
                ),
                insert_point,
            )
            for result in par_op.results:
                rewriter.replace_all_uses_with(
                    par_op.result_to_yield_arg(result),
                    result,
                )
            for par_region, layer in zip(
                par_op.par_regions, self.layers_to_parallelise, strict=True
            ):
                assert par_region.block.last_op, (
                    "Expected ParallelOp region to have a YieldOp as the last operation"
                )
                rewriter.replace_op(par_region.block.last_op, layer.get_yield_op())
        self.layers_to_parallelise.clear()
        self.qubits_seen.clear()

    def walk_circuit(self, circuit: CircuitOp, rewriter: PatternRewriter) -> None:
        """Walks through the operations in a circuit and parallelises them."""
        for op in circuit.walk():
            added = False
            insert_point = InsertPoint.before(op)
            if isinstance(op, (GateLikeOp, PauliNoiseOp)):
                if self.layers_to_parallelise and self.layers_to_parallelise[
                    -1
                ].get_qubits() == set(op.operands):
                    # share the same qubits - try to add to the current layer
                    added = self.layers_to_parallelise[-1].add_op(op)
                    if not added:
                        # if can't add then parallelise the current layer before this op
                        self._add_parallel_op_for_layer(insert_point, rewriter)
                    else:
                        op.detach()
                # don't share the same qubits
                elif set(op.operands) & self.qubits_seen:
                    # if seen qubits before, parallelise the current layer before this op
                    self._add_parallel_op_for_layer(insert_point, rewriter)

                if not added:
                    op.detach()
                    # if hasn't been added then add to a new layer
                    if isinstance(op, GateLikeOp):
                        self.layers_to_parallelise.append(
                            _GateLayer(gate_first=True, before_noise_op=None, gate_op=op)
                        )
                    elif isinstance(op, PauliNoiseOp):
                        self.layers_to_parallelise.append(
                            _GateLayer(gate_first=False, before_noise_op=op, gate_op=None)
                        )
                self.qubits_seen.update(op.operands)
            else:
                # not a gate or noise op, so parallelise any existing layer before this op
                self._add_parallel_op_for_layer(insert_point, rewriter)


class _GateLayerParallelisePattern(RewritePattern):
    """Rewrites the circuit to parallelise gate-like and noise operations."""

    @op_type_rewrite_pattern
    @override
    def match_and_rewrite(self, op: CircuitOp, rewriter: PatternRewriter) -> None:
        circuit_walker = _CircuitWalker()
        circuit_walker.walk_circuit(op, rewriter)


@dataclass(frozen=True)
class GateLayerParallelise(ModulePass):
    """Pass that attempts to parallelise the program in a way that reflects gate-layers.

    It attempts to mimic gate layers in Deltakit-Stim by parallelising gate-like (gates, measures,
    resets) operations that use different qubits. It does this greedily, so it will accumulate
    operations that use different qubits and when it encounters an operation that uses the same
    qubits as a previous operation, it will parallelise the accumulated operations before that
    operation.

    However, it will attempt to link together neighbouring noise and gate-like operations if
    they operate on the same qubits. A noise operation can be linked to at most one gate-like
    operation; a gate-like operation can be linked to at most two noise operations, but only
    its immediate predecessor and immediate successor. If operations are linked together, then
    when parallelised, they will be part of the same region.

    A non qref operation triggers the parallelisation of the current layer, as it is assumed to be
    a barrier to parallelisation."""

    name = "gate-layer-parallelise"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        PatternRewriteWalker(
            _GateLayerParallelisePattern(), apply_recursively=False
        ).rewrite_module(op)
