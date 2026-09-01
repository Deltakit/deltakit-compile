# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for building quantum circuits using the Circuit Builder API."""

from typing_extensions import override

from deltakit_compile.dialects import func
from deltakit_compile.dialects import log_asm_api as api
from deltakit_compile.frontend.common._builder import SubCallablesBuilder
from deltakit_compile.frontend.common._program_builder import Program, ProgramBuilder
from deltakit_compile.frontend.common._qubit_reg import QubitReg


class CircuitProgram(Program):
    """An immutable Circuit Builder program that can be compiled into a physical circuit."""


class CircuitProgramBuilder(ProgramBuilder[CircuitProgram]):
    """
    Builder class for the Circuit Builder API.

    Used to create Circuit Builder programs.
    """

    def __init__(self) -> None:
        # Internal state management.
        super().__init__()
        self._called = SubCallablesBuilder[func.FuncOp | api.CircuitDeclarationOp](
            "Circuit Builder program",
        )

    @override
    def build_program(self) -> CircuitProgram:
        """Generate a ``CircuitProgram`` from this builder."""
        return CircuitProgram(self._build_module())

    def declare_qubits(self, reg: QubitReg) -> QubitReg:
        """Declare a new QubitReg as part of this builder's program. This will attached the
        QubitReg to this builder, after which it can be used to perform operations that become part
        of this builder's program."""
        reg._declare_in_builder(self._builder)
        return reg
