# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Lowers Stim dialect to qec dialect."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Final

from numpy import isclose
from typing_extensions import Any, overload, override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Operation, SSAValue
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import PatternRewriter
from xdsl.rewriter import InsertPoint, Rewriter
from xdsl.utils.hints import isa

from deltakit_compile.dialects import qec, qstruct, stim
from deltakit_compile.passes.stim._common import walk_shallow
from deltakit_compile.utilities.max_min_dict import MaxMinDict

from ._common import copy_stim_tag

LAST_DET_IN_ROUND_TAG: Final[str] = "stim_to_qec.last_det_in_round"


@dataclass(kw_only=True)
class _OperationInformation:
    """Information gathered about an operation.

    It stores the the total shift in round numbers caused by all child operations, the repetitions
    of the operation if it is a repeat, the accumulated coord shift at the point this operation
    starts, the number of detectors in each round that are a DIRECT DESCENDENT (excludes nested
    operations) of this operation, and the information for all nested operations in the body
    of this operation.

    Attributes:
        body_shift (int): The total shift in round numbers caused by child operations.
        repetitions (int | None): The number of repetitions if this operation is a repeat,
            otherwise None.
        shift_at_start (int): The accumulated coord shift at the point this operation starts,
            in the context of its parent operation. If no shift has occurred, this will be 0.
        detectors_per_detector_round (MaxMinDict[int, int]): A mapping from round number to
            the count of detectors in that round, for rounds that are a direct descendent of the
            current operation.
        nested_circuit_and_repeat_information (dict[Operation, _OperationInformation]): The
            information for circuit and repeat operations nested within the current operation.
    """

    body_shift: int
    repetitions: int | None
    shift_at_start: int
    detectors_per_detector_round: MaxMinDict[int, int]

    nested_circuit_and_repeat_information: dict[Operation, _OperationInformation]


def _calculate_maximum_round_to_pass_in_for_repeat(
    nested_information: _OperationInformation,
    forward_op_max_round_seen: int | None,
) -> int | None:
    """Calculates the maximum round number, relative to the current operation, NOT the
    nested repeat, that needs to be passed into the nested repeat op.

    Returns the maximum round number that needs to be passed into the nested repeat op,
    or None if no detectors exist in the repeat body.

    The maximum round that needs to be passed into a repeat is determined by the detectors that
    come before it and the detectors that are created in the repeat.

    For example:
        // Round number starts at 0
        Shift detectors by 1
        Detector<0> (...)  // Needs to be passed in to repeat
        Detector<1> (...)  // Needs to be passed in to repeat
        Detector<2> (...)  // Needs to be passed in to repeat
        Detector<3> (...)  // Needs to be passed in to repeat
        Repeat<4> {
            Detector<1> (...)  // Will be -1 (not needed) after the ShiftCoords<2>
            Detector<2> (...)  // Will be 0 (needed in next iteration) after the ShiftCoords<2>
            Detector<3> (...)  // Will be 1 (needed in next iteration) after the ShiftCoords<2>
            Detector<4> (...)  // Will be 2 (needed in next iteration) after the ShiftCoords<2>
            ShiftCoords<2>
        }

    The way detector rounds are created is that it will only create detector rounds when it sure
    that there can be no more detectors in the same round. We know that a detector round can have
    no more detectors when the global shift offset from SHIFT COORDS operations exceeds the
    round number of the detector. Therefore, detector rounds are created on 2 conditions:
        - When we see a SHIFT COORDS `n` operation, we know we can emit `n` rounds, corresponding
              to the `n` shifts, as we know there can be no more detectors in those rounds.
        - At the end of the circuit, we can emit all remaining rounds, as we know there can be no
            more detectors in those rounds.

    Now consider the example above. We can see there is a SHIFT COORDS of 1 before the repeat, so
    we the detector round will have been created for round 0 before we enter the repeat.

    Now consider the first iteration of the repeat, where there is a total shift of 2. From
    the previous logic, GLOBAL rounds 1 and 2 will be created at the end of the first iteration,
    as the global offset will now be 3, which is greater than the round numbers of 1 and 2.
    This can be extended to all iterations of the repeat.

    Unfortunately, looking at the rounds in terms of the global shift is cumbersome to work with.
    Rather, it would be easier to work with round numbers relative to the start of each iteration
    of the repeat. With some thought, it should be possible to see that the detector rounds op
    corresponding to rounds 0 and 1 relative to the start of each iteration will be created in
    each iteration of the repeat.

    Note no detectors in round 0 relative to the start of each iteration will be created each
    iteration (there is no Detector<0> in the body of the repeat). However, this is just a
    technicality that occurs because the detector with the lowest round created in each iteration
    of the repeat happens to be in round 1 relative to the start of each iteration, rather than
    round 0. Since we only create detector round ops for rounds we are certain are completed,
    this creates a mismatch, but this is not problematic.

    Ignoring the detectors before the loop first, it can be seen detectors in round 2, 3, and 4
    will not be assigned a detector round in the current iteration. Therefore they must be
    passed into the next iteration of the repeat. In the next iteration, they will become
    block arguments corresponding to rounds 0, 1, and 2 respectively. To see this explicitly,
    see two iterations of the repeat unrolled below

    -------- First iteration of repeat --------
    Detector<1> (...)

    Detector<2> (...) // Is in the same round as "Detector<0>" (doesn't exist) in the next
                      // iteration, so becomes a block argument corresponding to round 0.
                      // Note there is no Detector<0> actually in the body of the repeat but
                      // this doesn't matter.

    Detector<3> (...) // Is in the same round as Detector<1> in the next iteration,
                      // so becomes a block argument corresponding to round 1

    Detector<4> (...) // Is in the same round as Detector<2> in the next iteration,
                      // so becomes a block argument corresponding to round 2
    ShiftCoords<2>
    -------- Second iteration of repeat --------
    Detector<1> (...)
    Detector<2> (...)
    Detector<3> (...)
    Detector<4> (...)
    ShiftCoords<2>

    From this example, it should be clear to see that the maximum round a block arg can correspond
    to is 2. This is because the detector in round 4 will correspond to round 2 in the
    next iteration.

    Why does this matter? Because block args of a repeat correspond to operands of the repeat op,
    and the operands of the repeat op are the detectors that need to be passed into the repeat op.

    If there were no detectors before the repeat, this can then be converted to a round number
    relative to its parent operation by adding the offset accumulated at the start of the
    repeat, which is 1 in this case, so the maximum round to pass in is 3.

    Now lets consider the detectors before the repeat. Detectors in rounds 0 and 1 relative to the
    start of each iteration of the repeat will be created in the repeat. Therefore rounds from
    0-7 inclusive will be created in the repeat, relative to the first iteration of the repeat.
    Converting this to a round number relative to its parent operation, we get rounds 1-8 inclusive.
    Therefore, the maximum round to pass in min(8, max_round_seen_before_repeat), because
    why pass in detectors in rounds that will not be created in the repeat?

    In this case, the maximum round seen before the repeat is 4 (global round number), so
    the maximum round to pass in is 4 - we take the maximum of the value calculated here and the
    previous.

    If the maximum round seen_before_repeat was 10, then the maximum round to pass in would be 8,
    as we don't need to pass in detectors in rounds that will not be created in the repeat.

    If it was 2, the maximum round to pass in is now determined by the repeat body, so it is 3.

    Note there is a special case where the maximum round seen before the repeat is None,
    which means there are no detectors before and the shift per iteration is greater than the
    maximum round per repeat. In this case, there is no need to have any block args, as all
    detectors created in the repeat will be in rounds that are completed in the same iteration,
    so there is no need to pass in any detectors from previous iterations. Theoretically, the
    function should return None in this case, but in this case, we will end up returning a
    negative value. This is fine because a negative number indicates that no block args
    are needed, so the logic in `_calculate_block_args_num` will still work correctly, as it
    will never enter the loop to calculate the number of block args, and will return an empty list,
    which is correct.

    Args:
        nested_information: The prepass information for the nested repeat operation.
        forward_op_max_round_seen: The maximum round number seen so far in the forward traversal
            of the parent operation, relative to the parent operation. None if no rounds have
            been seen yet.

    Returns:
        The maximum round number (relative to the parent operation) that must be passed into
        the repeat as an operand, or None if no detectors exist in the repeat body.
    """
    max_round = nested_information.detectors_per_detector_round.max_key

    assert isinstance(nested_information.repetitions, int), (
        "Expected repetitions to be an integer when function is called as part of processing "
        "a repeat op."
    )
    max_round_created_in_repeat = nested_information.body_shift * nested_information.repetitions - 1

    if max_round is None:
        # no detectors in nested op but might need to pass in detectors previously
        if forward_op_max_round_seen is None:
            return None
        return min(
            forward_op_max_round_seen,
            max_round_created_in_repeat + nested_information.shift_at_start,
        )

    # considering just the detectors inside the body of the repeat, the maximum round we need to
    # pass in is the maximum round created in the repeat minus the body shift (as the body
    # shift is the number of rounds created per iteration)
    max_round_to_pass_in = max_round - nested_information.body_shift

    # now considering detectors before the repeat
    if forward_op_max_round_seen is not None:
        # convert forward_op_max_round_seen to the round number relative to the start of the repeat
        # by subtracting the shift at the start of the repeat
        forward_op_max_round_seen -= nested_information.shift_at_start

        max_round_created_in_repeat = (
            nested_information.body_shift * nested_information.repetitions - 1
        )
        max_round_to_pass_in = max(
            min(forward_op_max_round_seen, max_round_created_in_repeat),
            max_round_to_pass_in,
        )
    return max_round_to_pass_in + nested_information.shift_at_start


