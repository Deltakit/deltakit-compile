// RUN: deltakit_compile compile-passes %s -p collapse-adjacent-alloc -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK: builtin.module {
    %q0 = qcore.alloc_qubit<coords = [(4.0, 0.0)], ids = [0]> -> !qcore.qubit
    %q1 = qcore.alloc_qubit<coords = [(0.0, 0.0)], ids = [3]> -> !qcore.qubit
    %q2, %q3 = qcore.alloc_qubit<coords = [(1.0, 0.0), (2.0, 0.0)], ids = [1, 2]> -> !qcore.qubit, !qcore.qubit
    %qreg1 = qcore.alloc_qubit<coords = [(0.0, 1.0), (0.0, 2.0), (0.0, 3.0)], ids = [4, 5, 6]> -> !qcore.qubit_reg<3>
// CHECK-NEXT: %q0, %q1, %q2, %q3, %qreg1 = qcore.alloc_qubit<coords = [(4.0, 0.0), (0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (0.0, 1.0), (0.0, 2.0), (0.0, 3.0)], ids = [0, 3, 1, 2, 4, 5, 6]> -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit_reg<3>
    qstruct.output(:)
// CHECK-NEXT: qstruct.output(:)
    %qreg2 = qcore.alloc_qubit<coords = [(2.1, 1.1)]> -> !qcore.qubit_reg<1>
    %q4 = qcore.alloc_qubit<ids = [0]> -> !qcore.qubit
    %qreg3 = qcore.alloc_qubit<coords = [(0.1, 1.1), (0.1, 2.1)]> -> !qcore.qubit_reg<2>
    %q5 = qcore.alloc_qubit<ids = [2]> -> !qcore.qubit
    %q6, %q7, %q8 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT: %qreg2, %qreg3 = qcore.alloc_qubit<coords = [(2.1, 1.1), (0.1, 1.1), (0.1, 2.1)]> -> !qcore.qubit_reg<1>, !qcore.qubit_reg<2>
// CHECK-NEXT: %q4, %q5 = qcore.alloc_qubit<ids = [0, 2]> -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT: %q6, %q7, %q8 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
    qstruct.output(:)
// CHECK-NEXT: qstruct.output(:)
    %0 = qcore.alloc_qubit<coords = [(4.0, 0.0)], ids = [0]> -> !qcore.qubit
    %1 = qcore.alloc_qubit<coords = [(0.0, 0.0)], ids = [1]> -> !qcore.qubit
    %2 = qcore.alloc_qubit<coords = [(1.0, 0.0)], ids = [2]> -> !qcore.qubit
    %3 = qcore.alloc_qubit<coords = [(2.0, 0.0)], ids = [3]> -> !qcore.qubit
    %4 = qcore.alloc_qubit<coords = [(3.0, 0.0)], ids = [4]> -> !qcore.qubit
// CHECK-NEXT: %0, %1, %2, %3, %4 = qcore.alloc_qubit<coords = [(4.0, 0.0), (0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)], ids = [0, 1, 2, 3, 4]> -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
    qstruct.output(:)
// CHECK-NEXT: qstruct.output(:)
    %q9, %qreg4 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit_reg<42>
    %q10 = qcore.alloc_qubit<ids = [42]> -> !qcore.qubit
// CHECK-NEXT: %q10 = qcore.alloc_qubit<ids = [42]> -> !qcore.qubit
// CHECK-NEXT: %q9, %qreg4 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit_reg<42>
}
// CHECK-NEXT: }
