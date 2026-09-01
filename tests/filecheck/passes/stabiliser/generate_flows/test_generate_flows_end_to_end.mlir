// RUN: deltakit_compile compile-passes %s -p generate-flows -O %t && filecheck %s --input-file %t

builtin.module {
  %q0 = qcore.alloc_qubit -> !qcore.qubit
  %q1 = qcore.alloc_qubit -> !qcore.qubit

  %s0_in = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
  %s0 = stab.circuit %s0_in : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [Z0 Z1, Z1]>
    with (%p0, %p1 : !qcore.qubit), (){
      qstruct.parallel<TOP> -> {
        qref.reset<Z> (%p0)
        qstruct.yield
      } {
        qref.reset<Z> (%p1)
        qstruct.yield
      }
      stab.yield []
    } [<+:>{I -> Z1}]
  %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, [Z0 Z1, Z1]> -> !stab.state<2 x !qcore.qubit, [Z0 Z1]>
    with (%r0, %r1 : !qcore.qubit), (){
      %m0 = qref.measure<Z> (%r0) -> i1
      %m1 = qref.measure<Z> (%r1) -> i1
      stab.yield [%m0, %m1 : i1, i1]
    } [<+:>{Z0 Z1 -> Z0 Z1}]
}

// CHECK: builtin.module {
// CHECK-NEXT:   %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:   %q1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:   %s0_in = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   %s0 = stab.circuit %s0_in : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [Z0 Z1, Z1]>
// CHECK-NEXT:     with (%p0, %p1 : !qcore.qubit), (){
// CHECK-NEXT:       qstruct.parallel<TOP> -> {
// CHECK-NEXT:         qref.reset<Z> (%p0)
// CHECK-NEXT:         qstruct.yield
// CHECK-NEXT:       } {
// CHECK-NEXT:         qref.reset<Z> (%p1)
// CHECK-NEXT:         qstruct.yield
// CHECK-NEXT:       }
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{I -> Z0 Z1}, <+:>{I -> Z1}]
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, [Z0 Z1, Z1]> -> !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0]>
// CHECK-NEXT:     with (%r0, %r1 : !qcore.qubit), (){
// CHECK-NEXT:       %m0 = qref.measure<Z> (%r0) -> i1
// CHECK-NEXT:       %m1 = qref.measure<Z> (%r1) -> i1
// CHECK-NEXT:       stab.yield [%m0, %m1 : i1, i1]
// CHECK-NEXT:     } [<+:0>{I -> Z0}, <+:>{Z0 Z1 -> Z0 Z1}, <+:1>{Z1 -> I}]
// CHECK-NEXT: }
