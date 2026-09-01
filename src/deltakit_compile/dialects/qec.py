# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for the xDSL dialect for Stim-like QEC physical circuit annotations."""

from collections.abc import Iterable, Sequence
from typing import TypeVar

from typing_extensions import override
from xdsl.dialects.builtin import ArrayAttr, Float64Type, FloatAttr, IntegerType, Signedness, i1
from xdsl.ir import Dialect, Operation, OpResult, ParametrizedAttribute, SSAValue, TypeAttribute
from xdsl.irdl import (
    AnyOf,
    AtLeast,
    EqAttrConstraint,
    MessageConstraint,
    RangeOf,
    irdl_attr_definition,
    operand_def,
    opt_prop_def,
    result_def,
    traits_def,
)
from xdsl.irdl.operations import (
    IRDLOperation,
    irdl_op_definition,
    var_operand_def,
)
from xdsl.traits import Pure
from xdsl.utils.exceptions import VerifyException

from deltakit_compile.dialects.common.attributes import (
    OptPlainArrayOfFloat64Directive,
)
from deltakit_compile.dialects.common.constraints import MessageIntConstraint
from deltakit_compile.dialects.common.traits import HasSideEffects
from deltakit_compile.dialects.qcore import (
    DecodingSideEffect,
    HasCircuitAncestor,
    NoQuantumEffect,
    QuantumEffectKind,
    has_quantum_effect,
)
from deltakit_compile.dialects.sobs import ObservableType as SobsObservableType

# region Type definitions


@irdl_attr_definition
class DetectorRefType(ParametrizedAttribute, TypeAttribute):
    """A type for the referenceable result of a detector. This represents a specific detector at
    run time so it can be included into detector rounds."""

    name = "qec.detector_ref"

    def __init__(self) -> None:
        super().__init__()  # overriding __init__ to remove unwanted arguments.


@irdl_attr_definition
class ObservableType(ParametrizedAttribute, TypeAttribute):
    """A type for logical observables. This type represents a logical observable - not a reference -
    and so is always used in an SSA like fashion."""

    name = "qec.observable"

    def __init__(self) -> None:
        super().__init__()  # overriding __init__ to remove unwanted arguments.


# endregion
# region Operation definitions


@irdl_op_definition
class DetectorOp(IRDLOperation):
    """Add a set of measurements as an error indicator in the decoding problem.

    This op is treated as having modified the decoding problem being continuously decoded in the
    background by a decoder, which we model by giving it DecodingSideEffect. Detectors may be
    grouped into rounds by providing their references to qec.detector_round, but this is not
    required."""

    name = "qec.detector"

    coords = opt_prop_def(ArrayAttr[FloatAttr[Float64Type]])
    """The spatial coordinate for this detector."""

    measurements = var_operand_def(RangeOf(EqAttrConstraint(i1)))
    """The measurements to include in the detector."""

    result = result_def(EqAttrConstraint(DetectorRefType()))
    """A reference to this detector that can be used to attach it to a detector round."""

    assembly_format = (
        f"(`<` {OptPlainArrayOfFloat64Directive.use('$coords')}^ `>`)? "
        "`(` $measurements `)` attr-dict"
    )
    custom_directives = (OptPlainArrayOfFloat64Directive,)

    traits = traits_def(DecodingSideEffect(), HasCircuitAncestor())

    def __init__(
        self,
        measurements: Sequence[SSAValue],
        coordinates: Iterable[FloatAttr[Float64Type] | float] | None = None,
    ) -> None:
        if coordinates is not None:
            coordinates = ArrayAttr(
                [
                    FloatAttr(coord, Float64Type()) if isinstance(coord, float) else coord
                    for coord in coordinates
                ]
            )
        super().__init__(
            operands=[measurements],
            result_types=[DetectorRefType()],
            properties={"coords": coordinates},
        )


@irdl_op_definition
class DecObservableOp(IRDLOperation):
    """Declare a new observable."""

    name = "qec.dec_observable"

    result = result_def(EqAttrConstraint(ObservableType()))
    """The declared observable."""

    assembly_format = "attr-dict `->` type($result)"

    traits = traits_def(Pure(), NoQuantumEffect())

    def __init__(self) -> None:
        super().__init__(
            result_types=[ObservableType()],
        )


