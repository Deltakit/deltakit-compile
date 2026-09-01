// RUN: ROUNDTRIP_MLIR

builtin.module {
// CHECK: builtin.module {

    // Declare circuits with different numbers of qubits.
    log_asm_api.circuit_dec @no_qubit() {
        log_asm_api.return
    }
    log_asm_api.circuit_dec @one_qubit(%q0_f: !qcore.qubit) -> !qcore.qubit {
        log_asm_api.return %q0_f : !qcore.qubit
    }
    log_asm_api.circuit_dec @three_qubits(%q0 : !qcore.qubit, %q1: !qcore.qubit, %q2: !qcore.qubit) -> (!qcore.qubit, !qcore.qubit, !qcore.qubit) {
        log_asm_api.return %q0, %q1, %q2 : !qcore.qubit, !qcore.qubit, !qcore.qubit
    }
    log_asm_api.circuit_dec @qubit_registers(%q0: !qcore.qubit_reg<3>) -> !qcore.qubit_reg<3> {
        log_asm_api.return %q0 : !qcore.qubit_reg<3>
    }

    // Test with non-qubit arguments.
    log_asm_api.circuit_dec @with_i1(%q0: !qcore.qubit, %m0: i1) -> !qcore.qubit {
        log_asm_api.return %q0 : !qcore.qubit
    }

    // Test with unsized qubit argument
    log_asm_api.circuit_dec @unsized_register(%qubits: tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
        log_asm_api.return %qubits : tensor<?x!qcore.qubit>
    }
// CHECK-NEXT:    log_asm_api.circuit_dec @no_qubit() {
// CHECK-NEXT:        log_asm_api.return
// CHECK-NEXT:    }
// CHECK-NEXT:    log_asm_api.circuit_dec @one_qubit(%q0_f: !qcore.qubit) -> !qcore.qubit {
// CHECK-NEXT:        log_asm_api.return %q0_f : !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:    log_asm_api.circuit_dec @three_qubits(%q0: !qcore.qubit, %q1: !qcore.qubit, %q2: !qcore.qubit) -> (!qcore.qubit, !qcore.qubit, !qcore.qubit) {
// CHECK-NEXT:        log_asm_api.return %q0, %q1, %q2 : !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:    log_asm_api.circuit_dec @qubit_registers(%q0: !qcore.qubit_reg<3>) -> !qcore.qubit_reg<3> {
// CHECK-NEXT:        log_asm_api.return %q0 : !qcore.qubit_reg<3>
// CHECK-NEXT:    }
// CHECK-NEXT:    log_asm_api.circuit_dec @with_i1(%q0: !qcore.qubit, %m0: i1) -> !qcore.qubit {
// CHECK-NEXT:        log_asm_api.return %q0 : !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:    log_asm_api.circuit_dec @unsized_register(%qubits: tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
// CHECK-NEXT:        log_asm_api.return %qubits : tensor<?x!qcore.qubit>
// CHECK-NEXT:    }

    // Calling a reset
    log_asm_api.circuit_dec @unsized_reset(%qubits: tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
        log_asm_api.unsized_reset<X>(%qubits : tensor<?x!qcore.qubit>)
        log_asm_api.return %qubits : tensor<?x!qcore.qubit>
    }
// CHECK-NEXT:    log_asm_api.circuit_dec @unsized_reset(%qubits: tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
// CHECK-NEXT:        log_asm_api.unsized_reset<X> (%qubits : tensor<?x!qcore.qubit>)
// CHECK-NEXT:        log_asm_api.return %qubits : tensor<?x!qcore.qubit>
// CHECK-NEXT:    }

    // Calling a gate
    log_asm_api.circuit_dec @unsized_gate(%qubits: tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
        log_asm_api.unsized_gate<#qcore.gate.x>(%qubits : tensor<?x!qcore.qubit>)
        log_asm_api.unsized_gate<#qcore.gate.x<sqrt, dag>>(%qubits : tensor<?x!qcore.qubit>)
        log_asm_api.unsized_gate<#qcore.gate.y>(%qubits : tensor<?x!qcore.qubit>)
        log_asm_api.unsized_gate<#qcore.gate.z>(%qubits : tensor<?x!qcore.qubit>)
        log_asm_api.unsized_gate<#qcore.gate.unitary<[[(0.0, 0.0), (1.0, 0.0)],
                                                      [(1.0, 0.0), (0.0, 0.0)]]>>(%qubits : tensor<?x!qcore.qubit>)
        log_asm_api.return %qubits : tensor<?x!qcore.qubit>
    }
