# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for the Rewrite patterns that canonicalise parts of the qstruct dialect."""

from collections.abc import Iterator

from typing_extensions import override
from xdsl.ir import Attribute, Operation, OpResult, Region, SSAValue
from xdsl.pattern_rewriter import PatternRewriter, RewritePattern, op_type_rewrite_pattern
from xdsl.rewriter import InsertPoint
from xdsl.traits import ConstantLike, IsTerminator, is_side_effect_free, is_speculatable
from xdsl.utils.hints import isa

from deltakit_compile.dialects import qcore, qstruct
from deltakit_compile.dialects import stabiliser as stab
from deltakit_compile.dialects.qcore import (
    RecursiveQuantumEffect,
    is_quantum_effect_free,
)
from deltakit_compile.utilities.ir_helpers import get_all_ssa_values


class InlineClassicalCircuit(RewritePattern):
    """Inline a circuit that does not have any quantum effects."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.CircuitOp, rewriter: PatternRewriter) -> None:
        assert op.has_trait(RecursiveQuantumEffect)
        if is_quantum_effect_free(op):
            yield_op = op.yield_op
            rewriter.inline_block(op.body.block, InsertPoint.before(op), op.args)
            rewriter.replace_op(op, [], yield_op.operands)
            rewriter.erase_op(yield_op)


class RemoveUnusedCircuitArgs(RewritePattern):
    """Remove arguments to a circuit that are not used inside the circuit body.

    Note that this will not remove qubit arguments because they are always yielded.
    """

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.CircuitOp, rewriter: PatternRewriter) -> None:
        new_operands: list[SSAValue] = []
        for operand, block_arg in zip(op.args, op.body.block.args, strict=True):
            if bool(block_arg.uses):  # Check if SSA is used
                new_operands.append(operand)
            else:
                rewriter.erase_block_argument(block_arg)

        if len(new_operands) < len(op.args):
            body = rewriter.move_region_contents_to_new_regions(op.body)
            rewriter.replace_op(op, qstruct.CircuitOp(new_operands, op.result_types, body))


class RemoveUnusedResults(RewritePattern):
    """Remove results yielded from a circuit or parallel body that are not used.

    Qubit results of a circuit may not be removed (all qubits passed into a circuit must be passed
    out again). Measurement results that are used in stab.concrete_flow_array attributes are not
    removed because they indicate the measurements associated with stabiliser flows, and this
    information is needed by the stabiliser flow pipeline to form detectors.
    """

    @staticmethod
    def _get_yields(op: qstruct.CircuitOp | qstruct.ParallelOp) -> Iterator[qstruct.YieldOp]:
        """Get the yield for each region in the provided op."""
        for region in op.regions:
            last_op = region.block.last_op
            assert isinstance(last_op, qstruct.YieldOp)
            yield last_op

    @staticmethod
    def _is_circuit_qubit(op: qstruct.CircuitOp | qstruct.ParallelOp, ssa: SSAValue) -> bool:
        """Is the SSA a qubit and the op a circuit, therefore meaning it can't be removed."""
        return isinstance(op, qstruct.CircuitOp) and isinstance(
            ssa.type, (qcore.QubitType, qcore.QubitRegType)
        )

    @staticmethod
    def _is_used_by_concrete_flow(result: OpResult) -> bool:
        """Is the SSA used in the stab.concrete_flow_array attribute as a measurement?"""
        attr = stab.ConcreteFlowArrayAttr.get(result.op)
        return attr is not None and attr.is_used_as_measurement(result)

    @staticmethod
    def _preserve_concrete_flow_array(
        old_op: Operation, new_op: Operation, removed_indices: set[int]
    ) -> None:
        """Copy any stab.concrete_flow_array attribute from old_op to new_op and update indices."""
        attr = stab.ConcreteFlowArrayAttr.get(old_op)
        if attr is not None:
            new_op.attributes[stab.ConcreteFlowArrayAttr.KEY] = attr.with_reindexed_measurements(
                removed_indices=removed_indices
            )

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(
        self, op: qstruct.CircuitOp | qstruct.ParallelOp, rewriter: PatternRewriter
    ) -> None:
        results_iter = iter(op.results)
        new_result_types_with_gaps: list[Attribute | None] = []

        for yield_op in self._get_yields(op):
            # For each yielded value, check if the correspond result is used
            new_yields = []
            for val in yield_op.arguments:
                if (
                    (result := next(results_iter)).uses
                    or self._is_used_by_concrete_flow(result)
                    or self._is_circuit_qubit(op, val)
                ):
                    new_yields.append(val)
                    new_result_types_with_gaps.append(val.type)
                else:
                    new_result_types_with_gaps.append(None)

            if len(new_yields) != len(yield_op.operands):
                rewriter.replace_op(yield_op, qstruct.YieldOp(*new_yields))

        if None in new_result_types_with_gaps:
            new_result_types = [
                res_type for res_type in new_result_types_with_gaps if res_type is not None
            ]
            match op:
                case qstruct.CircuitOp():
                    new_op: Operation = qstruct.CircuitOp(
                        op.args,
                        new_result_types,
                        rewriter.move_region_contents_to_new_regions(op.body),
                    )
                case qstruct.ParallelOp():
                    new_op = qstruct.ParallelOp(
                        new_result_types,
                        [
                            rewriter.move_region_contents_to_new_regions(region)
                            for region in op.par_regions
                        ],
                        op.alignment,
                    )

            removed_indices = {
                idx for idx, res_type in enumerate(new_result_types_with_gaps) if res_type is None
            }
            self._preserve_concrete_flow_array(op, new_op, removed_indices)

            new_res_iter = iter(new_op.results)
            rewriter.replace_op(
                op,
                new_op,
                [
                    None if res_type is None else next(new_res_iter)
                    for res_type in new_result_types_with_gaps
                ],
            )


