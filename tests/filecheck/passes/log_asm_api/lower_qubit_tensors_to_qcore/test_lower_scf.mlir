// RUN: deltakit_compile compile-passes -t %s -p lower-qubit-tensors-to-qcore --pass-args '{"permit_unresolved_casts": true, "permit_remaining_qubit_tensors": true}' -O %t && filecheck %s --input-file %t


builtin.module {
    %p0 = "test.op"() : () -> !qcore.qubit_reg<6>
    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
    %index = "test.op"() : () -> index
    %p2 = scf.for %i = %index to %index step %index
        iter_args(%pi = %p1) -> (tensor<?x!qcore.qubit>) {
        "test.op"(%pi) : (tensor<?x!qcore.qubit>) -> ()
        scf.yield %p1 : tensor<?x!qcore.qubit>
    }
    "test.op"(%p2) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0 = "test.op"() : () -> !qcore.qubit_reg<6>
// CHECK-NEXT:    %index = "test.op"() : () -> index
// CHECK-NEXT:    %p2 = scf.for %i = %index to %index step %index iter_args(%pi = %p0) -> (!qcore.qubit_reg<6>) {
// CHECK-NEXT:      %pi_1 = builtin.unrealized_conversion_cast %pi : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
// CHECK-NEXT:      "test.op"(%pi_1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:      scf.yield %p0 : !qcore.qubit_reg<6>
// CHECK-NEXT:    }
// CHECK-NEXT:    %p2_1 = builtin.unrealized_conversion_cast %p2 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%p2_1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %p0, %q0 = "test.op"() : () -> (!qcore.qubit_reg<6>, !qcore.qubit_reg<6>)
    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
    %q1 = builtin.unrealized_conversion_cast %q0 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
    %index = "test.op"() : () -> index
    %p2, %q2 = scf.for %i = %index to %index step %index
        iter_args(%pi = %p1, %qi = %q1) -> (tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>) {
        scf.yield %qi, %pi : tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>
    }
    "test.op"(%p2) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0, %q0 = "test.op"() : () -> (!qcore.qubit_reg<6>, !qcore.qubit_reg<6>)
// CHECK-NEXT:    %index = "test.op"() : () -> index
// CHECK-NEXT:    %p2, %q2 = scf.for %i = %index to %index step %index iter_args(%pi = %p0, %qi = %q0) -> (!qcore.qubit_reg<6>, !qcore.qubit_reg<6>) {
// CHECK-NEXT:      scf.yield %qi, %pi : !qcore.qubit_reg<6>, !qcore.qubit_reg<6>
// CHECK-NEXT:    }
// CHECK-NEXT:    %p2_1 = builtin.unrealized_conversion_cast %p2 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%p2_1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %p0, %q0 = "test.op"() : () -> (!qcore.qubit_reg<6>, !qcore.qubit_reg<6>)
    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
    %q1 = builtin.unrealized_conversion_cast %q0 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
    %condition = "test.op"() : () -> i1
    %picked = scf.if %condition -> (tensor<?x!qcore.qubit>) {
        scf.yield %p1 : tensor<?x!qcore.qubit>
    } else {
        scf.yield %q1 : tensor<?x!qcore.qubit>
    }
    "test.op"(%picked) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0, %q0 = "test.op"() : () -> (!qcore.qubit_reg<6>, !qcore.qubit_reg<6>)
// CHECK-NEXT:    %condition = "test.op"() : () -> i1
// CHECK-NEXT:    %picked = scf.if %condition -> (!qcore.qubit_reg<6>) {
// CHECK-NEXT:      scf.yield %p0 : !qcore.qubit_reg<6>
// CHECK-NEXT:    } else {
// CHECK-NEXT:      scf.yield %q0 : !qcore.qubit_reg<6>
// CHECK-NEXT:    }
// CHECK-NEXT:    %picked_1 = builtin.unrealized_conversion_cast %picked : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%picked_1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
    %p0, %q0 = "test.op"() : () -> (!qcore.qubit_reg<6>, !qcore.qubit_reg<6>)
    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
    %q1 = builtin.unrealized_conversion_cast %q0 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
    %switch = "test.op"() : () -> index
    %picked = scf.index_switch %switch -> tensor<?x!qcore.qubit>
    case 1 {
        "test.op"(%p1) : (tensor<?x!qcore.qubit>) -> ()
        scf.yield %p1 : tensor<?x!qcore.qubit>
    }
    case 2 {
        scf.yield %q1 : tensor<?x!qcore.qubit>
    }
    case 3 {
        scf.yield %p1 : tensor<?x!qcore.qubit>
    }
    default {
        %pi = "test.op"() : () -> !qcore.qubit_reg<6>
        %pii = builtin.unrealized_conversion_cast %pi : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
        scf.yield %pii : tensor<?x!qcore.qubit>
    }
    "test.op"(%picked) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0, %q0 = "test.op"() : () -> (!qcore.qubit_reg<6>, !qcore.qubit_reg<6>)
// CHECK-NEXT:    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    %switch = "test.op"() : () -> index
// CHECK-NEXT:    %picked = scf.index_switch %switch -> !qcore.qubit_reg<6>
// CHECK-NEXT:    case 1 {
// CHECK-NEXT:      "test.op"(%p1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:      scf.yield %p0 : !qcore.qubit_reg<6>
// CHECK-NEXT:    }
// CHECK-NEXT:    case 2 {
// CHECK-NEXT:      scf.yield %q0 : !qcore.qubit_reg<6>
// CHECK-NEXT:    }
// CHECK-NEXT:    case 3 {
// CHECK-NEXT:      scf.yield %p0 : !qcore.qubit_reg<6>
// CHECK-NEXT:    }
// CHECK-NEXT:    default {
// CHECK-NEXT:      %pi = "test.op"() : () -> !qcore.qubit_reg<6>
// CHECK-NEXT:      scf.yield %pi : !qcore.qubit_reg<6>
// CHECK-NEXT:    }
// CHECK-NEXT:    %picked_1 = builtin.unrealized_conversion_cast %picked : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%picked_1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }


// ----
// CHECK-NEXT: ----

builtin.module {
    %p0, %q0 = "test.op"() : () -> (!qcore.qubit_reg<6>, !qcore.qubit_reg<4>)
    %p1 = builtin.unrealized_conversion_cast %p0 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
    %q1 = builtin.unrealized_conversion_cast %q0 : !qcore.qubit_reg<4> to tensor<?x!qcore.qubit>
    %condition = "test.op"() : () -> i1
    %p2, %q2 = scf.while (%pi = %p1, %qi = %q1) : (tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>) -> (tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>) {
        %qi0 = "test.op"() : () -> !qcore.qubit_reg<4>
        %qi1 = builtin.unrealized_conversion_cast %qi0 : !qcore.qubit_reg<4> to tensor<?x!qcore.qubit>
        scf.condition(%condition) %pi, %qi1 : tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>
    } do {
        ^bb0(%pii: tensor<?x!qcore.qubit>, %qii: tensor<?x!qcore.qubit>):
        %pi0 = "test.op"() : () -> !qcore.qubit_reg<6>
        %pi1 = builtin.unrealized_conversion_cast %pi0 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
        scf.yield %pi1, %qii : tensor<?x!qcore.qubit>, tensor<?x!qcore.qubit>
    }
    "test.op"(%p2) : (tensor<?x!qcore.qubit>) -> ()
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %p0, %q0 = "test.op"() : () -> (!qcore.qubit_reg<6>, !qcore.qubit_reg<4>)
// CHECK-NEXT:    %condition = "test.op"() : () -> i1
// CHECK-NEXT:    %p2, %q2 = scf.while (%pi = %p0, %qi = %q0) : (!qcore.qubit_reg<6>, !qcore.qubit_reg<4>) -> (!qcore.qubit_reg<6>, !qcore.qubit_reg<4>) {
// CHECK-NEXT:      %qi0 = "test.op"() : () -> !qcore.qubit_reg<4>
// CHECK-NEXT:      scf.condition(%condition) %pi, %qi0 : !qcore.qubit_reg<6>, !qcore.qubit_reg<4>
// CHECK-NEXT:    } do {
// CHECK-NEXT:    ^bb0(%pii: !qcore.qubit_reg<6>, %qii: !qcore.qubit_reg<4>):
// CHECK-NEXT:      %pi0 = "test.op"() : () -> !qcore.qubit_reg<6>
// CHECK-NEXT:      scf.yield %pi0, %qii : !qcore.qubit_reg<6>, !qcore.qubit_reg<4>
// CHECK-NEXT:    }
// CHECK-NEXT:    %p2_1 = builtin.unrealized_conversion_cast %p2 : !qcore.qubit_reg<6> to tensor<?x!qcore.qubit>
// CHECK-NEXT:    "test.op"(%p2_1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:  }
