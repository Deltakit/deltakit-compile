# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for the plaquette dialect.

This dialect is used as an intermediate representation in the patch lowering pipeline between the
``log_asm`` dialect and the physical circuit dialects.

"""

from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from enum import Enum
from typing import ClassVar

from typing_extensions import TypeVar, override
from xdsl.dialects.builtin import I1, ArrayAttr, ArrayOfConstraint, IntAttr, NoneAttr, i1
from xdsl.dialects.utils import AbstractYieldOperation
from xdsl.ir import (
    Attribute,
    Block,
    Dialect,
    Operation,
    OpResult,
    ParametrizedAttribute,
    Region,
    SSAValue,
    SSAValues,
    VerifyException,
)
from xdsl.irdl import (
    AtLeast,
    AttrConstraint,
    AttrSizedOperandSegments,
    BaseAttr,
    ConstraintContext,
    IntConstraint,
    IntVarConstraint,
    IRDLOperation,
    RangeOf,
    base,
    irdl_attr_definition,
    irdl_op_definition,
    lazy_traits_def,
    opt_prop_def,
    param_def,
    prop_def,
    traits_def,
    var_operand_def,
    var_region_def,
    var_result_def,
)
from xdsl.parser import AttrParser
from xdsl.printer import Printer
from xdsl.traits import (
    HasParent,
    IsTerminator,
    OpTrait,
    Pure,
    RecursiveMemoryEffect,
    SingleBlockImplicitTerminator,
)

from deltakit_compile.dialects.common.attributes import AnyEnumAttribute
from deltakit_compile.dialects.common.constraints import NO_ENTRY_ARGS, MessageIntConstraint, SetOf
from deltakit_compile.dialects.qcore import (
    HasCircuitAncestor,
    NoQuantumEffect,
    PauliStringAttr,
    QubitType,
    RecursiveQuantumEffect,
)

# region Traits


class HasRoundAncestor(OpTrait):
    """A trait that indicates that the operation must be contained within a plaquette.round op."""

    @override
    def verify(self, op: Operation) -> None:
        """Verify that the op is inside a round op."""
        if op.parent_op() is not None and not self.has_round_ancestor(op):
            msg = "Op must be inside a plaquette.round operation."
            raise VerifyException(msg)

    @staticmethod
    def _walk_ancestors(op: Operation) -> Iterator[Operation]:
        """Iterates over the ancestors of an operation, including itself."""
        curr: Operation | None = op
        while curr is not None:
            yield curr
            curr = curr.parent_op()

    @staticmethod
    def get_round_ancestor(op: Operation) -> Operation | None:
        """Get the most recent round ancestor or None if one doesn't exist."""
        for a in HasRoundAncestor._walk_ancestors(op):
            if isinstance(a, RoundOp):
                return a
        return None

    @staticmethod
    def has_round_ancestor(op: Operation) -> bool:
        return HasRoundAncestor.get_round_ancestor(op) is not None


# endregion


# region Stabiliser measurement attributes


class StabiliserMeasurementMethodAttribute(ParametrizedAttribute, ABC):
    """Base class for all the schedule measurement methods."""

    name = "plaquette.abstract_measurement_method"

    @property
    @abstractmethod
    def num_qubits(self) -> int:
        """Number of data qubits the stabiliser measurement method expects."""

    @property
    @abstractmethod
    def num_measurements(self) -> int:
        """Number of measurements produced by the stabiliser measurement method."""

    @property
    @abstractmethod
    def stabiliser_weights(self) -> tuple[int, ...]:
        """Weights of the different stabilisers measured by the stabiliser measurement method.

        The number of stabilisers measured by the stabiliser measurement method should be the length
        of the returned tuple. Each entry corresponds to the weight (i.e., number of non-trivial
        Pauli matrices) of the corresponding stabiliser.

        The returned values are all expected to be in ``[1, self.num_qubits]`` (because of weight-0
        stabiliser is trivial, and we won't be measuring a stabiliser on something else than data
        qubits).
        """

    @classmethod
    def constr(
        cls,
        num_qubits: IntConstraint | None = None,
        num_measurements: IntConstraint | None = None,
        stabiliser_weights: int | IntConstraint | Sequence[int | IntConstraint] | None = None,
    ) -> AttrConstraint[StabiliserMeasurementMethodAttribute]:
        return StabiliserMeasurementMethodConstraint(
            num_qubits=num_qubits,
            num_measurements=num_measurements,
            stabiliser_weights=stabiliser_weights,
        )


class StabiliserMeasurementMethodConstraint(AttrConstraint[StabiliserMeasurementMethodAttribute]):
    """Constraint an attribute to be a valid stabiliser measurement method.

    Arguments:
        num_qubits: constraint on the number of qubits that should be supported by the stabiliser
            measurement method.
        num_measurements: constraint on the number of measurements that should be performed by the
            stabiliser measurement method.
        stabiliser_weights: constraint on the weight of the stabilisers that should be measured by
            the stabiliser measurement method. Note that this argument also implicitly constraint
            the number of stabilisers being measured.
    """

    def __init__(
        self,
        num_qubits: int | IntConstraint | None = None,
        num_measurements: int | IntConstraint | None = None,
        stabiliser_weights: int | IntConstraint | Sequence[int | IntConstraint] | None = None,
    ) -> None:
        if num_qubits is None:
            num_qubits = AtLeast(1)
        if num_measurements is None:
            num_measurements = AtLeast(1)
        if stabiliser_weights is None:
            stabiliser_weights = AtLeast(1)
        if isinstance(stabiliser_weights, (int, IntConstraint)):
            stabiliser_weights = [stabiliser_weights]

        self._num_qubits = MessageIntConstraint(num_qubits, "Number of qubits")
        self._num_measurements = MessageIntConstraint(num_measurements, "Number of measurements")
        self._stabiliser_weights = [
            MessageIntConstraint(constr, f"Stabiliser {i} weight")
            for i, constr in enumerate(stabiliser_weights)
        ]

    @override
    def verify(self, attr: Attribute, constraint_context: ConstraintContext) -> None:
        """Check if the attribute satisfies the constraint, or raise an exception otherwise."""
        BaseAttr(StabiliserMeasurementMethodAttribute).verify(attr, constraint_context)
        assert isinstance(attr, StabiliserMeasurementMethodAttribute)
        self._num_qubits.verify(attr.num_qubits, constraint_context)
        self._num_measurements.verify(attr.num_measurements, constraint_context)
        if len(self._stabiliser_weights) != len(attr.stabiliser_weights):
            msg = (
                f"Expected {len(self._stabiliser_weights)} stabilisers but got "
                f"{len(attr.stabiliser_weights)}."
            )
            raise VerifyException(msg)
        for constr, swattr in zip(self._stabiliser_weights, attr.stabiliser_weights, strict=True):
            constr.verify(swattr, constraint_context)

    @override
    def variables(self) -> set[str]:
        return (self._num_qubits.variables() | self._num_measurements.variables()).union(
            *(constr.variables() for constr in self._stabiliser_weights)
        )

    @override
    def mapping_type_vars(
        self, type_var_mapping: Mapping[TypeVar, AttrConstraint | IntConstraint]
    ) -> AttrConstraint[StabiliserMeasurementMethodAttribute]:
        return StabiliserMeasurementMethodConstraint(
            self._num_qubits.mapping_type_vars(type_var_mapping),
            self._num_measurements.mapping_type_vars(type_var_mapping),
            [constr.mapping_type_vars(type_var_mapping) for constr in self._stabiliser_weights],
        )


@irdl_attr_definition
class SynchronisedScheduleAttr(StabiliserMeasurementMethodAttribute):
    """An attribute representing the schedule of typical stabiliser measurements in surface code.

    This attribute can be provided to the ``stabs_measurement`` attribute of ``plaquette.plaquette``
    and represents a specific type of stabiliser measurement where:

    - there is a single syndrome qubit that is used to measure the stabiliser,
    - each data qubit interacts once with the syndrome qubit,
    - stabiliser measurements are all synchronised.

    In particular, this attribute cannot represent the following syndrome measurements:

    - super-dense syndrome extraction for the colour code (because there are 2 syndrome qubits),
    - mid-cycle-style syndrome extraction (because it does not use a "syndrome" qubit and entangling
      gates are applied in parallel),
    - diagonal hook-error schedule in general (because in order to avoid a lot of idle time, you
      probably want to interleave the syndrome measurement circuits, and that requires resets and
      measurements to not be synchronised).

    The above syndrome measurements should instead be represented by different attributes like this
    one that will have to be defined separately.

    The ``schedule`` attribute can have ``None`` entries, which means that the corresponding qubit
    is not used in the syndrome extraction circuit.

    Examples of this attribute:

    - `#plaquette.synchronised_schedule<[0, 2, 1, 3]>`
    - `#plaquette.synchronised_schedule<[0, 1, 2, 3]>`
    - `#plaquette.synchronised_schedule<[none, none, 2, 3]>`

    """

    name = "plaquette.synchronised_schedule"

    schedule: ArrayAttr[IntAttr[int] | NoneAttr] = param_def(
        ArrayOfConstraint(
            SetOf(
                RangeOf(IntAttr.constr(AtLeast(0)) | base(NoneAttr)),
                filter=lambda elem: isinstance(elem, IntAttr),
            )
        )
    )

    """The schedule at which each data-qubit should interact with the syndrome qubit. Starts at 0,
    so the first available schedule is ``0``."""

    def __init__(self, schedule: Iterable[int | None]):
        super().__init__(
            ArrayAttr([IntAttr(s) if isinstance(s, int) else NoneAttr() for s in schedule])
        )

    @classmethod
    @override
    def parse_parameters(cls, parser: AttrParser) -> list[Attribute]:
        with parser.in_angle_brackets():
            return [
                ArrayAttr(
                    parser.parse_comma_separated_list(
                        parser.Delimiter.SQUARE,
                        lambda: (
                            NoneAttr()
                            if parser.parse_optional_keyword("none") is not None
                            else IntAttr(
                                parser.parse_integer(allow_boolean=False, allow_negative=False)
                            )
                        ),
                    )
                )
            ]

    @override
    def print_parameters(self, printer: Printer) -> None:
        with printer.in_angle_brackets(), printer.in_square_brackets():
            printer.print_list(
                self.schedule,
                lambda i: (
                    printer.print_int(i.data)
                    if isinstance(i, IntAttr)
                    else printer.print_string("none")
                ),
            )

    @property
    @override
    def num_qubits(self) -> int:
        return len(self.schedule)

    @property
    @override
    def num_measurements(self) -> int:
        return 1

    @property
    @override
    def stabiliser_weights(self) -> tuple[int, ...]:
        return (sum(not isinstance(s, NoneAttr) for s in self.schedule),)


class RotatedSurfaceCodePlaquetteShapeTypeEnum(Enum):
    r"""Represents the shape of a rotated surface code plaquette.

    Values associated to enumeration members represents the data-qubit indices the corresponding
    plaquette has using the Z-ordering::

        0-----1
        |     |
        |     |
        2-----3

    For example, the ``TOP`` plaquette::

          x
         / \
        2---3

    is applied on data qubits ``2`` and ``3`` and the ``LEFT`` plaquette::

          1
         /|
        o |
         \|
          3

    is applied on qubits ``1`` and ``3``. Note that ``LEFT`` here means "the plaquette applied on
    the left boundary", which uses the qubits on the right of the regular bulk shape.
    """

    SQUARE = (0, 1, 2, 3)
    """The regular weight-4 bulk stabiliser plaquette."""
    TOP = (2, 3)
    """Weight-2 stabiliser on the top-boundary of the patch."""
    BOTTOM = (0, 1)
    """Weight-2 stabiliser on the bottom-boundary of the patch."""
    LEFT = (1, 3)
    """Weight-2 stabiliser on the left-boundary of the patch."""
    RIGHT = (0, 2)
    """Weight-2 stabiliser on the right-boundary of the patch."""


@irdl_attr_definition
class RotatedSurfaceCodePlaquetteShapeTypeAttr(
    AnyEnumAttribute[RotatedSurfaceCodePlaquetteShapeTypeEnum]
):
    """Attribute representing a plaquette shape.

    This is a temporary attribute until we have a reliable way to track qubit origins, at which
    point all the information contained in this attribute can be devised from the qubit coordinates.
    """

    name = "plaquette.rotated_surface_plaquette_shape"

    def __init__(self, shape_type: RotatedSurfaceCodePlaquetteShapeTypeEnum):
        super().__init__(shape_type)

    @property
    def num_qubits(self) -> int:
        return len(self.data.value)


# endregion

# region Operations


@irdl_op_definition
class YieldOp(AbstractYieldOperation[Attribute]):
    """Yield SSAValues from the scope of one region to its containing region."""

    name = "plaquette.yield"

    traits = lazy_traits_def(
        lambda: (IsTerminator(), HasParent(RoundOp, SubCircuitOp), Pure(), NoQuantumEffect())
    )


