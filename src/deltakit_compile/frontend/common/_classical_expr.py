# (c) Copyright Riverlane 2025-2026. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from typing_extensions import override
from xdsl.dialects.builtin import IntegerType
from xdsl.ir import Attribute

from deltakit_compile.frontend.common._builder import BaseAPIObject
from deltakit_compile.frontend.common._exceptions import (
    DifferentBuildersError,
)

if TYPE_CHECKING:
    from deltakit_compile.frontend.common._annotations import Observable


class ClassicalExpression(BaseAPIObject):
    """
    Base class for the SSA based classical variable structures.

    An expression can only result in a boolean value.
    """

    @property
    @override
    def _identifier_prefix(self) -> str:
        return "cexpr"

    @staticmethod
    def coerce(var: ClassicalExpression | int | bool) -> ClassicalExpression:
        """Helper to convert builtin Python ints and bools into Const ClassicalExpressions.

        Args:
            var: an instance that will be coerced to a ``Const``.

        Returns:
            A ``ClassicalExpression`` instance representing the provided ``var``.
        """
        if isinstance(var, ClassicalExpression):
            return var
        return Const(bool(var))

    @override
    def __eq__(self, other: ClassicalExpression | int | bool) -> ClassicalExpression:  # type: ignore[override]  # ty:ignore[invalid-method-override]
        if not isinstance(other, ClassicalExpression | int | bool):
            msg = f"Cannot evaluate '{self} == {other}'"
            raise NotImplementedError(msg)
        return ClassicalBinaryExpression(self, "==", ClassicalExpression.coerce(other))

    @override
    def __ne__(self, other: ClassicalExpression | int | bool) -> ClassicalExpression:  # type: ignore[override]  # ty:ignore[invalid-method-override]
        if not isinstance(other, ClassicalExpression | int | bool):
            msg = f"Cannot evaluate '{self} != {other}'"
            raise NotImplementedError(msg)
        return ClassicalBinaryExpression(self, "!=", ClassicalExpression.coerce(other))

    def __and__(self, other: ClassicalExpression | int | bool) -> ClassicalExpression:
        return ClassicalBinaryExpression(self, "&", ClassicalExpression.coerce(other))

    def __rand__(self, other: ClassicalExpression | int | bool) -> ClassicalExpression:
        return ClassicalBinaryExpression(ClassicalExpression.coerce(other), "&", self)

    def __or__(self, other: ClassicalExpression | int | bool) -> ClassicalExpression:
        return ClassicalBinaryExpression(self, "|", ClassicalExpression.coerce(other))

    def __ror__(self, other: ClassicalExpression | int | bool) -> ClassicalExpression:
        return ClassicalBinaryExpression(ClassicalExpression.coerce(other), "|", self)

    @override
    def __hash__(self) -> int:
        msg = f"Cannot meaningfully implement {type(self).__name__}.__hash__"
        raise NotImplementedError(msg)


class ClassicalBinaryExpression(ClassicalExpression):
    """A binary expression of two sub-expressions.

    Args:
        lhs: left hand side of the expression.
        cmd: binary operator representing the expression.
        rhs: right hand side of the expression.

    Raises:
        DifferentBuildersError: if ``lhs`` and ``rhs`` do not have the same builder.
    """

    def __init__(
        self,
        lhs: ClassicalExpression,
        cmd: Literal["==", "!=", "|", "&", "^"],
        rhs: ClassicalExpression,
    ) -> None:
        super().__init__()
        self._lhs = lhs
        self._cmd: Literal["==", "!=", "|", "&", "^"] = cmd
        self._rhs = rhs

        # If both lhs and rhs have a builder, it should be the same instance. Attach self to this
        # builder if that is the case.
        msg = "Cannot create a binary expression from results attached to different builders."
        if lhs._is_attached and rhs._is_attached and lhs._builder is not rhs._builder:
            raise DifferentBuildersError(msg)

    @property
    def lhs(self) -> ClassicalExpression:
        return self._lhs

    @property
    def cmd(self) -> Literal["==", "!=", "|", "&", "^"]:
        return self._cmd

    @property
    def rhs(self) -> ClassicalExpression:
        return self._rhs

    @override
    def __str__(self) -> str:
        return f"({self.lhs} {self.cmd} {self.rhs})"


class Const(ClassicalExpression):
    """A ClassicalExpression for a constant boolean value.

    Args:
        value: a boolean value that will be represented by the created ``Const`` instance.
    """

    def __init__(self, value: bool) -> None:
        super().__init__()
        self._value = value

    @property
    def value(self) -> bool:
        return self._value

    @override
    def __str__(self) -> str:
        return str(self.value)


class Result(ClassicalExpression):
    """A ClassicalExpression representing the result of some calculation."""

    @property
    @override
    def _type_info(self) -> Attribute:
        return IntegerType(1)


class ObservableExpression(ClassicalExpression):
    """Base class for classical expressions depending on an ``Observable``.

    This class is mainly used to represent observable-related quantities such as "is correction
    ready" or "get correction". The "get observable" query effectively builds upon the
    measurements stored by the observable, and so is not within the scope of this class.

    Args:
        observable: observable that is being queried.
    """

    def __init__(self, observable: Observable) -> None:
        super().__init__()
        self._observable = observable


class ObservableCorrectionIsReadyExpression(ObservableExpression):
    pass


class ObservableCorrectionExpression(ObservableExpression):
    pass


class UncorrectedObservableExpression(ObservableExpression):
    pass


class CorrectedObservableExpression(ObservableExpression):
    pass
