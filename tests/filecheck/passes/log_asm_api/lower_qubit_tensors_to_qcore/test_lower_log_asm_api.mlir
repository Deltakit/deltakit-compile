// RUN: deltakit_compile compile-passes -t %s -p lower-qubit-tensors-to-qcore --pass-args '{"permit_unresolved_casts": true, "permit_remaining_qubit_tensors": true}' -O %t && filecheck %s --input-file %t


builtin.module {
    %p0 = "test.op"() : () -> !log_asm.patch.rot_planar<size=(5, 5)>
    %p1 = log_asm_api.cast(%p0 : !log_asm.patch.rot_planar<size=(5, 5)>) -> tensor<?x!qcore.qubit>
    "test.op"(%p1) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0 = "test.op"() : () -> !log_asm.patch.rot_planar<size=(5, 5)>
// CHECK-NEXT:    %p1 = log_asm.cast(%p0 : !log_asm.patch.rot_planar<size=(5, 5)>) -> !qcore.qubit_reg<49>
// CHECK-NEXT:    %p1_1 = builtin.unrealized_conversion_cast %p1 : !qcore.qubit_reg<49> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%p1_1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %p0 = "test.op"() : () -> !log_asm.patch.rot_planar<size=(3, 3)>
    %p1 = log_asm_api.cast(%p0 : !log_asm.patch.rot_planar<size=(3, 3)>) -> tensor<?x!qcore.qubit>
    "test.op"(%p1) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0 = "test.op"() : () -> !log_asm.patch.rot_planar<size=(3, 3)>
// CHECK-NEXT:    %p1 = log_asm.cast(%p0 : !log_asm.patch.rot_planar<size=(3, 3)>) -> !qcore.qubit_reg<17>
// CHECK-NEXT:    %p1_1 = builtin.unrealized_conversion_cast %p1 : !qcore.qubit_reg<17> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%p1_1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %p0 = "test.op"() : () -> !qcore.qubit_reg<17>
    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<17> to tensor<?x!qcore.qubit>
    %p2 = log_asm_api.cast(%p1 : tensor<?x!qcore.qubit>) -> !log_asm.patch.rot_planar<size=(3, 3)>
    "test.op"(%p2) : (!log_asm.patch.rot_planar<size=(3, 3)>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0 = "test.op"() : () -> !qcore.qubit_reg<17>
// CHECK-NEXT:    %p2 = log_asm.cast(%p0 : !qcore.qubit_reg<17>) -> !log_asm.patch.rot_planar<size=(3, 3)>
// CHECK-NEXT:    "test.op"(%p2) : (!log_asm.patch.rot_planar<size=(3, 3)>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %p0 = "test.op"() : () -> !qcore.qubit_reg<17>
    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<17> to tensor<17x!qcore.qubit>
    %p2 = log_asm_api.cast(%p1 : tensor<17x!qcore.qubit>) -> tensor<?x!qcore.qubit>
    "test.op"(%p2) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0 = "test.op"() : () -> !qcore.qubit_reg<17>
// CHECK-NEXT:    %p0_1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<17> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%p0_1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %p0 = "test.op"() : () -> !qcore.qubit_reg<17>
    %p2 = log_asm_api.cast(%p0 : !qcore.qubit_reg<17>) -> !log_asm.patch.rot_planar<size=(3, 3)>
    "test.op"(%p2) : (!log_asm.patch.rot_planar<size=(3, 3)>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0 = "test.op"() : () -> !qcore.qubit_reg<17>
// CHECK-NEXT:    %p2 = log_asm.cast(%p0 : !qcore.qubit_reg<17>) -> !log_asm.patch.rot_planar<size=(3, 3)>
// CHECK-NEXT:    "test.op"(%p2) : (!log_asm.patch.rot_planar<size=(3, 3)>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %p0 = "test.op"() : () -> !qcore.qubit_reg<17>
    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<17> to tensor<?x!qcore.qubit>
    %p2 = log_asm_api.cast(%p1 : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
    "test.op"(%p2) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0 = "test.op"() : () -> !qcore.qubit_reg<17>
// CHECK-NEXT:    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<17> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%p1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %p0 = "test.op"() : () -> !qcore.qubit_reg<17>
    %p2 = log_asm_api.cast(%p0 : !qcore.qubit_reg<17>) -> tensor<?x!qcore.qubit>
    "test.op"(%p2) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0 = "test.op"() : () -> !qcore.qubit_reg<17>
// CHECK-NEXT:    %p0_1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<17> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%p0_1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %p0 = "test.op"() : () -> tensor<?xi1>
    %p1 = log_asm_api.cast(%p0 : tensor<?xi1>) -> tensor<?xi1>
    "test.op"(%p1) : (tensor<?xi1>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:      %p0 = "test.op"() : () -> tensor<?xi1>
// CHECK-NEXT:      %p1 = log_asm_api.cast(%p0 : tensor<?xi1>) -> tensor<?xi1>
// CHECK-NEXT:      "test.op"(%p1) : (tensor<?xi1>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    qstruct.circuit() -> {
    ^bb0():
    %p0 = "test.op"() : () -> !qcore.qubit_reg<6>
    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
    log_asm_api.unsized_reset<Z>(%p1 : tensor<?x!qcore.qubit>)
    qstruct.yield
    }
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    qstruct.circuit -> {
// CHECK-NEXT:      %p0 = "test.op"() : () -> !qcore.qubit_reg<6>
// CHECK-NEXT:      %0, %1, %2, %3, %4, %5 = qcore.unpack_qubit_reg(%p0 : !qcore.qubit_reg<6>)
// CHECK-NEXT:      qref.reset<Z> (%0, %1, %2, %3, %4, %5)
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    qstruct.circuit() -> {
    ^bb0():
    %p0 = "test.op"() : () -> !qcore.qubit_reg<4>
    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<4> to tensor<?x!qcore.qubit>
    log_asm_api.unsized_gate<#qcore.gate.h>(%p1 : tensor<?x!qcore.qubit>)
    qstruct.yield
    }
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    qstruct.circuit -> {
// CHECK-NEXT:      %p0 = "test.op"() : () -> !qcore.qubit_reg<4>
// CHECK-NEXT:      %0, %1, %2, %3 = qcore.unpack_qubit_reg(%p0 : !qcore.qubit_reg<4>)
// CHECK-NEXT:      qref.gate<#qcore.gate.h> (%0, %1, %2, %3)
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    qstruct.circuit() -> {
    ^bb0():
    %p0 = "test.op"() : () -> tensor<?x!qcore.qubit>
    log_asm_api.unsized_gate<#qcore.gate.h> (%p0 : tensor<?x!qcore.qubit>)
    log_asm_api.unsized_reset<X> (%p0 : tensor<?x!qcore.qubit>)
    qstruct.yield
    }
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    qstruct.circuit -> {
// CHECK-NEXT:      %p0 = "test.op"() : () -> tensor<?x!qcore.qubit>
// CHECK-NEXT:      log_asm_api.unsized_gate<#qcore.gate.h> (%p0 : tensor<?x!qcore.qubit>)
// CHECK-NEXT:      log_asm_api.unsized_reset<X> (%p0 : tensor<?x!qcore.qubit>)
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %p0 = "test.op"() : () -> !qcore.qubit_reg<17>
    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<17> to tensor<?x!qcore.qubit>
    %p2, %p3 = log_asm_api.tensor_slice(%p1[1:15:3]) tensor<?x!qcore.qubit> -> tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>
    "test.op"(%p2, %p3) : (tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0 = "test.op"() : () -> !qcore.qubit_reg<17>
// CHECK-NEXT:    %0, %1, %2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14, %15, %16 = qcore.unpack_qubit_reg(%p0 : !qcore.qubit_reg<17>)
// CHECK-NEXT:    %17 = qcore.pack_qubit_reg(%1, %4, %7, %10, %13) -> !qcore.qubit_reg<5>
// CHECK-NEXT:    %p2 = builtin.unrealized_conversion_cast %17 : !qcore.qubit_reg<5> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    %18 = qcore.pack_qubit_reg(%0, %2, %3, %5, %6, %8, %9, %11, %12, %14, %15, %16) -> !qcore.qubit_reg<12>
// CHECK-NEXT:    %p3 = builtin.unrealized_conversion_cast %18 : !qcore.qubit_reg<12> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%p2, %p3) : (tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %p0 = "test.op"() : () -> !qcore.qubit_reg<10>
    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<10> to tensor<10x!qcore.qubit>
    %p2, %p3 = log_asm_api.tensor_slice(%p1[-2:2:-1]) : tensor<10x!qcore.qubit> -> tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>
    "test.op"(%p2, %p3) : (tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0 = "test.op"() : () -> !qcore.qubit_reg<10>
// CHECK-NEXT:    %0, %1, %2, %3, %4, %5, %6, %7, %8, %9 = qcore.unpack_qubit_reg(%p0 : !qcore.qubit_reg<10>)
// CHECK-NEXT:    %10 = qcore.pack_qubit_reg(%8, %7, %6, %5, %4, %3) -> !qcore.qubit_reg<6>
// CHECK-NEXT:    %p2 = builtin.unrealized_conversion_cast %10 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    %11 = qcore.pack_qubit_reg(%0, %1, %2, %9) -> !qcore.qubit_reg<4>
// CHECK-NEXT:    %p3 = builtin.unrealized_conversion_cast %11 : !qcore.qubit_reg<4> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%p2, %p3) : (tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %p0 = "test.op"() : () -> !qcore.qubit_reg<10>
    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<10> to tensor<10x!qcore.qubit>
    %p2, %p3 = log_asm_api.tensor_slice(%p1[::]) : tensor<10x!qcore.qubit> -> tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>
    "test.op"(%p2, %p3) : (tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0 = "test.op"() : () -> !qcore.qubit_reg<10>
// CHECK-NEXT:    %0, %1, %2, %3, %4, %5, %6, %7, %8, %9 = qcore.unpack_qubit_reg(%p0 : !qcore.qubit_reg<10>)
// CHECK-NEXT:    %10 = qcore.pack_qubit_reg(%0, %1, %2, %3, %4, %5, %6, %7, %8, %9) -> !qcore.qubit_reg<10>
// CHECK-NEXT:    %p2 = builtin.unrealized_conversion_cast %10 : !qcore.qubit_reg<10> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    %p3 = tensor.empty() : tensor<0x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%p2, %p3) : (tensor<?x!qcore.qubit>, tensor<0x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %p0, %s0 = "test.op"() : () -> (!qcore.qubit_reg<5>, !qcore.qubit_reg<5>)
    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<5> to tensor<?x!qcore.qubit>
    %s1 = builtin.unrealized_conversion_cast %s0 : !qcore.qubit_reg<5> to tensor<?x!qcore.qubit>
    %p2 = log_asm_api.tensor_merge<[:10:2]>(%p1: tensor<?x!qcore.qubit>, %s1: tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
    "test.op"(%p2) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0, %s0 = "test.op"() : () -> (!qcore.qubit_reg<5>, !qcore.qubit_reg<5>)
// CHECK-NEXT:    %0, %1, %2, %3, %4 = qcore.unpack_qubit_reg(%p0 : !qcore.qubit_reg<5>)
// CHECK-NEXT:    %5, %6, %7, %8, %9 = qcore.unpack_qubit_reg(%s0 : !qcore.qubit_reg<5>)
// CHECK-NEXT:    %p2 = qcore.pack_qubit_reg(%0, %5, %1, %6, %2, %7, %3, %8, %4, %9) -> !qcore.qubit_reg<10>
// CHECK-NEXT:    %p2_1 = builtin.unrealized_conversion_cast %p2 : !qcore.qubit_reg<10> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%p2_1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %p0, %s0 = "test.op"() : () -> (!qcore.qubit_reg<15>, !qcore.qubit_reg<5>)
    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<15> to tensor<?x!qcore.qubit>
    %s1 = builtin.unrealized_conversion_cast %s0 : !qcore.qubit_reg<5> to tensor<?x!qcore.qubit>
    %p2 = log_asm_api.tensor_merge<[-1:-6:-1]>(%s1 : tensor<?x!qcore.qubit>, %p1: tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
    "test.op"(%p2) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0, %s0 = "test.op"() : () -> (!qcore.qubit_reg<15>, !qcore.qubit_reg<5>)
// CHECK-NEXT:    %0, %1, %2, %3, %4 = qcore.unpack_qubit_reg(%s0 : !qcore.qubit_reg<5>)
// CHECK-NEXT:    %5, %6, %7, %8, %9, %10, %11, %12, %13, %14, %15, %16, %17, %18, %19 = qcore.unpack_qubit_reg(%p0 : !qcore.qubit_reg<15>)
// CHECK-NEXT:    %p2 = qcore.pack_qubit_reg(%5, %6, %7, %8, %9, %10, %11, %12, %13, %14, %15, %16, %17, %18, %19, %4, %3, %2, %1, %0) -> !qcore.qubit_reg<20>
// CHECK-NEXT:    %p2_1 = builtin.unrealized_conversion_cast %p2 : !qcore.qubit_reg<20> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%p2_1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %p0, %s0 = "test.op"() : () -> (!qcore.qubit_reg<15>, tensor<0x!qcore.qubit>)
    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<15> to tensor<?x!qcore.qubit>
    %p2 = log_asm_api.tensor_merge<[100:105:1]>(%s0 : tensor<0x!qcore.qubit>, %p1: tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
    "test.op"(%p2) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0, %s0 = "test.op"() : () -> (!qcore.qubit_reg<15>, tensor<0x!qcore.qubit>)
// CHECK-NEXT:    %0, %1, %2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14 = qcore.unpack_qubit_reg(%p0 : !qcore.qubit_reg<15>)
// CHECK-NEXT:    %p2 = qcore.pack_qubit_reg(%0, %1, %2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14) -> !qcore.qubit_reg<15>
// CHECK-NEXT:    %p2_1 = builtin.unrealized_conversion_cast %p2 : !qcore.qubit_reg<15> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%p2_1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %p0, %s0 = "test.op"() : () -> (tensor<0x!qcore.qubit>, !qcore.qubit_reg<15>)
    %s1 = builtin.unrealized_conversion_cast %s0 : !qcore.qubit_reg<15> to tensor<?x!qcore.qubit>
    %p2 = log_asm_api.tensor_merge<[::]>(%s1 : tensor<?x!qcore.qubit>, %p0: tensor<0x!qcore.qubit>) -> tensor<?x!qcore.qubit>
    "test.op"(%p2) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0, %s0 = "test.op"() : () -> (tensor<0x!qcore.qubit>, !qcore.qubit_reg<15>)
// CHECK-NEXT:    %0, %1, %2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14 = qcore.unpack_qubit_reg(%s0 : !qcore.qubit_reg<15>)
// CHECK-NEXT:    %p2 = qcore.pack_qubit_reg(%0, %1, %2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14) -> !qcore.qubit_reg<15>
// CHECK-NEXT:    %p2_1 = builtin.unrealized_conversion_cast %p2 : !qcore.qubit_reg<15> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%p2_1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }
