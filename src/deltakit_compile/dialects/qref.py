# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for the xDSL dialect for referenced qubit based quantum operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from typing import ClassVar, Literal, cast

from typing_extensions import override
from xdsl.dialects.builtin import I1, ArrayAttr, ArrayOfConstraint, Float64Type, FloatAttr, i1
from xdsl.ir import Dialect, SSAValue
from xdsl.irdl import (
    IRDLOperation,
    base,
    irdl_op_definition,
    prop_def,
    traits_def,
    var_operand_def,
    var_result_def,
)
from xdsl.irdl.constraints import (
    AtLeast,
    EqIntConstraint,
    IntConstraint,
    IntVarConstraint,
    RangeOf,
)
from xdsl.parser import Parser
from xdsl.pattern_rewriter import RewritePattern
from xdsl.traits import HasCanonicalizationPatternsTrait
from xdsl.utils.hints import isa

from deltakit_compile.dialects import qcore
from deltakit_compile.dialects.common.attributes import (
    float64_to_string,
    parse_float64,
)
from deltakit_compile.dialects.common.constraints import (
    MessageIntConstraint,
    ModuloIntConstraint,
    SumOver,
)


class GateLikeOp(IRDLOperation, ABC):
    """A common base class for all gate-like (gate, measurement, reset) operations.

    Noise operations are not considered gate-like.
    """

    @property
    @abstractmethod
    def qubit_operand_groups(self) -> Sequence[Sequence[SSAValue[qcore.QubitType]]]:
        """The groups of qubit operands that this operation independently acts upon.

        This operation broadcasts across each group of qubits.
        """

    def is_broadcast(self) -> bool:
        """Return whether this gate is a broadcast operation, i.e. whether it acts on more than one
        group of qubits."""
        return len(self.qubit_operand_groups) > 1

    @property
    def qubit_operand_group(self) -> Sequence[SSAValue[qcore.QubitType]]:
        """The only group of qubit operands, assuming this is not a broadcast operation.

        Returns:
            The single group of qubit operands that this operation acts upon.

        Raises:
            ValueError: If this is a broadcast operation.
        """
        if self.is_broadcast():
            msg = "The 'qubit_operand_group' property is not available for broadcast operations."
            raise ValueError(msg)
        return self.qubit_operand_groups[0]


class _ResetOpHasCanonicalizationPatternsTrait(HasCanonicalizationPatternsTrait):
    @override
    @classmethod
    def get_canonicalization_patterns(cls) -> tuple[RewritePattern, ...]:
        from deltakit_compile.passes.canonicalisation.qref import (  # noqa: PLC0415
            DeadGateBeforeReset,
        )  # Imported here to avoid circular imports.

        return (DeadGateBeforeReset(),)


@irdl_op_definition
class ResetOp(GateLikeOp):
    """An operation for resetting the state of a qubit by reference.

    Args:
        basis: The basis to reset the qubit in to.
        qubits: A sequence of qubits references on which to apply the reset. Each qubit is
            individually reset.


    Attributes:
        name: The IR name of this op.
        basis: The Pauli basis the qubits are reset into.
        qubits: The references to qubits this operation applies the reset to.
        assembly_format: How the IR should be printed and parsed.
        custom_directives: The custom directives referenced in the assembly_format.
        traits: The traits of this op.
    """

    name = "qref.reset"

    basis = prop_def(qcore.PauliAttr)

    qubits = var_operand_def(RangeOf(base(qcore.QubitType)).of_length(AtLeast(1)))

    assembly_format = (
        f"`<` {qcore.PauliAttr.plain_directive('$basis')} `>` `(` $qubits `)` attr-dict"
    )
    custom_directives = (qcore.PauliAttr.plain_directive(),)

    traits = traits_def(
        qcore.QubitResetEffect("qubits"),
        qcore.HasCircuitAncestor(),
        _ResetOpHasCanonicalizationPatternsTrait(),
    )

    def __init__(self, basis: qcore.Pauli, qubits: Sequence[SSAValue]):
        super().__init__(operands=[qubits], properties={"basis": qcore.PauliAttr.coerce(basis)})

    @property
    @override
    def qubit_operand_groups(self) -> Sequence[Sequence[SSAValue[qcore.QubitType]]]:
        return [[cast(SSAValue[qcore.QubitType], qubit)] for qubit in self.qubits]


