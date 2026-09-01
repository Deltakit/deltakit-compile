// RUN: deltakit_compile compile-passes -t %s -p realign-qec-detectors -O %t && filecheck %s --input-file %t

// no measurements: empty detector is not moved
builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %0 = qstruct.circuit(%q : !qcore.qubit) -> !qcore.qubit {
  ^bb0(%qb: !qcore.qubit):
    %d = qec.detector()
    qstruct.yield %qb : !qcore.qubit
  }
}

//CHECK-NEXT: builtin.module {
//CHECK-NEXT:   %q = qcore.alloc_qubit -> !qcore.qubit
//CHECK-NEXT:   %0 = qstruct.circuit(%q : !qcore.qubit) -> !qcore.qubit {
//CHECK-NEXT:   ^bb0(%qb: !qcore.qubit):
//CHECK-NEXT:     %d = qec.detector()
//CHECK-NEXT:     qstruct.yield %qb : !qcore.qubit
//CHECK-NEXT:   }
//CHECK-NEXT: }

// ----
// CHECK: ----

// already in position: detector directly after its round is not moved
builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %0 = qstruct.circuit(%q : !qcore.qubit) -> !qcore.qubit {
  ^bb0(%qb: !qcore.qubit):
    %m = qref.measure<Z> (%qb) -> i1
    qec.measurement_round(%m : i1)
    %d = qec.detector(%m)
    qstruct.yield %qb : !qcore.qubit
  }
}

//CHECK-NEXT: builtin.module {
//CHECK-NEXT:   %q = qcore.alloc_qubit -> !qcore.qubit
//CHECK-NEXT:   %0 = qstruct.circuit(%q : !qcore.qubit) -> !qcore.qubit {
//CHECK-NEXT:   ^bb0(%qb: !qcore.qubit):
//CHECK-NEXT:     %m = qref.measure<Z> (%qb) -> i1
//CHECK-NEXT:     qec.measurement_round(%m : i1)
//CHECK-NEXT:     %d = qec.detector(%m)
//CHECK-NEXT:     qstruct.yield %qb : !qcore.qubit
//CHECK-NEXT:   }
//CHECK-NEXT: }

// ----
// CHECK: ----

// detector before its round: moves to just after it
builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %0 = qstruct.circuit(%q : !qcore.qubit) -> !qcore.qubit {
  ^bb0(%qb: !qcore.qubit):

//CHECK-NEXT: builtin.module {
//CHECK-NEXT:   %q = qcore.alloc_qubit -> !qcore.qubit
//CHECK-NEXT:   %0 = qstruct.circuit(%q : !qcore.qubit) -> !qcore.qubit {
//CHECK-NEXT:   ^bb0(%qb: !qcore.qubit):

    %m = qref.measure<Z> (%qb) -> i1
    qec.measurement_round(%m : i1)
    "test.op"():() -> ()
    %d = qec.detector(%m)
    qstruct.yield %qb : !qcore.qubit
  }
}

//CHECK-NEXT:     %m = qref.measure<Z> (%qb) -> i1
//CHECK-NEXT:     qec.measurement_round(%m : i1)
//CHECK-NEXT:     %d = qec.detector(%m)
//CHECK-NEXT:     "test.op"() : () -> ()
//CHECK-NEXT:     qstruct.yield %qb : !qcore.qubit
//CHECK-NEXT:   }
//CHECK-NEXT: }

// ----
// CHECK: ----

// detector between two rounds: moves after the last (highest-ID) round
builtin.module {
  %q, %q_1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %0, %1 = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
  ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit):

//CHECK-NEXT: builtin.module {
//CHECK-NEXT:   %q, %q_1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
//CHECK-NEXT:   %0, %1 = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
//CHECK-NEXT:   ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit):

    %m0 = qref.measure<Z> (%qb0) -> i1
    %m1 = qref.measure<Z> (%qb1) -> i1
    qec.measurement_round(%m0 : i1)
    %d = qec.detector(%m0, %m1)
    qec.measurement_round(%m1 : i1)
    qstruct.yield %qb0, %qb1 : !qcore.qubit, !qcore.qubit
  }
}

//CHECK-NEXT:     %m0 = qref.measure<Z> (%qb0) -> i1
//CHECK-NEXT:     %m1 = qref.measure<Z> (%qb1) -> i1
//CHECK-NEXT:     qec.measurement_round(%m0 : i1)
//CHECK-NEXT:     qec.measurement_round(%m1 : i1)
//CHECK-NEXT:     %d = qec.detector(%m0, %m1)
//CHECK-NEXT:     qstruct.yield %qb0, %qb1 : !qcore.qubit, !qcore.qubit
//CHECK-NEXT:   }
//CHECK-NEXT: }

// ----
// CHECK: ----

// measurement from repeat result: detector moves to just after the repeat + move detector after repeat
builtin.module {
  %q, %q_1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %0, %1 = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
  ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit):
    %m0 = qref.measure<Z> (%qb0) -> i1
    qec.measurement_round(%m0 : i1)

//CHECK-NEXT: builtin.module {
//CHECK-NEXT:   %q, %q_1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
//CHECK-NEXT:   %0, %1 = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
//CHECK-NEXT:   ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit):
//CHECK-NEXT:     %m0 = qref.measure<Z> (%qb0) -> i1
//CHECK-NEXT:     qec.measurement_round(%m0 : i1)

    %m_out = qstruct.repeat<2> (%m0 : i1) -> i1 {
    ^bb0(%m: i1):
      qstruct.yield %m : i1
    }

//CHECK-NEXT:     %m_out = qstruct.repeat<2> (%m0 : i1) -> i1 {
//CHECK-NEXT:     ^bb1(%m: i1):
//CHECK-NEXT:       qstruct.yield %m : i1
//CHECK-NEXT:     }

    %m1 = qref.measure<Z> (%qb1) -> i1
    %d1 = qec.detector(%m1)
    qec.measurement_round(%m1 : i1)
    %d2 = qec.detector(%m_out)
    qstruct.yield %qb0, %qb1 : !qcore.qubit, !qcore.qubit
  }
}

//CHECK-NEXT:     %d2 = qec.detector(%m_out)
//CHECK-NEXT:     %m1 = qref.measure<Z> (%qb1) -> i1
//CHECK-NEXT:     qec.measurement_round(%m1 : i1)
//CHECK-NEXT:     %d1 = qec.detector(%m1)
//CHECK-NEXT:     qstruct.yield %qb0, %qb1 : !qcore.qubit, !qcore.qubit
//CHECK-NEXT:   }
//CHECK-NEXT: }

// ----
// CHECK: ----

// detector inside repeat with outer-scope round: falls back to start of repeat body
builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %0 = qstruct.circuit(%q : !qcore.qubit) -> !qcore.qubit {
  ^bb0(%qb: !qcore.qubit):

//CHECK-NEXT: builtin.module {
//CHECK-NEXT:   %q = qcore.alloc_qubit -> !qcore.qubit
//CHECK-NEXT:   %0 = qstruct.circuit(%q : !qcore.qubit) -> !qcore.qubit {
//CHECK-NEXT:   ^bb0(%qb: !qcore.qubit):

    %m = qref.measure<Z> (%qb) -> i1
    qec.measurement_round(%m : i1)

//CHECK-NEXT:     %m = qref.measure<Z> (%qb) -> i1
//CHECK-NEXT:     qec.measurement_round(%m : i1)

    %m2 = qstruct.repeat<2> (%m : i1) -> i1 {
      ^bb1(%m_in: i1):
        %m1 = qref.measure<Z> (%qb) -> i1
        %d = qec.detector(%m_in)
      qstruct.yield %m1 : i1
    }
    qstruct.yield %qb : !qcore.qubit
  }
}

//CHECK-NEXT:     %m2 = qstruct.repeat<2> (%m : i1) -> i1 {
//CHECK-NEXT:     ^bb1(%m_in: i1):
//CHECK-NEXT:       %d = qec.detector(%m_in)
//CHECK-NEXT:       %m1 = qref.measure<Z> (%qb) -> i1
//CHECK-NEXT:       qstruct.yield %m1 : i1
//CHECK-NEXT:     }
//CHECK-NEXT:     qstruct.yield %qb : !qcore.qubit
//CHECK-NEXT:   }
//CHECK-NEXT: }

// ----
// CHECK: ----

// already in position: detector round directly after its detector is not moved
builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %0 = qstruct.circuit(%q : !qcore.qubit) -> !qcore.qubit {
  ^bb0(%qb: !qcore.qubit):
    %d = qec.detector()
    qec.detector_round(%d)
    qstruct.yield %qb : !qcore.qubit
  }
}

