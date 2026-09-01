# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Common functionality shared between transforms."""

from typing import NamedTuple

from xdsl.dialects.builtin import ModuleOp, UnrealizedConversionCastOp
from xdsl.ir import SSAValue
from xdsl.utils.diagnostic import Diagnostic

from deltakit_compile.dialects import stim
from deltakit_compile.exceptions import CompilerPassCheckError


class GlobalQubitTracker:
    """Class for keeping track of the relationship between symbols that refer to qubits (aliases,
    etc.) and the qubits themselves."""

    class _QubitRange(NamedTuple):
        """Global start ID and length in the global ID space of a qubit reg."""

        start: int
        length: int

    def __init__(self) -> None:
        self._id_lookup: dict[SSAValue, GlobalQubitTracker._QubitRange] = {}
        self._num_qubits: int = 0

    def alloc(self, ssa: SSAValue[stim.QubitType]) -> None:
        """Allocate new qubits."""
        length = 1
        self._id_lookup[ssa] = GlobalQubitTracker._QubitRange(start=self._num_qubits, length=length)
        self._num_qubits += length

    def get_global_qubit_ids(self, ssa: SSAValue) -> set[int]:
        """Get the globally unique IDs for the qubits represented by the provided ssa."""
        if ssa not in self._id_lookup:
            msg = f"Provided SSAValue has no associated qubits: {ssa}"
            raise KeyError(msg)

        reg = self._id_lookup[ssa]
        return set(range(reg.start, reg.start + reg.length))


def generate_global_qubit_tracker(module_op: ModuleOp) -> GlobalQubitTracker:
    """Do a pass of the program, creating a fully populated global qubit tracker. Note that every
    qubit declaration and alias SSAValue will be available regardless of scope."""
    qubit_tracker = GlobalQubitTracker()
    for opn in module_op.walk():
        if isinstance(opn, stim.QubitAllocOp):
            qubit_tracker.alloc(opn.res)

    return qubit_tracker


def check_leftover_unrealized_casts(
    pass_name: str, op: ModuleOp, pre_existing_casts: set[UnrealizedConversionCastOp]
) -> None:
    """Walks the IR to check for newly added UnrealizedConversionCastOps. If any are found we
    produces error message for each cast op, then raises them as an error."""
    new_casts = {
        child for child in op.walk() if isinstance(child, UnrealizedConversionCastOp)
    } - pre_existing_casts

    if new_casts:
        diagnostic = Diagnostic()
        for cast_op in new_casts:
            msg = (
                f"Cast from {', '.join(map(str, cast_op.inputs.types))} to "
                f"{', '.join(map(str, cast_op.outputs.types))} could not be resolved"
            )
            next_ops = [
                use.operation.name
                for res in cast_op.outputs
                for use in res.uses
                if not isinstance(use.operation, UnrealizedConversionCastOp)
            ]
            if next_ops:
                msg += (
                    ". This is because lowering through the following operations failed: "
                    f"{', '.join(next_ops)}"
                )
            else:
                msg += ". This is likely because the program contains unreconcilable types"
            diagnostic.add_message(cast_op, msg)
        diagnostic.raise_exception(
            cast_op.get_toplevel_object(),
            CompilerPassCheckError(f"{pass_name} pass failed to reconcile all casts when lowering"),
        )
