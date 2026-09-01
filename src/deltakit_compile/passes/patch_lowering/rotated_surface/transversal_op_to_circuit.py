# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""This module implements the ``transversal-op-to-circuit`` pass.

This pass will lower all the transversal operations directly to ``qref`` quantum gates,
circumventing the ``plaquette`` dialect entirely because it is an unnecessary step for transversal
operations.

For this module, transversal operations are logical operations that can be lowered to a simple
(trivial might even be a better description) quantum circuit. In practice, this pass handles the
following operations:

- ``log_asm.prepare<P>`` for ``P`` being either ``X`` or ``Z``, by applying a physical reset gate in
  the basis ``P`` to each data-qubit of the patch,
- ``log_asm.measure<P>`` for ``P`` being either ``X`` or ``Z``, by applying a physical measurement
  gate in the basis ``P`` to each data-qubit of the patch.

In the future, this pass should also handle (but does not handle yet):

- All the variants of ``log_asm.transversal``.

The Y-basis ``prepare`` and ``measure`` are not transversal operations (see
https://doi.org/10.22331/q-2024-04-08-1310) and might also not be perfectly fit for the
``plaquette`` dialect. Their implementation is left to the future for the moment.

Warning:
    This pass needs to assume a certain structure of the IR to find the last operation applied on
    the ``!sobs.observable`` (either a ``sobs.locate_observable`` or a ``sobs.dec_observable``) to
    correctly lower the ``log_asm.measure`` operation (which returns a corrected observable). It
    will try its best to find that operation in arbitrary circuits, but may not cover all the edge
    cases. Ideally, this pass should be applied just after ``place-observable``, which will generate
    an IR structure that is guaranteed to be covered here for unplaced-observables (but cannot
    ensure anything for user-provided placed observables).
"""

from dataclasses import dataclass
from typing import cast

from typing_extensions import override
from xdsl.dialects.builtin import ModuleOp, UnitAttr
from xdsl.ir import Block, SSAValue
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    GreedyRewritePatternApplier,
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)

import deltakit_compile.dialects.logical_assembly as logasm
from deltakit_compile.dialects import qcore, qec, qref, qstruct
from deltakit_compile.dialects import stabiliser as stab
from deltakit_compile.dialects.logical_assembly import RotatedPlanarPatchType
from deltakit_compile.dialects.sobs import ObservableType
from deltakit_compile.exceptions import CompilerPassCheckError
from deltakit_compile.shared.patch.rotated_planar._placement import get_data_qubits_indices
from deltakit_compile.shared.patch.rotated_planar._stabilisers import (
    global_stabilisers_for_memory_on_patch,
)


@dataclass(frozen=True)
class _PrepareOpPattern(RewritePattern):
    """Lower ``log_asm.prepare`` operations to ``qstruct.circuit`` with flow annotations."""

    parity: bool

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: logasm.PrepareOp, rewriter: PatternRewriter) -> None:
        patch_type = op.patch.type
        basis = op.basis
        if not isinstance(patch_type, RotatedPlanarPatchType):
            return
        data_qubit_indices = get_data_qubits_indices(patch_type)
        num_qubits = patch_type.num_qubits
        # Patch -> Qubits
        qubit_types = [qcore.QubitType() for _ in range(num_qubits)]
        cast_from_patch_op = logasm.CastOp(op.patch, qcore.QubitRegType(num_qubits))
        unpack_op = qcore.UnpackQubitRegOp(
            cast(SSAValue[qcore.QubitRegType], cast_from_patch_op.out)
        )
        # Building the CircuitOp that will contain the gates
        circuit_body = Block(arg_types=qubit_types)
        circuit_body.add_op(
            qref.ResetOp(op.basis, [circuit_body.args[i] for i in data_qubit_indices])
        )
        circuit_body.add_op(qstruct.YieldOp(*circuit_body.args))
        circuit_op = qstruct.CircuitOp(unpack_op.qubits, qubit_types, [circuit_body])
        # Annotating flows on the generated ``qstruct.circuit`` operation. For the moment, we
        # annotate flows using the knowledge that the only operations that can come after a prepare
        # are ``meas_stab`` or ``measure`` (because no other operation is currently implemented),
        # and so we annotate exactly the right flows.
        # In the future, we will rework that part to make sure the flows annotated are generic
        # enough.
        stabilisers = global_stabilisers_for_memory_on_patch(patch_type, self.parity)

        circuit_op.attributes[stab.ConcreteFlowArrayAttr.KEY] = stab.ConcreteFlowArrayAttr(
            [
                stab.ConcreteFlowAttr(
                    "+",
                    [],
                    qcore.PauliStringAttr.identity(num_qubits),
                    stabiliser,
                )
                for stabiliser in stabilisers
                if (
                    not stabiliser.is_identity()
                    and all(qstate.pauli_state == basis for qstate in stabiliser.qubit_states)
                )
            ]
        )
        # Mark the flows as droppable in case the do not perfectly align with other ops.
        circuit_op.attributes[stab.ConcreteFlowArrayAttr.DROPPABLE_FLOWS_KEY] = UnitAttr()
        # Qubits -> Patch
        pack_op = qcore.PackQubitRegOp(circuit_op.results)
        cast_to_patch_op = logasm.CastOp(pack_op.reg, patch_type)
        rewriter.replace_op(
            op, [cast_from_patch_op, unpack_op, circuit_op, pack_op, cast_to_patch_op]
        )


@dataclass(frozen=True)
class _MeasureOpPattern(RewritePattern):
    """Lower ``log_asm.measure`` operations to ``qstruct.circuit`` with flow annotations.

    This pattern is more complex than the ``log_asm.prepare`` one because it needs to find the
    correct SSA value representing the observable that is being measured by the matched logical
    measurement in order to insert the correct ``sobs`` operations to get the corrected value of
    this observable.

    This pattern will only modify the matched operation if all the following are checked:

    - the matched ``op`` is applied on a ``log_asm.patch.rot_planar``,
    - there is only one observable defined in the block containing ``op`` (in other terms, there is
      only one SSAValue of type ``sobs.observable`` that is not used by any other operation),
    - the unique ``sobs.observable`` SSAValue without any use is visible in the scope of the matched
      ``op`` (i.e., its owner should be in the same block as ``op``).

    If any one of the points above are not checked, the matched operation will be left unchanged.
    """

    parity: bool

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: logasm.MeasureOp, rewriter: PatternRewriter) -> None:
        patch_type = op.patch.type
        basis = op.basis
        if not isinstance(patch_type, RotatedPlanarPatchType):
            return

        # We need to find the observable that is measured by ``op``.
        obs_ssa = _MeasureOpPattern.find_last_sobs_observable_on_patch(op)
        # Note that the ``obs_ssa`` obtained might live in an inner scope. If that is the case, we
        # are in an explicitly unsupported case for the moment, so do not change anything and return
        ssa_owner = obs_ssa.owner
        parent_block = ssa_owner if isinstance(ssa_owner, Block) else ssa_owner.parent_block()
        if parent_block != op.parent_block():
            return

        data_qubit_indices = get_data_qubits_indices(patch_type)
        num_qubits = patch_type.num_qubits
        # Patch -> Qubits
        qubit_types = [qcore.QubitType() for _ in range(num_qubits)]
        cast_from_patch_op = logasm.CastOp(op.patch, qcore.QubitRegType(num_qubits))
        unpack_op = qcore.UnpackQubitRegOp(
            cast(SSAValue[qcore.QubitRegType], cast_from_patch_op.out)
        )
        # Building the CircuitOp that will contain the gates
        circuit_body = Block(arg_types=qubit_types)
        # Measuring each qubit in ``data_qubit_indices`` in order. The fact that measurements are
        # ordered like ``data_qubit_indices`` is used later in this pattern.
        measure_op = qref.MeasureOp([op.basis], [circuit_body.args[i] for i in data_qubit_indices])
        circuit_body.add_op(measure_op)
        circuit_body.add_op(qstruct.YieldOp(*circuit_body.args, *measure_op.results))
        circuit_op = qstruct.CircuitOp(
            unpack_op.qubits, [*qubit_types, *measure_op.result_types], [circuit_body]
        )
        # Annotating flows on the generated ``qstruct.circuit`` operation. For the moment, we
        # annotate flows using the knowledge that the only operations that can come after a prepare
        # are ``meas_stab`` or ``measure`` (because no other operation is currently implemented),
        # and so we annotate exactly the right flows.
        # In the future, we will rework that part to make sure the flows annotated are generic
        # enough.
        stabilisers = global_stabilisers_for_memory_on_patch(patch_type, self.parity)
        circuit_op.attributes[stab.ConcreteFlowArrayAttr.KEY] = stab.ConcreteFlowArrayAttr(
            [
                stab.ConcreteFlowAttr(
                    "+",
                    [
                        # Using the fact that measurements are ordered like ``data_qubit_indices``.
                        num_qubits + data_qubit_indices.index(mi)
                        for mi in stabiliser.get_qubit_indices()
                    ],
                    stabiliser,
                    qcore.PauliStringAttr.identity(num_qubits),
                )
                for stabiliser in stabilisers
                if (
                    not stabiliser.is_identity()
                    and all(qstate.pauli_state == basis for qstate in stabiliser.qubit_states)
                )
            ]
        )
        # Mark the flows as droppable in case the do not perfectly align with other ops.
        circuit_op.attributes[stab.ConcreteFlowArrayAttr.DROPPABLE_FLOWS_KEY] = UnitAttr()
        # log_asm.measure does not return a patch, so no need for Qubits -> Patch.
        # log_asm.measure DOES return a corrected observable, so we include it here.
        corrected_obs_op = qec.GetCorrectedOp(obs_ssa)
        rewriter.replace_op(op, (cast_from_patch_op, unpack_op, circuit_op, corrected_obs_op))

    @staticmethod
    def find_last_sobs_observable_on_patch(op: logasm.MeasureOp) -> SSAValue:
        """Find the last ``sobs.observable`` representing the observable measured by ``op``.

        This method will only work when a single observable (i.e., single ``log_asm.measure`` is
        present in the whole circuit. It will have to be improved as soon as we will want to handle
        more than a single observable and measurement.

        With the single observable limitation, this method is able to find the observable by walking
        the operations of the IR to find the only operation that yields an SSA value of type
        ``sobs.observable`` that has no use and is in the same block as ``op``.

        Args:
            op: ``log_asm.measure`` operation that returns a corrected bit corresponding to the
                observable this method should find.

        Returns:
            The ``sobs.observable`` SSA value representing the last observable state before its
            measurement.

        Raises:
            CompilerPassCheckError: when the observable could not be found.
        """
        enclosing_block = op.parent_block()
        assert enclosing_block is not None, "'log_asm.measure' is outside of a Block."
        candidates: list[tuple[SSAValue, bool]] = []
        seen_measure = False
        for inner_op in enclosing_block.ops:
            seen_measure |= inner_op is op
            for res in inner_op.results:
                if isinstance(res.type, ObservableType) and not tuple(res.uses):
                    candidates.append((res, not seen_measure))
        if len(candidates) == 1 and candidates[0][1]:
            return candidates[0][0]
        error_msg = "Could not find a suitable 'sobs.locate_observable' operation."
        raise CompilerPassCheckError(error_msg)


@dataclass(frozen=True)
class TransversalOpToCircuit(ModulePass):
    """Lower circuit-like transversal ``log_asm`` operations to ``qstruct.circuit`` with flow
    annotations.

    This pass lowers all the "circuit-like" operations to their circuit equivalent. A "circuit-like"
    operation is defined as an operation that is trivial to lower down as a sequence of quantum
    gates. The following operations are considered "circuit-like" by this pass:

    - ``log_asm.prepare``
    - ``log_asm.measure``

    For the moment, ``log_asm.transversal`` is explicitly not supported by this pass.
    """

    name = "transversal-op-to-circuit"

    parity: bool = True

    @override
    def apply(self, ctx, op: ModuleOp) -> None:
        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [_PrepareOpPattern(self.parity), _MeasureOpPattern(self.parity)]
            )
        ).rewrite_module(op)
