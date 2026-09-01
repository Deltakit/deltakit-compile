// RUN: deltakit_compile compile-passes -t %s -p stim-import-pipeline -p stim-export-pipeline --pass-args '{"verify_between_passes": true, "extract_tags_to_attributes": true}' -O %t.mlir && filecheck %s --input-file %t.mlir && deltakit_compile compile-passes -t %t.mlir -p stim-import-pipeline -p stim-export-pipeline --pass-args '{"verify_between_passes": true, "extract_tags_to_attributes": true}' -O %t.2.mlir && filecheck %s --input-file %t.2.mlir

// Tags, noise, gates, measures and simple nested repeats. Stim tags are extracted, so valid stim.tag attributes are lost in the round trip.
// Detectors rearranged so ordering is not preserved.

builtin.module {
  %0 = stim.qubit_alloc 0  {stim.tag = "{\"array\": [\"#Z\", 1, \"#1\", {\"key\": null}\\C}"} -> !stim.qubit
  %1 = stim.qubit_alloc 3 -> !stim.qubit
  %2 = stim.qubit_alloc 2 -> !stim.qubit
  %3 = stim.qubit_alloc 1 -> !stim.qubit
  %4 = stim.qubit_alloc 4 -> !stim.qubit
  stim.assign_qubit_coord <4.0, 0.0> (%0 : !stim.qubit)
  stim.assign_qubit_coord <0.0, 0.0> (%1 : !stim.qubit)
  stim.assign_qubit_coord <1.0, 0.0> (%2 : !stim.qubit)
  stim.assign_qubit_coord <2.0, 0.0> (%3 : !stim.qubit)
  stim.assign_qubit_coord <3.0, 0.0> (%4 : !stim.qubit)

// CHECK:             builtin.module {
// CHECK-NEXT:        %0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:        stim.assign_qubit_coord <4.0, 0.0> (%0 : !stim.qubit)
// CHECK-NEXT:        %1 = stim.qubit_alloc 3 -> !stim.qubit
// CHECK-NEXT:        stim.assign_qubit_coord <0.0, 0.0> (%1 : !stim.qubit)
// CHECK-NEXT:        %2 = stim.qubit_alloc 2 -> !stim.qubit
// CHECK-NEXT:        stim.assign_qubit_coord <1.0, 0.0> (%2 : !stim.qubit)
// CHECK-NEXT:        %3 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:        stim.assign_qubit_coord <2.0, 0.0> (%3 : !stim.qubit)
// CHECK-NEXT:        %4 = stim.qubit_alloc 4 -> !stim.qubit
// CHECK-NEXT:        stim.assign_qubit_coord <3.0, 0.0> (%4 : !stim.qubit)

  stim.reset Z (%0, %3, %1)  {stim.tag = "{\22my_type\22: \22#!test.type<\5C\22test\5C\22>\22}"}
  %m7 = stim.mpp[X, Z, Y] <0.05> (%0, %3, %1) -> i1
  stim.clifford CZ (%2, %1, %4, %3)
  stim.tick
  stim.reset X (%2, %4)
  stim.tick
  stim.clifford I (%0, %3, %1) {stim.tag = "{\"my_type\": \"#!test.type<\\\"test\\\">\"}"}
  stim.tick
  stim.clifford CZ (%2, %1, %4, %3)
  stim.tick
  stim.clifford CZ (%2, %3, %4, %0)

// CHECK-NEXT:        stim.reset Z (%0, %3, %1)
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        %m7 = stim.mpp[X, Z, Y] <0.05> (%0, %3, %1) -> i1
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        stim.clifford CZ (%2, %1, %4, %3)
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        stim.reset X (%2, %4)
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        stim.clifford CZ (%2, %1, %4, %3)
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        stim.clifford CZ (%2, %3, %4, %0)
// CHECK-NEXT:        stim.tick

  %e = stim.empty -> i1
  stim.depolarize1 <0.001> (%2, %4) {stim.tag = "{\22my_type\22: \22#!test.type<\5C\22test\5C\22>\22}"}
  stim.depolarize2 <0.002> (%2, %4) {stim.tag = "{\"my_type\": \"#!test.type<\\\"test\\\">\"}" }
  stim.tick
  %5, %6 = stim.measure X (%2, %4) {stim.tag = "{\"my_type\": \"#!test.type<\\\"test\\\">\"}"} -> i1, i1
  stim.tick

// CHECK-NEXT:        stim.depolarize1 <0.001> (%2, %4)
// CHECK-NEXT:        stim.depolarize2 <0.002{{(00000[0-9]*)?}}> (%2, %4)
// CHECK-NEXT:        %5, %6 = stim.measure X (%2, %4) -> i1, i1
// CHECK-NEXT:        stim.tick

  stim.detector <[1.0, 0.0, 0.0]> (%5 : i1) {stim.tag = "{\22my_type\22: \22#!test.type<\5C\22test\5C\22>\22}"}
  stim.detector <[3.0, 0.0, 2.0]> (%6 : i1)

// CHECK-NEXT:        stim.detector <[1.0, 0.0, 0.0]> (%5 : i1)
// CHECK-NEXT:        stim.detector <[3.0, 0.0, 0.0]> (%6 : i1)

  %7, %8 = stim.repeat 1 (%5, %6 : i1, i1) -> i1, i1 {
  ^bb0(%9: i1, %10: i1):
    %11, %12 = stim.repeat {stim.tag = "{\22my_type\22: \22#!test.type<\5C\22test\5C\22>\22}"} 2 (%9, %10 : i1, i1) -> i1, i1 {
    ^bb1(%13: i1, %14: i1):
      stim.reset X (%2, %4)
      stim.tick
      stim.clifford I (%0, %3, %1)
      stim.tick
      stim.clifford CZ (%2, %1, %4, %3)
      stim.tick
      stim.clifford CZ (%2, %3, %4, %0)

// CHECK-NEXT:        %7, %8 = stim.repeat 2 (%5, %6 : i1, i1) -> i1, i1 {
// CHECK-NEXT:        ^bb0(%9: i1, %10: i1):
// CHECK-NEXT:          stim.reset X (%2, %4)
// CHECK-NEXT:          stim.tick
// CHECK-NEXT:          stim.clifford CZ (%2, %1, %4, %3)
// CHECK-NEXT:          stim.tick
// CHECK-NEXT:          stim.clifford CZ (%2, %3, %4, %0)
// CHECK-NEXT:          stim.tick

      stim.pauli_channel_1 <0.01, 0.02, 0.03> (%2, %4) {stim.tag = "4324"}
      stim.tick
      %15, %16 = stim.measure X (%2, %4) -> i1, i1

// CHECK-NEXT:          stim.pauli_channel_1 <0.01, 0.02, 0.03> (%2, %4) {stim.tag = "4324"}
// CHECK-NEXT:          %11, %12 = stim.measure X (%2, %4) -> i1, i1
// CHECK-NEXT:          stim.tick

      stim.detector <[1.0, 0.0, 0.0]> (%13, %15 : i1, i1)
      stim.detector <[3.0, 0.0, 0.0]> (%14, %16 : i1, i1)
      stim.detector <[3.0, 0.0, 2.0]> (%14, %16 : i1, i1)
      stim.detector <[3.0, 0.0, 3.0]> (%15, %16 : i1, i1)
      stim.shift_coord <[0.0, 0.0, 1.0]>
      stim.yield %15, %16 : i1, i1
    }
    stim.yield %11, %12 : i1, i1
  }

// CHECK-NEXT:          stim.detector <[1.0, 0.0, 0.0]> (%9, %11 : i1, i1)
// CHECK-NEXT:          stim.detector <[3.0, 0.0, 0.0]> (%10, %12 : i1, i1)
// CHECK-NEXT:          stim.detector <[3.0, 0.0, 2.0]> (%10, %12 : i1, i1)
// CHECK-NEXT:          stim.detector <[3.0, 0.0, 3.0]> (%11, %12 : i1, i1)
// CHECK-NEXT:          stim.shift_coord <[0.0, 0.0, 1.0]>
// CHECK-NEXT:          stim.yield %11, %12 : i1, i1
// CHECK-NEXT:        }

  stim.reset X (%2, %4)
  stim.tick
  stim.clifford I (%0, %3, %1)
  stim.tick
  stim.clifford CZ (%2, %1, %4, %3)
  stim.tick
  stim.clifford CZ (%2, %3, %4, %0)
  stim.tick

// CHECK-NEXT:        stim.reset X (%2, %4)
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        stim.clifford CZ (%2, %1, %4, %3)
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        stim.clifford CZ (%2, %3, %4, %0)
// CHECK-NEXT:        stim.tick

  %17, %18 = stim.measure X (%2, %4) -> i1, i1
  stim.tick
  %19, %20, %21 = stim.measure Z (%0, %3, %1) -> i1, i1, i1
  stim.correlated_error <0.1> [Z] (%0) {stim.tag = "{\22my_type\22: \22#!test.type<\5C\22test\5C\22>\22}"}
  stim.else_correlated_error <0.2222222222222222> [X] (%1) {stim.tag = "{\"my_type\": \"#!test.type<\\\"test\\\">\"}" }
  stim.pauli_channel_2 <0.001, 0.002, 0.003, 0.004, 0.005, 0.006, 0.007, 0.008, 0.009, 0.01, 0.011, 0.012, 0.013, 0.014, 0.015> (%2, %4) {stim.tag = "{\22my_type\22: \22#!test.type<\5C\22test\5C\22>\22}"}
  stim.detector <[1.0, 0.0, 0.0]> (%7, %17 : i1, i1)
  stim.detector <[3.0, 0.0, 0.0]> (%8, %18 : i1, i1)
  stim.shift_coord <[0.0, 0.0, 1.0]>
  stim.observable_include <0> (%21 : i1) {stim.tag = "{\22my_type\22: \22#!test.type<\5C\22test\5C\22>\22}"}
  stim.detector <[1.0, 0.0, 0.0]> (%17, %21, %20 : i1, i1, i1)
  stim.detector <[3.0, 0.0, 0.0]> (%18, %19, %20 : i1, i1, i1)
  stim.shift_coord <[0.0, 0.0, 1.0]>
}

// CHECK-NEXT:        %13, %14 = stim.measure X (%2, %4) -> i1, i1
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        stim.detector <[1.0, 0.0, 0.0]> (%7, %13 : i1, i1)
// CHECK-NEXT:        stim.detector <[3.0, 0.0, 0.0]> (%8, %14 : i1, i1)
// CHECK-NEXT:        %15, %16, %17 = stim.measure Z (%0, %3, %1) -> i1, i1, i1
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        stim.detector <[1.0, 0.0, 1.0]> (%13, %17, %16 : i1, i1, i1)
// CHECK-NEXT:        stim.detector <[3.0, 0.0, 1.0]> (%14, %15, %16 : i1, i1, i1)
// CHECK-NEXT:        stim.pauli_channel_2 <0.19999999999999998, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.1, 0.0, 0.0, 0.0> (%0, %1)
// CHECK-NEXT:        stim.pauli_channel_2 <0.001, 0.002, 0.003, 0.004, 0.005, 0.006, 0.007, 0.008, 0.009, 0.01, 0.011, 0.012, 0.013, 0.014, 0.015> (%2, %4)
// CHECK-NEXT:        stim.observable_include <0> (%17 : i1)
// CHECK-NEXT:      }
