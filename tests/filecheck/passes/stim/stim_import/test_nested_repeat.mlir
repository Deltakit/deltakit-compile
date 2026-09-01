// RUN: deltakit_compile compile-passes -t %s -p stim-import-pipeline --pass-args '{"verify_between_passes": true}' -O %t && filecheck %s --input-file %t

// Nested repeat test with default settings.

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

// CHECK:       builtin.module {
// CHECK-NEXT:    %0 = qcore.alloc_qubit<coords = [(4.0, 0.0)], ids = [0]> -> !qcore.qubit
// CHECK-NEXT:    %1 = qcore.alloc_qubit<coords = [(0.0, 0.0)], ids = [1]> -> !qcore.qubit
// CHECK-NEXT:    %2 = qcore.alloc_qubit<coords = [(1.0, 0.0)], ids = [2]> -> !qcore.qubit
// CHECK-NEXT:    %3 = qcore.alloc_qubit<coords = [(2.0, 0.0)], ids = [3]> -> !qcore.qubit
// CHECK-NEXT:    %4 = qcore.alloc_qubit<coords = [(3.0, 0.0)], ids = [4]> -> !qcore.qubit

  stim.reset Z (%0, %3, %1)
  stim.tick
  stim.reset X (%2, %4)
  stim.tick
  stim.clifford I (%0, %3, %1)
  stim.tick
  stim.clifford CZ (%2, %1, %4, %3)
  stim.tick
  stim.clifford CZ (%2, %3, %4, %0)
  stim.tick
  %5, %6 = stim.measure X (%2, %4) -> i1, i1
  stim.tick
  stim.detector <[1.0, 0.0, 0.0]> (%5 : i1)
  stim.detector <[3.0, 0.0, 2.0]> (%6 : i1)

// CHECK-NEXT:    %5, %6, %7, %8, %9, %10 = qstruct.circuit(%0, %1, %2, %3, %4 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qec.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%11: !qcore.qubit, %12: !qcore.qubit, %13: !qcore.qubit, %14: !qcore.qubit, %15: !qcore.qubit):
// CHECK-NEXT:      %16 = qec.dec_observable {stim.obs_id = #builtin.int<0>} -> !qec.observable
// CHECK-NEXT:      qref.reset<Z> (%11, %14, %12)
// CHECK-NEXT:      qref.reset<X> (%13, %15)
// CHECK-NEXT:      qref.gate<#qcore.gate.cz> (%13, %12, %15, %14)
// CHECK-NEXT:      qref.gate<#qcore.gate.cz> (%13, %14, %15, %11)
// CHECK-NEXT:      %17, %18 = qref.measure<X> (%13, %15) -> i1, i1
// CHECK-NEXT:      qec.measurement_round(%17, %18 : i1, i1)
// CHECK-NEXT:      %19 = qec.detector<[1.0, 0.0]> (%17)
// CHECK-NEXT:      %20 = qec.detector<[3.0, 0.0]> (%18)
// CHECK-NEXT:      %21 = qec.detector()
// CHECK-NEXT:      %22 = qec.detector()

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
    %11, %12 = stim.measure X (%2, %4) -> i1, i1
    stim.detector <[1.0, 0.0, 0.0]> (%9, %11 : i1, i1)
    stim.detector <[3.0, 0.0, 0.0]> (%10, %12 : i1, i1)
    stim.detector <[3.0, 0.0, 2.0]> (%10, %12 : i1, i1)
    stim.detector <[3.0, 0.0, 3.0]> (%11, %12 : i1, i1)
    stim.shift_coord <[0.0, 0.0, 2.0]>

// CHECK-NEXT:      %23, %24, %25, %26, %27, %28, %29 = qstruct.repeat<6> (%16, %22, %19, %21, %20, %17, %18 : !qec.observable, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, i1, i1) -> !qec.observable, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, i1, i1 {
// CHECK-NEXT:      ^bb1(%30: !qec.observable, %31: !qec.detector_ref, %32: !qec.detector_ref, %33: !qec.detector_ref, %34: !qec.detector_ref, %35: i1, %36: i1):
// CHECK-NEXT:        qref.reset<X> (%13, %15)
// CHECK-NEXT:        qref.gate<#qcore.gate.cz> (%13, %12, %15, %14)
// CHECK-NEXT:        qref.gate<#qcore.gate.cz> (%13, %14, %15, %11)
// CHECK-NEXT:        %37, %38 = qref.measure<X> (%13, %15) -> i1, i1
// CHECK-NEXT:        qec.measurement_round(%37, %38 : i1, i1)
// CHECK-NEXT:        %39 = qec.detector<[1.0, 0.0]> (%35, %37)
// CHECK-NEXT:        %40 = qec.detector<[3.0, 0.0]> (%36, %38)
// CHECK-NEXT:        qec.detector_round(%31, %32, %39, %40)
// CHECK-NEXT:        qec.detector_round(%33)
// CHECK-NEXT:        %41 = qec.detector<[3.0, 0.0]> (%36, %38)
// CHECK-NEXT:        %42 = qec.detector<[3.0, 0.0]> (%37, %38)
// CHECK-NEXT:        %43 = qec.detector()
// CHECK-NEXT:        %44 = qec.detector()

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
      %21, %22 = stim.measure X (%2, %4) -> i1, i1
      stim.detector <[1.0, 0.0, 0.0]> (%19, %21 : i1, i1)
      stim.detector <[3.0, 0.0, 0.0]> (%20, %22 : i1, i1)
      stim.detector <[3.0, 0.0, 2.0]> (%20, %22 : i1, i1)
      stim.detector <[3.0, 0.0, 3.0]> (%21, %22 : i1, i1)
      stim.shift_coord <[0.0, 0.0, 1.0]>
      stim.observable_include <0> (%22 : i1)
      stim.yield %19, %20, %21, %22 : i1, i1, i1, i1
    }

