"""Tests for the Stab (Stabiliser) xDSL dialect"""

import re
from collections.abc import Callable, Sequence
from typing import Literal, cast

import pytest
from xdsl.dialects import test as t
from xdsl.dialects.builtin import I1, ArrayAttr, BoolAttr, IntAttr, IntegerType, Signedness, i1
from xdsl.ir import Attribute, AttributeInvT, Block, Operation, OpResult, Region, SSAValue
from xdsl.irdl import VarOpResult
from xdsl.irdl.constraints import (
    AnyAttr,
    AnyInt,
    ConstraintContext,
    EqAttrConstraint,
    EqIntConstraint,
    IntVarConstraint,
    RangeOf,
    RangeVarConstraint,
    VarConstraint,
)
from xdsl.parser import Parser
from xdsl.pattern_rewriter import PatternRewriter
from xdsl.utils.exceptions import ParseError, VerifyException

from deltakit_compile.dialects.qcore import (
    I_STATE_INDEX,
    Pauli,
    PauliAttr,
    PauliStringAttr,
    QubitPauliStateAttr,
    QubitRegType,
    QubitType,
    UnpackQubitRegOp,
)
from deltakit_compile.dialects.stabiliser import (
    CircuitOp,
    ConcreteFlowArrayAttr,
    ConcreteFlowAttr,
    FlowAttr,
    StateCastOp,
    StateConcatenateOp,
    StateMakeOp,
    StatePermuteOp,
    StateSplitOp,
    StateType,
    YieldOp,
    _CircuitEntryArgsConstraint,
    _FlowConstraint,
)
from tests.unit.conftest import DEFAULT_UINT_SIZE
from tests.unit.dialects.conftest import check_asm_roundtrip


def _typed_value(ty: AttributeInvT) -> SSAValue[AttributeInvT]:
    """Create a real SSA value with the given type using the test dialect."""

    return cast(SSAValue[AttributeInvT], t.TestOp(result_types=[ty]).res[0])


def _uint_type(size: int | None = None) -> IntegerType:
    """Convenience function for quickly creating a uint type."""
    size = DEFAULT_UINT_SIZE if size is None else size
    return IntegerType(size, Signedness.UNSIGNED)


@pytest.mark.parametrize(
    ("program", "error_msg"),
    [
        (
            '"test.op"()<{prop1 = #stab.flow<<+:1>{M -> 0}>}> : () -> ()',
            "Expected qcore.pauli_state in the form (X|Y|Z)([0-9]+), got 'M'",
        ),
        (
            '%0 = "test.op"() : () -> !stab.state<3 x !test.type<"qubit">, [X0 X1 Z2, X0 Z2]>'
            '%1 = stab.circuit %0 : !stab.state<3 x !test.type<"qubit">, [X0 X1 Z2, X0 Z2]>'
            '-> !stab.state<3 x !test.type<"qubit">, [X0 X1 Z2, X0 Z2]>'
            '  with (%q1, %q2, %q3 : !test.type<"qubit">), (){'
            "    stab.yield []"
            "  } [<+:>{X0 -> I}]",
            "Cannot parse index as a flow state 'X0' as it does not "
            "appear in the flow state context: [X0 X1 Z2, X0 Z2].",
        ),
        (
            '%0 = "test.op"() : () -> !test.type<"S">'
            '%1 = stab.circuit %0 : !test.type<"S"> -> !test.type<"S">'
            '  with (%q1, %q2, %q3 : !test.type<"qubit">), (){'
            "    stab.yield []"
            "  } [<+:>{I -> 0}, <+:>{0 -> X0}]",
            "Expected an index of a flow state or 'I'",
        ),
    ],
)
def test_parse_errors(xdsl_context, program, error_msg):
    """Test that parsing produce expected errors for stabiliser dialect."""
    with pytest.raises(ParseError, match=re.escape(error_msg)):
        check_asm_roundtrip(program, xdsl_context)


def test_flow_verify():
    """Test that FlowAttr.verify produces expected errors."""
    with pytest.raises(
        VerifyException,
        match=re.escape("Flow cannot start and finish in 'I' state (-1)."),
    ):
        FlowAttr.new(
            [
                BoolAttr.from_bool(False),
                ArrayAttr([]),
                IntAttr(I_STATE_INDEX),
                IntAttr(I_STATE_INDEX),
            ]
        )


def test_flow_constr_verify():
    """Test that _FlowConstraint produces expected errors."""

    input_states = IntVarConstraint("I", AnyInt())
    output_states = IntVarConstraint("O", AnyInt())

    constraint_context = ConstraintContext()
    constraint_context.set_int_variable(input_states.name, 2)
    constraint_context.set_int_variable(output_states.name, 3)

    flow = FlowAttr.new([BoolAttr.from_bool(False), ArrayAttr([]), IntAttr(4), IntAttr(0)])
    with pytest.raises(
        VerifyException,
        match=re.escape("Cannot use input flow state index 4 to index 2 input flow states."),
    ):
        _FlowConstraint(input_states, output_states).verify(flow, constraint_context)

    flow = FlowAttr.new([BoolAttr.from_bool(False), ArrayAttr([]), IntAttr(0), IntAttr(6)])
    with pytest.raises(
        VerifyException,
        match=re.escape("Cannot use output flow state index 6 to index 3 output flow states."),
    ):
        _FlowConstraint(input_states, output_states).verify(flow, constraint_context)


def test_concrete_flow_verify():
    """Test that ConcreteFlowAttr produces expected errors."""
    with pytest.raises(
        VerifyException,
        match=re.escape("Flow cannot start and finish in 'I' state."),
    ):
        ConcreteFlowAttr.new(
            [
                BoolAttr.from_bool(False),
                ArrayAttr([]),
                PauliStringAttr.identity(1),
                PauliStringAttr.identity(1),
            ]
        )

    with pytest.raises(
        VerifyException,
        match=re.escape("Input and output flow state Pauli strings must have the same length."),
    ):
        ConcreteFlowAttr.new(
            [
                BoolAttr.from_bool(False),
                ArrayAttr([]),
                PauliStringAttr.identity(1),
                PauliStringAttr([("X", 0)], 2),
            ]
        )

    # No error on valid concrete flow
    ConcreteFlowAttr.new(
        [
            BoolAttr.from_bool(False),
            ArrayAttr([]),
            PauliStringAttr.identity(1),
            PauliStringAttr([("X", 0)], 1),
        ]
    )


def test_concrete_flow_array_verify_nonempty():
    """Test that ConcreteFlowArrayAttr produces the expected error on an empty list."""
    with pytest.raises(
        VerifyException,
        match=re.escape("A stab.concrete_flow_array must contain at least one stab.concrete_flow."),
    ):
        ConcreteFlowArrayAttr.new([ArrayAttr([])])


@pytest.mark.parametrize(
    "flows",
    [
        [
            ConcreteFlowAttr("+", [], "X0 : 1", "X0 : 1"),
            ConcreteFlowAttr("+", [], "X0 : 1", "X0 : 1"),
        ],
        [
            ConcreteFlowAttr("+", [], "X1 : 2", "X0 : 2"),
            ConcreteFlowAttr("+", [], "X0 : 1", "X0 : 1"),
        ],
        [
            ConcreteFlowAttr("+", [0, 1], "X0 : 1", "X0 : 1"),
            ConcreteFlowAttr("+", [0], "X0 : 1", "X0 : 1"),
        ],
        [
            ConcreteFlowAttr("+", [], "X0 : 1", "X0 : 1"),
            ConcreteFlowAttr("-", [], "X0 : 1", "X0 : 1"),
        ],
    ],
)
def test_concrete_flow_array_verify_unique_sorted(flows: list[ConcreteFlowAttr]):
    """Test that ConcreteFlowArrayAttr produces the expected error when the flows are not
    unique/sorted."""
    with pytest.raises(
        VerifyException,
        match=re.escape(
            "stab.concrete_flows must be unique and sorted first by their input and output states, "
            "then by their sign, and then by their measurement indices."
        ),
    ):
        ConcreteFlowArrayAttr.new([ArrayAttr(flows)])


@pytest.mark.parametrize(
    "flows",
    [
        [
            ConcreteFlowAttr("+", [], "X0 : 1", "X0 : 1"),
            ConcreteFlowAttr("+", [0], "X0 : 1", "X0 : 1"),
        ],
        [
            ConcreteFlowAttr("-", [], "X0 : 1", "X0 : 1"),
            ConcreteFlowAttr("+", [], "X0 : 1", "X0 : 1"),
        ],
        [
            ConcreteFlowAttr("-", [0, 1], "X0 : 1", "X0 : 1"),
            ConcreteFlowAttr("+", [1], "X0 : 1", "X0 : 1"),
        ],
    ],
)
def test_concrete_flow_array_verify_valid_same_states(flows: list[ConcreteFlowAttr]):
    """Test that ConcreteFlowArrayAttr does not produce an error when there are multiple flows with
    the same input and output states but different signs and/or measurement indices."""
    ConcreteFlowArrayAttr.new([ArrayAttr(flows)])


def test_state_permute_op_result_type_is_permuted():
    """StatePermuteOp should compute its result StateType from the input StateType
    and the permutation. Tests permutation having type Sequence[int] and
    ArrayAttr[IntAttr]"""

    input_type = StateType(
        3,
        QubitType(),
        [[("X", 0)], [("Z", 2)]],
    )
    input_state = StateMakeOp.build(
        operands=[[]],
        result_types=[input_type],
    ).output

    op = StatePermuteOp(input_state, permutation=[2, 1, 0])
    op.verify()

    assert op.permutation_list == [2, 1, 0]

    expected_type = StateType(
        3,
        QubitType(),
        [[("Z", 0)], [("X", 2)]],
    )
    assert op.output.type == expected_type

    op2 = StatePermuteOp(input_state, permutation=ArrayAttr([IntAttr(2), IntAttr(1), IntAttr(0)]))
    op2.verify()
    assert op2.output.type == expected_type


def test_state_permute_op_permute_flow():
    """StatePermuteOp.permute_flow should remap qubit indices and preserve canonical sort."""

    input_type = StateType(
        3,
        QubitType(),
        [[("X", 0), ("Z", 2)]],
    )
    input_state = StateMakeOp.build(
        operands=[[]],
        result_types=[input_type],
    ).output

    op = StatePermuteOp(input_state, permutation=[2, 1, 0])
    op.verify()

    expected_flow = PauliStringAttr([("Z", 0), ("X", 2)], 3)
    assert op.permute_flow(input_type.states[0]) == expected_flow


@pytest.mark.parametrize(
    ("permutation", "match"),
    [
        # Not a bijection on {0,1}: 0 appears twice. This is caught by the attribute
        # constraint (SetOf) before the op's custom verifier runs.
        ([0, 0], r"Sequence contains duplicate elements"),
        # Not a bijection / out-of-range: set({1,2}) != {0,1}.
        ([1, 2], r"Permutation given does not define a permutation map"),
        # Too long.
        ([0, 1, 2], r"incorrect length for range variable"),
        # Too short.
        ([0], r"incorrect length for range variable"),
        # Negative indices are disallowed by the attribute constraint (AtLeast(0)).
        ([-1, 0], r"expected integer >= 0"),
    ],
)
def test_state_permute_op_rejects_non_bijection(permutation: list[int], match: str):
    """StatePermuteOp should reject invalid permutations (not a bijection, wrong length, etc)."""

    input_type = StateType(2, QubitType(), [[("X", 0)]])
    input_state = StateMakeOp.build(
        operands=[[]],
        result_types=[input_type],
    ).output

    def _build_and_verify() -> None:
        op = StatePermuteOp(input_state, permutation=permutation)
        op.verify()

    with pytest.raises(VerifyException, match=match):
        _build_and_verify()


def test_state_permute_op_verifies_output_matches_permutation():
    """If the output type doesn't match the permuted flows, verify should fail."""

    input_type = StateType(2, QubitType(), [[("X", 0)]])
    input_state = StateMakeOp.build(
        operands=[[]],
        result_types=[input_type],
    ).output

    # Build an op with an intentionally wrong result type (as if parsed incorrectly).
    wrong_type = StateType(2, QubitType(), [[("X", 0)]])

    def _build_and_verify_wrong_result_type() -> None:
        op = StatePermuteOp.build(
            operands=[input_state],
            result_types=[wrong_type],
            attributes={
                "permutation": ArrayAttr([IntAttr(1), IntAttr(0)]),
            },
        )
        op.verify()

    with pytest.raises(
        VerifyException,
        match=re.escape("stab.state.permute result type does not match the permuted flow states"),
    ):
        _build_and_verify_wrong_result_type()


def test_state_permute_op_verifies_output_matches_permutation_multiple_flows_one_wrong():
    """If there are multiple flows and only one is wrong, verify_ should still fail."""

    input_type = StateType(
        2,
        QubitType(),
        [[("X", 0)], [("Z", 1)]],
    )
    input_state = StateMakeOp.build(
        operands=[[]],
        result_types=[input_type],
    ).output

    # Correct permutation [1,0] should map X0->X1 and Z1->Z0.
    # We intentionally keep the Z flow correct but keep the X flow unpermuted.
    wrong_type = StateType(
        2,
        QubitType(),
        [[("X", 0)], [("Z", 1)]],
    )

    def _build_and_verify_wrong_result_type() -> None:
        op = StatePermuteOp.build(
            operands=[input_state],
            result_types=[wrong_type],
            attributes={
                "permutation": ArrayAttr([IntAttr(1), IntAttr(0)]),
            },
        )
        op.verify()

    with pytest.raises(
        VerifyException,
        match=re.escape("stab.state.permute result type does not match the permuted flow states"),
    ):
        _build_and_verify_wrong_result_type()


def test_state_permute_op_parse_rejects_non_int_list(xdsl_context):
    """The custom permutation syntax should be a square-bracket list of integers."""

    program = (
        '%0 = "test.op"() : () -> !stab.state<2 x !test.type<"qubit">, [X0]>'
        '%1 = stab.state.permute <foo>(%0 : !stab.state<2 x !test.type<"qubit">, [X0]>)'
        ' -> !stab.state<2 x !test.type<"qubit">, [X1]>'
    )
    with pytest.raises(ParseError):
        check_asm_roundtrip(program, xdsl_context)


def test_state_permute_op_is_identity():
    input_type = StateType(3, QubitType(), [])
    input_state = StateMakeOp.build(operands=[[]], result_types=[input_type]).output

    identity_permute = StatePermuteOp(input_state, permutation=[0, 1, 2])
    assert identity_permute.is_identity

    non_identity_permute = StatePermuteOp(input_state, permutation=[0, 2, 1])
    assert not non_identity_permute.is_identity

    # single-qubit case
    single_qubit_type = StateType(1, QubitType(), [])
    single_qubit_state = StateMakeOp.build(operands=[[]], result_types=[single_qubit_type]).output
    single_identity_permute = StatePermuteOp(single_qubit_state, permutation=[0])
    assert single_identity_permute.is_identity


def test_state_permute_op_permute_list() -> None:
    """Test that StatePermuteOp.permute_list correctly permutes sequences."""
    input_type = StateType(4, QubitType(), [])
    input_state = cast(SSAValue[StateType], t.TestOp(operands=[], result_types=[input_type]).res[0])

    # Test with permutation [2, 0, 3, 1]
    op = StatePermuteOp(input_state, permutation=[2, 0, 3, 1])

    # Test with list of strings
    input_list = ["a", "b", "c", "d"]
    result = op.permute_list(input_list)
    assert result == ["b", "d", "a", "c"]

    # Test with list of integers
    input_ints = [10, 20, 30, 40]
    result_ints = op.permute_list(input_ints)
    assert result_ints == [20, 40, 10, 30]

    # Test with identity permutation
    identity_op = StatePermuteOp(input_state, permutation=[0, 1, 2, 3])
    assert identity_op.permute_list(input_list) == input_list


@pytest.mark.parametrize(
    ("permutation", "input_seq", "expected_output"),
    [
        ([0], ["a"], ["a"]),
        ([1, 0], ["a", "b"], ["b", "a"]),
        ([2, 0, 1], ["a", "b", "c"], ["b", "c", "a"]),
        ([2, 1, 0], [1, 2, 3], [3, 2, 1]),
        ([0, 2, 1, 3], ["w", "x", "y", "z"], ["w", "y", "x", "z"]),
        ([3, 2, 1, 0], [10, 20, 30, 40], [40, 30, 20, 10]),
        ([0, 3, 2, 1], [10, 20, 30, 40], [10, 40, 30, 20]),
        ([0, 2, 3, 1], [10, 20, 30, 40], [10, 40, 20, 30]),
        ([2, 0, 3, 1], [10, 20, 30, 40], [20, 40, 10, 30]),
    ],
)
def test_state_permute_op_apply_permutation(
    permutation: list, input_seq: list, expected_output: list
) -> None:
    """Test that StatePermuteOp.apply_permutation correctly applies permutations."""
    result = StatePermuteOp.apply_permutation(permutation, input_seq)
    assert result == expected_output


def test_state_permute_op_apply_permutation_preserves_type() -> None:
    """Test that apply_permutation preserves element types."""

    # Test with complex objects
    class CustomObj:
        pass

    objects = [CustomObj for _ in range(3)]
    permutation = [2, 0, 1]
    result = StatePermuteOp.apply_permutation(permutation, objects)

    assert len(result) == 3
    assert objects[0] is result[2]
    assert objects[1] is result[0]
    assert objects[2] is result[1]


def test_state_permute_op_apply_permutation_invalid_permutation():
    permutation = [3, 1, 0, 0]
    with pytest.raises(ValueError, match="Input does not define a valid permutation map"):
        StatePermuteOp.apply_permutation(permutation, ["a", "a", "a", "a"])

    permutation = [3, 1, 0, 0]
    with pytest.raises(ValueError, match="Permutation and input sequence have different lengths"):
        StatePermuteOp.apply_permutation(permutation, ["a", "a", "a", "a", "A"])


@pytest.mark.parametrize(
    ("permutation", "expected_inverse"),
    [
        ([0], [0]),
        ([1, 0], [1, 0]),
        ([0, 1, 2], [0, 1, 2]),
        ([2, 0, 1], [1, 2, 0]),
        ([1, 2, 0], [2, 0, 1]),
        ([2, 1, 0], [2, 1, 0]),
        ([1, 3, 0, 2], [2, 0, 3, 1]),
        ([3, 2, 1, 0], [3, 2, 1, 0]),
    ],
)
def test_state_permute_op_invert_permutation(permutation, expected_inverse):
    """Test that StatePermuteOp.invert_permutation correctly inverts permutations."""
    result = StatePermuteOp.invert_permutation(permutation)
    assert result == expected_inverse


def test_state_permute_op_invert_permutation_roundtrip():
    """Test that inverting a permutation twice gives the original."""
    original = [3, 1, 0, 2]
    inverted = StatePermuteOp.invert_permutation(original)
    double_inverted = StatePermuteOp.invert_permutation(inverted)
    assert double_inverted == original


def test_state_permute_op_invert_permutation_composition():
    """Test that applying a permutation and then its inverse gives identity."""
    permutation = [2, 0, 3, 1]
    inverse = StatePermuteOp.invert_permutation(permutation)

    input_seq = ["a", "b", "c", "d"]
    permuted = StatePermuteOp.apply_permutation(permutation, input_seq)
    result = StatePermuteOp.apply_permutation(inverse, permuted)

    assert result == input_seq


def test_state_permute_op_invert_permutation_invalid_permutation():
    original = [3, 1, 0, 0]
    with pytest.raises(ValueError, match="Input does not define a valid permutation map"):
        StatePermuteOp.invert_permutation(original)


@pytest.mark.parametrize(
    ("permutation", "expected"),
    [
        ([0], True),
        ([0, 1], True),
        ([0, 1, 2, 3], True),
        ([1, 0], False),
        ([0, 2, 1], False),
        ([2, 1, 0], False),
        ([0, 1, 3, 2], False),
    ],
)
def test_state_permute_op_is_identity_permutation(permutation, expected):
    """Test that StatePermuteOp.is_identity_permutation correctly identifies identity
    permutations."""
    result = StatePermuteOp.is_identity_permutation(permutation)
    assert result == expected


def test_state_permute_op_calculate_permutation_from_states():
    """Test that StatePermuteOp.calculate_permutation_from_states correctly computes
    permutations."""
    # Create states with different qubit counts
    state_type_1 = StateType(2, QubitType(), [])
    state_type_2 = StateType(1, QubitType(), [])
    state_type_3 = StateType(3, QubitType(), [])

    state1 = StateMakeOp.build(operands=[[]], result_types=[state_type_1]).output
    state2 = StateMakeOp.build(operands=[[]], result_types=[state_type_2]).output
    state3 = StateMakeOp.build(operands=[[]], result_types=[state_type_3]).output

    # Test case 1: Identity reordering [state1, state2, state3] -> [state1, state2, state3]
    inputs = [state1, state2, state3]
    outputs = [state1, state2, state3]
    permutation = StatePermuteOp.calculate_permutation_from_states(inputs, outputs)
    # state1 has qubits 0-1, state2 has qubit 2, state3 has qubits 3-5
    assert permutation == [0, 1, 2, 3, 4, 5]

    # Test case 2: Reverse order [state1, state2, state3] -> [state3, state2, state1]
    inputs = [state1, state2, state3]
    outputs = [state3, state2, state1]
    permutation = StatePermuteOp.calculate_permutation_from_states(inputs, outputs)
    # Input: state1 (0-1) -> 4-5, state2 (2) -> 3, state3 (3-5) -> 0-2
    assert permutation == [4, 5, 3, 0, 1, 2]

    # Test case 3: Swap first two [state1, state2, state3] -> [state2, state1, state3]
    inputs = [state1, state2, state3]
    outputs = [state2, state1, state3]
    permutation = StatePermuteOp.calculate_permutation_from_states(inputs, outputs)
    # Input: state1 (0-1) -> 1-2, state2 (2) -> 0, state3 (3-5) -> 3-5
    assert permutation == [1, 2, 0, 3, 4, 5]


def test_state_permute_op_calculate_permutation_from_states_single_state():
    """Test calculate_permutation_from_states with a single state."""
    state_type = StateType(3, QubitType(), [])
    state = StateMakeOp.build(operands=[[]], result_types=[state_type]).output

    permutation = StatePermuteOp.calculate_permutation_from_states([state], [state])
    assert permutation == [0, 1, 2]


def test_state_permute_op_calculate_permutation_from_states_complex():
    """Test calculate_permutation_from_states with a more complex rearrangement."""
    # Create 4 states with 1 qubit each
    state_types = [StateType(1, QubitType(), []) for _ in range(4)]
    states = [StateMakeOp.build(operands=[[]], result_types=[st]).output for st in state_types]

    # Rearrange: [s0, s1, s2, s3] -> [s3, s1, s0, s2]
    inputs = states
    outputs = [states[3], states[1], states[0], states[2]]
    permutation = StatePermuteOp.calculate_permutation_from_states(inputs, outputs)
    # Input qubits: s0=0, s1=1, s2=2, s3=3
    # Output qubits: s3=0, s1=1, s0=2, s2=3
    # So: 0->2, 1->1, 2->3, 3->0
    assert permutation == [2, 1, 3, 0]


def test_state_permute_op_calculate_permutation_invalid_args():
    """Test calculate_permutation_from_states with a invalid arguments"""
    # Create 4 states with 1 qubit each
    state_types = [StateType(5, QubitType(), []) for _ in range(4)]
    states = [StateMakeOp.build(operands=[[]], result_types=[st]).output for st in state_types]

    inputs = states
    outputs = [states[3], states[1], states[0]]
    with pytest.raises(
        ValueError, match="The outputs sequence is not a permutation of the inputs sequence"
    ):
        StatePermuteOp.calculate_permutation_from_states(inputs, outputs)

    outputs = [states[3], states[1], states[0], states[0]]
    with pytest.raises(
        ValueError, match="The outputs sequence is not a permutation of the inputs sequence"
    ):
        StatePermuteOp.calculate_permutation_from_states(inputs, outputs)


@pytest.mark.parametrize(
    ("entry_args", "error_msg"),
    [
        ([t.TestType("T1")], "Expected 2 qubit arguments but got 1 block arguments."),
        (
            [t.TestType("T1"), t.TestType("T1")],
            re.escape(
                """attributes ('!test.type<"T1">', '!test.type<"T2">') expected from range """
                """variable 'A', but got ()"""
            ),
        ),
        (
            [t.TestType("T1"), t.TestType("T1"), t.TestType("T2")],
            re.escape(
                """attributes ('!test.type<"T1">', '!test.type<"T2">') expected from range """
                """variable 'A', but got ('!test.type<"T2">',)"""
            ),
        ),
        (
            [t.TestType("T1"), t.TestType("T2"), t.TestType("T1"), t.TestType("T2")],
            re.escape(
                """attribute !test.type<"T1"> expected from variable 'QT', """
                """but got !test.type<"T2">"""
            ),
        ),
    ],
)
def test_circuit_entry_arg_constr_verify(entry_args, error_msg):
    """Test that _CircuitEntryArgsConstraint produces expected errors."""
    n_qubits = IntVarConstraint("Q", AnyInt())
    qubit_type = VarConstraint("QT", AnyAttr())
    input_args = RangeVarConstraint("A", RangeOf(AnyAttr()))

    constraint_context = ConstraintContext()
    constraint_context.set_int_variable(n_qubits.name, 2)
    constraint_context.set_attr_variable(qubit_type.name, t.TestType("T1"))
    constraint_context.set_range_variable(input_args.name, (t.TestType("T1"), t.TestType("T2")))
    with pytest.raises(
        VerifyException,
        match=error_msg,
    ):
        _CircuitEntryArgsConstraint(n_qubits, qubit_type, input_args).verify(
            entry_args, constraint_context
        )


@pytest.mark.parametrize(
    ("qubit_count_constraint", "int_args", "length", "exp_error"),
    [
        (AnyInt(), RangeOf(AnyAttr()).of_length(EqIntConstraint(3)), 5, None),
        (
            AnyInt(),
            RangeOf(AnyAttr()).of_length(EqIntConstraint(4)),
            5,
            "Invalid value 3, expected 4",
        ),
        (
            AnyInt(),
            RangeOf(AnyAttr()).of_length(EqIntConstraint(3)),
            4,
            "Invalid value 2, expected 3",
        ),
        (
            AnyInt(),
            RangeOf(EqAttrConstraint(t.TestType("XX"))).of_length(EqIntConstraint(3)),
            5,
            None,
        ),
    ],
)
@pytest.mark.parametrize(
    "qubit_type",
    [AnyAttr(), EqAttrConstraint(t.TestType("My_T1"))],
)
def test_circuit_entry_arg_constr_verify_length(
    qubit_count_constraint, qubit_type, int_args, length, exp_error
):
    """Test _CircuitEntryArgsConstraint.verify_length() method, for correctly passing and raising
    an error."""
    constraint = _CircuitEntryArgsConstraint(
        IntVarConstraint("Q", qubit_count_constraint), qubit_type, int_args
    )

    constraint_context = ConstraintContext()
    constraint_context.set_int_variable("Q", 2)
    constraint_context.set_attr_variable("T1", t.TestType("T1"))
    constraint_context.set_range_variable("R1", (t.TestType("T1"), t.TestType("T2")))
    if exp_error is not None:
        with pytest.raises(VerifyException, match=exp_error):
            constraint.verify_length(length, constraint_context=constraint_context)
    else:
        constraint.verify_length(length, constraint_context=constraint_context)


@pytest.mark.parametrize(
    ("yield_func", "error_msg"),
    [
        (
            lambda args: YieldOp(args[:2], args),
            "Mismatched number of output_args and yielded values: 3 != 2",
        ),
        (
            lambda args: YieldOp(args[:2], [args[1], args[0]]),
            "Mismatched output_args type and yielded type at position 1: i1 != i2.",
        ),
        (
            lambda args: YieldOp(args[:1], args[1:]),
            re.escape("Cannot use measurement indices: [0,1] to index 1 yielded measurements."),
        ),
    ],
)
def test_circuit_op_verify(yield_func: Callable[[list[SSAValue]], YieldOp], error_msg: str):
    """Test that stim.circuit verify gives expected errors"""
    test_op = t.TestOp(
        result_types=[
            StateType(
                IntAttr(2),
                t.TestType("Q"),
                ArrayAttr(
                    [
                        PauliStringAttr(
                            ArrayAttr([QubitPauliStateAttr(PauliAttr.X(), IntAttr(0))]), 2
                        )
                    ]
                ),
            )
        ]
    )
    circuit_op = CircuitOp.build(
        operands=[test_op.res[0], []],
        regions=[
            Region(
                Block(
                    arg_types=[t.TestType("Q"), t.TestType("Q")],
                    ops=[
                        t_op := t.TestOp(
                            result_types=[
                                i1,
                                i1,
                                IntegerType(2),
                            ]
                        ),
                        yield_func(list(t_op.res)),
                    ],
                )
            )
        ],
        result_types=[test_op.res[0].type, [IntegerType(1), IntegerType(2)]],
        properties={
            "flows": ArrayAttr(
                [
                    FlowAttr(
                        BoolAttr.from_bool(True),
                        ArrayAttr([IntAttr(0), IntAttr(1)]),
                        IntAttr(0),
                        IntAttr(I_STATE_INDEX),
                    )
                ]
            )
        },
    )
    with pytest.raises(VerifyException, match=error_msg):
        circuit_op.verify()


def test_stab_circuit_verify_rejects_qcore_ops_in_body() -> None:
    """`stab.circuit` verification should reject qcore operations in the body."""

    # 1-qubit state types, no flows.
    in_state_t = StateType(1, QubitType(), [])
    out_state_t = StateType(1, QubitType(), [])

    # Build a circuit body containing a qcore op (invalid by construction).
    block = Block(arg_types=[QubitType()])
    body = Region(block)

    # Create a fake qubit_reg and unpack it inside the stab.circuit body.
    fake_reg = cast(OpResult[QubitRegType], t.TestOp(result_types=[QubitRegType(1)]).res[0])
    block.add_op(fake_reg.owner)
    block.add_op(UnpackQubitRegOp(fake_reg))

    # Terminator (no measurements / no extra outputs for this test).
    block.add_op(YieldOp(measurements=[], arguments=[]))

    state_val = t.TestOp(result_types=[in_state_t]).res[0]
    circuit = CircuitOp(state_val, out_state_t, input_args=[], body=body)

    msg = "Cannot use qcore ops in a stab.circuit body."
    with pytest.raises(VerifyException, match=msg):
        circuit.verify()


@pytest.mark.parametrize(
    "qubit_type",
    [t.TestType("q1"), _uint_type(12)],
)
@pytest.mark.parametrize(
    ("qubits", "exp_qubits", "flow_states", "exp_flow_states"),
    [
        (2, IntAttr(2), [], ArrayAttr([])),
        (IntAttr(5), IntAttr(5), ArrayAttr([]), ArrayAttr([])),
        (
            2,
            IntAttr(2),
            [
                PauliStringAttr.new(
                    [ArrayAttr([QubitPauliStateAttr.new([PauliAttr.X(), IntAttr(0)])]), IntAttr(2)]
                ),
                PauliStringAttr.new(
                    [ArrayAttr([QubitPauliStateAttr.new([PauliAttr.X(), IntAttr(1)])]), IntAttr(2)]
                ),
            ],
            ArrayAttr(
                [
                    PauliStringAttr.new(
                        [
                            ArrayAttr([QubitPauliStateAttr.new([PauliAttr.X(), IntAttr(0)])]),
                            IntAttr(2),
                        ]
                    ),
                    PauliStringAttr.new(
                        [
                            ArrayAttr([QubitPauliStateAttr.new([PauliAttr.X(), IntAttr(1)])]),
                            IntAttr(2),
                        ]
                    ),
                ]
            ),
        ),
        (
            5,
            IntAttr(5),
            ArrayAttr(
                [
                    PauliStringAttr.new(
                        [
                            ArrayAttr([QubitPauliStateAttr.new([PauliAttr.Y(), IntAttr(1)])]),
                            IntAttr(5),
                        ]
                    ),
                    PauliStringAttr.new(
                        [
                            ArrayAttr([QubitPauliStateAttr.new([PauliAttr.Z(), IntAttr(0)])]),
                            IntAttr(5),
                        ]
                    ),
                ]
            ),
            ArrayAttr(
                [
                    PauliStringAttr.new(
                        [
                            ArrayAttr([QubitPauliStateAttr.new([PauliAttr.Z(), IntAttr(0)])]),
                            IntAttr(5),
                        ]
                    ),
                    PauliStringAttr.new(
                        [
                            ArrayAttr([QubitPauliStateAttr.new([PauliAttr.Y(), IntAttr(1)])]),
                            IntAttr(5),
                        ]
                    ),
                ]
            ),
        ),
    ],
)
def test_state_type_init(qubits, exp_qubits, qubit_type, flow_states, exp_flow_states):
    """Test StateType init method.
    Tests that flow states get sorted by init."""
    state = StateType(qubits, qubit_type, flow_states)
    assert state == StateType(qubits=qubits, qubit_type=qubit_type, flow_states=flow_states)

    assert state.qubits == exp_qubits
    assert state.qubit_type == qubit_type
    assert state.flow_states == exp_flow_states


@pytest.mark.parametrize(
    ("input_str", "exp_error"),
    [
        (
            '!stab.state<3 x !test.type<"qubit">, [X0 X1 Z2, X0 Z2, X0 X2]>',
            "Each qcore.pauli_string in a stab.state must be unique and sorted",
        ),
        (
            '!stab.state<3 x !test.type<"qubit">, [X0 X1 Z2, X0 Z20]>',
            re.escape(
                "qcore.pauli_string refers to qubit indices [20] that are beyond its length of 3"
            ),
        ),
        (
            '!stab.state<3 x !test.type<"qubit">, [X0, Z0]>',
            re.escape(
                "All flow states in a stab.state must pairwise commute. "
                "Flow states #qcore.pauli_string<X0 : 3> and #qcore.pauli_string<Z0 : 3> do not "
                "commute."
            ),
        ),
    ],
)
def test_state_type_verify(xdsl_context, input_str: str, exp_error: str):
    """Test that constraints on StateType raise correct errors."""
    parser = Parser(xdsl_context, input_str)
    with pytest.raises(VerifyException, match=exp_error):
        parser.parse_attribute()


def test_state_type_with_new_flow_states():
    """Test that StateType.with_new_flow_states() correctly replaces flow states."""
    state = StateType(
        qubits=3,
        qubit_type=t.TestType("q"),
        flow_states=[[("X", 0), ("X", 1)], [("Z", 2)]],
    )
    new_flow_states = [[("Z", 0)], [("Z", 1)], [("X", 2)]]
    new_state = state.with_new_flow_states(new_flow_states)
    assert new_state.qubits.data == state.qubits.data
    assert new_state.qubit_type == state.qubit_type
    assert new_state.states == [PauliStringAttr(flow_state, 3) for flow_state in new_flow_states]


def _get_test_body(
    args: Sequence[Attribute],
    qubits: int,
    qubit_type: Attribute,
    measures: int,
    returns_op: t.TestOp | None,
):
    """Helper to get a circuit body."""
    ops: list[Operation] = []
    if returns_op is None:
        outputs = []
    else:
        ops.append(returns_op)
        outputs = list(returns_op.res)
    measurements = t.TestOp(result_types=[i1] * measures)
    ops.append(measurements)
    yield_op = YieldOp.build(operands=[measurements.res, outputs])
    ops.append(yield_op)
    block = Block(arg_types=[qubit_type] * qubits + list(args), ops=ops)
    return Region(block)


@pytest.mark.parametrize(
    (
        "input_args",
        "body",
        "exp_body",
        "output_args_types",
        "exp_output_args_types",
        "flows",
        "exp_flows",
        "verifies",
    ),
    [
        (
            t.TestOp(result_types=[t.TestType("t1"), t.TestType("t2")]).res,
            _get_test_body([t.TestType("t1"), t.TestType("t2")], 10, t.TestType("q"), 2, None),
            _get_test_body([t.TestType("t1"), t.TestType("t2")], 10, t.TestType("q"), 2, None),
            [],
            (),
            None,
            None,
            True,
        ),
        (
            t.TestOp(result_types=[t.TestType("t1")]).res,
            _get_test_body(
                [t.TestType("t2")],
                10,
                t.TestType("q"),
                3,
                t.TestOp(result_types=[t.TestType("t1")]),
            ).detach_block(0),
            _get_test_body(
                [t.TestType("t2")],
                10,
                t.TestType("q"),
                3,
                t.TestOp(result_types=[t.TestType("t1")]),
            ),
            None,
            (t.TestType("t1"),),
            [],
            ArrayAttr([]),
            False,
        ),
        (
            t.TestOp(result_types=[t.TestType("t1")]).res,
            [
                op.parent.detach_op(op)
                for op in _get_test_body(
                    [t.TestType("t2")],
                    10,
                    t.TestType("q"),
                    4,
                    t.TestOp(result_types=[t.TestType("t1")]),
                )
                .detach_block(0)
                .ops
            ],
            Region(
                Block(
                    [
                        op.parent.detach_op(op)
                        for op in _get_test_body(
                            [t.TestType("t2")],
                            10,
                            t.TestType("q"),
                            4,
                            t.TestOp(result_types=[t.TestType("t1")]),
                        )
                        .detach_block(0)
                        .ops
                    ]
                )
            ),
            [t.TestType("t_ret")],
            (t.TestType("t_ret"),),
            ArrayAttr(
                [
                    FlowAttr.new(
                        [
                            BoolAttr.from_bool(False),
                            ArrayAttr([IntAttr(1)]),
                            IntAttr(1),
                            IntAttr(-1),
                        ]
                    ),
                    FlowAttr.new(
                        [
                            BoolAttr.from_bool(False),
                            ArrayAttr([IntAttr(1)]),
                            IntAttr(0),
                            IntAttr(-1),
                        ]
                    ),
                ]
            ),
            ArrayAttr(
                [
                    FlowAttr.new(
                        [
                            BoolAttr.from_bool(False),
                            ArrayAttr([IntAttr(1)]),
                            IntAttr(0),
                            IntAttr(-1),
                        ]
                    ),
                    FlowAttr.new(
                        [
                            BoolAttr.from_bool(False),
                            ArrayAttr([IntAttr(1)]),
                            IntAttr(1),
                            IntAttr(-1),
                        ]
                    ),
                ]
            ),
            False,
        ),
    ],
)
def test_circuit_op_init(
    input_args, body, exp_body, output_args_types, exp_output_args_types, flows, exp_flows, verifies
):
    """Test that CircuitOp init works correctly"""
    input_state = t.TestOp(
        result_types=[StateType(10, t.TestType("q"), [[("X", 2), ("Y", 3)], [("Z", 1), ("Z", 4)]])]
    ).res[0]

    output_state_type = StateType(10, t.TestType("q"), [])

    circuit_op = CircuitOp(
        input_state,
        output_state_type,
        input_args=input_args,
        body=body,
        output_args_types=output_args_types,
        flows=flows,
    )

    assert circuit_op.input == input_state
    assert circuit_op.input_args == tuple(input_args)
    assert circuit_op.body.is_structurally_equivalent(exp_body)
    assert circuit_op.flows == exp_flows
    assert circuit_op.output.type == output_state_type
    assert circuit_op.output_args.types == exp_output_args_types
    if verifies:
        circuit_op.verify()
        assert (
            circuit_op.qubit_block_args == body.block.args[: len(body.block.args) - len(input_args)]
        )
        assert circuit_op.yield_op == body.block.last_op
    else:
        with pytest.raises(VerifyException):
            circuit_op.verify()


@pytest.mark.parametrize(
    ("num_qubits", "input_args_types"),
    [
        (0, []),
        (1, []),
        (5, []),
        (0, [t.TestType("t1")]),
        (0, [t.TestType("t1"), t.TestType("t2")]),
        (1, [t.TestType("t1")]),
        (5, [t.TestType("t1"), t.TestType("t2")]),
    ],
)
def test_circuit_op_block_args(num_qubits, input_args_types):
    """Test the qubit_block_args and other_block_args methods in CircuitOp."""
    input_state = t.TestOp(result_types=[StateType(num_qubits, t.TestType("q"), [])]).res[0]
    output_state_type = StateType(num_qubits, t.TestType("q"), [])
    input_args = t.TestOp(result_types=input_args_types).res

    body = _get_test_body(
        input_args_types,
        num_qubits,
        t.TestType("q"),
        0,
        t.TestOp(result_types=[t.TestType("t1")]),
    )

    circuit_op = CircuitOp(
        input_state,
        output_state_type,
        input_args=input_args,
        body=body,
    )

    assert len(circuit_op.qubit_block_args) == num_qubits
    assert all(arg.type == t.TestType("q") for arg in circuit_op.qubit_block_args)
    assert len(circuit_op.other_block_args) == len(input_args_types)
    assert all(
        arg.type == input_arg_type
        for arg, input_arg_type in zip(circuit_op.other_block_args, input_args_types, strict=True)
    )

    for other_block_arg, input_arg in zip(circuit_op.other_block_args, input_args, strict=True):
        assert circuit_op.block_arg_to_input_arg(other_block_arg) == input_arg
    for output_arg, yield_arg in zip(
        circuit_op.output_args, circuit_op.yield_op.arguments, strict=True
    ):
        assert circuit_op.output_arg_to_yield_arg(output_arg) == yield_arg


def test_circuit_op_arg_dereference_error():
    """Test that block_arg_to_input_arg and output_arg_to_yield_arg raise errors when their argument
    does not exist."""
    input_state = t.TestOp(result_types=[StateType(1, t.TestType("q"), [])]).res[0]
    output_state_type = StateType(1, t.TestType("q"), [])
    circuit_op = CircuitOp(
        input_state,
        output_state_type,
        input_args=[],
        body=_get_test_body([], 1, t.TestType("q"), 0, None),
    )

    fake_ssa_value = t.TestOp(result_types=[t.TestType("q")]).res[0]

    with pytest.raises(ValueError, match=r"is not a non-qubit block argument of this circuit."):
        circuit_op.block_arg_to_input_arg(fake_ssa_value)

    with pytest.raises(ValueError, match=r"is not an output argument of this circuit."):
        circuit_op.output_arg_to_yield_arg(fake_ssa_value)


def test_yield_op_concat():
    """Test YieldOp.concat concatenates measurements and arguments."""
    measurements1 = t.TestOp(result_types=[_uint_type(1), _uint_type(2)]).res
    args1 = t.TestOp(result_types=[t.TestType("A"), t.TestType("B")]).res
    yield1 = YieldOp(measurements1, args1)

    measurements2 = t.TestOp(result_types=[_uint_type(3)]).res
    args2 = t.TestOp(result_types=[t.TestType("C")]).res
    yield2 = YieldOp(measurements2, args2)

    concatenated = yield1.concat(yield2)

    expected_measurements = measurements1 + measurements2
    expected_args = args1 + args2

    assert concatenated.measurements == expected_measurements
    assert concatenated.arguments == expected_args


@pytest.mark.parametrize(
    ("qubits", "state_type", "exp_error"),
    [
        (
            t.TestOp(result_types=[t.TestType("q1")] * 4).res,
            StateType.new([IntAttr(4), t.TestType("q1"), ArrayAttr([])]),
            None,
        ),
        (
            t.TestOp(result_types=[t.TestType("q1")] * 6).res,
            StateType.new([IntAttr(4), t.TestType("q2"), ArrayAttr([])]),
            "integer 6 expected from int variable 'Qubits', but got 4",
        ),
        (
            t.TestOp(result_types=[t.TestType("q2")] * 6).res,
            StateType.new(
                [
                    IntAttr(6),
                    t.TestType("q2"),
                    ArrayAttr(
                        [
                            PauliStringAttr.new(
                                [
                                    ArrayAttr(
                                        [QubitPauliStateAttr.new([PauliAttr.Y(), IntAttr(1)])]
                                    ),
                                    IntAttr(6),
                                ]
                            )
                        ]
                    ),
                ]
            ),
            "The state created by stab.state.make cannot have any flow states.",
        ),
    ],
)
def test_state_make_init(qubits, state_type, exp_error):
    """Test StateMakeOp init method."""
    make_op = StateMakeOp(qubits, state_type)
    assert make_op.input_qubits == qubits
    assert make_op.output.type == state_type
    if exp_error is None:
        make_op.verify()
    else:
        with pytest.raises(VerifyException, match=exp_error):
            make_op.verify()


def test_state_cast_init():
    """Test StateCastOp init method."""

    input_state = t.TestOp(
        result_types=[StateType(9, t.TestType("Q"), [[("X", 1), ("Y", 3)], [("X", 2), ("Z", 7)]])]
    ).res[0]
    output_state_type = StateType(10, t.TestType("Q"), [[("Z", 1), ("Z", 3)], [("Z", 4), ("Y", 8)]])
    cast_op = StateCastOp(input_state, output_state_type)
    assert cast_op.input == input_state
    assert cast_op.output.type == output_state_type


@pytest.mark.parametrize(
    ("input_state_type_args", "output_state_type_args", "output", "discarded"),
    [
        (
            (2, t.TestType("Q"), [[("X", 0)], [("Z", 1)]]),
            (2, t.TestType("Q"), [[("X", 0)]]),
            [[("X", 0)]],
            [[("Z", 1)]],
        ),
        (
            (2, t.TestType("Q"), [[("X", 0)], [("Z", 1)]]),
            (2, t.TestType("Q"), [[("X", 0)], [("Z", 1)]]),
            [[("X", 0)], [("Z", 1)]],
            [],
        ),
        (
            (1, t.TestType("Q"), []),
            (1, t.TestType("Q"), []),
            [],
            [],
        ),
    ],
)
def test_state_cast_deltas(input_state_type_args, output_state_type_args, output, discarded):
    """Test StateCastOp's methods computing the output and discarded flow states."""
    input_state = t.TestOp(result_types=[StateType(*input_state_type_args)]).res[0]
    cast_op = StateCastOp(input_state, StateType(*output_state_type_args))

    assert cast_op.output_flow_states == {PauliStringAttr(f, 2) for f in output}
    assert cast_op.discarded_flow_states == {PauliStringAttr(f, 2) for f in discarded}


def test_state_cast_cannot_add_flow_states():
    """Test that StateCastOp raises an error when trying to add flow states."""
    input_state = t.TestOp(result_types=[StateType(2, t.TestType("Q"), [[("X", 0)]])]).res[0]
    output_state_type = StateType(2, t.TestType("Q"), [[("X", 0)], [("Z", 1)]])
    cast_op = StateCastOp(input_state, output_state_type)
    with pytest.raises(
        VerifyException,
        match=r"Invalid state cast: the flow states \{.*\} were added.",
    ):
        cast_op.verify()


@pytest.mark.parametrize(
    ("sign", "exp_sign"),
    [
        ("+", True),
        ("-", False),
        (True, True),
        (False, False),
        (BoolAttr.from_bool(True), True),
        (BoolAttr.from_bool(False), False),
    ],
)
def test_flow_attr_from_states(sign: BoolAttr | bool | Literal["+", "-"], exp_sign: bool):
    """Test FlowAttr's from_states() method"""
    input_state = t.TestOp(
        result_types=[
            input_state_type := StateType(
                8, t.TestType("q3"), [[("X", 1), ("Y", 3)], [("X", 2), ("Z", 7)]]
            )
        ]
    ).res[0]
    circuit = CircuitOp(
        input_state,
        output_state_type := StateType(
            8, t.TestType("q3"), [[("Z", 1), ("X", 5)], [("Z", 1), ("Y", 7)]]
        ),
        input_args=[],
        body=Block(
            arg_types=[t.TestType("q3")] * 8,
            ops=[
                test_op := t.TestOp(result_types=[_uint_type(1)] * 4),
                YieldOp(ms := test_op.res, []),
            ],
        ),
        flows=[FlowAttr("+", [0, 1], 0, 1), FlowAttr("-", [2, 3], 1, -1)],
    )

    flow = FlowAttr(sign, [0, 3], 0, 1)
    assert flow == FlowAttr.from_states(sign, [0, 3], 0, 1)
    assert flow == FlowAttr.from_states(
        sign,
        [ms[0], ms[3]],
        PauliStringAttr([("X", 1), ("Y", 3)], 8),
        output_state_type.states[1],
        context=circuit,
    )
    assert flow == FlowAttr.from_states(
        sign,
        [ms[0], ms[3]],
        input_state_type.states[0],
        PauliStringAttr([("Z", 1), ("Y", 7)], 8),
        measurement_context=ms,
        input_state_context=input_state_type.states,
        output_state_context=output_state_type.states,
    )
    assert flow.is_plus is exp_sign
    assert flow.is_minus is not exp_sign


def test_flow_attr_with_measurement_offset():
    """Test FlowAttr's with_measurement_offset() method."""
    flow = FlowAttr("+", [2, 5], 1, I_STATE_INDEX)
    assert flow.with_measurement_offset(3) == FlowAttr("+", [5, 8], 1, -1)
    assert flow.with_measurement_offset(0) == flow
    assert flow.with_measurement_offset(-2) == FlowAttr("+", [0, 3], 1, I_STATE_INDEX)

    with pytest.raises(
        ValueError,
        match=re.escape(
            "Cannot offset measurements by -3 as it would result in negative measurement indices."
        ),
    ):
        flow.with_measurement_offset(-3)


def test_flow_attr_is_creation_destruction_flow():
    """Test FlowAttr's is_creation_flow and is_destruction_flow properties."""
    creation_flow = FlowAttr("+", [0], I_STATE_INDEX, 0)
    destruction_flow = FlowAttr("-", [0, 1], 0, I_STATE_INDEX)
    neither_flow = FlowAttr("+", [1, 2], 1, 1)

    assert creation_flow.is_creation_flow
    assert not creation_flow.is_destruction_flow

    assert destruction_flow.is_destruction_flow
    assert not destruction_flow.is_creation_flow

    assert not neither_flow.is_creation_flow
    assert not neither_flow.is_destruction_flow


@pytest.mark.parametrize(
    ("sign", "exp_sign"),
    [
        ("+", True),
        ("-", False),
        (True, True),
        (False, False),
        (BoolAttr.from_bool(True), True),
        (BoolAttr.from_bool(False), False),
    ],
)
def test_concrete_flow_attr_init(sign: BoolAttr | bool | Literal["+", "-"], exp_sign: bool):
    """Test initialising a ConcreteFlowAttr."""
    flow = ConcreteFlowAttr(
        sign, [0, 1], PauliStringAttr([("X", 2)], 4), PauliStringAttr([("X", 2), ("Z", 3)], 4)
    )

    assert flow == ConcreteFlowAttr(sign, [0, 1], "X2 : 4", "X2 Z3 : 4")
    assert flow == ConcreteFlowAttr(
        sign, ArrayAttr([IntAttr(0), IntAttr(1)]), "X2 : 4", "X2 Z3 : 4"
    )
    assert flow.is_plus is exp_sign
    assert flow.is_minus is not exp_sign
    assert flow.measurement_indices == [0, 1]


def test_concrete_flow_attr_get_measurement_values():
    """Test ConcreteFlowAttr's get_measurement_values() method."""
    flow = ConcreteFlowAttr(
        "+", [0, 2], PauliStringAttr([("X", 2)], 3), PauliStringAttr([("X", 2)], 3)
    )
    op = t.TestOp(result_types=[_uint_type(1), _uint_type(1), _uint_type(1)])

    measurement_values = flow.get_measurement_values(op)
    assert measurement_values == [op.res[0], op.res[2]]


def test_concrete_flow_attr_is_used_as_measurement():
    """Test ConcreteFlowAttr identifies if an OpResult is a measurement used in the flow."""
    flow = ConcreteFlowAttr(
        "+", [0, 2], PauliStringAttr([("X", 2)], 3), PauliStringAttr([("X", 2)], 3)
    )
    op = t.TestOp(result_types=[_uint_type(1), _uint_type(1), _uint_type(1), _uint_type(1)])
    op.attributes["flows"] = ConcreteFlowArrayAttr([flow])

    assert flow.is_used_as_measurement(op.res[0])
    assert not flow.is_used_as_measurement(op.res[1])
    assert flow.is_used_as_measurement(op.res[2])
    assert not flow.is_used_as_measurement(op.res[3])


def test_concrete_flow_array_attr_is_used_as_measurement():
    """Test ConcreteFlowArrayAttr identifies if an OpResult is a measurement used in any flow."""
    flow1 = ConcreteFlowAttr(
        "+", [0], PauliStringAttr([("X", 2)], 3), PauliStringAttr([("X", 2)], 3)
    )
    flow2 = ConcreteFlowAttr(
        "-", [1], PauliStringAttr([("Z", 3)], 4), PauliStringAttr([("Z", 3)], 4)
    )
    flow_array = ConcreteFlowArrayAttr([flow1, flow2])
    op = t.TestOp(result_types=[_uint_type(1), _uint_type(1), _uint_type(1)])
    op.attributes["flows"] = flow_array

    assert flow_array.is_used_as_measurement(op.res[0])
    assert flow_array.is_used_as_measurement(op.res[1])
    assert not flow_array.is_used_as_measurement(op.res[2])


def test_concrete_flow_attrs_resize():
    """Test recursively resizing concrete flow Pauli strings."""
    flow = ConcreteFlowAttr("-", [1], "X0 : 2", "Z1 : 2")

    resized_flow = flow.resize(4)
    assert resized_flow == ConcreteFlowAttr("-", [1], "X0 : 4", "Z1 : 4")

    resized_array = ConcreteFlowArrayAttr([flow]).resize(5)
    assert resized_array == ConcreteFlowArrayAttr([ConcreteFlowAttr("-", [1], "X0 : 5", "Z1 : 5")])


@pytest.mark.parametrize(
    ("indices", "shift", "removed_indices", "expected_indices"),
    [
        ([], 0, None, []),
        ([], 12, {0, 1, 2}, []),
        ([0], 0, None, [0]),
        ([0], 1, None, [1]),
        ([1, 4], 0, set(), [1, 4]),
        ([0], 0, {1}, [0]),
        ([1], 0, {0}, [0]),
        ([0, 2], 0, {1}, [0, 1]),
        ([1, 4], 0, {0}, [0, 3]),
        ([1, 4], 0, {0, 2}, [0, 2]),
        ([1, 4], 0, {0, 2, 3}, [0, 1]),
        ([1, 4], 0, {0, 2, 3, 5, 6, 7, 8}, [0, 1]),
        ([1, 4], 0, {5, 6, 7, 8}, [1, 4]),
        ([2, 5, 8, 9], 0, {0, 3, 4, 7}, [1, 2, 4, 5]),
        ([2, 5, 8, 9], 5, {0, 3, 4, 7}, [6, 7, 9, 10]),
        ([2, 5, 8, 9], -1, {0, 3, 4, 7}, [0, 1, 3, 4]),
    ],
)
def test_concrete_flow_attr_with_reindexed_measurements(
    indices: list[int], shift: int, removed_indices: set[int] | None, expected_indices: list[int]
):
    """Test that ConcreteFlowAttr.with_reindexed_measurements correctly updates the indices.
    Also test ConcreteFlowArrayAttr's with_reindexed_measurements and
    reindex_measurements_in_attrs."""
    flow = ConcreteFlowAttr(
        "+", indices, PauliStringAttr.identity(1), PauliStringAttr([("X", 0)], 1)
    )
    reindexed_flow = flow.with_reindexed_measurements(shift=shift, removed_indices=removed_indices)
    assert reindexed_flow.measurement_indices == expected_indices

    flow2 = ConcreteFlowAttr(
        "+", indices, PauliStringAttr.identity(2), PauliStringAttr([("X", 1)], 2)
    )
    flow_array = ConcreteFlowArrayAttr([flow, flow2])
    reindexed_flow_array = flow_array.with_reindexed_measurements(
        shift=shift, removed_indices=removed_indices
    )
    assert len(reindexed_flow_array.flows) == 2
    assert reindexed_flow_array.flows.data[0].measurement_indices == expected_indices
    assert reindexed_flow_array.flows.data[1].measurement_indices == expected_indices


@pytest.mark.parametrize(
    ("indices", "shift", "removed_indices", "error_message"),
    [
        (
            [0],
            0,
            {0},
            (
                "Cannot remove output 0 as it is used as a measurement in "
                "#stab.concrete_flow<<+:0>{I -> X0 : 1}>"
            ),
        ),
        (
            [1, 4],
            0,
            {4},
            (
                "Cannot remove output 4 as it is used as a measurement in "
                "#stab.concrete_flow<<+:1, 4>{I -> X0 : 1}>"
            ),
        ),
        (
            [0, 4, 6, 8],
            0,
            {1, 2, 3, 5, 7, 8},
            (
                "Cannot remove output 8 as it is used as a measurement in "
                "#stab.concrete_flow<<+:0, 4, 6, 8>{I -> X0 : 1}>"
            ),
        ),
        (
            [0],
            -1,
            set(),
            "Invalid negative measurement index -1 after shift.",
        ),
    ],
)
def test_concrete_flow_attr_with_reindexed_measurements_invalid_same_index(
    indices: list[int], shift: int, removed_indices: set[int], error_message: str
):
    """Test that ConcreteFlowAttr.with_reindexed_measurements raises an error if an index to be
    removed is present in the measurement indices. Also test ConcreteFlowArrayAttr."""
    flow = ConcreteFlowAttr(
        "+", indices, PauliStringAttr.identity(1), PauliStringAttr([("X", 0)], 1)
    )
    with pytest.raises(ValueError, match=re.escape(error_message)):
        flow.with_reindexed_measurements(shift=shift, removed_indices=removed_indices)

    flow2 = ConcreteFlowAttr(
        "+", indices, PauliStringAttr.identity(2), PauliStringAttr([("X", 1)], 2)
    )
    flow_array = ConcreteFlowArrayAttr([flow, flow2])
    with pytest.raises(ValueError, match=re.escape(error_message)):
        flow_array.with_reindexed_measurements(shift=shift, removed_indices=removed_indices)


def test_concrete_flow_array_attr_get():
    """Test that ConcreteFlowArrayAttr.get() returns the flow array if present."""
    flow_array = ConcreteFlowArrayAttr(
        [ConcreteFlowAttr("+", [], PauliStringAttr.identity(1), PauliStringAttr([("X", 0)], 1))]
    )
    op = t.TestOp(result_types=[_uint_type(1)])
    op.attributes[ConcreteFlowArrayAttr.KEY] = flow_array
    assert ConcreteFlowArrayAttr.get(op) == flow_array

    # Not present
    del op.attributes[ConcreteFlowArrayAttr.KEY]
    assert ConcreteFlowArrayAttr.get(op) is None


def test_concrete_flow_array_attr_get_error_wrong_type():
    """Test that ConcreteFlowArrayAttr.get() raises if the attribute is of the wrong type."""
    op = t.TestOp(result_types=[_uint_type(1)])
    op.attributes[ConcreteFlowArrayAttr.KEY] = t.TestType("not a flow array")
    with pytest.raises(
        ValueError,
        match=re.escape(
            "Expected attribute stab.flows to be a ConcreteFlowArrayAttr, got test.type"
        ),
    ):
        ConcreteFlowArrayAttr.get(op)


@pytest.mark.parametrize(
    ("in_states", "out_states", "query_in", "query_out", "expected_found"),
    [
        (
            [[("X", 1)], [("Z", 3)]],
            [[("X", 7)], [("Z", 3)]],
            [("X", 1)],
            [("Z", 3)],
            True,
        ),
        (
            [[("X", 1)], [("Z", 3)]],
            [[("X", 7)], [("Z", 3)]],
            [("X", 1)],
            [("Z", 5)],
            False,
        ),
        (
            [[("X", 1)], [("Z", 3)]],
            [[("X", 7)], [("Z", 3)]],
            [("Z", 5)],
            [("Z", 3)],
            False,
        ),
    ],
)
def test_circuit_find_flow_and_absence(
    in_states: Sequence[Sequence[tuple[Pauli, int]]],
    out_states: Sequence[Sequence[tuple[Pauli, int]]],
    query_in: Sequence[tuple[Pauli, int]],
    query_out: Sequence[tuple[Pauli, int]],
    expected_found: bool,
) -> None:
    """Test `CircuitOp.find_flow` for presence and absence of specific flows.

    Args:
        in_states: Input-side flow states for the circuit's input ``StateType``.
        out_states: Output-side flow states for the circuit's output ``StateType``.
        query_in: The input flow state to search for.
        query_out: The output flow state paired with ``query_in`` to search for.
        expected_found: Whether the flow is expected to be present.
    """
    # Define input/output states
    input_state_type = StateType(8, t.TestType("q"), in_states)
    output_state_type = StateType(8, t.TestType("q"), out_states)
    input_state = t.TestOp(result_types=[input_state_type]).res[0]

    # Body with 2 measurements
    body = _get_test_body([], 8, t.TestType("q"), 2, None)

    # Flows: create one concrete flow from X1 -> Z3 regardless of sort order,
    # and one from the other input state to I
    idx_in_x1 = input_state_type.states.index(PauliStringAttr([("X", 1)], 8))
    idx_out_z3 = output_state_type.states.index(PauliStringAttr([("Z", 3)], 8))
    # pick the other input index (if it exists)
    other_in_indices = [i for i in range(len(input_state_type.states)) if i != idx_in_x1]
    other_in = other_in_indices[0] if other_in_indices else idx_in_x1
    flows = [
        FlowAttr("+", [0, 1], idx_in_x1, idx_out_z3),
        FlowAttr("-", [], other_in, I_STATE_INDEX),
    ]

    circuit = CircuitOp(input_state, output_state_type, input_args=[], body=body, flows=flows)

    found = circuit.find_flow(PauliStringAttr(query_in, 8), PauliStringAttr(query_out, 8))
    assert (found is not None) is expected_found
    if expected_found:
        assert found == flows[0]


@pytest.mark.parametrize(
    ("extra_in", "extra_out", "exp_new_flows"),
    [
        (
            [PauliStringAttr([("Y", 0)], 8)],
            [PauliStringAttr([("Z", 2)], 8)],
            [FlowAttr("+", [1], 1, 2), FlowAttr("-", [2], 2, I_STATE_INDEX)],
        ),
        (
            # Duplicated extras should be deduped; indices for existing states remain base order
            [PauliStringAttr([("X", 1)], 8)],
            [PauliStringAttr([("X", 5)], 8)],
            [FlowAttr("+", [1], 0, 1), FlowAttr("-", [2], 1, I_STATE_INDEX)],
        ),
        (
            # Identity extras are ignored and do not appear in mapping
            [PauliStringAttr.identity(8)],
            [PauliStringAttr.identity(8)],
            [FlowAttr("+", [1], 0, 1), FlowAttr("-", [2], 1, I_STATE_INDEX)],
        ),
        (
            # No pre-existing flows annotated on the circuit: relabeling returns empty.
            [PauliStringAttr([("Z", 1)], 8)],
            [PauliStringAttr([("X", 0)], 8)],
            [],
        ),
        (
            # Candidate additions that already exist should be ignored (set semantics).
            # With base input states [X1], [Z3] and output states [X5], [Z7], include
            # already-existing additions (X1 on input, X5 on output) plus genuinely new states
            # (X0 on input, X0 on output). Canonical union becomes [X0, X1, Z3] and
            # [X0, X5, Z7] respectively.
            # So:
            #   - input A index 0 (X1) -> 1, input B index 1 (Z3) -> 2
            #   - output D index 1 (Z7) stays 2 (since X0 is inserted at 0 and X5 already exists)
            [PauliStringAttr([("X", 1)], 8), PauliStringAttr([("X", 0)], 8)],
            [PauliStringAttr([("X", 5)], 8), PauliStringAttr([("X", 0)], 8)],
            [FlowAttr("+", [1], 1, 2), FlowAttr("-", [2], 2, I_STATE_INDEX)],
        ),
    ],
)
def test_remap_and_relabel_flows(
    extra_in: list[PauliStringAttr],
    extra_out: list[PauliStringAttr],
    exp_new_flows: list[FlowAttr],
) -> None:
    """Exercise flow remapping and relabeling end-to-end, including I-state handling.

    Args:
        extra_in: Additional input-side flow states to consider when computing
            the new input index mapping.
        extra_out: Additional output-side flow states to consider when computing
            the new output index mapping.
        exp_new_flows: The expected list of flows with updated input/output
            indices following relabeling with the computed maps.
    """
    # Input has A=[X1], B=[Z3]
    input_state = t.TestOp(
        result_types=[StateType(8, t.TestType("q"), [[("X", 1)], [("Z", 3)]])]
    ).res[0]
    # Output has C=[X5], D=[Z7]
    output_state_type = StateType(8, t.TestType("q"), [[("X", 5)], [("Z", 7)]])

    # Build body with 3 measurements so measurement indices 0..2 are valid
    body = _get_test_body([], 8, t.TestType("q"), 3, None)

    # Flows: f1 A(0)->D(1), f2 B(1)->I
    flows = [
        FlowAttr("+", [1], 0, 1),
        FlowAttr("-", [2], 1, I_STATE_INDEX),
    ]
    circuit = CircuitOp(input_state, output_state_type, input_args=[], body=body, flows=flows)

    # Special-case the edge case where the circuit has no pre-existing flows.
    if exp_new_flows == [] and extra_in == [PauliStringAttr([("Z", 1)], 8)]:
        circuit.flows = None

    new_flows = circuit.relabel_flows_from_flow_states(extra_in, extra_out)
    assert set(new_flows) == set(exp_new_flows)


def test_circuit_convert_flow_mmt_to_ssa_and_errors():
    """Test mapping and error handling in `CircuitOp.convert_flow_mmt_to_ssa`."""
    # Build a circuit with 3 qubits and two measurements
    input_state = t.TestOp(
        result_types=[
            StateType(
                3,
                t.TestType("q"),
                [[("X", 0)], [("Z", 1)]],
            )
        ]
    ).res[0]
    output_state_type = StateType(3, t.TestType("q"), [[("Z", 2)]])

    meas_op = t.TestOp(result_types=[_uint_type(1), _uint_type(1)])
    ms = meas_op.res
    body = Block(arg_types=[t.TestType("q")] * 3, ops=[meas_op, YieldOp(ms, [])])

    flow_in_circuit = FlowAttr("+", [0, 1], 0, 0)
    circuit = CircuitOp(
        input_state,
        output_state_type,
        input_args=[],
        body=body,
        flows=[flow_in_circuit],
    )

    # Success: map indices to SSAValues
    mapped = circuit.convert_flow_mmt_to_ssa(flow_in_circuit)
    assert mapped == {ms[0], ms[1]}

    # Error: flow not present
    with pytest.raises(ValueError, match=r"Flow input is not found in the circuit op."):
        circuit.convert_flow_mmt_to_ssa(FlowAttr("+", [0], 0, 0))

    # Error: no flows on circuit
    meas_op2 = t.TestOp(result_types=[_uint_type(1), _uint_type(1)])
    ms2 = meas_op2.res
    body2 = Block(arg_types=[t.TestType("q")] * 3, ops=[meas_op2, YieldOp(ms2, [])])
    circuit_no_flows = CircuitOp(
        input_state,
        output_state_type,
        input_args=[],
        body=body2,
    )
    with pytest.raises(ValueError, match=r"Flow input is not found in the circuit op."):
        circuit_no_flows.convert_flow_mmt_to_ssa(flow_in_circuit)


def test_add_measurements_to_yield_mutates_and_preserves_existing_order() -> None:
    """Verify `add_measurements_to_yield` mutates the circuit's yield while preserving
    measurement order.

    Returns:
        None: Assertions verify that existing measurements are preserved in
        order, new measurements from the same body are appended without
        duplicates, and arguments are preserved. Repeated calls with no new
        measurements are a no-op.
    """
    # Build a body with two measurement ops and a yield initially referencing only the first op
    m1 = t.TestOp(result_types=[i1, i1])
    ms1 = cast(VarOpResult[I1], m1.res)
    m2 = t.TestOp(result_types=[i1])
    ms2 = cast(VarOpResult[I1], m2.res)
    m3 = t.TestOp(result_types=[i1])
    ms3 = cast(VarOpResult[I1], m3.res)
    body = Block(
        arg_types=[t.TestType("q")] * 2,
        ops=[m1, m2, YieldOp(ms1, [])],
    )
    input_state = t.TestOp(result_types=[StateType(2, t.TestType("q"), [])]).res[0]
    circuit = CircuitOp(input_state, StateType(2, t.TestType("q"), []), input_args=[], body=body)

    old_yield = circuit.yield_op
    old_args = list(old_yield.arguments)

    # Add one existing measurement (ms1[0]) and one new (ms2[0])
    circuit.add_measurements_to_yield([ms1[0], ms2[0]], PatternRewriter(circuit.yield_op))

    # Yield op should be replaced (different object), circuit itself is mutated in place
    assert circuit.yield_op is not old_yield

    # Existing measurements preserved in order, new appended; arguments unchanged
    assert list(circuit.yield_op.measurements) == [ms1[0], ms1[1], ms2[0]]
    assert list(circuit.yield_op.arguments) == old_args

    # Calling again with no truly new measurements should be a no-op
    again = circuit.yield_op
    circuit.add_measurements_to_yield([ms1[0]], PatternRewriter(circuit.yield_op))
    assert circuit.yield_op is again

    # The list of measurements to add is deduplicated
    circuit.add_measurements_to_yield([ms3[0], ms3[0]], PatternRewriter(circuit.yield_op))
    assert list(circuit.yield_op.measurements) == [ms1[0], ms1[1], ms2[0], ms3[0]]


def test_circuit_find_flow_outputs_for_index_zero_identity_and_missing() -> None:
    """Test `CircuitOp.find_flow_outputs` for edge cases and identity handling.

    Returns:
        None: Asserts that outputs are returned when the input flow index is 0,
        identity flows are correctly handled, and an empty list is returned when
        no outputs exist for the given input.
    """
    # Build states
    input_state_type = StateType(
        3,
        t.TestType("q"),
        [[("X", 0)], [("Z", 1)], [("X", 2)]],
    )
    output_state_type = StateType(
        3,
        t.TestType("q"),
        [[("Z", 0)], [("X", 1)], [("Z", 2)]],
    )
    input_state = t.TestOp(result_types=[input_state_type]).res[0]

    # Measurements
    meas_op = t.TestOp(result_types=[_uint_type(1), _uint_type(1), _uint_type(1)])
    ms = meas_op.res
    body = Block(arg_types=[t.TestType("q")] * 3, ops=[meas_op, YieldOp(ms, [])])

    # Flows: include two flows starting from input index 0, and one creation flow from I
    flow_a = FlowAttr("+", [0], 0, 1)
    flow_b = FlowAttr("-", [1, 2], 0, 2)
    creation_flow = FlowAttr("+", [2], I_STATE_INDEX, 1)
    circuit = CircuitOp(
        input_state,
        output_state_type,
        input_args=[],
        body=body,
        flows=[flow_a, flow_b, creation_flow],
    )

    # Input idx = 0 should return both flows
    outputs_for_zero = circuit.find_flow_outputs(input_state_type.states[0])
    assert outputs_for_zero == [
        (output_state_type.states[1], {ms[0]}),
        (output_state_type.states[2], {ms[1], ms[2]}),
    ]

    # Identity (I_STATE_INDEX) should return the creation flow
    outputs_for_identity = circuit.find_flow_outputs(PauliStringAttr.identity(3))
    assert outputs_for_identity == [(output_state_type.states[1], {ms[2]})]

    # Missing input state should return empty
    assert circuit.find_flow_outputs(PauliStringAttr([("X", 10)], 11)) == []


@pytest.mark.parametrize(
    ("input_spec", "expected_pairs"),
    [
        # Input X0 has one outgoing flow
        (
            [("X", 0)],
            [
                ([("Z", 0)], {0}),
            ],
        ),
        # Identity creates multiple outputs via creation flows
        (
            [],
            [
                ([("X", 1)], {2}),
                ([("Z", 2)], {1}),
            ],
        ),
        # Destruction flow: Z1 -> I with no measurements
        (
            [("Z", 1)],
            [
                ([], set()),
            ],
        ),
    ],
)
def test_circuit_find_flow_outputs_parametrized(
    input_spec: Sequence[tuple[Literal["X", "Y", "Z"], int]],
    expected_pairs: Sequence[tuple[Sequence[tuple[Literal["X", "Y", "Z"], int]], set[int]]],
) -> None:
    """Parametrized test for `CircuitOp.find_flow_outputs` across multiple flows.

    Args:
        input_spec: The input flow state specification passed to ``PauliStringAttr``.
        expected_pairs: A list of pairs ``(state_spec, indexes)`` where
            ``state_spec`` is a flow state specification and ``indexes`` is a set
            of expected measurement indices corresponding to that output state.

    Returns:
        None: Asserts that the outputs returned by ``find_flow_outputs`` match
        the expected flow states and measurement index sets, ignoring ordering.
    """
    # State types
    input_state_type = StateType(
        3,
        t.TestType("q"),
        [[("X", 0)], [("Z", 1)], [("X", 2)]],
    )
    output_state_type = StateType(
        3,
        t.TestType("q"),
        [[("Z", 0)], [("X", 1)], [("Z", 2)]],
    )
    input_state = t.TestOp(result_types=[input_state_type]).res[0]

    # Measurements
    meas_op = t.TestOp(result_types=[_uint_type(1), _uint_type(1), _uint_type(1)])
    ms = meas_op.res
    body = Block(arg_types=[t.TestType("q")] * 3, ops=[meas_op, YieldOp(ms, [])])

    # Flows: two from X0, one destruction from Z1, two creation from I
    ctx_inputs = input_state_type.states
    ctx_outputs = output_state_type.states
    f1 = FlowAttr.from_states(
        "+",
        [0],
        ctx_inputs[0],
        ctx_outputs[0],
        input_state_context=ctx_inputs,
        output_state_context=ctx_outputs,
    )
    f3 = FlowAttr.from_states(
        "+",
        [],
        ctx_inputs[1],
        PauliStringAttr((), 3),
        input_state_context=ctx_inputs,
        output_state_context=ctx_outputs,
    )
    f4 = FlowAttr.from_states(
        "+",
        [2],
        PauliStringAttr((), 3),
        ctx_outputs[1],
        input_state_context=ctx_inputs,
        output_state_context=ctx_outputs,
    )
    f5 = FlowAttr.from_states(
        "+",
        [1],
        PauliStringAttr((), 3),
        ctx_outputs[2],
        input_state_context=ctx_inputs,
        output_state_context=ctx_outputs,
    )

    circuit = CircuitOp(
        input_state,
        output_state_type,
        input_args=[],
        body=body,
        flows=[f1, f3, f4, f5],
    )

    # Run
    input_flow = PauliStringAttr(input_spec, 3)
    outputs = circuit.find_flow_outputs(input_flow)

    # Normalise actual output to (state_str, frozenset(indexes)) ignoring order
    actual_norm = {
        (
            str(state),
            frozenset(ms.index(m) for m in mmt_set),
        )
        for (state, mmt_set) in outputs
    }

    # Normalise expected pairs to (state_str, frozenset(indexes))
    expected_norm = {
        (
            str(PauliStringAttr(state_spec, 3)),
            frozenset(indexes),
        )
        for (state_spec, indexes) in expected_pairs
    }

    assert actual_norm == expected_norm


def test_merge_and_relabel_flow_states_shifts_by_prefix_qubit_counts() -> None:
    qubit_ty = QubitType()
    s0 = StateType(2, qubit_ty, [[("X", 0)], [("Z", 1)]])
    s1 = StateType(3, qubit_ty, [[("Y", 0)], [("Z", 2)]])

    merged = StateType.merge_and_relabel_flow_states([s0, s1])

    # second state's indices should be shifted by 2
    assert merged == [
        PauliStringAttr([("X", 0)], 5),
        PauliStringAttr([("Z", 1)], 5),
        PauliStringAttr([("Y", 2)], 5),
        PauliStringAttr([("Z", 4)], 5),
    ]


