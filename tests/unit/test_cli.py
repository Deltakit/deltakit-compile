"""Tests for CLI"""

import importlib.metadata
import shutil
from pathlib import Path

import pytest
import typer
from deltakit_stim import Circuit
from packaging import version
from pytest_mock import MockerFixture, MockType
from typer.testing import CliRunner
from xdsl.dialects.builtin import ModuleOp

from deltakit_compile.cli import app
from deltakit_compile.constants import DIST_NAME

# Typer >=0.26 removed mix_stderr and made the behaviour where it's false the default, so we have to
# do this to support Typer from both before and after that change
runner = (
    CliRunner(mix_stderr=False)  # type: ignore [call-arg]
    if version.parse(typer.__version__) < version.parse("0.26")
    else CliRunner()
)


@pytest.fixture(name="pass_runner_flags")
def fixture_pass_runner_flags(tmp_path: Path):
    """Fixture to provide the pass runner CLI flags"""
    mlir_path = tmp_path / "program.mlir"
    mlir_path.write_text("builtin.module {}", encoding="utf-8")

    return [
        "compile-passes",
        str(mlir_path),
        "-p",
        "pass-0",
        "-p",
        "pass-1",
        "--pass-args",
        '{"param": 12}',
    ]


@pytest.fixture(name="mock_pass_runner")
def fixture_mock_pass_runner(mocker: MockerFixture):
    """Fixture to mock the deltakit compiler methods."""
    mock_class = mocker.patch("deltakit_compile.cli.PassRunner", autospec=True)
    mock = mock_class()
    mock.run.return_value = "Jeff"
    return mock


class TestDeltakitStimCommands:
    @pytest.mark.parametrize("output_name", ["", "steve.mlir"])
    def test_parse(self, output_name: str, tmp_path: Path, mocker: MockerFixture) -> None:
        mock = mocker.patch(
            "deltakit_compile.cli.deltakit_stim_circuit_to_dialect",
            autospec=True,
            return_value=ModuleOp([]),
        )

        circuit_path = tmp_path / "circuit.stim"
        circuit = Circuit("QUBIT_COORDS(0, 0) 0\nH 0\nM 0")
        circuit.to_file(circuit_path)

        args = ["deltakit-stim", "parse", str(circuit_path)]
        if output_name:
            temp_output_file = tmp_path / output_name
            args += ["-O", str(temp_output_file)]
        else:
            temp_output_file = tmp_path / "circuit_out.mlir"
        result = runner.invoke(app, args)

        assert result.exit_code == 0
        assert f"Output program file saved at: {temp_output_file}" in result.stdout
        assert temp_output_file.exists()
        mock.assert_called_once_with(circuit)

    @pytest.mark.parametrize("output_name", ["", "steve.stim"])
    def test_print(self, output_name: str, tmp_path: Path, mocker: MockerFixture) -> None:
        mock = mocker.patch(
            "deltakit_compile.cli.deltakit_stim_dialect_to_circuit",
            autospec=True,
            return_value=Circuit(),
        )

        module_path = tmp_path / "circuit.mlir"
        module_op = ModuleOp([])
        module_path.write_text(str(module_op), encoding="utf-8")

        args = ["deltakit-stim", "print", str(module_path)]
        if output_name:
            temp_output_file = tmp_path / output_name
            args += ["-O", str(temp_output_file)]
        else:
            temp_output_file = tmp_path / "circuit_out.stim"
        result = runner.invoke(app, args)

        assert result.exit_code == 0
        assert f"Output program file saved at: {temp_output_file}" in result.stdout
        assert temp_output_file.exists()
        mock.assert_called_once()
        assert module_op.is_structurally_equivalent(mock.call_args.args[0])


def test_compile_passes(tmp_path, pass_runner_flags, mock_pass_runner):
    """Test arguments to the compile-passes CLI are given to the pass runner correctly and an output
    MLIR file is created in the default location."""
    temp_output_file = tmp_path / "program_out.mlir"
    result = runner.invoke(app, pass_runner_flags)

    assert result.exit_code == 0
    assert f"Output program file saved at: {temp_output_file}" in result.stdout
    mock_pass_runner.run.assert_called_once_with(
        "builtin.module {}", ["pass-0", "pass-1"], {"param": 12}
    )


@pytest.mark.parametrize(
    ("test_flags", "exp_flag"),
    [(["--test-mode"], True), (["-t"], True), ([], False)],
)
def test_compile_passes_test_mode(tmp_path, mocker: MockerFixture, test_flags, exp_flag):
    """Test test mode arguments to the compile-passes CLI are given to the pass runner correctly
    and so test dialect ops are parsed only when they should be."""

    mock_class = mocker.patch("deltakit_compile.cli.PassRunner", autospec=True)
    mock_runner = mock_class.return_value

    mlir_path = tmp_path / "program.mlir"
    mlir_path.write_text('builtin.module { "test.op"() : () -> () }', encoding="utf-8")

    runner.invoke(app, ["compile-passes", str(mlir_path), *test_flags])

    mock_class.assert_called_once_with(include_test_dialect=exp_flag)
    mock_runner.run.assert_called_once_with('builtin.module { "test.op"() : () -> () }', [], {})


@pytest.mark.parametrize("args_str", ["{12: 12}", "asdf", "2", "[0, 1]"])
def test_compile_passes_invalid_pass_args(
    pass_runner_flags, mock_pass_runner: MockType, args_str: str
):
    """Test that invalid compile-passes pass args throws an error."""
    result = runner.invoke(app, [*pass_runner_flags, "--pass-args", args_str])

    assert result.exit_code == 1
    assert isinstance(result.exception, ValueError)
    assert "Pass arguments must be in a valid JSON dictionary" in str(result.exc_info)
    mock_pass_runner.run.assert_not_called()


def test_help_option() -> None:
    """Test the help text shows all options in a dev build and hides some options in a release
    build."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage" in result.stdout
    assert "version" in result.stdout
    assert "compile" in result.stdout


def test_cli_version() -> None:
    """Test the help option shows correct usage."""

    cli_version = runner.invoke(app, ["version"])
    assert f"deltakit_compile v{importlib.metadata.version(DIST_NAME)}" in cli_version.stdout


def test_cli_installed():
    """Test that the CLI command is available in the system PATH."""

    deltakit_compile_path = shutil.which("deltakit_compile")
    assert deltakit_compile_path is not None
    assert Path(deltakit_compile_path).exists()
