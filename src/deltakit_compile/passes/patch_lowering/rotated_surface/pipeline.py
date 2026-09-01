# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Pass that runs the whole patch lowering pipeline for rotated surface code patches."""

from typing import Annotated

from typing_extensions import override
from xdsl.passes import ModulePass
from xdsl.transforms.canonicalize import CanonicalizePass

from deltakit_compile.passes.common.pipeline import (
    ConfigurablePipeline,
    Configuration,
    configurable_pass,
)
from deltakit_compile.passes.patch_lowering.rotated_surface._placement import (
    ObservablePlacementStrategy,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.annotate_flows_from_plaquettes import (
    AnnotateFlowsFromPlaquettes,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.backpropagate_observables import (
    BackpropagateObservables,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.located_observable_to_move import (
    LocatedObservableToMove,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.lower_patch_declaration import (
    LowerPatchDeclaration,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.patch_to_plaquettes import (
    PatchToPlaquettes,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.place_observables import (
    PlaceObservables,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.plaquette_to_circuit import (
    PlaquetteToCircuit,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.plaquette_to_qstruct import (
    PlaquetteToQstruct,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.schedule_plaquettes import (
    SchedulePlaquettes,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.transversal_op_to_circuit import (
    TransversalOpToCircuit,
)
from deltakit_compile.passes.sobs_to_qec import SobsObservableToQec
from deltakit_compile.utilities.config_yaml import EnumByName


class RotatedSurfacePatchLoweringPipelineConfig(Configuration, frozen=True):
    boundary_parity: bool = True
    r"""Temporary configuration until this can be set on a per-patch basis.

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

    """

    observable_placement_strategy: Annotated[ObservablePlacementStrategy, EnumByName()] = (
        ObservablePlacementStrategy.PRE_DEFINED_TOP_LEFT
    )
    """Configures where the observable should be placed on the patch."""


@configurable_pass
class RotatedSurfacePatchLoweringPipeline(
    ConfigurablePipeline[RotatedSurfacePatchLoweringPipelineConfig]
):
    """A pass which runs the patch lowering pipeline for rotated surface code patches."""

    name = "rotated-surface-patch-lowering-pipeline"

    boundary_parity: bool = True
    r"""Temporary configuration until this can be set on a per-patch basis.

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

    """

    observable_placement_strategy: ObservablePlacementStrategy = (
        ObservablePlacementStrategy.PRE_DEFINED_TOP_LEFT
    )
    """Configures where the observable should be placed on the patch."""

    @override
    def get_passes(self) -> tuple[ModulePass, ...]:
        return (
            # ComputeBoundaryParity(), << Not until boundary_parity can be set on a per-patch basis
            BackpropagateObservables(),
            LowerPatchDeclaration(self.boundary_parity),
            PlaceObservables(self.observable_placement_strategy),
            PatchToPlaquettes(self.boundary_parity),
            LocatedObservableToMove(),
            SchedulePlaquettes(),
            AnnotateFlowsFromPlaquettes(),
            PlaquetteToCircuit(),
            PlaquetteToQstruct(),
            TransversalOpToCircuit(self.boundary_parity),
            SobsObservableToQec(),
            CanonicalizePass(),
        )
