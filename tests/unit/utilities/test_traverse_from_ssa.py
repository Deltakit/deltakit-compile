"""Tests for the CombineDetectorRoundsPass."""

import re
from typing import cast

import pytest
from xdsl.context import Context
from xdsl.dialects import test
from xdsl.dialects.builtin import IntegerAttr, i1
from xdsl.ir import Block, BlockArgument, ErasedSSAValue, Operation, OpResult, SSAValue

from deltakit_compile.dialects import arith, qcore, qec, qref, qstruct, scf
from deltakit_compile.dialects.qcore import QubitRegType, QubitType
from deltakit_compile.utilities.traverse_from_ssa import (
    TrackedQubit,
    find_all_predecessor_and_successor_ssas,
    find_backward_ssas,
    find_equivalent_qubit_ssas,
    find_forward_ssas,
    get_qubit_id,
)
from tests.unit.conftest import parse_ir

# region: Test IR Builders


build_repeat_circuit1 = """
    builtin.module {
      %0, %1, %2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
      %3, %4, %5 = qstruct.circuit(%0, %1, %2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) ->
      !qcore.qubit, !qcore.qubit, !qcore.qubit {
      ^bb0(%6: !qcore.qubit, %7: !qcore.qubit, %8: !qcore.qubit):
        %9 = qref.measure<Z> (%6) -> i1
        %10 = qref.measure<Z> (%7) -> i1
        %11 = qec.detector(%9, %10)
        %12, %13, %14 = qstruct.repeat<5> (%9, %10, %11 : i1, i1, !qec.detector_ref) -> i1, i1,
        !qec.detector_ref {
        ^bb1(%15: i1, %16: i1, %17: !qec.detector_ref):
          %18 = qref.measure<Z> (%6) -> i1
          %19 = qref.measure<Z> (%7) -> i1
          %20 = qec.detector(%16, %18)
          %21 = qec.detector(%19, %15)
          qec.detector_round(%20, %17)
          qstruct.yield %18, %19, %21 : i1, i1, !qec.detector_ref
        }
        %22, %23 = qref.measure<Z> (%6, %7) -> i1, i1
        %24 = qec.detector(%12, %22)
        %25 = qec.detector(%13, %23)
        qec.detector_round(%24, %25, %14)
        qstruct.yield %6, %7, %8 : !qcore.qubit, !qcore.qubit, !qcore.qubit
      }
    }
    """


build_repeat_circuit2 = """
    builtin.module {
      %0, %1, %2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
      %3, %4, %5 = qstruct.circuit(%0, %1, %2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) ->
      !qcore.qubit, !qcore.qubit, !qcore.qubit {
      ^bb0(%6: !qcore.qubit, %7: !qcore.qubit, %8: !qcore.qubit):
        %9 = qref.measure<Z> (%6) -> i1
        %10 = qref.measure<Z> (%7) -> i1
        %11 = qec.detector(%9, %10)
        %12, %13, %14 = qstruct.repeat<5> (%9, %10, %11 : i1, i1, !qec.detector_ref) -> i1, i1,
        !qec.detector_ref {
        ^bb1(%15: i1, %16: i1, %17: !qec.detector_ref):
          %18 = qref.measure<Z> (%6) -> i1
          %19 = qref.measure<Z> (%7) -> i1
          %20 = qec.detector(%15, %18)
          %21 = qec.detector(%19, %16)
          qec.detector_round(%20, %17)
          qstruct.yield %18, %19, %21 : i1, i1, !qec.detector_ref
        }
        %22, %23 = qref.measure<Z> (%6, %7) -> i1, i1
        %24 = qec.detector(%12, %22)
        %25 = qec.detector(%13, %23)
        qec.detector_round(%24, %25, %14)
        qstruct.yield %6, %7, %8 : !qcore.qubit, !qcore.qubit, !qcore.qubit
      }
    }
    """


build_for_circuit = """
    builtin.module {
      %0, %1, %2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
      %3, %4, %5, %6, %7, %8 = qstruct.circuit(%0, %1, %2 : !qcore.qubit, !qcore.qubit,
      !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1, !qec.detector_ref {
      ^bb0(%9: !qcore.qubit, %10: !qcore.qubit, %11: !qcore.qubit):
        %12 = qref.measure<Z> (%9) -> i1
        %13 = qref.measure<Z> (%10) -> i1
        %14 = qec.detector(%12, %13)
        qstruct.yield %9, %10, %11, %12, %13, %14 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1,
        i1, !qec.detector_ref
      }
      %9 = arith.constant 0 : i32
      %10 = arith.constant 5 : i32
      %11 = arith.constant 1 : i32
      %12, %13, %14, %15, %16, %17 = scf.for %18 = %9 to %10 step %11 iter_args(%19 = %3, %20 = %4,
      %21 = %5, %22 = %6, %23 = %7, %24 = %8) -> (!qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1,
      !qec.detector_ref)  : i32 {
        %25, %26, %27, %28, %29 = qstruct.circuit(%19, %20, %21 : !qcore.qubit, !qcore.qubit,
        !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1 {
        ^bb0(%30: !qcore.qubit, %31: !qcore.qubit, %32: !qcore.qubit):
          %33 = qref.measure<Z> (%30) -> i1
          %34 = qref.measure<Z> (%31) -> i1
          qstruct.yield %30, %31, %32, %33, %34 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1
        }
        %30 = qstruct.circuit(%23, %28, %29, %22, %24 : i1, i1, i1, i1, !qec.detector_ref) ->
        !qec.detector_ref {
        ^bb0(%31: i1, %32: i1, %33: i1, %34: i1, %35: !qec.detector_ref):
          %36 = qec.detector(%31, %32)
          %37 = qec.detector(%33, %32)
          qec.detector_round(%36, %35)
          qstruct.yield %37 : !qec.detector_ref
        }
        scf.yield %25, %26, %27, %28, %29, %30 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1,
        !qec.detector_ref
      }
      qstruct.circuit(%16, %15 : i1, i1) -> {
      ^bb0(%31: i1, %32: i1):
        %33 = qec.detector(%31, %32)
        qstruct.yield
      }
    }
    """


