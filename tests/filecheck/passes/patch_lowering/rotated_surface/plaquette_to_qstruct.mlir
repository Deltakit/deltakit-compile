// RUN: deltakit_compile compile-passes -t %s -p plaquette-to-qstruct -O %t && filecheck %s --input-file %t

// One plaquette.round with 2 plaquette.sub_circuit, the first one with 2 regions and the second one
// with 3 regions.
// Tests how the pass handles "empty" regions, how yielded SSA values are mapped and how neighbouring
// operations are not impacted.
builtin.module {
// CHECK: builtin.module {

    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %q1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT: %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT: %q1 = qcore.alloc_qubit -> !qcore.qubit

    %0, %1, %2, %3, %4, %5 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, i1, i1, i1, i1 {
        ^bb0(%arg0: !qcore.qubit, %arg1: !qcore.qubit):
        qref.reset<X> (%arg1)
        %r0, %r1, %r2, %r3 = plaquette.round(%arg0, %arg1) -> i1, i1, i1, i1 {
            ^bb1(%inner0: !qcore.qubit, %inner1: !qcore.qubit):
            %a, %b = plaquette.sub_circuit -> i1, i1 {
                %c = "test.op" () : () -> i1
                plaquette.yield %c : i1
            } {
                %d = "test.op" () : () -> i1
                plaquette.yield %d : i1
            }
            plaquette.yield %a, %b : i1, i1
        } {
            ^bb2(%inner2: !qcore.qubit, %inner3: !qcore.qubit):
            %e, %f = plaquette.sub_circuit -> i1, i1 {
                %g = "test.op" () : () -> i1
                plaquette.yield %g : i1
            } {
                %h = "test.op" () : () -> i1
                plaquette.yield %h : i1
            } {
                "test.op" () : () -> ()
                plaquette.yield
            }
            plaquette.yield %e, %f : i1, i1
        }
        qref.gate<#qcore.gate.cx> (%arg0, %arg1)
        qstruct.yield %arg0, %arg1, %r0, %r1, %r2, %r3 : !qcore.qubit, !qcore.qubit, i1, i1, i1, i1
    }

// CHECK-NEXT: %0, %1, %2, %3, %4, %5 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, i1, i1, i1, i1 {
// CHECK-NEXT:     ^bb0(%arg0: !qcore.qubit, %arg1: !qcore.qubit):
// CHECK-NEXT:     qref.reset<X> (%arg1)
// CHECK-NEXT:     %a, %e = qstruct.parallel<TOP> -> i1, i1 {
// CHECK-NEXT:         %c = "test.op"() : () -> i1
// CHECK-NEXT:         qstruct.yield %c : i1
// CHECK-NEXT:     } {
// CHECK-NEXT:         %g = "test.op"() : () -> i1
// CHECK-NEXT:         qstruct.yield %g : i1
// CHECK-NEXT:     }
// CHECK-NEXT:     %b, %f = qstruct.parallel<TOP> -> i1, i1 {
// CHECK-NEXT:         %d = "test.op"() : () -> i1
// CHECK-NEXT:         qstruct.yield %d : i1
// CHECK-NEXT:     } {
// CHECK-NEXT:         %h = "test.op"() : () -> i1
// CHECK-NEXT:         qstruct.yield %h : i1
// CHECK-NEXT:     }
// CHECK-NEXT:     qstruct.parallel<TOP> -> {
// CHECK-NEXT:         "test.op"() : () -> ()
// CHECK-NEXT:         qstruct.yield
// CHECK-NEXT:     }
// CHECK-NEXT:     qref.gate<#qcore.gate.cx> (%arg0, %arg1)
// CHECK-NEXT:     qstruct.yield %arg0, %arg1, %a, %b, %e, %f : !qcore.qubit, !qcore.qubit, i1, i1, i1, i1
// CHECK-NEXT: }

}
// CHECK-NEXT: }

// ----
// CHECK: ----

