# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Combines detector rounds whose measurements are in parallel."""

from collections.abc import Generator, Sequence

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Attribute, Operation, Region, SSAValue, cast
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import PatternRewriter
from xdsl.utils.hints import isa

from deltakit_compile.dialects import qec, qstruct, scf
from deltakit_compile.dialects.qref import MeasureOp
from deltakit_compile.passes.stim._common import copy_stim_tag_from_ops
from deltakit_compile.utilities.ordered_set import OrderedSet
from deltakit_compile.utilities.traverse_from_ssa import find_backward_ssas

LoopOps = scf.ForOp | scf.WhileOp | qstruct.RepeatOp
ConditionalOps = scf.IfOp | scf.IndexSwitchOp


def _lowest_common_region_or_op_ancestor(
    *ops: Operation,
) -> Region | Operation:
    """Finds the lowest common ancestor region or op among the given operations,
    by iteratively folding: lca(lca(op0, op1), op2), ..."""

    def ancestors_from(node: Region | Operation) -> list[Region | Operation]:
        """Returns [node, parent, grandparent, ...] including node itself, innermost-first."""
        result: list[Region | Operation] = [node]
        if isinstance(node, Operation):
            current: Region | None = node.parent_region()
        else:
            parent_op = node.parent_op()
            if parent_op is None:
                return result
            result.append(parent_op)
            current = parent_op.parent_region()
        while current:
            result.append(current)
            parent_op = current.parent_op()
            if parent_op:
                result.append(parent_op)
                current = parent_op.parent_region()
            else:
                break
        return result

    def lca_two(a: Region | Operation, b: Operation) -> Region | Operation:
        """LCA between 2 operands."""
        b_ancestor_set = set(ancestors_from(b))
        for ancestor in ancestors_from(a):
            if ancestor in b_ancestor_set:
                return ancestor
        msg = (
            ""
            "Expected to find a common ancestor region or op between the operations, but "
            "no common ancestor was found. This means that the operations are not part of the "
            "same top level module op."
        )

        b.emit_error(msg, ValueError(msg))
        return None

    result: Region | Operation = ops[0]
    for op in ops[1:]:
        result = lca_two(result, op)
    return result


def _get_operation_before_region(start_op: Operation, target_region: Region) -> Operation | None:
    """Traverses from start_op up the ancestor chain to target_region, and returns the operation
    just before target_region in the ancestor chain. If no such operation is found, returns None."""
    current_op: Operation | None = start_op
    while current_op:
        parent_region = current_op.parent_region()
        if parent_region == target_region:
            return current_op
        if parent_region is None:
            break
        current_op = parent_region.parent_op()
    return None


