# (c) Copyright Riverlane 2025-2026. All rights reserved.

"""Implement the ``annotate-flows-from-plaquettes`` pass that adds Pauli-flow annotations to
``qstruct.circuit`` operations containing ``plaquette.plaquette`` operations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from typing_extensions import override
from xdsl.dialects.builtin import I1, ModuleOp, NoneAttr, UnitAttr, i1
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    GreedyRewritePatternApplier,
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.utils.hints import isa

from deltakit_compile.dialects import plaquette, qstruct
from deltakit_compile.dialects.qcore import PauliStringAttr, qubit_count
from deltakit_compile.dialects.stabiliser import ConcreteFlowArrayAttr, ConcreteFlowAttr


@dataclass
class _AnnotateFlowOnSynchronisedSchedulePlaquetteOpPattern(RewritePattern):
    """Annotate the Pauli-flow on the matched ``plaquette.plaquette`` operations if supported.

    ``plaquette.plaquette`` operations supported by this pattern check all the conditions below:

    - Its stabiliser measurement method is an instance of ``SynchronisedScheduleAttr``.
    - All the entries of ``schedule`` in the stabiliser measurement method should be integers.
    - It does not have any attribute under the key ``ConcreteFlowArrayAttr.KEY``.

    This pass assumes that the ``plaquette.plaquette`` correctly measures the stabilisers. In
    particular, if the schedules of the ``plaquette.plaquette`` operations are wrong (e.g., leave
    some qubits entangled and so do not measure the correct stabilisers when considered as a whole)
    this pass will generate wrong Pauli flows.
    """

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: plaquette.PlaquetteOp, rewriter: PatternRewriter) -> None:
        if (
            not isinstance(
                stab_measurement_method := op.stabs_measurement, plaquette.SynchronisedScheduleAttr
            )
            or any(isinstance(schedule, NoneAttr) for schedule in stab_measurement_method.schedule)
            or ConcreteFlowArrayAttr.KEY in op.attributes
        ):
            return
        # The plaquette will have the flows:
        #     I -> STAB {meas}
        #     STAB -> I {meas}
        # Where STAB is the stabiliser measured, I is the identity and meas is the measurement
        # returned by the plaquette.
        stabiliser = op.stabilisers.data[0]
        identity = PauliStringAttr.identity(stabiliser.length.data)
        # We use ``[0]`` as the measurement representing the stabiliser measurement here because we
        # know that we have a ``SynchronisedScheduleAttr``, which only returns a single measurement,
        # and the matched ``plaquette.plaquette`` should also have a single measurement (per
        # constraints).
        op.attributes[ConcreteFlowArrayAttr.KEY] = ConcreteFlowArrayAttr(
            [
                ConcreteFlowAttr("+", [0], identity, stabiliser),
                ConcreteFlowAttr("+", [0], stabiliser, identity),
            ]
        )
        rewriter.notify_op_modified(op)


@dataclass
class _BubbleUpPlaquetteFlowsToRoundOpPattern(RewritePattern):
    """Annotate the Pauli-flow on the matched ``plaquette.round`` operations if supported.

    ``plaquette.round`` operations supported by this pattern check all the conditions below:

    - All of its children ``plaquette.plaquette`` operations have a Pauli flow annotation in their
      attr-dict under the key ``ConcreteFlowArrayAttr.KEY``.
    - It does not have any attribute under the key ``ConcreteFlowArrayAttr.KEY``.
    """

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: plaquette.RoundOp, rewriter: PatternRewriter) -> None:
        plaquette_ops = [
            child
            for par_region in op.par_regions
            for child in par_region.block.ops
            if isinstance(child, plaquette.PlaquetteOp)
        ]
        if (
            any(ConcreteFlowArrayAttr.KEY not in p_op.attributes for p_op in plaquette_ops)
            or ConcreteFlowArrayAttr.KEY in op.attributes
        ):
            return
        # The ``plaquette.round`` operation will aggregate the flows of its children
        # ``plaquette.plaquette`` operations. There is some bookkeeping to do to modify the indices
        # because the round operation will gather all the qubits / measurements of the
        # ``plaquette.plaquette`` operations.
        merged_flows = list[ConcreteFlowAttr]()
        yielded_values = op.get_yielded_values()
        num_qubits = len(op.qubits)

        for plaquette_op in plaquette_ops:
            flows = plaquette_op.attributes.get(ConcreteFlowArrayAttr.KEY)
            assert isinstance(flows, ConcreteFlowArrayAttr), (
                "Should be guaranteed as an internal invariant of the pass."
            )
            # Compute the map from ``plaquette_op.data_qubits`` indices to indices of the parent
            # ``RoundOp``.
            parent_block = plaquette_op.parent_block()
            assert parent_block is not None, "Checked by constraints."
            qubit_map: dict[int, int] = {
                i: parent_block.args.index(qssa) for i, qssa in enumerate(plaquette_op.data_qubits)
            }
            measurement_map: dict[int, int] = {
                i: yielded_values.index(res)
                for i, res in enumerate(plaquette_op.results)
                if res.type == i1
            }
            # Then for each flow, map each measurement index to the corresponding measurement index
            # in the results of ``op`` and each input/output Pauli flow to the qubits given as
            # operands to ``op``.
            for flow in flows.flows:
                merged_flows.append(
                    ConcreteFlowAttr(
                        flow.sign,
                        [measurement_map[m] for m in flow.measurement_indices],
                        flow.input_state.map_indices(qubit_map, num_qubits),
                        flow.output_state.map_indices(qubit_map, num_qubits),
                    )
                )

        op.attributes[ConcreteFlowArrayAttr.KEY] = ConcreteFlowArrayAttr(merged_flows)
        rewriter.notify_op_modified(op)


@dataclass
class _AnnotateFlowsOnCircuitFromRoundOpsPattern(RewritePattern):
    """Annotate the Pauli-flow on the matched ``qstruct.circuit`` operations if supported.

    ``qstruct.circuit`` operations supported by this pattern check all the conditions below:

    - All of its children ``plaquette.round`` operations have a Pauli flow annotation in their
      attr-dict under the key ``ConcreteFlowArrayAttr.KEY``.
    - There is only a single ``plaquette.round`` operation in the ``qstruct.circuit``.
    - It does not have any attribute under the key ``ConcreteFlowArrayAttr.KEY``.

    The second condition will eventually be lifted, but helps in simplifying the pattern for now
    by avoiding to have to handle aggregation of Pauli flows when multiple ``plaquette.round``
    operations are used in the ``qstruct.circuit`` and some detectors might have to be annotated.
    This condition is also checked by all the circuits we need to handle for the moment.
    """

    @staticmethod
    def _is_identity_map(mapping: Mapping[int, int]) -> bool:
        return all(k == v for k, v in mapping.items())

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.CircuitOp, rewriter: PatternRewriter) -> None:
        round_ops = [child for child in op.body.block.ops if isinstance(child, plaquette.RoundOp)]
        if len(round_ops) != 1 or ConcreteFlowArrayAttr.KEY in op.attributes:
            return
        round_op = round_ops[0]
        if not isinstance(
            concrete_flow_array_attr := round_op.attributes.get(ConcreteFlowArrayAttr.KEY),
            ConcreteFlowArrayAttr,
        ):
            return
        # The ``qstruct.circuit`` operation will aggregate the flows of its unique child
        # ``plaquette.round`` operation. There is some bookkeeping to do to modify the indices
        # because nothing guarantees that the operations are applied on the same qubit order and
        # return measurements in the same order.
        num_qubits: Final[int] = sum(qubit_count(argt) for argt in op.body.block.arg_types)
        circuit_block_args = op.body.block.args
        qubit_map: dict[int, int] = {
            i: circuit_block_args.index(q) for i, q in enumerate(round_op.operands)
        }
        measurement_map: dict[int, int] = {
            i: op.yield_op.operands.index(res)
            for i, res in enumerate(round_op.results)
            if isa(res.type, I1)
        }

        # Mark any flows added as droppable since they may not perfectly align with other circuits
        op.attributes[ConcreteFlowArrayAttr.DROPPABLE_FLOWS_KEY] = UnitAttr()
        rewriter.notify_op_modified(op)

        # If both maps are the identity, we don't have anything to change so we can directly re-use
        # the round operation attribute.
        if (_AnnotateFlowsOnCircuitFromRoundOpsPattern._is_identity_map(qubit_map)) and (
            _AnnotateFlowsOnCircuitFromRoundOpsPattern._is_identity_map(measurement_map)
        ):
            op.attributes[ConcreteFlowArrayAttr.KEY] = concrete_flow_array_attr
            return
        # Else, we have to map some indices.
        op.attributes[ConcreteFlowArrayAttr.KEY] = ConcreteFlowArrayAttr(
            [
                ConcreteFlowAttr(
                    flow.sign,
                    [measurement_map[mi] for mi in flow.measurement_indices],
                    flow.input_state.map_indices(qubit_map, num_qubits),
                    flow.output_state.map_indices(qubit_map, num_qubits),
                )
                for flow in concrete_flow_array_attr.flows
            ]
        )


@dataclass
class _CleanUpFlowsAnnotationsOnPlaquettesAndRoundsPattern(RewritePattern):
    """Remove the Pauli-flow annotations on all the ``plaquette.round`` and ``plaquette.plaquette``
    operations."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(
        self, op: plaquette.RoundOp | plaquette.PlaquetteOp, rewriter: PatternRewriter
    ) -> None:
        if ConcreteFlowArrayAttr.KEY in op.attributes:
            del op.attributes[ConcreteFlowArrayAttr.KEY]
            rewriter.notify_op_modified(op)


@dataclass(frozen=True)
class AnnotateFlowsFromPlaquettes(ModulePass):
    """Adds Pauli-flow annotations to ``qstruct.circuit`` operations containing
    ``plaquette.plaquette`` operations."""

    name = "annotate-flows-from-plaquettes"

    @override
    def apply(self, ctx, op: ModuleOp) -> None:
        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [
                    _AnnotateFlowOnSynchronisedSchedulePlaquetteOpPattern(),
                    _BubbleUpPlaquetteFlowsToRoundOpPattern(),
                    _AnnotateFlowsOnCircuitFromRoundOpsPattern(),
                ]
            )
        ).rewrite_region(op.body)
        PatternRewriteWalker(_CleanUpFlowsAnnotationsOnPlaquettesAndRoundsPattern()).rewrite_region(
            op.body
        )
