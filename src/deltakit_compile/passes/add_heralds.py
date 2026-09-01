# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module containing a pass that adds herald leakage events to a circuit."""

from dataclasses import dataclass

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.rewriter import InsertPoint

from deltakit_compile.dialects.deltakit_stim import HeraldLeakageEventOp
from deltakit_compile.dialects.stim import (
    DetectorOp,
    MeasurementGateOp,
    MultiPauliProductMeasurementOp,
)


class _AddHeraldsPattern(RewritePattern):
    """Add a herald leakage event and detectors that flag each herald before each measurement op."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(
        self,
        op: MeasurementGateOp | MultiPauliProductMeasurementOp,
        rewriter: PatternRewriter,
    ) -> None:
        herald_op = HeraldLeakageEventOp(op.targets)
        detector_ops = [DetectorOp([herald]) for herald in herald_op.heralds]
        rewriter.insert_op([herald_op, *detector_ops], InsertPoint.before(op))


@dataclass(frozen=True)
class AddHeralds(ModulePass):
    """Pass for adding herald leakage events and detectors that flag them to a circuit. Applying
    this pass as part of compilation to a control system program will require adaptivity aware
    decoding."""

    name = "add-heralds"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        PatternRewriteWalker(
            _AddHeraldsPattern(),
            apply_recursively=False,
        ).rewrite_module(op)
