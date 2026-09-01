"""Tests for the pass runner module."""

from dataclasses import dataclass

import pytest
from pytest_mock import MockerFixture
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.passes import ModulePass
from xdsl.utils.exceptions import ParseError

from deltakit_compile.pass_runner import PassRunner


@dataclass(frozen=True)
class Pass0(ModulePass):
    """Test pass 0."""

    test_param: list[float]

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        pass


@dataclass(frozen=True)
class Pass1(ModulePass):
    """Test pass 1."""

    def apply(self, ctx: Context, op: ModuleOp) -> None:
        pass


@pytest.fixture(name="mock_passes")
def fixture_mock_passes(mocker: MockerFixture):
    """Fixture that mocks the available compiler passes by replacing PASS_MAP."""
    mock_passes = (
        mocker.patch("tests.unit.test_pass_runner.Pass0", autospec=True),
        mocker.patch("tests.unit.test_pass_runner.Pass1", autospec=True),
    )
    mocker.patch("deltakit_compile.pass_runner.PASS_MAP", {"pass-0": Pass0, "pass-1": Pass1})
    return mock_passes


def test_run_passes(mock_passes):
    """Test running multiple passes with no arguments."""
    program = "builtin.module {\n}"
    program_out = PassRunner().run(program, ["pass-1", "pass-1"], {})
    assert program == program_out
    assert mock_passes[1].call_count == 2


def test_run_passes_with_test_dialect():
    """Test using PassRunner with test dialect input."""
    program = 'builtin.module {\n  "test.op"() : () -> ()\n}'
    program_out = PassRunner(include_test_dialect=True).run(program, [], {})
    assert program == program_out
    with pytest.raises(ParseError):
        PassRunner(include_test_dialect=False).run(program, [], {})


def test_multiple_module_ops(mock_passes):
    """Test running passes on multiple module ops."""
    program = "builtin.module {\n}\n// ----\nbuiltin.module {\n}"
    program_out = PassRunner().run(program, ["pass-1", "pass-1"], {})
    assert program == program_out
    assert mock_passes[1].call_count == 4


def test_pass_arguments(mock_passes):
    """Test that arguments are provided to passes only if they need them."""
    program = "builtin.module {\n}"
    program_out = PassRunner().run(program, ["pass-0", "pass-1"], {"test_param": [2, 4]})
    assert program == program_out
    mock_passes[0].assert_called_once_with([2, 4])
    mock_passes[1].assert_called_once_with()
