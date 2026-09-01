// RUN: deltakit_compile compile-passes --test-mode %s -p find-detectors -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK: builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %q1 = qcore.alloc_qubit -> !qcore.qubit

    %state0 = stab.state.make (%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
    %state1 = stab.state.make (%q1 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>

    %x0, %state4, %x1, %x2, %state5, %x3, %x4 = qstruct.parallel<BOTTOM> ->
          i1, !stab.state<1 x !qcore.qubit, [X0]>, i1, i1, !stab.state<1 x !qcore.qubit, [Z0]>, i1, i1 {
// CHECK:      %x0, %state4, [[OUT1:%[0-9]+]], [[OUT2:%[0-9]+]], %x1, %x2, %state5, %x3, %x4 = qstruct.parallel<BOTTOM> ->
// CHECK-SAME:       i1, !stab.state<1 x !qcore.qubit, [X0]>, i1, i1, i1, i1, !stab.state<1 x !qcore.qubit, [Z0]>, i1, i1 {
        %state2 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
                                      -> !stab.state<1 x !qcore.qubit, [X0]>
          with (%q0_b : !qcore.qubit), () {
            %m0 = qref.measure<X> (%q0_b) -> i1
            %m1 = qref.measure<X> (%q0_b) -> i1
            stab.yield [%m0, %m1 : i1, i1]
          } [<+:0, 1>{I -> X0}]
// CHECK-NEXT: %state2, [[OUT1_1:%[0-9]+]], [[OUT2_1:%[0-9]+]] = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                -> !stab.state<1 x !qcore.qubit, [X0]>
// CHECK-NEXT:    with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:      %m0 = qref.measure<X> (%q0_b) -> i1
// CHECK-NEXT:      %m1 = qref.measure<X> (%q0_b) -> i1
// CHECK-NEXT:      stab.yield [%m0, %m1 : i1, i1] %m0, %m1 : i1, i1
// CHECK-NEXT:    } [<+:0, 1>{I -> X0}]

        %y0 = "test.op"() : () -> i1
        %y1 = "test.op"() : () -> i1

        qstruct.yield %y0, %state2, %y1 : i1, !stab.state<1 x !qcore.qubit, [X0]>, i1
// CHECK:      qstruct.yield %y0, %state2, [[OUT1_1]], [[OUT2_1]], %y1 : i1, !stab.state<1 x !qcore.qubit, [X0]>, i1, i1, i1
    } {
// CHECK-NEXT: } {
        %state3 = stab.circuit %state1 : !stab.state<1 x !qcore.qubit, []>
                                      -> !stab.state<1 x !qcore.qubit, [Z0]>
          with (%q1_b : !qcore.qubit), () {
            stab.yield []
          } [<+:>{I -> Z0}]
// CHECK-NEXT: %state3 = stab.circuit %state1 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                               -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:    with (%q1_b : !qcore.qubit), (){
// CHECK-NEXT:      stab.yield []
// CHECK-NEXT:    } [<+:>{I -> Z0}]

        %y2 = "test.op"() : () -> i1
        %y3 = "test.op"() : () -> i1
        %y4 = "test.op"() : () -> i1

        qstruct.yield %y2, %state3, %y3, %y4 : i1, !stab.state<1 x !qcore.qubit, [Z0]>, i1, i1
// CHECK:     qstruct.yield %y2, %state3, %y3, %y4 : i1, !stab.state<1 x !qcore.qubit, [Z0]>, i1, i1
    }
// CHECK-NEXT: }
}
// CHECK-NEXT: }
