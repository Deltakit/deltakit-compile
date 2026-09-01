// RUN: deltakit_compile compile-passes %s -t -p canonicalize -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK:       builtin.module {
    %iq1 = qcore.alloc_qubit -> !qcore.qubit
    %iq2 = qcore.alloc_qubit -> !qcore.qubit
    %iq3 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:      %iq1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:      %iq2 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:      %iq3 = qcore.alloc_qubit -> !qcore.qubit
    %oq1, %or2, %oq3 = qstruct.circuit(%iq1, %iq2, %iq3 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
    ^bb0(%q1: !qcore.qubit, %q2: !qcore.qubit, %q3: !qcore.qubit):
// CHECK-NEXT:      %oq1, %or2, %oq3 = qstruct.circuit(%iq1, %iq2, %iq3 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:      ^bb0(%q1: !qcore.qubit, %q2: !qcore.qubit, %q3: !qcore.qubit):


// Not removed:
        qref.gate<#qcore.gate.x> (%q1, %q2, %q3)
// CHECK-NEXT:          qref.gate<#qcore.gate.x> (%q1, %q2, %q3)

// Removed:
        qref.gate<#qcore.gate.id> (%q1, %q2, %q3)
        qref.gate<#qcore.gate.id> (%q1)
        qref.gate<#qcore.gate.id> (%q2, %q3)
// CHECK-NOT:           #qcore.gate.id

// Not removed:
        qref.gate<#qcore.gate.unitary<[[(1,0),(0,0)],[(0,0),(1,0)]]>> (%q1, %q2, %q3)
// CHECK-NEXT:          qref.gate<#qcore.gate.unitary<[[(1.0, 0.0), (0.0, 0.0)], [(0.0, 0.0), (1.0, 0.0)]]>> (%q1, %q2, %q3)


        qstruct.yield %q1, %q2, %q3 : !qcore.qubit, !qcore.qubit, !qcore.qubit
    }
// CHECK-NEXT:          qstruct.yield %q1, %q2, %q3 : !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      }
    "test.op"(%oq1, %or2, %oq3) : (!qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:      "test.op"(%oq1, %or2, %oq3) : (!qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
}
// CHECK-NEXT:  }
