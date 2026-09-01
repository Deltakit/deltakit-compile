// RUN: deltakit_compile compile-passes %s -p stabiliser-flow-pipeline --pass-args '{"verify_between_passes": true}' -O %t && filecheck %s --input-file %t
//
// This test feeds the *already annotated* repetition-code circuit (with qec.detector ops in the
// body and flow annotations on the qstruct.circuit) through the stabiliser-flow-pipeline and checks
// the pipeline is idempotent (i.e. it produces the same IR back).

builtin.module {
    %qa = qcore.alloc_qubit<coords=[(0.0, 0.0)]> -> !qcore.qubit
    %qd1 = qcore.alloc_qubit<coords=[(1.0, 0.0)]> -> !qcore.qubit
    %qd2 = qcore.alloc_qubit<coords=[(2.0, 0.0)]> -> !qcore.qubit
    %0 = qcore.pack_qubit_reg(%qa, %qd1, %qd2) -> !qcore.qubit_reg<3>
    %1 = qstruct.circuit(%0 : !qcore.qubit_reg<3>) -> !qcore.qubit_reg<3> {
    ^bb0(%2: !qcore.qubit_reg<3>):
        %qa_b, %qd1_b, %qd2_b = qcore.unpack_qubit_reg(%2 : !qcore.qubit_reg<3>)
        qref.reset<Z> (%qd1_b, %qd2_b)
        qref.reset<Z> (%qa_b)
        qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
        qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
        %m1_b = qref.measure<Z> (%qa_b) -> i1
        %3 = qec.detector<[0.0, 0.0]> (%m1_b)
        qref.reset<Z> (%qa_b)
        qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
        qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
        %m2_b = qref.measure<Z> (%qa_b) -> i1
        %4 = qec.detector<[0.0, 0.0]> (%m1_b, %m2_b)
        qref.reset<Z> (%qa_b)
        qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
        qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
        %m3_b = qref.measure<Z> (%qa_b) -> i1
        %5 = qec.detector<[0.0, 0.0]> (%m2_b, %m3_b)
        %m4_b = qref.measure<Z> (%qd1_b) -> i1
        %m5_b = qref.measure<Z> (%qd2_b) -> i1
        %6 = qec.detector<[1.0, 0.0]> (%m3_b, %m4_b, %m5_b)
        %7 = qec.detector<[1.0, 0.0]> (%m4_b)
        %8 = qcore.pack_qubit_reg(%qa_b, %qd1_b, %qd2_b) -> !qcore.qubit_reg<3>
        qstruct.yield %8 : !qcore.qubit_reg<3>
    }
}

// CHECK:      builtin.module {
// CHECK-NEXT:     %qa = qcore.alloc_qubit<coords = [(0.0, 0.0)]> -> !qcore.qubit
// CHECK-NEXT:     %qd1 = qcore.alloc_qubit<coords = [(1.0, 0.0)]> -> !qcore.qubit
// CHECK-NEXT:     %qd2 = qcore.alloc_qubit<coords = [(2.0, 0.0)]> -> !qcore.qubit
// CHECK-NEXT:     %0 = qcore.pack_qubit_reg(%qa, %qd1, %qd2) -> !qcore.qubit_reg<3>
// CHECK-NEXT:     %1 = qstruct.circuit(%0 : !qcore.qubit_reg<3>) -> !qcore.qubit_reg<3> {
// CHECK-NEXT:     ^bb0(%2: !qcore.qubit_reg<3>):
// CHECK-NEXT:         %qa_b, %qd1_b, %qd2_b = qcore.unpack_qubit_reg(%2 : !qcore.qubit_reg<3>)
// CHECK-NEXT:         qref.reset<Z> (%qd1_b, %qd2_b)
// CHECK-NEXT:         qref.reset<Z> (%qa_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
// CHECK-NEXT:         %m1_b = qref.measure<Z> (%qa_b) -> i1
// CHECK-NEXT:         %3 = qec.detector<[0.0, 0.0]> (%m1_b)
// CHECK-NEXT:         qref.reset<Z> (%qa_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
// CHECK-NEXT:         %m2_b = qref.measure<Z> (%qa_b) -> i1
// CHECK-NEXT:         %4 = qec.detector<[0.0, 0.0]> (%m1_b, %m2_b)
// CHECK-NEXT:         qref.reset<Z> (%qa_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
// CHECK-NEXT:         %m3_b = qref.measure<Z> (%qa_b) -> i1
// CHECK-NEXT:         %5 = qec.detector<[0.0, 0.0]> (%m2_b, %m3_b)
// CHECK-NEXT:         %m4_b = qref.measure<Z> (%qd1_b) -> i1
// CHECK-NEXT:         %m5_b = qref.measure<Z> (%qd2_b) -> i1
// CHECK-NEXT:         %6 = qec.detector<[1.0, 0.0]> (%m3_b, %m4_b, %m5_b)
// CHECK-NEXT:         %7 = qec.detector<[1.0, 0.0]> (%m4_b)
// CHECK-NEXT:         qstruct.yield %2 : !qcore.qubit_reg<3>
// CHECK-NEXT:     }
// CHECK-NEXT: }
