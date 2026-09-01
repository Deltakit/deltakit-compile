// RUN: deltakit_compile compile-passes -t %s -p stim-import-pipeline --pass-args '{"verify_between_passes": true, "extract_tags_to_attributes": true, "respect_tick_parallelisation": false}' -O %t && filecheck %s --input-file %t

builtin.module {
  %0 = stim.qubit_alloc 0 -> !stim.qubit
  %1 = stim.qubit_alloc 1 -> !stim.qubit
  %2 = stim.qubit_alloc 3 -> !stim.qubit
  %3 = stim.qubit_alloc 2 -> !stim.qubit
  %4 = stim.qubit_alloc 4 -> !stim.qubit
  stim.assign_qubit_coord <0.0, 0.0> (%0 : !stim.qubit)
  stim.assign_qubit_coord <0.0, 0.0> (%1 : !stim.qubit)
  stim.reset Z (%0, %2, %1)
  stim.tick
  stim.reset X (%3, %4)
  stim.tick
  stim.clifford I (%0, %2, %1)
  stim.tick
  stim.clifford CZ (%3, %1, %4, %2)
  stim.tick
  stim.clifford CZ (%3, %2, %4, %0)
  stim.tick
  %5, %6 = stim.measure X (%3, %4) -> i1, i1
  stim.tick
}

// CHECK:          builtin.module {
// CHECK-NEXT:      %0 = qcore.alloc_qubit<coords = [(0.0, 0.0)], ids = [0]> -> !qcore.qubit
// CHECK-NEXT:      %1 = qcore.alloc_qubit<coords = [(0.0, 0.0)], ids = [1]> -> !qcore.qubit
// CHECK-NEXT:      %2 = qcore.alloc_qubit<ids = [3]> -> !qcore.qubit
// CHECK-NEXT:      %3 = qcore.alloc_qubit<ids = [2]> -> !qcore.qubit
// CHECK-NEXT:      %4 = qcore.alloc_qubit<ids = [4]> -> !qcore.qubit
// CHECK-NEXT:      %5, %6, %7, %8, %9 = qstruct.circuit(%0, %1, %2, %3, %4 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:      ^bb0(%10: !qcore.qubit, %11: !qcore.qubit, %12: !qcore.qubit, %13: !qcore.qubit, %14: !qcore.qubit):
// CHECK-NEXT:        qstruct.parallel<TOP> -> {
// CHECK-NEXT:          qref.reset<Z> (%10, %12, %11)
// CHECK-NEXT:          qstruct.yield
// CHECK-NEXT:        } {
// CHECK-NEXT:          qref.reset<X> (%13, %14)
// CHECK-NEXT:          qstruct.yield
// CHECK-NEXT:        }
// CHECK-NEXT:        qref.gate<#qcore.gate.cz> (%13, %11, %14, %12)
// CHECK-NEXT:        qref.gate<#qcore.gate.cz> (%13, %12, %14, %10)
// CHECK-NEXT:        %15, %16 = qref.measure<X> (%13, %14) -> i1, i1
// CHECK-NEXT:        qec.measurement_round(%15, %16 : i1, i1)
// CHECK-NEXT:        qstruct.yield %10, %11, %12, %13, %14 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      }
// CHECK-NEXT:    }
