from collections.abc import Callable
from typing import TypeVar

from xdsl.dialects import test
from xdsl.ir import Block, Operation

from deltakit_compile.frontend.common._builder import BaseAPIObject, OperationBuilder

_BaseAPIObject = TypeVar("_BaseAPIObject", bound=BaseAPIObject)


def add_to_builder_with_fake_ssa(
    builder: OperationBuilder, value: _BaseAPIObject
) -> _BaseAPIObject:
    op = test.TestOp(result_types=[value._type_info])
    return builder.append_op_and_update_ssas(op, value)


def number_of_operations(
    builder: OperationBuilder, should_be_removed: Callable[[Operation], bool] = lambda _: False
) -> int:
    return sum(1 for op in builder.block.ops if not should_be_removed(op))


def number_of_operations_of_type_in_block(
    block: Block, types_to_count: type[Operation] | tuple[type[Operation], ...]
) -> int:
    return sum(1 for op in block.ops if isinstance(op, types_to_count))
