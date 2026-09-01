"""Tests for the LowerPatchDeclaration pass.

This module tests the lower_patch_declaration pass that replaces
log_asm.patch_dec operations with qcore.alloc_qubit operations.
"""

import pytest
from xdsl.context import Context
from xdsl.dialects.builtin import ArrayAttr, IntAttr, ModuleOp
from xdsl.pattern_rewriter import PatternRewriteWalker

from deltakit_compile.dialects.logical_assembly import (
    CastOp,
    OrientationEnum,
    PatchDeclarationOp,
    PlacementAttr,
    RotatedPlanarPatchType,
)
from deltakit_compile.dialects.qcore import AllocQubitOp, PackQubitRegOp
from deltakit_compile.passes.patch_lowering.rotated_surface.lower_patch_declaration import (
    LowerPatchDeclaration,
    _PatchDeclarationPattern,
)
from tests.unit.conftest import parse_ir


def make_size(x: int, y: int) -> ArrayAttr[IntAttr]:
    """Create a properly typed ArrayAttr[IntAttr] for patch size."""
    return ArrayAttr([IntAttr(x), IntAttr(y)])


def create_patch_declaration(
    width: int,
    height: int,
    x: float = 0,
    y: float = 0,
    orientation: OrientationEnum = OrientationEnum.VERTICAL_Z,
) -> PatchDeclarationOp:
    """Create a simple patch declaration op."""
    patch_type = RotatedPlanarPatchType(
        make_size(width, height), PlacementAttr((x, y), orientation)
    )
    return PatchDeclarationOp(patch_type)


class TestPatchDeclarationPatternRewriting:
    """Tests for pattern matching and rewriting."""

    def test_pattern_replaces_patch_declaration(self, xdsl_context: Context) -> None:
        """Test that the pattern replaces PatchDeclarationOp with AllocQubitOp and cast."""
        ir = """
        builtin.module {
            %patch = log_asm.patch_dec
                -> !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=v_z>
        }
        """
        module = parse_ir(ir, xdsl_context)

        # Apply the pattern
        walker = PatternRewriteWalker(_PatchDeclarationPattern(parity=True))
        walker.rewrite_module(module)

        # Verify the module is valid
        module.verify()

        # Find the AllocQubitOp in the module
        alloc_ops = [op for op in module.walk() if isinstance(op, AllocQubitOp)]
        assert len(alloc_ops) == 1

        alloc_op = alloc_ops[0]
        assert len(alloc_op.results) == 17

    def test_pattern_creates_pack(self, xdsl_context: Context) -> None:
        """Test that pattern creates qcore.pack_qubit_reg."""
        ir = """
        builtin.module {
            %patch = log_asm.patch_dec
                -> !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=v_z>
        }
        """
        module = parse_ir(ir, xdsl_context)

        # Apply the pattern
        walker = PatternRewriteWalker(_PatchDeclarationPattern(parity=True))
        walker.rewrite_module(module)

        # Verify the module is valid
        module.verify()

        # Find the CastOp in the module
        pack_ops = [op for op in module.walk() if isinstance(op, PackQubitRegOp)]
        assert len(pack_ops) == 1

        pack_op = pack_ops[0]
        assert len(pack_op.qubits) == 17

    def test_pattern_creates_cast(self, xdsl_context: Context) -> None:
        """Test that pattern creates log_asm.cast for type compatibility."""
        ir = """
        builtin.module {
            %patch = log_asm.patch_dec
                -> !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=v_z>
        }
        """
        module = parse_ir(ir, xdsl_context)

        # Apply the pattern
        walker = PatternRewriteWalker(_PatchDeclarationPattern(parity=True))
        walker.rewrite_module(module)

        # Verify the module is valid
        module.verify()

        # Find the CastOp in the module
        cast_ops = [op for op in module.walk() if isinstance(op, CastOp)]
        assert len(cast_ops) == 1

    def test_pattern_with_multiple_patch_declarations(self, xdsl_context: Context) -> None:
        """Test that pattern correctly handles multiple patch declarations."""
        ir = """
        builtin.module {
            %patch1 = log_asm.patch_dec
                -> !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=v_z>
            %patch2 = log_asm.patch_dec
                -> !log_asm.patch.rot_planar<size=(2, 2), location=(0, 0), orient=v_z>
        }
        """
        module = parse_ir(ir, xdsl_context)

        # Apply the pattern
        walker = PatternRewriteWalker(_PatchDeclarationPattern(parity=True))
        walker.rewrite_module(module)

        # Verify the module is valid
        module.verify()

        # Find all AllocQubitOps in the module
        alloc_ops = [op for op in module.walk() if isinstance(op, AllocQubitOp)]
        assert len(alloc_ops) == 2

        # First patch (3x3): 14 qubits
        # Second patch (2x2): 8 qubits
        qubit_counts = sorted([len(op.results) for op in alloc_ops])
        assert qubit_counts == [7, 17]

    def test_pattern_preserves_qubit_coordinates(self, xdsl_context: Context) -> None:
        """Test that AllocQubitOp has the correct coordinates."""
        ir = """
        builtin.module {
            %patch = log_asm.patch_dec
                -> !log_asm.patch.rot_planar<size=(2, 2), location=(0, 0), orient=v_z>
        }
        """
        module = parse_ir(ir, xdsl_context)

        # Apply the pattern
        walker = PatternRewriteWalker(_PatchDeclarationPattern(parity=True))
        walker.rewrite_module(module)

        # Verify the module is valid
        module.verify()

        # Find the AllocQubitOp
        alloc_ops = [op for op in module.walk() if isinstance(op, AllocQubitOp)]
        assert len(alloc_ops) == 1

        alloc_op = alloc_ops[0]
        assert alloc_op.coords is not None
        assert len(alloc_op.coords) == 7


class TestBoundaryParityEffect:
    """Tests for the effect of parity parameter."""

    @pytest.mark.parametrize("parity", [True, False])
    def test_pattern_with_parity_true(self, xdsl_context: Context, parity: bool) -> None:
        ir = """
        builtin.module {
            %patch = log_asm.patch_dec
                -> !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=v_z>
        }
        """
        module = parse_ir(ir, xdsl_context)

        walker = PatternRewriteWalker(_PatchDeclarationPattern(parity=parity))
        walker.rewrite_module(module)

        # Verify the module is valid
        module.verify()

        alloc_ops = [op for op in module.walk() if isinstance(op, AllocQubitOp)]
        assert len(alloc_ops) == 1
        assert len(alloc_ops[0].results) == 17


class TestLowerPatchDeclarationPass:
    """Tests for the LowerPatchDeclaration pass."""

    @pytest.mark.parametrize("parity", [True, False])
    def test_pass_applies_pattern(self, xdsl_context: Context, parity: bool) -> None:
        """Test that LowerPatchDeclaration pass applies the pattern to a module."""
        ir = """
        builtin.module {
            %patch = log_asm.patch_dec
                -> !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=v_z>
        }
        """
        module = parse_ir(ir, xdsl_context)

        pass_instance = LowerPatchDeclaration(parity)
        pass_instance.apply(xdsl_context, module)

        # Verify the module is valid
        module.verify()

        # Verify that PatchDeclarationOp has been replaced
        patch_dec_ops = [op for op in module.walk() if isinstance(op, PatchDeclarationOp)]
        assert len(patch_dec_ops) == 0

        # Verify that AllocQubitOp has been created
        alloc_ops = [op for op in module.walk() if isinstance(op, AllocQubitOp)]
        assert len(alloc_ops) == 1

    def test_pass_has_correct_name(self) -> None:
        """Test that the pass has the correct name."""
        pass_instance = LowerPatchDeclaration()
        assert pass_instance.name == "lower-patch-declaration"

    @pytest.mark.parametrize("parity", [True, False])
    def test_pass_with_multiple_declarations(self, xdsl_context: Context, parity: bool) -> None:
        """Test pass behaviour with multiple patch declarations."""
        ir = """
        builtin.module {
            %patch1 = log_asm.patch_dec
                -> !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=v_z>
            %patch2 = log_asm.patch_dec
                -> !log_asm.patch.rot_planar<size=(2, 2), location=(0, 0), orient=v_z>
            %patch3 = log_asm.patch_dec
                -> !log_asm.patch.rot_planar<size=(4, 4), location=(0, 0), orient=v_z>
        }
        """
        module = parse_ir(ir, xdsl_context)

        pass_instance = LowerPatchDeclaration(parity)
        pass_instance.apply(xdsl_context, module)

        # Verify the module is valid
        module.verify()

        # All PatchDeclarationOp should be removed
        patch_dec_ops = [op for op in module.walk() if isinstance(op, PatchDeclarationOp)]
        assert len(patch_dec_ops) == 0

        # Should have 3 AllocQubitOps
        alloc_ops = [op for op in module.walk() if isinstance(op, AllocQubitOp)]
        assert len(alloc_ops) == 3

    def test_pass_preserves_module_structure(self, xdsl_context: Context) -> None:
        """Test that pass preserves the module structure."""
        ir = """
        builtin.module {
            %patch = log_asm.patch_dec
                -> !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=v_z>
        }
        """
        module = parse_ir(ir, xdsl_context)

        # Verify module is valid before pass
        assert isinstance(module, ModuleOp)

        pass_instance = LowerPatchDeclaration()
        pass_instance.apply(xdsl_context, module)

        # Verify the module is valid
        module.verify()

        # Verify module is still valid after pass
        assert isinstance(module, ModuleOp)
        assert len(module.body.ops) > 0

    @pytest.mark.parametrize(
        ("width", "height"),
        [(1, 1), (1, 2), (2, 1), (1, 3), (3, 1), (2, 2), (2, 3), (3, 2), (3, 3), (4, 4), (5, 5)],
    )
    def test_pass_module_verifies_for_different_sizes(
        self, xdsl_context: Context, width: int, height: int
    ) -> None:
        """Test that module verifies after lowering patches of different sizes."""
        ir = f"""
        builtin.module {{
            %patch = log_asm.patch_dec
                -> !log_asm.patch.rot_planar<size=({width}, {height}), location=(0, 0), orient=v_z>
        }}
        """
        module = parse_ir(ir, xdsl_context)

        pass_instance = LowerPatchDeclaration()
        pass_instance.apply(xdsl_context, module)

        # Verify the module is valid
        module.verify()

        # Verify that patch has been lowered
        patch_dec_ops = [op for op in module.walk() if isinstance(op, PatchDeclarationOp)]
        assert len(patch_dec_ops) == 0

        # Verify that AllocQubitOp has been created
        alloc_ops = [op for op in module.walk() if isinstance(op, AllocQubitOp)]
        assert len(alloc_ops) == 1
        assert len(alloc_ops[0].results) == 2 * width * height - 1


class TestPatternNonMatching:
    """Tests for cases where the pattern should not match."""

    def test_pattern_ignores_wrong_patch_type(self, xdsl_context: Context) -> None:
        """Test that pattern doesn't match UnrotatedPlanarPatchType."""
        ir = """
        builtin.module {
            %patch = log_asm.patch_dec
                -> !log_asm.patch.unrot_planar<size=(3, 3), location=(0, 0), orient=v_z>
        }
        """
        module = parse_ir(ir, xdsl_context)

        walker = PatternRewriteWalker(_PatchDeclarationPattern(parity=True))
        walker.rewrite_module(module)
        # Since the IR contains UnrotatedPlanarPatchType, the op should still be there
        assert any(isinstance(op, PatchDeclarationOp) for op in module.walk())
