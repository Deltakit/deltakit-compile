// RUN: deltakit_compile compile-passes -t %s -p merge-gate-like-broadcast-ops -O %t && filecheck %s --input-file %t

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit

  // Measurement regions merge into broadcast measure with results
  %q_b, %q_b1 = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_a1: !qcore.qubit):
    %mz_q, %mz_q1 = qstruct.parallel<TOP> {} -> i1, i1 {
      %mz_q_local = qref.measure<Z> (%q_a) -> i1
      qstruct.yield %mz_q_local : i1
    } {
      %mz_q1_local = qref.measure<Z> (%q_a1) -> i1
      qstruct.yield %mz_q1_local : i1
    }
    qstruct.yield %q_a, %q_a1 : !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_b1 = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_a1: !qcore.qubit):
// CHECK-NEXT:      %mz_q, %mz_q1 = qref.measure<Z> (%q_a, %q_a1) -> i1, i1
// CHECK-NEXT:      qstruct.yield %q_a, %q_a1 : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

// === Complex mixed merge groups ===

builtin.module {
  %q_h0 = qcore.alloc_qubit -> !qcore.qubit
  %q_h1 = qcore.alloc_qubit -> !qcore.qubit
  %q_mx0 = qcore.alloc_qubit -> !qcore.qubit
  %q_mx1 = qcore.alloc_qubit -> !qcore.qubit
  %q_mx2 = qcore.alloc_qubit -> !qcore.qubit
  %q_r = qcore.alloc_qubit -> !qcore.qubit

  // Two H gates, three X measurements (with results), and one Z reset.
  // Expect grouping into parallel regions: {H h0 h1}{measure X mx0 mx1 mx2}{reset Z r}
  %q_h0_b, %q_h1_b, %q_mx0_b, %q_mx1_b, %q_mx2_b, %q_r_b = qstruct.circuit(%q_h0, %q_h1, %q_mx0, %q_mx1, %q_mx2, %q_r : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%q_h0_a: !qcore.qubit, %q_h1_a: !qcore.qubit, %q_mx0_a: !qcore.qubit, %q_mx1_a: !qcore.qubit, %q_mx2_a: !qcore.qubit, %q_r_a: !qcore.qubit):
    %mx0, %mx1, %mx2 = qstruct.parallel<TOP> {} -> i1, i1, i1 {
      qref.gate<#qcore.gate.h> (%q_h0_a)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.h> (%q_h1_a)
      qstruct.yield
    } {
      %mx0_local = qref.measure<X> (%q_mx0_a) -> i1
      qstruct.yield %mx0_local : i1
    } {
      %mx1_local = qref.measure<X> (%q_mx1_a) -> i1
      qstruct.yield %mx1_local : i1
    } {
      %mx2_local = qref.measure<X> (%q_mx2_a) -> i1
      qstruct.yield %mx2_local : i1
    } {
      qref.reset<Z> (%q_r_a)
      qstruct.yield
    }
    qstruct.yield %q_h0_a, %q_h1_a, %q_mx0_a, %q_mx1_a, %q_mx2_a, %q_r_a : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q_h0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_h1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_mx0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_mx1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_mx2 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_r = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_h0_b, %q_h1_b, %q_mx0_b, %q_mx1_b, %q_mx2_b, %q_r_b = qstruct.circuit(%q_h0, %q_h1, %q_mx0, %q_mx1, %q_mx2, %q_r : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_h0_a: !qcore.qubit, %q_h1_a: !qcore.qubit, %q_mx0_a: !qcore.qubit, %q_mx1_a: !qcore.qubit, %q_mx2_a: !qcore.qubit, %q_r_a: !qcore.qubit):
// CHECK-NEXT:      %mx0, %mx1, %mx2 = qstruct.parallel<TOP> -> i1, i1, i1 {
// CHECK-NEXT:        qref.reset<Z> (%q_r_a)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      } {
// CHECK-NEXT:        qref.gate<#qcore.gate.h> (%q_h0_a, %q_h1_a)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      } {
// CHECK-NEXT:        %0, %1, %2 = qref.measure<X> (%q_mx0_a, %q_mx1_a, %q_mx2_a) -> i1, i1, i1
// CHECK-NEXT:        qstruct.yield %0, %1, %2 : i1, i1, i1
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield %q_h0_a, %q_h1_a, %q_mx0_a, %q_mx1_a, %q_mx2_a, %q_r_a : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

// === Additional measurement coverage ===

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit

  // Positive: measurements with equal noise merge into broadcast measurement
  %q_b, %q_1_b = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit):
    %mz_q, %mz_q1 = qstruct.parallel<TOP> {} -> i1, i1 {
      %mz_q_local = qref.measure<Z, 0.01> (%q_a) -> i1
      qstruct.yield %mz_q_local : i1
    } {
      %mz_q1_local = qref.measure<Z, 0.01> (%q_1_a) -> i1
      qstruct.yield %mz_q1_local : i1
    }
    qstruct.yield %q_a, %q_1_a : !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit):
