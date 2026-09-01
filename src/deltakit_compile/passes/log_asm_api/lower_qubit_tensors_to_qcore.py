# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Pass that lowers uses of qubit tensors (`tensor<?x!qcore.qubit>`) to use `qcore.qubit_reg`."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import (
    DYNAMIC_INDEX,
    ArrayOfConstraint,
    DenseArrayBase,
    IndexType,
    IntegerAttr,
    IntegerType,
    ModuleOp,
    TensorType,
    UnrealizedConversionCastOp,
)
from xdsl.dialects.utils import AbstractYieldOperation
from xdsl.ir import Attribute, Block, Operation, OpResult, SSAValue, SSAValues
from xdsl.irdl import AnyAttr, SingleOf, base
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
from xdsl.transforms.reconcile_unrealized_casts import ReconcileUnrealizedCastsPattern
from xdsl.utils.hints import isa

from deltakit_compile.dialects import arith, qcore, qref, qstruct, scf, tensor
from deltakit_compile.dialects import log_asm_api as api
from deltakit_compile.dialects import logical_assembly as logasm
from deltakit_compile.exceptions import CompilerPassCheckError, InvalidQubitTensorError
from deltakit_compile.passes._common import check_leftover_unrealized_casts

_QUBIT_TENSOR_CONSTR: Final = TensorType.constr(
    element_type=qcore.QubitType,
    shape=ArrayOfConstraint(SingleOf(AnyAttr())),
)


def _lowerable_cast_reg_value(operand: SSAValue) -> SSAValue[qcore.QubitRegType] | None:
    """Return the QubitReg SSAValue that was cast to `operand` if such a value exists, else return
    None. Used to check if we can lower ops on `operand` to ops on the `QubitRegType` that `operand`
    comes from."""
    if (
        isa(operand.owner, UnrealizedConversionCastOp)
        and len(operand.owner.outputs) == 1
        and _QUBIT_TENSOR_CONSTR.verifies(operand.owner.outputs[0].type)
        and isa(operand.owner.inputs, tuple[SSAValue[qcore.QubitRegType]])
    ):
        return operand.owner.inputs[0]
    return None


def _post_inject_unrealized_conversion_cast_op(
    operand: SSAValue, insertion_point: InsertPoint, rewriter: PatternRewriter
) -> UnrealizedConversionCastOp:
    """Insert an UnrealizedConversionCastOp at `insertion_point` that casts `operand` to a new
    result with the same type - then replaces all other uses of `operand` with this result.

    This then allows us to safely rewrite the type of `operand` without modifying the input types of
    ops that used `operand`."""
    cast_op, new_value = UnrealizedConversionCastOp.cast_one(operand, operand.type)
    rewriter.insert_op(cast_op, insertion_point)
    rewriter.replace_uses_with_if(
        operand,
        new_value,
        lambda use: use.operation != cast_op,
    )
    return cast_op


def _pre_inject_unrealized_conversion_cast_op(
    operand: SSAValue, using_op: Operation, operand_index: int, rewriter: PatternRewriter
) -> UnrealizedConversionCastOp:
    """Insert an UnrealizedConversionCastOp before `using_op` that casts `operand` to a new
    result with the same type - then replaces the specific use of `operand`
    (`using_op.operands[operand_index]`) with this result.

    This then allows us to safely rewrite the type of `using_op.operands[operand_index]`
    (the result of the new cast) without modifying the type of `operand`."""
    cast_op, new_value = UnrealizedConversionCastOp.cast_one(operand, operand.type)
    rewriter.insert_op(cast_op, InsertPoint.before(using_op))
    rewriter.replace_uses_with_if(
        operand,
        new_value,
        lambda operand_use: (
            operand_use.operation == using_op and operand_use.index == operand_index
        ),
    )
    return cast_op


def _replace_block_args(
    block: Block,
    indices_to_replace: Iterable[int],
    new_types: Sequence[Attribute],
    rewriter: PatternRewriter,
) -> None:
    """Insert casts after each block arg indexed by `indices_to_replace`, then updates the block
    arg's type to the corresponding type in `new_types`::

        ^bb0(%i : !t):
            ...(%i)

    becomes::

        ^bb0(%i : new_types[i]):
            %i1 = cast(%i) -> !t
            ...(%i1)

    for each `i` in `indices_to_replace`.
    """
    for i in indices_to_replace:
        # Cast block arg and update its type
        _post_inject_unrealized_conversion_cast_op(
            block.args[i], InsertPoint.at_start(block), rewriter
        )
        rewriter.replace_value_with_new_type(block.args[i], new_types[i])


