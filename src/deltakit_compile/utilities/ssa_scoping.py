# (c) Copyright Riverlane 2025-2026. All rights reserved.

"""Utilities for extracting SSA values from inner operations to outer blocks."""

from typing import TypeVar, cast

from xdsl.ir import Attribute, Block, BlockArgument, Operation, OpResult, Region, SSAValue
from xdsl.irdl.dominance import DominanceInfo
from xdsl.pattern_rewriter import PatternRewriter

from deltakit_compile.dialects import qstruct
from deltakit_compile.dialects.qcore import qubit_count
from deltakit_compile.dialects.stabiliser import ConcreteFlowArrayAttr

_T = TypeVar("_T", bound=Attribute)


# region Ancestors


def get_ancestors(op_or_block: Operation | Block) -> list[Region]:
    """Get the ancestors of ``op``, from oldest to newest."""
    current_region = op_or_block.parent_region()
    ancestors = list[Region]()
    while current_region is not None:
        ancestors.append(current_region)
        current_region = current_region.parent_region()
    # Reverse ``ancestors`` to return from oldest to newest.
    return ancestors[::-1]


def common_ancestor_region(lhs: Operation | Block, rhs: Operation | Block) -> Region | None:
    """Return the nearest region enclosing both operations or ``None`` if it does not exist."""
    first_region = lhs.parent_region()
    second_region = rhs.parent_region()
    if first_region is None or second_region is None:
        return None

    first_op_ancestors: list[Region] = get_ancestors(lhs)
    second_op_ancestors: list[Region] = get_ancestors(rhs)

    # If the oldest ancestors do not match, the operations do not have any common ancestor.
    if first_op_ancestors[0] != second_op_ancestors[0]:
        return None
    # Else, find the newest common ancestor.
    min_depth = min(len(first_op_ancestors), len(second_op_ancestors))
    for ancestor_idx in range(min_depth):
        if first_op_ancestors[ancestor_idx] != second_op_ancestors[ancestor_idx]:
            return first_op_ancestors[ancestor_idx - 1]
    # If we are here that means that both operations have the ``min_depth``-th region as an
    # ancestor, so this is the newest common ancestor.
    return first_op_ancestors[min_depth - 1]


# endregion

# region Private helpers


def _is_subsequent_use(use: Operation, anchor: Operation) -> bool:
    """Return whether ``use`` is outside and after ``anchor`` in their block."""
    if anchor.is_ancestor(use):
        return False
    anchor_block = anchor.parent_block()
    current = use
    while current.parent_block() is not anchor_block:
        parent = current.parent_op()
        if parent is None:
            return False
        current = parent
    return anchor.is_before_in_block(current)


def _value_dominates_target(
    value: SSAValue[_T], target_op: Operation, value_region: Region
) -> bool:
    """Return whether ``value`` dominates ``target_op`` from ``value_region``."""
    # Get the operation in ``value_region`` that contains ``target_op``.
    target_in_value_region = target_op
    while target_in_value_region.parent_region() is not value_region:
        parent_op = target_in_value_region.parent_op()
        if parent_op is None:
            return False
        target_in_value_region = parent_op

    # Get the blocks from ``value_region`` in which ``value`` and ``target_op`` are.
    target_block = target_in_value_region.parent_block()
    value_block = value.owner if isinstance(value.owner, Block) else value.owner.parent_block()
    # If any block is None, no domination.
    if target_block is None or value_block is None:
        return False
    # If the block of ``value`` does not dominate the block of ``target_op``, no domination.
    if not DominanceInfo(value_region).dominates(value_block, target_block):
        return False
    # From here we know that either ``value_block`` dominates ``target_block`` or they are the same
    # block. Handle the dominating case first.
    if value_block is not target_block:
        return True
    # From here, we know that ``value_block`` and ``target_block`` are the same. In which case, if
    # value is a block argument (i.e., ``isinstance(value.owner, Block)``) then it dominates target,
    # else we check operation ordering.
    return isinstance(value.owner, Block) or value.owner.is_before_in_block(target_in_value_region)


