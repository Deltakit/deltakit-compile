# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Pass to generate stabiliser flows to match those specified by user."""

from __future__ import annotations

import functools
import warnings
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field

import numpy as np
from typing_extensions import Self, override
from xdsl.context import Context
from xdsl.dialects.builtin import IntAttr, ModuleOp
from xdsl.ir import Operation, OpResult, SSAValue
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)

from deltakit_compile.dialects import qcore, qstruct
from deltakit_compile.dialects.stabiliser import (
    CircuitOp,
    StateMakeOp,
    StatePermuteOp,
    StateType,
)
from deltakit_compile.passes.stabiliser._common import (
    CalculateFlows,
    CircuitFlowData,
    FlowChainInfo,
    MatchFlows,
    MMTResults,
    WriteFlows,
)


@dataclass(frozen=True)
class _StateUseDefChainEntry:
    """An entry in a use-def chain of stabiliser states across circuit and other ops.

    The semantics of this structure is that `input_state_ssa` is an operand on `input_operation`
    which is transformed to the result `output_state_ssa` on `output_operation` as a single step in
    the use-def chain.

    We currently support only the following types of steps in the use-def chain: stab.circuit ops,
    stab.state.permute ops, and qstruct.yield ops of qstruct.parallel ops. The first two types of
    steps have the same operation as input and output; the last has a qstruct.yield as the input op
    and its qstruct.parallel parent as the output op.
    """

    input_state_ssa: SSAValue[StateType]
    output_state_ssa: SSAValue[StateType]
    input_operation: Operation
    output_operation: Operation

    def __post_init__(self) -> None:
        if self.input_state_ssa not in self.input_operation.operands:
            msg = "Input state SSA value must be an operand of the input operation."
            raise ValueError(msg)
        if self.output_state_ssa not in self.output_operation.results:
            msg = "Output state SSA value must be a result of the output operation."
            raise ValueError(msg)
        if (
            self._as_circuit_entry() is None
            and self._as_permute_entry() is None
            and not self._is_parallel_entry()
        ):
            msg = (
                "Unsupported use-def chain entry: only stab.circuit ops, stab.state.permute ops, "
                "and qstruct.parallel yields are supported."
            )
            raise NotImplementedError(msg)

    def _as_circuit_entry(self) -> CircuitOp | None:
        if isinstance(op := self.input_operation, CircuitOp) and op == self.output_operation:
            return op
        return None

    def _as_permute_entry(self) -> StatePermuteOp | None:
        if isinstance(op := self.input_operation, StatePermuteOp) and op == self.output_operation:
            return op
        return None

    def _is_parallel_entry(self) -> bool:
        return (
            isinstance(yield_op := self.input_operation, qstruct.YieldOp)
            and isinstance(parallel_op := self.output_operation, qstruct.ParallelOp)
            and yield_op.parent_op() == parallel_op
        )

    def propagate_flow_chains(
        self, flow_chains: list[_FlowChain], chain_length: int
    ) -> list[_FlowChain]:
        if (circuit := self._as_circuit_entry()) is not None:
            return _GenerateFlows.propagate_flows(flow_chains, chain_length, circuit)

        if (permute := self._as_permute_entry()) is not None:
            return _GenerateFlows.propagate_flows_through_permute(flow_chains, permute)

        assert self._is_parallel_entry()
        return _GenerateFlows.trivially_extend_flow_chains(flow_chains)

    def update_from_flows(self, flows: list[CircuitFlowData], rewriter: PatternRewriter) -> None:
        if circuit := self._as_circuit_entry():
            WriteFlows.update_circuit_op(flows, circuit, rewriter)
        elif permute := self._as_permute_entry():
            WriteFlows.update_permute_op(flows, permute, rewriter)
        else:
            assert self._is_parallel_entry()
            WriteFlows.update_flows_on_ssas(
                flows, self.input_state_ssa, self.output_state_ssa, rewriter
            )


