import re

import pytest
from xdsl.dialects import test
from xdsl.dialects.builtin import ModuleOp, i1
from xdsl.ir import Block, Region
from xdsl.pattern_rewriter import PatternRewriter

from deltakit_compile.dialects import qstruct, scf
from deltakit_compile.dialects.qcore import QubitType
from deltakit_compile.dialects.stabiliser import ConcreteFlowArrayAttr, ConcreteFlowAttr
from deltakit_compile.utilities.ssa_scoping import (
    _extract_from_circuit,
    _extract_from_parallel,
    _extract_from_repeat,
    _is_subsequent_use,
    common_ancestor_region,
    extract_value_from_inner_ops,
    get_ancestors,
    insert_value_to_be_reachable_by_op,
    make_ssa_value_available_at,
)

# region Ancestors


def test_get_ancestors_returns_regions_oldest_first() -> None:
    """Returns the module and nested circuit regions in enclosing order."""
    inner_op = test.TestOp()
    circuit = qstruct.CircuitOp([], [], [inner_op, qstruct.YieldOp()])
    module = ModuleOp([circuit])

    assert get_ancestors(inner_op) == [module.body, circuit.body]


def test_get_ancestors_accepts_blocks() -> None:
    """Returns the same ancestors when given the nested block directly."""
    inner_op = test.TestOp()
    circuit = qstruct.CircuitOp([], [], [inner_op, qstruct.YieldOp()])
    module = ModuleOp([circuit])

    assert get_ancestors(circuit.body.block) == [module.body, circuit.body]


def test_get_ancestors_for_unattached_operation() -> None:
    """Returns no regions for an operation that is not attached to an IR tree."""
    assert get_ancestors(test.TestOp()) == []


def test_common_ancestor_region_same_region() -> None:
    """Returns the containing region when both operations share a block."""
    first = test.TestOp()
    second = test.TestOp()
    module = ModuleOp([first, second])

    assert common_ancestor_region(first, second) is module.body


def test_common_ancestor_region_nested_operations() -> None:
    """Checks that the first common region is returned."""
    first = test.TestOp()
    second = test.TestOp()
    circuit = qstruct.CircuitOp([], [], [first, second, qstruct.YieldOp()])
    ModuleOp([circuit])

    assert common_ancestor_region(first, second) is circuit.body


def test_common_ancestor_region_sibling_regions() -> None:
    """Check when operations are in different sibling regions."""
    first = test.TestOp()
    first_circuit = qstruct.CircuitOp([], [], [first, qstruct.YieldOp()])
    second = test.TestOp()
    second_circuit = qstruct.CircuitOp([], [], [second, qstruct.YieldOp()])
    module = ModuleOp([first_circuit, second_circuit])

    assert common_ancestor_region(first, second) is module.body


def test_common_ancestor_region_without_common_region() -> None:
    """Raises when operations belong to separate operation trees."""
    first_module = ModuleOp([first := test.TestOp()])
    second_module = ModuleOp([second := test.TestOp()])

    assert common_ancestor_region(first, second) is None

    first_module.verify()
    second_module.verify()


def test_common_ancestor_region_accepts_blocks() -> None:
    """Returns the shared region when either input is a block."""
    first = test.TestOp()
    second = test.TestOp()
    circuit = qstruct.CircuitOp([], [], [first, second, qstruct.YieldOp()])
    _ = ModuleOp([circuit])

    assert common_ancestor_region(circuit.body.block, second) is circuit.body


def test_common_ancestor_region_returns_nearest_nested_region() -> None:
    """Returns the nearest shared region for operations at different nesting depths."""
    first = test.TestOp()
    inner_circuit = qstruct.CircuitOp([], [], [first, qstruct.YieldOp()])
    second = test.TestOp()
    outer_circuit = qstruct.CircuitOp([], [], [inner_circuit, second, qstruct.YieldOp()])
    ModuleOp([outer_circuit])

    assert common_ancestor_region(first, second) is outer_circuit.body