def _replace_yield_args(
    yield_op: AbstractYieldOperation,
    indices_to_replace: Iterable[int],
    new_types: Sequence[Attribute],
    rewriter: PatternRewriter,
) -> None:
    """Insert casts before each yield operand indexed by `indices_to_replace`, then updates the type
    of the new cast's result to the corresponding type in `new_types`::

        yield %i : !t

    becomes::

        %i1 = cast(%i) -> new_types[i]
        yield %i : new_types[i]

    for each `i` in `indices_to_replace`."""
    for i in indices_to_replace:
        # Cast yield operand and update its type
        _pre_inject_unrealized_conversion_cast_op(yield_op.arguments[i], yield_op, i, rewriter)
        rewriter.replace_value_with_new_type(yield_op.arguments[i], new_types[i])


def _insert_result_casts(results: Sequence[OpResult], indices_to_cast: Iterable[int], rewriter):
    """Insert a cast from each index in `indices_to_cast` after the producer of the result::

        %i = ...() -> !t
        ...(%i)

    becomes::

        %i = ...() -> !t
        %i1 = cast(%i) -> !t
        ...(%i1)

    for each `i` in `indices_to_replace`.
    """
    for i in indices_to_cast:
        # Cast results (input type to be updated by replacing the op)
        _post_inject_unrealized_conversion_cast_op(
            results[i], InsertPoint.after(results[i].owner), rewriter
        )


# region log asm api


@dataclass(frozen=True)
class _RewriteCastFromPatch(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: api.CastOp, rewriter: PatternRewriter) -> None:
        if not isinstance(
            patch_type := op.argument.type, logasm.SurfaceCodeBasePatch
        ) or not _QUBIT_TENSOR_CONSTR.verifies(op.result.type):
            return
        new_cast = logasm.CastOp(op.argument, qcore.QubitRegType(patch_type.num_qubits))
        unrealised_cast_op, new_value = UnrealizedConversionCastOp.cast_one(
            new_cast.out, op.result.type
        )
        rewriter.replace_op(op, (new_cast, unrealised_cast_op), (new_value,))


@dataclass(frozen=True)
class _RewriteCastFromReg(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: api.CastOp, rewriter: PatternRewriter) -> None:
        if not isinstance(
            op.argument.type, qcore.QubitRegType
        ) or not _QUBIT_TENSOR_CONSTR.verifies(op.result.type):
            return
        unrealised_cast_op, new_value = UnrealizedConversionCastOp.cast_one(
            op.argument, op.result.type
        )
        rewriter.replace_op(op, unrealised_cast_op, (new_value,))


@dataclass(frozen=True)
class _RewriteCastFromTensor(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: api.CastOp, rewriter: PatternRewriter) -> None:
        new_argument = _lowerable_cast_reg_value(op.argument)
        if not new_argument or not isinstance(
            res_type := op.result.type, qcore.QubitRegType | logasm.SurfaceCodeBasePatch
        ):
            return
        new_cast = logasm.CastOp(new_argument, res_type)
        rewriter.replace_op(op, new_cast)


@dataclass(frozen=True)
class _RewriteRedundantCast(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: api.CastOp, rewriter: PatternRewriter) -> None:
        if (
            _QUBIT_TENSOR_CONSTR | base(qcore.QubitRegType) | base(logasm.SurfaceCodeBasePatch)
        ).verifies(op.argument.type) and op.argument.type == op.result.type:
            rewriter.replace_op(op, (), (op.argument,))


@dataclass(frozen=True)
class _RewriteCastTensor(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: api.CastOp, rewriter: PatternRewriter) -> None:
        """
        Rewrite::
            %2 = cast(%1 : !qcore.qubit_reg<N>) -> tensor<Nx!qcore.qubit>
            %3 = api.cast(%2) -> tensor<Px!qcore.qubit>

        Into::

            %2 = cast(%1: !qcore.qubit_reg<N>) -> tensor<Nx!qcore.qubit>
            %3 = cast(%1: !qcore.qubit_reg<N>) -> tensor<Px!qcore.qubit>

        """
        new_argument = _lowerable_cast_reg_value(op.argument)
        if not new_argument or not _QUBIT_TENSOR_CONSTR.verifies(op.result.type):
            return
        if op.result.type.get_shape()[0] not in (new_argument.type.size.data, DYNAMIC_INDEX):
            # Only lower when the cast is possible
            # ie. the result is the correct size or dynamically sized
            return
        unrealised_cast_op, new_value = UnrealizedConversionCastOp.cast_one(
            new_argument, op.result.type
        )
        rewriter.replace_op(op, unrealised_cast_op, (new_value,))


