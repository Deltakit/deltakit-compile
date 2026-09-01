// RUN: ROUNDTRIP_MLIR
builtin.module {
    %0 = "test.op"() : () -> !log_asm.patch.rot_planar<size=(3,3), location=(10.0, 12.0), orient=h_z>
    %1 = "test.op"() : () -> !log_asm.patch.rot_planar<size=(5,3), location=(0.0, 0.0), orient=h_z>
    %2 = "test.op"() : () -> !log_asm.patch.rot_planar<size=(5,5), location=(-10.0, -12.0), orient=v_z>

    %3 = "test.op"() : () -> !log_asm.patch.unrot_planar<size=(3,3), location=(10.0, 12.0), orient=h_z>
    %4 = "test.op"() : () -> !log_asm.patch.unrot_planar<size=(5,3), location=(0.0, 0.0), orient=h_z>
    %5 = "test.op"() : () -> !log_asm.patch.unrot_planar<size=(5,5), location=(-10.0, -12.0), orient=v_z>

    %6 = "test.op"() : () -> !log_asm.patch.rot_planar<size=(5,5)>
    %7 = "test.op"() : () -> !log_asm.patch.unrot_planar<size=(5,5)>
}
// CHECK:       builtin.module {
// CHECK-NEXT:      %0 = "test.op"() : () -> !log_asm.patch.rot_planar<size=(3, 3), location=(10.0, 12.0), orient=h_z>
// CHECK-NEXT:      %1 = "test.op"() : () -> !log_asm.patch.rot_planar<size=(5, 3), location=(0.0, 0.0), orient=h_z>
// CHECK-NEXT:      %2 = "test.op"() : () -> !log_asm.patch.rot_planar<size=(5, 5), location=(-10.0, -12.0), orient=v_z>

// CHECK-NEXT:      %3 = "test.op"() : () -> !log_asm.patch.unrot_planar<size=(3, 3), location=(10.0, 12.0), orient=h_z>
// CHECK-NEXT:      %4 = "test.op"() : () -> !log_asm.patch.unrot_planar<size=(5, 3), location=(0.0, 0.0), orient=h_z>
// CHECK-NEXT:      %5 = "test.op"() : () -> !log_asm.patch.unrot_planar<size=(5, 5), location=(-10.0, -12.0), orient=v_z>

// CHECK-NEXT:      %6 = "test.op"() : () -> !log_asm.patch.rot_planar<size=(5, 5)>
// CHECK-NEXT:      %7 = "test.op"() : () -> !log_asm.patch.unrot_planar<size=(5, 5)>
// CHECK-NEXT:  }