// CHECK-NEXT:    log_asm_api.circuit_dec @unsized_gate(%qubits: tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
// CHECK-NEXT:        log_asm_api.unsized_gate<#qcore.gate.x> (%qubits : tensor<?x!qcore.qubit>)
// CHECK-NEXT:        log_asm_api.unsized_gate<#qcore.gate.x<sqrt, dag>> (%qubits : tensor<?x!qcore.qubit>)
// CHECK-NEXT:        log_asm_api.unsized_gate<#qcore.gate.y> (%qubits : tensor<?x!qcore.qubit>)
// CHECK-NEXT:        log_asm_api.unsized_gate<#qcore.gate.z> (%qubits : tensor<?x!qcore.qubit>)
// CHECK-NEXT:        log_asm_api.unsized_gate<#qcore.gate.unitary<[[(0.0, 0.0), (1.0, 0.0)],
// CHECK-SAME:                                                      [(1.0, 0.0), (0.0, 0.0)]]>> (%qubits : tensor<?x!qcore.qubit>)
// CHECK-NEXT:        log_asm_api.return %qubits : tensor<?x!qcore.qubit>
// CHECK-NEXT:    }

    // Examples of calling circuits
    %p0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3)>
    %qreg0 = log_asm_api.cast(%p0 : !log_asm.patch.rot_planar<size=(3, 3)>) -> tensor<?x!qcore.qubit>
    %ci0 = arith.constant 0 : index
    %qubit0 = tensor.extract %qreg0[%ci0] : tensor<?x!qcore.qubit>
    %qubit1 = log_asm_api.call @one_qubit(%qubit0) : (!qcore.qubit) -> !qcore.qubit

// CHECK-NEXT:    %p0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3)>
// CHECK-NEXT:    %qreg0 = log_asm_api.cast(%p0 : !log_asm.patch.rot_planar<size=(3, 3)>) -> tensor<?x!qcore.qubit>
// CHECK-NEXT:    %ci0 = arith.constant 0 : index
// CHECK-NEXT:    %qubit0 = tensor.extract %qreg0[%ci0] : tensor<?x!qcore.qubit>
// CHECK-NEXT:    %qubit1 = log_asm_api.call @one_qubit(%qubit0) : (!qcore.qubit) -> !qcore.qubit

    // Examples of cast operations
    log_asm_api.circuit_dec @casting_from_to_tensor(%qubits: tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
        %c0 = arith.constant 0 : index
        %q0 = tensor.extract %qubits[%c0] : tensor<?x!qcore.qubit>
        %m0 = qref.measure<Z>(%q0) -> i1
        %rec_single = tensor.from_elements %m0 : tensor<1xi1>
        %rec_unsized = log_asm_api.cast(%rec_single : tensor<1xi1>) -> tensor<?xi1>
        log_asm_api.return %qubits : tensor<?x!qcore.qubit>
    }

    log_asm_api.circuit_dec @casting_same_size_types(%qubits: tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
        %tensor17 = log_asm_api.cast(%qubits : tensor<?x!qcore.qubit>) -> tensor<17x!qcore.qubit>
        %qreg = log_asm_api.cast(%tensor17 : tensor<17x!qcore.qubit>) -> !qcore.qubit_reg<17>
        %patch3x3 = log_asm_api.cast(%qreg : !qcore.qubit_reg<17>) -> !log_asm.patch.rot_planar<size=(3, 3)>
        %unsized_tensor = log_asm_api.cast(%patch3x3 : !log_asm.patch.rot_planar<size=(3, 3)>) -> tensor<?x!qcore.qubit>
        log_asm_api.return %unsized_tensor : tensor<?x!qcore.qubit>
    }
// CHECK-NEXT:    log_asm_api.circuit_dec @casting_from_to_tensor(%qubits: tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
// CHECK-NEXT:        %c0 = arith.constant 0 : index
// CHECK-NEXT:        %q0 = tensor.extract %qubits[%c0] : tensor<?x!qcore.qubit>
// CHECK-NEXT:        %m0 = qref.measure<Z> (%q0) -> i1
// CHECK-NEXT:        %rec_single = tensor.from_elements %m0 : tensor<1xi1>
// CHECK-NEXT:        %rec_unsized = log_asm_api.cast(%rec_single : tensor<1xi1>) -> tensor<?xi1>
// CHECK-NEXT:        log_asm_api.return %qubits : tensor<?x!qcore.qubit>
// CHECK-NEXT:    }
// CHECK-NEXT:    log_asm_api.circuit_dec @casting_same_size_types(%qubits: tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
// CHECK-NEXT:        %tensor17 = log_asm_api.cast(%qubits : tensor<?x!qcore.qubit>) -> tensor<17x!qcore.qubit>
// CHECK-NEXT:        %qreg = log_asm_api.cast(%tensor17 : tensor<17x!qcore.qubit>) -> !qcore.qubit_reg<17>
// CHECK-NEXT:        %patch3x3 = log_asm_api.cast(%qreg : !qcore.qubit_reg<17>) -> !log_asm.patch.rot_planar<size=(3, 3)>
// CHECK-NEXT:        %unsized_tensor = log_asm_api.cast(%patch3x3 : !log_asm.patch.rot_planar<size=(3, 3)>) -> tensor<?x!qcore.qubit>
// CHECK-NEXT:        log_asm_api.return %unsized_tensor : tensor<?x!qcore.qubit>
// CHECK-NEXT:    }

    %qubit_tensor = "test.op"() : () -> tensor<?x!qcore.qubit>
    %t0, %l0 = log_asm_api.tensor_slice(%qubit_tensor[1:2:3]) : tensor<?x!qcore.qubit> -> tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>
    %t1, %l1 = log_asm_api.tensor_slice(%qubit_tensor[::]) : tensor<?x!qcore.qubit> -> tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>
    %t2, %l2 = log_asm_api.tensor_slice(%qubit_tensor[-1:-2:-3]) : tensor<?x!qcore.qubit> -> tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>
    %t3, %l3 = log_asm_api.tensor_slice(%qubit_tensor[3::1]) : tensor<?x!qcore.qubit> -> tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>
    %t4, %l4 = log_asm_api.tensor_slice(%qubit_tensor[:1:1]) : tensor<?x!qcore.qubit> -> tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>
    %t5, %l5 = log_asm_api.tensor_slice(%qubit_tensor[:1:]) {name = "value"} : tensor<?x!qcore.qubit> -> tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>

