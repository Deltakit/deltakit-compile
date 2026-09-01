// RUN: deltakit_compile compile-passes %s -p logasm-api-to-logasm-pipeline --pass-args '{"verify_between_passes": true}' -O %t && filecheck %s --input-file %t


builtin.module {
}
// CHECK:       builtin.module {
// CHECK-NEXT:  }

// ----
// CHECK: ----

builtin.module {
  %qreg = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3)>
  %tensor = log_asm_api.cast(%qreg: !log_asm.patch.rot_planar<size=(3, 3)>) -> tensor<?x!qcore.qubit>
  %qreg_again = log_asm_api.cast(%tensor: tensor<?x!qcore.qubit>) -> !log_asm.patch.rot_planar<size=(3, 3)>
  %qreg_1 = func.call @my_subroutine(%qreg) : (!log_asm.patch.rot_planar<size=(3, 3)>) -> !log_asm.patch.rot_planar<size=(3, 3)>
  qstruct.output(:)
  func.func @my_subroutine(%qreg_2: !log_asm.patch.rot_planar<size=(3, 3)>) -> !log_asm.patch.rot_planar<size=(3, 3)> {
    %qreg_3 = log_asm.meas_stab<5> (%qreg_2 : !log_asm.patch.rot_planar<size=(3, 3)>)
    func.return %qreg_3 : !log_asm.patch.rot_planar<size=(3, 3)>
  }
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %qreg = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3)>
// CHECK-NEXT:    %qreg_1 = log_asm.meas_stab<5> (%qreg : !log_asm.patch.rot_planar<size=(3, 3)>)
// CHECK-NEXT:    qstruct.output(:)
// CHECK-NEXT:  }

// ----
// CHECK: ----

