# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module containing a pass that wraps whole Deltakit-Stim circuit in a qstruct.circuit and converts
stim.repeat to qstruct.repeat"""

from dataclasses import dataclass

from typing_extensions import override
from xdsl.dialects.arith import ConstantOp
from xdsl.dialects.builtin import IntegerAttr, ModuleOp
from xdsl.ir import Block, Region, SSAValue
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    GreedyRewritePatternApplier,
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.rewriter import InsertPoint
from xdsl.utils.hints import isa

from deltakit_compile.dialects import qcore, qstruct, stim
from deltakit_compile.passes.stim._common import copy_stim_tag


class _QubitAllocPattern(RewritePattern):
    """Moves qubit allocation to separate block"""

    def __init__(self, block: Block):
        self._block = block

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qcore.AllocQubitOp, rewriter: PatternRewriter) -> None:
        if op.parent_block() == self._block:
            return
        block = op.parent_block()
        assert block, "Parent block of AllocQubitOp should not be None"
        assert block.get_toplevel_object() == block.parent_op()
        for result in op.results:
            new_arg = rewriter.insert_block_argument(block, len(block.args), result.type)
            rewriter.replace_all_uses_with(result, new_arg)
        op.detach()
        rewriter.insert_op(op, InsertPoint.at_end(self._block))


class _EmptyOpPattern(RewritePattern):
    """Replace empty operations with arith.constant"""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stim.EmptyOp, rewriter: PatternRewriter) -> None:
        new_op = ConstantOp(IntegerAttr.from_bool(False))
        copy_stim_tag(op, new_op)
        rewriter.replace_op(op, new_op)


class _RepeatOpPattern(RewritePattern):
    """Replace stim repeat operations with qstruct repeat operations"""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stim.RepeatOp, rewriter: PatternRewriter) -> None:
        new_repeat_op = qstruct.RepeatOp(
            op.repetitions, region := op.detach_region(op.body), op.iter_args
        )
        if isa(yield_op := region.block.last_op, stim.YieldOp):
            rewriter.replace_op(yield_op, qstruct.YieldOp(*yield_op.operands))

        copy_stim_tag(op, new_repeat_op)

        rewriter.replace_op(op, new_repeat_op)


@dataclass(frozen=True)
class StimToQStruct(ModulePass):
    """Pass that converts stim operations to qstruct operations.

    It wraps the IR in a single qstruct.circuit, moves qubit allocations out of the new circuit,
    replaces stim.EmptyOp with arith.constant, and converts stim.repeat to qstruct.repeat.

    This pass works best when there is only one top level ModuleOp, and that ModuleOp contains all
    the stim operations to be converted. If there are multiple ModuleOps, all the allocate
    operations will be moved to the start of the top level ModuleOp and the circuit op will be
    added to the end of the top level ModuleOp."""

    name = "stim-to-qstruct"

    @override
    def apply(self, ctx, op: ModuleOp) -> None:
        alloc_block = Block()
        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [_QubitAllocPattern(alloc_block), _EmptyOpPattern(), _RepeatOpPattern()],
                dce_enabled=False,
            ),
        ).rewrite_module(op)

        circuit_region = op.detach_region(op.body)
        circuit_block = circuit_region.block

        op.add_region(Region(alloc_block))

        qubits: list[SSAValue[qcore.QubitType]] = []
        for alloc_op in alloc_block.ops:
            assert isinstance(alloc_op, qcore.AllocQubitOp)
            assert len(alloc_op.result) == 1, "Each AllocQubitOp should produce exactly one result"
            qubit = alloc_op.result[0]
            assert isa(qubit, SSAValue[qcore.QubitType]), (
                "Result of AllocQubitOp should be of type QubitType"
            )
            qubits.append(qubit)

        circuit_block.add_op(qstruct.YieldOp(*circuit_block.args))

        circuit_op = qstruct.CircuitOp(
            qubits,
            [qcore.QubitType()] * len(qubits),
            circuit_region,
        )

        op.body.block.add_op(circuit_op)