def _yield_ssavalues_out_of_parallel_op(
    ssas: list[SSAValue],
    current_region: Region,
    rewriter: PatternRewriter,
) -> qstruct.ParallelOp:
    """Yield `ssas` out of the current region's parallel op. All ssas must be defined in the current
    region.

    Mutates `ssas` to update the SSAValues to the new propagated SSAValues after the
    parallel op."""
    parent_op = current_region.parent_op()
    assert isinstance(parent_op, qstruct.ParallelOp)

    result_offset = 0

    ssas_not_yielded_out = OrderedSet(ssas)

    current_yield_op = current_region.block.last_op
    assert isinstance(current_yield_op, qstruct.YieldOp), (
        "Expected last op of region to be a YieldOp, but found "
        f"{type(current_region.block.last_op)}."
    )

    ssa_to_yield_index: dict[SSAValue, int] = {}

    for i, operand in enumerate(current_yield_op.operands):
        if operand in ssas_not_yielded_out:
            ssas_not_yielded_out.discard(operand)
            ssa_to_yield_index[operand] = i

    if not ssas_not_yielded_out:
        # All SSA values are already being yielded by the existing yield op,
        # so no need to modify the parallel op.
        # However, still need to update `ssas`` to reference
        # the results of the parallel op.

        # get result offset for this region's yield operands in the parent
        # parallel op's results
        result_offset = 0
        for par_region in parent_op.regions:
            if par_region == current_region:
                break
            assert isinstance(par_region.block.last_op, qstruct.YieldOp), (
                "Expected last op of region to be a YieldOp, but found "
                f"{type(par_region.block.last_op)}."
            )
            result_offset += len(par_region.block.last_op.operands)

        # update the ssa values to propagate
        for i in range(len(ssas)):
            parallel_result = parent_op.results[ssa_to_yield_index[ssas[i]] + result_offset]
            assert isinstance(parallel_result, SSAValue), (
                f"Expected SSAValue type, but found {parallel_result.type}."
            )
            ssas[i] = parallel_result

        return parent_op

    # Need to modify parallel op to yield out extra detector SSAs
    new_result_types: list[Attribute] = []
    new_regions: list[Region] = []

    offset = 0
    result_offset = 0
    original_results_end = 0
    modified_results_end = 0

    for par_region in parent_op.regions:
        region_yield_op = par_region.block.last_op
        assert isinstance(region_yield_op, qstruct.YieldOp), (
            "Expected last op of region to be a YieldOp, but found "
            f"{type(par_region.block.last_op)}."
        )

        if par_region == current_region:
            # Add extra detector SSAs to this region's yield
            updated_yield_operands = list(current_yield_op.operands)
            result_offset = offset
            original_results_end = result_offset + len(updated_yield_operands)

            for detector_ssa in ssas_not_yielded_out:
                updated_yield_operands.append(detector_ssa)
                ssa_to_yield_index[detector_ssa] = len(current_yield_op.operands)

            rewriter.replace_op(
                current_yield_op, region_yield_op := qstruct.YieldOp(*updated_yield_operands)
            )
            modified_results_end = result_offset + len(updated_yield_operands)
            assert isinstance(region_yield_op, qstruct.YieldOp), (
                "Expected last op of region to be a YieldOp, but found "
                f"{type(par_region.block.last_op)}."
            )

        new_result_types.extend(region_yield_op.operand_types)
        offset += len(region_yield_op.operands)
        new_regions.append(rewriter.move_region_contents_to_new_regions(par_region))

    new_par_op = qstruct.ParallelOp(
        result_types=new_result_types,
        par_regions=new_regions,
        alignment=parent_op.alignment,
    )

    # Map old results to new results, preserving order but accounting for inserted values
    rewriter.replace_op(
        parent_op,
        new_par_op,
        new_results=new_par_op.results[:original_results_end]
        + new_par_op.results[modified_results_end:],
    )
    # Update `ssas` to reference the new parallel op's results
    for i in range(len(ssas)):
        yield_index = ssa_to_yield_index[ssas[i]]
        parallel_result = new_par_op.results[result_offset + yield_index]
        ssas[i] = parallel_result

    return new_par_op


def _propagate_ssa_values_to_region(
    ssa_values: Sequence[SSAValue],
    start_region: Region,
    end_region: Region,
    rewriter: PatternRewriter,
) -> tuple[list[SSAValue], qstruct.ParallelOp | None]:
    """Propagates the given SSAValues from the start region to the end region by adding them as
    operands to yield ops and results of parallel ops as necessary.

    The functions relies on 2 assumption:
    - The `ssa_values` passed in are in scope at the `start_region`, meaning they are either
    defined in the start_region or an ancestor region.
    - The `end_region` must be an ancestor of the `start_region`.
    """

    # given a region, find which detectors are defined in that region
    region_to_value: dict[Region, list[SSAValue]] = {}
    for value in ssa_values:
        parent_region = value.owner.parent_region()
        assert parent_region is not None, "Detector SSAValue should have a parent region"
        region_to_value.setdefault(parent_region, []).append(value)

    ssas_seen: list[SSAValue] = []

    current_region: Region | None = start_region

    last_par_op: qstruct.ParallelOp | None = None

    while current_region != end_region:
        if not current_region:
            msg = (
                ""
                "The end_region must be an ancestor of the start_region, but no ancestor"
                f" relationship was found between {start_region} and {end_region}."
            )
            raise ValueError(msg)

        ssas_seen.extend(region_to_value.get(current_region, []))
        region_to_value.pop(current_region, None)  # Safe delete even if not present

        parent_op = current_region.parent_op()
        assert isinstance(parent_op, qstruct.ParallelOp), (
            ""
            "Expected parent op of region to be a ParallelOp but found "
            f"{type(parent_op)}. This should not be possible as the two detector rounds "
            "are guaranteed to be part of the same circuit, loop or conditional body."
        )

        parent_region = parent_op.parent_region()

        last_par_op = _yield_ssavalues_out_of_parallel_op(ssas_seen, current_region, rewriter)

        current_region = parent_region

    for unseen_ssas in region_to_value.values():
        ssas_seen.extend(unseen_ssas)
    return ssas_seen, last_par_op


def _process_combined_rounds(
    detector_round_groups: Sequence[tuple[qec.DetectorRoundOp, ...]],
) -> None:
    """Given a tuple of rounds to combine, modifies the IR to combine them into a single round.

    It finds the LCA region or op ancestor of all rounds in the group, and propagates the SSA
    values of all rounds up to the LCA *region*. Temporary DetectorRoundOps are inserted to
    hold the propagated SSA values as they are propagated up, and are erased after all propagations
    are done and the SSA values have stabilised. Finally, a new combined DetectorRoundOp is inserted
    at the LCA region or op ancestor, and the original rounds are erased.

    Depending on whether the LCA is a region or an op, the insertion point of the new combined
    round is different:
    - If the LCA is a region, the last round in the group is propagated up to the LCA region,
    and the new round is inserted after the operation just before the LCA region.
      - If the LCA is an op, then the new round is inserted after the LCA op."""
    for group in detector_round_groups:
        if len(group) <= 1:
            continue
        lca_region: Region | Operation | None = _lowest_common_region_or_op_ancestor(*group)
        # lca can be operation or region
        if isinstance(lca_region, Region):
            # if region then want to insert combined round after the last detector round
            insertion_point = _get_operation_before_region(group[-1], lca_region)
            assert insertion_point is not None, (
                ""
                "Expected to find an operation before the common ancestor region to insert the"
                " combined round after"
            )
        else:
            assert isinstance(lca_region, Operation), (
                "Expected LCA to be either an Operation or Region"
            )
            insertion_point = lca_region
            lca_region = lca_region.parent_region()
        assert isinstance(lca_region, Region)
        # Insert a temp DetectorRoundOp after the insertion point to hold each
        # round's propagated SSA values. When a later round's propagation replaces
        # a parallel op, xDSL automatically updates the temp op's operands in the
        # IR, so the collected SSA values stay valid across all propagations.
        temp_ops: list[qec.DetectorRoundOp] = []
        for det_round in group:
            start_region = det_round.parent_region()
            assert start_region is not None, "Expected round to have a parent region"
            propagated, new_par_op = _propagate_ssa_values_to_region(
                det_round.detectors,
                start_region,
                lca_region,
                PatternRewriter(det_round),
            )
            if new_par_op is not None:
                insertion_point = new_par_op
            temp_op = qec.DetectorRoundOp(detectors=propagated)
            parent_block = insertion_point.parent_block()
            assert parent_block is not None, "Expected insertion point to have a parent block"
            parent_block.insert_op_after(temp_op, insertion_point)
            temp_ops.append(temp_op)

        # Now all propagations are done; collect the (now stable) SSA values
        # from the temp ops and erase everything that's been superseded.
        propagated_measurement_ssas: list[SSAValue] = []
        for temp_op in temp_ops:
            propagated_measurement_ssas.extend(temp_op.detectors)
            temp_op.detach()
            temp_op.erase()

        new_round = qec.DetectorRoundOp(detectors=propagated_measurement_ssas)
        # Copy stim tag from first round that carries one; warn if multiple rounds have tags
        copy_stim_tag_from_ops(
            group,
            new_round,
            "multiple DetectorRoundOps with stim tags are combined into one",
        )
        parent_block = insertion_point.parent_block()
        assert parent_block is not None, "Expected insertion point to have a parent block"
        parent_block.insert_op_after(new_round, insertion_point)

        for det_round in group:
            det_round.detach()
            det_round.erase()


