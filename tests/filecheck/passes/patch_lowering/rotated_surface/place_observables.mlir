// RUN: deltakit_compile compile-passes %s -p place-observables -O %t && filecheck %s --input-file %t

// Declaration without a locate is deleted by DCE
builtin.module {
// CHECK:       builtin.module {
    %obs_0 = sobs.dec_unplaced_observable -> !sobs.unplaced_observable
}
// CHECK-NEXT:  }

// ----
// CHECK: ----

// Declaration with several locate.
builtin.module {
// CHECK:       builtin.module {

    %obs_0 = sobs.dec_unplaced_observable -> !sobs.unplaced_observable
    %p0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=h_z>
    %p0_1 = log_asm.prepare<Z> (%p0 : !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=h_z>)
    %obs_1 = sobs.locate_unplaced_observable<Z>(%obs_0) on (%p0_1) -> !sobs.unplaced_observable
    %p0_2 = log_asm.meas_stab<3> (%p0_1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=h_z>)
    %obs_2 = sobs.locate_unplaced_observable<Z>(%obs_1) on (%p0_2) -> !sobs.unplaced_observable
    %p0_3 = log_asm.meas_stab<3> (%p0_2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=h_z>)
    %obs_3 = sobs.locate_unplaced_observable<Z>(%obs_2) on (%p0_3) -> !sobs.unplaced_observable
    %log = log_asm.measure<Z> (%p0_2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=h_z>) -> i1

// CHECK-NEXT:    %p0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
// CHECK-NEXT:    %p0_1 = log_asm.prepare<Z> (%p0 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)
// CHECK-NEXT:    %obs = log_asm.cast(%p0_1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> !qcore.qubit_reg<17>

// CHECK-NEXT:    %obs_1, %obs_2 = qstruct.circuit(%obs : !qcore.qubit_reg<17>) -> !sobs.observable, !qcore.qubit_reg<17> {
// CHECK-NEXT:    ^bb0(%0: !qcore.qubit_reg<17>):
// CHECK-NEXT:      %1, %2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14, %15, %16, %17 = qcore.unpack_qubit_reg(%0 : !qcore.qubit_reg<17>)
// CHECK-NEXT:      %18 = sobs.dec_observable(%3, %6, %9) -> !sobs.observable
// CHECK-NEXT:      qstruct.yield %18, %0 : !sobs.observable, !qcore.qubit_reg<17>
// CHECK-NEXT:    }
// CHECK-NEXT:    %obs_3 = log_asm.cast(%obs_2 : !qcore.qubit_reg<17>) -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
// CHECK-NEXT:    %obs_4 = builtin.unrealized_conversion_cast %obs_1 : !sobs.observable to !sobs.unplaced_observable

// CHECK-NEXT:    %p0_2 = log_asm.meas_stab<3> (%obs_3 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)

// CHECK-NEXT:    %obs_5 = log_asm.cast(%p0_2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> !qcore.qubit_reg<17>
// CHECK-NEXT:    %obs_6 = builtin.unrealized_conversion_cast %obs_4 : !sobs.unplaced_observable to !sobs.observable
// CHECK-NEXT:    %obs_7, %obs_8 = qstruct.circuit(%obs_6, %obs_5 : !sobs.observable, !qcore.qubit_reg<17>) -> !sobs.observable, !qcore.qubit_reg<17> {
// CHECK-NEXT:    ^bb0(%0: !sobs.observable, %1: !qcore.qubit_reg<17>):
// CHECK-NEXT:      %2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14, %15, %16, %17, %18 = qcore.unpack_qubit_reg(%1 : !qcore.qubit_reg<17>)
// CHECK-NEXT:      %19 = sobs.locate_observable(%0) on(%4, %7, %10) -> !sobs.observable
// CHECK-NEXT:      qstruct.yield %19, %1 : !sobs.observable, !qcore.qubit_reg<17>
// CHECK-NEXT:    }
// CHECK-NEXT:    %obs_9 = log_asm.cast(%obs_8 : !qcore.qubit_reg<17>) -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
// CHECK-NEXT:    %obs_10 = builtin.unrealized_conversion_cast %obs_7 : !sobs.observable to !sobs.unplaced_observable

// CHECK-NEXT:    %p0_3 = log_asm.meas_stab<3> (%obs_9 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)

// CHECK-NEXT:    %obs_11 = log_asm.cast(%p0_3 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> !qcore.qubit_reg<17>
// CHECK-NEXT:    %obs_12 = builtin.unrealized_conversion_cast %obs_10 : !sobs.unplaced_observable to !sobs.observable
// CHECK-NEXT:    %obs_13, %obs_14 = qstruct.circuit(%obs_12, %obs_11 : !sobs.observable, !qcore.qubit_reg<17>) -> !sobs.observable, !qcore.qubit_reg<17> {
// CHECK-NEXT:    ^bb0(%0: !sobs.observable, %1: !qcore.qubit_reg<17>):
// CHECK-NEXT:      %2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14, %15, %16, %17, %18 = qcore.unpack_qubit_reg(%1 : !qcore.qubit_reg<17>)
// CHECK-NEXT:      %19 = sobs.locate_observable(%0) on(%4, %7, %10) -> !sobs.observable
// CHECK-NEXT:      qstruct.yield %19, %1 : !sobs.observable, !qcore.qubit_reg<17>
// CHECK-NEXT:    }

// CHECK-NEXT:    %log = log_asm.measure<Z> (%obs_9 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> i1
}
// CHECK-NEXT:  }


// ----
// CHECK: ----

// Declaration with locates in a repeat block.
builtin.module {
// CHECK:       builtin.module {

    %obs_0 = sobs.dec_unplaced_observable -> !sobs.unplaced_observable
    %p0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=h_z>
    %p0_1 = log_asm.prepare<Z> (%p0 : !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=h_z>)
// CHECK-NEXT:    %p0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
// CHECK-NEXT:    %p0_1 = log_asm.prepare<Z> (%p0 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)


    %obs_1 = sobs.locate_unplaced_observable<Z>(%obs_0) on (%p0_1) -> !sobs.unplaced_observable
// CHECK-NEXT:    %obs = log_asm.cast(%p0_1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> !qcore.qubit_reg<17>
// CHECK-NEXT:    %obs_1, %obs_2 = qstruct.circuit(%obs : !qcore.qubit_reg<17>) -> !sobs.observable, !qcore.qubit_reg<17> {
// CHECK-NEXT:    ^bb0(%0: !qcore.qubit_reg<17>):
// CHECK-NEXT:      %1, %2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14, %15, %16, %17 = qcore.unpack_qubit_reg(%0 : !qcore.qubit_reg<17>)
// CHECK-NEXT:      %18 = sobs.dec_observable(%3, %6, %9) -> !sobs.observable
// CHECK-NEXT:      qstruct.yield %18, %0 : !sobs.observable, !qcore.qubit_reg<17>
// CHECK-NEXT:    }
// CHECK-NEXT:    %obs_3 = log_asm.cast(%obs_2 : !qcore.qubit_reg<17>) -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
// CHECK-NEXT:    %obs_4 = builtin.unrealized_conversion_cast %obs_1 : !sobs.observable to !sobs.unplaced_observable

    %p0_2, %obs_2 = qstruct.repeat<5>(%p0_1, %obs_1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=h_z>, !sobs.unplaced_observable) -> !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=h_z>, !sobs.unplaced_observable {
    ^bb0(%p: !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=h_z>, %obs: !sobs.unplaced_observable):
        %p1 = log_asm.meas_stab<3> (%p : !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=h_z>)
        %obs1 = sobs.locate_unplaced_observable<Z>(%obs) on (%p1) -> !sobs.unplaced_observable
        qstruct.yield %p1, %obs1: !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=h_z>, !sobs.unplaced_observable
    }
// CHECK-NEXT:    %p0_2, %obs_5 = qstruct.repeat<5> (%obs_3, %obs_4 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>, !sobs.unplaced_observable) -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>, !sobs.unplaced_observable {
// CHECK-NEXT:    ^bb0(%p: !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>, %obs_6: !sobs.unplaced_observable):
// CHECK-NEXT:      %p1 = log_asm.meas_stab<3> (%p : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)
// CHECK-NEXT:      %obs1 = log_asm.cast(%p1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> !qcore.qubit_reg<17>
// CHECK-NEXT:      %obs1_1 = builtin.unrealized_conversion_cast %obs_6 : !sobs.unplaced_observable to !sobs.observable
// CHECK-NEXT:      %obs1_2, %obs1_3 = qstruct.circuit(%obs1_1, %obs1 : !sobs.observable, !qcore.qubit_reg<17>) -> !sobs.observable, !qcore.qubit_reg<17> {
// CHECK-NEXT:      ^bb1(%0: !sobs.observable, %1: !qcore.qubit_reg<17>):
// CHECK-NEXT:        %2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14, %15, %16, %17, %18 = qcore.unpack_qubit_reg(%1 : !qcore.qubit_reg<17>)
// CHECK-NEXT:        %19 = sobs.locate_observable(%0) on(%4, %7, %10) -> !sobs.observable
// CHECK-NEXT:        qstruct.yield %19, %1 : !sobs.observable, !qcore.qubit_reg<17>
// CHECK-NEXT:      }
// CHECK-NEXT:      %obs1_4 = log_asm.cast(%obs1_3 : !qcore.qubit_reg<17>) -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
// CHECK-NEXT:      %obs1_5 = builtin.unrealized_conversion_cast %obs1_2 : !sobs.observable to !sobs.unplaced_observable
// CHECK-NEXT:      qstruct.yield %obs1_4, %obs1_5 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>, !sobs.unplaced_observable
// CHECK-NEXT:    }

    %log = log_asm.measure<Z> (%p0_2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0, 0), orient=h_z>) -> i1
// CHECK-NEXT:    %log = log_asm.measure<Z> (%p0_2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> i1

}
// CHECK-NEXT:  }
