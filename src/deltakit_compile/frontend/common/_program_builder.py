# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module containing base classes for program builders."""

from abc import abstractmethod
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Generic, ParamSpec, TypeAlias, TypeVar, cast

from typing_extensions import override
from xdsl.dialects.builtin import ModuleOp, i1
from xdsl.ir import Region, SSAValue, StringIO
from xdsl.printer import Printer

from deltakit_compile.dialects import func, qstruct
from deltakit_compile.dialects import log_asm_api as api
from deltakit_compile.frontend.common._builder import (
    BaseAPIObject,
    OperationBuilder,
    SubCallablesBuilder,
)
from deltakit_compile.frontend.common._circuit import (
    CircuitOutputType,
    CircuitRetType,
    InstantiatedCircuit,
    MeasurementBit,
    MeasurementReg,
    _is_circuit_argument_sequence,
    is_sequence,
)
from deltakit_compile.frontend.common._classical_expr import ClassicalExpression
from deltakit_compile.frontend.common._exceptions import (
    DifferentBuildersError,
    UnsupportedReturnTypeError,
)


@dataclass(frozen=True)
class Program:
    """An immutable program that can be compiled into a physical circuit."""

    _module: ModuleOp

    @property
    def module(self) -> ModuleOp:
        """A copy of the IR that defines this program."""
        return self._module.clone()

    @override
    def __str__(self) -> str:
        res = StringIO()
        printer = Printer(stream=res)
        printer.print_string(f"{type(self).__name__}(")
        printer.print_region(self._module.body)
        printer.print_string(")")
        return res.getvalue()


P = ParamSpec("P")
ProgramReturnType: TypeAlias = ClassicalExpression | MeasurementReg | MeasurementBit
_Program_type = TypeVar("_Program_type", bound=Program)


