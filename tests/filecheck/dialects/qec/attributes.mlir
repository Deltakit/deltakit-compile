// RUN: ROUNDTRIP_MLIR

builtin.module {
    %0 = "test.op"() {attr = !qec.detector_ref} : () -> !qec.detector_ref
    %1 = "test.op"() {attr = !qec.detector_ref} : () -> !qec.detector_ref
    %2 = "test.op"() {attr = !qec.observable} : () -> !qec.observable
    %3 = "test.op"() {attr = !qec.observable} : () -> !qec.observable
}

// CHECK:       builtin.module {
// CHECK-NEXT:      %0 = "test.op"() {attr = !qec.detector_ref} : () -> !qec.detector_ref
// CHECK-NEXT:      %1 = "test.op"() {attr = !qec.detector_ref} : () -> !qec.detector_ref
// CHECK-NEXT:      %2 = "test.op"() {attr = !qec.observable} : () -> !qec.observable
// CHECK-NEXT:      %3 = "test.op"() {attr = !qec.observable} : () -> !qec.observable
// CHECK-NEXT:  }
