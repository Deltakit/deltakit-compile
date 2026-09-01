"""Tests for the rewrite patterns in _patterns.py."""

from dataclasses import dataclass, field

import pytest
from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects import test as t
from xdsl.ir import Attribute, BlockArgument, OpResult, Use
from xdsl.pattern_rewriter import PatternRewriteWalker

from deltakit_compile.passes._patterns import (
    ControlFlowUnrealizedCastTypeConversionPattern,
    UnrealizedCastTypeConversionPattern,
)
from tests.unit.conftest import parse_ir


@dataclass(frozen=True)
class SimpleConversionPattern(UnrealizedCastTypeConversionPattern):
    """A simple UnrealizedCastTypeConversionPattern for testing.

    Converts !test.type<"A{x}"> to !test.type<"B{x}"> for any string x.
    !test.type<"same"> is returned as-is to test the case where the same type is returned.
    Returns None for all other types.
    """

    names_not_to_convert: list[str] = field(default_factory=list)
    """A list of name hints to exclude from conversion for testing the should_convert_* methods."""

    @override
    def should_convert_operand(self, use: Use) -> bool:
        return use.operation.operands[use.index].name_hint not in self.names_not_to_convert

    @override
    def should_convert_result(self, result: OpResult) -> bool:
        return result.name_hint not in self.names_not_to_convert

    @override
    def should_convert_block_arg(self, block_arg: BlockArgument) -> bool:
        return block_arg.name_hint not in self.names_not_to_convert

    @override
    def convert_type(self, type_: Attribute) -> Attribute | None:
        if isinstance(type_, t.TestType) and type_.data.startswith("A"):
            return t.TestType("B" + type_.data[1:])
        if type_ == t.TestType("same"):
            return type_
        return None


