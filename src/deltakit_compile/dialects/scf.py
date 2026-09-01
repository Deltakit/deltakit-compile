# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for appending custom traits to the existing MLIR scf dialect."""

from typing_extensions import override
from xdsl.dialects.scf import ConditionOp, ForOp, IfOp, IndexSwitchOp, Scf, WhileOp, YieldOp
from xdsl.pattern_rewriter import RewritePattern
from xdsl.traits import HasCanonicalizationPatternsTrait

from deltakit_compile.dialects.qcore import NoQuantumEffect, RecursiveQuantumEffect


class ForOpHasMoreCanonicalizationPatternsTrait(HasCanonicalizationPatternsTrait):
    @override
    @classmethod
    def get_canonicalization_patterns(cls) -> tuple[RewritePattern, ...]:
        from deltakit_compile.passes.canonicalisation.scf import (  # noqa: PLC0415
            SimplifyForToRepeat,
        )  # Imported here to avoid circular imports.

        return (SimplifyForToRepeat(),)


ConditionOp.traits.add_trait(NoQuantumEffect())
ForOp.traits.add_trait(ForOpHasMoreCanonicalizationPatternsTrait())
ForOp.traits.add_trait(RecursiveQuantumEffect())
IfOp.traits.add_trait(RecursiveQuantumEffect())
IndexSwitchOp.traits.add_trait(RecursiveQuantumEffect())
WhileOp.traits.add_trait(RecursiveQuantumEffect())
YieldOp.traits.add_trait(NoQuantumEffect())

__all__ = ["ConditionOp", "ForOp", "IfOp", "IndexSwitchOp", "Scf", "WhileOp", "YieldOp"]
