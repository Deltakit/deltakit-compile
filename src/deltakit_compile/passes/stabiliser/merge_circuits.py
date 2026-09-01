# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Pass to merge stab.circuit ops together when possible."""

import itertools
from collections import defaultdict
from dataclasses import dataclass

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Attribute, Block, SSAValue
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.rewriter import InsertPoint

from deltakit_compile.dialects import qec
from deltakit_compile.dialects import stabiliser as stab
from deltakit_compile.dialects.qcore import is_quantum_effect_free
from deltakit_compile.passes._use_def_viewer import UseDefViewer
from deltakit_compile.passes.stabiliser._common import verify_circuit_flows_present
from deltakit_compile.passes.stabiliser._existing_detectors import add_detectors_if_independent


def _merge_flows(
    circuit1: stab.CircuitOp, circuit2: stab.CircuitOp
) -> tuple[list[stab.FlowAttr], list[tuple[int, ...]]]:
    """Merge the flows of circuit1 and circuit2 together, returning the new flows and any detectors
    found (represented as tuples of measurement indices). Offset the measurement indices of
    circuit2's flows by the number of measurements in circuit1's yield op.

    The output of circuit1 must match the input of circuit2 and both must have flows specified.
    """
    assert circuit1.output == circuit2.input
    assert circuit1.flows is not None
    assert circuit2.flows is not None

    measurement_offset = len(circuit1.yield_op.measurements)
    offset_circuit2_flows = [
        flow.with_measurement_offset(measurement_offset) for flow in circuit2.flows
    ]

    # Inherit circuit1's destruction flows and circuit2's creation flows
    inherited_destruction_flows = [flow for flow in circuit1.flows if flow.is_destruction_flow]
    inherited_creation_flows = [flow for flow in offset_circuit2_flows if flow.is_creation_flow]
    new_flows = inherited_destruction_flows + inherited_creation_flows

    # Match up remaining flows
    medial_state_type = circuit1.output.type
    circuit1_outputs_to_flows = {
        medial_state_type.states[flow.output_state_index]: flow
        for flow in circuit1.flows
        if not flow.is_destruction_flow
    }
    circuit2_inputs_to_flows = {
        medial_state_type.states[flow.input_state_index]: flow
        for flow in offset_circuit2_flows
        if not flow.is_creation_flow
    }

    detectors: list[tuple[int, ...]] = []
    for medial_flow_state in medial_state_type.flow_states:
        flow1 = circuit1_outputs_to_flows[medial_flow_state]
        flow2 = circuit2_inputs_to_flows[medial_flow_state]

        if flow1.is_creation_flow and flow2.is_destruction_flow:
            # Found a detector; note the concatenated tuple is already in sorted order
            detectors.append(tuple(flow1.measurement_indices) + tuple(flow2.measurement_indices))
        else:
            new_flow = stab.FlowAttr(
                sign=flow1.is_plus == flow2.is_plus,
                measurements=flow1.measurements.data + flow2.measurements.data,
                input_state=flow1.input_state_index,
                output_state=flow2.output_state_index,
            )
            new_flows.append(new_flow)

    return new_flows, detectors


def _match_block_args_to_yields(
    circuit1: stab.CircuitOp, circuit2: stab.CircuitOp
) -> tuple[dict[SSAValue, SSAValue], set[SSAValue]]:
    """Return a mapping of block args in circuit2's body which correspond to yields from circuit1's
    body, to those yield SSA values, as well as the set of medial SSA values in the containing block
    corresponding to those args/yields."""

    # SSA values in the containing block which are output from circuit1 and input back into circuit2
    medial_ssas = set[SSAValue](circuit1.output_args) & set[SSAValue](circuit2.input_args)
    if not medial_ssas:
        return {}, set()

    # Look up each medial SSA value in circuit1's yields and circuit2's block args
    circuit1_outputs_to_yields = dict[SSAValue, SSAValue](
        zip(circuit1.output_args, circuit1.yield_op.arguments, strict=True)
    )
    circuit2_inputs_to_block_args = defaultdict[SSAValue, set[SSAValue]](set)
    for input_arg, block_arg in zip(circuit2.input_args, circuit2.other_block_args, strict=True):
        circuit2_inputs_to_block_args[input_arg].add(block_arg)

    block_args_to_yields = {
        block_arg: circuit1_outputs_to_yields[medial_ssa]
        for medial_ssa in medial_ssas
        for block_arg in circuit2_inputs_to_block_args[medial_ssa]
    }

    return block_args_to_yields, medial_ssas


