"""Tests for constraints Module"""

import re
from collections.abc import Callable, Sequence
from typing import Any

import pytest
from pytest_mock import MockerFixture
from xdsl.dialects.builtin import (
    DYNAMIC_INDEX,
    ArrayAttr,
    ArrayOfConstraint,
    IntAttr,
    IntegerType,
    StringAttr,
    i1,
    i32,
)
from xdsl.ir import Attribute
from xdsl.irdl import (
    IRDLAttrConstraint,
    IRDLOperation,
    irdl_op_definition,
    prop_def,
)
from xdsl.irdl.attributes import base
from xdsl.irdl.constraints import (
    AnyAttr,
    AnyInt,
    AtLeast,
    AttrConstraint,
    BaseAttr,
    ConstraintContext,
    EqAttrConstraint,
    EqIntConstraint,
    IntConstraint,
    IntVarConstraint,
    RangeConstraint,
    RangeOf,
    SingleOf,
    VarConstraint,
)
from xdsl.utils.exceptions import VerifyException

from deltakit_compile.dialects.common.constraints import (
    EMPTY_RANGE,
    NO_ENTRY_ARGS,
    BaseVarConstraint,
    IntTensorDimensionSizeConstraint,
    MessageIntConstraint,
    MessageRangeConstraint,
    ModuloIntConstraint,
    SetOf,
    SortedRangeOf,
    SumOver,
    TwoToThePowerOf,
)


@pytest.mark.parametrize(
    ("attrs", "underlying_constraint", "error_msg"),
    [
        ([IntAttr(1), IntAttr(2)], AnyAttr(), None),
        (
            [IntAttr(1), StringAttr("Kenton")],
            AnyAttr(),
            re.escape(
                "An attribute of base type 'builtin.int' was expected from variable 'B', "
                'but got "Kenton"'
            ),
        ),
        (
            [IntAttr(1), StringAttr("Kenton")],
            base(IntAttr),
            ".*",  # Don't care what the underlying error message of base(IntAttr) actually is
        ),
        (
            [IntAttr(1), IntAttr(1), StringAttr("Kenton")],
            AnyAttr(),
            re.escape(
                "An attribute of base type 'builtin.int' was expected from variable 'B', "
                'but got "Kenton"'
            ),
        ),
        ([StringAttr("123"), StringAttr("456")], AnyAttr(), None),
        (
            [StringAttr("123"), StringAttr("456")],
            VarConstraint("S", base(StringAttr)),
            ".*",  # Don't care what the underlying error message of VarConstraint(...) actually is
        ),
        ([StringAttr("123"), StringAttr("123")], VarConstraint("S", base(StringAttr)), None),
        ([StringAttr("123"), StringAttr("123")], EqAttrConstraint(StringAttr("123")), None),
    ],
)
def test_base_var_constraint(
    attrs: list[Attribute], underlying_constraint: AttrConstraint, error_msg: str | None
):
    """Test that BaseVarConstraint raises an error if attributes have different types, and does not
    raise an error when the types match."""
    context = ConstraintContext()

    base_var_constraint = BaseVarConstraint("B", underlying_constraint)

    assert base_var_constraint.can_infer(context.attr_variables) == underlying_constraint.can_infer(
        context.attr_variables
    )
    if underlying_constraint.can_infer(context.attr_variables):
        assert base_var_constraint.infer(context) == underlying_constraint.infer(context)

    assert base_var_constraint.mapping_type_vars({}) == BaseVarConstraint(
        "B", underlying_constraint.mapping_type_vars({})
    )

    assert base_var_constraint.variables() == underlying_constraint.variables() | {"B"}
    assert base_var_constraint.get_bases() == underlying_constraint.get_bases()

    for attr in attrs[:-1]:
        base_var_constraint.verify(attr, context)

    if error_msg is None:
        base_var_constraint.verify(attrs[-1], context)
        assert context.get_variable("B") == attrs[0]
    else:
        with pytest.raises(VerifyException, match=error_msg):
            base_var_constraint.verify(attrs[-1], context)


