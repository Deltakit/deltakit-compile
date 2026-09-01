# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for appending custom traits to the existing MLIR arith dialect."""

from xdsl.dialects.arith import (
    AddiOp,
    AndIOp,
    Arith,
    CmpiOp,
    ConstantOp,
    OrIOp,
    SelectOp,
    SubiOp,
    XOrIOp,
)

from deltakit_compile.dialects.qcore import NoQuantumEffect

CmpiOp.traits.add_trait(NoQuantumEffect())
ConstantOp.traits.add_trait(NoQuantumEffect())
AddiOp.traits.add_trait(NoQuantumEffect())
SubiOp.traits.add_trait(NoQuantumEffect())
AndIOp.traits.add_trait(NoQuantumEffect())
OrIOp.traits.add_trait(NoQuantumEffect())
XOrIOp.traits.add_trait(NoQuantumEffect())
SelectOp.traits.add_trait(NoQuantumEffect())

__all__ = [
    "AddiOp",
    "AndIOp",
    "Arith",
    "CmpiOp",
    "ConstantOp",
    "OrIOp",
    "SelectOp",
    "SubiOp",
    "XOrIOp",
]
