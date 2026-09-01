"""Tests for rotated surface patch-lowering pipeline."""

from deltakit_compile.passes.patch_lowering.rotated_surface._placement import (
    ObservablePlacementStrategy,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.pipeline import (
    RotatedSurfacePatchLoweringPipeline,
    RotatedSurfacePatchLoweringPipelineConfig,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.place_observables import (
    PlaceObservables,
)


def test_configuration_round_trips_with_named_observable_strategy() -> None:
    config = RotatedSurfacePatchLoweringPipelineConfig(
        observable_placement_strategy=ObservablePlacementStrategy.PRE_DEFINED_BOTTOM_RIGHT
    )

    yaml_config = str(config)
    round_tripped = RotatedSurfacePatchLoweringPipelineConfig.from_str(yaml_config)

    assert "observable_placement_strategy: PRE_DEFINED_BOTTOM_RIGHT" in yaml_config
    assert "!!python/" not in yaml_config
    assert round_tripped == config


def test_non_default_named_strategy_propagates_to_place_observables_pass() -> None:
    """A non-default scalar strategy value should configure PlaceObservables correctly."""
    config = RotatedSurfacePatchLoweringPipelineConfig.model_validate(
        {"observable_placement_strategy": "PRE_DEFINED_CENTER_LEFT"}
    )

    passes = RotatedSurfacePatchLoweringPipeline.passes_from_configuration(config)
    place_observables_pass = next(p for p in passes if isinstance(p, PlaceObservables))

    assert place_observables_pass.strategy is ObservablePlacementStrategy.PRE_DEFINED_CENTER_LEFT
