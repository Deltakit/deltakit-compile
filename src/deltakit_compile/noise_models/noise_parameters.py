# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module containing a generic class for storing noise model parameters."""

from __future__ import annotations

import warnings
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final, cast

from deltakit_stim import CircuitInstruction
from typing_extensions import override
from xdsl.ir import SSAValue

from deltakit_compile.dialects.deltakit_stim import LeakageOp, RelaxOp
from deltakit_compile.dialects.stim import (
    Depolarize1Op,
    Depolarize2Op,
    NoiseOp,
    PauliChannel1Op,
    PauliChannel2Op,
    QubitAllocOp,
)
from deltakit_compile.exceptions import NoiseWarning
from deltakit_compile.shared.deltakit_stim.gates import (
    DeltakitStimGateEnum,
    DeltakitStimQuantumOpEnum,
    MeasurementEnum,
    MPPEnum,
    ResetEnum,
    SingleQubitUnitaryEnum,
    TwoQubitUnitaryEnum,
)
from deltakit_compile.utilities.traverse_from_ssa import get_qubit_id


@dataclass(frozen=True)
class SingleQubitIdGate:
    """A one qubit gate type associated to a single qubit ID."""

    gate: SingleQubitUnitaryEnum | ResetEnum
    qubit_id: int


@dataclass(frozen=True)
class TwoQubitIdGate:
    """A two qubit gate type associated to two qubit IDs."""

    gate: TwoQubitUnitaryEnum
    qubit_id: tuple[int, int]


@dataclass(frozen=True)
class IdMeasurement:
    """A measurement gate type associated to a single qubit ID."""

    gate: MeasurementEnum
    qubit_id: int


@dataclass(frozen=True)
class IdMPP:
    """An MPP gate type associated to multiple qubit IDs."""

    gate: MPPEnum
    qubit_id: tuple[int, ...]


DeltakitStimGateKey = DeltakitStimGateEnum | ResetEnum | SingleQubitIdGate | TwoQubitIdGate
MeasurementKey = MeasurementEnum | IdMeasurement
DeltakitStimQuantumOpKey = DeltakitStimGateKey | MeasurementKey
DeltakitStimQuantumGatesetKey = DeltakitStimQuantumOpKey | MPPEnum | IdMPP

# Disable name checks as we don't have much choice than to obey Stim's very short naming style here


@dataclass(frozen=True)
class BasePauliNoise(ABC):
    """Base class for defining the a single application of pauli noise."""

    @abstractmethod
    def to_stim(self, targets: list[int]) -> CircuitInstruction:
        """Convert to a Deltakit-Stim noise instruction."""

    @abstractmethod
    def to_stim_op(self, targets: Sequence[SSAValue]) -> NoiseOp:
        """Convert to an xDSL stim dialect noise op."""


@dataclass(frozen=True)
class OneQubitDepolarisingNoise(BasePauliNoise):
    """Probability of error on a single qubit. On error occurrence, a pauli is applied at random."""

    p: float = 0

    @override
    def to_stim(self, targets: list[int]) -> CircuitInstruction:
        return CircuitInstruction(name="DEPOLARIZE1", targets=targets, gate_args=[self.p])

    @override
    def to_stim_op(self, targets: Sequence[SSAValue]) -> Depolarize1Op:
        return Depolarize1Op(targets, self.p)


@dataclass(frozen=True)
class TwoQubitDepolarisingNoise(BasePauliNoise):
    """Probability of error on two qubits. On error occurrence, a pair of paulis are applied at
    random."""

    p: float = 0

    @override
    def to_stim(self, targets: list[int]) -> CircuitInstruction:
        return CircuitInstruction(name="DEPOLARIZE2", targets=targets, gate_args=[self.p])

    @override
    def to_stim_op(self, targets: Sequence[SSAValue]) -> Depolarize2Op:
        return Depolarize2Op(targets, self.p)


@dataclass(frozen=True)
class OneQubitPauliNoise(BasePauliNoise):
    """Probability of each possible pauli error on a single qubit."""

    x: float = 0
    y: float = 0
    z: float = 0

    @override
    def to_stim(self, targets: list[int]) -> CircuitInstruction:
        if self.y == 0 and self.z == 0:
            return CircuitInstruction(name="X_ERROR", targets=targets, gate_args=[self.x])
        if self.x == 0 and self.z == 0:
            return CircuitInstruction(name="Y_ERROR", targets=targets, gate_args=[self.y])
        if self.x == 0 and self.y == 0:
            return CircuitInstruction(name="Z_ERROR", targets=targets, gate_args=[self.z])
        return CircuitInstruction(
            name="PAULI_CHANNEL_1",
            targets=cast(list[int], targets),
            gate_args=[self.x, self.y, self.z],
        )

    @override
    def to_stim_op(self, targets: Sequence[SSAValue]) -> PauliChannel1Op:
        return PauliChannel1Op(targets, [self.x, self.y, self.z])