@dataclass(frozen=True)
class _RewriteCast(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: api.CastOp, rewriter: PatternRewriter) -> None:
        if not isinstance(
            op.argument.type, logasm.BasePatch | qcore.QubitRegType
        ) or not isinstance(op.result.type, logasm.BasePatch | qcore.QubitRegType):
            return
        rewriter.replace_op(op, logasm.CastOp(op.argument, op.result.type))


@dataclass(frozen=True)
class _RewriteUnsizedResetOp(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: api.UnsizedResetOp, rewriter: PatternRewriter) -> None:
        new_argument = _lowerable_cast_reg_value(op.qubits)
        if not new_argument:
            return
        unpack_op = qcore.UnpackQubitRegOp(new_argument)
        rewriter.replace_op(op, [unpack_op, qref.ResetOp(op.basis, unpack_op.qubits)])


@dataclass(frozen=True)
class _RewriteUnsizedGateOp(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: api.UnsizedGateOp, rewriter: PatternRewriter) -> None:
        new_argument = _lowerable_cast_reg_value(op.qubits)
        if not new_argument:
            return
        if new_argument.type.size.data % op.gate.get_qubit_count() != 0:
            msg = (
                f"Cannot convert qubit tensor {op.qubits.type!s} to {new_argument.type!s}. "
                f"A register of {len(new_argument.type)} qubits is incompatible with a "
                f"{op.gate.short_str()} that uses {op.gate.get_qubit_count()} qubits."
            )
            raise InvalidQubitTensorError(msg)
        unpack_op = qcore.UnpackQubitRegOp(new_argument)
        rewriter.replace_op(op, [unpack_op, qref.GateOp(op.gate, unpack_op.qubits)])


def _get_slice_string(slice_tuple: tuple[int | None, int | None, int | None]) -> str:
    return ":".join(["" if part is None else str(part) for part in slice_tuple])


@dataclass(frozen=True)
class _RewriteTensorSliceOp(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: api.TensorSliceOp, rewriter: PatternRewriter) -> None:
        new_argument = _lowerable_cast_reg_value(op.input)
        if not new_argument:
            return
        unpack_op = qcore.UnpackQubitRegOp(new_argument)
        start = op.start.data if op.start is not None else None
        stop = op.stop.data if op.stop is not None else None
        step = op.step.data if op.step is not None else None
        outputs = tuple(unpack_op.results)[start:stop:step]
        if not outputs:
            slice_str = _get_slice_string((start, stop, step))
            msg = (
                f"Cannot slice qubit register of length {len(new_argument.type)} with "
                f"[{slice_str}]. Empty qubit registers are not allowed."
            )
            raise InvalidQubitTensorError(msg)
        pack_slice_op = qcore.PackQubitRegOp(outputs)
        cast_slice_op, new_slice_value = UnrealizedConversionCastOp.cast_one(
            pack_slice_op.reg, op.slice.type
        )

        leftovers = tuple(res for res in unpack_op.results if res not in outputs)

        if leftovers:
            pack_leftovers_op = qcore.PackQubitRegOp(leftovers)
            cast_leftovers_op, new_leftovers_value = UnrealizedConversionCastOp.cast_one(
                pack_leftovers_op.reg, op.leftovers.type
            )
            leftovers_ops = [pack_leftovers_op, cast_leftovers_op]
        else:
            # If there are no qubits in leftovers we cannot pack a QubitReg, so special case it as
            # an empty tensor instead
            empty_tensor = tensor.EmptyOp([], TensorType(qcore.QubitType(), (0,)))
            leftovers_ops = [empty_tensor]
            new_leftovers_value = empty_tensor.tensor

        rewriter.replace_op(
            op,
            [unpack_op, pack_slice_op, cast_slice_op, *leftovers_ops],
            (new_slice_value, new_leftovers_value),
        )


_EMPTY_QUBIT_TENSOR: Final[TensorType] = TensorType(qcore.QubitType(), (0,))


