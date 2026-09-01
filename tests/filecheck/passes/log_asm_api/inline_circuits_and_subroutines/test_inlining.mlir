// RUN: deltakit_compile compile-passes -t %s -p inline-circuits-and-subroutines -O %t && filecheck %s --input-file %t

builtin.module {
    // CHECK:       builtin.module {

    // Circuits represented as a callable circuit function
    log_asm_api.circuit_dec @circuit0(%qreg : tensor<?x!qcore.qubit>)
                                    -> tensor<?x!qcore.qubit> {

        %c0 = arith.constant 0 : index
        %q0 = tensor.extract %qreg[%c0] : tensor<?x!qcore.qubit>
        %m0 = qref.measure<Z>(%q0) -> i1

        log_asm_api.return %qreg : tensor<?x!qcore.qubit>
    }
// CHECK-NOT: log_asm_api.circuit_dec

    // Subroutines represented as standard MLIR functions
    func.func @subroutine0(%p : !log_asm.patch.rot_planar<size=(5, 5)>)
                            -> !log_asm.patch.rot_planar<size=(5, 5)> {
        %p_1 = log_asm.transversal<X>(%p : !log_asm.patch.rot_planar<size=(5, 5)>) -> !log_asm.patch.rot_planar<size=(5, 5)>
        func.return %p_1 : !log_asm.patch.rot_planar<size=(5, 5)>
    }
// CHECK-NOT: func.func

    %p0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5, 5)>
// CHECK-NEXT:    %p0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5, 5)>

    // Circuit call
    %p0_1 = log_asm_api.cast(%p0 : !log_asm.patch.rot_planar<size=(5, 5)>) -> tensor<?x!qcore.qubit>
// CHECK-NEXT:    %p0_1 = log_asm_api.cast(%p0 : !log_asm.patch.rot_planar<size=(5, 5)>) -> tensor<?x!qcore.qubit>

    %p0_2 = log_asm_api.call @circuit0(%p0_1) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
// CHECK-NEXT:    %p0_2 = qstruct.circuit(%p0_1 : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
// CHECK-NEXT:    ^bb0(%qreg: tensor<?x!qcore.qubit>):
// CHECK-NEXT:      %c0 = arith.constant 0 : index
// CHECK-NEXT:      %q0 = tensor.extract %qreg[%c0] : tensor<?x!qcore.qubit>
// CHECK-NEXT:      %m0 = qref.measure<Z> (%q0) -> i1
// CHECK-NEXT:      qstruct.yield %qreg : tensor<?x!qcore.qubit>
// CHECK-NEXT:    }

    %p0_3 = log_asm_api.cast(%p0_2 : tensor<?x!qcore.qubit>) -> !log_asm.patch.rot_planar<size=(5, 5)>
// CHECK-NEXT:    %p0_3 = log_asm_api.cast(%p0_2 : tensor<?x!qcore.qubit>) -> !log_asm.patch.rot_planar<size=(5, 5)>

    // Subroutine call
    %p0_4 = func.call @subroutine0(%p0_3) : (!log_asm.patch.rot_planar<size=(5, 5)>) -> !log_asm.patch.rot_planar<size=(5, 5)>
// CHECK-NEXT:    %p = log_asm.transversal<X> (%p0_3 : !log_asm.patch.rot_planar<size=(5, 5)>) -> !log_asm.patch.rot_planar<size=(5, 5)>

}
// CHECK-NEXT:  }


// ----
// CHECK-NEXT: ----

// Subroutine calling a circuit calling another circuit.
builtin.module {
    // CHECK:       builtin.module {

    // Circuits represented as a callable circuit functions
    log_asm_api.circuit_dec @circuit0(%qreg : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
        %c0 = arith.constant 0 : index
        %q0 = tensor.extract %qreg[%c0] : tensor<?x!qcore.qubit>
        %m0 = qref.measure<Z>(%q0) -> i1
        %qreg1 = log_asm_api.call @circuit1(%qreg) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
        log_asm_api.return %qreg1 : tensor<?x!qcore.qubit>
    }
// CHECK-NOT: log_asm_api.circuit_dec

    log_asm_api.circuit_dec @circuit1(%qreg : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
        %c0 = arith.constant 1 : index
        %q0 = tensor.extract %qreg[%c0] : tensor<?x!qcore.qubit>
        %m0 = qref.measure<X>(%q0) -> i1
        log_asm_api.return %qreg : tensor<?x!qcore.qubit>
    }
// CHECK-NOT: log_asm_api.circuit_dec

    // Subroutines represented as standard MLIR functions
    func.func @subroutine0(%p : !log_asm.patch.rot_planar<size=(5, 5)>) -> !log_asm.patch.rot_planar<size=(5, 5)> {
        %p0_1 = log_asm_api.cast(%p : !log_asm.patch.rot_planar<size=(5, 5)>) -> tensor<?x!qcore.qubit>
        %p0_2 = log_asm_api.call @circuit0(%p0_1) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
        %p0_3 = log_asm_api.cast(%p0_2 : tensor<?x!qcore.qubit>) -> !log_asm.patch.rot_planar<size=(5, 5)>
        func.return %p0_3 : !log_asm.patch.rot_planar<size=(5, 5)>
    }
// CHECK-NOT: func.func

    %p0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5, 5)>
// CHECK-NEXT:    %p0 = log_asm.patch_dec -> !log_asm.patch.rot_planar<size=(5, 5)>

    // Circuit call
    %p0_1 = log_asm_api.cast(%p0 : !log_asm.patch.rot_planar<size=(5, 5)>) -> tensor<?x!qcore.qubit>
// CHECK-NEXT:    %p0_1 = log_asm_api.cast(%p0 : !log_asm.patch.rot_planar<size=(5, 5)>) -> tensor<?x!qcore.qubit>

    %p0_2 = log_asm_api.call @circuit0(%p0_1) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
// CHECK-NEXT:    %p0_2 = qstruct.circuit(%p0_1 : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
// CHECK-NEXT:    ^bb0(%qreg: tensor<?x!qcore.qubit>):
// CHECK-NEXT:      %c0 = arith.constant 0 : index
// CHECK-NEXT:      %q0 = tensor.extract %qreg[%c0] : tensor<?x!qcore.qubit>
// CHECK-NEXT:      %m0 = qref.measure<Z> (%q0) -> i1
// CHECK-NEXT:      %c0_1 = arith.constant 1 : index
// CHECK-NEXT:      %q0_1 = tensor.extract %qreg[%c0_1] : tensor<?x!qcore.qubit>
// CHECK-NEXT:      %m0_1 = qref.measure<X> (%q0_1) -> i1
// CHECK-NEXT:      qstruct.yield %qreg : tensor<?x!qcore.qubit>
// CHECK-NEXT:    }

    %p0_3 = log_asm_api.cast(%p0_2 : tensor<?x!qcore.qubit>) -> !log_asm.patch.rot_planar<size=(5, 5)>
// CHECK-NEXT:    %p0_3 = log_asm_api.cast(%p0_2 : tensor<?x!qcore.qubit>) -> !log_asm.patch.rot_planar<size=(5, 5)>

    // Subroutine call
    %p0_4 = func.call @subroutine0(%p0_3) : (!log_asm.patch.rot_planar<size=(5, 5)>) -> !log_asm.patch.rot_planar<size=(5, 5)>
// CHECK-NEXT:    %p0_4 = log_asm_api.cast(%p0_3 : !log_asm.patch.rot_planar<size=(5, 5)>) -> tensor<?x!qcore.qubit>
// CHECK-NEXT:    %p0_5 = qstruct.circuit(%p0_4 : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
// CHECK-NEXT:    ^bb0(%qreg: tensor<?x!qcore.qubit>):
// CHECK-NEXT:      %c0 = arith.constant 0 : index
// CHECK-NEXT:      %q0 = tensor.extract %qreg[%c0] : tensor<?x!qcore.qubit>
// CHECK-NEXT:      %m0 = qref.measure<Z> (%q0) -> i1
// CHECK-NEXT:      %c0_1 = arith.constant 1 : index
// CHECK-NEXT:      %q0_1 = tensor.extract %qreg[%c0_1] : tensor<?x!qcore.qubit>
// CHECK-NEXT:      %m0_1 = qref.measure<X> (%q0_1) -> i1
// CHECK-NEXT:      qstruct.yield %qreg : tensor<?x!qcore.qubit>
// CHECK-NEXT:    }
}
// CHECK-NEXT:  }


// ----
// CHECK-NEXT: ----

