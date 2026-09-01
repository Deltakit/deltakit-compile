// RUN: deltakit_compile compile-passes %s -p qstruct-circuit-to-stab -O %t --test-mode && filecheck %s --input-file %t

// One qubit passed through one circuit

builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %q1 = qstruct.circuit(%q0: !qcore.qubit) -> !qcore.qubit {
    ^bb0(%q0_b: !qcore.qubit):
        qref.gate<#qcore.gate.x> (%q0_b)
        qstruct.yield %q0_b : !qcore.qubit
    }
}

// CHECK:      builtin.module {
// CHECK-NEXT:     %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:     [[S0:%[\w\d_]+]] = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S1:%[\w\d_]+]] = stab.state.concatenate([[S0]] : !stab.state<1 x !qcore.qubit, []>)
// CHECK-SAME:                        -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S2:%[\w\d_]+]] = stab.circuit [[S1]] : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                           -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:       with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:         qref.gate<#qcore.gate.x> (%q0_b)
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       }
// CHECK-NEXT: }

// ----

// One qubit register passed through one circuit

builtin.module {
    %r0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    %r1 = qstruct.circuit(%r0: !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
    ^bb0(%r0_b: !qcore.qubit_reg<2>):
        "test.op"() : () -> ()  // suppress DCE
        qstruct.yield %r0_b : !qcore.qubit_reg<2>
    }
}

// CHECK:      builtin.module {
// CHECK-NEXT:     %r0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
// CHECK-NEXT:     [[Q0:%[\w\d_]+]], [[Q1:%[\w\d_]+]] = qcore.unpack_qubit_reg(%r0 : !qcore.qubit_reg<2>)
// CHECK-NEXT:     [[S0:%[\w\d_]+]] = stab.state.make([[Q0]], [[Q1]] : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     [[S1:%[\w\d_]+]] = stab.state.concatenate([[S0]] : !stab.state<2 x !qcore.qubit, []>)
// CHECK-SAME:                        -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     [[S2:%[\w\d_]+]] = stab.circuit [[S1]] : !stab.state<2 x !qcore.qubit, []>
// CHECK-SAME:                                           -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:       with ([[Q2:%[\w\d_]+]], [[Q3:%[\w\d_+]]] : !qcore.qubit), (){
// CHECK-NEXT:         "test.op"() : () -> ()
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       }
// CHECK-NEXT: }

// ----

// Several qubits and registers passed through one circuit

builtin.module {
    %q0, %r0, %q1, %r1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit_reg<2>, !qcore.qubit, !qcore.qubit_reg<3>
    %q2, %r2, %q3, %r3 = qstruct.circuit(
        %q0, %r0, %q1, %r1 : !qcore.qubit, !qcore.qubit_reg<2>, !qcore.qubit, !qcore.qubit_reg<3>
    ) -> !qcore.qubit, !qcore.qubit_reg<2>, !qcore.qubit, !qcore.qubit_reg<3> {
    ^bb0(%q0_b: !qcore.qubit, %r0_b: !qcore.qubit_reg<2>, %q1_b: !qcore.qubit, %r1_b: !qcore.qubit_reg<3>):
        "test.op"() : () -> ()  // suppress DCE
        qstruct.yield %q1_b, %r0_b, %q0_b, %r1_b : !qcore.qubit, !qcore.qubit_reg<2>, !qcore.qubit, !qcore.qubit_reg<3>
    }
}

// CHECK:      builtin.module {
// CHECK-NEXT:     %q0, %r0, %q1, %r1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit_reg<2>, !qcore.qubit, !qcore.qubit_reg<3>
// CHECK-NEXT:     [[S0:%[\w\d_]+]] = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[Q0:%[\w\d_]+]], [[Q1:%[\w\d_]+]] = qcore.unpack_qubit_reg(%r0 : !qcore.qubit_reg<2>)
// CHECK-NEXT:     [[S1:%[\w\d_]+]] = stab.state.make([[Q0]], [[Q1]] : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     [[S2:%[\w\d_]+]] = stab.state.make(%q1 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[Q2:%[\w\d_]+]], [[Q3:%[\w\d_]+]], [[Q4:%[\w\d_]+]] = qcore.unpack_qubit_reg(%r1 : !qcore.qubit_reg<3>)
// CHECK-NEXT:     [[S3:%[\w\d_]+]] = stab.state.make([[Q2]], [[Q3]], [[Q4]] : !qcore.qubit) -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:     [[S4:%[\w\d_]+]] = stab.state.concatenate([[S0]], [[S1]], [[S2]], [[S3]]
// CHECK-SAME:         : !stab.state<1 x !qcore.qubit, []>, !stab.state<2 x !qcore.qubit, []>,
// CHECK-SAME:           !stab.state<1 x !qcore.qubit, []>, !stab.state<3 x !qcore.qubit, []>)
// CHECK-SAME:                        -> !stab.state<7 x !qcore.qubit, []>
// CHECK-NEXT:     [[S5:%[\w\d_]+]] = stab.circuit [[S4]] : !stab.state<7 x !qcore.qubit, []>
// CHECK-SAME:                                           -> !stab.state<7 x !qcore.qubit, []>
// CHECK-NEXT:       with ([[Q5:%[\w\d_]+]], [[Q6:%[\w\d_]+]], [[Q7:%[\w\d_]+]], [[Q8:%[\w\d_]+]],
// CHECK-SAME:             [[Q9:%[\w\d_]+]], [[Q10:%[\w\d_]+]], [[Q11:%[\w\d_]+]] : !qcore.qubit), (){
// CHECK-NEXT:         "test.op"() : () -> ()
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       }
// CHECK-NEXT: }

