"""Tests for the stabiliser flow pipeline. Most testing is done for individual passes or using
filecheck tests so this only tests config and pipeline creation."""

from deltakit_compile.passes.stabiliser.pipeline import (
    StabiliserFlowPipeline,
    StabiliserFlowPipelineConfig,
)


def test_creation():
    """Test creating the pipeline config and pipeline itself from said config"""

    config1 = StabiliserFlowPipelineConfig()
    config2 = StabiliserFlowPipelineConfig(verify_flows=True, generate_flows=True)
    assert config1 == config2
    config3 = StabiliserFlowPipelineConfig(verify_flows=False, generate_flows=False)

    pipeline1 = StabiliserFlowPipeline.from_configuration(config1)
    pipeline2 = StabiliserFlowPipeline.from_configuration(config3)
    assert pipeline1 != pipeline2
    assert pipeline1.get_passes() != pipeline2.get_passes()
    assert pipeline2 != StabiliserFlowPipeline(
        verify_flows=False, generate_flows=False, verify_between_passes=True
    )
    assert pipeline2 == StabiliserFlowPipeline(
        verify_flows=False, generate_flows=False, verify_between_passes=False
    )
