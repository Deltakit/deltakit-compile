# (c) Copyright Riverlane 2025-2026. All rights reserved.
from __future__ import annotations

import operator
from collections.abc import Callable, Iterable, Iterator, Sequence
from typing import Any, Generic, TypeAlias, TypeGuard, TypeVar, Union, overload

from typing_extensions import override


def is_iterable(obj: Any) -> TypeGuard[Iterable[Any]]:
    """Test if the provided object is iterable or not.

    Args:
        obj: the object to test for iterability.

    Returns:
        ``True`` if the object is iterable, else ``False``.
    """
    try:
        iter(obj)
    except TypeError:
        return False
    else:
        return True


_Num_co = TypeVar("_Num_co", bound=int | float, covariant=True)

VectorLike: TypeAlias = Union["Vector[_Num_co]", Iterable[_Num_co], _Num_co]


class Vector(Generic[_Num_co]):
    """A n-dimensional vector.

    Note:
        This is a strictly inferior re-implementation of a numpy array. Numpy is
        not strictly needed here because:

        1. we expect instances of this class to only have a few entries,
        2. we only need very simple operations on this class (addition, subtraction, potentially
        multiplication by a scalar, ...).

        If one of the above point is not verified anymore, using a numpy array might be a good
        call.

    Args:
        entries: Either an iterable over values or a single value.
        *remaining_entries: if ``entries`` is a single value, this argument may contain more
            values that should be included in the ``Vector`` instance.

    Raises:
        ValueError: when ``entries`` is an iterable and ``remaining_entries`` is not empty
            (e.g., ``Vector([1.0], 2.0)``).
    """

    @overload
    def __init__(self, entries: Iterable[_Num_co]) -> None: ...
    @overload
    def __init__(self, entries: _Num_co, *remaining_entries: _Num_co) -> None: ...

    def __init__(self, entries: Iterable[_Num_co] | _Num_co, *remaining_entries: _Num_co) -> None:
        self._entries: tuple[_Num_co, ...]
        if isinstance(entries, (float, int)):
            self._entries = (entries, *remaining_entries)
        else:
            if remaining_entries:
                msg = (
                    "Got an iterable as first argument and some remaining entries. This is "
                    "not supported."
                )
                raise ValueError(msg)
            self._entries = tuple(entries)

    def __len__(self) -> int:
        return len(self._entries)

    @staticmethod
    def _apply_binary_op(
        op: Callable[[_Num_co, _Num_co], _Num_co],
        lhs: Vector[_Num_co] | Sequence[_Num_co],
        rhs: Vector[_Num_co] | Sequence[_Num_co],
    ) -> Vector[_Num_co]:
        if len(lhs) != len(rhs):
            msg = (
                "Could not apply operation between sequences of different length. Got "
                f"{len(lhs)} and {len(rhs)}."
            )
            raise ValueError(msg)
        return Vector(tuple(op(left, right) for left, right in zip(lhs, rhs, strict=True)))

    def __add__(self, other: Vector[_Num_co] | Sequence[_Num_co]) -> Vector[_Num_co]:
        return Vector._apply_binary_op(operator.add, self, other)

    def __radd__(self, other: Vector[_Num_co] | Sequence[_Num_co]) -> Vector[_Num_co]:
        return Vector._apply_binary_op(operator.add, other, self)

    def __sub__(self, other: Vector[_Num_co] | Sequence[_Num_co]) -> Vector[_Num_co]:
        return Vector._apply_binary_op(operator.sub, self, other)

    def __rsub__(self, other: Vector[_Num_co] | Sequence[_Num_co]) -> Vector[_Num_co]:
        return Vector._apply_binary_op(operator.sub, other, self)

    @override
    def __eq__(self, other: object) -> bool:
        if not is_iterable(other):
            return False
        values = list(other)
        return len(values) == len(self._entries) and all(
            lhs == rhs for lhs, rhs in zip(self, other, strict=True)
        )

    @override
    def __hash__(self) -> int:
        return hash(self._entries)

    def __iter__(self) -> Iterator[_Num_co]:
        yield from self._entries

    @overload
    def __getitem__(self, index: int) -> _Num_co: ...
    @overload
    def __getitem__(self, index: slice) -> Vector[_Num_co]: ...
    def __getitem__(self, index: int | slice) -> _Num_co | Vector[_Num_co]:
        return self._entries[index] if isinstance(index, int) else Vector(self._entries[index])

    @override
    def __str__(self) -> str:
        return "({})".format(",".join(map(str, self._entries)))

    @override
    def __repr__(self) -> str:
        return "Vector(({}))".format(",".join(map(str, self._entries)))

    @staticmethod
    def as_vector(value: VectorLike[_Num_co]) -> Vector[_Num_co]:
        """Returns a ``Vector`` instance from the provided ``value`` avoiding copies if possible.

        Args:
            value: an instance that can be re-interpreted as a vector.

        Returns:
            A vector representing the provided ``value``.
        """
        if isinstance(value, Vector):
            return value
        if isinstance(value, (float, int)):
            return Vector([value])
        return Vector(value)
