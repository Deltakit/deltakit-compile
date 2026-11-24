# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module re-exporting symbols from ``deltakit_stim``.

All ``deltakit_stim`` imports in this repository must go through this module so that the
underlying implementation can be swapped by changing the import below.
"""

from importlib.metadata import version

from deltakit_stim import (
    Circuit,
    CircuitInstruction,
    CircuitRepeatBlock,
    GateTarget,
    PauliString,
    Tableau,
)

__version__: str = version("deltakit_stim")

__all__ = [
    "Circuit",
    "CircuitInstruction",
    "CircuitRepeatBlock",
    "GateTarget",
    "PauliString",
    "Tableau",
    "__version__",
]
