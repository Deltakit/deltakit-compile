# RUN: RUN_PYTHON %s > %t
# RUN: filecheck %s --input-file %t


from deltakit_compile.frontend.circuit import Circuit, CircuitBuilder
from deltakit_compile.frontend.circuit_builder import CircuitProgramBuilder
from deltakit_compile.frontend.common import MeasurementBit, QubitReg


def build_circ() -> Circuit[[QubitReg], MeasurementBit]:
    circ_builder = CircuitBuilder()
    qubit_subset = circ_builder.add_arg(QubitReg(2))
    circ_builder.gate("X", qubit_subset)
    ro = circ_builder.measure("Z", qubit_subset[0])
    circ_builder.add_return(ro)
    return circ_builder.build("circ")


builder = CircuitProgramBuilder()
circ = build_circ()

qubits = builder.declare_qubits(QubitReg(4))
ro0 = builder.call_circuit(circ(qubits[:2]))
ro1 = builder.call_circuit(circ(qubits[2:]))
builder.add_return(ro0)
builder.add_return(ro1)

program = builder.build_program()
print(program)

# CHECK:       CircuitProgram({
# CHECK-NEXT:    %0 = qcore.alloc_qubit -> !qcore.qubit_reg<4>
# CHECK-NEXT:    %qreg = log_asm_api.cast(%0 : !qcore.qubit_reg<4>) -> tensor<4x!qcore.qubit>
# CHECK-NEXT:    %1, %2 = log_asm_api.tensor_slice(%qreg[:2:]) : tensor<4x!qcore.qubit> -> tensor<2x!qcore.qubit>, tensor<2x!qcore.qubit>
# CHECK-NEXT:    %b, %qreg_1 = log_asm_api.call @circ(%1) : (tensor<2x!qcore.qubit>) -> (i1, tensor<2x!qcore.qubit>)
# CHECK-NEXT:    %3 = log_asm_api.tensor_merge<[:2:]>(%qreg_1 : tensor<2x!qcore.qubit>, %2 : tensor<2x!qcore.qubit>) -> tensor<4x!qcore.qubit>
# CHECK-NEXT:    %4, %5 = log_asm_api.tensor_slice(%3[2::]) : tensor<4x!qcore.qubit> -> tensor<2x!qcore.qubit>, tensor<2x!qcore.qubit>
# CHECK-NEXT:    %b_1, %qreg_2 = log_asm_api.call @circ(%4) : (tensor<2x!qcore.qubit>) -> (i1, tensor<2x!qcore.qubit>)
# CHECK-NEXT:    %6 = log_asm_api.tensor_merge<[2::]>(%qreg_2 : tensor<2x!qcore.qubit>, %5 : tensor<2x!qcore.qubit>) -> tensor<4x!qcore.qubit>
# CHECK-NEXT:    qstruct.output(%b, %b_1 : i1, i1)
# CHECK-NEXT:    log_asm_api.circuit_dec @circ(%qreg_3: tensor<2x!qcore.qubit>) -> (i1, tensor<2x!qcore.qubit>) {
# CHECK-NEXT:      log_asm_api.unsized_gate<#qcore.gate.x> (%qreg_3 : tensor<2x!qcore.qubit>)
# CHECK-NEXT:      %7, %8 = log_asm_api.tensor_slice(%qreg_3[0:1:1]) : tensor<2x!qcore.qubit> -> tensor<1x!qcore.qubit>, tensor<1x!qcore.qubit>
# CHECK-NEXT:      %9 = arith.constant 0 : index
# CHECK-NEXT:      %10 = tensor.extract %7[%9] : tensor<1x!qcore.qubit>
# CHECK-NEXT:      %b_2 = qref.measure<Z> (%10) -> i1
# CHECK-NEXT:      log_asm_api.return %b_2, %qreg_3 : i1, tensor<2x!qcore.qubit>
# CHECK-NEXT:    }
# CHECK-NEXT:  })
