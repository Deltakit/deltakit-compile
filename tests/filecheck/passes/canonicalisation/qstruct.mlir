// RUN: deltakit_compile compile-passes %s -t -p canonicalize -O %t && filecheck %s --input-file %t

// Test circuit op

builtin.module {
// CHECK:       builtin.module {
    %q, %q1, %q2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT: %q, %q1, %q2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit

// Circuit with no quantum effects is inlined
    %c_1 = qstruct.circuit -> i32 {
        %c = arith.constant 0 : i32
        qstruct.yield %c : i32
    }
    "test.op"(%c_1) : (i32) -> ()
// CHECK-NEXT: %c = arith.constant 0 : i32
// CHECK-NEXT: "test.op"(%c) : (i32) -> ()

// Circuit with quantum effects isn't inlined
    %c1, %q_1 = qstruct.circuit(%q : !qcore.qubit) -> i32, !qcore.qubit {
    ^bb0(%q_2: !qcore.qubit):
        qref.gate<#qcore.gate.x> (%q_2)
        %c1_1 = arith.constant 0 : i32
        qstruct.yield %c1_1, %q_2 : i32, !qcore.qubit
    }
    "test.op"(%c1) : (i32) -> ()
// CHECK-NEXT: %c1, %q_1 = qstruct.circuit(%q : !qcore.qubit) -> i32, !qcore.qubit {
// CHECK-NEXT: ^bb0(%q_2: !qcore.qubit):
// CHECK-NEXT:     qref.gate<#qcore.gate.x> (%q_2)
// CHECK-NEXT:     %c1_1 = arith.constant 0 : i32
// CHECK-NEXT:     qstruct.yield %c1_1, %q_2 : i32, !qcore.qubit
// CHECK-NEXT: }
// CHECK-NEXT: "test.op"(%c1) : (i32) -> ()

    // Circuit with unknown quantum effects isn't inlined
    qstruct.circuit -> {
        "test.op"() : () -> ()
        qstruct.yield
    }
// CHECK-NEXT: qstruct.circuit -> {
// CHECK-NEXT:     "test.op"() : () -> ()
// CHECK-NEXT:     qstruct.yield
// CHECK-NEXT: }

    // Unused circuit args are removed
    %q1_1 = qstruct.circuit(%q1, %c1 : !qcore.qubit, i32) -> !qcore.qubit {
    ^bb0(%q1_2: !qcore.qubit, %c1_2: i32):
        qref.gate<#qcore.gate.x> (%q1_2)
        qstruct.yield %q1_2 : !qcore.qubit
    }
// CHECK-NEXT: %q1_1 = qstruct.circuit(%q1 : !qcore.qubit) -> !qcore.qubit {
// CHECK-NEXT: ^bb0(%q1_2: !qcore.qubit):
// CHECK-NEXT:      qref.gate<#qcore.gate.x> (%q1_2)
// CHECK-NEXT:     qstruct.yield %q1_2 : !qcore.qubit
// CHECK-NEXT: }

    // Unused circuit returns are removed only if they aren't qubits
    %c2, %q2_1 = qstruct.circuit(%q2 : !qcore.qubit) -> i32, !qcore.qubit {
    ^bb0(%q2_2: !qcore.qubit):
        qref.gate<#qcore.gate.x> (%q2_2)
        %c2_1 = arith.constant 0 : i32
        qstruct.yield %c2_1, %q2_2 : i32, !qcore.qubit
    }
// CHECK-NEXT: %q2_1 = qstruct.circuit(%q2 : !qcore.qubit) -> !qcore.qubit {
// CHECK-NEXT: ^bb0(%q2_2: !qcore.qubit):
// CHECK-NEXT:     qref.gate<#qcore.gate.x> (%q2_2)
// CHECK-NEXT:     qstruct.yield %q2_2 : !qcore.qubit
// CHECK-NEXT: }

}
// CHECK-NEXT: }

// ----
// Test repeat op

builtin.module {
// CHECK:       builtin.module {

    // Constants in repeats are hoisted out
    qstruct.repeat<2> -> {
        %c0 = arith.constant 0 : i32
        "test.op"(%c0) : (i32) -> ()
        qstruct.yield
    }
// CHECK-NEXT:    %c0 = arith.constant 0 : i32
// CHECK-NEXT:    qstruct.repeat<2> () -> {
// CHECK-NEXT:      "test.op"(%c0) : (i32) -> ()
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    }

    // Repeats with only one iteration are inlined
    %c1 = "test.op"() : () -> i32
    %c1_1 = qstruct.repeat<1>(%c1 : i32) -> i32 {
    ^bb0(%c1_2: i32):
        %c1_3 = "test.op"(%c1_2) : (i32) -> i32
        qstruct.yield %c1_3 : i32
    }
    "test.op"(%c1_1) : (i32) -> ()
