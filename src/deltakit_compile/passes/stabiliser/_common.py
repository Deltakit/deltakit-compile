# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Common functionality for the stabiliser flow dialect."""

from __future__ import annotations

import bisect
import enum
import functools
import itertools
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import ClassVar, Final, TypeAlias, cast

import numpy as np
from xdsl.dialects.builtin import I1, ArrayAttr
from xdsl.ir import Operation, SSAValue, SSAValues
from xdsl.pattern_rewriter import PatternRewriter

from deltakit_compile.dialects import qcore, qec, qref, qstruct
from deltakit_compile.dialects.stabiliser import (
    CircuitOp,
    FlowAttr,
    StateMakeOp,
    StatePermuteOp,
    StateType,
)
from deltakit_compile.exceptions import BadUserFlowError
from deltakit_compile.passes.stabiliser._existing_detectors import (
    ExistingDetectors,
    add_detectors_if_independent,
)
from deltakit_compile.utilities.ordered_set import OrderedSet
from deltakit_compile.utilities.ssa_scoping import extract_value_from_inner_ops

# region Common verification methods


def verify_circuit_flows_present(op: CircuitOp) -> None:
    """Verify that the circuit has flows specified for all its input and output flow states.
    Note: does not check that the flows are actually valid over the circuit body.
    Treats a nonexistent flow annotation like an empty list of flows."""
    flows = op.flows if op.flows is not None else []

    flow_input_indices = {flow.input_state_index for flow in flows if not flow.is_creation_flow}
    flow_output_indices = {
        flow.output_state_index for flow in flows if not flow.is_destruction_flow
    }

    # Every flow state in the input and output stab.state must be used in the flows
    missing_inputs = set(range(len(op.input_flows))) - flow_input_indices
    missing_outputs = set(range(len(op.output_flows))) - flow_output_indices

    if missing_inputs or missing_outputs:
        # TODO: Improve error message with span pointing to the circuit
        msg = (
            "Some flows which are specified on neighbouring circuits are missing on this circuit.\n"
        )
        if missing_inputs:
            missing_input_states = [op.input_flows[i] for i in missing_inputs]
            msg += (
                "Missing flows starting with stabilisers: "
                f"{qcore.PauliStringAttr.collection_as_str(missing_input_states)}.\n"
            )
        if missing_outputs:
            missing_output_states = [op.output_flows[i] for i in missing_outputs]
            msg += (
                "Missing flows ending with stabilisers: "
                f"{qcore.PauliStringAttr.collection_as_str(missing_output_states)}.\n"
            )
        msg += (
            "Please add these flows, remove the corresponding stabilisers from the neighbouring "
            "circuits, or enable automatic flow generation."
        )
        raise BadUserFlowError(msg)


# endregion

# region Methods for algebra of flow states


@dataclass(frozen=True)
class LinDepFlowStates:
    """Result of searching for linear dependencies among flow states.

    Attributes:
        flow_states: Unflagged flow states that can be removed.
        lin_dependencies: Sets of flow states whose product is the identity.
    """

    flow_states: set[qcore.PauliStringAttr]
    lin_dependencies: set[frozenset[qcore.PauliStringAttr]]


def _row_reduce_bool_inplace(table: np.ndarray) -> None:
    """In-place row reduction of a boolean matrix to RREF using GF(2) arithmetic (XOR).

    Args:
        table: A 2D numpy boolean array to row-reduce in place. Must be of dtype np.bool_.
    """
    assert table.dtype == np.bool_, "Input table must be a boolean numpy array."
    nrows, ncols = table.shape
    pivot_row = 0
    for col in range(ncols):
        # Find pivot in this column
        found = -1
        for r in range(pivot_row, nrows):
            if table[r, col]:
                found = r
                break
        if found == -1:
            continue
        # Swap rows if needed
        if found != pivot_row:
            table[[pivot_row, found]] = table[[found, pivot_row]]
        # Eliminate all other rows with a 1 in this column (vectorized)
        mask = table[:, col].copy()
        mask[pivot_row] = False
        table[mask] ^= table[pivot_row]
        pivot_row += 1


def check_row_in_span(basis_matrix: np.ndarray, row: np.ndarray) -> np.ndarray | None:
    """Check whether a row is in the span, modulo 2, of the rows of the basis matrix.

    Method: Creates a table of shape [N+1, M+N+1] of form
    (                |        )
    (    basis table |  I     )
    (----------------|        )
    (        row     |        )
    and performs row reduction. The original row is in the span of basis iff there is a row [M+N+1],
    partitioned into 3 parts of size [M | N | 1], such that the first M elements are all 0, and the
    final element is a 1. The linear combination is given by the 'middle chunk' of columns: the N
    elements corresponding to indicators of the basis rows.

    Uses numpy boolean arrays for fast GF(2) arithmetic via XOR.

    Args:
        basis_matrix: A binary matrix (np.bool_) of shape [N, M].
        row: A binary vector (np.bool_) of shape [M].

    Returns:
        If row is in the span, returns a bool vector of shape [N] describing which linear
        combination of rows of the basis matrix combine to make the given row. Else, returns None.

    Raises:
        ValueError: If the size of the row is not compatible with the basis matrix.
    """
    basis_rows, basis_cols = basis_matrix.shape
    if row.shape[0] != basis_cols:
        msg = "Row and basis matrix given have different row lengths."
        raise ValueError(msg)

    table = np.zeros((basis_rows + 1, basis_cols + basis_rows + 1), dtype=np.bool_)

    # Fill left block with basis rows
    if basis_rows > 0:
        table[:basis_rows, :basis_cols] = np.asarray(basis_matrix, dtype=np.bool_)
        # Add identity in the middle block (top N rows)
        for idx in range(basis_rows):
            table[idx, basis_cols + idx] = True
    # Append the target row and set the final indicator column
    table[basis_rows, :basis_cols] = np.asarray(row, dtype=np.bool_)
    table[basis_rows, basis_cols + basis_rows] = True

    _row_reduce_bool_inplace(table)

    for idx in range(basis_rows + 1):
        # Check first M columns of row are all 0 and final column is 1
        if not np.any(table[idx, :basis_cols]) and table[idx, -1]:
            # Return linear combination of rows in basis (middle block)
            return table[idx, basis_cols : basis_cols + basis_rows]
    return None


def find_linearly_dependent_rows(
    matrix: np.ndarray, flag_idx: int
) -> tuple[set[int], set[frozenset[int]]]:
    """Find linear dependencies among the rows of a GF(2) matrix.

    A row is defined as *flagged* if its index is >= `flag_idx`.
    Only unflagged rows will be considered for removal.

    Returns indices of unflagged rows that can be removed and sets of
    row indices that are linearly dependent (i.e. sum to the zero row).
    Earlier entries in the matrix are preferred for removal.

    Method:
    - Augment the matrix on the right with an identity matrix.
    - Row-reduce the augmented matrix.
    - Any row whose left block is all zeros corresponds to a linear
      dependency described by the nonzero entries in the right block.
    """
    num_rows, num_cols = matrix.shape
    identity_matrix = np.identity(num_rows, dtype=np.bool_)
    extended = np.concatenate((matrix, identity_matrix), axis=1)
    _row_reduce_bool_inplace(extended)

    # search through rows for indices
    unflagged_to_remove: set[int] = set()
    lin_dep_sets: set[frozenset[int]] = set()
    for row_idx in range(extended.shape[0]):
        left = extended[row_idx, :num_cols]
        if not np.any(left):
            # found a redundancy - find vector corresponding to linear combination
            right = extended[row_idx, num_cols:]
            idxs: list[int] = np.nonzero(right)[0].tolist()
            lin_dep_sets.add(frozenset(idxs))
            if idxs and (i := min(idxs)) < flag_idx:
                unflagged_to_remove.add(i)
    return unflagged_to_remove, lin_dep_sets


class MatchFlows:
    """Class of linear algebra methods for manipulating flow states."""

    # Cache PauliAttr objects to avoid repeated construction
    _PAULI_X: Final[qcore.PauliAttr] = qcore.PauliAttr.X()
    _PAULI_Y: Final[qcore.PauliAttr] = qcore.PauliAttr.Y()
    _PAULI_Z: Final[qcore.PauliAttr] = qcore.PauliAttr.Z()

    @staticmethod
    def flow_state_symplectic(
        num_qubits: int, flow_states: list[qcore.PauliStringAttr]
    ) -> np.ndarray:
        """Computes the symplectic representation a list of flow state stabilisers.

        Args:
            num_qubits: The number of qubits in the flow states.
                Must be larger than the maximum qubit index in any of the flow states.
            flow_states: The flow states to represent in symplectic form.

        Returns:
            A numpy bool array of shape [len(flow_states), 2*num_qubits] in which row i is the
                symplectic representation of flow_states[i].
        """
        table = np.zeros((len(flow_states), num_qubits * 2), dtype=np.bool_)
        for state_index, flow_state in enumerate(flow_states):
            for qb in flow_state.qubit_states.data:
                if qb.pauli_state in (MatchFlows._PAULI_X, MatchFlows._PAULI_Y):
                    table[state_index, qb.qubit_index] = True
                if qb.pauli_state in (MatchFlows._PAULI_Z, MatchFlows._PAULI_Y):
                    table[state_index, qb.qubit_index + num_qubits] = True
        return table

    @staticmethod
    def find_linear_transform(
        old_flow_states: list[qcore.PauliStringAttr],
        new_flow_states: list[qcore.PauliStringAttr],
    ) -> tuple[np.ndarray, list[int]]:
        """Find a linear combination of old flow states for each new flow state as a matrix with
        elements in GF(2).

        If there are A old flow states and B new flow states, then the transform matrix will have B
        rows of length A. Rows will give linear combination of old flow states to produce
        corresponding new state.

        Note that the identity row is in the span of any basis and so will have a coefficient row of
        all zeros but will not appear in not_in_span.

        Args:
            old_flow_states: Collection of flow states forming a (not necessarily independent)
                spanning set.
            new_flow_states: Collection of target flow states to express as linear combinations.

        Returns:
            transform: A matrix over GF(2) (i.e. np.bool_) of shape [B, A].
                Row i gives coefficients (mod 2) over old_flow_states that produce
                new_flow_states[i]. If a new row is not in the span, its coefficient row is all 0s.
            not_in_span: A list of indices of rows of new_flow_states that are not representable as
                a linear combination of old_flow_states.

        Raises:
            ValueError: when either input list is empty, or old_flow_states contains the identity.
        """
        if not old_flow_states or not new_flow_states:
            msg = "Both lists of flow states provided must be non-empty."
            raise ValueError(msg)
        if any(ofs.is_identity() for ofs in old_flow_states):
            msg = "Old flow states should not contain the identity."
            raise ValueError(msg)

        # normalise number of qubits over all old and new states
        num_qubits = (
            max(state.get_max_qubit_index() for state in old_flow_states + new_flow_states) + 1
        )
        basis_table = MatchFlows.flow_state_symplectic(num_qubits, old_flow_states)
        new_table = MatchFlows.flow_state_symplectic(num_qubits, new_flow_states)

        new_rows = new_table.shape[0]
        transform = np.zeros((new_rows, basis_table.shape[0]), dtype=np.bool_)
        not_in_span: list[int] = []

        for i in range(new_rows):
            v = new_table[i, :]
            row_span_comb = check_row_in_span(basis_matrix=basis_table, row=v)
            if row_span_comb is not None:
                # new row is combination of old rows
                transform[i, :] = row_span_comb
            else:
                not_in_span.append(i)  # transform row already all 0s
        return transform, not_in_span

    @staticmethod
    def find_linearly_dependent_flow_states_with_flags(
        flow_states: list[qcore.PauliStringAttr], flag_idx: int
    ) -> LinDepFlowStates:
        """Returns set of unflagged flow states that can be removed due to
        linear dependence, possibly with flagged flow states, and
        any sets of flow states whose elements multiply to the identity.

        A flow state in the list given is defined as flagged if its index
        in the list is greater than or equal to the flag_idx given.

        An error is raised if the input flow state list contains
        an identity flow state.

        Note that this method finds a single solution to this problem
        in such a way that flow states appearing earlier in the list
        are eliminated with priority over those later.

        Example: suppose one has flow states A, AB, C, CD, CDE, E
        and one wants to remove linearly dependent flow states, but wants to
        preserve i.e. AB and CDE, one could flag AB and CDE by inputting the
        list [A, C, CD, E, AB, CDE] with flag_idx = 4 to solve the problem.
        The output would be (C, {C, CD, CDE, E}) here - which means that we
        should remove C to form a linearly independent set.
        """
        if not flow_states:
            return LinDepFlowStates(flow_states=set(), lin_dependencies=set())
        if any(state.is_identity() for state in flow_states):
            msg = "Flow state list given contains an identity state which is not supported."
            raise ValueError(msg)
        num_qubits = max(f.get_max_qubit_index() for f in flow_states) + 1
        symplectic_table = MatchFlows.flow_state_symplectic(num_qubits, flow_states)
        unflagged_to_remove, lin_dependencies = find_linearly_dependent_rows(
            symplectic_table, flag_idx
        )
        return LinDepFlowStates(
            flow_states={flow_states[i] for i in unflagged_to_remove},
            lin_dependencies={
                frozenset(flow_states[i] for i in dep_set) for dep_set in lin_dependencies
            },
        )


# endregion
# region Methods to account for branching of flows


MMTResults: TypeAlias = OrderedSet[SSAValue[I1]]
"""Measurement results - a set of I1 SSAValues accumulated from measurement gates."""


