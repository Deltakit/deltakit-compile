from deltakit_compile.dialects import qcore, qref
from deltakit_compile.passes.stim.gate_layer_parallelise import _GateLayer


def test_add_op_gate_first_returns_false_when_adding_another_gate():
    gate = qref.GateOp(gate=qcore.XGateAttr(), qubits=[])
    layer = _GateLayer(gate_first=True, before_noise_op=None, gate_op=gate)
    assert not layer.add_op(qref.GateOp(gate=qcore.XGateAttr(), qubits=[]))


def test_add_op_gate_first_returns_false_when_gate_and_noise():
    noise = qref.PauliNoiseOp(
        probabilities=qcore.PauliNoiseParametersAttr.single_pauli(0.1, 0.2, 0.3),
        qubits=[],
    )
    layer = _GateLayer(
        gate_first=True,
        before_noise_op=None,
        gate_op=qref.GateOp(gate=qcore.XGateAttr(), qubits=[]),
        after_noise_op=noise,
    )
    assert not layer.add_op(qref.GateOp(gate=qcore.XGateAttr(), qubits=[]))


def test_add_op_noise_first_returns_false_when_adding_another_gate():
    noise = qref.PauliNoiseOp(
        probabilities=qcore.PauliNoiseParametersAttr.single_pauli(0.1, 0.2, 0.3),
        qubits=[],
    )
    layer = _GateLayer(
        gate_first=False,
        before_noise_op=noise,
        gate_op=qref.GateOp(gate=qcore.XGateAttr(), qubits=[]),
    )
    assert not layer.add_op(qref.GateOp(gate=qcore.XGateAttr(), qubits=[]))


def test_add_op_noise_first_returns_false_when_already_has_gate_and_noise():
    noise = qref.PauliNoiseOp(
        probabilities=qcore.PauliNoiseParametersAttr.single_pauli(0.1, 0.2, 0.3),
        qubits=[],
    )
    layer = _GateLayer(
        gate_first=False,
        before_noise_op=noise,
        gate_op=qref.GateOp(gate=qcore.XGateAttr(), qubits=[]),
        after_noise_op=noise,
    )
    assert not layer.add_op(qref.GateOp(gate=qcore.XGateAttr(), qubits=[]))
