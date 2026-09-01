# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for Deltakit-Compile's LogicalAssembler Compiler"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from typing_extensions import override
from xdsl.dialects.builtin import Builtin, ModuleOp
from xdsl.passes import ModulePass
from xdsl.transforms.canonicalize import CanonicalizePass

from deltakit_compile.context import Context
from deltakit_compile.dialects.arith import Arith
from deltakit_compile.dialects.deltakit_stim import DeltakitStim
from deltakit_compile.dialects.func import Func
from deltakit_compile.dialects.log_asm_api import LogAsmApi
from deltakit_compile.dialects.logical_assembly import LogicalAsm
from deltakit_compile.dialects.plaquette import Plaquette
from deltakit_compile.dialects.qcore import QCore
from deltakit_compile.dialects.qec import Qec
from deltakit_compile.dialects.qref import QRef
from deltakit_compile.dialects.qstruct import QStruct
from deltakit_compile.dialects.scf import Scf
from deltakit_compile.dialects.sobs import Sobs
from deltakit_compile.dialects.stabiliser import Stab
from deltakit_compile.dialects.stim import Stim, to_stim
from deltakit_compile.dialects.tensor import Tensor
from deltakit_compile.frontend.circuit_builder import CircuitProgram
from deltakit_compile.frontend.logasm import LogAsmProgram
from deltakit_compile.passes.circuit_builder.pipeline import (
    CircuitBuilderToLogAsmPipeline,
    CircuitBuilderToLogAsmPipelineConfig,
)
from deltakit_compile.passes.common.pipeline import (
    ConfigurablePipeline,
    configurable_pass,
)
from deltakit_compile.passes.log_asm_api.pipeline import (
    LogAsmApiToLogAsmPipeline,
    LogAsmApiToLogAsmPipelineConfig,
)
from deltakit_compile.passes.logical_assembly.pipeline import (
    LogicalAssemblerCoreConfig,
    LogicalAssemblerCorePipeline,
    PhysicalCircuitIRExportConfig,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.pipeline import (
    RotatedSurfacePatchLoweringPipelineConfig,
)
from deltakit_compile.passes.stabiliser.pipeline import (
    StabiliserFlowPipelineConfig,
)
from deltakit_compile.passes.stim.stim_export.pipeline import (
    StimExportPipelineConfig,
)


@dataclass
class CompilationResult:
    """The result of Logical Assembler compilation."""

    program: str
    """The primary output of compilation"""
    module: ModuleOp
    """The last xDSL based IR for the compiled program before producing the output string"""
    auxiliary_outputs: Mapping[str, Any]
    """Auxiliary compilation results produced during compilation such as debug information, logs,
    or IR from different stages of compilation."""


class LogicalAssemblerConfig(LogicalAssemblerCoreConfig, frozen=True):
    """The Configuration for the LogicalAssembler."""

    api_to_logasm_config: LogAsmApiToLogAsmPipelineConfig = LogAsmApiToLogAsmPipelineConfig()
    """The configuration used to lower from Logical Assembly API IR to Logical Assembly dialect"""

    circuit_builder_to_logasm_config: CircuitBuilderToLogAsmPipelineConfig = (
        CircuitBuilderToLogAsmPipelineConfig()
    )
    """The configuration used to lower from Circuit Builder API to Logical Assembly dialect"""


@configurable_pass
class LogicalAssemblerFromApiPipeline(ConfigurablePipeline[LogicalAssemblerConfig]):
    """A pass pipeline that adds to the ``LogicalAssemblerCorePipeline`` to start at Logical
    Assembly API, rather than Logical Assembly."""

    api_to_logasm_config: LogAsmApiToLogAsmPipelineConfig = LogAsmApiToLogAsmPipelineConfig()
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
            LogAsmApiToLogAsmPipeline.from_configuration(self.api_to_logasm_config).get_passes()
        )
        passes.extend(
            LogicalAssemblerCorePipeline(
                self.stabiliser_flow_config, self.export_config, self.patch_lowering_config
            ).get_passes()
        )
        return tuple(passes)


