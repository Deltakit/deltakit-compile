# RUN: RUN_PYTHON %s True > %t.all_flows.stim && filecheck %s --check-prefixes CHECK,ALL-FLOWS --input-file %t.all_flows.stim
# RUN: RUN_PYTHON %s False > %t.some_flows.stim && filecheck %s --check-prefixes CHECK,SOME-FLOWS --input-file %t.some_flows.stim

# A distance-2 surface code.
# With ALL_FLOWS=True, all stabiliser flows are annotated.
# With ALL_FLOWS=False, stabiliser flows are annotated only on the memory rounds, not initialisation
# and measurement.
# Setup:
#    1-------3
#  / |       | \
# 4  |   6   |  5
#  \ |       | /
#    0-------2
# 4 and 5 are X stabiliser ancillas, 6 is a Z stabiliser ancilla.
# 3-round Z memory experiment, logical is 0 2.
# No parallelisation, all stabilisers measured sequentially.

import sys

from deltakit_compile.frontend.circuit_builder import CircuitProgramBuilder
from deltakit_compile.frontend.common import Circuit, CircuitBuilder, QubitReg
from deltakit_compile.frontend.logical_assembler import LogicalAssembler, LogicalAssemblerConfig
from deltakit_compile.passes.stim.stim_export.pipeline import StimExportPipelineConfig

ALL_FLOWS = sys.argv[1] == "True"

reset_builder = CircuitBuilder()
qreg = reset_builder.add_arg(QubitReg(7))
reset_builder.gate("RZ", qreg[:4])
if ALL_FLOWS:
    reset_builder.add_creation_flow(dict.fromkeys(qreg[:4], "Z"), [])
    reset_builder.add_creation_flow(dict.fromkeys(qreg[:2], "Z"), [])  # logical
reset_circuit = reset_builder.build("reset")


def build_memory(is_first: bool, is_last: bool) -> Circuit:
    memory_builder = CircuitBuilder()
    qreg = memory_builder.add_arg(QubitReg(7))
    memory_builder.gate("RX", qreg[4:])
    memory_builder.gate("CX", (qreg[4], qreg[0]))
    memory_builder.gate("CX", (qreg[4], qreg[1]))
    memory_builder.gate("CX", (qreg[5], qreg[2]))
    memory_builder.gate("CX", (qreg[5], qreg[3]))
    memory_builder.gate("CZ", (qreg[6], qreg[0]))
    memory_builder.gate("CZ", (qreg[6], qreg[1]))
    memory_builder.gate("CZ", (qreg[6], qreg[2]))
    memory_builder.gate("CZ", (qreg[6], qreg[3]))
    meas = memory_builder.measure("X", qreg[4:])
    memory_builder.add_return(meas)

    mx0, mx1, mz = meas
    memory_builder.add_destruction_flow(dict.fromkeys(qreg[:4], "Z"), [mz])
    memory_builder.add_creation_flow(dict.fromkeys(qreg[:4], "Z"), [mz])

    if not is_first:
        memory_builder.add_destruction_flow(dict.fromkeys(qreg[:2], "X"), [mx0])
        memory_builder.add_destruction_flow(dict.fromkeys(qreg[2:4], "X"), [mx1])
    if not is_last:
        memory_builder.add_creation_flow(dict.fromkeys(qreg[:2], "X"), [mx0])
        memory_builder.add_creation_flow(dict.fromkeys(qreg[2:4], "X"), [mx1])

    # logical
    memory_builder.add_flow(dict.fromkeys(qreg[:2], "Z"), dict.fromkeys(qreg[:2], "Z"), [])

    return memory_builder.build(f"memory_first_{is_first}_last_{is_last}")


first_memory_circuit = build_memory(is_first=True, is_last=False)
middle_memory_circuit = build_memory(is_first=False, is_last=False)
last_memory_circuit = build_memory(is_first=False, is_last=True)

meas_builder = CircuitBuilder()
qreg = meas_builder.add_arg(QubitReg(7))
meas = meas_builder.measure("Z", qreg[:4])
meas_builder.add_return(meas)
if ALL_FLOWS:
    meas_builder.add_destruction_flow(dict.fromkeys(qreg[:4], "Z"), meas)
    meas_builder.add_destruction_flow(dict.fromkeys(qreg[:2], "Z"), meas[:2])  # logical
meas_circuit = meas_builder.build("meas")

program_builder = CircuitProgramBuilder()
qreg = program_builder.declare_qubits(QubitReg(7))
program_builder.call_circuit(reset_circuit(qreg))
program_builder.call_circuit(first_memory_circuit(qreg))
program_builder.call_circuit(middle_memory_circuit(qreg))
program_builder.call_circuit(last_memory_circuit(qreg))
program_builder.call_circuit(meas_circuit(qreg))
program = program_builder.build_program()

assembler = LogicalAssembler(
    config=LogicalAssemblerConfig(export_config=StimExportPipelineConfig())
)
result = assembler.compile(program)
print(result.program)

# Note all detectors should be the same except possibly up to measurement and detector ordering.

# CHECK:      R 0 1 2 3
# CHECK-NEXT: TICK
# CHECK-NEXT: RX 4 5 6
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 4 0
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 4 1
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 5 2
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 5 3
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 6 0
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 6 1
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 6 2
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 6 3
# CHECK-NEXT: TICK
# CHECK-NEXT: MX 4 5 6
# CHECK-NEXT: TICK
# CHECK-NEXT: DETECTOR rec[-1]
# CHECK-NEXT: RX 4 5 6
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 4 0
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 4 1
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 5 2
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 5 3
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 6 0
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 6 1
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 6 2
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 6 3
# CHECK-NEXT: TICK
# CHECK-NEXT: MX 4 5 6
# CHECK-NEXT: TICK
# CHECK-DAG:  DETECTOR rec[-4] rec[-1]
# CHECK-DAG:  DETECTOR rec[-6] rec[-3]
# CHECK-DAG:  DETECTOR rec[-5] rec[-2]
# CHECK-NEXT: RX 4 5 6
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 4 0
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 4 1
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 5 2
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 5 3
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 6 0
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 6 1
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 6 2
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 6 3
# CHECK-NEXT: TICK
# CHECK-NEXT: MX 4 5 6
# CHECK-NEXT: TICK
# CHECK-DAG:  DETECTOR rec[-4] rec[-1]
# CHECK-DAG:  DETECTOR rec[-6] rec[-3]
# CHECK-DAG:  DETECTOR rec[-5] rec[-2]
# CHECK-NEXT: M 0 1 2 3
# CHECK-NEXT: TICK
# ALL-FLOWS-DAG:  DETECTOR rec[-5] rec[-4] rec[-3] rec[-2] rec[-1]
# ALL-FLOWS-DAG:  DETECTOR rec[-4] rec[-3]
# SOME-FLOWS-DAG:  DETECTOR rec[-5] rec[-3] rec[-4] rec[-2] rec[-1]
# SOME-FLOWS-DAG:  DETECTOR rec[-3] rec[-4]
