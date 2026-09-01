# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for the Stim xDSL dialect."""

from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from io import StringIO
from typing import IO, ClassVar, Final, cast

from typing_extensions import Self, override
from xdsl.dialects.builtin import (
    ArrayAttr,
    ArrayOfConstraint,
    Float64Type,
    FloatAttr,
    FloatData,
    IntAttr,
    ModuleOp,
    StringAttr,
    f64,
    i1,
)
from xdsl.dialects.utils import AbstractYieldOperation
from xdsl.ir import (
    Attribute,
    Block,
    Dialect,
    Operation,
    ParametrizedAttribute,
    SSAValue,
    TypeAttribute,
)
from xdsl.irdl import AtLeast, EqAttrConstraint, IntVarConstraint, RangeOf, opt_attr_def
from xdsl.irdl.attributes import base, irdl_attr_definition
from xdsl.irdl.operations import (
    IRDLOperation,
    VarOperand,
    irdl_op_definition,
    lazy_traits_def,
    opt_prop_def,
    prop_def,
    region_def,
    result_def,
    traits_def,
    var_operand_def,
    var_result_def,
)
from xdsl.parser import AttrParser, Parser
from xdsl.printer import Printer
from xdsl.traits import (
    HasParent,
    IsTerminator,
    Pure,
    RecursiveMemoryEffect,
    SingleBlockImplicitTerminator,
)
from xdsl.utils.exceptions import VerifyException

from deltakit_compile.dialects.common.attributes import (
    AnyEnumAttribute,
    OptPlainArrayOfFloat64Directive,
    OptPlainFloat64Directive,
    PlainArrayOfFloat64Directive,
    PlainFloatDataDirective,
    PlainIntAttr,
    PlainParsableParameterizedAttribute,
    float64_to_string,
    parse_float64,
)
from deltakit_compile.dialects.common.constraints import MessageIntConstraint
from deltakit_compile.dialects.qcore import (
    NoQuantumEffect,
    QubitGateEffect,
    QubitMeasureEffect,
    QubitResetEffect,
    RecursiveQuantumEffect,
)
from deltakit_compile.shared.deltakit_stim.gates import SingleQubitUnitaryEnum, TwoQubitUnitaryEnum
from deltakit_compile.utilities.base_enums import BetterStrEnum

TAG_ATTR: Final[str] = "stim.tag"


def escape_custom_escape_sequences(s: str) -> str:
    """Escape a text using custom escape sequences in stim.tag strings.

    Custom escape sequences, as defined in
    https://github.com/quantumlib/Stim/blob/79ae4f118ca11c615d6d8de7c6eed7d189d3a6eb/src/stim/circuit/circuit.h#L364:
    -                ] → \\C
    - carriage return  → \\r
    -        line feed → \\n
    -               \\ → \\B

    Note: \\ is processed first to avoid processing other escapes instead.
    """
    # Process in order, handling backslash first to avoid double-processing
    s = s.replace("\\", r"\B")
    s = s.replace("]", r"\C")
    s = s.replace("\r", r"\r")
    return s.replace("\n", r"\n")


def _print_op_stim(printer: Printer, opn: Operation, records: list[SSAValue]) -> None:
    """Try to print an unknown operation as Stim."""
    if not isinstance(opn, BaseStimOp):
        msg = f"Cannot print operation as Stim: {opn}"
        raise TypeError(msg)
    if isinstance(opn, (QubitAllocOp, YieldOp, EmptyOp)):
        # Op has no direct Stim equivalent
        return

    printer.print_string("\n")
    opn.print_stim(printer, records)


# region Cross-dialect attribute helpers


class ObservableIdAttr:
    """Helper for storing/retrieving an observable ID on an op's attr-dict.

    Attached to ops that return a !qec.observable to record the ID the observable had when it was
    part of a Stim circuit.
    """

    KEY: ClassVar[str] = "stim.obs_id"
    """The standard attr-dict key under which this attribute is stored."""

    @staticmethod
    def get(op: Operation) -> int | None:
        """Get the observable ID from an op's attr-dict, or None if not set."""
        attr = op.attributes.get(ObservableIdAttr.KEY)
        if attr is None:
            return None
        if not isinstance(attr, IntAttr):
            msg = f"Expected '{ObservableIdAttr.KEY}' to be an IntAttr, got {type(attr)}"
            raise TypeError(msg)
        return int(attr.data)

    @staticmethod
    def set(op: Operation, value: IntAttr | int) -> None:
        """Set the observable ID on an op's attr-dict."""
        op.attributes[ObservableIdAttr.KEY] = IntAttr.get(value)


# endregion

# region Attribute definitions


@irdl_attr_definition
class QubitType(ParametrizedAttribute, TypeAttribute):
    """Reference to a qubit."""

    name = "stim.qubit"


@irdl_attr_definition
class QubitMappingAttr(PlainParsableParameterizedAttribute):
    """
    This attribute provides a way to indicate the required connectivity or layout of `physical`
    qubits.

    It has one parameter that represents a co-ordinate array

    It is attached to a SSA-value associated with a qubit referred to in a circuit.
    This value is allocated at definition in a QubitCoord op.

    The co-ordinates may be used as a physical address of a qubit, or the relative address with
    respect to some known physical address.

    Operations that attach this as a property may represent the lattice-like structure of a physical
    quantum computer by having a property with an ArrayAttr[QubitCoordsAttr].
    """

    name = "stim.qubit_coord"

    coords: ArrayAttr[FloatData]

    def __init__(
        self,
        coords: list[float] | ArrayAttr[FloatData],
    ) -> None:
        if not isinstance(coords, ArrayAttr):
            coords = ArrayAttr(FloatData(arg) for arg in coords)
        super().__init__(coords)

    @property
    def coordinates(self) -> tuple[float, ...]:
        """The co-ordinates as a tuple."""
        return tuple(coord.data for coord in self.coords.data)

    @override
    @classmethod
    def parse_inner_parameters(cls, parser: AttrParser) -> Sequence[ArrayAttr[FloatData]]:
        coords = parser.parse_comma_separated_list(
            delimiter=parser.Delimiter.ANGLE,
            parse=lambda: FloatData(parse_float64(parser)),
        )
        return [ArrayAttr(coords)]

    @override
    def print_inner(self, printer: Printer) -> None:
        with printer.in_angle_brackets():
            printer.print_list(
                self.coords, lambda attr: printer.print_string(float64_to_string(attr.data))
            )


