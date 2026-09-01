"""Tests for attributes Module"""

import math
import re
from abc import ABC
from collections.abc import Sequence
from enum import Enum
from io import StringIO
from typing import Any, TypeVar

import numpy as np
import pytest
from xdsl.context import Context
from xdsl.dialects import test
from xdsl.dialects.builtin import ArrayAttr, Float64Type, FloatAttr, FloatData, IntAttr, IntegerType
from xdsl.ir import Attribute, Operation
from xdsl.irdl import AtLeast, param_def
from xdsl.irdl.attributes import irdl_attr_definition
from xdsl.irdl.declarative_assembly_format import (
    OperandsDirective,
    TypeDirective,
    VariadicOperandVariable,
)
from xdsl.irdl.operations import (
    IRDLOperation,
    irdl_op_definition,
    opt_prop_def,
    prop_def,
    var_operand_def,
)
from xdsl.parser import AttrParser, Parser
from xdsl.printer import Printer
from xdsl.utils.bitwise_casts import convert_u64_to_f64
from xdsl.utils.exceptions import ParseError

from deltakit_compile.dialects.common.attributes import (
    AnyEnumAttribute,
    OptPlainArrayOfFloat64Directive,
    OptPlainArrayOfFloatDataDirective,
    OptPlainFloat64Directive,
    OptPlainFloatDataDirective,
    OptPlainIntAttr,
    PlainArrayOfArrayOfIntAttrDirective,
    PlainArrayOfFloat64Directive,
    PlainArrayOfFloatDataDirective,
    PlainArrayOfIntAttrDirective,
    PlainFloat64Directive,
    PlainFloatDataDirective,
    PlainIntAttr,
    PlainParsableAttribute,
    PlainParsableData,
    PlainParsableParameterizedAttribute,
    RepeatedOperandType,
    float64_to_string,
    parse_float64,
    parse_optional_float64,
)

_T = TypeVar("_T", bound=Enum)


@pytest.fixture(
    name="plain_attr_type", params=[PlainParsableData, PlainParsableParameterizedAttribute]
)
def _plain_attr_type(request) -> type[PlainParsableAttribute]:
    """Fixture for an Attribute that subclasses PlainParsableData"""
    if request.param == PlainParsableData:

        @irdl_attr_definition
        class MyIntDataAttr(PlainParsableData[int]):
            """Test Attribute for an int"""

            name = "test.int"

            @classmethod
            def parse_inner_parameter(cls, parser: AttrParser) -> int:
                return parser.parse_integer()

            def print_inner_parameter(self, printer: Printer) -> None:
                printer.print_int(self.data)

        return MyIntDataAttr
    if request.param == PlainParsableParameterizedAttribute:

        @irdl_attr_definition
        class MyIntParamAttr(PlainParsableParameterizedAttribute):
            """Test Attribute for an int"""

            name = "test.int"

            value: IntAttr = param_def(IntAttr.constr(AtLeast(-1000)))

            def __init__(self, val: int) -> None:
                super().__init__(IntAttr(val))

            @classmethod
            def parse_inner_parameters(cls, parser: AttrParser) -> Sequence[Attribute]:
                return [IntAttr(parser.parse_integer())]

            def print_inner(self, printer: Printer) -> None:
                printer.print_int(self.value.data)

        return MyIntParamAttr
    raise ValueError()


@pytest.mark.parametrize("i", list(range(-4, 4)))
def test_parsing_plain_attr(i: int, plain_attr_type: type):
    """Tests automatically generated parsing and printing methods on PlainParsableData."""
    attr = plain_attr_type(i)
    output = StringIO()
    printer = Printer(stream=output)
    attr.print_inner(printer)

    string = output.getvalue()

    parser = Parser(Context(), " ".join([string, str(i)]))

    test_attr_1 = attr.parse_inner(parser)
    test_attr_2 = attr.parse_inner(parser)

    assert attr == test_attr_1
    assert attr == test_attr_2