// CHECK-NEXT:    %c1 = "test.op"() : () -> i32
// CHECK-NEXT:    %c1_1 = "test.op"(%c1) : (i32) -> i32
// CHECK-NEXT:    "test.op"(%c1_1) : (i32) -> ()

    // Empty repeat that only yields values defined outside its body is eliminated
    %c2 = "test.op"() : () -> i32
    %c2_1 = qstruct.repeat<10>(%c2 : i32) -> i32 {
    ^bb0(%c2_2: i32):
        qstruct.yield %c2 : i32
    }
    "test.op"(%c2_1) : (i32) -> ()
// CHECK-NEXT:    %c2 = "test.op"() : () -> i32
// CHECK-NEXT:    "test.op"(%c2) : (i32) -> ()

    // Empty repeat only yielding values from block args in the same order is eliminated
    %c3 = "test.op"() : () -> i32
    %c3_1 = qstruct.repeat<10>(%c3 : i32) -> i32 {
    ^bb0(%c3_2: i32):
        qstruct.yield %c3_2 : i32
    }
    "test.op"(%c3_1) : (i32) -> ()
// CHECK-NEXT:    %c3 = "test.op"() : () -> i32
// CHECK-NEXT:    "test.op"(%c3) : (i32) -> ()

    // Empty repeat yielding values from block args in different order is not eliminated
    %c4, %c5 = "test.op"() : () -> (i32, i32)
    %c5_1, %c4_1 = qstruct.repeat<3>(%c4, %c5 : i32, i32) -> i32, i32 {
    ^bb0(%inner0: i32, %inner1: i32):
        qstruct.yield %inner1, %inner0 : i32, i32 // Swap arg order
    }
    "test.op"(%c5_1, %c4_1) : (i32, i32) -> ()
// CHECK-NEXT:    %c4, %c5 = "test.op"() : () -> (i32, i32)
// CHECK-NEXT:    %c5_1, %c4_1 = qstruct.repeat<3> (%c4, %c5 : i32, i32) -> i32, i32 {
// CHECK-NEXT:    ^bb0(%inner0: i32, %inner1: i32):
// CHECK-NEXT:      qstruct.yield %inner1, %inner0 : i32, i32
// CHECK-NEXT:    }
// CHECK-NEXT:    "test.op"(%c5_1, %c4_1) : (i32, i32) -> ()

}
// CHECK-NEXT: }

// ----
// Test parallel op

