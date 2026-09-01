import pytest
from xdsl.builder import ImplicitBuilder
from xdsl.dialects.builtin import ModuleOp
from xdsl.dialects.test import TestOp
from xdsl.ir import Block, SSAValue

from deltakit_compile.dialects import qstruct, stim
from deltakit_compile.passes.stim.stim_to_qec import (
    MaxMinDict,
    _calculate_block_args_num,
    _calculate_maximum_round_to_pass_in_for_repeat,
    _gather_information_about_circuit_and_repeats,
    _get_detector_round_or_shift,
    _get_number_of_detectors_in_round,
    _OperationInformation,
)


def test_get_detector_round_or_shift() -> None:
    """Test that _get_detector_round_or_shift correctly returns the round or shift value."""
    assert _get_detector_round_or_shift(stim.ShiftCoordsOp(coords=[0, 0, 4])) == 4
    assert _get_detector_round_or_shift(stim.DetectorOp(coords=[0, 0, 4], targets=[])) == 4
    with pytest.raises(
        ValueError, match=r"The final value in the coords property is not close to an integer"
    ):
        _get_detector_round_or_shift(stim.ShiftCoordsOp(coords=[0, 0, 3.9]))


def test_calculate_block_args_num_isolated() -> None:
    """Test that _calculate_block_args_num correctly calculates the number of block arguments
    needed for a block containing a RepeatOp with iter_args."""
    # repeat 2x
    #   detector<3>
    #   detector<4>
    #   detector<5>
    #   detector<6>
    #   shift_coords<2>
    nested_info = _OperationInformation(
        body_shift=2,
        repetitions=2,
        shift_at_start=3,
        detectors_per_detector_round=MaxMinDict({3: 1, 4: 1, 5: 1, 6: 1}),
        nested_circuit_and_repeat_information={},
    )
    outside_detectors: MaxMinDict[int, int] = MaxMinDict()
    max_round_to_pass_in = _calculate_maximum_round_to_pass_in_for_repeat(
        nested_info, outside_detectors._max_key
    )
    assert max_round_to_pass_in is not None
    calculated_args_num = _calculate_block_args_num(
        nested_info,
        outside_detectors,
        max_round_to_pass_in,
    )
    assert calculated_args_num == [1, 1, 2, 2, 2]


def test_calculate_block_args_num_non_isolated() -> None:
    """Test that _calculate_block_args_num correctly calculates the number of block arguments
    needed for a block containing a RepeatOp with iter_args."""
    # repeat 3x
    #   detector<3>
    #   detector<4>
    #   detector<5>
    #   detector<6>
    #   shift_coords<2>
    nested_info = _OperationInformation(
        body_shift=2,
        repetitions=3,
        shift_at_start=3,
        detectors_per_detector_round=MaxMinDict({3: 2, 4: 1, 5: 1, 6: 1, 7: 2, 8: 1, 9: 1}),
        nested_circuit_and_repeat_information={},
    )
    outside_detectors: MaxMinDict[int, int] = MaxMinDict({4: 3, 6: 4, 8: 4})
    max_round_to_pass_in = _calculate_maximum_round_to_pass_in_for_repeat(
        nested_info, outside_detectors._max_key
    )
    assert max_round_to_pass_in is not None
    calculated_args_num = _calculate_block_args_num(
        nested_info,
        outside_detectors,
        max_round_to_pass_in,
    )
    assert calculated_args_num == [1, 1, 4, 2, 5, 3, 7, 3]


def test_calculate_maximum_round_to_pass_in_when_no_detectors() -> None:
    result = _OperationInformation(
        body_shift=0,
        repetitions=3,
        shift_at_start=0,
        detectors_per_detector_round=MaxMinDict(),
        nested_circuit_and_repeat_information={},
    )
    assert _calculate_maximum_round_to_pass_in_for_repeat(result, None) is None


def test_get_number_of_detectors_in_round_with_list() -> None:
    op_round_to_ssas: MaxMinDict[int, list[SSAValue]] = MaxMinDict(
        {1: [TestOp().res, TestOp().res], 2: [TestOp().res]}
    )
    assert _get_number_of_detectors_in_round(op_round_to_ssas, 1) == 2
    assert _get_number_of_detectors_in_round(op_round_to_ssas, 2) == 1
    assert _get_number_of_detectors_in_round(op_round_to_ssas, 3) == 0


