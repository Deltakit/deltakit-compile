// RUN: deltakit_compile compile-passes --test-mode %s -p find-detectors -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK: builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %state0 = stab.state.make (%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>

    %state1, %m0 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
                                       -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q0_b : !qcore.qubit), () {
        %m0_in = qref.measure<Z> (%q0_b) -> i1
        stab.yield [%m0_in : i1] %m0_in : i1
      } [<+:0>{I -> Z0}]
// CHECK:      %state1, [[OUT1:%[0-9]+]], %m0 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                               -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:   with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:     %m0_in = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:     stab.yield [%m0_in : i1] %m0_in, %m0_in : i1, i1
// CHECK-NEXT:   } [<+:0>{I -> Z0}]

    %b = "test.op"() : () -> i1

    %state2, %m1 = scf.if %b -> (!stab.state<1 x !qcore.qubit, [Z0]>, i1) {
// CHECK:      %state2, [[OUT2:%[0-9]+]], %m1 = scf.if %b -> (!stab.state<1 x !qcore.qubit, [Z0]>, i1, i1) {
        %state2_true, %m1_true = stab.circuit %state1 : !stab.state<1 x !qcore.qubit, [Z0]>
                                                     -> !stab.state<1 x !qcore.qubit, [Z0]>
          with (%q0_b : !qcore.qubit), () {
            %m1_in = qref.measure<Z> (%q0_b) -> i1
            stab.yield [%m1_in : i1] %m1_in : i1
          } [<+:0>{I -> Z0}, <+:0>{Z0 -> I}]
// CHECK-NEXT:   %state2_true, [[OUT2_T:%[0-9]+]], %m1_true = stab.circuit %state1 : !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-SAME:                                   -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:     with (%q0_b : !qcore.qubit), ([[IN1:%[0-9]+]] = [[OUT1]] : i1){
// CHECK-NEXT:       %m1_in = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:       qec.detector([[IN1]], %m1_in)
// CHECK-NEXT:       stab.yield [%m1_in : i1] %m1_in, %m1_in : i1, i1
// CHECK-NEXT:     } [<+:0>{I -> Z0}, <+:0>{Z0 -> I}]

        scf.yield %state2_true, %m1_true : !stab.state<1 x !qcore.qubit, [Z0]>, i1
// CHECK-NEXT:     scf.yield %state2_true, [[OUT2_T]], %m1_true : !stab.state<1 x !qcore.qubit, [Z0]>, i1, i1
    } else {
// CHECK-NEXT: } else {
        scf.yield %state1, %m0 : !stab.state<1 x !qcore.qubit, [Z0]>, i1
// CHECK-NEXT:     scf.yield %state1, [[OUT1]], %m0 : !stab.state<1 x !qcore.qubit, [Z0]>, i1, i1
    }
// CHECK-NEXT: }

    %state3 = stab.circuit %state2 : !stab.state<1 x !qcore.qubit, [Z0]>
                                  -> !stab.state<1 x !qcore.qubit, []>
      with (%q0_b : !qcore.qubit), () {
        %m2 = qref.measure<Z> (%q0_b) -> i1
        stab.yield [%m2 : i1]
      } [<+:0>{Z0 -> I}]
// CHECK-NEXT: %state3 = stab.circuit %state2 : !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-SAME:                               -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:   with (%q0_b : !qcore.qubit), ([[IN2:%[0-9]+]] = [[OUT2]] : i1){
// CHECK-NEXT:     %m2 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:     qec.detector([[IN2]], %m2)
// CHECK-NEXT:     stab.yield [%m2 : i1]
// CHECK-NEXT:   } [<+:0>{Z0 -> I}]
}
// CHECK-NEXT: }
