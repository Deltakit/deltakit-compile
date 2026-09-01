// RUN: deltakit_compile compile-passes -t %s -p gate-layer-parallelise -O %t && filecheck %s --input-file %t

builtin.module {
  %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %0, %1, %2 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, i1 {
  ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit):

// CHECK:       builtin.module {
// CHECK-NEXT:    %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    %0, %1, %2 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, i1 {
// CHECK-NEXT:    ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit):

    qref.gate<#qcore.gate.x> (%q0_1)
    stim.tick

// CHECK-NEXT:      qref.gate<#qcore.gate.x> (%q0_1)
// CHECK-NEXT:      stim.tick

    %m = qref.measure<X> (%q1_1) -> i1
    qref.pauli_noise<X=0.01, Y=0.01, Z=0.01> (%q1_1) {pos = "A"}
    qref.pauli_noise<X=0.02, Y=0.02, Z=0.02> (%q0_1) {pos = "B"}
    qref.gate<#qcore.gate.z> (%q0_1)
    qref.pauli_noise<X=0.01, Y=0.01, Z=0.01> (%q0_1) {pos = "C"}

// CHECK-NEXT:      %m = qstruct.parallel<TOP> -> i1 {
// CHECK-NEXT:        %m_1 = qref.measure<X> (%q1_1) -> i1
// CHECK-NEXT:        qref.pauli_noise<X = 0.01, Y = 0.01, Z = 0.01> (%q1_1) {pos = "A"}
// CHECK-NEXT:        qstruct.yield %m_1 : i1
// CHECK-NEXT:      } {
// CHECK-NEXT:        qref.pauli_noise<X = 0.02, Y = 0.02, Z = 0.02> (%q0_1) {pos = "B"}
// CHECK-NEXT:        qref.gate<#qcore.gate.z> (%q0_1)
// CHECK-NEXT:        qref.pauli_noise<X = 0.01, Y = 0.01, Z = 0.01> (%q0_1) {pos = "C"}
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      }

    qref.pauli_noise<X=0.5, Y=0.25, Z=0.125> (%q1_1) {pos = "D"}
    qref.pauli_noise<X=0.5, Y=0.25, Z=0.125> (%q0_1) {pos = "E"}

// CHECK-NEXT:      qstruct.parallel<TOP> -> {
// CHECK-NEXT:        qref.pauli_noise<X = 0.5, Y = 0.25, Z = 0.125> (%q1_1) {pos = "D"}
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      } {
// CHECK-NEXT:        qref.pauli_noise<X = 0.5, Y = 0.25, Z = 0.125> (%q0_1) {pos = "E"}
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      }

    qref.pauli_noise<X=0.5, Y=0.25, Z=0.125> (%q0_1) {pos = "F"}
    qref.reset<X> (%q0_1, %q1_1)

// CHECK-NEXT:      qref.pauli_noise<X = 0.5, Y = 0.25, Z = 0.125> (%q0_1) {pos = "F"}
// CHECK-NEXT:      qref.reset<X> (%q0_1, %q1_1)

    qref.pauli_noise<X=0.01, Y=0.01, Z=0.01> (%q1_1) {pos = "G"}
    qref.pauli_noise<X=0.5, Y=0.25, Z=0.125> (%q0_1) {pos = "H"}
    %m1 = qref.measure<X> (%q1_1) -> i1
    qstruct.yield %q0_1, %q1_1, %m : !qcore.qubit, !qcore.qubit, i1
  }
}

// CHECK-NEXT:      qstruct.parallel<TOP> -> {
// CHECK-NEXT:        qref.pauli_noise<X = 0.01, Y = 0.01, Z = 0.01> (%q1_1) {pos = "G"}
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      } {
// CHECK-NEXT:        qref.pauli_noise<X = 0.5, Y = 0.25, Z = 0.125> (%q0_1) {pos = "H"}
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      }
// CHECK-NEXT:      %m1 = qref.measure<X> (%q1_1) -> i1
// CHECK-NEXT:      qstruct.yield %q0_1, %q1_1, %m : !qcore.qubit, !qcore.qubit, i1
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----
// CHECK: ----

