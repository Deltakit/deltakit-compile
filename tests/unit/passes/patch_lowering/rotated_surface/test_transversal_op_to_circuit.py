"""Tests for the TransversalOpToCircuit pass.

This module tests the ``transversal-op-to-circuit`` pass that replaces "transversal" operations
(for the moment, ``log_asm.prepare`` and ``log_asm.measure``) into ``qcore`` operations.
"""

import re

import pytest
from xdsl.context import Context
from xdsl.pattern_rewriter import PatternRewriteWalker

from deltakit_compile.dialects.logical_assembly import (
    MeasureOp,
    PatchDeclarationOp,
    PrepareOp,
    UnrotatedPlanarPatchType,
)
from deltakit_compile.exceptions import CompilerPassCheckError
from deltakit_compile.passes.patch_lowering.rotated_surface.transversal_op_to_circuit import (
    _MeasureOpPattern,
    _PrepareOpPattern,
)
from tests.unit.conftest import parse_ir


def test_prepare_pattern_ignores_unrotated_patches(xdsl_context: Context) -> None:
    ir = """
    builtin.module {
        %patch = log_asm.patch_dec ->
            !log_asm.patch.unrot_planar<size=(2, 2), location=(0, 0), orient=v_z>
        %p0 = log_asm.prepare<Z>
            (%patch : !log_asm.patch.unrot_planar<size=(2, 2), location=(0, 0), orient=v_z>)
    }
    """
    module = parse_ir(ir, xdsl_context)
    walker = PatternRewriteWalker(_PrepareOpPattern(True))
    walker.rewrite_module(module)
    # All operations are applied on unrotated patches, they should be kept intact.
    decl_ops = [op for op in module.walk() if isinstance(op, PatchDeclarationOp)]
    assert len(decl_ops) == 1
    assert isinstance(decl_ops[0].res.type, UnrotatedPlanarPatchType)

    prepare_ops = [op for op in module.walk() if isinstance(op, PrepareOp)]
    assert len(prepare_ops) == 1
    assert isinstance(prepare_ops[0].patch.type, UnrotatedPlanarPatchType)


def test_measure_pattern_ignores_unrotated_patches(xdsl_context: Context) -> None:
    ir = """
    builtin.module {
        %patch = log_asm.patch_dec ->
            !log_asm.patch.unrot_planar<size=(2, 2), location=(0, 0), orient=h_z>
        %p0 = log_asm.prepare<Z>
            (%patch : !log_asm.patch.unrot_planar<size=(2, 2), location=(0, 0), orient=h_z>)

        %p0_1 = log_asm.meas_stab<2>
            (%p0 : !log_asm.patch.unrot_planar<size=(2, 2), location=(0.0, 0.0), orient=h_z>)

        %qreg = log_asm.cast(%p0_1 : !log_asm.patch.unrot_planar<size=(2, 2), location=(0.0, 0.0),
            orient=h_z>) -> !qcore.qubit_reg<9>
        %q_1, %q_2, %q_3, %q_4, %q_5, %q_6, %q_7, %q_8, %q_9 = qcore.unpack_qubit_reg(%qreg :
            !qcore.qubit_reg<9>)
        %pobs, %q_10, %q_11, %q12 = qstruct.circuit(%q_1, %q_4, %q_7 : !qcore.qubit, !qcore.qubit,
            !qcore.qubit) -> !sobs.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit {
            ^bb0(%0: !qcore.qubit, %1: !qcore.qubit, %2 : !qcore.qubit):
            %3 = sobs.dec_observable(%0, %1, %2) -> !sobs.observable
            qstruct.yield %3, %0, %1, %2: !sobs.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit
        }
        %log = log_asm.measure<Z> (%p0_1 : !log_asm.patch.unrot_planar<size=(2, 2),
            location=(0.0, 0.0), orient=h_z>) -> i1
    }
    """
    module = parse_ir(ir, xdsl_context)
    walker = PatternRewriteWalker(_MeasureOpPattern(True))
    walker.rewrite_module(module)
    # All operations are applied on unrotated patches, they should be kept intact.
    measure_ops = [op for op in module.walk() if isinstance(op, MeasureOp)]
    assert len(measure_ops) == 1
    assert isinstance(measure_ops[0].patch.type, UnrotatedPlanarPatchType)


def test_no_observable_to_find(xdsl_context: Context) -> None:
    ir = """
    builtin.module {
        %patch = log_asm.patch_dec ->
            !log_asm.patch.rot_planar<size=(2, 2), location=(0, 0), orient=h_z>
        %p0 = log_asm.prepare<Z>
            (%patch : !log_asm.patch.rot_planar<size=(2, 2), location=(0, 0), orient=h_z>)
        %p0_1 = log_asm.meas_stab<2>
            (%p0 : !log_asm.patch.rot_planar<size=(2, 2), location=(0.0, 0.0), orient=h_z>)
        %log = log_asm.measure<Z> (%p0_1 : !log_asm.patch.rot_planar<size=(2, 2),
            location=(0.0, 0.0), orient=h_z>) -> i1
    }
    """
    module = parse_ir(ir, xdsl_context)
    walker = PatternRewriteWalker(_MeasureOpPattern(True))
    msg = re.escape("Could not find a suitable 'sobs.locate_observable' operation.")
    with pytest.raises(CompilerPassCheckError, match=msg):
        walker.rewrite_module(module)