builtin.module {
    // CHECK:       builtin.module {

    // Unused parallel returns are removed, leaving only one region which is then inlined
    %c3, %c4, %c5 = qstruct.parallel<TOP> -> i32, i32, i32 {
        %c3_1 = arith.constant 0 : i32
        qstruct.yield %c3_1 : i32
    } {
        %c4_1 = "test.op"() : () -> i32
        %c5_1 = arith.constant 0 : i32
        qstruct.yield %c4_1, %c5_1 : i32, i32
    }
    "test.op"(%c4) : (i32) -> ()
// CHECK-NEXT: %c4 = "test.op"() : () -> i32
// CHECK-NEXT: "test.op"(%c4) : (i32) -> ()

    // Unnecessary nested parallels are flattened
    %c6, %c7, %c8, %c9 = qstruct.parallel<BOTTOM> -> i32, i32, i32, i32 {
        %c6_1, %c7_1 = qstruct.parallel<BOTTOM> -> i32, i32 {
            %c6_2 = "test.op"() : () -> i32
            qstruct.yield %c6_2 : i32
        } {
            %c7_2 = "test.op"() : () -> i32
            qstruct.yield %c7_2 : i32
        }
        qstruct.yield %c6_1, %c7_1 : i32, i32
    } {
        // Not flattened because alignment is different
        %c8_1, %c9_1 = qstruct.parallel<TOP> -> i32, i32 {
            %c8_2 = "test.op"() : () -> i32
            qstruct.yield %c8_2 : i32
        } {
            %c9_2 = "test.op"() : () -> i32
            qstruct.yield %c9_2 : i32
        }
        qstruct.yield %c8_1, %c9_1 : i32, i32
    }
    qstruct.output(%c6, %c7, %c8, %c9 : i32, i32, i32, i32)
// CHECK-NEXT:    %c6, %c7, %c8, %c9 = qstruct.parallel<BOTTOM> -> i32, i32, i32, i32 {
// CHECK-NEXT:      %c6_1 = "test.op"() : () -> i32
// CHECK-NEXT:      qstruct.yield %c6_1 : i32
// CHECK-NEXT:    } {
// CHECK-NEXT:      %c7_1 = "test.op"() : () -> i32
// CHECK-NEXT:      qstruct.yield %c7_1 : i32
// CHECK-NEXT:    } {
// CHECK-NEXT:      %c8_1, %c9_1 = qstruct.parallel<TOP> -> i32, i32 {
// CHECK-NEXT:        %c8_2 = "test.op"() : () -> i32
// CHECK-NEXT:        qstruct.yield %c8_2 : i32
// CHECK-NEXT:      } {
// CHECK-NEXT:        %c9_2 = "test.op"() : () -> i32
// CHECK-NEXT:        qstruct.yield %c9_2 : i32
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield %c8_1, %c9_1 : i32, i32
// CHECK-NEXT:    }
// CHECK-NEXT:    qstruct.output(%c6, %c7, %c8, %c9 : i32, i32, i32, i32)

    // Entirely unnecessary parallels are eliminated
    %c10 = qstruct.parallel<TOP> -> i32 {
        %c10_1 = arith.constant 0 : i32
        qstruct.yield %c10_1 : i32
    }
// CHECK-NOT: qstruct.parallel

    // Region that only yields SSAs from the outer scope are eliminated
    %c11 = arith.constant 0 : i32
    %c11_1, %c12, %c13 = qstruct.parallel<TOP> -> i32, i32, i32 {
        qstruct.yield %c11 : i32
    } {
        %c12_1 = "test.op"() : () -> (i32)
        qstruct.yield %c12_1 : i32
    } {
        %c13_1 = "test.op"() : () -> (i32)
        qstruct.yield %c13_1 : i32
    }
    "test.op"(%c11_1, %c12, %c13) : (i32, i32, i32) -> ()
// CHECK-NEXT:    %c11 = arith.constant 0 : i32
// CHECK-NEXT:    %c12, %c13 = qstruct.parallel<TOP> -> i32, i32 {
// CHECK-NEXT:      %c12_1 = "test.op"() : () -> i32
// CHECK-NEXT:      qstruct.yield %c12_1 : i32
// CHECK-NEXT:    } {
// CHECK-NEXT:      %c13_1 = "test.op"() : () -> i32
// CHECK-NEXT:      qstruct.yield %c13_1 : i32
// CHECK-NEXT:    }
// CHECK-NEXT:    "test.op"(%c11, %c12, %c13) : (i32, i32, i32) -> ()

    // Pure parallels are inlined
    %c14, %c15 = qstruct.parallel<BOTTOM> -> i32, i32 {
        %c14_1 = arith.constant 0 : i32
        qstruct.yield %c14_1 : i32
    } {
        %c15_1 = arith.constant 0 : i32
        qstruct.yield %c15_1 : i32
    }
    "test.op"(%c14, %c15) : (i32, i32) -> ()
// CHECK-NEXT:    %c14 = arith.constant 0 : i32
// CHECK-NEXT:    %c15 = arith.constant 0 : i32
// CHECK-NEXT:    "test.op"(%c14, %c15) : (i32, i32) -> ()


    // Parallel yields from otherwise empty regions are respected during canonicalisation
    %c16 = arith.constant 0 : i32
    %c17 = arith.constant 0 : i32
    %c16_a, %c17_a, %c17_b, %c16_b = qstruct.parallel<BOTTOM> -> i32, i32, i32, i32 {
        "test.op"(%c16) : (i32) -> ()
        qstruct.yield %c16, %c17 : i32, i32
    } {
        qstruct.yield %c17, %c16 : i32, i32
    }
    "test.op"(%c16_a, %c17_a, %c17_b, %c16_b) : (i32, i32, i32, i32) -> ()
// CHECK-NEXT:    %c16 = arith.constant 0 : i32
// CHECK-NEXT:    %c17 = arith.constant 0 : i32
// CHECK-NEXT:    "test.op"(%c16) : (i32) -> ()
// CHECK-NEXT:    "test.op"(%c16, %c17, %c17, %c16) : (i32, i32, i32, i32) -> ()

    // Parallel yields from outside the parallel can be removed.
    %c18 = arith.constant 0 : i32
    %c19 = arith.constant 0 : i32
    %c18_a, %c19_a = qstruct.parallel<BOTTOM> -> i32, i32 {
        "test.op"(%c18) : (i32) -> ()
        qstruct.yield %c18 : i32
    } {
        "test.op"(%c19) : (i32) -> ()
        qstruct.yield %c19 : i32
    }
    "test.op"(%c18_a, %c19_a) : (i32, i32) -> ()
// CHECK-NEXT:    %c18 = arith.constant 0 : i32
// CHECK-NEXT:    %c19 = arith.constant 0 : i32
// CHECK-NEXT:    qstruct.parallel<BOTTOM> -> {
// CHECK-NEXT:        "test.op"(%c18) : (i32) -> ()
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:    } {
// CHECK-NEXT:        "test.op"(%c19) : (i32) -> ()
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:    }
// CHECK-NEXT:    "test.op"(%c18, %c19) : (i32, i32) -> ()