builtin.module {
  %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %0, %1, %2 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, i1 {
  ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit):

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    %0, %1, %2 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, i1 {
// CHECK-NEXT:    ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit):

    qref.gate<#qcore.gate.x> (%q0_1)
    stim.tick

// CHECK-NEXT:      qref.gate<#qcore.gate.x> (%q0_1)
// CHECK-NEXT:      stim.tick

    %m = qref.measure<X> (%q1_1) -> i1
    qref.pauli_noise<X=0.01, Y=0.01, Z=0.01> (%q1_1) {pos = "A"}
    qref.pauli_noise<X=0.02, Y=0.02, Z=0.02> (%q0_1) {pos = "B"}
    qref.gate<#qcore.gate.z> (%q0_1)

// CHECK-NEXT:      %m = qstruct.parallel<TOP> -> i1 {
// CHECK-NEXT:        %m_1 = qref.measure<X> (%q1_1) -> i1
// CHECK-NEXT:        qref.pauli_noise<X = 0.01, Y = 0.01, Z = 0.01> (%q1_1) {pos = "A"}
// CHECK-NEXT:        qstruct.yield %m_1 : i1
// CHECK-NEXT:      } {
// CHECK-NEXT:        qref.pauli_noise<X = 0.02, Y = 0.02, Z = 0.02> (%q0_1) {pos = "B"}
// CHECK-NEXT:        qref.gate<#qcore.gate.z> (%q0_1)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      }

    "test.op"() ({
      ^bb1:
        qref.pauli_noise<X=0.01, Y=0.01, Z=0.01> (%q0_1) {pos = "C"}
        qref.pauli_noise<X=0.5, Y=0.25, Z=0.125> (%q1_1) {pos = "D"}

// CHECK-NEXT:      "test.op"() ({
// CHECK-NEXT:        qstruct.parallel<TOP> -> {
// CHECK-NEXT:          qref.pauli_noise<X = 0.01, Y = 0.01, Z = 0.01> (%q0_1) {pos = "C"}
// CHECK-NEXT:          qstruct.yield
// CHECK-NEXT:        } {
// CHECK-NEXT:          qref.pauli_noise<X = 0.5, Y = 0.25, Z = 0.125> (%q1_1) {pos = "D"}
// CHECK-NEXT:          qstruct.yield
// CHECK-NEXT:        }


        qref.pauli_noise<X=0.5, Y=0.25, Z=0.125> (%q0_1) {pos = "E"}

// CHECK-NEXT:        qref.pauli_noise<X = 0.5, Y = 0.25, Z = 0.125> (%q0_1) {pos = "E"}

        qref.pauli_noise<X=0.5, Y=0.25, Z=0.125> (%q0_1) {pos = "F"}
        qref.reset<X> (%q0_1, %q1_1)

// CHECK-NEXT:        qref.pauli_noise<X = 0.5, Y = 0.25, Z = 0.125> (%q0_1) {pos = "F"}
// CHECK-NEXT:        qref.reset<X> (%q0_1, %q1_1)

        qref.pauli_noise<X=0.01, Y=0.01, Z=0.01> (%q1_1) {pos = "G"}
        qref.pauli_noise<X=0.5, Y=0.25, Z=0.125> (%q0_1) {pos = "H"}

// CHECK-NEXT:        qstruct.parallel<TOP> -> {
// CHECK-NEXT:          qref.pauli_noise<X = 0.01, Y = 0.01, Z = 0.01> (%q1_1) {pos = "G"}
// CHECK-NEXT:          qstruct.yield
// CHECK-NEXT:        } {
// CHECK-NEXT:          qref.pauli_noise<X = 0.5, Y = 0.25, Z = 0.125> (%q0_1) {pos = "H"}
// CHECK-NEXT:          qstruct.yield
// CHECK-NEXT:        }

        "test.termop"() : () -> ()
    }) : () -> ()
    qref.gate<#qcore.gate.z> (%q0_1)
    qstruct.yield %q0_1, %q1_1, %m : !qcore.qubit, !qcore.qubit, i1
  }
}

// CHECK-NEXT:        "test.termop"() : () -> ()
// CHECK-NEXT:      }) : () -> ()
// CHECK-NEXT:      qref.gate<#qcore.gate.z> (%q0_1)
// CHECK-NEXT:      qstruct.yield %q0_1, %q1_1, %m : !qcore.qubit, !qcore.qubit, i1
// CHECK-NEXT:    }
// CHECK-NEXT:  }
