"""Tests for the Logical Assembly xDSL dialect"""

import re
from collections.abc import Sequence
from typing import cast

import pytest
from xdsl.context import Context
from xdsl.dialects import test
from xdsl.dialects.builtin import IntAttr, NoneAttr, i1
from xdsl.ir import OpResult
from xdsl.utils.exceptions import VerifyException

from deltakit_compile.dialects.logical_assembly import (
    BasePatch,
    CastOp,
    GateTypeAttr,
    GateTypeEnum,
    GrowOp,
    MeasStabOp,
    MeasureOp,
    MoveOp,
    MultiPauliMeasOp,
    OrientationEnum,
    PatchDeclarationOp,
    PlacementAttr,
    PrepareOp,
    RotatedPlanarPatchType,
    RotateOp,
    ShrinkOp,
    StepOp,
    SurfaceCodeBasePatch,
    TransversalGateOp,
    UnrotatedPlanarPatchType,
)
from deltakit_compile.dialects.qcore import PauliAttr, QubitRegType
from deltakit_compile.shared.patch.bounding_box import BoundingBox
from tests.unit.dialects.conftest import check_asm_roundtrip


@pytest.mark.parametrize(
    "program",
    [
        "%lq = log_asm.patch_dec -> "
        "!log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=v_z>",
        "%lq = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5, 5)>",
        "%lq = log_asm.patch_dec -> "
        "!log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=v_z>\n "
        "%lq1 = log_asm.prepare<Z> "
        "(%lq : !log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=v_z>)",
        "%lq = log_asm.patch_dec -> "
        "!log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=v_z>\n "
        "%lq1 = log_asm.meas_stab<20> "
        "(%lq : !log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=v_z>)",
        "%lq = log_asm.patch_dec -> "
        "!log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=v_z>\n "
        "%m_z = log_asm.measure<Z> "
        "(%lq : !log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=v_z>) -> i1",
        "%lq0 = log_asm.patch_dec -> "
        "!log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=v_z>\n "
        "%lq1 = log_asm.patch_dec -> "
        "!log_asm.patch.rot_planar<size=(5, 5), location=(11.0, 1.0), orient=v_z>\n "
        "%bridge = log_asm.patch_dec -> "
        "!log_asm.patch.rot_planar<size=(5, 5), location=(6.0, 1.0), orient=v_z>\n "
        "%r_zz, %lq01, %lq11 = log_asm.multi_pauli_meas<5, (Z, Z)> "
        "(%lq0, %lq1 : !log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=v_z>, "
        "!log_asm.patch.rot_planar<size=(5, 5), location=(11.0, 1.0), orient=v_z>) "
        "(%bridge : !log_asm.patch.rot_planar<size=(5, 5), location=(6.0, 1.0), orient=v_z>) -> i1",
        (
            "%lq = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5, 5), "
            "location=(1.0, 1.0), orient=v_z>\n "
            "%lq_h = log_asm.transversal<H> ("
            "%lq : !log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=v_z>) "
            "-> !log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=h_z>"
        ),
        (
            "%lq = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5, 5), "
            "location=(1.0, 1.0), orient=h_z>\n "
            "%lq_rot = log_asm.rotate<5> ("
            "%lq : !log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=h_z>) "
            "-> !log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 6.0), orient=v_z>"
        ),
        (
            "%lq = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5, 5), "
            "location=(1.0, 1.0), orient=v_z>\n "
            "%br = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 5), "
            "location=(6.0, 1.0), orient=v_z>\n "
            "%lq_m = log_asm.move<10> "
            "(%lq : !log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=v_z>) "
            "(%br : !log_asm.patch.rot_planar<size=(3, 5), location=(6.0, 1.0), orient=v_z>) "
            "-> !log_asm.patch.rot_planar<size=(5, 5), location=(9.0, 1.0), orient=v_z>"
        ),
        (
            "%lq = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5, 5), "
            "location=(1.0, 1.0), orient=v_z>\n "
            "%lq_g = log_asm.grow<10> "
            "(%lq : !log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=v_z>) "
            "-> !log_asm.patch.rot_planar<size=(7, 7), location=(0.0, 0.0), orient=v_z>"
        ),
        (
            "%lq = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5, 5), "
            "location=(1.0, 1.0), orient=v_z>\n "
            "%lq_s = log_asm.shrink<5> ("
            "%lq : !log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=v_z>) "
            "-> !log_asm.patch.rot_planar<size=(3, 3), location=(1.0, 1.0), orient=v_z>"
        ),
        (
            "%lq = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5, 5), "
            "location=(1.0, 1.0), orient=v_z>\n "
            "%lq_s = log_asm.step("
            "%lq : !log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=v_z>) "
            "-> !log_asm.patch.rot_planar<size=(5, 5), location=(2.0, 1.0), orient=v_z>"
        ),
    ],
)
def test_asm_roundtrip(program: str, xdsl_context: Context):
    """Test that operations can be parsed and printed to/from xDSL assembly representation."""
    check_asm_roundtrip(program, xdsl_context)
    # TODO move to filecheck test