// CHECK-NEXT:      %mz_q, %mz_q1 = qref.measure<Z, 0.01> (%q_a, %q_1_a) -> i1, i1
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit
  %q_2 = qcore.alloc_qubit -> !qcore.qubit

  // Mixed noise probabilities: form grouped parallel regions
  %q_b, %q_1_b, %q_2_b = qstruct.circuit(%q, %q_1, %q_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit):
    %mz_q, %mz_q1, %mx_q2 = qstruct.parallel<TOP> {} -> i1, i1, i1 {
      %mz_q_local = qref.measure<Z, 0.01> (%q_a) -> i1
      qstruct.yield %mz_q_local : i1
    } {
      %mz_q1_local = qref.measure<Z, 0.01> (%q_1_a) -> i1
      qstruct.yield %mz_q1_local : i1
    } {
      %mx_q2_local = qref.measure<Z, 0.02> (%q_2_a) -> i1
      qstruct.yield %mx_q2_local : i1
    }
    qstruct.yield %q_a, %q_1_a, %q_2_a : !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_2 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b, %q_2_b = qstruct.circuit(%q, %q_1, %q_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit):
// CHECK-NEXT:      %mz_q, %mz_q1, %mx_q2 = qstruct.parallel<TOP> -> i1, i1, i1 {
// CHECK-NEXT:        %0, %1 = qref.measure<Z, 0.01> (%q_a, %q_1_a) -> i1, i1
// CHECK-NEXT:        qstruct.yield %0, %1 : i1, i1
// CHECK-NEXT:      } {
// CHECK-NEXT:        %mx_q2_local = qref.measure<Z, 0.02> (%q_2_a) -> i1
// CHECK-NEXT:        qstruct.yield %mx_q2_local : i1
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a, %q_2_a : !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit
  %q_2 = qcore.alloc_qubit -> !qcore.qubit

  // Mixed bases: merge into one measure
  %q_b, %q_1_b, %q_2_b = qstruct.circuit(%q, %q_1, %q_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit):
    %m1, %m2, %m3 = qstruct.parallel<TOP> {} -> i1, i1, i1 {
      %m1_local = qref.measure<X> (%q_a) -> i1
      qstruct.yield %m1_local : i1
    } {
      %m2_local = qref.measure<Y> (%q_1_a) -> i1
      qstruct.yield %m2_local : i1
    } {
      %m3_local = qref.measure<Z> (%q_2_a) -> i1
      qstruct.yield %m3_local : i1
    }
    qstruct.yield %q_a, %q_1_a, %q_2_a : !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_2 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b, %q_2_b = qstruct.circuit(%q, %q_1, %q_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit):
// CHECK-NEXT:      %m1, %m2, %m3 = qref.measure<[X, Y, Z]> (%q_a, %q_1_a, %q_2_a) -> i1, i1, i1
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a, %q_2_a : !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }


// ----

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit
  %q_2 = qcore.alloc_qubit -> !qcore.qubit
  %q_3 = qcore.alloc_qubit -> !qcore.qubit
  %q_4 = qcore.alloc_qubit -> !qcore.qubit

  // Mixed single and multi-Pauli measurements: merge into one measure
  %q_b, %q_1_b, %q_2_b, %q_3_b, %q_4_b = qstruct.circuit(%q, %q_1, %q_2, %q_3, %q_4 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit, %q_3_a: !qcore.qubit, %q_4_a: !qcore.qubit):
    %m1, %m2, %m3 = qstruct.parallel<TOP> {} -> i1, i1, i1 {
      %m1_local = qref.measure<XX> (%q_a, %q_1_a) -> i1
      qstruct.yield %m1_local : i1
    } {
      %m2_local = qref.measure<Z> (%q_2_a) -> i1
      qstruct.yield %m2_local : i1
    } {
      %m3_local = qref.measure<YZ> (%q_3_a, %q_4_a) -> i1
      qstruct.yield %m3_local : i1
    }
    qstruct.yield %q_a, %q_1_a, %q_2_a, %q_3_a, %q_4_a : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_2 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_3 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_4 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b, %q_2_b, %q_3_b, %q_4_b = qstruct.circuit(%q, %q_1, %q_2, %q_3, %q_4 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit, %q_3_a: !qcore.qubit, %q_4_a: !qcore.qubit):
// CHECK-NEXT:      %m1, %m2, %m3 = qref.measure<[XX, Z, YZ]> (%q_a, %q_1_a, %q_2_a, %q_3_a, %q_4_a) -> i1, i1, i1
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a, %q_2_a, %q_3_a, %q_4_a : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit
  %q_2 = qcore.alloc_qubit -> !qcore.qubit
  %q_3 = qcore.alloc_qubit -> !qcore.qubit

  // Merges already broadcast measurements
  %q_b, %q_1_b, %q_2_b, %q_3_b = qstruct.circuit(%q, %q_1, %q_2, %q_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit, %q_3_a: !qcore.qubit):
    %m1, %m2, %m3 = qstruct.parallel<TOP> {} -> i1, i1, i1 {
      %m1_local, %m2_local = qref.measure<[XX, Y]> (%q_a, %q_1_a, %q_2_a) -> i1, i1
      qstruct.yield %m1_local, %m2_local : i1, i1
    } {
      %m3_local = qref.measure<Z> (%q_3_a) -> i1
      qstruct.yield %m3_local : i1
    }
    qstruct.yield %q_a, %q_1_a, %q_2_a, %q_3_a : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_2 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_3 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b, %q_2_b, %q_3_b = qstruct.circuit(%q, %q_1, %q_2, %q_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit, %q_3_a: !qcore.qubit):
// CHECK-NEXT:      %m1, %m2, %m3 = qref.measure<[XX, Y, Z]> (%q_a, %q_1_a, %q_2_a, %q_3_a) -> i1, i1, i1
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a, %q_2_a, %q_3_a : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

// === Additional single-qubit clifford coverage ===

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit
  %q_2 = qcore.alloc_qubit -> !qcore.qubit

  // Positive: three X regions merge into a single broadcast clifford
  %q_b, %q_1_b, %q_2_b = qstruct.circuit(%q, %q_1, %q_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit):
    qstruct.parallel<TOP> {} -> {
      qref.gate<#qcore.gate.x> (%q_a)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.x> (%q_1_a)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.x> (%q_2_a)
      qstruct.yield
    }
    qstruct.yield %q_a, %q_1_a, %q_2_a : !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_2 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b, %q_2_b = qstruct.circuit(%q, %q_1, %q_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit):
// CHECK-NEXT:      qref.gate<#qcore.gate.x> (%q_a, %q_1_a, %q_2_a)
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a, %q_2_a : !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit
  %q_2 = qcore.alloc_qubit -> !qcore.qubit

  // Positive: two X regions, one already broadcast, merge into a single broadcast clifford
  %q_b, %q_1_b, %q_2_b = qstruct.circuit(%q, %q_1, %q_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit):
    qstruct.parallel<TOP> {} -> {
      qref.gate<#qcore.gate.x> (%q_a, %q_1_a)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.x> (%q_2_a)
      qstruct.yield
    }
    qstruct.yield %q_a, %q_1_a, %q_2_a : !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_2 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b, %q_2_b = qstruct.circuit(%q, %q_1, %q_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit):
// CHECK-NEXT:      qref.gate<#qcore.gate.x> (%q_a, %q_1_a, %q_2_a)
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a, %q_2_a : !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }


// ----

// === Additional reset coverage ===

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit
  %q_2 = qcore.alloc_qubit -> !qcore.qubit

  // Positive: three Z resets merge into a single broadcast reset
  %q_b, %q_1_b, %q_2_b = qstruct.circuit(%q, %q_1, %q_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit):
    qstruct.parallel<TOP> {} -> {
      qref.reset<Z> (%q_a)
      qstruct.yield
    } {
      qref.reset<Z> (%q_1_a)
      qstruct.yield
    } {
      qref.reset<Z> (%q_2_a)
      qstruct.yield
    }
    qstruct.yield %q_a, %q_1_a, %q_2_a : !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_2 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b, %q_2_b = qstruct.circuit(%q, %q_1, %q_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit):
// CHECK-NEXT:      qref.reset<Z> (%q_a, %q_1_a, %q_2_a)
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a, %q_2_a : !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit
  %q_2 = qcore.alloc_qubit -> !qcore.qubit

  // Positive: two Z resets, one already broadcast, merge into a single broadcast reset
  %q_b, %q_1_b, %q_2_b = qstruct.circuit(%q, %q_1, %q_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit):
    qstruct.parallel<TOP> {} -> {
      qref.reset<Z> (%q_a, %q_1_a)
      qstruct.yield
    } {
      qref.reset<Z> (%q_2_a)
      qstruct.yield
    }
    qstruct.yield %q_a, %q_1_a, %q_2_a : !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_2 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b, %q_2_b = qstruct.circuit(%q, %q_1, %q_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit):
// CHECK-NEXT:      qref.reset<Z> (%q_a, %q_1_a, %q_2_a)
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a, %q_2_a : !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit

  // Single-qubit clifford regions merge into broadcast clifford
  %q_b, %q_1_b = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit):
    qstruct.parallel<TOP> {} -> {
      qref.gate<#qcore.gate.x> (%q_a)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.x> (%q_1_a)
      qstruct.yield
    }
    qstruct.yield %q_a, %q_1_a : !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit):
// CHECK-NEXT:      qref.gate<#qcore.gate.x> (%q_a, %q_1_a)
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit
  %q_2 = qcore.alloc_qubit -> !qcore.qubit

  // Mixed single-qubit cliffords: X on %q and %q_1 can merge; Z on %q_2 remains separate.
  // Expect parallel {X (%q, %q_1)} {Z (%q_2)}
  %q_b, %q_1_b, %q_2_b = qstruct.circuit(%q, %q_1, %q_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit):
    qstruct.parallel<TOP> {} -> {
      qref.gate<#qcore.gate.x> (%q_a)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.x> (%q_1_a)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.z> (%q_2_a)
      qstruct.yield
    }
    qstruct.yield %q_a, %q_1_a, %q_2_a : !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_2 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b, %q_2_b = qstruct.circuit(%q, %q_1, %q_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit):
// CHECK-NEXT:      qstruct.parallel<TOP> -> {
// CHECK-NEXT:        qref.gate<#qcore.gate.x> (%q_a, %q_1_a)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      } {
// CHECK-NEXT:        qref.gate<#qcore.gate.z> (%q_2_a)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a, %q_2_a : !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit

  // Negative: same Pauli (Z) but different noise parameters across regions; should not merge
  %q_b, %q_1_b = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit):
    %mz_q, %mz_q1 = qstruct.parallel<TOP> {} -> i1, i1 {
      %mz_q_local = qref.measure<Z, 0.01> (%q_a) -> i1
      qstruct.yield %mz_q_local : i1
    } {
      %mz_q1_local = qref.measure<Z, 0.02> (%q_1_a) -> i1
      qstruct.yield %mz_q1_local : i1
    }
    qstruct.yield %q_a, %q_1_a : !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit):
// CHECK-NEXT:      %mz_q, %mz_q1 = qstruct.parallel<TOP> -> i1, i1 {
// CHECK-NEXT:        %mz_q_local = qref.measure<Z, 0.01> (%q_a) -> i1
// CHECK-NEXT:        qstruct.yield %mz_q_local : i1
// CHECK-NEXT:      } {
// CHECK-NEXT:        %mz_q1_local = qref.measure<Z, 0.02> (%q_1_a) -> i1
// CHECK-NEXT:        qstruct.yield %mz_q1_local : i1
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit

  // Negative: regions contain non gate ops, nothing to merge.
  %q_b, %q_1_b = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit):
    qstruct.parallel<TOP> {} -> {
      "test.op"() : () -> ()
      qstruct.yield
    } {
      "test.op"() : () -> ()
      qstruct.yield
    }
    qstruct.yield %q_a, %q_1_a : !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit):
