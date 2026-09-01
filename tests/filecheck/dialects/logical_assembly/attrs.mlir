// RUN: ROUNDTRIP_MLIR

builtin.module {
    // Test OrientationAttr
    "test.op"() {attr = #log_asm.orientation<h_z>} : () -> ()
    "test.op"() {attr = #log_asm.orientation<v_z>} : () -> ()

    // Test GateTypeAttr
    "test.op"() {attr = #log_asm.gate_type<H>} : () -> ()
    "test.op"() {attr = #log_asm.gate_type<X>} : () -> ()

    // Test PlacementAttr
    "test.op"() {attr = #log_asm.placement<[10.0, 12.0],#log_asm.orientation<h_z>>} : () -> ()
    "test.op"() {attr = #log_asm.placement<[-10.0, 12.0],#log_asm.orientation<v_z>>} : () -> ()
}

// CHECK:       builtin.module {
// CHECK-NEXT:      "test.op"() {attr = #log_asm.orientation<h_z>} : () -> ()
// CHECK-NEXT:      "test.op"() {attr = #log_asm.orientation<v_z>} : () -> ()
// CHECK-NEXT:      "test.op"() {attr = #log_asm.gate_type<H>} : () -> ()
// CHECK-NEXT:      "test.op"() {attr = #log_asm.gate_type<X>} : () -> ()
// CHECK-NEXT:      "test.op"() {attr = #log_asm.placement<[10.0, 12.0], #log_asm.orientation<h_z>>} : () -> ()
// CHECK-NEXT:      "test.op"() {attr = #log_asm.placement<[-10.0, 12.0], #log_asm.orientation<v_z>>} : () -> ()
// CHECK-NEXT:  }
