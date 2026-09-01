// RUN: deltakit_compile compile-passes %s -p expand-states -O %t --test-mode && filecheck %s --input-file %t


builtin.module {
  %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
  %bool = "test.op"() : () -> i1
  %s1 = stab.state.permute<[4, 0, 2, 3, 1]> (%s : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<5 x !qcore.qubit, []>
  %s2 = scf.if %bool -> (!stab.state<5 x !qcore.qubit, []>)
  {
    %s2a = stab.circuit %s1 : !stab.state<5 x !qcore.qubit, []> -> !stab.state<5 x !qcore.qubit, []>
    with (%a, %b, %c, %d, %e : !qcore.qubit), (){
      "test.op"(%a, %b, %c, %d, %e) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
      stab.yield []
    }
    scf.yield %s2a : !stab.state<5 x !qcore.qubit, []>
  } else {
    %s2b = stab.circuit %s1 : !stab.state<5 x !qcore.qubit, []> -> !stab.state<5 x !qcore.qubit, []>
    with (%a, %b, %c, %d, %e : !qcore.qubit), (){
      "test.op"(%a, %b, %c, %d, %e) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
      stab.yield []
    }
    scf.yield %s2b : !stab.state<5 x !qcore.qubit, []>
  }
  "test.op"(%s2) : (!stab.state<5 x !qcore.qubit, []>) -> ()
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:    %bool = "test.op"() : () -> i1
// CHECK-NEXT:    %s1 = stab.state.permute<[4, 0, 2, 3, 1]> (%s : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:    %s2 = scf.if %bool -> (!stab.state<5 x !qcore.qubit, []>) {
// CHECK-NEXT:      %s2a = stab.circuit %s1 : !stab.state<5 x !qcore.qubit, []> -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:        with (%a, %b, %c, %d, %e : !qcore.qubit), (){
// CHECK-NEXT:          "test.op"(%a, %b, %c, %d, %e) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:          stab.yield []
// CHECK-NEXT:        }
// CHECK-NEXT:      scf.yield %s2a : !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:    } else {
// CHECK-NEXT:      %s2b = stab.circuit %s1 : !stab.state<5 x !qcore.qubit, []> -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:        with (%a, %b, %c, %d, %e : !qcore.qubit), (){
// CHECK-NEXT:          "test.op"(%a, %b, %c, %d, %e) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:          stab.yield []
// CHECK-NEXT:        }
// CHECK-NEXT:      scf.yield %s2b : !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:    }
// CHECK-NEXT:    "test.op"(%s2) : (!stab.state<5 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----


builtin.module {
  %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
  %t = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
  %a, %b = stab.state.split(%s : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<4 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
  %c, %d = stab.state.split(%t : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<4 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
  %bac = stab.state.concatenate(%a, %c : !stab.state<4 x !qcore.qubit, []>, !stab.state<4 x !qcore.qubit, []>) -> !stab.state<8 x !qcore.qubit, []>
  "test.op"(%bac) : (!stab.state<8 x !qcore.qubit, []>) -> ()
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:    %t = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:    %a, %b = stab.state.split(%s : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<4 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:    %c, %d = stab.state.split(%t : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<4 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:    %bac = stab.state.concatenate(%a, %c : !stab.state<4 x !qcore.qubit, []>, !stab.state<4 x !qcore.qubit, []>) -> !stab.state<8 x !qcore.qubit, []>
// CHECK-NEXT:    "test.op"(%bac) : (!stab.state<8 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:  }


// ----
// CHECK-NEXT: ----

builtin.module {
  %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
  %bool = "test.op"() : () -> i1
  %a, %b, %c, %d = stab.state.split(%s : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<2 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
  %s2 = scf.if %bool -> (!stab.state<5 x !qcore.qubit, []>)
  {
    %ac = stab.state.concatenate(%a, %c : !stab.state<2 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>) -> !stab.state<3 x !qcore.qubit, []>
    %s2a = stab.circuit %ac : !stab.state<3 x !qcore.qubit, []> -> !stab.state<3 x !qcore.qubit, []>
    with (%a1, %a2, %c1 : !qcore.qubit), (){
      "test.op"(%a1, %a2, %c1) : (!qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
      stab.yield []
    }
    scf.yield %s2a : !stab.state<3 x !qcore.qubit, []>
  } else {
    %ad = stab.state.concatenate(%a, %d : !stab.state<2 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>) -> !stab.state<3 x !qcore.qubit, []>
    %s2b = stab.circuit %ad : !stab.state<3 x !qcore.qubit, []> -> !stab.state<3 x !qcore.qubit, []>
    with (%a1, %a2, %d1 : !qcore.qubit), (){
      "test.op"(%a1, %a2, %d1) : (!qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
      stab.yield []
    }
    scf.yield %s2b : !stab.state<3 x !qcore.qubit, []>
  }
  "test.op"(%s2) : (!stab.state<5 x !qcore.qubit, []>) -> ()
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:    %bool = "test.op"() : () -> i1
// CHECK-NEXT:    %a, %b, %c, %d = stab.state.split(%s : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<2 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:    %s2 = scf.if %bool -> (!stab.state<5 x !qcore.qubit, []>) {
// CHECK-NEXT:      %ac = stab.state.concatenate(%a, %c : !stab.state<2 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>) -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:      %s2a = stab.circuit %ac : !stab.state<3 x !qcore.qubit, []> -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:        with (%a1, %a2, %c1 : !qcore.qubit), (){
// CHECK-NEXT:          "test.op"(%a1, %a2, %c1) : (!qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:          stab.yield []
// CHECK-NEXT:        }
// CHECK-NEXT:      scf.yield %s2a : !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:    } else {
// CHECK-NEXT:      %ad = stab.state.concatenate(%a, %d : !stab.state<2 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>) -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:      %s2b = stab.circuit %ad : !stab.state<3 x !qcore.qubit, []> -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:        with (%a1, %a2, %d1 : !qcore.qubit), (){
// CHECK-NEXT:          "test.op"(%a1, %a2, %d1) : (!qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:          stab.yield []
// CHECK-NEXT:        }
// CHECK-NEXT:      scf.yield %s2b : !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:    }
// CHECK-NEXT:    "test.op"(%s2) : (!stab.state<5 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:  }


// ----
// CHECK-NEXT: ----

builtin.module {
  %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
  %bool = "test.op"() : () -> i1
  %a, %b, %c, %d = stab.state.split(%s : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<2 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
  %e = scf.if %bool -> (!stab.state<1 x !qcore.qubit, []>)
  {
    %e1 = stab.circuit %c : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
    with (%c1 : !qcore.qubit), (){
      "test.op"(%c1) : (!qcore.qubit) -> ()
      stab.yield []
    }
    scf.yield %e1 : !stab.state<1 x !qcore.qubit, []>
  } else {
    %e2 = stab.circuit %d : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
    with (%d1 : !qcore.qubit), (){
      "test.op"(%d1) : (!qcore.qubit) -> ()
      stab.yield []
    }
    scf.yield %e2 : !stab.state<1 x !qcore.qubit, []>
  }
  "test.op"(%e) : (!stab.state<1 x !qcore.qubit, []>) -> ()
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:    %bool = "test.op"() : () -> i1
// CHECK-NEXT:    %a, %b, %c, %d = stab.state.split(%s : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<2 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:    %e = scf.if %bool -> (!stab.state<1 x !qcore.qubit, []>) {
// CHECK-NEXT:      %e1 = stab.circuit %c : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:        with (%c1 : !qcore.qubit), (){
// CHECK-NEXT:          "test.op"(%c1) : (!qcore.qubit) -> ()
// CHECK-NEXT:          stab.yield []
// CHECK-NEXT:        }
// CHECK-NEXT:      scf.yield %e1 : !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:    } else {
// CHECK-NEXT:      %e2 = stab.circuit %d : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:        with (%d1 : !qcore.qubit), (){
// CHECK-NEXT:          "test.op"(%d1) : (!qcore.qubit) -> ()
// CHECK-NEXT:          stab.yield []
// CHECK-NEXT:        }
// CHECK-NEXT:      scf.yield %e2 : !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:    }
// CHECK-NEXT:    "test.op"(%e) : (!stab.state<1 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:  }
