// RUN: deltakit_compile compile-passes %s -p stim-export-pipeline --pass-args '{"verify_between_passes": true}' -O %t && filecheck %s --input-file %t

// 3x3 rotated memory 10 rounds

builtin.module {

// CHECK: builtin.module {

  %0 = qcore.alloc_qubit<coords=[(2.0, 4.0)], ids=[0]> -> !qcore.qubit
  %1 = qcore.alloc_qubit<coords=[(4.0, 0.0)], ids=[1]> -> !qcore.qubit
  %2 = qcore.alloc_qubit<coords=[(1.0, 5.0)], ids=[2]> -> !qcore.qubit
  %3 = qcore.alloc_qubit<coords=[(3.0, 1.0)], ids=[3]> -> !qcore.qubit
  %4 = qcore.alloc_qubit<coords=[(5.0, 1.0)], ids=[4]> -> !qcore.qubit
  %5 = qcore.alloc_qubit<coords=[(6.0, 4.0)], ids=[5]> -> !qcore.qubit
  %6 = qcore.alloc_qubit<coords=[(0.0, 2.0)], ids=[6]> -> !qcore.qubit
  %7 = qcore.alloc_qubit<coords=[(2.0, 2.0)], ids=[7]> -> !qcore.qubit
  %8 = qcore.alloc_qubit<coords=[(1.0, 3.0)], ids=[8]> -> !qcore.qubit
  %9 = qcore.alloc_qubit<coords=[(3.0, 5.0)], ids=[9]> -> !qcore.qubit
  %10 = qcore.alloc_qubit<coords=[(4.0, 4.0)], ids=[10]> -> !qcore.qubit
  %11 = qcore.alloc_qubit<coords=[(5.0, 5.0)], ids=[11]> -> !qcore.qubit
  %12 = qcore.alloc_qubit<coords=[(1.0, 1.0)], ids=[12]> -> !qcore.qubit
  %13 = qcore.alloc_qubit<coords=[(4.0, 2.0)], ids=[13]> -> !qcore.qubit
  %14 = qcore.alloc_qubit<coords=[(3.0, 3.0)], ids=[14]> -> !qcore.qubit
  %15 = qcore.alloc_qubit<coords=[(2.0, 6.0)], ids=[15]> -> !qcore.qubit
  %16 = qcore.alloc_qubit<coords=[(5.0, 3.0)], ids=[16]> -> !qcore.qubit

  // CHECK-NEXT:   %0 = stim.qubit_alloc 0 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <2.0, 4.0> (%0 : !stim.qubit)
  // CHECK-NEXT:   %1 = stim.qubit_alloc 1 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <4.0, 0.0> (%1 : !stim.qubit)
  // CHECK-NEXT:   %2 = stim.qubit_alloc 2 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <1.0, 5.0> (%2 : !stim.qubit)
  // CHECK-NEXT:   %3 = stim.qubit_alloc 3 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <3.0, 1.0> (%3 : !stim.qubit)
  // CHECK-NEXT:   %4 = stim.qubit_alloc 4 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <5.0, 1.0> (%4 : !stim.qubit)
  // CHECK-NEXT:   %5 = stim.qubit_alloc 5 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <6.0, 4.0> (%5 : !stim.qubit)
  // CHECK-NEXT:   %6 = stim.qubit_alloc 6 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <0.0, 2.0> (%6 : !stim.qubit)
  // CHECK-NEXT:   %7 = stim.qubit_alloc 7 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <2.0, 2.0> (%7 : !stim.qubit)
  // CHECK-NEXT:   %8 = stim.qubit_alloc 8 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <1.0, 3.0> (%8 : !stim.qubit)
  // CHECK-NEXT:   %9 = stim.qubit_alloc 9 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <3.0, 5.0> (%9 : !stim.qubit)
  // CHECK-NEXT:   %10 = stim.qubit_alloc 10 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <4.0, 4.0> (%10 : !stim.qubit)
  // CHECK-NEXT:   %11 = stim.qubit_alloc 11 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <5.0, 5.0> (%11 : !stim.qubit)
  // CHECK-NEXT:   %12 = stim.qubit_alloc 12 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <1.0, 1.0> (%12 : !stim.qubit)
  // CHECK-NEXT:   %13 = stim.qubit_alloc 13 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <4.0, 2.0> (%13 : !stim.qubit)
  // CHECK-NEXT:   %14 = stim.qubit_alloc 14 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <3.0, 3.0> (%14 : !stim.qubit)
  // CHECK-NEXT:   %15 = stim.qubit_alloc 15 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <2.0, 6.0> (%15 : !stim.qubit)
  // CHECK-NEXT:   %16 = stim.qubit_alloc 16 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <5.0, 3.0> (%16 : !stim.qubit)

  %17, %18, %19, %20, %21, %22, %23, %24, %25, %26, %27, %28, %29, %30, %31, %32, %33, %34 = qstruct.circuit(%0, %1, %2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14, %15, %16 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qec.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%35: !qcore.qubit, %36: !qcore.qubit, %37: !qcore.qubit, %38: !qcore.qubit, %39: !qcore.qubit, %40: !qcore.qubit, %41: !qcore.qubit, %42: !qcore.qubit, %43: !qcore.qubit, %44: !qcore.qubit, %45: !qcore.qubit, %46: !qcore.qubit, %47: !qcore.qubit, %48: !qcore.qubit, %49: !qcore.qubit, %50: !qcore.qubit, %51: !qcore.qubit):
    %52 = qec.dec_observable -> !qec.observable
    qstruct.parallel<TOP> -> {
      qref.reset<Z> (%46, %37, %38, %47, %39, %49, %51, %43, %44)
      qstruct.yield
    } {
      qref.reset<X> (%45, %35, %36, %40, %48, %41, %50, %42)
      qstruct.yield
    }

    // CHECK-NEXT:   stim.reset Z (%11, %2, %3, %12, %4, %14, %16, %8, %9)
    // CHECK-NEXT:   stim.reset X (%10, %0, %1, %5, %13, %6, %15, %7)
    // CHECK-NEXT:   stim.tick

    qstruct.parallel<TOP> -> {
      qref.gate<#qcore.gate.cx> (%40, %46, %35, %37, %48, %49)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.cz> (%36, %38, %45, %44, %42, %43)
      qstruct.yield
    }

    // CHECK-NEXT:   stim.clifford CNOT (%5, %11, %0, %2, %13, %14)
    // CHECK-NEXT:   stim.clifford CZ (%1, %3, %10, %9, %7, %8)
    // CHECK-NEXT:   stim.tick

    qstruct.parallel<TOP> -> {
      qref.gate<#qcore.gate.cx> (%40, %51, %35, %43, %48, %38)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.cz> (%36, %39, %45, %46, %42, %49)
      qstruct.yield
    }

    // CHECK-NEXT:   stim.clifford CNOT (%5, %16, %0, %8, %13, %3)
    // CHECK-NEXT:   stim.clifford CZ (%1, %4, %10, %11, %7, %14)
    // CHECK-NEXT:   stim.tick

    qstruct.parallel<TOP> -> {
      qref.gate<#qcore.gate.cx> (%35, %44, %48, %51, %41, %43)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.cz> (%45, %49, %50, %37, %42, %47)
      qstruct.yield
    }

    // CHECK-NEXT:   stim.clifford CNOT (%0, %9, %13, %16, %6, %8)
    // CHECK-NEXT:   stim.clifford CZ (%10, %14, %15, %2, %7, %12)
    // CHECK-NEXT:   stim.tick

    qstruct.parallel<TOP> -> {
      qref.gate<#qcore.gate.cx> (%35, %49, %48, %39, %41, %47)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.cz> (%45, %51, %50, %44, %42, %38)
      qstruct.yield
    }

    // CHECK-NEXT:   stim.clifford CNOT (%0, %14, %13, %4, %6, %12)
    // CHECK-NEXT:   stim.clifford CZ (%10, %16, %15, %9, %7, %3)
    // CHECK-NEXT:   stim.tick

    %53, %54, %55, %56, %57, %58, %59, %60 = qref.measure<X> (%40, %36, %35, %48, %41, %45, %50, %42) -> i1, i1, i1, i1, i1, i1, i1, i1

    // CHECK-NEXT:   %17, %18, %19, %20, %21, %22, %23, %24 = stim.measure X (%5, %1, %0, %13, %6, %10, %15, %7) -> i1, i1, i1, i1, i1, i1, i1, i1

    qec.measurement_round(%53, %54, %55, %56, %57, %58, %59, %60 : i1, i1, i1, i1, i1, i1, i1, i1)

    // CHECK-NEXT:   stim.tick

    %61 = qec.detector<[4.0, 0.0]> (%54)
    %62 = qec.detector<[4.0, 4.0]> (%58)
    %63 = qec.detector<[2.0, 6.0]> (%59)
    %64 = qec.detector<[2.0, 2.0]> (%60)

    // CHECK-NEXT:   stim.detector <[4.0, 0.0, 0.0]> (%18 : i1)
    // CHECK-NEXT:   stim.detector <[4.0, 4.0, 0.0]> (%22 : i1)
    // CHECK-NEXT:   stim.detector <[2.0, 6.0, 0.0]> (%23 : i1)
    // CHECK-NEXT:   stim.detector <[2.0, 2.0, 0.0]> (%24 : i1)

    qec.detector_round(%61, %62, %63, %64)
    %65, %66, %67, %68, %69, %70, %71, %72 = qstruct.repeat<8> (%53, %54, %55, %56, %57, %58, %59, %60 : i1, i1, i1, i1, i1, i1, i1, i1) -> i1, i1, i1, i1, i1, i1, i1, i1 {

    // CHECK-NEXT:   %25, %26, %27, %28, %29, %30, %31, %32 = stim.repeat 8 (%17, %18, %19, %20, %21, %22, %23, %24 : i1, i1, i1, i1, i1, i1, i1, i1) -> i1, i1, i1, i1, i1, i1, i1, i1 {

    ^bb1(%73: i1, %74: i1, %75: i1, %76: i1, %77: i1, %78: i1, %79: i1, %80: i1):

    // CHECK-NEXT:   ^bb0(%33: i1, %34: i1, %35: i1, %36: i1, %37: i1, %38: i1, %39: i1, %40: i1):

      qref.reset<X> (%45, %35, %36, %40, %48, %41, %50, %42)

      // CHECK-NEXT:     stim.reset X (%10, %0, %1, %5, %13, %6, %15, %7)
      // CHECK-NEXT:     stim.tick

      qstruct.parallel<TOP> -> {
        qref.gate<#qcore.gate.cx> (%40, %46, %35, %37, %48, %49)
        qstruct.yield
      } {
        qref.gate<#qcore.gate.cz> (%36, %38, %45, %44, %42, %43)
        qstruct.yield
      }

      // CHECK-NEXT:     stim.clifford CNOT (%5, %11, %0, %2, %13, %14)
      // CHECK-NEXT:     stim.clifford CZ (%1, %3, %10, %9, %7, %8)
      // CHECK-NEXT:     stim.tick

      qstruct.parallel<TOP> -> {
        qref.gate<#qcore.gate.cx> (%40, %51, %35, %43, %48, %38)
        qstruct.yield
      } {
        qref.gate<#qcore.gate.cz> (%36, %39, %45, %46, %42, %49)
        qstruct.yield
      }

      // CHECK-NEXT:     stim.clifford CNOT (%5, %16, %0, %8, %13, %3)
      // CHECK-NEXT:     stim.clifford CZ (%1, %4, %10, %11, %7, %14)
      // CHECK-NEXT:     stim.tick

      qstruct.parallel<TOP> -> {
        qref.gate<#qcore.gate.cx> (%35, %44, %48, %51, %41, %43)
        qstruct.yield
      } {
        qref.gate<#qcore.gate.cz> (%45, %49, %50, %37, %42, %47)
        qstruct.yield
      }

      // CHECK-NEXT:     stim.clifford CNOT (%0, %9, %13, %16, %6, %8)
      // CHECK-NEXT:     stim.clifford CZ (%10, %14, %15, %2, %7, %12)
      // CHECK-NEXT:     stim.tick

      qstruct.parallel<TOP> -> {
        qref.gate<#qcore.gate.cx> (%35, %49, %48, %39, %41, %47)
        qstruct.yield
      } {
        qref.gate<#qcore.gate.cz> (%45, %51, %50, %44, %42, %38)
        qstruct.yield
      }

      // CHECK-NEXT:     stim.clifford CNOT (%0, %14, %13, %4, %6, %12)
      // CHECK-NEXT:     stim.clifford CZ (%10, %16, %15, %9, %7, %3)
      // CHECK-NEXT:     stim.tick

      %81, %82, %83, %84, %85, %86, %87, %88 = qref.measure<X> (%40, %36, %35, %48, %41, %45, %50, %42) -> i1, i1, i1, i1, i1, i1, i1, i1

      // CHECK-NEXT:     %41, %42, %43, %44, %45, %46, %47, %48 = stim.measure X (%5, %1, %0, %13, %6, %10, %15, %7) -> i1, i1, i1, i1, i1, i1, i1, i1

      qec.measurement_round(%81, %82, %83, %84, %85, %86, %87, %88 : i1, i1, i1, i1, i1, i1, i1, i1)

      // CHECK-NEXT:     stim.tick

      %89 = qec.detector<[6.0, 4.0]> (%81, %73)
      %90 = qec.detector<[4.0, 0.0]> (%82, %74)
      %91 = qec.detector<[2.0, 4.0]> (%83, %75)
      %92 = qec.detector<[4.0, 2.0]> (%84, %76)
      %93 = qec.detector<[0.0, 2.0]> (%85, %77)
      %94 = qec.detector<[4.0, 4.0]> (%78, %86)
      %95 = qec.detector<[2.0, 6.0]> (%87, %79)
      %96 = qec.detector<[2.0, 2.0]> (%88, %80)

      // CHECK-NEXT:     stim.detector <[6.0, 4.0, 1.0]> (%41, %33 : i1, i1)
      // CHECK-NEXT:     stim.detector <[4.0, 0.0, 1.0]> (%42, %34 : i1, i1)
      // CHECK-NEXT:     stim.detector <[2.0, 4.0, 1.0]> (%43, %35 : i1, i1)
      // CHECK-NEXT:     stim.detector <[4.0, 2.0, 1.0]> (%44, %36 : i1, i1)
      // CHECK-NEXT:     stim.detector <[0.0, 2.0, 1.0]> (%45, %37 : i1, i1)
      // CHECK-NEXT:     stim.detector <[4.0, 4.0, 1.0]> (%38, %46 : i1, i1)
      // CHECK-NEXT:     stim.detector <[2.0, 6.0, 1.0]> (%47, %39 : i1, i1)
      // CHECK-NEXT:     stim.detector <[2.0, 2.0, 1.0]> (%48, %40 : i1, i1)

      qec.detector_round(%89, %90, %91, %92, %93, %94, %95, %96)
      qstruct.yield %81, %82, %83, %84, %85, %86, %87, %88 : i1, i1, i1, i1, i1, i1, i1, i1

      // CHECK-NEXT:     stim.shift_coord <[0.0, 0.0, 1.0]>
      // CHECK-NEXT:     stim.yield %41, %42, %43, %44, %45, %46, %47, %48 : i1, i1, i1, i1, i1, i1, i1, i1

    }

    // CHECK-NEXT:   }

    qref.reset<X> (%45, %35, %36, %40, %48, %41, %50, %42)

    // CHECK-NEXT:   stim.reset X (%10, %0, %1, %5, %13, %6, %15, %7)
    // CHECK-NEXT:   stim.tick

    qstruct.parallel<TOP> -> {
      qref.gate<#qcore.gate.cx> (%40, %46, %35, %37, %48, %49)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.cz> (%36, %38, %45, %44, %42, %43)
      qstruct.yield
    }

    // CHECK-NEXT:   stim.clifford CNOT (%5, %11, %0, %2, %13, %14)
    // CHECK-NEXT:   stim.clifford CZ (%1, %3, %10, %9, %7, %8)
    // CHECK-NEXT:   stim.tick

    qstruct.parallel<TOP> -> {
      qref.gate<#qcore.gate.cx> (%40, %51, %35, %43, %48, %38)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.cz> (%36, %39, %45, %46, %42, %49)
      qstruct.yield
    }

    // CHECK-NEXT:   stim.clifford CNOT (%5, %16, %0, %8, %13, %3)
    // CHECK-NEXT:   stim.clifford CZ (%1, %4, %10, %11, %7, %14)
    // CHECK-NEXT:   stim.tick

    qstruct.parallel<TOP> -> {
      qref.gate<#qcore.gate.cx> (%35, %44, %48, %51, %41, %43)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.cz> (%45, %49, %50, %37, %42, %47)
      qstruct.yield
    }

    // CHECK-NEXT:   stim.clifford CNOT (%0, %9, %13, %16, %6, %8)
    // CHECK-NEXT:   stim.clifford CZ (%10, %14, %15, %2, %7, %12)
    // CHECK-NEXT:   stim.tick

    qstruct.parallel<TOP> -> {
      qref.gate<#qcore.gate.cx> (%35, %49, %48, %39, %41, %47)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.cz> (%45, %51, %50, %44, %42, %38)
      qstruct.yield
    }

    // CHECK-NEXT:   stim.clifford CNOT (%0, %14, %13, %4, %6, %12)
    // CHECK-NEXT:   stim.clifford CZ (%10, %16, %15, %9, %7, %3)
    // CHECK-NEXT:   stim.tick

    %97, %98, %99, %100, %101, %102, %103, %104 = qref.measure<X> (%40, %36, %35, %48, %41, %45, %50, %42) -> i1, i1, i1, i1, i1, i1, i1, i1

    // CHECK-NEXT:   %49, %50, %51, %52, %53, %54, %55, %56 = stim.measure X (%5, %1, %0, %13, %6, %10, %15, %7) -> i1, i1, i1, i1, i1, i1, i1, i1

    qec.measurement_round(%97, %98, %99, %100, %101, %102, %103, %104 : i1, i1, i1, i1, i1, i1, i1, i1)

    // CHECK-NEXT:   stim.tick

    %105 = qec.detector<[6.0, 4.0]> (%97, %65)
    %106 = qec.detector<[4.0, 0.0]> (%98, %66)
    %107 = qec.detector<[2.0, 4.0]> (%99, %67)
    %108 = qec.detector<[4.0, 2.0]> (%100, %68)
    %109 = qec.detector<[0.0, 2.0]> (%101, %69)
    %110 = qec.detector<[4.0, 4.0]> (%102, %70)
    %111 = qec.detector<[2.0, 6.0]> (%103, %71)
    %112 = qec.detector<[2.0, 2.0]> (%104, %72)

    // CHECK-NEXT:   stim.detector <[6.0, 4.0, 1.0]> (%49, %25 : i1, i1)
    // CHECK-NEXT:   stim.detector <[4.0, 0.0, 1.0]> (%50, %26 : i1, i1)
    // CHECK-NEXT:   stim.detector <[2.0, 4.0, 1.0]> (%51, %27 : i1, i1)
    // CHECK-NEXT:   stim.detector <[4.0, 2.0, 1.0]> (%52, %28 : i1, i1)
    // CHECK-NEXT:   stim.detector <[0.0, 2.0, 1.0]> (%53, %29 : i1, i1)
    // CHECK-NEXT:   stim.detector <[4.0, 4.0, 1.0]> (%54, %30 : i1, i1)
    // CHECK-NEXT:   stim.detector <[2.0, 6.0, 1.0]> (%55, %31 : i1, i1)
    // CHECK-NEXT:   stim.detector <[2.0, 2.0, 1.0]> (%56, %32 : i1, i1)

    qec.detector_round(%105, %106, %107, %108, %109, %110, %111, %112)
    %113, %114, %115, %116, %117, %118, %119, %120, %121 = qref.measure<Z> (%46, %37, %38, %47, %39, %49, %51, %43, %44) -> i1, i1, i1, i1, i1, i1, i1, i1, i1

    // CHECK-NEXT:   %57, %58, %59, %60, %61, %62, %63, %64, %65 = stim.measure Z (%11, %2, %3, %12, %4, %14, %16, %8, %9) -> i1, i1, i1, i1, i1, i1, i1, i1, i1

    qec.measurement_round(%113, %114, %115, %116, %117, %118, %119, %120, %121 : i1, i1, i1, i1, i1, i1, i1, i1, i1)

    // CHECK-NEXT:   stim.tick

    %122 = qec.detector<[4.0, 0.0]> (%98, %115, %117)
    %123 = qec.detector<[4.0, 4.0]> (%102, %113, %118, %119, %121)
    %124 = qec.detector<[2.0, 6.0]> (%114, %103, %121)
    %125 = qec.detector<[2.0, 2.0]> (%104, %115, %116, %118, %120)

    // CHECK-NEXT:   stim.detector <[4.0, 0.0, 2.0]> (%50, %59, %61 : i1, i1, i1)
    // CHECK-NEXT:   stim.detector <[4.0, 4.0, 2.0]> (%54, %57, %62, %63, %65 : i1, i1, i1, i1, i1)
    // CHECK-NEXT:   stim.detector <[2.0, 6.0, 2.0]> (%58, %55, %65 : i1, i1, i1)
    // CHECK-NEXT:   stim.detector <[2.0, 2.0, 2.0]> (%56, %59, %60, %62, %64 : i1, i1, i1, i1, i1)

    qec.detector_round(%122, %123, %124, %125)
    %126 = qec.observable_include(%52) using (%114, %116, %120) -> !qec.observable

    // CHECK-NEXT:   stim.observable_include <0> (%58, %60, %64 : i1, i1, i1)

    qstruct.yield %126, %35, %36, %37, %38, %39, %40, %41, %42, %43, %44, %45, %46, %47, %48, %49, %50, %51 : !qec.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
  %35 = qec.get_corrected(%17 : !qec.observable) -> i1
  qstruct.output(%35 : i1)

  // CHECK-NEXT: }

}

