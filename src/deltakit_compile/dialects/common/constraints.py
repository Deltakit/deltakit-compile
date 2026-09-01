# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Additional IRDL constraints to make writing dialects easier."""

from __future__ import annotations

import itertools
from collections.abc import Callable, Hashable, Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from typing import Any, Final, Generic, cast

from typing_extensions import TypeForm, TypeVar, override
from xdsl.dialects.builtin import DYNAMIC_INDEX
from xdsl.ir import Attribute
from xdsl.irdl import AnyAttr, IRDLAttrConstraint, RangeOf, get_int_constraint
from xdsl.irdl.constraints import (
    AnyInt,
    AttrConstraint,
    ConstraintContext,
    EqIntConstraint,
    IntConstraint,
    IntVarConstraint,
    RangeConstraint,
)
from xdsl.utils.exceptions import VerifyException

AttributeT_co = TypeVar("AttributeT_co", bound=Attribute, covariant=True, default=Attribute)


@dataclass(frozen=True)
class BaseVarConstraint(AttrConstraint[AttributeT_co], Generic[AttributeT_co]):
    """Constrain attributes such that:
        - `constraint` holds for each attribute
        - every attribute has the same base (`Attribute` type).

    For example, if the constraint `BaseVarConstraint("var", AnyOf([IntegerType, IndexType]))`
    was applied in one Operation to each of: `IntegerType(1)`, `IntegerType(32)`, and
    `IntegerType(64)` then this would pass.
    But if applied to: `IntegerType(1)`, `IntegerType(32)`, and `IndexType()` this would fail since
    all of the given `Attribute`s do not share a common base type: `IntegerType is not IndexType`.
    """

    name: str
    """The variable name used in the `ConstraintContext` to track the type of the constrained
    `Attribute`s. This must be unique for each mutually exclusive group of `Attributes` that are
    constrained to have the same `Attribute` type. This variable name is exposed as part of the
    error message provided when the constraint does not how, so should be intelligible to users."""

    constraint: AttrConstraint[AttributeT_co]
    """An inner constraint that also constrains every `Attribute` seen by this constraint."""

    @override
    def verify(
        self,
        attr: Attribute,
        constraint_context: ConstraintContext,
    ) -> None:
        self.constraint.verify(attr, constraint_context)
        ctx_attr = constraint_context.get_variable(self.name)
        if ctx_attr is not None:
            if type(ctx_attr) is not type(attr):
                msg = (
                    f"An attribute of base type '{type(ctx_attr).name}' was expected from variable "
                    f"'{self.name}', but got {attr}"
                )
                raise VerifyException(msg)
        else:
            constraint_context.set_attr_variable(self.name, attr)

    @override
    def variables(self) -> set[str]:
        return self.constraint.variables() | {self.name}

    @override
    def infer(self, context: ConstraintContext) -> AttributeT_co:
        return self.constraint.infer(context)

    @override
    def can_infer(self, var_constraint_names: AbstractSet[str]) -> bool:
        return self.constraint.can_infer(var_constraint_names)

    @override
    def get_bases(self) -> set[type[Attribute]] | None:
        return self.constraint.get_bases()

    @override
    def mapping_type_vars(
        self, type_var_mapping: Mapping[TypeVar, AttrConstraint | IntConstraint]
    ) -> BaseVarConstraint[AttributeT_co]:
        return BaseVarConstraint(self.name, self.constraint.mapping_type_vars(type_var_mapping))


@dataclass(frozen=True)
class SortedRangeOf(RangeConstraint[AttributeT_co]):
    """
    Constrain each element in a range to satisfy a given constraint, and be sorted
    """

    constr: RangeConstraint[AttributeT_co]
    """An inner RangeConstraint."""

    key: Callable[[AttributeT_co], Any]
    """A function to use to compare attributes when sorting."""
    reverse: bool = field(default=False, kw_only=True)
    """Whether the order of the range should be in descending order."""

    strictly_increasing: bool = False
    """Strictly increasing means that all consecutive pairs of elements are unambiguously ordered
    when self.key is used to sort them, such that for each pairwise `a` and `b`, `key(a) < key(b)`.
    This can be used to ensure uniqueness based on the given key."""

    @override
    def verify(
        self,
        attrs: Sequence[Attribute],
        constraint_context: ConstraintContext,
    ) -> None:
        self.constr.verify(attrs, constraint_context)
        # If self.constr.verify() hasn't raised an error this casting is correct.
        attrs = cast(Sequence[AttributeT_co], attrs)
        sorted_attrs = sorted(attrs, key=self.key, reverse=self.reverse)
        if sorted_attrs != list(attrs):
            attr_string = f"'{attrs[0]}'"
            prev_key = self.key(attrs[0])
            for attr in attrs[1:]:
                next_key = self.key(attr)
                if prev_key < next_key:
                    attr_string += " < "
                elif next_key < prev_key:
                    attr_string += " > "
                else:
                    attr_string += " == "
                attr_string += f"'{attr}'"
                prev_key = next_key

            reverse_msg = " in reverse order" if self.reverse else ""
            msg = f"Sequence of attributes is not sorted{reverse_msg}: [{attr_string}]"
            raise VerifyException(msg)
        if self.strictly_increasing:
            if self.reverse:
                sorted_attrs = list(reversed(sorted_attrs))
            for a, b in itertools.pairwise(sorted_attrs):
                if not self.key(a) < self.key(b):
                    msg = (
                        f"Sequence contains '{a}' and then '{b}' that are not strictly increasing."
                    )
                    raise VerifyException(msg)

    @override
    def verify_length(self, length: int, constraint_context: ConstraintContext) -> None:
        return self.constr.verify_length(length, constraint_context)

    @override
    def variables(self) -> set[str]:
        return self.constr.variables()

    @override
    def can_infer(self, var_constraint_names: AbstractSet[str], *, length_known: bool) -> bool:
        return self.constr.can_infer(var_constraint_names, length_known=length_known)

    @override
    def infer(
        self,
        context: ConstraintContext,
        *,
        length: int | None,
    ) -> Sequence[AttributeT_co]:
        return self.constr.infer(context, length=length)

    @override
    def mapping_type_vars(
        self, type_var_mapping: Mapping[TypeVar, AttrConstraint | IntConstraint]
    ) -> SortedRangeOf[AttributeT_co]:
        return SortedRangeOf(
            constr=self.constr.mapping_type_vars(type_var_mapping),
            key=self.key,
            reverse=self.reverse,
            strictly_increasing=self.strictly_increasing,
        )


_H = TypeVar("_H", bound=Hashable, default=Hashable)


@dataclass(frozen=True)
class SetOf(RangeConstraint[AttributeT_co], Generic[AttributeT_co, _H]):
    """
    Constrain an attribute range to have unique elements.
    """

    constr: RangeConstraint[AttributeT_co]
    """An underlying constraint on the attribute range that is also applied."""
    key: Callable[[AttributeT_co], _H] = field(default=lambda a: a)
    """A function to use to compare attributes when checking they are unique."""
    filter: Callable[[AttributeT_co], bool] | None = None
    """A optional function to use to filter attributes before comparing for duplicates."""

    @override
    def verify(
        self,
        attrs: Sequence[Attribute],
        constraint_context: ConstraintContext,
    ) -> None:
        self.constr.verify(attrs, constraint_context)
        # If self.constr.verify() hasn't raised an error this casting is correct.
        typed_attrs = cast(Sequence[AttributeT_co], attrs)
        if self.filter is not None:
            typed_attrs = [attr for attr in typed_attrs if self.filter(attr)]
        keys = {self.key(attr) for attr in typed_attrs}
        if len(keys) != len(typed_attrs):
            equality_buckets: dict[_H, list[AttributeT_co]] = {}
            for attr in typed_attrs:
                key = self.key(attr)
                equality_buckets.setdefault(key, []).append(attr)
            equality_buckets = {k: v for k, v in equality_buckets.items() if len(v) > 1}
            attr_strings = [
                " == ".join(f"'{attr!s}'({k})" for attr in v) for k, v in equality_buckets.items()
            ]
            msg = f"Sequence contains duplicate elements: {', '.join(attr_strings)}"
            raise VerifyException(msg)

    @override
    def verify_length(self, length: int, constraint_context: ConstraintContext) -> None:
        return self.constr.verify_length(length, constraint_context)

    @override
    def variables(self) -> set[str]:
        return self.constr.variables()

    @override
    def can_infer(self, var_constraint_names: AbstractSet[str], *, length_known: bool) -> bool:
        return self.constr.can_infer(var_constraint_names, length_known=length_known)

    @override
    def infer(self, context: ConstraintContext, *, length: int | None) -> Sequence[AttributeT_co]:
        return self.constr.infer(context, length=length)

    @override
    def mapping_type_vars(
        self, type_var_mapping: Mapping[TypeVar, AttrConstraint | IntConstraint]
    ) -> SetOf[AttributeT_co]:
        return SetOf(
            constr=self.constr.mapping_type_vars(type_var_mapping), key=self.key, filter=self.filter
        )


