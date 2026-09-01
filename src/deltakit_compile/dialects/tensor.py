# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for appending custom traits to the existing MLIR tensor dialect."""

from xdsl.dialects.tensor import (
    ConcatOp,
    DimOp,
    EmptyOp,
    ExtractOp,
    ExtractSliceOp,
    FromElementsOp,
    Tensor,
)

from deltakit_compile.dialects.qcore import NoQuantumEffect

ConcatOp.traits.add_trait(NoQuantumEffect())
DimOp.traits.add_trait(NoQuantumEffect())
EmptyOp.traits.add_trait(NoQuantumEffect())
ExtractOp.traits.add_trait(NoQuantumEffect())
ExtractSliceOp.traits.add_trait(NoQuantumEffect())
FromElementsOp.traits.add_trait(NoQuantumEffect())

__all__ = [
    "ConcatOp",
    "DimOp",
    "EmptyOp",
    "ExtractOp",
    "ExtractSliceOp",
    "FromElementsOp",
    "Tensor",
]