build_if_circuit = """
    builtin.module {
      %0, %1, %2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
      %3 = arith.constant true
      %4, %5, %6, %7, %8 = scf.if %3 -> (!qcore.qubit, !qcore.qubit, !qcore.qubit, i1,
      !qec.detector_ref) {
        %9, %10, %11, %12, %13 = qstruct.circuit(%0, %1, %2 : !qcore.qubit, !qcore.qubit,
        !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, !qec.detector_ref {
        ^bb0(%14: !qcore.qubit, %15: !qcore.qubit, %16: !qcore.qubit):
          %17 = qref.measure<Z> (%14) -> i1
          %18 = qref.measure<Z> (%15) -> i1
          %19 = qec.detector(%17, %18)
          qstruct.yield %14, %15, %16, %18, %19 : !qcore.qubit, !qcore.qubit, !qcore.qubit,
          i1, !qec.detector_ref
        }
        scf.yield %9, %10, %11, %12, %13 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1,
        !qec.detector_ref }
        else {
        %14, %15, %16, %17, %18 = qstruct.circuit(%0, %1, %2 : !qcore.qubit, !qcore.qubit,
        !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, !qec.detector_ref {
        ^bb0(%19: !qcore.qubit, %20: !qcore.qubit, %21: !qcore.qubit):
          %22 = qref.measure<Z> (%19) -> i1
          %23 = qref.measure<Z> (%21) -> i1
          %24 = qec.detector(%22, %23)
          qstruct.yield %19, %20, %21, %22, %24 : !qcore.qubit, !qcore.qubit, !qcore.qubit,
          i1, !qec.detector_ref
        }
        scf.yield %14, %15, %16, %17, %18 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1,
        !qec.detector_ref
      }
      qstruct.circuit(%7, %8 : i1, !qec.detector_ref) -> {
      ^bb0(%19: i1, %20: !qec.detector_ref):
        %21 = qec.detector(%19)
        qec.detector_round(%20, %21)
        qstruct.yield
      }
    }
    """


build_while_circuit = """
    builtin.module {
      %0, %1, %2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
      %3, %4, %5, %6, %7 = qstruct.circuit(%0, %1, %2 : !qcore.qubit, !qcore.qubit, !qcore.qubit)
      -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1 {
      ^bb0(%8: !qcore.qubit, %9: !qcore.qubit, %10: !qcore.qubit):
        %11 = qref.measure<Z> (%8) -> i1
        %12 = qref.measure<Z> (%9) -> i1
        qstruct.yield %8, %9, %10, %11, %12 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1
      }
      %8, %9, %10, %11, %12, %13 = scf.while (%14 = %3, %15 = %4, %16 = %5, %17 = %6, %18 = %7) :
      (!qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1) -> (!qcore.qubit, !qcore.qubit,
      !qcore.qubit, i1, i1, !qec.detector_ref) {
        %19 = qstruct.circuit(%6, %7 : i1, i1) -> !qec.detector_ref {
        ^bb0(%20: i1, %21: i1):
          %22 = qec.detector(%20, %21)
          qstruct.yield %22 : !qec.detector_ref
        }
        %20 = arith.constant true
        scf.condition(%20) %14, %15, %16, %17, %18, %19 : !qcore.qubit, !qcore.qubit,
        !qcore.qubit, i1, i1, !qec.detector_ref
      } do {
      ^bb0(%21: !qcore.qubit, %22: !qcore.qubit, %23: !qcore.qubit, %24: i1, %25: i1, %26:
      !qec.detector_ref):
        %27, %28, %29, %30, %31, %32 = qstruct.circuit(%21, %22, %23, %24, %25, %26 : !qcore.qubit,
        !qcore.qubit, !qcore.qubit, i1, i1, !qec.detector_ref) -> !qcore.qubit, !qcore.qubit,
        !qcore.qubit, i1, i1, !qec.detector_ref {
        ^bb1(%33: !qcore.qubit, %34: !qcore.qubit, %35: !qcore.qubit, %36: i1, %37: i1, %38:
        !qec.detector_ref):
          %39 = qref.measure<Z> (%33) -> i1
          %40 = qref.measure<Z> (%34) -> i1
          %41 = qec.detector(%37, %40)
          %42 = qec.detector(%39, %36)
          qec.detector_round(%41, %38)
          %43 = qec.detector(%36, %37)
          qstruct.yield %33, %34, %35, %39, %40, %42 : !qcore.qubit, !qcore.qubit, !qcore.qubit,
          i1, i1, !qec.detector_ref
        }
        scf.yield %27, %28, %29, %30, %31 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1
      }
      qstruct.circuit(%11, %12: i1, i1) -> !qec.detector_ref {
      ^bb0(%100: i1, %101: i1):
        %102 = qec.detector(%100, %101)
        qstruct.yield %102 : !qec.detector_ref
      }
    }
    """


