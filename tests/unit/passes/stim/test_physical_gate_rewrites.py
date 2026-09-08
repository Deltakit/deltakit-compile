# (c) Copyright Riverlane 2026. All rights reserved.
"""Tests for the public rewrite patterns used in the lower-physical-to-stim pass."""

import re
from typing import cast

import numpy as np
import pytest
from xdsl.context import Context
from xdsl.dialects.builtin import Builtin, ModuleOp, StringAttr
from xdsl.ir import Operation
from xdsl.pattern_rewriter import GreedyRewritePatternApplier, PatternRewriteWalker, RewritePattern

from deltakit_compile.dialects import qcore, qref, qstruct, stim
from deltakit_compile.dialects.ncstim import (
    NonCliffordGateEnum,
    NonCliffordGateOp,
    RotationGateOp,
    U3GateOp,
)
from deltakit_compile.dialects.qcore import (
    CCXGateAttr,
    CCZGateAttr,
    CHGateAttr,
    CXGateAttr,
    GateAttribute,
    HGateAttr,
    RotationGateAttr,
    SGateAttr,
    SqrtXXGateAttr,
    TGateAttr,
    UnitaryGateAttr,
    XGateAttr,
)
from deltakit_compile.exceptions import LostStimTagWarning, StimUnsupportedGate
from deltakit_compile.passes.stim._common import TAG_ATTR
from deltakit_compile.passes.stim.physical_gate_rewrites import (
    _QCORE_TO_STIM_GATE_MAPPING,
    AllocQubitPattern,
    GatePattern,
    InlineCircuitPattern,
    MeasurePattern,
    PauliNoisePattern,
    ResetPattern,
    get_existing_qubit_ids,
    get_physical_gate_rewrite_patterns,
    qcore_gate_to_deltakit_stim_enum,
    qcore_gate_to_ncstim_op,
)
from deltakit_compile.shared.deltakit_stim.gates import (
    DeltakitStimGateEnum,
    SingleQubitUnitaryEnum,
    TwoQubitUnitaryEnum,
)
from tests.unit.conftest import parse_ir


def get_common_context() -> Context:
    """Get a context with the relevant dialects loaded."""
    ctx = Context()
    ctx.load_dialect(Builtin)
    ctx.load_dialect(qcore.QCore)
    ctx.load_dialect(qref.QRef)
    ctx.load_dialect(qstruct.QStruct)
    return ctx


def get_ops_after_rewrites(mlir_str: str, rewrites: list[RewritePattern]) -> list[Operation]:
    """Parse the IR and apply the given rewrite patterns to get the rewritten ops to inspect."""
    module_op = parse_ir(mlir_str, get_common_context())
    PatternRewriteWalker(GreedyRewritePatternApplier(rewrites)).rewrite_module(module_op)
    return list(module_op.walk())


class TestQcoreGateToStimEnum:
    @pytest.mark.parametrize(
        ("gate", "exp_stim_enum"),
        [
            (XGateAttr(), SingleQubitUnitaryEnum.X),
            (XGateAttr().sqrt(), SingleQubitUnitaryEnum.SQRT_X),
            (XGateAttr().sqrt_dag(), SingleQubitUnitaryEnum.SQRT_X_DAG),
            (SqrtXXGateAttr(), TwoQubitUnitaryEnum.SQRT_XX),
        ],
    )
    def test_correct_output_type(
        self, gate: GateAttribute, exp_stim_enum: DeltakitStimGateEnum
    ) -> None:
        stim_enum = qcore_gate_to_deltakit_stim_enum(gate)
        assert isinstance(stim_enum, DeltakitStimGateEnum)
        assert stim_enum == exp_stim_enum

    def test_preserves_mapping_exactly(self) -> None:
        for gate, stim_enum in _QCORE_TO_STIM_GATE_MAPPING.items():
            assert qcore_gate_to_deltakit_stim_enum(gate) == stim_enum

    def test_incompatible_gate_raises_by_default(self) -> None:
        gate = UnitaryGateAttr.from_ndarray(np.array([[1, 0], [0, 1]]))
        with pytest.raises(
            StimUnsupportedGate,
            match=r"Cannot map qcore gate qcore\.gate\.unitary<\.\.\. 2x2> to Deltakit-Stim enum",
        ):
            qcore_gate_to_deltakit_stim_enum(gate)

    def test_no_raise_if_requested(self) -> None:
        gate = UnitaryGateAttr.from_ndarray(np.array([[1, 0], [0, 1]]))
        stim_enum = qcore_gate_to_deltakit_stim_enum(gate, raise_on_unsupported=False)
        assert stim_enum is None


