"""Tests for the QCore (Quantum Core) xDSL dialect"""

import cmath
import itertools
import math
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import AbstractContextManager, nullcontext
from io import StringIO
from typing import Any, Literal

import numpy as np
import pytest
from xdsl.context import Context
from xdsl.dialects import test as t
from xdsl.dialects.builtin import (
    ArrayAttr,
    ComplexType,
    DenseIntOrFPElementsAttr,
    Float32Type,
    Float64Type,
    FloatData,
    IntAttr,
    IntegerType,
    ModuleOp,
    StringAttr,
    TensorType,
    i1,
)
from xdsl.dialects.complex import ComplexNumberAttr
from xdsl.ir import Attribute, OpResult, SSAValue, SSAValues
from xdsl.irdl import AnyInt, IntVarConstraint, isa, opt_operand_def, opt_prop_def
from xdsl.irdl.constraints import AnyAttr, ConstraintContext, EqIntConstraint
from xdsl.irdl.declarative_assembly_format import AttributeVariable
from xdsl.irdl.operations import (
    Block,
    IRDLOperation,
    Operation,
    irdl_op_definition,
    operand_def,
    region_def,
    traits_def,
    var_operand_def,
)
from xdsl.parser import Parser
from xdsl.printer import Printer
from xdsl.rewriter import Rewriter
from xdsl.traits import NoTerminator
from xdsl.utils.exceptions import ParseError, VerifyException

from deltakit_compile.dialects import scf
from deltakit_compile.dialects.qcore import (
    I_STATE_INDEX,
    AllocQubitOp,
    AllocQubitPropsDirective,
    CCXGateAttr,
    CCZGateAttr,
    CHGateAttr,
    ConcatenateOp,
    CXGateAttr,
    CYGateAttr,
    CZGateAttr,
    DecodingSideEffect,
    GateAttribute,
    GateConstraint,
    GateOptionAttr,
    HasCircuitAncestor,
    HasProgramParent,
    HGateAttr,
    IdentityGateAttr,
    IsCircuit,
    IsProgram,
    ISWAPGateAttr,
    NoQuantumEffect,
    NpComplexMatrix,
    PackQubitRegOp,
    PatchQuantumEffect,
    PauliAttr,
    PauliNoiseParametersAttr,
    PauliStringAttr,
    QCore,
    QuantumEffect,
    QuantumEffectInstance,
    QuantumEffectKind,
    QubitCoordinateAttr,
    QubitGateEffect,
    QubitMeasureEffect,
    QubitPauliStateAttr,
    QubitRegType,
    QubitResetEffect,
    QubitType,
    RecursiveQuantumEffect,
    RotationGateAttr,
    SGateAttr,
    SplitOp,
    SqrtXXGateAttr,
    SqrtYYGateAttr,
    SqrtZZGateAttr,
    StandardGateAttribute,
    StateQubitIndex,
    SWAPGateAttr,
    TGateAttr,
    UnitaryGateAttr,
    UnpackQubitRegOp,
    XGateAttr,
    YGateAttr,
    ZGateAttr,
    _GateOption,
    get_quantum_effects,
    has_quantum_effect,
    is_quantum_effect_free,
    is_quantum_state_effect_free,
)


class TestQuantumEffectTraits:
    @irdl_op_definition
    class NoQuantumEffectOp(IRDLOperation):
        """Test op with no quantum effect."""

        name = "test.no_quantum"
        traits = traits_def(NoQuantumEffect())

    @irdl_op_definition
    class QubitResetEffectOp(IRDLOperation):
        """Test op that resets qubits."""

        name = "test.qubit_reset"
        arg = operand_def(AnyAttr())
        traits = traits_def(QubitResetEffect("arg"))

    @irdl_op_definition
    class QubitStateEffectOp(IRDLOperation):
        """Test op that modifies qubit states."""

        name = "test.qubit_state"
        args_name = var_operand_def(AnyAttr())
        traits = traits_def(QubitGateEffect("args_name"))

    @irdl_op_definition
    class QubitMeasureEffectOp(IRDLOperation):
        """Test op that measures qubits."""

        name = "test.qubit_measure"
        arg = opt_operand_def(AnyAttr())
        traits = traits_def(QubitMeasureEffect("arg"))

    @irdl_op_definition
    class PatchQuantumEffectOp(IRDLOperation):
        """Test op that does stuff to patches."""

        name = "test.patch_quantum"
        arg = opt_operand_def(AnyAttr())
        traits = traits_def(PatchQuantumEffect("arg"))

    @irdl_op_definition
    class DecodeSideEffectOp(IRDLOperation):
        """Test op that changes the decoding problem."""

        name = "test.decoding_side_effect"
        arg = opt_operand_def(AnyAttr())
        traits = traits_def(DecodingSideEffect())

    @irdl_op_definition
    class RecursiveQuantumEffectOp(IRDLOperation):
        """Test op that may contain quantum ops."""

        name = "test.recursive_quantum"
        region = region_def()
        traits = traits_def(RecursiveQuantumEffect())

    _qubit_ssa_val = t.TestOp(result_types=[t.TestType("T1")]).res[0]

    @pytest.mark.parametrize(
        ("op", "exp_effects"),
        [
            (NoQuantumEffectOp(), set()),
            (
                QubitResetEffectOp(operands=[_qubit_ssa_val]),
                {QuantumEffectKind.RESET},
            ),
            (
                QubitStateEffectOp(operands=[_qubit_ssa_val]),
                {QuantumEffectKind.STATE_CHANGE},
            ),
            (
                PatchQuantumEffectOp(operands=[_qubit_ssa_val]),
                {QuantumEffectKind.PATCH},
            ),
            (
                QubitMeasureEffectOp(operands=[_qubit_ssa_val]),
                {QuantumEffectKind.MEASURE},
            ),
            (
                QubitMeasureEffectOp(operands=[[]]),
                {},
            ),
            (RecursiveQuantumEffectOp(regions=[[Block()]]), set()),
            (
                RecursiveQuantumEffectOp(
                    regions=[
                        [
                            QubitResetEffectOp(operands=[_qubit_ssa_val]),
                            QubitMeasureEffectOp(operands=[_qubit_ssa_val]),
                        ]
                    ]
                ),
                {QuantumEffectKind.RESET, QuantumEffectKind.MEASURE},
            ),
            (
                RecursiveQuantumEffectOp(
                    regions=[
                        [
                            QubitResetEffectOp(operands=[_qubit_ssa_val]),
                            QubitResetEffectOp(operands=[_qubit_ssa_val]),
                            NoQuantumEffectOp(),
                        ]
                    ]
                ),
                {QuantumEffectKind.RESET},
            ),
        ],
    )
    def test_quantum_operand_effect_traits(
        self, op: Operation, exp_effects: set[QuantumEffectKind]
    ):
        """Test the functionality of each quantum operand effect trait."""
        trait = op.get_traits_of_type(QuantumEffect)[0]  # type: ignore[type-abstract]
        exp_effects_inst = {
            QuantumEffectInstance(e, self._qubit_ssa_val) for e in list(exp_effects)
        }
        assert trait.get_effects(op) == exp_effects_inst
        assert get_quantum_effects(op) == exp_effects_inst

        exp_has_effects = len(exp_effects) != 0
        assert trait.has_effects(op) == exp_has_effects
        assert is_quantum_effect_free(op) == (not exp_has_effects)
        assert is_quantum_state_effect_free(op) == (not exp_has_effects)

    @pytest.mark.parametrize(
        ("op", "exp_effects"),
        [
            (
                DecodeSideEffectOp(operands=[_qubit_ssa_val]),
                {QuantumEffectKind.DECODING},
            ),
            (
                RecursiveQuantumEffectOp(
                    regions=[
                        [
                            DecodeSideEffectOp(operands=[_qubit_ssa_val]),
                            DecodeSideEffectOp(operands=[_qubit_ssa_val]),
                            NoQuantumEffectOp(),
                        ]
                    ]
                ),
                {QuantumEffectKind.DECODING},
            ),
        ],
    )
    def test_quantum_effect_traits(self, op: Operation, exp_effects: set[QuantumEffectKind]):
        """Test the functionality of each quantum effect traits without operands."""
        trait = op.get_traits_of_type(QuantumEffect)[0]  # type: ignore[type-abstract]
        exp_effects_inst = {QuantumEffectInstance(e, None) for e in list(exp_effects)}
        assert trait.get_effects(op) == exp_effects_inst
        assert get_quantum_effects(op) == exp_effects_inst

        exp_has_effects = len(exp_effects) != 0
        assert trait.has_effects(op) == exp_has_effects
        assert is_quantum_effect_free(op) == (not exp_has_effects)
        assert is_quantum_state_effect_free(op)

    @pytest.mark.parametrize(
        "op",
        [
            t.TestOp(),
            RecursiveQuantumEffectOp(
                regions=[
                    [
                        QubitResetEffectOp(operands=[_qubit_ssa_val]),
                        t.TestOp(),
                    ]
                ]
            ),
        ],
    )
    def test_unknown_quantum_effect(self, op: Operation):
        """Test that None is returned whenever the quantum effect of an op is unknown."""
        assert get_quantum_effects(op) is None
        assert not is_quantum_effect_free(op)
        assert not is_quantum_state_effect_free(op)

    def test_has_quantum_effect(self):
        """Test the has_quantum_effect utility."""
        op = TestQuantumEffectTraits.RecursiveQuantumEffectOp(
            regions=[
                [
                    TestQuantumEffectTraits.QubitResetEffectOp(operands=[self._qubit_ssa_val]),
                    TestQuantumEffectTraits.QubitMeasureEffectOp(operands=[self._qubit_ssa_val]),
                ]
            ]
        )
        assert has_quantum_effect(op, QuantumEffectKind.RESET)
        assert not has_quantum_effect(op, QuantumEffectKind.STATE_CHANGE)

    def test_quantum_effect_value(self):
        """Test that the SSAValue affected by a quantum effect can be read."""

        @irdl_op_definition
        class HasEffectValueOp(IRDLOperation):
            """Test op that has a quantum effect with value."""

            name = "test.qubit_state"
            value = operand_def()
            traits = traits_def(QubitGateEffect("value"))

        @irdl_op_definition
        class HasEffectVariadicValueOp(IRDLOperation):
            """Test op that has a quantum effect with variadic value."""

            name = "test.qubit_state"
            value = var_operand_def()
            traits = traits_def(QubitGateEffect("value"))

        value_ssa = t.TestOp(result_types=[IntegerType(64)]).results[0]
        value2_ssa = t.TestOp(result_types=[IntegerType(64)]).results[0]

        opn = HasEffectValueOp(operands=[value_ssa])
        assert get_quantum_effects(opn) == {
            QuantumEffectInstance(QuantumEffectKind.STATE_CHANGE, value_ssa)
        }

        var_opn = HasEffectVariadicValueOp(operands=[[value_ssa, value2_ssa]])
        assert get_quantum_effects(var_opn) == {
            QuantumEffectInstance(QuantumEffectKind.STATE_CHANGE, value_ssa),
            QuantumEffectInstance(QuantumEffectKind.STATE_CHANGE, value2_ssa),
        }

    def test_invalid_quantum_effect_value(
        self,
    ):
        """Test that using an operand name that doesn't exist on the op when defining a quantum
        effect throws an error."""

        @irdl_op_definition
        class InvalidEffectValueOp(IRDLOperation):
            """Test op that has a quantum effect with an unknown operand name."""

            name = "test.qubit_state"
            value = operand_def()
            traits = traits_def(QubitGateEffect("steve"))

        value_ssa = t.TestOp(result_types=[IntegerType(64)]).results[0]
        opn = InvalidEffectValueOp(operands=[value_ssa])
        with pytest.raises(
            VerifyException, match="test\\.qubit_state doesn't have operand 'steve'"
        ):
            opn.verify()


