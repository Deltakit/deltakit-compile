# (c) Copyright Riverlane 2025-2026. All rights reserved.
import warnings
from collections.abc import Iterator, Sequence
from itertools import chain

from xdsl.ir import Operation

from deltakit_compile.dialects.stim import TAG_ATTR
from deltakit_compile.exceptions import LostStimTagWarning


def walk_shallow(op: Operation) -> Iterator[Operation]:
    """Yield all direct child ops across every region of *op*, without recursing further."""
    return chain.from_iterable(block.ops for region in op.regions for block in region.blocks)


def walk_shallow_reverse(op: Operation) -> Iterator[Operation]:
    """Yield all direct child ops across every region of *op* in reverse, without recursing
    further."""
    return chain.from_iterable(
        reversed(list(block.ops))
        for region in reversed(op.regions)
        for block in reversed(region.blocks)
    )


def copy_stim_tag(op: Operation, new_op: Operation) -> None:
    """Copy the stim.tag attribute from op to new_op if it exists."""
    if stim_tag := op.attributes.get(TAG_ATTR):
        new_op.attributes[TAG_ATTR] = stim_tag


def warn_stim_tag_lost(op: Operation, reason: str) -> None:
    """Emit a StimTagLostWarning if *op* carries a stim tag that will be dropped."""
    if op.attributes.get(TAG_ATTR) is not None:
        warnings.warn(
            f"A stim tag on {op.name} was lost: {reason}",
            LostStimTagWarning,
            stacklevel=2,
        )


def copy_stim_tag_from_ops(ops: Sequence[Operation], merged: Operation, reason: str) -> None:
    """Copy the stim tag from the first tagged op to merge, warning for each subsequent tagged op.

    Intended for passes that merge multiple ops into one, where at most one tag can be preserved.
    """
    first_copied = False
    for op in ops:
        if not first_copied:
            copy_stim_tag(op, merged)
            if op.attributes.get(TAG_ATTR) is not None:
                first_copied = True
        else:
            warn_stim_tag_lost(op, reason)
