// RUN: deltakit_compile compile-passes %s -p expand-states -O %t --test-mode && filecheck %s --input-file %t


builtin.module {
  %q0 = qcore.alloc_qubit -> !qcore.qubit
  %q0_1 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
  %q1 = stab.state.concatenate(%q0_1 : !stab.state<1 x !qcore.qubit, []>) -> !stab.state<1 x !qcore.qubit, []>
  %q1_1 = stab.circuit %q1 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
    with (%q0_b : !qcore.qubit), (){
      qref.gate<#qcore.gate.x> (%q0_b)
      stab.yield []
    }
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:    %q0_1 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:    %q1 = stab.circuit %q0_1 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:        qref.gate<#qcore.gate.x> (%q0_b)
// CHECK-NEXT:        stab.yield []
// CHECK-NEXT:      }
// CHECK-NEXT:  }

// ----
// CHECK-NEXT:  ----

builtin.module {
  %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
  %7 = stab.state.permute<[4, 0, 2, 3, 1]> (%s : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<5 x !qcore.qubit, []>
  %r2, %q0 = stab.state.split(%7 : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<4 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
  %8 = stab.state.concatenate(%r2, %q0 : !stab.state<4 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>) -> !stab.state<5 x !qcore.qubit, []>
  %9 = stab.circuit %8 : !stab.state<5 x !qcore.qubit, []> -> !stab.state<5 x !qcore.qubit, []>
    with (%a, %b, %c, %d, %e : !qcore.qubit), (){
      "test.op"(%a, %b, %c, %d, %e) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
      stab.yield []
    }
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:    %0 = stab.circuit %s : !stab.state<5 x !qcore.qubit, []> -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:      with (%e, %a, %c, %d, %b : !qcore.qubit), (){
// CHECK-NEXT:        "test.op"(%a, %b, %c, %d, %e) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:        stab.yield []
// CHECK-NEXT:      }
// CHECK-NEXT:  }


// ----
// CHECK-NEXT:  ----

builtin.module {
  %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
  %7 = stab.state.permute<[4, 0, 2, 3, 1]> (%s : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<5 x !qcore.qubit, []>
  %r2, %q0 = stab.state.split(%7 : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<4 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
  %8 = stab.state.concatenate(%q0, %r2 : !stab.state<1 x !qcore.qubit, []>, !stab.state<4 x !qcore.qubit, []>) -> !stab.state<5 x !qcore.qubit, []>
  %9 = stab.circuit %8 : !stab.state<5 x !qcore.qubit, []> -> !stab.state<5 x !qcore.qubit, []>
    with (%a, %b, %c, %d, %e : !qcore.qubit), (){
      "test.op"(%a, %b, %c, %d, %e) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
      stab.yield []
    }
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:    %0 = stab.circuit %s : !stab.state<5 x !qcore.qubit, []> -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:      with (%a, %b, %d, %e, %c : !qcore.qubit), (){
// CHECK-NEXT:        "test.op"(%a, %b, %c, %d, %e) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:        stab.yield []
// CHECK-NEXT:      }
// CHECK-NEXT:  }

// ----
// CHECK-NEXT:  ----

builtin.module {
  %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
  %7 = stab.state.permute<[4, 0, 2, 3, 1]> (%s : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<5 x !qcore.qubit, []>
  %r2, %q0, %q1 = stab.state.split(%7 : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<3 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
  %8 = stab.state.concatenate(%q0, %r2 : !stab.state<1 x !qcore.qubit, []>, !stab.state<3 x !qcore.qubit, []>) -> !stab.state<4 x !qcore.qubit, []>
  %9 = stab.circuit %8 : !stab.state<4 x !qcore.qubit, []> -> !stab.state<4 x !qcore.qubit, []>
    with (%a, %b, %c, %d : !qcore.qubit), (){
      "test.op"(%a, %b, %c, %d) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
      stab.yield []
    }
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:    %0 = stab.state.permute<[4, 1, 3, 0, 2]> (%s : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:    %1, %q1 = stab.state.split(%0 : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<4 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:    %2 = stab.circuit %1 : !stab.state<4 x !qcore.qubit, []> -> !stab.state<4 x !qcore.qubit, []>
// CHECK-NEXT:      with (%a, %b, %c, %d : !qcore.qubit), (){
// CHECK-NEXT:        "test.op"(%a, %b, %c, %d) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:        stab.yield []
// CHECK-NEXT:      }
// CHECK-NEXT:  }


// ----
// CHECK-NEXT:  ----

builtin.module {
  %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
  %r2, %q0, %q1 = stab.state.split(%s : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<3 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
  %8 = stab.state.concatenate(%r2, %q0 : !stab.state<3 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>) -> !stab.state<4 x !qcore.qubit, []>
  %9 = stab.circuit %8 : !stab.state<4 x !qcore.qubit, []> -> !stab.state<4 x !qcore.qubit, []>
    with (%a, %b, %c, %d : !qcore.qubit), (){
      "test.op"(%a, %b, %c, %d) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
      stab.yield []
    }
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:    %0, %q1 = stab.state.split(%s : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<4 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:    %1 = stab.circuit %0 : !stab.state<4 x !qcore.qubit, []> -> !stab.state<4 x !qcore.qubit, []>
// CHECK-NEXT:      with (%a, %b, %c, %d : !qcore.qubit), (){
// CHECK-NEXT:        "test.op"(%a, %b, %c, %d) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:        stab.yield []
// CHECK-NEXT:      }
// CHECK-NEXT:  }


// ----
// CHECK-NEXT:  ----

builtin.module {
  %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
  %7 = stab.state.permute<[4, 0, 2, 3, 1]> (%s : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<5 x !qcore.qubit, []>
  %r2, %q0, %q1 = stab.state.split(%7 : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<3 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
  %8 = stab.state.concatenate(%q0, %r2 : !stab.state<1 x !qcore.qubit, []>, !stab.state<3 x !qcore.qubit, []>) -> !stab.state<4 x !qcore.qubit, []>
  %9 = stab.circuit %8 : !stab.state<4 x !qcore.qubit, []> -> !stab.state<4 x !qcore.qubit, []>
    with (%a, %b, %c, %d : !qcore.qubit), (){
      "test.op"(%a, %b, %c, %d) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
      stab.yield []
    }
  %q0_1, %r2_1 = stab.state.split(%9 : !stab.state<4 x !qcore.qubit, []>) -> !stab.state<1 x !qcore.qubit, []>, !stab.state<3 x !qcore.qubit, []>
  %10 = stab.state.concatenate(%r2_1, %q0_1, %q1 : !stab.state<3 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>) -> !stab.state<5 x !qcore.qubit, []>
  "test.op"(%10) : (!stab.state<5 x !qcore.qubit, []>) -> ()
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:    %0 = stab.circuit %s : !stab.state<5 x !qcore.qubit, []> -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:      with (%1, %b, %d, %a, %c : !qcore.qubit), (){
// CHECK-NEXT:        "test.op"(%a, %b, %c, %d) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:        stab.yield []
// CHECK-NEXT:      } []
// CHECK-NEXT:    %1 = stab.state.permute<[4, 0, 2, 3, 1]> (%0 : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:    "test.op"(%1) : (!stab.state<5 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:  }


// ----
// CHECK-NEXT:  ----

builtin.module {
  %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
  %A = "test.op"() : () -> i32
  %r2, %q0, %q1 = stab.state.split(%s : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<3 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
  %8 = stab.state.concatenate(%q0, %r2 : !stab.state<1 x !qcore.qubit, []>, !stab.state<3 x !qcore.qubit, []>) -> !stab.state<4 x !qcore.qubit, []>
  %9, %A2, %B2 = stab.circuit %8 : !stab.state<4 x !qcore.qubit, []> -> !stab.state<4 x !qcore.qubit, []>
    with (%a, %b, %c, %d : !qcore.qubit), (%iA = %A : i32){
      "test.op"(%a, %b, %c, %d) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
      %B = "test.op"() : () -> i64
      stab.yield [] %iA, %B : i32, i64
    }
  %q0_1, %r2_1 = stab.state.split(%9 : !stab.state<4 x !qcore.qubit, []>) -> !stab.state<1 x !qcore.qubit, []>, !stab.state<3 x !qcore.qubit, []>
  %10 = stab.state.concatenate(%r2_1, %q0_1, %q1 : !stab.state<3 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>) -> !stab.state<5 x !qcore.qubit, []>
  "test.op"(%10) : (!stab.state<5 x !qcore.qubit, []>) -> ()
  "test.op"(%A2, %B2) : (i32, i64) -> ()
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:    %A = "test.op"() : () -> i32
// CHECK-NEXT:    %0, %A2, %B2 = stab.circuit %s : !stab.state<5 x !qcore.qubit, []> -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:      with (%b, %c, %d, %a, %1 : !qcore.qubit), (%iA = %A : i32){
// CHECK-NEXT:        "test.op"(%a, %b, %c, %d) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:        %B = "test.op"() : () -> i64
// CHECK-NEXT:        stab.yield [] %iA, %B : i32, i64
// CHECK-NEXT:      } []
// CHECK-NEXT:    "test.op"(%0) : (!stab.state<5 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:    "test.op"(%A2, %B2) : (i32, i64) -> ()
// CHECK-NEXT:  }


// ----
// CHECK-NEXT:  ----

builtin.module {
  %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
  %7 = stab.state.permute<[4, 0, 2, 3, 1]> (%s : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<5 x !qcore.qubit, []>
  %r2, %q0, %q1 = stab.state.split(%7 : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<3 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
  %8 = stab.state.concatenate(%q0, %r2 : !stab.state<1 x !qcore.qubit, []>, !stab.state<3 x !qcore.qubit, []>) -> !stab.state<4 x !qcore.qubit, []>
  %9 = stab.circuit %8 : !stab.state<4 x !qcore.qubit, []> -> !stab.state<4 x !qcore.qubit, []>
    with (%a, %b, %c, %d : !qcore.qubit), (){
      "test.op"(%a, %b, %c, %d) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
      stab.yield []
    }
  %q0_1, %r2_1 = stab.state.split(%9 : !stab.state<4 x !qcore.qubit, []>) -> !stab.state<1 x !qcore.qubit, []>, !stab.state<3 x !qcore.qubit, []>
  %10 = stab.state.concatenate(%r2_1, %q0_1, %q1 : !stab.state<3 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>) -> !stab.state<5 x !qcore.qubit, []>
  %11 = stab.state.permute<[4, 3, 2, 1, 0]> (%10 : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<5 x !qcore.qubit, []>
  "test.op"(%11) : (!stab.state<5 x !qcore.qubit, []>) -> ()
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:    %0 = stab.circuit %s : !stab.state<5 x !qcore.qubit, []> -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:      with (%1, %b, %d, %a, %c : !qcore.qubit), (){
// CHECK-NEXT:        "test.op"(%a, %b, %c, %d) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:        stab.yield []
// CHECK-NEXT:      } []
// CHECK-NEXT:    %1 = stab.state.permute<[0, 4, 2, 1, 3]> (%0 : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:    "test.op"(%1) : (!stab.state<5 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT:  ----

builtin.module {
  %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
  %7 = stab.state.permute<[4, 0, 2, 3, 1]> (%s : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<5 x !qcore.qubit, []>
  %8 = stab.circuit %7 : !stab.state<5 x !qcore.qubit, []> -> !stab.state<5 x !qcore.qubit, []>
    with (%a, %b, %c, %d, %e : !qcore.qubit), (){
      "test.op"(%a, %b, %c, %d, %e) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
      stab.yield []
    }
  "test.op"(%8) : (!stab.state<5 x !qcore.qubit, []>) -> ()
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %s = "test.op"() : () -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:    %0 = stab.circuit %s : !stab.state<5 x !qcore.qubit, []> -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:      with (%e, %a, %c, %d, %b : !qcore.qubit), (){
// CHECK-NEXT:        "test.op"(%a, %b, %c, %d, %e) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:        stab.yield []
// CHECK-NEXT:      }
// CHECK-NEXT:    %1 = stab.state.permute<[4, 0, 2, 3, 1]> (%0 : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<5 x !qcore.qubit, []>
// CHECK-NEXT:    "test.op"(%1) : (!stab.state<5 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT:  ----

builtin.module {
  %s, %t = "test.op"() : () -> (!stab.state<5 x !qcore.qubit, []>, !stab.state<5 x !qcore.qubit, []>)
  %s1 = stab.state.permute<[4, 0, 2, 3, 1]> (%s : !stab.state<5 x !qcore.qubit, []>) -> !stab.state<5 x !qcore.qubit, []>
  %ts = stab.state.concatenate(%t, %s1 : !stab.state<5 x !qcore.qubit, []>, !stab.state<5 x !qcore.qubit, []>) -> !stab.state<10 x !qcore.qubit, []>
  %ts1 = stab.circuit %ts : !stab.state<10 x !qcore.qubit, []> -> !stab.state<10 x !qcore.qubit, []>
  with (%ta, %tb, %tc, %td, %te, %sa, %sb, %sc, %sd, %se : !qcore.qubit), (){
    "test.op"(%ta, %tb, %tc, %td, %te, %sa, %sb, %sc, %sd, %se) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
    stab.yield []
  }
  "test.op"(%ts1) : (!stab.state<10 x !qcore.qubit, []>) -> ()
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %s, %t = "test.op"() : () -> (!stab.state<5 x !qcore.qubit, []>, !stab.state<5 x !qcore.qubit, []>)
// CHECK-NEXT:    %ts = stab.state.concatenate(%t, %s : !stab.state<5 x !qcore.qubit, []>, !stab.state<5 x !qcore.qubit, []>) -> !stab.state<10 x !qcore.qubit, []>
// CHECK-NEXT:    %ts1 = stab.circuit %ts : !stab.state<10 x !qcore.qubit, []> -> !stab.state<10 x !qcore.qubit, []>
// CHECK-NEXT:      with (%ta, %tb, %tc, %td, %te, %se, %sa, %sc, %sd, %sb : !qcore.qubit), (){
// CHECK-NEXT:        "test.op"(%ta, %tb, %tc, %td, %te, %sa, %sb, %sc, %sd, %se) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:        stab.yield []
// CHECK-NEXT:      }
// CHECK-NEXT:    %ts1_1 = stab.state.permute<[0, 1, 2, 3, 4, 9, 5, 7, 8, 6]> (%ts1 : !stab.state<10 x !qcore.qubit, []>) -> !stab.state<10 x !qcore.qubit, []>
// CHECK-NEXT:    "test.op"(%ts1_1) : (!stab.state<10 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:  }

// ----
// CHECK-NEXT: ----

builtin.module {
  %s = "test.op"() : () -> !stab.state<6 x !qcore.qubit, []>
  %x, %y, %z = "test.op"() : () -> (i1, i32, i64)
  %a, %b, %c = stab.state.split(%s : !stab.state<6 x !qcore.qubit, []>) -> !stab.state<2 x !qcore.qubit, []>, !stab.state<2 x !qcore.qubit, []>, !stab.state<2 x !qcore.qubit, []>
  %b1, %z2, %y2, %x2, %w2 = stab.circuit %b : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, []>
    with (%bqa, %bqb: !qcore.qubit), (%x1 = %x : i1, %y1 = %y : i32, %z1 = %z : i64){
      %w1 = "test.op"(%bqb, %x1, %z1, %y1, %bqb) : (!qcore.qubit, i1, i64, i32, !qcore.qubit) -> i1
      stab.yield [%x1 : i1] %z1, %y1, %x1, %w1 : i64, i32, i1, i1
    }
  "test.op"(%x2, %y2, %z2, %w2) : (i1, i32, i64, i1) -> ()
  %s1 = stab.state.concatenate(%c, %b1, %a : !stab.state<2 x !qcore.qubit, []>, !stab.state<2 x !qcore.qubit, []>, !stab.state<2 x !qcore.qubit, []>) -> !stab.state<6 x !qcore.qubit, []>
  "test.op"(%s1) : (!stab.state<6 x !qcore.qubit, []>) -> ()
}

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    %s = "test.op"() : () -> !stab.state<6 x !qcore.qubit, []>
// CHECK-NEXT:    %x, %y, %z = "test.op"() : () -> (i1, i32, i64)
// CHECK-NEXT:    %0, %z2, %y2, %x2, %w2 = stab.circuit %s : !stab.state<6 x !qcore.qubit, []> -> !stab.state<6 x !qcore.qubit, []>
// CHECK-NEXT:      with (%1, %2, %bqa, %bqb, %3, %4 : !qcore.qubit), (%x1 = %x : i1, %y1 = %y : i32, %z1 = %z : i64){
// CHECK-NEXT:        %w1 = "test.op"(%bqb, %x1, %z1, %y1, %bqb) : (!qcore.qubit, i1, i64, i32, !qcore.qubit) -> i1
// CHECK-NEXT:        stab.yield [%x1 : i1] %z1, %y1, %x1, %w1 : i64, i32, i1, i1
// CHECK-NEXT:      } []
// CHECK-NEXT:    "test.op"(%x2, %y2, %z2, %w2) : (i1, i32, i64, i1) -> ()
// CHECK-NEXT:    %s1 = stab.state.permute<[4, 5, 2, 3, 0, 1]> (%0 : !stab.state<6 x !qcore.qubit, []>) -> !stab.state<6 x !qcore.qubit, []>
// CHECK-NEXT:    "test.op"(%s1) : (!stab.state<6 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:  }
