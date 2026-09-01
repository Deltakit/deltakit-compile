# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for the sobs dialect.

This dialect is used to represent observables that are supported on patches or qubits and can be
moved by using stabiliser measurements to a different support.

"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import ClassVar

from typing_extensions import override
from xdsl.dialects.builtin import ArrayAttr, ArrayOfConstraint, i1
from xdsl.ir import Dialect, ParametrizedAttribute, SSAValue, TypeAttribute
from xdsl.irdl import (
    AtLeast,
    AttrSizedOperandSegments,
    EqAttrConstraint,
    IntConstraint,
    IntVarConstraint,
    IRDLOperation,
    RangeOf,
    base,
    irdl_attr_definition,
    irdl_op_definition,
    operand_def,
    prop_def,
    result_def,
    traits_def,
    var_operand_def,
)
from xdsl.parser import Parser
from xdsl.traits import Pure

from deltakit_compile.dialects import qcore
from deltakit_compile.dialects.logical_assembly import (
    SurfaceCodePatchConstraint,
)
from deltakit_compile.dialects.qcore import (
    DecodingSideEffect,
    HasCircuitAncestor,
    PauliAttr,
    QubitType,
)

# region Type definitions


@irdl_attr_definition
class ObservableType(ParametrizedAttribute, TypeAttribute):
    """A type for sobs-style placed logical observables."""

    name = "sobs.observable"

    def __init__(self) -> None:
        super().__init__()  # overriding __init__ to remove unwanted arguments.


@irdl_attr_definition
class UnplacedObservableType(ParametrizedAttribute, TypeAttribute):
    """A type for sobs-style unplaced logical observables."""

    name = "sobs.unplaced_observable"

    def __init__(self) -> None:
        super().__init__()  # overriding __init__ to remove unwanted arguments.


# endregion
# region Unplaced operation definitions


@irdl_op_definition
class DecUnplacedObservableOp(IRDLOperation):
    """Declare a new unplaced observable."""

    name = "sobs.dec_unplaced_observable"

    result = result_def(EqAttrConstraint(UnplacedObservableType()))
    """The declared unplaced observable."""

    assembly_format = "attr-dict `->` type($result)"

    traits = traits_def(Pure())

    def __init__(self) -> None:
        super().__init__(result_types=[UnplacedObservableType()])


@irdl_op_definition
class LocateUnplacedObservableOp(IRDLOperation):
    """Locate an existing unplaced observable on one or more patches."""

    name = "sobs.locate_unplaced_observable"

    # Number of inputs constraint, must be at least 1 patch.
    _IP: ClassVar[IntConstraint] = IntVarConstraint("InputPatches", AtLeast(1))

    bases = prop_def(ArrayOfConstraint(RangeOf(base(PauliAttr)).of_length(_IP)))
    """Basis of the observable for each of the patches the observable is located on."""

    obs = operand_def(EqAttrConstraint(UnplacedObservableType()))
    """The observable to locate on patches."""
    patches = var_operand_def(RangeOf(SurfaceCodePatchConstraint()).of_length(_IP))
    """A strictly positive number of patches the observable is located on."""

    result = result_def(EqAttrConstraint(UnplacedObservableType()))
    """The located unplaced observable."""

    traits = traits_def(DecodingSideEffect())

    def __init__(
        self,
        bases: ArrayAttr[PauliAttr] | Iterable[PauliAttr] | str,
        obs: SSAValue,
        patches: Sequence[SSAValue],
    ) -> None:
        if isinstance(bases, str):
            if not PauliAttr.is_valid_pauli_string(bases):
                msg = (
                    "Expected a PauliString (that only contains X, Y, or Z, characters) "
                    f"but got '{bases}'."
                )
                raise RuntimeError(msg)
            bases = ArrayAttr(map(PauliAttr, bases))
        elif not isinstance(bases, ArrayAttr):
            bases = ArrayAttr(bases)
        super().__init__(
            operands=(obs, patches),
            result_types=[UnplacedObservableType()],
            properties={"bases": bases},
        )

    @override
    @classmethod
    def parse(cls, parser: Parser) -> LocateUnplacedObservableOp:
        """Parses a `sobs.locate_unplaced_observable` op's body as::

            `<` pauli-string `>` `(` $obs `)` `on` `(` $patches `)` attr-dict? `->` type($result)

        where ``pauli-string`` is a sequence of one or more Pauli (e.g., ``XZZX``).
        """
        with parser.in_angle_brackets():
            bases = parser.expect(
                lambda: qcore.PauliAttr.parse_optional_pauli_string(parser),
                "Expected a Pauli string in the form 'XYZ'",
            )
        with parser.in_parens():
            observable = parser.parse_operand()
        parser.parse_keyword("on")
        patches = parser.parse_comma_separated_list(parser.Delimiter.PAREN, parser.parse_operand)
        attributes = parser.parse_optional_attr_dict()
        parser.parse_punctuation("->")
        return_types = parser.parse_comma_separated_list(parser.Delimiter.NONE, parser.parse_type)

        return cls.create(
            operands=(observable, *patches),
            properties={"bases": bases},
            attributes=attributes,
            result_types=return_types,
        )

    @override
    def print(self, printer) -> None:
        """Print a `sobs.locate_unplaced_observable` op's body as::

            `<` pauli-string `>` `(` $obs `)` `on` `(` $patches `)` attr-dict? `->` type($result)

        where ``pauli-string`` is a sequence of one or more Pauli (e.g., ``XZZX``).
        """
        with printer.in_angle_brackets():
            qcore.PauliAttr.print_pauli_string(self.bases.data, printer)
        printer.print_string(" ")
        with printer.in_parens():
            printer.print_ssa_value(self.obs)
        printer.print_string(" on ")
        with printer.in_parens():
            printer.print_list(self.patches, printer.print_ssa_value)
        if self.attributes:
            printer.print_string(" ")
            printer.print_attr_dict(self.attributes)
        printer.print_string(" -> ")
        printer.print_list(self.result_types, printer.print_attribute)

    def basis_on(self, patch: SSAValue) -> PauliAttr:
        """Get the basis of the observable on the provided patch.

        Args:
            patch: patch for which we want to recover the basis.

        Returns:
            The basis of the observable on the provided patch.

        Raises:
            ValueError: if the observable is not applied on the provided patch.
        """
        try:
            index = self.patches.index(patch)
        except ValueError as e:
            msg = (
                "The provided patch is not an operand of the sobs.locate_unplaced_observable "
                "operation."
            )
            raise ValueError(msg) from e
        return self.bases.data[index]