@dataclass(frozen=True)
class CurrentState:
    """A single branch's flow state and its measurement SSA history.

    Each measurement gate produces a MMTResults as readout. The `mmt_ssa` parameter stores a
    collection of MMTResults as the `flow_state` is propagated through a sequence of gates. The
    order of these results does not matter as only the sum of measurements is important in finding
    detectors.

    We assume that there is a linearly independent basis of flow chains that is being propagated,
    and this CurrentState represents the continuation of one or more of these flow chains or a
    creation flow. We assume each flow chain has a unique integer ID. `extending_combination`
    stores a set of those integer IDs which identifies which linear combination of flow chains are
    being continued by this CurrentState.

    A non-empty set means this state continues the specified linear combination of existing chains:
        A0 -> ... -> An -> B.
    An empty set represents a new creation chain:
        I -> ... -> I -> B.
    """

    flow_state: qcore.PauliStringAttr
    mmt_ssa: MMTResults | None

    extending_combination: frozenset[int] = frozenset()
    """Set of IDs of flow chains from a background basis that this state continues.
    An empty set means this is a new creation chain."""

    is_annotated_flow: bool = False
    """Whether the flow chain extension represented by this state is user-annotated, i.e. the final
    state of the flow chain is a user-specified flow. If so, it's treated as a user flow with a last
    user flow age of -1 regardless of the flow chains it extends, because the last user
    flow is the flow state itself (which is at "position -1" in the chain).

    Note on terminology: A user flow chain is a flow chain that has a user-annotated flow somewhere
    in it, while `is_annotated_flow=True` means that the final flow in the extended flow chain
    represented by this state is user-annotated.
    """

    @property
    def newly_created(self) -> bool:
        """Whether this is the new state of a new creation chain (extending no existing chains)."""
        return not self.extending_combination

    def __mul__(self, other: CurrentState) -> CurrentState:
        """Multiply two CurrentState objects via multiplication of their PauliStringAttr components
        and symmetric difference of their MMTResults and extending_combinations.
        """
        flow_state = self.flow_state * other.flow_state
        extending_combination = self.extending_combination.symmetric_difference(
            other.extending_combination
        )
        if not self.mmt_ssa:
            return CurrentState(
                flow_state, other.mmt_ssa, extending_combination=extending_combination
            )
        if not other.mmt_ssa:
            return CurrentState(
                flow_state, self.mmt_ssa, extending_combination=extending_combination
            )
        return CurrentState(
            flow_state,
            self.mmt_ssa.symmetric_difference(other.mmt_ssa),
            extending_combination=extending_combination,
        )

    @property
    def num_measurements(self) -> int:
        return len(self.mmt_ssa) if self.mmt_ssa is not None else 0

    @classmethod
    def detector(cls, mmt_ssa: MMTResults, num_qubits: int) -> CurrentState:
        """Construct a CurrentState representing a detector with the given measurement history."""
        return cls(
            flow_state=qcore.PauliStringAttr.identity(num_qubits),
            mmt_ssa=mmt_ssa,
            extending_combination=frozenset(),
        )

    @classmethod
    def identity(cls, num_qubits: int) -> CurrentState:
        """Construct a CurrentState representing the identity flow state with no measurements."""
        return cls(
            flow_state=qcore.PauliStringAttr.identity(num_qubits),
            mmt_ssa=None,
            extending_combination=frozenset(),
        )


@dataclass(frozen=True)
class FlowChainInfo:
    """The information about a flow chain needed for propagation to continue it.

    Includes the end state of the chain and extra information needed for correctness or heuristics.
    """

    flow_state: qcore.PauliStringAttr
    """The end state of the flow chain being continued."""

    age: int = 1
    """The age of the flow chain, i.e. its length removing initial identity flow states.
    Needed for correctness: if an older and a younger flow chain are multiplied, the older chain
    must be discarded to avoid duplicate flow states earlier in the chain. For example, if we have:
        (1): A -> B -> C
        (2): I -> D -> E
    If we multiply (1) and (2), we get:
        (3): A -> BD -> CE
    which duplicates (1) in the first step, so we have to discard (1).
    """

    last_user_flow_age: int | None = None
    """The age of the last user-specified flow in the chain, or None if there are no user flows.
    Needed for correctness: we must be careful to avoid disrupting user-specified flows when
    multiplying flow chains. For example, if we have:
        (1): A -> B -> C -> D with last_user_flow_age = 1 (B -> C is user-specified)
    then we are not allowed to multiply (1) with a flow chain of age > 1, e.g.
        (2): E -> F -> G -> H
        (3): I -> F -> G -> H
        (4): I -> I -> G -> H
    because the result would disrupt the user-specified flow B -> C. However we can multiply (1)
    with flow chains of age <= 1, e.g.
        (5): I -> I -> I -> H
    because doing so does not change the user-specified flow B -> C.
    """

    chain_measurements: int = 0
    """The number of measurements in the flow chain being continued, used for heuristics."""

    @property
    def is_user_flow(self) -> bool:
        return self.last_user_flow_age is not None


class FlowInSpanStatus(enum.Enum):
    """Status of a check of whether a flow state is in the span of the current flow states."""

    IN_SPAN = "in_span"
    FLOW_STATE_NOT_IN_SPAN = "flow_state_not_in_span"
    MEASUREMENTS_NOT_IN_SPAN = "measurements_not_in_span"


@dataclass(frozen=True)
class FlowInSpanResult:
    """Result of checking whether a flow state is in the span of the current flow states.

    Attributes:
        status: Whether the check passed, and if not, why.
        flow_basis: A basis of valid flows. Populated only when status is FLOW_STATE_NOT_IN_SPAN.
    """

    status: FlowInSpanStatus
    flow_basis: tuple[CurrentState, ...] = ()