class TestQcoreGateToNCStimOp:
    @pytest.fixture
    def qubit_allocs(self) -> list[stim.QubitAllocOp]:
        """Fresh qubit allocations for a single test. These are built per test, rather than
        shared as class-level SSA values, so that usage recorded on them (e.g. `SSAValue.uses`)
        by one test's gate ops can never leak into another test."""
        return [stim.QubitAllocOp(i) for i in range(3)]

    @pytest.mark.parametrize(
        ("gate", "exp_pauli_modifiers", "exp_angle"),
        [
            (RotationGateAttr.x(0.5), [stim.PauliAttr(stim.PauliOperatorEnum.X)], 0.5),
            (RotationGateAttr.y(0.25), [stim.PauliAttr(stim.PauliOperatorEnum.Y)], 0.25),
            (RotationGateAttr.z(1.0), [stim.PauliAttr(stim.PauliOperatorEnum.Z)], 1.0),
            (
                RotationGateAttr.xx(0.5),
                [
                    stim.PauliAttr(stim.PauliOperatorEnum.X),
                    stim.PauliAttr(stim.PauliOperatorEnum.X),
                ],
                0.5,
            ),
            (
                RotationGateAttr.spp([qcore.PauliAttr.X(), qcore.PauliAttr.Y()]),
                [
                    stim.PauliAttr(stim.PauliOperatorEnum.X),
                    stim.PauliAttr(stim.PauliOperatorEnum.Y),
                ],
                0.5,
            ),
            (
                RotationGateAttr.tpp_dag([qcore.PauliAttr.Z()]),
                [stim.PauliAttr(stim.PauliOperatorEnum.Z)],
                -0.25,
            ),
        ],
    )
    def test_rotation_gate_attr_maps_to_rotation_gate_op(
        self,
        gate: RotationGateAttr,
        exp_pauli_modifiers: list[stim.PauliAttr],
        exp_angle: float,
        qubit_allocs: list[stim.QubitAllocOp],
    ) -> None:
        """Tests that RotationGateAttr maps to RotationGateOp via a plain field copy, the choice
        of the most specific instruction name (R_X, SPP, TPP, ...) is entirely
        RotationGateOp's."""
        targets = [qubit_allocs[0].results[0]] * gate.get_qubit_count()
        op = qcore_gate_to_ncstim_op(gate, targets)
        assert isinstance(op, RotationGateOp)
        assert list(op.pauli_modifiers) == exp_pauli_modifiers
        assert op.angle.value.data == exp_angle
        assert list(op.operands) == targets

    @pytest.mark.parametrize(
        "matrix",
        [
            np.eye(2, dtype=complex),
            np.array([[0, 1], [1, 0]], dtype=complex),
            (1 / np.sqrt(2)) * np.array([[1, 1], [1, -1]], dtype=complex),
        ],
    )
    def test_single_qubit_unitary_gate_attr_maps_to_u3_gate_op(
        self, matrix: qcore.NpComplexMatrix, qubit_allocs: list[stim.QubitAllocOp]
    ) -> None:
        """Tests that a single-qubit UnitaryGateAttr maps to a U3GateOp whose angles reconstruct
        the original matrix."""
        qubit = qubit_allocs[0].results[0]
        gate = UnitaryGateAttr.from_ndarray(matrix)
        op = qcore_gate_to_ncstim_op(gate, [qubit])
        assert isinstance(op, U3GateOp)
        reconstructed = UnitaryGateAttr.from_u3(
            op.theta.value.data, op.phi.value.data, op.lam.value.data
        ).get_unitary_matrix()
        nonzero = np.abs(matrix) > 1e-9
        ratios = reconstructed[nonzero] / matrix[nonzero]
        assert np.allclose(ratios, ratios[0], atol=1e-9)
        assert np.isclose(abs(ratios[0]), 1.0, atol=1e-9)
        assert list(op.operands) == [qubit]

    def test_multi_qubit_unitary_gate_attr_raises_by_default(
        self, qubit_allocs: list[stim.QubitAllocOp]
    ) -> None:
        """Tests that a multi-qubit UnitaryGateAttr has no ncstim equivalent, arbitrary
        multi-qubit unitary synthesis is not covered in this mapping function, and raises by
        default, matching qcore_gate_to_lestim_enum's convention."""
        targets = [qubit_allocs[0].results[0], qubit_allocs[1].results[0]]
        gate = UnitaryGateAttr.from_ndarray(CXGateAttr().get_unitary_matrix())
        with pytest.raises(
            StimUnsupportedGate,
            match=r"Cannot map qcore gate qcore\.gate\.unitary<\.\.\. 4x4> to a tsim/clifft "
            r"instruction",
        ):
            qcore_gate_to_ncstim_op(gate, targets)

    def test_multi_qubit_unitary_gate_attr_no_raise_if_requested(
        self, qubit_allocs: list[stim.QubitAllocOp]
    ) -> None:
        """Tests that a multi-qubit UnitaryGateAttr returns None instead of raising when
        raise_on_unsupported is False."""
        targets = [qubit_allocs[0].results[0], qubit_allocs[1].results[0]]
        gate = UnitaryGateAttr.from_ndarray(CXGateAttr().get_unitary_matrix())
        assert qcore_gate_to_ncstim_op(gate, targets, raise_on_unsupported=False) is None

    @pytest.mark.parametrize(
        ("gate", "exp_gate_type", "target_indices"),
        [
            (XGateAttr(), SingleQubitUnitaryEnum.X, (0,)),
            (XGateAttr.sqrt(), SingleQubitUnitaryEnum.SQRT_X, (0,)),
            (HGateAttr(), SingleQubitUnitaryEnum.H, (0,)),
            (SGateAttr.dag(), SingleQubitUnitaryEnum.S_DAG, (0,)),
            (SqrtXXGateAttr(), TwoQubitUnitaryEnum.SQRT_XX, (0, 1)),
            (CXGateAttr(), TwoQubitUnitaryEnum.CNOT, (0, 1)),
        ],
    )
    def test_named_stim_gate_maps_to_stim_clifford_gate_op(
        self,
        gate: GateAttribute,
        exp_gate_type: SingleQubitUnitaryEnum | TwoQubitUnitaryEnum,
        target_indices: tuple[int, ...],
        qubit_allocs: list[stim.QubitAllocOp],
    ) -> None:
        """Tests that any gate already representable in plain stim (X, H, S_dag, sqrt(XX), CX,
        ...) maps to stim.CliffordGateOp, tried before any ncstim-specific form - an X gate
        should always come out as a plain stim X, never as an ncstim rotation, even though the
        latter is also a valid representation."""
        targets = [qubit_allocs[i].results[0] for i in target_indices]
        op = qcore_gate_to_ncstim_op(gate, targets)
        assert isinstance(op, stim.CliffordGateOp)
        assert op.gate_type.data == exp_gate_type
        assert list(op.operands) == targets

    @pytest.mark.parametrize(
        ("gate", "exp_gate_type", "target_indices"),
        [
            (TGateAttr(), NonCliffordGateEnum.T, (0,)),
            (TGateAttr.dag(), NonCliffordGateEnum.T_DAG, (0,)),
            (CCXGateAttr(), NonCliffordGateEnum.CCX, (0, 1, 2)),
            (CCZGateAttr(), NonCliffordGateEnum.CCZ, (0, 1, 2)),
            (CHGateAttr(), NonCliffordGateEnum.CH, (0, 1)),
        ],
    )
    def test_named_non_clifford_gate_maps_to_non_clifford_gate_op(
        self,
        gate: GateAttribute,
        exp_gate_type: NonCliffordGateEnum,
        target_indices: tuple[int, ...],
        qubit_allocs: list[stim.QubitAllocOp],
    ) -> None:
        """Tests that named gates with a dedicated ncstim opcode and no stim equivalent (T,
        T_DAG, CCX, CCZ, CH) map to NonCliffordGateOp."""
        targets = [qubit_allocs[i].results[0] for i in target_indices]
        op = qcore_gate_to_ncstim_op(gate, targets)
        assert isinstance(op, NonCliffordGateOp)
        assert op.gate_type.data == exp_gate_type
        assert list(op.operands) == targets


