# This file contains information which is proprietary to Riverlane Ltd
# ("Riverlane") and is Riverlane Confidential Information.

# (c) Copyright Riverlane 2025-2026. All rights reserved.

"""Pass that runs the whole stim import flow pipeline."""

from typing_extensions import override
from xdsl.passes import ModulePass
from xdsl.transforms.canonicalize import CanonicalizePass

from deltakit_compile.passes.common.pipeline import (
    ConfigurablePipeline,
    Configuration,
    configurable_pass,
)
from deltakit_compile.passes.realign_qec_detectors import RealignQecDetectors
from deltakit_compile.passes.stim.gate_layer_parallelise import GateLayerParallelise
from deltakit_compile.passes.stim.remove_stim_ticks import RemoveStimTicks
from deltakit_compile.passes.stim.stim_tag_to_attributes import StimTagToAttributes
from deltakit_compile.passes.stim.stim_to_qcore import StimToQcore
from deltakit_compile.passes.stim.stim_to_qec import StimToQec
from deltakit_compile.passes.stim.stim_to_qref import StimToQref
from deltakit_compile.passes.stim.stim_to_qstruct import StimToQStruct


class StimImportPipelineConfig(Configuration, frozen=True):
    """Configuration for the StimImportPipeline.

    Attributes:
        extract_tags_to_attributes: Whether to extract tags to attributes in the
            StimTagToAttributes pass.

        realign_detectors: whether to realign detectors to better reflect where their measurements
            occur in the circuit.

        respect_tick_parallelisation: If True, the remove-stim-ticks pass is run after the
            gate-layer-parallelise pass, which means that the parallelisation of gates will
            respect the tick boundaries. Otherwise, the remove-stim-ticks pass is run before
            the gate-layer-parallelise pass, which means that the parallelisation of gates will
            not necessarily respect the tick boundaries.
    """

    extract_tags_to_attributes: bool = False
    realign_detectors: bool = True
    respect_tick_parallelisation: bool = True


@configurable_pass
class StimImportPipeline(ConfigurablePipeline[StimImportPipelineConfig]):
    """A pass which runs the stim import pipeline.

    It  converts all ops from the `stim` dialect to the
    `qcore`, `qref`, `qstruct`, and `qec` dialects."""

    name = "stim-import-pipeline"
    realign_detectors: bool = True
    respect_tick_parallelisation: bool = True
    extract_tags_to_attributes: bool = False

    @override
    def get_passes(self) -> tuple[ModulePass, ...]:
        """Get the passes in the stim import pipeline.

        Returns:
            The sequence of passes that make up the stim import pipeline, in execution order.
        """
        passes: list[ModulePass] = [
            StimToQcore(),
            StimToQStruct(),
            StimToQec(),
        ]

        if self.realign_detectors:
            passes.append(RealignQecDetectors())

        passes.append(StimToQref())

        if not self.respect_tick_parallelisation:
            passes.append(RemoveStimTicks())
            passes.append(GateLayerParallelise())
        else:
            passes.append(GateLayerParallelise())
            passes.append(RemoveStimTicks())

        if self.extract_tags_to_attributes:
            passes.append(StimTagToAttributes())
        passes.append(CanonicalizePass())

        return tuple(passes)
