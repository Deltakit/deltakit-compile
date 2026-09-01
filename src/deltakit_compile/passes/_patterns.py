# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Common base rewrite patterns used by the passes."""

from abc import abstractmethod
from collections.abc import Iterable
from typing import ClassVar

from typing_extensions import override
from xdsl.dialects.builtin import UnrealizedConversionCastOp
from xdsl.ir import Attribute, Block, BlockArgument, Operation, OpResult, SSAValue, Use
from xdsl.pattern_rewriter import PatternRewriter, RewritePattern
from xdsl.rewriter import InsertPoint

from deltakit_compile.dialects import qstruct, scf


class UnrealizedCastTypeConversionPattern(RewritePattern):
    """A rewrite pattern that converts between types by inserting unrealised casts.

    For each argument, result, or block arg of each operation, if `should_convert_operand`,
    `should_convert_result`, or `should_convert_block_arg` returns True, this pattern will replace
    its type with the output of `convert_type` (if not None) and insert an unrealised cast to
    convert between the old and new types. This is similar to TypeConversionPattern with the
    addition of the unrealised casts.

    The unrealised casts are intended be reconciled later by ReconcileUnrealizedCastsPattern.
    Recursive conversion of parametrised types is not supported (unlike TypeConversionPattern).
    Attributes and properties are not converted and are preserved.
    This pattern should not be run recursively as it may recurse indefinitely.
    """

    @abstractmethod
    def should_convert_operand(self, use: Use) -> bool:
        """Return whether to convert the type of the operand given by `use`.

        If True, the corresponding operand type of the use's operation will be changed and an
        unrealised cast will be inserted before the use to convert back to the original type. The
        type will only actually be converted if `convert_type` returns a non-None type as well.
        """

    @abstractmethod
    def should_convert_result(self, result: OpResult) -> bool:
        """Return whether to convert the type of the given op result at its definition.

        If True, the corresponding return type of the result's operation will be changed and an
        unrealised cast will be inserted afterwards to convert back to the original type. The type
        will only actually be converted if `convert_type` returns a non-None type as well.
        """

    @abstractmethod
    def should_convert_block_arg(self, block_arg: BlockArgument) -> bool:
        """Return whether to convert the type of the given block arg at its definition.

        If True, the type of the block arg will be changed and an unrealised cast will be inserted
        at the start of the block to convert back to the original type. The type will only actually
        be converted if `convert_type` returns a non-None type as well.
        """

    @abstractmethod
    def convert_type(self, type_: Attribute) -> Attribute | None:
        """Convert the given type, returning the new type or None to indicate no conversion."""

    def _get_new_type(self, type_: Attribute, *, condition: bool) -> Attribute:
        """A convenience function to convert a type if a condition holds."""
        if condition:
            new_type = self.convert_type(type_)
            if new_type is not None:
                return new_type
        return type_

    def _make_casts(
        self, values: Iterable[SSAValue], new_types: Iterable[Attribute]
    ) -> tuple[list[UnrealizedConversionCastOp], list[SSAValue]]:
        """Make unrealised casts to convert `values` to `new_types` if the types differ, returning
        the casts and the new values with the new types."""
        casts: list[UnrealizedConversionCastOp] = []
        new_values: list[SSAValue] = []
        for value, new_type in zip(values, new_types, strict=True):
            if new_type == value.type:
                new_values.append(value)
            else:
                cast_op, new_value = UnrealizedConversionCastOp.cast_one(value, new_type)
                casts.append(cast_op)
                new_values.append(new_value)
        return casts, new_values

    def _convert_block_args(self, block: Block, rewriter: PatternRewriter) -> None:
        """Convert the types of the given block's block args and insert casts."""
        insert_point = InsertPoint.at_start(block)
        cast_ops: list[UnrealizedConversionCastOp] = []
        replacements: list[tuple[SSAValue, SSAValue]] = []

        for arg in block.args:
            new_type = self._get_new_type(arg.type, condition=self.should_convert_block_arg(arg))
            if new_type != arg.type:
                new_arg = rewriter.replace_value_with_new_type(arg, new_type)
                cast_op, cast_result = UnrealizedConversionCastOp.cast_one(new_arg, arg.type)
                cast_result.name_hint = new_arg.name_hint
                cast_ops.append(cast_op)
                replacements.append((new_arg, cast_result))

                rewriter.insert_op(cast_op, insert_point)
                insert_point = InsertPoint.after(cast_op)

        for new_arg, cast_result in replacements:
            rewriter.replace_uses_with_if(
                new_arg, cast_result, lambda use: use.operation not in cast_ops
            )

    @override
    def match_and_rewrite(self, op: Operation, rewriter: PatternRewriter) -> None:
        for region in op.regions:
            for block in region.blocks:
                self._convert_block_args(block, rewriter)

        new_operand_types = [
            self._get_new_type(operand.type, condition=self.should_convert_operand(Use(op, idx)))
            for idx, operand in enumerate(op.operands)
        ]
        new_result_types = [
            self._get_new_type(result.type, condition=self.should_convert_result(result))
            for result in op.results
        ]

        if new_operand_types != list(op.operand_types) or new_result_types != list(op.result_types):
            operand_casts, new_operands = self._make_casts(op.operands, new_operand_types)
            new_op = type(op).create(
                operands=new_operands,
                result_types=new_result_types,
                properties=op.properties,
                attributes=op.attributes,
                successors=op.successors,
                regions=[op.detach_region(region) for region in op.regions],
            )
            result_casts, new_results = self._make_casts(new_op.results, op.result_types)

            rewriter.replace_op(op, [*operand_casts, new_op, *result_casts], new_results)

            for old_result, new_op_result, cast_result in zip(
                op.results, new_op.results, new_results, strict=True
            ):
                new_op_result.name_hint = old_result.name_hint
                cast_result.name_hint = old_result.name_hint


