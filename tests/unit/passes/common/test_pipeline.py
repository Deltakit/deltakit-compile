import dataclasses
import re
from dataclasses import dataclass, field
from typing import Annotated, Literal, TypeVar, cast

import pytest
from typing_extensions import override
from xdsl.builder import Builder
from xdsl.context import Context
from xdsl.dialects.builtin import IntAttr, ModuleOp
from xdsl.ir import VerifyException
from xdsl.irdl import IRDLOperation, irdl_op_definition
from xdsl.passes import ModulePass
from xdsl.rewriter import InsertPoint
from xdsl.utils.runtime_final import runtime_final

from deltakit_compile.exceptions import (
    InvalidConfigurablePassDefinitionException,
    InvalidConfigurationDefinitionError,
    InvalidConfigYAML,
    InvalidPassConfigurationException,
)
from deltakit_compile.passes.common.pipeline import (
    ConfigurablePass,
    ConfigurablePipeline,
    Configuration,
    ConfigurationT_contra,
    FieldPathSpec,
    NamedConfiguration,
    NamedConfigurations,
    configurable_pass,
)


class TestConfiguration:
    """Tests for Configurations"""

    def test_incompatible_configs(self) -> None:
        """Test that incompatible config subclasses raise an error at config class definition
        time."""

        class MyConfig1(Configuration, frozen=True):
            my_option: bool

        class MyConfig2(NamedConfiguration, frozen=True):
            my_option: str | int

        with pytest.raises(
            InvalidConfigurationDefinitionError,
            match=re.escape(
                "Inherited configuration parameters must match in 'MyFullConfig': "
                "base class 'MyConfig2' has 'my_option' with type: str | int "
                "but base class 'MyConfig1' has 'my_option' with type: <class 'bool'>"
            ),
        ):

            class MyFullConfig(MyConfig1, MyConfig2, frozen=True):
                pass  # causes name conflict on 'my_option' with different types.

    def test_compatible_configs(self) -> None:
        """Test that compatible config subclasses do not raise an error."""

        class MyConfig1(Configuration, frozen=True):
            my_option1: int | str
            my_option2: None | str

        class MyConfig2(Configuration, frozen=True):
            my_option1: str | int
            my_option2: str | None

        class MyFullConfig(MyConfig1, MyConfig2, frozen=True):
            my_option1: str | int
            # does not cause name conflict on 'my_option' with different types.

        MyFullConfig(my_option1=1, my_option2=None)

    def test_named_configurations(self) -> None:

        class MyConfig(NamedConfiguration, frozen=True):
            my_int: int

        config = MyConfig(my_int=1)
        assert config.name == "MyConfig"
        assert str(config) == "{name: MyConfig, my_int: 1}\n"

        # Loading from str can omit the name:
        assert MyConfig.from_str("my_int: 1") == config

        class MyParentConfig(Configuration, frozen=True):
            sub_config: MyConfig

        # Loading from str inside a parent config can omit the name:
        assert MyParentConfig.from_str("sub_config: {my_int: 1}") == MyParentConfig(
            sub_config=config
        )

    def test_inherited_named_configurations(self) -> None:

        class MyConfig(NamedConfiguration, frozen=True):
            my_int: int

        class MyChildConfig(MyConfig, frozen=True):
            my_str: str

        config = MyChildConfig(my_int=1, my_str="hi")
        assert config.name == "MyChildConfig"
        assert str(config) == "{name: MyChildConfig, my_int: 1, my_str: hi}\n"

    def test_named_configurations_custom_name(self) -> None:

        class MyConfig(NamedConfiguration, frozen=True, config_name="This Config"):
            my_int: int

        config = MyConfig(my_int=1)
        assert config.name == "This Config"
        assert str(config) == "{name: This Config, my_int: 1}\n"

    def test_child_named_configurations(self) -> None:

        class MyConfig1(NamedConfiguration, frozen=True):
            my_int: int

        class MyConfig2(NamedConfiguration, frozen=True): ...

        class SuperConfig(Configuration, frozen=True):
            inner_config: NamedConfigurations[MyConfig1 | MyConfig2]

        config1 = SuperConfig(inner_config=MyConfig1(my_int=1))
        assert config1 == SuperConfig.from_str(str(config1))
        assert str(config1) == "inner_config: {name: MyConfig1, my_int: 1}\n"

        config2 = SuperConfig(inner_config=MyConfig2())
        assert config2 == SuperConfig.from_str(str(config2))
        assert str(config2) == "inner_config: {name: MyConfig2}\n"

    def test_child_invalid_named_configurations(self) -> None:

        class MyConfig1(NamedConfiguration, frozen=True, config_name="same name"):
            my_int: int

        class MyConfig2(NamedConfiguration, frozen=True, config_name="same name"): ...

        with pytest.raises(
            TypeError, match="Value 'same name' for discriminator 'name' mapped to multiple choices"
        ):

            class SuperConfig(Configuration, frozen=True):
                inner_config: NamedConfigurations[MyConfig1 | MyConfig2]


class TestPassesWork:
    """Tests for the ConfigurablePass system that use the system as expected and succeed
    in configuring passes."""

    @pytest.mark.parametrize("flag", [True, False])
    def test_simple_config(self, flag: bool):
        class MyConfig(Configuration, frozen=True):
            my_bool_option: bool
            my_other_option: bool

        @configurable_pass
        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            my_bool_option: bool

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        config = MyConfig(my_bool_option=flag, my_other_option=False)
        my_pass = MyPass.from_configuration(config)
        my_pass_normal = MyPass(flag)
        assert my_pass == my_pass_normal

    @pytest.mark.parametrize("flag", [True, False])
    def test_from_child_config(self, flag: bool):
        class MyConfig(Configuration, frozen=True):
            my_bool_option: bool
            my_other_option: bool

        class MyChildConfig(MyConfig, frozen=True):
            another_bool_option: bool

        @configurable_pass
        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            my_bool_option: bool

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        config = MyChildConfig(
            my_bool_option=flag, my_other_option=False, another_bool_option=False
        )

        # Test correct contravariant typing:
        my_pass_list: list[type[ConfigurablePass[MyChildConfig]]] = []
        my_pass_list.append(MyPass)
        my_passes = [Pass.from_configuration(config) for Pass in my_pass_list]

        my_pass = my_passes[0]
        my_pass_normal = MyPass(flag)
        assert my_pass == my_pass_normal

    @pytest.mark.parametrize("flag", [True, False])
    @pytest.mark.parametrize("string", ["Hello", "World"])
    def test_compound_config(self, flag: bool, string: str):
        class MyBoolConfig(Configuration, frozen=True):
            my_bool_option: bool

        class MyFullConfig(MyBoolConfig, frozen=True):
            my_string_option: str

        @configurable_pass
        class MyPass1(ConfigurablePass[MyBoolConfig]):
            name = "my-pass-1"

            my_bool_option: bool

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        @configurable_pass
        class MyPass2(ConfigurablePass[MyFullConfig]):
            name = "my-pass-2"

            my_bool_option: bool
            my_string_option: str

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        bool_config = MyBoolConfig(my_bool_option=flag)
        full_config = MyFullConfig(my_bool_option=flag, my_string_option=string)

        my_pass_1_bool = MyPass1.from_configuration(bool_config)
        my_pass_1_full = MyPass1.from_configuration(full_config)
        my_pass_1_normal = MyPass1(flag)
        assert my_pass_1_bool == my_pass_1_normal
        assert my_pass_1_full == my_pass_1_normal

        my_pass_2 = MyPass2.from_configuration(full_config)
        my_pass_2_normal = MyPass2(flag, string)
        assert my_pass_2 == my_pass_2_normal

    @pytest.mark.parametrize("flag", [True, False])
    @pytest.mark.parametrize("string", ["Hello", "World"])
    def test_complex_config(self, flag: bool, string: str):
        class MyBoolConfig(Configuration, frozen=True):
            my_bool_option: bool

        class MyStringConfig(Configuration, frozen=True):
            my_string_option: str

        class MyFullConfig(Configuration, frozen=True):
            bool_conf: MyBoolConfig
            string_conf: MyStringConfig

        @configurable_pass
        class MyPass1(ConfigurablePass[MyFullConfig]):
            name = "my-pass-1"

            bool_conf: MyBoolConfig | str

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        @configurable_pass
        class MyPass2(ConfigurablePass[MyFullConfig]):
            name = "my-pass-2"

            string_conf: str | MyStringConfig

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        bool_config = MyBoolConfig(my_bool_option=flag)
        string_config = MyStringConfig(my_string_option=string)
        full_config = MyFullConfig(bool_conf=bool_config, string_conf=string_config)

        my_pass_1 = MyPass1.from_configuration(full_config)
        my_pass_1_normal = MyPass1(bool_config)
        my_pass_1_string = MyPass1(str(bool_config))

        assert my_pass_1 == my_pass_1_normal
        assert my_pass_1_string == my_pass_1_normal

        my_pass_2 = MyPass2.from_configuration(full_config)
        my_pass_2_normal = MyPass2(string_config)
        my_pass_2_string = MyPass2(str(string_config))

        assert my_pass_2 == my_pass_2_normal
        assert my_pass_2_string == my_pass_2_normal

    @pytest.mark.parametrize("flag", [True, False])
    def test_nested_config_option(self, flag: bool):
        class MyBoolConfig(Configuration, frozen=True):
            my_bool_option: bool

        class MyPassConfig(Configuration, frozen=True):
            bool_conf: MyBoolConfig

        class MyFullConfig(Configuration, frozen=True):
            my_bool_option: bool
            sub_conf: MyPassConfig

        @configurable_pass
        class MyPass(ConfigurablePass[MyFullConfig]):
            name = "my-pass"

            my_bool_option: Annotated[bool, FieldPathSpec("sub_conf", "bool_conf")]

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        config = MyFullConfig(
            my_bool_option=not flag,
            sub_conf=MyPassConfig(bool_conf=MyBoolConfig(my_bool_option=flag)),
        )
        my_pass = MyPass.from_configuration(config)
        my_pass_normal = MyPass(flag)
        assert my_pass == my_pass_normal

    @pytest.mark.parametrize("flag", [True, False])
    def test_config_literals(self, flag: bool):
        class MyConfig(Configuration, frozen=True):
            my_bool_option: Literal[True, False]

        config = MyConfig(my_bool_option=flag)

        @configurable_pass
        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            my_bool_option: bool

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        my_pass = MyPass.from_configuration(config)
        my_pass_normal = MyPass(flag)
        assert my_pass == my_pass_normal

    @pytest.mark.parametrize("flag", [True, False])
    def test_pass_literals(self, flag: bool):
        class MyConfig(Configuration, frozen=True):
            my_bool_option: bool

        config = MyConfig(my_bool_option=flag)

        @configurable_pass
        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            my_bool_option: Literal[True, False]

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        my_pass = MyPass.from_configuration(config)
        my_pass_normal = MyPass(flag)
        assert my_pass == my_pass_normal

    @pytest.mark.parametrize("flag", [True, False])
    def test_no_init_config(self, flag: bool):
        class MyConfig(Configuration, frozen=True):
            my_bool_option: bool

        @configurable_pass
        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            my_bool_option: bool
            my_other_option: bool = dataclasses.field(init=False, default=flag)

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        config = MyConfig(my_bool_option=not flag)
        my_pass = MyPass.from_configuration(config)
        my_pass_normal = MyPass(not flag)
        assert my_pass == my_pass_normal

    @pytest.mark.parametrize("flag", [True, False])
    def test_passes_from_configuration(self, flag: bool) -> None:
        class MyConfig(Configuration, frozen=True):
            my_bool_option: bool

        @configurable_pass
        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            my_bool_option: bool

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        config = MyConfig(my_bool_option=flag)
        my_pass = MyPass.from_configuration(config)
        my_pass_from_tuple = MyPass.passes_from_configuration(config)
        assert (my_pass,) == my_pass_from_tuple

    @pytest.mark.parametrize("flag", [True, False])
    def test_automatic_configuration_conversion(self, flag: bool) -> None:
        class MySubConfig(Configuration, frozen=True):
            my_bool_option: bool
            my_list_option: list[int]
            my_string_option: str = "default_string"

        class MyConfig(Configuration, frozen=True):
            sub_conf: MySubConfig
            my_other_option: str | int

        @configurable_pass
        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            sub_conf: str | MySubConfig
            my_other_option: str | int

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        config = MyConfig(
            sub_conf=MySubConfig(my_bool_option=flag, my_list_option=[0, 1, 2, 3]),
            my_other_option="hello",
        )
        my_pass = MyPass(str(config.sub_conf), "hello")
        assert my_pass.sub_conf == config.sub_conf

    def test_config_properties(
        self,
    ) -> None:
        """Test that Configurations can use properties to define usable configuration parameters."""

        class MyConfig(Configuration, frozen=True):
            my_bool_option: bool
            my_other_option: bool

            @property
            def my_int_option(self) -> int:
                return int(self.my_bool_option) + int(self.my_other_option)

        @configurable_pass
        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            my_int_option: int

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        config = MyConfig(my_bool_option=True, my_other_option=True)
        my_pass = MyPass.from_configuration(config)
        assert my_pass == MyPass(2)

    @pytest.mark.parametrize("flag", [True, False])
    def test_pass_defaults(self, flag: bool):
        class MyConfig(Configuration, frozen=True):
            my_bool_option: bool
            my_other_option: bool

        @configurable_pass
        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            my_bool_option: bool = False
            my_defaulted_option: str = "default option"
            my_defaulted_factory_option: list[int] = field(default_factory=list)

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        config = MyConfig(my_bool_option=flag, my_other_option=False)
        my_pass = MyPass.from_configuration(config)
        my_pass_normal = MyPass(flag)
        assert my_pass == my_pass_normal

    def test_pass_full_config(self) -> None:
        class MyConfig(Configuration, frozen=True):
            my_bool_option: bool

        @configurable_pass
        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            the_config: Annotated[MyConfig, FieldPathSpec(field_name=".")] = field()

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        config = MyConfig(my_bool_option=True)
        my_pass = MyPass.from_configuration(config)
        my_pass_normal = MyPass(MyConfig(my_bool_option=True))
        assert my_pass == my_pass_normal
        assert my_pass.the_config is config

    def test_config_sub_types(self) -> None:
        class MyConfig(Configuration, frozen=True):
            my_bool_option: bool
            my_optional_int: None | int
            my_none: None = None

        @configurable_pass
        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            my_bool_or_none: Annotated[None | bool, FieldPathSpec(field_name="my_bool_option")]
            my_int_float_or_none: Annotated[
                None | float | int, FieldPathSpec(field_name="my_optional_int")
            ]
            my_none: None = None

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        config = MyConfig(my_bool_option=True, my_optional_int=None)
        my_pass = MyPass.from_configuration(config)
        my_pass_normal = MyPass(True, None)
        assert my_pass == my_pass_normal


