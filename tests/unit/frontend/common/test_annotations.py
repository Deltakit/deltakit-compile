import re

import pytest

from deltakit_compile.dialects.qec import DetectorRefType, ObservableIncludeOp
from deltakit_compile.frontend.common._annotations import (
    Detector,
    Observable,
)
from deltakit_compile.frontend.common._builder import OperationBuilder
from deltakit_compile.frontend.common._circuit import CircuitBuilder
from deltakit_compile.frontend.common._exceptions import (
    DifferentBuildersError,
    DuplicatedIdentifiersError,
    NoMeasurementProvidedError,
    ObservableError,
)
from deltakit_compile.frontend.common._measurements import MeasurementReg
from deltakit_compile.frontend.common._qubit_reg import Qubit, QubitReg
from deltakit_compile.frontend.common._vector import Vector
from tests.unit.frontend.conftest import add_to_builder_with_fake_ssa


def test_detector_initialisation() -> None:
    builder = OperationBuilder()
    mreg = add_to_builder_with_fake_ssa(builder, MeasurementReg(3))
    m0, m1, m2 = mreg[0], mreg[1], mreg[2]

    det = Detector([m0])
    assert det.measurements == (m0,)
    assert det.coordinates is None

    det = Detector([m0, m1, m2])
    assert det.measurements == (m0, m1, m2)
    assert det.coordinates is None

    coords = Vector(0, 0, 2, 45)
    det = Detector([m1], coordinates=coords)
    assert det.measurements == (m1,)
    assert det.coordinates == coords


def test_detector_without_measurements_raises() -> None:
    with pytest.raises(NoMeasurementProvidedError):
        Detector([])


def test_detector_with_duplicate_measurements_raises() -> None:
    builder = OperationBuilder()
    mreg_sized = add_to_builder_with_fake_ssa(builder, MeasurementReg(3))
    meas = mreg_sized[0]
    msg = f".*{{'{meas.identifier}'}}.*"
    with pytest.raises(DuplicatedIdentifiersError, match=msg):
        Detector([meas, meas])


def test_detector_with_measurements_from_different_holders_raises() -> None:
    builder1 = OperationBuilder()
    builder2 = OperationBuilder()
    mreg1 = add_to_builder_with_fake_ssa(builder1, MeasurementReg(3))
    mreg2 = add_to_builder_with_fake_ssa(builder2, MeasurementReg(4))

    m1, m2 = mreg1[1], mreg2[3]
    with pytest.raises(DifferentBuildersError):
        Detector([m1, m2])


def test_detector_type_info() -> None:
    builder = OperationBuilder()
    mreg = add_to_builder_with_fake_ssa(builder, MeasurementReg(1))
    assert isinstance(Detector([mreg[0]])._type_info, DetectorRefType)


def test_observable_initialisation() -> None:
    builder = OperationBuilder()
    qreg = add_to_builder_with_fake_ssa(builder, QubitReg())

    qubit = qreg[0]
    assert not Observable()._support
    assert Observable([qubit])._support == (qubit,)

    obs = Observable([qreg[i] for i in range(100)])
    assert obs._support is not None
    assert len(obs._support) == 100

    obs = Observable([qreg[3]])
    assert obs._support is not None
    assert len(obs._support) == 1

    msg = re.escape("Cannot define an observable on non-attached qubits.")
    with pytest.raises(ObservableError, match=msg):
        Observable([Qubit()])


def test_observable_include() -> None:
    builder = OperationBuilder()
    qreg = add_to_builder_with_fake_ssa(builder, QubitReg())
    mreg = add_to_builder_with_fake_ssa(builder, MeasurementReg(10))
    obs = add_to_builder_with_fake_ssa(builder, Observable())
    obs.include([mreg[0], mreg[3], mreg[6]])
    assert len(obs._measurements) == 3
    assert isinstance(builder.last_op, ObservableIncludeOp)

    obs.include(mreg)
    assert len(obs._measurements) == 13
    assert isinstance(builder.last_op, ObservableIncludeOp)

    obs_with_support = add_to_builder_with_fake_ssa(builder, Observable((qreg[0],)))
    msg = re.escape("Cannot use the include method when the observable is declared on a support.")
    with pytest.raises(ObservableError, match=msg):
        obs_with_support.include([mreg[0]])

    unattached_obs = Observable([qreg[3]])
    msg = re.escape("Cannot call Observable.include on an observable that is not attached.")
    with pytest.raises(ObservableError, match=msg):
        unattached_obs.include([mreg[0]])

    other_builder = OperationBuilder()
    omreg = add_to_builder_with_fake_ssa(other_builder, MeasurementReg(10))
    with pytest.raises(DifferentBuildersError):
        obs.include([omreg[0]])


