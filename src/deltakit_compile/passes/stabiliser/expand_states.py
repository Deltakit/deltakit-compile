# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Pass to expand the qubits used by stab.states so that idle qubits can maintain flows."""

import itertools
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Block, Operation, SSAValue
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    GreedyRewritePatternApplier,
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.rewriter import InsertPoint
from xdsl.utils.hints import isa

from deltakit_compile.dialects import qcore
from deltakit_compile.dialects import stabiliser as stab
from deltakit_compile.passes.canonicalisation.stabiliser import (
    CombineChainedConcatenates,
    CombineChainedPermutes,
    CombineChainedSplits,
    CombineConcatenatedStateMake,
    RemoveRedundantConcatenate,
    RemoveRedundantPermute,
    RemoveRedundantSplit,
    RemoveRedundantSplitAfterConcatenate,
    ReplaceConcatenateAfterSplitWithPermute,
)


class _RemoveConcatSubsetOfSplitPattern(RewritePattern):
    """A pattern to remove concatenations that are of a subset of a split op - where a permutation
    before splitting lets us remove the concatenation."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stab.StateConcatenateOp, rewriter: PatternRewriter) -> None:
        operands = op.inputs
        source = operands[0].owner
        if not isinstance(source, stab.StateSplitOp):
            return
        if not set(source.outputs).issuperset(operands):
            return
        if any(part.uses.get_length() > 1 for part in source.outputs):
            return
        assert isa(source.input, SSAValue[stab.StateType])
        # Now we have a StateSplitOp that returns some states, a subset of which are used in
        # op - this then could have been written as a permute and a split instead.
        parts = []
        leftovers = []
        leftover_indices = []
        concatenated = [range(0) for _ in op.inputs]
        qubit_count = 0
        for i, split_part in enumerate(source.outputs):
            next_size = split_part.type.total_qubits
            part_range = range(qubit_count, qubit_count + next_size)
            qubit_count += next_size
            parts.append(part_range)

            if split_part in op.inputs:
                index = op.inputs.index(split_part)
                concatenated[index] = part_range
            else:
                leftovers.append(part_range)
                leftover_indices.append(i)

        permutation = stab.StatePermuteOp.invert_permutation(
            list(itertools.chain(*concatenated, *leftovers))
        )

        permuted_input: SSAValue[stab.StateType]
        if not stab.StatePermuteOp.is_identity_permutation(permutation):
            permutation_op = stab.StatePermuteOp(source.input, permutation)
            permuted_input = permutation_op.output
            rewriter.insert_op(permutation_op, InsertPoint.before(source))
        else:
            permuted_input = source.input

        new_split = stab.StateSplitOp(
            permuted_input, [sum(map(len, concatenated)), *map(len, leftovers)]
        )
        rewriter.insert_op(new_split, InsertPoint.before(source))
        # The result of the new split start with the concatenated result, and are followed by
        # each leftover part.
        for i, leftover_index in enumerate(leftover_indices):
            rewriter.replace_all_uses_with(source.outputs[leftover_index], new_split.outputs[i + 1])
        rewriter.replace_op(op, (), (new_split.outputs[0],))
        rewriter.erase_op(source)


class _RemoveSplitSubsetOfConcatPattern(RewritePattern):
    """A pattern to remove splits that form a subset of a concatenation op - where a permutation
    after the concat lets us remove the split op instead."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stab.StateSplitOp, rewriter: PatternRewriter) -> None:
        uses = [result.get_unique_use() for result in op.outputs]
        destination = uses[0] and uses[0].operation
        if not isinstance(destination, stab.StateConcatenateOp) or any(
            (use and use.operation) != destination for use in uses
        ):
            return  # Don't touch splits whose results don't all go to the same concat op
        if len(destination.inputs) <= len(uses):
            return  # Don't handle the direct permute case since that does not need a new concat op.

        # Now we have a StateSplitOp that returns some states, all of which are used in a
        # concatenation op - this then could have been written as single concatenation op followed
        # by a permute instead.
        other_concat_inputs = [val for val in destination.inputs if val not in op.outputs]
        permute_output = list(destination.inputs)
        permute_input = list(op.outputs) + other_concat_inputs
        assert isa(permute_output, list[SSAValue[stab.StateType]])
        assert isa(permute_input, list[SSAValue[stab.StateType]])
        permutation = stab.StatePermuteOp.calculate_permutation_from_states(
            permute_input, permute_output
        )
        new_concat_inputs = [op.input, *other_concat_inputs]
        assert isa(new_concat_inputs, list[SSAValue[stab.StateType]])

        new_ops: list[Operation] = [new_concat_op := stab.StateConcatenateOp(new_concat_inputs)]
        new_result = new_concat_op.output

        if not stab.StatePermuteOp.is_identity_permutation(permutation):
            new_ops.append(permute_op := stab.StatePermuteOp(new_concat_op.output, permutation))
            new_result = permute_op.output

        rewriter.replace_op(destination, new_ops, (new_result,))
        rewriter.erase_op(op)


