import re

import pytest
from xdsl.context import Context
from xdsl.dialects import test as t
from xdsl.dialects.builtin import (
    DYNAMIC_INDEX,
    DenseArrayBase,
    IndexType,
    ModuleOp,
    TensorType,
    UnrealizedConversionCastOp,
    i64,
)
from xdsl.ir import Block

from deltakit_compile.dialects import log_asm_api as api
from deltakit_compile.dialects import qcore, scf, tensor
from deltakit_compile.exceptions import CompilerPassCheckError, InvalidQubitTensorError
from deltakit_compile.passes.log_asm_api.lower_qubit_tensors_to_qcore import (
    LowerQubitTensorsToQCore,
)


def test_invalid_unsized_gate_op(xdsl_context: Context) -> None:
    op = ModuleOp(
        [
            qubits_op := t.TestOp(result_types=[qcore.QubitRegType(5)]),
            cast_op := UnrealizedConversionCastOp.get(
                qubits_op.res, (TensorType(qcore.QubitType(), [DYNAMIC_INDEX]),)
            ),
            api.UnsizedGateOp(qcore.ISWAPGateAttr(), cast_op.outputs[0]),
        ]
    )
    module_pass = LowerQubitTensorsToQCore()
    with pytest.raises(
        InvalidQubitTensorError,
        match=re.escape(
            "Cannot convert qubit tensor tensor<?x!qcore.qubit> to !qcore.qubit_reg<5>. "
            "A register of 5 qubits is incompatible with a #qcore.gate.iswap that uses 2 qubits."
        ),
    ):
        module_pass.apply(xdsl_context, op)


def test_invalid_tensor_extract_slice_op(xdsl_context: Context) -> None:
    op = ModuleOp(
        [
            qubits_op := t.TestOp(result_types=[qcore.QubitRegType(5)]),
            cast_op := UnrealizedConversionCastOp.get(
                qubits_op.res, (TensorType(qcore.QubitType(), [DYNAMIC_INDEX]),)
            ),
            slice_op := tensor.ExtractSliceOp.build(
                operands=(cast_op.outputs, [], [], []),
                properties={
                    "static_offsets": DenseArrayBase.from_list(i64, [0]),
                    "static_sizes": DenseArrayBase.from_list(i64, [2]),
                    "static_strides": DenseArrayBase.from_list(i64, [1000]),
                },
                result_types=((TensorType(qcore.QubitType(), [2]),)),
            ),
            t.TestOp(operands=slice_op.results),
        ]
    )
    module_pass = LowerQubitTensorsToQCore()
    with pytest.raises(
        InvalidQubitTensorError,
        match=re.escape(
            "Cannot extract a slice from !qcore.qubit_reg<5>. "
            "Expected to get 2 qubits with offset 0 and stride 1000 "
            "but got 1 from qubits[0:2000:1000]"
        ),
    ):
        module_pass.apply(xdsl_context, op)


def test_unresolved_casts_error(xdsl_context) -> None:
    op = ModuleOp(
        [
            alloc := qcore.AllocQubitOp([qcore.QubitRegType(5)]),
            api_cast := api.CastOp(alloc.result[0], TensorType(qcore.QubitType(), [DYNAMIC_INDEX])),
            t.TestOp(operands=(api_cast.result,)),
        ]
    )
    op.verify()
    module_pass = LowerQubitTensorsToQCore()
    with pytest.raises(
        CompilerPassCheckError,
        match=re.compile(
            r"lower-qubit-tensors-to-qcore pass failed to reconcile all casts when lowering(\n|.)*"
            r"Cast from !qcore.qubit_reg<5> to tensor<\?x!qcore.qubit> could not be resolved. "
            r"This is because lowering through the following operations failed: test.op",
        ),
    ):
        module_pass.apply(xdsl_context, op)

    for_loop_body = Block(
        arg_types=(
            IndexType(),
            TensorType(qcore.QubitType(), [DYNAMIC_INDEX]),
            TensorType(qcore.QubitType(), [DYNAMIC_INDEX]),
        )
    )
    for_loop_body.add_op(scf.YieldOp(*reversed(for_loop_body.args[1:])))
    op = ModuleOp(
        [
            alloc1 := qcore.AllocQubitOp([qcore.QubitRegType(5)]),
            alloc2 := qcore.AllocQubitOp([qcore.QubitRegType(420)]),
            index_op := t.TestOp(result_types=[IndexType()]),
            api_cast1 := api.CastOp(
                alloc1.result[0], TensorType(qcore.QubitType(), [DYNAMIC_INDEX])
            ),
            api_cast2 := api.CastOp(
                alloc2.result[0], TensorType(qcore.QubitType(), [DYNAMIC_INDEX])
            ),
            for_op := scf.ForOp(
                index_op, index_op, index_op, (api_cast1.result, api_cast2.result), for_loop_body
            ),
            api.UnsizedResetOp(qcore.PauliAttr.X(), for_op.res[0]),
        ]
    )
    module_pass = LowerQubitTensorsToQCore()
    with pytest.raises(
        CompilerPassCheckError,
        match=re.compile(
            r"lower-qubit-tensors-to-qcore pass failed to reconcile all casts when lowering(\n|.)*"
            r"Cast from !qcore.qubit_reg<420> to tensor<\?x!qcore.qubit> could not be resolved. "
            r"This is likely because the program contains unreconcilable types",
        ),
    ):
        module_pass.apply(xdsl_context, op)