def test_common_ancestor_region_with_unattached_input() -> None:
    """Returns ``None`` when either input is not attached to a region."""
    attached = test.TestOp()
    ModuleOp([attached])

    assert common_ancestor_region(attached, test.TestOp()) is None
    assert common_ancestor_region(test.TestOp(), attached) is None


# endregion


# region Private helpers


def test_is_subsequent_use_returns_true_for_later_use() -> None:
    """Returns true when the use follows the anchor in their block."""
    anchor = test.TestOp()
    use = test.TestOp()
    ModuleOp([anchor, use])

    assert _is_subsequent_use(use, anchor)


def test_is_subsequent_use_returns_false_for_earlier_use() -> None:
    """Returns false when the use precedes the anchor in their block."""
    use = test.TestOp()
    anchor = test.TestOp()
    ModuleOp([use, anchor])

    assert not _is_subsequent_use(use, anchor)


def test_is_subsequent_use_returns_false_for_use_inside_anchor() -> None:
    """Returns false when the use is nested inside the anchor operation."""
    use = test.TestOp()
    anchor = qstruct.CircuitOp([], [], [use, qstruct.YieldOp()])
    ModuleOp([anchor])

    assert not _is_subsequent_use(use, anchor)


def test_is_subsequent_use_handles_nested_later_use() -> None:
    """Returns true when a later use is nested in a following operation."""
    anchor = test.TestOp()
    use = test.TestOp()
    following_circuit = qstruct.CircuitOp([], [], [use, qstruct.YieldOp()])
    ModuleOp([anchor, following_circuit])

    assert _is_subsequent_use(use, anchor)


def test_is_subsequent_use_returns_false_for_unrelated_tree() -> None:
    """Returns false when the use and anchor have different roots."""
    anchor = test.TestOp()
    use = test.TestOp()
    ModuleOp([anchor])
    ModuleOp([use])

    assert not _is_subsequent_use(use, anchor)


# endregion

# region Extracting SSAs


def test_extract_from_parallel_fails() -> None:
    """Tests that ``extract_from_parallel`` fails properly if the value cannot be extracted"""

    module = ModuleOp(Region([Block(arg_types=[i1])]))
    par_op = qstruct.make_parallel_from_ops([])
    module.body.block.add_op(par_op)
    with pytest.raises(
        ValueError,
        match=re.escape(
            "Cannot extract <BlockArgument[i1] name_hint: None, index: 0, uses: 0> "
            "from qstruct.parallel since value is not defined within the given op"
        ),
    ):
        _extract_from_parallel(module.body.block.args[0], par_op, PatternRewriter(par_op))


def test_extract_from_circuit_fails() -> None:
    """Tests that ``extract_from_circuit`` fails properly if the value cannot be extracted"""

    module = ModuleOp(Region([Block(arg_types=[i1])]))
    circuit_op = qstruct.CircuitOp([], [], [])
    module.body.block.add_op(circuit_op)
    with pytest.raises(
        ValueError,
        match=re.escape(
            "Cannot extract <BlockArgument[i1] name_hint: None, index: 0, uses: 0> "
            "from qstruct.circuit since value is not defined within the given op"
        ),
    ):
        _extract_from_circuit(module.body.block.args[0], circuit_op, PatternRewriter(circuit_op))


def test_extract_from_circuit() -> None:
    """Tests that ``extract_from_circuit`` works properly if the value can be extracted"""

    module = ModuleOp(Region([Block(arg_types=[i1])]))
    test_op = test.TestOp([], [i1])
    circuit_op = qstruct.CircuitOp([], [], [test_op, qstruct.YieldOp()])
    module.body.block.add_op(circuit_op)
    result = extract_value_from_inner_ops(
        test_op.results[0], circuit_op, PatternRewriter(circuit_op)
    )
    new_circ = result.owner
    assert isinstance(new_circ, qstruct.CircuitOp), "The owner should be a qstruct.circuit"
    assert tuple(new_circ.result_types) == (i1,), "It should also return a result."
    assert tuple(new_circ.yield_op.operand_types) == (i1,), (
        "Its yield operation should return a result too."
    )
    assert circuit_op not in module.ops, "Circuit should be replaced."
    assert new_circ in module.ops, "Circuit should be replaced."


