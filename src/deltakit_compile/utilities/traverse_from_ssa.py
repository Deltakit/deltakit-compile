# (c) Copyright Riverlane 2025-2026. All rights reserved.

"""Utilities for traversing forwards and backwards from an SSA value through structural operations.

Traversal returns the SSA values that are reachable (either forward or backward) through structural
operations for a target SSA value. When traversal reaches an operation that is not explicitly
handled, it stops at that boundary and returns the current SSA value as a possible origin.
"""

from dataclasses import dataclass
from typing import overload

from xdsl.ir import BlockArgument, Operation, OpResult, SSAValue, Use
from xdsl.utils.hints import isa

from deltakit_compile.dialects import qcore, qstruct, scf
from deltakit_compile.dialects.stim import QubitAllocOp


def _find_predecessor_ssas_one_step_backward_from_block_argument(
    ssa: BlockArgument,
) -> tuple[set[SSAValue], set[Operation]]:
    """Traverse backward from ``ssa`` through structural operations.

    This function performs only one "step" of traversal. For example, if the provided ``ssa`` comes
    from the block arguments of a (outer) ``qstruct.repeat`` (a structural operation) which yields a
    SSA value produced by another (inner) ``qstruct.repeat``, this function will only return the
    outer ``qstruct.repeat`` block argument and yield operand corresponding to the ``ssa`` value,
    and will **not** return anything from the inner ``qstruct.repeat``.

    Caller that need to handle multiple structural operations need to call that function several
    times.

    Args:
        ssa: source SSA value that this function will explore backward from.

    Returns:
        A set containing SSA values that are potential predecessors of ``ssa`` from a structural
        operation, not including ``ssa``, and a set containing the parent operation that blocked
        traversal.
    """
    index = ssa.index
    creator = ssa.block
    parent_op = creator.parent_op()

    source_ssas: set[SSAValue]
    match parent_op:
        case qstruct.CircuitOp():
            source_ssas = {parent_op.args[index]}
        case qstruct.RepeatOp():
            source_ssas = {parent_op.yield_op.arguments[index], parent_op.iter_args[index]}
        case scf.ForOp():
            assert isinstance(parent_op.body.block.last_op, scf.YieldOp), (
                "Expected last op of scf.ForOp body to be a scf.YieldOp."
            )
            if index == 0:
                # The first block argument of a for loop is the induction variable, which is not
                # produced by any operation.
                source_ssas = set()
            else:
                source_ssas = {
                    parent_op.body.block.last_op.arguments[index - 1],
                    parent_op.iter_args[index - 1],
                }
        case scf.WhileOp():
            if creator.parent_region() == parent_op.before_region:
                after_region_yield_op = parent_op.after_region.block.last_op
                assert isinstance(after_region_yield_op, scf.YieldOp), (
                    "Expected last op of scf.WhileOp after region to be a scf.YieldOp."
                )
                source_ssas = {parent_op.arguments[index], after_region_yield_op.arguments[index]}
            else:
                assert isinstance(parent_op.after_region.block.last_op, scf.YieldOp), (
                    "Expected last op of scf.WhileOp after region to be a scf.YieldOp."
                )
                cond_op = parent_op.before_region.block.last_op
                assert isinstance(cond_op, scf.ConditionOp), (
                    "Expected last op of scf.WhileOp before region to be a scf.Condition"
                )
                source_ssas = {cond_op.args[index]}
        # unsupported operation
        case _:
            return set(), {parent_op} if parent_op is not None else set()
    return source_ssas, set()


def _traverse_through_block_argument(ssa: BlockArgument, visited: set[SSAValue]) -> set[SSAValue]:
    """Traverse through a block argument to find possible origin SSA values.

    Args:
        ssa: The block argument to traverse from.
        visited: Set of visited SSA values to prevent infinite recursion.

    Returns:
        Set of possible origin SSA values reachable from this block argument.
        If the parent operation is not supported for traversal, the returned set
        contains only the current SSA value.
    """
    results: set[SSAValue] = set()
    if ssa in visited:
        return results
    visited.add(ssa)

    source_ssas, _ = _find_predecessor_ssas_one_step_backward_from_block_argument(ssa)
    if not source_ssas:
        # This is a terminal value, so we return {ssa} as advertised in the docstring.
        return {ssa}

    for source_ssa in source_ssas:
        sub = find_backward_ssas(source_ssa, visited)
        results.update(sub)

    return results


def _find_predecessor_ssas_one_step_backward_from_op_result(
    ssa: OpResult,
) -> tuple[set[SSAValue], set[Operation]]:
    """Traverse backward from ``ssa`` through structural operations.

    This function performs only one "step" of traversal. For example, if the provided ``ssa`` comes
    from the block arguments of a (outer) ``qstruct.repeat`` (a structural operation) which yields a
    SSA value produced by another (inner) ``qstruct.repeat``, this function will only return the
    outer ``qstruct.repeat`` block argument and yield operand corresponding to the ``ssa`` value,
    and will **not** return anything from the inner ``qstruct.repeat``.

    Caller that need to handle multiple structural operations need to call that function several
    times.

    Args:
        ssa: source SSA value that this function will explore backward from.

    Returns:
        A set containing SSA values that are potential predecessors of ``ssa`` from a structural
        operation, not including ``ssa``, and a set containing the parent operation that blocked
        traversal.
    """
    creator = ssa.op
    index = ssa.index

    source_ssas: set[SSAValue]
    match creator:
        # Pass through parallel operations
        case qstruct.ParallelOp():
            source_ssas = {creator.result_to_yield_arg(ssa)}

        # Pass through circuit/repeat operations
        case qstruct.CircuitOp() | qstruct.RepeatOp():
            source_ssas = {creator.yield_op.arguments[index]}

        # Pass through for loops
        case scf.ForOp():
            yield_op = creator.body.block.last_op
            assert isinstance(yield_op, scf.YieldOp), (
                "Expected last op of scf.ForOp body to be a scf.YieldOp."
            )
            source_ssas = {yield_op.arguments[index], creator.iter_args[index]}
        # Handle if/else branching
        case scf.IfOp():
            then_yield_op = creator.true_region.block.last_op
            else_yield_op = creator.false_region.block.last_op
            assert isinstance(then_yield_op, scf.YieldOp), (
                "Expected last op of scf.IfOp then region to be a scf.YieldOp."
            )
            assert isinstance(else_yield_op, scf.YieldOp), (
                "Expected last op of scf.IfOp else region to be a scf.YieldOp."
            )
            source_ssas = {then_yield_op.arguments[index], else_yield_op.arguments[index]}
        # Handle while loops
        case scf.WhileOp():
            before_cond_op = creator.before_region.block.last_op
            assert isinstance(before_cond_op, scf.ConditionOp), (
                "Expected last op of scf.WhileOp before region to be a scf.ConditionOp"
            )
            source_ssas = {before_cond_op.args[index]}
        # unsupported operation, stop here
        case _:
            return set(), {creator}

    return source_ssas, set()


def _traverse_through_operation_result(ssa: OpResult, visited: set[SSAValue]) -> set[SSAValue]:
    """Traverse through an operation result to find possible origin SSA values.

    Args:
        ssa: The operation result to traverse from.
        visited: Set of visited SSA values to prevent infinite recursion.

    Returns:
        Set of possible origin SSA values reachable from this operation result.
        If the creator operation is not supported for traversal, the returned
        set contains only the current SSA value.
    """
    results: set[SSAValue] = set()
    if ssa in visited:
        return results
    visited.add(ssa)

    source_ssas, _ = _find_predecessor_ssas_one_step_backward_from_op_result(ssa)
    if not source_ssas:
        # This is a terminal value, so we return {ssa} as advertised in the docstring.
        return {ssa}

    for source_ssa in source_ssas:
        sub = find_backward_ssas(source_ssa, visited)
        results.update(sub)

    return results


def _find_predecessor_ssas_one_step_backward(ssa: SSAValue) -> tuple[set[SSAValue], set[Operation]]:
    """Traverse backward from ``ssa`` through structural operations.

    This function performs only one "step" of traversal. For example, if the operation producing
    the provided ``ssa`` is a (outer) ``qstruct.repeat`` (a structural operation) which yields a SSA
    value produced by another (inner) ``struct.repeat``, this function will only return the outer
    ``qstruct.repeat`` block argument and yield operand corresponding to the ``ssa`` value, and will
    **not** return anything from the inner ``qstruct.repeat``.

    Caller that need to handle multiple structural operations need to call that function several
    times.

    Args:
        ssa: source SSA value that this function will explore backward from.

    Returns:
        A set containing SSA values that are potential predecessors of ``ssa``, not including
        ``ssa``, and a set containing the parent operation that blocked traversal.

    Raises:
        TypeError: If the SSA value is not an OpResult or BlockArgument.
    """

    # Dispatch to appropriate handler based on SSA value type
    if isa(ssa, BlockArgument):
        return _find_predecessor_ssas_one_step_backward_from_block_argument(ssa)
    # creator is an Operation
    if isa(ssa, OpResult):
        return _find_predecessor_ssas_one_step_backward_from_op_result(ssa)
    msg = f"Expected SSAValue to be either BlockArgument or OpResult, got {type(ssa)}"
    raise TypeError(msg)


