"""Test the changes made to the MLIR arith dialect."""

import pytest
from xdsl.ir import Operation

from deltakit_compile.dialects import arith
from deltakit_compile.dialects.qcore import NoQuantumEffect


@pytest.mark.parametrize(
    "op",
    [
        arith.CmpiOp,
        arith.ConstantOp,
        arith.AddiOp,
        arith.SubiOp,
        arith.AndIOp,
        arith.OrIOp,
        arith.XOrIOp,
        arith.SelectOp,
    ],
)
def test_arith_traits(op: Operation) -> None:
    """Test that the traits of arith ops have been extended correctly."""
    traits = list(op.traits)
    assert NoQuantumEffect() in traits
    assert len(traits) > 1  # Show the original traits are still there
