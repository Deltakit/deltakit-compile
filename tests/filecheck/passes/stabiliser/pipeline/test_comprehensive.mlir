// RUN: deltakit_compile compile-passes --test-mode %s -p stabiliser-flow-pipeline --pass-args '{"verify_between_passes": true, "generate_flows": false}' -O %t && filecheck %s --input-file %t
// Exercising supported corner cases of the stabiliser flow pipeline, other than those involving flow generation.

builtin.module {
    %q1 = qcore.alloc_qubit<coords=[(0.0, 0.0)]> -> !qcore.qubit
    %q2 = qcore.alloc_qubit -> !qcore.qubit
    %q3 = qcore.alloc_qubit -> !qcore.qubit

    // These registers will be used in two disjoint chains of circuits
    %reg0 = qcore.pack_qubit_reg(%q1, %q2) -> !qcore.qubit_reg<2>
    %reg1 = qcore.pack_qubit_reg(%q3) -> !qcore.qubit_reg<1>

    // Parallel ops, one branch of which has classical ops only
    %reg2, %m1_out, %reg3, %y, %x = qstruct.parallel<TOP> ->
            !qcore.qubit_reg<2>, i1, !qcore.qubit_reg<1>, i64, i1 {
        %reg2_in, %m1_in, %m2_in = qstruct.circuit(%reg0 : !qcore.qubit_reg<2>)
            {stab.flows = #stab.concrete_flow_array<[<+:1, 2>{I -> X0 X1 : 2}]>}
            -> !qcore.qubit_reg<2>, i1, i1 {
        ^bb0(%reg0_b : !qcore.qubit_reg<2>):
            %q1_b, %q2_b = qcore.unpack_qubit_reg(%reg0_b : !qcore.qubit_reg<2>)
            %m1 = qref.measure<X> (%q1_b) -> i1
            %m2 = qref.measure<X> (%q2_b) -> i1
            %reg0_b1 = qcore.pack_qubit_reg(%q1_b, %q2_b) -> !qcore.qubit_reg<2>
            qstruct.yield %reg0_b1, %m1, %m2 : !qcore.qubit_reg<2>, i1, i1
        }

        qstruct.yield %reg2_in, %m1_in : !qcore.qubit_reg<2>, i1
    } {
        // Two circuits in the same parallel region and some classical ops in between
        %q3_in, %m3_in = qstruct.circuit(%reg1 : !qcore.qubit_reg<1>)
            {stab.flows = #stab.concrete_flow_array<[<+:1>{I -> Z0 : 1}]>}
            -> !qcore.qubit, i1 {
        ^bb0(%reg1_b : !qcore.qubit_reg<1>):
            %q3_b = qcore.unpack_qubit_reg(%reg1_b : !qcore.qubit_reg<1>)
            %m3 = qref.measure<Z> (%q3_b) -> i1
            qstruct.yield %q3_b, %m3 : !qcore.qubit, i1
        }

        %y0 = arith.constant 0 : i64

        // Should be a detector here from Z0 -> I
        %reg3_in, %m4_in = qstruct.circuit(%q3_in : !qcore.qubit)
            {stab.flows = #stab.concrete_flow_array<[<+:>{I -> X0 : 1}, <+:1>{Z0 -> I : 1}]>}
            -> !qcore.qubit_reg<1>, i1 {
        ^bb0(%q3_b1 : !qcore.qubit):
            %m4 = qref.measure<Z> (%q3_b1) -> i1
            qref.reset<X> (%q3_b1)
            %reg3_b = qcore.pack_qubit_reg(%q3_b1) -> !qcore.qubit_reg<1>
            qstruct.yield %reg3_b, %m4 : !qcore.qubit_reg<1>, i1
        }

        qstruct.yield %reg3_in, %y0 : !qcore.qubit_reg<1>, i64
    } {
        // Classical operations only
        %x0 = arith.constant true
        qstruct.yield %x0 : i1
    }

    // Some classical control flow with no quantum operations: preserved
    %z = scf.if %m1_out -> (i1) {
        scf.yield %m1_out : i1
    } else {
        scf.yield %x : i1
    }
    %l = arith.constant 0 : index
    %u = "test.op"() : () -> index
    %step = arith.constant 1 : index
    %h = scf.for %i = %l to %u step %step iter_args(%k = %z) -> (i1) {
        %f = arith.xori %x, %x : i1
        %g = scf.while (%o = %f)  : (i1) -> i1 {
            scf.condition(%f) %f : i1
        } do {
        ^bb0(%c : i1):
            scf.yield %c : i1
        }
        scf.yield %g : i1
    }
    // Inhibit xDSL's automatic DCE
    qstruct.output(%y, %h : i64, i1)

    // Matching detectors across consecutive parallel regions, also parallel with no return
    qstruct.parallel<BOTTOM> -> {
        %reg4_in, %m5_in, %m6_in = qstruct.circuit(%reg2 : !qcore.qubit_reg<2>)
            {stab.flows = #stab.concrete_flow_array<[<+:1, 2>{X0 X1 -> I : 2}]>}
            -> !qcore.qubit_reg<2>, i1, i1 {
        ^bb0(%reg2_b : !qcore.qubit_reg<2>):
            %q1_b, %q2_b = qcore.unpack_qubit_reg(%reg2_b : !qcore.qubit_reg<2>)
            %m5 = qref.measure<X> (%q1_b) -> i1
            %m6 = qref.measure<X> (%q2_b) -> i1
            %reg2_b1 = qcore.pack_qubit_reg(%q1_b, %q2_b) -> !qcore.qubit_reg<2>
            qstruct.yield %reg2_b1, %m5, %m6 : !qcore.qubit_reg<2>, i1, i1
        }
        qstruct.yield
    } {
        %reg5_in, %m7_in = qstruct.circuit(%reg3 : !qcore.qubit_reg<1>)
            {stab.flows = #stab.concrete_flow_array<[<+:1>{X0 -> I : 1}]>}
            -> !qcore.qubit_reg<1>, i1 {
        ^bb0(%reg3_b : !qcore.qubit_reg<1>):
            %q3_b = qcore.unpack_qubit_reg(%reg3_b : !qcore.qubit_reg<1>)
            %m7 = qref.measure<X> (%q3_b) -> i1
            %reg3_b1 = qcore.pack_qubit_reg(%q3_b) -> !qcore.qubit_reg<1>
            qstruct.yield %reg3_b1, %m7 : !qcore.qubit_reg<1>, i1
        }
        qstruct.yield
    }
}

// CHECK:      builtin.module {
// CHECK-NEXT:     %q1 = qcore.alloc_qubit<coords = [(0.0, 0.0)]> -> !qcore.qubit
// CHECK-NEXT:     %q2 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:     %q3 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-DAG:      [[R0:%[\w\d_]+]] = qcore.pack_qubit_reg(%q1, %q2) -> !qcore.qubit_reg<2>
// CHECK-DAG:      [[R1:%[\w\d_]+]] = qcore.pack_qubit_reg(%q3) -> !qcore.qubit_reg<1>
// CHECK-NEXT:     %y0 = arith.constant 0 : i64
// CHECK-NEXT:     %x0 = arith.constant true
// CHECK-NEXT:     [[R2:%[\w\d_]+]], [[OUT1:%[\w\d_]+]], [[OUT2:%[\w\d_]+]], %m1_out, [[R3:%[\w\d_]+]] =
// CHECK-SAME:             qstruct.parallel<TOP> -> !qcore.qubit_reg<2>, i1, i1, i1, !qcore.qubit_reg<1> {
// CHECK-NEXT:         [[R2_IN:%[\w\d_]+]], [[OUT1_IN:%[\w\d_]+]], [[OUT2_IN:%[\w\d_]+]], %m1_in =
// CHECK-SAME:                 qstruct.circuit([[R0]] : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2>, i1, i1, i1 {
// CHECK-NEXT:         ^bb0([[R0_B:%[\w\d_]+]]: !qcore.qubit_reg<2>):
// CHECK-NEXT:             [[Q1:%[\w\d_]+]], [[Q2:%[\w\d_]+]] = qcore.unpack_qubit_reg([[R0_B]] : !qcore.qubit_reg<2>)
// CHECK-NEXT:             %m1 = qref.measure<X> ([[Q1]]) -> i1
// CHECK-NEXT:             %m2 = qref.measure<X> ([[Q2]]) -> i1
// CHECK-NEXT:             qstruct.yield [[R0_B]], %m1, %m2, %m1 : !qcore.qubit_reg<2>, i1, i1, i1
// CHECK-NEXT:         }
// CHECK-NEXT:         qstruct.yield [[R2_IN]], [[OUT1_IN:%[\w\d_]+]], [[OUT2_IN:%[\w\d_]+]], %m1_in
// CHECK-SAME:             : !qcore.qubit_reg<2>, i1, i1, i1
// CHECK-NEXT:     } {
// CHECK-NEXT:         [[R3_IN:%[\w\d_]+]] = qstruct.circuit([[R1]] : !qcore.qubit_reg<1>) -> !qcore.qubit_reg<1> {
// CHECK-NEXT:         ^bb0([[R1_B:%[\w\d_]+]]: !qcore.qubit_reg<1>):
// CHECK-NEXT:             [[Q3:%[\w\d_]+]] = qcore.unpack_qubit_reg([[R1_B]] : !qcore.qubit_reg<1>)
// CHECK-NEXT:             %m3 = qref.measure<Z> ([[Q3]]) -> i1
// CHECK-NEXT:             %m4 = qref.measure<Z> ([[Q3]]) -> i1
// CHECK-NEXT:             qref.reset<X> ([[Q3]])
// CHECK-NEXT:             [[D1:%[\w\d_]+]] = qec.detector(%m3, %m4)
// CHECK-NEXT:             qstruct.yield [[R1_B]] : !qcore.qubit_reg<1>
// CHECK-NEXT:         }
// CHECK-NEXT:         qstruct.yield [[R3_IN]] : !qcore.qubit_reg<1>
// CHECK-NEXT:     }
// CHECK-NEXT:     %z = scf.if %m1_out -> (i1) {
// CHECK-NEXT:         scf.yield %m1_out : i1
// CHECK-NEXT:     } else {
// CHECK-NEXT:         scf.yield %x0 : i1
// CHECK-NEXT:     }
// CHECK-NEXT:     %l = arith.constant 0 : index
// CHECK-NEXT:     %u = "test.op"() : () -> index
// CHECK-NEXT:     %step = arith.constant 1 : index
// CHECK-NEXT:     %f = arith.constant false
// CHECK-NEXT:     %h = scf.for %i = %l to %u step %step iter_args(%k = %z) -> (i1) {
// CHECK-NEXT:         %g = scf.while (%o = %f)  : (i1) -> i1 {
// CHECK-NEXT:             scf.condition(%f) %f : i1
// CHECK-NEXT:         } do {
// CHECK-NEXT:         ^bb0(%c: i1):
// CHECK-NEXT:             scf.yield %c : i1
// CHECK-NEXT:         }
// CHECK-NEXT:         scf.yield %g : i1
// CHECK-NEXT:     }
// CHECK-NEXT:     qstruct.output(%y0, %h : i64, i1)
// CHECK-NEXT:     qstruct.parallel<BOTTOM> -> {
// CHECK-NEXT:         [[R4_IN:%[\w\d_]+]] = qstruct.circuit([[R2]], [[OUT1]], [[OUT2]]
// CHECK-SAME:             : !qcore.qubit_reg<2>, i1, i1) -> !qcore.qubit_reg<2> {
// CHECK-NEXT:         ^bb1([[R2_B:%[\w\d_]+]]: !qcore.qubit_reg<2>, [[IN1:%[\w\d_]+]]: i1, [[IN2:%[\w\d_]+]]: i1):
// CHECK-NEXT:             [[Q4:%[\w\d_]+]], [[Q5:%[\w\d_]+]] = qcore.unpack_qubit_reg([[R2_B]] : !qcore.qubit_reg<2>)
// CHECK-NEXT:             %m5 = qref.measure<X> ([[Q4]]) -> i1
// CHECK-NEXT:             %m6 = qref.measure<X> ([[Q5]]) -> i1
// CHECK-NEXT:             [[D2:%[\w\d_]+]] = qec.detector<[0.0, 0.0]> ([[IN1]], [[IN2]], %m5, %m6)
// CHECK-NEXT:             qstruct.yield [[R2_B]] : !qcore.qubit_reg<2>
// CHECK-NEXT:         }
// CHECK-NEXT:         qstruct.yield
// CHECK-NEXT:     } {
// CHECK-NEXT:         [[R5_IN:%[\w\d_]+]] = qstruct.circuit([[R3]] : !qcore.qubit_reg<1>) -> !qcore.qubit_reg<1> {
// CHECK-NEXT:         ^bb1([[R3_B:%[\w\d_]+]]: !qcore.qubit_reg<1>):
// CHECK-NEXT:             [[Q6:%[\w\d_]+]] = qcore.unpack_qubit_reg([[R3_B]] : !qcore.qubit_reg<1>)
// CHECK-NEXT:             %m7 = qref.measure<X> ([[Q6]]) -> i1
// CHECK-NEXT:             [[D3:%[\w\d_]+]] = qec.detector(%m7)
// CHECK-NEXT:             qstruct.yield [[R3_B]] : !qcore.qubit_reg<1>
// CHECK-NEXT:         }
// CHECK-NEXT:         qstruct.yield
// CHECK-NEXT:     }
// CHECK-NEXT: }
