// RUN: deltakit_compile compile-passes %s -p stabiliser-flow-pipeline --pass-args '{"verify_between_passes": true, "verify_flows": false}' -O %t && filecheck %s --input-file %t
// Small d=2 surface code (rotated planar) memory experiment skeleton.
//
// Layout (one plausible rotated d=2 patch):
//   data:   d0, d1
//           d2, d3
//   ancillas: aX (measures X-type stabilizer), aZ0/aZ1 (measure Z-type stabilizers)
//
// This is intentionally minimal: 2 rounds of syndrome extraction followed by data readout.
// Also, have observable Z0 Z1 annotated and flowing through the circuit.

// Note that the generated detectors are not fully optimal but are correct and form a complete basis
// for the space of valid detectors.

builtin.module {
    // Declare data and ancilla qubits
    %d = qcore.alloc_qubit<coords=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)]> -> !qcore.qubit_reg<4>
    %a = qcore.alloc_qubit<coords=[(0.5, 0.5), (0.5, 1.5), (1.5, 1.5)]> -> !qcore.qubit_reg<3>

    // Preparation: reset qubits to |0>.
    %d_1, %a_1 = qstruct.circuit(%d, %a : !qcore.qubit_reg<4>, !qcore.qubit_reg<3>)
        {stab.flows = #stab.concrete_flow_array<[<+:>{I -> Z0 Z1 : 7}]>}
        -> !qcore.qubit_reg<4>, !qcore.qubit_reg<3> {
    ^bb0(%d_b: !qcore.qubit_reg<4>, %a_b: !qcore.qubit_reg<3>):
        %d0, %d1, %d2, %d3 = qcore.unpack_qubit_reg(%d_b : !qcore.qubit_reg<4>)
        %aX, %aZ0, %aZ1 = qcore.unpack_qubit_reg(%a_b : !qcore.qubit_reg<3>)
        qref.reset<Z> (%d0, %d1, %d2, %d3, %aX, %aZ0, %aZ1)
        %d_b1 = qcore.pack_qubit_reg(%d0, %d1, %d2, %d3) -> !qcore.qubit_reg<4>
        %a_b1 = qcore.pack_qubit_reg(%aX, %aZ0, %aZ1) -> !qcore.qubit_reg<3>
        qstruct.yield %d_b1, %a_b1 : !qcore.qubit_reg<4>, !qcore.qubit_reg<3>
    }


    // Round 1: measure Z stabilizers Z0 Z2 (aZ0) and Z1 Z3 (aZ1).
    %d_2, %a_2 = qstruct.circuit(%d_1, %a_1 : !qcore.qubit_reg<4>, !qcore.qubit_reg<3>)
        -> !qcore.qubit_reg<4>, !qcore.qubit_reg<3> {
    ^bb0(%d_b: !qcore.qubit_reg<4>, %a_b: !qcore.qubit_reg<3>):
        %d0, %d1, %d2, %d3 = qcore.unpack_qubit_reg(%d_b : !qcore.qubit_reg<4>)
        %aX, %aZ0, %aZ1 = qcore.unpack_qubit_reg(%a_b : !qcore.qubit_reg<3>)
        qref.reset<Z> (%aZ0)
        qref.gate<#qcore.gate.cx> (%d0, %aZ0)
        qref.gate<#qcore.gate.cx> (%d2, %aZ0)
        %mz0 = qref.measure<Z> (%aZ0) -> i1
        qref.reset<Z> (%aZ1)
        qref.gate<#qcore.gate.cx> (%d1, %aZ1)
        qref.gate<#qcore.gate.cx> (%d3, %aZ1)
        %mz1 = qref.measure<Z> (%aZ1) -> i1
        %d_b2 = qcore.pack_qubit_reg(%d0, %d1, %d2, %d3) -> !qcore.qubit_reg<4>
        %a_b2 = qcore.pack_qubit_reg(%aX, %aZ0, %aZ1) -> !qcore.qubit_reg<3>
        qstruct.yield %d_b2, %a_b2 : !qcore.qubit_reg<4>, !qcore.qubit_reg<3>
    }


    // Round 1: measure X stabilizer X0 X1 X2 X3 using aX.
    %d_3, %a_3 = qstruct.circuit(%d_2, %a_2 : !qcore.qubit_reg<4>, !qcore.qubit_reg<3>)
        -> !qcore.qubit_reg<4>, !qcore.qubit_reg<3> {
    ^bb0(%d_b: !qcore.qubit_reg<4>, %a_b: !qcore.qubit_reg<3>):
        %d0, %d1, %d2, %d3 = qcore.unpack_qubit_reg(%d_b : !qcore.qubit_reg<4>)
        %aX, %aZ0, %aZ1 = qcore.unpack_qubit_reg(%a_b : !qcore.qubit_reg<3>)
        qref.reset<X> (%aX)
        qref.gate<#qcore.gate.cx> (%aX, %d0)
        qref.gate<#qcore.gate.cx> (%aX, %d1)
        qref.gate<#qcore.gate.cx> (%aX, %d2)
        qref.gate<#qcore.gate.cx> (%aX, %d3)
        %mx1 = qref.measure<X> (%aX) -> i1
        %d_b3 = qcore.pack_qubit_reg(%d0, %d1, %d2, %d3) -> !qcore.qubit_reg<4>
        %a_b3 = qcore.pack_qubit_reg(%aX, %aZ0, %aZ1) -> !qcore.qubit_reg<3>
        qstruct.yield %d_b3, %a_b3 : !qcore.qubit_reg<4>, !qcore.qubit_reg<3>
    }

    // Round 2: repeat Z stabilizers Z0 Z2 (aZ0) and Z1 Z3 (aZ1).
    %d_4, %a_4 = qstruct.circuit(%d_3, %a_3 : !qcore.qubit_reg<4>, !qcore.qubit_reg<3>)
        -> !qcore.qubit_reg<4>, !qcore.qubit_reg<3> {
    ^bb0(%d_b: !qcore.qubit_reg<4>, %a_b: !qcore.qubit_reg<3>):
        %d0, %d1, %d2, %d3 = qcore.unpack_qubit_reg(%d_b : !qcore.qubit_reg<4>)
        %aX, %aZ0, %aZ1 = qcore.unpack_qubit_reg(%a_b : !qcore.qubit_reg<3>)
        qref.reset<Z> (%aZ0)
        qref.gate<#qcore.gate.cx> (%d0, %aZ0)
        qref.gate<#qcore.gate.cx> (%d2, %aZ0)
        %mz0_1 = qref.measure<Z> (%aZ0) -> i1
        qref.reset<Z> (%aZ1)
        qref.gate<#qcore.gate.cx> (%d1, %aZ1)
        qref.gate<#qcore.gate.cx> (%d3, %aZ1)
        %mz1_1 = qref.measure<Z> (%aZ1) -> i1
        %d_b4 = qcore.pack_qubit_reg(%d0, %d1, %d2, %d3) -> !qcore.qubit_reg<4>
        %a_b4 = qcore.pack_qubit_reg(%aX, %aZ0, %aZ1) -> !qcore.qubit_reg<3>
        qstruct.yield %d_b4, %a_b4 : !qcore.qubit_reg<4>, !qcore.qubit_reg<3>
    }

    // Round 2: repeat X stabilizer X0 X1 X2 X3 using aX.
    %d_5, %a_5 = qstruct.circuit(%d_4, %a_4 : !qcore.qubit_reg<4>, !qcore.qubit_reg<3>)
        -> !qcore.qubit_reg<4>, !qcore.qubit_reg<3> {
    ^bb0(%d_b: !qcore.qubit_reg<4>, %a_b: !qcore.qubit_reg<3>):
        %d0, %d1, %d2, %d3 = qcore.unpack_qubit_reg(%d_b : !qcore.qubit_reg<4>)
        %aX, %aZ0, %aZ1 = qcore.unpack_qubit_reg(%a_b : !qcore.qubit_reg<3>)
        qref.reset<X> (%aX)
        qref.gate<#qcore.gate.cx> (%aX, %d0)
        qref.gate<#qcore.gate.cx> (%aX, %d1)
        qref.gate<#qcore.gate.cx> (%aX, %d2)
        qref.gate<#qcore.gate.cx> (%aX, %d3)
        %mx2 = qref.measure<X> (%aX) -> i1
        %d_b5 = qcore.pack_qubit_reg(%d0, %d1, %d2, %d3) -> !qcore.qubit_reg<4>
        %a_b5 = qcore.pack_qubit_reg(%aX, %aZ0, %aZ1) -> !qcore.qubit_reg<3>
        qstruct.yield %d_b5, %a_b5 : !qcore.qubit_reg<4>, !qcore.qubit_reg<3>
    }

    // Final data readout in Z.
    %d_6, %a_6 = qstruct.circuit(%d_5, %a_5 : !qcore.qubit_reg<4>, !qcore.qubit_reg<3>)
        -> !qcore.qubit_reg<4>, !qcore.qubit_reg<3> {
    ^bb0(%d_b: !qcore.qubit_reg<4>, %a_b: !qcore.qubit_reg<3>):
        %d0, %d1, %d2, %d3 = qcore.unpack_qubit_reg(%d_b : !qcore.qubit_reg<4>)
        %rd0 = qref.measure<Z> (%d0) -> i1
        %rd1 = qref.measure<Z> (%d1) -> i1
        %rd2 = qref.measure<Z> (%d2) -> i1
        %rd3 = qref.measure<Z> (%d3) -> i1
        %d_b6 = qcore.pack_qubit_reg(%d0, %d1, %d2, %d3) -> !qcore.qubit_reg<4>
        qstruct.yield %d_b6, %a_b : !qcore.qubit_reg<4>, !qcore.qubit_reg<3>
    }
}