def _combine_circuit_bodies(
    circuit1: stab.CircuitOp,
    circuit2: stab.CircuitOp,
    block_args_to_yields: dict[SSAValue, SSAValue],
    rewriter: PatternRewriter,
) -> Block:
    """Concatenate circuit1 and circuit2's bodies into a new circuit body.

    Destructive: empties circuit1 and circuit2, which will no longer verify.

    Args:
        circuit1: The first circuit to merge.
        circuit2: The second circuit to merge.
        block_args_to_yields: A mapping of block args of circuit2 which correspond to yields from
            circuit1, to those yield SSA values in circuit1. These block args will be remapped to
            the corresponding yield SSA values in the new body and removed from the block args.
        rewriter: A PatternRewriter to use for constructing the new body.

    Returns:
        A circuit body combining the bodies of circuit1 and circuit2.
    """
    # Block args from circuit2 which are kept in the new body (not mapped to yields from circuit1)
    preserved_circuit2_block_args = tuple(
        arg for arg in circuit2.other_block_args if arg not in block_args_to_yields
    )

    block_arg_types = (
        # Both circuits should have the same number and type of qubit block args
        tuple(arg.type for arg in circuit1.qubit_block_args)
        + tuple(arg.type for arg in circuit1.other_block_args)
        + tuple(arg.type for arg in preserved_circuit2_block_args)
    )
    new_body = Block(arg_types=block_arg_types)

    new_qubit_block_args = new_body.args[: len(circuit1.qubit_block_args)]
    new_other_block_args = new_body.args[len(circuit1.qubit_block_args) :]

    # A map of SSA values to be remapped in the new body once fully constructed
    # Populate by mapping the block args of circuit1 and circuit2 to the new ones in new_body
    remap = dict[SSAValue, SSAValue](
        itertools.chain(
            zip(circuit1.qubit_block_args, new_qubit_block_args, strict=True),
            zip(circuit2.qubit_block_args, new_qubit_block_args, strict=True),
            zip(
                tuple(circuit1.other_block_args) + preserved_circuit2_block_args,
                new_other_block_args,
                strict=True,
            ),
        )
    )
    # Remap block args that correspond to yields from circuit1
    # If the yield arg is going to be remapped, go directly to the final remapped value
    for block_arg, yield_arg in block_args_to_yields.items():
        remap[block_arg] = remap.get(yield_arg, yield_arg)

    new_yield = circuit1.yield_op.concat(circuit2.yield_op)

    body1 = rewriter.move_region_contents_to_new_regions(circuit1.body)
    body2 = rewriter.move_region_contents_to_new_regions(circuit2.body)

    # Construct the new body by removing the old yields, concatenating, and adding the new yield
    assert body1.block.last_op is not None
    assert body2.block.last_op is not None
    rewriter.erase_op(body1.block.last_op)
    rewriter.erase_op(body2.block.last_op)
    rewriter.inline_block(
        body1.block,
        InsertPoint.at_start(new_body),
        [remap[old_ssa] for old_ssa in body1.block.args],
    )
    rewriter.inline_block(
        body2.block,
        InsertPoint.at_end(new_body),
        [remap[old_ssa] for old_ssa in body2.block.args],
    )
    rewriter.insert_op(new_yield, InsertPoint.at_end(new_body))

    return new_body


def _combine_input_output_args(
    circuit1: stab.CircuitOp, circuit2: stab.CircuitOp, medial_ssas: set[SSAValue]
) -> tuple[tuple[SSAValue, ...], tuple[Attribute, ...]]:
    """Find the new input args and output arg types for the merged circuit, respecting the removal
    of block args done in _combine_circuit_bodies."""
    new_input_args = circuit1.input_args + tuple(
        arg for arg in circuit2.input_args if arg not in medial_ssas
    )
    new_output_args_types = circuit1.output_args.types + circuit2.output_args.types
    return new_input_args, new_output_args_types


def _make_detectors(
    circuit: stab.CircuitOp, detectors: list[tuple[int, ...]]
) -> list[qec.DetectorOp]:
    """Make detectors from a list of tuples of measurement indices in the circuit's yield."""
    detector_ops: list[qec.DetectorOp] = []
    for detector_meas_idxs in detectors:
        detector_measurements = [circuit.yield_op.measurements[idx] for idx in detector_meas_idxs]
        detector_ops.append(qec.DetectorOp(detector_measurements))
    return detector_ops


def _can_merge_circuits(circuit1: stab.CircuitOp, circuit2: stab.CircuitOp) -> bool:
    """Check whether circuit1 and circuit2 can be merged according to the conditions specified in
    MergeCircuits's docstring."""
    if circuit1.output != circuit2.input or circuit1.parent != circuit2.parent:
        return False

    if (circuit1.flows is None) != (circuit2.flows is None):
        return False

    # Check that we're guaranteed there are no quantum ops between circuit1 and circuit2
    op = circuit1.next_op
    while op is not None and op != circuit2:
        if not is_quantum_effect_free(op):
            return False
        op = op.next_op

    # Check no inputs from circuit2 are dominated by outputs from circuit1 unless they are equal
    circuit1_outputs = set[SSAValue](circuit1.output_args)
    circuit2_inputs = set[SSAValue](circuit2.input_args)

    use_def_viewer = UseDefViewer()

    for output in circuit1_outputs - circuit2_inputs:
        dominated_ssas = use_def_viewer.get_dominated_ssas(output)
        if dominated_ssas & circuit2_inputs:
            return False

    return True


