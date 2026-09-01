// RUN: deltakit_compile compile-passes %s -p find-detectors -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK: builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %q1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT: %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT: %q1 = qcore.alloc_qubit -> !qcore.qubit

    %state0 = stab.state.make (%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT: %state0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>

    // Generated detector not in span of existing detectors: added
    %state1 = stab.circuit %state0 : !stab.state<2 x !qcore.qubit, []>
                                  -> !stab.state<2 x !qcore.qubit, [X0]>
      with (%q0_b, %q1_b : !qcore.qubit), () {
        %m0 = qref.measure<X> (%q0_b) -> i1
        stab.yield [%m0 : i1]
      } [<+:0>{I -> X0}]
    %state2 = stab.circuit %state1 : !stab.state<2 x !qcore.qubit, [X0]>
                                  -> !stab.state<2 x !qcore.qubit, []>
      with (%q0_b, %q1_b : !qcore.qubit), () {
        %m1 = qref.measure<X> (%q0_b) -> i1
        %m2 = qref.measure<X> (%q1_b) -> i1
        qec.detector(%m1, %m2)
        stab.yield [%m1 : i1]
      } [<+:0>{X0 -> I}]
// CHECK-NEXT: %state1, [[OUT1:%[0-9]+]] = stab.circuit %state0 : !stab.state<2 x !qcore.qubit, []>
// CHECK-SAME:                                                 -> !stab.state<2 x !qcore.qubit, [X0]>
// CHECK-NEXT:   with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:     %m0 = qref.measure<X> (%q0_b) -> i1
// CHECK-NEXT:     stab.yield [%m0 : i1] %m0 : i1
// CHECK-NEXT:   } [<+:0>{I -> X0}]
// CHECK-NEXT: %state2 = stab.circuit %state1 : !stab.state<2 x !qcore.qubit, [X0]>
// CHECK-SAME:                               -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   with (%q0_b, %q1_b : !qcore.qubit), ([[IN1:%[0-9]+]] = [[OUT1]] : i1){
// CHECK-NEXT:     %m1 = qref.measure<X> (%q0_b) -> i1
// CHECK-NEXT:     %m2 = qref.measure<X> (%q1_b) -> i1
// CHECK-NEXT:     qec.detector(%m1, %m2)
// CHECK-NEXT:     qec.detector([[IN1]], %m1)
// CHECK-NEXT:     stab.yield [%m1 : i1]
// CHECK-NEXT:   } [<+:0>{X0 -> I}]

    // Generated detector equal to existing detector: not added
    %state3 = stab.circuit %state2 : !stab.state<2 x !qcore.qubit, []>
                                  -> !stab.state<2 x !qcore.qubit, [X0]>
      with (%q0_b, %q1_b : !qcore.qubit), () {
        stab.yield []
      } [<+:>{I -> X0}]
    %state4 = stab.circuit %state3 : !stab.state<2 x !qcore.qubit, [X0]>
                                  -> !stab.state<2 x !qcore.qubit, []>
      with (%q0_b, %q1_b : !qcore.qubit), () {
        %m3 = qref.measure<X> (%q0_b) -> i1
        %m4 = qref.measure<X> (%q0_b) -> i1
        qec.detector(%m3, %m4)
        stab.yield [%m3, %m4 : i1, i1]
      } [<+:0,1>{X0 -> I}]
// CHECK-NEXT: %state3 = stab.circuit %state2 : !stab.state<2 x !qcore.qubit, []>
// CHECK-SAME:                               -> !stab.state<2 x !qcore.qubit, [X0]>
// CHECK-NEXT:   with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:     stab.yield []
// CHECK-NEXT:   } [<+:>{I -> X0}]
// CHECK-NEXT: %state4 = stab.circuit %state3 : !stab.state<2 x !qcore.qubit, [X0]>
// CHECK-SAME:                               -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:     %m3 = qref.measure<X> (%q0_b) -> i1
// CHECK-NEXT:     %m4 = qref.measure<X> (%q0_b) -> i1
// CHECK-NEXT:     qec.detector(%m3, %m4)
// CHECK-NEXT:     stab.yield [%m3, %m4 : i1, i1]
// CHECK-NEXT:   } [<+:0, 1>{X0 -> I}]

    // Generated detector in span of existing detectors: not added
    %state5 = stab.circuit %state4 : !stab.state<2 x !qcore.qubit, []>
                                  -> !stab.state<2 x !qcore.qubit, [X0]>
      with (%q0_b, %q1_b : !qcore.qubit), () {
        stab.yield []
      } [<+:>{I -> X0}]
    %state6 = stab.circuit %state5 : !stab.state<2 x !qcore.qubit, [X0]>
                                  -> !stab.state<2 x !qcore.qubit, []>
      with (%q0_b, %q1_b : !qcore.qubit), () {
        %m5 = qref.measure<X> (%q0_b) -> i1
        %m6 = qref.measure<X> (%q1_b) -> i1
        %m7 = qref.measure<X> (%q1_b) -> i1
        qec.detector(%m5, %m6)
        qec.detector(%m5, %m7)
        stab.yield [%m6, %m7 : i1, i1]
      } [<+:0,1>{X0 -> I}]
// CHECK-NEXT: %state5 = stab.circuit %state4 : !stab.state<2 x !qcore.qubit, []>
// CHECK-SAME:                               -> !stab.state<2 x !qcore.qubit, [X0]>
// CHECK-NEXT:   with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:     stab.yield []
// CHECK-NEXT:   } [<+:>{I -> X0}]
// CHECK-NEXT: %state6 = stab.circuit %state5 : !stab.state<2 x !qcore.qubit, [X0]>
// CHECK-SAME:                               -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:     %m5 = qref.measure<X> (%q0_b) -> i1
// CHECK-NEXT:     %m6 = qref.measure<X> (%q1_b) -> i1
// CHECK-NEXT:     %m7 = qref.measure<X> (%q1_b) -> i1
// CHECK-NEXT:     qec.detector(%m5, %m6)
// CHECK-NEXT:     qec.detector(%m5, %m7)
// CHECK-NEXT:     stab.yield [%m6, %m7 : i1, i1]
// CHECK-NEXT:   } [<+:0, 1>{X0 -> I}]

    // Second generated detector in span of existing detectors + first generated detector: not added
    %state7 = stab.circuit %state6 : !stab.state<2 x !qcore.qubit, []>
                                  -> !stab.state<2 x !qcore.qubit, [X0, X1]>
      with (%q0_b, %q1_b : !qcore.qubit), () {
        stab.yield []
      } [<+:>{I -> X0}, <+:>{I -> X1}]
    %state8 = stab.circuit %state7 : !stab.state<2 x !qcore.qubit, [X0, X1]>
                                  -> !stab.state<2 x !qcore.qubit, []>
      with (%q0_b, %q1_b : !qcore.qubit), () {
        %m8 = qref.measure<X> (%q0_b) -> i1
        %m9 = qref.measure<X> (%q1_b) -> i1
        %m10 = qref.measure<X> (%q1_b) -> i1
        qec.detector(%m8, %m9)
        stab.yield [%m8, %m9, %m10 : i1, i1, i1]
      } [<+:0,2>{X0 -> I}, <+:1,2>{X1 -> I}]
// CHECK-NEXT: %state7 = stab.circuit %state6 : !stab.state<2 x !qcore.qubit, []>
// CHECK-SAME:                               -> !stab.state<2 x !qcore.qubit, [X0, X1]>
// CHECK-NEXT:   with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:     stab.yield []
// CHECK-NEXT:   } [<+:>{I -> X0}, <+:>{I -> X1}]
// CHECK-NEXT: %state8 = stab.circuit %state7 : !stab.state<2 x !qcore.qubit, [X0, X1]>
// CHECK-SAME:                               -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:     %m8 = qref.measure<X> (%q0_b) -> i1
// CHECK-NEXT:     %m9 = qref.measure<X> (%q1_b) -> i1
// CHECK-NEXT:     %m10 = qref.measure<X> (%q1_b) -> i1
// CHECK-NEXT:     qec.detector(%m8, %m9)
// CHECK-NEXT:     qec.detector(%m8, %m10)
// CHECK-NEXT:     stab.yield [%m8, %m9, %m10 : i1, i1, i1]
// CHECK-NEXT:   } [<+:0, 2>{X0 -> I}, <+:1, 2>{X1 -> I}]

    // Generated detector equal to existing detector through input args: not added
    %state9, %m12 = stab.circuit %state8 : !stab.state<2 x !qcore.qubit, []>
                                        -> !stab.state<2 x !qcore.qubit, [X0]>
      with (%q0_b, %q1_b : !qcore.qubit), () {
        %m11 = qref.measure<X> (%q0_b) -> i1
        stab.yield [%m11 : i1] %m11 : i1
      } [<+:0>{I -> X0}]
    %state10 = stab.circuit %state9 : !stab.state<2 x !qcore.qubit, [X0]>
                                   -> !stab.state<2 x !qcore.qubit, []>
      with (%q0_b, %q1_b : !qcore.qubit), (%m13 = %m12 : i1) {
        %m14 = qref.measure<X> (%q1_b) -> i1
        qec.detector(%m13, %m14)
        stab.yield [%m14 : i1]
      } [<+:0>{X0 -> I}]
// CHECK-NEXT: %state9, [[OUT2:%[0-9]+]], %m12 = stab.circuit %state8 : !stab.state<2 x !qcore.qubit, []>
// CHECK-SAME:                                                       -> !stab.state<2 x !qcore.qubit, [X0]>
// CHECK-NEXT:   with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:     %m11 = qref.measure<X> (%q0_b) -> i1
// CHECK-NEXT:     stab.yield [%m11 : i1] %m11, %m11 : i1, i1
// CHECK-NEXT:   } [<+:0>{I -> X0}]
// CHECK-NEXT: %state10 = stab.circuit %state9 : !stab.state<2 x !qcore.qubit, [X0]>
// CHECK-SAME:                                -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   with (%q0_b, %q1_b : !qcore.qubit), (%m13 = %m12 : i1, [[IN2:%[0-9]+]] = [[OUT2]] : i1){
// CHECK-NEXT:     %m14 = qref.measure<X> (%q1_b) -> i1
// CHECK-NEXT:     qec.detector(%m13, %m14)
// CHECK-NEXT:     stab.yield [%m14 : i1]
// CHECK-NEXT:   } [<+:0>{X0 -> I}]

    // Tracing measurements back through parallel works (no detector added)
    %state11, %m17, %m18 = stab.circuit %state10 : !stab.state<2 x !qcore.qubit, []>
                                                -> !stab.state<2 x !qcore.qubit, [X0]>
      with (%q0_b, %q1_b : !qcore.qubit), () {
        %m15 = qref.measure<X> (%q0_b) -> i1
        %m16 = qref.measure<X> (%q0_b) -> i1
        stab.yield [%m15, %m16 : i1, i1] %m15, %m16 : i1, i1
      } [<+:0,1>{I -> X0}]
    %m19, %m20 = qstruct.parallel<TOP> -> i1, i1 {
        qstruct.yield %m17 : i1
    } {
        qstruct.yield %m18 : i1
    }
    %state12 = stab.circuit %state11 : !stab.state<2 x !qcore.qubit, [X0]>
                                    -> !stab.state<2 x !qcore.qubit, []>
      with (%q0_b, %q1_b : !qcore.qubit), (%m21 = %m19 : i1, %m22 = %m20 : i1) {
        qec.detector(%m21, %m22)
        stab.yield []
      } [<+:>{X0 -> I}]
// CHECK-NEXT: %state11, [[OUT3:%[0-9]+]], [[OUT4:%[0-9]+]], %m17, %m18 =
// CHECK-SAME:     stab.circuit %state10 : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [X0]>
// CHECK-NEXT:   with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:     %m15 = qref.measure<X> (%q0_b) -> i1
// CHECK-NEXT:     %m16 = qref.measure<X> (%q0_b) -> i1
// CHECK-NEXT:     stab.yield [%m15, %m16 : i1, i1] %m15, %m16, %m15, %m16 : i1, i1, i1, i1
// CHECK-NEXT:   } [<+:0, 1>{I -> X0}]
// CHECK-NEXT: %m19, %m20 = qstruct.parallel<TOP> -> i1, i1 {
// CHECK-NEXT:     qstruct.yield %m17 : i1
// CHECK-NEXT: } {
// CHECK-NEXT:     qstruct.yield %m18 : i1
// CHECK-NEXT: }
// CHECK-NEXT: %state12 = stab.circuit %state11 : !stab.state<2 x !qcore.qubit, [X0]>
// CHECK-SAME:                                 -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   with (%q0_b, %q1_b : !qcore.qubit), (%m21 = %m19 : i1, %m22 = %m20 : i1,
// CHECK-SAME:                  [[IN3:%[0-9]+]] = [[OUT3]] : i1, [[IN4:%[0-9]+]] = [[OUT4]] : i1){
// CHECK-NEXT:     qec.detector(%m21, %m22)
// CHECK-NEXT:     stab.yield []
// CHECK-NEXT:   } [<+:>{X0 -> I}]

    // Duplicate measurements in detector handled properly (treated mod 2)
    %state13 = stab.circuit %state12 : !stab.state<2 x !qcore.qubit, []>
                                    -> !stab.state<2 x !qcore.qubit, [X0]>
      with (%q0_b, %q1_b : !qcore.qubit), () {
        stab.yield []
      } [<+:>{I -> X0}]
    %state14 = stab.circuit %state13 : !stab.state<2 x !qcore.qubit, [X0]>
                                    -> !stab.state<2 x !qcore.qubit, []>
      with (%q0_b, %q1_b : !qcore.qubit), () {
        %m23 = qref.measure<X> (%q0_b) -> i1
        %m24 = qref.measure<X> (%q0_b) -> i1
        qec.detector(%m23, %m24, %m24)
        stab.yield [%m23 : i1]
      } [<+:0>{X0 -> I}]
// CHECK-NEXT: %state13 = stab.circuit %state12 : !stab.state<2 x !qcore.qubit, []>
// CHECK-SAME:                                 -> !stab.state<2 x !qcore.qubit, [X0]>
// CHECK-NEXT:   with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:     stab.yield []
// CHECK-NEXT:   } [<+:>{I -> X0}]
// CHECK-NEXT: %state14 = stab.circuit %state13 : !stab.state<2 x !qcore.qubit, [X0]>
// CHECK-SAME:                                 -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:     %m23 = qref.measure<X> (%q0_b) -> i1
// CHECK-NEXT:     %m24 = qref.measure<X> (%q0_b) -> i1
// CHECK-NEXT:     qec.detector(%m23, %m24, %m24)
// CHECK-NEXT:     stab.yield [%m23 : i1]
// CHECK-NEXT:   } [<+:0>{X0 -> I}]

    // Empty detector: not added
    %state15 = stab.circuit %state14 : !stab.state<2 x !qcore.qubit, []>
                                    -> !stab.state<2 x !qcore.qubit, [X0]>
      with (%q0_b, %q1_b : !qcore.qubit), () {
        stab.yield []
      } [<+:>{I -> X0}]
    %state16 = stab.circuit %state15 : !stab.state<2 x !qcore.qubit, [X0]>
                                    -> !stab.state<2 x !qcore.qubit, []>
      with (%q0_b, %q1_b : !qcore.qubit), () {
        stab.yield []
      } [<+:>{X0 -> I}]
// CHECK-NEXT: %state15 = stab.circuit %state14 : !stab.state<2 x !qcore.qubit, []>
// CHECK-SAME:                                 -> !stab.state<2 x !qcore.qubit, [X0]>
// CHECK-NEXT:   with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:     stab.yield []
// CHECK-NEXT:   } [<+:>{I -> X0}]
// CHECK-NEXT: %state16 = stab.circuit %state15 : !stab.state<2 x !qcore.qubit, [X0]>
// CHECK-SAME:                                 -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:     stab.yield []
// CHECK-NEXT:   } [<+:>{X0 -> I}]

}
// CHECK-NEXT: }