@irdl_op_definition
class RoundOp(IRDLOperation):
    """A container for plaquette operations that behaves nearly identically to ``qstruct.parallel``.

    This operation is a container for ``plaquette`` operations. Its only difference with
    ``qstruct.parallel`` is that the contained operations are allowed to overlap (i.e., use the same
    qubits). This operation is essentially a contract with the compiler that says that the
    operations contained in the ``plaquette.round`` will eventually be lowered down to operations
    that do not overlap and will be valid within a ``qstruct.parallel``.

    Parameters:
        qubits: SSA values representing the qubits this round operation is applied on.
        parallel_regions: Regions that are applied in parallel during the round. Each region will
            typically contain a ``plaquette.plaquette`` or ``plaquette.sub_circuit`` operation.
        measurements: If an integer, the number of measurements returned by the operation. Else, the
            types of measurements returned.

    Raises:
        RuntimeError: if ``measurements`` is a strictly negative integer.

    Attributes:
        name: operation name.
        qubits: Qubits that will be used in blocks of this round operation.
        par_regions: Regions that are supposed to be executed in parallel within the round
            operation.
        measurements: Measurements returned by the round, in the order of regions and in which each
            appear in its region.
        traits: xDSL specific attribute.
        assembly_format: xDSL specific attribute.
    """

    name = "plaquette.round"

    # Number of qubits constraint, must be at least 1 qubit.
    _DQ: ClassVar[IntConstraint] = IntVarConstraint("Qubits", AtLeast(1))

    qubits = var_operand_def(RangeOf(QubitType()).of_length(_DQ))
    par_regions = var_region_def("single_block", entry_args=RangeOf(QubitType()).of_length(_DQ))
    measurements = var_result_def(RangeOf(i1))

    traits = traits_def(
        RecursiveQuantumEffect(),
        RecursiveMemoryEffect(),
        SingleBlockImplicitTerminator(YieldOp),
        HasCircuitAncestor(),
    )

    assembly_format = "`(` $qubits `)` attr-dict `->` type($measurements) $par_regions"

    def __init__(
        self,
        qubits: Sequence[SSAValue],
        parallel_regions: Sequence[Region | Block | Sequence[Operation]],
        measurements: Sequence[Attribute] | int,
    ) -> None:
        if isinstance(measurements, int):
            if measurements < 0:
                msg = f"Cannot have a negative number of measurements. Got {measurements}."
                raise RuntimeError(msg)
            measurements = list(itertools.repeat(i1, measurements))
        regions = [Region(reg) if isinstance(reg, Block) else reg for reg in parallel_regions]
        super().__init__(operands=[qubits], regions=[regions], result_types=[measurements])

    def get_yielded_values(self) -> list[SSAValue]:
        """Get the SSAValues yielded from all regions."""
        return list(
            itertools.chain.from_iterable(
                yield_op.operands
                for region in self.par_regions
                if isinstance(yield_op := region.block.last_op, YieldOp)
            )
        )

    @override
    def verify_(self) -> None:
        """Verify that the yielded SSAValues at the end of the regions match the SSAValues returned
        by the op."""
        yielded_values = self.get_yielded_values()
        if len(yielded_values) != len(self.measurements):
            msg = (
                f"The number of variables yielded from the parallel regions ({len(yielded_values)})"
                " doesn't match the number returned from the round op containing them "
                f"({len(self.measurements)})"
            )
            raise VerifyException(msg)
        for yielded_value, result_value in zip(yielded_values, self.measurements, strict=True):
            if yielded_value.type != result_value.type:
                msg = (
                    f"Type of variable yielded from parallel region ({yielded_value.type}) doesn't "
                    "match the type of the corresponding variable returned from the round op "
                    f"containing said region ({result_value.type})"
                )
                raise VerifyException(msg)


