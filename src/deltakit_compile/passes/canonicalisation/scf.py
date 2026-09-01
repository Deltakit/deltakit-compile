# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for the Rewrite patterns that canonicalise parts of the qstruct dialect."""

from typing_extensions import override
from xdsl.pattern_rewriter import PatternRewriter, RewritePattern, op_type_rewrite_pattern
from xdsl.transforms.canonicalization_patterns.utils import const_evaluate_operand

from deltakit_compile.dialects import qstruct, scf


class SimplifyForToRepeat(RewritePattern):
    """Convert an scf.for to a qstruct.repeat if its lb, ub, and step are all constant and its
    iterator is not used."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: scf.ForOp, rewriter: PatternRewriter) -> None:
        if (
            (lb := const_evaluate_operand(op.lb)) is not None
            and (ub := const_evaluate_operand(op.ub)) is not None
            and (step := const_evaluate_operand(op.step)) is not None
            and not (iterator := op.body.block.args[0]).uses  # Existence guaranteed by verify
        ):
            # Python does this in O(1) under the hood
            reps = len(range(lb, ub, step))

            yield_op = op.body.block.last_op
            assert isinstance(yield_op, scf.YieldOp)
            rewriter.replace_op(yield_op, qstruct.YieldOp(*yield_op.operands))
            rewriter.erase_block_argument(iterator)
            rewriter.replace_op(
                op,
                qstruct.RepeatOp(
                    reps, rewriter.move_region_contents_to_new_regions(op.body), op.iter_args
                ),
            )
