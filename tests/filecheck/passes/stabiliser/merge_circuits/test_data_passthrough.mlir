// RUN: deltakit_compile compile-passes --test-mode %s -p merge-circuits -O %t && filecheck %s --input-file %t
// Test that merging handles input and output args correctly.

builtin.module {
// CHECK: builtin.module {

    %state0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:    %state0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, [Z0]>

    %x0 = "test.op"() : () -> !test.type<"A">
    %y0 = "test.op"() : () -> !test.type<"B">
    %z0 = "test.op"() : () -> !test.type<"C">
// CHECK-NEXT: %x0 = "test.op"() : () -> !test.type<"A">
// CHECK-NEXT: %y0 = "test.op"() : () -> !test.type<"B">
// CHECK-NEXT: %z0 = "test.op"() : () -> !test.type<"C">

    %state1, %m1, %m2, %x1, %x2, %y1 = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, [Z0]>
                                                           -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q0_b : !qcore.qubit), (%i1 = %x0 : !test.type<"A">, %i2 = %y0 : !test.type<"B">) {
        %m0 = qref.measure<Z> (%q0_b) -> i1
        stab.yield [%m0, %m0 : i1, i1] %m0, %m0, %i1, %i1, %i2 : i1, i1, !test.type<"A">, !test.type<"A">, !test.type<"B">
      } [<+:0>{I -> Z0}, <+:1>{Z0 -> I}]
    // an op with NoQuantumEffect
    %w0 = qcore.alloc_qubit -> !qcore.qubit
    %state2, %m7, %m8, %m9, %m10, %x3, %x4, %x5, %z1, %w1 = stab.circuit %state1 : !stab.state<1 x !qcore.qubit, [Z0]>
                                                                           -> !stab.state<1 x !qcore.qubit, [Z0]>
      with (%q1_b : !qcore.qubit), (
            %m3 = %m1 : i1, %m4 = %m1 : i1, %m5 = %m2 : i1, %i3 = %x1 : !test.type<"A">,
            %i4 = %x2 : !test.type<"A">, %i5 = %x2 : !test.type<"A">, %i6 = %y1 : !test.type<"B">,
            %i7 = %x0 : !test.type<"A">, %i8 = %z0 : !test.type<"C">, %i9 = %w0 : !qcore.qubit) {
        %m6 = qref.measure<Z> (%q1_b) -> i1
        stab.yield [%m3, %m3, %m4, %m5, %m6 : i1, i1, i1, i1, i1] %m3, %m3, %m4, %m6,
                   %i3, %i4, %i5, %i8, %i9 : i1, i1, i1, i1, !test.type<"A">, !test.type<"A">,
                   !test.type<"A">, !test.type<"C">, !qcore.qubit
      } [<+:0>{I -> Z0}, <+:1,3,4>{Z0 -> I}]
// CHECK-NEXT: %w0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT: %state2, %m1, %m2, %x1, %x2, %y1, %m7, %m8, %m9, %m10, %x3, %x4, %x5, %z1, %w1
// CHECK-SAME:     = stab.circuit %state0 : !stab.state<1 x !qcore.qubit, [Z0]> -> !stab.state<1 x !qcore.qubit, [Z0]>
// CHECK-NEXT:   with (%q0_b : !qcore.qubit), (%i1 = %x0 : !test.type<"A">, %i2 = %y0 : !test.type<"B">,
// CHECK-SAME:         %i7 = %x0 : !test.type<"A">, %i8 = %z0 : !test.type<"C">, %i9 = %w0 : !qcore.qubit){
// CHECK-NEXT:     %m0 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:     %m6 = qref.measure<Z> (%q0_b) -> i1
// CHECK-NEXT:     qec.detector(%m0, %m0, %m0, %m6)
// CHECK-NEXT:     stab.yield [%m0, %m0, %m0, %m0, %m0, %m0, %m6 : i1, i1, i1, i1, i1, i1, i1]
// CHECK-SAME:       %m0, %m0, %i1, %i1, %i2, %m0, %m0, %m0, %m6, %i1, %i1, %i1, %i8, %i9 : i1, i1,
// CHECK-SAME:       !test.type<"A">, !test.type<"A">, !test.type<"B">, i1, i1, i1, i1,
// CHECK-SAME:       !test.type<"A">, !test.type<"A">, !test.type<"A">, !test.type<"C">, !qcore.qubit
// CHECK-NEXT:   } [<+:2>{I -> Z0}, <+:1>{Z0 -> I}]

    "test.op"(%x0, %m1, %x1, %m7, %x5, %z1, %w1) : (!test.type<"A">, i1, !test.type<"A">, i1, !test.type<"A">, !test.type<"C">, !qcore.qubit) -> ()
// CHECK-NEXT: "test.op"(%x0, %m1, %x1, %m7, %x5, %z1, %w1) : (!test.type<"A">, i1, !test.type<"A">, i1, !test.type<"A">, !test.type<"C">, !qcore.qubit) -> ()
}
// CHECK-NEXT: }
