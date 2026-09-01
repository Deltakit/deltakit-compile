// RUN: ROUNDTRIP_MLIR

builtin.module {
    qcore.alloc_qubit ->
    qcore.alloc_qubit ->
    qcore.alloc_qubit ->
    qcore.alloc_qubit<coords=[], ids=[]> {attr_data="blahblah"} ->
    %qr1 = qcore.alloc_qubit -> !qcore.qubit_reg<3>
    %q1 = qcore.alloc_qubit -> !qcore.qubit
    %q2, %qr2, %qr3, %q3 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit_reg<3>, !qcore.qubit_reg<20>, !qcore.qubit
    %q4, %q5, %qr4 = qcore.alloc_qubit<coords=[(0, 0), (0, 1), (1, 0.5), (0.5, 1)]> {attr_data="blahblah"} -> !qcore.qubit, !qcore.qubit, !qcore.qubit_reg<2>
    %q6, %q7 = qcore.alloc_qubit<ids=[10, 20]> -> !qcore.qubit, !qcore.qubit
    %q8, %q9 = qcore.alloc_qubit<coords=[(0, 0), (1, 1)], ids=[5, 6]> -> !qcore.qubit, !qcore.qubit
    %q10, %q11 = qcore.alloc_qubit<ids=[7, 8], coords=[(2, 2), (3, 3)]> -> !qcore.qubit, !qcore.qubit
    %q12, %q13, %q14 = qcore.alloc_qubit<coords=[(4, 2), (1, 3), (0, -6)], ids=[42, 13, -6]> -> !qcore.qubit, !qcore.qubit, !qcore.qubit
    %q15 = qcore.alloc_qubit<ids=[3]> -> !qcore.qubit
    %qr5 = qcore.pack_qubit_reg(%q1, %q2, %q3, %q4, %q5) {attr_data="stringattr?"} -> !qcore.qubit_reg<5>
    %qr6 = qcore.pack_qubit_reg(%q1, %q2, %q5) -> !qcore.qubit_reg<3>
    %qu1, %qu2, %qu3 = qcore.unpack_qubit_reg(%qr6 : !qcore.qubit_reg<3>) {blah = "bobbins"}
    %qu4, %qu5 = qcore.unpack_qubit_reg(%qr4 : !qcore.qubit_reg<2>)
    %qcr1 = qcore.concatenate(%qr3, %qr4 : !qcore.qubit_reg<20>, !qcore.qubit_reg<2>) {pasta = "penne"} -> !qcore.qubit_reg<22>
    %qcr2 = qcore.concatenate(%qr2, %qr5, %qr6 : !qcore.qubit_reg<3>, !qcore.qubit_reg<5>, !qcore.qubit_reg<3>) -> !qcore.qubit_reg<11>
    %qsr1, %qsr2, %qsr3, %qsr4 = qcore.split(%qcr2 : !qcore.qubit_reg<11>) -> !qcore.qubit_reg<3>, !qcore.qubit_reg<3>, !qcore.qubit_reg<3>, !qcore.qubit_reg<2>
    %qsr5, %qsr6, %qsr7 = qcore.split(%qsr1 : !qcore.qubit_reg<3>) {pasta = "ravioli"} -> !qcore.qubit_reg<1>, !qcore.qubit_reg<1>, !qcore.qubit_reg<1>
}

// CHECK:       builtin.module {
// CHECK-NEXT:      qcore.alloc_qubit ->
// CHECK-NEXT:      qcore.alloc_qubit ->
// CHECK-NEXT:      qcore.alloc_qubit ->
// CHECK-NEXT:      qcore.alloc_qubit<coords = [], ids = []> {attr_data = "blahblah"} ->
// CHECK-NEXT:      %qr1 = qcore.alloc_qubit -> !qcore.qubit_reg<3>
// CHECK-NEXT:      %q1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:      %q2, %qr2, %qr3, %q3 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit_reg<3>, !qcore.qubit_reg<20>, !qcore.qubit
// CHECK-NEXT:      %q4, %q5, %qr4 = qcore.alloc_qubit<coords = [(0.0, 0.0), (0.0, 1.0), (1.0, 0.5), (0.5, 1.0)]> {attr_data = "blahblah"} -> !qcore.qubit, !qcore.qubit, !qcore.qubit_reg<2>
// CHECK-NEXT:      %q6, %q7 = qcore.alloc_qubit<ids = [10, 20]> -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      %q8, %q9 = qcore.alloc_qubit<coords = [(0.0, 0.0), (1.0, 1.0)], ids = [5, 6]> -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      %q10, %q11 = qcore.alloc_qubit<coords = [(2.0, 2.0), (3.0, 3.0)], ids = [7, 8]> -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      %q12, %q13, %q14 = qcore.alloc_qubit<coords = [(4.0, 2.0), (1.0, 3.0), (0.0, -6.0)], ids = [42, 13, -6]> -> !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      %q15 = qcore.alloc_qubit<ids = [3]> -> !qcore.qubit
// CHECK-NEXT:      %qr5 = qcore.pack_qubit_reg(%q1, %q2, %q3, %q4, %q5) {attr_data = "stringattr?"} -> !qcore.qubit_reg<5>
// CHECK-NEXT:      %qr6 = qcore.pack_qubit_reg(%q1, %q2, %q5) -> !qcore.qubit_reg<3>
// CHECK-NEXT:      %qu1, %qu2, %qu3 = qcore.unpack_qubit_reg(%qr6 : !qcore.qubit_reg<3>) {blah = "bobbins"}
// CHECK-NEXT:      %qu4, %qu5 = qcore.unpack_qubit_reg(%qr4 : !qcore.qubit_reg<2>)
// CHECK-NEXT:      %qcr1 = qcore.concatenate(%qr3, %qr4 : !qcore.qubit_reg<20>, !qcore.qubit_reg<2>) {pasta = "penne"} -> !qcore.qubit_reg<22>
// CHECK-NEXT:      %qcr2 = qcore.concatenate(%qr2, %qr5, %qr6 : !qcore.qubit_reg<3>, !qcore.qubit_reg<5>, !qcore.qubit_reg<3>) -> !qcore.qubit_reg<11>
// CHECK-NEXT:      %qsr1, %qsr2, %qsr3, %qsr4 = qcore.split(%qcr2 : !qcore.qubit_reg<11>) -> !qcore.qubit_reg<3>, !qcore.qubit_reg<3>, !qcore.qubit_reg<3>, !qcore.qubit_reg<2>
// CHECK-NEXT:      %qsr5, %qsr6, %qsr7 = qcore.split(%qsr1 : !qcore.qubit_reg<3>) {pasta = "ravioli"} -> !qcore.qubit_reg<1>, !qcore.qubit_reg<1>, !qcore.qubit_reg<1>
// CHECK-NEXT:  }
