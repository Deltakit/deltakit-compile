// RUN: deltakit_compile compile-passes --test-mode %s -p merge-circuits -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK: builtin.module {

    %state0 = "test.op"() : () -> !stab.state<3 x !qcore.qubit, [X0 X1, Z2]>
// CHECK-NEXT:    %state0 = "test.op"() : () -> !stab.state<3 x !qcore.qubit, [X0 X1, Z2]>

    %state1 = stab.circuit %state0 : !stab.state<3 x !qcore.qubit, [X0 X1, Z2]>
                                  -> !stab.state<3 x !qcore.qubit, [Z0, Z1, X2]>
      with (%q0_b, %q1_b, %q2_b : !qcore.qubit), () {
        %m0 = qref.measure<Z> (%q0_b) -> i1
        %m1 = qref.measure<Z> (%q1_b) -> i1
        %m2 = qref.measure<Z> (%q2_b) -> i1
        stab.yield [%m0, %m1, %m2 : i1, i1, i1]
      } [<-:>{I -> Z0}, <-:0,2>{I -> X2}, <+:1,2>{X0 X1 -> Z1}, <+:0>{Z2 -> I}]
    %state2 = stab.circuit %state1 : !stab.state<3 x !qcore.qubit, [Z0, Z1, X2]>
                                  -> !stab.state<3 x !qcore.qubit, [Z0 Z1, X2]>
      with (%q3_b, %q4_b, %q5_b : !qcore.qubit), () {
        %m3 = qref.measure<Z> (%q3_b) -> i1
        %m4 = qref.measure<Z> (%q4_b) -> i1
        stab.yield [%m3, %m4 : i1, i1]
      } [<-:0>{I -> X2}, <-:0,1>{Z0 -> I}, <-:1>{Z1 -> Z0 Z1}, <+:1>{X2 -> I}]
// CHECK-NEXT:    %state2 = stab.circuit %state0 : !stab.state<3 x !qcore.qubit, [X0 X1, Z2]>
// CHECK-SAME:                                  -> !stab.state<3 x !qcore.qubit, [Z0 Z1, X2]>
// CHECK-NEXT:      with (%q0_b, %q1_b, %q2_b : !qcore.qubit), (){
// CHECK-NEXT:        %m0 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:        %m1 = qref.measure<Z> (%q1_b) -> i1
// CHECK-NEXT:        %m2 = qref.measure<Z> (%q2_b) -> i1
// CHECK-NEXT:        %m3 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:        %m4 = qref.measure<Z> (%q1_b) -> i1
// CHECK-DAG:         qec.detector(%m0, %m2, %m4)
// CHECK-DAG:         qec.detector(%m3, %m4)
// CHECK-NEXT:        stab.yield [%m0, %m1, %m2, %m3, %m4 : i1, i1, i1, i1, i1]
// CHECK-NEXT:      } [<-:3>{I -> X2}, <-:1, 2, 4>{X0 X1 -> Z0 Z1}, <+:0>{Z2 -> I}]

}
// CHECK-NEXT: }
