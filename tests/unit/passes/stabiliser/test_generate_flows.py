"""Test file for stab_flow_generate_flows_pass.py"""

import re
from collections.abc import Callable
from typing import Literal, cast

import pytest
from xdsl.dialects import test
from xdsl.dialects.builtin import ArrayAttr
from xdsl.ir import Block, Region, SSAValue
from xdsl.pattern_rewriter import PatternRewriter

from deltakit_compile.dialects import qcore, qref, qstruct
from deltakit_compile.dialects.stabiliser import (
    CircuitOp,
    FlowAttr,
    StateMakeOp,
    StatePermuteOp,
    StateType,
    StateTypePauliStrings,
    YieldOp,
)
from deltakit_compile.exceptions import BadUserFlowError
from deltakit_compile.passes.stabiliser._common import CircuitFlowData, MMTResults
from deltakit_compile.passes.stabiliser.generate_flows import (
    _FlowChain,
    _GenerateFlows,
    _StateUseDefChain,
    _StateUseDefChainEntry,
)

PauliLiteral = Literal["X", "Y", "Z"]

# region Use-def chain tests


def test_state_use_def_chain_entry_invalid():
    """Test that _StateUseDefChainEntry validates its inputs as specified in the docstring."""
    ssa1, ssa2 = test.TestOp(result_types=[test.TestType("A")] * 2).results
    test_op = test.TestOp(operands=[ssa1], result_types=[test.TestType("A")])

    with pytest.raises(
        ValueError,
        match=re.escape("Input state SSA value must be an operand of the input operation."),
    ):
        _StateUseDefChainEntry(
            input_state_ssa=ssa2,
            output_state_ssa=test_op.results[0],
            input_operation=test_op,
            output_operation=test_op,
        )
    with pytest.raises(
        ValueError,
        match=re.escape("Output state SSA value must be a result of the output operation."),
    ):
        _StateUseDefChainEntry(
            input_state_ssa=ssa1,
            output_state_ssa=ssa2,
            input_operation=test_op,
            output_operation=test_op,
        )
    with pytest.raises(
        NotImplementedError,
        match=re.escape(
            "Unsupported use-def chain entry: only stab.circuit ops, stab.state.permute ops, and "
            "qstruct.parallel yields are supported."
        ),
    ):
        _StateUseDefChainEntry(
            input_state_ssa=ssa1,
            output_state_ssa=test_op.results[0],
            input_operation=test_op,
            output_operation=test_op,
        )


def test_state_use_def_chain_append():
    """Test appending several entries to a _StateUseDefChain."""
    q0 = test.TestOp(result_types=[qcore.QubitType()]).results[0]
    make_op = StateMakeOp([q0], StateType(1, qcore.QubitType(), []))

    permute_op = StatePermuteOp(make_op.output, permutation=[0])
    yield_op = qstruct.YieldOp(q0, permute_op.output)
    parallel_op = qstruct.ParallelOp(
        [qcore.QubitType(), StateType(1, qcore.QubitType(), [])], [Block([yield_op])]
    )

    use_def_chain = _StateUseDefChain(make_op)
    assert use_def_chain.initial_ssa == make_op.output
    assert use_def_chain.final_ssa == make_op.output

    use_def_chain.append(permute_op.output)
    assert use_def_chain.final_ssa == permute_op.output
    assert list(use_def_chain) == [
        _StateUseDefChainEntry(
            input_state_ssa=make_op.output,
            output_state_ssa=permute_op.output,
            input_operation=permute_op,
            output_operation=permute_op,
        )
    ]

    use_def_chain.append(parallel_op.results[1], input_op=yield_op)
    assert use_def_chain.final_ssa == parallel_op.results[1]
    assert list(use_def_chain) == [
        _StateUseDefChainEntry(
            input_state_ssa=make_op.output,
            output_state_ssa=permute_op.output,
            input_operation=permute_op,
            output_operation=permute_op,
        ),
        _StateUseDefChainEntry(
            input_state_ssa=permute_op.output,
            output_state_ssa=parallel_op.results[1],
            input_operation=yield_op,
            output_operation=parallel_op,
        ),
    ]


def test_state_use_def_chain_append_invalid():
    """Test that appending an unrelated entry to a _StateUseDefChain raises an error."""
    q0 = test.TestOp(result_types=[qcore.QubitType()]).results[0]
    make_op = StateMakeOp([q0], StateType(1, qcore.QubitType(), []))
    use_def_chain = _StateUseDefChain(make_op)

    unrelated_ssa = test.TestOp(result_types=[StateType(1, qcore.QubitType(), [])]).results[0]
    unrelated_permute = StatePermuteOp(unrelated_ssa, permutation=[0])

    with pytest.raises(
        ValueError,
        match=re.escape(
            "The final state SSA value of the chain must be an operand of the input op."
        ),
    ):
        use_def_chain.append(make_op.output, input_op=unrelated_permute)


def test_state_use_def_chain_trace():
    """Test that _UseDefChain.trace correctly traces a chain of operations."""
    q0 = qcore.AllocQubitOp(qcore.QubitType()).result[0]
    make_op = StateMakeOp([q0], StateType(1, qcore.QubitType(), []))

    circuit_op = CircuitOp(
        make_op.output,
        output_state_type=StateType(1, qcore.QubitType(), []),
        input_args=[],
        body=Block([YieldOp([], [])]),
        flows=None,
    )
    permute_op = StatePermuteOp(circuit_op.output, permutation=[0])
    yield_op = qstruct.YieldOp(permute_op.output)
    parallel_op = qstruct.ParallelOp([StateType(1, qcore.QubitType(), [])], [Block([yield_op])])

    chain = _StateUseDefChain.trace(make_op)

    assert chain.initial_ssa == make_op.output
    assert chain.final_ssa == parallel_op.res[0]
    assert list(chain) == [
        _StateUseDefChainEntry(
            input_state_ssa=make_op.output,
            output_state_ssa=circuit_op.output,
            input_operation=circuit_op,
            output_operation=circuit_op,
        ),
        _StateUseDefChainEntry(
            input_state_ssa=circuit_op.output,
            output_state_ssa=permute_op.output,
            input_operation=permute_op,
            output_operation=permute_op,
        ),
        _StateUseDefChainEntry(
            input_state_ssa=permute_op.output,
            output_state_ssa=parallel_op.res[0],
            input_operation=yield_op,
            output_operation=parallel_op,
        ),
    ]


def test_state_use_def_chain_trace_error_unsupported_operation():
    """Test that _StateUseDefChain.trace raises for unsupported operations."""
    q0 = qcore.AllocQubitOp(qcore.QubitType()).result[0]
    make_op = StateMakeOp([q0], StateType(1, qcore.QubitType(), []))
    test.TestOp(operands=[make_op.output], result_types=[StateType(1, qcore.QubitType(), [])])

    with pytest.raises(
        NotImplementedError,
        match=re.escape("Generate flows pass does not support test.op operations."),
    ):
        _StateUseDefChain.trace(make_op)


def test_state_use_def_chain_trace_error_yield_other_than_parallel():
    """Test that _StateUseDefChain.trace raises for unsupported uses of qstruct.yield."""
    q0 = qcore.AllocQubitOp(qcore.QubitType()).result[0]
    make_op = StateMakeOp([q0], StateType(1, qcore.QubitType(), []))
    yield_in_repeat = qstruct.YieldOp(make_op.output)
    qstruct.RepeatOp(repetitions=1, body=Block([yield_in_repeat]))

    with pytest.raises(
        NotImplementedError,
        match=re.escape(
            "Generate flows pass supports tracing through yields of qstruct.parallel ops only."
        ),
    ):
        _StateUseDefChain.trace(make_op)


def test_state_use_def_chain_trace_error_multiple_uses():
    """Test that _StateUseDefChain.trace raises if an SSA value is used by multiple operations."""
    q0 = qcore.AllocQubitOp(qcore.QubitType()).result[0]
    make_op = StateMakeOp([q0], StateType(1, qcore.QubitType(), []))
    StatePermuteOp(make_op.output, permutation=[0])
    StatePermuteOp(make_op.output, permutation=[0])

    with pytest.raises(
        NotImplementedError,
        match=re.escape("State type is used by multiple operations which is not supported."),
    ):
        _StateUseDefChain.trace(make_op)


# region _FlowChain class tests


def test_flow_chain_incorrect_inputs():
    """Ensure _FlowChain validates inputs and measurement lengths."""
    msg = "Flow chain requires at least one flow state."
    with pytest.raises(ValueError, match=msg):
        _FlowChain(flows=[], measurements=[])
    msg2 = "Measurement list length must be one less than number of flows."
    with pytest.raises(ValueError, match=msg2):
        _FlowChain(
            flows=[qcore.PauliStringAttr([("X", 0)], 1), qcore.PauliStringAttr([("Z", 0)], 1)],
            measurements=[],
        )
    msg3 = "Measurement list length must be one less than number of flows."
    with pytest.raises(ValueError, match=msg3):
        _FlowChain(
            flows=[qcore.PauliStringAttr([("X", 0)], 1), qcore.PauliStringAttr([("Z", 0)], 1)],
            measurements=[MMTResults(), MMTResults()],
        )
    msg4 = (
        "A flow chain requires each flow to be on the same number of qubits, but {1, 2} were found"
    )
    with pytest.raises(ValueError, match=msg4):
        _FlowChain(
            flows=[qcore.PauliStringAttr([("X", 0)], 1), qcore.PauliStringAttr([("Z", 0)], 2)],
            measurements=[MMTResults()],
        )


def test_multiply_flow_chains():
    """Test __mul__ combines flows, measurements, and resets user flags."""
    m1 = _mk_mmt_results()

    chain1 = _FlowChain(
        flows=[qcore.PauliStringAttr([("X", 0)], 1), qcore.PauliStringAttr([("Z", 0)], 1)],
        measurements=[MMTResults()],
        last_user_flow_age=0,
    )
    chain2 = _FlowChain(
        flows=[qcore.PauliStringAttr([("Z", 0)], 1), qcore.PauliStringAttr([("Y", 0)], 1)],
        measurements=[m1],
    )
    expected_product = _FlowChain(
        flows=[qcore.PauliStringAttr([("Y", 0)], 1), qcore.PauliStringAttr([("X", 0)], 1)],
        measurements=[m1],
    )
    product = chain1 * chain2
    assert product.flows == expected_product.flows
    assert len(product.measurements) == len(expected_product.measurements)
    assert all(
        product.measurements[i] == expected_product.measurements[i]
        for i in range(len(product.measurements))
    )
    assert product.is_user_flow == expected_product.is_user_flow


