"""Tests for the qubit/measurement trackers."""

import re

import pytest
from xdsl.context import Context
from xdsl.dialects import test
from xdsl.ir import SSAValue

from deltakit_compile.passes._qubit_measurement_tracker import (
    QubitMeasurementCoordinateTracker,
    QubitMeasurementTracker,
)
from tests.unit.conftest import parse_ir


@pytest.fixture(name="unknown_ssa_value")
def fixture_unknown_ssa_value() -> SSAValue:
    """An arbitrary SSA value of an arbitrary type."""
    return test.TestOp(result_types=[test.TestType("TestType")]).res[0]


@pytest.mark.parametrize(
    (
        "ir",
        "qubit_name_to_nums",
        "state_name_to_num_lists",
        "reg_name_to_num_lists",
        "meas_name_to_nums",
    ),
    [
        ("builtin.module {}", {}, {}, {}, {}),
        (
            """
            builtin.module {
                %q0 = qcore.alloc_qubit -> !qcore.qubit
            }
            """,
            {"q0": {0}},
            {},
            {},
            {},
        ),
        (
            """
            builtin.module {
                %q0 = qcore.alloc_qubit -> !qcore.qubit
                %q1 = qcore.alloc_qubit -> !qcore.qubit
                %s0 = stab.state.make (%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
                %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, []>
                                      -> !stab.state<2 x !qcore.qubit, []>
                  with (%q0_b, %q1_b : !qcore.qubit), () {
                    %m0 = qref.measure<Z> (%q0_b) -> i1
                    %m1 = qref.measure<Z> (%q1_b) -> i1
                    stab.yield []
                  }
            }
            """,
            {"q0": {0}, "q1": {1}, "q0_b": {0}, "q1_b": {1}},
            {"s0": ({0}, {1}), "s1": ({0}, {1})},
            {},
            {"m0": {0}, "m1": {1}},
        ),
        (
            """
            builtin.module {
                %q0 = qcore.alloc_qubit -> !qcore.qubit
                %s0 = stab.state.make (%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
                %s1 = stab.state.cast (%s0) !stab.state<1 x !qcore.qubit, []>
                    -> !stab.state<1 x !qcore.qubit, []>
            }
            """,
            {"q0": {0}},
            {"s0": ({0},), "s1": ({0},)},
            {},
            {},
        ),
        (
            """
            builtin.module {
                %q0 = qcore.alloc_qubit -> !qcore.qubit
                %q1 = qcore.alloc_qubit -> !qcore.qubit
                %s0 = stab.state.make (%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
                %s1, %m0_o = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, []>
                                             -> !stab.state<2 x !qcore.qubit, []>
                  with (%q0_b, %q1_b : !qcore.qubit), () {
                    %m0 = qref.measure<Z> (%q0_b) -> i1
                    stab.yield [] %m0 : i1
                  }
                %s2, %m2, %m3 = stab.circuit %s1 : !stab.state<2 x !qcore.qubit, []>
                                                -> !stab.state<2 x !qcore.qubit, []>
                  with (%q0_c, %q1_c : !qcore.qubit), (%m0_b = %m0_o : i1) {
                    %m1 = qref.measure<Z> (%q1_c) -> i1
                    stab.yield [] %m1, %m0_b : i1, i1
                  }
            }
            """,
            {"q0": {0}, "q1": {1}, "q0_b": {0}, "q1_b": {1}, "q0_c": {0}, "q1_c": {1}},
            {"s0": ({0}, {1}), "s1": ({0}, {1}), "s2": ({0}, {1})},
            {},
            {"m0": {0}, "m0_o": {0}, "m0_b": {0}, "m1": {1}, "m2": {1}, "m3": {0}},
        ),
        (
            # Circuit with yield measurements as well as arguments
            """
            builtin.module {
                %q0 = qcore.alloc_qubit -> !qcore.qubit
                %q1 = qcore.alloc_qubit -> !qcore.qubit
                %s0 = stab.state.make (%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
                %s1, %m0_o = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, []>
                                             -> !stab.state<2 x !qcore.qubit, []>
                  with (%q0_b, %q1_b : !qcore.qubit), () {
                    %m0 = qref.measure<Z> (%q0_b) -> i1
                    stab.yield [] %m0 : i1
                  }
                %s2, %m2, %m3 = stab.circuit %s1 : !stab.state<2 x !qcore.qubit, []>
                                                -> !stab.state<2 x !qcore.qubit, []>
                  with (%q0_c, %q1_c : !qcore.qubit), (%m0_b = %m0_o : i1) {
                    %m1 = qref.measure<Z> (%q1_c) -> i1
                    stab.yield [%m1 : i1] %m1, %m0_b : i1, i1
                  }
            }
            """,
            {"q0": {0}, "q1": {1}, "q0_b": {0}, "q1_b": {1}, "q0_c": {0}, "q1_c": {1}},
            {"s0": ({0}, {1}), "s1": ({0}, {1}), "s2": ({0}, {1})},
            {},
            {"m0": {0}, "m0_o": {0}, "m0_b": {0}, "m1": {1}, "m2": {1}, "m3": {0}},
        ),
        (
            """
            builtin.module {
                %q0 = qcore.alloc_qubit -> !qcore.qubit
                %q1 = qcore.alloc_qubit -> !qcore.qubit
                %s0 = stab.state.make (%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
                %s1 = stab.state.make (%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
                %s2, %m0_o = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, []>
                                             -> !stab.state<2 x !qcore.qubit, []>
                  with (%q0_b, %q1_b : !qcore.qubit), () {
                    %m0 = qref.measure<Z> (%q0_b) -> i1
                    stab.yield [] %m0 : i1
                  }
                %q2, %m1, %m2, %q3, %s3 = qstruct.parallel<TOP> -> !qcore.qubit, i1, i1,
                        !qcore.qubit, !stab.state<1 x !qcore.qubit, []> {
                    qstruct.yield %q1, %m0_o : !qcore.qubit, i1
                } {
                    %s4, %m2_in_o = stab.circuit %s1 : !stab.state<1 x !qcore.qubit, []>
                                                    -> !stab.state<1 x !qcore.qubit, []>
                      with (%q0_c : !qcore.qubit), () {
                        %m2_in = qref.measure<Z> (%q0_c) -> i1
                        stab.yield [] %m2_in : i1
                      }
                    qstruct.yield %m2_in_o, %q0, %s4 : i1, !qcore.qubit,
                        !stab.state<1 x !qcore.qubit, []>
                }
            }
            """,
            {"q0": {0}, "q1": {1}, "q0_b": {0}, "q0_c": {0}, "q1_b": {1}, "q2": {1}, "q3": {0}},
            {"s0": ({0}, {1}), "s1": ({0},), "s2": ({0}, {1}), "s3": ({0},), "s4": ({0},)},
            {},
            {"m0": {0}, "m0_o": {0}, "m1": {0}, "m2_in": {0}, "m2_in_o": {0}, "m2": {0}},
        ),
        (
            """
            builtin.module {
                %q0 = qcore.alloc_qubit -> !qcore.qubit
                %q1 = qcore.alloc_qubit -> !qcore.qubit
                %s0 = stab.state.make (%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
                %s1 = stab.state.make (%q1 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
                %s2 = stab.state.make (%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
                %s3 = stab.state.make (%q1, %q0 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
                %s0_a, %m0 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []>
                                             -> !stab.state<1 x !qcore.qubit, []>
                  with (%q0_b : !qcore.qubit), () {
                    %m0_i = qref.measure<Z> (%q0_b) -> i1
                    stab.yield [] %m0_i : i1
                  }
                %q2, %s4, %m2, %m3, %s5 = scf.if %m0 -> (
                        !qcore.qubit, !stab.state<1 x !qcore.qubit, []>, i1, i1,
                        !stab.state<2 x !qcore.qubit, []>) {
                    scf.yield %q0, %s0_a, %m0, %m0, %s2 : !qcore.qubit,
                        !stab.state<1 x !qcore.qubit, []>, i1, i1, !stab.state<2 x !qcore.qubit, []>
                } else {
                    %s1_a, %m1 = stab.circuit %s1 : !stab.state<1 x !qcore.qubit, []>
                                                 -> !stab.state<1 x !qcore.qubit, []>
                      with (%q1_b : !qcore.qubit), () {
                        %m1_i = qref.measure<Z> (%q1_b) -> i1
                        stab.yield [] %m1_i : i1
                      }
                    scf.yield %q1, %s1_a, %m1, %m0, %s3 : !qcore.qubit,
                        !stab.state<1 x !qcore.qubit, []>, i1, i1, !stab.state<2 x !qcore.qubit, []>
                }
            }
            """,
            {"q0": {0}, "q0_b": {0}, "q1": {1}, "q1_b": {1}, "q2": {0, 1}},
            {
                "s0": ({0},),
                "s0_a": ({0},),
                "s1": ({1},),
                "s1_a": ({1},),
                "s2": ({0}, {1}),
                "s3": ({1}, {0}),
                "s4": ({0, 1},),
                "s5": ({0, 1}, {0, 1}),
            },
            {},
            {"m0": {0}, "m0_i": {0}, "m1": {1}, "m1_i": {1}, "m2": {0, 1}, "m3": {0}},
        ),
        (
            """
            builtin.module {
                %q0 = qcore.alloc_qubit -> !qcore.qubit
                %q1 = qcore.alloc_qubit -> !qcore.qubit
                %q2 = qcore.alloc_qubit -> !qcore.qubit
                %s0 = stab.state.make (%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
                %s1 = stab.state.make (%q1, %q2 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
                %s2 = stab.state.make (%q2, %q0 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
                %s0_a, %m0 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, []>
                                             -> !stab.state<2 x !qcore.qubit, []>
                  with (%q0_b, %q1_b : !qcore.qubit), () {
                    %m0_i = qref.measure<Z> (%q0_b) -> i1
                    stab.yield [] %m0_i : i1
                  }
                %s1_a, %m1 = stab.circuit %s1 : !stab.state<2 x !qcore.qubit, []>
                                             -> !stab.state<2 x !qcore.qubit, []>
                  with (%q1_c, %q2_c : !qcore.qubit), () {
                    %m1_i = qref.measure<Z> (%q1_c) -> i1
                    stab.yield [] %m1_i : i1
                  }
                %s2_a, %m2 = stab.circuit %s2 : !stab.state<2 x !qcore.qubit, []>
                                             -> !stab.state<2 x !qcore.qubit, []>
                  with (%q2_d, %q0_d : !qcore.qubit), () {
                    %m2_i = qref.measure<Z> (%q2_d) -> i1
                    stab.yield [] %m2_i : i1
                  }
                %i = "test.op"() : () -> index
                %q3, %q4, %s3, %s4, %m3, %m4 = scf.index_switch %i -> !qcore.qubit, !qcore.qubit,
                        !stab.state<2 x !qcore.qubit, []>, !stab.state<2 x !qcore.qubit, []>, i1, i1
                case 1 {
                    scf.yield %q0, %q0, %s0_a, %s0_a, %m0, %m0 : !qcore.qubit, !qcore.qubit,
                        !stab.state<2 x !qcore.qubit, []>, !stab.state<2 x !qcore.qubit, []>, i1, i1
                }
                case 2 {
                    scf.yield %q1, %q1, %s1_a, %s1_a, %m1, %m1 : !qcore.qubit, !qcore.qubit,
                        !stab.state<2 x !qcore.qubit, []>, !stab.state<2 x !qcore.qubit, []>, i1, i1
                }
                default {
                    scf.yield %q2, %q0, %s2_a, %s0_a, %m2, %m0 : !qcore.qubit, !qcore.qubit,
                        !stab.state<2 x !qcore.qubit, []>, !stab.state<2 x !qcore.qubit, []>, i1, i1
                }
            }
            """,
            {
                "q0": {0},
                "q1": {1},
                "q2": {2},
                "q0_b": {0},
                "q0_d": {0},
                "q1_b": {1},
                "q1_c": {1},
                "q2_c": {2},
                "q2_d": {2},
                "q3": {0, 1, 2},
                "q4": {0, 1},
            },
            {
                "s0": ({0}, {1}),
                "s1": ({1}, {2}),
                "s2": ({2}, {0}),
                "s0_a": ({0}, {1}),
                "s1_a": ({1}, {2}),
                "s2_a": ({2}, {0}),
                "s3": ({0, 1, 2}, {0, 1, 2}),
                "s4": ({0, 1}, {1, 2}),
            },
            {},
            {
                "m0": {0},
                "m1": {1},
                "m2": {2},
                "m0_i": {0},
                "m1_i": {1},
                "m2_i": {2},
                "m3": {0, 1, 2},
                "m4": {0, 1},
            },
        ),
        (
            # Test tracing through qcore.pack_qubit_reg
            """
            builtin.module {
                %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
                %r0 = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
            }
            """,
            {"q0": {0}, "q1": {1}},
            {},
            {"r0": ({0}, {1})},
            {},
        ),
        (
            # Test tracing through qcore.unpack_qubit_reg
            """
            builtin.module {
                %r0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
                %q0, %q1 = qcore.unpack_qubit_reg(%r0 : !qcore.qubit_reg<2>)
            }
            """,
            {"q0": {0}, "q1": {1}},
            {},
            {"r0": ({0}, {1})},
            {},
        ),
        (
            # Test tracing through qcore.concatenate
            """
            builtin.module {
                %r0, %r1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>, !qcore.qubit_reg<3>
                %r2 = qcore.concatenate(%r0, %r1 : !qcore.qubit_reg<2>, !qcore.qubit_reg<3>)
                        -> !qcore.qubit_reg<5>
                %q0, %q1, %q2, %q3, %q4 = qcore.unpack_qubit_reg(%r2 : !qcore.qubit_reg<5>)
            }
            """,
            {"q0": {0}, "q1": {1}, "q2": {2}, "q3": {3}, "q4": {4}},
            {},
            {"r0": ({0}, {1}), "r1": ({2}, {3}, {4}), "r2": ({0}, {1}, {2}, {3}, {4})},
            {},
        ),
        (
            # Test tracing through qcore.split
            """
            builtin.module {
                %r0 = qcore.alloc_qubit -> !qcore.qubit_reg<5>
                %r1, %r2 = qcore.split(%r0 : !qcore.qubit_reg<5>)
                        -> !qcore.qubit_reg<2>, !qcore.qubit_reg<3>
                %q0, %q1 = qcore.unpack_qubit_reg(%r1 : !qcore.qubit_reg<2>)
                %q2, %q3, %q4 = qcore.unpack_qubit_reg(%r2 : !qcore.qubit_reg<3>)
            }
            """,
            {"q0": {0}, "q1": {1}, "q2": {2}, "q3": {3}, "q4": {4}},
            {},
            {"r0": ({0}, {1}, {2}, {3}, {4}), "r1": ({0}, {1}), "r2": ({2}, {3}, {4})},
            {},
        ),
        (
            # Mixture of registers and qubits in qcore.alloc_qubit
            """
            builtin.module {
                %q0, %r0, %q1, %q2, %r1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit_reg<2>,
                        !qcore.qubit, !qcore.qubit, !qcore.qubit_reg<1>
            }
            """,
            {"q0": {0}, "q1": {3}, "q2": {4}},
            {},
            {"r0": ({1}, {2}), "r1": ({5},)},
            {},
        ),
        (
            # Test tracing through qstruct.circuit
            """
            builtin.module {
                %q0, %r0 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit_reg<2>
                %r1, %q3, %m0 = qstruct.circuit(%q0, %r0 : !qcore.qubit, !qcore.qubit_reg<2>)
                        -> !qcore.qubit_reg<2>, !qcore.qubit, i1 {
                ^bb0(%q0_b : !qcore.qubit, %r0_b : !qcore.qubit_reg<2>):
                    %m0_i = qref.measure<Z> (%q0_b) -> i1
                    %q1, %q2 = qcore.unpack_qubit_reg(%r0_b : !qcore.qubit_reg<2>)
                    %r1_b = qcore.pack_qubit_reg(%q2, %q1) -> !qcore.qubit_reg<2>
                    qstruct.yield %r1_b, %q0_b, %m0_i : !qcore.qubit_reg<2>, !qcore.qubit, i1
                }
            }
            """,
            {"q0": {0}, "q0_b": {0}, "q1": {1}, "q2": {2}, "q3": {0}},
            {},
            {"r0": ({1}, {2}), "r0_b": ({1}, {2}), "r1_b": ({2}, {1}), "r1": ({2}, {1})},
            {"m0": {0}, "m0_i": {0}},
        ),
        (
            # Test tracing registers through branching
            """
            builtin.module {
                %q0, %q1, %q2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
                %i = "test.op"() : () -> i1
                %reg = scf.if %i -> (!qcore.qubit_reg<2>) {
                    %reg0 = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
                    scf.yield %reg0 : !qcore.qubit_reg<2>
                } else {
                    %reg1 = qcore.pack_qubit_reg(%q1, %q2) -> !qcore.qubit_reg<2>
                    scf.yield %reg1 : !qcore.qubit_reg<2>
                }
            }
            """,
            {"q0": {0}, "q1": {1}, "q2": {2}},
            {},
            {"reg": ({0, 1}, {1, 2}), "reg0": ({0}, {1}), "reg1": ({1}, {2})},
            {},
        ),
        (
            # Test tracing registers through parallel
            """
            builtin.module {
                %q0, %q1, %q2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
                %reg0, %reg1 = qstruct.parallel<TOP> -> !qcore.qubit_reg<2>, !qcore.qubit_reg<1> {
                    %reg0_i = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
                    qstruct.yield %reg0_i : !qcore.qubit_reg<2>
                } {
                    %reg1_i = qcore.pack_qubit_reg(%q2) -> !qcore.qubit_reg<1>
                    qstruct.yield %reg1_i : !qcore.qubit_reg<1>
                }
            }
            """,
            {"q0": {0}, "q1": {1}, "q2": {2}},
            {},
            {"reg0": ({0}, {1}), "reg1": ({2},), "reg0_i": ({0}, {1}), "reg1_i": ({2},)},
            {},
        ),
    ],
)
def test_qubit_measurement_tracker(
    ir: str,
    qubit_name_to_nums: dict[str, int],
    state_name_to_num_lists: dict[str, list[int]],
    reg_name_to_num_lists: dict[str, list[int]],
    meas_name_to_nums: dict[str, int],
    xdsl_context: Context,
):
    """Test that QubitMeasurementTracker correctly tracks qubits and measurements."""
    module_op = parse_ir(ir, xdsl_context)
    tracker = QubitMeasurementTracker.walk_module(module_op)

    used_qubit_names = set()
    for qubit_ssa in tracker.get_tracked_qubit_ssas():
        name = qubit_ssa.name_hint
        assert name is not None
        assert qubit_name_to_nums[name] == tracker.get_possible_qubit_nums(qubit_ssa)
        used_qubit_names.add(name)
    assert used_qubit_names == set(qubit_name_to_nums.keys())

    used_reg_names = set()
    for reg_ssa in tracker.get_tracked_register_ssas():
        name = reg_ssa.name_hint
        assert name is not None
        assert reg_name_to_num_lists[name] == tracker.get_possible_qubit_nums_from_register(reg_ssa)
        used_reg_names.add(name)
    assert used_reg_names == set(reg_name_to_num_lists.keys())

    used_state_names = set()
    for state_ssa in tracker.get_tracked_state_ssas():
        name = state_ssa.name_hint
        assert name is not None
        assert state_name_to_num_lists[name] == tracker.get_possible_qubit_nums_from_state(
            state_ssa
        )
        used_state_names.add(name)
    assert used_state_names == set(state_name_to_num_lists.keys())

    used_meas_names = set()
    for meas_ssa in tracker.get_tracked_measurement_ssas():
        name = meas_ssa.name_hint
        assert name is not None
        assert tracker.is_measurement(meas_ssa)
        assert meas_name_to_nums[name] == tracker.get_possible_qubit_nums_from_meas(meas_ssa)
        used_meas_names.add(name)
    assert used_meas_names == set(meas_name_to_nums.keys())