//CHECK-NEXT: builtin.module {
//CHECK-NEXT:   %q = qcore.alloc_qubit -> !qcore.qubit
//CHECK-NEXT:   %0 = qstruct.circuit(%q : !qcore.qubit) -> !qcore.qubit {
//CHECK-NEXT:   ^bb0(%qb: !qcore.qubit):
//CHECK-NEXT:     %d = qec.detector()
//CHECK-NEXT:     qec.detector_round(%d)
//CHECK-NEXT:     qstruct.yield %qb : !qcore.qubit
//CHECK-NEXT:   }
//CHECK-NEXT: }

// ----
// CHECK: ----

// detector round before other ops: moves to just after its detector
builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %0 = qstruct.circuit(%q : !qcore.qubit) -> !qcore.qubit {
  ^bb0(%qb: !qcore.qubit):
    %d = qec.detector()
    "test.op"() : () -> ()
    qec.detector_round(%d)
    qstruct.yield %qb : !qcore.qubit
  }
}

//CHECK-NEXT: builtin.module {
//CHECK-NEXT:   %q = qcore.alloc_qubit -> !qcore.qubit
//CHECK-NEXT:   %0 = qstruct.circuit(%q : !qcore.qubit) -> !qcore.qubit {
//CHECK-NEXT:   ^bb0(%qb: !qcore.qubit):
//CHECK-NEXT:     %d = qec.detector()
//CHECK-NEXT:     qec.detector_round(%d)
//CHECK-NEXT:     "test.op"() : () -> ()
//CHECK-NEXT:     qstruct.yield %qb : !qcore.qubit
//CHECK-NEXT:   }
//CHECK-NEXT: }

// ----
// CHECK: ----

// three detector rounds: each moves after its own detector, relative order preserved
builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %0 = qstruct.circuit(%q : !qcore.qubit) -> !qcore.qubit {
  ^bb0(%qb: !qcore.qubit):
    %d1 = qec.detector()
    %d2 = qec.detector()
    "test.op"() : () -> ()
    qec.detector_round(%d1)
    qec.detector_round()
    qec.detector_round(%d2)
    qstruct.yield %qb : !qcore.qubit
  }
}

//CHECK-NEXT: builtin.module {
//CHECK-NEXT:   %q = qcore.alloc_qubit -> !qcore.qubit
//CHECK-NEXT:   %0 = qstruct.circuit(%q : !qcore.qubit) -> !qcore.qubit {
//CHECK-NEXT:   ^bb0(%qb: !qcore.qubit):
//CHECK-NEXT:     %d1 = qec.detector()
//CHECK-NEXT:     qec.detector_round(%d1)
//CHECK-NEXT:     qec.detector_round()
//CHECK-NEXT:     %d2 = qec.detector()
//CHECK-NEXT:     qec.detector_round(%d2)
//CHECK-NEXT:     "test.op"() : () -> ()
//CHECK-NEXT:     qstruct.yield %qb : !qcore.qubit
//CHECK-NEXT:   }
//CHECK-NEXT: }

// ----
// CHECK: ----

// three detector rounds: but cannot put after own detector
builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %0 = qstruct.circuit(%q : !qcore.qubit) -> !qcore.qubit {
  ^bb0(%qb: !qcore.qubit):
    %d1 = qec.detector()
    %d2 = qec.detector()
    "test.op"() : () -> ()
    qec.detector_round(%d2)
    qec.detector_round()
    qec.detector_round(%d1)
    qstruct.yield %qb : !qcore.qubit
  }
}

//CHECK-NEXT: builtin.module {
//CHECK-NEXT:   %q = qcore.alloc_qubit -> !qcore.qubit
//CHECK-NEXT:   %0 = qstruct.circuit(%q : !qcore.qubit) -> !qcore.qubit {
//CHECK-NEXT:   ^bb0(%qb: !qcore.qubit):
//CHECK-NEXT:     %d1 = qec.detector()
//CHECK-NEXT:     %d2 = qec.detector()
//CHECK-NEXT:     qec.detector_round(%d2)
//CHECK-NEXT:     qec.detector_round()
//CHECK-NEXT:     qec.detector_round(%d1)
//CHECK-NEXT:     "test.op"() : () -> ()
//CHECK-NEXT:     qstruct.yield %qb : !qcore.qubit
//CHECK-NEXT:   }
//CHECK-NEXT: }

// ----
// CHECK: ----

// detector round inside repeat body referencing block arg: moves to start of repeat body
builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %0 = qstruct.circuit(%q : !qcore.qubit) -> !qcore.qubit {
  ^bb0(%qb: !qcore.qubit):
    %d_in = qec.detector()
    %d_out = qstruct.repeat<2> (%d_in : !qec.detector_ref) -> !qec.detector_ref {
    ^bb1(%d: !qec.detector_ref):
      "test.op"() : () -> ()
      qec.detector_round(%d)
      qstruct.yield %d : !qec.detector_ref
    }
    qstruct.yield %qb : !qcore.qubit
  }
}

//CHECK-NEXT: builtin.module {
//CHECK-NEXT:   %q = qcore.alloc_qubit -> !qcore.qubit
//CHECK-NEXT:   %0 = qstruct.circuit(%q : !qcore.qubit) -> !qcore.qubit {
//CHECK-NEXT:   ^bb0(%qb: !qcore.qubit):
//CHECK-NEXT:     %d_in = qec.detector()
//CHECK-NEXT:     %d_out = qstruct.repeat<2> (%d_in : !qec.detector_ref) -> !qec.detector_ref {
//CHECK-NEXT:     ^bb1(%d: !qec.detector_ref):
//CHECK-NEXT:       qec.detector_round(%d)
//CHECK-NEXT:       "test.op"() : () -> ()
//CHECK-NEXT:       qstruct.yield %d : !qec.detector_ref
//CHECK-NEXT:     }
//CHECK-NEXT:     qstruct.yield %qb : !qcore.qubit
//CHECK-NEXT:   }
//CHECK-NEXT: }

// ----
// CHECK: ----

// detector round inside repeat body referencing block arg and detector round that uses repeat
// result
builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %0 = qstruct.circuit(%q : !qcore.qubit) -> !qcore.qubit {
  ^bb0(%qb: !qcore.qubit):
    %d_in = qec.detector()
    %d_out = qstruct.repeat<2> (%d_in : !qec.detector_ref) -> !qec.detector_ref {
    ^bb1(%d: !qec.detector_ref):
      %d1 = qec.detector()
      qec.detector_round(%d1)
      "test.op"() : () -> ()
      qec.detector_round(%d)
      qstruct.yield %d : !qec.detector_ref
    }
    "test.op"() : () -> ()
    qec.detector_round(%d_out)
    qstruct.yield %qb : !qcore.qubit
  }
}

//CHECK-NEXT: builtin.module {
//CHECK-NEXT:   %q = qcore.alloc_qubit -> !qcore.qubit
//CHECK-NEXT:   %0 = qstruct.circuit(%q : !qcore.qubit) -> !qcore.qubit {
//CHECK-NEXT:   ^bb0(%qb: !qcore.qubit):
//CHECK-NEXT:     %d_in = qec.detector()
//CHECK-NEXT:     %d_out = qstruct.repeat<2> (%d_in : !qec.detector_ref) -> !qec.detector_ref {
//CHECK-NEXT:     ^bb1(%d: !qec.detector_ref):
//CHECK-NEXT:       %d1 = qec.detector()
//CHECK-NEXT:       qec.detector_round(%d1)
//CHECK-NEXT:       qec.detector_round(%d)
//CHECK-NEXT:       "test.op"() : () -> ()
//CHECK-NEXT:       qstruct.yield %d : !qec.detector_ref
//CHECK-NEXT:     }
//CHECK-NEXT:     qec.detector_round(%d_out)
//CHECK-NEXT:     "test.op"() : () -> ()
//CHECK-NEXT:     qstruct.yield %qb : !qcore.qubit
//CHECK-NEXT:   }
//CHECK-NEXT: }

// ----
// CHECK: ----