# endregion


# region Placed operation definition


@irdl_op_definition
class DecObservableOp(IRDLOperation):
    """Declare a new observable on qubits."""

    name = "sobs.dec_observable"

    qubits = var_operand_def(RangeOf(base(QubitType)).of_length(AtLeast(1)))
    result = result_def(EqAttrConstraint(ObservableType()))
    """The declared observable."""

    assembly_format = "`(` $qubits `)` attr-dict `->` type($result)"

    traits = traits_def(DecodingSideEffect())

    def __init__(self, qubits: Sequence[SSAValue]) -> None:
        super().__init__(operands=[qubits], result_types=[ObservableType()])


@irdl_op_definition
class LocateObservableOp(IRDLOperation):
    """Locate an existing observable on one or more qubits."""

    name = "sobs.locate_observable"

    obs = operand_def(EqAttrConstraint(ObservableType()))
    """The observable to locate on qubits."""
    qubits = var_operand_def(RangeOf(QubitType()).of_length(AtLeast(1)))
    """A strictly positive number of qubits the observable is located on."""

    result = result_def(EqAttrConstraint(ObservableType()))
    """The located observable."""

    assembly_format = "`(` $obs `)` `on` `(` $qubits `)` attr-dict `->` type($result)"

    traits = traits_def(DecodingSideEffect(), HasCircuitAncestor())

    def __init__(self, obs: SSAValue, qubits: Sequence[SSAValue]) -> None:
        super().__init__(operands=(obs, qubits), result_types=[ObservableType()])


@irdl_op_definition
class MoveObservableOp(IRDLOperation):
    """Move an existing placed observable on a new support of qubits, potentially using measurements
    to perform the move."""

    name = "sobs.move_observable"

    obs = operand_def(EqAttrConstraint(ObservableType()))
    """The observable to locate on qubits."""
    qubits = var_operand_def(RangeOf(QubitType()).of_length(AtLeast(1)))
    """A strictly positive number of qubits the observable is located on."""
    measurements = var_operand_def(RangeOf(EqAttrConstraint(i1)))
    """Measurements used to move the observable and that should be included in its definition."""

    result = result_def(EqAttrConstraint(ObservableType()))
    """The located observable."""

    traits = traits_def(DecodingSideEffect(), HasCircuitAncestor())

    assembly_format = (
        "`(` $obs `)` `to` `(` $qubits `)` `using` `(` $measurements `)` "
        "attr-dict `->` type($result)"
    )
    irdl_options = (AttrSizedOperandSegments(as_property=True),)

    def __init__(
        self, obs: SSAValue, qubits: Sequence[SSAValue], measurements: Sequence[SSAValue]
    ) -> None:
        super().__init__(operands=(obs, qubits, measurements), result_types=[ObservableType()])


# endregion

Sobs = Dialect(
    "sobs",
    [
        DecUnplacedObservableOp,
        LocateUnplacedObservableOp,
        DecObservableOp,
        LocateObservableOp,
        MoveObservableOp,
    ],
    [ObservableType, UnplacedObservableType],
)
