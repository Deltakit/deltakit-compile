# (c) Copyright Riverlane 2025-2026. All rights reserved.
class BuilderAPIError(Exception):
    pass


class NoMeasurementProvidedError(BuilderAPIError):
    def __init__(self, t: type) -> None:
        super().__init__(f"A {t.__name__} instance requires at least one measurement. Got none.")


class DifferentBuildersError(BuilderAPIError):
    def __init__(self, details: str = "") -> None:
        details_str = f" Details: {details}." if details else ""
        super().__init__(
            "Expected objects with the same builder but got at least two different builders."
            + details_str
        )


class ObjectNotAttachedError(BuilderAPIError):
    def __init__(self) -> None:
        super().__init__("Object does not have a builder. Operation is not permitted.")


class DuplicatedIdentifiersError(BuilderAPIError):
    def __init__(self, duplicates: set[str]) -> None:
        super().__init__(f"The following identifiers were provided more than once: {duplicates}.")


class InvalidSizeError(BuilderAPIError):
    pass


class EmptyRoundError(InvalidSizeError):
    def __init__(self, round_description: str) -> None:
        super().__init__(f"Need at least one object in a {round_description}.")


class ArgumentError(BuilderAPIError):
    pass


class ArgumentSizeError(ArgumentError):
    def __init__(self, expected: int, provided: int) -> None:
        super().__init__(
            f"Wrong number of arguments provided. Expected {expected} but got {provided}."
        )


class ArgumentTypeMismatchError(ArgumentError):
    def __init__(self, argument_position: int, expected_type: type, provided_type: type) -> None:
        super().__init__(
            f"Argument {argument_position} was declared as being of type {expected_type.__name__} "
            f"but got an instance of {provided_type.__name__}."
        )


class UnsupportedArgumentTypeError(ArgumentError):
    def __init__(self, provided_type: type) -> None:
        super().__init__(f"Incompatible argument type provided: {provided_type.__name__}.")


class UnsupportedReturnTypeError(ArgumentError):
    def __init__(self, provided_type: type) -> None:
        super().__init__(f"Incompatible return type provided: {provided_type.__name__}.")


class InvalidMeasurementError(BuilderAPIError):
    def __init__(self) -> None:
        super().__init__(
            "Found an invalid measurement. Measurements should be attached and have a "
            "size of exactly 1."
        )


class ObservableError(BuilderAPIError):
    pass


class MissingLocationError(BuilderAPIError):
    pass


class EmptyBuilderError(BuilderAPIError):
    pass


class NotAttachedToSSA(BuilderAPIError):
    def __init__(self, identifier: str) -> None:
        super().__init__(f"The object {identifier} has not been attached a SSA value yet.")


class InvalidBinaryOperationError(BuilderAPIError):
    def __init__(self, binop: str) -> None:
        super().__init__(f"The binary operation '{binop}' is not supported.")


class IdentifierConflictError(BuilderAPIError):
    pass
