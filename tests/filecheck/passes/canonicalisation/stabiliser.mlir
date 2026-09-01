// RUN: deltakit_compile compile-passes %s -t -p canonicalize -O %t && filecheck %s --input-file %t

// Trivial concatenates, splits, and permutes are removed

builtin.module {
    %s0 = "test.op"() : () -> !stab.state<2 x !qcore.qubit, []>

    %s1 = stab.state.concatenate(%s0 : !stab.state<2 x !qcore.qubit, []>) -> !stab.state<2 x !qcore.qubit, []>
    %s2 = stab.state.split(%s1 : !stab.state<2 x !qcore.qubit, []>) -> !stab.state<2 x !qcore.qubit, []>
    %s3 = stab.state.permute<[0, 1]>(%s2 : !stab.state<2 x !qcore.qubit, []>) -> !stab.state<2 x !qcore.qubit, []>

    "test.op"(%s3) : (!stab.state<2 x !qcore.qubit, []>) -> ()
}

// CHECK:       builtin.module {
// CHECK-NEXT:      %s0 = "test.op"() : () -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:      "test.op"(%s0) : (!stab.state<2 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:  }

// ----

// Two consecutive concatenates are combined into one

builtin.module {
    %s0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
    %s1 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
    %s2 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>

    %c0 = stab.state.concatenate(%s0, %s1 : !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>)
        -> !stab.state<2 x !qcore.qubit, []>
    %c1 = stab.state.concatenate(%c0, %s2 : !stab.state<2 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>)
        -> !stab.state<3 x !qcore.qubit, []>

    "test.op"(%c1) : (!stab.state<3 x !qcore.qubit, []>) -> ()
}

// CHECK:       builtin.module {
// CHECK-NEXT:      %s0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      %s1 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      %s2 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      %c1 = stab.state.concatenate(%s0, %s1, %s2 : !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:          !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>)
// CHECK-SAME:          -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:      "test.op"(%c1) : (!stab.state<3 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:  }

// ----

// Three consecutive concatenates are combined into one

builtin.module {
    %s0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
    %s1 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
    %s2 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
    %s3 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>

    %c0 = stab.state.concatenate(%s0, %s1 : !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>)
        -> !stab.state<2 x !qcore.qubit, []>
    %c1 = stab.state.concatenate(%s2, %s3 : !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>)
        -> !stab.state<2 x !qcore.qubit, []>
    %c2 = stab.state.concatenate(%c0, %c1 : !stab.state<2 x !qcore.qubit, []>, !stab.state<2 x !qcore.qubit, []>)
        -> !stab.state<4 x !qcore.qubit, []>

    "test.op"(%c2) : (!stab.state<4 x !qcore.qubit, []>) -> ()
}

// CHECK:       builtin.module {
// CHECK-NEXT:      %s0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      %s1 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      %s2 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      %s3 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      %c2 = stab.state.concatenate(%s0, %s1, %s2, %s3 : !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:          !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:          !stab.state<1 x !qcore.qubit, []>) -> !stab.state<4 x !qcore.qubit, []>
// CHECK-NEXT:      "test.op"(%c2) : (!stab.state<4 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:  }

// ----

// Consecutive concatenates: earlier concatenate not erased if output is used in another branch

builtin.module {
    %s0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
    %s1 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
    %s2 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
    %b = "test.op"() : () -> i1

    %c0 = stab.state.concatenate(%s0, %s1 : !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>)
        -> !stab.state<2 x !qcore.qubit, []>

    scf.if %b {
        %c1 = stab.state.concatenate(%c0, %s2 : !stab.state<2 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>)
            -> !stab.state<3 x !qcore.qubit, []>
        "test.op"(%c1) : (!stab.state<3 x !qcore.qubit, []>) -> ()
    } else {
        "test.op"(%c0) : (!stab.state<2 x !qcore.qubit, []>) -> ()
    }
}

// CHECK:      builtin.module {
// CHECK-NEXT:     %s0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     %s1 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     %s2 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     %b = "test.op"() : () -> i1
// CHECK-NEXT:     %c0 = stab.state.concatenate(%s0, %s1 : !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:         !stab.state<1 x !qcore.qubit, []>) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     scf.if %b {
// CHECK-NEXT:         %c1 = stab.state.concatenate(%s0, %s1, %s2 : !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:             !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>)
// CHECK-SAME:             -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:         "test.op"(%c1) : (!stab.state<3 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:     } else {
// CHECK-NEXT:         "test.op"(%c0) : (!stab.state<2 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:     }
// CHECK-NEXT: }

