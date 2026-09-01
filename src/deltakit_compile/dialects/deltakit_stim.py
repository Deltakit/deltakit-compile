# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for the Deltakit-Stim xDSL dialect that extends the Stim dialect with leakage ops."""

from collections.abc import Sequence
from typing import ClassVar, cast

from typing_extensions import override
from xdsl.dialects.builtin import Float64Type, FloatAttr, StringAttr, f64, i1
from xdsl.ir import Dialect, SSAValue
from xdsl.irdl.operations import irdl_op_definition, opt_prop_def, traits_def, var_result_def
from xdsl.printer import Printer
from xdsl.utils.exceptions import VerifyException

from deltakit_compile.dialects.common.attributes import OptPlainFloat64Directive
from deltakit_compile.dialects.qcore import QubitMeasureEffect
from deltakit_compile.dialects.stim import TAG_ATTR, GateOp, QubitAllocOp, SingleProbabilityNoiseOp


@irdl_op_definition
class HeraldLeakageEventOp(GateOp):
    """Determine whether the targeted qubits have leaked. If noise is provided, this is the
    probability that the leaked qubit is misclassified as not having leaked."""

    name = "deltakit_stim.herald_leakage_event"

    heralds = var_result_def(i1)
    noise = opt_prop_def(FloatAttr[Float64Type])

    traits = traits_def(QubitMeasureEffect("targets"))

    assembly_format = (
        f"` ` (`<` {OptPlainFloat64Directive.use('$noise')}^ `>` ` `)? "
        "`(` $targets `)` attr-dict `->` type(results)"
    )
    custom_directives = (OptPlainFloat64Directive,)

    def __init__(
        self,
        targets: Sequence[SSAValue],
        noise: FloatAttr[Float64Type] | float | None = None,
        tag: str | StringAttr | None = None,
    ):
        if isinstance(noise, float):
            noise = FloatAttr(noise, f64)
        super().__init__(
            operands=[targets],
            result_types=[[i1] * len(targets)],
            properties={
                "noise": noise,
            },
            attributes={TAG_ATTR: StringAttr.get(tag) if tag is not None else None},
        )

    @override
    def print_stim(self, printer: Printer, recs: list[SSAValue]):
        printer.print_string("HERALD_LEAKAGE_EVENT")
        printer.print_string(self._get_stim_tag_with_brackets())
        recs.extend(self.results)
        if self.noise:
            printer.print_string(f"({self.noise.value.data})")

        for ssa_qubit in self.operands:
            qubit_id = cast(QubitAllocOp, ssa_qubit.owner).id.data
            printer.print_string(f" {qubit_id}")

    @override
    def verify_(self):
        """Verify targets and heralds lengths are the same and non-zero."""
        if len(self.heralds) != len(self.targets):
            msg = (
                "A herald leakage event must return the same number of heralds as qubits it "
                "operates on"
            )
            raise VerifyException(msg)
        if not self.heralds:
            msg = "A herald leakage event must be on a non-zero number of qubits"
            raise VerifyException(msg)


@irdl_op_definition
class LeakageOp(SingleProbabilityNoiseOp):
    """Leaks the provided qubits with the given probability."""

    name = "deltakit_stim.leakage"
    STIM_INSTR_NAME: ClassVar[str] = "LEAKAGE"


@irdl_op_definition
class RelaxOp(SingleProbabilityNoiseOp):
    """Relaxes the provided qubits with the given probability."""

    name = "deltakit_stim.relax"
    STIM_INSTR_NAME: ClassVar[str] = "RELAX"


DeltakitStim = Dialect("deltakit-stim", [HeraldLeakageEventOp, LeakageOp, RelaxOp], [])