// ----

// One qubit register passed through one circuit: flattened out

builtin.module {
    %r0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    %r1 = qstruct.circuit(%r0: !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
    ^bb0(%r0_b: !qcore.qubit_reg<2>):
        "test.op"() : () -> ()  // suppress DCE
        qstruct.yield %r0_b : !qcore.qubit_reg<2>
    }
}
// CHECK:      builtin.module {
// CHECK-NEXT:     %r0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
// CHECK-NEXT:     [[Q0:%[\w\d_]+]], [[Q1:%[\w\d_]+]] = qcore.unpack_qubit_reg(%r0 : !qcore.qubit_reg<2>)
// CHECK-NEXT:     [[S0:%[\w\d_]+]] = stab.state.make([[Q0]], [[Q1]] : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     [[S1:%[\w\d_]+]] = stab.state.concatenate([[S0]] : !stab.state<2 x !qcore.qubit, []>)
// CHECK-SAME:                        -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     [[S2:%[\w\d_]+]] = stab.circuit [[S1]] : !stab.state<2 x !qcore.qubit, []>
// CHECK-SAME:                                           -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:       with ([[Q2:%[\w\d_]+]], [[Q3:%[\w\d_+]]] : !qcore.qubit), (){
// CHECK-NEXT:         "test.op"() : () -> ()
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       }
// CHECK-NEXT: }

// ----

// Qubit registers passed through circuits and manipulated: permutation calculated correctly

builtin.module {
    %r0, %r1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>, !qcore.qubit_reg<3>
    %r2, %q0 = qstruct.circuit(%r0, %r1 : !qcore.qubit_reg<2>, !qcore.qubit_reg<3>)
        -> !qcore.qubit_reg<4>, !qcore.qubit {
    ^bb0(%r0_b: !qcore.qubit_reg<2>, %r1_b: !qcore.qubit_reg<3>):
        %r2 = qcore.concatenate(%r0_b, %r1_b : !qcore.qubit_reg<2>, !qcore.qubit_reg<3>) -> !qcore.qubit_reg<5>
        %r3, %r4 = qcore.split(%r2 : !qcore.qubit_reg<5>) -> !qcore.qubit_reg<4>, !qcore.qubit_reg<1>
        %q1 = qcore.unpack_qubit_reg(%r4 : !qcore.qubit_reg<1>)
        %r5, %r6 = qcore.split(%r3 : !qcore.qubit_reg<4>) -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2>
        %q2, %q3 = qcore.unpack_qubit_reg(%r5 : !qcore.qubit_reg<2>)
        qref.gate<#qcore.gate.x> (%q1, %q2, %q3)
        %r7 = qcore.pack_qubit_reg(%q1, %q2) -> !qcore.qubit_reg<2>
        %r8 = qcore.concatenate(%r7, %r6 : !qcore.qubit_reg<2>, !qcore.qubit_reg<2>) -> !qcore.qubit_reg<4>
        qstruct.yield %r8, %q3 : !qcore.qubit_reg<4>, !qcore.qubit
    }
    %r9, %q4 = qstruct.circuit(%r2, %q0 : !qcore.qubit_reg<4>, !qcore.qubit) -> !qcore.qubit_reg<4>, !qcore.qubit {
    ^bb0(%r2_b: !qcore.qubit_reg<4>, %q1_b: !qcore.qubit):
        "test.op"() : () -> ()  // suppress DCE
        qstruct.yield %r2_b, %q1_b : !qcore.qubit_reg<4>, !qcore.qubit
    }
}
// CHECK:      builtin.module {
// CHECK-NEXT:     %r0, %r1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>, !qcore.qubit_reg<3>
// CHECK-NEXT:     [[R0Q0:%[\w\d_]+]], [[R0Q1:%[\w\d_]+]] = qcore.unpack_qubit_reg(%r0 : !qcore.qubit_reg<2>)
// CHECK-NEXT:     [[R0:%[\w\d_]+]] = stab.state.make([[R0Q0]], [[R0Q1]] : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     [[R1Q0:%[\w\d_]+]], [[R1Q1:%[\w\d_]+]], [[R1Q2:%[\w\d_]+]] = qcore.unpack_qubit_reg(%r1 : !qcore.qubit_reg<3>)
// CHECK-NEXT:     [[R1:%[\w\d_]+]] = stab.state.make([[R1Q0]], [[R1Q1]], [[R1Q2]] : !qcore.qubit) -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:     [[S0:%[\w\d_]+]] = stab.state.concatenate([[R0]], [[R1]] : !stab.state<2 x !qcore.qubit, []>,
// CHECK-SAME:         !stab.state<3 x !qcore.qubit, []>) -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:     [[S1:%[\w\d_]+]] = stab.circuit [[S0]] : !stab.state<5 x !qcore.qubit, []> -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:       with ([[R2Q0:%[\w\d_]+]], [[R2Q1:%[\w\d_]+]], [[R2Q2:%[\w\d_]+]], [[R2Q3:%[\w\d_]+]],
// CHECK-SAME:             [[R2Q4:%[\w\d_]+]] : !qcore.qubit), (){
// CHECK-NEXT:         qref.gate<#qcore.gate.x> ([[R2Q4]], [[R2Q0]], [[R2Q1]])
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       }
// CHECK-NEXT:     [[S2:%[\w\d_]+]] = stab.state.permute<[4, 0, 2, 3, 1]> ([[S1]] : !stab.state<5 x !qcore.qubit, []>)
// CHECK-SAME:                        -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:     [[S3:%[\w\d_]+]], [[S4:%[\w\d_]+]] = stab.state.split([[S2]] : !stab.state<5 x !qcore.qubit, []>)
// CHECK-SAME:         -> !stab.state<4 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S5:%[\w\d_]+]] = stab.state.concatenate([[S3]], [[S4]] : !stab.state<4 x !qcore.qubit, []>,
// CHECK-SAME:         !stab.state<1 x !qcore.qubit, []>) -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:     [[S6:%[\w\d_]+]] = stab.circuit [[S5]] : !stab.state<5 x !qcore.qubit, []> -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:       with ([[R3Q0:%[\w\d_]+]], [[R3Q1:%[\w\d_]+]], [[R3Q2:%[\w\d_]+]], [[R3Q3:%[\w\d_]+]],
// CHECK-SAME:             [[R3Q4:%[\w\d_]+]] : !qcore.qubit), (){
// CHECK-NEXT:         "test.op"() : () -> ()
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       }
// CHECK-NEXT: }