// ----

// Two consecutive splits are combined into one

builtin.module {
    %s0 = "test.op"() : () -> !stab.state<3 x !qcore.qubit, []>

    %s1, %s2 = stab.state.split(%s0 : !stab.state<3 x !qcore.qubit, []>)
        -> !stab.state<2 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
    %s3, %s4 = stab.state.split(%s1 : !stab.state<2 x !qcore.qubit, []>)
        -> !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>

    "test.op"(%s3, %s4, %s2) : (!stab.state<1 x !qcore.qubit, []>,
        !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>) -> ()
}

// CHECK:       builtin.module {
// CHECK-NEXT:      %s0 = "test.op"() : () -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:      %s3, %s4, %s2 = stab.state.split(%s0 : !stab.state<3 x !qcore.qubit, []>)
// CHECK-SAME:          -> !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:          !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      "test.op"(%s3, %s4, %s2) : (!stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:          !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:  }

// ----

// Three consecutive splits are combined into one

builtin.module {
    %s0 = "test.op"() : () -> !stab.state<4 x !qcore.qubit, []>

    %a, %b = stab.state.split(%s0 : !stab.state<4 x !qcore.qubit, []>)
        -> !stab.state<2 x !qcore.qubit, []>, !stab.state<2 x !qcore.qubit, []>
    %c, %d = stab.state.split(%a : !stab.state<2 x !qcore.qubit, []>)
        -> !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
    %e, %f = stab.state.split(%b : !stab.state<2 x !qcore.qubit, []>)
        -> !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>

    "test.op"(%c, %d, %e, %f) : (!stab.state<1 x !qcore.qubit, []>,
        !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>,
        !stab.state<1 x !qcore.qubit, []>) -> ()
}

// CHECK:       builtin.module {
// CHECK-NEXT:      %s0 = "test.op"() : () -> !stab.state<4 x !qcore.qubit, []>
// CHECK-NEXT:      %c, %d, %e, %f = stab.state.split(%s0 : !stab.state<4 x !qcore.qubit, []>)
// CHECK-SAME:          -> !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:          !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      "test.op"(%c, %d, %e, %f) : (!stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:          !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:          !stab.state<1 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:  }

// ----

// Consecutive splits: if the output is used in another branch, not combined.

builtin.module {
    %s0 = "test.op"() : () -> !stab.state<3 x !qcore.qubit, []>
    %b = "test.op"() : () -> i1

    %s1, %s2 = stab.state.split(%s0 : !stab.state<3 x !qcore.qubit, []>)
        -> !stab.state<2 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
    scf.if %b {
        %s3, %s4 = stab.state.split(%s1 : !stab.state<2 x !qcore.qubit, []>)
            -> !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
        "test.op"(%s3, %s4, %s2) : (!stab.state<1 x !qcore.qubit, []>,
            !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>) -> ()
    } else {
        "test.op"(%s1, %s2) : (!stab.state<2 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>) -> ()
    }
}

// CHECK:      builtin.module {
// CHECK-NEXT:     %s0 = "test.op"() : () -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:     %b = "test.op"() : () -> i1
// CHECK-NEXT:     %s1, %s2 = stab.state.split(%s0 : !stab.state<3 x !qcore.qubit, []>)
// CHECK-SAME:         -> !stab.state<2 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     scf.if %b {
// CHECK-NEXT:         %s3, %s4 = stab.state.split(%s1 : !stab.state<2 x !qcore.qubit, []>)
// CHECK-SAME:             -> !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:         "test.op"(%s3, %s4, %s2) : (!stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:             !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:     } else {
// CHECK-NEXT:         "test.op"(%s1, %s2) : (!stab.state<2 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:     }
// CHECK-NEXT: }

// ----

// Two consecutive permutes are composed into one

builtin.module {
    %s0 = "test.op"() : () -> !stab.state<3 x !qcore.qubit, []>

    %s1 = stab.state.permute<[1, 0, 2]> (%s0 : !stab.state<3 x !qcore.qubit, []>)
        -> !stab.state<3 x !qcore.qubit, []>
    %s2 = stab.state.permute<[0, 2, 1]> (%s1 : !stab.state<3 x !qcore.qubit, []>)
        -> !stab.state<3 x !qcore.qubit, []>

    "test.op"(%s2) : (!stab.state<3 x !qcore.qubit, []>) -> ()
}