def test_observable_move() -> None:
    builder = OperationBuilder()
    qreg = add_to_builder_with_fake_ssa(builder, QubitReg())
    mreg = add_to_builder_with_fake_ssa(builder, MeasurementReg(10))

    no_support_observable = add_to_builder_with_fake_ssa(builder, Observable())
    msg = re.escape(
        "Cannot use the move method when the observable has not been declared as being "
        "supported on qubits."
    )
    with pytest.raises(ObservableError, match=msg):
        no_support_observable.move([qreg[0]], [mreg[0]])

    obs = add_to_builder_with_fake_ssa(builder, Observable([qreg[0], qreg[4], qreg[3]]))
    obs.move([qreg[1], qreg[3], qreg[4], qreg[5], qreg[7]], [mreg[0], mreg[4]])
    assert obs._support is not None
    assert len(obs._support) == 5
    assert len(obs._measurements) == 2

    obs.move([qreg[0]], [mreg[1], mreg[5]])
    assert obs._support is not None
    assert len(obs._support) == 1
    assert len(obs._measurements) == 4


def test_observable_move_with_register() -> None:
    builder = OperationBuilder()
    qreg = add_to_builder_with_fake_ssa(builder, QubitReg())
    mreg = add_to_builder_with_fake_ssa(builder, MeasurementReg(10))
    obs = add_to_builder_with_fake_ssa(builder, Observable([qreg[0], qreg[4], qreg[3]]))

    obs.move([qreg[2]], mreg)
    assert obs._support is not None
    assert len(obs._support) == 1
    assert len(obs._measurements) == 10


def test_unattached_observable_move_raises() -> None:
    builder = OperationBuilder()
    qreg = add_to_builder_with_fake_ssa(builder, QubitReg())
    mreg = add_to_builder_with_fake_ssa(builder, MeasurementReg(10))

    unattached_obs = Observable([qreg[3]])
    msg = re.escape("Cannot call Observable.move on an observable that is not attached.")
    with pytest.raises(ObservableError, match=msg):
        unattached_obs.move([qreg[0]], [mreg[1], mreg[5]])


def test_observable_raises_when_from_different_builders() -> None:
    builder = OperationBuilder()
    qreg = add_to_builder_with_fake_ssa(builder, QubitReg())
    obs = add_to_builder_with_fake_ssa(builder, Observable((qreg[0],)))

    other_builder = OperationBuilder()
    other_qreg = add_to_builder_with_fake_ssa(other_builder, QubitReg())
    other_mreg = add_to_builder_with_fake_ssa(other_builder, MeasurementReg(10))

    with pytest.raises(DifferentBuildersError):
        obs.move((other_qreg[1],), (other_mreg[5],))


def test_uncorrected() -> None:
    builder = CircuitBuilder()

    obs = builder.declare_observable()
    uncorrected_value = obs.get_uncorrected()
    assert uncorrected_value._is_attached
    assert uncorrected_value._builder is builder._builder


def test_corrected() -> None:
    builder = CircuitBuilder()

    obs = builder.declare_observable()
    corrected_value = obs.get_corrected()
    assert corrected_value._is_attached
    assert corrected_value._builder is builder._builder


def test_correction_ready() -> None:
    builder = CircuitBuilder()

    obs = builder.declare_observable()
    is_correction_ready = obs.correction_ready()
    assert is_correction_ready._is_attached
    assert is_correction_ready._builder is builder._builder


def test_get_correction() -> None:
    builder = CircuitBuilder()

    obs = builder.declare_observable()
    correction = obs.get_correction()
    assert correction._is_attached
    assert correction._builder is builder._builder
