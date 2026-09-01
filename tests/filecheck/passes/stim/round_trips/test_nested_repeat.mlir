// RUN: deltakit_compile compile-passes -t %s -p stim-import-pipeline -p stim-export-pipeline --pass-args '{"verify_between_passes": true, "extract_tags_to_attributes": false, "realign_detectors": false}' -O %t.mlir && filecheck %s --input-file %t.mlir && deltakit_compile compile-passes -t %t.mlir -p stim-import-pipeline -p stim-export-pipeline --pass-args '{"verify_between_passes": true, "extract_tags_to_attributes": false, "realign_detectors": false}' -O %t.2.mlir && filecheck %s --input-file %t.2.mlir

// Nested repeat test. Detectors not realigned.

builtin.module {
  %0 = stim.qubit_alloc 0 -> !stim.qubit
  %1 = stim.qubit_alloc 1 -> !stim.qubit
  %2 = stim.qubit_alloc 2 -> !stim.qubit
  %3 = stim.qubit_alloc 3 -> !stim.qubit
  %4 = stim.qubit_alloc 4 -> !stim.qubit
  stim.assign_qubit_coord <4.0, 0.0> (%0 : !stim.qubit)
  stim.assign_qubit_coord <0.0, 0.0> (%1 : !stim.qubit)
  stim.assign_qubit_coord <1.0, 0.0> (%2 : !stim.qubit)
  stim.assign_qubit_coord <2.0, 0.0> (%3 : !stim.qubit)
  stim.assign_qubit_coord <3.0, 0.0> (%4 : !stim.qubit)
  %f1 = "test.op"() : () -> f64

// CHECK:       builtin.module {
// CHECK-NEXT:        %0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:        stim.assign_qubit_coord <4.0, 0.0> (%0 : !stim.qubit)
// CHECK-NEXT:        %1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:        stim.assign_qubit_coord <0.0, 0.0> (%1 : !stim.qubit)
// CHECK-NEXT:        %2 = stim.qubit_alloc 2 -> !stim.qubit
// CHECK-NEXT:        stim.assign_qubit_coord <1.0, 0.0> (%2 : !stim.qubit)
// CHECK-NEXT:        %3 = stim.qubit_alloc 3 -> !stim.qubit
// CHECK-NEXT:        stim.assign_qubit_coord <2.0, 0.0> (%3 : !stim.qubit)
// CHECK-NEXT:        %4 = stim.qubit_alloc 4 -> !stim.qubit
// CHECK-NEXT:        stim.assign_qubit_coord <3.0, 0.0> (%4 : !stim.qubit)
// CHECK-NEXT:        %f1 = "test.op"() : () -> f64

  stim.reset Z (%0, %3, %1)
  stim.reset X (%0, %3, %1)
  stim.tick
  stim.reset X (%2, %4)
  stim.tick
  stim.clifford I (%0, %3, %1)
  stim.tick
  stim.clifford CZ (%2, %1, %4, %3)
  stim.tick
  stim.clifford CZ (%2, %3, %4, %0)
  stim.tick

// CHECK-NEXT:        stim.reset Z (%0, %3, %1)
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        stim.reset X (%0, %3, %1)
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        stim.reset X (%2, %4)
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        stim.clifford CZ (%2, %1, %4, %3)
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        stim.clifford CZ (%2, %3, %4, %0)
// CHECK-NEXT:        stim.tick

  %5, %6 = stim.measure X (%2, %4) -> i1, i1
  stim.tick
  stim.detector <[1.0, 0.0, 0.0]> (%5 : i1)
  stim.detector <[3.0, 0.0, 2.0]> (%6 : i1)

// CHECK-NEXT:        %5, %6 = stim.measure X (%2, %4) -> i1, i1
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        stim.detector <[1.0, 0.0, 0.0]> (%5 : i1)
// CHECK-NEXT:        stim.detector <[3.0, 0.0, 2.0]> (%6 : i1)

  %7, %8 = stim.repeat 6 (%5, %6 : i1, i1) -> i1, i1 {
  ^bb0(%9: i1, %10: i1):
    stim.reset X (%2, %4)
    stim.tick
    stim.clifford I (%0, %3, %1)
    stim.tick
    stim.clifford CZ (%2, %1, %4, %3)
    stim.tick
    stim.clifford CZ (%2, %3, %4, %0)
    stim.tick

// CHECK-NEXT:        %7, %8 = stim.repeat 6 (%5, %6 : i1, i1) -> i1, i1 {
// CHECK-NEXT:        ^bb0(%9: i1, %10: i1):
// CHECK-NEXT:          stim.reset X (%2, %4)
// CHECK-NEXT:          stim.tick
// CHECK-NEXT:          stim.clifford CZ (%2, %1, %4, %3)
// CHECK-NEXT:          stim.tick
// CHECK-NEXT:          stim.clifford CZ (%2, %3, %4, %0)
// CHECK-NEXT:          stim.tick

    %11, %12 = stim.measure X (%2, %4) -> i1, i1
    stim.detector <[1.0, 0.0, 0.0]> (%9, %11 : i1, i1)
    stim.detector <[3.0, 0.0, 0.0]> (%10, %12 : i1, i1)
    stim.detector <[3.0, 0.0, 2.0]> (%10, %12 : i1, i1)
    stim.detector <[3.0, 0.0, 3.0]> (%11, %12 : i1, i1)
    stim.shift_coord <[0.0, 0.0, 2.0]>

// CHECK-NEXT:          %11, %12 = stim.measure X (%2, %4) -> i1, i1
// CHECK-NEXT:          stim.tick
// CHECK-NEXT:          stim.detector <[1.0, 0.0, 0.0]> (%9, %11 : i1, i1)
// CHECK-NEXT:          stim.detector <[3.0, 0.0, 0.0]> (%10, %12 : i1, i1)
// CHECK-NEXT:          stim.detector <[3.0, 0.0, 2.0]> (%10, %12 : i1, i1)
// CHECK-NEXT:          stim.detector <[3.0, 0.0, 3.0]> (%11, %12 : i1, i1)

    %13, %14, %15, %16 = stim.repeat 4 (%9, %10, %11, %12 : i1, i1, i1, i1) -> i1, i1, i1, i1 {
    ^bb1(%17: i1, %18: i1, %19: i1, %20: i1):
      stim.reset X (%2, %4)
      stim.tick
      stim.clifford I (%0, %3, %1)
      stim.tick
      stim.clifford CZ (%2, %1, %4, %3)
      stim.tick
      stim.clifford CZ (%2, %3, %4, %0)
      stim.tick

// CHECK-NEXT:          %13, %14, %15, %16 = stim.repeat 4 (%9, %10, %11, %12 : i1, i1, i1, i1) -> i1, i1, i1, i1 {
// CHECK-NEXT:          ^bb1(%17: i1, %18: i1, %19: i1, %20: i1):
// CHECK-NEXT:            stim.reset X (%2, %4)
// CHECK-NEXT:            stim.tick
// CHECK-NEXT:            stim.clifford CZ (%2, %1, %4, %3)
// CHECK-NEXT:            stim.tick
// CHECK-NEXT:            stim.clifford CZ (%2, %3, %4, %0)
// CHECK-NEXT:            stim.tick

      %21, %22 = stim.measure X (%2, %4) -> i1, i1
      stim.detector <[1.0, 0.0, 0.0]> (%19, %21 : i1, i1)
      stim.detector <[3.0, 0.0, 0.0]> (%20, %22 : i1, i1)
      stim.detector <[3.0, 0.0, 2.0]> (%20, %22 : i1, i1)
      stim.detector <[3.0, 0.0, 3.0]> (%21, %22 : i1, i1)
      stim.shift_coord <[0.0, 0.0, 1.0]>
      stim.observable_include <0> (%22 : i1)
      stim.yield %19, %20, %21, %22 : i1, i1, i1, i1
    }

// CHECK-NEXT:            %21, %22 = stim.measure X (%2, %4) -> i1, i1
// CHECK-NEXT:            stim.tick
// CHECK-NEXT:            stim.detector <[1.0, 0.0, 2.0]> (%19, %21 : i1, i1)
// CHECK-NEXT:            stim.detector <[3.0, 0.0, 2.0]> (%20, %22 : i1, i1)
// CHECK-NEXT:            stim.detector <[3.0, 0.0, 4.0]> (%20, %22 : i1, i1)
// CHECK-NEXT:            stim.detector <[3.0, 0.0, 5.0]> (%21, %22 : i1, i1)
// CHECK-NEXT:            stim.observable_include <0> (%22 : i1)
// CHECK-NEXT:            stim.shift_coord <[0.0, 0.0, 1.0]>
// CHECK-NEXT:            stim.yield %19, %20, %21, %22 : i1, i1, i1, i1

    stim.detector <[1.0, 0.0, 0.0]> (%13, %15 : i1, i1)
    stim.detector <[3.0, 0.0, 0.0]> (%14, %16 : i1, i1)
    stim.detector <[3.0, 0.0, 2.0]> (%14, %16 : i1, i1)
    stim.detector <[3.0, 0.0, 3.0]> (%15, %16 : i1, i1)
    stim.shift_coord <[0.0, 0.0, 2.0]>
    stim.yield %15, %16 : i1, i1
  }

// CHECK-NEXT:          }
// CHECK-NEXT:          stim.detector <[1.0, 0.0, 2.0]> (%13, %15 : i1, i1)
// CHECK-NEXT:          stim.detector <[3.0, 0.0, 2.0]> (%14, %16 : i1, i1)
// CHECK-NEXT:          stim.detector <[3.0, 0.0, 4.0]> (%14, %16 : i1, i1)
// CHECK-NEXT:          stim.detector <[3.0, 0.0, 5.0]> (%15, %16 : i1, i1)
// CHECK-NEXT:          stim.shift_coord <[0.0, 0.0, 4.0]>
// CHECK-NEXT:          stim.yield %15, %16 : i1, i1
// CHECK-NEXT:        }
// CHECK-NEXT:        stim.reset X (%2, %4)

  stim.reset X (%2, %4)
  stim.tick
  stim.clifford I (%0, %3, %1)
  stim.tick
  stim.clifford CZ (%2, %1, %4, %3)
  stim.clifford CZ (%2, %3, %4, %0)
  %23, %24 = stim.measure  X <0.4> (%2, %4) -> i1, i1
  stim.tick
  %25, %26, %27 = stim.measure Z (%0, %3, %1) -> i1, i1, i1
  stim.detector <[1.0, 0.0, 0.0]> (%7, %23 : i1, i1)
  stim.detector <[3.0, 0.0, 0.0]> (%8, %24 : i1, i1)
  stim.shift_coord <[0.0, 0.0, 1.0]>
  stim.observable_include <0> (%27 : i1)
  stim.detector <[1.0, 0.0, 0.0]> (%23, %27, %26 : i1, i1, i1)
  stim.detector <[3.0, 0.0, 0.0]> (%24, %25, %26 : i1, i1, i1)
  stim.shift_coord <[0.0, 0.0, 1.0]>
}

// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        stim.clifford CZ (%2, %1, %4, %3)
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        stim.clifford CZ (%2, %3, %4, %0)
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        %23, %24 = stim.measure X <0.4> (%2, %4) -> i1, i1
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        %25, %26, %27 = stim.measure Z (%0, %3, %1) -> i1, i1, i1
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        stim.detector <[1.0, 0.0, 0.0]> (%7, %23 : i1, i1)
// CHECK-NEXT:        stim.detector <[3.0, 0.0, 0.0]> (%8, %24 : i1, i1)
// CHECK-NEXT:        stim.observable_include <0> (%27 : i1)
// CHECK-NEXT:        stim.detector <[1.0, 0.0, 1.0]> (%23, %27, %26 : i1, i1, i1)
// CHECK-NEXT:        stim.detector <[3.0, 0.0, 1.0]> (%24, %25, %26 : i1, i1, i1)
// CHECK-NEXT:      }
