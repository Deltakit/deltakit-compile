from deltakit_compile.frontend.circuit import CircuitBuilder, QubitReg
from deltakit_compile.frontend.common._annotations import Detector
from deltakit_compile.frontend.common._exceptions import (
    ArgumentSizeError,
    ArgumentTypeMismatchError,
    DifferentBuildersError,
    DuplicatedIdentifiersError,
    InvalidBinaryOperationError,
    NoMeasurementProvidedError,
    NotAttachedToSSA,
    UnsupportedArgumentTypeError,
    UnsupportedReturnTypeError,
)
from deltakit_compile.frontend.common._measurements import MeasurementReg


def test_no_measurement_provided_error() -> None:
    assert "A int instance" in str(NoMeasurementProvidedError(int))
    assert "A Detector instance" in str(NoMeasurementProvidedError(Detector))


def test_different_builders_error() -> None:
    base_msg = "Expected objects with the same builder but got at least two different builders."
    assert str(DifferentBuildersError()) == base_msg
    assert str(DifferentBuildersError("h4x0r")) == base_msg + " Details: h4x0r."


def test_duplicated_identifier_error() -> None:
    assert (
        str(DuplicatedIdentifiersError({"id"}))
        == "The following identifiers were provided more than once: {'id'}."
    )
    msg = str(DuplicatedIdentifiersError({"id", "873465", "another_id"}))
    assert msg.startswith("The following identifiers were provided more than once: {")
    assert "'id'" in msg
    assert "'873465'" in msg
    assert "'another_id'" in msg


def test_argument_size_error() -> None:
    assert (
        str(ArgumentSizeError(0, 1)) == "Wrong number of arguments provided. Expected 0 but got 1."
    )
    assert (
        str(ArgumentSizeError(1000, 561))
        == "Wrong number of arguments provided. Expected 1000 but got 561."
    )


def test_argument_type_mismatch_error() -> None:
    assert str(ArgumentTypeMismatchError(0, MeasurementReg, QubitReg)) == (
        "Argument 0 was declared as being of type MeasurementReg but got an instance of QubitReg."
    )


def test_unsupported_argument_type_error() -> None:
    assert str(UnsupportedArgumentTypeError(int)) == "Incompatible argument type provided: int."
    assert (
        str(UnsupportedArgumentTypeError(MeasurementReg))
        == "Incompatible argument type provided: MeasurementReg."
    )


def test_unsupported_return_type_error() -> None:
    assert (str(UnsupportedReturnTypeError(int))) == "Incompatible return type provided: int."
    assert (str(UnsupportedReturnTypeError(float))) == "Incompatible return type provided: float."
    assert (
        str(UnsupportedReturnTypeError(CircuitBuilder))
    ) == "Incompatible return type provided: CircuitBuilder."


def test_not_attached_to_ssa_error() -> None:
    assert str(NotAttachedToSSA("id")) == "The object id has not been attached a SSA value yet."
    assert (
        str(NotAttachedToSSA("wiefjb"))
        == "The object wiefjb has not been attached a SSA value yet."
    )


def test_invalid_binary_operation_error() -> None:
    assert str(InvalidBinaryOperationError("==")) == "The binary operation '==' is not supported."
    assert str(InvalidBinaryOperationError("!=")) == "The binary operation '!=' is not supported."