// CHECK:       builtin.module {
// CHECK-NEXT:      %s0 = "test.op"() : () -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:      %s2 = stab.state.permute<[2, 0, 1]> (%s0 : !stab.state<3 x !qcore.qubit, []>)
// CHECK-SAME:          -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:      "test.op"(%s2) : (!stab.state<3 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:  }

// ----

// Consecutive permutes: first permute not removed if its output is used in another branch

builtin.module {
    %s0 = "test.op"() : () -> !stab.state<3 x !qcore.qubit, []>
    %b = "test.op"() : () -> i1

    %s1 = stab.state.permute<[1, 0, 2]> (%s0 : !stab.state<3 x !qcore.qubit, []>)
        -> !stab.state<3 x !qcore.qubit, []>
    scf.if %b {
        %s2 = stab.state.permute<[0, 2, 1]> (%s1 : !stab.state<3 x !qcore.qubit, []>)
            -> !stab.state<3 x !qcore.qubit, []>
        "test.op"(%s2) : (!stab.state<3 x !qcore.qubit, []>) -> ()
    } else {
        "test.op"(%s1) : (!stab.state<3 x !qcore.qubit, []>) -> ()
    }
}

// CHECK:      builtin.module {
// CHECK-NEXT:     %s0 = "test.op"() : () -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:     %b = "test.op"() : () -> i1
// CHECK-NEXT:     %s1 = stab.state.permute<[1, 0, 2]> (%s0 : !stab.state<3 x !qcore.qubit, []>)
// CHECK-SAME:         -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:     scf.if %b {
// CHECK-NEXT:         %s2 = stab.state.permute<[2, 0, 1]> (%s0 : !stab.state<3 x !qcore.qubit, []>)
// CHECK-SAME:             -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:         "test.op"(%s2) : (!stab.state<3 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:     } else {
// CHECK-NEXT:         "test.op"(%s1) : (!stab.state<3 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:     }
// CHECK-NEXT: }

// ----

// Concatenate two equal-sized states then split back — both ops removed

builtin.module {
    %s0 = "test.op"() : () -> !stab.state<2 x !qcore.qubit, []>
    %s1 = "test.op"() : () -> !stab.state<2 x !qcore.qubit, []>

    %c = stab.state.concatenate(%s0, %s1 : !stab.state<2 x !qcore.qubit, []>,
        !stab.state<2 x !qcore.qubit, []>) -> !stab.state<4 x !qcore.qubit, []>
    %a, %b = stab.state.split(%c : !stab.state<4 x !qcore.qubit, []>)
        -> !stab.state<2 x !qcore.qubit, []>, !stab.state<2 x !qcore.qubit, []>

    "test.op"(%a, %b) : (!stab.state<2 x !qcore.qubit, []>,
        !stab.state<2 x !qcore.qubit, []>) -> ()
}

// CHECK:       builtin.module {
// CHECK-NEXT:      %s0 = "test.op"() : () -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:      %s1 = "test.op"() : () -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:      "test.op"(%s0, %s1) : (!stab.state<2 x !qcore.qubit, []>,
// CHECK-SAME:          !stab.state<2 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:  }

// ----

// Concatenate three unequal-sized states then split back — both ops removed

builtin.module {
    %s0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
    %s1 = "test.op"() : () -> !stab.state<3 x !qcore.qubit, []>
    %s2 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>

    %c = stab.state.concatenate(%s0, %s1, %s2 : !stab.state<1 x !qcore.qubit, []>,
        !stab.state<3 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>)
        -> !stab.state<5 x !qcore.qubit, []>
    %a, %b, %d = stab.state.split(%c : !stab.state<5 x !qcore.qubit, []>)
        -> !stab.state<1 x !qcore.qubit, []>, !stab.state<3 x !qcore.qubit, []>,
        !stab.state<1 x !qcore.qubit, []>

    "test.op"(%a, %b, %d) : (!stab.state<1 x !qcore.qubit, []>,
        !stab.state<3 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>) -> ()
}

// CHECK:       builtin.module {
// CHECK-NEXT:      %s0 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      %s1 = "test.op"() : () -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:      %s2 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:      "test.op"(%s0, %s1, %s2) : (!stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:          !stab.state<3 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:  }

// ----

// Split then concatenate in the same order: identity permutation is generated and then removed

