"""Tests for the OrderedSet utility."""

import pytest

from deltakit_compile.utilities.ordered_set import OrderedSet


def test_ordered_set_preserves_constructor_order():
    """Test that the OrderedSet constructor preserves the order of elements."""
    assert list(OrderedSet([3, 1, 4, 1, 5, 9])) == [3, 1, 4, 5, 9]


def test_ordered_set_preserves_add_order():
    """Test that adding elements to an OrderedSet preserves their order."""
    s = OrderedSet[int]()
    for x in [3, 1, 4, 1, 5, 9]:
        s.add(x)
    assert list(s) == [3, 1, 4, 5, 9]


def test_ordered_set_preserves_add_and_remove_order():
    """Test that adding and removing elements from an OrderedSet preserves the order of remaining
    elements."""
    s = OrderedSet([3, 1])
    for x in [1, 4, 1, 5, 9]:
        s.add(x)
    s.remove(1)
    s.remove(5)
    assert list(s) == [3, 4, 9]


def test_ordered_set_basic_methods():
    """Test basic methods of OrderedSet."""
    s = OrderedSet([3, 1, 4])
    assert s
    assert len(s) == 3
    assert 1 in s
    assert 2 not in s
    assert list(s) == [3, 1, 4]
    assert repr(s) == "OrderedSet([3, 1, 4])"
    assert not OrderedSet[int]()
    assert repr(OrderedSet()) == "OrderedSet([])"


def test_ordered_set_equality():
    """Test OrderedSet equality works with other OrderedSets and with regular sets, and does not
    consider order. Also test that it does not consider other collection types equal."""
    assert OrderedSet([3, 1, 4]) == OrderedSet([3, 1, 4])
    assert OrderedSet([3, 1, 4]) == OrderedSet([1, 3, 4])
    assert OrderedSet([3, 1, 4]) == OrderedSet([1, 1, 1, 3, 3, 4])
    assert OrderedSet([3, 1, 4]) != OrderedSet([1, 2, 3])
    assert OrderedSet([3, 1, 4]) == {3, 1, 4}
    assert OrderedSet([3, 1, 4]) == frozenset({3, 1, 4})
    assert OrderedSet([3, 1, 4]) != {1, 2, 3}
    assert OrderedSet([3, 1, 4]) != [3, 1, 4]
    assert OrderedSet([3, 1, 4]) != (3, 1, 4)
    assert {3, 1, 4} == OrderedSet([3, 1, 4])
    assert frozenset({3, 1, 4}) == OrderedSet([3, 1, 4])
    assert {1, 2, 3} != OrderedSet([3, 1, 4])
    assert [3, 1, 4] != OrderedSet([3, 1, 4])  # noqa: SIM300
    assert (3, 1, 4) != OrderedSet([3, 1, 4])  # noqa: SIM300


@pytest.mark.parametrize(
    ("lhs", "rhs", "expected_subset", "expected_superset"),
    [
        ([], [], True, True),
        ([], [1, 2], True, False),
        ([1, 2], [1, 2], True, True),
        ([1, 2], [2, 1], True, True),
        ([1, 2], [1, 2, 3], True, False),
        ([1, 2], [2, 2, 1, 1, 3, 3], True, False),
        ([1, 2], [1], False, True),
        ([1, 1, 1, 2, 2, 2], [1, 1, 1, 1, 1], False, True),
        ([1, 2, 3], [1, 2], False, True),
        ([1, 2], [], False, True),
        ([1], [2], False, False),
    ],
)
def test_ordered_set_issubset_issuperset(
    lhs: list[int], rhs: list[int], expected_subset: bool, expected_superset: bool
):
    """Test the issubset and issuperset methods of OrderedSet."""
    assert OrderedSet(lhs).issubset(OrderedSet(rhs)) is expected_subset
    assert OrderedSet(lhs).issubset(rhs) is expected_subset
    assert set(lhs).issubset(OrderedSet(rhs)) is expected_subset
    assert OrderedSet(lhs).issuperset(OrderedSet(rhs)) is expected_superset
    assert OrderedSet(lhs).issuperset(rhs) is expected_superset
    assert set(lhs).issuperset(OrderedSet(rhs)) is expected_superset


@pytest.mark.parametrize(
    (
        "lhs",
        "rhs",
        "expected_union",
        "expected_intersection",
        "expected_difference",
        "expected_symmetric_difference",
    ),
    [
        ([], [], [], [], [], []),
        ([], [1, 2], [1, 2], [], [], [1, 2]),
        ([1, 2], [], [1, 2], [], [1, 2], [1, 2]),
        ([1, 2], [1, 2], [1, 2], [1, 2], [], []),
        ([1, 2], [2, 1], [1, 2], [1, 2], [], []),
        ([1, 2], [1, 2, 3], [1, 2, 3], [1, 2], [], [3]),
        ([1, 2, 3], [1, 2], [1, 2, 3], [1, 2], [3], [3]),
        ([1], [2], [1, 2], [], [1], [1, 2]),
        ([1, 2, 3], [3, 4, 5], [1, 2, 3, 4, 5], [3], [1, 2], [1, 2, 4, 5]),
    ],
)
def test_ordered_set_set_operations(
    lhs: list[int],
    rhs: list[int],
    expected_union: list[int],
    expected_intersection: list[int],
    expected_difference: list[int],
    expected_symmetric_difference: list[int],
):
    """Test the various set operations of OrderedSet."""
    ord_lhs = OrderedSet(lhs)
    ord_rhs = OrderedSet(rhs)
    assert ord_lhs.union(ord_rhs) == OrderedSet(expected_union)
    assert ord_lhs.union(rhs) == OrderedSet(expected_union)
    assert ord_lhs.intersection(ord_rhs) == OrderedSet(expected_intersection)
    assert ord_lhs.intersection(rhs) == OrderedSet(expected_intersection)
    assert ord_lhs.difference(ord_rhs) == OrderedSet(expected_difference)
    assert ord_lhs.difference(rhs) == OrderedSet(expected_difference)
    assert ord_lhs.symmetric_difference(ord_rhs) == OrderedSet(expected_symmetric_difference)
    assert ord_lhs.symmetric_difference(rhs) == OrderedSet(expected_symmetric_difference)

    # The original ordered sets should not have been modified (even in iteration order)
    assert list(ord_lhs) == lhs
    assert list(ord_rhs) == rhs


def test_ordered_set_set_operations_multiple_others():
    """Test the various set operations of OrderedSet work with multiple other iterables."""
    s = OrderedSet([1, 2, 3])
    assert s.union([3, 4], [4, 5]) == OrderedSet([1, 2, 3, 4, 5])
    assert s.intersection([2, 3], [3, 4]) == OrderedSet([3])
    assert s.difference([2], [3, 4]) == OrderedSet([1])
    assert s.symmetric_difference([2, 3], [3, 4]) == OrderedSet([1, 3, 4])

    # This syntax also works
    assert OrderedSet.union(s, [3, 4], [4, 5]) == OrderedSet([1, 2, 3, 4, 5])
    assert OrderedSet.intersection(s, [2, 3], [3, 4]) == OrderedSet([3])
    assert OrderedSet.difference(s, [2], [3, 4]) == OrderedSet([1])
    assert OrderedSet.symmetric_difference(s, [2, 3], [3, 4]) == OrderedSet([1, 3, 4])
