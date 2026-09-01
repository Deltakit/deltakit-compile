# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Tests for table attributes and ops shared across dialects."""

import re
import textwrap
from collections.abc import Mapping, Sequence
from io import StringIO

import pytest
from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import (
    DictionaryAttr,
    IntAttr,
    IntegerAttr,
    IntegerType,
    StringAttr,
)
from xdsl.ir import Attribute, Dialect
from xdsl.irdl.attributes import irdl_attr_definition
from xdsl.irdl.operations import irdl_op_definition
from xdsl.parser import AttrParser, Parser
from xdsl.printer import Printer
from xdsl.utils.exceptions import ParseError, VerifyException

from deltakit_compile.dialects.common.attributes import (
    PlainParsableAttribute,
    PlainParsableParameterizedAttribute,
)
from deltakit_compile.dialects.tables import (
    BaseSparseTableOp,
    SparseTableAttr,
    plain_attr_in_braces_parser,
    plain_attr_in_braces_printer,
)


@irdl_attr_definition
class TwoIntAttr(PlainParsableParameterizedAttribute):
    """Minimal test-only attribute with two named integer parameters."""

    name = "tables_test.two_int"

    qubit_id: IntAttr
    meas_rnd: IntAttr

    def __init__(self, *, qubit_id: int, meas_rnd: int) -> None:
        super().__init__(IntAttr(qubit_id), IntAttr(meas_rnd))

    @override
    @classmethod
    def parse_inner_parameters(cls, parser: AttrParser) -> Sequence[IntAttr]:
        parser.parse_keyword("qubit_id")
        parser.parse_punctuation("=")
        qubit_id = IntAttr(parser.parse_integer(allow_boolean=False))
        parser.parse_punctuation(",")
        parser.parse_keyword("meas_rnd")
        parser.parse_punctuation("=")
        meas_rnd = IntAttr(parser.parse_integer(allow_boolean=False))
        return [qubit_id, meas_rnd]

    @override
    def print_inner(self, printer: Printer) -> None:
        printer.print_string(f"qubit_id = {self.qubit_id.data}, meas_rnd = {self.meas_rnd.data}")


@irdl_op_definition
class ConcreteTableOp(BaseSparseTableOp):
    """Concrete test operation for BaseSparseTableOp."""

    name = "tables_test.op"


TablesTestDialect = Dialect("tables_test", [ConcreteTableOp], [])


def test_plain_attr_in_braces_parser():
    """Test the braced inner attribute parser generator."""
    parser = Parser(Context(), "{qubit_id = 4, meas_rnd = 1}")
    attr_parser_fn = plain_attr_in_braces_parser(TwoIntAttr)
    attr = attr_parser_fn(parser)
    assert isinstance(attr, TwoIntAttr)
    assert attr.qubit_id.data == 4
    assert attr.meas_rnd.data == 1


def test_plain_attr_in_braces_printer():
    """Test the braced inner attribute printer generator."""
    attr = TwoIntAttr(qubit_id=4, meas_rnd=1)
    stream = StringIO()
    printer = Printer(stream=stream)
    attr_printer_fn = plain_attr_in_braces_printer(TwoIntAttr)
    attr_printer_fn(printer, attr)
    output = stream.getvalue()
    assert output == "{qubit_id = 4, meas_rnd = 1}"


@pytest.mark.parametrize(
    ("table", "expected_items"),
    [
        ({}, {}),
        (DictionaryAttr({}), {}),
        ({0: IntAttr(1), 3: IntAttr(7)}, {"0": IntAttr(1), "3": IntAttr(7)}),
        ({1: StringAttr("a"), 55: StringAttr("b")}, {"1": StringAttr("a"), "55": StringAttr("b")}),
        (DictionaryAttr({"5": IntAttr(10)}), {"5": IntAttr(10)}),
    ],
)
def test_sparse_table_construction(
    table: Mapping[int, Attribute] | DictionaryAttr, expected_items: Mapping[str, Attribute]
):
    """Test the construction of SparseTableAttr with valid inputs."""
    attr = SparseTableAttr(table)
    assert attr.table.data == expected_items


@pytest.mark.parametrize(
    ("table", "exp_error_msg"),
    [
        ({0: IntAttr(1), 3: StringAttr("a")}, "Expected all values in table to have the same type"),
        (
            DictionaryAttr({"5": IntAttr(10), "6": StringAttr("b")}),
            "Expected all values in table to have the same type",
        ),
        (
            {0: IntAttr(1), 1: SparseTableAttr({0: IntAttr(0), 1: IntAttr(1)})},
            "Expected all values in table to have the same type",
        ),
        (
            {
                0: SparseTableAttr({0: IntAttr(0), 1: IntAttr(1)}),
                1: SparseTableAttr({0: StringAttr("a"), 1: StringAttr("b")}),
            },
            "Expected all values in table to have the same type",
        ),
        (
            {
                0: SparseTableAttr({0: IntAttr(0), 1: IntAttr(1)}),
                1: SparseTableAttr({0: SparseTableAttr({0: IntAttr(0), 1: IntAttr(1)})}),
            },
            "Expected all values in table to have the same type",
        ),
        (
            {-1: IntAttr(1), 3: IntAttr(2)},
            "Expected all keys in table to be non-negative integers, got '-1'",
        ),
        (
            DictionaryAttr({"-5": IntAttr(10), "6": IntAttr(11)}),
            "Expected all keys in table to be non-negative integers, got '-5'",
        ),
        (
            DictionaryAttr({"5": IntAttr(10), "a": IntAttr(11)}),
            "Expected all keys in table to be integers, got 'a'",
        ),
    ],
)
def test_sparse_table_construction_error(
    table: Mapping[int, Attribute] | DictionaryAttr, exp_error_msg: str
):
    """Test verification errors from construction of SparseTableAttr with invalid inputs."""
    with pytest.raises(VerifyException, match=exp_error_msg):
        SparseTableAttr(table).verify()


@pytest.mark.parametrize(
    ("table", "items"),
    [
        (SparseTableAttr({}), {}),
        (
            SparseTableAttr({0: IntAttr(1), 1: IntAttr(7), 2: IntAttr(7)}),
            {0: IntAttr(1), 1: IntAttr(7), 2: IntAttr(7)},
        ),
        (
            SparseTableAttr({1: StringAttr("a"), 55: StringAttr("b")}),
            {1: StringAttr("a"), 55: StringAttr("b")},
        ),
    ],
)
def test_sparse_table_accessors(table: SparseTableAttr, items: dict[int, Attribute]):
    """Test accessing items of a SparseTableAttr."""
    assert dict(table.items()) == items
    assert set(table.keys()) == set(items.keys())
    assert set(table.values()) == set(items.values())
    for key, value in items.items():
        assert table.lookup(key) == value


def test_sparse_table_non_existing_lookup():
    """Test looking up non-existing key in a SparseTableAttr."""
    attr = SparseTableAttr({0: IntAttr(1), 1: IntAttr(7), 3: IntAttr(7)})
    assert attr.lookup(2) is None


