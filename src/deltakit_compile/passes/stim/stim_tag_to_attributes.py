# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module containing a pass that converts stim.tag attribute to xdsl attributes"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import (
    ArrayAttr,
    BoolAttr,
    DictionaryAttr,
    Float64Type,
    FloatAttr,
    IntAttr,
    ModuleOp,
    NoneAttr,
    StringAttr,
)
from xdsl.ir import Attribute, Operation
from xdsl.parser import Parser
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
)
from xdsl.utils.exceptions import ParseError

from deltakit_compile.dialects.stim import TAG_ATTR


def _process_custom_escape_sequences(s: str) -> str:
    """Process custom escape sequences in stim.tag strings.

    Custom escape sequences:
    - \\C → ]
    - \\r → carriage return
    - \\n → line feed
    - \\B → \\

    Note: \\B is processed last to avoid double-processing with other escapes.
    """
    # Process in order, handling backslash last to avoid double-processing
    s = s.replace(r"\C", "]")
    s = s.replace(r"\r", "\r")
    s = s.replace(r"\n", "\n")
    return s.replace(r"\B", "\\")


_SupportedTypes = str | int | float | dict | list | None


def _handle_string(value: str, ctx: Context, suppress_failed_parsing: bool) -> Attribute:
    """Handle string conversion, attempting to parse as attribute if starts with '#'."""
    if value.startswith("#"):
        try:
            return Parser(ctx, value[1:]).parse_attribute()
        except ParseError as e:
            if not suppress_failed_parsing:
                raise e
    return StringAttr(value)


def _handle_int(value: int, _: Context, __: bool) -> IntAttr:
    """Handle integer conversion."""
    return IntAttr(value)


def _handle_bool(value: bool, _: Context, __: bool) -> BoolAttr:
    """Handle boolean conversion."""
    return BoolAttr.from_bool(value)


def _handle_float(value: float, _: Context, __: bool) -> FloatAttr:
    """Handle float conversion."""
    return FloatAttr(value, Float64Type())


def _handle_dict(value: dict, ctx: Context, suppress_failed_parsing: bool) -> DictionaryAttr:
    """Handle dictionary conversion, recursively converting values."""
    converted_dict = {
        k: _convert_value_to_attribute(v, ctx, suppress_failed_parsing=suppress_failed_parsing)
        for k, v in value.items()
    }
    return DictionaryAttr(converted_dict)


def _handle_list(value: list, ctx: Context, suppress_failed_parsing: bool) -> ArrayAttr:
    """Handle list conversion, recursively converting elements."""
    converted_list = [
        _convert_value_to_attribute(item, ctx, suppress_failed_parsing=suppress_failed_parsing)
        for item in value
    ]
    return ArrayAttr(converted_list)


def _handle_none(_: None, __: Context, ___: bool) -> NoneAttr:
    """Handle None conversion."""
    return NoneAttr()


# Dictionary mapping types to handler functions for O(1) lookup
_TYPE_HANDLERS: Final[dict[type, Callable[[Any, Context, bool], Attribute]]] = {
    str: _handle_string,
    int: _handle_int,
    float: _handle_float,
    bool: _handle_bool,
    dict: _handle_dict,
    list: _handle_list,
    type(None): _handle_none,
}


def _convert_value_to_attribute(
    value: _SupportedTypes, ctx: Context, suppress_failed_parsing: bool
) -> Attribute:
    """Convert a JSON value to the appropriate xDSL Attribute.

    For dicts and lists, recursively converts nested values.
    For strings starting with '#', attempts to parse as an attribute.

    Uses a dictionary lookup for O(1) performance.
    """
    value_type = type(value)
    handler = _TYPE_HANDLERS.get(value_type)

    if handler is None:
        msg = f"Unsupported type in {TAG_ATTR} JSON: {value_type}"
        raise ValueError(msg)

    return handler(value, ctx, suppress_failed_parsing)


class _StimTagRewrite(RewritePattern):
    """Add stim ticks to the circuit."""

    def __init__(self, ctx: Context, suppress_failed_parsing: bool):
        self._suppress_failed_parsing = suppress_failed_parsing
        self._ctx = ctx

    @override
    def match_and_rewrite(self, op: Operation, rewriter: PatternRewriter) -> None:
        if data := op.attributes.get(TAG_ATTR):
            if not isinstance(data, StringAttr):
                msg = (
                    f"Expected {TAG_ATTR} attribute to be a StringAttr, instead got, {data!s},"
                    f" of type , {[str(data.name)]}, on op, {op!s}"
                )
                raise TypeError(msg)
            # Process custom escape sequences before parsing JSON
            processed_string = _process_custom_escape_sequences(data.data)
            try:
                tag_dict: dict = json.loads(processed_string)
            except json.JSONDecodeError as e:
                if not self._suppress_failed_parsing:
                    msg = f"Could not parse {TAG_ATTR} attribute as JSON for op {op!s}: {e}"
                    raise json.JSONDecodeError(msg, processed_string, e.pos) from e
                return

            if not isinstance(tag_dict, dict):
                if not self._suppress_failed_parsing:
                    msg = (
                        f"Expected {TAG_ATTR} JSON to be a dictionary for op {op!s}, got "
                        f"{type(tag_dict)}"
                    )
                    raise ValueError(msg)
                return

            del op.attributes[TAG_ATTR]
            # Convert each JSON value to an appropriate attribute
            for key, value in tag_dict.items():
                op.attributes[key] = _convert_value_to_attribute(
                    value, self._ctx, suppress_failed_parsing=self._suppress_failed_parsing
                )

            # Remove the stim.tag attribute after processing
            rewriter.notify_op_modified(op)


@dataclass(frozen=True)
class StimTagToAttributes(ModulePass):
    """Pass that converts stim.tag attributes to xdsl attributes.

    The pass looks for stim.tag attributes on all operations, attempts to parse it as JSON, and if
    successful converts each key-value pair in the JSON to an xdsl attribute on the same operation.
    The original stim.tag attribute is removed after processing. For strings, if the string starts
    with #, the pass will attempt to parse the rest (excluding the #) of the string as an xdsl
    attribute.

    Attributes:
        suppress_failed_parsing (bool):
            If True, suppresses JSON parsing errors and xdsl attribute parsing
            errors. If JSON parsing fails, the stim.tag attribute will be left unchanged.
            If xdslattribute parsing fails for a string starting with #, the original string
            will be used as a StringAttr value. The default value is True.
        name:
            The name of the pass is "stim-tag-to-attributes".
    """

    suppress_failed_parsing: bool = True

    name = "stim-tag-to-attributes"

    @override
    def apply(self, ctx, op: ModuleOp) -> None:
        PatternRewriteWalker(
            _StimTagRewrite(ctx, self.suppress_failed_parsing), apply_recursively=False
        ).rewrite_module(op)
