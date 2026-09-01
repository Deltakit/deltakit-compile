# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for the xDSL dialect for stabiliser flow concepts."""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from io import StringIO
from typing import (
    ClassVar,
    Literal,
    TypeAlias,
    cast,
    overload,
)

from typing_extensions import TypeVar, override
from xdsl.context import Context
from xdsl.dialects.builtin import (
    I1,
    ArrayAttr,
    ArrayOfConstraint,
    BoolAttr,
    IntAttr,
    IntAttrConstraint,
    IntegerAttr,
    i1,
)
from xdsl.ir import (
    Attribute,
    AttributeCovT,
    Block,
    BlockArgument,
    Dialect,
    Operation,
    OpResult,
    ParametrizedAttribute,
    Region,
    SSAValue,
    TypeAttribute,
)
from xdsl.irdl.attributes import base, irdl_attr_definition, param_def
from xdsl.irdl.constraints import (
    AllOf,
    AnyAttr,
    AnyInt,
    AtLeast,
    AttrConstraint,
    ConstraintContext,
    EqIntConstraint,
    IntConstraint,
    IntVarConstraint,
    MessageConstraint,
    ParamAttrConstraint,
    RangeConstraint,
    RangeOf,
    RangeVarConstraint,
    VarConstraint,
)
from xdsl.irdl.declarative_assembly_format import (
    AttributeVariable,
    CustomDirective,
    OperandVariable,
    ParsingState,
    PrintingState,
    RegionVariable,
    ResultVariable,
    TypeDirective,
    VariadicOperandVariable,
    irdl_custom_directive,
)
from xdsl.irdl.operations import (
    AttrSizedOperandSegments,
    IRDLOperation,
    attr_def,
    irdl_op_definition,
    lazy_traits_def,
    operand_def,
    opt_prop_def,
    region_def,
    result_def,
    traits_def,
    var_operand_def,
    var_result_def,
)
from xdsl.parser import AttrParser, Parser, UnresolvedOperand
from xdsl.pattern_rewriter import PatternRewriter, RewritePattern
from xdsl.printer import Printer
from xdsl.traits import (
    HasCanonicalizationPatternsTrait,
    HasParent,
    IsolatedFromAbove,
    IsTerminator,
    Pure,
    RecursiveMemoryEffect,
    SingleBlockImplicitTerminator,
)
from xdsl.utils.exceptions import VerifyException

from deltakit_compile.dialects import qcore
from deltakit_compile.dialects.common.attributes import (
    PlainArrayOfIntAttrDirective,
    RepeatedOperandType,
)
from deltakit_compile.dialects.common.constraints import (
    MessageIntConstraint,
    SetOf,
    SortedRangeOf,
    SumOver,
)
from deltakit_compile.dialects.qcore import (
    I_STATE_INDEX,
    IsCircuit,
    NoQuantumEffect,
    Pauli,
    PauliStringAttr,
    QubitPauliStateAttr,
    RecursiveQuantumEffect,
    StateQubitIndex,
)
from deltakit_compile.utilities.ordered_set import OrderedSet

StateTypePauliStrings: TypeAlias = (
    ArrayAttr[PauliStringAttr]
    | Iterable[PauliStringAttr]
    | Iterable[PauliStringAttr | Iterable[QubitPauliStateAttr | tuple[Pauli, IntAttr | int]]]
)


@irdl_attr_definition
class StateType(ParametrizedAttribute, TypeAttribute):
    """A multi-qubit quantum state together with a set of stabiliser flow states which stabilise the
    state.

    This type represents the interface between parts of a quantum program based on the partially
    formed stabiliser flow properties at the boundaries of composable sections of quantum programs.
    States of this type are simultaneously stabilised by the flow states, which must pairwise
    commute. The flow states are required to be unique and sorted first by their qubit indices, then
    by their Pauli states.
    """

    name = "stab.state"

    _Q: ClassVar[IntVarConstraint] = IntVarConstraint("Qubits", AtLeast(0))

    qubits: IntAttr = param_def(IntAttrConstraint(_Q))
    qubit_type: TypeAttribute

    flow_states: ArrayAttr[PauliStringAttr] = param_def(
        MessageConstraint(
            ArrayOfConstraint(
                SortedRangeOf(
                    RangeOf(PauliStringAttr.constr(_Q)),
                    key=PauliStringAttr.sort_key,
                    strictly_increasing=True,
                )
            ),
            f"Each {PauliStringAttr.name} in a {name} must be unique and sorted first by the qubit "
            "indices they use, and then by each qubit's Pauli state.",
        ),
    )

    def __init__(
        self,
        qubits: IntAttr | int,
        qubit_type: TypeAttribute,
        flow_states: StateTypePauliStrings,
    ):
        qubits = IntAttr.get(qubits)
        if isinstance(flow_states, ArrayAttr):
            states = sorted(flow_states.data, key=PauliStringAttr.sort_key)
        else:
            states = sorted(
                [
                    (s if isinstance(s, PauliStringAttr) else PauliStringAttr(s, qubits))
                    for s in flow_states
                ],
                key=PauliStringAttr.sort_key,
            )
        super().__init__(qubits, qubit_type, ArrayAttr(states))

    @override
    def verify(self) -> None:
        """Verify that the flow states pairwise commute."""
        for state_a, state_b in itertools.combinations(self.flow_states, 2):
            if not state_a.commutes(state_b):
                msg = (
                    "All flow states in a stab.state must pairwise commute. "
                    f"Flow states {state_a} and {state_b} do not commute."
                )
                raise VerifyException(msg)

    def with_new_flow_states(self, new_flow_states: StateTypePauliStrings) -> StateType:
        """Get a new StateType with new flow states but the same qubits and qubit_type."""
        return StateType(self.qubits, self.qubit_type, new_flow_states)

    @property
    def total_qubits(self) -> StateQubitIndex:
        """The number of qubits represented by this state."""
        return self.qubits.data

    @property
    def states(self) -> Sequence[PauliStringAttr]:
        "The flow states of this state"
        return list(self.flow_states)

    @classmethod
    def parse_state_type(
        cls, parser: AttrParser
    ) -> tuple[IntAttr, TypeAttribute, ArrayAttr[PauliStringAttr]]:
        """Parse the internal attributes of a StateType.

        Parses things like:
            10 x !qcore.qubit, []
            2 x !qcore.qubit, [X0 X1, Z0 Z2]
        """
        qubits_int = IntAttr(
            parser.parse_integer(
                allow_boolean=False,
                allow_negative=False,
                context_msg=" Number of qubits in the state",
            )
        )
        parser.parse_keyword("x")
        qubit_type = parser.parse_type()
        parser.parse_punctuation(",")
        flows = ArrayAttr(
            [
                PauliStringAttr(qubit_states, length=qubits_int)
                for qubit_states in parser.parse_comma_separated_list(
                    delimiter=parser.Delimiter.SQUARE,
                    parse=lambda: PauliStringAttr.parse_qubit_pauli_states(parser),
                )
            ]
        )
        return (qubits_int, qubit_type, flows)

    @override
    @classmethod
    def parse_parameters(cls, parser: AttrParser) -> list[Attribute]:
        with parser.in_angle_brackets():
            return list(cls.parse_state_type(parser))

    def print_state_type(self, printer: Printer) -> None:
        """Print the internal attributes of a StateType."""

        printer.print_int(self.total_qubits)
        printer.print_string(" x ")
        printer.print_attribute(self.qubit_type)
        printer.print_string(", ")
        with printer.in_square_brackets():
            printer.print_list(
                self.flow_states,
                lambda flow: flow.print_qubit_pauli_states(printer),
                delimiter=", ",
            )

    @override
    def print_parameters(self, printer: Printer) -> None:
        with printer.in_angle_brackets():
            self.print_state_type(printer)

    @staticmethod
    def constr(
        qubits_constraint: IntConstraint,
        qubit_type_constraint: AttrConstraint,
        flow_states: IntConstraint,
    ) -> AttrConstraint[StateType]:
        """Get a constraint that constrains the attribute to be a StateType with the given
        IntConstraint applied to the StateType's qubits IntAttr field, with the given constraint
        on the qubit type, and a constraint on the number of flow states."""
        return ParamAttrConstraint(
            StateType,
            (
                IntAttr.constr(qubits_constraint),
                qubit_type_constraint,
                ArrayOfConstraint(RangeOf(AnyAttr()).of_length(flow_states)),
            ),
        )

    @staticmethod
    def merge_and_relabel_flow_states(
        state_types: Sequence[StateType],
    ) -> list[PauliStringAttr]:
        """Combine flow states from multiple StateType SSA values, preserving operand order.
        Note: each StateType must represent an independent set of qubits.

        Flow-state qubit indices are shifted so that each state's indices are correct in the
        concatenated state.
        """
        total_qubits = sum(state.total_qubits for state in state_types)
        base_idx: int = 0
        flow_states: list[PauliStringAttr] = []
        for state in state_types:
            flow_states.extend(
                [
                    f.shift_qubit_indices(base_idx, new_length=total_qubits)
                    for f in state.flow_states
                ]
            )
            base_idx += state.total_qubits
        return flow_states


def _parse_sign_and_measurements_header(
    parser: AttrParser,
) -> tuple[BoolAttr, ArrayAttr[IntAttr]]:
    """Parse a header giving the sign and measurement indices of a stabiliser flow.

    Examples of the header syntax:
        <+:0,1,2,3>
        <-:>
    """
    with parser.in_angle_brackets():
        sign_char = parser.parse_optional_punctuation("-")
        if sign_char is None:
            sign_char = parser.parse_punctuation("+")
        sign = IntegerAttr.from_bool(sign_char == "+")

        parser.parse_punctuation(":")
        measurement_idxs = parser.parse_optional_undelimited_comma_separated_list(
            lambda: parser.parse_optional_integer(allow_boolean=False, allow_negative=False),
            lambda: parser.parse_integer(allow_boolean=False, allow_negative=False),
        )
        measurement_indices = ArrayAttr(
            [IntAttr(i) for i in measurement_idxs] if measurement_idxs else []
        )
    return sign, measurement_indices


def _print_sign_and_measurements_header(
    printer: Printer, sign: bool, measurement_indices: Sequence[int]
) -> None:
    """Print a header giving the sign and measurement indices of a stabiliser flow."""
    with printer.in_angle_brackets():
        printer.print_string("+" if sign else "-")
        printer.print_string(":")
        if measurement_indices:
            printer.print_list(measurement_indices, printer.print_int)


@irdl_attr_definition
class FlowAttr(ParametrizedAttribute):
    """A FlowAttr represents the extra information that can connect input flow states and output
    flow states with measurements in a circuit. Each flow is based on the indices of the flow states
    within their respective state types and the indices of the measurements yielded from a circuit.
    The measurement indices are required to be non-negative, unique, and stored in sorted order."""

    name = "stab.flow"

    sign: BoolAttr
    measurements: ArrayAttr[IntAttr] = param_def(
        MessageConstraint(
            ArrayOfConstraint(
                SortedRangeOf(
                    RangeOf(IntAttrConstraint(AtLeast(0))),
                    key=lambda i: i.data,
                    strictly_increasing=True,
                )
            ),
            f"{name} measurement indices must be non-negative, sorted, and cannot contain "
            "duplicates.",
        )
    )
    input_state: IntAttr = param_def(IntAttrConstraint(AtLeast(I_STATE_INDEX)))
    output_state: IntAttr = param_def(IntAttrConstraint(AtLeast(I_STATE_INDEX)))

    def __init__(
        self,
        sign: BoolAttr | bool | Literal["+", "-"],
        measurements: ArrayAttr[IntAttr] | Iterable[IntAttr | int],
        input_state: IntAttr | int,
        output_state: IntAttr | int,
    ):
        if isinstance(sign, str):
            sign = sign == "+"
        if isinstance(sign, bool):
            sign = BoolAttr.from_bool(sign)
        measurements = ArrayAttr(
            sorted([IntAttr.get(i) for i in measurements], key=lambda i: i.data)
        )
        super().__init__(sign, measurements, IntAttr.get(input_state), IntAttr.get(output_state))

    @overload
    @staticmethod
    def from_states(
        sign: BoolAttr | bool | Literal["+", "-"],
        measurements: Iterable[SSAValue],
        input_state: PauliStringAttr | str,
        output_state: PauliStringAttr | str,
        *,
        context: CircuitOp,
    ) -> FlowAttr: ...

    @overload
    @staticmethod
    def from_states(
        sign: BoolAttr | bool | Literal["+", "-"],
        measurements: Iterable[SSAValue],
        input_state: PauliStringAttr | str,
        output_state: PauliStringAttr | str,
        *,
        measurement_context: Sequence[SSAValue],
        input_state_context: StateType | Sequence[PauliStringAttr],
        output_state_context: StateType | Sequence[PauliStringAttr],
    ) -> FlowAttr: ...

    @overload
    @staticmethod
    def from_states(
        sign: BoolAttr | bool | Literal["+", "-"],
        measurements: ArrayAttr[IntAttr] | Iterable[IntAttr | int],
        input_state: IntAttr | int,
        output_state: IntAttr | int,
        *,
        measurement_context: Sequence[SSAValue],
    ) -> FlowAttr: ...

    @overload
    @staticmethod
    def from_states(
        sign: BoolAttr | bool | Literal["+", "-"],
        measurements: ArrayAttr[IntAttr] | Iterable[IntAttr | int],
        input_state: PauliStringAttr | str,
        output_state: PauliStringAttr | str,
        *,
        input_state_context: StateType | Sequence[PauliStringAttr],
        output_state_context: StateType | Sequence[PauliStringAttr],
    ) -> FlowAttr: ...

    @overload
    @staticmethod
    def from_states(
        sign: BoolAttr | bool | Literal["+", "-"],
        measurements: ArrayAttr[IntAttr] | Iterable[IntAttr | int],
        input_state: IntAttr | int,
        output_state: IntAttr | int,
    ) -> FlowAttr: ...

    @staticmethod
    def from_states(
        sign: BoolAttr | bool | Literal["+", "-"],
        measurements: ArrayAttr[IntAttr] | Iterable[IntAttr | int | SSAValue],
        input_state: IntAttr | int | PauliStringAttr | str,
        output_state: IntAttr | int | PauliStringAttr | str,
        *,
        context: CircuitOp | None = None,
        measurement_context: Sequence[SSAValue] | None = None,
        input_state_context: StateType | Sequence[PauliStringAttr] | None = None,
        output_state_context: StateType | Sequence[PauliStringAttr] | None = None,
    ) -> FlowAttr:
        """Generates a FlowAttr using context information to get the correct index values for
        measurements, the input flow state, and the output flow state."""
        if context is not None:
            context.verify(verify_nested_ops=False)
            yield_op = context.body.block.last_op
            assert isinstance(yield_op, YieldOp)
            measurement_context = yield_op.measurements
            assert isinstance(context.input.type, StateType)
            input_state_context = context.input.type
            output_state_context = context.output.type

        measurement_idxs: list[IntAttr[int] | int] = []
        for m in measurements:
            if isinstance(m, SSAValue):
                assert measurement_context is not None
                measurement_idxs.append(measurement_context.index(m))
            else:
                measurement_idxs.append(m)

        if isinstance(input_state, str):
            input_state = PauliStringAttr.new(
                PauliStringAttr.parse_inner_parameters(Parser(Context(), input_state))
            )
        if isinstance(input_state_context, StateType):
            input_state_context = list(input_state_context.flow_states)
        if isinstance(input_state, PauliStringAttr):
            assert input_state_context is not None
            input_state = (
                I_STATE_INDEX
                if input_state.is_identity()
                else input_state_context.index(input_state)
            )

        if isinstance(output_state, str):
            output_state = PauliStringAttr.new(
                PauliStringAttr.parse_inner_parameters(Parser(Context(), output_state))
            )
        if isinstance(output_state_context, StateType):
            output_state_context = list(output_state_context.flow_states)
        if isinstance(output_state, PauliStringAttr):
            assert output_state_context is not None
            output_state = (
                I_STATE_INDEX
                if output_state.is_identity()
                else output_state_context.index(output_state)
            )

        return FlowAttr(
            sign=sign,
            measurements=measurement_idxs,
            input_state=input_state,
            output_state=output_state,
        )

    @override
    def verify(self) -> None:
        if self.input_state_index == I_STATE_INDEX and self.output_state_index == I_STATE_INDEX:
            msg = f"Flow cannot start and finish in 'I' state ({I_STATE_INDEX})."
            raise VerifyException(msg)

    @property
    def input_state_index(self) -> int:
        """Get the input state index for this flow - this refers to the flow in a circuit's
        input state type or it is `I_STATE_INDEX` indicating the 'I' state."""
        return self.input_state.data

    @property
    def output_state_index(self) -> int:
        """Get the output state index for this flow - this refers to the flow in a circuit's
        output state type or it is `I_STATE_INDEX` indicating the 'I' state."""
        return self.output_state.data

    @property
    def is_plus(self) -> bool:
        """True iff the sign of this flow is '+'"""
        return bool(self.sign.value.data)

    @property
    def is_minus(self) -> bool:
        """True iff the sign of this flow is '-'"""
        return not bool(self.sign.value.data)

    @property
    def is_creation_flow(self) -> bool:
        """True iff this flow is a creation flow (i.e. starts at 'I' state)."""
        return self.input_state_index == I_STATE_INDEX

    @property
    def is_destruction_flow(self) -> bool:
        """True iff this flow is a destruction flow (i.e. ends at 'I' state)."""
        return self.output_state_index == I_STATE_INDEX

    @property
    def measurement_indices(self) -> Sequence[int]:
        """The indices of the measurements this flow uses."""
        return [int_attr.data for int_attr in self.measurements]

    def sort_key(self) -> tuple[int, int]:
        """Get a sortable value from this FlowAttr for use in a list of flows."""
        return (self.input_state_index, self.output_state_index)

    def with_measurement_offset(self, offset: int) -> FlowAttr:
        """Get a new FlowAttr with all measurement indices offset by the given amount."""
        new_measurements = [index + offset for index in self.measurement_indices]

        if new_measurements and min(new_measurements) < 0:
            msg = (
                f"Cannot offset measurements by {offset} as it would result in negative "
                "measurement indices."
            )
            raise ValueError(msg)

        return FlowAttr(
            sign=self.sign,
            measurements=new_measurements,
            input_state=self.input_state,
            output_state=self.output_state,
        )

    @staticmethod
    def _parse_flow_state_index(
        parser: AttrParser, flow_states: list[PauliStringAttr] | None
    ) -> int:
        """Parse an flow state index as either an int representing the index,
        as 'I' representing the I state (`I_STATE_INDEX`), or as a PauliStringAttr which is matched
        against the given list of PauliStringAttr to get an index."""
        index = parser.parse_optional_integer(allow_boolean=False, allow_negative=False)
        if index is not None:
            return index

        qubit_states = PauliStringAttr.parse_qubit_pauli_states(parser)
        if len(qubit_states) == 0:
            return I_STATE_INDEX

        if flow_states is None:
            parser.raise_error("Expected an index of a flow state or 'I'.")
        for fs_index, flow_state in enumerate(flow_states):
            if flow_state.qubit_states == qubit_states:
                return fs_index

        # Qubit states weren't found in any of the flow states
        msg = StringIO()
        printer = Printer(stream=msg)
        printer.print_string("Cannot parse index as a flow state '")
        printer.print_list(qubit_states, lambda qs: qs.print_qubit_state(printer))
        printer.print_string("' as it does not appear in the flow state context: [")
        printer.print_list(flow_states, lambda f: f.print_qubit_pauli_states(printer))
        printer.print_string("].")
        parser.raise_error(msg.getvalue())
        # Can never get here but Ruff won't believe me
        msg = "Should be unreachable"  # pragma: no cover
        raise AssertionError(msg)  # pragma: no cover

    @classmethod
    def parse_flow_attr(
        cls,
        parser: AttrParser | Parser,
        input_flow_states: list[PauliStringAttr] | None = None,
        output_flow_states: list[PauliStringAttr] | None = None,
    ) -> tuple[BoolAttr, ArrayAttr[IntAttr], IntAttr, IntAttr]:
        """Parse the internal attributes of a FlowAttr.

        Parses things like:
            <+:0,1,2,3>{I -> 0}
            <-:>{4 -> 1}
            <+:0,1,2,3>{X0 X1 -> Z0 Z2}  // when given appropriate flow state context
        """
        sign, measurement_indices = _parse_sign_and_measurements_header(parser)

        with parser.in_braces():
            input_state = IntAttr(FlowAttr._parse_flow_state_index(parser, input_flow_states))
            parser.parse_punctuation("->")
            output_state = IntAttr(FlowAttr._parse_flow_state_index(parser, output_flow_states))
        return (sign, measurement_indices, input_state, output_state)

    @override
    @classmethod
    def parse_parameters(cls, parser: AttrParser) -> list[Attribute]:
        with parser.in_angle_brackets():
            return list(cls.parse_flow_attr(parser))

    def print_flow_attr(
        self,
        printer: Printer,
        input_flow_states: list[PauliStringAttr] | None = None,
        output_flow_states: list[PauliStringAttr] | None = None,
    ) -> None:
        """Print the internal attributes of a FlowAttr."""
        _print_sign_and_measurements_header(printer, self.is_plus, self.measurement_indices)

        with printer.in_braces():
            if self.input_state_index == I_STATE_INDEX:
                printer.print_string("I")
            elif input_flow_states is not None and 0 <= self.input_state_index < len(
                input_flow_states
            ):
                input_flow_states[self.input_state_index].print_qubit_pauli_states(printer)
            else:
                printer.print_int(self.input_state_index)

            printer.print_string(" -> ")

            if self.output_state_index == I_STATE_INDEX:
                printer.print_string("I")
            elif output_flow_states is not None and 0 <= self.output_state_index < len(
                output_flow_states
            ):
                output_flow_states[self.output_state_index].print_qubit_pauli_states(printer)
            else:
                printer.print_int(self.output_state_index)

    @override
    def print_parameters(self, printer: Printer) -> None:
        with printer.in_angle_brackets():
            self.print_flow_attr(printer)


@dataclass(frozen=True)
class _FlowConstraint(AttrConstraint[FlowAttr]):
    """Constrains a FlowAttr to use only state indices that are valid in the context of a number of
    input flows and output flows."""

    input_flows: IntVarConstraint
    output_flows: IntVarConstraint

    @staticmethod
    def _get_int_constraint_value(
        constraint_context: ConstraintContext, constraint: IntVarConstraint
    ) -> int:
        assert constraint.can_infer(constraint_context.int_variables), (
            f"Cannot verify constraint since {constraint.name} was not "
            "found in the constraint context. Constraints in operations or attributes using "
            "_FlowConstraint may need to be reordered."
        )
        return constraint.infer(constraint_context)

    @override
    def verify(
        self,
        attr: Attribute,
        constraint_context: ConstraintContext,
    ) -> None:
        base(FlowAttr).verify(attr, constraint_context)
        assert isinstance(attr, FlowAttr)

        number_of_input_flow_states = self._get_int_constraint_value(
            constraint_context, self.input_flows
        )
        if attr.input_state.data >= number_of_input_flow_states:
            msg = (
                f"Cannot use input flow state index {attr.input_state.data}"
                f" to index {number_of_input_flow_states} input flow states."
            )
            raise VerifyException(msg)

        number_of_output_flow_states = self._get_int_constraint_value(
            constraint_context, self.output_flows
        )
        if attr.output_state.data >= number_of_output_flow_states:
            msg = (
                f"Cannot use output flow state index {attr.output_state.data}"
                f" to index {number_of_output_flow_states} output flow states."
            )
            raise VerifyException(msg)

    @override
    def get_bases(self) -> set[type[Attribute]] | None:
        return {FlowAttr}

    @override
    def mapping_type_vars(
        self, type_var_mapping: Mapping[TypeVar, AttrConstraint | IntConstraint]
    ) -> AttrConstraint[FlowAttr]:
        return _FlowConstraint(
            IntVarConstraint(
                self.input_flows.name,
                self.input_flows.constraint.mapping_type_vars(type_var_mapping),
            ),
            IntVarConstraint(
                self.output_flows.name,
                self.output_flows.constraint.mapping_type_vars(type_var_mapping),
            ),
        )


@irdl_attr_definition
class ConcreteFlowAttr(ParametrizedAttribute):
    """A cross-dialect attribute which stores information about a single stabiliser flow.

    This attribute is intended to be attached to the attr-dict of an operation from another dialect
    (typically, qstruct.circuit) as part of a stab.concrete_flow_array to store stabiliser flows
    declared by the user or otherwise further up the compilation stack.

    The qubit indices of the input and output flow states are indexing into the qubits/qubit
    registers/stab.states stored in the operands of the attached op, as if all the qubit operands
    are in one big register. The measurement indices are indexing into the attached op's results.
    The validity of these indices is not verified by this attribute; this is the responsibility of
    the passes which use this attribute.

    This attribute is 'Concrete' because it stores the entire flow state of the input and output
    states in an isolated way, rather than just storing indices into a StateType (as FlowAttr does).
    """

    name = "stab.concrete_flow"

    _Q: ClassVar[IntConstraint] = MessageIntConstraint(
        IntVarConstraint("Qubits", AtLeast(0)),
        "Input and output flow state Pauli strings must have the same length.",
    )

    sign: BoolAttr
    measurements: ArrayAttr[IntAttr] = param_def(
        MessageConstraint(
            ArrayOfConstraint(
                SortedRangeOf(
                    RangeOf(IntAttrConstraint(AtLeast(0))),
                    key=lambda i: i.data,
                    strictly_increasing=True,
                )
            ),
            f"{name} measurement indices must be non-negative, sorted, and cannot contain "
            "duplicates.",
        )
    )
    input_state: PauliStringAttr = param_def(PauliStringAttr.constr(_Q))
    output_state: PauliStringAttr = param_def(PauliStringAttr.constr(_Q))

    def __init__(
        self,
        sign: BoolAttr | bool | Literal["+", "-"],
        measurements: ArrayAttr[IntAttr] | Iterable[IntAttr | int],
        input_state: PauliStringAttr | str,
        output_state: PauliStringAttr | str,
    ):
        if isinstance(sign, str):
            sign = sign == "+"
        if isinstance(sign, bool):
            sign = BoolAttr.from_bool(sign)
        measurements = ArrayAttr(
            sorted([IntAttr.get(i) for i in measurements], key=lambda i: i.data)
        )
        if isinstance(input_state, str):
            input_state = PauliStringAttr.new(
                PauliStringAttr.parse_inner_parameters(Parser(Context(), input_state))
            )
        if isinstance(output_state, str):
            output_state = PauliStringAttr.new(
                PauliStringAttr.parse_inner_parameters(Parser(Context(), output_state))
            )
        super().__init__(sign, measurements, input_state, output_state)

    @override
    def verify(self) -> None:
        # doesn't both start and end in I state
        if self.input_state.is_identity() and self.output_state.is_identity():
            msg = "Flow cannot start and finish in 'I' state."
            raise VerifyException(msg)

    @property
    def is_plus(self) -> bool:
        """True iff the sign of this flow is '+'."""
        return bool(self.sign.value.data)

    @property
    def is_minus(self) -> bool:
        """True iff the sign of this flow is '-'."""
        return not bool(self.sign.value.data)

    @property
    def measurement_indices(self) -> Sequence[int]:
        """The indices in the attached op's results of the measurements this flow uses."""
        return [int_attr.data for int_attr in self.measurements]

    def get_measurement_values(self, op: Operation) -> list[SSAValue]:
        """Get the SSAValues of the measurements this flow uses from the given op, which is assumed
        to be the op this attribute is attached to."""
        return [op.results[idx] for idx in self.measurement_indices]

    def is_used_as_measurement(self, result: OpResult) -> bool:
        """Return whether the given result is used as a measurement index in this flow, assuming
        this attribute is attached to result.op."""
        return result.index in self.measurement_indices

    def resize(self, new_length: int) -> ConcreteFlowAttr:
        """Return this concrete flow with both Pauli strings resized to ``new_length``."""
        return ConcreteFlowAttr(
            sign=self.sign,
            measurements=self.measurements,
            input_state=self.input_state.resize(new_length),
            output_state=self.output_state.resize(new_length),
        )

    def with_reindexed_measurements(
        self, *, shift: int = 0, removed_indices: set[int] | None = None
    ) -> ConcreteFlowAttr:
        """Get a new ConcreteFlowAttr with the measurement indices reindexed.

        Does nothing if none of the optional arguments are provided.

        Arguments:
            shift: A global shift to add to all measurement indices.
            removed_indices: The indices of results which we should treat as being removed from the
                attached op. The measurement indices will be reindexed as if these results were
                removed. They are assumed not to be used as measurement indices themselves.

        Returns:
            A new ConcreteFlowAttr with the same sign and flow states but with measurement indices
            reindexed as specified above.

        Raises:
            ValueError: If any of the removed indices are used in this flow, or if any index is
                negative after the shift.
        """
        removed_iter = iter(sorted(removed_indices or set()))
        removed_idx = next(removed_iter, None)
        offset = 0

        new_measurement_indices = []
        for index in self.measurement_indices:
            while removed_idx is not None and removed_idx < index:
                offset += 1
                removed_idx = next(removed_iter, None)
            if removed_idx == index:
                msg = f"Cannot remove output {index} as it is used as a measurement in {self}."
                raise ValueError(msg)
            new_index = index - offset + shift
            if new_index < 0:
                msg = f"Invalid negative measurement index {new_index} after shift."
                raise ValueError(msg)
            new_measurement_indices.append(new_index)

        return ConcreteFlowAttr(
            sign=self.sign,
            measurements=new_measurement_indices,
            input_state=self.input_state,
            output_state=self.output_state,
        )

    def sort_key(self) -> tuple[tuple[int, ...], tuple[int, ...], bool, tuple[int, ...]]:
        """Get a sortable value from this ConcreteFlowAttr for use in a list of concrete flows.

        Sorts by the input and output states, the sign, and the measurement indices in that order.
        """
        return (
            self.input_state.sort_key(),
            self.output_state.sort_key(),
            self.is_plus,
            tuple(self.measurement_indices),
        )

    @classmethod
    def parse_concrete_flow_attr(
        cls, parser: AttrParser | Parser
    ) -> tuple[BoolAttr, ArrayAttr[IntAttr], PauliStringAttr, PauliStringAttr]:
        """Parse the internal attributes of a ConcreteFlowAttr.

        Parses things like:
            <+:0,1,2,3>{I -> Y0}
            <-:>{X0 X1 -> Z0 Z2}
        """
        sign, measurement_indices = _parse_sign_and_measurements_header(parser)

        with parser.in_braces():
            input_state = PauliStringAttr.parse_qubit_pauli_states(parser)
            parser.parse_punctuation("->")
            output_state = PauliStringAttr.parse_qubit_pauli_states(parser)
            parser.parse_punctuation(":")
            length = parser.parse_integer(allow_boolean=False, allow_negative=False)
            input_pauli_string = PauliStringAttr(input_state, length)
            output_pauli_string = PauliStringAttr(output_state, length)

        return (sign, measurement_indices, input_pauli_string, output_pauli_string)

    @override
    @classmethod
    def parse_parameters(cls, parser: AttrParser) -> Sequence[Attribute]:
        with parser.in_angle_brackets():
            return cls.parse_concrete_flow_attr(parser)

    def print_concrete_flow_attr(self, printer: Printer) -> None:
        """Print the internal attributes of a ConcreteFlowAttr."""
        _print_sign_and_measurements_header(printer, self.is_plus, self.measurement_indices)

        with printer.in_braces():
            self.input_state.print_qubit_pauli_states(printer)
            printer.print_string(" -> ")
            self.output_state.print_qubit_pauli_states(printer)
            printer.print_string(" : ")
            printer.print_int(self.input_state.length.data)

    @override
    def print_parameters(self, printer: Printer) -> None:
        with printer.in_angle_brackets():
            self.print_concrete_flow_attr(printer)


@irdl_attr_definition
class ConcreteFlowArrayAttr(ParametrizedAttribute):
    """A cross-dialect attribute which stores information about the stabiliser flows of an op.

    This attribute is intended to be attached to the attr-dict of an operation from another dialect
    (typically, qstruct.circuit) to store stabiliser flows declared by the user or otherwise further
    up the compilation stack.

    This attribute puts no constraints on the concrete flows, except that there must be at least one
    and there must be no duplicate flows. It is the responsibility of passes using this attribute to
    verify any constraints they wish to put on the flows.
    """

    name = "stab.concrete_flow_array"

    KEY: ClassVar[str] = "stab.flows"
    """The standard key under which to store this attribute in the attr-dict of an operation.
    Passes that respect this attribute will look for it under this key. Final, do not modify."""
    DROPPABLE_FLOWS_KEY: ClassVar[str] = "stab.droppable_flows"
    """The standard key under which to store a UnitAttr iff the flows defined in the `stab.flows`
    Can be silently dropped, normally because they are automatically generated and might not form
    well defined flows across multiple circuits in all use-cases."""

    flows: ArrayAttr[ConcreteFlowAttr] = param_def(
        AllOf(
            (
                MessageConstraint(
                    ArrayOfConstraint(RangeOf(base(ConcreteFlowAttr)).of_length(AtLeast(1))),
                    f"A {name} must contain at least one {ConcreteFlowAttr.name}.",
                ),
                MessageConstraint(
                    ArrayOfConstraint(
                        SortedRangeOf(
                            RangeOf(base(ConcreteFlowAttr)),
                            key=ConcreteFlowAttr.sort_key,
                            strictly_increasing=True,
                        )
                    ),
                    f"{ConcreteFlowAttr.name}s must be unique and sorted first by their input and "
                    "output states, then by their sign, and then by their measurement indices.",
                ),
            )
        )
    )

    def __init__(self, flows: ArrayAttr[ConcreteFlowAttr] | Sequence[ConcreteFlowAttr]):
        flows = ArrayAttr(sorted(flows, key=ConcreteFlowAttr.sort_key))
        super().__init__(flows)

    @staticmethod
    def get(op: Operation) -> ConcreteFlowArrayAttr | None:
        """Get the ConcreteFlowArrayAttr attached to op with the standard key, if it exists."""
        attr = op.attributes.get(ConcreteFlowArrayAttr.KEY)
        if attr is not None and not isinstance(attr, ConcreteFlowArrayAttr):
            msg = (
                f"Expected attribute {ConcreteFlowArrayAttr.KEY} to be a ConcreteFlowArrayAttr, "
                f"got {attr.name}"
            )
            raise ValueError(msg)
        return attr

    def is_used_as_measurement(self, result: OpResult) -> bool:
        """Return whether the given result is used as a measurement index in any of the concrete
        flows in this array, assuming this attribute is attached to result.op."""
        return any(flow.is_used_as_measurement(result) for flow in self.flows)

    def resize(self, new_length: int) -> ConcreteFlowArrayAttr:
        """Return this array with every concrete flow resized to ``new_length``."""
        return ConcreteFlowArrayAttr([flow.resize(new_length) for flow in self.flows])

    def with_reindexed_measurements(
        self, *, shift: int = 0, removed_indices: set[int] | None = None
    ) -> ConcreteFlowArrayAttr:
        """Get a new ConcreteFlowArrayAttr with the measurement indices reindexed.
        Raises a ValueError if any of the removed indices are used in the flows or if any index
        would become negative after the shift.

        Arguments:
            shift: A global shift to add to all measurement indices.
            removed_indices: The indices of results which we should treat as being removed from the
                attached op. The measurement indices will be reindexed as if these results were
                removed. They are assumed not to be used as measurement indices themselves.

        Returns:
            A new ConcreteFlowArrayAttr with the same flows but with the measurement indices
            reindexed as specified above.
        """
        return ConcreteFlowArrayAttr(
            flows=[
                flow.with_reindexed_measurements(shift=shift, removed_indices=removed_indices)
                for flow in self.flows
            ]
        )

    @classmethod
    def parse_concrete_flow_array_attr(
        cls, parser: AttrParser | Parser
    ) -> ArrayAttr[ConcreteFlowAttr]:
        """Parse the internal list of concrete flows of a ConcreteFlowArrayAttr.

        Parses things like:
            [<+:0,1,2,3>{I -> Y0}, <-:>{X0 X1 -> Z0 Z2}]
        """

        def parse_concrete_flow() -> ConcreteFlowAttr:
            return ConcreteFlowAttr(*ConcreteFlowAttr.parse_concrete_flow_attr(parser))

        return ArrayAttr(
            parser.parse_comma_separated_list(
                delimiter=parser.Delimiter.SQUARE,
                parse=parse_concrete_flow,
            )
        )

    @override
    @classmethod
    def parse_parameters(cls, parser: AttrParser) -> Sequence[Attribute]:
        with parser.in_angle_brackets():
            return [cls.parse_concrete_flow_array_attr(parser)]

    def print_concrete_flow_array_attr(self, printer: Printer) -> None:
        """Print the internal list of concrete flows of a ConcreteFlowArrayAttr."""
        with printer.in_square_brackets():
            printer.print_list(
                self.flows, lambda flow: flow.print_concrete_flow_attr(printer), delimiter=", "
            )

    @override
    def print_parameters(self, printer: Printer) -> None:
        with printer.in_angle_brackets():
            self.print_concrete_flow_array_attr(printer)


@irdl_op_definition
class YieldOp(IRDLOperation):
    """The yielding operation for stab.circuit ops."""

    name = "stab.yield"

    measurements = var_operand_def(i1)
    arguments = var_operand_def(AnyAttr())

    assembly_format = (
        "` ` `[`($measurements^ `:` type($measurements))? `]` "
        "($arguments^ `:` type($arguments))? attr-dict"
    )

    traits = lazy_traits_def(
        lambda: (
            IsTerminator(),
            HasParent(CircuitOp),
            Pure(),
            NoQuantumEffect(),
        )
    )
    irdl_options = (AttrSizedOperandSegments(as_property=True),)

    def __init__(
        self,
        measurements: Sequence[SSAValue | Operation],
        arguments: Sequence[SSAValue | Operation],
    ):
        super().__init__(operands=[measurements, arguments])

    def concat(self, other: YieldOp) -> YieldOp:
        """Concatenate this yield with another by concatenating their measurements and arguments."""
        return YieldOp(
            measurements=self.measurements + other.measurements,
            arguments=self.arguments + other.arguments,
        )


@dataclass(frozen=True)
class _CircuitEntryArgsConstraint(RangeConstraint[AttributeCovT]):
    """Constrain a range to be a concatenation of 2 ranges. This uses an inferable 'qubits'
    constraint to determine the size of the first section, and the qubit_type constraint to
    constrain each element. The second section is then verified with the input_args RangeConstraint.
    """

    qubits: IntVarConstraint
    qubit_type: AttrConstraint[AttributeCovT]
    input_args: RangeConstraint[AttributeCovT]

    def _get_qubits_from_context(self, constraint_context: ConstraintContext) -> int:
        assert self.qubits.can_infer(constraint_context.int_variables), (
            "Cannot use entry args constraint since qubits constraint could not be inferred from "
            " the constraint context. Constraints in operations or attributes using "
            "_CircuitEntryArgsConstraint may need to be reordered."
        )
        number_of_qubits = self.qubits.infer(constraint_context)
        assert number_of_qubits is not None
        return number_of_qubits

    def _split_attrs(
        self, attrs: Sequence[Attribute], constraint_context: ConstraintContext
    ) -> tuple[Sequence[Attribute], Sequence[Attribute]]:
        number_of_qubits = self._get_qubits_from_context(constraint_context)
        if len(attrs) < number_of_qubits:
            msg = (
                f"Expected {number_of_qubits} qubit arguments but got {len(attrs)} block arguments."
            )
            raise VerifyException(msg)
        qubit_attrs = attrs[:number_of_qubits]
        input_attrs = attrs[number_of_qubits:]
        return tuple(qubit_attrs), tuple(input_attrs)

    @property
    def _qubit_range_constraint(self) -> RangeConstraint[AttributeCovT]:
        return RangeOf(self.qubit_type).of_length(self.qubits)

    @override
    def verify(
        self,
        attrs: Sequence[Attribute],
        constraint_context: ConstraintContext,
    ) -> None:
        qubit_attrs, input_attrs = self._split_attrs(attrs, constraint_context)

        self._qubit_range_constraint.verify(qubit_attrs, constraint_context)
        self.input_args.verify(input_attrs, constraint_context)

    @override
    def verify_length(self, length: int, constraint_context: ConstraintContext) -> None:
        number_of_qubits = self._get_qubits_from_context(constraint_context)
        number_of_inputs = length - number_of_qubits
        self._qubit_range_constraint.verify_length(number_of_qubits, constraint_context)
        self.input_args.verify_length(number_of_inputs, constraint_context)

    @override
    def variables(self) -> set[str]:
        """We don't consider the qubits IntVarConstraint itself to be extractable as we
        enforce that it exists in the context before we verify. But the inner constraint is still
        potentially available."""
        return (
            self.qubits.constraint.variables()
            | self.qubit_type.variables()
            | self.input_args.variables()
        )

    @override
    def mapping_type_vars(
        self, type_var_mapping: Mapping[TypeVar, AttrConstraint | IntConstraint]
    ) -> RangeConstraint[AttributeCovT]:
        return _CircuitEntryArgsConstraint(
            IntVarConstraint(
                self.qubits.name, self.qubits.constraint.mapping_type_vars(type_var_mapping)
            ),
            self.qubit_type.mapping_type_vars(type_var_mapping),
            self.input_args.mapping_type_vars(type_var_mapping),
        )


