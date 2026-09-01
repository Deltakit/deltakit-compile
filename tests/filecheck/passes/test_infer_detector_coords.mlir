// RUN: deltakit_compile compile-passes --test-mode %s -p infer-detector-coords -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK:      builtin.module {

    // Test leaves existing detector coordinates alone
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %q1 = qcore.alloc_qubit<coords=[(1.0, 2.0)]> -> !qcore.qubit
    %q0_b, %q1_b = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
    ^bb0(%q0_a: !qcore.qubit, %q1_a: !qcore.qubit):
        %r0 = qref.measure<Z> (%q0_a) -> i1
        %r1 = qref.measure<Z> (%q0_a) -> i1
        qec.detector<[3.0, 4.0, 5.0]> (%r0, %r1)
// CHECK-NEXT:    %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q1 = qcore.alloc_qubit<coords = [(1.0, 2.0)]> -> !qcore.qubit
// CHECK-NEXT:    %q0_b, %q1_b = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q0_a: !qcore.qubit, %q1_a: !qcore.qubit):
// CHECK-NEXT:        %r0 = qref.measure<Z> (%q0_a) -> i1
// CHECK-NEXT:        %r1 = qref.measure<Z> (%q0_a) -> i1
// CHECK-NEXT:        qec.detector<[3.0, 4.0, 5.0]> (%r0, %r1)

        // Test no change if no coordinates are annotated
        qec.detector(%r0, %r1)
// CHECK-NEXT:        qec.detector(%r0, %r1)

        // Test coordinates aren't overwritten if they are annotated
        %r2 = qref.measure<Z> (%q1_a) -> i1
        qec.detector<[6.0, 7.0]> (%r2)
// CHECK-NEXT:        %r2 = qref.measure<Z> (%q1_a) -> i1
// CHECK-NEXT:        qec.detector<[6.0, 7.0]> (%r2)

        qstruct.yield %q0_a, %q1_a : !qcore.qubit, !qcore.qubit
    }
// CHECK-NEXT:        qstruct.yield %q0_a, %q1_a : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }

    // Simple case: one measurement with coord
    %q2 = qcore.alloc_qubit<coords=[(3.0, 4.0)]> -> !qcore.qubit
    %q2_b = qstruct.circuit(%q2 : !qcore.qubit) -> !qcore.qubit {
    ^bb0(%q2_a: !qcore.qubit):
        %r2 = qref.measure<Z> (%q2_a) -> i1
        qec.detector(%r2)
        qstruct.yield %q2_a : !qcore.qubit
    }
// CHECK-NEXT:    %q2 = qcore.alloc_qubit<coords = [(3.0, 4.0)]> -> !qcore.qubit
// CHECK-NEXT:    %q2_b = qstruct.circuit(%q2 : !qcore.qubit) -> !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q2_a: !qcore.qubit):
// CHECK-NEXT:        %r2 = qref.measure<Z> (%q2_a) -> i1
// CHECK-NEXT:        qec.detector<[3.0, 4.0]> (%r2)
// CHECK-NEXT:        qstruct.yield %q2_a : !qcore.qubit
// CHECK-NEXT:    }

    // Two measurements with coords: average coords
    %q1_d, %q2_d = qstruct.circuit(%q1_b, %q2_b : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
    ^bb0(%q1_c: !qcore.qubit, %q2_c: !qcore.qubit):
        %r3 = qref.measure<Z> (%q1_c) -> i1
        %r4 = qref.measure<Z> (%q2_c) -> i1
        qec.detector(%r3, %r4)
        qstruct.yield %q1_c, %q2_c : !qcore.qubit, !qcore.qubit
    }