# endregion

# region Operation definitions

"""
Core Operations:
An operation is a quantum channel to apply to the quantum state of the system, and come under two
groups:
    1. `Gate` operations - pure and can be applied by a system controlling a quantum computer
    2. `Stabilizer` operations - destructive to the quantum state.

The only gate operations currently supported by Stim are Clifford gates.

Stim splits stabilizer operations into measurement gates - which add data to the measurement record,
and resets - which are silent and do not.
We model measurement results using SSA-values returned from operations here.

Stim also has `noise` operations which are used for simulating errors occurring. We currently do not
support them.
"""


class PauliOperatorEnum(BetterStrEnum):
    """
    Specify to explicitly indicate:
    * X : Pauli X operation
    * Y : Pauli Y operation
    * X : Pauli Z operation
    """

    X = "X"
    Y = "Y"
    Z = "Z"


@irdl_attr_definition
class PauliAttr(AnyEnumAttribute[PauliOperatorEnum], use_values=True):
    """Pauli operators as an attribute."""

    name = "stim.pauli"


# region Gate Operation Enum definitions


@irdl_attr_definition
class SingleQubitGateAttr(AnyEnumAttribute[SingleQubitUnitaryEnum], use_values=True):
    """Single qubit gate attribute."""

    name = "stim.singlequbitclifford"


@irdl_attr_definition
class TwoQubitGateAttr(AnyEnumAttribute[TwoQubitUnitaryEnum], use_values=True):
    """Two qubit gate attribute."""

    name = "stim.twoqubitclifford"


class BaseStimOp(IRDLOperation):
    """Abstract base class for all Stim operations."""

    tag = opt_attr_def(StringAttr, attr_name=TAG_ATTR)

    def _verify_2q_gate(self, targets: VarOperand) -> None:
        """Verify that a two qubit gate has an even number of targets."""
        if len(targets) % 2 != 0:
            msg = "Two qubit gates expect an even number of targets"
            raise VerifyException(msg)

    def _get_stim_tag_with_brackets(self) -> str:
        """Get the stim tag string representation."""
        attr = self.tag
        if attr is None or attr.data == "":
            return ""

        return "[" + escape_custom_escape_sequences(attr.data) + "]"

    @abstractmethod
    def print_stim(self, printer: Printer, recs: list[SSAValue]) -> None:
        """Print the contents of this operation as Stim string."""


@irdl_op_definition
class QubitAllocOp(BaseStimOp):
    """Allocate a qubit."""

    name = "stim.qubit_alloc"

    id = prop_def(IntAttr)
    res = result_def(QubitType)

    traits = traits_def(NoQuantumEffect())

    assembly_format = f"{PlainIntAttr.use('$id')} attr-dict `->` type($res)"
    custom_directives = (PlainIntAttr,)

    def __init__(self, qubit_id: int | IntAttr, tag: str | StringAttr | None = None):
        super().__init__(
            result_types=(QubitType(),),
            properties={"id": IntAttr.get(qubit_id)},
            attributes={TAG_ATTR: StringAttr.get(tag) if tag is not None else None},
        )

    @override
    def print_stim(self, printer: Printer, recs: list[SSAValue]) -> None:
        """This is skipped as this is not required in Stim."""


# endregion

# region Gate operation definitions


class GateOp(BaseStimOp, ABC):
    """
    Base class for stim gate operations.
    """

    T: ClassVar = IntVarConstraint(
        "Targets",
        MessageIntConstraint(AtLeast(1), "Gates must act on a non-zero number of qubits."),
    )

    targets = var_operand_def(RangeOf(base(QubitType)).of_length(T))