class CurrentStates:
    """A representation of the current flow states during the propagation of a single input flow
    state and their measurement history.

    We store four types of flows, where A is the input flow state and B is another flow state:
    - regular flows: A -> B
    - creation flows: I -> B
    - destruction flows: A -> I
    - detectors: I -> I

    We store only a basis of linearly independent flows to prevent exponential blowup.
    If the input flow state is the identity, some of these categories collapse and we have only
    creation flows and detectors. In this case, we count the identity as a flow state to be
    propagated so that the propagation of the identity flow state is always captured.

    Args:
        input_flow_basis: The basis of the space of input flow states to be propagated. Must be
            linearly independent. Note that the identity flow state is always in the span of every
            basis, so the identity flow state is always propagated (so creation flows and detectors
            are always found) and it should not be included in the input flow basis.
            If empty, only the identity flow state will be propagated.
        num_qubits: The number of qubits in the flow states. All flow states must have this number
            of qubits. Used in case the input flow basis is empty (so the identity is propagated).
        auto_reduce: If True, automatically reduce the current flow states to a linearly
            independent set when the number of propagating flows exceeds 2*num_qubits.
            Otherwise, the user must call `reduce()` manually.
    """

    def __init__(
        self,
        input_flow_basis: list[FlowChainInfo],
        num_qubits: int,
        *,
        auto_reduce: bool = True,
    ) -> None:
        self._input_basis_info = input_flow_basis
        self._num_qubits = num_qubits
        self._auto_reduce = auto_reduce

        if not all(info.flow_state.length.data == num_qubits for info in self._input_basis_info):
            msg = "All flow states in the input basis must have `num_qubits` qubits."
            raise ValueError(msg)

        self.propagating_flows: list[CurrentState] = []  # regular and creation flows
        self.destruction_flows: list[CurrentState] = []
        self.detectors: list[MMTResults] = []

        # We use this utility to maintain linearly independent detectors for now.
        self._existing_detectors = ExistingDetectors()

        for idx, basis_flow_info in enumerate(self._input_basis_info):
            self.propagating_flows.append(
                CurrentState(
                    basis_flow_info.flow_state, MMTResults(), extending_combination=frozenset({idx})
                )
            )

    @classmethod
    def from_flows(
        cls,
        num_qubits: int,
        input_flow_basis: list[FlowChainInfo],
        *,
        propagating_flows: list[CurrentState] | None = None,
        destruction_flows: list[CurrentState] | None = None,
        detectors: list[MMTResults] | None = None,
        auto_reduce: bool = True,
    ) -> CurrentStates:
        """Construct a CurrentStates with the given current flow states for testing purposes."""
        current_states = cls(input_flow_basis, num_qubits, auto_reduce=auto_reduce)
        current_states.propagating_flows = propagating_flows or []
        current_states.destruction_flows = destruction_flows or []
        for detector in detectors or []:
            current_states._add_detector(detector)
        return current_states

    def add_annotated_flow(
        self,
        flow_state: qcore.PauliStringAttr,
        mmt: MMTResults,
        flow_chain_info: FlowChainInfo | None,
    ) -> None:
        """Add a user-annotated flow to the current flow states so it can participate in reduction.
        If flow_chain_info is given, it is assumed to extend that chain, which is added to the
        basis. Otherwise it's assumed to be a creation flow."""

        if flow_chain_info is None:
            extending_combination = frozenset[int]()
        else:
            new_index = len(self._input_basis_info)
            extending_combination = frozenset({new_index})
            self._input_basis_info.append(flow_chain_info)

        new_state = CurrentState(
            flow_state, mmt, extending_combination=extending_combination, is_annotated_flow=True
        )
        self._add_flow(new_state)

    def _age(self, flow_state: CurrentState) -> int:
        """Return the age of the chain the given flow chain is extending."""
        return max(
            (self._input_basis_info[idx].age for idx in flow_state.extending_combination), default=0
        )

    def _total_measurements(self, flow_state: CurrentState) -> int:
        """Return the total number of measurements in the chain the given flow state is extending,
        including the measurements associated with the flow state itself."""
        return (
            sum(
                self._input_basis_info[idx].chain_measurements
                for idx in flow_state.extending_combination
            )
            + flow_state.num_measurements
        )

    def _last_user_flow_age(self, flow_state: CurrentState) -> int | None:
        """The age of the last user-specified flow in the chain that the given flow state is
        extending. If the flow state is a user-annotated flow, returns -1 (since the last user
        flow is the flow state itself, at "position -1" in the chain).

        If there are no user-specified flows in the chain, returns None.
        This method is careful to compute the last flow age correctly for flow states extending
        products of chains in the input flow basis.
        """
        if flow_state.is_annotated_flow:
            # The extension of the chain is a user flow, so it has a last user flow age of -1.
            return -1

        last_user_flow_age: int | None = None
        age = 0

        # Apply the flow chain multiplication rules for last_user_flow_age.
        for idx in flow_state.extending_combination:
            info = self._input_basis_info[idx]
            if info.last_user_flow_age is not None and info.last_user_flow_age >= age:
                last_user_flow_age = info.last_user_flow_age
            elif last_user_flow_age is not None and info.age > last_user_flow_age:
                last_user_flow_age = None
            age = max(age, info.age)

        return last_user_flow_age

    def _is_user_flow(self, flow_state: CurrentState) -> bool:
        """Whether the flow state is a user flow, i.e. it is either a user-annotated flow or extends
        a chain that has a user flow in it."""
        return self._last_user_flow_age(flow_state) is not None

    def get_all_states(self) -> Iterable[CurrentState]:
        """Iterate over the current basis of flow states, including all flow types including
        detectors."""
        yield from self.propagating_flows
        yield from self.destruction_flows
        for detector in self.detectors:
            yield CurrentState.detector(detector, self._num_qubits)

    def _add_flow(self, flow_state: CurrentState) -> None:
        """Add a flow state to the appropriate bucket depending on its type."""
        if flow_state.flow_state.is_identity():
            if flow_state.newly_created:
                # like I -> I: a detector
                self._add_detector(flow_state.mmt_ssa or MMTResults())
            else:
                # like A -> I: a destruction flow
                self.destruction_flows.append(flow_state)
        else:
            # like A -> B or I -> B: a propagating flow
            self.propagating_flows.append(flow_state)

    def _add_detector(self, detector: MMTResults) -> None:
        """Add a detector if it's linearly independent."""
        if not self._existing_detectors.in_span(detector):
            self.detectors.append(detector)
            self._existing_detectors.add_detector(detector)

    def _make_extension_matrix(
        self, flows: list[CurrentState], chain_order: list[int] | None = None
    ) -> np.ndarray:
        """Create a GF(2) matrix representing the extension combination sets of the given flows.

        Each row corresponds to a flow, and each column corresponds to an index in the input basis.
        A 1 in the matrix indicates that the flow extends the corresponding basis flow.

        chain_order controls the order of the columns in the matrix: column i corresponds to flow
        index chain_order[i]. By default, the columns are in the order of the input basis.
        """
        num_cols = len(self._input_basis_info)
        if chain_order is None:
            chain_idx_to_col = list(range(num_cols))
        else:
            chain_idx_to_col = [0] * num_cols
            for col_idx, chain_idx in enumerate(chain_order):
                chain_idx_to_col[chain_idx] = col_idx

        extension_matrix = np.zeros((len(flows), num_cols), dtype=np.bool_)
        for row_idx, cs in enumerate(flows):
            for chain_idx in cs.extending_combination:
                extension_matrix[row_idx, chain_idx_to_col[chain_idx]] = True
        return extension_matrix

    def _make_extension_vector(self, extending_combination: Iterable[int]) -> np.ndarray:
        """Create a GF(2) vector representing the given extension combination set.
        Same as _make_extension_matrix but for a single set."""
        extension_vector = np.zeros((len(self._input_basis_info),), dtype=np.bool_)
        for idx in extending_combination:
            extension_vector[idx] = True
        return extension_vector

    def check_in_span(self, flow_state: CurrentState) -> FlowInSpanResult:
        """Return a result describing whether the given flow state is in the span of the current
        flow states, and if not, why.

        Performs a reduction (`full_reduce()`) on the current states.
        """
        self.full_reduce()

        # After reduction, the end states of propagating flows are linearly independent. So there is
        # exactly one set of propagating flows that can produce the desired end state - find it.
        # built_up_approximation is a flow state in the span of the current flow states that we
        # build up incrementally to match flow_state.
        if flow_state.flow_state.is_identity():
            # The set producing the end state is empty, so short circuit to I -> I
            built_up_approximation = CurrentState.identity(self._num_qubits)
        else:
            # Guaranteed to be 1:1 after reduction
            end_state_to_propagating_flow = {cs.flow_state: cs for cs in self.propagating_flows}
            end_states = [cs.flow_state for cs in self.propagating_flows]

            end_state_matrix = MatchFlows.flow_state_symplectic(self._num_qubits, end_states)
            desired_end_state = MatchFlows.flow_state_symplectic(
                self._num_qubits, [flow_state.flow_state]
            )
            combination_indicator = check_row_in_span(end_state_matrix, desired_end_state[0, :])
            if combination_indicator is None:
                return FlowInSpanResult(
                    status=FlowInSpanStatus.FLOW_STATE_NOT_IN_SPAN,
                    flow_basis=tuple(self.propagating_flows + self.destruction_flows),
                )

            (indicator,) = combination_indicator.nonzero()
            flow_combination = [end_state_to_propagating_flow[end_states[i]] for i in indicator]

            built_up_approximation = functools.reduce(lambda x, y: x * y, flow_combination)
            assert built_up_approximation.flow_state == flow_state.flow_state

        # Now we have to match the chain extension combination ID sets and measurement histories.
        # After reduction, the extension combination sets of propagating and destruction flows are
        # linearly independent. So if the extension combination sets don't match, there is at most
        # one set of destruction flows that can be mixed in to produce the desired set - find it.
        ext_comb_to_add = flow_state.extending_combination.symmetric_difference(
            built_up_approximation.extending_combination
        )
        if ext_comb_to_add:
            if not self.destruction_flows:
                # No destruction flows to mix in so can't match the extension combinations
                return FlowInSpanResult(
                    status=FlowInSpanStatus.FLOW_STATE_NOT_IN_SPAN,
                    flow_basis=tuple(self.propagating_flows + self.destruction_flows),
                )

            extension_matrix = self._make_extension_matrix(self.destruction_flows)
            desired_extension = self._make_extension_vector(ext_comb_to_add)
            combination_indicator = check_row_in_span(extension_matrix, desired_extension)
            if combination_indicator is None:
                # No way to create the desired extension combination set from the destruction flows
                return FlowInSpanResult(
                    status=FlowInSpanStatus.FLOW_STATE_NOT_IN_SPAN,
                    flow_basis=tuple(self.propagating_flows + self.destruction_flows),
                )

            (indicator,) = combination_indicator.nonzero()
            for i in indicator:
                built_up_approximation *= self.destruction_flows[i]
            assert built_up_approximation.extending_combination == flow_state.extending_combination

        # Now the only way we can modify the measurement history is by mixing in detectors.
        # To get the measurement history from combination_with_end_state to flow_state, we need to
        # mix in the symmetric difference of their measurement histories. So that detector must be
        # in the span of the current detectors.
        flow_state_mmt = flow_state.mmt_ssa or MMTResults()
        combination_mmt = built_up_approximation.mmt_ssa or MMTResults()
        if not self._existing_detectors.difference_in_span(flow_state_mmt, combination_mmt):
            return FlowInSpanResult(status=FlowInSpanStatus.MEASUREMENTS_NOT_IN_SPAN)
        return FlowInSpanResult(status=FlowInSpanStatus.IN_SPAN)

    @staticmethod
    def _push_local_products(
        flows: list[CurrentState], gate: qref.GateLikeOp, qubits: tuple[SSAValue, ...]
    ) -> list[CurrentState]:
        """Pushes products of adjacent flow states through a gate to unblock them.
        Asserts that the products are unblocked by the gate.

        Args:
            flows: CurrentStates which multiply together to be unblocked on `gate`.
            gate: The gate that blocked propagation.
            qubits: The qubit SSA values used by the gate.

        Returns:
            Newly unblocked CurrentStates formed from pairwise products.
        """
        unblocked: list[CurrentState] = []
        for cs1, cs2 in itertools.pairwise(flows):
            product = cs1 * cs2
            updated_pairs = apply_flow(gate, qubits=qubits, flow_state=product.flow_state)
            assert updated_pairs
            unblocked.extend(
                _form_current_states_from_data(
                    updated_pairs, product.mmt_ssa, product.extending_combination
                )
            )
        return unblocked

    def _try_unblock(
        self, blocked_flows: list[CurrentState], gate: qref.GateLikeOp, qubits: tuple[SSAValue, ...]
    ) -> list[CurrentState]:
        """Attempt to unblock blocked flow states by multiplying them together, attempting to
        preserve locality by multiplying flows that are close in the list of blocked flows.

        For measurements: two flows that both anticommute with the measurement have a product that
        commutes with it. See the heuristic in `_unblock_by_multiplying_pairs` for details.

        For resets: blocked flows have a non-identity Pauli on the reset qubit. We can unblock by
        multiplying flows whose Paulis on the reset qubit cancel to identity. See the heuristic in
        `_try_unblock_reset` for details.

        Args:
            blocked_flows: CurrentStates that were blocked by `gate`.
            gate: The gate that blocked propagation.
            qubits: The qubit SSA values used by the gate.

        Returns:
            The newly unblocked CurrentStates formed from products of blocked flows, after
            propagating them through the gate. If no flows can be unblocked, return an empty list.
        """
        if isinstance(gate, qref.MeasureOp):
            # We know each of blocked_flows anticommutes with the measurement, so products of two
            # of them must commute and be unblocked.
            return self._unblock_by_multiplying_pairs(blocked_flows, gate, qubits)

        if isinstance(gate, qref.ResetOp):
            return self._try_unblock_reset(blocked_flows, gate, qubits)

        return []

    def _unblock_by_multiplying_pairs(
        self, blocked_flows: list[CurrentState], gate: qref.GateLikeOp, qubits: tuple[SSAValue, ...]
    ) -> list[CurrentState]:
        """Unblock flows blocked by a gate by multiplying pairs of flows heuristically.
        Asserts that the products are unblocked by the gate.

        The heuristic is as follows:
        - For each extending combination of chains, multiply adjacent pairs of flows which extend
          the same combination of chains to form creation flows. This minimises age of the resulting
          flows, and multiplying adjacent flows tries to preserve locality.
        - Choose the flow with the fewest measurements from each extending combination to multiply.
        - Sort the chosen flows by age and multiply adjacent pairs. This ensures that no extending
          chain combination can be the oldest chain in more than one pair, which would produce
          duplicate flow states earlier in the chains.

        Args:
            blocked_flows: CurrentStates that were blocked by the measurement gate.
            gate: The measurement gate that blocked propagation.
            qubits: The qubit SSA values used by the gate.

        Returns:
            Newly unblocked CurrentStates formed from products of blocked flows, after
            propagating them through the gate. If no flows can be unblocked, return an empty list.
        """

        unblocked: list[CurrentState] = []

        # Multiply adjacent pairs of flows which extend the same combination of chains to form
        # creation flows. This is a heuristic which minimises age of the resulting flows, and
        # multiplying adjacent flows tries to preserve locality.
        extending_comb_to_flows: dict[frozenset[int], list[CurrentState]] = defaultdict(list)
        for cs in blocked_flows:
            extending_comb_to_flows[cs.extending_combination].append(cs)

        # Note we iterate in the order the extending combinations are first seen
        for flows in extending_comb_to_flows.values():
            unblocked.extend(self._push_local_products(flows, gate, qubits))

        # Choose a representative from each extending combination to multiply: choose the one with
        # the fewest measurements in total as a heuristic.
        representatives = [
            min(flows, key=self._total_measurements) for flows in extending_comb_to_flows.values()
        ]

        # We need to multiply len(representatives)-1 pairs together to form the rest of the flows,
        # but to ensure we don't get duplicate flow states earlier in the chains, no extending chain
        # combination can be the oldest chain in more than one pair.
        # To fulfil this constraint, we sort by age and multiply adjacent pairs. This also lets us
        # try to form flows with smaller age when possible.
        representatives.sort(key=self._age)
        unblocked.extend(self._push_local_products(representatives, gate, qubits))

        return unblocked

    def _try_unblock_reset(
        self, blocked_flows: list[CurrentState], gate: qref.ResetOp, qubits: tuple[SSAValue, ...]
    ) -> list[CurrentState]:
        """Unblock flows blocked by a reset gate by combining flows whose Paulis on the reset
        qubit cancel to identity.

        A flow is unblocked on a reset gate if it is identity on the reset qubit. Hence we unblock
        flows by producing the identity on the reset qubit: X^2 = Y^2 = Z^2 = XYZ = I.

        The heuristic is as follows:
        - Sort blocked flow indices by their Pauli on the reset qubit. We can unblock by multiplying
          pairs of flows with the same Pauli: use the method from _unblock_by_multiplying_pairs.
        - If there are flows with all of X, Y, Z blocked on the reset qubit, the last linearly
          independent flow can be formed by multiplying one flow from each group, since XYZ = I.
          We must ensure that in the whole unblocking process, no flow can be the oldest chain in
          more than one multiplication, since otherwise we may introduce duplicate flow states
          earlier in the chain. Hence we choose the youngest flow from each X, Y, Z group (tiebreak
          by fewest measurements) to multiply to form the last flow.

        Args:
            blocked_flows: CurrentStates that were blocked by the reset gate.
            gate: The reset gate that blocked propagation.
            qubits: The qubit SSA values used by the gate.

        Returns:
            Newly unblocked CurrentStates.
        """
        # Determine the qubit index of the reset gate in the qubits tuple
        gate_index_list = _gate_indices(qubits, gate)
        assert len(gate_index_list) == 1, "Reset unblocking only supports single-qubit resets."
        reset_qubit_idx = gate_index_list[0]

        # Sort blocked flow indices by their Pauli on the reset qubit
        pauli_to_indices: dict[qcore.PauliAttr, list[int]] = {
            qcore.PauliAttr.X(): [],
            qcore.PauliAttr.Y(): [],
            qcore.PauliAttr.Z(): [],
        }
        for idx, cs in enumerate(blocked_flows):
            pauli = cs.flow_state.get_index_to_pauli().get(reset_qubit_idx)
            assert pauli is not None, (
                "Blocked flow must have a non-identity Pauli on the reset qubit."
            )
            pauli_to_indices[pauli].append(idx)

        unblocked: list[CurrentState] = []

        # Multiply pairs within each Pauli group
        for pauli_indices in pauli_to_indices.values():
            flows_in_group = [blocked_flows[i] for i in pauli_indices]
            unblocked.extend(self._unblock_by_multiplying_pairs(flows_in_group, gate, qubits))

        # If all three Pauli groups are nonempty, find the youngest flow from each group and
        # multiply together to form a flow with identity on the reset qubit (XYZ = I).
        # We choose the youngest flows to avoid getting duplicate flow states earlier in the chain:
        # the youngest flows will not have been the sole oldest flow in any pairwise multiplication,
        # so the product of youngest flows will not duplicate the flow states formed by pairwise
        # multiplication in any position.
        # Tiebreak on fewest measurements as a heuristic.
        if all(pauli_to_indices.values()):
            youngest = [
                min(
                    (blocked_flows[i] for i in pauli_to_indices[pauli]),
                    key=lambda cs: (self._age(cs), self._total_measurements(cs)),
                )
                for pauli in (qcore.PauliAttr.X(), qcore.PauliAttr.Y(), qcore.PauliAttr.Z())
            ]
            product = youngest[0] * youngest[1] * youngest[2]
            updated_pairs = apply_flow(gate, qubits=qubits, flow_state=product.flow_state)
            assert updated_pairs
            unblocked.extend(
                _form_current_states_from_data(
                    updated_pairs, product.mmt_ssa, product.extending_combination
                )
            )

        return unblocked

    def _apply_gate_op(self, gate: qref.GateLikeOp, qubits: tuple[SSAValue, ...]) -> None:
        """Propagate the current flow states and their measurements through a gate."""

        # Also push through the identity flow state to help with the heuristics: for reset and
        # measurement gates, this lets us capture I -> A flows directly instead of capturing them
        # indirectly through other flows (e.g. B -> C and B -> AC) which might not be reduced to
        # the single creation state.
        flows_to_propagate = list(self.propagating_flows)
        flows_to_propagate.append(CurrentState.identity(self._num_qubits))

        self.propagating_flows.clear()  # will be added to by _add_flow
        blocked_flows: list[CurrentState] = []

        for cs in flows_to_propagate:
            updated_pairs: list[tuple[qcore.PauliStringAttr, MMTResults | None]] = apply_flow(
                gate, qubits=qubits, flow_state=cs.flow_state
            )
            if not updated_pairs:
                blocked_flows.append(cs)
                continue

            # accumulate histories
            for state in _form_current_states_from_data(
                updated_pairs, cs.mmt_ssa, cs.extending_combination
            ):
                self._add_flow(state)

        # Attempt to unblock by multiplying adjacent pairs of blocked states.
        # Remaining flows that can't be unblocked are thrown away.
        if blocked_flows:
            unblocked = self._try_unblock(blocked_flows, gate, qubits)
            for state in unblocked:
                self._add_flow(state)

        if self._should_auto_reduce():
            self.reduce()

    def _apply_parallel_op(self, par_op: qstruct.ParallelOp, qubits: tuple[SSAValue, ...]) -> None:
        """Propagate the current flow states and their measurements through a ParallelOp."""

        # Just push through each of the branches in turn as if they were sequential.
        for branch in par_op.par_regions:
            self.propagate(branch.ops, qubits)

    def propagate(self, ops: Iterable[Operation], qubits: tuple[SSAValue, ...]) -> None:
        """Propagate the current flow states and their measurements through a list of operations.

        Args:
            ops: The operations to propagate through.
            qubits: The qubit SSA values used by the operations. Indices in the flow states
                correspond to the indices of qubits in this tuple.
        """

        for op in ops:
            if isinstance(op, (qref.GateLikeOp, qstruct.ParallelOp)):
                if isinstance(op, qref.GateLikeOp):
                    self._apply_gate_op(op, qubits)
                else:
                    self._apply_parallel_op(op, qubits)
            elif isinstance(op, qref.PauliNoiseOp):
                msg = "Propagating flows through noise ops is not supported."
                raise ValueError(msg)
            elif isinstance(op, qstruct.RepeatOp):
                # TODO: Support repeat ops
                msg = "Propagating flows over repeat ops is not yet supported."
                raise NotImplementedError(msg)
            elif not qcore.is_quantum_state_effect_free(op):
                msg = f"Propagating flows over unknown operation {op} is not supported."
                raise ValueError(msg)

    def _find_flow_from_duplicates_to_keep(self, states: list[CurrentState]) -> CurrentState:
        """Given a list of flows with the same end state, find which one to keep, taking into
        account the ages of the flows and whether they are user flows."""

        youngest_user_flow = min(
            (cs for cs in states if self._is_user_flow(cs)),
            key=lambda cs: (
                self._last_user_flow_age(cs),
                self._age(cs),
                self._total_measurements(cs),
            ),
            default=None,
        )
        youngest_non_user_flow = min(
            (cs for cs in states if not self._is_user_flow(cs)),
            key=lambda cs: (self._age(cs), self._total_measurements(cs)),
            default=None,
        )

        if youngest_user_flow is not None and youngest_non_user_flow is not None:
            last_user_flow_age = self._last_user_flow_age(youngest_user_flow)
            assert last_user_flow_age is not None

            if last_user_flow_age < self._age(youngest_non_user_flow):
                # The youngest user flow would have no other flow to multiply with which doesn't
                # touch its last user flow link. So keep it to avoid violating that condition.
                # Note that in this case we might have to throw out the youngest non-user flow to
                # avoid having to throw out this user flow.
                return youngest_user_flow

            # The youngest non-user flow would not have a younger flow to multiply with.
            # So keep it to avoid having to throw it out.
            return youngest_non_user_flow

        if youngest_user_flow is not None:
            return youngest_user_flow

        assert youngest_non_user_flow is not None
        return youngest_non_user_flow

    def _filter_duplicate_propagating_flows(self, removing=False) -> None:
        """Multiply propagating flows to eliminate any flows with duplicate end states. Generated
        destruction flows and detectors are added. Afterwards, the propagating flows all have unique
        end states.

        `removing` controls the behaviour when we cannot satisfy the age or last user flow age
        constraints described in `_FlowChain` without throwing out a flow. If True, we throw out
        non-user flows as needed to satisfy the constraints, and error if we'd have to throw out a
        user flow. If False, we keep a full basis of flows, even if it means violating one of the
        constraints, with the expectation that the constraint violations will be fixed later.
        This is done in `_reduce_all_extension_combinations`.
        """
        # end state -> list of current states with that end state
        end_state_to_flows: dict[qcore.PauliStringAttr, list[CurrentState]] = defaultdict(list)
        for cs in self.propagating_flows:
            end_state_to_flows[cs.flow_state].append(cs)

        self.propagating_flows.clear()
        for states in end_state_to_flows.values():
            # Which flow should we keep with this end state?
            state_to_keep = self._find_flow_from_duplicates_to_keep(states)
            self.propagating_flows.append(state_to_keep)

            states.sort(key=lambda cs: (self._age(cs), self._total_measurements(cs)))
            for idx, cs in enumerate(states):
                if cs is state_to_keep:
                    continue

                if self._is_user_flow(cs):
                    # The maximum age of the flow to multiply with is last_user_flow_age to
                    # avoid touching the last user flow link of cs. Find the rightmost as a
                    # heuristic.
                    last_user_flow_age = self._last_user_flow_age(cs)
                    assert last_user_flow_age is not None
                    latest_idx = bisect.bisect_right(states, last_user_flow_age, key=self._age) - 1

                    if latest_idx >= 0:
                        product = states[latest_idx] * cs
                    else:
                        # This user flow has no younger flows to multiply with, and it's not the one
                        # being kept. So we must either violate the user flow age constraint (i.e.,
                        # multiply it with a flow which touches its last user flow link) or error
                        # because we can't throw away a user flow.
                        if removing:
                            # Formally there are two user flows in conflict: the one being kept and
                            # this one, and we can't resolve it because there are no younger flows
                            # to multiply into this one.
                            # TODO: improve error message.
                            msg = (
                                f"User flow-derived chain ending with {cs.flow_state.as_str()} is "
                                "in an unresolvable conflict with user flow-derived chain ending "
                                f"with {state_to_keep.flow_state.as_str()}."
                            )
                            raise BadUserFlowError(msg)

                        # We want to keep the full basis of flow so just multiply it with something.
                        # This violates the user flow age constraint but we'll enforce that later.
                        product = state_to_keep * cs
                elif idx == 0:
                    if removing:
                        # The youngest flow is not the one being kept because the youngest user flow
                        # is older. To avoid violating the age constraint (that every chain can be
                        # the oldest chain in at most one flow), we must remove one of the youngest
                        # flows (choose this one).
                        continue
                    # We want to keep the full basis of flows and will enforce the age constraint
                    # later, so just multiply it with something (violating the age constraint).
                    product = state_to_keep * cs
                else:
                    # Non-user flow: multiply it with its left neighbour so every flow is the oldest
                    # in one pairing, since the left neighbour has the same or younger age.
                    # TODO: This could be any non-user flow to the left of cs, pick a
                    #  better one heuristically?
                    product = states[idx - 1] * cs

                assert product.flow_state.is_identity()
                self._add_flow(product)

    def _reduce_unique_propagating_flows(self, enforce_user_flow_preservation=False) -> None:
        """Perform Gaussian elimination on the propagating flows, assuming that their end states are
        unique. Generated destruction flows and detectors are added.

        If enforce_user_flow_preservation is True, then we ensure that violations of the user flow
        constraints are not introduced even if that means keeping linearly dependent flows.
        """

        # Required to be 1:1 by the precondition
        end_state_to_flows: dict[qcore.PauliStringAttr, CurrentState] = {
            cs.flow_state: cs for cs in self.propagating_flows
        }
        assert len(end_state_to_flows) == len(self.propagating_flows)

        # Sort states by decreasing age to keep younger states when multiplying out redundancies,
        # and otherwise by decreasing measurement count.
        # Note we must always keep the youngest states to avoid creating duplicate states earlier in
        # the chains.
        # Do not eliminate annotated flows to ensure they're propagated; the rest of the user flow
        # constraints are enforced in _reduce_all_extension_combinations.
        sorted_flows = sorted(
            self.propagating_flows,
            key=lambda cs: (
                not cs.is_annotated_flow,
                self._age(cs),
                not self._is_user_flow(cs),  # Prefer to eliminate non-user flows when possible.
                self._total_measurements(cs),
            ),
            reverse=True,
        )

        # We require end states to be unique so that we don't have to worry about measurement sets
        # during the Gaussian elimination, and can identify flows with their end states.
        lin_deps = MatchFlows.find_linearly_dependent_flow_states_with_flags(
            [cs.flow_state for cs in sorted_flows],
            # Ensure annotated flows aren't eliminated.
            flag_idx=len([cs for cs in sorted_flows if not cs.is_annotated_flow]),
        )
        to_remove = lin_deps.flow_states
        to_multiply_out = lin_deps.lin_dependencies

        if enforce_user_flow_preservation:
            # Don't remove any user flows to avoid violating the user flow constraints.
            # Note that since the sets of dependent flows found are minimal, if the oldest flow in
            # a dependent set is a user flow and multiplying out the dependent set later down the
            # line would require violating the user flow constraints, then it's safe to not remove
            # the user flow since we know the dependency won't be multiplied out later.
            for flow in list(to_remove):
                if self._is_user_flow(end_state_to_flows[flow]):
                    last_user_flow_age = self._last_user_flow_age(end_state_to_flows[flow])
                    assert last_user_flow_age is not None

                    # find the dependent set containing this user flow
                    dep_set = next(dep_set for dep_set in to_multiply_out if flow in dep_set)
                    if any(
                        self._age(end_state_to_flows[other_flow]) > last_user_flow_age
                        for other_flow in dep_set
                        if other_flow != flow
                    ):
                        # some flow in dep_set would conflict with the user flow constraints so it's
                        # safe to not remove this user flow
                        to_remove.remove(flow)

        # Remove redundant flows, keeping the original list order for locality.
        self.propagating_flows = [
            cs for cs in self.propagating_flows if cs.flow_state not in to_remove
        ]

        # Multiply out redundancies to form destruction flows and detectors.
        # Sort first for determinism.
        sorted_dependent_sets = sorted(
            (sorted(dep_set, key=qcore.PauliStringAttr.sort_key) for dep_set in to_multiply_out),
            key=lambda states: tuple(state.sort_key() for state in states),
        )
        for dependent_set in sorted_dependent_sets:
            product = functools.reduce(
                lambda cs1, cs2: cs1 * cs2, (end_state_to_flows[ps] for ps in dependent_set)
            )
            assert product.flow_state.is_identity()
            self._add_flow(product)

    def _reduce_propagating_flows(self) -> None:
        """Perform Gaussian elimination on the propagating flows so that their end states are
        linearly independent. This way we propagate at most 2*num_qubits flow states. This generates
        some destruction flows and detectors which are not reduced here."""

        # For convenience and heuristics, first remove duplicate end states, then do elimination on
        # the remainder whose end states are now unique.
        self._filter_duplicate_propagating_flows()
        self._reduce_unique_propagating_flows()

    def _reduce_destruction_flows(self) -> None:
        """Perform Gaussian elimination on the flow chain extension ID sets of the destruction flows
        to reduce them to a linearly independent set. This way no more destruction flows than
        necessary are kept. This generates some detectors."""

        # Don't eliminate annotated flows - the rest of the user flow constraints are ensured by
        # _reduce_all_extension_combinations.
        annotated_flows = [cs for cs in self.destruction_flows if cs.is_annotated_flow]
        non_annotated_flows = [cs for cs in self.destruction_flows if not cs.is_annotated_flow]

        if not non_annotated_flows:
            return

        # Sort by decreasing age to keep younger flows when multiplying out redundancies, and
        # otherwise by decreasing measurement count.
        sorted_idx_and_flows = sorted(
            enumerate(non_annotated_flows),
            key=lambda idx_cs: (self._age(idx_cs[1]), self._total_measurements(idx_cs[1])),
            reverse=True,
        )
        sorted_non_annotated = [cs for _, cs in sorted_idx_and_flows]
        flows_to_reduce = sorted_non_annotated + annotated_flows
        extension_matrix = self._make_extension_matrix(flows_to_reduce)

        # Perform Gaussian elimination to find linearly dependent rows.
        # flag_idx is set such that we only consider non-annotated flows for removal.
        sorted_idxs_to_remove, lin_dependencies = find_linearly_dependent_rows(
            extension_matrix, flag_idx=len(non_annotated_flows)
        )

        # Remove redundant flows, keeping the original order.
        original_idxs_to_remove = [sorted_idx_and_flows[idx][0] for idx in sorted_idxs_to_remove]
        self.destruction_flows = [
            cs for idx, cs in enumerate(non_annotated_flows) if idx not in original_idxs_to_remove
        ] + annotated_flows

        # Multiply out redundancies to form detectors. Sort first for determinism.
        sorted_dependencies = sorted(tuple(sorted(dep_set)) for dep_set in lin_dependencies)
        for dependency in sorted_dependencies:
            product = functools.reduce(
                lambda cs1, cs2: cs1 * cs2, (flows_to_reduce[idx] for idx in dependency)
            )
            assert product.newly_created
            assert product.flow_state.is_identity()
            self._add_flow(product)

    def _reduce_all_extension_combinations(self) -> None:
        # If there are no chains being extended (i.e. we're just propagating the identity flow) then
        # there is nothing to be done.
        if not self._input_basis_info:
            return

        # Order: user flows before non-user flows, each block sorted by age decreasing, then
        # by decreasing measurement count for heuristics.
        chain_order = list(range(len(self._input_basis_info)))
        chain_order.sort(
            key=lambda idx: (
                self._input_basis_info[idx].is_user_flow,
                self._input_basis_info[idx].age,
                self._input_basis_info[idx].chain_measurements,
            ),
            reverse=True,
        )
        user_chains = [idx for idx in chain_order if self._input_basis_info[idx].is_user_flow]

        num_user_chains = len(user_chains)
        num_non_user_chains = len(chain_order) - num_user_chains

        # Earlier flows will be multiplied out first when possible. So put annotated flows at the
        # end, so they'll be kept always, and otherwise order heuristically by age and measurements.
        flows_to_reduce = sorted(
            self.propagating_flows + self.destruction_flows,
            key=lambda cs: (not cs.is_annotated_flow, self._age(cs), self._total_measurements(cs)),
            reverse=True,
        )
        extension_matrix = self._make_extension_matrix(flows_to_reduce, chain_order=chain_order)

        # Add an identity on the right to keep track of the row combinations
        identity = np.identity(extension_matrix.shape[0], dtype=np.bool_)
        augmented_extension_matrix = np.concatenate([extension_matrix, identity], axis=1)

        # RREF to fulfil age constraint: every chain may be the oldest (leftmost) in at most one row
        _row_reduce_bool_inplace(augmented_extension_matrix)

        # Check that every user flow is propagated as an oldest chain in at least one row.
        # Since we're in RREF and the user flows are ordered first, this means every user flow
        # column must be a pivot, so the top left block of the matrix must be an identity matrix
        # of size num_user_chains.
        if num_user_chains > 0 and not np.array_equal(
            augmented_extension_matrix[:num_user_chains, :num_user_chains],
            np.identity(num_user_chains, dtype=np.bool_),
        ):
            # Find which ones failed to propagate independently.
            failed_user_chains = [
                idx for idx in range(num_user_chains) if not augmented_extension_matrix[idx, idx]
            ]
            failed_flow_states = [
                self._input_basis_info[user_chains[idx]].flow_state for idx in failed_user_chains
            ]
            failed_flow_states.sort(key=qcore.PauliStringAttr.sort_key)
            msg = (
                f"User flow chain(s) {qcore.PauliStringAttr.collection_as_str(failed_flow_states)} "
                "failed to propagate through the current circuit independently."
            )
            raise BadUserFlowError(msg)

        if num_non_user_chains > 0:
            for idx, user_chain in enumerate(user_chains):
                # To avoid overwriting the latest user flow link, the other chains in this user
                # chain's row must have age at most the user chain's last_user_flow_age.
                # In the matrix, this means the leftmost 1 in the row in the non-user section
                # must correspond to a chain with age at most last_user_flow_age.
                # The user section is already taken care of for us by the identity check above.
                last_user_flow_age = self._input_basis_info[user_chain].last_user_flow_age
                assert last_user_flow_age is not None

                non_user_row = augmented_extension_matrix[
                    idx, num_user_chains : num_user_chains + num_non_user_chains
                ]
                non_user_ones = non_user_row.nonzero()[0]
                if len(non_user_ones) != 0:
                    earliest_one: int = non_user_ones[0] + num_user_chains
                    chain_idx = chain_order[earliest_one]
                    if self._input_basis_info[chain_idx].age > last_user_flow_age:
                        # This non-user chain disrupts our user chain's last user flow link. We
                        # can't just remove it (it's necessary for this flow to propagate) so the
                        # user chain can't propagate without disrupting its last user flow link.
                        # TODO: improve error message.
                        user_flow_state = self._input_basis_info[user_chain].flow_state
                        msg = (
                            f"User-derived flow chain ending with {user_flow_state.as_str()} "
                            "cannot propagate through the current circuit."
                        )
                        raise BadUserFlowError(msg)

        # TODO: We could heuristically minimise measurements / maximise locality by
        # manipulating the augmented extension matrix here.

        # Multiply out the flows according to the right-hand side of the augmented matrix.
        self.propagating_flows.clear()
        self.destruction_flows.clear()
        row: np.ndarray
        for row in augmented_extension_matrix:
            # The left part of the row is the extension combination set, the right part is the
            # combination of flows to multiply together to form that extension combination set.
            extension_combination = frozenset(
                chain_order[i] for i in row[: len(chain_order)].nonzero()[0]
            )
            flow_combination = [flows_to_reduce[i] for i in row[len(chain_order) :].nonzero()[0]]
            product = functools.reduce(lambda cs1, cs2: cs1 * cs2, flow_combination)
            assert product.extending_combination == extension_combination
            self._add_flow(product)

        # The above might have resulted in multiplying destruction flows with propagating flows,
        # resulting in linear dependencies in the end states. We reduce again to be safe, removing
        # flows instead of multiplying user flows (which would violate last user flow age).
        # We don't need to reduce the destruction flows afterwards because they were LI before this
        # method and are therefore LI after filtering duplicates again.
        self._filter_duplicate_propagating_flows(removing=True)
        self._reduce_unique_propagating_flows(enforce_user_flow_preservation=True)

    def _should_auto_reduce(self) -> bool:
        return self._auto_reduce and len(self.propagating_flows) > 2 * self._num_qubits

    def reduce(self) -> None:
        """Perform Gaussian elimination to reduce the current flow states to a linearly independent
        set. This must be done frequently to avoid exponential growth in the flow state count.

        Afterwards, we're left with at most 2*num_qubits propagating flows and at most one
        destruction flow. A linearly independent set of detectors is maintained continuously.
        """

        # Reduce propagating flows by end states, generating destruction flows and detectors
        self._reduce_propagating_flows()

        # Reduce destruction flows, generating detectors
        self._reduce_destruction_flows()

    def full_reduce(self) -> None:
        """Reduce the tracked flows to a set of flows suitable to be output onto a circuit.

        Over and above `reduce()`, this method also tries to maximise the number of creation flows
        by reducing the extension chain combination ID sets to a linearly independent set, and it
        enforces the age and user flow constraints:

          - Every chain in the input basis can be the oldest chain in at most one flow (to avoid
            duplicate flows earlier in the chains).
          - Every user flow chain in the input basis must be the oldest chain in at least one
            flow, to ensure every user flow is propagated through the circuit, and the last user
            flow link of that chain can't be modified by multiplying with other flows.

        Afterwards, all non-identity end states and all non-empty extension combination ID sets
        should be linearly independent, and the constraints above should be met.
        """
        self.reduce()
        self._reduce_all_extension_combinations()


