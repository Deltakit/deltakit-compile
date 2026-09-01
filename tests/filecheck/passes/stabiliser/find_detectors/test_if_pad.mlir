// RUN: deltakit_compile compile-passes --test-mode %s -p find-detectors -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK: builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %q1 = qcore.alloc_qubit -> !qcore.qubit

    %state0 = stab.state.make (%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
    %state1 = stab.state.make (%q1 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>

    %state2 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
                                  -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q0_b : !qcore.qubit), () {
        stab.yield []
      } [<+:>{I -> Z0}]
// CHECK:      %state2 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                               -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:   with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:     stab.yield []
// CHECK-NEXT:   } [<+:>{I -> Z0}]

    %state3 = stab.circuit %state1 : !stab.state<1 x !qcore.qubit, []>
                                  -> !stab.state<1 x !qcore.qubit, [X0]>
      with (%q1_b : !qcore.qubit), () {
        stab.yield []
      } [<+:>{I -> X0}]
// CHECK-NEXT: %state3 = stab.circuit %state1 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                               -> !stab.state<1 x !qcore.qubit, [X0]>
// CHECK-NEXT:   with (%q1_b : !qcore.qubit), (){
// CHECK-NEXT:     stab.yield []
// CHECK-NEXT:   } [<+:>{I -> X0}]

    %b = "test.op"() : () -> i1

    %state4, %state5 = scf.if %b -> (!stab.state<1 x !qcore.qubit, [Z0]>, !stab.state<1 x !qcore.qubit, [X0]>) {
// CHECK:      %state4, [[OUT1:%[0-9]+]], %state5, [[OUT2:%[0-9]+]], [[OUT3:%[0-9]+]] =
// CHECK-SAME:             scf.if %b -> (!stab.state<1 x !qcore.qubit, [Z0]>, i1, !stab.state<1 x !qcore.qubit, [X0]>, i1, i1) {
        %state4_true = stab.circuit %state2 : !stab.state<1 x !qcore.qubit, [Z0]>
                                           -> !stab.state<1 x !qcore.qubit, [Z0]>
          with (%q0_b : !qcore.qubit), () {
            %m1 = qref.measure<Z> (%q0_b) -> i1
            stab.yield [%m1 : i1]
          } [<+:0>{Z0 -> Z0}]
// CHECK-NEXT: %state4_true, [[OUT1_T:%[0-9]+]] = stab.circuit %state2 : !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-SAME:                                 -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:   with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:     %m1 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:     stab.yield [%m1 : i1] %m1 : i1
// CHECK-NEXT:   } [<+:0>{Z0 -> Z0}]

        %state5_true = stab.circuit %state3 : !stab.state<1 x !qcore.qubit, [X0]>
                                           -> !stab.state<1 x !qcore.qubit, [X0]>
          with (%q1_b : !qcore.qubit), () {
            stab.yield []
          } [<+:>{X0 -> X0}]
// CHECK-NEXT: %state5_true = stab.circuit %state3 : !stab.state<1 x !qcore.qubit, [X0]>
// CHECK-SAME:                                    -> !stab.state<1 x !qcore.qubit, [X0]>
// CHECK-NEXT:   with (%q1_b : !qcore.qubit), (){
// CHECK-NEXT:     stab.yield []
// CHECK-NEXT:   } [<+:>{X0 -> X0}]
// CHECK-NEXT: [[PAD1:%[0-9]+]] = arith.constant false

        scf.yield %state4_true, %state5_true : !stab.state<1 x !qcore.qubit, [Z0]>, !stab.state<1 x !qcore.qubit, [X0]>
// CHECK-NEXT: scf.yield %state4_true, [[OUT1_T]], %state5_true, [[PAD1]], [[PAD1]] : !stab.state<1 x !qcore.qubit, [Z0]>,
// CHECK-SAME:           i1, !stab.state<1 x !qcore.qubit, [X0]>, i1, i1
    } else {
// CHECK-NEXT: } else {
      %state4_false = stab.circuit %state2 : !stab.state<1 x !qcore.qubit, [Z0]>
                                          -> !stab.state<1 x !qcore.qubit, [Z0]>
          with (%q0_b : !qcore.qubit), () {
            qref.reset<Z> (%q0_b)
            stab.yield []
          } [<+:>{Z0 -> Z0}]
// CHECK-NEXT: %state4_false = stab.circuit %state2 : !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-SAME:                                     -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:   with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:     qref.reset<Z> (%q0_b)
// CHECK-NEXT:     stab.yield []
// CHECK-NEXT:   } [<+:>{Z0 -> Z0}]
// CHECK-NEXT: [[PAD2:%[0-9]+]] = arith.constant false

      %state5_false = stab.circuit %state3 : !stab.state<1 x !qcore.qubit, [X0]>
                                          -> !stab.state<1 x !qcore.qubit, [X0]>
          with (%q1_b : !qcore.qubit), () {
            %m3 = qref.measure<X> (%q1_b) -> i1
            %m4 = qref.measure<X> (%q1_b) -> i1
            stab.yield [%m3, %m4 : i1, i1]
          } [<+:0, 1>{X0 -> X0}]
// CHECK-NEXT: %state5_false, [[OUT2_F:%[0-9]+]], [[OUT3_F:%[0-9]+]] = stab.circuit %state3 : !stab.state<1 x !qcore.qubit, [X0]>
// CHECK-SAME:                                  -> !stab.state<1 x !qcore.qubit, [X0]>
// CHECK-NEXT:   with (%q1_b : !qcore.qubit), (){
// CHECK-NEXT:     %m3 = qref.measure<X> (%q1_b) -> i1
// CHECK-NEXT:     %m4 = qref.measure<X> (%q1_b) -> i1
// CHECK-NEXT:     stab.yield [%m3, %m4 : i1, i1] %m3, %m4 : i1, i1
// CHECK-NEXT:   } [<+:0, 1>{X0 -> X0}]

      scf.yield %state4_false, %state5_false : !stab.state<1 x !qcore.qubit, [Z0]>, !stab.state<1 x !qcore.qubit, [X0]>
// CHECK-NEXT: scf.yield %state4_false, [[PAD2]], %state5_false, [[OUT2_F]], [[OUT3_F]] :
// CHECK-SAME:           !stab.state<1 x !qcore.qubit, [Z0]>, i1, !stab.state<1 x !qcore.qubit, [X0]>, i1, i1
    }
// CHECK-NEXT: }
}
// CHECK-NEXT: }
