"""Test generalised noise behaviour."""

from itertools import chain

import numpy as np
import pytest
import yaml
from pydantic_core import ValidationError

from deltakit_compile.noise_models.gate_noise import GateNoiseConfig
from deltakit_compile.noise_models.idle_noise import DecoherenceTime
from deltakit_compile.noise_models.noise_factory import noise_param_factory
from deltakit_compile.noise_models.noise_parameters import (
    GateNoise,
    GateNoiseDict,
    IdMeasurement,
    MeasurementNoise,
    MeasurementNoiseDict,
    OneQubitDepolarisingNoise,
    OneQubitPauliNoise,
    SingleQubitIdGate,
    TwoQubitDepolarisingNoise,
    TwoQubitIdGate,
)
from deltakit_compile.noise_models.si1000_noise import SI1000NoiseConfig
from deltakit_compile.shared.deltakit_stim.gates import (
    MeasurementEnum,
    ResetEnum,
    SingleQubitUnitaryEnum,
    TwoQubitUnitaryEnum,
)
from tests.unit.paths import DELTAKIT_COMPILE_TEST_RESOURCES_CONFIG_FOLDER


def test_generalised_noise_can_be_no_noise():
    """Test that the noise parameter factory can produce noise parameters that add no noise."""
    params = noise_param_factory(GateNoiseConfig())
    assert params.gates[SingleQubitUnitaryEnum.X] == GateNoise()
    assert params.gates[TwoQubitUnitaryEnum.CX] == GateNoise()
    assert params.gates[ResetEnum.R] == GateNoise()
    assert "john" not in params.gates
    assert len(params.idle.from_executed_ops({ResetEnum.R})) == 0
    assert params.measurement == MeasurementNoise()


@pytest.fixture(scope="module")
def gate_si1000_config():
    p = 1e-3
    opgate_p = p / 10
    mmt_p = 2 * p
    # inverting generalised noise decay
    op_gate_times = -np.log(1 - opgate_p / 0.75)
    mmt_gate_times = -np.log(1 - mmt_p / 0.75)
    op_times = dict.fromkeys(chain(SingleQubitUnitaryEnum, TwoQubitUnitaryEnum), op_gate_times)
    op_times.update(dict.fromkeys(chain(ResetEnum, MeasurementEnum), mmt_gate_times))
    gate_noise_dict = GateNoiseDict(
        {
            gate_name: GateNoise(after=[OneQubitDepolarisingNoise(p=p / 10)])
            for gate_name in SingleQubitUnitaryEnum
        }
    )
    gate_noise_dict.update(
        {
            gate_name: GateNoise(after=[TwoQubitDepolarisingNoise(p=p)])
            for gate_name in TwoQubitUnitaryEnum
        }
    )
    gate_noise_dict.update(
        {gate_name: GateNoise(after=[OneQubitPauliNoise(x=2 * p)]) for gate_name in ResetEnum}
    )
    gate_noise_dict.update(
        {gate_name: GateNoise(after=[OneQubitPauliNoise(z=2 * p)]) for gate_name in ["RX"]}
    )
    return GateNoiseConfig(
        gates=gate_noise_dict,
        measurement=MeasurementNoise(bit_flip_p=5 * p),
        decay=DecoherenceTime(t1_time=1.0, t2_time=1.0),
        operation_times=op_times,
    )


@pytest.fixture(scope="module")
def si1000_config():
    return SI1000NoiseConfig(p=1e-3)


def test_gate_noise_can_be_si1000(gate_si1000_config, si1000_config):
    """Test that the noise parameter factory can produce noise parameters that add SI1000 noise."""
    gate_si1000_params = noise_param_factory(gate_si1000_config)
    si1000_params = noise_param_factory(si1000_config)
    assert gate_si1000_params.gates == si1000_params.gates
    assert gate_si1000_params.measurement == si1000_params.measurement


