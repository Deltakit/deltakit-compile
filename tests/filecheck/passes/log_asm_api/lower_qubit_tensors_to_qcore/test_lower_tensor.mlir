// RUN: deltakit_compile compile-passes -t %s -p lower-qubit-tensors-to-qcore --pass-args '{"permit_unresolved_casts": true, "permit_remaining_qubit_tensors": true}' -O %t && filecheck %s --input-file %t



builtin.module {
    %r = "test.op"() : () -> (!qcore.qubit_reg<10>)
    %t = builtin.unrealized_conversion_cast %r : !qcore.qubit_reg<10> to tensor<?x!qcore.qubit>
    %c = arith.constant 5 : index
    %q = tensor.extract %t[%c] : tensor<?x!qcore.qubit>
    "test.op"(%q) : (!qcore.qubit) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %r = "test.op"() : () -> !qcore.qubit_reg<10>
// CHECK-NEXT:    %q, %q_1, %q_2, %q_3, %q_4, %q_5, %q_6, %q_7, %q_8, %q_9 = qcore.unpack_qubit_reg(%r : !qcore.qubit_reg<10>)
// CHECK-NEXT:    "test.op"(%q_5) : (!qcore.qubit) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %r = "test.op"() : () -> (!qcore.qubit_reg<3>)
    %t = builtin.unrealized_conversion_cast %r : !qcore.qubit_reg<3> to tensor<?x!qcore.qubit>
    %c = arith.constant 2 : index
    %q = tensor.extract %t[%c] : tensor<?x!qcore.qubit>
    "test.op"(%q) : (!qcore.qubit) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %r = "test.op"() : () -> !qcore.qubit_reg<3>
// CHECK-NEXT:    %q, %q_1, %q_2 = qcore.unpack_qubit_reg(%r : !qcore.qubit_reg<3>)
// CHECK-NEXT:    "test.op"(%q_2) : (!qcore.qubit) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %r = "test.op"() : () -> (!qcore.qubit_reg<3>)
    %t = builtin.unrealized_conversion_cast %r : !qcore.qubit_reg<3> to tensor<?x!qcore.qubit>
    %c = arith.constant 20 : index
    %q = tensor.extract %t[%c] : tensor<?x!qcore.qubit>
    "test.op"(%q) : (!qcore.qubit) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:      %r = "test.op"() : () -> !qcore.qubit_reg<3>
// CHECK-NEXT:      %t = builtin.unrealized_conversion_cast %r : !qcore.qubit_reg<3> to tensor<?x!qcore.qubit>
// CHECK-NEXT:      %c = arith.constant 20 : index
// CHECK-NEXT:      %q = tensor.extract %t[%c] : tensor<?x!qcore.qubit>
// CHECK-NEXT:      "test.op"(%q) : (!qcore.qubit) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %q0, %q1, %q2 = "test.op"() : () -> (!qcore.qubit, !qcore.qubit, !qcore.qubit)
    %t = tensor.from_elements %q0, %q1, %q2 : tensor<3x!qcore.qubit>
    "test.op"(%t) : (tensor<3x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:      %q0, %q1, %q2 = "test.op"() : () -> (!qcore.qubit, !qcore.qubit, !qcore.qubit)
// CHECK-NEXT:      %t = qcore.pack_qubit_reg(%q0, %q1, %q2) -> !qcore.qubit_reg<3>
// CHECK-NEXT:      %t_1 = builtin.unrealized_conversion_cast %t : !qcore.qubit_reg<3> to tensor<3x!qcore.qubit>
// CHECK-NEXT:      "test.op"(%t_1) : (tensor<3x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %i0, %i1, %i2 = "test.op"() : () -> (i1, i1, i1)
    %t = tensor.from_elements %i0, %i1, %i2 : tensor<3xi1>
    "test.op"(%t) : (tensor<3xi1>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:      %i0, %i1, %i2 = "test.op"() : () -> (i1, i1, i1)
// CHECK-NEXT:      %t = tensor.from_elements %i0, %i1, %i2 : tensor<3xi1>
// CHECK-NEXT:      "test.op"(%t) : (tensor<3xi1>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %r1, %r2 = "test.op"() : () -> (!qcore.qubit_reg<3>, !qcore.qubit_reg<4>)
    %t1 = builtin.unrealized_conversion_cast %r1 : !qcore.qubit_reg<3> to tensor<3x!qcore.qubit>
    %t2 = builtin.unrealized_conversion_cast %r2 : !qcore.qubit_reg<4> to tensor<?x!qcore.qubit>
    %t = tensor.concat dim(0) %t1, %t2 : (tensor<3x!qcore.qubit>, tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
    "test.op"(%t) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %r1, %r2 = "test.op"() : () -> (!qcore.qubit_reg<3>, !qcore.qubit_reg<4>)
// CHECK-NEXT:    %t = qcore.concatenate(%r1, %r2 : !qcore.qubit_reg<3>, !qcore.qubit_reg<4>) -> !qcore.qubit_reg<7>
// CHECK-NEXT:    %t_1 = builtin.unrealized_conversion_cast %t : !qcore.qubit_reg<7> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%t_1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %r1, %t2 = "test.op"() : () -> (!qcore.qubit_reg<3>, tensor<?x!qcore.qubit>)
    %t1 = builtin.unrealized_conversion_cast %r1 : !qcore.qubit_reg<3> to tensor<?x!qcore.qubit>
    %t = tensor.concat dim(0) %t1, %t2 : (tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
    "test.op"(%t) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %r1, %t2 = "test.op"() : () -> (!qcore.qubit_reg<3>, tensor<?x!qcore.qubit>)
// CHECK-NEXT:    %t1 = builtin.unrealized_conversion_cast %r1 : !qcore.qubit_reg<3> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    %t = tensor.concat dim(0) %t1, %t2 : (tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%t) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %r1 = "test.op"() : () -> !qcore.qubit_reg<4>
    %t = builtin.unrealized_conversion_cast %r1 : !qcore.qubit_reg<4> to tensor<?x!qcore.qubit>
    %c = arith.constant 0 : index
    %l = tensor.dim %t, %c : tensor<?x!qcore.qubit>
    "test.op"(%l) : (index) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %r1 = "test.op"() : () -> !qcore.qubit_reg<4>
// CHECK-NEXT:    %l = arith.constant 4 : index
// CHECK-NEXT:    "test.op"(%l) : (index) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %r1 = "test.op"() : () -> !qcore.qubit_reg<4>
    %t = builtin.unrealized_conversion_cast %r1 : !qcore.qubit_reg<4> to tensor<?x?x!qcore.qubit>
    %c = arith.constant 1 : index
    %l = tensor.dim %t, %c : tensor<?x?x!qcore.qubit>
    "test.op"(%l) : (index) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %r1 = "test.op"() : () -> !qcore.qubit_reg<4>
// CHECK-NEXT:    %t = builtin.unrealized_conversion_cast %r1 : !qcore.qubit_reg<4> to tensor<?x?x!qcore.qubit>
// CHECK-NEXT:    %c = arith.constant 1 : index
// CHECK-NEXT:    %l = tensor.dim %t, %c : tensor<?x?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%l) : (index) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %r = "test.op"() : () -> (!qcore.qubit_reg<10>)
    %t1 = builtin.unrealized_conversion_cast %r : !qcore.qubit_reg<10> to tensor<?x!qcore.qubit>
    %t2 = "tensor.extract_slice"(%t1) <{"static_offsets" = array<i64: 1>, "static_sizes" = array<i64: 3>, "static_strides" = array<i64: 1>, operandSegmentSizes = array<i32: 1, 0, 0, 0>}> : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
    "test.op"(%t2) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %r = "test.op"() : () -> !qcore.qubit_reg<10>
// CHECK-NEXT:    %t2, %t2_1, %t2_2, %t2_3, %t2_4, %t2_5, %t2_6, %t2_7, %t2_8, %t2_9 = qcore.unpack_qubit_reg(%r : !qcore.qubit_reg<10>)
// CHECK-NEXT:    %t2_10 = qcore.pack_qubit_reg(%t2_1, %t2_2, %t2_3) -> !qcore.qubit_reg<3>
// CHECK-NEXT:    %t2_11 = builtin.unrealized_conversion_cast %t2_10 : !qcore.qubit_reg<3> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%t2_11) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %r = "test.op"() : () -> (!qcore.qubit_reg<10>)
    %t1 = builtin.unrealized_conversion_cast %r : !qcore.qubit_reg<10> to tensor<?x!qcore.qubit>
    %t2 = "tensor.extract_slice"(%t1) <{static_offsets = array<i64: 2>, static_sizes = array<i64: 4>, static_strides = array<i64: 2>, operandSegmentSizes = array<i32: 1, 0, 0, 0>}> : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
    "test.op"(%t2) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %r = "test.op"() : () -> !qcore.qubit_reg<10>
// CHECK-NEXT:    %t2, %t2_1, %t2_2, %t2_3, %t2_4, %t2_5, %t2_6, %t2_7, %t2_8, %t2_9 = qcore.unpack_qubit_reg(%r : !qcore.qubit_reg<10>)
// CHECK-NEXT:    %t2_10 = qcore.pack_qubit_reg(%t2_2, %t2_4, %t2_6, %t2_8) -> !qcore.qubit_reg<4>
// CHECK-NEXT:    %t2_11 = builtin.unrealized_conversion_cast %t2_10 : !qcore.qubit_reg<4> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%t2_11) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %r = "test.op"() : () -> (!qcore.qubit_reg<10>)
    %t1 = builtin.unrealized_conversion_cast %r : !qcore.qubit_reg<10> to tensor<?x!qcore.qubit>
    %offset = arith.constant -2 : index
    %size = arith.constant 2 : index
    %stride = arith.constant -3 : index
    %t2 = "tensor.extract_slice"(%t1, %offset, %size, %stride) <{static_offsets = array<i64: -9223372036854775808>, static_sizes = array<i64: -9223372036854775808>, static_strides = array<i64: -9223372036854775808>, operandSegmentSizes = array<i32: 1, 1, 1, 1>}> : (tensor<?x!qcore.qubit>, index, index, index) -> tensor<?x!qcore.qubit>
    "test.op"(%t2) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %r = "test.op"() : () -> !qcore.qubit_reg<10>
// CHECK-NEXT:    %t2, %t2_1, %t2_2, %t2_3, %t2_4, %t2_5, %t2_6, %t2_7, %t2_8, %t2_9 = qcore.unpack_qubit_reg(%r : !qcore.qubit_reg<10>)
// CHECK-NEXT:    %t2_10 = qcore.pack_qubit_reg(%t2_8, %t2_5) -> !qcore.qubit_reg<2>
// CHECK-NEXT:    %t2_11 = builtin.unrealized_conversion_cast %t2_10 : !qcore.qubit_reg<2> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%t2_11) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %r = "test.op"() : () -> (!qcore.qubit_reg<10>)
    %t1 = builtin.unrealized_conversion_cast %r : !qcore.qubit_reg<10> to tensor<?x!qcore.qubit>
    %offset = arith.constant -2 : index
    %size_half = arith.constant 1 : index
    %size = arith.addi %size_half, %size_half : index
    %stride = arith.constant -3 : index
    %t2 = "tensor.extract_slice"(%t1, %offset, %size, %stride) <{static_offsets = array<i64: -9223372036854775808>, static_sizes = array<i64: -9223372036854775808>, static_strides = array<i64: -9223372036854775808>, operandSegmentSizes = array<i32: 1, 1, 1, 1>}> : (tensor<?x!qcore.qubit>, index, index, index) -> tensor<?x!qcore.qubit>
    "test.op"(%t2) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %r = "test.op"() : () -> !qcore.qubit_reg<10>
// CHECK-NEXT:    %t2, %t2_1, %t2_2, %t2_3, %t2_4, %t2_5, %t2_6, %t2_7, %t2_8, %t2_9 = qcore.unpack_qubit_reg(%r : !qcore.qubit_reg<10>)
// CHECK-NEXT:    %t2_10 = qcore.pack_qubit_reg(%t2_8, %t2_5) -> !qcore.qubit_reg<2>
// CHECK-NEXT:    %t2_11 = builtin.unrealized_conversion_cast %t2_10 : !qcore.qubit_reg<2> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%t2_11) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %r = "test.op"() : () -> tensor<3x4xi1>
    %t2 = "tensor.extract_slice"(%r) <{static_offsets = array<i64: 0, 0>, static_sizes = array<i64: 1, 1>, static_strides = array<i64: 1, 1>, operandSegmentSizes = array<i32: 1, 0, 0, 0>}> : (tensor<3x4xi1>) -> tensor<1x1xi1>
    "test.op"(%t2) : (tensor<1x1xi1>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:      %r = "test.op"() : () -> tensor<3x4xi1>
// CHECK-NEXT:      %t2 = "tensor.extract_slice"(%r) <{static_offsets = array<i64: 0, 0>, static_sizes = array<i64: 1, 1>, static_strides = array<i64: 1, 1>, operandSegmentSizes = array<i32: 1, 0, 0, 0>}> : (tensor<3x4xi1>) -> tensor<1x1xi1>
// CHECK-NEXT:      "test.op"(%t2) : (tensor<1x1xi1>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %r = "test.op"() : () -> !qcore.qubit_reg<10>
    %t = builtin.unrealized_conversion_cast %r : !qcore.qubit_reg<10> to tensor<?x!qcore.qubit>
    %t2 = "tensor.extract_slice"(%t) <{static_offsets = array<i64: 0, 0>, static_sizes = array<i64: 1, 1>, static_strides = array<i64: 1, 1>, operandSegmentSizes = array<i32: 1, 0, 0, 0>}> : (tensor<?x!qcore.qubit>) -> tensor<1x1x!qcore.qubit>
    "test.op"(%t2) : (tensor<1x1x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:      %r = "test.op"() : () -> !qcore.qubit_reg<10>
// CHECK-NEXT:      %t = builtin.unrealized_conversion_cast %r : !qcore.qubit_reg<10> to tensor<?x!qcore.qubit>
// CHECK-NEXT:      %t2 = "tensor.extract_slice"(%t) <{static_offsets = array<i64: 0, 0>, static_sizes = array<i64: 1, 1>, static_strides = array<i64: 1, 1>, operandSegmentSizes = array<i32: 1, 0, 0, 0>}> : (tensor<?x!qcore.qubit>) -> tensor<1x1x!qcore.qubit>
// CHECK-NEXT:      "test.op"(%t2) : (tensor<1x1x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %r = "test.op"() : () -> !qcore.qubit_reg<10>
    %t1 = builtin.unrealized_conversion_cast %r : !qcore.qubit_reg<10> to tensor<?x?x!qcore.qubit>
    %offset = arith.constant -2 : index
    %size = arith.constant 2 : index
    %stride = arith.constant -3 : index
    %t2 = "tensor.extract_slice"(%t1, %offset, %size, %size, %stride) <{static_offsets = array<i64: -9223372036854775808, 0>, static_sizes = array<i64: -9223372036854775808, -9223372036854775808>, static_strides = array<i64: -9223372036854775808, 1>, operandSegmentSizes = array<i32: 1, 1, 2, 1>}> : (tensor<?x?x!qcore.qubit>, index, index, index, index) -> tensor<?x?x!qcore.qubit>
    "test.op"(%t2) : (tensor<?x?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:      %r = "test.op"() : () -> !qcore.qubit_reg<10>
// CHECK-NEXT:      %t1 = builtin.unrealized_conversion_cast %r : !qcore.qubit_reg<10> to tensor<?x?x!qcore.qubit>
// CHECK-NEXT:      %offset = arith.constant -2 : index
// CHECK-NEXT:      %size = arith.constant 2 : index
// CHECK-NEXT:      %stride = arith.constant -3 : index
// CHECK-NEXT:      %t2 = "tensor.extract_slice"(%t1, %offset, %size, %size, %stride) <{static_offsets = array<i64: -9223372036854775808, 0>, static_sizes = array<i64: -9223372036854775808, -9223372036854775808>, static_strides = array<i64: -9223372036854775808, 1>, operandSegmentSizes = array<i32: 1, 1, 2, 1>}> : (tensor<?x?x!qcore.qubit>, index, index, index, index) -> tensor<?x?x!qcore.qubit>
// CHECK-NEXT:      "test.op"(%t2) : (tensor<?x?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }
