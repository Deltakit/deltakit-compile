// RUN: deltakit_compile compile-passes %s -p located-observable-to-move -O %t && filecheck %s --input-file %t

// Directly taken from an example in `place_observables.mlir`. Because the observable does not move,
// all the complexity around observables (casts from patch to qubits, wrapping in circuits, ...)
// should be canonicalised away.
builtin.module {
//CHECK:  builtin.module {

    %p0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
    %p0_1 = log_asm.prepare<Z> (%p0 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)
// CHECK-NEXT:    %p0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
// CHECK-NEXT:    %p0_1 = log_asm.prepare<Z> (%p0 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)

    // The following stays because that is the `dec_observable`.
    %qreg = log_asm.cast(%p0_1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> !qcore.qubit_reg<17>
    %q, %q_1, %q_2, %q_3, %q_4, %q_5, %q_6, %q_7, %q_8, %q_9, %q_10, %q_11, %q_12, %q_13, %q_14, %q_15, %q_16 = qcore.unpack_qubit_reg(%qreg : !qcore.qubit_reg<17>)
    %obs = sobs.dec_observable(%q_2, %q_5, %q_8) -> !sobs.observable

// CHECK-NEXT:    %qreg = log_asm.cast(%p0_1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> !qcore.qubit_reg<17>
// CHECK-NEXT:    %q, %q_1, %q_2, %q_3, %q_4, %q_5, %q_6, %q_7, %q_8, %q_9, %q_10, %q_11, %q_12, %q_13, %q_14, %q_15, %q_16 = qcore.unpack_qubit_reg(%qreg : !qcore.qubit_reg<17>)
// CHECK-NEXT:    %obs = sobs.dec_observable(%q_2, %q_5, %q_8) -> !sobs.observable

    // From now on, everything related to observables should be canonicalised away.
    %obs_1 = builtin.unrealized_conversion_cast %obs : !sobs.observable to !sobs.unplaced_observable

    %p0_2 = log_asm.meas_stab<3> (%p0_1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)

    %qreg_1 = log_asm.cast(%p0_2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> !qcore.qubit_reg<17>
    %q_24, %q_25, %q_26, %q_27, %q_28, %q_29, %q_30, %q_31, %q_32, %q_33, %q_34, %q_35, %q_36, %q_37, %q_38, %q_39, %q_40 = qcore.unpack_qubit_reg(%qreg_1 : !qcore.qubit_reg<17>)
    %obs_2 = builtin.unrealized_conversion_cast %obs_1 : !sobs.unplaced_observable to !sobs.observable
    %obs_3, %q_43, %q_44, %q_45 = qstruct.circuit(%obs_2, %q_26, %q_29, %q_32 : !sobs.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !sobs.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit {
        ^bb0(%0: !sobs.observable, %1: !qcore.qubit, %2: !qcore.qubit, %3: !qcore.qubit):
        %4 = sobs.locate_observable(%0) on(%1, %2, %3) -> !sobs.observable
        qstruct.yield %4, %1, %2, %3 : !sobs.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit
    }
    %obs_4 = builtin.unrealized_conversion_cast %obs_3 : !sobs.observable to !sobs.unplaced_observable

    %p0_3 = log_asm.meas_stab<3> (%p0_2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)

    %qreg_2 = log_asm.cast(%p0_3 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> !qcore.qubit_reg<17>
    %q_48, %q_49, %q_50, %q_51, %q_52, %q_53, %q_54, %q_55, %q_56, %q_57, %q_58, %q_59, %q_60, %q_61, %q_62, %q_63, %q_64 = qcore.unpack_qubit_reg(%qreg_2 : !qcore.qubit_reg<17>)
    %obs_5 = builtin.unrealized_conversion_cast %obs_4 : !sobs.unplaced_observable to !sobs.observable
    %obs_6, %q_67, %q_68, %q_69 = qstruct.circuit(%obs_5, %q_50, %q_53, %q_56 : !sobs.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !sobs.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit {
        ^bb0(%0: !sobs.observable, %1: !qcore.qubit, %2: !qcore.qubit, %3: !qcore.qubit):
        %4 = sobs.locate_observable(%0) on(%1, %2, %3) -> !sobs.observable
        qstruct.yield %4, %1, %2, %3 : !sobs.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit
    }

    %log = log_asm.measure<Z> (%p0_2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> i1

// CHECK-NEXT:    %p0_2 = log_asm.meas_stab<3> (%p0_1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)
// CHECK-NEXT:    %p0_3 = log_asm.meas_stab<3> (%p0_2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)
// CHECK-NEXT:    %log = log_asm.measure<Z> (%p0_2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> i1

}
