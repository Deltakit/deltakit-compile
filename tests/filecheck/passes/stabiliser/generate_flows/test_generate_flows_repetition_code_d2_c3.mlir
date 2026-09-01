// RUN: deltakit_compile compile-passes %s -p generate-flows -O %t && filecheck %s --input-file %t

// d=2 repetition code memory experiment run for 3 cycles.

builtin.module {
    %qa = qcore.alloc_qubit<coords=[(0.0, 0.0)]> -> !qcore.qubit   // ancilla qubit
    %qd1 = qcore.alloc_qubit<coords=[(1.0, 0.0)]> -> !qcore.qubit  // data qubit 1
    %qd2 = qcore.alloc_qubit<coords=[(2.0, 0.0)]> -> !qcore.qubit  // data qubit 2

    %state0 = stab.state.make (%qa, %qd1, %qd2 : !qcore.qubit) -> !stab.state<3 x !qcore.qubit, []>

    // Initial reset layer, with a logical on %qd1
    %state1 = stab.circuit %state0 : !stab.state<3 x !qcore.qubit, []>
                                  -> !stab.state<3 x !qcore.qubit, [Z1]>
      with (%qa_b, %qd1_b, %qd2_b : !qcore.qubit), () {
        qref.reset<Z> (%qd1_b)
        qref.reset<Z> (%qd2_b)
        stab.yield []
      } [<+:>{I -> Z1}]

    // First syndrome extraction cycle
    %state2 = stab.circuit %state1 : !stab.state<3 x !qcore.qubit, [Z1]>
                                  -> !stab.state<3 x !qcore.qubit, [Z1]>
      with (%qa_b, %qd1_b, %qd2_b : !qcore.qubit), () {
        qref.reset<Z> (%qa_b)
        qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
        qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
        %m1 = qref.measure<Z> (%qa_b) -> i1
        stab.yield [%m1 : i1]
      } [<+:>{Z1 -> Z1}]

    // Second syndrome extraction cycle
    %state3 = stab.circuit %state2 : !stab.state<3 x !qcore.qubit, [Z1]>
                                  -> !stab.state<3 x !qcore.qubit, [Z1]>
      with (%qa_b, %qd1_b, %qd2_b : !qcore.qubit), () {
        qref.reset<Z> (%qa_b)
        qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
        qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
        %m2 = qref.measure<Z> (%qa_b) -> i1
        stab.yield [%m2 : i1]
      } [<+:>{Z1 -> Z1}]

    // Third syndrome extraction cycle
    %state4 = stab.circuit %state3 : !stab.state<3 x !qcore.qubit, [Z1]>
                                  -> !stab.state<3 x !qcore.qubit, [Z1]>
      with (%qa_b, %qd1_b, %qd2_b : !qcore.qubit), () {
        qref.reset<Z> (%qa_b)
        qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
        qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
        %m3 = qref.measure<Z> (%qa_b) -> i1
        stab.yield [%m3 : i1]
      } [<+:>{Z1 -> Z1}]

    // Final measurement layer, measuring the logical on %qd1
    %state5 = stab.circuit %state4 : !stab.state<3 x !qcore.qubit, [Z1]>
                                  -> !stab.state<3 x !qcore.qubit, []>
      with (%qa_b, %qd1_b, %qd2_b : !qcore.qubit), () {
        %m4 = qref.measure<Z> (%qd1_b) -> i1
        %m5 = qref.measure<Z> (%qd2_b) -> i1
        stab.yield [%m4, %m5 : i1, i1]
      } [<+:0>{Z1 -> I}]
}

