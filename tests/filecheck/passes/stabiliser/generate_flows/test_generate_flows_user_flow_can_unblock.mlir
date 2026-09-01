// RUN: deltakit_compile compile-passes %s -p generate-flows -O %t && filecheck %s --input-file %t

// Case where the user flow must be multiplied to unblock.

builtin.module {
  %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %s0_in = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>

  %s0 = stab.circuit %s0_in : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [Z1]>
    with (%r0, %r1 : !qcore.qubit), (){
      qref.reset<Z> (%r1)
      stab.yield []
    }

  %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, [Z1]> -> !stab.state<2 x !qcore.qubit, [Z1]>
    with (%r0, %r1 : !qcore.qubit), (){
      stab.yield []
    } [<+:>{Z1 -> Z1}]

  %s2 = stab.circuit %s1 : !stab.state<2 x !qcore.qubit, [Z1]> -> !stab.state<2 x !qcore.qubit, []>
    with (%r0, %r1 : !qcore.qubit), (){
      qref.reset<Y> (%r0)
      stab.yield []
    }

  // There are two flow chains after the CX gate which are blocked on the MX:
  //   1. I -> Z1 -> Z1 -> Z1 -> Z0 Z1 (from the user flow)
  //   2. I -> I  -> I  -> Y0 -> Y0 X1
  // To unblock we have to multiply them together. Flow chain 2 is young enough not to mess up the
  // user flow's user-specified link, so we can unblock successfully.
  %s3 = stab.circuit %s2 : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, []>
    with (%r0, %r1 : !qcore.qubit), (){
      qref.gate<#qcore.gate.cx> (%r0, %r1)
      %m0 = qref.measure<X> (%r0) -> i1
      stab.yield []
    }
}

// CHECK:      builtin.module {
// CHECK-NEXT:   %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %s0_in = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   %s0 = stab.circuit %s0_in : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [Z1]>
// CHECK-NEXT:     with (%r0, %r1 : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%r1)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{I -> Z1}]
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, [Z1]> -> !stab.state<2 x !qcore.qubit, [Z1]>
// CHECK-NEXT:     with (%r0, %r1 : !qcore.qubit), (){
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{Z1 -> Z1}]
// CHECK-NEXT:   %s2 = stab.circuit %s1 : !stab.state<2 x !qcore.qubit, [Z1]> -> !stab.state<2 x !qcore.qubit, [Y0 Z1]>
// CHECK-NEXT:     with (%r0, %r1 : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Y> (%r0)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{Z1 -> Y0 Z1}]
// CHECK-NEXT:   %s3 = stab.circuit %s2 : !stab.state<2 x !qcore.qubit, [Y0 Z1]> -> !stab.state<2 x !qcore.qubit, [X0 Y1, X0]>
// CHECK-NEXT:     with (%r0, %r1 : !qcore.qubit), (){
// CHECK-NEXT:       qref.gate<#qcore.gate.cx> (%r0, %r1)
// CHECK-NEXT:       %m0 = qref.measure<X> (%r0) -> i1
// CHECK-NEXT:       stab.yield [%m0 : i1]
// CHECK-NEXT:     } [<+:0>{I -> X0}, <+:>{Y0 Z1 -> X0 Y1}]
// CHECK-NEXT: }
