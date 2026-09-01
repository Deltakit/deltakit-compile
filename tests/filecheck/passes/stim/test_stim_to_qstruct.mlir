// RUN: deltakit_compile compile-passes -t %s -p stim-to-qstruct -O %t && filecheck %s --input-file %t

builtin.module {

// CHECK:         builtin.module {

  %q0 = qcore.alloc_qubit<coords=[(4.0, 0.0)], ids=[0]> -> !qcore.qubit
  %q1 = qcore.alloc_qubit<ids=[1]> -> !qcore.qubit
  %q2 = qcore.alloc_qubit<coords=[(0.0, 10.0)], ids=[2]> -> !qcore.qubit

// CHECK-NEXT:      %q0 = qcore.alloc_qubit<coords = [(4.0, 0.0)], ids = [0]> -> !qcore.qubit
// CHECK-NEXT:      %q1 = qcore.alloc_qubit<ids = [1]> -> !qcore.qubit
// CHECK-NEXT:      %q2 = qcore.alloc_qubit<coords = [(0.0, 10.0)], ids = [2]> -> !qcore.qubit

  %q0_1 = builtin.unrealized_conversion_cast %q0 : !qcore.qubit to !stim.qubit
  %q1_1 = builtin.unrealized_conversion_cast %q1 : !qcore.qubit to !stim.qubit
  %q2_1 = builtin.unrealized_conversion_cast %q2 : !qcore.qubit to !stim.qubit

  stim.clifford X (%q0_1)
  %e = stim.empty -> i1
  %r0, %r1, %r2, %r3, %r4, %r5 = stim.repeat {stim.tag = "23"} 5 (%e, %e, %e, %e, %e, %e : i1, i1, i1, i1, i1, i1) -> i1, i1, i1, i1, i1, i1 {
    ^bb1(%v0: i1, %v1: i1, %v2: i1, %v3: i1, %v4: i1, %v5: i1):
      stim.clifford CZ (%q0_1, %q1_1)
      %m0, %m1 = stim.measure Z (%q0_1, %q1_1) -> i1, i1
      "test.op"(%q0_1, %q2_1) : (!stim.qubit, !stim.qubit) -> ()
      stim.yield %v2, %v3, %v4, %v5, %m0, %m1 : i1, i1, i1, i1, i1, i1
  }

// CHECK-NEXT:      %0, %1, %2 = qstruct.circuit(%q0, %q1, %q2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:      ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit, %q2_1: !qcore.qubit):
// CHECK-NEXT:        %q0_2 = builtin.unrealized_conversion_cast %q0_1 : !qcore.qubit to !stim.qubit
// CHECK-NEXT:        %q1_2 = builtin.unrealized_conversion_cast %q1_1 : !qcore.qubit to !stim.qubit
// CHECK-NEXT:        %q2_2 = builtin.unrealized_conversion_cast %q2_1 : !qcore.qubit to !stim.qubit
// CHECK-NEXT:        stim.clifford X (%q0_2)
// CHECK-NEXT:        %e = arith.constant false
// CHECK-NEXT:        %r0, %r1, %r2, %r3, %r4, %r5 = qstruct.repeat<5> (%e, %e, %e, %e, %e, %e : i1, i1, i1, i1, i1, i1) {stim.tag = "23"} -> i1, i1, i1, i1, i1, i1 {
// CHECK-NEXT:        ^bb1(%v0: i1, %v1: i1, %v2: i1, %v3: i1, %v4: i1, %v5: i1):
// CHECK-NEXT:          stim.clifford CZ (%q0_2, %q1_2)
// CHECK-NEXT:          %m0, %m1 = stim.measure Z (%q0_2, %q1_2) -> i1, i1
// CHECK-NEXT:          "test.op"(%q0_2, %q2_2) : (!stim.qubit, !stim.qubit) -> ()
// CHECK-NEXT:          qstruct.yield %v2, %v3, %v4, %v5, %m0, %m1 : i1, i1, i1, i1, i1, i1
// CHECK-NEXT:        }
// CHECK-NEXT:        qstruct.yield %q0_1, %q1_1, %q2_1 : !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      }

}

// CHECK-NEXT:    }
