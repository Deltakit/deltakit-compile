// RUN: deltakit_compile compile-passes %s -t -p canonicalize -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK:       builtin.module {
    %qr1 = qcore.alloc_qubit -> !qcore.qubit_reg<10>
// CHECK-NEXT:      %qr1 = qcore.alloc_qubit -> !qcore.qubit_reg<10>

    %qr2 = qcore.concatenate(%qr1 : !qcore.qubit_reg<10>) -> !qcore.qubit_reg<10>
    %qr3 = qcore.split(%qr2 : !qcore.qubit_reg<10>) -> !qcore.qubit_reg<10>
    %qr4a, %qr4b = qcore.split(%qr3 : !qcore.qubit_reg<10>) -> !qcore.qubit_reg<2>, !qcore.qubit_reg<8>
    %qr5a = qcore.concatenate(%qr4a : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2>
    %qr5b = qcore.concatenate(%qr4b : !qcore.qubit_reg<8>) -> !qcore.qubit_reg<8>
    %qr6 = qcore.concatenate(%qr5a, %qr5b : !qcore.qubit_reg<2>, !qcore.qubit_reg<8>) -> !qcore.qubit_reg<10>
// All these should be removed.

// Now swap the order of the parts of the qubit reg, which cannot be removed.
    %qr7a, %qr7b = qcore.split(%qr6 : !qcore.qubit_reg<10>) -> !qcore.qubit_reg<5>, !qcore.qubit_reg<5>
    %qr8 = qcore.concatenate(%qr7b, %qr7a : !qcore.qubit_reg<5>, !qcore.qubit_reg<5>) -> !qcore.qubit_reg<10>
// CHECK-NEXT:      %qr7a, %qr7b = qcore.split(%qr1 : !qcore.qubit_reg<10>) -> !qcore.qubit_reg<5>, !qcore.qubit_reg<5>
// CHECK-NEXT:      %qr8 = qcore.concatenate(%qr7b, %qr7a : !qcore.qubit_reg<5>, !qcore.qubit_reg<5>) -> !qcore.qubit_reg<10>

// Check the split concatenate pair the other way around now:
    %qr9a, %qr9b, %qr9c = qcore.split(%qr8 : !qcore.qubit_reg<10>) -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2>, !qcore.qubit_reg<6>
    %qr10ab = qcore.concatenate(%qr9a, %qr9b : !qcore.qubit_reg<2>, !qcore.qubit_reg<2>) -> !qcore.qubit_reg<4>
    %qr11a, %qr11b = qcore.split(%qr10ab : !qcore.qubit_reg<4>) -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2>
    %qr11 = qcore.concatenate(%qr11a, %qr11b, %qr9c: !qcore.qubit_reg<2>, !qcore.qubit_reg<2>, !qcore.qubit_reg<6>) -> !qcore.qubit_reg<10>

// Force the use of the qubits to stop everything getting wiped out
    "test.op"(%qr11) : (!qcore.qubit_reg<10>) -> ()
// CHECK-NEXT:      "test.op"(%qr8) : (!qcore.qubit_reg<10>) -> ()
}
// CHECK-NEXT:  }

// ----
// CHECK: ----

builtin.module {
// CHECK-NEXT:  builtin.module {
  %qr = qcore.alloc_qubit -> !qcore.qubit_reg<4>
  %qr2_0, %qr2_1 = qcore.split(%qr : !qcore.qubit_reg<4>) -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2>
// CHECK-NEXT:      %qr = qcore.alloc_qubit -> !qcore.qubit_reg<4>
// CHECK-NEXT:      %qr2, %qr2_1 = qcore.split(%qr : !qcore.qubit_reg<4>) -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2>

  // Register created by split, shouldn't be removed
  %q1, %q2 = qcore.unpack_qubit_reg(%qr2_0 : !qcore.qubit_reg<2>)
  %q3, %q4 = qcore.unpack_qubit_reg(%qr2_1 : !qcore.qubit_reg<2>)
// CHECK-NEXT:      %q1, %q2 = qcore.unpack_qubit_reg(%qr2 : !qcore.qubit_reg<2>)
// CHECK-NEXT:      %q3, %q4 = qcore.unpack_qubit_reg(%qr2_1 : !qcore.qubit_reg<2>)

  // Should get DCEd after unpack is removed
  %qr2_2 = qcore.pack_qubit_reg(%q1, %q3) -> !qcore.qubit_reg<2>
  // Should be removed by canonicalisation
  %qq1, %qq2 = qcore.unpack_qubit_reg(%qr2_2 : !qcore.qubit_reg<2>)

  "test.op"(%qq1, %qq2) : (!qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:      "test.op"(%q1, %q3) : (!qcore.qubit, !qcore.qubit) -> ()
}
// CHECK-NEXT:  }