@pytest.mark.parametrize(
    ("names_not_to_convert", "input_ir", "expected_ir"),
    [
        (
            [],
            """
            builtin.module {
                %a = "test.op"() : () -> !test.type<"A">
            }
            """,
            """
            builtin.module {
                %a = "test.op"() : () -> !test.type<"B">
                %a_1 = builtin.unrealized_conversion_cast %a : !test.type<"B"> to !test.type<"A">
            }
            """,
        ),
        (
            [],
            """
            builtin.module {
                %a = "test.op"() : () -> !test.type<"A">
                %b = "test.op"(%a) : (!test.type<"A">) -> !test.type<"A">
                %c = "test.op"(%b) : (!test.type<"A">) -> !test.type<"B">
                %d = "test.op"(%c) : (!test.type<"B">) -> !test.type<"A">
            }
            """,
            """
            builtin.module {
                %a = "test.op"() : () -> !test.type<"B">
                %a_1 = builtin.unrealized_conversion_cast %a : !test.type<"B"> to !test.type<"A">
                %a_2 = builtin.unrealized_conversion_cast %a_1 : !test.type<"A"> to !test.type<"B">
                %b = "test.op"(%a_2) : (!test.type<"B">) -> !test.type<"B">
                %b_1 = builtin.unrealized_conversion_cast %b : !test.type<"B"> to !test.type<"A">
                %b_2 = builtin.unrealized_conversion_cast %b_1 : !test.type<"A"> to !test.type<"B">
                %c = "test.op"(%b_2) : (!test.type<"B">) -> !test.type<"B">
                %d = "test.op"(%c) : (!test.type<"B">) -> !test.type<"B">
                %d_1 = builtin.unrealized_conversion_cast %d : !test.type<"B"> to !test.type<"A">
            }
            """,
        ),
        (
            [],
            """
            builtin.module {
                %a, %b, %c = "test.op"() : () -> (!test.type<"A0">, !test.type<"C">,
                    !test.type<"A1">)
                %d, %e = "test.op"(%a, %b) : (!test.type<"A0">, !test.type<"C">) ->
                    (!test.type<"D">, !test.type<"A2">)
                "test.op"(%d, %e, %c) : (!test.type<"D">, !test.type<"A2">, !test.type<"A1">) -> ()
            }
            """,
            """
            builtin.module {
                %a, %b, %c = "test.op"() : () -> (!test.type<"B0">, !test.type<"C">,
                    !test.type<"B1">)
                %a_1 = builtin.unrealized_conversion_cast %a : !test.type<"B0"> to !test.type<"A0">
                %c_1 = builtin.unrealized_conversion_cast %c : !test.type<"B1"> to !test.type<"A1">
                %a_2 = builtin.unrealized_conversion_cast %a_1 : !test.type<"A0"> to
                    !test.type<"B0">
                %d, %e = "test.op"(%a_2, %b) : (!test.type<"B0">, !test.type<"C">) ->
                    (!test.type<"D">, !test.type<"B2">)
                %e_1 = builtin.unrealized_conversion_cast %e : !test.type<"B2"> to !test.type<"A2">
                %e_2 = builtin.unrealized_conversion_cast %e_1 : !test.type<"A2"> to
                    !test.type<"B2">
                %c_2 = builtin.unrealized_conversion_cast %c_1 : !test.type<"A1"> to
                    !test.type<"B1">
                "test.op"(%d, %e_2, %c_2) : (!test.type<"D">, !test.type<"B2">, !test.type<"B1">)
                    -> ()
            }
            """,
        ),
        (
            [],
            """
            builtin.module {
                "test.op"() ({
                ^bb0(%a: !test.type<"A">):
                    "test.termop"() : () -> ()
                }) : () -> ()
            }
            """,
            """
            builtin.module {
                "test.op"() ({
                ^bb0(%a: !test.type<"B">):
                    %a_1 = builtin.unrealized_conversion_cast %a : !test.type<"B"> to
                        !test.type<"A">
                    "test.termop"() : () -> ()
                }) : () -> ()
            }
            """,
        ),
        (
            [],
            """
            builtin.module {
                "test.op"() ({
                ^bb0(%a: !test.type<"C">, %b: !test.type<"A1">, %c: !test.type<"A2">,
                        %d: !test.type<"D">):
                    "test.termop"(%d, %c, %b, %a) : (!test.type<"D">, !test.type<"A2">,
                        !test.type<"A1">, !test.type<"C">) -> ()
                }) : () -> ()
            }
            """,
            """
            builtin.module {
                "test.op"() ({
                ^bb0(%a: !test.type<"C">, %b: !test.type<"B1">, %c: !test.type<"B2">,
                        %d: !test.type<"D">):
                    %b_1 = builtin.unrealized_conversion_cast %b : !test.type<"B1"> to
                        !test.type<"A1">
                    %c_1 = builtin.unrealized_conversion_cast %c : !test.type<"B2"> to
                        !test.type<"A2">
                    %c_2 = builtin.unrealized_conversion_cast %c_1 : !test.type<"A2"> to
                        !test.type<"B2">
                    %b_2 = builtin.unrealized_conversion_cast %b_1 : !test.type<"A1"> to
                        !test.type<"B1">
                    "test.termop"(%d, %c_2, %b_2, %a) : (!test.type<"D">, !test.type<"B2">,
                        !test.type<"B1">, !test.type<"C">) -> ()
                }) : () -> ()
            }
            """,
        ),
        (
            # Leaves unrelated types alone
            [],
            """
            builtin.module {
                %a = "test.op"() : () -> !test.type<"C">
                %b = "test.op"(%a) : (!test.type<"C">) -> !test.type<"D">
            }
            """,
            """
            builtin.module {
                %a = "test.op"() : () -> !test.type<"C">
                %b = "test.op"(%a) : (!test.type<"C">) -> !test.type<"D">
            }
            """,
        ),
        (
            # Returning the same type is treated the same as returning None
            [],
            """
            builtin.module {
                %a = "test.op"() : () -> !test.type<"same">
                %b = "test.op"(%a) : (!test.type<"same">) -> !test.type<"same">
            }
            """,
            """
            builtin.module {
                %a = "test.op"() : () -> !test.type<"same">
                %b = "test.op"(%a) : (!test.type<"same">) -> !test.type<"same">
            }
            """,
        ),
        (
            # The various should_convert_* methods are respected
            ["x", "y", "z", "w"],
            """
            builtin.module {
                %x = "test.op"() : () -> !test.type<"A0">
                %a = "test.op"(%x) : (!test.type<"A0">) -> !test.type<"A1">
                %b = "test.op"(%a, %x) : (!test.type<"A1">, !test.type<"A0">) -> !test.type<"A2">
                %y = "test.op"(%b) ({
                ^bb0(%z: !test.type<"A4">, %c: !test.type<"A5">, %w: !test.type<"A6">):
                    "test.termop"(%z, %c, %w) : (!test.type<"A4">, !test.type<"A5">,
                        !test.type<"A6">) -> ()
                }) : (!test.type<"A2">) -> !test.type<"A3">
            }
            """,
            """
            builtin.module {
                %x = "test.op"() : () -> !test.type<"A0">
                %a = "test.op"(%x) : (!test.type<"A0">) -> !test.type<"B1">
                %a_1 = builtin.unrealized_conversion_cast %a : !test.type<"B1"> to !test.type<"A1">
                %a_2 = builtin.unrealized_conversion_cast %a_1 : !test.type<"A1"> to
                    !test.type<"B1">
                %b = "test.op"(%a_2, %x) : (!test.type<"B1">, !test.type<"A0">) -> !test.type<"B2">
                %b_1 = builtin.unrealized_conversion_cast %b : !test.type<"B2"> to !test.type<"A2">
                %b_2 = builtin.unrealized_conversion_cast %b_1 : !test.type<"A2"> to
                    !test.type<"B2">
                %y = "test.op"(%b_2) ({
                ^bb0(%z: !test.type<"A4">, %c: !test.type<"B5">, %w: !test.type<"A6">):
                    %c_1 = builtin.unrealized_conversion_cast %c : !test.type<"B5"> to
                        !test.type<"A5">
                    %c_2 = builtin.unrealized_conversion_cast %c_1 : !test.type<"A5"> to
                        !test.type<"B5">
                    "test.termop"(%z, %c_2, %w) : (!test.type<"A4">, !test.type<"B5">,
                        !test.type<"A6">) -> ()
                }) : (!test.type<"B2">) -> !test.type<"A3">
            }
            """,
        ),
    ],
)
def test_unrealized_cast_type_conversion_pattern(
    names_not_to_convert: list[str], input_ir: str, expected_ir: str, xdsl_context: Context
) -> None:
    module_op = parse_ir(input_ir, xdsl_context)
    expected_module_op = parse_ir(expected_ir, xdsl_context)
    pattern = SimpleConversionPattern(names_not_to_convert)
    PatternRewriteWalker(pattern, apply_recursively=False).rewrite_module(module_op)
    assert str(module_op) == str(expected_module_op)


