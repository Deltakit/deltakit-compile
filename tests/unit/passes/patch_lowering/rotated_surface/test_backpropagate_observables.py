"""Tests for the BackpropagateObservables pass."""

import pytest
from xdsl.builder import Builder
from xdsl.context import Context
from xdsl.dialects.builtin import ArrayAttr, IntAttr, ModuleOp, NoneAttr
from xdsl.pattern_rewriter import PatternRewriteWalker

from deltakit_compile.dialects import logical_assembly as log_asm
from deltakit_compile.dialects import qcore
from deltakit_compile.dialects.sobs import DecUnplacedObservableOp, LocateUnplacedObservableOp
from deltakit_compile.exceptions import CompilerPassCheckError
from deltakit_compile.passes.patch_lowering.rotated_surface.backpropagate_observables import (
    BackpropagateObservables,
    _MeasureOpPattern,
    _MeasureStabiliserOpPattern,
)


def build_memory_circuit(distance: int) -> ModuleOp:
    @ModuleOp
    @Builder.implicit_region
    def module():
        p0 = log_asm.PatchDeclarationOp(
            log_asm.RotatedPlanarPatchType(
                ArrayAttr([IntAttr(distance), IntAttr(distance)]),
                NoneAttr(),
            )
        ).res
        p1 = log_asm.PrepareOp(p0, qcore.PauliAttr.Z()).res
        p2 = log_asm.MeasStabOp(p1, distance).res
        log_asm.MeasureOp(p2, qcore.PauliAttr.Z())

    return module


def build_annotated_meas_stab_circuit(distance: int) -> ModuleOp:
    @ModuleOp
    @Builder.implicit_region
    def module():
        p0 = log_asm.PatchDeclarationOp(
            log_asm.RotatedPlanarPatchType(
                ArrayAttr([IntAttr(distance), IntAttr(distance)]),
                NoneAttr(),
            )
        ).res
        p1 = log_asm.PrepareOp(p0, qcore.PauliAttr.Z()).res
        p2 = log_asm.MeasStabOp(p1, distance).res
        obs = DecUnplacedObservableOp().result
        LocateUnplacedObservableOp([qcore.PauliAttr.Z()], obs, [p2])

    return module


@pytest.mark.parametrize("module_op", [build_memory_circuit(3), build_memory_circuit(5)])
def test_measure_op_pattern_inserts_declaration_and_locate(module_op: ModuleOp) -> None:
    PatternRewriteWalker(_MeasureOpPattern()).rewrite_module(module_op)

    block_ops = list(module_op.body.block.ops)
    dec_ops = [op for op in block_ops if isinstance(op, DecUnplacedObservableOp)]
    locate_ops = [op for op in block_ops if isinstance(op, LocateUnplacedObservableOp)]
    measure_ops = [op for op in block_ops if isinstance(op, log_asm.MeasureOp)]

    assert len(dec_ops) == 1
    assert len(locate_ops) == 1
    assert len(measure_ops) == 1

    dec_op: DecUnplacedObservableOp = dec_ops[0]
    locate_op: LocateUnplacedObservableOp = locate_ops[0]
    measure_op = measure_ops[0]

    # New declaration is inserted at the start of the block.
    assert block_ops[0] is dec_op
    # New locate is inserted immediately before the measure.
    assert block_ops[block_ops.index(measure_op) - 1] is locate_op

    assert locate_op.obs == dec_op.result
    assert len(locate_op.patches) == 1
    assert locate_op.patches[0] == measure_op.patch
    assert locate_op.bases.data[0] == measure_op.basis


def test_measure_op_pattern_is_noop_when_patch_is_already_annotated() -> None:
    @ModuleOp
    @Builder.implicit_region
    def module():
        p0 = log_asm.PatchDeclarationOp(
            log_asm.RotatedPlanarPatchType(ArrayAttr([IntAttr(3), IntAttr(3)]), NoneAttr())
        ).res
        p1 = log_asm.PrepareOp(p0, qcore.PauliAttr.Z()).res
        p2 = log_asm.MeasStabOp(p1, 3).res
        obs = DecUnplacedObservableOp().result
        LocateUnplacedObservableOp([qcore.PauliAttr.Z()], obs, [p2])
        log_asm.MeasureOp(p2, qcore.PauliAttr.Z())

    before = str(module)
    PatternRewriteWalker(_MeasureOpPattern()).rewrite_module(module)

    assert str(module) == before


