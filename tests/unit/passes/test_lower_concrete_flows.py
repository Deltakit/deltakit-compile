"""Exception tests for lower-concrete-flows pass (functional testing done using filecheck)."""

import re

import pytest
from xdsl.context import Context

from deltakit_compile.passes.lower_concrete_flows import LowerConcreteFlows
from tests.unit.conftest import parse_ir


def test_bad_concrete_flow_num_qubits_error(xdsl_context: Context):
    """Test we get an error when the number of qubits in a concrete flow doesn't match its
    circuit."""

    ir = """
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
    %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []>
                                            -> !stab.state<1 x !qcore.qubit, []>
        with (%q1 : !qcore.qubit), () {
        stab.yield []
        } {stab.flows = #stab.concrete_flow_array<[<+:>{I -> X0 : 2}]>}
    """

    module_op = parse_ir(ir, xdsl_context)

    with pytest.raises(
        ValueError,
        match=re.escape(
            "The number of qubits in a stab.concrete_flow does not match the "
            "number of qubits in its parent stab.circuit"
        ),
    ):
        LowerConcreteFlows().apply(xdsl_context, module_op)


@pytest.mark.parametrize(
    ("ir", "expected_error_types"),
    [
        (
            """
            %q0 = qcore.alloc_qubit -> !qcore.qubit
            %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
            %s1, %1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []>
                                    -> !stab.state<1 x !qcore.qubit, []>
              with (%q1 : !qcore.qubit), () {
                %0 = "test.op"() : () -> i32
                stab.yield [] %0 : i32
              } {stab.flows = #stab.concrete_flow_array<[<+:1>{I -> X0 : 1}]>}
            """,
            "i32",
        ),
        (
            """
            %q0 = qcore.alloc_qubit -> !qcore.qubit
            %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
            %s1, %i1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []>
                                    -> !stab.state<1 x !qcore.qubit, []>
              with (%q1 : !qcore.qubit), () {
                %i0 = "test.op"() : () -> i32
                stab.yield [] %i0 : i32
              } {stab.flows = #stab.concrete_flow_array<[<+:1>{I -> X0 : 1}]>}
            """,
            "i32 (%i0)",
        ),
        (
            """
            %q0 = qcore.alloc_qubit -> !qcore.qubit
            %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
            %s1, %i1, %3, %q2, %4 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []>
                                                    -> !stab.state<1 x !qcore.qubit, []>
              with (%q1 : !qcore.qubit), () {
                %i0, %1, %2 = "test.op"() : () -> (i32, i1, i64)
                stab.yield [] %i0, %1, %q1, %2 : i32, i1, !qcore.qubit, i64
              } {stab.flows = #stab.concrete_flow_array<[<+:1,2,3,4>{I -> X0 : 1}]>}
            """,
            "i32 (%i0), !qcore.qubit (%q1), i64",
        ),
    ],
)
def test_bad_measurement_type_errors(ir: str, expected_error_types: str, xdsl_context: Context):
    """Test we get an error when the concrete flow measurement values are not all of type i1."""
    module_op = parse_ir(ir, xdsl_context)

    with pytest.raises(
        TypeError,
        match=re.escape(
            "Stabiliser flow measurement values are of wrong type: expected all i1, got "
            + expected_error_types
        ),
    ):
        LowerConcreteFlows().apply(xdsl_context, module_op)


def test_non_creation_flow_on_first_circuit_errors(xdsl_context: Context):
    """Test we get an error when the first circuit after a stab.state.make op has a non-creation
    flow annotation, because it would require adding a flow state to the stab.state.make output."""

    ir = """
    builtin.module {
        %q0 = qcore.alloc_qubit -> !qcore.qubit
        %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
        %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []>
                              -> !stab.state<1 x !qcore.qubit, []>
          with (%q1 : !qcore.qubit), () {
            stab.yield []
          } {stab.flows = #stab.concrete_flow_array<[<+:>{X0 -> X0 : 1}]>}
    }
    """
    module_op = parse_ir(ir, xdsl_context)

    with pytest.raises(
        ValueError,
        match=re.escape(
            "The SSAValue is the output of a stab.StateMakeOp which can't have any flow states."
        ),
    ):
        LowerConcreteFlows().apply(xdsl_context, module_op)


@pytest.mark.parametrize(
    ("ir", "expected_error"),
    [
        (
            # Non-commuting flows on the same circuit
            """
            builtin.module {
                %q0 = qcore.alloc_qubit -> !qcore.qubit
                %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
                %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []>
                                    -> !stab.state<1 x !qcore.qubit, []>
                with (%q1 : !qcore.qubit), () {
                    stab.yield []
                } {stab.flows = #stab.concrete_flow_array<[<+:>{I -> X0 : 1}, <+:>{I -> Z0 : 1}]>}
                }
            """,
            "Cannot add flows to state type. #qcore.pauli_string<X0 : 1> and "
            "#qcore.pauli_string<Z0 : 1> do not commute.",
        ),
        (
            # Two flows on consecutive circuits imply non-commuting flow states in between
            """
            builtin.module {
                %q0 = qcore.alloc_qubit -> !qcore.qubit
                %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
                %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []>
                                    -> !stab.state<1 x !qcore.qubit, []>
                with (%q1 : !qcore.qubit), () {
                    stab.yield []
                } {stab.flows = #stab.concrete_flow_array<[<+:>{I -> X0 : 1}]>}
                %s2 = stab.circuit %s1 : !stab.state<1 x !qcore.qubit, []>
                                    -> !stab.state<1 x !qcore.qubit, []>
                with (%q2 : !qcore.qubit), () {
                    stab.yield []
                } {stab.flows = #stab.concrete_flow_array<[<+:>{Z0 -> I : 1}]>}
            }
            """,
            "Cannot add flow #qcore.pauli_string<Z0 : 1> to state type. It does not commute with "
            "existing flow #qcore.pauli_string<X0 : 1> on adjacent circuit.",
        ),
    ],
)
def test_non_commuting_flows_annotated_errors(ir: str, expected_error: str, xdsl_context: Context):
    """Test we get an error when the annotated concrete flows require us to add non-commuting flow
    states to a stab.state type."""

    module_op = parse_ir(ir, xdsl_context)

    with pytest.raises(ValueError, match=re.escape(expected_error)):
        LowerConcreteFlows().apply(xdsl_context, module_op)