class TestCircuitTraits:
    @irdl_op_definition
    class CircuitOp(IRDLOperation):
        """Test circuit op."""

        name = "test.circuit"
        body = region_def("single_block")
        traits = traits_def(IsCircuit(), NoTerminator())

    @irdl_op_definition
    class PhysicalGateOp(IRDLOperation):
        """Test op that can only exist inside a circuit op."""

        name = "test.physical_gate"
        traits = traits_def(HasCircuitAncestor())

    def test_is_circuit_verifies_no_scf_ops(self) -> None:
        """Test the verification of IsCircuit does not allow it to contain scf ops."""
        cond = t.TestOp(result_types=[i1]).results[0]
        opn = TestCircuitTraits.CircuitOp(regions=[[scf.IfOp(cond, [], [scf.YieldOp()])]])
        with pytest.raises(
            VerifyException,
            match=re.escape(
                "A circuit op (an op with the IsCircuit trait) may not contain "
                "control flow op 'scf.if'"
            ),
        ):
            opn.verify()

    def test_is_circuit_verifies_no_inner_circuits(self) -> None:
        """Test the verification of IsCircuit does not allow it to contain other circuit ops."""
        opn = TestCircuitTraits.CircuitOp(
            regions=[[TestCircuitTraits.CircuitOp(regions=[[Block()]])]]
        )
        with pytest.raises(
            VerifyException,
            match=re.escape(
                r"A circuit op (an op with the IsCircuit trait) may not contain "
                "another circuit op: 'test.circuit'"
            ),
        ):
            opn.verify()

    def test_has_circuit_ancestor_verify(self) -> None:
        """Test the verification of HasCircuitAncestor."""
        # No parent, this is allowed.
        opn = TestCircuitTraits.PhysicalGateOp()
        opn.verify()

        # Non-circuit parent
        parent = t.TestOp(regions=[[opn, t.TestTermOp()]])
        with pytest.raises(
            VerifyException,
            match=r"Op must be inside a circuit \(an op with the IsCircuit trait\).",
        ):
            parent.verify()

        # Circuit ancestor
        circ = TestCircuitTraits.CircuitOp(regions=[[parent]])
        circ.verify()

    def test_get_and_has_circuit_ancestor(self) -> None:
        """Test IsCircuit.get_circuit_ancestor and IsCircuit.has_circuit_ancestor."""
        # No parent
        opn = TestCircuitTraits.PhysicalGateOp()
        assert HasCircuitAncestor.get_circuit_ancestor(opn) is None
        assert not HasCircuitAncestor.has_circuit_ancestor(opn)

        # Non-circuit parent
        parent = t.TestOp(regions=[[opn, t.TestTermOp()]])
        assert HasCircuitAncestor.get_circuit_ancestor(opn) is None
        assert not HasCircuitAncestor.has_circuit_ancestor(opn)

        # Circuit ancestor
        circ = TestCircuitTraits.CircuitOp(regions=[[parent]])
        assert HasCircuitAncestor.get_circuit_ancestor(opn) == circ
        assert HasCircuitAncestor.has_circuit_ancestor(opn)

        # Also applies to the circuit itself
        assert HasCircuitAncestor.get_circuit_ancestor(circ) == circ
        assert HasCircuitAncestor.has_circuit_ancestor(circ)


class TestProgramTraits:
    @irdl_op_definition
    class ProgramOp(IRDLOperation):
        """Test program op."""

        name = "test.program"
        body = region_def("single_block")
        traits = traits_def(IsProgram(), NoTerminator())

    @irdl_op_definition
    class ProgramInstructionOp(IRDLOperation):
        """Test op that can only exist inside a program op."""

        name = "test.program_instruction"
        traits = traits_def(HasProgramParent())

    def test_is_program_verifies_module_parent(self) -> None:
        """Test the verification of IsProgram allows a module as the direct parent."""
        ModuleOp([TestProgramTraits.ProgramOp(regions=[[Block()]])]).verify()

    def test_is_program_verifies_detached_op(self) -> None:
        """Test that IsProgram allows a detached op with no parent at all."""
        opn = TestProgramTraits.ProgramOp(regions=[[Block()]])
        assert opn.parent_op() is None
        opn.verify()

    def test_is_program_verifies_non_module_non_program_parent_allowed(self) -> None:
        """Test that IsProgram allows a parent that is neither a module nor a program op."""
        opn = TestProgramTraits.ProgramOp(regions=[[Block()]])
        parent = t.TestOp(regions=[[opn, t.TestTermOp()]])
        parent.verify()

    def test_is_program_verifies_no_direct_nested_program(self) -> None:
        """Test that IsProgram does not allow being a direct child of another program op."""
        inner = TestProgramTraits.ProgramOp(regions=[[Block()]])
        outer = TestProgramTraits.ProgramOp(regions=[[inner]])
        with pytest.raises(
            VerifyException,
            match=re.escape(
                "A program op (an op with the IsProgram trait) must be the root of its "
                "program: it cannot be nested inside another program op."
            ),
        ):
            outer.verify()

    def test_is_program_verifies_no_indirect_nested_program(self) -> None:
        """Test that IsProgram does not allow being nested inside another program op via an
        intermediate non-program op."""
        inner = TestProgramTraits.ProgramOp(regions=[[Block()]])
        intermediate = t.TestOp(regions=[[inner, t.TestTermOp()]])
        outer = TestProgramTraits.ProgramOp(regions=[[intermediate]])
        with pytest.raises(
            VerifyException,
            match=re.escape(
                "A program op (an op with the IsProgram trait) must be the root of its "
                "program: it cannot be nested inside another program op."
            ),
        ):
            outer.verify()

    def test_has_program_parent_verify(self) -> None:
        """Test the verification of HasProgramParent."""
        # No parent, this is allowed.
        opn = TestProgramTraits.ProgramInstructionOp()
        opn.verify()

        # Non-program parent
        parent = t.TestOp(regions=[[opn, t.TestTermOp()]])
        with pytest.raises(
            VerifyException,
            match=r"Op must be a direct child of a program \(an op with the IsProgram trait\).",
        ):
            parent.verify()

        # Direct program parent
        opn2 = TestProgramTraits.ProgramInstructionOp()
        prog = TestProgramTraits.ProgramOp(regions=[[opn2]])
        ModuleOp([prog]).verify()

    def test_get_and_has_program_parent(self) -> None:
        """Test HasProgramParent.get_program_parent and HasProgramParent.has_program_parent."""
        # No parent
        opn = TestProgramTraits.ProgramInstructionOp()
        assert HasProgramParent.get_program_parent(opn) is None
        assert not HasProgramParent.has_program_parent(opn)

        # Non-program parent
        opn2 = TestProgramTraits.ProgramInstructionOp()
        t.TestOp(regions=[[opn2, t.TestTermOp()]])
        assert HasProgramParent.get_program_parent(opn2) is None
        assert not HasProgramParent.has_program_parent(opn2)

        # Direct program parent
        opn3 = TestProgramTraits.ProgramInstructionOp()
        prog = TestProgramTraits.ProgramOp(regions=[[opn3]])
        assert HasProgramParent.get_program_parent(opn3) == prog
        assert HasProgramParent.has_program_parent(opn3)

        # Program has no parent of its own here, so this does not apply to it.
        assert HasProgramParent.get_program_parent(prog) is None
        assert not HasProgramParent.has_program_parent(prog)

    def test_module_is_implicitly_a_program(self) -> None:
        """Test that a module counts as a program, even without the IsProgram trait."""
        opn = TestProgramTraits.ProgramInstructionOp()
        mod = ModuleOp([opn])
        mod.verify()

        assert IsProgram.is_program(mod)
        assert HasProgramParent.get_program_parent(opn) == mod
        assert HasProgramParent.has_program_parent(opn)