builtin.module {
  %qreg = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3)>
  %qreg_1 = log_asm.prepare<X> (%qreg : !log_asm.patch.rot_planar<size=(3, 3)>)
  %qreg_2 = log_asm.meas_stab<10> (%qreg_1 : !log_asm.patch.rot_planar<size=(3, 3)>)
  %0 = log_asm_api.cast(%qreg_2 : !log_asm.patch.rot_planar<size=(3, 3)>) -> tensor<?x!qcore.qubit>
  %1 = log_asm_api.call @my_circuit(%0) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
  %qreg_3 = log_asm_api.cast(%1 : tensor<?x!qcore.qubit>) -> !log_asm.patch.rot_planar<size=(3, 3)>
  %cexpr = log_asm.measure<X> (%qreg_3 : !log_asm.patch.rot_planar<size=(3, 3)>) -> i1
  %cexpr_1, %cexpr_2, %qreg_4 = func.call @my_subroutine(%qreg_3, %cexpr) : (!log_asm.patch.rot_planar<size=(3, 3)>, i1) -> (i1, i1, !log_asm.patch.rot_planar<size=(3, 3)>)
  %qreg_tensor_1 = log_asm_api.cast(%qreg_4 : !log_asm.patch.rot_planar<size=(3, 3)>) -> tensor<17x!qcore.qubit>
  %m_res, %qreg_tensor_2 = log_asm_api.call @my_circuit_2(%qreg_tensor_1) : (tensor<17x!qcore.qubit>) -> (tensor<2xi1>, tensor<17x!qcore.qubit>)
  %qreg_final = log_asm_api.cast(%qreg_tensor_2 : tensor<17x!qcore.qubit>) -> !log_asm.patch.rot_planar<size=(3, 3)>
  %zero = arith.constant 0 : index
  %bit_0 = tensor.extract %m_res[%zero] : tensor<2xi1>
  %one_2 = arith.constant 1 : index
  %bit_1 = tensor.extract %m_res[%one_2] : tensor<2xi1>
  qstruct.output(%cexpr, %bit_0, %bit_1 : i1, i1, i1)
  log_asm_api.circuit_dec @my_circuit(%qreg_5: tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
    log_asm_api.unsized_reset<Z> (%qreg_5 : tensor<?x!qcore.qubit>)
    log_asm_api.unsized_gate<#qcore.gate.h> (%qreg_5 : tensor<?x!qcore.qubit>)
    log_asm_api.unsized_gate<#qcore.gate.x> (%qreg_5 : tensor<?x!qcore.qubit>)
    log_asm_api.return %qreg_5 : tensor<?x!qcore.qubit>
  }
  log_asm_api.circuit_dec @my_circuit_2(%qubit_reg: tensor<17x!qcore.qubit>) -> (tensor<2xi1>, tensor<17x!qcore.qubit>) {
    %one = arith.constant 1 : index
    %q_1 = tensor.extract %qubit_reg[%one] : tensor<17x!qcore.qubit>
    %two = arith.constant 1 : index
    %q_2 = tensor.extract %qubit_reg[%two] : tensor<17x!qcore.qubit>
    %b, %b_1 = qref.measure<Z> (%q_1, %q_2) -> i1, i1
    %meas = tensor.from_elements %b, %b_1 : tensor<2xi1>
    log_asm_api.return %meas, %qubit_reg : tensor<2xi1>, tensor<17x!qcore.qubit>
  }
  func.func @my_subroutine(%qreg_5: !log_asm.patch.rot_planar<size=(3, 3)>, %cexpr_3: i1) -> (i1, i1, !log_asm.patch.rot_planar<size=(3, 3)>) {
    %qreg_6 = log_asm.prepare<Y> (%qreg_5 : !log_asm.patch.rot_planar<size=(3, 3)>)
    %qreg_7 = log_asm.meas_stab<5> (%qreg_6 : !log_asm.patch.rot_planar<size=(3, 3)>)
    %cexpr_4 = log_asm.measure<Z> (%qreg_7 : !log_asm.patch.rot_planar<size=(3, 3)>) -> i1
    func.return %cexpr_3, %cexpr_4, %qreg_7 : i1, i1, !log_asm.patch.rot_planar<size=(3, 3)>
  }
}
// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %qreg = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3)>
// CHECK-NEXT:    %qreg_1 = log_asm.prepare<X> (%qreg : !log_asm.patch.rot_planar<size=(3, 3)>)
// CHECK-NEXT:    %qreg_2 = log_asm.meas_stab<10> (%qreg_1 : !log_asm.patch.rot_planar<size=(3, 3)>)
// CHECK-NEXT:    %0 = log_asm.cast(%qreg_2 : !log_asm.patch.rot_planar<size=(3, 3)>) -> !qcore.qubit_reg<17>
// CHECK-NEXT:    %1 = qstruct.circuit(%0 : !qcore.qubit_reg<17>) -> !qcore.qubit_reg<17> {
// CHECK-NEXT:    ^bb0(%qreg_3: !qcore.qubit_reg<17>):
// CHECK-NEXT:      %2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14, %15, %16, %17, %18 = qcore.unpack_qubit_reg(%qreg_3 : !qcore.qubit_reg<17>)
// CHECK-NEXT:      qref.reset<Z> (%2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14, %15, %16, %17, %18)
// CHECK-NEXT:      qref.gate<#qcore.gate.h> (%2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14, %15, %16, %17, %18)
// CHECK-NEXT:      qref.gate<#qcore.gate.x> (%2, %3, %4, %5, %6, %7, %8, %9, %10, %11, %12, %13, %14, %15, %16, %17, %18)
// CHECK-NEXT:      qstruct.yield %qreg_3 : !qcore.qubit_reg<17>
// CHECK-NEXT:    }
// CHECK-NEXT:    %qreg_3 = log_asm.cast(%1 : !qcore.qubit_reg<17>) -> !log_asm.patch.rot_planar<size=(3, 3)>
// CHECK-NEXT:    %cexpr = log_asm.measure<X> (%qreg_3 : !log_asm.patch.rot_planar<size=(3, 3)>) -> i1
// CHECK-NEXT:    %qreg_4 = log_asm.prepare<Y> (%qreg_3 : !log_asm.patch.rot_planar<size=(3, 3)>)
// CHECK-NEXT:    %qreg_5 = log_asm.meas_stab<5> (%qreg_4 : !log_asm.patch.rot_planar<size=(3, 3)>)
// CHECK-NEXT:    %cexpr_1 = log_asm.measure<Z> (%qreg_5 : !log_asm.patch.rot_planar<size=(3, 3)>) -> i1
// CHECK-NEXT:    %qreg_tensor = log_asm.cast(%qreg_5 : !log_asm.patch.rot_planar<size=(3, 3)>) -> !qcore.qubit_reg<17>
// CHECK-NEXT:    %bit, %bit_1, %qreg_tensor_1 = qstruct.circuit(%qreg_tensor : !qcore.qubit_reg<17>) -> i1, i1, !qcore.qubit_reg<17> {
// CHECK-NEXT:    ^bb0(%qubit_reg: !qcore.qubit_reg<17>):
// CHECK-NEXT:      %q, %q_1, %q_2, %q_3, %q_4, %q_5, %q_6, %q_7, %q_8, %q_9, %q_10, %q_11, %q_12, %q_13, %q_14, %q_15, %q_16 = qcore.unpack_qubit_reg(%qubit_reg : !qcore.qubit_reg<17>)
// CHECK-NEXT:      %b, %b_1 = qref.measure<Z> (%q_1, %q_1) -> i1, i1
// CHECK-NEXT:      qstruct.yield %b, %b_1, %qubit_reg : i1, i1, !qcore.qubit_reg<17>
// CHECK-NEXT:    }
// CHECK-NEXT:    qstruct.output(%cexpr, %bit, %bit_1 : i1, i1, i1)
// CHECK-NEXT:  }

