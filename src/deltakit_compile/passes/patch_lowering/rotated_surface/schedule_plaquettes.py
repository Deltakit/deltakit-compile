# This file contains information which is proprietary to Riverlane Limited
# ("Riverlane") and is Riverlane Confidential Information.
# (c) Copyright Riverlane 2025-2026. All rights reserved.

"""Set the ``stabs_measurement`` attribute on supported ``plaquette.plaquette`` operations.

Note that at the moment this pass relies on ``patch-to-plaquette`` to enforce some invariants:

- That pass will have annotated on all the generated plaquettes an instance of
  ``RotatedSurfaceCodePlaquetteShapeTypeAttr`` under the attribute key
  ``PLAQUETTE_SHAPE_TYPE_ATTRIBUTE_KEY``.
- That pass will have ordered the data qubits on which each ``plaquette.plaquette`` instance is
  applied using the Z-ordering depicted below.
- As an optimisation, the pass will have also annotated on each ``plaquette.round`` under the
  attribute key ``PLAQUETTE_Z_OBSERVABLE_IS_VERTICAL_ATTRIBUTE_KEY`` a boolean value to orient
  correctly the hook errors.

These invariants are required until we have a reliable way of tracking back qubits to where they
come from in order to obtain their coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from typing_extensions import override
from xdsl.dialects.builtin import BoolAttr, ModuleOp, NoneAttr
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.utils.hints import isa

from deltakit_compile.dialects.plaquette import (
    HasRoundAncestor,
    PlaquetteOp,
    RotatedSurfaceCodePlaquetteShapeTypeAttr,
    SynchronisedScheduleAttr,
)
from deltakit_compile.dialects.qcore import PauliAttr
from deltakit_compile.exceptions import CompilerPassCheckError
from deltakit_compile.passes.patch_lowering.rotated_surface._constants import (
    PLAQUETTE_SHAPE_TYPE_ATTRIBUTE_KEY,
    PLAQUETTE_Z_OBSERVABLE_IS_VERTICAL_ATTRIBUTE_KEY,
)


@dataclass
class _SynchronisedSchedulePattern(RewritePattern):
    """Set the ``stabs_measurement`` attribute on supported ``plaquette.plaquette`` operations to
    a synchronised schedule measurement method.

    Supported ``plaquette.plaquette`` operations check all the conditions below:

    - A single measurement bit is returned.
    - A single stabiliser is measured.
    - A single extra qubit is provided to measure the syndrome.
    - The stabiliser is measured 2, 3 or 4 data qubits.
    - The ``plaquette.plaquette`` operation has an attribute under the key
      :data:`PLAQUETTE_SHAPE_TYPE_ATTRIBUTE_KEY` which is a
      ``RotatedSurfaceCodePlaquetteShapeTypeAttr`` instance.
    - The ``RotatedSurfaceCodePlaquetteShapeTypeAttr`` instance under the key
      :data:`PLAQUETTE_SHAPE_TYPE_ATTRIBUTE_KEY` in the attribute dictionary of the matched
      operation should be valid for exactly the number of data-qubits used by the
      ``plaquette.plaquette`` operation.
    - The ``plaquette.round`` parent operation has an attribute under the key
      ``PLAQUETTE_Z_OBSERVABLE_IS_VERTICAL_ATTRIBUTE_KEY`` which is a ``BoolAttr`` instance.

    In addition, and for the moment, the ``plaquette.plaquette`` should be applied on data qubits
    that are sorted using the Z-ordering::

        0-----1
        |     |
        |     |
        2-----3
    """

    _HORIZONTAL_HOOK_SCHEDULE: ClassVar[tuple[int, int, int, int]] = (0, 1, 2, 3)
    _VERTICAL_HOOK_SCHEDULE: ClassVar[tuple[int, int, int, int]] = (0, 2, 1, 3)

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: PlaquetteOp, rewriter: PatternRewriter) -> None:
        parent_round_op = HasRoundAncestor.get_round_ancestor(op)
        assert parent_round_op is not None, "Should be verified by traits and constraints."
        if (
            len(op.measurements) != 1
            or len(op.stabilisers) != 1
            or len(op.ancilla_qubits) != 1
            or len(op.data_qubits) not in (2, 3, 4)
            or not isinstance(
                plaquette_shape := op.attributes.get(PLAQUETTE_SHAPE_TYPE_ATTRIBUTE_KEY),
                RotatedSurfaceCodePlaquetteShapeTypeAttr,
            )
            or len(op.data_qubits) != plaquette_shape.num_qubits
            or not isa(
                vertical_z := parent_round_op.attributes.get(
                    PLAQUETTE_Z_OBSERVABLE_IS_VERTICAL_ATTRIBUTE_KEY
                ),
                BoolAttr,
            )
        ):
            # This is an explicitly unsupported ``plaquette.plaquette`` instance.
            return
        stabiliser = op.stabilisers.data[0]
        paulis = {qubit_state.pauli_state for qubit_state in stabiliser.qubit_states.data}
        if len(paulis) != 1:
            # This should be supported by the pass eventually, but is not yet.
            msg = "Stabilisers with mixed Paulis are not yet implemented."
            raise NotImplementedError(msg)

        pauli = next(iter(paulis))
        # If the Z observable is vertical, we want Z plaquettes to have horizontal hook errors.
        schedule: tuple[int, ...] = (
            _SynchronisedSchedulePattern._HORIZONTAL_HOOK_SCHEDULE
            if (pauli == PauliAttr.Z()) == vertical_z.value.data
            else _SynchronisedSchedulePattern._VERTICAL_HOOK_SCHEDULE
        )
        # We need to adapt the schedule if the plaquette depending on its shape.
        # Note that the Z-ordering pre-condition set by this pass matches the way we defined
        # ``schedule``, so we do not have to permute its entries.
        schedule = tuple(schedule[i] for i in plaquette_shape.data.value)
        # Before writing on ``op.stabs_measurement``, let's check that it does not already contain
        # the information we need.
        if op.stabs_measurement is not None:
            should_overwrite: bool = False
            # Ignore any other stabiliser measurement method.
            if isinstance(op.stabs_measurement, SynchronisedScheduleAttr):
                # Check that the ``schedule`` we computed is compatible with the stabiliser
                # measurement method that was already set.
                assert len(schedule) == len(op.stabs_measurement.schedule), (
                    "Should be verified by constraints and by construction."
                )
                for i, (new, existing) in enumerate(
                    zip(schedule, op.stabs_measurement.schedule, strict=True)
                ):
                    if isinstance(existing, NoneAttr):
                        should_overwrite = True
                        continue
                    if new != existing.data:
                        msg = (
                            "Trying to override an existing SynchronisedScheduleAttr with the one "
                            "computed by the compiler but they disagree. Existing schedule was "
                            f"{existing.data} at entry {i} but the compiler computed {new}."
                        )
                        raise CompilerPassCheckError(msg)
            if not should_overwrite:
                return
        # If we reached that point, that mean that at least one of the stabilisers should be
        # overwritten.
        op.stabs_measurement = SynchronisedScheduleAttr(schedule)
        rewriter.notify_op_modified(op)


@dataclass(frozen=True)
class SchedulePlaquettes(ModulePass):
    """Set the ``stabs_measurement`` attribute on ``plaquette.plaquette`` operations.

    This pass currently implements only one stabiliser measurement strategy: synchronised schedule.
    This strategy will be independently annotated on matched ``plaquette.plaquette`` according to
    the shape of the plaquette and the desired orientation for the hook error. The base schedules
    used are ``(0, 1, 2, 3)`` for horizontal hook errors and ``(0, 2, 1, 3)`` for vertical ones.
    """

    name = "schedule-plaquettes"

    @override
    def apply(self, ctx, op: ModuleOp) -> None:
        PatternRewriteWalker(_SynchronisedSchedulePattern()).rewrite_region(op.body)
