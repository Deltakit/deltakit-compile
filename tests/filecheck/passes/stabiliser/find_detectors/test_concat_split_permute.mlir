// RUN: deltakit_compile compile-passes %s -p find-detectors -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK: builtin.module {
    %q0, %q1, %q2, %q3 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT: %q0, %q1, %q2, %q3 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit

    %state0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
    %state1 = stab.state.make(%q2, %q3 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT: %state0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT: %state1 = stab.state.make(%q2, %q3 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>

    %state2 = stab.circuit %state0 : !stab.state<2 x !qcore.qubit, []>
                                  -> !stab.state<2 x !qcore.qubit, [X0 Z1, Z1]>
      with (%q0_b, %q1_b : !qcore.qubit), () {
        %m0 = qref.measure<X> (%q0_b) -> i1
        %m1 = qref.measure<Z> (%q1_b) -> i1
        stab.yield [%m0, %m1 : i1, i1]
      } [<+:0>{I -> X0 Z1}, <+:1>{I -> Z1}]
// CHECK-NEXT: %state2, [[OUT1:%[0-9]+]], [[OUT2:%[0-9]+]] = stab.circuit %state0 : !stab.state<2 x !qcore.qubit, []>
// CHECK-SAME:                                -> !stab.state<2 x !qcore.qubit, [X0 Z1, Z1]>
// CHECK-NEXT:    with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:      %m0 = qref.measure<X> (%q0_b) -> i1
// CHECK-NEXT:      %m1 = qref.measure<Z> (%q1_b) -> i1
// CHECK-NEXT:      stab.yield [%m0, %m1 : i1, i1] %m0, %m1 : i1, i1
// CHECK-NEXT:    } [<+:0>{I -> X0 Z1}, <+:1>{I -> Z1}]

    %state3 = stab.circuit %state1 : !stab.state<2 x !qcore.qubit, []>
                                  -> !stab.state<2 x !qcore.qubit, [X0 Y1, Y1]>
      with (%q2_b, %q3_b : !qcore.qubit), () {
        %m2 = qref.measure<X> (%q2_b) -> i1
        %m3 = qref.measure<Z> (%q3_b) -> i1
        stab.yield [%m2, %m3 : i1, i1]
      } [<+:0>{I -> X0 Y1}, <+:1>{I -> Y1}]
// CHECK-NEXT: %state3, [[OUT3:%[0-9]+]], [[OUT4:%[0-9]+]] = stab.circuit %state1 : !stab.state<2 x !qcore.qubit, []>
// CHECK-SAME:                                -> !stab.state<2 x !qcore.qubit, [X0 Y1, Y1]>
// CHECK-NEXT:    with (%q2_b, %q3_b : !qcore.qubit), (){
// CHECK-NEXT:      %m2 = qref.measure<X> (%q2_b) -> i1
// CHECK-NEXT:      %m3 = qref.measure<Z> (%q3_b) -> i1
// CHECK-NEXT:      stab.yield [%m2, %m3 : i1, i1] %m2, %m3 : i1, i1
// CHECK-NEXT:    } [<+:0>{I -> X0 Y1}, <+:1>{I -> Y1}]

    %state4 = stab.state.permute<[1, 0]> (%state2 : !stab.state<2 x !qcore.qubit, [X0 Z1, Z1]>)
        -> !stab.state<2 x !qcore.qubit, [Z0 X1, Z0]>
// CHECK-NEXT: %state4 = stab.state.permute<[1, 0]> (%state2 : !stab.state<2 x !qcore.qubit, [X0 Z1, Z1]>)
// CHECK-SAME:     -> !stab.state<2 x !qcore.qubit, [Z0 X1, Z0]>

    %state5 = stab.state.permute<[0, 1]> (%state3 : !stab.state<2 x !qcore.qubit, [X0 Y1, Y1]>)
        -> !stab.state<2 x !qcore.qubit, [X0 Y1, Y1]>
// CHECK-NEXT: %state5 = stab.state.permute<[0, 1]> (%state3 : !stab.state<2 x !qcore.qubit, [X0 Y1, Y1]>)
// CHECK-SAME:     -> !stab.state<2 x !qcore.qubit, [X0 Y1, Y1]>

    %state6 = stab.state.concatenate(%state4, %state5 : !stab.state<2 x !qcore.qubit, [Z0 X1, Z0]>,
        !stab.state<2 x !qcore.qubit, [X0 Y1, Y1]>)
        -> !stab.state<4 x !qcore.qubit, [Z0 X1, Z0, X2 Y3, Y3]>
// CHECK-NEXT: %state6 = stab.state.concatenate(%state4, %state5 : !stab.state<2 x !qcore.qubit, [Z0 X1, Z0]>,
// CHECK-SAME:     !stab.state<2 x !qcore.qubit, [X0 Y1, Y1]>)
// CHECK-SAME:     -> !stab.state<4 x !qcore.qubit, [Z0 X1, Z0, X2 Y3, Y3]>

    %state7 = stab.state.permute<[2, 3, 0, 1]> (
        %state6 : !stab.state<4 x !qcore.qubit, [Z0 X1, Z0, X2 Y3, Y3]>)
        -> !stab.state<4 x !qcore.qubit, [X0 Y1, Y1, Z2 X3, Z2]>
// CHECK-NEXT: %state7 = stab.state.permute<[2, 3, 0, 1]> (
// CHECK-SAME:     %state6 : !stab.state<4 x !qcore.qubit, [Z0 X1, Z0, X2 Y3, Y3]>
// CHECK-SAME:     -> !stab.state<4 x !qcore.qubit, [X0 Y1, Y1, Z2 X3, Z2]>

    %state8, %state9 = stab.state.split(%state7 : !stab.state<4 x !qcore.qubit, [X0 Y1, Y1, Z2 X3, Z2]>)
        -> !stab.state<2 x !qcore.qubit, [X0 Y1, Y1]>, !stab.state<2 x !qcore.qubit, [Z0 X1, Z0]>
// CHECK-NEXT: %state8, %state9 = stab.state.split(%state7 : !stab.state<4 x !qcore.qubit, [X0 Y1, Y1, Z2 X3, Z2]>)
// CHECK-SAME:     -> !stab.state<2 x !qcore.qubit, [X0 Y1, Y1]>, !stab.state<2 x !qcore.qubit, [Z0 X1, Z0]>

    %state10 = stab.circuit %state8 : !stab.state<2 x !qcore.qubit, [X0 Y1, Y1]>
                                   -> !stab.state<2 x !qcore.qubit, []>
      with (%q0_b, %q1_b : !qcore.qubit), () {
        %m4 = qref.measure<X> (%q0_b) -> i1
        %m5 = qref.measure<Z> (%q1_b) -> i1
        stab.yield [%m4, %m5 : i1, i1]
      } [<+:0>{X0 Y1 -> I}, <+:1>{Y1 -> I}]
// CHECK-NEXT: %state10 = stab.circuit %state8 : !stab.state<2 x !qcore.qubit, [X0 Y1, Y1]>
// CHECK-SAME:                                -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:    with (%q0_b, %q1_b : !qcore.qubit), ([[IN3:%[0-9]+]] = [[OUT3]] : i1, [[IN4:%[0-9]+]] = [[OUT4]] : i1){
// CHECK-NEXT:      %m4 = qref.measure<X> (%q0_b) -> i1
// CHECK-NEXT:      %m5 = qref.measure<Z> (%q1_b) -> i1
// CHECK-NEXT:      qec.detector([[IN3]], %m4)
// CHECK-NEXT:      qec.detector([[IN4]], %m5)
// CHECK-NEXT:      stab.yield [%m4, %m5 : i1, i1]
// CHECK-NEXT:    } [<+:0>{X0 Y1 -> I}, <+:1>{Y1 -> I}]

    %state11 = stab.circuit %state9 : !stab.state<2 x !qcore.qubit, [Z0 X1, Z0]>
                                   -> !stab.state<2 x !qcore.qubit, []>
      with (%q2_b, %q3_b : !qcore.qubit), () {
        %m6 = qref.measure<X> (%q2_b) -> i1
        %m7 = qref.measure<Z> (%q3_b) -> i1
        stab.yield [%m6, %m7 : i1, i1]
      } [<+:0>{Z0 X1 -> I}, <+:1>{Z0 -> I}]
// CHECK-NEXT: %state11 = stab.circuit %state9 : !stab.state<2 x !qcore.qubit, [Z0 X1, Z0]>
// CHECK-SAME:                                -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:    with (%q2_b, %q3_b : !qcore.qubit), ([[IN1:%[0-9]+]] = [[OUT1]] : i1, [[IN2:%[0-9]+]] = [[OUT2]] : i1){
// CHECK-NEXT:      %m6 = qref.measure<X> (%q2_b) -> i1
// CHECK-NEXT:      %m7 = qref.measure<Z> (%q3_b) -> i1
// CHECK-NEXT:      qec.detector([[IN1]], %m6)
// CHECK-NEXT:      qec.detector([[IN2]], %m7)
// CHECK-NEXT:      stab.yield [%m6, %m7 : i1, i1]
// CHECK-NEXT:    } [<+:0>{Z0 X1 -> I}, <+:1>{Z0 -> I}]
}
// CHECK-NEXT: }