def test_gate_noise_loads_from_yaml():
    """Test that the generalised noise model can be loaded from a YAML file."""
    file_path = DELTAKIT_COMPILE_TEST_RESOURCES_CONFIG_FOLDER / "gate_noise.yaml"
    with file_path.open("r") as f:
        data = yaml.safe_load(f)
        noise_model = GateNoiseConfig.model_validate(data)
    assert isinstance(noise_model, GateNoiseConfig)
    expected_gate_noise = GateNoiseDict(
        {
            SingleQubitUnitaryEnum.H: GateNoise(after=[OneQubitDepolarisingNoise(p=0.001)]),
            SingleQubitIdGate(SingleQubitUnitaryEnum.H, 0): GateNoise(
                after=[OneQubitDepolarisingNoise(p=0.003), OneQubitPauliNoise(1e-3, 2e-3, 3e-3)]
            ),
            TwoQubitUnitaryEnum.CX: GateNoise(after=[OneQubitDepolarisingNoise(p=0.003)]),
            TwoQubitIdGate(TwoQubitUnitaryEnum.CX, (1, 0)): GateNoise(
                after=[OneQubitDepolarisingNoise(p=0.002), TwoQubitDepolarisingNoise(p=0.001)]
            ),
        }
    )
    for key, value in expected_gate_noise.items():
        assert noise_model.gates[key] == value
    expected_measurement_noise = MeasurementNoiseDict(
        {
            MeasurementEnum.MZ: MeasurementNoise(
                after=[OneQubitPauliNoise(1e-3, 0, 0)], bit_flip_p=0.002
            ),
            IdMeasurement(MeasurementEnum.MZ, 0): MeasurementNoise(
                bit_flip_p=0.003,
                before=[OneQubitDepolarisingNoise(3e-3)],
            ),
            IdMeasurement(MeasurementEnum.MZ, 1): MeasurementNoise(
                bit_flip_p=0.004,
                after=[OneQubitDepolarisingNoise(3e-3)],
            ),
        }
    )
    for key, value in expected_measurement_noise.items():
        assert noise_model.measurement[key] == value
    assert noise_model.decay == {
        0: DecoherenceTime(t1_time=20.0, t2_time=10.0),
        1: DecoherenceTime(t1_time=30.0, t2_time=40.0),
    }
    assert noise_model.initialisation == {0: [OneQubitPauliNoise(x=5e-3)]}
    assert noise_model.operation_times == {
        SingleQubitUnitaryEnum.H: 50,
        SingleQubitIdGate(SingleQubitUnitaryEnum.H, 1): 40,
        TwoQubitIdGate(TwoQubitUnitaryEnum.CX, (0, 1)): 60,
        TwoQubitUnitaryEnum.CX: 70,
        MeasurementEnum.MZ: 80,
        IdMeasurement(MeasurementEnum.MZ, 0): 100,
        ResetEnum.RZ: 120,
    }


def test_gate_noise_throws_exception_on_invalid_gate():
    with pytest.raises(ValidationError, match=r".*Unrecognised gate name: INVALID_GATE.*"):
        GateNoiseConfig(gates={"INVALID_GATE": {}})


def test_gate_noise_throws_exception_on_invalid_number_of_params():
    with pytest.raises(ValidationError, match=r".*Unrecognised gate name: CX 0"):
        GateNoiseConfig(gates={"CX 0": {}})


def test_gate_noise_throws_exception_on_invalid_measurement():
    with pytest.raises(ValidationError, match=r".*Unrecognised measurement name: INVALID.*"):
        GateNoiseConfig(measurement={"INVALID": {}})


def test_gate_noise_throws_exception_on_invalid_measurement_params():
    with pytest.raises(ValidationError, match=r".*Unrecognised measurement name: M 0 1.*"):
        GateNoiseConfig(measurement={"M 0 1": {}})


def test_gate_noise_throws_exception_on_invalid_noise():
    with pytest.raises(ValidationError, match=r".*Unrecognised noise: INVALID.*"):
        GateNoiseConfig(gates={"X": {"after": ["INVALID"]}})


def test_gate_noise_throws_exception_on_invalid_operation():
    with pytest.raises(ValidationError, match=r".*Unrecognised operation name: INVALID.*"):
        GateNoiseConfig(operation_times={"INVALID": 0})
