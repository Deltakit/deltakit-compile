// RUN: deltakit_compile compile-passes -t %s -p stim-to-qref -O %t && filecheck %s --input-file %t

// Input IR is in the form produced by stim-to-qstruct: 6 qcore qubits allocated at module
// builtin.unrealized_conversion_cast before being used by stim operations.

// CHECK: builtin.module {

builtin.module {
    %q1, %q2, %q3, %q4, %q5, %q6 = qcore.alloc_qubit<> -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
    %q7, %q8, %q9, %q10, %q11, %q12 = qstruct.circuit(%q1, %q2, %q3, %q4, %q5, %q6 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
    ^bb0(%q1_1: !qcore.qubit, %q2_1: !qcore.qubit, %q3_1: !qcore.qubit, %q4_1: !qcore.qubit, %q5_1: !qcore.qubit, %q6_1: !qcore.qubit):
        %q1_2 = builtin.unrealized_conversion_cast %q1_1 : !qcore.qubit to !stim.qubit
        %q2_2 = builtin.unrealized_conversion_cast %q2_1 : !qcore.qubit to !stim.qubit
        %q3_2 = builtin.unrealized_conversion_cast %q3_1 : !qcore.qubit to !stim.qubit
        %q4_2 = builtin.unrealized_conversion_cast %q4_1 : !qcore.qubit to !stim.qubit
        %q5_2 = builtin.unrealized_conversion_cast %q5_1 : !qcore.qubit to !stim.qubit
        %q6_2 = builtin.unrealized_conversion_cast %q6_1 : !qcore.qubit to !stim.qubit

// CHECK-NEXT:  %q1, %q2, %q3, %q4, %q5, %q6 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:  %q7, %q8, %q9, %q10, %q11, %q12 = qstruct.circuit(%q1, %q2, %q3, %q4, %q5, %q6 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:      ^bb0(%q1_1: !qcore.qubit, %q2_1: !qcore.qubit, %q3_1: !qcore.qubit, %q4_1: !qcore.qubit, %q5_1: !qcore.qubit, %q6_1: !qcore.qubit):

// CHECK-NOT: %q1_2 = builtin.unrealized_conversion_cast %q1_1 : !qcore.qubit to !stim.qubit

        // Gates
        // CHECK-NEXT: qref.gate<#qcore.gate.x> (%q1_1)
        stim.clifford X (%q1_2)
        // CHECK-NEXT: qref.gate<#qcore.gate.h> (%q2_1)
        stim.clifford H (%q2_2)
        // CHECK-NEXT: qref.gate<#qcore.gate.cx> (%q1_1, %q2_1)
        stim.clifford CNOT (%q1_2, %q2_2)
        // CHECK-NEXT: qref.gate<#qcore.gate.cz> (%q3_1, %q4_1)
        stim.clifford CZ (%q3_2, %q4_2)

        // Resets
        // CHECK-NEXT: qref.reset<Z> (%q1_1)
        stim.reset Z (%q1_2)
        // CHECK-NEXT: qref.reset<X> (%q2_1)
        stim.reset X (%q2_2)
        // CHECK-NEXT: qref.reset<Y> (%q3_1)
        stim.reset Y (%q3_2)

        // Measurements (noiseless)
        // CHECK-NEXT: %m0 = qref.measure<Z> (%q1_1) -> i1
        %m0 = stim.measure Z (%q1_2) -> i1
        // CHECK-NEXT: %m1 = qref.measure<X> (%q2_1) -> i1
        %m1 = stim.measure X (%q2_2) -> i1
        // CHECK-NEXT: %m2 = qref.measure<Y> (%q3_1) -> i1
        %m2 = stim.measure Y (%q3_2) -> i1

        // Measurement with noise
        // CHECK-NEXT: %m3 = qref.measure<Z, 0.01> (%q4_1) -> i1
        %m3 = stim.measure Z <0.01> (%q4_2) -> i1

        // Multi-qubit measurement (broadcast)
        // CHECK-NEXT: %m4, %m5 = qref.measure<Z> (%q5_1, %q6_1) -> i1, i1
        %m4, %m5 = stim.measure Z (%q5_2, %q6_2) -> i1, i1

        // Depolarize 1
        // CHECK-NEXT: qref.pauli_noise<X = 0.0003333333333333333, Y = 0.0003333333333333333, Z = 0.0003333333333333333> (%q1_1, %q2_1, %q3_1, %q4_1, %q5_1, %q6_1)
        stim.depolarize1 <0.001> (%q1_2, %q2_2, %q3_2, %q4_2, %q5_2, %q6_2)

        // Depolarize 2
        // CHECK-NEXT: qref.pauli_noise<IX = 0.00013333333333333334, IY = 0.00013333333333333334, IZ = 0.00013333333333333334, XI = 0.00013333333333333334, XX = 0.00013333333333333334, XY = 0.00013333333333333334, XZ = 0.00013333333333333334, YI = 0.00013333333333333334, YX = 0.00013333333333333334, YY = 0.00013333333333333334, YZ = 0.00013333333333333334, ZI = 0.00013333333333333334, ZX = 0.00013333333333333334, ZY = 0.00013333333333333334, ZZ = 0.00013333333333333334> (%q3_1, %q4_1)
        stim.depolarize2 <0.002> (%q3_2, %q4_2)

        // Pauli channel 1
        // CHECK-NEXT: qref.pauli_noise<X = 0.01, Y = 0.02, Z = 0.03> (%q5_1, %q6_1)
        stim.pauli_channel_1 <0.01, 0.02, 0.03> (%q5_2, %q6_2)

        // Correlated error (single, no else)
        // CHECK-NEXT: qref.pauli_noise<Z = 0.1> (%q1_1)
        stim.correlated_error <0.1> [Z] (%q1_2)

        // Correlated error chain with one else: abs_prob_0 = 0.1, abs_prob_1 = 0.2*(1-0.1)
        // CHECK-NEXT: qref.pauli_noise<XX = 0.19999999999999998, ZX = 0.1> (%q2_1, %q3_1)
        stim.correlated_error <0.1> [Z, X] (%q2_2, %q3_2)
        stim.else_correlated_error <0.2222222222222222> [X, X] (%q2_2, %q3_2)

        // Correlated error chain with two elses spanning all 6 qubits
        // CHECK-NEXT: qref.pauli_noise<IIXXYI = 0.19999999999999998, YIIIIX = 0.30000000000000004, ZXIIII = 0.1> (%q1_1, %q2_1, %q3_1, %q4_1, %q5_1, %q6_1) {stim.tag = "tag1"}
        stim.correlated_error <0.1> [Z, X] (%q1_2, %q2_2) {stim.tag = "tag1"}
        stim.else_correlated_error <0.2222222222222222> [X, X, Y] (%q3_2, %q4_2, %q5_2) {stim.tag = "tag2"}
        stim.else_correlated_error <0.4285714285714286> [Y, X] (%q1_2, %q6_2)

        // MPP (noiseless): joint XZ measurement of q1 and q2 produces one parity bit
        // CHECK-NEXT: %m6 = qref.measure<XZ> (%q1_1, %q2_1) -> i1
        %m6 = stim.mpp[X, Z] (%q1_2, %q2_2) -> i1

        // MPP (with noise): joint XZY measurement of q1, q2, q3 with readout-flip probability
        // CHECK-NEXT: %m7 = qref.measure<XZY, 0.05> (%q1_1, %q2_1, %q3_1) -> i1
        %m7 = stim.mpp[X, Z, Y] <0.05> (%q1_2, %q2_2, %q3_2) -> i1

        // Pauli channel 2: two-qubit noise with explicit probabilities for each Pauli pair
        // CHECK-NEXT: qref.pauli_noise<IX = 0.001, IY = 0.002, IZ = 0.003, XI = 0.004, XX = 0.005, XY = 0.006, XZ = 0.007, YI = 0.008, YX = 0.009, YY = 0.01, YZ = 0.011, ZI = 0.012, ZX = 0.013, ZY = 0.014, ZZ = 0.015> (%q1_1, %q2_1)
        stim.pauli_channel_2 <0.001, 0.002, 0.003, 0.004, 0.005, 0.006, 0.007, 0.008, 0.009, 0.01, 0.011, 0.012, 0.013, 0.014, 0.015> (%q1_2, %q2_2)

        qstruct.yield %q1_1, %q2_1, %q3_1, %q4_1, %q5_1, %q6_1 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
    }
}

// CHECK-NEXT:     qstruct.yield %q1_1, %q2_1, %q3_1, %q4_1, %q5_1, %q6_1 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   }
// CHECK-NEXT: }

// ----
// CHECK: ----

builtin.module{
    qstruct.circuit -> {
    ^bb0():
        %q0 = stim.qubit_alloc 1 -> !stim.qubit
        %m0 = stim.measure Z (%q0) -> i1
        qstruct.yield
    }
}

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   qstruct.circuit -> {
// CHECK-NEXT:     %q0 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:     %q0_1 = builtin.unrealized_conversion_cast %q0 : !stim.qubit to !qcore.qubit
// CHECK-NEXT:     %m0 = qref.measure<Z> (%q0_1) -> i1
// CHECK-NEXT:     qstruct.yield
// CHECK-NEXT:   }
// CHECK-NEXT: }