# endregion

# region Extracting SSAs


def _extract_from_parallel(
    value: SSAValue[_T], op: qstruct.ParallelOp, rewriter: PatternRewriter
) -> OpResult[_T]:
    """Given an SSAValue result from directly inside a parallel op, `op`, get the result
    of `op` if it is already yielded or replace the parallel op with one that does yield the
    result, then return that result.
    """
    if isinstance(value.owner, Block) or value.owner.parent_op() != op:
        msg = (
            f"Cannot extract {value} from {op.name} since value is not defined within the given op"
        )
        raise ValueError(msg)
    try:
        return op.yield_arg_to_result(value)
    except ValueError:
        pass

    regions = [rewriter.move_region_contents_to_new_regions(region) for region in op.par_regions]
    region = value.owner.parent_region()
    assert region
    assert region in regions
    new_index = 0
    for par_region in regions:
        current_yield_op = par_region.block.last_op
        assert isinstance(current_yield_op, qstruct.YieldOp)
        new_index += len(current_yield_op.arguments)
        if par_region == region:
            rewriter.replace_op(
                current_yield_op, qstruct.YieldOp(*current_yield_op.arguments, value)
            )
            break

    result_types = list(op.result_types)
    result_types.insert(new_index, value.type)
    new_parallel = qstruct.ParallelOp(result_types, regions, op.alignment)
    new_results = list(new_parallel.res)
    rewriter.replace_op(op, new_parallel, new_results[:new_index] + new_results[new_index + 1 :])
    return cast(OpResult[_T], new_results[new_index])


def _extract_from_circuit(
    value: SSAValue[_T], op: qstruct.CircuitOp, rewriter: PatternRewriter
) -> OpResult[_T]:
    """Given an SSAValue result from directly inside a circuit op, `op`, get the result
    of `op` if it is already yielded or replace the circuit op with one that does yield the
    result, then return that result.
    """
    if isinstance(value.owner, Block) or value.owner.parent_op() != op:
        msg = (
            f"Cannot extract {value} from {op.name} since value is not defined within the given op"
        )
        raise ValueError(msg)
    try:
        index = op.yield_op.operands.index(value)
        return cast(OpResult[_T], op.res[index])
    except ValueError:
        pass

    # If we reach here, that means we need to replace the circuit operation to return the value.
    result_types = list(op.result_types)
    result_types.append(value.type)

    new_body = rewriter.move_region_contents_to_new_regions(op.body)
    old_yield = new_body.block.last_op
    assert isinstance(old_yield, qstruct.YieldOp)
    new_yield = qstruct.YieldOp(*old_yield.operands, value)
    rewriter.replace_op(old_yield, new_yield)

    new_circuit = qstruct.CircuitOp(op.args, result_types, new_body)
    new_results = list(new_circuit.res)
    rewriter.replace_op(op, new_circuit, new_results[:-1])
    return cast(OpResult[_T], new_results[-1])


def _extract_from_repeat(value: SSAValue[_T], op: qstruct.RepeatOp) -> OpResult[_T]:
    """Get a value yielded from a ``qstruct.repeat`` body in the containing scope."""
    if isinstance(value.owner, Block) or value.owner.parent_op() != op:
        msg = (
            f"Cannot extract {value} from {op.name} since value is not defined within the given op."
        )
        raise ValueError(msg)
    try:
        index = op.yield_op.operands.index(value)
    except ValueError:
        msg = f"Cannot extract {value} from {op.name} since it is not yielded from the repeat."
        raise ValueError(msg) from None
    return cast(OpResult[_T], op.res[index])


def extract_value_from_inner_ops(
    value: SSAValue[_T], target: Operation | Region, rewriter: PatternRewriter
) -> SSAValue[_T]:
    """Given an SSAValue, return a valid SSAValue that could be used by ``target_op`` that
    represents the same value - i.e. track the input value through parallel op yields to get
    a result that is valid to use in ``target_op``, potentially replacing parallel ops to add
    a new yielded value so it can be returned."""
    if (val_region := value.owner.parent_region()) and val_region.is_ancestor(target):
        return value
    target_parent = target.parent_op()
    assert target_parent
    assert target_parent.is_ancestor(value.owner)
    current_parent = value.owner.parent_op()
    assert current_parent
    current_value = value
    while current_parent != target_parent:
        if isinstance(current_parent, qstruct.ParallelOp):
            current_value = _extract_from_parallel(current_value, current_parent, rewriter)
        elif isinstance(current_parent, qstruct.CircuitOp):
            current_value = _extract_from_circuit(current_value, current_parent, rewriter)
        elif isinstance(current_parent, qstruct.RepeatOp):
            current_value = _extract_from_repeat(current_value, current_parent)
        else:
            msg = f"Cannot extract value out of {current_parent.name}"
            raise ValueError(msg)
        current_parent = current_value.owner.parent_op()
        assert current_parent
    return current_value


# endregion

# region Inserting SSAs


def _insert_into_circuit_or_repeat(
    value: SSAValue[_T], op: qstruct.CircuitOp | qstruct.RepeatOp, rewriter: PatternRewriter
) -> BlockArgument[_T]:
    """Make an enclosing value available as a circuit or repeat body block argument and result.

    If ``value`` is already used as an operand by ``op``, returns the corresponding block argument.
    Else, this function transforms (``qstruct.circuit`` can be replaced by ``qstruct.repeat<...>``
    in the following example)::

        %0 = ...
        ... = qstruct.circuit(...) {
            ^bb0(...)
            ...
            qstruct.yield(...)
        }
        [using %0]

    into

        %0 = ...
        ..., %1 = qstruct.circuit(..., %0) {
            ^bb0(..., %2)
            ...
            qstruct.yield(..., %2)
        }
        [using %1 instead of %0]

    Arguments:
        value: the value we want to have an SSA for in the circuit body.
        op: the circuit in which we want to have an SSA representing ``value``.
        rewriter: IR rewriter.

    Returns:
        A block argument of the provided ``op.body`` representing ``value``.
    """
    if value in op.operands:
        return cast(BlockArgument[_T], op.body.block.args[op.operands.index(value)])
    new_body = rewriter.move_region_contents_to_new_regions(region=op.body)
    # Insert the new block argument.
    new_body.block.insert_arg(value.type, len(new_body.block.args))
    # Add the newly inserted block argument to the yield.
    old_yield = new_body.block.last_op
    assert isinstance(old_yield, qstruct.YieldOp)
    new_block_arg = new_body.block.args[-1]
    rewriter.replace_op(old_yield, qstruct.YieldOp(*old_yield.arguments, new_block_arg))
    # Create the new circuit or repeat operation.
    new_operation = (
        qstruct.CircuitOp([*op.args, value], [*op.result_types, value.type], new_body)
        if isinstance(op, qstruct.CircuitOp)
        else qstruct.RepeatOp(op.repetitions, new_body, [*op.iter_args, value])
    )
    # We copied either a ``qstruct.repeat`` or a ``qstruct.circuit``. Because the operation changed,
    # we don't want to blindly copy all the attributes. Instead, we copy the ones we know about.
    # This means only the stabiliser flow attribute on a ``qstruct.circuit`` needs to be copied and
    # potentially changed.
    if (
        isinstance(op, qstruct.CircuitOp)
        and (flows := op.attributes.get(ConcreteFlowArrayAttr.KEY)) is not None
    ):
        # We added the new SSA at the end, so it does not change any of the existing indices.
        # The only thing that might change is the length on which the flows is defined if we added
        # one or more qubits.
        assert isinstance(flows, ConcreteFlowArrayAttr)
        if (num_added_qubits := qubit_count(value.type)) != 0:
            total_old_length = sum(qubit_count(arg.type) for arg in op.args)
            flows = flows.resize(total_old_length + num_added_qubits)
        new_operation.attributes[ConcreteFlowArrayAttr.KEY] = flows
    if (drop_flows := op.attributes.get(ConcreteFlowArrayAttr.DROPPABLE_FLOWS_KEY)) is not None:
        new_operation.attributes[ConcreteFlowArrayAttr.DROPPABLE_FLOWS_KEY] = drop_flows
    # Replace the old circuit/repeat operation with the new one.
    new_results = list(new_operation.res)
    rewriter.replace_op(op, new_operation, new_results[:-1])
    # Replace any subsequent use of ``value`` with ``new_results[-1]``.
    value.replace_uses_with_if(
        new_results[-1], lambda use: _is_subsequent_use(use.operation, new_operation)
    )
    return cast(BlockArgument[_T], new_block_arg)


