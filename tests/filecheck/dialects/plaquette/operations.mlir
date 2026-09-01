// RUN: ROUNDTRIP_MLIR

builtin.module {

    %qreg_0 = qcore.alloc_qubit -> !qcore.qubit_reg<5>
    %qreg_1 = qstruct.circuit(%qreg_0 : !qcore.qubit_reg<5>) -> !qcore.qubit_reg<5> {
    ^bb0(%qreg_2: !qcore.qubit_reg<5>):
        %q0, %q1, %q2, %q3, %q4 = qcore.unpack_qubit_reg(%qreg_2 : !qcore.qubit_reg<5>)

        // plaquette.round with plaquette.plaquette
        %xxxx, %xxxx_scheduled = plaquette.round(%q0, %q1, %q2, %q3, %q4) -> i1, i1 {
        ^bb1(%q0_1 : !qcore.qubit, %q1_1 : !qcore.qubit, %q2_1 : !qcore.qubit, %q3_1 : !qcore.qubit, %q4_1 : !qcore.qubit):
            %m0 = plaquette.plaquette<[X0 X1 X2 X3 : 4]> on (%q0_1, %q1_1, %q2_1, %q3_1) using (%q4_1) {attr = "ibute"} -> i1
            plaquette.yield %m0 : i1
        }
        // Also part of the round, but with a schedule
        {
        ^bb2(%q0_2 : !qcore.qubit, %q1_2 : !qcore.qubit, %q2_2 : !qcore.qubit, %q3_2 : !qcore.qubit, %q4_2 : !qcore.qubit):
            %m0 = plaquette.plaquette<[X0 X1 X2 X3 : 4], #plaquette.synchronised_schedule<[1, 2, 3, 4]>> on (%q0_2, %q1_2, %q2_2, %q3_2) using (%q4_2) -> i1
            plaquette.yield %m0 : i1
        }

        // plaquette.round with plaquette.sub_circuit
        %xxxx_1 = plaquette.round(%q0, %q1, %q2, %q3, %q4) -> i1 {
        ^bb3(%q0_3 : !qcore.qubit, %q1_3 : !qcore.qubit, %q2_3 : !qcore.qubit, %q3_3 : !qcore.qubit, %q4_3 : !qcore.qubit):
            %m0_2 = plaquette.sub_circuit -> i1 {
                qref.reset<X>(%q4_3)
                plaquette.yield
            } {
                qref.gate<#qcore.gate.cx>(%q4_3, %q0_3)
                plaquette.yield
            } {
                qref.gate<#qcore.gate.cx>(%q4_3, %q1_3)
                plaquette.yield
            } {
                qref.gate<#qcore.gate.cx>(%q4_3, %q2_3)
                plaquette.yield
            } {
                qref.gate<#qcore.gate.cx>(%q4_3, %q3_3)
                plaquette.yield
            } {
                %xxxx_2 = qref.measure<X>(%q4_3) -> i1
                plaquette.yield %xxxx_2 : i1
            }
            plaquette.yield %m0_2 : i1
        }

        %qreg_3 = qcore.pack_qubit_reg(%q0, %q1, %q2, %q3, %q4) -> !qcore.qubit_reg<5>
        qstruct.yield %qreg_3 : !qcore.qubit_reg<5>
    }
}

// CHECK:       builtin.module {
// CHECK-NEXT:      %qreg = qcore.alloc_qubit -> !qcore.qubit_reg<5>
// CHECK-NEXT:      %qreg_1 = qstruct.circuit(%qreg : !qcore.qubit_reg<5>) -> !qcore.qubit_reg<5> {
// CHECK-NEXT:      ^bb0(%qreg_2: !qcore.qubit_reg<5>):
// CHECK-NEXT:          %q0, %q1, %q2, %q3, %q4 = qcore.unpack_qubit_reg(%qreg_2 : !qcore.qubit_reg<5>)

// CHECK-NEXT:          %xxxx, %xxxx_scheduled = plaquette.round(%q0, %q1, %q2, %q3, %q4) -> i1, i1 {
// CHECK-NEXT:          ^bb1(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit, %q2_1: !qcore.qubit, %q3_1: !qcore.qubit, %q4_1: !qcore.qubit):
// CHECK-NEXT:              %m0 = plaquette.plaquette<[X0 X1 X2 X3 : 4]> on (%q0_1, %q1_1, %q2_1, %q3_1) using (%q4_1) {attr = "ibute"} -> i1
// CHECK-NEXT:              plaquette.yield %m0 : i1
// CHECK-NEXT:          }

// CHECK-SAME:          {
// CHECK-NEXT:          ^bb2(%q0_2: !qcore.qubit, %q1_2: !qcore.qubit, %q2_2: !qcore.qubit, %q3_2: !qcore.qubit, %q4_2: !qcore.qubit):
// CHECK-NEXT:              %m0_1 = plaquette.plaquette<[X0 X1 X2 X3 : 4], #plaquette.synchronised_schedule<[1, 2, 3, 4]>> on (%q0_2, %q1_2, %q2_2, %q3_2) using (%q4_2) -> i1
// CHECK-NEXT:              plaquette.yield %m0_1 : i1
// CHECK-NEXT:          }

// CHECK-NEXT:          %xxxx_1 = plaquette.round(%q0, %q1, %q2, %q3, %q4) -> i1 {
// CHECK-NEXT:          ^bb3(%q0_3: !qcore.qubit, %q1_3: !qcore.qubit, %q2_3: !qcore.qubit, %q3_3: !qcore.qubit, %q4_3: !qcore.qubit):
// CHECK-NEXT:              %m0_2 = plaquette.sub_circuit -> i1 {
// CHECK-NEXT:                  qref.reset<X> (%q4_3)
// CHECK-NEXT:                  plaquette.yield
// CHECK-NEXT:              } {
// CHECK-NEXT:                  qref.gate<#qcore.gate.cx> (%q4_3, %q0_3)
// CHECK-NEXT:                  plaquette.yield
// CHECK-NEXT:              } {
// CHECK-NEXT:                  qref.gate<#qcore.gate.cx> (%q4_3, %q1_3)
// CHECK-NEXT:                  plaquette.yield
// CHECK-NEXT:              } {
// CHECK-NEXT:                  qref.gate<#qcore.gate.cx> (%q4_3, %q2_3)
// CHECK-NEXT:                  plaquette.yield
// CHECK-NEXT:              } {
// CHECK-NEXT:                  qref.gate<#qcore.gate.cx> (%q4_3, %q3_3)
// CHECK-NEXT:                  plaquette.yield
// CHECK-NEXT:              } {
// CHECK-NEXT:                  %xxxx_2 = qref.measure<X> (%q4_3) -> i1
// CHECK-NEXT:                  plaquette.yield %xxxx_2 : i1
// CHECK-NEXT:              }
// CHECK-NEXT:              plaquette.yield %m0_2 : i1
// CHECK-NEXT:          }

// CHECK-NEXT:          %qreg_3 = qcore.pack_qubit_reg(%q0, %q1, %q2, %q3, %q4) -> !qcore.qubit_reg<5>
// CHECK-NEXT:          qstruct.yield %qreg_3 : !qcore.qubit_reg<5>
// CHECK-NEXT:      }
// CHECK-NEXT:  }
