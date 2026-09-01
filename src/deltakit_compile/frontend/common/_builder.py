# (c) Copyright Riverlane 2025-2026. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Collection, Iterable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Final, Generic, TypeGuard, TypeVar, cast, overload

from typing_extensions import Self, override
from xdsl.dialects.builtin import DYNAMIC_INDEX, TensorType
from xdsl.ir import Attribute, Block, Operation, Region, SSAValue
from xdsl.irdl import base

from deltakit_compile.dialects import func, log_asm_api, logical_assembly, qcore
from deltakit_compile.frontend.common._exceptions import (
    IdentifierConflictError,
    InvalidSizeError,
    ObjectNotAttachedError,
)
from deltakit_compile.frontend.common._identifiers import IdentifiersGenerator


class BaseAPIObject(ABC):
    """Represents an object that may have a parent builder, identifier and SSA value.

    Instances of this class may be used to track in which context an object was created and to
    check that the instance is used in the correct context (i.e., with the right builder). They are
    supposed to be user-facing instances that store all the information needed to add the required
    operations to the parent builder.
    """

    def __init__(self) -> None:
        self._parent_builder: OperationBuilder | None = None
        self._internal_identifier: str | None = None
        self._ssa: SSAValue | None = None

    @property
    @abstractmethod
    def _identifier_prefix(self) -> str:
        """Returns the prefix that will be used for generating identifiers for instances of this
        class."""

    @property
    def _type_info(self) -> Attribute:
        """Returns the prefix that will be used for generating identifiers for instances of this
        class."""
        msg = type(self).__name__ + "._type_info"
        raise NotImplementedError(msg)

    def _attach(self, builder: OperationBuilder, identifier: str) -> None:
        """Attach this object to a builder instance.

        Args:
            builder: the builder to attach this object to.
            identifier: an identifier that should be assigned to this object.
        """
        self._parent_builder = builder
        self._internal_identifier = identifier

    @property
    def _is_attached(self) -> bool:
        """Return ``True`` if ``self`` is managed by a ``OperationBuilder`` instance.

        Returns:
            ``True`` if ``self`` has been attached to a valid builder, else ``False``.
        """
        return self._parent_builder is not None

    @property
    def _builder(self) -> OperationBuilder:
        if self._parent_builder is None:
            raise ObjectNotAttachedError()
        return self._parent_builder

    @property
    def identifier(self) -> str:
        if self._internal_identifier is None:
            raise ObjectNotAttachedError()
        return self._internal_identifier

    @property
    def ssa(self) -> SSAValue:
        if self._ssa is None:
            raise ObjectNotAttachedError()
        return self._ssa

    @property
    def _owns_ssa(self) -> bool:
        """Return ``True`` if ``self`` directly owns an SSA value.

        Objects owning an SSA value are the ones attached with
        :meth:`OperationBuilder.append_op_and_update_ssas` (or one of its variants), meaning that
        their SSA value is defined by an operation stored in their builder. The other objects are
        either API-only (e.g., ``MeasurementRecord``) or lazily re-derive their SSA value from their
        source (e.g., the object returned by ``reg[0]``).
        """
        return self._ssa is not None

    def _update_ssa_value(self, ssa: SSAValue) -> None:
        self._ssa = ssa

    @override
    def __eq__(self, other: object, /) -> bool:
        return (
            isinstance(other, BaseAPIObject)
            and self._internal_identifier == other._internal_identifier
            and self._parent_builder is other._parent_builder
            and self._ssa == other._ssa
        )

    @override
    def __hash__(self) -> int:
        return hash(self._internal_identifier)

    def _get_unattached_deepcopy(self) -> Self:
        """Return a unattached deepcopy of ``self``.

        This method is used when a fresh copy of a :class:`.BaseAPIObject` is needed, for example
        when creating new :class:`.BaseAPIObject` instances to return after calling a subroutine.
        """
        cls = self.__class__
        result = cls.__new__(cls)
        for k, v in self.__dict__.items():
            value: Any
            if k in ["_parent_builder", "_internal_identifier", "_ssa"]:
                value = None
            else:
                value = deepcopy(v)
            setattr(result, k, value)
        return result


