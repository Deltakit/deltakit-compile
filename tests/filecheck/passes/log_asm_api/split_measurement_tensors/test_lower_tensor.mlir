// RUN: deltakit_compile compile-passes -t %s -p split-measurement-tensors --pass-args '{"permit_unresolved_casts": true, "permit_remaining_measurement_tensors": true}' -O %t && filecheck %s --input-file %t

builtin.module {
    %b0, %b1, %b2 = "test.op"() : () -> (i1, i1, i1)
    %t = builtin.unrealized_conversion_cast %b0, %b1, %b2 : i1, i1, i1 to tensor<10xi1>
    %c = arith.constant 2 : index
    %b2_1 = tensor.extract %t[%c] : tensor<10xi1>
    "test.op"(%b2_1) : (i1) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %b0, %b1, %b2 = "test.op"() : () -> (i1, i1, i1)
// CHECK-NEXT:    "test.op"(%b2) : (i1) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %b0, %b1, %b2 = "test.op"() : () -> (i1, i1, i1)
    %t = builtin.unrealized_conversion_cast %b0, %b1, %b2 : i1, i1, i1 to tensor<10xi1>
    %c = arith.constant 3 : index
    %b2_1 = tensor.extract %t[%c] : tensor<10xi1>
    "test.op"(%b2_1) : (i1) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:      %b0, %b1, %b2 = "test.op"() : () -> (i1, i1, i1)
// CHECK-NEXT:      %t = builtin.unrealized_conversion_cast %b0, %b1, %b2 : i1, i1, i1 to tensor<10xi1>
// CHECK-NEXT:      %c = arith.constant 3 : index
// CHECK-NEXT:      %b2_1 = tensor.extract %t[%c] : tensor<10xi1>
// CHECK-NEXT:      "test.op"(%b2_1) : (i1) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %b0, %b1, %b2 = "test.op"() : () -> (i1, i1, i1)
    %t = tensor.from_elements %b0, %b1, %b2 : tensor<3xi1>
    "test.op"(%t) : (tensor<3xi1>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:      %b0, %b1, %b2 = "test.op"() : () -> (i1, i1, i1)
// CHECK-NEXT:      %t = builtin.unrealized_conversion_cast %b0, %b1, %b2 : i1, i1, i1 to tensor<3xi1>
// CHECK-NEXT:      "test.op"(%t) : (tensor<3xi1>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %i0, %i1, %i2 = "test.op"() : () -> (i32, i32, i32)
    %t = tensor.from_elements %i0, %i1, %i2 : tensor<3xi32>
    "test.op"(%t) : (tensor<3xi32>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:      %i0, %i1, %i2 = "test.op"() : () -> (i32, i32, i32)
// CHECK-NEXT:      %t = tensor.from_elements %i0, %i1, %i2 : tensor<3xi32>
// CHECK-NEXT:      "test.op"(%t) : (tensor<3xi32>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %b0, %b1, %b2, %b3, %b4 = "test.op"() : () -> (i1, i1, i1, i1, i1)
    %t1 = builtin.unrealized_conversion_cast %b0, %b1, %b2 : i1, i1, i1 to tensor<3xi1>
    %t2 = builtin.unrealized_conversion_cast %b3, %b4 : i1, i1 to tensor<2xi1>
    %t = tensor.concat dim(0) %t2, %t1 : (tensor<2xi1>, tensor<3xi1>) -> tensor<5xi1>
    "test.op"(%t) : (tensor<5xi1>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %b0, %b1, %b2, %b3, %b4 = "test.op"() : () -> (i1, i1, i1, i1, i1)
// CHECK-NEXT:    %t = builtin.unrealized_conversion_cast %b3, %b4, %b0, %b1, %b2 : i1, i1, i1, i1, i1 to tensor<5xi1>
// CHECK-NEXT:    "test.op"(%t) : (tensor<5xi1>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %b0, %b1, %b2, %b3, %b4 = "test.op"() : () -> (i1, i1, i1, i1, i1)
    %t1 = builtin.unrealized_conversion_cast %b0, %b1, %b2 : i1, i1, i1 to tensor<3xi1>
    %t2 = builtin.unrealized_conversion_cast %b3, %b4 : i1, i1 to tensor<?xi1>
    %t = tensor.concat dim(0) %t2, %t1 : (tensor<?xi1>, tensor<3xi1>) -> tensor<?xi1>
    "test.op"(%t) : (tensor<?xi1>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %b0, %b1, %b2, %b3, %b4 = "test.op"() : () -> (i1, i1, i1, i1, i1)
// CHECK-NEXT:    %t1 = builtin.unrealized_conversion_cast %b0, %b1, %b2 : i1, i1, i1 to tensor<3xi1>
// CHECK-NEXT:    %t2 = builtin.unrealized_conversion_cast %b3, %b4 : i1, i1 to tensor<?xi1>
// CHECK-NEXT:    %t = tensor.concat dim(0) %t2, %t1 : (tensor<?xi1>, tensor<3xi1>) -> tensor<?xi1>
// CHECK-NEXT:    "test.op"(%t) : (tensor<?xi1>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %b0, %b1, %b2, %b3, %b4 = "test.op"() : () -> (i1, i1, i1, i1, i1)
    %t = builtin.unrealized_conversion_cast %b0, %b1, %b2, %b3, %b4 : i1, i1, i1, i1, i1 to tensor<5xi1>
    %c = arith.constant 0 : index
    %l = tensor.dim %t, %c : tensor<5xi1>
    "test.op"(%l) : (index) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %b0, %b1, %b2, %b3, %b4 = "test.op"() : () -> (i1, i1, i1, i1, i1)
// CHECK-NEXT:    %l = arith.constant 5 : index
// CHECK-NEXT:    "test.op"(%l) : (index) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %b0, %b1, %b2, %b3, %b4 = "test.op"() : () -> (i1, i1, i1, i1, i1)
    %t = builtin.unrealized_conversion_cast %b0, %b1, %b2, %b3, %b4 : i1, i1, i1, i1, i1 to tensor<?xi1>
    %c = arith.constant 0 : index
    %l = tensor.dim %t, %c : tensor<?xi1>
    "test.op"(%l) : (index) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %b0, %b1, %b2, %b3, %b4 = "test.op"() : () -> (i1, i1, i1, i1, i1)
// CHECK-NEXT:    %t = builtin.unrealized_conversion_cast %b0, %b1, %b2, %b3, %b4 : i1, i1, i1, i1, i1 to tensor<?xi1>
// CHECK-NEXT:    %c = arith.constant 0 : index
// CHECK-NEXT:    %l = tensor.dim %t, %c : tensor<?xi1>
// CHECK-NEXT:    "test.op"(%l) : (index) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %b0, %b1, %b2, %b3, %b4 = "test.op"() : () -> (i1, i1, i1, i1, i1)
    %t1 = builtin.unrealized_conversion_cast %b0, %b1, %b2, %b3, %b4 : i1, i1, i1, i1, i1 to tensor<5xi1>
    %t2 = "tensor.extract_slice"(%t1) <{"static_offsets" = array<i64: 1>, "static_sizes" = array<i64: 3>, "static_strides" = array<i64: 1>, operandSegmentSizes = array<i32: 1, 0, 0, 0>}> : (tensor<5xi1>) -> tensor<3xi1>
    "test.op"(%t2) : (tensor<3xi1>) -> ()
    %t3 = "tensor.extract_slice"(%t1) <{"static_offsets" = array<i64: 0>, "static_sizes" = array<i64: 2>, "static_strides" = array<i64: 2>, operandSegmentSizes = array<i32: 1, 0, 0, 0>}> : (tensor<5xi1>) -> tensor<2xi1>
    "test.op"(%t3) : (tensor<2xi1>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %b0, %b1, %b2, %b3, %b4 = "test.op"() : () -> (i1, i1, i1, i1, i1)
// CHECK-NEXT:    %t2 = builtin.unrealized_conversion_cast %b1, %b2, %b3 : i1, i1, i1 to tensor<3xi1>
// CHECK-NEXT:    "test.op"(%t2) : (tensor<3xi1>) -> ()
// CHECK-NEXT:    %t3 = builtin.unrealized_conversion_cast %b0, %b2 : i1, i1 to tensor<2xi1>
// CHECK-NEXT:    "test.op"(%t3) : (tensor<2xi1>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %b0, %b1, %b2, %b3, %b4 = "test.op"() : () -> (i1, i1, i1, i1, i1)
    %t1 = builtin.unrealized_conversion_cast %b0, %b1, %b2, %b3, %b4 : i1, i1, i1, i1, i1 to tensor<5xi1>
    %offset = arith.constant -2 : index
    %half_size = arith.constant 1 : index
    %size = arith.addi %half_size, %half_size : index
    %stride = arith.constant -1 : index
    %t2 = "tensor.extract_slice"(%t1, %offset, %size, %stride) <{static_offsets = array<i64: -9223372036854775808>, static_sizes = array<i64: -9223372036854775808>, static_strides = array<i64: -9223372036854775808>, operandSegmentSizes = array<i32: 1, 1, 1, 1>}> : (tensor<5xi1>, index, index, index) -> tensor<2xi1>
    "test.op"(%t2) : (tensor<2xi1>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %b0, %b1, %b2, %b3, %b4 = "test.op"() : () -> (i1, i1, i1, i1, i1)
// CHECK-NEXT:    %t2 = builtin.unrealized_conversion_cast %b3, %b2 : i1, i1 to tensor<2xi1>
// CHECK-NEXT:    "test.op"(%t2) : (tensor<2xi1>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %i0, %i1, %i2, %i3, %i4 = "test.op"() : () -> (i32, i32, i32, i32, i32)
    %t1 = builtin.unrealized_conversion_cast %i0, %i1, %i2, %i3, %i4 : i32, i32, i32, i32, i32 to tensor<5xi32>
    %t2 = "tensor.extract_slice"(%t1) <{"static_offsets" = array<i64: 1>, "static_sizes" = array<i64: 3>, "static_strides" = array<i64: 1>, operandSegmentSizes = array<i32: 1, 0, 0, 0>}> : (tensor<5xi32>) -> tensor<3xi32>
    "test.op"(%t2) : (tensor<3xi32>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %i0, %i1, %i2, %i3, %i4 = "test.op"() : () -> (i32, i32, i32, i32, i32)
// CHECK-NEXT:    %t1 = builtin.unrealized_conversion_cast %i0, %i1, %i2, %i3, %i4 : i32, i32, i32, i32, i32 to tensor<5xi32>
// CHECK-NEXT:    %t2 = "tensor.extract_slice"(%t1) <{static_offsets = array<i64: 1>, static_sizes = array<i64: 3>, static_strides = array<i64: 1>, operandSegmentSizes = array<i32: 1, 0, 0, 0>}> : (tensor<5xi32>) -> tensor<3xi32>
// CHECK-NEXT:    "test.op"(%t2) : (tensor<3xi32>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %b0, %b1, %b2, %b3, %b4 = "test.op"() : () -> (i1, i1, i1, i1, i1)
    %t1 = builtin.unrealized_conversion_cast %b0, %b1, %b2, %b3, %b4 : i1, i1, i1, i1, i1 to tensor<5xi1>
    %t2 = "tensor.extract_slice"(%t1) <{static_offsets = array<i64: 0, 0>, static_sizes = array<i64: 1, 1>, static_strides = array<i64: 1, 1>, operandSegmentSizes = array<i32: 1, 0, 0, 0>}> : (tensor<5xi1>) -> tensor<1x1xi1>
    "test.op"(%t2) : (tensor<1x1xi1>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %b0, %b1, %b2, %b3, %b4 = "test.op"() : () -> (i1, i1, i1, i1, i1)
// CHECK-NEXT:    %t1 = builtin.unrealized_conversion_cast %b0, %b1, %b2, %b3, %b4 : i1, i1, i1, i1, i1 to tensor<5xi1>
// CHECK-NEXT:    %t2 = "tensor.extract_slice"(%t1) <{static_offsets = array<i64: 0, 0>, static_sizes = array<i64: 1, 1>, static_strides = array<i64: 1, 1>, operandSegmentSizes = array<i32: 1, 0, 0, 0>}> : (tensor<5xi1>) -> tensor<1x1xi1>
// CHECK-NEXT:    "test.op"(%t2) : (tensor<1x1xi1>) -> ()
// CHECK-NEXT:  }
