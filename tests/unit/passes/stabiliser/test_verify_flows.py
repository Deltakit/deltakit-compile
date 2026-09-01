"""Tests for stab_flow_verification_pass.py"""

import re
from collections.abc import Callable

import pytest
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Block, SSAValue

from deltakit_compile.dialects import qcore, qref, qstruct
from deltakit_compile.dialects.stabiliser import (
    CircuitOp,
    FlowAttr,
    StateMakeOp,
    StateType,
    StateTypePauliStrings,
    YieldOp,
)
from deltakit_compile.exceptions import InvalidStabiliserFlowError
from deltakit_compile.passes.stabiliser.verify_flows import VerifyFlows

# --- Local helpers to build StateType and CircuitOp consistently ---


def mk_state_type(qubits: int, flows: StateTypePauliStrings) -> StateType:
    """Create a StateType with a single flow state over the given number of qubits."""
    return StateType(qubits=qubits, qubit_type=qcore.QubitType(), flow_states=flows)


def mk_circuit_op(
    input_qubits: int,
    input_flows: StateTypePauliStrings,
    output_flows: StateTypePauliStrings,
    add_ops: Callable[[Block], None],
    flows: list[FlowAttr] | None,
    add_yield: bool = True,
) -> CircuitOp:
    """Construct a CircuitOp.

    Args:
        input_qubits: Number of input qubits for the circuit body.
        input_flows: PauliStringAttr for the input stabiliser state.
        output_flows: PauliStringAttr for the expected output stabiliser state.
        add_ops: A function that takes a Block and mutates it by adding gate ops in order.
        flows: A list of FlowAttr annotations or None.
        add_yield: Whether to automatically add a YieldOp at the end with autodetected measurements.

    Returns:
        A CircuitOp constructed from the arguments.
    """
    qb_ops = [qcore.AllocQubitOp(qcore.QubitType()) for _ in range(input_qubits)]
    input_state = StateMakeOp(
        input_qubits=[qb.result[0] for qb in qb_ops],
        state_type=mk_state_type(input_qubits, input_flows),
    )

    body = Block(arg_types=[qcore.QubitType() for _ in range(input_qubits)])
    add_ops(body)

    if add_yield:
        # Append a terminator: stab.YieldOp. Collect measurement readouts in order, yield no args.
        measurements: list[SSAValue] = []
        for op in body.ops:
            if isinstance(op, qref.MeasureOp):
                measurements.extend(op.measurements)
        body.add_op(YieldOp(measurements, []))

    return CircuitOp(
        input_state.output,
        output_state_type=mk_state_type(input_qubits, output_flows),
        input_args=[],
        output_args_types=[],
        body=body,
        flows=flows,
    )


@pytest.fixture
def build_circuit1():
    """2-qubit circuit: input X, H then S on q0, MZ on q1, measurement history should mismatch."""

    def _add_ops(body: Block):
        q0, q1 = body.args
        body.add_op(qref.GateOp(qcore.HGateAttr(), [q0]))
        body.add_op(qref.GateOp(qcore.SGateAttr(), [q0]))
        body.add_op(qref.MeasureOp("Z", [q1]))

    return mk_circuit_op(
        input_qubits=2,
        input_flows=[[("X", 0)]],
        output_flows=[[("Z", 0)]],
        add_ops=_add_ops,
        flows=[FlowAttr("+", [0], 0, 0)],
    )


@pytest.fixture
def build_circuit2():
    """2-qubit circuit: input Z0,X1, measure Z on qubit1 (flow blocked for X on measurement)."""

    def _add_ops(body: Block):
        q1 = body.args[1]
        body.add_op(qref.MeasureOp("Z", [q1]))

    return mk_circuit_op(
        input_qubits=2,
        input_flows=[[("Z", 0), ("X", 1)]],
        output_flows=[[("Z", 0)]],
        add_ops=_add_ops,
        flows=[FlowAttr("+", [0], 0, 0)],
    )


@pytest.fixture
def build_circuit3():
    """2-qubit circuit: input Z0,X1, S on qubit0, output expects Z but mismatch triggered."""

    def _add_ops(body: Block):
        q0 = body.args[0]
        body.add_op(qref.GateOp(qcore.SGateAttr(), [q0]))

    return mk_circuit_op(
        input_qubits=2,
        input_flows=[[("Z", 0), ("X", 1)]],
        output_flows=[[("Z", 0)]],
        add_ops=_add_ops,
        flows=[FlowAttr("+", [], 0, 0)],
    )


@pytest.fixture
def build_circuit_pass_1q_h():
    """1-qubit circuit that should pass: input X, apply H, expect output Z, no measurements."""

    def _add_ops(body: Block):
        (q0,) = body.args
        body.add_op(qref.GateOp(qcore.HGateAttr(), [q0]))

    return mk_circuit_op(
        input_qubits=1,
        input_flows=[[("X", 0)]],
        output_flows=[[("Z", 0)]],
        add_ops=_add_ops,
        flows=[FlowAttr("+", [], 0, 0)],
    )


def test_wrong_output_flow_given(build_circuit3: CircuitOp):
    """Test error raised when wrong output flow given for an input flow that is not blocked."""
    with pytest.raises(
        InvalidStabiliserFlowError,
        match=re.escape(
            "Input flow state does not propagate to output flow state given. Input flow: Z0 X1; "
            "Desired output: Z0. Valid flows: span of [Z0 X1]."
        ),
    ):
        VerifyFlows.check_circuit_op(build_circuit3)


def test_input_flow_blocked(build_circuit2: CircuitOp):
    """Test error raised when input flow is blocked."""
    with pytest.raises(
        InvalidStabiliserFlowError,
        match=re.escape(
            "Input flow state does not propagate to output flow state given. Input flow: Z0 X1; "
            "Desired output: Z0. Valid flows: span of [Z1]."
        ),
    ):
        VerifyFlows.check_circuit_op(build_circuit2)


def test_wrong_measurements_given(build_circuit1: CircuitOp):
    """Test error raised when input flow and output flow states match but measurement
    annotations do not."""
    with pytest.raises(
        InvalidStabiliserFlowError,
        match=re.escape(
            "Measurement history given does not match given flow annotations. Flow X0 -> Z0 exists "
            "but specified measurement set is not achievable."
        ),
    ):
        VerifyFlows.check_circuit_op(build_circuit1)


def test_circuit_should_pass(build_circuit_pass_1q_h: CircuitOp):
    """Test where no exceptions are raised."""
    VerifyFlows.check_circuit_op(build_circuit_pass_1q_h)


def test_validate_stabiliser_flow_additional_pass_case():
    """Another pass case: H maps X->Z and no measurements, matching annotation."""

    def _add_ops(body: Block):
        (q0,) = body.args
        body.add_op(qref.GateOp(qcore.HGateAttr(), [q0]))

    circuit = mk_circuit_op(
        input_qubits=1,
        input_flows=[[("X", 0)]],
        output_flows=[[("Z", 0)]],
        add_ops=_add_ops,
        flows=[FlowAttr("+", [], 0, 0)],
    )
    VerifyFlows.check_circuit_op(circuit)


def test_validate_stabiliser_flow_yield_reordered_measurements_map_correctly():
    """Ensure measurement indices in FlowAttr are matched to YieldOp order, not gate order.

    Build a circuit with two measurements M_Z(q0) then M_Z(q1), but the YieldOp lists
    the readouts in reversed order [readout_q1, readout_q0]. The flow annotation should
    refer to the YieldOp index of the recorded measurement (0 for q1 in this case).
    """

    # Allocate 2 qubits and make an input state with Z0
    qb_ops = [qcore.AllocQubitOp(qcore.QubitType()) for _ in range(2)]
    input_state = StateMakeOp(
        input_qubits=[qb.result[0] for qb in qb_ops],
        state_type=mk_state_type(2, [[("Z", 0)]]),
    )

    # Build body: measure Z on q0 then Z on q1
    body = Block(arg_types=[qcore.QubitType(), qcore.QubitType()])
    q0, q1 = body.args
    m0 = qref.MeasureOp("Z", [q0])
    m1 = qref.MeasureOp("Z", [q1])
    body.add_op(m0)
    body.add_op(m1)

    # Yield measurements in reversed order: [readout_q1, readout_q0]
    # No additional arguments yielded
    body.add_op(YieldOp([*m1.measurements, *m0.measurements], []))

    # Expect the branch that records the second measurement only (q1), giving Z0+Z1.
    output_state_type = mk_state_type(2, [[("Z", 0), ("Z", 1)]])

    circuit = CircuitOp(
        input_state.output,
        output_state_type=output_state_type,
        input_args=[],
        output_args_types=[],
        body=body,
        # FlowAttr measurement indices should refer to YieldOp ordering: q1 is index 0
        flows=[FlowAttr("+", [0], 0, 0)],
    )

    # Should validate successfully using YieldOp-based measurement index mapping
    VerifyFlows.check_circuit_op(circuit)


def test_validate_stabiliser_flow_two_qubit_cx_chain_pass():
    """End-to-end: CX keeps X on target unchanged; annotation matches."""

    def _add_ops(body: Block):
        q0, q1 = body.args
        body.add_op(qref.GateOp(qcore.CXGateAttr(), [q0, q1]))

    circuit = mk_circuit_op(
        input_qubits=2,
        input_flows=[[("X", 1)]],
        output_flows=[[("X", 1)]],
        add_ops=_add_ops,
        flows=[FlowAttr("+", [], 0, 0)],
    )
    VerifyFlows.check_circuit_op(circuit)


def test_validate_stabiliser_flow_swap_then_h_pass():
    """End-to-end: SWAP then H maps Z0 -> Z1 -> X1; annotation matches."""

    def _add_ops(body: Block):
        q0, q1 = body.args
        body.add_op(qref.GateOp(qcore.SWAPGateAttr(), [q0, q1]))
        body.add_op(qref.GateOp(qcore.HGateAttr(), [q1]))

    circuit = mk_circuit_op(
        input_qubits=2,
        input_flows=[[("Z", 0)]],
        output_flows=[[("X", 1)]],
        add_ops=_add_ops,
        flows=[FlowAttr("+", [], 0, 0)],
    )
    VerifyFlows.check_circuit_op(circuit)


def test_validate_stabiliser_flow_iswap_pass():
    """End-to-end: ISWAP maps Z1 -> Z0; annotation matches."""

    def _add_ops(body: Block):
        q0, q1 = body.args
        body.add_op(qref.GateOp(qcore.ISWAPGateAttr(), [q0, q1]))

    circuit = mk_circuit_op(
        input_qubits=2,
        input_flows=[[("Z", 1)]],
        output_flows=[[("Z", 0)]],
        add_ops=_add_ops,
        flows=[FlowAttr("+", [], 0, 0)],
    )
    VerifyFlows.check_circuit_op(circuit)


def test_validate_stabiliser_flow_apply_noop_module():
    """apply() should run without error on an empty module (no CircuitOps)."""
    mod = ModuleOp([])
    ctx = Context()
    VerifyFlows().apply(ctx, mod)


def test_validate_stabiliser_flow_measurement_z_branch_from_identity_to_z_pass():
    """End-to-end: identity input measured Z -> Z with measurement recorded.
    Annotation should match."""

    def _add_ops(body: Block):
        (q0,) = body.args
        body.add_op(qref.MeasureOp("Z", [q0]))

    circuit = mk_circuit_op(
        input_qubits=1,
        input_flows=[[("Z", 0)]],
        output_flows=[[("Z", 0)]],
        add_ops=_add_ops,
        flows=[FlowAttr("+", [0], qcore.I_STATE_INDEX, 0)],
    )
    VerifyFlows.check_circuit_op(circuit)


def test_validate_stabiliser_flow_measurement_z_branch_z_to_z_no_record_pass():
    """End-to-end: Z input measured Z -> Z without recording; annotation (empty) matches."""

    def _add_ops(body: Block):
        (q0,) = body.args
        body.add_op(qref.MeasureOp("Z", [q0]))

    circuit = mk_circuit_op(
        input_qubits=1,
        input_flows=[[("Z", 0)]],
        output_flows=[[("Z", 0)]],
        add_ops=_add_ops,
        flows=[FlowAttr("+", [], 0, 0)],
    )
    VerifyFlows.check_circuit_op(circuit)


def test_validate_stabiliser_flow_measurement_z_branch_z_to_identity_with_record():
    """End-to-end: Z input measured Z -> identity with recording.
    Annotation should match (xfail due to type mismatch)."""

    def _add_ops(body: Block):
        (q0,) = body.args
        body.add_op(qref.MeasureOp("Z", [q0]))

    circuit = mk_circuit_op(
        input_qubits=1,
        input_flows=[[("Z", 0)]],
        output_flows=[[("Z", 0)]],
        add_ops=_add_ops,
        flows=[FlowAttr("+", [0], 0, qcore.I_STATE_INDEX)],
    )
    VerifyFlows.check_circuit_op(circuit)


def test_validate_stabiliser_flow_h_then_measure_z_no_record_pass():
    """Mixed: H then M_Z on q0; input X0 -> Z0; choose Z branch without recording."""

    def _add_ops(body: Block):
        (q0,) = body.args
        body.add_op(qref.GateOp(qcore.HGateAttr(), [q0]))
        body.add_op(qref.MeasureOp("Z", [q0]))

    circuit = mk_circuit_op(
        input_qubits=1,
        input_flows=[[("X", 0)]],
        output_flows=[[("Z", 0)]],
        add_ops=_add_ops,
        flows=[FlowAttr("+", [], 0, 0)],
    )
    VerifyFlows.check_circuit_op(circuit)


def test_validate_stabiliser_flow_h_then_measure_z_record_identity_pass():
    """Mixed: H then M_Z on q0; input X0 -> identity with recording."""

    def _add_ops(body: Block):
        (q0,) = body.args
        body.add_op(qref.GateOp(qcore.HGateAttr(), [q0]))
        body.add_op(qref.MeasureOp("Z", [q0]))

    circuit = mk_circuit_op(
        input_qubits=1,
        input_flows=[[("X", 0)]],
        output_flows=[[("Z", 0)]],
        add_ops=_add_ops,
        flows=[FlowAttr("+", [0], 0, qcore.I_STATE_INDEX)],
    )
    VerifyFlows.check_circuit_op(circuit)


def test_validate_stabiliser_flow_two_measurements_same_qubit_passes_z_branch():
    """Two M_Z on q0 starting from identity.
    Choose branch record then no-record -> final Z, measurements {0}."""

    def _add_ops(body: Block):
        (q0,) = body.args
        body.add_op(qref.MeasureOp("Z", [q0]))
        body.add_op(qref.MeasureOp("Z", [q0]))

    circuit = mk_circuit_op(
        input_qubits=1,
        input_flows=[[("Z", 0)]],
        output_flows=[[("Z", 0)]],
        add_ops=_add_ops,
        flows=[FlowAttr("+", [0], qcore.I_STATE_INDEX, 0)],
    )
    VerifyFlows.check_circuit_op(circuit)


def test_validate_stabiliser_flow_two_measurements_same_qubit_passes_identity_branch():
    """Two M_Z on q0 starting from Z.
    Choose no-record then record -> final identity, measurements {1}."""

    def _add_ops(body: Block):
        (q0,) = body.args
        body.add_op(qref.MeasureOp("Z", [q0]))
        body.add_op(qref.MeasureOp("Z", [q0]))

    circuit = mk_circuit_op(
        input_qubits=1,
        input_flows=[[("Z", 0)]],
        output_flows=[[("Z", 0)]],
        add_ops=_add_ops,
        flows=[FlowAttr("+", [1], 0, qcore.I_STATE_INDEX)],
    )
    VerifyFlows.check_circuit_op(circuit)


def test_validate_stabiliser_flow_measure_two_qubits_records_both_to_z0_z1_pass():
    """Measure Z on q0 then q1 from identity.
    Choose record both -> final Z0+Z1 with measurements {0,1}."""

    def _add_ops(body: Block):
        q0, q1 = body.args
        body.add_op(qref.MeasureOp("Z", [q0]))
        body.add_op(qref.MeasureOp("Z", [q1]))

    circuit = mk_circuit_op(
        input_qubits=2,
        input_flows=[[("X", 0)]],
        output_flows=[[("Z", 0), ("Z", 1)]],
        add_ops=_add_ops,
        flows=[FlowAttr("+", [0, 1], qcore.I_STATE_INDEX, 0)],
    )
    VerifyFlows.check_circuit_op(circuit)


def test_validate_stabiliser_flow_two_measurements_same_qubit_wrong_measurements_error():
    """Mismatch: annotations {} not valid for Z output starting from identity.
    Should be {0} or {1}."""

    def _add_ops(body: Block):
        (q0,) = body.args
        body.add_op(qref.MeasureOp("Z", [q0]))
        body.add_op(qref.MeasureOp("Z", [q0]))

    circuit = mk_circuit_op(
        input_qubits=1,
        input_flows=[[("Z", 0)]],
        output_flows=[[("Z", 0)]],
        add_ops=_add_ops,
        flows=[FlowAttr("+", [], qcore.I_STATE_INDEX, 0)],
    )
    with pytest.raises(
        InvalidStabiliserFlowError,
        match=re.escape(
            "Measurement history given does not match given flow annotations. Flow I -> Z0 exists "
            "but specified measurement set is not achievable."
        ),
    ):
        VerifyFlows.check_circuit_op(circuit)


