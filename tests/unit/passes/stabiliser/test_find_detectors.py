# This file contains information which is proprietary to Riverlane Limited
# ("Riverlane") and is Riverlane Confidential Information.

# (c) Copyright Riverlane 2026. All rights reserved.
"""Exception tests for find-detectors pass (functional testing done using filecheck)."""

import re

import pytest
from xdsl.dialects import test
from xdsl.dialects.builtin import ModuleOp

import deltakit_compile.dialects.stabiliser as stab
from deltakit_compile.exceptions import BadUserFlowError
from deltakit_compile.passes.stabiliser.find_detectors import FindDetectors


def test_with_no_flow_annotations(xdsl_context):
    """Test that it throws an error if the circuit has no flow annotations but has flows in its
    state type."""

    init_op = test.TestOp(result_types=[stab.StateType(10, test.TestType("q"), [[("X", 0)]])])
    circuit_op = stab.CircuitOp(
        input_state=init_op.res[0],
        output_state_type=stab.StateType(10, test.TestType("q"), []),
        input_args=[],
        body=[stab.YieldOp([], [])],
        flows=None,
    )
    module_op = ModuleOp([init_op, circuit_op])

    with pytest.raises(
        BadUserFlowError,
        match=re.escape(
            "Some flows which are specified on neighbouring circuits are missing on this circuit.\n"
            "Missing flows starting with stabilisers: [X0].\n"
            "Please add these flows, remove the corresponding stabilisers from the neighbouring "
            "circuits, or enable automatic flow generation."
        ),
    ):
        FindDetectors().apply(xdsl_context, module_op)


def test_with_insufficient_flow_annotations(xdsl_context):
    """Test that it throws an error if the circuit has insufficient flow annotations."""

    flows = [[("X", 0)], [("Z", 1)]]
    init_op = test.TestOp(result_types=[stab.StateType(10, test.TestType("q"), flows)])
    circuit_op = stab.CircuitOp(
        input_state=init_op.res[0],
        output_state_type=stab.StateType(10, test.TestType("q"), flows),
        input_args=[],
        body=[stab.YieldOp([], [])],
        flows=[stab.FlowAttr(sign="+", measurements=[], input_state=0, output_state=1)],
    )
    module_op = ModuleOp([init_op, circuit_op])

    with pytest.raises(
        BadUserFlowError,
        match=re.escape(
            "Some flows which are specified on neighbouring circuits are missing on this circuit.\n"
            "Missing flows starting with stabilisers: [Z1].\n"
            "Missing flows ending with stabilisers: [X0].\n"
            "Please add these flows, remove the corresponding stabilisers from the neighbouring "
            "circuits, or enable automatic flow generation."
        ),
    ):
        FindDetectors().apply(xdsl_context, module_op)


def test_with_unknown_state_origin(xdsl_context):
    """Test that it throws an error if the circuit's input state originates from an unknown op."""

    init_op = test.TestOp(result_types=[stab.StateType(10, test.TestType("q"), [[("X", 0)]])])
    circuit_op = stab.CircuitOp(
        input_state=init_op.res[0],
        output_state_type=stab.StateType(10, test.TestType("q"), [[("X", 0)]]),
        input_args=[],
        body=[stab.YieldOp([], [])],
        flows=[stab.FlowAttr(sign="+", measurements=[], input_state=0, output_state=0)],
    )
    module_op = ModuleOp([circuit_op])

    with pytest.raises(
        KeyError,
        match=r"Measurements for stabiliser state .*, flow state #qcore.pauli_string<X0 : 10> "
        "not found!",
    ):
        FindDetectors().apply(xdsl_context, module_op)