def _map_flows(
    *,
    original_flows: Iterable[stab.FlowAttr],
    flow_state_transformer: Callable[[qcore.PauliStringAttr], qcore.PauliStringAttr],
    old_in_flows: Sequence[qcore.PauliStringAttr],
    old_out_flows: Sequence[qcore.PauliStringAttr],
    new_in_flows: Sequence[qcore.PauliStringAttr],
    new_out_flows: Sequence[qcore.PauliStringAttr],
) -> list[stab.FlowAttr]:
    """Update each FlowAttr to index a new set of input and output flow states accounting for a
    transformation of the input and output states of each existing flow."""
    new_flows = []
    for original_flow in original_flows:
        input_idx = original_flow.input_state.data
        if input_idx != stab.I_STATE_INDEX:
            input_flow_state = old_in_flows[input_idx]
            input_idx = new_in_flows.index(flow_state_transformer(input_flow_state))
        output_idx = original_flow.output_state.data
        if output_idx != stab.I_STATE_INDEX:
            output_flow_state = old_out_flows[output_idx]
            output_idx = new_out_flows.index(flow_state_transformer(output_flow_state))
        new_flows.append(
            stab.FlowAttr(original_flow.sign, original_flow.measurements, input_idx, output_idx)
        )
    return new_flows


class _ExpandCircuitStatesPattern(RewritePattern):
    """A pattern to add new qubits into circuits that are otherwise idle, so that they can retain
    their flows.
    Rewrites:
        %a, %b, %c = stab.state.split(%s)
        %b1 = stab.circuit(%b) with (%bq1, %bq2, ...) ...
        %s1 = stab.state.concatenate(%c, %b1, %a)
    into:
        %t = stab.circuit(%s) with (%aq1, ..., %bq1, %bq2, ..., %cq1, ...) ...
        %s1 = stab.state.permute(%t)
    """

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stab.CircuitOp, rewriter: PatternRewriter) -> None:
        assert isa(op.input, SSAValue[stab.StateType])
        state_source = op.input.owner
        if not isinstance(state_source, stab.StateSplitOp):
            return
        assert isa(state_source.input, SSAValue[stab.StateType])

        idle_states = [val for val in state_source.outputs if val != op.input]
        if not idle_states:
            return

        state_destination = op.output.get_user_of_unique_use()
        if (
            not isinstance(state_destination, stab.StateConcatenateOp)
            or set(state_destination.inputs) - {op.output} != set(idle_states)
            or any(
                idle_state.get_user_of_unique_use() != state_destination
                for idle_state in idle_states
            )
        ):
            return

        new_state_order: list[SSAValue[stab.StateType]] = [*state_source.outputs]
        original_state_idx = new_state_order.index(op.input)
        state_offsets = [
            0,
            *itertools.accumulate(state.type.total_qubits for state in new_state_order),
        ]

        # Build a new circuit op with more qubits - always at the end so that existing flows are not
        # disrupted.
        original_qubits = op.output.type.total_qubits
        total_qubits = state_source.input.type.total_qubits
        new_circuit_block = Block(
            arg_types=([state_source.input.type.qubit_type] * total_qubits)
            + list(op.body.block.arg_types[original_qubits:])
        )
        rewriter.inline_block(
            op.body.block,
            InsertPoint(new_circuit_block),
            new_circuit_block.args[
                state_offsets[original_state_idx] : state_offsets[original_state_idx + 1]
            ]
            + new_circuit_block.args[total_qubits:],
        )

        output_state_types = [state.type for state in new_state_order]
        output_state_types[original_state_idx] = op.output.type
        output_flow_states = stab.StateType.merge_and_relabel_flow_states(output_state_types)
        output_state_type = stab.StateType(
            total_qubits, op.output.type.qubit_type, output_flow_states
        )

        # re-map flows from the original circuit to the new input type
        # new_input_flow_states = pre_permute_op.output.type.flow_states.data
        new_input_flow_states = state_source.input.type.flow_states.data
        new_output_flow_states = output_state_type.flow_states.data

        new_flows = _map_flows(
            original_flows=op.flows or [],
            flow_state_transformer=(
                lambda p: p.shift_qubit_indices(
                    state_offsets[original_state_idx], new_length=total_qubits
                )
            ),
            old_in_flows=op.input_flows,
            old_out_flows=op.output_flows,
            new_in_flows=new_input_flow_states,
            new_out_flows=new_output_flow_states,
        )
        # Always add idle state flows for the newly added idle qubits
        for state, offset in zip(new_state_order, state_offsets, strict=False):
            if state != op.input:
                for flow_state in state.type.flow_states.data:
                    new_flow_state = flow_state.shift_qubit_indices(offset, new_length=total_qubits)
                    input_idx = new_input_flow_states.index(new_flow_state)
                    output_idx = new_output_flow_states.index(new_flow_state)
                    new_flows.append(stab.FlowAttr("+", [], input_idx, output_idx))

        # Build the new circuit and replace the existing split, circuit, and concatenation
        new_circuit = stab.CircuitOp(
            state_source.input,
            output_state_type,
            input_args=op.input_args,
            body=new_circuit_block,
            flows=new_flows,
        )

        permuted_states = list(state_destination.inputs)
        permuted_states[original_state_idx] = op.input
        assert isa(permuted_states, list[SSAValue[stab.StateType]])
        post_permutation = stab.StatePermuteOp.calculate_permutation_from_states(
            state_source.outputs, permuted_states
        )
        post_permute_op = stab.StatePermuteOp(new_circuit.output, post_permutation)

        rewriter.replace_op(state_destination, post_permute_op)
        rewriter.replace_op(op, new_circuit, [None, *new_circuit.output_args])
        rewriter.erase_op(state_source)


