# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Pass that attempts to parallelise log_asm_api circuits, obeying the API's barrier semantics, as
part of lowering the program to logical assembly."""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Attribute, Block, Operation, Region, SSAValue
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    GreedyRewritePatternApplier,
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.rewriter import InsertPoint
from xdsl.traits import IsolatedFromAbove, IsTerminator, MemoryEffect, get_effects
from xdsl.utils.hints import isa

from deltakit_compile.dialects import log_asm_api as api
from deltakit_compile.dialects import logical_assembly as logasm
from deltakit_compile.dialects import qcore, qstruct, scf
from deltakit_compile.dialects.common.traits import HasSideEffects
from deltakit_compile.dialects.logical_assembly import RotatedPlanarPatchType
from deltakit_compile.shared.patch.bounding_box import BoundingBox


@dataclass(frozen=True)
class _RemoveBarriers(RewritePattern):
    """Pattern to remove log_asm_api.barrier ops."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: api.BarrierOp, rewriter: PatternRewriter) -> None:
        rewriter.replace_op(op, (), op.arguments)


@dataclass
class _ParallelisableBlock:
    block: list[Operation]
    generated_ssa_values: set[SSAValue] = field(default_factory=set)
    bounding_boxes: set[BoundingBox] = field(default_factory=set)

    def overlaps(self, boxes: set[BoundingBox]) -> bool:
        if self.bounding_boxes & boxes:
            return True
        return any(box1.intersects(box2) for box1 in self.bounding_boxes for box2 in boxes)


@dataclass
class _Paralleliser:
    rewriter: PatternRewriter
    reset_on_shrink: bool = False
    current_parallel_blocks: list[_ParallelisableBlock] = field(default_factory=list)

    @staticmethod
    def _all_used_ssa_values(
        op: Operation, *, created: set[SSAValue] | None = None
    ) -> set[SSAValue]:
        used = set()
        created = set() if created is None else created
        used.update(set(op.operands) - created)
        for region in op.regions:
            for block in region.blocks:
                created.update(block.args)
                for child in block.ops:
                    if child.has_trait(IsolatedFromAbove):
                        created.update(child.results)
                    else:
                        used.update(_Paralleliser._all_used_ssa_values(child, created=created))
        created.update(op.results)
        return used

    def _unparallelisable_op(self, op: Operation) -> bool:
        return (
            op.has_trait(qcore.HasProgramParent)
            or bool(op.has_trait(MemoryEffect) and get_effects(op))
            or op.has_trait(HasSideEffects)
        )

    def process_op(self, op: Operation) -> None:
        """Try to add `op` to a current parallel block, or make a new one if there are none to
        add to. If `op` depends on multiple parallel blocks, a new parallel op is inserted.
        """
        if self._unparallelisable_op(op):
            # Anything unparallelisable collapses all parallelisation for safety
            if len(self.current_parallel_blocks) > 1:
                self._make_parallel_op(self.current_parallel_blocks, InsertPoint.before(op))
            self.current_parallel_blocks = []
            return

        created_values: set[SSAValue] = set()
        used_values = self._all_used_ssa_values(op, created=created_values)
        used_area = {
            bbox
            for val in created_values | used_values
            if isa(val.type, RotatedPlanarPatchType) and (bbox := val.type.bounding_box) is not None
        }

        touched_parallel_blocks = [
            b
            for b in self.current_parallel_blocks
            if b.generated_ssa_values & used_values or b.overlaps(used_area)
        ]

        if not touched_parallel_blocks:
            # No connection to other blocks - this can be its own parallel thing.
            new_block = _ParallelisableBlock([op], set(op.results), used_area)
            self.current_parallel_blocks.append(new_block)
        elif len(touched_parallel_blocks) > 1:
            # Touches more than one otherwise parallel blocks, so we need to put those blocks
            # together
            parallel_op = self._make_parallel_op(touched_parallel_blocks, InsertPoint.before(op))
            total_area = set().union(*(block.bounding_boxes for block in touched_parallel_blocks))
            self.current_parallel_blocks = [
                b for b in self.current_parallel_blocks if b not in touched_parallel_blocks
            ]

            # Heuristic: if the size of the area covered by op is less than the parallel op
            # we do not include the parallel op in the new _ParallelisableBlock
            if len(used_area) < len(total_area):
                new_block = _ParallelisableBlock([op], set(op.results), used_area)
            else:
                new_block = _ParallelisableBlock(
                    [parallel_op, op],
                    set(parallel_op.res) | set(op.results),
                    total_area | used_area,
                )
            self.current_parallel_blocks.append(new_block)
        elif self.reset_on_shrink and len(used_area) < len(
            touched_parallel_blocks[0].bounding_boxes
        ):
            # new op uses less area than previous sequence of ops. We can choose to drop the
            # previous ops and let the parallelising continue with this new op.
            self.current_parallel_blocks.remove(touched_parallel_blocks[0])
            self.current_parallel_blocks.append(
                _ParallelisableBlock([op], set(op.results), used_area)
            )
        else:
            # op is only connected to one block and can be parallelised, so treat it as
            # sequentially part of that block
            touched_parallel_blocks[0].block.append(op)
            touched_parallel_blocks[0].generated_ssa_values.update(op.results)
            touched_parallel_blocks[0].bounding_boxes.update(used_area)

    def parallelise_block(self, block: Block) -> None:
        op = block.first_op
        while op:
            if op.has_trait(IsTerminator):
                if len(self.current_parallel_blocks) > 1:
                    self._make_parallel_op(self.current_parallel_blocks, InsertPoint.before(op))
                return
            self.process_op(op)

            op = op.next_op

        if len(self.current_parallel_blocks) > 1:
            self._make_parallel_op(self.current_parallel_blocks, InsertPoint.at_end(block))

    def _get_alignment(self, result_types: Sequence[Attribute]) -> qstruct.AlignmentAttr:
        """Alignment is chosen as BOTTOM when there are quantum types coming from the parallel as
        this ensures they are produced without needing to add excess stabiliser measurement rounds.
        For parallel ops that do not return quantum results, we use TOP alignment to allow any
        quantum operations to be completed as soon as possible, to minimise the need to insert
        rounds of stabiliser measurements at the beginning of regions."""
        return (
            qstruct.AlignmentAttr.BOTTOM()
            if any(
                isinstance(attr, (logasm.BasePatch, qcore.QubitType, qcore.QubitRegType))
                for attr in result_types
            )
            else qstruct.AlignmentAttr.TOP()
        )

    def _make_parallel_op(
        self, parallelisable_blocks: list[_ParallelisableBlock], insert_point: InsertPoint
    ) -> qstruct.ParallelOp:
        regions = []
        results: list[SSAValue] = []
        for par_block in parallelisable_blocks:
            block_ops = set(par_block.block)
            yielded_values = []
            new_block = Block()
            for op in par_block.block:
                op.detach()
                self.rewriter.insert_op(op, InsertPoint.at_end(new_block))
                for res in op.results:
                    if any(use.operation not in block_ops for use in res.uses):
                        yielded_values.append(res)
            self.rewriter.insert_op(qstruct.YieldOp(*yielded_values), InsertPoint.at_end(new_block))
            results.extend(yielded_values)
            regions.append(Region([new_block]))

        result_types = [val.type for val in results]
        par_op = qstruct.ParallelOp(result_types, regions, self._get_alignment(result_types))
        for i, output in enumerate(results):
            self.rewriter.replace_uses_with_if(
                output, par_op.res[i], lambda use: not par_op.is_ancestor(use.operation)
            )
        self.rewriter.insert_op(par_op, insert_point)
        return par_op


