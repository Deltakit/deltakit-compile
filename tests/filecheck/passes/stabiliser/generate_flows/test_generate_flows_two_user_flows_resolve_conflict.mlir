// RUN: deltakit_compile compile-passes %s -p generate-flows -O %t && filecheck %s --input-file %t

builtin.module {
  %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %s0_in = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>

  %s0 = stab.circuit %s0_in : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [Z0]>
    with (%r0, %r1 : !qcore.qubit), (){
      qref.reset<Z> (%r0)
      stab.yield []
    } [<+:>{I -> Z0}]

  // User Z0 flow from above propagates to Z0 -> Z0, which conflicts with the I -> Z0 flow
  // annotated on this circuit, or Z0 -> I. It must choose Z0 -> I to resolve the conflict even
  // though it's suboptimal in terms of measurement count.
  %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, [Z0]> -> !stab.state<2 x !qcore.qubit, [Z0, Z1]>
    with (%r0, %r1 : !qcore.qubit), (){
      qref.reset<Z> (%r1)
      qref.gate<#qcore.gate.cx> (%r0, %r1)
      %m0 = qref.measure<Z> (%r1) -> i1
      stab.yield [%m0 : i1]
    } [<+:0>{I -> Z0}, <+:0>{I -> Z1}]
}

// CHECK:      builtin.module {
// CHECK-NEXT:   %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %s0_in = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   %s0 = stab.circuit %s0_in : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [Z0]>
// CHECK-NEXT:     with (%r0, %r1 : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%r0)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{I -> Z0}]
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, [Z0]> -> !stab.state<2 x !qcore.qubit, [Z0, Z1]>
// CHECK-NEXT:     with (%r0, %r1 : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%r1)
// CHECK-NEXT:       qref.gate<#qcore.gate.cx> (%r0, %r1)
// CHECK-NEXT:       %m0 = qref.measure<Z> (%r1) -> i1
// CHECK-NEXT:       stab.yield [%m0 : i1]
// CHECK-NEXT:     } [<+:0>{I -> Z0}, <+:0>{I -> Z1}, <+:0>{Z0 -> I}]
// CHECK-NEXT: }