@irdl_custom_directive
class _CircuitBody(CustomDirective):
    """Custom printing and parsing declaration for the body part of a stab.circuit op with the form
    like:
        ```
        with (%q0, ..., %qx : !qcore.qubit), (%i0_ = %i0 : !..., ..., %iy_ = %iy : !...) {
            // block_args are: %q0, ..., %qx, %i0_, ..., %iy_
            ...
            stab.yield [%m0, ..., %mz] (%r1, ..., %rw : !r1_T, ..., !rw_T)
        }
        ```"""

    input_state: TypeDirective
    input_args: VariadicOperandVariable
    input_arg_types: TypeDirective
    body: RegionVariable
    output_args: TypeDirective

    @override
    def parse(self, parser: Parser, state: ParsingState) -> bool:
        """Parses the body part of a stab.circuit op.
        This parsing directive also parses input args (%i0...%iy)
        and sets the output args types based on the yield in the body.
        """
        parser.parse_keyword("with")

        # parse `(%q0, ..., %qx : !qcore.qubit)`
        with parser.in_parens():
            unresolved_qubit_vars = parser.parse_optional_undelimited_comma_separated_list(
                lambda: parser.parse_optional_argument(expect_type=False),
                lambda: parser.parse_argument(expect_type=False),
            )
            if unresolved_qubit_vars:
                parser.parse_punctuation(":")
                qubit_type = parser.parse_type()
                qubit_block_args = [var.resolve(qubit_type) for var in unresolved_qubit_vars]
            else:
                qubit_block_args = []

        parser.parse_punctuation(",")

        # parse `(%i0_ = %i0 : !..., ..., %iy_ = %iy : !...)`
        def parse_other_args() -> tuple[Parser.Argument, UnresolvedOperand]:
            unresolved_block_arg = parser.parse_argument(expect_type=False)
            parser.parse_punctuation("=")
            unresolved_input_arg = parser.parse_unresolved_operand()
            parser.parse_punctuation(":")
            arg_type = parser.parse_type()
            block_arg = unresolved_block_arg.resolve(arg_type)
            return block_arg, unresolved_input_arg

        other_args = parser.parse_comma_separated_list(parser.Delimiter.PAREN, parse_other_args)
        if other_args:
            other_block_args, input_args = zip(*other_args, strict=True)
            self.input_args.set(state, input_args)
            self.input_arg_types.set(state, [arg.type for arg in other_block_args])
        else:
            self.input_args.set_empty(state)
            self.input_arg_types.set_empty(state)
            other_block_args = ()

        # parse body: `{...}`
        body = parser.parse_region(qubit_block_args + list(other_block_args))
        self.body.set(state, body)

        # extract return types automatically from stab.yield
        if isinstance(yield_op := body.block.last_op, YieldOp):
            output_types = yield_op.arguments.types
            self.output_args.set(state, output_types)

        return True  # parsing is non-optional, so always return True

    @override
    def print(self, printer: Printer, state: PrintingState, op: IRDLOperation) -> None:
        """Prints the body part of a stab.circuit op.
        This printing directive also prints the input args (%i0...%iy)
        and the output args types based on the yield in the body.
        """
        with printer.indented():
            printer.print_string("\nwith ")

            input_state_type = cast(StateType, self.input_state.get(op)[0])
            assert isinstance(input_state_type, StateType)
            qubits = input_state_type.total_qubits

            # print `(%q0, ..., %qx : !qcore.qubit)`
            with printer.in_parens():
                qubit_block_args = self.body.get(op).block.args[:qubits]
                qubit_types = [arg.type for arg in qubit_block_args]
                printer.print_list(
                    qubit_block_args,
                    lambda arg: printer.print_block_argument(arg, print_type=False),
                )
                if qubit_types:
                    printer.print_string(" : ")
                    printer.print_attribute(qubit_types[0])

            printer.print_string(", ")

            # print `(%i0_ = %i0 : !..., ..., %iy_ = %iy : !...)`
            with printer.in_parens():
                other_block_args = self.body.get(op).block.args[qubits:]
                input_args = self.input_args.get(op)

                def print_args(args: tuple[BlockArgument, SSAValue]) -> None:
                    block_arg, input_arg = args
                    printer.print_block_argument(block_arg, print_type=False)
                    assert block_arg.type == input_arg.type
                    printer.print_string(" = ")
                    printer.print_ssa_value(input_arg)
                    printer.print_string(" : ")
                    printer.print_attribute(block_arg.type)

                printer.print_list(zip(other_block_args, input_args, strict=True), print_args)

            # print body
            body = self.body.get(op)
            printer.print_region(body, False, False)


@irdl_custom_directive
class _CircuitFlows(CustomDirective):
    """Custom printing and parsing declaration for an optional flows section of a Circuit Op.
    This will have the form:
        [<+>{I -> X1 Z2}, <-:0, 1, 2>{X0 Z1 -> I}]

    The Flow States can be referenced by their index (an integer) or by writing out the
    flow state (eg. 'X1 Z2').
    """

    flows: AttributeVariable

    input_state_ref: OperandVariable
    """This should be passed as `ref($operand)` in the custom assembly format, and gives access to
    a StateType that is used as input side context when printing and parsing FlowAttrs."""
    output_state_ref: TypeDirective
    """This should be passed as `ref(type($result))` in the custom assembly format, and gives
    access to a StateType that is used as output side context when printing and parsing
    FlowAttrs."""

    @override
    def parse(self, parser: Parser, state: ParsingState) -> bool:
        input_state_types = state.operand_types[self.input_state_ref.index]
        assert input_state_types is not None, (
            f"Cannot Parse. _CircuitFlows directive must come after {self.input_state_ref.name}."
        )
        assert len(input_state_types) == 1, (
            f"Cannot Parse. _CircuitFlows requires that {self.input_state_ref.name} has exactly "
            "one type."
        )
        if isinstance(input_state_types[0], StateType):
            input_flows = list(input_state_types[0].flow_states)
        else:
            input_flows = None

        output_ref_inner = self.output_state_ref.inner
        assert isinstance(output_ref_inner, ResultVariable), (
            "_CircuitFlows requires that output_state_ref is a 'type($result_variable)' directive."
        )
        output_state_types = state.result_types[output_ref_inner.index]
        assert output_state_types is not None, (
            f"Cannot Parse. _CircuitFlows directive must come after {output_ref_inner.name}."
        )
        assert len(output_state_types) == 1, (
            f"Cannot Parse. _CircuitFlows requires that {output_ref_inner.name} has exactly one "
            "type."
        )
        if isinstance(output_state_types[0], StateType):
            output_flows = list(output_state_types[0].flow_states)
        else:
            output_flows = None

        def parse_flow() -> FlowAttr:
            return FlowAttr(
                *FlowAttr.parse_flow_attr(
                    parser,
                    input_flow_states=input_flows,
                    output_flow_states=output_flows,
                )
            )

        flows = parser.parse_optional_comma_separated_list(parser.Delimiter.SQUARE, parse_flow)

        if flows is not None:
            self.flows.set(state, ArrayAttr(flows))
        else:
            self.flows.set_empty(state)
        return flows is not None

    @override
    def print(self, printer: Printer, state: PrintingState, op: IRDLOperation) -> None:
        input_state = self.input_state_ref.get(op).type
        assert isinstance(input_state, StateType)
        input_flows = list(input_state.flow_states)

        output_states = self.output_state_ref.get(op)
        assert output_states
        assert isinstance(output_states[0], StateType)
        output_flows = list(output_states[0].flow_states)

        state.print_whitespace(printer)

        flows = cast(ArrayAttr[FlowAttr], self.flows.get(op))
        assert isinstance(flows, ArrayAttr)

        with printer.in_square_brackets():
            printer.print_list(
                flows,
                lambda flow: flow.print_flow_attr(
                    printer,
                    input_flow_states=input_flows,
                    output_flow_states=output_flows,
                ),
            )

    @override
    def is_present(self, op: IRDLOperation) -> bool:
        return self.flows.get(op) is not None

    @override
    def is_anchorable(self) -> bool:
        return True

    @override
    def is_optional_like(self) -> bool:
        return True


