import re
from collections.abc import Sequence
from io import StringIO

import pytest
import xdsl.dialects.test as t
from xdsl.context import Context
from xdsl.dialects.builtin import IntegerType
from xdsl.ir import Attribute, Block, Operation, VerifyException
from xdsl.irdl import EqIntConstraint
from xdsl.irdl.constraints import ConstraintContext
from xdsl.printer import Printer

from deltakit_compile.dialects.plaquette import (
    Plaquette,
    PlaquetteOp,
    RoundOp,
    StabiliserMeasurementMethodConstraint,
    SubCircuitOp,
    SynchronisedScheduleAttr,
    YieldOp,
)
from deltakit_compile.dialects.qcore import PauliStringAttr, QubitRegType, QubitType


def _block_yielding_n_measurements(
    result_types: int | Sequence[Attribute], num_qubits: int = 1, include_args: bool = True
) -> Block:
    if isinstance(result_types, int):
        result_types = [IntegerType(1) for _ in range(result_types)]
    test_op = t.TestOp(result_types=result_types)
    return Block(
        [test_op, YieldOp(*test_op.results)],
        arg_types=[QubitType() for _ in range(num_qubits)] if include_args else [],
    )


def _encapsulate_in_round_op(op: Operation, num_qubits: int = 1) -> RoundOp:
    qubits_type = [QubitType() for _ in range(num_qubits)]
    qubits = t.TestOp(result_types=qubits_type).results
    return RoundOp(
        qubits, [Block([op, YieldOp(*op.results)], arg_types=qubits_type)], len(op.results)
    )


class TestYieldOp:
    def test_must_be_in_round_op(self) -> None:
        containing_op = t.TestOp(regions=[[Block([YieldOp()])]])
        msg = re.escape(
            "'plaquette.yield' expects parent op to be one of "
            "'plaquette.round', 'plaquette.sub_circuit'"
        )
        with pytest.raises(VerifyException, match=msg):
            containing_op.verify()


