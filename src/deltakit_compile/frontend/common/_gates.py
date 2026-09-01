# (c) Copyright Riverlane 2025-2026. All rights reserved.
from typing import Final

from deltakit_compile.dialects.qcore import (
    CXGateAttr,
    CYGateAttr,
    CZGateAttr,
    GateAttribute,
    HGateAttr,
    IdentityGateAttr,
    ISWAPGateAttr,
    PauliAttr,
    SGateAttr,
    SqrtXXGateAttr,
    SqrtYYGateAttr,
    SqrtZZGateAttr,
    SWAPGateAttr,
    TGateAttr,
    XGateAttr,
    YGateAttr,
    ZGateAttr,
)

RESET_MAPPING: Final[dict[str, PauliAttr]] = {
    "R": PauliAttr.Z(),
    "RX": PauliAttr.X(),
    "RY": PauliAttr.Y(),
    "RZ": PauliAttr.Z(),
}

GATE_MAPPING: Final[dict[str, GateAttribute]] = {
    "I": IdentityGateAttr(),
    "X": XGateAttr(),
    "Y": YGateAttr(),
    "Z": ZGateAttr(),
    "H": HGateAttr(),
    "S": SGateAttr(),
    "T": TGateAttr(),
    "CX": CXGateAttr(),
    "CY": CYGateAttr(),
    "CZ": CZGateAttr(),
    "SWAP": SWAPGateAttr(),
    "iSWAP": ISWAPGateAttr(),
    "SQRTXX": SqrtXXGateAttr(),
    "SQRTYY": SqrtYYGateAttr(),
    "SQRTZZ": SqrtZZGateAttr(),
}