@irdl_op_definition
class CircuitOp(IRDLOperation):
    """An operation representing a quantum circuit without branching control-flow, that uses
    stabiliser flows to manage detector finding and validating."""

    name = "stab.circuit"

    _Q: ClassVar[IntVarConstraint] = IntVarConstraint("Qubits", AtLeast(0))
    _QT: ClassVar[VarConstraint] = VarConstraint("Qubit Type", AnyAttr())
    _I_ARGS: ClassVar[RangeVarConstraint] = RangeVarConstraint("Input Args", RangeOf(AnyAttr()))

    _I_F: ClassVar[IntVarConstraint] = IntVarConstraint("Input Flow States", AtLeast(0))
    _O_F: ClassVar[IntVarConstraint] = IntVarConstraint("Output Flow States", AtLeast(0))

    input = operand_def(StateType.constr(_Q, _QT, _I_F))
    input_args = var_operand_def(_I_ARGS)

    body = region_def("single_block", entry_args=_CircuitEntryArgsConstraint(_Q, _QT, _I_ARGS))

    flows = opt_prop_def(
        AllOf(
            (
                MessageConstraint(
                    ArrayOfConstraint(RangeOf(_FlowConstraint(_I_F, _O_F))),
                    f"The 'flows' of a {name} must be an {ArrayAttr.name} of {FlowAttr.name}s that "
                    f"each index into the input and output {StateType.name} flow states.",
                ),
                MessageConstraint(
                    ArrayOfConstraint(
                        SetOf(
                            RangeOf(base(FlowAttr)),
                            key=lambda f: f.input_state_index,
                            filter=lambda f: f.input_state_index != I_STATE_INDEX,
                        )
                    ),
                    f"There must not be more than one {FlowAttr.name} that starts with each input "
                    f"flow state index unless it is I ({I_STATE_INDEX}).",
                ),
                MessageConstraint(
                    ArrayOfConstraint(
                        SetOf(
                            RangeOf(base(FlowAttr)),
                            key=lambda f: f.output_state_index,
                            filter=lambda f: f.output_state_index != I_STATE_INDEX,
                        )
                    ),
                    f"There must not be more than one {FlowAttr.name} that ends with each output "
                    f"flow state index unless it is I ({I_STATE_INDEX}).",
                ),
                MessageConstraint(
                    ArrayOfConstraint(
                        SortedRangeOf(
                            RangeOf(base(FlowAttr)), key=FlowAttr.sort_key, strictly_increasing=True
                        )
                    ),
                    f"{FlowAttr.name}s must be sorted, by input index, then output index.",
                ),
            )
        )
    )

    output = result_def(StateType.constr(_Q, _QT, _O_F))

    output_args = var_result_def()

    traits = traits_def(
        IsCircuit(),
        SingleBlockImplicitTerminator(YieldOp),
        RecursiveQuantumEffect(),
        RecursiveMemoryEffect(),
        IsolatedFromAbove(),
    )

    assembly_format = (
        "$input `:` type($input) `->` type($output) "
        "custom<_CircuitBody>("
        "   ref(type($input)), $input_args, type($input_args), $body, type($output_args)"
        ") "
        "(custom<_CircuitFlows>($flows, ref($input), ref(type($output)))^)?"
        "attr-dict"
    )

    custom_directives = (_CircuitBody, _CircuitFlows)

    def __init__(
        self,
        input_state: SSAValue,
        output_state_type: StateType,
        *,
        input_args: Sequence[SSAValue],
        body: Region | Block | Sequence[Operation],
        flows: ArrayAttr[FlowAttr] | Iterable[FlowAttr] | None = None,
        output_args_types: Sequence[Attribute] | None = None,
        attributes: Mapping[str, Attribute | None] | None = None,
    ):
        if isinstance(body, Block):
            body_region: Region | Sequence[Block] | Sequence[Operation] | None = [body]
        else:
            body_region = body

        properties = {}
        if flows is not None:
            properties["flows"] = ArrayAttr(sorted(flows, key=FlowAttr.sort_key))

        if output_args_types is None:
            yield_source: Region | Block | Sequence[Operation] | Operation | None = body
            if isinstance(yield_source, Region):
                yield_source = yield_source.last_block
            if isinstance(yield_source, Block):
                yield_source = yield_source.last_op
            if isinstance(yield_source, Sequence):
                yield_source = yield_source[-1]
            if isinstance(yield_source, YieldOp):
                output_args_types = yield_source.arguments.types

        super().__init__(
            operands=[input_state, input_args],
            result_types=[output_state_type, output_args_types],
            properties=properties,
            attributes=attributes,
            regions=[body_region],
        )

    @property
    def qubit_block_args(self) -> Sequence[BlockArgument]:
        """The qubit block arguments of the circuit body."""
        qubits = cast(StateType, self.input.type).total_qubits
        return self.body.block.args[:qubits]

    @property
    def other_block_args(self) -> Sequence[BlockArgument]:
        """The non-qubit block arguments of the circuit body."""
        qubits = cast(StateType, self.input.type).total_qubits
        return self.body.block.args[qubits:]

    @property
    def yield_op(self) -> YieldOp:
        """Get the YieldOp at the end of the circuit body."""
        return cast(YieldOp, self.body.block.last_op)  # If this is unsafe, irdl would catch it.

    def block_arg_to_input_arg(
        self, block_arg: BlockArgument[AttributeCovT]
    ) -> SSAValue[AttributeCovT]:
        """Get the input argument corresponding to the given non-qubit block argument."""
        try:
            index = self.other_block_args.index(block_arg)
        except ValueError:
            msg = f"{block_arg} is not a non-qubit block argument of this circuit."
            raise ValueError(msg) from None
        return cast(BlockArgument[AttributeCovT], self.input_args[index])

    def output_arg_to_yield_arg(
        self, output_arg: SSAValue[AttributeCovT]
    ) -> SSAValue[AttributeCovT]:
        """Get the yield op argument corresponding to the given output argument of the circuit."""
        try:
            index = self.output_args.index(output_arg)
        except ValueError:
            msg = f"{output_arg} is not an output argument of this circuit."
            raise ValueError(msg) from None
        return cast(SSAValue[AttributeCovT], self.yield_op.arguments[index])

    @override
    def verify_(self) -> None:
        """Verify that the yielded SSAValues at the end of the regions match the SSAValues returned
        by the op. Additionally verify no qcore operations are present in circuit body."""
        if len(self.yield_op.arguments.types) != len(self.output_args):
            msg = (
                "Mismatched number of output_args and yielded values: "
                f"{len(self.yield_op.arguments.types)} != {len(self.output_args)}"
            )
            raise VerifyException(msg)
        for i, (y, r) in enumerate(
            zip(self.yield_op.arguments.types, self.output_args, strict=True)
        ):
            if y != r.type:
                msg = (
                    f"Mismatched output_args type and yielded type at position {i}: "
                    f"{y} != {r.type}."
                )
                raise VerifyException(msg)

        if self.flows:
            number_of_measurements = len(self.yield_op.measurements)
            for flow in self.flows:
                if any(m.data >= number_of_measurements for m in flow.measurements):
                    msg = (
                        "Cannot use measurement indices: "
                        f"[{','.join([str(m.data) for m in flow.measurements.data])}] to index "
                        f"{number_of_measurements} yielded measurements."
                    )
                    raise VerifyException(msg)

        if any(op.dialect_name() == qcore.QCore.name for op in self.body.ops):
            msg = "Cannot use qcore ops in a stab.circuit body."
            raise VerifyException(msg)

    def _find_input_flow_state(self, flow_state: PauliStringAttr) -> int | None:
        """Get the index of a flow state in the circuit's input flow states.

        Args:
            flow_state: The flow state to search for.

        Returns:
            The index of the given flow state within the circuit's input flow
            states, or `I_STATE_INDEX` if it is the identity state. Returns
            `None` if the flow state is not present.
        """
        if flow_state.is_identity():
            return I_STATE_INDEX
        try:
            return self.input_flows.index(flow_state)
        except ValueError:
            return None

    def _find_output_flow_state(self, flow_state: PauliStringAttr) -> int | None:
        """Get the index of a flow state in the circuit's output flow states.

        Args:
            flow_state: The flow state to search for.

        Returns:
            The index of the given flow state within the circuit's output flow
            states, or `I_STATE_INDEX` if it is the identity state. Returns
            `None` if the flow state is not present.
        """
        if flow_state.is_identity():
            return I_STATE_INDEX
        try:
            return self.output_flows.index(flow_state)
        except ValueError:
            return None

    def find_flow(
        self, input_flow_state: PauliStringAttr, output_flow_state: PauliStringAttr
    ) -> FlowAttr | None:
        """Find a flow between the given input and output flow states.

        Args:
            input_flow_state: The source flow state to search for.
            output_flow_state: The destination flow state to search for.

        Returns:
            The matching flow if one exists from the input to the output flow
            state; otherwise `None`.
        """
        input_idx = self._find_input_flow_state(input_flow_state)
        output_idx = self._find_output_flow_state(output_flow_state)

        # If either state isn't present in the respective input/output flow sets, no flow exists.
        if input_idx is None or output_idx is None or self.flows is None:
            return None
        return next(
            (
                flow
                for flow in self.flows
                if flow.input_state_index == input_idx and flow.output_state_index == output_idx
            ),
            None,
        )

    @property
    def input_flows(self) -> Sequence[PauliStringAttr]:
        """Get the sequence of input flow states of the circuit.

        Returns:
            The input flow states for this circuit.
        """
        return cast(StateType, self.input.type).states

    @property
    def output_flows(self) -> Sequence[PauliStringAttr]:
        """Get the sequence of output flow states of the circuit.

        Returns:
            The output flow states for this circuit.
        """
        return self.output.type.states

    @property
    def used_input_flow_states(self) -> Sequence[PauliStringAttr]:
        """Returns the non-identity input flow states used by the annotated flows on the circuit."""
        if not self.flows:
            return []
        return [
            self.input_flows[flow.input_state_index]
            for flow in self.flows
            if flow.input_state_index >= 0
        ]

    @property
    def used_output_flow_states(self) -> Sequence[PauliStringAttr]:
        """Returns the non-identity output flow states used by flows on the circuit."""
        if not self.flows:
            return []
        return [
            self.output_flows[flow.output_state_index]
            for flow in self.flows
            if flow.output_state_index >= 0
        ]

    def convert_flow_mmt_to_ssa(self, flow: FlowAttr) -> OrderedSet[SSAValue[I1]]:
        """Map a flow's measurement indices to SSA values from the circuit's yield.

        Args:
            flow: The flow whose measurements should be converted.

        Returns:
            The set of SSA values corresponding to the flow's measurement
            indices.

        Raises:
            ValueError: If the given flow is not present on this circuit.
        """
        if not self.flows or flow not in self.flows:
            msg = "Flow input is not found in the circuit op."
            raise ValueError(msg)
        return OrderedSet(
            cast(SSAValue[I1], self.yield_op.measurements[idx]) for idx in flow.measurement_indices
        )

    def find_flow_outputs(
        self, flow_state: PauliStringAttr
    ) -> list[tuple[PauliStringAttr, OrderedSet[SSAValue[I1]]]]:
        """Find outputs and measurements for flows starting with a given input state.

        Args:
            flow_state: The input flow state to search for.

        Returns:
            A list of pairs where each pair contains the output flow state and
            the set of SSA measurement values used by the corresponding flow.
            Returns an empty list if no flows start from the given input state.
        """
        input_idx = self._find_input_flow_state(flow_state)
        flow_outputs: list[tuple[PauliStringAttr, OrderedSet[SSAValue[I1]]]] = []
        if input_idx is None or not self.flows:
            return flow_outputs
        for flow in self.flows:
            if flow.input_state_index == input_idx:
                # Map output index to a PauliStringAttr; handle I_STATE_INDEX specially
                out_state = (
                    PauliStringAttr.identity(self.output.type.total_qubits)
                    if flow.output_state_index == I_STATE_INDEX
                    else self.output_flows[flow.output_state_index]
                )
                flow_outputs.append((out_state, self.convert_flow_mmt_to_ssa(flow)))
        return flow_outputs

    def relabel_flows_from_flow_states(
        self, input_flow_states: list[PauliStringAttr], output_flow_states: list[PauliStringAttr]
    ) -> list[FlowAttr]:
        """Relabel existing flows given candidate additions to input/output flow states.

        Args:
            input_flow_states: Candidate flow states to add on the input side.
            output_flow_states: Candidate flow states to add on the output side.

        Returns:
            The relabeled flows as a list. Note that ``self.flows`` is not updated
            in this method. If the circuit has no flows an empty list is returned.
        """

        def make_index_mapping(
            old_flows: Sequence[PauliStringAttr], new_flows: Sequence[PauliStringAttr]
        ) -> dict[int, int]:
            # Collect what the new flows would look like into an indexed iterator
            input_iter = enumerate(
                sorted(
                    set(old_flows)
                    | (
                        set(new_flows)
                        - {PauliStringAttr.identity(cast(StateType, self.input.type).total_qubits)}
                    ),
                    key=PauliStringAttr.sort_key,
                )
            )
            # Generate a mapping from the existing flow indices to the new indices
            return {
                i: next(filter(lambda x: x[1] == state, input_iter))[0]
                for i, state in enumerate(old_flows)
            } | {I_STATE_INDEX: I_STATE_INDEX}

        input_index_map = make_index_mapping(self.input_flows, input_flow_states)
        output_index_map = make_index_mapping(self.output_flows, output_flow_states)

        return [
            FlowAttr(
                flow.sign,
                flow.measurements,
                input_index_map[flow.input_state_index],
                output_index_map[flow.output_state_index],
            )
            for flow in self.flows or []
        ]

    def add_measurements_to_yield(
        self, mmt_to_add: Iterable[SSAValue[I1]], rewriter: PatternRewriter
    ) -> None:
        """Append extra measurement SSA values to the circuit's yield.

        Assumes that all measurement values come from the same circuit body.
        Duplicate measurements are not added to the yield; the provided list of measurements
        will be deduplicated and only the earliest appearance of each measurement will be kept.

        Args:
            mmt_to_add: Measurement SSA values to append to the yield if not
                already present.
            rewriter: Optional rewriter to use when replacing the terminator.
        """
        to_append = OrderedSet[SSAValue[I1]]()
        for meas in mmt_to_add:
            if meas not in self.yield_op.measurements:
                to_append.add(meas)

        if not to_append:
            return

        new_yield = YieldOp(
            measurements=[*self.yield_op.measurements, *to_append],
            arguments=list(self.yield_op.arguments),
        )
        rewriter.replace_op(self.yield_op, new_yield)


