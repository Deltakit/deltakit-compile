# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for the Logical Assembler's core pipeline from logical assembly to physical circuit IR."""

from typing_extensions import override
from xdsl.passes import ModulePass
from xdsl.transforms.canonicalize import CanonicalizePass

from deltakit_compile.passes.common.pipeline import (
    ConfigurablePipeline,
    Configuration,
    NamedConfiguration,
    NamedConfigurations,
    configurable_pass,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.pipeline import (
    RotatedSurfacePatchLoweringPipeline,
    RotatedSurfacePatchLoweringPipelineConfig,
)
from deltakit_compile.passes.stabiliser.pipeline import (
    StabiliserFlowPipeline,
    StabiliserFlowPipelineConfig,
)
from deltakit_compile.passes.stim.stim_export.pipeline import (
    StimExportPipeline,
    StimExportPipelineConfig,
)


class PhysicalCircuitIRExportConfig(NamedConfiguration, frozen=True):
    """A export configuration for compiling to our physical circuit IR format.

    There are no options to choose when exporting to physical circuit IR."""


class LogicalAssemblerCoreConfig(Configuration, frozen=True):
    """The Configuration for the ``LogicalAssemblerCorePipeline``."""

    stabiliser_flow_config: StabiliserFlowPipelineConfig | None = StabiliserFlowPipelineConfig()
    """The configuration used to compute stabiliser flows, or None if this pipeline should be
    skipped entirely. """

    export_config: NamedConfigurations[PhysicalCircuitIRExportConfig | StimExportPipelineConfig] = (
        PhysicalCircuitIRExportConfig()
    )
    """Specifies the compilation target and export options using with the respective export
    pipeline."""

    verify_between_passes: bool = False
    """A debugging option that, if set, enables verification of the program's intermediate
    representation at each stage of compilation, at the cost of runtime performance."""


@configurable_pass
class LogicalAssemblerCorePipeline(ConfigurablePipeline[LogicalAssemblerCoreConfig]):
    """A pass pipeline that aggregates together everything needed to go from logical assembly
    through to physical circuit IR, and optionally then to stim IR"""

    name = "logical-assembler-core-pipeline"

    stabiliser_flow_config: StabiliserFlowPipelineConfig | None = StabiliserFlowPipelineConfig()
    export_config: PhysicalCircuitIRExportConfig | StimExportPipelineConfig = (
        PhysicalCircuitIRExportConfig()
    )
    patch_lowering_config: RotatedSurfacePatchLoweringPipelineConfig = (
        RotatedSurfacePatchLoweringPipelineConfig()
    )

    @override
    def get_passes(self) -> tuple[ModulePass, ...]:
        passes: list[ModulePass] = []
        passes.append(CanonicalizePass())
        passes.extend(
            RotatedSurfacePatchLoweringPipeline.from_configuration(
                self.patch_lowering_config
            ).get_passes()
        )
        if self.stabiliser_flow_config:
            passes.extend(
                StabiliserFlowPipeline.from_configuration(self.stabiliser_flow_config).get_passes()
            )
            passes.append(CanonicalizePass())
        # passes.extend(QPUSpecialisationPipeline().get_passes()), TODO
        if isinstance(self.export_config, StimExportPipelineConfig):
            passes.extend(StimExportPipeline.from_configuration(self.export_config).get_passes())
            passes.append(CanonicalizePass())
        return tuple(passes)
