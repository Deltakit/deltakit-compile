# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for the logical assembly API xDSL dialect.

This dialect is used to represent temporarily information from the API that is not representable
by the logasm dialect but is still needed in the early compilation process.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar, Final, TypeGuard, cast

from typing_extensions import override
from xdsl.dialects.builtin import (
    DYNAMIC_INDEX,
    ArrayAttr,
    ArrayOfConstraint,
    FunctionType,
    IntAttr,
    StringAttr,
    SymbolNameConstraint,
    SymbolRefAttr,
    TensorType,
)
from xdsl.dialects.utils import AbstractYieldOperation, parse_func_op_like, print_func_op_like
from xdsl.ir import Attribute, Block, Dialect, Operation, Region, SSAValue
from xdsl.irdl import (
    AnyAttr,
    AnyInt,
    AnyOf,
    AtLeast,
    AttrConstraint,
    IntVarConstraint,
    IRDLOperation,
    MessageConstraint,
    ParamAttrConstraint,
    RangeConstraint,
    RangeOf,
    RangeVarConstraint,
    SingleOf,
    VarConstraint,
    base,
    irdl_op_definition,
    lazy_traits_def,
    operand_def,
    opt_prop_def,
    prop_def,
    region_def,
    result_def,
    traits_def,
    var_operand_def,
    var_result_def,
)
from xdsl.parser import Parser
from xdsl.printer import Printer
from xdsl.traits import (
    HasParent,
    IsolatedFromAbove,
    IsTerminator,
    Pure,
    ReturnLike,
    SingleBlockImplicitTerminator,
    SymbolOpInterface,
    SymbolTable,
    SymbolUserOpInterface,
)
from xdsl.utils.exceptions import VerifyException

from deltakit_compile.dialects.common.attributes import OptPlainIntAttr
from deltakit_compile.dialects.common.constraints import IntTensorDimensionSizeConstraint, SumOver
from deltakit_compile.dialects.common.traits import HasSideEffects
from deltakit_compile.dialects.logical_assembly import BasePatch, SurfaceCodeBasePatch
from deltakit_compile.dialects.qcore import (
    GateAttribute,
    HasCircuitAncestor,
    IsCircuit,
    NoQuantumEffect,
    Pauli,
    PauliAttr,
    QubitGateEffect,
    QubitRegType,
    QubitResetEffect,
    QubitType,
    qubit_count,
)

LOCKSTEP_PARALLEL_ATTRIBUTE: Final[str] = "log_asm_api.lockstep"
"""The name of an attribute added to qstruct.parallel operations to mark them as needing to be
lock-stepped."""


def _is_sequence_of_operations(
    body: Region | Sequence[Operation] | Sequence[Block],
) -> TypeGuard[Sequence[Operation]]:
    return isinstance(body, Sequence) and all(isinstance(op, Operation) for op in body)


def _is_tensor_of_qubits(operand: Attribute) -> TypeGuard[TensorType]:
    return isinstance(operand, TensorType) and isinstance(operand.element_type, QubitType)


def _is_unsized_tensor_of_qubits(operand: Attribute) -> TypeGuard[TensorType]:
    return _is_tensor_of_qubits(operand) and operand.shape.data == (IntAttr(DYNAMIC_INDEX),)


_TENSOR_SIZE_CONSTRAINT: Final = MessageConstraint(
    ArrayOfConstraint(SingleOf(IntAttr.constr(IntTensorDimensionSizeConstraint()))),
    "Expected a 1-dimensional tensor.",
)
_1D_QUBIT_TENSOR_CONSTRAINT: Final = TensorType.constr(QubitType(), _TENSOR_SIZE_CONSTRAINT)


class CallOpSymbolUserOpInterface(SymbolUserOpInterface):
    """This is a re-implementation of ``xdsl.dialects.func.CallOpSymbolUserOpInterface``.

    This re-implementation is needed because the original class starts its ``verify`` by asserting
    that the provided operation is an instance of ``xdsl.dialects.func.CallOp``, which is not what
    we want for ``log_asm_api.call`` that is of type
    ``deltakit_compile.dialects.log_asm_api.CallOp``.
    """

    @override
    def verify(self, op: Operation) -> None:
        assert isinstance(op, CallOp)

        found_callee = SymbolTable.lookup_symbol(op, op.callee)
        if not found_callee:
            msg = f"'{op.callee}' could not be found in symbol table"
            raise VerifyException(msg)

        if not isinstance(found_callee, CircuitDeclarationOp):
            msg = f"'{op.callee}' does not reference a valid circuit declaration"
            raise VerifyException(msg)

        if len(found_callee.function_type.inputs) != len(op.arguments):
            msg = "Incorrect number of operands for callee"
            raise VerifyException(msg)

        if len(found_callee.function_type.outputs) != len(op.result_types):
            msg = "Incorrect number of results for callee"
            raise VerifyException(msg)

        for idx, (found_operand, operand) in enumerate(
            zip(found_callee.function_type.inputs, (arg.type for arg in op.arguments), strict=True)
        ):
            if found_operand != operand:
                msg = (
                    f"Operand type mismatch: expected operand type {found_operand}, "
                    f"but provided {operand} for operand number {idx}"
                )
                raise VerifyException(msg)

        for idx, (found_res, res) in enumerate(
            zip(found_callee.function_type.outputs, op.result_types, strict=True)
        ):
            if found_res != res:
                msg = (
                    f"result type mismatch: expected result type {found_res}, but "
                    f"provided {res} for result number {idx}"
                )
                raise VerifyException(msg)


@irdl_op_definition
class UnsizedResetOp(IRDLOperation):
    """Reset one or more qubits in the provided basis.
    be unknown (modelled as ``tensor<?x!qcore.qubit>``). This is a broadcast op that separately
    applies the reset to each provided qubit.
    """

    name = "log_asm_api.unsized_reset"

    basis = prop_def(PauliAttr)
    qubits = operand_def(_1D_QUBIT_TENSOR_CONSTRAINT)

    traits = traits_def(QubitResetEffect("qubits"), HasCircuitAncestor())

    assembly_format = (
        f"`<` {PauliAttr.plain_directive('$basis')} `>` `(` $qubits `:` type($qubits) `)` attr-dict"
    )
    custom_directives = (PauliAttr.plain_directive(),)

    def __init__(self, basis: Pauli, qubits: SSAValue):
        super().__init__(operands=[qubits], properties={"basis": PauliAttr.coerce(basis)})


@irdl_op_definition
class UnsizedGateOp(IRDLOperation):
    """Apply a gate to one ore more qubits.

    This operation is equivalent to a ``qref.gate`` but where the number of qubits operated on may
    be unknown (modelled as ``tensor<?x!qcore.qubit>``). This is a broadcast op that separately
    applies a single qubit gate to each provided qubit. Two qubit gates will operate on the provided
    qubits in pairs, three qubits gates in triplets, etc.
    """

    name = "log_asm_api.unsized_gate"

    gate = prop_def(GateAttribute)
    qubits = operand_def(_1D_QUBIT_TENSOR_CONSTRAINT)

    traits = traits_def(QubitGateEffect("qubits"), HasCircuitAncestor())

    assembly_format = "`<` $gate `>` `(` $qubits `:` type($qubits) `)` attr-dict"

    def __init__(self, gate: GateAttribute, qubits: SSAValue):
        super().__init__(operands=[qubits], properties={"gate": gate})

    @override
    def verify_(self) -> None:
        """Verify the gate can be broadcasted to provided qubits."""
        # The below is all checked by constraints and so should be valid.
        gate_arity = self.gate.get_qubit_count()
        size = cast(TensorType, self.qubits.type).shape.data[0].data
        if size != DYNAMIC_INDEX and size % gate_arity != 0:
            msg = (
                f"Invalid broadcast of {self.gate.name}: expected the gate to be applied on a "
                f"number of qubits that is a multiple of {gate_arity} but got {size}."
            )
            raise VerifyException(msg)


@irdl_op_definition
class BarrierOp(IRDLOperation):
    """Prevents operations from being parallelised by moving them past this op if they use the
    provided ``log_asm.patch`` or ``qcore.qubit_reg`` operands.

    Note:
        This operation does not have a "if no operands this applies to every patch" mode like in the
        API - instances of this op should have already been resolved to explicit lists of every
        affected patch.
    """

    name = "log_asm_api.barrier"

    _ARGS: ClassVar[RangeConstraint] = RangeVarConstraint(
        "Args", RangeOf(AnyOf((base(BasePatch), base(QubitRegType)))).of_length(AtLeast(1))
    )

    arguments = var_operand_def(_ARGS)
    res = var_result_def(_ARGS)

    traits = traits_def(Pure(), NoQuantumEffect())

    assembly_format = "`(` $arguments `:` type($arguments) `)` attr-dict"

    def __init__(self, operands: Sequence[SSAValue]) -> None:
        super().__init__(operands=[operands], result_types=[[operand.type for operand in operands]])


