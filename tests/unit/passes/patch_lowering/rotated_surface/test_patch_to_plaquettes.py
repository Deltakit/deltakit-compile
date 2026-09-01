"""Unit tests for the PatchToPlaquettes pass."""

import re

import pytest
from xdsl.builder import Builder
from xdsl.dialects.builtin import ArrayAttr, IntAttr, ModuleOp, NoneAttr
from xdsl.pattern_rewriter import PatternRewriteWalker

from deltakit_compile.dialects.logical_assembly import (
    MeasStabOp,
    OrientationEnum,
    PatchDeclarationOp,
    PlacementAttr,
    RotatedPlanarPatchType,
)
from deltakit_compile.dialects.plaquette import (
    RotatedSurfaceCodePlaquetteShapeTypeAttr,
    RotatedSurfaceCodePlaquetteShapeTypeEnum,
)
from deltakit_compile.exceptions import PatchLoweringError
from deltakit_compile.passes.patch_lowering.rotated_surface._constants import (
    PLAQUETTE_SHAPE_TYPE_ATTRIBUTE_KEY,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.patch_to_plaquettes import (
    _MeasStabiliserPattern,
)
from deltakit_compile.shared.patch.rotated_planar._stabilisers import _XX, _XXXX


def make_size(x: int, y: int) -> ArrayAttr[IntAttr]:
    return ArrayAttr([IntAttr(x), IntAttr(y)])


@pytest.mark.parametrize(("width", "height"), [(2, 2), (1, 2), (2, 1), (4, 3), (5, 5)])
def test_build_plaquette_blocks_returns_correct_number(width: int, height: int) -> None:
    patch_type = RotatedPlanarPatchType(
        make_size(width, height), PlacementAttr((0, 0), OrientationEnum.VERTICAL_Z)
    )
    num_plaquettes = width * height - 1
    blocks = _MeasStabiliserPattern._build_plaquette_blocks(patch_type, True)
    assert len(blocks) == num_plaquettes


@pytest.mark.parametrize(
    ("data_qubit_indices", "expected_shape"),
    [
        ((0, 1), RotatedSurfaceCodePlaquetteShapeTypeEnum.BOTTOM),
        ((0, 2), RotatedSurfaceCodePlaquetteShapeTypeEnum.RIGHT),
        ((1, 3), RotatedSurfaceCodePlaquetteShapeTypeEnum.LEFT),
        ((2, 3), RotatedSurfaceCodePlaquetteShapeTypeEnum.TOP),
        ((0, 1, 2, 3), RotatedSurfaceCodePlaquetteShapeTypeEnum.SQUARE),
    ],
)
def test_build_block_with_plaquette_annotates_shape(
    data_qubit_indices: tuple[int, ...],
    expected_shape: RotatedSurfaceCodePlaquetteShapeTypeEnum,
) -> None:
    origin = (0.5, 0.5)
    # Coordinates for a 1x1 patch: 4 data qubits (Z-ordered) + 1 ancilla.
    coordinates = [
        (0.5, 1.5),  # Z-order index 0 (top-left)
        (1.5, 1.5),  # Z-order index 1 (top-right)
        (0.5, 0.5),  # Z-order index 2 (bottom-left)
        (1.5, 0.5),  # Z-order index 3 (bottom-right)
        (1.0, 1.0),  # ancilla (centre)
    ]
    stabiliser = _XX if len(data_qubit_indices) == 2 else _XXXX
    block = _MeasStabiliserPattern._build_block_with_plaquette(
        stabiliser, len(coordinates), origin, data_qubit_indices, coordinates
    )
    plaquette_op = next(iter(block.ops))
    assert plaquette_op.attributes[
        PLAQUETTE_SHAPE_TYPE_ATTRIBUTE_KEY
    ] == RotatedSurfaceCodePlaquetteShapeTypeAttr(expected_shape)


@pytest.mark.parametrize(
    "data_qubit_indices",
    [
        (0,),
        (1, 2),  # diagonal pair: not a valid boundary plaquette
        (0, 3),  # the other diagonal
        (0, 1, 2),  # weight-3 is not supported yet.
        (1, 2, 3),  # weight-3
    ],
)
def test_build_block_with_plaquette_raises_on_unsupported_indices(
    data_qubit_indices: tuple[int, ...],
) -> None:
    origin = (0.5, 0.5)
    coordinates = [
        (0.5, 1.5),
        (1.5, 1.5),
        (0.5, 0.5),
        (1.5, 0.5),
        (1.0, 1.0),  # ancilla
    ]
    stabiliser = _XX
    with pytest.raises(NotImplementedError, match="Unsupported plaquette applied on data qubits"):
        _MeasStabiliserPattern._build_block_with_plaquette(
            stabiliser, len(coordinates), origin, data_qubit_indices, coordinates
        )


@pytest.mark.parametrize(
    "data_qubit_indices",
    [(5,), (0, 1, 2, 3, 4, 5), (349850,)],
)
def test_build_block_with_plaquette_raises_on_invalid_indices(
    data_qubit_indices: tuple[int, ...],
) -> None:
    origin = (0.5, 0.5)
    coordinates = [
        (0.5, 1.5),
        (1.5, 1.5),
        (0.5, 0.5),
        (1.5, 0.5),
        (1.0, 1.0),  # ancilla
    ]
    stabiliser = _XX
    msg = r"Cannot use data qubit with index \d+\. The maximum supported index is \d+\."
    with pytest.raises(PatchLoweringError, match=msg):
        _MeasStabiliserPattern._build_block_with_plaquette(
            stabiliser, len(coordinates), origin, data_qubit_indices, coordinates
        )


def test_meas_stab_without_placement_raises_runtime_error() -> None:
    @ModuleOp
    @Builder.implicit_region
    def module():
        patch = PatchDeclarationOp(RotatedPlanarPatchType(make_size(3, 3), NoneAttr())).res
        MeasStabOp(patch, 1)

    msg = re.escape("Patches without placement data are not supported.")
    with pytest.raises(PatchLoweringError, match=msg):
        PatternRewriteWalker(_MeasStabiliserPattern()).rewrite_module(module)