@dataclass(frozen=True)
class _ParalleliseBlocks(RewritePattern):
    """Pattern to parallelise all blocks"""

    reset_on_shrink: bool = False

    @override
    def match_and_rewrite(self, op: Operation, rewriter: PatternRewriter) -> None:
        for region in op.regions:
            if len(region.blocks) == 1:
                _Paralleliser(rewriter, self.reset_on_shrink).parallelise_block(region.block)


_PARALLELISABLE_OP_TYPES: Final[set[type[Operation]]] = {
    ModuleOp,
    scf.IfOp,
    scf.ForOp,
    scf.WhileOp,
    scf.IndexSwitchOp,
    qstruct.ParallelOp,
}


@dataclass(frozen=True)
class ParalleliseLogAsmApi(ModulePass):
    """A pass that parallelises log_asm_api based programs, respecting barriers."""

    name = "parallelise-log-asm-api"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        pattern = GreedyRewritePatternApplier([_ParalleliseBlocks(), _ParalleliseBlocks(True)])
        first_op = op.body.block.first_op
        if first_op is None:
            return
        # The pattern rewriter must take an op with a parent, despite us never using it
        # so we just use any valid op here.
        rewriter = PatternRewriter(first_op)

        rewriter.has_done_action = True
        while rewriter.has_done_action:
            # Apply parallelisation at the module op level until convergence
            rewriter.has_done_action = False
            for worklist_op in self._get_work_list(op):
                pattern.match_and_rewrite(worklist_op, rewriter)

        # remove all Barriers
        PatternRewriteWalker(_RemoveBarriers(), apply_recursively=False).rewrite_module(op)

    @staticmethod
    def _get_work_list(op: Operation) -> list[Operation]:
        """Gets all children ops that should be considered for parallelisation.
        We only parallelise blocks of regions of ops whose ancestors are all one of the
        ``_PARALLELISABLE_OP_TYPES`` to restrict parallelisation from interfering with circuits, or
        other structures we could not account for."""
        if type(op) in _PARALLELISABLE_OP_TYPES:
            return [
                op,
                *itertools.chain(
                    *(
                        ParalleliseLogAsmApi._get_work_list(child)
                        for region in op.regions
                        for child in region.block.ops
                    )
                ),
            ]
        return []
