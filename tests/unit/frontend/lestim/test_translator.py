"""Tests for translating Deltakit-Stim to the stim and deltakit-stim dialects"""

import pytest
from deltakit_stim import Circuit

from deltakit_compile.dialects.stim import CliffordGateOp, QubitAllocOp, QubitCoordsOp, ResetGateOp
from deltakit_compile.exceptions import InvalidInputStimCircuit
from deltakit_compile.frontend.deltakit_stim._translator import DeltakitStimTranslator

"""
Note that most tests of the Deltakit-Stim translator with valid circuit input are done as part of
the roundtrip tests located in test_stim.py - this file mostly contains tests of the translator's
responses to invalid input.
"""


def test_empty_circuit():
    """Test an empty circuit produces an IR with no ops."""
    circuit_op = DeltakitStimTranslator(Circuit()).to_xdsl_dialect()
    assert len(circuit_op.body.ops) == 0


@pytest.mark.parametrize(
    ("stim_str", "expected_alloc_num"),
    [
        ("QUBIT_COORDS(3, 0) 4", 1),
        ("R 0 1\n R 0 2", 3),
        ("H 4 2\n R 0 2 4 5", 4),
    ],
)
def test_qubit_alloc_gen(stim_str: str, expected_alloc_num: int):
    """Test that qubit allocation ops are added for every newly referenced qubit."""
    circuit_op = DeltakitStimTranslator(Circuit(stim_str)).to_xdsl_dialect()
    circuit_op.verify()

    allocs: list[QubitAllocOp] = []
    non_allocs: list[QubitCoordsOp | ResetGateOp | CliffordGateOp] = []
    for op in circuit_op.body.ops:
        if isinstance(op, QubitAllocOp):
            allocs.append(op)
        else:
            non_allocs.append(op)

    assert len(allocs) == expected_alloc_num
    for alloc in allocs:
        ssa_qubit = alloc.results[0]
        assert any(target == ssa_qubit for op in non_allocs for target in op.targets)


def test_invalid_instruction():
    """Test that an invalid instruction throws an error."""
    stim_str = "M 0 1\n INVALID_INSTRUCTION(1) rec[-2] rec[-1]"
    with pytest.raises(ValueError, match="Gate not found: 'INVALID_INSTRUCTION'"):
        DeltakitStimTranslator(Circuit(stim_str)).to_xdsl_dialect()


@pytest.mark.parametrize(
    "stim_str",
    ["SPP X1", "C_XYZ 0", "CXSWAP 0 1", "MPAD 1 0"],
)
def test_unknown_instruction(stim_str: str):
    """Test that a circuit with unknown instructions throws an error."""
    instr_name = stim_str.split(" ", maxsplit=1)[0].split("(", maxsplit=1)[0]

    with pytest.raises(
        InvalidInputStimCircuit,
        match=f"Deltakit-Stim {instr_name} instruction translation is not supported",
    ):
        DeltakitStimTranslator(Circuit(stim_str)).to_xdsl_dialect()


@pytest.mark.parametrize(
    ("stim_str", "error_str"),
    [
        ("OBSERVABLE_INCLUDE(1) rec[-2] rec[-1]", "Measurement record -2 is out of range"),
        (
            "REPEAT 2 {\n DETECTOR(0) rec[-1]\n }",
            "A measurement record is referred to that doesn't exist",
        ),
    ],
)
def test_undefined_record(stim_str: str, error_str: str):
    """Test that referring to a measurement record that doesn't exist throws an error."""
    with pytest.raises(InvalidInputStimCircuit, match=error_str):
        DeltakitStimTranslator(Circuit(stim_str)).to_xdsl_dialect()
