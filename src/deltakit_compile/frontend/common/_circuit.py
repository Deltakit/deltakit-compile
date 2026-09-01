# (c) Copyright Riverlane 2025-2026. All rights reserved.
from __future__ import annotations

import functools
from collections.abc import Collection, Generator, Iterable, Mapping, Sequence
from contextlib import contextmanager
from enum import Enum, auto
from io import StringIO
from typing import (
    Any,
    Generic,
    ParamSpec,
    TypeAlias,
    TypeGuard,
    TypeVar,
    cast,
    overload,
)

from typing_extensions import override
from xdsl.dialects.builtin import IntegerAttr, IntegerType, ModuleOp, TensorType, UnitAttr, i1
from xdsl.ir import Attribute, Block, Region, SSAValue
from xdsl.printer import Printer
from xdsl.traits import SymbolTable

from deltakit_compile.dialects import qstruct, tensor
from deltakit_compile.dialects.log_asm_api import (
    LOCKSTEP_PARALLEL_ATTRIBUTE,
    CallOp,
    CastOp,
    CircuitDeclarationOp,
    ReturnOp,
    UnsizedGateOp,
    UnsizedResetOp,
)
from deltakit_compile.dialects.qcore import (
    GateAttribute,
    PauliAttr,
    PauliStringAttr,
    QubitType,
)
from deltakit_compile.dialects.qec import (
    DecObservableOp,
    DetectorOp,
    DetectorRoundOp,
    MeasurementRoundOp,
)
from deltakit_compile.dialects.qref import MeasureOp
from deltakit_compile.dialects.qstruct import AlignmentAttr
from deltakit_compile.dialects.sobs import DecObservableOp as SobsDecObservableOp
from deltakit_compile.dialects.stabiliser import ConcreteFlowArrayAttr, ConcreteFlowAttr
from deltakit_compile.frontend.common._annotations import Detector, Observable
from deltakit_compile.frontend.common._builder import (
    BaseAPIObject,
    IndexedAPIObject,
    OperationBuilder,
    SubCallablesBuilder,
    all_objects_managed_by_same_builder,
    find_duplicated_identifiers,
)
from deltakit_compile.frontend.common._classical_expr import ClassicalExpression
from deltakit_compile.frontend.common._exceptions import (
    ArgumentError,
    ArgumentSizeError,
    ArgumentTypeMismatchError,
    DifferentBuildersError,
    DuplicatedIdentifiersError,
    EmptyRoundError,
    IdentifierConflictError,
    InvalidSizeError,
    ObjectNotAttachedError,
    UnsupportedArgumentTypeError,
    UnsupportedReturnTypeError,
)
from deltakit_compile.frontend.common._gates import GATE_MAPPING, RESET_MAPPING
from deltakit_compile.frontend.common._measurements import (
    MeasurementBit,
    MeasurementRecord,
    MeasurementReg,
)
from deltakit_compile.frontend.common._pauli import Pauli, PauliFlow, PauliString, PauliType
from deltakit_compile.frontend.common._qubit_reg import Qubit, QubitReg
from deltakit_compile.frontend.common._sequence import does_not_contain_none_values, is_sequence
from deltakit_compile.frontend.common._vector import Vector, VectorLike

CircuitArgType: TypeAlias = Qubit | QubitReg | ClassicalExpression | MeasurementReg | Observable
CircuitRetType: TypeAlias = ClassicalExpression | MeasurementBit | MeasurementReg | Observable

_CircuitArgType = TypeVar("_CircuitArgType", bound=CircuitArgType)
_CircuitRetType = TypeVar("_CircuitRetType", bound=CircuitRetType)

P = ParamSpec("P")
CircuitResultsType: TypeAlias = CircuitRetType | tuple[CircuitRetType, ...] | None
CircuitOutputType = TypeVar("CircuitOutputType", bound=CircuitResultsType)


@overload
def _is_circuit_argument_sequence(value: list[Any]) -> TypeGuard[list[CircuitArgType]]: ...
@overload
def _is_circuit_argument_sequence(
    value: tuple[Any, ...],
) -> TypeGuard[tuple[CircuitArgType, ...]]: ...
def _is_circuit_argument_sequence(value: Sequence[Any]) -> TypeGuard[Sequence[CircuitArgType]]:
    return all(isinstance(v, CircuitArgType) for v in value)


@overload
def _is_circuit_return_sequence(value: list[Any]) -> TypeGuard[list[CircuitRetType]]: ...
@overload
def _is_circuit_return_sequence(
    value: tuple[Any, ...],
) -> TypeGuard[tuple[CircuitRetType, ...]]: ...
def _is_circuit_return_sequence(value: Sequence[Any]) -> TypeGuard[Sequence[CircuitRetType]]:
    return all(isinstance(v, CircuitRetType) for v in value)