build_parallel_circuit = """
        builtin.module {
            %0, %1, %2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
            %3, %4, %5, %6, %7 = qstruct.circuit(%0, %1, %2 : !qcore.qubit, !qcore.qubit,
            !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qec.detector_ref,
            !qec.detector_ref {
            ^bb0(%8: !qcore.qubit, %9: !qcore.qubit, %10: !qcore.qubit):
                %11, %12, %13 = qstruct.parallel<TOP> -> i1, i1, i1 {
                ^bb1(%14: !qcore.qubit):
                    %15 = qref.measure<Z> (%8) -> i1
                    %16 = qref.measure<Z> (%9) -> i1
                    qstruct.yield %15, %16 : i1, i1
                } {
                    %17 = qref.measure<Z> (%10) -> i1
                    qstruct.yield %17 : i1
                }
                %18 = qec.detector(%11, %12)
                %19 = qec.detector(%12, %13)
                qstruct.yield %8, %9, %10, %18, %19 : !qcore.qubit, !qcore.qubit, !qcore.qubit,
                !qec.detector_ref, !qec.detector_ref
            }
        }
        """


build_measurement_passed_in_and_yielded_out = """
    builtin.module {
      %0, %1, %2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
      %3, %4, %5 = qstruct.circuit(%0, %1, %2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) ->
      !qcore.qubit, !qcore.qubit, !qcore.qubit {
      ^bb0(%6: !qcore.qubit, %7: !qcore.qubit, %8: !qcore.qubit):
        %9 = qref.measure<Z> (%6) -> i1
        %10 = qref.measure<Z> (%7) -> i1
        %11, %12 = qstruct.repeat<5> (%9, %10 : i1, i1) -> i1, i1 {
        ^bb1(%13: i1, %14: i1):
          %15 = qref.measure<Z> (%6) -> i1
          %16 = qec.detector(%13, %15)
          qstruct.yield %13, %15 : i1, i1
        }
        qstruct.yield %6, %7, %8 : !qcore.qubit, !qcore.qubit, !qcore.qubit
      }
    }
    """


build_error_result_circuit = """
    builtin.module {
      %0, %1, %2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
      %3, %4 = "test.op"(%0, %1) : (!qcore.qubit, !qcore.qubit) -> (i1, i1)
      %5 = qec.detector(%3, %4)
    }
    """


build_error_block_argument_circuit = """
        builtin.module {
            %0, %1, %2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
            %3, %4 = "test.op"(%0, %1) : (!qcore.qubit, !qcore.qubit) -> (i1, i1)
            "test.op"(%3) ({
            ^bb0(%5: i1):
                %6 = qec.detector(%5)
            }) : (i1) -> ()
        }
        """


build_error_repeat_circuit = """
    builtin.module {
      %0, %1, %2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
      %3, %4 = "test.op"(%0, %1) : (!qcore.qubit, !qcore.qubit) -> (i1, i1)
      %5, %6 = qstruct.repeat<5> (%3, %4 : i1, i1) -> i1, i1 {
      ^bb0(%7: i1, %8: i1):
        %9 = qref.measure<Z> (%0) -> i1
        qstruct.yield %8, %9 : i1, i1
      }
      %10 = qec.detector(%5, %6)
    }
    """


# endregion: Test IR Builders

# region: Test Functions - Different Usage Patterns


@pytest.mark.parametrize(
    ("module_str", "expected_indices"),
    [
        (
            build_repeat_circuit1,
            (
                [0, 1],
                [1, 3, 2],
                [3, 0, 2],
                [4, 2],
                [4, 3],
            ),
        ),
        (
            build_repeat_circuit2,
            (
                [0, 1],
                [0, 2],
                [1, 3],
                [4, 2],
                [4, 3],
            ),
        ),
        (
            build_for_circuit,
            ([0, 1], [1, 2, 3], [2, 3], [0, 1, 2, 3]),
        ),
        (
            build_if_circuit,
            (
                [0, 1],
                [2, 3],
                [1, 2],
            ),
        ),
        (
            build_while_circuit,
            ([0, 1], [1, 3], [0, 2], [0, 1, 2, 3], [0, 1, 2, 3]),
        ),
        (
            build_parallel_circuit,
            (
                [0, 1],
                [1, 2],
            ),
        ),
        (
            build_measurement_passed_in_and_yielded_out,
            ([0, 2],),
        ),
    ],
)
def test_get_measurement_ops_of_detector(
    module_str: str, expected_indices: tuple[list[int], ...], xdsl_context: Context
):
    """Test that the detector pattern can traverse through IR structure to find measurement ops."""
    module_op = parse_ir(module_str, xdsl_context, verify=True)
    measurements_ops = [op.results[0] for op in module_op.walk() if isinstance(op, qref.MeasureOp)]

    i = 0
    # Collect actual measurement ops found, organised by detector
    for op in module_op.walk():
        if isinstance(op, qec.DetectorOp):
            detector_indices = set()
            for measurement_ssa in op.measurements:
                measurement_ops = [ssa.owner for ssa in find_backward_ssas(measurement_ssa, set())]
                assert measurement_ops is not None
                for measurement_op in measurement_ops:
                    detector_indices.update(
                        [i for i, m in enumerate(measurements_ops) if measurement_op == m.owner]
                    )
            assert set(expected_indices[i]) == detector_indices, (
                f"Expected measurement indices {expected_indices[i]} for detector {i}, but found "
                f"{tuple(detector_indices)}"
            )
            i += 1