@irdl_op_definition
class PlaquetteOp(IRDLOperation):
    """Applies a plaquette on qubits.

    Args:
        data_qubits: SSA values representing the data-qubits this plaquette is applied on.
        stabilisers: stabiliser(s) that should be measured by this plaquette.
        measurements: measurements returned by this plaquette. Can either be a sequence of
            return types (that should be ``i1``) or an integer which represents the number of
            measurements that are returned by this plaquette.
        ancilla_qubits: Optional SSA values representing qubits that are not involved in any of
            the provided ``stabilisers`` but can be used by the plaquette if needed. These
            qubits might be used when translating a plaquette to a circuit, to choose the best
            syndrome extraction circuit possible with the provided resources.
        stabiliser_measurement_method: An optional attribute. If provided, it should be a valid and
            complete description of a type of stabiliser measurement circuit that is able to measure
            the ``stabilisers`` on ``data_qubits``, potentially using ``ancilla_qubits``, and
            produce exactly the number of ``measurements`` declared in this plaquette. Note that
            qubits in ``ancilla_qubits`` do not **have** to be used by the method, but **can** be
            used.

    Raises:
        RuntimeError: if ``measurements`` is a strictly negative integer.

    Attributes:
        name: operation name.
        stabilisers: Stabiliser(s) that should be measured by the operation. Should be the same
            length as the provided data-qubits.
        stabs_measurement: An optional "stabiliser measurement" method that are valid for
            the provided ``stabilisers``, ``data_qubits``, ``ancilla_qubits`` and ``measurements``.
        data_qubits: Qubits on which stabilisers to be measured are defined.
        ancilla_qubits: Additional ancilla qubits that can be used to measure the stabiliser(s).
        measurements: Measurements returned by the plaquette. Should include at least one bit per
            stabiliser, and might include an arbitrary number of additional bits (e.g., flag bits).
        traits: xDSL specific attribute.
        assembly_format: xDSL specific attribute.
        irdl_options: xDSL specific attribute.
        custom_directives: xDSL specific attribute.
    """

    name = "plaquette.plaquette"

    # Number of data-qubits constraint, must be at least 1 qubit.
    _DQ: ClassVar[IntConstraint] = IntVarConstraint("DataQubits", AtLeast(1))
    # Number of stabilisers constraint, must be at least 1 stabiliser.
    _ST: ClassVar[IntConstraint] = IntVarConstraint("Stabilisers", AtLeast(1))
    # Number of returned measurements constraint, must be at least 1 bit.
    _MS: ClassVar[IntConstraint] = IntVarConstraint("Measurements", AtLeast(1))

    stabilisers = prop_def(
        ArrayOfConstraint(RangeOf(PauliStringAttr.constr(length=_DQ)).of_length(_ST))
    )
    stabs_measurement = opt_prop_def(
        StabiliserMeasurementMethodAttribute.constr(num_qubits=_DQ, num_measurements=_MS)
    )

    data_qubits = var_operand_def(RangeOf(QubitType()).of_length(_DQ))
    ancilla_qubits = var_operand_def(RangeOf(QubitType()))
    measurements = var_result_def(RangeOf(i1).of_length(_MS))

    traits = traits_def(HasRoundAncestor())

    assembly_format = (
        f"`<` {PauliStringAttr.plain_array_of_directive('$stabilisers')} "
        f"(`,` $stabs_measurement^ )? `>` "
        "` ` `on` ` ` `(` $data_qubits `)` "
        "( ` ` `using` ` ` `(` $ancilla_qubits^ `)` )? "
        "attr-dict `->` type($measurements)"
    )
    irdl_options = (AttrSizedOperandSegments(as_property=True),)
    custom_directives = (PauliStringAttr.plain_array_of_directive(),)

    def __init__(
        self,
        data_qubits: Sequence[SSAValue],
        stabilisers: PauliStringAttr | Sequence[PauliStringAttr],
        measurements: Sequence[Attribute] | int,
        ancilla_qubits: Sequence[SSAValue] = (),
        stabiliser_measurement_method: StabiliserMeasurementMethodAttribute | None = None,
    ) -> None:
        properties: dict[str, Attribute] = {
            "stabilisers": ArrayAttr(
                [stabilisers] if isinstance(stabilisers, PauliStringAttr) else stabilisers
            )
        }
        if stabiliser_measurement_method is not None:
            properties["stabs_measurement"] = stabiliser_measurement_method
        if isinstance(measurements, int):
            if measurements < 0:
                msg = f"Cannot have a negative number of measurements. Got {measurements}."
                raise RuntimeError(msg)
            measurements = list(itertools.repeat(i1, measurements))
        super().__init__(
            operands=(data_qubits, ancilla_qubits),
            result_types=[measurements],
            properties=properties,
        )

    @override
    def verify_(self) -> None:
        # Ensure that no qubit appear twice.
        qubit_counter = Counter(itertools.chain(self.data_qubits, self.ancilla_qubits))
        num_duplicated_qubits = sum(1 for count in qubit_counter.values() if count > 1)
        if num_duplicated_qubits > 0:
            msg = (
                f"Found {num_duplicated_qubits} qubits that were provided more than once to a "
                "plaquette.plaquette operation. Operands of such an operation should be unique."
            )
            raise VerifyException(msg)
        # Ensure that there is at least one measurement per stabiliser
        if len(self.measurements) < len(self.stabilisers):
            msg = (
                "Expected at least one measurement result per stabiliser but got "
                f"{len(self.measurements)} measurements and {len(self.stabilisers)} stabilisers."
            )
            raise VerifyException(msg)
        # Ensure that the stabilisers provide the correct number of measurements
        if self.stabs_measurement is not None and (
            (num_measurements := self.stabs_measurement.num_measurements) != len(self.measurements)
        ):
            msg = (
                f"Expected the stabiliser measurement methods to return "
                f"{len(self.measurements)} bits but found {num_measurements} instead."
            )
            raise VerifyException(msg)

    @property
    def has_measurement_method(self) -> bool:
        return self.stabs_measurement is not None