// Example of a ``plaquette.round`` operation that is not handled by the pass (here because one of
// the region contains too many operations).
builtin.module {
// CHECK: builtin.module {

    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %q1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT: %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT: %q1 = qcore.alloc_qubit -> !qcore.qubit

    %0, %1 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
        ^bb0(%arg0: !qcore.qubit, %arg1: !qcore.qubit):
        plaquette.round(%arg0, %arg1) -> {
            ^bb1(%inner0: !qcore.qubit, %inner1: !qcore.qubit):
            qref.reset<X> (%inner0) // <<<< The problematic reset.
            plaquette.sub_circuit -> {
                plaquette.yield
            }
            plaquette.yield
        } {
            ^bb2(%inner2: !qcore.qubit, %inner3: !qcore.qubit):
            plaquette.sub_circuit -> {
                plaquette.yield
            }
            plaquette.yield
        }
        qstruct.yield %arg0, %arg1 : !qcore.qubit, !qcore.qubit
    }

// CHECK-NEXT: %0, %1 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:     ^bb0(%arg0: !qcore.qubit, %arg1: !qcore.qubit):
// CHECK-NEXT:     plaquette.round(%arg0, %arg1) -> {
// CHECK-NEXT:         ^bb1(%inner0: !qcore.qubit, %inner1: !qcore.qubit):
// CHECK-NEXT:         qref.reset<X> (%inner0)
// CHECK-NEXT:         plaquette.sub_circuit -> {
// CHECK-NEXT:             plaquette.yield
// CHECK-NEXT:         }
// CHECK-NEXT:         plaquette.yield
// CHECK-NEXT:     } {
// CHECK-NEXT:         ^bb2(%inner2: !qcore.qubit, %inner3: !qcore.qubit):
// CHECK-NEXT:         plaquette.sub_circuit -> {
// CHECK-NEXT:             plaquette.yield
// CHECK-NEXT:         }
// CHECK-NEXT:         plaquette.yield
// CHECK-NEXT:     }
// CHECK-NEXT:     qstruct.yield %arg0, %arg1 : !qcore.qubit, !qcore.qubit
// CHECK-NEXT: }


}
// CHECK-NEXT: }


// ----
// CHECK: ----

// Example of a ``plaquette.round`` operation that is not handled by the pass (here because one of
// the regions contains a ``qref.reset`` instead of a ``plaquette.sub_circuit``).
builtin.module {
// CHECK: builtin.module {

    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %q1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT: %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT: %q1 = qcore.alloc_qubit -> !qcore.qubit

    %0, %1 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
        ^bb0(%arg0: !qcore.qubit, %arg1: !qcore.qubit):
        plaquette.round(%arg0, %arg1) -> {
            ^bb1(%inner0: !qcore.qubit, %inner1: !qcore.qubit):
            qref.reset<X> (%inner0) // <<<< The problematic reset.
            plaquette.yield
        } {
            ^bb2(%inner2: !qcore.qubit, %inner3: !qcore.qubit):
            plaquette.sub_circuit -> {
                plaquette.yield
            }
            plaquette.yield
        }
        qstruct.yield %arg0, %arg1 : !qcore.qubit, !qcore.qubit
    }

// CHECK-NEXT: %0, %1 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:     ^bb0(%arg0: !qcore.qubit, %arg1: !qcore.qubit):
// CHECK-NEXT:     plaquette.round(%arg0, %arg1) -> {
// CHECK-NEXT:         ^bb1(%inner0: !qcore.qubit, %inner1: !qcore.qubit):
// CHECK-NEXT:         qref.reset<X> (%inner0)
// CHECK-NEXT:         plaquette.yield
// CHECK-NEXT:     } {
// CHECK-NEXT:         ^bb2(%inner2: !qcore.qubit, %inner3: !qcore.qubit):
// CHECK-NEXT:         plaquette.sub_circuit -> {
// CHECK-NEXT:             plaquette.yield
// CHECK-NEXT:         }
// CHECK-NEXT:         plaquette.yield
// CHECK-NEXT:     }
// CHECK-NEXT:     qstruct.yield %arg0, %arg1 : !qcore.qubit, !qcore.qubit
// CHECK-NEXT: }

}
// CHECK-NEXT: }

