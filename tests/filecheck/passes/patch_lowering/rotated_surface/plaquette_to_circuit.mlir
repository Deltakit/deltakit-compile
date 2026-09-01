// RUN: deltakit_compile compile-passes -t %s -p plaquette-to-circuit -O %t && filecheck %s --input-file %t

// Check that a single valid plaquette is correctly lowered to a sub_circuit.
builtin.module {
// CHECK:       builtin.module {

    %p0, %p0_1, %p0_2 = "test.op"() : () -> (!qcore.qubit, !qcore.qubit, !qcore.qubit)
// CHECK-NEXT:  %p0, %p0_1, %p0_2 = "test.op"() : () -> (!qcore.qubit, !qcore.qubit, !qcore.qubit)

    %p0_3, %p0_4, %p0_5 = qstruct.repeat<2> (%p0, %p0_1, %p0_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
        ^bb0(%0: !qcore.qubit, %1: !qcore.qubit, %2: !qcore.qubit):
        %3, %4, %5, %6 = qstruct.circuit(%0, %1, %2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1 {
            ^bb1(%7: !qcore.qubit, %8: !qcore.qubit, %9: !qcore.qubit):
            %10 = plaquette.round(%7, %8, %9) {plaquette.z_observable_is_vertical = true} -> i1 {
                ^bb2(%11: !qcore.qubit, %12: !qcore.qubit, %13: !qcore.qubit):
                %14 = plaquette.plaquette<[Z0 Z1 : 2], #plaquette.synchronised_schedule<[1, 3]>> on (%11, %12) using (%13) {plaquette.shape_type = #plaquette.rotated_surface_plaquette_shape<TOP>} -> i1
                plaquette.yield %14 : i1
            }
            qstruct.yield %7, %8, %9, %10 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1
        }
        qstruct.yield %3, %4, %5 : !qcore.qubit, !qcore.qubit, !qcore.qubit
    }

// CHECK-NEXT:  %p0_3, %p0_4, %p0_5 = qstruct.repeat<2> (%p0, %p0_1, %p0_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:      ^bb0(%0: !qcore.qubit, %1: !qcore.qubit, %2: !qcore.qubit):
// CHECK-NEXT:      %3, %4, %5, %6 = qstruct.circuit(%0, %1, %2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1 {
// CHECK-NEXT:          ^bb1(%7: !qcore.qubit, %8: !qcore.qubit, %9: !qcore.qubit):
// CHECK-NEXT:          %10 = plaquette.round(%7, %8, %9) {plaquette.z_observable_is_vertical = true} -> i1 {
// CHECK-NEXT:              ^bb2(%11: !qcore.qubit, %12: !qcore.qubit, %13: !qcore.qubit):
// CHECK-NEXT:              %14 = plaquette.sub_circuit -> i1 {
// CHECK-NEXT:                  qref.reset<X> (%13)
// CHECK-NEXT:                  plaquette.yield
// CHECK-NEXT:              } {
// CHECK-NEXT:                  plaquette.yield
// CHECK-NEXT:              } {
// CHECK-NEXT:                  qref.gate<#qcore.gate.cz> (%13, %11)
// CHECK-NEXT:                  plaquette.yield
// CHECK-NEXT:              } {
// CHECK-NEXT:                  plaquette.yield
// CHECK-NEXT:              } {
// CHECK-NEXT:                  qref.gate<#qcore.gate.cz> (%13, %12)
// CHECK-NEXT:                  plaquette.yield
// CHECK-NEXT:              } {
// CHECK-NEXT:                  %15 = qref.measure<X> (%13) -> i1
// CHECK-NEXT:                  plaquette.yield %15 : i1
// CHECK-NEXT:              }
// CHECK-NEXT:              plaquette.yield %14 : i1
// CHECK-NEXT:          }
// CHECK-NEXT:          qstruct.yield %7, %8, %9, %10 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield %3, %4, %5 : !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:  }

}
// CHECK-NEXT:  }

// ----
// CHECK: ----

// Check that a single invalid plaquette is not changed.
builtin.module {
// CHECK:       builtin.module {

    %p0, %p0_1, %p0_2 = "test.op"() : () -> (!qcore.qubit, !qcore.qubit, !qcore.qubit)
// CHECK-NEXT:  %p0, %p0_1, %p0_2 = "test.op"() : () -> (!qcore.qubit, !qcore.qubit, !qcore.qubit)

    %p0_3, %p0_4, %p0_5 = qstruct.repeat<2> (%p0, %p0_1, %p0_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
    ^bb0(%0: !qcore.qubit, %1: !qcore.qubit, %2: !qcore.qubit):
        %3, %4, %5, %6 = qstruct.circuit(%0, %1, %2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1 {
        ^bb1(%7: !qcore.qubit, %8: !qcore.qubit, %9: !qcore.qubit):
            %10 = plaquette.round(%7, %8, %9) {plaquette.z_observable_is_vertical = true} -> i1 {
            ^bb2(%11: !qcore.qubit, %12: !qcore.qubit, %13: !qcore.qubit):
                %14 = plaquette.plaquette<[Z0 Z1 : 2], #plaquette.synchronised_schedule<[1, none]>> on (%11, %12) using (%13) {plaquette.shape_type = #plaquette.rotated_surface_plaquette_shape<TOP>} -> i1
                plaquette.yield %14 : i1
            }
            qstruct.yield %7, %8, %9, %10 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1
        }
        qstruct.yield %3, %4, %5 : !qcore.qubit, !qcore.qubit, !qcore.qubit
    }

// CHECK-NEXT:  %p0_3, %p0_4, %p0_5 = qstruct.repeat<2> (%p0, %p0_1, %p0_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:  ^bb0(%0: !qcore.qubit, %1: !qcore.qubit, %2: !qcore.qubit):
// CHECK-NEXT:      %3, %4, %5, %6 = qstruct.circuit(%0, %1, %2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1 {
// CHECK-NEXT:      ^bb1(%7: !qcore.qubit, %8: !qcore.qubit, %9: !qcore.qubit):
// CHECK-NEXT:          %10 = plaquette.round(%7, %8, %9) {plaquette.z_observable_is_vertical = true} -> i1 {
// CHECK-NEXT:          ^bb2(%11: !qcore.qubit, %12: !qcore.qubit, %13: !qcore.qubit):
// CHECK-NEXT:              %14 = plaquette.plaquette<[Z0 Z1 : 2], #plaquette.synchronised_schedule<[1, none]>> on (%11, %12) using (%13) {plaquette.shape_type = #plaquette.rotated_surface_plaquette_shape<TOP>} -> i1
// CHECK-NEXT:              plaquette.yield %14 : i1
// CHECK-NEXT:          }
// CHECK-NEXT:          qstruct.yield %7, %8, %9, %10 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1
// CHECK-NEXT:      }
// CHECK-NEXT:      qstruct.yield %3, %4, %5 : !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:  }

}
// CHECK-NEXT:  }
