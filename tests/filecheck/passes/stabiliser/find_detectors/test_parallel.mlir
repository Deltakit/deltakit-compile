// RUN: deltakit_compile compile-passes %s -p find-detectors -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK: builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %q1 = qcore.alloc_qubit -> !qcore.qubit
    %q2 = qcore.alloc_qubit -> !qcore.qubit

    %state0 = stab.state.make (%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
    %state1 = stab.state.make (%q2 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>

    %state2 = stab.circuit %state0 : !stab.state<2 x !qcore.qubit, []>
                                  -> !stab.state<2 x !qcore.qubit, [X0 X1]>
      with (%q0_b, %q1_b : !qcore.qubit), () {
        %m0 = qref.measure<X> (%q0_b) -> i1
        stab.yield [%m0 : i1]
      } [<+:0>{I -> X0 X1}]
// CHECK:      %state2, [[OUT1:%[0-9]+]] = stab.circuit %state0 : !stab.state<2 x !qcore.qubit, []>
// CHECK-SAME:                               -> !stab.state<2 x !qcore.qubit, [X0 X1]>
// CHECK-NEXT:   with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:     %m0 = qref.measure<X> (%q0_b) -> i1
// CHECK-NEXT:     stab.yield [%m0 : i1] %m0 : i1
// CHECK-NEXT:   } [<+:0>{I -> X0 X1}]

    %state3 = stab.circuit %state1 : !stab.state<1 x !qcore.qubit, []>
                                  -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q2_b : !qcore.qubit), () {
        %m1 = qref.measure<Z> (%q2_b) -> i1
        stab.yield [%m1 : i1]
      } [<+:0>{I -> Z0}]
// CHECK-NEXT: %state3, [[OUT2:%[0-9]+]] = stab.circuit %state1 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                               -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:   with (%q2_b : !qcore.qubit), (){
// CHECK-NEXT:     %m1 = qref.measure<Z> (%q2_b) -> i1
// CHECK-NEXT:     stab.yield [%m1 : i1] %m1 : i1
// CHECK-NEXT:   } [<+:0>{I -> Z0}]

    %state4, %state5 = qstruct.parallel<TOP> -> !stab.state<2 x !qcore.qubit, [X0 X1]>, !stab.state<1 x !qcore.qubit, [Z0]> {
// CHECK-NEXT: %state4, [[OUT3:%[0-9]+]], %state5, [[OUT4:%[0-9]+]], [[OUT5:%[0-9]+]], [[OUT6:%[0-9]+]] = qstruct.parallel<TOP>
// CHECK-SAME:      -> !stab.state<2 x !qcore.qubit, [X0 X1]>, i1, !stab.state<1 x !qcore.qubit, [Z0]>, i1, i1, i1 {

        %state4_in = stab.circuit %state2 : !stab.state<2 x !qcore.qubit, [X0 X1]>
                                         -> !stab.state<2 x !qcore.qubit, [X0 X1]>
          with (%q0_b, %q1_b : !qcore.qubit), () {
            %m2 = qref.measure<X> (%q0_b) -> i1
            %m3 = qref.measure<X> (%q1_b) -> i1
            stab.yield [%m2, %m3 : i1, i1]
          } [<+:1>{I -> X0 X1}, <+:0>{X0 X1 -> I}]
// CHECK-NEXT:   %state4_in, [[OUT3_1:%[0-9]+]] = stab.circuit %state2 : !stab.state<2 x !qcore.qubit, [X0 X1]>
// CHECK-SAME:                                 -> !stab.state<2 x !qcore.qubit, [X0 X1]>
// CHECK-NEXT:     with (%q0_b, %q1_b : !qcore.qubit), ([[IN1:%[0-9]+]] = [[OUT1]] : i1){
// CHECK-NEXT:       %m2 = qref.measure<X> (%q0_b) -> i1
// CHECK-NEXT:       %m3 = qref.measure<X> (%q1_b) -> i1
// CHECK-NEXT:       qec.detector([[IN1]], %m2)
// CHECK-NEXT:       stab.yield [%m2, %m3 : i1, i1] %m3 : i1
// CHECK-NEXT:     } [<+:1>{I -> X0 X1}, <+:0>{X0 X1 -> I}]

        qstruct.yield %state4_in : !stab.state<2 x !qcore.qubit, [X0 X1]>
// CHECK-NEXT:     qstruct.yield %state4_in, [[OUT3_1]] : !stab.state<2 x !qcore.qubit, [X0 X1]>, i1
    } {
// CHECK-NEXT:   } {
        %state5_in = stab.circuit %state3 : !stab.state<1 x !qcore.qubit, [Z0]>
                                         -> !stab.state<1 x !qcore.qubit, [Z0]>
          with (%q2_b : !qcore.qubit), () {
            %m4 = qref.measure<Z> (%q2_b) -> i1
            %m5 = qref.measure<Z> (%q2_b) -> i1
            stab.yield [%m4, %m5 : i1, i1]
          } [<+:0, 1>{Z0 -> Z0}]
// CHECK-NEXT:   %state5_in, [[OUT4_1:%[0-9]+]], [[OUT5_1:%[0-9]+]], [[OUT6_1:%[0-9]+]]
// CHECK-SAME:          = stab.circuit %state3 : !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-SAME:                                -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:     with (%q2_b : !qcore.qubit), ([[IN2:%[0-9]+]] = [[OUT2]] : i1){
// CHECK-NEXT:       %m4 = qref.measure<Z> (%q2_b) -> i1
// CHECK-NEXT:       %m5 = qref.measure<Z> (%q2_b) -> i1
// CHECK-NEXT:       stab.yield [%m4, %m5 : i1, i1] [[IN2]], %m4, %m5 : i1, i1, i1
// CHECK-NEXT:     } [<+:0, 1>{Z0 -> Z0}]

        qstruct.yield %state5_in : !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:   qstruct.yield %state5_in, [[OUT4_1]], [[OUT5_1]], [[OUT6_1]] : !stab.state<1 x !qcore.qubit, [Z0]>, i1, i1, i1
    }
// CHECK-NEXT: }
}
// CHECK-NEXT: }
