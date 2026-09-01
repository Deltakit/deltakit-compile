"""Tests for the existing-detectors utility."""

import pytest
from xdsl.context import Context
from xdsl.dialects import test
from xdsl.dialects.builtin import ModuleOp

from deltakit_compile.dialects import qec
from deltakit_compile.dialects import stabiliser as stab
from deltakit_compile.passes.stabiliser._existing_detectors import (
    ExistingDetectors,
    add_detectors_if_independent,
)
from tests.unit.conftest import compute_name_to_ssa, parse_ir


@pytest.mark.parametrize(
    ("ir", "expected"),
    [
        (
            """
            %state0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
            %state1 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
                                          -> !stab.state<1 x !qcore.qubit, []>
              with (%q0_b : !qcore.qubit), () {
                %m0 = qref.measure<Z> (%q0_b) -> i1
                %m1 = qref.measure<Z> (%q0_b) -> i1
                stab.yield []
              }
            """,
            [([], True), (["m0"], False), (["m1"], False), (["m0", "m1"], False)],
        ),
        (
            """
            %state0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
            %state1 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
                                          -> !stab.state<1 x !qcore.qubit, []>
              with (%q0_b : !qcore.qubit), () {
                %m0 = qref.measure<Z> (%q0_b) -> i1
                %m1 = qref.measure<Z> (%q0_b) -> i1
                qec.detector(%m0)
                stab.yield []
              }
            """,
            [([], True), (["m0"], True), (["m1"], False), (["m0", "m1"], False)],
        ),
        (
            """
            %state0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
            %state1 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
                                          -> !stab.state<1 x !qcore.qubit, []>
              with (%q0_b : !qcore.qubit), () {
                %m0 = qref.measure<Z> (%q0_b) -> i1
                %m1 = qref.measure<Z> (%q0_b) -> i1
                %m2 = qref.measure<Z> (%q0_b) -> i1
                qec.detector(%m0, %m1)
                qec.detector(%m0, %m2)
                stab.yield []
              }
            """,
            [
                ([], True),
                (["m0"], False),
                (["m1"], False),
                (["m2"], False),
                (["m0", "m1"], True),
                (["m0", "m2"], True),
                (["m1", "m2"], True),
                (["m0", "m1", "m2"], False),
            ],
        ),
        (
            # tracing through previous circuit ops
            """
            %state0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
            %state1, %n0 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
                                               -> !stab.state<1 x !qcore.qubit, []>
              with (%q0_b : !qcore.qubit), () {
                %m0 = qref.measure<Z> (%q0_b) -> i1
                stab.yield [] %m0 : i1
              }
            %state2 = stab.circuit %state1 : !stab.state<1 x !qcore.qubit, []>
                                          -> !stab.state<1 x !qcore.qubit, []>
              with (%q1_b : !qcore.qubit), (%m1 = %n0 : i1) {
                %m2 = qref.measure<Z> (%q1_b) -> i1
                %m3 = qref.measure<Z> (%q1_b) -> i1
                qec.detector(%m1, %m2)
                qec.detector(%m1, %m3)
                stab.yield []
              }
            """,
            [
                ([], True),
                (["m1"], False),
                (["m2"], False),
                (["m3"], False),
                (["m1", "m2"], True),
                (["m1", "m3"], True),
                (["m2", "m3"], True),
                (["m1", "m2", "m3"], False),
            ],
        ),
        (
            # tracing through parallel ops
            """
            %b0 = "test.op"() : () -> i1
            %b3, %b4, %b5 = qstruct.parallel<TOP> -> i1, i1, i1 {
                %b1 = "test.op"() : () -> i1
                qstruct.yield %b0, %b1 : i1, i1
            } {
                %b2 = "test.op"() : () -> i1
                qstruct.yield %b2 : i1
            }
            %state0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
            %state1 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
                                          -> !stab.state<1 x !qcore.qubit, []>
              with (%q0_b : !qcore.qubit), (%m0 = %b0 : i1, %m1 = %b3 : i1, %m2 = %b4 : i1,
                                           %m3 = %b5 : i1) {
                qec.detector(%m0, %m2)
                qec.detector(%m3)
                stab.yield []
              }
            """,
            [
                ([], True),
                (["m0"], False),
                (["m1"], False),
                (["m2"], False),
                (["m3"], True),
                (["m0", "m2"], True),
                (["m0", "m3"], False),
                (["m1", "m2"], True),
                (["m1", "m3"], False),
                (["m2", "m3"], False),
                (["m0", "m1", "m2"], False),
                (["m0", "m1", "m3"], True),  # note m0 = m1 so this is just m3
                (["m0", "m2", "m3"], True),
                (["m1", "m2", "m3"], True),
                (["m0", "m1", "m2", "m3"], False),
            ],
        ),
    ],
)
def test_in_span(ir: str, expected: list[tuple[list[str], bool]], xdsl_context: Context):
    """Test in_span correctly identifies whether detectors are in the span of existing detectors."""
    module_op = parse_ir(ir, xdsl_context)
    name_to_ssa = compute_name_to_ssa(module_op)

    # Pick the last circuit op
    circuit_op = next(op for op in reversed(module_op.ops) if isinstance(op, stab.CircuitOp))

    existing_detectors = ExistingDetectors(circuit_op)

    for meas_names, in_span in expected:
        measurements = [name_to_ssa[name] for name in meas_names]
        assert existing_detectors.in_span(measurements) == in_span


