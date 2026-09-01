// RUN: deltakit_compile compile-passes -t %s -p stim-import-pipeline --pass-args '{"verify_between_passes": true, "extract_tags_to_attributes": true, "respect_tick_parallelisation": false}' -O %t && filecheck %s --input-file %t

// Tags, noise, gates, measures and simple nested repeats.

builtin.module {
  %0 = stim.qubit_alloc 0  {stim.tag = "{\"array\": [\"#Z\", 1, \"#1\", {\"key\": null}\\C}"} -> !stim.qubit
  %1 = stim.qubit_alloc 1 -> !stim.qubit
  %2 = stim.qubit_alloc 2 -> !stim.qubit
  %3 = stim.qubit_alloc 3 -> !stim.qubit
  %4 = stim.qubit_alloc 4 -> !stim.qubit
  stim.assign_qubit_coord <4.0, 0.0> (%0 : !stim.qubit)
  stim.assign_qubit_coord <0.0, 0.0> (%1 : !stim.qubit)
  stim.assign_qubit_coord <1.0, 0.0> (%2 : !stim.qubit)
  stim.assign_qubit_coord <2.0, 0.0> (%3 : !stim.qubit)
  stim.assign_qubit_coord <3.0, 0.0> (%4 : !stim.qubit)

// CHECK:       builtin.module {
// CHECK-NEXT:    %0 = qcore.alloc_qubit<coords = [(4.0, 0.0)], ids = [0]> {array = ["#Z", #builtin.int<1>, 1 : i64, {key = none}]} -> !qcore.qubit
// CHECK-NEXT:    %1 = qcore.alloc_qubit<coords = [(0.0, 0.0)], ids = [1]> -> !qcore.qubit
// CHECK-NEXT:    %2 = qcore.alloc_qubit<coords = [(1.0, 0.0)], ids = [2]> -> !qcore.qubit
// CHECK-NEXT:    %3 = qcore.alloc_qubit<coords = [(2.0, 0.0)], ids = [3]> -> !qcore.qubit
// CHECK-NEXT:    %4 = qcore.alloc_qubit<coords = [(3.0, 0.0)], ids = [4]> -> !qcore.qubit

  stim.reset Z (%0, %3, %1)  {stim.tag = "{\22my_type\22: \22#!test.type<\5C\22test\5C\22>\22}"}
  stim.tick
  stim.reset X (%2, %4)
  stim.tick
  stim.clifford I (%0, %3, %1) {stim.tag = "{\"my_type\": \"#!test.type<\\\"test\\\">\"}"}
  stim.tick
  stim.clifford CZ (%2, %1, %4, %3)
  stim.tick
  stim.clifford CZ (%2, %3, %4, %0)
  stim.depolarize1 <0.001> (%2, %4) {stim.tag = "{\22my_type\22: \22#!test.type<\5C\22test\5C\22>\22}"}
  stim.depolarize2 <0.002> (%2, %4) {stim.tag = "{\"my_type\": \"#!test.type<\\\"test\\\">\"}" }
  stim.tick
  %5, %6 = stim.measure X (%2, %4) {stim.tag = "{\"my_type\": \"#!test.type<\\\"test\\\">\"}"} -> i1, i1
  stim.tick
  stim.detector <[1.0, 0.0, 0.0]> (%5 : i1) {stim.tag = "{\22my_type\22: \22#!test.type<\5C\22test\5C\22>\22}"}
  stim.detector <[3.0, 0.0, 2.0]> (%6 : i1)

// CHECK-NEXT:    %5, %6, %7, %8, %9, %10 = qstruct.circuit(%0, %1, %2, %3, %4 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qec.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:   ^bb0(%11: !qcore.qubit, %12: !qcore.qubit, %13: !qcore.qubit, %14: !qcore.qubit, %15: !qcore.qubit):
// CHECK-NEXT:      %16 = qec.dec_observable {stim.obs_id = #builtin.int<0>} -> !qec.observable
// CHECK-NEXT:      qstruct.parallel<TOP> -> {
// CHECK-NEXT:        qref.reset<Z> (%11, %14, %12) {my_type = !test.type<"test">}
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      } {
// CHECK-NEXT:        qref.reset<X> (%13, %15)
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      }
// CHECK-NEXT:      qref.gate<#qcore.gate.cz> (%13, %12, %15, %14)
// CHECK-NEXT:      qref.gate<#qcore.gate.cz> (%13, %14, %15, %11)
// CHECK-NEXT:      qref.pauli_noise<X = 0.0003333333333333333, Y = 0.0003333333333333333, Z = 0.0003333333333333333> (%13, %15) {my_type = !test.type<"test">}
// CHECK-NEXT:      qref.pauli_noise<IX = 0.00013333333333333334, IY = 0.00013333333333333334, IZ = 0.00013333333333333334, XI = 0.00013333333333333334, XX = 0.00013333333333333334, XY = 0.00013333333333333334, XZ = 0.00013333333333333334, YI = 0.00013333333333333334, YX = 0.00013333333333333334, YY = 0.00013333333333333334, YZ = 0.00013333333333333334, ZI = 0.00013333333333333334, ZX = 0.00013333333333333334, ZY = 0.00013333333333333334, ZZ = 0.00013333333333333334> (%13, %15) {my_type = !test.type<"test">}
// CHECK-NEXT:      %17, %18 = qref.measure<X> (%13, %15) {my_type = !test.type<"test">} -> i1, i1
// CHECK-NEXT:      qec.measurement_round(%17, %18 : i1, i1)
// CHECK-NEXT:      %19 = qec.detector<[1.0, 0.0]> (%17) {my_type = !test.type<"test">}
// CHECK-NEXT:      %20 = qec.detector<[3.0, 0.0]> (%18)

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
      stim.pauli_channel_1 <0.01, 0.02, 0.03> (%2, %4) {stim.tag = "{\22my_type\22: \22#!test.type<\5C\22test\5C\22>\22}"}
      stim.tick
      %15, %16 = stim.measure X (%2, %4) -> i1, i1
      stim.detector <[1.0, 0.0, 0.0]> (%13, %15 : i1, i1)
      stim.detector <[3.0, 0.0, 0.0]> (%14, %16 : i1, i1)
      stim.detector <[3.0, 0.0, 2.0]> (%14, %16 : i1, i1)
      stim.detector <[3.0, 0.0, 3.0]> (%15, %16 : i1, i1)
      stim.shift_coord <[0.0, 0.0, 1.0]>
      stim.yield %15, %16 : i1, i1
    }
    stim.yield %11, %12 : i1, i1
  }

