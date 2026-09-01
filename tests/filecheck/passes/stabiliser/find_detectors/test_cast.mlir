// RUN: deltakit_compile compile-passes %s -p find-detectors -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK: builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %q1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT: %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT: %q1 = qcore.alloc_qubit -> !qcore.qubit

    %state0 = stab.state.make (%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT: %state0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>

    %state1 = stab.state.cast(%state0) !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT: %state1 = stab.state.cast(%state0) !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, []>

    %state2 = stab.circuit %state1 : !stab.state<2 x !qcore.qubit, []>
                                  -> !stab.state<2 x !qcore.qubit, [X0 Z1, Z0 X1]>
      with (%q0_b, %q1_b : !qcore.qubit), () {
        %m0 = qref.measure<X> (%q0_b) -> i1
        %m1 = qref.measure<Z> (%q1_b) -> i1
        stab.yield [%m0, %m1 : i1, i1]
      } [<+:0>{I -> X0 Z1}, <+:1>{I -> Z0 X1}]
// CHECK-NEXT: %state2, [[OUT1:%[0-9]+]], [[OUT2:%[0-9]+]] = stab.circuit %state1 : !stab.state<2 x !qcore.qubit, []>
// CHECK-SAME:                                -> !stab.state<2 x !qcore.qubit, [X0 Z1, Z0 X1]>
// CHECK-NEXT:    with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:      %m0 = qref.measure<X> (%q0_b) -> i1
// CHECK-NEXT:      %m1 = qref.measure<Z> (%q1_b) -> i1
// CHECK-NEXT:      stab.yield [%m0, %m1 : i1, i1] %m0, %m1 : i1, i1
// CHECK-NEXT:    } [<+:0>{I -> X0 Z1}, <+:1>{I -> Z0 X1}]

    %state3 = stab.state.cast(%state2) !stab.state<2 x !qcore.qubit, [X0 Z1, Z0 X1]> -> !stab.state<2 x !qcore.qubit, [X0 Z1, Z0 X1]>
// CHECK-NEXT: %state3 = stab.state.cast(%state2) !stab.state<2 x !qcore.qubit, [X0 Z1, Z0 X1]> -> !stab.state<2 x !qcore.qubit, [X0 Z1, Z0 X1]>

    %state4 = stab.state.cast(%state3) !stab.state<2 x !qcore.qubit, [X0 Z1, Z0 X1]> -> !stab.state<2 x !qcore.qubit, [X0 Z1]>
// CHECK-NEXT: %state4 = stab.state.cast(%state3) !stab.state<2 x !qcore.qubit, [X0 Z1, Z0 X1]> -> !stab.state<2 x !qcore.qubit, [X0 Z1]>

    %state5 = stab.circuit %state4 : !stab.state<2 x !qcore.qubit, [X0 Z1]>
                                  -> !stab.state<2 x !qcore.qubit, []>
      with (%q0_b, %q1_b : !qcore.qubit), () {
        %m2 = qref.measure<X> (%q0_b) -> i1
        stab.yield [%m2 : i1]
      } [<+:0>{X0 Z1 -> I}]
// CHECK-NEXT: %state5 = stab.circuit %state4 : !stab.state<2 x !qcore.qubit, [X0 Z1]>
// CHECK-SAME:                               -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:    with (%q0_b, %q1_b : !qcore.qubit), ([[IN1:%[0-9]+]] = [[OUT1]] : i1){
// CHECK-NEXT:      %m2 = qref.measure<X> (%q0_b) -> i1
// CHECK-NEXT:      qec.detector([[IN1]], %m2)
// CHECK-NEXT:      stab.yield [%m2 : i1]
// CHECK-NEXT:    } [<+:0>{X0 Z1 -> I}]
}
// CHECK-NEXT: }