class RemoveUnnecessaryParallel(RewritePattern):
    """Remove unused parallel regions, remove unnecessary nested parallels, and inline the parallel
    entirely if only one region is used."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.ParallelOp, rewriter: PatternRewriter) -> None:
        new_regions: list[Region] = []
        result_replacements: list[SSAValue | None] = []

        for region in op.par_regions:
            num_ops = len(region.block.ops)
            yield_op = region.block.last_op
            assert isinstance(yield_op, qstruct.YieldOp)
            if num_ops < 2 and not yield_op.arguments:
                # Unused region - don't carry it over and prep replacing parallel op's results with
                # the yield's operands if it has any
                result_replacements.extend(yield_op.arguments)
                continue

            # Region has some kind of contents - don't replace its results
            result_replacements.extend(None for _ in range(len(yield_op.arguments)))

            first_op = region.block.first_op
            if (
                num_ops == 2
                and isinstance(first_op, qstruct.ParallelOp)
                and first_op.alignment.data == op.alignment.data
            ):
                # Move contents of inner parallel into outer
                new_regions.extend(first_op.regions)
            else:
                new_regions.append(region)

        # Have the regions changed (or is the parallel trivially dead so already caught by DCE)
        if len(new_regions) > 0 and (
            len(new_regions) != len(op.par_regions)
            or not all(new_r is r for new_r, r in zip(new_regions, op.par_regions, strict=True))
        ):
            if len(new_regions) == 1:
                # Parallel is only one region - inline it
                region = new_regions[0]
                yield_op = region.block.last_op
                assert isinstance(yield_op, qstruct.YieldOp)
                rewriter.inline_block(region.block, InsertPoint.before(op))
                rewriter.replace_op(op, [], yield_op.arguments)
                rewriter.erase_op(yield_op)
            else:
                # Parallel has fewer regions but is still a parallel - replace it
                new_op = qstruct.ParallelOp(
                    [
                        res_type
                        for idx, res_type in enumerate(op.result_types)
                        if result_replacements[idx] is None
                    ],
                    [
                        rewriter.move_region_contents_to_new_regions(region)
                        for region in new_regions
                    ],
                    op.alignment,
                )
                new_results_iter = iter(new_op.results)
                rewriter.replace_op(
                    op,
                    new_op,
                    [
                        next(new_results_iter) if res_repl is None else res_repl
                        for res_repl in result_replacements
                    ],
                )


class HoistPureOpsFromParallel(RewritePattern):
    """Remove ops marked as Pure from inside qstruct.parallel ops where possible."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.ParallelOp, rewriter: PatternRewriter) -> None:
        for region in op.par_regions:
            for child in region.block.ops:
                if (
                    is_speculatable(child)
                    and is_quantum_effect_free(child)
                    and is_side_effect_free(child)
                    and not child.has_trait(IsTerminator)
                    and not any(
                        region.block.is_ancestor(value.owner)
                        for value in get_all_ssa_values(child)[0]
                    )
                ):
                    child.detach()
                    rewriter.insert_op(child, InsertPoint.before(op))


