"""Tests for the FlattenQubitRegistersPass."""

import warnings

import pytest
from xdsl.builder import ImplicitBuilder
from xdsl.context import Context
from xdsl.dialects import test
from xdsl.dialects.builtin import ModuleOp, StringAttr, i1
from xdsl.ir import Block, Region, SSAValue
from xdsl.pattern_rewriter import (
    PatternRewriteWalker,
)
from xdsl.utils.hints import isa

from deltakit_compile.dialects import qcore, qstruct
from deltakit_compile.dialects.stim import TAG_ATTR
from deltakit_compile.exceptions import LostStimTagWarning
from deltakit_compile.passes.flatten_qubit_registers import (
    FlattenQubitRegisters,
    _AllocPattern,
    _CircuitPattern,
    _ConcatenatePattern,
    _ConditionPattern,
    _ForPattern,
    _IfPattern,
    _IndexSwitchPattern,
    _ParallelPattern,
    _RepeatPattern,
    _SplitPattern,
    _WhilePattern,
    _YieldPattern,
    flatten_qubit_registers,
)
from tests.unit.conftest import parse_ir


@pytest.mark.parametrize(
    ("ir"),
    [
        """
        %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
        %q0, %q1 = qcore.unpack_qubit_reg(%qreg0 : !qcore.qubit_reg<2>)
        %q00 = "test.op"(%q0) : (!qcore.qubit) -> !qcore.qubit_reg<2>
        %q11 = "test.op"(%q1) : (!qcore.qubit) -> !qcore.qubit_reg<2>

        """,
    ],
)
def test_flatten_qubit_registers_unexpected_result(ir: str, xdsl_context: Context):
    """Test that the FlattenQubitRegistersPass raises an error for unexpected QubitRegType
    results."""
    module_op = parse_ir(ir, xdsl_context)
    flatten_pass = FlattenQubitRegisters()
    with pytest.raises(
        ValueError,
        match=r"Found QubitRegType result in test\.op at TestOp\([\s\S]*!qcore\.qubit_reg<2>"
        r"[\s\S]*\)\. All qubit registers should have been flattened\.",
    ):
        flatten_pass.apply(xdsl_context, module_op)


def test_flatten_qubit_registers_block_argument(xdsl_context: Context):
    """Test that the FlattenQubitRegistersPass raises an error for unexpected QubitRegType block
    arguments."""
    block = Block()
    block.insert_arg(qcore.QubitRegType(2), 0)

    module_op = ModuleOp(
        ops=[
            test.TestOp(
                result_types=[i1],
                operands=[qcore.AllocQubitOp(qcore.QubitType()).result[0]],
                regions=[[block]],
            )
        ]
    )

    flatten_pass = FlattenQubitRegisters()

    with pytest.raises(
        ValueError,
        match=r"Found QubitRegType block argument in test\.op at TestOp\([\s\S]*!qcore\.qubit"
        r"_reg<2>[\s\S]*\)\. All qubit registers should have been flattened\.",
    ):
        flatten_pass.apply(xdsl_context, module_op)


