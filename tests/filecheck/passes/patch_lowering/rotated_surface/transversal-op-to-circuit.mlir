// RUN: deltakit_compile compile-passes %s -t -p transversal-op-to-circuit --pass-args '{"parity": true}' -O %t && filecheck %s --input-file %t

// Test: Simple prepare operation with Z basis on a 2x2 patch
builtin.module {
// CHECK: builtin.module {

    %patch = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(2, 2), location=(0, 0), orient=v_z>
    %p0 = log_asm.prepare<Z> (%patch : !log_asm.patch.rot_planar<size=(2, 2), location=(0, 0), orient=v_z>)
}
// CHECK-NEXT: %patch = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(2, 2), location=(0.0, 0.0), orient=v_z>
// CHECK-NEXT: %p0 = log_asm.cast(%patch : !log_asm.patch.rot_planar<size=(2, 2), location=(0.0, 0.0), orient=v_z>) -> !qcore.qubit_reg<7>
// CHECK-NEXT: %p0_1, %p0_2, %p0_3, %p0_4, %p0_5, %p0_6, %p0_7 = qcore.unpack_qubit_reg(%p0 : !qcore.qubit_reg<7>)
// CHECK-NEXT: %p0_8, %p0_9, %p0_10, %p0_11, %p0_12, %p0_13, %p0_14 = qstruct.circuit(%p0_1, %p0_2, %p0_3, %p0_4, %p0_5, %p0_6, %p0_7 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) {stab.flows = #stab.concrete_flow_array<[<+:>{I -> Z0 Z2 : 7}, <+:>{I -> Z1 Z3 : 7}]>, stab.droppable_flows} -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit

// ----
// CHECK: ----

