// RUN: deltakit_compile compile-passes %s -p circuit-builder-to-logasm-pipeline --pass-args '{"verify_between_passes": true}' -O %t && filecheck %s --input-file %t

builtin.module {
}
// CHECK:       builtin.module {
// CHECK-NEXT:  }

// ----
// CHECK: ----

builtin.module {
    %0 = qcore.alloc_qubit -> !qcore.qubit_reg<4>

    %qreg = log_asm_api.cast(%0 : !qcore.qubit_reg<4>) -> tensor<4x!qcore.qubit>
    %1, %2 = log_asm_api.tensor_slice(%qreg[:2:]) : tensor<4x!qcore.qubit> -> tensor<2x!qcore.qubit>, tensor<2x!qcore.qubit>
    %b, %qreg_1 = log_asm_api.call @circ(%1) : (tensor<2x!qcore.qubit>) -> (i1, tensor<2x!qcore.qubit>)
    %3 = log_asm_api.tensor_merge<[:2:]>(%qreg_1 : tensor<2x!qcore.qubit>, %2 : tensor<2x!qcore.qubit>) -> tensor<4x!qcore.qubit>

    %4, %5 = log_asm_api.tensor_slice(%3[2::]) : tensor<4x!qcore.qubit> -> tensor<2x!qcore.qubit>, tensor<2x!qcore.qubit>
    %b_1, %qreg_2 = log_asm_api.call @circ(%4) : (tensor<2x!qcore.qubit>) -> (i1, tensor<2x!qcore.qubit>)
    %6 = log_asm_api.tensor_merge<[2::]>(%qreg_2 : tensor<2x!qcore.qubit>, %5 : tensor<2x!qcore.qubit>) -> tensor<4x!qcore.qubit>

    qstruct.output(%b, %b_1 : i1, i1)

    log_asm_api.circuit_dec @circ(%qreg_3: tensor<2x!qcore.qubit>) -> (i1, tensor<2x!qcore.qubit>) {
        log_asm_api.unsized_gate<#qcore.gate.x> (%qreg_3 : tensor<2x!qcore.qubit>)
        %7, %8 = log_asm_api.tensor_slice(%qreg_3[0:1:1]) : tensor<2x!qcore.qubit> -> tensor<1x!qcore.qubit>, tensor<1x!qcore.qubit>
        %9 = arith.constant 0 : index
        %10 = tensor.extract %7[%9] : tensor<1x!qcore.qubit>
        %b_2 = qref.measure<Z> (%10) -> i1
        log_asm_api.return %b_2, %qreg_3 : i1, tensor<2x!qcore.qubit>
    }
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %0 = qcore.alloc_qubit -> !qcore.qubit_reg<4>
// CHECK-NEXT:    %1, %2, %3, %4 = qcore.unpack_qubit_reg(%0 : !qcore.qubit_reg<4>)
// CHECK-NEXT:    %5 = qcore.pack_qubit_reg(%1, %2) -> !qcore.qubit_reg<2>
// CHECK-NEXT:    %6 = qcore.pack_qubit_reg(%3, %4) -> !qcore.qubit_reg<2>
// CHECK-NEXT:    %b, %qreg = qstruct.circuit(%5 : !qcore.qubit_reg<2>) -> i1, !qcore.qubit_reg<2> {
// CHECK-NEXT:    ^bb0(%qreg_1: !qcore.qubit_reg<2>):
// CHECK-NEXT:      %7, %8 = qcore.unpack_qubit_reg(%qreg_1 : !qcore.qubit_reg<2>)
// CHECK-NEXT:      qref.gate<#qcore.gate.x> (%7, %8)
// CHECK-NEXT:      %9 = qcore.pack_qubit_reg(%7) -> !qcore.qubit_reg<1>
// CHECK-NEXT:      %10 = qcore.unpack_qubit_reg(%9 : !qcore.qubit_reg<1>)
// CHECK-NEXT:      %b_1 = qref.measure<Z> (%10) -> i1
// CHECK-NEXT:      qstruct.yield %b_1, %qreg_1 : i1, !qcore.qubit_reg<2>
// CHECK-NEXT:    }
// CHECK-NEXT:    %7, %8 = qcore.unpack_qubit_reg(%qreg : !qcore.qubit_reg<2>)
// CHECK-NEXT:    %9, %10 = qcore.unpack_qubit_reg(%6 : !qcore.qubit_reg<2>)
// CHECK-NEXT:    %11 = qcore.pack_qubit_reg(%7, %8, %9, %10) -> !qcore.qubit_reg<4>
// CHECK-NEXT:    %12, %13, %14, %15 = qcore.unpack_qubit_reg(%11 : !qcore.qubit_reg<4>)
// CHECK-NEXT:    %16 = qcore.pack_qubit_reg(%14, %15) -> !qcore.qubit_reg<2>
// CHECK-NEXT:    %b_1, %qreg_1 = qstruct.circuit(%16 : !qcore.qubit_reg<2>) -> i1, !qcore.qubit_reg<2> {
// CHECK-NEXT:    ^bb0(%qreg_2: !qcore.qubit_reg<2>):
// CHECK-NEXT:      %17, %18 = qcore.unpack_qubit_reg(%qreg_2 : !qcore.qubit_reg<2>)
// CHECK-NEXT:      qref.gate<#qcore.gate.x> (%17, %18)
// CHECK-NEXT:      %19 = qcore.pack_qubit_reg(%17) -> !qcore.qubit_reg<1>
// CHECK-NEXT:      %20 = qcore.unpack_qubit_reg(%19 : !qcore.qubit_reg<1>)
// CHECK-NEXT:      %b_2 = qref.measure<Z> (%20) -> i1
// CHECK-NEXT:      qstruct.yield %b_2, %qreg_2 : i1, !qcore.qubit_reg<2>
// CHECK-NEXT:    }
// CHECK-NEXT:    qstruct.output(%b, %b_1 : i1, i1)
// CHECK-NEXT:  }