// ----

// CHECK: ----

// 3x3 rotated stability 10 rounds

builtin.module {

// CHECK: builtin.module {

  %0 = qcore.alloc_qubit<coords=[(4.0, 4.0)], ids=[0]> -> !qcore.qubit
  %1 = qcore.alloc_qubit<coords=[(2.0, 4.0)], ids=[1]> -> !qcore.qubit
  %2 = qcore.alloc_qubit<coords=[(4.0, 0.0)], ids=[2]> -> !qcore.qubit
  %3 = qcore.alloc_qubit<coords=[(0.0, 4.0)], ids=[3]> -> !qcore.qubit
  %4 = qcore.alloc_qubit<coords=[(6.0, 2.0)], ids=[4]> -> !qcore.qubit
  %5 = qcore.alloc_qubit<coords=[(1.0, 5.0)], ids=[5]> -> !qcore.qubit
  %6 = qcore.alloc_qubit<coords=[(3.0, 1.0)], ids=[6]> -> !qcore.qubit
  %7 = qcore.alloc_qubit<coords=[(5.0, 1.0)], ids=[7]> -> !qcore.qubit
  %8 = qcore.alloc_qubit<coords=[(4.0, 2.0)], ids=[8]> -> !qcore.qubit
  %9 = qcore.alloc_qubit<coords=[(3.0, 3.0)], ids=[9]> -> !qcore.qubit
  %10 = qcore.alloc_qubit<coords=[(2.0, 6.0)], ids=[10]> -> !qcore.qubit
  %11 = qcore.alloc_qubit<coords=[(2.0, 2.0)], ids=[11]> -> !qcore.qubit
  %12 = qcore.alloc_qubit<coords=[(5.0, 3.0)], ids=[12]> -> !qcore.qubit
  %13 = qcore.alloc_qubit<coords=[(1.0, 3.0)], ids=[13]> -> !qcore.qubit
  %14 = qcore.alloc_qubit<coords=[(3.0, 5.0)], ids=[14]> -> !qcore.qubit

  // CHECK-NEXT:   %0 = stim.qubit_alloc 0 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <4.0, 4.0> (%0 : !stim.qubit)
  // CHECK-NEXT:   %1 = stim.qubit_alloc 1 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <2.0, 4.0> (%1 : !stim.qubit)
  // CHECK-NEXT:   %2 = stim.qubit_alloc 2 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <4.0, 0.0> (%2 : !stim.qubit)
  // CHECK-NEXT:   %3 = stim.qubit_alloc 3 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <0.0, 4.0> (%3 : !stim.qubit)
  // CHECK-NEXT:   %4 = stim.qubit_alloc 4 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <6.0, 2.0> (%4 : !stim.qubit)
  // CHECK-NEXT:   %5 = stim.qubit_alloc 5 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <1.0, 5.0> (%5 : !stim.qubit)
  // CHECK-NEXT:   %6 = stim.qubit_alloc 6 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <3.0, 1.0> (%6 : !stim.qubit)
  // CHECK-NEXT:   %7 = stim.qubit_alloc 7 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <5.0, 1.0> (%7 : !stim.qubit)
  // CHECK-NEXT:   %8 = stim.qubit_alloc 8 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <4.0, 2.0> (%8 : !stim.qubit)
  // CHECK-NEXT:   %9 = stim.qubit_alloc 9 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <3.0, 3.0> (%9 : !stim.qubit)
  // CHECK-NEXT:   %10 = stim.qubit_alloc 10 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <2.0, 6.0> (%10 : !stim.qubit)
  // CHECK-NEXT:   %11 = stim.qubit_alloc 11 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <2.0, 2.0> (%11 : !stim.qubit)
  // CHECK-NEXT:   %12 = stim.qubit_alloc 12 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <5.0, 3.0> (%12 : !stim.qubit)
  // CHECK-NEXT:   %13 = stim.qubit_alloc 13 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <1.0, 3.0> (%13 : !stim.qubit)
  // CHECK-NEXT:   %14 = stim.qubit_alloc 14 -> !stim.qubit
  // CHECK-NEXT:   stim.assign_qubit_coord <3.0, 5.0> (%14 : !stim.qubit)

  %15, %16, %17, %18, %19, %20, %21, %22, %23, %24, %25, %26, %27, %28, %29, %30 = qstruct.circuit(%0, %1, %2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qec.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
  ^bb0(%31: !qcore.qubit, %32: !qcore.qubit, %33: !qcore.qubit, %34: !qcore.qubit, %35: !qcore.qubit, %36: !qcore.qubit, %37: !qcore.qubit, %38: !qcore.qubit, %39: !qcore.qubit, %40: !qcore.qubit, %41: !qcore.qubit, %42: !qcore.qubit, %43: !qcore.qubit, %44: !qcore.qubit, %45: !qcore.qubit):
    %46 = qec.dec_observable -> !qec.observable
    qref.reset<X> (%31, %32, %35, %33, %34, %36, %37, %38, %39, %40, %41, %42, %43, %44, %45)

    // CHECK-NEXT:   stim.reset X (%0, %1, %4, %2, %3, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14)
    // CHECK-NEXT:   stim.tick

    qstruct.parallel<TOP> -> {
      qref.gate<#qcore.gate.cx> (%32, %45, %39, %43)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.cz> (%42, %40, %33, %38, %34, %36)
      qstruct.yield
    }

    // CHECK-NEXT:   stim.clifford CNOT (%1, %14, %8, %12)
    // CHECK-NEXT:   stim.clifford CZ (%11, %9, %2, %7, %3, %5)
    // CHECK-NEXT:   stim.tick

    qstruct.parallel<TOP> -> {
      qref.gate<#qcore.gate.cx> (%32, %40, %39, %38)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.cz> (%42, %44, %31, %45, %35, %43, %33, %37)
      qstruct.yield
    }

    // CHECK-NEXT:   stim.clifford CNOT (%1, %9, %8, %7)
    // CHECK-NEXT:   stim.clifford CZ (%11, %13, %0, %14, %4, %12, %2, %6)
    // CHECK-NEXT:   stim.tick

    qstruct.parallel<TOP> -> {
      qref.gate<#qcore.gate.cx> (%32, %36, %39, %40)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.cz> (%42, %37, %31, %43, %41, %45, %34, %44)
      qstruct.yield
    }

    // CHECK-NEXT:   stim.clifford CNOT (%1, %5, %8, %9)
    // CHECK-NEXT:   stim.clifford CZ (%11, %6, %0, %12, %10, %14, %3, %13)
    // CHECK-NEXT:   stim.tick

    qstruct.parallel<TOP> -> {
      qref.gate<#qcore.gate.cx> (%32, %44, %39, %37)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.cz> (%31, %40, %41, %36, %35, %38)
      qstruct.yield
    }

    // CHECK-NEXT:   stim.clifford CNOT (%1, %13, %8, %6)
    // CHECK-NEXT:   stim.clifford CZ (%0, %9, %10, %5, %4, %7)
    // CHECK-NEXT:   stim.tick

    %47, %48, %49, %50, %51, %52, %53, %54 = qref.measure<X> (%32, %39, %42, %31, %41, %35, %33, %34) -> i1, i1, i1, i1, i1, i1, i1, i1

    // CHECK-NEXT:   %15, %16, %17, %18, %19, %20, %21, %22 = stim.measure X (%1, %8, %11, %0, %10, %4, %2, %3) -> i1, i1, i1, i1, i1, i1, i1, i1

    qec.measurement_round(%47, %48, %49, %50, %51, %52, %53, %54 : i1, i1, i1, i1, i1, i1, i1, i1)

    // CHECK-NEXT:   stim.tick

    %55 = qec.detector<[4.0, 2.0]> (%48)
    %56 = qec.detector<[2.0, 4.0]> (%47)

    // CHECK-NEXT:   stim.detector <[4.0, 2.0, 0.0]> (%16 : i1)
    // CHECK-NEXT:   stim.detector <[2.0, 4.0, 0.0]> (%15 : i1)

    qec.detector_round(%56, %55)
    %57 = qec.observable_include(%46) using (%53, %49, %50, %51, %52, %54) -> !qec.observable

    // CHECK-NEXT:   stim.observable_include <0> (%21, %17, %18, %19, %20, %22 : i1, i1, i1, i1, i1, i1)

    %58, %59, %60, %61, %62, %63, %64, %65 = qstruct.repeat<8> (%47, %48, %49, %50, %51, %52, %53, %54 : i1, i1, i1, i1, i1, i1, i1, i1) -> i1, i1, i1, i1, i1, i1, i1, i1 {

    // CHECK-NEXT:   %23, %24, %25, %26, %27, %28, %29, %30 = stim.repeat 8 (%15, %16, %17, %18, %19, %20, %21, %22 : i1, i1, i1, i1, i1, i1, i1, i1) -> i1, i1, i1, i1, i1, i1, i1, i1 {

    ^bb1(%66: i1, %67: i1, %68: i1, %69: i1, %70: i1, %71: i1, %72: i1, %73: i1):

    // CHECK-NEXT:   ^bb0(%31: i1, %32: i1, %33: i1, %34: i1, %35: i1, %36: i1, %37: i1, %38: i1):

      qref.reset<X> (%31, %32, %35, %33, %34, %39, %41, %42)

      // CHECK-NEXT:     stim.reset X (%0, %1, %4, %2, %3, %8, %10, %11)
      // CHECK-NEXT:     stim.tick

      qstruct.parallel<TOP> -> {
        qref.gate<#qcore.gate.cx> (%32, %45, %39, %43)
        qstruct.yield
      } {
        qref.gate<#qcore.gate.cz> (%42, %40, %33, %38, %34, %36)
        qstruct.yield
      }

      // CHECK-NEXT:     stim.clifford CNOT (%1, %14, %8, %12)
      // CHECK-NEXT:     stim.clifford CZ (%11, %9, %2, %7, %3, %5)
      // CHECK-NEXT:     stim.tick

      qstruct.parallel<TOP> -> {
        qref.gate<#qcore.gate.cx> (%32, %40, %39, %38)
        qstruct.yield
      } {
        qref.gate<#qcore.gate.cz> (%42, %44, %31, %45, %35, %43, %33, %37)
        qstruct.yield
      }

      // CHECK-NEXT:     stim.clifford CNOT (%1, %9, %8, %7)
      // CHECK-NEXT:     stim.clifford CZ (%11, %13, %0, %14, %4, %12, %2, %6)
      // CHECK-NEXT:     stim.tick

      qstruct.parallel<TOP> -> {
        qref.gate<#qcore.gate.cx> (%32, %36, %39, %40)
        qstruct.yield
      } {
        qref.gate<#qcore.gate.cz> (%42, %37, %31, %43, %41, %45, %34, %44)
        qstruct.yield
      }

      // CHECK-NEXT:     stim.clifford CNOT (%1, %5, %8, %9)
      // CHECK-NEXT:     stim.clifford CZ (%11, %6, %0, %12, %10, %14, %3, %13)
      // CHECK-NEXT:     stim.tick

      qstruct.parallel<TOP> -> {
        qref.gate<#qcore.gate.cx> (%32, %44, %39, %37)
        qstruct.yield
      } {
        qref.gate<#qcore.gate.cz> (%31, %40, %41, %36, %35, %38)
        qstruct.yield
      }

      // CHECK-NEXT:     stim.clifford CNOT (%1, %13, %8, %6)
      // CHECK-NEXT:     stim.clifford CZ (%0, %9, %10, %5, %4, %7)
      // CHECK-NEXT:     stim.tick

      %74, %75, %76, %77, %78, %79, %80, %81 = qref.measure<X> (%32, %39, %42, %31, %41, %35, %33, %34) -> i1, i1, i1, i1, i1, i1, i1, i1

      // CHECK-NEXT:     %39, %40, %41, %42, %43, %44, %45, %46 = stim.measure X (%1, %8, %11, %0, %10, %4, %2, %3) -> i1, i1, i1, i1, i1, i1, i1, i1

      qec.measurement_round(%74, %75, %76, %77, %78, %79, %80, %81 : i1, i1, i1, i1, i1, i1, i1, i1)

      // CHECK-NEXT:     stim.tick

      %82 = qec.detector<[0.0, 4.0]> (%81, %73)
      %83 = qec.detector<[4.0, 0.0]> (%80, %72)
      %84 = qec.detector<[6.0, 2.0]> (%71, %79)
      %85 = qec.detector<[2.0, 6.0]> (%78, %70)
      %86 = qec.detector<[4.0, 4.0]> (%77, %69)
      %87 = qec.detector<[2.0, 2.0]> (%76, %68)
      %88 = qec.detector<[4.0, 2.0]> (%75, %67)
      %89 = qec.detector<[2.0, 4.0]> (%74, %66)

      // CHECK-NEXT:     stim.detector <[0.0, 4.0, 1.0]> (%46, %38 : i1, i1)
      // CHECK-NEXT:     stim.detector <[4.0, 0.0, 1.0]> (%45, %37 : i1, i1)
      // CHECK-NEXT:     stim.detector <[6.0, 2.0, 1.0]> (%36, %44 : i1, i1)
      // CHECK-NEXT:     stim.detector <[2.0, 6.0, 1.0]> (%43, %35 : i1, i1)
      // CHECK-NEXT:     stim.detector <[4.0, 4.0, 1.0]> (%42, %34 : i1, i1)
      // CHECK-NEXT:     stim.detector <[2.0, 2.0, 1.0]> (%41, %33 : i1, i1)
      // CHECK-NEXT:     stim.detector <[4.0, 2.0, 1.0]> (%40, %32 : i1, i1)
      // CHECK-NEXT:     stim.detector <[2.0, 4.0, 1.0]> (%39, %31 : i1, i1)

      qec.detector_round(%89, %88, %87, %86, %85, %84, %83, %82)
      qstruct.yield %74, %75, %76, %77, %78, %79, %80, %81 : i1, i1, i1, i1, i1, i1, i1, i1

      // CHECK-NEXT:     stim.shift_coord <[0.0, 0.0, 1.0]>
      // CHECK-NEXT:     stim.yield %39, %40, %41, %42, %43, %44, %45, %46 : i1, i1, i1, i1, i1, i1, i1, i1

    }

    // CHECK-NEXT:   }

    qref.reset<X> (%31, %32, %35, %33, %34, %39, %41, %42)

    // CHECK-NEXT:   stim.reset X (%0, %1, %4, %2, %3, %8, %10, %11)
    // CHECK-NEXT:   stim.tick

    qstruct.parallel<TOP> -> {
      qref.gate<#qcore.gate.cx> (%32, %45, %39, %43)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.cz> (%42, %40, %33, %38, %34, %36)
      qstruct.yield
    }

    // CHECK-NEXT:   stim.clifford CNOT (%1, %14, %8, %12)
    // CHECK-NEXT:   stim.clifford CZ (%11, %9, %2, %7, %3, %5)
    // CHECK-NEXT:   stim.tick

    qstruct.parallel<TOP> -> {
      qref.gate<#qcore.gate.cx> (%32, %40, %39, %38)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.cz> (%42, %44, %31, %45, %35, %43, %33, %37)
      qstruct.yield
    }

    // CHECK-NEXT:   stim.clifford CNOT (%1, %9, %8, %7)
    // CHECK-NEXT:   stim.clifford CZ (%11, %13, %0, %14, %4, %12, %2, %6)
    // CHECK-NEXT:   stim.tick

    qstruct.parallel<TOP> -> {
      qref.gate<#qcore.gate.cx> (%32, %36, %39, %40)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.cz> (%42, %37, %31, %43, %41, %45, %34, %44)
      qstruct.yield
    }

    // CHECK-NEXT:   stim.clifford CNOT (%1, %5, %8, %9)
    // CHECK-NEXT:   stim.clifford CZ (%11, %6, %0, %12, %10, %14, %3, %13)
    // CHECK-NEXT:   stim.tick

    qstruct.parallel<TOP> -> {
      qref.gate<#qcore.gate.cx> (%32, %44, %39, %37)
      qstruct.yield
    } {
      qref.gate<#qcore.gate.cz> (%31, %40, %41, %36, %35, %38)
      qstruct.yield
    }

    // CHECK-NEXT:   stim.clifford CNOT (%1, %13, %8, %6)
    // CHECK-NEXT:   stim.clifford CZ (%0, %9, %10, %5, %4, %7)
    // CHECK-NEXT:   stim.tick

    %90, %91, %92, %93, %94, %95, %96, %97, %98, %99, %100, %101, %102, %103, %104 = qref.measure<X> (%32, %39, %42, %31, %41, %35, %33, %34, %44, %36, %37, %40, %45, %38, %43) -> i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1

    // CHECK-NEXT:   %47, %48, %49, %50, %51, %52, %53, %54, %55, %56, %57, %58, %59, %60, %61 = stim.measure X (%1, %8, %11, %0, %10, %4, %2, %3, %13, %5, %6, %9, %14, %7, %12) -> i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1

    qec.measurement_round(%90, %91, %92, %93, %94, %95, %96, %97, %98, %99, %100, %101, %102, %103, %104 : i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1, i1)

    // CHECK-NEXT:   stim.tick

    %105 = qec.detector<[4.0, 2.0]> (%91, %104, %100, %101, %103)
    %106 = qec.detector<[2.0, 4.0]> (%90, %98, %99, %101, %102)
    %107 = qec.detector<[0.0, 4.0]> (%97, %65)
    %108 = qec.detector<[4.0, 0.0]> (%96, %64)
    %109 = qec.detector<[6.0, 2.0]> (%95, %63)
    %110 = qec.detector<[2.0, 6.0]> (%94, %62)
    %111 = qec.detector<[4.0, 4.0]> (%93, %61)
    %112 = qec.detector<[2.0, 2.0]> (%92, %60)
    %113 = qec.detector<[4.0, 2.0]> (%91, %59)
    %114 = qec.detector<[2.0, 4.0]> (%90, %58)

    // CHECK-NEXT:   stim.detector <[4.0, 2.0, 1.0]> (%48, %61, %57, %58, %60 : i1, i1, i1, i1, i1)
    // CHECK-NEXT:   stim.detector <[2.0, 4.0, 1.0]> (%47, %55, %56, %58, %59 : i1, i1, i1, i1, i1)
    // CHECK-NEXT:   stim.detector <[0.0, 4.0, 1.0]> (%54, %30 : i1, i1)
    // CHECK-NEXT:   stim.detector <[4.0, 0.0, 1.0]> (%53, %29 : i1, i1)
    // CHECK-NEXT:   stim.detector <[6.0, 2.0, 1.0]> (%52, %28 : i1, i1)
    // CHECK-NEXT:   stim.detector <[2.0, 6.0, 1.0]> (%51, %27 : i1, i1)
    // CHECK-NEXT:   stim.detector <[4.0, 4.0, 1.0]> (%50, %26 : i1, i1)
    // CHECK-NEXT:   stim.detector <[2.0, 2.0, 1.0]> (%49, %25 : i1, i1)
    // CHECK-NEXT:   stim.detector <[4.0, 2.0, 1.0]> (%48, %24 : i1, i1)
    // CHECK-NEXT:   stim.detector <[2.0, 4.0, 1.0]> (%47, %23 : i1, i1)

    qec.detector_round(%114, %113, %112, %111, %110, %109, %108, %107)
    qec.detector_round(%106, %105)
    qstruct.yield %57, %31, %32, %33, %34, %35, %36, %37, %38, %39, %40, %41, %42, %43, %44, %45 : !qec.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
  %31 = qec.get_corrected(%15 : !qec.observable) -> i1
  qstruct.output(%31 : i1)

  // CHECK-NEXT: }

}
