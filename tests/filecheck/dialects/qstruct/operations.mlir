// RUN: ROUNDTRIP_MLIR

builtin.module {
    // Circuit op roundtripping
    qstruct.circuit -> {
        qstruct.yield
    }

    %0 = "test.op"() : () -> i32
    %1 = qstruct.circuit(%0 : i32) -> i64 {
    ^bb0(%2: i32):
        %3 = "test.op"(%2) : (i32) -> i64
        qstruct.yield %3 : i64
    }

    // Parallel op roundtripping
    %q = stim.qubit_alloc 0 -> !stim.qubit
    %q_1 = stim.qubit_alloc 1 -> !stim.qubit
    %q_2 = stim.qubit_alloc 2 -> !stim.qubit

    %rec_g, %rec_1g, %rec_2g = qstruct.parallel<TOP> -> i1, i1, i1 {
        stim.clifford X (%q)
        %rec = stim.measure Z (%q) -> i1
        qstruct.yield %rec : i1
    } {
        stim.clifford X (%q_1)
        stim.clifford X (%q_2)
        %rec_1, %rec_2 = stim.measure Z (%q_1, %q_2) -> i1, i1
        qstruct.yield %rec_1, %rec_2 : i1, i1
    }

    // Repeat op roundtripping
    qstruct.repeat<2> -> {
        "test.op"(%0) : (i32) -> ()
        qstruct.yield
    }

    %4 = "test.op"() : () -> i32
    %5 = qstruct.repeat<2> (%4 : i32) -> i32 {
    ^bb0(%6: i32):
        "test.op"(%6) : (i32) -> ()
        qstruct.yield %6 : i32
    }

    // Output op roundtripping
    qstruct.output(%0, %1 : i32, i64)
}

// CHECK:       builtin.module {
// CHECK-NEXT:      qstruct.circuit -> {
// CHECK-NEXT:          qstruct.yield
// CHECK-NEXT:      }

// CHECK:           %0 = "test.op"() : () -> i32
// CHECK-NEXT:      %1 = qstruct.circuit(%0 : i32) -> i64 {
// CHECK-NEXT:      ^bb0(%2: i32):
// CHECK-NEXT:          %3 = "test.op"(%2) : (i32) -> i64
// CHECK-NEXT:          qstruct.yield %3 : i64
// CHECK-NEXT:      }

// CHECK-NEXT:    %q = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:    %q_1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:    %q_2 = stim.qubit_alloc 2 -> !stim.qubit
// CHECK-NEXT:    %rec_g, %rec_1g, %rec_2g = qstruct.parallel<TOP> -> i1, i1, i1 {
// CHECK-NEXT:      stim.clifford X (%q)
// CHECK-NEXT:      %rec = stim.measure Z (%q) -> i1
// CHECK-NEXT:      qstruct.yield %rec : i1
// CHECK-NEXT:    } {
// CHECK-NEXT:      stim.clifford X (%q_1)
// CHECK-NEXT:      stim.clifford X (%q_2)
// CHECK-NEXT:      %rec_1, %rec_2 = stim.measure Z (%q_1, %q_2) -> i1, i1
// CHECK-NEXT:      qstruct.yield %rec_1, %rec_2 : i1, i1
// CHECK-NEXT:    }

// CHECK-NEXT:    qstruct.repeat<2> () -> {
// CHECK-NEXT:      "test.op"(%0) : (i32) -> ()
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    }

// CHECK-NEXT:    %2 = "test.op"() : () -> i32
// CHECK-NEXT:    %3 = qstruct.repeat<2> (%2 : i32) -> i32 {
// CHECK-NEXT:    ^bb0(%4: i32):
// CHECK-NEXT:      "test.op"(%4) : (i32) -> ()
// CHECK-NEXT:      qstruct.yield %4 : i32
// CHECK-NEXT:    }

// CHECK-NEXT:    qstruct.output(%0, %1 : i32, i64)

// CHECK-NEXT:  }
