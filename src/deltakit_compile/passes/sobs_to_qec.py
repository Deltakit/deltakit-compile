# (c) Copyright Riverlane 2025-2026. All rights reserved.

"""Lowering ``sobs`` operations to ``qec`` operations."""

import itertools
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import TypeAlias, cast

from typing_extensions import override
from xdsl.dialects import builtin
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Attribute, Operation, OpResult, SSAValue, Use
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    GreedyRewritePatternApplier,
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    TypeConversionPattern,
    attr_type_rewrite_pattern,
    op_type_rewrite_pattern,
)
from xdsl.rewriter import InsertPoint
from xdsl.transforms.reconcile_unrealized_casts import ReconcileUnrealizedCastsPattern

from deltakit_compile.dialects import qec, qref, qstruct, sobs
from deltakit_compile.dialects.qcore import HasCircuitAncestor, QubitType
from deltakit_compile.dialects.sobs import ObservableType
from deltakit_compile.exceptions import CompilerPassCheckError
from deltakit_compile.utilities.ssa_scoping import make_ssa_value_available_at
from deltakit_compile.utilities.traverse_from_ssa import (
    find_equivalent_qubit_ssas,
    find_forward_ssas,
)


def _operation_path(operation: Operation) -> tuple[int, ...]:
    """Return a lexicographically comparable path from the module to an operation.

    Each entry of the returned path corresponds to the index of an ancestor of ``operation`` in its
    block. ``ret[0]`` corresponds to the index of the oldest ancestor of ``operation`` before the
    ``ModuleOp``. ``ret[-1]`` corresponds to the index of ``operation`` in its block.
    """
    path: list[int] = []
    current = operation
    while (block := current.parent_block()) is not None:
        path.append(block.get_operation_index(current))
        parent = block.parent_op()
        if parent is None:
            break
        current = parent
    return tuple(reversed(path))


def _is_operation_strictly_between(
    operation: Operation, lower_bound: Operation, upper_bound: Operation
) -> bool:
    """Return whether ``operation`` occurs strictly between two structural operations."""
    return _operation_path(lower_bound) < _operation_path(operation) < _operation_path(upper_bound)


def _measurement_index(measurement: qref.MeasureOp, qubit_index: int) -> int:
    """Return the result index corresponding to a flattened qubit operand.

    Note that ``MeasureOp`` might measure multi-pauli observables (e.g., ``XX``), which means that
    the number of returned ``i1`` does not necessarily corresponds to the number of qubit operands,
    and is the reason why this function is not a simple identity returning ``qubit_index``.

    Args:
        measurement: measurement operation for which we want to find the ``i1`` result
            corresponding to the provided ``qubit_index``.
        qubit_index: index of the qubit that is being measured.

    Returns:
        The result index corresponding to the ``i1`` returned after measuring ``qubit_index``.
    """
    offset = 0
    for result_index, paulis in enumerate(measurement.paulis.data):
        if qubit_index < offset + len(paulis.data):
            return result_index
        offset += len(paulis.data)
    msg = "Could not find the measurement result corresponding to a measured qubit."
    raise CompilerPassCheckError(msg)


def _measurements_between(
    support: set[SSAValue], lower_bound: Operation, upper_bound: Operation
) -> list[OpResult]:
    """Find first measurements of qubit SSAs in ``support`` between ``lower_bound`` and
    ``upper_bound``.

    Args:
        support: a set SSA values representing the qubits on which the observable is currently
            supported.
        lower_bound: the operation that changed the observable support to ``support``.
        upper_bound: the operation after ``lower_bound`` that changed the observable support to
            something different from ``support``.

    Returns:
        All the SSAs corresponding to ``i1`` obtained from the first measurement applied on a qubit
        in ``support`` appearing after ``lower_bound`` but before ``upper_bound``.
    """
    measurements = list[OpResult]()
    for qubit in support:
        _, blocking_uses, _ = find_equivalent_qubit_ssas(cast(SSAValue[QubitType], qubit))
        candidates = [
            use
            for use in blocking_uses
            if (
                isinstance(measure_op := use.operation, qref.MeasureOp)
                and _is_operation_strictly_between(measure_op, lower_bound, upper_bound)
            )
        ]
        if not candidates:
            continue
        # In case of multiple measurements, take the first one.
        candidate = min(candidates, key=lambda use: _operation_path(use.operation))
        measurement = candidate.operation
        assert isinstance(measurement, qref.MeasureOp)
        result_index = _measurement_index(measurement, candidate.index)
        result = measurement.measurements[result_index]
        if result not in measurements:
            measurements.append(result)

    return measurements