def _get_number_of_detectors_in_round(
    op_rounds_to_detector_count_or_ssas: MaxMinDict[int, list[SSAValue]] | MaxMinDict[int, int],
    round_num: int,
) -> int:
    """Gets the number of detectors in a given round, accounting for the fact that the input
    mapping may be from round to list of SSAValues instead of round to count.

    Args:
        op_rounds_to_detector_count_or_ssas: A mapping from round number to either a list of
            SSAValues corresponding to detectors in that round, or a count of the number of
            detectors in that round.
        round_num: The round number to get the detector count for.
    Returns:
        The number of detectors in the given round.
    """
    detectors_in_round = op_rounds_to_detector_count_or_ssas.get(round_num, 0)
    if isinstance(detectors_in_round, list):
        return len(detectors_in_round)
    return detectors_in_round


def _calculate_block_args_num(
    nested_information: _OperationInformation,
    forward_op_rounds_to_detector_count_or_ssas: MaxMinDict[int, list[SSAValue]]
    | MaxMinDict[int, int],
    forward_op_max_round_to_pass_in: int,
) -> list[int]:
    """Computes the block argument counts for a repeat op.

    Returns `actual_block_args_num`: list of block argument counts per round in reverse order ie
    from highest round to lowest round.

    The number of block arguments for a given round is determined by 3 factors
    - The number of detectors in the round before in the repeat
    - The number of detectors in the round created in the repeat that will be mapped onto
    this round in the next iteration (see docstring of
    _calculate_maximum_round_to_pass_in_for_repeat for more details)
    - The number of block arguments from the previous iteration that will also be mapped onto this
    round in the next iteration.

    To give a concrete example, let's say we have a repeat

    Detector<5> (...)  // Round 5
    Detector<1> (...)  // Round 1

    Repeat 5x
        Detector<1> (...)  // Round 1
        Detector<2> (...)  // Round 2
        Detector<3> (...)  // Round 3
        Detector<4> (...)  // Round 4
        Detector<5> (...)  // Round 5
        ShiftCoords<2>
    EndRepeat

    For now ignore the detector before the repeat, so we only need to consider
    the last two factors, and there is no shift in the context of its parent operation.

    Using `_calculate_maximum_round_to_pass_in_for_repeat`, we can calculate that the maximum round
    that needs to be passed in 3 (5-2). How many detectors are there that will correspond
    to round 3 in the next iteration? Only detectors in round 5 will correspond to round 3 in the
    next iteration, so the number of block argument for round 3 is the number of detectors in
    round 5, which is 1.

    What about for round 2? It can be seen of detectors that will correspond to round 2 is
    the number of detectors in round 4. In this case, therefore the number of block arguments for
    round 2 is the number of detectors in round 4, which is 1.

    For round 1, we need to consider all the detectors in round 3. However, note that
    we also have block arguments that also correspond to round 3, not just detectors created
    in the repeat body. Therefore, the number of block arguments for round 1 is the number
    of detectors in round 3 plus the number of block arguments for round 3. Therefore, the
    number is 2.

    For round 0, we need all detectors in round 2, plus all block arguments for round 2,
    which is 1 + 1 = 2.

    It can be seen to calculate the block arguments correctly, iterating from the maximum round
    to the minimum round is required, as the block argument count for lower rounds depends on
    the block argument count for higher rounds.

    When we have detectors before as well, we need to consider them as well. So for the example
    above, lets include the detectors in round 5 and 1 before the repeat. Now the maximum round
    to pass in becomes 5, as we need to account for the detector in round 5 before the repeat.

    Starting from round 5, we can see we will need at least one block argument as we need
    to be able to pass the detector from tound 5 in. We can also see there will be no
    detectors created in the repeat or other block arguments that will correspond to round 5
    in the next iteration (this would require detectors in round 7), so the number of block
    arguments for round 5 is 1.

    For round 4, we can see again no detectors will correspond to round 4 in the next iteration,
    so the number of block arguments for round 4 is 0.

    For round 3, we can see there is one detector created in the repeat that will correspond to
    round 3 and the block argument for round 5 will correspond to round 3 as well, so the
    number of block arguments for round 3 is 2.

    For round 2, you should verify the number of block arguments is 1 as before.

    For round 1, note we have 2 detectors in round 3 from a previous iteration (including block
    arguments) that will correspond to round 1. We need to also be able to pass in the
    detector in round 1 before the repeat. However, passing in the detector before the repeat
    is only done at the start of the first iteration, so we don't need to add anymore block
    arguments to account for this - we can simply have 2 block arguments that correspond to
    round 1 which is sufficient to pass in the detector before the repeat in the first iteration
    and the detectors from round 3 in subsequent iterations.

    For round 0, we have 1 detector in round 2 that will correspond to round 0, and
    1 block argument for round 2, so its still 2.

    So the block args numbers are:
    Round 5: 1
    Round 4: 0
    Round 3: 2
    Round 2: 1
    Round 1: 2
    Round 0: 2

    So the list returned is [1, 0, 2, 1, 2, 2], which is the number of block arguments for each
    round from the maximum round to pass in to the minimum round to pass in, inclusive.

    Now consider this example.

    (Detector<3>) (...) * 2

    Repeat 1x
        Detector<0> (...)  // Round 0
        Detector<1> (...)  // Round 1
        Detector<2> (...)  // Round 2
        Detector<3> (...)  // Round 3
        Detector<4> (...)  // Round 4
        Detector<5> (...)  // Round 5
        ShiftCoords<2>
    EndRepeat

    In this case, the maximum round to pass in is still 3, but we will only create detectors in
    rounds 0 and 1. We still need the block argument for round 3 to ensure correct logic, but
    we dont need to pass in the detector before the repeat in round 3. Therefore, when calculating
    the number of block arguments for round 3, we ignore the detector outside. If we run the maths
    we get:

    Round 3: 1 (ignore the 2 detectors outside)
    Round 2: 1
    Round 1: 2 (1 from the block argument and 1 from the detector in round 3)
    Round 0: 2 (1 from the block argument and 1 from the detector in round 2)

    However, some of you (who haven't fallen asleep yet) may have noticed that we actually only
    need 1 block argument for round 1.

    The easiest way to think about this is why do we need 2 block arguments that correspond to
    round 1? Well, the detector created from `Detector<3>` from the immediate previous iteration
    will correspond to round 1, and the detector created from `Detector<5>` from 2 iterations
    ago will also correspond to round 1. Therefore, we need  2 block arguments to be able to pass
    in both of these detectors in round 1. However, since we only have 1 iteration, we will never
    need to pass in the detector from 2 iterations ago, so we can get away with only 1 block
    argument for round 1.

    This simplification has not been implemented as it is not necessary for correctness, and
    the logic to implement this simplification is more complex than the current logic, so it
    has been left out for now.

    Args:
        nested_information: The prepass information for the nested repeat operation.
        forward_op_rounds_to_detector_count_or_ssas: A mapping from round number (relative to
            the parent operation) to either detector SSA values or detector counts, representing
            detectors that appear before the repeat in the parent scope.
        forward_op_max_round_to_pass_in: The maximum round number (relative to the parent
            operation) that must be passed into the repeat, as returned by
            _calculate_maximum_round_to_pass_in_for_repeat.

    Returns:
        A list of block argument counts, one per round from the maximum round to pass in down
        to the minimum round (i.e. in descending round order).
    """
    nested_repeat_shift = nested_information.body_shift
    nested_detectors = nested_information.detectors_per_detector_round
    shift = nested_information.shift_at_start
    repetitions = nested_information.repetitions
    assert isinstance(repetitions, int), (
        "Expected repetitions to be an integer when function is called as part of processing "
        "a repeat op."
    )
    max_round_created_in_repeat = nested_repeat_shift * repetitions - 1 + shift

    # we say that the minimum round to pass in is the minimum possible round that can be created
    # in the repeat - this is the shift at the start of the repeat, as even if the repeat creates
    # detectors in round 0 relative to the repeat, the minimum round to pass in is still the shift
    # at the start of the repeat.
    forward_op_min_round_to_pass_in = nested_information.shift_at_start

    actual_block_args_num: list[int] = []
    for forward_op_round in range(
        forward_op_max_round_to_pass_in,
        forward_op_min_round_to_pass_in - 1,
        -1,
    ):
        prev_block_args_num = (
            actual_block_args_num[-nested_repeat_shift]
            if len(actual_block_args_num) >= nested_repeat_shift
            else 0
        )

        current_nested_round_number = forward_op_round - shift + nested_repeat_shift

        detector_count_from_current_iteration = nested_detectors.get(current_nested_round_number, 0)

        num_block_args = detector_count_from_current_iteration + prev_block_args_num

        if forward_op_round <= max_round_created_in_repeat:
            num_detectors_outside_repeat = _get_number_of_detectors_in_round(
                forward_op_rounds_to_detector_count_or_ssas, forward_op_round
            )

            num_block_args = max(num_block_args, num_detectors_outside_repeat)
        # we first need to account for detectors before the repeat we need to pass in and the
        # detectors that will be created in the repeat that are passed into the next iteration
        actual_block_args_num.append(num_block_args)

    return actual_block_args_num


def _get_info_about_repeat_op(
    op: qstruct.RepeatOp,
    shift: int,
    max_round: float,
    detector_rounds_counter: MaxMinDict[int, int],
    parent_information: dict[Operation, _OperationInformation],
) -> tuple[int, float | int]:
    """Gets information about a repeat operation.

    Specifically works out the total shift in round numbers caused by all child operations,
    the number of repetitions, the accumulated coord shift at the point this operation starts,
    the number of detectors in each round that are a DIRECT DESCENDENT (excludes nested operations)
    of this operation, and the information for all nested operations in the body of this operation.

    Updates the mutable collections (detector_rounds_counter, parent_information)
    in place. These correspond to the detector rounds that are a direct descendent of the
    parent operation (we need to add the results of this repeat operation), and the information for
    all nested operations within the parent operation.

    Args:
        op: The repeat operation to process.
        shift: The accumulated coord shift at the point this repeat is encountered.
        max_round: The maximum round observed so far in the parent traversal.
        detector_rounds_counter: MaxMinDict mapping round number to detector count for its
            parent operation, which is updated in place with the results of this repeat
            operation.
        parent_information: The information for the parent operation, used to store the information
            for this repeat op. Mutated in place.

    Returns:
        Updated (shift, max_round) after accounting for this repeat.
    """
    repeat_result = _gather_information_about_circuit_and_repeats(op)
    # set shift at start for repeat op
    repeat_result.shift_at_start = shift

    repeat_shift = repeat_result.body_shift
    repeat_detector_max_round = repeat_result.detectors_per_detector_round.max_key

    if repeat_detector_max_round is None:
        # no detectors in repeat
        parent_information[op] = repeat_result
        return shift + repeat_shift * op.repetitions.data, max_round

    if repeat_shift == 0:
        msg = (
            "Repeat op found which has at least one detector placed into a round, (the last "
            "coordinate of a DETECTOR instruction is treated as its round number), "
            "but the repeat does not shift the detector round numbers across"
            "iterations, ie the last coordinate of all `SHIFT_COORDS` instructions is 0."
        )
        op.emit_error(msg, NotImplementedError(msg))

    repeat_last_round = shift

    parent_information[op] = repeat_result
    repeat_detector_max_round += repeat_shift * (op.repetitions.data - 1) + shift
    repeat_last_round += repeat_shift * (op.repetitions.data)

    # update shift
    shift += repeat_shift * op.repetitions.data
    # find the last (minimum forward) round created in the repeat, accounting for all iterations

    isolated_max_round_to_pass_in = _calculate_maximum_round_to_pass_in_for_repeat(
        repeat_result, None
    )
    assert isolated_max_round_to_pass_in is not None, (
        "Expected isolated_max_round_to_pass_in to be not None when repeat has detectors."
    )

    # the number of detectors we expect to see in each round that are created from the results of
    # the repeat. note this may not actually match the number of ssa results of the repeat after
    # the forward pass because detectors before the repeat that are in the same round as detectors
    # created in the repeat will also be yielded out. however, they can be ignored because they
    # be empty detectors by that point.
    isolated_block_args_num: list[int] = _calculate_block_args_num(
        repeat_result,
        MaxMinDict(),
        isolated_max_round_to_pass_in,
    )

    assert len(isolated_block_args_num) == repeat_detector_max_round - repeat_last_round + 1, (
        "Expected the number of isolated block arguments to match the number of rounds created in "
        f"the repeat but got {len(isolated_block_args_num)} and "
        f"{repeat_detector_max_round - repeat_last_round + 1}."
    )

    for round_num in range(repeat_detector_max_round, repeat_last_round - 1, -1):
        count = isolated_block_args_num[repeat_detector_max_round - round_num]
        if count:
            if round_num not in detector_rounds_counter:
                detector_rounds_counter[round_num] = count
            else:
                detector_rounds_counter[round_num] += count
            isolated_block_args_num.append(count)

    max_round = max(max_round, repeat_detector_max_round)
    return shift, max_round


def _get_detector_round_or_shift(op: stim.ShiftCoordsOp | stim.DetectorOp) -> int:
    """Extracts the round or shift value from a ShiftCoordsOp or DetectorOp.

    Args:
        op: The operation to extract the round or shift value from.

    Returns:
        The round or shift value as an integer.
    Raises:
        ValueError: If the final value in the coords property is not close to an integer.
    """
    coords = op.coords
    assert coords is not None, "Expected coords to be not None for ShiftCoordsOp or DetectorOp."
    value = coords.data[-1].value.data
    if not isclose(value, round(value)):
        msg = f"The final value in the coords property is not close to an integer: {value}."
        op.emit_error(msg, ValueError(msg))
    return round(value)


def _gather_information_about_circuit_and_repeats(
    curr_op: ModuleOp | qstruct.CircuitOp | qstruct.RepeatOp,
) -> _OperationInformation:
    """Gets information about CircuitOps, and RepeatOps. Also gathers info about ModuleOp but they
    are not used in lowering pass.

    Traverses the operations in the body of curr_op in forward order. It keeps track of:
        - The total shift in the round numbers caused by child operations, accounting for all
            iterations of nested repeats.
        - If the op is a repeat, the number of repetitions.
        - The accumulated coord shift at the point this operation starts, in the context of its
            parent operation. If no shift has occurred, this will be 0.
        - The number of detectors in each round that are a DIRECT DESCENDENT (excludes
            nested operations) of this operation.
        - The information for all nested operations in the body of this operation.

    Args:
        curr_op: The operation to prepass on.

    Returns:
        A _OperationInformation containing the total shift, max round, detector rounds, and
        nested operation information observed in the body of curr_op.
    """
    shift = 0
    max_round = -float("inf")
    detector_rounds_counter: MaxMinDict[int, int] = MaxMinDict()
    nested_information: dict[Operation, _OperationInformation] = {}
    for op in walk_shallow(curr_op):
        if isa(op, stim.DetectorOp):
            if not op.coords:
                continue
            round_num = _get_detector_round_or_shift(op) + shift
            max_round = max(max_round, round_num)
            detector_rounds_counter[round_num] = detector_rounds_counter.get(round_num, 0) + 1
        elif isa(op, stim.ShiftCoordsOp):
            if not op.coords:
                continue
            shift += _get_detector_round_or_shift(op)
        elif isa(op, qstruct.RepeatOp):
            shift, max_round = _get_info_about_repeat_op(
                op, shift, max_round, detector_rounds_counter, nested_information
            )
        elif isa(op, qstruct.CircuitOp):
            result = _gather_information_about_circuit_and_repeats(op)
            max_round_in_circuit = result.detectors_per_detector_round.max_key
            max_round = max(
                max_round,
                max_round_in_circuit + shift if max_round_in_circuit is not None else -float("inf"),
            )
            shift += result.body_shift
            nested_information[op] = result

    return _OperationInformation(
        body_shift=shift,
        repetitions=None if not isinstance(curr_op, qstruct.RepeatOp) else curr_op.repetitions.data,
        shift_at_start=0,
        detectors_per_detector_round=detector_rounds_counter,
        nested_circuit_and_repeat_information=nested_information,
    )


def _emit_n_detector_rounds(
    n: int,
    insertion_point: InsertPoint,
    rounds_to_detector_ssas: MaxMinDict[int, list[SSAValue]],
    curr_round: int,
    rewriter: PatternRewriter,
) -> None:
    """Emit 'n' detector rounds.

    Args:
        n: The number of detector rounds to emit.
        insertion_point: The insertion point at which to insert the emitted ops.
        rounds_to_detector_ssas: Mapping from round number to detector SSA values; rounds that
            are emitted are removed from this dict in place.
        curr_round: The current (next to be emitted) round number.
        rewriter: The pattern rewriter to use for inserting ops.
    """

    # check if we can start emitting detector rounds because the earliest round that needs to be
    # emitted has been finished
    while n > 0:
        dets_in_round = rounds_to_detector_ssas.get(curr_round, [])
        if dets_in_round:
            assert curr_round == rounds_to_detector_ssas.min_key, (
                "Expected the current round to be the minimum key in rounds_to_detector_ssas."
                f"Got {curr_round} and {rounds_to_detector_ssas.min_key}."
            )
            rounds_to_detector_ssas.pop_min_key()
        rewriter.insert_op(
            qec.DetectorRoundOp(list(dets_in_round)),
            insertion_point=insertion_point,
        )
        n -= 1
        curr_round += 1


def _emit_detector_rounds_until_round(
    target_round: int | None,
    insertion_point: InsertPoint,
    rounds_to_detector_ssas: MaxMinDict[int, list[SSAValue]],
    curr_round: int,
    rewriter: PatternRewriter,
) -> None:
    """Emit detector rounds until the target round (inclusive) is emitted.

    Args:
        target_round: The last round to emit (inclusive). If None, emits all remaining rounds
            in rounds_to_detector_ssas.
        insertion_point: The insertion point at which to insert the emitted ops.
        rounds_to_detector_ssas: Mapping from round number to detector SSA values; consumed
            in place as rounds are emitted.
        curr_round: The current (next to be emitted) round number.
        rewriter: The pattern rewriter to use for inserting ops.
    """
    if target_round is None:
        if rounds_to_detector_ssas:
            last_round = rounds_to_detector_ssas.max_key
            assert isinstance(last_round, int)
            target_round = last_round
        else:
            target_round = curr_round - 1

    _emit_n_detector_rounds(
        target_round - curr_round + 1,
        insertion_point,
        rounds_to_detector_ssas,
        curr_round,
        rewriter,
    )


def _replace_detector_ops(
    op: stim.DetectorOp,
    forward_rounds_to_detector_ssas: MaxMinDict[int, list[SSAValue]],
    forward_shift: int,
    rewriter: PatternRewriter,
) -> None:
    """Replaces stim.DetectorOp with qec.DetectorOp and updates mapping of detector rounds to
    SSA values.

    Mutates the forward_rounds_to_detector_ssas collection in place.

    If a detector op has no coordinates, it is directly replaced with a qec.DetectorOp with the
    same targets. Otherwise, the stim.DetectorOp is replaced with a qec.DetectorOp with the
    same targets and coordinates (except the round number), and the
    forward_rounds_to_detector_ssas is updated to map from the forward round number
    to the SSA value of the new qec.DetectorOp result.

    Args:
        op: The stim.DetectorOp to replace.
        forward_rounds_to_detector_ssas: Mapping from round number to detector SSA values;
            mutated in place with the result of the new qec.DetectorOp.
        forward_shift: The accumulated forward coord shift at the point this detector is
            encountered.
        rewriter: The pattern rewriter to use for replacing the op.
    """
    if not op.coords:
        rewriter.replace_op(op, new_op := qec.DetectorOp(measurements=op.targets), new_results=[])
        copy_stim_tag(op, new_op)
        return

    forward_op_round_num = _get_detector_round_or_shift(op) + forward_shift
    rewriter.replace_op(
        op,
        det_op := qec.DetectorOp(measurements=op.targets, coordinates=op.coords.data[:-1]),
        new_results=[],
    )
    copy_stim_tag(op, det_op)

    if forward_op_round_num not in forward_rounds_to_detector_ssas:
        forward_rounds_to_detector_ssas[forward_op_round_num] = [det_op.result]
    else:
        forward_rounds_to_detector_ssas[forward_op_round_num].append(det_op.result)


def _replace_shift_coords_ops(
    op: stim.ShiftCoordsOp,
    forward_rounds_to_detector_ssas: MaxMinDict[int, list[SSAValue]],
    forward_shift: int,
    forward_op_curr_round: int,
    rewriter: PatternRewriter,
) -> tuple[int, int]:
    """Removes shift coords ops.

    Updates the forward_shift and forward_op_curr_round by the shift amount. If the shift coords op
    has no coordinates, it is simply removed. Otherwise, the shift coords op is removed and if the
    shift amount is 'n', then 'n' detector round ops are emitted and the forward_shift and
    forward_op_curr_round are updated by 'n'. Note that the forward_op_curr_round is
    incremented by 'n' regardless of whether there are any detector rounds to emit, because even
    if there are no detector rounds to emit, the shift in coordinates still means that the current
    round has been shifted forward by 'n'.

    Args:
        op: The stim.ShiftCoordsOp to remove.
        forward_rounds_to_detector_ssas: Mapping from round number to detector SSA values;
            consumed in place as detector rounds are emitted.
        forward_shift: The accumulated forward coord shift before this op.
        forward_op_curr_round: The current round number before this op.
        rewriter: The pattern rewriter to use for erasing the op and inserting detector rounds.

    Returns:
        Updated (forward_shift, forward_op_curr_round) after processing the shift coords op.
    """
    if not op.coords:
        rewriter.erase_op(op)
        return forward_shift, forward_op_curr_round

    shift = _get_detector_round_or_shift(op)
    _emit_n_detector_rounds(
        shift,
        InsertPoint.before(op),
        forward_rounds_to_detector_ssas,
        forward_op_curr_round,
        rewriter,
    )
    forward_shift += shift
    forward_op_curr_round += shift
    rewriter.erase_op(op)
    return forward_shift, forward_op_curr_round


def _calculate_repeat_operands(
    nested_information: _OperationInformation,
    forward_op_rounds_to_detector_ssas: MaxMinDict[int, list[SSAValue]],
    forward_shift: int,
    actual_block_args_num: list[int],
    forward_op_actual_max_round_to_pass_in: int,
    rewriter: PatternRewriter,
    create_empty_dets: bool = True,
) -> list[SSAValue]:
    """Computes the operands to pass into a repeat op.

    For each round that needs to be passed into the repeat, collects the detector SSA values
    from the parent scope and pads with empty detectors where the block arg count exceeds the
    number of actual detectors available.

    Args:
        nested_information: The prepass information for the nested repeat operation.
        forward_op_rounds_to_detector_ssas: Mapping from round number to detector SSA values
            accumulated in the parent scope before the repeat.
        forward_shift: The accumulated forward coord shift at the point the repeat is encountered,
            which must equal nested_information.shift_at_start.
        actual_block_args_num: List of block argument counts per round in descending round order,
            as returned by _calculate_block_args_num.
        forward_op_actual_max_round_to_pass_in: The maximum round number (relative to the parent
            operation) that must be passed into the repeat, as returned by
            _calculate_maximum_round_to_pass_in_for_repeat.
        rewriter: The pattern rewriter used to insert empty detector ops.
        create_empty_dets: If True, insert empty qec.DetectorOp placeholders to fill slots where
            no real detector is available. Defaults to True.

    Returns:
        A list of SSA values (in descending round order) to use as operands of the repeat op.
    """
    nested_min_det = nested_information.shift_at_start
    assert nested_min_det == forward_shift, (
        "Expected nested_min_det to be equal to forward_shift when function is called as part of "
        "processing a Repeat Op."
    )
    nested_repeat_shift = nested_information.body_shift
    nested_repeat_repetitions = nested_information.repetitions
    assert isinstance(nested_repeat_repetitions, int), (
        "Expected nested_repeat_repetitions to be an integer when function is called as part of "
        "processing a Repeat Op."
    )

    forward_op_min_round_to_pass_in = nested_min_det
    repeat_operands: list[SSAValue] = []

    max_round_created_in_repeat = (
        nested_information.shift_at_start + nested_repeat_shift * nested_repeat_repetitions - 1
    )

    for i, forward_op_round in enumerate(
        range(
            forward_op_actual_max_round_to_pass_in,
            forward_op_min_round_to_pass_in - 1,
            -1,
        )
    ):
        detectors_outside_repeat = []
        if forward_op_round <= max_round_created_in_repeat:
            detectors_outside_repeat = forward_op_rounds_to_detector_ssas.get(forward_op_round, [])
            repeat_operands.extend(detectors_outside_repeat)
        if create_empty_dets and actual_block_args_num[i] > len(detectors_outside_repeat):
            empty_det_ops_results = [
                rewriter.insert_op(qec.DetectorOp(measurements=[])).result
                for _ in range(actual_block_args_num[i] - len(detectors_outside_repeat))
            ]
            repeat_operands.extend(empty_det_ops_results)

    return repeat_operands


def _add_detector_block_args_to_repeat_and_map_to_round_numbers(
    nested_op: qstruct.RepeatOp,
    forward_op_actual_max_round_to_pass_in: int,
    forward_shift: int,
    actual_block_args_num: list[int],
) -> MaxMinDict[int, list[SSAValue]]:
    """Adds block arguments and maps them to round numbers relative
    to the nested repeat.

    Each detector block arg corresponds to a round number relative to the start of each iteration
    of the repeat.

    Args:
        nested_op: The repeat op whose block to add arguments to.
        forward_op_actual_max_round_to_pass_in: The maximum round number (relative to the parent
            operation) that must be passed into the repeat, as returned by
            _calculate_maximum_round_to_pass_in_for_repeat.
        forward_shift: The accumulated forward coord shift at the point the repeat is encountered.
        actual_block_args_num: List of block argument counts per round in descending round order.

    Returns:
        A MaxMinDict mapping forward round numbers (relative to the start of the repeat body)
        to the newly added block argument SSA values for those rounds.
    """
    # dict that maps forward round numbers relative to the nested repeat to ssa values
    forwards_nested_rounds_to_detector_ssas: MaxMinDict[int, list[SSAValue]] = MaxMinDict()
    # need to add the block arguments to the dictionary
    for i in range(len(actual_block_args_num)):
        num_args = actual_block_args_num[i]
        round_num = forward_op_actual_max_round_to_pass_in - i - forward_shift
        for _ in range(num_args):
            nested_op.body.block.insert_arg(qec.DetectorRefType(), 0)
        if num_args > 0:
            forwards_nested_rounds_to_detector_ssas[round_num] = list(
                nested_op.body.block.args[:num_args]
            )
    return forwards_nested_rounds_to_detector_ssas


def _replace_yield_op_for_repeat(
    nested_op: qstruct.RepeatOp,
    forwards_nested_rounds_to_detector_ssas: MaxMinDict[int, list[SSAValue]],
    actual_block_args_num: list[int],
    nested_information: _OperationInformation,
    forward_op_actual_max_round_to_pass_in: int,
    forward_shift: int,
    rewriter: PatternRewriter,
) -> None:
    """Creates the YieldOp for the repeat body and replaces the repeat op with a new RepeatOp.

    Computes the yield operands by iterating over rounds that need to be yielded out of the
    repeat body, padding with empty DetectorOps where necessary, then replaces the old yield op
    and the old nested repeat op with new ones.

    Args:
        nested_op: The repeat op being processed.
        forwards_nested_rounds_to_detector_ssas: Mapping from forward body round numbers to
            detector SSA values accumulated inside the repeat body.
        actual_block_args_num: List of block argument counts per round in descending round order.
        nested_information: The prepass information for the nested repeat operation.
        forward_op_actual_max_round_to_pass_in: The maximum round number (relative to the parent
            operation) that must be passed into the repeat, as returned by
            _calculate_maximum_round_to_pass_in_for_repeat.
        forward_shift: The accumulated forward coord shift at the point the repeat is encountered.
        rewriter: The pattern rewriter used to insert ops and replace the yield op.
    """
    forward_nested_first_round_to_yield = nested_information.body_shift
    forward_nested_last_round_to_yield = (
        forward_op_actual_max_round_to_pass_in - forward_shift + nested_information.body_shift
    )

    yield_operands: list[SSAValue] = []
    for forward_body_round in range(
        forward_nested_first_round_to_yield, forward_nested_last_round_to_yield + 1
    ):
        dets = forwards_nested_rounds_to_detector_ssas.get(forward_body_round, [])
        detector_index = -forward_body_round + forward_nested_first_round_to_yield - 1
        num_block_args = actual_block_args_num[detector_index]
        assert num_block_args >= len(dets), (
            "Expected the number of block arguments to be greater or equal to the number of"
            f"detectors for a given round but got {len(dets)} detectors and "
            f"{num_block_args} "
            "block arguments."
        )
        # add empty detectors to plug the gap between the number of detectors we need to pass in
        # during an iteration of the repeat and the number of block args allocated for that round
        #
        # by adding the empty detectors at the start always, we can guarantee that the empty
        # detectors are at the start of the block arguments for that round, and the actual
        # detectors are at the end, which makes it easier to create rounds after the repeat
        yield_operands.extend(
            [
                rewriter.insert_op(
                    qec.DetectorOp(measurements=[]), InsertPoint.before(nested_op.yield_op)
                ).result
                for _ in range(num_block_args - len(dets))
            ]
        )
        # add the actual detectors
        yield_operands.extend(dets)

    nested_repeat_yield_op = nested_op.yield_op

    # fill the rest of the yield operands with empty detectors
    yield_operands.extend(
        [
            rewriter.insert_op(
                qec.DetectorOp(measurements=[]), InsertPoint.before(nested_repeat_yield_op)
            ).result
            for _ in range(
                sum(
                    actual_block_args_num[
                        : -forward_nested_last_round_to_yield
                        + forward_nested_first_round_to_yield
                        - 1
                    ]
                )
            )
        ]
    )

    rewriter.replace_op(
        nested_repeat_yield_op,
        new_yield_op := qstruct.YieldOp(*yield_operands + list(nested_op.yield_op.operands)),
    )
    copy_stim_tag(nested_repeat_yield_op, new_yield_op)


