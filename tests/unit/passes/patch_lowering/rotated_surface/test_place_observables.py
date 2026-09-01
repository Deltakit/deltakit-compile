"""Tests for the PlaceObservables pass for rotated surface patches."""

from typing import Final

import pytest
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.pattern_rewriter import GreedyRewritePatternApplier, PatternRewriteWalker
from xdsl.transforms.dead_code_elimination import dce

from deltakit_compile.dialects.sobs import (
    DecObservableOp,
    DecUnplacedObservableOp,
    LocateObservableOp,
    LocateUnplacedObservableOp,
)
from deltakit_compile.passes.patch_lowering.rotated_surface import ObservablePlacementStrategy
from deltakit_compile.passes.patch_lowering.rotated_surface._placement import (
    PreDefinedObservablePlacementStrategy,
)
from deltakit_compile.passes.patch_lowering.rotated_surface.place_observables import (
    PlaceObservables,
    _LocateUnplacedObservableOp,
)
from tests.unit.conftest import parse_ir

# Patch type used across tests
_PATCH_3x3_H_Z: Final[str] = "!log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=h_z>"


@pytest.fixture
def one_locate_ir() -> str:
    return f"""
    builtin.module {{
        %obs_0 = sobs.dec_unplaced_observable -> !sobs.unplaced_observable
        %p0 = log_asm.patch_dec -> {_PATCH_3x3_H_Z}
        %p0_1 = log_asm.prepare<Z> (%p0 : {_PATCH_3x3_H_Z})
        %obs_1 = sobs.locate_unplaced_observable<Z>(%obs_0) on (%p0_1) -> !sobs.unplaced_observable
    }}
    """


@pytest.fixture
def three_locates_ir() -> str:
    return f"""
    builtin.module {{
        %obs_0 = sobs.dec_unplaced_observable -> !sobs.unplaced_observable
        %p0 = log_asm.patch_dec -> {_PATCH_3x3_H_Z}
        %p0_1 = log_asm.prepare<Z> (%p0 : {_PATCH_3x3_H_Z})
        %obs_1 = sobs.locate_unplaced_observable<Z>(%obs_0) on (%p0_1) -> !sobs.unplaced_observable
        %p0_2 = log_asm.meas_stab<3> (%p0_1 : {_PATCH_3x3_H_Z})
        %obs_2 = sobs.locate_unplaced_observable<Z>(%obs_1) on (%p0_2) -> !sobs.unplaced_observable
        %p0_3 = log_asm.meas_stab<3> (%p0_2 : {_PATCH_3x3_H_Z})
        %obs_3 = sobs.locate_unplaced_observable<Z>(%obs_2) on (%p0_3) -> !sobs.unplaced_observable
    }}
    """


