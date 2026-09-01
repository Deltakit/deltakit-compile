"""Exception/warning tests for the add noise pass."""

import pytest
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp

from deltakit_compile.dialects.stim import (
    Depolarize1Op,
    MeasurementGateOp,
    MultiPauliProductMeasurementOp,
    PauliOperatorEnum,
)
from deltakit_compile.noise_models.si1000_noise import SI1000NoiseConfig
from deltakit_compile.passes.add_noise import AddNoise
from deltakit_compile.utilities.gatesets import NativeGateSet


def test_existing_noise_warnings(xdsl_context: Context, recwarn: pytest.WarningsRecorder):
    """Test that warnings is printed if noise ops already exist in the circuit."""
    AddNoise(SI1000NoiseConfig(p=0.01), NativeGateSet().native_gates).apply(
        xdsl_context,
        ModuleOp(
            [
                Depolarize1Op([], 0.01),
                MeasurementGateOp([], PauliOperatorEnum.Z, noise=0.05),
                MultiPauliProductMeasurementOp(targets=[], pauli_modifiers=[], noise=0.05),
            ]
        ),
    )
    user_warnings = list(filter(lambda w: issubclass(w.category, UserWarning), recwarn))
    assert str(user_warnings[0].message) == "Adding noise to a circuit that already contains noise"
    assert (
        str(user_warnings[1].message)
        == "Adding measurement noise to measurements that are already noisy"
    )