def test_partition_and_relabel_flow_states_splits_and_shifts_to_local_indices() -> None:
    # Two registers: first has 2 qubits (global 0,1), second has 1 qubit (global 2).
    reg_sizes = [2, 1]
    flows = [
        PauliStringAttr([("Z", 0)], 3),  # bucket 0, shift by -2? (see function)
        PauliStringAttr([("X", 1)], 3),  # bucket 0
        PauliStringAttr([("Y", 2)], 3),  # bucket 1
    ]

    buckets = list(StateSplitOp._partition_and_relabel_flow_states(flows, reg_sizes))

    assert len(buckets) == 2
    assert buckets[0] == [PauliStringAttr([("Z", 0)], 2), PauliStringAttr([("X", 1)], 2)]
    assert buckets[1] == [PauliStringAttr([("Y", 0)], 1)]


def test_partition_and_relabel_flow_states_raises_if_flow_state_split() -> None:
    reg_sizes = [2, 1]
    flows = [PauliStringAttr([("Z", 0), ("Z", 2)], 3)]
    with pytest.raises(ValueError, match=f"Flow state {flows[0]} cannot be partitioned."):
        # The helper returns a generator; force evaluation to trigger the error.
        _ = list(StateSplitOp._partition_and_relabel_flow_states(flows, reg_sizes))


def test_state_concatenate_verify_valid() -> None:
    qubit_ty = QubitType()
    s0_ty = StateType(2, qubit_ty, [[("X", 0)]])
    s1_ty = StateType(1, qubit_ty, [[("Z", 0)]])

    v0 = _typed_value(s0_ty)
    v1 = _typed_value(s1_ty)

    op = StateConcatenateOp([v0, v1])
    assert list(op.output.type.flow_states) == [
        PauliStringAttr([("X", 0)], 3),
        PauliStringAttr([("Z", 2)], 3),
    ]
    op.verify()


def test_state_concatenate_verify_rejects_wrong_result_type(xdsl_context) -> None:
    # Build an op with an explicitly wrong result type via parsing, so we can exercise verify_.
    program = (
        '%a = "test.op"() : () -> !stab.state<2 x !qcore.qubit, [X0]>\n'
        '%b = "test.op"() : () -> !stab.state<1 x !qcore.qubit, [Z0]>\n'
        "%r = stab.state.concatenate(%a, %b : !stab.state<2 x !qcore.qubit, [X0]>, "
        "!stab.state<1 x !qcore.qubit, [Z0]>) -> !stab.state<3 x !qcore.qubit, []>\n"
    )
    module = Parser(xdsl_context, program).parse_module()
    op = next(op for op in module.ops if isinstance(op, StateConcatenateOp))
    with pytest.raises(
        VerifyException,
        match=re.escape(
            "stab.state.concatenate result type does not match the concatenation of its"
        ),
    ):
        op.verify()


def test_state_concatenate_input_to_output_flow_correct() -> None:
    """Test StateConcatenateOp.input_to_output_flow maps input to output flow states correctly."""
    state_type0 = StateType(2, QubitType(), [[("X", 0)]])
    state_type1 = StateType(2, QubitType(), [[("Z", 0)]])
    v0 = _typed_value(state_type0)
    v1 = _typed_value(state_type1)

    op = StateConcatenateOp([v0, v1])
    op.verify()

    assert op.input_to_output_flow(v0, PauliStringAttr([("X", 0)], 2)) == PauliStringAttr(
        [("X", 0)], 4
    )
    assert op.input_to_output_flow(v1, PauliStringAttr([("Z", 0)], 2)) == PauliStringAttr(
        [("Z", 2)], 4
    )

    # Doesn't verify that the flow state is actually present on the input
    assert op.input_to_output_flow(v0, PauliStringAttr([("Z", 0), ("Y", 1)], 2)) == PauliStringAttr(
        [("Z", 0), ("Y", 1)], 4
    )
    assert op.input_to_output_flow(v1, PauliStringAttr([("Y", 1)], 2)) == PauliStringAttr(
        [("Y", 3)], 4
    )


def test_state_concatenate_input_to_output_flow_rejects_unknown_input() -> None:
    """Test that StateConcatenateOp.input_to_output_flow raises if the input is not an operand."""
    state_type = StateType(2, QubitType(), [[("X", 0)]])
    v = _typed_value(state_type)

    op = StateConcatenateOp([v])
    op.verify()

    with pytest.raises(ValueError, match=r"Input state \<.*\> not found in inputs\."):
        op.input_to_output_flow(_typed_value(state_type), PauliStringAttr([("X", 0)], 2))


def test_state_split_op_verify_partition_error_currently_leaks_value_error():
    """Test that StateSplitOp.verify() leaks a ValueError from partitioning over a flow state."""

    # 2 qubits, split into two 1-qubit registers.
    # The flow state X0 X1 spans both partitions, so partitioning must fail.
    input_type = StateType(2, QubitType(), [[("X", 0), ("X", 1)]])
    input_state = StateMakeOp.build(
        operands=[[]],
        result_types=[input_type],
    ).output

    # Result types don't matter for this test: the verifier should fail before comparing outputs.
    out0 = StateType(1, QubitType(), [])
    out1 = StateType(1, QubitType(), [])
    op = StateSplitOp.build(
        operands=[input_state],
        result_types=[[out0, out1]],
    )

    with pytest.raises(
        ValueError,
        match=re.escape("Flow state #qcore.pauli_string<X0 X1 : 2> cannot be partitioned."),
    ):
        op.verify()


def test_state_split_verify_valid() -> None:
    qubit_ty = QubitType()
    in_ty = StateType(
        3,
        qubit_ty,
        [[("Z", 0)], [("Z", 1)], [("X", 2)]],
    )
    v_in = _typed_value(in_ty)

    op = StateSplitOp(v_in, [1, 2])
    op.verify()


def test_state_split_verify_rejects_spanning_flow_state() -> None:
    qubit_ty = QubitType()
    # This flow spans both partitions under [1,2].
    in_ty = StateType(3, qubit_ty, [[("Z", 0), ("Z", 1)]])
    v_in = _typed_value(in_ty)

    # The constructor computes result types via partitioning, so this fails early.
    with pytest.raises(
        ValueError,
        match=re.escape(
            f"Flow state {PauliStringAttr([('Z', 0), ('Z', 1)], 3)} cannot be partitioned."
        ),
    ):
        _ = StateSplitOp(v_in, [1, 2])


def test_state_split_verify_rejects_mismatched_result_type() -> None:
    input_state_type = StateType(
        qubits=3, qubit_type=QubitType(), flow_states=[[("Z", 0), ("X", 1)]]
    )
    output_state_type1 = StateType(
        qubits=2, qubit_type=QubitType(), flow_states=[[("Z", 0), ("X", 1)]]
    )
    output_state_type2 = StateType(qubits=1, qubit_type=QubitType(), flow_states=[[("Y", 0)]])
    v_in = _typed_value(input_state_type)
    op: StateSplitOp = StateSplitOp.build(
        operands=(v_in,),
        result_types=([output_state_type1, output_state_type2],),
    )
    with pytest.raises(
        VerifyException,
        match=re.escape("stab.state.split result types do not match the partitioned flow states"),
    ):
        op.verify()


def test_state_split_output_to_input_flow_correct() -> None:
    """Test StateSplitOp.output_to_input_flow maps input to output flow states correctly."""
    state_type0 = StateType(4, QubitType(), [[("X", 0)], [("Z", 2)]])
    input_ = _typed_value(state_type0)

    op = StateSplitOp(input_, [2, 2])
    op.verify()

    v0, v1 = op.outputs
    assert op.output_to_input_flow(v0, PauliStringAttr([("X", 0)], 2)) == PauliStringAttr(
        [("X", 0)], 4
    )
    assert op.output_to_input_flow(v1, PauliStringAttr([("Z", 0)], 2)) == PauliStringAttr(
        [("Z", 2)], 4
    )

    # Doesn't verify that the flow state is actually present on the output
    assert op.output_to_input_flow(v0, PauliStringAttr([("Z", 0), ("Y", 1)], 2)) == PauliStringAttr(
        [("Z", 0), ("Y", 1)], 4
    )
    assert op.output_to_input_flow(v1, PauliStringAttr([("Y", 1)], 2)) == PauliStringAttr(
        [("Y", 3)], 4
    )


def test_state_split_output_to_input_flow_rejects_unknown_input() -> None:
    """Test that StateSplitOp.output_to_input_flow raises if the input is not an output."""
    state_type = StateType(4, QubitType(), [[("X", 0)]])
    v = _typed_value(state_type)

    op = StateSplitOp(v, [2, 2])
    op.verify()

    with pytest.raises(ValueError, match=r"Output state \<.*\> not found in outputs\."):
        op.output_to_input_flow(_typed_value(state_type), PauliStringAttr([("X", 0)], 4))


def test_circuit_used_input_output_flows():
    """Test the properties used_input_flow_states and used_output_flow_states
    of CircuitOp."""

    # Input/output types each have 3 flow states, but we will only reference a subset.
    input_state_type = StateType(
        3,
        t.TestType("q"),
        [[("X", 0)], [("Z", 1)], [("X", 2)]],
    )
    output_state_type = StateType(
        3,
        t.TestType("q"),
        [[("Z", 0)], [("X", 1)], [("Z", 2)]],
    )

    input_state = t.TestOp(result_types=[input_state_type]).res[0]

    # Create a body so flow measurement indices are valid.
    meas_op = t.TestOp(result_types=[_uint_type(1), _uint_type(1), _uint_type(1)])
    ms = meas_op.res
    body = Block(arg_types=[t.TestType("q")] * 3, ops=[meas_op, YieldOp(ms, [])])

    # Flows:
    #   - Use input index 0 and 2, leaving input index 1 unused.
    #   - Use only output index 1, leaving output indices 0 and 2 unused.
    #   - Include an I-state flow on each side to ensure it's excluded.
    flows = [
        FlowAttr("+", [0], 0, 1),
        FlowAttr("-", [1, 2], 2, I_STATE_INDEX),
        FlowAttr("+", [2], I_STATE_INDEX, 0),
    ]

    circuit = CircuitOp(
        input_state,
        output_state_type,
        input_args=[],
        body=body,
        flows=flows,
    )

    assert circuit.used_input_flow_states == [
        PauliStringAttr([("X", 0)], 3),
        PauliStringAttr([("X", 2)], 3),
    ]
    assert circuit.used_output_flow_states == [
        PauliStringAttr([("Z", 0)], 3),
        PauliStringAttr([("X", 1)], 3),
    ]


def test_circuit_used_input_output_flows_empty() -> None:
    """Tests that the above helpers function correctly when there
    are no used non-identity input flow states.
    """

    input_state_type = StateType(1, t.TestType("q"), [])
    output_state_type = StateType(1, t.TestType("q"), [[("X", 0)]])
    input_state = t.TestOp(result_types=[input_state_type]).res[0]

    # Zero-qubit body, no measurements, no arguments.
    body = Block(arg_types=[], ops=[YieldOp([], [])])

    flows = [FlowAttr("+", [], I_STATE_INDEX, 0)]

    circuit = CircuitOp(
        input_state,
        output_state_type,
        input_args=[],
        body=body,
        flows=flows,
    )

    assert circuit.used_input_flow_states == []
    assert circuit.used_output_flow_states == [PauliStringAttr([("X", 0)], 1)]
