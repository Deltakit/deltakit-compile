"""Shared dialect test fixtures and functions."""

from collections.abc import Sequence
from io import StringIO

from deltakit_stim import Circuit
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import IRNode, Operation, SSAValue
from xdsl.parser import Parser
from xdsl.printer import Printer

from deltakit_compile.dialects.stim import to_stim
from deltakit_compile.frontend.deltakit_stim import deltakit_stim_circuit_to_dialect


def check_asm_roundtrip(program: str, ctx: Context):
    """Check that the given program roundtrips through IR, back to xDSL assembly exactly (including
    whitespaces)."""
    parser = Parser(ctx, program)
    ops: list[Operation] = []
    while (op := parser.parse_optional_operation()) is not None:
        ops.append(op)

    module_op = ModuleOp(ops)
    module_op.verify()

    res_io = StringIO()
    printer = Printer(stream=res_io)
    for op in ops[:-1]:
        printer.print_op(op)
        printer.print_string("\n ")
    printer.print_op(ops[-1])

    assert program == res_io.getvalue()


def check_ir_roundtrip(
    ops: Sequence[Operation], ctx: Context, generic_printing: bool | None = None
) -> None:
    """Check that the given program roundtrips from IR, to xDSL textual format and back.
    if ``generic_printing`` is None, this checks both generic printing and custom printing."""

    if generic_printing is None:
        check_ir_roundtrip(ops, ctx, generic_printing=False)
        check_ir_roundtrip(ops, ctx, generic_printing=True)
        return

    printed_ir = StringIO()
    printer = Printer(stream=printed_ir)
    printer.print_generic_format = generic_printing
    for i, op in enumerate(ops):
        if i:
            printer.print_string("\n")
        printer.print_op(op)

    parser = Parser(ctx, printed_ir.getvalue())
    parsed_ops: list[Operation] = []
    while (parsed_op := parser.parse_optional_operation()) is not None:
        parsed_op.verify()
        parsed_ops.append(parsed_op)

    check_ctx: dict[IRNode | SSAValue, IRNode | SSAValue] = {}
    for op, parsed_op in zip(ops, parsed_ops, strict=True):
        assert op.is_structurally_equivalent(parsed_op, context=check_ctx)


def check_stim_roundtrip(stim_str: str, exp_stim_str: str | None) -> None:
    """Do a roundtrip test from stim str to stim dialect and back to stim str. If exp_stim_str is
    None it is expected that the output stim will be identical to stim_str."""
    module_op = deltakit_stim_circuit_to_dialect(Circuit(stim_str))
    module_op.verify()

    out_stim_str = to_stim(module_op)
    exp_stim_str = stim_str if exp_stim_str is None else exp_stim_str
    assert out_stim_str == "\n" + exp_stim_str