@dataclass(frozen=True)
class TwoQubitPauliNoise(BasePauliNoise):
    """Probability of error for each possible pair of paulis on two qubits."""

    ix: float = 0
    iy: float = 0
    iz: float = 0
    xi: float = 0
    xx: float = 0
    xy: float = 0
    xz: float = 0
    yi: float = 0
    yx: float = 0
    yy: float = 0
    yz: float = 0
    zi: float = 0
    zx: float = 0
    zy: float = 0
    zz: float = 0

    def _to_probability_list(self) -> list[float]:
        """Get probabilities as a list."""
        return [
            self.ix,
            self.iy,
            self.iz,
            self.xi,
            self.xx,
            self.xy,
            self.xz,
            self.yi,
            self.yx,
            self.yy,
            self.yz,
            self.zi,
            self.zx,
            self.zy,
            self.zz,
        ]

    @override
    def to_stim(self, targets: list[int]) -> CircuitInstruction:
        return CircuitInstruction(
            name="PAULI_CHANNEL_2",
            targets=targets,
            gate_args=self._to_probability_list(),
        )

    @override
    def to_stim_op(self, targets: Sequence[SSAValue]) -> PauliChannel2Op:
        return PauliChannel2Op(targets, self._to_probability_list())


@dataclass(frozen=True)
class LeakageNoise(BasePauliNoise):
    """Probability of a single qubit leaking."""

    p: float = 0

    @override
    def to_stim(self, targets: list[int]) -> CircuitInstruction:
        return CircuitInstruction(name="LEAKAGE", targets=targets, gate_args=[self.p])

    @override
    def to_stim_op(self, targets: Sequence[SSAValue]) -> LeakageOp:
        return LeakageOp(targets, self.p)


@dataclass(frozen=True)
class RelaxNoise(BasePauliNoise):
    """Probability of a single leaked qubit relaxing."""

    p: float = 0

    @override
    def to_stim(self, targets: list[int]) -> CircuitInstruction:
        return CircuitInstruction(name="RELAX", targets=targets, gate_args=[self.p])

    @override
    def to_stim_op(self, targets: Sequence[SSAValue]) -> RelaxOp:
        return RelaxOp(targets, self.p)


@dataclass(frozen=True)
class GateNoise:
    """Class for defining the noise to be applied to a gate."""

    before: list[BasePauliNoise] = field(default_factory=list)
    """Noise to be added before the gate."""
    after: list[BasePauliNoise] = field(default_factory=list)
    """Noise to be added after the gate."""


@dataclass(frozen=True)
class MeasurementNoise(GateNoise):
    """Class for defining the noise to be applied to a qubit measurement."""

    bit_flip_p: float = 0.0
    """The probability of the returned classical measurement bit being the wrong result."""

    def __post_init__(self) -> None:
        if self.bit_flip_p > 1:
            warnings.warn(
                NoiseWarning(
                    f"Bit flip noise probability was {self.bit_flip_p}, "
                    "values greater than 1 are capped to 1.0"
                ),
                stacklevel=2,
            )
            object.__setattr__(self, "bit_flip_p", 1.0)


class GateNoiseDict(dict[DeltakitStimGateKey, GateNoise]):
    """Dictionary for storing noise parameters for a number of gate types."""

    @override
    def __getitem__(self, key: DeltakitStimGateKey) -> GateNoise:
        try:
            return super().__getitem__(key)
        except KeyError as exp:
            msg = f"Noise parameters have not been defined for {key} gates"
            raise KeyError(msg) from exp


class MeasurementNoiseDict(dict[MeasurementKey, MeasurementNoise]):
    """Dictionary for storing noise parameters for a number of measurement types."""

    @override
    def __getitem__(self, key: MeasurementKey) -> MeasurementNoise:
        try:
            return super().__getitem__(key)
        except KeyError as exp:
            msg = f"Noise parameters have not been defined for {key} measurements"
            raise KeyError(msg) from exp


class IdleTracker:
    """Track which qubits are idle or resonant idle and the ops executed on them."""

    def __init__(
        self,
        all_qubits: set[SSAValue],
        native_gateset: dict[DeltakitStimQuantumGatesetKey, float]
        | list[DeltakitStimQuantumGatesetKey]
        | None,
    ) -> None:
        self._executed_ops: dict[DeltakitStimQuantumOpEnum, list[int]] = defaultdict(list)
        self._all_qubits = all_qubits
        self.native_gateset = native_gateset
        self._idle_qubits: set[SSAValue] = set(self._all_qubits)
        self._resonant_idle_qubits: set[SSAValue] = set(self._all_qubits)

    def add_idle_qubit(self, target: SSAValue) -> None:
        """Add a qubit to the idle tracking set."""
        self._idle_qubits.add(target)

    def discard_idle_qubit(self, target: SSAValue) -> None:
        """Remove a qubit from the idle tracking set."""
        self._idle_qubits.discard(target)

    def discard_resonant_idle_qubit(self, target: SSAValue) -> None:
        """Remove a qubit from the resonant idle tracking set."""
        self._resonant_idle_qubits.discard(target)

    def reset(self) -> None:
        """Reset the idle tracker to the initial state."""
        self._executed_ops = defaultdict(list)
        self._idle_qubits = set(self._all_qubits)
        self._resonant_idle_qubits = set(self._all_qubits)

    @property
    def executed_ops(self) -> Mapping[DeltakitStimQuantumOpEnum, list[int]]:
        """Get the set of ops executed in this time step."""
        return self._executed_ops

    @property
    def all_qubits(self) -> list[SSAValue]:
        """Get the set of all qubits in this time step as an ordered list of SSA values."""
        return sorted(self._all_qubits, key=lambda x: cast(QubitAllocOp, x.owner).id.data)

    @property
    def idle_qubits(self) -> list[SSAValue]:
        """Get the set of idle qubits in this time step as an ordered list of SSA values."""
        return sorted(self._idle_qubits, key=lambda x: cast(QubitAllocOp, x.owner).id.data)

    @property
    def resonant_idle_qubits(self) -> list[SSAValue]:
        """Get the set of resonant qubits in this time step as an ordered list of SSA values."""
        if len(self._resonant_idle_qubits) == len(self._all_qubits):
            # There are no measurements or resets in this time step,
            # so there are no resonant idle qubits.
            return []
        return sorted(self._resonant_idle_qubits, key=lambda x: cast(QubitAllocOp, x.owner).id.data)

    @property
    def all_idle_qubits(self) -> list[SSAValue]:
        """Get the set of all idle and resonant idle qubits
        in this time step as an ordered list of SSA values."""
        all_idle_qubits = self._idle_qubits.union(self._resonant_idle_qubits)
        return sorted(all_idle_qubits, key=lambda x: cast(QubitAllocOp, x.owner).id.data)


class BaseIdleNoise(ABC):
    """Base class for defining idle noise to be applied on each time step of the circuit."""

    def record_op(
        self,
        idle_tracker: IdleTracker,
        op_type: DeltakitStimQuantumOpEnum,
        targets: Sequence[SSAValue],
    ) -> None:
        """Record how the execution of an op affects idle and resonantor idle qubits."""
        for target in targets:
            idle_tracker.executed_ops[op_type].append(get_qubit_id(target))
            idle_tracker.discard_idle_qubit(target)
            if isinstance(op_type, (ResetEnum, MeasurementEnum, MPPEnum)):
                idle_tracker.discard_resonant_idle_qubit(target)

    def reset(self, idle_tracker: IdleTracker) -> None:
        """Reset the executed op, idle and resonant idle qubits at the end of a time step."""
        idle_tracker.reset()

    @abstractmethod
    def from_executed_ops(
        self,
        executed_ops: Mapping[DeltakitStimQuantumOpEnum, list[int]],
        idle_qubit: int | None = None,
    ) -> list[BasePauliNoise]:
        """Get the noise that should be applied to idle qubits, depending on the types of quantum
        operation done during the time step."""


class NoIdleNoise(BaseIdleNoise):
    """Defines no idle noise."""

    @override
    def from_executed_ops(
        self,
        executed_ops: Mapping[DeltakitStimQuantumOpEnum, list[int]],
        idle_qubit: int | None = None,
    ) -> list[BasePauliNoise]:
        return []


MeasurementNoiseSpec = MeasurementNoise | MeasurementNoiseDict

# label for default qubit initialisation noise
DEFAULT_QUBIT_ID: Final[int] = -1


@dataclass(frozen=True)
class NoiseParameters:
    """Generic class for storing noise model parameters."""

    gates: GateNoiseDict
    """Noise to be applied to gates, indexed by gate names."""
    measurement: MeasurementNoiseSpec
    """Noise to be applied when measuring qubits."""
    idle: BaseIdleNoise
    """Noise to be added to idle qubits on each time step, where a time step is defined as
    the time between TICK/barrier calls."""
    resonant_idle: BaseIdleNoise = field(default_factory=NoIdleNoise)
    """Noise to be added to resonant idle qubits on each time step, where a time step is defined as
    the time between TICK/barrier calls. A resonant idle qubit is one that is not partaking in any
    measurement or reset operations in a given timestep, while other qubits are."""
    leakage_herald: float = 0.0
    """Leakage herald noise to be applied when there is leakage when measuring qubits. """
    initialisation: dict[int, list[BasePauliNoise]] = field(default_factory=dict)
    """Noise to be applied to qubit initialisations, indexed by qubit IDs. If you want
    to apply the same initialisation noise to all not otherwise listed qubits,
    use the key DEFAULT_QUBIT_ID."""