@pytest.mark.parametrize(
    ("input_data", "strict_increasing", "reverse", "exp_error"),
    [
        ([], True, False, None),
        ([], False, False, None),
        ([1], True, False, None),
        ([1], False, False, None),
        ([0, 10], True, False, None),
        ([0, 10], False, False, None),
        ([0, 10, 234], True, False, None),
        ([0, 10, 234], False, False, None),
        (
            [0, 10, 11],
            True,
            False,
            re.escape(
                "Sequence contains '#builtin.int<10>' and then '#builtin.int<11>' "
                "that are not strictly increasing."
            ),
        ),
        ([0, 10, 11], False, False, None),
        ([0, 10, 10], False, False, None),
        (
            [0, 10, 9],
            False,
            False,
            re.escape(
                "Sequence of attributes is not sorted: "
                "['#builtin.int<0>' < '#builtin.int<10>' > '#builtin.int<9>']"
            ),
        ),
        (
            [0, 10, 9],
            True,
            False,
            re.escape(
                "Sequence of attributes is not sorted: "
                "['#builtin.int<0>' < '#builtin.int<10>' > '#builtin.int<9>']"
            ),
        ),
        (
            [0, 10, 9],
            False,
            True,
            re.escape(
                "Sequence of attributes is not sorted in reverse order: "
                "['#builtin.int<0>' < '#builtin.int<10>' > '#builtin.int<9>']"
            ),
        ),
        (
            [0, 10, 10, 9],
            False,
            False,
            re.escape(
                "Sequence of attributes is not sorted: "
                "['#builtin.int<0>' < '#builtin.int<10>' == '#builtin.int<10>' > '#builtin.int<9>']"
            ),
        ),
        (
            [0, 10, 9],
            True,
            True,
            re.escape(
                "Sequence of attributes is not sorted in reverse order: "
                "['#builtin.int<0>' < '#builtin.int<10>' > '#builtin.int<9>']"
            ),
        ),
        (
            [12, 10, 9],
            True,
            True,
            None,
        ),
        (
            [12, 10, 10, 9],
            False,
            True,
            None,
        ),
    ],
)
def test_sorted_range_of_constraint(
    input_data: Sequence[int],
    strict_increasing: bool,
    reverse: bool,
    exp_error: str | None,
):
    """Test SortedRangeOf range constraint for correctness and raising errors."""

    @irdl_op_definition
    class TestOp(IRDLOperation):
        """Test op"""

        name = "test.test"

        int_values = prop_def(
            ArrayOfConstraint(
                SortedRangeOf(
                    RangeOf(base(IntAttr)),
                    key=lambda i: i.data // 2,
                    strictly_increasing=strict_increasing,
                    reverse=reverse,
                )
            )
        )

    input_data_attr = ArrayAttr([IntAttr(i) for i in input_data])

    op = TestOp(properties={"int_values": input_data_attr})

    if exp_error is not None:
        with pytest.raises(VerifyException, match=exp_error):
            op.verify()
    else:
        op.verify()


def never_key_getter(_: Any) -> int:
    """A key getter for SortedRangeOf SetOf, and SumOver constraints that should never get
    called."""
    pytest.fail("This key getting method should never be called.")


