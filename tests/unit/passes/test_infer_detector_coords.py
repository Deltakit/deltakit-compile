"""Exception tests for infer-detector-coords pass (functional testing done using filecheck)."""

import re

import pytest
from xdsl.context import Context
from xdsl.dialects import test
from xdsl.dialects.builtin import ModuleOp, i1

from deltakit_compile.dialects import qcore, qec, qref, scf
from deltakit_compile.passes.infer_detector_coords import InferDetectorCoords


def test_uneven_location_dimensions(xdsl_context: Context):
    """Test that the pass errors when averaging qubit coordinates with uneven dimensions."""

    module_op = ModuleOp(
        [
            test_op := test.TestOp(result_types=[i1]),
            alloc1 := qcore.AllocQubitOp(qcore.QubitType(), [(1.0, 2.0)]),
            alloc2 := qcore.AllocQubitOp(qcore.QubitType(), [(3.0, 4.0, 5.0)]),
            meas1 := qref.MeasureOp("Z", [alloc1.result[0]]),
            meas2 := qref.MeasureOp("Z", [alloc2.result[0]]),
            # return value of this if has both possible coordinates
            if_op := scf.IfOp(
                cond=test_op.res[0],
                return_types=[i1],
                true_region=[scf.YieldOp(meas1.measurements[0])],
                false_region=[scf.YieldOp(meas2.measurements[0])],
            ),
            qec.DetectorOp([if_op.results[0]]),
        ]
    )

    with pytest.raises(
        ValueError, match=re.escape("All qubit coordinates must have the same dimension.")
    ):
        InferDetectorCoords().apply(xdsl_context, module_op)
