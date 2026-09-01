// RUN: deltakit_compile compile-passes -t %s -p inline-circuits-and-subroutines --pass-args \
// RUN: '{"warn_on_loss_of_flows": true, "warn_on_circuits_not_inlined": true, "warn_on_functions_not_inlined": true}' -O %t.mlir &> %t.log && filecheck %s --input-file %t.log


// Used recursive circuit calls are untouched. Unused Recursive calls get removed.
builtin.module {

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
    // CHECK-DAG: DeltakitCompilerWarning: log_asm_api.circuit_dec "circuitA" could not be inlined: it is called recursively
    // CHECK-DAG: DeltakitCompilerWarning: log_asm_api.circuit_dec "circuitB" could not be inlined: it is called recursively
    // CHECK-DAG: DeltakitCompilerWarning: log_asm_api.circuit_dec "circuitC" could not be inlined: it is called recursively

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

    // CHECK-NOT: circuitX
    // CHECK-NOT: circuitY
    // CHECK-NOT: circuitZ

    %qreg = "test.op"() : () -> tensor<?x!qcore.qubit>
    %qreg1 = log_asm_api.call @circuitC(%qreg) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
    "test.op"(%qreg1) : (tensor<?x!qcore.qubit>) -> ()
}

// ----

// Used recursive subroutine calls are untouched. Unused Recursive calls get removed.
builtin.module {

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
    // CHECK-DAG: DeltakitCompilerWarning: func.func "funcA" could not be inlined: it is called recursively
    // CHECK-DAG: DeltakitCompilerWarning: func.func "funcB" could not be inlined: it is called recursively
    // CHECK-DAG: DeltakitCompilerWarning: func.func "funcC" could not be inlined: it is called recursively

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

    // CHECK-NOT: funcX
    // CHECK-NOT: funcY
    // CHECK-NOT: funcZ

    %qreg = "test.op"() : () -> tensor<?x!qcore.qubit>
    %qreg1 = func.call @funcC(%qreg) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
    "test.op"(%qreg1) : (tensor<?x!qcore.qubit>) -> ()

}

// ----


builtin.module {
    log_asm_api.circuit_dec @circuitA(%qreg : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> attributes {stab.flows = #stab.concrete_flow_array<[<+:1>{I -> X0 : 2}]>} {
        "test.op"() {circuit = "A"} : () -> ()
        log_asm_api.return %qreg : tensor<?x!qcore.qubit>
    }
    log_asm_api.circuit_dec @circuitB(%qreg : tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit> attributes {stab.flows = #stab.concrete_flow_array<[<+:1>{I -> X0 : 2}]>} {
        "test.op"() {circuit = "B"} : () -> ()
        %qreg_1 = log_asm_api.call @circuitA(%qreg) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
        log_asm_api.return %qreg_1 : tensor<?x!qcore.qubit>
    }

    %qreg = "test.op"() : () -> tensor<?x!qcore.qubit>
    %qreg_1 = log_asm_api.call @circuitB(%qreg) : (tensor<?x!qcore.qubit>) -> tensor<?x!qcore.qubit>
// CHECK: DeltakitCompilerWarning: Stabiliser flows for circuit declaration "circuitA" were dropped during circuit inlining into "circuitB"

    "test.op"(%qreg_1) : (tensor<?x!qcore.qubit>) -> ()
}