class ControlFlowUnrealizedCastTypeConversionPattern(UnrealizedCastTypeConversionPattern):
    """An UnrealizedCastTypeConversionPattern specialisation which converts the types of operands,
    results, and block args of control flow ops which are just passed directly through the op.

    Operands which are semantically meaningful to the op (eg. scf.if's condition) are not converted.
    """

    _CONTROL_FLOW_OPS: ClassVar[tuple[type[Operation], ...]] = (
        qstruct.ParallelOp,
        qstruct.RepeatOp,
        qstruct.YieldOp,
        scf.ForOp,
        scf.IfOp,
        scf.IndexSwitchOp,
        scf.WhileOp,
        scf.ConditionOp,
        scf.YieldOp,
    )

    _CONTROL_FLOW_SEMANTIC_OPERANDS: ClassVar[dict[type[Operation], set[int]]] = {
        scf.ForOp: {0, 1, 2},  # induction variable, lower bound, upper bound
        scf.IfOp: {0},  # condition
        scf.IndexSwitchOp: {0},  # switch value
        scf.ConditionOp: {0},  # condition
    }
    """Operand indices which have semantically meaningful types which should not be converted.
    Unmentioned operands are assumed to be passed through directly to results or block args.

    TODO: Use a more sustainable traits-based solution for identifying semantic operands.
    """

    @override
    def should_convert_operand(self, use: Use) -> bool:
        op_type = type(use.operation)
        return (
            op_type in self._CONTROL_FLOW_OPS
            and use.index not in self._CONTROL_FLOW_SEMANTIC_OPERANDS.get(op_type, set())
        )

    @override
    def should_convert_result(self, result: OpResult) -> bool:
        # All results of control flow ops are passed through directly from a yield op
        return type(result.op) in self._CONTROL_FLOW_OPS

    @override
    def should_convert_block_arg(self, block_arg: BlockArgument) -> bool:
        parent_op = block_arg.owner.parent_op()

        if isinstance(parent_op, scf.ForOp):
            # The first block arg of an scf.for is the induction variable which has a semantic type
            return block_arg.index != 0

        # All block args of other control flow ops are passed through directly from operands/yields
        return parent_op is not None and type(parent_op) in self._CONTROL_FLOW_OPS