class TestRoundOp:
    def test_must_be_in_circuit_op(self) -> None:
        qubits_producer_op = t.TestOp(result_types=[QubitType()])
        block = Block(
            [
                qubits_producer_op,
                RoundOp(qubits_producer_op.results, [], 0),
                t.TestTermOp(),
            ]
        )
        containing_op = t.TestOp(regions=[[block]])
        with pytest.raises(
            VerifyException,
            match=re.escape("Op must be inside a circuit (an op with the IsCircuit trait)."),
        ):
            containing_op.verify()

    @pytest.mark.parametrize(("num_qubits", "num_regions"), [(1, 0), (1, 1), (10, 3)])
    def test_empty(self, num_qubits: int, num_regions: int) -> None:
        qubits_type = [QubitType() for _ in range(num_qubits)]
        qubits = t.TestOp(result_types=qubits_type).results
        op = RoundOp(
            qubits,
            [Block([YieldOp()], arg_types=qubits_type) for _ in range(num_regions)],
            measurements=0,
        )
        op.verify()

    def test_no_qubit_fails(self) -> None:
        op = RoundOp([], [], 0)
        with pytest.raises(VerifyException, match="incorrect length for range variable"):
            op.verify()

    @pytest.mark.parametrize(
        ("num_qubits", "blocks", "expected_message"),
        [
            (
                1,
                [Block([YieldOp()], arg_types=[])],
                re.escape("integer 1 expected from int variable 'Qubits', but got 0"),
            ),
            (
                3,
                [Block([YieldOp()], arg_types=[QubitType(), QubitType()])],
                re.escape("integer 3 expected from int variable 'Qubits', but got 2"),
            ),
            (
                1,
                [Block([YieldOp()], arg_types=[QubitRegType(1)])],
                re.escape("Expected attribute !qcore.qubit but got !qcore.qubit_reg<1>"),
            ),
            (
                1,
                [
                    Block([YieldOp()], arg_types=[QubitType()]),
                    Block([YieldOp()], arg_types=[QubitRegType(1), QubitType()]),
                ],
                re.escape("integer 1 expected from int variable 'Qubits', but got 2"),
            ),
        ],
    )
    def test_block_with_wrong_entry_args_fails(
        self, num_qubits: int, blocks: Sequence[Block], expected_message: str
    ) -> None:
        qubits = t.TestOp(result_types=[QubitType() for _ in range(num_qubits)]).results
        op = RoundOp(qubits, blocks, 0)
        with pytest.raises(VerifyException, match=expected_message):
            op.verify()

    def test_negative_number_measurements_fails(self) -> None:
        with pytest.raises(
            RuntimeError, match=re.escape("Cannot have a negative number of measurements. Got -1.")
        ):
            _ = RoundOp([], [], -1)

    @pytest.mark.parametrize(
        ("num_measurements", "blocks", "expected_message"),
        [
            (1, [_block_yielding_n_measurements(1)], None),
            (6, [_block_yielding_n_measurements(6)], None),
            (6, [_block_yielding_n_measurements(3), _block_yielding_n_measurements(3)], None),
            (
                6,
                [
                    _block_yielding_n_measurements(3),
                    _block_yielding_n_measurements(0),
                    _block_yielding_n_measurements(3),
                ],
                None,
            ),
            (
                0,
                [
                    _block_yielding_n_measurements(0),
                    _block_yielding_n_measurements(0),
                    _block_yielding_n_measurements(0),
                ],
                None,
            ),
            (
                1,
                [_block_yielding_n_measurements(1), _block_yielding_n_measurements(1)],
                re.escape(
                    "The number of variables yielded from the parallel regions (2) doesn't match "
                    "the number returned from the round op containing them"
                ),
            ),
            (
                10,
                [_block_yielding_n_measurements(9), _block_yielding_n_measurements(0)],
                re.escape(
                    "The number of variables yielded from the parallel regions (9) doesn't match "
                    "the number returned from the round op containing them"
                ),
            ),
            (
                1,
                [_block_yielding_n_measurements([IntegerType(2)])],
                re.escape(
                    "Type of variable yielded from parallel region (i2) doesn't match the type of "
                    "the corresponding variable returned from the round op containing said region "
                    "(i1)"
                ),
            ),
        ],
    )
    def test_returned_measurements(
        self, num_measurements: int, blocks: Sequence[Block], expected_message: str | None
    ) -> None:
        qubits = t.TestOp(result_types=[QubitType()])
        op = RoundOp(qubits.results, blocks, num_measurements)
        if expected_message is not None:
            with pytest.raises(VerifyException, match=expected_message):
                op.verify()
        else:
            op.verify()


