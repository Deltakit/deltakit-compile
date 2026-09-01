// RUN: deltakit_compile compile-passes --test-mode %s -p generate-flows -O %t && filecheck %s --input-file %t

// Tests that generate-flows is able to propagate flow information through qstruct.parallel ops.

builtin.module {
  // Two disjoint sequences of circuit ops in parallel
  %a, %b = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %s0 = stab.state.make(%a : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
  %t0 = stab.state.make(%b : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>

  %s1, %t1 = qstruct.parallel<TOP> -> !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []> {
    %s1_in = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
      with (%qa : !qcore.qubit), () {
        qref.reset<X> (%qa)
        stab.yield []
      }
    qstruct.yield %s1_in : !stab.state<1 x !qcore.qubit, []>
  } {
    %t1_in = stab.circuit %t0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
      with (%qb : !qcore.qubit), () {
        qref.reset<Z> (%qb)
        stab.yield []
      }
    qstruct.yield %t1_in : !stab.state<1 x !qcore.qubit, []>
  }

  // Passing through a parallel region without a circuit
  %s2, %t2 = qstruct.parallel<TOP> -> !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []> {
    qstruct.yield %s1 : !stab.state<1 x !qcore.qubit, []>
  } {
    qstruct.yield %t1 : !stab.state<1 x !qcore.qubit, []>
  }

  %s3, %t3 = qstruct.parallel<BOTTOM> -> !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []> {
    %s3_in = stab.circuit %s2 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
      with (%qa2 : !qcore.qubit), () {
        %ma = qstruct.parallel<TOP> -> i1 {
          %inner_ma = qref.measure<X> (%qa2) -> i1
          qstruct.yield %inner_ma : i1
        }
        stab.yield []
      }
    qstruct.yield %s3_in : !stab.state<1 x !qcore.qubit, []>
  } {
    %t3_in = stab.circuit %t2 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
      with (%qb2 : !qcore.qubit), () {
        %mb = qref.measure<Z> (%qb2) -> i1
        stab.yield []
      }
    qstruct.yield %t3_in : !stab.state<1 x !qcore.qubit, []>
  }
}

// CHECK:      builtin.module {
// CHECK-NEXT:   %a, %b = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %s0 = stab.state.make(%a : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:   %t0 = stab.state.make(%b : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:   %s1, %t1 = qstruct.parallel<TOP> -> !stab.state<1 x !qcore.qubit, [X0]>, !stab.state<1 x !qcore.qubit, [Z0]> {
// CHECK-NEXT:     %s1_in = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, [X0]>
// CHECK-NEXT:       with (%qa : !qcore.qubit), (){
// CHECK-NEXT:         qref.reset<X> (%qa)
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       } [<+:>{I -> X0}]
// CHECK-NEXT:     qstruct.yield %s1_in_1 : !stab.state<1 x !qcore.qubit, [X0]>
// CHECK-NEXT:   } {
// CHECK-NEXT:     %t1_in = stab.circuit %t0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:       with (%qb : !qcore.qubit), (){
// CHECK-NEXT:         qref.reset<Z> (%qb)
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       } [<+:>{I -> Z0}]
// CHECK-NEXT:     qstruct.yield %t1_in_1 : !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:   }
// CHECK-NEXT:   %s2, %t2 = qstruct.parallel<TOP> -> !stab.state<1 x !qcore.qubit, [X0]>, !stab.state<1 x !qcore.qubit, [Z0]> {
// CHECK-NEXT:     qstruct.yield %s1_1 : !stab.state<1 x !qcore.qubit, [X0]>
// CHECK-NEXT:   } {
// CHECK-NEXT:     qstruct.yield %t1_1 : !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:   }
// CHECK-NEXT:   %s3, %t3 = qstruct.parallel<BOTTOM> -> !stab.state<1 x !qcore.qubit, [X0]>, !stab.state<1 x !qcore.qubit, [Z0]> {
// CHECK-NEXT:     %s3_in = stab.circuit %s2 : !stab.state<1 x !qcore.qubit, [X0]> -> !stab.state<1 x !qcore.qubit, [X0]>
// CHECK-NEXT:       with (%qa2 : !qcore.qubit), (){
// CHECK-NEXT:         %ma = qstruct.parallel<TOP> -> i1 {
// CHECK-NEXT:           %inner_ma = qref.measure<X> (%qa2) -> i1
// CHECK-NEXT:           qstruct.yield %inner_ma : i1
// CHECK-NEXT:         }
// CHECK-NEXT:         stab.yield [%ma : i1]
// CHECK-NEXT:       } [<+:0>{I -> X0}, <+:0>{X0 -> I}]
// CHECK-NEXT:     qstruct.yield %s3_in_1 : !stab.state<1 x !qcore.qubit, [X0]>
// CHECK-NEXT:   } {
// CHECK-NEXT:     %t3_in = stab.circuit %t2 : !stab.state<1 x !qcore.qubit, [Z0]> -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:       with (%qb2 : !qcore.qubit), (){
// CHECK-NEXT:         %mb = qref.measure<Z> (%qb2) -> i1
// CHECK-NEXT:         stab.yield [%mb : i1]
// CHECK-NEXT:       } [<+:0>{I -> Z0}, <+:0>{Z0 -> I}]
// CHECK-NEXT:     qstruct.yield %t3_in_1 : !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:   }
// CHECK-NEXT: }

