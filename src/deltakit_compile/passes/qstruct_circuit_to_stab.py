# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Pass converting qstruct circuits into stabiliser circuits."""

import itertools
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp, UnrealizedConversionCastOp
from xdsl.ir import Attribute, Block, Operation, OpResult, SSAValue, Use
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    GreedyRewritePatternApplier,
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.rewriter import InsertPoint
from xdsl.transforms.reconcile_unrealized_casts import ReconcileUnrealizedCastsPattern
from xdsl.utils.hints import isa

from deltakit_compile.dialects import qcore, qref, qstruct, sobs
from deltakit_compile.dialects import stabiliser as stab
from deltakit_compile.dialects.qcore import HasCircuitAncestor, qubit_count
from deltakit_compile.passes._patterns import ControlFlowUnrealizedCastTypeConversionPattern
from deltakit_compile.passes.flatten_qubit_registers import flatten_qubit_registers


def _cast_regs_to_states(
    qubits_or_regs: Iterable[SSAValue],
) -> tuple[list[UnrealizedConversionCastOp], list[SSAValue[stab.StateType]]]:
    casts_and_results = [
        UnrealizedConversionCastOp.cast_one(
            qubit_or_reg, stab.StateType(qubit_count(qubit_or_reg.type), qcore.QubitType(), [])
        )
        for qubit_or_reg in qubits_or_regs
    ]
    return [cast for cast, _ in casts_and_results], [result for _, result in casts_and_results]


def _cast_to_types(
    values: Iterable[SSAValue],
    type_pattern: Iterable[SSAValue],
) -> tuple[list[UnrealizedConversionCastOp], list[SSAValue]]:
    casts_and_results = [
        UnrealizedConversionCastOp.cast_one(state, target_value.type)
        for state, target_value in zip(values, type_pattern, strict=True)
    ]
    return [cast for cast, _ in casts_and_results], [result for _, result in casts_and_results]


def _split_qubits_and_others(values: Iterable[SSAValue]) -> tuple[list[SSAValue], list[SSAValue]]:
    qubits, others = [], []
    for value in values:
        if isinstance(value.type, (qcore.QubitType, qcore.QubitRegType)):
            qubits.append(value)
        else:
            others.append(value)
    return qubits, others


def _interleave_qubits_and_others(
    qubits: Sequence[SSAValue], others: Sequence[SSAValue], original_order: Sequence[SSAValue]
) -> list[SSAValue]:
    qubit_iter = iter(qubits)
    other_iter = iter(others)
    return [
        next(qubit_iter)
        if isinstance(value.type, (qcore.QubitType, qcore.QubitRegType))
        else next(other_iter)
        for value in original_order
    ]


class _QCoreAllocToStabMake(RewritePattern):
    """Add stab.make ops after each qcore.alloc_qubit op to convert qubit registers to stab states.

    The resulting stabiliser states are casted back to qubit registers using unrealised casts which
    are expected to be reconciled at the end.
    """

    @staticmethod
    def _make_state_make(alloc_result: SSAValue) -> tuple[list[Operation], SSAValue]:
        """Return a list of ops that convert the given qubit or register to a stab.state and cast it
        back to the original type, along with the cast result."""

        new_ops = list[Operation]()

        if isa(alloc_result, SSAValue[qcore.QubitRegType]):
            unpack_op = qcore.UnpackQubitRegOp(alloc_result)
            new_ops.append(unpack_op)
            qubits: Sequence[SSAValue[qcore.QubitType]] = unpack_op.qubits
        else:
            assert isa(alloc_result, SSAValue[qcore.QubitType])
            qubits = [alloc_result]

        make_op = stab.StateMakeOp(qubits, stab.StateType(len(qubits), qcore.QubitType(), []))
        cast_op, cast_result = UnrealizedConversionCastOp.cast_one(
            make_op.output, alloc_result.type
        )

        new_ops.extend([make_op, cast_op])
        return new_ops, cast_result

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qcore.AllocQubitOp, rewriter: PatternRewriter) -> None:
        new_ops: list[Operation] = []
        new_qubit_results: list[SSAValue] = []

        for alloc_result in op.results:
            alloc_new_ops, new_qubit_result = self._make_state_make(alloc_result)
            new_ops.extend(alloc_new_ops)
            new_qubit_results.append(new_qubit_result)

        rewriter.insert_op(new_ops, InsertPoint.after(op))

        new_ops_set = set(new_ops)
        for old_result, new_result in zip(op.results, new_qubit_results, strict=True):
            rewriter.replace_uses_with_if(
                old_result, new_result, lambda use: use.operation not in new_ops_set
            )