// ----
// CHECK: ----

builtin.module {
  %a0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>
  %b0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(1, 3), location=(3.0, 0.0), orient=v_z>
  %c0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 0.0), orient=v_z>

  %a1, %b1, %c1 = log_asm_api.barrier(%a0, %b0, %c0 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>, !log_asm.patch.rot_planar<size=(1, 3), location=(3.0, 0.0), orient=v_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 0.0), orient=v_z>)

  %a2 = log_asm.prepare<X> (%a1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>)
  %a3 = log_asm.meas_stab<10> (%a2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>)

  %c2 = log_asm.prepare<X> (%c1 : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 0.0), orient=v_z>)
  %c3 = log_asm.meas_stab<10> (%c2 : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 0.0), orient=v_z>)

  %m_ac, %a4, %c4 = log_asm.multi_pauli_meas<3, (Z, Z)>
            (%a3, %c3 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>,
                                    !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 0.0), orient=v_z>)
            (%b1 : !log_asm.patch.rot_planar<size=(1, 3), location=(3.0, 0.0), orient=v_z>) -> i1


  %a5 = log_asm.meas_stab<10> (%a4 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>)
  %c5 = log_asm.meas_stab<10> (%c4 : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 0.0), orient=v_z>)

  %m_a = log_asm.measure<Z> (%a5 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>) -> i1
  %a6, %c6 = log_asm_api.barrier(%a5, %c5 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 0.0), orient=v_z>)
  %m_c = log_asm.measure<Z> (%c6 : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 0.0), orient=v_z>) -> i1


  %d0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=v_z>
  func.func @my_subroutine(%x0: !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=v_z>, %x_m: i1) -> (i1, !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=v_z>) {
    %x1 = log_asm.prepare<Y> (%x0 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=v_z>)
    %x2 = log_asm.meas_stab<5> (%x1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=v_z>)
    %m_out = scf.if %x_m -> (i1) {
      %m_out1 = log_asm.measure<Z> (%x2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=v_z>) -> i1
      scf.yield %m_out1 : i1
    } else {
      %m_out2 = log_asm.measure<X> (%x2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=v_z>) -> i1
      scf.yield %m_out2 : i1
    }
    func.return %m_out, %x2 : i1, !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=v_z>
  }
  %m_d, %d1 = func.call @my_subroutine(%d0, %m_ac) : (!log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=v_z>, i1) -> (i1, !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=v_z>)

  qstruct.output(%m_ac, %m_a, %m_c, %m_d : i1, i1, i1, i1)
}


// CHECK-NEXT:  builtin.module {

