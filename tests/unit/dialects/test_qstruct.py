"""Tests for the quantum circuit structure xDSL dialect."""

import re
from typing import Literal

import pytest
from xdsl.builder import Builder
from xdsl.dialects import test as t
from xdsl.dialects.builtin import ModuleOp, VectorType, i1, i32
from xdsl.ir import Attribute, Block, Region
from xdsl.utils.exceptions import VerifyException

from deltakit_compile.dialects import qcore
from deltakit_compile.dialects.qstruct import (
    AlignmentAttr,
    CircuitOp,
    OutputOp,
    ParallelOp,
    RepeatOp,
    YieldOp,
    _AlignmentEnum,
    make_parallel_from_ops,
)


class TestAttributes:
    @pytest.mark.parametrize(
        ("literal", "enum"), [("TOP", _AlignmentEnum.TOP), ("BOTTOM", _AlignmentEnum.BOTTOM)]
    )
    def test_alignment_attr(self, literal: Literal["TOP", "BOTTOM"], enum: _AlignmentEnum):
        """Test init and coerce of AlignmentAttr."""
        align = AlignmentAttr(enum)
        assert align == AlignmentAttr(literal)
        assert align == AlignmentAttr.coerce(align)
        assert align == AlignmentAttr.coerce(literal)

    def test_alignment_attr_enum_methods(self):
        """Test the enum-like methods of AlignmentAttr."""
        assert AlignmentAttr("TOP") == AlignmentAttr.TOP()
        assert AlignmentAttr("BOTTOM") == AlignmentAttr.BOTTOM()