builtin.module {
    %s0 = "test.op"() : () -> !stab.state<3 x !qcore.qubit, []>

    %a, %b = stab.state.split(%s0 : !stab.state<3 x !qcore.qubit, []>)
        -> !stab.state<1 x !qcore.qubit, []>, !stab.state<2 x !qcore.qubit, []>
    %c = stab.state.concatenate(%a, %b : !stab.state<1 x !qcore.qubit, []>,
        !stab.state<2 x !qcore.qubit, []>) -> !stab.state<3 x !qcore.qubit, []>

    "test.op"(%c) : (!stab.state<3 x !qcore.qubit, []>) -> ()
}

// CHECK:       builtin.module {
// CHECK-NEXT:      %s0 = "test.op"() : () -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:      "test.op"(%s0) : (!stab.state<3 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:  }

// ----

// Split then concatenate in reversed order: combined into a permute

builtin.module {
    %s0 = "test.op"() : () -> !stab.state<3 x !qcore.qubit, []>

    %a, %b = stab.state.split(%s0 : !stab.state<3 x !qcore.qubit, []>)
        -> !stab.state<1 x !qcore.qubit, []>, !stab.state<2 x !qcore.qubit, []>
    %c = stab.state.concatenate(%b, %a : !stab.state<2 x !qcore.qubit, []>,
        !stab.state<1 x !qcore.qubit, []>) -> !stab.state<3 x !qcore.qubit, []>

    "test.op"(%c) : (!stab.state<3 x !qcore.qubit, []>) -> ()
}

// CHECK:       builtin.module {
// CHECK-NEXT:      %s0 = "test.op"() : () -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:      %c = stab.state.permute<[2, 0, 1]> (%s0 : !stab.state<3 x !qcore.qubit, []>)
// CHECK-SAME:          -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:      "test.op"(%c) : (!stab.state<3 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:  }

// ----

// Three-way split then concatenate in a different order: combined into a permute

builtin.module {
    %s0 = "test.op"() : () -> !stab.state<4 x !qcore.qubit, []>

    %a, %b, %d = stab.state.split(%s0 : !stab.state<4 x !qcore.qubit, []>)
        -> !stab.state<1 x !qcore.qubit, []>, !stab.state<2 x !qcore.qubit, []>,
        !stab.state<1 x !qcore.qubit, []>
    %c = stab.state.concatenate(%d, %b, %a : !stab.state<1 x !qcore.qubit, []>,
        !stab.state<2 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>)
        -> !stab.state<4 x !qcore.qubit, []>

    "test.op"(%c) : (!stab.state<4 x !qcore.qubit, []>) -> ()
}

// CHECK:       builtin.module {
// CHECK-NEXT:      %s0 = "test.op"() : () -> !stab.state<4 x !qcore.qubit, []>
// CHECK-NEXT:      %c = stab.state.permute<[3, 1, 2, 0]> (%s0 : !stab.state<4 x !qcore.qubit, []>)
// CHECK-SAME:          -> !stab.state<4 x !qcore.qubit, []>
// CHECK-NEXT:      "test.op"(%c) : (!stab.state<4 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:  }

// ----

// Two makes followed by concatenate are combined into one larger make

