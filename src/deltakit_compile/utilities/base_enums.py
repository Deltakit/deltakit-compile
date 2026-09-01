# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Base enum classes."""

from __future__ import annotations

from enum import EnumMeta, _EnumDict
from typing import Any, TypeVar, cast

from typing_extensions import override
from xdsl.utils.str_enum import StrEnum

EnumT = TypeVar("EnumT")


class IndexableEnumMeta(EnumMeta):
    """Enum meta class that makes enums indexable in O(1) time.
    Before trying to understand this it is advised that you read up on Python metaclasses, e.g.:
    https://stackoverflow.com/questions/100003/what-are-metaclasses-in-python
    """

    # These attributes and __getitem__ effectively get transferred onto the enum class
    _index_member_map_: dict[int, str]
    _member_index_map_: dict[str, int]

    def __new__(
        mcs: type[IndexableEnumMeta],
        cls: str,
        bases: tuple[type, ...],
        classdict: _EnumDict,
        **kwargs: Any,
    ) -> IndexableEnumMeta:
        # Meta method that creates the enum class
        enum_class = super().__new__(mcs, cls, bases, classdict, **kwargs)

        # Create index <-> member name mappings during class creation so we can do lookup by index
        # in O(1) time using it later
        enum_class._index_member_map_ = dict(enumerate(enum_class._member_map_.keys()))
        enum_class._member_index_map_ = {v: k for k, v in enum_class._index_member_map_.items()}
        return enum_class

    @override
    def __getitem__(cls: type[EnumT], name: int | str) -> EnumT:
        """Indexing support with both Enum["MEMBER"] (default behaviour) and Enum[1]."""
        assert isinstance(cls, IndexableEnumMeta)
        if isinstance(name, int):
            name = cls._index_member_map_[name]
        return cast(EnumT, cls._member_map_[name])


class BetterStrEnum(StrEnum, metaclass=IndexableEnumMeta):
    """String enum that has equivalent to 'in' for Python versions less than 3.11"""

    @classmethod
    def contains(cls, value: str) -> bool:
        """Equivalent to 'value in enum' syntax."""
        return value in cls._value2member_map_

    @property
    def to_index(self) -> int:
        """The index of the Enum member."""
        return type(self)._member_index_map_[self.name]
