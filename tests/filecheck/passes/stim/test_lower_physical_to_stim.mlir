// RUN: deltakit_compile compile-passes -t %s -p lower-physical-to-stim --pass-args '{"empty_detectors_get_deleted": false}' -O %t && filecheck %s --input-file %t

// Just gates

builtin.module {
  %q0, %q1, %q2, %q3 = qcore.alloc_qubit<coords=[(0, 0), (1, 1), (2, 2), (3, 3)]> -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  %0, %1, %2, %3 = qstruct.circuit(%q0, %q1, %q2, %q3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit{
  ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit, %q2_1: !qcore.qubit, %q3_1: !qcore.qubit):
    qref.gate<#qcore.gate.h> (%q0_1, %q1_1, %q2_1, %q3_1)
    qref.gate<#qcore.gate.cx> (%q0_1, %q1_1)
    qstruct.yield %q0_1, %q1_1, %q2_1, %q3_1: !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %q0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:    %q1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:    %q2 = stim.qubit_alloc 2 -> !stim.qubit
// CHECK-NEXT:    %q3 = stim.qubit_alloc 3 -> !stim.qubit
// CHECK-NEXT:    stim.assign_qubit_coord <0.0, 0.0> (%q0 : !stim.qubit)
// CHECK-NEXT:    stim.assign_qubit_coord <1.0, 1.0> (%q1 : !stim.qubit)
// CHECK-NEXT:    stim.assign_qubit_coord <2.0, 2.0> (%q2 : !stim.qubit)
// CHECK-NEXT:    stim.assign_qubit_coord <3.0, 3.0> (%q3 : !stim.qubit)
// CHECK-NEXT:    stim.clifford H (%q0, %q1, %q2, %q3)
// CHECK-NEXT:    stim.clifford CNOT (%q0, %q1)
// CHECK-NEXT:  }

// ----
// CHECK: ----

// Just noise

builtin.module {
  %q0, %q1, %q2, %q3, %q4, %q5 = qcore.alloc_qubit<coords=[(0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]>
    -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  %0, %1, %2, %3, %4, %5 = qstruct.circuit(%q0, %q1, %q2, %q3, %q4, %q5 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit)
    -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit{
  ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit, %q2_1: !qcore.qubit, %q3_1: !qcore.qubit, %q4_1: !qcore.qubit, %q5_1: !qcore.qubit):
    qref.pauli_noise<X=0.01, Y = 0.02, Z=0.03> (%q0_1, %q1_1)
    qref.pauli_noise<X=0.01, Y = 0.01, Z=0.01> (%q1_1, %q2_1, %q3_1)
    qref.pauli_noise<IZ=0.1, XI = 0.2, YI=0.3> (%q0_1, %q1_1)
    qref.pauli_noise<IX=0.01, IY=0.01, IZ=0.01, XI=0.01, XX=0.01, XY=0.01, XZ=0.01, YI=0.01, YX=0.01, YY=0.01, YZ=0.01, ZI=0.01, ZX=0.01, ZY=0.01, ZZ=0.01> (%q0_1, %q1_1, %q2_1, %q3_1)
    qref.pauli_noise<IZX=0.1, XIX = 0.2, YIX=0.3> (%q0_1, %q1_1, %q2_1)
    qref.pauli_noise<IZY=0.1, XYX = 0.2, YIX=0.3> (%q0_1, %q1_1, %q2_1, %q3_1, %q4_1, %q5_1)
    qstruct.yield %q0_1, %q1_1, %q2_1, %q3_1, %q4_1, %q5_1: !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %q0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:    %q1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:    %q2 = stim.qubit_alloc 2 -> !stim.qubit
// CHECK-NEXT:    %q3 = stim.qubit_alloc 3 -> !stim.qubit
// CHECK-NEXT:    %q4 = stim.qubit_alloc 4 -> !stim.qubit
// CHECK-NEXT:    %q5 = stim.qubit_alloc 5 -> !stim.qubit
// CHECK-NEXT:    stim.assign_qubit_coord <0.0, 0.0> (%q0 : !stim.qubit)
// CHECK-NEXT:    stim.assign_qubit_coord <1.0, 1.0> (%q1 : !stim.qubit)
// CHECK-NEXT:    stim.assign_qubit_coord <2.0, 2.0> (%q2 : !stim.qubit)
// CHECK-NEXT:    stim.assign_qubit_coord <3.0, 3.0> (%q3 : !stim.qubit)
// CHECK-NEXT:    stim.assign_qubit_coord <4.0, 4.0> (%q4 : !stim.qubit)
// CHECK-NEXT:    stim.assign_qubit_coord <5.0, 5.0> (%q5 : !stim.qubit)
// CHECK-NEXT:    stim.pauli_channel_1 <0.01, 0.02, 0.03> (%q0, %q1)
// CHECK-NEXT:    stim.depolarize1 <0.03> (%q1, %q2, %q3)
// CHECK-NEXT:    stim.pauli_channel_2 <0.0, 0.0, 0.1, 0.2, 0.0, 0.0, 0.0, 0.3, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0> (%q0, %q1)
// CHECK-NEXT:    stim.depolarize2 <0.15> (%q0, %q1, %q2, %q3)
// CHECK-NEXT:    stim.correlated_error <0.1> [Z, X] (%q1, %q2)
// CHECK-NEXT:    stim.else_correlated_error <0.22222222222222224> [X, X] (%q0, %q2)
// CHECK-NEXT:    stim.else_correlated_error <0.4285714285714286> [Y, X] (%q0, %q2)
// CHECK-NEXT:    stim.correlated_error <0.1> [Z, Y] (%q1, %q2)
// CHECK-NEXT:    stim.else_correlated_error <0.22222222222222224> [X, Y, X] (%q0, %q1, %q2)
// CHECK-NEXT:    stim.else_correlated_error <0.4285714285714286> [Y, X] (%q0, %q2)
// CHECK-NEXT:    stim.correlated_error <0.1> [Z, Y] (%q4, %q5)
// CHECK-NEXT:    stim.else_correlated_error <0.22222222222222224> [X, Y, X] (%q3, %q4, %q5)
// CHECK-NEXT:    stim.else_correlated_error <0.4285714285714286> [Y, X] (%q3, %q5)
// CHECK-NEXT:  }

// ----
// CHECK: ----

// Just measures

builtin.module {
  %q0, %q1, %q2, %q3 = qcore.alloc_qubit<coords=[(0, 0), (1, 1), (2, 2), (3, 3)]> -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  %0, %1, %2, %3 = qstruct.circuit(%q0, %q1, %q2, %q3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit{
  ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit, %q2_1: !qcore.qubit, %q3_1: !qcore.qubit):
    %m0, %m1, %m2 = qref.measure<Z>(%q0_1, %q1_1, %q3_1) -> i1, i1, i1
    %m3, %m4 = qref.measure<[Z,Z]>(%q0_1, %q1_1) -> i1, i1
    %m5, %m6, %m7 = qref.measure<[X,Z,X], 0.1>(%q0_1, %q1_1, %q2_1) -> i1, i1, i1
    %m8 = qref.measure<XZX, 0.2>(%q0_1, %q1_1, %q2_1) -> i1
    %m9, %m10 = qref.measure<YX, 0.3>(%q1_1, %q2_1, %q0_1, %q3_1) -> i1, i1
    qstruct.yield %q0_1, %q1_1, %q2_1, %q3_1: !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
  }
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %q0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:    %q1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:    %q2 = stim.qubit_alloc 2 -> !stim.qubit
// CHECK-NEXT:    %q3 = stim.qubit_alloc 3 -> !stim.qubit
// CHECK-NEXT:    stim.assign_qubit_coord <0.0, 0.0> (%q0 : !stim.qubit)
// CHECK-NEXT:    stim.assign_qubit_coord <1.0, 1.0> (%q1 : !stim.qubit)
// CHECK-NEXT:    stim.assign_qubit_coord <2.0, 2.0> (%q2 : !stim.qubit)
// CHECK-NEXT:    stim.assign_qubit_coord <3.0, 3.0> (%q3 : !stim.qubit)
// CHECK-NEXT:    %m0, %m1, %m2 = stim.measure Z (%q0, %q1, %q3) -> i1, i1, i1
// CHECK-NEXT:    %m3, %m4 = stim.measure Z (%q0, %q1) -> i1, i1
// CHECK-NEXT:    %m5, %m7 = stim.measure X <0.1> (%q0, %q2) -> i1, i1
// CHECK-NEXT:    %m6 = stim.measure Z <0.1> (%q1) -> i1
// CHECK-NEXT:    %m8 = stim.mpp[X, Z, X] <0.2> (%q0, %q1, %q2) -> i1
// CHECK-NEXT:    %m9 = stim.mpp[Y, X] <0.3> (%q1, %q2) -> i1
// CHECK-NEXT:    %m10 = stim.mpp[Y, X] <0.3> (%q0, %q3) -> i1
// CHECK-NEXT:  }

// ----
// CHECK: ----

// Gate + reset

builtin.module {
  %q0, %q1 = qcore.alloc_qubit<coords=[(0, 0), (1, 1)]> -> !qcore.qubit, !qcore.qubit
  %0, %1 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
  ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit):
    qref.reset<X>(%q0_1, %q1_1)
    qref.gate<#qcore.gate.h> (%q0_1, %q1_1)
    qref.gate<#qcore.gate.cx> (%q0_1, %q1_1)
    qstruct.yield %q0_1, %q1_1 : !qcore.qubit, !qcore.qubit
  }
}

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   %q0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:   %q1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:   stim.assign_qubit_coord <0.0, 0.0> (%q0 : !stim.qubit)
// CHECK-NEXT:   stim.assign_qubit_coord <1.0, 1.0> (%q1 : !stim.qubit)
// CHECK-NEXT:   stim.reset X (%q0, %q1)
// CHECK-NEXT:   stim.clifford H (%q0, %q1)
// CHECK-NEXT:   stim.clifford CNOT (%q0, %q1)
// CHECK-NEXT: }


// ----
// CHECK: ----

// Gate + reset + measure

builtin.module {
  %q0, %q1 = qcore.alloc_qubit<coords=[(0, 0), (1, 1)]> -> !qcore.qubit, !qcore.qubit
  %0, %1, %2, %3 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, i1, i1 {
  ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit):
    qref.reset<X>(%q0_1, %q1_1)
    qref.gate<#qcore.gate.h> (%q0_1, %q1_1)
    qref.gate<#qcore.gate.cx> (%q0_1, %q1_1)
    %m0, %m1 = qref.measure<Z>(%q0_1, %q1_1) -> i1, i1
    qstruct.yield %q0_1, %q1_1, %m0, %m1 : !qcore.qubit, !qcore.qubit, i1, i1
  }
}


// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   %q0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:   %q1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:   stim.assign_qubit_coord <0.0, 0.0> (%q0 : !stim.qubit)
// CHECK-NEXT:   stim.assign_qubit_coord <1.0, 1.0> (%q1 : !stim.qubit)
// CHECK-NEXT:   stim.reset X (%q0, %q1)
// CHECK-NEXT:   stim.clifford H (%q0, %q1)
// CHECK-NEXT:   stim.clifford CNOT (%q0, %q1)
// CHECK-NEXT:   %m0, %m1 = stim.measure Z (%q0, %q1) -> i1, i1
// CHECK-NEXT: }

// ----
// CHECK: ----

// Gate + reset + measure + noise

builtin.module {
  %q0, %q1, %q2 = qcore.alloc_qubit<coords=[(0, 0), (1, 1), (2, 2)]> -> !qcore.qubit, !qcore.qubit, !qcore.qubit
  %0, %1, %2, %3, %4 = qstruct.circuit(%q0, %q1, %q2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1 {
  ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit, %q2_1: !qcore.qubit):
    qref.reset<X>(%q0_1, %q1_1, %q2_1)
    qref.gate<#qcore.gate.h> (%q0_1, %q1_1, %q2_1)
    qref.pauli_noise<X=0.01, Y = 0.02, Z=0.03> (%q0_1, %q1_1)
    qref.pauli_noise<X=0.01, Y = 0.01, Z=0.01> (%q1_1, %q2_1)
    qref.pauli_noise<IZ=0.1, XI = 0.2, YI=0.3> (%q0_1, %q1_1)
    qref.gate<#qcore.gate.cx> (%q0_1, %q1_1)
    %m0, %m1 = qref.measure<[Z,Z]>(%q0_1, %q1_1) -> i1, i1
    qstruct.yield %q0_1, %q1_1, %q2_1, %m0, %m1 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1
  }
}


// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   %q0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:   %q1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:   %q2 = stim.qubit_alloc 2 -> !stim.qubit
// CHECK-NEXT:   stim.assign_qubit_coord <0.0, 0.0> (%q0 : !stim.qubit)
// CHECK-NEXT:   stim.assign_qubit_coord <1.0, 1.0> (%q1 : !stim.qubit)
// CHECK-NEXT:   stim.assign_qubit_coord <2.0, 2.0> (%q2 : !stim.qubit)
// CHECK-NEXT:   stim.reset X (%q0, %q1, %q2)
// CHECK-NEXT:   stim.clifford H (%q0, %q1, %q2)
// CHECK-NEXT:   stim.pauli_channel_1 <0.01, 0.02, 0.03> (%q0, %q1)
// CHECK-NEXT:   stim.depolarize1 <0.03> (%q1, %q2)
// CHECK-NEXT:   stim.pauli_channel_2 <0.0, 0.0, 0.1, 0.2, 0.0, 0.0, 0.0, 0.3, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0> (%q0, %q1)
// CHECK-NEXT:   stim.clifford CNOT (%q0, %q1)
// CHECK-NEXT:   %m0, %m1 = stim.measure Z (%q0, %q1) -> i1, i1
// CHECK-NEXT: }

// ----
// CHECK: ----

// 2 channel noise

builtin.module {
  %q0, %q1, %q2 = qcore.alloc_qubit<coords=[(0, 0), (1, 1), (2, 2)]> -> !qcore.qubit, !qcore.qubit, !qcore.qubit
  %0, %1, %2, %3, %4 = qstruct.circuit(%q0, %q1, %q2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1 {
  ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit, %q2_1: !qcore.qubit):
    qref.reset<X>(%q0_1, %q1_1, %q2_1)
    qref.gate<#qcore.gate.h> (%q0_1, %q1_1, %q2_1)
    qref.pauli_noise<IX=0.01, IY=0.01, IZ=0.01, XI=0.01, XX=0.01, XY=0.01, XZ=0.01, YI=0.01, YX=0.01, YY=0.01, YZ=0.01, ZI=0.01, ZX=0.01, ZY=0.01, ZZ=0.01> (%q0_1, %q1_1)
    qref.gate<#qcore.gate.cx> (%q0_1, %q1_1)
    %m0, %m1, %m2 = qref.measure<[X,Z,X], 0.1>(%q0_1, %q1_1, %q2_1) -> i1, i1, i1
    qstruct.yield %q0_1, %q1_1, %q2_1, %m0, %m1 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1
  }
}

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   %q0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:   %q1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:   %q2 = stim.qubit_alloc 2 -> !stim.qubit
// CHECK-NEXT:   stim.assign_qubit_coord <0.0, 0.0> (%q0 : !stim.qubit)
// CHECK-NEXT:   stim.assign_qubit_coord <1.0, 1.0> (%q1 : !stim.qubit)
// CHECK-NEXT:   stim.assign_qubit_coord <2.0, 2.0> (%q2 : !stim.qubit)
// CHECK-NEXT:   stim.reset X (%q0, %q1, %q2)
// CHECK-NEXT:   stim.clifford H (%q0, %q1, %q2)
// CHECK-NEXT:   stim.depolarize2 <0.15> (%q0, %q1)
// CHECK-NEXT:   stim.clifford CNOT (%q0, %q1)
// CHECK-NEXT:   %m0, %m2 = stim.measure X <0.1> (%q0, %q2) -> i1, i1
// CHECK-NEXT:   %m1 = stim.measure Z <0.1> (%q1) -> i1
// CHECK-NEXT: }

// ----
// CHECK: ----

// Multi-pauli measure

builtin.module {
  %q0, %q1, %q2 = qcore.alloc_qubit<coords=[(0, 0), (1, 1), (2, 2)]> -> !qcore.qubit, !qcore.qubit, !qcore.qubit
  %0, %1, %2, %3 = qstruct.circuit(%q0, %q1, %q2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1 {
  ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit, %q2_1: !qcore.qubit):
    qref.reset<X>(%q0_1, %q1_1, %q2_1)
    qref.gate<#qcore.gate.h> (%q0_1, %q1_1, %q2_1)
    qref.pauli_noise<IZX=0.1, XIX = 0.2, YIX=0.3> (%q0_1, %q1_1, %q2_1)
    qref.gate<#qcore.gate.cx> (%q0_1, %q1_1)
    %m0 = qref.measure<XZX, 0.2>(%q0_1, %q1_1, %q2_1) -> i1
    qstruct.yield %q0_1, %q1_1, %q2_1, %m0 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1
  }
}

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   %q0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:   %q1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:   %q2 = stim.qubit_alloc 2 -> !stim.qubit
// CHECK-NEXT:   stim.assign_qubit_coord <0.0, 0.0> (%q0 : !stim.qubit)
// CHECK-NEXT:   stim.assign_qubit_coord <1.0, 1.0> (%q1 : !stim.qubit)
// CHECK-NEXT:   stim.assign_qubit_coord <2.0, 2.0> (%q2 : !stim.qubit)
// CHECK-NEXT:   stim.reset X (%q0, %q1, %q2)
// CHECK-NEXT:   stim.clifford H (%q0, %q1, %q2)
// CHECK-NEXT:   stim.correlated_error <0.1> [Z, X] (%q1, %q2)
// CHECK-NEXT:   stim.else_correlated_error <0.22222222222222224> [X, X] (%q0, %q2)
// CHECK-NEXT:   stim.else_correlated_error <0.4285714285714286> [Y, X] (%q0, %q2)
// CHECK-NEXT:   stim.clifford CNOT (%q0, %q1)
// CHECK-NEXT:   %m0 = stim.mpp[X, Z, X] <0.2> (%q0, %q1, %q2) -> i1
// CHECK-NEXT: }

// ----
// CHECK: ----

builtin.module{
  %q0, %q1, %q2 = qcore.alloc_qubit<coords=[(0, 0), (1, 1), (2, 2)]> -> !qcore.qubit, !qcore.qubit, !qcore.qubit

// CHECK:         builtin.module {
// CHECK-NEXT:      %q0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:      %q1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:      %q2 = stim.qubit_alloc 2 -> !stim.qubit
// CHECK-NEXT:      stim.assign_qubit_coord <0.0, 0.0> (%q0 : !stim.qubit)
// CHECK-NEXT:      stim.assign_qubit_coord <1.0, 1.0> (%q1 : !stim.qubit)
// CHECK-NEXT:      stim.assign_qubit_coord <2.0, 2.0> (%q2 : !stim.qubit)

  %q00, %q11, %q22, %obs_2, %obs_3, %obs_4 = qstruct.circuit(%q0, %q1, %q2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qec.observable, !qec.observable, !qec.observable {
  ^bb(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit, %q2_1: !qcore.qubit):
      %m0, %m1 = qref.measure<Z>(%q0_1, %q1_1) -> i1, i1
      %d0 = qec.detector(%m0, %m1)
      %obs1 = qec.dec_observable {stim.obs_id = #builtin.int<1>} -> !qec.observable
      %obs2 = qec.dec_observable -> !qec.observable
      %obs3 = qec.dec_observable {stim.obs_id = #builtin.int<0>} -> !qec.observable
      %obs_3 = qec.observable_include(%obs3) using (%m0) -> !qec.observable

// CHECK-NEXT:      %m0, %m1 = stim.measure Z (%q0, %q1) -> i1, i1
// CHECK-NEXT:      stim.detector <[0.0]> (%m0, %m1 : i1, i1)
// CHECK-NEXT:      stim.observable_include <0> (%m0 : i1)

      %m2_1, %m3_1, %new_obs, %d1 = qstruct.repeat<5>(%m0, %m1, %obs1, %d0: i1, i1, !qec.observable, !qec.detector_ref) -> i1, i1, !qec.observable, !qec.detector_ref {
      ^bb0(%m0_1 : i1, %m1_1 : i1, %obs_arg : !qec.observable, %detector_arg : !qec.detector_ref):
          %m2, %m3 = qref.measure<Z>(%q0_1, %q1_1) -> i1, i1
          %obs_1 = qec.observable_include(%obs_arg) using (%m2) -> !qec.observable
          %obs_2 = qec.observable_include(%obs2) using (%m3) -> !qec.observable
          %d0_0 = qec.detector(%m0_1, %m2)
          %d1_0 = qec.detector(%m3, %m1_1)
          qec.detector_round(%d0_0, %detector_arg)
          qstruct.yield %m2, %m3, %obs_1, %d1_0 : i1, i1, !qec.observable, !qec.detector_ref
      }

// CHECK-NEXT:      %m2, %m3 = stim.repeat 5 (%m0, %m1 : i1, i1) -> i1, i1 {
// CHECK-NEXT:      ^bb0(%m0_1: i1, %m1_1: i1):
// CHECK-NEXT:        %m2_1, %m3_1 = stim.measure Z (%q0, %q1) -> i1, i1
// CHECK-NEXT:        stim.observable_include <1> (%m2_1 : i1)
// CHECK-NEXT:        stim.observable_include <2> (%m3_1 : i1)
// CHECK-NEXT:        stim.detector <[0.0]> (%m0_1, %m2_1 : i1, i1)
// CHECK-NEXT:        stim.detector <[1.0]> (%m3_1, %m1_1 : i1, i1)
// CHECK-NEXT:        stim.shift_coord <[1.0]>
// CHECK-NEXT:        stim.yield %m2_1, %m3_1 : i1, i1
// CHECK-NEXT:      }

      %m4, %m5 = qref.measure<Z>(%q0_1, %q1_1) -> i1, i1
      %d2 = qec.detector(%m2_1, %m4)
      %d3 = qec.detector(%m3_1, %m5)
      qec.detector_round(%d2, %d3, %d1)

      qstruct.yield %q0_1, %q1_1, %q2_1, %new_obs, %obs2, %obs3: !qcore.qubit, !qcore.qubit, !qcore.qubit, !qec.observable, !qec.observable, !qec.observable
  }

// CHECK-NEXT:      %m4, %m5 = stim.measure Z (%q0, %q1) -> i1, i1
// CHECK-NEXT:      stim.detector <[0.0]> (%m2, %m4 : i1, i1)
// CHECK-NEXT:      stim.detector <[0.0]> (%m3, %m5 : i1, i1)
// CHECK-NEXT:    }

  %corr1 = qec.get_correction(%obs_2: !qec.observable) -> i1
  %c0 = arith.constant 0 : i1
  %neg_corr = arith.xori %corr1, %c0 : i1
  %corr2 = qec.get_correction(%obs_3: !qec.observable) -> i1
  %corr3 = qec.get_correction(%obs_4: !qec.observable) -> i1
  qstruct.output(%neg_corr, %corr2, %corr3 : i1, i1, i1)
}


// ----
// CHECK: ----

builtin.module{
  %q1 = qcore.alloc_qubit<coords=[(0, 0)]> -> !qcore.qubit
  %0 = qstruct.circuit(%q1 : !qcore.qubit) -> !qcore.qubit {
  ^bb(%q1_1: !qcore.qubit):
      %m0 = qref.measure<Z>(%q1_1) -> i1
      %d1 = qec.detector(%m0)
      %d2 = qstruct.repeat<5>(%d1: !qec.detector_ref) -> !qec.detector_ref {
      ^bb0(%d1_1: !qec.detector_ref):
          %d3 = qstruct.repeat<5>(%d1_1: !qec.detector_ref) -> !qec.detector_ref {
          ^bb00(%d1_2: !qec.detector_ref):
              qstruct.yield %d1_2 : !qec.detector_ref
          }
          qstruct.yield %d3 : !qec.detector_ref
      }
      qec.detector_round(%d2)
      qstruct.yield %q1_1 : !qcore.qubit
  }

}

// CHECK-NEXT:    builtin.module {
// CHECK-NEXT:      %q1 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:      stim.assign_qubit_coord <0.0, 0.0> (%q1 : !stim.qubit)
// CHECK-NEXT:      %m0 = stim.measure Z (%q1) -> i1
// CHECK-NEXT:      stim.detector <[0.0]> (%m0 : i1)
// CHECK-NEXT:    }

// ----
// CHECK: ----

builtin.module{
  %q1, %q2 = qcore.alloc_qubit<> -> !qcore.qubit, !qcore.qubit
  %0, %1 = qstruct.circuit(%q1, %q2 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
  ^bb(%q1_1: !qcore.qubit, %q2_1: !qcore.qubit):
      %q5_1, %q6_1 = qstruct.repeat<2>(%q1_1, %q2_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
      ^bb0(%q1_2: !qcore.qubit, %q2_2: !qcore.qubit):
        %q3_1, %q4_1 = qstruct.repeat<2>(%q1_2, %q2_2 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
            ^bb0(%q1_3: !qcore.qubit, %q2_3: !qcore.qubit):
                qref.gate<#qcore.gate.h> (%q3_1, %q4_1)
                qstruct.yield %q1_3, %q2_3 : !qcore.qubit, !qcore.qubit
            }
          qstruct.yield %q3_1, %q4_1 : !qcore.qubit, !qcore.qubit
      }
      qstruct.yield %q5_1, %q6_1 : !qcore.qubit, !qcore.qubit
  }
}

// CHECK-NEXT:    builtin.module {
// CHECK-NEXT:      %q1 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:      %q2 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:      stim.repeat 2 () {
// CHECK-NEXT:        stim.repeat 2 () {
// CHECK-NEXT:          stim.clifford H (%q1, %q2)
// CHECK-NEXT:          stim.yield
// CHECK-NEXT:        }
// CHECK-NEXT:        stim.yield
// CHECK-NEXT:      }
// CHECK-NEXT:    }

// ----
// CHECK: ----

// How to verify the the correctness of detector rounds? Take the detector SSAValue and propagate it
// through repeats until you hit a detector round op (note for repeats there will be multiple paths).
// The final number is the round number attribute assigned plus the number of detector
// round ops you have passed through accounting for multiple iterations of repeats and excluding
// the current detector round op.

// Comments have been added to show how this work for some detectors. Not all paths are shown.


// 2 repeats sequentially


builtin.module {
// CHECK-NEXT: builtin.module {
  qstruct.circuit -> {
    qec.detector_round() {pos = "A"} // detector round 0
    %0 = qec.detector<[0.0, 0.0]> () // %29 -> %28 -> %26 -> C -> 6th rounnd
    %1 = qec.detector<[0.0, 0.0]> () // %26 -> C -> 2nd round
    %2 = qec.detector<[0.0, 0.0]> () // %25 -> C -> 2nd round

// CHECK-NEXT:    stim.detector <[0.0, 0.0, 6.0]> (:)
// CHECK-NEXT:    stim.detector <[0.0, 0.0, 2.0]> (:)
// CHECK-NEXT:    stim.detector <[0.0, 0.0, 2.0]> (:)

    %3 = qec.detector() // %28 -> %25 -> C- > 4th round
    %4 = qec.detector() // %27 -> %22 -> B -> 3rd round
    %5 = qec.detector() // %24 -> C -> 2nd round
    %6 = qec.detector() // %23 -> B -> 1st round
    %7 = qec.detector() // %22 -> B -> 1st round

// CHECK-NEXT:  stim.detector <[4.0]> (:)
// CHECK-NEXT:  stim.detector <[3.0]> (:)
// CHECK-NEXT:  stim.detector <[2.0]> (:)
// CHECK-NEXT:  stim.detector <[1.0]> (:)
// CHECK-NEXT:  stim.detector <[1.0]> (:)


    %12, %13, %14, %15, %16, %17, %18, %19 = qstruct.repeat<3> (%7, %6, %5, %2, %1, %4, %3, %0 : !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref) -> !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref {
    ^bb0(%22: !qec.detector_ref, %23: !qec.detector_ref, %24: !qec.detector_ref, %25: !qec.detector_ref, %26: !qec.detector_ref, %27: !qec.detector_ref, %28: !qec.detector_ref, %29: !qec.detector_ref):
      %31 = qec.detector<[0.0, 0.0]> () // C -> 2nd round
      %32 = qec.detector<[0.0, 0.0]> () // B -> 1st round
      %33 = qec.detector<[0.0, 0.0]> () // %23 -> B-> 3rd round
                                        // %13 ->  %52 -> D -> 3rd round
      %34 = qec.detector<[0.0, 0.0]> () // %27-> %22 -> B -> 5th round
                                        // %17 -> %56 -> %55 -> %51 -> D -> 5th round
      %35 = qec.detector<[0.0, 0.0]> () // %26 -> C -> 4th round
                                        // .....
      qec.detector_round(%22, %23, %32) {pos = "B"} // detector round 1
      qec.detector_round(%24, %25, %26, %31) {pos = "C"} // detector round 2

      %36 = qec.detector() // %24 -> C -> 4th round
      %37 = qec.detector() // %29 -> %28 -> %25 -> C -> 8th round

      qstruct.yield %27, %33, %36, %28, %35, %34, %29, %37 : !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref
    }

// CHECK-NEXT:  stim.repeat 3 () {
// CHECK-NEXT:    stim.detector <[0.0, 0.0, 2.0]> (:)
// CHECK-NEXT:    stim.detector <[0.0, 0.0, 1.0]> (:)
// CHECK-NEXT:    stim.detector <[0.0, 0.0, 3.0]> (:)
// CHECK-NEXT:    stim.detector <[0.0, 0.0, 5.0]> (:)
// CHECK-NEXT:    stim.detector <[0.0, 0.0, 4.0]> (:)
// CHECK-NEXT:    stim.detector <[4.0]> (:)
// CHECK-NEXT:    stim.detector <[8.0]> (:)
// CHECK-NEXT:    stim.shift_coord <[0.0, 0.0, 2.0]>
// CHECK-NEXT:    stim.yield
// CHECK-NEXT:  }

    %38 = qec.detector() // %54 -> %50 -> 2nd round
    %39 = qec.detector() // %51 -> 1st round
    %40 = qec.detector() // %50 -> 1st round

// CHECK-NEXT:  stim.detector <[2.0]> (:)
// CHECK-NEXT:  stim.detector <[1.0]> (:)
// CHECK-NEXT:  stim.detector <[1.0]> (:)

    // %14, %15, %18, %19 are guaranteed to be empty detectors - they are not passed in

    %43, %44, %45, %46, %47, %48, %49 = qstruct.repeat<2> (%40, %39, %13, %12, %38, %16, %17 : !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref) -> !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref {
    ^bb1(%50: !qec.detector_ref, %51: !qec.detector_ref, %52: !qec.detector_ref, %53: !qec.detector_ref, %54: !qec.detector_ref, %55: !qec.detector_ref, %56: !qec.detector_ref):
      %57 = qec.detector<[0.0, 0.0]> () // D -> 1st round
      %58 = qec.detector<[0.0, 0.0]> () // %52 -> D -> 2nd round
                                        // %45 -> E -> 2nd round
      %59 = qec.detector<[0.0, 0.0]> () // %53 -> D -> 2nd round
                                        // %46 -> E -> 2nd round
      qec.detector_round(%50, %51, %52, %53, %57) {pos = "D"} // detector round 1

      %60 = qec.detector() // %54 -> %50 -> D -> 3rd round
      %61 = qec.detector() // %56 -> %55 -> %51 -> D -> 4th round

      qstruct.yield %54, %55, %58, %59, %60, %56, %61 : !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref
    }
    // all other detectors from the repeat are guaranteed to be empty - not assigned to detector rounds
    qec.detector_round(%45, %46) {pos = "E"} // detector round 1
    qstruct.yield

// CHECK-NEXT:  stim.repeat 2 () {
// CHECK-NEXT:    stim.detector <[0.0, 0.0, 1.0]> (:)
// CHECK-NEXT:    stim.detector <[0.0, 0.0, 2.0]> (:)
// CHECK-NEXT:    stim.detector <[0.0, 0.0, 2.0]> (:)
// CHECK-NEXT:    stim.detector <[3.0]> (:)
// CHECK-NEXT:    stim.detector <[4.0]> (:)
// CHECK-NEXT:    stim.shift_coord <[0.0, 0.0, 1.0]>
// CHECK-NEXT:    stim.yield
// CHECK-NEXT:  }

  }
}

// CHECK-NEXT:  }

// ----
// CHECK: ----

// Nested repeat

builtin.module {
// CHECK-NEXT:  builtin.module {
  qstruct.circuit -> {
    %0 = qec.detector<[0.0, 0.0]> () // 0th round
    qec.detector_round(%0) {pos = "A"}

// CHECK-NEXT:    stim.detector <[0.0, 0.0, 0.0]> (:)

    qec.detector_round() {pos = "B"} // 1st round
    %1 = qec.detector<[0.0, 0.0]> () // %5 -> %12 -> 2nd round
    %2 = qec.detector()

// CHECK-NEXT:    stim.detector <[0.0, 0.0, 2.0]> (:)
// CHECK-NEXT:    stim.detector <[3.0]> (:)

    %3, %4 = qstruct.repeat<3> (%1, %2 : !qec.detector_ref, !qec.detector_ref) -> !qec.detector_ref, !qec.detector_ref {
    ^bb0(%5: !qec.detector_ref, %6: !qec.detector_ref):
      %7 = qec.detector()

// CHECK-NEXT:    stim.repeat 3 () {
// CHECK-NEXT:      stim.detector <[2.0]> (:)

      %8, %9, %10 = qstruct.repeat<2> (%7, %5, %6 : !qec.detector_ref, !qec.detector_ref, !qec.detector_ref) -> !qec.detector_ref, !qec.detector_ref, !qec.detector_ref {
      ^bb1(%11: !qec.detector_ref, %12: !qec.detector_ref, %13: !qec.detector_ref):
        %14 = qec.detector<[0.0, 0.0]> ()
        %15 = qec.detector<[0.0, 0.0]> () // %13 -> %12 -> C -> 4th round
                                          //        %9  -> D
                                          // %10 -> %5  -> %12 -> C
                                          //     -> %3  -> E
        qec.detector_round(%11, %12, %14) {pos = "C"} // 2nd round
        %16 = qec.detector()
        qstruct.yield %16, %13, %15 : !qec.detector_ref, !qec.detector_ref, !qec.detector_ref
      }

// CHECK-NEXT:      stim.repeat 2 () {
// CHECK-NEXT:        stim.detector <[0.0, 0.0, 2.0]> (:)
// CHECK-NEXT:        stim.detector <[0.0, 0.0, 4.0]> (:)
// CHECK-NEXT:        stim.detector <[3.0]> (:)
// CHECK-NEXT:        stim.shift_coord <[0.0, 0.0, 1.0]>
// CHECK-NEXT:        stim.yield
// CHECK-NEXT:      }

      %17 = qec.detector<[0.0, 0.0]> ()
      %18 = qec.detector<[0.0, 0.0]> () // D
                                        // %6  -> % 13 ....

      qec.detector_round(%9, %17) {pos = "D"} // 2nd round
      qstruct.yield %10, %18 : !qec.detector_ref, !qec.detector_ref
    }

// CHECK-NEXT:      stim.detector <[0.0, 0.0, 2.0]> (:)
// CHECK-NEXT:      stim.detector <[0.0, 0.0, 4.0]> (:)
// CHECK-NEXT:      stim.shift_coord <[0.0, 0.0, 1.0]>
// CHECK-NEXT:      stim.yield
// CHECK-NEXT:    }

    qec.detector_round(%3) {pos = "E"} // 2nd round
    qec.detector_round(%4) {pos = "F"} // 3rd round
    qstruct.yield

  }
}

// CHECK-NEXT:  }

// ----
// CHECK: ----

// stim.tag preservation: tags on gate, reset, measure, noise, detector, observable include

builtin.module {
  %q0, %q1, %q2 = qcore.alloc_qubit<coords=[(0, 0), (1, 1), (2, 2)]> -> !qcore.qubit, !qcore.qubit, !qcore.qubit
  %0, %1, %2, %3 = qstruct.circuit(%q0, %q1, %q2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qec.observable {
  ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit, %q2_1: !qcore.qubit):
    %obs = qec.dec_observable -> !qec.observable
    qref.reset<Z>(%q0_1, %q1_1, %q2_1) {stim.tag = "reset-tag"}
    qref.gate<#qcore.gate.h> (%q0_1, %q1_1) {stim.tag = "h-gate-tag"}
    qref.pauli_noise<X=0.01, Y=0.01, Z=0.01> (%q0_1, %q1_1) {stim.tag = "noise-tag"}
    qref.gate<#qcore.gate.cx> (%q0_1, %q2_1) {stim.tag = "cx-gate-tag"}
    %m0, %m1 = qref.measure<Z>(%q0_1, %q1_1) {stim.tag = "measure-tag"} -> i1, i1
    %d0 = qec.detector(%m0, %m1) {stim.tag = "detector-tag"}
    qec.detector_round(%d0)
    %obs_1 = qec.observable_include(%obs) using (%m1) {stim.tag = "obs-include-tag"} -> !qec.observable
    qstruct.yield %q0_1, %q1_1, %q2_1, %obs_1 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qec.observable
  }
  %corr = qec.get_correction(%3 : !qec.observable) -> i1
  qstruct.output(%corr : i1)
}

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   %q0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:   %q1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:   %q2 = stim.qubit_alloc 2 -> !stim.qubit
// CHECK-NEXT:   stim.assign_qubit_coord <0.0, 0.0> (%q0 : !stim.qubit)
// CHECK-NEXT:   stim.assign_qubit_coord <1.0, 1.0> (%q1 : !stim.qubit)
// CHECK-NEXT:   stim.assign_qubit_coord <2.0, 2.0> (%q2 : !stim.qubit)
// CHECK-NEXT:   stim.reset Z (%q0, %q1, %q2) {stim.tag = "reset-tag"}
// CHECK-NEXT:   stim.clifford H (%q0, %q1) {stim.tag = "h-gate-tag"}
// CHECK-NEXT:   stim.depolarize1 <0.03> (%q0, %q1) {stim.tag = "noise-tag"}
// CHECK-NEXT:   stim.clifford CNOT (%q0, %q2) {stim.tag = "cx-gate-tag"}
// CHECK-NEXT:   %m0, %m1 = stim.measure Z (%q0, %q1) {stim.tag = "measure-tag"} -> i1, i1
// CHECK-NEXT:   stim.detector <[0.0]> (%m0, %m1 : i1, i1) {stim.tag = "detector-tag"}
// CHECK-NEXT:   stim.observable_include <0> (%m1 : i1) {stim.tag = "obs-include-tag"}
// CHECK-NEXT: }