@pytest.fixture
def example_module(xdsl_context: Context) -> ModuleOp:
    """An example circuit IR for testing the existing detectors functionality."""
    ir = """
        %state0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
        %state1, %n0 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
                                           -> !stab.state<1 x !qcore.qubit, []>
          with (%q0_b : !qcore.qubit), () {
            %m0 = qref.measure<Z> (%q0_b) -> i1
            stab.yield [] %m0 : i1
          }
        %state2 = stab.circuit %state1 : !stab.state<1 x !qcore.qubit, []>
                                      -> !stab.state<1 x !qcore.qubit, []>
          with (%q1_b : !qcore.qubit), (%m1 = %n0 : i1) {
            %m2 = qref.measure<Z> (%q1_b) -> i1
            %m3 = qref.measure<Z> (%q1_b) -> i1
            %m4 = qref.measure<Z> (%q1_b) -> i1
            qec.detector(%m2, %m3)
            stab.yield []
          }
    """
    return parse_ir(ir, xdsl_context)


def test_in_span_unknown_measurement(example_module: ModuleOp):
    """Test in_span returns False for an unknown measurement, but they can cancel out."""
    name_to_ssa = compute_name_to_ssa(example_module)
    circuit_op = next(op for op in reversed(example_module.ops) if isinstance(op, stab.CircuitOp))
    unknown_ssa = test.TestOp(result_types=[test.TestType("A")]).results[0]

    existing_detectors = ExistingDetectors(circuit_op)
    existing_detectors.add_detector([name_to_ssa["m2"]])

    assert not existing_detectors.in_span([unknown_ssa])
    assert not existing_detectors.in_span([name_to_ssa["m2"], unknown_ssa])

    # putting the unknown measurement twice should cancel it out
    assert existing_detectors.in_span([unknown_ssa, unknown_ssa])
    assert existing_detectors.in_span([name_to_ssa["m2"], unknown_ssa, unknown_ssa])

    # but three times is the same as once
    assert not existing_detectors.in_span([unknown_ssa, unknown_ssa, unknown_ssa])