class TestAttributes:
    @pytest.mark.parametrize(
        ("literal", "as_str"),
        [
            ("Z", "#qcore.pauli<Z>"),
            ("X", "#qcore.pauli<X>"),
            ("Y", "#qcore.pauli<Y>"),
        ],
    )
    def test_pauli_attr(
        self,
        literal: Literal["X", "Y", "Z"],
        as_str: str,
        xdsl_context: Context,
    ):
        """Test init and methods of PauliAttr"""
        pauli = PauliAttr(literal)
        assert not literal or pauli == PauliAttr(literal)
        assert pauli == PauliAttr.coerce(pauli)
        assert pauli == PauliAttr.coerce(literal)

        str_val = StringIO()
        printer = Printer(stream=str_val)
        printer.print_attribute(pauli)
        assert str_val.getvalue() == as_str

        parser = Parser(xdsl_context, str_val.getvalue())
        attr = parser.parse_attribute()
        assert attr == pauli

    def test_pauli_attr_xyz(self):
        """Test the PauliAttr X() Y() Z() methods"""
        x = PauliAttr.X()
        y = PauliAttr.Y()
        z = PauliAttr.Z()

        assert x == PauliAttr("X")
        assert y == PauliAttr("Y")
        assert z == PauliAttr("Z")

        assert x not in (y, z)
        assert y not in (x, z)
        assert z not in (x, y)

        assert len({x, y, z, z, x, y}) == 3

    @pytest.mark.parametrize(
        ("p1", "p2", "expected_product"),
        [
            ("X", "X", None),
            ("Y", "Y", None),
            ("Z", "Z", None),
            ("X", "Y", PauliAttr("Z")),
            ("X", "Z", PauliAttr("Y")),
            ("Y", "X", PauliAttr("Z")),
            ("Y", "Z", PauliAttr("X")),
            ("Z", "X", PauliAttr("Y")),
            ("Z", "Y", PauliAttr("X")),
        ],
    )
    def test_pauli_attr_mul(self, p1, p2, expected_product):
        """Test the PauliAttr multiplication method."""
        assert PauliAttr(p1) * PauliAttr(p2) == expected_product

    @pytest.mark.parametrize(("pauli", "expected_result"), [("X", "Z"), ("Y", "Y"), ("Z", "X")])
    def test_pauli_attr_flipped(self, pauli, expected_result):
        """Test the PauliAttr multiplication method."""
        assert PauliAttr(pauli).flipped() == PauliAttr(expected_result)

    def test_pauli_string_parse_error(self):
        """Tests the parse error generated when t parsing malformed pauli-strings"""
        parser = Parser(Context(), "Hello")
        with pytest.raises(
            ParseError,
            match=re.escape(
                "Expected a PauliString (that only contains X, Y, or Z, characters) "
                "but got 'Hello'."
            ),
        ):
            PauliAttr.parse_optional_pauli_string(parser)
        parser = Parser(Context(), "XXXXx")
        with pytest.raises(
            ParseError,
            match=re.escape(
                "Expected a PauliString (that only contains X, Y, or Z, characters) "
                "but got 'XXXXx'."
            ),
        ):
            PauliAttr.parse_optional_pauli_string(parser)

    @pytest.mark.parametrize(
        ("attr", "res"), [(PauliAttr.X(), "X"), (PauliAttr.Y(), "Y"), (PauliAttr.Z(), "Z")]
    )
    def test_pauli_attr_to_string(self, attr: PauliAttr, res: str) -> None:
        assert attr.to_string() == res

    @pytest.mark.parametrize(
        "input_ir",
        [
            "",
            "XYZ",
            "XYZXYYXYXYX",
            "XXXXXXXXXXXXXXXXXX",
            "Y",
            "Z",
        ],
    )
    def test_pauli_string_round_trip(self, input_ir: str):
        """Tests that we can parse and print strings of PauliAttrs."""
        parser = Parser(Context(), input_ir)
        attr = PauliAttr.parse_optional_pauli_string(parser)
        str_io = StringIO()
        printer = Printer(stream=str_io)
        if attr is not None:
            assert isa(attr, ArrayAttr[PauliAttr])
            PauliAttr.print_pauli_string(attr, printer)
        assert input_ir == str_io.getvalue()

    @pytest.mark.parametrize(
        ("string", "expected_valid"),
        [
            ("", True),
            ("XYZ", True),
            ("XYZXYYXYXYX", True),
            ("XXXXXXXXXXXXXXXXXX", True),
            ("x", False),
            ("W", False),
            ("'", False),
            ("Γ", False),
            ("XXZZχ", False),
            ("Χ", False),  # noqa: RUF001
        ],
    )
    def test_is_valid_pauli_string(self, string: str, expected_valid: bool):
        if expected_valid:
            assert PauliAttr.is_valid_pauli_string(string)
        else:
            assert not PauliAttr.is_valid_pauli_string(string)

    def test_qubit_state_parse_error(self):
        """Test that parsing a qubit state produces expected errors."""
        parser = Parser(Context(), "<I>")
        with pytest.raises(
            ParseError,
            match=re.escape("Expected qcore.pauli_state in the form (X|Y|Z)([0-9]+), got 'I'"),
        ):
            QubitPauliStateAttr.parse_parameters(parser)

    @pytest.mark.parametrize(
        ("pauli_string", "error_msg"),
        [
            (
                PauliStringAttr.new(
                    [
                        ArrayAttr([QubitPauliStateAttr.new([PauliAttr.X(), IntAttr(10)])]),
                        IntAttr(11),
                    ]
                ),
                re.escape("integer 5 expected from int variable 'Q', but got 11"),
            ),
        ],
    )
    def test_pauli_string_constr_verify(self, pauli_string: PauliStringAttr, error_msg: str):
        """Test that PauliStringAttr.constr produces expected errors."""
        n_qubits = IntVarConstraint("Q", AnyInt())
        constraint_context = ConstraintContext()
        constraint_context.set_int_variable(n_qubits.name, 5)
        with pytest.raises(
            VerifyException,
            match=error_msg,
        ):
            PauliStringAttr.constr(n_qubits).verify(pauli_string, constraint_context)

    @pytest.mark.parametrize(
        ("args", "kwargs", "cls", "exp_attr"),
        [
            (
                ("Z", 0),
                {},
                QubitPauliStateAttr,
                QubitPauliStateAttr.new([PauliAttr.Z(), IntAttr(0)]),
            ),
            (
                (PauliAttr.Y(), 1),
                {},
                QubitPauliStateAttr,
                QubitPauliStateAttr.new([PauliAttr.Y(), IntAttr(1)]),
            ),
            (
                ("X",),
                {"index": 4},
                QubitPauliStateAttr,
                QubitPauliStateAttr.new([PauliAttr.X(), IntAttr(4)]),
            ),
            (
                (),
                {"pauli_state": "X", "index": 2},
                QubitPauliStateAttr,
                QubitPauliStateAttr.new([PauliAttr.X(), IntAttr(2)]),
            ),
        ],
    )
    def test_qubit_state_attr_init(self, args, kwargs, cls, exp_attr):
        """Test that the QubitPauliStateAttr init method works correctly."""
        attr = cls(*args, **kwargs)
        assert attr == exp_attr

    @pytest.mark.parametrize(
        ("args", "kwargs", "cls", "exp_attr"),
        [
            (
                ([(PauliAttr.Y(), 1)], 2),
                {},
                PauliStringAttr,
                PauliStringAttr.new(
                    [ArrayAttr([QubitPauliStateAttr.new([PauliAttr.Y(), IntAttr(1)])]), IntAttr(2)]
                ),
            ),
            (
                (
                    [
                        (PauliAttr.Y(), 1),
                        QubitPauliStateAttr.new([PauliAttr.X(), IntAttr(0)]),
                    ],
                    2,
                ),
                {},
                PauliStringAttr,
                PauliStringAttr.new(
                    [
                        ArrayAttr(
                            [
                                QubitPauliStateAttr.new([PauliAttr.X(), IntAttr(0)]),
                                QubitPauliStateAttr.new([PauliAttr.Y(), IntAttr(1)]),
                            ]
                        ),
                        IntAttr(2),
                    ]
                ),
            ),
            (
                (
                    ArrayAttr(
                        [
                            QubitPauliStateAttr.new([PauliAttr.X(), IntAttr(3)]),
                            QubitPauliStateAttr.new([PauliAttr.Z(), IntAttr(0)]),
                        ]
                    ),
                    IntAttr(4),
                ),
                {},
                PauliStringAttr,
                PauliStringAttr.new(
                    [
                        ArrayAttr(
                            [
                                QubitPauliStateAttr.new([PauliAttr.Z(), IntAttr(0)]),
                                QubitPauliStateAttr.new([PauliAttr.X(), IntAttr(3)]),
                            ]
                        ),
                        IntAttr(4),
                    ]
                ),
            ),
            (
                (),
                {"qubit_states": [("X", 1), ("X", 2), ("Z", 4)], "length": 5},
                PauliStringAttr,
                PauliStringAttr.new(
                    [
                        ArrayAttr(
                            [
                                QubitPauliStateAttr.new([PauliAttr.X(), IntAttr(1)]),
                                QubitPauliStateAttr.new([PauliAttr.X(), IntAttr(2)]),
                                QubitPauliStateAttr.new([PauliAttr.Z(), IntAttr(4)]),
                            ]
                        ),
                        IntAttr(5),
                    ]
                ),
            ),
        ],
    )
    def test_pauli_string_attr_init(self, args, kwargs, cls, exp_attr):
        """Test that the PauliStringAttr init method works correctly."""
        attr = cls(*args, **kwargs)
        assert attr == exp_attr

    @pytest.mark.parametrize("pauli", ["X", "Y", "Z"])
    def test_pauli_string_repeat(self, pauli):
        """Test that PauliStringAttr.repeat produces repeated Pauli strings."""
        assert PauliStringAttr.repeat(pauli, 3) == PauliStringAttr(
            [(pauli, 0), (pauli, 1), (pauli, 2)], 3
        )

    @pytest.mark.parametrize(
        ("pauli_init", "length", "expected"),
        [
            ([("X", 0), ("Y", 1), ("Z", 2)], 3, [PauliAttr.X(), PauliAttr.Y(), PauliAttr.Z()]),
            ([("X", 0), ("Y", 2)], 3, [PauliAttr.X(), None, PauliAttr.Y()]),
            ([], 1, [None]),
            ([], 5, [None] * 5),
            ([("X", 5)], 6, [None, None, None, None, None, PauliAttr.X()]),
        ],
    )
    def test_pauli_string_iter(self, pauli_init, length, expected):
        """Test that PauliStringAttr __iter__ method works correctly."""
        pauli_string = PauliStringAttr(pauli_init, length)
        iterated = list(pauli_string)
        assert iterated == expected

    @pytest.mark.parametrize(
        ("a_states", "b_states", "expected"),
        [
            (
                [("X", 0)],
                [("X", 0)],
                True,
            ),
            (
                [("X", 0)],
                [("Z", 0)],
                False,
            ),
            (
                [("X", 0), ("Z", 1)],
                [("Y", 1)],
                False,
            ),
            (
                [("X", 0), ("X", 1)],
                [("Z", 0), ("Z", 1)],
                True,
            ),
            (
                [("X", 0), ("Z", 2)],
                [("Y", 1)],
                True,
            ),
            (
                [("X", 0), ("X", 2), ("X", 4)],
                [("Z", 0), ("Z", 1), ("Z", 2), ("Z", 3), ("Z", 4)],
                False,
            ),
        ],
    )
    def test_pauli_string_commute(self, a_states, b_states, expected):
        """Test that PauliStringAttr.commutes works correctly."""
        state_a = PauliStringAttr(a_states, 5)
        state_b = PauliStringAttr(b_states, 5)
        assert state_a.commutes(state_b) == expected
        assert state_b.commutes(state_a) == expected

    @pytest.mark.parametrize(
        ("a_states", "b_states", "expected"),
        [
            ([("X", 0)], [("X", 0)], []),
            ([("X", 0)], [("Y", 0)], [("Z", 0)]),
            ([("X", 0)], [("Y", 1)], [("X", 0), ("Y", 1)]),
            ([("X", 0), ("Y", 1)], [("X", 1), ("Z", 2)], [("X", 0), ("Z", 1), ("Z", 2)]),
        ],
    )
    def test_pauli_string_multiplication(self, a_states, b_states, expected):
        """Test that PauliStringAttr __mul__ operation works correctly."""
        first = PauliStringAttr(a_states, 3)
        second = PauliStringAttr(b_states, 3)
        prod = first * second
        prod.verify()
        assert prod == PauliStringAttr(expected, 3)

    def test_mismatched_pauli_string_length(self):
        """Test that PauliStringAttr throws an error in an interaction between two strings that
        are of incompatible lengths."""
        state_a = PauliStringAttr.identity(5)
        state_b = PauliStringAttr.identity(6)
        with pytest.raises(
            ValueError,
            match=re.escape(
                "Cannot check whether Pauli strings of differing lengths commute (5 != 6)"
            ),
        ):
            state_a.commutes(state_b)
        with pytest.raises(
            ValueError,
            match=re.escape("Cannot multiply Pauli strings of differing lengths (5 != 6)"),
        ):
            state_a * state_b

    @pytest.mark.parametrize(
        ("states", "expected_weight"),
        [
            ([], 0),
            ([("Z", 2)], 1),
            ([("X", 0), ("X", 1), ("X", 5)], 3),
            ([("Y", 0), ("Y", 1), ("Z", 3), ("X", 4)], 4),
        ],
    )
    def test_pauli_string_weight(self, states, expected_weight):
        """Test that PauliStringAttr.get_weight returns the number of non-identity Paulis.

        E.g.:
        - [] -> 0
        - X0 X1 X5 -> 3
        """
        assert PauliStringAttr(states, 10).get_weight() == expected_weight

    def test_pauli_string_is_identity(self):
        """Test that PauliStringAttr.is_identity() returns whether whether all Paulis are
        identity."""
        assert PauliStringAttr([], 10).is_identity()
        assert not PauliStringAttr([("X", 0)], 1).is_identity()
        assert not PauliStringAttr([("Y", 1), ("Z", 3), ("X", 4)], 5).is_identity()

    def test_pauli_string_identity(self):
        """Test that PauliStringAttr.identity() returns the identity Pauli string."""
        assert PauliStringAttr.identity(2) == PauliStringAttr([], 2)
        assert PauliStringAttr.identity(2).is_identity()

    def test_pauli_string_resize(self):
        """Test resizing a Pauli string without changing its qubit indices."""
        pauli_string = PauliStringAttr([("X", 0), ("Z", 2)], 4)

        assert pauli_string.resize(6) == PauliStringAttr([("X", 0), ("Z", 2)], 6)
        assert pauli_string.resize(3) == PauliStringAttr([("X", 0), ("Z", 2)], 3)

    @pytest.mark.parametrize(
        ("new_length", "message"),
        [
            (0, "A Pauli string must be on at least 1 qubit."),
            (2, "Cannot resize Pauli string to length 2 because it uses qubit index 2."),
        ],
    )
    def test_pauli_string_resize_invalid(self, new_length: int, message: str):
        """Test that resizing rejects invalid lengths and truncated non-identity support."""
        pauli_string = PauliStringAttr([("Z", 2)], 4)

        with pytest.raises(ValueError, match=re.escape(message)):
            pauli_string.resize(new_length)

    @pytest.mark.parametrize(
        ("pauli", "expected_result"),
        [
            ((("X", 1), ("Z", 4), ("Y", 5), 6), (("Z", 1), ("X", 4), ("Y", 5), 6)),
            ((("X", 1), 19), (("Z", 1), 19)),
        ],
    )
    def test_pauli_string_flipped(self, pauli, expected_result):
        """Test that Pauli strings are correctly flipped."""
        *paulis, length = pauli
        *epaulis, elength = expected_result
        assert PauliStringAttr(paulis, length).flipped() == PauliStringAttr(epaulis, elength)

    def test_pauli_string_permute_indices(self):
        """PauliStringAttr.permute_indices should remap qubit indices and preserve canonical
        sort."""

        pauli_string = PauliStringAttr([("Z", 2), ("X", 0)], 3)
        # Ensure non-trivial permutation and that output is sorted by index.
        permuted = pauli_string.permute_indices([2, 1, 0])
        assert permuted == PauliStringAttr([("Z", 0), ("X", 2)], 3)

    @pytest.mark.parametrize(
        ("pstring", "mapping", "length", "expected_result"),
        [
            (PauliStringAttr([("X", 0)], 1), {0: 0, 1: 1}, None, PauliStringAttr([("X", 0)], 1)),
            (PauliStringAttr([("X", 0)], 1), {0: 0, 1: 1}, 1, PauliStringAttr([("X", 0)], 1)),
            (PauliStringAttr([("X", 0)], 4), {0: 0, 1: 1}, None, PauliStringAttr([("X", 0)], 4)),
            (
                PauliStringAttr([("X", 0)], 1),
                {0: 4, 1: 1, 2: 0},
                None,
                PauliStringAttr([("X", 4)], 5),
            ),
            (
                PauliStringAttr([("X", 0), ("Z", 4)], 10),
                {i: (i + 1) % 10 for i in range(10)},
                None,
                PauliStringAttr([("X", 1), ("Z", 5)], 10),
            ),
        ],
    )
    def test_pauli_string_map_indices(
        self,
        pstring: PauliStringAttr,
        mapping: Mapping[int, int],
        length: int | None,
        expected_result: PauliStringAttr,
    ) -> None:
        assert pstring.map_indices(mapping, length) == expected_result

    @pytest.mark.parametrize(
        ("pauli_string", "expected"),
        [
            (PauliStringAttr.identity(3), I_STATE_INDEX),
            (PauliStringAttr([("X", 0)], 1), 0),
            (PauliStringAttr([("Z", 3), ("X", 10)], 11), 3),
            # Order should not matter in construction; PauliStringAttr canonicalises internally.
            (PauliStringAttr([("X", 7), ("Y", 2), ("Z", 5)], 10), 2),
        ],
    )
    def test_pauli_string_get_min_qubit_index_parametrized(
        self, pauli_string: PauliStringAttr, expected: int
    ) -> None:
        assert pauli_string.get_min_qubit_index() == expected

    @pytest.mark.parametrize(
        ("pauli_string", "indices", "expected_local_pauli_string"),
        [
            (PauliStringAttr.identity(2), [0, 1], PauliStringAttr.identity(2)),
            (PauliStringAttr([("X", 0)], 1), [0], PauliStringAttr([("X", 0)], 1)),
            (
                PauliStringAttr([("X", 0), ("Z", 2)], 3),
                [0, 2],
                PauliStringAttr([("X", 0), ("Z", 1)], 2),
            ),
            (
                PauliStringAttr([("X", 0), ("Z", 2)], 3),
                [2, 0],
                PauliStringAttr([("Z", 0), ("X", 1)], 2),
            ),
            (
                PauliStringAttr([("X", 0), ("Y", 1), ("Z", 2)], 3),
                [2, 0],
                PauliStringAttr([("Z", 0), ("X", 1)], 2),
            ),
        ],
    )
    def test_pauli_string_get_local_pauli_string(
        self,
        pauli_string: PauliStringAttr,
        indices: list[StateQubitIndex],
        expected_local_pauli_string: PauliStringAttr,
    ) -> None:
        local_string = pauli_string.get_local_pauli_string(indices)
        local_string.verify()
        assert local_string == expected_local_pauli_string

    def test_pauli_string_get_local_pauli_string_invalid(self) -> None:
        pauli_string = PauliStringAttr([("X", 0), ("Z", 2)], 3)
        with pytest.raises(
            ValueError,
            match=re.escape(
                "Cannot create a local Pauli string longer than its origin Pauli string."
            ),
        ):
            pauli_string.get_local_pauli_string([0, 1, 2, 0])
        with pytest.raises(
            ValueError,
            match=re.escape(
                "Cannot create a local Pauli string using indices of qubits beyond the length "
                "of the origin Pauli string."
            ),
        ):
            pauli_string.get_local_pauli_string([3])

    @pytest.mark.parametrize(
        ("pauli_string", "local_pauli_string", "indices", "expected"),
        [
            (
                PauliStringAttr.identity(1),
                PauliStringAttr.identity(1),
                [],
                PauliStringAttr.identity(1),
            ),
            (
                PauliStringAttr.identity(12),
                PauliStringAttr.identity(4),
                [4, 2, 10, 11],
                PauliStringAttr.identity(12),
            ),
            (
                PauliStringAttr.identity(1),
                PauliStringAttr([("X", 0)], 1),
                [0],
                PauliStringAttr([("X", 0)], 1),
            ),
            (
                PauliStringAttr.identity(6),
                PauliStringAttr([("X", 0)], 1),
                [5],
                PauliStringAttr([("X", 5)], 6),
            ),
            (
                PauliStringAttr.identity(4),
                PauliStringAttr([("X", 0), ("Z", 2)], 3),
                [3, 1, 2],
                PauliStringAttr([("Z", 2), ("X", 3)], 4),
            ),
            (
                PauliStringAttr([("X", 0), ("Y", 1), ("Z", 2)], 3),
                PauliStringAttr([("Y", 0), ("Z", 1)], 2),
                [2, 0],
                PauliStringAttr([("Z", 0), ("Y", 1), ("Y", 2)], 3),
            ),
            # also overwrites even when the local Pauli string is I at the given index
            (
                PauliStringAttr([("X", 0), ("Y", 1), ("Z", 2)], 3),
                PauliStringAttr.identity(3),
                [0, 1, 2],
                PauliStringAttr.identity(3),
            ),
            (
                PauliStringAttr([("X", 0), ("Y", 1), ("Z", 2)], 3),
                PauliStringAttr([("X", 0)], 2),
                [1, 0],
                PauliStringAttr([("X", 1), ("Z", 2)], 3),
            ),
        ],
    )
    def test_pauli_string_with_updated_local_pauli_string(
        self,
        pauli_string: PauliStringAttr,
        local_pauli_string: PauliStringAttr,
        indices: list[StateQubitIndex],
        expected: PauliStringAttr,
    ) -> None:
        updated = pauli_string.with_updated_local_pauli_string(local_pauli_string, indices)
        updated.verify()
        assert updated == expected

    def test_pauli_string_with_updated_local_pauli_string_invalid_indices(self) -> None:
        """Test that PauliStringAttr.with_updated_local_pauli_string errors if the local Pauli
        string has too many non-identity Pauils for the number of indices given."""
        pauli_string = PauliStringAttr.identity(1)
        local_pauli_string = PauliStringAttr([("X", 0), ("Z", 2)], 3)
        indices = [1]  # Not enough indices for the 2 non-identity Paulis in local_pauli_string.

        with pytest.raises(
            ValueError,
            match=re.escape(
                "The Pauli string #qcore.pauli_string<X0 Z2 : 3> is not local to the indices [1]."
            ),
        ):
            pauli_string.with_updated_local_pauli_string(local_pauli_string, indices)

    @pytest.mark.parametrize(
        ("pauli_string", "shift", "expected"),
        [
            (PauliStringAttr.identity(1), 0, PauliStringAttr.identity(1)),
            (PauliStringAttr.identity(6), 5, PauliStringAttr.identity(6)),
            (PauliStringAttr([("X", 0)], 1), 0, PauliStringAttr([("X", 0)], 1)),
            (PauliStringAttr([("X", 0)], 6), 5, PauliStringAttr([("X", 5)], 6)),
            (
                PauliStringAttr([("X", 0), ("Z", 2)], 10),
                5,
                PauliStringAttr([("X", 5), ("Z", 7)], 10),
            ),
            (
                PauliStringAttr([("Z", 3), ("X", 10)], 11),
                -3,
                PauliStringAttr([("Z", 0), ("X", 7)], 11),
            ),
        ],
    )
    def test_pauli_string_shift_qubit_indices_parametrized(
        self, pauli_string: PauliStringAttr, shift: int, expected: PauliStringAttr
    ) -> None:
        assert pauli_string.shift_qubit_indices(shift) == expected

    def test_pauli_string_shift_new_length(self):
        pauli_string = PauliStringAttr([("X", 0)], 2)
        assert pauli_string.shift_qubit_indices(3, new_length=4) == PauliStringAttr([("X", 3)], 4)

    @pytest.mark.parametrize(
        ("pauli_string", "shift"),
        [
            (PauliStringAttr([("X", 0)], 1), -1),
            (PauliStringAttr([("Z", 2)], 3), -3),
            (PauliStringAttr([("X", 1), ("Z", 4)], 5), -2),  # would make X-1
        ],
    )
    def test_pauli_string_shift_qubit_indices_negative_shift_raises(
        self, pauli_string: PauliStringAttr, shift: int
    ) -> None:
        msg = "The shift given would produce qubit states with negative indices."
        with pytest.raises(ValueError, match=msg):
            _ = pauli_string.shift_qubit_indices(shift)

    def test_pauli_string_shift_beyond_max_raises(self):
        pauli_string = PauliStringAttr([("X", 0)], 2)
        with pytest.raises(
            ValueError,
            match=re.escape(
                "The shift given would produces qubit states with indices "
                "greater than the length of the Pauli string."
            ),
        ):
            _ = pauli_string.shift_qubit_indices(3)

    @pytest.mark.parametrize(
        ("pauli_strings", "expected"),
        [
            # Empty collection
            ([], "[]"),
            # Single identity Pauli string
            ([PauliStringAttr.identity(3)], "[I]"),
            # Single non-identity Pauli string
            ([PauliStringAttr([("X", 0)], 3)], "[X0]"),
            # Multiple Pauli strings - should be sorted by sort_key
            (
                [
                    PauliStringAttr([("X", 0), ("Z", 1)], 3),
                    PauliStringAttr([("Y", 2)], 3),
                    PauliStringAttr([("X", 0)], 3),
                ],
                "[X0 Z1, X0, Y2]",
            ),
            # Test that order is normalized (sorted) - same as above but in different order
            (
                [
                    PauliStringAttr([("Y", 2)], 3),
                    PauliStringAttr([("X", 0), ("Z", 1)], 3),
                    PauliStringAttr([("X", 0)], 3),
                ],
                "[X0 Z1, X0, Y2]",
            ),
            # Longer Pauli strings
            (
                [
                    PauliStringAttr([("X", 0), ("Y", 5), ("Z", 10)], 15),
                    PauliStringAttr([("Z", 0)], 15),
                ],
                "[X0 Y5 Z10, Z0]",
            ),
        ],
    )
    def test_pauli_string_collection_as_str(
        self, pauli_strings: list[PauliStringAttr], expected: str
    ):
        """Test that PauliStringAttr.collection_as_str() returns a formatted string
        representation of a collection of Pauli strings."""
        assert PauliStringAttr.collection_as_str(pauli_strings) == expected

    @pytest.mark.parametrize("numbers", [(1,), (1, -2, 3), [0.000001, 0.1111111, 2**64]])
    def test_qubit_coordinate_attr(self, numbers: Sequence[float]):
        """Test the QubitCoordinateAttr correctly stores coordinate values, and its helpers work."""
        coords = QubitCoordinateAttr(numbers)
        assert coords.data == tuple(numbers)
        assert len(coords) == len(list(numbers))
        assert tuple(coords) == coords.values.data
        assert [v.value.data for v in coords] == list(coords.data)
        assert all(v.type == Float64Type() for v in coords)

    def test_alloc_qubit_props(self):
        """Test that AllocQubitPropsDirective correctly identifies itself as an optional
        and anchorable directive, and checks if coords_attr_var and ids_attr_var are present"""
        coords_attr_var = AttributeVariable("coords_prop", True, True, None)
        ids_attr_var = AttributeVariable("ids_prop", True, True, None)
        assert AllocQubitPropsDirective(coords_attr_var, ids_attr_var).is_optional_like()
        assert AllocQubitPropsDirective(coords_attr_var, ids_attr_var).is_anchorable()

    @pytest.mark.parametrize(
        ("input_str", "expectation"),
        [
            ("test.coords_and_ids_op", nullcontext("test.coords_and_ids_op ")),
            ("test.coords_and_ids_op coords=[]", nullcontext("test.coords_and_ids_op coords = []")),
            ("test.coords_and_ids_op {}", nullcontext("test.coords_and_ids_op ")),
            (
                "test.coords_and_ids_op coords=[] {}",
                nullcontext("test.coords_and_ids_op coords = []"),
            ),
            (
                "test.coords_and_ids_op coords=[(0,0.1), (1,2)]",
                nullcontext("test.coords_and_ids_op coords = [(0.0, 0.1), (1.0, 2.0)]"),
            ),
            (
                "test.coords_and_ids_op ids=[0, 4, -2]",
                nullcontext("test.coords_and_ids_op ids = [0, 4, -2]"),
            ),
            (
                "test.coords_and_ids_op coords=[(0,0.1), (1,2)], ids=[9, 3]",
                nullcontext(
                    "test.coords_and_ids_op coords = [(0.0, 0.1), (1.0, 2.0)], ids = [9, 3]"
                ),
            ),
            (
                "test.coords_and_ids_op ids=[1, 2], coords=[(0,0.1), (1,2)]",
                nullcontext(
                    "test.coords_and_ids_op coords = [(0.0, 0.1), (1.0, 2.0)], ids = [1, 2]"
                ),
            ),
            (
                "test.coords_and_ids_op ids=[-1, 2],",
                pytest.raises(ParseError, match="Expected 'coords' or 'ids' keyword after ','"),
            ),
            (
                "test.coords_and_ids_op coords=[(0,0.1), (1,2)],",
                pytest.raises(ParseError, match="Expected 'coords' or 'ids' keyword after ','"),
            ),
            ("test.coords_and_ids_op blah=[]", nullcontext("test.coords_and_ids_op ")),
        ],
    )
    def test_alloc_qubit_props_parsing_and_printing(
        self, input_str: str, expectation: AbstractContextManager[str | pytest.ExceptionInfo]
    ):
        """Test that AllocQubitPropsDirective correctly parses and prints including whether it
        raises an error when the input is malformed.

        Arguments:
            input_str: A string to parse (a test.coords_and_ids_op)
            expectation: The expected result (in a nullcontext) or exception context for the parsed
                `input_str`
        """

        @irdl_op_definition
        class TCoordsIdsOp(IRDLOperation):
            name = "test.coords_and_ids_op"
            coords_prop = opt_prop_def(ArrayAttr[QubitCoordinateAttr])
            ids_prop = opt_prop_def(ArrayAttr[IntAttr])

            assembly_format = (
                f"{AllocQubitPropsDirective.use('$coords_prop', '$ids_prop')} attr-dict"
            )
            custom_directives = (AllocQubitPropsDirective,)

        context = Context()
        context.load_attr_or_type(QubitCoordinateAttr)
        context.load_attr_or_type(IntAttr)
        context.load_op(TCoordsIdsOp)
        parser = Parser(context, input_str)

        with expectation as e:
            op = parser.parse_op()
            op.verify()
            assert isinstance(op, TCoordsIdsOp)
            output_stream = StringIO()
            printer = Printer(stream=output_stream)
            printer.print_op(op)
            assert output_stream.getvalue() == e

    @pytest.mark.parametrize(
        ("method", "args", "expected_values"),
        [
            (
                PauliNoiseParametersAttr,
                (
                    DenseIntOrFPElementsAttr.from_list(
                        TensorType(Float64Type(), [4, 4]), [1 / 16] * 16
                    ),
                ),
                tuple([1 / 16] * 16),
            ),
            (PauliNoiseParametersAttr.from_pauli, ("X", 0.2), (0.8, 0.2, 0.0, 0.0)),
            (PauliNoiseParametersAttr.from_pauli, ("Z", 0.3), (0.7, 0.0, 0.0, 0.3)),
            (PauliNoiseParametersAttr.single_pauli, (0.2, 0.2, 0.4), (0.2, 0.2, 0.2, 0.4)),
            (PauliNoiseParametersAttr.single_pauli, (0.3, 0.1, 0.4), (0.2, 0.3, 0.1, 0.4)),
            (
                PauliNoiseParametersAttr.two_pauli,
                (
                    0.3,
                    0.1,
                    0.1,
                    0.05,
                    0.02,
                    0.02,
                    0.05,
                    0.01,
                    0.05,
                    0.04,
                    0.02,
                    0.06,
                    0.004,
                    0.006,
                    0,
                ),
                (
                    0.17,
                    0.3,
                    0.1,
                    0.1,
                    0.05,
                    0.02,
                    0.02,
                    0.05,
                    0.01,
                    0.05,
                    0.04,
                    0.02,
                    0.06,
                    0.004,
                    0.006,
                    0,
                ),
            ),
            (PauliNoiseParametersAttr.depolarise, (1, 0.3), (0.7, 0.3 / 3, 0.3 / 3, 0.3 / 3)),
            (PauliNoiseParametersAttr.depolarise, (1, 0.2), (0.8, 0.2 / 3, 0.2 / 3, 0.2 / 3)),
            (PauliNoiseParametersAttr.depolarise, (2, 0.3), tuple([0.7] + ([0.3 / 15] * 15))),
            (PauliNoiseParametersAttr.depolarise, (3, 0.3), tuple([0.7] + ([0.3 / 63] * 63))),
            (
                PauliNoiseParametersAttr.depolarise,
                (2, 0.3, False),
                tuple([0.7] + ([0.3 / 15] * 15)),
            ),
            (
                PauliNoiseParametersAttr.depolarise,
                (3, 0.3, False),
                tuple([0.7] + ([0.3 / 63] * 63)),
            ),
            (
                PauliNoiseParametersAttr.depolarise,
                (2, 0.3, True),
                tuple([0.7 + (0.3 / 16)] + ([0.3 / 16] * 15)),
            ),
            (
                PauliNoiseParametersAttr.depolarise,
                (3, 0.3, True),
                tuple([0.7 + (0.3 / 64)] + ([0.3 / 64] * 63)),
            ),
            (PauliNoiseParametersAttr.uniform, (1,), tuple([1 / 4] * 4)),
            (PauliNoiseParametersAttr.uniform, (2,), tuple([1 / 16] * 16)),
            (PauliNoiseParametersAttr.uniform, (3,), tuple([1 / 64] * 64)),
            (
                PauliNoiseParametersAttr.from_pauli_strings_dict,
                ({(None, PauliAttr.X()): 0.3},),
                (0.7, 0.3, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            ),
            (
                PauliNoiseParametersAttr.from_pauli_strings_dict,
                ({(PauliAttr.Y(),): 0.3, (None,): 0.7},),
                (0.7, 0.0, 0.3, 0.0),
            ),
            (
                PauliNoiseParametersAttr.from_str_dict,
                ({"IZ": 0.1},),
                (0.9, 0.0, 0.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            ),
            (
                PauliNoiseParametersAttr.from_str_dict,
                ({"Z": 0.1, "I": 0.9},),
                (0.9, 0.0, 0.0, 0.1),
            ),
            (
                PauliNoiseParametersAttr.from_tensor_coord_dict,
                ({(0, 3): 0.1, (1, 2): 0.2},),
                (0.7, 0.0, 0.0, 0.1, 0.0, 0.0, 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            ),
        ],
    )
    def test_pauli_noise_parameters_attr_inits(
        self, method: Callable, args: tuple, expected_values: tuple[float, ...]
    ):
        """Test that the different creation methods for PauliNoiseParametersAttr works. As well as
        helper methods."""
        n = method(*args)
        assert isinstance(n, PauliNoiseParametersAttr)
        assert n.tensor.get_values()[1:] == expected_values[1:]
        # Compare the first value as 'isclose' since it could be calculated from the other values.
        assert math.isclose(n.tensor.get_values()[0], expected_values[0])

        assert 4 ** n.qubit_count() == len(expected_values)

        n2 = PauliNoiseParametersAttr.from_str_dict(
            {n._index_to_ident(i): p for i, p in enumerate(n.tensor.get_values())}
        )
        assert n2 == n

    def test_pauli_noise_parameters_attr_init_error(self):
        """Test passing invalid ident to creation function throws error."""
        with pytest.raises(
            ValueError, match=re.escape("'x' is not a valid part of a probability identifier.")
        ):
            PauliNoiseParametersAttr.from_str_dict({"xxx": 1.0})

    @pytest.mark.parametrize(
        ("tensor", "exp_error"),
        [
            (
                DenseIntOrFPElementsAttr.from_list(
                    TensorType(Float64Type(), [4]), [0.999999999999999, 0.0, 0.0, 0.000001]
                ),
                re.escape(
                    "The sum of noise probabilities must sum to 1.0 but got 1.000000999999999."
                ),
            ),
            (
                DenseIntOrFPElementsAttr.from_list(TensorType(Float64Type(), [2]), [0.5, 0.5]),
                re.escape(
                    "The pauli noise tensor shape must be length 4 in each rank/dimension "
                    "and have 1 rank per qubit.\nUnderlying verification failure: Expected "
                    "attribute #builtin.int<4> but got #builtin.int<2>"
                ),
            ),
            (
                DenseIntOrFPElementsAttr.from_list(
                    TensorType(Float32Type(), [4, 4]), [1 / 16] * 16
                ),
                re.escape("f32 should be of base attribute f64"),
            ),
            (
                DenseIntOrFPElementsAttr.from_list(
                    TensorType(Float64Type(), [4, 4]), ([2 / 15] * 15) + [-1]
                ),
                re.escape("Noise probabilities must be non-negative but got ZZ = -1.0."),
            ),
            (
                DenseIntOrFPElementsAttr.from_list(
                    TensorType(Float64Type(), [4]), [0.0, -1.0, 1.0, 1.0]
                ),
                re.escape("Noise probabilities must be non-negative but got X = -1.0."),
            ),
            (
                DenseIntOrFPElementsAttr.from_list(
                    TensorType(Float64Type(), [4, 4, 4]),
                    ([1 / 62] * 27) + [-0.2, 0.2] + ([1 / 62] * 35),
                ),
                re.escape("Noise probabilities must be non-negative but got XYZ = -0.2."),
            ),
        ],
    )
    def test_pauli_noise_parameters_attr_verify(self, tensor: Attribute, exp_error: str):
        with pytest.raises(VerifyException, match=exp_error):
            PauliNoiseParametersAttr.new([tensor])

    @pytest.mark.parametrize(
        ("ir_string", "exp_error"),
        [
            (
                "Xx=1",
                re.escape(
                    "Expected noise parameters as a list of (`I`|`X`|`Y`|`Z`)+ `=` probability\n"
                    "Underlying error: 'x' is not a valid part of a probability identifier."
                ),
            ),
            (
                "YY=half",
                re.escape("Expected float literal"),
            ),
            (
                "            ",
                re.escape("identifier expected in the form [IXYZ]+"),
            ),
            (
                "XX=1, Y=2",
                re.escape(
                    "Expected noise parameters as a list of (`I`|`X`|`Y`|`Z`)+ `=` probability\n"
                    "Underlying error: All tensor coordinates must have the same number of "
                    "indices/Paulis."
                ),
            ),
            (
                "XX=1, YI=2,) ",
                re.escape("identifier expected in the form [IXYZ]+"),
            ),
        ],
    )
    def test_pauli_noise_parameters_attr_parse_errors(self, ir_string: str, exp_error: str):
        parser = Parser(Context(), ir_string)
        with pytest.raises(ParseError, match=exp_error):
            PauliNoiseParametersAttr.parse_inner_parameters(parser)

    def test_pauli_noise_parameters_attr_constraint(self):
        inner_constraint = IntVarConstraint("Name", EqIntConstraint(3))
        constraint = PauliNoiseParametersAttr.constr(inner_constraint)
        constraint.verify(PauliNoiseParametersAttr.depolarise(3, 0.2), ConstraintContext())
        # We don't care what the message is since it comes from EqIntConstraint not us:
        with pytest.raises(VerifyException):
            constraint.verify(PauliNoiseParametersAttr.depolarise(2, 0.2), ConstraintContext())
        assert constraint.mapping_type_vars({}) == PauliNoiseParametersAttr.constr(
            inner_constraint.mapping_type_vars({})
        )
        assert constraint.variables() == inner_constraint.variables()


def _matches_up_to_global_phase(
    m1: NpComplexMatrix, m2: NpComplexMatrix, tolerance: float = 1e-9
) -> bool:
    nonzero = np.abs(m2) > tolerance
    ratios = m1[nonzero] / m2[nonzero]
    return bool(
        np.allclose(ratios, ratios[0], atol=tolerance)
        and np.isclose(abs(ratios[0]), 1.0, atol=tolerance)
    )


class TestGateAttributes:
    @pytest.mark.parametrize(
        ("argument", "error_type", "error_msg"),
        [
            (
                [[(0, 0)]],
                VerifyException,
                re.escape(
                    "The dimensions of a unitary matrix must be 2**n by 2**n where n is the number "
                    "of qubits acted upon.\n"
                    "Underlying verification failure: "
                    "Got i = 1, so for i = 2**n, n = 0: expected integer >= 1, got 0"
                ),
            ),
            (
                [[(0, 0), (1, 0)], [(1, 0), (0, 0)]],
                None,
                None,
            ),
            (
                [[(1, 0), (0, 0)], [(0, 0), (1, 0)]],
                None,
                None,
            ),
            (
                DenseIntOrFPElementsAttr.from_list(
                    TensorType(ComplexType(Float64Type()), (2, 2)),
                    [(1.0, 0.0), (0.0, 0.0), (0.0, 0.0), (1.0, 0.0)],
                ),
                None,
                None,
            ),
            (
                [
                    [
                        ComplexNumberAttr(
                            FloatData(1.0), FloatData(0.0), ComplexType(Float64Type())
                        ),
                        (0, 0),
                    ],
                    [(0, 0), (1 + 0j)],
                ],
                None,
                None,
            ),
            (
                [
                    [(1, 0), (0, 0), (0, 0), (0, 0)],
                    [(0, 0), (0, 0), (0, 1), (0, 0)],
                    [(0, 0), (0, 1), (0, 0), (0, 0)],
                    [(0, 0), (0, 0), (0, 0), (1, 0)],
                ],
                None,
                None,
            ),
            (
                [
                    [(1, 1), (0, 0), (0, 0), (0, 0)],
                    [(0, 0), (0, 0), (0, 1), (0, 0)],
                    [(0, 0), (0, 1), (0, 0), (0, 0)],
                    [(0, 0), (0, 0), (0, 0), (1, 0)],
                ],
                VerifyException,
                re.escape("The given matrix, U, is not unitary since | U @ dag(U) - I | != 0."),
            ),
            (
                [[(1, 0), (0, 0)], [(0, 0), (1, 0), (1, 0)]],
                ValueError,
                re.escape(
                    "Argument does not form a square matrix, expected each row to be the same "
                    "length as the number of rows, but argument was:"
                ),
            ),
            (
                [[(1, 0), (0, 0)], [(0, 0), (1, 0)], [(0, 0), (1, 0)]],
                ValueError,
                re.escape(
                    "Argument does not form a square matrix, expected each row to be the same "
                    "length as the number of rows, but argument was:"
                ),
            ),
            (
                [],
                ValueError,
                re.escape(
                    "Argument does not form a square matrix, expected each row to be the same "
                    "length as the number of rows, but argument was:"
                ),
            ),
            (
                [[(1, 0), (0, 0), (0, 0)], [(0, 0), (1, 0), (0, 0)], [(0, 0), (1, 0), (0, 0)]],
                VerifyException,
                re.escape(
                    "The dimensions of a unitary matrix must be 2**n by 2**n where n is the "
                    "number of qubits acted upon.\n"
                    "Underlying verification failure: "
                    "Expected 3 = 2**n for some integer n, but log2(3) is not an integer."
                ),
            ),
        ],
    )
    def test_unitary_gate_attr(
        self, argument: Any, error_type: type[Exception] | None, error_msg: str | None
    ):
        """Tests the init method of UnitaryGateAttr and verification of constraints.

        Args:
            argument: The argument to pass to UnitaryGateAttr's constructor
            error_type: The type of Exception expected if an exception is
                expected.
            error_msg: The regex match for the expected exception, if expected.
        """
        if error_type is None or error_msg is None:
            val = UnitaryGateAttr(argument)
            assert UnitaryGateAttr.coerce(val) == UnitaryGateAttr.coerce(argument)

        else:
            with pytest.raises(error_type, match=error_msg):
                UnitaryGateAttr(argument)

    @pytest.mark.parametrize(
        "array",
        [
            np.identity(4, dtype=np.complex128),
            np.array([[0, -1j], [1j, 0]]),
            np.array([[0.70710678118, 0.70710678118], [0.70710678118, -0.70710678118]]),
        ],
    )
    def test_unitary_gate_attr_from_ndarray(self, array: np.ndarray):
        unitary = UnitaryGateAttr.from_ndarray(array)
        assert unitary == UnitaryGateAttr.coerce(array)
        new_array = unitary.as_ndarray()
        assert new_array.flags.writeable is False
        new_array2 = unitary.get_unitary_matrix()
        assert np.all(new_array == new_array2)
        assert unitary.as_unitary_gate_attr() is unitary

        assert new_array.shape == array.shape[:2]
        assert new_array.shape == (2 ** unitary.get_qubit_count(), 2 ** unitary.get_qubit_count())
        assert (array == new_array).all()
        with pytest.raises(ValueError, match="assignment destination is read-only"):
            new_array[0, 0] = 1

        assert unitary.short_str() == f"qcore.gate.unitary<... {array.shape[0]}x{array.shape[1]}>"

    @pytest.mark.parametrize(
        "array",
        [
            np.array([[[1, 2], [1, 2]], [[1, 2], [1, 2]], [[1, 2], [1, 2]], [[1, 2], [1, 2]]]),
            np.array([]),
        ],
    )
    def test_unitary_gate_attr_from_ndarray_fails(self, array: np.ndarray):
        with pytest.raises(
            ValueError,
            match=r"Expected a unitary matrix array with 2 dimensions but got [0-9]+\.",
        ):
            UnitaryGateAttr.from_ndarray(array)

    @pytest.mark.parametrize(
        ("input_str", "error_msg"),
        [
            ("<[]>", re.escape("Could not parse values as a square matrix of complex floats.")),
            ("<[[(a,b)]]>", re.escape("Expected float literal")),
            (
                "<[[(0,0), (0,0)]]>",
                re.escape("Could not parse values as a square matrix of complex floats."),
            ),
            (
                "<[[(0,0), (0,0)],[(0,0), (0,0)],[(0,0), (0,0)]]>",
                re.escape("Could not parse values as a square matrix of complex floats."),
            ),
            (
                "<[[(0), (0)],[(0), (0)]]>",
                re.escape("Expected ','"),
            ),
            (
                "<[[0, 0],[0, 0]]>",
                re.escape("'(' expected"),
            ),
        ],
    )
    def test_unitary_gate_attr_parse_error(self, input_str: str, error_msg: str):
        context = Context()
        parser = Parser(context, input_str)
        with pytest.raises(ParseError, match=error_msg):
            UnitaryGateAttr.parse_parameters(parser)

    def test_unitary_gate_attr_constr(self):
        constraint = UnitaryGateAttr.constr(qubits=EqIntConstraint(1))
        constraint.verify(
            UnitaryGateAttr([[(1, 0), (0, 0)], [(0, 0), (1, 0)]]),
            constraint_context=ConstraintContext(),
        )
        with pytest.raises(
            VerifyException,
            match=re.escape(
                "The number of qubits, n, as determined by the size of the unitary gate matrix "
                "does not satisfy its constraint.\n"
                "Underlying verification failure: "
                "Got i = 4, so for i = 2**n, n = 2: Invalid value 2, expected 1"
            ),
        ):
            constraint.verify(
                UnitaryGateAttr(
                    [
                        [(1, 0), (0, 0), (0, 0), (0, 0)],
                        [(0, 0), (1, 0), (0, 0), (0, 0)],
                        [(0, 0), (0, 0), (1, 0), (0, 0)],
                        [(0, 0), (0, 0), (0, 0), (-1, 0)],
                    ]
                ),
                constraint_context=ConstraintContext(),
            )

        constraint = UnitaryGateAttr.constr(dimension=EqIntConstraint(2))
        constraint.verify(
            UnitaryGateAttr([[(1, 0), (0, 0)], [(0, 0), (1, 0)]]),
            constraint_context=ConstraintContext(),
        )
        with pytest.raises(
            VerifyException,
            match=re.escape(
                "The size of the unitary gate matrix does not satisfy its constraint.\n"
                "Underlying verification failure: Expected attribute #builtin.int<2> but got "
                "#builtin.int<4>"
            ),
        ):
            constraint.verify(
                UnitaryGateAttr(
                    [
                        [(1, 0), (0, 0), (0, 0), (0, 0)],
                        [(0, 0), (1, 0), (0, 0), (0, 0)],
                        [(0, 0), (0, 0), (1, 0), (0, 0)],
                        [(0, 0), (0, 0), (0, 0), (-1, 0)],
                    ]
                ),
                constraint_context=ConstraintContext(),
            )

    @pytest.mark.parametrize(
        ("gate_type", "options", "allowed", "function"),
        [
            (IdentityGateAttr, [], True, IdentityGateAttr),
            (IdentityGateAttr, ["dag"], False, None),
            (IdentityGateAttr, ["sqrt"], False, None),
            (IdentityGateAttr, ["sqrt", "dag"], False, None),
            (XGateAttr, [], True, XGateAttr),
            (XGateAttr, ["dag"], False, None),
            (XGateAttr, ["sqrt"], True, XGateAttr.sqrt),
            (XGateAttr, ["sqrt", "dag"], True, XGateAttr.sqrt_dag),
            (YGateAttr, [], True, YGateAttr),
            (YGateAttr, ["dag"], False, None),
            (YGateAttr, ["sqrt"], True, YGateAttr.sqrt),
            (YGateAttr, ["sqrt", "dag"], True, YGateAttr.sqrt_dag),
            (ZGateAttr, [], True, ZGateAttr),
            (ZGateAttr, ["dag"], False, None),
            (ZGateAttr, ["sqrt"], False, None),
            (ZGateAttr, ["sqrt", "dag"], False, None),
            (HGateAttr, [], True, HGateAttr),
            (HGateAttr, ["dag"], False, None),
            (HGateAttr, ["sqrt"], False, None),
            (HGateAttr, ["sqrt", "dag"], False, None),
            (SGateAttr, [], True, SGateAttr),
            (SGateAttr, ["dag"], True, SGateAttr.dag),
            (SGateAttr, ["sqrt"], False, None),
            (SGateAttr, ["sqrt", "dag"], False, None),
            (TGateAttr, [], True, TGateAttr),
            (TGateAttr, ["dag"], True, TGateAttr.dag),
            (TGateAttr, ["sqrt"], False, None),
            (TGateAttr, ["sqrt", "dag"], False, None),
            (SqrtXXGateAttr, [], True, SqrtXXGateAttr),
            (SqrtXXGateAttr, ["dag"], True, SqrtXXGateAttr.dag),
            (SqrtXXGateAttr, ["sqrt"], False, None),
            (SqrtXXGateAttr, ["sqrt", "dag"], False, None),
            (SqrtYYGateAttr, [], True, SqrtYYGateAttr),
            (SqrtYYGateAttr, ["dag"], True, SqrtYYGateAttr.dag),
            (SqrtYYGateAttr, ["sqrt"], False, None),
            (SqrtYYGateAttr, ["sqrt", "dag"], False, None),
            (SqrtZZGateAttr, [], True, SqrtZZGateAttr),
            (SqrtZZGateAttr, ["dag"], True, SqrtZZGateAttr.dag),
            (SqrtZZGateAttr, ["sqrt"], False, None),
            (SqrtZZGateAttr, ["sqrt", "dag"], False, None),
            (CXGateAttr, [], True, CXGateAttr),
            (CXGateAttr, ["dag"], False, None),
            (CXGateAttr, ["sqrt"], False, None),
            (CXGateAttr, ["sqrt", "dag"], False, None),
            (CYGateAttr, [], True, CYGateAttr),
            (CYGateAttr, ["dag"], False, None),
            (CYGateAttr, ["sqrt"], False, None),
            (CYGateAttr, ["sqrt", "dag"], False, None),
            (CZGateAttr, [], True, CZGateAttr),
            (CZGateAttr, ["dag"], False, None),
            (CZGateAttr, ["sqrt"], False, None),
            (CZGateAttr, ["sqrt", "dag"], False, None),
            (SWAPGateAttr, [], True, SWAPGateAttr),
            (SWAPGateAttr, ["dag"], False, None),
            (SWAPGateAttr, ["sqrt"], False, None),
            (SWAPGateAttr, ["sqrt", "dag"], False, None),
            (ISWAPGateAttr, [], True, ISWAPGateAttr),
            (ISWAPGateAttr, ["dag"], True, ISWAPGateAttr.dag),
            (ISWAPGateAttr, ["sqrt"], False, None),
            (ISWAPGateAttr, ["sqrt", "dag"], False, None),
            (CCXGateAttr, [], True, CCXGateAttr),
            (CCXGateAttr, ["dag"], False, None),
            (CCXGateAttr, ["sqrt"], False, None),
            (CCXGateAttr, ["sqrt", "dag"], False, None),
            (CCZGateAttr, [], True, CCZGateAttr),
            (CCZGateAttr, ["dag"], False, None),
            (CCZGateAttr, ["sqrt"], False, None),
            (CCZGateAttr, ["sqrt", "dag"], False, None),
            (CHGateAttr, [], True, CHGateAttr),
            (CHGateAttr, ["dag"], False, None),
            (CHGateAttr, ["sqrt"], False, None),
            (CHGateAttr, ["sqrt", "dag"], False, None),
        ],
    )
    def test_gates_with_options(
        self,
        gate_type: type[StandardGateAttribute],
        options: Sequence[str],
        allowed: bool,
        function: Callable[[], GateAttribute] | None,
    ):
        """Tests that StandardGateAttribute correctly validate their options"""
        options_array = ArrayAttr([GateOptionAttr(_GateOption(o)) for o in options])
        if allowed:
            gate_1 = gate_type.new([options_array])
            assert function is not None
            gate_2 = function()
            assert gate_1 == gate_2
        else:
            error_match = (
                "Only the following options are allowed for a '"
                f"{re.escape(gate_type.name)}': <>(, <(sqrt|dag)(, (sqrt|dag))*>)*\n"
            )
            with pytest.raises(VerifyException, match=error_match):
                gate_type.new([options_array])

    @pytest.fixture
    def all_standard_gates(self) -> list[StandardGateAttribute]:
        standard_gate_types = [
            attr for attr in QCore.attributes if issubclass(attr, StandardGateAttribute)
        ]
        all_standard_gates: list[StandardGateAttribute] = []
        all_options: list[tuple[_GateOption, ...]] = [
            (),
            *itertools.permutations(_GateOption, len(_GateOption)),
        ]
        for gate_type in standard_gate_types:
            made_gate = False
            for options in all_options:
                try:
                    gate = gate_type.new([ArrayAttr([GateOptionAttr(o) for o in options])])
                    all_standard_gates.append(gate)
                    made_gate = True
                except VerifyException:
                    pass
            assert made_gate, f"{gate_type}"

        assert len(all_standard_gates) == len(set(all_standard_gates))
        return all_standard_gates

    def test_unique_standard_gates(self, all_standard_gates: list[StandardGateAttribute]) -> None:
        """Tests that no 2 standard gate attributes in the qcore dialect define the same unitary
        matrix, up to a global phase - two gates that are the same physical operation but differ
        by an overall phase would be just as confusing a duplicate as two bit-for-bit identical
        matrices."""
        assert len(all_standard_gates) == len(set(all_standard_gates))

        for gate1, gate2 in itertools.combinations(all_standard_gates, 2):
            assert gate1 != gate2
            if gate1.get_qubit_count() == gate2.get_qubit_count():
                # large tolerance is used to avoid a reasonable possibility of confusion between
                # standard gates after a few precision losing matrix operations.
                assert not _matches_up_to_global_phase(
                    gate1.get_unitary_matrix(), gate2.get_unitary_matrix(), tolerance=1e-5
                )

    @pytest.mark.parametrize(
        ("gate_func1", "gate_func2"),
        [
            (IdentityGateAttr, IdentityGateAttr),
            (XGateAttr.sqrt, XGateAttr),
            (XGateAttr.sqrt_dag, XGateAttr),
            (YGateAttr.sqrt, YGateAttr),
            (YGateAttr.sqrt_dag, YGateAttr),
            (ZGateAttr.sqrt, ZGateAttr),
            (ZGateAttr.sqrt_dag, ZGateAttr),
            (SGateAttr, ZGateAttr),
            (SGateAttr.dag, ZGateAttr),
        ],
    )
    def test_gate_sqrt_match(
        self, gate_func1: Callable[[], GateAttribute], gate_func2: Callable[[], GateAttribute]
    ):
        matrix = gate_func1().get_unitary_matrix()
        new_matrix = matrix @ matrix
        exp_matrix = gate_func2().get_unitary_matrix()
        assert np.allclose(exp_matrix, new_matrix, rtol=1e-10, atol=1e-10)

    @pytest.mark.parametrize(
        ("gate_func", "qubits"),
        [
            (IdentityGateAttr, 1),
            (XGateAttr, 1),
            (XGateAttr.sqrt, 1),
            (XGateAttr.sqrt_dag, 1),
            (YGateAttr, 1),
            (YGateAttr.sqrt, 1),
            (YGateAttr.sqrt_dag, 1),
            (ZGateAttr, 1),
            (ZGateAttr.sqrt, 1),
            (ZGateAttr.sqrt_dag, 1),
            (HGateAttr, 1),
            (SGateAttr, 1),
            (SGateAttr.dag, 1),
            (TGateAttr, 1),
            (TGateAttr.dag, 1),
            (SqrtXXGateAttr, 2),
            (SqrtXXGateAttr.dag, 2),
            (SqrtYYGateAttr, 2),
            (SqrtYYGateAttr.dag, 2),
            (SqrtZZGateAttr, 2),
            (SqrtZZGateAttr.dag, 2),
            (CXGateAttr, 2),
            (CYGateAttr, 2),
            (CZGateAttr, 2),
            (SWAPGateAttr, 2),
            (ISWAPGateAttr, 2),
            (ISWAPGateAttr.dag, 2),
            (CHGateAttr, 2),
            (CCXGateAttr, 3),
            (CCZGateAttr, 3),
        ],
    )
    def test_standard_gate_creation(self, gate_func: Callable[[], GateAttribute], qubits: int):
        """tests methods that make standard gates, and test all these gates have correct qubit
        counts."""
        gate = gate_func()
        assert isinstance(gate, GateAttribute)
        assert isinstance(gate, StandardGateAttribute)
        assert gate.get_qubit_count() == qubits
        matrix = gate.get_unitary_matrix()
        assert matrix.shape == (2**qubits, 2**qubits)

    def test_all_standard_gates_unitary(self, all_standard_gates: list[StandardGateAttribute]):
        """Tests that all standard gates can convert into well formed UnitaryGateAttrs, which also
        checks the matrices are unitary."""
        for gate in all_standard_gates:
            matrix = gate.get_unitary_matrix()
            assert matrix.dtype == GateAttribute.NP_FORMAT
            unitary = UnitaryGateAttr.from_ndarray(matrix)
            assert np.all(unitary.get_unitary_matrix() == matrix)
            assert unitary == gate.as_unitary_gate_attr()

            str_io = StringIO()
            printer = Printer(stream=str_io)
            printer.print_attribute(gate)
            ctx = Context()
            ctx.load_dialect(QCore)
            parser = Parser(ctx, str_io.getvalue())
            attr = parser.parse_attribute()
            assert attr == gate

    def test_all_standard_gate_short_str(self, all_standard_gates: list[StandardGateAttribute]):
        """Tests that all standard gates have a functioning and unique short_str method."""
        for gate in all_standard_gates:
            assert gate.short_str() == str(gate)
        strs = {gate.short_str() for gate in all_standard_gates}
        assert len(strs) == len(all_standard_gates)
        assert (
            max(map(len, strs)) < 30
        )  # using 30 characters as an arbitrary limit for being 'short'

    def test_gate_constraint(self):
        """Tests GateConstraint verifies correctly"""
        inner_constraint = IntVarConstraint("Name", EqIntConstraint(2))
        constraint = GateConstraint(inner_constraint)
        constraint.verify(ISWAPGateAttr(), ConstraintContext())
        # We don't care what the message is since it comes from EqIntConstraint not us:
        with pytest.raises(VerifyException):
            constraint.verify(XGateAttr.sqrt_dag(), ConstraintContext())

        assert constraint.mapping_type_vars({}) == GateConstraint(
            inner_constraint.mapping_type_vars({})
        )
        assert constraint.variables() == inner_constraint.variables()

    def test_unitary_gate_attr_from_u3(self):
        """Tests that UnitaryGateAttr.from_u3 produces the same matrix as the tsim/clifft U3
        convention, and round-trips through the general unitary machinery."""
        gate = UnitaryGateAttr.from_u3(0.5, 0.0, 1.0)
        assert isinstance(gate, UnitaryGateAttr)
        assert gate.get_qubit_count() == 1
        matrix = gate.get_unitary_matrix()
        assert matrix.shape == (2, 2)
        assert np.allclose(matrix @ matrix.conj().T, np.eye(2), atol=1e-10)
        # U3(pi/2, 0, pi) is the Hadamard gate.
        assert np.allclose(matrix, HGateAttr().get_unitary_matrix(), atol=1e-10)

    @pytest.mark.parametrize(
        "matrix",
        [
            UnitaryGateAttr.from_u3(0.0, 0.0, 0.0).get_unitary_matrix(),  # identity: a, d
            # dominant, b and c both ~0
            UnitaryGateAttr.from_u3(1.0, 0.0, 1.0).get_unitary_matrix(),  # X: a, d both ~0
            UnitaryGateAttr.from_u3(1.0, 0.5, 0.0).get_unitary_matrix(),  # Y-like: a, d both ~0
            UnitaryGateAttr.from_u3(0.0, 0.0, 0.25).get_unitary_matrix(),  # T-like: b, c both ~0
            UnitaryGateAttr.from_u3(0.5, 0.0, 1.0).get_unitary_matrix(),  # H: well conditioned
            UnitaryGateAttr.from_u3(0.37, 0.81, -1.2).get_unitary_matrix(),  # generic
            UnitaryGateAttr.from_u3(1.6, -2.3, 0.05).get_unitary_matrix(),  # theta outside
            # [0, 1], still must round-trip
            cmath.exp(1j * 0.73) * np.eye(2, dtype=complex),  # an arbitrary global phase with
            # no rotation at all, from_u3 can't produce this, so this one case stays a literal
            # matrix.
        ],
    )
    def test_unitary_gate_attr_matrix_to_u3_angles_round_trips(self, matrix: NpComplexMatrix):
        """Tests that UnitaryGateAttr.from_u3(*matrix_to_u3_angles(matrix)) reconstructs matrix
        up to global phase - matrix_to_u3_angles is the inverse of from_u3. Covers the
        well-conditioned case and both degenerate edge cases (a or c ~ 0), reusing from_u3 itself
        (rather than a separate hand-rolled U3 matrix builder) to build the round-trip inputs."""
        theta, phi, lam = UnitaryGateAttr.matrix_to_u3_angles(matrix)
        reconstructed = UnitaryGateAttr.from_u3(theta, phi, lam).get_unitary_matrix()
        assert _matches_up_to_global_phase(reconstructed, matrix)

    def test_rotation_gate_attr_not_standard_gate_attribute(self):
        """RotationGateAttr is parameterised by a Pauli string and a continuous angle rather than
        a closed set of options, so unlike the named gates above it is a GateAttribute, not a
        StandardGateAttribute."""
        gate = RotationGateAttr.x(0.5)
        assert isinstance(gate, GateAttribute)
        assert not isinstance(gate, StandardGateAttribute)

    @pytest.mark.parametrize(
        ("gate", "expected_qubit_count"),
        [
            (RotationGateAttr.x(0.5), 1),
            (RotationGateAttr.y(0.25), 1),
            (RotationGateAttr.z(2.0), 1),
            (RotationGateAttr.xx(0.5), 2),
            (RotationGateAttr.yy(-0.7), 2),
            (RotationGateAttr.zz(1.3), 2),
            (RotationGateAttr.spp([PauliAttr.X(), PauliAttr.Y(), PauliAttr.Z()]), 3),
            (RotationGateAttr.tpp_dag([PauliAttr.Z()]), 1),
        ],
    )
    def test_rotation_gate_attr_creation(self, gate: RotationGateAttr, expected_qubit_count: int):
        """Tests RotationGateAttr reports the correct qubit count and produces a well formed,
        unitary matrix."""
        assert gate.get_qubit_count() == expected_qubit_count
        matrix = gate.get_unitary_matrix()
        assert matrix.shape == (2**expected_qubit_count, 2**expected_qubit_count)
        assert matrix.dtype == GateAttribute.NP_FORMAT
        assert np.allclose(matrix @ matrix.conj().T, np.eye(2**expected_qubit_count), atol=1e-10)

    @pytest.mark.parametrize(
        ("gate", "expected_matrix_gate"),
        [
            (RotationGateAttr.x(1.0), XGateAttr()),
            (RotationGateAttr.x(0.5), XGateAttr.sqrt()),
            (RotationGateAttr.y(1.0), YGateAttr()),
            (RotationGateAttr.y(0.5), YGateAttr.sqrt()),
            (RotationGateAttr.z(1.0), ZGateAttr()),
            (RotationGateAttr.spp([PauliAttr.Z()]), SGateAttr()),
            (RotationGateAttr.spp_dag([PauliAttr.Z()]), SGateAttr.dag()),
            (RotationGateAttr.tpp([PauliAttr.Z()]), TGateAttr()),
            (RotationGateAttr.spp([PauliAttr.X(), PauliAttr.X()]), SqrtXXGateAttr()),
        ],
    )
    def test_rotation_gate_attr_matches_standard_gate_up_to_global_phase(
        self, gate: RotationGateAttr, expected_matrix_gate: GateAttribute
    ):
        """RotationGateAttr is exp(-i*alpha*pi/2*P), the plain textbook Pauli-rotation convention,
        which differs from the named gates' matrix convention by an angle-dependent global phase.
        So e.g. RotationGateAttr.spp(Z0) is the same physical gate as SGateAttr, but not a
        bit-for-bit identical matrix."""
        matrix = gate.get_unitary_matrix()
        expected = expected_matrix_gate.get_unitary_matrix()

        # Some entries are exactly 0 at these angles, so only compare ratios where the
        # denominator is non-zero.
        nonzero = np.abs(expected) > 1e-10
        ratios = matrix[nonzero] / expected[nonzero]
        assert np.allclose(ratios, ratios[0], atol=1e-10), "should differ by a single global phase"
        assert np.isclose(abs(ratios[0]), 1.0, atol=1e-10), (
            "the phase factor must have unit magnitude"
        )

    @pytest.mark.parametrize(
        "text",
        [
            "#qcore.gate.rotation<X, 0.5>",
            "#qcore.gate.rotation<XX, -0.5>",
            "#qcore.gate.rotation<XYZ, 0.1234567891>",
        ],
    )
    def test_rotation_gate_attr_parse_print_round_trip(self, text: str):
        """Tests that RotationGateAttr parses and prints back to the same text."""
        ctx = Context()
        ctx.load_dialect(QCore)
        parser = Parser(ctx, text)
        attr = parser.parse_attribute()
        assert isinstance(attr, RotationGateAttr)

        str_io = StringIO()
        printer = Printer(stream=str_io)
        printer.print_attribute(attr)
        assert str_io.getvalue() == text

    def test_rotation_gate_attr_equality(self):
        """Tests that RotationGateAttr compares equal iff the Pauli string and angle both
        match."""
        pauli_string = [PauliAttr.X(), PauliAttr.Y()]
        other_pauli_string = [PauliAttr.X(), PauliAttr.Z()]
        assert RotationGateAttr(pauli_string, 0.5) == RotationGateAttr(pauli_string, 0.5)
        assert RotationGateAttr(pauli_string, 0.5) != RotationGateAttr(pauli_string, 0.6)
        assert RotationGateAttr(pauli_string, 0.5) != RotationGateAttr(other_pauli_string, 0.5)
        assert RotationGateAttr.x(0.5) == RotationGateAttr([PauliAttr.X()], 0.5)
        assert RotationGateAttr.spp(pauli_string) == RotationGateAttr(pauli_string, 0.5)
        assert RotationGateAttr.spp_dag(pauli_string) == RotationGateAttr(pauli_string, -0.5)
        assert RotationGateAttr.tpp(pauli_string) == RotationGateAttr(pauli_string, 0.25)
        assert RotationGateAttr.tpp_dag(pauli_string) == RotationGateAttr(pauli_string, -0.25)


class TestTypes:
    def test_qubit_type(self):
        """Tests QubitType construction and methods such as equality."""
        qubit_type = QubitType()
        assert QubitType() == qubit_type
        assert t.TestType("qubit") != qubit_type

    @pytest.mark.parametrize("size", range(1, 5))
    def test_qubit_reg_type(self, size: int):
        """Test QubitRegType construction and methods such as equality"""
        qubit_reg_type = QubitRegType(size)
        assert qubit_reg_type == QubitRegType(IntAttr(size))
        assert qubit_reg_type != QubitRegType(100)
        assert len(qubit_reg_type) == size

    @pytest.mark.parametrize(
        ("size", "error_msg"),
        [
            (IntAttr(-1), "expected integer >= 1, got -1"),
            (IntAttr(0), "expected integer >= 1, got 0"),
            (
                StringAttr("Hot Chocolate"),
                re.escape('"Hot Chocolate" should be of base attribute builtin.int'),
            ),
        ],
    )
    def test_qubit_reg_type_verification(self, size: Attribute, error_msg: str):
        """Test QubitRegType verification"""
        with pytest.raises(VerifyException, match=error_msg):
            QubitRegType.new((size,))


class TestOps:
    @pytest.mark.parametrize(
        ("coords", "ids", "result_types", "error_msg"),
        [
            (
                [(1, 2), (3, 4)],
                None,
                (),
                re.escape(
                    "Number of coordinates and allocated qubits do not match.\n"
                    "Underlying verification failure: "
                    "integer 0 expected from int variable 'Qubit_Count', but got 2"
                ),
            ),
            (
                None,
                [1, 4],
                (),
                re.escape(
                    "Number of ids and allocated qubits do not match.\n"
                    "Underlying verification failure: "
                    "integer 0 expected from int variable 'Qubit_Count', but got 2"
                ),
            ),
            (
                [(1, 2), (3, 4, 5)],
                None,
                QubitRegType(2),
                re.escape(
                    "All coordinates in a qcore.alloc_qubit must have the same number of "
                    "dimensions."
                ),
            ),
            (
                [(i, i - 1, i + 0.5) for i in range(10)],
                None,
                (QubitRegType(4), QubitRegType(1), QubitType()),
                re.escape(
                    "Number of coordinates and allocated qubits do not match.\n"
                    "Underlying verification failure: "
                    "integer 6 expected from int variable 'Qubit_Count', but got 10"
                ),
            ),
            (
                [(1, 2), (3, 4)],
                [1, 4, -5],
                (QubitRegType(2),),
                re.escape(
                    "Number of ids and allocated qubits do not match.\n"
                    "Underlying verification failure: "
                    "integer 2 expected from int variable 'Qubit_Count', but got 3"
                ),
            ),
            (
                [(1, 2), (3, 4)],
                [-1, 4, 5],
                (QubitRegType(3),),
                re.escape(
                    "Number of coordinates and allocated qubits do not match.\n"
                    "Underlying verification failure: "
                    "integer 3 expected from int variable 'Qubit_Count', but got 2"
                ),
            ),
        ],
    )
    def test_alloc_qubits_verify(
        self,
        coords: Iterable[Iterable[float]] | None,
        ids: Iterable[int] | None,
        result_types: Sequence[QubitType | QubitRegType] | QubitType | QubitRegType,
        error_msg: str,
    ):
        """Test that AllocQubits verifies correctly"""
        op = AllocQubitOp(result_types, coords, ids)
        with pytest.raises(VerifyException, match=error_msg):
            op.verify()

    @pytest.mark.parametrize(
        ("results", "qubit_count"),
        [
            ([QubitType(), QubitRegType(6)], 7),
            ([QubitRegType(7), QubitType(), QubitType()], 9),
            ([], 0),
        ],
    )
    def test_alloc_qubit_qubit_count(
        self,
        results: Sequence[QubitType | QubitRegType] | QubitType | QubitRegType,
        qubit_count: int,
    ):
        op = AllocQubitOp(results)
        op.verify()
        assert op.qubit_count() == qubit_count

    @pytest.mark.parametrize(
        ("coords", "result_types", "qubit_idx", "index", "expected_result"),
        [
            (None, [QubitType()], 0, None, None),
            (None, [QubitRegType(3)], 0, 0, None),
            (None, [QubitRegType(3)], 0, 2, None),
            (None, [QubitRegType(3), QubitType()], 1, None, None),
            ([(1.0, 2.0)], [QubitType()], 0, None, (1.0, 2.0)),
            ([(1.0, 2.0), (3.0, 4.0)], [QubitRegType(2)], 0, 0, (1.0, 2.0)),
            ([(1.0, 2.0), (3.0, 4.0)], [QubitRegType(2)], 0, 1, (3.0, 4.0)),
            ([(1.0, 2.0), (3.0, 4.0)], [QubitType(), QubitType()], 0, None, (1.0, 2.0)),
            ([(1.0, 2.0), (3.0, 4.0)], [QubitType(), QubitType()], 1, None, (3.0, 4.0)),
            ([(1.0, 2.0), (3.0, 4.0)], [QubitType(), QubitRegType(1)], 1, 0, (3.0, 4.0)),
            ([(1.0, 2.0), (3.0, 4.0)], [QubitRegType(1), QubitType()], 0, 0, (1.0, 2.0)),
            ([(1.0, 2.0), (3.0, 4.0)], [QubitRegType(1), QubitRegType(1)], 1, 0, (3.0, 4.0)),
            (
                [(i, i + 0.5) for i in range(4)],
                [QubitRegType(2), QubitRegType(2)],
                0,
                1,
                (1.0, 1.5),
            ),
            (
                [(i, i + 0.5) for i in range(4)],
                [QubitRegType(2), QubitRegType(2)],
                1,
                0,
                (2.0, 2.5),
            ),
            (
                [(i, i + 0.5) for i in range(8)],
                [QubitRegType(2), QubitType(), QubitType(), QubitRegType(3), QubitType()],
                2,
                None,
                (3.0, 3.5),
            ),
            (
                [(i, i + 0.5) for i in range(8)],
                [QubitRegType(2), QubitType(), QubitType(), QubitRegType(3), QubitType()],
                3,
                2,
                (6.0, 6.5),
            ),
            (
                [(i, i + 0.5) for i in range(8)],
                [QubitRegType(2), QubitType(), QubitType(), QubitRegType(3), QubitType()],
                4,
                None,
                (7.0, 7.5),
            ),
        ],
    )
    def test_alloc_qubit_get_qubit_coordinate_valid(
        self,
        coords: Iterable[Iterable[float]] | None,
        result_types: Sequence[QubitType | QubitRegType] | QubitType | QubitRegType,
        qubit_idx: int,
        index: int | None,
        expected_result: tuple[float, ...] | None,
    ):
        op = AllocQubitOp(result_types, coordinates=coords)
        op.verify()
        qubit = op.results[qubit_idx]

        location = op.get_qubit_coordinate(qubit, index)  # type: ignore[arg-type]
        if expected_result is None:
            assert location is None
        else:
            assert location.data == expected_result  # type: ignore[union-attr]

    @pytest.mark.parametrize(
        ("ids", "result_types", "qubit_idx", "index", "expected_result"),
        [
            (None, [QubitType()], 0, None, None),
            (None, [QubitRegType(3)], 0, 0, None),
            (None, [QubitRegType(3)], 0, 2, None),
            (None, [QubitRegType(3), QubitType()], 1, None, None),
            ([0], [QubitType()], 0, None, 0),
            ([0, 1], [QubitRegType(2)], 0, 0, 0),
            ([0, 1], [QubitRegType(2)], 0, 1, 1),
            ([0, 1], [QubitType(), QubitType()], 0, None, 0),
            ([0, 1], [QubitType(), QubitType()], 1, None, 1),
            ([0, 1], [QubitType(), QubitRegType(1)], 1, 0, 1),
            ([0, 1], [QubitRegType(1), QubitType()], 0, 0, 0),
            ([0, 1], [QubitRegType(1), QubitRegType(1)], 1, 0, 1),
            (
                list(range(4)),
                [QubitRegType(2), QubitRegType(2)],
                0,
                1,
                1,
            ),
            (
                list(range(4)),
                [QubitRegType(2), QubitRegType(2)],
                1,
                0,
                2,
            ),
            (
                list(range(8)),
                [QubitRegType(2), QubitType(), QubitType(), QubitRegType(3), QubitType()],
                2,
                None,
                3,
            ),
            (
                list(range(8)),
                [QubitRegType(2), QubitType(), QubitType(), QubitRegType(3), QubitType()],
                3,
                2,
                6,
            ),
            (
                list(range(8)),
                [QubitRegType(2), QubitType(), QubitType(), QubitRegType(3), QubitType()],
                4,
                None,
                7,
            ),
        ],
    )
    def test_alloc_qubit_get_qubit_id_valid(
        self,
        ids: Iterable[int] | None,
        result_types: Sequence[QubitType | QubitRegType] | QubitType | QubitRegType,
        qubit_idx: int,
        index: int | None,
        expected_result: tuple[float, ...] | None,
    ):
        op = AllocQubitOp(result_types, ids=ids)
        op.verify()
        qubit = op.results[qubit_idx]

        id_ = op.get_qubit_id(qubit, index)  # type: ignore[arg-type]
        if expected_result is None:
            assert id_ is None
        else:
            assert id_.data == expected_result  # type: ignore[union-attr]

    @pytest.mark.parametrize(
        ("result_types", "qubit_idx", "index", "error_type", "error_msg"),
        [
            (
                [QubitType()],
                0,
                1,
                TypeError,
                re.escape("Index provided for a single qubit."),
            ),
            (
                [QubitRegType(3)],
                0,
                None,
                TypeError,
                re.escape("Qubit register provided without an index."),
            ),
            (
                [QubitRegType(3)],
                0,
                3,
                IndexError,
                re.escape("Index 3 out of bounds for qubit register of size 3."),
            ),
            (
                [QubitType()],
                None,
                None,
                ValueError,
                re.escape("The given qubit is not allocated by this operation."),
            ),
        ],
    )
    @pytest.mark.parametrize(
        "get_attribute_method", [AllocQubitOp.get_qubit_coordinate, AllocQubitOp.get_qubit_id]
    )
    def test_alloc_qubit_get_qubit_coordinate_invalid(
        self,
        result_types: Sequence[QubitType | QubitRegType] | QubitType | QubitRegType,
        qubit_idx: int | None,
        index: int | None,
        error_type: type[Exception],
        error_msg: str,
        get_attribute_method: Callable[
            [AllocQubitOp, SSAValue[QubitType | QubitRegType], int | None],
            IntAttr | QubitCoordinateAttr | None,
        ],
    ):
        # should all happen even with no coords provided
        op = AllocQubitOp(result_types, None, None)
        op.verify()

        if qubit_idx is None:
            # unrelated qubit index
            qubit = t.TestOp(result_types=[QubitType()]).res[0]
        else:
            qubit = op.results[qubit_idx]

        with pytest.raises(error_type, match=error_msg):
            get_attribute_method(op, qubit, index)  # type: ignore[arg-type]

    def test_pack_qubit_reg_op_verify(self):
        """Test that verification of types in PackQubitRegOp works correctly"""
        op = PackQubitRegOp(
            t.TestOp(result_types=[QubitType(), QubitType()]).res,
        )
        Rewriter.replace_value_with_new_type(op.reg, QubitRegType(20))
        with pytest.raises(
            VerifyException,
            match=re.escape(
                "result 'reg' at position 0 does not verify:\n"
                "integer 2 expected from int variable 'Qubit_Count', but got 20"
            ),
        ):
            op.verify()
        op = PackQubitRegOp(
            t.TestOp(result_types=[QubitType(), QubitRegType(1)]).res,
        )
        with pytest.raises(
            VerifyException,
            match=re.escape("Expected attribute !qcore.qubit but got !qcore.qubit_reg<1>"),
        ):
            op.verify()

    def test_unpack_qubit_reg_op_verify(self):
        """Test that verification of types in UnpackQubitRegOp works correctly"""
        reg_operand = t.TestOp(result_types=[QubitRegType(2)]).res[0]
        op = UnpackQubitRegOp(reg_operand)
        op.results = SSAValues([OpResult(QubitType(), op, i) for i in range(4)])
        with pytest.raises(
            VerifyException,
            match=re.escape(
                "result 'qubits' at positions 0 to 3 does not verify:\n"
                "incorrect length for range variable:\n"
                "integer 2 expected from int variable 'Qubit_Count', but got 4"
            ),
        ):
            op.verify()
        qubit_operand = t.TestOp(result_types=[QubitType()]).res[0]
        op = UnpackQubitRegOp.create(operands=(qubit_operand,), result_types=(QubitType(),))
        with pytest.raises(
            VerifyException,
            match=re.escape(
                "operand 'reg' at position 0 does not verify:\n"
                "!qcore.qubit should be of base attribute qcore.qubit_reg"
            ),
        ):
            op.verify()

    def test_concatenate_op_verify(self):
        """Test that verification of types in ConcatenateOp works correctly."""
        op = ConcatenateOp(t.TestOp(result_types=[QubitRegType(2), QubitRegType(2)]).res)
        Rewriter.replace_value_with_new_type(op.out_reg, QubitRegType(6))
        with pytest.raises(
            VerifyException,
            match=re.escape(
                "result 'out_reg' at position 0 does not verify:\n"
                "The number of qubits in input and output do not match.\n"
                "Underlying verification failure: "
                "integer 4 expected from int variable 'Qubit_Count', but got 6"
            ),
        ):
            op.verify()

    def test_split_op_verify(self):
        """Test that verification of types in SplitOp works correctly."""
        op = SplitOp(t.TestOp(result_types=[QubitRegType(5)]).res, [2, 4])
        with pytest.raises(
            VerifyException,
            match=re.escape(
                "result 'out_regs' at positions 0 to 1 does not verify:\n"
                "Incorrect sum over range that produced values "
                "'!qcore.qubit_reg<2>' (2) + '!qcore.qubit_reg<4>' (4) = 6:\n"
                "The number of qubits in input and output do not match.\n"
                "Underlying verification failure: "
                "integer 5 expected from int variable 'Qubit_Count', but got 6"
            ),
        ):
            op.verify()

    def test_quantum_effects(self):
        """Test that ops have correct quantum effect traits."""
        alloc_op = AllocQubitOp(QubitType())
        assert get_quantum_effects(alloc_op) == set()
        pack_op = PackQubitRegOp(t.TestOp(result_types=[QubitType(), QubitType()]).res)
        assert get_quantum_effects(pack_op) == set()
        unpack_op = UnpackQubitRegOp(t.TestOp(result_types=[QubitRegType(2)]).res[0])
        assert get_quantum_effects(unpack_op) == set()