// ----

// One qubit passed through two circuits

builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %q1 = qstruct.circuit(%q0: !qcore.qubit) -> !qcore.qubit {
    ^bb0(%q0_b: !qcore.qubit):
        qref.gate<#qcore.gate.x> (%q0_b)
        qstruct.yield %q0_b : !qcore.qubit
    }
    %q2 = qstruct.circuit(%q1: !qcore.qubit) -> !qcore.qubit {
    ^bb0(%q1_b: !qcore.qubit):
        qref.gate<#qcore.gate.h> (%q1_b)
        qstruct.yield %q1_b : !qcore.qubit
    }
}
// CHECK:      builtin.module {
// CHECK-NEXT:     %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:     [[S0:%[\w\d_]+]] = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S1:%[\w\d_]+]] = stab.state.concatenate([[S0]] : !stab.state<1 x !qcore.qubit, []>)
// CHECK-SAME:                        -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S2:%[\w\d_]+]] = stab.circuit [[S1]] : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                           -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:       with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:         qref.gate<#qcore.gate.x> (%q0_b)
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       }
// CHECK-NEXT:     [[S3:%[\w\d_]+]] = stab.state.permute<[0]> ([[S2]] : !stab.state<1 x !qcore.qubit, []>)
// CHECK-SAME:                        -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S4:%[\w\d_]+]] = stab.state.split([[S3]] : !stab.state<1 x !qcore.qubit, []>)
// CHECK-SAME:                        -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S5:%[\w\d_]+]] = stab.state.concatenate([[S4]] : !stab.state<1 x !qcore.qubit, []>)
// CHECK-SAME:                        -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S6:%[\w\d_]+]] = stab.circuit [[S5]] : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                           -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:       with (%q1_b : !qcore.qubit), (){
// CHECK-NEXT:         qref.gate<#qcore.gate.h> (%q1_b)
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       }
// CHECK-NEXT: }

// ----

// Three qubits and two circuits, the second only using two qubits: generates the correct
// permutation, split, and concatenate

