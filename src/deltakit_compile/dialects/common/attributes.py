# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Helper classes for creating and using attributes in dialects."""

from __future__ import annotations

import abc
import math
import types
from abc import abstractmethod
from collections.abc import Hashable, Iterator, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import (
    ClassVar,
    Generic,
    TypeVar,
    cast,
    get_args,
    get_origin,
    overload,
)

from typing_extensions import Self, override
from xdsl.dialects.builtin import (
    ArrayAttr,
    Float64Type,
    FloatAttr,
    FloatData,
    IntAttr,
)
from xdsl.ir import Attribute, Data, ParametrizedAttribute
from xdsl.irdl import isa
from xdsl.irdl.declarative_assembly_format import (
    AttributeVariable,
    CustomDirective,
    ParsingState,
    PrintingState,
    PunctuationDirective,
    TypeDirective,
    VariadicOperandVariable,
    irdl_custom_directive,
)
from xdsl.irdl.operations import IRDLOperation
from xdsl.parser import AttrParser, Parser
from xdsl.printer import Printer
from xdsl.utils.mlir_lexer import MLIRLexer, PunctuationSpelling

EnumT = TypeVar("EnumT", bound=Enum)


class PlainParsableAttribute(Attribute):
    """Superclass for all Attributes that can be printed and parsed plainly - without bracketing
    syntax.
    The main function is to provide helpers for generating CustomDirectives for the assembly format.
    """

    _PLAIN_DIRECTIVE: ClassVar[type[_PlainAttributeDirective]]
    """The class's plain attribute directive."""
    _PLAIN_ARRAY_DIRECTIVE: ClassVar[type[_PlainArrayOfAttributeDirective]]
    """The class's plain ArrayAttr[cls] directive."""

    @override
    def __init_subclass__(cls) -> None:
        super().__init_subclass__()

        plain_directive_name = f"Plain{cls.__name__}"
        plain_directive: type[_PlainAttributeDirective] = irdl_custom_directive(
            types.new_class(
                plain_directive_name,
                (_PlainAttributeDirective,),
                kwds={"attr_cls": cls},
                exec_body=lambda ns: ns.update({"__annotations__": {"attr": AttributeVariable}}),
            )
        )
        cls._PLAIN_DIRECTIVE = plain_directive

        plain_array_directive_name = f"PlainArrayOf{cls.__name__}"
        plain_array_directive: type[_PlainArrayOfAttributeDirective] = irdl_custom_directive(
            types.new_class(
                plain_array_directive_name,
                (_PlainArrayOfAttributeDirective,),
                kwds={"attr_cls": cls},
                exec_body=lambda ns: ns.update(
                    {
                        "__annotations__": {
                            "left_delimiter": PunctuationDirective,
                            "attr": AttributeVariable,
                            "right_delimiter": PunctuationDirective,
                        }
                    }
                ),
            )
        )
        cls._PLAIN_ARRAY_DIRECTIVE = plain_array_directive

    @overload
    @classmethod
    def plain_directive(
        cls,
    ) -> type[_PlainAttributeDirective]: ...

    @overload
    @classmethod
    def plain_directive(cls, arg: str) -> str: ...

    @classmethod
    def plain_directive(cls, arg: str | None = None) -> type[_PlainAttributeDirective] | str:
        """Get an assembly format custom directive for printing and parsing this element.
        If an arg string is given, return the assembly format fragment that calls the custom
        directive with the given argument."""
        if arg is None:
            return cls._PLAIN_DIRECTIVE
        return cls._PLAIN_DIRECTIVE.use(arg)

    @overload
    @classmethod
    def plain_array_of_directive(
        cls,
    ) -> type[_PlainArrayOfAttributeDirective]: ...

    @overload
    @classmethod
    def plain_array_of_directive(
        cls,
        arg: str,
        left_delimiter: PunctuationSpelling = "[",
        right_delimiter: PunctuationSpelling = "]",
    ) -> str: ...

    @classmethod
    def plain_array_of_directive(
        cls,
        arg: str | None = None,
        left_delimiter: PunctuationSpelling = "[",
        right_delimiter: PunctuationSpelling = "]",
    ) -> type[_PlainArrayOfAttributeDirective] | str:
        """Get an assembly format custom directive for printing and parsing an ArrayAttr of this
        element.
        If an arg string is given, return the assembly format fragment that calls the custom
        directive with the given argument."""
        if arg is None:
            return cls._PLAIN_ARRAY_DIRECTIVE
        return cls._PLAIN_ARRAY_DIRECTIVE.use(arg, left_delimiter, right_delimiter)

    @classmethod
    @abstractmethod
    def parse_inner(cls, parser: AttrParser) -> Self:
        """Parse a plain instance of this Attribute."""

    @abstractmethod
    def print_inner(self, printer: Printer) -> None:
        """Print a plain instance of this Attribute."""


