// RUN: deltakit_compile compile-passes %s -p lower-patch-declaration -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK:       builtin.module {

    %p0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=v_z>
// CHECK-NEXT:      %p0, %p0_1, %p0_2, %p0_3, %p0_4, %p0_5, %p0_6, %p0_7, %p0_8,
// CHECK-SAME:      %p0_9, %p0_10, %p0_11, %p0_12, %p0_13, %p0_14, %p0_15, %p0_16
// CHECK-SAME:      = qcore.alloc_qubit<coords = [(0.5, 0.5), (0.5, 1.5), (0.5, 2.5), (1.5, 0.5), (1.5, 1.5),
// CHECK-SAME:      (1.5, 2.5), (2.5, 0.5), (2.5, 1.5), (2.5, 2.5), (1.0, 1.0), (1.0, 2.0),
// CHECK-SAME:      (2.0, 1.0), (2.0, 2.0), (1.0, 3.0), (3.0, 2.0), (2.0, 0.0), (0.0, 1.0)]>
// CHECK-SAME:      -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit,
// CHECK-SAME:      !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit,
// CHECK-SAME:      !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit,
// CHECK-SAME:      !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      %p0_17 = qcore.pack_qubit_reg(%p0, %p0_1, %p0_2, %p0_3, %p0_4, %p0_5, %p0_6,
// CHECK-SAME:      %p0_7, %p0_8, %p0_9, %p0_10, %p0_11, %p0_12, %p0_13, %p0_14, %p0_15, %p0_16) ->
// CHECK-SAME:      !qcore.qubit_reg<17>
// CHECK-NEXT:      %p0_18 = log_asm.cast(%p0_17 : !qcore.qubit_reg<17>) ->
// CHECK-SAME:      !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>

}
// CHECK-NEXT:  }

// ----
// CHECK: ----

builtin.module {
// CHECK:       builtin.module {
    %p1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(1, 3), location=(0, 0), orient=v_z>
    %p2 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>
// CHECK-NEXT:      %p1, %p1_1, %p1_2, %p1_3, %p1_4 = qcore.alloc_qubit<coords = [(0.5, 0.5), (0.5, 1.5), (0.5, 2.5), (0.0, 1.0), (1.0, 2.0)]> -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      %p1_5 = qcore.pack_qubit_reg(%p1, %p1_1, %p1_2, %p1_3, %p1_4) -> !qcore.qubit_reg<5>
// CHECK-NEXT:      %p1_6 = log_asm.cast(%p1_5 : !qcore.qubit_reg<5>) -> !log_asm.patch.rot_planar<size=(1, 3), location=(0.0, 0.0), orient=v_z>
// CHECK-NEXT:      %p2, %p2_1, %p2_2 = qcore.alloc_qubit<coords = [(0.5, 0.5), (1.5, 0.5), (1.0, 1.0)]> -> !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      %p2_3 = qcore.pack_qubit_reg(%p2, %p2_1, %p2_2) -> !qcore.qubit_reg<3>
// CHECK-NEXT:      %p2_4 = log_asm.cast(%p2_3 : !qcore.qubit_reg<3>) -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>
}
// CHECK-NEXT:  }

// ----
// CHECK: ----

builtin.module {
// CHECK:       builtin.module {
    %p1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(1, 3), location=(1, -10), orient=v_z>
    %p2 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.5, 3.5), orient=h_z>
// CHECK-NEXT:      %p1, %p1_1, %p1_2, %p1_3, %p1_4 = qcore.alloc_qubit<coords = [(1.5, -9.5), (1.5, -8.5), (1.5, -7.5), (1.0, -9.0), (2.0, -8.0)]> -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      %p1_5 = qcore.pack_qubit_reg(%p1, %p1_1, %p1_2, %p1_3, %p1_4) -> !qcore.qubit_reg<5>
// CHECK-NEXT:      %p1_6 = log_asm.cast(%p1_5 : !qcore.qubit_reg<5>) -> !log_asm.patch.rot_planar<size=(1, 3), location=(1.0, -10.0), orient=v_z>
// CHECK-NEXT:      %p2, %p2_1, %p2_2 = qcore.alloc_qubit<coords = [(1.0, 4.0), (2.0, 4.0), (1.5, 4.5)]> -> !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      %p2_3 = qcore.pack_qubit_reg(%p2, %p2_1, %p2_2) -> !qcore.qubit_reg<3>
// CHECK-NEXT:      %p2_4 = log_asm.cast(%p2_3 : !qcore.qubit_reg<3>) -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.5, 3.5), orient=h_z>
}
// CHECK-NEXT:  }
