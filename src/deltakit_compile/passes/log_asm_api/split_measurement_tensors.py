# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Pass that splits measurement tensors (`tensor<3xi1>`) into individual `i1`s."""

import itertools
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import (
    DYNAMIC_INDEX,
    I1,
    ArrayOfConstraint,
    DenseArrayBase,
    IndexType,
    IntAttr,
    IntegerAttr,
    IntegerType,
    ModuleOp,
    TensorType,
    UnrealizedConversionCastOp,
)
from xdsl.ir import Block, OpResult, SSAValue, SSAValues
from xdsl.irdl import AnyAttr, AtLeast, SingleOf, isa
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    GreedyRewritePatternApplier,
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.rewriter import InsertPoint
from xdsl.transforms.canonicalization_patterns.utils import const_evaluate_operand
from xdsl.transforms.common_subexpression_elimination import cse

from deltakit_compile.dialects import arith, qstruct, tensor
from deltakit_compile.exceptions import CompilerPassCheckError, InvalidQubitTensorError
from deltakit_compile.passes._common import check_leftover_unrealized_casts

_MEAS_TENSOR_CONSTR: Final = TensorType.constr(
    element_type=I1,
    shape=ArrayOfConstraint(SingleOf(IntAttr.constr(AtLeast(1)))),
)


def _lowerable_cast_split_i1s(operand: SSAValue) -> tuple[SSAValue[I1], ...] | None:
    """Return the `i1` SSAValues that was cast to `operand` if such a value exists, else return
    None. Used to check if we can lower ops on `operand` to ops on the split `i1`s that `operand`
    was cast from."""
    if (
        isa(operand.owner, UnrealizedConversionCastOp)
        and len(operand.owner.outputs) == 1
        and _MEAS_TENSOR_CONSTR.verifies(operand.owner.outputs[0].type)
        and isa(operand.owner.inputs, tuple[SSAValue[I1], ...])
    ):
        return operand.owner.inputs
    return None


# region tensor


@dataclass(frozen=True)
class _RewriteExtractOp(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: tensor.ExtractOp, rewriter: PatternRewriter) -> None:
        split_i1s = _lowerable_cast_split_i1s(op.tensor)
        if (
            not split_i1s
            or len(op.indices) != 1
            or (index := const_evaluate_operand(op.indices[0])) is None
            or (not 0 <= index < len(split_i1s))
        ):
            return
        rewriter.replace_all_uses_with(op.result, split_i1s[index])
        rewriter.erase_op(op)


@dataclass(frozen=True)
class _RewriteFromElementsOp(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: tensor.FromElementsOp, rewriter: PatternRewriter) -> None:
        if not _MEAS_TENSOR_CONSTR.verifies(op.result.type):
            return
        rewriter.replace_op(op, UnrealizedConversionCastOp.get(op.elements, [op.result.type]))


@dataclass(frozen=True)
class _RewriteConcatOp(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: tensor.ConcatOp, rewriter: PatternRewriter) -> None:
        split_i1s: list[SSAValue[I1]] = []
        for arg in op.inputs:
            if (arg_i1s := _lowerable_cast_split_i1s(arg)) is None:
                return
            split_i1s.extend(arg_i1s)
        rewriter.replace_op(op, UnrealizedConversionCastOp.get(split_i1s, [op.result.type]))


@dataclass(frozen=True)
class _RewriteDimOp(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: tensor.DimOp, rewriter: PatternRewriter) -> None:
        split_i1s = _lowerable_cast_split_i1s(op.source)
        if not split_i1s or (const_evaluate_operand(op.index)) != 0:
            return
        rewriter.replace_op(op, arith.ConstantOp(IntegerAttr(len(split_i1s), IndexType())))