@irdl_op_definition
class MeasureOp(GateLikeOp):
    """An operation for measuring the state of a qubit by reference.

    This op measures one or more qubits in the provided (potentially-multi-pauli) bases.
    This is a broadcast op that measures the qubits in the groups expressed by the provided arrays
    of paulis i.e., bit-flips are applied per multi-pauli measurement.
    eg. ``$r01, %r23, %r45 = qref.measure<XX> (%q0, %q1, %q2, %q3, %q4, %q5)`` will perform
    multiple 'XX' measurements to use up all the qubit operands and so here, for 6 operands, and a
    multi-pauli measurement that uses 2 qubits we get 3 distinct measurement taking place.
    This input is parsed the into an identical operation as
    ``$r01, %r23, %r45 = qref.measure<[XX, XX, XX]> (%q0, %q1, %q2, %q3, %q4, %q5)`` which is the
    more general form that explicitly shows the 3 different measurements.
    The noise parameter defines an the probability of a bit flip for each of the 3 measurements
    independently.


    Args:
        paulis: multiple Pauli strings to measure the qubits in, or the Pauli string for a
            potentially-multi-pauli measurement to be broadcast across the given qubits.
        qubits: A sequence of qubits references on which to apply the measurements. Qubits are
            grouped by the flattened structure of ``paulis`` where each inner Pauli string is a
            separate measurement with a separate i1 result.
        noise: The bit-flip probability per measurement.


    Attributes:
        name: The IR name of this op.
        paulis: An array of Pauli string measurements.
        noise: The bit-flip probability per measurement.
        qubits: The references to qubits this operation measures.
        measurements: The result of each potentially-multi-pauli measurement
        traits: The traits of this op.
    """

    name = "qref.measure"

    _Q: ClassVar[IntConstraint] = MessageIntConstraint(
        IntVarConstraint("Qubits", AtLeast(1)),
        "The number of qubit operands must equal the total number of Paulis across each Pauli "
        "string.",
    )
    _R: ClassVar[IntConstraint] = MessageIntConstraint(
        IntVarConstraint("Results", AtLeast(1)),
        "The number of measurement results must equal the number of Pauli strings.",
    )

    _MULTI_PAULI_MEASURE_STRING: ClassVar[ArrayOfConstraint[qcore.PauliAttr]] = ArrayOfConstraint(
        RangeOf(base(qcore.PauliAttr)).of_length(
            MessageIntConstraint(AtLeast(1), "Pauli strings must have at least one Pauli.")
        )
    )
    """Constrains each Pauli string as an ArrayAttr[PauliAttr] with length >= 1"""

    paulis: ArrayAttr[ArrayAttr[qcore.PauliAttr]] = prop_def(
        ArrayOfConstraint(
            SumOver(
                RangeOf(_MULTI_PAULI_MEASURE_STRING),
                len,  # Constrains the sum of lengths of the Pauli strings
                _Q,  # So that they sum to the number of qubit operands.
            ).of_length(_R)  # Constrains the number of Pauli strings to the number of results.
        )
    )
    noise = prop_def(FloatAttr[Float64Type])

    qubits = var_operand_def(RangeOf(base(qcore.QubitType)).of_length(_Q))

    measurements = var_result_def(RangeOf(i1).of_length(_R))

    traits = traits_def(
        qcore.QubitMeasureEffect("qubits"),
        qcore.HasCircuitAncestor(),
    )

    def __init__(
        self,
        paulis: ArrayAttr[ArrayAttr[qcore.PauliAttr]]
        | qcore.Pauli
        | Sequence[qcore.PauliAttr]
        | str,
        qubits: Sequence[SSAValue],
        noise: FloatAttr[Float64Type] | float = 0.0,
    ):
        if not isinstance(paulis, ArrayAttr):
            paulis = self._convert_paulis_arg(paulis, len(qubits))
        if not isinstance(noise, FloatAttr):
            noise = FloatAttr(float(noise), Float64Type())

        super().__init__(
            operands=[qubits],
            properties={"paulis": paulis, "noise": noise},
            result_types=[[i1] * len(paulis)],
        )

    @staticmethod
    def _convert_paulis_arg(
        arg: qcore.Pauli | Sequence[qcore.PauliAttr] | str,
        qubit_count: int,
    ) -> ArrayAttr[ArrayAttr[qcore.PauliAttr]]:
        """Broadcasts one single-or-multi pauli measurement into an array of multi-pauli
        measurements that will use qubit_count qubits, if that number is possible. Checking the
        total qubit count is left to the op's verification."""

        if isinstance(arg, qcore.PauliAttr):
            return ArrayAttr([ArrayAttr([arg])] * qubit_count)
        if not arg:
            msg = "Cannot convert an empty sequence into qref.measure Pauli string."
            raise ValueError(msg)
        copies = qubit_count // len(arg)
        if isinstance(arg, str):
            if not isa(arg, Sequence[Literal["X", "Y", "Z"]]):
                msg = (
                    f"Cannot convert '{arg}' into a Pauli string. "
                    "Expected only 'X's, 'Y's, and 'Z's."
                )
                raise ValueError(msg)
            return ArrayAttr([ArrayAttr([qcore.PauliAttr.coerce(p) for p in arg])] * copies)
        return ArrayAttr([ArrayAttr(arg)] * copies)

    @override
    @classmethod
    def parse(cls, parser: Parser) -> MeasureOp:
        """Parses a `qref.measure` op's body as::

            `<` (pauli-string | `[` pauli-string (`,` pauli-string)* `]`)
            (`,` plain_float($noise))? `>`
            `(` $qubits `)` attr-dict? `->` type($measurements)

        where each pauli-string is [XYZ]+ and if it not given inside the `[` ... `]` then it is
        assumed to be the same Pauli string for each result.
        eg.
            `... = qref.measure<XX> (%1, %2, %3, %4) -> i1, i1` is the same as
            `... = qref.measure<[XX, XX]> (%1, %2, %3, %4) -> i1, i1`
        """
        proto_paulis = None
        paulis = None
        with parser.in_angle_brackets():
            proto_paulis = qcore.PauliAttr.parse_optional_pauli_string(parser)
            if proto_paulis is None:
                paulis = ArrayAttr(
                    parser.parse_comma_separated_list(
                        parser.Delimiter.SQUARE,
                        lambda: parser.expect(
                            lambda: qcore.PauliAttr.parse_optional_pauli_string(parser),
                            "Expected a Pauli string in the form 'XYZ'",
                        ),
                        "Expected a single Pauli string, or a list of Pauli strings",
                    )
                )
            if parser.parse_optional_punctuation(","):
                noise = FloatAttr(parse_float64(parser), Float64Type())
            else:
                noise = FloatAttr(0.0, Float64Type())
        qubits = parser.parse_comma_separated_list(parser.Delimiter.PAREN, parser.parse_operand)

        attributes = parser.parse_optional_attr_dict()

        parser.parse_punctuation("->")
        return_types = parser.parse_comma_separated_list(parser.Delimiter.NONE, parser.parse_type)

        if paulis is None:
            assert proto_paulis is not None
            paulis = ArrayAttr([proto_paulis] * len(return_types))

        return cls.create(
            operands=qubits,
            properties={"paulis": paulis, "noise": noise},
            attributes=attributes,
            result_types=return_types,
        )

    @override
    def print(self, printer) -> None:
        """Prints a `qref.measure` op's body as::

            `<` (pauli-string | `[` pauli-string (`,` pauli-string)* `]`)
            (`,` plain_float($noise))? `>`
            `(` $qubits `)` attr-dict? `->` type($measurements)

        where if all the Pauli strings are the same, then only one is printed
        (without the `[` ... `]`), and if the noise is exactly 0.0 then it is not printed.
        """
        with printer.in_angle_brackets():
            if len(set(self.paulis.data)) == 1:
                qcore.PauliAttr.print_pauli_string(self.paulis.data[0], printer)
            else:
                with printer.in_square_brackets():
                    printer.print_list(
                        self.paulis, lambda ps: qcore.PauliAttr.print_pauli_string(ps, printer)
                    )
            if self.noise.value.data != 0.0:
                printer.print_string(", ")
                printer.print_string(float64_to_string(self.noise.value.data))

        printer.print_string(" ")

        with printer.in_parens():
            printer.print_list(self.qubits, printer.print_ssa_value)

        if self.attributes:
            printer.print_string(" ")
            printer.print_attr_dict(self.attributes)

        printer.print_string(" -> ")
        printer.print_list(self.result_types, printer.print_attribute)

    @property
    @override
    def qubit_operand_groups(self) -> Sequence[Sequence[SSAValue[qcore.QubitType]]]:
        qubit_groups = list(self.get_operand_segments())
        return cast(Sequence[Sequence[SSAValue[qcore.QubitType]]], qubit_groups)

    def get_operand_segments(self) -> Iterator[tuple[SSAValue, ...]]:
        """Iterates over each separate potentially-multi-pauli measurement yielding its operands.

        Yields:
            The operands for each potentially-multi-pauli measurement.
        """
        qubits_idx = 0
        for pauli_string_len in map(len, self.paulis):
            yield self.qubits[qubits_idx : qubits_idx + pauli_string_len]
            qubits_idx += pauli_string_len

    @property
    def pauli(self) -> Sequence[qcore.PauliAttr]:
        """The single Pauli string this op measures, assuming it is not a broadcast op.

        Returns:
            The single Pauli string this op measures.

        Raises:
            ValueError: If this is a broadcast operation.
        """
        if self.is_broadcast():
            msg = "The 'pauli' property is not available for broadcast operations."
            raise ValueError(msg)
        return self.paulis.data[0].data

    @property
    def measurement(self) -> SSAValue[I1]:
        """The single measurement result of this op, assuming it is not a broadcast op.

        Returns:
            The single measurement result of this op.

        Raises:
            ValueError: If this is a broadcast operation.
        """
        if self.is_broadcast():
            msg = "The 'measurement' property is not available for broadcast operations."
            raise ValueError(msg)
        return self.measurements[0]