@pytest.mark.parametrize("reverse", [True, False])
@pytest.mark.parametrize("strictly_increasing", [True, False])
@pytest.mark.parametrize(
    ("inner_constraint", "length", "constraint_context", "expect_error"),
    [
        (RangeOf(AnyAttr()), 5, ConstraintContext(), False),
        (RangeOf(AnyAttr()).of_length(EqIntConstraint(4)), 5, ConstraintContext(), True),
        (
            RangeOf(AnyAttr()).of_length(IntVarConstraint("P", AnyInt())),
            5,
            ConstraintContext(),
            False,
        ),
        (
            RangeOf(AnyAttr()).of_length(IntVarConstraint("P", AnyInt())),
            5,
            ConstraintContext({}, {}, {"P": 4}),
            True,
        ),
    ],
)
def test_sorted_range_of_constraint_verify_length(
    reverse: bool,
    strictly_increasing: bool,
    inner_constraint: RangeConstraint,
    length: int,
    constraint_context: ConstraintContext,
    expect_error: bool,
):
    """Test that SortedRangeOf.verify_length works as expected and uses underlying constraint."""

    sorted_range_constr = SortedRangeOf(
        inner_constraint,
        key=never_key_getter,
        strictly_increasing=strictly_increasing,
        reverse=reverse,
    )
    if expect_error:
        with pytest.raises(VerifyException):
            # The error is raised from the inner constraint so we don't care what the message is.
            sorted_range_constr.verify_length(length, constraint_context)
    else:
        sorted_range_constr.verify_length(length, constraint_context)


@pytest.mark.parametrize("reverse", [True, False])
@pytest.mark.parametrize("strictly_increasing", [True, False])
def test_sorted_range_of_constraint_inference(reverse: bool, strictly_increasing: bool):
    """Test that SortedRangeOf constraint has correct inference rules and type mapping method."""

    sorted_range_constr = SortedRangeOf(
        RangeOf(var_constr := VarConstraint("I", base(IntAttr))),
        key=never_key_getter,
        strictly_increasing=strictly_increasing,
        reverse=reverse,
    )
    assert sorted_range_constr.variables() == var_constr.variables()
    assert sorted_range_constr.can_infer({"I"}, length_known=True) is True
    assert sorted_range_constr.can_infer(set(), length_known=True) is False
    assert sorted_range_constr.can_infer({"I"}, length_known=False) is False
    assert sorted_range_constr.can_infer(set(), length_known=False) is False

    ctx = ConstraintContext({"I": IntAttr(1)})
    inferred = sorted_range_constr.infer(ctx, length=4)
    assert inferred == (
        IntAttr(1),
        IntAttr(1),
        IntAttr(1),
        IntAttr(1),
    )
    assert sorted_range_constr.mapping_type_vars({}) == SortedRangeOf(
        RangeOf(var_constr.mapping_type_vars({})),
        key=never_key_getter,
        strictly_increasing=strictly_increasing,
        reverse=reverse,
    )


def never_filter(_: Any) -> bool:
    """A filter for SetOf constraints that should never get called."""
    pytest.fail("This filter method should never be called.")


@pytest.mark.parametrize(
    ("inner_constraint", "key_func", "filter_func", "attrs", "exp_error"),
    [
        (RangeOf(AnyAttr()), never_key_getter, never_filter, (), None),
        (
            RangeOf(AnyAttr()),
            lambda v: v.data,
            None,
            (IntAttr(2), IntAttr(3)),
            None,
        ),
        (
            RangeOf(AnyAttr()),
            lambda v: v.data // 2,
            None,
            (IntAttr(3), IntAttr(2)),
            re.escape(
                "Sequence contains duplicate elements: '#builtin.int<3>'(1) == '#builtin.int<2>'(1)"
            ),
        ),
        (
            RangeOf(AnyAttr()),
            lambda v: v.data // 2,
            lambda v: v.data < 3,
            (IntAttr(3), IntAttr(2)),
            None,
        ),
        (
            RangeOf(AnyAttr()).of_length(EqIntConstraint(1)),
            lambda v: v.data // 2,
            lambda v: v.data < 3,
            (IntAttr(3), IntAttr(2)),
            ".*",  # Error raised from EqIntConstraint() so we don't need to string match it.
        ),
    ],
)
def test_set_of_constraint(
    inner_constraint: RangeConstraint,
    key_func: Callable[[Any], Any],
    filter_func: Callable[[Any], bool] | None,
    attrs: Sequence[Attribute],
    exp_error: str | None,
):
    """Test SetOf range constraint raises errors on .verify() when input sequences have duplicate
    elements (after filter and mapping functions are applied) or fails the inner constraint's
    .verify() and does not raise errors when they don't have duplicates."""

    constraint = SetOf(inner_constraint, key_func, filter=filter_func)

    if exp_error is not None:
        with pytest.raises(VerifyException, match=exp_error):
            constraint.verify(attrs, ConstraintContext())
    else:
        constraint.verify(attrs, ConstraintContext())


