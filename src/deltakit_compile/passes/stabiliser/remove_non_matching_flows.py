# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Rewrite patterns for removing stabiliser flows which do not match up to stabiliser flows on
surrounding circuits."""

from dataclasses import dataclass

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ArrayAttr, ModuleOp
from xdsl.ir import SSAValue
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    GreedyRewritePatternApplier,
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)

from deltakit_compile.dialects import qcore
from deltakit_compile.dialects import stabiliser as stab
from deltakit_compile.passes.stabiliser._common import WriteFlows


def _succeeding_circuit(state: SSAValue) -> stab.CircuitOp | None:
    if state.has_more_than_one_use():
        msg = "Expected a stab.circuit output to have at most one use."
        raise ValueError(msg)
    user = state.get_user_of_unique_use()
    if isinstance(user, stab.CircuitOp):
        return user
    return None


class _RemoveNonMatchingFlows(RewritePattern):
    """Remove stabiliser flows from a circuit which do not match its neighbouring circuits.
    Only directly adjacent circuits are supported.
    Only flows marked as droppable will be considered for removal."""

    @staticmethod
    def _flow_state_used_in_circuit(
        flow_state: qcore.PauliStringAttr,
        circuit: stab.CircuitOp | None,
        check_inputs: bool,
    ) -> bool:
        if circuit is None:
            return False
        return flow_state in (
            circuit.used_input_flow_states if check_inputs else circuit.used_output_flow_states
        )

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stab.CircuitOp, rewriter: PatternRewriter) -> None:
        if op.flows is None or stab.ConcreteFlowArrayAttr.DROPPABLE_FLOWS_KEY not in op.attributes:
            return

        preceding_circuit = op.input.owner if isinstance(op.input.owner, stab.CircuitOp) else None
        succeeding_circuit = _succeeding_circuit(op.output)

        filtered_flows = [
            flow
            for flow in op.flows
            if (
                flow.is_creation_flow
                or self._flow_state_used_in_circuit(
                    op.input_flows[flow.input_state_index], preceding_circuit, check_inputs=False
                )
            )
            and (
                flow.is_destruction_flow
                or self._flow_state_used_in_circuit(
                    op.output_flows[flow.output_state_index], succeeding_circuit, check_inputs=True
                )
            )
        ]
        if len(filtered_flows) == len(op.flows):
            return

        op.flows = ArrayAttr(filtered_flows)
        rewriter.notify_op_modified(op)

        # Notify all neighbouring circuits so their flows can be filtered in response to the flows
        # removed here.
        for circuit in (preceding_circuit, succeeding_circuit):
            if circuit is not None:
                rewriter.notify_op_modified(circuit)


class _RemoveUnusedFlowStates(RewritePattern):
    """Remove output flow states that are unused by the circuit chain."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stab.CircuitOp, rewriter: PatternRewriter) -> None:
        if stab.ConcreteFlowArrayAttr.DROPPABLE_FLOWS_KEY not in op.attributes:
            return
        succeeding_circuit = _succeeding_circuit(op.output)
        used_flow_states = set(op.used_output_flow_states)
        if succeeding_circuit is not None:
            used_flow_states.update(succeeding_circuit.used_input_flow_states)

        flow_states_to_remove = set(op.output.type.states) - used_flow_states
        WriteFlows.remove_flow_states_from_output(op, flow_states_to_remove, rewriter)


@dataclass(frozen=True)
class RemoveNonMatchingFlows(ModulePass):
    """Remove all flows from stabiliser circuits which do not match up with adjacent circuits.

    As this will remove user-specified flows, it should be used only when a full set of flows are
    annotated, possibly including spurious extra flows, such as in the output from the patch
    lowering pipeline.

    Also removes flow states from the output stab.states of stabiliser circuits which are not used
    by the adjacent circuits.

    Supports only linear chains of circuits (no casts or control flow). Does not support parallel.
    """

    name = "remove-non-matching-flows"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [
                    _RemoveNonMatchingFlows(),
                    _RemoveUnusedFlowStates(),
                ]
            ),
            apply_recursively=True,
        ).rewrite_module(op)
