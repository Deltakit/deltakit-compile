// RUN: deltakit_compile compile-passes -t %s -p parallelise-log-asm-api -O %t && filecheck %s --input-file %t
builtin.module {

    // Declare input patches
    %patch_A_0_ = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
    %patch_B_0_ = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>

    // Prepare input patches
    // (Since many ops don't change the type of the result - the `->` [type] part of the normal mlir operation syntax is omitted
    // from the dialect where possible. The return type of prepare is just the same as the operand type.)
    %patch_A_1_ = log_asm.prepare<Z> (%patch_A_0_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)
    %patch_B_1_ = log_asm.prepare<Z> (%patch_B_0_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>)

    // Initial measure stabilisers
    %patch_A_2_ = log_asm.meas_stab<3> (%patch_A_1_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)
    %patch_B_2_ = log_asm.meas_stab<3> (%patch_B_1_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>)

    // Declare and prepare patches for the first multi-pauli
    %patch_C_1_ = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>
    %patch_C_2_ = log_asm.prepare<X> (%patch_C_1_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>)
    %bridgeAC_2_ = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 1), location=(0.0, 3.0), orient=h_z>

    // First multi-pauli
    // The return types are i1 followed simply by the types of the logical patch operands, so these are not repeated in the syntax.
    %measurement_AC, %patch_A_3_, %patch_C_3_ = log_asm.multi_pauli_meas<3, (Z, Z)>
        (%patch_A_2_, %patch_C_2_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>,
                                !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>)
        (%bridgeAC_2_ : !log_asm.patch.rot_planar<size=(3, 1), location=(0.0, 3.0), orient=h_z>) -> i1

    // Stabilisers on all the logical patches
    %patch_A_4_ = log_asm.meas_stab<3> (%patch_A_3_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) {tag = "hi"}
    %patch_B_4_ = log_asm.meas_stab<3> (%patch_B_2_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>)
    %patch_C_4_ = log_asm.meas_stab<3> (%patch_C_3_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>)

    // Declare and prepare patches for the second multi-pauli
    %bridgeBC_4_ = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(1, 3), location=(3.0, 4.0), orient=h_z>

    // Second multi-pauli
    %measurement_BC, %patch_B_5_, %patch_C_5_ = log_asm.multi_pauli_meas<3, (X, X)>
        (%patch_B_4_, %patch_C_4_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>,
                                !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>)
        (%bridgeBC_4_ : !log_asm.patch.rot_planar<size=(1, 3), location=(3.0, 4.0), orient=h_z>) -> i1

    // Measure out patch C
    // Measurements do not return the logical patch operands - there is only one result, which has type i1 (bool).
    %measurementC = log_asm.measure<Z> (%patch_C_5_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>) -> i1

    // Stabilisers on all the logical patches
    // No need to do it on A since the last op on A was a meas_stab which will 'grow' in rounds to fill the gap
    %patch_B_6_ = log_asm.meas_stab<3> (%patch_B_5_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>)

    // Measure out A and B
    %measurementA = log_asm.measure<Z> (%patch_A_4_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> i1
    %measurementB = log_asm.measure<Z> (%patch_B_6_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>) -> i1

    // Our measurement results are: %measurement_AC, %measurement_BC, %measurementC, and then %measurementA and %measurementB
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %patch_B_4_, %patch_A_4_, %patch_C_4_, %bridgeBC_4_ = qstruct.parallel<BOTTOM> -> !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>, !log_asm.patch.rot_planar<size=(1, 3), location=(3.0, 4.0), orient=h_z> {
// CHECK-NEXT:      %patch_B_0_ = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>
// CHECK-NEXT:      %patch_B_1_ = log_asm.prepare<Z> (%patch_B_0_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>)
// CHECK-NEXT:      %patch_B_2_ = log_asm.meas_stab<3> (%patch_B_1_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>)
// CHECK-NEXT:      %patch_B_4__1 = log_asm.meas_stab<3> (%patch_B_2_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>)
// CHECK-NEXT:      qstruct.yield %patch_B_4__1 : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>
// CHECK-NEXT:    } {
// CHECK-NEXT:      %patch_A_2_, %patch_C_2_, %bridgeAC_2_ = qstruct.parallel<BOTTOM> -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>, !log_asm.patch.rot_planar<size=(3, 1), location=(0.0, 3.0), orient=h_z> {
// CHECK-NEXT:        %patch_A_0_ = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
// CHECK-NEXT:        %patch_A_1_ = log_asm.prepare<Z> (%patch_A_0_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)
// CHECK-NEXT:        %patch_A_2__1 = log_asm.meas_stab<3> (%patch_A_1_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)
// CHECK-NEXT:        qstruct.yield %patch_A_2__1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
// CHECK-NEXT:      } {
// CHECK-NEXT:        %patch_C_1_ = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>
// CHECK-NEXT:        %patch_C_2__1 = log_asm.prepare<X> (%patch_C_1_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>)
// CHECK-NEXT:        qstruct.yield %patch_C_2__1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>
// CHECK-NEXT:      } {
// CHECK-NEXT:        %bridgeAC_2__1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 1), location=(0.0, 3.0), orient=h_z>
// CHECK-NEXT:        qstruct.yield %bridgeAC_2__1 : !log_asm.patch.rot_planar<size=(3, 1), location=(0.0, 3.0), orient=h_z>
// CHECK-NEXT:      }
// CHECK-NEXT:      %measurement_AC, %patch_A_3_, %patch_C_3_ = log_asm.multi_pauli_meas<3, (Z, Z)> (%patch_A_2_, %patch_C_2_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>) (%bridgeAC_2_ : !log_asm.patch.rot_planar<size=(3, 1), location=(0.0, 3.0), orient=h_z>) -> i1
// CHECK-NEXT:      %patch_A_4__1, %patch_C_4__1 = qstruct.parallel<BOTTOM> -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z> {
// CHECK-NEXT:        %patch_A_4__2 = log_asm.meas_stab<3> (%patch_A_3_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) {tag = "hi"}
// CHECK-NEXT:        qstruct.yield %patch_A_4__2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
// CHECK-NEXT:      } {
// CHECK-NEXT:        %patch_C_4__2 = log_asm.meas_stab<3> (%patch_C_3_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>)
// CHECK-NEXT:        qstruct.yield %patch_C_4__2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield %patch_A_4__1, %patch_C_4__1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>
// CHECK-NEXT:    } {
// CHECK-NEXT:      %bridgeBC_4__1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(1, 3), location=(3.0, 4.0), orient=h_z>
// CHECK-NEXT:      qstruct.yield %bridgeBC_4__1 : !log_asm.patch.rot_planar<size=(1, 3), location=(3.0, 4.0), orient=h_z>
// CHECK-NEXT:    }
// CHECK-NEXT:    qstruct.parallel<TOP> -> {
// CHECK-NEXT:      %measurement_BC, %patch_B_5_, %patch_C_5_ = log_asm.multi_pauli_meas<3, (X, X)> (%patch_B_4_, %patch_C_4_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>) (%bridgeBC_4_ : !log_asm.patch.rot_planar<size=(1, 3), location=(3.0, 4.0), orient=h_z>) -> i1
// CHECK-NEXT:      qstruct.parallel<TOP> -> {
// CHECK-NEXT:        %measurementC = log_asm.measure<Z> (%patch_C_5_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>) -> i1
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      } {
// CHECK-NEXT:        %patch_B_6_ = log_asm.meas_stab<3> (%patch_B_5_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>)
// CHECK-NEXT:        %measurementB = log_asm.measure<Z> (%patch_B_6_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>) -> i1
// CHECK-NEXT:        qstruct.yield
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    } {
// CHECK-NEXT:      %measurementA = log_asm.measure<Z> (%patch_A_4_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> i1
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    }
// CHECK-NEXT:  }