// Pure ops are hoisted out of parallels, but not if they require values from inside the parallel.
    %c20_a, %c23_a = qstruct.parallel<BOTTOM> -> i32, i32 {
        %c20 = arith.constant 20 : i32
        "test.op"(%c20) : (i32) -> ()
        qstruct.yield %c20 : i32
    } {
        %c21 = "test.op"() : () -> (i32)
        %c22 = arith.constant 22 : i32
        %c23 = arith.addi %c21, %c22 : i32
        "test.op"(%c23) : (i32) -> ()
        qstruct.yield %c22 : i32
    }
    "test.op"(%c20_a, %c23_a) : (i32, i32) -> ()
// CHECK-NEXT:    %c20 = arith.constant 20 : i32
// CHECK-NEXT:    %c22 = arith.constant 22 : i32
// CHECK-NEXT:    qstruct.parallel<BOTTOM> -> {
// CHECK-NEXT:      "test.op"(%c20) : (i32) -> ()
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    } {
// CHECK-NEXT:      %c21 = "test.op"() : () -> i32
// CHECK-NEXT:      %c23 = arith.addi %c21, %c22 : i32
// CHECK-NEXT:      "test.op"(%c23) : (i32) -> ()
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    }
// CHECK-NEXT:    "test.op"(%c20, %c22) : (i32, i32) -> ()

}
// CHECK-NEXT:  }



// ----
// Test stab.concrete_flow_array measurement indices count as a use of the qubits and the indices
// are updated when unused results are removed.

builtin.module {
// CHECK:       builtin.module {
    %q1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT: %q1 = qcore.alloc_qubit -> !qcore.qubit

    // Reference to measurement in flow inhibits removing the result
    %q2, %n1 = qstruct.circuit(%q1 : !qcore.qubit) {
        stab.flows = #stab.concrete_flow_array<[<+:1>{I -> X0 : 1}]>
    } -> !qcore.qubit, i1 {
    ^bb0(%q1_1: !qcore.qubit):
        %m1 = qref.measure<X> (%q1_1) -> i1
        qstruct.yield %q1_1, %m1 : !qcore.qubit, i1
    }
// CHECK-NEXT:      %q2, %n1 = qstruct.circuit(%q1 : !qcore.qubit) {
// CHECK-SAME:        stab.flows = #stab.concrete_flow_array<[<+:1>{I -> X0 : 1}]>
// CHECK-SAME:      } -> !qcore.qubit, i1 {
// CHECK-NEXT:      ^bb0(%q1_1: !qcore.qubit):
// CHECK-NEXT:        %m1 = qref.measure<X> (%q1_1) -> i1
// CHECK-NEXT:        qstruct.yield %q1_1, %m1 : !qcore.qubit, i1
// CHECK-NEXT:      }

    // Measurement indices are updated when unused results are removed
    %n2, %c1, %n3, %q3, %c2, %n4 = qstruct.circuit(%q2 : !qcore.qubit) {
        stab.flows = #stab.concrete_flow_array<[<+:0,2>{I -> X0 : 1}, <+:5>{X0 -> I : 1}]>
    } -> i1, i32, i1, !qcore.qubit, i32, i1 {
    ^bb0(%q1_1: !qcore.qubit):
        %m1 = qref.measure<X> (%q1_1) -> i1
        %m2 = qref.measure<X> (%q1_1) -> i1
        %c1_1 = arith.constant 0 : i32
        qstruct.yield %m1, %c1_1, %m1, %q1_1, %c1_1, %m2 : i1, i32, i1, !qcore.qubit, i32, i1
    }
// CHECK-NEXT:      %n2, %n3, %q3, %n4 = qstruct.circuit(%q2 : !qcore.qubit) {
// CHECK-SAME:        stab.flows = #stab.concrete_flow_array<[<+:0, 1>{I -> X0 : 1}, <+:3>{X0 -> I : 1}]>
// CHECK-SAME:      } -> i1, i1, !qcore.qubit, i1 {
// CHECK-NEXT:      ^bb0(%q1_1: !qcore.qubit):
// CHECK-NEXT:        %m1 = qref.measure<X> (%q1_1) -> i1
// CHECK-NEXT:        %m2 = qref.measure<X> (%q1_1) -> i1
// CHECK-NEXT:        qstruct.yield %m1, %m1, %q1_1, %m2 : i1, i1, !qcore.qubit, i1
// CHECK-NEXT:      }
}
// CHECK-NEXT:  }