@pytest.mark.parametrize(
    ("inner_constraint", "length", "constraint_context", "expect_error"),
    [
        (RangeOf(AnyAttr()), 5, ConstraintContext(), False),
        (RangeOf(AnyAttr()).of_length(EqIntConstraint(4)), 5, ConstraintContext(), True),
        (
            RangeOf(AnyAttr()).of_length(IntVarConstraint("P", AnyInt())),
            5,
            ConstraintContext(),
            False,
        ),
        (
            RangeOf(AnyAttr()).of_length(IntVarConstraint("P", AnyInt())),
            5,
            ConstraintContext({}, {}, {"P": 4}),
            True,
        ),
    ],
)
def test_set_of_constraint_verify_length(
    inner_constraint: RangeConstraint,
    length: int,
    constraint_context: ConstraintContext,
    expect_error: bool,
):
    """Test that SetOf.verify_length uses underlying constraint when verifying the length."""
    set_constr = SetOf(
        inner_constraint,
        key=never_key_getter,
        filter=never_filter,
    )
    if expect_error:
        with pytest.raises(VerifyException):
            # The error is raised from the inner constraint so we don't care what the message is.
            set_constr.verify_length(length, constraint_context)
    else:
        set_constr.verify_length(length, constraint_context)


def test_set_of_constraint_inference():
    """Test that SetOf constraint has correct inference rules and type mapping method."""

    set_constr = SetOf(
        RangeOf(var_constr := VarConstraint("I", base(IntAttr))),
        key=never_key_getter,
        filter=never_filter,
    )
    assert set_constr.variables() == var_constr.variables()
    assert set_constr.can_infer({"I"}, length_known=True) is True
    assert set_constr.can_infer(set(), length_known=True) is False
    assert set_constr.can_infer({"I"}, length_known=False) is False
    assert set_constr.can_infer(set(), length_known=False) is False

    ctx = ConstraintContext({"I": IntAttr(1)})
    inferred = set_constr.infer(ctx, length=4)
    assert inferred == (
        IntAttr(1),
        IntAttr(1),
        IntAttr(1),
        IntAttr(1),
    )
    assert set_constr.mapping_type_vars({}) == SetOf(
        RangeOf(var_constr.mapping_type_vars({})), key=never_key_getter, filter=never_filter
    )


@pytest.mark.parametrize(
    ("inner_constraint", "key_func", "sum_constr", "attrs", "exp_error"),
    [
        (RangeOf(AnyAttr()), never_key_getter, AnyInt(), (), None),
        (
            RangeOf(AnyAttr()),
            lambda v: v.data,
            AnyInt(),
            (IntAttr(2), IntAttr(3)),
            None,
        ),
        (
            RangeOf(AnyAttr()),
            lambda v: v.data // 2,
            EqIntConstraint(3),
            (IntAttr(3), IntAttr(2)),
            re.escape(
                "Incorrect sum over range that produced values "
                "'#builtin.int<3>' (1) + '#builtin.int<2>' (1) = 2:\nInvalid value 2, expected 3"
            ),
        ),
        (
            RangeOf(AnyAttr()),
            never_key_getter,
            EqIntConstraint(-1),
            (),
            re.escape("Incorrect sum over empty range:\nInvalid value 0, expected -1"),
        ),
        (
            RangeOf(AnyAttr()),
            lambda v: v.data // 2,
            EqIntConstraint(2),
            (IntAttr(3), IntAttr(2)),
            None,
        ),
        (
            RangeOf(AnyAttr()).of_length(EqIntConstraint(1)),
            lambda v: v.data // 2,
            EqIntConstraint(999),
            (IntAttr(3), IntAttr(2)),
            ".*",  # Error raised from EqIntConstraint() so we don't need to string match it.
        ),
    ],
)
def test_sum_over_constraint(
    inner_constraint: RangeConstraint,
    key_func: Callable[[Any], Any],
    sum_constr: IntConstraint,
    attrs: Sequence[Attribute],
    exp_error: str | None,
):
    """Test SumOver range constraint raises errors on .verify() when input sequences fails the
    inner constraint's.verify() and does not raise errors when they don't have duplicates."""

    constraint = SumOver(inner_constraint, key_func, sum_constr)

    if exp_error is not None:
        with pytest.raises(VerifyException, match=exp_error):
            constraint.verify(attrs, ConstraintContext())
    else:
        constraint.verify(attrs, ConstraintContext())