class TestInlineCircuitPattern:
    mlir_str = """%q0 = qcore.alloc_qubit -> !qcore.qubit
%m0_1, %q0_1 = qstruct.circuit(%q0 : !qcore.qubit) {stim.tag = "abcd"} -> i1, !qcore.qubit {
^bb0(%arg0 : !qcore.qubit):
    qref.gate<#qcore.gate.x>(%arg0) {a_tag = "text"}
    %m0 = qref.measure<Z>(%arg0) -> i1
    qstruct.yield %m0, %arg0 : i1, !qcore.qubit
}
qstruct.output(%m0_1 : i1)
"""

    def test_stim_tag_lost_warning(self) -> None:
        """Test that a warning is issued when a qstruct.circuit op with a stim.tag is inlined."""
        # TODO: should this warn for ALL attributes rather than just stim.tag?

        module_op = parse_ir(self.mlir_str, get_common_context())

        with pytest.warns(
            LostStimTagWarning,
            match=r"test: Stim tag on qstruct.circuit was lost because it was inlined.",
        ):
            PatternRewriteWalker(InlineCircuitPattern("test")).rewrite_module(module_op)

    @pytest.mark.filterwarnings("ignore::deltakit_compile.exceptions.LostStimTagWarning")
    def test_erases_qstruct_circuit(self) -> None:
        """Test that the circuit is correctly inlined."""

        ops = get_ops_after_rewrites(self.mlir_str, [InlineCircuitPattern()])
        assert any(isinstance(op, qstruct.CircuitOp) for op in ops) is False


