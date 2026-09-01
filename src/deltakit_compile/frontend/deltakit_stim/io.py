# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module defining the public API methods for working with Deltakit-Stim circuits in
deltakit-compile."""

from deltakit_stim import Circuit
from xdsl.context import Context
from xdsl.dialects.arith import Arith
from xdsl.dialects.builtin import Builtin, ModuleOp
from xdsl.dialects.scf import Scf

from deltakit_compile.dialects.deltakit_stim import DeltakitStim
from deltakit_compile.dialects.qcore import QCore
from deltakit_compile.dialects.qec import Qec
from deltakit_compile.dialects.qref import QRef
from deltakit_compile.dialects.qstruct import QStruct
from deltakit_compile.dialects.stim import Stim, to_stim
from deltakit_compile.frontend.deltakit_stim._translator import DeltakitStimTranslator
from deltakit_compile.passes.stim.stim_export.pipeline import (
    StimExportPipeline,
    StimExportPipelineConfig,
)
from deltakit_compile.passes.stim.stim_import.pipeline import (
    StimImportPipeline,
    StimImportPipelineConfig,
)

DEFAULT_IMPORT_CONFIG = StimImportPipelineConfig()
DEFAULT_EXPORT_CONFIG = StimExportPipelineConfig()


def deltakit_stim_context() -> Context:
    """Returns an xDSL Context object pre-loaded with the appropriate dialects for working with
    Deltakit-Stim and physical circuit IR.

    Keep in mind that, depending on the passes you are running, more dialects may need to be loaded
    using Context.load_dialect().
    """
    ctx = Context()
    ctx.load_dialect(Builtin)
    # Stim-related dialects
    ctx.load_dialect(Stim)
    ctx.load_dialect(DeltakitStim)
    # Physical circuit IR dialects
    ctx.load_dialect(QCore)
    ctx.load_dialect(QRef)
    ctx.load_dialect(QStruct)
    ctx.load_dialect(Qec)
    ctx.load_dialect(Arith)
    ctx.load_dialect(Scf)
    return ctx


def deltakit_stim_circuit_to_dialect(circuit: Circuit) -> ModuleOp:
    """Returns a ModuleOp containing operations from deltakit's stim and deltakit-stim dialects.

    Some gates in the circuit are split into multiple operations in the stim dialect where they are
    semantically equivalent.
    """
    module_op = DeltakitStimTranslator(circuit).to_xdsl_dialect()
    module_op.verify()
    return module_op


def deltakit_stim_dialect_to_circuit(module_op: ModuleOp) -> Circuit:
    """Converts a ModuleOp containing operations from deltakit's stim and deltakit-stim dialects
    into a Deltakit-Stim Circuit object."""
    module_op.verify()
    # TODO: Directly emit ops to Deltakit-Stim circuit objects rather than reparsing from string
    return Circuit(to_stim(module_op))


def deltakit_stim_circuit_to_physical_circuit_ir(
    circuit: Circuit, config: StimImportPipelineConfig = DEFAULT_IMPORT_CONFIG
) -> ModuleOp:
    """Returns a ModuleOp containing operations from the deltakit qcore, qstruct, qref, and qec
    dialects."""
    module_op = deltakit_stim_circuit_to_dialect(circuit)
    pipeline = StimImportPipeline.from_configuration(config)
    pipeline.apply(deltakit_stim_context(), module_op)
    return module_op


def physical_circuit_ir_to_deltakit_stim_circuit(
    module_op: ModuleOp, config: StimExportPipelineConfig = DEFAULT_EXPORT_CONFIG
) -> Circuit:
    """Converts a ModuleOp containing operations from the deltakit qcore, qstruct, qref, and qec
    dialects into a Deltakit-Stim Circuit object."""
    pipeline = StimExportPipeline.from_configuration(config)
    pipeline.apply(deltakit_stim_context(), module_op)
    return deltakit_stim_dialect_to_circuit(module_op)