@pytest.mark.parametrize(
    ("inner_constraint", "length", "constraint_context", "expect_error"),
    [
        (RangeOf(AnyAttr()), 5, ConstraintContext(), False),
        (RangeOf(AnyAttr()).of_length(EqIntConstraint(4)), 5, ConstraintContext(), True),
        (
            RangeOf(AnyAttr()).of_length(IntVarConstraint("P", AnyInt())),
            5,
            ConstraintContext(),
            False,
        ),
        (
            RangeOf(AnyAttr()).of_length(IntVarConstraint("P", AnyInt())),
            5,
            ConstraintContext({}, {}, {"P": 4}),
            True,
        ),
    ],
)
def test_sum_over_constraint_verify_length(
    inner_constraint: RangeConstraint,
    length: int,
    constraint_context: ConstraintContext,
    expect_error: bool,
):
    """Test that SumOver.verify_length uses underlying constraint when verifying the length."""
    sum_constr = SumOver(inner_constraint, key=never_key_getter, sum_constr=AnyInt())
    if expect_error:
        with pytest.raises(VerifyException):
            # The error is raised from the inner constraint so we don't care what the message is.
            sum_constr.verify_length(length, constraint_context)
    else:
        sum_constr.verify_length(length, constraint_context)


def test_sum_over_constraint_inference():
    """Test that SumOver constraint has correct inference rules and type mapping method."""

    sum_constr = SumOver(
        range_constr := RangeOf(VarConstraint("I", base(IntAttr))),
        key=never_key_getter,
        sum_constr=(int_constr := IntVarConstraint("S", AnyInt())),
    )
    assert sum_constr.variables() == range_constr.variables() | int_constr.variables()
    for variables in [set(), {"I"}]:
        for len_known in [False, True]:
            assert sum_constr.can_infer(
                variables, length_known=len_known
            ) == range_constr.can_infer(variables, length_known=len_known)

    ctx = ConstraintContext({"I": IntAttr(1)})
    inferred = sum_constr.infer(ctx, length=4)
    assert inferred == (
        IntAttr(1),
        IntAttr(1),
        IntAttr(1),
        IntAttr(1),
    )
    assert sum_constr.mapping_type_vars({}) == SumOver(
        range_constr.mapping_type_vars({}),
        key=never_key_getter,
        sum_constr=int_constr.mapping_type_vars({}),
    )


def test_message_range_constraint():
    """Test that MessageRangeConstraint raises errors with custom messages."""
    constraint = MessageRangeConstraint(SingleOf(EqAttrConstraint(i1)), "Test")

    with pytest.raises(
        VerifyException,
        match=re.escape("Test\nUnderlying verification failure: Expected attribute i1 but got i32"),
    ):
        constraint.verify([i32], ConstraintContext())

    # Also test that it works without errors
    constraint.verify([i1], ConstraintContext())

    with pytest.raises(
        VerifyException,
        match=re.escape(
            "Test\nUnderlying verification failure: Expected a single attribute, got 2"
        ),
    ):
        constraint.verify_length(2, ConstraintContext())
    constraint.verify_length(1, ConstraintContext())


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (i1, RangeOf(i1)),
        (IntegerType, RangeOf(BaseAttr(IntegerType))),
        (IntAttr, RangeOf(BaseAttr(IntAttr))),
        (IntAttr(4), RangeOf(EqAttrConstraint(IntAttr(4)))),
    ],
)
def test_message_range_constraint_init(
    a: RangeConstraint | IRDLAttrConstraint, b: RangeConstraint | IRDLAttrConstraint
):
    assert MessageRangeConstraint(a, "test") == MessageRangeConstraint(b, "test")


