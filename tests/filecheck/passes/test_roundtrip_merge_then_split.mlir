// RUN: deltakit_compile compile-passes %s -p merge-gate-like-broadcast-ops -p split-gate-like-broadcast-ops -O %t && filecheck %s --input-file %t

// === Roundtrip: merge then split should preserve the original IR (single gate class) ===

// Case 1: single-qubit clifford X regions
builtin.module {
  %q0 = stim.qubit_alloc 0 -> !stim.qubit
  %q1 = stim.qubit_alloc 1 -> !stim.qubit

  qstruct.parallel<TOP> {} -> {
    stim.clifford X (%q0)
    qstruct.yield
  } {
    stim.clifford X (%q1)
    qstruct.yield
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:    %q1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:    qstruct.parallel<TOP> -> {
// CHECK-NEXT:      stim.clifford X (%q0)
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    } {
// CHECK-NEXT:      stim.clifford X (%q1)
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

// Case 2: reset Z regions
builtin.module {
  %q0 = stim.qubit_alloc 0 -> !stim.qubit
  %q1 = stim.qubit_alloc 1 -> !stim.qubit

  qstruct.parallel<TOP> {} -> {
    stim.reset Z (%q0)
    qstruct.yield
  } {
    stim.reset Z (%q1)
    qstruct.yield
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:    %q1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:    qstruct.parallel<TOP> -> {
// CHECK-NEXT:      stim.reset Z (%q0)
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    } {
// CHECK-NEXT:      stim.reset Z (%q1)
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

// Case 3: measurement Z regions (with results)
builtin.module {
  %q0 = stim.qubit_alloc 0 -> !stim.qubit
  %q1 = stim.qubit_alloc 1 -> !stim.qubit

  %m0, %m1 = qstruct.parallel<TOP> {} -> i1, i1 {
    %mz0 = stim.measure Z (%q0) -> i1
    qstruct.yield %mz0 : i1
  } {
    %mz1 = stim.measure Z (%q1) -> i1
    qstruct.yield %mz1 : i1
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:    %q1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:    %m0, %m1 = qstruct.parallel<TOP> -> i1, i1 {
// CHECK-NEXT:      %[[M0:.*]] = stim.measure Z (%q0) -> i1
// CHECK-NEXT:      qstruct.yield %[[M0]] : i1
// CHECK-NEXT:    } {
// CHECK-NEXT:      %[[M1:.*]] = stim.measure Z (%q1) -> i1
// CHECK-NEXT:      qstruct.yield %[[M1]] : i1
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

// Case 4: no-change case with different gate types in regions (H vs reset Z)
builtin.module {
  %q0 = stim.qubit_alloc 0 -> !stim.qubit
  %q1 = stim.qubit_alloc 1 -> !stim.qubit

  qstruct.parallel<TOP> {} -> {
    stim.clifford H (%q0)
    qstruct.yield
  } {
    stim.reset Z (%q1)
    qstruct.yield
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:    %q1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:    qstruct.parallel<TOP> -> {
// CHECK-NEXT:      stim.clifford H (%q0)
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    } {
// CHECK-NEXT:      stim.reset Z (%q1)
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----

// Case 5: nested parallel inside a parallel; inner has identical gates
builtin.module {
  %q0 = stim.qubit_alloc 0 -> !stim.qubit
  %q1 = stim.qubit_alloc 1 -> !stim.qubit

  qstruct.parallel<TOP> {} -> {
    qstruct.parallel<TOP> {} -> {
      stim.clifford X (%q0)
      qstruct.yield
    } {
      stim.clifford X (%q1)
      qstruct.yield
    }
    qstruct.yield
  } {
    stim.reset Z (%q0)
    qstruct.yield
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:    %q1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:    qstruct.parallel<TOP> -> {
// CHECK-NEXT:      qstruct.parallel<TOP> -> {
// CHECK-NEXT:        stim.clifford X (%q0)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      } {
// CHECK-NEXT:        stim.clifford X (%q1)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    } {
// CHECK-NEXT:      stim.reset Z (%q0)
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    }
// CHECK-NEXT:  }
