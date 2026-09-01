from __future__ import annotations

from typing import overload

import pytest
from typing_extensions import override
from xdsl.dialects import test as _test
from xdsl.dialects.builtin import NoneAttr, NoneType
from xdsl.ir import Attribute, SSAValue

from deltakit_compile.frontend.common._builder import (
    BaseAPIObject,
    IndexedAPIObject,
    OperationBuilder,
    ParentRegInformation,
    TerminalIndexedAPIObject,
    all_objects_managed_by_same_builder,
    find_duplicated_identifiers,
)
from deltakit_compile.frontend.common._exceptions import InvalidSizeError, ObjectNotAttachedError
from tests.unit.frontend.conftest import add_to_builder_with_fake_ssa, number_of_operations


class _APIObject(BaseAPIObject):
    @property
    @override
    def _identifier_prefix(self) -> str:
        return "test"

    @property
    @override
    def _type_info(self) -> Attribute:
        return NoneType()


class _APIObjectWithState(BaseAPIObject):
    def __init__(self) -> None:
        super().__init__()
        self.state = "I am state!"
        self.list = ["A", "nice", "list", "of", "things."]

    @property
    @override
    def _identifier_prefix(self) -> str:
        return "test"

    @property
    @override
    def _type_info(self) -> Attribute:
        return NoneType()


def test_default_api_builder_object_type_info_raises() -> None:
    class _APIObjectNoTypeInfoOverride(BaseAPIObject):
        @property
        @override
        def _identifier_prefix(self) -> str:
            return "test"

    builder = OperationBuilder()
    with pytest.raises(NotImplementedError):
        builder.append_argument(_APIObjectNoTypeInfoOverride())


def test_unattached_api_builder_object_raises() -> None:
    unattached = _APIObject()

    with pytest.raises(ObjectNotAttachedError):
        _ = unattached._builder
    with pytest.raises(ObjectNotAttachedError):
        _ = unattached.identifier
    with pytest.raises(ObjectNotAttachedError):
        _ = unattached.ssa


def test_api_builder_object_eq() -> None:
    unattached = _APIObject()
    assert unattached == _APIObject()

    builder = OperationBuilder()
    attached = builder.append_argument(_APIObject())
    assert attached != unattached


def test_api_builder_object_hash() -> None:
    unattached = _APIObject()
    assert hash(unattached) == hash(_APIObject())


def test_builder_initialisation() -> None:
    builder = OperationBuilder()
    assert len(builder.arguments) == 0
    assert len(builder.returns) == 0
    assert builder.num_arguments == 0
    assert builder.block.is_empty


def test_builder_append_argument() -> None:
    builder = OperationBuilder()
    obj = builder.append_argument(_APIObject())
    assert obj._is_attached
    assert obj.ssa
    assert len(builder.block.args) == 1
    assert len(builder.arguments) == 1


def test_builder_append_return() -> None:
    builder = OperationBuilder()
    obj = builder.append_argument(_APIObject())
    builder.append_return(obj)
    assert len(builder.returns) == 1


def test_builder_add_without_ssa() -> None:
    builder = OperationBuilder()
    obj = add_to_builder_with_fake_ssa(builder, _APIObject())
    assert obj._is_attached
    assert len(builder.arguments) == 0
    assert len(builder.returns) == 0
    assert (
        number_of_operations(builder, should_be_removed=lambda op: isinstance(op, _test.TestOp))
        == 0
    )


def test_builder_is_managing() -> None:
    builder = OperationBuilder()
    obj = add_to_builder_with_fake_ssa(builder, _APIObject())
    assert builder.is_managing(obj)
    assert not builder.is_managing(_APIObject())

    arg = builder.append_argument(_APIObject())
    assert builder.is_managing(arg)


def test_builder_managed_objects() -> None:
    builder = OperationBuilder()
    assert builder.managed_objects == ()

    arg = builder.append_argument(_APIObject())
    with_ssa = add_to_builder_with_fake_ssa(builder, _APIObject())
    without_ssa = builder.add_without_ssa(_APIObject())

    # Objects are reported in the order in which they have been attached.
    assert builder.managed_objects == (arg, with_ssa, without_ssa)
    # Objects attached to a child builder are not reported by its parent.
    child = builder.get_child_builder()
    child_object = child.add_without_ssa(_APIObject())
    assert builder.managed_objects == (arg, with_ssa, without_ssa)
    assert child.managed_objects == (child_object,)