@pytest.mark.parametrize(
    ("orientation", "location", "size", "error_msg"),
    [
        (
            OrientationEnum.VERTICAL_Z,
            [1],
            [3, 5],
            "Patch location must be a 2D coordinate stored as an ArrayAttr of 2 FloatAttrs.",
        ),
        (
            OrientationEnum.VERTICAL_Z,
            [1, 2, 3],
            [3, 5],
            "Patch location must be a 2D coordinate stored as an ArrayAttr of 2 FloatAttrs.",
        ),
        (
            OrientationEnum.VERTICAL_Z,
            [1, 3],
            [3],
            "Patch size must be 2D stored as an ArrayAttr of 2 positive value IntAttrs.",
        ),
        (
            OrientationEnum.VERTICAL_Z,
            [3, 1],
            [0, 0],
            "Patch size must be 2D stored as an ArrayAttr of 2 positive value IntAttrs.",
        ),
        (
            OrientationEnum.VERTICAL_Z,
            [1, 1],
            [1, -1],
            "Patch size must be 2D stored as an ArrayAttr of 2 positive value IntAttrs.",
        ),
        (
            OrientationEnum.VERTICAL_Z,
            [1, 1],
            [3, 3, 3],
            "Patch size must be 2D stored as an ArrayAttr of 2 positive value IntAttrs.",
        ),
    ],
)
@pytest.mark.parametrize("patch_class", [RotatedPlanarPatchType, UnrotatedPlanarPatchType])
def test_verify_surface_code_patches(
    patch_class: type[SurfaceCodeBasePatch],
    orientation: OrientationEnum | None,
    location: Sequence[int] | None,
    size: Sequence[int],
    error_msg: str,
):
    """Test that SurfaceCodeBasePatches and PlacementAttr raise exceptions for invalid patch
    parameters."""
    # Suppress PT012 - We intentionally allow multiple statements in this pytest.raises block
    # because both PlacementAttr and patch_class may raise VerifyException, and we want to
    # check for either.
    with pytest.raises(VerifyException, match=error_msg):  # noqa: PT012
        placement = (
            PlacementAttr(location, orientation)
            if (orientation is not None and location is not None)
            else None
        )
        patch_class(size, placement)  # type: ignore[arg-type]
        # Ignore the type to check runtime behaviour invalid arguments.


