// RUN: deltakit_compile compile-passes -t %s -p split-measurement-tensors -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK:       builtin.module {
    %p0 = "test.op"() : () -> !log_asm.patch.rot_planar<size=(5, 5)>
    %p0_1 = log_asm.cast(%p0 : !log_asm.patch.rot_planar<size=(5, 5)>) -> !qcore.qubit_reg<49>
// CHECK-NEXT:  %p0 = "test.op"() : () -> !log_asm.patch.rot_planar<size=(5, 5)>
// CHECK-NEXT:  %p0_1 = log_asm.cast(%p0 : !log_asm.patch.rot_planar<size=(5, 5)>) -> !qcore.qubit_reg<49>

    %p0_2, %rec = qstruct.circuit(%p0_1 : !qcore.qubit_reg<49>) -> !qcore.qubit_reg<49>, tensor<3xi1> {
    ^bb0(%p0_3 : !qcore.qubit_reg<49>):
// CHECK-NEXT:  %p0_2, %0, %1, %2 = qstruct.circuit(%p0_1 : !qcore.qubit_reg<49>) -> !qcore.qubit_reg<49>, i1, i1, i1 {
// CHECK-NEXT:  ^bb0(%p0_3: !qcore.qubit_reg<49>):

        %q0, %q1, %q2, %q3, %q4, %q5, %q6, %q7, %q8, %q9, %q10, %q11, %q12, %q13, %q14, %q15, %q16, %q17, %q18, %q19, %q20, %q21, %q22, %q23, %q24, %q25, %q26, %q27, %q28, %q29, %q30, %q31, %q32, %q33, %q34, %q35, %q36, %q37, %q38, %q39, %q40, %q41, %q42, %q43, %q44, %q45, %q46, %q47, %q48 = qcore.unpack_qubit_reg(%p0_3 : !qcore.qubit_reg<49>)
        qref.reset<Z> (%q0, %q1, %q2, %q3, %q4, %q5, %q6, %q7, %q8, %q9, %q10, %q11, %q12, %q13, %q14, %q15, %q16, %q17, %q18, %q19, %q20, %q21, %q22, %q23, %q24, %q25, %q26, %q27, %q28, %q29, %q30, %q31, %q32, %q33, %q34, %q35, %q36, %q37, %q38, %q39, %q40, %q41, %q42, %q43, %q44, %q45, %q46, %q47, %q48)
        qref.gate<#qcore.gate.h> (%q0)
        qref.gate<#qcore.gate.cx> (%q0, %q3)
// CHECK-NEXT:    %q0, %q1, %q2, %q3, %q4, %q5, %q6, %q7, %q8, %q9, %q10, %q11, %q12, %q13, %q14, %q15, %q16, %q17, %q18, %q19, %q20, %q21, %q22, %q23, %q24, %q25, %q26, %q27, %q28, %q29, %q30, %q31, %q32, %q33, %q34, %q35, %q36, %q37, %q38, %q39, %q40, %q41, %q42, %q43, %q44, %q45, %q46, %q47, %q48 = qcore.unpack_qubit_reg(%p0_3 : !qcore.qubit_reg<49>)
// CHECK-NEXT:    qref.reset<Z> (%q0, %q1, %q2, %q3, %q4, %q5, %q6, %q7, %q8, %q9, %q10, %q11, %q12, %q13, %q14, %q15, %q16, %q17, %q18, %q19, %q20, %q21, %q22, %q23, %q24, %q25, %q26, %q27, %q28, %q29, %q30, %q31, %q32, %q33, %q34, %q35, %q36, %q37, %q38, %q39, %q40, %q41, %q42, %q43, %q44, %q45, %q46, %q47, %q48)
// CHECK-NEXT:    qref.gate<#qcore.gate.h> (%q0)
// CHECK-NEXT:    qref.gate<#qcore.gate.cx> (%q0, %q3)

        %m0, %m1, %m2 = qref.measure<Z>(%q0, %q2, %q4) -> i1, i1, i1
        %rec_1 = tensor.from_elements %m0, %m1, %m2 : tensor<3xi1>
// CHECK-NEXT:    %m0, %m1, %m2 = qref.measure<Z> (%q0, %q2, %q4) -> i1, i1, i1

        %c0 = arith.constant 0 : index
        %len = tensor.dim %rec, %c0 : tensor<3xi1>
        %c1 = arith.constant 1 : index
        %last_index = arith.subi %len, %c1 : index
        %m2_1 = tensor.extract %rec_1[%last_index] : tensor<3xi1>
        qec.detector(%m2_1)
// CHECK-NEXT:    %3 = qec.detector(%m2)

        qstruct.yield %p0_3, %rec_1 : !qcore.qubit_reg<49>, tensor<3xi1>
    }
