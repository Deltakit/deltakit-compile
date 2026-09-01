// RUN: deltakit_compile compile-passes --test-mode %s -p merge-circuits -O %t && filecheck %s --input-file %t
// Test that the merge-circuits pass merges repeatedly until a fixed point.

builtin.module {
// CHECK: builtin.module {

    %state0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:    %state0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, [Z0]>

    %b0 = "test.op"() : () -> !test.type<"A">

    %state1, %n0, %b1 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, [Z0]>
                                            -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q0_b : !qcore.qubit), (%i0 = %b0 : !test.type<"A">) {
        %m0 = qref.measure<Z> (%q0_b) -> i1
        stab.yield [%m0 : i1] %m0, %i0 : i1, !test.type<"A">
      } [<-:0>{I -> Z0}, <+:>{Z0 -> I}]
    %state2, %n1, %b2 = stab.circuit %state1 : !stab.state<1 x !qcore.qubit, [Z0]>
                                            -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q1_b : !qcore.qubit), (%m3 = %n0 : i1, %i2 = %b1 : !test.type<"A">) {
        %m1 = qref.measure<Z> (%q1_b) -> i1
        stab.yield [%m1, %m3 : i1, i1] %m1, %i2 : i1, !test.type<"A">
      } [<+:>{I -> Z0}, <-:0,1>{Z0 -> I}]
    %state3, %n2, %b3 = stab.circuit %state2 : !stab.state<1 x !qcore.qubit, [Z0]>
                                            -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q2_b : !qcore.qubit), (%m4 = %n0 : i1, %m5 = %n1 : i1, %i3 = %b2 : !test.type<"A">) {
        %m2 = qref.measure<Z> (%q2_b) -> i1
        stab.yield [%m2, %m4, %m5 : i1, i1, i1] %m2, %i3 : i1, !test.type<"A">
      } [<+:1,2>{I -> Z0}, <-:0>{Z0 -> I}]
// CHECK:         %state3, %n0, %b1, %n1, %b2, %n2, %b3 = stab.circuit %state0
// CHECK-SAME:        : !stab.state<1 x !qcore.qubit, [Z0]> -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:      with (%q0_b : !qcore.qubit), (%i0 = %b0 : !test.type<"A">){
// CHECK-NEXT:        %m0 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:        %m1 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:        qec.detector(%m0, %m1, %m0)
// CHECK-NEXT:        %m2 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:        qec.detector(%m2)
// CHECK-NEXT:        stab.yield [%m0, %m1, %m0, %m2, %m0, %m1 : i1, i1, i1, i1, i1, i1]
// CHECK-SAME:          %m0, %i0, %m1, %i0, %m2, %i0 : i1, !test.type<"A">, i1, !test.type<"A">, i1, !test.type<"A">
// CHECK-NEXT:      } [<+:4, 5>{I -> Z0}, <+:>{Z0 -> I}]

}
// CHECK-NEXT: }