def test_validate_stabiliser_flow_cx_then_measure_control_record_pass():
    """Mixed: CX then M_Z(q0); input X1 -> record branch yields X1+Z0."""

    def _add_ops(body: Block):
        q0, q1 = body.args
        body.add_op(qref.GateOp(qcore.CXGateAttr(), [q0, q1]))
        body.add_op(qref.MeasureOp("Z", [q0]))

    circuit = mk_circuit_op(
        input_qubits=2,
        input_flows=[[("X", 1)]],
        output_flows=[[("X", 1), ("Z", 0)]],
        add_ops=_add_ops,
        flows=[FlowAttr("+", [0], 0, 0)],
    )
    VerifyFlows.check_circuit_op(circuit)


def test_validate_stabiliser_flow_swap_then_measure_z_record_identity_pass():
    """Mixed: SWAP then M_Z(q1); input Z0 -> identity with recording."""

    def _add_ops(body: Block):
        q0, q1 = body.args
        body.add_op(qref.GateOp(qcore.SWAPGateAttr(), [q0, q1]))
        body.add_op(qref.MeasureOp("Z", [q1]))

    circuit = mk_circuit_op(
        input_qubits=2,
        input_flows=[[("Z", 0)]],
        output_flows=[[("Z", 1)]],
        add_ops=_add_ops,
        flows=[FlowAttr("+", [0], 0, qcore.I_STATE_INDEX)],
    )
    VerifyFlows.check_circuit_op(circuit)


def test_validate_stabiliser_flow_parallel():
    """The measurement SSA value is resolved correctly when a measurement is inside a parallel."""

    def _add_ops(body: Block):
        (q0,) = body.args
        mz = qref.MeasureOp("Z", [q0])
        par_region = Block([mz, qstruct.YieldOp(mz.measurement)])
        parallel = qstruct.ParallelOp(result_types=[mz.measurement.type], par_regions=[par_region])
        body.add_op(parallel)
        body.add_op(YieldOp(parallel.results, []))

    circuit = mk_circuit_op(
        input_qubits=1,
        input_flows=[[("Z", 0)]],
        output_flows=[],
        add_ops=_add_ops,
        flows=[FlowAttr("+", [0], 0, qcore.I_STATE_INDEX)],
        add_yield=False,
    )
    VerifyFlows.check_circuit_op(circuit)


def test_validate_stabiliser_flow_on_module_op():
    """Test that multiple circuit ops in a module op are validated independently."""

    # Circuit 1 (1 flow): 1-qubit H gate, X -> Z, no measurements
    def _add_ops_c1(body: Block):
        (q0,) = body.args
        body.add_op(qref.GateOp(qcore.HGateAttr(), [q0]))

    circuit1 = mk_circuit_op(
        input_qubits=1,
        input_flows=[[("X", 0)]],
        output_flows=[[("Z", 0)]],
        add_ops=_add_ops_c1,
        flows=[FlowAttr("+", [], 0, 0)],
    )

    # Circuit 2 (1 flow): 2-qubit CX, X1 -> X1
    def _add_ops_c2(body: Block):
        q0, q1 = body.args
        body.add_op(qref.GateOp(qcore.CXGateAttr(), [q0, q1]))

    circuit2 = mk_circuit_op(
        input_qubits=2,
        input_flows=[[("X", 1)]],
        output_flows=[[("X", 1)]],
        add_ops=_add_ops_c2,
        flows=[
            FlowAttr("+", [], 0, 0),  # X1 -> X1
        ],
    )

    # Circuit 3 (2 flows): 1-qubit M_Z, support both Z branch cases
    # - identity -> Z with record [0]
    # - Z -> Z with no record
    def _add_ops_c3(body: Block):
        (q0,) = body.args
        body.add_op(qref.MeasureOp("Z", [q0]))

    circuit3 = mk_circuit_op(
        input_qubits=1,
        input_flows=[[("Z", 0)]],
        output_flows=[[("Z", 0)]],
        add_ops=_add_ops_c3,
        flows=[
            FlowAttr("+", [0], qcore.I_STATE_INDEX, 0),  # I -> Z with record
            FlowAttr("+", [], 0, 0),  # Z -> Z with no record
        ],
    )

    # Bundle into a module op and run the pass
    mod = ModuleOp([circuit1, circuit2, circuit3])
    ctx = Context()
    VerifyFlows().apply(ctx, mod)
