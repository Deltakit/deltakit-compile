# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for the xDSL dialect for structuring quantum circuits."""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from enum import auto
from typing import ClassVar, Literal, cast

from typing_extensions import override
from xdsl.dialects.builtin import IndexType, IntAttr, IntegerType, TensorType
from xdsl.dialects.utils import AbstractYieldOperation
from xdsl.ir import (
    Attribute,
    AttributeCovT,
    AttributeInvT,
    Block,
    BlockArgument,
    Dialect,
    Operation,
    OpResult,
    Region,
    SSAValue,
)
from xdsl.irdl import (
    AnyAttr,
    AnyInt,
    AtLeast,
    AttrConstraint,
    IntVarConstraint,
    RangeConstraint,
    RangeOf,
    RangeVarConstraint,
    base,
    prop_def,
    region_def,
    var_operand_def,
)
from xdsl.irdl.attributes import irdl_attr_definition
from xdsl.irdl.operations import (
    IRDLOperation,
    irdl_op_definition,
    lazy_traits_def,
    traits_def,
    var_region_def,
    var_result_def,
)
from xdsl.pattern_rewriter import RewritePattern
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

from deltakit_compile.dialects.common.attributes import AnyEnumAttribute, PlainIntAttr
from deltakit_compile.dialects.common.constraints import SumOver
from deltakit_compile.dialects.common.traits import HasSideEffects
from deltakit_compile.dialects.qcore import (
    IsCircuit,
    QubitRegType,
    QubitType,
    RecursiveQuantumEffect,
    qubit_count,
)
from deltakit_compile.dialects.stim import NoQuantumEffect
from deltakit_compile.utilities.base_enums import BetterStrEnum

# region Attribute definitions


class _AlignmentEnum(BetterStrEnum):
    """Enum for parallel alignment options."""

    TOP = auto()
    """The first op in each region starts at the same time."""
    BOTTOM = auto()
    """The last op in each region ends at the same time."""


@irdl_attr_definition
class AlignmentAttr(AnyEnumAttribute[_AlignmentEnum]):
    """An Attribute for the possible ways operations can be aligned between the parallel regions of
    a qstruct.parallel."""

    name = "qstruct.align"

    def __init__(self, alignment: _AlignmentEnum | Literal["TOP", "BOTTOM"]):
        if not isinstance(alignment, _AlignmentEnum):
            alignment = _AlignmentEnum[alignment]
        super().__init__(alignment)

    @classmethod
    def TOP(cls) -> AlignmentAttr:  # noqa: N802
        """The first op in each region starts at the same time."""
        return cls(_AlignmentEnum.TOP)

    @classmethod
    def BOTTOM(cls) -> AlignmentAttr:  # noqa: N802
        """The last op in each region ends at the same time."""
        return cls(_AlignmentEnum.BOTTOM)

    @staticmethod
    def coerce(alignment: AlignmentAttr | Literal["TOP", "BOTTOM"]) -> AlignmentAttr:
        """Ensures the argument is returned as a AlignmentAttr."""
        if isinstance(alignment, AlignmentAttr):
            return alignment
        return AlignmentAttr(alignment)


# endregion

# region Operation definitions


@irdl_op_definition
class YieldOp(AbstractYieldOperation[Attribute]):
    """Yield SSAValues from the scope of one region to its containing region."""

    name = "qstruct.yield"

    traits = lazy_traits_def(
        lambda: (
            IsTerminator(),
            HasParent(ParallelOp, CircuitOp, RepeatOp),
            Pure(),
            NoQuantumEffect(),
        )
    )


class _CircuitOpHasCanonicalizationPatternsTrait(HasCanonicalizationPatternsTrait):
    @override
    @classmethod
    def get_canonicalization_patterns(cls) -> tuple[RewritePattern, ...]:
        from deltakit_compile.passes.canonicalisation.qstruct import (  # noqa: PLC0415
            InlineClassicalCircuit,
            RemoveUnusedCircuitArgs,
            RemoveUnusedResults,
        )  # Imported here to avoid circular imports.

        return (InlineClassicalCircuit(), RemoveUnusedCircuitArgs(), RemoveUnusedResults())


