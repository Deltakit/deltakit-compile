// RUN: ROUNDTRIP_MLIR

// Aliases for the patch's type and the type it becomes when it's rotated
!lq_patch_type = !log_asm.patch.rot_planar<size=(5,5), location=(1.0, 1.0), orient=v_z>
!rot_patch_type = !log_asm.patch.rot_planar<size=(5,5), location=(1.0, 1.0), orient=h_z>

builtin.module {
    %lq = log_asm.patch_dec -> !lq_patch_type
    %lq_p = log_asm.prepare<Z> (%lq : !lq_patch_type)
    %lq_h = log_asm.transversal<H> (%lq_p : !lq_patch_type) -> !rot_patch_type
    %lq_rot = log_asm.rotate<5> (%lq_h : !rot_patch_type) -> !lq_patch_type
    %r_x = log_asm.measure<X> (%lq_rot : !lq_patch_type) -> i1
}

// CHECK: builtin.module {
// CHECK-NEXT:   %lq = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=v_z>
// CHECK-NEXT:   %lq_p = log_asm.prepare<Z> (%lq : !log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=v_z>)
// CHECK-NEXT:   %lq_h = log_asm.transversal<H> (%lq_p : !log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=v_z>) -> !log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=h_z>
// CHECK-NEXT:   %lq_rot = log_asm.rotate<5> (%lq_h : !log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=h_z>) -> !log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=v_z>
// CHECK-NEXT:   %r_x = log_asm.measure<X> (%lq_rot : !log_asm.patch.rot_planar<size=(5, 5), location=(1.0, 1.0), orient=v_z>) -> i1
// CHECK-NEXT: }