def insert_value_to_be_reachable_by_op(
    value: SSAValue[_T], target_op: Operation, rewriter: PatternRewriter
) -> SSAValue[_T]:
    """Return a SSA value that can be used in the scope of ``target_op``.

    This function ensures that an SSA value is within scope to be used by ``target_op`` by inserting
    arguments into intermediary operations if needed.

    It assumes that ``value`` is created in a region dominates ``target_op``.
    """
    if (value_region := value.owner.parent_region()) is None:
        msg = "Cannot insert an SSA value without an enclosing region."
        raise ValueError(msg)

    if not _value_dominates_target(value, target_op, value_region):
        msg = f"The provided value {value} does not dominate {target_op}."
        raise ValueError(msg)

    if value_region == target_op.parent_region():
        return value

    # Get all the operations we need to insert ``value`` into.
    target_ancestors = get_ancestors(target_op)
    target_ancestors = target_ancestors[target_ancestors.index(value_region) + 1 :]
    parent_ops = [ancestor.parent_op() for ancestor in target_ancestors]

    current_value = value
    for parent_op in parent_ops:
        assert parent_op is not None, (
            "Internal invariant: can't be none because the first entry is an operation in the same "
            "scope as ``value`` and the following one are operation within that operation."
        )
        if isinstance(parent_op, qstruct.ParallelOp):
            # Parallel operations can use the enclosing scope, so no need to insert anything.
            continue
        if isinstance(parent_op, (qstruct.CircuitOp, qstruct.RepeatOp)):
            current_value = _insert_into_circuit_or_repeat(current_value, parent_op, rewriter)
        else:
            msg = f"Cannot insert value into {parent_op.name}"
            raise ValueError(msg)
    return current_value


# endregion


def make_ssa_value_available_at(
    value: SSAValue[_T], target_op: Operation, rewriter: PatternRewriter
) -> SSAValue[_T]:
    """Ensure that the value represented by ``value`` is within scope to be used by ``target_op``.

    This function may rewrite structural operations in order to make sure that an SSA value
    equivalent to ``value`` is available in the scope of ``target_op``.

    Arguments:
        value: SSA value we want to use in the scope of ``target_op``.
        target_op: operation that should be able to use the returned SSA value.
        rewriter: IR rewriter.

    Returns:
        The (newly created or pre-existing) SSA value equivalent to ``value`` that is within scope
        to be used by ``target_op``.

    Raises:
        ValueError: if ``value`` is created in a region that has no common ancestor with
            ``target_op``.
    """
    if (common_ancestor := common_ancestor_region(value.owner, target_op)) is None:
        msg = f"{value} and {target_op} do not have a common ancestor."
        raise ValueError(msg)
    outer_value = extract_value_from_inner_ops(value, common_ancestor, rewriter)
    return insert_value_to_be_reachable_by_op(outer_value, target_op, rewriter)