def find_backward_ssas(ssa: SSAValue, visited: set[SSAValue] | None = None) -> set[SSAValue]:
    """Find all possible SSA values that this SSA value could have originated from.

    Args:
        ssa: The SSA value to traverse from.
        visited: Set of visited SSA values to prevent infinite recursion.

    Returns:
        A set of possible origin SSA values reached by traversing through
        supported structural operations (ParallelOp, CircuitOp, RepeatOp, loops,
        etc.). Traversal stops at unsupported operations and keeps the current
        SSA value as a possible origin.

    Raises:
        TypeError: If the SSA value is not an OpResult or BlockArgument.
    """
    if visited is None:
        visited = set()

    # Dispatch to appropriate handler based on SSA value type
    if isa(ssa, BlockArgument):
        return _traverse_through_block_argument(ssa, visited)
    # creator is an Operation
    if isa(ssa, OpResult):
        return _traverse_through_operation_result(ssa, visited)
    msg = f"Expected SSAValue to be either BlockArgument or OpResult, got {type(ssa)}"
    raise TypeError(msg)


def _forward_qstruct_yield(ssa: SSAValue, op: qstruct.YieldOp, idx: int) -> list[SSAValue]:
    """Return the SSA values that ``ssa`` flows into via a ``qstruct.yield``.

    Arguments:
        ssa: SSA value to track forward.
        op: Yield operation yielding ``ssa``.
        idx: Index of the operand of ``op`` representing ``ssa``.

    Returns:
        SSA values that ``ssa`` flows into via a ``qstruct.yield``.
    """
    parent = op.parent_op()
    # Yielding from a circuit: add the corresponding result.
    if isinstance(parent, qstruct.CircuitOp):
        return [parent.res[idx]]
    # Yielding from a repeat: add the corresponding result AND the corresponding block argument for
    # the next iteration of the repeat.
    if isinstance(parent, qstruct.RepeatOp):
        loop_back = parent.body.block.args[idx]
        return [parent.res[idx], loop_back]
    # Yielding from a parallel: add the corresponding result.
    if isinstance(parent, qstruct.ParallelOp):
        return [parent.yield_arg_to_result(ssa)]
    # Unsupported operation: we do not forward anything, that's not a "structural" operation.
    return []


def _forward_scf_yield(op: scf.YieldOp, idx: int) -> list[SSAValue]:
    """Return the SSA values given as the ``idx``-th argument of a ``scf.yield`` operation."""
    parent = op.parent_op()
    # Looping operation: add the result, and potential loop-back block-argument. For the loop-back
    # argument, don't forget that the induction variable appears first in the block arguments, so
    # we need to offset ``idx`` by 1.
    if isinstance(parent, scf.ForOp):
        loop_back = parent.body.block.args[idx + 1]
        return [parent.res[idx], loop_back]
    if isinstance(parent, scf.IfOp):
        return [parent.output[idx]]
    # A yield can only appear in the after-region of the while operation, and by definition of the
    # while operation its operands are directly forwarded to the before-region of the while
    # operation.
    if isinstance(parent, scf.WhileOp):
        loop_back = parent.before_region.block.args[idx]
        return [loop_back]
    return []


def _find_successor_ssas_one_step_forward(ssa: SSAValue) -> tuple[set[SSAValue], set[Use]]:
    """Traverse forward from ``ssa`` through structural operations.

    This function performs only one "step" of traversal. For example, if one of the operation using
    the provided ``ssa`` is a ``qstruct.repeat`` (a structural operation) which contains another
    ``struct.repeat``, this function will only return the outer ``qstruct.repeat`` block argument
    and result corresponding to the ``ssa`` value, and will **not** return anything from the inner
    ``qstruct.repeat``.

    Caller that need to handle multiple structural operations need to call that function several
    times.

    Args:
        ssa: source SSA value that this function will explore forward from.

    Returns:
        A pair ``(SSA values, terminal uses)`` containing SSA values that are potential successors
        of ``ssa`` through structural operations and uses of ``ssa`` that were not handled by this
        function because the operation is not supported (not a structural operation).
    """
    forwarded_ssas = set[SSAValue]()
    terminal_uses = set[Use]()

    for use in ssa.uses:
        op = use.operation
        idx = use.index

        # Recurse inside the circuit/repeat operation.
        if isinstance(op, qstruct.CircuitOp | qstruct.RepeatOp):
            forwarded_ssas.add(op.body.block.args[idx])

        elif isinstance(op, qstruct.YieldOp):
            forwarded_ssas.update(_forward_qstruct_yield(ssa, op, idx))

        # ForOp operands implicitly starts with ``start``, ``stop`` and ``step``. The block
        # representing the for-loop body only takes the induction variable as its first operand. So
        # we don't need to explore anything if ``start``, ``stop`` or ``step`` are given (because
        # they do not appear in the for-loop body), and we need to offset for the induction variable
        # that is in the first position of the block arguments.
        # Note that if the for-loop performs 0 iterations, it returns directly the input values, so
        # the corresponding results should be added.
        elif isinstance(op, scf.ForOp) and idx >= 3:
            iter_arg_idx = idx - 3
            forwarded_ssas.update([op.body.block.args[iter_arg_idx + 1], op.results[iter_arg_idx]])

        elif isinstance(op, scf.WhileOp):
            forwarded_ssas.add(op.before_region.block.args[idx])

        elif isinstance(op, scf.YieldOp):
            forwarded_ssas.update(_forward_scf_yield(op, idx))

        # The first operand of ConditionOp is the condition being evaluated, and this condition is
        # not forwarded to the after-region. So we do not have to continue exploring if the SSA
        # representing the condition is given to us here, and we need to account for the fact that
        # the after-region block only takes the other operands of ConditionOp.
        elif isinstance(op, scf.ConditionOp) and idx >= 1:
            forwarded_arg_idx = idx - 1
            while_op = op.parent_op()
            assert isinstance(while_op, scf.WhileOp), "Expected ConditionOp to be inside a WhileOp."
            forwarded_ssas.add(while_op.after_region.block.args[forwarded_arg_idx])
            forwarded_ssas.add(while_op.res[forwarded_arg_idx])

        # We did not match the operation, which means it is considered to be a non-structural
        # operation that the user might have to handle themselves. Keeping the ``Use`` instance to
        # make the caller life easier.
        else:
            terminal_uses.add(use)

    return forwarded_ssas, terminal_uses