class InstantiatedCircuit(Generic[P, CircuitOutputType]):
    """
    A wrapper to represent a ``Circuit`` instance that has been instantiated with specific inputs.

    The only way to produce an instance of this class is to call ``Circuit.__call__``.

    Arguments:
        module: a ``builtin.module`` operation containing a ``log_asm_api.circuit_dec`` operation
            named by ``entry_point_identifier`` and also containing all the circuits it depends on.
            This is specifically the same ``builtin.module`` operation instance from the
            ``Circuit``.
        entry_point_identifier: The name of the entry point circuit declaration in ``module``
        results: Python type of the results returned by the instantiated ``Circuit``.
        *args: SSA values corresponding to the input arguments of the circuit wrapped into a
            circuit API type. This is used to check what the user provides when calling
            ``Circuit.__call__`` in order to create an ``InstantiatedCircuit``.
        **kwargs: an empty collection. This will raise if any kwargs is provided.
    """

    def __init__(
        self,
        module: ModuleOp,
        entry_point_identifier: str,
        results: CircuitOutputType,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        assert not kwargs, "Should be guaranteed by caller."
        assert all(isinstance(outer, CircuitArgType) for outer in args)
        assert not find_duplicated_identifiers(cast(Collection[CircuitArgType], args))

        self._module = module
        self._entry_point_identifier = entry_point_identifier
        self._results = results
        self._outer_arguments = tuple[CircuitArgType, ...](cast(Iterable[CircuitArgType], args))

    @property
    def module(self) -> ModuleOp:
        return self._module

    @property
    def entry_point_identifier(self) -> str:
        return self._entry_point_identifier

    @property
    def results(self) -> CircuitOutputType:
        return self._results

    @property
    def arguments(self) -> tuple[CircuitArgType, ...]:
        return self._outer_arguments

    @functools.cached_property
    def declaration_op(self) -> CircuitDeclarationOp:
        op = SymbolTable.lookup_symbol(self.module, self.entry_point_identifier)
        assert isinstance(op, CircuitDeclarationOp)
        return op

    @functools.cached_property
    def called_circuits(self) -> Mapping[str, CircuitDeclarationOp]:
        return {
            op.sym_name.data: op
            for op in self.module.ops
            if isinstance(op, CircuitDeclarationOp)
            and op.sym_name.data != self.entry_point_identifier
        }

    @property
    def identifier(self) -> str:
        return self.entry_point_identifier

    @property
    def results_tuple(self) -> tuple[CircuitRetType, ...]:
        if self.results is None:
            return ()
        if isinstance(self.results, CircuitRetType):
            return (self.results,)
        return self.results


class Circuit(Generic[P, CircuitOutputType]):
    """
    A user-defined low-level sub-routine that can be called in a ``LogASM`` context.

    This class is not designed to be instantiated directly. Instances of this class can be obtained
    by calling ``CircuitBuilder.build(...)``.

    The ``Circuit`` class represents a LogASM-compatible sub-routine implemented using low-level
    instructions that are not directly accessible at the LogASM abstraction level. Think LogASM
    as being the C language and Circuit being the inline assembly that may be needed to
    implement very specific operations not possible through the high-level C API.

    Args:
        module: A ModuleOp containing a ``log_asm_api.circuit_dec`` operation named by
            ``entry_point_identifier``, as well as all the other circuits it depends on.
        entry_point_identifier: The name of the entry point circuit declaration in ``module``
        result_type: return type of the ``Circuit`` instance.
        *args: SSA values corresponding to the input arguments of the circuit wrapped into a
            circuit API type. This is used to check what the user provides when calling
            ``Circuit.__call__`` in order to create an ``InstantiatedCircuit``.
        **kwargs: an empty collection. This will raise if any kwargs is provided.

    Raises:
        InvalidSizeError: if the provided ``block`` does not contain exactly one operation.
        RuntimeError: if the provided ``block`` contains exactly one operation but it is not a
            ``qstruct.CircuitOp``.
    """

    def __init__(
        self,
        module: ModuleOp,
        entry_point_identifier: str,
        result_type: CircuitOutputType,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        if kwargs:
            kwargs_keys = ", ".join(f"'{k}'" for k in kwargs)
            msg = (
                f"Cannot instantiate a {Circuit.__name__} with keyword arguments (kwargs). "
                f"The following keyword arguments were found: {kwargs_keys}."
            )
            raise RuntimeError(msg)
        if not _is_circuit_argument_sequence(args):
            sargs = ", ".join(map(str, args))
            msg = f"The provided arguments '({sargs})' contains at least one invalid argument type."
            raise ArgumentError(msg)
        self._arguments = args
        self._module = module
        self._entry_point_identifier = entry_point_identifier
        self._result_type = result_type

    def __call__(
        self, *args: P.args, **kwargs: P.kwargs
    ) -> InstantiatedCircuit[P, CircuitOutputType]:
        """Instantiate the represented ``Circuit`` with explicit inputs.

        This method is the only way to produce ``InstantiatedCircuit`` instances which can then be
        re-used in a LogASM program.

        Args:
            *args: an arbitrary number of inputs to give to the represented circuit. The number and
                order of provided inputs should exactly match the number and order of arguments
                required by the circuit.
            **kwargs: an empty collection. This will raise if any keyword argument are provided.

        Returns:
            an immutable representation of the ``Circuit`` when applied to the provided inputs that
            can then be re-used in a LogASM context.

        Raises:
            ArgumentSizeError: if the number of provided arguments does not match the expected
                number of arguments.
            ArgumentTypeMismatchError: if any of the provided argument is not of the expected type.
            RuntimeError: if ``kwargs`` is not empty.
        """
        if kwargs:
            kwargs_keys = ", ".join(f"'{k}'" for k in kwargs)
            msg = (
                f"Cannot call a {Circuit.__name__} with keyword arguments (kwargs). "
                f"The following keyword arguments were found: {kwargs_keys}."
            )
            raise RuntimeError(msg)
        if len(args) != len(self._arguments):
            raise ArgumentSizeError(expected=len(self._arguments), provided=len(args))
        if not all(isinstance(v, CircuitArgType) for v in args):
            sargs = ", ".join(map(str, args))
            msg = f"The provided arguments '({sargs})' contains at least one invalid argument type."
            raise ArgumentError(msg)
        assert _is_circuit_argument_sequence(self._arguments), "Checked in __init__."

        for i, (arg, expected_type) in enumerate(zip(args, self._arguments, strict=True)):
            if not isinstance(arg, type(expected_type)):
                raise ArgumentTypeMismatchError(
                    argument_position=i, expected_type=type(expected_type), provided_type=type(arg)
                )
        return InstantiatedCircuit[P, CircuitOutputType](
            self._module, self._entry_point_identifier, self._result_type, *args, **kwargs
        )

    @override
    def __str__(self) -> str:
        res = StringIO()
        printer = Printer(stream=res)
        printer.print_string(f"{type(self).__name__}('{self._entry_point_identifier}' ")

        declaration_op = SymbolTable.lookup_symbol(self._module, self._entry_point_identifier)
        assert isinstance(declaration_op, CircuitDeclarationOp)
        subcircuits = {
            op.sym_name.data: op
            for op in self._module.ops
            if isinstance(op, CircuitDeclarationOp)
            and op.sym_name.data != self._entry_point_identifier
        }
        # Rely on the block args and yield to show the contents of self.arguments and self.results
        # without having to print them directly
        printer.print_region(declaration_op.body)
        if (flows_attr := declaration_op.attributes.get(ConcreteFlowArrayAttr.KEY)) is not None:
            assert isinstance(flows_attr, ConcreteFlowArrayAttr)
            num_flows = len(flows_attr.flows)
            printer.print_string(" with flows ")
            with printer.in_braces():
                with printer.indented():
                    printer.print_string("\n")
                    for i, flow in enumerate(flows_attr.flows.data):
                        flow.print_concrete_flow_attr(printer)
                        if i != num_flows - 1:
                            printer.print_string(",")
                            printer.print_string("\n")
                printer.print_string("\n")
        if subcircuits:
            printer.print_string(" which calls ")
            with printer.in_braces():
                with printer.indented():
                    for i, (name, op) in enumerate(subcircuits.items()):
                        if i:
                            printer.print_string(",")
                        printer.print_string(f"\n'{name}' ")
                        printer.print_region(op.body)
                printer.print_string("\n")
        printer.print_string(")")
        return res.getvalue()


class ParallelAlignment(Enum):
    """Defines the possible alignments in parallel blocks.

    Attributes:
        TOP: Parallel operations/circuits start at the same time.
        BOTTOM: Parallel operations/circuits end at the same time.
        LOCKSTEP: The contents of parallel circuits are aligned operation-by-operation.
    """

    TOP = auto()
    BOTTOM = auto()
    LOCKSTEP = auto()


class ParallelScope:
    def __init__(self, circ_builder: CircuitBuilder, align: ParallelAlignment) -> None:
        self._circ_builder = circ_builder
        self._alignment = align
        self._regions: list[Region] = []
        self._results: list[BaseAPIObject] = []
        self._views: list[BaseAPIObject] = []

    @property
    def alignment(self) -> ParallelAlignment:
        """Alignment used in this parallel."""
        return self._alignment

    @property
    def regions(self) -> tuple[Region, ...]:
        return tuple(self._regions)

    @property
    def results(self) -> tuple[BaseAPIObject, ...]:
        return tuple(self._results)

    @property
    def result_types(self) -> tuple[Attribute, ...]:
        return tuple(res._type_info for res in self._results)

    @contextmanager
    def __call__(self) -> Generator[None]:
        """Create a parallel region within a parallel."""
        outer_builder = self._circ_builder._builder
        inner_builder = outer_builder.get_child_builder()
        self._circ_builder._builder = inner_builder
        try:
            yield
        finally:
            # We add the necessary yield operations to the region, and store it.
            escaping = _escaping_objects(inner_builder)
            yield_op = qstruct.YieldOp(*(obj.ssa for obj in escaping))
            block = inner_builder.region.detach_block(0)
            block.add_op(yield_op)
            self._regions.append(Region(block))
            # ``inner_builder`` is discarded here, so everything it manages is transferred to the
            # enclosing builder by ``CircuitBuilder.parallel``, once the results exist.
            self._results.extend(escaping)
            self._views.extend(_views_to_reattach(inner_builder, escaping))
            # Returns declared within the region are returns of the circuit, so we hand them over.
            for ret in inner_builder.returns:
                outer_builder.append_return(ret)
            # And restore the state of the builder.
            self._circ_builder._builder = outer_builder

    def _reattach_views(self, outer_builder: OperationBuilder) -> None:
        """Transfer the objects that do not own an SSA value to ``outer_builder``.

        These objects re-derive their SSA value from their source on demand (e.g., ``reg[0]``), so
        they are valid again once their source has been remapped to a result of the parallel. They
        still need re-attaching so that the operations they lazily create go to the right block.

        Args:
            outer_builder: the builder enclosing the parallel operation.
        """
        for view in self._views:
            source = view.source if isinstance(view, IndexedAPIObject) else view
            if source is not view and not outer_builder.has_in_scope(source):
                # The source did not escape, so ``view`` cannot be resolved any more. Leaving it on
                # the discarded builder makes any further use of it raise.
                continue
            outer_builder.add_without_ssa(view)


def _escaping_objects(region_builder: OperationBuilder) -> list[BaseAPIObject]:
    """Return the objects of ``region_builder`` that must escape its region through a yield.

    Only objects owning an SSA value can escape, and only valid circuit results are worth escaping:
    qubits are passed by reference, so the temporary registers created to apply an operation (see
    ``CircuitBuilder._as_qubit_register``) never need to leave their region.

    Every candidate is yielded, even ones only used within the region (e.g., the bits backing the
    register returned by ``CircuitBuilder.measure``), as whether the user still holds a reference
    cannot be known here. Unused results are removed by the canonicalisation of the parallel.

    Args:
        region_builder: the builder holding the operations of a single parallel region.

    Returns:
        The objects to yield out of the region, in the order in which they were created.
    """
    escaping: list[BaseAPIObject] = []
    seen_ids: set[int] = set()
    for obj in region_builder.managed_objects:
        if id(obj) in seen_ids or not obj._owns_ssa or not isinstance(obj, CircuitRetType):
            continue
        seen_ids.add(id(obj))
        escaping.append(obj)
    return escaping


def _views_to_reattach(
    region_builder: OperationBuilder, escaping: Sequence[BaseAPIObject]
) -> list[BaseAPIObject]:
    """Return non-SSA-owning objects worth re-attaching after a parallel region.

    Indexed objects can only be resolved after the region if their root source escaped it. API-only
    objects (e.g., ``MeasurementRecord``) are still transferred as they can hold user-managed
    state even without an SSA value.
    """
    escaped_sources = {
        id(obj.source) if isinstance(obj, IndexedAPIObject) else id(obj) for obj in escaping
    }
    views: list[BaseAPIObject] = []
    seen_ids: set[int] = set()
    for obj in region_builder.managed_objects:
        if id(obj) in seen_ids or obj._owns_ssa:
            continue
        if isinstance(obj, IndexedAPIObject) and id(obj.source) not in escaped_sources:
            continue
        seen_ids.add(id(obj))
        views.append(obj)
    return views


class CircuitBuilder:
    """Builder interface to construct low-level circuits.

    Circuits are always used within a LogASM context and should be seen as low-level code that is
    not representable using the higher-level LogASM interface. A good analogy would be to see the
    LogASM interface as C-level programming and the Circuit interface as inline assembly in the C
    program.
    """

    def __init__(self) -> None:
        # Internal-only attributes.
        self._builder = OperationBuilder()
        self._called = SubCallablesBuilder[CircuitDeclarationOp]("circuit")
        self._flows: list[PauliFlow] = []

    # region Private helper methods
    def _check_all_are_in_scope(self, objs: BaseAPIObject | Iterable[BaseAPIObject]) -> None:
        if isinstance(objs, BaseAPIObject):
            objs = [objs]
        for obj in objs:
            if not obj._is_attached:
                raise ObjectNotAttachedError()
            if not self._builder.has_in_scope(obj):
                msg = (
                    f"Object {obj.identifier} is not attached to the correct builder. Objects "
                    "need to be given to CircuitBuilder.add_arg before being used."
                )
                raise DifferentBuildersError(msg)

    # region Arguments and returns

    def add_arg(self, arg: _CircuitArgType) -> _CircuitArgType:
        """Declares a new input argument for the circuit being built.

        Args:
            arg: A patch, ``QubitReg``, ``Observable``, or classical argument for the circuit.

        Raises:
            UnsupportedArgumentTypeError: if the provided argument type is not supported.
            InvalidSizeError: if the provided argument is an unsized register of qubits and the
                circuit being built has already been annotated with some flows.
        Returns:
            The instances provided as input that can now be used in other methods of the circuit
            builder.
        """
        if not isinstance(arg, CircuitArgType):
            raise UnsupportedArgumentTypeError(type(arg))
        if isinstance(arg, QubitReg) and arg.is_unsized and self._flows:
            msg = (
                "Flow annotations and unsized registers are incompatible. Cannot add an unsized "
                "register as argument to a circuit that already contains some flow annotation."
            )
            raise InvalidSizeError(msg)
        return self._builder.append_argument(arg)

    def _check_return_value(self, value: Any) -> None:
        """Check that the provided ``value`` can be registered as a return value of ``self``."""
        if not isinstance(value, CircuitRetType):
            raise UnsupportedReturnTypeError(type(value))
        if value._builder is not self._builder:
            msg = "Cannot add as return a value that is managed by another builder."
            raise DifferentBuildersError(msg)

    @overload
    def add_return(self, value: _CircuitRetType) -> _CircuitRetType: ...
    @overload
    def add_return(self, value: Sequence[_CircuitRetType]) -> tuple[_CircuitRetType, ...]: ...
    def add_return(
        self, value: _CircuitRetType | Sequence[_CircuitRetType]
    ) -> _CircuitRetType | tuple[_CircuitRetType, ...]:
        """Register the provided object, or objects, as returned value(s).

        Args:
            value: either a single object, or a sequence of objects, that will be registered as
                return value(s) of the circuit currently being built. Sequences are accepted so
                that the results of ``call_circuit``, which are tuples when the callee returns
                several values, can be forwarded directly.

        Raises:
            UnsupportedReturnTypeError: if the provided ``value``, or any of the values it contains,
                is not an instance of supported return types.
            DifferentBuildersError: if the provided ``value``, or any of the values it contains, has
                been created by another builder.

        Returns:
            The provided ``value``, as a convenience. A sequence input is returned as a tuple.
        """
        if isinstance(value, CircuitRetType):
            self._check_return_value(value)
            self._builder.append_return(value)
            return value
        if not is_sequence(value):
            raise UnsupportedReturnTypeError(type(value))
        values = tuple(value)
        # Check everything before appending anything to avoid registering only part of the provided
        # values if one of them is invalid (i.e. if the error is caught somewhere).
        for val in values:
            self._check_return_value(val)
        for val in values:
            self._builder.append_return(val)
        return values

    @property
    def _has_unsized_arguments(self) -> bool:
        return any(isinstance(arg, QubitReg) and arg.is_unsized for arg in self._builder.arguments)

    # region Applying operations

    def _as_qubit_register(self, value: Qubit | QubitReg | Sequence[Qubit]) -> QubitReg:
        if isinstance(value, QubitReg):
            return value
        if isinstance(value, Qubit):
            return self._builder.append_op_and_update_ssas(
                tensor.FromElementsOp(value.ssa, result_type=TensorType(QubitType(), (1,))),
                QubitReg(1, [value.location] if value.location is not None else None),
            )
        locations = [qubit.location for qubit in value]
        return self._builder.append_op_and_update_ssas(
            tensor.FromElementsOp(
                *[qubit.ssa for qubit in value],
                result_type=TensorType(QubitType(), (len(value),)),
            ),
            QubitReg(len(value), locations if does_not_contain_none_values(locations) else None),
        )

    @classmethod
    def _get_gate_or_reset_attribute(cls, name: str) -> GateAttribute | PauliAttr:
        if name in RESET_MAPPING:
            return RESET_MAPPING[name]
        if name in GATE_MAPPING:
            return GATE_MAPPING[name]

        msg = f"Gate '{name}' is not yet supported."
        raise IndexError(msg)

    def gate(self, gate: str, operand: Qubit | QubitReg | Sequence[Qubit]) -> None:
        """Apply the provided gate (where reset is also considered a type of gate) to the provided
        register of qubits.

        Args:
            gate: the quantum gate to apply to the provided ``register``.
            operand: a representation of the qubits the provided ``gate`` should be applied to.

        Raises:
            InvalidSizeError: if ``register`` is an empty sequence.
        """
        # Check that we got a valid input
        if is_sequence(operand) and not operand:
            msg = "Cannot apply gate on empty operand."
            raise InvalidSizeError(msg)
        self._check_all_are_in_scope(operand)
        qreg = self._as_qubit_register(operand)

        attr = self._get_gate_or_reset_attribute(gate)
        # Note that the below operations are equivalent to `qref.reset`` or ``qref.gate``, which do
        # not return a new SSA value, so there is no need to update ``operand.ssa``.
        self._builder.append_ops_ignoring_ssas(
            UnsizedResetOp(attr, qreg.ssa)
            if isinstance(attr, PauliAttr)
            else UnsizedGateOp(attr, qreg.ssa)
        )

    @overload
    def measure(
        self,
        basis: PauliType,
        operand: QubitReg | Sequence[Qubit],
    ) -> MeasurementReg: ...
    @overload
    def measure(
        self,
        basis: PauliType,
        operand: Qubit,
    ) -> MeasurementBit: ...
    def measure(
        self,
        basis: PauliType,
        operand: Qubit | QubitReg | Sequence[Qubit],
    ) -> MeasurementBit | MeasurementReg:
        """Measures provided qubits in the provided ``basis``.

        Args:
            basis: basis in which to measure all the qubits in the provided ``operand``.
            operand: a representation of the qubits that should be measured in the provided
                ``basis``.

        Raises:
            InvalidSizeError: if the provided operand is unsized or empty.

        Returns:
            An object representing the measurement result.
        """
        basis = basis.to_qcore_attr() if isinstance(basis, Pauli) else PauliAttr.coerce(basis)
        if isinstance(operand, Sequence) and not operand:
            msg = "Cannot apply measurement on empty register."
            raise InvalidSizeError(msg)
        if isinstance(operand, QubitReg) and operand.num_qubits is None:
            msg = "Cannot measure an unsized register."
            raise InvalidSizeError(msg)
        self._check_all_are_in_scope(operand)
        # Simple case for a single qubit input
        if isinstance(operand, Qubit):
            return self._builder.append_op_and_update_ssas(
                MeasureOp(basis, [operand.ssa]), MeasurementBit()
            )
        # Else, we handle the operand as a sequence of qubits
        if isinstance(operand, QubitReg):
            operand = [operand[i] for i in range(len(operand))]

        op = MeasureOp(basis, [qubit.ssa for qubit in operand])
        num_qubits = len(operand)
        results = self._builder.append_op_and_update_ssas(
            op, [MeasurementBit() for _ in range(num_qubits)]
        )
        tensor_op = tensor.FromElementsOp(
            *[res.ssa for res in results], result_type=TensorType(i1, (num_qubits,))
        )
        return self._builder.append_op_and_update_ssas(tensor_op, MeasurementReg(num_qubits))

    @overload
    def mpp(
        self, basis: Sequence[PauliType], operand: QubitReg | Sequence[Qubit]
    ) -> MeasurementBit | MeasurementReg: ...
    @overload
    def mpp(self, basis: Sequence[PauliType], operand: Qubit) -> MeasurementBit: ...
    def mpp(
        self, basis: Sequence[PauliType], operand: Qubit | QubitReg | Sequence[Qubit]
    ) -> MeasurementBit | MeasurementReg:
        """Measures the provided qubits in the provided Multi Pauli ``basis``.

        Args:
            basis: Multi Pauli basis that all the qubits in the provided ``operand`` will be
                measured in.
            operand: a representation of the qubits that should be measured in the provided
                ``basis``. The number of qubits should be a multiple of the number of bases in
                ``basis``. If the multiple is greater than 1, the measurement will be repeated on
                consecutive chunks of qubits. For example, if the provided operand has 6 qubits and
                the provided basis is of length 2, then the measurement will be performed 3 times:
                once on the first 2 qubits, once on the middle 2 qubits, and once on the last 2
                qubits, leading to 3 measurement results.

        Raises:
            InvalidSizeError: if the provided operand is unsized, empty or not a multiple of the
                number of provided bases.

        Returns:
            An object representing the measurement result. There will be `num_qubits // len(basis)`
            measurement results.
        """
        self._check_all_are_in_scope(operand)
        if isinstance(operand, Sequence) and not operand:
            msg = "Cannot apply measurement on empty register."
            raise InvalidSizeError(msg)
        if isinstance(operand, QubitReg) and operand.num_qubits is None:
            msg = "Cannot measure an unsized register."
            raise InvalidSizeError(msg)

        if isinstance(operand, QubitReg):
            operand = [operand[i] for i in range(len(operand))]

        # Simple case for a single bit output
        if isinstance(operand, Qubit) or len(operand) == len(basis):
            operand_ssas = (
                [operand.ssa] if isinstance(operand, Qubit) else [qubit.ssa for qubit in operand]
            )
            return self._builder.append_op_and_update_ssas(
                MeasureOp(
                    [
                        b.to_qcore_attr() if isinstance(b, Pauli) else PauliAttr.coerce(b)
                        for b in basis
                    ],
                    operand_ssas,
                ),
                MeasurementBit(),
            )

        num_qubits = len(operand)
        if num_qubits % len(basis) != 0:
            msg = (
                f"Number of qubits in the provided register ({num_qubits}) should be a "
                f"multiple of the number of provided bases ({len(basis)})."
            )
            raise InvalidSizeError(msg)
        op = MeasureOp(
            [b.to_qcore_attr() if isinstance(b, Pauli) else PauliAttr.coerce(b) for b in basis],
            [qubit.ssa for qubit in operand],
        )
        num_bits = num_qubits // len(basis)
        results = self._builder.append_op_and_update_ssas(
            op, [MeasurementBit() for _ in range(num_bits)]
        )
        concat_op = tensor.ConcatOp(
            [res.ssa for res in results],
            IntegerAttr.from_index_int_value(0),
            TensorType(IntegerType(1), (num_bits,)),
        )
        return self._builder.append_op_and_update_ssas(concat_op, MeasurementReg(num_bits))

    # region Declaring structures

    def declare_record(self) -> MeasurementRecord:
        """Declares a new measurement record that can then be populated with measurement results.

        Returns:
            A new empty measurement record that can be populated.
        """
        new_record = MeasurementRecord()
        return self._builder.add_without_ssa(new_record)

    def measurement_round(self, *measurements: MeasurementBit | MeasurementReg) -> None:
        """Declares a new measurement round grouping the provided measurements together.

        A measurement round can be used to explicitly hint to the compiler that all the grouped
        measurements are expected to be performed around the same time and should be transferred to
        a decoder as a group.

        By default, the compiler will assume that measurements performed in parallel are part of the
        same measurement round.

        Args:
            *measurements: measurement results that should be added to the round.

        Raises:
            EmptyRoundError: if no measurement is provided.
            DuplicatedIdentifiersError: if the same measurement is provided several times.
        """
        if not measurements:
            round_description = "measurement round"
            raise EmptyRoundError(round_description)
        self._check_all_are_in_scope(measurements)
        # Check that there is no duplicate provided.
        if duplicated_ids := find_duplicated_identifiers(measurements):
            raise DuplicatedIdentifiersError(duplicated_ids)
        self._builder.append_ops_ignoring_ssas(
            MeasurementRoundOp([meas.ssa for meas in measurements])
        )

    def add_flow(
        self,
        input_paulis: Mapping[Qubit, PauliType],
        output_paulis: Mapping[Qubit, PauliType],
        measurements: Iterable[MeasurementBit] | MeasurementReg,
        parity: bool = True,
    ) -> None:
        """Add the provided flow to the list of flows implemented by the built circuit.

        Explicitly declared flows serve two purposes:

        1. They act as a safeguard against most implementation errors, because declared flows can be
           checked against the implemented circuit and any inconsistency can be reported.
        2. They control how detectors will eventually be formed, and so are an indirect way of
           controlling the resulting decoding graph.

        Flow annotations are incompatible with unsized registers, so this method will raise if it is
        called on a circuit builder that has at least one unsized register as argument.

        Args:
            input_paulis: input Pauli string.
            output_paulis: expected output Pauli string when ``input_paulis`` is given as input.
            measurements: raw measurements that are involved in the Pauli flow.
            parity: if ``True``, the flow has a '+' sign. Else, it has a '-' sign.

        Returns:
            The created PauliFlow instance.

        Raises:
            InvalidSizeError: if an unsized register is present in the declared arguments of the
                built circuit.
        """
        self._check_all_are_in_scope(input_paulis.keys())
        self._check_all_are_in_scope(output_paulis.keys())
        self._check_all_are_in_scope(measurements)
        for m in measurements:
            ancestors_and_self = (m, *m.ancestors)
            if any(ret in ancestors_and_self for ret in self._builder.returns):
                continue
            msg = (
                "Measurements used in flow annotations should be marked as returned first by "
                "calling CircuitBuilder.add_return. Found a measurement that was not returned."
            )
            raise RuntimeError(msg)
        if self._has_unsized_arguments:
            msg = "Cannot define flows on circuits with unsized register."
            raise InvalidSizeError(msg)
        self._flows.append(
            PauliFlow(PauliString(input_paulis), PauliString(output_paulis), measurements, parity)
        )

    def add_creation_flow(
        self,
        output_paulis: Mapping[Qubit, PauliType],
        measurements: Iterable[MeasurementBit] | MeasurementReg,
        parity: bool = True,
    ) -> None:
        """Convenience method wrapping ``add_flow`` when the input Pauli string is empty.

        Args:
            output_paulis: expected output Pauli string when ``input_paulis`` is given as input.
            measurements: raw measurements that are involved in the Pauli flow.
            parity: if ``True``, the flow has a '+' sign. Else, it has a '-' sign.

        Returns:
            The created PauliFlow instance.
        """
        self.add_flow({}, output_paulis, measurements, parity)

    def add_destruction_flow(
        self,
        input_paulis: Mapping[Qubit, PauliType],
        measurements: Iterable[MeasurementBit] | MeasurementReg,
        parity: bool = True,
    ) -> None:
        """Convenience method wrapping ``add_flow`` when the output Pauli string is empty.

        Args:
            input_paulis: input Pauli string.
            measurements: raw measurements that are involved in the Pauli flow.
            parity: if ``True``, the flow has a '+' sign. Else, it has a '-' sign.

        Returns:
            The created PauliFlow instance.
        """
        self.add_flow(input_paulis, {}, measurements, parity)

    def detector(
        self,
        measurements: Collection[MeasurementBit],
        coordinates: VectorLike[float] | None = None,
    ) -> Detector:
        """Explicitly declares a new detector and adds it to the circuit.

        The preferred way to build detectors is indirectly, by declaring flows with ``add_flow`` and
        letting the compiler finding the detectors.

        When the above is not possible or not convenient, detectors can be explicitly added to the
        circuit with this method.

        Args:
            measurements: raw measurements whose parity is known to be deterministic in the absence
                of errors.
            coordinates: optional vector of floating-point coordinates that can be used, for
                example, to give a spatial location to the detector.

        Returns:
            A detector instance containing the provided measurements.
        """
        self._check_all_are_in_scope(measurements)
        if coordinates is not None:
            coordinates = Vector.as_vector(coordinates)
        op = DetectorOp([meas.ssa for meas in measurements], coordinates)
        return self._builder.append_op_and_update_ssas(op, Detector(measurements, coordinates))

    @overload
    def detector_round(self, detectors: Detector, *remaining_detectors: Detector) -> None: ...
    @overload
    def detector_round(self, detectors: Collection[Detector]) -> None: ...

    def detector_round(
        self, detectors: Detector | Collection[Detector], *remaining: Detector
    ) -> None:
        """Declares detectors to be part of the same 'round'.

        Instead of manually providing a "time" coordinate and grouping detectors with matching time
        coordinates into rounds, the ``CircuitBuilder`` take an explicit approach of declaring the
        rounds.

        Args:
            detectors: if a single detector is provided, the other detectors that should be part of
                the group should be provided in ``remaining``. Else, ``remaining`` should be empty
                and all the detectors of the group should be provided.
            *remaining: empty when ``detectors`` contains more than a single instance. Else,
                contains the remaining instances that should be considered as part of the group.

        Raises:
            DifferentBuildersError: if the provided detectors are not managed by the same builder.
            DuplicatedIdentifiersError: if duplicated detectors are found.
            EmptyRoundError: if no detectors are provided.
        """
        all_detectors: tuple[Detector, ...] = (
            (detectors, *remaining) if isinstance(detectors, Detector) else tuple(detectors)
        )
        if not all_detectors:
            round_description = "detector round"
            raise EmptyRoundError(round_description)
        # Check that all the provided detectors are managed by the same builder
        if not all_objects_managed_by_same_builder(all_detectors):
            msg = "All the detectors in a detector round should be managed by the same builder."
            raise DifferentBuildersError(msg)
        # Check that there is no duplicate provided.
        if dups := find_duplicated_identifiers(all_detectors):
            raise DuplicatedIdentifiersError(dups)
        self._builder.append_ops_ignoring_ssas(DetectorRoundOp([det.ssa for det in all_detectors]))

    def declare_observable(self, qubits: QubitReg | Sequence[Qubit] | None = None) -> Observable:
        """Declares a new observable that is supported on the provided qubits.

        Args:
            qubits: optional qubits the observable should be supported on. If provided, the returned
                observable will need to be updated by calling ``move``. Else, it will need to be
                updated using ``include``.

        Returns:
            An object representing the newly declared observables.

        Raises:
            NotImplementedError: if ``qubits is not None`` because the ``sobs`` dialect that defines
                the operation we would need is not implemented yet.
        """
        if qubits is not None:
            self._check_all_are_in_scope(qubits)
            if isinstance(qubits, QubitReg):
                if qubits.num_qubits is None:
                    msg = "Cannot declare an observable on a unsized qubit register."
                    raise InvalidSizeError(msg)
                qubits = [qubits[i] for i in range(qubits.num_qubits)]
            return self._builder.append_op_and_update_ssas(
                SobsDecObservableOp([q.ssa for q in qubits]), Observable(qubits)
            )
        # else
        return self._builder.append_op_and_update_ssas(DecObservableOp(), Observable())

    # region Context managers

    @contextmanager
    def repeat(self, num_repetitions: int) -> Generator[None]:
        """Enters in a repeat block.

        This method creates a context manager that will track the operations while the context
        manager lives and, at exit, will add a repeat operation with the appropriate body to the
        currently built circuit.

        Args:
            num_repetitions: a strictly positive number of repetitions for the inner block.

        Raises:
            InvalidSizeError: when the provided ``num_repetitions`` is invalid.
        """
        if num_repetitions < 0:
            msg = f"Cannot have a negative number of repetitions. Got {num_repetitions}."
            raise InvalidSizeError(msg)
        if num_repetitions == 0:
            msg = (
                "Cannot have a number of repetitions equal to 0 as that might create ambiguous "
                "situations."
            )
            raise InvalidSizeError(msg)

        msg = "Features using context-managers ('with ...:') are not yet implemented in the API."
        raise NotImplementedError(msg)
        outer_builder = self._builder
        inner_builder = OperationBuilder()
        self._builder = inner_builder
        try:
            yield
        finally:
            self._builder = outer_builder
        # TODO: Add support for repeat blocks

    @contextmanager
    def parallel(
        self, align: ParallelAlignment = ParallelAlignment.TOP
    ) -> Generator[ParallelScope]:
        """Enters a new parallel.

        This method creates a context manager object that can be called as an inner context manager
        to create a new parallel region. It will track the operations created while the context
        manager lives and, at exit, will add a parallel operation with the appropriate body to the
        currently built circuit.

        Values created within a region (e.g., measurement results) are automatically yielded out of
        it and become usable only after the whole parallel block has been closed (that is, when this
        outer context manager exits).
        Until then, they cannot be used from sibling regions, nor in the gap between two
        ``with p():`` blocks from the same parallel.

        Args:
            align: how parallel operation alignment should be handled.

        Yields:
            An object that can be called as a context manager to create parallel regions.
        """
        parallel_scope = ParallelScope(self, align)
        yield parallel_scope

        alignment: AlignmentAttr
        match align:
            case ParallelAlignment.TOP:
                alignment = AlignmentAttr.TOP()
            case ParallelAlignment.BOTTOM:
                alignment = AlignmentAttr.BOTTOM()
            case ParallelAlignment.LOCKSTEP:
                alignment = AlignmentAttr.TOP()

        parallel_op = qstruct.ParallelOp(
            parallel_scope.result_types, parallel_scope.regions, alignment=alignment
        )
        if align == ParallelAlignment.LOCKSTEP:
            parallel_op.attributes[LOCKSTEP_PARALLEL_ATTRIBUTE] = UnitAttr()

        # Appending the operation re-attaches the yielded objects to ``self._builder`` and remaps
        # their SSA value onto the corresponding result of ``parallel_op``. The objects deriving
        # their SSA value from those can then be re-attached too.
        self._builder.append_op_and_update_ssas(
            parallel_op,
            parallel_scope.results,
        )
        parallel_scope._reattach_views(self._builder)

    # region Interface with Circuit

    @staticmethod
    def _get_pauli_string_attribute_from_pauli_string(
        pauli_string: PauliString, qubit_arguments: Sequence[Qubit | QubitReg]
    ) -> PauliStringAttr:
        num_qubits = sum(len(q) for q in qubit_arguments)
        paulis: list[tuple[PauliAttr, int]] = []
        for qubit, pauli in pauli_string.items():
            index = IndexedAPIObject.get_object_index_in_sequence(qubit_arguments, qubit)
            if index is None:
                msg = "Could not find the source of a qubit in a Pauli string."
                raise RuntimeError(msg)
            paulis.append((pauli.to_qcore_attr(), index))
        return PauliStringAttr(paulis, num_qubits)

    def _get_flow_attribute(self) -> ConcreteFlowArrayAttr | None:
        """Return the correct flow annotations that should be included on the circuit being built.

        This method relies on several invariants that are listed below:

        1. Flow annotations and unsized registers are incompatible and are already guarded against.
           This method will raise an assertion error if this invariant is broken. So if any flow is
           present in ``self._flows``, all the qubit register arguments are sized.
        2. Qubit registers are returned in the same order they have been declared as arguments.

        Returns:
            An array of flows that should be added to the attribute dictionary of the built circuit
            or ``None`` if no flow should be added.
        """
        if not self._flows:
            return None
        assert not self._has_unsized_arguments, (
            "The add_flow and add_args methods are supposed to check that circuits with unsized "
            "arguments cannot be annotated with flows. This is not verified as the currently built "
            f"circuit contains flows ({self._flows}) and at least one unsized argument in its "
            f"arguments ({self._builder.arguments})."
        )
        qubit_args = [arg for arg in self._builder.arguments if isinstance(arg, (Qubit, QubitReg))]

        returned_measurements = [
            ret
            for ret in self._builder.returns
            if isinstance(ret, (MeasurementBit, MeasurementReg))
        ]
        concrete_flows: list[ConcreteFlowAttr] = []
        for flow in self._flows:
            measurements = [
                IndexedAPIObject.get_object_index_in_sequence(returned_measurements, measurement)
                for measurement in flow.measurements
            ]
            assert does_not_contain_none_values(measurements), (
                "Ensured by CircuitBuilder.add_flow that checks if the measurements are marked as "
                "returned first."
            )

            input_state = CircuitBuilder._get_pauli_string_attribute_from_pauli_string(
                flow.inputs, qubit_args
            )
            output_state = CircuitBuilder._get_pauli_string_attribute_from_pauli_string(
                flow.outputs, qubit_args
            )
            concrete_flows.append(
                ConcreteFlowAttr("+" if flow.sign else "-", measurements, input_state, output_state)
            )
        return ConcreteFlowArrayAttr(concrete_flows)

    def build(self, identifier: str) -> Circuit[..., Any]:
        """Builds and returns an immutable representation of the built circuit.

        Args:
            identifier: name that will be used to identify the circuit declaration in MLIR and that
                will be used when calling that circuit.

        Returns:
            An immutable representation of the circuit being built at the moment of calling. The
            results of the returned circuit are only known at runtime (they are defined by the calls
            to ``add_return`` made before building), so they are typed as ``Any``. Annotate the
            variable holding the result with the expected ``Circuit[[...], ...]`` type to get static
            checking of the arguments and results of that circuit.
        """
        if identifier in self._called.callables:
            msg = (
                f"Cannot build the circuit with identifier '{identifier}' as it already calls a "
                "circuit with that identifier."
            )
            raise IdentifierConflictError(msg)
        input_arguments = self._builder.arguments
        return_values = self._builder.returns
        # The following checks are double-checking an internal invariant of the CircuitBuilder
        # instance.
        assert _is_circuit_argument_sequence(input_arguments), (
            "Expected valid arguments. CircuitBuilder.add_arg should have failed earlier."
        )
        assert _is_circuit_return_sequence(return_values), (
            "Expected valid return types. CircuitBuilder.add_return should have failed earlier."
        )
        # Note that some BaseAPIObject instances (instances of TerminalIndexedAPIObject) are
        # computing SSA values lazily. All the arguments and results SSA values should be present
        # before cloning the region (else value mapping will fail), so we explicitly call ``.ssa``
        # here to ensure that.
        return_results_ssas = [ret.ssa for ret in return_values]
        arguments_ssas = [arg.ssa for arg in self._builder.arguments]
        # Appending the yield operation to a copy of the current state of the builder.
        new_region = Region()
        value_mapper: dict[SSAValue, SSAValue] = {}
        self._builder.region.clone_into(new_region, value_mapper=value_mapper)
        return_results = [value_mapper[ssa] for ssa in return_results_ssas]
        # All qubits registers in the API are implemented with TensorType for consistency, so to
        # implement qubit passing by value in the ir, given qubits passed by reference in the API we
        # add a new result for each qubit tensor argument that will be used to update the caller
        # qubit registers after it calls this circuit.
        return_results += [
            value_mapper[ssa]
            for ssa in arguments_ssas
            if (TensorType.constr(QubitType())).verifies(ssa.type) or ssa.type == QubitType()
        ]
        return_op = ReturnOp(*return_results)
        new_region.block.add_op(return_op)
        # Build the `log_asm_api.circuit_dec` operation that will represent the built circuit.
        circuit_op = CircuitDeclarationOp(
            name=identifier,
            function_type=(
                self._builder.block.arg_types,
                tuple(ret.type for ret in return_results),
            ),
            body=new_region,
        )
        if (flows := self._get_flow_attribute()) is not None:
            circuit_op.attributes[ConcreteFlowArrayAttr.KEY] = flows
        module = ModuleOp(Region([Block([circuit_op])]))
        module.body.block.add_ops(
            [op.clone(value_mapper=value_mapper) for op in self._called.callables.values()]
        )
        module.verify()
        # Adapting returns (which is currently a tuple) to the expected return type:
        subroutine_returns: CircuitResultsType
        if len(return_values) == 0:
            subroutine_returns = None
        elif len(return_values) == 1:
            subroutine_returns = return_values[0]
        else:
            subroutine_returns = return_values
        return Circuit(module, identifier, subroutine_returns, *input_arguments)

    def call_circuit(self, circuit: InstantiatedCircuit[P, CircuitOutputType]) -> CircuitOutputType:
        """Calls an instantiated circuit.

        This method should be called with the result of calling a ``Circuit`` object with the
        appropriate inputs.

        Args:
            circuit: the instantiated circuit to call.

        Returns:
            The measurement results returned by the called circuit.

        Raises:
            DifferentBuildersError: if the provided ``circuit`` has been instantiated on registers
                that are not tracked by this instance of the builder.
        """
        # Check that the provided outer arguments (i.e., the arguments provided when instantiating
        # the Circuit) have been created in this builder.
        for arg in circuit.arguments:
            if not self._builder.is_managing(arg):
                raise DifferentBuildersError()

        # Register the circuit in this builder
        self._called.add_callable(
            circuit.identifier, circuit.declaration_op, circuit.called_circuits
        )

        # handle casting tensor<10x!...> input types to tensor<?x!...>.
        pre_call_ops: list[CastOp] = []
        call_args: list[SSAValue] = [
            self._called.coerce_operand_from_arg(
                outer_arg.ssa, inner_type, op_list=pre_call_ops, callable_ident=circuit.identifier
            )
            for inner_type, outer_arg in zip(
                circuit.declaration_op.function_type.inputs, circuit.arguments, strict=True
            )
        ]

        # Make the call

        call_op = CallOp(
            circuit.identifier, call_args, tuple(circuit.declaration_op.function_type.outputs)
        )

        # Collect which API objects are quantum args to implement pass-by-reference
        post_call_ops, quantum_args, quantum_results = self._called.recast_quantum_results(
            circuit.arguments, call_op.ret
        )

        # Add all the ops to the builder and update the API objects with the new ssa values
        explicit_returns = [res._get_unattached_deepcopy() for res in circuit.results_tuple]
        ret = self._builder.append_ops_and_update_ssas(
            (*pre_call_ops, call_op, *post_call_ops),
            list(call_op.ret[: len(circuit.results_tuple)]) + quantum_results,
            explicit_returns + quantum_args,
        )
        ret = ret[: len(circuit.results_tuple)]
        # The below cast are valid because we adapt the type of the return here to the type of the
        # expected result from ``circuit`` dynamically.
        if circuit.results is None:
            return cast(CircuitOutputType, None)
        if isinstance(circuit.results, CircuitRetType):
            return cast(CircuitOutputType, ret[0])
        return cast(CircuitOutputType, tuple(ret))
