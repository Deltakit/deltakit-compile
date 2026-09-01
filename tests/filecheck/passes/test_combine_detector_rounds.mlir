// RUN: deltakit_compile compile-passes -t %s -p combine-detector-rounds -O %t && filecheck %s --input-file %t

// broadcast measurement

builtin.module {
  %q, %q_1, %q_2, %q_3 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  %0, %1, %2, %3 = qstruct.circuit(%q, %q_1, %q_2, %q_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit, %qb2: !qcore.qubit, %qb3: !qcore.qubit):
    %m2, %m3, %m4, %m5 = qref.measure<Z> (%qb0, %qb1, %qb2, %qb3) -> i1, i1, i1, i1
    %d0 = qec.detector(%m2, %m3)
    qec.detector_round(%d0)
    %d1 = qec.detector(%m4, %m5)
    qec.detector_round(%d1)
    qstruct.yield %qb0, %qb1, %qb2, %qb3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

//CHECK-NEXT:   builtin.module {
//CHECK-NEXT:     %q, %q_1, %q_2, %q_3 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
//CHECK-NEXT:     %0, %1, %2, %3 = qstruct.circuit(%q, %q_1, %q_2, %q_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
//CHECK-NEXT:     ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit, %qb2: !qcore.qubit, %qb3: !qcore.qubit):
//CHECK-NEXT:       %m2, %m3, %m4, %m5 = qref.measure<Z> (%qb0, %qb1, %qb2, %qb3) -> i1, i1, i1, i1
//CHECK-NEXT:       %d0 = qec.detector(%m2, %m3)
//CHECK-NEXT:       %d1 = qec.detector(%m4, %m5)
//CHECK-NEXT:       qec.detector_round(%d0, %d1)
//CHECK-NEXT:       qstruct.yield %qb0, %qb1, %qb2, %qb3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
//CHECK-NEXT:     }
//CHECK-NEXT:   }

// ----
// CHECK: ----

// single parallel

builtin.module {
  %q, %q_1, %q_2, %q_3 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  %0, %1, %2, %3 = qstruct.circuit(%q, %q_1, %q_2, %q_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit, %qb2: !qcore.qubit, %qb3: !qcore.qubit):
    %m2, %m3, %m4, %m5 = qstruct.parallel<TOP> -> i1, i1, i1, i1 {
      %m0, %m1 = qref.measure<Z> (%qb0, %qb1) -> i1, i1
      qstruct.yield %m0, %m1 : i1, i1
    } {
      %m1_1, %m2 = qref.measure<Z> (%qb2, %qb3) -> i1, i1
      qstruct.yield %m1_1, %m2 : i1, i1
    }
    %d0 = qec.detector(%m2, %m3)
    qec.detector_round(%d0)
    %d1 = qec.detector(%m4, %m5)
    qec.detector_round(%d1)
    qstruct.yield %qb0, %qb1, %qb2, %qb3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

//CHECK-NEXT:   builtin.module {
//CHECK-NEXT:     %q, %q_1, %q_2, %q_3 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
//CHECK-NEXT:     %0, %1, %2, %3 = qstruct.circuit(%q, %q_1, %q_2, %q_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
//CHECK-NEXT:     ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit, %qb2: !qcore.qubit, %qb3: !qcore.qubit):
//CHECK-NEXT:       %m2, %m3, %m4, %m5 = qstruct.parallel<TOP> -> i1, i1, i1, i1 {
//CHECK-NEXT:         %m0, %m1 = qref.measure<Z> (%qb0, %qb1) -> i1, i1
//CHECK-NEXT:         qstruct.yield %m0, %m1 : i1, i1
//CHECK-NEXT:       } {
//CHECK-NEXT:         %m1_1, %m2_1 = qref.measure<Z> (%qb2, %qb3) -> i1, i1
//CHECK-NEXT:         qstruct.yield %m1_1, %m2_1 : i1, i1
//CHECK-NEXT:       }
//CHECK-NEXT:       %d0 = qec.detector(%m2, %m3)
//CHECK-NEXT:       %d1 = qec.detector(%m4, %m5)
//CHECK-NEXT:       qec.detector_round(%d0, %d1)
//CHECK-NEXT:       qstruct.yield %qb0, %qb1, %qb2, %qb3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
//CHECK-NEXT:     }
//CHECK-NEXT:   }

// ----
// CHECK: ----

builtin.module {
  %q, %q_1, %q_2, %q_3 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  %0, %1, %2, %3 = qstruct.circuit(%q, %q_1, %q_2, %q_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit, %qb2: !qcore.qubit, %qb3: !qcore.qubit):
    %m2, %m3, %m4, %m5 = qstruct.parallel<TOP> -> i1, i1, i1, i1 {
      %m0, %m1 = qref.measure<Z> (%qb0, %qb1) -> i1, i1
      qstruct.yield %m0, %m1 : i1, i1
    } {
      %m1_1, %m2 = qref.measure<Z> (%qb2, %qb3) -> i1, i1
      qstruct.yield %m1_1, %m2 : i1, i1
    }
    %4, %5, %6 = qstruct.parallel<TOP> -> !qec.detector_ref, i1, !qec.detector_ref {
      %d0 = qec.detector(%m2, %m3)
      qec.detector_round(%d0)
      qstruct.yield %d0, %m2: !qec.detector_ref, i1
    } {
       %d1 = qec.detector(%m4, %m5)
       qec.detector_round(%d1)
       qstruct.yield %d1: !qec.detector_ref
    }
    qstruct.yield %qb0, %qb1, %qb2, %qb3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

//CHECK-NEXT:   builtin.module {
//CHECK-NEXT:     %q, %q_1, %q_2, %q_3 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
//CHECK-NEXT:     %0, %1, %2, %3 = qstruct.circuit(%q, %q_1, %q_2, %q_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
//CHECK-NEXT:     ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit, %qb2: !qcore.qubit, %qb3: !qcore.qubit):
//CHECK-NEXT:       %m2, %m3, %m4, %m5 = qstruct.parallel<TOP> -> i1, i1, i1, i1 {
//CHECK-NEXT:         %m0, %m1 = qref.measure<Z> (%qb0, %qb1) -> i1, i1
//CHECK-NEXT:         qstruct.yield %m0, %m1 : i1, i1
//CHECK-NEXT:       } {
//CHECK-NEXT:         %m1_1, %m2_1 = qref.measure<Z> (%qb2, %qb3) -> i1, i1
//CHECK-NEXT:         qstruct.yield %m1_1, %m2_1 : i1, i1
//CHECK-NEXT:       }
//CHECK-NEXT:       %4, %5, %6 = qstruct.parallel<TOP> -> !qec.detector_ref, i1, !qec.detector_ref {
//CHECK-NEXT:         %d0 = qec.detector(%m2, %m3)
//CHECK-NEXT:         qstruct.yield %d0, %m2 : !qec.detector_ref, i1
//CHECK-NEXT:       } {
//CHECK-NEXT:         %d1 = qec.detector(%m4, %m5)
//CHECK-NEXT:         qstruct.yield %d1 : !qec.detector_ref
//CHECK-NEXT:       }
//CHECK-NEXT:       qec.detector_round(%4, %6)
//CHECK-NEXT:       qstruct.yield %qb0, %qb1, %qb2, %qb3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
//CHECK-NEXT:     }
//CHECK-NEXT:   }

// ----
// CHECK: ----

// 2 level nested parallel

builtin.module {
  %q, %q_1, %q_2, %q_3, %q_4, %q_5 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  %0, %1, %2, %3, %4, %5 = qstruct.circuit(%q, %q_1, %q_2, %q_3, %q_4, %q_5 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit)
     -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit, %qb2: !qcore.qubit, %qb3: !qcore.qubit, %qb4: !qcore.qubit, %qb5: !qcore.qubit):
    // parallel
    %m2, %m3 = qstruct.parallel<TOP> -> i1, i1 {
      %m00 = qstruct.parallel<TOP> -> i1 {
          %m0 = qref.measure<Z> (%qb1) -> i1
          qstruct.yield %m0 : i1
      }
      qstruct.yield %m00 : i1
    } {
       %m01 = qstruct.parallel<TOP> -> i1 {
          %m0 = qref.measure<Z> (%qb0) -> i1
          qstruct.yield %m0 : i1
      }
      qstruct.yield %m01 : i1
    }
    %d0 = qec.detector(%m2)
    qec.detector_round(%d0)
    %d1 = qec.detector(%m3)
    qec.detector_round(%d1)
    qstruct.yield %qb0, %qb1, %qb2, %qb3, %qb4, %qb5 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

//CHECK-NEXT:   builtin.module {
//CHECK-NEXT:     %q, %q_1, %q_2, %q_3, %q_4, %q_5 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
//CHECK-NEXT:     %0, %1, %2, %3, %4, %5 = qstruct.circuit(%q, %q_1, %q_2, %q_3, %q_4, %q_5 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
//CHECK-NEXT:     ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit, %qb2: !qcore.qubit, %qb3: !qcore.qubit, %qb4: !qcore.qubit, %qb5: !qcore.qubit):
//CHECK-NEXT:       %m2, %m3 = qstruct.parallel<TOP> -> i1, i1 {
//CHECK-NEXT:         %m00 = qstruct.parallel<TOP> -> i1 {
//CHECK-NEXT:           %m0 = qref.measure<Z> (%qb1) -> i1
//CHECK-NEXT:           qstruct.yield %m0 : i1
//CHECK-NEXT:         }
//CHECK-NEXT:         qstruct.yield %m00 : i1
//CHECK-NEXT:       } {
//CHECK-NEXT:         %m01 = qstruct.parallel<TOP> -> i1 {
//CHECK-NEXT:           %m0_1 = qref.measure<Z> (%qb0) -> i1
//CHECK-NEXT:           qstruct.yield %m0_1 : i1
//CHECK-NEXT:         }
//CHECK-NEXT:         qstruct.yield %m01 : i1
//CHECK-NEXT:       }
//CHECK-NEXT:       %d0 = qec.detector(%m2)
//CHECK-NEXT:       %d1 = qec.detector(%m3)
//CHECK-NEXT:       qec.detector_round(%d0, %d1)
//CHECK-NEXT:       qstruct.yield %qb0, %qb1, %qb2, %qb3, %qb4, %qb5 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
//CHECK-NEXT:     }
//CHECK-NEXT:   }

// ----
// CHECK: ----

// 2 level nested parallel but one parallel has extra op so can't combine

builtin.module {
  %q, %q_1, %q_2, %q_3, %q_4, %q_5 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  %0, %1, %2, %3, %4, %5 = qstruct.circuit(%q, %q_1, %q_2, %q_3, %q_4, %q_5 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit)
     -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit, %qb2: !qcore.qubit, %qb3: !qcore.qubit, %qb4: !qcore.qubit, %qb5: !qcore.qubit):
    // parallel
    %m2, %m3 = qstruct.parallel<TOP> -> i1, i1 {
      %m00 = qstruct.parallel<TOP> -> i1 {
          %m0 = qref.measure<Z> (%qb1) -> i1
          arith.constant 0 : i1
          qstruct.yield %m0 : i1
      }
      qstruct.yield %m00 : i1
    } {
       %m01 = qstruct.parallel<TOP> -> i1 {
          %m0 = qref.measure<Z> (%qb0) -> i1
          qstruct.yield %m0 : i1
      }
      qstruct.yield %m01 : i1
    }
    %d0 = qec.detector(%m2)
    qec.detector_round(%d0)
    %d1 = qec.detector(%m3)
    qec.detector_round(%d1)
    qstruct.yield %qb0, %qb1, %qb2, %qb3, %qb4, %qb5 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

//CHECK-NEXT:   builtin.module {
//CHECK-NEXT:     %q, %q_1, %q_2, %q_3, %q_4, %q_5 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
//CHECK-NEXT:     %0, %1, %2, %3, %4, %5 = qstruct.circuit(%q, %q_1, %q_2, %q_3, %q_4, %q_5 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
//CHECK-NEXT:     ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit, %qb2: !qcore.qubit, %qb3: !qcore.qubit, %qb4: !qcore.qubit, %qb5: !qcore.qubit):
//CHECK-NEXT:       %m2, %m3 = qstruct.parallel<TOP> -> i1, i1 {
//CHECK-NEXT:         %m00 = qstruct.parallel<TOP> -> i1 {
//CHECK-NEXT:           %m0 = qref.measure<Z> (%qb1) -> i1
//CHECK-NEXT:           %6 = arith.constant false
//CHECK-NEXT:           qstruct.yield %m0 : i1
//CHECK-NEXT:         }
//CHECK-NEXT:         qstruct.yield %m00 : i1
//CHECK-NEXT:       } {
//CHECK-NEXT:         %m01 = qstruct.parallel<TOP> -> i1 {
//CHECK-NEXT:           %m0_1 = qref.measure<Z> (%qb0) -> i1
//CHECK-NEXT:           qstruct.yield %m0_1 : i1
//CHECK-NEXT:         }
//CHECK-NEXT:         qstruct.yield %m01 : i1
//CHECK-NEXT:       }
//CHECK-NEXT:       %d0 = qec.detector(%m2)
//CHECK-NEXT:       qec.detector_round(%d0)
//CHECK-NEXT:       %d1 = qec.detector(%m3)
//CHECK-NEXT:       qec.detector_round(%d1)
//CHECK-NEXT:       qstruct.yield %qb0, %qb1, %qb2, %qb3, %qb4, %qb5 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
//CHECK-NEXT:     }
//CHECK-NEXT:   }
// ----
// CHECK: ----

// 3 level nested parallel

builtin.module {
  %q, %q_1, %q_2, %q_3, %q_4, %q_5 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  %0, %1, %2, %3, %4, %5 = qstruct.circuit(%q, %q_1, %q_2, %q_3, %q_4, %q_5 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit)
     -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit, %qb2: !qcore.qubit, %qb3: !qcore.qubit, %qb4: !qcore.qubit, %qb5: !qcore.qubit):
    // parallel
    %m000, %m001, %m002, %m003, %m004, %m005 = qstruct.parallel<TOP> -> i1, i1, i1, i1, i1, i1 {
          %m0 = qref.measure<Z> (%qb0) -> i1
          qstruct.yield %m0 : i1
    } {
        %m00, %m01, %m02, %m03, %m04 = qstruct.parallel<TOP> -> i1, i1, i1, i1, i1 {
          %m0, %m1 = qref.measure<Z> (%qb4, %qb5) -> i1, i1
          qstruct.yield %m0, %m1 : i1, i1
      } {
        %m1, %m2 = qref.measure<Z> (%qb2, %qb3) -> i1, i1
        qstruct.yield %m1, %m2 : i1, i1
      } {
        %m05 = qstruct.parallel<TOP> -> i1 {
          %m0 = qref.measure<Z> (%qb1) -> i1
          qstruct.yield %m0 : i1
      }
      qstruct.yield %m05 : i1
      }
      qstruct.yield %m00, %m01, %m02, %m03, %m04 : i1, i1, i1, i1, i1
    }
    %d0 = qec.detector(%m000)
    qec.detector_round(%d0)
    %d1 = qec.detector(%m001)
    qec.detector_round(%d1)
    %d2 = qec.detector(%m002)
    qec.detector_round(%d2)
    %d3 = qec.detector(%m003)
    qec.detector_round(%d3)
    %d4 = qec.detector(%m004)
    qec.detector_round(%d4)
    %d5 = qec.detector(%m005)
    qec.detector_round(%d5)
    qstruct.yield %qb0, %qb1, %qb2, %qb3, %qb4, %qb5 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

//CHECK-NEXT:   builtin.module {
//CHECK-NEXT:     %q, %q_1, %q_2, %q_3, %q_4, %q_5 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
//CHECK-NEXT:     %0, %1, %2, %3, %4, %5 = qstruct.circuit(%q, %q_1, %q_2, %q_3, %q_4, %q_5 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
//CHECK-NEXT:     ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit, %qb2: !qcore.qubit, %qb3: !qcore.qubit, %qb4: !qcore.qubit, %qb5: !qcore.qubit):
//CHECK-NEXT:       %m000, %m001, %m002, %m003, %m004, %m005 = qstruct.parallel<TOP> -> i1, i1, i1, i1, i1, i1 {
//CHECK-NEXT:         %m0 = qref.measure<Z> (%qb0) -> i1
//CHECK-NEXT:         qstruct.yield %m0 : i1
//CHECK-NEXT:       } {
//CHECK-NEXT:         %m00, %m01, %m02, %m03, %m04 = qstruct.parallel<TOP> -> i1, i1, i1, i1, i1 {
//CHECK-NEXT:           %m0_1, %m1 = qref.measure<Z> (%qb4, %qb5) -> i1, i1
//CHECK-NEXT:           qstruct.yield %m0_1, %m1 : i1, i1
//CHECK-NEXT:         } {
//CHECK-NEXT:           %m1_1, %m2 = qref.measure<Z> (%qb2, %qb3) -> i1, i1
//CHECK-NEXT:           qstruct.yield %m1_1, %m2 : i1, i1
//CHECK-NEXT:         } {
//CHECK-NEXT:           %m05 = qstruct.parallel<TOP> -> i1 {
//CHECK-NEXT:             %m0_2 = qref.measure<Z> (%qb1) -> i1
//CHECK-NEXT:             qstruct.yield %m0_2 : i1
//CHECK-NEXT:           }
//CHECK-NEXT:           qstruct.yield %m05 : i1
//CHECK-NEXT:         }
//CHECK-NEXT:         qstruct.yield %m00, %m01, %m02, %m03, %m04 : i1, i1, i1, i1, i1
//CHECK-NEXT:       }
//CHECK-NEXT:       %d0 = qec.detector(%m000)
//CHECK-NEXT:       %d1 = qec.detector(%m001)
//CHECK-NEXT:       %d2 = qec.detector(%m002)
//CHECK-NEXT:       %d3 = qec.detector(%m003)
//CHECK-NEXT:       %d4 = qec.detector(%m004)
//CHECK-NEXT:       %d5 = qec.detector(%m005)
//CHECK-NEXT:       qec.detector_round(%d0, %d1, %d2, %d3, %d4, %d5)
//CHECK-NEXT:       qstruct.yield %qb0, %qb1, %qb2, %qb3, %qb4, %qb5 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
//CHECK-NEXT:     }
//CHECK-NEXT:   }

// ----
// CHECK: ----

// Detector round in a loop should not be combined outside of the loop

builtin.module {
  %q, %q_1, %q_2, %q_3 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit

  %0, %1, %2, %3 = qstruct.circuit(%q, %q_1, %q_2, %q_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit)
     -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit, %qb2: !qcore.qubit, %qb3: !qcore.qubit):
    // parallel
    qstruct.parallel<TOP> -> {
        qstruct.repeat<5> -> {
          %m0, %m1 = qref.measure<Z> (%qb0, %qb1) -> i1, i1
          %d0 = qec.detector(%m0, %m1)
          qec.detector_round(%d0)
          qstruct.yield
        }
        qstruct.yield
    } {
        %m1, %m2 = qref.measure<Z> (%qb2, %qb3) -> i1, i1
        %d1 = qec.detector(%m1, %m2)
        qec.detector_round(%d1)
        qstruct.yield
    }
    qstruct.yield %qb0, %qb1, %qb2, %qb3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

//CHECK-NEXT:   builtin.module {
//CHECK-NEXT:     %q, %q_1, %q_2, %q_3 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
//CHECK-NEXT:     %0, %1, %2, %3 = qstruct.circuit(%q, %q_1, %q_2, %q_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
//CHECK-NEXT:     ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit, %qb2: !qcore.qubit, %qb3: !qcore.qubit):
//CHECK-NEXT:       qstruct.parallel<TOP> -> {
//CHECK-NEXT:         qstruct.repeat<5> () -> {
//CHECK-NEXT:           %m0, %m1 = qref.measure<Z> (%qb0, %qb1) -> i1, i1
//CHECK-NEXT:           %d0 = qec.detector(%m0, %m1)
//CHECK-NEXT:           qec.detector_round(%d0)
//CHECK-NEXT:           qstruct.yield
//CHECK-NEXT:         }
//CHECK-NEXT:         qstruct.yield
//CHECK-NEXT:       } {
//CHECK-NEXT:         %m1_1, %m2 = qref.measure<Z> (%qb2, %qb3) -> i1, i1
//CHECK-NEXT:         %d1 = qec.detector(%m1_1, %m2)
//CHECK-NEXT:         qec.detector_round(%d1)
//CHECK-NEXT:         qstruct.yield
//CHECK-NEXT:       }
//CHECK-NEXT:       qstruct.yield %qb0, %qb1, %qb2, %qb3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
//CHECK-NEXT:     }
//CHECK-NEXT:   }

// ----
// CHECK: ----

// Detector rounds formed from consecutive parallel measurements
builtin.module {
  %q, %q_1, %q_2, %q_3 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  %0, %1, %2, %3 = qstruct.circuit(%q, %q_1, %q_2, %q_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit)
     -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit, %qb2: !qcore.qubit, %qb3: !qcore.qubit):
    // parallel
    %mpr0_q0, %mpr0_q1, %mpr0_q2, %mpr0_q3 = qstruct.parallel<TOP> -> i1, i1, i1, i1 {
        %mr0_q0, %mr0_q1 = qref.measure<Z> (%qb0, %qb1) -> i1, i1
        qstruct.yield %mr0_q0, %mr0_q1 : i1, i1
    } {
        %mr0_q2, %mr0_q3 = qref.measure<Z> (%qb2, %qb3) -> i1, i1
        qstruct.yield %mr0_q2, %mr0_q3 : i1, i1
    }
    %mpr1_q0, %mpr1_q1, %mpr1_q2, %mpr1_q3 = qstruct.parallel<TOP> -> i1, i1, i1, i1 {
        %mr1_q0, %mr1_q1 = qref.measure<Z> (%qb0, %qb1) -> i1, i1
        qstruct.yield %mr1_q0, %mr1_q1 : i1, i1
    } {
        %mr1_q2, %mr1_q3 = qref.measure<Z> (%qb2, %qb3) -> i1, i1
        qstruct.yield %mr1_q2, %mr1_q3 : i1, i1
    }
    %dr0_q0 = qec.detector(%mpr0_q0, %mpr1_q0)
    %dr0_q1 = qec.detector(%mpr0_q1, %mpr1_q1)
    qec.detector_round(%dr0_q0, %dr0_q1)
    %dr0_q2 = qec.detector(%mpr0_q2, %mpr1_q2)
    %dr0_q3 = qec.detector(%mpr0_q3, %mpr1_q3)
    qec.detector_round(%dr0_q2, %dr0_q3)
    %mpr2_q0, %mpr2_q1, %mpr2_q2, %mpr2_q3 = qstruct.parallel<TOP> -> i1, i1, i1, i1 {
        %mr2_q0, %mr2_q1 = qref.measure<Z> (%qb0, %qb1) -> i1, i1
        qstruct.yield %mr2_q0, %mr2_q1 : i1, i1
    } {
        %mr2_q2, %mr2_q3 = qref.measure<Z> (%qb2, %qb3) -> i1, i1
        qstruct.yield %mr2_q2, %mr2_q3 : i1, i1
    }
    %dr1_q0 = qec.detector(%mpr1_q0, %mpr2_q0)
    %dr1_q1 = qec.detector(%mpr1_q1, %mpr2_q1)
    qec.detector_round(%dr1_q0, %dr1_q1)
    %dr1_q2 = qec.detector(%mpr1_q2, %mpr2_q2)
    %dr1_q3 = qec.detector(%mpr1_q3, %mpr2_q3)
    qec.detector_round(%dr1_q2, %dr1_q3)
    qstruct.yield %qb0, %qb1, %qb2, %qb3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %q, %q_1, %q_2, %q_3 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    %0, %1, %2, %3 = qstruct.circuit(%q, %q_1, %q_2, %q_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit, %qb2: !qcore.qubit, %qb3: !qcore.qubit):
// CHECK-NEXT:      %mpr0_q0, %mpr0_q1, %mpr0_q2, %mpr0_q3 = qstruct.parallel<TOP> -> i1, i1, i1, i1 {
// CHECK-NEXT:          %mr0_q0, %mr0_q1 = qref.measure<Z> (%qb0, %qb1) -> i1, i1
// CHECK-NEXT:          qstruct.yield %mr0_q0, %mr0_q1 : i1, i1
// CHECK-NEXT:      } {
// CHECK-NEXT:          %mr0_q2, %mr0_q3 = qref.measure<Z> (%qb2, %qb3) -> i1, i1
// CHECK-NEXT:          qstruct.yield %mr0_q2, %mr0_q3 : i1, i1
// CHECK-NEXT:      }
// CHECK-NEXT:      %mpr1_q0, %mpr1_q1, %mpr1_q2, %mpr1_q3 = qstruct.parallel<TOP> -> i1, i1, i1, i1 {
// CHECK-NEXT:          %mr1_q0, %mr1_q1 = qref.measure<Z> (%qb0, %qb1) -> i1, i1
// CHECK-NEXT:          qstruct.yield %mr1_q0, %mr1_q1 : i1, i1
// CHECK-NEXT:      } {
// CHECK-NEXT:          %mr1_q2, %mr1_q3 = qref.measure<Z> (%qb2, %qb3) -> i1, i1
// CHECK-NEXT:          qstruct.yield %mr1_q2, %mr1_q3 : i1, i1
// CHECK-NEXT:      }
// CHECK-NEXT:      %dr0_q0 = qec.detector(%mpr0_q0, %mpr1_q0)
// CHECK-NEXT:      %dr0_q1 = qec.detector(%mpr0_q1, %mpr1_q1)
// CHECK-NEXT:      %dr0_q2 = qec.detector(%mpr0_q2, %mpr1_q2)
// CHECK-NEXT:      %dr0_q3 = qec.detector(%mpr0_q3, %mpr1_q3)
// CHECK-NEXT:      qec.detector_round(%dr0_q0, %dr0_q1, %dr0_q2, %dr0_q3)
// CHECK-NEXT:      %mpr2_q0, %mpr2_q1, %mpr2_q2, %mpr2_q3 = qstruct.parallel<TOP> -> i1, i1, i1, i1 {
// CHECK-NEXT:          %mr2_q0, %mr2_q1 = qref.measure<Z> (%qb0, %qb1) -> i1, i1
// CHECK-NEXT:          qstruct.yield %mr2_q0, %mr2_q1 : i1, i1
// CHECK-NEXT:      } {
// CHECK-NEXT:          %mr2_q2, %mr2_q3 = qref.measure<Z> (%qb2, %qb3) -> i1, i1
// CHECK-NEXT:          qstruct.yield %mr2_q2, %mr2_q3 : i1, i1
// CHECK-NEXT:      }
// CHECK-NEXT:      %dr1_q0 = qec.detector(%mpr1_q0, %mpr2_q0)
// CHECK-NEXT:      %dr1_q1 = qec.detector(%mpr1_q1, %mpr2_q1)
// CHECK-NEXT:      %dr1_q2 = qec.detector(%mpr1_q2, %mpr2_q2)
// CHECK-NEXT:      %dr1_q3 = qec.detector(%mpr1_q3, %mpr2_q3)
// CHECK-NEXT:      qec.detector_round(%dr1_q0, %dr1_q1, %dr1_q2, %dr1_q3)
// CHECK-NEXT:      qstruct.yield %qb0, %qb1, %qb2, %qb3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----
// CHECK: ----

// Check that unknown operation doesn't cause an error - nothing should change here

builtin.module {
  %q, %q_1, %q_2, %q_3 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  %0, %1, %2, %3 = qstruct.circuit(%q, %q_1, %q_2, %q_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit, %qb2: !qcore.qubit, %qb3: !qcore.qubit):
    %m2, %m3, %m4, %m5 = "test.op" (): () -> (i1, i1, i1, i1)
    %d0 = "test.op" (): () -> !qec.detector_ref
    qec.detector_round(%d0)
    %d1 = qec.detector(%m4, %m5)
    qec.detector_round(%d1)
    %d2 = qec.detector(%m2, %m3)
    qec.detector_round(%d2)
    qstruct.yield %qb0, %qb1, %qb2, %qb3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %q, %q_1, %q_2, %q_3 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    %0, %1, %2, %3 = qstruct.circuit(%q, %q_1, %q_2, %q_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit, %qb2: !qcore.qubit, %qb3: !qcore.qubit):
// CHECK-NEXT:      %m2, %m3, %m4, %m5 = "test.op"() : () -> (i1, i1, i1, i1)
// CHECK-NEXT:      %d0 = "test.op"() : () -> !qec.detector_ref
// CHECK-NEXT:      qec.detector_round(%d0)
// CHECK-NEXT:      %d1 = qec.detector(%m4, %m5)
// CHECK-NEXT:      qec.detector_round(%d1)
// CHECK-NEXT:      %d2 = qec.detector(%m2, %m3)
// CHECK-NEXT:      qec.detector_round(%d2)
// CHECK-NEXT:      qstruct.yield %qb0, %qb1, %qb2, %qb3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }
