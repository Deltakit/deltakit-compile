// RUN: deltakit_compile compile-passes %s -t -p find-detectors -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK: builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit

    %state0 = stab.state.make (%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK:      %state0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>

    %state1 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
                                  -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q0_b : !qcore.qubit), () {
        %m0 = qref.measure<Z> (%q0_b) -> i1
        stab.yield [%m0 : i1]
      } [<+:0>{I->Z0}]
// CHECK:      %state1, [[OUT1:%[0-9]+]] = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                                 -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:   with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:     %m0 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:     stab.yield [%m0 : i1] %m0 : i1
// CHECK-NEXT:   } [<+:0>{I -> Z0}]

    %state2, %other_value1 = stab.circuit %state1 : !stab.state<1 x !qcore.qubit, [Z0]>
                                  -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q0_b : !qcore.qubit), () {
        %m1 = qref.measure<Z> (%q0_b) -> i1
        %m2 = qref.measure<Z> (%q0_b) -> i1
        %other_value  = "test.op"() : () -> i32
        stab.yield [%m1, %m2 : i1, i1] %other_value : i32
      } [<+:1>{I->Z0}, <+:0>{Z0->I}]

    "test.op"(%other_value1) : (i32) -> ()
// CHECK:      %state2, [[OUT2:%[0-9]+]], %other_value1 = stab.circuit %state1 : !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-SAME:                                                 -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:   with (%q0_b : !qcore.qubit), ([[IN1:%[0-9]+]] = [[OUT1]] : i1){
// CHECK-NEXT:     %m1 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:     %m2 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:     %other_value  = "test.op"() : () -> i32
// CHECK-NEXT:     qec.detector([[IN1]], %m1)
// CHECK-NEXT:     stab.yield [%m1, %m2 : i1, i1] %m2, %other_value : i1, i32
// CHECK-NEXT:   } [<+:1>{I -> Z0}, <+:0>{Z0 -> I}]

// CHECK-NEXT: "test.op"(%other_value1) : (i32) -> ()

    %state3 = stab.circuit %state2 : !stab.state<1 x !qcore.qubit, [Z0]>
                                  -> !stab.state<1 x !qcore.qubit, []>
      with (%q0_b : !qcore.qubit), () {
        %m3 = qref.measure<Z> (%q0_b) -> i1
        stab.yield [%m3 : i1]
      } [<+:0>{Z0->I}]
// CHECK:      %state3 = stab.circuit %state2 : !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-SAME:                               -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:   with (%q0_b : !qcore.qubit), ([[IN2:%[0-9]+]] = [[OUT2]] : i1){
// CHECK-NEXT:     %m3 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:     qec.detector([[IN2]], %m3)
// CHECK-NEXT:     stab.yield [%m3 : i1]
// CHECK-NEXT:   } [<+:0>{Z0 -> I}]
}
// CHECK: }