_BaseAPIObjectType = TypeVar("_BaseAPIObjectType", bound=BaseAPIObject)
_BaseAPITupleObjectType = TypeVar("_BaseAPITupleObjectType", bound=tuple[BaseAPIObject, ...])
_BaseAPISequenceObjectType = TypeVar("_BaseAPISequenceObjectType", bound=Sequence[BaseAPIObject])


class OperationBuilder:
    """A convenience class to store xDSL operations and interface them nicely with identifiers of
    the API.

    This class keeps the different API objects synchronised with the internal operations that are
    being stored. In particular, it updates the internal objects' stored SSA value to reflect the
    current state of each object.
    """

    def __init__(self, *, _parent: OperationBuilder | None = None) -> None:
        self._parent = _parent
        self._id_generator = IdentifiersGenerator()
        self._managed_objects: dict[str, BaseAPIObject] = {}
        self._region = Region(Block([]))
        self._input_arguments: list[BaseAPIObject] = []
        """The API objects used as arguments. These objects are mutable, so the actual input type is
        stored in the corresponding block argument of `self._region.block`, and these API objects
        can be used to inspect any changes in the type during the the life of the builder."""
        self._return_values: list[BaseAPIObject] = []

    # region Builder interface

    def add_without_ssa(self, obj: _BaseAPIObjectType) -> _BaseAPIObjectType:
        """Add a new object to the managed objects.

        The added object will be attached to ``self``, but no SSA value will be attached to it. This
        method is used for types that are API-only and are never represented in the IR (e.g.,
        ``MeasurementRecord``).

        Args:
            obj: an object to add to this builder. The provided object will become attached to
                ``self`` and will be given an identifier.

        Returns:
            The provided ``obj`` instance, now attached to ``self``.
        """
        new_identifier = self._id_generator.new_identifier(obj)
        obj._attach(self, new_identifier)
        self._managed_objects[new_identifier] = obj
        return obj

    def _add_to_managed_objects(self, obj: _BaseAPIObjectType, ssa: SSAValue) -> _BaseAPIObjectType:
        """Add a new object to the list of managed objects.

        Args:
            obj: an object to add to this builder. The provided object will become attached to
                ``self`` and will be given an identifier.
            ssa: the SSA value that will be attached to the provided ``obj``.

        Returns:
            The provided ``obj`` instance, now attached to ``self`` and with a reference to the
            provided ``ssa`` value.
        """
        obj = self.add_without_ssa(obj)
        if ssa.name_hint is None:
            ssa.name_hint = obj.identifier
        obj._update_ssa_value(ssa)
        return obj

    def is_managing(self, obj: BaseAPIObject) -> bool:
        """Check if ``self`` manages the provided object.

        Most operations on managed objects require them to be managed by a manager instance.

        Args:
            obj: instance to check.

        Returns:
            ``True`` if ``self`` is managing ``obj``, else ``False``.
        """
        return obj._is_attached and obj._builder is self

    def has_in_scope(self, obj: BaseAPIObject) -> bool:
        """Check if ``self`` or one of its parent manages the provided object.

        Most operations on managed objects require them to be managed by a manager instance.

        Args:
            obj: instance to check.

        Returns:
            ``True`` if ``self`` or one of its parent is managing ``obj``, else ``False``.
        """
        return (obj._is_attached and obj._builder is self) or (
            self._parent is not None and self._parent.has_in_scope(obj)
        )

    # endregion

    # region Getters

    @property
    def has_parent(self) -> bool:
        return self._parent is not None

    @property
    def parent(self) -> OperationBuilder | None:
        return self._parent

    @property
    def block(self) -> Block:
        return self._region.block

    @property
    def region(self) -> Region:
        return self._region

    @property
    def arguments(self) -> tuple[BaseAPIObject, ...]:
        return tuple(self._input_arguments)

    @property
    def returns(self) -> tuple[BaseAPIObject, ...]:
        return tuple(self._return_values)

    @property
    def managed_objects(self) -> tuple[BaseAPIObject, ...]:
        """All the objects attached to ``self``, in the order in which they have been attached."""
        return tuple(self._managed_objects.values())

    def all_managed_objects_of_type(
        self, type_: type[_BaseAPIObjectType]
    ) -> Iterable[_BaseAPIObjectType]:
        """Return an iterable over all managed objects of the given type.

        Args:
            type_: type of objects that should be returned. Check is done using ``isinstance``, so
                children types are also returned.

        Returns:
            An iterable over all managed objects of the given type.
        """

        def _filter(obj: BaseAPIObject) -> TypeGuard[_BaseAPIObjectType]:
            return isinstance(obj, type_)

        return filter(_filter, self._managed_objects.values())

    @property
    def last_op(self) -> Operation | None:
        return self.block.last_op

    def get_child_builder(self) -> OperationBuilder:
        """Return a new builder that "inherits" from self."""
        return OperationBuilder(_parent=self)

    # region Argument declaration

    @property
    def num_arguments(self) -> int:
        """Get the number of arguments declared in this builder."""
        return len(self.block.args)

    def append_argument(self, argument: _BaseAPIObjectType) -> _BaseAPIObjectType:
        """Add a new argument to the builder.

        Args:
            argument: a builder object that will be attached to ``self`` and initialised to be
                usable in other methods of ``self``.

        Returns:
            the provided ``argument`` correctly attached to ``self`` and with a new SSA value.
        """
        pos = self.num_arguments
        self.block.insert_arg(argument._type_info, pos)
        self._add_to_managed_objects(argument, ssa=self.block.args[pos])
        self._input_arguments.append(argument)
        return argument

    # endregion

    # region Return value declaration

    def append_return(self, value: BaseAPIObject) -> None:
        """Declare the SSA value associated to the provided ``value`` as a returned value."""
        self._return_values.append(value)

    # endregion

    # region Adding operations

    @overload
    def append_op_and_update_ssas(
        self, op: Operation, outputs: _BaseAPIObjectType
    ) -> _BaseAPIObjectType: ...
    @overload
    def append_op_and_update_ssas(
        self, op: Operation, outputs: _BaseAPITupleObjectType
    ) -> _BaseAPITupleObjectType: ...
    @overload
    def append_op_and_update_ssas(
        self, op: Operation, outputs: _BaseAPISequenceObjectType
    ) -> _BaseAPISequenceObjectType: ...
    @overload
    def append_op_and_update_ssas(self, op: Operation) -> tuple[()]: ...
    def append_op_and_update_ssas(
        self, op: Operation, outputs: Sequence[_BaseAPIObjectType] | _BaseAPIObjectType = ()
    ) -> Sequence[_BaseAPIObjectType] | _BaseAPIObjectType:
        """Append an xDSL operation and set the output SSA values to the provided objects.

        This is one of the main method of ``OperationBuilder``. It allows to add a new operation to
        the builder and update the Python API objects with the SSA values returned by that
        operation.

        Warning:
            This method modifies the objects in ``outputs`` in-place by setting their ``ssa``
            attribute to a new value.

        Args:
            op: a valid xDSL operation to add to the builder.
            outputs: a sequence of builder objects that will be updated with the SSA values returned
                by ``op``. The number of provided objects in this argument should match the number
                of returned SSA values by ``op``.

        Raises:
            InvalidSizeError: if ``op`` returns ``n`` SSA values but ``m != n`` objects are provided
                in ``outputs``.

        Returns:
            The objects provided in ``outputs``, with an updated SSA value.
        """
        return self.append_ops_and_update_ssas((op,), op.results, outputs)

    @overload
    def append_ops_and_update_ssas(
        self, ops: Iterable[Operation], ssa_values: Sequence[SSAValue], outputs: _BaseAPIObjectType
    ) -> _BaseAPIObjectType: ...
    @overload
    def append_ops_and_update_ssas(
        self,
        ops: Iterable[Operation],
        ssa_values: Sequence[SSAValue],
        outputs: _BaseAPITupleObjectType,
    ) -> _BaseAPITupleObjectType: ...
    @overload
    def append_ops_and_update_ssas(
        self,
        ops: Iterable[Operation],
        ssa_values: Sequence[SSAValue],
        outputs: _BaseAPISequenceObjectType,
    ) -> _BaseAPISequenceObjectType: ...
    @overload
    def append_ops_and_update_ssas(self, ops: Iterable[Operation]) -> tuple[()]: ...
    def append_ops_and_update_ssas(
        self,
        ops: Iterable[Operation],
        ssa_values: Sequence[SSAValue] = (),
        outputs: Sequence[_BaseAPIObjectType] | _BaseAPIObjectType = (),
    ) -> Sequence[_BaseAPIObjectType] | _BaseAPIObjectType:
        """Append xDSL operations and set the given SSA values to the provided objects.

        This is one of the main method of ``OperationBuilder``. It allows new operations to be
        added to the builder and update the Python API objects with new SSA values.

        Warning:
            This method modifies the objects in ``outputs`` in-place by setting their ``ssa``
            attribute to a new value.

        Args:
            ops: A sequence of valid xDSL operations to add to the builder.
            ssa_values: A sequence of values to use to update the given Python API objects. These
                are normally the results of the ops.
            outputs: A sequence of builder objects that will be updated with the ssa values from
                ``ssa_values``. The number of provided objects in this argument should match the
                length of ``ssa_values``.

        Raises:
            InvalidSizeError: If the number of ssa values and outputs given are not the same.

        Returns:
            The objects provided in ``outputs``, with an updated SSA value.
        """
        return_single: bool = False
        if isinstance(outputs, BaseAPIObject):
            outputs = (outputs,)
            return_single = True
        if len(ssa_values) != len(outputs):
            msg = f"Expected {len(outputs)} results but {len(ssa_values)} results were given."
            raise InvalidSizeError(msg)
        for op in ops:
            self.append_ops_ignoring_ssas(op)
        for obj, ssa in zip(outputs, ssa_values, strict=True):
            self._add_to_managed_objects(obj, ssa)
        return outputs if not return_single else cast(_BaseAPIObjectType, outputs[0])

    def append_ops_ignoring_ssas(self, *ops: Operation) -> None:
        """Append the provided operations without updating any SSA value in Python objects.

        This method should typically be used for operations that are only taking references instead
        of re-creating new SSA values.

        It might also be used when the operation returns SSA values, but these values are never
        represented in the API (e.g., the SSA value returned by a ``arith.const`` operation that
        will be used as an index in ``tensor.extract``).

        Args:
            *ops: valid xDSL operations to add to the builder.
        """
        self.block.add_ops(ops)


