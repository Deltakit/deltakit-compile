# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for appending custom traits to the existing MLIR func dialect."""

from xdsl.dialects.func import CallOp, Func, FuncOp, ReturnOp

from deltakit_compile.dialects.qcore import NoQuantumEffect

ReturnOp.traits.add_trait(NoQuantumEffect())

__all__ = ["CallOp", "Func", "FuncOp", "ReturnOp"]