@irdl_op_definition
class CliffordGateOp(GateOp):
    """
    Clifford gates.
    """

    name = "stim.clifford"

    gate_type = prop_def(base(SingleQubitGateAttr) | base(TwoQubitGateAttr))

    traits = traits_def(QubitGateEffect("targets"))

    def __init__(
        self,
        gate_type: (SingleQubitUnitaryEnum | TwoQubitUnitaryEnum)
        | (SingleQubitGateAttr | TwoQubitGateAttr),
        targets: Sequence[SSAValue],
        tag: str | StringAttr | None = None,
    ):
        if isinstance(gate_type, SingleQubitUnitaryEnum):
            gate_type = SingleQubitGateAttr(gate_type)
        elif isinstance(gate_type, TwoQubitUnitaryEnum):
            gate_type = TwoQubitGateAttr(gate_type)
        super().__init__(
            operands=[targets],
            properties={"gate_type": gate_type},
            attributes={TAG_ATTR: StringAttr.get(tag) if tag is not None else None},
        )

    @override
    def verify_(self) -> None:
        """Verify custom constraints."""
        if isinstance(self.gate_type, TwoQubitGateAttr):
            self._verify_2q_gate(self.targets)

    @override
    @classmethod
    def parse(cls, parser: Parser) -> Self:
        """
        Parse assembly without names of properties with the form:
            stim.clifford $gate_type $pauli_modifier? $dag? $sqrt? $ctrl? `(` $targets `)` attr-dict

        """
        gate_type: SingleQubitGateAttr | TwoQubitGateAttr
        ident = parser.parse_optional_identifier()
        if ident and SingleQubitUnitaryEnum.contains(ident):
            gate_type = SingleQubitGateAttr(SingleQubitUnitaryEnum(ident))
        elif ident and TwoQubitUnitaryEnum.contains(ident):
            gate_type = TwoQubitGateAttr(TwoQubitUnitaryEnum(ident))
        else:
            parser.raise_error(
                "Expected a gate name of either SingleQubitGateAttr or "
                "TwoQubitGateAttr for stim.clifford"
            )

        targets = parser.parse_comma_separated_list(
            parser.Delimiter.PAREN, parser.parse_unresolved_operand
        )
        qubits = parser.resolve_operands(targets, len(targets) * [QubitType()], parser.pos)

        attr_dict = parser.parse_optional_attr_dict()
        return cls.build(
            operands=(qubits,), properties={"gate_type": gate_type}, attributes=attr_dict
        )

    @override
    def print(self, printer: Printer) -> None:
        """Print the gate as assembly."""
        printer.print_string(" ")
        printer.print_string(self.gate_type.data)
        printer.print_string(" ")
        printer.print_operands(self.targets)
        printer.print_op_attributes(self.attributes)

    @override
    def print_stim(self, printer: Printer, recs: list[SSAValue]) -> None:
        """Print Clifford Gate Operation as Stim."""
        printer.print_string(self.gate_type.data)
        printer.print_string(self._get_stim_tag_with_brackets())

        for ssa_qubit in self.operands:
            qubit_id = cast(QubitAllocOp, ssa_qubit.owner).id.data
            printer.print_string(f" {qubit_id}")


# endregion

# region Stabilizer operation definitions


@irdl_op_definition
class MeasurementGateOp(GateOp):
    """
    Measurements take parens for noise.
    """

    name = "stim.measure"

    pauli_modifier = prop_def(PauliAttr)
    readouts = var_result_def(
        RangeOf(EqAttrConstraint(i1)).of_length(
            MessageIntConstraint(
                GateOp.T,
                (
                    "A measurement operation must return the same number of readouts as "
                    "qubits it operates on"
                ),
            )
        )
    )
    noise = opt_prop_def(FloatAttr[Float64Type])

    traits = traits_def(QubitMeasureEffect("targets"))

    assembly_format = (
        f"{PauliAttr.plain_directive('$pauli_modifier')} ` ` "
        f"(`<` {OptPlainFloat64Directive.use('$noise')}^ `>`)? "
        "`(` $targets `)` attr-dict `->` type(results)"
    )

    custom_directives = (PauliAttr.plain_directive(), OptPlainFloat64Directive)

    def __init__(
        self,
        targets: Sequence[SSAValue],
        pauli_modifier: PauliOperatorEnum | PauliAttr = PauliOperatorEnum.Z,
        noise: FloatAttr[Float64Type] | float | None = None,
        tag: str | StringAttr | None = None,
    ):
        pauli_modifier = PauliAttr.from_argument(pauli_modifier)
        if isinstance(noise, float):
            noise = FloatAttr(noise, f64)
        super().__init__(
            operands=[targets],
            result_types=[[i1] * len(targets)],
            properties={
                "pauli_modifier": pauli_modifier,
                "noise": noise,
            },
            attributes={TAG_ATTR: StringAttr.get(tag) if tag is not None else None},
        )

    @override
    def print_stim(self, printer: Printer, recs: list[SSAValue]) -> None:
        printer.print_string("M")
        if self.pauli_modifier.data != PauliOperatorEnum.Z:
            printer.print_string(self.pauli_modifier.data)
        printer.print_string(self._get_stim_tag_with_brackets())
        recs.extend(self.results)
        if self.noise:
            printer.print_string(f"({self.noise.value.data})")

        for ssa_qubit in self.operands:
            qubit_id = cast(QubitAllocOp, ssa_qubit.owner).id.data
            printer.print_string(f" {qubit_id}")


@irdl_op_definition
class MultiPauliProductMeasurementOp(GateOp):
    """
    Joint measurement allowing different Pauli bases per qubit.

    - Produces exactly one classical bit that is the parity of all qubits.
    - Optional noise parameter allowed.
    """

    name = "stim.mpp"

    pauli_modifiers = prop_def(
        ArrayAttr.constr(
            RangeOf(base(PauliAttr)).of_length(
                MessageIntConstraint(
                    GateOp.T,
                    (
                        "A multi-pauli product measurement operation must have the same number of "
                        "pauli modifiers as targeted qubits."
                    ),
                )
            )
        )
    )
    readout = result_def(i1)
    noise = opt_prop_def(FloatAttr[Float64Type])

    traits = traits_def(QubitMeasureEffect("targets"))

    assembly_format = (
        f"{PauliAttr.plain_array_of_directive('$pauli_modifiers')} ` ` "
        f"(`<` {OptPlainFloat64Directive.use('$noise')}^ `>`)? "
        "`(` $targets `)` attr-dict `->` type($readout)"
    )

    custom_directives = (PauliAttr.plain_array_of_directive(), OptPlainFloat64Directive)

    def __init__(
        self,
        targets: Sequence[SSAValue],
        pauli_modifiers: Sequence[PauliOperatorEnum | PauliAttr],
        noise: FloatAttr[Float64Type] | float | None = None,
        tag: str | StringAttr | None = None,
    ):
        # Normalise per-qubit modifiers
        pm_array = ArrayAttr([PauliAttr.from_argument(pm) for pm in pauli_modifiers])

        # Normalise noise
        if isinstance(noise, float):
            noise = FloatAttr(noise, f64)

        super().__init__(
            operands=[targets],
            result_types=[i1],
            properties={
                "pauli_modifiers": pm_array,
                "noise": noise,
            },
            attributes={TAG_ATTR: StringAttr.get(tag) if tag is not None else None},
        )

    @override
    def print_stim(self, printer: Printer, recs: list[SSAValue]) -> None:
        printer.print_string("MPP")
        printer.print_string(self._get_stim_tag_with_brackets())
        if self.noise:
            printer.print_string(f"({self.noise.value.data})")
        recs.extend(self.results)

        tokens: list[str] = []
        for ssa_qubit, pauli_attr in zip(self.targets, self.pauli_modifiers.data, strict=True):
            qubit_id = cast(QubitAllocOp, ssa_qubit.owner).id.data
            tokens.append(f"{pauli_attr.data}{qubit_id}")
        if tokens:
            printer.print_string(" " + "*".join(tokens))


