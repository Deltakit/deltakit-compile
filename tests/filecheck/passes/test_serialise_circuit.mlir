// RUN: deltakit_compile compile-passes %s -p serialise-circuit -O %t && filecheck %s --input-file %t

builtin.module {
    %q = stim.qubit_alloc 0 -> !stim.qubit
    %q_1 = stim.qubit_alloc 1 -> !stim.qubit
    %q_2 = stim.qubit_alloc 2 -> !stim.qubit

    %rec_g, %rec_1g, %rec_2g = qstruct.parallel<BOTTOM> -> i1, i1, i1 {
        stim.clifford X (%q)
        %rec = stim.measure Z (%q) -> i1
        qstruct.yield %rec : i1
    } {
        stim.clifford X (%q_1)
        stim.clifford X (%q_2)
        %rec_1, %rec_2 = stim.measure Z (%q_1, %q_2) -> i1, i1
        qstruct.yield %rec_1, %rec_2 : i1, i1
    }
    stim.detector (%rec_g, %rec_1g : i1, i1)
}

// CHECK:       builtin.module {
// CHECK-NEXT:    %q = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:    %q_1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:    %q_2 = stim.qubit_alloc 2 -> !stim.qubit
// CHECK-NEXT:    stim.clifford X (%q)
// CHECK-NEXT:    %rec = stim.measure Z (%q) -> i1
// CHECK-NEXT:    stim.clifford X (%q_1)
// CHECK-NEXT:    stim.clifford X (%q_2)
// CHECK-NEXT:    %rec_1, %rec_2 = stim.measure Z (%q_1, %q_2) -> i1, i1
// CHECK-NEXT:    stim.detector (%rec, %rec_1 : i1, i1)
// CHECK-NEXT:  }
