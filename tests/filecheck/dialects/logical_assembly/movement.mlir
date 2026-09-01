// RUN: ROUNDTRIP_MLIR
builtin.module {
    %lq0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5,5), location=(0.0, 0.0), orient=h_z>
    %lq1 = log_asm.prepare <Z> (%lq0 : !log_asm.patch.rot_planar<size=(5,5), location=(0.0, 0.0), orient=h_z>)

    %bridge = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5,5), location=(5.0, 0.0), orient=h_z>

    %lq_moved = log_asm.move <30> (%lq1 : !log_asm.patch.rot_planar<size=(5,5), location=(0.0, 0.0), orient=h_z>)
                 (%bridge : !log_asm.patch.rot_planar<size=(5,5), location=(5.0, 0.0), orient=h_z>)
                    -> !log_asm.patch.rot_planar<size=(5,5), location=(10.0, 0.0), orient=h_z>

    %lq_grown = log_asm.grow <100>
                    (%lq_moved : !log_asm.patch.rot_planar<size=(5,5), location=(10.0, 0.0), orient=h_z>)
                        -> !log_asm.patch.rot_planar<size=(10,10), location=(9.0, -1.0), orient=h_z>

    %lq_shrunk = log_asm.shrink<20> (%lq_grown : !log_asm.patch.rot_planar<size=(10,10), location=(9.0, -1.0), orient=h_z>)
                                    -> !log_asm.patch.rot_planar<size=(9,9), location=(9.0, -1.0), orient=h_z>

    %lq_stepped = log_asm.step (%lq_shrunk : !log_asm.patch.rot_planar<size=(9,9), location=(9.0, -1.0), orient=h_z>)
                                    -> !log_asm.patch.rot_planar<size=(9,9), location=(10.0, -1.0), orient=h_z>

    %lq_rot = log_asm.rotate<5> (%lq_stepped : !log_asm.patch.rot_planar<size=(9,9), location=(10.0, -1.0), orient=h_z>)
                                    -> !log_asm.patch.rot_planar<size=(9,9), location=(1.0, -1.0), orient=v_z>

    %r_z = log_asm.measure <Z> (%lq_rot : !log_asm.patch.rot_planar<size=(9,9), location=(1.0, -1.0), orient=v_z>) -> i1
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:      %lq0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=h_z>
// CHECK-NEXT:      %lq1 = log_asm.prepare<Z> (%lq0 : !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=h_z>)

// CHECK-NEXT:      %bridge = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5, 5), location=(5.0, 0.0), orient=h_z>

// CHECK-NEXT:      %lq_moved = log_asm.move<30> (%lq1 : !log_asm.patch.rot_planar<size=(5, 5), location=(0.0, 0.0), orient=h_z>)
// CHECK-SAME:                   (%bridge : !log_asm.patch.rot_planar<size=(5, 5), location=(5.0, 0.0), orient=h_z>)
// CHECK-SAME:                      -> !log_asm.patch.rot_planar<size=(5, 5), location=(10.0, 0.0), orient=h_z>

// CHECK-NEXT:      %lq_grown = log_asm.grow<100>
// CHECK-SAME:                      (%lq_moved : !log_asm.patch.rot_planar<size=(5, 5), location=(10.0, 0.0), orient=h_z>)
// CHECK-SAME:                          -> !log_asm.patch.rot_planar<size=(10, 10), location=(9.0, -1.0), orient=h_z>

// CHECK-NEXT:      %lq_shrunk = log_asm.shrink<20> (%lq_grown : !log_asm.patch.rot_planar<size=(10, 10), location=(9.0, -1.0), orient=h_z>)
// CHECK-SAME:                                      -> !log_asm.patch.rot_planar<size=(9, 9), location=(9.0, -1.0), orient=h_z>

// CHECK-NEXT:      %lq_stepped = log_asm.step(%lq_shrunk : !log_asm.patch.rot_planar<size=(9, 9), location=(9.0, -1.0), orient=h_z>)
// CHECK-SAME:                                      -> !log_asm.patch.rot_planar<size=(9, 9), location=(10.0, -1.0), orient=h_z>

// CHECK-NEXT:      %lq_rot = log_asm.rotate<5> (%lq_stepped : !log_asm.patch.rot_planar<size=(9, 9), location=(10.0, -1.0), orient=h_z>)
// CHECK-SAME:                                      -> !log_asm.patch.rot_planar<size=(9, 9), location=(1.0, -1.0), orient=v_z>
// CHECK-NEXT:      %r_z = log_asm.measure<Z> (%lq_rot : !log_asm.patch.rot_planar<size=(9, 9), location=(1.0, -1.0), orient=v_z>) -> i1
// CHECK-NEXT:  }