class TestPlainAttribute:
    @pytest.fixture(name="op_with_plain_attr")
    def _op_with_plain_attr(self, plain_attr_type: type[PlainParsableAttribute]) -> type[Operation]:
        @irdl_op_definition
        class OpWithAttr(IRDLOperation):
            """Op that uses plain_int_attr"""

            name = "test.op_with_attr"

            int_prop = opt_prop_def(plain_attr_type)

            custom_directives = (plain_attr_type.plain_directive(),)
            assembly_format = f"( `:` {plain_attr_type.plain_directive('$int_prop')}^ )? attr-dict"

        return OpWithAttr

    def test_plain_attribute_directive(
        self,
        plain_attr_type: type,
        op_with_plain_attr: type[Operation],
    ):
        """Tests that the plain_directive of any PlainParsableData correctly prints and parses."""

        for i in range(5):
            op = op_with_plain_attr(properties={"int_prop": plain_attr_type(i)})
            output = StringIO()
            printer = Printer(stream=output)
            printer.print_op(op)
            printer.print_string("\n")
            printer.print_generic_format = True
            printer.print_op(op)

            output_string = output.getvalue()
            context = Context()
            context.load_attr_or_type(plain_attr_type)
            context.load_op(op_with_plain_attr)
            parser = Parser(context, output_string)
            op_1 = parser.parse_op()
            op_2 = parser.parse_op()
            assert op.is_structurally_equivalent(op_1)
            assert op_1.is_structurally_equivalent(op_2)


class TestPlainArrayOfAttribute:
    """Tests for _PlainArrayOfAttributeDirective and PlainParsableData.plain_array_of_directive()"""

    @pytest.fixture(name="op_with_plain_attrs")
    def _op_with_plain_attrs(self, plain_attr_type: type[PlainParsableAttribute]):
        @irdl_op_definition
        class OpWithArrayAttr(IRDLOperation):
            """Op that uses an array attr of plain_int_attr"""

            name = "test.op_with_array_attr"

            ints_prop = opt_prop_def(ArrayAttr[plain_attr_type])  # type: ignore[valid-type]
            custom_directives = (plain_attr_type.plain_array_of_directive(),)
            assembly_format = (
                f"({plain_attr_type.plain_array_of_directive('$ints_prop', '<', ')')}^)? attr-dict"
            )

        return OpWithArrayAttr

    @pytest.fixture(name="test_context")
    def _test_context(
        self,
        plain_attr_type: type[PlainParsableAttribute],
        op_with_plain_attrs: type[Operation],
    ):
        context = Context()
        context.load_attr_or_type(plain_attr_type)
        context.load_op(op_with_plain_attrs)
        return context

    def test_roundtrip(
        self,
        plain_attr_type: type,
        op_with_plain_attrs: type[Operation],
        test_context: Context,
    ):
        """Print and parse test for plain array of directive of PlainParsableData."""

        for attr in [None] + [ArrayAttr([plain_attr_type(j) for j in range(i)]) for i in range(5)]:
            op = op_with_plain_attrs.create(
                properties={"ints_prop": attr} if attr is not None else {}
            )
            output = StringIO()
            printer = Printer(stream=output)
            printer.print_op(op)
            printer.print_string("\n")
            printer.print_generic_format = True
            printer.print_op(op)

            output_string = output.getvalue()

            parser = Parser(test_context, output_string)
            op_1 = parser.parse_op()
            op_2 = parser.parse_op()
            assert op.is_structurally_equivalent(op_1)
            assert op_1.is_structurally_equivalent(op_2)

    def test_parse_failure(
        self,
        test_context: Context,
    ):
        """Tests that the plain array of directive produces a useful parse error when ending
        delimiter is not found"""

        parser = Parser(test_context, "test.op_with_array_attr <0")
        with pytest.raises(ParseError, match=re.escape("Expected closing delimiter: ')'")):
            parser.parse_op()


def test_any_enum_attribute_indirect_inheritance():
    """Test that AnyEnumAttribute cannot have indirect inheritance"""

    with pytest.raises(TypeError, match="Only direct inheritance from AnyEnumAttribute is allowed"):

        class MiddleClass(AnyEnumAttribute[_T], ABC):
            """Base Attribute Class"""


def test_any_enum_attribute_parsable_names():
    """Test that AnyEnumAttribute cannot unparsable enum names"""

    class TestEnum(Enum):
        """Unparsable Enum"""

        Σ = 1  # noqa: PLC2401
        τ = 2  # noqa: PLC2401
        A𑑓 = 3  # noqa: PLC2401

    with pytest.raises(
        TypeError,
        match="All enumerated variables of an Enum must be parsable as an identifier",
    ):

        @irdl_attr_definition
        class NotEnumAttr(AnyEnumAttribute[TestEnum]):
            """Attribute for TestEnum"""

            name = "test.test_enum"


