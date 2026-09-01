// RUN: deltakit_compile compile-passes --test-mode %s -p merge-circuits -O %t && filecheck %s --input-file %t
// Test that detectors in the span of existing detectors are not added when merging.

builtin.module {
// CHECK: builtin.module {

    %state0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT: %state0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>

    %state1, %n0 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
                                       -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q0_b : !qcore.qubit), () {
        %m0 = qref.measure<Z> (%q0_b) -> i1
        stab.yield [%m0 : i1] %m0 : i1
      } [<+:0>{I -> Z0}]
    %state2 = stab.circuit %state1 : !stab.state<1 x !qcore.qubit, [Z0]>
                                  -> !stab.state<1 x !qcore.qubit, []>
      with (%q1_b : !qcore.qubit), (%m1 = %n0 : i1) {
        %m2 = qref.measure<Z> (%q1_b) -> i1
        %m3 = qref.measure<Z> (%q1_b) -> i1
        qec.detector(%m1, %m3)
        qec.detector(%m2, %m3)
        stab.yield [%m2 : i1]
      } [<+:0>{Z0 -> I}]
// CHECK-NEXT: %state2, %n0 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                    -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:   with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:     %m0 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:     %m2 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:     %m3 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:     qec.detector(%m0, %m3)
// CHECK-NEXT:     qec.detector(%m2, %m3)
// CHECK-NEXT:     stab.yield [%m0, %m2 : i1, i1] %m0 : i1
// CHECK-NEXT:   } []

    // Also including detectors in the first circuit
    %state3 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
                                  -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q2_b : !qcore.qubit), () {
        %m4 = qref.measure<Z> (%q2_b) -> i1
        %m5 = qref.measure<Z> (%q2_b) -> i1
        qec.detector(%m4, %m5)
        stab.yield [%m4, %m5 : i1, i1]
      } [<+:0, 1>{I -> Z0}]
    %state4 = stab.circuit %state3 : !stab.state<1 x !qcore.qubit, [Z0]>
                                  -> !stab.state<1 x !qcore.qubit, []>
      with (%q3_b : !qcore.qubit), () {
        stab.yield []
      } [<+:>{Z0 -> I}]
// CHECK-NEXT: %state4 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                               -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:   with (%q2_b : !qcore.qubit), (){
// CHECK-NEXT:     %m4 = qref.measure<Z> (%q2_b) -> i1
// CHECK-NEXT:     %m5 = qref.measure<Z> (%q2_b) -> i1
// CHECK-NEXT:     qec.detector(%m4, %m5)
// CHECK-NEXT:     stab.yield [%m4, %m5 : i1, i1]
// CHECK-NEXT:   } []

}
// CHECK-NEXT: }