class TestLocateUnplacedObservablePattern:
    """Tests for _LocateUnplacedObservableOp which translates ``sobs.locate_unplaced_observable``
    ops."""

    def _apply_patterns(self, module: ModuleOp, strategy=None) -> None:
        strategy = strategy or PreDefinedObservablePlacementStrategy()
        PatternRewriteWalker(
            GreedyRewritePatternApplier([_LocateUnplacedObservableOp(strategy)])
        ).rewrite_region(module.body)

    def test_first_locate_becomes_dec_observable(
        self, xdsl_context: Context, one_locate_ir: str
    ) -> None:
        """Check that the first ``sobs.locate_unplaced_observable`` after a declaration is rewritten
        to a ``sobs.dec_observable``."""
        module = parse_ir(one_locate_ir, xdsl_context)
        self._apply_patterns(module)
        module.verify()

        dec_obs_ops = [op for op in module.walk() if isinstance(op, DecObservableOp)]
        assert len(dec_obs_ops) == 1

    def test_first_locate_removes_locate_unplaced(
        self, xdsl_context: Context, one_locate_ir: str
    ) -> None:
        """After rewriting, no ``sobs.locate_unplaced_observable`` ops remain."""
        module = parse_ir(one_locate_ir, xdsl_context)
        self._apply_patterns(module)
        module.verify()

        locate_unplaced_ops = [
            op for op in module.walk() if isinstance(op, LocateUnplacedObservableOp)
        ]
        assert locate_unplaced_ops == []

    def test_subsequent_locates_become_locate_observable(
        self, xdsl_context: Context, three_locates_ir: str
    ) -> None:
        """All ``sobs.locate_unplaced_observable`` ops after the first become
        ``sobs.locate_observable``."""
        module = parse_ir(three_locates_ir, xdsl_context)
        self._apply_patterns(module)
        module.verify()

        locate_obs_ops = [op for op in module.walk() if isinstance(op, LocateObservableOp)]
        assert len(locate_obs_ops) == 2

    def test_three_locates_produce_one_dec_observable(
        self, xdsl_context: Context, three_locates_ir: str
    ) -> None:
        """Only the first ``sobs.locate_unplaced_observable`` produces a ``sobs.dec_observable``."""
        module = parse_ir(three_locates_ir, xdsl_context)
        self._apply_patterns(module)
        module.verify()

        dec_obs_ops = [op for op in module.walk() if isinstance(op, DecObservableOp)]
        assert len(dec_obs_ops) == 1

    def test_raises_for_multiple_patches(self, xdsl_context: Context) -> None:
        """Pattern raises NotImplementedError when ``sobs.locate_unplaced_observable`` has more than
        a single patch."""
        ir = f"""
        builtin.module {{
            %obs_0 = sobs.dec_unplaced_observable -> !sobs.unplaced_observable
            %p0 = log_asm.patch_dec -> {_PATCH_3x3_H_Z}
            %p1 = log_asm.patch_dec -> {_PATCH_3x3_H_Z}
            %p0_1 = log_asm.prepare<Z> (%p0 : {_PATCH_3x3_H_Z})
            %p1_1 = log_asm.prepare<Z> (%p1 : {_PATCH_3x3_H_Z})
            %obs_1 = sobs.locate_unplaced_observable<ZZ>(%obs_0) on (%p0_1, %p1_1)
                -> !sobs.unplaced_observable
        }}
        """
        module = parse_ir(ir, xdsl_context)
        strategy = PreDefinedObservablePlacementStrategy()

        with pytest.raises(NotImplementedError, match="Only one patch is currently supported"):
            PatternRewriteWalker(_LocateUnplacedObservableOp(strategy)).rewrite_module(module)


