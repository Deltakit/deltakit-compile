// RUN: deltakit_compile compile-passes %s -p generate-flows -O %t && filecheck %s --input-file %t

// Tests that generate-flows is able to generate flow information through stab.state.permute ops.

builtin.module {
  %a, %b = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %s0 = stab.state.make(%a, %b : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>

  %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, []>
    with (%qa, %qb : !qcore.qubit), () {
      qref.reset<X> (%qa)
      qref.reset<Z> (%qb)
      stab.yield []
    }

  %s2 = stab.state.permute<[1, 0]> (%s1 : !stab.state<2 x !qcore.qubit, []>) -> !stab.state<2 x !qcore.qubit, []>

  %s3 = stab.circuit %s2 : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, []>
    with (%qa2, %qb2 : !qcore.qubit), () {
      %ma = qref.measure<Z> (%qa2) -> i1
      %mb = qref.measure<X> (%qb2) -> i1
      stab.yield []
    }
}

// CHECK:      builtin.module {
// CHECK-NEXT:   %a, %b = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %s0 = stab.state.make(%a, %b : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [X0, Z1]>
// CHECK-NEXT:     with (%qa, %qb : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<X> (%qa)
// CHECK-NEXT:       qref.reset<Z> (%qb)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{I -> X0}, <+:>{I -> Z1}]
// CHECK-NEXT:   %s2 = stab.state.permute<[1, 0]> (%s1 : !stab.state<2 x !qcore.qubit, [X0, Z1]>)
// CHECK-SAME:       -> !stab.state<2 x !qcore.qubit, [Z0, X1]>
// CHECK-NEXT:   %s3 = stab.circuit %s2 : !stab.state<2 x !qcore.qubit, [Z0, X1]>
// CHECK-SAME:       -> !stab.state<2 x !qcore.qubit, [Z0, X1]>
// CHECK-NEXT:     with (%qa2, %qb2 : !qcore.qubit), (){
// CHECK-NEXT:       %ma = qref.measure<Z> (%qa2) -> i1
// CHECK-NEXT:       %mb = qref.measure<X> (%qb2) -> i1
// CHECK-NEXT:       stab.yield [%mb, %ma : i1, i1]
// CHECK-NEXT:     } [<+:1>{I -> Z0}, <+:0>{I -> X1}, <+:1>{Z0 -> I}, <+:0>{X1 -> I}]
// CHECK-NEXT: }
