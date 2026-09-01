// RUN: deltakit_compile compile-passes %s -p generate-flows -p find-detectors -O %t && filecheck %s --input-file %t

builtin.module {
  %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %s0_in = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>

  %s0 = stab.circuit %s0_in : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [Z0]>
    with (%r0, %r1 : !qcore.qubit), (){
      qref.reset<Z> (%r0)
      stab.yield []
    } [<+:>{I -> Z0}]

  // The user flow Z0 branches to Z0 and Z0 Z1.
  // We preserve only one (Z0, because it minimises measurements).
  %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, [Z0]> -> !stab.state<2 x !qcore.qubit, []>
    with (%r0, %r1 : !qcore.qubit), (){
      %m0 = qref.measure<Z> (%r1) -> i1
      stab.yield [%m0 : i1]
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
// CHECK-NEXT:   %s1, %0 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, [Z0]> -> !stab.state<2 x !qcore.qubit, [Z0, Z1]>
// CHECK-NEXT:     with (%r0, %r1 : !qcore.qubit), (){
// CHECK-NEXT:       %m0 = qref.measure<Z> (%r1) -> i1
// CHECK-NEXT:       stab.yield [%m0 : i1] %m0 : i1
// CHECK-NEXT:     } [<+:0>{I -> Z1}, <+:>{Z0 -> Z0}]
// CHECK-NEXT: }