@irdl_op_definition
class CircuitOp(IRDLOperation):
    """A container for physical circuit ops, allowing the effect of the circuit elements of a
    program to be constrained and managed in chunks.

    The qubits it operates on are declared globally and passed in as arguments. Any qubit passed
    into a circuit must be yielded out - it is treated as SSA coming out of the circuit, regardless
    of if the ops inside the circuit are qref."""

    name = "qstruct.circuit"

    _NUM_QUBITS: ClassVar[RangeConstraint] = SumOver(
        RangeOf(AnyAttr()), qubit_count, IntVarConstraint("Qubits", AnyInt())
    )
    """Constrains ranges of types to have the same total number of qubits."""
    _ARGS: ClassVar[RangeConstraint] = RangeVarConstraint("Arguments", _NUM_QUBITS)
    """Variable constraint to ensure the exact same types are used, and also the total number of
    qubits matches uses other uses of _NUM_QUBITS. """

    args = var_operand_def(_ARGS)
    res = var_result_def(_NUM_QUBITS)
    body = region_def("single_block", entry_args=_ARGS)

    traits = traits_def(
        IsCircuit(),
        SingleBlockImplicitTerminator(YieldOp),
        RecursiveQuantumEffect(),
        RecursiveMemoryEffect(),
        IsolatedFromAbove(),
        _CircuitOpHasCanonicalizationPatternsTrait(),
    )

    assembly_format = " (`(` $args^ `:` type($args) `)`)? attr-dict `->` type($res) $body"

    def __init__(
        self,
        arguments: Sequence[SSAValue],
        result_types: Sequence[Attribute],
        body: Region | Sequence[Operation] | Sequence[Block],
    ) -> None:
        if isinstance(body, Sequence) and all(isinstance(op, Operation) for op in body):
            body = cast(Sequence[Operation], body)
            body = Region(Block(ops=body, arg_types=[arg.type for arg in arguments]))
        super().__init__(
            operands=[arguments],
            result_types=[result_types],
            regions=[body],
        )

    @override
    def verify_(self) -> None:
        """Verify the circuit body's yield op has the same operand types as the circuit results."""
        yielded_types = self.yield_op.operand_types
        if len(yielded_types) != len(self.result_types):
            msg = (
                f"The number of variables yielded from the circuit ({len(yielded_types)})"
                " doesn't match the number of variables the circuit op returns "
                f"({len(self.result_types)})"
            )
            raise VerifyException(msg)
        for yielded_type, result_type in zip(yielded_types, self.result_types, strict=True):
            if yielded_type != result_type:
                msg = (
                    f"The type of variable yielded from the circuit ({yielded_type}) doesn't "
                    "match the type of the corresponding variable the circuit op returns "
                    f"({result_type})"
                )
                raise VerifyException(msg)

    @property
    def yield_op(self) -> YieldOp:
        """Get this circuit's yield op."""
        # Safe cast as yield's presence is verified by SingleBlockImplicitTerminator
        return cast(YieldOp, self.body.block.last_op)

    @property
    def num_qubits(self) -> int:
        """The number of qubits this circuit operates on."""
        return sum(qubit_count(arg.type) for arg in self.args)

    def operand_for_block_arg(self, arg: SSAValue[AttributeInvT]) -> SSAValue[AttributeInvT]:
        """Return the operand that corresponds to the given block argument of this circuit's
        body."""
        if not isinstance(arg, BlockArgument) or arg.owner.parent_op() != self:
            msg = (
                f"Cannot get {self.name} operand for value {arg}: "
                "SSAValue is not a block argument of this circuit's body."
            )
            raise ValueError(msg)
        # Casting assumes self verifies which checks these types match up correctly.
        return cast(SSAValue[AttributeInvT], self.args[arg.index])


class _RepeatOpHasCanonicalizationPatternsTrait(HasCanonicalizationPatternsTrait):
    @override
    @classmethod
    def get_canonicalization_patterns(cls) -> tuple[RewritePattern, ...]:
        from deltakit_compile.passes.canonicalisation.qstruct import (  # noqa: PLC0415
            RehoistConstInRepeat,
            SimplifyTrivialRepeat,
        )  # Imported here to avoid circular imports.

        return (RehoistConstInRepeat(), SimplifyTrivialRepeat())