builtin.module {
    %q0, %q1, %q2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
    %q3, %q4, %q5 = qstruct.circuit(%q0, %q1, %q2 : !qcore.qubit, !qcore.qubit, !qcore.qubit)
        -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
    ^bb0(%q0_b: !qcore.qubit, %q1_b: !qcore.qubit, %q2_b: !qcore.qubit):
        "test.op"() : () -> ()  // suppress DCE
        qstruct.yield %q2_b, %q0_b, %q1_b : !qcore.qubit, !qcore.qubit, !qcore.qubit
    }
    %q6, %q7 = qstruct.circuit(%q5, %q3 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
    ^bb0(%q5_b: !qcore.qubit, %q3_b: !qcore.qubit):
        "test.op"() : () -> ()  // suppress DCE
        qstruct.yield %q5_b, %q3_b : !qcore.qubit, !qcore.qubit
    }
}
// CHECK:      builtin.module {
// CHECK-NEXT:     %q0, %q1, %q2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:     [[S0:%[\w\d_]+]] = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S1:%[\w\d_]+]] = stab.state.make(%q1 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S2:%[\w\d_]+]] = stab.state.make(%q2 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S3:%[\w\d_]+]] = stab.state.concatenate([[S0]], [[S1]], [[S2]]
// CHECK-SAME:          : !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:            !stab.state<1 x !qcore.qubit, []>) -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:     [[S4:%[\w\d_]+]] = stab.circuit [[S3]] : !stab.state<3 x !qcore.qubit, []>
// CHECK-SAME:                                           -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:       with (%q0_b, %q1_b, %q2_b : !qcore.qubit), (){
// CHECK-NEXT:         "test.op"() : () -> ()
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       }
// CHECK-NEXT:     [[S5:%[\w\d_]+]] = stab.state.permute<[2, 0, 1]> ([[S4]] : !stab.state<3 x !qcore.qubit, []>)
// CHECK-SAME:                        -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:     [[S6:%[\w\d_]+]], [[S7:%[\w\d_]+]], [[S8:%[\w\d_]+]] = stab.state.split(
// CHECK-SAME:         [[S5]] : !stab.state<3 x !qcore.qubit, []>) -> !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:         !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S9:%[\w\d_]+]] = stab.state.concatenate([[S8]], [[S6]] : !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:         !stab.state<1 x !qcore.qubit, []>) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     [[S10:%[\w\d_]+]] = stab.circuit [[S9]] : !stab.state<2 x !qcore.qubit, []>
// CHECK-SAME:                                            -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:       with (%q5_b, %q3_b : !qcore.qubit), (){
// CHECK-NEXT:         "test.op"() : () -> ()
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       }
// CHECK-NEXT: }

// ----

// One non-qubit arg passes through correctly

builtin.module {
    %i0 = arith.constant 42 : i32
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %q1, %i1 = qstruct.circuit(%q0, %i0 : !qcore.qubit, i32) -> !qcore.qubit, i32 {
    ^bb0(%q0_b: !qcore.qubit, %i0_b: i32):
        "test.op"() : () -> ()  // suppress DCE
        qstruct.yield %q0_b, %i0_b : !qcore.qubit, i32
    }
    "test.op"(%i1) : (i32) -> ()  // use it afterwards
}
// CHECK:      builtin.module {
// CHECK-NEXT:     %i0 = arith.constant 42 : i32
// CHECK-NEXT:     %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:     [[S0:%[\w\d_]+]] = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S1:%[\w\d_]+]] = stab.state.concatenate([[S0]] : !stab.state<1 x !qcore.qubit, []>)
// CHECK-SAME:                        -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S2:%[\w\d_]+]], [[I1:%[\w\d_]+]] = stab.circuit [[S1]] : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                               -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:       with (%q0_b : !qcore.qubit), (%i0_b = %i0 : i32){
// CHECK-NEXT:         "test.op"() : () -> ()
// CHECK-NEXT:         stab.yield [] %i0_b : i32
// CHECK-NEXT:       }
// CHECK-NEXT:     "test.op"([[I1]]) : (i32) -> ()
// CHECK-NEXT: }

// ----

// Several non-qubit args and yields are sorted to the end

builtin.module {
    %i0 = arith.constant 42 : i32
    %i1 = arith.constant 17 : i64
    %i2 = arith.constant false
    %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
    %i3, %i4, %q2, %i5, %q3, %i6 = qstruct.circuit(%i0, %i1, %q0, %i2, %q1 : i32, i64, !qcore.qubit, i1, !qcore.qubit)
        -> i1, i64, !qcore.qubit, i1, !qcore.qubit, i64 {
    ^bb0(%i0_b: i32, %i1_b: i64, %q0_b: !qcore.qubit, %i2_b: i1, %q1_b: !qcore.qubit):
        "test.op"() : () -> ()  // suppress DCE
        %i3_i = arith.xori %i2_b, %i2_b : i1
        %i4_i = arith.constant 123 : i64
        qstruct.yield %i3_i, %i4_i, %q0_b, %i2_b, %q1_b, %i1_b : i1, i64, !qcore.qubit, i1, !qcore.qubit, i64
    }
    "test.op"(%i3, %i4, %i5, %i6) : (i1, i64, i1, i64) -> ()  // use them afterwards
}
// CHECK:      builtin.module {
// CHECK-NEXT:     %i0 = arith.constant 42 : i32
// CHECK-NEXT:     %i1 = arith.constant 17 : i64
// CHECK-NEXT:     %i2 = arith.constant false
// CHECK-NEXT:     %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:     [[S0:%[\w\d_]+]] = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S1:%[\w\d_]+]] = stab.state.make(%q1 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S2:%[\w\d_]+]] = stab.state.concatenate([[S0]], [[S1]] : !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:         !stab.state<1 x !qcore.qubit, []>) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     [[S3:%[\w\d_]+]], [[I3:%[\w\d_]+]], [[I4:%[\w\d_]+]], [[I5:%[\w\d_]+]], [[I6:%[\w\d_]+]]
// CHECK-SAME:         = stab.circuit [[S2]] : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:       with (%q0_b, %q1_b : !qcore.qubit), (%i0_b = %i0 : i32, %i1_b = %i1 : i64, %i2_b = %i2 : i1){
// CHECK-NEXT:         "test.op"() : () -> ()
// CHECK-NEXT:         %i3_i = arith.xori %i2_b, %i2_b : i1
// CHECK-NEXT:         %i4_i = arith.constant 123 : i64
// CHECK-NEXT:         stab.yield [] %i3_i, %i4_i, %i2_b, %i1_b : i1, i64, i1, i64
// CHECK-NEXT:       }
// CHECK-NEXT:     "test.op"([[I3]], [[I4]], [[I5]], [[I6]]) : (i1, i64, i1, i64) -> ()
// CHECK-NEXT: }

