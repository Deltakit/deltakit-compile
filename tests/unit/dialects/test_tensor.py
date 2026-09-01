"""Test the changes made to the MLIR tensor dialect."""

import pytest
from xdsl.ir import Operation

from deltakit_compile.dialects import tensor
from deltakit_compile.dialects.qcore import NoQuantumEffect


@pytest.mark.parametrize(
    "op",
    [tensor.DimOp, tensor.EmptyOp, tensor.ExtractOp, tensor.ExtractSliceOp, tensor.FromElementsOp],
)
def test_tensor_traits(op: Operation) -> None:
    """Test that the traits of tensor ops have been extended correctly."""
    traits = list(op.traits)
    assert NoQuantumEffect() in traits
    if op not in (tensor.ExtractOp, tensor.FromElementsOp):
        assert len(traits) > 1  # Show the original traits are still there
