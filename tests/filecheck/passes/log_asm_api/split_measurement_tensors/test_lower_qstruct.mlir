// RUN: deltakit_compile compile-passes -t %s -p split-measurement-tensors --pass-args '{"permit_unresolved_casts": true, "permit_remaining_measurement_tensors": true}' -O %t && filecheck %s --input-file %t

builtin.module {
    %b0, %b1, %b2 = "test.op"() : () -> (i1, i1, i1)
    %t = builtin.unrealized_conversion_cast %b0, %b1, %b2 : i1, i1, i1 to tensor<3xi1>
    %t2 = qstruct.circuit(%t : tensor<3xi1>) -> tensor<3xi1> {
        ^bb0(%t1 : tensor<3xi1>):
            "test.op"(%t1) : (tensor<3xi1>) -> ()
            qstruct.yield %t1 : tensor<3xi1>
    }
    "test.op"(%t2) : (tensor<3xi1>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %b0, %b1, %b2 = "test.op"() : () -> (i1, i1, i1)
// CHECK-NEXT:    %0, %1, %2 = qstruct.circuit(%b0, %b1, %b2 : i1, i1, i1) -> i1, i1, i1 {
// CHECK-NEXT:    ^bb0(%3: i1, %4: i1, %5: i1):
// CHECK-NEXT:      %t1 = builtin.unrealized_conversion_cast %3, %4, %5 : i1, i1, i1 to tensor<3xi1>
// CHECK-NEXT:      "test.op"(%t1) : (tensor<3xi1>) -> ()
// CHECK-NEXT:      qstruct.yield %3, %4, %5 : i1, i1, i1
// CHECK-NEXT:    }
// CHECK-NEXT:    %t2 = builtin.unrealized_conversion_cast %0, %1, %2 : i1, i1, i1 to tensor<3xi1>
// CHECK-NEXT:    "test.op"(%t2) : (tensor<3xi1>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %b0, %b1, %b2, %b3, %b4 = "test.op"() : () -> (i1, i1, i1, i1, i1)
    %i0, %i1, %i2 = "test.op"() : () -> (i32, i32, i32)
    %t = builtin.unrealized_conversion_cast %b0, %b1, %b2 : i1, i1, i1 to tensor<3xi1>
    %t1 = builtin.unrealized_conversion_cast %b3, %b4 : i1, i1 to tensor<2xi1>
    %i0_1, %t_1, %i1_1, %t1_1, %i2_1 = qstruct.circuit(%i0, %t, %i1, %t1, %i2 : i32, tensor<3xi1>, i32, tensor<2xi1>, i32) -> i32, tensor<3xi1>, i32, tensor<2xi1>, i32 {
        ^bb0(%i0_2 : i32, %t_2 : tensor<3xi1>, %i1_2 : i32, %t1_2 : tensor<2xi1>, %i2_2 : i32):
            "test.op"(%i0_2, %t_2, %i1_2, %t1_2, %i2_2) : (i32, tensor<3xi1>, i32, tensor<2xi1>, i32) -> ()
            qstruct.yield %i0_2, %t_2, %i1_2, %t1_2, %i2_2 : i32, tensor<3xi1>, i32, tensor<2xi1>, i32
    }
    "test.op"(%i0_1, %t_1, %i1_1, %t1_1, %i2_1) : (i32, tensor<3xi1>, i32, tensor<2xi1>, i32) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %b0, %b1, %b2, %b3, %b4 = "test.op"() : () -> (i1, i1, i1, i1, i1)
// CHECK-NEXT:    %i0, %i1, %i2 = "test.op"() : () -> (i32, i32, i32)
// CHECK-NEXT:    %i0_1, %0, %1, %2, %i1_1, %3, %4, %i2_1 = qstruct.circuit(%i0, %b0, %b1, %b2, %i1, %b3, %b4, %i2 : i32, i1, i1, i1, i32, i1, i1, i32) -> i32, i1, i1, i1, i32, i1, i1, i32 {
// CHECK-NEXT:    ^bb0(%i0_2: i32, %5: i1, %6: i1, %7: i1, %i1_2: i32, %8: i1, %9: i1, %i2_2: i32):
// CHECK-NEXT:      %t1 = builtin.unrealized_conversion_cast %8, %9 : i1, i1 to tensor<2xi1>
// CHECK-NEXT:      %t = builtin.unrealized_conversion_cast %5, %6, %7 : i1, i1, i1 to tensor<3xi1>
// CHECK-NEXT:      "test.op"(%i0_2, %t, %i1_2, %t1, %i2_2) : (i32, tensor<3xi1>, i32, tensor<2xi1>, i32) -> ()
// CHECK-NEXT:      qstruct.yield %i0_2, %5, %6, %7, %i1_2, %8, %9, %i2_2 : i32, i1, i1, i1, i32, i1, i1, i32
// CHECK-NEXT:    }
// CHECK-NEXT:    %t1 = builtin.unrealized_conversion_cast %3, %4 : i1, i1 to tensor<2xi1>
// CHECK-NEXT:    %t = builtin.unrealized_conversion_cast %0, %1, %2 : i1, i1, i1 to tensor<3xi1>
// CHECK-NEXT:    "test.op"(%i0_1, %t, %i1_1, %t1, %i2_1) : (i32, tensor<3xi1>, i32, tensor<2xi1>, i32) -> ()
// CHECK-NEXT:  }