class _GateOpHasCanonicalizationPatternsTrait(HasCanonicalizationPatternsTrait):
    @override
    @classmethod
    def get_canonicalization_patterns(cls) -> tuple[RewritePattern, ...]:
        from deltakit_compile.passes.canonicalisation.qref import (  # noqa: PLC0415
            IdentityGateElimination,
        )  # Imported here to avoid circular imports.

        return (IdentityGateElimination(),)


@irdl_op_definition
class GateOp(GateLikeOp):
    """An operation for applying a quantum gate to a qubit reference.

    Args:
        gate: The quantum gate to apply.
        qubits: A sequence of qubits references on which to apply the gate. The sequence must
            contain a positive integer multiple of the gate's qubit count, n. This operation will
            apply the gate in a broadcast fashion to each mutually exclusive subsequence of n
            qubits.


    Attributes:
        name: The IR name of this op.
        gate: The gate that this operation applies.
        qubits: The references to qubits this operation applies the gate to.
        assembly_format: How the IR should be printed and parsed.
        traits: The traits of this op.
    """

    name = "qref.gate"

    _QUBITS: ClassVar[IntConstraint]
    _GATE_SIZE: ClassVar[IntConstraint]
    _QUBITS, _GATE_SIZE = ModuloIntConstraint.make_pair(
        IntVarConstraint("Qubits", AtLeast(1)),
        "Gate Size",
        MessageIntConstraint(
            EqIntConstraint(0),
            "The number of qubit operands must be a multiple of the number "
            "that the given gate operates on.",
        ),
    )
    """Constraints that enforces: 'Qubits' % 'Gate Size' == 0."""

    gate = prop_def(qcore.GateConstraint(_GATE_SIZE))

    qubits = var_operand_def(RangeOf(base(qcore.QubitType)).of_length(_QUBITS))

    assembly_format = "`<` $gate `>` `(` $qubits `)` attr-dict"

    traits = traits_def(
        qcore.QubitGateEffect("qubits"),
        qcore.HasCircuitAncestor(),
        _GateOpHasCanonicalizationPatternsTrait(),
    )

    def __init__(self, gate: qcore.GateAttribute, qubits: Sequence[SSAValue]):
        super().__init__(operands=[qubits], properties={"gate": gate})

    @property
    @override
    def qubit_operand_groups(self) -> Sequence[Sequence[SSAValue[qcore.QubitType]]]:
        qubit_groups = list(self.get_operand_segments())
        return cast(Sequence[Sequence[SSAValue[qcore.QubitType]]], qubit_groups)

    def get_operand_segments(self) -> Iterator[tuple[SSAValue, ...]]:
        """Iterates over each separate gate application yielding its operands.

        Yields:
            The operands for each gate application.
        """
        for i in range(0, len(self.qubits), self.gate.get_qubit_count()):
            yield self.qubits[i : i + self.gate.get_qubit_count()]