@pytest.mark.parametrize(
    ("use_values", "exp_error"),
    [
        (False, r"Expected one of: \[A, B, C\] but got D"),
        (True, r"Expected the value of one of the members of TestEnum: \[a, bb, ccc\] but got D."),
    ],
)
def test_any_enum_attribute_parse_error(use_values: bool, exp_error: str):
    """Test that AnyEnumAttribute fails to parse gracefully"""

    class Toy:
        """Test value for enum"""

        def __init__(self, s: str, c: int):
            self.s = s
            self.c = c

        def __eq__(self, other: object) -> bool:
            if isinstance(other, Toy):
                other = other.s * other.c
            if isinstance(other, str):
                return (self.s * self.c) == other
            return NotImplemented

        def __hash__(self) -> int:
            return hash((self.s, self.c))

        def __str__(self) -> str:
            return self.s * self.c

    class TestEnum(Enum):
        """TestEnum"""

        A = Toy("a", 1)
        B = Toy("b", 2)
        C = Toy("c", 3)

    @irdl_attr_definition
    class NotEnumAttr(AnyEnumAttribute[TestEnum], use_values=use_values):
        """Attribute for TestEnum"""

        name = "test.test_enum"

    context = Context()
    context.load_attr_or_type(NotEnumAttr)
    parser = Parser(context, "<D>")

    with pytest.raises(ParseError, match=exp_error):
        NotEnumAttr.parse_parameter(parser)


@pytest.mark.parametrize(
    ("enum", "value"),
    [
        (
            Enum("TestEnum", {"ENUM1": 1, "ENUM2": None, "ENUM3": "hello", "ENUM4": type}),
            tuple,
        ),
        (Enum("EnumAttr", {}), "value"),
        (Enum("EnumAttr", {}), type(Enum)),
        (Enum("MutableEnumAttr", {"Member": []}), {}),
        (Enum("Test", {"M1": 1, "M2": 2}), 0),
    ],
)
def test_any_enum_attribute_initialise_fail(enum: type[Enum], value: Any):
    """Test that you cannot initialise an AnyEnumAttribute with just any value"""

    @irdl_attr_definition
    class EnumAttr(AnyEnumAttribute[enum]):  # type: ignore[valid-type]
        """Attribute for whatever 'enum' is"""

        name = "test.enum"

    with pytest.raises(
        ValueError,
        match=f"Cannot initialise EnumAttr with non-'{enum.__name__}' value: '{value}'",
    ):
        EnumAttr(value)


@pytest.mark.parametrize(
    ("enum", "use_values"),
    [
        (Enum("TestEnum", {"ENUM1": 1, "ENUM2": None, "ENUM3": "hello", "ENUM4": type}), False),
        (Enum("EnumAttr", {}), False),
        (Enum("MutableEnumAttr", {"Member": []}), False),
        (Enum("TestEnum", {"ENUM1": "e1", "ENUM2": "e2", "ENUM3": "e3", "ENUM4": "e4"}), True),
    ],
)
def test_any_enum_attribute_works(enum: type[Enum], use_values: bool):
    """Test that AnyEnumAttribute is able to generate attributes correctly, and test helper
    methods."""

    @irdl_attr_definition
    class EnumAttr(AnyEnumAttribute[enum], use_values=use_values):  # type: ignore[valid-type]
        """Attribute for whatever 'enum' is"""

        name = "test.enum"

    if use_values:
        test_string = " ".join(f"<{member.value}>" for member in enum)
    else:
        test_string = " ".join(f"<{member.name}>" for member in enum)
    context = Context()
    context.load_attr_or_type(EnumAttr)
    parser = Parser(context, test_string)
    string_value = StringIO()
    printer = Printer(stream=string_value)
    for i, member in enumerate(enum):
        res = EnumAttr.parse_parameter(parser)
        assert res == member

        attr = EnumAttr(member)
        assert attr.data == member
        attr.verify()

        if i:
            printer.print_string(" ")
        attr.print_parameter(printer)

    assert string_value.getvalue() == test_string

    for member in enum:
        arg_result = EnumAttr.from_argument(member)
        assert arg_result == EnumAttr(member)
        arg_result = EnumAttr.from_argument(EnumAttr(member))
        assert arg_result == EnumAttr(member)
    assert EnumAttr.from_argument(None) is None

    assert [EnumAttr(e) for e in enum] == list(EnumAttr)