def test_multiply_flow_chains_user_age_preserved_when_other_young_enough():
    """The last user flow age is preserved when the other chain is young enough to not disrupt the
    last user flow."""
    # chain1: length 3, last_user_flow_age=1; chain2: age=1 (I -> I -> X0)
    chain1 = _FlowChain(
        flows=[
            qcore.PauliStringAttr([("X", 0)], 1),
            qcore.PauliStringAttr([("Z", 0)], 1),
            qcore.PauliStringAttr([("Y", 0)], 1),
        ],
        measurements=[MMTResults(), MMTResults()],
        last_user_flow_age=1,
    )
    chain2 = _FlowChain(
        flows=[
            qcore.PauliStringAttr.identity(1),
            qcore.PauliStringAttr.identity(1),
            qcore.PauliStringAttr([("X", 0)], 1),
        ],
        measurements=[MMTResults(), MMTResults()],
    )
    assert chain2.age == 1

    product = chain1 * chain2
    assert product.last_user_flow_age == 1

    # Also test the reverse
    product_reverse = chain2 * chain1
    assert product_reverse.last_user_flow_age == 1


def test_multiply_flow_chains_both_user_ages_too_old_drops_user_age():
    """When both chains have user ages but neither is young enough to preserve the other's,
    the product has no user age."""
    # chain1: last_user_flow_age=0, age=3; chain2: last_user_flow_age=0, age=3
    chain1 = _FlowChain(
        flows=[
            qcore.PauliStringAttr([("X", 0)], 1),
            qcore.PauliStringAttr([("Z", 0)], 1),
            qcore.PauliStringAttr([("Y", 0)], 1),
        ],
        measurements=[MMTResults(), MMTResults()],
        last_user_flow_age=0,
    )
    chain2 = _FlowChain(
        flows=[
            qcore.PauliStringAttr([("Z", 0)], 1),
            qcore.PauliStringAttr([("X", 0)], 1),
            qcore.PauliStringAttr([("Z", 0)], 1),
        ],
        measurements=[MMTResults(), MMTResults()],
        last_user_flow_age=0,
    )
    product = chain1 * chain2
    assert product.last_user_flow_age is None


def test_multiply_flow_chains_neither_user_produces_non_user():
    """When neither chain has a user flow, the product is not a user flow."""
    chain1 = _FlowChain(
        flows=[qcore.PauliStringAttr([("X", 0)], 1), qcore.PauliStringAttr([("Z", 0)], 1)],
        measurements=[MMTResults()],
    )
    chain2 = _FlowChain(
        flows=[qcore.PauliStringAttr([("Z", 0)], 1), qcore.PauliStringAttr([("X", 0)], 1)],
        measurements=[MMTResults()],
    )
    product = chain1 * chain2
    assert product.last_user_flow_age is None
    assert not product.is_user_flow


def test_multiply_flow_chains_different_lengths():
    """Test that multiplying chains of different lengths raises an error."""
    chain1 = _FlowChain(flows=[qcore.PauliStringAttr([("X", 0)], 1)], measurements=[])
    chain2 = _FlowChain(
        flows=[qcore.PauliStringAttr([("Z", 0)], 1), qcore.PauliStringAttr([("Y", 0)], 1)],
        measurements=[MMTResults()],
    )
    msg = "Flow chains provided do not have same length."
    with pytest.raises(ValueError, match=msg):
        chain1 * chain2


def test_multiply_many_chains_empty_list_raises():
    """An empty list should raise a ValueError."""
    msg = "Require at least one _FlowChain for multiplication."
    with pytest.raises(ValueError, match=msg):
        _FlowChain.multiply_many([])


def test_multiply_many_chains_single_element_returns_it():
    """A single-element list should return that exact _FlowChain instance."""
    chain = _FlowChain(
        flows=[qcore.PauliStringAttr([("X", 0)], 1), qcore.PauliStringAttr([("Z", 0)], 1)],
        measurements=[MMTResults()],
        last_user_flow_age=0,
    )
    result = _FlowChain.multiply_many([chain])
    assert result is chain


def test_multiply_many_chains_three_chains_product():
    """Multiplication of three equal-length chains produces the expected flow and measurements."""
    # All chains length 3, so 2 measurement steps per chain
    chain1 = _FlowChain(
        flows=[
            qcore.PauliStringAttr([("X", 0)], 1),
            qcore.PauliStringAttr([("Z", 0)], 1),
            qcore.PauliStringAttr.identity(1),
        ],
        measurements=[MMTResults(), MMTResults()],
    )
    chain2 = _FlowChain(
        flows=[
            qcore.PauliStringAttr([("Z", 0)], 1),
            qcore.PauliStringAttr([("Z", 0)], 1),
            qcore.PauliStringAttr([("X", 0)], 1),
        ],
        measurements=[MMTResults(), MMTResults()],
    )
    chain3 = _FlowChain(
        flows=[
            qcore.PauliStringAttr([("Y", 0)], 1),
            qcore.PauliStringAttr([("X", 0)], 1),
            qcore.PauliStringAttr([("Z", 0)], 1),
        ],
        measurements=[MMTResults(), MMTResults()],
    )

    product = _FlowChain.multiply_many([chain1, chain2, chain3])

    # Expected per position:
    # pos0: X * Z = Y; Y * Y = I
    # pos1: Z * Z = I; I * X = X
    # pos2: I * X = X; X * Z = Y
    assert product.flows == [
        qcore.PauliStringAttr.identity(1),
        qcore.PauliStringAttr([("X", 0)], 1),
        qcore.PauliStringAttr([("Y", 0)], 1),
    ]
    # Measurements symmetric difference of empty sets stays empty
    assert product.measurements == [MMTResults(), MMTResults()]
    # Product chains are marked as not user-specified
    assert not product.is_user_flow


def _mk_mmt_results() -> MMTResults:
    """Create a measurement readout bundle (MMTResults) using a 1-qubit Z measurement."""
    body = Block(arg_types=[qcore.QubitType()])
    (q0,) = body.args
    gate = qref.MeasureOp("Z", [q0])
    body.add_op(gate)
    return MMTResults(gate.measurements)


def test_add_to_chain_appends_flow_and_measurements():
    """Append a new flow and ensure the measurement MMTResults set is recorded correctly."""
    chain = _FlowChain(flows=[qcore.PauliStringAttr([("X", 0)], 1)], measurements=[])
    new_flow = qcore.PauliStringAttr([("Z", 0)], 1)
    m1 = _mk_mmt_results()
    m2 = _mk_mmt_results()
    mmt_set = m1.union(m2)

    returned = chain.add_to_chain(new_flow, mmt_set, None)

    assert returned.flows == [
        qcore.PauliStringAttr([("X", 0)], 1),
        qcore.PauliStringAttr([("Z", 0)], 1),
    ]
    assert len(returned.measurements) == 1
    assert returned.measurements[0] == mmt_set


def test_add_to_chain_is_user_flow_flag_sets_age_zero():
    """When is_user_flow_flag=True the new link is the user link, so last_user_flow_age=0."""
    chain = _FlowChain(flows=[qcore.PauliStringAttr([("X", 0)], 1)], measurements=[])
    result = chain.add_to_chain(
        qcore.PauliStringAttr([("Z", 0)], 1), measurements_from_prev=None, is_user_flow_flag=True
    )
    assert result.last_user_flow_age == 0
    assert result.is_user_flow


def test_add_to_chain_existing_user_age_incremented():
    """When the chain already has a user age, each extension increments it by 1."""
    chain = _FlowChain(
        flows=[qcore.PauliStringAttr([("X", 0)], 1), qcore.PauliStringAttr([("Z", 0)], 1)],
        measurements=[MMTResults()],
        last_user_flow_age=0,
    )
    extended = chain.add_to_chain(qcore.PauliStringAttr([("Y", 0)], 1), measurements_from_prev=None)
    assert extended.last_user_flow_age == 1

    extended_again = extended.add_to_chain(
        qcore.PauliStringAttr([("X", 0)], 1), measurements_from_prev=None
    )
    assert extended_again.last_user_flow_age == 2


def test_add_to_chain_no_user_age_remains_none():
    """When the chain has no user age and the flag is False, the result has no user age."""
    chain = _FlowChain(flows=[qcore.PauliStringAttr([("X", 0)], 1)], measurements=[])
    result = chain.add_to_chain(
        qcore.PauliStringAttr([("Z", 0)], 1), measurements_from_prev=None, is_user_flow_flag=False
    )
    assert result.last_user_flow_age is None
    assert not result.is_user_flow


def test_mult_near_identical_chains_identity_result():
    """Two chains identical up to the last step whose end flows multiply to I
    should return an identity chain with the final measurement set equal to the
    symmetric difference of the last measurement sets.
    """
    i = qcore.PauliStringAttr.identity(1)
    z0 = qcore.PauliStringAttr([("Z", 0)], 1)
    x0 = qcore.PauliStringAttr([("X", 0)], 1)

    m1 = _mk_mmt_results()

    # Build two near-identical chains of length 3, differing only in last mmt set
    chain1 = _FlowChain(flows=[i, z0, x0], measurements=[MMTResults(), m1])
    chain2 = _FlowChain(flows=[i, z0, x0], measurements=[MMTResults(), MMTResults()])

    result = _FlowChain.mult_near_identical(chain1, chain2)

    # Expect I -> I -> I and measurements [∅, {m1}]
    assert result.flows == [i, i, i]
    assert result.measurements == [MMTResults(), m1]
    assert not result.is_user_flow


def test_mult_near_identical_chains_length_1():
    """Chains of length 1 should be considered near-identical and just multiplied."""
    i = qcore.PauliStringAttr.identity(1)
    x0 = qcore.PauliStringAttr([("X", 0)], 1)

    chain = _FlowChain(flows=[x0, x0], measurements=[MMTResults()], last_user_flow_age=0)
    result = _FlowChain.mult_near_identical(chain, chain)

    assert result.flows == [i, i]
    assert result.measurements == [MMTResults()]
    assert not result.is_user_flow


def test_mult_near_identical_chains_raises_on_flow_prefix_mismatch():
    """Mismatched prefix flows should raise an informative ValueError."""
    i = qcore.PauliStringAttr.identity(1)
    x0 = qcore.PauliStringAttr([("X", 0)], 1)
    z0 = qcore.PauliStringAttr([("Z", 0)], 1)

    chain1 = _FlowChain(flows=[i, x0, z0], measurements=[MMTResults(), MMTResults()])
    chain2 = _FlowChain(flows=[i, z0, x0], measurements=[MMTResults(), MMTResults()])
    msg = "There are flow states, other than the last, that don't match."
    with pytest.raises(ValueError, match=msg):
        _FlowChain.mult_near_identical(chain1, chain2)


def test_mult_near_identical_chains_raises_on_measurement_prefix_mismatch():
    """Mismatched prefix measurement histories should raise an informative ValueError."""
    i = qcore.PauliStringAttr.identity(1)
    x0 = qcore.PauliStringAttr([("X", 0)], 1)

    m1 = _mk_mmt_results()

    # Same prefix flows, but different first measurement set
    chain1 = _FlowChain(flows=[i, x0, x0], measurements=[MMTResults(), MMTResults()])
    chain2 = _FlowChain(flows=[i, x0, x0], measurements=[m1, MMTResults()])

    msg = "There are measurement results, other than the last, that don't match."
    with pytest.raises(
        ValueError,
        match=msg,
    ):
        _FlowChain.mult_near_identical(chain1, chain2)


def test_age_examples_from_docstring():
    """Age examples: I->I->I->A->B has age 2, A->B->C has age 3.
    We don't care about cases such as I -> A -> I -> B as the
    chain I -> A -> I will be written into circuit ops and this portion
    of the  chain would be replaced by I -> I -> I"""
    i = qcore.PauliStringAttr.identity(2)
    x = qcore.PauliStringAttr([("X", 0)], 2)
    y = qcore.PauliStringAttr([("Z", 0)], 2)
    z = qcore.PauliStringAttr([("Y", 1)], 2)

    chain1 = _FlowChain(
        flows=[i, i, i, x, y], measurements=[MMTResults(), MMTResults(), MMTResults(), MMTResults()]
    )
    assert chain1.age == 2

    chain2 = _FlowChain(flows=[x, y, z], measurements=[MMTResults(), MMTResults()])
    assert chain2.age == 3

    chain3 = _FlowChain(flows=[i, i, i], measurements=[MMTResults(), MMTResults()])
    assert chain3.age == 0


# endregion
# region GenerateFlows class tests


def mk_state_type(qubits: int, flow_states: StateTypePauliStrings) -> StateType:
    """Create a StateType with a single flow state over the given number of qubits."""
    return StateType(qubits=qubits, qubit_type=qcore.QubitType(), flow_states=flow_states)


def mk_circuit_op(
    input_qubits: int,
    input_flows: StateTypePauliStrings,
    output_flows: StateTypePauliStrings,
    add_ops: Callable,
    flows: list[FlowAttr] | None,
    *,
    input_state: SSAValue | None = None,
) -> CircuitOp:
    """Construct a CircuitOp.

    Args:
        input_qubits: Number of input qubits for the circuit body.
        input_flows: Input stabiliser states.
        output_flows: Expected output stabiliser states.
        add_ops: Function that takes a Block and mutates it by adding gate ops in order.
        flows: List of FlowAttr annotations or None.
        input_state: Optional input state SSA value for the circuit interface. If omitted,
            a fresh `stab.state.make` is inserted to create the state.

    Returns:
        CircuitOp: Circuit op containing qubit and flow data input.
    """
    if input_state is None:
        qb_ops = [qcore.AllocQubitOp(qcore.QubitType()) for _ in range(input_qubits)]
        input_state_op = StateMakeOp(
            input_qubits=[qb.result[0] for qb in qb_ops],
            state_type=mk_state_type(input_qubits, input_flows),
        )
        input_state = input_state_op.output

    body = Block(arg_types=[qcore.QubitType() for _ in range(input_qubits)])
    add_ops(body)

    # Append a terminator: stab.YieldOp. Collect measurement readouts in order, yield no args.
    measurements: list[SSAValue] = []
    for op in body.ops:
        if isinstance(op, qref.MeasureOp):
            measurements.extend(op.measurements)
    body.add_op(YieldOp(measurements, []))

    return CircuitOp(
        input_state,
        output_state_type=mk_state_type(input_qubits, output_flows),
        input_args=[],
        output_args_types=[],
        body=body,
        flows=flows,
    )


@pytest.mark.parametrize(
    ("chain_ends", "expected_output_flow_states"),
    [
        # Z0 -> Z0 and Z0 -> I expected
        ([[("Z", 0)]], [[("Z", 0)], []]),
        # X0 Z1 and X0 Z2 both blocked so expect Z1 Z2 -> Z0 Z1 Z2 (with mmt)
        # and Z1 Z2 -> Z1 Z2 (no mmt)
        # which gets reduced to Z1 Z2 -> Z1 Z2 and I -> Z0
        (
            [[("X", 0), ("Z", 1)], [("X", 0), ("Z", 2)]],
            [[("Z", 1), ("Z", 2)], [("Z", 0)]],
        ),
    ],
)
def test_propagate_flow_chains_mz_gate(chain_ends, expected_output_flow_states):
    """Test propagate_flow_chains deal with branching and blocking of flows correctly
    through an MZ gate."""

    def _add_ops(body: Block):
        q0, _, _ = body.args
        body.add_op(qref.MeasureOp("Z", [q0]))

    circuit = mk_circuit_op(
        input_qubits=3, input_flows=[], output_flows=[], add_ops=_add_ops, flows=[]
    )
    chain_list = [
        _FlowChain(flows=[qcore.PauliStringAttr(chain_end, 3)], measurements=[])
        for chain_end in chain_ends
    ]
    propagations = _GenerateFlows.propagate_flow_chains(chain_list, [], 1, circuit)
    output_flows = {f.end_state for f in propagations}
    assert set(output_flows) == {
        qcore.PauliStringAttr(state, 3) for state in expected_output_flow_states
    }


def test_propagate_flow_chains_one_many_two_measurements_same_qubit():
    """Propagate a single chain through two Z measurements on the same qubit.

    This exercises one-to-many branching across a circuit op and the reduction logic
    that keeps the measurement-recorded branch plus adjacent pair products.
    """

    def _add_ops(body: Block):
        (q0,) = body.args
        body.add_op(qref.MeasureOp("Z", [q0]))
        body.add_op(qref.MeasureOp("Z", [q0]))

    circuit = mk_circuit_op(
        input_qubits=1, input_flows=[], output_flows=[], add_ops=_add_ops, flows=[]
    )

    # Start with Z0, which commutes and branches at each measurement
    chain_list = [_FlowChain(flows=[qcore.PauliStringAttr([("Z", 0)], 1)], measurements=[])]

    propagations = _GenerateFlows.propagate_flow_chains(chain_list, [], 1, circuit)

    # Expect 3 linearly independent output chains:
    # Z0 -> I (m1), I -> I (m1, m2), I -> Z0 (m1)
    assert len(propagations) == 3

    end_states = [ch.end_state for ch in propagations]
    # 2 branches end in identity, other in Z0
    assert end_states.count(qcore.PauliStringAttr.identity(1)) == 2
    assert end_states.count(qcore.PauliStringAttr([("Z", 0)], 1)) == 1

    # Compare measurement history sizes
    # Note: each chain has exactly one measurement set corresponding to this circuit op
    m_sizes = [len(ch.measurements[0]) for ch in propagations]
    assert sorted(m_sizes) == [1, 1, 2]


def test_unblock_chains_single_measurement_blocked_x_flows():
    """Two chains blocked by the same Z measurement on q0 should multiply to unblock.

    Starting from X0 and X0, both anti-commute with MZ and are blocked. Their product is I,
    which commutes with MZ and branches to I (no readout) and Z0 (with readout). Reduction
    keeps Z0 and adds I via adjacent multiplication.
    """

    def _add_ops(body: Block):
        (q0,) = body.args
        body.add_op(qref.MeasureOp("Z", [q0]))

    circuit = mk_circuit_op(
        input_qubits=1, input_flows=[], output_flows=[], add_ops=_add_ops, flows=[]
    )

    chain_list = [
        _FlowChain(flows=[qcore.PauliStringAttr([("X", 0)], 1)], measurements=[]),
        _FlowChain(flows=[qcore.PauliStringAttr([("X", 0)], 1)], measurements=[]),
    ]

    propagations = _GenerateFlows.propagate_flow_chains(chain_list, [], 1, circuit)

    output_flows = {ch.end_state for ch in propagations}
    assert output_flows == {qcore.PauliStringAttr.identity(1), qcore.PauliStringAttr([("Z", 0)], 1)}


def test_propagate_flow_chains_gates_and_annotations_together():
    """Test propagate_flow_chains with both gate-propagated and annotation-propagated chains.

    Circuit: H gate on q0 with annotated flow X0 -> Z0.
    Gate-propagated chain ends in Z0, annotation-propagated chain ends in X0.
    After H: gate chain Z0 -> X0 via gates, user chain X0 -> Z0 via annotation.
    The annotated flow should be preserved and the gate-propagated flow should coexist.
    """

    def _add_ops(body: Block):
        (q0,) = body.args
        body.add_op(qref.GateOp(qcore.HGateAttr(), [q0]))

    x0 = qcore.PauliStringAttr([("X", 0)], 1)
    z0 = qcore.PauliStringAttr([("Z", 0)], 1)

    circuit = mk_circuit_op(
        input_qubits=1,
        input_flows=[x0],
        output_flows=[z0],
        add_ops=_add_ops,
        flows=[FlowAttr.from_states(True, [], 0, 0)],
    )

    gate_chain = _FlowChain(flows=[z0], measurements=[])
    user_chain = _FlowChain(flows=[x0], measurements=[])

    propagations = _GenerateFlows.propagate_flow_chains(
        propagate_by_gates=[gate_chain],
        propagate_by_annotations=[user_chain],
        chain_length=1,
        circuit=circuit,
    )

    end_states = {ch.end_state for ch in propagations}
    # Gate chain: Z0 -> X0 (H maps Z to X)
    assert x0 in end_states
    # User chain: X0 -> Z0 (annotated flow)
    assert z0 in end_states

    # The user-annotated chain should have is_user_flow set
    user_result = [ch for ch in propagations if ch.end_state == z0 and ch.is_user_flow]
    assert len(user_result) == 1
    assert user_result[0].last_user_flow_age == 0


def test_small_repetition_code_flow_generation_and_propagation():
    """Form initial flow chains on 3 qubits and propagate through a repetition code
    with 2 data qubits and an ancilla qubit - i.e. a detecting region.
    """

    def _add_ops(body: Block):
        d0, d1, a0 = body.args

        # Reset ancillas at the start of each round
        body.add_op(qref.ResetOp("Z", [a0]))

        # Parity checks onto ancillas
        body.add_op(qref.GateOp(qcore.CXGateAttr(), [d0, a0]))
        body.add_op(qref.GateOp(qcore.CXGateAttr(), [d1, a0]))

        # Z measurement then reset per ancilla
        body.add_op(qref.MeasureOp("Z", [a0]))
        body.add_op(qref.ResetOp("Z", [a0]))

        # Parity checks onto ancillas
        body.add_op(qref.GateOp(qcore.CXGateAttr(), [d0, a0]))
        body.add_op(qref.GateOp(qcore.CXGateAttr(), [d1, a0]))

        # final Z measurement
        body.add_op(qref.MeasureOp("Z", [a0]))

    # Build circuit with 3 qubits
    circuit = mk_circuit_op(
        input_qubits=3, input_flows=[], output_flows=[], add_ops=_add_ops, flows=None
    )
    # initial flow chains: identity only (no input states provided)
    chains = []

    # Propagate all chains through the repetition code circuit
    # Expect a basis of 3 linearly independent flows: I -> Z0Z1Z2, I -> Z0Z1 (m1), I -> I (m1, m2)
    propagations = _GenerateFlows.propagate_flow_chains(chains, [], 1, circuit)

    # Verify the exact flows
    i = qcore.PauliStringAttr.identity(3)
    z012 = qcore.PauliStringAttr([("Z", 0), ("Z", 1), ("Z", 2)], 3)
    z01 = qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 3)

    assert any(tuple(chain.flows) == (i, z012) for chain in propagations), (
        "Expected I -> Z0Z1Z2 flow"
    )
    assert any(
        tuple(chain.flows) == (i, z01) and len(chain.measurements[0]) == 1 for chain in propagations
    ), "Expected I -> Z0Z1 flow"
    assert any(
        tuple(chain.flows) == (i, i) and len(chain.measurements[0]) == 2 for chain in propagations
    ), "Expected I -> I flow with 2 measurements"


def test_propagate_flow_chains_via_annotations():
    """Test for _GenerateFlows.propagate_flow_chains with annotations.

    Build a fixed circuit with no gates in the body but with flow annotations,
    including flows that end in identity and flows starting from identity.
    Verify that a single-step chain ending in `chain_end` is appended to
    `expected_new_end` via user flows.
    """

    # Define input and output flow state contexts (indices implied by ordering)
    input_flows = [
        qcore.PauliStringAttr([("Z", 0)], 3),
        qcore.PauliStringAttr([("X", 1)], 3),
        qcore.PauliStringAttr([("Z", 2)], 3),
    ]
    output_flows = [
        qcore.PauliStringAttr([("X", 0)], 3),
        qcore.PauliStringAttr([("Z", 1)], 3),
        qcore.PauliStringAttr([("Z", 2)], 3),
    ]

    # Construct flow annotations:
    # + { Z0 -> X0 }
    f1 = FlowAttr.from_states(
        sign=True,
        measurements=[],
        input_state="Z0 : 3",
        output_state="X0 : 3",
        input_state_context=input_flows,
        output_state_context=output_flows,
    )

    # + { X1 -> I } (destruction flow)
    idx_x1 = input_flows.index(qcore.PauliStringAttr([("X", 1)], 3))
    f2 = FlowAttr.from_states(True, [], idx_x1, qcore.I_STATE_INDEX)

    # + { I -> Z2 } (creation flow)
    idx_z2_out = output_flows.index(qcore.PauliStringAttr([("Z", 2)], 3))
    f3 = FlowAttr.from_states(True, [], qcore.I_STATE_INDEX, idx_z2_out)

    # Build a circuit with no gates in the body, but with the above flows
    def _add_ops_noop(body: Block):
        # No operations added; body remains empty and yields no measurements
        pass

    circuit = mk_circuit_op(
        input_qubits=3,
        input_flows=input_flows,
        output_flows=output_flows,
        add_ops=_add_ops_noop,
        flows=[f1, f2, f3],
    )

    # Propagate these test chains (identity is implicitly propagated)
    chains_to_propagate = [
        _FlowChain(flows=[qcore.PauliStringAttr([("Z", 0)], 3)], measurements=[]),
        _FlowChain(flows=[qcore.PauliStringAttr([("X", 1)], 3)], measurements=[]),
    ]
    expected_chains = [
        _FlowChain(
            flows=[qcore.PauliStringAttr([("Z", 0)], 3), qcore.PauliStringAttr([("X", 0)], 3)],
            measurements=[MMTResults()],
            last_user_flow_age=0,
        ),
        _FlowChain(
            flows=[qcore.PauliStringAttr.identity(3), qcore.PauliStringAttr([("Z", 2)], 3)],
            measurements=[MMTResults()],
            last_user_flow_age=0,
        ),
        _FlowChain(
            flows=[qcore.PauliStringAttr([("X", 1)], 3), qcore.PauliStringAttr.identity(3)],
            measurements=[MMTResults()],
            last_user_flow_age=0,
        ),
    ]

    # Propagate via user flows and verify appended end state
    out = _GenerateFlows.propagate_flow_chains([], chains_to_propagate, 1, circuit)
    assert out == expected_chains


@pytest.mark.parametrize(
    ("chain_ends", "expected_output_flow_states"),
    [
        # Z0 -> Z0 and Z0 -> I expected (propagation via gates only)
        ([[("Z", 0)]], [[("Z", 0)], []]),
        # X0 Z1 and X0 Z2 both blocked so expect Z1 Z2 -> Z0 Z1 Z2 (with mmt)
        # and Z1 Z2 -> Z1 Z2 (no mmt)
        # which gets reduced to Z1 Z2 -> Z1 Z2 and I -> Z0
        (
            [[("X", 0), ("Z", 1)], [("X", 0), ("Z", 2)]],
            [[("Z", 1), ("Z", 2)], [("Z", 0)]],
        ),
    ],
)
def test_propagate_flows_no_user_annotations(chain_ends, expected_output_flow_states):
    """Test _GenerateFlows.propagate_flows with no user annotations.

    Should behave identically to gate-based propagation.
    """

    def _add_ops(body: Block):
        q0, _, _ = body.args
        body.add_op(qref.MeasureOp("Z", [q0]))

    circuit = mk_circuit_op(
        input_qubits=3, input_flows=[], output_flows=[], add_ops=_add_ops, flows=[]
    )
    chain_list = [
        _FlowChain(flows=[qcore.PauliStringAttr(chain_end, 3)], measurements=[])
        for chain_end in chain_ends
    ]

    propagations = _GenerateFlows.propagate_flows(chain_list, 1, circuit)
    output_flows = {f.end_state for f in propagations}
    assert output_flows == {
        qcore.PauliStringAttr(state, 3) for state in expected_output_flow_states
    }


@pytest.mark.parametrize(
    ("chain_end", "permutation", "expected_end"),
    [
        ([("Z", 0)], [0], [("Z", 0)]),
        ([("Z", 0)], [1, 0], [("Z", 1)]),
        ([("Z", 0), ("X", 1)], [1, 0], [("Z", 1), ("X", 0)]),
    ],
)
def test_propagate_flows_through_permute(chain_end, permutation, expected_end):
    q0 = qcore.AllocQubitOp(qcore.QubitType()).result[0]
    state_make = StateMakeOp([q0], StateType(1, qcore.QubitType(), []))
    permute = StatePermuteOp(state_make.output, permutation)

    chain = _FlowChain(flows=[qcore.PauliStringAttr(chain_end, 2)])
    expected_chain = _FlowChain(
        flows=[qcore.PauliStringAttr(chain_end, 2), qcore.PauliStringAttr(expected_end, 2)],
        measurements=[MMTResults()],
    )

    propagations = _GenerateFlows.propagate_flows_through_permute([chain], permute)
    assert propagations == [expected_chain]


def test_trivially_extend_flow_chains():
    chain = _FlowChain(
        flows=[qcore.PauliStringAttr([("Z", 0)], 2), qcore.PauliStringAttr([("X", 1)], 2)],
        measurements=[MMTResults()],
    )
    expected_chain = _FlowChain(
        flows=[
            qcore.PauliStringAttr([("Z", 0)], 2),
            qcore.PauliStringAttr([("X", 1)], 2),
            qcore.PauliStringAttr([("X", 1)], 2),
        ],
        measurements=[MMTResults(), MMTResults()],
    )
    assert _GenerateFlows.trivially_extend_flow_chains([chain]) == [expected_chain]
    assert len(chain) == 2  # original chain should not be mutated


@pytest.mark.parametrize(
    (
        "non_matching_specs",
        "unmatched_input_specs",
        "expected_gates_specs",
        "expected_user_specs",
    ),
    [
        # Case A: 3 non-user chains, 1 unmatched input.
        # Non-matching chains: X0, X1, X2
        # Unmatched inputs: X0 X1 (needs product of X0 and X1)
        # Expect: user products {X0 X1}; gates continue 2 leftover: {X0, X2}
        (
            [[("X", 0)], [("X", 1)], [("X", 2)]],
            [
                [("X", 0), ("X", 1)],
            ],
            [[("X", 0)], [("X", 2)]],
            [[("X", 0), ("X", 1)]],
        ),
        # Case B: overlapping products using shared chain.
        # Non-matching chains: X0, X1, X2
        # Unmatched inputs: X0 X2 and X1 X2
        # Expect: user products {X0 X2, X1 X2}; gates continue one leftovers: {X0}
        (
            [[("X", 0)], [("X", 1)], [("X", 2)]],
            [[("X", 0), ("X", 2)], [("X", 1), ("X", 2)]],
            [[("X", 0)]],
            [[("X", 0), ("X", 2)], [("X", 1), ("X", 2)]],
        ),
    ],
)
def test_match_to_user_by_multiplication_parametrized(
    non_matching_specs, unmatched_input_specs, expected_gates_specs, expected_user_specs
):
    """Parametrized tests for matching unmatched inputs by multiplying non-matching chains.

    Verifies that the correct split of chains to propagate via gates vs. user flows
    is returned, including scenarios where leftover non-user chains are continued.
    """

    non_matching = [
        _FlowChain(flows=[qcore.PauliStringAttr(spec, 3)], measurements=[])
        for spec in non_matching_specs
    ]
    unmatched_inputs = [qcore.PauliStringAttr(spec, 3) for spec in unmatched_input_specs]

    gates_list, user_list = _GenerateFlows.match_to_user_by_multiplication(
        non_matching, [], unmatched_inputs
    )

    user_end_states = {ch.end_state for ch in user_list}
    gates_end_states = {ch.end_state for ch in gates_list}

    assert user_end_states == {qcore.PauliStringAttr(spec, 3) for spec in expected_user_specs}
    assert gates_end_states == {qcore.PauliStringAttr(spec, 3) for spec in expected_gates_specs}


@pytest.mark.parametrize(
    (
        "non_matching_specs",
        "unmatched_input_specs",
        "expected_gates_specs",
        "expected_user_specs",
        "expected_warning_substrings",
    ),
    [
        # Case 1: flow chains ending in X0 and X1; user inputs include Z0 and X1
        # X1 is matched directly, leaving Z0 unmatched. Expect warning mentioning Z0.
        (
            [[("X", 0)], [("X", 1)]],
            [[("Z", 0)], [("X", 1)]],
            [[("X", 0)]],  # only X0 continues via gates; X1 matched by user
            [[("X", 1)]],
            ["Z0"],
        ),
        # Case 2: chains ending in X0 X1 and Z0 Z1; user inputs are Y0 and Y1
        # Neither Y0 nor Y1 can be formed; expect a warning mentioning both.
        (
            [[("X", 0), ("X", 1)], [("Z", 0), ("Z", 1)]],
            [[("Y", 0)], [("Y", 1)]],
            [[("X", 0), ("X", 1)], [("Z", 0), ("Z", 1)]],
            [],
            ["Y0", "Y1"],
        ),
    ],
)
def test_match_to_user_by_multiplication_warns_unmatched_inputs(
    non_matching_specs,
    unmatched_input_specs,
    expected_gates_specs,
    expected_user_specs,
    expected_warning_substrings,
):
    """Ensure a UserWarning is emitted when unmatched user inputs cannot be formed
    from non-matching chains, and verify the returned chain splits.

    This targets the warning path in `_GenerateFlows.match_to_user_by_multiplication`.
    """

    non_matching = [
        _FlowChain(flows=[qcore.PauliStringAttr(spec, 2)], measurements=[])
        for spec in non_matching_specs
    ]
    unmatched_inputs = [qcore.PauliStringAttr(spec, 2) for spec in unmatched_input_specs]

    # Compose the expected warning message substring for match
    msg = (
        "Cannot find flows ending with flow states "
        + ", ".join(
            str(qcore.PauliStringAttr(spec, 2))
            for spec in unmatched_input_specs
            if spec not in expected_user_specs
        )
        + ". These are not continued in the generation of flows."
    )
    with pytest.warns(UserWarning, match=msg) as record:
        gates_list, user_list = _GenerateFlows.match_to_user_by_multiplication(
            non_matching, [], unmatched_inputs
        )

    # Verify warning(s) mention the expected substrings (e.g., "Z0", "Y0", "Y1").
    assert len(record) >= 1
    msg = str(record[0].message)
    for sub in expected_warning_substrings:
        assert sub in msg

    user_end_states = {ch.end_state for ch in user_list}
    gates_end_states = {ch.end_state for ch in gates_list}

    assert user_end_states == {qcore.PauliStringAttr(spec, 2) for spec in expected_user_specs}
    assert gates_end_states == {qcore.PauliStringAttr(spec, 2) for spec in expected_gates_specs}


def _mk_chain(spec: list[tuple[str, int]], num_qubits: int, is_user: bool = False) -> _FlowChain:
    """Helper to make a two-step _FlowChain with optional user flag."""
    # Cast the Pauli tag to the expected Literal type to keep type-checkers happy.
    typed_spec = [(cast("PauliLiteral", p), i) for (p, i) in spec]

    return _FlowChain(
        flows=[
            qcore.PauliStringAttr.identity(num_qubits),
            qcore.PauliStringAttr(typed_spec, num_qubits),
        ],
        measurements=[MMTResults()],
        last_user_flow_age=0 if is_user else None,
    )


def test_match_to_user_by_multiplication_with_matching_chains_simple():
    """When matching_chains include a user-matched input, combinations may use it
    together with a non-matching chain to form an unmatched input.

    Setup: matching=X0 (user), non-matching=X2, unmatched input is X0 X2.
    Expect: product X0 X2 added to user propagation; no leftover gates propagation.
    """

    non_matching = [_mk_chain([("X", 2)], 3)]
    matching = [_mk_chain([("X", 0)], 3, is_user=True)]
    unmatched_inputs = [qcore.PauliStringAttr([("X", 0), ("X", 2)], 3)]

    gates_list, user_list = _GenerateFlows.match_to_user_by_multiplication(
        non_matching, matching, unmatched_inputs
    )

    user_end_states = {ch.end_state for ch in user_list}
    gates_end_states = {ch.end_state for ch in gates_list}

    assert user_end_states == {qcore.PauliStringAttr([("X", 0), ("X", 2)], 3)}
    assert gates_end_states == set()


def test_match_to_user_by_multiplication_with_matching_chains_overlap_and_leftover():
    """If multiple unmatched inputs are matched using non-matching chains,
    the function may retain a leftover youngest non-user chain for gate propagation.

    Setup: matching=X0 (user), non-matching=X1, X2; unmatched input is X1 X2.
    Expect: user_list contains X1 X2; exactly one leftover in gates_list (either X1 or X2).
    """

    non_matching = [_mk_chain([("X", 1)], 3), _mk_chain([("X", 2)], 3)]
    matching = [_mk_chain([("X", 0)], 3, is_user=True)]
    unmatched_inputs = [qcore.PauliStringAttr([("X", 1), ("X", 2)], 3)]

    gates_list, user_list = _GenerateFlows.match_to_user_by_multiplication(
        non_matching, matching, unmatched_inputs
    )

    user_end_states = {ch.end_state for ch in user_list}
    gates_end_states = {ch.end_state for ch in gates_list}

    assert user_end_states == {qcore.PauliStringAttr([("X", 1), ("X", 2)], 3)}
    # One leftover chain (youngest by age) should remain; it's either X1 or X2
    assert len(gates_end_states) == 1
    assert gates_end_states.issubset(
        {qcore.PauliStringAttr([("X", 1)], 3), qcore.PauliStringAttr([("X", 2)], 3)}
    )


def test_match_to_user_by_multiplication_with_matching_chains_multiple_rows():
    """Matching chains can be reused across multiple unmatched inputs.

    Setup: matching=X1 (user), non-matching=X0 and X2; unmatched inputs are X0 X1 and X1 X2.
    Expect: user_list contains both products; no leftover gates propagation.
    """

    non_matching = [_mk_chain([("X", 0)], 3), _mk_chain([("X", 2)], 3)]
    matching = [_mk_chain([("X", 1)], 3, is_user=True)]
    unmatched_inputs = [
        qcore.PauliStringAttr([("X", 0), ("X", 1)], 3),
        qcore.PauliStringAttr([("X", 1), ("X", 2)], 3),
    ]

    gates_list, user_list = _GenerateFlows.match_to_user_by_multiplication(
        non_matching, matching, unmatched_inputs
    )

    user_end_states = {ch.end_state for ch in user_list}
    gates_end_states = {ch.end_state for ch in gates_list}

    assert user_end_states == {
        qcore.PauliStringAttr([("X", 0), ("X", 1)], 3),
        qcore.PauliStringAttr([("X", 1), ("X", 2)], 3),
    }
    assert gates_end_states == set()


def test_match_to_user_by_multiplication_preserves_user_flow():
    """When a matching (last_user_flow_age=0) chain participates in a product to form
    an unmatched user input, the matching chain itself must still be preserved and
    propagated via user annotations.

    Setup:
    - matching=X0 (user), non-matching X2
    - unmatched input includes X0 X2
    Expect:
    - propagate_flows returns chains appended via user flows for both X0 and X0 X2
    (i.e., matching chain preserved and product chain added).
    """

    # Provide chains: matching X0 (user) and non-matching X2
    c1 = _mk_chain([("X", 0)], 3, is_user=True)
    c2 = _mk_chain([("X", 2)], 3, is_user=False)
    chain_list = [c1, c2]

    out_chains_gates, out_chains_user = _GenerateFlows.match_to_user_by_multiplication(
        non_matching_chains=chain_list,
        matching_chains=[],
        unmatched_inputs=[qcore.PauliStringAttr([("X", 0), ("X", 2)], 3)],
    )

    assert out_chains_gates == [c1]
    assert out_chains_user == [c1 * c2]


@pytest.mark.parametrize(
    ("chain_ends", "expected_ends", "annotated_flows"),
    [
        (
            [[("X", 0)], [("Z", 0)]],
            [[("X", 0)], [("Z", 0)]],
            [[("X", 0)], [("Z", 0)]],
        ),
        (
            [[("X", 0)], [("Z", 0)]],
            [[("Z", 0)], [("Y", 0)]],
            [[("Y", 0)], [("Y", 0)]],
        ),
    ],
)
def test_propagate_flows_circuit_1(chain_ends, expected_ends, annotated_flows):
    """Test propagate user flows with partial user flow annotations on circuit op.
    Circuit 1: H gate with flow X -> Z annotated"""
    # Build a 1-qubit circuit: apply H on q0. Annotate user flow given.

    f = FlowAttr.from_states(True, [], 0, 0)

    def _add_ops(body: Block):
        (q0,) = body.args
        body.add_op(qref.GateOp(qcore.HGateAttr(), [q0]))

    circuit = mk_circuit_op(
        input_qubits=1,
        input_flows=[annotated_flows[0]],
        output_flows=[annotated_flows[1]],
        add_ops=_add_ops,
        flows=[f],
    )

    chain_list = [
        _FlowChain(flows=[qcore.PauliStringAttr(spec, 1)], measurements=[]) for spec in chain_ends
    ]

    out_flows = _GenerateFlows.propagate_flows(chain_list, 1, circuit)
    end_states = {ch.end_state for ch in out_flows}
    assert end_states == {qcore.PauliStringAttr(spec, 1) for spec in expected_ends}


def test_propagate_flow_chains_over_c1_with_user_i_to_z1_and_annotated_z0z1_to_z0z1():
    """Propagate a seed basis over a 2-qubit MZ+MZ circuit ("c1") with a
    pre-specified user flow Z0Z1->Z0Z1.

    Seed chain list (all length-2):
      - I -> I
      - I -> Z0
      - I -> Z1   (marked as user flow chain with last_user_flow_age=0)

    Expectations:
      - Z0 and Z1 should survive two Z measurements (they commute), and Z0Z1 is
        introduced via the user-annotated fixed-point flow.
      - The user flag on the Z1 seed chain should be preserved on its propagated output.
      - Reduction should keep the Z0 Z1 and Z0 branches because they're user flows and the Z1 branch
        should be reduced to a destruction flow.
    """

    def _add_two_mz(body: Block):
        q0, q1 = body.args
        body.add_op(qref.MeasureOp("Z", [q0]))
        body.add_op(qref.MeasureOp("Z", [q1]))

    circuit = mk_circuit_op(
        input_qubits=2,
        input_flows=[[("Z", 0), ("Z", 1)], [("Z", 1)]],
        output_flows=[[("Z", 0), ("Z", 1)], [("Z", 0)], [("Z", 1)]],
        add_ops=_add_two_mz,
        flows=[
            # Z0Z1 -> Z0Z1 annotated on c1.
            FlowAttr.from_states(True, [], 0, 0),
        ],
    )

    # Seed chains: I->Z0, I->Z1 (user).
    seed_chains = [
        _FlowChain(
            flows=[qcore.PauliStringAttr.identity(2), qcore.PauliStringAttr([("Z", 0)], 2)],
            measurements=[MMTResults()],
        ),
        _FlowChain(
            flows=[qcore.PauliStringAttr.identity(2), qcore.PauliStringAttr([("Z", 1)], 2)],
            measurements=[MMTResults()],
            last_user_flow_age=0,
        ),
    ]
    propagated = _GenerateFlows.propagate_flows(seed_chains, 2, circuit)
    prop_flows = [prop.flows for prop in propagated]

    end_states = {ch.end_state for ch in propagated}
    assert qcore.PauliStringAttr([("Z", 0)], 2) in end_states
    assert qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 2) in end_states
    assert qcore.PauliStringAttr.identity(2) in end_states  # one destruction flow

    # Check explicitly for the expected destruction flow
    assert [
        qcore.PauliStringAttr.identity(2),
        qcore.PauliStringAttr([("Z", 1)], 2),
        qcore.PauliStringAttr.identity(2),
    ] in prop_flows


def test_propagate_flow_chains_single_blocked_chain_returns_empty():
    """Chain blocked by a measurement: should return just the creation flow from that
    measurement."""

    def _add_ops(body: Block):
        (q0,) = body.args
        body.add_op(qref.MeasureOp("Z", [q0]))

    circuit = mk_circuit_op(
        input_qubits=1, input_flows=[], output_flows=[], add_ops=_add_ops, flows=[]
    )

    chain_list = [
        _FlowChain(flows=[qcore.PauliStringAttr([("X", 0)], 1)], measurements=[]),
    ]

    result = _GenerateFlows.propagate_flow_chains(chain_list, [], 1, circuit)
    assert len(result) == 1
    assert result[0].flows == [
        qcore.PauliStringAttr.identity(1),
        qcore.PauliStringAttr([("Z", 0)], 1),
    ]


# region Tests for writing flows


def test_format_flow_chain_list_filters_out_of_range() -> None:
    """_StateUseDefChain._format_flow_chain_list returns only chains that have an entry at the
    circuit index."""
    i = qcore.PauliStringAttr.identity(1)
    x0 = qcore.PauliStringAttr([("X", 0)], 1)

    # chain length 2 => only index 0 is valid
    chain_short = _FlowChain(flows=[i, x0], measurements=[MMTResults()])
    # chain length 3 => indices 0 and 1 valid
    chain_long = _FlowChain(flows=[i, i, x0], measurements=[MMTResults(), MMTResults()])

    # idx=0 should include both chains
    flows_idx0 = _StateUseDefChain._format_flow_chain_list([chain_short, chain_long], 0)
    assert flows_idx0 == [
        CircuitFlowData(i, x0, MMTResults()),
        CircuitFlowData(i, i, MMTResults()),
    ]
    # idx=1 should include only chain_long
    flows_idx1 = _StateUseDefChain._format_flow_chain_list([chain_short, chain_long], 1)
    assert flows_idx1 == [CircuitFlowData(i, x0, MMTResults())]


def test_update_from_flow_chains_updates_only_matching_indices():
    """_StateUseDefChain.update_from_flow_chains uses format_flow_chain_list per circuit index."""
    iden = qcore.PauliStringAttr.identity(1)
    x0 = qcore.PauliStringAttr([("X", 0)], 1)

    q0 = qcore.AllocQubitOp(results=[qcore.QubitType()]).result[0]
    make = StateMakeOp([q0], StateType(1, qcore.QubitType(), ArrayAttr([])))

    def _add_ops(body: Block):
        (q0,) = body.args
        body.add_op(qref.MeasureOp("Z", [q0]))

    producer = mk_circuit_op(
        input_qubits=1,
        input_flows=[],
        output_flows=[],
        add_ops=lambda _: None,
        flows=[],
        input_state=make.output,
    )

    adapter = mk_circuit_op(
        input_qubits=1,
        input_flows=[],
        output_flows=[],
        add_ops=lambda _: None,
        flows=[],
        input_state=producer.output,
    )

    # Two consumer circuits; only the first should get an update from the chain.
    c0 = mk_circuit_op(
        input_qubits=1,
        input_flows=[],
        output_flows=[],
        add_ops=_add_ops,
        flows=[],
        input_state=adapter.output,
    )
    c1 = mk_circuit_op(
        input_qubits=1,
        input_flows=[],
        output_flows=[],
        add_ops=_add_ops,
        flows=[],
        input_state=c0.output,
    )

    m1 = c0.yield_op.measurements[0]

    chain = _FlowChain(
        flows=[iden, iden, x0, x0],
        measurements=[MMTResults(), MMTResults(), MMTResults([m1])],
    )

    use_def_chain = _StateUseDefChain(make)
    use_def_chain.append(producer.output)
    use_def_chain.append(adapter.output)
    use_def_chain.append(c0.output)
    use_def_chain.append(c1.output)

    use_def_chain.update_from_flow_chains([chain], PatternRewriter(c0.yield_op))

    assert len(cast(ArrayAttr[FlowAttr], c0.flows).data) == 1
    # c1 should remain unchanged (no flow at idx=1 for a length-2 chain).
    assert cast(ArrayAttr[FlowAttr], c1.flows).data == ()


def test_generate_flows_pass_simple_three_circuits():
    """End-to-end test exercising the pass over three consecutive circuits.

    Pipeline:
        c0: MX(q0)
        c1: H(q0) with a pre-annotated flow X -> Z (no measurements)
        c2: MZ(q0)

    Assertions are phrased in terms of the resulting per-circuit flow annotations.
    """

    x0 = qcore.PauliStringAttr([("X", 0)], 1)
    z0 = qcore.PauliStringAttr([("Z", 0)], 1)

    q0 = qcore.AllocQubitOp(results=[qcore.QubitType()]).result[0]
    make = StateMakeOp([q0], StateType(1, qcore.QubitType(), ArrayAttr([])))

    # c0: MX
    def _add_mx(body: Block):
        (q0,) = body.args
        body.add_op(qref.MeasureOp("X", [q0]))

    c0 = mk_circuit_op(
        input_qubits=1,
        input_flows=[],
        output_flows=[x0],
        add_ops=_add_mx,
        flows=[],
        input_state=make.output,
    )

    # c1: H, pre-annotated with a flow X -> Z.
    # This still exercises “some pre-annotated flows exist” while avoiding
    # adding anti-commuting flow states (X and Z) to the same StateType.
    def _add_h(body: Block):
        (q0,) = body.args
        body.add_op(qref.GateOp(qcore.HGateAttr(), [q0]))

    c1 = mk_circuit_op(
        input_qubits=1,
        input_flows=[x0],
        output_flows=[z0],
        add_ops=_add_h,
        flows=[FlowAttr(sign="+", measurements=[], input_state=0, output_state=0)],
        input_state=c0.output,
    )

    # c2: MZ
    def _add_mz(body: Block):
        (q0,) = body.args
        body.add_op(qref.MeasureOp("Z", [q0]))

    c2 = mk_circuit_op(
        input_qubits=1,
        input_flows=[],
        output_flows=[],
        add_ops=_add_mz,
        flows=[],
        input_state=c1.output,
    )

    use_def_chain = _StateUseDefChain(make)
    use_def_chain.append(c0.output)
    use_def_chain.append(c1.output)
    use_def_chain.append(c2.output)

    # Run the generation + write logic over the chain.
    flow_chains_to_write = _GenerateFlows.find_flow_chains_for_use_def_chain(use_def_chain)
    use_def_chain.update_from_flow_chains(flow_chains_to_write, PatternRewriter(c0.yield_op))

    def _flow_index_pairs(c: CircuitOp) -> set[tuple[int, int]]:
        return {
            (f.input_state_index, f.output_state_index)
            for f in cast(ArrayAttr[FlowAttr], c.flows).data
        }

    # First circuit (MX): expect at least I->X (and possibly I->I depending on
    # chain filtering/normalisation).
    assert (qcore.I_STATE_INDEX, 0) in _flow_index_pairs(c0)

    # Second circuit (H): expect only the pre-annotated X->Z.
    assert _flow_index_pairs(c1) == {(0, 0)}

    # Third circuit (MZ): expect Z->I and I->Z.
    assert _flow_index_pairs(c2) == {
        (0, qcore.I_STATE_INDEX),
        (qcore.I_STATE_INDEX, 0),
    }