@dataclass(frozen=True)
class _RewriteTensorMergeOp(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: api.TensorMergeOp, rewriter: PatternRewriter) -> None:
        sliced_input = (
            op.sliced_input
            if op.sliced_input.type == _EMPTY_QUBIT_TENSOR
            else _lowerable_cast_reg_value(op.sliced_input)
        )
        leftovers_input = (
            op.leftovers_input
            if op.leftovers_input.type == _EMPTY_QUBIT_TENSOR
            else _lowerable_cast_reg_value(op.leftovers_input)
        )

        if not sliced_input or not leftovers_input:
            return

        if isa(sliced_input, SSAValue[qcore.QubitRegType]):
            unpack_op = qcore.UnpackQubitRegOp(sliced_input)
            rewriter.insert_op(unpack_op, InsertPoint.before(op))
            sliced_qubits = list(unpack_op.qubits)
        else:
            assert sliced_input.type == _EMPTY_QUBIT_TENSOR
            sliced_qubits = []

        if isa(leftovers_input, SSAValue[qcore.QubitRegType]):
            unpack_op = qcore.UnpackQubitRegOp(leftovers_input)
            rewriter.insert_op(unpack_op, InsertPoint.before(op))
            leftovers_qubits = list(unpack_op.qubits)
        else:
            assert leftovers_input.type == _EMPTY_QUBIT_TENSOR
            leftovers_qubits = []

        indices = list(range(len(sliced_qubits) + len(leftovers_qubits)))

        start = op.start.data if op.start is not None else None
        stop = op.stop.data if op.stop is not None else None
        step = op.step.data if op.step is not None else None

        from_slice = indices[start:stop:step]

        if len(from_slice) != len(sliced_qubits):
            slice_str = _get_slice_string((start, stop, step))
            msg = (
                f"Cannot merge qubits into qubit register of length {len(indices)}, "
                f"slicing with [{slice_str}] requires {len(from_slice)} sliced and "
                f"{len(indices) - len(from_slice)} leftover qubits "
                f"but {len(sliced_qubits)} and {len(leftovers_qubits)} were provided."
            )
            raise InvalidQubitTensorError(msg)

        new_qubits: list[SSAValue] = []
        leftovers_iter = iter(leftovers_qubits)
        for i in indices:
            if i in from_slice:
                new_qubits.append(sliced_qubits[from_slice.index(i)])
            else:
                new_qubits.append(next(leftovers_iter))

        pack_op = qcore.PackQubitRegOp(new_qubits)
        unrealised_cast_op, new_value = UnrealizedConversionCastOp.cast_one(
            pack_op.reg, op.result.type
        )
        rewriter.replace_op(op, [pack_op, unrealised_cast_op], (new_value,))


# endregion
# region tensor


@dataclass(frozen=True)
class _RewriteExtractOp(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: tensor.ExtractOp, rewriter: PatternRewriter) -> None:
        new_argument = _lowerable_cast_reg_value(op.tensor)
        if (
            not new_argument
            or len(op.indices) != 1
            or (index := const_evaluate_operand(op.indices[0])) is None
            or (not 0 <= index < len(new_argument.type))
        ):
            return
        unpack_op = qcore.UnpackQubitRegOp(new_argument)
        rewriter.replace_op(op, unpack_op, (unpack_op.qubits[index],))


@dataclass(frozen=True)
class _RewriteFromElementsOp(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: tensor.FromElementsOp, rewriter: PatternRewriter) -> None:
        if not _QUBIT_TENSOR_CONSTR.verifies(op.result.type):
            return
        _post_inject_unrealized_conversion_cast_op(op.result, InsertPoint.after(op), rewriter)
        rewriter.replace_op(op, qcore.PackQubitRegOp(op.elements))


@dataclass(frozen=True)
class _RewriteConcatOp(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: tensor.ConcatOp, rewriter: PatternRewriter) -> None:
        lowerable_inputs = [_lowerable_cast_reg_value(arg) for arg in op.inputs]
        if not isa(lowerable_inputs, list[SSAValue[qcore.QubitRegType]]):
            return
        _post_inject_unrealized_conversion_cast_op(op.result, InsertPoint.after(op), rewriter)
        rewriter.replace_op(op, qcore.ConcatenateOp(lowerable_inputs))


@dataclass(frozen=True)
class _RewriteDimOp(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: tensor.DimOp, rewriter: PatternRewriter) -> None:
        new_argument = _lowerable_cast_reg_value(op.source)
        if not new_argument or (const_evaluate_operand(op.index)) != 0:
            return
        rewriter.replace_op(op, arith.ConstantOp(IntegerAttr(len(new_argument.type), IndexType())))


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
        new_argument = _lowerable_cast_reg_value(op.source)
        if (
            not new_argument
            or (offset := self._get_parameter(op.static_offsets, op.offsets)) is None
            or (size := self._get_parameter(op.static_sizes, op.sizes)) is None
            or size <= 0
            or (stride := self._get_parameter(op.static_strides, op.strides)) is None
            or stride == 0
        ):
            return
        unpack_op = qcore.UnpackQubitRegOp(new_argument)
        end = offset + (stride * size)
        qubits = list(unpack_op.qubits[offset:end:stride])
        if len(qubits) != size:
            unpack_op.erase()
            msg = (
                f"Cannot extract a slice from {new_argument.type}. "
                f"Expected to get {size} qubits with offset {offset} and stride {stride} "
                f"but got {len(qubits)} from qubits[{offset}:{end}:{stride}]"
            )
            raise InvalidQubitTensorError(msg)

        _post_inject_unrealized_conversion_cast_op(op.result, InsertPoint.after(op), rewriter)
        rewriter.replace_op(op, (unpack_op, qcore.PackQubitRegOp(qubits)))


