"""Shared pytest fixtures."""

from pathlib import Path
from typing import Final

import numpy as np
import pytest
from xdsl.context import Context
from xdsl.dialects.builtin import Builtin, ModuleOp
from xdsl.dialects.test import Test
from xdsl.ir import Operation, SSAValue
from xdsl.parser import Parser

from deltakit_compile.dialects.arith import Arith
from deltakit_compile.dialects.deltakit_stim import DeltakitStim
from deltakit_compile.dialects.log_asm_api import LogAsmApi
from deltakit_compile.dialects.logical_assembly import LogicalAsm
from deltakit_compile.dialects.ncstim import NCStim
from deltakit_compile.dialects.plaquette import Plaquette
from deltakit_compile.dialects.qcore import QCore
from deltakit_compile.dialects.qec import Qec
from deltakit_compile.dialects.qref import QRef
from deltakit_compile.dialects.qstruct import QStruct
from deltakit_compile.dialects.scf import Scf
from deltakit_compile.dialects.sobs import Sobs
from deltakit_compile.dialects.stabiliser import Stab
from deltakit_compile.dialects.stim import Stim

DEFAULT_UINT_SIZE: Final[int] = 64


@pytest.fixture
def xdsl_context():
    """Fixture for constructing the xDSL context object."""
    ctx = Context()
    ctx.load_dialect(QCore)
    ctx.load_dialect(QRef)
    ctx.load_dialect(Stim)
    ctx.load_dialect(DeltakitStim)
    ctx.load_dialect(LogicalAsm)
    ctx.load_dialect(LogAsmApi)
    ctx.load_dialect(NCStim)
    ctx.load_dialect(Plaquette)
    ctx.load_dialect(QStruct)
    ctx.load_dialect(Qec)
    ctx.load_dialect(Builtin)
    ctx.load_dialect(Arith)
    ctx.load_dialect(Scf)
    ctx.load_dialect(Sobs)
    ctx.load_dialect(Stab)
    ctx.load_dialect(Test)
    return ctx


def parse_ir(ir: str, context: Context, verify: bool = True) -> ModuleOp:
    """Parse a string of IR and return the encoded ModuleOp."""
    parser = Parser(context, ir)
    ops: list[Operation] = []
    while (op := parser.parse_optional_operation()) is not None:
        ops.append(op)

    module_op = ModuleOp(ops)
    if verify:
        module_op.verify()
    return module_op


def compute_name_to_ssa(module_op: ModuleOp) -> dict[str, SSAValue]:
    """Compute a mapping from name hints to SSA values for all SSA values in the module that have a
    name hint."""
    result_name_to_ssa: dict[str, SSAValue] = {
        result.name_hint: result
        for op in module_op.walk()
        for result in op.results
        if result.name_hint is not None
    }
    block_arg_name_to_ssa: dict[str, SSAValue] = {
        arg.name_hint: arg
        for block in module_op.walk_blocks()
        for arg in block.args
        if arg.name_hint is not None
    }
    return result_name_to_ssa | block_arg_name_to_ssa


@pytest.fixture(scope="session", name="reference_data_dir")
def fixture_reference_data_dir():
    return Path("tests", "resources", "reference_data")


@pytest.fixture(scope="session")
def random_generator():
    """Get a Numpy random number generator"""
    return np.random.default_rng()