def _next_observable_uses(value: OpResult[ObservableType]) -> list[Operation]:
    """Find the unique non-structural operation using an observable value."""
    _, blocking_uses = find_forward_ssas(value)
    return [blocking_use.operation for blocking_use in blocking_uses]


_OBSERVABLE_TERMINAL_USE_TYPES: TypeAlias = (
    qec.GetCorrectedOp | qec.GetCorrectionOp | qec.GetUncorrectedOp | qec.IsCorrectionReadyOp
)
_OBSERVABLE_SOBS_OP_TYPES: TypeAlias = sobs.DecObservableOp | sobs.MoveObservableOp
_OBSERVABLE_CHAIN_PAIRWISE_ITERABLE: TypeAlias = Iterable[
    tuple[_OBSERVABLE_SOBS_OP_TYPES, sobs.MoveObservableOp | _OBSERVABLE_TERMINAL_USE_TYPES]
]


@dataclass(frozen=True)
class _ObservableOperationChain:
    """Store a chain of operations on a ``sobs.observable``.

    This data-class ensures that the chain of operation stored checks all the following invariants:
    - The chain contains at least 2 operations.
    - The first entry is an instance of ``sobs.DecObservableOp``.
    - The last entry is an instance of ``qec.GetCorrectedOp``, ``qec.GetCorrectionOp``,
      ``qec.GetUncorrectedOp`` or ``qec.IsCorrectionReadyOp``.
    - All the other entries are instances of ``sobs.MoveObservableOp``.
    """

    operations: list[_OBSERVABLE_SOBS_OP_TYPES]
    terminals: list[_OBSERVABLE_TERMINAL_USE_TYPES]

    def __post_init__(self) -> None:
        assert len(self.operations) >= 1
        assert isinstance(self.operations[0], sobs.DecObservableOp)
        assert all(isinstance(op, sobs.MoveObservableOp) for op in self.operations[1:])
        assert len(self.terminals) >= 1
        assert all(isinstance(op, _OBSERVABLE_TERMINAL_USE_TYPES) for op in self.terminals)
        assert sorted(self.terminals, key=_operation_path) == self.terminals

    def pairwise_iterable(self) -> _OBSERVABLE_CHAIN_PAIRWISE_ITERABLE:
        # Cast is checked by __post_init__.
        return cast(
            _OBSERVABLE_CHAIN_PAIRWISE_ITERABLE,
            itertools.pairwise([*self.operations, self.terminals[0]]),
        )

    @property
    def terminal_ops(self) -> list[_OBSERVABLE_TERMINAL_USE_TYPES]:
        return self.terminals

    @property
    def first_terminal_op(self) -> _OBSERVABLE_TERMINAL_USE_TYPES:
        return self.terminals[0]


def _get_chain_of_operations_on_observable_starting_with(
    op: sobs.DecObservableOp,
) -> _ObservableOperationChain:
    current: _OBSERVABLE_SOBS_OP_TYPES = op
    chain: list[_OBSERVABLE_SOBS_OP_TYPES] = [current]
    terminals: list[_OBSERVABLE_TERMINAL_USE_TYPES]
    while True:
        upper_bounds = _next_observable_uses(current.result)
        # Here ``upper_bounds`` should be either:
        # - a single ``sobs.move_observable`` operation or,
        # - an arbitrary number of ``_OBSERVABLE_TERMINAL_USE_TYPES`` operations.
        if len(upper_bounds) == 1 and isinstance(
            upper_bound := upper_bounds[0], (sobs.DecObservableOp, sobs.MoveObservableOp)
        ):
            chain.append(upper_bound)
            current = upper_bound
        elif all(isinstance(ub, _OBSERVABLE_TERMINAL_USE_TYPES) for ub in upper_bounds):
            terminals = cast(
                list[_OBSERVABLE_TERMINAL_USE_TYPES], sorted(upper_bounds, key=_operation_path)
            )
            break
        else:
            msg = (
                f"Expected an observable chain to be a chain of {sobs.MoveObservableOp.name} "
                "operations ended by an arbitrary number of terminal operations, but found "
                f"{upper_bounds} while exploring."
            )
            raise RuntimeError(msg)
    return _ObservableOperationChain(chain, terminals)


