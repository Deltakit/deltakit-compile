"""Tests for exceptions in the collapse-adjacent-alloc pass."""

import re

import pytest
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.parser import IntAttr

from deltakit_compile.dialects import qcore, qstruct
from deltakit_compile.passes.collapse_adjacent_alloc import CollapseAdjacentAlloc


@pytest.mark.parametrize("alloc_type", [qcore.QubitType(), qcore.QubitRegType(1)])
def test_raise_on_duplicate_ids(
    xdsl_context: Context, alloc_type: qcore.QubitType | qcore.QubitRegType
) -> None:
    module_op = ModuleOp(
        [
            qcore.AllocQubitOp(alloc_type, ids=[1]),
            qcore.AllocQubitOp(alloc_type, ids=[1]),
        ]
    )

    with pytest.raises(
        ValueError,
        match=re.escape("Duplicate id 1 found while collecting adjacent qcore.alloc_qubit ops."),
    ):
        CollapseAdjacentAlloc().apply(xdsl_context, module_op)


@pytest.mark.parametrize("alloc_type", [qcore.QubitType(), qcore.QubitRegType(1)])
def test_raise_on_mismatching_coords_dim(
    xdsl_context: Context, alloc_type: qcore.QubitType | qcore.QubitRegType
) -> None:
    module_op = ModuleOp(
        [
            qcore.AllocQubitOp(alloc_type, coordinates=[(1.0, 2.0)]),
            qcore.AllocQubitOp(alloc_type, coordinates=[(1.0, 2.0, 3.0)]),
        ]
    )

    with pytest.raises(
        ValueError,
        match=re.escape(
            "Coordinate (1.0, 2.0, 3.0) has dimension 3 which does not match the expected "
            "dimension of 2"
        ),
    ):
        CollapseAdjacentAlloc().apply(xdsl_context, module_op)


@pytest.mark.parametrize("alloc_type", [qcore.QubitType(), qcore.QubitRegType(1)])
def test_raise_on_duplicate_coords(
    xdsl_context: Context, alloc_type: qcore.QubitType | qcore.QubitRegType
) -> None:
    module_op = ModuleOp(
        [
            qcore.AllocQubitOp(alloc_type, coordinates=[(1.0, 2.0)]),
            qcore.AllocQubitOp(alloc_type, coordinates=[(1.0, 2.0)]),
        ]
    )

    with pytest.raises(
        ValueError,
        match=re.escape(
            "Duplicate coordinate (1.0, 2.0) found while collecting adjacent qcore.alloc_qubit ops."
        ),
    ):
        CollapseAdjacentAlloc().apply(xdsl_context, module_op)


@pytest.mark.parametrize("alloc_type", [qcore.QubitType(), qcore.QubitRegType(1)])
def test_raise_on_attributes(
    xdsl_context: Context, alloc_type: qcore.QubitType | qcore.QubitRegType
) -> None:
    module_op = ModuleOp([alloc_op := qcore.AllocQubitOp(alloc_type)])
    alloc_op.attributes["some_attr"] = IntAttr(42)

    with pytest.raises(
        ValueError,
        match=r"AllocQubitOp\(.*\) has attributes which would be lost when collapsing\.",
    ):
        CollapseAdjacentAlloc().apply(xdsl_context, module_op)


@pytest.mark.parametrize("alloc_type", [qcore.QubitType(), qcore.QubitRegType(1)])
def test_no_raise_on_attributes_if_configured(
    xdsl_context: Context, alloc_type: qcore.QubitType | qcore.QubitRegType
) -> None:
    module_op = ModuleOp([alloc_op := qcore.AllocQubitOp(alloc_type)])
    alloc_op.attributes["some_attr"] = IntAttr(42)

    # Should not raise any exceptions
    CollapseAdjacentAlloc(raise_on_attributes=False).apply(xdsl_context, module_op)


def test_no_raise_on_no_allocs(xdsl_context: Context) -> None:
    module_op = ModuleOp([qstruct.OutputOp([])])

    # Should not raise any exceptions
    CollapseAdjacentAlloc().apply(xdsl_context, module_op)