def _form_current_states_from_data(
    updates: list[tuple[qcore.PauliStringAttr, MMTResults | None]],
    current_mmt: MMTResults | None,
    extending_combination: frozenset[int] = frozenset(),
) -> list[CurrentState]:
    """Converts input data into current form, with additional measurements being added
    to the input measurement set, if it exists."""
    # normalise current measurements given
    base_mmt = current_mmt or MMTResults()
    new_states: list[CurrentState] = []
    for new_flow_state, mmt_results in updates:
        if mmt_results:
            new_states.append(
                CurrentState(new_flow_state, base_mmt.union(mmt_results), extending_combination)
            )
        else:
            new_states.append(CurrentState(new_flow_state, base_mmt, extending_combination))
    return new_states


class CalculateFlows:
    """Functions used in propagation of flows."""

    @staticmethod
    def propagate_input_flow_basis(
        input_flow_info: list[FlowChainInfo],
        qubits: tuple[SSAValue, ...],
        ops: Sequence[Operation],
    ) -> CurrentStates:
        """Determines set of possible output flows with corresponding measurement history given
        a basis of input flow chains and a sequence of gates.

        A flow state A is said to be blocked by a gate if there is no such B such that the
        stabiliser flow through the gate A -> B is valid.  This occurs for:
        - measurements if and only if A anti-commutes with the gate's Pauli string
        - resets if and only if A is not the identity Pauli string, I.

        For each possible flow state, there is a history of measurements stored in CurrentStates.
        Note that each possible current flow state corresponds to a path through the circuit passing
        through different sets of measurements en route.

        Care is taken with:
        - categorisation of gates into Cliffords, resets and single qubit measurements
        - measurements causing branching of flow that propagates through
          - in particular, when measurement and flow state have disjoint support
        - measurements that don't allow some flow states through
        - recording measurement only when the output of flow depends on mmt result
        - resets only admitting identity state as input

        e.g. M_Z admits 3 non-trivial flows:
        a) Z -> Z
        b) Z -> (-1)^m I
        c) I -> (-1)^m Z

        and does not admit flow states with input stabilisers X or Y so any such flows should be
        removed from the set of possible output flows, i.e. the returned flow state.

        Args:
            input_flow_info: The basis of the space of flow states to propagate, with chain age
                and information for heuristics.
            qubits: The tuple of qubit ssa values indexed by input_flow_state and used by the ops in
                gates.
            ops: A sequence of operations to apply in order.

        Returns:
            The resulting mapping of flow data to histories if propagation succeeds, or the blocking
            operation if all flows are blocked.

        Raises:
            ValueError: If the operations contain noise ops.
            NotImplementedError: If the operations contain ops that are not yet supported.
        """
        current_flow_states = CurrentStates(input_flow_info, num_qubits=len(qubits))
        current_flow_states.propagate(ops, qubits)
        return current_flow_states


