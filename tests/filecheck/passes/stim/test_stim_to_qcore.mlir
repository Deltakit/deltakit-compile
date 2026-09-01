// RUN: deltakit_compile compile-passes %s -p stim-to-qcore -O %t && filecheck %s --input-file %t

builtin.module {
  %q0 = stim.qubit_alloc 0 {stim.tag = "a"} -> !stim.qubit
  %q1 = stim.qubit_alloc 1 {stim.tag = "b"} -> !stim.qubit
  %q2 = stim.qubit_alloc 2 -> !stim.qubit

  stim.assign_qubit_coord <4.0, 0.0> (%q0 : !stim.qubit)
  stim.assign_qubit_coord <0.0, 10> (%q2 : !stim.qubit)

  %0, %1, %2 = stim.measure Z (%q0, %q1, %q2) -> i1, i1, i1
  stim.assign_qubit_coord <5.0, 10> (%q0 : !stim.qubit)
}

//CHECK:        builtin.module {
//CHECK-NEXT:     %q0 = qcore.alloc_qubit<coords = [(4.0, 0.0, 5.0, 10.0)], ids = [0]> {stim.tag = "a"} -> !qcore.qubit
//CHECK-NEXT:     %q0_1 = builtin.unrealized_conversion_cast %q0 : !qcore.qubit to !stim.qubit
//CHECK-NEXT:     %q1 = qcore.alloc_qubit<ids = [1]> {stim.tag = "b"} -> !qcore.qubit
//CHECK-NEXT:     %q1_1 = builtin.unrealized_conversion_cast %q1 : !qcore.qubit to !stim.qubit
//CHECK-NEXT:     %q2 = qcore.alloc_qubit<coords = [(0.0, 10.0)], ids = [2]> -> !qcore.qubit
//CHECK-NEXT:     %q2_1 = builtin.unrealized_conversion_cast %q2 : !qcore.qubit to !stim.qubit
//CHECK-NEXT:     %0, %1, %2 = stim.measure Z (%q0_1, %q1_1, %q2_1) -> i1, i1, i1
//CHECK-NEXT:   }