def test_message_range_constraint_passthrough_methods(mocker: MockerFixture):
    """Test that MessageRangeConstraint calls the appropriate inner constraint methods."""
    inner_constraint = RangeOf(i32)
    mocked = mocker.Mock(spec=inner_constraint, wraps=inner_constraint)
    constraint = MessageRangeConstraint(mocked, "Test")

    assert constraint.verify([], ConstraintContext({"a": IntAttr(-1)})) is None
    mocked.verify.assert_called_once_with([], ConstraintContext({"a": IntAttr(-1)}))

    assert constraint.variables() == set()
    mocked.variables.assert_called_once_with()

    assert constraint.can_infer({"a", "b", "c"}, length_known=True) is True
    mocked.can_infer.assert_called_once_with({"a", "b", "c"}, length_known=True)

    assert constraint.infer(ConstraintContext({"b": IntAttr(-1)}), length=1) == (i32,)
    mocked.infer.assert_called_once_with(ConstraintContext({"b": IntAttr(-1)}), length=1)

    mapped = constraint.mapping_type_vars({})
    assert isinstance(mapped, MessageRangeConstraint)
    assert mapped.message == constraint.message
    mocked.mapping_type_vars.assert_called_once_with({})


@pytest.mark.parametrize("constr", [EMPTY_RANGE, NO_ENTRY_ARGS])
def test_empty_range_constraint(constr: RangeConstraint):
    assert constr.can_infer(set(), length_known=False)
    assert constr.can_infer(set(), length_known=True)
    assert constr.infer(ConstraintContext(), length=None) == ()
    assert constr.variables() == set()
    constr.verify([], ConstraintContext())
    assert not constr.verifies([IntAttr(1)])
    with pytest.raises(
        VerifyException,
        match=re.escape("incorrect length for range variable:\nInvalid value 2, expected 0"),
    ):
        constr.verify([IntAttr(1), IntAttr(2)], ConstraintContext())


def test_no_entry_args_error() -> None:
    with pytest.raises(
        VerifyException,
        match=re.escape(
            "Expected 0 entry arguments\n"
            "Underlying verification failure: incorrect length for range variable:\n"
            "Invalid value 3, expected 0"
        ),
    ):
        NO_ENTRY_ARGS.verify([IntAttr(1), IntAttr(2), IntAttr(2)], ConstraintContext())


def test_message_int_constraint():
    """Test that MessageIntConstraint raises errors with custom messages."""
    constraint = MessageIntConstraint(0, "Test")

    with pytest.raises(
        VerifyException,
        match=re.escape("Test\nUnderlying verification failure: Invalid value 5, expected 0"),
    ):
        constraint.verify(5, ConstraintContext())

    # Also test that it works without errors
    constraint.verify(0, ConstraintContext())


def test_message_int_constraint_passthrough_methods(mocker: MockerFixture):
    """Test that MessageIntConstraint calls the appropriate inner constraint methods."""
    inner_constraint = EqIntConstraint(10)
    mocked = mocker.Mock(spec=inner_constraint, wraps=inner_constraint)
    constraint = MessageIntConstraint(mocked, "Test")

    assert constraint.verify(10, ConstraintContext({"a": IntAttr(-1)})) is None
    mocked.verify.assert_called_once_with(10, ConstraintContext({"a": IntAttr(-1)}))

    assert constraint.variables() == set()
    mocked.variables.assert_called_once_with()

    assert constraint.can_infer({"a", "b", "c"}) is True
    mocked.can_infer.assert_called_once_with({"a", "b", "c"})

    assert constraint.infer(ConstraintContext({"b": IntAttr(-1)})) == 10
    mocked.infer.assert_called_once_with(ConstraintContext({"b": IntAttr(-1)}))

    mapped = constraint.mapping_type_vars({})
    assert isinstance(mapped, MessageIntConstraint)
    assert mapped.message == constraint.message
    mocked.mapping_type_vars.assert_called_once_with({})


