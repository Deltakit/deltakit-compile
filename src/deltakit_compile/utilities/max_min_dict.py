# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Dictionary that keeps track of the maximum and minimum keys that have been added to it
and supports removing the minimum key ONLY."""

import heapq
from typing import TYPE_CHECKING, Any

from typing_extensions import TypeVar, override

if TYPE_CHECKING:
    from _typeshed import SupportsDunderLT


T = TypeVar("T", bound="SupportsDunderLT")
V = TypeVar("V")


class MaxMinDict(dict[T, V]):
    """A dictionary that keeps track of the maximum and minimum keys that have been added to it.

    Supports removing the minimum key BUT not the maximum key.

    The key type must be orderable, supporting < and > comparisons.

    Args:
        *args: (Any) Positional arguments passed to the underlying dict.
        **kwargs: (Any) Keyword arguments passed to the underlying dict.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._max_key: T | None = max(self.keys()) if self else None
        self._sorted_heapq: list[T] = list(self.keys())
        heapq.heapify(self._sorted_heapq)

    @override
    def __setitem__(self, key: T, value: V) -> None:
        if self._max_key is None or key > self._max_key:
            self._max_key = key
        if key not in self:
            heapq.heappush(self._sorted_heapq, key)
        super().__setitem__(key, value)

    @property
    def max_key(self) -> T | None:
        return self._max_key

    @property
    def min_key(self) -> T | None:
        return self._sorted_heapq[0] if self._sorted_heapq else None

    def pop_min_key(self) -> T | None:
        min_key = self.min_key
        if min_key is None:
            return None
        super().pop(min_key)
        heapq.heappop(self._sorted_heapq)
        if len(self) == 0:
            self._max_key = None
        return min_key
