// RUN: deltakit_compile compile-passes %s -p split-gate-like-broadcast-ops -p merge-gate-like-broadcast-ops -O %t && filecheck %s --input-file %t

// === Roundtrip: split then merge should preserve the original IR (single gate class) ===

// Case 1: broadcast single-qubit clifford X
builtin.module {
  %q0 = stim.qubit_alloc 0 -> !stim.qubit
  %q1 = stim.qubit_alloc 1 -> !stim.qubit

  stim.clifford X (%q0, %q1)
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:    %q1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:    stim.clifford X (%q0, %q1)
// CHECK-NEXT:  }

// ----

// Case 2: broadcast reset Z
builtin.module {
  %q0 = stim.qubit_alloc 0 -> !stim.qubit
  %q1 = stim.qubit_alloc 1 -> !stim.qubit

  stim.reset Z (%q0, %q1)
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:    %q1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:    stim.reset Z (%q0, %q1)
// CHECK-NEXT:  }

// ----

// Case 3: broadcast measurement Z (with results)
builtin.module {
  %q0 = stim.qubit_alloc 0 -> !stim.qubit
  %q1 = stim.qubit_alloc 1 -> !stim.qubit

  %m0, %m1 = stim.measure Z (%q0, %q1) -> i1, i1
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:    %q1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:    %m0, %m1 = stim.measure Z (%q0, %q1) -> i1, i1
// CHECK-NEXT:  }

// ----

// Case 4: broadcast gate nested inside a parallel region should roundtrip
builtin.module {
  %q0 = stim.qubit_alloc 0 -> !stim.qubit
  %q1 = stim.qubit_alloc 1 -> !stim.qubit
  %q2 = stim.qubit_alloc 2 -> !stim.qubit

  qstruct.parallel<TOP> {} -> {
    // Nested broadcast X
    stim.clifford X (%q0, %q1)
    qstruct.yield
  } {
    stim.reset Z (%q2)
    qstruct.yield
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:    %q0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:    %q1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:    %q2 = stim.qubit_alloc 2 -> !stim.qubit
// CHECK-NEXT:    qstruct.parallel<TOP> -> {
// CHECK-NEXT:      stim.clifford X (%q0, %q1)
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    } {
// CHECK-NEXT:      stim.reset Z (%q2)
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    }
// CHECK-NEXT:  }
