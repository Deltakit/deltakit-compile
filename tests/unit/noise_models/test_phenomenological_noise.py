"""Test phenomenological noise behaviour."""

import pytest
from pydantic_core import ValidationError

from deltakit_compile.noise_models.phenomenological_noise import PhenomenologicalNoiseConfig


def test_phenomenological_noise_throws_exception_on_invalid_noise():
    """Test that an exception is raised for invalid phenomenological noise."""
    with pytest.raises(
        ValidationError, match=r".*Unrecognised phenomenological_noise format: INVALID.*"
    ):
        PhenomenologicalNoiseConfig(phenomenological_noise="INVALID")


def test_phenomenological_noise_throws_exception_on_invalid_noise_channel():
    """Test that an exception is raised for invalid phenomenological noise channel."""
    with pytest.raises(ValidationError, match=r".*Unrecognised noise: INVALID.*"):
        PhenomenologicalNoiseConfig(phenomenological_noise={0: "INVALID"})


@pytest.mark.parametrize(
    ("noise", "err_msg"),
    [
        ("OneQubitDepolarisingNoise", r"Expected 1 param for OneQubitDepolarisingNoise, got 0"),
        ("OneQubitPauliNoise", r"Expected 1, 2 or 3 params for OneQubitPauliNoise, got 0"),
        ("RelaxNoise 0 0", r"Expected 1 param for RelaxNoise, got 2"),
        ("LeakageNoise 0.1 0.2 0.3", r"Expected 1 param for LeakageNoise, got 3"),
    ],
)
def test_phenomenological_noise_throws_exception_on_invalid_parameters_for_noise_channel(
    noise: str, err_msg: str
):
    """Test that an exception is raised when inputting the
    wrong number of parameters on a noise channel."""
    with pytest.raises(ValidationError, match=err_msg):
        PhenomenologicalNoiseConfig.model_validate({"phenomenological_noise": {0: noise}})


def test_no_phenomenological_noise_if_not_provided():
    """Test that no phenomenological noise is added if not provided."""
    assert PhenomenologicalNoiseConfig(phenomenological_noise=None).phenomenological_noise is None