# endregion
# region qstruct


@dataclass(frozen=True)
class _RewriteCircuitOpOperand(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.CircuitOp, rewriter: PatternRewriter) -> None:
        """
        Rewrite::

            %0 = cast(%q0)
            %3 = qstruct.circuit(%0) {
            ^(%1)
            ...
            qstruct.yield %2
            }

        Into::

            %0 = cast(%q0)
            %q3 = qstruct.circuit(%q0) {
            ^(%q1)
            %1 = cast(%q1)
            ...
            qstruct.yield %2
            }
        """
        new_arguments = SSAValues(_lowerable_cast_reg_value(arg) or arg for arg in op.operands)
        replaced_indices = [i for i, arg in enumerate(op.args) if new_arguments[i] != arg]
        if not replaced_indices:
            return

        # Replace operands
        op.operands = new_arguments
        rewriter.notify_op_modified(op)

        _replace_block_args(op.body.block, replaced_indices, new_arguments.types, rewriter)


@dataclass(frozen=True)
class _RewriteCircuitOpResult(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.CircuitOp, rewriter: PatternRewriter) -> None:
        """
        Rewrite::

            %3 = qstruct.circuit(...) {
            ...
            %2 = cast(%q)
            qstruct.yield %2
            }

        Into::

            %q3 = qstruct.circuit(...) {
            ...
            %2 = cast(%q)
            qstruct.yield %q
            }
            %3 = cast(%q3)

        """
        yield_op = op.yield_op
        new_arguments = [_lowerable_cast_reg_value(arg) or arg for arg in yield_op.operands]
        replaced_indices = [i for i, arg in enumerate(yield_op.operands) if new_arguments[i] != arg]
        if not replaced_indices:
            return

        # Replace operands
        rewriter.replace_op(yield_op, qstruct.YieldOp(*new_arguments))

        _insert_result_casts(op.res, replaced_indices, rewriter)
        for i in replaced_indices:
            # Update the result types
            rewriter.replace_value_with_new_type(op.res[i], new_arguments[i].type)


@dataclass(frozen=True)
class _RewriteRepeatOp(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.RepeatOp, rewriter: PatternRewriter) -> None:
        """
        Rewrite::

            %0 = cast(%q0)
            %3 = qstruct.repeat(%0) {
            ^(%1)
            ...
            qstruct.yield %2
            }

        Into::

            %0 = cast(%q0)
            %q3 = qstruct.repeat(%q0) {
            ^(%q1)
            %1 = cast(%q1)
            ...
            %q2 = cast(%2)
            qstruct.yield %q2
            }
            %3 = cast(%q3)
        """
        new_arguments = SSAValues(_lowerable_cast_reg_value(arg) or arg for arg in op.iter_args)
        replaced_indices = [i for i, arg in enumerate(op.iter_args) if new_arguments[i] != arg]

        if not replaced_indices:
            return

        block = op.body.block
        op.body.detach_block(block)
        yield_op = block.last_op
        assert isinstance(yield_op, qstruct.YieldOp)

        _replace_block_args(block, replaced_indices, new_arguments.types, rewriter)
        _replace_yield_args(yield_op, replaced_indices, new_arguments.types, rewriter)
        _insert_result_casts(op.res, replaced_indices, rewriter)
        rewriter.replace_op(op, qstruct.RepeatOp(op.repetitions, block, new_arguments))


