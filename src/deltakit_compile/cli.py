# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""
CLI module
"""

import importlib.metadata
import json
from pathlib import Path
from typing import Annotated

import typer
from deltakit_stim import Circuit
from typer.core import TyperGroup
from typing_extensions import override
from xdsl.parser import Parser

from deltakit_compile.constants import DIST_NAME
from deltakit_compile.frontend.deltakit_stim.io import (
    deltakit_stim_circuit_to_dialect,
    deltakit_stim_context,
    deltakit_stim_dialect_to_circuit,
)
from deltakit_compile.pass_runner import ArgumentDict, PassRunner


class OrderCommands(TyperGroup):
    """Subclass enforcing that commands are ordered in alphabetical order in the help messages."""

    @override
    def list_commands(self, ctx):
        return sorted(self.commands)


app = typer.Typer(
    cls=OrderCommands,
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)


# region Deltakit-Stim commands

deltakit_stim_app = typer.Typer(
    cls=OrderCommands,
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)
app.add_typer(
    deltakit_stim_app,
    name="deltakit-stim",
    help="Commands for converting between MLIR and Deltakit-Stim circuits.",
)


@deltakit_stim_app.command("parse")
def parse_deltakit_stim(
    input_path: Annotated[
        Path,
        typer.Argument(
            exists=True, dir_okay=False, help="Path to the input Deltakit-Stim circuit."
        ),
    ],
    output_path: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-O",
            help="Destination path for the output MLIR file. "
            "If not specified, it's next to the input file with an _out suffix.",
        ),
    ] = None,
) -> None:
    """Convert a Deltakit-Stim circuit to an MLIR file containing operations from Deltakit's stim
    and deltakit-stim dialects."""
    circuit = Circuit.from_file(input_path)
    module_op = deltakit_stim_circuit_to_dialect(circuit)

    # If no output path provided, use input filename with _out
    if output_path is None:
        output_path = input_path.with_name(f"{input_path.stem}_out.mlir")

    output_path.write_text(str(module_op), encoding="utf-8")
    print(f"Output program file saved at: {output_path}")  # noqa: T201


@deltakit_stim_app.command("print")
def print_deltakit_stim(
    input_path: Annotated[
        Path, typer.Argument(exists=True, dir_okay=False, help="Path to the input MLIR file.")
    ],
    output_path: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-O",
            help="Destination path for the output Deltakit-Stim circuit. "
            "If not specified, it's next to the input file with an _out suffix.",
        ),
    ] = None,
) -> None:
    """Convert an MLIR file containing operations from Deltakit's stim and deltakit-stim dialects
    into a Deltakit-Stim circuit."""
    module_str = input_path.read_text(encoding="utf-8")
    module_op = Parser(deltakit_stim_context(), module_str).parse_module()
    circuit = deltakit_stim_dialect_to_circuit(module_op)

    # If no output path provided, use input filename with _out
    if output_path is None:
        output_path = input_path.with_name(f"{input_path.stem}_out.stim")

    circuit.to_file(output_path)
    print(f"Output program file saved at: {output_path}")  # noqa: T201


# endregion

# region root commands


def _parse_pass_arguments(params_str: str) -> ArgumentDict:
    """Parse a JSON string of pass arguments into a dictionary."""
    try:
        input_parameters = json.loads(params_str)
        if not isinstance(input_parameters, dict):
            msg = f"Pass arguments are {type(input_parameters)}, but should be a dictionary"
            raise ValueError(msg)

        return input_parameters
    except ValueError as exp:
        msg = "Pass arguments must be in a valid JSON dictionary"
        raise ValueError(msg) from exp


@app.command("compile-passes")
def compile_passes(
    input_path: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, help="Path to the input program file."),
    ],
    output_path: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-O",
            help="Destination path for the compiled file. "
            "If not specified, it defaults to the input file's directory with an _out suffix.",
        ),
    ] = None,
    passes: Annotated[
        list[str] | None,
        typer.Option(
            "--pass",
            "-p",
            help="Compiler pass to be run on the input file. "
            "Use this multiple times for multiple passes, run in the order listed.",
        ),
    ] = None,
    pass_args: str = typer.Option(
        default="{}",
        help="Additional arguments to be provided to the compiler passes. "
        "These must be in the form of a JSON dict, e.g. '{\"param\": 0xFF}'.",
    ),
    test_mode: Annotated[
        bool,
        typer.Option(
            "--test-mode",
            "-t",
            help="Flag to enable a testing mode where the Test dialect can be used.",
        ),
    ] = False,
) -> None:
    """Run individual compiler passes on an MLIR file.

    With this you can run any passes in any order with any arguments with no guard rails (for
    testing and experimentation). Multiple module ops can be in the same input MLIR file (treated as
    separate programs) if separated by '// ----' lines."""
    program = input_path.read_text(encoding="utf-8")
    params = _parse_pass_arguments(pass_args)
    output_program = PassRunner(include_test_dialect=test_mode).run(
        program, passes if passes is not None else [], params
    )

    if output_path is None:
        output_path = input_path.with_name(f"{input_path.stem}_out.mlir")

    output_path.write_text(output_program, encoding="utf-8")
    print(f"Output program file saved at: {output_path}")  # noqa: T201


@app.command("version")
def deltakit_compile_version() -> None:
    """Print the version of deltakit_compile."""
    print(f"deltakit_compile v{importlib.metadata.version(DIST_NAME)}")  # noqa: T201


# endregion

if __name__ == "__main__":  # pragma: no cover
    app()