@irdl_op_definition
class CircuitDeclarationOp(IRDLOperation):
    """Declare a circuit (a container for physical operations) that can be called later like a
    function.

    The qubits it operates on are declared globally and passed in as arguments. Any qubit passed
    into a circuit must be returned as SSA values regardless of if the operations inside the circuit
    are ``qref``.
    """

    name = "log_asm_api.circuit_dec"

    _NUM_QUBITS: ClassVar[RangeConstraint] = SumOver(
        RangeOf(AnyAttr()), qubit_count, IntVarConstraint("Qubits", AnyInt())
    )
    """Constrains ranges of types to have the same total number of qubits."""
    _ARGS: ClassVar[RangeConstraint] = RangeVarConstraint("Arguments", _NUM_QUBITS)
    """Variable constraint to ensure the exact same types are used, and also the total number of
    qubits matches uses other uses of _NUM_QUBITS. """

    sym_name = prop_def(SymbolNameConstraint())
    function_type = prop_def(
        ParamAttrConstraint(
            FunctionType,
            (ArrayOfConstraint(_ARGS), ArrayOfConstraint(_NUM_QUBITS)),
        )
    )
    body = region_def("single_block", entry_args=_ARGS)

    traits = lazy_traits_def(
        lambda: (
            IsCircuit(),
            IsolatedFromAbove(),
            SymbolOpInterface(),
            NoQuantumEffect(),
            HasSideEffects(),
            SingleBlockImplicitTerminator(ReturnOp),
        )
    )

    def __init__(
        self,
        name: str,
        function_type: FunctionType | tuple[Sequence[Attribute], Sequence[Attribute]],
        body: Region | Sequence[Operation] | Sequence[Block],
    ) -> None:
        # Harmonise input by forcing ``function_type`` to be an instance of ``FunctionType``.
        if isinstance(function_type, tuple):
            inputs, outputs = function_type
            function_type = FunctionType.from_lists(inputs, outputs)
        # If the body is provided as a list of operations, create an appropriate region.
        if _is_sequence_of_operations(body):
            body = Region(Block(ops=body, arg_types=function_type.inputs))
        properties: dict[str, Attribute | None] = {
            "sym_name": StringAttr(name),
            "function_type": function_type,
        }
        super().__init__(properties=properties, regions=[body])

    @override
    @classmethod
    def parse(cls, parser: Parser) -> CircuitDeclarationOp:
        (name, input_types, return_types, region, extra_attrs, _, _) = parse_func_op_like(
            parser, reserved_attr_names=("sym_name", "function_type")
        )
        return CircuitDeclarationOp.create(
            regions=[region],
            properties={
                "sym_name": StringAttr(name),
                "function_type": FunctionType(ArrayAttr(input_types), ArrayAttr(return_types)),
            },
            attributes=extra_attrs.data if extra_attrs is not None else {},
        )

    @override
    def print(self, printer: Printer):
        print_func_op_like(
            printer,
            self.sym_name,
            self.function_type,
            self.body,
            self.attributes,
            reserved_attr_names=(
                "sym_name",
                "function_type",
                "arg_attrs",
            ),
        )

    @override
    def verify_(self) -> None:
        """Verify the circuit declaration body's return op has the same operand types as the
        declared results."""
        returned_types = self.return_op.operand_types
        if len(returned_types) != len(self.function_type.outputs):
            msg = (
                "The number of variables returned from the circuit declaration "
                f"({len(self.function_type.outputs)}) doesn't match the number of variables the "
                f"inner block returns ({len(returned_types)})."
            )
            raise VerifyException(msg)
        for i, (returned_type, output_type) in enumerate(
            zip(returned_types, self.function_type.outputs, strict=True)
        ):
            if returned_type != output_type:
                msg = (
                    f"The type of the {i + 1}-th variable returned from the circuit declaration "
                    f"({output_type}) doesn't match the type of the corresponding variable the "
                    f"inner block returns ({returned_type})."
                )
                raise VerifyException(msg)

    @property
    def return_op(self) -> ReturnOp:
        """Get this circuit declaration return op."""
        # Safe cast as yield's presence is verified by SingleBlockImplicitTerminator
        return cast(ReturnOp, self.body.block.last_op)


@irdl_op_definition
class ReturnOp(AbstractYieldOperation[Attribute]):
    """Return operation for circuit declaration in logasm_api dialect."""

    name = "log_asm_api.return"
    traits = traits_def(IsTerminator(), ReturnLike(), HasParent(CircuitDeclarationOp), Pure())


@irdl_op_definition
class CallOp(IRDLOperation):
    name = "log_asm_api.call"

    callee = prop_def(SymbolRefAttr)
    arguments = var_operand_def()
    ret = var_result_def()

    traits = traits_def(CallOpSymbolUserOpInterface())

    assembly_format = "$callee `(` $arguments `)` attr-dict `:` functional-type($arguments, $ret)"

    def __init__(
        self,
        callee: str | SymbolRefAttr,
        arguments: Sequence[SSAValue | Operation],
        return_types: Sequence[Attribute],
    ):
        if isinstance(callee, str):
            callee = SymbolRefAttr(callee)
        super().__init__(
            operands=[arguments], result_types=[return_types], properties={"callee": callee}
        )


@irdl_op_definition
class CastOp(IRDLOperation):
    """A more permissive version of the ``log_asm.cast`` that allows for conversion between any
    equivalent ``log_asm.patch``, ``qcore.qubit_reg``, or tensor type.

    This operation only supports casting where the element type is the same and either the lengths
    are the same or it is going from or to an unknown length 1D tensor.
    """

    name = "log_asm_api.cast"

    _TYPE_CONSTRAINT: ClassVar[AttrConstraint] = (
        base(QubitRegType)
        | base(SurfaceCodeBasePatch)
        | TensorType.constr(shape=_TENSOR_SIZE_CONSTRAINT)
    )

    argument = operand_def(_TYPE_CONSTRAINT)
    result = result_def(_TYPE_CONSTRAINT)

    traits = traits_def(Pure(), NoQuantumEffect())

    assembly_format = "`(` $argument `:` type($argument) `)` attr-dict `->` type($result)"

    def __init__(
        self, from_: SSAValue, to: QubitRegType | SurfaceCodeBasePatch | TensorType
    ) -> None:
        super().__init__(operands=[from_], result_types=[to])

    @staticmethod
    def _get_size(typ: QubitRegType | SurfaceCodeBasePatch) -> int:
        match typ:
            case QubitRegType():
                return typ.size.data
            case SurfaceCodeBasePatch():
                return typ.num_qubits

    @override
    def verify_(self) -> None:
        """Verify that the in/out element types are the same size or at least one of them is a
        dynamically sized tensor."""
        # First, standardise the types. For the purposes of validation, QubitRegType and
        # SurfaceCodeBasePatch instances behave just like sized tensors.
        in_type = cast(QubitRegType | SurfaceCodeBasePatch | TensorType, self.argument.type)
        if isinstance(in_type, (QubitRegType, SurfaceCodeBasePatch)):
            in_type = TensorType(QubitType(), shape=(CastOp._get_size(in_type),))
        out_type = cast(QubitRegType | SurfaceCodeBasePatch | TensorType, self.result.type)
        if isinstance(out_type, (QubitRegType, SurfaceCodeBasePatch)):
            out_type = TensorType(QubitType(), shape=(CastOp._get_size(out_type),))

        # Now we just have to compare tensor types.
        if in_type.element_type != out_type.element_type:
            msg = (
                f"Cannot cast an object of type {self.argument.type} into {self.result.type}: "
                "types are incompatible."
            )
            raise VerifyException(msg)
        in_size, out_size = in_type.shape.data[0].data, out_type.shape.data[0].data
        if in_size != DYNAMIC_INDEX and out_size != DYNAMIC_INDEX and in_size != out_size:  # noqa: PLR1714
            msg = (
                f"Cannot cast an object of type {self.argument.type} (of size {in_size}) into "
                f"{self.result.type} (of size {out_size}) due to differing sizes."
            )
            raise VerifyException(msg)


_ZEROABLE_TENSOR_SIZE_CONSTRAINT: Final = MessageConstraint(
    ArrayOfConstraint(
        SingleOf(IntAttr.constr(IntTensorDimensionSizeConstraint(allow_zero_length=True)))
    ),
    "Expected a 1-dimensional tensor.",
)