// CHECK-NEXT:      qstruct.parallel<TOP> -> {
// CHECK-NEXT:        "test.op"() : () -> ()
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      } {
// CHECK-NEXT:        "test.op"() : () -> ()
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit

  // Negative: one region has only yield, other has a clifford then yield; should not merge
  %q_b, %q_1_b = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit):
    qstruct.parallel<TOP> {} -> {
      qstruct.yield
    } {
      qref.gate<#qcore.gate.x> (%q_1_a)
      qstruct.yield
    }
    qstruct.yield %q_a, %q_1_a : !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit):
// CHECK-NEXT:      qstruct.parallel<TOP> -> {
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      } {
// CHECK-NEXT:        qref.gate<#qcore.gate.x> (%q_1_a)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit

  // Positive: reset regions merge into broadcast reset (empty yields)
  %q_b, %q_1_b = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit):
    qstruct.parallel<TOP> {} -> {
      qref.reset<Z> (%q_a)
      qstruct.yield
    } {
      qref.reset<Z> (%q_1_a)
      qstruct.yield
    }
    qstruct.yield %q_a, %q_1_a : !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit):
// CHECK-NEXT:      qref.reset<Z> (%q_a, %q_1_a)
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit
  %q_2 = qcore.alloc_qubit -> !qcore.qubit

  // Mixed resets: Z on %q and %q_1 merge; X on %q_2 remains separate.
  // Expect parallel {reset Z (%q, %q_1)} {reset X (%q_2)}
  %q_b, %q_1_b, %q_2_b = qstruct.circuit(%q, %q_1, %q_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit):
    qstruct.parallel<TOP> {} -> {
      qref.reset<Z> (%q_a)
      qstruct.yield
    } {
      qref.reset<Z> (%q_1_a)
      qstruct.yield
    } {
      qref.reset<X> (%q_2_a)
      qstruct.yield
    }
    qstruct.yield %q_a, %q_1_a, %q_2_a : !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_2 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b, %q_2_b = qstruct.circuit(%q, %q_1, %q_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit):
// CHECK-NEXT:      qstruct.parallel<TOP> -> {
// CHECK-NEXT:        qref.reset<Z> (%q_a, %q_1_a)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      } {
// CHECK-NEXT:        qref.reset<X> (%q_2_a)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a, %q_2_a : !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit

  // Negative: region contains more than two ops, should not merge
  %q_b, %q_1_b = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit):
    qstruct.parallel<TOP> {} -> {
      qref.gate<#qcore.gate.x> (%q_a)
      qref.gate<#qcore.gate.z> (%q_a)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.x> (%q_1_a)
      qstruct.yield
    }
    qstruct.yield %q_a, %q_1_a : !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit):
// CHECK-NEXT:      qstruct.parallel<TOP> -> {
// CHECK-NEXT:        qref.gate<#qcore.gate.x> (%q_a)
// CHECK-NEXT:        qref.gate<#qcore.gate.z> (%q_a)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      } {
// CHECK-NEXT:        qref.gate<#qcore.gate.x> (%q_1_a)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit
  %q_2 = qcore.alloc_qubit -> !qcore.qubit
  %q_3 = qcore.alloc_qubit -> !qcore.qubit

  // Two-qubit clifford regions merge into broadcast clifford over pairs
  %q_b, %q_1_b, %q_2_b, %q_3_b = qstruct.circuit(%q, %q_1, %q_2, %q_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit, %q_3_a: !qcore.qubit):
    qstruct.parallel<TOP> {} -> {
      qref.gate<#qcore.gate.cx> (%q_a, %q_1_a)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.cx> (%q_2_a, %q_3_a)
      qstruct.yield
    }
    qstruct.yield %q_a, %q_1_a, %q_2_a, %q_3_a : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_2 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_3 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b, %q_2_b, %q_3_b = qstruct.circuit(%q, %q_1, %q_2, %q_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit, %q_3_a: !qcore.qubit):
