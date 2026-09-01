// RUN: ROUNDTRIP_MLIR

builtin.module {
// CHECK:       builtin.module {

    "test.op"() {alignment = #qstruct.align<TOP>} : () -> ()
    "test.op"() {alignment = #qstruct.align<BOTTOM>} : () -> ()
// CHECK-NEXT:    "test.op"() {alignment = #qstruct.align<TOP>} : () -> ()
// CHECK-NEXT:    "test.op"() {alignment = #qstruct.align<BOTTOM>} : () -> ()

}
// CHECK-NEXT:  }
