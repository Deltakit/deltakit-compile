# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""A set which remembers its insertion order."""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Iterator, MutableSet
from typing import TypeVar

from typing_extensions import override

T = TypeVar("T", bound=Hashable)


class OrderedSet(MutableSet[T]):
    """A set which remembers the order in which elements were added.

    It therefore has a deterministic iteration order. Insertion, deletion, and membership testing
    are all efficient. Equality is set equality and does not depend on the order of insertion.

    The order after set operations (union, intersection, difference, symmetric difference) is
    unspecified but deterministic. Note that union, intersection, and symmetric difference are not
    necessarily commutative with respect to the ordering.

    Note: If this class becomes a maintenance burden, it can be replaced with the third-party
    ordered-set package: https://github.com/rspeer/ordered-set.
    """

    def __init__(self, iterable: Iterable[T] | None = None) -> None:
        # The set is stored as the keys of a backing dict, since dict remembers the insertion order
        # since Python 3.7.
        self._dict: dict[T, None] = dict.fromkeys(iterable or [])

    @override
    def __len__(self) -> int:
        """The number of elements in the set."""
        return len(self._dict)

    @override
    def __contains__(self, item: object) -> bool:
        """Check if an item is in the set."""
        return item in self._dict

    @override
    def __iter__(self) -> Iterator[T]:
        """Iterate over the elements of the set in insertion order."""
        return iter(self._dict.keys())

    @override
    def add(self, item: T) -> None:
        """Add an item to the set."""
        self._dict[item] = None

    @override
    def discard(self, item: T) -> None:
        """Remove an item from the set if it is present."""
        self._dict.pop(item, None)

    def issubset(self, other: Iterable[T]) -> bool:
        """Check if the set is a subset of the elements of another iterable."""
        if not isinstance(other, OrderedSet):
            other = OrderedSet(other)
        return self <= other

    def issuperset(self, other: Iterable[T]) -> bool:
        """Check if the set is a superset of the elements of another iterable."""
        if not isinstance(other, OrderedSet):
            other = OrderedSet(other)
        return self >= other

    def union(self, *others: Iterable[T]) -> OrderedSet[T]:
        """Return the union of the set with other iterables as a new OrderedSet."""
        result = OrderedSet(self)
        for other in others:
            result |= other if isinstance(other, OrderedSet) else OrderedSet(other)
        return result

    def intersection(self, *others: Iterable[T]) -> OrderedSet[T]:
        """Return the intersection of the set with other iterables as a new OrderedSet."""
        result = OrderedSet(self)
        for other in others:
            result &= other if isinstance(other, OrderedSet) else OrderedSet(other)
        return result

    def difference(self, *others: Iterable[T]) -> OrderedSet[T]:
        """Return the difference of the set with other iterables as a new OrderedSet."""
        result = OrderedSet(self)
        for other in others:
            result -= other if isinstance(other, OrderedSet) else OrderedSet(other)
        return result

    def symmetric_difference(self, *others: Iterable[T]) -> OrderedSet[T]:
        """Return the symmetric difference of the set with other iterables as a new OrderedSet.

        The semantics for multiple 'others' sets is an iterated symmetric difference, i.e.
        symmetric_difference(A, B, C) is A ^ B ^ C. This corresponds to an iterated XOR.
        An element is in the result if it is in an odd number of the sets (including self).
        """
        result = OrderedSet(self)
        for other in others:
            result ^= other if isinstance(other, OrderedSet) else OrderedSet(other)
        return result

    @override
    def __repr__(self) -> str:
        return f"OrderedSet({list(self)})"
