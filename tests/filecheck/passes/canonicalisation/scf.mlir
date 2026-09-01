// RUN: deltakit_compile compile-passes %s -t -p canonicalize -O %t && filecheck %s --input-file %t


builtin.module {
// CHECK:       builtin.module {
    %lb = arith.constant 0 : index
    %ub = arith.constant 10 : index
    %step = arith.constant 2 : index
// CHECK-NEXT:    %lb = arith.constant 0 : index
// CHECK-NEXT:    %ub = arith.constant 10 : index
// CHECK-NEXT:    %step = arith.constant 2 : index

    // lb, ub, and step are all constant and iterator isn't used - convert to repeat
    %c0 = "test.op"() : () -> i32
    %c0_1 = scf.for %iv = %lb  to %ub step %step iter_args(%c0_2 = %c0) -> (i32) {
        %c0_3 = "test.op"(%c0_2) : (i32) -> i32
        scf.yield %c0_3 : i32
    }
// CHECK-NEXT:    %c0 = "test.op"() : () -> i32
// CHECK-NEXT:    %c0_1 = qstruct.repeat<5> (%c0 : i32) -> i32 {
// CHECK-NEXT:    ^bb0(%c0_2: i32):
// CHECK-NEXT:      %c0_3 = "test.op"(%c0_2) : (i32) -> i32
// CHECK-NEXT:      qstruct.yield %c0_3 : i32
// CHECK-NEXT:    }

    // Step isn't constant - leave as-is
    %c1 = "test.op"() : () -> index
    scf.for %iv = %lb to %ub step %c1 {
        "test.op"() : () -> ()
    }
// CHECK-NEXT:    %c1 = "test.op"() : () -> index
// CHECK-NEXT:    scf.for %iv = %lb to %ub step %c1 {
// CHECK-NEXT:      "test.op"() : () -> ()
// CHECK-NEXT:    }

    // Iterator is used - leave as-is
    scf.for %iv = %lb to %ub step %step {
        "test.op"(%iv) : (index) -> ()
    }
// CHECK-NEXT:    scf.for %iv_1 = %lb to %ub step %step {
// CHECK-NEXT:      "test.op"(%iv_1) : (index) -> ()
// CHECK-NEXT:    }
}
// CHECK-NEXT: }
