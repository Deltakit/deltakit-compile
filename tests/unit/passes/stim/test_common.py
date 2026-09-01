from xdsl.builder import Builder
from xdsl.dialects import test as t
from xdsl.dialects.builtin import ModuleOp

from deltakit_compile.passes.stim._common import walk_shallow, walk_shallow_reverse


def test_walk_shallow():
    """Test that walk_shallow correctly yields all direct child ops across every region of an op."""
    ans = []

    @Builder.implicit_region
    def region1():
        ans.append(t.TestOp())
        ans.append(t.TestOp())

    @Builder.implicit_region
    def region2():
        ans.append(t.TestOp())

    op_with_regions = t.TestOp(regions=[region1, region2])
    module = ModuleOp(module_ans := [op_with_regions, op_with_regions.clone()])

    assert list(walk_shallow(op_with_regions)) == ans
    assert list(walk_shallow(module)) == module_ans


def test_walk_shallow_reverse():
    """Test that walk_shallow_reverse correctly yields all direct child ops across every region of
    an op in reverse order."""
    ans = []

    @Builder.implicit_region
    def region1():
        ans.append(t.TestOp())
        ans.append(t.TestOp())

    @Builder.implicit_region
    def region2():
        ans.append(t.TestOp())

    op_with_regions = t.TestOp(regions=[region1, region2])
    module = ModuleOp(module_ans := [op_with_regions, op_with_regions.clone()])

    assert list(walk_shallow_reverse(op_with_regions)) == ans[::-1]
    assert list(walk_shallow_reverse(module)) == module_ans[::-1]
