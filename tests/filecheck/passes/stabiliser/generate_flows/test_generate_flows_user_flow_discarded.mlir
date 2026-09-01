// RUN: deltakit_compile compile-passes %s -p generate-flows -O %t && filecheck %s --input-file %t

builtin.module {
  %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %s0_in = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>

  %s0 = stab.circuit %s0_in : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [Z0]>
    with (%r0, %r1 : !qcore.qubit), (){
      qref.reset<Z> (%r0)
      stab.yield []
    }

  %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, [Z0]> -> !stab.state<2 x !qcore.qubit, [Z0 Z1]>
    with (%r0, %r1 : !qcore.qubit), (){
      %m0 = qref.measure<Z> (%r1) -> i1
      stab.yield [%m0 : i1]
    } [<+:0>{Z0 -> Z0 Z1}]

  // This circuit naively has a basis of flows:
  //   I -> Z0 Z1 (m1)
  //   Z0 -> I (m1)
  //   Z1 -> Z1
  // But we can't preserve all of them and simultaneously satisfy the user flow (Z0 Z1).
  // So the output should be:
  //   Z0 Z1 -> Z0
  //   I -> Z0 Z1 (m1)
  // even though the destruction flow has to be thrown out.
  %s2 = stab.circuit %s1 : !stab.state<2 x !qcore.qubit, [Z0 Z1]> -> !stab.state<2 x !qcore.qubit, []>
    with (%r0, %r1 : !qcore.qubit), (){
      %m1 = qref.measure<Z> (%r0) -> i1
      qref.gate<#qcore.gate.cx> (%r1, %r0)
      stab.yield []
    }
}

// CHECK:      builtin.module {
// CHECK-NEXT:   %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %s0_in = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   %s0 = stab.circuit %s0_in : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [Z0]>
// CHECK-NEXT:     with (%r0, %r1 : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%r0)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{I -> Z0}]
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, [Z0]> -> !stab.state<2 x !qcore.qubit, [Z0 Z1]>
// CHECK-NEXT:     with (%r0, %r1 : !qcore.qubit), (){
// CHECK-NEXT:       %m0 = qref.measure<Z> (%r1) -> i1
// CHECK-NEXT:       stab.yield [%m0 : i1]
// CHECK-NEXT:     } [<+:0>{Z0 -> Z0 Z1}]
// CHECK-NEXT:   %s2 = stab.circuit %s1 : !stab.state<2 x !qcore.qubit, [Z0 Z1]> -> !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0]>
// CHECK-NEXT:     with (%r0, %r1 : !qcore.qubit), (){
// CHECK-NEXT:       %m1 = qref.measure<Z> (%r0) -> i1
// CHECK-NEXT:       qref.gate<#qcore.gate.cx> (%r1, %r0)
// CHECK-NEXT:       stab.yield [%m1 : i1]
// CHECK-NEXT:     } [<+:0>{I -> Z0 Z1}, <+:>{Z0 Z1 -> Z0}]
// CHECK-NEXT: }