def test_leftover_qubit_tensors_error(xdsl_context) -> None:
    op = ModuleOp(
        [
            qubits_op := t.TestOp(result_types=[qcore.QubitRegType(5)]),
            cast_op := UnrealizedConversionCastOp.get(
                qubits_op.res, (TensorType(qcore.QubitType(), [DYNAMIC_INDEX]),)
            ),
            t.TestOp(operands=cast_op.outputs),
        ]
    )
    op.verify()
    module_pass = LowerQubitTensorsToQCore()
    with pytest.raises(
        CompilerPassCheckError,
        match=re.escape("Found leftover qubit tensor operand. test.op could not be lowered."),
    ):
        module_pass.apply(xdsl_context, op)

    op = ModuleOp(
        [
            qubits_op := t.TestOp(result_types=[TensorType(qcore.QubitType(), [DYNAMIC_INDEX])]),
            t.TestOp(operands=qubits_op.results),
        ]
    )
    op.verify()
    module_pass = LowerQubitTensorsToQCore()
    with pytest.raises(
        CompilerPassCheckError,
        match=re.escape(
            "lower-qubit-tensors-to-qcore pass failed to lower all qubit tensors, "
            "test.op could not be lowered"
        ),
    ):
        module_pass.apply(xdsl_context, op)


def test_invalid_tensor_slice(xdsl_context: Context) -> None:
    tensor_type = TensorType(qcore.QubitType(), [DYNAMIC_INDEX])
    op = ModuleOp(
        [
            qubits_op := t.TestOp(result_types=[qcore.QubitRegType(5)]),
            cast_op := UnrealizedConversionCastOp.get(qubits_op.res, (tensor_type,)),
            slice_op := api.TensorSliceOp(cast_op.results[0], tensor_type, tensor_type, 0, 0, 1),
            t.TestOp(operands=slice_op.results),
        ]
    )
    module_pass = LowerQubitTensorsToQCore()
    with pytest.raises(
        InvalidQubitTensorError,
        match=re.escape(
            "Cannot slice qubit register of length 5 with [0:0:1]. "
            "Empty qubit registers are not allowed."
        ),
    ):
        module_pass.apply(xdsl_context, op)


@pytest.mark.parametrize(
    ("config", "msg"),
    [
        (
            (5, 5, 0, 0, 1),
            "Cannot merge qubits into qubit register of length 10, slicing with [0:0:1] "
            "requires 0 sliced and 10 leftover qubits but 5 and 5 were provided",
        ),
        (
            (1, 10, 1, 4, 1),
            "Cannot merge qubits into qubit register of length 11, slicing with [1:4:1] "
            "requires 3 sliced and 8 leftover qubits but 1 and 10 were provided",
        ),
        (
            (0, 1, None, None, None),
            "Cannot merge qubits into qubit register of length 1, slicing with [::] "
            "requires 1 sliced and 0 leftover qubits but 0 and 1 were provided",
        ),
    ],
)
def test_invalid_tensor_merge(
    xdsl_context: Context,
    config: tuple[int, int, int | None, int | None, int | None],
    msg: str,
) -> None:
    sliced_len, leftovers_len, start, stop, step = config
    tensor_type = TensorType(qcore.QubitType(), [DYNAMIC_INDEX])
    op = ModuleOp(
        [
            sliced_op := t.TestOp(
                result_types=[qcore.QubitRegType(sliced_len) if sliced_len else tensor_type]
            ),
            leftovers_op := t.TestOp(
                result_types=[qcore.QubitRegType(leftovers_len) if leftovers_len else tensor_type]
            ),
            sliced_cast_op := UnrealizedConversionCastOp.get(
                sliced_op.res, (TensorType(qcore.QubitType(), [sliced_len and DYNAMIC_INDEX]),)
            ),
            leftovers_cast_op := UnrealizedConversionCastOp.get(
                leftovers_op.res,
                (TensorType(qcore.QubitType(), [leftovers_len and DYNAMIC_INDEX]),),
            ),
            slice_op := api.TensorMergeOp(
                sliced_cast_op.results[0],
                leftovers_cast_op.results[0],
                tensor_type,
                start,
                stop,
                step,
            ),
            t.TestOp(operands=slice_op.results),
        ]
    )
    module_pass = LowerQubitTensorsToQCore()
    with pytest.raises(
        InvalidQubitTensorError,
        match=re.escape(msg),
    ):
        module_pass.apply(xdsl_context, op)