class TestCircuitOp:
    @pytest.mark.parametrize(
        ("ins", "outs", "ins_qubits", "outs_qubits"),
        [
            ([], [qcore.QubitType()], 0, 1),
            ([qcore.QubitRegType(2)], [qcore.QubitRegType(4)], 2, 4),
            ([qcore.QubitRegType(2), qcore.QubitType()], [qcore.QubitRegType(4)], 3, 4),
        ],
    )
    def test_circuit_qubit_num_verify(
        self, ins: list[Attribute], outs: list[Attribute], ins_qubits: int, outs_qubits: int
    ) -> None:
        """Test that a circuit op verifies the number of qubits it takes in matches the number of
        qubits it returns."""
        in_ssas = t.TestOp(result_types=ins).results
        out_ssas = t.TestOp(result_types=outs).results
        error_msg = (
            f".*integer {ins_qubits} expected from int variable 'Qubits', but got {outs_qubits}.*"
        )
        with pytest.raises(VerifyException, match=error_msg):
            CircuitOp(in_ssas, outs, [YieldOp(*out_ssas)]).verify()

    def test_verify_circuit_args(self) -> None:
        """Test that a circuit op verifies that its args and block args match."""
        i = t.TestOp(result_types=[i1]).results[0]
        circuit_op = CircuitOp.build(operands=[[i]], result_types=[[]], regions=[[YieldOp()]])
        with pytest.raises(
            VerifyException,
            match=r"attributes \('i1',\) expected from range variable 'Arguments', but got \(\)",
        ):
            circuit_op.verify()
        circuit_op = CircuitOp([i], [], [YieldOp()])
        circuit_op.verify()  # Proper constructor sets block args

    def test_verify_circuit_results(self) -> None:
        """Test that a circuit op verifies that its yields and results match."""
        circuit_op = CircuitOp([], [i1], [YieldOp()])
        with pytest.raises(
            VerifyException,
            match=r"The number of variables yielded from the circuit \(0\) doesn't match the "
            r"number of variables the circuit op returns \(1\)",
        ):
            circuit_op.verify()

        @Builder.implicit_region
        def body():
            i = t.TestOp(result_types=[i32])
            YieldOp(i)

        circuit_op = CircuitOp([], [i1], body)
        with pytest.raises(
            VerifyException,
            match=r"The type of variable yielded from the circuit \(i32\) doesn't match the "
            r"type of the corresponding variable the circuit op returns \(i1\)",
        ):
            circuit_op.verify()

    def test_circuit_num_qubits(self) -> None:
        """Test that num_qubits counts the number of qubits operated on by the circuit."""
        circuit_op = CircuitOp([], [], [YieldOp()])
        assert circuit_op.num_qubits == 0

        circuit_op = CircuitOp(
            t.TestOp(result_types=[qcore.QubitType()]).results,
            [],
            [YieldOp(t.TestOp(result_types=[qcore.QubitType()]).results[0])],
        )
        assert circuit_op.num_qubits == 1

        circuit_op = CircuitOp(
            t.TestOp(result_types=[qcore.QubitRegType(2), qcore.QubitType()]).results,
            [],
            [YieldOp(t.TestOp(result_types=[qcore.QubitRegType(3)]).results[0])],
        )
        assert circuit_op.num_qubits == 3

    def test_operand_for_block_arg(self) -> None:
        """Test the operand_for_block_arg method"""

        types = (i1, qcore.QubitType())
        block = Block([], arg_types=types)
        block.add_op(YieldOp(*block.args))
        inputs = t.TestOp(result_types=types)
        circuit_op = CircuitOp(inputs.res, types, Region(block))
        circuit_op.verify()

        assert circuit_op.operand_for_block_arg(block.args[0]) == circuit_op.args[0]
        assert circuit_op.operand_for_block_arg(block.args[1]) == circuit_op.args[1]

        with pytest.raises(
            ValueError,
            match=r"Cannot get qstruct\.circuit operand for value <OpResult.*>: "
            "SSAValue is not a block argument of this circuit's body",
        ):
            circuit_op.operand_for_block_arg(circuit_op.args[0])

        other_block = Block([], arg_types=[i1])
        with pytest.raises(
            ValueError,
            match=r"Cannot get qstruct\.circuit operand for value <BlockArgument.*>: "
            "SSAValue is not a block argument of this circuit's body",
        ):
            circuit_op.operand_for_block_arg(other_block.args[0])

        other_circuit = circuit_op.clone()
        with pytest.raises(
            ValueError,
            match=r"Cannot get qstruct\.circuit operand for value <BlockArgument.*>: "
            "SSAValue is not a block argument of this circuit's body",
        ):
            circuit_op.operand_for_block_arg(other_circuit.body.block.args[0])


class TestRepeatOp:
    def test_repeat_verify(self):
        """Test the verification for the repeat op."""
        with pytest.raises(VerifyException, match=r"expected integer >= 1, got 0"):
            RepeatOp(0, Block([YieldOp()])).verify()

        ssa = t.TestOp(result_types=[t.TestType("T")]).results[0]
        with pytest.raises(
            VerifyException,
            match=r"The number of iter_args \(2\), the number of block arguments in the repeat "
            r"body \(0\), the number of values yielded from the repeat body \(1\), and the number "
            r"of results returned \(2\) must all match",
        ):
            RepeatOp(2, Block([YieldOp(ssa)]), [ssa, ssa]).verify()

        ssa2 = t.TestOp(result_types=[t.TestType("T2")]).results[0]
        with pytest.raises(
            VerifyException,
            match=r'The iter arg type !test.type<"T2">, block arg type !test.type<"T">, '
            r'yielded value type !test.type<"T">, and result type !test.type<"T2"> must all match',
        ):
            RepeatOp(2, Block([YieldOp(ssa)], arg_types=[ssa.type]), [ssa2]).verify()