class _QStructToStabCircuit(RewritePattern):
    """Convert a qstruct.circuit op to a stab.circuit.

    Each qubit/register is converted to a stab.state using an unrealised cast and a stab.concatenate
    op is used to combine them into a single state for the stab.circuit. The qubit/register
    arguments expected by the circuit body are reconstructed using pack/unpack ops. This pass
    therefore leaves qcore operations within the circuit body which are expected to be unravelled
    in a later rewrite.

    The unrealised casts are expected to be reconciled once all surrounding qstruct ops have been
    converted.
    """

    @staticmethod
    def _calculate_circuit_permutation(circuit_op: qstruct.CircuitOp) -> list[int]:
        """Calculate a permutation describing how circuit_op reorders its qubits.

        Args:
            circuit_op: The qstruct circuit for which to calculate the permutation.

        Returns:
            A list of integers representing the permutation. The ith qubit in the input arguments to
            circuit_op is sent to the permutation[i]'th qubit in the output.

        Raises:
            NotImplementedError: If an unknown operation affecting qubits is encountered.
        """
        qubit_counter = itertools.count()
        qubit_to_idx: dict[tuple[SSAValue, int], int] = {
            (arg, idx): next(qubit_counter)
            for arg in circuit_op.body.block.args
            for idx in range(qubit_count(arg.type))
        }

        for op in circuit_op.walk(region_first=True):
            if isinstance(op, (qcore.PackQubitRegOp, qcore.ConcatenateOp)):
                in_regs = op.in_regs if isinstance(op, qcore.ConcatenateOp) else op.qubits
                out_reg: SSAValue = op.out_reg if isinstance(op, qcore.ConcatenateOp) else op.reg
                offset = 0
                for in_reg in in_regs:
                    for idx in range(qubit_count(in_reg.type)):
                        qubit_to_idx[out_reg, offset + idx] = qubit_to_idx[in_reg, idx]
                    offset += qubit_count(in_reg.type)
            elif isinstance(op, (qcore.UnpackQubitRegOp, qcore.SplitOp)):
                in_reg = op.in_reg if isinstance(op, qcore.SplitOp) else op.reg
                out_regs = op.out_regs if isinstance(op, qcore.SplitOp) else op.qubits
                offset = 0
                for out_reg in out_regs:
                    for idx in range(qubit_count(out_reg.type)):
                        qubit_to_idx[out_reg, idx] = qubit_to_idx[in_reg, offset + idx]
                    offset += qubit_count(out_reg.type)
            elif isinstance(op, qstruct.ParallelOp):
                for result in op.results:
                    for idx in range(qubit_count(result.type)):
                        yielded = op.result_to_yield_arg(result)
                        qubit_to_idx[result, idx] = qubit_to_idx[yielded, idx]
            elif not isinstance(
                op,
                (
                    qstruct.YieldOp,
                    qstruct.CircuitOp,
                    qref.GateLikeOp,
                    sobs.DecObservableOp,
                    sobs.LocateObservableOp,
                    sobs.MoveObservableOp,
                ),
            ):
                # If we see an op we don't understand which uses qubits, we can't know whether it
                # affects the permutation, so we throw an error.
                # walk() will also walk the circuit op, so ignore it too.
                if any(
                    isinstance(arg.type, (qcore.QubitType, qcore.QubitRegType))
                    for arg in [*op.operands, *op.results]
                ):
                    msg = f"Cannot calculate permutation through unknown op {op} in qstruct circuit"
                    raise NotImplementedError(msg)

        return [
            qubit_to_idx[yield_arg, idx]
            for yield_arg in circuit_op.yield_op.arguments
            for idx in range(qubit_count(yield_arg.type))
        ]

    @staticmethod
    def _recover_register_format(
        new_qubit_args: Sequence[SSAValue],
        new_other_args: Iterable[SSAValue],
        original_args: Iterable[SSAValue],
    ) -> tuple[list[Operation], list[SSAValue]]:
        """Recover the original register format expected by the circuit body by packing qubits.

        Args:
            new_qubit_args: The individual qubit arguments to the new stab.circuit body.
            new_other_args: The non-qubit arguments to the new stab.circuit body.
            original_args: The original arguments to the qstruct.circuit body. There must be as many
                qubits in the registers in these arguments as there are in new_qubit_args.

        Returns:
            pack_ops: A list of pack operations to pack the individual qubits back into registers.
            replacement_args: A list of SSA values derived from the outputs of the pack ops whose
                types match original_args, to be used to replace original_args in the circuit body.
        """
        pack_ops = list[Operation]()
        replacement_args = list[SSAValue]()

        num_qubits_seen = 0
        other_arg_iter = iter(new_other_args)
        for arg in original_args:
            if isinstance(arg.type, qcore.QubitType):
                replacement_args.append(new_qubit_args[num_qubits_seen])
                num_qubits_seen += 1
            elif isinstance(arg.type, qcore.QubitRegType):
                reg_size = qubit_count(arg.type)
                reg_qubits = new_qubit_args[num_qubits_seen : num_qubits_seen + reg_size]
                num_qubits_seen += reg_size

                pack_op = qcore.PackQubitRegOp(reg_qubits)
                pack_ops.append(pack_op)
                replacement_args.append(pack_op.reg)
            else:
                replacement_args.append(next(other_arg_iter))

        return (pack_ops, replacement_args)

    @staticmethod
    def _reindex_concrete_flow_array(
        concrete_flow_array: stab.ConcreteFlowArrayAttr | None, yield_types: Sequence[Attribute]
    ) -> stab.ConcreteFlowArrayAttr | None:
        """Given a concrete flow array indexing into a qstruct.circuit, return an equivalent
        concrete flow array indexing into the generated stab.circuit, or None if input is None."""
        if concrete_flow_array is None:
            return None

        # The qubit operands (including the input stab.state) are in the same order in both the
        # qstruct and stab circuits, so we don't need to reindex the flow states.
        # The stab.circuit outputs are in the same order as the qstruct.circuit yields, except the
        # qubit yields are compressed into a single stab.state at the beginning.
        # Thus, we just reindex the concrete flows to remove the qubit yields, then add 1 to each
        # measurement index to account for the new input state at position 0.
        qubit_indices = {
            idx
            for idx, type_ in enumerate(yield_types)
            if isinstance(type_, (qcore.QubitType, qcore.QubitRegType))
        }
        return concrete_flow_array.with_reindexed_measurements(
            removed_indices=qubit_indices, shift=1
        )

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: qstruct.CircuitOp, rewriter: PatternRewriter) -> None:
        if (par := op.parent_op()) is not None and HasCircuitAncestor.has_circuit_ancestor(par):
            msg = "Nested circuits are not supported in qstruct-circuit-to-stab"  # pragma: no cover
            raise NotImplementedError(msg)

        # the permutation describing how the circuit reorders the qubits, which we will need to
        # apply using stab.permute
        permutation = self._calculate_circuit_permutation(op)

        yield_op = op.yield_op
        qubit_reg_args, other_args = _split_qubits_and_others(op.args)

        num_qubits = sum(qubit_count(arg.type) for arg in qubit_reg_args)
        other_arg_types = [arg.type for arg in other_args]
        new_body = Block(arg_types=[qcore.QubitType()] * num_qubits + other_arg_types)
        new_qubit_args = list(new_body.args[:num_qubits])
        new_other_args = list(new_body.args[num_qubits:])

        # Pack the qubits back into their original register format for the circuit body - the pack
        # ops will be flattened out later
        pack_ops, replacement_args = self._recover_register_format(
            new_qubit_args, new_other_args, op.args
        )
        new_body.add_ops(pack_ops)
        rewriter.inline_block(op.body.block, InsertPoint.at_end(new_body), replacement_args)

        # Note the values of these arguments were updated to use replacement_args by the inlining
        qubit_reg_yields, other_yields = _split_qubits_and_others(yield_op.arguments)
        new_yield = stab.YieldOp(measurements=[], arguments=other_yields)
        rewriter.replace_op(yield_op, new_yield)

        cast_to_state, stab_states = _cast_regs_to_states(qubit_reg_args)
        concatenate = stab.StateConcatenateOp(stab_states)

        # Copy any concrete flows from the original circuit to be used later, reindexing as needed
        attributes = {
            stab.ConcreteFlowArrayAttr.KEY: self._reindex_concrete_flow_array(
                stab.ConcreteFlowArrayAttr.get(op), yield_op.arguments.types
            ),
            stab.ConcreteFlowArrayAttr.DROPPABLE_FLOWS_KEY: op.attributes.get(
                stab.ConcreteFlowArrayAttr.DROPPABLE_FLOWS_KEY
            ),
        }

        new_circuit_op = stab.CircuitOp(
            input_state=concatenate.output,
            output_state_type=stab.StateType(num_qubits, qcore.QubitType(), []),
            input_args=other_args,
            body=new_body,
            output_args_types=[yield_arg.type for yield_arg in other_yields],
            attributes=attributes,
        )

        # reconstruct the original register format for the circuit yields by permuting and splitting
        permute = stab.StatePermuteOp(new_circuit_op.output, permutation)
        split = stab.StateSplitOp(
            permute.output,
            [qubit_count(qubit_yield.type) for qubit_yield in qubit_reg_yields],
        )
        cast_back, qubit_outputs = _cast_to_types(split.outputs, qubit_reg_yields)
        interleaved_outputs = _interleave_qubits_and_others(
            qubit_outputs, new_circuit_op.output_args, yield_op.arguments
        )
        rewriter.replace_op(
            op,
            [*cast_to_state, concatenate, new_circuit_op, permute, split, *cast_back],
            interleaved_outputs,
        )


class _LowerQCoreConcatenatePack(RewritePattern):
    """Convert qcore.concatenate and qcore.pack_qubit_reg outside circuits to stab.concatenate."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(
        self, op: qcore.ConcatenateOp | qcore.PackQubitRegOp, rewriter: PatternRewriter
    ) -> None:
        if HasCircuitAncestor.has_circuit_ancestor(op):
            return

        input_regs = op.in_regs if isinstance(op, qcore.ConcatenateOp) else op.qubits
        output_reg = op.out_reg if isinstance(op, qcore.ConcatenateOp) else op.reg

        cast_to_state, stab_states = _cast_regs_to_states(input_regs)
        concatenate = stab.StateConcatenateOp(stab_states)
        cast_back, result = UnrealizedConversionCastOp.cast_one(concatenate.output, output_reg.type)
        rewriter.replace_op(op, [*cast_to_state, concatenate, cast_back], [result])


class _LowerQCoreSplitUnpack(RewritePattern):
    """Convert qcore.split and qcore.unpack_qubit_reg outside circuits to stab.split."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(
        self, op: qcore.SplitOp | qcore.UnpackQubitRegOp, rewriter: PatternRewriter
    ) -> None:
        if HasCircuitAncestor.has_circuit_ancestor(op):
            return

        input_reg = op.in_reg if isinstance(op, qcore.SplitOp) else op.reg
        output_regs = op.out_regs if isinstance(op, qcore.SplitOp) else op.qubits

        cast_to_state, stab_state = UnrealizedConversionCastOp.cast_one(
            input_reg, stab.StateType(qubit_count(input_reg.type), qcore.QubitType(), [])
        )
        split = stab.StateSplitOp(stab_state, [qubit_count(reg.type) for reg in output_regs])
        cast_back, new_output_regs = _cast_to_types(split.outputs, output_regs)
        rewriter.replace_op(op, [cast_to_state, split, *cast_back], new_output_regs)


