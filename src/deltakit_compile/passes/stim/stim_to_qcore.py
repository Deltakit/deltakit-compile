# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module containing a that replaces stim qubit allocations with qcore.alloc_qubits"""

from dataclasses import dataclass
from typing import Final

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import (
    ArrayAttr,
    FloatData,
    ModuleOp,
    UnrealizedConversionCastOp,
)
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.utils.hints import isa

from deltakit_compile.dialects import qcore, stim

from ._common import copy_stim_tag

_COORD_ATTR: Final[str] = "stim_to_qcore.coords"


class _ReplaceStimCoordsOpPattern(RewritePattern):
    """Concatatenates coordinates from multiple `stim.QubitCoordsOp` onto the corresponding
    `stim.QubitAllocOp`."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stim.QubitCoordsOp, rewriter: PatternRewriter) -> None:
        coords = op.qubitcoord.coords.data
        for qubit in op.targets:
            # this works because in the `stim` dialect, only qubit alloc ops can produce qubits.
            # repeats cannot because they only take in `i1` operands so will only produce
            # `i1` results.
            alloc_op = qubit.owner
            assert isinstance(alloc_op, stim.QubitAllocOp), (
                "Expected operand of stim.assign_qubit_coord to be defined by a stim.QubitAlloc "
                "operation."
            )
            old = alloc_op.attributes.get(_COORD_ATTR, ArrayAttr([]))
            assert isinstance(old, ArrayAttr)
            alloc_op.attributes[_COORD_ATTR] = ArrayAttr(old.data + coords)
            rewriter.erase_op(op)


class _ReplaceStimQubitAllocOpPattern(RewritePattern):
    """Replaces stim qubit allocations with `qcore.alloc_qubits` and assigns coordinates based
    on the attribute created by `_ReplaceStimCoordsOpPattern`."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stim.QubitAllocOp, rewriter: PatternRewriter) -> None:
        coords = op.attributes.get(_COORD_ATTR, ArrayAttr([]))
        assert isa(coords, ArrayAttr[FloatData]), (
            "Expected coordinate attribute to be an array of float data."
        )
        rewriter.replace_op(
            op,
            [
                new_op := qcore.AllocQubitOp(
                    qcore.QubitType(),
                    coordinates=[[coord.data for coord in coords.data]] if coords.data else None,
                    ids=[op.id],
                ),
                cast_op := UnrealizedConversionCastOp(
                    operands=[new_op.result],
                    result_types=[stim.QubitType()],
                ),
            ],
            new_results=cast_op.results,
        )

        copy_stim_tag(op, new_op)


@dataclass(frozen=True)
class StimToQcore(ModulePass):
    """Pass that replaces stim qubit allocations with qcore.alloc_qubits."""

    name = "stim-to-qcore"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        PatternRewriteWalker(_ReplaceStimCoordsOpPattern()).rewrite_module(op)

        PatternRewriteWalker(_ReplaceStimQubitAllocOpPattern()).rewrite_module(op)
