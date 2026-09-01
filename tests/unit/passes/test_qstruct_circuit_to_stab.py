"""Tests for particular functionality in the qstruct-circuit-to-stab pass."""

import pytest
from xdsl.context import Context

from deltakit_compile.dialects import qstruct
from deltakit_compile.passes.qstruct_circuit_to_stab import _QStructToStabCircuit
from tests.unit.conftest import parse_ir


@pytest.mark.parametrize(
    ("ir", "expected_permutation"),
    [
        (
            """
            builtin.module {
                qstruct.circuit -> {
                    qstruct.yield
                }
            }
            """,
            [],
        ),
        (
            """
            builtin.module {
                %q0 = qcore.alloc_qubit -> !qcore.qubit
                qstruct.circuit(%q0 : !qcore.qubit) -> !qcore.qubit {
                ^bb0(%q0_1: !qcore.qubit):
                    qstruct.yield %q0_1 : !qcore.qubit
                }
            }
            """,
            [0],
        ),
        (
            """
            builtin.module {
                %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
                qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit)
                    -> !qcore.qubit, !qcore.qubit {
                ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit):
                    qstruct.yield %q1_1, %q0_1 : !qcore.qubit, !qcore.qubit
                }
            }
            """,
            [1, 0],
        ),
        (
            """
            builtin.module {
                %r0 = qcore.alloc_qubit -> !qcore.qubit_reg<3>
                qstruct.circuit(%r0 : !qcore.qubit_reg<3>) -> !qcore.qubit_reg<3> {
                ^bb0(%r0_1: !qcore.qubit_reg<3>):
                    qstruct.yield %r0_1 : !qcore.qubit_reg<3>
                }
            }
            """,
            [0, 1, 2],
        ),
        (
            """
            builtin.module {
                %r0 = qcore.alloc_qubit -> !qcore.qubit_reg<3>
                qstruct.circuit(%r0 : !qcore.qubit_reg<3>)
                    -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
                ^bb0(%r0_1: !qcore.qubit_reg<3>):
                    %q0, %q1, %q2 = qcore.unpack_qubit_reg(%r0_1 : !qcore.qubit_reg<3>)
                    qstruct.yield %q2, %q0, %q1 : !qcore.qubit, !qcore.qubit, !qcore.qubit
                }
            }
            """,
            [2, 0, 1],
        ),
        (
            """
            builtin.module {
                %r0 = qcore.alloc_qubit -> !qcore.qubit_reg<3>
                qstruct.circuit(%r0 : !qcore.qubit_reg<3>)
                    -> !qcore.qubit_reg<2>, !qcore.qubit_reg<1> {
                ^bb0(%r0_1: !qcore.qubit_reg<3>):
                    %q0, %q1, %q2 = qcore.unpack_qubit_reg(%r0_1 : !qcore.qubit_reg<3>)
                    %r1 = qcore.pack_qubit_reg(%q1, %q2) -> !qcore.qubit_reg<2>
                    %r2 = qcore.pack_qubit_reg(%q0) -> !qcore.qubit_reg<1>
                    %r3 = qcore.concatenate(%r1, %r2 : !qcore.qubit_reg<2>, !qcore.qubit_reg<1>)
                        -> !qcore.qubit_reg<3>
                    %r4, %r5 = qcore.split(%r3 : !qcore.qubit_reg<3>) -> !qcore.qubit_reg<1>,
                        !qcore.qubit_reg<2>
                    qstruct.yield %r5, %r4 : !qcore.qubit_reg<2>, !qcore.qubit_reg<1>
                }
            }
            """,
            [2, 0, 1],
        ),
        (
            """
            builtin.module {
                %r0, %q0, %r1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>, !qcore.qubit,
                    !qcore.qubit_reg<5>
                qstruct.circuit(%r0, %q0, %r1 : !qcore.qubit_reg<2>, !qcore.qubit,
                    !qcore.qubit_reg<5>) -> !qcore.qubit, !qcore.qubit, !qcore.qubit_reg<6> {
                ^bb0(%r0_1: !qcore.qubit_reg<2>, %q0_1: !qcore.qubit, %r1_1: !qcore.qubit_reg<5>):
                    %r2, %r3, %r4 = qcore.split(%r1_1 : !qcore.qubit_reg<5>) -> !qcore.qubit_reg<2>,
                        !qcore.qubit_reg<1>, !qcore.qubit_reg<2>
                    %q1 = qcore.unpack_qubit_reg(%r3 : !qcore.qubit_reg<1>)
                    %r5 = qcore.concatenate(%r4, %r0_1 : !qcore.qubit_reg<2>, !qcore.qubit_reg<2>)
                        -> !qcore.qubit_reg<4>
                    %q2, %q3 = qcore.unpack_qubit_reg(%r2 : !qcore.qubit_reg<2>)
                    %r6 = qcore.pack_qubit_reg(%q1, %q0_1, %q3, %q2) -> !qcore.qubit_reg<4>
                    %r7 = qcore.concatenate(%r6, %r5 : !qcore.qubit_reg<4>, !qcore.qubit_reg<4>)
                        -> !qcore.qubit_reg<8>
                    %r8, %r9 = qcore.split(%r7 : !qcore.qubit_reg<8>) -> !qcore.qubit_reg<6>,
                        !qcore.qubit_reg<2>
                    %q4, %q5 = qcore.unpack_qubit_reg(%r9 : !qcore.qubit_reg<2>)
                    qstruct.yield %q4, %q5, %r8 : !qcore.qubit, !qcore.qubit, !qcore.qubit_reg<6>
                }
            }
            """,
            [0, 1, 5, 2, 4, 3, 6, 7],
        ),
        (
            """
            builtin.module {
                %r0, %r1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2>
                qstruct.circuit(%r0, %r1 : !qcore.qubit_reg<2>, !qcore.qubit_reg<2>)
                    -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2> {
                ^bb0(%r0_1: !qcore.qubit_reg<2>, %r1_1: !qcore.qubit_reg<2>):
                    %r2, %r3 = qstruct.parallel<TOP> -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2> {
                        %q0, %q1 = qcore.unpack_qubit_reg(%r0_1 : !qcore.qubit_reg<2>)
                        %r4 = qcore.pack_qubit_reg(%q1, %q0) -> !qcore.qubit_reg<2>
                        qstruct.yield %r4 : !qcore.qubit_reg<2>
                    } {
                        %q2, %q3 = qcore.unpack_qubit_reg(%r1_1 : !qcore.qubit_reg<2>)
                        %r5 = qcore.pack_qubit_reg(%q3, %q2) -> !qcore.qubit_reg<2>
                        qstruct.yield %r5 : !qcore.qubit_reg<2>
                    }
                    qstruct.yield %r3, %r2 : !qcore.qubit_reg<2>, !qcore.qubit_reg<2>
                }
            }
            """,
            [3, 2, 1, 0],
        ),
    ],
)
def test_calculate_circuit_permutation(
    ir: str, expected_permutation: list[int], xdsl_context: Context
) -> None:
    module_op = parse_ir(ir, xdsl_context)
    circuit_op = next(op for op in module_op.walk() if isinstance(op, qstruct.CircuitOp))
    assert _QStructToStabCircuit._calculate_circuit_permutation(circuit_op) == expected_permutation