// CHECK-NEXT:    %q1_d, %q2_d = qstruct.circuit(%q1_b, %q2_b : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q1_c: !qcore.qubit, %q2_c: !qcore.qubit):
// CHECK-NEXT:        %r3 = qref.measure<Z> (%q1_c) -> i1
// CHECK-NEXT:        %r4 = qref.measure<Z> (%q2_c) -> i1
// CHECK-NEXT:        qec.detector<[2.0, 3.0]> (%r3, %r4)
// CHECK-NEXT:        qstruct.yield %q1_c, %q2_c : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }

    // Three measurements, weighted average
    %q1_f, %q2_f = qstruct.circuit(%q1_d, %q2_d : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
    ^bb0(%q1_e: !qcore.qubit, %q2_e: !qcore.qubit):
        %r5 = qref.measure<Z> (%q1_e) -> i1
        %r6 = qref.measure<Z> (%q1_e) -> i1
        %r7 = qref.measure<Z> (%q2_e) -> i1
        qec.detector(%r5, %r6, %r7)
        qstruct.yield %q1_e, %q2_e : !qcore.qubit, !qcore.qubit
    }
// CHECK-NEXT:    %q1_f, %q2_f = qstruct.circuit(%q1_d, %q2_d : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q1_e: !qcore.qubit, %q2_e: !qcore.qubit):
// CHECK-NEXT:        %r5 = qref.measure<Z> (%q1_e) -> i1
// CHECK-NEXT:        %r6 = qref.measure<Z> (%q1_e) -> i1
// CHECK-NEXT:        %r7 = qref.measure<Z> (%q2_e) -> i1
// CHECK-NEXT:        qec.detector<[1.6666666666666667, 2.6666666666666665]> (%r5, %r6, %r7)
// CHECK-NEXT:        qstruct.yield %q1_e, %q2_e : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }

    // Ignore measurements without coords
    %q3 = qcore.alloc_qubit -> !qcore.qubit
    %q1_h, %q2_h, %q3_b = qstruct.circuit(%q1_f, %q2_f, %q3 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
    ^bb0(%q1_g: !qcore.qubit, %q2_g: !qcore.qubit, %q3_a: !qcore.qubit):
        %r8 = qref.measure<Z> (%q1_g) -> i1
        %r9 = qref.measure<Z> (%q2_g) -> i1
        %r10 = qref.measure<Z> (%q3_a) -> i1
        qec.detector(%r8, %r9, %r10)
        qstruct.yield %q1_g, %q2_g, %q3_a : !qcore.qubit, !qcore.qubit, !qcore.qubit
    }
// CHECK-NEXT:    %q3 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q1_h, %q2_h, %q3_b = qstruct.circuit(%q1_f, %q2_f, %q3 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q1_g: !qcore.qubit, %q2_g: !qcore.qubit, %q3_a: !qcore.qubit):
// CHECK-NEXT:        %r8 = qref.measure<Z> (%q1_g) -> i1
// CHECK-NEXT:        %r9 = qref.measure<Z> (%q2_g) -> i1
// CHECK-NEXT:        %r10 = qref.measure<Z> (%q3_a) -> i1
// CHECK-NEXT:        qec.detector<[2.0, 3.0]> (%r8, %r9, %r10)
// CHECK-NEXT:        qstruct.yield %q1_g, %q2_g, %q3_a : !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }

    // Capable of tracing measurements through circuits
    %q2_j, %m0 = qstruct.circuit(%q2_h : !qcore.qubit) -> !qcore.qubit, i1 {
    ^bb0(%q2_i: !qcore.qubit):
        %r11 = qref.measure<Z> (%q2_i) -> i1
        qstruct.yield %q2_i, %r11 : !qcore.qubit, i1
    }
    %q1_j = qstruct.circuit(%q1_h, %m0 : !qcore.qubit, i1) -> !qcore.qubit {
    ^bb0(%q1_i: !qcore.qubit, %m0_in: i1):
        %r12 = qref.measure<Z> (%q1_i) -> i1
        qec.detector(%m0_in)
        qec.detector(%r12, %m0_in)
        qstruct.yield %q1_i : !qcore.qubit
    }
