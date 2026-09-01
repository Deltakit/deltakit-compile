// RUN: ROUNDTRIP_MLIR

builtin.module {
    %0 = "test.op"() {attr = !sobs.unplaced_observable} : () -> !sobs.unplaced_observable
    %1 = "test.op"() {attr = !sobs.unplaced_observable} : () -> !sobs.unplaced_observable
    %2 = "test.op"() {attr = !sobs.observable} : () -> !sobs.observable
    %3 = "test.op"() {attr = !sobs.observable} : () -> !sobs.observable
}

// CHECK:       builtin.module {
// CHECK-NEXT:      %0 = "test.op"() {attr = !sobs.unplaced_observable} : () -> !sobs.unplaced_observable
// CHECK-NEXT:      %1 = "test.op"() {attr = !sobs.unplaced_observable} : () -> !sobs.unplaced_observable
// CHECK-NEXT:      %2 = "test.op"() {attr = !sobs.observable} : () -> !sobs.observable
// CHECK-NEXT:      %3 = "test.op"() {attr = !sobs.observable} : () -> !sobs.observable
// CHECK-NEXT:  }
