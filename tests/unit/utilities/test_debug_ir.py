import re

import pytest
from xdsl.dialects import test as t
from xdsl.dialects.builtin import ModuleOp, i1
from xdsl.ir import Block, Region

from deltakit_compile.utilities.debug_ir import verify_ir_is_closed


def test_debug_ir_dangling_result_operand() -> None:

    t_op = t.TestOp(result_types=[i1])
    module = ModuleOp([t.TestOp(operands=t_op.res)])

    with pytest.raises(
        ValueError, match="Not all connected IR nodes share the same top level node"
    ):
        verify_ir_is_closed(module)


def test_debug_ir_dangling_block_arg_operand() -> None:

    t_op = t.TestOp(regions=(Region([Block([], arg_types=[i1])]),))
    module = ModuleOp([t.TestOp(operands=t_op.regs[0].block.args)])

    with pytest.raises(
        ValueError, match="Not all connected IR nodes share the same top level node"
    ):
        verify_ir_is_closed(module)


def test_debug_ir_dangling_result() -> None:

    module = ModuleOp([t_op := t.TestOp(result_types=[i1])])
    t.TestOp(operands=t_op.res)

    with pytest.raises(
        ValueError, match="Not all connected IR nodes share the same top level node"
    ):
        verify_ir_is_closed(module)


def test_debug_ir_dangling_block_arg() -> None:

    module = ModuleOp(Region([block := Block(arg_types=[i1])]))
    t.TestOp(operands=block.args)

    with pytest.raises(
        ValueError, match="Not all connected IR nodes share the same top level node"
    ):
        verify_ir_is_closed(module)


def test_debug_ir_dangling_successor_use() -> None:

    module = ModuleOp([t.TestOp(), t.TestOp(), t.TestOp()])
    t.TestTermOp(result_types=[i1], successors=(module.body.block,))

    with pytest.raises(
        ValueError, match="Not all connected IR nodes share the same top level node"
    ):
        verify_ir_is_closed(module)


def test_debug_ir_dangling_successor_use_from_block() -> None:

    block = Block([start_op := t.TestOp(), t.TestOp(), t.TestOp()])
    t.TestTermOp(result_types=[i1], successors=(block,))

    with pytest.raises(ValueError, match=re.escape("Block ^bb0 is used within top level nodes 1")):
        verify_ir_is_closed(start_op)


def test_debug_ir_dangling_successor() -> None:

    module = ModuleOp(
        [t.TestOp(), t.TestOp(), t.TestOp(), t.TestTermOp(result_types=[i1], successors=(Block(),))]
    )

    with pytest.raises(
        ValueError, match="Not all connected IR nodes share the same top level node"
    ):
        verify_ir_is_closed(module)


def test_debug_ir_dangling_operands() -> None:

    t_op = t.TestOp(result_types=[i1, i1, i1])
    module = ModuleOp([t.TestOp(operands=t_op.res)])

    with pytest.raises(
        ValueError, match="Not all connected IR nodes share the same top level node"
    ):
        verify_ir_is_closed(module)


def test_debug_ir_indirectly_connected_node() -> None:

    t_op = t.TestOp(result_types=[i1, i1, i1])
    t.TestOp(operands=t_op.res)
    module = ModuleOp([t.TestOp(operands=t_op.res)])
    with pytest.raises(ValueError, match=r"is connected to top level nodes 0, \?\?\?"):
        verify_ir_is_closed(module)


def test_debug_ir_indirect_node_summary_edgecase() -> None:

    t_op = t.TestOp(result_types=[i1])
    module = ModuleOp([t_op])
    t.TestOp(operands=t_op.res)
    t.TestOp(operands=t_op.res)

    with pytest.raises(ValueError, match=r"is connected to top level nodes (\d, )\?\?\?"):
        verify_ir_is_closed(module, exit_early=True)


