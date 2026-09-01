# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Compiler pass converting stabiliser circuits into qstruct circuits."""

from dataclasses import dataclass
from typing import cast

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp, UnrealizedConversionCastOp
from xdsl.ir import Attribute, Block, Region, SSAValue
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

from deltakit_compile.dialects import qstruct
from deltakit_compile.dialects import stabiliser as stab
from deltakit_compile.dialects.qcore import (
    PackQubitRegOp,
    QubitRegType,
    UnpackQubitRegOp,
)
from deltakit_compile.passes._patterns import ControlFlowUnrealizedCastTypeConversionPattern


class _LowerStabCircuit(RewritePattern):
    """Lower a `stab.circuit` op to a `qstruct.circuit`.

    Note that:
    - `stab` uses a state value (`!stab.state<...>`).
    - `qstruct` uses a packed register (`!qcore.qubit_reg<N>`).

    We bridge these using pack/unpack operations and (temporarily) unrealised casts that are
    later reconciled.
    """

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stab.CircuitOp, rewriter: PatternRewriter) -> None:
        input_state = op.input
        yield_op = op.yield_op
        qubit_reg_type = QubitRegType(op.output.type.qubits)

        new_body = Block(arg_types=list(op.input_args.types))
        input_args = list(new_body.args)
        unpack_op = UnpackQubitRegOp(
            cast(SSAValue[QubitRegType], new_body.insert_arg(qubit_reg_type, 0))
        )
        new_body.add_op(unpack_op)
        rewriter.inline_block(
            op.body.block, InsertPoint.at_end(new_body), [*unpack_op.qubits, *input_args]
        )
        pack_op = PackQubitRegOp(unpack_op.qubits)
        rewriter.replace_op(yield_op, [pack_op, qstruct.YieldOp(pack_op.reg, *yield_op.arguments)])
        cast_op = UnrealizedConversionCastOp.get([input_state], [qubit_reg_type])
        new_circuit_op = qstruct.CircuitOp(
            [*cast_op.outputs, *op.input_args],
            [qubit_reg_type, *op.output_args.types],
            Region(new_body),
        )
        cast_back = UnrealizedConversionCastOp.get([new_circuit_op.res[0]], [op.output.type])
        rewriter.replace_op(
            op, [cast_op, new_circuit_op, cast_back], [*cast_back.outputs, *new_circuit_op.res[1:]]
        )


class _LowerStabMake(RewritePattern):
    """Lower `stab.state.make` to a packed qubit register plus casts.

    This preserves intermediate types by:
    - directly packing the input qubit SSA values into `!qcore.qubit_reg<N>`, and
    - emitting an unrealised cast back to the original stabiliser state type.

    The unrealised cast is expected to be removed/reconciled once all surrounding `stab.circuit`
    ops have been lowered.
    """

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stab.StateMakeOp, rewriter: PatternRewriter) -> None:
        new_op = PackQubitRegOp(op.input_qubits)
        cast_op, output = UnrealizedConversionCastOp.cast_one(new_op.reg, op.output.type)
        rewriter.replace_op(op, [new_op, cast_op], [output])


class _LowerStabCast(RewritePattern):
    """Erase `stab.state.cast`.

    `stab.state.cast` only adjusts the stabiliser state's flow data. It does
    not correspond to a computational operation on the underlying qubits, so in this lowering we
    simply forward the input SSA value.
    """

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stab.StateCastOp, rewriter: PatternRewriter) -> None:
        cast_op, output = UnrealizedConversionCastOp.cast_one(op.input, op.output.type)
        rewriter.replace_op(op, [cast_op], [output])


class _ConvertStabStateTypes(ControlFlowUnrealizedCastTypeConversionPattern):
    """Convert all !stab.state types in control flow ops to appropriate !qcore.qubit_reg types."""

    @override
    def convert_type(self, type_: Attribute) -> QubitRegType | None:
        if isinstance(type_, stab.StateType):
            return QubitRegType(type_.total_qubits)
        return None


@dataclass(frozen=True)
class StabCircuitToQstruct(ModulePass):
    """Convert all stabiliser circuits in a module to qstruct circuits.

    This pass lowers each `stab.circuit` to a `qstruct.circuit` by:

    - packing the circuit's input qubits into a single `!qcore.qubit_reg<N>` argument,
    - unpacking the register inside the new `qstruct.circuit` body,
    - inlining the original stabiliser body with a block-argument mapping, and
    - yielding a repacked register.

    Importantly, all extra (non-qubit) operands and all intermediate SSA values in the body keep
    their original types. The rewrite only changes the state/qubit boundary representation.
    """

    name = "stab-circuit-to-qstruct"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        """Apply the stab-to-qstruct conversion rewrites to a module.

        Args:
            ctx: context in which to apply the rewrite. Ignored by this pass.
            op: The module operation to rewrite.
        """
        # Traverse the module and apply the conversion pattern to each stab.CircuitOp
        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [
                    _LowerStabCircuit(),
                    _LowerStabMake(),
                    _LowerStabCast(),
                ]
            )
        ).rewrite_module(op)

        PatternRewriteWalker(_ConvertStabStateTypes(), apply_recursively=False).rewrite_module(op)

        PatternRewriteWalker(ReconcileUnrealizedCastsPattern()).rewrite_module(op)