def test_any_enum_attribute_must_be_subclassed():
    """Tests that trying to directly make an instance of AnyEnumAttribute fails gracefully."""
    enum_type = Enum("TestEnum", {"ENUM1": 1, "ENUM2": None, "ENUM3": "hello", "ENUM4": type})
    val = enum_type.ENUM1
    with pytest.raises(
        TypeError,
        match=re.escape(
            "AnyEnumAttribute cannot be directly initialised. "
            "It must be subclassed to provide the enum type."
        ),
    ):
        AnyEnumAttribute(val)


@pytest.mark.parametrize(
    "enum",
    [
        Enum("TestEnum", {"ENUM1": 1, "ENUM2": None, "ENUM3": "hello", "ENUM4": type}),
        Enum("EnumAttr", {}),
        Enum("MutableEnumAttr", {"Member": []}),
    ],
)
def test_any_enum_attribute_plain_parsing(enum: type[Enum]):
    """Tests that the plain_directive of any AntEnumAttr correctly prints and parses."""

    @irdl_attr_definition
    class EnumAttr(AnyEnumAttribute[enum]):  # type: ignore[valid-type]
        """Attribute for whatever 'enum' is"""

        name = "test.enum"

    @irdl_op_definition
    class OpWithEnum(IRDLOperation):
        """Op that uses EnumAttr"""

        name = "test.op_with_enum"

        enum_prop = prop_def(EnumAttr)

        custom_directives = (EnumAttr.plain_directive(),)
        assembly_format = f"{EnumAttr.plain_directive('$enum_prop')} attr-dict"

    for member in enum:
        op = OpWithEnum(properties={"enum_prop": EnumAttr(member)})
        output = StringIO()
        printer = Printer(stream=output)
        printer.print_op(op)
        printer.print_string("\n")
        printer.print_generic_format = True
        printer.print_op(op)

        output_string = output.getvalue()
        context = Context()
        context.load_attr_or_type(EnumAttr)
        context.load_op(OpWithEnum)
        parser = Parser(context, output_string)
        op_1 = parser.parse_op()
        op_2 = parser.parse_op()
        assert op_1.is_structurally_equivalent(op_2)


@pytest.mark.parametrize(
    "directive",
    [PlainIntAttr, OptPlainIntAttr],
)
@pytest.mark.parametrize("input_str", ["test.test -1", "test.test 0", "test.test 999999999999999"])
def test_plain_int_attr_roundtrip(directive: type[PlainIntAttr | OptPlainIntAttr], input_str: str):
    """Test that custom assembly formats PlaintIntAttr and OptPlaintIntAttr work"""

    @irdl_op_definition
    class TestOp(IRDLOperation):
        """Test op"""

        name = "test.test"

        int_value = prop_def(IntAttr)

        assembly_format = f"attr-dict {directive.use('$int_value')}"

        custom_directives = (directive,)

    context = Context()
    context.load_op(TestOp)
    parser = Parser(context, input_str)
    test_op = parser.parse_op()
    result_str = str(test_op)

    assert input_str == result_str


@pytest.mark.parametrize(
    "input_str",
    [
        "test.test",
        "test.test 0",
        "test.test 999999999999999",
        "test.test 0 x 0",
        "test.test 0 x -1",
        "test.test x 23",
        "test.test x -99999999999",
    ],
)
def test_opt_plain_int_attr_roundtrip(input_str: str):
    """Test that custom assembly directive OptPlaintIntAttr works"""

    @irdl_op_definition
    class TestOp(IRDLOperation):
        """Test op"""

        name = "test.test"

        int_value1 = opt_prop_def(IntAttr)
        int_value2 = opt_prop_def(IntAttr)

        assembly_format = (
            f"attr-dict ({OptPlainIntAttr.use('$int_value1')}^)? "
            "(`x` custom<OptPlainIntAttr>($int_value2)^)?"
        )

        custom_directives = (OptPlainIntAttr,)

    context = Context()
    context.load_op(TestOp)
    parser = Parser(context, input_str)
    test_op = parser.parse_op()
    result_str = str(test_op)

    assert input_str == result_str


