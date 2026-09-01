// RUN: deltakit_compile compile-passes %s -p stim-export-pipeline --pass-args '{"verify_between_passes": true}' -O %t && filecheck %s --input-file %t

// non standard example
builtin.module {
  %0 = qcore.alloc_qubit<coords=[(4.0, 0.0)], ids=[1]> -> !qcore.qubit
  %1 = qcore.alloc_qubit<coords=[(0.0, 0.0)], ids=[4]> -> !qcore.qubit
  %2 = qcore.alloc_qubit<coords=[(1.0, 0.0)]> -> !qcore.qubit
  %3 = qcore.alloc_qubit<coords=[(2.0, 0.0)], ids=[2]> -> !qcore.qubit
  %4 = qcore.alloc_qubit<coords=[(3.0, 0.0)]> -> !qcore.qubit

// CHECK:         builtin.module {
// CHECK-NEXT:      %0 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:      stim.assign_qubit_coord <4.0, 0.0> (%0 : !stim.qubit)
// CHECK-NEXT:      %1 = stim.qubit_alloc 4 -> !stim.qubit
// CHECK-NEXT:      stim.assign_qubit_coord <0.0, 0.0> (%1 : !stim.qubit)
// CHECK-NEXT:      %2 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:      stim.assign_qubit_coord <1.0, 0.0> (%2 : !stim.qubit)
// CHECK-NEXT:      %3 = stim.qubit_alloc 2 -> !stim.qubit
// CHECK-NEXT:      stim.assign_qubit_coord <2.0, 0.0> (%3 : !stim.qubit)
// CHECK-NEXT:      %4 = stim.qubit_alloc 3 -> !stim.qubit
// CHECK-NEXT:      stim.assign_qubit_coord <3.0, 0.0> (%4 : !stim.qubit)

  %5, %6, %7, %8, %9, %10 = qstruct.circuit(%0, %1, %2, %3, %4 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qec.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%11: !qcore.qubit, %12: !qcore.qubit, %13: !qcore.qubit, %14: !qcore.qubit, %15: !qcore.qubit):
    %16 = qec.dec_observable {stim.obs_id = #builtin.int<0>} -> !qec.observable
    qstruct.parallel<TOP> -> {
      qref.reset<Z> (%11, %14, %12) {stim.tag = "reset_tag"}
      qstruct.yield
    } {
      qref.reset<X> (%13, %15)
      qstruct.yield
    }
    qref.pauli_noise<X=0.001, Y=0.001, Z=0.001> (%11, %12, %13, %14, %15) {stim.tag = "noise_tag"}
    qref.gate<#qcore.gate.cz> (%13, %12, %15, %14) {stim.tag = "my_tag"}
    qref.pauli_noise<IX=0.005, XI=0.005, XX=0.005> (%13, %12, %15, %14)
    qref.gate<#qcore.gate.cz> (%13, %14, %15, %11) {stim.tag = "my_other_tag"}
    qref.pauli_noise<IX=0.005, XI=0.005, XX=0.005> (%13, %14, %15, %11)
    qref.pauli_noise<IZX=0.1, XIX=0.2, YIX=0.3> (%11, %12, %14)
    %17, %18 = qref.measure<X> (%13, %15) {stim.tag = "measure_tag"} -> i1, i1
    qref.pauli_noise<X=0.002, Y=0.002, Z=0.002> (%13, %15)
    qec.measurement_round(%17, %18 : i1, i1)

// CHECK-NEXT:      stim.reset Z (%0, %3, %1) {stim.tag = "reset_tag"}
// CHECK-NEXT:      stim.reset X (%2, %4)
// CHECK-NEXT:      stim.tick
// CHECK-NEXT:      stim.depolarize1 <0.003> (%0, %1, %2, %3, %4) {stim.tag = "noise_tag"}
// CHECK-NEXT:      stim.clifford CZ (%2, %1, %4, %3) {stim.tag = "my_tag"}
// CHECK-NEXT:      stim.tick
// CHECK-NEXT:      stim.pauli_channel_2 <0.005, 0.0, 0.0, 0.005, 0.005, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0> (%2, %1, %4, %3)
// CHECK-NEXT:      stim.clifford CZ (%2, %3, %4, %0) {stim.tag = "my_other_tag"}
// CHECK-NEXT:      stim.tick
// CHECK-NEXT:      stim.pauli_channel_2 <0.005, 0.0, 0.0, 0.005, 0.005, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0> (%2, %3, %4, %0)
// CHECK-NEXT:      stim.correlated_error <0.1> [Z, X] (%1, %3)
// CHECK-NEXT:      stim.else_correlated_error <0.22222222222222224> [X, X] (%0, %3)
// CHECK-NEXT:      stim.else_correlated_error <0.4285714285714286> [Y, X] (%0, %3)
// CHECK-NEXT:      %5, %6 = stim.measure X (%2, %4) {stim.tag = "measure_tag"} -> i1, i1
// CHECK-NEXT:      stim.tick
// CHECK-NEXT:      stim.depolarize1 <0.006> (%2, %4)

    %19 = qec.detector<[1.0, 0.0]> (%17) {stim.tag = "det_tag"}
    %20 = qec.detector<[3.0, 0.0]> (%18)
    %21 = qec.detector()
    %22 = qec.detector()
    %23 = qec.detector()
    %24 = qec.detector()
    %25 = qec.detector()
    %26 = qec.detector()

// CHECK-NEXT:      stim.detector <[1.0, 0.0, 0.0]> (%5 : i1) {stim.tag = "det_tag"}
// CHECK-NEXT:      stim.detector <[3.0, 0.0, 0.0]> (%6 : i1)

    %27, %28, %29, %30, %31, %32, %33, %34 = qstruct.repeat<2> (%19, %24, %25, %22, %23, %26, %17, %18 : !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, i1, i1) {stim.tag = "repeat_tag"} -> !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, i1, i1 {
    ^bb1(%35: !qec.detector_ref, %36: !qec.detector_ref, %37: !qec.detector_ref, %38: !qec.detector_ref, %39: !qec.detector_ref, %40: !qec.detector_ref, %41: i1, %42: i1):
      qref.reset<X> (%13, %15)
      qref.gate<#qcore.gate.cz> (%13, %12, %15, %14)
      qref.gate<#qcore.gate.cz> (%13, %14, %15, %11)
      %43, %44 = qref.measure<X> (%13, %15) -> i1, i1
      qec.measurement_round(%43, %44 : i1, i1)
      %45 = qec.detector<[1.0, 0.0]> (%41, %43)
      %46 = qec.detector<[3.0, 0.0]> (%42, %44)
      qec.detector_round(%35, %36, %37, %45, %46)
      %47 = qec.detector<[3.0, 0.0]> (%42, %44)
      %48 = qec.detector<[3.0, 0.0]> (%43, %44)
      %49 = qec.detector()
      qstruct.yield %49, %38, %39, %40, %47, %48, %43, %44 : !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, i1, i1
    }

// CHECK-NEXT:      %7, %8 = stim.repeat {stim.tag = "repeat_tag"} 2 (%5, %6 : i1, i1) -> i1, i1 {
// CHECK-NEXT:      ^bb0(%9: i1, %10: i1):
// CHECK-NEXT:        stim.reset X (%2, %4)
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        stim.clifford CZ (%2, %1, %4, %3)
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        stim.clifford CZ (%2, %3, %4, %0)
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        %11, %12 = stim.measure X (%2, %4) -> i1, i1
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        stim.detector <[1.0, 0.0, 0.0]> (%9, %11 : i1, i1)
// CHECK-NEXT:        stim.detector <[3.0, 0.0, 0.0]> (%10, %12 : i1, i1)
// CHECK-NEXT:        stim.detector <[3.0, 0.0, 2.0]> (%10, %12 : i1, i1)
// CHECK-NEXT:        stim.detector <[3.0, 0.0, 3.0]> (%11, %12 : i1, i1)
// CHECK-NEXT:        stim.shift_coord <[0.0, 0.0, 1.0]>
// CHECK-NEXT:        stim.yield %11, %12 : i1, i1
// CHECK-NEXT:      }

    qref.reset<X> (%13, %15)
    qref.gate<#qcore.gate.cz> (%13, %12, %15, %14)
    qref.gate<#qcore.gate.cz> (%13, %14, %15, %11)
    %50, %51 = qref.measure<X> (%13, %15) -> i1, i1
    qec.measurement_round(%50, %51 : i1, i1)
    %52 = qec.detector<[1.0, 0.0]> (%33, %50)
    %53 = qec.detector<[3.0, 0.0]> (%34, %51)
    qec.detector_round(%20, %21, %28, %29, %52, %53)
    %54, %55, %56 = qref.measure<Z> (%11, %14, %12) -> i1, i1, i1
    qec.measurement_round(%54, %55, %56 : i1, i1, i1)
    %57 = qec.detector<[1.0, 0.0]> (%50, %56, %55)
    %58 = qec.detector<[3.0, 0.0]> (%51, %54, %55)
    qec.detector_round(%30, %31, %57, %58)
    qec.detector_round(%32)
    %59 = qec.observable_include(%16) using (%56) {stim.tag = "obs_tag"} -> !qec.observable
    qstruct.yield %59, %11, %12, %13, %14, %15 : !qec.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
  %11 = qec.get_corrected(%5 : !qec.observable) -> i1
  qstruct.output(%11 : i1)
}

// CHECK-NEXT:      stim.reset X (%2, %4)
// CHECK-NEXT:      stim.tick
// CHECK-NEXT:      stim.clifford CZ (%2, %1, %4, %3)
// CHECK-NEXT:      stim.tick
// CHECK-NEXT:      stim.clifford CZ (%2, %3, %4, %0)
// CHECK-NEXT:      stim.tick
// CHECK-NEXT:      %13, %14 = stim.measure X (%2, %4) -> i1, i1
// CHECK-NEXT:      stim.tick
// CHECK-NEXT:      stim.detector <[1.0, 0.0, 0.0]> (%7, %13 : i1, i1)
// CHECK-NEXT:      stim.detector <[3.0, 0.0, 0.0]> (%8, %14 : i1, i1)
// CHECK-NEXT:      %15, %16, %17 = stim.measure Z (%0, %3, %1) -> i1, i1, i1
// CHECK-NEXT:      stim.tick
// CHECK-NEXT:      stim.detector <[1.0, 0.0, 1.0]> (%13, %17, %16 : i1, i1, i1)
// CHECK-NEXT:      stim.detector <[3.0, 0.0, 1.0]> (%14, %15, %16 : i1, i1, i1)
// CHECK-NEXT:      stim.observable_include <0> (%17 : i1) {stim.tag = "obs_tag"}
// CHECK-NEXT:    }
