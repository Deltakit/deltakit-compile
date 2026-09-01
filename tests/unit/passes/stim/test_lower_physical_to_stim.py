import warnings

import pytest
from xdsl.builder import Builder, ImplicitBuilder
from xdsl.context import Context
from xdsl.dialects import test as t
from xdsl.dialects.builtin import (
    FloatAttr,
    IntegerAttr,
    IntegerType,
    ModuleOp,
    StringAttr,
    UnitAttr,
    i64,
)
from xdsl.ir import Block, BlockArgument, Region
from xdsl.pattern_rewriter import PatternRewriteWalker

from deltakit_compile.dialects import arith, qstruct, stim
from deltakit_compile.dialects.qcore import AllocQubitOp, QubitType, UnitaryGateAttr, XGateAttr
from deltakit_compile.dialects.qec import (
    DecObservableOp,
    DetectorOp,
    DetectorRefType,
    DetectorRoundOp,
    MeasurementRoundOp,
    ObservableType,
)
from deltakit_compile.dialects.qref import GateOp, MeasureOp
from deltakit_compile.dialects.qstruct import RepeatOp
from deltakit_compile.dialects.stim import DetectorOp as stimDetectorOp
from deltakit_compile.dialects.stim import ObservableIdAttr, TickAnnotationOp
from deltakit_compile.exceptions import (
    CompilerPassCheckError,
    LostStimTagWarning,
    StimUnsupportedGate,
    StimUnsupportedInstruction,
)
from deltakit_compile.passes.stim._common import TAG_ATTR
from deltakit_compile.passes.stim.lower_physical_to_stim import (
    _ROUND_NUM_ATTR,
    _SEEN_ATTR,
    _SHIFT_ATTR,
    LowerPhysicalToStim,
    _delete_existing_attributes,
    _detector_round_prepass,
    _DetectorPattern,
    _DetectorRoundPattern,
    _DetectorShiftPattern,
    _get_existing_observable_ids,
    _MeasurementRoundPattern,
    _ObservablePattern,
    _QStructOutputPattern,
    _RepeatPattern,
    _verify_all_stim,
)
from deltakit_compile.passes.stim.physical_gate_rewrites import InlineCircuitPattern
from tests.unit.conftest import parse_ir


def test_unknown_gate_raises_error(xdsl_context: Context):
    """Test that an unknown gate raises an error"""
    with pytest.raises(
        StimUnsupportedGate,
        match=r"Cannot map qcore gate qcore\.gate\.unitary<\.\.\. 2x2> to Deltakit-Stim enum",
    ):
        LowerPhysicalToStim(verify_all_stim=True).apply(
            xdsl_context,
            ModuleOp(
                [
                    GateOp(
                        UnitaryGateAttr([[(1, 0), (0, 0)], [(0, 0), (1, 0)]]),
                        [AllocQubitOp(QubitType()).result[0]],
                    )
                ]
            ),
        )


class TestVerifyAllStim:
    def test_verify_all_stim_raises_on_non_stim_operation(self):
        """Test that _VerifyAllStim raises StimUnsupportedInstruction for non-stim operations."""
        # Create a module with a non-stim operation (GateOp from qref dialect)
        qubit = AllocQubitOp(QubitType()).result[0]
        module = ModuleOp([GateOp(UnitaryGateAttr([[(1, 0), (0, 0)], [(0, 0), (1, 0)]]), [qubit])])

        with pytest.raises(
            StimUnsupportedInstruction,
            match=r"Non-stim operation found.",
        ):
            _verify_all_stim(module)

    def test_verify_all_stim_raises_on_unremoved_detector(self):
        """Test that _VerifyAllStim raises StimUnsupportedInstruction for unremoved DetectorOp."""
        # Create a detector operation that wasn't removed
        qubit = AllocQubitOp(QubitType()).result[0]
        measurement = MeasureOp("Z", [qubit]).measurement
        detector = (detector_op := DetectorOp([measurement])).result
        test_op = t.TestOp(operands=[detector])

        module = ModuleOp([detector_op, test_op])

        with pytest.raises(
            StimUnsupportedInstruction,
            match=r"A detector op was not removed.",
        ):
            _verify_all_stim(module)

    def test_verify_all_stim_passes_with_only_stim_ops(self):
        """Test that _VerifyAllStim does not raise when module only contains stim operations."""

        module = ModuleOp([TickAnnotationOp()])

        # Should not raise any exception
        _verify_all_stim(module)


class TestDetectorRoundPrepass:
    def test_different_length_coordinates_throws(self) -> None:
        """Test that a detector with different length coordinates throws an error."""

        m1 = arith.ConstantOp(IntegerAttr.from_bool(True)).result
        detector1 = DetectorOp(
            [m1],
            coordinates=[],
        )
        detector2 = DetectorOp(
            [m1],
            coordinates=[(FloatAttr(0.0, 64))],
        )
        module = ModuleOp([detector1, detector2])

        with pytest.raises(
            StimUnsupportedInstruction,
            match=r"All detectors must have the same number of coordinates",
        ):
            _detector_round_prepass(module)

    def test_detector_round_prepass(self) -> None:
        """Test that _detector_round_prepass assigns round and shift attributes correctly."""
        detector_ops: list[DetectorRoundOp] = []
        repeat_ops: list[qstruct.RepeatOp] = []

        @ModuleOp
        @Builder.implicit_region
        def module():
            nonlocal detector_ops, repeat_ops
            detector = t.TestOp(result_types=[DetectorRefType()]).results[0]
            detector_ops.append(DetectorRoundOp([detector]))  # round 0
            detector_ops.append(DetectorRoundOp([detector]))  # round 1

            block1 = Block()
            with ImplicitBuilder(block1):
                detector_ops.append(DetectorRoundOp([detector]))  # round 2
                detector_ops.append(DetectorRoundOp([detector]))  # round 3
                detector_ops.append(DetectorRoundOp([detector]))  # round 4

                block2 = Block()
                with ImplicitBuilder(block2):
                    detector_ops.append(DetectorRoundOp([detector]))  # round 5
                    detector_ops.append(DetectorRoundOp([detector]))  # round 6
                    detector_ops.append(DetectorRoundOp([detector]))  # round 7 - should get shift=3

                repeat_ops.append(
                    qstruct.RepeatOp(repetitions=3, body=block2)
                )  # should have shift=3

            repeat_ops.append(qstruct.RepeatOp(repetitions=3, body=block1))

            detector_ops.append(DetectorRoundOp([detector]))  # round 2

        length = _detector_round_prepass(module)

        assert length == 0, f"Expected coordinate length to be 0, got {length}"

        expected_rounds = [0, 1, 2, 3, 4, 5, 6, 7, 2]
        for i, detector_op in enumerate(detector_ops):
            assert _ROUND_NUM_ATTR in detector_op.attributes
            assert detector_op.attributes[_ROUND_NUM_ATTR] == IntegerAttr(expected_rounds[i], 64), (
                f"detector_ops[{i}] expected round={expected_rounds[i]}, got "
                f"{detector_op.attributes[_ROUND_NUM_ATTR]}"
            )

        assert _SHIFT_ATTR in detector_ops[7].attributes
        assert detector_ops[7].attributes[_SHIFT_ATTR] == IntegerAttr(3, 64)

        assert _SHIFT_ATTR in repeat_ops[0].attributes
        assert repeat_ops[0].attributes[_SHIFT_ATTR] == IntegerAttr(3, 64)

        # test_ops[1] is at module level (not inside block1), so it shouldn't have a shift
        assert _SHIFT_ATTR not in repeat_ops[1].attributes


def test_non_integer_shift_attribute_throws() -> None:
    """Test that a non-integer shift attribute throws an error."""
    detector_op = DetectorRoundOp([])
    detector_op.attributes[_SHIFT_ATTR] = FloatAttr(1.5, 64)
    module = ModuleOp([detector_op])

    with pytest.raises(
        ValueError,
        match=r"The 'shift' attribute is expected to be an IntegerAttr",
    ):
        PatternRewriteWalker(_DetectorShiftPattern(0)).rewrite_module(module)


def test_declare_observable_in_repeat_throws() -> None:
    """Test that declaring an observable in a repeat block throws an error."""

    @ModuleOp
    @Builder.implicit_region
    def module():
        repeat_block = Block()
        with ImplicitBuilder(repeat_block):
            DecObservableOp()

        RepeatOp(2, body=Region(repeat_block))

    with pytest.raises(
        StimUnsupportedInstruction,
        match=r"Defining an observable inside a loop block is not supported in Deltakit-Stim.",
    ):
        PatternRewriteWalker(_ObservablePattern({})).rewrite_module(module)


def test_qstruct_output_not_at_module_level_raises() -> None:
    """Test that a qstruct.OutputOp nested inside a non-module op raises CompilerPassCheckError."""

    @ModuleOp
    @Builder.implicit_region
    def module():
        inner_block = Block()
        with ImplicitBuilder(inner_block):
            qstruct.OutputOp([])
        t.TestOp(regions=[Region(inner_block)])

    with pytest.raises(
        CompilerPassCheckError,
        match=r"pass can only lower qstruct.output ops that are in the top level of the module",
    ):
        PatternRewriteWalker(_QStructOutputPattern()).rewrite_module(module)


class TestDetectorRoundPattern:
    def test_detector_round_pattern_with_test_op_result(self) -> None:
        """Test that _DetectorShiftPattern behaves correctly when a DetectorRoundOp has a TestOp
        result."""
        detector_round_ops: list[DetectorRoundOp] = []

        @ModuleOp
        @Builder.implicit_region
        def module():
            nonlocal detector_round_ops
            detector1 = t.TestOp(result_types=[DetectorRefType()]).results[0]
            detector2 = DetectorOp(
                [arith.ConstantOp(IntegerAttr.from_bool(True)).result], coordinates=[]
            ).result
            detector_round_ops.append(op := DetectorRoundOp([detector1, detector2]))  # round 0
            op.attributes[_ROUND_NUM_ATTR] = IntegerAttr(0, 64)

        PatternRewriteWalker(_DetectorRoundPattern()).rewrite_module(module)
        last_op = module.body.block.last_op
        assert isinstance(last_op, DetectorRoundOp), (
            f"Expected last operation to be a DetectorRoundOp, instead got {type(last_op)}"
        )
        assert len(last_op.detectors) == 1, (
            f"Expected 1 detector in the DetectorRoundOp, got {len(last_op.detectors)}"
        )
        assert last_op.attributes[_ROUND_NUM_ATTR] == IntegerAttr(0, 64), (
            f"Expected round attribute to be 0, got {last_op.attributes[_ROUND_NUM_ATTR]}"
        )
        assert not any(op.attributes.get("lower_to_stim_seen") for op in module.walk()), (
            "Expected no operations to have the 'lower_to_stim_seen' attribute after"
            "pattern application, but found at least one."
        )

    def test_detector_round_pattern_with_test_op_arg(self) -> None:
        """Test that _DetectorShiftPattern behaves correctly when a DetectorRoundOp has a TestOp
        block argument."""
        detector_round_ops: list[DetectorRoundOp] = []

        @ModuleOp
        @Builder.implicit_region
        def module():
            nonlocal detector_round_ops
            test_block = Block(arg_types=[DetectorRefType()])
            detector = test_block.args[0]
            with ImplicitBuilder(test_block):
                detector_round_ops.append(op := DetectorRoundOp([detector]))  # round 0
                op.attributes[_ROUND_NUM_ATTR] = IntegerAttr(0, 64)
            t.TestOp(regions=[Region(test_block)])

        PatternRewriteWalker(_DetectorRoundPattern()).rewrite_module(module)
        assert any(detector_round_ops[0] == op for op in module.walk())
        assert not any(op.attributes.get("lower_to_stim_seen") for op in module.walk()), (
            "Expected no operations to have the 'lower_to_stim_seen' attribute after"
            "pattern application, but found at least one."
        )

    def test_detector_round_pattern_with_detector_yielded_from_repeat(self) -> None:
        """Test that _DetectorShiftPattern behaves correctly when a detector that comes from a
        TestOp is yielded from a repeat block and used in a DetectorRoundOp."""
        detector_round_ops: list[DetectorRoundOp] = []

        @ModuleOp
        @Builder.implicit_region
        def module():
            nonlocal detector_round_ops
            detector1 = t.TestOp(result_types=[DetectorRefType()]).results[0]

            repeat_block = Block(arg_types=[DetectorRefType()])
            detector_arg = repeat_block.args[0]
            with ImplicitBuilder(repeat_block):
                yield_op = qstruct.YieldOp(detector_arg)
                yield_op.attributes[_SHIFT_ATTR] = IntegerAttr(0, 64)

            detector2 = qstruct.RepeatOp(
                2, body=Region(repeat_block), iter_args=[detector1]
            ).results[0]
            detector_round_ops.append(op := DetectorRoundOp([detector2]))
            op.attributes[_ROUND_NUM_ATTR] = IntegerAttr(0, 64)

        PatternRewriteWalker(_DetectorRoundPattern()).rewrite_module(module)
        assert any(detector_round_ops[0] == op for op in module.walk())
        assert not any(op.attributes.get("lower_to_stim_seen") for op in module.walk()), (
            "Expected no operations to have the 'lower_to_stim_seen' attribute after"
            "pattern application, but found at least one."
        )

    def test_detector_round_pattern_with_repeat_block_and_detector_from_test_op(self) -> None:
        """Test that _DetectorShiftPattern behaves correctly when a DetectorRoundOp is inside a
        repeat block with a detector from a TestOp outside the repeat block."""
        detector_round_ops: list[DetectorRoundOp] = []

        @ModuleOp
        @Builder.implicit_region
        def module():
            nonlocal detector_round_ops
            detector = t.TestOp(result_types=[DetectorRefType()]).results[0]

            repeat_block = Block(arg_types=[DetectorRefType()])
            detector_arg = repeat_block.args[0]
            with ImplicitBuilder(repeat_block):
                detector_round_ops.append(op := DetectorRoundOp([detector_arg]))  # round 0
                op.attributes[_ROUND_NUM_ATTR] = IntegerAttr(0, 64)
                yield_op = qstruct.YieldOp(detector_arg)
                yield_op.attributes[_SHIFT_ATTR] = IntegerAttr(1, 64)

            qstruct.RepeatOp(2, body=Region(repeat_block), iter_args=[detector])

        PatternRewriteWalker(_DetectorRoundPattern()).rewrite_module(module)
        assert any(detector_round_ops[0] == op for op in module.walk())
        assert not any(op.attributes.get("lower_to_stim_seen") for op in module.walk()), (
            "Expected no operations to have the 'lower_to_stim_seen' attribute after"
            "pattern application, but found at least one."
        )

    def test_detector_round_pattern_with_repeat_block_and_detector_from_test_op_and_detector_op(
        self,
    ) -> None:
        """Test that _DetectorShiftPattern behaves correctly when a DetectorRoundOp with both a
        TestOp detector in a repeat block and a DetectorOp detector outside a repeat block."""
        detector_round_ops: list[DetectorRoundOp] = []
        detector_op: list[DetectorOp] = []

        @ModuleOp
        @Builder.implicit_region
        def module():
            nonlocal detector_round_ops
            detector_op.append(
                DetectorOp([arith.ConstantOp(IntegerAttr.from_bool(True)).result], coordinates=[])
            )
            detector1 = detector_op[0].result
            repeat_block = Block(arg_types=[DetectorRefType()])
            detector_arg = repeat_block.args[0]
            with ImplicitBuilder(repeat_block):
                detector2 = t.TestOp(result_types=[DetectorRefType()]).results[0]
                detector_round_ops.append(
                    op := DetectorRoundOp([detector_arg, detector2])
                )  # round 0
                op.attributes[_ROUND_NUM_ATTR] = IntegerAttr(0, 64)
                yield_op = qstruct.YieldOp(detector2)
                yield_op.attributes[_SHIFT_ATTR] = IntegerAttr(1, 64)

            qstruct.RepeatOp(2, body=Region(repeat_block), iter_args=[detector1])

        PatternRewriteWalker(_DetectorRoundPattern()).rewrite_module(module)
        assert any(detector_round_ops[0] == op for op in module.walk())
        assert detector_op[0].attributes.get(_ROUND_NUM_ATTR) == IntegerAttr(0, 64), (
            "Expected round attribute to be 0, got "
            f"{detector_op[0].attributes.get(_ROUND_NUM_ATTR)}"
        )
        assert not any(op.attributes.get("lower_to_stim_seen") for op in module.walk()), (
            "Expected no operations to have the 'lower_to_stim_seen' attribute after"
            "pattern application, but found at least one."
        )

    def test_detector_round_pattern_with_erased_ssa_fails(self) -> None:
        """Test that _DetectorRoundPattern raises an error when a DetectorRoundOp has an SSA value
        that was erased."""

        @ModuleOp
        @Builder.implicit_region
        def module():
            detector = t.TestOp(result_types=[DetectorRefType()]).results[0]
            op = DetectorRoundOp([detector])
            op.attributes[_ROUND_NUM_ATTR] = IntegerAttr(0, 64)
            detector.erase(safe_erase=False)

        with pytest.raises(ValueError, match=r"Unknown SSA value type for detector reference."):
            PatternRewriteWalker(_DetectorRoundPattern()).rewrite_module(module)

    def test_detector_used_in_multiple_rounds_raises(self) -> None:
        """Test that _DetectorRoundPattern raises an error when a DetectorRoundOp has a detector
        that is used in multiple rounds."""

        @ModuleOp
        @Builder.implicit_region
        def module():
            detector = DetectorOp(
                [arith.ConstantOp(IntegerAttr.from_bool(True)).result], coordinates=[]
            ).result
            op1 = DetectorRoundOp([detector])
            op1.attributes[_ROUND_NUM_ATTR] = IntegerAttr(0, 64)
            op2 = DetectorRoundOp([detector])
            op2.attributes[_ROUND_NUM_ATTR] = IntegerAttr(1, 64)

        with pytest.raises(
            StimUnsupportedInstruction,
            match=r"Detector is used in multiple rounds, which is not supported in Deltakit-Stim.",
        ):
            PatternRewriteWalker(_DetectorRoundPattern()).rewrite_module(module)


def test_measurement_round_pattern() -> None:
    """Test that measurement round ops are erased"""

    @ModuleOp
    @Builder.implicit_region
    def module():
        m1 = MeasureOp("Z", [AllocQubitOp(QubitType()).result[0]]).results
        m2 = MeasureOp("X", [AllocQubitOp(QubitType()).result[0]]).results
        MeasurementRoundOp([*m1, *m2])

    PatternRewriteWalker(_MeasurementRoundPattern()).rewrite_module(module)
    for op in module.walk():
        assert not isinstance(op, MeasurementRoundOp), (
            "Expected all MeasureRoundOps to be erased, but found one."
        )


def test_detector_pattern_with_none_coords() -> None:
    """Test that a DetectorOp with None coords is handled correctly when converted to stim."""

    @ModuleOp
    @Builder.implicit_region
    def module():
        # Test case 1: coords is None and round attribute is None
        DetectorOp([arith.ConstantOp(IntegerAttr.from_bool(True)).result])

        # Test case 2: coords is None but round attribute is present
        detector2 = DetectorOp([arith.ConstantOp(IntegerAttr.from_bool(True)).result])
        detector2.attributes[_ROUND_NUM_ATTR] = IntegerAttr(5, 64)

    PatternRewriteWalker(_DetectorPattern(False)).rewrite_module(module)

    # Verify both detectors were converted to stim DetectorOp
    stim_detectors = [op for op in module.walk() if isinstance(op, stimDetectorOp)]
    assert len(stim_detectors) == 2, f"Expected 2 stim detectors, got {len(stim_detectors)}"

    # First detector should have no coords (None or empty ArrayAttr)
    assert stim_detectors[0].coords is None or len(stim_detectors[0].coords.data) == 0, (
        f"Expected first detector to have no coords, got {stim_detectors[0].coords}"
    )

    # Second detector should have round number as the only coordinate
    assert stim_detectors[1].coords is not None, "Expected second detector to have coords"
    assert len(stim_detectors[1].coords.data) == 1, (
        f"Expected second detector to have 1 coordinate, got {len(stim_detectors[1].coords.data)}"
    )
    assert stim_detectors[1].coords.data[0] == FloatAttr(5, 64), (
        f"Expected coordinate to be 5, got {stim_detectors[1].coords.data[0]}"
    )


@pytest.mark.parametrize(
    ("ir", "match"),
    [
        (
            # qubits switch places in the yield
            """
                %q1, %q2 = qcore.alloc_qubit<> -> !qcore.qubit, !qcore.qubit
                %0, %1 = qstruct.circuit(%q1, %q2 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit,
                !qcore.qubit {
                ^bb(%q1_1: !qcore.qubit, %q2_1: !qcore.qubit):
                    %q3_1, %q4_1 = qstruct.repeat<2>(%q1_1, %q2_1 : !qcore.qubit, !qcore.qubit)
                    -> !qcore.qubit, !qcore.qubit {
                    ^bb0(%q1_2: !qcore.qubit, %q2_2: !qcore.qubit):
                        qref.gate<#qcore.gate.h> (%q1_2, %q2_2)
                        qref.gate<#qcore.gate.cx> (%q1_2, %q2_2)
                        qstruct.yield %q2_1, %q1_2 : !qcore.qubit, !qcore.qubit
                    }
                    qstruct.yield %q3_1, %q4_1 : !qcore.qubit, !qcore.qubit
                }
            """,
            r"A repeat op was not removed.",
        ),
        (
            # detectors switch places in the yield
            """
            %q1, %q2 = qcore.alloc_qubit<> -> !qcore.qubit, !qcore.qubit
            %0, %1 = qstruct.circuit(%q1, %q2 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit,
            !qcore.qubit {
            ^bb(%q1_1: !qcore.qubit, %q2_1: !qcore.qubit):
                %m1 = qref.measure<Z> (%q1_1) -> i1
                %d1 = qec.detector(%m1)
                %d2 = qec.detector(%m1)
                %q3_1, %d3, %d4 = qstruct.repeat<2>(%q1_1, %d1, %d2 : !qcore.qubit,
                !qec.detector_ref, !qec.detector_ref) -> !qcore.qubit, !qec.detector_ref,
                !qec.detector_ref {
                ^bb0(%q1_2: !qcore.qubit, %d3_1: !qec.detector_ref, %d4_1: !qec.detector_ref):
                    qref.gate<#qcore.gate.h> (%q1_2)
                    qstruct.yield %q1_2, %d4_1, %d3_1 : !qcore.qubit, !qec.detector_ref,
                    !qec.detector_ref
                }
                qstruct.yield %q1_1, %q2_1 : !qcore.qubit, !qcore.qubit
            }
            """,
            r"A detector op was not removed.",
        ),
    ],
)
def test_unreplaceable_repeat_op_raises_error(ir: str, match: str, xdsl_context: Context) -> None:
    """Test that a repeat op that cannot be replaced with a stim repeat raises an error."""
    module = parse_ir(ir, xdsl_context)

    with pytest.raises(StimUnsupportedInstruction, match=match):
        LowerPhysicalToStim(verify_all_stim=True).apply(xdsl_context, module)


