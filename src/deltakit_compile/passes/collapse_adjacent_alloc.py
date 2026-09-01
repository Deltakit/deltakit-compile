# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module containing a pass that collapses adjacent AllocQubitOps into a min set of allocations."""

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Operation, OpResult
from xdsl.parser import IntAttr
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
)
from xdsl.rewriter import InsertPoint

from deltakit_compile.dialects.qcore import (
    AllocQubitOp,
    QubitCoordinateAttr,
    QubitRegType,
    QubitType,
)
from deltakit_compile.passes.common.pipeline import (
    ConfigurablePass,
    Configuration,
    configurable_pass,
)


class _CollapseAllocOpsPattern(RewritePattern):
    def __init__(self, raise_on_attributes: bool) -> None:
        self._raise_on_attributes = raise_on_attributes

        self._seen: set[AllocQubitOp] = set()

        self._remaining_result_idxs: set[int] = set()
        self._results: list[OpResult[QubitType | QubitRegType]] = []
        self._coords: list[None | QubitCoordinateAttr | tuple[QubitCoordinateAttr, ...]] = []
        self._coord_dim: int | None = None
        self._unique_coords: set[tuple[float, ...]] = set()
        self._ids: list[None | IntAttr | tuple[IntAttr, ...]] = []
        self._unique_ids: set[int] = set()

    def _clear(self) -> None:
        self._seen.clear()

        self._remaining_result_idxs.clear()
        self._results.clear()
        self._coords.clear()
        self._coord_dim = None
        self._unique_coords.clear()
        self._ids.clear()
        self._unique_ids.clear()

    def _check_unique(
        self,
        *,
        coords: tuple[QubitCoordinateAttr, ...] | None = None,
        ids: tuple[IntAttr, ...] | None = None,
    ) -> None:
        if coords is not None:
            for c in coords:
                if (c_data := c.data) in self._unique_coords:
                    msg = (
                        f"Duplicate coordinate {c_data} found while collecting adjacent "
                        f"{AllocQubitOp.name} ops."
                    )
                    raise ValueError(msg)
                if self._coord_dim is None:
                    self._coord_dim = len(c_data)
                elif len(c_data) != self._coord_dim:
                    msg = (
                        f"Coordinate {c_data} has dimension {len(c_data)} which does not match "
                        f"the expected dimension of {self._coord_dim} while collecting adjacent "
                        f"{AllocQubitOp.name} ops."
                    )
                    raise ValueError(msg)
                self._unique_coords.add(c_data)

        if ids is not None:
            for i in ids:
                if (i_data := i.data) in self._unique_ids:
                    msg = (
                        f"Duplicate id {i_data} found while collecting adjacent "
                        f"{AllocQubitOp.name} ops."
                    )
                    raise ValueError(msg)
                self._unique_ids.add(i_data)

    def _record(self, op: AllocQubitOp) -> None:
        if self._raise_on_attributes and op.attributes:
            msg = f"{op} has attributes which would be lost when collapsing."
            raise ValueError(msg)
        self._seen.add(op)

        self._results.extend(op.result)
        qubit_result_types = op.result.types
        current_data_idx = 0
        for t in qubit_result_types:
            self._remaining_result_idxs.add(len(self._remaining_result_idxs))
            if isinstance(t, QubitType):
                if (coords := op.coords) is not None:
                    c_data: tuple[QubitCoordinateAttr, ...] = (coords.data[current_data_idx],)
                    self._check_unique(coords=c_data)
                    self._coords.append(c_data[0])
                else:
                    self._coords.append(None)

                if (ids := op.ids) is not None:
                    i_data: tuple[IntAttr, ...] = (ids.data[current_data_idx],)
                    self._check_unique(ids=i_data)
                    self._ids.append(i_data[0])
                else:
                    self._ids.append(None)

                current_data_idx += 1

            elif isinstance(t, QubitRegType):
                num_qubits = t.size.data
                if (coords := op.coords) is not None:
                    c_data = coords.data[current_data_idx : current_data_idx + num_qubits]
                    self._check_unique(coords=c_data)
                    self._coords.append(c_data)
                else:
                    self._coords.append(None)

                if (ids := op.ids) is not None:
                    i_data = ids.data[current_data_idx : current_data_idx + num_qubits]
                    self._check_unique(ids=i_data)
                    self._ids.append(i_data)
                else:
                    self._ids.append(None)

                current_data_idx += num_qubits

    def _collapse_allocs(
        self,
        rewriter: PatternRewriter,
        insertion_point: InsertPoint,
        *,
        include_coords: bool,
        include_ids: bool,
    ) -> None:
        to_allocate = {
            i
            for i in self._remaining_result_idxs
            if (self._coords[i] is not None) == include_coords
            and (self._ids[i] is not None) == include_ids
        }
        if not to_allocate:
            return

        ordered_idxs = sorted(to_allocate)
        flattened_coords: list[QubitCoordinateAttr] = []
        flattened_ids: list[IntAttr] = []
        for i in ordered_idxs:
            if include_coords:
                ith_coord = self._coords[i]
                assert ith_coord is not None
                if isinstance(ith_coord, tuple):
                    flattened_coords.extend(ith_coord)
                else:
                    flattened_coords.append(ith_coord)

            if include_ids:
                ith_id = self._ids[i]
                assert ith_id is not None
                if isinstance(ith_id, tuple):
                    flattened_ids.extend(ith_id)
                else:
                    flattened_ids.append(ith_id)

        self._remaining_result_idxs.difference_update(to_allocate)
        old_results = [self._results[i] for i in ordered_idxs]
        rewriter.insert_op(
            new_op := AllocQubitOp(
                results=[result.type for result in old_results],
                coordinates=flattened_coords if include_coords else None,
                ids=flattened_ids if include_ids else None,
            ),
            insertion_point,
        )
        for old_result, new_result in zip(old_results, new_op.result, strict=True):
            rewriter.replace_all_uses_with(old_result, new_result)

    def replace_seen_allocs(self, rewriter: PatternRewriter, insertion_point: InsertPoint) -> None:
        if not self._remaining_result_idxs:
            return
        # First collapse to an op which allocates both ids and coords
        self._collapse_allocs(rewriter, insertion_point, include_coords=True, include_ids=True)
        # Then collapse any remaining ops which allocate only coords
        self._collapse_allocs(rewriter, insertion_point, include_coords=True, include_ids=False)
        # Then only ids
        self._collapse_allocs(rewriter, insertion_point, include_coords=False, include_ids=True)
        # Finally, those with no metadata
        self._collapse_allocs(rewriter, insertion_point, include_coords=False, include_ids=False)

        assert not self._remaining_result_idxs, "Not all alloc ops were collapsed"

        for alloc_op in self._seen:
            alloc_op.detach()
            alloc_op.erase()

        self._clear()

    @override
    def match_and_rewrite(self, op: Operation, rewriter: PatternRewriter) -> None:
        if isinstance(op, AllocQubitOp):
            self._record(op)
        else:  # Non-alloc op
            self.replace_seen_allocs(rewriter, InsertPoint.before(op))


class CollapseAdjacentAllocConfig(Configuration, frozen=True):
    raise_on_attributes: bool = True


@configurable_pass
class CollapseAdjacentAlloc(ConfigurablePass[CollapseAdjacentAllocConfig]):
    """
    Combine adjacent `qcore.alloc_qubit` ops into a minimal set of (max 4) ops where possible based
    on whether coords and/or ids are defined by each original operation.

    Only adjacent allocations are combined so any other ops will prevent AllocQubitOps either side
    from being combined with each other. IDs and coordinates must be unique and coordinates must
    have the same dimension across combined ops (since these are both verified within AllocQubitOp).
    """

    name = "collapse-adjacent-alloc"

    raise_on_attributes: bool = True

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        PatternRewriteWalker(
            collapser := _CollapseAllocOpsPattern(self.raise_on_attributes),
            apply_recursively=False,
        ).rewrite_module(op)

        # Emit any remaining alloc ops at the end of the module
        if op.ops.last:  # check this is a non-empty module
            collapser.replace_seen_allocs(
                PatternRewriter(op.ops.last), InsertPoint.at_end(op.body.block)
            )