builtin.module {
  qstruct.circuit -> {
    %0 = qec.detector<[0.0, 0.0]> ()
    "test.op"() : () -> ()
    qec.detector_round(%0)
    "test.op"() : () -> ()
    "test.op"() : () -> ()
    qec.detector_round()
    %1 = qec.detector<[0.0, 0.0]> ()
    %2 = qec.detector()
    %3, %4 = qstruct.repeat<3> (%1, %2 : !qec.detector_ref, !qec.detector_ref) -> !qec.detector_ref, !qec.detector_ref {
    ^bb0(%5: !qec.detector_ref, %6: !qec.detector_ref):
      %7, %8 = qstruct.repeat<2> (%5, %6 : !qec.detector_ref, !qec.detector_ref) -> !qec.detector_ref, !qec.detector_ref {
      ^bb1(%9: !qec.detector_ref, %10: !qec.detector_ref):
        %11 = qec.detector<[0.0, 0.0]> ()
        "test.op"() : () -> ()
        %12 = qec.detector<[0.0, 0.0]> ()
        "test.op"() : () -> ()
        qec.detector_round(%9, %11)
        qstruct.yield %10, %12 : !qec.detector_ref, !qec.detector_ref
      }
      "test.op"() : () -> ()
      "test.op"() : () -> ()
      %13 = qec.detector<[0.0, 0.0]> ()
      "test.op"() : () -> ()
      %14 = qec.detector<[0.0, 0.0]> ()
      qec.detector_round(%7, %13)
      qstruct.yield %8, %14 : !qec.detector_ref, !qec.detector_ref
    }
    "test.op"() : () -> ()
    qec.detector_round(%3)
    qec.detector_round(%4)
    qstruct.yield
  }
}

//CHECK-NEXT:  builtin.module {
//CHECK-NEXT:    qstruct.circuit -> {
//CHECK-NEXT:      %0 = qec.detector<[0.0, 0.0]> ()
//CHECK-NEXT:      qec.detector_round(%0)
//CHECK-NEXT:      qec.detector_round()
//CHECK-NEXT:      "test.op"() : () -> ()
//CHECK-NEXT:      "test.op"() : () -> ()
//CHECK-NEXT:      "test.op"() : () -> ()
//CHECK-NEXT:      %1 = qec.detector<[0.0, 0.0]> ()
//CHECK-NEXT:      %2 = qec.detector()
//CHECK-NEXT:      %3, %4 = qstruct.repeat<3> (%1, %2 : !qec.detector_ref, !qec.detector_ref) -> !qec.detector_ref, !qec.detector_ref {
//CHECK-NEXT:      ^bb0(%5: !qec.detector_ref, %6: !qec.detector_ref):
//CHECK-NEXT:        %7, %8 = qstruct.repeat<2> (%5, %6 : !qec.detector_ref, !qec.detector_ref) -> !qec.detector_ref, !qec.detector_ref {
//CHECK-NEXT:        ^bb1(%9: !qec.detector_ref, %10: !qec.detector_ref):
//CHECK-NEXT:          %11 = qec.detector<[0.0, 0.0]> ()
//CHECK-NEXT:          qec.detector_round(%9, %11)
//CHECK-NEXT:          "test.op"() : () -> ()
//CHECK-NEXT:          %12 = qec.detector<[0.0, 0.0]> ()
//CHECK-NEXT:          "test.op"() : () -> ()
//CHECK-NEXT:          qstruct.yield %10, %12 : !qec.detector_ref, !qec.detector_ref
//CHECK-NEXT:        }
//CHECK-NEXT:        "test.op"() : () -> ()
//CHECK-NEXT:        "test.op"() : () -> ()
//CHECK-NEXT:        %13 = qec.detector<[0.0, 0.0]> ()
//CHECK-NEXT:        qec.detector_round(%7, %13)
//CHECK-NEXT:        "test.op"() : () -> ()
//CHECK-NEXT:        %14 = qec.detector<[0.0, 0.0]> ()
//CHECK-NEXT:        qstruct.yield %8, %14 : !qec.detector_ref, !qec.detector_ref
//CHECK-NEXT:      }
//CHECK-NEXT:      qec.detector_round(%3)
//CHECK-NEXT:      qec.detector_round(%4)
//CHECK-NEXT:      "test.op"() : () -> ()
//CHECK-NEXT:      qstruct.yield
//CHECK-NEXT:    }
//CHECK-NEXT:  }

// ----
// CHECK: ----

