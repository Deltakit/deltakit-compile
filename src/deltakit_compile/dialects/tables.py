# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""xDSL dialect module representing table operations shared by
multiple dialect."""

from collections import Counter
from collections.abc import Callable, Iterable, Mapping, ValuesView
from typing import Any

from typing_extensions import Self, override
from xdsl.dialects.builtin import DictionaryAttr
from xdsl.ir import Attribute, Dialect
from xdsl.irdl.attributes import irdl_attr_definition
from xdsl.irdl.operations import IRDLOperation, prop_def, traits_def
from xdsl.parser import AttrParser, Parser
from xdsl.printer import Printer
from xdsl.utils.exceptions import VerifyException

from deltakit_compile.dialects.common.attributes import (
    PlainParsableAttribute,
    PlainParsableParameterizedAttribute,
)
from deltakit_compile.dialects.common.traits import HasSideEffects


def plain_attr_in_braces_parser(
    attr_type: type[PlainParsableAttribute],
) -> Callable[[AttrParser], Attribute]:
    """Return a parser function to parse a PlainParsableAttribute in braces."""

    def parser(parser: AttrParser) -> Attribute:
        with parser.in_braces():
            return attr_type.parse_inner(parser)

    return parser


def plain_attr_in_braces_printer(
    attr_type: type[PlainParsableAttribute],
) -> Callable[[Printer, Attribute], None]:
    """Return a printer function to plainly print a PlainParsableAttribute in braces."""

    def printer(printer: Printer, attr: Attribute) -> None:
        if not isinstance(attr, attr_type):
            msg = f"Expected inner value of type {attr_type.name}, got {type(attr).name}"
            raise VerifyException(msg)

        with printer.in_braces():
            attr.print_inner(printer)

    return printer


@irdl_attr_definition
class SparseTableAttr(PlainParsableParameterizedAttribute):
    """An attribute for a sparse representation of a table."""

    name = "tables.sparse_table"

    table: DictionaryAttr

    def __init__(
        self,
        table: Mapping[int, Attribute] | DictionaryAttr,
    ):
        if not isinstance(table, DictionaryAttr):
            table = DictionaryAttr({str(k): v for (k, v) in table.items()})

        super().__init__(table)

    def keys(self) -> Iterable[int]:
        """Return an iterable of the table's integer keys."""
        return (int(k) for k in self.table.data)

    def values(self) -> ValuesView[Attribute]:
        """Return an iterable of the table's values."""
        return self.table.data.values()

    def items(self) -> Iterable[tuple[int, Attribute]]:
        """Return an iterable of the table's items."""
        return ((int(k), v) for k, v in self.table.data.items())

    def lookup(self, key: int) -> Attribute | None:
        """Looks up the value for a given key in the sparse table."""
        return self.table.data.get(str(key), None)

    @classmethod
    def _parse_nested_parameters(
        cls,
        parser: AttrParser,
        names: list[str],
        inner_attr_parser: Callable[[AttrParser], Attribute] | None = None,
    ) -> list[Attribute]:
        name, *names = names

        def parse_entry() -> tuple[str, Attribute]:
            """Parse a single entry of the form `<optional-name>? <key> <attribute>`."""
            if name:
                parser.parse_keyword(name)

            key = str(parser.parse_integer(False, False))

            if names:
                return key, cls.parse_nested(parser, names, inner_attr_parser)

            if inner_attr_parser:
                return key, inner_attr_parser(parser)

            return key, parser.parse_attribute()

        entries = parser.parse_comma_separated_list(parser.Delimiter.BRACES, parse_entry)

        entries_map = dict(entries)
        if len(entries_map) != len(entries):
            duplicates = [
                f"'{key}'"
                for key, count in Counter([key for key, _ in entries]).items()
                if count > 1
            ]
            if len(duplicates) > 1:
                parser.raise_error(f"Duplicate keys {', '.join(duplicates)} in table")
            else:
                parser.raise_error(f"Duplicate key {duplicates[0]} in table")

        return [DictionaryAttr(entries_map)]

    @classmethod
    def parse_nested(
        cls,
        parser: AttrParser,
        names: list[str],
        inner_attr_parser: Callable[[AttrParser], Attribute] | None = None,
    ) -> Self:
        """Parse N nested sparse tables with potentially named entries.

        The number of nested tables N is `len(names)`. Use an empty string in names to parse
        unnamed entries. If `inner_attr_parser` is not None, it will be used to parse the innermost
        attribute.

        Parse format is `{<optional-name> <key> <value>, ...}`
        If <value> is an innermost plain attribute, it will be parsed in braces as `{<value>}`.
        """
        return cls.new(cls._parse_nested_parameters(parser, names, inner_attr_parser))

    @override
    @classmethod
    def parse_inner_parameters(cls, parser: AttrParser) -> list[Attribute]:
        """Parse the SparseTableAttr parameters excluding outer angle brackets.
        Parse format is `{<key> <value>, ...}`"""
        return cls._parse_nested_parameters(parser, [""])

    def print_nested(
        self,
        printer: Printer,
        names: list[str],
        inner_attr_printer: Callable[[Printer, Any], None] | None = None,
        print_multiline: bool = False,
    ) -> None:
        """Print N nested sparse tables with potentially named entries.

        The number of nested tables N is `len(names)`. Use an empty string in `names` to print
        unnamed entries. If `inner_attr_printer` is not None, it will be used to print the innermost
        attribute.

        Print format is `{<optional-name> <key> <value>, ...}`
        If <value> is an innermost plain attribute, it will be printed in braces as `{<value>}`.
        """
        name, *names = names

        def print_entry(k: str, v: Attribute) -> None:
            """Print a single entry in the form `<optional-name>? <key> <attribute>`."""
            if name:
                printer.print_string(name)
                printer.print_string(" ")

            printer.print_string(k)
            printer.print_string(" ")

            if names:
                if not isinstance(v, SparseTableAttr):
                    msg = f"Expected nested sparse table attribute, got {type(v).name}"
                    raise VerifyException(msg)

                v.print_nested(printer, names, inner_attr_printer, print_multiline)
            elif inner_attr_printer:
                inner_attr_printer(printer, v)
            else:
                printer.print_attribute(v)

        if not self.table.data:
            printer.print_string("{}")
            return

        with printer.in_braces():
            with printer.indented():
                entries_list = sorted(self.table.data.items(), key=lambda e: int(e[0]))

                if print_multiline:
                    printer.print_string("\n")

                for i, (k, v) in enumerate(entries_list):
                    if i:
                        printer.print_string(",\n" if print_multiline else ", ")

                    print_entry(k, v)

            if print_multiline:
                printer.print_string("\n")

    @override
    def print_inner(self, printer: Printer) -> None:
        """Print the SparseTableAttr parameters excluding outer angle brackets.

        Print format is `{<key> <value>, ...}`"""
        self.print_nested(printer, [""])

    @override
    def verify(self) -> None:
        """Verify that all values in the table have the same inner value type and nesting,
        and that all keys are non-negative integers."""
        if not self.table.data.values():
            return

        def nesting_and_inner_type(attr: Attribute) -> tuple[int, type]:
            nest_count = 0
            while isinstance(attr, SparseTableAttr):
                nest_count += 1
                attr = next(iter(attr.table.data.values()))

            return (nest_count, type(attr))

        values = iter(self.table.data.values())
        first_type = nesting_and_inner_type(next(values))
        if not all(nesting_and_inner_type(v) == first_type for v in values):
            msg = "Expected all values in table to have the same type"
            raise VerifyException(msg)

        for k in self.table.data:
            try:
                if int(k) < 0:
                    msg = f"Expected all keys in table to be non-negative integers, got '{k}'"
                    raise VerifyException(msg)
            except ValueError as err:
                msg = f"Expected all keys in table to be integers, got '{k}'"
                raise VerifyException(msg) from err


class BaseSparseTableOp(IRDLOperation):
    """Base class for operations that contain a single sparse table attribute."""

    table: SparseTableAttr = prop_def(SparseTableAttr)

    traits = traits_def(HasSideEffects())

    def __init__(self, table: SparseTableAttr):
        super().__init__(properties={"table": table})

    @classmethod
    def parse_(
        cls, parser: Parser, names: list[str], inner_type: type[PlainParsableAttribute]
    ) -> Self:
        """Parse a nested sparse table with a plain attribute in braces as the innermost element."""
        table = SparseTableAttr.parse_nested(parser, names, plain_attr_in_braces_parser(inner_type))
        attr_dict = parser.parse_optional_attr_dict()
        return cls.build(properties={"table": table}, attributes=attr_dict)

    def print_(
        self, printer: Printer, names: list[str], inner_type: type[PlainParsableAttribute]
    ) -> None:
        """Print a nested sparse table with a plain attribute in braces as the innermost element."""
        self.table.print_nested(printer, names, plain_attr_in_braces_printer(inner_type), True)
        printer.print_op_attributes(self.attributes)


Tables = Dialect(
    "tables",
    [],
    [
        SparseTableAttr,
    ],
)