@irdl_op_definition
class RepeatOp(IRDLOperation):
    """A loop where the number of repetitions is known at compile time (making it usable inside
    qstruct.circuit)."""

    name = "qstruct.repeat"

    repetitions = prop_def(IntAttr.constr(AtLeast(1)))
    iter_args = var_operand_def()
    res = var_result_def()

    body = region_def("single_block")

    traits = traits_def(
        SingleBlockImplicitTerminator(YieldOp),
        _RepeatOpHasCanonicalizationPatternsTrait(),
        RecursiveMemoryEffect(),
        RecursiveQuantumEffect(),
    )

    assembly_format = (
        f"`<` {PlainIntAttr.use('$repetitions')} `>` `(`($iter_args^ `:` type($iter_args))?`)` "
        "attr-dict `->` type($res) $body"
    )

    custom_directives = (PlainIntAttr,)

    def __init__(
        self,
        repetitions: int | IntAttr,
        body: Region | Sequence[Block] | Block,
        iter_args: Sequence[SSAValue] = (),
    ):
        super().__init__(
            operands=[iter_args],
            result_types=[[SSAValue.get(a).type for a in iter_args]],
            regions=[[body]] if isinstance(body, Block) else [body],
            properties={"repetitions": IntAttr.get(repetitions)},
        )

    @override
    def verify_(self) -> None:
        """Verify the repeat body's yield op has the same operand types as the repeat's results."""
        yielded_types = self.yield_op.operand_types
        if (
            len(self.iter_args) != len(self.body.block.args)
            or len(self.body.block.args) != len(yielded_types)
            or len(yielded_types) != len(self.res)
        ):
            msg = (
                f"The number of iter_args ({len(self.iter_args)}), "
                f"the number of block arguments in the repeat body ({len(self.body.block.args)}), "
                f"the number of values yielded from the repeat body ({len(yielded_types)}), and "
                f"the number of results returned ({len(self.res)}) must all match."
            )
            raise VerifyException(msg)

        for iter_arg, block_arg, yielded_type, result_value in zip(
            self.iter_args, self.body.block.args, yielded_types, self.res, strict=True
        ):
            if (
                iter_arg.type != block_arg.type
                or block_arg.type != yielded_type
                or yielded_type != result_value.type
            ):
                msg = (
                    f"The iter arg type {iter_arg.type}, "
                    f"block arg type {block_arg.type}, "
                    f"yielded value type {yielded_type}, and "
                    f"result type {result_value.type} must all match."
                )
                raise VerifyException(msg)

    @property
    def yield_op(self) -> YieldOp:
        """Get this repeat's yield op."""
        # Safe cast as yield's presence is verified by SingleBlockImplicitTerminator
        return cast(YieldOp, self.body.block.last_op)


class _ParallelOpHasCanonicalizationPatternsTrait(HasCanonicalizationPatternsTrait):
    @override
    @classmethod
    def get_canonicalization_patterns(cls) -> tuple[RewritePattern, ...]:
        from deltakit_compile.passes.canonicalisation.qstruct import (  # noqa: PLC0415
            HoistPureOpsFromParallel,
            RemovePureParallel,
            RemoveUnnecessaryParallel,
            RemoveUnusedResults,
            RemoveUseOfParallelResults,
        )  # Imported here to avoid circular imports.

        return (
            RemoveUseOfParallelResults(),
            RemoveUnusedResults(),
            RemoveUnnecessaryParallel(),
            RemovePureParallel(),
            HoistPureOpsFromParallel(),
        )