// comprehensive: measure_rounds placed after consecutive measurements; detector and
// detector_round ops out of order in the final round (before their measure_rounds).
// In the repeat body, each detector is interleaved with its own measurement_round.
// Expected transformations:
//   - repeat body: %dr0 moves to after measurement_round(%mr0),
//                  %dr1 is already after measurement_round(%mr1)
//   - outer block: %d_fin0/%d_fin1 move after their measure_rounds,
//                  qec.detector_round moves after %d_fin1
builtin.module {
  %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %out0, %out1 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
  ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit):
    %m0 = qref.measure<Z> (%qb0) -> i1
    %m1 = qref.measure<Z> (%qb1) -> i1
    qec.measurement_round(%m0 : i1)
    qec.measurement_round(%m1 : i1)
    %m_fin0, %m_fin1 = qstruct.repeat<3> (%m0, %m1 : i1, i1) -> i1, i1 {
    ^bb1(%m_prev0: i1, %m_prev1: i1):
      %mr0 = qref.measure<Z> (%qb0) -> i1
      %mr1 = qref.measure<Z> (%qb1) -> i1
      qec.measurement_round(%mr0 : i1)
      qec.measurement_round(%mr1 : i1)
      %dr0 = qec.detector(%mr0, %m_prev0)
      %dr1 = qec.detector(%mr1, %m_prev1)
      qec.detector_round(%dr0, %dr1)
      qec.detector_round()
      qstruct.yield %mr0, %mr1 : i1, i1
    }
    %m_data0 = qref.measure<Z> (%qb0) -> i1
    %m_data1 = qref.measure<Z> (%qb1) -> i1
    %d_fin0 = qec.detector(%m_data0, %m_fin0)
    %d_fin1 = qec.detector(%m_data1, %m_fin1)
    qec.detector_round(%d_fin0, %d_fin1)
    qec.measurement_round(%m_data0 : i1)
    qec.measurement_round(%m_data1 : i1)
    qec.detector_round()
    qstruct.yield %qb0, %qb1 : !qcore.qubit, !qcore.qubit
  }
}

//CHECK-NEXT: builtin.module {
//CHECK-NEXT:   %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
//CHECK-NEXT:   %out0, %out1 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
//CHECK-NEXT:   ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit):
//CHECK-NEXT:     %m0 = qref.measure<Z> (%qb0) -> i1
//CHECK-NEXT:     %m1 = qref.measure<Z> (%qb1) -> i1
//CHECK-NEXT:     qec.measurement_round(%m0 : i1)
//CHECK-NEXT:     qec.measurement_round(%m1 : i1)
//CHECK-NEXT:     %m_fin0, %m_fin1 = qstruct.repeat<3> (%m0, %m1 : i1, i1) -> i1, i1 {
//CHECK-NEXT:     ^bb1(%m_prev0: i1, %m_prev1: i1):
//CHECK-NEXT:       %mr0 = qref.measure<Z> (%qb0) -> i1
//CHECK-NEXT:       %mr1 = qref.measure<Z> (%qb1) -> i1
//CHECK-NEXT:       qec.measurement_round(%mr0 : i1)
//CHECK-NEXT:       %dr0 = qec.detector(%mr0, %m_prev0)
//CHECK-NEXT:       qec.measurement_round(%mr1 : i1)
//CHECK-NEXT:       %dr1 = qec.detector(%mr1, %m_prev1)
//CHECK-NEXT:       qec.detector_round(%dr0, %dr1)
//CHECK-NEXT:       qec.detector_round()
//CHECK-NEXT:       qstruct.yield %mr0, %mr1 : i1, i1
//CHECK-NEXT:     }
//CHECK-NEXT:     %m_data0 = qref.measure<Z> (%qb0) -> i1
//CHECK-NEXT:     %m_data1 = qref.measure<Z> (%qb1) -> i1
//CHECK-NEXT:     qec.measurement_round(%m_data0 : i1)
//CHECK-NEXT:     %d_fin0 = qec.detector(%m_data0, %m_fin0)
//CHECK-NEXT:     qec.measurement_round(%m_data1 : i1)
//CHECK-NEXT:     %d_fin1 = qec.detector(%m_data1, %m_fin1)
//CHECK-NEXT:     qec.detector_round(%d_fin0, %d_fin1)
//CHECK-NEXT:     qec.detector_round()
//CHECK-NEXT:     qstruct.yield %qb0, %qb1 : !qcore.qubit, !qcore.qubit
//CHECK-NEXT:   }
//CHECK-NEXT: }