def test_unsupported_operation_result_in_pattern(xdsl_context: Context):
    """Test that the pattern raises NotImplementedError when encountering unsupported operations."""
    module = parse_ir(build_error_result_circuit, xdsl_context, verify=False)

    for op in module.walk():
        if isinstance(op, qec.DetectorOp):
            ops = [ssa.owner for ssa in find_backward_ssas(op.measurements[0], set())]
            assert len(ops) == 1
            assert isinstance(ops[0], test.TestOp)


def test_unsupported_operation_block_arg_in_pattern(xdsl_context: Context):
    """Test that the pattern raises NotImplementedError when encountering unsupported operations."""
    module = parse_ir(build_error_block_argument_circuit, xdsl_context, verify=False)

    for op in module.walk():
        if isinstance(op, qec.DetectorOp):
            ops = [ssa.owner for ssa in find_backward_ssas(op.measurements[0], set())]
            assert len(ops) == 1
            assert isinstance(ops[0], Block)


def test_unsupported_operation_through_repeat(xdsl_context: Context):
    """Test that the pattern raises NotImplementedError when encountering unsupported operations."""
    module = parse_ir(build_error_repeat_circuit, xdsl_context, verify=False)

    for op in module.walk():
        if isinstance(op, qec.DetectorOp):
            ops = [ssa.owner for ssa in find_backward_ssas(op.measurements[0], set())]
            assert len(ops) == 2
            assert isinstance(ops[0], qref.MeasureOp)
            assert isinstance(ops[1], test.TestOp)


def test_traverse_from_ssa_non_block_arg_or_op_result_throws():
    """Test that traverse_from_ssa raises TypeError when given an SSA value that is neither a
    BlockArgument nor an OpResult."""

    erased_value = ErasedSSAValue(i1, arith.ConstantOp(IntegerAttr(1, 1)).result)
    with pytest.raises(TypeError, match="Expected SSAValue to be either BlockArgument or OpResult"):
        find_backward_ssas(erased_value)


# endregion: Test Functions - Different Usage Patterns


def test_get_qubit_id_block_arg():
    with pytest.raises(
        TypeError, match=r"Expected OpResult, got <class 'xdsl.ir.core.BlockArgument'>"
    ):
        get_qubit_id(BlockArgument(i1, Block(), 0))


def test_get_qubit_id_op_non_alloc_qubit_alloc():
    with pytest.raises(
        TypeError, match=r"Expected QubitAllocOp, got <class 'xdsl.dialects.test.TestOp'>"
    ):
        get_qubit_id(test.TestOp([], [qcore.QubitType()]).results[0])


# region: Tests for find_forward_ssas

build_linear_circuit = """
    builtin.module {
      %0, %1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
      %2, %3 = qstruct.circuit(%0, %1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
      ^bb0(%4: !qcore.qubit, %5: !qcore.qubit):
        qstruct.yield %4, %5 : !qcore.qubit, !qcore.qubit
      }
    }
    """

build_circuit_containing_repeat = """
    builtin.module {
      %0 = qcore.alloc_qubit -> !qcore.qubit
      %1 = qstruct.circuit(%0 : !qcore.qubit) -> !qcore.qubit {
      ^bb0(%2: !qcore.qubit):
        %3 = qstruct.repeat<3> (%2 : !qcore.qubit) -> !qcore.qubit {
        ^bb1(%4: !qcore.qubit):
          qstruct.yield %4 : !qcore.qubit
        }
        qstruct.yield %3 : !qcore.qubit
      }
      %5 = qstruct.circuit(%1 : !qcore.qubit) -> !qcore.qubit {
        ^bb0(%6: !qcore.qubit):
        %7 = qref.measure<Z>(%6) -> i1
        qstruct.yield %6 : !qcore.qubit
      }
    }
    """


def test_find_forward_ssas_circuit_arg_to_result(xdsl_context: Context):
    """Test that circuit arg is forwarded to the circuit result through block arg and yield."""
    module = parse_ir(build_linear_circuit, xdsl_context, verify=True)

    alloc_ops = [op for op in module.walk() if isinstance(op, qcore.AllocQubitOp)]
    circuit_ops = [op for op in module.walk() if isinstance(op, qstruct.CircuitOp)]
    assert alloc_ops
    assert circuit_ops

    qubit_ssa = alloc_ops[0].results[0]
    circuit_result = circuit_ops[0].res[0]

    forward_ssas, terminal_uses = find_forward_ssas(qubit_ssa)

    assert circuit_result in forward_ssas
    assert not terminal_uses, "All operations using '%0' are structural."


def test_find_forward_ssas_terminal_has_no_structural_uses(xdsl_context: Context):
    """Test that a terminal SSA value with no structural uses returns itself."""
    module = parse_ir(build_linear_circuit, xdsl_context, verify=True)

    circuit_ops = [op for op in module.walk() if isinstance(op, qstruct.CircuitOp)]
    circuit_result = circuit_ops[0].res[0]

    forward_ssas, terminal_uses = find_forward_ssas(circuit_result)
    assert forward_ssas == {circuit_result}
    assert not terminal_uses, "No operation using '%2'."


def test_find_forward_ssas_circuit_containing_repeat(xdsl_context: Context):
    """Test forward traversal through a circuit containing a repeat."""
    module = parse_ir(build_circuit_containing_repeat, xdsl_context, verify=True)

    alloc_ops = [op for op in module.walk() if isinstance(op, qcore.AllocQubitOp)]
    circuit_ops = [op for op in module.walk() if isinstance(op, qstruct.CircuitOp)]
    measure_ops = [op for op in module.walk() if isinstance(op, qref.MeasureOp)]

    non_terminal_result = circuit_ops[0].res[0]
    terminal_result = circuit_ops[1].res[0]

    forward_ssas, terminal_uses = find_forward_ssas(alloc_ops[0].results[0])
    assert non_terminal_result not in forward_ssas
    assert terminal_result in forward_ssas
    assert len(terminal_uses) == 1
    tuse = next(iter(terminal_uses))
    assert tuse.operation == measure_ops[0]


@pytest.mark.parametrize(
    "module_str",
    [
        build_repeat_circuit1,
        build_repeat_circuit2,
        build_for_circuit,
        build_if_circuit,
        build_while_circuit,
        build_parallel_circuit,
        build_measurement_passed_in_and_yielded_out,
        build_linear_circuit,
        build_circuit_containing_repeat,
    ],
)
def test_find_forward_ssas_round_trip(module_str: str, xdsl_context: Context):
    """Round-trip property (forward direction): for every backward-leaf SSA ``a`` (i.e.
    ``find_backward_ssas(a) == {a}``) and every ``b`` in ``find_forward_ssas(a)``, ``a`` must
    be in ``find_backward_ssas(b)``.

    Backward leaves are SSA values where backward traversal stops, either because they are produced
    by a non-structural op or are block args of a non-structural parent. For such leaves, the
    forward and backward traversals are consistent duals.
    """
    module = parse_ir(module_str, xdsl_context, verify=False)

    all_ssas: list = []
    for op in module.walk():
        all_ssas.extend(op.results)
    for block in module.walk_blocks():
        all_ssas.extend(block.args)

    for ssa in all_ssas:
        backward_origins = find_backward_ssas(ssa)
        # Only check SSAs that are backward leaves (traversal stops at themselves)
        if backward_origins != {ssa}:
            continue
        forward_terminals, _ = find_forward_ssas(ssa)
        for terminal in forward_terminals:
            origins = find_backward_ssas(terminal)
            assert ssa in origins, (
                f"Round-trip failed: {ssa} -> forward -> {terminal}, "
                f"but {ssa} not in find_backward_ssas({terminal}) = {origins}"
            )


# endregion: Tests for find_forward_ssas

# region Bidirectional traversal


def test_bidirectional_traversal_circuit_and_repeat(xdsl_context: Context) -> None:
    module = parse_ir(build_circuit_containing_repeat, xdsl_context, verify=False)
    qubit_alloc_ops = [op for op in module.walk() if isinstance(op, qcore.AllocQubitOp)]
    assert len(qubit_alloc_ops) == 1
    qubit_alloc_op = qubit_alloc_ops[0]
    qubit = qubit_alloc_op.results[0]
    assert isinstance(qubit.type, QubitType)

    equivalent_ssas, blocking_uses, blocking_ops = find_all_predecessor_and_successor_ssas(qubit)
    assert len(equivalent_ssas) == 7
    assert len(blocking_uses) == 1
    assert isinstance(blocking_uses.pop().operation, qref.MeasureOp)
    assert not blocking_ops


def test_bidirectional_traversal_linear_circuit(xdsl_context: Context) -> None:
    module = parse_ir(build_linear_circuit, xdsl_context, verify=False)
    qubit_alloc_ops = [op for op in module.walk() if isinstance(op, qcore.AllocQubitOp)]
    assert len(qubit_alloc_ops) == 1
    qubit_alloc_op = qubit_alloc_ops[0]
    for qubit_ssa in qubit_alloc_op.results:
        assert isinstance(qubit_ssa.type, QubitType)

        equivalent_ssas, blocking_uses, blocking_ops = find_all_predecessor_and_successor_ssas(
            qubit_ssa
        )
        assert len(equivalent_ssas) == 3
        assert not blocking_uses
        assert not blocking_ops


# region Qubit index tracking


@pytest.mark.parametrize(
    ("ssa_creation_op", "index", "expected_error"),
    [
        (test.TestOp(result_types=[QubitType()]), None, None),
        (test.TestOp(result_types=[QubitRegType(10)]), 0, None),
        (test.TestOp(result_types=[QubitRegType(10)]), 9, None),
        (
            test.TestOp(result_types=[QubitType()]),
            1,
            TypeError("A scalar qubit cannot have a register index."),
        ),
        (
            test.TestOp(result_types=[QubitRegType(1)]),
            None,
            TypeError("A qubit register requires a register index."),
        ),
        (
            test.TestOp(result_types=[QubitRegType(10)]),
            10,
            IndexError("Register index 10 is out of bounds for !qcore.qubit_reg<10>."),
        ),
        (
            test.TestOp(result_types=[QubitRegType(10)]),
            23,
            IndexError("Register index 23 is out of bounds for !qcore.qubit_reg<10>."),
        ),
        (
            test.TestOp(result_types=[i1]),
            None,
            TypeError("Expected a qubit or qubit register SSA value, got i1."),
        ),
    ],
)
def test_tracked_qubit_creation(
    ssa_creation_op: Operation, index: int | None, expected_error: Exception | None
) -> None:
    if expected_error is not None:
        with pytest.raises(type(expected_error), match=re.escape(expected_error.args[0])):
            TrackedQubit(ssa_creation_op.results[0], index)
    else:
        tqubit = TrackedQubit(ssa_creation_op.results[0], index)
        assert tqubit.index == index
        assert tqubit.ssa == ssa_creation_op.results[0]


