// RUN: deltakit_compile compile-passes %s -p stabiliser-flow-pipeline --pass-args '{"verify_between_passes": true}' -O %t && filecheck %s --input-file %t
// d=2 repetition code memory experiment run for 3 cycles

builtin.module {
    %qa = qcore.alloc_qubit<coords=[(0.0, 0.0)]> -> !qcore.qubit   // ancilla qubit
    %qd1 = qcore.alloc_qubit<coords=[(1.0, 0.0)]> -> !qcore.qubit  // data qubit 1
    %qd2 = qcore.alloc_qubit<coords=[(2.0, 0.0)]> -> !qcore.qubit  // data qubit 2

    // Initial reset layer, with a logical on %qd1
    %qa_1, %qd1_1, %qd2_1 = qstruct.circuit(%qa, %qd1, %qd2 : !qcore.qubit, !qcore.qubit, !qcore.qubit)
        {stab.flows = #stab.concrete_flow_array<[<+:>{I -> Z1 : 3}]>} -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
    ^bb0(%qa_b: !qcore.qubit, %qd1_b: !qcore.qubit, %qd2_b: !qcore.qubit):
        qref.reset<Z> (%qd1_b, %qd2_b)
        qstruct.yield %qa_b, %qd1_b, %qd2_b : !qcore.qubit, !qcore.qubit, !qcore.qubit
    }

    // First syndrome extraction cycle
    %qa_2, %qd1_2, %qd2_2, %m1 = qstruct.circuit(%qa_1, %qd1_1, %qd2_1 : !qcore.qubit, !qcore.qubit, !qcore.qubit)
        {stab.flows = #stab.concrete_flow_array<[<+:3>{I -> Z1 Z2 : 3}, <+:>{Z1 -> Z1 : 3}]>}
        -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1 {
    ^bb0(%qa_b: !qcore.qubit, %qd1_b: !qcore.qubit, %qd2_b: !qcore.qubit):
        qref.reset<Z> (%qa_b)
        qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
        qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
        %m1_b = qref.measure<Z> (%qa_b) -> i1
        qstruct.yield %qa_b, %qd1_b, %qd2_b, %m1_b : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1
    }

    // Second syndrome extraction cycle
    %qa_3, %qd1_3, %qd2_3, %m2 = qstruct.circuit(%qa_2, %qd1_2, %qd2_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit)
        {stab.flows = #stab.concrete_flow_array<[<+:3>{I -> Z1 Z2 : 3}, <+:3>{Z1 Z2 -> I : 3}, <+:>{Z1 -> Z1 : 3}]>}
        -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1 {
    ^bb0(%qa_b: !qcore.qubit, %qd1_b: !qcore.qubit, %qd2_b: !qcore.qubit):
        qref.reset<Z> (%qa_b)
        qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
        qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
        %m2_b = qref.measure<Z> (%qa_b) -> i1
        qstruct.yield %qa_b, %qd1_b, %qd2_b, %m2_b : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1
    }

    // Third syndrome extraction cycle
    %qa_4, %qd1_4, %qd2_4, %m3 = qstruct.circuit(%qa_3, %qd1_3, %qd2_3 : !qcore.qubit, !qcore.qubit, !qcore.qubit)
        {stab.flows = #stab.concrete_flow_array<[<+:3>{Z1 Z2 -> I : 3}, <+:>{Z1 -> Z1 : 3}]>}
        -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1 {
    ^bb0(%qa_b: !qcore.qubit, %qd1_b: !qcore.qubit, %qd2_b: !qcore.qubit):
        qref.reset<Z> (%qa_b)
        qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
        qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
        %m3_b = qref.measure<Z> (%qa_b) -> i1
        qstruct.yield %qa_b, %qd1_b, %qd2_b, %m3_b : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1
    }

    // Final measurement layer, measuring the logical on %qd1
    %qa_5, %qd1_5, %qd2_5, %m4, %m5 = qstruct.circuit(%qa_4, %qd1_4, %qd2_4 : !qcore.qubit, !qcore.qubit, !qcore.qubit)
        {stab.flows = #stab.concrete_flow_array<[<+:3>{Z1 -> I : 3}]>}
        -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1 {
    ^bb0(%qa_b: !qcore.qubit, %qd1_b: !qcore.qubit, %qd2_b: !qcore.qubit):
        %m4_b = qref.measure<Z> (%qd1_b) -> i1
        %m5_b = qref.measure<Z> (%qd2_b) -> i1
        qstruct.yield %qa_b, %qd1_b, %qd2_b, %m4_b, %m5_b : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1, i1
    }
}

// CHECK:      builtin.module {
// CHECK-NEXT:   %qa = qcore.alloc_qubit<coords = [(0.0, 0.0)]> -> !qcore.qubit
// CHECK-NEXT:   %qd1 = qcore.alloc_qubit<coords = [(1.0, 0.0)]> -> !qcore.qubit
// CHECK-NEXT:   %qd2 = qcore.alloc_qubit<coords = [(2.0, 0.0)]> -> !qcore.qubit
// CHECK-NEXT:   [[R0:%[\w\d_]+]] = qcore.pack_qubit_reg(%qa, %qd1, %qd2) -> !qcore.qubit_reg<3>
// CHECK-NEXT:   [[R1:%[\w\d_]+]] = qstruct.circuit([[R0]] : !qcore.qubit_reg<3>) -> !qcore.qubit_reg<3> {
// CHECK-NEXT:   ^bb0([[R2:%[\w\d_]+]]: !qcore.qubit_reg<3>):
// CHECK-NEXT:       %qa_b, %qd1_b, %qd2_b = qcore.unpack_qubit_reg([[R2]] : !qcore.qubit_reg<3>)
// CHECK-NEXT:       qref.reset<Z> (%qd1_b, %qd2_b)
// CHECK-NEXT:       qref.reset<Z> (%qa_b)
// CHECK-NEXT:       qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
// CHECK-NEXT:       qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
// CHECK-NEXT:       %m1_b = qref.measure<Z> (%qa_b) -> i1
// CHECK-NEXT:       [[D1:%[\w\d_]+]] = qec.detector<[0.0, 0.0]> (%m1_b)
// CHECK-NEXT:       qref.reset<Z> (%qa_b)
// CHECK-NEXT:       qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
// CHECK-NEXT:       qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
// CHECK-NEXT:       %m2_b = qref.measure<Z> (%qa_b) -> i1
// CHECK-NEXT:       [[D2:%[\w\d_]+]] = qec.detector<[0.0, 0.0]> (%m1_b, %m2_b)
// CHECK-NEXT:       qref.reset<Z> (%qa_b)
// CHECK-NEXT:       qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
// CHECK-NEXT:       qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
// CHECK-NEXT:       %m3_b = qref.measure<Z> (%qa_b) -> i1
// CHECK-NEXT:       [[D3:%[\w\d_]+]] = qec.detector<[0.0, 0.0]> (%m2_b, %m3_b)
// CHECK-NEXT:       %m4_b = qref.measure<Z> (%qd1_b) -> i1
// CHECK-NEXT:       %m5_b = qref.measure<Z> (%qd2_b) -> i1
// CHECK-NEXT:       [[D4:%[\w\d_]+]] = qec.detector<[1.0, 0.0]> (%m3_b, %m4_b, %m5_b)
// CHECK-NEXT:       [[D5:%[\w\d_]+]] = qec.detector<[1.0, 0.0]> (%m4_b)
// CHECK-NEXT:       qstruct.yield [[R2]] : !qcore.qubit_reg<3>
// CHECK-NEXT:   }
// CHECK-NEXT: }