@irdl_op_definition
class SubCircuitOp(IRDLOperation):
    name = "plaquette.sub_circuit"

    seq_regions = var_region_def("single_block", entry_args=NO_ENTRY_ARGS)
    """Regions each containing gates that can be executed in parallel. Regions are ordered and
    will be executed sequentially."""
    measurements = var_result_def(RangeOf(i1))
    """Measurement bits returned by the circuit."""

    traits = traits_def(HasRoundAncestor(), RecursiveQuantumEffect(), RecursiveMemoryEffect())

    assembly_format = "attr-dict `->` type($measurements) $seq_regions"

    def __init__(
        self,
        sequential_regions: Sequence[Region | Block | Sequence[Operation]],
        measurements: Sequence[Attribute] | int,
    ) -> None:
        if isinstance(measurements, int):
            if measurements < 0:
                msg = f"Cannot have a negative number of measurements. Got {measurements}."
                raise RuntimeError(msg)
            measurements = list(itertools.repeat(i1, measurements))
        regions = [Region(reg) if isinstance(reg, Block) else reg for reg in sequential_regions]
        super().__init__(regions=[regions], result_types=[measurements])

    def _get_yielded_values(self) -> list[SSAValue]:
        """Get the SSAValues yielded from all regions."""
        return list(
            itertools.chain.from_iterable(
                yield_op.operands
                for region in self.seq_regions
                if isinstance(yield_op := region.block.last_op, YieldOp)
            )
        )

    @override
    def verify_(self) -> None:
        """Verify that the yielded SSAValues at the end of the regions match the SSAValues returned
        by the op."""
        yielded_values = self._get_yielded_values()
        if len(yielded_values) != len(self.measurements):
            msg = (
                f"The number of variables yielded from the parallel regions ({len(yielded_values)})"
                " doesn't match the number returned from the round op containing them "
                f"({len(self.measurements)})"
            )
            raise VerifyException(msg)
        for yielded_value, result_value in zip(yielded_values, self.measurements, strict=True):
            if yielded_value.type != result_value.type:
                msg = (
                    f"Type of variable yielded from parallel region ({yielded_value.type}) doesn't "
                    "match the type of the corresponding variable returned from the round op "
                    f"containing said region ({result_value.type})"
                )
                raise VerifyException(msg)

    def get_results_for_yield(self, yield_op: YieldOp) -> SSAValues[OpResult[I1]]:
        """Returns the results of `self` corresponding to the given `YieldOp` that must be the last
        op of one of the regions in `seq_regions`."""
        offset = 0
        for region in self.seq_regions:
            child_yield = region.block.last_op
            assert isinstance(child_yield, YieldOp)
            if yield_op == child_yield:
                return self.measurements[offset : offset + len(child_yield.arguments)]
            offset += len(child_yield.arguments)
        msg = "Provided YieldOp does not belong to this SubCircuitOp"
        raise ValueError(msg)


# endregion

Plaquette = Dialect(
    "plaquette",
    [YieldOp, RoundOp, PlaquetteOp, SubCircuitOp],
    [SynchronisedScheduleAttr, RotatedSurfaceCodePlaquetteShapeTypeAttr],
)