// CHECK:      builtin.module {
// CHECK-NEXT:     %d = qcore.alloc_qubit<coords = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)]> -> !qcore.qubit_reg<4>
// CHECK-NEXT:     [[Q0:%[\w\d_]+]], [[Q1:%[\w\d_]+]], [[Q2:%[\w\d_]+]], [[Q3:%[\w\d_]+]]
// CHECK-SAME:         = qcore.unpack_qubit_reg(%d : !qcore.qubit_reg<4>)
// CHECK-NEXT:     %a = qcore.alloc_qubit<coords = [(0.5, 0.5), (0.5, 1.5), (1.5, 1.5)]> -> !qcore.qubit_reg<3>
// CHECK-NEXT:     [[Q4:%[\w\d_]+]], [[Q5:%[\w\d_]+]], [[Q6:%[\w\d_]+]] = qcore.unpack_qubit_reg(%a : !qcore.qubit_reg<3>)
// CHECK-NEXT:     [[R0:%[\w\d_]+]] = qcore.pack_qubit_reg([[Q0]], [[Q1]], [[Q2]], [[Q3]], [[Q4]],
// CHECK-SAME:         [[Q5]], [[Q6]]) -> !qcore.qubit_reg<7>
// CHECK-NEXT:     [[R1:%[\w\d_]+]] = qstruct.circuit([[R0]] : !qcore.qubit_reg<7>) -> !qcore.qubit_reg<7> {
// CHECK-NEXT:     ^bb0([[R2:%[\w\d_]+]]: !qcore.qubit_reg<7>):
// CHECK-NEXT:         %d0, %d1, %d2, %d3, %aX, %aZ0, %aZ1 = qcore.unpack_qubit_reg([[R2]] : !qcore.qubit_reg<7>)
// CHECK-NEXT:         qref.reset<Z> (%d0, %d1, %d2, %d3, %aX, %aZ0, %aZ1)
// CHECK-NEXT:         qref.reset<Z> (%aZ0)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%d0, %aZ0)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%d2, %aZ0)
// CHECK-NEXT:         %mz0 = qref.measure<Z> (%aZ0) -> i1
// CHECK-NEXT:         qref.reset<Z> (%aZ1)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%d1, %aZ1)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%d3, %aZ1)
// CHECK-NEXT:         %mz1 = qref.measure<Z> (%aZ1) -> i1
// CHECK-NEXT:         [[D1:%[\w\d_]+]] = qec.detector<[1.0, 1.5]> (%mz1, %mz0)
// CHECK-NEXT:         [[D2:%[\w\d_]+]] = qec.detector<[1.5, 1.5]> (%mz1)
// CHECK-NEXT:         qref.reset<X> (%aX)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%aX, %d0)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%aX, %d1)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%aX, %d2)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%aX, %d3)
// CHECK-NEXT:         %mx1 = qref.measure<X> (%aX) -> i1
// CHECK-NEXT:         qref.reset<Z> (%aZ0)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%d0, %aZ0)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%d2, %aZ0)
// CHECK-NEXT:         %mz0_1 = qref.measure<Z> (%aZ0) -> i1
// CHECK-NEXT:         qref.reset<Z> (%aZ1)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%d1, %aZ1)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%d3, %aZ1)
// CHECK-NEXT:         %mz1_1 = qref.measure<Z> (%aZ1) -> i1
// CHECK-NEXT:         [[D3:%[\w\d_]+]] = qec.detector<[0.5, 1.5]> (%mz0, %mz0_1)
// CHECK-NEXT:         [[D4:%[\w\d_]+]] = qec.detector<[1.5, 1.5]> (%mz1, %mz1_1)
// CHECK-NEXT:         qref.reset<X> (%aX)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%aX, %d0)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%aX, %d1)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%aX, %d2)
// CHECK-NEXT:         qref.gate<#qcore.gate.cx> (%aX, %d3)
// CHECK-NEXT:         %mx2 = qref.measure<X> (%aX) -> i1
// CHECK-NEXT:         [[D5:%[\w\d_]+]] = qec.detector<[0.5, 0.5]> (%mx1, %mx2)
// CHECK-NEXT:         %rd0 = qref.measure<Z> (%d0) -> i1
// CHECK-NEXT:         %rd1 = qref.measure<Z> (%d1) -> i1
// CHECK-NEXT:         %rd2 = qref.measure<Z> (%d2) -> i1
// CHECK-NEXT:         %rd3 = qref.measure<Z> (%d3) -> i1
// CHECK-NEXT:         [[D6:%[\w\d_]+]] = qec.detector<[0.5, 0.0]> (%rd1, %rd0)
// CHECK-NEXT:         [[D7:%[\w\d_]+]] = qec.detector<[0.16666666666666666, 0.8333333333333334]> (%mz0_1, %rd0, %rd2)
// CHECK-NEXT:         [[D8:%[\w\d_]+]] = qec.detector<[1.1666666666666667, 0.8333333333333334]> (%mz1_1, %rd1, %rd3)
// CHECK-NEXT:         qstruct.yield [[R2]] : !qcore.qubit_reg<7>
// CHECK-NEXT:     }
// CHECK-NEXT: }
