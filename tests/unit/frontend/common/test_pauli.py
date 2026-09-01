import re

import pytest

from deltakit_compile.dialects.qcore import PauliAttr
from deltakit_compile.frontend.common import PauliType
from deltakit_compile.frontend.common._builder import OperationBuilder
from deltakit_compile.frontend.common._exceptions import (
    DuplicatedIdentifiersError,
    ObjectNotAttachedError,
)
from deltakit_compile.frontend.common._measurements import MeasurementReg
from deltakit_compile.frontend.common._pauli import Pauli, PauliFlow, PauliString
from deltakit_compile.frontend.common._qubit_reg import Qubit, QubitReg
from tests.unit.frontend.conftest import add_to_builder_with_fake_ssa


def test_pauli_string_initialisation() -> None:
    builder = OperationBuilder()
    reg = add_to_builder_with_fake_ssa(builder, QubitReg())

    with pytest.raises(ObjectNotAttachedError):
        PauliString({Qubit(): Pauli.X})

    pstr = PauliString({reg[0]: Pauli.X, reg[1]: "Z", reg[3]: PauliAttr.Y()})
    assert len(pstr) == 3


def test_pauli_string_getters() -> None:
    builder = OperationBuilder()
    reg = add_to_builder_with_fake_ssa(builder, QubitReg())

    q0, q1, q2, q3 = [reg[i] for i in range(4)]
    pstr = PauliString({q0: Pauli.X, q1: Pauli.Z, q3: Pauli.Y})
    assert len(pstr) == 3
    assert pstr[q0] == Pauli.X
    assert pstr[q1] == Pauli.Z
    assert pstr[q3] == Pauli.Y

    with pytest.raises(KeyError):
        pstr[q2]

    assert pstr.get(q0) == Pauli.X
    assert pstr.get(q1) == Pauli.Z
    assert pstr.get(q2) is None
    assert pstr.get(q3) == Pauli.Y

    with pytest.raises(ObjectNotAttachedError):
        pstr[Qubit()]

    with pytest.raises(ObjectNotAttachedError):
        pstr.get(Qubit())


def test_pauli_flow_instantiation() -> None:
    builder = OperationBuilder()
    reg = add_to_builder_with_fake_ssa(builder, QubitReg(4))
    meas = add_to_builder_with_fake_ssa(builder, MeasurementReg(10))

    q0, q1 = [reg[i] for i in range(2)]
    m0, m1, m2 = [meas[i] for i in range(3)]

    empty_flow = PauliFlow(PauliString({}), PauliString({}), [])
    assert len(empty_flow.inputs) == 0
    assert len(empty_flow.outputs) == 0
    assert len(empty_flow.measurements) == 0
    assert empty_flow.sign

    inputs = PauliString({q0: Pauli.X})
    outputs = PauliString({q1: Pauli.X})
    measurements = (m1, m2)
    flow = PauliFlow(inputs, outputs, measurements)
    assert flow.inputs == inputs
    assert flow.outputs == outputs
    assert flow.measurements == measurements
    assert flow.sign

    msg = re.escape(
        f"The following identifiers were provided more than once: {{'{m0.identifier}'}}."
    )
    with pytest.raises(DuplicatedIdentifiersError, match=msg):
        PauliFlow(PauliString({}), PauliString({}), [m0, m0])


@pytest.mark.parametrize(
    ("inp", "expected"),
    [
        (Pauli.X, Pauli.X),
        (Pauli.Y, Pauli.Y),
        (Pauli.Z, Pauli.Z),
        ("X", Pauli.X),
        ("Y", Pauli.Y),
        ("Z", Pauli.Z),
        (PauliAttr.X(), Pauli.X),
        (PauliAttr.Y(), Pauli.Y),
        (PauliAttr.Z(), Pauli.Z),
    ],
)
def test_pauli_coerce(inp: PauliType, expected: Pauli) -> None:
    assert Pauli.coerce(inp) == expected