class TestCheckIfRewritable:
    """Test the _check_if_rewritable function, which checks whether a repeat op can be replaced
    with a stim repeat op.:"""

    def test_when_qubit_not_yielded_out(self) -> None:
        """Test that the _check_if_rewritable function correctly identifies whether a repeat op is
        rewritable when a qubit is not yielded out of the repeat block."""
        repeat_op1: qstruct.RepeatOp | None = None

        @ModuleOp
        @Builder.implicit_region
        def module():
            nonlocal repeat_op1
            q0 = stim.QubitAllocOp(0).res
            q00 = stim.QubitAllocOp(1).res
            repeat1_body = Block(arg_types=[stim.QubitType(), stim.QubitType()])
            q1, _ = repeat1_body.args
            with ImplicitBuilder(repeat1_body):
                q3 = t.TestOp(result_types=[stim.QubitType()]).res[0]
                qstruct.YieldOp(q1, q3)

            repeat_op1 = qstruct.RepeatOp(2, body=Region(repeat1_body), iter_args=[q0, q00])

        assert repeat_op1 is not None
        assert not _RepeatPattern({}, {})._check_if_rewritable(repeat_op1)

    def test_when_detector_used_in_non_qec_op(self) -> None:
        """Test that the _check_if_rewritable function correctly identifies that a repeat op is not
        rewritable when a detector is used in a non-QEC operation."""
        repeat_op1: qstruct.RepeatOp | None = None

        @ModuleOp
        @Builder.implicit_region
        def module():
            nonlocal repeat_op1
            d0 = DetectorOp([arith.ConstantOp(IntegerAttr.from_bool(True)).result]).results[0]
            repeat1_body = Block(arg_types=[DetectorRefType()])
            d1 = repeat1_body.args
            with ImplicitBuilder(repeat1_body):
                t.TestOp(operands=d1)
                qstruct.YieldOp(*d1)

            repeat_op1 = qstruct.RepeatOp(2, body=Region(repeat1_body), iter_args=[d0])

        assert repeat_op1 is not None
        assert not _RepeatPattern({}, {})._check_if_rewritable(repeat_op1)

    def test_when_qcore_qubit_operand(self) -> None:
        """Test that the _check_if_rewritable function correctly identifies that a repeat op is not
        rewritable when a there is qcore qubit operand in the repeat block."""
        repeat_op1: qstruct.RepeatOp | None = None

        @ModuleOp
        @Builder.implicit_region
        def module():
            nonlocal repeat_op1
            q0 = AllocQubitOp([QubitType()]).result[0]
            repeat1_body = Block(arg_types=[QubitType()])
            q1 = repeat1_body.args[0]
            with ImplicitBuilder(repeat1_body):
                t.TestOp(operands=[q1])
                qstruct.YieldOp(q1)

            repeat_op1 = qstruct.RepeatOp(2, body=Region(repeat1_body), iter_args=[q0])

        assert repeat_op1 is not None
        assert not _RepeatPattern({}, {})._check_if_rewritable(repeat_op1)

    def test_when_i32_block_arg(self) -> None:
        """Test that the _check_if_rewritable function correctly identifies that a repeat op is not
        rewritable when there is an i32 block argument."""
        repeat_op1: qstruct.RepeatOp | None = None

        @ModuleOp
        @Builder.implicit_region
        def module():
            nonlocal repeat_op1
            i32 = arith.ConstantOp(IntegerAttr(42, 32)).result
            repeat1_body = Block(arg_types=[IntegerType(32)])
            i32_arg = repeat1_body.args[0]
            with ImplicitBuilder(repeat1_body):
                t.TestOp(operands=[i32_arg])
                qstruct.YieldOp(i32_arg)

            repeat_op1 = qstruct.RepeatOp(2, body=Region(repeat1_body), iter_args=[i32])

        assert repeat_op1 is not None
        assert not _RepeatPattern({}, {})._check_if_rewritable(repeat_op1)

    def test_when_detector_arg_not_traversed(self) -> None:
        """Test that the _check_if_rewritable function correctly identifies that a repeat op is not
        rewritable when there is a detector argument that is not traversed."""
        repeat_op1: qstruct.RepeatOp | None = None

        @ModuleOp
        @Builder.implicit_region
        def module():
            nonlocal repeat_op1
            q0 = DetectorOp([]).result
            repeat1_body = Block(arg_types=[DetectorRefType()])
            q1 = repeat1_body.args[0]
            with ImplicitBuilder(repeat1_body):
                qstruct.YieldOp(q1)

            repeat_op1 = qstruct.RepeatOp(2, body=Region(repeat1_body), iter_args=[q0])

        assert repeat_op1 is not None
        assert not _RepeatPattern({}, {})._check_if_rewritable(repeat_op1)

    def test_when_detector_arg_traversed(self) -> None:
        """Test that the _check_if_rewritable function correctly identifies that a repeat op is not
        rewritable when there is a detector argument that is traversed."""
        repeat_op1: qstruct.RepeatOp | None = None

        q1: BlockArgument[DetectorRefType] | None = None

        @ModuleOp
        @Builder.implicit_region
        def module():
            nonlocal repeat_op1
            nonlocal q1
            q0 = DetectorOp([]).result
            repeat1_body = Block(arg_types=[DetectorRefType()])
            q1 = repeat1_body.args[0]
            with ImplicitBuilder(repeat1_body):
                qstruct.YieldOp(q1)

            repeat_op1 = qstruct.RepeatOp(2, body=Region(repeat1_body), iter_args=[q0])

        assert repeat_op1 is not None
        assert q1 is not None
        assert _RepeatPattern({q1: IntegerAttr(0, i64)}, {})._check_if_rewritable(repeat_op1)


