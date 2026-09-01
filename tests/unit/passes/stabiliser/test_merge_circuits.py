"""Exception tests for the merge-circuits pass."""

import re

import pytest
from xdsl.dialects import test
from xdsl.dialects.builtin import ModuleOp

from deltakit_compile.dialects import qcore
from deltakit_compile.dialects import stabiliser as stab
from deltakit_compile.exceptions import BadUserFlowError
from deltakit_compile.passes.stabiliser.merge_circuits import MergeCircuits


@pytest.mark.parametrize(
    ("first_flows", "second_flows", "missing_message"),
    [
        pytest.param(
            None,
            None,
            "Missing flows ending with stabilisers: [Z0].\n",
            id="no-flows-on-both-circuits",
        ),
        pytest.param(
            [],
            [],
            "Missing flows ending with stabilisers: [Z0].\n",
            id="insufficient-flows-on-both-circuits",
        ),
        pytest.param(
            [],
            [stab.FlowAttr("+", [], qcore.I_STATE_INDEX, 0)],
            "Missing flows ending with stabilisers: [Z0].\n",
            id="insufficient-flows-on-first-circuit",
        ),
        pytest.param(
            [stab.FlowAttr("+", [], qcore.I_STATE_INDEX, 0)],
            [],
            "Missing flows starting with stabilisers: [Z0].\n",
            id="insufficient-flows-on-second-circuit",
        ),
    ],
)
def test_merge_circuits_reports_missing_flows(
    xdsl_context,
    first_flows: list[stab.FlowAttr] | None,
    second_flows: list[stab.FlowAttr] | None,
    missing_message: str,
) -> None:
    """Report missing flow annotations before attempting to merge circuits."""
    empty_state = stab.StateType(1, qcore.QubitType(), [])
    z0_state = stab.StateType(1, qcore.QubitType(), [qcore.PauliStringAttr([("Z", 0)], 1)])

    initial = test.TestOp(result_types=[empty_state])
    first = stab.CircuitOp(
        initial.res[0], z0_state, input_args=[], body=[stab.YieldOp([], [])], flows=first_flows
    )
    second = stab.CircuitOp(
        first.output, empty_state, input_args=[], body=[stab.YieldOp([], [])], flows=second_flows
    )
    module = ModuleOp([initial, first, second])

    expected_message = (
        "Some flows which are specified on neighbouring circuits are missing on this circuit.\n"
        f"{missing_message}"
        "Please add these flows, remove the corresponding stabilisers from the neighbouring "
        "circuits, or enable automatic flow generation."
    )

    with pytest.raises(BadUserFlowError, match=re.escape(expected_message)):
        MergeCircuits().apply(xdsl_context, module)