// CHECK-NEXT:    %qubit_tensor = "test.op"() : () -> tensor<?x!qcore.qubit>
// CHECK-NEXT:    %t0, %l0 = log_asm_api.tensor_slice(%qubit_tensor[1:2:3]) : tensor<?x!qcore.qubit> -> tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>
// CHECK-NEXT:    %t1, %l1 = log_asm_api.tensor_slice(%qubit_tensor[::]) : tensor<?x!qcore.qubit> -> tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>
// CHECK-NEXT:    %t2, %l2 = log_asm_api.tensor_slice(%qubit_tensor[-1:-2:-3]) : tensor<?x!qcore.qubit> -> tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>
// CHECK-NEXT:    %t3, %l3 = log_asm_api.tensor_slice(%qubit_tensor[3::1]) : tensor<?x!qcore.qubit> -> tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>
// CHECK-NEXT:    %t4, %l4 = log_asm_api.tensor_slice(%qubit_tensor[:1:1]) : tensor<?x!qcore.qubit> -> tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>
// CHECK-NEXT:    %t5, %l5 = log_asm_api.tensor_slice(%qubit_tensor[:1:]) {name = "value"} : tensor<?x!qcore.qubit> -> tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>

    %sliced, %leftovers = "test.op"() : () -> (tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>)

    %merged0 = log_asm_api.tensor_merge<[1:2:3]>(%sliced : tensor<?x!qcore.qubit>, %leftovers : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
    %merged1 = log_asm_api.tensor_merge<[::]>(%sliced : tensor<?x!qcore.qubit>, %leftovers : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
    %merged2 = log_asm_api.tensor_merge<[-1:-2:-3]>(%sliced : tensor<?x!qcore.qubit>, %leftovers : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
    %merged3 = log_asm_api.tensor_merge<[3::1]>(%sliced : tensor<?x!qcore.qubit>, %leftovers : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
    %merged4 = log_asm_api.tensor_merge<[:1:1]>(%sliced : tensor<?x!qcore.qubit>, %leftovers : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
    %merged5 = log_asm_api.tensor_merge<[:1:]>(%sliced : tensor<?x!qcore.qubit>, %leftovers : tensor<?x!qcore.qubit>) {name = "value"} -> tensor<?x!qcore.qubit>

// CHECK-NEXT:    %sliced, %leftovers = "test.op"() : () -> (tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>)
// CHECK-NEXT:    %merged0 = log_asm_api.tensor_merge<[1:2:3]>(%sliced : tensor<?x!qcore.qubit>, %leftovers : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
// CHECK-NEXT:    %merged1 = log_asm_api.tensor_merge<[::]>(%sliced : tensor<?x!qcore.qubit>, %leftovers : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
// CHECK-NEXT:    %merged2 = log_asm_api.tensor_merge<[-1:-2:-3]>(%sliced : tensor<?x!qcore.qubit>, %leftovers : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
// CHECK-NEXT:    %merged3 = log_asm_api.tensor_merge<[3::1]>(%sliced : tensor<?x!qcore.qubit>, %leftovers : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
// CHECK-NEXT:    %merged4 = log_asm_api.tensor_merge<[:1:1]>(%sliced : tensor<?x!qcore.qubit>, %leftovers : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
// CHECK-NEXT:    %merged5 = log_asm_api.tensor_merge<[:1:]>(%sliced : tensor<?x!qcore.qubit>, %leftovers : tensor<?x!qcore.qubit>) {name = "value"} -> tensor<?x!qcore.qubit>
}
// CHECK-NEXT: }
