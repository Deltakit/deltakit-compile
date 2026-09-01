// RUN: deltakit_compile compile-passes %s -p expand-states -O %t --test-mode && filecheck %s --input-file %t

builtin.module {
  %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, [Z0, X1 X2 X4, X1, X2, Y3, X4]>
  %7 = stab.state.permute<[4, 0, 2, 3, 1]> (%s : !stab.state<5 x !qcore.qubit, [Z0, X1 X2 X4, X1, X2, Y3, X4]>) -> !stab.state<5 x !qcore.qubit, [X0 X1 X2, X0, X1, X2, Y3, Z4]>
  %r2, %q0, %q1 = stab.state.split(%7 : !stab.state<5 x !qcore.qubit, [X0 X1 X2, X0, X1, X2, Y3, Z4]>) -> !stab.state<3 x !qcore.qubit, [X0 X1 X2, X0, X1, X2]>, !stab.state<1 x !qcore.qubit, [Y0]>, !stab.state<1 x !qcore.qubit, [Z0]>
  %8 = stab.state.concatenate(%q0, %r2 : !stab.state<1 x !qcore.qubit, [Y0]>, !stab.state<3 x !qcore.qubit, [X0 X1 X2, X0, X1, X2]>) -> !stab.state<4 x !qcore.qubit, [Y0, X1 X2 X3, X1, X2, X3]>
  %9 = stab.circuit %8 : !stab.state<4 x !qcore.qubit, [Y0, X1 X2 X3, X1, X2, X3]> -> !stab.state<4 x !qcore.qubit, [Y0, X1 X2 X3, X1, X2, X3]>
    with (%a, %b, %c, %d : !qcore.qubit), (){
      "test.op"(%a, %b, %c, %d) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
      stab.yield []
    } [<-:>{Y0 -> X1}]
  %q0_1, %r2_1 = stab.state.split(%9 : !stab.state<4 x !qcore.qubit, [Y0, X1 X2 X3, X1, X2, X3]>) -> !stab.state<1 x !qcore.qubit, [Y0]>, !stab.state<3 x !qcore.qubit, [X0 X1 X2, X0, X1, X2]>
  %10 = stab.state.concatenate(%r2_1, %q0_1, %q1 : !stab.state<3 x !qcore.qubit, [X0 X1 X2, X0, X1, X2]>, !stab.state<1 x !qcore.qubit, [Y0]>, !stab.state<1 x !qcore.qubit, [Z0]>) -> !stab.state<5 x !qcore.qubit, [X0 X1 X2, X0, X1, X2, Y3, Z4]>
  %11 = stab.state.permute<[4, 3, 2, 1, 0]> (%10 : !stab.state<5 x !qcore.qubit, [X0 X1 X2, X0, X1, X2, Y3, Z4]>) -> !stab.state<5 x !qcore.qubit, [Z0, Y1, X2 X3 X4, X2, X3, X4]>
  "test.op"(%11) : (!stab.state<5 x !qcore.qubit, [Z0, Y1, X2 X3 X4, X2, X3, X4]>) -> ()
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, [Z0, X1 X2 X4, X1, X2, Y3, X4]>
// CHECK-NEXT:    %0 = stab.circuit %s : !stab.state<5 x !qcore.qubit, [Z0, X1 X2 X4, X1, X2, Y3, X4]> -> !stab.state<5 x !qcore.qubit, [Z0, X1 X2 X4, X1, X2, Y3, X4]>
// CHECK-NEXT:      with (%1, %b, %d, %a, %c : !qcore.qubit), (){
// CHECK-NEXT:        "test.op"(%a, %b, %c, %d) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:        stab.yield []
// CHECK-NEXT:      } [<+:>{Z0 -> Z0}, <-:>{Y3 -> X1}]
// CHECK-NEXT:    %1 = stab.state.permute<[0, 4, 2, 1, 3]> (%0 : !stab.state<5 x !qcore.qubit, [Z0, X1 X2 X4, X1, X2, Y3, X4]>) -> !stab.state<5 x !qcore.qubit, [Z0, Y1, X2 X3 X4, X2, X3, X4]>
// CHECK-NEXT:    "test.op"(%1) : (!stab.state<5 x !qcore.qubit, [Z0, Y1, X2 X3 X4, X2, X3, X4]>) -> ()
// CHECK-NEXT:  }