@pytest.mark.parametrize(
    ("size", "location", "orientation"),
    [
        ((1, 2), [3, 4], OrientationEnum.HORIZONTAL_Z),
        ((100, 200), [-3, -4], OrientationEnum.HORIZONTAL_Z),
        ((3, 3), [20, -4], OrientationEnum.VERTICAL_Z),
        ((3, 3), None, None),
    ],
)
@pytest.mark.parametrize("patch_class", [RotatedPlanarPatchType, UnrotatedPlanarPatchType])
def test_surface_codes_patches(
    patch_class: type[SurfaceCodeBasePatch],
    orientation: OrientationEnum | None,
    location: Sequence[int] | None,
    size: tuple[int, int],
):
    """Test constructor and helper methods work for patch types (subclasses of
    SurfaceCodeBasePatch) and PlacementAttr."""
    placement = (
        PlacementAttr(location, orientation)
        if (orientation is not None and location is not None)
        else None
    )
    patch_type = patch_class(size, placement)
    assert isinstance(patch_type, SurfaceCodeBasePatch)
    assert [i.data for i in patch_type.size] == list(size)
    assert patch_type.placement == (placement or NoneAttr())
    assert patch_type.orientation_data == orientation

    new_placement = PlacementAttr([0, -1], OrientationEnum.VERTICAL_Z)
    replaced_patch_type = patch_type.with_new_placement(new_placement)
    assert replaced_patch_type.size == patch_type.size
    assert replaced_patch_type != patch_type
    assert replaced_patch_type.placement == new_placement
    assert patch_type.placement != new_placement
    assert replaced_patch_type.orientation_data == OrientationEnum.VERTICAL_Z

    flipped_patch_type = patch_type.with_flipped_observable()
    flipped_placement = (
        PlacementAttr(location, orientation.rotate())
        if (orientation is not None and location is not None)
        else NoneAttr()
    )
    assert flipped_patch_type.size == patch_type.size
    assert flipped_patch_type.placement == flipped_placement
    assert isinstance(flipped_placement, NoneAttr) or patch_type.placement != flipped_placement
    assert flipped_patch_type.orientation_data == (
        orientation.rotate() if orientation is not None else None
    )

    same_patch_type = patch_type.with_offset_size((0, 0))
    assert same_patch_type == patch_type
    bigger_patch_type = patch_type.with_offset_size((1, 1))
    assert bigger_patch_type.size_data == tuple(s + 1 for s in patch_type.size_data)
    smaller_patch_type = patch_type.with_offset_size((0, -1))
    w, h = patch_type.size_data
    assert smaller_patch_type.size_data == (w, h - 1)
    assert smaller_patch_type.orientation_data == orientation

    with pytest.raises(
        RuntimeError,
        match=re.escape("Cannot offset a 2-dimensional placement with a 1-dimensional offset."),
    ):
        patch_type.with_offset_size((1,))


@pytest.mark.parametrize(
    ("size", "location", "expected_bbox"),
    [
        ((1, 2), [3, 4], BoundingBox(3, 4, 4, 6)),
        ((100, 200), [-3, -4], BoundingBox(-3, -4, 97, 196)),
        ((3, 3), [20, -4], BoundingBox(20, -4, 23, -1)),
        ((3, 3), None, None),
    ],
)
@pytest.mark.parametrize("patch_class", [RotatedPlanarPatchType, UnrotatedPlanarPatchType])
def test_surface_codes_patches_bounding_box(
    patch_class: type[SurfaceCodeBasePatch],
    size: tuple[int, int],
    location: Sequence[int] | None,
    expected_bbox: tuple[tuple[float, float], tuple[float, float]] | None,
):
    placement = (
        PlacementAttr(location, OrientationEnum.VERTICAL_Z) if (location is not None) else None
    )
    patch_type = patch_class(size, placement)
    bbox = patch_type.bounding_box
    assert bbox == expected_bbox


