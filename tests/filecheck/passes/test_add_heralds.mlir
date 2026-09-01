// RUN: deltakit_compile compile-passes %s -p add-heralds -O %t && filecheck %s --input-file %t

builtin.module {
    // CHECK:       builtin.module {
    %0 = stim.qubit_alloc 0 -> !stim.qubit
    %1 = stim.qubit_alloc 1 -> !stim.qubit
    %2 = stim.qubit_alloc 2 -> !stim.qubit
    // CHECK-NEXT:    %0 = stim.qubit_alloc 0 -> !stim.qubit
    // CHECK-NEXT:    %1 = stim.qubit_alloc 1 -> !stim.qubit
    // CHECK-NEXT:    %2 = stim.qubit_alloc 2 -> !stim.qubit

    deltakit_stim.leakage <0.001> (%2)
    stim.clifford CX (%2, %1)
    stim.pauli_channel_1 <0.01, 0.0, 0.0> (%1, %2)
    // CHECK-NEXT:    deltakit_stim.leakage <0.001> (%2)
    // CHECK-NEXT:    stim.clifford CX (%2, %1)
    // CHECK-NEXT:    stim.pauli_channel_1 <0.01, 0.0, 0.0> (%1, %2)

    // CHECK-NEXT:    %3, %4 = deltakit_stim.herald_leakage_event (%1, %2) -> i1, i1
    // CHECK-NEXT:    stim.detector (%3 : i1)
    // CHECK-NEXT:    stim.detector (%4 : i1)

    %3 = stim.mpp[Z, Z] (%1, %2) -> i1
    // CHECK-NEXT:    %5 = stim.mpp[Z, Z] (%1, %2) -> i1
    // CHECK-NEXT:    %6, %7 = deltakit_stim.herald_leakage_event (%1, %2) -> i1, i1
    // CHECK-NEXT:    stim.detector (%6 : i1)
    // CHECK-NEXT:    stim.detector (%7 : i1)
    %4 = stim.mpp[X, X] (%1, %2) -> i1
    // CHECK-NEXT:    %8 = stim.mpp[X, X] (%1, %2) -> i1

    // CHECK-NEXT:    %9, %10 = deltakit_stim.herald_leakage_event (%1, %2) -> i1, i1
    // CHECK-NEXT:    stim.detector (%9 : i1)
    // CHECK-NEXT:    stim.detector (%10 : i1)

    %5, %6 = stim.measure Z (%1, %2) -> i1, i1
    stim.detector <[1.0, 0.0, 0.0]> (%5 : i1)
    // CHECK-NEXT:    %11, %12 = stim.measure Z (%1, %2) -> i1, i1
    // CHECK-NEXT:    stim.detector <[1.0, 0.0, 0.0]> (%11 : i1)

    %7, %8 = stim.repeat 2 (%3, %4 : i1, i1) -> i1, i1 {
    ^bb0(%11: i1, %12: i1):
    // CHECK-NEXT:    %13, %14 = stim.repeat 2 (%5, %8 : i1, i1) -> i1, i1 {
    // CHECK-NEXT:    ^bb0(%15: i1, %16: i1):

        stim.tick
        // CHECK-NEXT:      stim.tick

        // CHECK-NEXT:      %17, %18, %19 = deltakit_stim.herald_leakage_event (%0, %1, %2) -> i1, i1, i1
        // CHECK-NEXT:      stim.detector (%17 : i1)
        // CHECK-NEXT:      stim.detector (%18 : i1)
        // CHECK-NEXT:      stim.detector (%19 : i1)

        %17, %18, %19 = stim.measure Z (%0, %1, %2) -> i1, i1, i1
        stim.reset Z (%1, %2)
        stim.shift_coord <[0.0, 0.0, 1.0]>
        stim.detector <[1.0, 0.0, 0.0]> (%17, %18 : i1, i1)
        stim.detector <[2.0, 0.0, 0.0]> (%3, %18 : i1, i1)
        stim.detector <[3.0, 0.0, 0.0]> (%18, %19 : i1, i1)

        // CHECK-NEXT:      %20, %21, %22 = stim.measure Z (%0, %1, %2) -> i1, i1, i1
        // CHECK-NEXT:      stim.reset Z (%1, %2)
        // CHECK-NEXT:      stim.shift_coord <[0.0, 0.0, 1.0]>
        // CHECK-NEXT:      stim.detector <[1.0, 0.0, 0.0]> (%20, %21 : i1, i1)
        // CHECK-NEXT:      stim.detector <[2.0, 0.0, 0.0]> (%5, %21 : i1, i1)
        // CHECK-NEXT:      stim.detector <[3.0, 0.0, 0.0]> (%21, %22 : i1, i1)

        stim.yield %17, %18 : i1, i1
    }
    // CHECK-NEXT:      stim.yield %20, %21 : i1, i1
    // CHECK-NEXT:    }
}
// CHECK-NEXT:  }
