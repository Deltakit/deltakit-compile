// RUN: deltakit_compile compile-passes --test-mode %s -O %t && filecheck %s --input-file %t

// Checks `stab.state.permute` prints/parses with `<[...]>` and preserves an attr-dict.

builtin.module {
  %0 = "test.op"() : () -> !stab.state<3 x !test.type<"qubit">, [X0]>

  // CHECK: stab.state.permute<[2, 0, 1]> (%0 : !stab.state<3 x !test.type<"qubit">, [X0]>) -> !stab.state<3 x !test.type<"qubit">, [X2]>
  %1 = stab.state.permute<[2, 0, 1]> (%0 : !stab.state<3 x !test.type<"qubit">, [X0]>)
    -> !stab.state<3 x !test.type<"qubit">, [X2]>

  %2 = "test.op"() : () -> !stab.state<2 x !test.type<"qubit">, [Z1]>

  // CHECK: stab.state.permute<[1, 0]> (%2 : !stab.state<2 x !test.type<"qubit">, [Z1]>) {tag = "hello"} -> !stab.state<2 x !test.type<"qubit">, [Z0]>
  %3 = stab.state.permute<[1, 0]> (%2 : !stab.state<2 x !test.type<"qubit">, [Z1]>) {tag = "hello"}
    -> !stab.state<2 x !test.type<"qubit">, [Z0]>
}
