# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Trackers for tracing qubit and measurement SSA values."""

import itertools
from collections.abc import Iterable, Sequence
from typing import cast

from typing_extensions import Self, override
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Operation, SSAValue

from deltakit_compile.dialects import qcore, qref, qstruct, scf
from deltakit_compile.dialects import stabiliser as stab


class QubitMeasurementTracker:
    """Tracks the qubits associated with qubit registers, stab.state, and measurement SSA values
    through circuits and control flow.

    The supported operations through which qubits and measurements are tracked are:
      - qcore.alloc_qubit
      - qcore.pack_qubit_reg
      - qcore.unpack_qubit_reg
      - qcore.concatenate
      - qcore.split
      - qref.measure
      - qstruct.circuit
      - stab.state.make
      - stab.state.cast
      - stab.circuit
      - qstruct.parallel
      - scf.if
      - scf.index_switch

    Keeps track of qubits using an internal qubit numbering. This is separate from the optional id
    (from qcore.alloc_qubit) which may also be present on each qubit.
    """

    def __init__(self) -> None:
        self._next_qubit_num = 0

        # SSAValues for individual qubits to possible qubit numbers.
        self._qubit_ssa_to_qubit_num = dict[SSAValue, set[int]]()
        # SSAValues for qubit registers to the possible qubit numbers for each of their qubits.
        self._register_ssa_to_qubit_nums = dict[SSAValue, tuple[set[int], ...]]()
        # SSAValues for stab.states to the possible qubit numbers for each of their qubits.
        self._state_ssa_to_qubit_nums = dict[SSAValue, tuple[set[int], ...]]()
        # SSAValues for measurements to their possible qubit numbers.
        self._meas_ssa_to_qubit_nums = dict[SSAValue, set[int]]()

    def get_tracked_qubit_ssas(self) -> Iterable[SSAValue]:
        """Get all qubit SSA values which are tracked."""
        return self._qubit_ssa_to_qubit_num.keys()

    def get_tracked_register_ssas(self) -> Iterable[SSAValue]:
        """Get all qubit register SSA values which are tracked."""
        return self._register_ssa_to_qubit_nums.keys()

    def get_tracked_state_ssas(self) -> Iterable[SSAValue]:
        """Get all stab.state SSA values which are tracked."""
        return self._state_ssa_to_qubit_nums.keys()

    def get_tracked_measurement_ssas(self) -> Iterable[SSAValue]:
        """Get all measurement SSA values which are tracked."""
        return self._meas_ssa_to_qubit_nums.keys()

    def get_possible_qubit_nums(self, qubit_ssa: SSAValue) -> set[int]:
        """Get the set of qubit numbers which may be associated with the given qubit SSA value."""
        try:
            return self._qubit_ssa_to_qubit_num[qubit_ssa]
        except KeyError:
            msg = f"Qubit SSA value not registered: {qubit_ssa}"
            raise ValueError(msg) from None

    def get_possible_qubit_nums_from_register(self, reg_ssa: SSAValue) -> tuple[set[int], ...]:
        """Get the set of qubit numbers which may be associated with each qubit in the given qubit
        register SSA value."""
        try:
            return self._register_ssa_to_qubit_nums[reg_ssa]
        except KeyError:
            msg = f"Qubit register SSA value not registered: {reg_ssa}"
            raise ValueError(msg) from None

    def get_possible_qubit_nums_from_state(self, state_ssa: SSAValue) -> tuple[set[int], ...]:
        """Get the set of qubit numbers which may be associated with each qubit in the given
        stab.state SSA value."""
        try:
            return self._state_ssa_to_qubit_nums[state_ssa]
        except KeyError:
            msg = f"Stabiliser state SSA value not registered: {state_ssa}"
            raise ValueError(msg) from None

    def get_possible_qubit_nums_from_meas(self, meas_ssa: SSAValue) -> set[int]:
        """Get the set of qubit numbers which the given measurement SSA value might represent a
        measurement of."""
        try:
            return self._meas_ssa_to_qubit_nums[meas_ssa]
        except KeyError:
            msg = f"Measurement SSA value not registered: {meas_ssa}"
            raise ValueError(msg) from None

    def is_measurement(self, ssa: SSAValue) -> bool:
        """Check if the given SSA value is a registered measurement."""
        return ssa in self.get_tracked_measurement_ssas()

    def _new_qubit_num(self) -> int:
        """Generate a new internal qubit number."""
        qubit_num = self._next_qubit_num
        self._next_qubit_num += 1
        return qubit_num

    @classmethod
    def walk_module(cls, module_op: ModuleOp) -> Self:
        """Initialise a qubit tracker by walking the given module."""
        tracker = cls()
        tracker._walk(module_op)
        return tracker

    def _walk(self, op: Operation) -> None:
        self._before_walking_children(op)

        for region in op.regions:
            for block in region.blocks:
                for inner_op in block.ops:
                    self._walk(inner_op)

        self._after_walking_children(op)

        self.process_operation(op)

    def _before_walking_children(self, op: Operation) -> None:
        if isinstance(op, qcore.AllocQubitOp):
            self._on_qubit_alloc(op)
        elif isinstance(op, qcore.PackQubitRegOp):
            self._on_qubit_pack(op.reg, op.qubits)
        elif isinstance(op, qcore.UnpackQubitRegOp):
            self._on_qubit_unpack(op.qubits, op.reg)
        elif isinstance(op, qcore.ConcatenateOp):
            self._on_qubit_concatenate(op.out_reg, op.in_regs)
        elif isinstance(op, qcore.SplitOp):
            self._on_qubit_split(op.out_regs, op.in_reg)
        elif isinstance(op, qstruct.CircuitOp):
            self._before_walking_circuit_op(op)
        elif isinstance(op, stab.StateMakeOp):
            self._on_state_make(op.input_qubits, op.output)
        elif isinstance(op, stab.StateCastOp):
            self._propagate_state(op.input, op.output)
        elif isinstance(op, stab.CircuitOp):
            self._before_walking_stab_circuit_op(op)
        elif isinstance(op, qref.MeasureOp):
            for qubit, meas in zip(op.qubits, op.measurements, strict=True):
                self._on_measure(qubit, meas)

    def _after_walking_children(self, op: Operation) -> None:
        if isinstance(op, qstruct.CircuitOp):
            self._after_walking_circuit_op(op)
        elif isinstance(op, stab.CircuitOp):
            self._after_walking_stab_circuit_op(op)
        elif isinstance(op, qstruct.ParallelOp):
            self._after_walking_parallel_op(op)
        elif isinstance(op, (scf.IfOp, scf.IndexSwitchOp)):
            self._after_walking_branching_op(op)

    def _before_walking_circuit_op(self, op: qstruct.CircuitOp) -> None:
        for block_arg, input_arg in zip(op.body.block.args, op.args, strict=True):
            if isinstance(input_arg.type, qcore.QubitType):
                self._propagate_qubit(input_arg, block_arg)
            elif isinstance(input_arg.type, qcore.QubitRegType):
                self._propagate_qubit_register(input_arg, block_arg)
            elif self.is_measurement(input_arg):
                self._propagate_measurement(input_arg, block_arg)

    def _after_walking_circuit_op(self, op: qstruct.CircuitOp) -> None:
        for yield_operand, output_arg in zip(op.yield_op.operands, op.results, strict=True):
            if isinstance(output_arg.type, qcore.QubitType):
                self._propagate_qubit(yield_operand, output_arg)
            elif isinstance(output_arg.type, qcore.QubitRegType):
                self._propagate_qubit_register(yield_operand, output_arg)
            elif self.is_measurement(yield_operand):
                self._propagate_measurement(yield_operand, output_arg)

    def _before_walking_stab_circuit_op(self, op: stab.CircuitOp) -> None:
        # Assume stab.states and qubits are not passed through circuit other block args.
        self._on_state_unmake(op.input, op.qubit_block_args)
        self._propagate_state(op.input, op.output)
        for block_arg, input_arg in zip(op.other_block_args, op.input_args, strict=True):
            if self.is_measurement(input_arg):
                self._propagate_measurement(input_arg, block_arg)

    def _after_walking_stab_circuit_op(self, op: stab.CircuitOp) -> None:
        # Assume stab.states and qubits are not passed through circuit operands.
        for yield_operand, output_arg in zip(op.yield_op.arguments, op.output_args, strict=True):
            if self.is_measurement(yield_operand):
                self._propagate_measurement(yield_operand, output_arg)

    def _after_walking_parallel_op(self, op: qstruct.ParallelOp) -> None:
        all_yield_operands = itertools.chain.from_iterable(
            cast(qstruct.YieldOp, region.block.last_op).operands for region in op.par_regions
        )
        for result, yield_operand in zip(op.res, all_yield_operands, strict=True):
            ret_type = result.type
            assert ret_type == yield_operand.type
            if isinstance(ret_type, qcore.QubitType):
                self._propagate_qubit(yield_operand, result)
            elif isinstance(ret_type, qcore.QubitRegType):
                self._propagate_qubit_register(yield_operand, result)
            elif isinstance(ret_type, stab.StateType):
                self._propagate_state(yield_operand, result)
            elif self.is_measurement(yield_operand):
                self._propagate_measurement(yield_operand, result)

    def _after_walking_branching_op(self, op: scf.IfOp | scf.IndexSwitchOp) -> None:
        # Iterate simultaneously over the results and the yields from each branch.
        all_branch_yields = [
            cast(qstruct.YieldOp, region.block.last_op).operands for region in op.regions
        ]
        for result, *branch_yields in zip(op.output, *all_branch_yields, strict=True):
            ret_type = result.type
            assert all(ret_type == yield_operand.type for yield_operand in branch_yields)
            if isinstance(ret_type, qcore.QubitType):
                self._merge_qubit(branch_yields, result)
            elif isinstance(ret_type, qcore.QubitRegType):
                self._merge_qubit_register(branch_yields, result)
            elif isinstance(ret_type, stab.StateType):
                self._merge_state(branch_yields, result)
            elif any(self.is_measurement(operand) for operand in branch_yields):
                self._merge_measurement(branch_yields, result)

    def _on_qubit_alloc(self, alloc_op: qcore.AllocQubitOp) -> None:
        """Record the allocation of a qubit."""
        for qubit_ssa in alloc_op.result:
            if isinstance(qubit_ssa.type, qcore.QubitRegType):
                self._register_ssa_to_qubit_nums[qubit_ssa] = tuple(
                    {self._new_qubit_num()} for _ in range(len(qubit_ssa.type))
                )
            else:  # single qubit
                self._qubit_ssa_to_qubit_num[qubit_ssa] = {self._new_qubit_num()}

    def _on_qubit_pack(self, reg_ssa: SSAValue, qubits: Iterable[SSAValue]) -> None:
        """Record packing several qubits into a qubit register."""
        self._register_ssa_to_qubit_nums[reg_ssa] = tuple(
            self.get_possible_qubit_nums(qubit_ssa) for qubit_ssa in qubits
        )

    def _on_qubit_unpack(self, qubits: Iterable[SSAValue], reg_ssa: SSAValue) -> None:
        """Record unpacking several qubits from a qubit register."""
        qubit_num_lists = self._register_ssa_to_qubit_nums[reg_ssa]
        for qubit_ssa, qubit_nums in zip(qubits, qubit_num_lists, strict=True):
            self._qubit_ssa_to_qubit_num[qubit_ssa] = qubit_nums

    def _on_qubit_concatenate(self, new_reg_ssa: SSAValue, reg_ssas: Iterable[SSAValue]) -> None:
        """Record concatenating several qubit registers into a new qubit register."""
        reg_qubit_num_lists = [
            self.get_possible_qubit_nums_from_register(reg_ssa) for reg_ssa in reg_ssas
        ]
        self._register_ssa_to_qubit_nums[new_reg_ssa] = tuple(
            itertools.chain.from_iterable(reg_qubit_num_lists)
        )

    def _on_qubit_split(self, new_reg_ssas: Iterable[SSAValue], reg_ssa: SSAValue) -> None:
        """Record splitting a qubit register into several new qubit registers."""
        reg_qubit_num_list = self.get_possible_qubit_nums_from_register(reg_ssa)

        # The list of sets of possible qubit numbers for each new register.
        new_reg_to_qubit_num_lists = list[Sequence[set[int]]]()
        idx = 0
        for new_reg_ssa in new_reg_ssas:
            num_new_reg_qubits = len(cast(qcore.QubitRegType, new_reg_ssa.type))
            new_reg_to_qubit_num_lists.append(reg_qubit_num_list[idx : idx + num_new_reg_qubits])
            idx += num_new_reg_qubits

        for new_reg_ssa, new_reg_qubit_num_list in zip(
            new_reg_ssas, new_reg_to_qubit_num_lists, strict=True
        ):
            self._register_ssa_to_qubit_nums[new_reg_ssa] = tuple(new_reg_qubit_num_list)

    def _on_state_make(self, qubits: Iterable[SSAValue], state: SSAValue) -> None:
        """Record packing several qubits into a stab.state."""
        self._state_ssa_to_qubit_nums[state] = tuple(
            self.get_possible_qubit_nums(qubit_ssa) for qubit_ssa in qubits
        )

    def _on_state_unmake(self, state: SSAValue, qubits: Iterable[SSAValue]) -> None:
        """Record unpacking several qubits from a stab.state."""
        qubit_num_lists = self._state_ssa_to_qubit_nums[state]
        for qubit_ssa, qubit_nums in zip(qubits, qubit_num_lists, strict=True):
            self._qubit_ssa_to_qubit_num[qubit_ssa] = qubit_nums

    def _on_measure(self, qubit: SSAValue, meas: SSAValue) -> None:
        """Record measuring a qubit."""
        self._meas_ssa_to_qubit_nums[meas] = self.get_possible_qubit_nums(qubit)

    def _propagate_qubit(self, old_qubit: SSAValue, new_qubit: SSAValue) -> None:
        """Record a qubit propagating unchanged to a new SSA value."""
        self._qubit_ssa_to_qubit_num[new_qubit] = self.get_possible_qubit_nums(old_qubit)

    def _propagate_qubit_register(self, old_reg: SSAValue, new_reg: SSAValue) -> None:
        """Record a qubit register propagating unchanged to a new SSA value."""
        possible_qubit_nums = self.get_possible_qubit_nums_from_register(old_reg)
        self._register_ssa_to_qubit_nums[new_reg] = possible_qubit_nums

    def _propagate_state(self, old_state: SSAValue, new_state: SSAValue) -> None:
        """Record a stab.state propagating unchanged to a new SSA value."""
        self._state_ssa_to_qubit_nums[new_state] = self.get_possible_qubit_nums_from_state(
            old_state
        )

    def _propagate_measurement(self, old_meas: SSAValue, new_meas: SSAValue) -> None:
        """Record a measurement propagating unchanged to a new SSA value."""
        self._meas_ssa_to_qubit_nums[new_meas] = self.get_possible_qubit_nums_from_meas(old_meas)

    def _merge_qubit(self, branch_qubits: list[SSAValue], new_qubit: SSAValue) -> None:
        """Record several possible qubits propagating unchanged to a new SSA value."""
        branch_possible_qubit_nums = [
            self.get_possible_qubit_nums(branch_qubit) for branch_qubit in branch_qubits
        ]
        self._qubit_ssa_to_qubit_num[new_qubit] = set().union(*branch_possible_qubit_nums)

    def _merge_possible_qubit_tuples(
        self, branch_to_qubit_to_possible_nums: list[tuple[set[int], ...]]
    ) -> tuple[set[int], ...]:
        """Merge several tuples of sets of possible qubit numbers (e.g., from different branches)
        into a single tuple of sets of possible qubit numbers."""
        num_qubits = len(branch_to_qubit_to_possible_nums[0])
        assert all(
            len(qubit_to_possible_nums) == num_qubits
            for qubit_to_possible_nums in branch_to_qubit_to_possible_nums
        )

        # The list of sets of possible qubit numbers for each qubit in each branch.
        qubit_to_branch_to_possible_nums = [
            [
                qubit_to_possible_nums[qubit_idx]
                for qubit_to_possible_nums in branch_to_qubit_to_possible_nums
            ]
            for qubit_idx in range(num_qubits)
        ]

        # Merge the possible qubit numbers for each qubit in turn across all branches.
        return tuple(
            set().union(*branch_to_possible_nums)
            for branch_to_possible_nums in qubit_to_branch_to_possible_nums
        )

    def _merge_state(self, branch_states: list[SSAValue], new_state: SSAValue) -> None:
        """Record several possible stab.states propagating unchanged to a new SSA value."""
        # The list of sets of possible qubit numbers for each branch's state.
        branch_to_qubit_to_possible_nums = [
            self.get_possible_qubit_nums_from_state(branch_state) for branch_state in branch_states
        ]
        self._state_ssa_to_qubit_nums[new_state] = self._merge_possible_qubit_tuples(
            branch_to_qubit_to_possible_nums
        )

    def _merge_qubit_register(self, branch_states: list[SSAValue], new_state: SSAValue) -> None:
        """Record several possible qubit registers propagating unchanged to a new SSA value."""
        # The list of sets of possible qubit numbers for each branch's register.
        branch_to_qubit_to_possible_nums = [
            self.get_possible_qubit_nums_from_register(branch_state)
            for branch_state in branch_states
        ]
        self._register_ssa_to_qubit_nums[new_state] = self._merge_possible_qubit_tuples(
            branch_to_qubit_to_possible_nums
        )

    def _merge_measurement(self, branch_meas: list[SSAValue], new_meas: SSAValue) -> None:
        """Record several possible measurements propagating unchanged to a new SSA value.
        Ignore any SSA values that don't correspond to measurements (such as padding)."""
        branch_possible_qubit_nums = [
            self.get_possible_qubit_nums_from_meas(branch_measurement)
            for branch_measurement in branch_meas
            if self.is_measurement(branch_measurement)
        ]
        self._meas_ssa_to_qubit_nums[new_meas] = set().union(*branch_possible_qubit_nums)

    def process_operation(self, op: Operation) -> None:
        """Process an operation while walking a module.

        May be overridden by subclasses. Called after all tracking done by the base class has been
        performed for the operation. Parents are processed after their children.
        """