@irdl_op_definition
class ResetGateOp(GateOp):
    """
    Resets take no parens.
    """

    name = "stim.reset"

    pauli_modifier = prop_def(PauliAttr)

    traits = traits_def(QubitResetEffect("targets"))

    assembly_format = (
        f"{PauliAttr.plain_directive('$pauli_modifier')} ` ` `(` $targets `)` attr-dict"
    )

    custom_directives = (PauliAttr.plain_directive(),)

    def __init__(
        self,
        targets: Sequence[SSAValue],
        pauli_modifier: PauliOperatorEnum | PauliAttr = PauliOperatorEnum.Z,
        tag: str | StringAttr | None = None,
    ):
        if isinstance(pauli_modifier, PauliOperatorEnum):
            pauli_modifier = PauliAttr(pauli_modifier)
        super().__init__(
            operands=[targets],
            properties={"pauli_modifier": pauli_modifier},
            attributes={TAG_ATTR: StringAttr.get(tag) if tag is not None else None},
        )

    @override
    def print_stim(self, printer: Printer, recs: list[SSAValue]) -> None:
        """Print reset gate operation as Stim"""

        printer.print_string("R")
        if self.pauli_modifier.data != PauliOperatorEnum.Z:
            printer.print_string(self.pauli_modifier.data)
        printer.print_string(self._get_stim_tag_with_brackets())
        for ssa_qubit in self.operands:
            qubit_id = cast(QubitAllocOp, ssa_qubit.owner).id.data
            printer.print_string(f" {qubit_id}")


# endregion

# region Noise operations


class NoiseOp(BaseStimOp, ABC):
    """Base class for stim noise operations."""

    targets = var_operand_def(QubitType())
    traits = traits_def(QubitGateEffect("targets"))

    @abstractmethod
    def get_probabilities(self) -> list[float]:
        """Get all probabilities associated with this noise op as a list."""

    @override
    def verify_(self) -> None:
        """Verify that noise probabilities are valid and sum to a valid probability."""
        probs = self.get_probabilities()
        if any(not 0 <= (prob := i) <= 1 for i in probs):
            msg = f"Noise probability ({prob}) must be between 0 and 1"
            raise VerifyException(msg)
        if not 0 <= sum(probs) <= 1:
            msg = f"Noise probabilities ({probs}) must sum to between 0 and 1"
            raise VerifyException(msg)

    def _print_stim(
        self, stim_name: str, printer: Printer, probabilities: list[float] | None = None
    ) -> None:
        """Print the noise op as a Stim instruction. Uses all of the op's probabilities if none
        provided."""
        probabilities = self.get_probabilities() if probabilities is None else probabilities
        printer.print_string(stim_name)
        printer.print_string(self._get_stim_tag_with_brackets())
        printer.print_string("(")
        printer.print_list(
            probabilities, lambda float_value: printer.print_string(str(float_value))
        )
        printer.print_string(")")
        for ssa_qubit in self.operands:
            qubit_id = cast(QubitAllocOp, ssa_qubit.owner).id.data
            printer.print_string(f" {qubit_id}")


class SingleProbabilityNoiseOp(NoiseOp):
    """Base class for noise ops where the noise is expressed as a single noise probability."""

    STIM_INSTR_NAME: ClassVar[str]
    probability = prop_def(FloatData)

    assembly_format = (
        f"` ` `<` {PlainFloatDataDirective.use('$probability')} `>` `(` $targets `)` attr-dict"
    )
    custom_directives = (PlainFloatDataDirective,)

    def __init__(
        self,
        targets: Sequence[SSAValue],
        probability: float | FloatData,
        tag: str | StringAttr | None = None,
    ):
        super().__init__(
            operands=[targets],
            properties={"probability": FloatData.get(probability)},
            attributes={TAG_ATTR: StringAttr.get(tag) if tag is not None else None},
        )

    @override
    def get_probabilities(self) -> list[float]:
        return [self.probability.data]

    @override
    def print_stim(self, printer: Printer, recs: list[SSAValue]) -> None:
        self._print_stim(self.STIM_INSTR_NAME, printer)


@irdl_op_definition
class Depolarize1Op(SingleProbabilityNoiseOp):
    """Applies single-qubit depolarizing noise with the given probability."""

    name = "stim.depolarize1"
    STIM_INSTR_NAME: ClassVar[str] = "DEPOLARIZE1"


@irdl_op_definition
class Depolarize2Op(SingleProbabilityNoiseOp):
    """Applies two-qubit depolarizing noise with the given probability."""

    name = "stim.depolarize2"
    STIM_INSTR_NAME: ClassVar[str] = "DEPOLARIZE2"

    @override
    def verify_(self) -> None:
        """Verify that the targets are in pairs and noise probability is a valid probability."""
        super().verify_()
        self._verify_2q_gate(self.targets)


