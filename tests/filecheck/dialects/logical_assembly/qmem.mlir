// RUN: ROUNDTRIP_MLIR

// Alias for patch type with parameters (rotated planar code, Z logical is vertical,
// located at coordinate (1, 1), size is 5 x 5).
!lq_patch_type = !log_asm.patch.rot_planar<size=(3,3), location=(1.0, 1.0), orient=v_z>

builtin.module {
    // Declare the parameterised patch
    %lq = log_asm.patch_dec -> !lq_patch_type
    // Initialise the patch in the Z basis
    %lq_p = log_asm.prepare<Z> (%lq : !lq_patch_type)
    // Measure stabilizer for 20 rounds.
    %lq_m = log_asm.meas_stab<20> (%lq_p : !lq_patch_type)
    // Measure patch in the Z basis
    %r_z = log_asm.measure<Z> (%lq_m : !lq_patch_type) -> i1
}

// CHECK: builtin.module {
// CHECK-NEXT:   %lq = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(1.0, 1.0), orient=v_z>
// CHECK-NEXT:   %lq_p = log_asm.prepare<Z> (%lq : !log_asm.patch.rot_planar<size=(3, 3), location=(1.0, 1.0), orient=v_z>)
// CHECK-NEXT:   %lq_m = log_asm.meas_stab<20> (%lq_p : !log_asm.patch.rot_planar<size=(3, 3), location=(1.0, 1.0), orient=v_z>)
// CHECK-NEXT:   %r_z = log_asm.measure<Z> (%lq_m : !log_asm.patch.rot_planar<size=(3, 3), location=(1.0, 1.0), orient=v_z>) -> i1
// CHECK-NEXT: }
