# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Lower ``log_asm`` rotated surface code patches to ``plaquette.plaquette``.

At the moment, this pass will also annotate attributes on the plaquettes and respect some
invariants in order to facilitate the implementation of ``schedule-plaquettes``. The following
invariants are currently enforced, but will eventually be removed:

- This pass will annotate on all the generated plaquettes an instance of
  ``RotatedSurfaceCodePlaquetteShapeTypeAttr`` under the attribute key
  ``PLAQUETTE_SHAPE_TYPE_ATTRIBUTE_KEY``.
- This pass will order the data qubits on which each ``plaquette.plaquette`` instance is applied
  using the Z-ordering depicted below.
- As an optimisation, this pass will also annotate on each ``plaquette.round`` under the attribute
  key ``PLAQUETTE_Z_OBSERVABLE_IS_VERTICAL_ATTRIBUTE_KEY`` a boolean value to orient correctly the
  hook errors.

The Z-ordering of data qubits is::

    0-----1
    |     |
    |     |
    2-----3

So the plaquette::

    0
    | \
    |  q
    | /
    2

will correspond to an operation like::

    plaquette.plaquette<[Z0 Z1 : 2]> on (%0, %2) using (%q) -> i1

The first 2 invariants above will be removed when we will have a way to track back the origin of
qubits and get their coordinates from that origin.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import repeat
from typing import ClassVar, cast

from typing_extensions import override
from xdsl.dialects.builtin import BoolAttr, ModuleOp, NoneAttr, i1
from xdsl.ir import Block, Operation, SSAValue
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    GreedyRewritePatternApplier,
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)

from deltakit_compile.dialects.logical_assembly import (
    CastOp,
    MeasStabOp,
    MeasureOp,
    OrientationEnum,
    PrepareOp,
    RotatedPlanarPatchType,
)
from deltakit_compile.dialects.plaquette import (
    PlaquetteOp,
    RotatedSurfaceCodePlaquetteShapeTypeAttr,
    RotatedSurfaceCodePlaquetteShapeTypeEnum,
    RoundOp,
)
from deltakit_compile.dialects.plaquette import YieldOp as PlaquetteYieldOp
from deltakit_compile.dialects.qcore import (
    PackQubitRegOp,
    PauliStringAttr,
    QubitRegType,
    QubitType,
    UnpackQubitRegOp,
)
from deltakit_compile.dialects.qstruct import CircuitOp, RepeatOp, YieldOp
from deltakit_compile.exceptions import PatchLoweringError
from deltakit_compile.passes.patch_lowering.rotated_surface._constants import (
    PLAQUETTE_SHAPE_TYPE_ATTRIBUTE_KEY,
    PLAQUETTE_Z_OBSERVABLE_IS_VERTICAL_ATTRIBUTE_KEY,
)
from deltakit_compile.shared.patch.rotated_planar._placement import patch_type_to_coordinates
from deltakit_compile.shared.patch.rotated_planar._stabilisers import (
    local_stabilisers_for_memory_on_patch,
)


