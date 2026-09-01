// RUN: deltakit_compile compile-passes -t %s -p parallelise-log-asm-api -O %t && filecheck %s --input-file %t

builtin.module {
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----


// simple memory circuit - no real parallelisation possible

builtin.module {
    %qreg = qcore.alloc_qubit<coords=[(0.5, 0.5), (1.5, 0.5), (1.0, 1.0)]> -> !qcore.qubit_reg<3>
    %p0 = log_asm.cast(%qreg : !qcore.qubit_reg<3>) -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>
    %p0_1 = log_asm.prepare<Z>(%p0 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>)
    %p0_2 = log_asm.meas_stab<2>(%p0_1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>)
    %log = log_asm.measure<Z>(%p0_2 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>) -> i1
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %qreg = qcore.alloc_qubit<coords = [(0.5, 0.5), (1.5, 0.5), (1.0, 1.0)]> -> !qcore.qubit_reg<3>
// CHECK-NEXT:    %p0 = log_asm.cast(%qreg : !qcore.qubit_reg<3>) -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>
// CHECK-NEXT:    %p0_1 = log_asm.prepare<Z> (%p0 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:    %p0_2 = log_asm.meas_stab<2> (%p0_1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:    %log = log_asm.measure<Z> (%p0_2 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>) -> i1
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

// sequential memory circuits on the same patch areas - no real parallelisation possible

builtin.module {
    %a0 = qcore.alloc_qubit<coords=[(0.5, 0.5), (1.5, 0.5), (1.0, 1.0)]> -> !qcore.qubit_reg<3>
    %a1 = log_asm.cast(%a0 : !qcore.qubit_reg<3>) -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>
    %a2 = log_asm.prepare<Z>(%a1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>)
    %a3 = log_asm.meas_stab<2>(%a2 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>)
    %a4 = log_asm.measure<Z>(%a3 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>) -> i1

    %b0 = qcore.alloc_qubit<coords=[(0.5, 0.5), (1.5, 0.5), (1.0, 1.0)]> -> !qcore.qubit_reg<3>
    %b1 = log_asm.cast(%b0 : !qcore.qubit_reg<3>) -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>
    %b2 = log_asm.prepare<Z>(%b1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>)
    %b3 = log_asm.meas_stab<2>(%b2 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>)
    %b4 = log_asm.measure<Z>(%b3 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>) -> i1
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %a0 = qcore.alloc_qubit<coords = [(0.5, 0.5), (1.5, 0.5), (1.0, 1.0)]> -> !qcore.qubit_reg<3>
// CHECK-NEXT:    %a1 = log_asm.cast(%a0 : !qcore.qubit_reg<3>) -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>
// CHECK-NEXT:    %a2 = log_asm.prepare<Z> (%a1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:    %a3 = log_asm.meas_stab<2> (%a2 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:    %a4 = log_asm.measure<Z> (%a3 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>) -> i1
// CHECK-NEXT:    %b0 = qcore.alloc_qubit<coords = [(0.5, 0.5), (1.5, 0.5), (1.0, 1.0)]> -> !qcore.qubit_reg<3>
// CHECK-NEXT:    %b1 = log_asm.cast(%b0 : !qcore.qubit_reg<3>) -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>
// CHECK-NEXT:    %b2 = log_asm.prepare<Z> (%b1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:    %b3 = log_asm.meas_stab<2> (%b2 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:    %b4 = log_asm.measure<Z> (%b3 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>) -> i1
// CHECK-NEXT:  }


// ----
// CHECK-NEXT: ----

// memory circuits in parallel

builtin.module {
    %a1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>
    %a2 = log_asm.prepare<Z>(%a1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>)
    %a3 = log_asm.meas_stab<2>(%a2 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>)
    %a4 = log_asm.measure<Z>(%a3 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>) -> i1

    %b1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(2, 1), location=(0, 1), orient=v_z>
    %b2 = log_asm.prepare<Z>(%b1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 1), orient=v_z>)
    %b3 = log_asm.meas_stab<2>(%b2 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 1), orient=v_z>)
    %b4 = log_asm.measure<Z>(%b3 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 1), orient=v_z>) -> i1
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    qstruct.parallel<TOP> -> {
// CHECK-NEXT:      %a1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>
// CHECK-NEXT:      %a2 = log_asm.prepare<Z> (%a1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:      %a3 = log_asm.meas_stab<2> (%a2 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:      %a4 = log_asm.measure<Z> (%a3 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>) -> i1
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    } {
// CHECK-NEXT:      %b1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 1.0), orient=v_z>
// CHECK-NEXT:      %b2 = log_asm.prepare<Z> (%b1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 1.0), orient=v_z>)
// CHECK-NEXT:      %b3 = log_asm.meas_stab<2> (%b2 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 1.0), orient=v_z>)
// CHECK-NEXT:      %b4 = log_asm.measure<Z> (%b3 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 1.0), orient=v_z>) -> i1
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    }
// CHECK-NEXT:  }


// ----
// CHECK-NEXT: ----

// memory circuits in parallel, but stopped by a barrier.

builtin.module {
    %a1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>
    %a2 = log_asm.prepare<Z>(%a1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>)
    %a3 = log_asm.meas_stab<2>(%a2 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>)
    %a4 = log_asm.measure<Z>(%a3 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>) -> i1

    %b0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(2, 1), location=(0, 1), orient=v_z>
    %a5, %b1 = log_asm_api.barrier(%a3, %b0 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>, !log_asm.patch.rot_planar<size=(2, 1), location=(0, 1), orient=v_z>)

    %b2 = log_asm.prepare<Z>(%b1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 1), orient=v_z>)
    %b3 = log_asm.meas_stab<2>(%b2 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 1), orient=v_z>)
    %b4 = log_asm.measure<Z>(%b3 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 1), orient=v_z>) -> i1
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %a3, %b0 = qstruct.parallel<BOTTOM> -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>, !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 1.0), orient=v_z> {
// CHECK-NEXT:      %a1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>
// CHECK-NEXT:      %a2 = log_asm.prepare<Z> (%a1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:      %a3_1 = log_asm.meas_stab<2> (%a2 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:      %a4 = log_asm.measure<Z> (%a3_1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>) -> i1
// CHECK-NEXT:      qstruct.yield %a3_1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>
// CHECK-NEXT:    } {
// CHECK-NEXT:      %b0_1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 1.0), orient=v_z>
// CHECK-NEXT:      qstruct.yield %b0_1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 1.0), orient=v_z>
// CHECK-NEXT:    }
// CHECK-NEXT:    %b2 = log_asm.prepare<Z> (%b0 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 1.0), orient=v_z>)
// CHECK-NEXT:    %b3 = log_asm.meas_stab<2> (%b2 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 1.0), orient=v_z>)
// CHECK-NEXT:    %b4 = log_asm.measure<Z> (%b3 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 1.0), orient=v_z>) -> i1
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

// 2 multi-pauli products on shared patches

builtin.module {
    %a1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>
    %a2 = log_asm.prepare<Z>(%a1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>)
    %a3 = log_asm.meas_stab<2>(%a2 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>)

    %b1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(2, 1), location=(0, 2), orient=v_z>
    %b2 = log_asm.prepare<Z>(%b1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 2), orient=v_z>)
    %b3 = log_asm.meas_stab<2>(%b2 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 2), orient=v_z>)

    %c = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(2, 1), location=(0, 1), orient=v_z>

    %m1, %a4, %b4 = log_asm.multi_pauli_meas<3, (Z, Z)>
            (%a3, %b3 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>,
                                    !log_asm.patch.rot_planar<size=(2, 1), location=(0, 2), orient=v_z>)
            (%c : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 1), orient=v_z>) -> i1

    %d = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(2, 1), location=(0, 3), orient=v_z>

    %e1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(2, 1), location=(0, 4), orient=v_z>
    %e2 = log_asm.prepare<Z>(%e1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 4), orient=v_z>)
    %e3 = log_asm.meas_stab<2>(%e2 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 4), orient=v_z>)

    %m2, %b5, %e4 = log_asm.multi_pauli_meas<3, (Z, Z)>
            (%b4, %e3 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 2), orient=v_z>,
                                    !log_asm.patch.rot_planar<size=(2, 1), location=(0, 4), orient=v_z>)
            (%d : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 3), orient=v_z>) -> i1

    %a5 = log_asm.meas_stab<2>(%a4 : !log_asm.patch.rot_planar<size=(2, 1), location=(0, 0), orient=v_z>)
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %a4, %b4, %d, %e3 = qstruct.parallel<BOTTOM> -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>, !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 2.0), orient=v_z>, !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 3.0), orient=v_z>, !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 4.0), orient=v_z> {
// CHECK-NEXT:      %a3, %b3, %c = qstruct.parallel<BOTTOM> -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>, !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 2.0), orient=v_z>, !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 1.0), orient=v_z> {
// CHECK-NEXT:        %a1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>
// CHECK-NEXT:        %a2 = log_asm.prepare<Z> (%a1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:        %a3_1 = log_asm.meas_stab<2> (%a2 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:        qstruct.yield %a3_1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>
// CHECK-NEXT:      } {
// CHECK-NEXT:        %b1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 2.0), orient=v_z>
// CHECK-NEXT:        %b2 = log_asm.prepare<Z> (%b1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 2.0), orient=v_z>)
// CHECK-NEXT:        %b3_1 = log_asm.meas_stab<2> (%b2 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 2.0), orient=v_z>)
// CHECK-NEXT:        qstruct.yield %b3_1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 2.0), orient=v_z>
// CHECK-NEXT:      } {
// CHECK-NEXT:        %c_1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 1.0), orient=v_z>
// CHECK-NEXT:        qstruct.yield %c_1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 1.0), orient=v_z>
// CHECK-NEXT:      }
// CHECK-NEXT:      %m1, %a4_1, %b4_1 = log_asm.multi_pauli_meas<3, (Z, Z)> (%a3, %b3 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>, !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 2.0), orient=v_z>) (%c : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 1.0), orient=v_z>) -> i1
// CHECK-NEXT:      qstruct.yield %a4_1, %b4_1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>, !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 2.0), orient=v_z>
// CHECK-NEXT:    } {
// CHECK-NEXT:      %d_1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 3.0), orient=v_z>
// CHECK-NEXT:      qstruct.yield %d_1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 3.0), orient=v_z>
// CHECK-NEXT:    } {
// CHECK-NEXT:      %e1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 4.0), orient=v_z>
// CHECK-NEXT:      %e2 = log_asm.prepare<Z> (%e1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 4.0), orient=v_z>)
// CHECK-NEXT:      %e3_1 = log_asm.meas_stab<2> (%e2 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 4.0), orient=v_z>)
// CHECK-NEXT:      qstruct.yield %e3_1 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 4.0), orient=v_z>
// CHECK-NEXT:    }
// CHECK-NEXT:    qstruct.parallel<TOP> -> {
// CHECK-NEXT:      %m2, %b5, %e4 = log_asm.multi_pauli_meas<3, (Z, Z)> (%b4, %e3 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 2.0), orient=v_z>, !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 4.0), orient=v_z>) (%d : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 3.0), orient=v_z>) -> i1
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    } {
// CHECK-NEXT:      %a5 = log_asm.meas_stab<2> (%a4 : !log_asm.patch.rot_planar<size=(2, 1), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    }
// CHECK-NEXT:  }
