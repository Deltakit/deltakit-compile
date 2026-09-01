// RUN: deltakit_compile compile-passes %s -p add-stim-ticks -O %t && filecheck %s --input-file %t

builtin.module {
  %q, %q_1, %q_2, %q_3 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit

  %0, %1, %2, %3 = qstruct.circuit(%q, %q_1, %q_2, %q_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit)
     -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit, %qb2: !qcore.qubit, %qb3: !qcore.qubit):
    // qref operations
    qref.gate<#qcore.gate.cx>(%qb0, %qb1, %qb2, %qb3)
    qref.reset<Z> (%qb0, %qb1, %qb2, %qb3)
    %m0, %m1, %m2 = qref.measure<Z>(%qb0, %qb1, %qb2) -> i1, i1, i1
    qref.pauli_noise<X=0.01, Y=0.01, Z=0.01>(%qb1, %qb3)

  // parallel op has gates
  qstruct.parallel<TOP> -> {
      qref.gate<#qcore.gate.h> (%qb0, %qb1)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.x> (%qb2, %qb3)
      qstruct.yield
    }

    // parallel op has measures
    %mA, %mB, %mC, %mD = qstruct.parallel<TOP> -> i1, i1, i1, i1 {
      %m0_1, %m1_1 = qref.measure<Z> (%qb0, %qb1) -> i1, i1
      qstruct.yield %m0_1, %m1_1 : i1, i1
    } {
      %m2_1, %m3_1 = qref.measure<X> (%qb2, %qb3) -> i1, i1
      qstruct.yield %m2_1, %m3_1 : i1, i1
    }

    // parallel op has resets
      qstruct.parallel<TOP> -> {
        qref.reset<Z> (%qb0, %qb1)
        qstruct.yield
    } {
        qref.reset<Z> (%qb2, %qb3)
        qstruct.yield
    }

    // parallel op has noise only
      qstruct.parallel<TOP> -> {
        qref.pauli_noise<X=0.01, Y=0.01, Z=0.01>(%qb1, %qb3)
        qstruct.yield
    } {
        qref.pauli_noise<X=0.01, Y=0.01, Z=0.01>(%qb0, %qb2)
        qstruct.yield
    }

    // nested parallel op with parallel ops inside
    qstruct.parallel<TOP> -> {
        qstruct.parallel<TOP> -> {
            qref.gate<#qcore.gate.h> (%qb0)
            qstruct.yield
        } {
            qref.gate<#qcore.gate.x> (%qb1)
            qstruct.yield
        }
        qstruct.yield
    } {
        qstruct.parallel<TOP> -> {
            qref.gate<#qcore.gate.y> (%qb2)
            qstruct.yield
        } {
            qref.gate<#qcore.gate.z> (%qb3)
            qstruct.yield
        }
        qstruct.yield
    }

    %dA, %dB = qstruct.parallel<TOP> -> !qec.detector_ref, !qec.detector_ref {
      %d0_1 = qec.detector(%mA, %mB)
      qstruct.yield %d0_1 : !qec.detector_ref
    } {
      %d1_1 = qec.detector(%mC, %mD)
      qstruct.yield %d1_1 : !qec.detector_ref
    }

    qstruct.yield %qb0, %qb1, %qb2, %qb3
       : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}



