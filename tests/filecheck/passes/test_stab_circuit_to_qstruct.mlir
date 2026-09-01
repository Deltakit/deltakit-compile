// RUN: deltakit_compile compile-passes %s -p stab-circuit-to-qstruct -O %t --test-mode && filecheck %s --input-file %t

// Case: No input_args. Input state defined by stab.state.make.
// Expect: pass derives qubits from state.make, pre-packs them, converts to qstruct.circuit, and erases dead state.make.

builtin.module {
    %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
    %s0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>

    %c0 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, []>
                                -> !stab.state<2 x !qcore.qubit, []>
    with (%qb0, %qb1 : !qcore.qubit), () {
      stab.yield []
    }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT: }

// ----

// Case: Circuit body ops are preserved.
// Expect: side-effect-free ops inside the stab.circuit body are still present inside the
// lowered qstruct.circuit body.

builtin.module {
  %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %s0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>

  %c0 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, []>
                              -> !stab.state<2 x !qcore.qubit, []>
  with (%qb0, %qb1 : !qcore.qubit), () {
    "test.op"(%qb0) : (!qcore.qubit) -> ()
    "test.op"(%qb1) : (!qcore.qubit) -> ()
    stab.yield []
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:   %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %s0 = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
// CHECK-NEXT:   %c0 = qstruct.circuit(%s0 : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
// CHECK-NEXT:   ^bb0(%0: !qcore.qubit_reg<2>):
// CHECK-NEXT:     %qb0, %qb1 = qcore.unpack_qubit_reg(%{{.*}} : !qcore.qubit_reg<2>)
// CHECK-NEXT:     "test.op"(%qb0) : (!qcore.qubit) -> ()
// CHECK-NEXT:     "test.op"(%qb1) : (!qcore.qubit) -> ()
// CHECK-NEXT:     %1 = qcore.pack_qubit_reg(%qb0, %qb1) -> !qcore.qubit_reg<2>
// CHECK-NEXT:     qstruct.yield %1 : !qcore.qubit_reg<2>
// CHECK-NEXT:   }
// CHECK-NEXT: }

// ----


// Case: Input state flows through stab.state.cast before stab.circuit.
// Expect: pass walks through the cast to recover qubits, converts to qstruct.circuit,
// and erases the now-dead cast + state.make.

builtin.module {
  %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %s0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
  // state.cast may only remove flow states, not add them. This is a no-op cast.
  %s1 = stab.state.cast(%s0) !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, []>

  %c0 = stab.circuit %s1 : !stab.state<2 x !qcore.qubit, []>
                              -> !stab.state<2 x !qcore.qubit, []>
  with (%qb0, %qb1 : !qcore.qubit), () {
    // Suppress DCE
    "test.op"(%qb0, %qb1) : (!qcore.qubit, !qcore.qubit) -> ()
    stab.yield []
  }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:   %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %s0 = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
// CHECK-NEXT:   %c0 = qstruct.circuit(%s0 : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
// CHECK-NEXT:   ^bb0(%0: !qcore.qubit_reg<2>):
// CHECK-NEXT:     %qb0, %qb1 = qcore.unpack_qubit_reg(%0 : !qcore.qubit_reg<2>)
// CHECK-NEXT:     "test.op"(%qb0, %qb1) : (!qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:     %1 = qcore.pack_qubit_reg(%qb0, %qb1) -> !qcore.qubit_reg<2>
// CHECK-NEXT:     qstruct.yield %1 : !qcore.qubit_reg<2>
// CHECK-NEXT:   }
// CHECK-NEXT: }

// ----

// Case: stab circuit with some flows attached.
// Expect: same as above, flows not recorded on qstruct op.

builtin.module {
  %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %state0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>

  %state1 = stab.circuit %state0 : !stab.state<2 x !qcore.qubit, []>
                                  -> !stab.state<2 x !qcore.qubit, [X0, Z1]>
    with (%qb0, %qb1 : !qcore.qubit), () {
      // Suppress DCE
      "test.op"(%qb0, %qb1) : (!qcore.qubit, !qcore.qubit) -> ()
      stab.yield []
    } [<+:>{I -> X0}, <+:>{I -> Z1}]
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:   %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %state0 = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
// CHECK-NEXT:   %state1 = qstruct.circuit(%state0 : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
// CHECK-NEXT:   ^bb0(%0: !qcore.qubit_reg<2>):
// CHECK-NEXT:     %qb0, %qb1 = qcore.unpack_qubit_reg(%0 : !qcore.qubit_reg<2>)
// CHECK-NEXT:     "test.op"(%qb0, %qb1) : (!qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:     %1 = qcore.pack_qubit_reg(%qb0, %qb1) -> !qcore.qubit_reg<2>
// CHECK-NEXT:     qstruct.yield %1 : !qcore.qubit_reg<2>
// CHECK-NEXT:   }
// CHECK-NEXT: }

// ----


// Case: Circuit has non-qubit input/output args.
// Expect: lowering threads the extra operand through qstruct.circuit, keeps its type,
// and preserves the yielded extra result.

builtin.module {
  %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %s0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
  %flag = arith.constant true

  %s1, %out = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, []>
                             -> !stab.state<2 x !qcore.qubit, []>
  with (%qb0, %qb1 : !qcore.qubit), (%in = %flag : i1) {
    // Preserve/forward the non-qubit arg.
    stab.yield [] %in : i1
  }

  // Keep results alive so DCE can't erase the boundary rewriting we're testing.
  qstruct.output(%out : i1)
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:   %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %s0 = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
// CHECK-NEXT:   %flag = arith.constant true
// CHECK-NEXT:   %0, %out = qstruct.circuit(%s0, %flag : !qcore.qubit_reg<2>, i1) -> !qcore.qubit_reg<2>, i1 {
// CHECK-NEXT:   ^bb0(%1: !qcore.qubit_reg<2>, %in: i1):
// CHECK-NEXT:     %qb0, %qb1 = qcore.unpack_qubit_reg(%1 : !qcore.qubit_reg<2>)
// CHECK-NEXT:     %2 = qcore.pack_qubit_reg(%qb0, %qb1) -> !qcore.qubit_reg<2>
// CHECK-NEXT:     qstruct.yield %2, %in : !qcore.qubit_reg<2>, i1
// CHECK-NEXT:   }
// CHECK-NEXT:   qstruct.output(%out : i1)
// CHECK-NEXT: }

// ----

// Case: scf.if statement (simple case)

builtin.module {
  %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %state0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
  %state1 = stab.state.make(%q1 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
  %b = arith.constant true

  %state2 = scf.if %b -> (!stab.state<1 x !qcore.qubit, []>) {
    scf.yield %state0 : !stab.state<1 x !qcore.qubit, []>
  } else {
    scf.yield %state1 : !stab.state<1 x !qcore.qubit, []>
  }

  // Suppress DCE
  stab.circuit %state2 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
    with (%qb0 : !qcore.qubit), () {
      "test.op"(%qb0) : (!qcore.qubit) -> ()
      stab.yield []
    }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:   %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %state0 = qcore.pack_qubit_reg(%q0) -> !qcore.qubit_reg<1>
// CHECK-NEXT:   %state1 = qcore.pack_qubit_reg(%q1) -> !qcore.qubit_reg<1>
// CHECK-NEXT:   %b = arith.constant true
// CHECK-NEXT:   %state2 = scf.if %b -> (!qcore.qubit_reg<1>) {
// CHECK-NEXT:     scf.yield %state0 : !qcore.qubit_reg<1>
// CHECK-NEXT:   } else {
// CHECK-NEXT:     scf.yield %state1 : !qcore.qubit_reg<1>
// CHECK-NEXT:   }
// CHECK-NEXT:   %0 = qstruct.circuit(%state2 : !qcore.qubit_reg<1>) -> !qcore.qubit_reg<1> {
// CHECK-NEXT:   ^bb0(%1: !qcore.qubit_reg<1>):
// CHECK-NEXT:     %qb0 = qcore.unpack_qubit_reg(%1 : !qcore.qubit_reg<1>)
// CHECK-NEXT:     "test.op"(%qb0) : (!qcore.qubit) -> ()
// CHECK-NEXT:     %2 = qcore.pack_qubit_reg(%qb0) -> !qcore.qubit_reg<1>
// CHECK-NEXT:     qstruct.yield %2 : !qcore.qubit_reg<1>
// CHECK-NEXT:   }
// CHECK-NEXT: }

// ----

// Case: scf.if statement (more complex case)

builtin.module {
  %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %state0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
  %b0 = arith.constant true

  %state1, %b1 = scf.if %b0 -> (!stab.state<2 x !qcore.qubit, []>, i1) {
    %if_state0, %if0_b = stab.circuit %state0 : !stab.state<2 x !qcore.qubit, []>
                                             -> !stab.state<2 x !qcore.qubit, []>
    with (%qb0, %qb1 : !qcore.qubit), () {
      "test.op"(%qb0) : (!qcore.qubit) -> ()
      %inner_if0_b = "test.op"(%qb1) : (!qcore.qubit) -> (i1)
      stab.yield [] %inner_if0_b : i1
    }
    scf.yield %if_state0, %if0_b : !stab.state<2 x !qcore.qubit, []>, i1
  } else {
    %if_state1, %if1_b = stab.circuit %state0 : !stab.state<2 x !qcore.qubit, []>
                                             -> !stab.state<2 x !qcore.qubit, []>
    with (%qb0, %qb1 : !qcore.qubit), () {
      "test.op"(%qb0) : (!qcore.qubit) -> ()
      %inner_if1_b = "test.op"(%qb1) : (!qcore.qubit) -> (i1)
      stab.yield [] %inner_if1_b : i1
    }
    scf.yield %if_state1, %if1_b : !stab.state<2 x !qcore.qubit, []>, i1
  }

  %state2 = stab.circuit %state1 : !stab.state<2 x !qcore.qubit, []>
                                -> !stab.state<2 x !qcore.qubit, [X0, Z1]>
    with (%qb0, %qb1 : !qcore.qubit), () {
      "test.op"(%qb0) : (!qcore.qubit) -> ()
      stab.yield []
    }
  [<+:>{I -> X0}, <+:>{I -> Z1}]
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:   %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %state0 = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
// CHECK-NEXT:   %b0 = arith.constant true
// CHECK-NEXT:   %state1, %b1 = scf.if %b0 -> (!qcore.qubit_reg<2>, i1) {
// CHECK-NEXT:     %if_state0, %if0_b = qstruct.circuit(%state0 : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2>, i1 {
// CHECK-NEXT:     ^bb0(%0: !qcore.qubit_reg<2>):
// CHECK-NEXT:       %qb0, %qb1 = qcore.unpack_qubit_reg(%0 : !qcore.qubit_reg<2>)
// CHECK-NEXT:       "test.op"(%qb0) : (!qcore.qubit) -> ()
// CHECK-NEXT:       %inner_if0_b = "test.op"(%qb1) : (!qcore.qubit) -> i1
// CHECK-NEXT:       %1 = qcore.pack_qubit_reg(%qb0, %qb1) -> !qcore.qubit_reg<2>
// CHECK-NEXT:       qstruct.yield %1, %inner_if0_b : !qcore.qubit_reg<2>, i1
// CHECK-NEXT:     }
// CHECK-NEXT:     scf.yield %if_state0, %if0_b : !qcore.qubit_reg<2>, i1
// CHECK-NEXT:   } else {
// CHECK-NEXT:     %if_state1, %if1_b = qstruct.circuit(%state0 : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2>, i1 {
// CHECK-NEXT:     ^bb0(%0: !qcore.qubit_reg<2>):
// CHECK-NEXT:       %qb0, %qb1 = qcore.unpack_qubit_reg(%0 : !qcore.qubit_reg<2>)
// CHECK-NEXT:       "test.op"(%qb0) : (!qcore.qubit) -> ()
// CHECK-NEXT:       %inner_if1_b = "test.op"(%qb1) : (!qcore.qubit) -> i1
// CHECK-NEXT:       %1 = qcore.pack_qubit_reg(%qb0, %qb1) -> !qcore.qubit_reg<2>
// CHECK-NEXT:       qstruct.yield %1, %inner_if1_b : !qcore.qubit_reg<2>, i1
// CHECK-NEXT:     }
// CHECK-NEXT:     scf.yield %if_state1, %if1_b : !qcore.qubit_reg<2>, i1
// CHECK-NEXT:   }
// CHECK-NEXT:   %state2 = qstruct.circuit(%state1 : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
// CHECK-NEXT:   ^bb0(%0: !qcore.qubit_reg<2>):
// CHECK-NEXT:     %qb0, %qb1 = qcore.unpack_qubit_reg(%0 : !qcore.qubit_reg<2>)
// CHECK-NEXT:     "test.op"(%qb0) : (!qcore.qubit) -> ()
// CHECK-NEXT:     %1 = qcore.pack_qubit_reg(%qb0, %qb1) -> !qcore.qubit_reg<2>
// CHECK-NEXT:     qstruct.yield %1 : !qcore.qubit_reg<2>
// CHECK-NEXT:   }
// CHECK-NEXT: }

// ----

// Case: scf.index_switch statement

builtin.module {
  %q0 = qcore.alloc_qubit -> !qcore.qubit
  %state0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
  %index = arith.constant 0 : index

  %state1 = scf.index_switch %index -> !stab.state<1 x !qcore.qubit, []>
  case 0 {
    scf.yield %state0 : !stab.state<1 x !qcore.qubit, []>
  }
  default {
    scf.yield %state0 : !stab.state<1 x !qcore.qubit, []>
  }

  // Suppress DCE
  %state2 = stab.circuit %state1 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
    with (%qb0 : !qcore.qubit), () {
      "test.op"(%qb0) : (!qcore.qubit) -> ()
      stab.yield []
    }
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:   %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:   %state0 = qcore.pack_qubit_reg(%q0) -> !qcore.qubit_reg<1>
// CHECK-NEXT:   %index = arith.constant 0 : index
// CHECK-NEXT:   %state1 = scf.index_switch %index -> !qcore.qubit_reg<1>
// CHECK-NEXT:   case 0 {
// CHECK-NEXT:     scf.yield %state0 : !qcore.qubit_reg<1>
// CHECK-NEXT:   }
// CHECK-NEXT:   default {
// CHECK-NEXT:     scf.yield %state0 : !qcore.qubit_reg<1>
// CHECK-NEXT:   }
// CHECK-NEXT:   %state2 = qstruct.circuit(%state1 : !qcore.qubit_reg<1>) -> !qcore.qubit_reg<1> {
// CHECK-NEXT:   ^bb0(%0: !qcore.qubit_reg<1>):
// CHECK-NEXT:     %qb0 = qcore.unpack_qubit_reg(%0 : !qcore.qubit_reg<1>)
// CHECK-NEXT:     "test.op"(%qb0) : (!qcore.qubit) -> ()
// CHECK-NEXT:     %1 = qcore.pack_qubit_reg(%qb0) -> !qcore.qubit_reg<1>
// CHECK-NEXT:     qstruct.yield %1 : !qcore.qubit_reg<1>
// CHECK-NEXT:   }
// CHECK-NEXT: }

// ----

// Case: qstruct.parallel statement

builtin.module {
  %q0, %q1, %q2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
  %o0, %o1 = qstruct.parallel<BOTTOM> -> i1, i1 {
    %state0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
    %state1, %i3 = stab.circuit %state0 : !stab.state<2 x !qcore.qubit, []>
                                       -> !stab.state<2 x !qcore.qubit, []>
      with (%qb0, %qb1 : !qcore.qubit), () {
        %i2 = qstruct.parallel<TOP> -> i1 {
          %i1 = qref.measure<X> (%qb0) -> i1
          qstruct.yield %i1 : i1
        } {
          qref.gate<#qcore.gate.x>(%qb1)
          qstruct.yield
        }
        stab.yield [] %i2 : i1
      }
    qstruct.yield %i3 : i1
  } {
    %state2 = stab.state.make(%q2 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
    %state3, %i5 = stab.circuit %state2 : !stab.state<1 x !qcore.qubit, []>
                                       -> !stab.state<1 x !qcore.qubit, []>
      with (%qb2 : !qcore.qubit), () {
        %i4 = qref.measure<X> (%qb2) -> i1
        stab.yield [] %i4 : i1
      }
    qstruct.yield %i5 : i1
  }
  qstruct.output(%o0, %o1 : i1, i1)
}

// CHECK-LABEL: builtin.module {
// CHECK-NEXT:   %q0, %q1, %q2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %o0, %o1 = qstruct.parallel<BOTTOM> -> i1, i1 {
// CHECK-NEXT:     %state0 = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
// CHECK-NEXT:     %0, %i3 = qstruct.circuit(%state0 : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2>, i1 {
// CHECK-NEXT:     ^bb0(%1: !qcore.qubit_reg<2>):
// CHECK-NEXT:       %qb0, %qb1 = qcore.unpack_qubit_reg(%1 : !qcore.qubit_reg<2>)
// CHECK-NEXT:       %i2 = qstruct.parallel<TOP> -> i1 {
// CHECK-NEXT:         %i1 = qref.measure<X> (%qb0) -> i1
// CHECK-NEXT:         qstruct.yield %i1 : i1
// CHECK-NEXT:       } {
// CHECK-NEXT:         qref.gate<#qcore.gate.x> (%qb1)
// CHECK-NEXT:         qstruct.yield
// CHECK-NEXT:       }
// CHECK-NEXT:       %2 = qcore.pack_qubit_reg(%qb0, %qb1) -> !qcore.qubit_reg<2>
// CHECK-NEXT:       qstruct.yield %2, %i2 : !qcore.qubit_reg<2>, i1
// CHECK-NEXT:     }
// CHECK-NEXT:     qstruct.yield %i3 : i1
// CHECK-NEXT:   } {
// CHECK-NEXT:     %state2 = qcore.pack_qubit_reg(%q2) -> !qcore.qubit_reg<1>
// CHECK-NEXT:     %1, %i5 = qstruct.circuit(%state2 : !qcore.qubit_reg<1>) -> !qcore.qubit_reg<1>, i1 {
// CHECK-NEXT:     ^bb0(%2: !qcore.qubit_reg<1>):
// CHECK-NEXT:       %qb2 = qcore.unpack_qubit_reg(%2 : !qcore.qubit_reg<1>)
// CHECK-NEXT:       %i4 = qref.measure<X> (%qb2) -> i1
// CHECK-NEXT:       %3 = qcore.pack_qubit_reg(%qb2) -> !qcore.qubit_reg<1>
// CHECK-NEXT:       qstruct.yield %3, %i4 : !qcore.qubit_reg<1>, i1
// CHECK-NEXT:     }
// CHECK-NEXT:     qstruct.yield %i5 : i1
// CHECK-NEXT:   }
// CHECK-NEXT:   qstruct.output(%o0, %o1 : i1, i1)
// CHECK-NEXT: }

// ----

// Case: loops

builtin.module {
  %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
  %state0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
  %c = arith.constant 10 : index

  %state1 = scf.for %i = %c to %c step %c iter_args(%state = %state0) -> (!stab.state<2 x !qcore.qubit, []>) {
    %s0 = stab.circuit %state : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, []>
      with (%qb0, %qb1 : !qcore.qubit), () {
        "test.op"(%qb0, %qb1) : (!qcore.qubit, !qcore.qubit) -> ()
        stab.yield []
      }
    scf.yield %s0 : !stab.state<2 x !qcore.qubit, []>
  }

  %state2 = qstruct.repeat<5> (%state1 : !stab.state<2 x !qcore.qubit, []>) -> !stab.state<2 x !qcore.qubit, []> {
  ^bb0(%state_in: !stab.state<2 x !qcore.qubit, []>):
    %s0 = stab.circuit %state_in : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, []>
      with (%qb0, %qb1 : !qcore.qubit), () {
        "test.op"(%qb0, %qb1) : (!qcore.qubit, !qcore.qubit) -> ()
        stab.yield []
      }
    qstruct.yield %s0 : !stab.state<2 x !qcore.qubit, []>
  }

  %state3 = scf.while (%state = %state2) : (!stab.state<2 x !qcore.qubit, []>) -> !stab.state<2 x !qcore.qubit, []> {
    %b0 = "test.op"() : () -> i1
    scf.condition(%b0) %state : !stab.state<2 x !qcore.qubit, []>
  } do {
  ^bb0(%state_in: !stab.state<2 x !qcore.qubit, []>):
    %s0 = stab.circuit %state_in : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, []>
      with (%qb0, %qb1 : !qcore.qubit), () {
        "test.op"(%qb0, %qb1) : (!qcore.qubit, !qcore.qubit) -> ()
        stab.yield []
      }
    scf.yield %s0 : !stab.state<2 x !qcore.qubit, []>
  }
}
// CHECK-LABEL: builtin.module {
// CHECK-NEXT:   %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %state0 = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
// CHECK-NEXT:   %c = arith.constant 10 : index
// CHECK-NEXT:   %state1 = scf.for %i = %c to %c step %c iter_args(%state = %state0) -> (!qcore.qubit_reg<2>) {
// CHECK-NEXT:     %s0 = qstruct.circuit(%state : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
// CHECK-NEXT:     ^bb0(%0: !qcore.qubit_reg<2>):
// CHECK-NEXT:       %qb0, %qb1 = qcore.unpack_qubit_reg(%0 : !qcore.qubit_reg<2>)
// CHECK-NEXT:       "test.op"(%qb0, %qb1) : (!qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:       %1 = qcore.pack_qubit_reg(%qb0, %qb1) -> !qcore.qubit_reg<2>
// CHECK-NEXT:       qstruct.yield %1 : !qcore.qubit_reg<2>
// CHECK-NEXT:     }
// CHECK-NEXT:     scf.yield %s0 : !qcore.qubit_reg<2>
// CHECK-NEXT:   }
// CHECK-NEXT:   %state2 = qstruct.repeat<5> (%state1 : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
// CHECK-NEXT:   ^bb0(%state_in: !qcore.qubit_reg<2>):
// CHECK-NEXT:     %s0_1 = qstruct.circuit(%state_in : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
// CHECK-NEXT:     ^bb1(%0: !qcore.qubit_reg<2>):
// CHECK-NEXT:       %qb0, %qb1 = qcore.unpack_qubit_reg(%0 : !qcore.qubit_reg<2>)
// CHECK-NEXT:       "test.op"(%qb0, %qb1) : (!qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:       %1 = qcore.pack_qubit_reg(%qb0, %qb1) -> !qcore.qubit_reg<2>
// CHECK-NEXT:       qstruct.yield %1 : !qcore.qubit_reg<2>
// CHECK-NEXT:     }
// CHECK-NEXT:     qstruct.yield %s0_1 : !qcore.qubit_reg<2>
// CHECK-NEXT:   }
// CHECK-NEXT:   %state3 = scf.while (%state_1 = %state2) : (!qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
// CHECK-NEXT:     %b0 = "test.op"() : () -> i1
// CHECK-NEXT:     scf.condition(%b0) %state_1 : !qcore.qubit_reg<2>
// CHECK-NEXT:   } do {
// CHECK-NEXT:   ^bb1(%state_in_1: !qcore.qubit_reg<2>):
// CHECK-NEXT:     %s0_2 = qstruct.circuit(%state_in_1 : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
// CHECK-NEXT:     ^bb2(%0: !qcore.qubit_reg<2>):
// CHECK-NEXT:       %qb0, %qb1 = qcore.unpack_qubit_reg(%0 : !qcore.qubit_reg<2>)
// CHECK-NEXT:       "test.op"(%qb0, %qb1) : (!qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:       %1 = qcore.pack_qubit_reg(%qb0, %qb1) -> !qcore.qubit_reg<2>
// CHECK-NEXT:       qstruct.yield %1 : !qcore.qubit_reg<2>
// CHECK-NEXT:     }
// CHECK-NEXT:     scf.yield %s0_2 : !qcore.qubit_reg<2>
// CHECK-NEXT:   }
// CHECK-NEXT: }
