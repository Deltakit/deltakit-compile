// RUN: deltakit_compile compile-passes %s -t -p find-detectors -O %t && filecheck %s --input-file %t

// No flows specified: no-op

builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %state0 = stab.state.make (%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>

    %state1 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
                                  -> !stab.state<1 x !qcore.qubit, []>
      with (%q0_b : !qcore.qubit), () {
        qref.reset<Z>(%q0_b)
        stab.yield []
      }

    %state2 = stab.circuit %state1 : !stab.state<1 x !qcore.qubit, []>
                                  -> !stab.state<1 x !qcore.qubit, []>
      with (%q0_b : !qcore.qubit), () {
        qref.reset<Z>(%q0_b)
        stab.yield []
      }

    %state3 = stab.circuit %state2 : !stab.state<1 x !qcore.qubit, []>
                                  -> !stab.state<1 x !qcore.qubit, []>
      with (%q0_b : !qcore.qubit), () {
        %other_value  = "test.op"() : () -> i32
        stab.yield []
      }
}

// CHECK:      builtin.module {
// CHECK-NEXT:     %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:     %state0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     %state1 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                   -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:       with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:         qref.reset<Z> (%q0_b)
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       }
// CHECK-NEXT:     %state2 = stab.circuit %state1 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                   -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:       with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:         qref.reset<Z> (%q0_b)
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       }
// CHECK-NEXT:     %state3 = stab.circuit %state2 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                   -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:       with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:         %other_value = "test.op"() : () -> i32
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       }
// CHECK-NEXT: }

// ----
// CHECK-NEXT: ----

// Flows specified in one chain but not in the other: no-op on the other chain

builtin.module {
    %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
    %state00 = stab.state.make (%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
    %state01 = stab.state.make (%q1 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>

    %state10 = stab.circuit %state00 : !stab.state<1 x !qcore.qubit, []>
                                    -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q0_b : !qcore.qubit), () {
        qref.reset<Z>(%q0_b)
        stab.yield []
      } [<+:>{I -> Z0}]

    %state20 = stab.circuit %state10 : !stab.state<1 x !qcore.qubit, [Z0]>
                                    -> !stab.state<1 x !qcore.qubit, []>
      with (%q0_b : !qcore.qubit), () {
        %m0 = qref.measure<Z>(%q0_b) -> i1
        stab.yield [%m0 : i1]
      } [<+:0>{Z0 -> I}]

    %state11 = stab.circuit %state01 : !stab.state<1 x !qcore.qubit, []>
                                    -> !stab.state<1 x !qcore.qubit, []>
      with (%q0_b : !qcore.qubit), () {
        qref.reset<Z>(%q0_b)
        stab.yield []
      }

    %state21 = stab.circuit %state11 : !stab.state<1 x !qcore.qubit, []>
                                    -> !stab.state<1 x !qcore.qubit, []>
      with (%q0_b : !qcore.qubit), () {
        %m0 = qref.measure<Z>(%q0_b) -> i1
        stab.yield [%m0 : i1]
      }
}

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:    %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    %state00 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:    %state01 = stab.state.make(%q1 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:    %state10 = stab.circuit %state00 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                    -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:      with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:        qref.reset<Z> (%q0_b)
// CHECK-NEXT:        stab.yield []
// CHECK-NEXT:      } [<+:>{I -> Z0}]
// CHECK-NEXT:    %state20 = stab.circuit %state10 : !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-SAME:                                    -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:        %m0 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:        [[D0:%[0-9]+]] = qec.detector(%m0)
// CHECK-NEXT:        stab.yield [%m0 : i1]
// CHECK-NEXT:      } [<+:0>{Z0 -> I}]
// CHECK-NEXT:    %state11 = stab.circuit %state01 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                    -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:        qref.reset<Z> (%q0_b)
// CHECK-NEXT:        stab.yield []
// CHECK-NEXT:      }
// CHECK-NEXT:    %state21 = stab.circuit %state11 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                    -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:        %m0 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:        stab.yield [%m0 : i1]
// CHECK-NEXT:      }
// CHECK-NEXT:}

// ----
// CHECK-NEXT: ----

// Flows specified on part of the chain but not the other

builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %state0 = stab.state.make (%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>

    %state1 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
                                  -> !stab.state<1 x !qcore.qubit, []>
      with (%q0_b : !qcore.qubit), () {
        qref.reset<Z>(%q0_b)
        stab.yield []
      }

    %state2 = stab.circuit %state1 : !stab.state<1 x !qcore.qubit, []>
                                  -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q0_b : !qcore.qubit), () {
        qref.reset<Z>(%q0_b)
        stab.yield []
      } [<+:>{I -> Z0}]

    %state3 = stab.circuit %state2 : !stab.state<1 x !qcore.qubit, [Z0]>
                                  -> !stab.state<1 x !qcore.qubit, []>
      with (%q0_b : !qcore.qubit), () {
        %m0 = qref.measure<Z>(%q0_b) -> i1
        stab.yield [%m0 : i1]
      } [<+:0>{Z0 -> I}]
}

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:     %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:     %state0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     %state1 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                   -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:       with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:         qref.reset<Z> (%q0_b)
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       }
// CHECK-NEXT:     %state2 = stab.circuit %state1 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                   -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:       with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:         qref.reset<Z> (%q0_b)
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       } [<+:>{I -> Z0}]
// CHECK-NEXT:     %state3 = stab.circuit %state2 : !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-SAME:                                   -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:       with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:         %m0 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:         [[D0:%[0-9]+]] = qec.detector(%m0)
// CHECK-NEXT:         stab.yield [%m0 : i1]
// CHECK-NEXT:       } [<+:0>{Z0 -> I}]
// CHECK-NEXT: }
