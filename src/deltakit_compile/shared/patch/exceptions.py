# (c) Copyright Riverlane 2025-2026. All rights reserved.
from deltakit_compile.exceptions import DeltakitCompilerError


class PatchError(DeltakitCompilerError):
    """Generic error for patch-related exceptions."""


class UnsizedPatchError(DeltakitCompilerError):
    """Raised when a sized patch type is expected, but an unsized patch type is provided."""


class UnplacedPatchError(DeltakitCompilerError):
    """Raised when a placed patch type is expected, but an unplaced patch type is provided."""