@configurable_pass
class LogicalAssemblerFromCircuitBuilderPipeline(ConfigurablePipeline[LogicalAssemblerConfig]):
    """A pass pipeline that adds to the ``LogicalAssemblerCorePipeline`` to start at Circuit
    Builder API, rather than Logical Assembly."""

    circuit_builder_to_logasm_config: CircuitBuilderToLogAsmPipelineConfig = (
        CircuitBuilderToLogAsmPipelineConfig()
    )
    stabiliser_flow_config: StabiliserFlowPipelineConfig | None = StabiliserFlowPipelineConfig()
    export_config: PhysicalCircuitIRExportConfig | StimExportPipelineConfig = (
        PhysicalCircuitIRExportConfig()
    )

    @override
    def get_passes(self) -> tuple[ModulePass, ...]:
        passes: list[ModulePass] = []
        passes.append(CanonicalizePass())
        passes.extend(
            CircuitBuilderToLogAsmPipeline.from_configuration(
                self.circuit_builder_to_logasm_config
            ).get_passes()
        )
        passes.extend(
            LogicalAssemblerCorePipeline(
                self.stabiliser_flow_config, self.export_config
            ).get_passes()
        )
        return tuple(passes)


@dataclass
class LogicalAssembler:
    """The interface for compiling Logical Assembly and Circuit Builder programs.

    Compiling directly from logical assembly IR is also supported. Compilation is to our physical
    circuit IR (to be passed to e.g. deltakit-simulate) or to Deltakit-Stim.
    """

    config: LogicalAssemblerConfig = field(default_factory=LogicalAssemblerConfig)

    def compile(self, program: LogAsmProgram | CircuitProgram | ModuleOp) -> CompilationResult:
        """Compile a Logical Assembly API, Circuit Builder, or Logical Assembly IR program into a
        physical circuit.

        Args:
            program: The program to compile from a `LogAsmBuilder`, `CircuitProgramBuilder`, or
                already as a `ModuleOp`.

        Returns:
            A compiled quantum circuit implementing the given program, and the requested auxiliary
            outputs produced during compilation.
        """
        if isinstance(program, LogAsmProgram):
            program = program.module
            pipeline: ConfigurablePipeline = LogicalAssemblerFromApiPipeline.from_configuration(
                self.config
            )
        elif isinstance(program, CircuitProgram):
            program = program.module
            pipeline = LogicalAssemblerFromCircuitBuilderPipeline.from_configuration(self.config)
        else:
            pipeline = LogicalAssemblerCorePipeline.from_configuration(self.config)

        context = self.make_context()
        pipeline.apply(context, program)

        output_string = (
            to_stim(program)
            if isinstance(self.config.export_config, StimExportPipelineConfig)
            else str(program)
        )

        return CompilationResult(output_string, program, context.auxiliary_outputs)

    @staticmethod
    def make_context() -> Context:
        xdsl_context = Context()
        xdsl_context.load_dialect(QCore)
        xdsl_context.load_dialect(QRef)
        xdsl_context.load_dialect(LogicalAsm)
        xdsl_context.load_dialect(LogAsmApi)
        xdsl_context.load_dialect(Stim)
        xdsl_context.load_dialect(DeltakitStim)
        xdsl_context.load_dialect(Plaquette)
        xdsl_context.load_dialect(QStruct)
        xdsl_context.load_dialect(Qec)
        xdsl_context.load_dialect(Builtin)
        xdsl_context.load_dialect(Arith)
        xdsl_context.load_dialect(Scf)
        xdsl_context.load_dialect(Sobs)
        xdsl_context.load_dialect(Stab)
        xdsl_context.load_dialect(Tensor)
        xdsl_context.load_dialect(Func)
        return xdsl_context
