# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for the ncstim xDSL dialect that extends the Stim dialect with the non-Clifford
instructions tsim and clifft add on top of standard Stim."""

from collections.abc import Sequence
from typing import Final, cast

from typing_extensions import override
from xdsl.dialects.builtin import ArrayAttr, Float64Type, FloatAttr, StringAttr, f64
from xdsl.ir import Dialect, SSAValue
from xdsl.irdl import RangeOf, isa
from xdsl.irdl.attributes import base, irdl_attr_definition
from xdsl.irdl.declarative_assembly_format import (
    AttributeVariable,
    CustomDirective,
    ParsingState,
    PrintingState,
    irdl_custom_directive,
)
from xdsl.irdl.operations import IRDLOperation, irdl_op_definition, prop_def, traits_def
from xdsl.parser import Parser
from xdsl.printer import Printer
from xdsl.utils.exceptions import VerifyException

from deltakit_compile.dialects.common.attributes import (
    AnyEnumAttribute,
    PlainFloat64Directive,
    float64_to_string,
)
from deltakit_compile.dialects.common.constraints import MessageIntConstraint
from deltakit_compile.dialects.qcore import QubitGateEffect
from deltakit_compile.dialects.stim import (
    TAG_ATTR,
    GateOp,
    PauliAttr,
    PauliOperatorEnum,
    QubitAllocOp,
)
from deltakit_compile.utilities.base_enums import BetterStrEnum


def _verify_unique_targets(op: GateOp) -> None:
    """Verify that no qubit is targeted more than once, mirroring tsim/clifft's own rejection of
    duplicate target qubits (e.g. `R_XX(0.5) 3 3`) at parse time."""
    seen: set[SSAValue] = set()
    for target in op.targets:
        if target in seen:
            msg = f"{op.name} targets the same qubit more than once."
            raise VerifyException(msg)
        seen.add(target)


class NonCliffordGateEnum(BetterStrEnum):
    """Enum for a non-Clifford gate with no continuous parameter, in tsim/clifft."""

    T = "T"
    T_DAG = "T_DAG"
    CCZ = "CCZ"
    CCX = "CCX"
    CH = "CH"


@irdl_attr_definition
class NonCliffordGateAttr(AnyEnumAttribute[NonCliffordGateEnum], use_values=True):
    """A non-Clifford gate with no continuous parameter, as an attribute."""

    name = "ncstim.non_clifford_gate"


@irdl_op_definition
class NonCliffordGateOp(GateOp):
    """A fixed-identity, non-Clifford gate with no continuous parameter, mirroring tsim/clifft's
    T, T_DAG, CCZ, CCX, and CH instructions."""

    name = "ncstim.non_clifford"

    gate_type = prop_def(NonCliffordGateAttr)

    traits = traits_def(QubitGateEffect("targets"))

    assembly_format = (
        f"{NonCliffordGateAttr.plain_directive('$gate_type')} `(` $targets `)` attr-dict"
    )
    custom_directives = (NonCliffordGateAttr.plain_directive(),)

    def __init__(
        self,
        gate_type: NonCliffordGateEnum | NonCliffordGateAttr,
        targets: Sequence[SSAValue],
        tag: str | StringAttr | None = None,
    ):
        gate_type = NonCliffordGateAttr.from_argument(gate_type)
        super().__init__(
            operands=[targets],
            properties={"gate_type": gate_type},
            attributes={TAG_ATTR: StringAttr.get(tag) if tag is not None else None},
        )

    @override
    def verify_(self) -> None:
        _verify_unique_targets(self)

    @override
    def print_stim(self, printer: Printer, recs: list[SSAValue]) -> None:
        printer.print_string(self.gate_type.data)
        printer.print_string(self._get_stim_tag_with_brackets())

        for ssa_qubit in self.operands:
            qubit_id = cast(QubitAllocOp, ssa_qubit.owner).id.data
            printer.print_string(f" {qubit_id}")


@irdl_custom_directive
class PlainPauliStringDirective(CustomDirective):
    """Custom printing and parsing declaration for an ArrayAttr[PauliAttr] property in the form
    `XYZ` (a bare run of X/Y/Z characters, one per element) instead of `[X, Y, Z]`."""

    attr: AttributeVariable

    @override
    def parse(self, parser: Parser, state: ParsingState) -> bool:
        string = parser.expect(parser.parse_optional_identifier, "Expected a Pauli string")
        paulis: list[PauliAttr] = []
        for char in string:
            if char not in "XYZ":
                parser.raise_error(
                    f"Expected a Pauli string (X, Y, or Z characters) but got '{string}'"
                )
            paulis.append(PauliAttr(PauliOperatorEnum[char]))
        self.attr.set(state, ArrayAttr(paulis))
        return True

    @override
    def print(self, printer: Printer, state: PrintingState, op: IRDLOperation) -> None:
        state.print_whitespace(printer)
        pauli_string = self.attr.get(op)
        assert isa(pauli_string, ArrayAttr[PauliAttr])
        printer.print_list(pauli_string, lambda p: p.print_inner(printer), delimiter="")

    @classmethod
    def use(cls, argument: str) -> str:
        return f"custom<{cls.__name__}>({argument})"


_AXIS_ROTATION_NAMES: Final[dict[tuple[PauliOperatorEnum, ...], str]] = {
    (PauliOperatorEnum.X,): "R_X",
    (PauliOperatorEnum.Y,): "R_Y",
    (PauliOperatorEnum.Z,): "R_Z",
    (PauliOperatorEnum.X, PauliOperatorEnum.X): "R_XX",
    (PauliOperatorEnum.Y, PauliOperatorEnum.Y): "R_YY",
    (PauliOperatorEnum.Z, PauliOperatorEnum.Z): "R_ZZ",
}
_SPECIAL_ANGLE_NAMES: Final[dict[float, str]] = {
    0.5: "SPP",
    -0.5: "SPP_DAG",
    0.25: "TPP",
    -0.25: "TPP_DAG",
}


@irdl_op_definition
class RotationGateOp(GateOp):
    """`exp(-i*alpha*pi/2*P)` for a Pauli product P and angle alpha, P is a plain, dense list of
    Paulis: one per targeted qubit, in order, with no gaps. Mirrors tsim/clifft's
    R_PAULI instruction.

    This op covers the entire family of Pauli Rotations at a fixed
    Pauli-string shape and/or a fixed angle: R_X/R_Y/R_Z/R_XX/R_YY/R_ZZ and
    SPP/SPP_DAG/TPP/TPP_DAG are all print-time special cases of this one op, not separate op
    types. See print_stim for the exact precedence between them.
    """

    name = "ncstim.rotation"

    pauli_modifiers = prop_def(
        ArrayAttr.constr(
            RangeOf(base(PauliAttr)).of_length(
                MessageIntConstraint(
                    GateOp.T,
                    "A rotation gate must have the same number of pauli modifiers as targeted "
                    "qubits.",
                )
            )
        )
    )
    angle = prop_def(FloatAttr[Float64Type])

    traits = traits_def(QubitGateEffect("targets"))

    assembly_format = (
        f"{PlainPauliStringDirective.use('$pauli_modifiers')} `<` "
        f"{PlainFloat64Directive.use('$angle')} `>` `(` $targets `)` attr-dict"
    )
    custom_directives = (PlainPauliStringDirective, PlainFloat64Directive)

    def __init__(
        self,
        pauli_modifiers: ArrayAttr[PauliAttr] | Sequence[PauliAttr],
        angle: float | FloatAttr[Float64Type],
        targets: Sequence[SSAValue],
        tag: str | StringAttr | None = None,
    ):
        if not isinstance(pauli_modifiers, ArrayAttr):
            pauli_modifiers = ArrayAttr(pauli_modifiers)
        if isinstance(angle, float):
            angle = FloatAttr(angle, f64)
        super().__init__(
            operands=[targets],
            properties={"pauli_modifiers": pauli_modifiers, "angle": angle},
            attributes={TAG_ATTR: StringAttr.get(tag) if tag is not None else None},
        )

    @override
    def verify_(self) -> None:
        _verify_unique_targets(self)

    @override
    def print_stim(self, printer: Printer, recs: list[SSAValue]) -> None:
        paulis = tuple(pauli.data for pauli in self.pauli_modifiers)
        qubit_ids = [cast(QubitAllocOp, ssa_qubit.owner).id.data for ssa_qubit in self.operands]

        axis_name = _AXIS_ROTATION_NAMES.get(paulis)
        if axis_name is not None:
            printer.print_string(axis_name)
            printer.print_string(self._get_stim_tag_with_brackets())
            printer.print_string(f"({float64_to_string(self.angle)})")
            for qubit_id in qubit_ids:
                printer.print_string(f" {qubit_id}")
            return

        pauli_string = "*".join(
            f"{pauli.data}{qubit_id}"
            for pauli, qubit_id in zip(self.pauli_modifiers, qubit_ids, strict=True)
        )

        special_name = _SPECIAL_ANGLE_NAMES.get(self.angle.value.data)
        if special_name is not None:
            printer.print_string(special_name)
            printer.print_string(self._get_stim_tag_with_brackets())
            printer.print_string(f" {pauli_string}")
            return

        printer.print_string("R_PAULI")
        printer.print_string(self._get_stim_tag_with_brackets())
        printer.print_string(f"({float64_to_string(self.angle)}) {pauli_string}")


@irdl_op_definition
class U3GateOp(GateOp):
    """A general single-qubit rotation parameterised by three angles (theta, phi, lambda), each a
    multiple of pi, mirroring tsim/clifft's U3 instruction.

    theta, phi, and lambda are stored as three separate plain FloatAttr properties.

    Kept separate from RotationGateOp because it is strictly more general than any Pauli
    rotation: RotationGateOp (and everything built from it) is a one-axis rotation, the Pauli
    string fixes the axis, only the angle is free, so it can never reach an arbitrary
    single-qubit gate on its own. U3's three free angles can.
    """

    name = "ncstim.u3"

    theta = prop_def(FloatAttr[Float64Type])
    phi = prop_def(FloatAttr[Float64Type])
    lam = prop_def(FloatAttr[Float64Type])

    traits = traits_def(QubitGateEffect("targets"))

    assembly_format = (
        "`<` "
        f"{PlainFloat64Directive.use('$theta')} `,` "
        f"{PlainFloat64Directive.use('$phi')} `,` "
        f"{PlainFloat64Directive.use('$lam')} `>` `(` $targets `)` attr-dict"
    )
    custom_directives = (PlainFloat64Directive,)

    def __init__(
        self,
        theta: float | FloatAttr[Float64Type],
        phi: float | FloatAttr[Float64Type],
        lam: float | FloatAttr[Float64Type],
        targets: Sequence[SSAValue],
        tag: str | StringAttr | None = None,
    ):
        if isinstance(theta, float):
            theta = FloatAttr(theta, f64)
        if isinstance(phi, float):
            phi = FloatAttr(phi, f64)
        if isinstance(lam, float):
            lam = FloatAttr(lam, f64)
        super().__init__(
            operands=[targets],
            properties={"theta": theta, "phi": phi, "lam": lam},
            attributes={TAG_ATTR: StringAttr.get(tag) if tag is not None else None},
        )

    @override
    def print_stim(self, printer: Printer, recs: list[SSAValue]) -> None:
        printer.print_string("U3")
        printer.print_string(self._get_stim_tag_with_brackets())
        with printer.in_parens():
            printer.print_list(
                (self.theta, self.phi, self.lam),
                lambda angle: printer.print_string(float64_to_string(angle)),
            )

        for ssa_qubit in self.operands:
            qubit_id = cast(QubitAllocOp, ssa_qubit.owner).id.data
            printer.print_string(f" {qubit_id}")


NCStim = Dialect("ncstim", [NonCliffordGateOp, RotationGateOp, U3GateOp], [NonCliffordGateAttr])
