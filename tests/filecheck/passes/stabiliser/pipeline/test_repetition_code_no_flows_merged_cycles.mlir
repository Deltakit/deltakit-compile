// RUN: deltakit_compile compile-passes %s -p stabiliser-flow-pipeline --pass-args '{"verify_between_passes": true}' -O %t && filecheck %s --input-file %t
// d=2 repetition code memory experiment run for 3 cycles, with no input flow annotations.
//
// This test ensures the stabiliser-flow-pipeline merges *all* rounds of syndrome extraction
// into a single qstruct.circuit op (i.e. there is exactly one qstruct.circuit in the output).

// Note that the generated detectors are not necessarily optimal but are correct and form a complete
// basis for the space of valid detectors.

builtin.module {
    %qa = qcore.alloc_qubit<coords=[(0.0, 0.0)]> -> !qcore.qubit
    %qd1 = qcore.alloc_qubit<coords=[(1.0, 0.0)]> -> !qcore.qubit
    %qd2 = qcore.alloc_qubit<coords=[(2.0, 0.0)]> -> !qcore.qubit

    %state0 = stab.state.make(%qa, %qd1, %qd2 : !qcore.qubit) -> !stab.state<3 x !qcore.qubit, []>

    // Initial reset layer.
    %qa_1, %qd1_1, %qd2_1 = qstruct.circuit(%qa, %qd1, %qd2 : !qcore.qubit, !qcore.qubit, !qcore.qubit)
        -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
    ^bb0(%qa_b: !qcore.qubit, %qd1_b: !qcore.qubit, %qd2_b: !qcore.qubit):
        qref.reset<Z> (%qd1_b, %qd2_b)
        qstruct.yield %qa_b, %qd1_b, %qd2_b : !qcore.qubit, !qcore.qubit, !qcore.qubit
    }

    // 3 syndrome extraction cycles.
    %qa_2, %qd1_2, %qd2_2 = qstruct.circuit(%qa_1, %qd1_1, %qd2_1 : !qcore.qubit, !qcore.qubit, !qcore.qubit)
        -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
    ^bb0(%qa_b: !qcore.qubit, %qd1_b: !qcore.qubit, %qd2_b: !qcore.qubit):
        // round 1
        qref.reset<Z> (%qa_b)
        qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
        qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
        %m1_b = qref.measure<Z> (%qa_b) -> i1
        // round 2
        qref.reset<Z> (%qa_b)
        qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
        qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
        %m2_b = qref.measure<Z> (%qa_b) -> i1
        // round 3
        qref.reset<Z> (%qa_b)
        qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
        qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
        %m3_b = qref.measure<Z> (%qa_b) -> i1
        qstruct.yield %qa_b, %qd1_b, %qd2_b : !qcore.qubit, !qcore.qubit, !qcore.qubit
    }

    // Final measurement layer.
    %qa_3, %qd1_3, %qd2_3 = qstruct.circuit(%qa_2, %qd1_2, %qd2_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit)
        -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
    ^bb0(%qa_b: !qcore.qubit, %qd1_b: !qcore.qubit, %qd2_b: !qcore.qubit):
        %m4_b = qref.measure<Z> (%qd1_b) -> i1
        %m5_b = qref.measure<Z> (%qd2_b) -> i1
        qstruct.yield %qa_b, %qd1_b, %qd2_b : !qcore.qubit, !qcore.qubit, !qcore.qubit
    }
}

// CHECK:      builtin.module {
// CHECK-NEXT:     %qa = qcore.alloc_qubit<coords = [(0.0, 0.0)]> -> !qcore.qubit
// CHECK-NEXT:     %qd1 = qcore.alloc_qubit<coords = [(1.0, 0.0)]> -> !qcore.qubit
// CHECK-NEXT:     %qd2 = qcore.alloc_qubit<coords = [(2.0, 0.0)]> -> !qcore.qubit
// CHECK-NEXT:     [[R0:%[\w\d_]+]] = qcore.pack_qubit_reg(%qa, %qd1, %qd2) -> !qcore.qubit_reg<3>
// CHECK-NEXT:     [[R1:%[\w\d_]+]] = qstruct.circuit([[R0]] : !qcore.qubit_reg<3>) -> !qcore.qubit_reg<3> {
// CHECK-NEXT:     ^bb0([[R2:%[\w\d_]+]]: !qcore.qubit_reg<3>):
// CHECK-NEXT:         %qa_b, %qd1_b, %qd2_b = qcore.unpack_qubit_reg([[R2]] : !qcore.qubit_reg<3>)
// CHECK-NEXT:         qref.reset<Z> (%qd1_b, %qd2_b)
// CHECK-NEXT:         qref.reset<Z> (%qa_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
// CHECK-NEXT:         %m1_b = qref.measure<Z> (%qa_b) -> i1
// CHECK-NEXT:         qref.reset<Z> (%qa_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
// CHECK-NEXT:         %m2_b = qref.measure<Z> (%qa_b) -> i1
// CHECK-NEXT:         qref.reset<Z> (%qa_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
// CHECK-NEXT:         %m3_b = qref.measure<Z> (%qa_b) -> i1
// CHECK-DAG:          [[D1:%[\w\d_]+]] = qec.detector<[0.0, 0.0]> (%m1_b, %m2_b)
// CHECK-DAG:          [[D2:%[\w\d_]+]] = qec.detector<[0.0, 0.0]> (%m1_b, %m3_b)
// CHECK-DAG:          [[D3:%[\w\d_]+]] = qec.detector<[0.0, 0.0]> (%m1_b)
// CHECK-NEXT:         %m4_b = qref.measure<Z> (%qd1_b) -> i1
// CHECK-NEXT:         %m5_b = qref.measure<Z> (%qd2_b) -> i1
// CHECK-NEXT:         [[D4:%[\w\d_]+]] = qec.detector<[1.0, 0.0]> (%m1_b, %m5_b, %m4_b)
// CHECK-NEXT:         [[D5:%[\w\d_]+]] = qec.detector<[2.0, 0.0]> (%m5_b)
// CHECK-NEXT:         qstruct.yield [[R2]] : !qcore.qubit_reg<3>
// CHECK-NEXT:     }
// CHECK-NEXT: }