@dataclass
class _LowerObservableChain(RewritePattern):
    """Lower one linear placed-observable chain and its support measurements."""

    @staticmethod
    def _replace_sobs_operation_with_qec(
        op: _OBSERVABLE_SOBS_OP_TYPES, rewriter: PatternRewriter
    ) -> None:
        """Replace ``op`` with the appropriate ``qec`` operation (and casts around it)."""
        # Early check: if ``op`` is a ``sobs.move_observable`` without any measurement, just remove
        # it and return.
        if isinstance(op, sobs.MoveObservableOp) and not op.measurements:
            rewriter.replace_all_uses_with(op.result, op.obs)
            rewriter.erase_op(op)
            return

        new_operations: tuple[Operation, ...]
        if isinstance(op, sobs.DecObservableOp):
            qec_declaration_op = qec.DecObservableOp()
            cast_qec_to_sobs, sobs_observable = builtin.UnrealizedConversionCastOp.cast_one(
                qec_declaration_op.result, sobs.ObservableType()
            )
            new_operations = (qec_declaration_op, cast_qec_to_sobs)
        else:
            assert isinstance(op, sobs.MoveObservableOp), "Invariant of _ObservableOperationChain"
            cast_sobs_to_qec, qec_observable = builtin.UnrealizedConversionCastOp.cast_one(
                op.obs, qec.ObservableType()
            )
            include_op = qec.ObservableIncludeOp(qec_observable, op.measurements)
            cast_qec_to_sobs, sobs_observable = builtin.UnrealizedConversionCastOp.cast_one(
                include_op.out_obs, sobs.ObservableType()
            )
            new_operations = (cast_sobs_to_qec, include_op, cast_qec_to_sobs)
        rewriter.replace_op(op, new_operations, (sobs_observable,))

    @staticmethod
    def add_measurements_to_observable(
        measurements_ssas: Sequence[SSAValue],
        next_observable_use: sobs.MoveObservableOp | _OBSERVABLE_TERMINAL_USE_TYPES,
        rewriter: PatternRewriter,
    ) -> None:
        """Inserts a ``qec.observable_include`` with the provided ``measurements_ssas`` before
        ``next_observable_use`` if ``measurements_ssas`` is not empty.

        This method will first ensure that all the measurements SSAs provided in
        ``measurements_ssas`` are reachable by ``next_observable_use``. If not, it will change
        structural operations to ensure that we can use the SSAs in an operation inserted just
        before ``next_observable_use``. Then, it will insert the ``qec.observable_include``
        operation just before ``next_observable_use``.
        """
        if not measurements_ssas:
            return
        # sobs -> qec
        cast_sobs_to_qec, qec_observable = builtin.UnrealizedConversionCastOp.cast_one(
            next_observable_use.obs, qec.ObservableType()
        )
        rewriter.insert_op(cast_sobs_to_qec, InsertPoint.before(next_observable_use))
        # Main operations, enclosed in circuit if ``next_observable_use`` is not already.
        main_operation: Operation
        if HasCircuitAncestor.has_circuit_ancestor(next_observable_use):
            main_operation = qec.ObservableIncludeOp(qec_observable, measurements_ssas)
        else:
            # Enclose in a circuit
            main_operation = qstruct.CircuitOp(
                [qec_observable, *measurements_ssas], [qec.ObservableType()], []
            )
            block_args = main_operation.body.block.args
            include_op = qec.ObservableIncludeOp(block_args[0], block_args[1:])
            main_operation.body.block.add_op(include_op)
            main_operation.body.block.add_op(qstruct.YieldOp(include_op.out_obs))
        rewriter.insert_op(main_operation, InsertPoint.after(cast_sobs_to_qec))
        out_observable = cast(OpResult[qec.ObservableType], main_operation.results[0])
        # qec -> sobs
        cast_qec_to_sobs, new_observable = builtin.UnrealizedConversionCastOp.cast_one(
            out_observable, sobs.ObservableType()
        )
        rewriter.insert_op(cast_qec_to_sobs, InsertPoint.after(main_operation))

        # Note that the below function uses ``next_observable_use``, which is a loop variable. To
        # avoid linting errors, we explicitly bind insert_before to the function here.
        def _is_insert_before(use: Use, insert_before=next_observable_use) -> bool:
            return use.operation is insert_before

        rewriter.replace_uses_with_if(next_observable_use.obs, new_observable, _is_insert_before)

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: sobs.DecObservableOp, rewriter: PatternRewriter) -> None:
        # Recover the chain of operations the observable go through.
        chain = _get_chain_of_operations_on_observable_starting_with(op)

        # Then, for each pair of consecutive operation on the observable, extract the current
        # support of the observable, find measurements on that support between two consecutive
        # operations on the observable, and add these measurements to the ``qec`` observable with a
        # ``qec.observable_include`` operation if any. At the same time, replace ``lower_bound``
        # with the correct operation.
        for lower_bound, upper_bound in chain.pairwise_iterable():
            # Get the measurements, potentially rewriting some operations to make sure those
            # measurement SSAs are in the scope of ``upper_bound``.
            current_support = set(lower_bound.qubits)
            measurements = _measurements_between(current_support, lower_bound, upper_bound)
            measurements_ssas = [
                make_ssa_value_available_at(measurement, upper_bound, rewriter)
                for measurement in measurements
            ]

            # Handle the sobs operation: replace it with a ``qec.dec_observable``, with the
            # appropriate casts to avoid changing any else outside of ``lower_bound``.
            _LowerObservableChain._replace_sobs_operation_with_qec(lower_bound, rewriter)

            # If any qubit on the support has been measured before setting a new support, add those
            # measurements to the observable too. The measurements are added to the observable just
            # before ``upper_bound`` for the moment.
            if measurements_ssas:
                self.add_measurements_to_observable(measurements_ssas, upper_bound, rewriter)

        # Finally, because we want everything to use the ``qec`` dialect, we change the type of the
        # observable that is given to the terminal operation.
        for terminal_op in chain.terminal_ops:

            def _is_terminal_op(
                use: Use, terminal_op: _OBSERVABLE_TERMINAL_USE_TYPES = terminal_op
            ) -> bool:
                return use.operation is terminal_op

            sobs_observable_ssa = terminal_op.obs
            cast_op, qec_observable_ssa = builtin.UnrealizedConversionCastOp.cast_one(
                sobs_observable_ssa, qec.ObservableType()
            )
            rewriter.insert_op(cast_op, InsertPoint.before(terminal_op))
            rewriter.replace_uses_with_if(sobs_observable_ssa, qec_observable_ssa, _is_terminal_op)


class ConvertObservableTypesPattern(TypeConversionPattern):
    """Convert all sobs observable types to qec observable types."""

    @override
    @attr_type_rewrite_pattern
    def convert_type(self, typ: sobs.ObservableType) -> Attribute:
        return qec.ObservableType()


@dataclass(frozen=True)
class SobsObservableToQec(ModulePass):
    """Lower placed ``sobs`` observables to ``qec`` observable operations."""

    name = "sobs-observable-to-qec"

    @override
    def apply(self, ctx, op: ModuleOp) -> None:
        PatternRewriteWalker(_LowerObservableChain()).rewrite_module(op)
        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [ReconcileUnrealizedCastsPattern(), ConvertObservableTypesPattern()]
            )
        ).rewrite_module(op)
