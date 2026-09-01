// RUN: ROUNDTRIP_MLIR

builtin.module {
    %i0, %i1, %i2, %i3, %i4, %i5, %i6, %i7 = "test.op" () : () -> (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit)
    %o0, %o1, %o2, %o3, %o4, %o5, %o6, %o7 = qstruct.circuit
    (%i0, %i1, %i2, %i3, %i4, %i5, %i6, %i7 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) ->
    !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
    ^bb0(%0 : !qcore.qubit, %1 : !qcore.qubit, %2 : !qcore.qubit, %3 : !qcore.qubit, %4 : !qcore.qubit, %5 : !qcore.qubit, %6 : !qcore.qubit, %7 : !qcore.qubit):

        qref.reset<X>   (%0, %1, %2, %3) {john = "John"}
        qref.reset<Y> (%4, %5, %6)
        qref.reset<Z>(%7)

// CHECK:       qref.reset<X> (%0, %1, %2, %3) {john = "John"}
// CHECK-NEXT:  qref.reset<Y> (%4, %5, %6)
// CHECK-NEXT:  qref.reset<Z> (%7)


        %b0_0_, %b0_1_, %b0_2_, %b0_3_ = qref.measure<X>   (%0, %1, %2, %3) {chicken = "Chicken"} -> i1, i1, i1, i1
        %b1_0_, %b1_1_, %b1_2_ = qref.measure<Y> (%4, %5, %6) -> i1, i1, i1
        %b2_0_ = qref.measure<Z>(%7) -> i1

// CHECK-NEXT:  %b0_0_, %b0_1_, %b0_2_, %b0_3_ = qref.measure<X> (%0, %1, %2, %3) {chicken = "Chicken"} -> i1, i1, i1, i1
// CHECK-NEXT:  %b1_0_, %b1_1_, %b1_2_ = qref.measure<Y> (%4, %5, %6) -> i1, i1, i1
// CHECK-NEXT:  %b2_0_ = qref.measure<Z> (%7) -> i1

        %b3_0_, %b3_1_ = qref.measure<XX>(%0, %1, %2, %3) {mark = "Mark"} -> i1, i1
        %b4_0_ = qref.measure<YYY> (%4, %5, %6) -> i1

// CHECK-NEXT:  %b3_0_, %b3_1_ = qref.measure<XX> (%0, %1, %2, %3) {mark = "Mark"} -> i1, i1
// CHECK-NEXT:  %b4_0_ = qref.measure<YYY> (%4, %5, %6) -> i1

        %b5_0_, %b5_1_ = qref.measure<[XX, XX]>(%0, %1, %2, %3) -> i1, i1
        %b6_0_, %b6_1_ = qref.measure<[YYY, YYY]> (%4, %5, %6, %0, %1, %2) -> i1, i1
        %b7_0_, %b7_1_, %b7_2_, %b7_3_, %b7_4_, %b7_5_, %b7_6_ = qref.measure<[X,X,X,  X, X, X,  X]>   (%0, %1, %2, %3, %4, %5, %6) -> i1, i1, i1, i1, i1, i1, i1

// CHECK-NEXT:  %b5_0_, %b5_1_ = qref.measure<XX> (%0, %1, %2, %3) -> i1, i1
// CHECK-NEXT:  %b6_0_, %b6_1_ = qref.measure<YYY> (%4, %5, %6, %0, %1, %2) -> i1, i1
// CHECK-NEXT:  %b7_0_, %b7_1_, %b7_2_, %b7_3_, %b7_4_, %b7_5_, %b7_6_ = qref.measure<X> (%0, %1, %2, %3, %4, %5, %6) -> i1, i1, i1, i1, i1, i1, i1

        %b8_0_, %b8_1_ = qref.measure<[XX, ZZ]>(%0, %1, %2, %3) -> i1, i1
        %b9_0_, %b9_1_ = qref.measure<[YYX, ZYY]> (%4, %5, %6, %0, %1, %2) -> i1, i1
        %b10_0_, %b10_1_, %b10_2_, %b10_3_, %b10_4_, %b10_5_, %b10_6_ = qref.measure<[X,X,X,  X, Z, X,  X]>   (%0, %1, %2, %3, %4, %5, %6) -> i1, i1, i1, i1, i1, i1, i1

// CHECK-NEXT:  %b8_0_, %b8_1_ = qref.measure<[XX, ZZ]> (%0, %1, %2, %3) -> i1, i1
// CHECK-NEXT:  %b9_0_, %b9_1_ = qref.measure<[YYX, ZYY]> (%4, %5, %6, %0, %1, %2) -> i1, i1
// CHECK-NEXT:  %b10_0_, %b10_1_, %b10_2_, %b10_3_, %b10_4_, %b10_5_, %b10_6_ = qref.measure<[X, X, X, X, Z, X, X]> (%0, %1, %2, %3, %4, %5, %6) -> i1, i1, i1, i1, i1, i1, i1


        qref.gate<#qcore.gate.x> (%0, %1, %2, %3) {sleep = "NO"}
        qref.gate<#qcore.gate.iswap<dag>> (%4, %5, %6, %7)
        qref.gate<#qcore.gate.swap<>> (%7, %0)
        qref.gate<#qcore.gate.unitary<
            [
                [(1,0), (0,0), (0,0), (0,0),  (0,0), (0,0), (0,0), (0,0)],
                [(0,0), (1,0), (0,0), (0,0),  (0,0), (0,0), (0,0), (0,0)],
                [(0,0), (0,0), (1,0), (0,0),  (0,0), (0,0), (0,0), (0,0)],
                [(0,0), (0,0), (0,0), (1,0),  (0,0), (0,0), (0,0), (0,0)],
                [(0,0), (0,0), (0,0), (0,0),  (1,0), (0,0), (0,0), (0,0)],
                [(0,0), (0,0), (0,0), (0,0),  (0,0), (1,0), (0,0), (0,0)],
                [(0,0), (0,0), (0,0), (0,0),  (0,0), (0,0), (1,0), (0,0)],
                [(0,0), (0,0), (0,0), (0,0),  (0,0), (0,0), (0,0), (1,0)]
            ]
        >> (%7, %0, %1)
        qref.gate<#qcore.gate.unitary<
            [
                [(1,0), (0,0), (0,0), (0,0),  (0,0), (0,0), (0,0), (0,0)],
                [(0,0), (1,0), (0,0), (0,0),  (0,0), (0,0), (0,0), (0,0)],
                [(0,0), (0,0), (1,0), (0,0),  (0,0), (0,0), (0,0), (0,0)],
                [(0,0), (0,0), (0,0), (1,0),  (0,0), (0,0), (0,0), (0,0)],
                [(0,0), (0,0), (0,0), (0,0),  (1,0), (0,0), (0,0), (0,0)],
                [(0,0), (0,0), (0,0), (0,0),  (0,0), (1,0), (0,0), (0,0)],
                [(0,0), (0,0), (0,0), (0,0),  (0,0), (0,0), (1,0), (0,0)],
                [(0,0), (0,0), (0,0), (0,0),  (0,0), (0,0), (0,0), (1,0)]
            ]
        >> (%7, %0, %1, %2, %4, %5)

// CHECK:       qref.gate<#qcore.gate.x> (%0, %1, %2, %3) {sleep = "NO"}
// CHECK-NEXT:  qref.gate<#qcore.gate.iswap<dag>> (%4, %5, %6, %7)
// CHECK-NEXT:  qref.gate<#qcore.gate.swap> (%7, %0)
// CHECK-NEXT:  qref.gate<#qcore.gate.unitary<[[
// CHECK-SAME:  ]]>> (%7, %0, %1)
// CHECK-NEXT:  qref.gate<#qcore.gate.unitary<[[
// CHECK-SAME:  ]]>> (%7, %0, %1, %2, %4, %5)

        qref.pauli_noise<IIIIIIII=1>(%0, %1, %2, %3, %4, %5, %6, %7)
        qref.pauli_noise<IIIIIIIX=1>(%0, %1, %2, %3, %4, %5, %6, %7) {Qubits = "Everywhere"}
        qref.pauli_noise<ZZZXYYIX=0.5, ZZZIYYIX=0.25, ZZZXYYIY=0.25>(%0, %1, %2, %3, %4, %5, %6, %7)
// CHECK-NEXT:  qref.pauli_noise<IIIIIIII = 1.0> (%0, %1, %2, %3, %4, %5, %6, %7)
// CHECK-NEXT:  qref.pauli_noise<IIIIIIIX = 1.0> (%0, %1, %2, %3, %4, %5, %6, %7) {Qubits = "Everywhere"}
// CHECK-NEXT:  qref.pauli_noise<ZZZIYYIX = 0.25, ZZZXYYIX = 0.5, ZZZXYYIY = 0.25> (%0, %1, %2, %3, %4, %5, %6, %7)

        qref.pauli_noise<XX = 0.25, YY = 0.25, ZZ = 0.25> (%0, %1, %2, %3, %4, %5, %6, %7)
// CHECK-NEXT:  qref.pauli_noise<XX = 0.25, YY = 0.25, ZZ = 0.25> (%0, %1, %2, %3, %4, %5, %6, %7)
        qref.pauli_noise<II = 0.25, XX = 0.25, YY = 0.25, ZZ = 0.25> (%0, %1, %2, %3)
// CHECK-NEXT:  qref.pauli_noise<XX = 0.25, YY = 0.25, ZZ = 0.25> (%0, %1, %2, %3)
        qref.pauli_noise<IIII = 1.0> (%0, %1, %2, %3)
// CHECK-NEXT:  qref.pauli_noise<IIII = 1.0> (%0, %1, %2, %3)
        qref.pauli_noise<X = 0.2> (%0, %1, %2, %3)
// CHECK-NEXT:  qref.pauli_noise<X = 0.2> (%0, %1, %2, %3)
        qref.pauli_noise<Z = 0.25, Y = 0.25, X = 0.25> (%0, %1, %2, %3)
// CHECK-NEXT:  qref.pauli_noise<X = 0.25, Y = 0.25, Z = 0.25> (%0, %1, %2, %3)

        qstruct.yield %0, %1, %2, %3, %4, %5, %6, %7 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
    }
}
