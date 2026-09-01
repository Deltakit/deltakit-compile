"""Test the changes made to the MLIR scf dialect."""

import pytest
from xdsl.ir import Operation
from xdsl.traits import OpTrait

from deltakit_compile.dialects import scf
from deltakit_compile.dialects.qcore import NoQuantumEffect, RecursiveQuantumEffect


@pytest.mark.parametrize(
    ("op", "new_trait"),
    [
        (scf.ConditionOp, NoQuantumEffect()),
        (scf.ForOp, RecursiveQuantumEffect()),
        (scf.IfOp, RecursiveQuantumEffect()),
        (scf.IndexSwitchOp, RecursiveQuantumEffect()),
        (scf.WhileOp, RecursiveQuantumEffect()),
        (scf.YieldOp, NoQuantumEffect()),
    ],
)
def test_scf_traits(op: Operation, new_trait: OpTrait) -> None:
    """Test that the traits of scf ops have been extended correctly."""
    traits = list(op.traits)
    assert new_trait in traits
    assert len(traits) > 1  # Show the original traits are still there
