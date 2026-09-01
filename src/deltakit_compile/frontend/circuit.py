# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""
Frontend Circuit API.

This module defines the circuit API. Circuits are the low-level way of interacting with
the compiler by going one level deeper than LogASM, providing way more control on the
resulting program at the cost of less checks and potential optimisations.

The main structure is :class:`.CircuitBuilder` that should be instantiated to construct
a :class:`Circuit` piece by piece, and recover the resulting circuit by calling
:meth:`.CircuitBuilder.build`.

Examples:

    from deltakit_compile.frontend.circuit import CircuitBuilder, QubitReg

    builder = CircuitBuilder()
    qreg = builder.add_arg(QubitReg())
    builder.add_gate("X", qreg[0])
    circuit = builder.build()
"""

from .common import (
    Circuit,
    CircuitBuilder,
    MeasurementBit,
    MeasurementReg,
    Observable,
    ParallelAlignment,
    Pauli,
    Qubit,
    QubitReg,
    Result,
)

__all__ = [
    "Circuit",
    "CircuitBuilder",
    "MeasurementBit",
    "MeasurementReg",
    "Observable",
    "ParallelAlignment",
    "Pauli",
    "Qubit",
    "QubitReg",
    "Result",
]
