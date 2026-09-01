"""Exception tests for the inline-circuits-and-subroutines pass."""

import pytest
from xdsl.context import Context
from xdsl.dialects import test as t
from xdsl.dialects.builtin import ModuleOp, StringAttr
from xdsl.ir import Block, Region

from deltakit_compile.dialects import func
from deltakit_compile.dialects import log_asm_api as api
from deltakit_compile.exceptions import CompilerPassCheckError
from deltakit_compile.passes.log_asm_api.inline_circuits_and_subroutines import (
    InlineCircuitsAndSubroutines,
)


def test_recursive_function_exception() -> None:
    """Test that an error is raised, when the 'error_on_functions_not_inlined' option is set in the
    pass and there is a used, recursively defined, function."""

    func_op = func.FuncOp(
        "A",
        ([], []),
        Region(
            Block(
                [
                    t.TestOp(attributes={"function": StringAttr("A")}),
                    func.CallOp("A", [], []),
                    func.ReturnOp(),
                ]
            )
        ),
    )
    outer_call = func.CallOp("A", [], [])
    module_op = ModuleOp([func_op, outer_call])

    module_op.verify()
    module_pass = InlineCircuitsAndSubroutines(error_on_functions_not_inlined=True)

    with pytest.raises(
        CompilerPassCheckError,
        match=r'func\.func "A" could not be inlined: it is called recursively',
    ):
        module_pass.apply(Context(), module_op)


def test_recursive_circuit_exception() -> None:
    """Test that an error is raised, when the 'error_on_circuits_not_inlined' option is set in the
    pass and there is a used, recursively defined, circuit."""
    circuit_dec = api.CircuitDeclarationOp(
        "A",
        ([], []),
        Region(
            Block(
                [
                    t.TestOp(attributes={"circuit": StringAttr("A")}),
                    api.CallOp("A", [], []),
                    api.ReturnOp(),
                ]
            )
        ),
    )
    outer_call = api.CallOp("A", [], [])
    module_op = ModuleOp([circuit_dec, outer_call])

    module_op.verify()
    module_pass = InlineCircuitsAndSubroutines(error_on_circuits_not_inlined=True)

    with pytest.raises(
        CompilerPassCheckError,
        match=r'log_asm_api\.circuit_dec "A" could not be inlined: it is called recursively',
    ):
        module_pass.apply(Context(), module_op)
