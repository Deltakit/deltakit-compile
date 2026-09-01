# This file contains information which is proprietary to Riverlane Limited
# ("Riverlane") and is Riverlane Confidential Information.

# (c) Copyright Riverlane 2026. All rights reserved.
"""Tests for the RealignQecDetectors pass."""

import pytest
import xdsl.dialects.test as t
from xdsl.builder import ImplicitBuilder
from xdsl.dialects.builtin import IntAttr, ModuleOp, i1
from xdsl.ir import Block
from xdsl.rewriter import InsertPoint

from deltakit_compile.dialects import qec, qstruct, stim
from deltakit_compile.passes.realign_qec_detectors import (
    _MOVE_DETECTOR_OP_ID_TAG,
    _assign_id_prepass,
    _find_insertion_op_or_block_for_detector_op,
    _find_insertion_op_or_block_for_detector_round_op,
    _MoveDetectorRoundPass,
)


class _NeverPlacingPattern(_MoveDetectorRoundPass):
    """Subclass that deliberately skips all placement to trigger the pending-rounds invariant."""

    def _try_place_pending_rounds(self, insert_point: InsertPoint) -> None:
        pass


DETECTOR_ID_TAG = "test_detector_id"
DETECTOR_ROUND_ID_TAG = "test_detector_round_id"


class TestAssignIdPrepass:
    def test_assigns_ids_to_flat_ops(self) -> None:
        """IDs are assigned in walk order to all ops, including the module itself."""
        det_ops = [stim.DetectorOp(coords=[], targets=[]) for _ in range(3)]
        module = ModuleOp(det_ops)

        _assign_id_prepass(module, DETECTOR_ID_TAG)

        # module receives ID 0; the three body ops receive consecutive IDs 1, 2, 3
        assert module.attributes[DETECTOR_ID_TAG] == IntAttr(0)
        for i, op in enumerate(det_ops):
            assert op.attributes[DETECTOR_ID_TAG] == IntAttr(i + 1)

    def test_assigns_ids_into_nested_ops(self) -> None:
        """IDs are assigned in walk order, descending into nested ops."""
        first_det = stim.DetectorOp(coords=[], targets=[])

        inner_block_obj = Block()
        with ImplicitBuilder(inner_block_obj):
            inner_det = stim.DetectorOp(coords=[], targets=[])
            qstruct.YieldOp()

        repeat_op = qstruct.RepeatOp(repetitions=2, body=inner_block_obj)
        after_det = stim.DetectorOp(coords=[], targets=[])
        module = ModuleOp([first_det, repeat_op, after_det])

        _assign_id_prepass(module, DETECTOR_ID_TAG)

        # Walk order: module(0), first_det(1), repeat_op(2), inner_det(3), yield(4), after_det(5)
        assert first_det.attributes[DETECTOR_ID_TAG] == IntAttr(1)
        assert inner_det.attributes[DETECTOR_ID_TAG] == IntAttr(3)
        assert after_det.attributes[DETECTOR_ID_TAG] == IntAttr(5)

    def test_all_ops_receive_ids(self) -> None:
        """Every op in the module receives an ID tag regardless of type."""
        det_op = stim.DetectorOp(coords=[], targets=[])
        shift_op = stim.ShiftCoordsOp(coords=[0, 0, 1])
        module = ModuleOp([det_op, shift_op])

        _assign_id_prepass(module, DETECTOR_ID_TAG)

        assert DETECTOR_ID_TAG in det_op.attributes
        assert DETECTOR_ID_TAG in shift_op.attributes

    def test_different_tag_names_dont_conflict(self) -> None:
        """Two prepasses with different tag names assign independent IDs."""
        det_op = stim.DetectorOp(coords=[], targets=[])

        inner_block = Block()
        with ImplicitBuilder(inner_block):
            inner_det = stim.DetectorOp(coords=[], targets=[])
            qstruct.YieldOp()

        repeat_op = qstruct.RepeatOp(repetitions=1, body=inner_block)
        module = ModuleOp([det_op, repeat_op])

        _assign_id_prepass(module, DETECTOR_ID_TAG)
        _assign_id_prepass(module, DETECTOR_ROUND_ID_TAG)

        # both tags should have the same IDs since the traversal is the same
        assert det_op.attributes[DETECTOR_ID_TAG] == det_op.attributes[DETECTOR_ROUND_ID_TAG]
        assert inner_det.attributes[DETECTOR_ID_TAG] == inner_det.attributes[DETECTOR_ROUND_ID_TAG]

    def test_ids_are_sequential_starting_from_zero(self) -> None:
        """IDs start at 0 for the first op encountered in the walk and increment by one."""
        det_op = stim.DetectorOp(coords=[], targets=[])
        shift_op = stim.ShiftCoordsOp(coords=[0, 0, 1])
        module = ModuleOp([det_op, shift_op])

        _assign_id_prepass(module, DETECTOR_ID_TAG)

        assert module.attributes[DETECTOR_ID_TAG] == IntAttr(0)
        assert det_op.attributes[DETECTOR_ID_TAG] == IntAttr(1)
        assert shift_op.attributes[DETECTOR_ID_TAG] == IntAttr(2)


class TestFindInsertionOpOrBlockForDetectorOp:
    def test_returns_none_for_no_measurements(self) -> None:
        """A detector with no measurement operands returns None."""
        det_op = qec.DetectorOp([])
        assert _find_insertion_op_or_block_for_detector_op(det_op) is None

    def test_measurement_used_by_measure_round(self) -> None:
        """When the measurement is directly used by a MeasurementRoundOp, that op is returned."""
        m = t.TestOp(result_types=[i1]).results[0]
        round_op = qec.MeasurementRoundOp([m])
        round_op.attributes[_MOVE_DETECTOR_OP_ID_TAG] = IntAttr(0)
        det_op = qec.DetectorOp([m])

        assert _find_insertion_op_or_block_for_detector_op(det_op) is round_op

    def test_multiple_measurements_returns_round_with_highest_id(self) -> None:
        """When measurements belong to different rounds, the round with the highest ID is
        returned."""
        m0 = t.TestOp(result_types=[i1]).results[0]
        m1 = t.TestOp(result_types=[i1]).results[0]
        round_op0 = qec.MeasurementRoundOp([m0])
        round_op0.attributes[_MOVE_DETECTOR_OP_ID_TAG] = IntAttr(0)
        round_op1 = qec.MeasurementRoundOp([m1])
        round_op1.attributes[_MOVE_DETECTOR_OP_ID_TAG] = IntAttr(1)
        det_op = qec.DetectorOp([m0, m1])

        assert _find_insertion_op_or_block_for_detector_op(det_op) is round_op1

    def test_measurement_from_block_arg_returns_block(self) -> None:
        """When the measurement is a block argument with no MeasurementRoundOp uses, the block is
        returned."""
        m_init = t.TestOp(result_types=[i1]).results[0]
        inner_block = Block(arg_types=[i1])
        with ImplicitBuilder(inner_block):
            det_op = qec.DetectorOp([inner_block.args[0]])
            qstruct.YieldOp(inner_block.args[0])
        repeat_op = qstruct.RepeatOp(repetitions=2, body=inner_block, iter_args=[m_init])
        repeat_op.attributes[_MOVE_DETECTOR_OP_ID_TAG] = IntAttr(0)

        assert _find_insertion_op_or_block_for_detector_op(det_op) is inner_block

    def test_measurement_from_repeat_result_returns_repeat_op(self) -> None:
        """When the measurement is a result of a RepeatOp, the RepeatOp is returned."""
        m_init = t.TestOp(result_types=[i1]).results[0]
        inner_block = Block(arg_types=[i1])
        with ImplicitBuilder(inner_block):
            qstruct.YieldOp(inner_block.args[0])
        repeat_op = qstruct.RepeatOp(repetitions=2, body=inner_block, iter_args=[m_init])
        repeat_op.attributes[_MOVE_DETECTOR_OP_ID_TAG] = IntAttr(0)

        m_result = repeat_op.res[0]
        det_op = qec.DetectorOp([m_result])

        assert _find_insertion_op_or_block_for_detector_op(det_op) is repeat_op