class TestParallelOp:
    def test_verify_parallel_yield_num(self):
        """Test that a parallel op where the number of SSAValues yielded in the regions doesn't
        match those returned by the op."""

        @ModuleOp
        @Builder.implicit_region
        def module_op():
            qubit0 = t.TestOp(result_types=[t.TestType("qubit")])
            qubit1 = t.TestOp(result_types=[t.TestType("qubit")])

            @Builder.implicit_region
            def par0():
                ro0 = t.TestOp(operands=[qubit0], result_types=[t.TestType("bit")])
                YieldOp(ro0)

            @Builder.implicit_region
            def par1():
                ro1 = t.TestOp(operands=[qubit1], result_types=[t.TestType("bit")])
                YieldOp(ro1)

            ParallelOp([t.TestType("bit")], [par0, par1])

        with pytest.raises(
            VerifyException,
            match="The number of variables yielded from the parallel regions \\(2\\) doesn't match "
            "the number returned from the parallel op containing them \\(1\\)",
        ):
            module_op.verify()

    def test_verify_parallel_yield_type(self):
        """Test that a parallel op where the type of an SSAValue yielded in the regions doesn't
        match those returned by the op."""

        @ModuleOp
        @Builder.implicit_region
        def module_op():
            qubit0 = t.TestOp(result_types=[t.TestType("qubit")])
            qubit1 = t.TestOp(result_types=[t.TestType("qubit")])

            @Builder.implicit_region
            def par0():
                ro0 = t.TestOp(operands=[qubit0], result_types=[t.TestType("bit")])
                YieldOp(ro0)

            @Builder.implicit_region
            def par1():
                ro1 = t.TestOp(operands=[qubit1], result_types=[t.TestType("bit")])
                YieldOp(ro1)

            ParallelOp([t.TestType("bit"), t.TestType("qubit")], [par0, par1])

        with pytest.raises(
            VerifyException,
            match=r'Type of variable yielded from parallel region \(!test.type<"bit">\) doesn\'t '
            "match the type of the corresponding variable returned from the parallel op containing "
            r'said region \(!test.type<"qubit">\)',
        ):
            module_op.verify()

    def test_parallel_verify_qubit_overlap(self):
        """Test that a parallel with the same qubit used in multiple regions throws an error."""

        @ModuleOp
        @Builder.implicit_region
        def module_op():
            qubit = qcore.AllocQubitOp([qcore.QubitType()])

            @Builder.implicit_region
            def par0():
                t.TestOp(operands=[qubit])
                YieldOp()

            @Builder.implicit_region
            def par1():
                t.TestOp(operands=[qubit])
                YieldOp()

            ParallelOp([], [par0, par1])

        with pytest.raises(
            VerifyException,
            match=r"Regions 0 and 1 in the same parallel use the same qubits: .*!qcore.qubit.*",
        ):
            module_op.verify()

    def test_parallel_result_to_yield_arg_and_yield_arg_to_result(self):
        """Test that result_to_yield_arg and yield_arg_to_result correctly map the yield args and
        results of a parallel op to each other."""

        qubit0 = t.TestOp(result_types=[t.TestType("qubit")]).results[0]
        qubit1 = t.TestOp(result_types=[t.TestType("qubit")]).results[0]

        @Builder.implicit_region
        def par0():
            ro0 = t.TestOp(operands=[qubit0], result_types=[t.TestType("bit")])
            YieldOp(ro0)

        @Builder.implicit_region
        def par1():
            YieldOp()

        @Builder.implicit_region
        def par2():
            ro1 = t.TestOp(operands=[qubit1], result_types=[t.TestType("bit")]).results[0]
            ro2 = t.TestOp(operands=[qubit1], result_types=[t.TestType("bit")]).results[0]
            YieldOp(ro1, ro2)

        parallel = ParallelOp(
            [t.TestType("bit"), t.TestType("bit"), t.TestType("bit")], [par0, par1, par2]
        )

        assert parallel.result_to_yield_arg(parallel.results[0]) == par0.block.last_op.operands[0]
        assert parallel.result_to_yield_arg(parallel.results[1]) == par2.block.last_op.operands[0]
        assert parallel.result_to_yield_arg(parallel.results[2]) == par2.block.last_op.operands[1]

        assert parallel.yield_arg_to_result(par0.block.last_op.operands[0]) == parallel.results[0]
        assert parallel.yield_arg_to_result(par2.block.last_op.operands[0]) == parallel.results[1]
        assert parallel.yield_arg_to_result(par2.block.last_op.operands[1]) == parallel.results[2]

        unknown_ssa = t.TestOp(result_types=[t.TestType("bit")]).results[0]
        with pytest.raises(ValueError, match=re.escape("is not a result of this ParallelOp.")):
            parallel.result_to_yield_arg(unknown_ssa)
        with pytest.raises(
            ValueError, match=re.escape("is not yielded from any region of this ParallelOp.")
        ):
            parallel.yield_arg_to_result(unknown_ssa)

    @pytest.mark.parametrize(
        ("specs", "exp_types", "exp_yield_counts"),
        [
            # Mix of ops: [bit], [], [bit] -> results [bit, bit]; yields per region [1,0,1]
            (
                [[t.TestType("bit")], [], [t.TestType("bit")]],
                [t.TestType("bit"), t.TestType("bit")],
                [1, 0, 1],
            ),
            # All ops without results -> no results, yields [0,0]
            (
                [[], []],
                [],
                [0, 0],
            ),
            # Single op with a single result -> [bit]
            (
                [[t.TestType("bit")]],
                [t.TestType("bit")],
                [1],
            ),
            # Two single-result ops with different types: [thing], [bit]
            (
                [[t.TestType("thing")], [t.TestType("bit")]],
                [t.TestType("thing"), t.TestType("bit")],
                [1, 1],
            ),
            # One op with two results, one op with none -> [bit, bit], []
            (
                [[t.TestType("bit"), t.TestType("bit")], []],
                [t.TestType("bit"), t.TestType("bit")],
                [2, 0],
            ),
        ],
    )
    def test_make_parallel_from_ops_builds_expected_parallel(
        self, specs: list[list[Attribute]], exp_types: list[Attribute], exp_yield_counts: list[int]
    ):
        """Parametrized test for qstruct.make_parallel_from_ops.

        Each spec entry is a list of result types for a TestOp; an empty list means
        an op with no results. The helper should produce one region per op, with a
        YieldOp carrying the op's results, and aggregate the ParallelOp results in
        the same order.
        """
        # Build the ops from the specs
        ops: list[t.TestOp] = []
        for res_types in specs:
            ops.append(t.TestOp(result_types=res_types))

        parallel = make_parallel_from_ops(ops)

        # Check overall shape
        assert isinstance(parallel, ParallelOp)
        assert [res.type for res in parallel.res] == exp_types
        assert len(parallel.regions) == len(specs)

        # Check each region contains the original op followed by a yield of the op's results
        for i, op in enumerate(ops):
            block_ops = list(parallel.regions[i].block.ops)
            assert block_ops[0] is op
            assert isinstance(block_ops[1], YieldOp)
            assert len(block_ops[1].operands) == exp_yield_counts[i]
            # Operand identity should match the op results in order
            for j in range(exp_yield_counts[i]):
                assert block_ops[1].operands[j] is op.results[j]

        # Verify constructed ParallelOp is well-formed
        parallel.verify()


class TestOutputOp:
    @pytest.mark.parametrize(
        ("arg_type", "arg_str"),
        [
            (qcore.QubitType(), "!qcore.qubit"),
            (qcore.QubitRegType(2), "!qcore.qubit_reg"),
            (VectorType(i32, [1]), "vector<1xi32>"),
        ],
    )
    def test_output_op_verify(self, arg_type: Attribute, arg_str: str):
        """Test that qstruct.output only takes in the builtin types we use."""
        op = OutputOp(
            t.TestOp(result_types=[arg_type]).res,
        )
        with pytest.raises(
            VerifyException,
            match=re.escape(
                "operand 'arguments' at position 0 does not verify:\n| Unexpected attribute "
                f"{arg_str}"
            ),
        ):
            op.verify()
