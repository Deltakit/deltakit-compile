# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Tests for IR helper utilities."""

from xdsl.builder import Builder
from xdsl.dialects import test as t
from xdsl.dialects.builtin import ModuleOp, i32, i64
from xdsl.ir import Block, Region

from deltakit_compile.utilities.ir_helpers import get_all_ssa_values


class TestGetAllSSAValues:
    """Tests for the get_all_ssa_values function."""

    def test_simple_operation_no_operands(self):
        """Test that an operation with no operands returns empty used set and its results in
        created set."""
        # Create a simple test operation with no operands
        op = t.TestOp(result_types=[i32, i64])

        used, created = get_all_ssa_values(op)

        assert used == set(), "Operation with no operands should have empty used set"
        assert created == set(op.results), "Created set should contain all results"

    def test_simple_operation_with_operands(self):
        """Test that an operation with operands returns them in used set."""
        # Create SSA values from outside
        external_op = t.TestOp(result_types=[i32, i64])
        external_values = list(external_op.results)

        # Create operation that uses those values
        op = t.TestOp(operands=external_op.results, result_types=[i32])

        used, created = get_all_ssa_values(op)

        assert used == set(external_values), "Used set should contain external operands"
        assert created == set(op.results), "Created set should contain operation results"

    def test_operation_with_single_region(self):
        """Test that an operation with a region correctly tracks block args and nested ops."""

        @ModuleOp
        @Builder.implicit_region
        def module():
            # External value
            external = t.TestOp(result_types=[i32])

            # Operation with a region that has block args
            @Builder.implicit_region([i32, i64])
            def region_body(args):
                arg1, arg2 = args
                # Use external value and block arg
                inner_op = t.TestOp(operands=[external, arg1], result_types=[i32])
                # Another op using the result of inner_op
                t.TestOp(operands=[inner_op, arg2], result_types=[i64])

            t.TestOp(operands=[external], result_types=[i32], regions=[region_body])

        op_with_region = module.body.block.last_op
        assert op_with_region is not None

        used, created = get_all_ssa_values(op_with_region)

        # external should be in used (it's passed as operand to op_with_region)
        external_value = module.body.block.ops.first.results[0]
        assert used == {external_value}, "External operand should be in used set"

        exp_created = set()
        # Block args should be in created
        exp_created |= set(op_with_region.regions[0].blocks[0].args)

        # Results of inner operations should be in created
        inner_ops = list(op_with_region.regions[0].blocks[0].ops)
        for inner_op in inner_ops:
            exp_created |= set(inner_op.results)

        # Result of the operation itself should be in created
        exp_created |= set(op_with_region.results)

        assert created == exp_created

    def test_operation_with_multiple_blocks(self):
        """Test that an operation with a region that has multiple blocks correctly tracks created
        values."""

        # Setup a result used before it is defined in each block
        block2 = Block([awkward_result_op := t.TestOp(result_types=[i32])])
        block1 = Block([t.TestOp(operands=awkward_result_op.res)])

        op = t.TestOp(operands=[], regions=[Region([block1, block2])])
        ModuleOp([op])

        used, created = get_all_ssa_values(op)

        # There are no external, used values
        assert used == set()

        # the only created value is defined after its use, and still counts.
        assert created == set(awkward_result_op.res)

    def test_operation_with_nested_regions(self):
        """Test that deeply nested operations correctly track used and created values."""

        @ModuleOp
        @Builder.implicit_region
        def module():
            # External value
            external1 = t.TestOp(result_types=[i32])
            external2 = t.TestOp(result_types=[i32])

            # Outer operation with region
            @Builder.implicit_region([i32])
            def outer_region(outer_args):
                internal_op = t.TestOp(result_types=[i32])

                # Middle operation with nested region
                @Builder.implicit_region([i64])
                def inner_region(inner_args):
                    # Use external, outer_arg, and inner_arg
                    t.TestOp(
                        operands=[external1, *outer_args, *inner_args, *internal_op.res],
                        result_types=[i32],
                    )

                t.TestOp(
                    operands=[*outer_args, *external2.res],
                    result_types=[i64],
                    regions=[inner_region],
                )

            t.TestOp(operands=[external1], result_types=[i32], regions=[outer_region])

        module_ops = list(module.body.block.ops)
        outer_op = module_ops[2]
        assert outer_op is not None
        internal_op = outer_op.regions[0].blocks[0].first_op
        assert internal_op is not None
        middle_op = outer_op.regions[0].blocks[0].last_op
        assert middle_op is not None
        inner_op = middle_op.regions[0].blocks[0].first_op
        assert inner_op is not None

        used, created = get_all_ssa_values(outer_op)

        # Externals should be in used
        external_value1 = module_ops[0].results[0]
        external_value2 = module_ops[1].results[0]
        assert used == {external_value1, external_value2}, "External value should be in used set"

        exp_created = set()
        # All block args from all nested regions should be in created
        exp_created |= set(outer_op.regions[0].blocks[0].args)
        exp_created |= set(middle_op.regions[0].blocks[0].args)

        # All results should be in created
        exp_created |= set(outer_op.results)
        exp_created |= set(internal_op.results)
        exp_created |= set(middle_op.results)
        exp_created |= set(inner_op.results)

        assert created == exp_created