def test_tracked_qubit_register_index() -> None:
    qubit_ssa = test.TestOp(result_types=[QubitType()]).results[0]
    qreg_ssa = test.TestOp(result_types=[QubitRegType(10)]).results[0]
    assert TrackedQubit(qreg_ssa, 1).register_index == 1
    with pytest.raises(TypeError, match=re.escape("Expected a tracked qubit in a register.")):
        _ = TrackedQubit(qubit_ssa).register_index


def test_strict_traversal_tracks_pack_and_unpack(xdsl_context: Context) -> None:
    module = parse_ir(
        """
        builtin.module {
          %0, %1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
          %2 = qcore.pack_qubit_reg(%0, %1) -> !qcore.qubit_reg<2>
          %3, %4 = qcore.unpack_qubit_reg(%2 : !qcore.qubit_reg<2>)
        }
        """,
        xdsl_context,
        verify=True,
    )
    alloc = next(op for op in module.walk() if isinstance(op, qcore.AllocQubitOp))
    pack = next(op for op in module.walk() if isinstance(op, qcore.PackQubitRegOp))
    unpack = next(op for op in module.walk() if isinstance(op, qcore.UnpackQubitRegOp))

    equivalent, blocking_uses, blocking_ops = find_equivalent_qubit_ssas(pack.reg, 1)

    assert equivalent == {
        TrackedQubit(pack.reg, 1),
        TrackedQubit(alloc.results[1]),
        TrackedQubit(unpack.results[1]),
    }
    assert not blocking_uses
    assert not blocking_ops

    # Check that calling the function again on one of the equivalent values returns the same thing.
    equivalent2, blocking_uses2, blocking_ops2 = find_equivalent_qubit_ssas(
        cast(OpResult[QubitType], alloc.results[1])
    )
    assert equivalent == equivalent2
    assert blocking_uses == blocking_uses2
    assert blocking_ops == blocking_ops2


def test_strict_traversal_preserves_concatenate_and_split_offsets(xdsl_context: Context) -> None:
    module = parse_ir(
        """
        builtin.module {
          %0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
          %1 = qcore.alloc_qubit -> !qcore.qubit_reg<3>
          %2 = qcore.concatenate(%0, %1 : !qcore.qubit_reg<2>, !qcore.qubit_reg<3>)
            -> !qcore.qubit_reg<5>
          %3, %4 = qcore.split(%2 : !qcore.qubit_reg<5>)
            -> !qcore.qubit_reg<1>, !qcore.qubit_reg<4>
        }
        """,
        xdsl_context,
        verify=True,
    )
    regs = [op for op in module.walk() if isinstance(op, qcore.AllocQubitOp)]
    concat = next(op for op in module.walk() if isinstance(op, qcore.ConcatenateOp))
    split = next(op for op in module.walk() if isinstance(op, qcore.SplitOp))

    equivalent, blocking_uses, blocking_ops = find_equivalent_qubit_ssas(
        cast(OpResult[QubitRegType], regs[1].results[0]), 1
    )

    assert TrackedQubit(concat.out_reg, 3) in equivalent
    assert TrackedQubit(split.out_regs[1], 2) in equivalent
    assert not blocking_uses
    assert not blocking_ops

    # Check that calling the function again on one of the equivalent values returns the same thing.
    equivalent2, blocking_uses2, blocking_ops2 = find_equivalent_qubit_ssas(concat.out_reg, 3)
    assert equivalent == equivalent2
    assert blocking_uses == blocking_uses2
    assert blocking_ops == blocking_ops2


def test_strict_traversal_tracks_circuit(xdsl_context: Context) -> None:
    module = parse_ir(build_linear_circuit, xdsl_context, verify=True)
    alloc = next(op for op in module.walk() if isinstance(op, qcore.AllocQubitOp))
    circuit = next(op for op in module.walk() if isinstance(op, qstruct.CircuitOp))

    equivalent, blocking_uses, blocking_ops = find_equivalent_qubit_ssas(
        cast(OpResult[QubitType], alloc.results[0])
    )

    assert equivalent == {
        TrackedQubit(alloc.results[0]),
        TrackedQubit(circuit.body.block.args[0]),
        TrackedQubit(circuit.results[0]),
    }
    assert not blocking_uses
    assert not blocking_ops

    # Check that calling the function again on one of the equivalent values returns the same thing.
    equivalent2, blocking_uses2, blocking_ops2 = find_equivalent_qubit_ssas(
        cast(OpResult[QubitType], circuit.results[0])
    )
    assert equivalent == equivalent2
    assert blocking_uses == blocking_uses2
    assert blocking_ops == blocking_ops2


def test_strict_traversal_tracks_parallel(xdsl_context: Context) -> None:
    module = parse_ir(
        """
        builtin.module {
          %0, %1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
          %2, %3 = qstruct.parallel<TOP> -> !qcore.qubit, !qcore.qubit {
            qstruct.yield %0 : !qcore.qubit
          } {
            qstruct.yield %1 : !qcore.qubit
          }
        }
        """,
        xdsl_context,
        verify=True,
    )
    alloc = next(op for op in module.walk() if isinstance(op, qcore.AllocQubitOp))
    parallel = next(op for op in module.walk() if isinstance(op, qstruct.ParallelOp))

    equivalent, blocking_uses, blocking_ops = find_equivalent_qubit_ssas(
        cast(OpResult[QubitType], alloc.results[0])
    )

    assert equivalent == {
        TrackedQubit(alloc.results[0]),
        TrackedQubit(parallel.results[0]),
    }
    assert not blocking_uses
    assert not blocking_ops


def test_strict_traversal_blocks_on_repeat(xdsl_context: Context) -> None:
    module = parse_ir(
        """
        builtin.module {
          %0, %1, %2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
          %3, %4, %5 = qstruct.repeat<100> (%0, %1, %2 : !qcore.qubit, !qcore.qubit, !qcore.qubit)
              -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
            ^bb0(%6: !qcore.qubit, %7: !qcore.qubit, %8: !qcore.qubit):
              qstruct.yield %7, %8, %6 : !qcore.qubit, !qcore.qubit, !qcore.qubit
          }
        }
        """,
        xdsl_context,
        verify=True,
    )
    alloc = next(op for op in module.walk() if isinstance(op, qcore.AllocQubitOp))
    repeat = next(op for op in module.walk() if isinstance(op, qstruct.RepeatOp))

    _, blocking_uses, _ = find_equivalent_qubit_ssas(cast(OpResult[QubitType], alloc.results[0]))
    assert any(use.operation is repeat for use in blocking_uses)
    _, _, blocking_ops = find_equivalent_qubit_ssas(cast(OpResult[QubitType], repeat.results[0]))
    assert repeat in blocking_ops


def test_strict_traversal_tracks_identity_repeat(xdsl_context: Context) -> None:
    module = parse_ir(
        """
        builtin.module {
          %0 = qcore.alloc_qubit -> !qcore.qubit
          %1 = qstruct.repeat<100> (%0 : !qcore.qubit) -> !qcore.qubit {
            ^bb0(%2: !qcore.qubit):
              qstruct.yield %2 : !qcore.qubit
          }
        }
        """,
        xdsl_context,
        verify=True,
    )
    alloc = next(op for op in module.walk() if isinstance(op, qcore.AllocQubitOp))
    repeat = next(op for op in module.walk() if isinstance(op, qstruct.RepeatOp))

    equivalent, blocking_uses, blocking_ops = find_equivalent_qubit_ssas(
        cast(OpResult[QubitType], alloc.results[0])
    )

    assert equivalent == {
        TrackedQubit(alloc.results[0]),
        TrackedQubit(repeat.body.block.args[0]),
        TrackedQubit(repeat.results[0]),
    }
    assert not blocking_uses
    assert not blocking_ops


def test_equivalent_traversal_blocks_on_unsupported_operation_result() -> None:
    operation = test.TestOp(result_types=[QubitType()])
    _, _, blocking_ops = find_equivalent_qubit_ssas(cast(SSAValue[QubitType], operation.results[0]))
    assert blocking_ops == {operation}


def test_equivalent_traversal_blocks_on_unsupported_operation_block_arg() -> None:
    operation = test.TestOp(regions=[[Block(arg_types=[QubitType()])]])
    block_argument = operation.regions[0].blocks[0].args[0]

    _, _, blocking_ops = find_equivalent_qubit_ssas(cast(SSAValue[QubitType], block_argument))

    assert blocking_ops == {operation}


def test_strict_traversal_tracks_repeat_with_multiple_iter_args_through_circuit(
    xdsl_context: Context,
) -> None:
    module = parse_ir(
        """
        builtin.module {
          %0, %1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
          %2, %3 = qstruct.repeat<3> (%0, %1 : !qcore.qubit, !qcore.qubit)
              -> !qcore.qubit, !qcore.qubit {
            ^bb0(%4: !qcore.qubit, %5: !qcore.qubit):
              %6, %7 = qstruct.circuit(%4, %5 : !qcore.qubit, !qcore.qubit)
                  -> !qcore.qubit, !qcore.qubit {
                ^bb1(%8: !qcore.qubit, %9: !qcore.qubit):
                  qstruct.yield %8, %9 : !qcore.qubit, !qcore.qubit
              }
              qstruct.yield %6, %7 : !qcore.qubit, !qcore.qubit
          }
        }
        """,
        xdsl_context,
        verify=True,
    )
    alloc = next(op for op in module.walk() if isinstance(op, qcore.AllocQubitOp))
    repeat = next(op for op in module.walk() if isinstance(op, qstruct.RepeatOp))
    circuit = next(op for op in module.walk() if isinstance(op, qstruct.CircuitOp))

    for index in range(2):
        equivalent, blocking_uses, blocking_ops = find_equivalent_qubit_ssas(
            cast(OpResult[QubitType], alloc.results[index])
        )

        assert {
            TrackedQubit(alloc.results[index]),
            TrackedQubit(repeat.body.block.args[index]),
            TrackedQubit(circuit.body.block.args[index]),
            TrackedQubit(circuit.results[index]),
            TrackedQubit(repeat.results[index]),
        } == equivalent
        assert not blocking_uses
        assert not blocking_ops

        backward_equivalent, backward_blocking_uses, backward_blocking_ops = (
            find_equivalent_qubit_ssas(cast(OpResult[QubitType], repeat.results[index]))
        )
        assert backward_equivalent == equivalent
        assert backward_blocking_uses == blocking_uses
        assert backward_blocking_ops == blocking_ops


