// RUN: deltakit_compile compile-passes %s -p lower-concrete-flows -O %t --test-mode && filecheck %s --input-file %t

// One circuit, no measurements

builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
    %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
      with (%q1 : !qcore.qubit), () {
        stab.yield []
      } {stab.flows = #stab.concrete_flow_array<[<+:>{I -> X0 : 1}]>}
}
// CHECK:      builtin.module {
// CHECK-NEXT:   %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:   %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, [X0]>
// CHECK-NEXT:     with (%q1 : !qcore.qubit), (){
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{I -> X0}]
// CHECK-NEXT: }

// ----

// One circuit with one measurement in a flow

builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
    %s1, %m1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
      with (%q1 : !qcore.qubit), () {
        %m0 = qref.measure<Z> (%q1) -> i1
        stab.yield [] %m0 : i1
      } {stab.flows = #stab.concrete_flow_array<[<+:1>{I -> X0 : 1}]>}
}
// CHECK:      builtin.module {
// CHECK-NEXT:   %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:   %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:   %s1, %m1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, [X0]>
// CHECK-NEXT:     with (%q1 : !qcore.qubit), (){
// CHECK-NEXT:       %m0 = qref.measure<Z> (%q1) -> i1
// CHECK-NEXT:       stab.yield [%m0 : i1] %m0 : i1
// CHECK-NEXT:     } [<+:0>{I -> X0}]
// CHECK-NEXT: }

// ----

// One circuit with several flows and measurements

builtin.module {
    %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
    %s0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
    %s1, %i0, %m0, %m1, %i1, %m2 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, []>
        -> !stab.state<2 x !qcore.qubit, []>
      with (%q2, %q3 : !qcore.qubit), () {
        %m3 = qref.measure<Z> (%q2) -> i1
        %m4 = qref.measure<Z> (%q2) -> i1
        %m5 = qref.measure<Z> (%q2) -> i1
        %i2, %i3 = "test.op"() : () -> (i32, i32)
        stab.yield [%m4 : i1] %i2, %m3, %m4, %i3, %m5 : i32, i1, i1, i32, i1
      } {stab.flows = #stab.concrete_flow_array<[<+:2,3,5>{I -> X0 X1 : 2}, <+:3,5>{I -> X0 : 2}, <+:3>{I -> X1 : 2}]>}
}
// CHECK:      builtin.module {
// CHECK-NEXT:   %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %s0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   %s1, %i0, %m0, %m1, %i1, %m2 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, []>
// CHECK-SAME:       -> !stab.state<2 x !qcore.qubit, [X0 X1, X0, X1]>
// CHECK-NEXT:     with (%q2, %q3 : !qcore.qubit), (){
// CHECK-NEXT:       %m3 = qref.measure<Z> (%q2) -> i1
// CHECK-NEXT:       %m4 = qref.measure<Z> (%q2) -> i1
// CHECK-NEXT:       %m5 = qref.measure<Z> (%q2) -> i1
// CHECK-NEXT:       %i2, %i3 = "test.op"() : () -> (i32, i32)
// CHECK-NEXT:       stab.yield [%m4, %m3, %m5 : i1, i1, i1] %i2, %m3, %m4, %i3, %m5 : i32, i1, i1, i32, i1
// CHECK-NEXT:     } [<+:0, 1, 2>{I -> X0 X1}, <+:0, 2>{I -> X0}, <+:0>{I -> X1}]
// CHECK-NEXT: }

// ----

// Two circuits, flows on first: input type of second is updated

builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
    %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
      with (%q1 : !qcore.qubit), () {
        stab.yield []
      } {stab.flows = #stab.concrete_flow_array<[<+:>{I -> X0 : 1}]>}
    %s2 = stab.circuit %s1 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
      with (%q2 : !qcore.qubit), () {
        stab.yield []
      }
}
// CHECK:      builtin.module {
// CHECK-NEXT:   %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:   %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, [X0]>
// CHECK-NEXT:     with (%q1 : !qcore.qubit), (){
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{I -> X0}]
// CHECK-NEXT:   %s2 = stab.circuit %s1 : !stab.state<1 x !qcore.qubit, [X0]> -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     with (%q2 : !qcore.qubit), (){
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     }
// CHECK-NEXT: }

// ----

// Two circuits, flows on second: output type of first is updated

builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
    %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
      with (%q1 : !qcore.qubit), () {
        stab.yield []
      }
    %s2 = stab.circuit %s1 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, []>
      with (%q2 : !qcore.qubit), () {
        stab.yield []
      } {stab.flows = #stab.concrete_flow_array<[<+:>{X0 -> Z0 : 1}]>}
}
// CHECK:      builtin.module {
// CHECK-NEXT:   %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:   %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<1 x !qcore.qubit, []> -> !stab.state<1 x !qcore.qubit, [X0]>
// CHECK-NEXT:     with (%q1 : !qcore.qubit), (){
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     }
// CHECK-NEXT:   %s2 = stab.circuit %s1 : !stab.state<1 x !qcore.qubit, [X0]> -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:     with (%q2 : !qcore.qubit), (){
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{X0 -> Z0}]
// CHECK-NEXT: }

// ----

// Two circuits, flows on both: state type in between gets union of the flow states

builtin.module {
    %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
    %s0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
    %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, []>
      with (%q2, %q3 : !qcore.qubit), () {
        stab.yield []
      } {stab.flows = #stab.concrete_flow_array<[<+:>{I -> X0 X1 : 2}, <+:>{I -> X0 : 2}]>}
    %s2 = stab.circuit %s1 : !stab.state<2 x !qcore.qubit, []> -> !stab.state<2 x !qcore.qubit, []>
      with (%q4, %q5 : !qcore.qubit), () {
        stab.yield []
      } {stab.flows = #stab.concrete_flow_array<[<+:>{X0 X1 -> Z0 Z1 : 2}, <+:>{X1 -> I : 2}]>}
}
// CHECK:      builtin.module {
// CHECK-NEXT:   %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %s0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:   %s1 = stab.circuit %s0 : !stab.state<2 x !qcore.qubit, []>
// CHECK-SAME:       -> !stab.state<2 x !qcore.qubit, [X0 X1, X0, X1]>
// CHECK-NEXT:     with (%q2, %q3 : !qcore.qubit), (){
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{I -> X0 X1}, <+:>{I -> X0}]
// CHECK-NEXT:   %s2 = stab.circuit %s1 : !stab.state<2 x !qcore.qubit, [X0 X1, X0, X1]>
// CHECK-SAME:       -> !stab.state<2 x !qcore.qubit, [Z0 Z1]>
// CHECK-NEXT:     with (%q4, %q5 : !qcore.qubit), (){
// CHECK-NEXT:       stab.yield []
// CHECK-NEXT:     } [<+:>{X0 X1 -> Z0 Z1}, <+:>{X1 -> I}]
// CHECK-NEXT: }