class CorrelatedErrorBaseOp(NoiseOp):
    """Base class for CorrelatedErrorOp and ElseCorrelatedErrorOp Operations.

    Handles stim printing, property definitions, etc for the two subclasses."""

    STIM_INSTR_NAME: ClassVar[str]

    paulis: ArrayAttr[PauliAttr] = prop_def(ArrayOfConstraint(PauliAttr))
    probability = prop_def(FloatData)

    assembly_format = (
        f"` ` `<` {PlainFloatDataDirective.use('$probability')} `>` "
        f"{PauliAttr.plain_array_of_directive('$paulis')} `(` $targets `)` attr-dict"
    )
    custom_directives = (PlainFloatDataDirective, PauliAttr.plain_array_of_directive())

    def __init__(
        self,
        targets: Sequence[SSAValue],
        paulis: Iterable[PauliOperatorEnum | PauliAttr],
        probability: float | FloatData,
        tag: str | StringAttr | None = None,
    ) -> None:
        paulis_attr = ArrayAttr([PauliAttr.get(p) for p in paulis])
        super().__init__(
            operands=[targets],
            properties={"probability": FloatData.get(probability), "paulis": paulis_attr},
            attributes={TAG_ATTR: StringAttr.get(tag) if tag is not None else None},
        )

    @override
    def get_probabilities(self) -> list[float]:
        return [self.probability.data]

    @override
    def verify_(self) -> None:
        super().verify_()
        if len(self.paulis) != len(self.targets):
            msg = (
                f"Expected one Pauli per target but got: {len(self.paulis)} Pauli for "
                f"{len(self.targets)} targets."
            )
            raise VerifyException(msg)

    @override
    def print_stim(self, printer: Printer, recs: list[SSAValue]) -> None:
        printer.print_string(self.STIM_INSTR_NAME)
        printer.print_string(self._get_stim_tag_with_brackets())
        with printer.in_parens():
            printer.print_string(str(self.probability.data))
        for pauli, ssa_qubit in zip(self.paulis, self.targets, strict=True):
            qubit_id = cast(QubitAllocOp, ssa_qubit.owner).id.data
            printer.print_string(f" {pauli.data}{qubit_id}")


@irdl_op_definition
class CorrelatedErrorOp(CorrelatedErrorBaseOp):
    """Applies the correlated noise defined by the Paulis with the given probability.

    In Stim, the "correlated error occurred flag" is set to True if an error occurred, else it is
    set to False.
    """

    name = "stim.correlated_error"

    STIM_INSTR_NAME: ClassVar[str] = "CORRELATED_ERROR"


@irdl_op_definition
class ElseCorrelatedErrorOp(CorrelatedErrorBaseOp):
    """Applies the correlated noise defined by the Paulis with the given probability if the previous
    CorrelatedErrorOp or ElseCorrelatedErrorOp did not produce an error.

    In Stim, the "correlated error occurred flag" is set to True if an error occurred.
    """

    name = "stim.else_correlated_error"

    STIM_INSTR_NAME: ClassVar[str] = "ELSE_CORRELATED_ERROR"

    @override
    def verify_(self) -> None:
        super().verify_()
        if self.parent is not None and not isinstance(self.prev_op, CorrelatedErrorBaseOp):
            msg = (
                f"{self.name} must follow either another {self.name} op "
                f"or a {CorrelatedErrorOp.name} op."
            )
            raise VerifyException(msg)


@irdl_op_definition
class PauliChannel1Op(NoiseOp):
    """Applies single-qubit noise with probability specified per-channel."""

    name = "stim.pauli_channel_1"

    probability_x = prop_def(FloatData)
    probability_y = prop_def(FloatData)
    probability_z = prop_def(FloatData)

    assembly_format = (
        "` ` "
        f"`<` {PlainFloatDataDirective.use('$probability_x')} "
        f"`,` {PlainFloatDataDirective.use('$probability_y')} "
        f"`,` {PlainFloatDataDirective.use('$probability_z')} "
        f"`>` `(` $targets `)` attr-dict"
    )
    custom_directives = (PlainFloatDataDirective,)

    def __init__(
        self,
        targets: Sequence[SSAValue],
        probabilities: Sequence[float] | Sequence[FloatData],
        tag: str | StringAttr | None = None,
    ):
        if len(probabilities) != 3:
            msg = "PAULI_CHANNEL_1 expects 3 probabilities"
            raise ValueError(msg)
        super().__init__(
            operands=[targets],
            properties={
                "probability_x": FloatData.get(probabilities[0]),
                "probability_y": FloatData.get(probabilities[1]),
                "probability_z": FloatData.get(probabilities[2]),
            },
            attributes={TAG_ATTR: StringAttr.get(tag) if tag is not None else None},
        )

    @override
    def get_probabilities(self) -> list[float]:
        return [self.probability_x.data, self.probability_y.data, self.probability_z.data]

    @override
    def print_stim(self, printer: Printer, recs: list[SSAValue]) -> None:
        if self.probability_y.data == 0 and self.probability_z.data == 0:
            self._print_stim("X_ERROR", printer, [self.probability_x.data])
        elif self.probability_x.data == 0 and self.probability_z.data == 0:
            self._print_stim("Y_ERROR", printer, [self.probability_y.data])
        elif self.probability_x.data == 0 and self.probability_y.data == 0:
            self._print_stim("Z_ERROR", printer, [self.probability_z.data])
        else:
            self._print_stim("PAULI_CHANNEL_1", printer)


@irdl_op_definition
class PauliChannel2Op(NoiseOp):
    """Applies two-qubit noise with probability specified for each possible Pauli pair."""

    name = "stim.pauli_channel_2"

    probability_ix = prop_def(FloatData)
    probability_iy = prop_def(FloatData)
    probability_iz = prop_def(FloatData)
    probability_xi = prop_def(FloatData)
    probability_xx = prop_def(FloatData)
    probability_xy = prop_def(FloatData)
    probability_xz = prop_def(FloatData)
    probability_yi = prop_def(FloatData)
    probability_yx = prop_def(FloatData)
    probability_yy = prop_def(FloatData)
    probability_yz = prop_def(FloatData)
    probability_zi = prop_def(FloatData)
    probability_zx = prop_def(FloatData)
    probability_zy = prop_def(FloatData)
    probability_zz = prop_def(FloatData)

    assembly_format = (
        "` ` "
        f"`<` {PlainFloatDataDirective.use('$probability_ix')} "
        f"`,` {PlainFloatDataDirective.use('$probability_iy')} "
        f"`,` {PlainFloatDataDirective.use('$probability_iz')} "
        f"`,` {PlainFloatDataDirective.use('$probability_xi')} "
        f"`,` {PlainFloatDataDirective.use('$probability_xx')} "
        f"`,` {PlainFloatDataDirective.use('$probability_xy')} "
        f"`,` {PlainFloatDataDirective.use('$probability_xz')} "
        f"`,` {PlainFloatDataDirective.use('$probability_yi')} "
        f"`,` {PlainFloatDataDirective.use('$probability_yx')} "
        f"`,` {PlainFloatDataDirective.use('$probability_yy')} "
        f"`,` {PlainFloatDataDirective.use('$probability_yz')} "
        f"`,` {PlainFloatDataDirective.use('$probability_zi')} "
        f"`,` {PlainFloatDataDirective.use('$probability_zx')} "
        f"`,` {PlainFloatDataDirective.use('$probability_zy')} "
        f"`,` {PlainFloatDataDirective.use('$probability_zz')} "
        f"`>` `(` $targets `)` attr-dict"
    )
    custom_directives = (PlainFloatDataDirective,)

    def __init__(
        self,
        targets: Sequence[SSAValue],
        probabilities: Sequence[float] | Sequence[FloatData],
        tag: str | StringAttr | None = None,
    ):
        if len(probabilities) != 15:
            msg = "PAULI_CHANNEL_2 expects 15 probabilities"
            raise ValueError(msg)
        super().__init__(
            operands=[targets],
            properties={
                "probability_ix": FloatData.get(probabilities[0]),
                "probability_iy": FloatData.get(probabilities[1]),
                "probability_iz": FloatData.get(probabilities[2]),
                "probability_xi": FloatData.get(probabilities[3]),
                "probability_xx": FloatData.get(probabilities[4]),
                "probability_xy": FloatData.get(probabilities[5]),
                "probability_xz": FloatData.get(probabilities[6]),
                "probability_yi": FloatData.get(probabilities[7]),
                "probability_yx": FloatData.get(probabilities[8]),
                "probability_yy": FloatData.get(probabilities[9]),
                "probability_yz": FloatData.get(probabilities[10]),
                "probability_zi": FloatData.get(probabilities[11]),
                "probability_zx": FloatData.get(probabilities[12]),
                "probability_zy": FloatData.get(probabilities[13]),
                "probability_zz": FloatData.get(probabilities[14]),
            },
            attributes={TAG_ATTR: StringAttr.get(tag) if tag is not None else None},
        )

    @override
    def get_probabilities(self) -> list[float]:
        return [
            self.probability_ix.data,
            self.probability_iy.data,
            self.probability_iz.data,
            self.probability_xi.data,
            self.probability_xx.data,
            self.probability_xy.data,
            self.probability_xz.data,
            self.probability_yi.data,
            self.probability_yx.data,
            self.probability_yy.data,
            self.probability_yz.data,
            self.probability_zi.data,
            self.probability_zx.data,
            self.probability_zy.data,
            self.probability_zz.data,
        ]

    @override
    def verify_(self) -> None:
        """Verify that the targets are in pairs and noise probability is a valid probability."""
        super().verify_()
        self._verify_2q_gate(self.targets)

    @override
    def print_stim(self, printer: Printer, recs: list[SSAValue]) -> None:
        self._print_stim("PAULI_CHANNEL_2", printer)


# endregion

# region Annotation operations

"""
Annotation Operations

Stim contains a number of `Annotations` - instructions which do not affect the operational semantics
of the stim circuit - but may provide useful information about the circuit being run or how decoding
should be done.

These are essentially code-directives for compiler analyses on the circuit.

Here each is attached as an attribute instead - but as they may appear in the code, are also given
operations that can drive the change of a value and be used to direct printing of stim circuits.
"""


class AnnotationOp(BaseStimOp, ABC):
    """
    Base Annotation operation.

    This is used to indicate operations that are stim annotations,
    these do not have operational semantics,
    so this will be used during transforms to ignore these operations.
    """


@irdl_op_definition
class QubitCoordsOp(AnnotationOp):
    """
    Annotation operation that assigns a qubit reference to a coordinate.
    """

    name = "stim.assign_qubit_coord"

    qubitcoord = prop_def(QubitMappingAttr)
    targets = var_operand_def(QubitType())

    traits = traits_def(NoQuantumEffect())

    assembly_format = (
        f"{QubitMappingAttr.plain_directive('$qubitcoord')} ` `"
        "`(` $targets `:` type($targets) `)` attr-dict"
    )
    custom_directives = (QubitMappingAttr.plain_directive(),)

    def __init__(
        self,
        targets: list[SSAValue],
        qubitmapping: QubitMappingAttr,
        tag: str | StringAttr | None = None,
    ):
        super().__init__(
            operands=[targets],
            properties={"qubitcoord": qubitmapping},
            attributes={TAG_ATTR: StringAttr.get(tag) if tag is not None else None},
        )

    @override
    def print_stim(self, printer: Printer, recs: list[SSAValue]) -> None:
        coords = [str(coord.data) for coord in self.qubitcoord.coords.data]
        qubit_ids = [
            str(cast(QubitAllocOp, ssa_qubit.owner).id.data) for ssa_qubit in self.operands
        ]

        coordinates = ", ".join(coords)
        targets = " ".join(qubit_ids)

        printer.print_string("QUBIT_COORDS")
        printer.print_string(self._get_stim_tag_with_brackets())
        printer.print_string(f"({coordinates}) {targets}")


class MeasurementTargetOp(AnnotationOp, ABC):
    """Base class for ops that target measurement bits as operands."""


@irdl_op_definition
class DetectorOp(MeasurementTargetOp):
    """Annotation operation that forms a detector from readouts."""

    name = "stim.detector"

    coords = opt_prop_def(ArrayAttr[FloatAttr[Float64Type]])
    targets = var_operand_def(i1)

    traits = traits_def(NoQuantumEffect())

    assembly_format = (
        f"` ` (`<` {OptPlainArrayOfFloat64Directive.use('$coords')}^ `>`)? "
        "`(` $targets `:` type($targets) `)` attr-dict"
    )
    custom_directives = (OptPlainArrayOfFloat64Directive,)

    def __init__(
        self,
        targets: Sequence[SSAValue],
        coords: ArrayAttr[FloatAttr[Float64Type]] | Sequence[float] | None = None,
        tag: str | StringAttr | None = None,
    ):
        if coords is not None and not isinstance(coords, ArrayAttr):
            coords = ArrayAttr(FloatAttr(arg, f64) for arg in coords)
        super().__init__(
            operands=[targets],
            properties={"coords": coords},
            attributes={TAG_ATTR: StringAttr.get(tag) if tag is not None else None},
        )

    @override
    def print_stim(self, printer: Printer, recs: list[SSAValue]) -> None:
        printer.print_string("DETECTOR")
        printer.print_string(self._get_stim_tag_with_brackets())
        if self.coords:
            coords = [str(coord.value.data) for coord in self.coords.data]
            printer.print_string("(")
            printer.print_list(coords, printer.print_string)
            printer.print_string(")")

        for target in self.targets:
            printer.print_string(f" rec[-{len(recs) - recs.index(target)}]")


@irdl_op_definition
class ObservableIncludeOp(MeasurementTargetOp):
    """Annotation operation that assigns readouts to an observable."""

    name = "stim.observable_include"

    observable = prop_def(IntAttr)
    targets = var_operand_def(i1)

    traits = traits_def(NoQuantumEffect())

    assembly_format = (
        f"` ` `<` {PlainIntAttr.use('$observable')} `>` ` ` "
        "`(` $targets `:` type($targets) `)` attr-dict"
    )
    custom_directives = (PlainIntAttr,)

    def __init__(
        self,
        targets: Sequence[SSAValue],
        observable: int | IntAttr,
        tag: str | StringAttr | None = None,
    ):
        if isinstance(observable, int):
            observable = IntAttr(observable)
        super().__init__(
            operands=[targets],
            properties={"observable": observable},
            attributes={TAG_ATTR: StringAttr.get(tag) if tag is not None else None},
        )

    @override
    def print_stim(self, printer: Printer, recs: list[SSAValue]) -> None:
        """Print stim for observable include operation"""
        printer.print_string("OBSERVABLE_INCLUDE")
        printer.print_string(self._get_stim_tag_with_brackets())
        printer.print_string(f"({self.observable.data})")

        for target in self.targets:
            printer.print_string(f" rec[-{len(recs) - recs.index(target)}]")


@irdl_op_definition
class ShiftCoordsOp(AnnotationOp):
    """Annotation operation that shifts successive detector coordinates by the provided amount."""

    name = "stim.shift_coord"

    coords = prop_def(ArrayAttr[FloatAttr[Float64Type]])

    traits = traits_def(NoQuantumEffect())

    assembly_format = f"` ` `<` {PlainArrayOfFloat64Directive.use('$coords')} `>` attr-dict"
    custom_directives = (PlainArrayOfFloat64Directive,)

    def __init__(
        self,
        coords: ArrayAttr[FloatAttr[Float64Type]] | Sequence[float],
        tag: str | StringAttr | None = None,
    ):
        if not isinstance(coords, ArrayAttr):
            coords = ArrayAttr(FloatAttr(arg, f64) for arg in coords)
        super().__init__(
            properties={"coords": coords},
            attributes={TAG_ATTR: StringAttr.get(tag) if tag is not None else None},
        )

    @override
    def print_stim(self, printer: Printer, recs: list[SSAValue]) -> None:
        coords = [str(coord.value.data) for coord in self.coords.data]
        printer.print_string("SHIFT_COORDS")
        printer.print_string(self._get_stim_tag_with_brackets())
        printer.print_string("(")
        printer.print_list(coords, printer.print_string)
        printer.print_string(")")


@irdl_op_definition
class TickAnnotationOp(AnnotationOp):
    """
    A tick annotation is essentially an empty marker that can be used by the compiler.
    """

    name = "stim.tick"
    assembly_format = "attr-dict"

    traits = traits_def(NoQuantumEffect())

    def __init__(self, tag: str | StringAttr | None = None) -> None:
        super().__init__(
            operands=[], attributes={TAG_ATTR: StringAttr.get(tag) if tag is not None else None}
        )

    @override
    def print_stim(self, printer: Printer, recs: list[SSAValue]) -> None:
        printer.print_string("TICK")
        printer.print_string(self._get_stim_tag_with_brackets())


# endregion

# region Controlflow operations


