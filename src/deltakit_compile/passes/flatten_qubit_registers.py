# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module containing a pass that flattens qubit registers."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypeGuard

from typing_extensions import overload, override
from xdsl.context import Context
from xdsl.dialects import scf
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Attribute, BlockArgument, Operation, Region, SSAValue
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    GreedyRewritePatternApplier,
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.rewriter import InsertPoint
from xdsl.utils.hints import isa

from deltakit_compile.dialects import qstruct
from deltakit_compile.dialects.qcore import (
    AllocQubitOp,
    ConcatenateOp,
    PackQubitRegOp,
    QubitRegType,
    QubitType,
    SplitOp,
    UnpackQubitRegOp,
)
from deltakit_compile.passes.canonicalisation.qcore import RemoveRedundantUnpackAfterPack
from deltakit_compile.passes.stim._common import copy_stim_tag, warn_stim_tag_lost


@overload
def _is_qubit_reg(value: BlockArgument) -> TypeGuard[BlockArgument[QubitRegType]]: ...


@overload
def _is_qubit_reg(value: SSAValue) -> TypeGuard[SSAValue[QubitRegType]]: ...


def _is_qubit_reg(value: SSAValue) -> bool:
    """Type guard to help type checkers recognise `SSAValues` or `BlockArguments` with
    QubitRegType."""
    return isa(value.type, QubitRegType)


class _ConcatenatePattern(RewritePattern):
    """Lower ConcatenateOp into UnpackQubitRegOp and PackQubitRegOp."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: ConcatenateOp, rewriter: PatternRewriter) -> None:
        """Lowers ConcatenateOp into UnpackQubitRegOp and PackQubitRegOp."""

        new_ops: list = []

        for operand in op.in_regs:
            assert _is_qubit_reg(operand), "ConcatenateOp operands must be of QubitRegType"
            unpack_op = UnpackQubitRegOp(operand)
            new_ops.append(unpack_op)

        new_ops.append(
            PackQubitRegOp([qubit for unpack_op in new_ops for qubit in unpack_op.results])
        )

        # Replace the original ConcatenateOp with the new PackQubitRegOp
        rewriter.replace_op(op, new_ops)
        warn_stim_tag_lost(
            op, "ConcatenateOp is expanded into unpack/pack ops with no single correspondent"
        )


class _SplitPattern(RewritePattern):
    """Lower SplitOp into UnpackQubitRegOp and PackQubitRegOp."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: SplitOp, rewriter: PatternRewriter) -> None:
        """Lowers SplitOp into UnpackQubitRegOp and PackQubitRegOp."""

        in_reg = op.in_reg
        assert _is_qubit_reg(in_reg), "SplitOp operand must be of QubitRegType"

        # Unpack the input register into individual qubits
        unpack_op = UnpackQubitRegOp(in_reg)
        rewriter.insert_op(unpack_op, InsertPoint.before(rewriter.current_operation))

        # Create new PackQubitRegOps for each output register
        new_pack_ops: list[PackQubitRegOp] = []
        qubit_offset = 0

        for result in op.out_regs:
            result_type = result.type
            num_qubits = len(result_type)

            # Get the slice of qubits for this output register
            qubits_for_this_result = unpack_op.results[qubit_offset : qubit_offset + num_qubits]

            # Create a PackQubitRegOp for this output register
            pack_op = PackQubitRegOp(qubits_for_this_result)
            new_pack_ops.append(pack_op)

            # Update offset for next iteration
            qubit_offset += num_qubits

        # Replace the original SplitOp with the new PackQubitRegOps
        rewriter.replace_op(
            op,
            new_pack_ops,
            new_results=[result for pack_op in new_pack_ops for result in pack_op.results],
        )
        warn_stim_tag_lost(
            op, "SplitOp is expanded into unpack/pack ops with no single correspondent"
        )