@dataclass(frozen=True)
class _PlainAttributeDirective(CustomDirective):
    """Custom printing and parsing Assembly Format Directive for any subclass of
    PlainParsableAttribute. Prints and parses the plain data without needing the attribute name or
    other syntax.
    """

    attr: AttributeVariable
    _PARSABLE: ClassVar[type[PlainParsableAttribute]]
    """The PlainParsableAttribute type to print and parse."""

    @override
    def __init_subclass__(cls, *, attr_cls: type[PlainParsableAttribute]) -> None:
        super().__init_subclass__()
        cls._PARSABLE = attr_cls

    @classmethod
    def use(cls, format_arg: str) -> str:
        """Get an assembly format fragment that will use this CustomDirective."""
        return f" custom<{cls.__name__}>({format_arg}) "

    @override
    def parse(self, parser: Parser, state: ParsingState) -> bool:
        value = self._PARSABLE.parse_inner(parser)
        self.attr.set(state, value)
        return True

    @override
    def print(self, printer: Printer, state: PrintingState, op: IRDLOperation) -> None:
        state.print_whitespace(printer)
        attr = self.attr.get(op)
        assert isa(attr, self._PARSABLE)
        attr.print_inner(printer)

    @override
    def is_present(self, op: IRDLOperation) -> bool:
        return self.attr.get(op) is not None

    @override
    def is_anchorable(self) -> bool:
        return True


@dataclass(frozen=True)
class _PlainArrayOfAttributeDirective(CustomDirective):
    """Custom printing and parsing Assembly Format Directive for any ArrayAttr of a subclass of
    PlainParsableAttribute.
    Prints and parses a comma separated list, in delimiters, of the plain data without needing
    the attribute name or other syntax.
    """

    left_delimiter: PunctuationDirective
    attr: AttributeVariable
    right_delimiter: PunctuationDirective

    _PARSABLE: ClassVar[type[PlainParsableAttribute]]
    """The PlainParsableAttribute to print and parse an ArrayAttr of."""

    @override
    def __init_subclass__(cls, *, attr_cls: type[PlainParsableAttribute]) -> None:
        super().__init_subclass__()
        cls._PARSABLE = attr_cls

    @classmethod
    def use(
        cls,
        format_arg: str,
        left_delimiter: PunctuationSpelling = "[",
        right_delimiter: PunctuationSpelling = "]",
    ) -> str:
        """Get an assembly format fragment that will use this CustomDirective."""
        return f" custom<{cls.__name__}>(`{left_delimiter}`, {format_arg}, `{right_delimiter}`) "

    @override
    def parse(self, parser: Parser, state: ParsingState) -> bool:
        list_opened = self.left_delimiter.parse_optional(parser, state)
        if not list_opened:
            return False
        empty_list = self.right_delimiter.parse_optional(parser, state)
        if empty_list:
            self.attr.set(state, ArrayAttr([]))
            return True
        attr_list = parser.parse_comma_separated_list(
            parser.Delimiter.NONE, lambda: self._PARSABLE.parse_inner(parser)
        )

        list_closed = self.right_delimiter.parse(parser, state)
        if not list_closed:
            parser.raise_error(f"Expected closing delimiter: '{self.right_delimiter.punctuation}'")

        self.attr.set(state, ArrayAttr(attr_list))
        return True

    @override
    def print(self, printer: Printer, state: PrintingState, op: IRDLOperation) -> None:
        array_attr = self.attr.get(op)
        assert isa(array_attr, ArrayAttr)
        self.left_delimiter.print(printer, state, op)
        for i, element in enumerate(array_attr):
            if i:
                printer.print_string(", ")
            assert isa(element, self._PARSABLE)
            element.print_inner(printer)

        self.right_delimiter.print(printer, state, op)

    @override
    def is_present(self, op: IRDLOperation) -> bool:
        return self.attr.get(op) is not None

    @override
    def is_anchorable(self) -> bool:
        return True

    @override
    def is_optional_like(self) -> bool:
        return self.left_delimiter.is_optional_like()


DataElement_co = TypeVar("DataElement_co", covariant=True, bound=Hashable)