def _remove_detector_rounds_emitted_in_repeats(
    detector_rounds: MaxMinDict[int, Any], curr_round: int
) -> None:
    """Removes detector rounds from the forward_op_detector_rounds that are lower than the
    curr_round.

    This is used to get rid of detector rounds that would have been emitted inside the repeat
    loops, as these rounds would have already been accounted for.

    Args:
        detector_rounds: The round-keyed dict to purge; mutated in place.
        curr_round: All rounds with a key strictly less than this value are removed.
    """
    if detector_rounds:
        forward_earliest_detector_round = detector_rounds.min_key
        assert isinstance(forward_earliest_detector_round, int), (
            "Expected round numbers in detector_rounds to be integers."
        )
        while forward_earliest_detector_round < curr_round:
            detector_rounds.pop_min_key()
            if not detector_rounds:
                break
            forward_earliest_detector_round = detector_rounds.min_key
            assert isinstance(forward_earliest_detector_round, int), (
                "Expected round numbers in detector_rounds to be integers."
            )


def _replace_repeat_ops(
    nested_op: qstruct.RepeatOp,
    forward_op_rounds_to_detector_ssas: MaxMinDict[int, list[SSAValue]],
    information: _OperationInformation,
    forward_shift: int,
    forward_op_curr_round: int,
    rewriter: PatternRewriter,
) -> tuple[int, int]:
    """Handles repeat ops during the replacement of stim detectors, shift coordinates and detector
    rounds.

    Mutates forward_rounds_to_detector_ssas with results of the repeat op.

    Args:
        nested_op: The repeat op to process.
        forward_op_rounds_to_detector_ssas: Mapping from round number to detector SSA values
            accumulated in the parent scope; mutated in place.
        information: The prepass information for the parent operation containing this repeat.
        forward_shift: The accumulated forward coord shift at the point the repeat is encountered.
        forward_op_curr_round: The current round number at the point the repeat is encountered.
        rewriter: The pattern rewriter used to replace ops.

    Returns:
        Updated (forward_shift, forward_op_curr_round) after processing the repeat op.
    """
    nested_repeat_info = information.nested_circuit_and_repeat_information[nested_op]
    nested_repeat_shift = nested_repeat_info.body_shift
    nested_min_det = nested_repeat_info.shift_at_start

    forward_op_max_round_to_pass_in = _calculate_maximum_round_to_pass_in_for_repeat(
        nested_repeat_info, forward_op_rounds_to_detector_ssas.max_key
    )
    isolated_max_round_to_pass_in = _calculate_maximum_round_to_pass_in_for_repeat(
        nested_repeat_info, None
    )
    max_round_created_in_repeat = (
        nested_min_det + nested_repeat_shift * nested_op.repetitions.data - 1
    )

    if forward_op_max_round_to_pass_in is None:
        repeat_operands = list(nested_op.iter_args)
        forwards_nested_rounds_to_detector_ssas: MaxMinDict[int, list[SSAValue]] = MaxMinDict()
        actual_block_args_num = []
    else:
        actual_block_args_num = _calculate_block_args_num(
            nested_repeat_info,
            forward_op_rounds_to_detector_ssas,
            forward_op_max_round_to_pass_in,
        )

        repeat_operands = _calculate_repeat_operands(
            nested_repeat_info,
            forward_op_rounds_to_detector_ssas,
            forward_shift,
            actual_block_args_num,
            forward_op_max_round_to_pass_in,
            rewriter,
        )

        # dict that maps forward round numbers relative to the nested repeat to ssa values
        forwards_nested_rounds_to_detector_ssas = (
            _add_detector_block_args_to_repeat_and_map_to_round_numbers(
                nested_op,
                forward_op_max_round_to_pass_in,
                forward_shift,
                actual_block_args_num,
            )
        )

    forwards_nested_rounds_to_detector_ssas = _replace_stim_detector_and_shift_coords(
        nested_op, nested_repeat_info, forwards_nested_rounds_to_detector_ssas
    )

    if forward_op_max_round_to_pass_in is not None:
        _replace_yield_op_for_repeat(
            nested_op,
            forwards_nested_rounds_to_detector_ssas,
            actual_block_args_num,
            nested_repeat_info,
            forward_op_max_round_to_pass_in,
            forward_shift,
            rewriter,
        )

        # reverse to match the order of the block arguments that
        # will be added since the block arguments go left to right in
        # ascending order of rounds but we iterated in reverse order
        repeat_operands.reverse()
        repeat_operands += list(nested_op.iter_args)

    rewriter.replace_op(
        nested_op,
        new_repeat_op := qstruct.RepeatOp(
            repetitions=nested_op.repetitions,
            body=rewriter.move_region_contents_to_new_regions(nested_op.body),
            iter_args=repeat_operands,
        ),
        new_results=new_repeat_op.results[-len(nested_op.iter_args) :]
        if len(nested_op.iter_args) > 0
        else [],
    )
    copy_stim_tag(nested_op, new_repeat_op)

    forward_shift += nested_repeat_shift * nested_op.repetitions.data

    forward_first_round_outside_repeat = max_round_created_in_repeat + 1
    forward_op_curr_round = forward_first_round_outside_repeat

    _remove_detector_rounds_emitted_in_repeats(
        information.detectors_per_detector_round, forward_op_curr_round
    )

    _remove_detector_rounds_emitted_in_repeats(
        forward_op_rounds_to_detector_ssas, forward_op_curr_round
    )

    if isolated_max_round_to_pass_in is not None:
        # calculate block args for repeat in isolation (neglecting any detectors that came before)
        isolated_block_args_num = _calculate_block_args_num(
            nested_repeat_info,
            MaxMinDict(),
            isolated_max_round_to_pass_in,
        )
    else:
        isolated_block_args_num = []

    # update forward_op_rounds_to_detector_ssas with the results of the new repeat
    counter = 0
    for i, (isolated_num, actual_num) in enumerate(
        zip(isolated_block_args_num[::-1], actual_block_args_num[::-1], strict=False)
    ):
        curr_round = forward_first_round_outside_repeat + i
        start_index = counter + actual_num - isolated_num
        end_index = counter + actual_num
        if curr_round in forward_op_rounds_to_detector_ssas:
            forward_op_rounds_to_detector_ssas[curr_round].extend(
                new_repeat_op.results[start_index:end_index]
            )
        else:
            forward_op_rounds_to_detector_ssas[forward_first_round_outside_repeat + i] = list(
                new_repeat_op.results[start_index:end_index]
            )
        counter += actual_num

    return forward_shift, forward_op_curr_round