def test_qubit_measurement_tracker_invalid_qubit_ssa(unknown_ssa_value: SSAValue):
    """Test that QubitMeasurementTracker.get_possible_qubit_nums errors on
    an unknown qubit SSA value."""
    tracker = QubitMeasurementTracker()
    with pytest.raises(ValueError, match=re.escape("Qubit SSA value not registered")):
        tracker.get_possible_qubit_nums(unknown_ssa_value)


def test_qubit_measurement_tracker_invalid_register_ssa(unknown_ssa_value: SSAValue):
    """Test that QubitMeasurementTracker.get_possible_qubit_nums_from_register errors on
    an unknown register SSA."""
    tracker = QubitMeasurementTracker()
    with pytest.raises(ValueError, match=re.escape("Qubit register SSA value not registered")):
        tracker.get_possible_qubit_nums_from_register(unknown_ssa_value)


def test_qubit_measurement_tracker_invalid_state_ssa(unknown_ssa_value: SSAValue):
    """Test that QubitMeasurementTracker.get_possible_qubit_nums_from_state errors on
    an unknown state SSA."""
    tracker = QubitMeasurementTracker()
    with pytest.raises(ValueError, match=re.escape("Stabiliser state SSA value not registered")):
        tracker.get_possible_qubit_nums_from_state(unknown_ssa_value)