class TestPlaquetteOp:
    def test_must_be_in_round_op(self) -> None:
        qubits = t.TestOp(result_types=[QubitType()]).results
        op = PlaquetteOp(qubits, [PauliStringAttr([("X", 0)], 1)], 1)
        containing_op = t.TestOp(regions=[[Block([op, t.TestTermOp()])]])
        with pytest.raises(
            VerifyException, match=re.escape("Op must be inside a plaquette.round operation.")
        ):
            containing_op.verify()

    def test_negative_number_measurements_fails(self) -> None:
        qubits = t.TestOp(result_types=[QubitType()]).results
        with pytest.raises(
            RuntimeError, match=re.escape("Cannot have a negative number of measurements. Got -1.")
        ):
            _ = PlaquetteOp(qubits, [PauliStringAttr([("X", 0)], 1)], -1)

    def test_no_data_qubits_fails(self) -> None:
        op = PlaquetteOp([], [], 1)
        with pytest.raises(
            VerifyException,
            match=re.escape("operand 'data_qubits' expected at position 0 does not verify"),
        ):
            op.verify()

    def test_no_stabiliser_fails(self) -> None:
        qubits = t.TestOp(result_types=[QubitType()]).results
        op = PlaquetteOp(qubits, [], 1)
        with pytest.raises(VerifyException, match=re.escape("incorrect length for range variable")):
            op.verify()

    @pytest.mark.parametrize(("num_qubits", "stab_length"), [(1, 2), (2, 1), (10, 11), (1, 4)])
    def test_wrong_stabiliser_length_fails(self, num_qubits: int, stab_length: int) -> None:
        qubits = t.TestOp(result_types=[QubitType() for _ in range(num_qubits)]).results
        op = PlaquetteOp(qubits, [PauliStringAttr([("X", 0)], stab_length)], 1)
        with pytest.raises(
            VerifyException,
            match=re.escape(
                f"integer {num_qubits} expected from int variable 'DataQubits', but "
                f"got {stab_length}"
            ),
        ):
            op.verify()

    def test_shared_qubits_fails(self) -> None:
        qubits = t.TestOp(result_types=[QubitType()]).results
        op = PlaquetteOp(qubits, [PauliStringAttr([("X", 0)], 1)], 1, ancilla_qubits=qubits)
        msg = re.escape(
            "Found 1 qubits that were provided more than once to a plaquette.plaquette operation."
        )
        with pytest.raises(VerifyException, match=msg):
            op.verify()

    @pytest.mark.parametrize(("num_measurements", "num_stabilisers"), [(1, 2), (10, 11), (1, 4)])
    def test_less_measurements_than_stabilisers_fails(
        self, num_measurements: int, num_stabilisers: int
    ) -> None:
        qubits = t.TestOp(result_types=[QubitType()]).results
        op = PlaquetteOp(
            qubits,
            [PauliStringAttr([("X", 0)], 1) for _ in range(num_stabilisers)],
            num_measurements,
        )
        with pytest.raises(
            VerifyException,
            match=re.escape(
                "Expected at least one measurement result per stabiliser but got "
                f"{num_measurements} measurements and {num_stabilisers} stabilisers."
            ),
        ):
            op.verify()

    @pytest.mark.parametrize(
        ("num_data_qubits", "num_stabilisers", "schedule", "expected_error"),
        [
            (2, 1, [1, 2], None),
            (2, 2, [1, 2], "integer 2 expected from int variable 'Measurements', but got 1"),
            # Number of entries in schedule does not match number of data-qubits
            (2, 1, [1], "integer 2 expected from int variable 'DataQubits', but got 1"),
            (2, 1, [1, 2, 3], "integer 2 expected from int variable 'DataQubits', but got 3"),
        ],
    )
    def test_schedule_property(
        self,
        num_data_qubits: int,
        num_stabilisers: int,
        schedule: Sequence[int],
        expected_error: str | None,
    ) -> None:
        qubits = t.TestOp(result_types=[QubitType() for _ in range(num_data_qubits)]).results
        op = PlaquetteOp(
            qubits,
            [PauliStringAttr([("X", 0)], num_data_qubits) for _ in range(num_stabilisers)],
            num_stabilisers,
            stabiliser_measurement_method=SynchronisedScheduleAttr(schedule),
        )
        if expected_error is not None:
            with pytest.raises(VerifyException, match=re.escape(expected_error)):
                op.verify()
        else:
            op.verify()