@irdl_op_definition
class StateMakeOp(IRDLOperation):
    """An operation that constructs a stabiliser state for working with stab.circuits ops etc.
    States created by this operation must have no flow states."""

    name = "stab.state.make"

    _Q: ClassVar[IntVarConstraint] = IntVarConstraint("Qubits", AtLeast(0))
    _QT: ClassVar[VarConstraint] = VarConstraint("Qubit Type", AnyAttr())

    input_qubits = var_operand_def(RangeOf(_QT).of_length(_Q))
    output = result_def(
        StateType.constr(
            _Q,
            _QT,
            MessageIntConstraint(
                EqIntConstraint(0),
                f"The state created by {name} cannot have any flow states.",
            ),
        )
    )

    traits = traits_def(Pure(), NoQuantumEffect())

    assembly_format = (
        " (`(` $input_qubits^ `:` "
        "custom<RepeatedOperandType>(type($input_qubits), ref($input_qubits)) `)`)?"
        "`->` type($output) attr-dict"
    )

    custom_directives = (RepeatedOperandType,)

    def __init__(
        self,
        input_qubits: Sequence[SSAValue],
        state_type: StateType,
        *,
        attributes: Mapping[str, Attribute | None] | None = None,
    ):
        super().__init__(
            operands=[input_qubits],
            result_types=[state_type],
            attributes=attributes,
        )


@irdl_op_definition
class StateCastOp(IRDLOperation):
    """An operation that casts between stabiliser states with the same number and type of qubits.
    Can only remove flow states, not add them."""

    name = "stab.state.cast"

    _Q: ClassVar[IntVarConstraint] = IntVarConstraint("Qubits", AtLeast(0))
    _QT: ClassVar[VarConstraint] = VarConstraint("Qubit Type", AnyAttr())

    input = operand_def(StateType.constr(_Q, _QT, AnyInt()))
    output = result_def(StateType.constr(_Q, _QT, AnyInt()))

    traits = traits_def(Pure(), NoQuantumEffect())

    assembly_format = " `(` $input `)` type($input) `->` type($output) attr-dict"

    def __init__(
        self,
        input_state: SSAValue,
        output_state_type: StateType,
        *,
        attributes: Mapping[str, Attribute | None] | None = None,
    ):
        super().__init__(
            operands=[input_state],
            result_types=[output_state_type],
            attributes=attributes,
        )

    @override
    def verify_(self) -> None:
        """Verify that no flow states are added in the cast."""
        input_state_type = cast(StateType, self.input.type)
        if not set(self.output.type.flow_states).issubset(input_state_type.flow_states):
            added_states = set(self.output.type.flow_states) - set(input_state_type.flow_states)
            msg = f"Invalid state cast: the flow states {added_states} were added."
            raise VerifyException(msg)

    @property
    def output_flow_states(self) -> set[PauliStringAttr]:
        """Get the remaining flow states in the output of the cast."""
        return set(self.output.type.states)

    @property
    def discarded_flow_states(self) -> set[PauliStringAttr]:
        """Get the flow states that are discarded by the cast."""
        input_state_type = cast(StateType, self.input.type)
        return set(input_state_type.states) - set(self.output.type.states)


class _StatePermuteOpHasCanonicalizationPatternsTrait(HasCanonicalizationPatternsTrait):
    @override
    @classmethod
    def get_canonicalization_patterns(cls) -> tuple[RewritePattern, ...]:
        from deltakit_compile.passes.canonicalisation.stabiliser import (  # noqa: PLC0415
            CombineChainedPermutes,
            RemoveRedundantPermute,
        )  # Imported here to avoid circular imports.

        return (RemoveRedundantPermute(), CombineChainedPermutes())


_T = TypeVar("_T")


@irdl_op_definition
class StatePermuteOp(IRDLOperation):
    """An operation to permute the qubit indices of a stabiliser state while preserving
    the correct flows states."""

    name = "stab.state.permute"

    _Q: ClassVar[IntVarConstraint] = IntVarConstraint("Qubits", AtLeast(0))
    _QT: ClassVar[VarConstraint] = VarConstraint("Qubit Type", AnyAttr())

    input = operand_def(StateType.constr(_Q, _QT, AnyInt()))
    output = result_def(StateType.constr(_Q, _QT, AnyInt()))
    permutation = attr_def(
        ArrayOfConstraint(SetOf(RangeOf(IntAttr.constr(AtLeast(0)))).of_length(_Q))
    )
    """Permutation represented as an array of integer indices, where i -> permutation[i].
    Entries are constrained to be non-negative and form a set the same size as the original
    and are verified to be a bijective mapping of the qubits."""

    traits = traits_def(
        Pure(), NoQuantumEffect(), _StatePermuteOpHasCanonicalizationPatternsTrait()
    )

    # Parse/print the permutation as a plain list of integers wrapped in angle brackets, e.g.:
    #   stab.state.permute <[2, 0, 1]> (%in : !stab.state<...>) -> !stab.state<...>
    assembly_format = (
        "`<` "
        f"{PlainArrayOfIntAttrDirective.use('$permutation')} "
        "`>` "
        "`(` $input `:` type($input) `)` attr-dict `->` type($output)"
    )

    custom_directives = (PlainArrayOfIntAttrDirective,)

    def __init__(
        self,
        input_state: SSAValue[StateType],
        permutation: ArrayAttr[IntAttr] | Sequence[int],
    ):
        perm_attr = (
            ArrayAttr([IntAttr(i) for i in permutation])
            if isinstance(permutation, Sequence)
            else permutation
        )
        perm_data = (
            [i.data for i in permutation] if isinstance(permutation, ArrayAttr) else permutation
        )
        result_type = StateType(
            qubits=input_state.type.qubits,
            qubit_type=input_state.type.qubit_type,
            flow_states=[f.permute_indices(perm_data) for f in input_state.type.flow_states],
        )
        super().__init__(
            operands=[input_state],
            result_types=[result_type],
            attributes={"permutation": perm_attr},
        )

    @override
    def verify_(self) -> None:
        """Verify that the permutation is valid and the output state
        is result of this permutation."""
        if set(self.permutation_list) != set(range(len(self.permutation_list))):
            msg = "Permutation given does not define a permutation map."
            raise VerifyException(msg)
        flow_states = cast(StateType, self.input.type).flow_states
        if (expected_flows := {self.permute_flow(flow) for flow in flow_states}) != (
            got_flows := set(self.output.type.flow_states)
        ):
            wrong_state_msg = (
                "stab.state.permute result type does not match the permuted flow states. "
                f"Expected flow states: {PauliStringAttr.collection_as_str(expected_flows)}, "
                f"got: {PauliStringAttr.collection_as_str(got_flows)}."
            )
            raise VerifyException(wrong_state_msg)

    @property
    def permutation_list(self) -> list[int]:
        """Get the permutation as a list of integers."""
        return [i.data for i in self.permutation]

    @property
    def is_identity(self) -> bool:
        """Check if the permutation is the identity (does not change the order of elements)."""
        return self.is_identity_permutation(self.permutation_list)

    def permute_flow(self, flow_state: PauliStringAttr) -> PauliStringAttr:
        """Permute an input flow state according to this op's permutation."""
        return flow_state.permute_indices(self.permutation_list)

    def permute_list(self, input_sequence: Sequence[_T]) -> list[_T]:
        """Permute an input sequence according to this op's permutation.
        The input sequence must be the same length as the size of this op's permutation."""
        return self.apply_permutation(self.permutation_list, input_sequence)

    @staticmethod
    def apply_permutation(permutation: list[int], input_sequence: Sequence[_T]) -> list[_T]:
        """Permute an input sequence according to the permutation.
        The input sequence must be the same length as the permutation.
        The permutation must be a valid permutation list (include all integers from 0 to its length)
        """
        if len(permutation) != len(input_sequence):
            msg = "Permutation and input sequence have different lengths"
            raise ValueError(msg)
        if set(permutation) != set(range(len(permutation))):
            msg = "Input does not define a valid permutation map"
            raise ValueError(msg)
        output: list[_T | None] = [None for _ in range(len(permutation))]
        for new_idx, element in zip(permutation, input_sequence, strict=True):
            output[new_idx] = element
        return cast(list[_T], output)

    @staticmethod
    def invert_permutation(permutation: Sequence[int]) -> list[int]:
        """Get the permutation that undoes the given permutation.
        The input must be a valid permutation - contain all values
        in [0, |permutation|) exactly once."""
        reorder_map = {p: idx for idx, p in enumerate(permutation)}
        if set(reorder_map) != set(range(len(permutation))):
            msg = "Input does not define a valid permutation map"
            raise ValueError(msg)
        return [reorder_map[i] for i in range(len(reorder_map))]

    @staticmethod
    def is_identity_permutation(permutation: Iterable[int]) -> bool:
        """Returns True if the given permutation is the identity permutation, otherwise returns
        False."""
        return all(a == b for a, b in zip(permutation, itertools.count(), strict=False))

    @staticmethod
    def calculate_permutation_from_states(
        inputs: Sequence[SSAValue[StateType]], outputs: Sequence[SSAValue[StateType]]
    ) -> list[int]:
        """Calculate the qubit permutation corresponding to rearranging inputs into outputs,
        assuming outputs is a rearrangement of inputs."""
        in_set = set(inputs)
        if len(inputs) != len(in_set) or len(inputs) != len(outputs) or in_set != set(outputs):
            msg = "The outputs sequence is not a permutation of the inputs sequence"
            raise ValueError(msg)
        qubit_offset = 0
        output_ranges = {
            state: range(qubit_offset, qubit_offset := qubit_offset + state.type.total_qubits)
            for state in outputs
        }
        return list(itertools.chain(*(output_ranges[state] for state in inputs)))