// Test: recover the output of place-observables.
builtin.module {
// CHECK:         builtin.module {

    %p0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
    %p0_1 = log_asm.prepare<Z> (%p0 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)
// CHECK-NEXT:    %p0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
// CHECK-NEXT:    %p0_1 = log_asm.cast(%p0 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> !qcore.qubit_reg<17>
// CHECK-NEXT:    %p0_2, %p0_3, %p0_4, %p0_5, %p0_6, %p0_7, %p0_8, %p0_9, %p0_10, %p0_11, %p0_12, %p0_13, %p0_14, %p0_15, %p0_16, %p0_17, %p0_18 = qcore.unpack_qubit_reg(%p0_1 : !qcore.qubit_reg<17>)
// CHECK-NEXT:    %p0_19, %p0_20, %p0_21, %p0_22, %p0_23, %p0_24, %p0_25, %p0_26, %p0_27, %p0_28, %p0_29, %p0_30, %p0_31, %p0_32, %p0_33, %p0_34, %p0_35
// CHECK-SAME:    = qstruct.circuit(%p0_2, %p0_3, %p0_4, %p0_5, %p0_6, %p0_7, %p0_8, %p0_9, %p0_10, %p0_11, %p0_12, %p0_13, %p0_14, %p0_15, %p0_16, %p0_17, %p0_18 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit)
// CHECK-SAME:    {stab.flows = #stab.concrete_flow_array<[<+:>{I -> Z0 Z1 : 17}, <+:>{I -> Z1 Z2 Z4 Z5 : 17}, <+:>{I -> Z3 Z4 Z6 Z7 : 17}, <+:>{I -> Z7 Z8 : 17}]>, stab.droppable_flows}
// CHECK-SAME:    -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%0: !qcore.qubit, %1: !qcore.qubit, %2: !qcore.qubit, %3: !qcore.qubit, %4: !qcore.qubit, %5: !qcore.qubit, %6: !qcore.qubit, %7: !qcore.qubit, %8: !qcore.qubit, %9: !qcore.qubit, %10: !qcore.qubit, %11: !qcore.qubit, %12: !qcore.qubit, %13: !qcore.qubit, %14: !qcore.qubit, %15: !qcore.qubit, %16: !qcore.qubit):
// CHECK-NEXT:        qref.reset<Z> (%0, %1, %2, %3, %4, %5, %6, %7, %8)
// CHECK-NEXT:        qstruct.yield %0, %1, %2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14, %15, %16 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:    %p0_36 = qcore.pack_qubit_reg(%p0_19, %p0_20, %p0_21, %p0_22, %p0_23, %p0_24, %p0_25, %p0_26, %p0_27, %p0_28, %p0_29, %p0_30, %p0_31, %p0_32, %p0_33, %p0_34, %p0_35) -> !qcore.qubit_reg<17>
// CHECK-NEXT:    %p0_37 = log_asm.cast(%p0_36 : !qcore.qubit_reg<17>) -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>

// The following should be kept unchanged except that identifiers are shifted.
    %qreg = log_asm.cast(%p0_1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> !qcore.qubit_reg<17>
    %q_1, %q_2, %q_3, %q_4, %q_5, %q_6, %q_7, %q_8, %q_9, %q_10, %q_11, %q_12, %q_13, %q_14, %q_15, %q_16, %q_17 = qcore.unpack_qubit_reg(%qreg : !qcore.qubit_reg<17>)
    %pobs, %q_18, %q_19, %q_20 = qstruct.circuit(%q_2, %q_5, %q_8 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !sobs.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit {
        ^bb0(%0: !qcore.qubit, %1: !qcore.qubit, %2: !qcore.qubit):
        %3 = sobs.dec_observable(%0, %1, %2) -> !sobs.observable
        qstruct.yield %3, %0, %1, %2 : !sobs.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit
    }
    %uobs = builtin.unrealized_conversion_cast %pobs : !sobs.observable to !sobs.unplaced_observable

    %p0_2 = log_asm.meas_stab<3> (%p0_1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)

    %qreg_1 = log_asm.cast(%p0_2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> !qcore.qubit_reg<17>
    %q_24, %q_25, %q_26, %q_27, %q_28, %q_29, %q_30, %q_31, %q_32, %q_33, %q_34, %q_35, %q_36, %q_37, %q_38, %q_39, %q_40 = qcore.unpack_qubit_reg(%qreg_1 : !qcore.qubit_reg<17>)
    %pobs_1 = builtin.unrealized_conversion_cast %uobs : !sobs.unplaced_observable to !sobs.observable
    %pobs_2, %q_43, %q_44, %q_45 = qstruct.circuit(%pobs_1, %q_25, %q_28, %q_31 : !sobs.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !sobs.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit {
        ^bb0(%0: !sobs.observable, %1: !qcore.qubit, %2: !qcore.qubit, %3: !qcore.qubit):
        %4 = sobs.locate_observable(%0) on(%1, %2, %3) -> !sobs.observable
        qstruct.yield %4, %1, %2, %3 : !sobs.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit
    }


// CHECK-NEXT:    %qreg = log_asm.cast(%p0_37 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> !qcore.qubit_reg<17>
// CHECK-NEXT:    %q, %q_1, %q_2, %q_3, %q_4, %q_5, %q_6, %q_7, %q_8, %q_9, %q_10, %q_11, %q_12, %q_13, %q_14, %q_15, %q_16 = qcore.unpack_qubit_reg(%qreg : !qcore.qubit_reg<17>)
// CHECK-NEXT:    %pobs, %q_17, %q_18, %q_19 = qstruct.circuit(%q_1, %q_4, %q_7 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !sobs.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:        ^bb0(%0: !qcore.qubit, %1: !qcore.qubit, %2: !qcore.qubit):
// CHECK-NEXT:        %3 = sobs.dec_observable(%0, %1, %2) -> !sobs.observable
// CHECK-NEXT:        qstruct.yield %3, %0, %1, %2 : !sobs.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }
// CHECK-NEXT:    %uobs = builtin.unrealized_conversion_cast %pobs : !sobs.observable to !sobs.unplaced_observable

// CHECK-NEXT:    %p0_38 = log_asm.meas_stab<3> (%p0_37 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)

// CHECK-NEXT:    %qreg_1 = log_asm.cast(%p0_38 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> !qcore.qubit_reg<17>
// CHECK-NEXT:    %q_20, %q_21, %q_22, %q_23, %q_24, %q_25, %q_26, %q_27, %q_28, %q_29, %q_30, %q_31, %q_32, %q_33, %q_34, %q_35, %q_36 = qcore.unpack_qubit_reg(%qreg_1 : !qcore.qubit_reg<17>)
// CHECK-NEXT:    %pobs_1 = builtin.unrealized_conversion_cast %uobs : !sobs.unplaced_observable to !sobs.observable
// CHECK-NEXT:    %pobs_2, %q_37, %q_38, %q_39 = qstruct.circuit(%pobs_1, %q_21, %q_24, %q_27 : !sobs.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !sobs.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:        ^bb0(%0: !sobs.observable, %1: !qcore.qubit, %2: !qcore.qubit, %3: !qcore.qubit):
// CHECK-NEXT:        %4 = sobs.locate_observable(%0) on(%1, %2, %3) -> !sobs.observable
// CHECK-NEXT:        qstruct.yield %4, %1, %2, %3 : !sobs.observable, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }


// The following should be changed
    %log = log_asm.measure<Z> (%p0_2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> i1
    // Use %log to avoid elimination
    "test.op"(%log) : (i1) -> ()
// CHECK-NEXT:    %log = log_asm.cast(%p0_38 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> !qcore.qubit_reg<17>
// CHECK-NEXT:    %log_1, %log_2, %log_3, %log_4, %log_5, %log_6, %log_7, %log_8, %log_9, %log_10, %log_11, %log_12, %log_13, %log_14, %log_15, %log_16, %log_17 = qcore.unpack_qubit_reg(%log : !qcore.qubit_reg<17>)
// CHECK-NEXT:    %log_18, %log_19, %log_20, %log_21, %log_22, %log_23, %log_24, %log_25, %log_26, %log_27, %log_28, %log_29, %log_30, %log_31, %log_32, %log_33, %log_34, %log_35, %log_36, %log_37, %log_38, %log_39, %log_40, %log_41, %log_42, %log_43
// CHECK-SAME:    = qstruct.circuit(%log_1, %log_2, %log_3, %log_4, %log_5, %log_6, %log_7, %log_8, %log_9, %log_10, %log_11, %log_12, %log_13, %log_14, %log_15, %log_16, %log_17 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit)
// CHECK-SAME:    {stab.flows = #stab.concrete_flow_array<[<+:17, 18>{Z0 Z1 -> I : 17}, <+:18, 19, 21, 22>{Z1 Z2 Z4 Z5 -> I : 17}, <+:20, 21, 23, 24>{Z3 Z4 Z6 Z7 -> I : 17}, <+:24, 25>{Z7 Z8 -> I : 17}]>, stab.droppable_flows}
// CHECK-SAME:    -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1, i1, i1, i1, i1, i1, i1, i1 {
// CHECK-NEXT:    ^bb0(%0: !qcore.qubit, %1: !qcore.qubit, %2: !qcore.qubit, %3: !qcore.qubit, %4: !qcore.qubit, %5: !qcore.qubit, %6: !qcore.qubit, %7: !qcore.qubit, %8: !qcore.qubit, %9: !qcore.qubit, %10: !qcore.qubit, %11: !qcore.qubit, %12: !qcore.qubit, %13: !qcore.qubit, %14: !qcore.qubit, %15: !qcore.qubit, %16: !qcore.qubit):
// CHECK-NEXT:        %17, %18, %19, %20, %21, %22, %23, %24, %25 = qref.measure<Z> (%0, %1, %2, %3, %4, %5, %6, %7, %8) -> i1, i1, i1, i1, i1, i1, i1, i1, i1
// CHECK-NEXT:        qstruct.yield %0, %1, %2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14, %15, %16, %17, %18, %19, %20, %21, %22, %23, %24, %25 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1, i1, i1, i1, i1, i1, i1, i1
// CHECK-NEXT:    }
// CHECK-NEXT:    %log_44 = qec.get_corrected(%pobs_2 : !sobs.observable) -> i1
// CHECK-NEXT:    "test.op"(%log_44) : (i1) -> ()
}