@pytest.mark.parametrize(
    ("ir", "expected_ir"),
    [
        (
            # Flattens simple qubit register ops within a qstruct.circuit region
            """
            %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
            %q0, %q1 = qcore.unpack_qubit_reg(%qreg0 : !qcore.qubit_reg<2>)
            qstruct.circuit (%q0, %q1 : !qcore.qubit, !qcore.qubit)
                {flatten = 1} -> !qcore.qubit, !qcore.qubit {
            ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit):
                %qreg1 = qcore.pack_qubit_reg(%q0_1) -> !qcore.qubit_reg<1>
                %qreg2 = qcore.pack_qubit_reg(%q1_1) -> !qcore.qubit_reg<1>
                %qreg3 = qcore.concatenate(%qreg1, %qreg2 : !qcore.qubit_reg<1>,
                    !qcore.qubit_reg<1>) -> !qcore.qubit_reg<2>
                %q2, %q3 = qcore.unpack_qubit_reg(%qreg3 : !qcore.qubit_reg<2>)
                qstruct.yield %q2, %q3 : !qcore.qubit, !qcore.qubit
            }
            """,
            """
            %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
            %q0, %q1 = qcore.unpack_qubit_reg(%qreg0 : !qcore.qubit_reg<2>)
            qstruct.circuit (%q0, %q1 : !qcore.qubit, !qcore.qubit)
                {flatten = 1} -> !qcore.qubit, !qcore.qubit {
            ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit):
                qstruct.yield %q0_1, %q1_1 : !qcore.qubit, !qcore.qubit
            }
            """,
        ),
        (
            # Flattens more complex qubit register ops within a qstruct.circuit region
            """
            %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<4>
            %q0, %q1, %q2, %q3 = qcore.unpack_qubit_reg(%qreg0 : !qcore.qubit_reg<4>)
            qstruct.circuit (%q0, %q1, %q2, %q3 : !qcore.qubit, !qcore.qubit, !qcore.qubit,
                !qcore.qubit) {flatten = 1} -> !qcore.qubit, !qcore.qubit, !qcore.qubit,
                !qcore.qubit {
            ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit, %q2_1: !qcore.qubit,
                %q3_1: !qcore.qubit):
                %qreg1 = qcore.pack_qubit_reg(%q0_1, %q1_1) -> !qcore.qubit_reg<2>
                %qreg2 = qcore.pack_qubit_reg(%q2_1, %q3_1) -> !qcore.qubit_reg<2>
                %qreg3 = qcore.concatenate(%qreg1, %qreg2 : !qcore.qubit_reg<2>,
                    !qcore.qubit_reg<2>) -> !qcore.qubit_reg<4>
                %qreg4, %qreg5 = qcore.split(%qreg3 : !qcore.qubit_reg<4>) -> !qcore.qubit_reg<1>,
                    !qcore.qubit_reg<3>
                %qreg6 = qcore.concatenate(%qreg5, %qreg4 : !qcore.qubit_reg<3>,
                    !qcore.qubit_reg<1>) -> !qcore.qubit_reg<4>
                %q4, %q5, %q6, %q7 = qcore.unpack_qubit_reg(%qreg6 : !qcore.qubit_reg<4>)
                qstruct.yield %q4, %q5, %q6, %q7 : !qcore.qubit, !qcore.qubit, !qcore.qubit,
                    !qcore.qubit
            }
            """,
            """
            %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<4>
            %q0, %q1, %q2, %q3 = qcore.unpack_qubit_reg(%qreg0 : !qcore.qubit_reg<4>)
            qstruct.circuit (%q0, %q1, %q2, %q3 : !qcore.qubit, !qcore.qubit, !qcore.qubit,
                !qcore.qubit) {flatten = 1} -> !qcore.qubit, !qcore.qubit, !qcore.qubit,
                !qcore.qubit {
            ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit, %q2_1: !qcore.qubit,
                %q3_1: !qcore.qubit):
                qstruct.yield %q1_1, %q2_1, %q3_1, %q0_1 : !qcore.qubit, !qcore.qubit, !qcore.qubit,
                    !qcore.qubit
            }
            """,
        ),
        (
            # Registers referenced from outside the region are unpacked
            """
            %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
            %qreg1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
            %b = "test.op"() : () -> i1
            scf.if %b -> (!qcore.qubit) {
                %qreg2 = qcore.concatenate(%qreg0, %qreg1 : !qcore.qubit_reg<2>,
                    !qcore.qubit_reg<2>) -> !qcore.qubit_reg<4>
                %q0, %q1, %q2, %q3 = qcore.unpack_qubit_reg(%qreg2 : !qcore.qubit_reg<4>)
                scf.yield %q0 : !qcore.qubit
            } else {
                %qreg3 = qcore.concatenate(%qreg1, %qreg0 : !qcore.qubit_reg<2>,
                    !qcore.qubit_reg<2>) -> !qcore.qubit_reg<4>
                %q4, %q5, %q6, %q7 = qcore.unpack_qubit_reg(%qreg3 : !qcore.qubit_reg<4>)
                scf.yield %q4 : !qcore.qubit
            } {flatten = 1}
            """,
            """
            %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
            %qreg1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
            %b = "test.op"() : () -> i1
            scf.if %b -> (!qcore.qubit) {
                %qreg2, %qreg2_1 = qcore.unpack_qubit_reg(%qreg0 : !qcore.qubit_reg<2>)
                scf.yield %qreg2 : !qcore.qubit
            } else {
                %qreg3, %qreg3_1 = qcore.unpack_qubit_reg(%qreg1 : !qcore.qubit_reg<2>)
                scf.yield %qreg3 : !qcore.qubit
            } {flatten = 1}
            """,
        ),
    ],
)
def test_flatten_in_region(ir: str, expected_ir: str, xdsl_context: Context):
    """Test that the flatten_qubit_registers function correctly flattens within a region."""
    module_op = parse_ir(ir, xdsl_context)
    expected_module_op = parse_ir(expected_ir, xdsl_context)

    for op in module_op.walk():
        if "flatten" in op.attributes:
            for region in op.regions:
                flatten_qubit_registers(region)

    assert str(module_op) == str(expected_module_op)


