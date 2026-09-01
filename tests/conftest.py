# (c) Copyright Riverlane 2020-2025.
import numpy as np
import pytest


@pytest.fixture(scope="session")
def random_generator():
    return np.random.default_rng()
