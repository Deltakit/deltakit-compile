"""Tests for the quantum circuit structure xDSL dialect."""

import re
from collections.abc import Sequence

import pytest
import xdsl.dialects.test as t
from xdsl.dialects.builtin import ArrayAttr, Float32Type, FloatAttr, IntegerType, ModuleOp, i1, i32
from xdsl.ir import Block, Operation
from xdsl.irdl import (
    AnyAttr,
    IRDLOperation,
    ParamAttrConstraint,
    irdl_op_definition,
    opt_operand_def,
    opt_result_def,
    traits_def,
)
from xdsl.transforms.dead_code_elimination import is_trivially_dead
from xdsl.utils.exceptions import VerifyException

from deltakit_compile.dialects.qcore import (
    QuantumEffectInstance,
    QuantumEffectKind,
    QubitMeasureEffect,
    get_quantum_effects,
)
from deltakit_compile.dialects.qec import (
    DecObservableOp,
    DetectorOp,
    DetectorRefType,
    DetectorRoundOp,
    GetCorrectedOp,
    GetCorrectionOp,
    GetUncorrectedOp,
    IsCorrectionReadyOp,
    MeasurementRoundOp,
    ObservableIncludeOp,
    ObservableType,
)


class TestTypes:
    """Tests for Types defined in the qec dialect."""

    def test_types(self):
        """Test that the qec types can be inited correctly."""
        det_ref = DetectorRefType()
        obvs = ObservableType()
        assert ParamAttrConstraint(DetectorRefType, []).verifies(det_ref)
        assert ParamAttrConstraint(ObservableType, []).verifies(obvs)


class TestOps:
    def test_detector_verifies(self):
        """Tests that qec.detector op verifies correctly."""
        test_alloc = t.TestOp(result_types=(i1, i1, i32))
        args = test_alloc.results

        op = DetectorOp(args)
        with pytest.raises(VerifyException, match="Expected attribute i1 but got i32"):
            op.verify()

        op = DetectorOp.build(operands=[args[:2]], result_types=[i1])
        with pytest.raises(
            VerifyException, match=re.escape("Expected attribute !qec.detector_ref but got i1")
        ):
            op.verify()

        op = DetectorOp(args[:2])
        op.coords = ArrayAttr([FloatAttr(0.1, Float32Type())])
        with pytest.raises(VerifyException, match=re.escape("f32 should be of base attribute f64")):
            op.verify()

        op = DetectorOp(args[:2], [0.1, 0.2, -0.1])
        op.verify()

        ModuleOp([test_alloc, op])
        with pytest.raises(
            VerifyException,
            match=re.escape("Op must be inside a circuit (an op with the IsCircuit trait)"),
        ):
            op.verify()

    """Tests for Operations defined in the qec dialect."""

    def test_detector_traits(self):
        """Tests that qec detector ops have DecodingSideEffects."""
        test_alloc = t.TestOp(result_types=(i1, i1, i1))
        args = test_alloc.results
        op = DetectorOp(args)
        op.verify()
        assert get_quantum_effects(op) == {QuantumEffectInstance(QuantumEffectKind.DECODING, None)}

    def test_dec_observable_verifies(self):
        """Tests that qec.dec_observable op verifies correctly."""
        test_alloc = t.TestOp(result_types=(i1, i1, i32))
        args = test_alloc.results

        op = DecObservableOp()
        op.verify()
        assert op.result.type == ObservableType()

        op = DecObservableOp.create(operands=args)
        with pytest.raises(VerifyException, match="Expected 0 operands, but got 3"):
            op.verify()

        op = DecObservableOp.create(result_types=[i1])
        with pytest.raises(
            VerifyException, match=re.escape("Expected attribute !qec.observable but got i1")
        ):
            op.verify()

    def test_dec_observable_traits(self):
        """Tests that qec dec observable ops have NoQuantumEffect and Pure traits."""
        op = DecObservableOp()
        op.verify()
        assert get_quantum_effects(op) == set()
        assert is_trivially_dead(op)

    def test_observable_include_verifies(self):
        """Tests that qec.observable_include op verifies correctly."""
        obs_test_alloc = t.TestOp(result_types=(ObservableType(), ObservableType()))
        ob1, ob2 = obs_test_alloc.results
        test_alloc = t.TestOp(result_types=(i1, i1, i32))
        args = test_alloc.results

        op = ObservableIncludeOp(ob1, args[:2])
        op.verify()
        assert op.in_obs == ob1
        assert op.measurements == (args[0], args[1])
        assert op.out_obs.type == ObservableType()

        op = ObservableIncludeOp.create(operands=[ob1, ob2, *args])
        with pytest.raises(
            VerifyException, match=re.escape("Expected attribute i1 but got !qec.observable")
        ):
            op.verify()

        op = ObservableIncludeOp.create(operands=[ob2, args[0]], result_types=[i1])
        with pytest.raises(
            VerifyException, match=re.escape("Expected attribute !qec.observable but got i1")
        ):
            op.verify()

        op = ObservableIncludeOp(ob2, args[:2])
        ModuleOp([obs_test_alloc, test_alloc, op])
        with pytest.raises(
            VerifyException,
            match=re.escape("Op must be inside a circuit (an op with the IsCircuit trait)"),
        ):
            op.verify()

    def test_observable_include_traits(self):
        """Tests that qec dec observable ops have NoQuantumEffect and Pure traits."""
        test_alloc = t.TestOp(result_types=(ObservableType(), i1, i1, i1, i1))
        args = test_alloc.results
        op = ObservableIncludeOp(args[0], args[1:])
        op.verify()
        assert get_quantum_effects(op) == set()
        assert is_trivially_dead(op)

    @pytest.mark.parametrize(
        "op_type", [GetUncorrectedOp, GetCorrectionOp, GetCorrectedOp, IsCorrectionReadyOp]
    )
    def test_getter_ops_verify(
        self,
        op_type: type[GetUncorrectedOp | GetCorrectionOp | GetCorrectedOp | IsCorrectionReadyOp],
    ):
        """Tests that the qec.get_... / qec.is_... ops verify correctly."""
        obs_test_alloc = t.TestOp(result_types=(ObservableType(), ObservableType(), i1))
        ob_1, ob_2, int1 = obs_test_alloc.results

        op = op_type(ob_1)
        op.verify()
        assert op.obs == ob_1
        assert op.result.type == i1

        op = op_type.create(operands=[ob_1, ob_2], result_types=[i1])
        with pytest.raises(
            VerifyException,
            match=re.escape("Operation does not verify: Expected 1 operand, but got 2"),
        ):
            op.verify()

        op = op_type.create(operands=[int1], result_types=[i1])
        with pytest.raises(
            VerifyException,
            match=re.escape("Expected attribute !qec.observable or !sobs.observable"),
        ):
            op.verify()

        op = op_type.create(operands=[ob_1], result_types=[i32])
        with pytest.raises(VerifyException, match=re.escape("Expected attribute i1 but got i32")):
            op.verify()

    @pytest.mark.parametrize(
        "op_type", [GetUncorrectedOp, GetCorrectionOp, GetCorrectedOp, IsCorrectionReadyOp]
    )
    def test__getter_ops_traits(self, op_type: type[Operation]):
        """Tests that qec dec observable ops have NoQuantumEffect and Pure traits."""
        test_alloc = t.TestOp(result_types=(ObservableType(),))
        obs = test_alloc.results[0]
        op = op_type.create(operands=[obs], result_types=[i1])
        op.verify()
        assert get_quantum_effects(op) == set()
        assert is_trivially_dead(op)

    @irdl_op_definition
    class TMeasure(IRDLOperation):
        """Test measurement op."""

        name = "test.measure"
        arg = opt_operand_def(AnyAttr())
        res = opt_result_def(AnyAttr())
        traits = traits_def(QubitMeasureEffect("arg"))

    def test_expected_round_type(
        self,
    ):
        """Test that the expected round type is returned"""
        qubit_alloc_op1 = t.TestOp(result_types=[t.TestType("qubit")])
        qubit_alloc_op2 = t.TestOp(result_types=[t.TestType("qubit")])
        measure_op1 = self.TMeasure(operands=[qubit_alloc_op1.results[0]], result_types=[i1])
        measure_op2 = self.TMeasure(operands=[qubit_alloc_op2.results[0]], result_types=[i1])
        measure_round_op = MeasurementRoundOp((*measure_op1.results, *measure_op2.results))
        ops = measure_round_op.get_round_measurement_ops(self.TMeasure)
        assert len(ops) == 2
        assert measure_op1 in ops
        assert measure_op2 in ops
        measure_round_op.verify()

    def test_bad_expected_round_type(self):
        """Test that an error will be raised if an unexpected round type is found"""
        qubit_alloc_op1 = t.TestOp(result_types=[t.TestType("qubit")])
        qubit_alloc_op2 = t.TestOp(result_types=[t.TestType("qubit")])
        measure_op1 = self.TMeasure(operands=[qubit_alloc_op1.results[0]], result_types=[i1])
        measure_op2 = self.TMeasure(operands=[qubit_alloc_op2.results[0]], result_types=[i1])
        unexpected_op = t.TestOp(operands=[qubit_alloc_op1.results[0]], result_types=[i1])
        measure_round_op = MeasurementRoundOp(
            (*measure_op1.results, *measure_op2.results, *unexpected_op.results)
        )
        with pytest.raises(
            ValueError,
            match=r"Found 1 operations that are not of expected type 'test.measure' "
            r"these ops are: test.op",
        ):
            measure_round_op.get_round_measurement_ops(self.TMeasure)

    @pytest.mark.parametrize(
        ("args", "error"),
        [
            (
                t.TestOp().results,
                "qec.measurement_round must have at least 1 quantum measure op.",
            ),
            (
                [t.TestOp(result_types=[IntegerType(1)]).results[0]],
                "OpResult parent must have the MEASURE QuantumEffect trait.",
            ),
            (
                [t.TestOp(result_types=[IntegerType(8)]).results[0]],
                "operand 'measurements' at position 0 does not verify:\nUnexpected attribute i8",
            ),
            (
                [Block(arg_types=[i1]).args[0]],
                "All measurement operands are expected to be of OpResult type",
            ),
        ],
    )
    def test_verify_measure_round_op(self, args, error):
        """Test that MeasurementRoundOp verify catches bad args"""
        with pytest.raises(VerifyException, match=error):
            MeasurementRoundOp(args).verify(False)

    @pytest.mark.parametrize(
        "inputs",
        [[], [0], [0, 1, 2], [0, 1, 2, 3], [0, 0, 0], [3, 2, 1, 0]],
    )
    def test_detector_round_init(self, inputs: Sequence[int]) -> None:
        """Tests that the DetectorRoundOp init method works as expected."""
        t_op = t.TestOp(result_types=[DetectorRefType()] * 4)
        operands = [t_op.res[i] for i in inputs]
        op = DetectorRoundOp(operands)
        assert list(op.detectors) == operands