class _StateUseDefChain:
    """Represents a chain of circuit ops and other operations taking and returning stabiliser
    states, where the output state of one operation is the input state of the next.

    This structure can only represent linear chains of operations, so operations such as
    stab.concatenate and stab.split as well as branching control flow are not supported.
    """

    def __init__(self, initial_make: StateMakeOp) -> None:
        self._initial_make = initial_make
        self._entries: list[_StateUseDefChainEntry] = []

    @classmethod
    def trace(cls, initial_make: StateMakeOp) -> Self:
        """Trace the use-def chain of ops that use the state initiated by the input StateMakeOp.

        Raise NotImplementedError if a state has multiple users (i.e. the chain is not linear) or
        its use is an unsupported operation.
        """
        chain = cls(initial_make)

        while (consumer_op := chain.final_ssa.get_user_of_unique_use()) is not None:
            if isinstance(consumer_op, (CircuitOp, StatePermuteOp)):
                chain.append(consumer_op.output)
            elif isinstance(yield_op := consumer_op, qstruct.YieldOp):
                # We support only tracing through yields of qstruct.parallel ops
                if isinstance(parallel := yield_op.parent_op(), qstruct.ParallelOp):
                    chain.append(parallel.yield_arg_to_result(chain.final_ssa), input_op=yield_op)
                else:
                    msg = (
                        "Generate flows pass supports tracing through yields of qstruct.parallel "
                        "ops only."
                    )
                    raise NotImplementedError(msg)
            else:
                msg = f"Generate flows pass does not support {consumer_op.name} operations."
                raise NotImplementedError(msg)

        if chain.final_ssa.has_more_than_one_use():
            msg = "State type is used by multiple operations which is not supported."
            raise NotImplementedError(msg)

        return chain

    @property
    def initial_ssa(self) -> SSAValue[StateType]:
        """The SSA value of the state at the start of the chain (after the stab.state.make)."""
        return self._initial_make.output

    @property
    def final_ssa(self) -> SSAValue[StateType]:
        """The SSA value of the state at the end of the chain."""
        if not self._entries:
            return self._initial_make.output
        return self._entries[-1].output_state_ssa

    def append(self, result_ssa: OpResult[StateType], *, input_op: Operation | None = None) -> None:
        """Add `result_ssa` and the operation which outputs it to the use-def chain.

        `input_op` is an operation which takes the current final SSA value of the chain as an
        operand; it defaults to the owner of `result_ssa` if not provided. It is assumed that the
        semantics of `input_op` and `result_ssa.owner` transform the final SSA value of the chain
        to `result_ssa`. For example, `input_op` might be the corresponding qstruct.yield op if
        `result_ssa` is an output of a qstruct.parallel op.
        """
        if input_op is None:
            input_op = result_ssa.owner
        if self.final_ssa not in input_op.operands:
            msg = "The final state SSA value of the chain must be an operand of the input op."
            raise ValueError(msg)

        entry = _StateUseDefChainEntry(
            input_state_ssa=self.final_ssa,
            output_state_ssa=result_ssa,
            input_operation=input_op,
            output_operation=result_ssa.owner,
        )
        self._entries.append(entry)

    def __iter__(self) -> Iterator[_StateUseDefChainEntry]:
        """Iterate over the entries in the use-def chain in order."""
        return iter(self._entries)

    @staticmethod
    def _format_flow_chain_list(flow_chains: list[_FlowChain], idx: int) -> list[CircuitFlowData]:
        """Return flow data for each flow chain at a given operation index.

        Filters out flow chains that are too short to have a flow at `idx`.

        Assumes that all flow chains in `flow_chains` start at the same time.
        This will be guaranteed by the generate-flows pass.
        """
        result: list[CircuitFlowData] = []
        for chain in flow_chains:
            flow = chain.find_flow_in_chain(idx)
            if flow is not None:
                result.append(flow)
        return result

    def update_from_flow_chains(
        self, flow_chains: list[_FlowChain], rewriter: PatternRewriter
    ) -> None:
        """Update each op in this use-def chain using `flow_chains`.

        For each op, this extracts the corresponding per-boundary flow information from every chain
        and, when present, writes those flows and any derived detectors into that operation.
        """
        for idx, chain_entry in enumerate(self):
            flows = self._format_flow_chain_list(flow_chains, idx)
            chain_entry.update_from_flows(flows, rewriter)