// CHECK-NEXT:      qref.gate<#qcore.gate.cx> (%q_a, %q_1_a, %q_2_a, %q_3_a)
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a, %q_2_a, %q_3_a : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit
  %q_2 = qcore.alloc_qubit -> !qcore.qubit

  // Negative: region contains more than one gate, should not merge
  %q_b, %q_1_b, %q_2_b = qstruct.circuit(%q, %q_1, %q_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit):
    qstruct.parallel<TOP> {} -> {
      qref.gate<#qcore.gate.x> (%q_a)
      qref.gate<#qcore.gate.x> (%q_1_a)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.x> (%q_2_a)
      qstruct.yield
    }
    qstruct.yield %q_a, %q_1_a, %q_2_a : !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_2 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b, %q_2_b = qstruct.circuit(%q, %q_1, %q_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit):
// CHECK-NEXT:      qstruct.parallel<TOP> -> {
// CHECK-NEXT:        qref.gate<#qcore.gate.x> (%q_a)
// CHECK-NEXT:        qref.gate<#qcore.gate.x> (%q_1_a)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      } {
// CHECK-NEXT:        qref.gate<#qcore.gate.x> (%q_2_a)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a, %q_2_a : !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit

  // Negative: resets with different pauli modifiers across regions, should not merge
  %q_b, %q_1_b = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit):
    qstruct.parallel<TOP> {} -> {
      qref.reset<Z> (%q_a)
      qstruct.yield
    } {
      qref.reset<X> (%q_1_a)
      qstruct.yield
    }
    qstruct.yield %q_a, %q_1_a : !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit):
// CHECK-NEXT:      qstruct.parallel<TOP> -> {
// CHECK-NEXT:        qref.reset<Z> (%q_a)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      } {
// CHECK-NEXT:        qref.reset<X> (%q_1_a)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit

  // Negative: different gate params across regions, should not merge
  %q_b, %q_1_b = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit):
    qstruct.parallel<TOP> {} -> {
      qref.gate<#qcore.gate.x> (%q_a)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.h> (%q_1_a)
      qstruct.yield
    }
    qstruct.yield %q_a, %q_1_a : !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit):
// CHECK-NEXT:      qstruct.parallel<TOP> -> {
// CHECK-NEXT:        qref.gate<#qcore.gate.x> (%q_a)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      } {
// CHECK-NEXT:        qref.gate<#qcore.gate.h> (%q_1_a)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

// === Mixed single-qubit clifford coverage (two X and two H) ===

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit
  %q_2 = qcore.alloc_qubit -> !qcore.qubit
  %q_3 = qcore.alloc_qubit -> !qcore.qubit

  // Two X gates and two H gates; expect two broadcast regions grouped by type
  %q_b, %q_1_b, %q_2_b, %q_3_b = qstruct.circuit(%q, %q_1, %q_2, %q_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit, %q_3_a: !qcore.qubit):
    qstruct.parallel<TOP> {} -> {
      qref.gate<#qcore.gate.x> (%q_a)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.x> (%q_1_a)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.h> (%q_2_a)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.h> (%q_3_a)
      qstruct.yield
    }
    qstruct.yield %q_a, %q_1_a, %q_2_a, %q_3_a : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_2 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_3 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b, %q_2_b, %q_3_b = qstruct.circuit(%q, %q_1, %q_2, %q_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit, %q_2_a: !qcore.qubit, %q_3_a: !qcore.qubit):
// CHECK-NEXT:      qstruct.parallel<TOP> -> {
// CHECK-NEXT:        qref.gate<#qcore.gate.x> (%q_a, %q_1_a)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      } {
// CHECK-NEXT:        qref.gate<#qcore.gate.h> (%q_2_a, %q_3_a)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a, %q_2_a, %q_3_a : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

builtin.module {
  %q = qcore.alloc_qubit -> !qcore.qubit
  %q_1 = qcore.alloc_qubit -> !qcore.qubit

  // Negative: mixed gate classes across regions, should not merge
  %q_b, %q_1_b = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
  ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit):
    qstruct.parallel<TOP> {} -> {
      qref.reset<Z> (%q_a)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.x> (%q_1_a)
      qstruct.yield
    }
    qstruct.yield %q_a, %q_1_a : !qcore.qubit, !qcore.qubit
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q_b, %q_1_b = qstruct.circuit(%q, %q_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q_a: !qcore.qubit, %q_1_a: !qcore.qubit):
// CHECK-NEXT:      qstruct.parallel<TOP> -> {
// CHECK-NEXT:        qref.reset<Z> (%q_a)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      } {
// CHECK-NEXT:        qref.gate<#qcore.gate.x> (%q_1_a)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield %q_a, %q_1_a : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:  }
