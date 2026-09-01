# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Enums for Deltakit-Stim gates."""

from deltakit_compile.utilities.base_enums import BetterStrEnum


class AnnotationEnum(BetterStrEnum):
    """Enum for the parsable annotation instructions in Deltakit-Stim."""

    COORD = "QUBIT_COORDS"
    TICK = "TICK"
    DETECTOR = "DETECTOR"
    OBSERVABLE = "OBSERVABLE_INCLUDE"
    SHIFT = "SHIFT_COORDS"


class SingleQubitUnitaryEnum(BetterStrEnum):
    """Enum for the parseable single qubit unitary gates in Deltakit-Stim."""

    IDENTITY = "I"
    X = "X"
    Y = "Y"
    Z = "Z"
    HXY = "H_XY"
    HYZ = "H_YZ"
    HXZ = "H_XZ"
    H = "H"
    SQRT_X_DAG = "SQRT_X_DAG"
    SQRT_Y_DAG = "SQRT_Y_DAG"
    SQRT_Z_DAG = "SQRT_Z_DAG"
    SQRT_X = "SQRT_X"
    SQRT_Y = "SQRT_Y"
    SQRT_Z = "SQRT_Z"
    S_DAG = "S_DAG"
    S = "S"


class TwoQubitUnitaryEnum(BetterStrEnum):
    """Enum for the parseable two qubit unitary gates in Deltakit-Stim."""

    SQRT_XX_DAG = "SQRT_XX_DAG"
    SQRT_YY_DAG = "SQRT_YY_DAG"
    SQRT_ZZ_DAG = "SQRT_ZZ_DAG"
    SQRT_XX = "SQRT_XX"
    SQRT_YY = "SQRT_YY"
    SQRT_ZZ = "SQRT_ZZ"

    ISWAP = "ISWAP"
    ISWAP_DAG = "ISWAP_DAG"
    SWAP = "SWAP"

    CNOT = "CNOT"
    CX = "CX"
    CY = "CY"
    CZ = "CZ"
    XCX = "XCX"
    XCY = "XCY"
    XCZ = "XCZ"
    YCX = "YCX"
    YCY = "YCY"
    YCZ = "YCZ"
    ZCX = "ZCX"
    ZCY = "ZCY"
    ZCZ = "ZCZ"


class MeasurementEnum(BetterStrEnum):
    """Enum for the parseable measurement instructions in Deltakit-Stim."""

    MX = "MX"
    MY = "MY"
    MZ = "MZ"
    M = "M"
    MR = "MR"
    MRX = "MRX"
    MRY = "MRY"
    MRZ = "MRZ"


class MPPEnum(BetterStrEnum):
    """Enum for the parseable pauli product measurement instructions in Deltakit-Stim."""

    MPP = "MPP"


class ResetEnum(BetterStrEnum):
    """Enum for the parseable reset instructions in Deltakit-Stim."""

    RX = "RX"
    RY = "RY"
    RZ = "RZ"
    R = "R"


class NoiseEnum(BetterStrEnum):
    """Enum for the parseable noise instructions in Deltakit-Stim."""

    DEPOLARIZE1 = "DEPOLARIZE1"
    DEPOLARIZE2 = "DEPOLARIZE2"
    PAULI_CHANNEL_1 = "PAULI_CHANNEL_1"
    PAULI_CHANNEL_2 = "PAULI_CHANNEL_2"
    X_ERROR = "X_ERROR"
    Y_ERROR = "Y_ERROR"
    Z_ERROR = "Z_ERROR"
    CORRELATED_ERROR = "E"
    ELSE_CORRELATED_ERROR = "ELSE_CORRELATED_ERROR"


class LeakageEnum(BetterStrEnum):
    """Enum for the parseable leakage instructions in Deltakit-Stim."""

    HERALD_LEAKAGE_EVENT = "HERALD_LEAKAGE_EVENT"
    LEAKAGE = "LEAKAGE"
    RELAX = "RELAX"


DeltakitStimGateEnum = SingleQubitUnitaryEnum | TwoQubitUnitaryEnum
DeltakitStimQuantumOpEnum = DeltakitStimGateEnum | MeasurementEnum | MPPEnum | ResetEnum