@dataclass(frozen=True)
class _FlowChain:
    """Represents an unsigned chain of stabiliser flow states across consecutive circuit operations.

    Note that the unsigned flow chains of a given length and number of qubits form a vector space,
    where the identity flow chain (I -> I -> ... -> I) is the zero vector and "vector addition" is
    given by flow chain multiplication. You can see this by converting each flow state (Pauli
    string) to its symplectic representation: a binary vector of length 2*num_qubits. Then
    Pauli multiplication is just mod-2 vector addition.

    Pauli strings of length n (such as the end states of a set of flow chains) also form a vector
    space of dimension 2n in the same way, via the symplectic representation.

    We frequently exploit this fact to maintain only a basis of flow chains at each point in flow
    propagation, which lets us manipulate only linearly many flow chains rather than keeping track
    of all possible flow chains (of which there are exponentially many).

    Properties:
    - flows: ordered list of flow states
    - measurements: list of measurement result sets between successive flows
      (length must be len(flows) - 1)
    - last_user_flow_age: the age of the last user-specified link in the chain, i.e. the number of
      flow states in the tail of the chain after the last user-specified flow A -> B. None if there
      are no user-specified flows in the chain. E.g., if the chain is
        A -> B -> C -> D
      then the last user flow age is 0 if C -> D is user-specified, else 1 if B -> C is user-
      specified, and so on. Note that if the chain is of length 1 then last_user_flow_age must be
      None because there are no links in the chain - a length 1 chain cannot be a user chain.
    """

    flows: list[qcore.PauliStringAttr]
    measurements: list[MMTResults] = field(default_factory=list)
    last_user_flow_age: int | None = None

    def __post_init__(self) -> None:
        if not self.flows:
            msg = "Flow chain requires at least one flow state."
            raise ValueError(msg)
        if len(self.measurements) != len(self.flows) - 1:
            msg = "Measurement list length must be one less than number of flows."
            raise ValueError(msg)
        if self.last_user_flow_age is not None and not (
            0 <= self.last_user_flow_age < len(self.flows) - 1
        ):
            msg = "Last user flow age must be between 0 and the length of the chain minus 2."
            raise ValueError(msg)
        flows_num_qubits = {f.length.data for f in self.flows}
        if len(flows_num_qubits) != 1:
            msg = (
                "A flow chain requires each flow to be on the same number of qubits, "
                f"but {flows_num_qubits} were found"
            )
            raise ValueError(msg)

    @property
    def age(self) -> int:
        """Returns number of flow states since last I state if exists,
        else, the length of the flow chain.

        Examples: I -> I -> I -> A -> B would have age 2
                  A -> B -> C would have age 3
        """
        for idx, flow in enumerate(reversed(self.flows)):
            if flow.is_identity():
                return idx

        return len(self.flows)

    @property
    def is_user_flow(self) -> bool:
        return self.last_user_flow_age is not None

    @property
    def end_state(self) -> qcore.PauliStringAttr:
        """Returns last flow state in the chain."""
        return self.flows[-1]

    @property
    def is_destruction_chain(self) -> bool:
        """Returns whether the chain ends in the identity flow state."""
        return self.end_state.is_identity()

    @property
    def num_measurements(self) -> int:
        """Returns total number of measurements across the flow chain."""
        return sum(len(mmt) for mmt in self.measurements)

    def add_to_chain(
        self,
        flow: qcore.PauliStringAttr,
        measurements_from_prev: MMTResults | None,
        is_user_flow_flag: bool = False,
    ) -> _FlowChain:
        """Return a new _FlowChain with the new flow and measurements appended."""
        if measurements_from_prev is None:
            measurements_from_prev = MMTResults()

        new_last_user_flow_age: int | None
        if is_user_flow_flag:
            new_last_user_flow_age = 0
        elif self.last_user_flow_age is not None:
            new_last_user_flow_age = self.last_user_flow_age + 1
        else:
            new_last_user_flow_age = None

        return _FlowChain(
            flows=[*self.flows, flow],
            measurements=[
                *self.measurements,
                measurements_from_prev if measurements_from_prev is not None else MMTResults(),
            ],
            last_user_flow_age=new_last_user_flow_age,
        )

    def __len__(self) -> int:
        """Returns length of chain defined to be length of the flows list."""
        return len(self.flows)

    def __mul__(self, other: _FlowChain) -> _FlowChain:
        """
        Returns product of flow chains of same length.
        Pauli product is taken on each PauliStringAttr of the chains' flows.
        Measurements are XORed.
        The product's last user flow age (i.e., whether it's a user flow and where the last user-
        specified link is) is computed based on the ages and last user flow ages of the two chains.
        """
        # if flow chains don't have same length raise an error
        # Note: multiplying flows of lengths m and n to produce a chain
        # of length min(m,n) (over the common circuit ops) is well defined
        # but is not currently implemented.
        if len(self.flows) != len(other.flows):
            msg = "Flow chains provided do not have same length."
            raise ValueError(msg)

        flow_product = [f1 * f2 for f1, f2 in zip(self.flows, other.flows, strict=True)]

        mmt_product = [
            m1.symmetric_difference(m2)
            for m1, m2 in zip(self.measurements, other.measurements, strict=True)
        ]

        # The product of a user flow with another flow is a user flow with the same last user flow
        # age if the other flow is young enough not to modify either of the flow states in the last
        # user-specified link.
        if self.last_user_flow_age is not None and self.last_user_flow_age >= other.age:
            new_last_user_flow_age = self.last_user_flow_age
        elif other.last_user_flow_age is not None and other.last_user_flow_age >= self.age:
            new_last_user_flow_age = other.last_user_flow_age
        else:
            new_last_user_flow_age = None

        return _FlowChain(flow_product, mmt_product, last_user_flow_age=new_last_user_flow_age)

    def find_flow_in_chain(self, circuit_idx: int) -> CircuitFlowData | None:
        """Returns the input flow state, output flow state and measurement results
        that this flow state refers to at the given circuit index. Returns None if the index
        is out of range."""
        # index of circuit must be less than the number of measurements
        # (i.e. 1 less than length of chain)
        if circuit_idx < 0 or circuit_idx >= len(self) - 1:
            return None
        return CircuitFlowData(
            input_state=self.flows[circuit_idx],
            output_state=self.flows[circuit_idx + 1],
            measurements=self.measurements[circuit_idx],
        )

    @staticmethod
    def identity(chain_length: int, num_qubits: IntAttr | int) -> _FlowChain:
        """Returns chain of flows I -> I -> ... -> I of length `chain_length`
        with no measurement history for any of the constituent flows."""
        return _FlowChain(
            flows=[qcore.PauliStringAttr([], num_qubits) for _ in range(chain_length)],
            measurements=[MMTResults() for _ in range(chain_length - 1)],
        )

    def get_continuation_info(self) -> FlowChainInfo:
        """Return the flow chain properties needed to continue propagation."""
        return FlowChainInfo(
            self.end_state, self.age, self.last_user_flow_age, self.num_measurements
        )

    @staticmethod
    def multiply_many(chain_list: Sequence[_FlowChain]) -> _FlowChain:
        """Multiply a non-empty list of flow chains.

        Args:
            chain_list: Chains to multiply. Must contain at least one element.

        Returns:
            The product of all chains in the list, multiplied left-to-right.

        Raises:
            ValueError: If `chain_list` is empty.
        """
        if not chain_list:
            msg = "Require at least one _FlowChain for multiplication."
            raise ValueError(msg)
        product = chain_list[0]
        for chain in chain_list[1:]:
            product *= chain
        return product

    @staticmethod
    def mult_near_identical(chain1: _FlowChain, chain2: _FlowChain) -> _FlowChain:
        """Multiply chains that are identical up to their final flow state.

        This is used for chains like:
        A -> B -> ... -> C -> D and A -> B -> ... -> C -> E,
        where the measurement history up to $C$ is identical.
        """
        if len(chain1) == 1:
            return chain1 * chain2

        if chain1.flows[:-1] != chain2.flows[:-1]:
            msg = "There are flow states, other than the last, that don't match."
            raise ValueError(msg)
        if chain1.measurements[:-1] != chain2.measurements[:-1]:
            msg = "There are measurement results, other than the last, that don't match."
            raise ValueError(msg)
        final_mmt = chain1.measurements[-1].symmetric_difference(chain2.measurements[-1])
        final_flow_state = chain1.end_state * chain2.end_state
        return _FlowChain.identity(
            chain_length=len(chain1) - 1, num_qubits=final_flow_state.length
        ).add_to_chain(final_flow_state, final_mmt)


def _unique_chains(chains: list[_FlowChain]) -> list[_FlowChain]:
    """Return unique chains in input list where uniqueness is defined by
    both flow states and measurements agreeing.
    """
    unique: list[_FlowChain] = []
    for ch in chains:
        if not any(ch.flows == u.flows and ch.measurements == u.measurements for u in unique):
            unique.append(ch)
    return unique


class _GenerateFlows:
    """
    Pass to walk through a module op and annotate flow states and flow attrs to
    circuit ops without annotations. If a circuit op is reached with user-specified
    flow states, output/input flow states are matched where possible. An error is
    raised if a user specified flow cannot be matched. Flows are then propagated
    forward in the output basis given by the user. Flows are immediately written in
    if they end with a destruction flow.

    Algorithmic details
    -------------------
    _FlowChain objects are used to record a single consecutive sequence of flows (
    PauliStringAttrs and corresponding measurements) and a Boolean flag to record
    whether the sequence of flows includes a pre-specified flow or not. For example,
    consecutive circuit ops with flows A -> B, B -> C and C -> D would form the flow
    chain A -> B -> C -> D.

    Such sequences of flows may terminate in a blocked flow e.g. if the flow state D was
    blocked by the next circuit op, the whole chain would be blocked. This means that,
    for instance, B would be blocked by the concatenation of the last 3 circuit ops and
    similarly for A and C etc. In this case, we do not want to record the flows
    A -> B, B -> C and C -> D as we go along as we would have to write, match and then
    delete these flows from circuit ops. This motivates the _FlowChain construction.

    Algorithm explanation:

    _FlowChains are initialised at the start of the first circuit op reached.
    If there are no flows specified, the basis of Pauli strings <X_i, Z_i> is chosen.
    If some flows are specified, this partial basis is supplemented by single qubit
    Paulis X_i and Z_i.

    At each point in time a list of _FlowChains is stored, representing a basis of the space
    of possible flow chains at that point. At each circuit op, the end states of the flow chains
    are propagated through the circuit op. If a circuit op has no user-specified flows, this is
    done by propagating the set of end flow states of the chains through the circuit op using
    the algorithm in CurrentStates. Unblocking is handled in CurrentStates.

    If blocking occurs, it's possible that CurrentStates may report that some flow chains need
    to be multiplied together to form a basis of the remainder of the space of flow chains
    which is not blocked. This is done after each circuit op if necessary.

    If a circuit op has user-specified flows, a Gaussian
    elimination is done to match the end flow state with the inputs of the given
    flows. Corresponding _FlowChains are multiplied accordingly and the matched
    pre-specified flows are appended to the product chains. A warning is raised if
    a user input flow cannot be matched to any generated flows. Any generated flows
    not in the span of the user-specified ones are propagated through as normal.

    Note that I -> I is a valid stabiliser flow across all possible circuit ops.
    Since it's the zero point of the vector space of unsigned flow chains, it is always implied by
    the basis of flow chains and we do not keep track of it explicitly.

    This process repeats until the end of the module op. Any remaining flows are then written in.

    The writing in of _FlowChains is done so that the following conditions are met:
    - all input flow states are unique, except for the identity
    - all output flow states are unique, except for the identity
    - the lists of input and output flow states are sorted.
    The writing in methods handle any pre-existing flows written into circuit ops.
    """

    @staticmethod
    def propagate_flow_chains(
        propagate_by_gates: list[_FlowChain],
        propagate_by_annotations: list[_FlowChain],
        chain_length: int,
        circuit: CircuitOp,
    ) -> list[_FlowChain]:
        """Propagates the flow chains through the circuit and appends the results.

        Args:
            propagate_by_gates: A basis of flow chains to propagate through the circuit by gates.
                The end states should be unique and not the identity. At each index in the flow
                chains, all the flow states should be linearly independent other than the identity.
            propagate_by_annotations: A basis of flow chains to propagate through the circuit using
                the user-specified flow annotations. The identity flow chain is always propagated
                through any creation flows annotated on the circuit and should not be included.
            chain_length: The length of all the flow chains before propagation. This is used in case
                the basis of flow chains is empty, in which case the identity chain is propagated
                by gates.
            circuit: The circuit to propagate the flow chains through.

        Returns:
            The new list of flow chains, consisting of:
              - linear combinations of propagate_by_gates extended with the propagated flow states
                through the circuit
              - the chains in propagate_by_annotations extended via the flow annotations on circuit.
            Flows propagated by annotations take priority. The new flow chains all have length
            `chain_length + 1` and we guarantee that at each index (including the end states), all
            the flow states are linearly independent other than the identity, except when dependent
            flow chains are specified by the user (but the flow states are then still unique).
        """

        # Propagate first by gates - this includes propagating the identity chain (i.e. finding
        # creation flows) always, even if propagate_by_gates is empty.
        qubits = tuple(circuit.qubit_block_args)
        gate_list = list(circuit.body.ops)
        output_states = CalculateFlows.propagate_input_flow_basis(
            [chain.get_continuation_info() for chain in propagate_by_gates], qubits, gate_list
        )

        # Propagate flows in propagate_by_annotations by annotated flows.
        for chain in propagate_by_annotations:
            propagations = circuit.find_flow_outputs(chain.end_state)
            assert len(propagations) == 1
            new_output, mmt = propagations[0]

            # Add the annotated flow to output_states so it can reduce the other flows.
            output_states.add_annotated_flow(new_output, mmt, chain.get_continuation_info())

        # Propagate annotated creation flows.
        iden_propagations = circuit.find_flow_outputs(qcore.PauliStringAttr.identity(len(qubits)))
        for new_output, mmt in iden_propagations:
            # Add the annotated flow to output_states - flow_chain_info=None means creation flow.
            output_states.add_annotated_flow(new_output, mmt, flow_chain_info=None)

        # The list of chains appearing as extension chains in output_states at the end, in order.
        chains_to_extend = propagate_by_gates + propagate_by_annotations

        # Reduce so that the end states of the chains and the flow chains being extended are all
        # linearly independent (and so unique).
        output_states.full_reduce()

        # Append the propagated flow states to the corresponding flow chains.
        new_chains: list[_FlowChain] = []
        identity_chain = _FlowChain.identity(chain_length, len(qubits))
        for state in output_states.get_all_states():
            if state.is_annotated_flow:
                assert len(state.extending_combination) <= 1, (
                    "User-annotated flows cannot be combined with other flows!"
                )

            chain_to_extend = functools.reduce(
                lambda x, y: x * y,
                (chains_to_extend[i] for i in state.extending_combination),
                identity_chain,
            )
            extension_chain = chain_to_extend.add_to_chain(
                flow=state.flow_state,
                measurements_from_prev=state.mmt_ssa,
                is_user_flow_flag=state.is_annotated_flow,
            )
            new_chains.append(extension_chain)

        return new_chains

    @staticmethod
    def match_to_user_by_multiplication(
        non_matching_chains: list[_FlowChain],
        matching_chains: list[_FlowChain],
        unmatched_inputs: list[qcore.PauliStringAttr],
    ) -> tuple[list[_FlowChain], list[_FlowChain]]:
        """Matches user input states with the end products of chains when possible.
        A warning is raised if a user input cannot be matched with any chains.

        Requires that none of the input flow chains are destruction chains; these
        must be filtered out beforehand (and indeed are throughout the generate-flows algorithm).

        Returns a tuple of 2 lists of flow chains:
        1. chains which should be propagated via gates
        2. chains which should be propagated via the user's flow annotations.

        'Leftover' chains, which are:
        - those whose end states are not used in any multiplication to form user input states
        - chains that are used in multiplication but are needed to retain a full basis of flows
        are added to the list of chains for gate propagation.
        """
        chains_to_propagate_via_gates: list[_FlowChain] = []
        chains_to_propagate_via_user: list[_FlowChain] = []

        input_chains: list[_FlowChain] = non_matching_chains + matching_chains
        if not input_chains:
            # No chains to match against; fall back to propagation via gates.
            return non_matching_chains, []

        # find combinations of input chains that form user input flow states
        transform, not_found_indices = MatchFlows.find_linear_transform(
            [chain.end_state for chain in input_chains], unmatched_inputs
        )
        # store chains that are used in a combination to match a user input state
        # that are not user flows (i.e. aren't necessarily carried forward)
        # Track indices of non-user chains used in combinations (avoid unhashable _FlowChain)
        used_non_user_chain_indices: set[int] = set()

        # Iterate only over non-zero entries of the transform matrix.
        # Group column indices by row using a dictionary for clarity.
        rows, cols = np.nonzero(transform)
        rows_list = rows.tolist()
        cols_list = cols.tolist()
        if rows.size:
            row_to_cols: dict[int, list[int]] = {}
            for r, c in zip(rows_list, cols_list, strict=True):
                row_to_cols.setdefault(int(r), []).append(int(c))

            for r in sorted(row_to_cols):
                c_indices = row_to_cols[r]

                chains_to_multiply: list[_FlowChain] = []
                for c_int in c_indices:
                    corresponding_chain = input_chains[c_int]
                    if not corresponding_chain.is_user_flow and c_int < len(non_matching_chains):
                        used_non_user_chain_indices.add(c_int)
                    chains_to_multiply.append(corresponding_chain)

                if chains_to_multiply:
                    product_chain = _FlowChain.multiply_many(chains_to_multiply)
                    chains_to_propagate_via_user.append(product_chain)

        # check whether all user inputs have been matched to
        if not_found_indices:
            # raise warning that cannot find flows corresponding to corresponding input states
            # these won't be continued
            not_found = [unmatched_inputs[idx] for idx in not_found_indices]
            err_flow_string = ", ".join(str(s) for s in not_found)
            warnings.warn(
                (
                    f"Cannot find flows ending with flow states {err_flow_string}. "
                    "These are not continued in the generation of flows."
                ),
                category=UserWarning,
                stacklevel=2,
            )

        # Remove num_matched_rows amount of chains from unique used_non_user_chains
        # to reduce redundancy.
        # This list contains non-user_flow chains only and so may be smaller in
        # length than num_matched_rows, in which case none of these flows
        # are continued.
        num_non_user_chains_to_prop = len(used_non_user_chain_indices) - (
            transform.shape[0] - len(not_found_indices)
        )
        if num_non_user_chains_to_prop > 0:
            # TODO: This could lose some independent flows.
            # keep the youngest chains
            used_non_user_chain_list = [non_matching_chains[i] for i in used_non_user_chain_indices]
            used_non_user_chain_list.sort(key=lambda x: x.age)
            chains_to_propagate_via_gates += used_non_user_chain_list[:num_non_user_chains_to_prop]

        # Exclude chains already used (by identity) when adding remaining non-matching chains
        # note, all matching chains already in list to be propagated via user in outer routine
        # this function need only return new matchings to user input flow states
        chains_to_propagate_via_gates += [
            chain
            for i, chain in enumerate(non_matching_chains)
            if i not in used_non_user_chain_indices
        ]

        return chains_to_propagate_via_gates, chains_to_propagate_via_user

    @staticmethod
    def propagate_flows(
        flow_chains: list[_FlowChain], chain_length: int, circuit: CircuitOp
    ) -> list[_FlowChain]:
        """Propagates flow chains over a circuit op, matching with any
        user flows that are specified.

        Requires that none of the flow chains are destruction chains (i.e. do
        not end in the identity state). These should be filtered out beforehand.

        First, check matching of the end of flow chains with input flows and
        append corresponding outputs if so. Then check compatibility of any
        flow chains determined from previous user-specified flows: the
        condition is that the end of the flow chain state is not in the span of
        the input flow states. If it is, then we know it is a non-trivial
        combination by the first check, so raise a compatibility error.

        Note that the identity flow is handled automatically by
        both propagate_flows_via_annotations and propagate_flow_chains, so we don't
        have to worry about it here.

        Finally, computes a combination matrix for flow chains that can be
        altered. For those that can be altered, flow chains are multiplied
        accordingly. Otherwise, the output state is computed via the physical
        gates pass algorithm.

        Note that this guarantees there are no duplicate flows here as the chains
        are partitioned into non-matching and matching sets, and then some new
        chains are created by multiplication of > 1 other chains.
        """
        # find used input flow states
        used_input_flow_states: Sequence[qcore.PauliStringAttr] = circuit.used_input_flow_states

        # if no user flows then propagate all chains via gates
        if not circuit.flows:
            # No user-specified flows; propagate all chains via gates
            return _GenerateFlows.propagate_flow_chains(
                propagate_by_gates=flow_chains,
                propagate_by_annotations=[],
                chain_length=chain_length,
                circuit=circuit,
            )

        # filter chains whose end state matches input state of a flow annotation
        chains_to_propagate_via_user: list[_FlowChain] = []
        matched_input_states: set[qcore.PauliStringAttr] = set()
        for chain in flow_chains:
            assert not chain.is_destruction_chain
            if chain.end_state in used_input_flow_states:
                chains_to_propagate_via_user.append(chain)
                matched_input_states.add(chain.end_state)

        # user input states that haven't been matched
        unmatched_inputs = [
            state for state in used_input_flow_states if state not in matched_input_states
        ]
        # chains with ends that don't match any user flows
        non_matching_chains = [
            chain for chain in flow_chains if chain.end_state not in used_input_flow_states
        ]

        # if all user inputs are matched then all non-matching chains to be propagated by gates
        if not unmatched_inputs:
            return _GenerateFlows.propagate_flow_chains(
                propagate_by_gates=non_matching_chains,
                propagate_by_annotations=chains_to_propagate_via_user,
                chain_length=chain_length,
                circuit=circuit,
            )

        # all user flows should be retained
        chains_to_propagate_via_gates = [
            chain for chain in non_matching_chains if chain.is_user_flow
        ]
        # try matching unmatched user flows by multiplying chains
        extra_chains_for_gates, extra_chains_for_user = (
            _GenerateFlows.match_to_user_by_multiplication(
                non_matching_chains, chains_to_propagate_via_user, unmatched_inputs
            )
        )
        # TODO: Warn if we can't match some user input flow states
        chains_to_propagate_via_gates += extra_chains_for_gates
        chains_to_propagate_via_user += extra_chains_for_user

        # propagate flows either by gates or flow annotations
        return _GenerateFlows.propagate_flow_chains(
            propagate_by_gates=chains_to_propagate_via_gates,
            propagate_by_annotations=chains_to_propagate_via_user,
            chain_length=chain_length,
            circuit=circuit,
        )

    @staticmethod
    def propagate_flows_through_permute(
        flow_chains: list[_FlowChain], permute: StatePermuteOp
    ) -> list[_FlowChain]:
        """Propagate flow chains through a permute op.

        This is done by applying the permutation to the end flow state of each chain and extending
        each chain with the new flow state and no new measurements.
        """
        return [
            chain.add_to_chain(permute.permute_flow(chain.end_state), measurements_from_prev=None)
            for chain in flow_chains
        ]

    @staticmethod
    def trivially_extend_flow_chains(flow_chains: list[_FlowChain]) -> list[_FlowChain]:
        """Extend each flow chain by adding a trivial flow from the end state to itself.

        This is useful for covering use-def chain steps that do not change the flows.
        """
        return [
            chain.add_to_chain(chain.end_state, measurements_from_prev=None)
            for chain in flow_chains
        ]

    @staticmethod
    def find_flow_chains_for_use_def_chain(use_def_chain: _StateUseDefChain) -> list[_FlowChain]:
        """Generates list of flow chains over the use-def chain given.

        After propagating through each op, chains are filtered, first to ensure there exists at most
        one chain ending in each non-identity state, then to ensure linear independence of the end
        states of chains as best as possible. Destruction chains found are not continued and are
        returned to be written in at the end.
        """
        # The use-def chain must not start with any flows (since it starts with a make op).
        # So we start by propagating just the identity flow chain. Since we propagate a basis of
        # flow chains, the space consisting of just the identity chain is represented by an empty
        # basis. So we propagate an empty basis of chains to start to propagate just identity.
        assert not use_def_chain.initial_ssa.type.flow_states.data
        chains_to_propagate: list[_FlowChain] = []

        chains_to_write: list[_FlowChain] = []
        for idx, chain_entry in enumerate(use_def_chain):
            # propagate through this link in the chain
            current_chain_length = idx + 1
            new_chains = chain_entry.propagate_flow_chains(
                chains_to_propagate, current_chain_length
            )

            chains_to_propagate = _unique_chains(
                [chain for chain in new_chains if not chain.is_destruction_chain]
            )
            chains_to_write.extend(
                _unique_chains([chain for chain in new_chains if chain.is_destruction_chain])
            )

        chains_to_write.extend(chains_to_propagate)
        return chains_to_write


class _GenerateFlowsAndWritePattern(RewritePattern):
    """Rewrite pattern that generates and writes flows on circuit ops within a module op."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, make_op: StateMakeOp, rewriter: PatternRewriter) -> None:
        use_def_chain = _StateUseDefChain.trace(make_op)
        flow_chains_to_write = _GenerateFlows.find_flow_chains_for_use_def_chain(use_def_chain)
        # after each circuit op, flow chains that end in same state are filtered
        # and are left with product of flow chains, which we cannot guarantee have unique
        # flow states at each circuit interface. Uniqueness is guaranteed when
        # updating state types of adjacent circuits
        use_def_chain.update_from_flow_chains(flow_chains_to_write, rewriter)


@dataclass(frozen=True)
class GenerateFlows(ModulePass):
    """Pass that generates and writes flows on circuit ops within a module op."""

    name = "generate-flows"

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        """Apply the generate flows pass."""
        PatternRewriteWalker(
            _GenerateFlowsAndWritePattern(), apply_recursively=False
        ).rewrite_module(op)