def test_owns_ssa() -> None:
    builder = OperationBuilder()

    assert not _APIObject()._owns_ssa
    assert builder.append_argument(_APIObject())._owns_ssa
    assert add_to_builder_with_fake_ssa(builder, _APIObject())._owns_ssa
    # API-only objects are attached without any SSA value.
    assert not builder.add_without_ssa(_APIObject())._owns_ssa


def test_builder_append_op_and_update_ssas() -> None:
    builder = OperationBuilder()
    arg = builder.append_argument(_APIObject())
    arg2 = builder.append_op_and_update_ssas(_test.TestOp(result_types=[NoneType()]), arg)

    assert arg2._is_attached
    assert arg2._ssa is not None
    assert len(builder.block.ops) == 1
    assert len(list(builder.all_managed_objects_of_type(_APIObject))) == 2

    arg3, arg4 = builder.append_op_and_update_ssas(
        _test.TestOp([arg2.ssa], [NoneAttr(), NoneAttr()]), [arg2, _APIObject()]
    )
    assert arg3 is arg2
    assert arg3._is_attached
    assert arg3._ssa is not None
    assert arg4._is_attached
    assert arg4._ssa is not None

    with pytest.raises(InvalidSizeError):
        _ = builder.append_op_and_update_ssas(
            _test.TestOp([arg4.ssa], [NoneAttr(), NoneAttr()]), [_APIObject()]
        )


def test_all_objects_managed_by_same_builder() -> None:
    builder = OperationBuilder()
    other_builder = OperationBuilder()

    a = builder.append_argument(_APIObject())
    b = other_builder.append_argument(_APIObject())

    assert all_objects_managed_by_same_builder([a, a, a])
    assert all_objects_managed_by_same_builder([b, b, b])
    assert all_objects_managed_by_same_builder([])
    assert not all_objects_managed_by_same_builder([a, b])
    assert not all_objects_managed_by_same_builder([_APIObject(), b])
    assert not all_objects_managed_by_same_builder([_APIObject(), _APIObject()])


def test_duplicated_identifiers() -> None:
    builder = OperationBuilder()

    a = builder.append_argument(_APIObject())
    b = builder.append_argument(_APIObject())

    assert not find_duplicated_identifiers([a, b])
    assert len(find_duplicated_identifiers([a, b, b])) == 1
    assert len(find_duplicated_identifiers([a, b, b, a])) == 2


def test_unattached_deepcopy() -> None:
    unattached = _APIObject()
    assert unattached._get_unattached_deepcopy() == unattached

    builder = OperationBuilder()

    attached_without_ssa = builder.add_without_ssa(_APIObject())
    assert attached_without_ssa._is_attached
    assert not attached_without_ssa._get_unattached_deepcopy()._is_attached

    attached_with_ssa = add_to_builder_with_fake_ssa(builder, _APIObject())
    assert attached_with_ssa._is_attached
    assert attached_with_ssa._ssa is not None
    cpy = attached_with_ssa._get_unattached_deepcopy()
    assert not cpy._is_attached
    assert cpy._ssa is None

    attached_with_ssa_and_state = add_to_builder_with_fake_ssa(builder, _APIObjectWithState())
    assert attached_with_ssa_and_state._is_attached
    assert attached_with_ssa_and_state._ssa is not None
    cpy_state = attached_with_ssa_and_state._get_unattached_deepcopy()
    assert cpy_state.list == attached_with_ssa_and_state.list
    assert cpy_state.state == attached_with_ssa_and_state.state
    assert not cpy_state._is_attached
    assert cpy_state._ssa is None


class _AtomicIndexAPIObject(TerminalIndexedAPIObject["_RegIndexAPIObject"]):
    @override
    def __len__(self) -> int:
        return 1

    @property
    @override
    def _identifier_prefix(self) -> str:
        return "atom"

    @property
    @override
    def ssa(self) -> SSAValue:
        raise NotImplementedError()