def _merge_circuits(
    circuit1: stab.CircuitOp, circuit2: stab.CircuitOp, rewriter: PatternRewriter
) -> stab.CircuitOp:
    """Merge two stab.circuit ops into a new stab.circuit op, assuming they can be merged as defined
    by _can_merge_circuits.

    Destructive: empties circuit1 and circuit2 bodies.
    """
    verify_circuit_flows_present(circuit1)
    verify_circuit_flows_present(circuit2)
    if circuit1.flows is not None and circuit2.flows is not None:
        new_flows, new_detectors = _merge_flows(circuit1, circuit2)
    else:
        new_flows = None
        new_detectors = []

    block_args_to_yields, medial_ssas = _match_block_args_to_yields(circuit1, circuit2)
    new_body = _combine_circuit_bodies(circuit1, circuit2, block_args_to_yields, rewriter)
    new_input_args, new_output_args_types = _combine_input_output_args(
        circuit1, circuit2, medial_ssas
    )

    new_circuit = stab.CircuitOp(
        input_state=circuit1.input,
        output_state_type=circuit2.output.type,
        input_args=new_input_args,
        body=new_body,
        flows=new_flows,
        output_args_types=new_output_args_types,
    )

    detectors = _make_detectors(new_circuit, new_detectors)
    redundant_detectors = add_detectors_if_independent(new_circuit, detectors)

    # Clean up the detectors that didn't get added
    for detector in redundant_detectors:
        detector.erase()

    return new_circuit


def _merge_and_replace_circuits(
    circuit1: stab.CircuitOp, circuit2: stab.CircuitOp, rewriter: PatternRewriter
) -> None:
    """Merge two stab.circuit ops and replace them with the merged circuit in the IR.

    Assumes they can be merged as defined by _can_merge_circuits.
    """
    new_circuit = _merge_circuits(circuit1, circuit2, rewriter)

    rewriter.insert_op(new_circuit, InsertPoint.after(circuit2))

    # Replace uses of circuit2's output state with the new circuit's output state
    rewriter.replace_all_uses_with(circuit2.output, new_circuit.output)

    # Replace uses of both circuits' output args with the new circuit's output args
    # Note that if one of the output args of circuit1 is only used as an input arg to circuit2, then
    # it will be present but unused in the output IR.
    all_old_output_args = circuit1.output_args + circuit2.output_args
    for old_ssa, new_ssa in zip(all_old_output_args, new_circuit.output_args, strict=True):
        rewriter.replace_all_uses_with(old_ssa, new_ssa)

    # Erase circuit2 first since circuit1's output is used by circuit2
    rewriter.erase_op(circuit2)
    rewriter.erase_op(circuit1)


class _MergeCircuitsPattern(RewritePattern):
    """A pattern which merges a stab.circuit with the stab.circuit using its output if possible."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, circuit: stab.CircuitOp, rewriter: PatternRewriter) -> None:
        # Try to merge circuit with the use of its output
        if not circuit.output.has_one_use():
            # Note there really shouldn't be multiple uses due to no-cloning
            return

        assert circuit.output.first_use is not None
        user_op = circuit.output.first_use.operation

        if isinstance(user_op, stab.CircuitOp) and _can_merge_circuits(circuit, user_op):
            _merge_and_replace_circuits(circuit, user_op, rewriter)


@dataclass(frozen=True)
class MergeCircuits(ModulePass):
    """Pass to merge stab.circuit ops together when possible.

    This pass combines together pairs of stab.circuit ops obeying the following conditions:
    - the first circuit's output state must match the second circuit's input state.
    - The circuits must be in the same block (so there is no control flow between them).
    - There must be no other quantum ops between the circuits, so timing does not get changed.
    - Either both circuits have flows specified, or neither do.
    - The input args of the second circuit must not be downstream in the SSA use DAG from the
    outputs of the first circuit, unless they are directly connected (i.e. the output of the first
    circuit is passed to the input of the second circuit). This ensures there is no computation
    between the two circuits which would get elided in the merge.

    The circuits' bodies are combined together and the input and output args are merged. Note all
    output args from both circuits are preserved, which may result in unused output args if some
    outputs from the first circuit are only used as inputs to the second circuit. Any detectors
    formed by creation flows from the first circuit and destruction flows from the second circuit
    are added to the end of the merged circuit's body, unless they are in the span of the existing
    detectors. (These are the same rules applied to existing detectors in the find-detectors pass.)

    The pass is applied repeatedly until no more merges can be made.
    """

    name = "merge-circuits"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        PatternRewriteWalker(_MergeCircuitsPattern()).rewrite_module(op)
