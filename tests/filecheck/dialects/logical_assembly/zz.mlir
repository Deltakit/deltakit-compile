// RUN: ROUNDTRIP_MLIR

// Alias patch types for all patches in the program
!lq0_patch_type = !log_asm.patch.rot_planar<size=(5,5), location=(0.0,0.0), orient=v_z>
!lq1_patch_type = !log_asm.patch.rot_planar<size=(5,5), location=(10.0,0.0), orient=v_z>
!bridge_patch_type = !log_asm.patch.rot_planar<size=(5,5), location=(5.0,0.0), orient=v_z>

builtin.module {
    %lq0 = log_asm.patch_dec -> !lq0_patch_type
    %lq1 = log_asm.patch_dec -> !lq1_patch_type
    %lq0_p = log_asm.prepare<Z> (%lq0 : !lq0_patch_type)
    %lq1_p = log_asm.prepare<Z> (%lq1 : !lq1_patch_type)
    %lq0_s = log_asm.meas_stab<5> (%lq0_p : !lq0_patch_type)
    %lq1_s = log_asm.meas_stab<5> (%lq1_p : !lq1_patch_type)

    %bridge = log_asm.patch_dec -> !bridge_patch_type
    %r_zz, %lq0_m, %lq1_m = log_asm.multi_pauli_meas<5, (Z, Z)> (%lq0_s, %lq1_s :
                !lq0_patch_type, !lq1_patch_type) (%bridge : !bridge_patch_type) -> i1

    %lq0_s2 = log_asm.meas_stab<5> (%lq0_m : !lq0_patch_type)
    %lq1_s2 = log_asm.meas_stab<5> (%lq1_m : !lq1_patch_type)
    %r_z0 = log_asm.measure<Z> (%lq0_s2 : !lq0_patch_type) -> i1
    %r_z1 = log_asm.measure<Z> (%lq1_s2 : !lq1_patch_type) -> i1
}

// CHECK:       builtin.module {
// CHECK-NEXT:      %lq0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=v_z>
// CHECK-NEXT:      %lq1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5, 5), location=(10.0, 0.0), orient=v_z>
// CHECK-NEXT:      %lq0_p = log_asm.prepare<Z> (%lq0 : !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:      %lq1_p = log_asm.prepare<Z> (%lq1 : !log_asm.patch.rot_planar<size=(5, 5), location=(10.0, 0.0), orient=v_z>)
// CHECK-NEXT:      %lq0_s = log_asm.meas_stab<5> (%lq0_p : !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:      %lq1_s = log_asm.meas_stab<5> (%lq1_p : !log_asm.patch.rot_planar<size=(5, 5), location=(10.0, 0.0), orient=v_z>)

// CHECK:           %bridge = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5, 5), location=(5.0, 0.0), orient=v_z>
// CHECK-NEXT:      %r_zz, %lq0_m, %lq1_m = log_asm.multi_pauli_meas<5, (Z, Z)> (%lq0_s, %lq1_s :
// CHECK-SAME:          !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=v_z>, !log_asm.patch.rot_planar<size=(5, 5), location=(10.0, 0.0), orient=v_z>)
// CHECK-SAME:          (%bridge : !log_asm.patch.rot_planar<size=(5, 5), location=(5.0, 0.0), orient=v_z>) -> i1

// CHECK:           %lq0_s2 = log_asm.meas_stab<5> (%lq0_m : !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:      %lq1_s2 = log_asm.meas_stab<5> (%lq1_m : !log_asm.patch.rot_planar<size=(5, 5), location=(10.0, 0.0), orient=v_z>)
// CHECK-NEXT:      %r_z0 = log_asm.measure<Z> (%lq0_s2 : !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=v_z>) -> i1
// CHECK-NEXT:      %r_z1 = log_asm.measure<Z> (%lq1_s2 : !log_asm.patch.rot_planar<size=(5, 5), location=(10.0, 0.0), orient=v_z>) -> i1
// CHECK-NEXT:  }
