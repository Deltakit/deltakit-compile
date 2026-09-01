// RUN: deltakit_compile compile-passes %s -p parallelise-circuit -O %t && filecheck %s --input-file %t

builtin.module {
    %q = stim.qubit_alloc 0 -> !stim.qubit
    %q_1 = stim.qubit_alloc 1 -> !stim.qubit
    %q_2 = stim.qubit_alloc 2 -> !stim.qubit

    // Should parallelise twice
    stim.clifford X (%q)
    stim.clifford X (%q_1)
    stim.clifford X (%q)
    stim.clifford X (%q_1)

    stim.tick

    // Shouldn't parallelise due to shared qubit
    stim.clifford CX (%q, %q_1)
    stim.clifford CZ (%q_1, %q_2)

    stim.shift_coord <[0.0, 0.0, 1.0]>

    // Should parallelise with SSAValue passing out of the new parallel to the detector
    %rec, %rec_1 = stim.measure Z (%q, %q_1) -> i1, i1
    %rec_2 = stim.measure Z (%q_2) -> i1
    stim.detector <[0.0, 0.0]> (%rec, %rec_1, %rec_2 : i1, i1, i1)

    // Should only parallelise inside the repeat
    stim.clifford X (%q)
    stim.repeat 26  {
        stim.clifford X (%q_1)
        stim.clifford X (%q_2)
        stim.yield
    }
    stim.clifford X (%q)
}

// CHECK:       builtin.module {
// CHECK-NEXT:    %q = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:    %q_1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:    %q_2 = stim.qubit_alloc 2 -> !stim.qubit
// CHECK-NEXT:    qstruct.parallel<TOP> -> {
// CHECK-NEXT:      stim.clifford X (%q)
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    } {
// CHECK-NEXT:      stim.clifford X (%q_1)
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    }
// CHECK-NEXT:    qstruct.parallel<TOP> -> {
// CHECK-NEXT:      stim.clifford X (%q)
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    } {
// CHECK-NEXT:      stim.clifford X (%q_1)
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    }
// CHECK-NEXT:    stim.tick
// CHECK-NEXT:    stim.clifford CX (%q, %q_1)
// CHECK-NEXT:    stim.clifford CZ (%q_1, %q_2)
// CHECK-NEXT:    stim.shift_coord <[0.0, 0.0, 1.0]>
// CHECK-NEXT:    %rec, %rec_1, %rec_2 = qstruct.parallel<TOP> -> i1, i1, i1 {
// CHECK-NEXT:      %rec_3, %rec_4 = stim.measure Z (%q, %q_1) -> i1, i1
// CHECK-NEXT:      qstruct.yield %rec_3, %rec_4 : i1, i1
// CHECK-NEXT:    } {
// CHECK-NEXT:      %rec_5 = stim.measure Z (%q_2) -> i1
// CHECK-NEXT:      qstruct.yield %rec_5 : i1
// CHECK-NEXT:    }
// CHECK-NEXT:    stim.detector <[0.0, 0.0]> (%rec, %rec_1, %rec_2 : i1, i1, i1)
// CHECK-NEXT:    stim.clifford X (%q)
// CHECK-NEXT:    stim.repeat 26 () {
// CHECK-NEXT:      qstruct.parallel<TOP> -> {
// CHECK-NEXT:        stim.clifford X (%q_1)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      } {
// CHECK-NEXT:        stim.clifford X (%q_2)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      }
// CHECK-NEXT:      stim.yield
// CHECK-NEXT:    }
// CHECK-NEXT:    stim.clifford X (%q)
// CHECK-NEXT:  }
