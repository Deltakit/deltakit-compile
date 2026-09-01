"""Unit tests for the individual rewrite patterns in `stab_circuit_to_qstruct`.

These tests check that each individual rewrite pattern produces the expected
number of objects of a certain type.
"""

from __future__ import annotations

from xdsl.context import Context
from xdsl.dialects import test as test_dialect
from xdsl.dialects.builtin import IntegerType, ModuleOp, UnrealizedConversionCastOp
from xdsl.ir import Block, Region
from xdsl.pattern_rewriter import PatternRewriter, PatternRewriteWalker

from deltakit_compile.dialects import qstruct
from deltakit_compile.dialects import stabiliser as stab
from deltakit_compile.dialects.qcore import (
    AllocQubitOp,
    PackQubitRegOp,
    QubitRegType,
    QubitType,
)
from deltakit_compile.passes.stab_circuit_to_qstruct import (
    _ConvertStabStateTypes,
    _LowerStabCast,
    _LowerStabCircuit,
    _LowerStabMake,
)
from tests.unit.conftest import parse_ir


def _count_ops(module: ModuleOp, op_type: type) -> int:
    return sum(1 for op in module.walk() if isinstance(op, op_type))


def test_lower_stab_make_produces_pack_and_unrealized_cast() -> None:
    """`_LowerStabMake` should replace `stab.state.make` with `qcore.pack_qubit_reg` + cast."""

    # Build: stab.state.make(%q0, %q1) -> !stab.state<2>
    in_state_t = stab.StateType(2, QubitType(), [])

    alloc = AllocQubitOp([QubitType(), QubitType()], [])
    q0, q1 = alloc.results
    make = stab.StateMakeOp([q0, q1], in_state_t)
    # Keep the make result alive so DCE can't erase the lowered pack/cast.
    keep = test_dialect.TestOp(operands=[make.output], result_types=[])
    module = ModuleOp([alloc, make, keep])

    _LowerStabMake().match_and_rewrite(make, PatternRewriter(make))

    assert _count_ops(module, stab.StateMakeOp) == 0
    assert _count_ops(module, PackQubitRegOp) == 1
    assert _count_ops(module, UnrealizedConversionCastOp) == 1


def test_lower_stab_cast_produces_unrealized_cast_only() -> None:
    """`_LowerStabCast` should erase `stab.state.cast` into an unrealized cast."""

    in_state_t = stab.StateType(1, QubitType(), [])
    out_state_t = stab.StateType(1, QubitType(), [])

    # Produce a fake input state via an unrealized cast from a qubit_reg.
    fake_reg = test_dialect.TestOp(result_types=[QubitRegType(1)]).res[0]
    to_state = UnrealizedConversionCastOp.get([fake_reg], [in_state_t])
    cast = stab.StateCastOp(to_state.outputs[0], out_state_t)

    # Keep cast result alive to avoid DCE removing the lowered cast.
    keep = test_dialect.TestOp(operands=[cast.output], result_types=[])
    module = ModuleOp([fake_reg.owner, to_state, cast, keep])
    _LowerStabCast().match_and_rewrite(cast, PatternRewriter(cast))

    assert _count_ops(module, stab.StateCastOp) == 0
    # One original unrealized cast remains (qcore.qubit_reg -> stab.state), and the
    # stab.state.cast is replaced by exactly one new unrealized cast (stab.state -> stab.state).
    assert _count_ops(module, UnrealizedConversionCastOp) == 2


def _mk_minimal_stab_circuit_with_make_and_cast() -> ModuleOp:
    """Create a module containing a `stab.circuit` with `stab.state.make` and `stab.state.cast`.

    The circuit signature includes a non-qubit argument/result to ensure the lowering keeps extra
    operands/results intact.
    """

    i1 = IntegerType(1)

    # State with 2 qubits and no flow states.
    in_state_t = stab.StateType(2, QubitType(), [])
    out_state_t = stab.StateType(2, QubitType(), [])

    # Circuit body block args are 2 qubits + the extra i1 argument.
    q = QubitType()
    block = Block(arg_types=[q, q, i1])
    body = Region(block)
    q0, q1, flag = block.args

    make_op = stab.StateMakeOp([q0, q1], in_state_t)
    block.add_op(make_op)
    cast_op = stab.StateCastOp(make_op.output, out_state_t)
    block.add_op(cast_op)
    yield_op = stab.YieldOp(measurements=[], arguments=[cast_op.output, flag])
    block.add_op(yield_op)

    # The outer `stab.circuit` takes a state value plus the extra i1.
    state_val = test_dialect.TestOp(result_types=[in_state_t]).res[0]
    circuit = stab.CircuitOp(
        state_val,
        out_state_t,
        input_args=[flag],
        body=body,
        output_args_types=[i1],
    )

    return ModuleOp([state_val.owner, circuit])


def test_lower_stab_circuit_produces_qstruct_circuit_and_unrealized_casts() -> None:
    """`_LowerStabCircuit` should replace `stab.circuit` with casts + `qstruct.circuit`."""

    module = _mk_minimal_stab_circuit_with_make_and_cast()

    # Apply the pattern directly to the single `stab.circuit` op, like the other unit tests in
    # this file do (avoids relying on module-wide greedy rewriting infrastructure).
    [circuit_op] = [op for op in module.walk() if isinstance(op, stab.CircuitOp)]
    _LowerStabCircuit().match_and_rewrite(circuit_op, PatternRewriter(circuit_op))

    assert _count_ops(module, stab.CircuitOp) == 0
    assert _count_ops(module, qstruct.CircuitOp) == 1
    # There should be 2 casts bridging `stab.state` <-> `qcore.qubit_reg` at the circuit
    # boundary.
    assert _count_ops(module, UnrealizedConversionCastOp) == 2


def test_convert_stab_state_types_rewrites_stab_state_types_(xdsl_context: Context) -> None:
    """`_ConvertStabStateTypes` should convert `!stab.state` types in control flow to
    `!qcore.qubit_reg` types."""

    ir = """
    builtin.module {
        %q0 = qcore.alloc_qubit -> !qcore.qubit
        %r0 = qcore.pack_qubit_reg(%q0) -> !qcore.qubit_reg<1>
        %s0 = builtin.unrealized_conversion_cast %r0 : !qcore.qubit_reg<1> to
            !stab.state<1 x !qcore.qubit, []>
        %s1 = qstruct.parallel<TOP> -> !stab.state<1 x !qcore.qubit, []> {
            qstruct.yield %s0 : !stab.state<1 x !qcore.qubit, []>
        }
    }
    """
    expected_ir = """
    builtin.module {
        %q0 = qcore.alloc_qubit -> !qcore.qubit
        %r0 = qcore.pack_qubit_reg(%q0) -> !qcore.qubit_reg<1>
        %s0 = builtin.unrealized_conversion_cast %r0 : !qcore.qubit_reg<1> to
            !stab.state<1 x !qcore.qubit, []>
        %s1 = qstruct.parallel<TOP> -> !qcore.qubit_reg<1> {
            %s0_1 = builtin.unrealized_conversion_cast %s0 : !stab.state<1 x !qcore.qubit, []> to
                !qcore.qubit_reg<1>
            qstruct.yield %s0_1 : !qcore.qubit_reg<1>
        }
        %s1_1 = builtin.unrealized_conversion_cast %s1 : !qcore.qubit_reg<1> to
            !stab.state<1 x !qcore.qubit, []>
    }
    """

    module = parse_ir(ir, xdsl_context)
    expected_module = parse_ir(expected_ir, xdsl_context)
    PatternRewriteWalker(_ConvertStabStateTypes(), apply_recursively=False).rewrite_module(module)
    assert str(module) == str(expected_module)
