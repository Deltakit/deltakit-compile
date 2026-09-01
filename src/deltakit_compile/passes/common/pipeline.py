# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Structures for handling pass pipelines, passes, and their configurations."""

from __future__ import annotations

import dataclasses
import types
from abc import abstractmethod
from dataclasses import dataclass, field
from inspect import isclass
from types import NoneType, UnionType
from typing import (
    Annotated,
    Any,
    ClassVar,
    Generic,
    Literal,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

import pydantic
from typing_extensions import Self, TypeForm, dataclass_transform, override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import VerifyException
from xdsl.passes import ModulePass, PassPipeline
from xdsl.utils.hints import isa
from xdsl.utils.runtime_final import is_runtime_final, runtime_final

from deltakit_compile.exceptions import (
    InvalidConfigurablePassDefinitionException,
    InvalidConfigurationDefinitionError,
    InvalidConfigYAML,
    InvalidPassConfigurationException,
)
from deltakit_compile.utilities.config_yaml import ConfigYAML


class Configuration(ConfigYAML, frozen=True):
    """Base class for all pipeline and pass configurations"""

    @override
    def __init_subclass__(cls, frozen: bool = True) -> None:
        """Ensures at sub-class creation time that all parent classes that are ``Configuration``s
        use the same types for each field.

        Some type checkers insist subclasses include `frozen=True` to ensure subclasses of frozen
        dataclasses remain frozen, others complain at this unless the parent class's init_subclass
        method has this extra argument too, so we include the `frozen` argument here to please type
        checkers. In any case, subclasses should always set `frozen=True` as all ``Configuration``s
        must be immutable."""
        assert frozen
        bases = cls.__bases__
        config_bases: list[type[Configuration]] = [b for b in bases if issubclass(b, Configuration)]
        fields: dict[str, tuple[type[Configuration], pydantic.fields.FieldInfo]] = {}
        for config in config_bases:
            for field_name, field_info in config.model_fields.items():
                seen_config, seen_info = fields.setdefault(field_name, (config, field_info))
                if field_info.annotation != seen_info.annotation:
                    msg = (
                        f"Inherited configuration parameters must match in '{cls.__name__}': "
                        f"base class '{config.__name__}' has "
                        f"'{field_name}' with type: {field_info.annotation} "
                        f"but base class '{seen_config.__name__}' has "
                        f"'{field_name}' with type: {seen_info.annotation}"
                    )
                    raise InvalidConfigurationDefinitionError(msg)


class NamedConfiguration(Configuration, frozen=True):
    """Base class for configurations that can be used in a ``NamedConfigurations`` union field.
    Then allows a union of different subtypes types of ``NamedConfiguration`` to be specified as a
    field inside other configurations.

    This base class automatically creates a ``name`` field in each subclass instance, that is always
    set to the subclass's name, or ``config_name`` if it is given when defining the subclass. This
    field is then used by pydantic to initialise the correct ``NamedConfiguration`` sub-type when
    loading a config a parent config, but can be ignored if the type of ``Configuration`` is not a
    union."""

    name: str = pydantic.Field(init=False, frozen=True)
    """The fixed name of this configuration type."""

    @override
    def __init_subclass__(cls, config_name: str | None = None) -> None:
        cls_name = config_name or cls.__name__
        # We override the 'name' field to give it a default
        cls.name = pydantic.Field(init=False, default=cls_name, frozen=True)
        # We also have to override the runtime type-system to set the type of the field to the
        # correct `Literal` so pydantic can run its checks on the model properly.
        cls.__annotations__["name"] = Literal[cls_name]
        super().__init_subclass__()


_NamedConfigurationsT = TypeVar("_NamedConfigurationsT", bound=NamedConfiguration)
NamedConfigurations = Annotated[_NamedConfigurationsT, pydantic.Field(discriminator="name")]
"""A discriminated ``Configuration`` field that accepts the given ``NamedConfiguration`` types."""

ConfigurationT_contra = TypeVar("ConfigurationT_contra", bound=Configuration, contravariant=True)


class FieldPathSpec:
    """A path through a hierarchical `Configuration` structure, used to annotate `ConfigurablePass`
    field type hints. For example::

        my_option: Annotated[int, FieldPathSpec("sub_conf1", "sub_conf2")]

    When generating the pass from a `Configuration` `my_option` will be taken from
    `config.sub_conf1.sub_conf2.my_option`. `config.sub_conf1` and `config.sub_conf1.sub_conf2`
    must both be `Configuration`s.

    A `field_name` argument can also be passed that overrides the field searched for in the config,
    (which by default is the same name as the field in the `ConfigurablePass`) for example::

        my_option: Annotated[int, FieldPathSpec("sub_conf1", field_name="config_name")]

    will populate the `my_option` field with the value given in the `config` at
    `config.sub_conf1.config_name`.

    By setting `field_name` to `"."` the field can be set to the entire given `Configuration`. For
    example::

        class MyPass(ConfigurablePass[MyConfiguration]):
            name = "my-pass"
            the_config: Annotated[MyConfiguration, FieldPathSpec(field_name=".")]
    """

    def __init__(self, *field_path_names: str, field_name: str | None = None) -> None:
        self._field_path_names = tuple(field_path_names)
        self._field_name = field_name

    @property
    def field_path_names(self) -> tuple[str, ...]:
        """The sequence of field names that prefix the variable name."""
        return self._field_path_names

    def field_name(self, dataclass_field_name: str) -> tuple[str] | tuple[()]:
        """The field name to search for given this FieldPathSpec"""
        if self._field_name is None:
            return (dataclass_field_name,)
        if self._field_name == ".":
            return ()
        return (self._field_name,)

    @classmethod
    def extract_field_path(cls, dataclass_field: dataclasses.Field) -> tuple[str, ...]:
        """Extract the sequence of field names to find within a `Configuration` based on a
        potentially annotated `dataclasses.Field`."""
        if get_origin(dataclass_field.type) is Annotated:
            annotations = get_args(dataclass_field.type)
            if isa(annotations, tuple[Any, FieldPathSpec]):
                spec = annotations[1]
                return (*spec.field_path_names, *spec.field_name(dataclass_field.name))
        return (dataclass_field.name,)


@dataclass(frozen=True)
class _ConfigurablePassBase(ModulePass):
    """Private base class for ConfigurablePass, used to work around Python's typing
    limitations with higher order type variables."""


@dataclass(frozen=True)
class ConfigurablePass(_ConfigurablePassBase, Generic[ConfigurationT_contra]):
    """Base class for module passes that can be instantiated from a Configuration."""

    _config_type: ClassVar[type[ConfigurationT_contra]]
    """The type of Configuration that can instantiate this class."""

    @override
    def __init_subclass__(cls, generic_subclass: type[ConfigurablePass] | bool = False) -> None:
        """Extract the type bound to the typevar when subclasses are created.

        Args:
            generic_subclass: The generic_subclass argument should be left as `False` for concrete
                subclasses. If the subclass is itself generic and designed to be further subclassed
                It should pass `True` for itself, and then override its `__init_subclass__` method
                to pass itself as `generic_subclass` to this `__init_subclass__`. See
                `ConfigurablePipeline` for an example of this generic behaviour. Defaults to
                `False`.

        Raises:
            InvalidConfigurablePassDefinitionException: The generic TypeVar `ConfigurationT_contra`
                of the subclass must bound as a concrete type unless generic_subclass is True
        """
        super().__init_subclass__()
        if generic_subclass is True:
            return
        if generic_subclass is False:
            generic_subclass = ConfigurablePass

        orig_bases = cls.__orig_bases__  # type: ignore[attr-defined]
        config_convertible_base = next(b for b in orig_bases if get_origin(b) is generic_subclass)
        config_type = get_args(config_convertible_base)[0]
        if isinstance(config_type, TypeVar):
            msg = (
                f"Cannot automatically detect the type of the Configuration for '{cls.__name__}': "
                f"found TypeVar '{config_type}' but expected concrete Configuration type"
            )
            raise InvalidConfigurablePassDefinitionException(msg)
        assert issubclass(config_type, Configuration)
        cls._config_type = config_type  # type: ignore[reportAttributeAccessIssue]

    def __post_init__(self) -> None:
        """Proactively convert any fields with type `str | C` where `C` is a subclass of
        `Configuration` into that `C` type - automatically applying the pydantic validation of the
        data from the YAML representation.

        This allows `ConfigurablePass`es that use `Configuration`s as fields to work
        from xDSLs ArgSpec mechanism, and so from the command line too."""

        if not is_runtime_final(type(self)):
            msg = (
                "Cannot instantiate a ConfigurablePass that is not runtime final. "
                f"Class definition for '{type(self).__name__}' is probably missing the "
                "@configurable_pass decorator"
            )
            raise InvalidConfigurablePassDefinitionException(msg)

        fields: tuple[dataclasses.Field[Any], ...] = dataclasses.fields(self)
        field_types = get_type_hints(type(self))
        for dataclass_field in fields:
            if not dataclass_field.init:
                """Only convert fields that come from the init - custom inits should handle their
                own logic"""
                continue

            field_value = getattr(self, dataclass_field.name)
            if not isinstance(field_value, str):
                """Only convert fields whose value is currently a string."""
                continue

            field_type = field_types[dataclass_field.name]
            if get_origin(field_type) not in (Union, UnionType):
                """Only convert fields whose type hint is `str | C`."""
                continue

            config_types = [typ for typ in get_args(field_type) if issubclass(typ, Configuration)]
            if not config_types:
                """Where `C` is a subtype of `Configuration`."""
                continue

            new_value = None
            errors = []
            for config_type in config_types:
                """If there are multiple union-ed subclasses of Configuration, use the first that
                work."""
                try:
                    new_value = config_type.from_str(field_value)
                    break
                except InvalidConfigYAML as error:
                    errors.append(error)
            if new_value is None:
                if len(errors) == 1:
                    raise errors[0]
                msgs = [f"Could not validate model as any of {config_types}:"]
                msgs.extend([f"\t{e}" for e in errors])
                raise InvalidConfigYAML("\n".join(msgs))
            object.__setattr__(self, dataclass_field.name, new_value)

    @classmethod
    def from_configuration(cls, config: ConfigurationT_contra) -> Self:
        """
        Return an instance of this class built from the given configuration.

        This classmethod inspects this class' dataclass fields and for each one that should be
        inited it extracts the field of the same name in the given `config`.
        Annotated a field in `cls` using `FieldPathSpec` will define how to find that
        field within a nested structure of `Configuration`s inside `config`.
        `property` methods defined in `Configuration`s are also traversed and used to fill fields
        of this pass as if they were regular fields.
        """

        if not isinstance(config, cls._config_type):
            msg = f"expected {cls._config_type} but got {type(config)}"
            raise TypeError(msg)
        config = cls._config_type.model_validate(config)
        fields: tuple[dataclasses.Field[Any], ...] = dataclasses.fields(cls)

        arg_dict = dict[str, Any]()
        field_types = get_type_hints(cls)

        for dataclass_field in fields:
            if not dataclass_field.init:
                continue

            field_path = FieldPathSpec.extract_field_path(dataclass_field)

            current_config = config
            for i, current_field_name in enumerate(field_path):
                if not isinstance(current_config, Configuration):
                    msg = (
                        f"'{cls.__name__}' requires a configuration at "
                        f"'{'.'.join(field_path[:i])}' "
                        f"but '{current_field_name}' is not a Configuration object"
                    )
                    raise InvalidPassConfigurationException(msg)
                current_config_fields = type(current_config).model_fields
                if current_field_name in current_config_fields or isinstance(
                    getattr(type(current_config), current_field_name, None), property
                ):
                    current_config = getattr(current_config, current_field_name)
                elif dataclass_field.default is not dataclasses.MISSING:
                    current_config = dataclass_field.default
                    break
                elif dataclass_field.default_factory is not dataclasses.MISSING:
                    current_config = dataclass_field.default_factory()
                    break
                else:
                    msg = (
                        f"'{cls.__name__}' requires configuration '{'.'.join(field_path)}' "
                        "but the given Configuration does not have a "
                        f"'{'.'.join(field_path[: i + 1])}' field or property"
                    )
                    raise InvalidPassConfigurationException(msg)

            arg = current_config
            field_type = field_types[dataclass_field.name]
            if not isa(arg, field_type):
                msg = (
                    f"Expected type {field_type} for '{dataclass_field.name}' "
                    f"but got a {type(arg)} from the given Configuration"
                )
                raise InvalidPassConfigurationException(msg)

            arg_dict[dataclass_field.name] = arg

        return cls(**arg_dict)

    @classmethod
    def passes_from_configuration(cls, config: ConfigurationT_contra) -> tuple[ModulePass, ...]:
        """Get the tuple of passes that when run in order execute this pass as per `config`.

        For most passes this will return an instance of this class configured with `config` but for
        `ConfigurablePipeline`es this will return the sequence of inner passes that make up that
        pipeline."""
        return (cls.from_configuration(config),)


@dataclass(frozen=True)
class ConfigurablePipeline(ConfigurablePass[ConfigurationT_contra], generic_subclass=True):
    """A base class for pass pipelines. Supports being configured from a generic Configuration, and
    getting a sequence of passes that define the pipeline."""

    verify_between_passes: bool = field(default=False, kw_only=True)

    @override
    def __init_subclass__(cls, generic_subclass: type[ConfigurablePass] | bool = False) -> None:
        if generic_subclass is True:
            return
        if generic_subclass is False:
            generic_subclass = ConfigurablePipeline
        super().__init_subclass__(generic_subclass=generic_subclass)

    @abstractmethod
    def get_passes(self) -> tuple[ModulePass, ...]:
        """Get the sequence of passes this pass pipeline runs."""

    @override
    @classmethod
    def passes_from_configuration(cls, config: ConfigurationT_contra) -> tuple[ModulePass, ...]:
        pipeline_pass = cls.from_configuration(config)
        return pipeline_pass.get_passes()

    @staticmethod
    def _verify_callback(
        previous_pass: ModulePass | None, op: ModuleOp, next_pass: ModulePass | None
    ) -> None:
        try:
            op.verify()
        except VerifyException as verify_error:
            msg = "IR does not verify"
            msg += f" after '{previous_pass.name}' pass" if previous_pass else ""
            msg += "," if previous_pass and next_pass else ""
            msg += f" before '{next_pass.name}' pass" if next_pass else ""
            # __notes__ only in 3.11 and above
            if hasattr(verify_error, "add_note"):
                # Use official API if present
                verify_error.add_note(msg)
            else:
                # Use xDSLs __notes__ work around if not
                if not hasattr(verify_error, "__notes__"):
                    notes: list[str] = []
                    verify_error.__notes__ = notes
                else:
                    notes = verify_error.__notes__
                notes.append(msg)
            raise verify_error

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        PassPipeline(
            self.get_passes(),
            callback=self._verify_callback if self.verify_between_passes else None,
        ).apply(ctx, op)


ConfiguredPassInvT = TypeVar("ConfiguredPassInvT", bound=type[_ConfigurablePassBase])


def _is_subtype(subtype: TypeForm[type], supertype: TypeForm[type]) -> bool:
    """Return False if `subtype` is definitely not a sub type of `supertype`.

    This is designed to check cases where the subtype is a concrete simple class, or a union of
    these. Checking is permissive in that only when a subtype is definitely not compatible with
    supertype is the result False, this enables class creation time checks to handle most cases but
    init time checks handle the complex corner cases."""
    if supertype is NoneType:
        return subtype is NoneType
    sub_origin = get_origin(subtype)
    super_origin = get_origin(supertype)
    # get_origin checks that the types are not a parametrized generic
    if isclass(subtype) and isclass(supertype) and (super_origin is None):
        return issubclass(subtype, supertype)
    if sub_origin == types.UnionType:
        return all(_is_subtype(arg, supertype) for arg in get_args(subtype))
    if super_origin in (Union, types.UnionType):
        return any(_is_subtype(subtype, arg) for arg in get_args(supertype))
    if isinstance(sub_origin, type) and super_origin in (list, dict, tuple):
        return (
            sub_origin is super_origin
            and len(get_args(subtype)) == len(get_args(supertype))
            and all(
                _is_subtype(sub, sup)
                for sub, sup in zip(get_args(subtype), get_args(supertype), strict=True)
            )
        )
    return True


@dataclass_transform(frozen_default=True)
def configurable_pass(cls: ConfiguredPassInvT) -> ConfiguredPassInvT:
    """Decorator for creating and validating `ConfigurablePass`es. Use on all concrete
    implementations of `ConfigurablePass` to validate the generic `ConfigurationT_contra`
    type is capable of providing the arguments required by the pass class.

    Args:
        cls: A concrete subclass of ConfigurablePass. Limitations in Python's type hints
            means this method cannot be typed properly, however any argument that is not a concrete
            subclass of ConfigurablePass is invalid. This limitation is because Python lacks higher
            order type hints (i.e. `type[ConfiguredPassInvT[ConfigurationT_contra]]` is an invalid
            type hint if `ConfiguredPassInvT` is a TypeVar bound to `ConfiguredPass`).

    Raises:
        TypeError: If ``cls`` is not a subclass of ConfigurablePass
        InvalidConfigurablePassDefinitionException: If ``cls`` is does not form a valid
            configurable pass definition. This is likely to be because the ``Configuration``
            ``cls`` claims to convert from does not provide the fields required by ``cls``.

    Returns:
        The modified class, ``cls``, as a dataclasses.dataclass.
    """

    if not issubclass(cls, ConfigurablePass) or cls == ConfigurablePass:
        msg = f"Expected a subclass of ConfigurablePass but got {cls}"
        raise TypeError(msg)
    config_type = cls._config_type  # type: ignore[misc]
    # cls._config_type is guaranteed to exist, is manually type checked, and is only read, so mypy's
    # error is unnecessary.
    if not issubclass(config_type, Configuration):
        msg = f"'{cls.__name__}._config_type' must be a subclass of Configuration"
        raise InvalidConfigurablePassDefinitionException(msg)

    data_class_cls = dataclass(frozen=True)(cls)

    data_class_field_types = get_type_hints(data_class_cls)
    dataclass_fields = dataclasses.fields(data_class_cls)
    for dataclass_field in dataclass_fields:
        if not dataclass_field.init:
            continue
        field_path = FieldPathSpec.extract_field_path(dataclass_field)

        current_config_type: type = config_type
        for i, current_field_name in enumerate(field_path):
            if not issubclass(current_config_type, Configuration):
                msg = (
                    f"'{cls.__name__}' requires a configuration at '{'.'.join(field_path[:i])}' "
                    f"but this is not a Configuration object in {config_type.__name__}"
                )
                raise InvalidConfigurablePassDefinitionException(msg)

            current_config_fields = current_config_type.model_fields
            if current_field_name in current_config_fields:
                next_type = current_config_fields[current_field_name].annotation
            elif isinstance(
                property_object := getattr(current_config_type, current_field_name, None), property
            ):
                next_type = get_type_hints(property_object.fget)["return"]
            elif (
                dataclass_field.default is not dataclasses.MISSING
                or dataclass_field.default_factory is not dataclasses.MISSING
            ):
                # Fail to get a value but it's okay because there is a default in the dataclass
                current_config_type = data_class_field_types[dataclass_field.name]
                break
            else:
                msg = (
                    f"'{cls.__name__}' requires configuration '{'.'.join(field_path)}' from "
                    f"'{config_type.__name__}' but '{current_config_type.__name__}' does not "
                    f"have a '{current_field_name}' field or property"
                )
                raise InvalidConfigurablePassDefinitionException(msg)

            if next_type is None:
                msg = (
                    "All fields in a Configuration used by a ConfigurablePass must be "
                    f"typed but '{current_field_name}' in '{current_config_type.__name__}' is not"
                )
                raise InvalidConfigurablePassDefinitionException(msg)
            current_config_type = next_type
        data_class_field_type = data_class_field_types[dataclass_field.name]
        if not _is_subtype(current_config_type, data_class_field_type):
            msg = (
                f"'{cls.__name__}' requires configuration '{'.'.join(field_path)}' from "
                f"'{config_type.__name__}' but this field has type {current_config_type} "
                f"which is incompatible with '{cls.__name__}.{dataclass_field.name}' "
                f"that has type {data_class_field_type}"
            )
            raise InvalidConfigurablePassDefinitionException(msg)

    return runtime_final(cast(ConfiguredPassInvT, data_class_cls))