class _DetectorRoundPrepass:
    """Prepass that collects detector rounds that can be combined."""

    def __init__(self) -> None:
        self.detector_rounds_to_regions_and_parallel_ops: dict[
            tuple[qec.DetectorRoundOp, ...], set[ModuleOp | qstruct.ParallelOp | MeasureOp]
        ] = {}
        self.op_to_detection_rounds: dict[
            LoopOps | ConditionalOps | qstruct.CircuitOp | None,
            set[tuple[qec.DetectorRoundOp, ...]],
        ] = {}

    def _get_measurement_ssas_of_detector(
        self, detector: SSAValue[qec.DetectorRefType]
    ) -> set[SSAValue] | None:
        """Finds all Measurement SSAs that make up a DetectorRefType SSAValue.

        Returns None if an unsupported operation is encountered while back-traversing the detector
        SSAValue."""
        measurements: set[SSAValue] = set()

        # Traverse to find DetectorOps and extract their measurements
        ops = [ssa.owner for ssa in find_backward_ssas(detector)]

        if not all(isinstance(op, qec.DetectorOp) for op in ops):
            return None

        detector_ops = cast(list[qec.DetectorOp], ops)

        for detector_op in detector_ops:
            measurements.update(measurement for measurement in detector_op.measurements)
        return measurements

    def _get_measurement_ops_of_measurement(self, measurement: SSAValue) -> set[MeasureOp] | None:
        """Finds the MeasureOps that creates a Measurement SSAValue.

        Returns None if an unsupported operation is encountered while back-traversing the
        measurement SSAValue."""
        # Traverse to find MeasureOps
        measurement_ops = [ssa.owner for ssa in find_backward_ssas(measurement)]
        if not all(isinstance(op, MeasureOp) for op in measurement_ops):
            return None
        return set(cast(list[MeasureOp], measurement_ops))

    def _get_measurement_ops_of_detector(
        self, detector: SSAValue[qec.DetectorRefType]
    ) -> set[MeasureOp] | None:
        """Finds the MeasureOps that create the Measurement SSAValues that make up a DetectorRefType
        SSAValue.

        Returns None if an unsupported operation is encountered while back-traversing the detector
        SSAValue."""
        measurements = self._get_measurement_ssas_of_detector(detector)
        if measurements is None:
            return None

        measurement_ops: set[MeasureOp] = set()
        for measurement in measurements:
            if (ops := self._get_measurement_ops_of_measurement(measurement)) is None:
                return None
            measurement_ops.update(ops)
        return measurement_ops

    def _get_measurement_ops_of_detector_round(
        self, detector_round: qec.DetectorRoundOp
    ) -> set[MeasureOp] | None:
        """Finds the MeasureOps that create the Measurement SSAValues that make up the
        DetectorRefType SSAValues in a DetectorRoundOp.

        Returns None if an unsupported operation is encountered while back-traversing the detector
        round."""
        measurement_ops: set[MeasureOp] = set()
        for detector_ref in detector_round.detectors:
            assert isa(detector_ref, SSAValue[qec.DetectorRefType]), (  # type: ignore[type-abstract]
                "Expected SSAValue of type DetectorRefType"
            )
            if (ops := self._get_measurement_ops_of_detector(detector_ref)) is None:
                return None
            measurement_ops.update(ops)
        return measurement_ops

    def _check_if_zero_or_one_non_yield_op(self, region: Region) -> bool:
        """Checks if there is only zero or one non-yield op in the region, and if so returns
        true."""
        num_ops = len(region.block.ops)
        if num_ops > 2:
            return False
        if num_ops == 1:
            assert isinstance(region.block.first_op, qstruct.YieldOp), (
                ""
                "Expected the only op in the region to be a YieldOp, but found "
                f"{type(region.block.first_op)}."
            )
            return True
        if isinstance(region.block.first_op, qstruct.ParallelOp):
            for subregion in region.block.first_op.regions:
                if not self._check_if_zero_or_one_non_yield_op(subregion):
                    return False
        return True

    def _extract_parallelisable_ancestors(
        self, op: MeasureOp
    ) -> Generator[MeasureOp | qstruct.ParallelOp]:
        """Yield itself and all parallelisable ancestors of a MeasureOp.

        A parallelisable ancestor is a ParallelOp such that each region of the ParallelOp contains
        at most one non-yield op, and any nested parallel ops also satisfy this condition
        recursively."""
        yield op
        curr_op: Operation | None = op
        while curr_op:
            parent_region = curr_op.parent_region()
            if parent_region is None:
                break
            elif self._check_if_zero_or_one_non_yield_op(parent_region):
                parent_op = parent_region.parent_op()
                if isinstance(parent_op, (qstruct.ParallelOp)):
                    yield parent_op
                curr_op = parent_op
            else:
                break

    def _get_enclosing_operation(
        self, op: Operation
    ) -> LoopOps | ConditionalOps | qstruct.CircuitOp | None:
        """Finds the parent scf.ForOp, scf.WhileOp, qstruct.RepeatOp, scf.IfOp, or
        scf.IndexSwitchOp, qstruct.CircuitOp of an operation, if it exists."""
        parent_op = op.parent_op()
        while parent_op:
            if isinstance(parent_op, (LoopOps | ConditionalOps | qstruct.CircuitOp)):
                return parent_op
            parent_op = parent_op.parent_op()
        return None

    def _check_combinable(self, op: qec.DetectorRoundOp) -> bool:
        """Checks if a DetectorRoundOp is combinable with other rounds.

        A DetectorRoundOp is combinable if it is not inside a loop, and all its detectors
        originate from DetectorOps. This is a simplification to avoid the complexity of handling
        loops and other cases."""
        parent_op = op.parent_op()
        while parent_op:
            if isinstance(parent_op, LoopOps):
                return False
            parent_op = parent_op.parent_op()

        return all(isinstance(detector_ref.owner, qec.DetectorOp) for detector_ref in op.detectors)

    def collect(self, module: ModuleOp) -> list[tuple[qec.DetectorRoundOp, ...]]:
        """Collects detector rounds into groups of rounds that can be combined together.

        The first stage is to find which rounds can be combined with this one. For simplicity,
        we restrict the possible rounds to combine with to be rounds that are in the same loop,
        conditional or circuit body.

        We first find all the measurement ops that make up the detector round. For a given
        measurement op, we do an inorder traversal of its parent parallel ops and regions,
        and compare it against the parallel ops and regions of the measurement ops of other rounds
        that we have seen so far. If the first match is a region, then they are in the same
        parallel region - they cannot be combined with each other. If the first match is a
        parallel op, then the two rounds are in parallel and can be combined together, so this
        round is passed on to the next stage.

        After processing all measurement ops that make up the measurement round, we are left
        with a set of possible measurement rounds that can be combined with this round. A round
        is then arbitrarily chosen from this set to be combined with this round.
        """
        for op in module.walk():
            if not isinstance(op, qec.DetectorRoundOp):
                continue

            # TODO: support combining rounds inside repeats.
            # In the final iteration of a repeat, detectors that have not yet been assigned a
            # round are yielded out rather than assigned one inside the repeat; they are then
            # assigned to a round outside the repeat. The stim import pipeline tracks which
            # round each repeat result belongs to so that these detectors can be assigned to
            # the correct outside round. Combining rounds inside the repeat changes that
            # round-to-result mapping, and updating it would require moving results from one
            # round to another — which is not yet implemented.
            # For now, combining rounds inside repeats is disabled, as is combining any round
            # whose detectors are results of a repeat.

            # This can be done by looking at what block args are used in the two detector rounds
            # to be combined. Then, it should be possible to trace that to the results of the
            # repeat, and then make sure all the results are in the same detector round.

            # TODO: track loop iteration counts when back-traversing measurement ops.
            # When a loop contains exactly one measurement op and no measurements precede the
            # loop, back-traversing any detector round defined inside the loop always reaches
            # that same measurement op. Two rounds may have their measurements originate from
            # different iterations of the loop, but as there is only one measurement op,
            # they appear to be in parallel.

            if not self._check_combinable(op):
                continue

            enclosing_op = self._get_enclosing_operation(op)

            # the possible rounds to combine with must be in the same loop/conditional/circuit body
            possible_rounds = self.op_to_detection_rounds.get(enclosing_op, set())

            measurement_ops = self._get_measurement_ops_of_detector_round(op)

            if measurement_ops is None:
                # unsupported operation encountered while back-traversing the detector round;
                # skip this round
                continue

            parallel_op_and_regions: set[qstruct.ParallelOp | ModuleOp | MeasureOp] = set()
            for measure_op in measurement_ops:
                inorder_regions_and_parallel_ops = []
                for parallelisable_ancestor in self._extract_parallelisable_ancestors(measure_op):
                    parallel_op_and_regions.add(parallelisable_ancestor)
                    inorder_regions_and_parallel_ops.append(parallelisable_ancestor)
                next_possible_rounds = set()
                for possible_round in possible_rounds:
                    round_ops_and_regions = self.detector_rounds_to_regions_and_parallel_ops.get(
                        possible_round, set()
                    )

                    for parallel_op_or_region in inorder_regions_and_parallel_ops:
                        if parallel_op_or_region in round_ops_and_regions:
                            next_possible_rounds.add(possible_round)
                            break
                possible_rounds = next_possible_rounds

            if possible_rounds:
                # If there are possible rounds to combine with, combine with the first one
                # (arbitrary choice)
                round_to_combine = next(iter(possible_rounds))

                new_tuple = (*round_to_combine, op)
                new_parallel_ops_and_regions = (
                    self.detector_rounds_to_regions_and_parallel_ops.get(round_to_combine, set())
                    | parallel_op_and_regions
                )
                self.detector_rounds_to_regions_and_parallel_ops[new_tuple] = (
                    new_parallel_ops_and_regions
                )
                self.op_to_detection_rounds.setdefault(enclosing_op, set()).add(new_tuple)

                # delete old entries for the individual rounds that have now been combined
                self.op_to_detection_rounds[enclosing_op].discard(round_to_combine)
                self.detector_rounds_to_regions_and_parallel_ops.pop(round_to_combine, None)
            else:
                # No possible rounds to combine with, so add this round as a new entry
                self.detector_rounds_to_regions_and_parallel_ops[(op,)] = parallel_op_and_regions
                self.op_to_detection_rounds.setdefault(enclosing_op, set()).add((op,))

        return list(self.detector_rounds_to_regions_and_parallel_ops.keys())


class CombineDetectorRounds(ModulePass):
    """Pass to combine detector rounds whose measurements are in parallel."""

    name = "combine-detector-rounds"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        detector_round_groups = _DetectorRoundPrepass().collect(op)

        _process_combined_rounds(detector_round_groups)