class _BaseFlatteningPattern(RewritePattern):
    """Base class for flattening qubit register operands in operations."""

    def _flatten_operands(
        self,
        operands: Sequence[SSAValue],
    ) -> list[SSAValue]:
        """Flatten operands, expanding qubit registers into individual qubits.

        Returns the flattened operand list.
        """
        new_operands: list[SSAValue] = []
        for operand in operands:
            if _is_qubit_reg(operand) and isinstance(operand.owner, PackQubitRegOp):
                new_operands.extend(operand.owner.qubits)
            else:
                new_operands.append(operand)
        return new_operands

    def _flatten_result_types(
        self,
        results: Sequence[SSAValue],
    ) -> list[Attribute]:
        """Flatten result types, expanding qubit registers into individual qubit types.

        Returns the flattened result type list.
        """
        new_result_types: list[Attribute] = []
        for result in results:
            if _is_qubit_reg(result):
                new_result_types.extend([QubitType()] * len(result.type))
            else:
                new_result_types.append(result.type)
        return new_result_types

    def _map_results(
        self,
        old_results: Sequence[SSAValue],
        new_op_results: Sequence[SSAValue],
    ) -> tuple[list[PackQubitRegOp], list[SSAValue]]:
        """Map flattened results back to register types where needed.

        Returns a tuple of (pack_ops, new_results).
        """
        new_pack_ops: list[PackQubitRegOp] = []
        new_results: list[SSAValue] = []
        result_idx = 0

        for result in old_results:
            if _is_qubit_reg(result):
                num_qubits = len(result.type)
                new_pack_ops.append(
                    PackQubitRegOp(new_op_results[result_idx : result_idx + num_qubits])
                )
                new_results.append(new_pack_ops[-1].reg)
                result_idx += num_qubits
            else:
                new_results.append(new_op_results[result_idx])
                result_idx += 1

        return new_pack_ops, new_results


class _BaseRegionOpPattern(_BaseFlatteningPattern):
    """Base class for flattening qubit register arguments in operations with regions."""

    def _flatten_args_and_block_args(
        self, args: Sequence[SSAValue], block, rewriter: PatternRewriter, offset: int = 0
    ) -> list[SSAValue]:
        """Flatten arguments and simultaneously modify block arguments.

        Returns the flattened argument list.
        """
        new_args: list[SSAValue] = []
        block_arg_idx = offset

        for arg in args:
            if _is_qubit_reg(arg) and isinstance(arg.owner, PackQubitRegOp):
                # Flatten the argument
                num_qubits = len(arg.type)
                new_args.extend(arg.owner.qubits)

                # Insert new individual qubit block arguments
                new_block_args = [
                    rewriter.insert_block_argument(block, block_arg_idx + i, QubitType())
                    for i in range(num_qubits)
                ]

                # Collect new qubits into a register and replace old block argument uses with the
                # new register
                old_block_arg = block.args[block_arg_idx + num_qubits]
                pack_op = rewriter.insert_op(
                    PackQubitRegOp(new_block_args), InsertPoint.at_start(block)
                )
                rewriter.replace_all_uses_with(old_block_arg, pack_op.reg)
                rewriter.erase_block_argument(old_block_arg)

                block_arg_idx += num_qubits
            else:
                new_args.append(arg)
                block_arg_idx += 1

        return new_args