class PlainParsableData(PlainParsableAttribute, Data[DataElement_co], Generic[DataElement_co]):
    """Superclass for Data Attributes that can be printed and parsed plainly - without bracketing
    syntax.
    """

    @classmethod
    @abstractmethod
    def parse_inner_parameter(cls, parser: AttrParser) -> DataElement_co:
        """Parses the inner data value plainly - without surrounding bracketing"""

    @override
    @classmethod
    def parse_parameter(cls, parser: AttrParser) -> DataElement_co:
        with parser.in_angle_brackets():
            return cls.parse_inner_parameter(parser)

    @override
    @classmethod
    def parse_inner(cls, parser: AttrParser) -> Self:
        """Parse a plain instance of this Attribute."""
        return cls.new(cls.parse_inner_parameter(parser))

    @abstractmethod
    def print_inner_parameter(self, printer: Printer) -> None:
        """Prints the plain inner data value - without surrounding bracketing"""

    @override
    def print_parameter(self, printer: Printer) -> None:
        """Print the attribute parameter."""
        with printer.in_angle_brackets():
            self.print_inner_parameter(printer)

    @override
    def print_inner(self, printer: Printer) -> None:
        """Print a plain instance of this Attribute."""
        self.print_inner_parameter(printer)


class PlainParsableParameterizedAttribute(PlainParsableAttribute, ParametrizedAttribute):
    """Superclass for ParametrizedAttributes that can be printed and parsed plainly - without
    bracketing syntax.

    When subclassing this class both ``parse_inner_parameters`` and ``print_inner`` (from
    PlainParsableAttribute) must be implemented.
    """

    @classmethod
    @abstractmethod
    def parse_inner_parameters(cls, parser: AttrParser) -> Sequence[Attribute]:
        """Parses the inner data plainly into the Attributes that Parameterise this Attribute
        - without surrounding bracketing."""

    @override
    @classmethod
    def parse_parameters(cls, parser: AttrParser) -> Sequence[Attribute]:
        with parser.in_angle_brackets():
            return cls.parse_inner_parameters(parser)

    @override
    @classmethod
    def parse_inner(cls, parser: AttrParser) -> Self:
        return cls.new(cls.parse_inner_parameters(parser))

    @override
    def print_parameters(self, printer: Printer) -> None:
        with printer.in_angle_brackets():
            self.print_inner(printer)


AnyEnumAttributeT = TypeVar("AnyEnumAttributeT")


class _AnyEnumAttributeTypeMeta(abc.ABCMeta):
    """Metaclass that adds an __iter__ method to the type of a AnyEnumAttribute.
    This should only be used by AnyEnumAttribute."""

    def __iter__(cls: type[AnyEnumAttributeT]) -> Iterator[AnyEnumAttributeT]:
        """Iterate through each `Attribute` this class defines based on the underlying Enum."""
        assert issubclass(cls, AnyEnumAttribute)
        yield from [cls.from_argument(enum_val) for enum_val in cls._enum_type]


class AnyEnumAttribute(PlainParsableData[EnumT], metaclass=_AnyEnumAttributeTypeMeta):
    """Use any Enum as an attribute. Supports parsing and printing based on the Enum instances'
    `.name` field, or if `use_values=True` the value of the enum is used (In this case the value
    must define equality with a str that can be parsed as an identifier, and __str__ to get back
    the same string).
    This class is based on xdsl's EnumAttribute class that achieves effectively the same thing but
    is restricted to just StrEnums
    """

    _enum_type: ClassVar[type[Enum]]
    _use_values: ClassVar[bool]

    def __init__(self, value: EnumT):
        if type(self) is AnyEnumAttribute:
            msg = (
                f"{type(self).__name__} cannot be directly initialised. It must be subclassed to "
                "provide the enum type."
            )
            raise TypeError(msg)
        try:
            value = cast(EnumT, type(self)._enum_type(value))
        except (ValueError, TypeError) as error:
            msg = (
                f"Cannot initialise {type(self).__name__} with "
                f"non-'{type(self)._enum_type.__name__}' value: '{value}'"
            )
            raise ValueError(msg) from error
        super().__init__(value)

    @override
    def __init_subclass__(cls, use_values: bool = False) -> None:
        super().__init_subclass__()
        orig_bases = cls.__orig_bases__  # type: ignore[attr-defined]
        enum_attr = next(b for b in orig_bases if get_origin(b) is AnyEnumAttribute)
        enum_type = get_args(enum_attr)[0]
        if isinstance(enum_type, TypeVar):
            msg = "Only direct inheritance from AnyEnumAttribute is allowed"
            raise TypeError(msg)
        assert issubclass(enum_type, Enum)
        for enum_instance in enum_type:
            matchable = str(enum_instance.value) if use_values else enum_instance.name
            if MLIRLexer.bare_identifier_suffix_regex.fullmatch(matchable) is None:
                msg = "All enumerated variables of an Enum must be parsable as an identifier"
                raise TypeError(msg)
        cls._enum_type = enum_type
        cls._use_values = use_values

    @override
    @classmethod
    def parse_inner_parameter(cls, parser: AttrParser) -> EnumT:
        """Parses the plain enum that this AnyEnumAttribute stores.
        If use_values was set then an identifier is parsed and the first matching value is selected.
        Otherwise the name of the enum values is used."""
        if cls._use_values:
            identifier = parser.parse_identifier(f" to be a value of a {cls._enum_type.__name__}.")
            for value in cls._enum_type:
                if value.value == identifier:
                    return cast(EnumT, value)
            parser.raise_error(
                f"Expected the value of one of the members of {cls._enum_type.__name__}: "
                f"[{', '.join(str(value.value) for value in cls._enum_type)}] "
                f"but got {identifier}."
            )
        names = [state.name for state in cls._enum_type]
        identifier = parser.parse_identifier(f" {cls._enum_type.__name__}: [{', '.join(names)}].")
        if identifier not in names:
            parser.raise_error(f"Expected one of: [{', '.join(names)}] but got {identifier}.")
        state = cls._enum_type[identifier]
        return cast(EnumT, state)

    @override
    def print_inner_parameter(self, printer: Printer) -> None:
        """Prints the plain enum (name) that this AnyEnumAttribute stores."""
        if self._use_values:
            printer.print_string(str(self.data.value))
        else:
            printer.print_string(self.data.name)

    @overload
    @classmethod
    def from_argument(cls, argument: Self | EnumT) -> Self: ...

    @overload
    @classmethod
    def from_argument(cls, argument: Self | EnumT | None) -> Self | None: ...

    @classmethod
    def from_argument(cls, argument: Self | EnumT | None) -> Self | None:
        """Helper method to turn an argument that could be an EnumT, AnyEnumAttribute[EnumT], or
        None into an AnyEnumAttribute[EnumT] or None"""
        if argument is None:
            return None
        if isinstance(argument, cls):
            return argument
        return cls(cast(EnumT, argument))


@irdl_custom_directive
class OptPlainIntAttr(CustomDirective):
    """Custom printing and parsing declaration for an optional IntAttr property in the form `109`
    instead of `#builtin.int<109>`"""

    attr: AttributeVariable

    @override
    def parse(self, parser: Parser, state: ParsingState) -> bool:
        value = parser.parse_optional_integer(allow_boolean=False)
        if value is not None:
            self.attr.set(state, IntAttr(value))
        return value is not None

    @override
    def print(self, printer: Printer, state: PrintingState, op: IRDLOperation) -> None:
        state.print_whitespace(printer)
        int_attr = self.attr.get(op)
        assert isinstance(int_attr, IntAttr)
        printer.print_int(int_attr.data)

    @override
    def is_present(self, op: IRDLOperation) -> bool:
        return self.attr.get(op) is not None

    @override
    def is_anchorable(self) -> bool:
        return True

    @override
    def is_optional_like(self) -> bool:
        return True

    @classmethod
    def use(cls, argument: str) -> str:
        """Returns the custom assembly format fragment that will call this method on the argument
        given. Used inside an Operation's assembly format definition eg:
        ```
            assembly_format = f"... {OptPlainIntAttr.use('$my_int')} ..."
            custom_directives = (OptPlainIntAttr,)
        ```
        """
        return f"custom<{cls.__name__}>({argument})"


@irdl_custom_directive
class PlainIntAttr(CustomDirective):
    """Custom printing and parsing declaration for an IntAttr property in the form `109`
    instead of `#builtin.int<109>`"""

    attr: AttributeVariable

    @override
    def parse(self, parser: Parser, state: ParsingState) -> bool:
        value = parser.parse_integer(allow_boolean=False)
        self.attr.set(state, IntAttr(value))
        return True

    @override
    def print(self, printer: Printer, state: PrintingState, op: IRDLOperation) -> None:
        state.print_whitespace(printer)
        int_attr = self.attr.get(op)
        assert isinstance(int_attr, IntAttr)
        printer.print_int(int_attr.data)

    @classmethod
    def use(cls, argument: str) -> str:
        """Returns the custom assembly format fragment that will call this method on the argument
        given. Used inside an Operation's assembly format definition eg:
        ```
            assembly_format = f"... {PlainIntAttr.use('$my_int')} ..."
            custom_directives = (PlainIntAttr,)
        ```
        """
        return f"custom<{cls.__name__}>({argument})"