@pytest.mark.parametrize(
    "module_op", [build_annotated_meas_stab_circuit(3), build_annotated_meas_stab_circuit(5)]
)
def test_measure_stabiliser_op_pattern_backpropagates_to_input_patch(module_op: ModuleOp) -> None:
    PatternRewriteWalker(_MeasureStabiliserOpPattern()).rewrite_module(module_op)

    block_ops = list(module_op.body.block.ops)
    meas_stab_op = next(op for op in block_ops if isinstance(op, log_asm.MeasStabOp))
    locate_ops = [op for op in block_ops if isinstance(op, LocateUnplacedObservableOp)]

    assert len(locate_ops) == 2

    input_patch_locates = [
        lop for lop in locate_ops if len(lop.patches) == 1 and lop.patches[0] == meas_stab_op.patch
    ]
    output_patch_locates = [
        lop for lop in locate_ops if len(lop.patches) == 1 and lop.patches[0] == meas_stab_op.res
    ]

    assert len(input_patch_locates) == 1
    assert len(output_patch_locates) == 1

    input_locate = input_patch_locates[0]
    output_locate = output_patch_locates[0]

    # The output patch locate must now consume the result of the newly inserted input locate.
    assert output_locate.obs == input_locate.result
    # The inserted locate should preserve the observable basis.
    assert input_locate.bases == output_locate.bases


def test_measure_stabiliser_op_pattern_is_noop_when_input_is_already_annotated() -> None:
    @ModuleOp
    @Builder.implicit_region
    def module():
        p0 = log_asm.PatchDeclarationOp(
            log_asm.RotatedPlanarPatchType(ArrayAttr([IntAttr(3), IntAttr(3)]), NoneAttr())
        ).res
        obs = DecUnplacedObservableOp().result
        p1 = log_asm.PrepareOp(p0, qcore.PauliAttr.Z()).res
        obs1 = LocateUnplacedObservableOp([qcore.PauliAttr.Z()], obs, [p1]).result
        p2 = log_asm.MeasStabOp(p1, 3).res
        LocateUnplacedObservableOp([qcore.PauliAttr.Z()], obs1, [p2])

    before = str(module)
    PatternRewriteWalker(_MeasureStabiliserOpPattern()).rewrite_module(module)

    assert str(module) == before


@pytest.mark.parametrize(
    ("prepare_basis", "measure_basis"),
    [(qcore.PauliAttr.Z(), qcore.PauliAttr.X()), (qcore.PauliAttr.X(), qcore.PauliAttr.Z())],
)
def test_backpropagate_observables_raises_on_prepare_measure_basis_mismatch(
    prepare_basis: qcore.PauliAttr, measure_basis: qcore.PauliAttr
) -> None:
    @ModuleOp
    @Builder.implicit_region
    def module():
        p0 = log_asm.PatchDeclarationOp(
            log_asm.RotatedPlanarPatchType(ArrayAttr([IntAttr(3), IntAttr(3)]), NoneAttr())
        ).res
        p1 = log_asm.PrepareOp(p0, prepare_basis).res
        log_asm.MeasureOp(p1, measure_basis)

    expected_msg = (
        f"Expected an observable in the basis {prepare_basis} on the patch due to the "
        f"presence of a log_asm.prepare<{prepare_basis}> operation applied on that patch but "
        f"got an observable in the basis {measure_basis}."
    )

    with pytest.raises(CompilerPassCheckError, match=expected_msg):
        BackpropagateObservables().apply(Context(), module)


def test_backpropagate_observables_raises_on_unsupported_operation() -> None:
    @ModuleOp
    @Builder.implicit_region
    def unsupported_op_module():
        p0 = log_asm.PatchDeclarationOp(
            log_asm.RotatedPlanarPatchType(
                ArrayAttr([IntAttr(3), IntAttr(3)]),
                NoneAttr(),
            )
        ).res
        p1 = log_asm.PrepareOp(p0, qcore.PauliAttr.Z()).res
        # Unsupported operation below
        p1_1 = log_asm.TransversalGateOp(p1, log_asm.GateTypeEnum.H).res[0]
        p2 = log_asm.MeasStabOp(p1_1, 3).res
        log_asm.MeasureOp(p2, qcore.PauliAttr.Z())

    expected_msg = "Error while applying pattern: TransversalGateOp is not yet supported."
    with pytest.raises(NotImplementedError, match=expected_msg):
        BackpropagateObservables().apply(Context(), unsupported_op_module)