@irdl_op_definition
class PauliNoiseOp(IRDLOperation):
    """An operation for applying/representing an independent noise probability on a set of qubit
    references.

    Args:
        probabilities: The Pauli noise to apply.
        qubits: A sequence of qubits references on which to apply the noise. The sequence must
            contain a positive integer multiple of the noises' qubit count, n. This operation will
            apply the noise in a broadcast fashion to each mutually exclusive subsequence of n
            qubits.


    Attributes:
        name: The IR name of this op.
        probabilities: The Pauli noise this op applies.
        qubits: The references to qubits this operation applies the noise to.
        assembly_format: How the IR should be printed and parsed.
        custom_directives: The CustomDirectives used in the assembly_format.
        traits: The traits of this op.
    """

    name = "qref.pauli_noise"
    _QUBITS: ClassVar[IntConstraint]
    _NOISE_WIDTH: ClassVar[IntConstraint]
    _QUBITS, _NOISE_WIDTH = ModuloIntConstraint.make_pair(
        IntVarConstraint("Qubits", AtLeast(1)),
        "Noise Width",
        MessageIntConstraint(
            EqIntConstraint(0),
            "The number of qubit operands must be a multiple of the number "
            "that the given qcore.pauli_noise_parameters Attribute operates on.",
        ),
    )
    """Constraints that enforces: 'Qubits' % 'Noise Width' == 0."""

    probabilities: qcore.PauliNoiseParametersAttr = prop_def(
        qcore.PauliNoiseParametersAttr.constr(_NOISE_WIDTH)
    )

    qubits = var_operand_def(RangeOf(base(qcore.QubitType)).of_length(_QUBITS))

    assembly_format = (
        f"`<` {qcore.PauliNoiseParametersAttr.plain_directive('$probabilities')} `>` "
        "`(` $qubits `)` attr-dict"
    )

    custom_directives = (qcore.PauliNoiseParametersAttr.plain_directive(),)

    traits = traits_def(
        qcore.QubitGateEffect("qubits"),
        qcore.HasCircuitAncestor(),
    )

    def __init__(
        self,
        probabilities: qcore.PauliNoiseParametersAttr,
        qubits: Sequence[SSAValue],
    ):
        super().__init__(operands=[qubits], properties={"probabilities": probabilities})


QRef = Dialect(
    "qref",
    [ResetOp, MeasureOp, GateOp, PauliNoiseOp],
    [],
)