// ----

// Pack, unpack, split, concatenate at the top level

builtin.module {
    %r0, %q0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>, !qcore.qubit
    %q1, %q2 = qcore.unpack_qubit_reg(%r0 : !qcore.qubit_reg<2>)
    %r1 = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
    %r2 = qcore.pack_qubit_reg(%q2) -> !qcore.qubit_reg<1>
    %r3 = qcore.concatenate(%r1, %r2 : !qcore.qubit_reg<2>, !qcore.qubit_reg<1>) -> !qcore.qubit_reg<3>
    %r4, %r5 = qcore.split(%r3 : !qcore.qubit_reg<3>) -> !qcore.qubit_reg<1>, !qcore.qubit_reg<2>
    // suppress DCE
    %r6, %r7 = qstruct.circuit(%r4, %r5 : !qcore.qubit_reg<1>, !qcore.qubit_reg<2>)
        -> !qcore.qubit_reg<1>, !qcore.qubit_reg<2> {
    ^bb0(%r4_b: !qcore.qubit_reg<1>, %r5_b: !qcore.qubit_reg<2>):
        "test.op"() : () -> ()
        qstruct.yield %r4_b, %r5_b : !qcore.qubit_reg<1>, !qcore.qubit_reg<2>
    }
}
// CHECK:      builtin.module {
// CHECK-NEXT:     %r0, %q0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>, !qcore.qubit
// CHECK-NEXT:     [[R0Q0:%[\w\d_]+]], [[R0Q1:%[\w\d_]+]] = qcore.unpack_qubit_reg(%r0 : !qcore.qubit_reg<2>)
// CHECK-NEXT:     [[R0:%[\w\d_]+]] = stab.state.make([[R0Q0]], [[R0Q1]] : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     [[Q0:%[\w\d_]+]] = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[Q1:%[\w\d_]+]], [[Q2:%[\w\d_]+]] = stab.state.split([[R0]] : !stab.state<2 x !qcore.qubit, []>)
// CHECK-SAME:         -> !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[R1:%[\w\d_]+]] = stab.state.concatenate([[Q0]], [[Q1]] : !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:         !stab.state<1 x !qcore.qubit, []>) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     [[R2:%[\w\d_]+]] = stab.state.concatenate([[Q2]] : !stab.state<1 x !qcore.qubit, []>)
// CHECK-SAME:         -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[R3:%[\w\d_]+]] = stab.state.concatenate([[R1]], [[R2]] : !stab.state<2 x !qcore.qubit, []>,
// CHECK-SAME:         !stab.state<1 x !qcore.qubit, []>) -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:     [[R4:%[\w\d_]+]], [[R5:%[\w\d_]+]] = stab.state.split([[R3]] : !stab.state<3 x !qcore.qubit, []>)
// CHECK-SAME:         -> !stab.state<1 x !qcore.qubit, []>, !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     [[S0:%[\w\d_]+]] = stab.state.concatenate([[R4]], [[R5]] : !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:         !stab.state<2 x !qcore.qubit, []>) -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:     [[S1:%[\w\d_]+]] = stab.circuit [[S0]] : !stab.state<3 x !qcore.qubit, []>
// CHECK-SAME:                                           -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:       with ([[I0:%[\w\d_]+]], [[I1:%[\w\d_]+]], [[I2:%[\w\d_]+]] : !qcore.qubit), (){
// CHECK-NEXT:         "test.op"() : () -> ()
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       }
// CHECK-NEXT: }

// ----

// Passing qubits through control flow, simple case

