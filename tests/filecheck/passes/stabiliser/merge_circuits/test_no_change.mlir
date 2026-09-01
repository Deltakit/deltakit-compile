// RUN: deltakit_compile compile-passes --test-mode %s -p merge-circuits -O %t && filecheck %s --input-file %t
// Test several configurations that result in no merges being performed.

builtin.module {
// CHECK: builtin.module {

    // No downstream uses
    %state0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
    %state1 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
                                  -> !stab.state<1 x !qcore.qubit, []>
      with (%q0_b : !qcore.qubit), () {
        stab.yield []
      }
// CHECK-NEXT:    %state0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:    %state1 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                  -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:        stab.yield []
// CHECK-NEXT:      }

    // One has flows specified and the other does not
    %state2 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
    %state3 = stab.circuit %state2 : !stab.state<1 x !qcore.qubit, []>
                                  -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q1_b : !qcore.qubit), () {
        stab.yield []
      } [<+:>{I -> Z0}]
    %state4 = stab.circuit %state3 : !stab.state<1 x !qcore.qubit, [Z0]>
                                  -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q2_b : !qcore.qubit), () {
        stab.yield []
      }
// CHECK-NEXT:    %state2 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:    %state3 = stab.circuit %state2 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                  -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:      with (%q1_b : !qcore.qubit), (){
// CHECK-NEXT:        stab.yield []
// CHECK-NEXT:      } [<+:>{I -> Z0}]
// CHECK-NEXT:    %state4 = stab.circuit %state3 : !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-SAME:                                  -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:      with (%q2_b : !qcore.qubit), (){
// CHECK-NEXT:        stab.yield []
// CHECK-NEXT:      }

    // Computation on passed-through values in between
    %state5 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
    %state6, %b0 = stab.circuit %state5 : !stab.state<1 x !qcore.qubit, []>
                                       -> !stab.state<1 x !qcore.qubit, []>
      with (%q3_b : !qcore.qubit), () {
        %b0_in = "test.op"() : () -> i1
        stab.yield [] %b0_in : i1
      }
    %b1 = arith.xori %b0, %b0 : i1
    %state7 = stab.circuit %state6 : !stab.state<1 x !qcore.qubit, []>
                                  -> !stab.state<1 x !qcore.qubit, []>
      with (%q4_b : !qcore.qubit), (%b1_in = %b1 : i1) {
        stab.yield []
      }
// CHECK-NEXT:    %state5 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:    %state6, %b0 = stab.circuit %state5 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                       -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      with (%q3_b : !qcore.qubit), (){
// CHECK-NEXT:        %b0_in = "test.op"() : () -> i1
// CHECK-NEXT:        stab.yield [] %b0_in : i1
// CHECK-NEXT:      }
// CHECK-NEXT:    %b1 = arith.xori %b0, %b0 : i1
// CHECK-NEXT:    %state7 = stab.circuit %state6 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                  -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      with (%q4_b : !qcore.qubit), (%b1_in = %b1 : i1){
// CHECK-NEXT:        stab.yield []
// CHECK-NEXT:      }

    // Quantum computation in between (even unrelated)
    %state8 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
    %state9 = stab.circuit %state8 : !stab.state<1 x !qcore.qubit, []>
                                  -> !stab.state<1 x !qcore.qubit, []>
      with (%q5_b : !qcore.qubit), () {
        stab.yield []
      }
    %state10 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
    %state11 = stab.circuit %state10 : !stab.state<1 x !qcore.qubit, []>
                                    -> !stab.state<1 x !qcore.qubit, []>
      with (%q6_b : !qcore.qubit), () {
        qref.gate<#qcore.gate.h> (%q6_b)
        stab.yield []
      }
    %state12 = stab.circuit %state9 : !stab.state<1 x !qcore.qubit, []>
                                   -> !stab.state<1 x !qcore.qubit, []>
      with (%q7_b : !qcore.qubit), () {
        stab.yield []
      }
// CHECK-NEXT:    %state8 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:    %state9 = stab.circuit %state8 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                  -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      with (%q5_b : !qcore.qubit), (){
// CHECK-NEXT:        stab.yield []
// CHECK-NEXT:      }
// CHECK-NEXT:    %state10 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:    %state11 = stab.circuit %state10 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                    -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      with (%q6_b : !qcore.qubit), (){
// CHECK-NEXT:        qref.gate<#qcore.gate.h> (%q6_b)
// CHECK-NEXT:        stab.yield []
// CHECK-NEXT:      }
// CHECK-NEXT:    %state12 = stab.circuit %state9 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                   -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      with (%q7_b : !qcore.qubit), (){
// CHECK-NEXT:        stab.yield []
// CHECK-NEXT:      }

    // Not in the same block (so there could be control flow)
    %state13 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
    %state14 = stab.circuit %state13 : !stab.state<1 x !qcore.qubit, []>
                                    -> !stab.state<1 x !qcore.qubit, []>
      with (%q8_b : !qcore.qubit), () {
        stab.yield []
      }
    "test.op"() ({
        %state15 = stab.circuit %state14 : !stab.state<1 x !qcore.qubit, []>
                                        -> !stab.state<1 x !qcore.qubit, []>
          with (%q9_b : !qcore.qubit), () {
            stab.yield []
          }

        "test.termop"() : () -> ()
    }) : () -> ()
// CHECK-NEXT:    %state13 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:    %state14 = stab.circuit %state13 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                    -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      with (%q8_b : !qcore.qubit), (){
// CHECK-NEXT:        stab.yield []
// CHECK-NEXT:      }
// CHECK-NEXT:    "test.op"() ({
// CHECK-NEXT:        %state15 = stab.circuit %state14 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                        -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:          with (%q9_b : !qcore.qubit), (){
// CHECK-NEXT:            stab.yield []
// CHECK-NEXT:          }
// CHECK-NEXT:        "test.termop"() : () -> ()
// CHECK-NEXT:    }) : () -> ()

}
// CHECK-NEXT: }