// CHECK: builtin.module {
// CHECK-NEXT:   %qa = qcore.alloc_qubit<coords = [(0.0, 0.0)]> -> !qcore.qubit
// CHECK-NEXT:   %qd1 = qcore.alloc_qubit<coords = [(1.0, 0.0)]> -> !qcore.qubit
// CHECK-NEXT:   %qd2 = qcore.alloc_qubit<coords = [(2.0, 0.0)]> -> !qcore.qubit
// CHECK-NEXT:   %state0 = stab.state.make(%qa, %qd1, %qd2 : !qcore.qubit) -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:   %state1 = stab.circuit %state0 : !stab.state<3 x !qcore.qubit, []> -> !stab.state<3 x !qcore.qubit, [Z1 Z2, Z1]>
// CHECK-NEXT:     with (%qa_b, %qd1_b, %qd2_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%qd1_b)
// CHECK-NEXT:       qref.reset<Z> (%qd2_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{I -> Z1 Z2}, <+:>{I -> Z1}]
// CHECK-NEXT:   %state2 = stab.circuit %state1 : !stab.state<3 x !qcore.qubit, [Z1 Z2, Z1]> -> !stab.state<3 x !qcore.qubit, [Z1 Z2, Z1]>
// CHECK-NEXT:     with (%qa_b, %qd1_b, %qd2_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%qa_b)
// CHECK-NEXT:       qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
// CHECK-NEXT:       qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
// CHECK-NEXT:       %m1 = qref.measure<Z> (%qa_b) -> i1
// CHECK-NEXT:       stab.yield [%m1 : i1]
// CHECK-NEXT:     } [<+:0>{I -> Z1 Z2}, <+:0>{Z1 Z2 -> I}, <+:>{Z1 -> Z1}]
// CHECK-NEXT:   %state3 = stab.circuit %state2 : !stab.state<3 x !qcore.qubit, [Z1 Z2, Z1]> -> !stab.state<3 x !qcore.qubit, [Z1 Z2, Z1]>
// CHECK-NEXT:     with (%qa_b, %qd1_b, %qd2_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%qa_b)
// CHECK-NEXT:       qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
// CHECK-NEXT:       qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
// CHECK-NEXT:       %m2 = qref.measure<Z> (%qa_b) -> i1
// CHECK-NEXT:       stab.yield [%m2 : i1]
// CHECK-NEXT:     } [<+:0>{I -> Z1 Z2}, <+:0>{Z1 Z2 -> I}, <+:>{Z1 -> Z1}]
// CHECK-NEXT:   %state4 = stab.circuit %state3 : !stab.state<3 x !qcore.qubit, [Z1 Z2, Z1]> -> !stab.state<3 x !qcore.qubit, [Z0 Z1 Z2, Z1 Z2, Z1]>
// CHECK-NEXT:     with (%qa_b, %qd1_b, %qd2_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%qa_b)
// CHECK-NEXT:       qref.gate<#qcore.gate.cx> (%qd1_b, %qa_b)
// CHECK-NEXT:       qref.gate<#qcore.gate.cx> (%qd2_b, %qa_b)
// CHECK-NEXT:       %m3 = qref.measure<Z> (%qa_b) -> i1
// CHECK-NEXT:       stab.yield [%m3 : i1]
// CHECK-NEXT:     } [<+:>{I -> Z0 Z1 Z2}, <+:0>{I -> Z1 Z2}, <+:0>{Z1 Z2 -> I}, <+:>{Z1 -> Z1}]
// CHECK-NEXT:   %state5 = stab.circuit %state4 : !stab.state<3 x !qcore.qubit, [Z0 Z1 Z2, Z1 Z2, Z1]> -> !stab.state<3 x !qcore.qubit, [Z0 Z1 Z2, Z1, Z2]>
// CHECK-NEXT:     with (%qa_b, %qd1_b, %qd2_b : !qcore.qubit), (){
// CHECK-NEXT:       %m4 = qref.measure<Z> (%qd1_b) -> i1
// CHECK-NEXT:       %m5 = qref.measure<Z> (%qd2_b) -> i1
// CHECK-NEXT:       stab.yield [%m4, %m5 : i1, i1]
// CHECK-NEXT:     } [<+:0>{I -> Z1}, <+:1>{I -> Z2}, <+:>{Z0 Z1 Z2 -> Z0 Z1 Z2}, <+:0, 1>{Z1 Z2 -> I}, <+:0>{Z1 -> I}]
// CHECK-NEXT: }