@pytest.mark.parametrize(
    ("ir", "expected"),
    [
        (
            """
            %qreg0, %qreg1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2>
            %qreg2 = qcore.concatenate(%qreg0, %qreg1 : !qcore.qubit_reg<2>, !qcore.qubit_reg<2>)
            -> !qcore.qubit_reg<4>
            "test.op"(%qreg2) : (!qcore.qubit_reg<4>) -> ()
            """,
            """
            %qreg0, %qreg1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2>
            %qreg2, %qreg2_1 = qcore.unpack_qubit_reg(%qreg0 : !qcore.qubit_reg<2>)
            %qreg2_2, %qreg2_3 = qcore.unpack_qubit_reg(%qreg1 : !qcore.qubit_reg<2>)
            %qreg2_4 = qcore.pack_qubit_reg(%qreg2, %qreg2_1, %qreg2_2, %qreg2_3)
            -> !qcore.qubit_reg<4>
            "test.op"(%qreg2_4) : (!qcore.qubit_reg<4>) -> ()
            """,
        ),
    ],
)
def test_concatenate_pattern(ir, expected, xdsl_context: Context):
    """Test that the ConcatenatePattern correctly lowers ConcatenateOp into UnpackQubitRegOp and
    PackQubitRegOp."""
    module_op = parse_ir(ir, xdsl_context)
    expected_module_op = parse_ir(expected, xdsl_context)
    PatternRewriteWalker(
        _ConcatenatePattern(),
    ).rewrite_module(module_op)
    assert str(module_op) == str(expected_module_op)


@pytest.mark.parametrize(
    ("ir", "expected"),
    [
        (
            """
            %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<4>
            %qreg1, %qreg2 = qcore.split(%qreg0 : !qcore.qubit_reg<4>)
            -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2>
            "test.op"(%qreg1, %qreg2) : (!qcore.qubit_reg<2>, !qcore.qubit_reg<2>) -> ()
            """,
            """
            %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<4>
            %0, %1, %2, %3 = qcore.unpack_qubit_reg(%qreg0 : !qcore.qubit_reg<4>)
            %qreg1 = qcore.pack_qubit_reg(%0, %1) -> !qcore.qubit_reg<2>
            %qreg2 = qcore.pack_qubit_reg(%2, %3) -> !qcore.qubit_reg<2>
            "test.op"(%qreg1, %qreg2) : (!qcore.qubit_reg<2>, !qcore.qubit_reg<2>) -> ()
            """,
        ),
    ],
)
def test_split_pattern(ir, expected, xdsl_context: Context):
    """Test that the SplitPattern correctly lowers SplitOp into UnpackQubitRegOp and
    PackQubitRegOp."""
    module_op = parse_ir(ir, xdsl_context)
    expected_module_op = parse_ir(expected, xdsl_context)
    PatternRewriteWalker(
        _SplitPattern(),
    ).rewrite_module(module_op)
    assert str(module_op) == str(expected_module_op)


@pytest.mark.parametrize(
    ("ir", "expected"),
    [
        (
            """
            %qreg0, %q0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>, !qcore.qubit
            "test.op"(%qreg0, %q0) : (!qcore.qubit_reg<2>, !qcore.qubit) -> ()
            """,
            """
            %0, %1, %q0 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
            %qreg0 = qcore.pack_qubit_reg(%0, %1) -> !qcore.qubit_reg<2>
            "test.op"(%qreg0, %q0) : (!qcore.qubit_reg<2>, !qcore.qubit) -> ()
            """,
        ),
    ],
)
def test_alloc_pattern(ir, expected, xdsl_context: Context):
    """Test that the AllocPattern correctly flattens AllocQubitOp with qubit register results."""
    module_op = parse_ir(ir, xdsl_context)
    expected_module_op = parse_ir(expected, xdsl_context)
    PatternRewriteWalker(
        _AllocPattern(),
    ).rewrite_module(module_op)
    assert str(module_op) == str(expected_module_op)


