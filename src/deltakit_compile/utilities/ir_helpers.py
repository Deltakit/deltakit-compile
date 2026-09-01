# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Utility methods for analysing xDSL IR."""

from xdsl.ir import Operation, SSAValue


def get_all_ssa_values(op: Operation) -> tuple[set[SSAValue], set[SSAValue]]:
    """Get every `SSAValue` used as an operand in `op` that originates from outside `op` and every
    `SSAValue` created by and inside `op`.

    Args:
        op: The Operation to search for `SSAValue`s.

    Returns:
        The set of used `SSAValues` and the set of created `SSAValues`.
    """
    used: set[SSAValue] = set()
    created: set[SSAValue] = set()
    _get_all_ssa_values(op, used=used, created=created)
    return used - created, created


def _get_all_ssa_values(op: Operation, *, used: set[SSAValue], created: set[SSAValue]) -> None:
    """Add every `SSAValue` used by and within `op` to `used` and every `SSAValue` created by or
    within `op` to `created`.
    """
    used.update(op.operands)
    for region in op.regions:
        for block in region.blocks:
            created.update(block.args)
            for child in block.ops:
                _get_all_ssa_values(child, used=used, created=created)
    created.update(op.results)