@dataclass(frozen=True)
class SumOver(RangeConstraint[AttributeT_co], Generic[AttributeT_co]):
    """
    Constrain an attribute range's sum by an IntConstraint.
    """

    constr: RangeConstraint[AttributeT_co]
    """An underlying constraint on the attribute range that is also applied."""
    key: Callable[[AttributeT_co], int]
    """A function to use to map each attribute to an integer to sum together."""
    sum_constr: IntConstraint
    """An IntConstraint that constrains the result of summing over the range."""

    @override
    def verify(
        self,
        attrs: Sequence[Attribute],
        constraint_context: ConstraintContext,
    ) -> None:
        self.constr.verify(attrs, constraint_context)
        # If self.constr.verify() hasn't raised an error this casting is correct.
        typed_attrs = cast(Sequence[AttributeT_co], attrs)
        values = [self.key(attr) for attr in typed_attrs]
        value_sum = sum(values)
        try:
            self.sum_constr.verify(value_sum, constraint_context)
        except VerifyException as e:
            if values:
                value_strings = [
                    f"'{attr}' ({val})" for attr, val in zip(typed_attrs, values, strict=True)
                ]
                msg = (
                    "Incorrect sum over range that produced values "
                    f"{' + '.join(value_strings)} = {value_sum}:\n{e!s}"
                )
            else:
                msg = f"Incorrect sum over empty range:\n{e!s}"
            raise VerifyException(msg) from e

    @override
    def verify_length(self, length: int, constraint_context: ConstraintContext) -> None:
        return self.constr.verify_length(length, constraint_context)

    @override
    def variables(self) -> set[str]:
        return self.constr.variables() | self.sum_constr.variables()

    @override
    def can_infer(self, var_constraint_names: AbstractSet[str], *, length_known: bool) -> bool:
        return self.constr.can_infer(var_constraint_names, length_known=length_known)

    @override
    def infer(self, context: ConstraintContext, *, length: int | None) -> Sequence[AttributeT_co]:
        return self.constr.infer(context, length=length)

    @override
    def mapping_type_vars(
        self, type_var_mapping: Mapping[TypeVar, AttrConstraint | IntConstraint]
    ) -> SumOver[AttributeT_co]:
        return SumOver(
            constr=self.constr.mapping_type_vars(type_var_mapping),
            key=self.key,
            sum_constr=self.sum_constr.mapping_type_vars(type_var_mapping),
        )


@dataclass(frozen=True, init=False)
class MessageRangeConstraint(RangeConstraint[AttributeT_co], Generic[AttributeT_co]):
    """
    Attach a message to an RangeConstraint, to provide more context when the constraint
    is not satisfied.
    """

    constr: RangeConstraint[AttributeT_co]
    """The inner constraint each int seen by this constraint is actually constrained by."""
    message: str
    """The message attached to the error message provided when `constr` does not verify."""

    def __init__(
        self,
        constr: RangeConstraint[AttributeT_co] | IRDLAttrConstraint[AttributeT_co],
        message: str,
    ):
        if not isinstance(constr, RangeConstraint):
            constr = RangeOf(constr)
        object.__setattr__(self, "constr", constr)
        object.__setattr__(self, "message", message)

    @override
    def verify(
        self,
        attrs: Sequence[Attribute],
        constraint_context: ConstraintContext,
    ) -> None:
        try:
            return self.constr.verify(attrs, constraint_context)
        except VerifyException as e:
            msg = f"{self.message}\nUnderlying verification failure: {e.args[0]}"
            raise VerifyException(msg, *e.args[1:]) from None

    @override
    def verify_length(self, length: int, constraint_context: ConstraintContext) -> None:
        try:
            return self.constr.verify_length(length, constraint_context)
        except VerifyException as e:
            msg = f"{self.message}\nUnderlying verification failure: {e.args[0]}"
            raise VerifyException(msg, *e.args[1:]) from None

    @override
    def variables(self) -> set[str]:
        return self.constr.variables()

    @override
    def can_infer(self, var_constraint_names: AbstractSet[str], *, length_known: bool) -> bool:
        return self.constr.can_infer(var_constraint_names, length_known=length_known)

    @override
    def infer(self, context: ConstraintContext, *, length: int | None) -> Sequence[AttributeT_co]:
        return self.constr.infer(context, length=length)

    @override
    def mapping_type_vars(
        self, type_var_mapping: Mapping[TypeVar, AttrConstraint | IntConstraint]
    ) -> MessageRangeConstraint[AttributeT_co]:
        return MessageRangeConstraint(self.constr.mapping_type_vars(type_var_mapping), self.message)


