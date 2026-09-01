# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Configuration YAML related utilities."""

from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, TypeVar, cast

import yaml
from pydantic import BaseModel, BeforeValidator, GetCoreSchemaHandler, ValidationError
from pydantic_core import CoreSchema, core_schema
from typing_extensions import Self, override
from yaml import Dumper, ScalarNode, YAMLError

from deltakit_compile.exceptions import InvalidConfigYAML


class HexIntT(int):
    """An int that should be dumped in hex format in YAML."""

    @classmethod
    def __get_pydantic_core_schema__(cls, _: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        return core_schema.no_info_after_validator_function(cls, handler(int))

    @classmethod
    def hexint_representer(cls, dumper: Dumper, data: "HexIntT") -> ScalarNode:
        """HexInt to YAML conversion."""
        return dumper.represent_scalar("tag:yaml.org,2002:int", hex(data))


HexInt = Annotated[HexIntT | int, BeforeValidator(HexIntT)]

# Globally add printing for HexIntT
yaml.add_representer(HexIntT, HexIntT.hexint_representer)

ConfigYAMLT = TypeVar("ConfigYAMLT", bound="ConfigYAML")


class ConfigYAML(BaseModel, frozen=True, extra="forbid"):
    """Base class for defining the contents of a configuration YAML."""

    @override
    def __str__(self) -> str:
        return str(
            yaml.dump(
                self.model_dump(exclude_none=True),
                sort_keys=False,
                default_flow_style=None,
            )
        )

    @classmethod
    def from_str(cls, config_str: str) -> Self:
        """Load configuration from a YAML string and parse it into a class instance."""
        try:
            config_data = yaml.safe_load(config_str)
            return cls.model_validate(config_data)
        except (YAMLError, ValidationError) as err:
            msg = f"Error loading {cls.__name__}: {err}"
            raise InvalidConfigYAML(msg) from err

    @classmethod
    def from_file(cls, config_path: Path | str) -> Self:
        """Load configuration from a YAML file and parse it into a class instance."""
        config_path = Path(config_path) if isinstance(config_path, str) else config_path
        try:
            return cls.from_str(config_path.read_text(encoding="utf-8"))
        except FileNotFoundError as err:
            msg = f"Error loading {cls.__name__}: {err}"
            raise InvalidConfigYAML(msg) from err

    @staticmethod
    def validate_version(exp_num_fields: int) -> Callable[[str], str]:
        """Helper function for creating a validation function for version numbers in the form e.g.
        X.Y.Z if exp_num_fields is 3)."""

        def validator(version: str) -> str:
            ver_fields = version.split(".")
            if len(ver_fields) != exp_num_fields or any(not f.isdigit() for f in ver_fields):
                exp_format = ".".join([chr(i + ord("A")) for i in range(exp_num_fields)])
                msg = f"Version number '{version}' is not in the format '{exp_format}'"
                raise ValueError(msg)
            return version

        return validator


class EnumByName:
    """Pydantic schema that uses enumeration member names as values for serialisation.

    This helper allows fields typed as an ``Enum`` to be configured by the enum member *name*
    rather than the enum member *value*.

    Validation accepts either:
    - a member of the target enum class, or
    - a string equal to a member name.

    Serialisation always emits the enum member name (e.g. ``"PRE_DEFINED_TOP_LEFT"``).
    This is useful when enum values are implementation details (for example, ``auto()`` values)
    but configuration files should remain stable and human-readable.

    Args:
        ignore_case: If True (default), incoming string names are matched case-insensitively.
            If False, names must match exactly.
    """

    def __init__(self, *, ignore_case: bool = True):
        self.ignore_case = ignore_case

    def __get_pydantic_core_schema__(self, enum_cls: type[Enum], _handler: GetCoreSchemaHandler):
        """Build a Pydantic core schema for ``enum_cls``.

        The generated schema validates either enum instances or string member names and
        serialises enum values back to their member names.

        Args:
            enum_cls: Enum class this schema should validate/serialise.
            _handler: Unused Pydantic schema handler (kept for protocol compatibility).

        Returns:
            A ``CoreSchema`` implementing enum-name validation and serialisation.
        """
        name_enum = cast(
            type[Enum], Enum("name_enum", {member.name: member.name for member in enum_cls})
        )

        def enum_or_name(value: Enum | str) -> Enum:
            """Coerce a string enum name or enum instance into a member of ``enum_cls``."""
            if isinstance(value, str):
                if not self.ignore_case:
                    try:
                        return enum_cls[value]
                    except KeyError as e:
                        msg = f"{enum_cls.__name__} member not found: {value}"
                        raise ValueError(msg) from e
                try:
                    return next(
                        member for member in enum_cls if member.name.lower() == value.lower()
                    )
                except StopIteration as e:
                    msg = f"{enum_cls.__name__} member not found: {value}"
                    raise ValueError(msg) from e
            elif isinstance(value, enum_cls):
                return value
            msg = (
                f"Expected {enum_cls.__name__} member or name, got {type(value).__name__}: {value}"
            )
            raise ValueError(msg)

        return core_schema.no_info_plain_validator_function(
            enum_or_name,
            json_schema_input_schema=core_schema.enum_schema(
                enum_cls, list(name_enum.__members__.values())
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(lambda e: e.name),
        )