@dataclass
class _MeasStabiliserPattern(RewritePattern):
    r"""Replace a ``log_asm.meas_stab`` operation by a ``plaquette.round`` operation containing
    ``plaquette.plaquette``.

    Note that this pass removes ``log_asm.meas_stab<0>`` operations, as they correspond to no-ops.

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

    _Z_SHAPE_OFFSET: ClassVar[tuple[tuple[float, float], ...]] = ((0, 1), (1, 1), (0, 0), (1, 0))
    """Offsets to add to the origin (bottom-left qubit) of a plaquette to get all the data-qubits,
    following a Z order.

    The z order is illustrated below::

        0----1
        |    |
        |    |
        2----3

    Note that the numbers above are also the order in which data-qubits are indexed. When documented
    as such (e.g. :meth:`._build_block_with_plaquette`), ``0`` means "the top-left data-qubit
    obtained by adding ``_Z_SHAPE_OFFSET[0]`` to the origin of the plaquette".
    """

    _ALL_DATA_QUBIT_INDICES: ClassVar[tuple[int, int, int, int]] = (0, 1, 2, 3)
    _TOP_DATA_QUBIT_INDICES: ClassVar[tuple[int, int]] = (0, 1)
    _BOTTOM_DATA_QUBIT_INDICES: ClassVar[tuple[int, int]] = (2, 3)
    _LEFT_DATA_QUBIT_INDICES: ClassVar[tuple[int, int]] = (0, 2)
    _RIGHT_DATA_QUBIT_INDICES: ClassVar[tuple[int, int]] = (1, 3)

    @staticmethod
    def _build_block_with_plaquette(
        stabiliser: PauliStringAttr,
        num_qubits: int,
        origin: tuple[float, float],
        data_qubit_indices: tuple[int, ...],
        coordinates: Sequence[tuple[float, float]],
    ) -> Block:
        """Build a block containing a ``plaquette.plaquette`` operation and a ``plaquette.yield``
        operation.

        Arguments:
            stabiliser: stabiliser that should be measured by the ``plaquette.plaquette`` in the
                returned block.
            num_qubits: total number of qubits composing the patch.
            origin: origin of the plaquette to represent as a ``plaquette.plaquette` operation.
            data_qubit_indices: indices of data-qubits that are used by the plaquette to build.
                Indices follow a Z pattern on the plaquette. See documentation of
                :data:`._Z_SHAPE_OFFSET` for a diagram.
            coordinates: coordinates of all the qubits composing the patch. Used as a map from
                coordinates to qubit indices by calling ``list.index``.

        Returns:
            A ``Block`` instance containing exactly 2 operations:
            - a ``plaquette.plaquette`` operation and,
            - a ``qstruct.yield`` operation.
        """
        block = Block(arg_types=list(repeat(QubitType(), num_qubits)))
        # Computing qubit coordinates
        if max(data_qubit_indices) >= len(_MeasStabiliserPattern._Z_SHAPE_OFFSET):
            msg = (
                f"Cannot use data qubit with index {max(data_qubit_indices)}. The maximum "
                f"supported index is {len(_MeasStabiliserPattern._Z_SHAPE_OFFSET) - 1}."
            )
            raise PatchLoweringError(msg)
        offsets = [_MeasStabiliserPattern._Z_SHAPE_OFFSET[i] for i in data_qubit_indices]
        data_qubits_coords = [(origin[0] + a, origin[1] + b) for a, b in offsets]
        ancilla_qubit_coords = (origin[0] + 0.5, origin[1] + 0.5)
        # Computing the plaquette shape type
        plaquette_shape: RotatedSurfaceCodePlaquetteShapeTypeEnum
        match sorted(data_qubit_indices):
            case [0, 1]:
                plaquette_shape = RotatedSurfaceCodePlaquetteShapeTypeEnum.BOTTOM
            case [0, 2]:
                plaquette_shape = RotatedSurfaceCodePlaquetteShapeTypeEnum.RIGHT
            case [1, 3]:
                plaquette_shape = RotatedSurfaceCodePlaquetteShapeTypeEnum.LEFT
            case [2, 3]:
                plaquette_shape = RotatedSurfaceCodePlaquetteShapeTypeEnum.TOP
            case [0, 1, 2, 3]:
                plaquette_shape = RotatedSurfaceCodePlaquetteShapeTypeEnum.SQUARE
            case dqi:
                msg = f"Unsupported plaquette applied on data qubits {dqi}."
                raise NotImplementedError(msg)
        # Recovering the qubits SSAs
        data_qubit_ssas = [block.args[coordinates.index(coords)] for coords in data_qubits_coords]
        ancilla_qubit_ssa = block.args[coordinates.index(ancilla_qubit_coords)]
        plaquette_op = PlaquetteOp(data_qubit_ssas, stabiliser, 1, [ancilla_qubit_ssa])
        plaquette_op.attributes[PLAQUETTE_SHAPE_TYPE_ATTRIBUTE_KEY] = (
            RotatedSurfaceCodePlaquetteShapeTypeAttr(plaquette_shape)
        )
        block.add_op(plaquette_op)
        block.add_op(PlaquetteYieldOp(*plaquette_op.measurements))
        return block

    @staticmethod
    def _build_plaquette_blocks(patch_type: RotatedPlanarPatchType, parity: bool) -> list[Block]:
        r"""Return all the ``plaquette.plaquette`` blocks required to implement the provided patch
        type.

        Implementation note: this function is using the ``origin`` of each plaquette. The origin is
        defined as the bottom-left qubit of the enclosing square plaquette, even for weight-2
        plaquettes that do not use that qubit. For example::

                .
               /|
              . |
               \|
            o   .

        where ``o`` is the origin and ``.`` represent used qubits.
        This is the reason why the origin is computed with ``- 0.5`` instead of the probably
        expected (but wrong) ``+ 0.5``. See for example::

                  .
                 / \
                .---.---.\
                |   |   | .
               /.---.---./
              . |   |   |
            x  \.---.---.
                     \ /
              O       .

            o       x
        where both ``x``s show the origin of the left/bottom boundary plaquettes, ``O`` shows the
        patch origin=``(offx, offy)`` and ``o`` shows the origin of the bottom-left-most plaquette
        (that is on the corner, and so nearly always empty).

        Args:
            patch_type: patch to generate stabilisers for.
            parity: position of the left-most stabiliser of the top boundary.

        Returns:
            A list of ``plaquette.plaquette` operations.
        """
        # Pre-conditions
        assert patch_type.placement_data is not None, "Should be ensured by caller"
        # Pre-computing a few constant quantities that will be re-used.
        num_qubits = patch_type.num_qubits
        offx, offy = patch_type.placement_data
        width, height = patch_type.size_data
        coordinates = patch_type_to_coordinates(patch_type, parity)
        stabilisers = local_stabilisers_for_memory_on_patch(patch_type, parity)
        blocks: list[Block] = []

        # Building the bulk plaquettes
        for y, line in enumerate(stabilisers[1:-1]):
            for x, stab in enumerate(line[1:-1]):
                if stab.is_identity():
                    continue
                # Offset x and y by one because the enumerates above do not include the first
                # plaquette (and it should be accounted for to compute the origin).
                origin = (x + 1 + offx - 0.5, y + 1 + offy - 0.5)
                block = _MeasStabiliserPattern._build_block_with_plaquette(
                    stab,
                    num_qubits,
                    origin,
                    _MeasStabiliserPattern._ALL_DATA_QUBIT_INDICES,
                    coordinates,
                )
                blocks.append(block)

        # Building the top boundary plaquettes
        for x in range(width + 1):
            if (stab := stabilisers[-1][x]).is_identity():
                continue
            origin = (x + offx - 0.5, height + offy - 0.5)
            block = _MeasStabiliserPattern._build_block_with_plaquette(
                stab,
                num_qubits,
                origin,
                _MeasStabiliserPattern._BOTTOM_DATA_QUBIT_INDICES,
                coordinates,
            )
            blocks.append(block)

        # Building the bottom boundary plaquettes
        for x in range(width + 1):
            if (stab := stabilisers[0][x]).is_identity():
                continue
            origin = (x + offx - 0.5, offy - 0.5)
            block = _MeasStabiliserPattern._build_block_with_plaquette(
                stab,
                num_qubits,
                origin,
                _MeasStabiliserPattern._TOP_DATA_QUBIT_INDICES,
                coordinates,
            )
            blocks.append(block)

        # Building the left boundary plaquettes
        for y in range(height + 1):
            if (stab := stabilisers[y][0]).is_identity():
                continue
            origin = (offx - 0.5, y + offy - 0.5)
            block = _MeasStabiliserPattern._build_block_with_plaquette(
                stab,
                num_qubits,
                origin,
                _MeasStabiliserPattern._RIGHT_DATA_QUBIT_INDICES,
                coordinates,
            )
            blocks.append(block)

        # Building the right boundary plaquettes
        for y in range(height + 1):
            if (stab := stabilisers[y][-1]).is_identity():
                continue
            origin = (width + offx - 0.5, y + offy - 0.5)
            block = _MeasStabiliserPattern._build_block_with_plaquette(
                stab,
                num_qubits,
                origin,
                _MeasStabiliserPattern._LEFT_DATA_QUBIT_INDICES,
                coordinates,
            )
            blocks.append(block)

        return blocks

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: MeasStabOp, rewriter: PatternRewriter) -> None:
        patch_type = op.patch.type
        if not isinstance(patch_type, RotatedPlanarPatchType):
            return
        num_rounds = op.min_rounds.data
        if num_rounds == 0:
            # `log_asm.meas_stab<0>` is essentially a no-op, so we remove it here.
            rewriter.replace_op(op, (), (op.patch,))
            return
        if isinstance(patch_type.placement, NoneAttr):
            msg = "Patches without placement data are not supported."
            raise PatchLoweringError(msg)
        # Building the individual plaquette.plaquette operations
        num_qubits = patch_type.num_qubits
        qubit_types = tuple(repeat(QubitType(), num_qubits))
        plaquette_blocks = _MeasStabiliserPattern._build_plaquette_blocks(patch_type, self.parity)
        num_measurements = len(plaquette_blocks)

        # Wrapping them in a plaquette.round and building the block for the wrapping
        # qstruct.circuit.
        circuit_block = Block(arg_types=qubit_types)
        round_op = RoundOp(circuit_block.args, plaquette_blocks, num_measurements)
        round_op.attributes[PLAQUETTE_Z_OBSERVABLE_IS_VERTICAL_ATTRIBUTE_KEY] = BoolAttr.from_bool(
            patch_type.placement.orientation.data == OrientationEnum.VERTICAL_Z
        )
        circuit_block.add_op(round_op)
        circuit_block.add_op(YieldOp(*circuit_block.args, *round_op.measurements))

        # Wrapping the plaquette.round in a qstruct.circuit and building the block for the wrapping
        # qstruct.repeat.
        repeat_block = Block(arg_types=qubit_types)
        circuit_op = CircuitOp(
            repeat_block.args, (*qubit_types, *list(repeat(i1, num_measurements))), [circuit_block]
        )
        repeat_block.add_op(circuit_op)
        repeat_block.add_op(YieldOp(*circuit_op.results[:num_qubits]))

        # Wrapping the qstruct.circuit in a qstruct.repeat operation, unpacking and packing back
        # the patch on which the original ``log_asm.meas_stab`` operation was applied on.
        cast_to_qreg_op = CastOp(op.patch, QubitRegType(num_qubits))
        unpack_op = UnpackQubitRegOp(cast(SSAValue[QubitRegType], cast_to_qreg_op.out))
        repeat_op = RepeatOp(num_rounds, [repeat_block], iter_args=unpack_op.qubits)
        pack_op = PackQubitRegOp(repeat_op.res)
        cast_to_patch_op = CastOp(pack_op.reg, patch_type)

        # Replacing the operation
        rewriter.replace_op(op, [cast_to_qreg_op, unpack_op, repeat_op, pack_op, cast_to_patch_op])


@dataclass(frozen=True)
class _UnsupportedOpPattern(RewritePattern):
    """Raise a ``NotImplementedError`` on ``log_asm`` operations not matched by other patterns.

    This pattern will raise on any ``log_asm`` operation encountered. It can be used as the last
    pattern in a ``GreedyRewritePatternApplier`` to catch any operation that is not yet implemented
    and avoid silent failure.
    """

    ignored_operations: ClassVar[tuple[type[Operation], ...]] = (PrepareOp, MeasureOp, CastOp)
    """Operations ignored because they are handled by ``transversal-op-to-circuit`` or should
    eventually be canonicalised out (``log_asm.cast``)."""
    supported_operations: ClassVar[tuple[type[Operation], ...]] = (MeasStabOp,)
    """Operations supported by this pass."""

    all_ignored_operations: ClassVar[tuple[type[Operation], ...]] = (
        ignored_operations + supported_operations
    )

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: Operation, rewriter: PatternRewriter) -> None:
        if op.dialect_name() == "log_asm" and not isinstance(op, self.all_ignored_operations):
            msg = f"{type(op).__name__} is not yet supported by 'patch-to-plaquette'."
            raise NotImplementedError(msg)


@dataclass(frozen=True)
class PatchToPlaquettes(ModulePass):
    """Replace ``log_asm`` operations with ``plaquette`` operations."""

    name = "patch-to-plaquettes"

    parity: bool = True

    @override
    def apply(self, ctx, op: ModuleOp) -> None:
        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [_MeasStabiliserPattern(self.parity), _UnsupportedOpPattern()]
            )
        ).rewrite_region(op.body)