# endregion
# region Methods for applying gates to flow states


def get_reduced_flow_state(
    flow_state: qcore.PauliStringAttr, idx_set: set[int]
) -> qcore.PauliStringAttr:
    """Return the part of `flow_state` with support only on the qubits with index in the given set.

    Example: X0 Y1 Z2 with idx_list = [1, 5] returns Y1.
    """
    reduced_qubits: list[qcore.QubitPauliStateAttr] = []
    for qb in flow_state.qubit_states:
        if qb.qubit_index in idx_set:
            reduced_qubits.append(qb)
    return qcore.PauliStringAttr(reduced_qubits, flow_state.length)


def _gate_indices(qubits: tuple[SSAValue, ...], gate: qref.GateLikeOp) -> list[int]:
    """Helper to map a gate's target SSAValues to their indices in the given qubits tuple."""
    return [qubits.index(operand) for group in gate.qubit_operand_groups for operand in group]


def apply_flow(
    gate: qref.GateLikeOp,
    qubits: tuple[SSAValue, ...],
    flow_state: qcore.PauliStringAttr,
) -> list[tuple[qcore.PauliStringAttr, MMTResults | None]]:
    """Compute the flow resulting from applying a Clifford, measurement or reset gate.
    If the flow is blocked, return an empty list.
    Each tuple of the list represents a possible branch of the flow.
    """
    gate_index_list = _gate_indices(qubits, gate)

    # Cliffords
    if isinstance(gate, qref.GateOp):
        new_flow_state = CliffordFlows.apply_clifford(gate.gate, gate_index_list, flow_state)
        return [(new_flow_state, None)]

    # Reset gates
    if isinstance(gate, qref.ResetOp):
        if len(gate.qubits) > 1:
            msg = "Flow propagation does not support multi-qubit reset gates!"
            raise NotImplementedError(msg)

        local_flow_state = flow_state.get_local_pauli_string(gate_index_list)
        # resets can only be I -> Pauli or I -> I on the reset targets; block if overlap
        # need I -> I flow, else cannot interpret resets as creating flows,
        # reset here causes branching but parallel ops reduce exponential blow up
        if local_flow_state.is_identity():
            # Construct a local flow containing the Pauli on all reset targets
            local_reset_flow = qcore.PauliStringAttr.repeat(gate.basis, len(gate_index_list))
            return [
                (
                    flow_state.with_updated_local_pauli_string(local_reset_flow, gate_index_list),
                    None,
                ),
                (flow_state, None),
            ]
        # Overlap with existing flow on any target blocks the reset
        return []

    # Measurement gates
    if isinstance(gate, qref.MeasureOp):
        gate_pauli_string = MeasurementFlows.find_mmt_gate_pauli_string(
            gate, gate_index_list, flow_state.length.data
        )
        record_branches: list[tuple[qcore.PauliStringAttr, bool]] = (
            MeasurementFlows.apply_measurement(
                gate_pauli_string,
                flow_state,
            )
        )
        # Convert record flags to actual measurement SSA sets or None
        mmt_set = MMTResults(gate.measurements)
        converted: list[tuple[qcore.PauliStringAttr, MMTResults | None]] = []
        for st, record in record_branches:
            converted.append((st, mmt_set if record else None))
        return converted

    msg = "Unknown gate type for flow application."
    raise NotImplementedError(msg)


def backpropagate_observable(
    gate: qref.GateLikeOp, observable: qcore.PauliStringAttr, qubits: tuple[SSAValue, ...]
) -> qcore.PauliStringAttr:
    """Backpropagate a Pauli observable through Clifford, measurement, and reset gates.

    Assumes that the gate is not broadcast (it operates on only n qubits for an n-qubit gate),
    except that broadcast reset gates are supported.

    Clifford gates:
    - For gate G in the set {X, Y, Z, H, S, CX, SWAP, iSWAP} and Paulis P and P', if P' = G P G†,
        then P = G P' G† (up to a global phase). Hence, we may use apply_flows in the reverse
        direction to compute the backpropagated observable.

    Measurement gates:
    - Backpropagation succeeds only when the measurement operator commutes
        with the observable. Measurement outcomes are not recorded here.

    Reset gates:
    - Remove only the components of the observable that act on qubits being
        reset; keep non-overlapping components unchanged.

    Args:
        gate: Gate to backpropagate through.
        observable: Pauli string to backpropagate.
        qubits: SSA qubits indexed by observable and usable by gate.

    Returns:
        The backpropagated observable.

    Raises:
        ValueError: when the gate is not of one of the above supported types.
    """

    gate_index_list = [
        qubits.index(operand) for group in gate.qubit_operand_groups for operand in group
    ]

    # Cliffords
    if isinstance(gate, qref.GateOp):
        return CliffordFlows.apply_clifford(gate.gate, gate_index_list, observable)

    # Handle measurement gates (including multi-Pauli) using Pauli mapping and commutation check
    if isinstance(gate, qref.MeasureOp):
        pauli_string = gate.pauli  # Assume not broadcast
        measurement_flow = qcore.PauliStringAttr(
            zip(pauli_string, gate_index_list, strict=True), len(qubits)
        )
        commutes = measurement_flow.commutes(observable)
        return observable if commutes else qcore.PauliStringAttr([], len(qubits))

    # Handle reset gates: remove only overlapping qubits; keep the rest
    if isinstance(gate, qref.ResetOp):
        reset_indices = set(gate_index_list)
        remaining = [
            qb for qb in observable.qubit_states.data if qb.qubit_index not in reset_indices
        ]
        return qcore.PauliStringAttr(remaining, len(qubits))

    msg = "Unknown gate type for observable backpropagation."
    raise ValueError(msg)