EMPTY_RANGE: Final[RangeConstraint] = RangeOf(AnyAttr()).of_length(0)
"""Constrains a range to be empty - i.e. of length 0."""

NO_ENTRY_ARGS: Final[RangeConstraint] = MessageRangeConstraint(
    EMPTY_RANGE, "Expected 0 entry arguments"
)
"""Used to constrain regions defs to have no block arguments."""


@dataclass(frozen=True, init=False)
class MessageIntConstraint(IntConstraint):
    """
    Attach a message to an IntConstraint, to provide more context when the constraint
    is not satisfied.
    """

    constr: IntConstraint
    """The inner constraint each int seen by this constraint is actually constrained by."""
    message: str
    """The message attached to the error message provided when `constr` does not verify."""

    def __init__(
        self,
        constr: IntConstraint | int | TypeForm[int],
        message: str,
    ):
        if not isinstance(constr, IntConstraint):
            constr = get_int_constraint(constr)
        object.__setattr__(self, "constr", constr)
        object.__setattr__(self, "message", message)

    @override
    def verify(
        self,
        i: int,
        constraint_context: ConstraintContext,
    ) -> None:
        try:
            return self.constr.verify(i, constraint_context)
        except VerifyException as e:
            msg = f"{self.message}\nUnderlying verification failure: {e.args[0]}"
            raise VerifyException(
                msg,
                *e.args[1:],
            ) from None

    @override
    def variables(self) -> set[str]:
        return self.constr.variables()

    @override
    def can_infer(self, var_constraint_names: AbstractSet[str]) -> bool:
        return self.constr.can_infer(var_constraint_names)

    @override
    def infer(self, context: ConstraintContext) -> int:
        return self.constr.infer(context)

    @override
    def mapping_type_vars(
        self, type_var_mapping: Mapping[TypeVar, AttrConstraint | IntConstraint]
    ) -> MessageIntConstraint:
        return MessageIntConstraint(self.constr.mapping_type_vars(type_var_mapping), self.message)


@dataclass(frozen=True)
class TwoToThePowerOf(IntConstraint):
    """Constrains that base-2 log of the int satisfies the underlying constraint. If the log of the
    value is not an integer this will not verify.

    Attributes:
        constr: The constraint that this ``TwoToThePowerOf`` constraint applies to each integer
            base-2 logarithm of the input int.

    Args:
        constr: A constraint to apply to the base-2 logarithm of the value that TwoToThePowerOf
            constrains.
    """

    constr: IntConstraint

    @override
    def verify(
        self,
        i: int,
        constraint_context: ConstraintContext,
    ) -> None:
        if i <= 0:
            msg = f"Expected {i} = 2**n for some integer n, but n is not well defined."
            raise VerifyException(msg) from None

        if i.bit_count() != 1:
            msg = f"Expected {i} = 2**n for some integer n, but log2({i}) is not an integer."
            raise VerifyException(msg)

        log_val = i.bit_length() - 1
        try:
            self.constr.verify(log_val, constraint_context)
        except VerifyException as e:
            msg = f"Got i = {i}, so for i = 2**n, n = {log_val}: " + e.args[0]
            raise VerifyException(msg) from e

    @override
    def variables(self) -> set[str]:
        return self.constr.variables()

    @override
    def can_infer(self, var_constraint_names: AbstractSet[str]) -> bool:
        return self.constr.can_infer(var_constraint_names)

    @override
    def infer(self, context: ConstraintContext) -> int:
        return 2 ** self.constr.infer(context)

    @override
    def mapping_type_vars(
        self, type_var_mapping: Mapping[TypeVar, AttrConstraint | IntConstraint]
    ) -> TwoToThePowerOf:
        return TwoToThePowerOf(self.constr.mapping_type_vars(type_var_mapping))


@dataclass(frozen=True)
class IntTensorDimensionSizeConstraint(IntConstraint):
    """Constrain an integer to be a valid dimension size for a tensor."""

    allow_zero_length: bool = False

    @override
    def verify(self, i: int, constraint_context: ConstraintContext) -> None:
        if (i + self.allow_zero_length) <= 0 and i != DYNAMIC_INDEX:
            msg = (
                f"Invalid value {i}, expected a "
                f"{'non-negative' if self.allow_zero_length else 'strictly positive'}"
                " integer or DYNAMIC_INDEX"
            )
            raise VerifyException(msg)

    @override
    def mapping_type_vars(
        self, type_var_mapping: Mapping[TypeVar, AttrConstraint | IntConstraint]
    ) -> IntConstraint:
        return self