class _AllocPattern(_BaseFlatteningPattern):
    """Replaces AllocQubitOp with qubit register results with a single AllocQubitOp which only
    allocates individual qubits."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: AllocQubitOp, rewriter: PatternRewriter) -> None:
        """Replaces AllocQubitOp with qubit register results with a single AllocQubitOp which only
        allocates individual qubits."""
        has_any_reg_results = any(_is_qubit_reg(result) for result in op.result)

        if not has_any_reg_results:
            return

        new_result_types = self._flatten_result_types(op.results)
        assert isa(new_result_types, list[QubitType])
        new_alloc_op = AllocQubitOp(results=new_result_types, coordinates=op.coords)
        new_pack_ops, new_results = self._map_results(op.results, new_alloc_op.results)
        rewriter.replace_op(op, [new_alloc_op, *new_pack_ops], new_results)


class _CircuitPattern(_BaseRegionOpPattern):
    """Lower CircuitOp with qubit register arguments into CircuitOp with individual qubits."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.CircuitOp, rewriter: PatternRewriter) -> None:
        """Lowers CircuitOp with qubit register arguments/results into individual qubits."""
        has_reg_args = any(
            _is_qubit_reg(arg) and isinstance(arg.owner, PackQubitRegOp) for arg in op.args
        )
        has_reg_results = any(_is_qubit_reg(result) for result in op.results)

        if not (has_reg_args or has_reg_results):
            return

        # Move body to new region first
        new_body = rewriter.move_region_contents_to_new_regions(op.body)
        block = new_body.block

        # Flatten arguments and block arguments
        new_args = self._flatten_args_and_block_args(op.args, block, rewriter)

        # Flatten result types
        new_result_types = self._flatten_result_types(op.results)

        new_circuit_op = qstruct.CircuitOp(
            new_args,
            result_types=new_result_types,
            body=new_body,
        )

        # Map results back to register types
        new_pack_ops, new_results = self._map_results(op.results, new_circuit_op.results)

        rewriter.replace_op(op, [new_circuit_op, *new_pack_ops], new_results)
        copy_stim_tag(op, new_circuit_op)


class _RepeatPattern(_BaseRegionOpPattern):
    """Lower RepeatOp with qubit register arguments into RepeatOp with individual qubits."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.RepeatOp, rewriter: PatternRewriter) -> None:
        """Lowers RepeatOp with qubit register iter_args into individual qubits."""
        has_reg_iter_args = any(
            _is_qubit_reg(arg) and isinstance(arg.owner, PackQubitRegOp) for arg in op.iter_args
        )

        if not has_reg_iter_args:
            return

        # Move body to new region first
        new_body = rewriter.move_region_contents_to_new_regions(op.body)
        block = new_body.block

        # Flatten iter_args and block arguments
        new_iter_args = self._flatten_args_and_block_args(op.iter_args, block, rewriter)

        new_repeat_op = qstruct.RepeatOp(
            op.repetitions,
            body=new_body,
            iter_args=new_iter_args,
        )

        # Map results back to register types
        new_pack_ops, new_results = self._map_results(op.results, new_repeat_op.results)

        rewriter.replace_op(op, [new_repeat_op, *new_pack_ops], new_results)
        copy_stim_tag(op, new_repeat_op)


class _ParallelPattern(_BaseFlatteningPattern):
    """Lower ParallelOp with qubit register results into ParallelOp with individual qubits."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.ParallelOp, rewriter: PatternRewriter) -> None:
        """Lowers ParallelOp with qubit register results into ParallelOp with individual qubits."""
        has_reg_results = any(_is_qubit_reg(result) for result in op.results)

        if not has_reg_results:
            return

        # Flatten result types
        new_result_types = self._flatten_result_types(op.results)

        new_parallel_op = qstruct.ParallelOp(
            result_types=new_result_types,
            par_regions=[
                rewriter.move_region_contents_to_new_regions(region) for region in op.par_regions
            ],
            alignment=op.alignment,
        )

        # Map results back to register types
        new_pack_ops, new_results = self._map_results(op.results, new_parallel_op.results)

        rewriter.replace_op(op, [new_parallel_op, *new_pack_ops], new_results)
        copy_stim_tag(op, new_parallel_op)


class _YieldPattern(_BaseFlatteningPattern):
    """Lower YieldOp with qubit register operands into YieldOp with individual qubits."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(
        self, op: scf.YieldOp | qstruct.YieldOp, rewriter: PatternRewriter
    ) -> None:
        """Lowers YieldOp with qubit register operands into individual qubits."""
        has_reg_operands = any(
            _is_qubit_reg(operand) and isinstance(operand.owner, PackQubitRegOp)
            for operand in op.operands
        )

        if not has_reg_operands:
            return

        new_operands = self._flatten_operands(op.operands)
        new_yield_op = (
            scf.YieldOp(*new_operands)
            if isinstance(op, scf.YieldOp)
            else qstruct.YieldOp(*new_operands)
        )
        rewriter.replace_op(op, new_yield_op)
        copy_stim_tag(op, new_yield_op)


class _ConditionPattern(_BaseRegionOpPattern):
    """Lower ConditionOp with qubit register arguments into ConditionOp with individual qubits."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: scf.ConditionOp, rewriter: PatternRewriter) -> None:
        has_reg_args = any(
            _is_qubit_reg(arg) and isinstance(arg.owner, PackQubitRegOp) for arg in op.args
        )

        if not has_reg_args:
            return
        parent = op.parent_op()
        assert isinstance(parent, scf.WhileOp), "ConditionOp should only be used within WhileOp"
        new_args = self._flatten_args_and_block_args(op.args, parent.after_region.block, rewriter)
        new_condition_op = scf.ConditionOp(
            op.condition,
            *new_args,
        )
        rewriter.replace_op(op, new_condition_op)
        copy_stim_tag(op, new_condition_op)


class _ForPattern(_BaseRegionOpPattern):
    """Lower ForOp with qubit register iter_args into ForOp with individual qubits."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: scf.ForOp, rewriter: PatternRewriter) -> None:
        """Lowers ForOp with qubit register iter_args into individual qubits."""
        has_reg_iter_args = any(
            _is_qubit_reg(arg) and isinstance(arg.owner, PackQubitRegOp) for arg in op.iter_args
        )

        if not has_reg_iter_args:
            return

        # Move body to new region first
        new_body = rewriter.move_region_contents_to_new_regions(op.body)
        block = new_body.block

        # Flatten iter_args and block arguments. Offset of 1 as the induction variable is the
        # first block argument.
        new_iter_args = self._flatten_args_and_block_args(op.iter_args, block, rewriter, 1)

        new_for_op = scf.ForOp(
            op.lb,
            op.ub,
            op.step,
            body=new_body,
            iter_args=new_iter_args,
        )

        # Map results back to register types
        new_pack_ops, new_results = self._map_results(op.results, new_for_op.results)

        rewriter.replace_op(op, [new_for_op, *new_pack_ops], new_results)
        copy_stim_tag(op, new_for_op)


class _WhilePattern(_BaseRegionOpPattern):
    """Lower WhileOp with qubit register arguments into WhileOp with individual qubits."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: scf.WhileOp, rewriter: PatternRewriter) -> None:
        """Lowers WhileOp with qubit register arguments into individual qubits."""
        has_reg_args = any(
            _is_qubit_reg(arg) and isinstance(arg.owner, PackQubitRegOp) for arg in op.arguments
        )
        has_reg_results = any(_is_qubit_reg(result) for result in op.results)

        if not has_reg_args and not has_reg_results:
            return

        # Move body to new regions first
        new_before_region = rewriter.move_region_contents_to_new_regions(op.before_region)
        new_after_region = rewriter.move_region_contents_to_new_regions(op.after_region)

        # Flatten arguments and block arguments in before region. After region is handled by
        # the ConditionOp pattern.
        new_arguments = self._flatten_args_and_block_args(
            op.arguments, new_before_region.block, rewriter
        )

        # Flatten result types
        new_result_types = self._flatten_result_types(op.results)

        new_while_op = scf.WhileOp(
            arguments=new_arguments,
            result_types=new_result_types,
            before_region=new_before_region,
            after_region=new_after_region,
        )

        # Map results back to register types
        new_pack_ops, new_results = self._map_results(op.results, new_while_op.results)

        rewriter.replace_op(op, [new_while_op, *new_pack_ops], new_results)
        copy_stim_tag(op, new_while_op)