def test_delete_existing_attributes() -> None:
    """Test that existing attributes are deleted when applying the pass multiple times."""

    op1 = t.TestOp()
    op1.attributes[_SEEN_ATTR] = UnitAttr()
    op1.attributes[_ROUND_NUM_ATTR] = IntegerAttr(5, IntegerType(64))
    op1.attributes[_SHIFT_ATTR] = IntegerAttr(3, IntegerType(64))
    op2 = t.TestOp()
    op2.attributes[_SEEN_ATTR] = UnitAttr()
    module = ModuleOp([op1, op2])

    _delete_existing_attributes(module)

    for op in module.walk():
        assert _SEEN_ATTR not in op.attributes, (
            f"Expected {_SEEN_ATTR} to be deleted, but it was found on {op}"
        )
        assert _ROUND_NUM_ATTR not in op.attributes, (
            f"Expected {_ROUND_NUM_ATTR} to be deleted, but it was found on {op}"
        )
        assert _SHIFT_ATTR not in op.attributes, (
            f"Expected {_SHIFT_ATTR} to be deleted, but it was found on {op}"
        )


def test_detector_round_in_repeat_throws() -> None:
    """Test that a DetectorRoundOp that uses the same detector inside a repeat block throws
    an error."""

    @ModuleOp
    @Builder.implicit_region
    def module():
        d0 = DetectorOp([arith.ConstantOp(IntegerAttr.from_bool(True)).result]).result
        repeat_block = Block(arg_types=[DetectorRefType()])
        d0_0 = repeat_block.args[0]
        with ImplicitBuilder(repeat_block):
            round_op = DetectorRoundOp([d0_0])
            round_op.attributes[_ROUND_NUM_ATTR] = IntegerAttr(0, 64)
            yield_op = qstruct.YieldOp(d0_0)
            yield_op.attributes[_SHIFT_ATTR] = IntegerAttr(1, 64)

        RepeatOp(2, body=Region(repeat_block), iter_args=[d0])

    with pytest.raises(
        StimUnsupportedInstruction,
        match=(
            r"During traversal of a repeat operation, the same block argument"
            r" was encountered with different round numbers."
        ),
    ):
        PatternRewriteWalker(_DetectorRoundPattern()).rewrite_module(module)


def test_observable_traversal_fails() -> None:
    """Test that an observable that is traversed in a repeat block throws an error."""

    @ModuleOp
    @Builder.implicit_region
    def module():
        obs1 = DecObservableOp().result
        obs2 = DecObservableOp().result
        repeat_block = Block(arg_types=[ObservableType(), ObservableType()])
        arg1, arg2 = repeat_block.args
        with ImplicitBuilder(repeat_block):
            qstruct.YieldOp(arg2, arg1)

        RepeatOp(2, body=Region(repeat_block), iter_args=[obs1, obs2])

    with pytest.raises(
        StimUnsupportedInstruction,
        match=r"Lower physical to stim: "
        "An observable was yielded in a repeat block and the "
        "corresponding block argument was used with a different "
        "observable. This is not supported in Deltakit-Stim ",
    ):
        PatternRewriteWalker(_ObservablePattern({})).rewrite_module(module)


def test_multiple_observables_with_same_id_throws() -> None:
    """Test that multiple DecObservableOps with the same ID throws an error."""

    @ModuleOp
    @Builder.implicit_region
    def module():
        obs1 = DecObservableOp()
        ObservableIdAttr.set(obs1, 0)
        obs2 = DecObservableOp()
        ObservableIdAttr.set(obs2, 0)

    with pytest.raises(
        ValueError,
        match=r"Duplicate observable id 0 found. Observable ids must be unique.",
    ):
        PatternRewriteWalker(
            _ObservablePattern(_get_existing_observable_ids(module))
        ).rewrite_module(module)


def _make_module_with_obs_ids(*ids: int) -> ModuleOp:
    """Helper to build a ModuleOp containing DecObservableOps with the given explicit IDs."""

    @ModuleOp
    @Builder.implicit_region
    def module():
        for obs_id in ids:
            op = DecObservableOp()
            ObservableIdAttr.set(op, obs_id)

    return module


def test_conflicting_qubit_ids_raises() -> None:
    module = ModuleOp([AllocQubitOp([QubitType(), QubitType()], ids=[2, 2])])
    with pytest.raises(ValueError, match=r"Duplicate qubit id 2 found"):
        LowerPhysicalToStim().apply(Context(), module)

    module = ModuleOp([AllocQubitOp([QubitType()], ids=[3]), AllocQubitOp([QubitType()], ids=[3])])
    with pytest.raises(ValueError, match=r"Duplicate qubit id 3 found"):
        LowerPhysicalToStim().apply(Context(), module)


class TestGetExistingObservableIds:
    def test_no_obs_ids_returns_empty_dict(self) -> None:
        """With no DecObservableOps the result is an empty dict."""
        module = ModuleOp([])
        assert _get_existing_observable_ids(module) == {}

    def test_single_id_returns_singleton_interval(self) -> None:
        """A single existing id n maps to {n: n+1}."""
        module = _make_module_with_obs_ids(5)
        assert _get_existing_observable_ids(module) == {5: 6}

    def test_non_adjacent_ids_are_separate_intervals(self) -> None:
        """IDs with a gap between them stay as separate intervals."""
        module = _make_module_with_obs_ids(0, 5)
        assert _get_existing_observable_ids(module) == {0: 1, 5: 6}

    def test_right_adjacent_ids_merge(self) -> None:
        """IDs [1, 2] in order → merged interval {1: 3}."""
        module = _make_module_with_obs_ids(1, 2)
        assert _get_existing_observable_ids(module) == {1: 3}

    def test_left_adjacent_ids_merge(self) -> None:
        """IDs [3, 2] where the new id is left-adjacent → merged interval {2: 4}."""
        module = _make_module_with_obs_ids(3, 2)
        assert _get_existing_observable_ids(module) == {2: 4}

    def test_both_adjacent_ids_merge(self) -> None:
        """IDs [1, 3, 2] where 2 bridges 1 and 3 → single interval {1: 4}."""
        module = _make_module_with_obs_ids(1, 3, 2)
        assert _get_existing_observable_ids(module) == {1: 4}

    def test_right_merge_before_left_merge(self) -> None:
        """IDs [3, 1, 2] — right-merge happens when processing 2 (2+1=3 already a block start)
        then left-merge joins with 1 → single interval {1: 4}."""
        module = _make_module_with_obs_ids(3, 1, 2)
        assert _get_existing_observable_ids(module) == {1: 4}

    def test_ids_without_explicit_attr_are_ignored(self) -> None:
        """DecObservableOps without observable IDs are skipped."""

        @ModuleOp
        @Builder.implicit_region
        def module():
            DecObservableOp()  # no observable ID set

        assert _get_existing_observable_ids(module) == {}

    def test_duplicate_id_raises(self) -> None:
        """Duplicate explicit IDs raise ValueError."""
        module = _make_module_with_obs_ids(2, 2)
        with pytest.raises(ValueError, match=r"Duplicate observable id 2 found"):
            _get_existing_observable_ids(module)


class TestStimTagPreservation:
    """Tests that stim tags are copied or warned about during lowering."""

    def test_gate_tag_preserved(self, xdsl_context: Context) -> None:
        """Tags on qref.GateOp are copied to the new stim.CliffordGateOp."""
        qubit = AllocQubitOp(QubitType()).result[0]
        gate_op = GateOp(XGateAttr(), [qubit])
        gate_op.attributes[TAG_ATTR] = StringAttr("my_tag")
        module = ModuleOp([qubit.owner, gate_op])
        LowerPhysicalToStim().apply(xdsl_context, module)
        clifford_ops = [op for op in module.walk() if isinstance(op, stim.CliffordGateOp)]
        assert len(clifford_ops) == 1
        assert clifford_ops[0].attributes.get(TAG_ATTR) == StringAttr("my_tag")

    def test_measurement_round_tag_warns(self) -> None:
        """A stim tag on a MeasurementRoundOp triggers a StimTagLostWarning."""

        @ModuleOp
        @Builder.implicit_region
        def module():
            m = MeasureOp("Z", [AllocQubitOp(QubitType()).result[0]]).results
            op = MeasurementRoundOp([*m])
            op.attributes[TAG_ATTR] = StringAttr("lost_tag")

        with pytest.warns(LostStimTagWarning, match="qec.measurement_round"):
            PatternRewriteWalker(_MeasurementRoundPattern()).rewrite_module(module)

    def test_measurement_round_no_tag_no_warn(self) -> None:
        """No warning is emitted when a MeasurementRoundOp has no stim tag."""

        @ModuleOp
        @Builder.implicit_region
        def module():
            m = MeasureOp("Z", [AllocQubitOp(QubitType()).result[0]]).results
            MeasurementRoundOp([*m])

        with warnings.catch_warnings():
            warnings.simplefilter("error", LostStimTagWarning)
            PatternRewriteWalker(_MeasurementRoundPattern()).rewrite_module(module)

    def test_inline_circuit_tag_warns(self, xdsl_context: Context) -> None:
        """A stim tag on a qstruct.CircuitOp triggers a StimTagLostWarning when inlined."""

        @ModuleOp
        @Builder.implicit_region
        def module():
            qubit = AllocQubitOp(QubitType()).result[0]
            body = Block(arg_types=[QubitType()])
            with ImplicitBuilder(body):
                qstruct.YieldOp()
            circuit = qstruct.CircuitOp(arguments=[qubit], result_types=[], body=Region(body))
            circuit.attributes[TAG_ATTR] = StringAttr("circuit_tag")

        with pytest.warns(LostStimTagWarning, match="qstruct.circuit"):
            PatternRewriteWalker(InlineCircuitPattern()).rewrite_module(module)