// CHECK-NEXT:      %21 = qec.detector()
// CHECK-NEXT:      %22 = qec.detector()
// CHECK-NEXT:      %23 = qec.detector()
// CHECK-NEXT:      %24 = qec.detector()
// CHECK-NEXT:      %25 = qec.detector()
// CHECK-NEXT:      %26 = qec.detector()
// CHECK-NEXT:      %27, %28, %29, %30, %31, %32, %33, %34 = qstruct.repeat<2> (%19, %24, %25, %22, %23, %26, %17, %18 : !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, i1, i1) {my_type = !test.type<"test">} -> !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, i1, i1 {
// CHECK-NEXT:      ^bb1(%35: !qec.detector_ref, %36: !qec.detector_ref, %37: !qec.detector_ref, %38: !qec.detector_ref, %39: !qec.detector_ref, %40: !qec.detector_ref, %41: i1, %42: i1):
// CHECK-NEXT:        qref.reset<X> (%13, %15)
// CHECK-NEXT:        qref.gate<#qcore.gate.cz> (%13, %12, %15, %14)
// CHECK-NEXT:        qref.gate<#qcore.gate.cz> (%13, %14, %15, %11)
// CHECK-NEXT:        qref.pauli_noise<X = 0.01, Y = 0.02, Z = 0.03> (%13, %15) {my_type = !test.type<"test">}
// CHECK-NEXT:        %43, %44 = qref.measure<X> (%13, %15) -> i1, i1
// CHECK-NEXT:        qec.measurement_round(%43, %44 : i1, i1)
// CHECK-NEXT:        %45 = qec.detector<[1.0, 0.0]> (%41, %43)
// CHECK-NEXT:        %46 = qec.detector<[3.0, 0.0]> (%42, %44)
// CHECK-NEXT:        qec.detector_round(%35, %36, %37, %45, %46)
// CHECK-NEXT:        %47 = qec.detector<[3.0, 0.0]> (%42, %44)
// CHECK-NEXT:        %48 = qec.detector<[3.0, 0.0]> (%43, %44)
// CHECK-NEXT:        %49 = qec.detector()
// CHECK-NEXT:        qstruct.yield %49, %38, %39, %40, %47, %48, %43, %44 : !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, i1, i1
// CHECK-NEXT:      }

  stim.reset X (%2, %4)
  stim.tick
  stim.clifford I (%0, %3, %1)
  stim.tick
  stim.clifford CZ (%2, %1, %4, %3)
  stim.tick
  stim.clifford CZ (%2, %3, %4, %0)
  stim.tick
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