builtin.module {
    %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
    %b = "test.op"() : () -> i1
    %q2 = scf.if %b -> (!qcore.qubit) {
        scf.yield %q0 : !qcore.qubit
    } else {
        scf.yield %q1 : !qcore.qubit
    }
    // suppress DCE
    %q3 = qstruct.circuit (%q2 : !qcore.qubit) -> !qcore.qubit {
    ^bb0(%q2_b: !qcore.qubit):
        "test.op"() : () -> ()
        qstruct.yield %q2_b : !qcore.qubit
    }
}
// CHECK:      builtin.module {
// CHECK-NEXT:     %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:     [[S0:%[\w\d_]+]] = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S1:%[\w\d_]+]] = stab.state.make(%q1 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     %b = "test.op"() : () -> i1
// CHECK-NEXT:     [[S2:%[\w\d_]+]] = scf.if %b -> (!stab.state<1 x !qcore.qubit, []>) {
// CHECK-NEXT:       scf.yield [[S0]] : !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     } else {
// CHECK-NEXT:       scf.yield [[S1]] : !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     }
// CHECK-NEXT:     [[S3:%[\w\d_]+]] = stab.state.concatenate([[S2]] : !stab.state<1 x !qcore.qubit, []>)
// CHECK-SAME:         -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S4:%[\w\d_]+]] = stab.circuit [[S3]] : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                           -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:       with (%q2_b : !qcore.qubit), (){
// CHECK-NEXT:         "test.op"() : () -> ()
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       }
// CHECK-NEXT: }

// ----

// Passing qubits through control flow, complex case

builtin.module {
    %q0, %r0 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit_reg<2>
    %j, %i0, %i1, %i2 = "test.op"() : () -> (index, index, index, index)
    %r3 = scf.for %iv = %i0 to %i1 step %i2 iter_args(%r1 = %r0) -> (!qcore.qubit_reg<2>) {
        %q1, %q2 = qcore.unpack_qubit_reg(%r1 : !qcore.qubit_reg<2>)
        %q3, %q4 = scf.index_switch %j -> !qcore.qubit, !qcore.qubit
        case 0 {
            scf.yield %q1, %q2 : !qcore.qubit, !qcore.qubit
        }
        case 1 {
            scf.yield %q2, %q1 : !qcore.qubit, !qcore.qubit
        }
        default {
            scf.yield %q1, %q2 : !qcore.qubit, !qcore.qubit
        }
        %r2 = qcore.pack_qubit_reg(%q3, %q4) -> !qcore.qubit_reg<2>
        scf.yield %r2 : !qcore.qubit_reg<2>
    }
    %r4 = scf.while (%r5 = %r3) : (!qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
        %b0 = "test.op"() : () -> i1
        scf.condition(%b0) %r5 : !qcore.qubit_reg<2>
    } do {
    ^bb0(%r5_b: !qcore.qubit_reg<2>):
        scf.yield %r5_b : !qcore.qubit_reg<2>
    }
    %q5, %o, %r6 = qstruct.parallel<BOTTOM> -> !qcore.qubit, i1, !qcore.qubit_reg<2> {
        %o1 = arith.constant false
        qstruct.yield %q0, %o1 : !qcore.qubit, i1
    } {
        qstruct.yield %r4 : !qcore.qubit_reg<2>
    }
    %r7 = qstruct.repeat<2> (%r6 : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
    ^bb1(%r6_b: !qcore.qubit_reg<2>):
        qstruct.yield %r6_b : !qcore.qubit_reg<2>
    }
    // suppress DCE
    %q6, %r8 = qstruct.circuit(%q5, %r7 : !qcore.qubit, !qcore.qubit_reg<2>)
        -> !qcore.qubit, !qcore.qubit_reg<2> {
    ^bb2(%q5_b: !qcore.qubit, %r7_b: !qcore.qubit_reg<2>):
        "test.op"() : () -> ()
        qstruct.yield %q5_b, %r7_b : !qcore.qubit, !qcore.qubit_reg<2>
    }
    qstruct.output(%o : i1)
}
// CHECK:      builtin.module {
// CHECK-NEXT:     %q0, %r0 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit_reg<2>
// CHECK-NEXT:     [[Q0:%[\w\d_]+]] = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[R0Q0:%[\w\d_]+]], [[R0Q1:%[\w\d_]+]] = qcore.unpack_qubit_reg(%r0 : !qcore.qubit_reg<2>)
// CHECK-NEXT:     [[R0:%[\w\d_]+]] = stab.state.make([[R0Q0]], [[R0Q1]] : !qcore.qubit)
// CHECK-SAME:         -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     %j, %i0, %i1, %i2 = "test.op"() : () -> (index, index, index, index)
// CHECK-NEXT:     %r3 = scf.for %iv = %i0 to %i1 step %i2 iter_args(%r1 = [[R0]])
// CHECK-SAME:             -> (!stab.state<2 x !qcore.qubit, []>) {
// CHECK-NEXT:         [[Q1:%[\w\d_]+]], [[Q2:%[\w\d_]+]] = stab.state.split(%r1
// CHECK-SAME:             : !stab.state<2 x !qcore.qubit, []>) -> !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:             !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:         %q3, %q4 = scf.index_switch %j -> !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:             !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:         case 0 {
// CHECK-NEXT:             scf.yield [[Q1]], [[Q2]] : !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:                 !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:         }
// CHECK-NEXT:         case 1 {
// CHECK-NEXT:             scf.yield [[Q2]], [[Q1]] : !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:                 !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:         }
// CHECK-NEXT:         default {
// CHECK-NEXT:             scf.yield [[Q1]], [[Q2]] : !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:                 !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:         }
// CHECK-NEXT:         [[R2:%[\w\d_]+]] = stab.state.concatenate(%q3, %q4
// CHECK-SAME:             : !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>)
// CHECK-SAME:             -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:         scf.yield [[R2]] : !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     }
// CHECK-NEXT:     %r4 = scf.while (%r5 = %r3) : (!stab.state<2 x !qcore.qubit, []>)
// CHECK-SAME:             -> !stab.state<2 x !qcore.qubit, []> {
// CHECK-NEXT:         %b0 = "test.op"() : () -> i1
// CHECK-NEXT:         scf.condition(%b0) %r5 : !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     } do {
// CHECK-NEXT:     ^bb0(%r5_b: !stab.state<2 x !qcore.qubit, []>):
// CHECK-NEXT:         scf.yield %r5_b : !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     }
// CHECK-NEXT:     %q5, %o, %r6 = qstruct.parallel<BOTTOM> -> !stab.state<1 x !qcore.qubit, []>, i1,
// CHECK-SAME:             !stab.state<2 x !qcore.qubit, []> {
// CHECK-NEXT:         %o1 = arith.constant false
// CHECK-NEXT:         qstruct.yield [[Q0]], %o1 : !stab.state<1 x !qcore.qubit, []>, i1
// CHECK-NEXT:     } {
// CHECK-NEXT:         qstruct.yield %r4 : !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     }
// CHECK-NEXT:     %r7 = qstruct.repeat<2> (%r6 : !stab.state<2 x !qcore.qubit, []>)
// CHECK-SAME:             -> !stab.state<2 x !qcore.qubit, []> {
// CHECK-NEXT:     ^bb1(%r6_b: !stab.state<2 x !qcore.qubit, []>):
// CHECK-NEXT:         qstruct.yield %r6_b : !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     }
// CHECK-NEXT:     [[S0:%[\w\d_]+]] = stab.state.concatenate(%q5, %r7 : !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:         !stab.state<2 x !qcore.qubit, []>) -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:     [[S1:%[\w\d_]+]] = stab.circuit [[S0]] : !stab.state<3 x !qcore.qubit, []>
// CHECK-SAME:         -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:       with ([[SQ0:%[\w\d_]+]], [[SQ1:%[\w\d_]+]], [[SQ2:%[\w\d_]+]] : !qcore.qubit), (){
// CHECK-NEXT:         "test.op"() : () -> ()
// CHECK-NEXT:          stab.yield []
// CHECK-NEXT:       }
// CHECK-NEXT:     qstruct.output(%o : i1)
// CHECK-NEXT: }