class TestPlaceObservablesPass:
    def test_pass_removes_dec_only(self, xdsl_context: Context) -> None:
        """Pass removes a standalone ``sobs.dec_unplaced_observable``."""
        ir = """
        builtin.module {
            %obs = sobs.dec_unplaced_observable -> !sobs.unplaced_observable
        }
        """
        module = parse_ir(ir, xdsl_context)
        PlaceObservables().apply(xdsl_context, module)
        module.verify()

        dec_ops = [op for op in module.walk() if isinstance(op, DecUnplacedObservableOp)]
        assert dec_ops == []

    def test_pass_removes_all_unplaced_ops(
        self, xdsl_context: Context, three_locates_ir: str
    ) -> None:
        """After the pass, no unplaced observable ops remain."""
        module = parse_ir(three_locates_ir, xdsl_context)
        PlaceObservables().apply(xdsl_context, module)
        dce(module)  # Explicit call to DCE to remove the declaration operations
        module.verify()

        dec_unplaced = [op for op in module.walk() if isinstance(op, DecUnplacedObservableOp)]
        locate_unplaced = [op for op in module.walk() if isinstance(op, LocateUnplacedObservableOp)]
        assert dec_unplaced == []
        assert locate_unplaced == []

    def test_pass_one_locate_produces_dec_observable(
        self, xdsl_context: Context, one_locate_ir: str
    ) -> None:
        """Pass with one locate op produces a dec_observable operation."""
        module = parse_ir(one_locate_ir, xdsl_context)
        PlaceObservables().apply(xdsl_context, module)
        dce(module)  # Explicit call to DCE to remove the declaration operations
        module.verify()

        dec_obs_ops = [op for op in module.walk() if isinstance(op, DecObservableOp)]
        assert len(dec_obs_ops) == 1

    def test_pass_three_locates_produces_correct_op_counts(
        self, xdsl_context: Context, three_locates_ir: str
    ) -> None:
        """Pass with three locate ops produces one dec_observable and two locate_observable."""
        module = parse_ir(three_locates_ir, xdsl_context)
        PlaceObservables().apply(xdsl_context, module)
        module.verify()

        dec_obs_ops = [op for op in module.walk() if isinstance(op, DecObservableOp)]
        locate_obs_ops = [op for op in module.walk() if isinstance(op, LocateObservableOp)]
        assert len(dec_obs_ops) == 1
        assert len(locate_obs_ops) == 2

    def test_pass_accepts_custom_strategy(self, xdsl_context: Context, one_locate_ir: str) -> None:
        """Pass accepts and uses a custom ObservablePlacementStrategy."""
        strategy = ObservablePlacementStrategy.PRE_DEFINED_CENTER_RIGHT
        module = parse_ir(one_locate_ir, xdsl_context)
        PlaceObservables(strategy=strategy).apply(xdsl_context, module)
        module.verify()

        dec_obs_ops = [op for op in module.walk() if isinstance(op, DecObservableOp)]
        assert len(dec_obs_ops) == 1

    def test_pass_raises_on_invalid_patch_type(
        self, xdsl_context: Context, one_locate_ir: str
    ) -> None:
        """Pass accepts and uses a custom ObservablePlacementStrategy."""
        ir = """
        builtin.module {
            %obs_0 = sobs.dec_unplaced_observable -> !sobs.unplaced_observable
            %p0 = log_asm.patch_dec ->
                !log_asm.patch.unrot_planar<size=(3, 3), location=(0, 0), orient=h_z>
            %p0_1 = log_asm.prepare<Z>
                (%p0 : !log_asm.patch.unrot_planar<size=(3, 3), location=(0, 0), orient=h_z>)
            %obs_1 = sobs.locate_unplaced_observable<Z>(%obs_0) on (%p0_1)
                -> !sobs.unplaced_observable
        }
        """
        module = parse_ir(ir, xdsl_context)
        msg = "Patches of type UnrotatedPlanarPatchType are not currently supported"
        with pytest.raises(NotImplementedError, match=msg):
            PlaceObservables().apply(xdsl_context, module)

    def test_pass_valid_module_after_multiple_observables(self, xdsl_context: Context) -> None:
        """Pass produces a valid module when multiple independent observables are declared."""
        ir = f"""
        builtin.module {{
            %obs_a = sobs.dec_unplaced_observable -> !sobs.unplaced_observable
            %p_a = log_asm.patch_dec -> {_PATCH_3x3_H_Z}
            %p_a1 = log_asm.prepare<Z> (%p_a : {_PATCH_3x3_H_Z})
            %obs_a1 = sobs.locate_unplaced_observable<Z>(%obs_a) on (%p_a1)
                -> !sobs.unplaced_observable

            %obs_b = sobs.dec_unplaced_observable -> !sobs.unplaced_observable
            %p_b = log_asm.patch_dec -> {_PATCH_3x3_H_Z}
            %p_b1 = log_asm.prepare<Z> (%p_b : {_PATCH_3x3_H_Z})
            %obs_b1 = sobs.locate_unplaced_observable<Z>(%obs_b) on (%p_b1)
                -> !sobs.unplaced_observable
        }}
        """
        module = parse_ir(ir, xdsl_context)
        PlaceObservables().apply(xdsl_context, module)
        module.verify()

        dec_obs_ops = [op for op in module.walk() if isinstance(op, DecObservableOp)]
        assert len(dec_obs_ops) == 2
