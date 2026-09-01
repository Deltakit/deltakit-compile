# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Pass that runs the whole stabiliser flow pipeline."""

from typing_extensions import override
from xdsl.passes import ModulePass
from xdsl.transforms.canonicalize import CanonicalizePass

from deltakit_compile.passes.common.pipeline import (
    ConfigurablePipeline,
    Configuration,
    configurable_pass,
)
from deltakit_compile.passes.infer_detector_coords import InferDetectorCoords
from deltakit_compile.passes.lower_concrete_flows import LowerConcreteFlows
from deltakit_compile.passes.merge_gate_like_broadcast_ops import MergeGateLikeBroadcastOps
from deltakit_compile.passes.qstruct_circuit_to_stab import QStructCircuitToStabPass
from deltakit_compile.passes.split_gate_like_broadcast_ops import SplitGateLikeBroadcastOps
from deltakit_compile.passes.stab_circuit_to_qstruct import StabCircuitToQstruct
from deltakit_compile.passes.stabiliser.find_detectors import FindDetectors
from deltakit_compile.passes.stabiliser.generate_flows import GenerateFlows
from deltakit_compile.passes.stabiliser.merge_circuits import MergeCircuits
from deltakit_compile.passes.stabiliser.remove_non_matching_flows import RemoveNonMatchingFlows
from deltakit_compile.passes.stabiliser.verify_flows import VerifyFlows


class StabiliserFlowPipelineConfig(Configuration, frozen=True):
    verify_flows: bool = True
    """Whether to run the stabiliser flow verification pass as part of the pipeline."""

    generate_flows: bool = True
    """Whether to run the GenerateFlows pass as part of the pipeline."""


@configurable_pass
class StabiliserFlowPipeline(ConfigurablePipeline[StabiliserFlowPipelineConfig]):
    """A pass which runs the stabiliser flow pipeline, which generates detectors automatically."""

    name = "stabiliser-flow-pipeline"

    verify_flows: bool = True
    """Whether to run the stabiliser flow verification pass as part of the pipeline."""

    generate_flows: bool = True
    """Whether to run the GenerateFlows pass as part of the pipeline."""

    @override
    def get_passes(self) -> tuple[ModulePass, ...]:
        passes: list[ModulePass] = [
            SplitGateLikeBroadcastOps(),
            QStructCircuitToStabPass(),
            CanonicalizePass(),
            LowerConcreteFlows(),
        ]

        if self.verify_flows:
            passes.append(VerifyFlows())
        passes.append(RemoveNonMatchingFlows())
        if self.generate_flows:
            passes.append(GenerateFlows())

        passes.extend(
            [
                MergeCircuits(),
                FindDetectors(),
                StabCircuitToQstruct(),
                MergeGateLikeBroadcastOps(),
                InferDetectorCoords(),
                CanonicalizePass(),
            ]
        )

        return tuple(passes)