def all_objects_managed_by_same_builder(objs: Collection[BaseAPIObject]) -> bool:
    """Returns ``True`` if all the provided objects are managed by the same builder.

    Args:
        objs: an arbitrary sequence of ``BuilderObject``.

    Returns:
        ``True`` if all the objects in ``obj`` are managed by the same builder. Note that an empty
        ``objs`` would return true, just like ``all([])`` is returning ``True`` in standard
        Python.
    """
    # If there is no object, return True
    if not objs:
        return True
    # If any of the provided object is not attached, return False.
    if any(not obj._is_attached for obj in objs):
        return False
    # If they are all attached to the same builder, return True. Else False.
    objs_iter = iter(objs)
    builder = next(objs_iter)._builder
    return all(obj._builder is builder for obj in objs_iter)


def find_duplicated_identifiers(objs: Collection[BaseAPIObject]) -> set[str]:
    """Find duplicated identifiers in the sequence of given objects.

    This function returns a collection of identifiers that are duplicated in the provided ``objs``.

    Two objects with the same identifier are considered equal if they both are managed by the same
    builder. This function does not check that second condition, which can be checked by
    :meth:`.all_objects_managed_by_same_builder`.

    Args:
        objs: an arbitrary sequence of ``BuilderObject``.

    Returns:
        a collection of duplicated identifiers.
    """
    counter = Counter(obj.identifier for obj in objs)
    return {k for k, v in counter.items() if v > 1}