builtin.module {
    %q0, %q1, %q2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
    %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
    %s1 = stab.state.make(%q1, %q2 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>

    %c = stab.state.concatenate(%s0, %s1 : !stab.state<1 x !qcore.qubit, []>,
        !stab.state<2 x !qcore.qubit, []>) -> !stab.state<3 x !qcore.qubit, []>

    "test.op"(%c) : (!stab.state<3 x !qcore.qubit, []>) -> ()
}

// CHECK:       builtin.module {
// CHECK-NEXT:      %q0, %q1, %q2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      %c = stab.state.make(%q0, %q1, %q2 : !qcore.qubit)
// CHECK-SAME:          -> !stab.state<3 x !qcore.qubit, []>
// CHECK-NEXT:      "test.op"(%c) : (!stab.state<3 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:  }

// ----

// Three makes with uneven sizes followed by concatenate are combined into one larger make

builtin.module {
    %q0, %q1, %q2, %q3, %q4, %q5 = qcore.alloc_qubit
        -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
    %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
    %s1 = stab.state.make(%q1, %q2, %q3 : !qcore.qubit) -> !stab.state<3 x !qcore.qubit, []>
    %s2 = stab.state.make(%q4, %q5 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>

    %c = stab.state.concatenate(%s2, %s0, %s1 : !stab.state<2 x !qcore.qubit, []>,
        !stab.state<1 x !qcore.qubit, []>, !stab.state<3 x !qcore.qubit, []>)
        -> !stab.state<6 x !qcore.qubit, []>

    "test.op"(%c) : (!stab.state<6 x !qcore.qubit, []>) -> ()
}

// CHECK:       builtin.module {
// CHECK-NEXT:      %q0, %q1, %q2, %q3, %q4, %q5 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit,
// CHECK-SAME:          !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      %c = stab.state.make(%q4, %q5, %q0, %q1, %q2, %q3 : !qcore.qubit)
// CHECK-SAME:          -> !stab.state<6 x !qcore.qubit, []>
// CHECK-NEXT:      "test.op"(%c) : (!stab.state<6 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:  }

// ----

// Subsequences of state make ops within a concatenate are collapsed

builtin.module {
    %q0, %q1, %q2, %q3, %q4 = qcore.alloc_qubit
        -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
    %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
    %s1 = stab.state.make(%q1 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
    %s2 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
    %s3 = stab.state.make(%q2 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
    %s4 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
    %s5 = stab.state.make(%q3 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
    %s6 = stab.state.make(%q4 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>

    %c = stab.state.concatenate(%s0, %s1, %s2, %s3, %s4, %s5, %s6 : !stab.state<1 x !qcore.qubit, []>,
        !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>,
        !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>,
        !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>)
        -> !stab.state<7 x !qcore.qubit, []>

    "test.op"(%c) : (!stab.state<7 x !qcore.qubit, []>) -> ()
}

// CHECK:      builtin.module {
// CHECK-NEXT:     %q0, %q1, %q2, %q3, %q4 = qcore.alloc_qubit
// CHECK-SAME:         -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:     %s2 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     %s3 = stab.state.make(%q2 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     %s4 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     %0 = stab.state.make(%q0, %q1 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     %1 = stab.state.make(%q3, %q4 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:     %c = stab.state.concatenate(%0, %s2, %s3, %s4, %1 : !stab.state<2 x !qcore.qubit, []>,
// CHECK-SAME:         !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:         !stab.state<1 x !qcore.qubit, []>, !stab.state<2 x !qcore.qubit, []>)
// CHECK-SAME:         -> !stab.state<7 x !qcore.qubit, []>
// CHECK-NEXT:     "test.op"(%c) : (!stab.state<7 x !qcore.qubit, []>) -> ()
// CHECK-NEXT: }

// ----

// Using a state make's output in another branch inhibits collapsing

builtin.module {
    %q0, %q1, %q2, %q3, %q4 = qcore.alloc_qubit
        -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
    %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
    %s1 = stab.state.make(%q1 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
    %s2 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
    %s3 = stab.state.make(%q2 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
    %s4 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
    %s5 = stab.state.make(%q3 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
    %s6 = stab.state.make(%q4 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
    %b = "test.op"() : () -> i1

    scf.if %b {
        %c = stab.state.concatenate(%s0, %s1, %s2, %s3, %s4, %s5, %s6 : !stab.state<1 x !qcore.qubit, []>,
            !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>,
            !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>,
            !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>)
            -> !stab.state<7 x !qcore.qubit, []>
        "test.op"(%c) : (!stab.state<7 x !qcore.qubit, []>) -> ()
    } else {
        "test.op"(%s1, %s3) : (!stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>) -> ()
    }
}

// CHECK:      builtin.module {
// CHECK-NEXT:     %q0, %q1, %q2, %q3, %q4 = qcore.alloc_qubit
// CHECK-SAME:         -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:     %s0 = stab.state.make(%q0 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     %s1 = stab.state.make(%q1 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     %s2 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     %s3 = stab.state.make(%q2 : !qcore.qubit) -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     %s4 = "test.op"() : () -> !stab.state<1 x !qcore.qubit, []>
// CHECK-NEXT:     %b = "test.op"() : () -> i1
// CHECK-NEXT:     scf.if %b {
// CHECK-NEXT:         %0 = stab.state.make(%q3, %q4 : !qcore.qubit) -> !stab.state<2 x !qcore.qubit, []>
// CHECK-NEXT:         %c = stab.state.concatenate(%s0, %s1, %s2, %s3, %s4, %0
// CHECK-SAME:             : !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:             !stab.state<1 x !qcore.qubit, []>, !stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:             !stab.state<1 x !qcore.qubit, []>, !stab.state<2 x !qcore.qubit, []>)
// CHECK-SAME:             -> !stab.state<7 x !qcore.qubit, []>
// CHECK-NEXT:         "test.op"(%c) : (!stab.state<7 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:     } else {
// CHECK-NEXT:         "test.op"(%s1, %s3) : (!stab.state<1 x !qcore.qubit, []>,
// CHECK-SAME:             !stab.state<1 x !qcore.qubit, []>) -> ()
// CHECK-NEXT:     }
// CHECK-NEXT: }

// ----

// Canonicalisations work with nonempty flow states too

builtin.module {
    %q0, %q1, %q2, %q3 = qcore.alloc_qubit
        -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
    %s0 = stab.state.make(%q0, %q1, %q2, %q3 : !qcore.qubit) -> !stab.state<4 x !qcore.qubit, []>

    %s1 = stab.circuit %s0 : !stab.state<4 x !qcore.qubit, []>
                          -> !stab.state<4 x !qcore.qubit, [X0 Z2, Y1 X3]>
      with (%q0_1, %q1_1, %q2_1, %q3_1 : !qcore.qubit), () {
        "test.op"(%q0_1, %q1_1, %q2_1, %q3_1) : (!qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> ()
        stab.yield []
      }

    %s2 = stab.state.permute<[0, 1, 2, 3]> (%s1 : !stab.state<4 x !qcore.qubit, [X0 Z2, Y1 X3]>)
        -> !stab.state<4 x !qcore.qubit, [X0 Z2, Y1 X3]>
    %s3 = stab.state.permute<[0, 2, 1, 3]> (%s2 : !stab.state<4 x !qcore.qubit, [X0 Z2, Y1 X3]>)
        -> !stab.state<4 x !qcore.qubit, [X0 Z1, Y2 X3]>
    %s4 = stab.state.permute<[2, 3, 0, 1]> (%s3 : !stab.state<4 x !qcore.qubit, [X0 Z1, Y2 X3]>)
        -> !stab.state<4 x !qcore.qubit, [Y0 X1, X2 Z3]>
    %s5 = stab.state.split(%s4 : !stab.state<4 x !qcore.qubit, [Y0 X1, X2 Z3]>)
        -> !stab.state<4 x !qcore.qubit, [Y0 X1, X2 Z3]>
    %s6, %s7 = stab.state.split(%s5 : !stab.state<4 x !qcore.qubit, [Y0 X1, X2 Z3]>)
        -> !stab.state<2 x !qcore.qubit, [Y0 X1]>, !stab.state<2 x !qcore.qubit, [X0 Z1]>
    %s8 = stab.state.concatenate(%s6 : !stab.state<2 x !qcore.qubit, [Y0 X1]>)
        -> !stab.state<2 x !qcore.qubit, [Y0 X1]>
    %s9 = stab.state.concatenate(%s8, %s7 : !stab.state<2 x !qcore.qubit, [Y0 X1]>,
        !stab.state<2 x !qcore.qubit, [X0 Z1]>) -> !stab.state<4 x !qcore.qubit, [Y0 X1, X2 Z3]>

    "test.op"(%s9) : (!stab.state<4 x !qcore.qubit, [Y0 X1, X2 Z3]>) -> ()
}

// CHECK:       builtin.module {
// CHECK-NEXT:      %q0, %q1, %q2, %q3 = qcore.alloc_qubit
// CHECK-SAME:          -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      %s0 = stab.state.make(%q0, %q1, %q2, %q3 : !qcore.qubit) -> !stab.state<4 x !qcore.qubit, []>
// CHECK-NEXT:      %s1 = stab.circuit %s0 : !stab.state<4 x !qcore.qubit, []>
// CHECK-SAME:          -> !stab.state<4 x !qcore.qubit, [X0 Z2, Y1 X3]>
// CHECK-NEXT:        with (%q0_1, %q1_1, %q2_1, %q3_1 : !qcore.qubit), (){
// CHECK-NEXT:          "test.op"(%q0_1, %q1_1, %q2_1, %q3_1) : (!qcore.qubit, !qcore.qubit,
// CHECK-SAME:              !qcore.qubit, !qcore.qubit) -> ()
// CHECK-NEXT:          stab.yield []
// CHECK-NEXT:        }
// CHECK-NEXT:      %s4 = stab.state.permute<[2, 0, 3, 1]> (%s1 : !stab.state<4 x !qcore.qubit, [X0 Z2, Y1 X3]>)
// CHECK-SAME:          -> !stab.state<4 x !qcore.qubit, [Y0 X1, X2 Z3]>
// CHECK-NEXT:      "test.op"(%s4) : (!stab.state<4 x !qcore.qubit, [Y0 X1, X2 Z3]>) -> ()
// CHECK-NEXT:  }
