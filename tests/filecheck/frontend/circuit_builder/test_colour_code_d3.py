# RUN: RUN_PYTHON %s True > %t.all_flows.stim && filecheck %s --check-prefixes CHECK,ALL-FLOWS --input-file %t.all_flows.stim
# RUN: RUN_PYTHON %s False > %t.some_flows.stim && filecheck %s --check-prefixes CHECK,SOME-FLOWS --input-file %t.some_flows.stim

# A distance-3 colour code.
# With ALL_FLOWS=True, all stabiliser flows are annotated.
# With ALL_FLOWS=False, stabiliser flows are annotated only on the memory rounds, not initialisation
# and measurement.
# Setup:
# 0-------1------8------2
#  \       \           /
#   \       \         /
#    \       \       /
#     7       3-----4
#      \     /     /
#       \   /     /
#        \ /     /
#         5     9
#          \   /
#           \ /
#            6
# 0-6 are data qubits, 7-9 are ancillas.
# One ancilla per stabiliser, we measure Z then X sequentially.
# 3-round Z memory experiment, logical is 0 1 2.
# No parallelisation for now, all gates are sequential.

import sys

from deltakit_compile.frontend.circuit_builder import CircuitProgramBuilder
from deltakit_compile.frontend.common import Circuit, CircuitBuilder, PauliType, Qubit, QubitReg
from deltakit_compile.frontend.logical_assembler import LogicalAssembler, LogicalAssemblerConfig
from deltakit_compile.passes.stim.stim_export.pipeline import StimExportPipelineConfig

ALL_FLOWS = sys.argv[1] == "True"

STABILISERS = {
    7: [0, 1, 3, 5],
    8: [1, 2, 3, 4],
    9: [3, 4, 5, 6],
}

ANCILLAS = sorted(STABILISERS.keys())

LOGICAL = [0, 1, 2]


def select(reg: QubitReg, indices: list[int]) -> list[Qubit]:
    return [reg[i] for i in indices]


def make_stabiliser(
    kind: PauliType, reg: QubitReg, stabiliser: list[int]
) -> dict[Qubit, PauliType]:
    return dict.fromkeys(select(reg, stabiliser), kind)


def build_initial() -> Circuit:
    reset_builder = CircuitBuilder()
    qreg = reset_builder.add_arg(QubitReg(10))
    reset_builder.gate("RZ", qreg[:7])

    if ALL_FLOWS:
        for stabiliser in STABILISERS.values():
            reset_builder.add_creation_flow(make_stabiliser("Z", qreg, stabiliser), [])

        reset_builder.add_creation_flow(make_stabiliser("Z", qreg, LOGICAL), [])

    return reset_builder.build("reset")


def build_memory(is_first: bool, is_last: bool) -> Circuit:
    memory_builder = CircuitBuilder()
    qreg = memory_builder.add_arg(QubitReg(10))

    # first extract Z stabilisers
    memory_builder.gate("RX", select(qreg, [7, 8, 9]))

    for ancilla, stabiliser in STABILISERS.items():
        for data_qubit in select(qreg, stabiliser):
            memory_builder.gate("CZ", (qreg[ancilla], data_qubit))

    z_meas = memory_builder.measure("X", select(qreg, [7, 8, 9]))

    # then extract X stabilisers
    memory_builder.gate("RX", select(qreg, [7, 8, 9]))

    for ancilla, stabiliser in STABILISERS.items():
        for data_qubit in select(qreg, stabiliser):
            memory_builder.gate("CX", (qreg[ancilla], data_qubit))

    x_meas = memory_builder.measure("X", select(qreg, [7, 8, 9]))

    memory_builder.add_return(z_meas)
    memory_builder.add_return(x_meas)

    for idx, ancilla in enumerate(ANCILLAS):
        memory_builder.add_destruction_flow(
            make_stabiliser("Z", qreg, STABILISERS[ancilla]), [z_meas[idx]]
        )
        memory_builder.add_creation_flow(
            make_stabiliser("Z", qreg, STABILISERS[ancilla]), [z_meas[idx]]
        )
        if not is_first:
            memory_builder.add_destruction_flow(
                make_stabiliser("X", qreg, STABILISERS[ancilla]), [x_meas[idx]]
            )
        if not is_last:
            memory_builder.add_creation_flow(
                make_stabiliser("X", qreg, STABILISERS[ancilla]), [x_meas[idx]]
            )

    logical = make_stabiliser("Z", qreg, LOGICAL)
    memory_builder.add_flow(logical, logical, [])

    return memory_builder.build(f"memory_first_{is_first}_last_{is_last}")


def build_final() -> Circuit:
    meas_builder = CircuitBuilder()
    qreg = meas_builder.add_arg(QubitReg(10))
    meas = meas_builder.measure("Z", qreg[:7])
    meas_builder.add_return(meas)

    if ALL_FLOWS:
        for stabiliser in STABILISERS.values():
            stabiliser_meas = [meas[idx] for idx in stabiliser]
            meas_builder.add_destruction_flow(
                make_stabiliser("Z", qreg, stabiliser), stabiliser_meas
            )

        logical_meas = [meas[idx] for idx in LOGICAL]
        meas_builder.add_destruction_flow(make_stabiliser("Z", qreg, LOGICAL), logical_meas)

    return meas_builder.build("meas")


initial_circuit = build_initial()
first_memory_circuit = build_memory(is_first=True, is_last=False)
middle_memory_circuit = build_memory(is_first=False, is_last=False)
last_memory_circuit = build_memory(is_first=False, is_last=True)
final_circuit = build_final()

program_builder = CircuitProgramBuilder()
qreg = program_builder.declare_qubits(QubitReg(10))
program_builder.call_circuit(initial_circuit(qreg))
program_builder.call_circuit(first_memory_circuit(qreg))
program_builder.call_circuit(middle_memory_circuit(qreg))
program_builder.call_circuit(last_memory_circuit(qreg))
program_builder.call_circuit(final_circuit(qreg))
program = program_builder.build_program()

assembler = LogicalAssembler(
    config=LogicalAssemblerConfig(export_config=StimExportPipelineConfig())
)
result = assembler.compile(program)
print(result.program)

# Note all detectors should be the same except possibly up to measurement and detector ordering.

# CHECK:      R 0 1 2 3 4 5 6
# CHECK-NEXT: TICK
# CHECK-NEXT: RX 7 8 9
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 7 0
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 7 1
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 7 3
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 7 5
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 8 1
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 8 2
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 8 3
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 8 4
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 9 3
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 9 4
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 9 5
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 9 6
# CHECK-NEXT: TICK
# CHECK-NEXT: MX 7 8 9
# CHECK-NEXT: TICK
# CHECK-NEXT: RX 7 8 9
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 7 0
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 7 1
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 7 3
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 7 5
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 8 1
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 8 2
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 8 3
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 8 4
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 9 3
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 9 4
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 9 5
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 9 6
# CHECK-NEXT: TICK
# CHECK-NEXT: MX 7 8 9
# CHECK-NEXT: TICK
# CHECK-DAG:  DETECTOR rec[-6]
# CHECK-DAG:  DETECTOR rec[-5]
# CHECK-DAG:  DETECTOR rec[-4]
# CHECK-NEXT: RX 7 8 9
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 7 0
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 7 1
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 7 3
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 7 5
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 8 1
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 8 2
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 8 3
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 8 4
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 9 3
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 9 4
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 9 5
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 9 6
# CHECK-NEXT: TICK
# CHECK-NEXT: MX 7 8 9
# CHECK-NEXT: TICK
# CHECK-NEXT: RX 7 8 9
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 7 0
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 7 1
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 7 3
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 7 5
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 8 1
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 8 2
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 8 3
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 8 4
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 9 3
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 9 4
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 9 5
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 9 6
# CHECK-NEXT: TICK
# CHECK-NEXT: MX 7 8 9
# CHECK-NEXT: TICK
# CHECK-DAG:  DETECTOR rec[-9] rec[-3]
# CHECK-DAG:  DETECTOR rec[-12] rec[-6]
# CHECK-DAG:  DETECTOR rec[-8] rec[-2]
# CHECK-DAG:  DETECTOR rec[-11] rec[-5]
# CHECK-DAG:  DETECTOR rec[-7] rec[-1]
# CHECK-DAG:  DETECTOR rec[-10] rec[-4]
# CHECK-NEXT: RX 7 8 9
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 7 0
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 7 1
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 7 3
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 7 5
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 8 1
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 8 2
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 8 3
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 8 4
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 9 3
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 9 4
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 9 5
# CHECK-NEXT: TICK
# CHECK-NEXT: CZ 9 6
# CHECK-NEXT: TICK
# CHECK-NEXT: MX 7 8 9
# CHECK-NEXT: TICK
# CHECK-NEXT: RX 7 8 9
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 7 0
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 7 1
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 7 3
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 7 5
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 8 1
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 8 2
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 8 3
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 8 4
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 9 3
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 9 4
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 9 5
# CHECK-NEXT: TICK
# CHECK-NEXT: CNOT 9 6
# CHECK-NEXT: TICK
# CHECK-NEXT: MX 7 8 9
# CHECK-NEXT: TICK
# CHECK-DAG:  DETECTOR rec[-9] rec[-3]
# CHECK-DAG:  DETECTOR rec[-12] rec[-6]
# CHECK-DAG:  DETECTOR rec[-8] rec[-2]
# CHECK-DAG:  DETECTOR rec[-11] rec[-5]
# CHECK-DAG:  DETECTOR rec[-7] rec[-1]
# CHECK-DAG:  DETECTOR rec[-10] rec[-4]
# CHECK-NEXT: M 0 1 2 3 4 5 6
# CHECK-NEXT: TICK
# ALL-FLOWS-DAG:  DETECTOR rec[-7] rec[-6] rec[-5]
# ALL-FLOWS-DAG:  DETECTOR rec[-13] rec[-7] rec[-6] rec[-4] rec[-2]
# ALL-FLOWS-DAG:  DETECTOR rec[-12] rec[-6] rec[-5] rec[-4] rec[-3]
# ALL-FLOWS-DAG:  DETECTOR rec[-11] rec[-4] rec[-2] rec[-3] rec[-1]
# SOME-FLOWS-DAG:  DETECTOR rec[-5] rec[-7] rec[-6]
# SOME-FLOWS-DAG:  DETECTOR rec[-13] rec[-7] rec[-6] rec[-4] rec[-2]
# SOME-FLOWS-DAG:  DETECTOR rec[-12] rec[-5] rec[-6] rec[-4] rec[-3]
# SOME-FLOWS-DAG:  DETECTOR rec[-11] rec[-4] rec[-3] rec[-2] rec[-1]
