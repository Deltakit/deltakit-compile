import re

import pytest
import xdsl.dialects.test as t
from xdsl.context import Context
from xdsl.dialects import tensor
from xdsl.dialects.builtin import (
    DYNAMIC_INDEX,
    DenseArrayBase,
    ModuleOp,
    TensorType,
    UnrealizedConversionCastOp,
    i1,
    i64,
)

from deltakit_compile.exceptions import CompilerPassCheckError, InvalidQubitTensorError
from deltakit_compile.passes.log_asm_api.split_measurement_tensors import SplitMeasurementTensors


def test_invalid_tensor_extract_slice_op(xdsl_context: Context) -> None:
    op = ModuleOp(
        [
            split_i1s_op := t.TestOp(result_types=[i1 for _ in range(5)]),
            cast_op := UnrealizedConversionCastOp.get(split_i1s_op.res, (TensorType(i1, [5]),)),
            slice_op := tensor.ExtractSliceOp.build(
                operands=(cast_op.outputs, [], [], []),
                properties={
                    "static_offsets": DenseArrayBase.from_list(i64, [0]),
                    "static_sizes": DenseArrayBase.from_list(i64, [2]),
                    "static_strides": DenseArrayBase.from_list(i64, [1000]),
                },
                result_types=((TensorType(i1, [2]),)),
            ),
            t.TestOp(operands=slice_op.results),
        ]
    )
    module_pass = SplitMeasurementTensors()
    with pytest.raises(
        InvalidQubitTensorError,
        match=re.escape(
            "Couldn't handle a tensor.extract_slice when splitting measurement tensors. "
            "Expected to get 2 measurements with offset 0 and stride 1000 "
            "but got 1 from measurements[0:2000:1000]"
        ),
    ):
        module_pass.apply(xdsl_context, op)


def test_unresolved_casts_error(xdsl_context) -> None:
    op = ModuleOp(
        [
            alloc := t.TestOp(result_types=[i1, i1, i1]),
            from_elem := tensor.FromElementsOp(*alloc.results, result_type=TensorType(i1, [3])),
            t.TestOp(operands=(from_elem.result,)),
        ]
    )
    op.verify()
    module_pass = SplitMeasurementTensors()
    with pytest.raises(
        CompilerPassCheckError,
        match=re.compile(
            r"split-measurement-tensors pass failed to reconcile all casts when lowering(\n|.)*"
            r"Cast from i1, i1, i1 to tensor<3xi1> could not be resolved. "
            r"This is because lowering through the following operations failed: test.op",
        ),
    ):
        module_pass.apply(xdsl_context, op)


def test_leftover_measurement_tensors_error(xdsl_context) -> None:
    op = ModuleOp(
        [
            meas_op := t.TestOp(result_types=[i1, i1, i1, i1, i1]),
            cast_op := UnrealizedConversionCastOp.get(meas_op.res, (TensorType(i1, [5]),)),
            t.TestOp(operands=cast_op.outputs),
        ]
    )
    op.verify()
    module_pass = SplitMeasurementTensors()
    with pytest.raises(
        CompilerPassCheckError,
        match=re.escape("Found leftover measurement tensor operand. test.op could not be lowered."),
    ):
        module_pass.apply(xdsl_context, op)

    op = ModuleOp(
        [
            meas_op := t.TestOp(result_types=[TensorType(i1, [DYNAMIC_INDEX])]),
            t.TestOp(operands=meas_op.results),
        ]
    )
    op.verify()
    module_pass = SplitMeasurementTensors()
    with pytest.raises(
        CompilerPassCheckError,
        match=re.escape(
            "split-measurement-tensors pass failed to lower all measurement tensors, "
            "test.op could not be lowered"
        ),
    ):
        module_pass.apply(xdsl_context, op)