// ----
// CHECK: ----

// One plaquette.round with 2 plaquette.sub_circuit, both with 2 regions.
// Tests how the pass handles the ``plaquette.yield`` terminator of ``plaquette.round`` regions
// shuffling the results
builtin.module {
// CHECK: builtin.module {

    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %q1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT: %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT: %q1 = qcore.alloc_qubit -> !qcore.qubit

    %0, %1, %2, %3, %4, %5 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, i1, i1, i1, i1 {
        ^bb0(%arg0: !qcore.qubit, %arg1: !qcore.qubit):
        qref.reset<X> (%arg1)
        %r0, %r1, %r2, %r3 = plaquette.round(%arg0, %arg1) -> i1, i1, i1, i1 {
            ^bb1(%inner0: !qcore.qubit, %inner1: !qcore.qubit):
            %a, %b = plaquette.sub_circuit -> i1, i1 {
                %c = "test.op" () : () -> i1
                plaquette.yield %c : i1
            } {
                %d = "test.op" () : () -> i1
                plaquette.yield %d : i1
            }
            plaquette.yield %b, %a : i1, i1 // << Shuffled here.
        } {
            ^bb2(%inner2: !qcore.qubit, %inner3: !qcore.qubit):
            %e, %f = plaquette.sub_circuit -> i1, i1 {
                %g = "test.op" () : () -> i1
                plaquette.yield %g : i1
            } {
                %h = "test.op" () : () -> i1
                plaquette.yield %h : i1
            }
            plaquette.yield %e, %f : i1, i1
        }
        qref.gate<#qcore.gate.cx> (%arg0, %arg1)
        qstruct.yield %arg0, %arg1, %r0, %r1, %r2, %r3 : !qcore.qubit, !qcore.qubit, i1, i1, i1, i1
    }

// CHECK-NEXT: %0, %1, %2, %3, %4, %5 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, i1, i1, i1, i1 {
// CHECK-NEXT:     ^bb0(%arg0: !qcore.qubit, %arg1: !qcore.qubit):
// CHECK-NEXT:     qref.reset<X> (%arg1)
// CHECK-NEXT:     %a, %e = qstruct.parallel<TOP> -> i1, i1 {
// CHECK-NEXT:         %c = "test.op"() : () -> i1
// CHECK-NEXT:         qstruct.yield %c : i1
// CHECK-NEXT:     } {
// CHECK-NEXT:         %g = "test.op"() : () -> i1
// CHECK-NEXT:         qstruct.yield %g : i1
// CHECK-NEXT:     }
// CHECK-NEXT:     %b, %f = qstruct.parallel<TOP> -> i1, i1 {
// CHECK-NEXT:         %d = "test.op"() : () -> i1
// CHECK-NEXT:         qstruct.yield %d : i1
// CHECK-NEXT:     } {
// CHECK-NEXT:         %h = "test.op"() : () -> i1
// CHECK-NEXT:         qstruct.yield %h : i1
// CHECK-NEXT:     }
// CHECK-NEXT:     qref.gate<#qcore.gate.cx> (%arg0, %arg1)
// CHECK-NEXT:     qstruct.yield %arg0, %arg1, %b, %a, %e, %f : !qcore.qubit, !qcore.qubit, i1, i1, i1, i1
// CHECK-NEXT: }

}
// CHECK-NEXT: }

// ----
// CHECK: ----