def test_extract_already_yielded_value_from_circuit() -> None:
    """Tests that ``extract_from_circuit`` works properly if the value already exists in the parent
    block."""
    module = ModuleOp(Region([Block()]))
    test_op = test.TestOp([], [i1])
    circuit_op = qstruct.CircuitOp([], [i1], [test_op, qstruct.YieldOp(*test_op.results)])
    module.body.block.add_op(circuit_op)
    result = extract_value_from_inner_ops(
        test_op.results[0], circuit_op, PatternRewriter(circuit_op)
    )
    assert result.owner is circuit_op
    assert module.body.block.first_op is circuit_op


def test_extract_already_yielded_value_from_repeat() -> None:
    """Tests that an existing repeat result can be extracted."""
    module = ModuleOp(Region([Block(arg_types=[i1])]))
    value = test.TestOp(result_types=[i1])
    repeat_op = qstruct.RepeatOp(
        2,
        Block([value, qstruct.YieldOp(value.results[0])], arg_types=[i1]),
        [module.body.block.args[0]],
    )
    module.body.block.add_op(repeat_op)
    result = _extract_from_repeat(value.results[0], repeat_op)
    assert result is repeat_op.res[0]


def test_extract_from_repeat_fails_for_value_outside_repeat() -> None:
    """Tests that a value not defined in the repeat body is rejected."""
    module = ModuleOp(Region([Block(arg_types=[i1])]))
    repeat_op = qstruct.RepeatOp(2, Block([qstruct.YieldOp()]))
    module.body.block.add_op(repeat_op)

    with pytest.raises(
        ValueError,
        match=re.escape(
            "Cannot extract <BlockArgument[i1] name_hint: None, index: 0, uses: 0> "
            "from qstruct.repeat since value is not defined within the given op."
        ),
    ):
        _extract_from_repeat(module.body.block.args[0], repeat_op)


def test_extract_from_repeat_fails_for_value_not_yielded() -> None:
    """Tests that a value not yielded by the repeat is rejected."""
    value = test.TestOp(result_types=[i1])
    repeat_op = qstruct.RepeatOp(2, Block([value, qstruct.YieldOp()]))
    ModuleOp([repeat_op])

    with pytest.raises(
        ValueError,
        match=re.escape(
            "Cannot extract <OpResult[i1] name_hint: None, index: 0, operation: test.op, uses: 0> "
            "from qstruct.repeat since it is not yielded from the repeat."
        ),
    ):
        _extract_from_repeat(value.results[0], repeat_op)


def test_extract_from_inner_ops_fails() -> None:
    """Tests that ``extract_value_from_inner_ops`` fails properly if the value cannot be
    extracted"""

    module = ModuleOp(Region([Block(arg_types=[i1])]))
    inner_op = scf.IfOp(
        cond=module.body.block.args[0],
        return_types=[i1],
        true_region=Region(
            Block(
                [
                    (test_op := test.TestOp(result_types=[i1])),
                    scf.YieldOp(module.body.block.args[0]),
                ]
            )
        ),
        false_region=Region(Block([scf.YieldOp(module.body.block.args[0])])),
    )
    par_op = qstruct.make_parallel_from_ops([inner_op])
    module.body.block.add_op(par_op)
    module.body.block.add_op(target := test.TestOp())
    with pytest.raises(
        ValueError,
        match=re.escape("Cannot extract value out of scf.if"),
    ):
        extract_value_from_inner_ops(test_op.res[0], target, PatternRewriter(par_op))


# endregion

# region Inserting SSAs