def test_generate_flows_pass_matches_filecheck_mlir_example():
    """Translate the lit/FileCheck MLIR example into Python IR construction.

    This matches the structure of the FileCheck test:
    - circuit 0: parallel reset Z on 2 qubits, with user flow I -> Z1
    - circuit 1: two Z measurements, with user flow Z0Z1 -> Z0Z1

    It uses the same helper constructors as other tests in this file so you can
    drop breakpoints and inspect the intermediate CircuitOps and flow chains.
    """

    q0, q1 = qcore.AllocQubitOp(results=[qcore.QubitType(), qcore.QubitType()]).result
    make = StateMakeOp([q0, q1], StateType(2, qcore.QubitType(), ArrayAttr([])))

    # Circuit 0: parallel reset Z on two qubits.
    def _add_parallel_resets(body: Block):
        q0, q1 = body.args
        r0 = Block([qref.ResetOp("Z", [q0])])
        r1 = Block([qref.ResetOp("Z", [q1])])
        body.add_op(qstruct.ParallelOp(result_types=[], par_regions=[Region(r0), Region(r1)]))

    c0 = mk_circuit_op(
        input_qubits=2,
        input_flows=[],
        output_flows=[[("Z", 0), ("Z", 1)], [("Z", 1)]],
        add_ops=_add_parallel_resets,
        flows=[
            # I -> Z1 (identity input is implicit and always present).
            FlowAttr.from_states(True, [], qcore.I_STATE_INDEX, 1),
        ],
        input_state=make.output,
    )

    # Circuit 1: measure Z on each qubit.
    def _add_two_mz(body: Block):
        q0, q1 = body.args
        body.add_op(qref.MeasureOp("Z", [q0]))
        body.add_op(qref.MeasureOp("Z", [q1]))

    c1 = mk_circuit_op(
        input_qubits=2,
        input_flows=[[("Z", 0), ("Z", 1)], [("Z", 1)]],
        # Include the additional output context states required for the flows we
        # want to assert on.
        output_flows=[[("Z", 0), ("Z", 1)], [("Z", 0)], [("Z", 1)]],
        add_ops=_add_two_mz,
        flows=[
            # Z0Z1 -> Z0Z1
            FlowAttr.from_states(True, [], 0, 0),
        ],
        input_state=c0.output,
    )

    use_def_chain = _StateUseDefChain(make)
    use_def_chain.append(c0.output)
    use_def_chain.append(c1.output)

    # Run the generation + write logic over the chain.
    flow_chains_to_write = _GenerateFlows.find_flow_chains_for_use_def_chain(use_def_chain)
    use_def_chain.update_from_flow_chains(flow_chains_to_write, PatternRewriter(c0.yield_op))

    def _flow_index_pairs(c: CircuitOp) -> set[tuple[int, int]]:
        assert c.flows is not None
        return {
            (f.input_state_index, f.output_state_index)
            for f in cast(ArrayAttr[FlowAttr], c.flows).data
        }

    # Current behaviour: circuit 0 gains additional flows inferred from the reset
    # semantics and the declared output flow-state context.
    # We assert at least the user-provided I->Z1 plus the additional inferred I->Z0Z1.
    assert list(c0.output_flows) == [
        qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 2),
        qcore.PauliStringAttr([("Z", 1)], 2),
    ]
    assert {(qcore.I_STATE_INDEX, 0), (qcore.I_STATE_INDEX, 1)} == _flow_index_pairs(c0)

    # Check circuit 1's output flow-state context has the expected 3 states in order.
    assert list(c1.output_flows) == [
        qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 2),
        qcore.PauliStringAttr([("Z", 0)], 2),
        qcore.PauliStringAttr([("Z", 1)], 2),
    ]

    # Then assert the expected flows are present by index pairs.
    # Input context indices (as constructed above):
    #   0: Z0Z1
    #   1: Z1
    # Output context indices (asserted above):
    #   0: Z0Z1
    #   1: Z0
    #   2: Z1
    expected_pairs_c1 = {
        (qcore.I_STATE_INDEX, 1),  # I -> Z0
        (0, 0),  # Z0 Z1 -> Z0 Z1
        (1, qcore.I_STATE_INDEX),  # Z1 -> I
    }
    assert expected_pairs_c1 == _flow_index_pairs(c1)


def test_generate_flows_edge_case_user_flow_blocked_by_measurement():
    """Test the following edge case where a user flow is blocked by a measurement.

    Pipeline:
        c0: RZ(q0), annotated flow I -> Z0
        c1: MX(q0)

    Should raise a descriptive BadUserFlowError.
    """
    z0 = qcore.PauliStringAttr([("Z", 0)], 1)

    q0 = qcore.AllocQubitOp(results=[qcore.QubitType()]).result[0]
    make = StateMakeOp([q0], StateType(1, qcore.QubitType(), ArrayAttr([])))

    # c0: Reset Z with user flow I -> Z0
    def _add_reset(body: Block):
        (q0,) = body.args
        body.add_op(qref.ResetOp("Z", [q0]))

    c0 = mk_circuit_op(
        input_qubits=1,
        input_flows=[],
        output_flows=[z0],
        add_ops=_add_reset,
        flows=[FlowAttr.from_states(True, [], qcore.I_STATE_INDEX, 0)],
        input_state=make.output,
    )

    # c1: MX (blocks Z0 since Z and X anticommute)
    def _add_mx(body: Block):
        (q0,) = body.args
        body.add_op(qref.MeasureOp("X", [q0]))

    c1 = mk_circuit_op(
        input_qubits=1,
        input_flows=[z0],
        output_flows=[],
        add_ops=_add_mx,
        flows=[],
        input_state=c0.output,
    )

    use_def_chain = _StateUseDefChain(make)
    use_def_chain.append(c0.output)
    use_def_chain.append(c1.output)

    with pytest.raises(
        BadUserFlowError,
        match=re.escape(
            "User flow chain(s) [Z0] failed to propagate through the current circuit independently."
        ),
    ):
        _GenerateFlows.find_flow_chains_for_use_def_chain(use_def_chain)


def test_generate_flows_edge_case_user_flow_blocked_by_reset():
    """Test the following edge case where a user flow is blocked by a reset.

    Pipeline:
        c0: RZ(q0), annotated flow I -> Z0
        c1: RZ(q0)

    Should raise a descriptive BadUserFlowError.
    """
    z0 = qcore.PauliStringAttr([("Z", 0)], 1)

    q0 = qcore.AllocQubitOp(results=[qcore.QubitType()]).result[0]
    make = StateMakeOp([q0], StateType(1, qcore.QubitType(), ArrayAttr([])))

    # c0: Reset Z with user flow I -> Z0
    def _add_reset(body: Block):
        (q0,) = body.args
        body.add_op(qref.ResetOp("Z", [q0]))

    c0 = mk_circuit_op(
        input_qubits=1,
        input_flows=[],
        output_flows=[z0],
        add_ops=_add_reset,
        flows=[FlowAttr.from_states(True, [], qcore.I_STATE_INDEX, 0)],
        input_state=make.output,
    )

    # c1: RZ (blocks Z0 since it's non-identity)
    c1 = mk_circuit_op(
        input_qubits=1,
        input_flows=[z0],
        output_flows=[],
        add_ops=_add_reset,
        flows=[],
        input_state=c0.output,
    )

    use_def_chain = _StateUseDefChain(make)
    use_def_chain.append(c0.output)
    use_def_chain.append(c1.output)

    with pytest.raises(
        BadUserFlowError,
        match=re.escape(
            "User flow chain(s) [Z0] failed to propagate through the current circuit independently."
        ),
    ):
        _GenerateFlows.find_flow_chains_for_use_def_chain(use_def_chain)


def test_generate_flows_edge_case_unblocking_disrupts_user_flow_1():
    """Test that a user flow which would need to be multiplied out to unblock raises an error.

    Pipeline:
        c0: RZ(q1) - creates Z1
        c1: RY(q0) - creates Y0
        c2: identity, annotated flow Z1 -> Z1
        c3: CX(q0, q1), MX(q0)

    After CX, there are two flow chains blocked on MX(q0):
        1. I -> Z1 -> Z1 -> Z1 -> Z0 Z1 (where the second Z1 -> Z1 is the user flow link)
        2. I -> I  -> Y0 -> Y0 -> Y0 X1
    Unblocking requires multiplying them together, but this would disrupt both ends of the user flow
    link. So we should raise BadUserFlowError.
    """
    z1 = qcore.PauliStringAttr([("Z", 1)], 2)

    q0, q1 = qcore.AllocQubitOp(results=[qcore.QubitType(), qcore.QubitType()]).result
    make = StateMakeOp([q0, q1], StateType(2, qcore.QubitType(), ArrayAttr([])))

    # c0: Reset Z on q1
    def _add_reset_z_q1(body: Block):
        _, q1 = body.args
        body.add_op(qref.ResetOp("Z", [q1]))

    c0 = mk_circuit_op(
        input_qubits=2,
        input_flows=[],
        output_flows=[],
        add_ops=_add_reset_z_q1,
        flows=[],
        input_state=make.output,
    )

    # c1: Reset Y on q0
    def _add_reset_y_q0(body: Block):
        q0, _ = body.args
        body.add_op(qref.ResetOp("Y", [q0]))

    c1 = mk_circuit_op(
        input_qubits=2,
        input_flows=[],
        output_flows=[z1],
        add_ops=_add_reset_y_q0,
        flows=[],
        input_state=c0.output,
    )

    # c2: identity with user flow Z1 -> Z1
    c2 = mk_circuit_op(
        input_qubits=2,
        input_flows=[z1],
        output_flows=[z1],
        add_ops=lambda _: None,
        flows=[FlowAttr.from_states(True, [], 0, 0)],
        input_state=c1.output,
    )

    # c3: CX(q0, q1) then MX(q0)
    def _add_cx_mx(body: Block):
        q0, q1 = body.args
        body.add_op(qref.GateOp(qcore.CXGateAttr(), [q0, q1]))
        body.add_op(qref.MeasureOp("X", [q0]))

    c3 = mk_circuit_op(
        input_qubits=2,
        input_flows=[z1],
        output_flows=[],
        add_ops=_add_cx_mx,
        flows=[],
        input_state=c2.output,
    )

    use_def_chain = _StateUseDefChain(make)
    use_def_chain.append(c0.output)
    use_def_chain.append(c1.output)
    use_def_chain.append(c2.output)
    use_def_chain.append(c3.output)

    with pytest.raises(
        BadUserFlowError,
        match=re.escape(
            "User-derived flow chain ending with Z1 cannot propagate through the current circuit."
        ),
    ):
        _GenerateFlows.find_flow_chains_for_use_def_chain(use_def_chain)


def test_generate_flows_edge_case_unblocking_disrupts_user_flow_2():
    """Same as above, except the unblocking only disrupts the right-hand end of the user flow link.

    Pipeline:
        c0: RZ(q1) - creates Z1
        c1: RY(q0) - creates Y0, annotated flow Z1 -> Z1
        c2: CX(q0, q1), MX(q0)

    After CX, there are two flow chains blocked on MX(q0):
        1. I -> Z1 -> Z1 -> Z0 Z1 (where the Z1 -> Z1 is the user flow link)
        2. I -> I  -> Y0 -> Y0 X1
    Unblocking requires multiplying them together, but this would disrupt the right-hand end of the
    user flow link. So we should raise BadUserFlowError.
    """
    z1 = qcore.PauliStringAttr([("Z", 1)], 2)

    q0, q1 = qcore.AllocQubitOp(results=[qcore.QubitType(), qcore.QubitType()]).result
    make = StateMakeOp([q0, q1], StateType(2, qcore.QubitType(), ArrayAttr([])))

    # c0: Reset Z on q1
    def _add_reset_z_q1(body: Block):
        _, q1 = body.args
        body.add_op(qref.ResetOp("Z", [q1]))

    c0 = mk_circuit_op(
        input_qubits=2,
        input_flows=[],
        output_flows=[z1],
        add_ops=_add_reset_z_q1,
        flows=[],
        input_state=make.output,
    )

    # c1: Reset Y on q0, user flow Z1 -> Z1
    def _add_reset_y_q0(body: Block):
        q0, _ = body.args
        body.add_op(qref.ResetOp("Y", [q0]))

    c1 = mk_circuit_op(
        input_qubits=2,
        input_flows=[z1],
        output_flows=[z1],
        add_ops=_add_reset_y_q0,
        flows=[FlowAttr.from_states(True, [], 0, 0)],
        input_state=c0.output,
    )

    # c2: CX(q0, q1) then MX(q0)
    def _add_cx_mx(body: Block):
        q0, q1 = body.args
        body.add_op(qref.GateOp(qcore.CXGateAttr(), [q0, q1]))
        body.add_op(qref.MeasureOp("X", [q0]))

    c2 = mk_circuit_op(
        input_qubits=2,
        input_flows=[z1],
        output_flows=[],
        add_ops=_add_cx_mx,
        flows=[],
        input_state=c1.output,
    )

    use_def_chain = _StateUseDefChain(make)
    use_def_chain.append(c0.output)
    use_def_chain.append(c1.output)
    use_def_chain.append(c2.output)

    with pytest.raises(
        BadUserFlowError,
        match=re.escape(
            "User-derived flow chain ending with Z1 cannot propagate through the current circuit."
        ),
    ):
        _GenerateFlows.find_flow_chains_for_use_def_chain(use_def_chain)


def test_generate_flows_edge_case_unblocking_disrupts_user_flow_3():
    """Same as above, except the two flows that need to multiply are both user flows.

    Pipeline:
        c0: RZ(q1) - creates Z1
        c1: RY(q0) - creates Y0, annotated flow Z1 -> Z1
        c2: CX(q0, q1), annotated flow Y0 -> Y0 X1.
        c3: MX(q0)

    After CX, there are two flow chains blocked on MX(q0):
        1. I -> Z1 -> Z1 -> Z0 Z1 (where the Z1 -> Z1 is the user flow link)
        2. I -> I  -> Y0 -> Y0 X1
    Unblocking requires multiplying them together, but this would disrupt both user flow links.
    So we should raise BadUserFlowError.
    """
    z1 = qcore.PauliStringAttr([("Z", 1)], 2)
    y0 = qcore.PauliStringAttr([("Y", 0)], 2)
    y0x1 = qcore.PauliStringAttr([("Y", 0), ("X", 1)], 2)

    q0, q1 = qcore.AllocQubitOp(results=[qcore.QubitType(), qcore.QubitType()]).result
    make = StateMakeOp([q0, q1], StateType(2, qcore.QubitType(), ArrayAttr([])))

    # c0: Reset Z on q1
    def _add_reset_z_q1(body: Block):
        _, q1 = body.args
        body.add_op(qref.ResetOp("Z", [q1]))

    c0 = mk_circuit_op(
        input_qubits=2,
        input_flows=[],
        output_flows=[z1],
        add_ops=_add_reset_z_q1,
        flows=[],
        input_state=make.output,
    )

    # c1: Reset Y on q0, user flow Z1 -> Z1
    def _add_reset_y_q0(body: Block):
        q0, _ = body.args
        body.add_op(qref.ResetOp("Y", [q0]))

    c1 = mk_circuit_op(
        input_qubits=2,
        input_flows=[z1],
        output_flows=[z1],
        add_ops=_add_reset_y_q0,
        flows=[FlowAttr.from_states(True, [], 0, 0)],
        input_state=c0.output,
    )

    # c2: CX(q0, q1), user flow Y0 -> Y0 X1
    def _add_cx(body: Block):
        q0, q1 = body.args
        body.add_op(qref.GateOp(qcore.CXGateAttr(), [q0, q1]))

    c2 = mk_circuit_op(
        input_qubits=2,
        input_flows=[y0, z1],
        output_flows=[y0x1],
        add_ops=_add_cx,
        flows=[FlowAttr.from_states(True, [], 0, 0)],
        input_state=c1.output,
    )

    # c3: MX(q0)
    def _add_mx(body: Block):
        (q0, _) = body.args
        body.add_op(qref.MeasureOp("X", [q0]))

    c3 = mk_circuit_op(
        input_qubits=2,
        input_flows=[y0x1],
        output_flows=[],
        add_ops=_add_mx,
        flows=[],
        input_state=c2.output,
    )

    use_def_chain = _StateUseDefChain(make)
    use_def_chain.append(c0.output)
    use_def_chain.append(c1.output)
    use_def_chain.append(c2.output)
    use_def_chain.append(c3.output)

    with pytest.raises(
        BadUserFlowError,
        match=re.escape(
            "User flow chain(s) [Y0 X1] failed to propagate through the current circuit "
            "independently."
        ),
    ):
        _GenerateFlows.find_flow_chains_for_use_def_chain(use_def_chain)


def test_generate_flows_edge_case_two_user_flows_unresolvable_conflict():
    """Test that two incompatible user flows raise BadUserFlowError.

    Pipeline:
        c0: RZ(q0), RZ(q1), annotated flows I -> Z0 and I -> Z1
        c1: CX(q0, q1), MZ(q1), annotated flow Z1 -> Z0

    User flow Z0 from c0 must propagate as Z0 -> Z0 (since to get to Z0 Z1 -> I it would require
    Z1 mixed in). But the annotated flow Z1 -> Z0 on c1 conflicts with it (both end states are Z0).
    Should raise BadUserFlowError.
    """
    z0 = qcore.PauliStringAttr([("Z", 0)], 2)
    z1 = qcore.PauliStringAttr([("Z", 1)], 2)

    q0, q1 = qcore.AllocQubitOp(results=[qcore.QubitType(), qcore.QubitType()]).result
    make = StateMakeOp([q0, q1], StateType(2, qcore.QubitType(), ArrayAttr([])))

    # c0: Reset Z on both qubits, with user flows I -> Z0 and I -> Z1
    def _add_two_resets(body: Block):
        q0, q1 = body.args
        body.add_op(qref.ResetOp("Z", [q0]))
        body.add_op(qref.ResetOp("Z", [q1]))

    c0 = mk_circuit_op(
        input_qubits=2,
        input_flows=[],
        output_flows=[z0, z1],
        add_ops=_add_two_resets,
        flows=[
            FlowAttr.from_states(True, [], qcore.I_STATE_INDEX, 0),
            FlowAttr.from_states(True, [], qcore.I_STATE_INDEX, 1),
        ],
        input_state=make.output,
    )

    # c1: CX(q0, q1), MZ(q1), with user flow Z1 -> Z0 (with measurement)
    def _add_cx_mz(body: Block):
        q0, q1 = body.args
        body.add_op(qref.GateOp(qcore.CXGateAttr(), [q0, q1]))
        body.add_op(qref.MeasureOp("Z", [q1]))

    c1 = mk_circuit_op(
        input_qubits=2,
        input_flows=[z0, z1],
        output_flows=[z0],
        add_ops=_add_cx_mz,
        flows=[FlowAttr.from_states(True, [0], 1, 0)],
        input_state=c0.output,
    )

    use_def_chain = _StateUseDefChain(make)
    use_def_chain.append(c0.output)
    use_def_chain.append(c1.output)

    with pytest.raises(BadUserFlowError, match="unresolvable conflict"):
        _GenerateFlows.find_flow_chains_for_use_def_chain(use_def_chain)