class _StateConcatenateOpHasCanonicalizationPatternsTrait(HasCanonicalizationPatternsTrait):
    @override
    @classmethod
    def get_canonicalization_patterns(cls) -> tuple[RewritePattern, ...]:
        from deltakit_compile.passes.canonicalisation.stabiliser import (  # noqa: PLC0415
            CombineChainedConcatenates,
            CombineConcatenatedStateMake,
            RemoveRedundantConcatenate,
            ReplaceConcatenateAfterSplitWithPermute,
        )  # Imported here to avoid circular imports.

        return (
            RemoveRedundantConcatenate(),
            CombineChainedConcatenates(),
            ReplaceConcatenateAfterSplitWithPermute(),
            CombineConcatenatedStateMake(),
        )


@irdl_op_definition
class StateConcatenateOp(IRDLOperation):
    """Merge multiple stabiliser states into one with qubits in the order provided.

    Semantics:
        - All input states must have the same qubit *type*.
        - The output state's qubit count is the sum of the input qubit counts, and the qubits
          appear in operand order.
        - The output state's flow states are the concatenation of the input flow states, where
          flow states from later operands have their qubit indices shifted by the number of qubits
          in all preceding operands.

    """

    name = "stab.state.concatenate"

    _Q: ClassVar[IntConstraint] = MessageIntConstraint(
        IntVarConstraint("Qubit count", AnyInt()),
        "The number of qubits in input and output do not match.",
    )
    _QT: ClassVar[VarConstraint] = VarConstraint("Qubit Type", AnyAttr())

    inputs = var_operand_def(
        SumOver(
            RangeOf(
                StateType.constr(
                    qubits_constraint=AnyInt(), qubit_type_constraint=_QT, flow_states=AnyInt()
                )
            ),
            lambda state_type: state_type.total_qubits,  # type: ignore[arg-type]
            _Q,
        ).of_length(AtLeast(1))
    )
    output = result_def(
        StateType.constr(
            qubits_constraint=_Q,
            qubit_type_constraint=_QT,
            flow_states=AnyInt(),
        )
    )

    assembly_format = "`(` $inputs `:` type($inputs) `)` attr-dict `->` type($output)"

    traits = traits_def(
        Pure(), NoQuantumEffect(), _StateConcatenateOpHasCanonicalizationPatternsTrait()
    )

    @override
    def verify_(self) -> None:
        inputs: list[StateType] = [cast(StateType, state.type) for state in self.inputs]
        out_ty = cast(StateType, self.output.type)

        expected_states = StateType.merge_and_relabel_flow_states(inputs)

        if expected_states != list(out_ty.flow_states):
            msg = (
                "stab.state.concatenate result type does not match the concatenation of its "
                f"inputs. Expected {PauliStringAttr.collection_as_str(expected_states)}, "
                f"got {out_ty}."
            )
            raise VerifyException(msg)

    def __init__(self, states: Sequence[SSAValue[StateType]]) -> None:
        result_type = StateType(
            qubits=sum(state.type.total_qubits for state in states),
            qubit_type=states[0].type.qubit_type,
            flow_states=StateType.merge_and_relabel_flow_states(
                [cast(StateType, state.type) for state in states]
            ),
        )
        super().__init__(operands=(states,), result_types=(result_type,))

    def input_to_output_flow(
        self, input_state: SSAValue, flow_state: PauliStringAttr
    ) -> PauliStringAttr:
        """Get the output flow state for a given flow state from a given input state.

        No verification is done that the given flow state is actually a flow state of the given
        input state. Raises ValueError if the input state is not one of the inputs to this op.
        """
        total_qubits = self.output.type.total_qubits
        qubit_offset = 0
        for input_ in self.inputs:
            if input_ == input_state:
                return flow_state.shift_qubit_indices(qubit_offset, new_length=total_qubits)
            qubit_offset += cast(StateType, input_.type).total_qubits

        msg = f"Input state {input_state} not found in inputs."
        raise ValueError(msg)


class _StateSplitOpHasCanonicalizationPatternsTrait(HasCanonicalizationPatternsTrait):
    @override
    @classmethod
    def get_canonicalization_patterns(cls) -> tuple[RewritePattern, ...]:
        from deltakit_compile.passes.canonicalisation.stabiliser import (  # noqa: PLC0415
            CombineChainedSplits,
            RemoveRedundantSplit,
            RemoveRedundantSplitAfterConcatenate,
        )  # Imported here to avoid circular imports.

        return (
            RemoveRedundantSplit(),
            RemoveRedundantSplitAfterConcatenate(),
            CombineChainedSplits(),
        )


@irdl_op_definition
class StateSplitOp(IRDLOperation):
    """Split a stabiliser state into multiple states.

    The split is given by a partition of qubit indices into disjoint sets. Each output contains
    exactly the flow states whose support lies entirely within that partition element.

    If any flow state has support spanning 2 or more partition elements, verification of
    StateType will fail.
    """

    name = "stab.state.split"

    _Q: ClassVar[IntConstraint] = MessageIntConstraint(
        IntVarConstraint("Qubit count", AnyInt()),
        "The number of qubits in input and output do not match.",
    )
    _QT: ClassVar[VarConstraint] = VarConstraint("Qubit Type", AnyAttr())

    input = operand_def(StateType.constr(_Q, _QT, AnyInt()))
    outputs = var_result_def(
        SumOver(
            RangeOf(StateType.constr(AnyInt(), _QT, AnyInt())),
            lambda state_type: state_type.total_qubits,  # type: ignore[arg-type]
            _Q,
        )
    )

    assembly_format = "`(` $input `:` type($input) `)` attr-dict `->` type($outputs)"

    traits = traits_def(Pure(), NoQuantumEffect(), _StateSplitOpHasCanonicalizationPatternsTrait())

    @staticmethod
    def _partition_and_relabel_flow_states(
        flow_states: Iterable[PauliStringAttr], qubit_reg_sizes: Sequence[int]
    ) -> Iterator[list[PauliStringAttr]]:
        """Partition flow states across output registers and relabel qubit indices.

        This helper splits the input `flow_states` according to the contiguous register sizes
        given by `qubit_reg_sizes`.

        For each output register, it yields the subset of flow states whose support lies entirely
        within that register, with qubit indices shifted so that the register's first qubit becomes
        index 0.

        Args:
            flow_states: Flow states expressed in the *common* qubit index space and sorted by
                their minimum qubit index.
            qubit_reg_sizes: Sizes of each output register partition. The registers are assumed to
                be contiguous and in order.

        Yields:
            One list of relabelled flow states per output register.

        Raises:
            ValueError: If any flow state has support spanning 2 or more partitions.
        """
        output_index = 0
        min_qubit = 0
        next_min_qubit = min_qubit + qubit_reg_sizes[output_index]

        output_state: list[PauliStringAttr] = []
        for state in flow_states:
            state_min_qubit = state.get_min_qubit_index()

            while state_min_qubit >= next_min_qubit:
                yield output_state
                output_state = []
                output_index += 1
                min_qubit = next_min_qubit
                next_min_qubit = min_qubit + qubit_reg_sizes[output_index]

            if state.get_max_qubit_index() >= next_min_qubit:
                msg = f"Flow state {state} cannot be partitioned."
                raise ValueError(msg)

            output_state.append(
                state.shift_qubit_indices(-min_qubit, new_length=qubit_reg_sizes[output_index])
            )
        yield output_state
        output_index += 1
        yield from [[] for _ in range(len(qubit_reg_sizes) - output_index)]

    @override
    def verify_(self) -> None:
        input_state_type = cast(StateType, self.input.type)
        output_state_types = [cast(StateType, v.type) for v in self.outputs]
        reg_sizes = [t.total_qubits for t in output_state_types]

        try:
            splits = StateSplitOp._partition_and_relabel_flow_states(
                input_state_type.flow_states.data, reg_sizes
            )
        except ValueError as e:
            raise VerifyException(str(e)) from e

        for output_state, expected_flows in zip(output_state_types, splits, strict=True):
            if set(output_state.flow_states.data) != set(expected_flows):
                msg = (
                    "stab.state.split result types do not match the partitioned flow states. "
                    f" Expected flow states {PauliStringAttr.collection_as_str(expected_flows)}, "
                    f"got {output_state}."
                )
                raise VerifyException(msg)

    def __init__(self, state: SSAValue[StateType], qubit_reg_sizes: Sequence[int]) -> None:
        flow_state_splits = StateSplitOp._partition_and_relabel_flow_states(
            state.type.flow_states.data, qubit_reg_sizes
        )
        qubit_type = state.type.qubit_type
        state_types = [
            StateType(reg_size, qubit_type, flows)
            for flows, reg_size in zip(flow_state_splits, qubit_reg_sizes, strict=True)
        ]
        super().__init__(operands=(state,), result_types=(state_types,))

    def output_to_input_flow(
        self, output_state: SSAValue, flow_state: PauliStringAttr
    ) -> PauliStringAttr:
        """Get the input flow state for a given flow state from a given output state.

        No verification is done that the given flow state is actually a flow state of the given
        output state. Raises ValueError if the output state is not one of the outputs of this op.
        """
        total_qubits = cast(StateType, self.input.type).total_qubits
        qubit_offset = 0
        for output_ in self.outputs:
            if output_ == output_state:
                return flow_state.shift_qubit_indices(qubit_offset, new_length=total_qubits)
            qubit_offset += cast(StateType, output_.type).total_qubits

        msg = f"Output state {output_state} not found in outputs."
        raise ValueError(msg)


Stab = Dialect(
    "stab",
    [
        YieldOp,
        CircuitOp,
        StateMakeOp,
        StateCastOp,
        StateConcatenateOp,
        StateSplitOp,
        StatePermuteOp,
    ],
    [StateType, FlowAttr, ConcreteFlowAttr, ConcreteFlowArrayAttr],
)