@irdl_op_definition
class TensorSliceOp(IRDLOperation):
    """A mechanism to represent index slicing of 1-D tensors within the API without fully
    expanding dynamic indexing cases into verbose arithmetic logic."""

    name = "log_asm_api.tensor_slice"

    _TENSOR_ELEMENT: ClassVar[AttrConstraint] = VarConstraint("Element Type", AnyAttr())

    input = operand_def(
        TensorType.constr(element_type=_TENSOR_ELEMENT, shape=_ZEROABLE_TENSOR_SIZE_CONSTRAINT)
    )

    start = opt_prop_def(IntAttr)
    stop = opt_prop_def(IntAttr)
    step = opt_prop_def(IntAttr)

    slice = result_def(
        TensorType.constr(element_type=_TENSOR_ELEMENT, shape=_ZEROABLE_TENSOR_SIZE_CONSTRAINT)
    )

    leftovers = result_def(
        TensorType.constr(element_type=_TENSOR_ELEMENT, shape=_ZEROABLE_TENSOR_SIZE_CONSTRAINT)
    )

    traits = traits_def(Pure(), NoQuantumEffect())

    assembly_format = (
        "`(` $input `` "
        f"`[` `` ({OptPlainIntAttr.use('$start')}^)? ``"
        f"`:` `` ({OptPlainIntAttr.use('$stop')}^)? ``"
        f"`:` `` ({OptPlainIntAttr.use('$step')}^)? ``"
        "`]` `)` attr-dict `:` type($input) `->` type($slice) `,` type($leftovers)"
    )
    custom_directives = (OptPlainIntAttr,)

    def __init__(
        self,
        tensor: SSAValue,
        slice_type: TensorType,
        leftovers_type: TensorType,
        start: IntAttr | int | None = None,
        stop: IntAttr | int | None = None,
        step: IntAttr | int | None = None,
    ):
        super().__init__(
            operands=(tensor,),
            result_types=(slice_type, leftovers_type),
            properties={
                "start": None if start is None else IntAttr.get(start),
                "stop": None if stop is None else IntAttr.get(stop),
                "step": None if step is None else IntAttr.get(step),
            },
        )


@irdl_op_definition
class TensorMergeOp(IRDLOperation):
    """A mechanism to represent the inverse of index slicing of 1-D tensors within the API without
    fully expanding dynamic indexing cases into verbose arithmetic logic. This op takes two
    inputs, the ``base_input``, and the ``sliced_input``. It produces a new tensor that is the
    result of updating the values of ``base_input[start:stop:step]`` with the values of
    ``sliced_input``."""

    name = "log_asm_api.tensor_merge"

    _TENSOR_ELEMENT: ClassVar[AttrConstraint] = VarConstraint("Element Type", AnyAttr())
    sliced_input = operand_def(
        TensorType.constr(element_type=_TENSOR_ELEMENT, shape=_ZEROABLE_TENSOR_SIZE_CONSTRAINT)
    )

    leftovers_input = operand_def(
        TensorType.constr(element_type=_TENSOR_ELEMENT, shape=_ZEROABLE_TENSOR_SIZE_CONSTRAINT)
    )

    start = opt_prop_def(IntAttr)
    stop = opt_prop_def(IntAttr)
    step = opt_prop_def(IntAttr)

    result = result_def(
        TensorType.constr(element_type=_TENSOR_ELEMENT, shape=_ZEROABLE_TENSOR_SIZE_CONSTRAINT)
    )

    traits = traits_def(Pure(), NoQuantumEffect())

    assembly_format = (
        "`<` ``"
        f"`[` `` ({OptPlainIntAttr.use('$start')}^)? ``"
        f"`:` `` ({OptPlainIntAttr.use('$stop')}^)? ``"
        f"`:` `` ({OptPlainIntAttr.use('$step')}^)? ``"
        "`]` `` `>` `` `(` "
        "$sliced_input `:` type($sliced_input) `,` $leftovers_input `:` type($leftovers_input) "
        "`)` attr-dict `->` type($result)"
    )

    custom_directives = (OptPlainIntAttr,)

    def __init__(
        self,
        sliced_input: SSAValue,
        leftovers_input: SSAValue,
        output_type: Attribute,
        start: IntAttr | int | None = None,
        stop: IntAttr | int | None = None,
        step: IntAttr | int | None = None,
    ):
        super().__init__(
            operands=(sliced_input, leftovers_input),
            result_types=(output_type,),
            properties={
                "start": None if start is None else IntAttr.get(start),
                "stop": None if stop is None else IntAttr.get(stop),
                "step": None if step is None else IntAttr.get(step),
            },
        )


LogAsmApi = Dialect(
    "log_asm_api",
    [
        UnsizedResetOp,
        UnsizedGateOp,
        BarrierOp,
        CircuitDeclarationOp,
        ReturnOp,
        CallOp,
        CastOp,
        TensorSliceOp,
        TensorMergeOp,
    ],
    [],
)
