import operator

import pytest

from deltakit_compile.frontend.common._annotations import Observable
from deltakit_compile.frontend.common._builder import OperationBuilder
from deltakit_compile.frontend.common._classical_expr import (
    ClassicalBinaryExpression,
    ClassicalExpression,
    Const,
    ObservableExpression,
    Result,
)
from deltakit_compile.frontend.common._exceptions import DifferentBuildersError
from tests.unit.frontend.conftest import add_to_builder_with_fake_ssa


def test_const() -> None:
    assert Const(True).value
    assert not Const(False).value
    assert isinstance(ClassicalExpression.coerce(0), Const)
    assert isinstance(ClassicalExpression.coerce(923874), Const)
    true = Const(True)
    assert ClassicalExpression.coerce(true) is true


@pytest.mark.parametrize(
    ("op", "rep"),
    [(operator.eq, "=="), (operator.ne, "!="), (operator.or_, "|"), (operator.and_, "&")],
)
def test_binary_expression(op, rep) -> None:
    true = Const(True)
    comparison = op(true, False)
    assert isinstance(comparison, ClassicalBinaryExpression)
    assert comparison.lhs is true
    assert comparison.cmd == rep
    assert isinstance(comparison.rhs, Const)
    assert not comparison.rhs.value
    assert str(comparison) == f"(True {rep} False)"


@pytest.mark.parametrize(
    ("op", "rep"),
    [(operator.or_, "|"), (operator.and_, "&")],
)
def test_reverse_binary_expression(op, rep) -> None:
    true = Const(True)
    comparison = op(False, true)
    assert isinstance(comparison, ClassicalBinaryExpression)
    assert isinstance(comparison.lhs, Const)
    assert not comparison.lhs.value
    assert comparison.cmd == rep
    assert comparison.rhs is true
    assert str(comparison) == f"(False {rep} True)"


def test_binary_expression_different_builders() -> None:
    builder = OperationBuilder()
    res = add_to_builder_with_fake_ssa(builder, Result())
    other_builder = OperationBuilder()
    ores = add_to_builder_with_fake_ssa(other_builder, Result())
    msg = "Cannot create a binary expression from results attached to different builders"
    with pytest.raises(DifferentBuildersError, match=msg):
        ClassicalBinaryExpression(res, "==", ores)


def test_invalid_use_of_eq() -> None:
    true = Const(True)
    with pytest.raises(NotImplementedError):
        _ = true == "true"


def test_invalid_use_of_ne() -> None:
    true = Const(True)
    with pytest.raises(NotImplementedError):
        _ = true != "true"


def test_hashing_classical_expression() -> None:
    msg = "Cannot meaningfully implement Const.__hash__"
    with pytest.raises(NotImplementedError, match=msg):
        hash(Const.coerce(0))


def test_observable_expression() -> None:
    obs = Observable()
    assert ObservableExpression(obs)._observable == obs