@dataclass(frozen=True)
class _ConvertQubitTypesToStabStates(ControlFlowUnrealizedCastTypeConversionPattern):
    """Convert any remaining qubit/register types in control flow to stab.states using unrealised
    casts, to be reconciled at the end.

    Don't convert any control flow ops inside circuits; note qstruct.parallel ops are allowed inside
    circuits.
    """

    def _should_disallow(self, op: Operation) -> bool:
        return HasCircuitAncestor.has_circuit_ancestor(op)

    @override
    def should_convert_operand(self, use: Use) -> bool:
        return super().should_convert_operand(use) and not self._should_disallow(use.operation)

    @override
    def should_convert_result(self, result: OpResult) -> bool:
        return super().should_convert_result(result) and not self._should_disallow(result.op)

    @override
    def should_convert_block_arg(self, block_arg):
        return super().should_convert_block_arg(block_arg) and not self._should_disallow(
            block_arg.owner.parent_op()
        )

    @override
    def convert_type(self, type_: Attribute) -> stab.StateType | None:
        if isinstance(type_, (qcore.QubitType, qcore.QubitRegType)):
            return stab.StateType(qubit_count(type_), qcore.QubitType(), [])
        return None


@dataclass(frozen=True)
class QStructCircuitToStabPass(ModulePass):
    """Convert all qstruct circuits in a module to stabiliser circuits.

    Every qcore.qubit or qcore.qubit_reg which occurs outside a circuit is converted to a stab.state
    and all operations on the qubits/regs (split, concatenate, etc.) are converted to their stab
    equivalents. To convert each qstruct.circuit, the stab.states corresponding to the arguments
    are concatenated to form the stab.circuit input state and pack/unpack operations are used to
    reconstruct the qubit/reg format expected by the circuit body. The output state is split back
    into the individual stab.states corresponding to the qubits/regs in the qstruct.circuit yields.

    Nested qstruct.circuit ops are not supported.
    """

    name = "qstruct-circuit-to-stab"

    def _flatten_registers_in_stab_circuits(self, module_op: ModuleOp) -> None:
        """Flatten out any qubit registers in stab.circuit bodies which remain at the end."""
        for op in module_op.walk():
            if isinstance(op, stab.CircuitOp):
                flatten_qubit_registers(op.body)

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [
                    _QStructToStabCircuit(),
                    _LowerQCoreConcatenatePack(),
                    _LowerQCoreSplitUnpack(),
                ]
            )
        ).rewrite_module(op)

        # Apply afterwards to avoid lowering qcore.unpack ops generated after allocs
        PatternRewriteWalker(_QCoreAllocToStabMake(), apply_recursively=False).rewrite_module(op)

        PatternRewriteWalker(
            _ConvertQubitTypesToStabStates(), apply_recursively=False
        ).rewrite_module(op)
        PatternRewriteWalker(ReconcileUnrealizedCastsPattern()).rewrite_module(op)

        self._flatten_registers_in_stab_circuits(op)