@irdl_op_definition
class EmptyOp(BaseStimOp):
    """Create a dud measurement SSAValue that fills the initial states of repeat op iter_args in
    cases where there is no measurement to fill that slot in the record in the first iteration of
    the loop but it is filled in later iterations. The result of this op is therefore never used."""

    name = "stim.empty"

    res = result_def(i1)

    traits = traits_def(NoQuantumEffect())

    assembly_format = "attr-dict `->` type($res)"

    def __init__(
        self,
    ) -> None:
        super().__init__(operands=(), result_types=[i1])

    @override
    def print_stim(self, printer: Printer, recs: list[SSAValue]) -> None:
        """This is skipped as this op has no meaning in Stim."""


@irdl_op_definition
class YieldOp(BaseStimOp, AbstractYieldOperation[Attribute]):
    """Control flow yielding Op. Used to return SSA values for measurements taken during a
    stim.repeat"""

    name = "stim.yield"

    traits = lazy_traits_def(
        lambda: (
            IsTerminator(),
            HasParent(RepeatOp),
            Pure(),
        )
    )

    @override
    def print_stim(self, printer: Printer, recs: list[SSAValue]) -> None:
        """No need to print stim.yield as it is implicit."""


@irdl_op_definition
class RepeatOp(BaseStimOp):
    """Stim repeat block (based on scf.for)."""

    name = "stim.repeat"

    repetitions = prop_def(IntAttr)

    iter_args = var_operand_def(i1)
    res = var_result_def(i1)

    body = region_def("single_block")

    traits = traits_def(
        SingleBlockImplicitTerminator(YieldOp),
        RecursiveMemoryEffect(),
        RecursiveQuantumEffect(),
    )

    assembly_format = (
        f"attr-dict {PlainIntAttr.use('$repetitions')} ` `"
        "`(`($iter_args^ `:` type($iter_args))?`)` (`->` type($res)^)? $body"
    )
    custom_directives = (PlainIntAttr,)

    def __init__(
        self,
        repetitions: int | IntAttr,
        body: Sequence[Block] | Block,
        iter_args: Sequence[SSAValue] = (),
        tag: str | StringAttr | None = None,
    ):
        if isinstance(body, Block):
            body = [body]

        if isinstance(repetitions, int):
            repetitions = IntAttr(repetitions)

        super().__init__(
            operands=[iter_args],
            result_types=[[SSAValue.get(a).type for a in iter_args]],
            regions=[body],
            properties={"repetitions": repetitions},
            attributes={TAG_ATTR: StringAttr.get(tag) if tag is not None else None},
        )

    @override
    def verify_(self) -> None:
        """Verify the number of repetitions and that the iter_args, block args, yields, and returns
        all match."""
        if self.repetitions.data < 1:
            msg = "repetitions must be > 0"
            raise VerifyException(msg)

        yielded_values: list[SSAValue] = []
        if isinstance(self.body.block.last_op, YieldOp):
            yielded_values.extend(self.body.block.last_op.operands)

        if (
            len(self.iter_args) != len(self.body.block.args)
            or len(self.body.block.args) != len(yielded_values)
            or len(yielded_values) != len(self.res)
        ):
            msg = (
                f"The number of iter_args ({len(self.iter_args)}), "
                f"the number of block arguments in the repeat body ({len(self.body.block.args)}), "
                f"the number of values yielded from the repeat body ({len(yielded_values)}), and "
                f"the number of results returned ({len(self.res)}) must all match"
            )
            raise VerifyException(msg)

        for iter_arg, block_arg, yielded_value, result_value in zip(
            self.iter_args, self.body.block.args, yielded_values, self.res, strict=False
        ):
            if (
                iter_arg.type != block_arg.type
                or block_arg.type != yielded_value.type
                or yielded_value.type != result_value.type
            ):
                msg = (
                    f"The iter arg type {iter_arg.type}, "
                    f"block arg type {block_arg.type}, "
                    f"yielded value type {yielded_value.type}, and "
                    f"result type {result_value.type} must all match"
                )
                raise VerifyException(msg)

    @override
    def print_stim(self, printer: Printer, recs: list[SSAValue]) -> None:
        """Please repeat operation as Stim."""
        # Record SSAs inside the repeat will come from the block's args
        arg_recs = self.body.block.args
        del recs[-len(arg_recs) :]
        recs.extend(arg_recs)

        printer.print_string("REPEAT")
        printer.print_string(self._get_stim_tag_with_brackets())
        printer.print_string(f" {self.repetitions.data} {{")

        with printer.indented():
            for opn in self.body.ops:
                _print_op_stim(printer, opn, recs)

        printer.print_string("\n}")

        # Record SSAs after the repeat will come from the op's results
        del recs[-len(self.res) :]
        recs.extend(self.res)


# endregion


def print_stim(module: ModuleOp, output: IO[str]) -> None:
    """Print module as a Stim via an IO stream."""

    printer = Printer(stream=output, indent_num_spaces=4)
    records: list[SSAValue] = []

    for opn in module.body.ops:
        _print_op_stim(printer, opn, records)


def to_stim(module: ModuleOp) -> str:
    """Convert module to a Stim file string."""

    stream = StringIO()
    print_stim(module, stream)
    return stream.getvalue()


Stim = Dialect(
    "stim",
    [
        CliffordGateOp,
        Depolarize1Op,
        Depolarize2Op,
        DetectorOp,
        EmptyOp,
        MultiPauliProductMeasurementOp,
        MeasurementGateOp,
        ObservableIncludeOp,
        CorrelatedErrorOp,
        ElseCorrelatedErrorOp,
        PauliChannel1Op,
        PauliChannel2Op,
        QubitAllocOp,
        QubitCoordsOp,
        RepeatOp,
        ResetGateOp,
        ShiftCoordsOp,
        TickAnnotationOp,
        YieldOp,
    ],
    [
        QubitType,
        QubitMappingAttr,
        PauliAttr,
        SingleQubitGateAttr,
        TwoQubitGateAttr,
    ],
)