class ProgramBuilder(Generic[_Program_type]):
    """Base class for program builders, i.e., builders without the constraints of custom
    circuits."""

    def __init__(self) -> None:
        # Internal state management.
        self._builder = OperationBuilder()
        self._called: SubCallablesBuilder[func.FuncOp | api.CircuitDeclarationOp]

    def _build_module(self) -> ModuleOp:
        """Build the module op that will be inserted inside the built program object."""
        if self._builder.arguments:
            msg = "Top level programs cannot have arguments."
            raise RuntimeError(msg)
        # Note that the `.ssa` property is lazy for some API objects, so we need to call it here
        # **before** clonging the region, else we might clone a region in which the SSA value never
        # existed, which will result in an error later.
        results: list[SSAValue] = []
        for i, ret in enumerate(self._builder.returns):
            if isinstance(ret, MeasurementReg):
                results.extend(bit.ssa for bit in ret.unpack())
                continue
            if ret.ssa.type != i1:
                msg = (
                    "Top level programs can only return boolean values but got "
                    f"an SSA of type {ret.ssa.type} for the {i}-th returned value."
                )
                raise RuntimeError(msg)
            results.append(ret.ssa)
        value_mapper: dict[SSAValue, SSAValue] = {}
        new_region = Region()
        self._builder.region.clone_into(new_region, value_mapper=value_mapper)
        new_region.block.add_op(qstruct.OutputOp([value_mapper[ret] for ret in results]))
        new_region.block.add_ops(
            [op.clone(value_mapper=value_mapper) for op in self._called.callables.values()]
        )
        module = ModuleOp(new_region)
        module.verify()
        return module

    @abstractmethod
    def build_program(self) -> _Program_type:
        """Generate a program from this builder."""

    def add_return(self, result: ProgramReturnType | Sequence[ProgramReturnType]) -> None:
        """Add one or several classical results to this program."""
        results: Sequence[Any] = (
            (result,)
            if isinstance(result, ProgramReturnType) or not is_sequence(result)
            else result
        )
        # Check everything before appending anything to avoid registering only part of the provided
        # results if one of them is invalid (i.e. if the error is caught somewhere).
        for res in results:
            if not isinstance(res, ProgramReturnType):
                raise UnsupportedReturnTypeError(type(res))
        for res in results:
            self._builder.append_return(res)

    @contextmanager
    def if_(self, expr: ClassicalExpression):
        """Make a context that defines the conditional execution of the internal operations.

        Usage:

            with builder.if_(some_existing_ClassicalExpression):
                ...
                operate on patches
                ...
        """
        msg = "Features using context-managers ('with ...:') are not yet implemented in the API."
        raise NotImplementedError(msg)
        outer_builder = self._builder
        inner_builder = OperationBuilder()
        self._builder = inner_builder
        yield
        self._builder = outer_builder
        # TODO: Add support for If statements

    @contextmanager
    def else_(self):
        """Make a context that defines the else portion of a conditionally executed section of the
        program. This may only be used immediately after a `with builder.if_():` context.

        Usage:

            with builder.if_(some_existing_ClassicalExpression):
                ...
            with builder.else_():
                ...
                operate on patches
                ...
        """
        msg = "Features using context-managers ('with ...:') are not yet implemented in the API."
        raise NotImplementedError(msg)
        # TODO: check that the very last operation added to self._builder is an IfOp. If that is
        # not the case, this is an invalid use of builder.else_, so we raise.
        outer_builder = self._builder
        inner_builder = OperationBuilder()
        self._builder = inner_builder
        yield
        self._builder = outer_builder
        # TODO: Add support for If statements

    @contextmanager
    def while_(self, expr: ClassicalExpression):
        """Make a context that executes the internal section of the program while the given expr
        holds."""
        msg = "Features using context-managers ('with ...:') are not yet implemented in the API."
        raise NotImplementedError(msg)
        outer_builder = self._builder
        inner_builder = OperationBuilder()
        self._builder = inner_builder
        yield
        self._builder = outer_builder
        # TODO: Add support for While loop

    @contextmanager
    def for_(self, start: int, stop: int, step: int = 1):
        """Make a context the executes the internal section of the program in a loop given the
        start index, (exclusive) stop index, and step value."""
        msg = "Features using context-managers ('with ...:') are not yet implemented in the API."
        raise NotImplementedError(msg)
        outer_builder = self._builder
        inner_builder = OperationBuilder()
        self._builder = inner_builder
        yield
        self._builder = outer_builder
        # TODO: Add support for For loops

    def _check_args_are_managed(self, args: Sequence[BaseAPIObject]) -> None:
        """Check that the provided arguments (i.e., the arguments provided when instantiating
        a subroutine/circuit) have been created in this builder."""
        for arg in args:
            if not self._builder.is_managing(arg):
                raise DifferentBuildersError()

    def call_circuit(self, circuit: InstantiatedCircuit[P, CircuitOutputType]) -> CircuitOutputType:
        """Call a circuit from this this program, returning its declared results.

        Arguments:
            circuit: the circuit to add to the program.

        Returns:
            Objects representing the output of the called circuit.

        Example:

            circuit_builder = CircuitBuilder()
            # ...
            my_circuit = circuit_builder.build("my_circuit")

            builder = CircuitProgramBuilder() # or LogAsmBuilder
            qubits = builder.declare_qubits(QubitReg(2))
            builder.call_circuit(my_circuit(qubits))
        """
        # Checked by InstantiatedCircuit __post_init__, but Python typing system does not allow us
        # to encode such a constraint
        assert _is_circuit_argument_sequence(circuit.arguments)
        # Check that the provided outer arguments (i.e., the arguments provided when instantiating
        # the Circuit) have been created in this builder.
        self._check_args_are_managed(circuit.arguments)

        # Register the circuit in this builder
        self._called.add_callable(
            circuit.identifier, circuit.declaration_op, circuit.called_circuits
        )

        pre_call_ops: list[api.CastOp] = []
        call_args = [
            self._called.coerce_operand_from_arg(
                outer_arg.ssa, inner_type, op_list=pre_call_ops, callable_ident=circuit.identifier
            )
            for inner_type, outer_arg in zip(
                circuit.declaration_op.function_type.inputs, circuit.arguments, strict=True
            )
        ]

        # Make the call
        call_op = api.CallOp(
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

        # The below casts are valid because we adapt the type of the return here to the type of the
        # expected result from ``circuit`` dynamically.
        if circuit.results is None:
            return cast(CircuitOutputType, None)
        if isinstance(circuit.results, CircuitRetType):
            return cast(CircuitOutputType, ret[0])
        return cast(CircuitOutputType, tuple(ret))