@pytest.mark.parametrize(
    ("size", "location", "orientation"),
    [
        ((1, 2), [3, 4], OrientationEnum.HORIZONTAL_Z),
        ((100, 200), [-3, -4], OrientationEnum.HORIZONTAL_Z),
        ((3, 3), [20, -4], OrientationEnum.VERTICAL_Z),
        ((3, 3), None, None),
    ],
)
@pytest.mark.parametrize("patch_class", [RotatedPlanarPatchType, UnrotatedPlanarPatchType])
def test_patch_dec_op_init(
    patch_class: type[SurfaceCodeBasePatch],
    orientation: OrientationEnum | None,
    location: Sequence[int] | None,
    size: tuple[int, int],
):
    """Test PatchDeclarationOp constructor."""
    placement = (
        PlacementAttr(location, orientation)
        if (orientation is not None) and (location is not None)
        else None
    )
    patch_type = patch_class(size, placement)

    op = PatchDeclarationOp(patch_type)
    assert isinstance(op.res.type, patch_class)
    assert op.res.type.size_data == tuple(i.data for i in patch_type.size)
    if not isinstance(patch_type.placement, NoneAttr):
        assert op.res.type.placement_data == tuple(
            i.value.data for i in patch_type.placement.location
        )
    assert op.res.type == patch_type


@pytest.mark.parametrize(
    ("size", "location", "orientation"),
    [
        ((6, 4), [3, 4], OrientationEnum.HORIZONTAL_Z),
        ((100, 200), [-3, -4], OrientationEnum.HORIZONTAL_Z),
        ((3, 3), [20, -4], OrientationEnum.VERTICAL_Z),
    ],
)
@pytest.mark.parametrize("patch_class", [RotatedPlanarPatchType, UnrotatedPlanarPatchType])
def test_movement_op_init_methods(
    patch_class: type[SurfaceCodeBasePatch],
    orientation: OrientationEnum,
    location: Sequence[int],
    size: tuple[int, int],
):
    """Test op constructors for ops that do patch movement/resizing."""
    placement = PlacementAttr(location, orientation)
    patch_type = patch_class(size, placement)

    patch = cast(OpResult[SurfaceCodeBasePatch], test.TestOp(result_types=[patch_type]).res[0])
    new_location = tuple(
        a.value.data + b
        for a, b in zip(placement.location, [0, patch_type.size.data[1].data], strict=True)
    )
    RotateOp(
        patch,
        10,
        patch_type.with_new_placement(PlacementAttr(new_location, placement.orientation.rotate())),
    )

    MoveOp(
        patch,
        10,
        [],
        patch_type.with_new_placement(PlacementAttr(new_location, placement.orientation)),
    )

    GrowOp(
        patch,
        10,
        patch_class((size[0] + 2, size[1] + 2), placement),
    )

    ShrinkOp(
        patch,
        10,
        patch_class((size[0] - 2, size[1] - 2), placement),
    )

    new_location = tuple(a.value.data + b for a, b in zip(placement.location, [1, 0], strict=True))
    StepOp(
        patch,
        patch_type.with_new_placement(PlacementAttr(new_location, placement.orientation)),
    )


@pytest.mark.parametrize(
    ("size", "location", "orientation"),
    [
        ((6, 4), [3, 4], OrientationEnum.HORIZONTAL_Z),
        ((100, 200), [-3, -4], OrientationEnum.HORIZONTAL_Z),
        ((3, 3), [20, -4], OrientationEnum.VERTICAL_Z),
        ((3, 3), None, None),
    ],
)
@pytest.mark.parametrize("patch_class", [RotatedPlanarPatchType, UnrotatedPlanarPatchType])
def test_quantum_op_init_methods(
    patch_class: type[SurfaceCodeBasePatch],
    orientation: OrientationEnum | None,
    location: Sequence[int] | None,
    size: tuple[int, int],
):
    """Test op constructors for ops that do specific quantum operations."""
    placement = (
        PlacementAttr(location, orientation)
        if (orientation is not None and location is not None)
        else None
    )
    patch_type = patch_class(size, placement)

    patch = test.TestOp(result_types=[patch_type]).res[0]

    for basis in (PauliAttr.X(), PauliAttr.Y(), PauliAttr.Z()):
        prep_op = PrepareOp(patch, basis)
        assert prep_op.res.type.size_data == tuple(i.data for i in patch_type.size)
        if not isinstance(patch_type.placement, NoneAttr):
            assert prep_op.res.type.placement_data == tuple(
                i.value.data for i in patch_type.placement.location
            )
        else:
            assert prep_op.res.type.placement_data is None
        assert prep_op.basis == basis
        measure_op = MeasureOp(patch, basis)
        assert isinstance(measure_op.patch.type, patch_class)
        assert measure_op.patch.type.size_data == tuple(i.data for i in patch_type.size)
        if not isinstance(patch_type.placement, NoneAttr):
            assert measure_op.patch.type.placement_data == tuple(
                i.value.data for i in patch_type.placement.location
            )
        else:
            assert measure_op.patch.type.placement_data is None
        assert measure_op.measurement.type == i1
        assert measure_op.basis == basis

    for rounds in (0, 10, 20):
        meas_stab_op = MeasStabOp(patch, rounds)
        assert isinstance(meas_stab_op.patch.type, patch_class)
        assert meas_stab_op.patch.type.size_data == tuple(i.data for i in patch_type.size)
        if not isinstance(patch_type.placement, NoneAttr):
            assert meas_stab_op.patch.type.placement_data == tuple(
                i.value.data for i in patch_type.placement.location
            )
        else:
            assert meas_stab_op.patch.type.placement_data is None

        assert meas_stab_op.res.type == patch.type
        assert meas_stab_op.min_rounds.data == rounds

    for gate in (GateTypeEnum.H, GateTypeEnum.X, GateTypeEnum.Z):
        gate_attr = GateTypeAttr(gate)
        res_type = patch_type
        if gate == GateTypeEnum.H and not isinstance(res_type.placement, NoneAttr):
            res_type = res_type.with_new_placement(
                PlacementAttr(res_type.placement.location, res_type.placement.orientation.rotate())
            )
        transversal_op = TransversalGateOp(patch, gate, res_type)
        assert transversal_op.is_structurally_equivalent(
            TransversalGateOp([patch], gate, [res_type])
        )
        assert len(transversal_op.res) == 1
        assert transversal_op.res.types[0] == res_type
        assert transversal_op.gate_type == gate_attr


@pytest.mark.parametrize("patch_class", [RotatedPlanarPatchType, UnrotatedPlanarPatchType])
@pytest.mark.parametrize("gate", [GateTypeEnum.H, GateTypeEnum.X, GateTypeEnum.Z])
def test_transversal_op_verify_location(
    patch_class: type[SurfaceCodeBasePatch],
    gate: GateTypeEnum,
):
    """Tests TransversalOps requirement that the location does not change.
    Orientation is not checked."""
    patch_type = patch_class((5, 5), PlacementAttr([10, 10], OrientationEnum.HORIZONTAL_Z))
    res_type = patch_class((5, 5), PlacementAttr([10, 11], OrientationEnum.HORIZONTAL_Z))

    patch = test.TestOp(result_types=[patch_type]).res[0]

    transversal_op = TransversalGateOp(patch, gate, res_type)

    with pytest.raises(
        VerifyException,
        match=re.escape(
            "Operand patches cannot move during a log_asm.transversal operation. "
            "Operand patch 0 has location: (10.0, 10.0), but has location (10.0, 11.0) in the "
            "result."
        ),
    ):
        transversal_op.verify()