@pytest.mark.parametrize(
    ("ir", "expected"),
    [
        (
            # Flattens operands and results
            """
            %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
            %qreg0_pack = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
            %qreg1 = qstruct.circuit(%qreg0_pack: !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
            ^bb(%arg0 : !qcore.qubit_reg<2>):
                qstruct.yield %arg0 : !qcore.qubit_reg<2>
            }
            "test.op"(%qreg1) : (!qcore.qubit_reg<2>) -> ()
            """,
            """
            %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
            %qreg0_pack = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
            %qreg1, %qreg1_1 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit)
            -> !qcore.qubit, !qcore.qubit {
            ^bb(%0: !qcore.qubit, %1: !qcore.qubit):
                %arg0 = qcore.pack_qubit_reg(%0, %1) -> !qcore.qubit_reg<2>
                qstruct.yield %arg0 : !qcore.qubit_reg<2>
            }
            %qreg1_2 = qcore.pack_qubit_reg(%qreg1, %qreg1_1) -> !qcore.qubit_reg<2>
            "test.op"(%qreg1_2) : (!qcore.qubit_reg<2>) -> ()
            """,
        ),
        (
            # Flattens results only
            """
            %qreg0_pack = qcore.alloc_qubit -> !qcore.qubit_reg<2>
            %qreg1 = qstruct.circuit(%qreg0_pack: !qcore.qubit_reg<2>)
            -> !qcore.qubit_reg<2> {
            ^bb(%arg0 : !qcore.qubit_reg<2>):
                qstruct.yield %arg0 : !qcore.qubit_reg<2>
            }
            "test.op"(%qreg1) : (!qcore.qubit_reg<2>) -> ()
            """,
            """
            %qreg0_pack = qcore.alloc_qubit -> !qcore.qubit_reg<2>
            %qreg1, %qreg1_1 = qstruct.circuit(%qreg0_pack : !qcore.qubit_reg<2>)
            -> !qcore.qubit, !qcore.qubit {
            ^bb(%arg0: !qcore.qubit_reg<2>):
                qstruct.yield %arg0 : !qcore.qubit_reg<2>
            }
            %qreg1_2 = qcore.pack_qubit_reg(%qreg1, %qreg1_1) -> !qcore.qubit_reg<2>
            "test.op"(%qreg1_2) : (!qcore.qubit_reg<2>) -> ()
            """,
        ),
    ],
)
def test_circuit_pattern(ir, expected, xdsl_context: Context):
    """Test that the CircuitPattern correctly flattens CircuitOp with qubit register
    arguments/results."""
    module_op = parse_ir(ir, xdsl_context)
    expected_module_op = parse_ir(expected, xdsl_context, verify=False)
    PatternRewriteWalker(_CircuitPattern()).rewrite_module(module_op)
    assert str(module_op) == str(expected_module_op)


@pytest.mark.parametrize(
    ("ir", "expected"),
    [
        (
            # Flattens operands and results
            """
            %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
            %qreg0_pack = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
            %qreg1 = qstruct.repeat<2>(%qreg0_pack: !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
            ^bb(%arg1 : !qcore.qubit_reg<2>):
                qstruct.yield %arg1 : !qcore.qubit_reg<2>
            }
            "test.op"(%qreg1) : (!qcore.qubit_reg<2>) -> ()
            """,
            """
            %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
            %qreg0_pack = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
            %qreg1, %qreg1_1 = qstruct.repeat<2> (%q0, %q1 : !qcore.qubit, !qcore.qubit)
            -> !qcore.qubit, !qcore.qubit {
            ^bb(%0: !qcore.qubit, %1: !qcore.qubit):
                %arg1 = qcore.pack_qubit_reg(%0, %1) -> !qcore.qubit_reg<2>
                qstruct.yield %arg1 : !qcore.qubit_reg<2>
            }
            %qreg1_2 = qcore.pack_qubit_reg(%qreg1, %qreg1_1) -> !qcore.qubit_reg<2>
            "test.op"(%qreg1_2) : (!qcore.qubit_reg<2>) -> ()
            """,
        ),
        (
            # Flattens nothing - results and operands are linked together
            """
            %qreg0_pack = qcore.alloc_qubit -> !qcore.qubit_reg<2>
            %qreg1 = qstruct.repeat<2>(%qreg0_pack: !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
            ^bb(%arg1 : !qcore.qubit_reg<2>):
                qstruct.yield %arg1 : !qcore.qubit_reg<2>
            }
            "test.op"(%qreg1) : (!qcore.qubit_reg<2>) -> ()
            """,
            """
            %qreg0_pack = qcore.alloc_qubit -> !qcore.qubit_reg<2>
            %qreg1 = qstruct.repeat<2> (%qreg0_pack : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
            ^bb(%arg1: !qcore.qubit_reg<2>):
                qstruct.yield %arg1 : !qcore.qubit_reg<2>
            }
            "test.op"(%qreg1) : (!qcore.qubit_reg<2>) -> ()
            """,
        ),
    ],
)
def test_repeat_pattern(ir, expected, xdsl_context: Context):
    """Test that the RepeatPattern correctly flattens RepeatOp with qubit register iter_args."""
    module_op = parse_ir(ir, xdsl_context)
    expected_module_op = parse_ir(expected, xdsl_context, verify=False)
    PatternRewriteWalker(_RepeatPattern()).rewrite_module(module_op)
    assert str(module_op) == str(expected_module_op)