@irdl_custom_directive
class PlainArrayOfIntAttrDirective(CustomDirective):
    """Custom printing and parsing declaration for an ArrayAttr[IntAttr] property in
    the form::

        [1, 0, -10, 2]

    instead of::

         [#builtin.int<1>, #builtin.int<0>, #builtin.int<-10>, #builtin.int<2>]"""

    attr: AttributeVariable

    @override
    def parse(self, parser: Parser, state: ParsingState) -> bool:
        values = parser.parse_comma_separated_list(
            parser.Delimiter.SQUARE, lambda: parser.parse_integer(allow_boolean=False)
        )
        attr = ArrayAttr([IntAttr(value) for value in values])
        self.attr.set(state, attr)
        return True

    @override
    def print(self, printer: Printer, state: PrintingState, op: IRDLOperation) -> None:
        state.print_whitespace(printer)
        attr = self.attr.get(op)
        assert isa(attr, ArrayAttr[IntAttr])
        with printer.in_square_brackets():
            printer.print_list(attr, lambda value: printer.print_int(value.data))

    @classmethod
    def use(cls, argument: str) -> str:
        """Returns the custom assembly format fragment that will call this method on the argument
        given. Used inside an Operation's assembly format definition eg:
        ```
            assembly_format = f"... {PlainArrayOfIntAttrDirective.use('$my_array')} ..."
            custom_directives = (PlainArrayOfIntAttrDirective,)
        ```
        """
        return f"custom<{cls.__name__}>({argument})"

    @override
    def is_anchorable(self):
        return True

    @override
    def is_present(self, op):
        return self.attr.get(op) is not None


@irdl_custom_directive
class PlainArrayOfArrayOfIntAttrDirective(CustomDirective):
    """Custom printing and parsing declaration for an ArrayAttr[ArrayAttr[IntAttr]] property in
    the form::

        [[1], [1, 2], []]

    instead of::

         [[#builtin.int<1>], [#builtin.int<1>, #builtin.int<2>], []]"""

    attr: AttributeVariable

    @override
    def parse(self, parser: Parser, state: ParsingState) -> bool:
        values = parser.parse_comma_separated_list(
            parser.Delimiter.SQUARE,
            lambda: parser.parse_comma_separated_list(
                parser.Delimiter.SQUARE, lambda: parser.parse_integer(allow_boolean=False)
            ),
        )
        attr = ArrayAttr([ArrayAttr([IntAttr(i) for i in value]) for value in values])
        self.attr.set(state, attr)
        return True

    @override
    def print(self, printer: Printer, state: PrintingState, op: IRDLOperation) -> None:
        state.print_whitespace(printer)
        attr = self.attr.get(op)
        assert isa(attr, ArrayAttr[ArrayAttr[IntAttr]])

        def print_inner(inner_array: ArrayAttr[IntAttr]) -> None:
            with printer.in_square_brackets():
                printer.print_list(inner_array, lambda value: printer.print_int(value.data))

        with printer.in_square_brackets():
            printer.print_list(attr, print_inner)

    @classmethod
    def use(cls, argument: str) -> str:
        """Returns the custom assembly format fragment that will call this method on the argument
        given. Used inside an Operation's assembly format definition eg::

            assembly_format = f"... {PlainArrayOfArrayOfIntAttrDirective.use('$my_array')} ..."
            custom_directives = (PlainArrayOfArrayOfIntAttrDirective,)
        """
        return f"custom<{cls.__name__}>({argument})"

    @override
    def is_anchorable(self):
        return True

    @override
    def is_present(self, op):
        return self.attr.get(op) is not None


@irdl_custom_directive
class RepeatedOperandType(CustomDirective):
    """Custom printing and parsing declaration for a type that is repeated N times."""

    types: TypeDirective
    reference: VariadicOperandVariable

    @override
    def parse(self, parser: Parser, state: ParsingState) -> bool:
        type_attr = parser.parse_optional_type()
        if type_attr is None:
            self.types.set_empty(state)
            return False
        unresolved_operands = state.operands[self.reference.index]
        assert unresolved_operands is not None, (
            "RepeatedOperandType must come after the reference has been parsed."
        )
        length = len(unresolved_operands)
        self.types.set(state, [type_attr] * length)
        return True

    @override
    def set_empty(self, state: ParsingState) -> None:
        self.types.set_empty(state)
        super().set_empty(state)

    @override
    def print(self, printer: Printer, state: PrintingState, op: IRDLOperation) -> None:
        state.print_whitespace(printer)
        type_attrs = self.types.get(op)
        assert len(set(type_attrs)) == 1
        printer.print_attribute(type_attrs[0])

    @override
    def is_present(self, op: IRDLOperation) -> bool:
        return len(self.types.get(op)) > 0

    @override
    def is_anchorable(self) -> bool:
        return True

    @override
    def is_optional_like(self) -> bool:
        return True