// ----

// qstruct.parallel inside a circuit

builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %q1 = qstruct.circuit(%q0: !qcore.qubit) -> !qcore.qubit {
    ^bb0(%q0_b: !qcore.qubit):
        %q0_c = qstruct.parallel<BOTTOM> -> !qcore.qubit {
            "test.op"() : () -> ()  // suppress DCE
            qstruct.yield %q0_b : !qcore.qubit
        }
        qstruct.yield %q0_c : !qcore.qubit
    }
}
// CHECK:      builtin.module {
// CHECK-NEXT:     %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:     [[S0:%[\w\d_]+]] = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S1:%[\w\d_]+]] = stab.state.concatenate([[S0]] : !stab.state<1 x !qcore.qubit, []>)
// CHECK-SAME:                        -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S2:%[\w\d_]+]] = stab.circuit [[S1]] : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                           -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:       with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:         %q0_c = qstruct.parallel<BOTTOM> -> !qcore.qubit {
// CHECK-NEXT:           "test.op"() : () -> ()
// CHECK-NEXT:           qstruct.yield %q0_b : !qcore.qubit
// CHECK-NEXT:         }
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       }
// CHECK-NEXT: }

// ----

// Preserves the stab.concrete_flow_array attribute, simple case

builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %q1 = qstruct.circuit(%q0: !qcore.qubit)
        {stab.flows = #stab.concrete_flow_array<[<+:>{I -> X0 : 1}]>} -> !qcore.qubit {
    ^bb0(%q0_b: !qcore.qubit):
        "test.op"() : () -> ()  // suppress DCE
        qstruct.yield %q0_b : !qcore.qubit
    }
}
// CHECK:      builtin.module {
// CHECK-NEXT:     %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:     [[S0:%[\w\d_]+]] = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S1:%[\w\d_]+]] = stab.state.concatenate([[S0]] : !stab.state<1 x !qcore.qubit, []>)
// CHECK-SAME:                        -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S2:%[\w\d_]+]] = stab.circuit [[S1]] : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                           -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:       with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:         "test.op"() : () -> ()
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       } {stab.flows = #stab.concrete_flow_array<[<+:>{I -> X0 : 1}]>}
// CHECK-NEXT: }

// ----

// Preserves the stab.concrete_flow_array attribute, updating measurement indices

builtin.module {
    %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
    %m0, %q2, %m1, %q3, %m2 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit)
        {stab.flows = #stab.concrete_flow_array<[<+:0,2,4>{I -> X0 X1 : 2}, <+:2>{I -> X0 : 2}, <+:4>{I -> X1 : 2}]>}
        -> i1, !qcore.qubit, i1, !qcore.qubit, i1 {
    ^bb0(%q0_b: !qcore.qubit, %q1_b: !qcore.qubit):
        %i0, %i1, %i2 = "test.op"() : () -> (i1, i1, i1)
        qstruct.yield %i0, %q0_b, %i1, %q1_b, %i2 : i1, !qcore.qubit, i1, !qcore.qubit, i1
    }
}
// CHECK:      builtin.module {
// CHECK-NEXT:     %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:     [[S0:%[\w\d_]+]] = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S1:%[\w\d_]+]] = stab.state.make(%q1 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     [[S2:%[\w\d_]+]] = stab.state.concatenate([[S0]], [[S1]] : !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:         !stab.state<1 x !qcore.qubit, []>) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     [[S3:%[\w\d_]+]], [[M0:%[\w\d_]+]], [[M1:%[\w\d_]+]], [[M2:%[\w\d_]+]] =
// CHECK-SAME:         stab.circuit [[S2]] : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:       with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:         %i0, %i1, %i2 = "test.op"() : () -> (i1, i1, i1)
// CHECK-NEXT:         stab.yield [] %i0, %i1, %i2 : i1, i1, i1
// CHECK-NEXT:       } {stab.flows = #stab.concrete_flow_array<[
// CHECK-SAME:           <+:1, 2, 3>{I -> X0 X1 : 2}, <+:2>{I -> X0 : 2}, <+:3>{I -> X1 : 2}]>}

// ----

// Registers flattened through qstruct.parallel inside circuit

builtin.module {
    %r0, %r1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2>
    %r2 = qstruct.circuit(%r0, %r1 : !qcore.qubit_reg<2>, !qcore.qubit_reg<2>) -> !qcore.qubit_reg<4> {
    ^bb0(%r0_b: !qcore.qubit_reg<2>, %r1_b: !qcore.qubit_reg<2>):
        %q0, %q1, %q6, %q7 = qstruct.parallel<BOTTOM> -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
            %q2, %q3 = qcore.unpack_qubit_reg(%r0_b : !qcore.qubit_reg<2>)
            qref.gate<#qcore.gate.x> (%q2)
            qstruct.yield %q3, %q2 : !qcore.qubit, !qcore.qubit
        } {
            %q4, %q5 = qcore.unpack_qubit_reg(%r1_b : !qcore.qubit_reg<2>)
            qref.gate<#qcore.gate.x> (%q4)
            qstruct.yield %q5, %q4 : !qcore.qubit, !qcore.qubit
        }
        %r3 = qcore.pack_qubit_reg(%q0, %q1, %q6, %q7) -> !qcore.qubit_reg<4>
        qstruct.yield %r3 : !qcore.qubit_reg<4>
    }
}
// CHECK:      builtin.module {
// CHECK-NEXT:     %r0, %r1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2>
// CHECK-NEXT:     [[R0Q0:%[\w\d_]+]], [[R0Q1:%[\w\d_]+]] = qcore.unpack_qubit_reg(%r0 : !qcore.qubit_reg<2>)
// CHECK-NEXT:     [[R0:%[\w\d_]+]] = stab.state.make([[R0Q0]], [[R0Q1]] : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     [[R1Q0:%[\w\d_]+]], [[R1Q1:%[\w\d_]+]] = qcore.unpack_qubit_reg(%r1 : !qcore.qubit_reg<2>)
// CHECK-NEXT:     [[R1:%[\w\d_]+]] = stab.state.make([[R1Q0]], [[R1Q1]] : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     [[S0:%[\w\d_]+]] = stab.state.concatenate([[R0]], [[R1]] : !stab.state<2 x !qcore.qubit, []>,
// CHECK-SAME:         !stab.state<2 x !qcore.qubit, []>) -> !stab.state<4 x !qcore.qubit, []>
// CHECK-NEXT:     [[S1:%[\w\d_]+]] = stab.circuit [[S0]] : !stab.state<4 x !qcore.qubit, []>
// CHECK-SAME:                                           -> !stab.state<4 x !qcore.qubit, []>
// CHECK-NEXT:       with ([[Q0:%[\w\d_]+]], [[Q1:%[\w\d_]+]], [[Q2:%[\w\d_]+]],
// CHECK-SAME:             [[Q3:%[\w\d_]+]] : !qcore.qubit), (){
// CHECK-NEXT:         %q0, %q1, %q6, %q7 = qstruct.parallel<BOTTOM> -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:           qref.gate<#qcore.gate.x> ([[Q0]])
// CHECK-NEXT:           qstruct.yield [[Q1]], [[Q0]] : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:         } {
// CHECK-NEXT:           qref.gate<#qcore.gate.x> ([[Q2]])
// CHECK-NEXT:           qstruct.yield [[Q3]], [[Q2]] : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:         }
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       }
// CHECK-NEXT: }