@pytest.mark.parametrize(
    ("ir", "expected"),
    [
        (
            # Flattens results
            """
            %qreg1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
            %qreg2 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
            %qreg3, %qreg4 = qstruct.parallel<TOP> -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2> {
                qstruct.yield %qreg1 : !qcore.qubit_reg<2>
            } {
                qstruct.yield %qreg2 : !qcore.qubit_reg<2>
            }
            "test.op"(%qreg3, %qreg4) : (!qcore.qubit_reg<2>, !qcore.qubit_reg<2>) -> ()
            """,
            """
            %qreg1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
            %qreg2 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
            %0, %1, %2, %3 = qstruct.parallel<TOP> -> !qcore.qubit, !qcore.qubit, !qcore.qubit,
            !qcore.qubit {
                qstruct.yield %qreg1 : !qcore.qubit_reg<2>
            } {
                qstruct.yield %qreg2 : !qcore.qubit_reg<2>
            }
            %qreg3 = qcore.pack_qubit_reg(%0, %1) -> !qcore.qubit_reg<2>
            %qreg4 = qcore.pack_qubit_reg(%2, %3) -> !qcore.qubit_reg<2>
            "test.op"(%qreg3, %qreg4) : (!qcore.qubit_reg<2>, !qcore.qubit_reg<2>) -> ()
            """,
        ),
    ],
)
def test_parallel_pattern(ir, expected, xdsl_context: Context):
    """Test that the ParallelPattern correctly flattens ParallelOp with qubit register results."""
    module_op = parse_ir(ir, xdsl_context)
    expected_op = parse_ir(expected, xdsl_context, verify=False)
    PatternRewriteWalker(
        _ParallelPattern(),
    ).rewrite_module(module_op)
    assert str(module_op) == str(expected_op)


@pytest.mark.parametrize(
    ("ir", "expected"),
    [
        (
            # Flattens operands
            """
            %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
            %qreg1 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit_reg<2> {
            ^bb(%arg0 : !qcore.qubit, %arg1 : !qcore.qubit):
                %qreg = qcore.pack_qubit_reg(%arg0, %arg1) -> !qcore.qubit_reg<2>
                qstruct.yield %qreg : !qcore.qubit_reg<2>
            }
            """,
            """
            %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
            %qreg1 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit_reg<2> {
            ^bb(%arg0: !qcore.qubit, %arg1: !qcore.qubit):
                %qreg = qcore.pack_qubit_reg(%arg0, %arg1) -> !qcore.qubit_reg<2>
                qstruct.yield %arg0, %arg1 : !qcore.qubit, !qcore.qubit
            }
            """,
        ),
        (
            # Flattens nothing
            """
            %qreg = qcore.alloc_qubit -> !qcore.qubit_reg<2>
            %qreg1 = qstruct.circuit(%qreg: !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
            ^bb(%arg0 : !qcore.qubit_reg<2>):
                qstruct.yield %arg0 : !qcore.qubit_reg<2>
            }
            """,
            """
            %qreg = qcore.alloc_qubit -> !qcore.qubit_reg<2>
            %qreg1 = qstruct.circuit(%qreg : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
            ^bb(%arg0: !qcore.qubit_reg<2>):
                qstruct.yield %arg0 : !qcore.qubit_reg<2>
            }
            """,
        ),
    ],
)
def test_yield_pattern(ir, expected, xdsl_context: Context):
    """Test that the YieldPattern correctly flattens YieldOp with qubit register operands."""
    module_op = parse_ir(ir, xdsl_context)
    expected_module_op = parse_ir(expected, xdsl_context, verify=False)
    PatternRewriteWalker(
        _YieldPattern(),
    ).rewrite_module(module_op)
    assert str(module_op) == str(expected_module_op)


@pytest.mark.parametrize(
    ("ir", "expected"),
    [
        (
            # Flattens operands and block arguments
            """
            %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
            %qreg0_pack = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
            %cond = "test.op"() : () -> i1
            %res = scf.while (%arg0 = %qreg0_pack) : (!qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
                scf.condition(%cond) %qreg0_pack : !qcore.qubit_reg<2>
            } do {
            ^bb(%arg1 : !qcore.qubit_reg<2>):
                scf.yield %arg1 : !qcore.qubit_reg<2>
            }
            """,
            """
            %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
            %qreg0_pack = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
            %cond = "test.op"() : () -> i1
            %res = scf.while (%arg0 = %qreg0_pack) : (!qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
                scf.condition(%cond) %q0, %q1 : !qcore.qubit, !qcore.qubit
            } do {
            ^bb(%0: !qcore.qubit, %1: !qcore.qubit):
                %arg1 = qcore.pack_qubit_reg(%0, %1) -> !qcore.qubit_reg<2>
                scf.yield %arg1 : !qcore.qubit_reg<2>
            }
            """,
        ),
        (
            # Flattens nothing
            """
            %qreg0_pack = qcore.alloc_qubit  -> !qcore.qubit_reg<2>
            %cond = "test.op"() : () -> i1
            %res = scf.while (%arg0 = %qreg0_pack) : (!qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
                scf.condition(%cond) %qreg0_pack : !qcore.qubit_reg<2>
            } do {
            ^bb(%arg1 : !qcore.qubit_reg<2>):
                scf.yield %arg1 : !qcore.qubit_reg<2>
            }
            """,
            """
            %qreg0_pack = qcore.alloc_qubit  -> !qcore.qubit_reg<2>
            %cond = "test.op"() : () -> i1
            %res = scf.while (%arg0 = %qreg0_pack) : (!qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
                scf.condition(%cond) %qreg0_pack : !qcore.qubit_reg<2>
            } do {
            ^bb(%arg1 : !qcore.qubit_reg<2>):
                scf.yield %arg1 : !qcore.qubit_reg<2>
            }
            """,
        ),
    ],
)
def test_condition_pattern(ir, expected, xdsl_context: Context):
    """Test that the ConditionPattern correctly flattens ConditionOp with qubit register
    arguments."""
    module_op = parse_ir(ir, xdsl_context)
    expected_module_op = parse_ir(expected, xdsl_context, verify=False)
    PatternRewriteWalker(
        _ConditionPattern(),
    ).rewrite_module(module_op)
    assert str(module_op) == str(expected_module_op)


