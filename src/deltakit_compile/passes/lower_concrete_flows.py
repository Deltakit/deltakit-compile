# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Pass lowering stab.concrete_flow_array attributes to flows directly on stabiliser circuits."""

from dataclasses import dataclass
from typing import cast

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import I1, ModuleOp
from xdsl.ir import SSAValue
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.utils.hints import isa

from deltakit_compile.dialects import stabiliser as stab
from deltakit_compile.passes.stabiliser._common import (
    CircuitFlowData,
    MMTResults,
    WriteFlows,
)


class _LowerConcreteFlows(RewritePattern):
    """Lower concrete flow attributes directly onto stabiliser circuit ops."""

    @staticmethod
    def _concrete_flow_to_flow_data(
        op: stab.CircuitOp, concrete_flow: stab.ConcreteFlowAttr
    ) -> CircuitFlowData:
        if concrete_flow.input_state.length.data != cast(stab.StateType, op.input.type).qubits.data:
            msg = (
                f"The number of qubits in a {concrete_flow.name} does not match "
                f"the number of qubits in its parent {op.name}"
            )
            raise ValueError(msg)

        output_measurements = concrete_flow.get_measurement_values(op)
        yielded_measurements = [op.output_arg_to_yield_arg(meas) for meas in output_measurements]

        if not isa(yielded_measurements, list[SSAValue[I1]]):
            bad_type_ssas = [ssa for ssa in yielded_measurements if not isa(ssa, SSAValue[I1])]
            formatted_types = ", ".join(
                str(ssa.type) + (f" (%{ssa.name_hint})" if ssa.name_hint else "")
                for ssa in bad_type_ssas
            )
            msg = (
                "Stabiliser flow measurement values are of wrong type: expected all i1, got "
                + formatted_types
            )
            raise TypeError(msg)

        return CircuitFlowData(
            input_state=concrete_flow.input_state,
            output_state=concrete_flow.output_state,
            measurements=MMTResults(yielded_measurements),
        )

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stab.CircuitOp, rewriter: PatternRewriter) -> None:
        concrete_flow_array = stab.ConcreteFlowArrayAttr.get(op)
        if concrete_flow_array is None:
            return

        del op.attributes[stab.ConcreteFlowArrayAttr.KEY]
        rewriter.notify_op_modified(op)

        flow_data = [
            self._concrete_flow_to_flow_data(op, concrete_flow)
            for concrete_flow in concrete_flow_array.flows
        ]

        WriteFlows.update_circuit_op(flow_data, op, rewriter)


@dataclass(frozen=True)
class LowerConcreteFlows(ModulePass):
    """Lowers stab.concrete_flow_array attributes on stabiliser circuits to flows annotated directly
    on the stabiliser circuit ops and flow states on their surrounding stabiliser state types.

    Any stab.circuit op with a stab.concrete_flow_array attribute will have that attribute removed
    and the corresponding flow will be written onto the circuit. The flow states of the input and
    output state type, and the flows in the previous and next circuits, will be adjusted to include
    the input and output flow states of the new flows.

    Does not yet support control flow.

    TODO: Add support for control flow operations
    """

    name = "lower-concrete-flows"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        PatternRewriteWalker(_LowerConcreteFlows(), apply_recursively=False).rewrite_module(op)