class TestFindInsertionOpOrBlockForDetectorRoundOp:
    def test_single_detector_op_returns_that_op(self) -> None:
        """A round targeting a single DetectorOp returns that DetectorOp."""
        m = t.TestOp(result_types=[i1]).results[0]
        det_op = qec.DetectorOp([m])
        det_op.attributes[_MOVE_DETECTOR_OP_ID_TAG] = IntAttr(5)
        round_op = qec.DetectorRoundOp([det_op.result])

        assert _find_insertion_op_or_block_for_detector_round_op(round_op) is det_op

    def test_multiple_detector_ops_returns_highest_id(self) -> None:
        """When a round targets multiple DetectorOps the one with the highest ID is returned."""
        m0 = t.TestOp(result_types=[i1]).results[0]
        m1 = t.TestOp(result_types=[i1]).results[0]
        det_op0 = qec.DetectorOp([m0])
        det_op0.attributes[_MOVE_DETECTOR_OP_ID_TAG] = IntAttr(3)
        det_op1 = qec.DetectorOp([m1])
        det_op1.attributes[_MOVE_DETECTOR_OP_ID_TAG] = IntAttr(7)
        round_op = qec.DetectorRoundOp([det_op0.result, det_op1.result])

        assert _find_insertion_op_or_block_for_detector_round_op(round_op) is det_op1

    def test_repeat_result_returns_repeat_op(self) -> None:
        """When a detector ref is the result of a RepeatOp the RepeatOp is returned."""
        m = t.TestOp(result_types=[i1]).results[0]
        det_op_init = qec.DetectorOp([m])
        det_op_init.attributes[_MOVE_DETECTOR_OP_ID_TAG] = IntAttr(1)

        inner_block = Block(arg_types=[qec.DetectorRefType()])
        with ImplicitBuilder(inner_block):
            qstruct.YieldOp(inner_block.args[0])
        repeat_op = qstruct.RepeatOp(
            repetitions=2, body=inner_block, iter_args=[det_op_init.result]
        )
        repeat_op.attributes[_MOVE_DETECTOR_OP_ID_TAG] = IntAttr(10)

        round_op = qec.DetectorRoundOp([repeat_op.res[0]])

        assert _find_insertion_op_or_block_for_detector_round_op(round_op) is repeat_op

    def test_block_arg_returns_enclosing_block(self) -> None:
        """When a detector ref is a repeat iter-arg (block argument) the enclosing block
        is returned."""
        m = t.TestOp(result_types=[i1]).results[0]
        det_op_init = qec.DetectorOp([m])
        det_op_init.attributes[_MOVE_DETECTOR_OP_ID_TAG] = IntAttr(1)

        inner_block = Block(arg_types=[qec.DetectorRefType()])
        with ImplicitBuilder(inner_block):
            round_op = qec.DetectorRoundOp([inner_block.args[0]])
            qstruct.YieldOp(inner_block.args[0])
        repeat_op = qstruct.RepeatOp(
            repetitions=2, body=inner_block, iter_args=[det_op_init.result]
        )
        repeat_op.attributes[_MOVE_DETECTOR_OP_ID_TAG] = IntAttr(10)

        assert _find_insertion_op_or_block_for_detector_round_op(round_op) is inner_block

    def test_repeat_result_beats_earlier_detector_op(self) -> None:
        """A RepeatOp result with a higher ID takes precedence over a directly-referenced
        DetectorOp with a lower ID."""
        m0 = t.TestOp(result_types=[i1]).results[0]
        m1 = t.TestOp(result_types=[i1]).results[0]

        det_op_direct = qec.DetectorOp([m0])
        det_op_direct.attributes[_MOVE_DETECTOR_OP_ID_TAG] = IntAttr(3)

        det_op_init = qec.DetectorOp([m1])
        det_op_init.attributes[_MOVE_DETECTOR_OP_ID_TAG] = IntAttr(1)
        inner_block = Block(arg_types=[qec.DetectorRefType()])
        with ImplicitBuilder(inner_block):
            qstruct.YieldOp(inner_block.args[0])
        repeat_op = qstruct.RepeatOp(
            repetitions=2, body=inner_block, iter_args=[det_op_init.result]
        )
        repeat_op.attributes[_MOVE_DETECTOR_OP_ID_TAG] = IntAttr(10)

        round_op = qec.DetectorRoundOp([det_op_direct.result, repeat_op.res[0]])

        assert _find_insertion_op_or_block_for_detector_round_op(round_op) is repeat_op

    def test_block_arg_beats_earlier_detector_op(self) -> None:
        """A block argument whose enclosing repeat op has a higher ID beats a directly-referenced
        DetectorOp with a lower ID."""
        m0 = t.TestOp(result_types=[i1]).results[0]
        m1 = t.TestOp(result_types=[i1]).results[0]

        det_op_direct = qec.DetectorOp([m0])
        det_op_direct.attributes[_MOVE_DETECTOR_OP_ID_TAG] = IntAttr(3)

        det_op_init = qec.DetectorOp([m1])
        det_op_init.attributes[_MOVE_DETECTOR_OP_ID_TAG] = IntAttr(1)
        inner_block = Block(arg_types=[qec.DetectorRefType()])
        with ImplicitBuilder(inner_block):
            round_op = qec.DetectorRoundOp([det_op_direct.result, inner_block.args[0]])
            qstruct.YieldOp(inner_block.args[0])
        repeat_op = qstruct.RepeatOp(
            repetitions=2, body=inner_block, iter_args=[det_op_init.result]
        )
        repeat_op.attributes[_MOVE_DETECTOR_OP_ID_TAG] = IntAttr(10)

        assert _find_insertion_op_or_block_for_detector_round_op(round_op) is inner_block


class TestMoveDetectorRoundPatternRewriteModule:
    def test_raises_runtime_error_if_pending_rounds_remain(self) -> None:
        """rewrite_module raises RuntimeError when pending_rounds is non-empty after the walk.

        This invariant should never be violated in correct usage; it guards against internal
        bugs in the pass.  We force the violation here by using _NeverPlacingPattern, which
        skips all placement so that every scheduled round stays in pending_rounds until the
        end-of-module check fires."""
        round_op = qec.DetectorRoundOp([])
        module = ModuleOp([round_op])
        _assign_id_prepass(module, _MOVE_DETECTOR_OP_ID_TAG)

        with pytest.raises(
            RuntimeError,
            match="realign qec detectors: some detector rounds could "
            "not be moved and are still pending after walking the whole module",
        ):
            _NeverPlacingPattern().rewrite_module(module)
