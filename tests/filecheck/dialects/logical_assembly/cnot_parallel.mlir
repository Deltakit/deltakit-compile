// RUN: ROUNDTRIP_MLIR
builtin.module {

    // Declare input patches
    %patch_A_0_ = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
    %patch_B_0_ = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>

    // Prepare input patches
    // (Since many ops don't change the type of the result - the `->` [type] part of the normal mlir operation syntax is omitted
    // from the dialect where possible. The return type of prepare is just the same as the operand type.)
    %patch_A_2_, %patch_B_2_ = qstruct.parallel<TOP> ->
                !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>,
                !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>
    {
        %patch_A_1_p = log_asm.prepare<Z> (%patch_A_0_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)
        %patch_A_2_p = log_asm.meas_stab<3> (%patch_A_1_p : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)
        qstruct.yield %patch_A_2_p : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
    } {
        %patch_B_1_p = log_asm.prepare<Z> (%patch_B_0_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>)
        %patch_B_2_p = log_asm.meas_stab<3> (%patch_B_1_p : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>)
        qstruct.yield %patch_B_2_p : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>
    }

    // Declare and prepare patches for the first multi-pauli. patch_dec and prepare can be considered to take 0 rounds in block graphs.
    %patch_C_1_ = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>
    %patch_C_2_ = log_asm.prepare<X> (%patch_C_1_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>)
    %bridgeAC_2_ = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 1), location=(0.0, 3.0), orient=h_z>

    // First multi-pauli, while B continues with stabilisers
    %measurement_AC, %patch_A_3_, %patch_C_3_, %patch_B_3_ = qstruct.parallel<TOP> ->
                i1,
                !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>,
                !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>,
                !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>
    {
        %measurement_AC_p, %patch_A_3_p, %patch_C_3_p = log_asm.multi_pauli_meas<3, (Z, Z)>
            (%patch_A_2_, %patch_C_2_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>,
                                    !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>)
            (%bridgeAC_2_ : !log_asm.patch.rot_planar<size=(3, 1), location=(0.0, 3.0), orient=h_z>) -> i1
        qstruct.yield %measurement_AC_p, %patch_A_3_p, %patch_C_3_p :
                    i1,
                    !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>,
                    !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>
    } {
        %patch_B_3_p = log_asm.meas_stab<3> (%patch_B_2_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>)
        qstruct.yield %patch_B_3_p : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>
    }

    // Stabilisers on all the logical patches - this is not actually required for an efficient CNOT implementation but is included here
    // to demonstrate uses of qstruct.parallel with 3 simultaneous regions.
    %patch_A_4_, %patch_B_4_, %patch_C_4_ = qstruct.parallel<TOP> ->
                !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>,
                !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>,
                !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>
    {
        %patch_A_4_p = log_asm.meas_stab<3> (%patch_A_3_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)
        qstruct.yield %patch_A_4_p : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
    } {
        %patch_B_4_p = log_asm.meas_stab<3> (%patch_B_3_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>)
        qstruct.yield %patch_B_4_p : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>
    } {
        %patch_C_4_p = log_asm.meas_stab<3> (%patch_C_3_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>)
        qstruct.yield %patch_C_4_p : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>
    }

    // Declare bridge patch for the second multi-pauli
    %bridgeBC_4_ = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(1, 3), location=(3.0, 4.0), orient=h_z>

    // Second multi-pauli while A continues with stabilisers
    %measurement_BC, %patch_B_5_, %patch_C_5_, %patch_A_5_ = qstruct.parallel<TOP> ->
                i1,
                !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>,
                !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>,
                !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
    {
        %measurement_BC_p, %patch_B_5_p, %patch_C_5_p = log_asm.multi_pauli_meas<3, (X, X)>
            (%patch_B_4_, %patch_C_4_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>,
                                    !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>)
            (%bridgeBC_4_ : !log_asm.patch.rot_planar<size=(1, 3), location=(3.0, 4.0), orient=h_z>) -> i1
        qstruct.yield %measurement_BC_p, %patch_B_5_p, %patch_C_5_p :
                    i1,
                    !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>,
                    !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>
    } {
        %patch_A_5_p = log_asm.meas_stab<3> (%patch_A_4_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)
        qstruct.yield %patch_A_5_p : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
    }

    // Measure out patch C, this can also be considered to take 0 rounds in a block graph diagram
    // Measurements do not return the logical patch operands - there is only one result, which has type i1 (bool).
    %measurementC = log_asm.measure<Z> (%patch_C_5_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>) -> i1

    // Stabilisers on the logical patches A and B.
    %patch_A_6_, %patch_B_6_ = qstruct.parallel<TOP> ->
                !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>,
                !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>
    {
        %patch_A_6_p = log_asm.meas_stab<3> (%patch_A_5_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)
        qstruct.yield %patch_A_6_p : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
    } {
        %patch_B_6_p = log_asm.meas_stab<3> (%patch_B_5_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>)
        qstruct.yield %patch_B_6_p : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>
    }

    // Measure out A and B
    %measurementA, %measurementB = qstruct.parallel<TOP> -> i1, i1
    {
        %measurementA_p = log_asm.measure<Z> (%patch_A_4_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> i1
        qstruct.yield %measurementA_p : i1
    } {
        %measurementB_p = log_asm.measure<Z> (%patch_B_6_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>) -> i1
        qstruct.yield %measurementB_p : i1
    }

    // Our measurement results are: %measurement_AC, %measurement_BC, %measurementC, and then %measurementA and %measurementB
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %patch_A_0_ = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
// CHECK-NEXT:    %patch_B_0_ = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>
// CHECK-NEXT:    %patch_A_2_, %patch_B_2_ = qstruct.parallel<TOP> -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z> {
// CHECK-NEXT:      %patch_A_1_p = log_asm.prepare<Z> (%patch_A_0_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)
// CHECK-NEXT:      %patch_A_2_p = log_asm.meas_stab<3> (%patch_A_1_p : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)
// CHECK-NEXT:      qstruct.yield %patch_A_2_p : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
// CHECK-NEXT:    } {
// CHECK-NEXT:      %patch_B_1_p = log_asm.prepare<Z> (%patch_B_0_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>)
// CHECK-NEXT:      %patch_B_2_p = log_asm.meas_stab<3> (%patch_B_1_p : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>)
// CHECK-NEXT:      qstruct.yield %patch_B_2_p : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>
// CHECK-NEXT:    }
// CHECK-NEXT:    %patch_C_1_ = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>
// CHECK-NEXT:    %patch_C_2_ = log_asm.prepare<X> (%patch_C_1_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>)
// CHECK-NEXT:    %bridgeAC_2_ = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 1), location=(0.0, 3.0), orient=h_z>
// CHECK-NEXT:    %measurement_AC, %patch_A_3_, %patch_C_3_, %patch_B_3_ = qstruct.parallel<TOP> -> i1, !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z> {
// CHECK-NEXT:      %measurement_AC_p, %patch_A_3_p, %patch_C_3_p = log_asm.multi_pauli_meas<3, (Z, Z)> (%patch_A_2_, %patch_C_2_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>) (%bridgeAC_2_ : !log_asm.patch.rot_planar<size=(3, 1), location=(0.0, 3.0), orient=h_z>) -> i1
// CHECK-NEXT:      qstruct.yield %measurement_AC_p, %patch_A_3_p, %patch_C_3_p : i1, !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>
// CHECK-NEXT:    } {
// CHECK-NEXT:      %patch_B_3_p = log_asm.meas_stab<3> (%patch_B_2_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>)
// CHECK-NEXT:      qstruct.yield %patch_B_3_p : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>
// CHECK-NEXT:    }
// CHECK-NEXT:    %patch_A_4_, %patch_B_4_, %patch_C_4_ = qstruct.parallel<TOP> -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z> {
// CHECK-NEXT:      %patch_A_4_p = log_asm.meas_stab<3> (%patch_A_3_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)
// CHECK-NEXT:      qstruct.yield %patch_A_4_p : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
// CHECK-NEXT:    } {
// CHECK-NEXT:      %patch_B_4_p = log_asm.meas_stab<3> (%patch_B_3_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>)
// CHECK-NEXT:      qstruct.yield %patch_B_4_p : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>
// CHECK-NEXT:    } {
// CHECK-NEXT:      %patch_C_4_p = log_asm.meas_stab<3> (%patch_C_3_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>)
// CHECK-NEXT:      qstruct.yield %patch_C_4_p : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>
// CHECK-NEXT:    }
// CHECK-NEXT:    %bridgeBC_4_ = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(1, 3), location=(3.0, 4.0), orient=h_z>
// CHECK-NEXT:    %measurement_BC, %patch_B_5_, %patch_C_5_, %patch_A_5_ = qstruct.parallel<TOP> -> i1, !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z> {
// CHECK-NEXT:      %measurement_BC_p, %patch_B_5_p, %patch_C_5_p = log_asm.multi_pauli_meas<3, (X, X)> (%patch_B_4_, %patch_C_4_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>) (%bridgeBC_4_ : !log_asm.patch.rot_planar<size=(1, 3), location=(3.0, 4.0), orient=h_z>) -> i1
// CHECK-NEXT:      qstruct.yield %measurement_BC_p, %patch_B_5_p, %patch_C_5_p : i1, !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>
// CHECK-NEXT:    } {
// CHECK-NEXT:      %patch_A_5_p = log_asm.meas_stab<3> (%patch_A_4_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)
// CHECK-NEXT:      qstruct.yield %patch_A_5_p : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
// CHECK-NEXT:    }
// CHECK-NEXT:    %measurementC = log_asm.measure<Z> (%patch_C_5_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=h_z>) -> i1
// CHECK-NEXT:    %patch_A_6_, %patch_B_6_ = qstruct.parallel<TOP> -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z> {
// CHECK-NEXT:      %patch_A_6_p = log_asm.meas_stab<3> (%patch_A_5_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>)
// CHECK-NEXT:      qstruct.yield %patch_A_6_p : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>
// CHECK-NEXT:    } {
// CHECK-NEXT:      %patch_B_6_p = log_asm.meas_stab<3> (%patch_B_5_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>)
// CHECK-NEXT:      qstruct.yield %patch_B_6_p : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>
// CHECK-NEXT:    }
// CHECK-NEXT:    %measurementA, %measurementB = qstruct.parallel<TOP> -> i1, i1 {
// CHECK-NEXT:      %measurementA_p = log_asm.measure<Z> (%patch_A_4_ : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=h_z>) -> i1
// CHECK-NEXT:      qstruct.yield %measurementA_p : i1
// CHECK-NEXT:    } {
// CHECK-NEXT:      %measurementB_p = log_asm.measure<Z> (%patch_B_6_ : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 4.0), orient=h_z>) -> i1
// CHECK-NEXT:      qstruct.yield %measurementB_p : i1
// CHECK-NEXT:    }
// CHECK-NEXT:  }
