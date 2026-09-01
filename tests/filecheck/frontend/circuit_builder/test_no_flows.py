# RUN: RUN_PYTHON %s > %t
# RUN: filecheck %s --input-file %t

# A simple program with no flows specified at all.
# Tests that the stabiliser flow pipeline does nothing and doesn't error when generate-flows is
# disabled in this case.

from deltakit_compile.frontend.circuit import Circuit, CircuitBuilder
from deltakit_compile.frontend.circuit_builder import CircuitProgramBuilder
from deltakit_compile.frontend.common import MeasurementBit, QubitReg
from deltakit_compile.frontend.logical_assembler import LogicalAssembler, LogicalAssemblerConfig
from deltakit_compile.passes.stabiliser.pipeline import StabiliserFlowPipelineConfig
from deltakit_compile.passes.stim.stim_export.pipeline import StimExportPipelineConfig


def build_circ() -> Circuit[[QubitReg], MeasurementBit]:
    circ_builder = CircuitBuilder()
    qubit_subset = circ_builder.add_arg(QubitReg(2))
    circ_builder.gate("X", qubit_subset)
    ro = circ_builder.measure("Z", qubit_subset[0])
    circ_builder.add_return(ro)
    return circ_builder.build("circ")


builder = CircuitProgramBuilder()
circ = build_circ()

qubits = builder.declare_qubits(QubitReg(2))
ro0 = builder.call_circuit(circ(qubits))
ro1 = builder.call_circuit(circ(qubits))
ro2 = builder.call_circuit(circ(qubits))
builder.add_return(ro0)
builder.add_return(ro1)
builder.add_return(ro2)

program = builder.build_program()

assembler = LogicalAssembler(
    config=LogicalAssemblerConfig(
        stabiliser_flow_config=StabiliserFlowPipelineConfig(generate_flows=False),
        export_config=StimExportPipelineConfig(),
    )
)
result = assembler.compile(program)
print(result.program)

# CHECK:      X 0 1
# CHECK-NEXT: TICK
# CHECK-NEXT: M 0
# CHECK-NEXT: TICK
# CHECK-NEXT: X 0 1
# CHECK-NEXT: TICK
# CHECK-NEXT: M 0
# CHECK-NEXT: TICK
# CHECK-NEXT: X 0 1
# CHECK-NEXT: TICK
# CHECK-NEXT: M 0
# CHECK-NEXT: TICK