OperationT = TypeVar("OperationT", bound=Operation)

CALLABLE_TYPE_TO_NAME_MAP: Final[dict[type, str]] = {
    func.FuncOp: "subroutine",
    log_asm_api.CircuitDeclarationOp: "circuit",
}


@dataclass
class SubCallablesBuilder(Generic[OperationT]):
    """Stores a map from identifiers to callable Operations and provides methods to add new
    callables safely and helpers to implement callable caller methods in builders."""

    builder_name: str
    _callables: dict[str, OperationT] = field(default_factory=dict)

    @property
    def callables(self) -> Mapping[str, OperationT]:
        return self._callables

    @staticmethod
    def is_quantum_type(attr: Attribute) -> bool:
        """Return True iff attr is a TypeAttribute for a quantum type that should be treated as pass
        by reference when calling."""
        return (
            base(logical_assembly.SurfaceCodeBasePatch)
            | TensorType.constr(qcore.QubitType())
            | base(qcore.QubitRegType)
            | base(qcore.QubitType)
        ).verifies(attr)

    def add_callable(
        self,
        identifier: str,
        declaration: OperationT,
        used_subcallables: Mapping[str, OperationT],
    ) -> None:
        """Add a new callable and its dependant callables to the ``callables`` mapping, checking
        that none of them already have conflicting definitions.

        Args:
            identifier: identifier of the callable operation to add.
            declaration: operation declaring the callable.
            used_subcallables: a read-only mapping from callable identifiers to their declaration
                operation containing callables used internally in ``declaration``.

        Raises:
            IdentifierConflictError: if any callable identifier clashes, i.e., two subroutines
                with the same identifier have a different declaration.
        """
        existing_declaration = self._callables.get(identifier)
        if existing_declaration is not None and not existing_declaration.is_structurally_equivalent(
            declaration
        ):
            dec_name = CALLABLE_TYPE_TO_NAME_MAP.get(type(declaration), "callable")
            existing_name = CALLABLE_TYPE_TO_NAME_MAP.get(type(existing_declaration), "callable")
            msg = (
                f"Could not call the {dec_name} with identifier '{identifier}': a different "
                f"{existing_name} with the same identifier has already been used and the two "
                "different definitions would clash."
            )
            raise IdentifierConflictError(msg)
        common_identifiers = self._callables.keys() & used_subcallables.keys()
        for common_identifier in common_identifiers:
            if not self._callables[common_identifier].is_structurally_equivalent(
                used_subcallables[common_identifier]
            ):
                dec_name = CALLABLE_TYPE_TO_NAME_MAP.get(type(declaration), "callable")
                msg = (
                    f"Could not call the {dec_name} with identifier '{identifier}' because it "
                    f"uses a declaration for '{common_identifier}' that does not match with the "
                    f"declaration already present in the {self.builder_name} currently being built."
                )
                raise IdentifierConflictError(msg)
        if existing_declaration is None:
            self._callables[identifier] = declaration.clone()
            for dec_name, subroutine in used_subcallables.items():
                if dec_name in common_identifiers:
                    continue
                self._callables[dec_name] = subroutine.clone()

    def coerce_operand_from_arg(
        self,
        arg: SSAValue,
        expected_type: Attribute,
        *,
        op_list: list[log_asm_api.CastOp],
        callable_ident: str = "callable",
    ) -> SSAValue:
        """Attempt to cast the argument into the expected type returning the ssa value for the
        argument, which will be either ``arg`` or the result of casting.
        All cast operations needed are appended to the ``op_list`` argument in-place."""
        arg_type = arg.type
        # No casting needed
        if expected_type == arg_type:
            return arg
        # cast tensor<nx!E> to tensor<?x!E>
        if (
            isinstance(expected_type, TensorType)
            and isinstance(arg_type, TensorType)
            and expected_type.element_type == arg_type.element_type
            and expected_type.get_shape() == (DYNAMIC_INDEX,)
            and len(arg_type.get_shape()) == 1
        ):
            op_list.append(cast_op := log_asm_api.CastOp(arg, expected_type))
            return cast_op.result
        # cast qcore.qubit_reg<n> to tensor<?x!qcore.qubit> or tensor<nx!qcore.qubit>
        if (
            isinstance(expected_type, TensorType)
            and isinstance(arg_type, qcore.QubitRegType)
            and expected_type.element_type == qcore.QubitType()
            and len(expected_type.get_shape()) == 1
            and expected_type.get_shape()[0] in (DYNAMIC_INDEX, arg_type.size.data)
        ):
            op_list.append(cast_op := log_asm_api.CastOp(arg, expected_type))
            return cast_op.result
        # cast log_asm.patch.rot_planar<...> to tensor<?x!qcore.qubit> or tensor<nx!qcore.qubit>
        if (
            isinstance(expected_type, TensorType)
            and isinstance(arg_type, logical_assembly.SurfaceCodeBasePatch)
            and expected_type.element_type == qcore.QubitType()
            and len(expected_type.get_shape()) == 1
            and expected_type.get_shape()[0] in (DYNAMIC_INDEX, arg_type.num_qubits)
        ):
            op_list.append(cast_op := log_asm_api.CastOp(arg, expected_type))
            return cast_op.result
        msg = (
            f"Cannot call {callable_ident} with expression of type {arg_type}, "
            f"expected a {expected_type}"
        )
        raise TypeError(msg)

    def coerce_arg_from_result(
        self,
        res: SSAValue,
        expected_type: Attribute,
        *,
        op_list: list[log_asm_api.CastOp],
    ) -> SSAValue:
        """Attempt to cast the result back into the expected arg type returning the ssa value for
        the result, which will be either ``res`` or the result of casting.
        All cast operations needed are appended to the ``op_list`` argument in-place."""
        res_type = res.type
        # No casting needed
        if expected_type == res_type:
            return res
        # cast tensor<?x!E> to tensor<nx!E>
        if (
            isinstance(res_type, TensorType)
            and isinstance(expected_type, TensorType)
            and expected_type.element_type == res_type.element_type
            and res_type.get_shape() == (DYNAMIC_INDEX,)
            and len(expected_type.get_shape()) == 1
        ):
            op_list.append(cast_op := log_asm_api.CastOp(res, expected_type))
            return cast_op.result
        # cast tensor<?x!qcore.qubit> or tensor<nx!qcore.qubit> to qcore.qubit_reg<n>
        if (
            isinstance(res_type, TensorType)
            and isinstance(expected_type, qcore.QubitRegType)
            and res_type.element_type == qcore.QubitType()
            and len(res_type.get_shape()) == 1
            and res_type.get_shape()[0] in (DYNAMIC_INDEX, expected_type.size.data)
        ):
            op_list.append(cast_op := log_asm_api.CastOp(res, expected_type))
            return cast_op.result
        # cast tensor<?x!qcore.qubit> or tensor<nx!qcore.qubit> to log_asm.patch.rot_planar<...>
        if (
            isinstance(res_type, TensorType)
            and isinstance(expected_type, logical_assembly.SurfaceCodeBasePatch)
            and res_type.element_type == qcore.QubitType()
            and len(res_type.get_shape()) == 1
            and res_type.get_shape()[0] in (DYNAMIC_INDEX, expected_type.num_qubits)
        ):
            op_list.append(cast_op := log_asm_api.CastOp(res, expected_type))
            return cast_op.result
        # Allow changing the patch type without casting
        if (
            isinstance(res_type, logical_assembly.SurfaceCodeBasePatch)
            and isinstance(expected_type, logical_assembly.SurfaceCodeBasePatch)
            and type(res_type) is type(expected_type)
        ):
            return res

        msg = (
            f"Cannot reconcile pass-by-reference quantum argument/result of type {res_type} with "
            f"variable of type {expected_type}"
        )
        raise TypeError(msg)

    def recast_quantum_results(
        self,
        args: Sequence[BaseAPIObject],
        returned_ssas: Sequence[SSAValue],
    ) -> tuple[Sequence[log_asm_api.CastOp], list[BaseAPIObject], list[SSAValue]]:
        """Filter arguments and returned ssa values for quantum types, then match them up and cast
        to the argument type where necessary. Return the required casting ops, the quantum argument
        API Objects that should be updated to new results, and the new results."""
        quantum_args = [arg for arg in args if self.is_quantum_type(arg.ssa.type)]
        quantum_results = [res for res in returned_ssas if self.is_quantum_type(res.type)]
        if len(quantum_args) != len(quantum_results):
            msg = (
                "The number of quantum arguments and quantum results do no match. "
                "Cannot implement pass by reference on these values."
            )
            raise ValueError(msg)

        if not quantum_args:
            return ((), quantum_args, quantum_results)

        ops: list[log_asm_api.CastOp] = []
        for res_idx, qarg in enumerate(quantum_args):
            new_res = self.coerce_arg_from_result(
                quantum_results[res_idx], qarg.ssa.type, op_list=ops
            )
            quantum_results[res_idx] = new_res
        return ops, quantum_args, quantum_results


ParentAPIObjectType = TypeVar("ParentAPIObjectType", bound="IndexedAPIObject")


@dataclass(frozen=True)
class ParentRegInformation(Generic[ParentAPIObjectType]):
    """Store information on how a given object has been obtained through indexing.

    Attributes:
        parent: the source object that has been indexed to get the object this instance refers to.
        index: the index used to index ``parent`` in order to obtain the object this instance refers
            to.
    """

    parent: ParentAPIObjectType
    index: int | slice


class IndexedAPIObject(BaseAPIObject, ABC, Generic[ParentAPIObjectType]):
    """Base class for any ``BaseAPIObject`` that can be obtained by indexing another
    ``BaseAPIObject`` instance.

    This base class should be used for registers and bits/qubits as these can be obtained by
    indexing a register. It provides convenience methods to retrieve the source of the object and
    its corresponding index.

    Args:
        _parent_information: internal-only argument that should be provided when the object is
            obtained through an indexing.
    """

    def __init__(
        self, *, _parent_information: ParentRegInformation[ParentAPIObjectType] | None = None
    ) -> None:
        super().__init__()
        self._parent_information = _parent_information

    @property
    def ancestors(self: Self) -> list[ParentAPIObjectType]:
        current: ParentAPIObjectType | Self = self
        ancestors: list[ParentAPIObjectType] = []
        while current._parent_information is not None:
            current = current._parent_information.parent
            ancestors.append(current)
        return ancestors

    @property
    def source(self) -> ParentAPIObjectType | Self:
        ancestors = self.ancestors
        return ancestors[-1] if ancestors else self

    @property
    def parent(self) -> ParentAPIObjectType | None:
        """Direct parent of ``self`` or ``None`` if ``self`` has no parent."""
        if self._parent_information is None:
            return None
        return self._parent_information.parent

    @property
    def index(self) -> slice | int | None:
        """Index used on ``self.parent`` to obtain ``self``, ``None`` if ``self`` has no parent."""
        if self._parent_information is None:
            return None
        return self._parent_information.index

    @property
    def is_root_parent(self) -> bool:
        """``True`` if ``self`` has no parent, else ``False``."""
        return self._parent_information is None

    @abstractmethod
    def __len__(self) -> int: ...

    @staticmethod
    def get_object_index_in_sequence(
        sequence: Sequence[IndexedAPIObject], obj: TerminalIndexedAPIObject
    ) -> int | None:
        """Find the index in the register formed by the concatenation of ``sequence`` to recover
        ``obj``.

        Args:
            sequence: A sequence of registers or atomic objects that is interpreted as a unique
                register of atomic objects.
            obj: the atomic object in ``sequence`` to find the index of.

        Returns:
            The position of ``obj`` in the provided ``sequence`` when it is seen as a unique
            register obtained by concatenating all the elements in ``sequence`` if ``obj`` has been
            found in ``sequence``, else ``None``.
        """
        source = obj.source
        index_in_source = obj.resolve_index() or 0
        index_offset: int = 0
        for arg in sequence:
            if arg == source:
                return index_in_source + index_offset
            index_offset += len(arg)
        return None

    def has_ancestor(self, obj: IndexedAPIObject) -> bool:
        return obj in self.ancestors


