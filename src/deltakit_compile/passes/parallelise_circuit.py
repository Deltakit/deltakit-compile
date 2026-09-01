# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module containing a pass that parallelises quantum operations."""

from dataclasses import dataclass
from typing import cast

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Block, Operation, Region, SSAValue
from xdsl.passes import ModulePass

from deltakit_compile.dialects.qcore import get_quantum_effects
from deltakit_compile.dialects.qstruct import ParallelOp, YieldOp
from deltakit_compile.dialects.stim import QubitAllocOp
from deltakit_compile.passes._common import GlobalQubitTracker


@dataclass(frozen=True)
class ParalleliseCircuit(ModulePass):
    """Pass that parallelises quantum operations, where possible.

    The pass keeps track of which qubits have quantum effects applied to them (reset, gate, measure)
    and puts these quantum effect ops in parallel if we know they target different qubits. For cases
    like an alias to a qubit where the index is an SSAValue we assume that any qubit in the register
    could be affected and parallelise nothing else using that register with ops that use the
    ambiguous alias.

    The pass makes no attempt to parallelise classical ops, only neighbouring quantum ops. It will
    also only parallelise individual gates, so you can't end up with multiple consecutive gates in
    a parallel region. Gate definitions are entirely ignored (not that there'd be much to
    parallelise inside them).
    """

    name = "parallelise-circuit"

    def _parallelise(self, ops: list[Operation]) -> None:
        """Parallelise the provided ops and put the new ParallelOp before the first op."""
        if len(ops) < 2:
            return

        parent_block = cast(Block, ops[0].parent_block())
        prev_op = ops[0].prev_op

        # Create all the new parallel blocks
        parallel_blocks: list[Block | Region] = []
        parallel_results: list[SSAValue] = []
        yield_ops: set[Operation] = set()
        for opn in ops:
            opn.detach()
            yield_op = YieldOp(*opn.results)
            parallel_blocks.append(Block([opn, yield_op]))
            parallel_results.extend(opn.results)
            yield_ops.add(yield_op)

        # Insert new parallel op before first op we are parallelising
        parallel_op = ParallelOp([r.type for r in parallel_results], parallel_blocks)
        if prev_op is not None:
            parent_block.insert_op_after(parallel_op, prev_op)
        elif isinstance(parent_block.first_op, Operation):
            parent_block.insert_op_before(parallel_op, parent_block.first_op)
        else:
            parent_block.add_op(parallel_op)

        # Update uses of parallelised ops' SSAValues to point to the parallel op's results
        for old_result, new_result in zip(parallel_results, parallel_op.results, strict=False):
            old_result.replace_uses_with_if(new_result, lambda u: u.operation not in yield_ops)

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        qubit_tracker = GlobalQubitTracker()
        used_qubits: set[int] = set()
        ops_to_parallelise: list[Operation] = []
        cur_parent: Block | None = op.body.block

        for opn in op.walk():
            if cur_parent != opn.parent:
                # We've changed region - end current parallel
                self._parallelise(ops_to_parallelise)
                used_qubits.clear()
                ops_to_parallelise.clear()
                cur_parent = opn.parent

            if isinstance(opn, QubitAllocOp):
                qubit_tracker.alloc(opn.res)

            # Parallelise ops with quantum effects that operate on qubits or patches
            effects = get_quantum_effects(opn)
            if effects and all(effect.value is not None for effect in effects):
                target_qubits: set[int] = set()
                affected_ssas = {e.value for e in effects if e.value is not None}
                for ssa in affected_ssas:
                    target_qubits |= qubit_tracker.get_global_qubit_ids(ssa)

                if len(used_qubits.intersection(target_qubits)) != 0:
                    # This quantum op shares qubits with other ops we're parallelising - end current
                    # parallel
                    self._parallelise(ops_to_parallelise)
                    used_qubits.clear()
                    ops_to_parallelise.clear()

                ops_to_parallelise.append(opn)
                used_qubits |= target_qubits
            else:
                # This op doesn't have a known quantum effect - end current parallel
                self._parallelise(ops_to_parallelise)
                used_qubits.clear()
                ops_to_parallelise.clear()

        # Parallelise any remaining ops at the end
        self._parallelise(ops_to_parallelise)
