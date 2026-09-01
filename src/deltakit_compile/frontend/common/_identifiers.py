# (c) Copyright Riverlane 2025-2026. All rights reserved.
from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from deltakit_compile.frontend.common._builder import BaseAPIObject


class IdentifiersGenerator:
    """Generate new identifiers.

    Instances of this class should be used to generate new names for various objects that might
    need an identifier in the LogASM or Circuit APIs.

    Warning:
        This class guarantees that the same name will never be returned twice **by the same
        instance**. There is absolutely no guarantee of uniqueness across instances.
    """

    def __init__(self) -> None:
        self._indices: defaultdict[str, int] = defaultdict(lambda: 0)

    def _new_identifier(self, prefix: str) -> str:
        """Generate a new name for the given prefix.

        Args:
            prefix: a string representing the "type" of the object you want an identifier from.
                For example: `"det"`, `"meas"`, ... Can be any string.

        Returns:
            An identifier that was never returned before when calling this method on ``self``.
        """
        index = self._indices[prefix]
        self._indices[prefix] += 1
        return f"{prefix}_{index}"

    def new_identifier(self, obj: BaseAPIObject) -> str:
        """Generate a new name for the given object.

        Args:
            obj: the object to recover an identifier for.

        Returns:
            An identifier that was never returned before when calling this method on ``self``.
        """
        return self._new_identifier(obj._identifier_prefix)


class ArgumentMapping(NamedTuple):
    """Represents a mapping between two builder objects. Used to link operands to their
    corresponding argument.

    Attributes:
        inner: instance representing the argument in the inner context (e.g., within a sub-routine).
        outer: instance representing the argument in the outer context (e.g., within a circuit
            calling a sub-routine).
    """

    inner: BaseAPIObject
    outer: BaseAPIObject