def float64_to_string(value: float | FloatData | FloatAttr[Float64Type]) -> str:
    """Returns a canonical string form for floats across dialects.

    The format matches the precision xDSL uses for Float64Type() but avoids using scientific
    notation so that `0.1` stays as `0.1` instead of `1.000000e-01` where reasonable.

    Use ``parse_float64`` to parse the strings back into floats to ensure consistency and
    compatibility.
    The result is parsable with ``Parser.parse_float`` or ``Parser.parse_number`` unless it is
    `nan`, `inf`, or `-inf`. If the floating point value is `+inf`, `-inf`, or `nan` then `'inf'`,
    `'-inf'`, and `'nan'` are used respectively.

    """
    if isinstance(value, FloatAttr):
        value = value.value
    if isinstance(value, FloatData):
        value = value.data
    value = float(value)

    #  Handle the edge cases
    if math.isnan(value):
        return "nan"
    if math.isinf(value):
        return "-inf" if value < 0 else "inf"

    # Attempt to use a nice printing format with up to 10 decimal places.
    float_str = f"{value:.10f}"

    # Remove white space and unnecessary trailing 0s
    float_str = float_str.strip().rstrip("0")
    if float_str.endswith("."):
        float_str = float_str + "0"

    # If this string perfectly parses back to the same value, and isn't much longer than
    # the normal str representation then accept it.
    if float(float_str) == value and len(float_str) <= len(str(value)) + 2:
        return float_str

    # Fall back to default str method that might use scientific notation.
    float_str = str(value)
    # Ensure that any use of scientific notation maintains the a decimal place so it is correctly
    # identifiable / parsable as a float by xDSL.
    if "." not in float_str:
        index = float_str.index("e")
        float_str = float_str[:index] + ".0" + float_str[index:]
    return float_str


def parse_optional_float64(parser: AttrParser) -> float | None:
    """Parses an optional floating point number generated in the canonical form by
    ``float64_to_string``.
    Also parses an integer into a float for convenience."""

    is_negative = bool(parser.parse_optional_punctuation("-"))
    if parser.parse_optional_keyword("nan"):
        return math.nan
    if parser.parse_optional_keyword("inf"):
        return -math.inf if is_negative else math.inf

    if (
        integer := parser.parse_optional_integer(allow_boolean=False, allow_negative=False)
    ) is not None:
        return float(-integer) if is_negative else float(integer)

    number = parser.parse_optional_float(allow_negative=False)
    if is_negative and number is None:
        parser.raise_error("Expected a floating point number following a '-'.")
    if number is None:
        return None
    return -number if is_negative else number


def parse_float64(parser: AttrParser) -> float:
    """Parses a floating point number generated in the canonical form by ``float64_to_string``.
    Also parses an integer into a float for convenience."""
    return parser.expect(lambda: parse_optional_float64(parser), "Expected float literal")


@irdl_custom_directive
class PlainFloat64Directive(CustomDirective):
    """Custom printing and parsing declaration for a FloatAttr[Float64Type] property in the form
    `0.1` instead of `1.000000e-01`"""

    attr: AttributeVariable

    @override
    def parse(self, parser: Parser, state: ParsingState) -> bool:
        value = parse_float64(parser)
        self.attr.set(state, FloatAttr(value, Float64Type()))
        return True

    @override
    def print(self, printer: Printer, state: PrintingState, op: IRDLOperation) -> None:
        state.print_whitespace(printer)
        float_attr = self.attr.get(op)
        assert isa(float_attr, FloatAttr[Float64Type])
        printer.print_string(float64_to_string(float_attr))

    @classmethod
    def use(cls, argument: str) -> str:
        """Returns the custom assembly format fragment that will call this method on the argument
        given. Used inside an Operation's assembly format definition eg:
        ```
            assembly_format = f"... {PlainFloat64Directive.use('$my_float')} ..."
            custom_directives = (PlainFloat64Directive,)
        ```
        """
        return f"custom<{cls.__name__}>({argument})"


@irdl_custom_directive
class OptPlainFloat64Directive(CustomDirective):
    """Custom printing and parsing declaration for an optional FloatAttr[Float64Type] property in
    the form `0.1` instead of `1.000000e-01`"""

    attr: AttributeVariable

    @override
    def parse(self, parser: Parser, state: ParsingState) -> bool:
        value = parse_optional_float64(parser)
        if value is not None:
            self.attr.set(state, FloatAttr(value, Float64Type()))
        return value is not None

    @override
    def print(self, printer: Printer, state: PrintingState, op: IRDLOperation) -> None:
        state.print_whitespace(printer)
        float_attr = self.attr.get(op)
        assert isa(float_attr, FloatAttr[Float64Type])
        printer.print_string(float64_to_string(float_attr))

    @override
    def is_present(self, op: IRDLOperation) -> bool:
        return self.attr.get(op) is not None

    @override
    def is_anchorable(self) -> bool:
        return True

    @override
    def is_optional_like(self) -> bool:
        return True

    @classmethod
    def use(cls, argument: str) -> str:
        """Returns the custom assembly format fragment that will call this method on the argument
        given. Used inside an Operation's assembly format definition eg:
        ```
            assembly_format = f"... {OptPlainFloat64Directive.use('$my_float')} ..."
            custom_directives = (OptPlainFloat64Directive,)
        ```
        """
        return f"custom<{cls.__name__}>({argument})"


@irdl_custom_directive
class PlainArrayOfFloat64Directive(CustomDirective):
    """Custom printing and parsing declaration for an ArrayAttr[FloatAttr[Float64Type]] property in
    the form::

        [1.0, 0.01, -1.0e-61]

    instead of::

         [1.000000e+00 : f64, 1.000000e-02 : f64, -1.0000000e-61 : f64]"""

    attr: AttributeVariable

    @override
    def parse(self, parser: Parser, state: ParsingState) -> bool:
        values = parser.parse_comma_separated_list(
            parser.Delimiter.SQUARE, lambda: parse_float64(parser)
        )
        attr = ArrayAttr([FloatAttr(value, Float64Type()) for value in values])
        self.attr.set(state, attr)
        return True

    @override
    def print(self, printer: Printer, state: PrintingState, op: IRDLOperation) -> None:
        state.print_whitespace(printer)
        attr = self.attr.get(op)
        assert isa(attr, ArrayAttr[FloatAttr[Float64Type]])
        with printer.in_square_brackets():
            printer.print_list(attr, lambda value: printer.print_string(float64_to_string(value)))

    @classmethod
    def use(cls, argument: str) -> str:
        """Returns the custom assembly format fragment that will call this method on the argument
        given. Used inside an Operation's assembly format definition eg:
        ```
            assembly_format = f"... {PlainArrayOfFloat64Directive.use('$my_array')} ..."
            custom_directives = (PlainArrayOfFloat64Directive,)
        ```
        """
        return f"custom<{cls.__name__}>({argument})"


@irdl_custom_directive
class OptPlainArrayOfFloat64Directive(CustomDirective):
    """Custom printing and parsing declaration for an optional ArrayAttr[FloatAttr[Float64Type]]
    property in the form::

        [1.0, 0.01, -1.0e-61]

    instead of::

         [1.000000e+00 : f64, 1.000000e-02 : f64, -1.0000000e-61 : f64]"""

    attr: AttributeVariable

    @override
    def parse(self, parser: Parser, state: ParsingState) -> bool:
        values = parser.parse_optional_comma_separated_list(
            parser.Delimiter.SQUARE, lambda: parse_float64(parser)
        )
        if values is not None:
            attr = ArrayAttr([FloatAttr(value, Float64Type()) for value in values])
            self.attr.set(state, attr)
        return values is not None

    @override
    def print(self, printer: Printer, state: PrintingState, op: IRDLOperation) -> None:
        state.print_whitespace(printer)
        attr = self.attr.get(op)
        assert isa(attr, ArrayAttr[FloatAttr[Float64Type]])
        with printer.in_square_brackets():
            printer.print_list(attr, lambda value: printer.print_string(float64_to_string(value)))

    @override
    def is_present(self, op: IRDLOperation) -> bool:
        return self.attr.get(op) is not None

    @override
    def is_anchorable(self) -> bool:
        return True

    @override
    def is_optional_like(self) -> bool:
        return True

    @classmethod
    def use(cls, argument: str) -> str:
        """Returns the custom assembly format fragment that will call this method on the argument
        given. Used inside an Operation's assembly format definition eg:
        ```
            assembly_format = f"... {OptPlainArrayOfFloat64Directive.use('$my_array')} ..."
            custom_directives = (OptPlainArrayOfFloat64Directive,)
        ```
        """
        return f"custom<{cls.__name__}>({argument})"


@irdl_custom_directive
class PlainFloatDataDirective(CustomDirective):
    """Custom printing and parsing declaration for a FloatData property in the form
    `0.1` instead of `1.000000e-01`. Assumes an underlying float64 is sufficient precision."""

    attr: AttributeVariable

    @override
    def parse(self, parser: Parser, state: ParsingState) -> bool:
        value = parse_float64(parser)
        self.attr.set(state, FloatData(value))
        return True

    @override
    def print(self, printer: Printer, state: PrintingState, op: IRDLOperation) -> None:
        state.print_whitespace(printer)
        float_attr = self.attr.get(op)
        assert isa(float_attr, FloatData)
        printer.print_string(float64_to_string(float_attr))

    @classmethod
    def use(cls, argument: str) -> str:
        """Returns the custom assembly format fragment that will call this method on the argument
        given. Used inside an Operation's assembly format definition eg:
        ```
            assembly_format = f"... {PlainFloatDataDirective.use('$my_float')} ..."
            custom_directives = (PlainFloatDataDirective,)
        ```
        """
        return f"custom<{cls.__name__}>({argument})"