// CHECK-NEXT:        %45, %46, %47, %48, %49, %50, %51, %52, %53, %54 = qstruct.repeat<4> (%30, %41, %34, %44, %42, %43, %35, %36, %37, %38 : !qec.observable, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, i1, i1, i1, i1) -> !qec.observable, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, i1, i1, i1, i1 {
// CHECK-NEXT:        ^bb2(%55: !qec.observable, %56: !qec.detector_ref, %57: !qec.detector_ref, %58: !qec.detector_ref, %59: !qec.detector_ref, %60: !qec.detector_ref, %61: i1, %62: i1, %63: i1, %64: i1):
// CHECK-NEXT:          qref.reset<X> (%13, %15)
// CHECK-NEXT:          qref.gate<#qcore.gate.cz> (%13, %12, %15, %14)
// CHECK-NEXT:          qref.gate<#qcore.gate.cz> (%13, %14, %15, %11)
// CHECK-NEXT:          %65, %66 = qref.measure<X> (%13, %15) -> i1, i1
// CHECK-NEXT:          qec.measurement_round(%65, %66 : i1, i1)
// CHECK-NEXT:          %67 = qec.detector<[1.0, 0.0]> (%63, %65)
// CHECK-NEXT:          %68 = qec.detector<[3.0, 0.0]> (%64, %66)
// CHECK-NEXT:          qec.detector_round(%56, %57, %67, %68)
// CHECK-NEXT:          %69 = qec.detector<[3.0, 0.0]> (%64, %66)
// CHECK-NEXT:          %70 = qec.detector<[3.0, 0.0]> (%65, %66)
// CHECK-NEXT:          %71 = qec.observable_include(%55) using (%66) -> !qec.observable
// CHECK-NEXT:          qstruct.yield %71, %58, %59, %60, %69, %70, %63, %64, %65, %66 : !qec.observable, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, i1, i1, i1, i1
// CHECK-NEXT:        }

    stim.detector <[1.0, 0.0, 0.0]> (%13, %15 : i1, i1)
    stim.detector <[3.0, 0.0, 0.0]> (%14, %16 : i1, i1)
    stim.detector <[3.0, 0.0, 2.0]> (%14, %16 : i1, i1)
    stim.detector <[3.0, 0.0, 3.0]> (%15, %16 : i1, i1)
    stim.shift_coord <[0.0, 0.0, 2.0]>
    stim.yield %15, %16 : i1, i1
  }

// CHECK-NEXT:        %72 = qec.detector<[1.0, 0.0]> (%51, %53)
// CHECK-NEXT:        %73 = qec.detector<[3.0, 0.0]> (%52, %54)
// CHECK-NEXT:        qec.detector_round(%46, %47, %72, %73)
// CHECK-NEXT:        qec.detector_round(%48, %49)
// CHECK-NEXT:        %74 = qec.detector<[3.0, 0.0]> (%52, %54)
// CHECK-NEXT:        %75 = qec.detector<[3.0, 0.0]> (%53, %54)
// CHECK-NEXT:        %76 = qec.detector()
// CHECK-NEXT:        qstruct.yield %45, %50, %74, %75, %76, %53, %54 : !qec.observable, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, i1, i1
// CHECK-NEXT:      }

  stim.reset X (%2, %4)
  stim.tick
  stim.clifford I (%0, %3, %1)
  stim.tick
  stim.clifford CZ (%2, %1, %4, %3)
  stim.tick
  stim.clifford CZ (%2, %3, %4, %0)
  stim.tick
  %23, %24 = stim.measure X (%2, %4) -> i1, i1
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

// CHECK-NEXT:      qref.reset<X> (%13, %15)
// CHECK-NEXT:      qref.gate<#qcore.gate.cz> (%13, %12, %15, %14)
// CHECK-NEXT:      qref.gate<#qcore.gate.cz> (%13, %14, %15, %11)
// CHECK-NEXT:      %77, %78 = qref.measure<X> (%13, %15) -> i1, i1
// CHECK-NEXT:      qec.measurement_round(%77, %78 : i1, i1)
// CHECK-NEXT:      %79 = qec.detector<[1.0, 0.0]> (%28, %77)
// CHECK-NEXT:      %80 = qec.detector<[3.0, 0.0]> (%29, %78)
// CHECK-NEXT:      qec.detector_round(%24, %25, %79, %80)
// CHECK-NEXT:      %81, %82, %83 = qref.measure<Z> (%11, %14, %12) -> i1, i1, i1
// CHECK-NEXT:      qec.measurement_round(%81, %82, %83 : i1, i1, i1)
// CHECK-NEXT:      %84 = qec.detector<[1.0, 0.0]> (%77, %83, %82)
// CHECK-NEXT:      %85 = qec.detector<[3.0, 0.0]> (%78, %81, %82)
// CHECK-NEXT:      qec.detector_round(%26, %84, %85)
// CHECK-NEXT:      %86 = qec.observable_include(%23) using (%83) -> !qec.observable
// CHECK-NEXT:      qstruct.yield %86, %11, %12, %13, %14, %15 : !qec.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:    %11 = qec.get_corrected(%5 : !qec.observable) -> i1
// CHECK-NEXT:    qstruct.output(%11 : i1)
// CHECK-NEXT:  }
