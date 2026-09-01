"""Exception tests for remap qubits pass (functional testing done using filecheck)."""

from typing import Final

import numpy as np
import pytest
from xdsl.builder import Builder
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp

from deltakit_compile.dialects.qcore import AllocQubitOp, QubitType, UnitaryGateAttr
from deltakit_compile.dialects.qref import GateOp
from deltakit_compile.exceptions import NonStandardUnitaryGateError
from deltakit_compile.passes.unitaries_to_named_gates import UnitariesToNamedGates

_random_unitary: Final[UnitaryGateAttr] = UnitaryGateAttr(
    [
        [
            (0.18680135049287339, -0.3711192991460318),
            (0.7081640472604931, -0.34231789770282406),
            (0.13127592677099512, 0.08720016494329963),
            (-0.4274437181348288, -0.03394834969044622),
        ],
        [
            (-0.42402342827353356, -0.7759570229477943),
            (-0.08067489833022212, 0.26018202872264895),
            (0.04339610270671557, 0.07077639084469176),
            (0.19893444252759515, -0.3121286143041571),
        ],
        [
            (0.04074740462720858, 0.12092622338398548),
            (-0.07490855589168924, -0.5224249950095569),
            (-0.4226674366165549, 0.2017767903595619),
            (0.1720928080110006, -0.6754256144719358),
        ],
        [
            (-0.13932569744346102, 0.09887062058406809),
            (0.1677921768568208, -0.020630802656894848),
            (0.08045557951484178, 0.8616469739250874),
            (0.32472474182891947, 0.29644281047009463),
        ],
    ],  # Unknown unitary matrix
)


@pytest.mark.parametrize(
    "random_unitary",
    [_random_unitary],
)
def test_unknown_unitary_raises(random_unitary: UnitaryGateAttr, xdsl_context: Context):
    """Test that an unknown unitary matrix throws a NonstandardUnitaryGateError."""

    @ModuleOp
    @Builder.implicit_region
    def module_op():
        GateOp(
            random_unitary,
            qubits=AllocQubitOp([QubitType(), QubitType()]).result,
        )

    with pytest.raises(NonStandardUnitaryGateError):
        UnitariesToNamedGates(precision=1e-5).apply(xdsl_context, module_op)


@pytest.mark.parametrize(
    "random_unitary",
    [_random_unitary],
)
def test_unknown_unitary_doesnt_raise(random_unitary: UnitaryGateAttr, xdsl_context: Context):
    """Test that an unknown unitary matrix does not throw a NonstandardUnitaryGateError."""

    @ModuleOp
    @Builder.implicit_region
    def module_op():
        GateOp(
            random_unitary,
            qubits=AllocQubitOp([QubitType(), QubitType()]).result,
        )

    UnitariesToNamedGates(precision=1e-5, unknown_unitary_error=False).apply(
        xdsl_context, module_op
    )


def test_known_unitary_rounding_precision(xdsl_context: Context):
    """Test that a known unitary matrix with small numerical errors is correctly identified as a
    standard gate."""
    # Define a unitary matrix that is close to the Hadamard gate
    hadamard_matrix = (1 / np.sqrt(2)) * np.array([[1 + 1e-7, 1 - 1e-7], [1 - 1e-7, -1 - 1e-7]])

    @ModuleOp
    @Builder.implicit_region
    def module_op():
        GateOp(
            UnitaryGateAttr(
                [
                    [(float(round(z.real, 10)), float(round(z.imag, 10))) for z in row]
                    for row in hadamard_matrix
                ]
            ),
            qubits=AllocQubitOp([QubitType()]).result,
        )

    # This should not raise an error since the matrix is close to a known gate
    UnitariesToNamedGates(precision=1e-5).apply(xdsl_context, module_op)