class TestSubCircuitOp:
    def test_must_be_in_round_op(self) -> None:
        op = SubCircuitOp([Block([t.TestTermOp()])], measurements=0)
        containing_op = t.TestOp(regions=[[Block([op, YieldOp()])]])
        with pytest.raises(
            VerifyException, match=re.escape("Op must be inside a plaquette.round operation.")
        ):
            containing_op.verify()

    @pytest.mark.parametrize("num_regions", range(3))
    def test_empty(self, num_regions: int) -> None:
        op = _encapsulate_in_round_op(
            SubCircuitOp(
                [Block([YieldOp()]) for _ in range(num_regions)],
                measurements=0,
            )
        )
        op.verify()

    def test_negative_number_measurements_fails(self) -> None:
        with pytest.raises(
            RuntimeError, match=re.escape("Cannot have a negative number of measurements. Got -1.")
        ):
            _ = SubCircuitOp([], -1)

    @pytest.mark.parametrize(
        ("num_measurements", "blocks", "expected_message"),
        [
            (1, [_block_yielding_n_measurements(1, include_args=False)], None),
            (6, [_block_yielding_n_measurements(6, include_args=False)], None),
            (
                6,
                [
                    _block_yielding_n_measurements(3, include_args=False),
                    _block_yielding_n_measurements(3, include_args=False),
                ],
                None,
            ),
            (
                6,
                [
                    _block_yielding_n_measurements(3, include_args=False),
                    _block_yielding_n_measurements(0, include_args=False),
                    _block_yielding_n_measurements(3, include_args=False),
                ],
                None,
            ),
            (
                0,
                [
                    _block_yielding_n_measurements(0, include_args=False),
                    _block_yielding_n_measurements(0, include_args=False),
                    _block_yielding_n_measurements(0, include_args=False),
                ],
                None,
            ),
            (
                1,
                [
                    _block_yielding_n_measurements(1, include_args=False),
                    _block_yielding_n_measurements(1, include_args=False),
                ],
                re.escape(
                    "The number of variables yielded from the parallel regions (2) doesn't match "
                    "the number returned from the round op containing them"
                ),
            ),
            (
                10,
                [
                    _block_yielding_n_measurements(9, include_args=False),
                    _block_yielding_n_measurements(0, include_args=False),
                ],
                re.escape(
                    "The number of variables yielded from the parallel regions (9) doesn't match "
                    "the number returned from the round op containing them"
                ),
            ),
            (
                1,
                [_block_yielding_n_measurements([IntegerType(2)], include_args=False)],
                re.escape(
                    "Type of variable yielded from parallel region (i2) doesn't match the type of "
                    "the corresponding variable returned from the round op containing said region "
                    "(i1)"
                ),
            ),
        ],
    )
    def test_returned_measurements(
        self, num_measurements: int, blocks: Sequence[Block], expected_message: str | None
    ) -> None:
        op = _encapsulate_in_round_op(SubCircuitOp(blocks, num_measurements))
        if expected_message is not None:
            with pytest.raises(VerifyException, match=expected_message):
                op.verify()
        else:
            op.verify()

    def test_no_block_args(self) -> None:
        msg = re.escape("Expected 0 entry arguments")
        with pytest.raises(VerifyException, match=msg):
            SubCircuitOp([_block_yielding_n_measurements(1, include_args=True)], 1).verify()

    def test_get_results_for_yield(self) -> None:
        """Test that get_results_for_yield returns the correct measurement slices."""
        # Create blocks with different numbers of yielded measurements
        block1 = _block_yielding_n_measurements(2, include_args=False)
        block2 = _block_yielding_n_measurements(3, include_args=False)
        block3 = _block_yielding_n_measurements(1, include_args=False)

        # Create SubCircuitOp with 6 total measurements (2 + 3 + 1)
        sub_circuit = SubCircuitOp([block1, block2, block3], measurements=6)

        # Get the YieldOps from each block
        yield_op1 = block1.last_op
        yield_op2 = block2.last_op
        yield_op3 = block3.last_op

        assert isinstance(yield_op1, YieldOp)
        assert isinstance(yield_op2, YieldOp)
        assert isinstance(yield_op3, YieldOp)

        # Test that each YieldOp returns the correct slice of measurements
        results1 = sub_circuit.get_results_for_yield(yield_op1)
        assert len(results1) == 2
        assert results1 == sub_circuit.measurements[0:2]

        results2 = sub_circuit.get_results_for_yield(yield_op2)
        assert len(results2) == 3
        assert results2 == sub_circuit.measurements[2:5]

        results3 = sub_circuit.get_results_for_yield(yield_op3)
        assert len(results3) == 1
        assert results3 == sub_circuit.measurements[5:6]

    def test_get_results_for_yield_with_unrelated_yield_raises(self) -> None:
        """Test that get_results_for_yield raises ValueError for unrelated YieldOp."""
        # Create a SubCircuitOp with one region
        block = _block_yielding_n_measurements(2, include_args=False)
        sub_circuit = SubCircuitOp([block], measurements=2)

        # Create an unrelated YieldOp
        unrelated_yield = YieldOp()

        # Test that calling with unrelated YieldOp raises ValueError
        with pytest.raises(
            ValueError, match=re.escape("Provided YieldOp does not belong to this SubCircuitOp")
        ):
            sub_circuit.get_results_for_yield(unrelated_yield)


# region Synchronised schedule tests


