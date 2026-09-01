# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Tests for the context module."""

import pytest

from deltakit_compile.context import Context
from deltakit_compile.passes.combine_detector_rounds import CombineDetectorRounds
from deltakit_compile.passes.remap_qubits import RemapQubits


def test_context_auxiliary_outputs():
    """Test that auxiliary outputs can be added and retrieved from the context."""
    ctx = Context()
    pass1 = CombineDetectorRounds()
    ctx.add_auxiliary_output(pass1, "output1", "value1")
    pass2 = RemapQubits([2, 2], None)
    ctx.add_auxiliary_output(pass2, "output2", [1, 2, 3])
    assert ctx.auxiliary_outputs == {
        "combine-detector-rounds.output1": "value1",
        "remap-qubits.output2": [1, 2, 3],
    }


def test_duplicate_auxiliary_output_raises():
    """Test that adding a duplicate auxiliary output raises an error."""
    ctx = Context()
    pass1 = RemapQubits([2, 2], None)
    ctx.add_auxiliary_output(pass1, "output1", "value1")
    with pytest.raises(
        ValueError,
        match=r"Auxiliary output with name 'output1' already exists for pass 'remap-qubits'.",
    ):
        ctx.add_auxiliary_output(pass1, "output1", "value2")


def test_auxiliary_output_overwrite():
    """Test overwriting a duplicate auxiliary output with `allow_overwrite=True`."""
    ctx = Context()
    pass1 = RemapQubits([2, 2], None)
    ctx.add_auxiliary_output(pass1, "output1", "value1")
    ctx.add_auxiliary_output(pass1, "output1", "value2", allow_overwrite=True)
    assert ctx.auxiliary_outputs == {
        "remap-qubits.output1": "value2",
    }


def test_clone_context():
    """Test that cloning a context preserves auxiliary outputs."""
    ctx = Context()
    pass1 = CombineDetectorRounds()
    ctx.add_auxiliary_output(pass1, "output1", "value1")
    cloned_ctx = ctx.clone()
    ctx.add_auxiliary_output(pass1, "output1", "value2", allow_overwrite=True)
    assert isinstance(cloned_ctx, Context)
    assert ctx.auxiliary_outputs == {
        "combine-detector-rounds.output1": "value2",
    }
    assert cloned_ctx.auxiliary_outputs == {
        "combine-detector-rounds.output1": "value1",
    }
