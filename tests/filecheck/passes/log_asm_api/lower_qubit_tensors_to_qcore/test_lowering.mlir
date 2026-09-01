// RUN: deltakit_compile compile-passes -t %s -p lower-qubit-tensors-to-qcore -O %t && filecheck %s --input-file %t


// Test simple cases
builtin.module {
    // CHECK:       builtin.module {
    %p0 = "test.op"() : () -> (!log_asm.patch.rot_planar<size=(5, 5)>)
// CHECK-NEXT:    %p0 = "test.op"() : () -> !log_asm.patch.rot_planar<size=(5, 5)>
    %p0_1 = log_asm_api.cast(%p0 : !log_asm.patch.rot_planar<size=(5, 5)>) -> tensor<?x!qcore.qubit>
// CHECK-NEXT:    %p0_1 = log_asm.cast(%p0 : !log_asm.patch.rot_planar<size=(5, 5)>) -> !qcore.qubit_reg<49>

    %p0_3 = qstruct.circuit(%p0_1 : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
// CHECK-NEXT:    %p0_2 = qstruct.circuit(%p0_1 : !qcore.qubit_reg<49>) -> !qcore.qubit_reg<49> {
    ^bb0(%p0_2 : tensor<?x!qcore.qubit>):
// CHECK-NEXT:    ^bb0(%p0_3: !qcore.qubit_reg<49>):
// CHECK-NEXT:      %q0, %q0_1, %q0_2, %q0_3, %q0_4, %q0_5, %q0_6, %q0_7, %q0_8, %q0_9, %q0_10, %q0_11, %q0_12, %q0_13, %q0_14, %q0_15, %q0_16, %q0_17, %q0_18, %q0_19, %q0_20, %q0_21, %q0_22, %q0_23, %q0_24, %q0_25, %q0_26, %q0_27, %q0_28, %q0_29, %q0_30, %q0_31, %q0_32, %q0_33, %q0_34, %q0_35, %q0_36, %q0_37, %q0_38, %q0_39, %q0_40, %q0_41, %q0_42, %q0_43, %q0_44, %q0_45, %q0_46, %q0_47, %q0_48 = qcore.unpack_qubit_reg(%p0_3 : !qcore.qubit_reg<49>)

        log_asm_api.unsized_reset<Z>(%p0_2 : tensor<?x!qcore.qubit>)
// CHECK-NEXT:      qref.reset<Z> (%q0, %q0_1, %q0_2, %q0_3, %q0_4, %q0_5, %q0_6, %q0_7, %q0_8, %q0_9, %q0_10, %q0_11, %q0_12, %q0_13, %q0_14, %q0_15, %q0_16, %q0_17, %q0_18, %q0_19, %q0_20, %q0_21, %q0_22, %q0_23, %q0_24, %q0_25, %q0_26, %q0_27, %q0_28, %q0_29, %q0_30, %q0_31, %q0_32, %q0_33, %q0_34, %q0_35, %q0_36, %q0_37, %q0_38, %q0_39, %q0_40, %q0_41, %q0_42, %q0_43, %q0_44, %q0_45, %q0_46, %q0_47, %q0_48)

        %c0 = arith.constant 0 : index
        %q0 = tensor.extract %p0_2[%c0] : tensor<?x!qcore.qubit>
        qref.gate<#qcore.gate.h>(%q0)
// CHECK-NEXT:      qref.gate<#qcore.gate.h> (%q0)

        %c0_1 = arith.constant 0 : index
        %q0_1 = tensor.extract %p0_2[%c0_1] : tensor<?x!qcore.qubit>
        %c3 = arith.constant 3 : index
        %q3 = tensor.extract %p0_2[%c3] : tensor<?x!qcore.qubit>
        qref.gate<#qcore.gate.cx(%q0_1, %q3)
// CHECK-NEXT:      qref.gate<#qcore.gate.cx> (%q0, %q0_3)

        qstruct.yield %p0_2 : tensor<?x!qcore.qubit>
// CHECK-NEXT:      qstruct.yield %p0_3 : !qcore.qubit_reg<49>
    }
// CHECK-NEXT:    }

    %p0_4 = log_asm_api.cast(%p0_3 : tensor<?x!qcore.qubit>) -> !log_asm.patch.rot_planar<size=(5, 5)>
// CHECK-NEXT:    %p0_3 = log_asm.cast(%p0_2 : !qcore.qubit_reg<49>) -> !log_asm.patch.rot_planar<size=(5, 5)>
    "test.op"(%p0_4) : (!log_asm.patch.rot_planar<size=(5, 5)>) -> ()
// CHECK-NEXT:    "test.op"(%p0_3) : (!log_asm.patch.rot_planar<size=(5, 5)>) -> ()
}
// CHECK-NEXT:  }