@irdl_op_definition
class ParallelOp(IRDLOperation):
    """Define regions that execute in parallel."""

    name = "qstruct.parallel"

    alignment = prop_def(AlignmentAttr)
    res = var_result_def()  # Passing SSAValues from within nested regions to their enclosing scope
    par_regions = var_region_def("single_block")

    traits = traits_def(
        SingleBlockImplicitTerminator(YieldOp),
        RecursiveQuantumEffect(),
        RecursiveMemoryEffect(),
        _ParallelOpHasCanonicalizationPatternsTrait(),
    )

    assembly_format = (
        f"`<` {AlignmentAttr.plain_directive('$alignment')} `>` "
        "attr-dict `->` type($res) $par_regions"
    )
    custom_directives = (AlignmentAttr.plain_directive(),)

    def __init__(
        self,
        result_types: Sequence[Attribute],
        par_regions: Sequence[Block | Region],
        alignment: AlignmentAttr | Literal["TOP", "BOTTOM"] = "TOP",
    ):
        super().__init__(
            result_types=[result_types],
            regions=[[Region(r) if isinstance(r, Block) else r for r in par_regions]],
            properties={"alignment": AlignmentAttr.coerce(alignment)},
        )

    def _get_yielded_values(self) -> list[SSAValue]:
        """Get the SSAValues yielded from all regions."""
        return list(
            itertools.chain.from_iterable(
                yield_op.operands
                for region in self.regions
                if isinstance(yield_op := region.block.last_op, YieldOp)
            )
        )

    def yield_arg_to_result(self, yield_arg: SSAValue[AttributeCovT]) -> OpResult[AttributeCovT]:
        """Get the result SSAValue that corresponds to the given yield op argument."""
        yielded_values = self._get_yielded_values()
        try:
            index = yielded_values.index(yield_arg)
        except ValueError:
            msg = f"{yield_arg} is not yielded from any region of this ParallelOp."
            raise ValueError(msg) from None

        return cast(OpResult[AttributeCovT], self.res[index])

    def result_to_yield_arg(self, result: SSAValue[AttributeCovT]) -> SSAValue[AttributeCovT]:
        """Get the yield op argument that corresponds to the given result SSAValue."""
        try:
            index = self.res.index(result)
        except ValueError:
            msg = f"{result} is not a result of this ParallelOp."
            raise ValueError(msg) from None

        yielded_values = self._get_yielded_values()
        return cast(SSAValue[AttributeCovT], yielded_values[index])

    @override
    def verify_(self) -> None:
        """Verify that the yielded SSAValues at the end of the regions match the SSAValues returned
        by the op and that qubits are not shared by the parallel regions."""
        yielded_values = self._get_yielded_values()

        if len(yielded_values) != len(self.res):
            msg = (
                f"The number of variables yielded from the parallel regions ({len(yielded_values)})"
                " doesn't match the number returned from the parallel op containing them "
                f"({len(self.res)})"
            )
            raise VerifyException(msg)
        for yielded_value, result_value in zip(yielded_values, self.res, strict=False):
            if yielded_value.type != result_value.type:
                msg = (
                    f"Type of variable yielded from parallel region ({yielded_value.type}) doesn't "
                    "match the type of the corresponding variable returned from the parallel op "
                    f"containing said region ({result_value.type})"
                )
                raise VerifyException(msg)

        # We want to know if any qubit SSAs operated on in one region are also operated on in
        # another region, so get all qubit SSA operands across all regions. Note that this won't
        # work if the IR uses old SSAs with new SSAs for the same qubit.
        qubit_ssas_per_region = [
            {
                operand
                for op in region.walk()
                for operand in op.operands
                if isinstance(operand.type, (QubitType, QubitRegType))
            }
            for region in self.par_regions
        ]
        for (a_idx, ssa_set_a), (b_idx, ssa_set_b) in itertools.combinations(
            enumerate(qubit_ssas_per_region), r=2
        ):
            overlap = ssa_set_a & ssa_set_b
            if overlap:
                msg = (
                    f"Regions {a_idx} and {b_idx} in the same parallel use the same qubits: "
                    f"{overlap}"
                )
                raise VerifyException(msg)


def make_parallel_from_ops(ops: Sequence[Operation]) -> ParallelOp:
    """
    Helper that takes a list of operations and makes them into a single parallel op.
    """
    regions: list[Region] = []
    result_types: list[Attribute] = []
    for inner_op in ops:
        # Collect results from the op; for ops without results this will be empty
        # Accumulate result types in parallel op order
        result_types.extend(inner_op.result_types)
        regions.append(Region(Block([inner_op, YieldOp(*inner_op.results)])))
    return ParallelOp(result_types=result_types, par_regions=regions)


@irdl_op_definition
class OutputOp(IRDLOperation):
    """Mark SSAValues as being outputs of the program."""

    name = "qstruct.output"

    _INT_ARGS: ClassVar[AttrConstraint] = base(IntegerType) | base(IndexType)

    arguments = var_operand_def(TensorType.constr(element_type=_INT_ARGS) | _INT_ARGS)

    traits = traits_def(HasSideEffects())

    assembly_format = "`(` operands `:` type(operands) `)` attr-dict"

    def __init__(self, arguments: Sequence[SSAValue]) -> None:
        super().__init__(operands=[arguments])


# endregion

QStruct = Dialect("qstruct", [CircuitOp, ParallelOp, RepeatOp, YieldOp, OutputOp], [AlignmentAttr])