@pytest.mark.parametrize(
    ("ir", "expected"),
    [
        (
            # Flattens operands, block arguments and results
            """
            %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
            %qreg0_pack = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
            %c0 = "test.op"() : () -> index
            %c1 = "test.op"() : () -> index
            %c2 = "test.op"() : () -> index
            %res = scf.for %i = %c0 to %c1 step %c2 iter_args(%arg0 = %qreg0_pack)
            -> (!qcore.qubit_reg<2>) {
                scf.yield %arg0 : !qcore.qubit_reg<2>
            }
            "test.op"(%res) : (!qcore.qubit_reg<2>) -> ()
            """,
            """
            %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
            %qreg0_pack = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
            %c0 = "test.op"() : () -> index
            %c1 = "test.op"() : () -> index
            %c2 = "test.op"() : () -> index
            %res, %res_1 = scf.for %i = %c0 to %c1 step %c2 iter_args(%0 = %q0, %1 = %q1)
            -> (!qcore.qubit, !qcore.qubit) {
                %arg0 = qcore.pack_qubit_reg(%0, %1) -> !qcore.qubit_reg<2>
                scf.yield %arg0 : !qcore.qubit_reg<2>
            }
            %res_2 = qcore.pack_qubit_reg(%res, %res_1) -> !qcore.qubit_reg<2>
            "test.op"(%res_2) : (!qcore.qubit_reg<2>) -> ()
            """,
        ),
        (
            # Flattens nothing - operands, block arguments and results are linked together
            """
            %qreg0_pack = qcore.alloc_qubit -> !qcore.qubit_reg<2>
            %c0 = "test.op"() : () -> index
            %c1 = "test.op"() : () -> index
            %c2 = "test.op"() : () -> index
            %res = scf.for %i = %c0 to %c1 step %c2 iter_args(%arg0 = %qreg0_pack)
            -> (!qcore.qubit_reg<2>) {
                scf.yield %arg0 : !qcore.qubit_reg<2>
            }
            "test.op"(%res) : (!qcore.qubit_reg<2>) -> ()
            """,
            """
            %qreg0_pack = qcore.alloc_qubit -> !qcore.qubit_reg<2>
            %c0 = "test.op"() : () -> index
            %c1 = "test.op"() : () -> index
            %c2 = "test.op"() : () -> index
            %res = scf.for %i = %c0 to %c1 step %c2 iter_args(%arg0 = %qreg0_pack)
            -> (!qcore.qubit_reg<2>) {
                scf.yield %arg0 : !qcore.qubit_reg<2>
            }
            "test.op"(%res) : (!qcore.qubit_reg<2>) -> ()
            """,
        ),
    ],
)
def test_for_pattern(ir, expected, xdsl_context: Context):
    """Test that the ForPattern correctly flattens ForOp with qubit register iter_args."""
    module_op = parse_ir(ir, xdsl_context)
    expected_module_op = parse_ir(expected, xdsl_context, verify=False)
    PatternRewriteWalker(
        _ForPattern(),
    ).rewrite_module(module_op)
    assert str(module_op) == str(expected_module_op)


