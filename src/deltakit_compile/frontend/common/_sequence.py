# (c) Copyright Riverlane 2025-2026. All rights reserved.
from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, TypeGuard, TypeVar

from typing_extensions import overload

_T = TypeVar("_T")


@overload
def does_not_contain_none_values(seq: tuple[_T | None, ...]) -> TypeGuard[tuple[_T, ...]]: ...
@overload
def does_not_contain_none_values(seq: list[_T | None]) -> TypeGuard[list[_T]]: ...
@overload
def does_not_contain_none_values(seq: Sequence[_T | None]) -> TypeGuard[Sequence[_T]]: ...


def does_not_contain_none_values(seq: Iterable[_T | None]) -> TypeGuard[Iterable[_T]]:
    return all(v is not None for v in seq)


def is_sequence_of(seq: Sequence[Any], typ: type[_T]) -> TypeGuard[Sequence[_T]]:
    return all(isinstance(obj, typ) for obj in seq)


def is_sequence(obj: Any) -> TypeGuard[Sequence[Any]]:
    return isinstance(obj, Sequence)


def _slice_len(s: slice, indexed_sequence_length: int) -> int:
    """Get the length of the object resulting from indexing a sequence of length
    ``indexed_sequence_length`` with the provided ``s``.

    Args:
        s: slice used to index a sequence of length ``indexed_sequence_length``.
        indexed_sequence_length: length of the sequence being indexed by the provided ``s``.

    Returns:
        The number of elements that are indexed by the provided slice.
    """
    return len(list(range(indexed_sequence_length))[s])