class TestExecutionTimeErrors:
    """Test exceptions that are caused at execution time - ie when configs are used to try to create
    passes."""

    def test_invalid_pass_configuration(self) -> None:
        class MyConfig(Configuration, frozen=True):
            my_int: int

        class MyConfig2(Configuration, frozen=True):
            my_int: int

        @runtime_final
        @dataclass(frozen=True)
        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            my_int: int

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        config = MyConfig2(my_int=2)

        with pytest.raises(
            TypeError,
            match=r"expected <class '.*\.MyConfig'> but got <class '.*\.MyConfig2'>",
        ):
            MyPass.from_configuration(cast(MyConfig, config))

    def test_invalid_pass_literals(self) -> None:
        class MyConfig(Configuration, frozen=True):
            my_option: int

        @configurable_pass
        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            my_option: Literal[0, 11]

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        config = MyConfig(my_option=10)

        with pytest.raises(
            InvalidPassConfigurationException,
            match=re.escape(
                "Expected type typing.Literal[0, 11] for 'my_option' "
                "but got a <class 'int'> from the given Configuration"
            ),
        ):
            MyPass.from_configuration(config)

    def test_invalid_pass_field_path(self) -> None:
        class MyConfig(Configuration, frozen=True):
            sub_conf: int

        @runtime_final
        @dataclass(frozen=True)
        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            my_option: Annotated[int, FieldPathSpec("sub_conf")]

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        config = MyConfig(sub_conf=2)

        with pytest.raises(
            InvalidPassConfigurationException,
            match=re.escape(
                "'MyPass' requires a configuration at 'sub_conf' "
                "but 'my_option' is not a Configuration object"
            ),
        ):
            MyPass.from_configuration(config)

    def test_invalid_pass_field_missing(self) -> None:
        class MyConfig(Configuration, frozen=True):
            my_option: int

        @runtime_final
        @dataclass(frozen=True)
        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            my_options: int

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        config = MyConfig(my_option=2)

        with pytest.raises(
            InvalidPassConfigurationException,
            match=re.escape(
                "'MyPass' requires configuration 'my_options' "
                "but the given Configuration does not have a 'my_options' field or property"
            ),
        ):
            MyPass.from_configuration(config)

    def test_invalid_pass_nested_field_missing(self) -> None:
        class MySubConfig(Configuration, frozen=True):
            my_option: int

        class MyConfig(Configuration, frozen=True):
            sub_conf: MySubConfig

        @runtime_final
        @dataclass(frozen=True)
        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            my_options: Annotated[int, FieldPathSpec("sub_conf")]

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        config = MyConfig(sub_conf=MySubConfig(my_option=4))

        with pytest.raises(
            InvalidPassConfigurationException,
            match=re.escape(
                "'MyPass' requires configuration 'sub_conf.my_options' "
                "but the given Configuration does not have a "
                "'sub_conf.my_options' field or property"
            ),
        ):
            MyPass.from_configuration(config)

    def test_runtime_final_check(self) -> None:
        class MyConfig(Configuration, frozen=True):
            my_option: int

        @dataclass(frozen=True)
        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            my_option: int

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        config = MyConfig(my_option=4)

        with pytest.raises(
            InvalidConfigurablePassDefinitionException,
            match=re.escape(
                "Cannot instantiate a ConfigurablePass that is not runtime final. "
                "Class definition for 'MyPass' is probably missing the @configurable_pass decorator"
            ),
        ):
            MyPass.from_configuration(config)

    @pytest.mark.parametrize("flag", [True, False])
    def test_failed_automatic_configuration_conversion_multi_option(self, flag: bool) -> None:
        class MySubConfig(Configuration, frozen=True):
            my_bool_option: bool

        class MyConfig(Configuration, frozen=True):
            sub_conf: MySubConfig
            my_other_option: str | int

        @configurable_pass
        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            sub_conf: str | MySubConfig | MyConfig
            my_other_option: str | int

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        config = MyConfig(sub_conf=MySubConfig(my_bool_option=flag), my_other_option="hello")
        with pytest.raises(
            InvalidConfigYAML,
            match=(
                r"Could not validate model as any of "
                r"\[<class '.*\.MySubConfig'>, <class '.*\.MyConfig'>\]:\n"
                r"\tError loading MySubConfig: .*(\n|.)+"
                r"\tError loading MyConfig: .*(\n|.)+"
            ),
        ):
            MyPass(str(config.sub_conf) + "hello", "hello")

    @pytest.mark.parametrize("flag", [True, False])
    def test_failed_automatic_configuration_conversion(self, flag: bool) -> None:
        class MySubConfig(Configuration, frozen=True):
            my_bool_option: bool

        class MyConfig(Configuration, frozen=True):
            sub_conf: MySubConfig
            my_other_option: str | int

        @configurable_pass
        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            sub_conf: str | MySubConfig
            my_other_option: str | int

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        config = MyConfig(sub_conf=MySubConfig(my_bool_option=flag), my_other_option="hello")
        with pytest.raises(
            InvalidConfigYAML,
            match=(r"Error loading MySubConfig: .*(\n|.)+"),
        ):
            MyPass(str(config.sub_conf) + "hello", "hello")


class TestPassDefinitionErrors:
    """Test exceptions that are caused at the point of pass class definition."""

    def test_generic_subclass(self) -> None:
        """Tests that subclasses of ConfigurablePass[C] normally must not have a typevar
        for C."""
        C = TypeVar("C", bound=Configuration)

        with pytest.raises(
            InvalidConfigurablePassDefinitionException,
            match=re.escape(
                "Cannot automatically detect the type of the Configuration for 'MyPass': "
                "found TypeVar '~C' but expected concrete Configuration type"
            ),
        ):

            class MyPass(ConfigurablePass[C]):
                name = "my-pass"

    def test_invalid_configuration_type(self) -> None:
        """Tests that ConfigurablePasses have a valid _config_type type."""

        class MyFakeConfig:
            """Bad config"""

            my_bool: bool

        class MyConfig(Configuration, frozen=True):
            """Good config"""

            my_bool: bool

        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            my_bool: bool

        # mypy doing the right thing here, but we want to test this error behaviour
        MyPass._config_type = MyFakeConfig  # type: ignore[assignment, misc]

        with pytest.raises(
            InvalidConfigurablePassDefinitionException,
            match=re.escape("'MyPass._config_type' must be a subclass of Configuration"),
        ):
            configurable_pass(MyPass)

    def test_invalid_configuration_field(self) -> None:
        """Tests that ConfigurablePasses have Configurations with compatible types."""

        class MyConfig(Configuration, frozen=True):
            my_bool: str | bool | int

        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            my_bool: bool | str | float

        with pytest.raises(
            InvalidConfigurablePassDefinitionException,
            match=re.escape(
                "'MyPass' requires configuration 'my_bool' from 'MyConfig' "
                "but this field has type str | bool | int "
                "which is incompatible with 'MyPass.my_bool' that has type bool | str | float"
            ),
        ):
            configurable_pass(MyPass)

    def test_invalid_configuration_path_exists(self) -> None:
        """Tests that ConfigurablePasses have Configurations with compatible
        sub-configurations (that exist)."""

        class MyConfig(Configuration, frozen=True):
            my_bool: bool

        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            my_bool: Annotated[bool, FieldPathSpec("sub_conf")]

        with pytest.raises(
            InvalidConfigurablePassDefinitionException,
            match=re.escape(
                "'MyPass' requires configuration 'sub_conf.my_bool' from 'MyConfig' "
                "but 'MyConfig' does not have a 'sub_conf' field or property"
            ),
        ):
            configurable_pass(MyPass)

    def test_invalid_configuration_path_type(self) -> None:
        """Tests that ConfigurablePasses have Configurations with compatible
        sub-configurations (of Configuration type)."""

        @dataclass(frozen=True)
        class BadConfig:
            my_bool: bool

        class MyConfig(Configuration, frozen=True):
            sub_conf: BadConfig

        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            my_bool: Annotated[bool, FieldPathSpec("sub_conf")]

        with pytest.raises(
            InvalidConfigurablePassDefinitionException,
            match=re.escape(
                "'MyPass' requires a configuration at 'sub_conf' "
                "but this is not a Configuration object in MyConfig"
            ),
        ):
            configurable_pass(MyPass)

    def test_invalid_configuration_annotation_type(self) -> None:
        """Tests that ConfigurablePasses have Configurations with a type hint for each
        field."""

        class MyConfig(Configuration, frozen=True):
            my_bool: bool

        MyConfig.model_fields["my_bool"].annotation = None

        class MyPass(ConfigurablePass[MyConfig]):
            name = "my-pass"

            my_bool: bool

        with pytest.raises(
            InvalidConfigurablePassDefinitionException,
            match=re.escape(
                "All fields in a Configuration used by a ConfigurablePass must be typed "
                "but 'my_bool' in 'MyConfig' is not"
            ),
        ):
            configurable_pass(MyPass)

    def test_configurable_pass_on_wrong_class(self) -> None:
        """Tests that configurable_pass rejects incorrect classes."""

        class MyPass(ModulePass):
            name = "my-pass"

            my_bool: bool

        with pytest.raises(
            TypeError,
            match=r"Expected a subclass of ConfigurablePass but got <class '.*\.MyPass'>",
        ):
            configurable_pass(cast(type[ConfigurablePass], MyPass))


class TestPipeline:
    """Tests for the ConfigurablePipeline class"""

    @pytest.mark.parametrize("flag", [True, False])
    def test_simple_pipeline(self, flag: bool):
        class MyConfig(Configuration, frozen=True):
            my_bool_option: bool
            my_other_option: bool

        @configurable_pass
        class MyPass1(ConfigurablePass[MyConfig]):
            name = "my-pass-1"

            my_bool_option: bool

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        @configurable_pass
        class MyPass2(ConfigurablePass[MyConfig]):
            name = "my-pass-2"

            my_other_option: bool

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        @configurable_pass
        class MyPipeline(ConfigurablePipeline[MyConfig]):
            name = "my-pipeline"

            my_bool_option: bool

            @override
            def get_passes(self) -> tuple[ModulePass, ...]:
                if self.my_bool_option:
                    return (MyPass1(self.my_bool_option),)
                return (MyPass1(self.my_bool_option), MyPass2(not self.my_bool_option))

        config = MyConfig(my_bool_option=flag, my_other_option=False)
        my_pipeline = MyPipeline.from_configuration(config)
        my_pipeline_normal = MyPipeline(flag)
        assert my_pipeline == my_pipeline_normal

        assert my_pipeline.get_passes() == MyPipeline.passes_from_configuration(config)
        if flag:
            assert my_pipeline.get_passes() == (MyPass1(flag),)
        else:
            assert my_pipeline.get_passes() == (MyPass1(flag), MyPass2(not flag))

    @pytest.mark.parametrize("flag", [True, False])
    def test_multi_config_pipeline(self, flag: bool):
        class MyConfig1(Configuration, frozen=True):
            my_bool_option: bool
            my_other_option1: bool

        @configurable_pass
        class MyPass1(ConfigurablePass[MyConfig1]):
            name = "my-pass-1"

            my_bool_option: bool
            my_other_option1: bool

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        class MyConfig2(Configuration, frozen=True):
            my_bool_option: bool
            my_other_option2: bool

        @configurable_pass
        class MyPass2(ConfigurablePass[MyConfig2]):
            name = "my-pass-2"

            my_bool_option: bool
            my_other_option2: bool

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                pass

        class MyFullConfig(MyConfig1, frozen=True):
            my_other_option3: bool

        @configurable_pass
        class MyPipeline(ConfigurablePipeline[MyFullConfig]):
            name = "my-pipeline"

            my_bool_option: bool
            my_other_option1: bool
            # No config for my_other_option2
            my_other_option3: bool

            @override
            def get_passes(self) -> tuple[ModulePass, ...]:
                passes: list[ModulePass] = []
                passes.append(MyPass1(self.my_bool_option, my_other_option1=self.my_other_option1))
                passes.append(MyPass2(self.my_bool_option, my_other_option2=False))
                if self.my_other_option3:
                    passes.append(MyPass1(not self.my_bool_option, self.my_other_option1))
                return tuple(passes)

        config = MyFullConfig(my_bool_option=flag, my_other_option1=False, my_other_option3=True)
        my_pipeline = MyPipeline.from_configuration(config)
        my_pipeline_normal = MyPipeline(flag, False, True)
        assert my_pipeline == my_pipeline_normal

        assert my_pipeline.get_passes() == MyPipeline.passes_from_configuration(config)
        assert my_pipeline.get_passes() == (
            MyPass1(flag, False),
            MyPass2(flag, False),
            MyPass1(not flag, False),
        )

    @pytest.mark.parametrize("flag", [True, False])
    def test_pipeline_run(self, flag: bool) -> None:
        """Test that pipeline passes run properly."""

        class MyConfig(Configuration, frozen=True):
            my_bool_option: bool
            my_other_option: bool

        @configurable_pass
        class MyPass1(ConfigurablePass[MyConfig]):
            name = "my-pass-1"

            my_bool_option: bool

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                op.attributes[self.name] = IntAttr(int(self.my_bool_option))

        @configurable_pass
        class MyPass2(ConfigurablePass[MyConfig]):
            name = "my-pass-2"

            my_other_option: bool

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                op.attributes[self.name] = IntAttr(int(self.my_other_option))

        @configurable_pass
        class MyPipeline(ConfigurablePipeline[MyConfig]):
            name = "my-pipeline"

            my_bool_option: bool

            @override
            def get_passes(self) -> tuple[ModulePass, ...]:
                if self.my_bool_option:
                    return (MyPass1(self.my_bool_option),)
                return (MyPass1(self.my_bool_option), MyPass2(not self.my_bool_option))

        config = MyConfig(my_bool_option=flag, my_other_option=False)

        my_pipeline = MyPipeline.from_configuration(config)
        op1 = ModuleOp([])
        my_pipeline.apply(Context(), op1)

        passes = MyPipeline.passes_from_configuration(config)
        op2 = ModuleOp([])
        for p in passes:
            p.apply(Context(), op2)

        assert op1.is_structurally_equivalent(op2)

        assert op1.attributes["my-pass-1"] == IntAttr(int(flag))
        if not flag:
            assert op1.attributes["my-pass-2"] == IntAttr(int(True))

    def test_pipeline_verifies_between_passes(self) -> None:
        """Test we can use verify_between_passes in a config"""

        class MyConfig(Configuration, frozen=True):
            my_bool_option: bool
            verify_between_passes: bool

        @irdl_op_definition
        class FailOp(IRDLOperation):
            name = "test.fail"

            def verify_(self):
                msg = "Always fails"
                raise VerifyException(msg)

        @configurable_pass
        class MyPassAddsAttr(ConfigurablePass[MyConfig]):
            name = "my-pass-adds-attr"

            my_bool_option: bool

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                op.attributes[self.name] = IntAttr(int(self.my_bool_option))

        @configurable_pass
        class MyPassAddsFail(ConfigurablePass[MyConfig]):
            name = "my-pass-adds-fail"

            my_bool_option: bool

            @override
            def apply(self, ctx: Context, op: ModuleOp) -> None:
                Builder(InsertPoint.at_end(op.body.block)).insert_op(
                    FailOp(attributes={self.name: IntAttr(int(self.my_bool_option))})
                )

        @configurable_pass
        class MyPipeline1(ConfigurablePipeline[MyConfig]):
            name = "my-pipeline-1"

            my_bool_option: bool

            @override
            def get_passes(self) -> tuple[ModulePass, ...]:
                return (MyPassAddsAttr(self.my_bool_option), MyPassAddsFail(self.my_bool_option))

        @configurable_pass
        class MyPipeline2(ConfigurablePipeline[MyConfig]):
            name = "my-pipeline-2"

            my_bool_option: bool

            @override
            def get_passes(self) -> tuple[ModulePass, ...]:
                return (MyPassAddsFail(self.my_bool_option), MyPassAddsAttr(self.my_bool_option))

        op_with_fail = ModuleOp([FailOp()])

        config = MyConfig(my_bool_option=True, verify_between_passes=False)
        my_pipeline_1 = MyPipeline1.from_configuration(config)
        my_pipeline_1.apply(Context(), op_with_fail)

        config = MyConfig(my_bool_option=True, verify_between_passes=True)
        my_pipeline_1 = MyPipeline1.from_configuration(config)
        with pytest.raises(
            VerifyException,
            match=r"Always fails(\n|.)*"
            r"IR does not verify before 'my-pass-adds-attr' pass",
        ):
            my_pipeline_1.apply(Context(), op_with_fail)

        empty_op = ModuleOp([])

        my_pipeline_1 = MyPipeline1(True)
        my_pipeline_1.apply(Context(), empty_op)

        empty_op = ModuleOp([])

        my_pipeline_2 = MyPipeline2(True)
        my_pipeline_2.apply(Context(), empty_op)

    def test_pipeline_subclass(self) -> None:
        """Test that ConfigurablePipeline can be subclassed generically."""

        class MyConfig(Configuration, frozen=True):
            my_bool_option: bool
            my_other_option: bool

        @dataclass(frozen=True)
        class MyConfigurablePipeline(
            ConfigurablePipeline[ConfigurationT_contra], generic_subclass=True
        ):
            my_bool_option: bool

            @override
            def __init_subclass__(
                cls, generic_subclass: type[ConfigurablePass] | bool = False
            ) -> None:
                if generic_subclass is True:
                    return
                if generic_subclass is False:
                    generic_subclass = MyConfigurablePipeline
                super().__init_subclass__(generic_subclass=generic_subclass)

            def get_passes(self) -> tuple[ModulePass, ...]:
                return ()

        @configurable_pass
        class MyPass(MyConfigurablePipeline[MyConfig]):
            pass
