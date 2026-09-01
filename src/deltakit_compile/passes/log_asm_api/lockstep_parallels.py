# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module containing a pass that converts parallel operations to lockstep according to log_asm_api
rules."""

import itertools
from collections.abc import Sequence
from dataclasses import dataclass, field

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Block, Operation, SSAValue
from xdsl.pattern_rewriter import (
    GreedyRewritePatternApplier,
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.rewriter import InsertPoint

from deltakit_compile.dialects.log_asm_api import LOCKSTEP_PARALLEL_ATTRIBUTE
from deltakit_compile.dialects.qstruct import AlignmentAttr, ParallelOp, YieldOp
from deltakit_compile.passes.canonicalisation.qstruct import (
    RemovePureParallel,
    RemoveUnnecessaryParallel,
    RemoveUseOfParallelResults,
)
from deltakit_compile.passes.common.pipeline import (
    ConfigurablePass,
    Configuration,
    configurable_pass,
)


@dataclass(frozen=True)
class _LockstepRewrite(RewritePattern):
    """Replace each parallel op with the contents of its regions, inlined one after the other."""

    expected_attribute: str | None = None
    skipped_operations: frozenset[str] = field(default_factory=frozenset)

    def _create_parallel_from_op_groups(
        self,
        op_groups: Sequence[Sequence[Operation]],
        alignment: AlignmentAttr,
        rewriter: PatternRewriter,
    ) -> ParallelOp:
        """Create a parallel op from groups of operations, and update ssa value uses."""
        parallel_regions: list[Block] = []

        all_results: list[SSAValue] = []
        for group in op_groups:
            group_results = []
            block = Block()
            for op in group:
                if op.parent:
                    op.detach()
                rewriter.insert_op(op, InsertPoint(block))
                for res in op.results:
                    if any(use.operation not in group for use in res.uses):
                        group_results.append(res)
            rewriter.insert_op(YieldOp(*group_results), InsertPoint(block))
            all_results.extend(group_results)
            parallel_regions.append(block)

        parallel_op = ParallelOp([res.type for res in all_results], parallel_regions, alignment)
        for old_val, new_val in zip(all_results, parallel_op.res, strict=True):
            rewriter.replace_uses_with_if(
                old_val, new_val, lambda use: not parallel_op.is_ancestor(use.operation)
            )
        return parallel_op

    def match(self, op: ParallelOp) -> bool:
        """Check if we should attempt to lockstep `op`."""
        if self.expected_attribute is not None and self.expected_attribute not in op.attributes:
            return False

        ops_per_region = [list(region.block.ops) for region in op.regions]
        non_skippable_ops_per_region = [
            len(
                [
                    region_op
                    for region_op in region_list
                    if region_op.name not in self.skipped_operations
                    and not isinstance(region_op, YieldOp)
                ]
            )
            for region_list in ops_per_region
        ]
        return any(count > 1 for count in non_skippable_ops_per_region)

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: ParallelOp, rewriter: PatternRewriter) -> None:

        if not self.match(op):
            return
        alignment = op.alignment

        groups_per_region: list[list[list[Operation]]] = []
        for region in op.regions:
            groups: list[list[Operation]] = []
            next_group: list[Operation] = []
            next_op = region.block.first_op
            unskippable_found = False
            while next_op and not isinstance(next_op, YieldOp):
                if next_op.name in self.skipped_operations:
                    next_group.append(next_op)
                elif not unskippable_found:
                    unskippable_found = True
                    next_group.append(next_op)
                else:
                    groups.append(next_group)
                    next_group = [next_op]
                next_op = next_op.next_op
            if next_group:
                groups.append(next_group)
            groups_per_region.append(groups)

        if alignment == AlignmentAttr.BOTTOM():
            parallel_iterators = [reversed(lst) for lst in groups_per_region]
        else:
            parallel_iterators = [iter(lst) for lst in groups_per_region]

        parallel_ops: list[ParallelOp] = []
        for par_op_groups in itertools.zip_longest(*parallel_iterators, fillvalue=[]):
            parallel_op = self._create_parallel_from_op_groups(par_op_groups, alignment, rewriter)
            parallel_ops.append(parallel_op)

        if alignment == AlignmentAttr.BOTTOM():
            # Reverse the parallel ops to get back to the globally correct order
            parallel_ops.reverse()

        for par_op in parallel_ops:
            rewriter.insert_op(par_op, InsertPoint.before(op))


class LockstepParallelsConfig(Configuration, frozen=True):
    """Configuration class for the LockstepParallels pass"""

    expected_attribute: str | None = LOCKSTEP_PARALLEL_ATTRIBUTE
    skipped_operations: tuple[str, ...] = ("qec.detector",)


@configurable_pass
class LockstepParallels(ConfigurablePass[LockstepParallelsConfig]):
    """Pass that converts parallel operations to lockstep operations.

    The parallel regions are converted to lockstep in the order they are listed."""

    name = "lockstep-parallels"

    expected_attribute: str | None = None
    skipped_operations: tuple[str, ...] = ()

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [
                    RemovePureParallel(),
                    RemoveUseOfParallelResults(),
                    RemoveUnnecessaryParallel(),
                    _LockstepRewrite(
                        self.expected_attribute,
                        frozenset(self.skipped_operations),
                    ),
                ]
            )
        ).rewrite_module(op)