@pytest.mark.parametrize(
    ("ir", "expected"),
    [
        (
            # Flattens operands, block arguments and results
            """
            %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
            %qreg0_pack = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
            %cond = "test.op"() : () -> i1
            %res = scf.while (%arg0 = %qreg0_pack) : (!qcore.qubit_reg<2>)
            -> !qcore.qubit_reg<2> {
                scf.condition(%cond) %arg0 : !qcore.qubit_reg<2>
            } do {
            ^bb(%arg1 : !qcore.qubit_reg<2>):
                scf.yield %arg1 : !qcore.qubit_reg<2>
            }
            """,
            """
            %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
            %qreg0_pack = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
            %cond = "test.op"() : () -> i1
            %res, %res_1 = scf.while (%0 = %q0, %1 = %q1) : (!qcore.qubit, !qcore.qubit)
            -> (!qcore.qubit, !qcore.qubit) {
                %arg0 = qcore.pack_qubit_reg(%0, %1) -> !qcore.qubit_reg<2>
                scf.condition(%cond) %arg0 : !qcore.qubit_reg<2>
            } do {
            ^bb(%arg1: !qcore.qubit_reg<2>):
                scf.yield %arg1 : !qcore.qubit_reg<2>
            }
            %res_2 = qcore.pack_qubit_reg(%res, %res_1) -> !qcore.qubit_reg<2>
            """,
        ),
        (
            # Flattens results only
            """
            %qreg0_pack = qcore.alloc_qubit -> !qcore.qubit_reg<2>
            %cond = "test.op"() : () -> i1
            %res = scf.while (%arg0 = %qreg0_pack) : (!qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
                scf.condition(%cond) %arg0 : !qcore.qubit_reg<2>
            } do {
            ^bb(%arg1 : !qcore.qubit_reg<2>):
                scf.yield %arg1 : !qcore.qubit_reg<2>
            }
            "test.op"(%res) : (!qcore.qubit_reg<2>) -> ()
            """,
            """
            %qreg0_pack = qcore.alloc_qubit -> !qcore.qubit_reg<2>
            %cond = "test.op"() : () -> i1
            %res, %res_1 = scf.while (%arg0 = %qreg0_pack) : (!qcore.qubit_reg<2>) -> (!qcore.qubit,
            !qcore.qubit) {
                scf.condition(%cond) %arg0 : !qcore.qubit_reg<2>
            } do {
            ^bb(%arg1: !qcore.qubit_reg<2>):
                scf.yield %arg1 : !qcore.qubit_reg<2>
            }
            %res_2 = qcore.pack_qubit_reg(%res, %res_1) -> !qcore.qubit_reg<2>
            "test.op"(%res_2) : (!qcore.qubit_reg<2>) -> ()
            """,
        ),
    ],
)
def test_while_pattern(ir, expected, xdsl_context: Context):
    """Test that the WhilePattern correctly flattens WhileOp with qubit register
    arguments/results."""
    module_op = parse_ir(ir, xdsl_context)
    expected_module_op = parse_ir(expected, xdsl_context, verify=False)
    PatternRewriteWalker(
        _WhilePattern(),
    ).rewrite_module(module_op)
    assert str(module_op) == str(expected_module_op)


@pytest.mark.parametrize(
    ("ir", "expected"),
    [
        (
            # Flattens results
            """
            %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
            %qreg = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
            %cond = "test.op"() : () -> i1
            %res = scf.if %cond -> (!qcore.qubit_reg<2>) {
                scf.yield %qreg : !qcore.qubit_reg<2>
            } else {
                scf.yield %qreg : !qcore.qubit_reg<2>
            }
            "test.op"(%res) : (!qcore.qubit_reg<2>) -> ()
            """,
            """
            %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
            %qreg = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
            %cond = "test.op"() : () -> i1
            %res, %res_1 = scf.if %cond -> (!qcore.qubit, !qcore.qubit) {
                scf.yield %qreg : !qcore.qubit_reg<2>
            } else {
                scf.yield %qreg : !qcore.qubit_reg<2>
            }
            %res_2 = qcore.pack_qubit_reg(%res, %res_1) -> !qcore.qubit_reg<2>
            "test.op"(%res_2) : (!qcore.qubit_reg<2>) -> ()
            """,
        ),
    ],
)
def test_if_pattern(ir, expected, xdsl_context: Context):
    """Test that the IfPattern correctly flattens IfOp with qubit register results."""
    module_op = parse_ir(ir, xdsl_context)
    expected_module_op = parse_ir(expected, xdsl_context, verify=False)
    PatternRewriteWalker(
        _IfPattern(),
    ).rewrite_module(module_op)
    assert str(module_op) == str(expected_module_op)


@pytest.mark.parametrize(
    ("ir", "expected"),
    [
        # Flattens results
        (
            """
            %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
            %qreg = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
            %idx = "test.op"() : () -> index
            %res = scf.index_switch %idx -> !qcore.qubit_reg<2>
            case 0 {
                scf.yield %qreg : !qcore.qubit_reg<2>
            }
            default {
                scf.yield %qreg : !qcore.qubit_reg<2>
            }
            "test.op"(%res) : (!qcore.qubit_reg<2>) -> ()
            """,
            """
            %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
            %qreg = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
            %idx = "test.op"() : () -> index
            %res, %res_1 = scf.index_switch %idx -> !qcore.qubit, !qcore.qubit
            case 0 {
                scf.yield %qreg : !qcore.qubit_reg<2>
            }
            default {
                scf.yield %qreg : !qcore.qubit_reg<2>
            }
            %res_2 = qcore.pack_qubit_reg(%res, %res_1) -> !qcore.qubit_reg<2>
            "test.op"(%res_2) : (!qcore.qubit_reg<2>) -> ()
            """,
        ),
    ],
)
def test_index_switch_pattern(ir, expected, xdsl_context: Context):
    """Test that the IndexSwitchPattern correctly flattens IndexSwitchOp with qubit register
    results."""
    module_op = parse_ir(ir, xdsl_context)
    expected_module_op = parse_ir(expected, xdsl_context, verify=False)
    PatternRewriteWalker(
        _IndexSwitchPattern(),
    ).rewrite_module(module_op)
    assert str(module_op) == str(expected_module_op)