// CHECK-NEXT:      qref.reset<X> (%13, %15)
// CHECK-NEXT:      qref.gate<#qcore.gate.cz> (%13, %12, %15, %14)
// CHECK-NEXT:      qref.gate<#qcore.gate.cz> (%13, %14, %15, %11)
// CHECK-NEXT:      %50, %51 = qref.measure<X> (%13, %15) -> i1, i1
// CHECK-NEXT:      qec.measurement_round(%50, %51 : i1, i1)
// CHECK-NEXT:      %52 = qec.detector<[1.0, 0.0]> (%33, %50)
// CHECK-NEXT:      %53 = qec.detector<[3.0, 0.0]> (%34, %51)
// CHECK-NEXT:      qec.detector_round(%20, %21, %28, %29, %52, %53)
// CHECK-NEXT:      %54, %55, %56 = qref.measure<Z> (%11, %14, %12) -> i1, i1, i1
// CHECK-NEXT:      qec.measurement_round(%54, %55, %56 : i1, i1, i1)
// CHECK-NEXT:      %57 = qec.detector<[1.0, 0.0]> (%50, %56, %55)
// CHECK-NEXT:      %58 = qec.detector<[3.0, 0.0]> (%51, %54, %55)
// CHECK-NEXT:      qec.detector_round(%30, %31, %57, %58)
// CHECK-NEXT:      qec.detector_round(%32)
// CHECK-NEXT:      qstruct.parallel<TOP> -> {
// CHECK-NEXT:        qref.pauli_noise<IX = 0.19999999999999998, ZI = 0.1> (%11, %12) {my_type = !test.type<"test">}
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      } {
// CHECK-NEXT:        qref.pauli_noise<IX = 0.001, IY = 0.002, IZ = 0.003, XI = 0.004, XX = 0.005, XY = 0.006, XZ = 0.007, YI = 0.008, YX = 0.009, YY = 0.01, YZ = 0.011, ZI = 0.012, ZX = 0.013, ZY = 0.014, ZZ = 0.015> (%13, %15) {my_type = !test.type<"test">}
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      }
// CHECK-NEXT:      %59 = qec.observable_include(%16) using (%56) {my_type = !test.type<"test">} -> !qec.observable
// CHECK-NEXT:      qstruct.yield %59, %11, %12, %13, %14, %15 : !qec.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:    %11 = qec.get_corrected(%5 : !qec.observable) -> i1
// CHECK-NEXT:    qstruct.output(%11 : i1)
// CHECK-NEXT:  }