class RemovePureParallel(RewritePattern):
    """Inline parallels that don't have side effects, as there is little meaning to explicitly
    timing pure ops."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.ParallelOp, rewriter: PatternRewriter) -> None:
        if is_quantum_effect_free(op) and is_side_effect_free(op):
            new_results: list[SSAValue] = []
            for region in op.regions:
                yield_op = region.block.last_op
                assert isinstance(yield_op, qstruct.YieldOp)
                rewriter.inline_block(region.block, InsertPoint.before(op))
                new_results.extend(yield_op.operands)
                rewriter.erase_op(yield_op)

            rewriter.replace_op(op, [], new_results)


class RemoveUseOfParallelResults(RewritePattern):
    """Removes uses of the results of Parallels that could have used a higher up value."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.ParallelOp, rewriter: PatternRewriter) -> None:
        yields = [region.block.last_op for region in op.regions]
        assert isa(yields, list[qstruct.YieldOp])
        yielded = [arg for yield_op in yields for arg in yield_op.arguments]
        results = op.res
        for arg, result in zip(yielded, results, strict=True):
            if not op.is_ancestor(arg.owner):
                rewriter.replace_all_uses_with(result, arg)


class RehoistConstInRepeat(RewritePattern):
    """Hoist constants out of repeats (based on RehoistConstInLoops)."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.RepeatOp, rewriter: PatternRewriter) -> None:
        for child_op in op.body.ops:
            if child_op.has_trait(ConstantLike):
                # we only rehoist consts that are not embedded in another region inside the loop
                rewriter.insert_op(new_const := child_op.clone())
                rewriter.replace_op(child_op, (), new_const.results)


class SimplifyTrivialRepeat(RewritePattern):
    """Replace single-iteration repeats with their bodies and removes empty repeats that iterate at
    least once and only return values defined outside of the repeat."""

    @staticmethod
    def _is_ssa_defined_in_op(op: qstruct.RepeatOp, ssa: SSAValue) -> bool:
        """Is the provided SSA defined by an op inside the provided repeat op, or by the op's block
        args."""
        return op.is_ancestor(ssa.owner)

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.RepeatOp, rewriter: PatternRewriter) -> None:
        yield_op = op.yield_op

        # If the repeat has 1 iteration, inline its body and remove the repeat.
        if op.repetitions.data == 1:
            rewriter.inline_block(op.body.block, InsertPoint.before(op), op.iter_args)
            rewriter.replace_op(op, [], yield_op.operands)
            rewriter.erase_op(yield_op)
            return

        if len(op.body.block.ops) < 2:
            # If an empty repeat only yields values defined outside of the repeat
            if not any(self._is_ssa_defined_in_op(op, ssa) for ssa in yield_op.operands):
                rewriter.replace_op(op, [], yield_op.operands)
                return

            # If an empty repeat only yields its own block args in the same order
            if len(op.body.block.args) == len(yield_op.operands) and all(
                a == o for a, o in zip(op.body.block.args, yield_op.operands, strict=True)
            ):
                rewriter.replace_op(op, [], op.iter_args)