@dataclass(frozen=True)
class ModuloIntConstraint(IntConstraint):
    """Constrains ints to have a `value % divisor == remainder` relationship.

    This constraint combines multiple sub-constraints together. Initialising this directly is not
    recommended, use ``ModuloIntConstraint.make_pair`` to create the appropriate ``IntConstraint``s
    for the value and divisor that will then apply this constraint when verified.
    """

    is_divisor: bool
    value_constr: IntConstraint
    divisor_constr: IntConstraint
    remainder_constr: IntConstraint = field(default_factory=lambda: EqIntConstraint(0))

    def __post_init__(self) -> None:
        """Checks that the given constraints are solvable."""
        msg = (
            "Cannot construct a verifiable ModuloIntConstraint if the constraint on the {} can "
            "not be inferred once it has been verified."
        )
        if not self.value_constr.can_infer(self.value_constr.variables()):
            raise ValueError(msg.format("value"))
        if not self.divisor_constr.can_infer(self.divisor_constr.variables()):
            raise ValueError(msg.format("divisor"))

    @override
    def verify(
        self,
        i: int,
        constraint_context: ConstraintContext,
    ) -> None:
        value, divisor = None, None
        if self.is_divisor:
            self.divisor_constr.verify(i, constraint_context)
            divisor = i
        else:
            self.value_constr.verify(i, constraint_context)
            value = i

        if value is None and self.value_constr.can_infer(constraint_context.int_variables):
            value = self.value_constr.infer(constraint_context)
        if divisor is None and self.divisor_constr.can_infer(constraint_context.int_variables):
            divisor = self.divisor_constr.infer(constraint_context)
        if divisor == 0:
            msg = "Divide by zero error, cannot take x % 0."
            raise VerifyException(msg)
        if value is not None and divisor is not None:
            remainder = value % divisor
            try:
                self.remainder_constr.verify(remainder, constraint_context)
            except VerifyException as e:
                msg = f"Tried to verify {value} % {divisor} = {remainder}. " + e.args[0]
                raise VerifyException(msg) from e

    @override
    def variables(self) -> set[str]:
        return self.divisor_constr.variables() if self.is_divisor else self.value_constr.variables()

    @override
    def can_infer(self, var_constraint_names: AbstractSet[str]) -> bool:
        return (
            self.divisor_constr.can_infer(var_constraint_names)
            if self.is_divisor
            else self.value_constr.can_infer(var_constraint_names)
        )

    @override
    def infer(self, context: ConstraintContext) -> int:
        return (
            self.divisor_constr.infer(context)
            if self.is_divisor
            else self.value_constr.infer(context)
        )

    @override
    def mapping_type_vars(
        self, type_var_mapping: Mapping[TypeVar, AttrConstraint | IntConstraint]
    ) -> ModuloIntConstraint:
        return ModuloIntConstraint(
            self.is_divisor,
            self.value_constr.mapping_type_vars(type_var_mapping),
            self.divisor_constr.mapping_type_vars(type_var_mapping),
            self.remainder_constr.mapping_type_vars(type_var_mapping),
        )

    @staticmethod
    def make_pair(
        value: int | str | IntConstraint,
        divisor: int | str | IntConstraint,
        remainder: int | str | IntConstraint = 0,
    ) -> tuple[ModuloIntConstraint, ModuloIntConstraint]:
        """Makes a pair of ``ModuloIntConstraint`` that verify the 'value' and 'divisor' have the
        relationship 'value' % 'divisor' == 'remainder'.

        Args:
            value: The constraint on 'value', which must be inferable once verified.
            divisor: The constraint on 'divisor', which must be inferable once verified.
            remainder: The constraint on 'remainder', which will be verified once both `value` and
                `divisor` have been.

        Returns:
            The ``IntConstraint`` for the 'value' and the ``IntConstraint`` for the 'divisor'.
        """

        def coerce(v: int | str | IntConstraint) -> IntConstraint:
            if isinstance(v, int):
                v = EqIntConstraint(v)
            elif isinstance(v, str):
                v = IntVarConstraint(v, AnyInt())
            return v

        value, divisor, remainder = tuple(coerce(v) for v in (value, divisor, remainder))

        return (
            ModuloIntConstraint(False, value, divisor, remainder),
            ModuloIntConstraint(True, value, divisor, remainder),
        )