@pytest.mark.parametrize(
    ("input_str", "names", "inner_type", "expected"),
    [
        ("{}", [""], None, SparseTableAttr({})),
        ("{\n}", [""], None, SparseTableAttr({})),
        ("{}", ["prefix"], None, SparseTableAttr({})),
        ("{\n}", ["prefix"], TwoIntAttr, SparseTableAttr({})),
        (
            "{4 1}",
            [""],
            None,
            SparseTableAttr({4: IntegerAttr(IntAttr(data=1), IntegerType(64))}),
        ),
        (
            '{0 "Craig", 4 "Steven"}',
            [""],
            None,
            SparseTableAttr({0: StringAttr("Craig"), 4: StringAttr("Steven")}),
        ),
        (
            '{ prefix 0 "a", prefix 1 "b" }',
            ["prefix"],
            None,
            SparseTableAttr({0: StringAttr("a"), 1: StringAttr("b")}),
        ),
        (
            "{ prefix 0 {qubit_id = 4, meas_rnd = 1}, prefix 2 {qubit_id = 0, meas_rnd = 0} }",
            ["prefix"],
            TwoIntAttr,
            SparseTableAttr(
                {
                    0: TwoIntAttr(qubit_id=4, meas_rnd=1),
                    2: TwoIntAttr(qubit_id=0, meas_rnd=0),
                }
            ),
        ),
        (
            """{
              outer 0 {
                inner 0 {qubit_id = 4, meas_rnd = 1},
                inner 1 {qubit_id = 0, meas_rnd = 0}
              },
              outer 2 {
                inner 0 {qubit_id = 3, meas_rnd = 5}
              }
            }""",
            ["outer", "inner"],
            TwoIntAttr,
            SparseTableAttr(
                {
                    0: SparseTableAttr(
                        {
                            0: TwoIntAttr(qubit_id=4, meas_rnd=1),
                            1: TwoIntAttr(qubit_id=0, meas_rnd=0),
                        }
                    ),
                    2: SparseTableAttr({0: TwoIntAttr(qubit_id=3, meas_rnd=5)}),
                }
            ),
        ),
    ],
)
def test_sparse_table_parse_nested(
    input_str: str,
    names: list[str],
    inner_type: type[PlainParsableAttribute] | None,
    expected: SparseTableAttr,
):
    """Test nested parsing of SparseTableAttr."""
    parser = Parser(Context(), input_str)
    assert (
        SparseTableAttr.parse_nested(
            parser,
            names,
            plain_attr_in_braces_parser(inner_type) if inner_type is not None else None,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("input_str", "names", "inner_type", "exp_error_msg"),
    [
        (
            """{
              prefix 0 {qubit_id = 4, meas_rnd = 1},
              prefix 2 #builtin.int<5>
            }""",
            ["prefix"],
            TwoIntAttr,
            "'{' expected",
        ),
        (
            """{
              0 {qubit_id = 0, meas_rnd = 0},
              1 {qubit_id = 1, meas_rnd = 1},
            }""",
            ["prefix"],
            TwoIntAttr,
            "Expected 'prefix'",
        ),
        (
            """{
              outer 0 {
                inner 0 {qubit_id = 4, meas_rnd = 1},
                inner 1 {qubit_id = 0, meas_rnd = 0}
              },
              outer 2 {qubit_id = 3, meas_rnd = 5}
            }""",
            ["outer", "inner"],
            TwoIntAttr,
            "Expected 'inner'",
        ),
    ],
)
def test_sparse_table_parse_nested_error(
    input_str: str,
    names: list[str],
    inner_type: type[PlainParsableAttribute] | None,
    exp_error_msg: str,
):
    """Test errors while doing nested parsing of SparseTableAttr."""
    parser = Parser(Context(), input_str)
    with pytest.raises(ParseError, match=exp_error_msg):
        SparseTableAttr.parse_nested(
            parser,
            names,
            plain_attr_in_braces_parser(inner_type) if inner_type is not None else None,
        )


def test_sparse_table_parse_duplicate_key_error():
    """Test parsing error for a SparseTableAttr string with duplicate keys."""
    parser = Parser(Context(), "{0 1, 0 2}")
    with pytest.raises(ParseError, match="Duplicate key '0' in table"):
        SparseTableAttr.parse_inner_parameters(parser)


def test_sparse_table_parse_duplicate_keys_error():
    """Test parsing error for a SparseTableAttr string with multiple duplicate keys."""
    parser = Parser(Context(), "{0 1, 0 2, 1 3, 1 4}")
    with pytest.raises(ParseError, match="Duplicate keys '0', '1' in table"):
        SparseTableAttr.parse_inner_parameters(parser)


@pytest.mark.parametrize(
    ("input_attr", "names", "inner_type", "expected"),
    [
        (
            SparseTableAttr({0: IntAttr(1), 3: IntAttr(7)}),
            [""],
            None,
            "{0 #builtin.int<1>, 3 #builtin.int<7>}",
        ),
        (
            SparseTableAttr({0: StringAttr("aa"), 3: StringAttr("b")}),
            [""],
            None,
            '{0 "aa", 3 "b"}',
        ),
        (
            SparseTableAttr({0: StringAttr("aa"), 3: StringAttr("b")}),
            ["prefix"],
            None,
            '{ prefix 0 "aa", prefix 3 "b"}',
        ),
        (
            SparseTableAttr(
                {
                    0: TwoIntAttr(qubit_id=4, meas_rnd=1),
                    3: TwoIntAttr(qubit_id=0, meas_rnd=0),
                }
            ),
            ["prefix"],
            TwoIntAttr,
            """{
              prefix 0 {qubit_id = 4, meas_rnd = 1},
              prefix 3 {qubit_id = 0, meas_rnd = 0}
            }""",
        ),
        (
            SparseTableAttr(
                {
                    0: SparseTableAttr(
                        {
                            1: TwoIntAttr(qubit_id=4, meas_rnd=1),
                            2: TwoIntAttr(qubit_id=0, meas_rnd=0),
                        }
                    ),
                    3: SparseTableAttr({2: TwoIntAttr(qubit_id=0, meas_rnd=0)}),
                }
            ),
            ["outer", "inner"],
            TwoIntAttr,
            """{
              outer 0 {
                inner 1 {qubit_id = 4, meas_rnd = 1},
                inner 2 {qubit_id = 0, meas_rnd = 0}
              },
              outer 3 {
                inner 2 {qubit_id = 0, meas_rnd = 0}
              }
            }""",
        ),
    ],
)
def test_sparse_table_print_nested(
    input_attr: SparseTableAttr,
    names: list[str],
    inner_type: type[PlainParsableAttribute] | None,
    expected: str,
):
    """Test nested printing of SparseTableAttr."""
    stream = StringIO()
    printer = Printer(stream=stream)
    input_attr.print_nested(
        printer,
        names,
        plain_attr_in_braces_printer(inner_type) if inner_type is not None else None,
    )
    produced = re.sub(r"\s+", "", stream.getvalue())
    expected = re.sub(r"\s+", "", expected)
    assert produced == expected


@pytest.mark.parametrize(
    ("input_attr", "names", "inner_type", "exp_error_msg"),
    [
        (
            SparseTableAttr({0: IntAttr(1), 3: IntAttr(7)}),
            ["outer", "inner"],
            None,
            "Expected nested sparse table attribute, got builtin.int",
        ),
        (
            SparseTableAttr(
                {
                    0: SparseTableAttr({0: TwoIntAttr(qubit_id=0, meas_rnd=0)}),
                    1: SparseTableAttr({1: TwoIntAttr(qubit_id=1, meas_rnd=1)}),
                }
            ),
            ["outer"],
            TwoIntAttr,
            "Expected inner value of type tables_test.two_int, got tables.sparse_table",
        ),
    ],
)
def test_sparse_table_print_nested_error(
    input_attr: SparseTableAttr,
    names: list[str],
    inner_type: type[PlainParsableAttribute] | None,
    exp_error_msg: str,
):
    """Test errors while doing nested printing of SparseTableAttr."""
    stream = StringIO()
    printer = Printer(stream=stream)
    with pytest.raises(VerifyException, match=exp_error_msg):
        input_attr.print_nested(
            printer,
            names,
            plain_attr_in_braces_printer(inner_type) if inner_type is not None else None,
        )


@pytest.mark.parametrize(
    ("input_ir"),
    [
        "{}",
        '{0 "Craig"}',
        '{0 "Craig", 4 "Steven"}',
    ],
)
def test_sparse_table_attr_roundtrip(input_ir: str):
    """Test roundtrip parsing and printing of SparseTableAttr."""
    parser = Parser(Context(), input_ir)
    attr = SparseTableAttr.parse_inner(parser)
    stream = StringIO()
    attr.print_inner(Printer(stream=stream))
    assert re.sub(r"\s+", "", stream.getvalue()) == re.sub(r"\s+", "", input_ir)


def test_sparse_table_print_multiline():
    """Test that print_nested with print_multiline=True emits newlines around entries."""
    attr = SparseTableAttr({0: StringAttr("a"), 1: StringAttr("b")})
    stream = StringIO()
    attr.print_nested(Printer(stream=stream), [""], print_multiline=True)
    output = stream.getvalue()
    assert "\n" in output
    stream2 = StringIO()
    attr.print_nested(Printer(stream=stream2), [""])
    assert re.sub(r"\s+", "", output) == re.sub(r"\s+", "", stream2.getvalue())


def test_sparse_table_print_whitespace():
    """Test that print_nested correctly formats whitespace."""
    attr = SparseTableAttr({0: StringAttr("a"), 1: StringAttr("b")})
    stream = StringIO()
    attr.print_nested(Printer(stream=stream), [""], print_multiline=True)
    assert stream.getvalue() == textwrap.dedent("""\
        {
          0 "a",
          1 "b"
        }""")
    stream2 = StringIO()
    attr.print_nested(Printer(stream=stream2), [""])
    assert stream2.getvalue() == '{0 "a", 1 "b"}'


def test_sparse_table_print_empty():
    """Test that print_nested correctly formats empty tables."""
    attr = SparseTableAttr({})
    stream = StringIO()
    attr.print_nested(Printer(stream=stream), [""], print_multiline=True)
    assert stream.getvalue() == "{}"
    stream2 = StringIO()
    attr.print_nested(Printer(stream=stream2), [""])
    assert stream2.getvalue() == "{}"


def test_base_sparse_table_op_init():
    """Test BaseSparseTableOp.__init__ via concrete ConcreteTableOp."""
    table = SparseTableAttr({0: StringAttr("a"), 1: StringAttr("b")})
    op = ConcreteTableOp(table)
    assert op.table == table


def test_base_sparse_table_op_parse():
    """Test BaseSparseTableOp.parse_ parsing a nested table with an inner attribute."""
    ctx = Context()
    ctx.load_dialect(TablesTestDialect)
    input_ir = "{ 0 {qubit_id = 4, meas_rnd = 1}, 2 {qubit_id = 0, meas_rnd = 0} }"
    parser = Parser(ctx, input_ir)
    op = ConcreteTableOp.parse_(parser, [""], TwoIntAttr)
    assert len(op.table.table.data) == 2
    assert "0" in op.table.table.data
    assert "2" in op.table.table.data


def test_base_sparse_table_op_print():
    """Test BaseSparseTableOp.print_ printing a table with an inner attribute."""
    table = SparseTableAttr(
        {
            0: TwoIntAttr(qubit_id=4, meas_rnd=1),
            2: TwoIntAttr(qubit_id=0, meas_rnd=0),
        }
    )
    op = ConcreteTableOp(table)
    stream = StringIO()
    op.print_(Printer(stream=stream), [""], TwoIntAttr)
    output = stream.getvalue()
    assert "\n" in output
    assert re.search(r"0\s+{qubit_id\s*=\s*4,\s*meas_rnd\s*=\s*1}", re.sub(r"\s+", " ", output))
    assert re.search(r"2\s+{qubit_id\s*=\s*0,\s*meas_rnd\s*=\s*0}", re.sub(r"\s+", " ", output))


def test_base_sparse_table_op_print_whitespace():
    """Test BaseSparseTableOp.print_ printing of spaces and newlines."""
    table = SparseTableAttr(
        {
            0: TwoIntAttr(qubit_id=4, meas_rnd=1),
            2: TwoIntAttr(qubit_id=0, meas_rnd=0),
        }
    )
    op = ConcreteTableOp(table)
    stream = StringIO()
    op.print_(Printer(stream=stream), [""], TwoIntAttr)
    assert stream.getvalue() == textwrap.dedent("""\
        {
          0 {qubit_id = 4, meas_rnd = 1},
          2 {qubit_id = 0, meas_rnd = 0}
        }""")