@dataclass(frozen=True)
class _RewriteExtractSliceOp(RewritePattern):
    @staticmethod
    def _get_parameter(
        static_param: DenseArrayBase[IntegerType], dynamic_params: Sequence[SSAValue]
    ) -> int | None:
        if len(static_param) != 1:
            return None
        param: int = static_param.get_values()[0]
        if param != DYNAMIC_INDEX:
            return param
        return const_evaluate_operand(dynamic_params[0])

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: tensor.ExtractSliceOp, rewriter: PatternRewriter) -> None:
        split_i1s = _lowerable_cast_split_i1s(op.source)
        if (
            not split_i1s
            or (offset := self._get_parameter(op.static_offsets, op.offsets)) is None
            or (size := self._get_parameter(op.static_sizes, op.sizes)) is None
            or size <= 0
            or (stride := self._get_parameter(op.static_strides, op.strides)) is None
            or stride == 0
        ):
            return
        end = offset + (stride * size)
        sliced_i1s = split_i1s[offset:end:stride]
        if len(sliced_i1s) != size:
            msg = (
                f"Couldn't handle a {op.name} when splitting measurement tensors. "
                f"Expected to get {size} measurements with offset {offset} and stride {stride} "
                f"but got {len(sliced_i1s)} from measurements[{offset}:{end}:{stride}]"
            )
            raise InvalidQubitTensorError(msg)
        rewriter.replace_op(op, UnrealizedConversionCastOp.get(sliced_i1s, [op.result.type]))


# endregion
# region qstruct


@dataclass(frozen=True)
class _RewriteCircuitOpOperand(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.CircuitOp, rewriter: PatternRewriter) -> None:
        """
        Rewrite::

            %t0 = cast(%b0, %b1, %b2)
            %t0_3 = qstruct.circuit(%t0) {
            ^(%t0_1)
            ...
            qstruct.yield %t0_2
            }

        Into::

            %t0 = cast(%b0, %b1, %b2)
            %t0_3 = qstruct.circuit(%b0, %b1, %b2) {
            ^(%b0_1, %b1_1, %b2_1)
            %t0_1 = cast(%b0_1, %b1_1, %b2_1)
            ...
            qstruct.yield %t0_2
            }
        """
        # Replace measurement tensor args directly with their corresponding tuples of i1s so the
        # indices of the arguments aren't changed
        new_arguments = [_lowerable_cast_split_i1s(arg) or arg for arg in op.operands]
        replaced_indices = {i for i, arg in enumerate(op.args) if new_arguments[i] != arg}
        if not replaced_indices:
            return

        # Replace operands with a single flat list of arguments
        flat_arguments: list[SSAValue] = []
        for arg in new_arguments:
            if isinstance(arg, tuple):
                flat_arguments.extend(arg)
            else:
                flat_arguments.append(arg)
        op.operands = flat_arguments
        rewriter.notify_op_modified(op)

        # Replace block args with split i1s
        old_block = op.body.detach_block(0)
        op.body.add_block(
            Block(
                (old_block.detach_op(o) for o in old_block.ops),
                arg_types=SSAValues(flat_arguments).types,
            )
        )

        # Add cast back to tensor and replace uses with the cast's result
        new_idx: int = 0
        for old_idx, new_arg in enumerate(new_arguments):
            if old_idx in replaced_indices:
                assert isinstance(new_arg, tuple)
                block_arg_i1s = op.body.block.args[new_idx : new_idx + len(new_arg)]

                cast_op = UnrealizedConversionCastOp.get(
                    block_arg_i1s, [old_block.args[old_idx].type]
                )
                rewriter.insert_op(cast_op, InsertPoint.at_start(op.body.block))
                rewriter.replace_all_uses_with(old_block.args[old_idx], cast_op.results[0])

                new_idx += len(new_arg)
            else:
                rewriter.replace_all_uses_with(old_block.args[old_idx], op.body.block.args[new_idx])
                new_idx += 1


