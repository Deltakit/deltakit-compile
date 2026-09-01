# This file contains information which is proprietary to Riverlane Limited
# ("Riverlane") and is Riverlane Confidential Information.
# (c) Copyright Riverlane 2025-2026. All rights reserved.

"""Implementation of the :class:`.PlaceObservables` pass for rotated surface patches.

This module implements a minimum viable pass to place unplaced observables on rotated surface code
patches. It translates all ``sobs.dec_unplaced_observable`` and ``sobs.locate_unplaced_observable``
applied to rotated surface code patches to ``sobs.dec_observable`` and ``sobs.locate_observable``
respectively.
"""

from dataclasses import dataclass
from typing import cast

from typing_extensions import override
from xdsl.dialects.builtin import ModuleOp, UnrealizedConversionCastOp
from xdsl.ir import Block, Operation, Region, SSAValue
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    GreedyRewritePatternApplier,
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)

from deltakit_compile.dialects import logical_assembly as logasm
from deltakit_compile.dialects import qcore, qstruct, sobs
from deltakit_compile.passes.patch_lowering.rotated_surface._placement import (
    BaseObservablePlacementStrategy,
    ObservablePlacementStrategy,
)
from deltakit_compile.utilities.traverse_from_ssa import find_backward_ssas


@dataclass
class _LocateUnplacedObservableOp(RewritePattern):
    """Translates a ``sobs.locate_unplaced_observable`` into a ``sobs.locate_observable``.

    This pattern handles ``sobs.locate_unplaced_observable`` operations appearing just after a
    ``sobs.dec_unplaced_observable`` slightly differently than the other
    ``sobs.locate_unplaced_observable`` operations:

    - the first ``sobs.locate_unplaced_observable`` operation after a
      ``sobs.dec_unplaced_observable`` will be translated to a ``sobs.dec_observable``,
    - all the other ``sobs.locate_unplaced_observable`` operations will be translated to
      ``sobs.locate_observable`` operations.

    This is to ensure that the ``sobs.dec_observable`` is applied on qubits that already have a well
    defined quantum state and avoid semantically unclear operations (e.g., what should happen if
    the qubits in the ``sobs.dec_observable`` operation are ``reset`` just after declaration?).
    """

    strategy: BaseObservablePlacementStrategy

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(
        self, op: sobs.LocateUnplacedObservableOp, rewriter: PatternRewriter
    ) -> None:
        if len(op.patches) != 1:
            msg = (
                "Only one patch is currently supported in "
                f"{sobs.LocateUnplacedObservableOp.__name__}."
            )
            raise NotImplementedError(msg)
        input_patch = op.patches[0]
        patch_type = input_patch.type
        if not isinstance(patch_type, logasm.RotatedPlanarPatchType):
            msg = f"Patches of type {type(patch_type).__name__} are not currently supported."
            raise NotImplementedError(msg)
        # Preparing data/operations that will be used in all cases
        qreg_type = qcore.QubitRegType(patch_type.num_qubits)
        cast_to_reg_op = logasm.CastOp(input_patch, qreg_type)

        # Indices for the support qubits
        qubit_indices = self.strategy.place_on_patch(patch_type, op.bases.data[0])
        # Handle differently the first ``sobs.locate_uplaced_observable`` operation of the chain
        # to replace it with a ``sobs.declare_observable`` instead.
        obs_ops: tuple[Operation, ...]
        new_observable: SSAValue
        new_qreg: SSAValue
        if any(
            isinstance(potential_origin.owner, sobs.DecUnplacedObservableOp)
            for potential_origin in find_backward_ssas(op.obs)
        ):
            circuit_body = Block(arg_types=(qreg_type,))
            unpack_op = qcore.UnpackQubitRegOp(
                cast(SSAValue[qcore.QubitRegType], circuit_body.args[0])
            )
            circuit_body.add_op(unpack_op)
            dec_obs_op = sobs.DecObservableOp([unpack_op.qubits[idx] for idx in qubit_indices])
            circuit_body.add_op(dec_obs_op)
            circuit_body.add_op(qstruct.YieldOp(dec_obs_op.result, *circuit_body.args))
            circuit_op = qstruct.CircuitOp(
                (cast_to_reg_op.out,), (sobs.ObservableType(), qreg_type), Region(circuit_body)
            )
            obs_ops = (circuit_op,)
            new_observable, new_qreg = circuit_op.res
        else:
            from_unplaced_observable_op = UnrealizedConversionCastOp.get(
                [op.obs], [sobs.ObservableType()]
            )
            circuit_body = Block(arg_types=(sobs.ObservableType(), qreg_type))
            unpack_op = qcore.UnpackQubitRegOp(
                cast(SSAValue[qcore.QubitRegType], circuit_body.args[1])
            )
            circuit_body.add_op(unpack_op)
            locate_obs_op = sobs.LocateObservableOp(
                circuit_body.args[0], [unpack_op.qubits[idx] for idx in qubit_indices]
            )
            circuit_body.add_op(locate_obs_op)
            circuit_body.add_op(qstruct.YieldOp(locate_obs_op.result, *circuit_body.args[1:]))
            circuit_op = qstruct.CircuitOp(
                (from_unplaced_observable_op.results[0], cast_to_reg_op.out),
                (sobs.ObservableType(), qreg_type),
                Region(circuit_body),
            )
            obs_ops = (from_unplaced_observable_op, circuit_op)
            new_observable, new_qreg = circuit_op.res

        cast_to_patch_op = logasm.CastOp(new_qreg, patch_type)
        to_unplaced_observable_op, new_result = UnrealizedConversionCastOp.cast_one(
            new_observable, sobs.UnplacedObservableType()
        )
        rewriter.replace_op(
            op,
            [
                cast_to_reg_op,
                *obs_ops,
                cast_to_patch_op,
                to_unplaced_observable_op,
            ],
            (new_result,),
        )

        # Replace all other uses of the patch with the new patch
        rewriter.replace_uses_with_if(
            input_patch, cast_to_patch_op.out, lambda use: use.operation != cast_to_reg_op
        )


@dataclass(frozen=True)
class PlaceObservables(ModulePass):
    """Place observables on specific qubits.

    This pass translates ``sobs.dec_unplaced_observable`` and ``sobs.locate_unplaced_observable``
    operations into ``sobs.dec_observable`` and ``sobs.locate_observable``.
    """

    name = "place-observables"

    strategy: ObservablePlacementStrategy = ObservablePlacementStrategy.PRE_DEFINED_TOP_LEFT

    @override
    def apply(self, ctx, op: ModuleOp) -> None:
        PatternRewriteWalker(
            GreedyRewritePatternApplier([_LocateUnplacedObservableOp(self.strategy.value)])
        ).rewrite_module(op)