@irdl_custom_directive
class OptPlainFloatDataDirective(CustomDirective):
    """Custom printing and parsing declaration for an optional FloatData property in
    the form `0.1` instead of `1.000000e-01`. Assumes an underlying float64 is sufficient
    precision."""

    attr: AttributeVariable

    @override
    def parse(self, parser: Parser, state: ParsingState) -> bool:
        value = parse_optional_float64(parser)
        if value is not None:
            self.attr.set(state, FloatData(value))
        return value is not None

    @override
    def print(self, printer: Printer, state: PrintingState, op: IRDLOperation) -> None:
        state.print_whitespace(printer)
        float_attr = self.attr.get(op)
        assert isa(float_attr, FloatData)
        printer.print_string(float64_to_string(float_attr))

    @override
    def is_present(self, op: IRDLOperation) -> bool:
        return self.attr.get(op) is not None

    @override
    def is_anchorable(self) -> bool:
        return True

    @override
    def is_optional_like(self) -> bool:
        return True

    @classmethod
    def use(cls, argument: str) -> str:
        """Returns the custom assembly format fragment that will call this method on the argument
        given. Used inside an Operation's assembly format definition eg:
        ```
            assembly_format = f"... {OptPlainFloatDataDirective.use('$my_float')} ..."
            custom_directives = (OptPlainFloatDataDirective,)
        ```
        """
        return f"custom<{cls.__name__}>({argument})"


@irdl_custom_directive
class PlainArrayOfFloatDataDirective(CustomDirective):
    """Custom printing and parsing declaration for an ArrayAttr[FloatData] property in
    the form::

        [1.0, 0.01, -1.0e-61]

    instead of::

         [1.000000e+00 : f64, 1.000000e-02 : f64, -1.0000000e-61 : f64]

    Assumes an underlying float64 is sufficient precision."""

    attr: AttributeVariable

    @override
    def parse(self, parser: Parser, state: ParsingState) -> bool:
        values = parser.parse_comma_separated_list(
            parser.Delimiter.SQUARE, lambda: parse_float64(parser)
        )
        attr = ArrayAttr([FloatData(value) for value in values])
        self.attr.set(state, attr)
        return True

    @override
    def print(self, printer: Printer, state: PrintingState, op: IRDLOperation) -> None:
        state.print_whitespace(printer)
        attr = self.attr.get(op)
        assert isa(attr, ArrayAttr[FloatData])
        with printer.in_square_brackets():
            printer.print_list(attr, lambda value: printer.print_string(float64_to_string(value)))

    @classmethod
    def use(cls, argument: str) -> str:
        """Returns the custom assembly format fragment that will call this method on the argument
        given. Used inside an Operation's assembly format definition eg:
        ```
            assembly_format = f"... {PlainArrayOfFloatDataDirective.use('$my_array')} ..."
            custom_directives = (PlainArrayOfFloatDataDirective,)
        ```
        """
        return f"custom<{cls.__name__}>({argument})"


@irdl_custom_directive
class OptPlainArrayOfFloatDataDirective(CustomDirective):
    """Custom printing and parsing declaration for an optional ArrayAttr[FloatData]
    property in the form::

        [1.0, 0.01, -1.0e-61]

    instead of::

         [1.000000e+00 : f64, 1.000000e-02 : f64, -1.0000000e-61 : f64]

    Assumes an underlying float64 is sufficient precision."""

    attr: AttributeVariable

    @override
    def parse(self, parser: Parser, state: ParsingState) -> bool:
        values = parser.parse_optional_comma_separated_list(
            parser.Delimiter.SQUARE, lambda: parse_float64(parser)
        )
        if values is not None:
            attr = ArrayAttr([FloatData(value) for value in values])
            self.attr.set(state, attr)
        return values is not None

    @override
    def print(self, printer: Printer, state: PrintingState, op: IRDLOperation) -> None:
        state.print_whitespace(printer)
        attr = self.attr.get(op)
        assert isa(attr, ArrayAttr[FloatData])
        with printer.in_square_brackets():
            printer.print_list(attr, lambda value: printer.print_string(float64_to_string(value)))

    @override
    def is_present(self, op: IRDLOperation) -> bool:
        return self.attr.get(op) is not None

    @override
    def is_anchorable(self) -> bool:
        return True

    @override
    def is_optional_like(self) -> bool:
        return True

    @classmethod
    def use(cls, argument: str) -> str:
        """Returns the custom assembly format fragment that will call this method on the argument
        given. Used inside an Operation's assembly format definition eg:
        ```
            assembly_format = f"... {OptPlainArrayOfFloatDataDirective.use('$my_array')} ..."
            custom_directives = (OptPlainArrayOfFloatDataDirective,)
        ```
        """
        return f"custom<{cls.__name__}>({argument})"