class TestStimTagPreservation:
    """Tests that stim tags are copied or warned during flatten_qubit_registers pass."""

    def test_circuit_tag_copied(self):
        """A stim tag on a CircuitOp is copied to the new CircuitOp."""
        q0 = qcore.AllocQubitOp(qcore.QubitType()).result[0]
        qreg = qcore.AllocQubitOp(qcore.QubitRegType(1)).result[0]

        body = Block(arg_types=[qcore.QubitType(), qcore.QubitRegType(1)])
        q0_arg, qreg_arg = body.args
        assert isinstance(q0_arg.type, qcore.QubitType)
        assert isa(qreg_arg, SSAValue[qcore.QubitRegType])
        with ImplicitBuilder(body):
            unpacked = qcore.UnpackQubitRegOp(qreg_arg).results[0]
            qstruct.YieldOp(q0_arg, unpacked)

        circuit = qstruct.CircuitOp(
            arguments=[q0, qreg],
            result_types=[qcore.QubitType(), qcore.QubitType()],
            body=Region(body),
        )
        circuit.attributes[TAG_ATTR] = StringAttr("circuit_tag")
        module = ModuleOp([q0.owner, qreg.owner, circuit])

        PatternRewriteWalker(_CircuitPattern()).rewrite_module(module)

        new_circuits = [op for op in module.walk() if isinstance(op, qstruct.CircuitOp)]
        assert len(new_circuits) == 1
        assert new_circuits[0].attributes.get(TAG_ATTR) == StringAttr("circuit_tag")

    def test_concatenate_tag_warns(self):
        """A stim tag on a ConcatenateOp triggers a StimTagLostWarning."""
        qreg0 = qcore.AllocQubitOp(qcore.QubitRegType(1)).result[0]
        qreg1 = qcore.AllocQubitOp(qcore.QubitRegType(1)).result[0]
        assert isa(qreg0, SSAValue[qcore.QubitRegType])
        assert isa(qreg1, SSAValue[qcore.QubitRegType])
        concat_op = qcore.ConcatenateOp([qreg0, qreg1])
        concat_op.attributes[TAG_ATTR] = StringAttr("concat_tag")
        module = ModuleOp([qreg0.owner, qreg1.owner, concat_op])

        with pytest.warns(LostStimTagWarning, match="qcore.concatenate"):
            PatternRewriteWalker(_ConcatenatePattern()).rewrite_module(module)

    def test_split_tag_warns(self):
        """A stim tag on a SplitOp triggers a StimTagLostWarning."""
        qreg = qcore.AllocQubitOp(qcore.QubitRegType(2)).result[0]
        split_op = qcore.SplitOp(
            qreg,
            out_reg_types=[qcore.QubitRegType(1), qcore.QubitRegType(1)],
        )
        split_op.attributes[TAG_ATTR] = StringAttr("split_tag")
        module = ModuleOp([qreg.owner, split_op])

        with pytest.warns(LostStimTagWarning, match="qcore.split"):
            PatternRewriteWalker(_SplitPattern()).rewrite_module(module)

    def test_circuit_no_tag_no_warn(self):
        """No warning is emitted for a CircuitOp with no stim tag."""

        q0 = qcore.AllocQubitOp(qcore.QubitType()).result[0]
        qreg = qcore.AllocQubitOp(qcore.QubitRegType(1)).result[0]
        body = Block(arg_types=[qcore.QubitType(), qcore.QubitRegType(1)])
        q0_arg, qreg_arg = body.args
        with ImplicitBuilder(body):
            unpacked = qcore.UnpackQubitRegOp(qreg_arg).results[0]
            qstruct.YieldOp(q0_arg, unpacked)
        circuit = qstruct.CircuitOp(
            arguments=[q0, qreg],
            result_types=[qcore.QubitType(), qcore.QubitType()],
            body=Region(body),
        )
        module = ModuleOp([q0.owner, qreg.owner, circuit])

        with warnings.catch_warnings():
            warnings.simplefilter("error", LostStimTagWarning)
            PatternRewriteWalker(_CircuitPattern()).rewrite_module(module)