@irdl_op_definition
class ObservableIncludeOp(IRDLOperation):
    """Form a new observable from an existing observable and measurements that are XORed with it."""

    name = "qec.observable_include"

    in_obs = operand_def(EqAttrConstraint(ObservableType()))
    """The existing observable to XOR with."""

    measurements = var_operand_def(EqAttrConstraint(i1))
    """The measurements to XOR with the observable."""

    out_obs = result_def(EqAttrConstraint(ObservableType()))
    """The new observable that is the XOR of the input observable and measurements."""

    assembly_format = (
        " `(` $in_obs `)` `using` ` ` `(` $measurements `)` attr-dict `->` type($out_obs)"
    )

    traits = traits_def(Pure(), NoQuantumEffect(), HasCircuitAncestor())

    def __init__(self, observable: SSAValue, measurements: Sequence[SSAValue]) -> None:
        super().__init__(
            operands=[observable, measurements],
            result_types=[ObservableType()],
        )


@irdl_op_definition
class GetUncorrectedOp(IRDLOperation):
    """Get the uncorrected value of an observable.

    I.e., the XOR of all the measurement bits it's accumulated at that point with no decoding
    required."""

    name = "qec.get_uncorrected"

    obs = operand_def(
        MessageConstraint(
            EqAttrConstraint(ObservableType()) | EqAttrConstraint(SobsObservableType()),
            "Expected attribute !qec.observable or !sobs.observable for 'obs' operand.",
        )
    )
    """The observable to get the uncorrected value for."""

    result = result_def(EqAttrConstraint(i1))
    """The uncorrected result of the observable."""

    assembly_format = " `(` $obs `:` type($obs) `)` attr-dict `->` type($result)"

    traits = traits_def(Pure(), NoQuantumEffect())

    def __init__(self, observable: SSAValue) -> None:
        super().__init__(
            operands=[observable],
            result_types=[i1],
        )


@irdl_op_definition
class GetCorrectionOp(IRDLOperation):
    """Get the correction (has the value been flipped so far) of an observable.

    Given decoding is happening continuously in the background we can ask for a correction bit at
    any time. This op may therefore be used in deciding how the decoding problem should be windowed
    so that the decoder will have the correction available at that specific point in the program.

    Note, however, that the decoding may not be keeping up with current execution. This op is
    treated as blocking execution until the correction is made available."""

    name = "qec.get_correction"

    obs = operand_def(
        MessageConstraint(
            EqAttrConstraint(ObservableType()) | EqAttrConstraint(SobsObservableType()),
            "Expected attribute !qec.observable or !sobs.observable for 'obs' operand.",
        )
    )
    """The observable to get the correction value for."""

    result = result_def(EqAttrConstraint(i1))
    """The correction value result for the observable."""

    assembly_format = " `(` $obs `:` type($obs) `)` attr-dict `->` type($result)"

    traits = traits_def(Pure(), NoQuantumEffect())

    def __init__(self, observable: SSAValue) -> None:
        super().__init__(
            operands=[observable],
            result_types=[i1],
        )


@irdl_op_definition
class GetCorrectedOp(IRDLOperation):
    """Get the corrected value of an observable.

    Given decoding is happening continuously in the background we can ask for a corrected value at
    any time. This op may therefore be used in deciding how the decoding problem should be windowed
    so that the decoder will have the corrected value available at that specific point in the
    program.

    Note, however, that the decoding may not be keeping up with current execution. This op is
    treated as blocking execution until the correction is made available."""

    name = "qec.get_corrected"

    obs = operand_def(
        MessageConstraint(
            EqAttrConstraint(ObservableType()) | EqAttrConstraint(SobsObservableType()),
            "Expected attribute !qec.observable or !sobs.observable for 'obs' operand.",
        )
    )
    """The observable to get the correction value for."""

    result = result_def(EqAttrConstraint(i1))
    """The correction value result for the observable."""

    assembly_format = " `(` $obs `:` type($obs) `)` attr-dict `->` type($result)"

    traits = traits_def(Pure(), NoQuantumEffect())

    def __init__(self, observable: SSAValue) -> None:
        super().__init__(
            operands=[observable],
            result_types=[i1],
        )


@irdl_op_definition
class IsCorrectionReadyOp(IRDLOperation):
    """Check whether the correction (and corrected value) for an observable is ready to be read.

    Every new detector or modification to the observable in question (i.e. every new SSAValue
    created for it) is treated as extending the decoding problem, and so delaying when the
    correction could be available from the decoder. This Op returns a i1 SSAValue that will
    be True at runtime iff the observable has been decoded and is ready to have the correction
    or corrected value read.

    This op does not block execution until the correction is made available, allowing users to
    check it as part of a loop condition and perform memory or stabiliser measurements, for example,
    until the given observable has been decoded and is ready."""

    name = "qec.is_correction_ready"

    obs = operand_def(
        MessageConstraint(
            EqAttrConstraint(ObservableType()) | EqAttrConstraint(SobsObservableType()),
            "Expected attribute !qec.observable or !sobs.observable for 'obs' operand.",
        )
    )
    """The observable to check if a correction has been decoded for."""

    result = result_def(EqAttrConstraint(i1))
    """Whether the correction value result for the observable is now available."""

    assembly_format = " `(` $obs `:` type($obs) `)` attr-dict `->` type($result)"

    traits = traits_def(Pure(), NoQuantumEffect())

    def __init__(self, observable: SSAValue) -> None:
        super().__init__(
            operands=[observable],
            result_types=[i1],
        )


