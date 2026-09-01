// RUN: deltakit_compile compile-passes -t %s -p patch-to-plaquettes -O %t && filecheck %s --input-file %t

// Test that some operations are ignored without failing.
builtin.module {
// CHECK:       builtin.module {

    %qreg = qcore.alloc_qubit<coords=[(0.5, 0.5), (1.5, 0.5), (1.0, 1.0)]> -> !qcore.qubit_reg<3>
    %p0 = log_asm.cast(%qreg : !qcore.qubit_reg<3>) -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>
    %p0_1 = log_asm.prepare<Z>(%p0 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>)
    %log = log_asm.measure<Z>(%p0_1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>) -> i1

// CHECK-NEXT:      %qreg = qcore.alloc_qubit<coords = [(0.5, 0.5), (1.5, 0.5), (1.0, 1.0)]> -> !qcore.qubit_reg<3>
// CHECK-NEXT:      %p0 = log_asm.cast(%qreg : !qcore.qubit_reg<3>) -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>
// CHECK-NEXT:      %p0_1 = log_asm.prepare<Z> (%p0 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:      %log = log_asm.measure<Z> (%p0_1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>) -> i1

}
// CHECK-NEXT:  }

// ----
// CHECK: ----

// Test that something else than a rotated planar patch is also ignored
builtin.module {
// CHECK:       builtin.module {

    %qreg = qcore.alloc_qubit<coords=[(0.5, 0.5), (1.5, 0.5), (1.0, 1.0)]> -> !qcore.qubit_reg<3>
    %p0 = log_asm.cast(%qreg : !qcore.qubit_reg<3>) -> !log_asm.patch.unrot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>
    %p0_1 = log_asm.prepare<Z>(%p0 : !log_asm.patch.unrot_planar<size=(2, 1), location=(0, 0), orient=v_z>)
    %p0_2 = log_asm.meas_stab<2>(%p0_1 : !log_asm.patch.unrot_planar<size=(2, 1), location=(0, 0), orient=v_z>)
    %log = log_asm.measure<Z>(%p0_2 : !log_asm.patch.unrot_planar<size=(2, 1), location=(0, 0), orient=v_z>) -> i1

// CHECK-NEXT:      %qreg = qcore.alloc_qubit<coords = [(0.5, 0.5), (1.5, 0.5), (1.0, 1.0)]> -> !qcore.qubit_reg<3>
// CHECK-NEXT:      %p0 = log_asm.cast(%qreg : !qcore.qubit_reg<3>) -> !log_asm.patch.unrot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>
// CHECK-NEXT:      %p0_1 = log_asm.prepare<Z> (%p0 : !log_asm.patch.unrot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:      %p0_2 = log_asm.meas_stab<2> (%p0_1 : !log_asm.patch.unrot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:      %log = log_asm.measure<Z> (%p0_2 : !log_asm.patch.unrot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>) -> i1

}
// CHECK-NEXT:  }

// ----
// CHECK: ----

// Test that a measure stabiliser with 0 rounds is erased.
builtin.module {
// CHECK:       builtin.module {

    %qreg = qcore.alloc_qubit<coords=[(0.5, 0.5), (1.5, 0.5), (1.0, 1.0)]> -> !qcore.qubit_reg<3>
    %p0 = log_asm.cast(%qreg : !qcore.qubit_reg<3>) -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>
    %p0_1 = log_asm.prepare<Z>(%p0 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>)
    %p0_2 = log_asm.meas_stab<0>(%p0_1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>)
    %log = log_asm.measure<Z>(%p0_2 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>) -> i1

// CHECK-NEXT:      %qreg = qcore.alloc_qubit<coords = [(0.5, 0.5), (1.5, 0.5), (1.0, 1.0)]> -> !qcore.qubit_reg<3>
// CHECK-NEXT:      %p0 = log_asm.cast(%qreg : !qcore.qubit_reg<3>) -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>
// CHECK-NEXT:      %p0_1 = log_asm.prepare<Z> (%p0 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:      %log = log_asm.measure<Z> (%p0_1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>) -> i1

}
// CHECK-NEXT:  }

// ----
// CHECK: ----

