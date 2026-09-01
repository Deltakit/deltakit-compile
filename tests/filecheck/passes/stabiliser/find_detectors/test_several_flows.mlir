// RUN: deltakit_compile compile-passes %s -p find-detectors -O %t && filecheck %s --input-file %t
// COM: note the flows in this file are not internally correct but this doesn't matter for this transform

builtin.module {
// CHECK: builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %q1 = qcore.alloc_qubit -> !qcore.qubit

    %state0 = stab.state.make (%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK:      %state0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>

    %state1 = stab.circuit %state0 : !stab.state<2 x !qcore.qubit, []>
                                  -> !stab.state<2 x !qcore.qubit, [X0 X1, X0]>
      with (%q0_b, %q1_b : !qcore.qubit), () {
        %m0 = qref.measure<Z> (%q0_b) -> i1
        %m1 = qref.measure<Z> (%q1_b) -> i1
        stab.yield [%m0, %m1 : i1, i1]
      } [<+:0, 1>{I -> X0 X1}, <+:0>{I -> X0}]
// CHECK:      %state1, [[OUT1_1:%[0-9]+]], [[OUT1_2:%[0-9]+]], [[OUT1_3:%[0-9]+]] =
// CHECK-SAME:        stab.circuit %state0 : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [X0 X1, X0]>
// CHECK-NEXT:   with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:     %m0 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:     %m1 = qref.measure<Z> (%q1_b) -> i1
// CHECK-NEXT:     stab.yield [%m0, %m1 : i1, i1] %m0, %m1, %m0 : i1, i1, i1
// CHECK-NEXT:   } [<+:0, 1>{I -> X0 X1}, <+:0>{I -> X0}]

    %state2 = stab.circuit %state1 : !stab.state<2 x !qcore.qubit, [X0 X1, X0]>
                                  -> !stab.state<2 x !qcore.qubit, [Z0 X1, Z0]>
      with (%q0_b, %q1_b : !qcore.qubit), () {
        qref.gate<#qcore.gate.h> (%q0_b)
        %m3 = qref.measure<X> (%q1_b) -> i1
        stab.yield [%m3 : i1]
      } [<+:0>{X0 X1 -> Z0 X1}, <+:>{X0 -> Z0}]
// CHECK:      %state2, [[OUT2_1:%[0-9]+]], [[OUT2_2:%[0-9]+]], [[OUT2_3:%[0-9]+]], [[OUT2_4:%[0-9]+]] =
// CHECK-SAME:        stab.circuit %state1 : !stab.state<2 x !qcore.qubit, [X0 X1, X0]> -> !stab.state<2 x !qcore.qubit, [Z0 X1, Z0]>
// CHECK-NEXT:   with (%q0_b, %q1_b : !qcore.qubit), ([[IN1_1:%[0-9]+]] = [[OUT1_1]] : i1,
// CHECK-SAME:         [[IN1_2:%[0-9]+]] = [[OUT1_2]] : i1, [[IN1_3:%[0-9]+]] = [[OUT1_3]] : i1){
// CHECK-NEXT:     qref.gate<#qcore.gate.h> (%q0_b)
// CHECK-NEXT:     %m3 = qref.measure<X> (%q1_b) -> i1
// CHECK-NEXT:     stab.yield [%m3 : i1] [[IN1_1]], [[IN1_2]], %m3, [[IN1_3]] : i1, i1, i1, i1
// CHECK-NEXT:   } [<+:0>{X0 X1 -> Z0 X1}, <+:>{X0 -> Z0}]

    %state3 = stab.circuit %state2 : !stab.state<2 x !qcore.qubit, [Z0 X1, Z0]>
                                  -> !stab.state<2 x !qcore.qubit, [X0]>
      with (%q0_b, %q1_b : !qcore.qubit), () {
        %m4 = qref.measure<Z> (%q0_b) -> i1
        %m5 = qref.measure<Z> (%q1_b) -> i1
        %m6 = qref.measure<X> (%q0_b) -> i1
        stab.yield [%m4, %m6 : i1, i1]
      } [<+:1>{I -> X0}, <+:>{Z0 X1 -> I}, <+:0>{Z0 -> I}]
// CHECK:      %state3, [[OUT3:%[0-9]+]] = stab.circuit %state2 : !stab.state<2 x !qcore.qubit, [Z0 X1, Z0]>
// CHECK-SAME:                                                 -> !stab.state<2 x !qcore.qubit, [X0]>
// CHECK-NEXT:   with (%q0_b, %q1_b : !qcore.qubit), ([[IN2_1:%[0-9]+]] = [[OUT2_1]] : i1,
// CHECK-SAME:         [[IN2_2:%[0-9]+]] = [[OUT2_2]] : i1, [[IN2_3:%[0-9]+]] = [[OUT2_3]] : i1, [[IN2_4:%[0-9]+]] = [[OUT2_4]] : i1){
// CHECK-NEXT:     %m4 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:     %m5 = qref.measure<Z> (%q1_b) -> i1
// CHECK-NEXT:     %m6 = qref.measure<X> (%q0_b) -> i1
// CHECK-NEXT:     qec.detector([[IN2_1]], [[IN2_2]], [[IN2_3]])
// CHECK-NEXT:     qec.detector([[IN2_4]], %m4)
// CHECK-NEXT:     stab.yield [%m4, %m6 : i1, i1] %m6 : i1
// CHECK-NEXT:   } [<+:1>{I -> X0}, <+:>{Z0 X1 -> I}, <+:0>{Z0 -> I}]
}
// CHECK: }