class TestSynchronisedScheduleAttr:
    @pytest.mark.parametrize(
        ("schedule", "expected_num_qubits", "expected_num_measurements", "expected_weight"),
        [
            # Single qubit, single measurement
            ([0], 1, 1, 1),
            # Multiple qubits, standard schedule
            ([0, 1, 2, 3], 4, 1, 4),
            ([0, 2, 1, 3], 4, 1, 4),
            # Large schedule
            ([0, 1, 2, 3, 4, 5], 6, 1, 6),
            # Two qubits
            ([0, 1], 2, 1, 2),
            # With some unused qubits
            ([0, 1, None, 3], 4, 1, 3),
            ([None, 3, None, 2], 4, 1, 2),
            ([None, 3, None, None], 4, 1, 1),
        ],
    )
    def test_properties_with_valid_schedules(
        self,
        schedule: list[int],
        expected_num_qubits: int,
        expected_num_measurements: int,
        expected_weight: int,
    ) -> None:
        """Test that properties are correctly computed for valid schedules."""
        attr = SynchronisedScheduleAttr(schedule)
        assert attr.num_qubits == expected_num_qubits
        assert attr.num_measurements == expected_num_measurements
        assert attr.stabiliser_weights == (expected_weight,)

    @pytest.mark.parametrize(
        ("schedule", "expected_display"),
        [
            # Simple sequences
            ([0], "#plaquette.synchronised_schedule<[0]>"),
            ([0, 1], "#plaquette.synchronised_schedule<[0, 1]>"),
            ([0, 1, 2, 3], "#plaquette.synchronised_schedule<[0, 1, 2, 3]>"),
            # Non-sequential indices
            ([3, 1, 2, 0], "#plaquette.synchronised_schedule<[3, 1, 2, 0]>"),
            # With some None entries
            ([None, 1, None, 0], "#plaquette.synchronised_schedule<[none, 1, none, 0]>"),
        ],
    )
    def test_string_representation(self, schedule: list[int], expected_display: str) -> None:
        """Test that the string representation is correct."""
        attr = SynchronisedScheduleAttr(schedule)
        ctx = Context()
        ctx.load_dialect(Plaquette)
        output = StringIO()
        printer = Printer(stream=output)
        printer.print_attribute(attr)
        assert output.getvalue() == expected_display


class TestStabiliserMeasurementMethodConstraint:
    """Test suite for constraint verification on measurement methods."""

    @pytest.mark.parametrize(
        ("schedule", "num_qubits", "num_measurements", "stabiliser_weight", "expected_error"),
        [
            # Valid constraints
            ([0], 1, 1, 1, None),
            ([None], 1, 1, 0, None),
            ([1, 2, 3, 4], 4, 1, 4, None),
            ([1, None, 3, 4], 4, 1, 3, None),
            ([5, 8], 2, 1, 2, None),
            # Invalid stabiliser weight
            ([None], 1, 1, 1, "Invalid value 0, expected 1"),
            # Invalid number of qubits
            ([0, 2, 5], 1, 1, 3, "Invalid value 3, expected 1"),
            # Invalid number of measurements (always 1 for this stabiliser measurement type)
            ([1, 2, 3], 3, 0, 3, "Invalid value 1, expected 0"),
            ([1, 2, 3], 3, 2, 3, "Invalid value 1, expected 2"),
        ],
    )
    def test_constraint_verification_with_valid_attributes(
        self,
        schedule: list[int | None],
        num_qubits: int,
        num_measurements: int,
        stabiliser_weight: int,
        expected_error: str | None,
    ) -> None:
        """Test that constraints accept valid synchronised schedule attributes."""
        attr = SynchronisedScheduleAttr(schedule)
        constraint = StabiliserMeasurementMethodConstraint(
            EqIntConstraint(num_qubits),
            EqIntConstraint(num_measurements),
            EqIntConstraint(stabiliser_weight),
        )
        constraint_ctx = ConstraintContext()

        if expected_error is None:
            # Should not raise
            constraint.verify(attr, constraint_ctx)
        else:
            with pytest.raises(VerifyException, match=re.escape(expected_error)):
                constraint.verify(attr, constraint_ctx)

    @pytest.mark.parametrize("schedule", [[0, 1, 2], [0, 1, 2, 3], [0], [None, 1, 4]])
    def test_constraint_with_default_constraints(self, schedule: list[int]) -> None:
        """Test constraint verification with default constraint parameters."""

        attr = SynchronisedScheduleAttr(schedule)
        constraint = StabiliserMeasurementMethodConstraint()
        constraint_ctx = ConstraintContext()

        # Should verify without raising
        constraint.verify(attr, constraint_ctx)


# endregion