@pytest.mark.parametrize("patch_class", [RotatedPlanarPatchType, UnrotatedPlanarPatchType])
def test_multi_pauli_measure_init(
    patch_class: type[SurfaceCodeBasePatch],
):
    """Tests that MultiPauliMeasOp's init method works with correct arguments."""

    patch_types = [
        patch_class((3, 3), PlacementAttr([0, 0], OrientationEnum.HORIZONTAL_Z)),
        patch_class((3, 3), PlacementAttr([4, 4], OrientationEnum.HORIZONTAL_Z)),
        patch_class((3, 3), PlacementAttr([8, 0], OrientationEnum.VERTICAL_Z)),
    ]

    bridge_types = [
        patch_class((3, 3), PlacementAttr([4, 0], OrientationEnum.HORIZONTAL_Z)),
        patch_class((1, 3), PlacementAttr([3, 0], OrientationEnum.HORIZONTAL_Z)),
        patch_class((3, 1), PlacementAttr([4, 3], OrientationEnum.HORIZONTAL_Z)),
        patch_class((1, 3), PlacementAttr([7, 0], OrientationEnum.HORIZONTAL_Z)),
    ]
    patches = test.TestOp(result_types=patch_types).res
    bridges = test.TestOp(result_types=bridge_types).res

    op = MultiPauliMeasOp(15, [PauliAttr.Z(), PauliAttr.X(), PauliAttr.X()], patches, bridges)
    assert tuple(op.res.types) == tuple(patch_types)
    assert tuple(op.get_logical_patch_types()) == tuple(patch_types)
    assert tuple(op.get_bridge_patch_types()) == tuple(bridge_types)
    assert op.measurement.type == i1


@pytest.mark.parametrize(
    ("out_patch_class", "orientation", "location", "size", "error_msg"),
    [
        (
            RotatedPlanarPatchType,
            OrientationEnum.VERTICAL_Z,
            [1, 1],
            (3, 3),
            re.escape(
                "log_asm.rotate expects the orientation of the input and output to be different"
            ),
        ),
        (
            UnrotatedPlanarPatchType,
            OrientationEnum.HORIZONTAL_Z,
            [1, 1],
            (3, 3),
            re.escape(
                "An attribute of base type 'log_asm.patch.rot_planar' was expected from variable "
                "'PatchType', but got !log_asm.patch.unrot_planar"
            ),
        ),
    ],
)
def test_verify_rotate(
    out_patch_class: type[SurfaceCodeBasePatch],
    orientation: OrientationEnum,
    location: Sequence[int],
    size: tuple[int, int],
    error_msg: str,
):
    """Test that RotateOp.verify() raises exceptions for invalid patch parameters."""
    in_patch_type = RotatedPlanarPatchType(
        (3, 3), PlacementAttr((1, 1), OrientationEnum.VERTICAL_Z)
    )
    in_patch_ssa = test.TestOp(result_types=[in_patch_type]).res[0]

    out_patch_type = out_patch_class(size, PlacementAttr(location, orientation))

    with pytest.raises(VerifyException, match=error_msg):
        RotateOp.create(
            operands=[in_patch_ssa],
            result_types=[out_patch_type],
            properties={"rounds": IntAttr(100)},
        ).verify()


@pytest.mark.parametrize(
    ("out_patch_class", "orientation", "location", "size", "error_msg"),
    [
        (
            UnrotatedPlanarPatchType,
            OrientationEnum.VERTICAL_Z,
            [1, 1],
            [3, 3],
            re.escape(
                "An attribute of base type 'log_asm.patch.rot_planar' was expected from variable "
                "'PatchType', but got !log_asm.patch.unrot_planar"
            ),
        )
    ],
)
def test_verify_resize_ops(
    out_patch_class: type[SurfaceCodeBasePatch],
    orientation: OrientationEnum,
    location: Sequence[int],
    size: tuple[int, int],
    error_msg: str,
):
    """Test that children of BaseResizeOp raises exceptions for shared invalid parameters."""
    in_patch_ssa = test.TestOp(
        result_types=[
            RotatedPlanarPatchType((3, 3), PlacementAttr((1, 1), OrientationEnum.VERTICAL_Z))
        ]
    ).res[0]
    br_patch_ssa = test.TestOp(
        result_types=[
            RotatedPlanarPatchType((3, 3), PlacementAttr((5, 1), OrientationEnum.VERTICAL_Z))
        ]
    ).res[0]

    res_type = out_patch_class(
        size=size,
        placement=PlacementAttr(location, orientation),
    )
    with pytest.raises(VerifyException, match=error_msg):
        MoveOp.create(
            operands=[in_patch_ssa, br_patch_ssa],
            result_types=[res_type],
        ).verify()

    with pytest.raises(VerifyException, match=error_msg):
        GrowOp.create(
            operands=[in_patch_ssa],
            result_types=[res_type],
            properties={"rounds": IntAttr(5)},
        ).verify()

    with pytest.raises(VerifyException, match=error_msg):
        ShrinkOp.create(
            operands=[in_patch_ssa],
            result_types=[res_type],
            properties={"rounds": IntAttr(5)},
        ).verify()


def test_verify_move_size():
    """Test that a move with a change in patch size raises an exception."""
    in_patch_ssa = test.TestOp(
        result_types=[
            RotatedPlanarPatchType((3, 3), PlacementAttr((1, 1), OrientationEnum.VERTICAL_Z))
        ]
    ).res[0]
    br_patch_ssa = test.TestOp(
        result_types=[
            RotatedPlanarPatchType((3, 3), PlacementAttr((5, 1), OrientationEnum.VERTICAL_Z))
        ]
    ).res[0]

    out_patch = RotatedPlanarPatchType(
        size=(5, 5),
        placement=PlacementAttr(
            orientation=OrientationEnum.VERTICAL_Z,
            location=[9, 1],
        ),
    )

    with pytest.raises(
        VerifyException,
        match=re.escape(
            "The size of the patch does not meet the requirements.\n"
            "Underlying verification failure: "
            "attribute [#builtin.int<3>, #builtin.int<3>] expected from variable 'PatchSize', "
            "but got [#builtin.int<5>, #builtin.int<5>]"
        ),
    ):
        MoveOp.create(
            operands=[in_patch_ssa, br_patch_ssa],
            result_types=[out_patch],
        ).verify()


@pytest.mark.parametrize(
    ("out_patch_class", "orientation", "location", "size", "error_msg"),
    [
        (
            UnrotatedPlanarPatchType,
            OrientationEnum.VERTICAL_Z,
            [1, 1],
            (3, 3),
            re.escape(
                "An attribute of base type 'log_asm.patch.rot_planar' was expected from variable "
                "'PatchType', but got !log_asm.patch.unrot_planar"
            ),
        ),
        (
            RotatedPlanarPatchType,
            OrientationEnum.HORIZONTAL_Z,
            [1, 1],
            (3, 3),
            re.escape(
                "The orientation does not meet the requirements.\n"
                "Underlying verification failure: "
                "attribute #log_asm.orientation<v_z> expected from variable 'PatchOrientation', "
                "but got #log_asm.orientation<h_z>"
            ),
        ),
        (
            RotatedPlanarPatchType,
            OrientationEnum.VERTICAL_Z,
            [1, 1],
            (5, 5),
            re.escape(
                "The size of the patch does not meet the requirements.\n"
                "Underlying verification failure: "
                "attribute [#builtin.int<3>, #builtin.int<3>] expected from variable 'PatchSize', "
                "but got [#builtin.int<5>, #builtin.int<5>]"
            ),
        ),
    ],
)
def test_verify_step(
    out_patch_class: type[SurfaceCodeBasePatch],
    orientation: OrientationEnum,
    location: Sequence[int],
    size: tuple[int, int],
    error_msg: str,
):
    """Test that StepOp.verify() raises exceptions for invalid patch parameters."""
    in_patch_ssa = test.TestOp(
        result_types=[
            RotatedPlanarPatchType((3, 3), PlacementAttr((1, 1), OrientationEnum.VERTICAL_Z))
        ]
    ).res[0]
    res_type = out_patch_class(
        size=size,
        placement=PlacementAttr(location, orientation),
    )
    with pytest.raises(VerifyException, match=error_msg):
        StepOp.create(
            operands=[in_patch_ssa],
            result_types=[res_type],
        ).verify()