def test_strict_traversal_tracks_nested_identity_repeats(xdsl_context: Context) -> None:
    module = parse_ir(
        """
        builtin.module {
          %0 = qcore.alloc_qubit -> !qcore.qubit
          %1 = qstruct.repeat<3> (%0 : !qcore.qubit) -> !qcore.qubit {
            ^bb0(%2: !qcore.qubit):
              %3 = qstruct.repeat<2> (%2 : !qcore.qubit) -> !qcore.qubit {
                ^bb1(%4: !qcore.qubit):
                  qstruct.yield %4 : !qcore.qubit
              }
              qstruct.yield %3 : !qcore.qubit
          }
        }
        """,
        xdsl_context,
        verify=True,
    )
    alloc = next(op for op in module.walk() if isinstance(op, qcore.AllocQubitOp))
    repeats = [op for op in module.walk() if isinstance(op, qstruct.RepeatOp)]
    outer_repeat, inner_repeat = repeats

    equivalent, blocking_uses, blocking_ops = find_equivalent_qubit_ssas(
        cast(OpResult[QubitType], alloc.results[0])
    )

    assert equivalent == {
        TrackedQubit(alloc.results[0]),
        TrackedQubit(outer_repeat.body.block.args[0]),
        TrackedQubit(inner_repeat.body.block.args[0]),
        TrackedQubit(inner_repeat.results[0]),
        TrackedQubit(outer_repeat.results[0]),
    }
    assert not blocking_uses
    assert not blocking_ops


def test_strict_traversal_tracks_identity_repeat_register(xdsl_context: Context) -> None:
    module = parse_ir(
        """
        builtin.module {
          %0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
          %1 = qstruct.repeat<3> (%0 : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
            ^bb0(%2: !qcore.qubit_reg<2>):
              qstruct.yield %2 : !qcore.qubit_reg<2>
          }
        }
        """,
        xdsl_context,
        verify=True,
    )
    alloc = next(op for op in module.walk() if isinstance(op, qcore.AllocQubitOp))
    repeat = next(op for op in module.walk() if isinstance(op, qstruct.RepeatOp))

    equivalent, blocking_uses, blocking_ops = find_equivalent_qubit_ssas(
        cast(OpResult[QubitRegType], alloc.results[0]), 1
    )

    assert equivalent == {
        TrackedQubit(alloc.results[0], 1),
        TrackedQubit(repeat.body.block.args[0], 1),
        TrackedQubit(repeat.results[0], 1),
    }
    assert not blocking_uses
    assert not blocking_ops


def test_strict_traversal_blocks_on_scf(xdsl_context: Context) -> None:
    module = parse_ir(build_for_circuit, xdsl_context, verify=True)
    alloc = next(op for op in module.walk() if isinstance(op, qcore.AllocQubitOp))
    loop = next(op for op in module.walk() if isinstance(op, scf.ForOp))

    _, blocking_uses, _ = find_equivalent_qubit_ssas(cast(OpResult[QubitType], alloc.results[0]))

    assert any(use.operation is loop for use in blocking_uses)


shifting_repeat_circuit = """
    builtin.module {
      %0, %1, %2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
      %3, %4, %5 = qstruct.circuit(%0, %1, %2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) \
           -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
      ^bb0(%6 : !qcore.qubit, %7 : !qcore.qubit, %8 : !qcore.qubit):
        %9, %10, %11 = qstruct.repeat<REPEAT_NUM> (%6, %7, %8 : !qcore.qubit, !qcore.qubit, \
               !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
        ^bb1(%12: !qcore.qubit, %13: !qcore.qubit, %14: !qcore.qubit):
          qstruct.yield %14, %12, %13 : !qcore.qubit, !qcore.qubit, !qcore.qubit
        }
        qstruct.yield %9, %10, %11 : !qcore.qubit, !qcore.qubit, !qcore.qubit
      }
    }
"""


@pytest.mark.xfail(
    reason="'qstruct.repeat' are handled as if they had an infinite number of repetitions."
)
@pytest.mark.parametrize(("repeat", "expected_equivalent_ssas"), [(1, 5), (2, 8), (3, 11)])
def test_bidirectional_traversal_shifting_circuit(
    repeat: int, expected_equivalent_ssas: int, xdsl_context: Context
) -> None:
    module = parse_ir(
        shifting_repeat_circuit.replace("REPEAT_NUM", str(repeat)), xdsl_context, verify=False
    )
    qubit_alloc_ops = [op for op in module.walk() if isinstance(op, qcore.AllocQubitOp)]
    assert len(qubit_alloc_ops) == 1
    qubit_alloc_op = qubit_alloc_ops[0]
    for qubit_ssa in qubit_alloc_op.results:
        assert isinstance(qubit_ssa.type, QubitType)
        equivalent_ssas, blocking_uses, blocking_ops = find_all_predecessor_and_successor_ssas(
            qubit_ssa
        )
        assert len(equivalent_ssas) == expected_equivalent_ssas
        assert not blocking_uses
        assert not blocking_ops