// CHECK-NEXT:    %q2_j, %m0 = qstruct.circuit(%q2_h : !qcore.qubit) -> !qcore.qubit, i1 {
// CHECK-NEXT:    ^bb0(%q2_i: !qcore.qubit):
// CHECK-NEXT:        %r11 = qref.measure<Z> (%q2_i) -> i1
// CHECK-NEXT:        qstruct.yield %q2_i, %r11 : !qcore.qubit, i1
// CHECK-NEXT:    }
// CHECK-NEXT:    %q1_j = qstruct.circuit(%q1_h, %m0 : !qcore.qubit, i1) -> !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q1_i: !qcore.qubit, %m0_in: i1):
// CHECK-NEXT:        %r12 = qref.measure<Z> (%q1_i) -> i1
// CHECK-NEXT:        qec.detector<[3.0, 4.0]> (%m0_in)
// CHECK-NEXT:        qec.detector<[2.0, 3.0]> (%r12, %m0_in)
// CHECK-NEXT:        qstruct.yield %q1_i : !qcore.qubit
// CHECK-NEXT:    }

    // Capable of tracing through registers, packs, unpacks, concatenates, splits
    %reg0, %q4, %q5 = qcore.alloc_qubit<coords=[(0.0, 1.0), (0.0, 2.0), (0.0, 3.0), (0.0, 4.0)]>
        -> !qcore.qubit_reg<2>, !qcore.qubit, !qcore.qubit
    %q6, %q7 = qcore.unpack_qubit_reg(%reg0 : !qcore.qubit_reg<2>)
    %reg1 = qcore.pack_qubit_reg(%q5, %q6) -> !qcore.qubit_reg<2>
    %reg2 = qcore.pack_qubit_reg(%q4, %q7) -> !qcore.qubit_reg<2>
    %reg3 = qcore.concatenate(%reg1, %reg2 : !qcore.qubit_reg<2>, !qcore.qubit_reg<2>) -> !qcore.qubit_reg<4>
    %reg4 = qstruct.circuit(%reg3 : !qcore.qubit_reg<4>) -> !qcore.qubit_reg<4> {
    ^bb0(%reg4_a: !qcore.qubit_reg<4>):
        %reg5, %reg6 = qcore.split(%reg4_a : !qcore.qubit_reg<4>) -> !qcore.qubit_reg<3>, !qcore.qubit_reg<1>
        %q5_a, %q6_a, %q4_a = qcore.unpack_qubit_reg(%reg5 : !qcore.qubit_reg<3>)
        %q7_a = qcore.unpack_qubit_reg(%reg6 : !qcore.qubit_reg<1>)
        %r13 = qref.measure<Z> (%q4_a) -> i1
        %r14 = qref.measure<Z> (%q5_a) -> i1
        %r15 = qref.measure<Z> (%q6_a) -> i1
        %r16 = qref.measure<Z> (%q7_a) -> i1
        qec.detector(%r13)
        qec.detector(%r14)
        qec.detector(%r15)
        qec.detector(%r16)
        %reg7 = qcore.pack_qubit_reg(%q4_a, %q5_a, %q6_a, %q7_a) -> !qcore.qubit_reg<4>
        qstruct.yield %reg7 : !qcore.qubit_reg<4>
    }
