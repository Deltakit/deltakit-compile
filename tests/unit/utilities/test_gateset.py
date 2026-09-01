"""Tests for native gate sets."""

import pytest

from deltakit_compile.shared.deltakit_stim.gates import SingleQubitUnitaryEnum, TwoQubitUnitaryEnum
from deltakit_compile.utilities.gatesets import (
    DEFAULT_GATES,
    EXHAUSTIVE_GATESET,
    ExhaustiveGateSet,
    NativeGateSet,
    NativeGateSetAndTimes,
)


def test_native_gateset_with_default_gates():
    """Test NativeGateSet with default gates."""
    gateset = NativeGateSet(native_gates=None)
    assert gateset.native_gates == dict.fromkeys(DEFAULT_GATES, 1.0)


def test_native_gateset_with_custom_gates():
    """Test NativeGateSet with custom gates set."""
    custom_gates = {SingleQubitUnitaryEnum.X, SingleQubitUnitaryEnum.Y, TwoQubitUnitaryEnum.CX}
    gateset = NativeGateSet(native_gates=custom_gates)
    assert gateset.native_gates == dict.fromkeys(custom_gates, 1.0)


def test_exhaustive_gateset():
    """Test ExhaustiveGateSet includes all available gates."""
    gateset = ExhaustiveGateSet()
    assert set(gateset.native_gates.keys()) == EXHAUSTIVE_GATESET
    assert all(time == 1.0 for time in gateset.native_gates.values())


def test_invalid_gates_in_native_gateset():
    """Test NativeGateSetAndTimes with invalid gates in native gate set."""

    with pytest.raises(ValueError, match=r"{'A'} are not valid gates in the native gate set."):
        NativeGateSetAndTimes(native_gates={SingleQubitUnitaryEnum.X: 1.0, "A": 1.0})


def test_native_gateset_invalid_with_negative_times():
    """Test NativeGateSetAndTimes with invalid gate times in native gate set."""

    with pytest.raises(
        ValueError,
        match=r"A gate time must be a non-negative float but that for X is -1.0.",
    ):
        NativeGateSetAndTimes(native_gates={SingleQubitUnitaryEnum.X: -1.0})


def test_adding_valid_gate_to_native_gateset():
    """Test NativeGateSetAndTimes with valid gate addition to native gate set."""

    gateset = NativeGateSetAndTimes(native_gates={SingleQubitUnitaryEnum.X: 1.0})
    gateset.add_gate(SingleQubitUnitaryEnum.Y, 1.0)
    assert gateset.native_gates == {SingleQubitUnitaryEnum.X: 1.0, SingleQubitUnitaryEnum.Y: 1.0}


def test_adding_invalid_gate_to_native_gateset():
    """Test NativeGateSetAndTimes with invalid gate addition to native gate set."""

    with pytest.raises(ValueError, match=r"Unknown gate T supplied."):
        NativeGateSetAndTimes(native_gates={SingleQubitUnitaryEnum.X: 1.0}).add_gate("T", 1.0)
