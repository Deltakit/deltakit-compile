# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""deltakit_compile exceptions."""

# region Exceptions


class DeltakitCompilerError(Exception):
    """Base class for deltakit_compile exceptions."""


class InvalidInputStimCircuit(DeltakitCompilerError):
    """Input Deltakit-Stim circuit is invalid."""


class InvalidInputQasmProgram(DeltakitCompilerError):
    """Input OpenQASM 3 program is invalid."""


class InvalidOutputFile(DeltakitCompilerError):
    """Output file is invalid."""


class InvalidConfigYAML(DeltakitCompilerError):
    """Invalid configuration YAML."""


class InvalidPassConfigurationException(InvalidConfigYAML):
    """Invalid pass configuration."""


class InvalidConfigurablePassDefinitionException(DeltakitCompilerError):
    """Invalid ConfigurablePass definition."""


class InvalidConfigurationDefinitionError(DeltakitCompilerError):
    """Invalid Configuration definition."""


class CompilerPassCheckError(DeltakitCompilerError):
    """A check defined by a compiler pass that failed."""


class PatchNotPreparedError(DeltakitCompilerError):
    """Use of an unprepared logical patch or used bridge."""


class InvalidQubitTensorError(DeltakitCompilerError):
    """Qubit Tensor is invalid in the operation it is used in."""


class StimUnsupportedGate(DeltakitCompilerError):
    """Qcore gate cannot be lowered to a Deltakit-Stim gate."""


class StimUnsupportedInstruction(DeltakitCompilerError):
    """Instruction cannot be lowered to a Deltakit-Stim instruction."""


class NonStandardUnitaryGateError(DeltakitCompilerError):
    """Raised when a unitary gate is encountered that does not match any known standard gates."""


class UnsupportedOperationError(DeltakitCompilerError):
    """Raised when a pass encounters an operation that is explicitly not supported."""


class InvalidStabiliserFlowError(DeltakitCompilerError):
    """Raised when an annotated stabiliser flow does not exist over its circuit."""


class BadUserFlowError(DeltakitCompilerError):
    """Raised when a user-specified stabiliser flow is invalid for reasons other than failing to
    exist over the annotated circuit.

    For example, it is blocked in the next circuit or is incompatible with a user-specified flow
    over another circuit. Also raised when flow annotations are required but not present, such as
    when flow generation is disabled.
    """


# endregion

# region Warnings


class DeltakitCompilerWarning(Warning):
    """A warning intended to be a base for any warning emitted during compilation"""


class NoiseWarning(DeltakitCompilerWarning):
    """A warning relating to noise either in usage or initial parsing from config"""


class LostStimTagWarning(DeltakitCompilerWarning):
    """A warning emitted when a Deltakit-Stim tag is dropped"""


class PatchLoweringError(DeltakitCompilerError):
    """Generic error for exceptions in the patch-lowering pipeline."""


# endregion