// One plaquette.round with 2 plaquette.sub_circuit, both with 1 region.
// Tests how the pass handles the ``plaquette.yield`` terminator of ``plaquette.round`` regions
// yielding the same result twice.
builtin.module {
// CHECK: builtin.module {

    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %q1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT: %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT: %q1 = qcore.alloc_qubit -> !qcore.qubit

    %0, %1, %2, %3, %4, %5 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, i1, i1, i1, i1 {
        ^bb0(%arg0: !qcore.qubit, %arg1: !qcore.qubit):
        qref.reset<X> (%arg1)
        %r0, %r1, %r2, %r3 = plaquette.round(%arg0, %arg1) -> i1, i1, i1, i1 {
            ^bb1(%inner0: !qcore.qubit, %inner1: !qcore.qubit):
            %a = plaquette.sub_circuit -> i1 {
                %b = "test.op" () : () -> i1
                plaquette.yield %b : i1
            }
            plaquette.yield %a, %a : i1, i1 // << Repetition here.
        } {
            ^bb2(%inner2: !qcore.qubit, %inner3: !qcore.qubit):
            %c = plaquette.sub_circuit -> i1 {
                %d = "test.op" () : () -> i1
                plaquette.yield %d : i1
            }
            plaquette.yield %c, %c : i1, i1 // << And repetition here too.
        }
        qref.gate<#qcore.gate.cx> (%arg0, %arg1)
        qstruct.yield %arg0, %arg1, %r0, %r1, %r2, %r3 : !qcore.qubit, !qcore.qubit, i1, i1, i1, i1
    }

// CHECK-NEXT: %0, %1, %2, %3, %4, %5 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, i1, i1, i1, i1 {
// CHECK-NEXT:     ^bb0(%arg0: !qcore.qubit, %arg1: !qcore.qubit):
// CHECK-NEXT:     qref.reset<X> (%arg1)
// CHECK-NEXT:     %a, %c = qstruct.parallel<TOP> -> i1, i1 {
// CHECK-NEXT:         %b = "test.op"() : () -> i1
// CHECK-NEXT:         qstruct.yield %b : i1
// CHECK-NEXT:     } {
// CHECK-NEXT:         %d = "test.op"() : () -> i1
// CHECK-NEXT:         qstruct.yield %d : i1
// CHECK-NEXT:     }
// CHECK-NEXT:     qref.gate<#qcore.gate.cx> (%arg0, %arg1)
// CHECK-NEXT:     qstruct.yield %arg0, %arg1, %a, %a, %c, %c : !qcore.qubit, !qcore.qubit, i1, i1, i1, i1
// CHECK-NEXT: }

}
// CHECK-NEXT: }


// ----
// CHECK: ----

// One plaquette.round with 2 plaquette.sub_circuit, both with 1 region.
// Tests how the pass handles the ``plaquette.yield`` terminator of ``plaquette.round`` regions
// yielding the same result twice.
builtin.module {
// CHECK: builtin.module {

    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %q1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT: %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT: %q1 = qcore.alloc_qubit -> !qcore.qubit

    %0, %1, %2, %3, %4, %5 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, i1, i1, i1, i1 {
        ^bb0(%arg0: !qcore.qubit, %arg1: !qcore.qubit):
        qref.reset<X> (%arg1)
        %r0, %r1, %r2, %r3 = plaquette.round(%arg0, %arg1) -> i1, i1, i1, i1 {
            ^bb1(%inner0: !qcore.qubit, %inner1: !qcore.qubit):
            %a = plaquette.sub_circuit -> i1 {
                %b = qref.measure<X> (%inner0) -> i1
                plaquette.yield %b : i1
            }
            plaquette.yield %a, %a : i1, i1
        } {
            ^bb2(%inner2: !qcore.qubit, %inner3: !qcore.qubit):
            %c = plaquette.sub_circuit -> i1 {
                %d = qref.measure<Z> (%inner3) -> i1
                plaquette.yield %d : i1
            }
            plaquette.yield %c, %c : i1, i1
        }
        qref.gate<#qcore.gate.cx> (%arg0, %arg1)
        qstruct.yield %arg0, %arg1, %r0, %r1, %r2, %r3 : !qcore.qubit, !qcore.qubit, i1, i1, i1, i1
    }

// CHECK-NEXT: %0, %1, %2, %3, %4, %5 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, i1, i1, i1, i1 {
// CHECK-NEXT:     ^bb0(%arg0: !qcore.qubit, %arg1: !qcore.qubit):
// CHECK-NEXT:     qref.reset<X> (%arg1)
// CHECK-NEXT:     %a, %c = qstruct.parallel<TOP> -> i1, i1 {
// CHECK-NEXT:         %b = qref.measure<X> (%arg0) -> i1
// CHECK-NEXT:         qstruct.yield %b : i1
// CHECK-NEXT:     } {
// CHECK-NEXT:         %d = qref.measure<Z> (%arg1) -> i1
// CHECK-NEXT:         qstruct.yield %d : i1
// CHECK-NEXT:     }
// CHECK-NEXT:     qref.gate<#qcore.gate.cx> (%arg0, %arg1)
// CHECK-NEXT:     qstruct.yield %arg0, %arg1, %a, %a, %c, %c : !qcore.qubit, !qcore.qubit, i1, i1, i1, i1
// CHECK-NEXT: }

}
// CHECK-NEXT: }


