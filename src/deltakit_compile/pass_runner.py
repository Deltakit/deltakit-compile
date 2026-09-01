# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module storing a generic compiler pass runner."""

import inspect
from typing import Any

from xdsl.context import Context
from xdsl.dialects.builtin import Builtin, ModuleOp
from xdsl.dialects.test import Test
from xdsl.parser import Parser
from xdsl.passes import ModulePass
from xdsl.transforms.canonicalize import CanonicalizePass

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
from deltakit_compile.dialects.stim import Stim
from deltakit_compile.dialects.tables import Tables
from deltakit_compile.dialects.tensor import Tensor
from deltakit_compile.passes.add_heralds import AddHeralds
from deltakit_compile.passes.add_noise import AddNoise
from deltakit_compile.passes.circuit_builder.pipeline import CircuitBuilderToLogAsmPipeline
from deltakit_compile.passes.collapse_adjacent_alloc import CollapseAdjacentAlloc
from deltakit_compile.passes.combine_detector_rounds import CombineDetectorRounds
from deltakit_compile.passes.convert_parallels_to_lockstep import ConvertParallelsToLockstep
from deltakit_compile.passes.flatten_qubit_registers import FlattenQubitRegisters
from deltakit_compile.passes.infer_detector_coords import InferDetectorCoords
from deltakit_compile.passes.log_asm_api.inline_circuits_and_subroutines import (
    InlineCircuitsAndSubroutines,
)
from deltakit_compile.passes.log_asm_api.lockstep_parallels import LockstepParallels
from deltakit_compile.passes.log_asm_api.lower_qubit_tensors_to_qcore import (
    LowerQubitTensorsToQCore,
)
from deltakit_compile.passes.log_asm_api.parallelise_log_asm_api import ParalleliseLogAsmApi
from deltakit_compile.passes.log_asm_api.pipeline import LogAsmApiToLogAsmPipeline
from deltakit_compile.passes.log_asm_api.split_measurement_tensors import SplitMeasurementTensors
from deltakit_compile.passes.logical_assembly.pipeline import LogicalAssemblerCorePipeline
from deltakit_compile.passes.lower_concrete_flows import LowerConcreteFlows
from deltakit_compile.passes.merge_gate_like_broadcast_ops import MergeGateLikeBroadcastOps
from deltakit_compile.passes.parallelise_circuit import ParalleliseCircuit
from deltakit_compile.passes.patch_lowering.rotated_surface.annotate_flows_from_plaquettes import (
    AnnotateFlowsFromPlaquettes,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.backpropagate_observables import (
    BackpropagateObservables,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.located_observable_to_move import (
    LocatedObservableToMove,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.lower_patch_declaration import (
    LowerPatchDeclaration,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.patch_to_plaquettes import (
    PatchToPlaquettes,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.pipeline import (
    RotatedSurfacePatchLoweringPipeline,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.place_observables import (
    PlaceObservables,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.plaquette_to_circuit import (
    PlaquetteToCircuit,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.plaquette_to_qstruct import (
    PlaquetteToQstruct,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.schedule_plaquettes import (
    SchedulePlaquettes,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.transversal_op_to_circuit import (
    TransversalOpToCircuit,
)
from deltakit_compile.passes.qstruct_circuit_to_stab import QStructCircuitToStabPass
from deltakit_compile.passes.realign_qec_detectors import RealignQecDetectors
from deltakit_compile.passes.remap_qubits import RemapQubits
from deltakit_compile.passes.serialise_circuit import SerialiseCircuit
from deltakit_compile.passes.sobs_to_qec import SobsObservableToQec
from deltakit_compile.passes.split_gate_like_broadcast_ops import SplitGateLikeBroadcastOps
from deltakit_compile.passes.stab_circuit_to_qstruct import StabCircuitToQstruct
from deltakit_compile.passes.stabiliser.expand_states import ExpandStates
from deltakit_compile.passes.stabiliser.find_detectors import FindDetectors
from deltakit_compile.passes.stabiliser.generate_flows import GenerateFlows
from deltakit_compile.passes.stabiliser.merge_circuits import MergeCircuits
from deltakit_compile.passes.stabiliser.pipeline import StabiliserFlowPipeline
from deltakit_compile.passes.stabiliser.remove_non_matching_flows import RemoveNonMatchingFlows
from deltakit_compile.passes.stabiliser.verify_flows import VerifyFlows
from deltakit_compile.passes.stim.add_stim_ticks import AddStimTicks
from deltakit_compile.passes.stim.gate_layer_parallelise import GateLayerParallelise
from deltakit_compile.passes.stim.lower_physical_to_stim import LowerPhysicalToStim
from deltakit_compile.passes.stim.remove_stim_ticks import RemoveStimTicks
from deltakit_compile.passes.stim.stim_export.pipeline import StimExportPipeline
from deltakit_compile.passes.stim.stim_import.pipeline import StimImportPipeline
from deltakit_compile.passes.stim.stim_tag_to_attributes import StimTagToAttributes
from deltakit_compile.passes.stim.stim_to_qcore import StimToQcore
from deltakit_compile.passes.stim.stim_to_qec import StimToQec
from deltakit_compile.passes.stim.stim_to_qref import StimToQref
from deltakit_compile.passes.stim.stim_to_qstruct import StimToQStruct
from deltakit_compile.passes.unitaries_to_named_gates import UnitariesToNamedGates

# Mapping from pass names to classes for all custom passes
PASS_MAP: dict[str, type[ModulePass]] = {
    RemapQubits.name: RemapQubits,
    AddNoise.name: AddNoise,
    ParalleliseCircuit.name: ParalleliseCircuit,
    SerialiseCircuit.name: SerialiseCircuit,
    VerifyFlows.name: VerifyFlows,
    MergeCircuits.name: MergeCircuits,
    FindDetectors.name: FindDetectors,
    GenerateFlows.name: GenerateFlows,
    InferDetectorCoords.name: InferDetectorCoords,
    MergeGateLikeBroadcastOps.name: MergeGateLikeBroadcastOps,
    SplitGateLikeBroadcastOps.name: SplitGateLikeBroadcastOps,
    RemoveNonMatchingFlows.name: RemoveNonMatchingFlows,
    StabiliserFlowPipeline.name: StabiliserFlowPipeline,
    CanonicalizePass.name: CanonicalizePass,
    QStructCircuitToStabPass.name: QStructCircuitToStabPass,
    StabCircuitToQstruct.name: StabCircuitToQstruct,
    LowerConcreteFlows.name: LowerConcreteFlows,
    ConvertParallelsToLockstep.name: ConvertParallelsToLockstep,
    AddStimTicks.name: AddStimTicks,
    LowerPhysicalToStim.name: LowerPhysicalToStim,
    FlattenQubitRegisters.name: FlattenQubitRegisters,
    AddHeralds.name: AddHeralds,
    UnitariesToNamedGates.name: UnitariesToNamedGates,
    StimTagToAttributes.name: StimTagToAttributes,
    StimToQStruct.name: StimToQStruct,
    RemoveStimTicks.name: RemoveStimTicks,
    InlineCircuitsAndSubroutines.name: InlineCircuitsAndSubroutines,
    LowerQubitTensorsToQCore.name: LowerQubitTensorsToQCore,
    GateLayerParallelise.name: GateLayerParallelise,
    StimToQcore.name: StimToQcore,
    CombineDetectorRounds.name: CombineDetectorRounds,
    RealignQecDetectors.name: RealignQecDetectors,
    StimToQref.name: StimToQref,
    BackpropagateObservables.name: BackpropagateObservables,
    StimToQec.name: StimToQec,
    LowerPatchDeclaration.name: LowerPatchDeclaration,
    StimExportPipeline.name: StimExportPipeline,
    StimImportPipeline.name: StimImportPipeline,
    SplitMeasurementTensors.name: SplitMeasurementTensors,
    LogAsmApiToLogAsmPipeline.name: LogAsmApiToLogAsmPipeline,
    ExpandStates.name: ExpandStates,
    PlaceObservables.name: PlaceObservables,
    PatchToPlaquettes.name: PatchToPlaquettes,
    LocatedObservableToMove.name: LocatedObservableToMove,
    SchedulePlaquettes.name: SchedulePlaquettes,
    PlaquetteToCircuit.name: PlaquetteToCircuit,
    TransversalOpToCircuit.name: TransversalOpToCircuit,
    AnnotateFlowsFromPlaquettes.name: AnnotateFlowsFromPlaquettes,
    PlaquetteToQstruct.name: PlaquetteToQstruct,
    ParalleliseLogAsmApi.name: ParalleliseLogAsmApi,
    LockstepParallels.name: LockstepParallels,
    RotatedSurfacePatchLoweringPipeline.name: RotatedSurfacePatchLoweringPipeline,
    CircuitBuilderToLogAsmPipeline.name: CircuitBuilderToLogAsmPipeline,
    LogicalAssemblerCorePipeline.name: LogicalAssemblerCorePipeline,
    CollapseAdjacentAlloc.name: CollapseAdjacentAlloc,
    SobsObservableToQec.name: SobsObservableToQec,
}


ArgumentDict = dict[str, Any]


class PassRunner:
    """Generic compiler pass runner.
    With this you can run any passes in any order with any arguments with no guard rails (for test
    purposes)."""

    def __init__(self, *, include_test_dialect: bool = False) -> None:
        self._xdsl_context = Context()
        self._xdsl_context.load_dialect(QCore)
        self._xdsl_context.load_dialect(QRef)
        self._xdsl_context.load_dialect(LogicalAsm)
        self._xdsl_context.load_dialect(LogAsmApi)
        self._xdsl_context.load_dialect(Stim)
        self._xdsl_context.load_dialect(DeltakitStim)
        self._xdsl_context.load_dialect(Plaquette)
        self._xdsl_context.load_dialect(QStruct)
        self._xdsl_context.load_dialect(Qec)
        self._xdsl_context.load_dialect(Builtin)
        self._xdsl_context.load_dialect(Arith)
        self._xdsl_context.load_dialect(Scf)
        self._xdsl_context.load_dialect(Sobs)
        self._xdsl_context.load_dialect(Stab)
        self._xdsl_context.load_dialect(Tensor)
        self._xdsl_context.load_dialect(Func)
        self._xdsl_context.load_dialect(Tables)
        if include_test_dialect:
            self._xdsl_context.load_dialect(Test)

    def _parse_program(self, program: str) -> list[ModuleOp]:
        """Split the program into chunks at every '// ----' in the text and parse each chunk into a
        module op."""
        programs = program.split("// ----")
        return [Parser(self._xdsl_context, p).parse_module() for p in programs]

    @classmethod
    def _print_program(cls, module_ops: list[ModuleOp]) -> str:
        """Combine a series of module ops into a single program string, '// ----' used to separate
        the output of each module op."""
        return "\n// ----\n".join([str(module_op) for module_op in module_ops])

    @classmethod
    def _filter_pass_args(
        cls, pass_class: type[ModulePass], pass_args: ArgumentDict
    ) -> ArgumentDict:
        """Filter pass_args to only contain arguments that exist in the __init__ of pass_class."""
        class_args = set(inspect.signature(pass_class).parameters)
        filtered_args_keys = set(pass_args).intersection(class_args)
        return {k: v for k, v in pass_args.items() if k in filtered_args_keys}

    def _apply_passes(
        self, module_op: ModuleOp, passes: list[str], pass_args: ArgumentDict
    ) -> None:
        """Apply passes on a single module_op."""
        module_op.verify()

        for pass_name in passes:
            pass_class = PASS_MAP[pass_name]
            filtered_pass_args = self._filter_pass_args(pass_class, pass_args)
            pass_class(**filtered_pass_args).apply(self._xdsl_context, module_op)

        module_op.verify()

    def run(self, program: str, passes: list[str], pass_args: ArgumentDict) -> str:
        """Run a list of compiler passes on the provided MLIR program."""
        module_ops = self._parse_program(program)

        for module_op in module_ops:
            self._apply_passes(module_op, passes, pass_args)

        return self._print_program(module_ops)
