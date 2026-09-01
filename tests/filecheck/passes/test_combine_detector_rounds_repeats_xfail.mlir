// RUN: deltakit_compile compile-passes -t %s -p combine-detector-rounds -O %t && filecheck %s --input-file %t
// XFAIL: *

// Detector rounds formed from repeats with parallel measurements
builtin.module {
  %q, %q_1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %0, %1 = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit)
     -> !qcore.qubit, !qcore.qubit {
  ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit):
    %mpr0_q0, %mpr0_q1 = qstruct.parallel<TOP> -> i1, i1 {
        %mr0_q0 = qref.measure<Z> (%qb0) -> i1
        qstruct.yield %mr0_q0 : i1
    } {
        %mr0_q1 = qref.measure<Z> (%qb1) -> i1
        qstruct.yield %mr0_q1 : i1
    }
    %mpr5_q0, %mpr5_q1 = qstruct.repeat<5> (%mpr0_q0, %mpr0_q1 : i1, i1) -> i1, i1 {
      ^bb1(%mprn_q0: i1, %mprn_q1: i1):
          %mprn1_q0, %mprn1_q1 = qref.measure<Z> (%qb0, %qb1) -> i1, i1
          %drn_q0 = qec.detector(%mprn_q0, %mprn1_q0)
          qec.detector_round(%drn_q0)
          %drn_q1 = qec.detector(%mprn_q1, %mprn1_q1)
          qec.detector_round(%drn_q1)
          qstruct.yield %mprn1_q0, %mprn1_q1 : i1, i1
    }
    qstruct.yield %qb0, %qb1 : !qcore.qubit, !qcore.qubit
  }
}

// CHECK:       builtin.module {
// CHECK-NEXT:    %q, %q_1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    %0, %1 = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit):
// CHECK-NEXT:      %mpr0_q0, %mpr0_q1 = qstruct.parallel<TOP> -> i1, i1 {
// CHECK-NEXT:          %mr0_q0 = qref.measure<Z> (%qb0) -> i1
// CHECK-NEXT:          qstruct.yield %mr0_q0 : i1
// CHECK-NEXT:      } {
// CHECK-NEXT:          %mr0_q1 = qref.measure<Z> (%qb1) -> i1
// CHECK-NEXT:          qstruct.yield %mr0_q1 : i1
// CHECK-NEXT:      }
// CHECK-NEXT:      %mpr5_q0, %mpr5_q1 = qstruct.repeat<5> (%mpr0_q0, %mpr0_q1 : i1, i1) -> i1, i1 {
// CHECK-NEXT:        ^bb1(%mprn_q0: i1, %mprn_q1: i1):
// CHECK-NEXT:            %mprn1_q0, %mprn1_q1 = qref.measure<Z> (%qb0, %qb1) -> i1, i1
// CHECK-NEXT:            %drn_q0 = qec.detector(%mprn_q0, %mprn1_q0)
// CHECK-NEXT:            %drn_q1 = qec.detector(%mprn_q1, %mprn1_q1)
// CHECK-NEXT:            qec.detector_round(%drn_q0, %drn_q1)
// CHECK-NEXT:            qstruct.yield %mprn1_q0, %mprn1_q1 : i1, i1
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield %qb0, %qb1 : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }
