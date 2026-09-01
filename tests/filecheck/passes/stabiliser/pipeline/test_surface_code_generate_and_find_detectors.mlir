// RUN: deltakit_compile compile-passes %s -p split-gate-like-broadcast-ops -p generate-flows -p find-detectors -p merge-gate-like-broadcast-ops --pass-args '{"verify_between_passes": true}' -O %t && filecheck %s --input-file %t
// Same 3 round d=2 surface code (in stabiliser dialect), running just generate flows and find detectors pass
// Seeing observable flow of Z0 Z1 through the circuit.

// Note that the generated flows are not fully optimal but are correct and form a complete basis for
// the space of valid flows.

builtin.module {
    %d0 = qcore.alloc_qubit<coords=[(0.0, 0.0)]> -> !qcore.qubit
    %d1 = qcore.alloc_qubit<coords=[(1.0, 0.0)]> -> !qcore.qubit
    %d2 = qcore.alloc_qubit<coords=[(0.0, 1.0)]> -> !qcore.qubit
    %d3 = qcore.alloc_qubit<coords=[(1.0, 1.0)]> -> !qcore.qubit
    %aX = qcore.alloc_qubit<coords=[(0.5, 0.5)]> -> !qcore.qubit
    %aZ0 = qcore.alloc_qubit<coords=[(0.5, 1.5)]> -> !qcore.qubit
    %aZ1 = qcore.alloc_qubit<coords=[(1.5, 1.5)]> -> !qcore.qubit

    %state0 = stab.state.make(%d0, %d1, %d2, %d3, %aX, %aZ0, %aZ1 : !qcore.qubit) -> !stab.state<7 x !qcore.qubit, []>

    // Preparation: reset qubits to |0>.
    %state1 = stab.circuit %state0 : !stab.state<7 x !qcore.qubit, []> -> !stab.state<7 x !qcore.qubit, [Z0 Z1]>
      with (%d0_b, %d1_b, %d2_b, %d3_b, %aX_b, %aZ0_b, %aZ1_b : !qcore.qubit), () {
        qref.reset<Z> (%d0_b, %d1_b, %d2_b, %d3_b, %aX_b, %aZ0_b, %aZ1_b)
        stab.yield []
    } [<+:>{I -> Z0 Z1}]

    // Round 1: measure Z stabilizers Z0 Z2 (aZ0) and Z1 Z3 (aZ1).
    %state2 = stab.circuit %state1 : !stab.state<7 x !qcore.qubit, [Z0 Z1]> -> !stab.state<7 x !qcore.qubit, []>
      with (%d0_b, %d1_b, %d2_b, %d3_b, %aX_b, %aZ0_b, %aZ1_b : !qcore.qubit), () {
        qref.reset<Z> (%aZ0_b)
        qref.gate<#qcore.gate.cx> (%d0_b, %aZ0_b)
        qref.gate<#qcore.gate.cx> (%d2_b, %aZ0_b)
        %mz0_1 = qref.measure<Z> (%aZ0_b) -> i1
        qref.reset<Z> (%aZ1_b)
        qref.gate<#qcore.gate.cx> (%d1_b, %aZ1_b)
        qref.gate<#qcore.gate.cx> (%d3_b, %aZ1_b)
        %mz1_1 = qref.measure<Z> (%aZ1_b) -> i1
        stab.yield [%mz0_1, %mz1_1 : i1, i1]
      } []

    // Round 1: measure X stabilizer X0 X1 X2 X3 using aX.
    %state3 = stab.circuit %state2 : !stab.state<7 x !qcore.qubit, []> -> !stab.state<7 x !qcore.qubit, []>
      with (%d0_b, %d1_b, %d2_b, %d3_b, %aX_b, %aZ0_b, %aZ1_b : !qcore.qubit), () {
        qref.reset<X> (%aX_b)
        qref.gate<#qcore.gate.cx> (%aX_b, %d0_b)
        qref.gate<#qcore.gate.cx> (%aX_b, %d1_b)
        qref.gate<#qcore.gate.cx> (%aX_b, %d2_b)
        qref.gate<#qcore.gate.cx> (%aX_b, %d3_b)
        %mx1 = qref.measure<X> (%aX_b) -> i1
        stab.yield [%mx1 : i1]
      } []

    // Round 2: repeat Z stabilizers Z0 Z2 (aZ0) and Z1 Z3 (aZ1).
    %state4 = stab.circuit %state3 : !stab.state<7 x !qcore.qubit, []> -> !stab.state<7 x !qcore.qubit, []>
      with (%d0_b, %d1_b, %d2_b, %d3_b, %aX_b, %aZ0_b, %aZ1_b : !qcore.qubit), () {
        qref.reset<Z> (%aZ0_b)
        qref.gate<#qcore.gate.cx> (%d0_b, %aZ0_b)
        qref.gate<#qcore.gate.cx> (%d2_b, %aZ0_b)
        %mz0_2 = qref.measure<Z> (%aZ0_b) -> i1
        qref.reset<Z> (%aZ1_b)
        qref.gate<#qcore.gate.cx> (%d1_b, %aZ1_b)
        qref.gate<#qcore.gate.cx> (%d3_b, %aZ1_b)
        %mz1_2 = qref.measure<Z> (%aZ1_b) -> i1
        stab.yield [%mz0_2, %mz1_2 : i1, i1]
      } []

    // Round 2: repeat X stabilizer X0 X1 X2 X3 using aX.
    %state5 = stab.circuit %state4 : !stab.state<7 x !qcore.qubit, []> -> !stab.state<7 x !qcore.qubit, []>
      with (%d0_b, %d1_b, %d2_b, %d3_b, %aX_b, %aZ0_b, %aZ1_b : !qcore.qubit), () {
        qref.reset<X> (%aX_b)
        qref.gate<#qcore.gate.cx> (%aX_b, %d0_b)
        qref.gate<#qcore.gate.cx> (%aX_b, %d1_b)
        qref.gate<#qcore.gate.cx> (%aX_b, %d2_b)
        qref.gate<#qcore.gate.cx> (%aX_b, %d3_b)
        %mx2 = qref.measure<X> (%aX_b) -> i1
        stab.yield [%mx2 : i1]
      } []

    // Final data readout in Z.
    %state6 = stab.circuit %state5 : !stab.state<7 x !qcore.qubit, []> -> !stab.state<7 x !qcore.qubit, []>
      with (%d0_b, %d1_b, %d2_b, %d3_b, %aX_b, %aZ0_b, %aZ1_b : !qcore.qubit), () {
        %rd0 = qref.measure<Z> (%d0_b) -> i1
        %rd1 = qref.measure<Z> (%d1_b) -> i1
        %rd2 = qref.measure<Z> (%d2_b) -> i1
        %rd3 = qref.measure<Z> (%d3_b) -> i1
        stab.yield [%rd0, %rd1, %rd2, %rd3 : i1, i1, i1, i1]
      } []
}

// CHECK:      builtin.module {
// CHECK-NEXT:     %d0 = qcore.alloc_qubit<coords = [(0.0, 0.0)]> -> !qcore.qubit
// CHECK-NEXT:     %d1 = qcore.alloc_qubit<coords = [(1.0, 0.0)]> -> !qcore.qubit
// CHECK-NEXT:     %d2 = qcore.alloc_qubit<coords = [(0.0, 1.0)]> -> !qcore.qubit
// CHECK-NEXT:     %d3 = qcore.alloc_qubit<coords = [(1.0, 1.0)]> -> !qcore.qubit
// CHECK-NEXT:     %aX = qcore.alloc_qubit<coords = [(0.5, 0.5)]> -> !qcore.qubit
// CHECK-NEXT:     %aZ0 = qcore.alloc_qubit<coords = [(0.5, 1.5)]> -> !qcore.qubit
// CHECK-NEXT:     %aZ1 = qcore.alloc_qubit<coords = [(1.5, 1.5)]> -> !qcore.qubit
// CHECK-NEXT:     %state0 = stab.state.make(%d0, %d1, %d2, %d3, %aX, %aZ0, %aZ1 : !qcore.qubit) -> !stab.state<7 x !qcore.qubit, []>
// CHECK-NEXT:     %state1 = stab.circuit %state0 : !stab.state<7 x !qcore.qubit, []> -> !stab.state<7 x !qcore.qubit, [Z0 Z1 Z2 Z3, Z0 Z1, Z1 Z3]>
// CHECK-NEXT:       with (%d0_b, %d1_b, %d2_b, %d3_b, %aX_b, %aZ0_b, %aZ1_b : !qcore.qubit), (){
// CHECK-NEXT:         qref.reset<Z> (%d0_b, %d1_b, %d2_b, %d3_b, %aX_b, %aZ0_b, %aZ1_b)
// CHECK-NEXT:         stab.yield []
// CHECK-NEXT:       } [<+:>{I -> Z0 Z1 Z2 Z3}, <+:>{I -> Z0 Z1}, <+:>{I -> Z1 Z3}]
// CHECK-NEXT:     %state2, %0, %1 = stab.circuit %state1 : !stab.state<7 x !qcore.qubit, [Z0 Z1 Z2 Z3, Z0 Z1, Z1 Z3]> -> !stab.state<7 x !qcore.qubit, [Z0 Z1, Z0 Z2, Z1 Z3]>
// CHECK-NEXT:       with (%d0_b, %d1_b, %d2_b, %d3_b, %aX_b, %aZ0_b, %aZ1_b : !qcore.qubit), (){
// CHECK-NEXT:         qref.reset<Z> (%aZ0_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%d0_b, %aZ0_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%d2_b, %aZ0_b)
// CHECK-NEXT:         %mz0 = qref.measure<Z> (%aZ0_b) -> i1
// CHECK-NEXT:         qref.reset<Z> (%aZ1_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%d1_b, %aZ1_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%d3_b, %aZ1_b)
// CHECK-NEXT:         %mz1 = qref.measure<Z> (%aZ1_b) -> i1
// CHECK-NEXT:         [[D1:%[\w\d_]+]] = qec.detector(%mz0, %mz1)
// CHECK-NEXT:         [[D2:%[\w\d_]+]] = qec.detector(%mz1)
// CHECK-NEXT:         stab.yield [%mz0, %mz1 : i1, i1] %mz0, %mz1 : i1, i1
// CHECK-NEXT:       } [<+:0>{I -> Z0 Z2}, <+:1>{I -> Z1 Z3}, <+:0, 1>{Z0 Z1 Z2 Z3 -> I}, <+:>{Z0 Z1 -> Z0 Z1}, <+:1>{Z1 Z3 -> I}]
// CHECK-NEXT:     %state3, %2, %3, %4 = stab.circuit %state2 : !stab.state<7 x !qcore.qubit, [Z0 Z1, Z0 Z2, Z1 Z3]> -> !stab.state<7 x !qcore.qubit, [X0 X1 X2 X3, Z0 Z1, Z0 Z2, Z1 Z3]>
// CHECK-NEXT:       with (%d0_b, %d1_b, %d2_b, %d3_b, %aX_b, %aZ0_b, %aZ1_b : !qcore.qubit), (%5 = %0 : i1, %6 = %1 : i1){
// CHECK-NEXT:         qref.reset<X> (%aX_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%aX_b, %d0_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%aX_b, %d1_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%aX_b, %d2_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%aX_b, %d3_b)
// CHECK-NEXT:         %mx1 = qref.measure<X> (%aX_b) -> i1
// CHECK-NEXT:         stab.yield [%mx1 : i1] %mx1, %5, %6 : i1, i1, i1
// CHECK-NEXT:       } [<+:0>{I -> X0 X1 X2 X3}, <+:>{Z0 Z1 -> Z0 Z1}, <+:>{Z0 Z2 -> Z0 Z2}, <+:>{Z1 Z3 -> Z1 Z3}]
// CHECK-NEXT:     %state4, %5, %6, %7 = stab.circuit %state3 : !stab.state<7 x !qcore.qubit, [X0 X1 X2 X3, Z0 Z1, Z0 Z2, Z1 Z3]> -> !stab.state<7 x !qcore.qubit, [X0 X1 X2 X3, Z0 Z1, Z0 Z2 Z5, Z0 Z2, Z1 Z3 Z6, Z1 Z3]>
// CHECK-NEXT:       with (%d0_b, %d1_b, %d2_b, %d3_b, %aX_b, %aZ0_b, %aZ1_b : !qcore.qubit), (%8 = %2 : i1, %9 = %3 : i1, %10 = %4 : i1){
// CHECK-NEXT:         qref.reset<Z> (%aZ0_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%d0_b, %aZ0_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%d2_b, %aZ0_b)
// CHECK-NEXT:         %mz0 = qref.measure<Z> (%aZ0_b) -> i1
// CHECK-NEXT:         qref.reset<Z> (%aZ1_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%d1_b, %aZ1_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%d3_b, %aZ1_b)
// CHECK-NEXT:         %mz1 = qref.measure<Z> (%aZ1_b) -> i1
// CHECK-NEXT:         [[D3:%[\w\d_]+]] = qec.detector(%9, %mz0)
// CHECK-NEXT:         [[D4:%[\w\d_]+]] = qec.detector(%10, %mz1)
// CHECK-NEXT:         stab.yield [%mz0, %mz1 : i1, i1] %8, %mz0, %mz1 : i1, i1, i1
// CHECK-NEXT:       } [<+:>{I -> Z0 Z2 Z5}, <+:0>{I -> Z0 Z2}, <+:>{I -> Z1 Z3 Z6}, <+:1>{I -> Z1 Z3}, <+:>{X0 X1 X2 X3 -> X0 X1 X2 X3}, <+:>{Z0 Z1 -> Z0 Z1}, <+:0>{Z0 Z2 -> I}, <+:1>{Z1 Z3 -> I}]
// CHECK-NEXT:     %state5, %8, %9, %10 = stab.circuit %state4 : !stab.state<7 x !qcore.qubit, [X0 X1 X2 X3, Z0 Z1, Z0 Z2 Z5, Z0 Z2, Z1 Z3 Z6, Z1 Z3]> -> !stab.state<7 x !qcore.qubit, [Z0 Z1, Z0 Z2 Z5, Z0 Z2, Z1 Z3 Z6, Z1 Z3, X4]>
// CHECK-NEXT:       with (%d0_b, %d1_b, %d2_b, %d3_b, %aX_b, %aZ0_b, %aZ1_b : !qcore.qubit), (%11 = %5 : i1, %12 = %6 : i1, %13 = %7 : i1){
// CHECK-NEXT:         qref.reset<X> (%aX_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%aX_b, %d0_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%aX_b, %d1_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%aX_b, %d2_b)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%aX_b, %d3_b)
// CHECK-NEXT:         %mx2 = qref.measure<X> (%aX_b) -> i1
// CHECK-NEXT:         [[D5:%[\w\d_]+]] = qec.detector(%11, %mx2)
// CHECK-NEXT:         stab.yield [%mx2 : i1] %12, %13, %mx2 : i1, i1, i1
// CHECK-NEXT:       } [<+:0>{I -> X4}, <+:0>{X0 X1 X2 X3 -> I}, <+:>{Z0 Z1 -> Z0 Z1}, <+:>{Z0 Z2 Z5 -> Z0 Z2 Z5}, <+:>{Z0 Z2 -> Z0 Z2}, <+:>{Z1 Z3 Z6 -> Z1 Z3 Z6}, <+:>{Z1 Z3 -> Z1 Z3}]
// CHECK-NEXT:     %state6, %11, %12, %13, %14, %15 = stab.circuit %state5 : !stab.state<7 x !qcore.qubit, [Z0 Z1, Z0 Z2 Z5, Z0 Z2, Z1 Z3 Z6, Z1 Z3, X4]> -> !stab.state<7 x !qcore.qubit, [Z0 Z2 Z5, Z0, Z1 Z3 Z6, Z1, Z2, Z3, X4]>
// CHECK-NEXT:       with (%d0_b, %d1_b, %d2_b, %d3_b, %aX_b, %aZ0_b, %aZ1_b : !qcore.qubit), (%16 = %8 : i1, %17 = %9 : i1, %18 = %10 : i1){
// CHECK-NEXT:         %rd0 = qref.measure<Z> (%d0_b) -> i1
// CHECK-NEXT:         %rd1 = qref.measure<Z> (%d1_b) -> i1
// CHECK-NEXT:         %rd2 = qref.measure<Z> (%d2_b) -> i1
// CHECK-NEXT:         %rd3 = qref.measure<Z> (%d3_b) -> i1
// CHECK-NEXT:         [[D6:%[\w\d_]+]] = qec.detector(%rd0, %rd1)
// CHECK-NEXT:         [[D7:%[\w\d_]+]] = qec.detector(%16, %rd0, %rd2)
// CHECK-NEXT:         [[D8:%[\w\d_]+]] = qec.detector(%17, %rd1, %rd3)
// CHECK-NEXT:         stab.yield [%rd0, %rd1, %rd2, %rd3 : i1, i1, i1, i1] %rd0, %rd1, %rd2, %rd3, %18 : i1, i1, i1, i1, i1
// CHECK-NEXT:       } [<+:0>{I -> Z0}, <+:1>{I -> Z1}, <+:2>{I -> Z2}, <+:3>{I -> Z3}, <+:0, 1>{Z0 Z1 -> I}, <+:>{Z0 Z2 Z5 -> Z0 Z2 Z5}, <+:0, 2>{Z0 Z2 -> I}, <+:>{Z1 Z3 Z6 -> Z1 Z3 Z6}, <+:1, 3>{Z1 Z3 -> I}, <+:>{X4 -> X4}]
// CHECK-NEXT: }
