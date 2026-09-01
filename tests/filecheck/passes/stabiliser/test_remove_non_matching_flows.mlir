// RUN: deltakit_compile compile-passes %s -p remove-non-matching-flows -O %t && filecheck %s --input-file %t

// Remove a single flow not matched on a single circuit with no successor

builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>

    %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q0_b : !qcore.qubit), (){
        qref.reset<Z>(%q0_b)
        stab.yield []
      } [<+:>{I -> Z0}] {stab.droppable_flows}
}

// CHECK:      builtin.module {
// CHECK-NEXT:   %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:   %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%q0_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } {stab.droppable_flows}
// CHECK-NEXT: }

// ----
// CHECK-NEXT: ----

// Remove a single flow not matched on a circuit's successor

builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>

    %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q0_b : !qcore.qubit), (){
        qref.reset<Z>(%q0_b)
        stab.yield []
      } [<+:>{I -> Z0}] {stab.droppable_flows}

    %s2 = stab.circuit %s1 : !stab.state<1 x !qcore.qubit, [Z0]> -> !stab.state<1 x !qcore.qubit, []>
      with (%q0_b : !qcore.qubit), (){
        qref.reset<Z>(%q0_b)
        stab.yield []
      } {stab.droppable_flows}
}

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:   %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%q0_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } {stab.droppable_flows}
// CHECK-NEXT:   %s2 = stab.circuit %s1 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%q0_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } {stab.droppable_flows}
// CHECK-NEXT: }

// ----
// CHECK-NEXT: ----

// Remove a single flow not matched on a circuit's predecessor

builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>

    %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q0_b : !qcore.qubit), (){
        qref.reset<Z>(%q0_b)
        stab.yield []
      } {stab.droppable_flows}

    %s2 = stab.circuit %s1 : !stab.state<1 x !qcore.qubit, [Z0]> -> !stab.state<1 x !qcore.qubit, []>
      with (%q0_b : !qcore.qubit), (){
        qref.reset<Z>(%q0_b)
        stab.yield []
      } [<+:>{Z0 -> I}] {stab.droppable_flows}
}

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:   %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%q0_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } {stab.droppable_flows}
// CHECK-NEXT:   %s2 = stab.circuit %s1 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%q0_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } {stab.droppable_flows}
// CHECK-NEXT: }

// ----
// CHECK-NEXT: ----

// Remove multiple flows and keep one

builtin.module {
    %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
    %s0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>

    %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [Z0, X1]>
      with (%q0_b, %q1_b : !qcore.qubit), (){
        qref.reset<Z>(%q0_b)
        stab.yield []
      } [<+:>{I -> Z0}, <+:>{I -> X1}] {stab.droppable_flows}

    %s2 = stab.circuit %s1 : !stab.state<2 x !qcore.qubit, [Z0, X1]> -> !stab.state<2 x !qcore.qubit, [X1]>
      with (%q0_b, %q1_b : !qcore.qubit), (){
        qref.reset<Z>(%q0_b)
        stab.yield []
      } [<+:>{I -> X1}, <+:>{Z0 -> I}] {stab.droppable_flows}
}

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %s0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [Z0]>
// CHECK-NEXT:     with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%q0_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{I -> Z0}] {stab.droppable_flows}
// CHECK-NEXT:   %s2 = stab.circuit %s1 : !stab.state<2 x !qcore.qubit, [Z0]> -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%q0_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{Z0 -> I}] {stab.droppable_flows}
// CHECK-NEXT: }

// ----
// CHECK-NEXT: ----

// Remove extraneous flow states not matched by anything

builtin.module {
    %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
    %s0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>

    %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [X0 X1, Z0 Z1]>
      with (%q0_b, %q1_b : !qcore.qubit), (){
        qref.reset<Z>(%q0_b)
        stab.yield []
      } {stab.droppable_flows}

    %s2 = stab.circuit %s1 : !stab.state<2 x !qcore.qubit, [X0 X1, Z0 Z1]> -> !stab.state<2 x !qcore.qubit, [X0 X1, X0]>
      with (%q0_b, %q1_b : !qcore.qubit), (){
        qref.reset<Z>(%q0_b)
        stab.yield []
      } {stab.droppable_flows}
}

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %s0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%q0_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } {stab.droppable_flows}
// CHECK-NEXT:   %s2 = stab.circuit %s1 : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%q0_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } {stab.droppable_flows}
// CHECK-NEXT: }

// ----
// CHECK-NEXT: ----

// Remove a whole flow chain that isn't wrapped up

builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>

    %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q0_b : !qcore.qubit), (){
        qref.reset<Z>(%q0_b)
        stab.yield []
      } [<+:>{I -> Z0}] {stab.droppable_flows}

    %s2 = stab.circuit %s1 : !stab.state<1 x !qcore.qubit, [Z0]> -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q0_b : !qcore.qubit), (){
        qref.reset<Z>(%q0_b)
        stab.yield []
      } [<+:>{Z0 -> Z0}] {stab.droppable_flows}
}

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:   %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%q0_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } {stab.droppable_flows}
// CHECK-NEXT:   %s2 = stab.circuit %s1 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%q0_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } {stab.droppable_flows}
// CHECK-NEXT: }

// ----
// CHECK-NEXT: ----

// Remove whole flow chains that don't match

