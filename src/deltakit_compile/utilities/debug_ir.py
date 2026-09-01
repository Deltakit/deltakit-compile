# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for helpful debugging methods for xDSLs IR"""

from collections import OrderedDict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from io import StringIO
from typing import TypeAlias, TypeVar

from xdsl.ir import Block, BlockArgument, IRNode, Operation, OpResult, Region, SSAValue
from xdsl.printer import Printer
from xdsl.utils.diagnostic import Diagnostic

T = TypeVar("T")
OrderedSetDict: TypeAlias = dict[T, None]
"""Using a dict as a means to store an ordered set as keys to None-values."""


@dataclass
class _SearchState:
    """The state of a search through the IR that tracks context for how part of the IR are
    connected"""

    seen_nodes: set[IRNode] = field(default_factory=set)
    nodes_to_check: OrderedDict[IRNode, OrderedSetDict[SSAValue | Block]] = field(
        default_factory=OrderedDict
    )
    """Tracks all nodes as they need to be checked, along with a 'connection point' that provides
    context for how they were reached in the search"""

    def _add_next_from_op(self, op: Operation) -> None:
        for operand in op.operands:
            self.add_connection(operand.owner, operand)
        for result in op.results:
            for use in result.uses:
                self.add_connection(use.operation, result)
        for region in op.regions:
            self.add_connection(region)
        for successor in op.successors:
            self.add_connection(successor, successor)
        if op.parent:
            self.add_connection(op.parent)

    def _add_next_from_region(self, region: Region) -> None:
        for block in region.blocks:
            self.add_connection(block)
        if region.parent:
            self.add_connection(region.parent)

    def _add_next_from_block(self, block: Block) -> None:
        for use in block.uses:
            self.add_connection(use.operation, block)
        for next_op in block.ops:
            self.add_connection(next_op, block)
        for arg in block.args:
            for use in arg.uses:
                self.add_connection(use.operation, arg)
        if block.parent:
            self.add_connection(block.parent)

    def add_next_nodes(
        self,
        current_node: IRNode,
    ) -> None:
        match current_node:
            case Operation():
                self._add_next_from_op(current_node)
            case Region():
                self._add_next_from_region(current_node)
            case Block():
                self._add_next_from_block(current_node)

    def add_connection(
        self, node: IRNode, connection_point: SSAValue | Block | None = None
    ) -> None:
        if node not in self.seen_nodes:
            connections = self.nodes_to_check.setdefault(node, OrderedSetDict())
            if connection_point:
                connections |= {connection_point: None}

    def has_next(self) -> bool:
        return bool(self.nodes_to_check)

    def get_next(self) -> tuple[IRNode, OrderedSetDict[SSAValue | Block]]:
        node, connections = self.nodes_to_check.popitem(last=False)
        self.seen_nodes.add(node)
        return node, connections


def verify_ir_is_closed(op: Operation, exit_early: bool = True):
    """Checks that every other IRNode connected to op by ssa values has the same root level
    parent operation IRNode"""
    original_top_level_node = op.get_toplevel_object()

    search_state = _SearchState()

    search_state.add_connection(op)

    f = StringIO()

    failed = False
    seen_top_level_nodes: OrderedSetDict[IRNode] = OrderedSetDict({original_top_level_node: None})
    failing_connection_points: OrderedSetDict[SSAValue | Block] = OrderedSetDict()

    while search_state.has_next():
        current_node, connection_points = search_state.get_next()
        if (
            current_top_level_node := current_node.get_toplevel_object()
        ) != original_top_level_node:
            failed = True
            seen_top_level_nodes |= {current_top_level_node: None}
            failing_connection_points.update(connection_points)
            if exit_early:
                break
        else:
            search_state.add_next_nodes(current_node)

    if not failed:
        return

    diagnostic = Diagnostic({op: ["Connection checking started here"]})
    printer = Printer(stream=f, diagnostic=diagnostic, print_generic_format=True)
    top_level_nodes = {node: idx for idx, node in enumerate(seen_top_level_nodes)}

    for connection_point in failing_connection_points:
        _fill_diagnostic_for_connection_point(diagnostic, connection_point, top_level_nodes)

    for connection_point in failing_connection_points:
        _print_summary_for_connection_point(printer, connection_point, top_level_nodes)

    for original_top_level_node, idx in top_level_nodes.items():
        printer.print_string("\n\n" + "=" * 100 + "\n\n")
        printer.print_string(f"Top Level Node {idx} - ")
        _print_ir_node(printer, original_top_level_node)
    printer.print_string("\n\n" + "=" * 100)

    msg = "Not all connected IR nodes share the same top level node."
    raise ValueError(msg + f.getvalue())