class _RegIndexAPIObject(IndexedAPIObject["_RegIndexAPIObject"]):
    def __init__(
        self,
        name: str = "<empty>",
        *,
        _parent_information: ParentRegInformation[_RegIndexAPIObject] | None = None,
    ) -> None:
        super().__init__(_parent_information=_parent_information)
        self._name = name

    @override
    def __eq__(self, value: object) -> bool:
        if not isinstance(value, _RegIndexAPIObject):
            return NotImplemented
        return self._name == value._name and super().__eq__(value)

    @override
    def __len__(self) -> int:
        return 100

    @property
    @override
    def _identifier_prefix(self) -> str:
        return "reg"

    @overload
    def __getitem__(self, index: int) -> _AtomicIndexAPIObject: ...
    @overload
    def __getitem__(self, index: slice) -> _RegIndexAPIObject: ...
    def __getitem__(self, index: int | slice) -> _AtomicIndexAPIObject | _RegIndexAPIObject:
        return (
            _AtomicIndexAPIObject(_parent_information=ParentRegInformation(self, index))
            if isinstance(index, int)
            else _RegIndexAPIObject(
                f"{self._name}[{index}]", _parent_information=ParentRegInformation(self, index)
            )
        )

    def __hash__(self) -> int:
        return 0


@pytest.mark.parametrize("type_", [_AtomicIndexAPIObject, _RegIndexAPIObject])
def test_self_source(type_: type[_AtomicIndexAPIObject | _RegIndexAPIObject]) -> None:
    atomic = type_()
    assert atomic.source is atomic


def test_indexed_api_object_parent() -> None:
    reg0 = _RegIndexAPIObject()
    reg1 = reg0[::2]
    obj2 = reg1[3]
    assert obj2.parent is reg1
    assert reg1.parent is reg0
    assert reg0.parent is None


def test_indexed_api_object_index() -> None:
    reg0 = _RegIndexAPIObject()
    reg1 = reg0[::2]
    obj2 = reg1[3]
    assert obj2.index == 3
    assert reg1.index == slice(None, None, 2)
    assert reg0.index is None


def test_indexed_api_object_is_root_parent() -> None:
    reg0 = _RegIndexAPIObject()
    reg1 = reg0[::2]
    assert not reg1.is_root_parent
    assert reg0.is_root_parent


def test_indexed_api_object_has_ancestors() -> None:
    reg0 = _RegIndexAPIObject()
    reg1 = reg0[::2]
    assert reg1.has_ancestor(reg0)
    assert not reg0.has_ancestor(reg0)
    assert not reg0.has_ancestor(reg1)


def test_nested_object_source() -> None:
    reg = _RegIndexAPIObject()
    reg2 = reg[::2][1:]
    atomic = reg2[:6][0]
    assert reg2.source is reg
    assert atomic.source is reg


def test_nested_object_index() -> None:
    reg = _RegIndexAPIObject()
    reg2 = reg[::2][1:]
    reg2_index = reg2[3].resolve_index()
    assert reg2_index == tuple(range(len(reg)))[::2][1:][3]

    atomic = reg2[:6][0]
    atomic_index = atomic.resolve_index()
    assert atomic_index == 2


def test_get_index_from_sequence() -> None:
    lhs, rhs = _RegIndexAPIObject("lhs"), _RegIndexAPIObject("rhs")
    sequence = [lhs, _AtomicIndexAPIObject(), rhs]
    assert IndexedAPIObject.get_object_index_in_sequence(sequence, lhs[0]) == 0
    assert IndexedAPIObject.get_object_index_in_sequence(sequence, lhs[82]) == 82
    assert IndexedAPIObject.get_object_index_in_sequence(sequence, rhs[0]) == 101
    assert IndexedAPIObject.get_object_index_in_sequence(sequence, rhs[35]) == 136
    assert (
        IndexedAPIObject.get_object_index_in_sequence(sequence, _RegIndexAPIObject("other")[3])
        is None
    )