@dataclass(frozen=True)
class SimpleControlFlowTypeConversionPattern(ControlFlowUnrealizedCastTypeConversionPattern):
    """A simple ControlFlowUnrealizedCastTypeConversionPattern for testing.

    Converts everything to !test.type<"T">.
    """

    @override
    def convert_type(self, _: Attribute) -> Attribute:
        return t.TestType("T")


@pytest.mark.parametrize(
    ("input_ir", "expected_ir"),
    [
        (
            """
            builtin.module {
                %a, %b = "test.op"() : () -> (!test.type<"A">, !test.type<"A">)
                %c, %d = qstruct.parallel<BOTTOM> -> !test.type<"A">, !test.type<"A"> {
                    qstruct.yield %a : !test.type<"A">
                } {
                    qstruct.yield %b : !test.type<"A">
                }
            }
            """,
            """
            builtin.module {
                %a, %b = "test.op"() : () -> (!test.type<"A">, !test.type<"A">)
                %c, %d = qstruct.parallel<BOTTOM> -> !test.type<"T">, !test.type<"T"> {
                    %a_1 = builtin.unrealized_conversion_cast %a : !test.type<"A"> to
                        !test.type<"T">
                    qstruct.yield %a_1 : !test.type<"T">
                } {
                    %b_1 = builtin.unrealized_conversion_cast %b : !test.type<"A"> to
                        !test.type<"T">
                    qstruct.yield %b_1 : !test.type<"T">
                }
                %c_1 = builtin.unrealized_conversion_cast %c : !test.type<"T"> to !test.type<"A">
                %d_1 = builtin.unrealized_conversion_cast %d : !test.type<"T"> to !test.type<"A">
            }
            """,
        ),
        (
            """
            builtin.module {
                %a = "test.op"() : () -> !test.type<"A">
                %b = qstruct.repeat<2> (%a : !test.type<"A">) -> !test.type<"A"> {
                ^bb0(%c : !test.type<"A">):
                    "test.op"(%c) : (!test.type<"A">) -> !test.type<"A">
                    qstruct.yield %c : !test.type<"A">
                }
            }
            """,
            """
            builtin.module {
                %a = "test.op"() : () -> !test.type<"A">
                %a_1 = builtin.unrealized_conversion_cast %a : !test.type<"A"> to !test.type<"T">
                %b = qstruct.repeat<2> (%a_1 : !test.type<"T">) -> !test.type<"T"> {
                ^bb0(%c : !test.type<"T">):
                    %c_1 = builtin.unrealized_conversion_cast %c : !test.type<"T"> to
                        !test.type<"A">
                    "test.op"(%c_1) : (!test.type<"A">) -> !test.type<"A">
                    %c_2 = builtin.unrealized_conversion_cast %c_1 : !test.type<"A"> to
                        !test.type<"T">
                    qstruct.yield %c_2 : !test.type<"T">
                }
                %b_1 = builtin.unrealized_conversion_cast %b : !test.type<"T"> to !test.type<"A">
            }
            """,
        ),
        (
            """
            builtin.module {
                %b, %a = "test.op"() : () -> (i1, i1)
                %c, %d = scf.if %b -> (i1, i1) {
                    scf.yield %b, %a : i1, i1
                } else {
                    scf.yield %a, %b : i1, i1
                }
            }
            """,
            """
            builtin.module {
                %b, %a = "test.op"() : () -> (i1, i1)
                %c, %d = scf.if %b -> (!test.type<"T">, !test.type<"T">) {
                    %b_1 = builtin.unrealized_conversion_cast %b : i1 to !test.type<"T">
                    %a_1 = builtin.unrealized_conversion_cast %a : i1 to !test.type<"T">
                    scf.yield %b_1, %a_1 : !test.type<"T">, !test.type<"T">
                } else {
                    %a_2 = builtin.unrealized_conversion_cast %a : i1 to !test.type<"T">
                    %b_2 = builtin.unrealized_conversion_cast %b : i1 to !test.type<"T">
                    scf.yield %a_2, %b_2 : !test.type<"T">, !test.type<"T">
                }
                %c_1 = builtin.unrealized_conversion_cast %c : !test.type<"T"> to i1
                %d_1 = builtin.unrealized_conversion_cast %d : !test.type<"T"> to i1
            }
            """,
        ),
        (
            """
            builtin.module {
                %a = "test.op"() : () -> index
                %b = scf.index_switch %a -> index
                case 1 {
                    scf.yield %a : index
                }
                default {
                    scf.yield %a : index
                }
            }
            """,
            """
            builtin.module {
                %a = "test.op"() : () -> index
                %b = scf.index_switch %a -> !test.type<"T">
                case 1 {
                    %a_1 = builtin.unrealized_conversion_cast %a : index to !test.type<"T">
                    scf.yield %a_1 : !test.type<"T">
                }
                default {
                    %a_2 = builtin.unrealized_conversion_cast %a : index to !test.type<"T">
                    scf.yield %a_2 : !test.type<"T">
                }
                %b_1 = builtin.unrealized_conversion_cast %b : !test.type<"T"> to index
            }
            """,
        ),
        (
            """
            builtin.module {
                %i, %j = "test.op"() : () -> (index, index)
                %n, %o = scf.for %k = %i to %j step %j iter_args(%l = %i, %m = %j)
                        -> (index, index) {
                    scf.yield %l, %m : index, index
                }
            }
            """,
            """
            builtin.module {
                %i, %j = "test.op"() : () -> (index, index)
                %i_1 = builtin.unrealized_conversion_cast %i : index to !test.type<"T">
                %j_1 = builtin.unrealized_conversion_cast %j : index to !test.type<"T">
                %n, %o = scf.for %k = %i to %j step %j iter_args(%l = %i_1, %m = %j_1)
                        -> (!test.type<"T">, !test.type<"T">) {
                    %l_1 = builtin.unrealized_conversion_cast %l : !test.type<"T"> to index
                    %m_1 = builtin.unrealized_conversion_cast %m : !test.type<"T"> to index
                    %l_2 = builtin.unrealized_conversion_cast %l_1 : index to !test.type<"T">
                    %m_2 = builtin.unrealized_conversion_cast %m_1 : index to !test.type<"T">
                    scf.yield %l_2, %m_2 : !test.type<"T">, !test.type<"T">
                }
                %n_1 = builtin.unrealized_conversion_cast %n : !test.type<"T"> to index
                %o_1 = builtin.unrealized_conversion_cast %o : !test.type<"T"> to index
            }
            """,
        ),
        (
            """
            builtin.module {
                %a = "test.op"() : () -> i1
                %b = scf.while (%c = %a) : (i1) -> i1 {
                    scf.condition(%c) %c : i1
                } do {
                ^bb0(%d: i1):
                    scf.yield %d : i1
                }
            }
            """,
            """
            builtin.module {
                %a = "test.op"() : () -> i1
                %a_1 = builtin.unrealized_conversion_cast %a : i1 to !test.type<"T">
                %b = scf.while (%c = %a_1) : (!test.type<"T">) -> !test.type<"T"> {
                    %c_1 = builtin.unrealized_conversion_cast %c : !test.type<"T"> to i1
                    %c_2 = builtin.unrealized_conversion_cast %c_1 : i1 to !test.type<"T">
                    scf.condition(%c_1) %c_2 : !test.type<"T">
                } do {
                ^bb0(%d: !test.type<"T">):
                    %d_1 = builtin.unrealized_conversion_cast %d : !test.type<"T"> to i1
                    %d_2 = builtin.unrealized_conversion_cast %d_1 : i1 to !test.type<"T">
                    scf.yield %d_2 : !test.type<"T">
                }
                %b_1 = builtin.unrealized_conversion_cast %b : !test.type<"T"> to i1
            }
            """,
        ),
    ],
)
def test_control_flow_pattern(input_ir: str, expected_ir: str, xdsl_context: Context):
    module_op = parse_ir(input_ir, xdsl_context)
    expected_module_op = parse_ir(expected_ir, xdsl_context)
    pattern = SimpleControlFlowTypeConversionPattern()
    PatternRewriteWalker(pattern, apply_recursively=False).rewrite_module(module_op)
    assert str(module_op) == str(expected_module_op)
