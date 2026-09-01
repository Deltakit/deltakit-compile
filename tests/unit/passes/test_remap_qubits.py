"""Exception tests for remap qubits pass (functional testing done using filecheck)."""

import re

import pytest
from xdsl.builder import Builder
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp

from deltakit_compile.dialects.stim import (
    QubitAllocOp,
    QubitCoordsOp,
    QubitMappingAttr,
    ResetGateOp,
)
from deltakit_compile.exceptions import InvalidPassConfigurationException
from deltakit_compile.passes.remap_qubits import RemapQubits, RotationConfig


def test_qubit_alloc_with_no_coords(xdsl_context: Context):
    """Test that a qubit used without giving it coordinates throws an error."""

    @ModuleOp
    @Builder.implicit_region
    def module_op():
        qubit_0 = QubitAllocOp(0).results[0]
        QubitCoordsOp([qubit_0], QubitMappingAttr([0, 0]))
        qubit_1 = QubitAllocOp(1).results[0]
        ResetGateOp([qubit_0, qubit_1])

    with pytest.raises(ValueError, match="Qubit 1 used without assigning it QUBIT_COORDS"):
        RemapQubits([2, 2], {0: [2, 2], 1: [2, 3]}).apply(xdsl_context, module_op)


def test_invalid_qubit_coords(xdsl_context: Context):
    """Test that a qubit used with coordinates that aren't in the qubit_mapping throws an error."""

    @ModuleOp
    @Builder.implicit_region
    def module_op():
        qubit_0 = QubitAllocOp(0).results[0]
        QubitCoordsOp([qubit_0], QubitMappingAttr([0, 0]))

    with pytest.raises(
        ValueError,
        match="A qubit with coordinates \\(0, 0\\) is used in the program, but "
        "there is no qubit with those coordinates in the qubit_mapping",
    ):
        RemapQubits([0, 0], {0: [2, 2]}).apply(xdsl_context, module_op)


def test_dimension_mismatch(xdsl_context: Context):
    """Test that mismatched dimensions between the patch location and qubit coords throws an
    error."""

    @ModuleOp
    @Builder.implicit_region
    def module_op():
        qubit_0 = QubitAllocOp(0).results[0]
        QubitCoordsOp([qubit_0], QubitMappingAttr([0, 0]))
        qubit_1 = QubitAllocOp(1).results[0]
        QubitCoordsOp([qubit_1], QubitMappingAttr([1, 1]))
        ResetGateOp([qubit_0, qubit_1])

    msg = (
        r"qubit_coord_offset \(\[2, 2, 2\]\) length doesn't match a qubit's coordinates "
        r"\(\[0, 0\]\) length.*"
    )
    with pytest.raises(ValueError, match=msg):
        RemapQubits([2, 2, 2], {}).apply(xdsl_context, module_op)


def test_no_patch_location_in_config(xdsl_context: Context):
    """Test that no patch location in the config is supported."""

    @ModuleOp
    @Builder.implicit_region
    def module_op():
        qubit_0 = QubitAllocOp(0).results[0]
        QubitCoordsOp([qubit_0], QubitMappingAttr([0, 0]))
        ResetGateOp([qubit_0])

    RemapQubits(None, {1: [0, 0]}).apply(xdsl_context, module_op)
    alloc_op = module_op.body.block.first_op
    assert isinstance(alloc_op, QubitAllocOp)
    assert alloc_op.id.data == 1


def test_no_qubit_mapping_in_config(xdsl_context: Context):
    """Test that having no qubit_mapping throws an error."""

    @ModuleOp
    @Builder.implicit_region
    def module_op():
        qubit_0 = QubitAllocOp(0).results[0]
        QubitCoordsOp([qubit_0], QubitMappingAttr([0, 0]))
        ResetGateOp([qubit_0])

    with pytest.raises(InvalidPassConfigurationException) as ex_info:
        RemapQubits([2, 2], None).apply(xdsl_context, module_op)
    assert "Cannot apply 'remap-qubits' transformation unless 'qubit_mapping' is provided." in str(
        ex_info.value
    )


def test_1d_qubit_rotation(xdsl_context: Context):
    """Test that a qubit mapping with 1D coordinates throws an error when a rotation config is
    provided."""

    @ModuleOp
    @Builder.implicit_region
    def module_op():
        qubit_0 = QubitAllocOp(0).results[0]
        QubitCoordsOp([qubit_0], QubitMappingAttr([0]))

    rotation_config = (90, (0, 0))  # 90 degree rotation around the origin in 1D space

    msg = re.escape(
        "Cannot apply rotation to qubits with less than 2 dimensions. "
        "Qubit with coordinates [0] cannot be rotated."
    )

    # Error thrown when rotation config provided with 1D qubit coordinates
    with pytest.raises(ValueError, match=msg):
        RemapQubits([0], {0: [0]}, rotation_config).apply(xdsl_context, module_op)

    # Error not thrown when rotation config not provided with 1D qubit coordinates
    RemapQubits([2], {0: [2]}).apply(xdsl_context, module_op)


@pytest.mark.parametrize(
    (
        "initial_coords_0",
        "initial_coords_1",
        "offset",
        "angle",
        "expected_coords_0",
        "expected_coords_1",
    ),
    [
        # 2D coordinates: (1, 0) rotated 90° -> (0, 1), (0, 1) rotated 90° -> (-1, 0)
        ([1, 0], [0, 1], None, 90, [0, 1], [-1, 0]),
        # 3D coordinates: rotation only affects first 2 dims, third dim just gets offset
        ([1, 0, 10], [0, 1, 3], [2, 2, 3], 90, [2, 3, 13], [1, 2, 6]),
        # 4D coordinates: rotation only affects first 2 dims, other dims just get offset
        ([1, 0, 10, 7], [0, 1, 3, 8], [2, 2, 3, 5], 90, [2, 3, 13, 12], [1, 2, 6, 13]),
        # 2D with 45° rotation: (1, 0) -> (0.70711, 0.70711), (0, 1) -> (-0.70711, 0.70711)
        ([1, 0], [0, 1], [2, 2], 45, [2.70711, 2.70711], [1.29289, 2.70711]),
        # 3D with 45° rotation
        ([1, 0, 10], [0, 1, 3], None, 45, [0.70711, 0.70711, 10], [-0.70711, 0.70711, 3]),
        # 4D with 45° rotation
        (
            [1, 0, 10, 7],
            [0, 1, 3, 8],
            [2, 2, 3, 5],
            45,
            [2.70711, 2.70711, 13, 12],
            [1.29289, 2.70711, 6, 13],
        ),
    ],
    ids=["2D_90deg", "3D_90deg", "4D_90deg", "2D_45deg", "3D_45deg", "4D_45deg"],
)
def test_qubit_rotation_around_origin(
    xdsl_context: Context,
    initial_coords_0,
    initial_coords_1,
    offset,
    angle,
    expected_coords_0,
    expected_coords_1,
):
    """Test that qubits are correctly rotated when a rotation config is provided."""

    @ModuleOp
    @Builder.implicit_region
    def module_op():
        qubit_0 = QubitAllocOp(0).results[0]
        QubitCoordsOp([qubit_0], QubitMappingAttr(initial_coords_0))
        qubit_1 = QubitAllocOp(1).results[0]
        QubitCoordsOp([qubit_1], QubitMappingAttr(initial_coords_1))
        ResetGateOp([qubit_0, qubit_1])

    # Rotate counterclockwise around the origin
    rotation_config = (angle, (0, 0))
    qubit_mapping = {
        0: expected_coords_0,
        1: expected_coords_1,
    }
    RemapQubits(offset, qubit_mapping, rotation_config).apply(xdsl_context, module_op)

    # Verify the coordinates were updated correctly
    coords_ops = [op for op in module_op.body.block.ops if isinstance(op, QubitCoordsOp)]
    assert len(coords_ops) == 2

    actual_coords_0 = [coord.data for coord in coords_ops[0].qubitcoord.coords.data]
    actual_coords_1 = [coord.data for coord in coords_ops[1].qubitcoord.coords.data]

    assert actual_coords_0 == pytest.approx(expected_coords_0, abs=1e-5)
    assert actual_coords_1 == pytest.approx(expected_coords_1, abs=1e-5)


@pytest.mark.parametrize(
    (
        "initial_coords_0",
        "initial_coords_1",
        "center",
        "angle",
        "offset",
        "expected_coords_0",
        "expected_coords_1",
    ),
    [
        # 2D: Rotate 90° around (1, 1)
        ([1, 0], [0, 1], (1, 1), 90, [2, 2], [4, 3], [3, 2]),
        # 3D: Rotate 90° around (2, 3), z dimension only gets offset
        ([3, 3, 10], [2, 4, 5], (2, 3), 90, [1, 1, 2], [3, 5, 12], [2, 4, 7]),
        # 4D: Rotate 90° around (-1, -1), other dimensions only get offset
        ([0, -1, 8, 3], [-1, 0, 2, 7], (-1, -1), 90, [0, 0, 1, 2], [-1, 0, 9, 5], [-2, -1, 3, 9]),
        # 2D: Rotate 45° around (1, 1)
        # (2, 1) -> translate (1, 0) -> rotate (0.70711, 0.70711) -> back (1.70711, 1.70711)
        # (1, 2) -> translate (0, 1) -> rotate (-0.70711, 0.70711) -> back (0.29289, 1.70711)
        ([2, 1], [1, 2], (1, 1), 45, [0, 0], [1.70711, 1.70711], [0.29289, 1.70711]),
        # 3D: Rotate 45° around (2, 3)
        (
            [3, 3, 10],
            [2, 4, 5],
            (2, 3),
            45,
            [0, 0, 2],
            [2.70711, 3.70711, 12],
            [1.29289, 3.70711, 7],
        ),
        # 4D: Rotate 45° around (0, 0)
        (
            [1, 1, 5, 3],
            [2, 0, 8, 7],
            (0, 0),
            45,
            [1, 1, 2, 4],
            [1, 2.41421, 7, 7],
            [2.41421, 2.41421, 10, 11],
        ),
    ],
    ids=[
        "2D_90deg_center_(1,1)",
        "3D_90deg_center_(2,3)",
        "4D_90deg_center_(-1,-1)",
        "2D_45deg_center_(1,1)",
        "3D_45deg_center_(2,3)",
        "4D_45deg_center_(0,0)",
    ],
)
def test_qubit_rotation_around_different_centres(
    xdsl_context: Context,
    initial_coords_0,
    initial_coords_1,
    center,
    angle,
    offset,
    expected_coords_0,
    expected_coords_1,
):
    """Test that qubits are correctly rotated around different centres."""

    @ModuleOp
    @Builder.implicit_region
    def module_op():
        qubit_0 = QubitAllocOp(0).results[0]
        QubitCoordsOp([qubit_0], QubitMappingAttr(initial_coords_0))
        qubit_1 = QubitAllocOp(1).results[0]
        QubitCoordsOp([qubit_1], QubitMappingAttr(initial_coords_1))
        ResetGateOp([qubit_0, qubit_1])

    # Rotate counterclockwise around the specified center
    rotation_config = (angle, center)
    qubit_mapping = {
        0: expected_coords_0,
        1: expected_coords_1,
    }
    RemapQubits(offset, qubit_mapping, rotation_config).apply(xdsl_context, module_op)

    # Verify the coordinates were updated correctly
    coords_ops = [op for op in module_op.body.block.ops if isinstance(op, QubitCoordsOp)]
    assert len(coords_ops) == 2

    actual_coords_0 = [coord.data for coord in coords_ops[0].qubitcoord.coords.data]
    actual_coords_1 = [coord.data for coord in coords_ops[1].qubitcoord.coords.data]

    assert actual_coords_0 == pytest.approx(expected_coords_0, abs=1e-5)
    assert actual_coords_1 == pytest.approx(expected_coords_1, abs=1e-5)


@pytest.mark.parametrize(
    (
        "initial_coords_0",
        "initial_coords_1",
        "center",
        "angle",
        "offset",
        "expected_coords_0",
        "expected_coords_1",
    ),
    [
        # 2D: Rotate 90° around (1, 1)
        ([1, 0], [0, 1], (1, 1), 90, [2, 2], [4, 3], [3, 2]),
        # 3D: Rotate 90° around (2, 3), z dimension only gets offset
        ([3, 3, 10], [2, 4, 5], (2, 3), 90, [1, 1, 2], [3, 5, 12], [2, 4, 7]),
        # 4D: Rotate 90° around (-1, -1), other dimensions only get offset
        ([0, -1, 8, 3], [-1, 0, 2, 7], (-1, -1), 90, [0, 0, 1, 2], [-1, 0, 9, 5], [-2, -1, 3, 9]),
        # 2D: Rotate 45° around (1, 1)
        # (2, 1) -> translate (1, 0) -> rotate (0.70711, 0.70711) -> back (1.70711, 1.70711)
        # (1, 2) -> translate (0, 1) -> rotate (-0.70711, 0.70711) -> back (0.29289, 1.70711)
        ([2, 1], [1, 2], (1, 1), 45, [0, 0], [1.70711, 1.70711], [0.29289, 1.70711]),
        # 3D: Rotate 45° around (2, 3)
        (
            [3, 3, 10],
            [2, 4, 5],
            (2, 3),
            45,
            [0, 0, 2],
            [2.70711, 3.70711, 12],
            [1.29289, 3.70711, 7],
        ),
        # 4D: Rotate 45° around (0, 0)
        (
            [1, 1, 5, 3],
            [2, 0, 8, 7],
            (0, 0),
            45,
            [1, 1, 2, 4],
            [1, 2.41421, 7, 7],
            [2.41421, 2.41421, 10, 11],
        ),
    ],
    ids=[
        "2D_90deg_center_(1,1)",
        "3D_90deg_center_(2,3)",
        "4D_90deg_center_(-1,-1)",
        "2D_45deg_center_(1,1)",
        "3D_45deg_center_(2,3)",
        "4D_45deg_center_(0,0)",
    ],
)
def test_qubit_rotation_around_different_centres_using_rotation_config(
    xdsl_context: Context,
    initial_coords_0,
    initial_coords_1,
    center,
    angle,
    offset,
    expected_coords_0,
    expected_coords_1,
):
    """Test that qubits are correctly rotated around different centres."""

    @ModuleOp
    @Builder.implicit_region
    def module_op():
        qubit_0 = QubitAllocOp(0).results[0]
        QubitCoordsOp([qubit_0], QubitMappingAttr(initial_coords_0))
        qubit_1 = QubitAllocOp(1).results[0]
        QubitCoordsOp([qubit_1], QubitMappingAttr(initial_coords_1))
        ResetGateOp([qubit_0, qubit_1])

    # Rotate counterclockwise around the specified center
    rotation_config = (angle, center)
    qubit_mapping = {
        0: expected_coords_0,
        1: expected_coords_1,
    }
    RemapQubits(offset, qubit_mapping, RotationConfig(*rotation_config)).apply(
        xdsl_context, module_op
    )

    # Verify the coordinates were updated correctly
    coords_ops = [op for op in module_op.body.block.ops if isinstance(op, QubitCoordsOp)]
    assert len(coords_ops) == 2

    actual_coords_0 = [coord.data for coord in coords_ops[0].qubitcoord.coords.data]
    actual_coords_1 = [coord.data for coord in coords_ops[1].qubitcoord.coords.data]

    assert actual_coords_0 == pytest.approx(expected_coords_0, abs=1e-5)
    assert actual_coords_1 == pytest.approx(expected_coords_1, abs=1e-5)