def test_add_detector(example_module: ModuleOp):
    """Test that add_detector correctly adds new detectors."""
    name_to_ssa = compute_name_to_ssa(example_module)
    circuit_op = next(op for op in reversed(example_module.ops) if isinstance(op, stab.CircuitOp))

    existing_detectors = ExistingDetectors(circuit_op)

    def add_detector(meas_names: list[str]) -> None:
        measurements = [name_to_ssa[name] for name in meas_names]
        existing_detectors.add_detector(measurements)

    # Already existing detector
    add_detector(["m2", "m3"])
    assert existing_detectors.in_span([name_to_ssa["m2"], name_to_ssa["m3"]])
    assert not existing_detectors.in_span([name_to_ssa["m2"]])

    # New detector with new measurement
    add_detector(["m1", "m2"])
    assert existing_detectors.in_span([name_to_ssa["m1"], name_to_ssa["m2"]])
    assert existing_detectors.in_span([name_to_ssa["m2"], name_to_ssa["m3"]])
    assert existing_detectors.in_span([name_to_ssa["m1"], name_to_ssa["m3"]])
    assert not existing_detectors.in_span([name_to_ssa["m1"]])
    assert not existing_detectors.in_span([name_to_ssa["m2"]])
    assert not existing_detectors.in_span([name_to_ssa["m3"]])

    # New detector with existing measurement
    add_detector(["m1"])
    assert existing_detectors.in_span([name_to_ssa["m1"], name_to_ssa["m2"]])
    assert existing_detectors.in_span([name_to_ssa["m2"], name_to_ssa["m3"]])
    assert existing_detectors.in_span([name_to_ssa["m1"], name_to_ssa["m3"]])
    assert existing_detectors.in_span([name_to_ssa["m1"]])
    assert existing_detectors.in_span([name_to_ssa["m2"]])
    assert existing_detectors.in_span([name_to_ssa["m3"]])


def test_no_initial_op(example_module: ModuleOp):
    """Test that ExistingDetectors can be initialised with no circuit op."""
    name_to_ssa = compute_name_to_ssa(example_module)

    def add_detector(meas_names: list[str]) -> None:
        measurements = [name_to_ssa[name] for name in meas_names]
        existing_detectors.add_detector(measurements)

    existing_detectors = ExistingDetectors()
    assert existing_detectors.in_span([])  # empty detector is always in span
    assert not existing_detectors.in_span([name_to_ssa["m1"]])  # new measurement is not in span

    add_detector(["m1"])
    assert existing_detectors.in_span([name_to_ssa["m1"]])  # now in span
    assert not existing_detectors.in_span([name_to_ssa["m2"]])  # new measurement is not in span

    add_detector(["m2"])
    assert existing_detectors.in_span([name_to_ssa["m1"]])
    assert existing_detectors.in_span([name_to_ssa["m1"], name_to_ssa["m2"]])


@pytest.mark.parametrize(
    ("detectors_to_add_by_name", "expected_detectors_by_name"),
    [
        (
            [],
            [("m2", "m3")],
        ),
        (
            [("m1",)],
            [("m2", "m3"), ("m1",)],
        ),
        (
            [("m2", "m3")],
            [("m2", "m3")],
        ),
        (
            [("m3", "m2")],
            [("m2", "m3")],
        ),
        (
            [("m1", "m2")],
            [("m2", "m3"), ("m1", "m2")],
        ),
        (
            [("m1", "m2"), ("m1", "m3")],
            [("m2", "m3"), ("m1", "m2")],
        ),
        (
            # doesn't add empty detector
            [()],
            [("m2", "m3")],
        ),
    ],
)
def test_add_detectors_if_independent(
    detectors_to_add_by_name: list[tuple[str, ...]],
    expected_detectors_by_name: list[tuple[str, ...]],
    example_module: ModuleOp,
):
    """Test that add_detectors_if_independent adds only the expected detectors."""
    name_to_ssa = compute_name_to_ssa(example_module)
    circuit_op = next(op for op in reversed(example_module.ops) if isinstance(op, stab.CircuitOp))

    detectors_to_add = [
        qec.DetectorOp([name_to_ssa[name] for name in meas_names])
        for meas_names in detectors_to_add_by_name
    ]
    expected_detectors = [
        qec.DetectorOp([name_to_ssa[name] for name in meas_names])
        for meas_names in expected_detectors_by_name
    ]

    add_detectors_if_independent(circuit_op, detectors_to_add)

    actual_detectors = [op for op in circuit_op.body.ops if isinstance(op, qec.DetectorOp)]
    assert len(actual_detectors) == len(expected_detectors)
    for actual, expected in zip(actual_detectors, expected_detectors, strict=True):
        assert len(actual.measurements) == len(expected.measurements)
        for actual_target, expected_target in zip(
            actual.measurements, expected.measurements, strict=True
        ):
            assert actual_target == expected_target