def _get_nodes_string(
    top_level_nodes: Mapping[IRNode, int],
    nodes: Iterable[IRNode],
    *,
    excluded_node: IRNode | None = None,
    excluded_id: int | None = None,
) -> str:
    """Get a string for printing out a list of top level node indices from an iterable of any
    nodes."""
    connected_nodes = {
        top_level_nodes.get(node)
        for node in nodes
        if not (excluded_node and node == excluded_node.get_toplevel_object())
    }
    if excluded_id is not None:
        connected_nodes -= {excluded_id}

    return ", ".join(
        map(
            str,
            sorted(node for node in connected_nodes if isinstance(node, int)),
        )
    ) + (", ???" if None in connected_nodes else "")


def _print_summary_for_connection_point(
    printer: Printer, connection_point: SSAValue | Block, top_level_nodes: dict[IRNode, int]
) -> None:
    """Prints a summary message for for the connection point, mapping it to the top level nodes it
    connects to."""
    printer.print_string("\n")
    if isinstance(connection_point, SSAValue):
        printer.print_string("SSAValue ")
        printer.print_ssa_value(connection_point)
        ir_node = connection_point.owner
    else:
        assert isinstance(connection_point, Block)
        printer.print_string("Block ")
        printer.print_block_name(connection_point)
        ir_node = connection_point

    if (def_idx := top_level_nodes.get(ir_node.get_toplevel_object())) == 0:
        connected_nodes_for_message = _get_nodes_string(
            top_level_nodes,
            {use.operation.get_toplevel_object() for use in connection_point.uses},
            excluded_id=def_idx,
        )
        printer.print_string(f" is used within top level nodes {connected_nodes_for_message}")
    else:
        printer.print_string(f" is defined within top level node {def_idx or '???'}")


def _fill_diagnostic_for_connection_point(
    diagnostic: Diagnostic,
    connection_point: SSAValue | Block,
    top_level_nodes: Mapping[IRNode, int],
) -> None:
    """Add messages to a diagnostic to mark where the connection point between two IR structures
    are"""
    if isinstance(connection_point, SSAValue):
        connected_nodes: set[IRNode] = set()
        for use in connection_point.uses:
            if use.operation.get_toplevel_object() == connection_point.owner.get_toplevel_object():
                continue
            diagnostic.op_messages.setdefault(use.operation, []).append(
                f"Operand at index {use.index} is connected to top level node "
                f"{top_level_nodes.get(connection_point.owner.get_toplevel_object(), '???')}"
            )
            connected_nodes.add(use.operation.get_toplevel_object())

        if isinstance(connection_point.owner, Operation):
            msg = (
                f"at index {connection_point.index}"
                if isinstance(connection_point, OpResult)
                else ""
            )
            diagnostic.op_messages.setdefault(connection_point.owner, []).append(
                f"Result {msg} is connected to top level nodes "
                + _get_nodes_string(
                    top_level_nodes,
                    connected_nodes,
                    excluded_node=connection_point.owner,
                )
            )
        elif isinstance(connection_point.owner, Block) and (
            parent_op := connection_point.owner.parent_op()
        ):
            msg = (
                f"arg idx {connection_point.index}"
                if isinstance(connection_point, BlockArgument)
                else ""
            )
            region_idx = parent_op.regions.index(connection_point.owner.parent)
            block_idx = parent_op.regions[region_idx].blocks.index(connection_point.owner)
            diagnostic.op_messages.setdefault(parent_op, []).append(
                f"BlockArgument (region {region_idx}, block {block_idx}, {msg}) "
                f"is connected to top level nodes "
                + _get_nodes_string(
                    top_level_nodes,
                    connected_nodes,
                    excluded_node=connection_point.owner,
                )
            )
    elif isinstance(connection_point, Block):
        connected_nodes = set()
        for use in connection_point.uses:
            if use.operation.get_toplevel_object() == connection_point.get_toplevel_object():
                continue
            diagnostic.op_messages.setdefault(use.operation, []).append(
                f"Successor at index {use.index} is connected to top level node "
                f"{top_level_nodes.get(connection_point.get_toplevel_object(), '???')}"
            )
            connected_nodes.add(use.operation)
        if parent_op := connection_point.parent_op():
            region_idx = parent_op.regions.index(connection_point.parent)
            block_idx = parent_op.regions[region_idx].blocks.index(connection_point)
            diagnostic.op_messages.setdefault(parent_op, []).append(
                f"Block (region {region_idx}, block {block_idx}) "
                f"is connected to top level nodes "
                + _get_nodes_string(
                    top_level_nodes,
                    connected_nodes,
                    excluded_node=connection_point,
                )
            )


def _print_ir_node(printer: Printer, node: IRNode) -> None:
    if isinstance(node, Operation):
        printer.print_string("Operation:\n")
        printer.print_op(node)
    elif isinstance(node, Block):
        printer.print_string("Block:\n")
        printer.print_block(node)
    elif isinstance(node, Region):
        printer.print_string("Region:\n")
        printer.print_region(node)