@dataclass(frozen=True)
class _RewriteParallelOp(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.ParallelOp, rewriter: PatternRewriter) -> None:
        """
        Rewrite::

            %0 = cast(%q0)
            %2, %3 = qstruct.parallel -> T, ...{
            ...
            qstruct.yield %0
            } {
            ...
            qstruct.yield %1
            }

        Into::

            %0 = cast(%q0)
            %q2, %3 = qstruct.parallel -> Q, ...{
            ...
            qstruct.yield %q0
            } {
            ...
            qstruct.yield %1
            }
            %2 = cast(%q2)
        """
        new_types = []
        changed = False
        for par_region in op.par_regions:
            yield_op = par_region.block.last_op
            assert isinstance(yield_op, qstruct.YieldOp)
            new_arguments = tuple(
                _lowerable_cast_reg_value(arg) or arg for arg in yield_op.arguments
            )
            new_types.extend([arg.type for arg in new_arguments])
            if new_arguments != yield_op.arguments:
                rewriter.replace_op(yield_op, qstruct.YieldOp(*new_arguments))
                changed = True

        if not changed:
            return

        regions = list(op.par_regions)
        for region in regions:
            op.detach_region(region)
        new_parallel = qstruct.ParallelOp(new_types, regions, op.alignment)
        new_ops: list[Operation] = [new_parallel]
        new_results: list[SSAValue] = list(new_parallel.res)
        for i in range(len(new_results)):
            if new_results[i].type != op.res[i].type:
                cast_op, new_res = UnrealizedConversionCastOp.cast_one(
                    new_results[i], op.res[i].type
                )
                new_ops.append(cast_op)
                new_results[i] = new_res

        rewriter.replace_op(op, new_ops, new_results)


# endregion
# region scf


@dataclass(frozen=True)
class _RewriteForOp(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: scf.ForOp, rewriter: PatternRewriter) -> None:
        """
        Rewrite::

            %0 = cast(%q0)
            ..., %3 = scf.for(ub,lb,step, ..., %0) {
            ^(%index, ..., %1)
            ...
            scf.yield ..., %2
            }

        Into::

            %0 = cast(%q0)
            ..., %q3 = scf.for(ub,lb,step, ..., %q0) {
            ^(%index, ..., %q1)
            %1 = cast(%q1)
            ...
            %q2 = cast(%2)
            scf.yield ..., %q2
            }
            %3 = cast(%q3)
        """
        new_arguments = SSAValues(_lowerable_cast_reg_value(arg) or arg for arg in op.iter_args)
        replaced_indices = [i for i, arg in enumerate(op.iter_args) if new_arguments[i] != arg]
        if not replaced_indices:
            return

        block = op.body.block
        op.body.detach_block(block)
        yield_op = block.last_op
        assert isinstance(yield_op, scf.YieldOp)

        _replace_block_args(
            block,
            (i + 1 for i in replaced_indices),
            (IndexType(), *new_arguments.types),
            rewriter,
        )
        _replace_yield_args(yield_op, replaced_indices, new_arguments.types, rewriter)
        _insert_result_casts(op.res, replaced_indices, rewriter)

        rewriter.replace_op(op, scf.ForOp(op.lb, op.ub, op.step, new_arguments, block))


@dataclass(frozen=True)
class _RewriteIfOp(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: scf.IfOp, rewriter: PatternRewriter) -> None:
        """
        Rewrite::

            %0 = cast(%q0)
            %1 = cast(%q1)
            %2 = scf.if(%...) -> T {
            ...
            scf.yield %0
            } else {
            ...
            scf.yield %1
            }

        Into::

            %0 = cast(%q0)
            %1 = cast(%q1)
            %q2 = scf.if(%...) -> Q {
            ...
            scf.yield %q0
            } else {
            ...
            scf.yield %q1
            }
            %2 = cast(%q2)
        """
        true_region = op.true_region
        false_region = op.false_region
        true_yield = true_region.block.last_op
        false_yield = false_region.block.last_op
        assert isinstance(true_yield, scf.YieldOp)
        assert isinstance(false_yield, scf.YieldOp)

        new_true_yielded: list[SSAValue] = []
        new_false_yielded: list[SSAValue] = []
        changed = False
        for true_arg, false_arg in zip(true_yield.arguments, false_yield.arguments, strict=True):
            new_true_arg = _lowerable_cast_reg_value(true_arg)
            new_false_arg = _lowerable_cast_reg_value(false_arg)
            if new_true_arg and new_false_arg and new_true_arg.type == new_false_arg.type:
                new_true_yielded.append(new_true_arg)
                new_false_yielded.append(new_false_arg)
                changed = True
            else:
                new_true_yielded.append(true_arg)
                new_false_yielded.append(false_arg)

        if not changed:
            return

        true_region = op.detach_region(true_region)
        false_region = op.detach_region(false_region)
        rewriter.replace_op(true_yield, scf.YieldOp(*new_true_yielded))
        rewriter.replace_op(false_yield, scf.YieldOp(*new_false_yielded))

        new_if = scf.IfOp(
            op.cond, [value.type for value in new_true_yielded], true_region, false_region
        )
        new_ops: list[Operation] = [new_if]
        new_results: list[SSAValue] = list(new_if.output)
        for i in range(len(new_results)):
            if new_results[i].type != op.output[i].type:
                cast_op, new_res = UnrealizedConversionCastOp.cast_one(
                    new_results[i], op.output[i].type
                )
                new_ops.append(cast_op)
                new_results[i] = new_res

        rewriter.replace_op(op, new_ops, new_results)


