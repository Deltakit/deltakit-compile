// RUN: deltakit_compile compile-passes -t %s -p parallelise-log-asm-api -O %t && filecheck %s --input-file %t
builtin.module {
  %qreg = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=h_z>
  %qreg_1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5, 5), location=(6.0, 0.0), orient=h_z>
  %qreg_2 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(1, 5), location=(5.0, 0.0), orient=h_z>
  %qreg_3 = log_asm.prepare<Z> (%qreg : !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=h_z>)
  %qreg_4 = log_asm.prepare<Z> (%qreg_1 : !log_asm.patch.rot_planar<size=(5, 5), location=(6.0, 0.0), orient=h_z>)
  %qreg_5 = log_asm.meas_stab<5> (%qreg_3 : !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=h_z>)
  %qreg_6 = log_asm.meas_stab<5> (%qreg_4 : !log_asm.patch.rot_planar<size=(5, 5), location=(6.0, 0.0), orient=h_z>)
  %cexpr, %qreg_7, %qreg_8 = log_asm.multi_pauli_meas<5, (Z, Z)> (%qreg_5, %qreg_6 : !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=h_z>, !log_asm.patch.rot_planar<size=(5, 5), location=(6.0, 0.0), orient=h_z>) (%qreg_2 : !log_asm.patch.rot_planar<size=(1, 5), location=(5.0, 0.0), orient=h_z>) -> i1
  %qreg_9 = log_asm.meas_stab<5> (%qreg_7 : !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=h_z>)
  %qreg_10 = log_asm.meas_stab<5> (%qreg_8 : !log_asm.patch.rot_planar<size=(5, 5), location=(6.0, 0.0), orient=h_z>)
  %cexpr_1 = log_asm.measure<Z> (%qreg_9 : !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=h_z>) -> i1
  %cexpr_2 = log_asm.measure<Z> (%qreg_10 : !log_asm.patch.rot_planar<size=(5, 5), location=(6.0, 0.0), orient=h_z>) -> i1
  qstruct.output(:)
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %qreg, %qreg_1, %qreg_2 = qstruct.parallel<BOTTOM> -> !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=h_z>, !log_asm.patch.rot_planar<size=(5, 5), location=(6.0, 0.0), orient=h_z>, !log_asm.patch.rot_planar<size=(1, 5), location=(5.0, 0.0), orient=h_z> {
// CHECK-NEXT:      %qreg_3 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=h_z>
// CHECK-NEXT:      %qreg_4 = log_asm.prepare<Z> (%qreg_3 : !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=h_z>)
// CHECK-NEXT:      %qreg_5 = log_asm.meas_stab<5> (%qreg_4 : !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=h_z>)
// CHECK-NEXT:      qstruct.yield %qreg_5 : !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=h_z>
// CHECK-NEXT:    } {
// CHECK-NEXT:      %qreg_6 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5, 5), location=(6.0, 0.0), orient=h_z>
// CHECK-NEXT:      %qreg_7 = log_asm.prepare<Z> (%qreg_6 : !log_asm.patch.rot_planar<size=(5, 5), location=(6.0, 0.0), orient=h_z>)
// CHECK-NEXT:      %qreg_8 = log_asm.meas_stab<5> (%qreg_7 : !log_asm.patch.rot_planar<size=(5, 5), location=(6.0, 0.0), orient=h_z>)
// CHECK-NEXT:      qstruct.yield %qreg_8 : !log_asm.patch.rot_planar<size=(5, 5), location=(6.0, 0.0), orient=h_z>
// CHECK-NEXT:    } {
// CHECK-NEXT:      %qreg_9 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(1, 5), location=(5.0, 0.0), orient=h_z>
// CHECK-NEXT:      qstruct.yield %qreg_9 : !log_asm.patch.rot_planar<size=(1, 5), location=(5.0, 0.0), orient=h_z>
// CHECK-NEXT:    }
// CHECK-NEXT:    %cexpr, %qreg_10, %qreg_11 = log_asm.multi_pauli_meas<5, (Z, Z)> (%qreg, %qreg_1 : !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=h_z>, !log_asm.patch.rot_planar<size=(5, 5), location=(6.0, 0.0), orient=h_z>) (%qreg_2 : !log_asm.patch.rot_planar<size=(1, 5), location=(5.0, 0.0), orient=h_z>) -> i1
// CHECK-NEXT:    qstruct.parallel<TOP> -> {
// CHECK-NEXT:      %qreg_12 = log_asm.meas_stab<5> (%qreg_10 : !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=h_z>)
// CHECK-NEXT:      %cexpr_1 = log_asm.measure<Z> (%qreg_12 : !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=h_z>) -> i1
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    } {
// CHECK-NEXT:      %qreg_13 = log_asm.meas_stab<5> (%qreg_11 : !log_asm.patch.rot_planar<size=(5, 5), location=(6.0, 0.0), orient=h_z>)
// CHECK-NEXT:      %cexpr_2 = log_asm.measure<Z> (%qreg_13 : !log_asm.patch.rot_planar<size=(5, 5), location=(6.0, 0.0), orient=h_z>) -> i1
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    }
// CHECK-NEXT:    qstruct.output(:)
// CHECK-NEXT:  }
