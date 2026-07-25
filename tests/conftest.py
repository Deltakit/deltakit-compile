# (c) Copyright Riverlane 2020-2026. All rights reserved.
import numpy as np
import pytest


@pytest.fixture
def random_generator():
    return np.random.default_rng()
