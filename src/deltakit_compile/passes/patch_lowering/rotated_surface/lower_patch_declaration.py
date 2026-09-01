# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Implementation of the :class:`.BackpropagateObservables` pass.

This module implements a minimum viable pass to back-propagate observables through
``log_asm.meas_stab`` operations and declare them at ``log_asm.measure`` operations.

The implementation will have to be substantially reworked to handle programs beyond a simple
memory experiment.
"""

from dataclasses import dataclass

from typing_extensions import override
from xdsl.dialects.builtin import ModuleOp
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)

from deltakit_compile.dialects.logical_assembly import (
    CastOp,
    PatchDeclarationOp,
    RotatedPlanarPatchType,
)
from deltakit_compile.dialects.qcore import AllocQubitOp, PackQubitRegOp, QubitType
from deltakit_compile.shared.patch.rotated_planar._placement import patch_type_to_coordinates


@dataclass
class _PatchDeclarationPattern(RewritePattern):
    r"""Replace a ``log_asm.patch_dec`` operation by a ``qcore.alloc_qubit`` operation.

    This pattern will replace each ``log_asm.patch_dec`` operation by:
    1. a ``qcore.alloc_qubit`` operation and,
    2. a ``qcore.pack_qubit_reg`` operation to group the qubits as a register and,
    3. a ``log_asm.cast`` operation to keep the same output type as the original operation.

    Illustration of the effect of the ``boundary_parity`` parameter when it is ``True``::

              .
             / \
            .---.---.\
            |   |   | .
           /.---.---./
          . |   |   |
           \.---.---.
                 \ /
                  .

    and when it is ``False``::

                  .
                 / \
           /.---.---.
          . |   |   |
           \.---.---.\
            |   |   | .
            .---.---./
             \ /
              .


    Illustration of the effect of the ``boundary_parity`` on patches that have a width of ``1`` when
    it is ``True``::

          .\
          | .
         /./
        . |
         \.

    and when it is ``False``::

         /.
        . |
         \.\
          | .
          ./


    Attributes:
        parity: if ``True``, the left-most weight-2 stabiliser on the top boundary is
            populated. Else, it is not populated (and so its direct right neighbour is). This is a
            temporary parameter until that information is encoded on the patch type.
            When the width (X dimension) of the patch is exactly ``1``, ``True`` means that the
            top weight-2 stabiliser on the right boundary is included in the patch. Patches with a
            height of ``1`` follow the general rule.
    """

    parity: bool = True

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: PatchDeclarationOp, rewriter: PatternRewriter) -> None:
        patch_type = op.res.type
        if not isinstance(patch_type, RotatedPlanarPatchType):
            return
        coordinates = patch_type_to_coordinates(patch_type, self.parity)
        qubit_alloc_op = AllocQubitOp([QubitType() for _ in range(len(coordinates))], coordinates)
        pack_op = PackQubitRegOp(qubit_alloc_op.results)
        cast_op = CastOp(pack_op.reg, patch_type)
        rewriter.replace_op(op, [qubit_alloc_op, pack_op, cast_op])


@dataclass(frozen=True)
class LowerPatchDeclaration(ModulePass):
    """Replace ``log_asm.patch_dec`` operations to ``qcore.qubit_alloc`` and
    ``builtin.unrealized_conversion_cast`` operations."""

    name = "lower-patch-declaration"

    parity: bool = True

    @override
    def apply(self, ctx, op: ModuleOp) -> None:
        PatternRewriteWalker(_PatchDeclarationPattern(self.parity)).rewrite_region(op.body)