def test_qubit_measurement_tracker_invalid_measurement_ssa(unknown_ssa_value: SSAValue):
    """Test that QubitMeasurementTracker.get_possible_qubit_nums_from_meas errors on
    an unknown measurement SSA."""
    tracker = QubitMeasurementTracker()
    with pytest.raises(ValueError, match=re.escape("Measurement SSA value not registered")):
        tracker.get_possible_qubit_nums_from_meas(unknown_ssa_value)


@pytest.mark.parametrize(
    ("ir", "meas_name_to_locations"),
    [
        ("builtin.module {}", {}),
        (
            """
            builtin.module {
                %q0 = qcore.alloc_qubit -> !qcore.qubit
                %s0 = stab.state.make (%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
                %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []>
                                      -> !stab.state<1 x !qcore.qubit, []>
                  with (%q0_b : !qcore.qubit), () {
                    %m0 = qref.measure<Z> (%q0_b) -> i1
                    stab.yield []
                  }
            }
            """,
            {"m0": []},
        ),
        (
            """
            builtin.module {
                %q0 = qcore.alloc_qubit<coords=[(1.0, 2.0)]> -> !qcore.qubit
                %s0 = stab.state.make (%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
                %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []>
                                      -> !stab.state<1 x !qcore.qubit, []>
                  with (%q0_b : !qcore.qubit), () {
                    %m0 = qref.measure<Z> (%q0_b) -> i1
                    stab.yield []
                  }
            }
            """,
            {"m0": [(1.0, 2.0)]},
        ),
        (
            # Multiple possible locations
            """
            builtin.module {
                %q0 = qcore.alloc_qubit<coords=[(1.0, 2.0)]> -> !qcore.qubit
                %q1 = qcore.alloc_qubit<coords=[(3.0, 4.0)]> -> !qcore.qubit
                %b = "test.op"() : () -> i1
                %q2 = scf.if %b -> (!qcore.qubit) {
                    scf.yield %q0 : !qcore.qubit
                } else {
                    scf.yield %q1 : !qcore.qubit
                }
                %s0 = stab.state.make (%q2 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
                %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []>
                                      -> !stab.state<1 x !qcore.qubit, []>
                  with (%q2_b : !qcore.qubit), () {
                    %m0 = qref.measure<Z> (%q2_b) -> i1
                    stab.yield []
                  }
            }
            """,
            {"m0": [(1.0, 2.0), (3.0, 4.0)]},
        ),
        (
            """
            builtin.module {
                %q0 = qcore.alloc_qubit<coords=[(1.0, 2.0)]> -> !qcore.qubit
                %q1 = qcore.alloc_qubit<coords=[(3.0, 4.0)]> -> !qcore.qubit
                %b = "test.op"() : () -> i1
                %m2 = scf.if %b -> (i1) {
                    %s0 = stab.state.make (%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
                    %s1, %m0 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []>
                                               -> !stab.state<1 x !qcore.qubit, []>
                      with (%q0_b : !qcore.qubit), () {
                        %m0_i = qref.measure<Z> (%q0_b) -> i1
                        stab.yield [] %m0_i : i1
                      }
                    scf.yield %m0 : i1
                } else {
                    %s2 = stab.state.make (%q1 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
                    %s3, %m1 = stab.circuit %s2 : !stab.state<1 x !qcore.qubit, []>
                                               -> !stab.state<1 x !qcore.qubit, []>
                      with (%q1_b : !qcore.qubit), () {
                        %m1_i = qref.measure<Z> (%q1_b) -> i1
                        stab.yield [] %m1_i : i1
                      }
                    scf.yield %m1 : i1
                }
            }
            """,
            {
                "m0": [(1.0, 2.0)],
                "m1": [(3.0, 4.0)],
                "m0_i": [(1.0, 2.0)],
                "m1_i": [(3.0, 4.0)],
                "m2": [(1.0, 2.0), (3.0, 4.0)],
            },
        ),
        (
            # Ignores possible qubits without locations
            """
            builtin.module {
                %q0 = qcore.alloc_qubit<coords=[(1.0, 2.0)]> -> !qcore.qubit
                %q1 = qcore.alloc_qubit -> !qcore.qubit
                %b = "test.op"() : () -> i1
                %q2 = scf.if %b -> (!qcore.qubit) {
                    scf.yield %q0 : !qcore.qubit
                } else {
                    scf.yield %q1 : !qcore.qubit
                }
                %s0 = stab.state.make (%q2 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
                %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []>
                                      -> !stab.state<1 x !qcore.qubit, []>
                  with (%q2_b : !qcore.qubit), () {
                    %m0 = qref.measure<Z> (%q2_b) -> i1
                    stab.yield []
                  }
            }
            """,
            {"m0": [(1.0, 2.0)]},
        ),
        (
            # Assigns coords to qubits in registers correctly
            """
            builtin.module {
                %r0 = qcore.alloc_qubit<coords=[(1.0, 2.0), (3.0, 4.0)]> -> !qcore.qubit_reg<2>
                %m2, %r2 = qstruct.circuit(%r0 : !qcore.qubit_reg<2>)
                        -> i1, !qcore.qubit_reg<2> {
                ^bb0(%r1 : !qcore.qubit_reg<2>):
                    %q0, %q1 = qcore.unpack_qubit_reg(%r1 : !qcore.qubit_reg<2>)
                    %m0 = qref.measure<Z> (%q0) -> i1
                    %m1 = qref.measure<Z> (%q1) -> i1
                    qstruct.yield %m0, %r1 : i1, !qcore.qubit_reg<2>
                }
            }
            """,
            {"m0": [(1.0, 2.0)], "m1": [(3.0, 4.0)], "m2": [(1.0, 2.0)]},
        ),
        (
            # Including when allocating qubits and registers at the same time
            """
            builtin.module {
                %r0, %q1, %r1 = qcore.alloc_qubit
                    <coords=[(1.0, 2.0), (3.0, 4.0), (5.0, 6.0), (7.0, 8.0)]>
                    -> !qcore.qubit_reg<1>, !qcore.qubit, !qcore.qubit_reg<2>
                %r3 = qstruct.circuit(%r0, %q1, %r1 : !qcore.qubit_reg<1>, !qcore.qubit,
                        !qcore.qubit_reg<2>) -> !qcore.qubit_reg<4> {
                ^bb0(%r0_b : !qcore.qubit_reg<1>, %q1_b : !qcore.qubit,
                     %r1_b : !qcore.qubit_reg<2>):
                    %q2 = qcore.unpack_qubit_reg(%r0_b : !qcore.qubit_reg<1>)
                    %q3, %q4 = qcore.unpack_qubit_reg(%r1_b : !qcore.qubit_reg<2>)
                    %m0 = qref.measure<Z> (%q1_b) -> i1
                    %m1 = qref.measure<Z> (%q2) -> i1
                    %m2 = qref.measure<Z> (%q3) -> i1
                    %m3 = qref.measure<Z> (%q4) -> i1
                    %r3_i = qcore.pack_qubit_reg(%q1_b, %q2, %q3, %q4) -> !qcore.qubit_reg<4>
                    qstruct.yield %r3_i : !qcore.qubit_reg<4>
                }
            }
            """,
            {"m0": [(3.0, 4.0)], "m1": [(1.0, 2.0)], "m2": [(5.0, 6.0)], "m3": [(7.0, 8.0)]},
        ),
    ],
)
def test_qubit_measurement_location_tracker(
    ir: str,
    meas_name_to_locations: dict[str, list[tuple[float, ...]]],
    xdsl_context: Context,
):
    """Test that QubitMeasurementCoordinateTracker correctly tracks locations."""
    module_op = parse_ir(ir, xdsl_context)
    tracker = QubitMeasurementCoordinateTracker.walk_module(module_op)

    used_meas_names = set()
    for meas_ssa in tracker.get_tracked_measurement_ssas():
        name = meas_ssa.name_hint
        assert name is not None
        possible_locations = tracker.get_possible_measurement_coords(meas_ssa)
        expected_locations = meas_name_to_locations[name]
        assert [location.data for location in possible_locations] == expected_locations
        used_meas_names.add(name)
    assert used_meas_names == set(meas_name_to_locations.keys())


def test_qubit_measurement_location_tracker_invalid_measurement_ssa(
    unknown_ssa_value: SSAValue,
):
    """Test that QubitMeasurementCoordinateTracker.get_possible_measurement_coords errors on
    an unknown measurement SSA."""
    tracker = QubitMeasurementCoordinateTracker()
    with pytest.raises(ValueError, match=re.escape("Measurement SSA value not registered")):
        tracker.get_possible_measurement_coords(unknown_ssa_value)
