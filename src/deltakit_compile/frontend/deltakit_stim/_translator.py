# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for translating Deltakit-Stim circuit objects to xDSL IRs."""

from __future__ import annotations

from collections import defaultdict
from typing import NamedTuple

from deltakit_stim import Circuit, CircuitInstruction, CircuitRepeatBlock, GateTarget
from xdsl.builder import Builder
from xdsl.dialects.builtin import ModuleOp, StringAttr
from xdsl.ir import Block, SSAValue
from xdsl.rewriter import InsertPoint

from deltakit_compile.dialects.deltakit_stim import HeraldLeakageEventOp, LeakageOp, RelaxOp
from deltakit_compile.dialects.stim import (
    CliffordGateOp,
    CorrelatedErrorOp,
    Depolarize1Op,
    Depolarize2Op,
    DetectorOp,
    ElseCorrelatedErrorOp,
    EmptyOp,
    MeasurementGateOp,
    MultiPauliProductMeasurementOp,
    ObservableIncludeOp,
    PauliChannel1Op,
    PauliChannel2Op,
    PauliOperatorEnum,
    QubitAllocOp,
    QubitCoordsOp,
    QubitMappingAttr,
    RepeatOp,
    ResetGateOp,
    ShiftCoordsOp,
    TickAnnotationOp,
    YieldOp,
)
from deltakit_compile.exceptions import InvalidInputStimCircuit
from deltakit_compile.shared.deltakit_stim.gates import (
    AnnotationEnum,
    LeakageEnum,
    MeasurementEnum,
    NoiseEnum,
    ResetEnum,
    SingleQubitUnitaryEnum,
    TwoQubitUnitaryEnum,
)


class _NamedRepeat(NamedTuple):
    """A repeat block with an identifier."""

    repeat_count: int
    body: _TaggedCircuit
    identifier: str
    tag: str | StringAttr | None
    name: str = "REPEAT"


_TaggedCircuit = list[CircuitInstruction | _NamedRepeat]
"""Emulate a Deltakit-Stim circuit, which includes repeats with identifiers"""


class _ScopeEarliestIndices(NamedTuple):
    """Container for the earliest indices into the record around a particular scope."""

    start_earliest_index: int
    """The earliest index accessed from the start of the body of the scope."""
    end_earliest_index: int
    """The earliest index accessed from the end of the scope."""


class _RecordScopeMap:
    """Class that figures out how far back in the record needs to be available in different scopes
    of the circuit (repeat blocks). This requires that the repeat instructions have unique tags.

    The algorithm iterates backwards through the circuit, tracking the earliest index in the record
    that has been referenced so far. There is an entry in the map for each repeat in the circuit,
    which is updated with the most negative record indices referenced in and after the repeat. This
    mean we now know how many of the measurement SSAValues need to be iter_args/yielded in the
    repeat during translation to IR.
    """

    def __init__(self, circuit: _TaggedCircuit) -> None:
        self._ro_num = 0
        self._earliest_global_index = 0
        self._earliest_index_map: defaultdict[str, _ScopeEarliestIndices] = defaultdict(
            lambda: _ScopeEarliestIndices(0, 0)
        )
        self._parse_circuit(circuit)

    def _parse_circuit(self, circuit: _TaggedCircuit) -> None:
        """Parse the circuit to fill out the index map."""
        for instr in reversed(circuit):
            if isinstance(instr, _NamedRepeat):
                cur_indices = self._earliest_index_map[instr.identifier]
                # Record the earliest index into the record at the end of the repeat
                new_end_earliest_index = self._earliest_global_index + self._ro_num
                end_earliest_index = min(new_end_earliest_index, cur_indices.end_earliest_index)

                for _ in range(instr.repeat_count):
                    self._parse_circuit(instr.body)

                # Record the earliest index into the record at the start of the repeat
                new_start_earliest_index = self._earliest_global_index + self._ro_num
                start_earliest_index = min(
                    new_start_earliest_index, cur_indices.start_earliest_index
                )
                self._earliest_index_map[instr.identifier] = _ScopeEarliestIndices(
                    start_earliest_index, end_earliest_index
                )

            elif MeasurementEnum.contains(instr.name):
                self._ro_num += len(instr.targets_copy())

            elif (
                instr.name in (AnnotationEnum.DETECTOR, AnnotationEnum.OBSERVABLE)
                and len(targets := instr.targets_copy()) > 0
            ):
                oldest_target = min(target.value for target in targets)
                global_index = oldest_target - self._ro_num
                self._earliest_global_index = min(self._earliest_global_index, global_index)

    def get_earliest_record_indices(self, repeat: _NamedRepeat) -> _ScopeEarliestIndices:
        """Get the earliest indices into the record used during or after the provided repeat
        block."""
        return self._earliest_index_map[repeat.identifier]


def _get_safe_tag(instr: CircuitInstruction | CircuitRepeatBlock) -> str | StringAttr | None:
    tag = getattr(instr, "tag", None)
    return tag or None


class DeltakitStimTranslator:
    """Class for translating Deltakit-Stim circuit objects to xDSL IRs."""

    def __init__(self, circuit: Circuit) -> None:
        _, self.circuit = self._tag_repeats(circuit)
        self.circuit_op = ModuleOp([])
        self.builder = Builder(InsertPoint.at_end(self.circuit_op.body.block))
        self.prev_qubit_alloc: QubitAllocOp | None = None
        self.qubit_ssa_map: dict[int, SSAValue] = {}
        self.record_ssas: list[SSAValue] = []
        self.record_scope_map = _RecordScopeMap(self.circuit)

    def _ensure_qubit_alloc(self, q: int) -> SSAValue:
        """Ensure a qubit alloc exists for index `q` and return its SSA value.

        Inserts the alloc at the beginning of the program (after the previous
        alloc, if any) to keep allocs in the global scope and preserve order.
        """
        if q not in self.qubit_ssa_map:
            new_op = QubitAllocOp(q)
            self.qubit_ssa_map[q] = new_op.results[0]

            # Insert alloc at the beginning of the program to guarantee it is in the global scope
            main_insert_point = self.builder.insertion_point
            self.builder.insertion_point = (
                InsertPoint.after(self.prev_qubit_alloc)
                if self.prev_qubit_alloc is not None
                else InsertPoint.at_start(self.circuit_op.body.block)
            )
            self.builder.insert(new_op)
            self.prev_qubit_alloc = new_op
            self.builder.insertion_point = main_insert_point

        return self.qubit_ssa_map[q]

    @classmethod
    def _raise_unknown_instr_error(cls, instr: CircuitInstruction) -> None:
        """Raise an error indicating the instruction is unknown."""
        msg = f"Deltakit-Stim {instr.name} instruction translation is not supported."
        raise InvalidInputStimCircuit(msg)

    @classmethod
    def _tag_repeats(cls, circuit: Circuit, num_tagged: int = 0) -> tuple[int, _TaggedCircuit]:
        """Tag the repeats a circuit with unique numbers, returning the total number tagged and a
        tagged circuit."""
        tagged_circuit = _TaggedCircuit()
        for instr in circuit:  # type: ignore[attr-defined]
            if isinstance(instr, CircuitRepeatBlock):
                num_tagged, repeat_body = cls._tag_repeats(instr.body_copy(), num_tagged)
                tagged_circuit.append(
                    _NamedRepeat(
                        repeat_count=instr.repeat_count,
                        body=repeat_body,
                        identifier=f"REPEAT_{num_tagged}",
                        tag=_get_safe_tag(instr),
                    ),
                )
                num_tagged += 1
            else:
                tagged_circuit.append(instr)

        return num_tagged, tagged_circuit

    def _extract_qubit_targets(self, targets: list[GateTarget]) -> list[SSAValue]:
        """Extract qubit targets as SSA values and add the qubit alloc operations implied by the use
        of a target for the first time to the top of self.circuit_op."""
        ssa_qubits: list[SSAValue] = []

        for target in targets:
            if target.is_qubit_target:
                ssa_qubits.append(self._ensure_qubit_alloc(target.value))

        return ssa_qubits

    def _extract_mpp_target_and_modifiers_groups(
        self, targets: list[GateTarget]
    ) -> list[tuple[list[SSAValue], list[PauliOperatorEnum]]]:
        """Extract MPP qubit SSA values and their Pauli modifiers grouped by
        product measurement. Each group corresponds to one product measurement.
        Groups are separated by spaces (non-combiner gaps) in the Deltakit-Stim instruction.
        For each group:
        - Skips product combiners ('*').
        - Ensures qubit alloc ops exist, returning aligned lists of SSAValues,
          `PauliOperatorEnum` modifiers.
        """
        groups: list[tuple[list[SSAValue], list[PauliOperatorEnum]]] = []
        current_qubits: list[SSAValue] = []
        current_modifiers: list[PauliOperatorEnum] = []
        expect_combiner = False

        for target in targets:
            if target.is_combiner:
                expect_combiner = False
            elif target.is_x_target or target.is_y_target or target.is_z_target:
                if expect_combiner and current_qubits:
                    # Gap (no combiner) before this target — start a new group
                    groups.append((current_qubits, current_modifiers))
                    current_qubits = []
                    current_modifiers = []
                current_qubits.append(self._ensure_qubit_alloc(target.value))
                current_modifiers.append(PauliOperatorEnum(target.pauli_type))
                expect_combiner = True

        if current_qubits:
            groups.append((current_qubits, current_modifiers))

        return groups

    @classmethod
    def _pauli_suffix_to_modifier(cls, instr_name: str) -> PauliOperatorEnum:
        """Get a pauli modifier from the last character (X, Y, Z) of a gate name."""
        pauli_suffix = instr_name[-1]
        if PauliOperatorEnum.contains(pauli_suffix):
            return PauliOperatorEnum(pauli_suffix)

        return PauliOperatorEnum.Z

    def _extract_rec_targets(self, targets: list[GateTarget]) -> list[SSAValue]:
        """Extract record (measurement) targets as SSA values."""
        ssa_recs: list[SSAValue] = []

        for target in targets:
            if target.is_measurement_record_target:
                rec_index = target.value
                if abs(rec_index) > len(self.record_ssas):
                    msg = (
                        f"Measurement record {rec_index} is out of range - "
                        f"available record is {len(self.record_ssas)} measurements long"
                    )
                    raise InvalidInputStimCircuit(msg)

                ssa_recs.append(self.record_ssas[rec_index])

        return ssa_recs

    def _translate_annotation(self, instr: CircuitInstruction) -> None:
        """Translate a Deltakit-Stim annotation instruction to xDSL ops and add them to
        self.circuit_op."""
        tag = _get_safe_tag(instr)
        match AnnotationEnum(instr.name):
            case AnnotationEnum.COORD:
                ssa_targets = self._extract_qubit_targets(instr.targets_copy())
                mapping = QubitMappingAttr(instr.gate_args_copy())
                self.builder.insert(QubitCoordsOp(ssa_targets, mapping, tag=tag))
            case AnnotationEnum.TICK:
                self.builder.insert(TickAnnotationOp(tag=tag))
            case AnnotationEnum.DETECTOR:
                recs = self._extract_rec_targets(instr.targets_copy())
                self.builder.insert(DetectorOp(recs, instr.gate_args_copy() or None, tag=tag))
            case AnnotationEnum.OBSERVABLE:
                recs = self._extract_rec_targets(instr.targets_copy())
                observable = int(instr.gate_args_copy()[0])
                self.builder.insert(ObservableIncludeOp(recs, observable, tag=tag))
            case AnnotationEnum.SHIFT:
                self.builder.insert(ShiftCoordsOp(instr.gate_args_copy(), tag=tag))

    def _translate_measurement(self, instr: CircuitInstruction) -> None:
        """Translate a Deltakit-Stim measurement instruction to xDSL ops and add them to
        self.circuit_op."""
        ssa_targets = self._extract_qubit_targets(instr.targets_copy())
        pauli_modifier = self._pauli_suffix_to_modifier(instr.name)
        noise = instr.gate_args_copy()[0] if len(instr.gate_args_copy()) > 0 else None

        meas_op = MeasurementGateOp(
            targets=ssa_targets,
            pauli_modifier=pauli_modifier,
            noise=noise,
            tag=_get_safe_tag(instr),
        )
        self.builder.insert(meas_op)
        self.record_ssas.extend(meas_op.results)

        # Create a reset op after measurement for MR, MRX, MRY, MRZ
        if "R" in instr.name:
            self.builder.insert(
                ResetGateOp(
                    targets=ssa_targets, pauli_modifier=pauli_modifier, tag=_get_safe_tag(instr)
                )
            )

    def _translate_mpp(self, instr: CircuitInstruction) -> None:
        """Translate MPP measurement instruction to xDSL ops and add to self.circuit_op.

        Each product group becomes a separate MultiPauliProductMeasurementOp.
        """
        groups = self._extract_mpp_target_and_modifiers_groups(instr.targets_copy())
        args = instr.gate_args_copy()
        noise = args[0] if args else None

        for ssa_targets, pauli_array in groups:
            meas_op = MultiPauliProductMeasurementOp(
                targets=ssa_targets,
                pauli_modifiers=pauli_array,
                noise=noise,
                tag=_get_safe_tag(instr),
            )
            self.builder.insert(meas_op)
            self.record_ssas.extend(meas_op.results)

    def _translate_reset(self, instr: CircuitInstruction) -> None:
        """Translate a Deltakit-Stim reset instruction to xDSL ops and add them to
        self.circuit_op."""
        ssa_targets = self._extract_qubit_targets(instr.targets_copy())
        pauli_modifier = self._pauli_suffix_to_modifier(instr.name)
        self.builder.insert(
            ResetGateOp(
                targets=ssa_targets, pauli_modifier=pauli_modifier, tag=_get_safe_tag(instr)
            )
        )

    def _translate_single_qubit_gate(self, instr: CircuitInstruction) -> None:
        """Translate a Deltakit-Stim single qubit gate to xDSL ops and add them to
        self.circuit_op."""
        ssa_targets = self._extract_qubit_targets(instr.targets_copy())
        self.builder.insert(
            CliffordGateOp(
                gate_type=SingleQubitUnitaryEnum(instr.name),
                targets=ssa_targets,
                tag=_get_safe_tag(instr),
            )
        )

    def _translate_two_qubit_gate(self, instr: CircuitInstruction) -> None:
        """Translate a Deltakit-Stim two qubit gate to xDSL ops and add them to self.circuit_op."""
        ssa_targets = self._extract_qubit_targets(instr.targets_copy())
        self.builder.insert(
            CliffordGateOp(
                gate_type=TwoQubitUnitaryEnum(instr.name),
                targets=ssa_targets,
                tag=_get_safe_tag(instr),
            )
        )

    def _translate_noise(self, instr: CircuitInstruction) -> None:
        """Translate a Deltakit-Stim noise instructions to xDSL ops and add them to
        self.circuit_op."""
        ssa_targets = self._extract_qubit_targets(instr.targets_copy())
        probabilities = instr.gate_args_copy()
        tag = _get_safe_tag(instr)
        match NoiseEnum(instr.name):
            case NoiseEnum.DEPOLARIZE1:
                self.builder.insert(Depolarize1Op(ssa_targets, probabilities[0], tag=tag))
            case NoiseEnum.DEPOLARIZE2:
                self.builder.insert(Depolarize2Op(ssa_targets, probabilities[0], tag=tag))
            case NoiseEnum.PAULI_CHANNEL_1:
                self.builder.insert(PauliChannel1Op(ssa_targets, probabilities, tag=tag))
            case NoiseEnum.PAULI_CHANNEL_2:
                self.builder.insert(PauliChannel2Op(ssa_targets, probabilities, tag=tag))
            case NoiseEnum.X_ERROR:
                self.builder.insert(PauliChannel1Op(ssa_targets, [probabilities[0], 0, 0], tag=tag))
            case NoiseEnum.Y_ERROR:
                self.builder.insert(PauliChannel1Op(ssa_targets, [0, probabilities[0], 0], tag=tag))
            case NoiseEnum.Z_ERROR:
                self.builder.insert(PauliChannel1Op(ssa_targets, [0, 0, probabilities[0]], tag=tag))
            case NoiseEnum.CORRELATED_ERROR:
                groups = self._extract_mpp_target_and_modifiers_groups(instr.targets_copy())
                targets = [target for targets, _ in groups for target in targets]
                modifiers = [modifier for _, modifiers in groups for modifier in modifiers]
                self.builder.insert(
                    CorrelatedErrorOp(targets, modifiers, probabilities[0], tag=tag)
                )
            case NoiseEnum.ELSE_CORRELATED_ERROR:
                groups = self._extract_mpp_target_and_modifiers_groups(instr.targets_copy())
                targets = [target for targets, _ in groups for target in targets]
                modifiers = [modifier for _, modifiers in groups for modifier in modifiers]
                self.builder.insert(
                    ElseCorrelatedErrorOp(targets, modifiers, probabilities[0], tag=tag)
                )

    def _translate_leakage(self, instr: CircuitInstruction) -> None:
        """Translate a Deltakit-Stim-specific leakage instruction."""
        ssa_targets = self._extract_qubit_targets(instr.targets_copy())
        probabilities = instr.gate_args_copy()
        tag = _get_safe_tag(instr)
        match LeakageEnum(instr.name):
            case LeakageEnum.HERALD_LEAKAGE_EVENT:
                self.builder.insert(
                    herald_op := HeraldLeakageEventOp(
                        ssa_targets, probabilities[0] if probabilities else None, tag=tag
                    )
                )
                self.record_ssas.extend(herald_op.heralds)
            case LeakageEnum.LEAKAGE:
                self.builder.insert(LeakageOp(ssa_targets, probabilities[0], tag=tag))
            case LeakageEnum.RELAX:
                self.builder.insert(RelaxOp(ssa_targets, probabilities[0], tag=tag))

    def _translate_repeat(self, repeat_block: _NamedRepeat) -> None:
        """Translate a repeat block into a scf.for loop and add it to self.circuit_op."""
        parent_builder = self.builder

        record_indices = self.record_scope_map.get_earliest_record_indices(repeat_block)
        if len(self.record_ssas) < abs(record_indices.start_earliest_index):
            msg = "A measurement record is referred to that doesn't exist"
            raise InvalidInputStimCircuit(msg)

        iter_arg_count = -min(record_indices)
        if iter_arg_count > 0:
            # If the earliest record index (start or end) is before now (is negative) then we need
            # iteration arguments. We might also need to insert empty ssa constants to enable the
            # values to track properly though the loop
            empty_ssa_num = max(0, iter_arg_count - len(self.record_ssas))
            if empty_ssa_num > 0:
                # Not enough measurements to fill iter_args for the first iteration (but fine on
                # later iterations) so add extra empty SSAs
                empty_op = EmptyOp()
                self.builder.insert(empty_op)
                iter_args = ([empty_op.res] * empty_ssa_num) + (
                    self.record_ssas[-(iter_arg_count - empty_ssa_num) :]
                )
            else:
                # Iter args contain all the latest measurement SSAs down to the the earliest used
                # after this point
                iter_args = self.record_ssas[-iter_arg_count:]
        else:
            # Otherwise we know that there are no iteration arguments needed
            iter_args = []

        # Insert the ops that are inside the repeat in a new block
        block = Block(arg_types=[a.type for a in iter_args])
        self.builder = Builder(InsertPoint.at_end(block))

        # Record SSAs used inside the repeat should all come from the iter_args
        self.record_ssas = list(block.args)

        self._translate_circuit(repeat_block.body)

        # Yield the same number of measurement SSAs as in the iter args, but with the latest in the
        # record as of the end of the loop body. This creates a shifting effect of the SSA values as
        # the loop iterates, modelling the record's append-only list behaviour
        values_to_yield = self.record_ssas[-iter_arg_count:] if iter_arg_count > 0 else []
        self.builder.insert(YieldOp(*values_to_yield))

        self.builder = parent_builder

        # Insert for loop (containing new block) into circuit
        repeat_op = RepeatOp(repeat_block.repeat_count, block, iter_args, tag=repeat_block.tag)
        self.builder.insert(repeat_op)

        # Record SSAs used after the repeat should all come from the repeat's results
        self.record_ssas = list(repeat_op.res)

    def _translate_circuit(self, circuit: _TaggedCircuit) -> None:
        """Translate a Deltakit-Stim circuit (could be the circuit inside a repeat block) into
        operations in Deltakit's stim and deltakit-stim dialects."""
        for instr in circuit:
            if isinstance(instr, _NamedRepeat):
                self._translate_repeat(instr)
            elif AnnotationEnum.contains(instr.name):
                self._translate_annotation(instr)
            elif MeasurementEnum.contains(instr.name):
                self._translate_measurement(instr)
            elif ResetEnum.contains(instr.name):
                self._translate_reset(instr)
            elif instr.name == "MPP":
                self._translate_mpp(instr)
            elif SingleQubitUnitaryEnum.contains(instr.name):
                self._translate_single_qubit_gate(instr)
            elif TwoQubitUnitaryEnum.contains(instr.name):
                self._translate_two_qubit_gate(instr)
            elif NoiseEnum.contains(instr.name):
                self._translate_noise(instr)
            elif LeakageEnum.contains(instr.name):
                self._translate_leakage(instr)
            else:
                self._raise_unknown_instr_error(instr)

    def to_xdsl_dialect(self) -> ModuleOp:
        """Translate the Deltakit-Stim circuit to Deltakit's stim and deltakit-stim dialects."""
        self._translate_circuit(self.circuit)
        return self.circuit_op
