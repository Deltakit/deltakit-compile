# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module containing a pass that converts parallel operations to lockstep."""

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import chain, zip_longest

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Attribute, Block, Operation, OpOperands, OpResult, Region
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    GreedyRewritePatternApplier,
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)

from deltakit_compile.dialects.qstruct import AlignmentAttr, CircuitOp, ParallelOp, YieldOp
from deltakit_compile.passes.canonicalisation.qstruct import RemoveUnnecessaryParallel
from deltakit_compile.passes.stim._common import copy_stim_tag_from_ops, warn_stim_tag_lost


class _ConvertParallelsToLockstepRewrite(RewritePattern):
    """Replace each parallel op with the contents of its regions, inlined one after the other."""

    def _create_parallel_from_ops_tuple(
        self,
        ops_tuple: Sequence[Operation | None],
        alignment: AlignmentAttr,
    ) -> tuple[Operation | None, list[OpOperands]]:
        """Create a parallel op from a tuple of operations, remapping results.

        Returns the new parallel op (or single operation if only one non-None op in the tuple)
        and the operands from YieldOps encountered.
        """
        parallel_regions: list[Block] = []
        parallel_result_types: list[Attribute] = []
        yield_operands: list[OpOperands] = []

        old_results: list[OpResult] = []

        for opn in ops_tuple:
            if opn is not None:
                if isinstance(opn, YieldOp):
                    yield_operands.append(opn.operands)
                else:
                    if opn.parent:
                        opn.detach()
                    old_results.extend(opn.results)
                    block = Block(ops=[opn])  # Don't add YieldOp yet
                    parallel_regions.append(block)
                    parallel_result_types.extend(opn.result_types)

        if not parallel_regions:
            return None, yield_operands

        if len(parallel_regions) == 1:
            assert parallel_regions[0].first_op
            op = parallel_regions[0].first_op
            op.detach()  # Detach the single operation from its current position
            # For single operations, no remapping is needed since the operation itself is returned
            return op, yield_operands  # The single operation in the block
        parallel_op = ParallelOp(
            result_types=parallel_result_types,
            par_regions=parallel_regions,
            alignment=alignment,
        )

        for old_result, new_result in zip(old_results, parallel_op.res, strict=True):
            old_result.replace_all_uses_with(new_result)

        # Now add YieldOps to each region - they will use the original (non-remapped) values
        for block in parallel_regions:
            assert block.first_op, (
                "convert_parallels_to_lockstep: (Should never occur) Block should contain at "
                "least one operation"
            )
            block.add_op(YieldOp(*block.first_op.results))

        return parallel_op, yield_operands

    def _combine_circuits(
        self,
        circuits: Sequence[CircuitOp],
        alignment: AlignmentAttr,
    ) -> CircuitOp:
        """Combine CircuitOps in a tuple of operations into a single CircuitOp, remapping results.

        Returns the new CircuitOp (or single operation if only one non-None op in the tuple)
        and the operands from YieldOps encountered.
        """
        # Create iterators for each circuit's ops (chaining across all blocks)
        reverse_func = reversed if alignment == AlignmentAttr.BOTTOM() else lambda x: x
        circuit_iterators = [
            chain.from_iterable(
                reverse_func(block.ops) for region in circuit.regions for block in region.blocks
            )
            for circuit in circuits
        ]

        # Collect arguments (SSAValues passed to circuits) and result types
        circuit_args = [operand for circuit in circuits for operand in circuit.operands]
        circuit_arg_types = [operand.type for operand in circuit_args]
        circuit_result_types = [
            res_type for circuit in circuits for res_type in circuit.result_types
        ]

        # SSAValues yielded by the circuits being composed together
        circuit_yield_operands: list[OpOperands] = []
        # Operations in new circuit body
        circuit_ops_list: list[Operation] = []

        # Iterate through circuit ops in lockstep
        for circuit_ops_tuple in zip_longest(*circuit_iterators):
            parallel_op, extra_circuit_yield_operands = self._create_parallel_from_ops_tuple(
                circuit_ops_tuple, alignment
            )
            circuit_yield_operands.extend(extra_circuit_yield_operands)
            if parallel_op:
                circuit_ops_list.append(parallel_op)

        # Create the new circuit op with proper structure (without yield op yet)
        if alignment == AlignmentAttr.BOTTOM():
            circuit_ops_list.reverse()
        new_circuit_body = Block(arg_types=circuit_arg_types, ops=circuit_ops_list)

        # Remap old block arguments to new block arguments
        arg_idx = 0
        for circuit in circuits:
            for old_arg in circuit.body.block.args:
                new_arg = new_circuit_body.args[arg_idx]
                old_arg.replace_all_uses_with(new_arg)
                arg_idx += 1

        # Extract SSAValues from yield operands (already updated by replace_all_uses_with)
        circuit_yielded_ssas = [
            operand
            for circuit_yielded_operands in circuit_yield_operands
            for operand in circuit_yielded_operands
        ]

        new_circuit_op = CircuitOp(
            arguments=circuit_args,
            result_types=circuit_result_types,
            body=Region(new_circuit_body),
        )

        # Map old results to new circuit results
        old_circuit_results = [result for circuit in circuits for result in circuit.results]
        for old_result, new_result in zip(old_circuit_results, new_circuit_op.results, strict=True):
            old_result.replace_all_uses_with(new_result)

        # Now add yield op to circuit - operands already updated by replace_all_uses_with
        new_circuit_op.body.block.add_op(YieldOp(*circuit_yielded_ssas))

        # Copy stim tag from the first circuit that carries one; warn for any others
        copy_stim_tag_from_ops(
            circuits,
            new_circuit_op,
            "Multiple CircuitOps are combined into one, so only one stim tag can be preserved",
        )

        return new_circuit_op

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: ParallelOp, rewriter: PatternRewriter) -> None:
        # Iterate through operations in lockstep: 1st op from each region, then 2nd, etc.
        contained_ops: list[Operation] = []
        yield_operands: list[OpOperands] = []
        alignment = op.alignment

        # Create iterators for each region's ops (chaining across all blocks in each region)
        ops_per_region = [list(region.block.ops) for region in op.regions]

        # Can't do anything if all regions have 1 non-yield op and at most only one CircuitOp
        if (
            all(len(region_list) == 2 for region_list in ops_per_region)
            and sum(isinstance(ops[0], CircuitOp) for ops in ops_per_region) <= 1
        ):
            return

        if alignment == AlignmentAttr.BOTTOM():
            # Reverse each list, zip, then reverse the result to align from the end
            ops_iterator = zip_longest(*[reversed(lst) for lst in ops_per_region])
        else:
            ops_iterator = zip_longest(*ops_per_region)

        for ops_tuple in ops_iterator:
            circuits = [circuit for circuit in ops_tuple if isinstance(circuit, CircuitOp)]
            non_circuits: list[Operation | None] = [
                opn for opn in ops_tuple if opn is not None and not isinstance(opn, CircuitOp)
            ]

            if not circuits:
                combined_circuit = None
            elif len(circuits) == 1:
                circuits[0].detach()
                combined_circuit = circuits[0]
            else:
                combined_circuit = self._combine_circuits(circuits, alignment)

            non_circuits.append(
                combined_circuit
            )  # Add the combined circuit to the tuple for parallel creation
            parallel_op, extra_yield_operands = self._create_parallel_from_ops_tuple(
                non_circuits, alignment
            )
            yield_operands.extend(extra_yield_operands)
            if parallel_op:
                contained_ops.append(parallel_op)

        if alignment == AlignmentAttr.BOTTOM():
            contained_ops.reverse()

        # Extract SSAValues from YieldOps after all remapping is complete
        yielded_ssas = [operand for operands_view in yield_operands for operand in operands_view]

        rewriter.replace_op(op, contained_ops, new_results=yielded_ssas)
        warn_stim_tag_lost(
            op, "ParallelOp is expanded into multiple ops with no single correspondent"
        )


@dataclass(frozen=True)
class ConvertParallelsToLockstep(ModulePass):
    """Pass that converts parallel operations to lockstep operations.

    The parallel regions are converted to lockstep in the order they are listed."""

    name = "convert-parallels-to-lockstep"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [_ConvertParallelsToLockstepRewrite(), RemoveUnnecessaryParallel()]
            )
        ).rewrite_module(op)
