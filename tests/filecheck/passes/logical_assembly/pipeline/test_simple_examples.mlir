// RUN: deltakit_compile compile-passes %s -p logical-assembler-core-pipeline --pass-args '{"verify_between_passes": true}' -O %t && filecheck %s --input-file %t
// XFAIL: *
// This is xfailed because the main example doesn't work with generate flows due to incorrect handling of qubit reg packing/unpacking

builtin.module {
}
// CHECK:       builtin.module {
// CHECK-NEXT:  }

// ----
// CHECK: ----

builtin.module {
    %0 = qcore.alloc_qubit -> !qcore.qubit_reg<4>

    %1, %2, %3, %4 = qcore.unpack_qubit_reg(%0 : !qcore.qubit_reg<4>)
    %5 = qcore.pack_qubit_reg(%1, %2) -> !qcore.qubit_reg<2>

    %b, %qreg = qstruct.circuit(%5 : !qcore.qubit_reg<2>) -> i1, !qcore.qubit_reg<2> {
    ^bb0(%qreg_1: !qcore.qubit_reg<2>):
        %6, %7 = qcore.unpack_qubit_reg(%qreg_1 : !qcore.qubit_reg<2>)
        qref.gate<#qcore.gate.x> (%6, %7)
        %b_1 = qref.measure<Z> (%6) -> i1
        qstruct.yield %b_1, %qreg_1 : i1, !qcore.qubit_reg<2>
    }

    %6 = qcore.pack_qubit_reg(%3, %4) -> !qcore.qubit_reg<2>

    %b_1, %qreg_1 = qstruct.circuit(%6 : !qcore.qubit_reg<2>) -> i1, !qcore.qubit_reg<2> {
    ^bb0(%qreg_2: !qcore.qubit_reg<2>):
        %7, %8 = qcore.unpack_qubit_reg(%qreg_2 : !qcore.qubit_reg<2>)
        qref.gate<#qcore.gate.x> (%7, %8)
        %b_2 = qref.measure<Z> (%7) -> i1
        qstruct.yield %b_2, %qreg_2 : i1, !qcore.qubit_reg<2>
    }

    qstruct.output(%b, %b_1 : i1, i1)
}