def _replace_stim_detector_and_shift_coords(
    curr_op: ModuleOp | qstruct.CircuitOp | qstruct.RepeatOp,
    information: _OperationInformation,
    forward_rounds_to_detector_ssas: MaxMinDict[int, list[SSAValue]] | None = None,
    forward_shift: int = 0,
    forward_op_curr_round: int = 0,
    forward_op_finished_round: set[int] | None = None,
) -> MaxMinDict[int, list[SSAValue]]:
    """Replace stim.DetectorOp, stim.ShiftCoordsOp with qec.DetectorOp and
    qec.DetectorRoundOp ops.

    Args:
        curr_op: The operation to perform the forward traversal on.
        information: The prepass information for the current operation.
        forward_rounds_to_detector_ssas: A MaxMinDict mapping round numbers to detector SSA values.
            The round numbers are relative to the current operation with the shift at the beginning
            of the body being considered 0. Defaults to None.
        forward_shift: The accumulated forward shift at the start of the traversal. Defaults to 0.
        forward_op_curr_round: The current round number at the start of the traversal. Defaults
            to 0.
        forward_op_finished_round: The set of round numbers that have been fully populated with
            detectors and are ready to be emitted. Defaults to None.

    Returns:
        An updated MaxMinDict mapping round numbers to detector SSA values remaining after
        the traversal (rounds that have not yet been emitted as detector round ops).
    """
    if forward_rounds_to_detector_ssas is None:
        forward_rounds_to_detector_ssas = MaxMinDict()
    if forward_op_finished_round is None:
        forward_op_finished_round = set()
    for op in walk_shallow(curr_op):
        rewriter = PatternRewriter(op)
        if isa(op, stim.DetectorOp):
            _replace_detector_ops(
                op,
                forward_rounds_to_detector_ssas,
                forward_shift,
                rewriter,
            )
        elif isa(op, stim.ShiftCoordsOp):
            forward_shift, forward_op_curr_round = _replace_shift_coords_ops(
                op,
                forward_rounds_to_detector_ssas,
                forward_shift,
                forward_op_curr_round,
                rewriter,
            )
        elif isa(op, qstruct.RepeatOp):
            forward_shift, forward_op_curr_round = _replace_repeat_ops(
                op,
                forward_rounds_to_detector_ssas,
                information,
                forward_shift,
                forward_op_curr_round,
                rewriter,
            )
        elif isa(op, qstruct.CircuitOp):
            _replace_stim_detector_and_shift_coords(
                op,
                information.nested_circuit_and_repeat_information[op],
                forward_rounds_to_detector_ssas,
                forward_shift,
                forward_op_curr_round,
                forward_op_finished_round,
            )
            circuit_max_round = information.nested_circuit_and_repeat_information[
                op
            ].detectors_per_detector_round.max_key
            forward_op_curr_round = (
                max(
                    forward_op_curr_round,
                    circuit_max_round + forward_shift + 1,
                )
                if circuit_max_round is not None
                else forward_op_curr_round
            )
            forward_shift += information.nested_circuit_and_repeat_information[op].body_shift

    if isinstance(curr_op, qstruct.CircuitOp):
        assert curr_op.body.block.last_op
        _emit_detector_rounds_until_round(
            None,
            InsertPoint.before(curr_op.yield_op),
            forward_rounds_to_detector_ssas,
            forward_op_curr_round,
            PatternRewriter(curr_op.yield_op),
        )
    return forward_rounds_to_detector_ssas


def _create_measurement_rounds(module: ModuleOp) -> None:
    """Groups consecutive stim.MeasurementGateOp results into qec.MeasurementRoundOp ops.

    Walks all operations in the module. Each contiguous run of
    stim.MeasurementGateOps is collected and then replaced by a single
    qec.MeasurementRoundOp inserted immediately before the first non-measurement op
    that follows them.

    Args:
        module: The top-level module to transform.
    """
    measurement_ssas: list[SSAValue] = []
    for op in module.walk():
        if isa(op, stim.MeasurementGateOp):
            measurement_ssas.extend(op.results)
        else:
            if not measurement_ssas:
                continue
            assert (
                measurement_ssas[0].owner.parent_block()
                == measurement_ssas[-1].owner.parent_block()
                == op.parent_block()
            ), (
                "Expected all measurement SSA values to be from the same block as the "
                "current operation."
            )
            Rewriter.insert_op(qec.MeasurementRoundOp(measurement_ssas), InsertPoint.before(op))
            measurement_ssas.clear()


def _add_get_corrected_for_observable(
    circuit_op: qstruct.CircuitOp, num_of_observables: int
) -> None:
    """Inserts qec.GetCorrectedOp and qstruct.OutputOp after the circuit op.

    For each of the first `num_of_observables` results of `circuit_op`, inserts a
    qec.GetCorrectedOp immediately after the circuit op, then collects all of their
    results into a single qstruct.OutputOp.

    Args:
        circuit_op: The circuit op whose leading observable results are to be corrected.
        num_of_observables: The number of observable SSA results at the front of
            circuit_op.res to wrap with qec.GetCorrectedOp.
    """
    if num_of_observables == 0:
        return
    observables_ssas = circuit_op.res[:num_of_observables]
    parent_block = circuit_op.parent_block()
    assert parent_block is not None, "Expected the parent block of the CircuitOp to not be None."
    insertion_op = circuit_op.next_op
    output_ssas = []
    for ssa in observables_ssas:
        Rewriter.insert_op(op := qec.GetCorrectedOp(ssa), InsertPoint(parent_block, insertion_op))
        output_ssas.append(op.result)
    Rewriter.insert_op(qstruct.OutputOp(output_ssas), InsertPoint(parent_block, insertion_op))


@overload
def _replace_stim_observable_include_ops(
    obs_id_to_ssa: dict[int, SSAValue],
    repeat_to_obs_id_enclosed: dict[qstruct.RepeatOp, list[int]],
    op: qstruct.RepeatOp,
) -> None: ...


@overload
def _replace_stim_observable_include_ops(
    obs_id_to_ssa: dict[int, SSAValue],
    repeat_to_obs_id_enclosed: dict[qstruct.RepeatOp, list[int]],
    op: qstruct.CircuitOp,
) -> tuple[qstruct.CircuitOp, int]: ...


def _replace_stim_observable_include_ops(
    obs_id_to_ssa: dict[int, SSAValue],
    repeat_to_obs_id_enclosed: dict[qstruct.RepeatOp, list[int]],
    op: qstruct.CircuitOp | qstruct.RepeatOp,
) -> None | tuple[qstruct.CircuitOp, int]:
    """Replaces Stim ObservableIncludeOps in the given operation with qec.ObservableIncludeOps
    using the provided mapping from observable id to SSA value.

    For repeat ops containing observable includes, inserts block arguments and iter args to
    thread the observable SSA values through the loop. For the top-level circuit op, also
    prepends the observable results to the circuit's result types and returns the new op.

    Args:
        obs_id_to_ssa: Mapping from Stim observable id to the SSA value representing that
            observable (a qec.DecObservableOp result). Mutated in place as
            ObservableIncludeOps are replaced.
        repeat_to_obs_id_enclosed: Mapping from RepeatOps to the list of observable ids
            enclosed within them (including in nested repeats), as returned by
            _add_observable_dec_ops.
        op: The circuit or repeat op to transform.

    Returns:
        None when called on a RepeatOp. When called on a CircuitOp, returns a tuple of the
        replacement CircuitOp and the number of observable results prepended to its results.
    """
    for child_op in walk_shallow(op):
        if isa(child_op, stim.ObservableIncludeOp):
            obs_id = child_op.observable.data
            assert obs_id in obs_id_to_ssa, (
                f"Expected to find observable id {obs_id} in obs_id_to_ssa."
            )
            Rewriter.replace_op(
                child_op,
                obs_inc_op := qec.ObservableIncludeOp(obs_id_to_ssa[obs_id], child_op.targets),
                new_results=[],
            )
            obs_id_to_ssa[obs_id] = obs_inc_op.out_obs
            copy_stim_tag(child_op, obs_inc_op)
        elif isa(child_op, qstruct.RepeatOp):
            if child_op not in repeat_to_obs_id_enclosed:
                continue
            nested_obs_id_to_ssa: dict[int, SSAValue] = {}
            nested_obs_ids = repeat_to_obs_id_enclosed[child_op]
            for obs_id in nested_obs_ids[::-1]:
                child_op.body.block.insert_arg(qec.ObservableType(), 0)
                nested_obs_id_to_ssa[obs_id] = child_op.body.block.args[0]
            nested_obs_operands = [obs_id_to_ssa[obs_id] for obs_id in nested_obs_ids]
            new_body = Rewriter.move_region_contents_to_new_regions(child_op.body)
            new_repeat_op = qstruct.RepeatOp(
                repetitions=child_op.repetitions,
                body=new_body,
                iter_args=nested_obs_operands + list(child_op.iter_args),
            )
            Rewriter.replace_op(
                child_op,
                new_repeat_op,
                new_results=list(new_repeat_op.results[len(nested_obs_ids) :])
                if child_op.results
                else [],
            )
            copy_stim_tag(child_op, new_repeat_op)
            _replace_stim_observable_include_ops(
                nested_obs_id_to_ssa, repeat_to_obs_id_enclosed, new_repeat_op
            )
            for i, obs_id in enumerate(nested_obs_ids):
                obs_id_to_ssa[obs_id] = new_repeat_op.results[i]
    yield_op = op.yield_op
    assert isa(yield_op, qstruct.YieldOp), (
        "Expected the last operation in the block to be a YieldOp."
    )
    if isinstance(op, qstruct.RepeatOp):
        # obs_id_to_ssa was built by inserting in [::-1] order, so values() is reversed relative
        # to the block args / iter_args order. Reversing restores the correct order.
        obs_yield_values = reversed(obs_id_to_ssa.values())
        Rewriter.replace_op(
            yield_op,
            new_yield_op := qstruct.YieldOp(*itertools.chain(obs_yield_values, yield_op.operands)),
        )
        copy_stim_tag(yield_op, new_yield_op)
        return None
    obs_values = obs_id_to_ssa.values()
    Rewriter.replace_op(
        yield_op, new_yield_op := qstruct.YieldOp(*itertools.chain(obs_values, yield_op.operands))
    )
    copy_stim_tag(yield_op, new_yield_op)
    new_result_types = [v.type for v in obs_values] + list(op.result_types)
    new_body = Rewriter.move_region_contents_to_new_regions(op.body)
    new_circuit_op = qstruct.CircuitOp(list(op.args), new_result_types, new_body)
    Rewriter.replace_op(op, new_circuit_op, new_results=list(new_circuit_op.res[len(obs_values) :]))
    copy_stim_tag(op, new_circuit_op)
    return new_circuit_op, len(obs_values)


