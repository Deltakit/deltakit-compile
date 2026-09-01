# This file contains information which is proprietary to Riverlane Limited
# ("Riverlane") and is Riverlane Confidential Information.
# (c) Copyright Riverlane 2025-2026. All rights reserved.

"""Implement the ``plaquette-to-qstruct`` pass that lowers ``plaquette.sub_circuit`` and
``plaquette.round`` operations to ``qstruct.parallel`` operations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from typing_extensions import override
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Region, SSAValue
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.rewriter import BlockInsertPoint, InsertPoint
from xdsl.utils.hints import isa

from deltakit_compile.dialects import plaquette, qstruct


@dataclass
class _PlaquetteOpPattern(RewritePattern):
    """Lowers supported ``plaquette.round`` operations into ``qstruct.parallel``.

    Supported ``plaquette.round`` operations check all the conditions below:

    - Each of its parallel single-block regions contains exactly one ``plaquette.sub_circuit``
      operation and one ``plaquette.yield`` operation.

    This pass will lower operations like::

        %7, %8, %9 = plaquette.round(%0, %1, %2, %3, %4, %5, %6) -> i1, i1, i1 {
            ^bb2(%10: ..., %11: ..., %12: ..., %13: ..., %14: ..., %15: ..., %16: ...):
            %17 = plaquette.sub_circuit -> i1
                { [0_0] } { [0_1] } { [0_2] } { [0_3] } { [0_4] } { [0_5] } { [0_6] -> i1 }
            plaquette.yield %17 : i1
        } {
            ^bb3(%18: ..., %19: ..., %20: ..., %21: ..., %22: ..., %23: ..., %24: ...):
            %25 = plaquette.sub_circuit -> i1
                { [1_0] } { [1_1] } { [1_2] } { [1_3] -> i1 } { [1_4] } { [1_5] } { [1_6] }
            plaquette.yield %25 : i1
        } {
            ^bb4(%26: ..., %27: ..., %28: ..., %29: ..., %30: ..., %31: ..., %32: ...):
            %33 = plaquette.sub_circuit -> i1
                { [2_0] } { [2_1] } { [2_2] } { [2_3] } { [2_4] } { [2_5] -> i1 }
            plaquette.yield %33 : i1
        }

    where ``[n_t]`` means the ``n``-th parallel block executed at time ``t`` and ``[n_t] -> i1``
    means that this block returns an ``i1`` value, into::

        qstruct.parallel<TOP>            { [0_0]' }       { [1_0]' }       { [2_0]' }
        qstruct.parallel<TOP>            { [0_1]' }       { [1_1]' }       { [2_1]' }
        qstruct.parallel<TOP>            { [0_2]' }       { [1_2]' }       { [2_2]' }
        %8 = qstruct.parallel<TOP> -> i1 { [0_3]' }       { [1_3]' -> i1 } { [2_3]' }
        qstruct.parallel<TOP>            { [0_4]' }       { [1_4]' }       { [2_4]' }
        %9 = qstruct.parallel<TOP> -> i1 { [0_5]' }       { [1_5]' }       { [2_5]' -> i1 }
        %7 = qstruct.parallel<TOP> -> i1 { [0_6]' -> i1 } { [1_6]' }

    Note how the overall results stay the same, but are now produced by different operations, and
    potentially (like in the example above) in a different order. Also note that ``[2_6]`` was not
    present in the original example, and so has been left out of the last ``qstruct.parallel``.
    The ``'`` symbol after each ``[n_t]`` is here to show that the SSAs used by each block have been
    changed (they are not block arguments from the ``plaquette.round`` blocks any more but come from
    the outer context).

    Note also that there are complications when yielded values may be duplicated. For example,
    something like::

        %3, %4, %5, %6 = plaquette.round(%0, %1, %2) -> i1, i1, i1, i1 {
            ^bb2(%7: ..., %8: ..., %9: ...):
            %10, %11 = plaquette.sub_circuit -> i1, i1
                { [0_0] -> i1 (%a) } { [0_1] } { [0_2] -> i1 (%b) }
            plaquette.yield %11, %10 : i1, i1
        } {
            ^bb3(%12: ..., %13: ..., %14: ...):
            %15 = plaquette.sub_circuit -> i1
                { [1_0] -> i1 (%c) } { [1_1] } { [1_2] }
            plaquette.yield %15, %15 : i1, i1
        }

    where the first region of ``plaquette.round`` permutes the yielded values and the second region
    duplicates will be translated into::

        %4, %5, %6 = qstruct.parallel<TOP> { [0_0]' -> i1 (%a) } { [1_0]' -> i1, i1 (%c, %c) }
                     qstruct.parallel<TOP> { [0_1]' }            { [1_1]' }
        %3         = qstruct.parallel<TOP> { [0_2]' -> i1 (%b) } { [1_2]' }

    where the shuffling and duplication of ``plaquette.yield`` impact both the ``qstruct.yield``
    operations in the parallel blocks and the order in which we assign SSA values.
    """

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: plaquette.RoundOp, rewriter: PatternRewriter) -> None:
        """Lower ``plaquette.round`` to ``qstruct.parallel`` by transposing the block structure.

        This is the main method implementing the pattern. See class docstring for an example of what
        this method is doing.

        Args:
            op: any ``plaquette.RoundOp`` that might be replaced by a ``qstruct.parallel`` by this
                pattern.
            rewriter: rewriter used by the pattern to re-write the IR.
        """
        sub_circuits = [region.block.first_op for region in op.par_regions]
        if not isa(sub_circuits, Sequence[plaquette.SubCircuitOp]):
            return
        if any(not isa(sub_circuit.next_op, plaquette.YieldOp) for sub_circuit in sub_circuits):
            return

        # First collapse all parallelised qubits into their outer qubit arguments.
        for par_region in op.par_regions:
            for operand, arg in zip(op.qubits, par_region.block.args, strict=True):
                rewriter.replace_all_uses_with(arg, operand)

        # Then iterate over the collections of parallel sub circuit regions to make new parallel ops
        sub_circuit_region_iterators = [iter(list(circuit.seq_regions)) for circuit in sub_circuits]
        while any(
            next_regions := [
                next(region_iter, None) for region_iter in sub_circuit_region_iterators
            ]
        ):
            par_regions: list[Region] = []
            results_to_replace: list[SSAValue] = []
            for sub_circuit, region in zip(sub_circuits, next_regions, strict=True):
                if region:
                    yield_op = region.block.last_op
                    assert isa(yield_op, plaquette.YieldOp)
                    results_to_replace.extend(sub_circuit.get_results_for_yield(yield_op))

                    # Swap yield ops without erasing the original
                    rewriter.insert_op(
                        qstruct.YieldOp(*yield_op.arguments), InsertPoint.after(yield_op)
                    )
                    yield_op.detach()

                    # Move the original block into a new region, and replace it with a dummy block
                    # to ensure `get_results_for_yield` always works
                    par_region = rewriter.move_region_contents_to_new_regions(region)
                    replacement_block = rewriter.create_block(
                        BlockInsertPoint.at_start(region), arg_types=par_region.block.arg_types
                    )
                    rewriter.insert_op(yield_op, InsertPoint.at_end(replacement_block))

                    par_regions.append(par_region)
            parallel_op = qstruct.ParallelOp([res.type for res in results_to_replace], par_regions)
            rewriter.insert_op(parallel_op, InsertPoint.before(op))
            for old, new in zip(results_to_replace, parallel_op.res, strict=True):
                rewriter.replace_all_uses_with(old, new)

        # Finally discard the now empty original op
        rewriter.replace_op(op, (), op.get_yielded_values())


@dataclass(frozen=True)
class PlaquetteToQstruct(ModulePass):
    """Lowers ``plaquette.sub_circuit`` and ``plaquette.round`` operations to ``qstruct.parallel``
    operations."""

    name = "plaquette-to-qstruct"

    @override
    def apply(self, ctx, op: ModuleOp) -> None:
        PatternRewriteWalker(_PlaquetteOpPattern()).rewrite_region(op.body)
