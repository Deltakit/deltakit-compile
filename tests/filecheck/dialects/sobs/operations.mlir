// RUN: ROUNDTRIP_MLIR

builtin.module {
    // Unplaced observable
    %unplaced_obs = sobs.dec_unplaced_observable -> !sobs.unplaced_observable
    %patch_A = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
    %unplaced_obs_1 = sobs.locate_unplaced_observable<X>(%unplaced_obs) on (%patch_A) {wasa = "bi"} -> !sobs.unplaced_observable

    // Placed observable
    %q0, %q1, %q2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
    %q0_1, %q1_1, %q2_1 = qstruct.circuit(%q0, %q1, %q2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
    ^bb0(%q0_2 : !qcore.qubit, %q1_2 : !qcore.qubit, %q2_2: !qcore.qubit):
        %obs = sobs.dec_observable (%q0_2) -> !sobs.observable
        %obs_1 = sobs.locate_observable (%obs) on (%q2_2) -> !sobs.observable
        %meas = qref.measure<X>(%q1_2) -> i1
        %obs_moved = sobs.move_observable (%obs_1) to (%q2_2) using (%meas) -> !sobs.observable
        qstruct.yield %q0_2, %q1_2, %q2_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit
    }
}


// CHECK:           %unplaced_obs = sobs.dec_unplaced_observable -> !sobs.unplaced_observable
// CHECK-NEXT:      %patch_A = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
// CHECK-NEXT:      %unplaced_obs_1 = sobs.locate_unplaced_observable<X> (%unplaced_obs) on (%patch_A) {wasa = "bi"} -> !sobs.unplaced_observable
// CHECK-NEXT:      %q0, %q1, %q2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      %q0_1, %q1_1, %q2_1 = qstruct.circuit(%q0, %q1, %q2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:      ^bb0(%q0_2: !qcore.qubit, %q1_2: !qcore.qubit, %q2_2: !qcore.qubit):
// CHECK-NEXT:          %obs = sobs.dec_observable(%q0_2) -> !sobs.observable
// CHECK-NEXT:          %obs_1 = sobs.locate_observable(%obs) on(%q2_2) -> !sobs.observable
// CHECK-NEXT:          %meas = qref.measure<X> (%q1_2) -> i1
// CHECK-NEXT:          %obs_moved = sobs.move_observable(%obs_1) to(%q2_2) using(%meas) -> !sobs.observable
// CHECK-NEXT:          qstruct.yield %q0_2, %q1_2, %q2_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      }