def _traverse_forward(ssa: SSAValue, visited: set[SSAValue]) -> tuple[set[SSAValue], set[Use]]:
    """Traverse forward from an SSA value through structural operations.

    Args:
        ssa: The SSA value to traverse from.
        visited: Set of visited SSA values to prevent infinite recursion.

    Returns:
        Set of terminal SSA values (SSA values that are used by at least one non-structural
        operation) reachable forward from this value through supported structural
        operations and the set of terminal uses (i.e., non-structural operations that were found
        while exploring but for which the exploration stopped because they are not structural
        operations). Returns ``({ssa}, uses)`` if no structural uses are found (i.e., the provided
        ``ssa`` is either not used, or only used by non-structural operations).
    """
    if ssa in visited:
        return set(), set()
    visited.add(ssa)

    forwarded_ssas, terminal_uses = _find_successor_ssas_one_step_forward(ssa)

    if not forwarded_ssas:
        return {ssa}, terminal_uses

    ssas = set[SSAValue]()
    for fssa in forwarded_ssas:
        ssas_, term_uses = _traverse_forward(fssa, visited)
        ssas.update(ssas_)
        terminal_uses.update(term_uses)
    return ssas, terminal_uses


def find_forward_ssas(
    ssa: SSAValue,
    visited: set[SSAValue] | None = None,
) -> tuple[set[SSAValue], set[Use]]:
    """Find all SSA values that this SSA value is a potential origin of.

    This is the dual of ``find_backward_ssa``: where that function traverses backwards
    through structural operations to find origins, this function traverses forwards through uses to
    find all SSA values that could have ``ssa`` as a potential origin.

    Traversal follows values forward through structural operations (``ParallelOp``, ``CircuitOp``,
    ``RepeatOp``, ``scf`` loops, etc.) and stops at SSA values with no structural uses, returning
    them as terminals.

    Args:
        ssa: The SSA value to traverse from.
        visited: Set of visited SSA values to prevent infinite recursion.

    Returns:
        Set of terminal SSA values (SSA values that are used by at least one non-structural
        operation) reachable forward from this value through supported structural
        operations and the set of terminal uses (i.e., non-structural operations that were found
        while exploring but for which the exploration stopped because they are not structural
        operations). Returns ``({ssa}, uses)`` if no structural uses are found (i.e., the provided
        ``ssa`` is either not used, or only used by non-structural operations).
    """
    if visited is None:
        visited = set()
    return _traverse_forward(ssa, visited)


def find_all_predecessor_and_successor_ssas(
    ssa: SSAValue,
) -> tuple[set[SSAValue], set[Use], set[Operation]]:
    """Find all SSA values that are potential predecessors or successors of ``ssa``.

    This function is similar to ``find_forward_ssas`` and ``find_backward_ssas`` but differs in two
    core points:
    1. It returns all the SSA values, not only the ones that resulted in the exploration being
       blocked.
    2. It performs a bidirectional traversal.

    For the moment, this function assumes that ``qstruct.repeat`` operations have an infinite number
    of rounds, and so might return a larger super-set of the potentially equivalent SSA values if a
    ``qstruct.repeat`` operation is explored.

    Args:
        ssa: The SSA value to traverse from.

    Returns:
        A tuple composed of:
        - the set of SSA values that are potential predecessors or successors of ``ssa``, including
          ``ssa``.
        - the set of uses that blocked the forward traversal (guaranteed to be non-structural
          operations),
        - the set of operations that blocked the backward traversal (guaranteed to be non-structural
          operations).

    Raises:
        TypeError: If the SSA value is not an ``OpResult`` or ``BlockArgument``.
    """
    visited_ssas = set[SSAValue]()
    to_explore_not_visited = {ssa}
    blocking_uses = set[Use]()
    blocking_ops = set[Operation]()
    while to_explore_not_visited:
        explored_ssa = to_explore_not_visited.pop()
        visited_ssas.add(explored_ssa)

        # Collect all the potential successor and predecessor SSA values by first going forward and
        # then going backward.
        forward_ssas, blocker_uses = _find_successor_ssas_one_step_forward(explored_ssa)
        backward_ssas, blocker_ops = _find_predecessor_ssas_one_step_backward(explored_ssa)

        # Then update the data-structures
        to_explore_not_visited |= (forward_ssas | backward_ssas) - visited_ssas
        blocking_uses |= blocker_uses
        blocker_ops |= blocker_ops

    return visited_ssas, blocking_uses, blocking_ops


# region Qubit-index tracking


@dataclass(frozen=True)
class TrackedQubit:
    """Dataclass identifying a qubit.

    This class can represent a qubit in two ways:
    - either ``self.ssa.type`` is a ``qcore.QubitType()``, in which case ``self.index`` is ``None``
      and the qubit is represented by ``self.ssa``.
    - or ``self.ssa.type`` is a ``qcore.QubitRegType()``, in which case ``self.index`` is not
      ``None`` and the qubit is represented by the ``self.index``-th entry of ``self.ssa``.

    Attributes:
        ssa: SSA value representing (potentially partially) the tracked qubit.
        index: if ``self.ssa`` represents a qubit register, the index of the tracked qubit. Else,
            ``None``.
    """

    ssa: SSAValue
    index: int | None = None

    def __post_init__(self) -> None:
        if isinstance(self.ssa.type, qcore.QubitType):
            if self.index is not None:
                msg = "A scalar qubit cannot have a register index."
                raise TypeError(msg)
        elif isinstance(self.ssa.type, qcore.QubitRegType):
            if self.index is None:
                msg = "A qubit register requires a register index."
                raise TypeError(msg)
            if not 0 <= self.index < len(self.ssa.type):
                msg = f"Register index {self.index} is out of bounds for {self.ssa.type}."
                raise IndexError(msg)
        else:
            msg = f"Expected a qubit or qubit register SSA value, got {self.ssa.type}."
            raise TypeError(msg)

    @property
    def register_index(self) -> int:
        """Return the register index, raising if ``self.index`` is ``None``."""
        if self.index is None:
            msg = "Expected a tracked qubit in a register."
            raise TypeError(msg)
        return self.index


_QCORE_OPS_TYPE = (
    qcore.PackQubitRegOp | qcore.UnpackQubitRegOp | qcore.ConcatenateOp | qcore.SplitOp
)


@dataclass
class _StrictTraversalContext:
    """Store a cache for identity-repeat computation to avoid any re-computation.

    This data-class is threaded through most of the qubit-index analysis exploration and stores the
    status of already explored ``qstruct.repeat`` operations. It exists to avoid re-computing
    whether a given ``qstruct.repeat`` is a position-preserving repeat or not.

    Position-preserving ``qstruct.repeat`` are repeat operations for which we can guarantee that the
    order of equivalent SSAs is not shuffled between loops. The typical example of a non-identity
    (shuffling) repeat would be::

        qstruct.repeat<100>(%0, %1, %2) {
            ^bb0(%3, %4, %5)
            qstruct.yield(%4, %5, %3)
        }

    Only position-preserving ``qstruct.repeat`` operations are currently supported.

    Attributes:
        identity_repeats: cache attribute storing whether an explored ``qstruct.repeat`` operation
            is a position-preserving repeat or not.
    """

    identity_repeats: dict[qstruct.RepeatOp, bool]

    def is_identity_repeat(self, op: qstruct.RepeatOp) -> bool:
        """Check if the given operation is a position-preserving repeat."""
        if op not in self.identity_repeats:
            self.identity_repeats[op] = _compute_identity_repeat(op, self)
        return self.identity_repeats[op]


def _strict_forward_qcore(
    value: TrackedQubit, op: _QCORE_OPS_TYPE, operand_index: int | None
) -> set[TrackedQubit]:
    """Return the tracked qubit successor through a ``qcore`` grouping operation.

    ``qcore.pack_qubit_reg`` and ``qcore.unpack_qubit_reg`` preserve the order of qubits in a
    register. ``qcore.concatenate`` converts an input register index into an index in the combined
    register, while ``qcore.split`` performs the inverse mapping.

    Args:
        value: The qubit or register element being tracked.
        op: The ``qcore`` grouping operation using ``value``.
        operand_index: The operand position of ``value`` in ``op``. This is relevant for variadic
            operands such as for ``qcore.pack_qubit_reg`` and ``qcore.concatenate``.

    Returns:
        A set containing the equivalent qubit explored.
    """
    assert value.ssa in op.operands
    match op:
        case qcore.PackQubitRegOp():
            return {TrackedQubit(op.reg, operand_index)}
        case qcore.UnpackQubitRegOp():
            assert value.index is not None, "UnpackQubitRegOp takes a register as operand."
            return {TrackedQubit(op.qubits[value.index])}
        case qcore.ConcatenateOp():
            assert value.index is not None, "ConcatenateOp takes registers as operands."
            offset = sum(qcore.qubit_count(reg.type) for reg in op.in_regs[:operand_index])
            return {TrackedQubit(op.out_reg, offset + value.index)}
        case qcore.SplitOp():
            assert value.index is not None, "SplitOp takes registers as operands."
            offset = 0
            for result in op.out_regs:
                result_size = qcore.qubit_count(result.type)
                if value.index < offset + result_size:
                    return {TrackedQubit(result, value.index - offset)}
                offset += result_size
            # In theory this part of the code is unreachable because qcore.split constraints check
            # that the number of qubits in the input and in the output match.
            msg = (  # pragma: no cover
                f"Could not track qubit {value} through {op}: it seems like {value.index} is "
                "greater than the number of qubits in the output of the operation, which should "
                "not happen."
            )
            raise AssertionError(msg)  # pragma: no cover


def _compute_identity_repeat(op: qstruct.RepeatOp, context: _StrictTraversalContext) -> bool:
    """Return whether a repeat preserves every iteration argument at the same position.

    This function explores recursively the body of ``op`` by setting ``op`` as a barrier. This
    allows to handle nested structural operations (e.g., nested ``qstruct.repeat``) without
    going out of ``op`` body.

    Args:
        op: The repeat operation whose iteration arguments are being checked.
        context: The traversal context used to cache identity results for repeats encountered while
            checking this operation.

    Returns:
        ``True`` if every yielded value is considered equivalent to the corresponding body
        argument, otherwise ``False``.
    """
    for body_arg, yielded_arg in zip(op.body.block.args, op.yield_op.operands, strict=True):
        qubit_count = qcore.qubit_count(body_arg.type)
        assert qubit_count == qcore.qubit_count(yielded_arg.type), (
            "Checked by qstruct.repeat verify_."
        )
        for index in range(qubit_count):
            body_qubit = TrackedQubit(
                body_arg,
                index if isinstance(body_arg.type, qcore.QubitRegType) else None,
            )
            yielded_qubit = TrackedQubit(
                yielded_arg,
                index if isinstance(yielded_arg.type, qcore.QubitRegType) else None,
            )
            if yielded_qubit not in _strict_forward_without_repeat(
                body_qubit, blocked_repeat=op, context=context
            ):
                return False
    return True


def _strict_forward_without_repeat(
    value: TrackedQubit,
    *,
    blocked_repeat: qstruct.RepeatOp,
    context: _StrictTraversalContext,
) -> set[TrackedQubit]:
    """Find values reachable forward while stopping at ``blocked_repeat``.

    This function is used to explore the body of a ``qstruct.repeat`` to check if it is
    position-preserving without exploring outside of the body.

    Nested ``qstruct.repeat`` are traversed normally.

    Args:
        value: The starting qubit, including its register index when applicable.
        blocked_repeat: The ``qstruct.repeat`` operation at which traversal must stop.
        context: The traversal context used to cache identity results for nested repeats.

    Returns:
        All equivalent tracked qubits reached by exploring the IR, stopping any path when it
        reaches ``blocked_repeat``.
    """
    visited = {value}
    pending = [value]
    while pending:
        current = pending.pop()
        for use in current.ssa.uses:
            successors, _ = _strict_forward_one_use(
                current, use, blocked_repeat=blocked_repeat, context=context
            )
            new_successors = [successor for successor in successors if successor not in visited]
            pending.extend(new_successors)
            visited.update(new_successors)
    return visited


def _strict_forward_yield(
    value: TrackedQubit,
    op: qstruct.YieldOp,
    operand_index: int,
    *,
    context: _StrictTraversalContext,
    blocked_repeat: qstruct.RepeatOp | None = None,
) -> set[TrackedQubit] | None:
    """Return successors for a structural yield operation.

    A ``qstruct.yield`` within a ``qstruct.repeat`` is traversed only when the ``qstruct.repeat``
    has been proven to preserve all body arguments positionally and is not ``blocked_repeat``.

    Args:
        value: The qubit being tracked.
        op: The ``qstruct.yield`` operation using the tracked value.
        operand_index: The yielded-value position of ``value`` in ``op``.
        context: The traversal context used to cache identity results for repeats.
        blocked_repeat: An optional "boundary" that must not be traversed. Used when recursively
            exploring ``qstruct.repeat`` operations body to check if they preserve the position of
            their iteration arguments.

    Returns:
        A set containing the equivalent successors, or ``None`` if the yield is unsupported (e.g.,
        if ``op`` is within a ``qstruct.repeat`` that does not preserve the position of its
        iteration arguments).
    """
    parent = op.parent_op()
    index = value.index
    if isinstance(parent, qstruct.CircuitOp):
        return {TrackedQubit(parent.res[operand_index], index)}
    if (
        isinstance(parent, qstruct.RepeatOp)
        and parent is not blocked_repeat
        and context.is_identity_repeat(parent)
    ):
        return {TrackedQubit(parent.res[operand_index], index)}
    if isinstance(parent, qstruct.ParallelOp):
        return {TrackedQubit(parent.yield_arg_to_result(value.ssa), index)}
    return None