// CHECK:      builtin.module {
// CHECK-NEXT:   %q, %q_1, %q_2, %q_3 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %0, %1, %2, %3 = qstruct.circuit(%q, %q_1, %q_2, %q_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:   ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit, %qb2: !qcore.qubit, %qb3: !qcore.qubit):
// CHECK-NEXT:     qref.gate<#qcore.gate.cx> (%qb0, %qb1, %qb2, %qb3)
// CHECK-NEXT:     stim.tick
// CHECK-NEXT:     qref.reset<Z> (%qb0, %qb1, %qb2, %qb3)
// CHECK-NEXT:     stim.tick
// CHECK-NEXT:     %m0, %m1, %m2 = qref.measure<Z> (%qb0, %qb1, %qb2) -> i1, i1, i1
// CHECK-NEXT:     stim.tick
// CHECK-NEXT:     qref.pauli_noise<X = 0.01, Y = 0.01, Z = 0.01> (%qb1, %qb3)
// CHECK-NEXT:     qstruct.parallel<TOP> -> {
// CHECK-NEXT:       qref.gate<#qcore.gate.h> (%qb0, %qb1)
// CHECK-NEXT:       qstruct.yield
// CHECK-NEXT:     } {
// CHECK-NEXT:       qref.gate<#qcore.gate.x> (%qb2, %qb3)
// CHECK-NEXT:       qstruct.yield
// CHECK-NEXT:     }
// CHECK-NEXT:     stim.tick
// CHECK-NEXT:     %mA, %mB, %mC, %mD = qstruct.parallel<TOP> -> i1, i1, i1, i1 {
// CHECK-NEXT:       %m0_1, %m1_1 = qref.measure<Z> (%qb0, %qb1) -> i1, i1
// CHECK-NEXT:       qstruct.yield %m0_1, %m1_1 : i1, i1
// CHECK-NEXT:     } {
// CHECK-NEXT:       %m2_1, %m3 = qref.measure<X> (%qb2, %qb3) -> i1, i1
// CHECK-NEXT:       qstruct.yield %m2_1, %m3 : i1, i1
// CHECK-NEXT:     }
// CHECK-NEXT:     stim.tick
// CHECK-NEXT:     qstruct.parallel<TOP> -> {
// CHECK-NEXT:       qref.reset<Z> (%qb0, %qb1)
// CHECK-NEXT:       qstruct.yield
// CHECK-NEXT:     } {
// CHECK-NEXT:       qref.reset<Z> (%qb2, %qb3)
// CHECK-NEXT:       qstruct.yield
// CHECK-NEXT:     }
// CHECK-NEXT:     stim.tick
// CHECK-NEXT:     qstruct.parallel<TOP> -> {
// CHECK-NEXT:       qref.pauli_noise<X = 0.01, Y = 0.01, Z = 0.01> (%qb1, %qb3)
// CHECK-NEXT:       qstruct.yield
// CHECK-NEXT:     } {
// CHECK-NEXT:       qref.pauli_noise<X = 0.01, Y = 0.01, Z = 0.01> (%qb0, %qb2)
// CHECK-NEXT:       qstruct.yield
// CHECK-NEXT:     }
// CHECK-NEXT:     qstruct.parallel<TOP> -> {
// CHECK-NEXT:       qstruct.parallel<TOP> -> {
// CHECK-NEXT:         qref.gate<#qcore.gate.h> (%qb0)
// CHECK-NEXT:         qstruct.yield
// CHECK-NEXT:       } {
// CHECK-NEXT:         qref.gate<#qcore.gate.x> (%qb1)
// CHECK-NEXT:         qstruct.yield
// CHECK-NEXT:       }
// CHECK-NEXT:       qstruct.yield
// CHECK-NEXT:     } {
// CHECK-NEXT:       qstruct.parallel<TOP> -> {
// CHECK-NEXT:         qref.gate<#qcore.gate.y> (%qb2)
// CHECK-NEXT:         qstruct.yield
// CHECK-NEXT:       } {
// CHECK-NEXT:         qref.gate<#qcore.gate.z> (%qb3)
// CHECK-NEXT:         qstruct.yield
// CHECK-NEXT:       }
// CHECK-NEXT:       qstruct.yield
// CHECK-NEXT:     }
// CHECK-NEXT:     stim.tick
// CHECK-NEXT:     %dA, %dB = qstruct.parallel<TOP> -> !qec.detector_ref, !qec.detector_ref {
// CHECK-NEXT:       %d0 = qec.detector(%mA, %mB)
// CHECK-NEXT:       qstruct.yield %d0 : !qec.detector_ref
// CHECK-NEXT:     } {
// CHECK-NEXT:       %d1 = qec.detector(%mC, %mD)
// CHECK-NEXT:       qstruct.yield %d1 : !qec.detector_ref
// CHECK-NEXT:     }
// CHECK-NEXT:     qstruct.yield %qb0, %qb1, %qb2, %qb3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   }
// CHECK-NEXT: }
