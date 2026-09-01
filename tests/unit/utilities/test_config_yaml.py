"""Tests for configuration YAML related utilities."""

import re
from enum import Enum
from pathlib import Path
from typing import Annotated

import pytest
from pydantic import ValidationError

from deltakit_compile.exceptions import InvalidConfigYAML
from deltakit_compile.utilities.config_yaml import ConfigYAML, EnumByName, HexInt


def test_yaml_hex_printing() -> None:
    """Test that ints can be printed as both decimal and hex in YAML."""

    class MixedInts(ConfigYAML, frozen=True):
        """Pydantic model that mixes decimal and hex ints."""

        dec_int: int
        hex_int: HexInt

    config = MixedInts(dec_int=20, hex_int=20)
    assert str(config) == "{dec_int: 20, hex_int: 0x14}\n"


def test_config_yaml_roundtrip(tmp_path: Path) -> None:
    """Test that config YAMLs can be roundtripped to and from string and file."""

    class FakeYAML(ConfigYAML, frozen=True):
        """Test YAML class."""

        d: dict[str, int]
        l_: list[list[HexInt]]
        f: float

    config = FakeYAML(d={"bob": 100}, l_=[[12, 13], [14]], f=0.01)
    assert config == FakeYAML.from_str(str(config))

    config_path = tmp_path / "config.yaml"
    config_path.write_text(str(config), encoding="utf-8")
    assert config == FakeYAML.from_file(config_path)


@pytest.mark.parametrize("yaml_str", ["i: 12\ndave: 10", "i: 'dave'", "i::::dave::::"])
def test_invalid_config_str_loading(yaml_str: str) -> None:
    """Test that loading an invalid config string throws errors of the correct type."""

    class FakeYAML(ConfigYAML, frozen=True):
        """Test YAML class."""

        i: int

    with pytest.raises(InvalidConfigYAML, match="Error loading FakeYAML:"):
        FakeYAML.from_str(yaml_str)


def test_invalid_config_file_loading(tmp_path: Path):
    """Test that loading an invalid config file throws errors of the correct type."""

    class FakeYAML(ConfigYAML, frozen=True):
        """Test YAML class."""

        i: int

    config_path = tmp_path / "config.yaml"  # Empty path
    with pytest.raises(InvalidConfigYAML, match="Error loading FakeYAML:"):
        FakeYAML.from_file(config_path)


def test_validate_version() -> None:
    """Test that the function returned by the validate_version helper throws exceptions for
    appropriate input."""
    ConfigYAML.validate_version(3)("0.12.40")
    ConfigYAML.validate_version(2)("0.2")
    with pytest.raises(ValueError, match=r"Version number 'v0\.2' is not in the format 'A\.B'"):
        ConfigYAML.validate_version(2)("v0.2")
    with pytest.raises(ValueError, match=r"Version number '0\.2' is not in the format 'A\.B\.C'"):
        ConfigYAML.validate_version(3)("0.2")
    with pytest.raises(
        ValueError, match=r"Version number '0\.-2\.10' is not in the format 'A\.B\.C'"
    ):
        ConfigYAML.validate_version(3)("0.-2.10")
    with pytest.raises(
        ValueError, match=r"Version number '0\.\.10' is not in the format 'A\.B\.C'"
    ):
        ConfigYAML.validate_version(3)("0..10")
    with pytest.raises(
        ValueError, match=r"Version number 'dave' is not in the format 'A\.B\.C\.D\.E'"
    ):
        ConfigYAML.validate_version(5)("dave")


def test_enums_by_name_fields() -> None:

    class Enum1(Enum):
        """Test Enum1"""

        E1 = ("hello", 1)
        E2 = ("goodbye", 2)
        E3 = ("I'm an enum!", 3)
        E4 = ("I'm a test enum!", 4)

    class Enum2(Enum):
        """Test Enum2"""

        E1 = ("hello", 1)
        E2 = ("goodbye", 2)
        E3 = ("I'm an enum!", 30)
        E4 = ("I'm a test enum!", 40)

    class TestConfig(ConfigYAML, frozen=True):
        """Test Config using EnumByName"""

        my_enum1a: Annotated[Enum1, EnumByName()]
        my_enum2a: Annotated[Enum2, EnumByName()]
        my_enum1b: Annotated[Enum1, EnumByName(ignore_case=False)]
        my_enum2b: Annotated[Enum2, EnumByName(ignore_case=False)]

    my_config = TestConfig(
        my_enum1a=Enum1.E3,
        my_enum2a=Enum2.E4,
        my_enum1b=Enum1.E1,
        my_enum2b=Enum2.E2,
    )
    # Test round trip:
    assert my_config == TestConfig.from_str(str(my_config))

    # Test correct parsing
    assert my_config == TestConfig.from_str(
        "{my_enum1a: E3, my_enum2a: E4, my_enum1b: E1, my_enum2b: E2}"
    )
    assert my_config == TestConfig.from_str(
        "{my_enum1a: e3, my_enum2a: e4, my_enum1b: E1, my_enum2b: E2}"
    )

    # Test errors for case sensitive checking
    with pytest.raises(InvalidConfigYAML, match="Enum1 member not found: e1"):
        TestConfig.from_str("{my_enum1a: e3, my_enum2a: e4, my_enum1b: e1, my_enum2b: e2}")

    # Test errors for non-existent enum member
    with pytest.raises(InvalidConfigYAML, match="Enum1 member not found: e6"):
        TestConfig.from_str("{my_enum1a: e6, my_enum2a: e4, my_enum1b: E1, my_enum2b: E2}")

    # Test errors for non-existent enum member
    with pytest.raises(InvalidConfigYAML, match="Enum2 member not found: E6"):
        TestConfig.from_str("{my_enum1a: e3, my_enum2a: e4, my_enum1b: E1, my_enum2b: E6}")

    with pytest.raises(
        ValidationError, match=re.escape("Expected Enum1 member or name, got Enum2: Enum2.E3")
    ):
        my_config = TestConfig(  # Ignoring type to check exception
            my_enum1a=Enum2.E3,  # type: ignore[arg-type]
            my_enum2a=Enum2.E4,
            my_enum1b=Enum1.E1,
            my_enum2b=Enum2.E2,
        )
    # Test string output is correct
    assert str(my_config) == "{my_enum1a: E3, my_enum2a: E4, my_enum1b: E1, my_enum2b: E2}\n"