// ----

builtin.module {
  // Parallel inside circuit, with some qubits not used in some parallels
  %a, %b = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %s0 = stab.state.make(%a, %b : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>

  %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, []>
    with (%qa, %qb : !qcore.qubit), () {
      qstruct.parallel<BOTTOM> -> {
        qref.reset<X> (%qa)
        qstruct.yield
      } {
        qref.reset<X> (%qb)
        qstruct.yield
      }
      qstruct.parallel<TOP> -> {
        qref.gate<#qcore.gate.h> (%qa)
        qstruct.yield
      } {
        qstruct.yield
      }
      qstruct.parallel<BOTTOM> -> {
        %m1 = qref.measure<Z> (%qa) -> i1
        qstruct.yield
      } {
        %m2 = qref.measure<X> (%qb) -> i1
        qstruct.yield
      }
      stab.yield []
    }
}

// CHECK:      builtin.module {
// CHECK-NEXT:   %a, %b = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %s0 = stab.state.make(%a, %b : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [Z0, X1]>
// CHECK-NEXT:     with (%qa, %qb : !qcore.qubit), (){
// CHECK-NEXT:       qstruct.parallel<BOTTOM> -> {
// CHECK-NEXT:         qref.reset<X> (%qa)
// CHECK-NEXT:         qstruct.yield
// CHECK-NEXT:       } {
// CHECK-NEXT:         qref.reset<X> (%qb)
// CHECK-NEXT:         qstruct.yield
// CHECK-NEXT:       }
// CHECK-NEXT:       qstruct.parallel<TOP> -> {
// CHECK-NEXT:         qref.gate<#qcore.gate.h> (%qa)
// CHECK-NEXT:         qstruct.yield
// CHECK-NEXT:       } {
// CHECK-NEXT:         qstruct.yield
// CHECK-NEXT:       }
// CHECK-NEXT:       %0, %1 = qstruct.parallel<BOTTOM> -> i1, i1 {
// CHECK-NEXT:         %m1 = qref.measure<Z> (%qa) -> i1
// CHECK-NEXT:         qstruct.yield %m1 : i1
// CHECK-NEXT:       } {
// CHECK-NEXT:         %m2 = qref.measure<X> (%qb) -> i1
// CHECK-NEXT:         qstruct.yield %m2 : i1
// CHECK-NEXT:       }
// CHECK-DAG:        [[D0:%[0-9]+]] = qec.detector(%0)
// CHECK-DAG:        [[D1:%[0-9]+]] = qec.detector(%1)
// CHECK-NEXT:       stab.yield [%0, %1 : i1, i1]
// CHECK-NEXT:     } [<+:>{I -> Z0}, <+:>{I -> X1}]
// CHECK-NEXT: }