// Test that a 2x1 patch is lowered to a single plaquette which is:
//   .
//  / \
// .---.
builtin.module {
// CHECK:       builtin.module {

    // Same beginning as the previous module operation.
    %qreg = qcore.alloc_qubit<coords=[(0.5, 0.5), (1.5, 0.5), (1.0, 1.0)]> -> !qcore.qubit_reg<3>
    %p0 = log_asm.cast(%qreg : !qcore.qubit_reg<3>) -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>
    %p0_1 = log_asm.prepare<Z>(%p0 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>)
// CHECK-NEXT:      %qreg = qcore.alloc_qubit<coords = [(0.5, 0.5), (1.5, 0.5), (1.0, 1.0)]> -> !qcore.qubit_reg<3>
// CHECK-NEXT:      %p0 = log_asm.cast(%qreg : !qcore.qubit_reg<3>) -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>
// CHECK-NEXT:      %p0_1 = log_asm.prepare<Z> (%p0 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>)

    // The only operation that is being changed.
    %p0_2 = log_asm.meas_stab<2>(%p0_1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>)
// CHECK-NEXT:  %p0_2 = log_asm.cast(%p0_1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>) -> !qcore.qubit_reg<3>
// CHECK-NEXT:  %p0_3, %p0_4, %p0_5 = qcore.unpack_qubit_reg(%p0_2 : !qcore.qubit_reg<3>)
// CHECK-NEXT:  %p0_6, %p0_7, %p0_8 = qstruct.repeat<2> (%p0_3, %p0_4, %p0_5 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:      ^bb0(%0: !qcore.qubit, %1: !qcore.qubit, %2: !qcore.qubit):
// CHECK-NEXT:      %3, %4, %5, %6 = qstruct.circuit(%0, %1, %2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1 {
// CHECK-NEXT:          ^bb1(%7: !qcore.qubit, %8: !qcore.qubit, %9: !qcore.qubit):
// CHECK-NEXT:          %10 = plaquette.round(%7, %8, %9) {plaquette.z_observable_is_vertical = true} -> i1 {
// CHECK-NEXT:              ^bb2(%11: !qcore.qubit, %12: !qcore.qubit, %13: !qcore.qubit):
// CHECK-NEXT:              %14 = plaquette.plaquette<[Z0 Z1 : 2]> on (%11, %12) using (%13) {plaquette.shape_type = #plaquette.rotated_surface_plaquette_shape<TOP>} -> i1
// CHECK-NEXT:              plaquette.yield %14 : i1
// CHECK-NEXT:          }
// CHECK-NEXT:          qstruct.yield %7, %8, %9, %10 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield %3, %4, %5 : !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:  }
// CHECK-NEXT:  %p0_9 = qcore.pack_qubit_reg(%p0_6, %p0_7, %p0_8) -> !qcore.qubit_reg<3>
// CHECK-NEXT:  %p0_10 = log_asm.cast(%p0_9 : !qcore.qubit_reg<3>) -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>

    // Same end as the previous module operation.
    %log = log_asm.measure<Z>(%p0_2 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>) -> i1
// CHECK-NEXT:      %log = log_asm.measure<Z> (%p0_10 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>) -> i1

}
// CHECK-NEXT:  }

// ----
// CHECK: ----

