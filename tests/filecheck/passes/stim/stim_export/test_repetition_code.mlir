// RUN: deltakit_compile compile-passes %s -p stim-export-pipeline --pass-args '{"verify_between_passes": true}' -O %t && filecheck %s --input-file %t

// d=3 repetition code memory experiment run for 10 rounds
builtin.module {
  %0 = qcore.alloc_qubit<coords=[(4.0, 0.0)], ids=[0]> -> !qcore.qubit
  %1 = qcore.alloc_qubit<coords=[(0.0, 0.0)], ids=[1]> -> !qcore.qubit
  %2 = qcore.alloc_qubit<coords=[(1.0, 0.0)], ids=[2]> -> !qcore.qubit
  %3 = qcore.alloc_qubit<coords=[(2.0, 0.0)], ids=[3]> -> !qcore.qubit
  %4 = qcore.alloc_qubit<coords=[(3.0, 0.0)], ids=[4]> -> !qcore.qubit

// CHECK:         builtin.module {
// CHECK-NEXT:      %0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:      stim.assign_qubit_coord <4.0, 0.0> (%0 : !stim.qubit)
// CHECK-NEXT:      %1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:      stim.assign_qubit_coord <0.0, 0.0> (%1 : !stim.qubit)
// CHECK-NEXT:      %2 = stim.qubit_alloc 2 -> !stim.qubit
// CHECK-NEXT:      stim.assign_qubit_coord <1.0, 0.0> (%2 : !stim.qubit)
// CHECK-NEXT:      %3 = stim.qubit_alloc 3 -> !stim.qubit
// CHECK-NEXT:      stim.assign_qubit_coord <2.0, 0.0> (%3 : !stim.qubit)
// CHECK-NEXT:      %4 = stim.qubit_alloc 4 -> !stim.qubit
// CHECK-NEXT:      stim.assign_qubit_coord <3.0, 0.0> (%4 : !stim.qubit)

  %5, %6, %7, %8, %9, %obs = qstruct.circuit(%0, %1, %2, %3, %4 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qec.observable {
  ^bb0(%10: !qcore.qubit, %11: !qcore.qubit, %12: !qcore.qubit, %13: !qcore.qubit, %14: !qcore.qubit):
    %obs1 = qec.dec_observable -> !qec.observable
    qstruct.parallel<TOP> -> {
      qref.reset<Z> (%10, %11, %13)
      qstruct.yield
    } {
      qref.reset<X> (%12, %14)
      qstruct.yield
    }
    qref.gate<#qcore.gate.cz> (%12, %11, %14, %13)
    qref.gate<#qcore.gate.cz> (%12, %13, %14, %10)
    %15, %16 = qref.measure<X> (%12, %14) -> i1, i1
    qec.measurement_round(%15, %16 : i1, i1)

// CHECK-NEXT:      stim.reset Z (%0, %1, %3)
// CHECK-NEXT:      stim.reset X (%2, %4)
// CHECK-NEXT:      stim.tick
// CHECK-NEXT:      stim.clifford CZ (%2, %1, %4, %3)
// CHECK-NEXT:      stim.tick
// CHECK-NEXT:      stim.clifford CZ (%2, %3, %4, %0)
// CHECK-NEXT:      stim.tick
// CHECK-NEXT:      %5, %6 = stim.measure X (%2, %4) -> i1, i1
// CHECK-NEXT:      stim.tick

    %17 = qec.detector<[3.0, 0.0]> (%16)
    %18 = qec.detector<[1.0, 0.0]> (%15)
    qec.detector_round(%18, %17)

// CHECK-NEXT:      stim.detector <[3.0, 0.0, 0.0]> (%6 : i1)
// CHECK-NEXT:      stim.detector <[1.0, 0.0, 0.0]> (%5 : i1)

    %19, %20 = qstruct.repeat<8> (%15, %16 : i1, i1) -> i1, i1 {
    ^bb1(%21: i1, %22: i1):
      qref.reset<X> (%12, %14) // good
      qref.gate<#qcore.gate.cz> (%12, %11, %14, %13)
      qref.gate<#qcore.gate.cz> (%12, %13, %14, %10)
      %23, %24 = qref.measure<X> (%12, %14) -> i1, i1
      qec.measurement_round(%23, %24 : i1, i1)
      %25 = qec.detector<[3.0, 0.0]> (%22, %24)
      %26 = qec.detector<[1.0, 0.0]> (%21, %23)
      qec.detector_round(%26, %25)
      qstruct.yield %23, %24 : i1, i1
    }

// CHECK-NEXT:      %7, %8 = stim.repeat 8 (%5, %6 : i1, i1) -> i1, i1 {
// CHECK-NEXT:      ^bb0(%9: i1, %10: i1):
// CHECK-NEXT:        stim.reset X (%2, %4)
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        stim.clifford CZ (%2, %1, %4, %3)
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        stim.clifford CZ (%2, %3, %4, %0)
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        %11, %12 = stim.measure X (%2, %4) -> i1, i1
// CHECK-NEXT:        stim.tick
// CHECK-NEXT:        stim.detector <[3.0, 0.0, 1.0]> (%10, %12 : i1, i1)
// CHECK-NEXT:        stim.detector <[1.0, 0.0, 1.0]> (%9, %11 : i1, i1)
// CHECK-NEXT:        stim.shift_coord <[0.0, 0.0, 1.0]>
// CHECK-NEXT:        stim.yield %11, %12 : i1, i1
// CHECK-NEXT:      }

    qref.reset<X> (%12, %14)
    qref.gate<#qcore.gate.cz> (%12, %11, %14, %13)
    qref.gate<#qcore.gate.cz> (%12, %13, %14, %10)
    %27, %28, %29, %30, %31 = qstruct.parallel<TOP> -> i1, i1, i1, i1, i1 {
      %32, %33 = qref.measure<X> (%12, %14) -> i1, i1
      qstruct.yield %32, %33 : i1, i1
    } {
      %34, %35, %36 = qref.measure<Z> (%10, %13, %11) -> i1, i1, i1
      qstruct.yield %34, %35, %36 : i1, i1, i1
    }
    qec.measurement_round(%27, %28, %29, %30, %31 : i1, i1, i1, i1, i1)

// CHECK-NEXT:      stim.reset X (%2, %4)
// CHECK-NEXT:      stim.tick
// CHECK-NEXT:      stim.clifford CZ (%2, %1, %4, %3)
// CHECK-NEXT:      stim.tick
// CHECK-NEXT:      stim.clifford CZ (%2, %3, %4, %0)
// CHECK-NEXT:      stim.tick
// CHECK-NEXT:      %13, %14 = stim.measure X (%2, %4) -> i1, i1
// CHECK-NEXT:      %15, %16, %17 = stim.measure Z (%0, %3, %1) -> i1, i1, i1
// CHECK-NEXT:      stim.tick

    %37 = qec.detector<[3.0, 0.0]> (%28, %29, %30)
    %38 = qec.detector<[1.0, 0.0]> (%27, %31, %30)
    %39 = qec.detector<[3.0, 0.0]> (%20, %28)
    %40 = qec.detector<[1.0, 0.0]> (%19, %27)
    qec.detector_round(%40, %39)
    qec.detector_round(%38, %37)
    %obs1_1 = qec.observable_include(%obs1) using (%31) -> !qec.observable
    qstruct.yield %10, %11, %12, %13, %14, %obs1_1 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qec.observable
  }
  %o0 = qec.get_corrected(%obs : !qec.observable) {stim.obs_id = #builtin.int<0>} -> i1
  qstruct.output(%o0 : i1)
}

// CHECK-NEXT:      stim.detector <[3.0, 0.0, 1.0]> (%14, %15, %16 : i1, i1, i1)
// CHECK-NEXT:      stim.detector <[1.0, 0.0, 1.0]> (%13, %17, %16 : i1, i1, i1)
// CHECK-NEXT:      stim.detector <[3.0, 0.0, 1.0]> (%8, %14 : i1, i1)
// CHECK-NEXT:      stim.detector <[1.0, 0.0, 1.0]> (%7, %13 : i1, i1)
// CHECK-NEXT:      stim.observable_include <0> (%17 : i1)
// CHECK-NEXT:    }

// ----
// CHECK: ----

// d = 5 stability experiment for 10 rounds

builtin.module {
  %0 = qcore.alloc_qubit<coords=[(4.0, 0.0)], ids=[0]> -> !qcore.qubit
  %1 = qcore.alloc_qubit<coords=[(16.0, 0.0)], ids=[1]> -> !qcore.qubit
  %2 = qcore.alloc_qubit<coords=[(17.0, 0.0)], ids=[2]> -> !qcore.qubit
  %3 = qcore.alloc_qubit<coords=[(7.0, 0.0)], ids=[3]> -> !qcore.qubit
  %4 = qcore.alloc_qubit<coords=[(8.0, 0.0)], ids=[4]> -> !qcore.qubit
  %5 = qcore.alloc_qubit<coords=[(10.0, 0.0)], ids=[5]> -> !qcore.qubit
  %6 = qcore.alloc_qubit<coords=[(1.0, 0.0)], ids=[6]> -> !qcore.qubit
  %7 = qcore.alloc_qubit<coords=[(9.0, 0.0)], ids=[7]> -> !qcore.qubit
  %8 = qcore.alloc_qubit<coords=[(11.0, 0.0)], ids=[8]> -> !qcore.qubit
  %9 = qcore.alloc_qubit<coords=[(0.0, 0.0)], ids=[9]> -> !qcore.qubit
  %10 = qcore.alloc_qubit<coords=[(12.0, 0.0)], ids=[10]> -> !qcore.qubit
  %11 = qcore.alloc_qubit<coords=[(2.0, 0.0)], ids=[11]> -> !qcore.qubit
  %12 = qcore.alloc_qubit<coords=[(13.0, 0.0)], ids=[12]> -> !qcore.qubit
  %13 = qcore.alloc_qubit<coords=[(14.0, 0.0)], ids=[13]> -> !qcore.qubit
  %14 = qcore.alloc_qubit<coords=[(3.0, 0.0)], ids=[14]> -> !qcore.qubit
  %15 = qcore.alloc_qubit<coords=[(15.0, 0.0)], ids=[15]> -> !qcore.qubit
  %16 = qcore.alloc_qubit<coords=[(5.0, 0.0)], ids=[16]> -> !qcore.qubit
  %17 = qcore.alloc_qubit<coords=[(6.0, 0.0)], ids=[17]> -> !qcore.qubit

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:    stim.assign_qubit_coord <4.0, 0.0> (%0 : !stim.qubit)
// CHECK-NEXT:    %1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:    stim.assign_qubit_coord <16.0, 0.0> (%1 : !stim.qubit)
// CHECK-NEXT:    %2 = stim.qubit_alloc 2 -> !stim.qubit
// CHECK-NEXT:    stim.assign_qubit_coord <17.0, 0.0> (%2 : !stim.qubit)
// CHECK-NEXT:    %3 = stim.qubit_alloc 3 -> !stim.qubit
// CHECK-NEXT:    stim.assign_qubit_coord <7.0, 0.0> (%3 : !stim.qubit)
// CHECK-NEXT:    %4 = stim.qubit_alloc 4 -> !stim.qubit
// CHECK-NEXT:    stim.assign_qubit_coord <8.0, 0.0> (%4 : !stim.qubit)
// CHECK-NEXT:    %5 = stim.qubit_alloc 5 -> !stim.qubit
// CHECK-NEXT:    stim.assign_qubit_coord <10.0, 0.0> (%5 : !stim.qubit)
// CHECK-NEXT:    %6 = stim.qubit_alloc 6 -> !stim.qubit
// CHECK-NEXT:    stim.assign_qubit_coord <1.0, 0.0> (%6 : !stim.qubit)
// CHECK-NEXT:    %7 = stim.qubit_alloc 7 -> !stim.qubit
// CHECK-NEXT:    stim.assign_qubit_coord <9.0, 0.0> (%7 : !stim.qubit)
// CHECK-NEXT:    %8 = stim.qubit_alloc 8 -> !stim.qubit
// CHECK-NEXT:    stim.assign_qubit_coord <11.0, 0.0> (%8 : !stim.qubit)
// CHECK-NEXT:    %9 = stim.qubit_alloc 9 -> !stim.qubit
// CHECK-NEXT:    stim.assign_qubit_coord <0.0, 0.0> (%9 : !stim.qubit)
// CHECK-NEXT:    %10 = stim.qubit_alloc 10 -> !stim.qubit
// CHECK-NEXT:    stim.assign_qubit_coord <12.0, 0.0> (%10 : !stim.qubit)
// CHECK-NEXT:    %11 = stim.qubit_alloc 11 -> !stim.qubit
// CHECK-NEXT:    stim.assign_qubit_coord <2.0, 0.0> (%11 : !stim.qubit)
// CHECK-NEXT:    %12 = stim.qubit_alloc 12 -> !stim.qubit
// CHECK-NEXT:    stim.assign_qubit_coord <13.0, 0.0> (%12 : !stim.qubit)
// CHECK-NEXT:    %13 = stim.qubit_alloc 13 -> !stim.qubit
// CHECK-NEXT:    stim.assign_qubit_coord <14.0, 0.0> (%13 : !stim.qubit)
// CHECK-NEXT:    %14 = stim.qubit_alloc 14 -> !stim.qubit
// CHECK-NEXT:    stim.assign_qubit_coord <3.0, 0.0> (%14 : !stim.qubit)
// CHECK-NEXT:    %15 = stim.qubit_alloc 15 -> !stim.qubit
// CHECK-NEXT:    stim.assign_qubit_coord <15.0, 0.0> (%15 : !stim.qubit)
// CHECK-NEXT:    %16 = stim.qubit_alloc 16 -> !stim.qubit
// CHECK-NEXT:    stim.assign_qubit_coord <5.0, 0.0> (%16 : !stim.qubit)
// CHECK-NEXT:    %17 = stim.qubit_alloc 17 -> !stim.qubit
// CHECK-NEXT:    stim.assign_qubit_coord <6.0, 0.0> (%17 : !stim.qubit)

  %18, %19, %20, %21, %22, %23, %24, %25, %26, %27, %28, %29, %30, %31, %32, %33, %34, %35 = qstruct.circuit(%0, %1, %2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14, %15, %16, %17 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%36: !qcore.qubit, %37: !qcore.qubit, %38: !qcore.qubit, %39: !qcore.qubit, %40: !qcore.qubit, %41: !qcore.qubit, %42: !qcore.qubit, %43: !qcore.qubit, %44: !qcore.qubit, %45: !qcore.qubit, %46: !qcore.qubit, %47: !qcore.qubit, %48: !qcore.qubit, %49: !qcore.qubit, %50: !qcore.qubit, %51: !qcore.qubit, %52: !qcore.qubit, %53: !qcore.qubit):
    qref.reset<X> (%43, %36, %37, %45, %44, %38, %46, %39, %47, %48, %40, %49, %50, %51, %41, %52, %53, %42)
    qref.gate<#qcore.gate.cz> (%38, %45, %42, %47, %50, %36, %52, %53, %39, %40, %43, %41, %44, %46, %48, %49, %51, %37)
    qref.gate<#qcore.gate.cz> (%38, %37, %42, %45, %50, %47, %52, %36, %39, %53, %43, %40, %44, %41, %48, %46, %51, %49)
    %54, %55, %56, %57, %58, %59, %60, %61, %62 = qref.measure<X> (%38, %42, %50, %52, %39, %43, %44, %48, %51) -> i1, i1, i1, i1, i1, i1, i1, i1, i1
    qec.measurement_round(%54, %55, %56, %57, %58, %59, %60, %61, %62 : i1, i1, i1, i1, i1, i1, i1, i1, i1)
    stim.observable_include <0> (%62, %54, %55, %56, %57, %58, %59, %60, %61 : i1, i1, i1, i1, i1, i1, i1, i1, i1)

// CHECK-NEXT:    stim.reset X (%7, %0, %1, %9, %8, %2, %10, %3, %11, %12, %4, %13, %14, %15, %5, %16, %17, %6)
// CHECK-NEXT:    stim.tick
// CHECK-NEXT:    stim.clifford CZ (%2, %9, %6, %11, %14, %0, %16, %17, %3, %4, %7, %5, %8, %10, %12, %13, %15, %1)
// CHECK-NEXT:    stim.tick
// CHECK-NEXT:    stim.clifford CZ (%2, %1, %6, %9, %14, %11, %16, %0, %3, %17, %7, %4, %8, %5, %12, %10, %15, %13)
// CHECK-NEXT:    stim.tick
// CHECK-NEXT:    %18, %19, %20, %21, %22, %23, %24, %25, %26 = stim.measure X (%2, %6, %14, %16, %3, %7, %8, %12, %15) -> i1, i1, i1, i1, i1, i1, i1, i1, i1
// CHECK-NEXT:    stim.tick
// CHECK-NEXT:    stim.observable_include <0> (%26, %18, %19, %20, %21, %22, %23, %24, %25 : i1, i1, i1, i1, i1, i1, i1, i1, i1)

    %63, %64, %65, %66, %67, %68, %69, %70, %71 = qstruct.repeat<8> (%54, %55, %56, %57, %58, %59, %60, %61, %62 : i1, i1, i1, i1, i1, i1, i1, i1, i1) -> i1, i1, i1, i1, i1, i1, i1, i1, i1 {
    ^bb1(%72: i1, %73: i1, %74: i1, %75: i1, %76: i1, %77: i1, %78: i1, %79: i1, %80: i1):
      qref.reset<X> (%43, %44, %38, %39, %48, %50, %51, %52, %42)
      qref.gate<#qcore.gate.cz> (%38, %45, %42, %47, %50, %36, %52, %53, %39, %40, %43, %41, %44, %46, %48, %49, %51, %37)
      qref.gate<#qcore.gate.cz> (%38, %37, %42, %45, %50, %47, %52, %36, %39, %53, %43, %40, %44, %41, %48, %46, %51, %49)
      %81, %82, %83, %84, %85, %86, %87, %88, %89 = qref.measure<X> (%38, %42, %50, %52, %39, %43, %44, %48, %51) -> i1, i1, i1, i1, i1, i1, i1, i1, i1
      qec.measurement_round(%81, %82, %83, %84, %85, %86, %87, %88, %89 : i1, i1, i1, i1, i1, i1, i1, i1, i1)
      %90 = qec.detector<[15.0, 0.0]> (%89, %80)
      %91 = qec.detector<[13.0, 0.0]> (%79, %88)
      %92 = qec.detector<[11.0, 0.0]> (%78, %87)
      %93 = qec.detector<[9.0, 0.0]> (%77, %86)
      %94 = qec.detector<[7.0, 0.0]> (%76, %85)
      %95 = qec.detector<[5.0, 0.0]> (%75, %84)
      %96 = qec.detector<[3.0, 0.0]> (%74, %83)
      %97 = qec.detector<[1.0, 0.0]> (%82, %73)
      %98 = qec.detector<[17.0, 0.0]> (%72, %81)
      qec.detector_round(%98, %97, %96, %95, %94, %93, %92, %91, %90)
      qstruct.yield %81, %82, %83, %84, %85, %86, %87, %88, %89 : i1, i1, i1, i1, i1, i1, i1, i1, i1
    }

// CHECK-NEXT:    %27, %28, %29, %30, %31, %32, %33, %34, %35 = stim.repeat 8 (%18, %19, %20, %21, %22, %23, %24, %25, %26 : i1, i1, i1, i1, i1, i1, i1, i1, i1) -> i1, i1, i1, i1, i1, i1, i1, i1, i1 {
// CHECK-NEXT:    ^bb0(%36: i1, %37: i1, %38: i1, %39: i1, %40: i1, %41: i1, %42: i1, %43: i1, %44: i1):
// CHECK-NEXT:      stim.reset X (%7, %8, %2, %3, %12, %14, %15, %16, %6)
// CHECK-NEXT:      stim.tick
// CHECK-NEXT:      stim.clifford CZ (%2, %9, %6, %11, %14, %0, %16, %17, %3, %4, %7, %5, %8, %10, %12, %13, %15, %1)
// CHECK-NEXT:      stim.tick
// CHECK-NEXT:      stim.clifford CZ (%2, %1, %6, %9, %14, %11, %16, %0, %3, %17, %7, %4, %8, %5, %12, %10, %15, %13)
// CHECK-NEXT:      stim.tick
// CHECK-NEXT:      %45, %46, %47, %48, %49, %50, %51, %52, %53 = stim.measure X (%2, %6, %14, %16, %3, %7, %8, %12, %15) -> i1, i1, i1, i1, i1, i1, i1, i1, i1
// CHECK-NEXT:      stim.tick
// CHECK-NEXT:      stim.detector <[15.0, 0.0, 0.0]> (%53, %44 : i1, i1)
// CHECK-NEXT:      stim.detector <[13.0, 0.0, 0.0]> (%43, %52 : i1, i1)
// CHECK-NEXT:      stim.detector <[11.0, 0.0, 0.0]> (%42, %51 : i1, i1)
// CHECK-NEXT:      stim.detector <[9.0, 0.0, 0.0]> (%41, %50 : i1, i1)
// CHECK-NEXT:      stim.detector <[7.0, 0.0, 0.0]> (%40, %49 : i1, i1)
// CHECK-NEXT:      stim.detector <[5.0, 0.0, 0.0]> (%39, %48 : i1, i1)
// CHECK-NEXT:      stim.detector <[3.0, 0.0, 0.0]> (%38, %47 : i1, i1)
// CHECK-NEXT:      stim.detector <[1.0, 0.0, 0.0]> (%46, %37 : i1, i1)
// CHECK-NEXT:      stim.detector <[17.0, 0.0, 0.0]> (%36, %45 : i1, i1)
// CHECK-NEXT:      stim.shift_coord <[0.0, 0.0, 1.0]>
// CHECK-NEXT:      stim.yield %45, %46, %47, %48, %49, %50, %51, %52, %53 : i1, i1, i1, i1, i1, i1, i1, i1, i1
// CHECK-NEXT:    }

    qref.reset<X> (%43, %44, %38, %39, %48, %50, %51, %52, %42)
    qref.gate<#qcore.gate.cz> (%38, %45, %42, %47, %50, %36, %52, %53, %39, %40, %43, %41, %44, %46, %48, %49, %51, %37)
    qref.gate<#qcore.gate.cz> (%38, %37, %42, %45, %50, %47, %52, %36, %39, %53, %43, %40, %44, %41, %48, %46, %51, %49)
    %99, %100, %101, %102, %103, %104, %105, %106, %107, %108, %109, %110, %111, %112, %113, %114, %115, %116 = qref.measure<X> (%38, %42, %50, %52, %39, %43, %44, %48, %51, %36, %37, %45, %46, %47, %40, %49, %41, %53) -> i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1
    qec.measurement_round(%99, %100, %101, %102, %103, %104, %105, %106, %107, %108, %109, %110, %111, %112, %113, %114, %115, %116 : i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1)

// CHECK-NEXT:    stim.reset X (%7, %8, %2, %3, %12, %14, %15, %16, %6)
// CHECK-NEXT:    stim.tick
// CHECK-NEXT:    stim.clifford CZ (%2, %9, %6, %11, %14, %0, %16, %17, %3, %4, %7, %5, %8, %10, %12, %13, %15, %1)
// CHECK-NEXT:    stim.tick
// CHECK-NEXT:    stim.clifford CZ (%2, %1, %6, %9, %14, %11, %16, %0, %3, %17, %7, %4, %8, %5, %12, %10, %15, %13)
// CHECK-NEXT:    stim.tick
// CHECK-NEXT:    %54, %55, %56, %57, %58, %59, %60, %61, %62, %63, %64, %65, %66, %67, %68, %69, %70, %71 = stim.measure X (%2, %6, %14, %16, %3, %7, %8, %12, %15, %0, %1, %9, %10, %11, %4, %13, %5, %17) -> i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1
// CHECK-NEXT:    stim.tick

    %117 = qec.detector<[15.0, 0.0]> (%71, %107)
    %118 = qec.detector<[13.0, 0.0]> (%70, %106)
    %119 = qec.detector<[11.0, 0.0]> (%69, %105)
    %120 = qec.detector<[9.0, 0.0]> (%68, %104)
    %121 = qec.detector<[7.0, 0.0]> (%67, %103)
    %122 = qec.detector<[5.0, 0.0]> (%66, %102)
    %123 = qec.detector<[3.0, 0.0]> (%101, %65)
    %124 = qec.detector<[1.0, 0.0]> (%64, %100)
    %125 = qec.detector<[17.0, 0.0]> (%63, %99)
    qec.detector_round(%125, %124, %123, %122, %121, %120, %119, %118, %117)
    qstruct.yield %36, %37, %38, %39, %40, %41, %42, %43, %44, %45, %46, %47, %48, %49, %50, %51, %52, %53 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

// CHECK-NEXT:    stim.detector <[15.0, 0.0, 0.0]> (%35, %62 : i1, i1)
// CHECK-NEXT:    stim.detector <[13.0, 0.0, 0.0]> (%34, %61 : i1, i1)
// CHECK-NEXT:    stim.detector <[11.0, 0.0, 0.0]> (%33, %60 : i1, i1)
// CHECK-NEXT:    stim.detector <[9.0, 0.0, 0.0]> (%32, %59 : i1, i1)
// CHECK-NEXT:    stim.detector <[7.0, 0.0, 0.0]> (%31, %58 : i1, i1)
// CHECK-NEXT:    stim.detector <[5.0, 0.0, 0.0]> (%30, %57 : i1, i1)
// CHECK-NEXT:    stim.detector <[3.0, 0.0, 0.0]> (%56, %29 : i1, i1)
// CHECK-NEXT:    stim.detector <[1.0, 0.0, 0.0]> (%28, %55 : i1, i1)
// CHECK-NEXT:    stim.detector <[17.0, 0.0, 0.0]> (%27, %54 : i1, i1)
// CHECK-NEXT:  }

// ----
// CHECK: ----
// d=2 repetition code memory experiment run for 3 cycles

builtin.module {
    // Allocate data qubits in reversed coordinate order, ancilla separately
    %reg_d_rev = qcore.alloc_qubit<coords=[(2.0, 0.0), (1.0, 0.0)]> -> !qcore.qubit_reg<2>
    %qa_lone = qcore.alloc_qubit<> -> !qcore.qubit

    // Unpack reversed register: %qd2_at_2_0 at (2,0), %qd1_at_1_0 at (1,0)
    %qd2_at_2_0, %qd1_at_1_0 = qcore.unpack_qubit_reg(%reg_d_rev : !qcore.qubit_reg<2>)

    // Pack everything into 1-qubit registers, then concatenate in scrambled order [qd1, qd2, qa]
    %reg_ancilla_singleton  = qcore.pack_qubit_reg(%qa_lone)   -> !qcore.qubit_reg<1>
    %reg_data1_singleton    = qcore.pack_qubit_reg(%qd1_at_1_0) -> !qcore.qubit_reg<1>
    %reg_data2_singleton    = qcore.pack_qubit_reg(%qd2_at_2_0) -> !qcore.qubit_reg<1>
    %reg_scrambled = qcore.concatenate(%reg_data1_singleton, %reg_data2_singleton, %reg_ancilla_singleton : !qcore.qubit_reg<1>, !qcore.qubit_reg<1>, !qcore.qubit_reg<1>) -> !qcore.qubit_reg<3>

    // Split back into [qd1, qd2] and [qa], then re-concatenate in the correct order [qa, qd1, qd2]
    %reg_data_qd1_qd2, %reg_anc_qa = qcore.split(%reg_scrambled : !qcore.qubit_reg<3>) -> !qcore.qubit_reg<2>, !qcore.qubit_reg<1>
    %reg_qa_qd1_qd2_ordered = qcore.concatenate(%reg_anc_qa, %reg_data_qd1_qd2 : !qcore.qubit_reg<1>, !qcore.qubit_reg<2>) -> !qcore.qubit_reg<3>

    // Unpack to named individual qubits: %qa at (0,0), %qd1 at (1,0), %qd2 at (2,0)
    %qa, %qd1, %qd2 = qcore.unpack_qubit_reg(%reg_qa_qd1_qd2_ordered : !qcore.qubit_reg<3>)

// CHECK-NEXT:     builtin.module {
// CHECK-NEXT:       %reg_d_rev = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:       %reg_d_rev_1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:       stim.assign_qubit_coord <2.0, 0.0> (%reg_d_rev : !stim.qubit)
// CHECK-NEXT:       stim.assign_qubit_coord <1.0, 0.0> (%reg_d_rev_1 : !stim.qubit)
// CHECK-NEXT:       %qa_lone = stim.qubit_alloc 2 -> !stim.qubit

    // Initial reset layer, with a logical on %qd1
    %reg_qd1_qd2_after_reset, %qa_1 = qstruct.circuit(%qa, %qd1, %qd2 : !qcore.qubit, !qcore.qubit, !qcore.qubit)
        -> !qcore.qubit_reg<2>, !qcore.qubit {
    ^bb0(%qa_b: !qcore.qubit, %qd1_b: !qcore.qubit, %qd2_b: !qcore.qubit):
        // Weird: pack all 3 into a register, split into ancilla reg<1> + data reg<2>
        %reg_all_args_packed = qcore.pack_qubit_reg(%qa_b, %qd1_b, %qd2_b) -> !qcore.qubit_reg<3>
        %reg_anc_arg, %reg_data_args = qcore.split(%reg_all_args_packed : !qcore.qubit_reg<3>) -> !qcore.qubit_reg<1>, !qcore.qubit_reg<2>
        %qd1_unpacked, %qd2_unpacked = qcore.unpack_qubit_reg(%reg_data_args : !qcore.qubit_reg<2>)
        qref.reset<Z> (%qd1_unpacked, %qd2_unpacked)
        // Weird: re-pack data, unpack ancilla, repack ancilla, concat, unpack for yield
        %reg_data_repacked = qcore.pack_qubit_reg(%qd1_unpacked, %qd2_unpacked) -> !qcore.qubit_reg<2>
        %qa_unpacked = qcore.unpack_qubit_reg(%reg_anc_arg : !qcore.qubit_reg<1>)
        %reg_anc_repacked = qcore.pack_qubit_reg(%qa_unpacked) -> !qcore.qubit_reg<1>
        %reg_all_recombined = qcore.concatenate(%reg_anc_repacked, %reg_data_repacked : !qcore.qubit_reg<1>, !qcore.qubit_reg<2>) -> !qcore.qubit_reg<3>
        // Unpack the fully-recombined reg<3> so we have named values to yield from
        %qa_for_yield, %qd1_for_yield, %qd2_for_yield = qcore.unpack_qubit_reg(%reg_all_recombined : !qcore.qubit_reg<3>)
        // Yield data pair as reg<2> and ancilla as individual qubit (odd register/scalar mix)
        %reg_yield_data = qcore.pack_qubit_reg(%qd1_for_yield, %qd2_for_yield) -> !qcore.qubit_reg<2>
        qstruct.yield %reg_yield_data, %qa_for_yield : !qcore.qubit_reg<2>, !qcore.qubit
    }

// CHECK-NEXT:       stim.reset Z (%reg_d_rev_1, %reg_d_rev)
// CHECK-NEXT:       stim.tick
    // First syndrome extraction cycle: pass data reg<2> directly (no unpack before circuit)
    %qa_2, %qd1_2, %qd2_2, %m1 = qstruct.circuit(%qa_1, %reg_qd1_qd2_after_reset : !qcore.qubit, !qcore.qubit_reg<2>)
        -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1 {
    ^bb0(%qa_b: !qcore.qubit, %reg_data_b: !qcore.qubit_reg<2>):
        // Unpack the data register inside the circuit
        %qd1_b, %qd2_b = qcore.unpack_qubit_reg(%reg_data_b : !qcore.qubit_reg<2>)
        qref.reset<Z> (%qa_b)
        qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
        qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
        %m1_b = qref.measure<Z> (%qa_b) -> i1
        qstruct.yield %qa_b, %qd1_b, %qd2_b, %m1_b : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1
    }

// CHECK-NEXT:       stim.reset Z (%qa_lone)
// CHECK-NEXT:       stim.tick
// CHECK-NEXT:       stim.clifford CNOT (%reg_d_rev_1, %qa_lone)
// CHECK-NEXT:       stim.tick
// CHECK-NEXT:       stim.clifford CNOT (%reg_d_rev, %qa_lone)
// CHECK-NEXT:       stim.tick
// CHECK-NEXT:       %m1_b = stim.measure Z (%qa_lone) -> i1
// CHECK-NEXT:       stim.tick

    // Between circuits: pack qubits in wrong order [qd2, qa, qd1], split, fix, unpack
    %reg_packed_wrong_order_qd2_qa_qd1 = qcore.pack_qubit_reg(%qd2_2, %qa_2, %qd1_2) -> !qcore.qubit_reg<3>
    %reg_split_qd2, %reg_split_qa_qd1 = qcore.split(%reg_packed_wrong_order_qd2_qa_qd1 : !qcore.qubit_reg<3>) -> !qcore.qubit_reg<1>, !qcore.qubit_reg<2>
    %qd2_2_extracted = qcore.unpack_qubit_reg(%reg_split_qd2 : !qcore.qubit_reg<1>)
    %qa_2_extracted, %qd1_2_extracted = qcore.unpack_qubit_reg(%reg_split_qa_qd1 : !qcore.qubit_reg<2>)
    %reg_packed_correct_order_qa_qd1_qd2 = qcore.pack_qubit_reg(%qa_2_extracted, %qd1_2_extracted, %qd2_2_extracted) -> !qcore.qubit_reg<3>
    %qa_2_reordered, %qd1_2_reordered, %qd2_2_reordered = qcore.unpack_qubit_reg(%reg_packed_correct_order_qa_qd1_qd2 : !qcore.qubit_reg<3>)

    // Pack data qubits into a reg<2> to pass as a register arg into the second syndrome circuit
    %reg_data_into_second_syndrome = qcore.pack_qubit_reg(%qd1_2_reordered, %qd2_2_reordered) -> !qcore.qubit_reg<2>

    // Second syndrome extraction cycle: ancilla as qubit, data as reg<2>
    %qa_3, %qd1_3, %qd2_3, %m2 = qstruct.circuit(%qa_2_reordered, %reg_data_into_second_syndrome : !qcore.qubit, !qcore.qubit_reg<2>)
        -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1 {
    ^bb0(%qa_b: !qcore.qubit, %reg_data_b: !qcore.qubit_reg<2>):
        // Unpack the data register inside the circuit
        %qd1_b, %qd2_b = qcore.unpack_qubit_reg(%reg_data_b : !qcore.qubit_reg<2>)
        qref.reset<Z> (%qa_b)
        qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
        qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
        %m2_b = qref.measure<Z> (%qa_b) -> i1
        qstruct.yield %qa_b, %qd1_b, %qd2_b, %m2_b : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1
    }

// CHECK-NEXT:       stim.reset Z (%qa_lone)
// CHECK-NEXT:       stim.tick
// CHECK-NEXT:       stim.clifford CNOT (%reg_d_rev_1, %qa_lone)
// CHECK-NEXT:       stim.tick
// CHECK-NEXT:       stim.clifford CNOT (%reg_d_rev, %qa_lone)
// CHECK-NEXT:       stim.tick
// CHECK-NEXT:       %m2_b = stim.measure Z (%qa_lone) -> i1
// CHECK-NEXT:       stim.tick

    // Pack data qubits into a reg<2> to pass as a register arg into the third syndrome circuit
    %reg_data_into_third_syndrome = qcore.pack_qubit_reg(%qd1_3, %qd2_3) -> !qcore.qubit_reg<2>

    // Third syndrome yields reg<1> (ancilla) + reg<2> (data) — uses split results directly
    %reg_qa_c3, %reg_data_c3, %m3 = qstruct.circuit(%qa_3, %reg_data_into_third_syndrome : !qcore.qubit, !qcore.qubit_reg<2>)
        -> !qcore.qubit_reg<1>, !qcore.qubit_reg<2>, i1 {
    ^bb0(%qa_b: !qcore.qubit, %reg_data_b: !qcore.qubit_reg<2>):
        qref.reset<Z> (%qa_b)
        // Unpack the incoming data register before the existing pack/unpack weirdness
        %qd1_b, %qd2_b = qcore.unpack_qubit_reg(%reg_data_b : !qcore.qubit_reg<2>)
        // Weird: pack data qubits into a reg<2>, unpack back before gates
        %reg_data_qd1_qd2_packed = qcore.pack_qubit_reg(%qd1_b, %qd2_b) -> !qcore.qubit_reg<2>
        %qd1_for_gates, %qd2_for_gates = qcore.unpack_qubit_reg(%reg_data_qd1_qd2_packed : !qcore.qubit_reg<2>)
        qref.gate<#qcore.gate.cx> (%qd1_for_gates, %qa_b)
        qref.gate<#qcore.gate.cx> (%qd2_for_gates, %qa_b)
        %m3_b = qref.measure<Z> (%qa_b) -> i1
        // Weird: pack all 3 together, split into [anc, data], unpack each for yield
        %reg_all_3_packed_for_yield = qcore.pack_qubit_reg(%qa_b, %qd1_for_gates, %qd2_for_gates) -> !qcore.qubit_reg<3>
        %reg_anc_split_for_yield, %reg_data_split_for_yield = qcore.split(%reg_all_3_packed_for_yield : !qcore.qubit_reg<3>) -> !qcore.qubit_reg<1>, !qcore.qubit_reg<2>
        // Yield the split registers directly — no unpack needed here
        qstruct.yield %reg_anc_split_for_yield, %reg_data_split_for_yield, %m3_b : !qcore.qubit_reg<1>, !qcore.qubit_reg<2>, i1
    }

// CHECK-NEXT:       stim.reset Z (%qa_lone)
// CHECK-NEXT:       stim.tick
// CHECK-NEXT:       stim.clifford CNOT (%reg_d_rev_1, %qa_lone)
// CHECK-NEXT:       stim.tick
// CHECK-NEXT:       stim.clifford CNOT (%reg_d_rev, %qa_lone)
// CHECK-NEXT:       stim.tick
// CHECK-NEXT:       %m3_b = stim.measure Z (%qa_lone) -> i1
// CHECK-NEXT:       stim.tick

    // Unpack the register results of the third syndrome circuit
    %qa_4 = qcore.unpack_qubit_reg(%reg_qa_c3 : !qcore.qubit_reg<1>)
    %qd1_4, %qd2_4 = qcore.unpack_qubit_reg(%reg_data_c3 : !qcore.qubit_reg<2>)

    // Pack all qubits into reg<3> to pass into the final measurement circuit
    %reg_all_for_final = qcore.pack_qubit_reg(%qa_4, %qd1_4, %qd2_4) -> !qcore.qubit_reg<3>

    // Final measurement layer, measuring the logical on %qd1
    %qa_5, %qd1_5, %qd2_5, %m4, %m5 = qstruct.circuit(%reg_all_for_final : !qcore.qubit_reg<3>)
        -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1 {
    ^bb0(%reg_all_b: !qcore.qubit_reg<3>):
        // Unpack all qubits from the combined register inside the circuit
        %qa_b, %qd1_b, %qd2_b = qcore.unpack_qubit_reg(%reg_all_b : !qcore.qubit_reg<3>)
        %m4_b = qref.measure<Z> (%qd1_b) -> i1
        %m5_b = qref.measure<Z> (%qd2_b) -> i1
        qstruct.yield %qa_b, %qd1_b, %qd2_b, %m4_b, %m5_b : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1
    }
}

// CHECK-NEXT:       %m4_b = stim.measure Z (%reg_d_rev_1) -> i1
// CHECK-NEXT:       stim.tick
// CHECK-NEXT:       %m5_b = stim.measure Z (%reg_d_rev) -> i1
// CHECK-NEXT:       stim.tick
// CHECK-NEXT:     }