@pytest.mark.parametrize(
    "input_str",
    [
        "test.test [-1, 0, -10000, 9999999, 3]",
        "test.test [0, 2, 3, 10, 3]",
        "test.test [999999999999999, 800000000000000000000]",
        "test.test []",
    ],
)
def test_plain_array_of_int_attr_roundtrip(input_str: str):
    """Test that custom assembly format PlainArrayOfIntAttrDirective works."""

    @irdl_op_definition
    class TestOp(IRDLOperation):
        """Test op"""

        name = "test.test"

        int_values = prop_def(ArrayAttr[IntAttr])

        assembly_format = f"attr-dict {PlainArrayOfIntAttrDirective.use('$int_values')}"

        custom_directives = (PlainArrayOfIntAttrDirective,)

    context = Context()
    context.load_op(TestOp)
    parser = Parser(context, input_str)
    test_op = parser.parse_op()
    result_str = str(test_op)

    assert input_str == result_str


@pytest.mark.parametrize(
    "input_str",
    [
        "test.test [[-1], [0], [-10000], [9999999], [3]]",
        "test.test [[0, 2, 3, 10, 3]]",
        "test.test [[0, 2, 3], [10, 3]]",
        "test.test [[999999999999999], [800000000000000000000]]",
        "test.test []",
        "test.test [[]]",
    ],
)
def test_plain_array_of_array_of_int_attr_roundtrip(input_str: str):
    """Test that custom assembly format PlainArrayOfArrayOfIntAttrDirective works."""

    @irdl_op_definition
    class TestOp(IRDLOperation):
        """Test op"""

        name = "test.test"

        int_values = prop_def(ArrayAttr[ArrayAttr[IntAttr]])

        assembly_format = f"attr-dict {PlainArrayOfArrayOfIntAttrDirective.use('$int_values')}"

        custom_directives = (PlainArrayOfArrayOfIntAttrDirective,)

    context = Context()
    context.load_op(TestOp)
    parser = Parser(context, input_str)
    test_op = parser.parse_op()
    result_str = str(test_op)

    assert input_str == result_str


@pytest.mark.parametrize(
    ("test_assembly_format", "input_str", "output_str"),
    [
        (
            "attr-dict `[` ($input`:`custom<RepeatedOperandType>(type($input), ref($input))^)? `]`",
            "test.test[%0, %1 : i32]",
            None,
        ),
        (
            "attr-dict `[` ($input`:`custom<RepeatedOperandType>(type($input), ref($input))^)? `]`",
            "test.test[]",
            None,
        ),
        (
            "attr-dict $input `[` (custom<RepeatedOperandType>(type($input), ref($input))^ )? `]`",
            "test.test %0, %1[i64]",
            None,
        ),
        (
            "attr-dict $input `[` (custom<RepeatedOperandType>(type($input), ref($input))^)? `]`",
            "test.test[]",
            None,
        ),
        (
            "attr-dict $input `[` (custom<RepeatedOperandType>(type($input), ref($input))^)? `]`",
            "test.test[i12]",
            "test.test[]",
        ),
    ],
)
def test_repeated_operand_type_roundtrip(
    test_assembly_format: str, input_str: str, output_str: str | None
):
    """Test that custom assembly format RepeatedOperandType work"""

    @irdl_op_definition
    class TestOp(IRDLOperation):
        """Test op"""

        name = "test.test"

        input = var_operand_def(IntegerType)

        assembly_format = test_assembly_format

        custom_directives = (RepeatedOperandType,)

    context = Context()
    context.load_op(TestOp)
    parser = Parser(context, input_str)
    test_op = parser.parse_op()
    result_str = str(test_op)

    if output_str is None:
        output_str = input_str
    assert output_str == result_str


def test_repeated_operand_type():
    """Test that RepeatedOperandType correctly identifies itself as anchorable and optional, and
    correctly identifies when it is present."""
    type_directive = TypeDirective(OperandsDirective())
    variable = VariadicOperandVariable("test", 0)
    repeated_operand_type = RepeatedOperandType(type_directive, variable)

    assert repeated_operand_type.is_anchorable()
    assert repeated_operand_type.is_optional_like()

    test_op_present = test.TestOp(operands=[test.TestOp(result_types=[test.TestType("T")]).res[0]])
    assert repeated_operand_type.is_present(test_op_present)

    test_op_not_present = test.TestOp()
    assert not repeated_operand_type.is_present(test_op_not_present)


@pytest.mark.parametrize(
    ("value", "exp_str"),
    [
        (math.inf, "inf"),
        (-math.inf, "-inf"),
        (math.nan, "nan"),
        (0, "0.0"),
        (-0, "0.0"),
        (-0.0, "-0.0"),
        (1, "1.0"),
        (0.1, "0.1"),
        (0.002, "0.002"),
        (0.0003, "0.0003"),
        (0.00004, "0.00004"),
        (0.000005, "5.0e-06"),
        (0.0000006, "6.0e-07"),
        (0.00000007, "7.0e-08"),
        (-0.1, "-0.1"),
        (math.pi, "3.141592653589793"),
        (1e-60, "1.0e-60"),
        (1e60, "1.0e+60"),
        (FloatData(0.2), "0.2"),
        (FloatAttr(FloatData(0.3), Float64Type()), "0.3"),
    ],
)
def test_float64_to_string_round_trip(
    value: float | FloatData | FloatAttr[Float64Type], exp_str: str
):
    """Test a sample of numbers to check that ``float64_to_string`` produces the correct string
    and that it can be parsed by ``parse_float64`` to the same value."""
    if isinstance(value, FloatAttr):
        f_value = value.value.data
    elif isinstance(value, FloatData):
        f_value = value.data
    else:
        f_value = float(value)

    result = float64_to_string(value)
    assert result == exp_str

    parser = Parser(Context(), result)
    number = parse_float64(parser)
    assert isinstance(number, float)
    if math.isnan(f_value):
        assert math.isnan(number)
    else:
        assert number == f_value


def test_float64_to_string_round_trip_random_sample():
    """Test a large sample of floating point numbers to check that ``float64_to_string`` produces a
    correct looking string that can be parsed by ``parse_float64``."""
    random = np.random.Generator(np.random.PCG64(10))
    ints = random.integers(0, 2**64 - 1, size=10000, dtype=np.uint64)
    for i in ints:
        f_value = convert_u64_to_f64(i)
        result = float64_to_string(f_value)

        if math.isinf(f_value):
            assert re.match("-?inf", result)
        elif math.isnan(f_value):
            assert result == "nan"
        else:
            assert re.match(r"^-?[0-9]+\.[0-9]+$", result) or re.match(
                r"^-?[1-9]\.[0-9]+e[+-][0-9][0-9]+$", result
            )

        parser = Parser(Context(), result)
        number = parse_float64(parser)
        assert isinstance(number, float)

        if math.isnan(f_value):
            assert math.isnan(number)
        else:
            assert number == f_value

        # Also check that ints parse with parse_float64 properly
        parser = Parser(Context(), str(i))
        integer = parse_float64(parser)
        assert i == integer


def test_parse_optional_float64_error():
    """Tests that parse_optional_float64 raises a correct error for half-parsed floats."""
    parser = Parser(Context(), "-hello")
    with pytest.raises(
        ParseError, match=re.escape("Expected a floating point number following a '-'.")
    ):
        parse_optional_float64(parser)

    parser = Parser(Context(), "-hello")
    with pytest.raises(
        ParseError, match=re.escape("Expected a floating point number following a '-'.")
    ):
        parse_float64(parser)


@pytest.mark.parametrize(
    ("directive", "prop_type"),
    [
        (PlainFloat64Directive, FloatAttr[Float64Type]),
        (OptPlainFloat64Directive, FloatAttr[Float64Type]),
        (PlainFloatDataDirective, FloatData),
        (OptPlainFloatDataDirective, FloatData),
    ],
)
@pytest.mark.parametrize(
    "input_str", ["test.test -1.0", "test.test 0.0", "test.test 999999999999999.0"]
)
def test_plain_float64_directive_roundtrip(
    directive: type[
        PlainFloat64Directive
        | OptPlainFloat64Directive
        | PlainFloatDataDirective
        | OptPlainFloatDataDirective
    ],
    prop_type: type[Attribute],
    input_str: str,
):
    """Test that custom assembly formats PlainFloat64Directive and OptPlainFloat64Directive work."""

    @irdl_op_definition
    class TestOp(IRDLOperation):
        """Test op"""

        name = "test.test"

        float_value = prop_def(prop_type)

        assembly_format = f"attr-dict {directive.use('$float_value')}"

        custom_directives = (directive,)

    context = Context()
    context.load_op(TestOp)
    parser = Parser(context, input_str)
    test_op = parser.parse_op()
    result_str = str(test_op)

    assert input_str == result_str