@pytest.mark.parametrize(
    ("inp", "offset", "expected_output_or_error_msg"),
    [
        (
            PlacementAttr([0, 0], OrientationEnum.VERTICAL_Z),
            (0, 0),
            PlacementAttr([0, 0], OrientationEnum.VERTICAL_Z),
        ),
        (
            PlacementAttr([0, 0], OrientationEnum.VERTICAL_Z),
            (-1, 1),
            PlacementAttr([-1, 1], OrientationEnum.VERTICAL_Z),
        ),
        (
            PlacementAttr([0, 0], OrientationEnum.VERTICAL_Z),
            (-3,),
            "Cannot offset a 2-dimensional placement with a 1-dimensional offset.",
        ),
        (
            PlacementAttr([0, 0], OrientationEnum.VERTICAL_Z),
            (-3, 0, 3),
            "Cannot offset a 2-dimensional placement with a 3-dimensional offset.",
        ),
    ],
)
def test_placement_attr_with_offset(
    inp: PlacementAttr,
    offset: tuple[int, ...],
    expected_output_or_error_msg: PlacementAttr | str,
) -> None:
    if isinstance(expected_output_or_error_msg, str):
        with pytest.raises(RuntimeError, match=re.escape(expected_output_or_error_msg)):
            _ = inp.with_offset(offset)
    else:
        out = inp.with_offset(offset)
        assert out == expected_output_or_error_msg


def test_rotated_placement_attr() -> None:
    placement = PlacementAttr((0, 0), OrientationEnum.VERTICAL_Z)
    assert placement.orientation.data == OrientationEnum.VERTICAL_Z
    assert placement.rotated().orientation.data == OrientationEnum.HORIZONTAL_Z
    assert placement.rotated().rotated().orientation.data == OrientationEnum.VERTICAL_Z


@pytest.mark.parametrize(
    ("from_", "to", "error_msg"),
    [
        (RotatedPlanarPatchType((3, 3), NoneAttr()), QubitRegType(17), None),
        (RotatedPlanarPatchType((5, 5), NoneAttr()), QubitRegType(49), None),
        (RotatedPlanarPatchType((6, 6), NoneAttr()), QubitRegType(71), None),
        (RotatedPlanarPatchType((4, 5), NoneAttr()), QubitRegType(39), None),
        (
            RotatedPlanarPatchType((4, 5), NoneAttr()),
            RotatedPlanarPatchType((4, 5), NoneAttr()),
            None,
        ),
        (QubitRegType(42), QubitRegType(42), None),
        (
            RotatedPlanarPatchType((3, 3), NoneAttr()),
            QubitRegType(1),
            "Cannot cast from !log_asm.patch.rot_planar<size=(3, 3)> (17 qubits) to "
            "!qcore.qubit_reg<1> (1 qubits): the types represent a different number of qubits.",
        ),
        (
            QubitRegType(1),
            RotatedPlanarPatchType((3, 3), NoneAttr()),
            "Cannot cast from !qcore.qubit_reg<1> (1 qubits) to !log_asm.patch.rot_planar"
            "<size=(3, 3)> (17 qubits): the types represent a different number of qubits.",
        ),
    ],
)
def test_cast_op_verify(
    from_: BasePatch | QubitRegType, to: BasePatch | QubitRegType, error_msg: str | None
) -> None:
    in_ssa = test.TestOp(result_types=[from_]).res[0]
    cast_op = CastOp(in_ssa, to)
    if error_msg is not None:
        with pytest.raises(VerifyException, match=re.escape(error_msg)):
            cast_op.verify()
    else:
        cast_op.verify()