class TestGetExistingQubitIDs:
    @pytest.mark.parametrize(
        ("mlir_str", "expected_ids"),
        [
            ("", set()),
            (
                "%0 = qcore.alloc_qubit -> !qcore.qubit\n"
                "%1 = qcore.alloc_qubit<ids=[-3]> -> !qcore.qubit",
                {-3},
            ),
            (
                "%0 = qcore.alloc_qubit<ids=[0]> -> !qcore.qubit\n"
                "%1 = qcore.alloc_qubit<ids=[1]> -> !qcore.qubit\n"
                "%4 = qcore.alloc_qubit<ids=[4]> -> !qcore.qubit",
                {0, 1, 4},
            ),
            (
                "%0, %4, %2 = qcore.alloc_qubit<ids=[0, 4, 2]> -> "
                "!qcore.qubit, !qcore.qubit, !qcore.qubit",
                {0, 4, 2},
            ),
        ],
    )
    def test_normal_use(self, mlir_str: str, expected_ids: set[int]) -> None:
        module_op = parse_ir(mlir_str, get_common_context())
        assert get_existing_qubit_ids(module_op) == expected_ids

    def test_raises_on_duplicate(self) -> None:
        mlir_str = (
            "%0 = qcore.alloc_qubit<ids=[0]> -> !qcore.qubit\n"
            "%1 = qcore.alloc_qubit<ids=[0]> -> !qcore.qubit"
        )
        module_op = parse_ir(mlir_str, get_common_context())
        with pytest.raises(ValueError, match=re.escape("Duplicate qubit id 0 found.")):
            get_existing_qubit_ids(module_op)


class TestAllocQubitPattern:
    @staticmethod
    def _get_ops_and_pattern(mlir_str: str) -> tuple[list[Operation], AllocQubitPattern]:
        module_op = parse_ir(mlir_str, get_common_context())
        pattern = AllocQubitPattern(set())
        # We don't want to use GreedyRewritePatternApplier for these tests, else the op is erased
        PatternRewriteWalker(pattern).rewrite_module(module_op)
        return list(module_op.walk()), pattern

    def test_erases_alloc_qubit(self) -> None:
        mlir_str = "%q0 = qcore.alloc_qubit -> !qcore.qubit"
        ops, _ = self._get_ops_and_pattern(mlir_str)
        assert any(isinstance(op, qcore.AllocQubitOp) for op in ops) is False

    def test_single_allocs(self) -> None:
        mlir_str = (
            "%q0 = qcore.alloc_qubit -> !qcore.qubit\n%q1 = qcore.alloc_qubit -> !qcore.qubit"
        )
        ops, _ = self._get_ops_and_pattern(mlir_str)
        assert len(ops) == 3  # the module op is counted too
        # Check 0 and 1 allocated correctly
        assert cast(stim.QubitAllocOp, ops[1]).id.data == 0
        assert cast(stim.QubitAllocOp, ops[2]).id.data == 1

    def test_multi_single_allocs(self) -> None:
        mlir_str = "%q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit"
        ops, _ = self._get_ops_and_pattern(mlir_str)
        assert [type(op) for op in ops] == [ModuleOp, stim.QubitAllocOp, stim.QubitAllocOp]

    def test_raises_for_qubit_reg(self) -> None:
        mlir_str = "%qreg = qcore.alloc_qubit -> !qcore.qubit_reg<2>"
        module_op = parse_ir(mlir_str, get_common_context())
        with pytest.raises(
            NotImplementedError,
            match=re.escape(
                "Rewriting `qcore.AllocQubitOp`s which produce qubit registers is not supported."
            ),
        ):
            PatternRewriteWalker(AllocQubitPattern(set())).rewrite_module(module_op)

    def test_set_coords(self) -> None:
        mlir_str = (
            "%q0, %q1 = qcore.alloc_qubit<coords=[(1, 0), (0, 1)]> -> !qcore.qubit, !qcore.qubit"
        )
        ops, _ = self._get_ops_and_pattern(mlir_str)
        # all allocated first, then all coords
        assert [type(op) for op in ops] == [
            ModuleOp,
            stim.QubitAllocOp,
            stim.QubitAllocOp,
            stim.QubitCoordsOp,
            stim.QubitCoordsOp,
        ]
        assert cast(stim.QubitCoordsOp, ops[-2]).qubitcoord.coordinates == (1, 0)
        assert cast(stim.QubitCoordsOp, ops[-1]).qubitcoord.coordinates == (0, 1)