class TestPrePass:
    def test_prepass_on_repeat_with_no_detectors(self) -> None:
        """Test that _prepass correctly calculates the total shift, max round, and min round for a
        simple circuit with a RepeatOp that contains no detectors."""
        circuit_block = Block()

        with ImplicitBuilder(circuit_block):
            block = Block()

            with ImplicitBuilder(block):
                stim.ShiftCoordsOp(coords=[0, 0, 4])
                stim.ShiftCoordsOp(coords=[])
                qstruct.YieldOp()

            repeat_op = qstruct.RepeatOp(repetitions=3, body=block)

        circuit_op = qstruct.CircuitOp(arguments=[], result_types=[], body=[circuit_block])

        _repeat_result = _gather_information_about_circuit_and_repeats(repeat_op)
        _circuit_result = _gather_information_about_circuit_and_repeats(circuit_op)
        _module_result = _gather_information_about_circuit_and_repeats(ModuleOp([circuit_op]))

        _expected_repeat_result = _OperationInformation(
            repetitions=3,
            shift_at_start=0,
            body_shift=4,
            detectors_per_detector_round=MaxMinDict(),
            nested_circuit_and_repeat_information={},
        )
        _expected_circuit_result = _OperationInformation(
            repetitions=None,
            shift_at_start=0,
            body_shift=12,
            detectors_per_detector_round=MaxMinDict(),
            nested_circuit_and_repeat_information={repeat_op: _expected_repeat_result},
        )
        _expected_module_result = _OperationInformation(
            repetitions=None,
            shift_at_start=0,
            body_shift=12,
            detectors_per_detector_round=MaxMinDict(),
            nested_circuit_and_repeat_information={circuit_op: _expected_circuit_result},
        )

        assert _repeat_result == _expected_repeat_result
        assert _circuit_result == _expected_circuit_result
        assert _module_result == _expected_module_result

    def test_prepass_on_repeat(self) -> None:
        """Test that _prepass correctly calculates the total shift, max round, and min round for a
        simple circuit with a RepeatOp."""
        circuit_block = Block()

        with ImplicitBuilder(circuit_block):
            block = Block()

            with ImplicitBuilder(block):
                stim.DetectorOp(coords=[3, 4, 8], targets=[])
                stim.DetectorOp(coords=[], targets=[])
                stim.ShiftCoordsOp(coords=[0, 0, 4])
                stim.DetectorOp(coords=[3, 4, 4], targets=[])
                stim.DetectorOp(coords=[3, 4, 2], targets=[])
                stim.ShiftCoordsOp(coords=[0, 0, 6])
                stim.DetectorOp(coords=[3, 4, 1], targets=[])
                qstruct.YieldOp()

            repeat_op = qstruct.RepeatOp(repetitions=3, body=block)

        circuit_op = qstruct.CircuitOp(arguments=[], result_types=[], body=[circuit_block])

        _repeat_result = _gather_information_about_circuit_and_repeats(repeat_op)
        _circuit_result = _gather_information_about_circuit_and_repeats(circuit_op)
        _module_result = _gather_information_about_circuit_and_repeats(ModuleOp([circuit_op]))

        _expected_repeat_result = _OperationInformation(
            repetitions=3,
            shift_at_start=0,
            body_shift=10,
            detectors_per_detector_round=MaxMinDict({11: 1, 6: 1, 8: 2}),
            nested_circuit_and_repeat_information={},
        )
        _expected_circuit_result = _OperationInformation(
            repetitions=None,
            shift_at_start=0,
            body_shift=30,
            detectors_per_detector_round=MaxMinDict({31: 1}),
            nested_circuit_and_repeat_information={repeat_op: _expected_repeat_result},
        )
        _expected_module_result = _OperationInformation(
            repetitions=None,
            shift_at_start=0,
            body_shift=30,
            detectors_per_detector_round=MaxMinDict(),
            nested_circuit_and_repeat_information={circuit_op: _expected_circuit_result},
        )

        assert _repeat_result == _expected_repeat_result
        assert _circuit_result == _expected_circuit_result
        assert _module_result == _expected_module_result

    def test_prepass_on_repeat_with_detectors_before(self) -> None:
        """Test that _prepass correctly calculates the total shift, max round, and min round for a
        simple circuit with a RepeatOp."""
        circuit_block = Block()

        with ImplicitBuilder(circuit_block):
            block = Block()

            stim.DetectorOp(coords=[3, 4, 4], targets=[])
            with ImplicitBuilder(block):
                stim.DetectorOp(coords=[3, 4, 0], targets=[])
                stim.DetectorOp(coords=[3, 4, 1], targets=[])
                stim.DetectorOp(coords=[3, 4, 2], targets=[])
                stim.ShiftCoordsOp(coords=[0, 0, 1])
                qstruct.YieldOp()

            repeat_op = qstruct.RepeatOp(repetitions=3, body=block)

        circuit_op = qstruct.CircuitOp(arguments=[], result_types=[], body=[circuit_block])

        _repeat_result = _gather_information_about_circuit_and_repeats(repeat_op)
        _circuit_result = _gather_information_about_circuit_and_repeats(circuit_op)
        _module_result = _gather_information_about_circuit_and_repeats(ModuleOp([circuit_op]))

        _expected_repeat_result = _OperationInformation(
            repetitions=3,
            shift_at_start=0,
            body_shift=1,
            detectors_per_detector_round=MaxMinDict({0: 1, 1: 1, 2: 1}),
            nested_circuit_and_repeat_information={},
        )
        _expected_circuit_result = _OperationInformation(
            repetitions=None,
            shift_at_start=0,
            body_shift=3,
            detectors_per_detector_round=MaxMinDict({4: 2, 3: 2}),
            nested_circuit_and_repeat_information={repeat_op: _expected_repeat_result},
        )
        _expected_module_result = _OperationInformation(
            repetitions=None,
            shift_at_start=0,
            body_shift=3,
            detectors_per_detector_round=MaxMinDict(),
            nested_circuit_and_repeat_information={circuit_op: _expected_circuit_result},
        )

        assert _repeat_result == _expected_repeat_result
        assert _circuit_result == _expected_circuit_result
        assert _module_result == _expected_module_result

    def test_prepass_on_nested_repeat(self) -> None:
        """Test _prepass on a circuit containing a nested REPEAT.

        Inner body (x2):  DETECTOR(0,0,0) ; DETECTOR(0,0,2) ; SHIFT_COORDS(0,0,1)
        → shift=1, rounds in body at relative coords {0, 2}

        Outer body (x3):  inner_repeat ; DETECTOR(0,0,3) ; DETECTOR(0,0,4) ; DETECTOR(0,0,8) ;
        SHIFT_COORDS(0,0,3)
        → each outer iteration contains two inner iterations plus three extra detectors
        """
        inner_block = Block()
        with ImplicitBuilder(inner_block):
            stim.DetectorOp(coords=[0, 0, 0], targets=[])
            stim.DetectorOp(coords=[0, 0, 2], targets=[])
            stim.ShiftCoordsOp(coords=[0, 0, 1])
            qstruct.YieldOp()

        inner_repeat = qstruct.RepeatOp(repetitions=2, body=inner_block)

        outer_block = Block()
        with ImplicitBuilder(outer_block):
            outer_block.add_op(inner_repeat)
            stim.DetectorOp(coords=[0, 0, 3], targets=[])
            stim.DetectorOp(coords=[0, 0, 4], targets=[])
            stim.DetectorOp(coords=[0, 0, 8], targets=[])
            stim.ShiftCoordsOp(coords=[0, 0, 3])
            qstruct.YieldOp()

        outer_repeat = qstruct.RepeatOp(repetitions=3, body=outer_block)
        module = ModuleOp([outer_repeat])

        _inner_result = _gather_information_about_circuit_and_repeats(inner_repeat)
        _outer_result = _gather_information_about_circuit_and_repeats(outer_repeat)
        _module_result = _gather_information_about_circuit_and_repeats(module)

        # inner repeat: shift=1, max_round=2, min_round=0. convert to forwards traversal by adding
        # the shift
        assert _inner_result == _OperationInformation(
            repetitions=2,
            shift_at_start=0,
            body_shift=1,
            detectors_per_detector_round=MaxMinDict({0: 1, 2: 1}),
            nested_circuit_and_repeat_information={},
        )

        # # outer repeat: shift=5, max_round=10, min_round=0.
        assert _outer_result == _OperationInformation(
            repetitions=3,
            shift_at_start=0,
            body_shift=5,
            detectors_per_detector_round=MaxMinDict({2: 1, 3: 1, 5: 1, 6: 1, 10: 1}),
            nested_circuit_and_repeat_information={
                inner_repeat: _OperationInformation(
                    repetitions=2,
                    shift_at_start=0,
                    body_shift=1,
                    detectors_per_detector_round=MaxMinDict({0: 1, 2: 1}),
                    nested_circuit_and_repeat_information={},
                )
            },
        )

        # # module: shift=15, max_round=20, min_round = 0
        assert _module_result == _OperationInformation(
            repetitions=None,
            shift_at_start=0,
            body_shift=15,
            detectors_per_detector_round=MaxMinDict({20: 1, 16: 1, 15: 2}),
            nested_circuit_and_repeat_information={
                outer_repeat: _OperationInformation(
                    repetitions=3,
                    shift_at_start=0,
                    body_shift=5,
                    detectors_per_detector_round=MaxMinDict({2: 1, 3: 1, 5: 1, 6: 1, 10: 1}),
                    nested_circuit_and_repeat_information={
                        inner_repeat: _OperationInformation(
                            repetitions=2,
                            shift_at_start=0,
                            body_shift=1,
                            detectors_per_detector_round=MaxMinDict({0: 1, 2: 1}),
                            nested_circuit_and_repeat_information={},
                        )
                    },
                )
            },
        )

    def test_prepass_on_repeat_with_no_shift_throws(self) -> None:
        """Test that _prepass raises a NotImplementedError when a RepeatOp has no ShiftCoordsOp in
        its body."""
        block = Block()
        with ImplicitBuilder(block):
            stim.DetectorOp(coords=[0, 0, 0], targets=[])
            stim.DetectorOp(coords=[0, 0, 2], targets=[])
            qstruct.YieldOp()

        repeat_op = qstruct.RepeatOp(repetitions=2, body=block)

        with pytest.raises(
            NotImplementedError,
            match=(r"Repeat op found which has at least one detector placed into a round"),
        ):
            _gather_information_about_circuit_and_repeats(ModuleOp([repeat_op]))
