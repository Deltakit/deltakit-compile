# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Pass that runs the whole stim export flow pipeline."""

from typing_extensions import override
from xdsl.passes import ModulePass
from xdsl.transforms.canonicalize import CanonicalizePass

from deltakit_compile.passes.combine_detector_rounds import CombineDetectorRounds
from deltakit_compile.passes.common.pipeline import (
    ConfigurablePipeline,
    NamedConfiguration,
    configurable_pass,
)
from deltakit_compile.passes.convert_parallels_to_lockstep import ConvertParallelsToLockstep
from deltakit_compile.passes.flatten_qubit_registers import FlattenQubitRegisters
from deltakit_compile.passes.merge_gate_like_broadcast_ops import MergeGateLikeBroadcastOps
from deltakit_compile.passes.serialise_circuit import SerialiseCircuit
from deltakit_compile.passes.stim.add_stim_ticks import AddStimTicks
from deltakit_compile.passes.stim.lower_physical_to_stim import LowerPhysicalToStim
from deltakit_compile.passes.unitaries_to_named_gates import UnitariesToNamedGates


class StimExportPipelineConfig(NamedConfiguration, frozen=True):
    """Configuration for the StimExportPipeline.

    Attributes:
        unitaries_to_named_gates_precision: The precision to use when matching unitary matrices
            to named gates in the UnitariesToNamedGates pass. This is maximum allowed absolute
            difference between each element of the unitary matrix and the corresponding element
            of the standard gate's matrix representation. Default is 10^-6."""

    unitaries_to_named_gates_precision: float = 1e-6


@configurable_pass
class StimExportPipeline(ConfigurablePipeline[StimExportPipelineConfig]):
    """A pass which runs the stim export pipeline, which converts all ops to the stim dialect."""

    name = "stim-export-pipeline"
    unitaries_to_named_gates_precision: float = 1e-6

    @override
    def get_passes(self) -> tuple[ModulePass, ...]:
        """Get the passes in the stim export pipeline.

        Returns:
            The sequence of passes that make up the stim export pipeline, in execution order.
        """
        return (
            UnitariesToNamedGates(precision=self.unitaries_to_named_gates_precision),
            ConvertParallelsToLockstep(),
            MergeGateLikeBroadcastOps(),
            CombineDetectorRounds(),
            AddStimTicks(),
            SerialiseCircuit(),
            FlattenQubitRegisters(),
            LowerPhysicalToStim(),
            CanonicalizePass(),
        )
