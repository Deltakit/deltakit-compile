// RUN: deltakit_compile compile-passes --test-mode %s -p merge-circuits -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK: builtin.module {

    %state0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:    %state0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>

    %state1 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
                                  -> !stab.state<1 x !qcore.qubit, []>
      with (%q0_b : !qcore.qubit), () {
        qref.gate<#qcore.gate.x> (%q0_b)
        stab.yield []
      }
    %state2 = stab.circuit %state1 : !stab.state<1 x !qcore.qubit, []>
                                  -> !stab.state<1 x !qcore.qubit, []>
      with (%q1_b : !qcore.qubit), () {
        qref.gate<#qcore.gate.z> (%q1_b)
        stab.yield []
      }
// CHECK-NEXT:    %state2 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                  -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:        qref.gate<#qcore.gate.x> (%q0_b)
// CHECK-NEXT:        qref.gate<#qcore.gate.z> (%q0_b)
// CHECK-NEXT:        stab.yield []
// CHECK-NEXT:      }

}
// CHECK-NEXT: }
