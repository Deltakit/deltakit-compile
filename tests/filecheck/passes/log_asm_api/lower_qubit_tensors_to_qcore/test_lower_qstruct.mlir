// RUN: deltakit_compile compile-passes -t %s -p lower-qubit-tensors-to-qcore --pass-args '{"permit_unresolved_casts": true, "permit_remaining_qubit_tensors": true}' -O %t && filecheck %s --input-file %t

builtin.module {
    %p0 = "test.op"() : () -> !qcore.qubit_reg<6>
    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
    %p2 = qstruct.circuit(%p1: tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>{
        ^bb0(%pi: tensor<?x!qcore.qubit>):
            "test.op"(%pi) : (tensor<?x!qcore.qubit>) -> ()
            qstruct.yield %pi : tensor<?x!qcore.qubit>
    }
    "test.op"(%p2) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0 = "test.op"() : () -> !qcore.qubit_reg<6>
// CHECK-NEXT:    %p2 = qstruct.circuit(%p0 : !qcore.qubit_reg<6>) -> !qcore.qubit_reg<6> {
// CHECK-NEXT:    ^bb0(%pi: !qcore.qubit_reg<6>):
// CHECK-NEXT:      %pi_1 = builtin.unrealized_conversion_cast %pi : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
// CHECK-NEXT:      "test.op"(%pi_1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:      qstruct.yield %pi : !qcore.qubit_reg<6>
// CHECK-NEXT:    }
// CHECK-NEXT:    %p2_1 = builtin.unrealized_conversion_cast %p2 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%p2_1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %p0, %q0 = "test.op"() : () -> (!qcore.qubit_reg<6>, !qcore.qubit_reg<4>)
    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
    %q1 = builtin.unrealized_conversion_cast %q0 : !qcore.qubit_reg<4> to tensor<?x!qcore.qubit>
    %p2, %q2 = qstruct.circuit(%p1, %q1: tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit> {
        ^bb0(%pi: tensor<?x!qcore.qubit>, %qi: tensor<?x!qcore.qubit>):
            "test.op"(%pi) : (tensor<?x!qcore.qubit>) -> ()
            qstruct.yield %pi, %qi: tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>
    }
    "test.op"(%p2) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0, %q0 = "test.op"() : () -> (!qcore.qubit_reg<6>, !qcore.qubit_reg<4>)
// CHECK-NEXT:    %p2, %q2 = qstruct.circuit(%p0, %q0 : !qcore.qubit_reg<6>, !qcore.qubit_reg<4>) -> !qcore.qubit_reg<6>, !qcore.qubit_reg<4> {
// CHECK-NEXT:    ^bb0(%pi: !qcore.qubit_reg<6>, %qi: !qcore.qubit_reg<4>):
// CHECK-NEXT:      %pi_1 = builtin.unrealized_conversion_cast %pi : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
// CHECK-NEXT:      "test.op"(%pi_1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:      qstruct.yield %pi, %qi : !qcore.qubit_reg<6>, !qcore.qubit_reg<4>
// CHECK-NEXT:    }
// CHECK-NEXT:    %p2_1 = builtin.unrealized_conversion_cast %p2 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%p2_1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %p0, %q0 = "test.op"() : () -> (!qcore.qubit_reg<6>, !qcore.qubit_reg<4>)
    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
    %q1 = builtin.unrealized_conversion_cast %q0 : !qcore.qubit_reg<4> to tensor<?x!qcore.qubit>
    %p2, %q2 = qstruct.repeat<10000000>(%p1, %q1: tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit> {
        ^bb0(%pi: tensor<?x!qcore.qubit>, %qi: tensor<?x!qcore.qubit>):
            "test.op"(%pi) : (tensor<?x!qcore.qubit>) -> ()
            qstruct.yield %pi, %qi: tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>
    }
    "test.op"(%p2) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0, %q0 = "test.op"() : () -> (!qcore.qubit_reg<6>, !qcore.qubit_reg<4>)
// CHECK-NEXT:    %p2, %q2 = qstruct.repeat<10000000> (%p0, %q0 : !qcore.qubit_reg<6>, !qcore.qubit_reg<4>) -> !qcore.qubit_reg<6>, !qcore.qubit_reg<4> {
// CHECK-NEXT:    ^bb0(%pi: !qcore.qubit_reg<6>, %qi: !qcore.qubit_reg<4>):
// CHECK-NEXT:      %pi_1 = builtin.unrealized_conversion_cast %pi : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
// CHECK-NEXT:      "test.op"(%pi_1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:      %pi_2 = builtin.unrealized_conversion_cast %pi_1 : tensor<?x!qcore.qubit> to !qcore.qubit_reg<6>
// CHECK-NEXT:      qstruct.yield %pi_2, %qi : !qcore.qubit_reg<6>, !qcore.qubit_reg<4>
// CHECK-NEXT:    }
// CHECK-NEXT:    %p2_1 = builtin.unrealized_conversion_cast %p2 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%p2_1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %p0, %q0 = "test.op"() : () -> (!qcore.qubit_reg<6>, !qcore.qubit_reg<4>)
    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
    %q1 = builtin.unrealized_conversion_cast %q0 : !qcore.qubit_reg<4> to tensor<?x!qcore.qubit>
    %p2, %q2 = qstruct.parallel<TOP> -> tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit> {
            "test.op"(%p1) : (tensor<?x!qcore.qubit>) -> ()
            qstruct.yield %p1: tensor<?x!qcore.qubit>
    }
    {
            "test.op"(%q1) : (tensor<?x!qcore.qubit>) -> ()
            qstruct.yield %q1: tensor<?x!qcore.qubit>
    }
    "test.op"(%p2) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0, %q0 = "test.op"() : () -> (!qcore.qubit_reg<6>, !qcore.qubit_reg<4>)
// CHECK-NEXT:    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    %q1 = builtin.unrealized_conversion_cast %q0 : !qcore.qubit_reg<4> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    %0, %1 = qstruct.parallel<TOP> -> !qcore.qubit_reg<6>, !qcore.qubit_reg<4> {
// CHECK-NEXT:      "test.op"(%p1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:      qstruct.yield %p0 : !qcore.qubit_reg<6>
// CHECK-NEXT:    } {
// CHECK-NEXT:      "test.op"(%q1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:      qstruct.yield %q0 : !qcore.qubit_reg<4>
// CHECK-NEXT:    }
// CHECK-NEXT:    %p2 = builtin.unrealized_conversion_cast %0 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%p2) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }
