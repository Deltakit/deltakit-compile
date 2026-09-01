# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Pass that automatically adds detectors from stabiliser flow annotations."""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import cast

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp, i1
from xdsl.ir import Attribute, Block, Operation, Region, SSAValue
from xdsl.passes import ModulePass
from xdsl.rewriter import InsertPoint, Rewriter

from deltakit_compile.dialects import arith, qcore, qec, qstruct, scf
from deltakit_compile.dialects import stabiliser as stab
from deltakit_compile.dialects.qcore import is_quantum_effect_free
from deltakit_compile.passes.stabiliser._common import verify_circuit_flows_present
from deltakit_compile.passes.stabiliser._existing_detectors import add_detectors_if_independent


@dataclass(frozen=True)
class _OperandsExpansion:
    """Data expressing a list of operands expanded with measurements for stabiliser states and
    its relation to the original operand list. Immutable.

    We require that the added measurements for each stabiliser state and flow state appear
    immediately after the stabiliser state, sorted by the standard flow state order. All other
    operands must be in the same positions as in the original list.
    """

    old_operands: tuple[SSAValue, ...] = field(default_factory=tuple)
    """The original list of operands."""

    new_operands: tuple[SSAValue, ...] = field(default_factory=tuple)
    """The new list of operands with measurements added."""

    old_to_new_indices: Mapping[int, int] = field(default_factory=dict)
    """Maps indices in the old operands to indices in the new operands which hold the same value."""

    state_to_meas_range: Mapping[tuple[int, qcore.PauliStringAttr], tuple[int, int]] = field(
        default_factory=dict
    )
    """Maps (new operand index of stab.state, flow state) to the [start, end) range of indices in
    the new operands list of the measurements for that flow state."""

    def __post_init__(self) -> None:
        # Enforce the constraints
        new_idx = 0
        for old_idx, old_operand in enumerate(self.old_operands):
            new_operand_idx = new_idx
            assert old_operand == self.new_operands[new_operand_idx]
            assert self.old_to_new_indices[old_idx] == new_operand_idx
            new_idx += 1

            if isinstance(old_operand.type, stab.StateType):
                for flow_state in old_operand.type.flow_states:  # in sorted order
                    start, end = self.state_to_meas_range[new_operand_idx, flow_state]
                    assert start == new_idx
                    new_idx = end

    @property
    def new_operand_types(self) -> list[Attribute]:
        """The types of the new operands."""
        return [val.type for val in self.new_operands]

    def get_meas_range_from_old_idx(
        self, old_idx: int, flow_state: qcore.PauliStringAttr
    ) -> tuple[int, int]:
        """Get a range of measurement indices from the index of a stab.state in old_operands."""
        new_idx = self.old_to_new_indices[old_idx]
        return self.state_to_meas_range[new_idx, flow_state]

    def concat(self, other: _OperandsExpansion) -> _OperandsExpansion:
        """Return another expansion concatenated onto this one, updating indices appropriately."""
        old_offset = len(self.old_operands)
        new_offset = len(self.new_operands)

        appended_old_operands = self.old_operands + other.old_operands
        appended_new_operands = self.new_operands + other.new_operands

        appended_old_to_new_indices = dict(self.old_to_new_indices)
        for old_idx, new_idx in other.old_to_new_indices.items():
            appended_old_to_new_indices[old_idx + old_offset] = new_idx + new_offset

        appended_state_to_meas_range = dict(self.state_to_meas_range)
        for (state_idx, flow_state), (start, end) in other.state_to_meas_range.items():
            new_range = (start + new_offset, end + new_offset)
            appended_state_to_meas_range[state_idx + new_offset, flow_state] = new_range

        return _OperandsExpansion(
            old_operands=appended_old_operands,
            new_operands=appended_new_operands,
            old_to_new_indices=appended_old_to_new_indices,
            state_to_meas_range=appended_state_to_meas_range,
        )

    def pad(
        self, old_idx: int, flow_state: qcore.PauliStringAttr, padding: list[SSAValue]
    ) -> _OperandsExpansion:
        """Return a new expansion with padding added to the measurements for the given flow state
        for the stab.state at old_idx in old_operands."""
        new_idx = self.old_to_new_indices[old_idx]
        assert (new_idx, flow_state) in self.state_to_meas_range
        _, insert_idx = self.state_to_meas_range[new_idx, flow_state]

        padded_new_operands = (
            self.new_operands[:insert_idx] + tuple(padding) + self.new_operands[insert_idx:]
        )

        offset = len(padding)

        def pad_new_index(new_idx: int) -> int:
            return new_idx if new_idx < insert_idx else new_idx + offset

        def pad_meas_range(
            idx: int, fs: qcore.PauliStringAttr, start: int, end: int
        ) -> tuple[int, int]:
            if idx < new_idx or (idx == new_idx and fs.sort_key() < flow_state.sort_key()):
                return (start, end)
            elif idx == new_idx and fs.sort_key() == flow_state.sort_key():  # noqa: RET505
                return (start, end + offset)
            else:
                return (start + offset, end + offset)

        padded_old_to_new_indices = {
            old: pad_new_index(new) for old, new in self.old_to_new_indices.items()
        }
        padded_state_to_meas_range = {
            (pad_new_index(idx), fs): pad_meas_range(idx, fs, start, end)
            for (idx, fs), (start, end) in self.state_to_meas_range.items()
        }

        return _OperandsExpansion(
            old_operands=self.old_operands,
            new_operands=padded_new_operands,
            old_to_new_indices=padded_old_to_new_indices,
            state_to_meas_range=padded_state_to_meas_range,
        )

    @staticmethod
    def harmonise(
        expansions: list[_OperandsExpansion],
        make_padding: Callable[[SSAValue], SSAValue],
    ) -> list[_OperandsExpansion]:
        """Given a list of expansions with the same number and types of old operands,
        pad each expansion so each (stab.state, flow state) has the same number of measurements.
        make_padding returns a padding SSAValue given the stab.state to pad.
        There must be at least one expansion in the list.
        """
        assert expansions, "There must be at least one expansion to harmonise."
        assert all(
            len(exp.old_operands) == len(expansions[0].old_operands) for exp in expansions
        ), "All expansions must have the same number of old operands."

        def range_size(start_end: tuple[int, int]) -> int:
            start, end = start_end
            return end - start

        # Map of (old stab.state index, flow state) to max number of measurements in any expansion
        max_num_measurements: dict[tuple[int, qcore.PauliStringAttr], int] = {}

        # Find the max number of measurements for each (stab.state, flow state)
        for old_idx, old_operand in enumerate(expansions[0].old_operands):
            assert all(exp.old_operands[old_idx].type == old_operand.type for exp in expansions), (
                "Each old operand list must have the same pattern of types."
            )

            if isinstance(state_type := old_operand.type, stab.StateType):
                for flow_state in state_type.flow_states:
                    # Find max number of measurements for this flow state
                    max_num_measurements[old_idx, flow_state] = max(
                        range_size(exp.get_meas_range_from_old_idx(old_idx, flow_state))
                        for exp in expansions
                    )

        # Pad each expansion to have the max number of measurements
        new_expansions: list[_OperandsExpansion] = []
        for expansion in expansions:
            new_exp = expansion
            for (old_idx, flow_state), max_num_meas in max_num_measurements.items():
                num_padding = max_num_meas - range_size(
                    new_exp.get_meas_range_from_old_idx(old_idx, flow_state)
                )
                if num_padding:
                    state_ssa = expansion.old_operands[old_idx]
                    padding = [make_padding(state_ssa) for _ in range(num_padding)]
                    new_exp = new_exp.pad(old_idx, flow_state, padding)
            new_expansions.append(new_exp)

        return new_expansions


class _FindDetectorsPattern:
    """Automatically add detectors using the stabiliser flow annotations.

    This pass modifies each CircuitOp to take in a list of measurements for each input flow state,
    output a list of measurements for each output flow state, and add detectors where appropriate.
    The measurements associated with each flow state are the measurements that will form part of a
    detector when the associated flow state terminates.

    In more detail, for each stabiliser flow state in a `stab.state`, we associate a list of
    measurements which form part of that stabiliser's current flow. When a flow terminates at a
    destruction flow, we add a detector from its measurements. In each CircuitOp, we add inputs for
    the measurements from each incoming flow and output the measurements for each outgoing flow.
    Detectors are not added if they are in the span of existing detectors, i.e., if there is a set
    of existing or previously added detectors whose sum (mod 2) gives the new detector.
    """

    def __init__(self) -> None:
        # The list of measurements associated with each stab.state and flow state
        self._state_and_flow_to_meas: dict[
            tuple[SSAValue, qcore.PauliStringAttr], list[SSAValue]
        ] = {}

    def _get_measurements_for_flow(
        self, state: SSAValue, flow_state: qcore.PauliStringAttr
    ) -> list[SSAValue]:
        if (state, flow_state) not in self._state_and_flow_to_meas:
            msg = f"Measurements for stabiliser state {state}, flow state {flow_state} not found!"
            raise KeyError(msg)
        return self._state_and_flow_to_meas[state, flow_state]

    def _expand_operand_list(self, operands: Iterable[SSAValue]) -> _OperandsExpansion:
        """For each stab.state operand in the list, add its measurements immediately after it
        in the standardised order. Error if any stab.state operand doesn't have measurements.
        Return a summary of the expansion (does not modify operands).
        """
        operands = tuple(operands)

        new_operands: list[SSAValue] = []
        old_to_new_indices: dict[int, int] = {}
        state_to_meas_range: dict[tuple[int, qcore.PauliStringAttr], tuple[int, int]] = {}

        for old_idx, operand in enumerate(operands):
            new_idx = len(new_operands)
            old_to_new_indices[old_idx] = new_idx
            new_operands.append(operand)

            if isinstance(operand.type, stab.StateType):
                for flow_state in operand.type.flow_states:
                    measurements = self._get_measurements_for_flow(operand, flow_state)
                    state_to_meas_range[new_idx, flow_state] = (
                        len(new_operands),
                        len(new_operands) + len(measurements),
                    )
                    new_operands.extend(measurements)

        return _OperandsExpansion(
            old_operands=operands,
            new_operands=tuple(new_operands),
            old_to_new_indices=old_to_new_indices,
            state_to_meas_range=state_to_meas_range,
        )

    def _replace_op_mapping_results(
        self,
        old_op: Operation,
        new_op: Operation,
        old_to_new_indices: Mapping[int, int],
    ) -> None:
        """Replace ops, replacing result SSA values according to old_to_new_indices."""
        Rewriter.insert_op(new_op, InsertPoint.after(old_op))
        for old_idx, new_idx in old_to_new_indices.items():
            old_op.results[old_idx].replace_all_uses_with(new_op.results[new_idx])
        Rewriter.erase_op(old_op)

    def _record_result_measurements(
        self,
        op: Operation,
        state_to_meas_range: Mapping[tuple[int, qcore.PauliStringAttr], tuple[int, int]],
    ) -> None:
        """Record the result measurements for each outgoing flow."""
        for (state_idx, flow_state), (start, end) in state_to_meas_range.items():
            state = op.results[state_idx]
            self._state_and_flow_to_meas[state, flow_state] = [
                op.results[idx] for idx in range(start, end)
            ]

    def _replace_and_record(
        self,
        old_op: Operation,
        new_op: Operation,
        expansion: _OperandsExpansion,
    ) -> None:
        """Replace ops, updating results and recording flows according to the expansion.
        Note the expansion operands themselves aren't used, only their metadata."""
        self._replace_op_mapping_results(old_op, new_op, expansion.old_to_new_indices)
        self._record_result_measurements(new_op, expansion.state_to_meas_range)

    def _handle_flow(
        self,
        flow: stab.FlowAttr,
        input_state: SSAValue,
        circuit_block: Block,
    ) -> tuple[list[SSAValue], list[SSAValue], qec.DetectorOp | None]:
        """Handle a single flow for a circuit.

        Returns a list of SSA values to be added to the circuit's inputs, a list of SSA values to be
        added to the circuit's yields, and an optional new detector to be added to the circuit.

        Warning:
            Mutates circuit_block.
        """

        new_input_measurements: list[SSAValue] = []
        new_yield_measurements: list[SSAValue] = []

        # The measurement SSA values within the circuit block associated with this flow
        circuit_measurements: list[SSAValue] = []

        if not flow.is_creation_flow:
            # Add the incoming measurements from this flow as inputs to the circuit
            input_flow_state = cast(stab.StateType, input_state.type).states[flow.input_state_index]
            new_input_measurements = self._get_measurements_for_flow(input_state, input_flow_state)

            # Take them as arguments to the block
            circuit_measurements.extend(
                circuit_block.insert_arg(i1, len(circuit_block.args))
                for _ in range(len(new_input_measurements))
            )

        yield_op = cast(stab.YieldOp, circuit_block.last_op)

        # Add the measurements associated with the flow from this circuit
        flow_measurements = [yield_op.measurements[idx] for idx in flow.measurement_indices]
        circuit_measurements.extend(flow_measurements)

        if flow.is_destruction_flow:
            # Destruction flow - add detector from measurements
            detector = qec.DetectorOp(circuit_measurements)
        else:
            # Passing through - yield measurements back out
            new_yield_measurements = circuit_measurements
            detector = None

        return new_input_measurements, new_yield_measurements, detector

    def _replace_circuit(
        self,
        old_op: stab.CircuitOp,
        new_body: Region,
        new_inputs: list[SSAValue],
        new_yields: list[SSAValue],
    ) -> stab.CircuitOp:
        """Replace the circuit op with a new one with the given body and added inputs and yields.
        Return the new circuit op.
        """

        # Add all new yields to the yield op
        # Put new yields on the left for consistency with the standard order from _OperandsExpansion
        # in which the measurements come immediately after the stab.state.
        if new_yields:
            yield_op = cast(stab.YieldOp, new_body.block.last_op)
            Rewriter.replace_op(
                yield_op,
                stab.YieldOp(
                    yield_op.measurements,
                    new_yields + list(yield_op.arguments),
                ),
            )

        # Add new inputs to the circuit op and add new yields to output
        new_op = stab.CircuitOp(
            input_state=old_op.input,
            output_state_type=old_op.output.type,
            input_args=list(old_op.input_args) + new_inputs,
            body=new_body,
            flows=old_op.flows,
            output_args_types=([i1] * len(new_yields)) + [arg.type for arg in old_op.output_args],
            attributes=old_op.attributes,
        )

        # Replace the op, mapping old results to new results
        old_to_new_indices = {
            idx: idx if idx == 0 else idx + len(new_yields) for idx in range(len(old_op.results))
        }
        self._replace_op_mapping_results(old_op, new_op, old_to_new_indices)

        return new_op

    def _handle_circuit(self, op: stab.CircuitOp) -> None:
        if not op.input_flows and not op.output_flows:
            # Allow use-case with no flows present at all: no-op.
            return
        verify_circuit_flows_present(op)

        # The ith element is the list of new input/output SSA values for the flow with the
        # ith input or output flow state index.
        # This scheme ensures the input and outputs are in the order of the stab.state flow states.
        num_input_flow_states = len(op.input_flows)
        num_output_flow_states = len(op.output_flows)
        new_input_measurements: list[list[SSAValue]] = [[] for _ in range(num_input_flow_states)]
        new_yield_measurements: list[list[SSAValue]] = [[] for _ in range(num_output_flow_states)]
        new_detectors: list[qec.DetectorOp] = []

        new_body = Rewriter.move_region_contents_to_new_regions(op.body)

        for flow in op.flows or []:  # in order of input index
            input_measurements, yield_measurements, detector = self._handle_flow(
                flow, op.input, new_body.block
            )
            if input_measurements:
                new_input_measurements[flow.input_state_index] = input_measurements
            if yield_measurements:
                new_yield_measurements[flow.output_state_index] = yield_measurements
            if detector is not None:
                new_detectors.append(detector)

        new_op = self._replace_circuit(
            op,
            new_body,
            list(itertools.chain.from_iterable(new_input_measurements)),
            list(itertools.chain.from_iterable(new_yield_measurements)),
        )
        redundant_detectors = add_detectors_if_independent(new_op, new_detectors)

        # Clean up the detectors that didn't get added
        for detector in redundant_detectors:
            detector.erase()

        # Record the measurements for each output flow state
        idx = 0
        for output_flow, yields in zip(new_op.output_flows, new_yield_measurements, strict=True):
            self._state_and_flow_to_meas[new_op.output, output_flow] = list(
                new_op.output_args[idx : idx + len(yields)]
            )
            idx += len(yields)

    def _handle_parallel(self, op: qstruct.ParallelOp) -> None:
        new_result_types: list[Attribute] = []
        full_expansion = _OperandsExpansion()

        # Expand each region's yield
        for region in op.par_regions:
            yield_op = cast(qstruct.YieldOp, region.block.last_op)
            expansion = self._expand_operand_list(yield_op.operands)
            Rewriter.replace_op(yield_op, qstruct.YieldOp(*expansion.new_operands))

            new_result_types.extend(expansion.new_operand_types)
            full_expansion = full_expansion.concat(expansion)

        # Replace the parallel op
        new_op = qstruct.ParallelOp(
            result_types=new_result_types,
            par_regions=[
                Rewriter.move_region_contents_to_new_regions(region) for region in op.par_regions
            ],
            alignment=op.alignment,
        )
        self._replace_and_record(op, new_op, full_expansion)

    def _insert_padding_zero(self, insert_point: InsertPoint) -> SSAValue:
        """Insert a constant zero for padding and return its SSA value."""
        constant = arith.ConstantOp.from_int_and_width(0, i1)
        Rewriter.insert_op(constant, insert_point)
        return constant.result

    def _handle_branching(self, op: scf.IfOp | scf.IndexSwitchOp) -> _OperandsExpansion:
        """Given an scf.if or scf.index_switch, harmonise the yield operands across all branches
        and return a representative operands expansion."""
        expansions: list[_OperandsExpansion] = []

        # Generate the desired expansions for each yield but don't modify yet
        for region in op.regions:
            yield_op = cast(scf.YieldOp, region.block.last_op)
            expansions.append(self._expand_operand_list(yield_op.operands))

        padding_zeros: dict[SSAValue, SSAValue] = {}

        # Lazily generate a single constant zero after the given stab.state for padding
        def make_padding(state_ssa: SSAValue) -> SSAValue:
            if state_ssa not in padding_zeros:
                # Trace where the stab.state came from and insert there
                if isinstance(state_ssa.owner, Operation):
                    insert_point = InsertPoint.after(state_ssa.owner)
                else:
                    # Block argument - insert at start of block
                    insert_point = InsertPoint.at_start(state_ssa.owner)
                padding_zeros[state_ssa] = self._insert_padding_zero(insert_point)
            return padding_zeros[state_ssa]

        # Pad each expansion so they all match
        harmonised_expansions = _OperandsExpansion.harmonise(expansions, make_padding=make_padding)

        # Now replace each yield operand list with the padded expansions
        for region, expansion in zip(op.regions, harmonised_expansions, strict=True):
            yield_op = cast(scf.YieldOp, region.block.last_op)
            Rewriter.replace_op(yield_op, scf.YieldOp(*expansion.new_operands))

        representative_exp = harmonised_expansions[0]
        assert all(
            exp.new_operand_types == representative_exp.new_operand_types
            and exp.old_to_new_indices == representative_exp.old_to_new_indices
            and exp.state_to_meas_range == representative_exp.state_to_meas_range
            for exp in harmonised_expansions
        )
        return representative_exp

    def _handle_if(self, op: scf.IfOp) -> None:
        yield_expansion = self._handle_branching(op)

        new_op = scf.IfOp(
            cond=op.cond,
            return_types=yield_expansion.new_operand_types,
            true_region=Rewriter.move_region_contents_to_new_regions(op.true_region),
            false_region=Rewriter.move_region_contents_to_new_regions(op.false_region),
        )
        self._replace_and_record(op, new_op, yield_expansion)

    def _handle_index_switch(self, op: scf.IndexSwitchOp) -> None:
        yield_expansion = self._handle_branching(op)

        new_op = scf.IndexSwitchOp(
            arg=op.arg,
            result_types=yield_expansion.new_operand_types,
            cases=op.cases,
            case_regions=[
                Rewriter.move_region_contents_to_new_regions(region) for region in op.case_regions
            ],
            default_region=Rewriter.move_region_contents_to_new_regions(op.default_region),
        )
        self._replace_and_record(op, new_op, yield_expansion)

    def _handle_cast(self, op: stab.StateCastOp) -> None:
        # Record the measurements just for flows that pass through the cast
        for preserved_flow in op.output_flow_states:
            self._state_and_flow_to_meas[op.output, preserved_flow] = (
                self._get_measurements_for_flow(op.input, preserved_flow)
            )

    def _handle_permute(self, op: stab.StatePermuteOp) -> None:
        for flow in cast(stab.StateType, op.input.type).flow_states:
            output_flow = op.permute_flow(flow)
            self._state_and_flow_to_meas[op.output, output_flow] = self._get_measurements_for_flow(
                op.input, flow
            )

    def _handle_concatenate(self, op: stab.StateConcatenateOp) -> None:
        for input_state in op.inputs:
            for flow in cast(stab.StateType, input_state.type).flow_states:
                output_flow = op.input_to_output_flow(input_state, flow)
                self._state_and_flow_to_meas[op.output, output_flow] = (
                    self._get_measurements_for_flow(input_state, flow)
                )

    def _handle_split(self, op: stab.StateSplitOp) -> None:
        for output_state in op.outputs:
            for flow in cast(stab.StateType, output_state.type).flow_states:
                input_flow = op.output_to_input_flow(output_state, flow)
                self._state_and_flow_to_meas[output_state, flow] = self._get_measurements_for_flow(
                    op.input, input_flow
                )

    def apply(self, op: ModuleOp) -> None:
        """Apply the pass throughout the given module."""
        for child_op in op.walk(region_first=True):
            if isinstance(child_op, stab.CircuitOp):
                self._handle_circuit(child_op)
            elif isinstance(child_op, qstruct.ParallelOp):
                self._handle_parallel(child_op)
            elif isinstance(child_op, scf.IfOp):
                self._handle_if(child_op)
            elif isinstance(child_op, scf.IndexSwitchOp):
                self._handle_index_switch(child_op)
            elif isinstance(child_op, (qstruct.RepeatOp, scf.ForOp, scf.WhileOp)):
                # Ignore purely classical loops
                if not is_quantum_effect_free(child_op):
                    # TODO: Support loops
                    msg = "Loops are not yet supported in find-detectors."  # pragma: no cover
                    raise NotImplementedError(msg)
            elif isinstance(child_op, stab.StateCastOp):
                self._handle_cast(child_op)
            elif isinstance(child_op, stab.StatePermuteOp):
                self._handle_permute(child_op)
            elif isinstance(child_op, stab.StateConcatenateOp):
                self._handle_concatenate(child_op)
            elif isinstance(child_op, stab.StateSplitOp):
                self._handle_split(child_op)


@dataclass(frozen=True)
class FindDetectors(ModulePass):
    """Pass that automatically adds detectors from stabiliser flows annotations.

    This pass uses a local modification of each CircuitOp to keep track of the measurements
    associated with each stabiliser flow state and add detectors when a flow terminates.
    Detectors are not added if they are redundant, i.e., if there is a set of existing or previously
    added detectors whose sum (mod 2) gives the new detector.

    This pass requires that all circuits already have flow annotations.
    """

    name = "find-detectors"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        _FindDetectorsPattern().apply(op)
