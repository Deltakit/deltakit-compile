// RUN: deltakit_compile compile-passes %s -p split-gate-like-broadcast-ops -O %t && filecheck %s --input-file %t

builtin.module {
    %qo = qcore.alloc_qubit -> !qcore.qubit
    %qo_1 = qcore.alloc_qubit -> !qcore.qubit
    %qo_2 = qcore.alloc_qubit -> !qcore.qubit
    %qo_3 = qcore.alloc_qubit -> !qcore.qubit

    %qo_a, %qo_a1, %qo_a2, %qo_a3 = qstruct.circuit(
        %qo, %qo_1, %qo_2, %qo_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit)
        -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
    ^bb0(%q: !qcore.qubit, %q_1: !qcore.qubit, %q_2: !qcore.qubit, %q_3: !qcore.qubit):
        // Single-qubit broadcast across three targets should split into regions
        qref.gate<#qcore.gate.x> (%q, %q_1, %q_2)

        // Measurement broadcast across two targets should split and return i1 per region
        %m0, %m1 = qref.measure<Z> (%q, %q_1) -> i1, i1
        qec.detector<[0.0, 0.0]> (%m0, %m1)

        // Measurement broadcast with several Paulis should split
        %m2, %m3, %m4 = qref.measure<[XX, Y, Z]>(%q, %q_1, %q_2, %q_3) -> i1, i1, i1

        // Two-qubit broadcast across four targets (two pairs) should split into two regions
        qref.gate<#qcore.gate.cx> (%q, %q_1, %q_2, %q_3)

        // Reset broadcast across two targets should split into two regions (no results)
        qref.reset<Z> (%q, %q_1)

        // Unchanged cases should pass through:
        // - Single-qubit clifford with single target
        qref.gate<#qcore.gate.x> (%q_3)
        // - Measurement with single target (single or multi-Pauli)
        %m5 = qref.measure<Z> (%q_2) -> i1
        %m6 = qref.measure<ZZ> (%q_2, %q_3) -> i1
        // - Two-qubit clifford with exactly two targets
        qref.gate<#qcore.gate.cx> (%q_1, %q_2)
        // - Reset with single target
        qref.reset<Z> (%q_3)

        qstruct.yield %q, %q_1, %q_2, %q_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
    }
}

// CHECK:       builtin.module {
// CHECK-NEXT:      %qo = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:      %qo_1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:      %qo_2 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:      %qo_3 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:      %qo_a, %qo_a1, %qo_a2, %qo_a3 = qstruct.circuit(
// CHECK-SAME:          %qo, %qo_1, %qo_2, %qo_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit)
// CHECK-SAME:          -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:      ^bb0(%q: !qcore.qubit, %q_1: !qcore.qubit, %q_2: !qcore.qubit, %q_3: !qcore.qubit):
// CHECK-NEXT:          qstruct.parallel<TOP> -> {
// CHECK-NEXT:            qref.gate<#qcore.gate.x> (%q)
// CHECK-NEXT:            qstruct.yield
// CHECK-NEXT:          } {
// CHECK-NEXT:            qref.gate<#qcore.gate.x> (%q_1)
// CHECK-NEXT:            qstruct.yield
// CHECK-NEXT:          } {
// CHECK-NEXT:            qref.gate<#qcore.gate.x> (%q_2)
// CHECK-NEXT:            qstruct.yield
// CHECK-NEXT:          }
// CHECK-NEXT:          [[M0:%[a-zA-Z0-9_]+]], [[M1:%[a-zA-Z0-9_]+]] = qstruct.parallel<TOP> -> i1, i1 {
// CHECK-NEXT:            [[A:%[0-9]+]] = qref.measure<Z> (%q) -> i1
// CHECK-NEXT:            qstruct.yield [[A]] : i1
// CHECK-NEXT:          } {
// CHECK-NEXT:            [[B:%[0-9]+]] = qref.measure<Z> (%q_1) -> i1
// CHECK-NEXT:            qstruct.yield [[B]] : i1
// CHECK-NEXT:          }
// CHECK-NEXT:          qec.detector<[0.0, 0.0]> ([[M0]], [[M1]])
// CHECK-NEXT:          [[M2:%[a-zA-Z0-9_]+]], [[M3:%[a-zA-Z0-9_]+]], [[M4:%[a-zA-Z0-9_]+]]
// CHECK-SAME:              = qstruct.parallel<TOP> -> i1, i1, i1 {
// CHECK-NEXT:            [[C:%[0-9]+]] = qref.measure<XX> (%q, %q_1) -> i1
// CHECK-NEXT:            qstruct.yield [[C]] : i1
// CHECK-NEXT:          } {
// CHECK-NEXT:            [[D:%[0-9]+]] = qref.measure<Y> (%q_2) -> i1
// CHECK-NEXT:            qstruct.yield [[D]] : i1
// CHECK-NEXT:          } {
// CHECK-NEXT:            [[E:%[0-9]+]] = qref.measure<Z> (%q_3) -> i1
// CHECK-NEXT:            qstruct.yield [[E]] : i1
// CHECK-NEXT:          }
// CHECK-NEXT:          qstruct.parallel<TOP> -> {
// CHECK-NEXT:            qref.gate<#qcore.gate.cx> (%q, %q_1)
// CHECK-NEXT:            qstruct.yield
// CHECK-NEXT:          } {
// CHECK-NEXT:            qref.gate<#qcore.gate.cx> (%q_2, %q_3)
// CHECK-NEXT:            qstruct.yield
// CHECK-NEXT:          }
// CHECK-NEXT:          qstruct.parallel<TOP> -> {
// CHECK-NEXT:            qref.reset<Z> (%q)
// CHECK-NEXT:            qstruct.yield
// CHECK-NEXT:          } {
// CHECK-NEXT:            qref.reset<Z> (%q_1)
// CHECK-NEXT:            qstruct.yield
// CHECK-NEXT:          }
// CHECK-NEXT:          qref.gate<#qcore.gate.x> (%q_3)
// CHECK-NEXT:          [[SINGLE_MEAS:%[a-zA-Z0-9_]+]] = qref.measure<Z> (%q_2) -> i1
// CHECK-NEXT:          [[SINGLE_MEAS2:%[a-zA-Z0-9_]+]] = qref.measure<ZZ> (%q_2, %q_3) -> i1
// CHECK-NEXT:          qref.gate<#qcore.gate.cx> (%q_1, %q_2)
// CHECK-NEXT:          qref.reset<Z> (%q_3)
// CHECK-NEXT:          qstruct.yield %q, %q_1, %q_2, %q_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      }
// CHECK-NEXT:  }