def test_debug_ir_valid_example() -> None:

    module = ModuleOp([t_op1 := t.TestOp(result_types=[i1]), t_op2 := t.TestOp(operands=t_op1.res)])
    block1 = Block(arg_types=[i1, i1])
    block1.add_op(t.TestOp(operands=t_op1.res))
    block1.add_op(t.TestOp(operands=block1.args))
    block1.add_op(t_op3 := t.TestOp(result_types=[i1]))
    block1.add_op(t.TestTermOp(operands=block1.args))
    block2 = Block(arg_types=[i1])
    block2.add_op(t.TestTermOp(operands=(*t_op3.res, *block2.args)))
    region = Region([block1, block2])
    module.body.block.add_op(t.TestTermOp(operands=t_op2.res, regions=[region]))

    verify_ir_is_closed(module)


EXPECTED_ERROR_STRING = """Not all connected IR nodes share the same top level node.
SSAValue %0 is defined within top level node 1
SSAValue %1 is defined within top level node 2
SSAValue %2 is used within top level nodes 1, 3
Block ^bb0 is defined within top level node 4
Block ^bb1 is defined within top level node 3

====================================================================================================

Top Level Node 0 - Operation:
"builtin.module"() ({
^^^^^^^^^^^^^^^^------------------
| Connection checking started here
----------------------------------
  %2 = "test.termop"(%0, %1) [^bb0, ^bb1] : (i1, i1) -> i1
  ^^^^^^^^^^^^^^^^^^-----------------------------------
  | Operand at index 0 is connected to top level node 1
  -----------------------------------------------------
  ^^^^^^^^^^^^^^^^^^-----------------------------------
  | Operand at index 1 is connected to top level node 2
  -----------------------------------------------------
  ^^^^^^^^^^^^^^^^^^--------------------------------------
  | Result at index 0 is connected to top level nodes 1, 3
  --------------------------------------------------------
  ^^^^^^^^^^^^^^^^^^-------------------------------------
  | Successor at index 0 is connected to top level node 4
  -------------------------------------------------------
  ^^^^^^^^^^^^^^^^^^-------------------------------------
  | Successor at index 1 is connected to top level node 3
  -------------------------------------------------------
^bb2:
  "test.termop"(%2) : (i1) -> ()
}) : () -> ()

====================================================================================================

Top Level Node 1 - Operation:
%0 = "test.op"() ({
^^^^^^^^^^^^^^---------------------------------------
| Result at index 0 is connected to top level nodes 0
-----------------------------------------------------
  "test.op"(%2, %1) : (i1, i1) -> ()
  ^^^^^^^^^--------------------------------------------
  | Operand at index 1 is connected to top level node 2
  -----------------------------------------------------
  ^^^^^^^^^--------------------------------------------
  | Operand at index 0 is connected to top level node 0
  -----------------------------------------------------
}) : () -> i1

====================================================================================================

Top Level Node 2 - Operation:
%1 = "test.op"() : () -> i1
^^^^^^^^^^^^^^------------------------------------------
| Result at index 0 is connected to top level nodes 0, 1
--------------------------------------------------------

====================================================================================================

Top Level Node 3 - Region:
{
  "test.termop"() [^bb1] : () -> ()
  "test.op"(%2) : (i1) -> ()
  ^^^^^^^^^--------------------------------------------
  | Operand at index 0 is connected to top level node 0
  -----------------------------------------------------
}

====================================================================================================

Top Level Node 4 - Block:

^bb0:

===================================================================================================="""


def test_debug_ir_multiple_issues() -> None:

    block1 = Block()
    t_op1 = t.TestOp(result_types=[i1], regions=(Region([block1]),))
    t_op2 = t.TestOp(result_types=[i1])
    Region([block2 := Block()])
    block2.add_op(t.TestTermOp(successors=(block2,)))

    module = ModuleOp(
        Region(
            [
                Block(
                    [
                        t_op3 := t.TestTermOp(
                            operands=(*t_op1.res, *t_op2.res),
                            successors=(Block(), block2),
                            result_types=[i1],
                        )
                    ]
                ),
                Block(
                    [
                        t.TestTermOp(
                            operands=t_op3.res,
                        )
                    ]
                ),
            ]
        )
    )
    block1.add_op(t.TestOp(operands=(*t_op3.res, *t_op2.res)))
    block2.add_op(t.TestOp(operands=t_op3.res))
    with pytest.raises(ValueError, match=re.escape(EXPECTED_ERROR_STRING)):
        verify_ir_is_closed(module, exit_early=False)
