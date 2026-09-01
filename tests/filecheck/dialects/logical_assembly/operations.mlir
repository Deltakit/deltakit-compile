// RUN: ROUNDTRIP_MLIR

builtin.module {
    %lq = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3)>
    %qreg = log_asm.cast (%lq : !log_asm.patch.rot_planar<size=(3, 3)>) -> !qcore.qubit_reg<17>
}

// CHECK: builtin.module {
// CHECK-NEXT:   %lq = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3)>
// CHECK-NEXT:   %qreg = log_asm.cast(%lq : !log_asm.patch.rot_planar<size=(3, 3)>) -> !qcore.qubit_reg<17>
// CHECK-NEXT: }