// CHECK-NEXT:    %reg0, %q4, %q5 = qcore.alloc_qubit<coords = [(0.0, 1.0), (0.0, 2.0), (0.0, 3.0), (0.0, 4.0)]>
// CHECK-SAME:        -> !qcore.qubit_reg<2>, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    %q6, %q7 = qcore.unpack_qubit_reg(%reg0 : !qcore.qubit_reg<2>)
// CHECK-NEXT:    %reg1 = qcore.pack_qubit_reg(%q5, %q6) -> !qcore.qubit_reg<2>
// CHECK-NEXT:    %reg2 = qcore.pack_qubit_reg(%q4, %q7) -> !qcore.qubit_reg<2>
// CHECK-NEXT:    %reg3 = qcore.concatenate(%reg1, %reg2 : !qcore.qubit_reg<2>, !qcore.qubit_reg<2>) -> !qcore.qubit_reg<4>
// CHECK-NEXT:    %reg4 = qstruct.circuit(%reg3 : !qcore.qubit_reg<4>) -> !qcore.qubit_reg<4> {
// CHECK-NEXT:    ^bb0(%reg4_a: !qcore.qubit_reg<4>):
// CHECK-NEXT:        %reg5, %reg6 = qcore.split(%reg4_a : !qcore.qubit_reg<4>) -> !qcore.qubit_reg<3>, !qcore.qubit_reg<1>
// CHECK-NEXT:        %q5_a, %q6_a, %q4_a = qcore.unpack_qubit_reg(%reg5 : !qcore.qubit_reg<3>)
// CHECK-NEXT:        %q7_a = qcore.unpack_qubit_reg(%reg6 : !qcore.qubit_reg<1>)
// CHECK-NEXT:        %r13 = qref.measure<Z> (%q4_a) -> i1
// CHECK-NEXT:        %r14 = qref.measure<Z> (%q5_a) -> i1
// CHECK-NEXT:        %r15 = qref.measure<Z> (%q6_a) -> i1
// CHECK-NEXT:        %r16 = qref.measure<Z> (%q7_a) -> i1
// CHECK-NEXT:        qec.detector<[0.0, 3.0]> (%r13)
// CHECK-NEXT:        qec.detector<[0.0, 4.0]> (%r14)
// CHECK-NEXT:        qec.detector<[0.0, 1.0]> (%r15)
// CHECK-NEXT:        qec.detector<[0.0, 2.0]> (%r16)
// CHECK-NEXT:        %reg7 = qcore.pack_qubit_reg(%q4_a, %q5_a, %q6_a, %q7_a) -> !qcore.qubit_reg<4>
// CHECK-NEXT:        qstruct.yield %reg7 : !qcore.qubit_reg<4>
// CHECK-NEXT:    }

    // Branching: measurement SSA values having multiple possible qubits is handled by averaging
    // the possible qubit locations, and is weighted as one qubit.
    %b = "test.op"() : () -> i1
    %m1 = scf.if %b -> (i1) {
        %q1_l, %r17 = qstruct.circuit(%q1_j : !qcore.qubit) -> !qcore.qubit, i1 {
        ^bb0(%q1_k: !qcore.qubit):
            %r17_i = qref.measure<Z> (%q1_k) -> i1
            qstruct.yield %q1_k, %r17_i : !qcore.qubit, i1
        }
        scf.yield %r17 : i1
    } else {
        %q2_l, %r18 = qstruct.circuit(%q2_j : !qcore.qubit) -> !qcore.qubit, i1 {
        ^bb0(%q2_k: !qcore.qubit):
            %r18_i = qref.measure<Z> (%q2_k) -> i1
            qstruct.yield %q2_k, %r18_i : !qcore.qubit, i1
        }
        scf.yield %r18 : i1
    }
    %q8 = qcore.alloc_qubit<coords=[(1.0, 1.0)]> -> !qcore.qubit
    %q8_b = qstruct.circuit(%q8, %m1 : !qcore.qubit, i1) -> !qcore.qubit {
    ^bb0(%q8_a: !qcore.qubit, %m1_in : i1):
        %r19 = qref.measure<Z> (%q8_a) -> i1
        qec.detector(%m1_in, %r19)
        qstruct.yield %q8_a : !qcore.qubit
    }
// CHECK-NEXT:    %b = "test.op"() : () -> i1
// CHECK-NEXT:    %m1 = scf.if %b -> (i1) {
// CHECK-NEXT:        %q1_l, %r17 = qstruct.circuit(%q1_j : !qcore.qubit) -> !qcore.qubit, i1 {
// CHECK-NEXT:        ^bb0(%q1_k: !qcore.qubit):
// CHECK-NEXT:            %r17_i = qref.measure<Z> (%q1_k) -> i1
// CHECK-NEXT:            qstruct.yield %q1_k, %r17_i : !qcore.qubit, i1
// CHECK-NEXT:        }
// CHECK-NEXT:        scf.yield %r17 : i1
// CHECK-NEXT:    } else {
// CHECK-NEXT:        %q2_l, %r18 = qstruct.circuit(%q2_j : !qcore.qubit) -> !qcore.qubit, i1 {
// CHECK-NEXT:        ^bb0(%q2_k: !qcore.qubit):
// CHECK-NEXT:            %r18_i = qref.measure<Z> (%q2_k) -> i1
// CHECK-NEXT:            qstruct.yield %q2_k, %r18_i : !qcore.qubit, i1
// CHECK-NEXT:        }
// CHECK-NEXT:        scf.yield %r18 : i1
// CHECK-NEXT:    }
// CHECK-NEXT:    %q8 = qcore.alloc_qubit<coords = [(1.0, 1.0)]> -> !qcore.qubit
// CHECK-NEXT:    %q8_b = qstruct.circuit(%q8, %m1 : !qcore.qubit, i1) -> !qcore.qubit {
// CHECK-NEXT:    ^bb0(%q8_a: !qcore.qubit, %m1_in: i1):
// CHECK-NEXT:        %r19 = qref.measure<Z> (%q8_a) -> i1
// CHECK-NEXT:        qec.detector<[1.5, 2.0]> (%m1_in, %r19)
// CHECK-NEXT:        qstruct.yield %q8_a : !qcore.qubit
// CHECK-NEXT:    }

    // Similar, passing through qubits and registers
    %q9, %q10 = qcore.alloc_qubit<coords=[(1.0, 2.0), (2.0, 3.0)]> -> !qcore.qubit, !qcore.qubit
    %q11 = qcore.alloc_qubit -> !qcore.qubit
    %reg8 = qcore.pack_qubit_reg(%q9, %q10) -> !qcore.qubit_reg<2>
    %reg9 = qcore.pack_qubit_reg(%q10, %q11) -> !qcore.qubit_reg<2>
    %qif, %regif = scf.if %b -> (!qcore.qubit, !qcore.qubit_reg<2>) {
        scf.yield %q9, %reg8 : !qcore.qubit, !qcore.qubit_reg<2>
    } else {
        scf.yield %q10, %reg9 : !qcore.qubit, !qcore.qubit_reg<2>
    }
    %qif_b, %regif_b = qstruct.circuit(%qif, %regif : !qcore.qubit, !qcore.qubit_reg<2>) -> !qcore.qubit, !qcore.qubit_reg<2> {
    ^bb0(%qif_a: !qcore.qubit, %regif_a: !qcore.qubit_reg<2>):
        %qreg0, %qreg1 = qcore.unpack_qubit_reg(%regif_a : !qcore.qubit_reg<2>)
        %r20 = qref.measure<Z> (%qif_a) -> i1
        %r21 = qref.measure<Z> (%qreg0) -> i1
        %r22 = qref.measure<Z> (%qreg1) -> i1
        %regif_bin = qcore.pack_qubit_reg(%qreg0, %qreg1) -> !qcore.qubit_reg<2>
        qec.detector(%r20)
        qec.detector(%r21, %r22)
        qstruct.yield %qif_a, %regif_bin : !qcore.qubit, !qcore.qubit_reg<2>
    }
// CHECK-NEXT:    %q9, %q10 = qcore.alloc_qubit<coords = [(1.0, 2.0), (2.0, 3.0)]> -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    %q11 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %reg8 = qcore.pack_qubit_reg(%q9, %q10) -> !qcore.qubit_reg<2>
// CHECK-NEXT:    %reg9 = qcore.pack_qubit_reg(%q10, %q11) -> !qcore.qubit_reg<2>
// CHECK-NEXT:    %qif, %regif = scf.if %b -> (!qcore.qubit, !qcore.qubit_reg<2>) {
// CHECK-NEXT:        scf.yield %q9, %reg8 : !qcore.qubit, !qcore.qubit_reg<2>
// CHECK-NEXT:    } else {
// CHECK-NEXT:        scf.yield %q10, %reg9 : !qcore.qubit, !qcore.qubit_reg<2>
// CHECK-NEXT:    }
// CHECK-NEXT:    %qif_b, %regif_b = qstruct.circuit(%qif, %regif : !qcore.qubit, !qcore.qubit_reg<2>) -> !qcore.qubit, !qcore.qubit_reg<2> {
// CHECK-NEXT:    ^bb0(%qif_a: !qcore.qubit, %regif_a: !qcore.qubit_reg<2>):
// CHECK-NEXT:        %qreg0, %qreg1 = qcore.unpack_qubit_reg(%regif_a : !qcore.qubit_reg<2>)
// CHECK-NEXT:        %r20 = qref.measure<Z> (%qif_a) -> i1
// CHECK-NEXT:        %r21 = qref.measure<Z> (%qreg0) -> i1
// CHECK-NEXT:        %r22 = qref.measure<Z> (%qreg1) -> i1
// CHECK-NEXT:        %regif_bin = qcore.pack_qubit_reg(%qreg0, %qreg1) -> !qcore.qubit_reg<2>
// CHECK-NEXT:        qec.detector<[1.5, 2.5]> (%r20)
// CHECK-NEXT:        qec.detector<[1.75, 2.75]> (%r21, %r22)
// CHECK-NEXT:        qstruct.yield %qif_a, %regif_bin : !qcore.qubit, !qcore.qubit_reg<2>
// CHECK-NEXT:    }

    // Passing through parallel properly
    %q12, %reg10 = qcore.alloc_qubit<coords=[(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)]> -> !qcore.qubit, !qcore.qubit_reg<2>
    %m2, %q13, %reg11 = qstruct.parallel<TOP> -> i1, !qcore.qubit, !qcore.qubit_reg<2> {
        qstruct.yield %m1, %q12 : i1, !qcore.qubit
    } {
        qstruct.yield %reg10 : !qcore.qubit_reg<2>
    }
    %q13_b, %reg11_b = qstruct.circuit(%q13, %reg11 : !qcore.qubit, !qcore.qubit_reg<2>) -> !qcore.qubit, !qcore.qubit_reg<2> {
    ^bb0(%q13_a: !qcore.qubit, %reg11_a: !qcore.qubit_reg<2>):
        %qreg0, %qreg1 = qcore.unpack_qubit_reg(%reg11_a : !qcore.qubit_reg<2>)
        %r23 = qref.measure<Z> (%q13_a) -> i1
        %r24 = qref.measure<Z> (%qreg0) -> i1
        %r25 = qref.measure<Z> (%qreg1) -> i1
        %reg11_bin = qcore.pack_qubit_reg(%qreg0, %qreg1) -> !qcore.qubit_reg<2>
        qec.detector(%r23, %r24, %r25)
        qstruct.yield %q13_a, %reg11_bin : !qcore.qubit, !qcore.qubit_reg<2>
    }
// CHECK-NEXT:    %q12, %reg10 = qcore.alloc_qubit<coords = [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)]> -> !qcore.qubit, !qcore.qubit_reg<2>
// CHECK-NEXT:    %m2, %q13, %reg11 = qstruct.parallel<TOP> -> i1, !qcore.qubit, !qcore.qubit_reg<2> {
// CHECK-NEXT:        qstruct.yield %m1, %q12 : i1, !qcore.qubit
// CHECK-NEXT:    } {
// CHECK-NEXT:        qstruct.yield %reg10 : !qcore.qubit_reg<2>
// CHECK-NEXT:    }
// CHECK-NEXT:    %q13_b, %reg11_b = qstruct.circuit(%q13, %reg11 : !qcore.qubit, !qcore.qubit_reg<2>) -> !qcore.qubit, !qcore.qubit_reg<2> {
// CHECK-NEXT:    ^bb0(%q13_a: !qcore.qubit, %reg11_a: !qcore.qubit_reg<2>):
// CHECK-NEXT:        %qreg0, %qreg1 = qcore.unpack_qubit_reg(%reg11_a : !qcore.qubit_reg<2>)
// CHECK-NEXT:        %r23 = qref.measure<Z> (%q13_a) -> i1
// CHECK-NEXT:        %r24 = qref.measure<Z> (%qreg0) -> i1
// CHECK-NEXT:        %r25 = qref.measure<Z> (%qreg1) -> i1
// CHECK-NEXT:        %reg11_bin = qcore.pack_qubit_reg(%qreg0, %qreg1) -> !qcore.qubit_reg<2>
// CHECK-NEXT:        qec.detector<[3.0, 4.0]> (%r23, %r24, %r25)
// CHECK-NEXT:        qstruct.yield %q13_a, %reg11_bin : !qcore.qubit, !qcore.qubit_reg<2>
// CHECK-NEXT:    }
}
// CHECK-NEXT: }
