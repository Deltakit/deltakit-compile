// RUN: deltakit_compile compile-passes %s -p remap-qubits --pass-args '{"qubit_coord_offset": [0.5, -2.0], "qubit_mapping": {"5": [0.5, 8.0], "6": [4.5, -2.0]}}' -O %t && filecheck %s --input-file %t

builtin.module {
    %0 = stim.qubit_alloc 0 -> !stim.qubit
    %1 = stim.qubit_alloc 1 -> !stim.qubit
    stim.assign_qubit_coord <4.0, 0.0> (%0 : !stim.qubit)
    stim.assign_qubit_coord <0.0, 10> (%1 : !stim.qubit)
}

// CHECK:       builtin.module {
// CHECK-NEXT:    %0 = stim.qubit_alloc 6 -> !stim.qubit
// CHECK-NEXT:    %1 = stim.qubit_alloc 5 -> !stim.qubit
// CHECK-NEXT:    stim.assign_qubit_coord <4.5, -2.0> (%0 : !stim.qubit)
// CHECK-NEXT:    stim.assign_qubit_coord <0.5, 8.0> (%1 : !stim.qubit)
// CHECK-NEXT:  }
