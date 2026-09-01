// RUN: deltakit_compile compile-passes %s -p generate-flows -O %t && filecheck %s --input-file %t

// The user should be able to specify linearly dependent creation flows.

builtin.module {
  %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %s0_in = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>

  %s0 = stab.circuit %s0_in : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0, Z1]>
    with (%r0, %r1 : !qcore.qubit), (){
      qref.reset<Z> (%r0)
      qref.reset<Z> (%r1)
      stab.yield []
    } [<+:>{I -> Z0 Z1}, <+:>{I -> Z0}, <+:>{I -> Z1}]

  // They all propagate peacefully through an identity circuit even though they're dependent.
  %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0, Z1]> -> !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0, Z1]>
    with (%r0, %r1 : !qcore.qubit), (){
      stab.yield []
    }
}

// CHECK:      builtin.module {
// CHECK-NEXT:   %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %s0_in = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   %s0 = stab.circuit %s0_in : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0, Z1]>
// CHECK-NEXT:     with (%r0, %r1 : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%r0)
// CHECK-NEXT:       qref.reset<Z> (%r1)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{I -> Z0 Z1}, <+:>{I -> Z0}, <+:>{I -> Z1}]
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0, Z1]> -> !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0, Z1]>
// CHECK-NEXT:     with (%r0, %r1 : !qcore.qubit), (){
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{Z0 Z1 -> Z0 Z1}, <+:>{Z0 -> Z0}, <+:>{Z1 -> Z1}]
// CHECK-NEXT: }

// ----
// CHECK-NEXT: ----

// Also linearly dependent destruction flows.

builtin.module {
  %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %s0_in = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>

  %s0 = stab.circuit %s0_in : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0, Z1]>
    with (%r0, %r1 : !qcore.qubit), (){
      qref.reset<Z> (%r0)
      qref.reset<Z> (%r1)
      stab.yield []
    }

  %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0, Z1]> -> !stab.state<2 x !qcore.qubit, []>
    with (%r0, %r1 : !qcore.qubit), (){
      %m0 = qref.measure<Z> (%r0) -> i1
      %m1 = qref.measure<Z> (%r1) -> i1
      stab.yield [%m0, %m1 : i1, i1]
    } [<+:0, 1>{Z0 Z1 -> I}, <+:0>{Z0 -> I}, <+:1>{Z1 -> I}]
}

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %s0_in = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   %s0 = stab.circuit %s0_in : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0, Z1]>
// CHECK-NEXT:     with (%r0, %r1 : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%r0)
// CHECK-NEXT:       qref.reset<Z> (%r1)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{I -> Z0 Z1}, <+:>{I -> Z0}, <+:>{I -> Z1}]
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0, Z1]> -> !stab.state<2 x !qcore.qubit, [Z0, Z1]>
// CHECK-NEXT:     with (%r0, %r1 : !qcore.qubit), (){
// CHECK-NEXT:       %m0 = qref.measure<Z> (%r0) -> i1
// CHECK-NEXT:       %m1 = qref.measure<Z> (%r1) -> i1
// CHECK-NEXT:       stab.yield [%m0, %m1 : i1, i1]
// CHECK-NEXT:     } [<+:0>{I -> Z0}, <+:1>{I -> Z1}, <+:0, 1>{Z0 Z1 -> I}, <+:0>{Z0 -> I}, <+:1>{Z1 -> I}]
// CHECK-NEXT: }

// ----
// CHECK-NEXT: ----

// Also linearly dependent flows in the middle.

builtin.module {
  %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %s0_in = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>

  %s0 = stab.circuit %s0_in : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0, Z1]>
    with (%r0, %r1 : !qcore.qubit), (){
      qref.reset<Z> (%r0)
      qref.reset<Z> (%r1)
      stab.yield []
    }

  %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0, Z1]> -> !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0, Z1]>
    with (%r0, %r1 : !qcore.qubit), (){
      stab.yield []
    } [<+:>{Z0 Z1 -> Z0 Z1}, <+:>{Z0 -> Z0}, <+:>{Z1 -> Z1}]

  %s2 = stab.circuit %s1 : !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0, Z1]> -> !stab.state<2 x !qcore.qubit, []>
    with (%r0, %r1 : !qcore.qubit), (){
      %m0 = qref.measure<Z> (%r0) -> i1
      %m1 = qref.measure<Z> (%r1) -> i1
      stab.yield []
    }
}

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %s0_in = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   %s0 = stab.circuit %s0_in : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0, Z1]>
// CHECK-NEXT:     with (%r0, %r1 : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%r0)
// CHECK-NEXT:       qref.reset<Z> (%r1)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{I -> Z0 Z1}, <+:>{I -> Z0}, <+:>{I -> Z1}]
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0, Z1]> -> !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0, Z1]>
// CHECK-NEXT:     with (%r0, %r1 : !qcore.qubit), (){
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{Z0 Z1 -> Z0 Z1}, <+:>{Z0 -> Z0}, <+:>{Z1 -> Z1}]
// CHECK-NEXT:   %s2 = stab.circuit %s1 : !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0, Z1]> -> !stab.state<2 x !qcore.qubit, [Z0, Z1]>
// CHECK-NEXT:     with (%r0, %r1 : !qcore.qubit), (){
// CHECK-NEXT:       %m0 = qref.measure<Z> (%r0) -> i1
// CHECK-NEXT:       %m1 = qref.measure<Z> (%r1) -> i1
// CHECK-NEXT:       stab.yield [%m0, %m1 : i1, i1]
// CHECK-NEXT:     } [<+:0>{I -> Z0}, <+:1>{I -> Z1}, <+:0, 1>{Z0 Z1 -> I}, <+:0>{Z0 -> I}, <+:1>{Z1 -> I}]
// CHECK-NEXT: }