@dataclass(frozen=True)
class _RewriteIndexSwitchOp(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: scf.IndexSwitchOp, rewriter: PatternRewriter) -> None:
        """
        Rewrite::

            %0 = cast(%q0)
            %1 = cast(%q1)
            %2 = scf.index_switch(%...) -> T
            case 0 {
            ...
            scf.yield %0
            }
            ...
            default {
            ...
            scf.yield %1
            }

        Into::

            %0 = cast(%q0)
            %1 = cast(%q1)
            %q2 = scf.index_switch(%...) -> Q
            case 0 {
            ...
            scf.yield %q0
            }
            ...
            default {
            ...
            scf.yield %q1
            }
            %2 = cast(%q2)
        """
        default_region = op.default_region
        case_regions = op.case_regions
        default_yield_op = default_region.block.last_op
        case_yield_ops = [region.block.last_op for region in case_regions]
        assert isinstance(default_yield_op, scf.YieldOp)
        assert isa(case_yield_ops, list[scf.YieldOp])

        new_default_yields: list[SSAValue] = []
        new_cases_yields: list[list[SSAValue]] = []
        changed = False
        for i, default_arg in enumerate(default_yield_op.arguments):
            case_args = [yield_op.arguments[i] for yield_op in case_yield_ops]

            new_default_arg = _lowerable_cast_reg_value(default_arg)
            new_case_args = [_lowerable_cast_reg_value(arg) for arg in case_args]
            if (
                new_default_arg
                and isa(new_case_args, list[SSAValue])
                and all(new_default_arg.type == arg.type for arg in new_case_args)
            ):
                new_default_yields.append(new_default_arg)
                new_cases_yields.append(new_case_args)
                changed = True
            else:
                new_default_yields.append(default_arg)
                new_cases_yields.append(case_args)

        if not changed:
            return

        op.detach_region(default_region)
        for region in case_regions:
            op.detach_region(region)

        rewriter.replace_op(default_yield_op, scf.YieldOp(*new_default_yields))
        for i, case_yield in enumerate(case_yield_ops):
            rewriter.replace_op(case_yield, scf.YieldOp(*[args[i] for args in new_cases_yields]))

        new_index_switch = scf.IndexSwitchOp(
            op.arg, op.cases, default_region, case_regions, [arg.type for arg in new_default_yields]
        )
        new_ops: list[Operation] = [new_index_switch]
        new_results: list[SSAValue] = list(new_index_switch.output)
        for i in range(len(new_results)):
            if new_results[i].type != op.output[i].type:
                cast_op, new_res = UnrealizedConversionCastOp.cast_one(
                    new_results[i], op.output[i].type
                )
                new_ops.append(cast_op)
                new_results[i] = new_res

        rewriter.replace_op(op, new_ops, new_results)


@dataclass(frozen=True)
class _RewriteWhileOpFromOperand(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: scf.WhileOp, rewriter: PatternRewriter) -> None:
        """
        Rewrite::

            %0 = cast(%q0)
            ... = scf.while(..., %0) {
            ^(..., %1)
            ...
            scf.condition (...), ...
            } do {
            ^(...)
            ...
            scf.yield ..., %2
            }

        Into::

            %0 = cast(%q0)
            ..., %q3 = scf.while(..., %q0) {
            ^(..., %q1)
            %1 = cast(%q1)
            ...
            scf.condition (...), ...
            } do {
            ^(...)
            ...
            %q1 = cast(%2)
            scf.yield ..., %q2
            }
        """

        new_arguments = SSAValues(_lowerable_cast_reg_value(arg) or arg for arg in op.arguments)
        replaced_indices = [i for i, arg in enumerate(op.arguments) if new_arguments[i] != arg]
        if not replaced_indices:
            return

        before_block = op.before_region.block
        after_block = op.after_region.block
        op.before_region.detach_block(before_block)
        op.after_region.detach_block(after_block)

        yield_op = after_block.last_op
        assert isinstance(yield_op, scf.YieldOp)

        _replace_block_args(before_block, replaced_indices, new_arguments.types, rewriter)
        _replace_yield_args(yield_op, replaced_indices, new_arguments.types, rewriter)

        rewriter.replace_op(
            op, scf.WhileOp(new_arguments, op.res.types, (before_block,), (after_block,))
        )


