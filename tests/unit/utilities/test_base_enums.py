"""Test base enum classes."""

from deltakit_compile.utilities.base_enums import BetterStrEnum


class TEnum(BetterStrEnum):
    """Test enum."""

    ITEM_0 = "item_0"
    ITEM_1 = "item_1"
    ITEM_2 = "item_2"


def test_better_str_enum_contains():
    """Test the BetterStrEnum contains method."""
    assert TEnum.contains("item_1")
    assert not TEnum.contains("item_3")


def test_better_str_enum_indexing():
    """Test that BetterStrEnum subclasses can be indexed."""
    assert TEnum["ITEM_0"] == TEnum.ITEM_0
    assert TEnum[2] == TEnum.ITEM_2  # type: ignore[misc]
    assert TEnum.ITEM_1.to_index == 1
