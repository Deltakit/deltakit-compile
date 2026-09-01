# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Pass that validates the stabiliser flow annotations for each CircuitOp in a Module."""

from dataclasses import dataclass
from typing import cast

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import I1, ModuleOp
from xdsl.ir import Operation, SSAValue
from xdsl.passes import ModulePass

from deltakit_compile.dialects.qcore import I_STATE_INDEX, PauliStringAttr
from deltakit_compile.dialects.stabiliser import CircuitOp
from deltakit_compile.exceptions import InvalidStabiliserFlowError
from deltakit_compile.passes.stabiliser._common import (
    CalculateFlows,
    CurrentState,
    FlowChainInfo,
    FlowInSpanStatus,
    MMTResults,
)


@dataclass(frozen=True)
class VerifyFlows(ModulePass):
    """Pass to validate stabiliser flows annotated on 1 circuit op are correct up to sign.

    Computes possible output flow state(s), if any, given each input flow state.
    Accounts for branching of flows due to measurements.

    Will raise errors when:
      - input flow states and/or flow annotations are missing
      - a flow with given input flow state does not exist i.e. is blocked by a gate
      - a flow with given input flow state exists but output state provided does not match
      - the measurements associated with FlowAttr do not match
    """

    name = "verify-flows"

    @staticmethod
    def check_circuit_op(circuit: CircuitOp) -> None:
        """Checks that the flow annotations on a CircuitOp are consistent with the circuit body, up
        to sign.

        For each flow annotation, we propagate the input flow state through the circuit and compare
        the resulting output flow state and measurements with the annotated output flow state and
        measurements.

        Args:
            circuit: The CircuitOp to check.

        Raises:
            ValueError: If any annotated flow is inconsistent with the circuit body.
        """
        ops_list: list[Operation] = list(circuit.body.ops)
        flow_annotations = circuit.flows.data if circuit.flows is not None else ()

        # We must pass the tuple of qubit ssa values used in this circuit with any flow states
        # since all qcore.pauli_state Attributes reference its order.
        qubits: tuple[SSAValue, ...] = tuple(circuit.qubit_block_args)

        for flow in flow_annotations:
            input_idx, output_idx = flow.input_state_index, flow.output_state_index

            if input_idx == I_STATE_INDEX:
                # Since propagate_input_flow_basis propagates a full basis of input flow states,
                # propagating the identity is done by passing an empty basis.
                input_flow_state = PauliStringAttr.identity(len(qubits))
                input_flow_basis: list[FlowChainInfo] = []
                # The indices in the input flow basis that the output is expected to extend - empty
                # for creation flows, {0} for flows extending a non-identity state.
                output_extending_combination = frozenset[int]()
            else:
                input_flow_state = circuit.input_flows[input_idx]
                input_flow_basis = [FlowChainInfo(input_flow_state)]
                output_extending_combination = frozenset({0})

            output_flow_state = (
                circuit.output.type.states[output_idx]
                if output_idx != I_STATE_INDEX
                else PauliStringAttr.identity(len(qubits))
            )

            # compare with dictionary of calculated output when given a basis of just this flow
            expected_output = CalculateFlows.propagate_input_flow_basis(
                input_flow_info=input_flow_basis, qubits=qubits, ops=ops_list
            )

            # Check the desired flow is in the space of propagated flows
            desired_mmts = MMTResults(
                cast(SSAValue[I1], circuit.yield_op.measurements[idx])
                for idx in flow.measurement_indices
            )
            desired_state = CurrentState(
                flow_state=output_flow_state,
                mmt_ssa=desired_mmts,
                extending_combination=output_extending_combination,
            )

            # TODO: Point the user to the circuit causing the error.
            span_result = expected_output.check_in_span(desired_state)
            if span_result.status == FlowInSpanStatus.FLOW_STATE_NOT_IN_SPAN:
                flow_state_basis = [cs.flow_state for cs in span_result.flow_basis]
                msg = (
                    "Input flow state does not propagate to output flow state given. "
                    f"Input flow: {input_flow_state.as_str()}; Desired output: "
                    f"{output_flow_state.as_str()}. Valid flows: span of "
                    f"{PauliStringAttr.collection_as_str(flow_state_basis) or 'none'}."
                )
                raise InvalidStabiliserFlowError(msg)
            if span_result.status == FlowInSpanStatus.MEASUREMENTS_NOT_IN_SPAN:
                # TODO: Tell the user what the measurements are somehow.
                msg = (
                    "Measurement history given does not match given flow annotations. "
                    f"Flow {input_flow_state.as_str()} -> {output_flow_state.as_str()} exists but "
                    f"specified measurement set is not achievable."
                )
                raise InvalidStabiliserFlowError(msg)

            assert span_result.status == FlowInSpanStatus.IN_SPAN, "Unknown flow-in-span status."

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        """Run the validation over all CircuitOp operations in the module."""

        for opn in op.walk():
            if isinstance(opn, CircuitOp):
                VerifyFlows.check_circuit_op(opn)
