"""Tests for the Stim frontend API."""

from deltakit_stim import Circuit
from xdsl.dialects.arith import Arith
from xdsl.dialects.builtin import Builtin
from xdsl.dialects.scf import Scf
from xdsl.parser import Parser

from deltakit_compile.dialects.deltakit_stim import DeltakitStim
from deltakit_compile.dialects.qcore import QCore
from deltakit_compile.dialects.qec import Qec
from deltakit_compile.dialects.qref import QRef
from deltakit_compile.dialects.qstruct import QStruct
from deltakit_compile.dialects.stim import Stim
from deltakit_compile.frontend.deltakit_stim.io import (
    deltakit_stim_circuit_to_dialect,
    deltakit_stim_circuit_to_physical_circuit_ir,
    deltakit_stim_context,
    deltakit_stim_dialect_to_circuit,
    physical_circuit_ir_to_deltakit_stim_circuit,
)


def test_deltakit_stim_context_dialect_loading() -> None:
    exp_dialects = [Builtin, Stim, DeltakitStim, QCore, QRef, QStruct, Qec, Arith, Scf]
    context = deltakit_stim_context()
    assert len(list(context.loaded_dialects)) == len(exp_dialects)
    assert all(d in context.loaded_dialects for d in exp_dialects)


CIRCUIT = """
M 0
TICK
DETECTOR rec[-1]
"""

STIM_IR = """
builtin.module {
  %0 = stim.qubit_alloc 0 -> !stim.qubit
  %1 = stim.measure Z (%0) -> i1
  stim.tick
  stim.detector (%1 : i1)
}
"""

PHY_IR = """
builtin.module {
  %0 = qcore.alloc_qubit<ids = [0]> -> !qcore.qubit
  %1 = qstruct.circuit(%0 : !qcore.qubit) -> !qcore.qubit {
  ^bb0(%2: !qcore.qubit):
    %3 = qref.measure<Z> (%2) -> i1
    qec.measurement_round(%3 : i1)
    %4 = qec.detector(%3)
    qstruct.yield %2 : !qcore.qubit
  }
}
"""


def test_smoke_deltakit_stim_circuit_to_dialect() -> None:
    """Smoke test deltakit_stim_circuit_to_dialect - just showing the API works, as filecheck test
    are used for more thorough testing of the translation process."""
    module_op = deltakit_stim_circuit_to_dialect(Circuit(CIRCUIT))
    assert str(module_op).strip() == STIM_IR.strip()


def test_smoke_deltakit_stim_dialect_to_circuit() -> None:
    """Smoke test deltakit_stim_dialect_to_circuit - just showing the API works, as filecheck tests
    are used for more thorough testing of the translation process."""
    module_op = Parser(deltakit_stim_context(), STIM_IR).parse_module()
    circuit = deltakit_stim_dialect_to_circuit(module_op)
    assert str(circuit).strip() == CIRCUIT.strip()


def test_smoke_deltakit_stim_circuit_to_physical_circuit_ir() -> None:
    """Smoke test deltakit_stim_circuit_to_physical_circuit_ir - just showing the API works, as
    filecheck tests are used for more thorough testing of the translation process."""
    module_op = deltakit_stim_circuit_to_physical_circuit_ir(Circuit(CIRCUIT))
    assert str(module_op).strip() == PHY_IR.strip()


def test_smoke_physical_circuit_ir_to_deltakit_stim_circuit() -> None:
    """Smoke test physical_circuit_ir_to_deltakit_stim_circuit - just showing the API works, as
    filecheck tests are used for more thorough testing of the translation process."""
    module_op = Parser(deltakit_stim_context(), PHY_IR).parse_module()
    circuit = physical_circuit_ir_to_deltakit_stim_circuit(module_op)
    assert str(circuit).strip() == CIRCUIT.strip()