// CHECK-NEXT:    qstruct.yield %p0_3, %m0, %m1, %m2 : !qcore.qubit_reg<49>, i1, i1, i1
// CHECK-NEXT:  }

    %p0_3, %rec_3 = qstruct.circuit(%p0_2, %rec : !qcore.qubit_reg<49>, tensor<3xi1>) -> !qcore.qubit_reg<49>, tensor<4xi1> {
    ^bb0(%p0_4 : !qcore.qubit_reg<49>, %rec_2 : tensor<3xi1>):
        %q0, %q1, %q2, %q3, %q4, %q5, %q6, %q7, %q8, %q9, %q10, %q11, %q12, %q13, %q14, %q15, %q16, %q17, %q18, %q19, %q20, %q21, %q22, %q23, %q24, %q25, %q26, %q27, %q28, %q29, %q30, %q31, %q32, %q33, %q34, %q35, %q36, %q37, %q38, %q39, %q40, %q41, %q42, %q43, %q44, %q45, %q46, %q47, %q48 = qcore.unpack_qubit_reg(%p0_4 : !qcore.qubit_reg<49>)
// CHECK-NEXT:  %p0_3, %m0, %m1, %m2, %m3 = qstruct.circuit(%p0_2, %0, %1, %2 : !qcore.qubit_reg<49>, i1, i1, i1) -> !qcore.qubit_reg<49>, i1, i1, i1, i1 {
// CHECK-NEXT:  ^bb0(%p0_4: !qcore.qubit_reg<49>, %3: i1, %m1_1: i1, %4: i1):
// CHECK-NEXT:    %q0, %q1, %q2, %q3, %q4, %q5, %q6, %q7, %q8, %q9, %q10, %q11, %q12, %q13, %q14, %q15, %q16, %q17, %q18, %q19, %q20, %q21, %q22, %q23, %q24, %q25, %q26, %q27, %q28, %q29, %q30, %q31, %q32, %q33, %q34, %q35, %q36, %q37, %q38, %q39, %q40, %q41, %q42, %q43, %q44, %q45, %q46, %q47, %q48 = qcore.unpack_qubit_reg(%p0_4 : !qcore.qubit_reg<49>)



        %m3 = qref.measure<Z>(%q2) -> i1
        %rec_add_1 = tensor.from_elements %m3 : tensor<1xi1>
        %rec_4 = tensor.concat dim(0) %rec_2, %rec_add_1 : (tensor<3xi1>, tensor<1xi1>) -> tensor<4xi1>
// CHECK-NEXT:    %m3_1 = qref.measure<Z> (%q2) -> i1

        %rec_middle = "tensor.extract_slice"(%rec_4) <{"static_offsets" = array<i64: 1>, "static_sizes" = array<i64: 2>, "static_strides" = array<i64: 1>, operandSegmentSizes = array<i32: 1, 0, 0, 0>}> : (tensor<4xi1>) -> tensor<2xi1>
        %c0 = arith.constant 0 : index
        %m1 = tensor.extract %rec_middle[%c0] : tensor<2xi1>
        qec.detector(%m1, %m3)
// CHECK-NEXT:    %5 = qec.detector(%m1_1, %m3_1)

        qstruct.yield %p0_4, %rec_4 : !qcore.qubit_reg<49>, tensor<4xi1>
    }
// CHECK-NEXT:    qstruct.yield %p0_4, %3, %m1_1, %4, %m3_1 : !qcore.qubit_reg<49>, i1, i1, i1, i1
// CHECK-NEXT:  }

    %c0 = arith.constant 0 : index
    %m0 = tensor.extract %rec_3[%c0] : tensor<4xi1>
    %c1 = arith.constant 1 : index
    %m1 = tensor.extract %rec_3[%c1] : tensor<4xi1>
    %c2 = arith.constant 2 : index
    %m2 = tensor.extract %rec_3[%c2] : tensor<4xi1>
    %c3 = arith.constant 3 : index
    %m3 = tensor.extract %rec_3[%c3] : tensor<4xi1>
    qstruct.output(%m0, %m1, %m2, %m3 : i1, i1, i1, i1)
}
// CHECK-NEXT:  qstruct.output(%m0, %m1, %m2, %m3 : i1, i1, i1, i1)
// CHECK-NEXT:  }