class QubitMeasurementCoordinateTracker(QubitMeasurementTracker):
    """Tracks the measurements associated with SSA values and their qubits' locations."""

    def __init__(self) -> None:
        super().__init__()
        self._qubit_num_to_coord: dict[int, qcore.QubitCoordinateAttr] = {}

    def get_possible_measurement_coords(
        self, meas_ssa: SSAValue
    ) -> list[qcore.QubitCoordinateAttr]:
        """Get a list of possible qubit coords for a given measurement SSA value, ignoring any
        possible measurements that do not have a recorded coordinate."""
        qubit_nums = self.get_possible_qubit_nums_from_meas(meas_ssa)
        return [
            self._qubit_num_to_coord[qubit_num]
            for qubit_num in qubit_nums
            if qubit_num in self._qubit_num_to_coord
        ]

    @override
    def process_operation(self, op: Operation) -> None:
        if isinstance(op, qcore.AllocQubitOp) and op.coords is not None:
            for qubit in op.result:
                if isinstance(qubit.type, qcore.QubitType):
                    coord = op.get_qubit_coordinate(cast(SSAValue[qcore.QubitType], qubit))
                    assert coord is not None

                    # There's only one possible number because the qubit has just been allocated
                    (qubit_num,) = self.get_possible_qubit_nums(qubit)
                    self._qubit_num_to_coord[qubit_num] = coord
                else:  # qubit registers
                    qubit_reg = cast(SSAValue[qcore.QubitRegType], qubit)
                    qubit_nums = self.get_possible_qubit_nums_from_register(qubit_reg)

                    # Again, there's only one possible number for each qubit
                    for idx, (qubit_num,) in enumerate(qubit_nums):
                        coord = op.get_qubit_coordinate(qubit_reg, idx)
                        assert coord is not None
                        self._qubit_num_to_coord[qubit_num] = coord
