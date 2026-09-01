// RUN: ROUNDTRIP_MLIR

builtin.module {
// CHECK:       builtin.module {

    "test.op"() {meas_stab = #plaquette.synchronised_schedule<[0]>} : () -> ()
    "test.op"() {meas_stab = #plaquette.synchronised_schedule<[0, 1]>} : () -> ()
    "test.op"() {meas_stab = #plaquette.synchronised_schedule<[0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 938457690348567]>} : () -> ()
    "test.op"() {meas_stab = #plaquette.synchronised_schedule<[none, 1, none, 0]>} : () -> ()
// CHECK-NEXT:  "test.op"() {meas_stab = #plaquette.synchronised_schedule<[0]>} : () -> ()
// CHECK-NEXT:  "test.op"() {meas_stab = #plaquette.synchronised_schedule<[0, 1]>} : () -> ()
// CHECK-NEXT:  "test.op"() {meas_stab = #plaquette.synchronised_schedule<[0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 938457690348567]>} : () -> ()
// CHECK-NEXT:  "test.op"() {meas_stab = #plaquette.synchronised_schedule<[none, 1, none, 0]>} : () -> ()

    "test.op"() {shape = #plaquette.rotated_surface_plaquette_shape<SQUARE>} : () -> ()
    "test.op"() {shape = #plaquette.rotated_surface_plaquette_shape<TOP>} : () -> ()
    "test.op"() {shape = #plaquette.rotated_surface_plaquette_shape<BOTTOM>} : () -> ()
    "test.op"() {shape = #plaquette.rotated_surface_plaquette_shape<LEFT>} : () -> ()
    "test.op"() {shape = #plaquette.rotated_surface_plaquette_shape<RIGHT>} : () -> ()
// CHECK-NEXT:  "test.op"() {shape = #plaquette.rotated_surface_plaquette_shape<SQUARE>} : () -> ()
// CHECK-NEXT:  "test.op"() {shape = #plaquette.rotated_surface_plaquette_shape<TOP>} : () -> ()
// CHECK-NEXT:  "test.op"() {shape = #plaquette.rotated_surface_plaquette_shape<BOTTOM>} : () -> ()
// CHECK-NEXT:  "test.op"() {shape = #plaquette.rotated_surface_plaquette_shape<LEFT>} : () -> ()
// CHECK-NEXT:  "test.op"() {shape = #plaquette.rotated_surface_plaquette_shape<RIGHT>} : () -> ()


}
// CHECK-NEXT:  }
