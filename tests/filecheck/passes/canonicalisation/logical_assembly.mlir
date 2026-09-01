// RUN: deltakit_compile compile-passes %s -t -p canonicalize -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK:       builtin.module {
    %qr1 = qcore.alloc_qubit -> !qcore.qubit_reg<17>
// CHECK-NEXT:  %qr1 = qcore.alloc_qubit -> !qcore.qubit_reg<17>

    // Identity cast should be removed
    %qr2 = log_asm.cast (%qr1 : !qcore.qubit_reg<17>) -> !qcore.qubit_reg<17>

    // Cast and casting back should be removed too
    %p2 = log_asm.cast (%qr1 : !qcore.qubit_reg<17>) -> !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>
    %qr3 = log_asm.cast (%p2 : !log_asm.patch.rot_planar<size=(3, 3), location=(0.0, 0.0), orient=v_z>) -> !qcore.qubit_reg<17>

    // Using the outputs to avoid DCE
    "test.op"(%qr2) : (!qcore.qubit_reg<17>) -> ()
    "test.op"(%qr3) : (!qcore.qubit_reg<17>) -> ()
// CHECK-NEXT:  "test.op"(%qr1) : (!qcore.qubit_reg<17>) -> ()
// CHECK-NEXT:  "test.op"(%qr1) : (!qcore.qubit_reg<17>) -> ()

}
// CHECK-NEXT:  }
