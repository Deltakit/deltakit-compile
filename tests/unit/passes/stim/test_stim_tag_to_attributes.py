# (c) Copyright Riverlane 202. All rights reserved.
"""Tests for the stim_tag_to_attributes pass."""

import json

import pytest
from xdsl.context import Context
from xdsl.dialects.builtin import StringAttr
from xdsl.utils.exceptions import ParseError

from deltakit_compile.dialects.stim import escape_custom_escape_sequences
from deltakit_compile.passes.stim.stim_tag_to_attributes import (
    StimTagToAttributes,
    _convert_value_to_attribute,
    _handle_string,
    _process_custom_escape_sequences,
)
from tests.unit.conftest import parse_ir


def test_non_string_tag_attribute(xdsl_context: Context):
    """Test that a stim.tag attribute which is not a StringAttr raises a TypeError."""
    mlir = """
        "test.op"() {stim.tag = 42} : () -> ()
    """

    module_op = parse_ir(mlir, xdsl_context)

    with pytest.raises(TypeError, match=r"Expected stim.tag attribute to be a StringAttr"):
        StimTagToAttributes(False).apply(xdsl_context, module_op)


def test_non_dictionary_string_attribute(xdsl_context: Context):
    """Test that a stim.tag attribute which is a StringAttr and parses to a non-dictionary raises
    a ValueError."""
    mlir = """
        "test.op"() {stim.tag = "34324"} : () -> ()
    """

    module_op = parse_ir(mlir, xdsl_context)

    with pytest.raises(
        ValueError, match=r"Expected stim.tag JSON to be a dictionary for op \"test.op\""
    ):
        StimTagToAttributes(False).apply(xdsl_context, module_op)


class TestConvertValueToAttribute:
    """Tests for the convert_value_to_attribute function."""

    def test_unsupported_type_raises_value_error(self):
        # Test with a type that's not in the _TYPE_HANDLERS dictionary
        unsupported_value = object()

        with pytest.raises(
            ValueError, match=r"Unsupported type in stim\.tag JSON: <class 'object'>"
        ):
            _convert_value_to_attribute(unsupported_value, Context(), suppress_failed_parsing=False)

    def test_unsupported_type_tuple_raises_value_error(self):
        """Test that a tuple (unsupported type) raises a ValueError."""
        unsupported_value = (1, 2, 3)

        with pytest.raises(
            ValueError, match=r"Unsupported type in stim\.tag JSON: <class 'tuple'>"
        ):
            _convert_value_to_attribute(unsupported_value, Context(), suppress_failed_parsing=False)

    def test_unsupported_type_set_raises_value_error(self):
        """Test that a set (unsupported type) raises a ValueError."""
        unsupported_value = {1, 2, 3}

        with pytest.raises(ValueError, match=r"Unsupported type in stim\.tag JSON: <class 'set'>"):
            _convert_value_to_attribute(unsupported_value, Context(), suppress_failed_parsing=False)

    def test_unsupported_type_bytes_raises_value_error(self):
        """Test that bytes (unsupported type) raises a ValueError."""
        unsupported_value = b"hello"

        with pytest.raises(
            ValueError, match=r"Unsupported type in stim\.tag JSON: <class 'bytes'>"
        ):
            _convert_value_to_attribute(unsupported_value, Context(), suppress_failed_parsing=False)


class TestHandleString:
    """Tests for the _handle_string function."""

    def test_parse_error_raised_when_parsing_fails_and_not_suppressed(self, xdsl_context: Context):
        """Test that ParseError is raised when attribute parsing fails and suppression is off."""
        # Invalid attribute syntax - missing closing bracket
        invalid_attr_string = "##builtin.int<42"

        with pytest.raises(ParseError):
            _handle_string(invalid_attr_string, xdsl_context, suppress_failed_parsing=False)

    def test_parse_error_raised_for_unknown_dialect(self, xdsl_context: Context):
        """Test that ParseError is raised when dialect is not recognised."""
        # Unknown dialect
        invalid_attr_string = "##unknown_dialect.some_attr<value>"

        with pytest.raises(ParseError):
            _handle_string(invalid_attr_string, xdsl_context, suppress_failed_parsing=False)

    def test_returns_string_attr_when_parsing_fails_and_suppressed(self, xdsl_context: Context):
        """Test that StringAttr is returned when attribute parsing fails and suppression is on."""
        # Invalid attribute syntax
        invalid_attr_string = "##builtin.int<42"

        result = _handle_string(invalid_attr_string, xdsl_context, suppress_failed_parsing=True)

        assert isinstance(result, StringAttr)
        assert result.data == invalid_attr_string


def test_failed_json_parse(xdsl_context: Context):
    """Test that a JSON parsing error in the stim.tag attribute raises a JSONDecodeError."""
    # The string "not a json" is not valid JSON, so this should raise an error
    mlir = """
        "test.op"() {stim.tag = "not a json"} : () -> ()
    """

    module_op = parse_ir(mlir, xdsl_context)

    with pytest.raises(json.JSONDecodeError):
        StimTagToAttributes(False).apply(xdsl_context, module_op)


@pytest.mark.parametrize(
    ("original", "escaped"),
    [
        ("", ""),
        ("plain text", "plain text"),
        ("]", r"\C"),
        ("\\", r"\B"),
        ("\n", r"\n"),
        ("\r", r"\r"),
        ("a]b\\c\nd\re", r"a\Cb\Bc\nd\re"),
    ],
)
def test_custom_escape_sequences_roundtrip(original: str, escaped: str):
    """Escape and unescape helpers should be inverses for supported sequences."""
    assert escape_custom_escape_sequences(original) == escaped
    assert _process_custom_escape_sequences(escaped) == original