// ----
// CHECK: ----

// One plaquette.round with 2 plaquette.sub_circuit, both with 1 region.
// Tests how the pass handles the ``plaquette.yield`` terminators handle
// arguments from outside themselves.
builtin.module {
// CHECK: builtin.module {

    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %q1 = qcore.alloc_qubit -> !qcore.qubit

// CHECK-NEXT: %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT: %q1 = qcore.alloc_qubit -> !qcore.qubit

    %0, %1, %2, %3, %4, %5 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, i1, i1, i1, i1 {
        ^bb0(%arg0: !qcore.qubit, %arg1: !qcore.qubit):
        %x, %y, %z = "test.op"() : () -> (i1, i1, i1)
        qref.reset<X> (%arg1)
        %r0, %r1, %r2, %r3 = plaquette.round(%arg0, %arg1) -> i1, i1, i1, i1 {
            ^bb1(%inner0: !qcore.qubit, %inner1: !qcore.qubit):
            %a = plaquette.sub_circuit -> i1 {
                %b = qref.measure<X> (%inner0) -> i1
                plaquette.yield %x : i1
            }
            plaquette.yield %y, %a : i1, i1
        } {
            ^bb2(%inner2: !qcore.qubit, %inner3: !qcore.qubit):
            %c = plaquette.sub_circuit -> i1 {
                %d = qref.measure<Z> (%inner3) -> i1
                plaquette.yield %d : i1
            }
            plaquette.yield %c, %z : i1, i1
        }
        qref.gate<#qcore.gate.cx> (%arg0, %arg1)
        qstruct.yield %arg0, %arg1, %r0, %r1, %r2, %r3 : !qcore.qubit, !qcore.qubit, i1, i1, i1, i1
    }

// CHECK-NEXT: %0, %1, %2, %3, %4, %5 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, i1, i1, i1, i1 {
// CHECK-NEXT:     ^bb0(%arg0: !qcore.qubit, %arg1: !qcore.qubit):
// CHECK-NEXT:     %x, %y, %z = "test.op"() : () -> (i1, i1, i1)
// CHECK-NEXT:     qref.reset<X> (%arg1)
// CHECK-NEXT:     %a, %c = qstruct.parallel<TOP> -> i1, i1 {
// CHECK-NEXT:         %b = qref.measure<X> (%arg0) -> i1
// CHECK-NEXT:         qstruct.yield %x : i1
// CHECK-NEXT:     } {
// CHECK-NEXT:         %d = qref.measure<Z> (%arg1) -> i1
// CHECK-NEXT:         qstruct.yield %d : i1
// CHECK-NEXT:     }
// CHECK-NEXT:     qref.gate<#qcore.gate.cx> (%arg0, %arg1)
// CHECK-NEXT:     qstruct.yield %arg0, %arg1, %y, %a, %c, %z : !qcore.qubit, !qcore.qubit, i1, i1, i1, i1
// CHECK-NEXT: }

}
// CHECK-NEXT: }