builtin.module {
    %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
    %s0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>

    %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0, Z1]>
      with (%q0_b, %q1_b : !qcore.qubit), (){
        qref.reset<Z>(%q0_b)
        stab.yield []
      } [<+:>{I -> Z0}, <+:>{I -> Z1}] {stab.droppable_flows}

    %s2 = stab.circuit %s1 : !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0, Z1]> -> !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0, Z1]>
      with (%q0_b, %q1_b : !qcore.qubit), (){
        qref.reset<Z>(%q0_b)
        stab.yield []
      } [<+:>{Z0 Z1 -> Z0 Z1}, <+:>{Z0 -> Z0}, <+:>{Z1 -> Z1}] {stab.droppable_flows}

    %s3 = stab.circuit %s2 : !stab.state<2 x !qcore.qubit, [Z0 Z1, Z0, Z1]> -> !stab.state<2 x !qcore.qubit, []>
      with (%q0_b, %q1_b : !qcore.qubit), (){
        qref.reset<Z>(%q0_b)
        stab.yield []
      } [<+:>{Z0 Z1 -> I}, <+:>{Z1 -> I}] {stab.droppable_flows}
}

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %s0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, [Z1]>
// CHECK-NEXT:     with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%q0_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{I -> Z1}] {stab.droppable_flows}
// CHECK-NEXT:   %s2 = stab.circuit %s1 : !stab.state<2 x !qcore.qubit, [Z1]> -> !stab.state<2 x !qcore.qubit, [Z1]>
// CHECK-NEXT:     with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%q0_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{Z1 -> Z1}] {stab.droppable_flows}
// CHECK-NEXT:   %s3 = stab.circuit %s2 : !stab.state<2 x !qcore.qubit, [Z1]> -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     with (%q0_b, %q1_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%q0_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{Z1 -> I}] {stab.droppable_flows}
// CHECK-NEXT: }

// ----
// CHECK-NEXT: ----

// Remove a long flow chain with no successor

builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>

    %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q0_b : !qcore.qubit), (){
        qref.reset<Z>(%q0_b)
        stab.yield []
      } [<+:>{I -> Z0}] {stab.droppable_flows}

    %s2 = stab.circuit %s1 : !stab.state<1 x !qcore.qubit, [Z0]> -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q0_b : !qcore.qubit), (){
        qref.reset<Z>(%q0_b)
        stab.yield []
      } [<+:>{Z0 -> Z0}] {stab.droppable_flows}

    %s3 = stab.circuit %s2 : !stab.state<1 x !qcore.qubit, [Z0]> -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q0_b : !qcore.qubit), (){
        qref.reset<Z>(%q0_b)
        stab.yield []
      } [<+:>{Z0 -> Z0}] {stab.droppable_flows}

    %s4 = stab.circuit %s3 : !stab.state<1 x !qcore.qubit, [Z0]> -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q0_b : !qcore.qubit), (){
        qref.reset<Z>(%q0_b)
        stab.yield []
      } [<+:>{Z0 -> Z0}] {stab.droppable_flows}

    %s5 = stab.circuit %s4 : !stab.state<1 x !qcore.qubit, [Z0]> -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q0_b : !qcore.qubit), (){
        qref.reset<Z>(%q0_b)
        stab.yield []
      } [<+:>{Z0 -> Z0}] {stab.droppable_flows}
}

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:   %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%q0_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } {stab.droppable_flows}
// CHECK-NEXT:   %s2 = stab.circuit %s1 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%q0_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } {stab.droppable_flows}
// CHECK-NEXT:   %s3 = stab.circuit %s2 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%q0_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } {stab.droppable_flows}
// CHECK-NEXT:   %s4 = stab.circuit %s3 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%q0_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } {stab.droppable_flows}
// CHECK-NEXT:   %s5 = stab.circuit %s4 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%q0_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } {stab.droppable_flows}
// CHECK-NEXT: }

// ----
// CHECK-NEXT: ----

// Doesn't drop flows on circuits not marked as droppable

builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>

    %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q0_b : !qcore.qubit), (){
        qref.reset<Z>(%q0_b)
        stab.yield []
      } [<+:>{I -> Z0}]
}

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:   %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:     with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%q0_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{I -> Z0}]
// CHECK-NEXT: }

// ----
// CHECK-NEXT: ----

// Non-droppable circuits stop removal

builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>

    %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q0_b : !qcore.qubit), (){
        qref.reset<Z>(%q0_b)
        stab.yield []
      } [<+:>{I -> Z0}] {stab.droppable_flows}

    %s2 = stab.circuit %s1 : !stab.state<1 x !qcore.qubit, [Z0]> -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q0_b : !qcore.qubit), (){
        qref.reset<Z>(%q0_b)
        stab.yield []
      } [<+:>{Z0 -> Z0}]
}

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:   %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:     with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:       qref.reset<Z> (%q0_b)
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{I -> Z0}] {stab.droppable_flows}
// CHECK-NEXT:    %s2 = stab.circuit %s1 : !stab.state<1 x !qcore.qubit, [Z0]> -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:      with (%q0_b : !qcore.qubit), (){
// CHECK-NEXT:        qref.reset<Z> (%q0_b)
// CHECK-NEXT:        stab.yield []
// CHECK-NEXT:      } [<+:>{Z0 -> Z0}]
// CHECK-NEXT: }