class _PushPermutesAfterCircuitPattern(RewritePattern):
    """A pattern to take permute ops on the input of circuits and move it below the circuit."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stab.CircuitOp, rewriter: PatternRewriter) -> None:
        state_source = op.input.owner
        if not isinstance(state_source, stab.StatePermuteOp):
            return
        if state_source.output.get_user_of_unique_use() != op:
            return
        assert isa(state_source.input, SSAValue[stab.StateType])

        permutation = state_source.permutation_list
        total_qubits = len(permutation)
        new_circuit_block = Block(arg_types=op.body.block.arg_types)
        new_qubits = new_circuit_block.args[:total_qubits]
        permuted_qubits = state_source.permute_list(new_qubits)
        rewriter.inline_block(
            op.body.block,
            InsertPoint(new_circuit_block),
            permuted_qubits + list(new_circuit_block.args[total_qubits:]),
        )

        inverse_permutation = stab.StatePermuteOp.invert_permutation(permutation)
        # Generate the circuits new output state by applying the inverse permutation, such that
        # after we add the new permutation op we will get the same type back.
        output_state_type = stab.StateType(
            op.output.type.total_qubits,
            op.output.type.qubit_type,
            [flow.permute_indices(inverse_permutation) for flow in op.output.type.flow_states],
        )

        # re-map flows from the original circuit to the new input type
        new_input_flow_states = state_source.input.type.flow_states.data
        new_output_flow_states = output_state_type.flow_states.data

        if op.flows is None:
            new_flows = None
        else:
            new_flows = _map_flows(
                original_flows=op.flows or [],
                flow_state_transformer=(lambda p: p.permute_indices(inverse_permutation)),
                old_in_flows=op.input_flows,
                old_out_flows=op.output_flows,
                new_in_flows=new_input_flow_states,
                new_out_flows=new_output_flow_states,
            )

        # Build the new circuit and replace the existing split, circuit, and concatenation
        new_circuit = stab.CircuitOp(
            state_source.input,
            output_state_type,
            input_args=op.input_args,
            body=new_circuit_block,
            flows=new_flows,
        )

        post_permute_op = stab.StatePermuteOp(new_circuit.output, permutation)
        rewriter.replace_op(
            op, (new_circuit, post_permute_op), (post_permute_op.output, *new_circuit.output_args)
        )
        rewriter.erase_op(state_source)


class _PushPermutesAfterConcatenatePattern(RewritePattern):
    """A pattern to take permute ops before a concatenate and move it to apply to the result of the
    concatenate."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stab.StatePermuteOp, rewriter: PatternRewriter) -> None:
        concat_op = op.output.get_user_of_unique_use()
        if not isinstance(concat_op, stab.StateConcatenateOp):
            return
        assert isa(concat_op.inputs, Sequence[SSAValue[stab.StateType]])
        assert isa(op.input, SSAValue[stab.StateType])
        permutation = op.permutation_list
        preceding_operands = list(
            itertools.takewhile(lambda operand: operand != op.output, concat_op.inputs)
        )
        offset = sum(operand.type.total_qubits for operand in preceding_operands)

        new_permutation = [
            *range(offset),
            *(p + offset for p in permutation),
            *range(offset + len(permutation), concat_op.output.type.total_qubits),
        ]

        new_concat_op = stab.StateConcatenateOp(
            (*preceding_operands, op.input, *concat_op.inputs[len(preceding_operands) + 1 :])
        )
        new_permute_op = stab.StatePermuteOp(new_concat_op.output, new_permutation)
        rewriter.replace_op(concat_op, (new_concat_op, new_permute_op), (new_permute_op.output,))
        rewriter.erase_op(op)


@dataclass(frozen=True)
class ExpandStates(ModulePass):
    """Pass to try to add qubits to stabiliser states that are used in circuits so that those qubits
    can take part in stabiliser flows while being idle.
    """

    name = "expand-states"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        stab_canonicalisation_passes = [
            RemoveRedundantPermute(),
            RemoveRedundantConcatenate(),
            RemoveRedundantSplit(),
            RemoveRedundantSplitAfterConcatenate(),
            ReplaceConcatenateAfterSplitWithPermute(),
            CombineChainedPermutes(),
            CombineChainedConcatenates(),
            CombineChainedSplits(),
            CombineConcatenatedStateMake(),
        ]
        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [
                    *stab_canonicalisation_passes,
                    _RemoveConcatSubsetOfSplitPattern(),
                    _RemoveSplitSubsetOfConcatPattern(),
                    _ExpandCircuitStatesPattern(),
                    _PushPermutesAfterCircuitPattern(),
                    _PushPermutesAfterConcatenatePattern(),
                ]
            )
        ).rewrite_module(op)