class TestGatePattern:
    outer_mlir_str = """%q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
%q0_1, %q1_1 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit)
    -> !qcore.qubit, !qcore.qubit {{
^bb0(%arg0 : !qcore.qubit, %arg1 : !qcore.qubit):
    {}
    qstruct.yield %arg0, %arg1: !qcore.qubit, !qcore.qubit
}}
"""
    """Reused outer MLIR string which allocates qubits and a qstruct.circuit to place ops in."""

    @staticmethod
    def _get_ops(mlir_str: str) -> list[Operation]:
        return get_ops_after_rewrites(mlir_str, [InlineCircuitPattern(), GatePattern()])

    def test_replaces_all_gates(self) -> None:
        mlir_str = self.outer_mlir_str.format(
            "qref.gate<#qcore.gate.x>(%arg0)\nqref.gate<#qcore.gate.cx>(%arg0, %arg1)"
        )
        ops = self._get_ops(mlir_str)
        assert [type(op) for op in ops] == [
            ModuleOp,
            qcore.AllocQubitOp,
            stim.CliffordGateOp,
            stim.CliffordGateOp,
        ]
        assert cast(stim.CliffordGateOp, ops[-2]).gate_type.data == "X"
        assert cast(stim.CliffordGateOp, ops[-1]).gate_type.data == "CNOT"

    def test_copies_stim_tag(self) -> None:
        mlir_str = self.outer_mlir_str.format('qref.gate<#qcore.gate.x>(%arg0) {stim.tag = "abcd"}')
        ops = self._get_ops(mlir_str)
        assert cast(stim.GateOp, ops[-1]).attributes.get(TAG_ATTR) == StringAttr("abcd")

    def test_default_conversion_func_raises_on_unsupported_gate(self) -> None:
        mlir_str = self.outer_mlir_str.format("qref.gate<#qcore.gate.t>(%arg0)")
        module_op = parse_ir(mlir_str, get_common_context())
        with pytest.raises(
            StimUnsupportedGate,
            match=re.escape("Cannot map qcore gate #qcore.gate.t to Deltakit-Stim enum"),
        ):
            PatternRewriteWalker(GatePattern()).rewrite_module(module_op)

    def test_nondefault_conversion_func(self) -> None:
        def custom_conversion_func(_gate, qubits) -> stim.CliffordGateOp:
            # Just return a X for all gates
            return stim.CliffordGateOp(gate_type=SingleQubitUnitaryEnum.X, targets=qubits)

        mlir_str = self.outer_mlir_str.format(
            "qref.gate<#qcore.gate.x>(%arg0)\nqref.gate<#qcore.gate.cx>(%arg0, %arg1)"
        )
        ops = get_ops_after_rewrites(
            mlir_str, [InlineCircuitPattern(), GatePattern(custom_conversion_func)]
        )
        assert [type(op) for op in ops] == [
            ModuleOp,
            qcore.AllocQubitOp,
            stim.CliffordGateOp,
            stim.CliffordGateOp,
        ]
        assert all(
            cast(stim.CliffordGateOp, op).gate_type.data == "X"
            for op in ops
            if isinstance(op, stim.CliffordGateOp)
        )

    def test_no_rewrite_if_conversion_func_returns_none(self) -> None:
        def custom_conversion_func(_gate, _qubits) -> None:
            return None

        mlir_str = self.outer_mlir_str.format(
            "qref.gate<#qcore.gate.x>(%arg0)\nqref.gate<#qcore.gate.cx>(%arg0, %arg1)"
        )
        ops = get_ops_after_rewrites(
            mlir_str, [InlineCircuitPattern(), GatePattern(custom_conversion_func)]
        )
        assert [type(op) for op in ops] == [
            ModuleOp,
            qcore.AllocQubitOp,
            qref.GateOp,
            qref.GateOp,
        ]


class TestResetPattern:
    outer_mlir_str = """%q0 = qcore.alloc_qubit -> !qcore.qubit
%q0_1 = qstruct.circuit(%q0 : !qcore.qubit) -> !qcore.qubit {{
^bb0(%arg0 : !qcore.qubit):
    {}
    qstruct.yield %arg0: !qcore.qubit
}}
"""

    @staticmethod
    def _get_ops(mlir_str: str) -> list[Operation]:
        return get_ops_after_rewrites(mlir_str, [InlineCircuitPattern(), ResetPattern()])

    @pytest.mark.parametrize("basis", ["X", "Y", "Z"])
    def test_replaces_all_resets(self, basis: str) -> None:
        mlir_str = self.outer_mlir_str.format(f"qref.reset<{basis}>(%arg0)")
        ops = self._get_ops(mlir_str)
        assert [type(op) for op in ops] == [
            ModuleOp,
            qcore.AllocQubitOp,
            stim.ResetGateOp,
        ]
        assert cast(stim.ResetGateOp, ops[-1]).pauli_modifier.data == basis

    @pytest.mark.parametrize("basis", ["X", "Y", "Z"])
    def test_copies_stim_tag(self, basis: str) -> None:
        mlir_str = self.outer_mlir_str.format(f'qref.reset<{basis}>(%arg0) {{stim.tag = "MoL=42"}}')
        ops = self._get_ops(mlir_str)
        assert cast(stim.ResetGateOp, ops[-1]).attributes.get(TAG_ATTR) == StringAttr("MoL=42")


class TestMeasurePattern:
    outer_mlir_str = """%q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
%q0_1, %q1_1 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit)
    -> !qcore.qubit, !qcore.qubit {{
^bb0(%arg0 : !qcore.qubit, %arg1 : !qcore.qubit):
    {}
    qstruct.yield %arg0, %arg1 : !qcore.qubit, !qcore.qubit
}}
"""

    @staticmethod
    def _get_ops(mlir_str: str) -> list[Operation]:
        return get_ops_after_rewrites(mlir_str, [InlineCircuitPattern(), MeasurePattern()])

    def _get_pauli_str_from_modifiers_attr(
        self, op: stim.MeasurementGateOp | stim.MultiPauliProductMeasurementOp
    ) -> str:
        """Get the string representation of the pauli modifiers from a stim measurement ops."""
        if isinstance(op, stim.MeasurementGateOp):
            return op.pauli_modifier.data

        return "".join(mod.data for mod in op.pauli_modifiers.data)

    def test_single_qubit_and_noise(self) -> None:
        mlir_str = self.outer_mlir_str.format(
            "%m0 = qref.measure<Z>(%arg0) -> i1\n"
            "%m1, %m2 = qref.measure<X, 0.1>(%arg0, %arg1) -> i1, i1"
        )
        ops = self._get_ops(mlir_str)
        assert [type(op) for op in ops] == [
            ModuleOp,
            qcore.AllocQubitOp,
            stim.MeasurementGateOp,
            stim.MeasurementGateOp,
        ]

        first_measure_op = cast(stim.MeasurementGateOp, ops[-2])
        assert self._get_pauli_str_from_modifiers_attr(first_measure_op) == "Z"
        assert len(first_measure_op.targets) == 1

        second_measure_op = cast(stim.MeasurementGateOp, ops[-1])
        assert self._get_pauli_str_from_modifiers_attr(second_measure_op) == "X"
        assert second_measure_op.noise is not None
        assert second_measure_op.noise.value.data == 0.1
        assert len(second_measure_op.targets) == 2

    def test_multi_qubit_same_pauli_and_noise(self) -> None:
        mlir_str = self.outer_mlir_str.format(
            "%m0 = qref.measure<ZZ>(%arg0, %arg1) -> i1\n"
            "%m1 = qref.measure<YX, 0.42>(%arg0, %arg1) -> i1"
        )
        ops = self._get_ops(mlir_str)
        assert [type(op) for op in ops] == [
            ModuleOp,
            qcore.AllocQubitOp,
            stim.MultiPauliProductMeasurementOp,
            stim.MultiPauliProductMeasurementOp,
        ]

        measure_op_0 = cast(stim.MultiPauliProductMeasurementOp, ops[2])
        assert self._get_pauli_str_from_modifiers_attr(measure_op_0) == "ZZ"
        assert len(measure_op_0.targets) == 2

        measure_op_1 = cast(stim.MultiPauliProductMeasurementOp, ops[3])
        assert self._get_pauli_str_from_modifiers_attr(measure_op_1) == "YX"
        assert measure_op_1.noise is not None
        assert measure_op_1.noise.value.data == 0.42
        assert len(measure_op_1.targets) == 2

    def test_multi_qubit_different_pauli(self) -> None:
        mlir_str = self.outer_mlir_str.format("%m1 = qref.measure<XZ>(%arg0, %arg1) -> i1")
        ops = self._get_ops(mlir_str)
        assert [type(op) for op in ops] == [
            ModuleOp,
            qcore.AllocQubitOp,
            stim.MultiPauliProductMeasurementOp,
        ]
        measure_op = cast(stim.MultiPauliProductMeasurementOp, ops[2])
        assert self._get_pauli_str_from_modifiers_attr(measure_op) == "XZ"
        assert len(measure_op.targets) == 2

    def test_multi_qubit_list_basis(self) -> None:
        mlir_str = self.outer_mlir_str.format(
            "%m0, %m1 = qref.measure<[X, Z]>(%arg0, %arg1) -> i1, i1"
        )
        ops = self._get_ops(mlir_str)
        assert [type(op) for op in ops] == [
            ModuleOp,
            qcore.AllocQubitOp,
            stim.MeasurementGateOp,
            stim.MeasurementGateOp,
        ]
        measure_op_0 = cast(stim.MeasurementGateOp, ops[2])
        assert self._get_pauli_str_from_modifiers_attr(measure_op_0) == "X"

        measure_op_1 = cast(stim.MeasurementGateOp, ops[3])
        assert self._get_pauli_str_from_modifiers_attr(measure_op_1) == "Z"

    def test_copies_stim_tag(self) -> None:
        mlir_str = self.outer_mlir_str.format(
            '%m0 = qref.measure<Y>(%arg0) {stim.tag = "abc"} -> i1\n'
            '%m1, %m2 = qref.measure<[X, Z]>(%arg0, %arg1) {stim.tag = "def"} -> i1, i1'
        )
        ops = self._get_ops(mlir_str)
        assert cast(stim.MeasurementGateOp, ops[2]).attributes.get(TAG_ATTR) == StringAttr("abc")
        # tag should be copied to both new gates
        assert cast(stim.MeasurementGateOp, ops[3]).attributes.get(TAG_ATTR) == StringAttr("def")
        assert cast(stim.MeasurementGateOp, ops[4]).attributes.get(TAG_ATTR) == StringAttr("def")


class TestPauliNoisePattern:
    outer_mlir_str = """%q0, %q1, %q2 = qcore.alloc_qubit
    -> !qcore.qubit, !qcore.qubit, !qcore.qubit
%q0_1, %q1_1, %q2_1 = qstruct.circuit(%q0, %q1, %q2 : !qcore.qubit, !qcore.qubit, !qcore.qubit)
    -> !qcore.qubit, !qcore.qubit, !qcore.qubit {{
^bb0(%arg0 : !qcore.qubit, %arg1 : !qcore.qubit, %arg2 : !qcore.qubit):
    {}
    qstruct.yield %arg0, %arg1, %arg2: !qcore.qubit, !qcore.qubit, !qcore.qubit
}}
"""

    @staticmethod
    def _get_ops(mlir_str: str) -> list[Operation]:
        return get_ops_after_rewrites(mlir_str, [InlineCircuitPattern(), PauliNoisePattern()])

    def test_rank1_depolarizing(self) -> None:
        mlir_str = self.outer_mlir_str.format("qref.pauli_noise<X=0.01, Y=0.01, Z=0.01>(%arg0)")
        ops = self._get_ops(mlir_str)
        assert [type(op) for op in ops] == [ModuleOp, qcore.AllocQubitOp, stim.Depolarize1Op]
        assert cast(stim.Depolarize1Op, ops[-1]).probability.data == pytest.approx(0.03)

    def test_rank1_pauli_channel(self) -> None:
        mlir_str = self.outer_mlir_str.format("qref.pauli_noise<X=0.01, Y=0.02, Z=0.03>(%arg0)")
        ops = self._get_ops(mlir_str)
        assert [type(op) for op in ops] == [ModuleOp, qcore.AllocQubitOp, stim.PauliChannel1Op]
        channel_op = cast(stim.PauliChannel1Op, ops[-1])
        assert channel_op.probability_x.data == pytest.approx(0.01)
        assert channel_op.probability_y.data == pytest.approx(0.02)
        assert channel_op.probability_z.data == pytest.approx(0.03)

    def test_rank2_depolarizing(self) -> None:
        mlir_str = self.outer_mlir_str.format(
            "qref.pauli_noise<IX=0.01, IY=0.01, IZ=0.01, XI=0.01, XX=0.01, XY=0.01, XZ=0.01,"
            " YI=0.01, YX=0.01, YY=0.01, YZ=0.01, ZI=0.01, ZX=0.01, ZY=0.01, ZZ=0.01>(%arg0, %arg1)"
        )
        ops = self._get_ops(mlir_str)
        assert [type(op) for op in ops] == [ModuleOp, qcore.AllocQubitOp, stim.Depolarize2Op]
        assert cast(stim.Depolarize2Op, ops[-1]).probability.data == pytest.approx(0.15)  # 0.01*15

    def test_rank2_pauli_channel(self) -> None:
        mlir_str = self.outer_mlir_str.format(
            "qref.pauli_noise<IZ=0.1, XI=0.2, YI=0.3>(%arg0, %arg1)"
        )
        ops = self._get_ops(mlir_str)
        assert [type(op) for op in ops] == [ModuleOp, qcore.AllocQubitOp, stim.PauliChannel2Op]
        channel_op = cast(stim.PauliChannel2Op, ops[-1])
        assert channel_op.probability_iz.data == pytest.approx(0.1)
        assert channel_op.probability_xi.data == pytest.approx(0.2)
        assert channel_op.probability_yi.data == pytest.approx(0.3)
        assert channel_op.probability_ix.data == pytest.approx(0.0)

    def test_higher_rank_correlated_errors(self) -> None:
        mlir_str = self.outer_mlir_str.format(
            "qref.pauli_noise<IZX=0.1, XIX=0.2, YIX=0.3>(%arg0, %arg1, %arg2)"
        )
        ops = self._get_ops(mlir_str)
        assert [type(op) for op in ops] == [
            ModuleOp,
            qcore.AllocQubitOp,
            stim.CorrelatedErrorOp,
            stim.ElseCorrelatedErrorOp,
            stim.ElseCorrelatedErrorOp,
        ]
        assert cast(stim.CorrelatedErrorOp, ops[2]).probability.data == pytest.approx(0.1)
        assert cast(stim.ElseCorrelatedErrorOp, ops[3]).probability.data == pytest.approx(0.2 / 0.9)
        assert cast(stim.ElseCorrelatedErrorOp, ops[4]).probability.data == pytest.approx(0.3 / 0.7)

    def test_copies_stim_tag_rank1(self) -> None:
        mlir_str = self.outer_mlir_str.format(
            'qref.pauli_noise<X=0.01, Y=0.01, Z=0.01>(%arg0) {stim.tag = "start"}'
        )
        ops = self._get_ops(mlir_str)
        assert cast(stim.Depolarize1Op, ops[-1]).attributes.get(TAG_ATTR) == StringAttr("start")

    def test_copies_stim_tag_rank2(self) -> None:
        mlir_str = self.outer_mlir_str.format(
            "qref.pauli_noise<IX=0.01, IY=0.01, IZ=0.01, XI=0.01, XX=0.01, XY=0.01, XZ=0.01, "
            "YI=0.01, YX=0.01, YY=0.01, YZ=0.01, ZI=0.01, ZX=0.01, ZY=0.01, ZZ=0.01>(%arg0, %arg1)"
            '{stim.tag = "dnf"}'
        )
        ops = self._get_ops(mlir_str)
        assert cast(stim.Depolarize2Op, ops[-1]).attributes.get(TAG_ATTR) == StringAttr("dnf")

    def test_copies_stim_tag_higher_rank(self) -> None:
        mlir_str = self.outer_mlir_str.format(
            'qref.pauli_noise<IZX=0.1, XIX=0.2, YIX=0.3>(%arg0, %arg1, %arg2) {stim.tag = "sob"}'
        )
        ops = self._get_ops(mlir_str)
        # tag should be copied onto all created error ops
        correlated_ops = [
            op for op in ops if isinstance(op, (stim.CorrelatedErrorOp, stim.ElseCorrelatedErrorOp))
        ]
        for op in correlated_ops:
            assert op.attributes.get(TAG_ATTR) == StringAttr("sob")


def test_get_patterns() -> None:
    patterns = get_physical_gate_rewrite_patterns(set())
    assert len(patterns) == 5
    assert all(isinstance(pattern, RewritePattern) for pattern in patterns)