// Test that a 2x2 patch is lowered to the correct plaquettes which are:
//
//    o
//   / \
//  /   \
// o-----o
// |     |
// |     |
// o-----o
//  \   /
//   \ /
//    o
builtin.module {
// CHECK:       builtin.module {

    // Same beginning as the previous module operation.
    %qreg = qcore.alloc_qubit<coords=[(0.5, 0.5), (0.5, 1.5), (1.5, 0.5), (1.5, 1.5), (1.0, 1.0), (1.0, 2.0), (1.0, 0.0)]> -> !qcore.qubit_reg<7>
    %p0 = log_asm.cast(%qreg : !qcore.qubit_reg<7>) -> !log_asm.patch.rot_planar<size=(2, 2), location=(0.0, 0.0), orient=v_z>
    %p0_1 = log_asm.prepare<Z>(%p0 : !log_asm.patch.rot_planar<size=(2, 2), location=(0, 0), orient=v_z>)
// CHECK-NEXT:      %qreg = qcore.alloc_qubit<coords = [(0.5, 0.5), (0.5, 1.5), (1.5, 0.5), (1.5, 1.5), (1.0, 1.0), (1.0, 2.0), (1.0, 0.0)]> -> !qcore.qubit_reg<7>
// CHECK-NEXT:      %p0 = log_asm.cast(%qreg : !qcore.qubit_reg<7>) -> !log_asm.patch.rot_planar<size=(2, 2), location=(0.0, 0.0), orient=v_z>
// CHECK-NEXT:      %p0_1 = log_asm.prepare<Z> (%p0 : !log_asm.patch.rot_planar<size=(2, 2), location=(0.0, 0.0), orient=v_z>)

    // The only operation that is being changed.
    %p0_2 = log_asm.meas_stab<46>(%p0_1 : !log_asm.patch.rot_planar<size=(2, 2), location=(0, 0), orient=v_z>)
// CHECK-NEXT:  %p0_2 = log_asm.cast(%p0_1 : !log_asm.patch.rot_planar<size=(2, 2), location=(0.0, 0.0), orient=v_z>) -> !qcore.qubit_reg<7>
// CHECK-NEXT:  %p0_3, %p0_4, %p0_5, %p0_6, %p0_7, %p0_8, %p0_9 = qcore.unpack_qubit_reg(%p0_2 : !qcore.qubit_reg<7>)
// CHECK-NEXT:  %p0_10, %p0_11, %p0_12, %p0_13, %p0_14, %p0_15, %p0_16 = qstruct.repeat<46> (%p0_3, %p0_4, %p0_5, %p0_6, %p0_7, %p0_8, %p0_9 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:      ^bb0(%0: !qcore.qubit, %1: !qcore.qubit, %2: !qcore.qubit, %3: !qcore.qubit, %4: !qcore.qubit, %5: !qcore.qubit, %6: !qcore.qubit):
// CHECK-NEXT:      %7, %8, %9, %10, %11, %12, %13, %14, %15, %16 = qstruct.circuit(%0, %1, %2, %3, %4, %5, %6 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1, i1 {
// CHECK-NEXT:          ^bb1(%17: !qcore.qubit, %18: !qcore.qubit, %19: !qcore.qubit, %20: !qcore.qubit, %21: !qcore.qubit, %22: !qcore.qubit, %23: !qcore.qubit):
// CHECK-NEXT:          %24, %25, %26 = plaquette.round(%17, %18, %19, %20, %21, %22, %23) {plaquette.z_observable_is_vertical = true} -> i1, i1, i1 {
// CHECK-NEXT:              ^bb2(%27: !qcore.qubit, %28: !qcore.qubit, %29: !qcore.qubit, %30: !qcore.qubit, %31: !qcore.qubit, %32: !qcore.qubit, %33: !qcore.qubit):
// CHECK-NEXT:              %34 = plaquette.plaquette<[X0 X1 X2 X3 : 4]> on (%28, %30, %27, %29) using (%31) {plaquette.shape_type = #plaquette.rotated_surface_plaquette_shape<SQUARE>} -> i1
// CHECK-NEXT:              plaquette.yield %34 : i1
// CHECK-NEXT:          } {
// CHECK-NEXT:              ^bb3(%35: !qcore.qubit, %36: !qcore.qubit, %37: !qcore.qubit, %38: !qcore.qubit, %39: !qcore.qubit, %40: !qcore.qubit, %41: !qcore.qubit):
// CHECK-NEXT:              %42 = plaquette.plaquette<[Z0 Z1 : 2]> on (%36, %38) using (%40) {plaquette.shape_type = #plaquette.rotated_surface_plaquette_shape<TOP>} -> i1
// CHECK-NEXT:              plaquette.yield %42 : i1
// CHECK-NEXT:          } {
// CHECK-NEXT:              ^bb4(%43: !qcore.qubit, %44: !qcore.qubit, %45: !qcore.qubit, %46: !qcore.qubit, %47: !qcore.qubit, %48: !qcore.qubit, %49: !qcore.qubit):
// CHECK-NEXT:              %50 = plaquette.plaquette<[Z0 Z1 : 2]> on (%43, %45) using (%49) {plaquette.shape_type = #plaquette.rotated_surface_plaquette_shape<BOTTOM>} -> i1
// CHECK-NEXT:              plaquette.yield %50 : i1
// CHECK-NEXT:          }
// CHECK-NEXT:          qstruct.yield %17, %18, %19, %20, %21, %22, %23, %24, %25, %26 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1, i1
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield %7, %8, %9, %10, %11, %12, %13 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:  }
// CHECK-NEXT:  %p0_17 = qcore.pack_qubit_reg(%p0_10, %p0_11, %p0_12, %p0_13, %p0_14, %p0_15, %p0_16) -> !qcore.qubit_reg<7>
// CHECK-NEXT:  %p0_18 = log_asm.cast(%p0_17 : !qcore.qubit_reg<7>) -> !log_asm.patch.rot_planar<size=(2, 2), location=(0.0, 0.0), orient=v_z>

    // Same end as the previous module operation.
    %log = log_asm.measure<Z>(%p0_2 : !log_asm.patch.rot_planar<size=(2, 2), location=(0, 0), orient=v_z>) -> i1
// CHECK-NEXT:      %log = log_asm.measure<Z> (%p0_18 : !log_asm.patch.rot_planar<size=(2, 2), location=(0.0, 0.0), orient=v_z>) -> i1

}
// CHECK-NEXT:  }