//              The everything to do with a, b, c is in parallel to setting up d:
// CHECK-NEXT:    %m_ac, %m_a, %m_c, %x2 = qstruct.parallel<BOTTOM> -> i1, i1, i1, !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=v_z> {
//              All the patch declarations are in parallel but then barriers stop further parallelisation here
// CHECK-NEXT:      %a0, %b0, %c0 = qstruct.parallel<BOTTOM> -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>, !log_asm.patch.rot_planar<size=(1, 3), location=(3.0, 0.0), orient=v_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 0.0), orient=v_z> {
// CHECK-NEXT:        %a0_1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>
// CHECK-NEXT:        qstruct.yield %a0_1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>
// CHECK-NEXT:      } {
// CHECK-NEXT:        %b0_1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(1, 3), location=(3.0, 0.0), orient=v_z>
// CHECK-NEXT:        qstruct.yield %b0_1 : !log_asm.patch.rot_planar<size=(1, 3), location=(3.0, 0.0), orient=v_z>
// CHECK-NEXT:      } {
// CHECK-NEXT:        %c0_1 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 0.0), orient=v_z>
// CHECK-NEXT:        qstruct.yield %c0_1 : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 0.0), orient=v_z>
// CHECK-NEXT:      }
//              After the barrier - preparation/first measure stabilisers of a and b are parallelised
// CHECK-NEXT:      %a3, %c3 = qstruct.parallel<BOTTOM> -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 0.0), orient=v_z> {
// CHECK-NEXT:        %a2 = log_asm.prepare<X> (%a0 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:        %a3_1 = log_asm.meas_stab<10> (%a2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:        qstruct.yield %a3_1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>
// CHECK-NEXT:      } {
// CHECK-NEXT:        %c2 = log_asm.prepare<X> (%c0 : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 0.0), orient=v_z>)
// CHECK-NEXT:        %c3_1 = log_asm.meas_stab<10> (%c2 : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 0.0), orient=v_z>)
// CHECK-NEXT:        qstruct.yield %c3_1 : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 0.0), orient=v_z>
// CHECK-NEXT:      }
//              The multi pauli measure is still in parallel with preparing d but not anything else
// CHECK-NEXT:      %m_ac_1, %a4, %c4 = log_asm.multi_pauli_meas<3, (Z, Z)> (%a3, %c3 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>, !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 0.0), orient=v_z>) (%b0 : !log_asm.patch.rot_planar<size=(1, 3), location=(3.0, 0.0), orient=v_z>) -> i1
//              After the pauli pauli operations on a and c and be in parallel
// CHECK-NEXT:      %a5, %m_a_1, %c5 = qstruct.parallel<BOTTOM> -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>, i1, !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 0.0), orient=v_z> {
// CHECK-NEXT:        %a5_1 = log_asm.meas_stab<10> (%a4 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>)
// CHECK-NEXT:        %m_a_2 = log_asm.measure<Z> (%a5_1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>) -> i1
// CHECK-NEXT:        qstruct.yield %a5_1, %m_a_2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>, i1
// CHECK-NEXT:      } {
// CHECK-NEXT:        %c5_1 = log_asm.meas_stab<10> (%c4 : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 0.0), orient=v_z>)
// CHECK-NEXT:        qstruct.yield %c5_1 : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 0.0), orient=v_z>
// CHECK-NEXT:      }
//              The barrier stopped us putting the measure on c in parallel with anything on a
// CHECK-NEXT:      %m_c_1 = log_asm.measure<Z> (%c5 : !log_asm.patch.rot_planar<size=(3, 3), location=(4.0, 0.0), orient=v_z>) -> i1
// CHECK-NEXT:      qstruct.yield %m_ac_1, %m_a_1, %m_c_1 : i1, i1, i1
// CHECK-NEXT:    } {
//              This is in parallel with all the a,b,c stuff, but cannot be parallelised further
// CHECK-NEXT:      %d0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=v_z>
// CHECK-NEXT:      %x1 = log_asm.prepare<Y> (%d0 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=v_z>)
// CHECK-NEXT:      %x2_1 = log_asm.meas_stab<5> (%x1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=v_z>)
// CHECK-NEXT:      qstruct.yield %x2_1 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=v_z>
// CHECK-NEXT:    }
//              After all the a,b,c, stuff, we can do the rest of the d stuff - the if-statement control flow bits.
// CHECK-NEXT:    %m_out = scf.if %m_ac -> (i1) {
// CHECK-NEXT:      %m_out1 = log_asm.measure<Z> (%x2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=v_z>) -> i1
// CHECK-NEXT:      scf.yield %m_out1 : i1
// CHECK-NEXT:    } else {
// CHECK-NEXT:      %m_out2 = log_asm.measure<X> (%x2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 4.0), orient=v_z>) -> i1
// CHECK-NEXT:      scf.yield %m_out2 : i1
// CHECK-NEXT:    }
// CHECK-NEXT:    qstruct.output(%m_ac, %m_a, %m_c, %m_out : i1, i1, i1, i1)
// CHECK-NEXT:  }
