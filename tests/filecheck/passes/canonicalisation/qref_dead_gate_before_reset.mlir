// RUN: deltakit_compile compile-passes %s -t -p canonicalize -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK:       builtin.module {
    %iq1 = qcore.alloc_qubit -> !qcore.qubit
    %iq2 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:      %iq1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:      %iq2 = qcore.alloc_qubit -> !qcore.qubit
    %oq1, %oq2 = qstruct.circuit(%iq1, %iq2 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
    ^bb0(%q1: !qcore.qubit, %q2: !qcore.qubit):
// CHECK-NEXT:      %oq1, %oq2 = qstruct.circuit(%iq1, %iq2 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:      ^bb0(%q1: !qcore.qubit, %q2: !qcore.qubit):

// The case from Deltakit/deltakit#286: a basis change left behind after a
// measurement, on a qubit that is reset before anything else touches it.
        %m1 = qref.measure<Z>(%q1) -> i1
        qref.gate<#qcore.gate.h> (%q1)
        qref.reset<Z> (%q1)
// CHECK-NEXT:          %m1 = qref.measure<Z> (%q1) -> i1
// CHECK-NEXT:          qref.reset<Z> (%q1)

// Not removed: %q2 is used by a two-qubit gate between the gate and the reset.
        qref.gate<#qcore.gate.h> (%q2)
        qref.gate<#qcore.gate.cx> (%q1, %q2)
        qref.reset<Z> (%q2)
// CHECK-NEXT:          qref.gate<#qcore.gate.h> (%q2)
// CHECK-NEXT:          qref.gate<#qcore.gate.cx> (%q1, %q2)
// CHECK-NEXT:          qref.reset<Z> (%q2)

// Not removed, by choice rather than by necessity: a two-qubit gate whose
// qubits are all reset straight after is in fact dead, but this pattern only
// removes single-qubit gates, so that each removal is a decision about one
// qubit. Lifting that is follow-up work, and this case pins the current
// behaviour so the restriction cannot be dropped by accident.
        qref.gate<#qcore.gate.cx> (%q1, %q2)
        qref.reset<Z> (%q1, %q2)
// CHECK-NEXT:          qref.gate<#qcore.gate.cx> (%q1, %q2)
// CHECK-NEXT:          qref.reset<Z> (%q1, %q2)

// Not removed: the gate covers a qubit that is not being reset. Removing it as
// a unit would be wrong and this pattern does not split broadcasts.
        qref.gate<#qcore.gate.h> (%q1, %q2)
        qref.reset<Z> (%q1)
// CHECK-NEXT:          qref.gate<#qcore.gate.h> (%q1, %q2)
// CHECK-NEXT:          qref.reset<Z> (%q1)

// Not removed: an operation carrying a region uses the qubits it captures
// without listing them as operands, so the repeat below measures %q1 even
// though %q1 appears nowhere in its operand list. Walking past it would delete
// a gate that is very much alive.
        qref.gate<#qcore.gate.h> (%q1)
        qstruct.repeat<2> () -> {
            %m2 = qref.measure<Z>(%q1) -> i1
            qstruct.yield
        }
        qref.reset<Z> (%q1)
// CHECK-NEXT:          qref.gate<#qcore.gate.h> (%q1)
// CHECK-NEXT:          qstruct.repeat<2> () -> {
// CHECK-NEXT:              %m2 = qref.measure<Z> (%q1) -> i1
// CHECK-NEXT:              qstruct.yield
// CHECK-NEXT:          }
// CHECK-NEXT:          qref.reset<Z> (%q1)

        qstruct.yield %q1, %q2 : !qcore.qubit, !qcore.qubit
    }
// CHECK-NEXT:          qstruct.yield %q1, %q2 : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      }
    "test.op"(%oq1, %oq2) : (!qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:      "test.op"(%oq1, %oq2) : (!qcore.qubit, !qcore.qubit) -> ()
}
// CHECK-NEXT:  }
