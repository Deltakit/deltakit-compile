"""Tests for traits shared between deltakit_compile dialects."""

import re
from collections.abc import Callable, Sequence

import pytest
from xdsl.dialects import test as t
from xdsl.ir import Operation, Region, VerifyException
from xdsl.irdl import (
    AttrSizedRegionSegments,
    IRDLOperation,
    irdl_op_definition,
    opt_region_def,
    region_def,
    traits_def,
    var_region_def,
)
from xdsl.traits import EffectInstance, IsTerminator, MemoryEffectKind, MemoryWriteEffect

from deltakit_compile.dialects.common.traits import (
    HasParentRegion,
    get_memory_effects,
    has_memory_effect,
)


@irdl_op_definition
class MemOp(IRDLOperation):
    name = "test.mem"

    traits = traits_def(MemoryWriteEffect())


def test_memory_effect_helpers():
    """Tests memory effect helper methods."""
    effects = get_memory_effects(MemOp())
    assert effects == {EffectInstance(MemoryEffectKind.WRITE)}
    assert has_memory_effect(MemOp())

    effects = get_memory_effects(t.TestOp())
    assert effects == set()
    assert not has_memory_effect(t.TestOp())


class TestHasParentRegion:
    @irdl_op_definition
    class MyParentOp(IRDLOperation):
        name = "test.parent"

        a = region_def()
        b = opt_region_def()
        c = var_region_def()

        irdl_options = (AttrSizedRegionSegments(),)

    def test_no_parent(self):

        @irdl_op_definition
        class MyChildOp(IRDLOperation):
            name = "test.myop"

            traits = traits_def(HasParentRegion(self.MyParentOp))

        op = MyChildOp()
        op.verify()

    @pytest.mark.parametrize(
        ("has_parent_region_trait", "parent_regions_func", "error"),
        [
            (
                HasParentRegion(MyParentOp),
                lambda op: [[op()], [op()], [[op()], [op()]]],
                None,
            ),
            (
                HasParentRegion((MyParentOp, "a")),
                lambda op: [[op()], None, [Region(), Region()]],
                None,
            ),
            (
                HasParentRegion((MyParentOp, "a")),
                lambda op: [Region(), None, [[op()], Region()]],
                re.escape(
                    " Operation does not verify: 'test.myop' expects parent region 'test.parent'.a"
                ),
            ),
            (
                HasParentRegion((MyParentOp, "b")),
                lambda op: [Region(), [op()], [Region(), Region()]],
                None,
            ),
            (
                HasParentRegion((MyParentOp, "c")),
                lambda op: [Region(), None, [[op()], [op()]]],
                None,
            ),
            (
                HasParentRegion((MyParentOp, "c", 1)),
                lambda op: [Region(), None, [[], [op()]]],
                None,
            ),
            (
                HasParentRegion((MyParentOp, "c", 0)),
                lambda op: [Region(), None, [[op()], []]],
                None,
            ),
            (
                HasParentRegion((MyParentOp, "c", 0)),
                lambda op: [Region(), None, [[], [op()]]],
                re.escape(
                    "Operation does not verify: "
                    "'test.myop' expects parent region 'test.parent'.c[0]"
                ),
            ),
            (
                HasParentRegion((MyParentOp, "c", 0), (MyParentOp, "b")),
                lambda op: [Region(), None, [[op()], []]],
                None,
            ),
            (
                HasParentRegion((MyParentOp, "c", 0), (MyParentOp, "b")),
                lambda op: [Region(), [op()], [[op()], []]],
                None,
            ),
            (
                HasParentRegion((MyParentOp, "c", 0), (MyParentOp, "b")),
                lambda op: [Region(), [op()], [[op()], [op()]]],
                re.escape(
                    "Operation does not verify: "
                    "'test.myop' expects parent region to be one of "
                    "'test.parent'.c[0], 'test.parent'.b"
                ),
            ),
            (
                HasParentRegion((MyParentOp, "b"), (MyParentOp, "c", 0)),
                lambda op: [Region(), None, [[op()], []]],
                None,
            ),
            (
                HasParentRegion((MyParentOp, 1)),
                lambda op: [Region(), None, [[op()], []]],
                None,
            ),
            (
                HasParentRegion((MyParentOp, 1)),
                lambda op: [Region(), [op()], []],
                None,
            ),
            (
                HasParentRegion((MyParentOp, -1)),
                lambda op: [Region(), [], [[], [], [op()]]],
                None,
            ),
            (
                HasParentRegion((MyParentOp, "c", -2)),
                lambda op: [Region(), [], [[], [op()], []]],
                None,
            ),
            (
                HasParentRegion((MyParentOp, "c", -2)),
                lambda op: [Region(), [], [[], [op()], [], []]],
                re.escape(
                    "Operation does not verify: "
                    "'test.myop' expects parent region 'test.parent'.c[-2]"
                ),
            ),
            (
                HasParentRegion(t.TestOp, (MyParentOp, "a")),
                lambda op: [[op()], None, [Region(), Region()]],
                None,
            ),
        ],
    )
    def test_region_parent(
        self,
        has_parent_region_trait: HasParentRegion,
        parent_regions_func: Callable[
            [Callable[[], Operation]], Sequence[Region | Sequence[Operation] | None]
        ],
        error: str | None,
    ) -> None:

        @irdl_op_definition
        class MyChildOp(IRDLOperation):
            name = "test.myop"

            traits = traits_def(has_parent_region_trait, IsTerminator())

        parent = self.MyParentOp(regions=parent_regions_func(MyChildOp))
        if error is None:
            parent.verify()
        else:
            with pytest.raises(VerifyException, match=error):
                parent.verify()

    def test_invalid_creation(self) -> None:

        with pytest.raises(
            ValueError,
            match=re.escape(
                "Could not create HasParentRegion trait: "
                "test.parent does not have a region named 'd'"
            ),
        ):
            HasParentRegion((self.MyParentOp, "d"))

        with pytest.raises(
            ValueError,
            match=re.escape(
                "Could not create HasParentRegion trait: "
                "'test.parent'.a is not variadic, but an index (2) was specified."
            ),
        ):
            HasParentRegion((self.MyParentOp, "a", 2))

        with pytest.raises(
            ValueError,
            match=re.escape(
                "Could not create HasParentRegion trait: "
                "'test.parent'.b is not variadic, but an index (-1) was specified."
            ),
        ):
            HasParentRegion((self.MyParentOp, "b", -1))