def _add_observable_dec_ops(
    module: ModuleOp,
) -> tuple[dict[int, SSAValue], dict[qstruct.RepeatOp, list[int]], qstruct.CircuitOp]:
    """Adds DecObservableOps to the CircuitOp in the module for each Stim ObservableIncludeOp.

    For each unique observable id found in the module, inserts a qec.DecObservableOp at the
    start of the circuit op body and records which RepeatOps enclose that observable id.

    Args:
        module: The top-level module to scan for stim.ObservableIncludeOps.

    Returns:
        A tuple of:
            - A mapping from observable id to the SSA value of the corresponding
              qec.DecObservableOp result.
            - A mapping from RepeatOps to the list of observable ids enclosed by that
              RepeatOp (including nested RepeatOps).
            - The single qstruct.CircuitOp found in the module.
    """
    obs_id_to_ssa: dict[int, SSAValue] = {}
    repeat_to_obs_id_enclosed: dict[qstruct.RepeatOp, list[int]] = {}
    circuit_op = None
    for op in module.walk():
        if isa(op, stim.ObservableIncludeOp):
            obs_id = op.observable.data
            if obs_id in obs_id_to_ssa:
                continue
            assert circuit_op is not None, "Expected to see a CircuitOp in the module."
            Rewriter.insert_op(
                dec_obs_op := qec.DecObservableOp(),
                InsertPoint.at_start(circuit_op.body.block),
            )
            stim.ObservableIdAttr.set(dec_obs_op, obs_id)
            obs_id_to_ssa[obs_id] = dec_obs_op.results[0]
            curr_op: Operation = op
            while curr_op != circuit_op:
                parent_op = curr_op.parent_op()
                assert parent_op is not None, "Expected parent op to not be None."
                if isa(parent_op, qstruct.RepeatOp):
                    if parent_op not in repeat_to_obs_id_enclosed:
                        repeat_to_obs_id_enclosed[parent_op] = [obs_id]
                    else:
                        repeat_to_obs_id_enclosed[parent_op].append(obs_id)
                curr_op = parent_op
        elif isa(op, qstruct.CircuitOp):
            assert circuit_op is None, "Expected to only see one CircuitOp in the module."
            circuit_op = op
    assert circuit_op is not None, "Expected to see a CircuitOp in the module."
    return obs_id_to_ssa, repeat_to_obs_id_enclosed, circuit_op


@dataclass(frozen=True)
class StimToQec(ModulePass):
    """Pass that lowers Stim dialect operations to the qec dialect.

    It converts Stim Operations that relate to quantum error correction, ie detectors, shifts and
    observables, into the qec dialect.

    For observables, the difference between the two dialects is in Stim, you add measurements
    to an observable using a `OBSERVABLE_INCLUDE` with a global observable index. On the other
    hand, in the qec dialect, observables a created using a `qec.declare_observable` operation,
    which creates a SSAValue that represents the observable, and then you add measurements to it
    using a `qec.add_to_observable` operation, which takes the observable SSAValue as an
    operand and returns a new SSAValue representing the updated observable.

    For detectors and detector rounds, in Stim, the last coordinate of the detector is treated
    as its round number (if there are no coordinates, the detector is not part of any round).
    In the qec dialect, detectors are grouped explicitly using a `qec.detector_round` operation.
    You cannot add a detector to a round that has already been created, so you must group all
    detectors in the same round together into a single operation. This difference is the main
    reason for the complexity of this pass as it makes repeat operations much more complicated
    to handle, as it may be possible for detectors in the same round to be created in different
    iterations of the repeat.

    Finally, this pass will also create measurement rounds using `qec.measurement_round`
    operations. There is no equivalent in Stim, so all consecutive measurement ops are treated
    as being in the same round. Measurement rounds follow the same rules as detector rounds,
    in that you cannot add a measurement to a round that has already been created.
    """

    """Pass that lowers Stim dialect operations to the qec dialect.

    It converts Stim Operations that relate to quantum error correction, ie detectors, shifts and
    observables, into the qec dialect.

    For observables, the difference between the two dialects is in Stim, you add measurements
    to an observable using a `OBSERVABLE_INCLUDE` with a global observable index. On the other
    hand, in the qec dialect, observables a created using a `qec.declare_observable` operation,
    which creates a SSAValue that represents the observable, and then you add measurements to it
    using a `qec.add_to_observable` operation, which takes the observable SSAValue as an
    operand and returns a new SSAValue representing the updated observable.

    For detectors and detector rounds, in Stim, the last coordinate of the detector is treated
    as its round number (if there are no coordinates, the detector is not part of any round).
    In the qec dialect, detectors are grouped explicitly using a `qec.detector_round` operation.
    You cannot add a detector to a round that has already been created, so you must group all
    detectors in the same round together into a single operation. This difference is the main
    reason for the complexity of this pass as it makes repeat operations much more complicated
    to handle, as it may be possible for detectors in the same round to be created in different
    iterations of the repeat.

    Finally, this pass will also create measurement rounds using `qec.measurement_round`
    operations. There is no equivalent in Stim, so all consecutive measurement ops are treated
    as being in the same round. Measurement rounds follow the same rules as detector rounds,
    in that you cannot add a measurement to a round that has already been created.
    """

    name = "stim-to-qec"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        _information = _gather_information_about_circuit_and_repeats(op)
        _replace_stim_detector_and_shift_coords(op, _information)
        _create_measurement_rounds(op)
        observable_to_ssa, repeat_to_obs_id_enclosed, circuit_op = _add_observable_dec_ops(op)
        new_circuit_op, obs_values_len = _replace_stim_observable_include_ops(
            observable_to_ssa, repeat_to_obs_id_enclosed, circuit_op
        )
        _add_get_corrected_for_observable(new_circuit_op, obs_values_len)
