// RUN: deltakit_compile compile-passes %s -p backpropagate-observables -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK:       builtin.module {

    // No observable already annotated
    %p0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3)>
    %p0_1 = log_asm.prepare<Z>(%p0 : !log_asm.patch.rot_planar<size=(3, 3)>)
    %p0_2 = log_asm.meas_stab<3>(%p0_1 : !log_asm.patch.rot_planar<size=(3, 3)>)
    %log = log_asm.measure<Z>(%p0_2 : !log_asm.patch.rot_planar<size=(3, 3)>) -> i1

// CHECK-NEXT:      %0 = sobs.dec_unplaced_observable -> !sobs.unplaced_observable
// CHECK-NEXT:      %p0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3)>
// CHECK-NEXT:      %p0_1 = log_asm.prepare<Z> (%p0 : !log_asm.patch.rot_planar<size=(3, 3)>)
// CHECK-NEXT:      %1 = sobs.locate_unplaced_observable<Z> (%0) on (%p0_1) -> !sobs.unplaced_observable
// CHECK-NEXT:      %p0_2 = log_asm.meas_stab<3> (%p0_1 : !log_asm.patch.rot_planar<size=(3, 3)>)
// CHECK-NEXT:      %2 = sobs.locate_unplaced_observable<Z> (%1) on (%p0_2) -> !sobs.unplaced_observable
// CHECK-NEXT:      %log = log_asm.measure<Z> (%p0_2 : !log_asm.patch.rot_planar<size=(3, 3)>) -> i1
}
// CHECK-NEXT:  }

// ----
// CHECK: ----

builtin.module {
// CHECK:       builtin.module {
    // Observable declared, but missing annotations
    %obs1 = sobs.dec_unplaced_observable -> !sobs.unplaced_observable
    %p2 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3)>
    %p2_1 = log_asm.prepare<Z>(%p2 : !log_asm.patch.rot_planar<size=(3, 3)>)
    %p2_2 = log_asm.meas_stab<3>(%p2_1 : !log_asm.patch.rot_planar<size=(3, 3)>)
    %obs1_1 = sobs.locate_unplaced_observable<Z> (%obs1) on (%p2_2) -> !sobs.unplaced_observable
    %log2 = log_asm.measure<Z>(%p2_2 : !log_asm.patch.rot_planar<size=(3, 3)>) -> i1

// CHECK-NEXT:      %obs1 = sobs.dec_unplaced_observable -> !sobs.unplaced_observable
// CHECK-NEXT:      %p2 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3)>
// CHECK-NEXT:      %p2_1 = log_asm.prepare<Z> (%p2 : !log_asm.patch.rot_planar<size=(3, 3)>)
// CHECK-NEXT:      %0 = sobs.locate_unplaced_observable<Z> (%obs1) on (%p2_1) -> !sobs.unplaced_observable
// CHECK-NEXT:      %p2_2 = log_asm.meas_stab<3> (%p2_1 : !log_asm.patch.rot_planar<size=(3, 3)>)
// CHECK-NEXT:      %obs1_1 = sobs.locate_unplaced_observable<Z> (%0) on (%p2_2) -> !sobs.unplaced_observable
// CHECK-NEXT:      %log2 = log_asm.measure<Z> (%p2_2 : !log_asm.patch.rot_planar<size=(3, 3)>) -> i1
}
// CHECK-NEXT:  }
