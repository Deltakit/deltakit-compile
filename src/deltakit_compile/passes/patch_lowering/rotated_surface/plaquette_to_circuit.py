# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Implement the ``plaquette-to-circuit`` pass that lowers ``plaquette.plaquette`` operations to
``plaquette.sub_circuit`` operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from typing_extensions import override
from xdsl.dialects.builtin import ArrayAttr, IntAttr, ModuleOp
from xdsl.ir import Block, Operation
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    GreedyRewritePatternApplier,
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.utils.hints import isa

from deltakit_compile.dialects import plaquette, qcore, qref
from deltakit_compile.dialects.plaquette import HasRoundAncestor

_ROUND_OP_MAX_SCHEDULE_ATTR_KEY: Final[str] = "plaquette.round.max_synchronised_schedule"

_PAULI_TO_CONTROLLED_GATE: Final[dict[qcore.PauliAttr, qcore.GateAttribute]] = {
    qcore.PauliAttr.X(): qcore.CXGateAttr(),
    qcore.PauliAttr.Y(): qcore.CYGateAttr(),
    qcore.PauliAttr.Z(): qcore.CZGateAttr(),
}


@dataclass
class _AnnotateMaxScheduleOnRoundOpPattern(RewritePattern):
    """Add an entry in the attribute dictionary of valid ``plaquette.round`` operations.

    This pattern will add an ``IntAttr`` value representing the maximum schedule over all the
    ``plaquette.plaquette`` operations in the matched ``plaquette.round`` operation to the attribute
    dictionary of the matched op. The attribute will be added under the key
    ``_ROUND_OP_MAX_SCHEDULE_ATTR_KEY`` and only if the matched operation verifies all the below
    conditions:

    - It contains at least one ``plaquette.plaquette`` operation.
    - All the ``plaquette.plaquette`` operations contained in the matched operation should have a
      measurement method defined (i.e., not ``NoneAttr``), which should be of type
      ``plaquette.SynchronisedScheduleAttr``.
    - All of the ``plaquette.SynchronisedScheduleAttr`` measurement methods are fully scheduled
      (i.e., no ``NoneAttr`` entry in the schedule).
    """

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: plaquette.RoundOp, rewriter: PatternRewriter) -> None:
        plaquette_ops = [wok for wok in op.walk() if isinstance(wok, plaquette.PlaquetteOp)]
        if not plaquette_ops:
            return
        measurement_methods = [plaquette_op.stabs_measurement for plaquette_op in plaquette_ops]
        if not isa(measurement_methods, list[plaquette.SynchronisedScheduleAttr]):
            return
        schedules = [mm.schedule for mm in measurement_methods]
        if not isa(schedules, list[ArrayAttr[IntAttr]]):
            return
        max_schedule = IntAttr(max(max((s.data for s in sched), default=0) for sched in schedules))
        if op.attributes.get(_ROUND_OP_MAX_SCHEDULE_ATTR_KEY) != max_schedule:
            op.attributes[_ROUND_OP_MAX_SCHEDULE_ATTR_KEY] = max_schedule
            rewriter.notify_op_modified(op)


@dataclass
class _ClearMaxScheduleOnRoundOpPattern(RewritePattern):
    """Remove the ``_ROUND_OP_MAX_SCHEDULE_ATTR_KEY`` attribute on ``plaquette.round`` operations.

    This pattern clears up the attributes set by the ``_AnnotateMaxScheduleOnRoundOpPattern``.
    """

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: plaquette.RoundOp, rewriter: PatternRewriter) -> None:
        if _ROUND_OP_MAX_SCHEDULE_ATTR_KEY in op.attributes:
            del op.attributes[_ROUND_OP_MAX_SCHEDULE_ATTR_KEY]
            rewriter.notify_op_modified(op)


@dataclass
class _PlaquetteOpPattern(RewritePattern):
    """Lowers supported ``plaquette.plaquette`` operations into ``plaquette.sub_circuit``.

    Supported ``plaquette.plaquette`` operations check all the conditions below:

    - It must have exactly one stabiliser which must not be the identity.
    - Its stabiliser measurement method is an instance of ``SynchronisedScheduleAttr``.
    - All the entries of ``schedule`` in the stabiliser measurement method should be integers.
    - It must have at least one syndrome qubit.
    - Its parent ``plaquette.round`` operation should have an ``IntAttr`` value under the attribute
      key ``_ROUND_OP_MAX_SCHEDULE_ATTR_KEY`` (should be verified by running
      ``_AnnotateMaxScheduleOnRoundOpPattern`` before this pass).
    """

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: plaquette.PlaquetteOp, rewriter: PatternRewriter) -> None:
        if (
            # Checking the max_schedule annotation on the parent round operation.
            not isinstance(
                parent_round_op := HasRoundAncestor.get_round_ancestor(op), plaquette.RoundOp
            )
            or not isinstance(
                max_schedule := parent_round_op.attributes.get(_ROUND_OP_MAX_SCHEDULE_ATTR_KEY),
                IntAttr,
            )
            # Checking the validity of the stabiliser measurement method.
            or not isinstance(
                stab_measurement_method := op.stabs_measurement, plaquette.SynchronisedScheduleAttr
            )
            or not isa(stab_measurement_method.schedule, ArrayAttr[IntAttr])
            or len(op.ancilla_qubits) < 1
            or len(op.stabilisers) != 1
            or (stabiliser := op.stabilisers.data[0]).is_identity()
        ):
            return
        ancilla_qubit = op.ancilla_qubits[0]
        schedule = tuple(s.data for s in stab_measurement_method.schedule)
        # The ``plaquette.sub_circuit`` will have the following regions:
        # 1.         Reset the syndrome qubit in the X basis.
        reset_layer: list[Operation] = [qref.ResetOp("X", (ancilla_qubit,)), plaquette.YieldOp()]
        # [2 - n+1]. Apply the ``n`` entangling gates specified by the schedule.
        entangling_layers: list[list[Operation]] = [[] for _ in range(max_schedule.data + 1)]
        for sched, data_qubit, pauli in zip(schedule, op.data_qubits, stabiliser, strict=True):
            if pauli is None:
                # Measuring identity on this data qubit: do nothing.
                continue
            entangling_gate = _PAULI_TO_CONTROLLED_GATE[pauli]
            entangling_layers[sched].extend(
                (qref.GateOp(entangling_gate, (ancilla_qubit, data_qubit)), plaquette.YieldOp())
            )
        # n+2.       Measure the syndrome qubit in the X basis.
        measurement_op = qref.MeasureOp("X", (ancilla_qubit,))
        yield_op = plaquette.YieldOp(measurement_op.measurement)
        last_round_ops: list[Operation] = [measurement_op, yield_op]
        # Now build the different blocks, adding yield operations in empty blocks.
        sequential_blocks = [
            Block(layer or [plaquette.YieldOp()])
            for layer in (reset_layer, *entangling_layers, last_round_ops)
        ]
        subcircuit_op = plaquette.SubCircuitOp(sequential_blocks, 1)
        rewriter.replace_op(op, subcircuit_op)


@dataclass(frozen=True)
class PlaquetteToCircuit(ModulePass):
    """Lowers ``plaquette.plaquette`` operations into ``plaquette.sub_circuit`` operations."""

    name = "plaquette-to-circuit"

    @override
    def apply(self, ctx, op: ModuleOp) -> None:
        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [_AnnotateMaxScheduleOnRoundOpPattern(), _PlaquetteOpPattern()]
            )
        ).rewrite_module(op)
        PatternRewriteWalker(_ClearMaxScheduleOnRoundOpPattern()).rewrite_module(op)
