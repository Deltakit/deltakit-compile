// RUN: deltakit_compile compile-passes %s -p generate-flows -O %t && filecheck %s --input-file %t

// This test checks that the generate-flows pass can handle multiple independent
// stabiliser state chains in the same module without cross-contaminating flow
// information between the chains.
//
// In particular, we create two separate state.make roots, each feeding a short
// chain of circuits. The two chains should be processed independently.

builtin.module {
  // --- Chain A (2 qubits) ---
  %a0 = qcore.alloc_qubit -> !qcore.qubit
  %a1 = qcore.alloc_qubit -> !qcore.qubit

  // --- Chain B (1 qubit) ---
  %b0 = qcore.alloc_qubit -> !qcore.qubit

  // Both state roots at the top.
  %a_in = stab.state.make(%a0, %a1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
  %b_in = stab.state.make(%b0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>

  // A0: a single reset on qubit 0.
  %a_s0 = stab.circuit %a_in : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [Z0]>
    with (%qa0, %qa1 : !qcore.qubit), (){
      qref.reset<Z> (%qa0)
      stab.yield []
    }

  // B0: a single reset on qubit 0 of the 1-qubit state.
  %b_s0 = stab.circuit %b_in : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, [Z0]>
    with (%qb0 : !qcore.qubit), (){
      qref.reset<Z> (%qb0)
      stab.yield []
    }

  // B1: a single measurement on qubit 0.
  %b_s1 = stab.circuit %b_s0 : !stab.state<1 x !qcore.qubit, [Z0]> -> !stab.state<1 x !qcore.qubit, []>
    with (%rb0 : !qcore.qubit), (){
      %mb0 = qref.measure<Z> (%rb0) -> i1
      stab.yield [%mb0 : i1]
    }

  // A1: a single measurement on qubit 0.
  %a_s1 = stab.circuit %a_s0 : !stab.state<2 x !qcore.qubit, [Z0]> -> !stab.state<2 x !qcore.qubit, []>
    with (%ra0, %ra1 : !qcore.qubit), (){
      %ma0 = qref.measure<Z> (%ra0) -> i1
      stab.yield [%ma0 : i1]
    }
}

// CHECK: builtin.module {
// CHECK-NEXT:   %a0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:   %a1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:   %b0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:   %a_in = stab.state.make(%a0, %a1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   %b_in = stab.state.make(%b0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:   %a_s0 = stab.circuit %a_in : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [Z0]>
// CHECK-NEXT:     with (%qa0, %qa1 : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%qa0)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{I -> Z0}]
// CHECK-NEXT:   %b_s0 = stab.circuit %b_in : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:     with (%qb0 : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%qb0)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{I -> Z0}]
// CHECK-NEXT:   %b_s1 = stab.circuit %b_s0 : !stab.state<1 x !qcore.qubit, [Z0]> -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:     with (%rb0 : !qcore.qubit), (){
// CHECK-NEXT:       %mb0 = qref.measure<Z> (%rb0) -> i1
// CHECK-NEXT:       stab.yield [%mb0 : i1]
// CHECK-NEXT:     } [<+:0>{I -> Z0}, <+:0>{Z0 -> I}]
// CHECK-NEXT:   %a_s1 = stab.circuit %a_s0 : !stab.state<2 x !qcore.qubit, [Z0]> -> !stab.state<2 x !qcore.qubit, [Z0]>
// CHECK-NEXT:     with (%ra0, %ra1 : !qcore.qubit), (){
// CHECK-NEXT:       %ma0 = qref.measure<Z> (%ra0) -> i1
// CHECK-NEXT:       stab.yield [%ma0 : i1]
// CHECK-NEXT:     } [<+:0>{I -> Z0}, <+:0>{Z0 -> I}]
// CHECK-NEXT: }