// Used recursive circuit calls are untouched. Unused Recursive calls get removed.
builtin.module {
// CHECK:       builtin.module {

    log_asm_api.circuit_dec @circuitA(%qreg : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
        "test.op"() {circuit = "A"} : () -> ()
        %qreg1 = log_asm_api.call @circuitB(%qreg) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
        log_asm_api.return %qreg : tensor<?x!qcore.qubit>
    }
    log_asm_api.circuit_dec @circuitB(%qreg : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
        "test.op"() {circuit = "B"} : () -> ()
        %qreg1 = log_asm_api.call @circuitA(%qreg) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
        log_asm_api.return %qreg : tensor<?x!qcore.qubit>
    }
    log_asm_api.circuit_dec @circuitC(%qreg : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
        "test.op"() {circuit = "C"} : () -> ()
        %qreg1 = log_asm_api.call @circuitB(%qreg) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
        log_asm_api.return %qreg : tensor<?x!qcore.qubit>
    }
    // CHECK: @circuitA
    // CHECK: @circuitB
    // CHECK: @circuitC

    log_asm_api.circuit_dec @circuitX(%qreg : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
        "test.op"() {circuit = "X"} : () -> ()
        %qreg1 = log_asm_api.call @circuitY(%qreg) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
        log_asm_api.return %qreg : tensor<?x!qcore.qubit>
    }
    log_asm_api.circuit_dec @circuitY(%qreg : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
        "test.op"() {circuit = "Y"} : () -> ()
        %qreg1 = log_asm_api.call @circuitZ(%qreg) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
        log_asm_api.return %qreg : tensor<?x!qcore.qubit>
    }
    log_asm_api.circuit_dec @circuitZ(%qreg : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
        "test.op"() {circuit = "Z"} : () -> ()
        %qreg1 = log_asm_api.call @circuitX(%qreg) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
        log_asm_api.return %qreg : tensor<?x!qcore.qubit>
    }

    // CHECK-NOT: @circuitX
    // CHECK-NOT: @circuitY
    // CHECK-NOT: @circuitZ

    %qreg = "test.op"() : () -> tensor<?x!qcore.qubit>
    %qreg1 = log_asm_api.call @circuitC(%qreg) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
    "test.op"(%qreg1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK:           %qreg = "test.op"() : () -> tensor<?x!qcore.qubit>
// CHECK-NEXT:      %qreg1 = log_asm_api.call @circuitC(%qreg) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
// CHECK-NEXT:      "test.op"(%qreg1) : (tensor<?x!qcore.qubit>) -> ()

}
// CHECK-NEXT:  }



// ----
// CHECK-NEXT: ----

// Used recursive subroutine calls are untouched. Unused Recursive calls get removed.
builtin.module {
// CHECK:       builtin.module {

    func.func @funcA(%qreg : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
        "test.op"() {func = "A"} : () -> ()
        %qreg1 = func.call @funcB(%qreg) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
        func.return %qreg : tensor<?x!qcore.qubit>
    }
    func.func @funcB(%qreg : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
        "test.op"() {func = "B"} : () -> ()
        %qreg1 = func.call @funcA(%qreg) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
        func.return %qreg : tensor<?x!qcore.qubit>
    }
    func.func @funcC(%qreg : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
        "test.op"() {func = "B"} : () -> ()
        %qreg1 = func.call @funcB(%qreg) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
        func.return %qreg : tensor<?x!qcore.qubit>
    }
    // CHECK: @funcA
    // CHECK: @funcB
    // CHECK: @funcC

    func.func @funcX(%qreg : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
        "test.op"() {func = "X"} : () -> ()
        %qreg1 = func.call @funcY(%qreg) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
        func.return %qreg : tensor<?x!qcore.qubit>
    }
    func.func @funcY(%qreg : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
        "test.op"() {func = "Y"} : () -> ()
        %qreg1 = func.call @funcZ(%qreg) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
        func.return %qreg : tensor<?x!qcore.qubit>
    }
    func.func @funcZ(%qreg : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> {
        "test.op"() {func = "Z"} : () -> ()
        %qreg1 = func.call @funcZ(%qreg) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
        func.return %qreg : tensor<?x!qcore.qubit>
    }

    // CHECK-NOT: @funcX
    // CHECK-NOT: @funcY
    // CHECK-NOT: @funcZ

    %qreg = "test.op"() : () -> tensor<?x!qcore.qubit>
    %qreg1 = func.call @funcC(%qreg) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
    "test.op"(%qreg1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK:           %qreg = "test.op"() : () -> tensor<?x!qcore.qubit>
// CHECK-NEXT:      %qreg1 = func.call @funcC(%qreg) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
// CHECK-NEXT:      "test.op"(%qreg1) : (tensor<?x!qcore.qubit>) -> ()

}
// CHECK-NEXT:  }


// ----
// CHECK-NEXT: ----

builtin.module {
// CHECK:       builtin.module {

    log_asm_api.circuit_dec @circuitA(%qreg : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> attributes {stab.flows = #stab.concrete_flow_array<[<+:1>{I -> X0 : 1}]>} {
        "test.op"() {circuit = "A"} : () -> ()
        log_asm_api.return %qreg : tensor<?x!qcore.qubit>
    }
// CHECK-NOT: @circuitA

    %qreg = "test.op"() : () -> tensor<?x!qcore.qubit>
// CHECK:           %qreg = "test.op"() : () -> tensor<?x!qcore.qubit>

    %qreg_1 = log_asm_api.call @circuitA(%qreg) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
// CHECK-NEXT:      %qreg_1 = qstruct.circuit(%qreg : tensor<?x!qcore.qubit>) {stab.flows = #stab.concrete_flow_array<[<+:1>{I -> X0 : 1}]>} -> tensor<?x!qcore.qubit> {
// CHECK-NEXT:      ^bb0(%qreg_2: tensor<?x!qcore.qubit>):
// CHECK-NEXT:        "test.op"() {circuit = "A"} : () -> ()
// CHECK-NEXT:        qstruct.yield %qreg_2 : tensor<?x!qcore.qubit>
// CHECK-NEXT:      }

    "test.op"(%qreg_1) : (tensor<?x!qcore.qubit>) -> ()
// CHECK-NEXT:      "test.op"(%qreg_1) : (tensor<?x!qcore.qubit>) -> ()

}
// CHECK-NEXT:  }