@pytest.mark.parametrize(
    ("inner_constraint", "i", "exp_error"),
    [
        (
            AnyInt(),
            0,
            re.escape("Expected 0 = 2**n for some integer n, but n is not well defined."),
        ),
        (
            AnyInt(),
            -1,
            re.escape("Expected -1 = 2**n for some integer n, but n is not well defined."),
        ),
        (
            AnyInt(),
            10,
            re.escape("Expected 10 = 2**n for some integer n, but log2(10) is not an integer."),
        ),
        (AnyInt(), 1, None),
        (AtLeast(3), 8, None),
        (
            AtLeast(4),
            8,
            re.escape("Got i = 8, so for i = 2**n, n = 3: expected integer >= 4, got 3"),
        ),
    ],
)
def test_two_to_the_power_of_constraint(
    inner_constraint: IntConstraint,
    i: int,
    exp_error: str | None,
):
    """Test TwoRaisedTo int constraint raises errors on .verify() when input integer does not have
    a log2(i) that satisfies the inner constraint.

    Arguments:
        inner_constraint: A constraint to pass to TwoToThePowerOf
        i: A value to verify
        exp_error: A string to match the VerifyException if ``i`` should not verify, else None if it
            no VerifyException should be raised.
    """

    constraint = TwoToThePowerOf(inner_constraint)

    if exp_error is not None:
        with pytest.raises(VerifyException, match=exp_error):
            constraint.verify(i, ConstraintContext())
    else:
        constraint.verify(i, ConstraintContext())


def test_two_to_the_power_of_constraint_inference():
    """Test that TwoRaisedTo constraint has correct inference rules and type mapping method."""

    two_to_the_power_of_constr = TwoToThePowerOf(inner := IntVarConstraint("I", AnyInt()))
    assert two_to_the_power_of_constr.variables() == inner.variables()
    for variables in [set(), {"I"}]:
        assert two_to_the_power_of_constr.can_infer(variables) == inner.can_infer(variables)

    ctx = ConstraintContext({}, {}, {"I": 1})
    inferred = two_to_the_power_of_constr.infer(ctx)
    assert inferred == 2

    assert two_to_the_power_of_constr.mapping_type_vars({}) == TwoToThePowerOf(
        inner.mapping_type_vars({})
    )