# endregion
# region Lookup tables for gates


class CliffordFlows:
    """Lookup-table based stabiliser flow updates for Clifford gates.

    The table maps (gate enum) -> {PauliStringAttr: PauliStringAttr} on local indices.
    Indices are relabelled by the caller.
    """

    TABLE: ClassVar[
        dict[qcore.GateAttribute, dict[qcore.PauliStringAttr, qcore.PauliStringAttr]]
    ] = {
        # Single-qubit gates: input/output as PauliStringAttr on local index 0
        qcore.IdentityGateAttr(): {
            qcore.PauliStringAttr([("X", 0)], 1): qcore.PauliStringAttr([("X", 0)], 1),
            qcore.PauliStringAttr([("Y", 0)], 1): qcore.PauliStringAttr([("Y", 0)], 1),
            qcore.PauliStringAttr([("Z", 0)], 1): qcore.PauliStringAttr([("Z", 0)], 1),
        },
        qcore.XGateAttr(): {
            qcore.PauliStringAttr([("X", 0)], 1): qcore.PauliStringAttr([("X", 0)], 1),
            qcore.PauliStringAttr([("Y", 0)], 1): qcore.PauliStringAttr([("Y", 0)], 1),
            qcore.PauliStringAttr([("Z", 0)], 1): qcore.PauliStringAttr([("Z", 0)], 1),
        },
        qcore.YGateAttr(): {
            qcore.PauliStringAttr([("X", 0)], 1): qcore.PauliStringAttr([("X", 0)], 1),
            qcore.PauliStringAttr([("Y", 0)], 1): qcore.PauliStringAttr([("Y", 0)], 1),
            qcore.PauliStringAttr([("Z", 0)], 1): qcore.PauliStringAttr([("Z", 0)], 1),
        },
        qcore.ZGateAttr(): {
            qcore.PauliStringAttr([("X", 0)], 1): qcore.PauliStringAttr([("X", 0)], 1),
            qcore.PauliStringAttr([("Y", 0)], 1): qcore.PauliStringAttr([("Y", 0)], 1),
            qcore.PauliStringAttr([("Z", 0)], 1): qcore.PauliStringAttr([("Z", 0)], 1),
        },
        qcore.HGateAttr(): {
            qcore.PauliStringAttr([("X", 0)], 1): qcore.PauliStringAttr([("Z", 0)], 1),
            qcore.PauliStringAttr([("Z", 0)], 1): qcore.PauliStringAttr([("X", 0)], 1),
            qcore.PauliStringAttr([("Y", 0)], 1): qcore.PauliStringAttr([("Y", 0)], 1),
        },
        qcore.SGateAttr(): {
            qcore.PauliStringAttr([("X", 0)], 1): qcore.PauliStringAttr([("Y", 0)], 1),
            qcore.PauliStringAttr([("Y", 0)], 1): qcore.PauliStringAttr([("X", 0)], 1),
            qcore.PauliStringAttr([("Z", 0)], 1): qcore.PauliStringAttr([("Z", 0)], 1),
        },
        # Two-qubit gates: inputs/outputs as PauliStringAttr on local indices
        # (0: control, 1: target)
        qcore.CXGateAttr(): {
            # Single-qubit inputs
            qcore.PauliStringAttr([("X", 0)], 2): qcore.PauliStringAttr([("X", 0), ("X", 1)], 2),
            qcore.PauliStringAttr([("Y", 0)], 2): qcore.PauliStringAttr([("Y", 0), ("X", 1)], 2),
            qcore.PauliStringAttr([("Z", 0)], 2): qcore.PauliStringAttr([("Z", 0)], 2),
            qcore.PauliStringAttr([("X", 1)], 2): qcore.PauliStringAttr([("X", 1)], 2),
            qcore.PauliStringAttr([("Y", 1)], 2): qcore.PauliStringAttr([("Z", 0), ("Y", 1)], 2),
            qcore.PauliStringAttr([("Z", 1)], 2): qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 2),
            # Two-qubit inputs
            qcore.PauliStringAttr([("X", 0), ("X", 1)], 2): qcore.PauliStringAttr([("X", 0)], 2),
            qcore.PauliStringAttr([("X", 0), ("Y", 1)], 2): qcore.PauliStringAttr(
                [("Y", 0), ("Z", 1)], 2
            ),
            qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2): qcore.PauliStringAttr(
                [("Y", 0), ("Y", 1)], 2
            ),
            qcore.PauliStringAttr([("Y", 0), ("X", 1)], 2): qcore.PauliStringAttr([("Y", 0)], 2),
            qcore.PauliStringAttr([("Y", 0), ("Y", 1)], 2): qcore.PauliStringAttr(
                [("X", 0), ("Z", 1)], 2
            ),
            qcore.PauliStringAttr([("Y", 0), ("Z", 1)], 2): qcore.PauliStringAttr(
                [("X", 0), ("Y", 1)], 2
            ),
            qcore.PauliStringAttr([("Z", 0), ("X", 1)], 2): qcore.PauliStringAttr(
                [("Z", 0), ("X", 1)], 2
            ),
            qcore.PauliStringAttr([("Z", 0), ("Y", 1)], 2): qcore.PauliStringAttr([("Y", 1)], 2),
            qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 2): qcore.PauliStringAttr([("Z", 1)], 2),
        },
        qcore.CYGateAttr(): {
            qcore.PauliStringAttr([("X", 0)], 2): qcore.PauliStringAttr([("X", 0), ("Y", 1)], 2),
            qcore.PauliStringAttr([("Y", 0)], 2): qcore.PauliStringAttr([("Y", 0), ("Y", 1)], 2),
            qcore.PauliStringAttr([("Z", 0)], 2): qcore.PauliStringAttr([("Z", 0)], 2),
            qcore.PauliStringAttr([("X", 1)], 2): qcore.PauliStringAttr([("Z", 0), ("X", 1)], 2),
            qcore.PauliStringAttr([("Y", 1)], 2): qcore.PauliStringAttr([("Y", 1)], 2),
            qcore.PauliStringAttr([("Z", 1)], 2): qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 2),
            qcore.PauliStringAttr([("X", 0), ("X", 1)], 2): qcore.PauliStringAttr(
                [("Y", 0), ("Z", 1)], 2
            ),
            qcore.PauliStringAttr([("X", 0), ("Y", 1)], 2): qcore.PauliStringAttr([("X", 0)], 2),
            qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2): qcore.PauliStringAttr(
                [("Y", 0), ("X", 1)], 2
            ),
            qcore.PauliStringAttr([("Y", 0), ("X", 1)], 2): qcore.PauliStringAttr(
                [("X", 0), ("Z", 1)], 2
            ),
            qcore.PauliStringAttr([("Y", 0), ("Y", 1)], 2): qcore.PauliStringAttr([("Y", 0)], 2),
            qcore.PauliStringAttr([("Y", 0), ("Z", 1)], 2): qcore.PauliStringAttr(
                [("X", 0), ("X", 1)], 2
            ),
            qcore.PauliStringAttr([("Z", 0), ("X", 1)], 2): qcore.PauliStringAttr([("X", 1)], 2),
            qcore.PauliStringAttr([("Z", 0), ("Y", 1)], 2): qcore.PauliStringAttr(
                [("Z", 0), ("Y", 1)], 2
            ),
            qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 2): qcore.PauliStringAttr([("Z", 1)], 2),
        },
        qcore.CZGateAttr(): {
            qcore.PauliStringAttr([("X", 0)], 2): qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2),
            qcore.PauliStringAttr([("Y", 0)], 2): qcore.PauliStringAttr([("Y", 0), ("Z", 1)], 2),
            qcore.PauliStringAttr([("Z", 0)], 2): qcore.PauliStringAttr([("Z", 0)], 2),
            qcore.PauliStringAttr([("X", 1)], 2): qcore.PauliStringAttr([("Z", 0), ("X", 1)], 2),
            qcore.PauliStringAttr([("Y", 1)], 2): qcore.PauliStringAttr([("Z", 0), ("Y", 1)], 2),
            qcore.PauliStringAttr([("Z", 1)], 2): qcore.PauliStringAttr([("Z", 1)], 2),
            qcore.PauliStringAttr([("X", 0), ("X", 1)], 2): qcore.PauliStringAttr(
                [("Y", 0), ("Y", 1)], 2
            ),
            qcore.PauliStringAttr([("X", 0), ("Y", 1)], 2): qcore.PauliStringAttr(
                [("Y", 0), ("X", 1)], 2
            ),
            qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2): qcore.PauliStringAttr([("X", 0)], 2),
            qcore.PauliStringAttr([("Y", 0), ("X", 1)], 2): qcore.PauliStringAttr(
                [("X", 0), ("Y", 1)], 2
            ),
            qcore.PauliStringAttr([("Y", 0), ("Y", 1)], 2): qcore.PauliStringAttr(
                [("X", 0), ("X", 1)], 2
            ),
            qcore.PauliStringAttr([("Y", 0), ("Z", 1)], 2): qcore.PauliStringAttr([("Y", 0)], 2),
            qcore.PauliStringAttr([("Z", 0), ("X", 1)], 2): qcore.PauliStringAttr([("X", 1)], 2),
            qcore.PauliStringAttr([("Z", 0), ("Y", 1)], 2): qcore.PauliStringAttr([("Y", 1)], 2),
            qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 2): qcore.PauliStringAttr(
                [("Z", 0), ("Z", 1)], 2
            ),
        },
        qcore.SWAPGateAttr(): {
            qcore.PauliStringAttr([("X", 0)], 2): qcore.PauliStringAttr([("X", 1)], 2),
            qcore.PauliStringAttr([("X", 1)], 2): qcore.PauliStringAttr([("X", 0)], 2),
            qcore.PauliStringAttr([("Y", 0)], 2): qcore.PauliStringAttr([("Y", 1)], 2),
            qcore.PauliStringAttr([("Y", 1)], 2): qcore.PauliStringAttr([("Y", 0)], 2),
            qcore.PauliStringAttr([("Z", 0)], 2): qcore.PauliStringAttr([("Z", 1)], 2),
            qcore.PauliStringAttr([("Z", 1)], 2): qcore.PauliStringAttr([("Z", 0)], 2),
            qcore.PauliStringAttr([("X", 0), ("X", 1)], 2): qcore.PauliStringAttr(
                [("X", 0), ("X", 1)], 2
            ),
            qcore.PauliStringAttr([("Y", 0), ("Y", 1)], 2): qcore.PauliStringAttr(
                [("Y", 0), ("Y", 1)], 2
            ),
            qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 2): qcore.PauliStringAttr(
                [("Z", 0), ("Z", 1)], 2
            ),
            qcore.PauliStringAttr([("X", 0), ("Y", 1)], 2): qcore.PauliStringAttr(
                [("Y", 0), ("X", 1)], 2
            ),
            qcore.PauliStringAttr([("Y", 0), ("X", 1)], 2): qcore.PauliStringAttr(
                [("X", 0), ("Y", 1)], 2
            ),
            qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2): qcore.PauliStringAttr(
                [("Z", 0), ("X", 1)], 2
            ),
            qcore.PauliStringAttr([("Z", 0), ("X", 1)], 2): qcore.PauliStringAttr(
                [("X", 0), ("Z", 1)], 2
            ),
            qcore.PauliStringAttr([("Y", 0), ("Z", 1)], 2): qcore.PauliStringAttr(
                [("Z", 0), ("Y", 1)], 2
            ),
            qcore.PauliStringAttr([("Z", 0), ("Y", 1)], 2): qcore.PauliStringAttr(
                [("Y", 0), ("Z", 1)], 2
            ),
        },
        qcore.ISWAPGateAttr(): {
            qcore.PauliStringAttr([("X", 0), ("X", 1)], 2): qcore.PauliStringAttr(
                [("X", 0), ("X", 1)], 2
            ),
            qcore.PauliStringAttr([("X", 0), ("Y", 1)], 2): qcore.PauliStringAttr(
                [("Y", 0), ("X", 1)], 2
            ),
            qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2): qcore.PauliStringAttr([("Y", 1)], 2),
            qcore.PauliStringAttr([("Y", 0), ("X", 1)], 2): qcore.PauliStringAttr(
                [("X", 0), ("Y", 1)], 2
            ),
            qcore.PauliStringAttr([("Y", 0), ("Y", 1)], 2): qcore.PauliStringAttr(
                [("Y", 0), ("Y", 1)], 2
            ),
            qcore.PauliStringAttr([("Y", 0), ("Z", 1)], 2): qcore.PauliStringAttr([("X", 1)], 2),
            qcore.PauliStringAttr([("Z", 0), ("X", 1)], 2): qcore.PauliStringAttr([("Y", 0)], 2),
            qcore.PauliStringAttr([("Z", 0), ("Y", 1)], 2): qcore.PauliStringAttr([("X", 0)], 2),
            qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 2): qcore.PauliStringAttr(
                [("Z", 0), ("Z", 1)], 2
            ),
            qcore.PauliStringAttr([("X", 1)], 2): qcore.PauliStringAttr([("Y", 0), ("Z", 1)], 2),
            qcore.PauliStringAttr([("Y", 1)], 2): qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2),
            qcore.PauliStringAttr([("Z", 1)], 2): qcore.PauliStringAttr([("Z", 0)], 2),
            qcore.PauliStringAttr([("X", 0)], 2): qcore.PauliStringAttr([("Z", 0), ("Y", 1)], 2),
            qcore.PauliStringAttr([("Y", 0)], 2): qcore.PauliStringAttr([("Z", 0), ("X", 1)], 2),
            qcore.PauliStringAttr([("Z", 0)], 2): qcore.PauliStringAttr([("Z", 1)], 2),
        },
        qcore.SqrtXXGateAttr(): {
            qcore.PauliStringAttr([("X", 0)], 2): qcore.PauliStringAttr([("X", 0)], 2),
            qcore.PauliStringAttr([("Y", 0)], 2): qcore.PauliStringAttr([("Z", 0), ("X", 1)], 2),
            qcore.PauliStringAttr([("Z", 0)], 2): qcore.PauliStringAttr([("Y", 0), ("X", 1)], 2),
            qcore.PauliStringAttr([("X", 1)], 2): qcore.PauliStringAttr([("X", 1)], 2),
            qcore.PauliStringAttr([("Y", 1)], 2): qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2),
            qcore.PauliStringAttr([("Z", 1)], 2): qcore.PauliStringAttr([("X", 0), ("Y", 1)], 2),
            qcore.PauliStringAttr([("X", 0), ("X", 1)], 2): qcore.PauliStringAttr(
                [("X", 0), ("X", 1)], 2
            ),
            qcore.PauliStringAttr([("X", 0), ("Y", 1)], 2): qcore.PauliStringAttr([("Z", 1)], 2),
            qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2): qcore.PauliStringAttr([("Y", 1)], 2),
            qcore.PauliStringAttr([("Y", 0), ("X", 1)], 2): qcore.PauliStringAttr([("Z", 0)], 2),
            qcore.PauliStringAttr([("Y", 0), ("Y", 1)], 2): qcore.PauliStringAttr(
                [("Y", 0), ("Y", 1)], 2
            ),
            qcore.PauliStringAttr([("Y", 0), ("Z", 1)], 2): qcore.PauliStringAttr(
                [("Y", 0), ("Z", 1)], 2
            ),
            qcore.PauliStringAttr([("Z", 0), ("X", 1)], 2): qcore.PauliStringAttr([("Y", 0)], 2),
            qcore.PauliStringAttr([("Z", 0), ("Y", 1)], 2): qcore.PauliStringAttr(
                [("Z", 0), ("Y", 1)], 2
            ),
            qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 2): qcore.PauliStringAttr(
                [("Z", 0), ("Z", 1)], 2
            ),
        },
        qcore.SqrtYYGateAttr(): {
            qcore.PauliStringAttr([("X", 0)], 2): qcore.PauliStringAttr([("Z", 0), ("Y", 1)], 2),
            qcore.PauliStringAttr([("Y", 0)], 2): qcore.PauliStringAttr([("Y", 0)], 2),
            qcore.PauliStringAttr([("Z", 0)], 2): qcore.PauliStringAttr([("X", 0), ("Y", 1)], 2),
            qcore.PauliStringAttr([("X", 1)], 2): qcore.PauliStringAttr([("Y", 0), ("Z", 1)], 2),
            qcore.PauliStringAttr([("Y", 1)], 2): qcore.PauliStringAttr([("Y", 1)], 2),
            qcore.PauliStringAttr([("Z", 1)], 2): qcore.PauliStringAttr([("Y", 0), ("X", 1)], 2),
            qcore.PauliStringAttr([("X", 0), ("X", 1)], 2): qcore.PauliStringAttr(
                [("X", 0), ("X", 1)], 2
            ),
            qcore.PauliStringAttr([("X", 0), ("Y", 1)], 2): qcore.PauliStringAttr([("Z", 0)], 2),
            qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2): qcore.PauliStringAttr(
                [("X", 0), ("Z", 1)], 2
            ),
            qcore.PauliStringAttr([("Y", 0), ("X", 1)], 2): qcore.PauliStringAttr([("Z", 1)], 2),
            qcore.PauliStringAttr([("Y", 0), ("Y", 1)], 2): qcore.PauliStringAttr(
                [("Y", 0), ("Y", 1)], 2
            ),
            qcore.PauliStringAttr([("Y", 0), ("Z", 1)], 2): qcore.PauliStringAttr([("X", 1)], 2),
            qcore.PauliStringAttr([("Z", 0), ("X", 1)], 2): qcore.PauliStringAttr(
                [("Z", 0), ("X", 1)], 2
            ),
            qcore.PauliStringAttr([("Z", 0), ("Y", 1)], 2): qcore.PauliStringAttr([("X", 0)], 2),
            qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 2): qcore.PauliStringAttr(
                [("Z", 0), ("Z", 1)], 2
            ),
        },
        qcore.SqrtZZGateAttr(): {
            qcore.PauliStringAttr([("X", 0)], 2): qcore.PauliStringAttr([("Y", 0), ("Z", 1)], 2),
            qcore.PauliStringAttr([("Y", 0)], 2): qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2),
            qcore.PauliStringAttr([("Z", 0)], 2): qcore.PauliStringAttr([("Z", 0)], 2),
            qcore.PauliStringAttr([("X", 1)], 2): qcore.PauliStringAttr([("Z", 0), ("Y", 1)], 2),
            qcore.PauliStringAttr([("Y", 1)], 2): qcore.PauliStringAttr([("Z", 0), ("X", 1)], 2),
            qcore.PauliStringAttr([("Z", 1)], 2): qcore.PauliStringAttr([("Z", 1)], 2),
            qcore.PauliStringAttr([("X", 0), ("X", 1)], 2): qcore.PauliStringAttr(
                [("X", 0), ("X", 1)], 2
            ),
            qcore.PauliStringAttr([("X", 0), ("Y", 1)], 2): qcore.PauliStringAttr(
                [("X", 0), ("Y", 1)], 2
            ),
            qcore.PauliStringAttr([("X", 0), ("Z", 1)], 2): qcore.PauliStringAttr([("Y", 0)], 2),
            qcore.PauliStringAttr([("Y", 0), ("X", 1)], 2): qcore.PauliStringAttr(
                [("Y", 0), ("X", 1)], 2
            ),
            qcore.PauliStringAttr([("Y", 0), ("Y", 1)], 2): qcore.PauliStringAttr(
                [("Y", 0), ("Y", 1)], 2
            ),
            qcore.PauliStringAttr([("Y", 0), ("Z", 1)], 2): qcore.PauliStringAttr([("X", 0)], 2),
            qcore.PauliStringAttr([("Z", 0), ("X", 1)], 2): qcore.PauliStringAttr([("Y", 1)], 2),
            qcore.PauliStringAttr([("Z", 0), ("Y", 1)], 2): qcore.PauliStringAttr([("X", 1)], 2),
            qcore.PauliStringAttr([("Z", 0), ("Z", 1)], 2): qcore.PauliStringAttr(
                [("Z", 0), ("Z", 1)], 2
            ),
        },
    }

    @staticmethod
    def apply_clifford(
        gate: qcore.GateAttribute, indices: list[int], flow_state: qcore.PauliStringAttr
    ) -> qcore.PauliStringAttr:
        """Apply a Clifford gate to the given indices of a flow state.
        Assumes that the gate is a Clifford gate.
        Raises error when the gate is not yet implemented or the number of indices provided is not
        the same as the number of qubits the gate acts on (so the gate must not be broadcast).
        """
        if len(indices) != gate.get_qubit_count():
            msg = f"Expected {gate.get_qubit_count()} indices for {gate}, but got {len(indices)}."
            raise ValueError(msg)

        local_flow_state = flow_state.get_local_pauli_string(indices)

        if local_flow_state.is_identity():
            return flow_state

        try:
            table_for_gate = CliffordFlows.TABLE[gate]
        except KeyError:
            msg = f"Gate {gate} not implemented yet or not Clifford."
            raise NotImplementedError(msg) from None

        new_local_flow_state = table_for_gate[local_flow_state]

        return flow_state.with_updated_local_pauli_string(new_local_flow_state, indices)


# Inverse (DAG) gates of these types have the same stabiliser flows up to sign as the un-daggered
# gates, so we just copy the tables.
CliffordFlows.TABLE[qcore.SGateAttr(dag=True)] = CliffordFlows.TABLE[qcore.SGateAttr()].copy()
CliffordFlows.TABLE[qcore.ISWAPGateAttr(dag=True)] = CliffordFlows.TABLE[
    qcore.ISWAPGateAttr()
].copy()
CliffordFlows.TABLE[qcore.SqrtXXGateAttr(dag=True)] = CliffordFlows.TABLE[
    qcore.SqrtXXGateAttr()
].copy()
CliffordFlows.TABLE[qcore.SqrtYYGateAttr(dag=True)] = CliffordFlows.TABLE[
    qcore.SqrtYYGateAttr()
].copy()
CliffordFlows.TABLE[qcore.SqrtZZGateAttr(dag=True)] = CliffordFlows.TABLE[
    qcore.SqrtZZGateAttr()
].copy()


class MeasurementFlows:
    """Lookup-table based updates for single-qubit measurement gates."""

    @staticmethod
    def find_mmt_gate_pauli_string(
        measure_op: qref.MeasureOp, gate_index_list: list[int], length: int
    ) -> qcore.PauliStringAttr:
        """Return the Pauli string corresponding to the given measurement operator.

        Assumes measure_op is not a broadcast measurement, i.e. it applies only one measurement.
        """
        if measure_op.is_broadcast():
            msg = "Broadcast measurement ops are not supported for measurement Pauli extraction."
            raise ValueError(msg)

        if len(gate_index_list) != len(measure_op.pauli):
            msg = "Gate index list does not match Pauli modifiers provided."
            raise ValueError(msg)

        return qcore.PauliStringAttr(zip(measure_op.pauli, gate_index_list, strict=True), length)

    @staticmethod
    def apply_measurement(
        gate_pauli: qcore.PauliStringAttr,
        flow_state: qcore.PauliStringAttr,
    ) -> list[tuple[qcore.PauliStringAttr, bool]]:
        """Apply a measurement to a flow state.

        Args:
            gate_pauli: The Pauli string corresponding to the measurement operator.
            flow_state: The flow state to apply the measurement to.

        Returns:
            A list of tuples with a flow state and a Boolean describing whether the measurement
            needs to be recorded. If the flow state is blocked by the gate, an empty list is
            returned.

        Stabiliser flow rules
        ---------------------
        If Q is a Pauli string corresponding to the measurement operator M_Q and P is another Pauli
        string, then either:
        - P, Q anti-commute: flow of P through M_Q is not possible
        - P, Q commute:
            - P -> P (measurement not recorded)
            - P -> (-1)^m PQ (measurement is recorded)
        """
        if gate_pauli.commutes(flow_state):
            return [(flow_state, False), (flow_state * gate_pauli, True)]
        # else, flow blocked
        return []


# endregion
# region Rewrite methods for state types


def _verify_flows_compatible(
    flows_to_add: list[qcore.PauliStringAttr], existing_flows: Iterable[qcore.PauliStringAttr]
) -> None:
    """Verify that the flows to add are pairwise commuting and commute with existing flows."""
    for flow1, flow2 in itertools.combinations(flows_to_add, 2):
        if not flow1.commutes(flow2):
            msg = f"Cannot add flows to state type. {flow1} and {flow2} do not commute."
            raise ValueError(msg)
    for flow in flows_to_add:
        for existing_flow in existing_flows:
            if not flow.commutes(existing_flow):
                msg = (
                    f"Cannot add flow {flow} to state type. It does not commute with existing flow "
                    f"{existing_flow} on adjacent circuit."
                )
                raise ValueError(msg)


def update_state_type_adjacent_ops(
    state_type_ssa: SSAValue[StateType],
    flows_to_add: list[qcore.PauliStringAttr],
    rewriter: PatternRewriter,
) -> None:
    """Add flow states to a state type and relabel flows in adjacent operations.

    Finds the operations that produce or consume the given state type and
    updates their flows to reflect the addition of the given flow states.
    If no flow states are provided, no changes are made.

    Note that it is valid to include the identity flow state in the input
    but this will not be added to the state type (by the stab dialect rules).

    Supported operations are stab.circuit, stab.state.permute, and the qstruct.yield ops of
    qstruct.parallel ops. stab.state.make is supported only if flows_to_add is empty since
    StateMakeOps can't have flow states.

    Note that adjacent StatePermuteOps might not verify afterwards. It is the
    caller's responsibility to ensure that compatible flow states are added to
    the input and output of permute ops.

    Args:
        state_type_ssa: The SSA value of the state type at a circuit
            interface.
        flows_to_add: The flow states to add to the state type.
        rewriter: optional rewriter input

    Raises:
        ValueError: If the SSA value does not originate from a valid
            operation, or if a StateMakeOp is asked to add flow states, or
            if the SSA value is not used by a supported operation.
    """
    # StateType cannot include the identity PauliStringAttr([]); identity is represented implicitly.
    flows_to_add = [f for f in flows_to_add if not f.is_identity()]
    if not flows_to_add:
        return

    # find ops
    c1 = state_type_ssa.owner
    c2 = state_type_ssa.get_user_of_unique_use()

    # verify ops
    if not isinstance(c1, (CircuitOp, StatePermuteOp, qstruct.ParallelOp, StateMakeOp)):
        msg = (
            "The input SSA value must result from a stab.CircuitOp, stab.StatePermuteOp, "
            "qstruct.ParallelOp, or stab.StateMakeOp."
        )
        raise ValueError(msg)
    if isinstance(c1, StateMakeOp) and flows_to_add:
        msg = "The SSAValue is the output of a stab.StateMakeOp which can't have any flow states."
        raise ValueError(msg)
    if c2 is not None and not isinstance(c2, (CircuitOp, StatePermuteOp, qstruct.YieldOp)):
        msg = (
            "The input SSA value must be used by a stab.CircuitOp, stab.StatePermuteOp, or "
            "qstruct.YieldOp."
        )
        raise ValueError(msg)
    if isinstance(c2, qstruct.YieldOp) and not isinstance(c2.parent_op(), qstruct.ParallelOp):
        msg = (
            "The input SSA value may only be used by a qstruct.YieldOp if it is the yield of a "
            "qstruct.ParallelOp."
        )
        raise ValueError(msg)

    _verify_flows_compatible(flows_to_add, state_type_ssa.type.states)

    # compute relabelling of flows
    if isinstance(c1, CircuitOp):
        new_c1_flows = ArrayAttr(
            c1.relabel_flows_from_flow_states(input_flow_states=[], output_flow_states=flows_to_add)
        )
    if isinstance(c2, CircuitOp):
        new_c2_flows = ArrayAttr(
            c2.relabel_flows_from_flow_states(input_flow_states=flows_to_add, output_flow_states=[])
        )

    # update state type at interface
    all_flow_states = list(state_type_ssa.type.states) + flows_to_add
    # sort states to be in order for verification, ensure no duplicates continue
    all_flow_states = sorted(set(all_flow_states), key=qcore.PauliStringAttr.sort_key)
    new_state_type = state_type_ssa.type.with_new_flow_states(all_flow_states)
    # rewrite state type
    rewriter.replace_value_with_new_type(state_type_ssa, new_state_type)

    if isinstance(c1, CircuitOp):
        c1.flows = new_c1_flows
        rewriter.notify_op_modified(c1)
    if isinstance(c2, CircuitOp):
        c2.flows = new_c2_flows
        rewriter.notify_op_modified(c2)


@dataclass(frozen=True, slots=True)
class CircuitFlowData:
    """Information for a single flow across a circuit op.

    This groups the following:

    - `input_state`: the flow state before the circuit op
    - `output_state`: the flow state after the circuit op
    - `measurements`: the measurement SSA values recorded for that boundary. These are measurement
        SSA values that appear in the circuit's yield op's measurements list.
    """

    input_state: qcore.PauliStringAttr
    output_state: qcore.PauliStringAttr
    measurements: MMTResults


class WriteFlows:
    """
    Class of methods to write flows onto circuit ops and add detectors where relevant.

    The writing in of flows is done so that the following conditions are met:
    - all input flow states are unique, except for the identity
    - all output flow states are unique, except for the identity
    - the lists of input and output flow states are sorted.
    The writing in methods handle any pre-existing flows written into circuit ops.

    Mid-circuit detectors are found when flows between the same input and output on a
    circuit op exist but with different measurement results.
    """

    @staticmethod
    def _relabel_flows_for_state_type_change(
        flows: ArrayAttr[FlowAttr] | None,
        old_flow_states: Sequence[qcore.PauliStringAttr],
        new_flow_states: Sequence[qcore.PauliStringAttr],
        *,
        input_side: bool,
    ) -> ArrayAttr[FlowAttr] | None:
        """Relabel flow indices after removing states from one side of a circuit interface.
        If input_side is True, relabel the input state indices; otherwise, relabel the output state
        indices. new_flow_states must be a subsequence of old_flow_states.
        Returns None if all flow indices would be removed."""
        if flows is None:
            return None

        new_state_indices = {flow_state: idx for idx, flow_state in enumerate(new_flow_states)}
        relabelled_flows: list[FlowAttr] = []
        for flow in flows:
            old_state_index = flow.input_state_index if input_side else flow.output_state_index
            if old_state_index == qcore.I_STATE_INDEX:
                new_state_index = qcore.I_STATE_INDEX
            else:
                old_state = old_flow_states[old_state_index]
                try:
                    new_state_index = new_state_indices[old_state]
                except KeyError:
                    msg = f"Cannot remove flow state {old_state} while it is used by a flow."
                    raise ValueError(msg) from None

            relabelled_flows.append(
                FlowAttr(
                    flow.sign,
                    flow.measurements,
                    new_state_index if input_side else flow.input_state_index,
                    flow.output_state_index if input_side else new_state_index,
                )
            )
        return ArrayAttr(relabelled_flows) if relabelled_flows else None

    @staticmethod
    def remove_flow_states_from_output(
        circuit: CircuitOp,
        flow_states_to_remove: Iterable[qcore.PauliStringAttr],
        rewriter: PatternRewriter,
    ) -> None:
        """Remove specified flow states from the output of a circuit and update adjacent circuit
        ops. Supports only circuit ops."""
        output_ssa = cast(SSAValue[StateType], circuit.output)
        old_state_type = output_ssa.type
        old_flow_states = list(old_state_type.states)
        flow_states_to_remove = set(flow_states_to_remove)
        new_flow_states = [
            flow_state for flow_state in old_flow_states if flow_state not in flow_states_to_remove
        ]
        if len(new_flow_states) == len(old_flow_states):
            return

        if output_ssa.has_more_than_one_use():
            msg = "Expected a circuit output to have at most one succeeding circuit."
            raise ValueError(msg)
        circuit.flows = WriteFlows._relabel_flows_for_state_type_change(
            circuit.flows, old_flow_states, new_flow_states, input_side=False
        )
        rewriter.notify_op_modified(circuit)

        new_state_type = old_state_type.with_new_flow_states(new_flow_states)
        new_output_ssa = rewriter.replace_value_with_new_type(output_ssa, new_state_type)

        user = new_output_ssa.get_user_of_unique_use()
        if isinstance(user, CircuitOp):
            user.flows = WriteFlows._relabel_flows_for_state_type_change(
                user.flows, old_flow_states, new_flow_states, input_side=True
            )
            rewriter.notify_op_modified(user)

    @staticmethod
    def update_circuit_op(
        flows: list[CircuitFlowData],
        circuit: CircuitOp,
        rewriter: PatternRewriter,
    ) -> None:
        """Mutate circuit op with added flows given by the CircuitFlowData tuples
        in the `flows`. Also add in any new detector ops found."""

        # add in new flow states to state types
        WriteFlows.update_flows_on_ssas(
            flows=flows,
            input_ssa=cast(SSAValue[StateType], circuit.input),
            output_ssa=cast(SSAValue[StateType], circuit.output),
            rewriter=rewriter,
        )
        # update yield
        measurements = [s for f in flows for s in f.measurements]
        for measurement in measurements:
            value = extract_value_from_inner_ops(measurement, circuit.yield_op, rewriter)
            circuit.add_measurements_to_yield((value,), rewriter=rewriter)
        # add in new flow annotations and collect detectors
        annotations, detector_ops = WriteFlows.construct_new_flows_and_detectors(
            flows, circuit, rewriter
        )
        existing_flows = list(circuit.flows) if circuit.flows else []
        sorted_new_flows = existing_flows + annotations
        sorted_new_flows.sort(key=lambda flow: flow.sort_key())
        circuit.flows = ArrayAttr(sorted_new_flows)
        # add detectors if they are independent
        redundant = add_detectors_if_independent(circuit, detector_ops)
        for detector_op in redundant:
            detector_op.erase()

    @staticmethod
    def update_permute_op(
        flows: list[CircuitFlowData],
        permute: StatePermuteOp,
        rewriter: PatternRewriter,
    ) -> None:
        """Mutate the permute op with the given added input/output flow states."""
        # Sanity check: each flow to add is just a valid permutation
        assert all(
            not flow.measurements and flow.output_state == permute.permute_flow(flow.input_state)
            for flow in flows
        )

        # Ensure the state types are updated on both the input and the output
        WriteFlows.update_flows_on_ssas(
            flows=flows,
            input_ssa=cast(SSAValue[StateType], permute.input),
            output_ssa=cast(SSAValue[StateType], permute.output),
            rewriter=rewriter,
        )

    @staticmethod
    def update_flows_on_ssas(
        flows: list[CircuitFlowData],
        input_ssa: SSAValue[StateType],
        output_ssa: SSAValue[StateType],
        rewriter: PatternRewriter,
    ) -> None:
        """Add the input flow states of `flows` to `input_ssa` and the output flow states to
        `output_ssa`, and update adjacent ops."""
        input_flow_states = [flow.input_state for flow in flows]
        update_state_type_adjacent_ops(
            state_type_ssa=input_ssa,
            flows_to_add=input_flow_states,
            rewriter=rewriter,
        )
        output_flow_states = [flow.output_state for flow in flows]
        update_state_type_adjacent_ops(
            state_type_ssa=output_ssa,
            flows_to_add=output_flow_states,
            rewriter=rewriter,
        )

    @staticmethod
    def construct_new_flows_and_detectors(
        flows: list[CircuitFlowData],
        circuit: CircuitOp,
        rewriter: PatternRewriter,
    ) -> tuple[list[FlowAttr], list[qec.DetectorOp]]:
        """From a list of (input, output, measurements) triples, build new FlowAttrs
        to write into `circuit` and collect any detectors.

        Rules:
        - If both input and output are identity and measurements non-empty, record a detector.
        - If a flow already exists on the circuit with the same input and output flow state,
          compare measurements; any difference forms a detector. Do not rewrite a duplicate flow.
          This works since if A ->(m) B is a flow and A ->(M) B is a flow then their product
          I ->(m XOR M) I is a flow and indeed a detector.
        - Otherwise, construct a new FlowAttr:
            * sign = '+'
            * measurements = indices of `mmt_set` in new circuit yield
            * input_state = mapped index from `input_map` unless identity (then I_STATE_INDEX)
            * output_state = mapped index from `output_map` unless identity (then I_STATE_INDEX)

        Returns (list of new FlowAttrs to add, set of detector measurement sets).
        """
        additions: list[FlowAttr] = []
        detector_ops: list[qec.DetectorOp] = []
        used_inputs = set(circuit.used_input_flow_states)
        used_outputs = set(circuit.used_output_flow_states)

        # Deterministic ordering for detector targets and measurement indices: use the order of
        # measurements in the circuit yield (which matches their appearance order).
        yield_measurements: Sequence[SSAValue[I1]] = cast(
            Sequence[SSAValue[I1]], circuit.yield_op.measurements
        )
        yield_index: dict[SSAValue, int] = {m: i for i, m in enumerate(yield_measurements)}

        def extract_measurement_ssas(mmts: Iterable[SSAValue[I1]]) -> SSAValues[SSAValue[I1]]:
            if not mmts:
                return SSAValues()

            # We use 'dummy' detector ops here to store the measurement ssas because
            # extract_value_from_inner_ops might replace/rewrite ops thus invalidating
            # existing SSAValues - by using these values in this op the rewriter's op
            # replacement mechanism will automatically keep the SSAValue references in
            # detector_op up to date.
            detector_op = qec.DetectorOp(measurements=[])
            for mmt in mmts:
                resolved_mmt = extract_value_from_inner_ops(mmt, circuit.yield_op, rewriter)
                new_detector_op = qec.DetectorOp([*detector_op.measurements, resolved_mmt])
                detector_op.erase()
                detector_op = new_detector_op

            result = cast(SSAValues[SSAValue[I1]], detector_op.measurements)
            detector_op.erase()
            return result

        for f in flows:
            inp, out, mmt_set = f.input_state, f.output_state, f.measurements
            # Identity to identity: only detectors are relevant
            if inp.is_identity() and out.is_identity():
                if mmt_set:
                    resolved_mmts = extract_measurement_ssas(mmt_set)
                    detector_ops.append(
                        qec.DetectorOp(sorted(resolved_mmts, key=lambda ssa: yield_index[ssa]))
                    )
                continue

            # Existing matching flow: compare measurements
            flow_match = circuit.find_flow(inp, out)
            if flow_match is not None:
                flow_match_mmt_ssa = OrderedSet[SSAValue[I1]](
                    cast(SSAValue[I1], circuit.yield_op.measurements[idx])
                    for idx in flow_match.measurement_indices
                )
                resolved_mmt_set = MMTResults(extract_measurement_ssas(mmt_set))
                det = resolved_mmt_set.symmetric_difference(flow_match_mmt_ssa)
                if det:
                    detector_ops.append(
                        qec.DetectorOp(sorted(det, key=lambda ssa: yield_index[ssa]))
                    )
                continue

            # if a single input or single output already written then do not add flow
            # annotation as will not verify and we no longer have the flow chain
            # structure for the annotation to be useful
            if inp in used_inputs or out in used_outputs:
                continue

            # Resolve twice since the each extract might make new ops that invalidate the ssa values
            # returned by other calls until all values are available at the circuit level
            for mmt in mmt_set:
                extract_value_from_inner_ops(mmt, circuit.yield_op, rewriter)
            new_mmt_set = [
                extract_value_from_inner_ops(mmt, circuit.yield_op, rewriter) for mmt in mmt_set
            ]
            # Otherwise, add a new flow annotation and add to seen inputs/outputs
            mmt_indices: list[int] = sorted(yield_index[mmt] for mmt in new_mmt_set)
            inp_idx = circuit._find_input_flow_state(inp)
            out_idx = circuit._find_output_flow_state(out)
            # Add a new flow when both indices are found
            if inp_idx is not None and out_idx is not None:
                additions.append(
                    FlowAttr(
                        sign="+",
                        measurements=mmt_indices,
                        input_state=inp_idx,
                        output_state=out_idx,
                    )
                )
            if not inp.is_identity():
                used_inputs.add(inp)
            if not out.is_identity():
                used_outputs.add(out)

        additions = list(set(additions))
        return additions, detector_ops