@dataclass(frozen=True)
class _RewriteWhileOpFromCondition(RewritePattern):
    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: scf.WhileOp, rewriter: PatternRewriter) -> None:
        """
        Rewrite::

            ..., %2 = scf.while(...) {
            ^(..., %1)
            ...
            %0 = cast(%q0)
            scf.condition (...) ..., %0
            } do {
            ^(..., %1)
            ...
            scf.yield ...
            }

        Into::

            ..., %q2 = scf.while(...) {
            ^(..., %1)
            ...
            %0 = cast(%q0)
            scf.condition (...) ..., %q0
            } do {
            ^(..., %q1)
            %1 = cast(%q1)
            ...
            scf.yield ...
            }
            %2 = cast(%q2)
        """

        cond_op = op.before_region.block.last_op
        assert isinstance(cond_op, scf.ConditionOp)
        new_cond_yields = SSAValues(_lowerable_cast_reg_value(arg) or arg for arg in cond_op.args)
        replaced_indices = [i for i, arg in enumerate(cond_op.args) if new_cond_yields[i] != arg]
        if not replaced_indices:
            return

        before_block = op.before_region.block
        after_block = op.after_region.block
        op.before_region.detach_block(before_block)
        op.after_region.detach_block(after_block)

        rewriter.replace_op(cond_op, scf.ConditionOp(cond_op.condition, *new_cond_yields))

        _replace_block_args(after_block, replaced_indices, new_cond_yields.types, rewriter)
        _insert_result_casts(op.res, replaced_indices, rewriter)

        rewriter.replace_op(
            op, scf.WhileOp(op.arguments, new_cond_yields.types, (before_block,), (after_block,))
        )


# endregion


@dataclass(frozen=True)
class LowerQubitTensorsToQCore(ModulePass):
    """A pass to lower uses of qubit tensors (`tensor<?x!qcore.qubit>`) to use `qcore.qubit_reg`.

    The pass optimistically tries to convert all `log_asm_api.cast` ops into `log_asm.cast` ops that
    return `qcore.qubit_reg`s instead of tensors, and then convert each use of the tensor into the
    appropriate `qcore.qubit_reg` based ops."""

    name = "lower-qubit-tensors-to-qcore"

    permit_unresolved_casts: bool = False
    permit_remaining_qubit_tensors: bool = False

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
                    ReconcileUnrealizedCastsPattern(),
                    _RewriteCastFromPatch(),
                    _RewriteCastFromReg(),
                    _RewriteCastFromTensor(),
                    _RewriteRedundantCast(),
                    _RewriteCastTensor(),
                    _RewriteCast(),
                    _RewriteUnsizedResetOp(),
                    _RewriteUnsizedGateOp(),
                    _RewriteTensorSliceOp(),
                    _RewriteTensorMergeOp(),
                    _RewriteExtractOp(),
                    _RewriteFromElementsOp(),
                    _RewriteConcatOp(),
                    _RewriteDimOp(),
                    _RewriteExtractSliceOp(),
                    _RewriteCircuitOpOperand(),
                    _RewriteCircuitOpResult(),
                    _RewriteRepeatOp(),
                    _RewriteParallelOp(),
                    _RewriteForOp(),
                    _RewriteIfOp(),
                    _RewriteIndexSwitchOp(),
                    _RewriteWhileOpFromOperand(),
                    _RewriteWhileOpFromCondition(),
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
        if not self.permit_remaining_qubit_tensors:
            self.check_leftover_qubit_tensors(op)

    def check_leftover_qubit_tensors(self, op: ModuleOp) -> None:
        """Walks the IR to check there are no SSAValues with a qubit tensor type."""
        for child_op in op.walk():
            for value in list(child_op.results) + [
                arg for region in child_op.regions for block in region.blocks for arg in block.args
            ]:
                if _QUBIT_TENSOR_CONSTR.verifies(value.type):
                    if (
                        isinstance(child_op, UnrealizedConversionCastOp)
                        and len(child_op.results) == 1
                    ):
                        using_op = next(iter(value.uses))
                        msg = (
                            "Found leftover qubit tensor operand. "
                            f"{using_op.operation.name} could not be lowered."
                        )
                        using_op.operation.emit_error(msg, CompilerPassCheckError(msg))

                    child_op.emit_error(
                        f"Found leftover qubit tensor: This op could not be lowered by {self.name}",
                        CompilerPassCheckError(
                            f"{self.name} pass failed to lower all qubit tensors, "
                            f"{child_op.name} could not be lowered."
                        ),
                    )
