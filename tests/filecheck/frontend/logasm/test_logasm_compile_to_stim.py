# RUN: RUN_PYTHON %s > %t
# RUN: filecheck %s --input-file %t


from deltakit_compile.frontend.common._circuit import CircuitBuilder
from deltakit_compile.frontend.common._qubit_reg import QubitReg
from deltakit_compile.frontend.logasm import (
    LogAsmBuilder,
)
from deltakit_compile.frontend.logical_assembler import LogicalAssembler, LogicalAssemblerConfig
from deltakit_compile.passes.stim.stim_export.pipeline import (
    StimExportPipelineConfig,
)

builder = CircuitBuilder()
qreg = builder.add_arg(QubitReg(5))
builder.gate("RX", (qreg[1], qreg[3]))
builder.gate("CX", (qreg[0], qreg[1]))
builder.gate("CX", (qreg[3], qreg[1]))

builder.gate("CX", (qreg[3], qreg[2]))
builder.gate("CX", (qreg[3], qreg[4]))

m_reg = builder.measure("X", (qreg[1], qreg[3]))
builder.add_return(m_reg)
circuit = builder.build("silly_circuit")

lbuilder = LogAsmBuilder()
qreg = lbuilder.declare_patch(QubitReg(5))

round_1 = lbuilder.call_circuit(circuit(qreg))
round_2 = lbuilder.call_circuit(circuit(qreg))
round_3 = lbuilder.call_circuit(circuit(qreg))

logasm_program = lbuilder.build_program()


assembler = LogicalAssembler(
    LogicalAssemblerConfig(export_config=StimExportPipelineConfig(), verify_between_passes=True)
)
result = assembler.compile(logasm_program)
print(result.program)
# CHECK-NEXT:  RX 1 3
# CHECK-NEXT:  TICK
# CHECK-NEXT:  CNOT 0 1
# CHECK-NEXT:  TICK
# CHECK-NEXT:  CNOT 3 1
# CHECK-NEXT:  TICK
# CHECK-NEXT:  CNOT 3 2
# CHECK-NEXT:  TICK
# CHECK-NEXT:  CNOT 3 4
# CHECK-NEXT:  TICK
# CHECK-NEXT:  MX 1 3
# CHECK-NEXT:  TICK
# CHECK-NEXT:  DETECTOR rec[-2]
# CHECK-NEXT:  RX 1 3
# CHECK-NEXT:  TICK
# CHECK-NEXT:  CNOT 0 1
# CHECK-NEXT:  TICK
# CHECK-NEXT:  CNOT 3 1
# CHECK-NEXT:  TICK
# CHECK-NEXT:  CNOT 3 2
# CHECK-NEXT:  TICK
# CHECK-NEXT:  CNOT 3 4
# CHECK-NEXT:  TICK
# CHECK-NEXT:  MX 1 3
# CHECK-NEXT:  TICK
# CHECK-NEXT:  DETECTOR rec[-2]
# CHECK-NEXT:  DETECTOR rec[-3] rec[-1]
# CHECK-NEXT:  RX 1 3
# CHECK-NEXT:  TICK
# CHECK-NEXT:  CNOT 0 1
# CHECK-NEXT:  TICK
# CHECK-NEXT:  CNOT 3 1
# CHECK-NEXT:  TICK
# CHECK-NEXT:  CNOT 3 2
# CHECK-NEXT:  TICK
# CHECK-NEXT:  CNOT 3 4
# CHECK-NEXT:  TICK
# CHECK-NEXT:  MX 1 3
# CHECK-NEXT:  TICK
# CHECK-NEXT:  DETECTOR rec[-2]
# CHECK-NEXT:  DETECTOR rec[-3] rec[-1]