class TerminalIndexedAPIObject(IndexedAPIObject[ParentAPIObjectType]):
    """Base class for API objects that can be obtained from an ``IndexedAPIObject`` but are not
    indexable any more.

    Classes like ``Qubit`` or ``MeasurementBit`` will inherit from this class.

    It enforces that the ``ssa`` property should be re-implemented to take into account the fact
    that the SSA value should only be produced when needed, and not at object construction.
    """

    @override
    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, TerminalIndexedAPIObject):
            return NotImplemented
        if self.is_root_parent or value.is_root_parent:
            return super().__eq__(value)
        # If both have a parent, compare the qubits according to their source and index to avoid
        # false negatives here.
        return self.source == value.source and self.resolve_index() == value.resolve_index()

    @override
    def __hash__(self) -> int:
        return (
            super().__hash__() if self.is_root_parent else hash((self.source, self.resolve_index()))
        )

    @property
    @abstractmethod
    @override
    def ssa(self) -> SSAValue:
        return super().ssa

    def resolve_index(self: Self) -> int | None:
        """Compute the index needed to recover ``self`` directly from its root source.

        ``IndexedAPIObject`` instances form a forest where each tree root is an object without
        parent (i.e., not obtained by indexing an existing object). This method find the index that
        can be used to index the root of tree ``self`` belongs to to recover ``self``.

        Returns:
            The index that can be used to index the root of the tree ``self`` belongs to to recover
            ``self`` or ``None`` if ``self`` is the root of the tree.
        """
        if self.is_root_parent:
            return None

        source: ParentAPIObjectType | Self = self
        all_indices: list[int | slice] = []
        while (parent := source._parent_information) is not None:
            all_indices.append(parent.index)
            source = parent.parent

        assert all_indices, "Expected at least one index because self has a parent."
        if not isinstance(i_final := all_indices[0], int):
            msg = f"Cannot resolve the index of {self} as it appear to not be a single qubit."
            raise RuntimeError(msg)
        assert all(isinstance(idx, slice) for idx in all_indices[1:]), (
            "All indices (except potentially the last one) should be slice instances."
        )

        all_slices = cast(list[slice], all_indices[1:])
        # Compose all slices as an affine map (outermost first), then evaluate at i_final.
        # A slice s maps position j in its result to position (s.start + j * s.step) in its parent,
        # so composing slices yields offset + j * step for some (offset, step).
        # We do not have to care about the stop here because unsized registers are treated as
        # infinite size in the API (i.e., any index is valid) and sized registers should have
        # already checked that the stop index was valid.
        offset, step = 0, 1
        for s in reversed(all_slices):
            offset += (s.start or 0) * step
            step *= s.step or 1
        return offset + i_final * step