@pytest.mark.parametrize(
    "ir",
    [
        # qubit operand
        """
        builtin.module {
            %q0 = qcore.alloc_qubit -> !qcore.qubit
            qstruct.circuit(%q0 : !qcore.qubit) -> !qcore.qubit {
            ^bb0(%q0_1: !qcore.qubit):
                "test.op"(%q0_1) : (!qcore.qubit) -> ()
                qstruct.yield %q0_1 : !qcore.qubit
            }
        }
        """,
        # qubit result
        """
        builtin.module {
            %q0 = qcore.alloc_qubit -> !qcore.qubit
            qstruct.circuit(%q0 : !qcore.qubit) -> !qcore.qubit {
            ^bb0(%q0_1: !qcore.qubit):
                %q1 = "test.op"() : () -> !qcore.qubit
                qstruct.yield %q1 : !qcore.qubit
            }
        }
        """,
        # both
        """
        builtin.module {
            %q0 = qcore.alloc_qubit -> !qcore.qubit
            qstruct.circuit(%q0 : !qcore.qubit) -> !qcore.qubit {
            ^bb0(%q0_1: !qcore.qubit):
                %q1 = "test.op"(%q0_1) : (!qcore.qubit) -> !qcore.qubit
                qstruct.yield %q1 : !qcore.qubit
            }
        }
        """,
    ],
)
def test_calculate_circuit_permutation_unknown_op(ir: str, xdsl_context: Context) -> None:
    module_op = parse_ir(ir, xdsl_context)
    circuit_op = next(op for op in module_op.walk() if isinstance(op, qstruct.CircuitOp))
    with pytest.raises(
        NotImplementedError,
        match=(
            r'Cannot calculate permutation through unknown op .*"test\.op".* in qstruct circuit'
        ),
    ):
        _QStructToStabCircuit._calculate_circuit_permutation(circuit_op)
