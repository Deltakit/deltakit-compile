// RUN: deltakit_compile compile-passes %s -p stim-export-pipeline --pass-args '{"verify_between_passes": true}' -O %t && filecheck %s --input-file %t


builtin.module {
    %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    %qreg1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    %qq1 = qcore.alloc_qubit -> !qcore.qubit

// CHECK:       builtin.module {
// CHECK-NEXT:    %qreg0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:    %qreg0_1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:    %qreg1 = stim.qubit_alloc 2 -> !stim.qubit
// CHECK-NEXT:    %qreg1_1 = stim.qubit_alloc 3 -> !stim.qubit
// CHECK-NEXT:    %qq1 = stim.qubit_alloc 4 -> !stim.qubit

    %qreg0_4, %obs_out_out, %qreg1_4, %qq1_1 = qstruct.parallel<TOP> -> !qcore.qubit_reg<2>, !qec.observable, !qcore.qubit_reg<2>, !qcore.qubit {
        // Circuit 1
        %q00, %q11 = qcore.unpack_qubit_reg(%qreg0 : !qcore.qubit_reg<2>)
        %qreg00 = qcore.pack_qubit_reg(%q00, %q11) -> !qcore.qubit_reg<2>
        %qreg0_3, %obs_out = qstruct.circuit(%qreg00 : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2>, !qec.observable {
        ^bb0(%qreg0_1: !qcore.qubit_reg<2>):
            %q0, %q1= qcore.unpack_qubit_reg(%qreg0_1 : !qcore.qubit_reg<2>)
            %obs = qec.dec_observable -> !qec.observable
            %obs_2 = qstruct.repeat<5> (%obs : !qec.observable) -> !qec.observable {
            ^bb1(%obs_in: !qec.observable):
              %m0, %m1 = qref.measure<Z>(%q0, %q1) -> i1, i1
              %d0 = qec.detector(%m0, %m1)
              qec.detector_round(%d0)
              %obs1 = qec.observable_include(%obs_in) using (%m0) -> !qec.observable
              qstruct.yield %obs1 : !qec.observable
            }
            %qreg0_2 = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
            qstruct.yield %qreg0_2, %obs_2 : !qcore.qubit_reg<2>, !qec.observable
        }
        // End of circuit 1
        qstruct.yield %qreg0_3, %obs_out : !qcore.qubit_reg<2>, !qec.observable
    } {
        // Circuit 2
        %qreg1_3, %qqq_1 = qstruct.circuit(%qreg1, %qq1 : !qcore.qubit_reg<2>, !qcore.qubit) -> !qcore.qubit_reg<2>, !qcore.qubit {
        ^bb1(%qreg1_1: !qcore.qubit_reg<2>, %qq_1: !qcore.qubit):
            %q0, %q1 = qcore.unpack_qubit_reg(%qreg1_1 : !qcore.qubit_reg<2>)
            qref.gate<#qcore.gate.unitary<[
              [(1.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
              [(0.0, 0.0), (1.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
              [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (1.0, 0.0)],
              [(0.0, 0.0), (0.0, 0.0), (1.0, 0.0), (0.0, 0.0)]
            ]>> (%q0, %q1)
            qstruct.parallel<TOP> -> {
                qref.gate<#qcore.gate.unitary<[[(0.5, 0.5), (0.5, -0.5)], [(0.5, -0.5), (0.5, 0.5)]]>> (%q0)
                qstruct.yield
            }
            {
                qref.gate<#qcore.gate.unitary<[[(0.0, 0.0), (0.0, -1.0)], [(0.0, 1.0), (0.0, 0.0)]]>> (%q1)
                qref.reset<Z> (%q1)
                qstruct.yield
            }
            %m0, %m1 = qref.measure<Z>(%q0, %q1) -> i1, i1
            %d0 = qec.detector(%m0, %m1)
            qec.detector_round(%d0)
            %qreg1_2 = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
            qstruct.yield %qreg1_2, %qq_1 : !qcore.qubit_reg<2>, !qcore.qubit
        }
        // End of circuit 2
        %q0, %q1 = qcore.unpack_qubit_reg(%qreg1_3 : !qcore.qubit_reg<2>)
        %qreg11 = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
        qstruct.yield %qreg11, %qqq_1 : !qcore.qubit_reg<2>, !qcore.qubit
    }
  %11 = qec.get_corrected(%obs_out_out : !qec.observable) -> i1
  qstruct.output(%11 : i1)
}


// CHECK-NEXT:    stim.clifford CNOT (%qreg1, %qreg1_1)
// CHECK-NEXT:    stim.clifford SQRT_X (%qreg1)
// CHECK-NEXT:    stim.clifford Y (%qreg1_1)
// CHECK-NEXT:    stim.reset Z (%qreg1_1)
// CHECK-NEXT:    %m0, %m1 = stim.measure Z (%qreg1, %qreg1_1) -> i1, i1
// CHECK-NEXT:    stim.detector <[0.0]> (%m0, %m1 : i1, i1)
// CHECK-NEXT:    stim.tick
// CHECK-NEXT:    stim.repeat 5 () {
// CHECK-NEXT:      %m0_1, %m1_1 = stim.measure Z (%qreg0, %qreg0_1) -> i1, i1
// CHECK-NEXT:      stim.detector <[1.0]> (%m0_1, %m1_1 : i1, i1)
// CHECK-NEXT:      stim.observable_include <0> (%m0_1 : i1)
// CHECK-NEXT:      stim.shift_coord <[1.0]>
// CHECK-NEXT:      stim.yield
// CHECK-NEXT:    }
// CHECK-NEXT:    stim.tick
// CHECK-NEXT:  }