def _strict_forward_one_use(
    value: TrackedQubit,
    use: Use,
    *,
    context: _StrictTraversalContext,
    blocked_repeat: qstruct.RepeatOp | None = None,
) -> tuple[set[TrackedQubit], bool]:
    """Return successors and whether a use is a blocker."""
    op, operand_index = use.operation, use.index
    assert value.ssa in op.operands
    if isinstance(op, _QCORE_OPS_TYPE):
        # Supported qcore operations are not blocking the exploration.
        return _strict_forward_qcore(value, op, operand_index), False
    if (
        isinstance(op, qstruct.RepeatOp)
        and op is not blocked_repeat
        and context.is_identity_repeat(op)
    ) or isinstance(op, qstruct.CircuitOp):
        # CircuitOp or position-preserving RepeatOp are not blocking the exploration.
        return {TrackedQubit(op.body.block.args[operand_index], value.index)}, False
    # The following operations might be blocking the exploration. By default, if the operation is
    # not handled by a below if branch, it is supposed blocking and so ``successors`` is ``None`` by
    # default.
    successors: set[TrackedQubit] | None = None
    if isinstance(op, qstruct.YieldOp):
        successors = _strict_forward_yield(
            value, op, operand_index, context=context, blocked_repeat=blocked_repeat
        )
    return successors or set(), successors is None


def _strict_forward_one_step(
    value: TrackedQubit, *, context: _StrictTraversalContext
) -> tuple[set[TrackedQubit], set[Use]]:
    """Return strict structural successors of a tracked qubit by iterating all its uses.

    Args:
        value: the tracked qubit to find equivalent SSAs of.
        context: The traversal context used to cache identity results for repeats.

    Returns:
        a pair of ``(equivalent qubits, blocking uses)`` where:

        - ``equivalent qubits`` is a set of ``TrackedQubit`` that are equivalent to ``value`` and,
        - ``blocking uses`` are uses of ``value.ssa`` that were not supported by this function and
          so returned as "blockers".
    """
    successors: set[TrackedQubit] = set()
    blockers: set[Use] = set()
    ssa = value.ssa

    for use in ssa.uses:
        forwarded, blocked = _strict_forward_one_use(value, use, context=context)
        successors.update(forwarded)
        if blocked:
            blockers.add(use)

    return successors, blockers


def _strict_backward_block_argument(
    ssa: BlockArgument, index: int | None, *, context: _StrictTraversalContext
) -> tuple[set[TrackedQubit], set[Operation]]:
    """Return predecessors for a structural block argument."""
    parent = ssa.block.parent_op()
    assert parent is not None, "A block without a parent should not happen."
    position = ssa.index
    if isinstance(parent, qstruct.CircuitOp):
        return {TrackedQubit(parent.args[position], index)}, set()
    if isinstance(parent, qstruct.RepeatOp) and context.is_identity_repeat(parent):
        return {TrackedQubit(parent.iter_args[position], index)}, set()
    return set(), {parent}


def _strict_backward_op_result(
    value: TrackedQubit, *, context: _StrictTraversalContext
) -> tuple[set[TrackedQubit], set[Operation]]:
    """Return predecessors for a structural operation result."""
    ssa = value.ssa
    assert isinstance(ssa, OpResult)
    op = ssa.op
    if isinstance(op, qcore.AllocQubitOp):
        # qcore.alloc_qubit is the only operation that stops the back-propagation without being
        # registered as a blocking op.
        return set(), set()
    if isinstance(op, _QCORE_OPS_TYPE):
        return _strict_backward_qcore(value, op)
    if isinstance(op, (qstruct.CircuitOp, qstruct.RepeatOp, qstruct.ParallelOp)):
        return _strict_backward_structural(value, op, context=context)
    return set(), {op}


def _strict_backward_qcore(
    value: TrackedQubit, op: _QCORE_OPS_TYPE
) -> tuple[set[TrackedQubit], set[Operation]]:
    """Return predecessors for qcore register-grouping results."""
    ssa = value.ssa
    assert isinstance(ssa, OpResult)
    match op:
        case qcore.PackQubitRegOp():
            return {TrackedQubit(op.qubits[value.register_index])}, set()
        case qcore.UnpackQubitRegOp():
            return {TrackedQubit(op.reg, ssa.index)}, set()
        case qcore.ConcatenateOp():
            absolute_index = value.register_index
            offset = 0
            for reg in op.in_regs:
                reg_size = qcore.qubit_count(reg.type)
                if absolute_index < offset + reg_size:
                    return {TrackedQubit(reg, absolute_index - offset)}, set()
                offset += reg_size
            # In theory this part of the code is unreachable because qcore.concatenate constraints
            # check that the number of qubits in the input and in the output match.
            msg = (  # pragma: no cover
                f"Could not track qubit {value} through {op}: it seems like {value.index} is "
                "greater than the number of qubits in the operands of the operation, which should "
                "not happen."
            )
            raise AssertionError(msg)  # pragma: no cover
        case qcore.SplitOp():
            result_index = op.out_regs.index(ssa)
            offset = sum(qcore.qubit_count(reg.type) for reg in op.out_regs[:result_index])
            return {TrackedQubit(op.in_reg, offset + value.register_index)}, set()


def _strict_backward_structural(
    value: TrackedQubit,
    op: qstruct.CircuitOp | qstruct.ParallelOp | qstruct.RepeatOp,
    *,
    context: _StrictTraversalContext,
) -> tuple[set[TrackedQubit], set[Operation]]:
    """Return predecessors for structural operation results."""
    ssa, index = value.ssa, value.index
    assert isinstance(ssa, OpResult)
    match op:
        case qstruct.CircuitOp():
            return {TrackedQubit(op.yield_op.arguments[ssa.index], index)}, set()
        case qstruct.RepeatOp():
            if context.is_identity_repeat(op):
                return {TrackedQubit(op.yield_op.arguments[ssa.index], index)}, set()
            return set(), {op}
        case qstruct.ParallelOp():
            return {TrackedQubit(op.result_to_yield_arg(ssa), index)}, set()


def _strict_backward_one_step(
    value: TrackedQubit, *, context: _StrictTraversalContext
) -> tuple[set[TrackedQubit], set[Operation]]:
    """Return strict structural predecessors of a tracked qubit."""
    ssa = value.ssa
    if isinstance(ssa, BlockArgument):
        return _strict_backward_block_argument(ssa, value.index, context=context)
    if isinstance(ssa, OpResult):
        return _strict_backward_op_result(value, context=context)
    msg = f"Expected {OpResult.__name__} or {BlockArgument.__name__}, got {type(ssa).__name__}."
    raise TypeError(msg)


@overload
def find_equivalent_qubit_ssas(
    ssa: SSAValue[qcore.QubitType], index: None = None
) -> tuple[set[TrackedQubit], set[Use], set[Operation]]: ...
@overload
def find_equivalent_qubit_ssas(
    ssa: SSAValue[qcore.QubitRegType], index: int
) -> tuple[set[TrackedQubit], set[Use], set[Operation]]: ...


def find_equivalent_qubit_ssas(
    ssa: SSAValue[qcore.QubitType] | SSAValue[qcore.QubitRegType], index: int | None = None
) -> tuple[set[TrackedQubit], set[Use], set[Operation]]:
    """Find structurally equivalent qubit SSA values.

    This function is different from ``find_all_predecessor_and_successor_ssas`` in two ways:

    1. it only works for qubits and will fail if the provided ``ssa`` is not qubit-like (see
       argument documentation for a precise definition),
    2. it returns the strictly equivalent SSA values.

    As such, this function is more restrictive than ``find_all_predecessor_and_successor_ssas`` on
    its allowed inputs, and has a stricter condition on the SSA values returned.

    Args:
        ssa: A scalar qubit SSA value or a qubit-register SSA value. Register values must be paired
            with an ``index`` identifying the element to track.
        index: The zero-based element index when ``ssa`` is a register, or ``None`` for a scalar
            qubit. The value is validated by ``TrackedQubit``.

    Returns:
        A tuple ``(equivalent qubits, blocking uses, blocking operations)`` with:

        - the set of all equivalent qubits that have been found by this function,
        - the set of all the blocking uses (i.e., uses from an operation that is unsupported by this
          function),
        - the set of all the blocking operations (i.e., operations that create an SSA value that is
          considered equivalent, but that are not supported by this function).
    """
    start = TrackedQubit(ssa, index)
    context = _StrictTraversalContext(identity_repeats={})
    visited: set[TrackedQubit] = set()
    pending = [start]
    blocking_uses: set[Use] = set()
    blocking_ops: set[Operation] = set()

    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        forward, uses = _strict_forward_one_step(current, context=context)
        backward, ops = _strict_backward_one_step(current, context=context)
        blocking_uses.update(uses)
        blocking_ops.update(ops)
        pending.extend((forward | backward) - visited)

    return visited, blocking_uses, blocking_ops


# endregion


def get_qubit_id(target: SSAValue) -> int:
    """Get the ID of a qubit from its SSA value. Assumes the SSA value is an
    OpResult and has QubitAllocOp as its operation. This circumvents some typing
    issues by performing the checks dynamically."""
    if not isinstance(target, OpResult):
        msg = f"Expected OpResult, got {type(target)}"
        raise TypeError(msg)
    if not isinstance((operation := target.op), QubitAllocOp):
        msg = f"Expected QubitAllocOp, got {type(operation)}"
        raise TypeError(msg)
    return operation.id.data
