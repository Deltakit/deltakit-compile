// RUN: deltakit_compile compile-passes -t %s -p schedule-plaquettes -O %t && filecheck %s --input-file %t

// Check that a single plaquette is correctly scheduled.
builtin.module {
// CHECK:       builtin.module {

    %p0, %p0_1, %p0_2 = "test.op"() : () -> (!qcore.qubit, !qcore.qubit, !qcore.qubit)
    %p0_3, %p0_4, %p0_5 = qstruct.repeat<2> (%p0, %p0_1, %p0_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
        ^bb0(%0: !qcore.qubit, %1: !qcore.qubit, %2: !qcore.qubit):
        %3, %4, %5, %6 = qstruct.circuit(%0, %1, %2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1 {
            ^bb1(%7: !qcore.qubit, %8: !qcore.qubit, %9: !qcore.qubit):
            %10 = plaquette.round(%7, %8, %9) {plaquette.z_observable_is_vertical = true} -> i1 {
                ^bb2(%11: !qcore.qubit, %12: !qcore.qubit, %13: !qcore.qubit):
                %14 = plaquette.plaquette<[Z0 Z1 : 2]> on (%11, %12) using (%13) {plaquette.shape_type = #plaquette.rotated_surface_plaquette_shape<TOP>} -> i1
                plaquette.yield %14 : i1
            }
            qstruct.yield %7, %8, %9, %10 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1
        }
        qstruct.yield %3, %4, %5 : !qcore.qubit, !qcore.qubit, !qcore.qubit
    }

// CHECK-NEXT:      %p0, %p0_1, %p0_2 = "test.op"() : () -> (!qcore.qubit, !qcore.qubit, !qcore.qubit)
// CHECK-NEXT:      %p0_3, %p0_4, %p0_5 = qstruct.repeat<2> (%p0, %p0_1, %p0_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:          ^bb0(%0: !qcore.qubit, %1: !qcore.qubit, %2: !qcore.qubit):
// CHECK-NEXT:          %3, %4, %5, %6 = qstruct.circuit(%0, %1, %2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1 {
// CHECK-NEXT:              ^bb1(%7: !qcore.qubit, %8: !qcore.qubit, %9: !qcore.qubit):
// CHECK-NEXT:              %10 = plaquette.round(%7, %8, %9) {plaquette.z_observable_is_vertical = true} -> i1 {
// CHECK-NEXT:                  ^bb2(%11: !qcore.qubit, %12: !qcore.qubit, %13: !qcore.qubit):
// CHECK-NEXT:                  %14 = plaquette.plaquette<[Z0 Z1 : 2], #plaquette.synchronised_schedule<[1, 3]>> on (%11, %12) using (%13) {plaquette.shape_type = #plaquette.rotated_surface_plaquette_shape<TOP>} -> i1
// CHECK-NEXT:                  plaquette.yield %14 : i1
// CHECK-NEXT:              }
// CHECK-NEXT:              qstruct.yield %7, %8, %9, %10 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1
// CHECK-NEXT:          }
// CHECK-NEXT:          qstruct.yield %3, %4, %5 : !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      }

}
// CHECK-NEXT:  }

// ----
// CHECK: ----

// Check that a single plaquette with partial but valid schedule is correctly scheduled.
builtin.module {
// CHECK:       builtin.module {

    %p0, %p0_1, %p0_2 = "test.op"() : () -> (!qcore.qubit, !qcore.qubit, !qcore.qubit)
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

// CHECK-NEXT:      %p0, %p0_1, %p0_2 = "test.op"() : () -> (!qcore.qubit, !qcore.qubit, !qcore.qubit)
// CHECK-NEXT:      %p0_3, %p0_4, %p0_5 = qstruct.repeat<2> (%p0, %p0_1, %p0_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:          ^bb0(%0: !qcore.qubit, %1: !qcore.qubit, %2: !qcore.qubit):
// CHECK-NEXT:          %3, %4, %5, %6 = qstruct.circuit(%0, %1, %2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1 {
// CHECK-NEXT:              ^bb1(%7: !qcore.qubit, %8: !qcore.qubit, %9: !qcore.qubit):
// CHECK-NEXT:              %10 = plaquette.round(%7, %8, %9) {plaquette.z_observable_is_vertical = true} -> i1 {
// CHECK-NEXT:                  ^bb2(%11: !qcore.qubit, %12: !qcore.qubit, %13: !qcore.qubit):
// CHECK-NEXT:                  %14 = plaquette.plaquette<[Z0 Z1 : 2], #plaquette.synchronised_schedule<[1, 3]>> on (%11, %12) using (%13) {plaquette.shape_type = #plaquette.rotated_surface_plaquette_shape<TOP>} -> i1
// CHECK-NEXT:                  plaquette.yield %14 : i1
// CHECK-NEXT:              }
// CHECK-NEXT:              qstruct.yield %7, %8, %9, %10 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1
// CHECK-NEXT:          }
// CHECK-NEXT:          qstruct.yield %3, %4, %5 : !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      }

}
// CHECK-NEXT:  }

// ----
// CHECK: ----

// Check that unsupported plaquettes are not changed.
builtin.module {
// CHECK:       builtin.module {

    %p0, %p0_1, %p0_2 = "test.op"() : () -> (!qcore.qubit, !qcore.qubit, !qcore.qubit)
    %p0_3, %p0_4, %p0_5 = qstruct.repeat<2> (%p0, %p0_1, %p0_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
        ^bb0(%0: !qcore.qubit, %1: !qcore.qubit, %2: !qcore.qubit):
        %3, %4, %5, %6 = qstruct.circuit(%0, %1, %2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1 {
            ^bb1(%7: !qcore.qubit, %8: !qcore.qubit, %9: !qcore.qubit):
            %10 = plaquette.round(%7, %8, %9) -> i1 { // <<<< Missing the attribute here.
                ^bb2(%11: !qcore.qubit, %12: !qcore.qubit, %13: !qcore.qubit):
                %14 = plaquette.plaquette<[Z0 Z1 : 2]> on (%11, %12) using (%13) {plaquette.shape_type = #plaquette.rotated_surface_plaquette_shape<TOP>} -> i1
                plaquette.yield %14 : i1
            }
            %15 = plaquette.round(%7, %8, %9) {plaquette.z_observable_is_vertical = true} -> i1 {
                ^bb3(%16: !qcore.qubit, %17: !qcore.qubit, %18: !qcore.qubit): // vvvvvvv Missing the attribute here.
                %19 = plaquette.plaquette<[Z0 Z1 : 2]> on (%16, %17) using (%18) -> i1
                plaquette.yield %19 : i1
            }
            qstruct.yield %7, %8, %9, %10 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1
        }
        qstruct.yield %3, %4, %5 : !qcore.qubit, !qcore.qubit, !qcore.qubit
    }

// CHECK-NEXT:      %p0, %p0_1, %p0_2 = "test.op"() : () -> (!qcore.qubit, !qcore.qubit, !qcore.qubit)
// CHECK-NEXT:      %p0_3, %p0_4, %p0_5 = qstruct.repeat<2> (%p0, %p0_1, %p0_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:          ^bb0(%0: !qcore.qubit, %1: !qcore.qubit, %2: !qcore.qubit):
// CHECK-NEXT:          %3, %4, %5, %6 = qstruct.circuit(%0, %1, %2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1 {
// CHECK-NEXT:              ^bb1(%7: !qcore.qubit, %8: !qcore.qubit, %9: !qcore.qubit):
// CHECK-NEXT:              %10 = plaquette.round(%7, %8, %9) -> i1 {
// CHECK-NEXT:                  ^bb2(%11: !qcore.qubit, %12: !qcore.qubit, %13: !qcore.qubit):
// CHECK-NEXT:                  %14 = plaquette.plaquette<[Z0 Z1 : 2]> on (%11, %12) using (%13) {plaquette.shape_type = #plaquette.rotated_surface_plaquette_shape<TOP>} -> i1
// CHECK-NEXT:                  plaquette.yield %14 : i1
// CHECK-NEXT:              }
// CHECK-NEXT:              %15 = plaquette.round(%7, %8, %9) {plaquette.z_observable_is_vertical = true} -> i1 {
// CHECK-NEXT:                  ^bb3(%16: !qcore.qubit, %17: !qcore.qubit, %18: !qcore.qubit):
// CHECK-NEXT:                  %19 = plaquette.plaquette<[Z0 Z1 : 2]> on (%16, %17) using (%18) -> i1
// CHECK-NEXT:                  plaquette.yield %19 : i1
// CHECK-NEXT:              }
// CHECK-NEXT:              qstruct.yield %7, %8, %9, %10 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1
// CHECK-NEXT:          }
// CHECK-NEXT:          qstruct.yield %3, %4, %5 : !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      }

}
// CHECK-NEXT:  }

// ----
// CHECK: ----

// Test that the plaquettes in the following patch are correctly scheduled:
//
//     o-----o
//    /|     |\
//   o |     | o
//    \|     |/
//     o-----o
builtin.module {
// CHECK:       builtin.module {

    %qreg = "test.op"() : () -> !qcore.qubit_reg<7>
    %q, %q_1, %q_2, %q_3, %q_4, %q_5, %q_6 = qcore.unpack_qubit_reg(%qreg : !qcore.qubit_reg<7>)
// CHECK-NEXT:    %qreg = "test.op"() : () -> !qcore.qubit_reg<7>
// CHECK-NEXT:    %q, %q_1, %q_2, %q_3, %q_4, %q_5, %q_6 = qcore.unpack_qubit_reg(%qreg : !qcore.qubit_reg<7>)

    %q_7, %q_8, %q_9, %q_10, %q_11, %q_12, %q_13 = qstruct.repeat<4> (%q, %q_1, %q_2, %q_3, %q_4, %q_5, %q_6 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
        ^bb0(%0: !qcore.qubit, %1: !qcore.qubit, %2: !qcore.qubit, %3: !qcore.qubit, %4: !qcore.qubit, %5: !qcore.qubit, %6: !qcore.qubit):
        %7, %8, %9, %10, %11, %12, %13, %14, %15, %16 = qstruct.circuit(%0, %1, %2, %3, %4, %5, %6 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1, i1 {
            ^bb1(%17: !qcore.qubit, %18: !qcore.qubit, %19: !qcore.qubit, %20: !qcore.qubit, %21: !qcore.qubit, %22: !qcore.qubit, %23: !qcore.qubit):
            %24, %25, %26 = plaquette.round(%17, %18, %19, %20, %21, %22, %23) {plaquette.z_observable_is_vertical = true} -> i1, i1, i1 {
                ^bb2(%27: !qcore.qubit, %28: !qcore.qubit, %29: !qcore.qubit, %30: !qcore.qubit, %31: !qcore.qubit, %32: !qcore.qubit, %33: !qcore.qubit):
                %34 = plaquette.plaquette<[X0 X1 X2 X3 : 4]> on (%28, %30, %27, %29) using (%31) {plaquette.shape_type = #plaquette.rotated_surface_plaquette_shape<SQUARE>} -> i1
                plaquette.yield %34 : i1
            } {
                ^bb3(%35: !qcore.qubit, %36: !qcore.qubit, %37: !qcore.qubit, %38: !qcore.qubit, %39: !qcore.qubit, %40: !qcore.qubit, %41: !qcore.qubit):
                %42 = plaquette.plaquette<[Z0 Z1 : 2]> on (%36, %38) using (%40) {plaquette.shape_type = #plaquette.rotated_surface_plaquette_shape<LEFT>} -> i1
                plaquette.yield %42 : i1
            } {
                ^bb4(%43: !qcore.qubit, %44: !qcore.qubit, %45: !qcore.qubit, %46: !qcore.qubit, %47: !qcore.qubit, %48: !qcore.qubit, %49: !qcore.qubit):
                %50 = plaquette.plaquette<[Z0 Z1 : 2]> on (%43, %45) using (%49) {plaquette.shape_type = #plaquette.rotated_surface_plaquette_shape<RIGHT>} -> i1
                plaquette.yield %50 : i1
            }
            qstruct.yield %17, %18, %19, %20, %21, %22, %23, %24, %25, %26 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1, i1
        }
        qstruct.yield %7, %8, %9, %10, %11, %12, %13 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
    }

// CHECK-NEXT:    %q_7, %q_8, %q_9, %q_10, %q_11, %q_12, %q_13 = qstruct.repeat<4> (%q, %q_1, %q_2, %q_3, %q_4, %q_5, %q_6 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:    ^bb0(%0: !qcore.qubit, %1: !qcore.qubit, %2: !qcore.qubit, %3: !qcore.qubit, %4: !qcore.qubit, %5: !qcore.qubit, %6: !qcore.qubit):
// CHECK-NEXT:        %7, %8, %9, %10, %11, %12, %13, %14, %15, %16 = qstruct.circuit(%0, %1, %2, %3, %4, %5, %6 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1, i1 {
// CHECK-NEXT:        ^bb1(%17: !qcore.qubit, %18: !qcore.qubit, %19: !qcore.qubit, %20: !qcore.qubit, %21: !qcore.qubit, %22: !qcore.qubit, %23: !qcore.qubit):
// CHECK-NEXT:            %24, %25, %26 = plaquette.round(%17, %18, %19, %20, %21, %22, %23) {plaquette.z_observable_is_vertical = true} -> i1, i1, i1 {
// CHECK-NEXT:            ^bb2(%27: !qcore.qubit, %28: !qcore.qubit, %29: !qcore.qubit, %30: !qcore.qubit, %31: !qcore.qubit, %32: !qcore.qubit, %33: !qcore.qubit):
// CHECK-NEXT:                %34 = plaquette.plaquette<[X0 X1 X2 X3 : 4], #plaquette.synchronised_schedule<[0, 2, 1, 3]>> on (%28, %30, %27, %29) using (%31) {plaquette.shape_type = #plaquette.rotated_surface_plaquette_shape<SQUARE>} -> i1
// CHECK-NEXT:                plaquette.yield %34 : i1
// CHECK-NEXT:            } {
// CHECK-NEXT:            ^bb3(%35: !qcore.qubit, %36: !qcore.qubit, %37: !qcore.qubit, %38: !qcore.qubit, %39: !qcore.qubit, %40: !qcore.qubit, %41: !qcore.qubit):
// CHECK-NEXT:                %42 = plaquette.plaquette<[Z0 Z1 : 2], #plaquette.synchronised_schedule<[2, 3]>> on (%36, %38) using (%40) {plaquette.shape_type = #plaquette.rotated_surface_plaquette_shape<LEFT>} -> i1
// CHECK-NEXT:                plaquette.yield %42 : i1
// CHECK-NEXT:            } {
// CHECK-NEXT:            ^bb4(%43: !qcore.qubit, %44: !qcore.qubit, %45: !qcore.qubit, %46: !qcore.qubit, %47: !qcore.qubit, %48: !qcore.qubit, %49: !qcore.qubit):
// CHECK-NEXT:                %50 = plaquette.plaquette<[Z0 Z1 : 2], #plaquette.synchronised_schedule<[0, 1]>> on (%43, %45) using (%49) {plaquette.shape_type = #plaquette.rotated_surface_plaquette_shape<RIGHT>} -> i1
// CHECK-NEXT:                plaquette.yield %50 : i1
// CHECK-NEXT:            }
// CHECK-NEXT:            qstruct.yield %17, %18, %19, %20, %21, %22, %23, %24, %25, %26 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1, i1
// CHECK-NEXT:        }
// CHECK-NEXT:        qstruct.yield %7, %8, %9, %10, %11, %12, %13 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:    }

}
// CHECK-NEXT:  }