def test_insert_value_into_circuit() -> None:
    """Tests that an enclosing value becomes a circuit body argument."""
    module = ModuleOp(Region([Block(arg_types=[i1])]))
    value = module.body.block.args[0]
    target = test.TestOp()
    circuit_op = qstruct.CircuitOp([], [], [target, qstruct.YieldOp()])
    module.body.block.add_op(circuit_op)
    subsequent_use = test.TestOp(operands=[value])
    module.body.block.add_op(subsequent_use)

    result = insert_value_to_be_reachable_by_op(value, target, PatternRewriter(circuit_op))
    module.verify()
    new_circuit = result.owner.parent_op()
    assert isinstance(new_circuit, qstruct.CircuitOp)
    assert result is new_circuit.body.block.args[0]
    assert subsequent_use.operands[0] is new_circuit.res[-1]


def test_insert_qubit_into_circuit_resizes_concrete_flows() -> None:
    """Tests that threading a qubit into a circuit extends its concrete flow states."""
    qubit_type = QubitType()
    module = ModuleOp(Region([Block(arg_types=[qubit_type, qubit_type])]))
    existing_qubit, qubit_to_insert = module.body.block.args
    body = Block(arg_types=[qubit_type])
    target = test.TestOp()
    body.add_ops([target, qstruct.YieldOp(body.args[0])])
    circuit_op = qstruct.CircuitOp([existing_qubit], [qubit_type], Region(body))
    circuit_op.attributes[ConcreteFlowArrayAttr.KEY] = ConcreteFlowArrayAttr(
        [ConcreteFlowAttr("+", [], "X0 : 1", "Z0 : 1")]
    )
    module.body.block.add_op(circuit_op)

    insert_value_to_be_reachable_by_op(qubit_to_insert, target, PatternRewriter(circuit_op))

    new_circuit = module.body.block.last_op
    assert isinstance(new_circuit, qstruct.CircuitOp)
    assert ConcreteFlowArrayAttr.get(new_circuit) == ConcreteFlowArrayAttr(
        [ConcreteFlowAttr("+", [], "X0 : 2", "Z0 : 2")]
    )
    module.verify()


def test_insert_value_into_repeat() -> None:
    """Tests that an enclosing value becomes a repeat loop-carried argument."""
    module = ModuleOp(Region([Block(arg_types=[i1])]))
    value = module.body.block.args[0]
    target = test.TestOp()
    repeat_op = qstruct.RepeatOp(2, Block([target, qstruct.YieldOp()]))
    module.body.block.add_op(repeat_op)

    result = insert_value_to_be_reachable_by_op(value, target, PatternRewriter(repeat_op))
    module.verify()
    new_repeat = result.owner.parent_op()
    assert isinstance(new_repeat, qstruct.RepeatOp)
    assert result is new_repeat.body.block.args[0]
    assert tuple(new_repeat.iter_args) == (value,)
    assert tuple(new_repeat.yield_op.arguments) == (result,)


def test_insert_value_already_reachable() -> None:
    """Tests that a value in the target operation's region is returned unchanged."""
    module = ModuleOp(Region([Block(arg_types=[i1])]))
    value = module.body.block.args[0]
    target = test.TestOp()
    module.body.block.add_op(target)

    result = insert_value_to_be_reachable_by_op(value, target, PatternRewriter(target))

    assert result is value
    module.verify()


def test_insert_value_fails_for_result_defined_after_target() -> None:
    """Tests that a later result in the same block cannot be used by the target."""
    value = test.TestOp(result_types=[i1])
    target = test.TestOp()
    _ = ModuleOp([target, value])

    with pytest.raises(ValueError, match=re.escape("does not dominate")):
        insert_value_to_be_reachable_by_op(value.results[0], target, PatternRewriter(target))


def test_insert_value_fails_for_result_in_another_block() -> None:
    """Tests that a result from a non-dominating block cannot be used by the target."""
    value = test.TestOp(result_types=[i1])
    target = test.TestOp()
    _ = ModuleOp(Region([Block([value]), Block([target])]))

    with pytest.raises(ValueError, match=re.escape("does not dominate")):
        insert_value_to_be_reachable_by_op(value.results[0], target, PatternRewriter(target))


def test_insert_value_through_parallel() -> None:
    """Tests that parallel operations do not require value threading."""
    module = ModuleOp(Region([Block(arg_types=[i1])]))
    value = module.body.block.args[0]
    target = test.TestOp()
    parallel_op = qstruct.make_parallel_from_ops([target])
    module.body.block.add_op(parallel_op)

    result = insert_value_to_be_reachable_by_op(value, target, PatternRewriter(parallel_op))

    assert result is value
    module.verify()


def test_insert_value_fails_for_unsupported_operation() -> None:
    """Tests that unsupported intermediary operations are rejected."""
    module = ModuleOp(Region([Block(arg_types=[i1])]))
    value = module.body.block.args[0]
    target = test.TestOp()
    if_op = scf.IfOp(
        cond=value,
        return_types=[],
        true_region=Region(Block([target, scf.YieldOp()])),
        false_region=Region(Block([scf.YieldOp()])),
    )
    module.body.block.add_op(if_op)

    with pytest.raises(ValueError, match=re.escape("Cannot insert value into scf.if")):
        insert_value_to_be_reachable_by_op(value, target, PatternRewriter(if_op))


def test_insert_value_fails_for_value_outside_target_scope() -> None:
    """Tests that values from an unrelated operation tree are rejected."""
    value_module = ModuleOp(Region([Block(arg_types=[i1])]))
    target_module = ModuleOp([test.TestOp()])
    value = value_module.body.block.args[0]
    target = target_module.body.block.first_op
    assert target is not None

    msg = re.escape(
        "The provided value <BlockArgument[i1] name_hint: None, index: 0, uses: 0> does "
        "not dominate"
    )
    with pytest.raises(ValueError, match=msg):
        insert_value_to_be_reachable_by_op(value, target, PatternRewriter(target))


def test_insert_value_fails_for_result_from_unrelated_tree() -> None:
    """Tests that an operation result from another tree is rejected."""
    producer = test.TestOp(result_types=[i1])
    value_module = ModuleOp([producer])
    target = test.TestOp()
    target_module = ModuleOp([target])

    with pytest.raises(
        ValueError,
        match=re.escape(f"The provided value {producer.results[0]} does not dominate {target}."),
    ):
        insert_value_to_be_reachable_by_op(producer.results[0], target, PatternRewriter(target))

    value_module.verify()
    target_module.verify()


# endregion


def test_make_value_available_between_sibling_circuits() -> None:
    """Tests routing a value from one circuit into a sibling circuit."""
    module = ModuleOp(Region([Block()]))
    producer = test.TestOp(result_types=[i1])
    first_circuit = qstruct.CircuitOp([], [], [producer, qstruct.YieldOp()])
    target = test.TestOp()
    second_circuit = qstruct.CircuitOp([], [], [target, qstruct.YieldOp()])
    module.body.block.add_op(first_circuit)
    module.body.block.add_op(second_circuit)

    assert common_ancestor_region(producer, target) is module.body
    result = make_ssa_value_available_at(
        producer.results[0], target, PatternRewriter(second_circuit)
    )
    module.verify()
    new_first_circuit = producer.parent_op()
    new_second_circuit = result.owner.parent_op()
    assert isinstance(new_first_circuit, qstruct.CircuitOp)
    assert isinstance(new_second_circuit, qstruct.CircuitOp)
    assert result is new_second_circuit.body.block.args[-1]
    assert new_second_circuit.args[-1] is new_first_circuit.res[0]


def test_make_value_available_from_later_sibling_circuit_fails() -> None:
    """Tests that a later sibling circuit cannot be routed into an earlier one."""
    module = ModuleOp(Region([Block()]))
    target = test.TestOp()
    first_circuit = qstruct.CircuitOp([], [], [target, qstruct.YieldOp()])
    producer = test.TestOp(result_types=[i1])
    second_circuit = qstruct.CircuitOp([], [], [producer, qstruct.YieldOp()])
    module.body.block.add_op(first_circuit)
    module.body.block.add_op(second_circuit)

    with pytest.raises(ValueError, match=re.escape("does not dominate")):
        make_ssa_value_available_at(producer.results[0], target, PatternRewriter(first_circuit))