@dataclass(frozen=True)
class _RewriteCircuitOpResult(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.CircuitOp, rewriter: PatternRewriter) -> None:
        """
        Rewrite::

            %t0_1 = qstruct.circuit(...) {
            ...
            %t0 = cast(%b0, %b1, %b2)
            qstruct.yield %t0
            }

        Into::

            %b0_1, %b1_1, %b2_1 = qstruct.circuit(...) {
            ...
            %t0 = cast(%b0, %b1, %b2)
            qstruct.yield %b0, %b1, %b2
            }
            %t0_1 = cast(%b0_1, %b1_1, %b2_1)

        """
        # Replace measurement tensor args directly with their corresponding tuples of i1s so the
        # indices of the arguments aren't changed
        yield_op = op.yield_op
        new_arguments = [_lowerable_cast_split_i1s(arg) or arg for arg in yield_op.operands]
        replaced_indices = {i for i, arg in enumerate(yield_op.operands) if new_arguments[i] != arg}
        if not replaced_indices:
            return

        # Replace yield operands with a single flat list of arguments
        flat_arguments: list[SSAValue] = []
        for arg in new_arguments:
            if isinstance(arg, tuple):
                flat_arguments.extend(arg)
            else:
                flat_arguments.append(arg)
        rewriter.replace_op(yield_op, qstruct.YieldOp(*flat_arguments))

        # Replace op results with the same types as the yield operands
        old_results = op.results
        flat_results = [
            OpResult(yield_arg.type, op, idx) for (idx, yield_arg) in enumerate(flat_arguments)
        ]
        op.results = SSAValues(flat_results)
        rewriter.notify_op_modified(op)

        # Add cast back to tensor and replace uses with the cast's result
        new_idx: int = 0
        for old_idx, new_arg in enumerate(new_arguments):
            if old_idx in replaced_indices:
                assert isinstance(new_arg, tuple)
                result_i1s = op.results[new_idx : new_idx + len(new_arg)]

                cast_op = UnrealizedConversionCastOp.get(result_i1s, [old_results[old_idx].type])
                rewriter.insert_op(cast_op, InsertPoint.after(op))
                rewriter.replace_all_uses_with(old_results[old_idx], cast_op.results[0])

                new_idx += len(new_arg)
            else:
                rewriter.replace_all_uses_with(old_results[old_idx], op.results[new_idx])
                new_idx += 1


# endregion


@dataclass(frozen=True)
class SplitMeasurementTensors(ModulePass):
    """A pass that splits measurement tensors (`tensor<3xi1>`) into individual `i1`s.

    The pass treats all i1 tensors as being measurement tensors to be broken down. It also doesn't
    handle tensors of unknown length (`tensor<?xi1>`), throwing an error if these are present.
    """

    name = "split-measurement-tensors"

    permit_unresolved_casts: bool = False
    permit_remaining_measurement_tensors: bool = False

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:

        if not self.permit_unresolved_casts:
            existing_casts = {
                child for child in op.walk() if isinstance(child, UnrealizedConversionCastOp)
            }
        else:
            existing_casts = set()

        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [
                    _RewriteExtractOp(),
                    _RewriteFromElementsOp(),
                    _RewriteConcatOp(),
                    _RewriteDimOp(),
                    _RewriteExtractSliceOp(),
                    _RewriteCircuitOpOperand(),
                    _RewriteCircuitOpResult(),
                ],
                ctx=ctx,
                folding_enabled=True,
                dce_enabled=True,
            ),
            apply_recursively=True,
        ).rewrite_module(op)
        cse(op)

        if not self.permit_unresolved_casts:
            check_leftover_unrealized_casts(self.name, op, existing_casts)
        if not self.permit_remaining_measurement_tensors:
            self.check_leftover_measurement_tensors(op)

    def check_leftover_measurement_tensors(self, op: ModuleOp) -> None:
        """Walks the IR to check there are no SSAValues with an i1 tensor type, whether known or
        unknown length."""
        any_meas_tensor_constr = TensorType.constr(
            element_type=I1,
            shape=ArrayOfConstraint(SingleOf(AnyAttr())),
        )

        for child_op in op.walk():
            for value in itertools.chain(
                child_op.results,
                (
                    arg
                    for region in child_op.regions
                    for block in region.blocks
                    for arg in block.args
                ),
            ):
                if any_meas_tensor_constr.verifies(value.type):
                    if (
                        isinstance(child_op, UnrealizedConversionCastOp)
                        and len(child_op.results) == 1
                    ):
                        using_op = next(iter(value.uses))
                        msg = (
                            "Found leftover measurement tensor operand. "
                            f"{using_op.operation.name} could not be lowered."
                        )
                        using_op.operation.emit_error(msg, CompilerPassCheckError(msg))

                    child_op.emit_error(
                        "Found leftover measurement tensor: This op could not be lowered by "
                        f"{self.name}",
                        CompilerPassCheckError(
                            f"{self.name} pass failed to lower all measurement tensors, "
                            f"{child_op.name} could not be lowered."
                        ),
                    )
