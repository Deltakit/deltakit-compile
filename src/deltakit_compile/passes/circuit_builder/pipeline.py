# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Pass that runs the circuit builder API to logical assembly dialect pipeline."""

from typing import Annotated, ClassVar

from typing_extensions import override
from xdsl.passes import ModulePass
from xdsl.transforms.canonicalize import CanonicalizePass
from xdsl.transforms.common_subexpression_elimination import CommonSubexpressionElimination

from deltakit_compile.dialects.log_asm_api import LOCKSTEP_PARALLEL_ATTRIBUTE
from deltakit_compile.passes.common.pipeline import (
    ConfigurablePipeline,
    FieldPathSpec,
    configurable_pass,
)
from deltakit_compile.passes.log_asm_api.inline_circuits_and_subroutines import (
    InlineCircuitsAndSubroutines,
    InlineCircuitsAndSubroutinesConfig,
)
from deltakit_compile.passes.log_asm_api.lockstep_parallels import (
    LockstepParallels,
    LockstepParallelsConfig,
)
from deltakit_compile.passes.log_asm_api.lower_qubit_tensors_to_qcore import (
    LowerQubitTensorsToQCore,
)
from deltakit_compile.passes.log_asm_api.split_measurement_tensors import SplitMeasurementTensors


class CircuitBuilderToLogAsmPipelineConfig(InlineCircuitsAndSubroutinesConfig, frozen=True):
    """Configuration for the Circuit Builder API to Logical Assembly pipeline.
    Subclasses ``InlineCircuitsAndSubroutinesConfig`` to get all its options, and overrides two with
    new default values. See ``InlineCircuitsAndSubroutinesConfig`` for details of each option."""

    error_on_circuits_not_inlined: bool = True
    error_on_functions_not_inlined: bool = True

    lockstep_parallels_config: LockstepParallelsConfig = LockstepParallelsConfig(
        expected_attribute=LOCKSTEP_PARALLEL_ATTRIBUTE, skipped_operations=("qec.detector",)
    )


@configurable_pass
class CircuitBuilderToLogAsmPipeline(ConfigurablePipeline[CircuitBuilderToLogAsmPipelineConfig]):
    """A pass which runs the Circuit Builder API to logical assembly dialect pipeline."""

    name = "circuit-builder-to-logasm-pipeline"

    _DEFAULT_CONFIG: ClassVar[CircuitBuilderToLogAsmPipelineConfig] = (
        CircuitBuilderToLogAsmPipelineConfig()
    )

    lockstep_parallels_config: LockstepParallelsConfig | str = (
        _DEFAULT_CONFIG.lockstep_parallels_config
    )

    inline_circuits_and_subroutines_config: Annotated[
        str | InlineCircuitsAndSubroutinesConfig, FieldPathSpec(field_name=".")
    ] = _DEFAULT_CONFIG

    @override
    def get_passes(self) -> tuple[ModulePass, ...]:
        assert isinstance(
            self.inline_circuits_and_subroutines_config, InlineCircuitsAndSubroutinesConfig
        )
        assert isinstance(self.lockstep_parallels_config, LockstepParallelsConfig)
        passes: list[ModulePass] = [
            CanonicalizePass(),
            CommonSubexpressionElimination(),
            LockstepParallels.from_configuration(self.lockstep_parallels_config),
            InlineCircuitsAndSubroutines.from_configuration(
                self.inline_circuits_and_subroutines_config
            ),
            LowerQubitTensorsToQCore(),
            SplitMeasurementTensors(),
        ]

        return tuple(passes)
