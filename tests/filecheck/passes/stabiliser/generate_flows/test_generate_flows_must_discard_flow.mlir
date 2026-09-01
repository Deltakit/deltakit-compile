// RUN: deltakit_compile compile-passes %s -p generate-flows -O %t && filecheck %s --input-file %t

builtin.module {
  %q0 = qcore.alloc_qubit -> !qcore.qubit
  %s0_in = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>

  %s0 = stab.circuit %s0_in : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, [Z0]>
    with (%p0 : !qcore.qubit), (){
      qref.reset<Z> (%p0)
      stab.yield []
    } [<+:>{I -> Z0}]

  // The I -> Z0 or Z0 -> I flow from the measurement must be discarded because it conflicts with
  // the user flow.
  %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, [Z0]> -> !stab.state<1 x !qcore.qubit, [Z0]>
    with (%r0 : !qcore.qubit), (){
      %m0 = qref.measure<Z> (%r0) -> i1
      stab.yield []
    } [<+:>{Z0 -> Z0}]
}

// CHECK:      builtin.module {
// CHECK-NEXT:   %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:   %s0_in = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:   %s0 = stab.circuit %s0_in : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:     with (%p0 : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%p0)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{I -> Z0}]
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, [Z0]> -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:     with (%r0 : !qcore.qubit), (){
// CHECK-NEXT:       %m0 = qref.measure<Z> (%r0) -> i1
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{Z0 -> Z0}]
// CHECK-NEXT: }
