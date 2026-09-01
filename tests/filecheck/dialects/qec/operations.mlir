// RUN: ROUNDTRIP_MLIR

builtin.module {
    %0 = qcore.alloc_qubit<> -> !qcore.qubit
    %q_after, %o3_after = qstruct.circuit(%0 : !qcore.qubit) -> !qcore.qubit, !qec.observable {
    ^bb0(%q0: !qcore.qubit):
        %1 = qref.measure<Z>(%q0) -> i1
        qec.measurement_round(%1 : i1)
        %2 = qref.measure<Z> (%q0) -> i1
        qec.measurement_round(%1, %2 : i1, i1)
        %d0 = qec.detector(%1, %2) {attr_name = "nothing"}
        %d1 = qec.detector<[0.0, 1.0, 1.002, 2.3]> (%1, %2)
        qec.detector_round(%d0, %d1) {name = "Lau"}
        qec.detector_round(%d0)
        %o0 = qec.dec_observable -> !qec.observable
        %o1 = qec.dec_observable {name="Harry"} -> !qec.observable
        %o2 = qec.observable_include (%o0) using (%1, %2) -> !qec.observable
        %o3 = qec.observable_include (%o1) using (%2) {name = "Dick"} -> !qec.observable
        %unc_o2 = qec.get_uncorrected(%o2 : !qec.observable) {name = "Tom"} -> i1
        %c_o2 = qec.get_correction(%o2 : !qec.observable) {name = "Tom"} -> i1
        %ced_o2 = qec.get_corrected(%o2 : !qec.observable) {name = "Tom"} -> i1
        %ready_o2 = qec.is_correction_ready(%o2 : !qec.observable) {name = "Maverick"} -> i1
        %so0 = sobs.dec_observable(%q0) -> !sobs.observable
        %unc_so1 = qec.get_uncorrected(%so0 : !sobs.observable) {name = "Tim"} -> i1
        %c_so1 = qec.get_correction(%so0 : !sobs.observable) {name = "Tam"} -> i1
        %ced_so1 = qec.get_corrected(%so0 : !sobs.observable) {name = "Tum"} -> i1
        %ready_so1 = qec.is_correction_ready(%so0 : !sobs.observable) {name = "Maverock"} -> i1

        qstruct.yield %q0, %o3: !qcore.qubit, !qec.observable
    }
    %unc_o3 = qec.get_uncorrected(%o3_after : !qec.observable) -> i1
    %c_o3 = qec.get_correction(%o3_after : !qec.observable) -> i1
    %ced_o3 = qec.get_corrected(%o3_after : !qec.observable) -> i1
    %ready_o3 = qec.is_correction_ready(%o3_after : !qec.observable) -> i1
}


// CHECK:           %1 = qref.measure<Z> (%q0) -> i1
// CHECK-NEXT:      qec.measurement_round(%1 : i1)
// CHECK-NEXT:      %2 = qref.measure<Z> (%q0) -> i1
// CHECK-NEXT:      qec.measurement_round(%1, %2 : i1, i1)
// CHECK-NEXT:      %d0 = qec.detector(%1, %2) {attr_name = "nothing"}
// CHECK-NEXT:      %d1 = qec.detector<[0.0, 1.0, 1.002, 2.3]> (%1, %2)
// CHECK-NEXT:      qec.detector_round(%d0, %d1) {name = "Lau"}
// CHECK-NEXT:      qec.detector_round(%d0)
// CHECK-NEXT:      %o0 = qec.dec_observable -> !qec.observable
// CHECK-NEXT:      %o1 = qec.dec_observable {name = "Harry"} -> !qec.observable
// CHECK-NEXT:      %o2 = qec.observable_include(%o0) using (%1, %2) -> !qec.observable
// CHECK-NEXT:      %o3 = qec.observable_include(%o1) using (%2) {name = "Dick"} -> !qec.observable
// CHECK-NEXT:      %unc_o2 = qec.get_uncorrected(%o2 : !qec.observable) {name = "Tom"} -> i1
// CHECK-NEXT:      %c_o2 = qec.get_correction(%o2 : !qec.observable) {name = "Tom"} -> i1
// CHECK-NEXT:      %ced_o2 = qec.get_corrected(%o2 : !qec.observable) {name = "Tom"} -> i1
// CHECK-NEXT:      %ready_o2 = qec.is_correction_ready(%o2 : !qec.observable) {name = "Maverick"} -> i1
// CHECK-NEXT:      %so0 = sobs.dec_observable(%q0) -> !sobs.observable
// CHECK-NEXT:      %unc_so1 = qec.get_uncorrected(%so0 : !sobs.observable) {name = "Tim"} -> i1
// CHECK-NEXT:      %c_so1 = qec.get_correction(%so0 : !sobs.observable) {name = "Tam"} -> i1
// CHECK-NEXT:      %ced_so1 = qec.get_corrected(%so0 : !sobs.observable) {name = "Tum"} -> i1
// CHECK-NEXT:      %ready_so1 = qec.is_correction_ready(%so0 : !sobs.observable) {name = "Maverock"} -> i1

// CHECK:       %unc_o3 = qec.get_uncorrected(%o3_after : !qec.observable) -> i1
// CHECK-NEXT:  %c_o3 = qec.get_correction(%o3_after : !qec.observable) -> i1
// CHECK-NEXT:  %ced_o3 = qec.get_corrected(%o3_after : !qec.observable) -> i1
// CHECK-NEXT:  %ready_o3 = qec.is_correction_ready(%o3_after : !qec.observable) -> i1
