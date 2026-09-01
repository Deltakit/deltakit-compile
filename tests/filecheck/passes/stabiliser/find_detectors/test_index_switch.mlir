// RUN: deltakit_compile compile-passes --test-mode %s -p find-detectors -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK: builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit

    %state0 = stab.state.make (%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>

    %i = "test.op"() : () -> index

    %state1 = scf.index_switch %i -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK:      %state1, [[OUT1:%[0-9]+]], [[OUT2:%[0-9]+]] = scf.index_switch %i
// CHECK-SAME:              -> !stab.state<1 x !qcore.qubit, [Z0]>, i1, i1
    case 1 {
// CHECK-NEXT: case 1 {
        %state1_case1 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
                                            -> !stab.state<1 x !qcore.qubit, [Z0]>
          with (%q0_b : !qcore.qubit), () {
            qref.reset<Z> (%q0_b)
            stab.yield []
          } [<+:>{I -> Z0}]
// CHECK-NEXT:   %state1_case1 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                       -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:     with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%q0_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{I -> Z0}]
// CHECK-NEXT:   [[PAD1:%[0-9]+]] = arith.constant false

        scf.yield %state1_case1 : !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:   scf.yield %state1_case1, [[PAD1]], [[PAD1]] : !stab.state<1 x !qcore.qubit, [Z0]>, i1, i1
    }
    case 2 {
// CHECK-NEXT: }
// CHECK-NEXT: case 2 {
        %state1_case2 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
                                            -> !stab.state<1 x !qcore.qubit, [Z0]>
          with (%q0_b : !qcore.qubit), () {
            %m0 = qref.measure<Z> (%q0_b) -> i1
            stab.yield [%m0 : i1]
          } [<+:0>{I -> Z0}]
// CHECK-NEXT:   %state1_case2, [[OUT1_C2:%[0-9]+]] = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
// CHECK-SAME:                                     -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:     with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:       %m0 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:       stab.yield [%m0 : i1] %m0 : i1
// CHECK-NEXT:     } [<+:0>{I -> Z0}]
// CHECK-NEXT:   [[PAD2:%[0-9]+]] = arith.constant false

        scf.yield %state1_case2 : !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:   scf.yield %state1_case2, [[OUT1_C2]], [[PAD2]] : !stab.state<1 x !qcore.qubit, [Z0]>, i1, i1
    }
    default {
// CHECK-NEXT: }
// CHECK-NEXT: default {
        %state1_default = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, []>
                                              -> !stab.state<1 x !qcore.qubit, [Z0]>
          with (%q0_b : !qcore.qubit), () {
            %m1 = qref.measure<Z> (%q0_b) -> i1
            %m2 = qref.measure<Z> (%q0_b) -> i1
            stab.yield [%m1, %m2 : i1, i1]
          } [<+:0, 1>{I -> Z0}]
// CHECK-NEXT:   %state1_default, [[OUT1_D:%[0-9]+]], [[OUT2_D:%[0-9]+]] = stab.circuit %state0
// CHECK-SAME:            : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:     with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:       %m1 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:       %m2 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:       stab.yield [%m1, %m2 : i1, i1] %m1, %m2 : i1, i1
// CHECK-NEXT:     } [<+:0, 1>{I -> Z0}]

        scf.yield %state1_default : !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:   scf.yield %state1_default, [[OUT1_D]], [[OUT2_D]] : !stab.state<1 x !qcore.qubit, [Z0]>, i1, i1
    }
// CHECK-NEXT: }
}
// CHECK-NEXT: }