T = TypeVar("T", bound=Operation)


@irdl_op_definition
class MeasurementRoundOp(IRDLOperation):
    """Declare a measurement round.

    Groups a set of measurements into a measurement round, where a measurement round is an efficient
    grouping for transmission to a QEC system (decoder), typically determined based on the
    measurements all being taken at around the same time.

    For example, the measurements from a single stabiliser round would form a single measurement
    round, as would measuring out the data qubits at the end of a memory experiment, but if
    measuring the data qubits is combined into the final stabiliser round then that is one big
    measurement round. This is effectively a label that gives extra information to the decoder
    compilation stage in a full qec system.
    """

    name = "qec.measurement_round"
    # ui1 needed for as long as we use this op with the qasm3 dialect
    measurements = var_operand_def(
        RangeOf(AnyOf.get(i1, IntegerType(1, Signedness.UNSIGNED))).of_length(
            MessageIntConstraint(
                AtLeast(1),
                "qec.measurement_round must have at least 1 quantum measure op.",
            )
        )
    )

    assembly_format = "`(` $measurements `:` type($measurements) `)` attr-dict"

    traits = traits_def(HasSideEffects())
    # HasCircuitAncestor() cannot be included for as long as we use this with the qasm3 dialect

    def __init__(self, measurements: Sequence[SSAValue]):
        super().__init__(operands=[measurements])

    @override
    def verify_(self) -> None:
        """
        Verify that the measurement OpResult parents have the qubit measurement effect trait.
        """
        for op_result in self.measurements:
            if not isinstance(op_result, OpResult):
                msg = (
                    "All measurement operands are expected to be of OpResult type,"
                    f" {type(op_result)} type found."
                )
                raise VerifyException(msg)
            if not has_quantum_effect(op_result.op, QuantumEffectKind.MEASURE):
                msg = "OpResult parent must have the MEASURE QuantumEffect trait."
                raise VerifyException(msg)

    def get_round_measurement_ops(self, expected_type: type[T]) -> set[T]:
        """
        Get the parent measure operations of the stored OpResults.
        """
        unique_measurement_ops = {
            op_res.op
            for op_res in self.measurements
            if isinstance(op_res, OpResult) and isinstance(op_res.op, expected_type)
        }

        all_measurement_ops = {
            op_res.op for op_res in self.measurements if isinstance(op_res, OpResult)
        }

        if wrong_type_ops := all_measurement_ops.difference(unique_measurement_ops):
            str_wrong_type_ops = ", ".join(op.name for op in wrong_type_ops)
            msg = (
                f"Found {len(wrong_type_ops)} operations that are not of expected"
                f" type '{expected_type.name}' these ops are: {str_wrong_type_ops}"
            )
            raise ValueError(msg)

        return unique_measurement_ops


@irdl_op_definition
class DetectorRoundOp(IRDLOperation):
    """Declare a detector round.

    Groups a set of detectors into a detector round, where a detector round is the set of detectors
    that would form a single syndrome as input to a streaming decoder (QEC system).

    For example, the detectors from a single stabiliser round would form a single detector round,
    as would the detectors formed from measuring the data qubits at the end of a memory experiment,
    regardless of how the grouping of the measurement rounds. This is effectively a label that gives
    extra information to the decoder compilation stage in a full qec system.
    """

    name = "qec.detector_round"

    detectors = var_operand_def(RangeOf(DetectorRefType()))

    assembly_format = "`(` $detectors  `)` attr-dict"

    def __init__(self, detectors: Sequence[SSAValue]):
        super().__init__(operands=[detectors])

    traits = traits_def(HasSideEffects(), HasCircuitAncestor())


# endregion

Qec = Dialect(
    "qec",
    [
        DetectorOp,
        DecObservableOp,
        ObservableIncludeOp,
        GetUncorrectedOp,
        GetCorrectionOp,
        GetCorrectedOp,
        IsCorrectionReadyOp,
        MeasurementRoundOp,
        DetectorRoundOp,
    ],
    [DetectorRefType, ObservableType],
)