@pytest.mark.parametrize(
    ("value_constr", "value", "divisor_constr", "divisor", "remainder_constr", "exp_error"),
    [
        (1, 1, 1, 1, 0, None),
        (1, 1, 1, 1, 1, re.escape("Tried to verify 1 % 1 = 0. Invalid value 0, expected 1")),
        (10, 10, 3, 3, 2, re.escape("Tried to verify 10 % 3 = 1. Invalid value 1, expected 2")),
        ("A", 10, "B", 3, 2, re.escape("Tried to verify 10 % 3 = 1. Invalid value 1, expected 2")),
        ("A", 10, "B", 3, "C", None),
        (10, 11, 1, 1, 0, re.escape("Invalid value 11, expected 10")),
        (10, 10, 1, 2, 0, re.escape("Invalid value 2, expected 1")),
        (10, 10, IntVarConstraint("B", AtLeast(2)), 2, 0, None),
        (
            10,
            10,
            IntVarConstraint("B", AtLeast(2)),
            1,
            0,
            re.escape("expected integer >= 2, got 1"),
        ),
        (
            "A",
            10,
            "B",
            3,
            AtLeast(3),
            re.escape("Tried to verify 10 % 3 = 1. expected integer >= 3, got 1"),
        ),
        (
            "A",
            10,
            "B",
            6,
            AtLeast(3),
            None,
        ),
        ("A", 10, "B", 0, 0, re.escape("Divide by zero error, cannot take x % 0.")),
    ],
)
def test_int_modulo_verifies_correctly(
    value_constr: IntConstraint | str | int,
    value: int,
    divisor_constr: IntConstraint | str | int,
    divisor: int,
    remainder_constr: IntConstraint,
    exp_error: str | None,
):
    """Tests that ModuloIntConstraint correctly verifies inputs no matter the order of
    verification, and has correctly defined/implemented methods."""
    m1, m2 = ModuloIntConstraint.make_pair(value_constr, divisor_constr, remainder_constr)
    assert m1.is_divisor != m2.is_divisor
    assert m1.value_constr == m2.value_constr
    assert m1.divisor_constr == m1.divisor_constr
    assert m1.remainder_constr == m2.remainder_constr

    assert m1.variables() == m1.value_constr.variables()
    assert m2.variables() == m2.divisor_constr.variables()
    assert m1.can_infer(set()) == m1.value_constr.can_infer(set())
    assert m2.can_infer(set()) == m2.divisor_constr.can_infer(set())

    if m1.can_infer(set()):
        assert m1.infer(ConstraintContext()) == m1.value_constr.infer(ConstraintContext())
    if m2.can_infer(set()):
        assert m2.infer(ConstraintContext()) == m2.divisor_constr.infer(ConstraintContext())

    assert m1.mapping_type_vars({}) == m1
    assert m2.mapping_type_vars({}) == m2

    if exp_error is None:
        context = ConstraintContext()
        m1.verify(value, context)
        m2.verify(divisor, context)
        context = ConstraintContext()
        m2.verify(divisor, context)
        m1.verify(value, context)
    else:
        context = ConstraintContext()
        with pytest.raises(VerifyException, match=exp_error):  # noqa: PT012
            m1.verify(value, context)
            m2.verify(divisor, context)
        context = ConstraintContext()
        with pytest.raises(VerifyException, match=exp_error):  # noqa: PT012
            m2.verify(divisor, context)
            m1.verify(value, context)


def test_making_invalid_modulo_int_constraint():
    """Test that ModuloIntConstraint cannot be inited with invalid child constraints."""
    uninferable = AtLeast(3)
    inferable = IntVarConstraint("X", AnyInt())
    with pytest.raises(
        ValueError,
        match=re.escape(
            "Cannot construct a verifiable ModuloIntConstraint if the constraint on the value "
            "can not be inferred once it has been verified."
        ),
    ):
        ModuloIntConstraint(True, uninferable, inferable, AnyInt())
    with pytest.raises(
        ValueError,
        match=re.escape(
            "Cannot construct a verifiable ModuloIntConstraint if the constraint on the divisor "
            "can not be inferred once it has been verified."
        ),
    ):
        ModuloIntConstraint(True, inferable, uninferable, AnyInt())


@pytest.mark.parametrize(
    ("i", "exp_error"),
    [
        (1, None),
        (5, None),
        (DYNAMIC_INDEX, None),
        (0, re.escape("Invalid value 0, expected a strictly positive integer or DYNAMIC_INDEX")),
        (-1, re.escape("Invalid value -1, expected a strictly positive integer or DYNAMIC_INDEX")),
    ],
)
def test_tensor_size_constraint(i: int, exp_error: str | None) -> None:
    """Test IntTensorDimensionSizeConstraint int constraint raises errors on .verify() when input
    integer is not a valid tensor dimension.

    Arguments:
        i: A value to verify
        exp_error: A string to match the VerifyException if ``i`` should not verify, else None if it
            no VerifyException should be raised.
    """

    constraint = IntTensorDimensionSizeConstraint()

    if exp_error is not None:
        with pytest.raises(VerifyException, match=exp_error):
            constraint.verify(i, ConstraintContext())
    else:
        constraint.verify(i, ConstraintContext())

    assert constraint.mapping_type_vars({}) == constraint
