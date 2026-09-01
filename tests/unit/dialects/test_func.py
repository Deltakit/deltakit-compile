"""Test the changes made to the MLIR func dialect."""

import pytest
from xdsl.ir import Operation
from xdsl.traits import OpTrait

from deltakit_compile.dialects import func
from deltakit_compile.dialects.qcore import NoQuantumEffect


@pytest.mark.parametrize(
    ("op", "new_trait"),
    [
        (func.CallOp, None),
        (func.FuncOp, None),
        (func.ReturnOp, NoQuantumEffect()),
    ],
)
def test_func_traits(op: Operation, new_trait: OpTrait | None) -> None:
    """Test that the traits of func ops have been extended correctly."""
    traits = list(op.traits)
    min_traits_len = 0
    if new_trait is not None:
        assert new_trait in traits
        min_traits_len = 1
    assert len(traits) > min_traits_len  # Show the original traits are still there