class _IfPattern(_BaseRegionOpPattern):
    """Lower IfOp with qubit register arguments into IfOp with individual qubits."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: scf.IfOp, rewriter: PatternRewriter) -> None:
        """Lowers IfOp with qubit register arguments into individual qubits."""
        has_reg_results = any(_is_qubit_reg(arg) for arg in op.output)

        if not has_reg_results:
            return

        # Flatten result types
        new_result_types = self._flatten_result_types(op.results)

        new_if_op = scf.IfOp(
            cond=op.cond,
            return_types=new_result_types,
            true_region=rewriter.move_region_contents_to_new_regions(op.true_region),
            false_region=rewriter.move_region_contents_to_new_regions(op.false_region),
        )

        # Map results back to register types
        new_pack_ops, new_results = self._map_results(op.results, new_if_op.results)
        rewriter.replace_op(op, [new_if_op, *new_pack_ops], new_results)
        copy_stim_tag(op, new_if_op)


class _IndexSwitchPattern(_BaseRegionOpPattern):
    """Lowers IndexSwitchOp with qubit register arguments into individual qubits."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: scf.IndexSwitchOp, rewriter: PatternRewriter) -> None:
        has_reg_results = any(_is_qubit_reg(res) for res in op.output)

        if not has_reg_results:
            return

        # Flatten result types
        new_result_types = self._flatten_result_types(op.results)

        new_index_switch_op = scf.IndexSwitchOp(
            arg=op.arg,
            cases=op.cases,
            case_regions=[
                rewriter.move_region_contents_to_new_regions(case) for case in op.case_regions
            ],
            default_region=rewriter.move_region_contents_to_new_regions(op.default_region),
            result_types=new_result_types,
        )

        # Map results back to register types
        new_pack_ops, new_results = self._map_results(op.results, new_index_switch_op.results)
        rewriter.replace_op(op, [new_index_switch_op, *new_pack_ops], new_results)
        copy_stim_tag(op, new_index_switch_op)


def _verify_no_qubit_registers(op: Operation) -> None:
    """Verifies that no QubitRegType values exist as block arguments, or results."""
    # Don't need to check operands as they are either be a result from another operation or a block
    # argument, so will be checked by one of the other two checks.

    # Check results
    for result in op.results:
        if _is_qubit_reg(result):
            msg = (
                "flatten_qubit_registers: "
                f"Found QubitRegType result in {op.name} at {op}. "
                f"All qubit registers should have been flattened."
            )
            raise ValueError(msg)

    # Check block arguments
    for region in op.regions:
        for block in region.blocks:
            for arg in block.args:
                if _is_qubit_reg(arg):
                    msg = (
                        "flatten_qubit_registers: "
                        f"Found QubitRegType block argument in {op.name} at {op}. "
                        f"All qubit registers should have been flattened."
                    )
                    raise ValueError(msg)


def flatten_qubit_registers(region: Region) -> None:
    """Flatten qubit registers in the given region.

    All qubit registers introduced within the region are replaced with individual qubits.
    If the region uses qubit register SSA values from outside the region, these are unpacked at the
    first use and the unpacked qubits are used afterwards.
    The results and operands of the op containing the region are not adjusted, so be cautious when
    using this function with regions of ops with qubit register operands or results.
    """

    PatternRewriteWalker(
        GreedyRewritePatternApplier(
            [
                _AllocPattern(),
                _ConcatenatePattern(),
                _SplitPattern(),
                RemoveRedundantUnpackAfterPack(),
                _CircuitPattern(),
                _RepeatPattern(),
                _YieldPattern(),
                _ConditionPattern(),
                _ForPattern(),
                _WhilePattern(),
                _IfPattern(),
                _IndexSwitchPattern(),
                _ParallelPattern(),
            ],
        )
    ).rewrite_region(region)


@dataclass(frozen=True)
class FlattenQubitRegisters(ModulePass):
    """Pass that flattens qubit registers in the circuit.

    After this pass, there should be no SSAValues of QubitRegType. All qubits should be represented
    as individual SSAValues of QubitType.
    """

    name = "flatten-qubit-registers"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        flatten_qubit_registers(op.body)

        # Verify that all qubit registers have been flattened
        for operation in op.walk():
            _verify_no_qubit_registers(operation)