@pytest.mark.parametrize(
    ("directive", "prop_type"),
    [
        (OptPlainFloat64Directive, FloatAttr[Float64Type]),
        (OptPlainFloatDataDirective, FloatData),
    ],
)
@pytest.mark.parametrize(
    "input_str",
    [
        "test.test",
        "test.test 0.0",
        "test.test 999999999999999.0",
        "test.test 0.0 x 0.0",
        "test.test 0.0 x -1.0",
        "test.test x 23.0",
        "test.test x -99999999999.0",
    ],
)
def test_opt_plain_float64_directive_roundtrip(
    directive: type[OptPlainFloat64Directive | OptPlainFloatDataDirective],
    prop_type: type[Attribute],
    input_str: str,
):
    """Test that custom assembly formats with OptPlainFloat64Directives work."""

    @irdl_op_definition
    class TestOp(IRDLOperation):
        """Test op"""

        name = "test.test"

        float_value1 = opt_prop_def(prop_type)
        float_value2 = opt_prop_def(prop_type)

        assembly_format = (
            f"attr-dict ({directive.use('$float_value1')}^)? "
            f"(`x` {directive.use('$float_value2')}^)?"
        )

        custom_directives = (directive,)

    context = Context()
    context.load_op(TestOp)
    parser = Parser(context, input_str)
    test_op = parser.parse_op()
    result_str = str(test_op)

    assert input_str == result_str


@pytest.mark.parametrize(
    ("directive", "prop_type"),
    [
        (PlainArrayOfFloat64Directive, ArrayAttr[FloatAttr[Float64Type]]),
        (OptPlainArrayOfFloat64Directive, ArrayAttr[FloatAttr[Float64Type]]),
        (PlainArrayOfFloatDataDirective, ArrayAttr[FloatData]),
        (OptPlainArrayOfFloatDataDirective, ArrayAttr[FloatData]),
    ],
)
@pytest.mark.parametrize(
    "input_str",
    [
        "test.test [-1.0, 0.0, -0.0, inf, 0.001]",
        "test.test [0.0, 2.0, 3.0, 10.0, 0.03]",
        "test.test [999999999999999.0, 8.0e-10]",
        "test.test []",
    ],
)
def test_plain_array_of_float64_attr_roundtrip(
    directive: type[
        PlainArrayOfFloat64Directive
        | OptPlainArrayOfFloat64Directive
        | PlainArrayOfFloatDataDirective
        | OptPlainArrayOfFloatDataDirective
    ],
    prop_type: type[Attribute],
    input_str: str,
):
    """Test that custom assembly formats PlainArrayOfFloat64Directive and
    OptPlainArrayOfFloat64Directive work"""

    @irdl_op_definition
    class TestOp(IRDLOperation):
        """Test op"""

        name = "test.test"

        float_values = prop_def(prop_type)

        assembly_format = f"attr-dict {directive.use('$float_values')}"

        custom_directives = (directive,)

    context = Context()
    context.load_op(TestOp)
    parser = Parser(context, input_str)
    test_op = parser.parse_op()
    result_str = str(test_op)

    assert input_str == result_str


@pytest.mark.parametrize(
    ("directive", "prop_type"),
    [
        (OptPlainArrayOfFloat64Directive, ArrayAttr[FloatAttr[Float64Type]]),
        (OptPlainArrayOfFloatDataDirective, ArrayAttr[FloatData]),
    ],
)
@pytest.mark.parametrize(
    "input_str",
    [
        "test.test",
        "test.test [0.0]",
        "test.test [999999999999999.0, 2.0]",
        "test.test [] x []",
        "test.test [1.0] x [-1.0]",
        "test.test x [23.0]",
        "test.test x [-99999999999.0]",
    ],
)
def test_opt_plain_array_of_float64_attr_roundtrip(
    directive: type[OptPlainArrayOfFloat64Directive | OptPlainArrayOfFloatDataDirective],
    prop_type: type[Attribute],
    input_str: str,
):
    """Test that custom assembly format OptPlainArrayOfFloat64Directive work."""

    @irdl_op_definition
    class TestOp(IRDLOperation):
        """Test op"""

        name = "test.test"

        float_values1 = opt_prop_def(prop_type)
        float_values2 = opt_prop_def(prop_type)

        assembly_format = (
            f"attr-dict ({directive.use('$float_values1')}^)? "
            f"(`x` {directive.use('$float_values2')}^)?"
        )

        custom_directives = (directive,)

    context = Context()
    context.load_op(TestOp)
    parser = Parser(context, input_str)
    test_op = parser.parse_op()
    result_str = str(test_op)

    assert input_str == result_str
