// RUN: deltakit_compile compile-passes -t %s -p flatten-qubit-registers -O %t && filecheck %s --input-file %t

// Register allocation and block arguments flattened

builtin.module {
    %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    %q0, %q1 = qstruct.circuit(%qreg0 : !qcore.qubit_reg<2>) -> !qcore.qubit, !qcore.qubit {
    ^bb0(%qreg0_1 : !qcore.qubit_reg<2>):
        %q00, %q11 = qcore.unpack_qubit_reg(%qreg0_1 : !qcore.qubit_reg<2>)
        qref.gate<#qcore.gate.h> (%q00)
        qstruct.yield %q00, %q11 : !qcore.qubit, !qcore.qubit
    }
}

// CHECK-NEXT:      builtin.module {
// CHECK-NEXT:        %qreg0, %qreg0_1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:        %q0, %q1 = qstruct.circuit(%qreg0, %qreg0_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:        ^bb0(%q00: !qcore.qubit, %q11: !qcore.qubit):
// CHECK-NEXT:          qref.gate<#qcore.gate.h> (%q00)
// CHECK-NEXT:          qstruct.yield %q00, %q11 : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:        }
// CHECK-NEXT:      }

// ----
// CHECK: ----

// Register allocation, block arguments and results flattened

builtin.module {
    %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    %qreg1 = qstruct.circuit(%qreg0 : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
    ^bb0(%qreg0_1 : !qcore.qubit_reg<2>):
        %q00, %q11 = qcore.unpack_qubit_reg(%qreg0_1 : !qcore.qubit_reg<2>)
        qref.gate<#qcore.gate.h> (%q00)
        %qreg = qcore.pack_qubit_reg(%q00, %q11) -> !qcore.qubit_reg<2>
        qstruct.yield %qreg : !qcore.qubit_reg<2>
    }
}

// CHECK-NEXT:      builtin.module {
// CHECK-NEXT:        %qreg0, %qreg0_1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:        %qreg1, %qreg1_1 = qstruct.circuit(%qreg0, %qreg0_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:        ^bb0(%q00: !qcore.qubit, %q11: !qcore.qubit):
// CHECK-NEXT:          qref.gate<#qcore.gate.h> (%q00)
// CHECK-NEXT:          qstruct.yield %q00, %q11 : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:        }
// CHECK-NEXT:      }

// ----
// CHECK: ----

// Pack qubits, block arguments and results flattened

builtin.module {
    %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
    %qreg0 = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
    %qreg1 = qstruct.circuit(%qreg0 : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
    ^bb0(%qreg0_1 : !qcore.qubit_reg<2>):
        %q00, %q11 = qcore.unpack_qubit_reg(%qreg0_1 : !qcore.qubit_reg<2>)
        qref.gate<#qcore.gate.h> (%q00)
        %qreg = qcore.pack_qubit_reg(%q00, %q11) -> !qcore.qubit_reg<2>
        qstruct.yield %qreg : !qcore.qubit_reg<2>
    }
}

// CHECK-NEXT:      builtin.module {
// CHECK-NEXT:        %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:        %qreg1, %qreg1_1 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:        ^bb0(%q00: !qcore.qubit, %q11: !qcore.qubit):
// CHECK-NEXT:          qref.gate<#qcore.gate.h> (%q00)
// CHECK-NEXT:          qstruct.yield %q00, %q11 : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:        }
// CHECK-NEXT:      }

// ----
// CHECK: ----

// Circuit and if flattened

builtin.module {
    %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    %m00 = arith.constant 0 : i1

    %qreg_out = scf.if %m00 -> (!qcore.qubit_reg<2>) {
        scf.yield %qreg0 : !qcore.qubit_reg<2>
    } else {
        %q0, %q1 = qcore.unpack_qubit_reg(%qreg0 : !qcore.qubit_reg<2>)
        %qreg2 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit_reg<2> {
        ^bb1(%q00: !qcore.qubit, %q11: !qcore.qubit):
            qref.gate<#qcore.gate.y>(%q00, %q11)
            %qreg_1 = qcore.pack_qubit_reg(%q00, %q11) -> !qcore.qubit_reg<2>
            qstruct.yield %qreg_1 : !qcore.qubit_reg<2>
        }
        scf.yield %qreg2 : !qcore.qubit_reg<2>
    }
}

// CHECK-NEXT:      builtin.module {
// CHECK-NEXT:        %qreg0, %qreg0_1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:        %m00 = arith.constant false
// CHECK-NEXT:        %qreg_out, %qreg_out_1 = scf.if %m00 -> (!qcore.qubit, !qcore.qubit) {
// CHECK-NEXT:          scf.yield %qreg0, %qreg0_1 : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:        } else {
// CHECK-NEXT:          %qreg2, %qreg2_1 = qstruct.circuit(%qreg0, %qreg0_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:          ^bb0(%q00: !qcore.qubit, %q11: !qcore.qubit):
// CHECK-NEXT:            qref.gate<#qcore.gate.y> (%q00, %q11)
// CHECK-NEXT:            qstruct.yield %q00, %q11 : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:          }
// CHECK-NEXT:          scf.yield %qreg2, %qreg2_1 : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:        }
// CHECK-NEXT:      }

// ----
// CHECK: ----

// Complex example with parallel circuits and qubit registers

builtin.module {
    %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    %qreg1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    %qq1 = qcore.alloc_qubit -> !qcore.qubit
    // Parallel circuits with BOTTOM alignment
    %qreg0_4, %qreg1_4, %qq1_1 = qstruct.parallel<BOTTOM> -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2>, !qcore.qubit {
        // Circuit 1
        %qreg0_3 = qstruct.circuit(%qreg0 : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
        ^bb0(%qreg0_1 : !qcore.qubit_reg<2>):
            %q0, %q1= qcore.unpack_qubit_reg(%qreg0_1 : !qcore.qubit_reg<2>)
            %m0, %m1 = qref.measure<Z>(%q0, %q1) -> i1, i1
            %d0 = qec.detector(%m0, %m1)
            %qreg0_2 = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
            qstruct.yield %qreg0_2 : !qcore.qubit_reg<2>
        }
        // End of circuit 1
        qstruct.yield %qreg0_3 : !qcore.qubit_reg<2>
    } {
        // Circuit 2
        %qreg1_3, %qqq_1 = qstruct.circuit(%qreg1, %qq1 : !qcore.qubit_reg<2>, !qcore.qubit) -> !qcore.qubit_reg<2>, !qcore.qubit {
        ^bb1(%qreg1_1 : !qcore.qubit_reg<2>, %qq_1 : !qcore.qubit):
            %q0, %q1 = qcore.unpack_qubit_reg(%qreg1_1 : !qcore.qubit_reg<2>)
            qref.gate<#qcore.gate.h>(%q0, %q1)
            %m0, %m1 = qref.measure<Z>(%q0, %q1) -> i1, i1
            %d0 = qec.detector(%m0, %m1)
            %qreg1_2 = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
            qstruct.yield %qreg1_2, %qq_1 : !qcore.qubit_reg<2>, !qcore.qubit
        }
        // End of circuit 2
        qstruct.yield %qreg1_3, %qqq_1 : !qcore.qubit_reg<2>, !qcore.qubit
    }
}

// CHECK-NEXT:   builtin.module {
// CHECK-NEXT:     %qreg0, %qreg0_1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:     %qreg1, %qreg1_1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:     %qq1 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:     %0, %1, %2, %3, %qq1_1 = qstruct.parallel<BOTTOM> -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:       %qreg0_2, %qreg0_3 = qstruct.circuit(%qreg0, %qreg0_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:       ^bb0(%q0: !qcore.qubit, %q1: !qcore.qubit):
// CHECK-NEXT:         %m0, %m1 = qref.measure<Z> (%q0, %q1) -> i1, i1
// CHECK-NEXT:         %d0 = qec.detector(%m0, %m1)
// CHECK-NEXT:         qstruct.yield %q0, %q1 : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:       }
// CHECK-NEXT:       qstruct.yield %qreg0_2, %qreg0_3 : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:     } {
// CHECK-NEXT:       %4, %5, %qqq = qstruct.circuit(%qreg1, %qreg1_1, %qq1 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:       ^bb0(%q0: !qcore.qubit, %q1: !qcore.qubit, %qq: !qcore.qubit):
// CHECK-NEXT:         qref.gate<#qcore.gate.h> (%q0, %q1)
// CHECK-NEXT:         %m0, %m1 = qref.measure<Z> (%q0, %q1) -> i1, i1
// CHECK-NEXT:         %d0 = qec.detector(%m0, %m1)
// CHECK-NEXT:         qstruct.yield %q0, %q1, %qq : !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:       }
// CHECK-NEXT:       qstruct.yield %4, %5, %qqq : !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:     }
// CHECK-NEXT:   }

// ----
// CHECK: ----

// Example with qubit register concatenation, splitting and packing

builtin.module{
    %qreg1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    %qreg2 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    %qreg3 = qcore.concatenate(%qreg1, %qreg2 : !qcore.qubit_reg<2>, !qcore.qubit_reg<2>) -> !qcore.qubit_reg<4>
    %qreg4 = qstruct.circuit(%qreg3 : !qcore.qubit_reg<4>) -> !qcore.qubit_reg<4> {
        ^bb0(%qreg0_1 : !qcore.qubit_reg<4>):
            %qreg0_2, %qreg0_3 = qcore.split(%qreg0_1 : !qcore.qubit_reg<4>) -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2>
            %q0, %q1 = qcore.unpack_qubit_reg(%qreg0_2 : !qcore.qubit_reg<2>)
            %m0, %m1 = qref.measure<Z>(%q0, %q1) -> i1, i1
            %d0 = qec.detector(%m0, %m1)
            %qreg0_4 = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
            %qreg0_5 = qcore.concatenate(%qreg0_3, %qreg0_4: !qcore.qubit_reg<2>, !qcore.qubit_reg<2>) -> !qcore.qubit_reg<4>
            qstruct.yield %qreg0_5 : !qcore.qubit_reg<4>
        }
}

// CHECK-NEXT:     builtin.module {
// CHECK-NEXT:       %qreg1, %qreg1_1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:       %qreg2, %qreg2_1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:       %qreg4, %qreg4_1, %qreg4_2, %qreg4_3 = qstruct.circuit(%qreg1, %qreg1_1, %qreg2, %qreg2_1 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:       ^bb0(%q0: !qcore.qubit, %q1: !qcore.qubit, %qreg0: !qcore.qubit, %qreg0_1: !qcore.qubit):
// CHECK-NEXT:         %m0, %m1 = qref.measure<Z> (%q0, %q1) -> i1, i1
// CHECK-NEXT:         %d0 = qec.detector(%m0, %m1)
// CHECK-NEXT:         qstruct.yield %qreg0, %qreg0_1, %q0, %q1 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:       }
// CHECK-NEXT:     }

// ----
// CHECK: ----

// Circuit with repeat

builtin.module{
    %qreg1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    %qreg2, %m1, %m2 = qstruct.circuit(%qreg1 : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2>, i1, i1 {
        ^bb0(%qreg0_1 : !qcore.qubit_reg<2>):
            %q0, %q1 = qcore.unpack_qubit_reg(%qreg0_1 : !qcore.qubit_reg<2>)
            %m0, %m1 = qref.measure<Z>(%q0, %q1) -> i1, i1
            %qreg0_2 = qcore.pack_qubit_reg(%q0, %q1) -> !qcore.qubit_reg<2>
            %m2_1, %m3_1, %qreg0_3 = qstruct.repeat<5>(%m0, %m1, %qreg0_2: i1, i1, !qcore.qubit_reg<2>) -> i1, i1, !qcore.qubit_reg<2> {
            ^bb1(%m0_1: i1, %m1_1 : i1, %qreg : !qcore.qubit_reg<2>):
                %q00, %q11 = qcore.unpack_qubit_reg(%qreg : !qcore.qubit_reg<2>)
                %m2, %m3 = qref.measure<Z>(%q00, %q11) -> i1, i1
                qec.detector(%m0_1, %m2)
                qec.detector(%m1_1, %m3)
                %qreg_1 = qcore.pack_qubit_reg(%q00, %q11) -> !qcore.qubit_reg<2>
                qstruct.yield %m2, %m3, %qreg_1 : i1, i1, !qcore.qubit_reg<2>
            }
            qstruct.yield %qreg0_3, %m2_1, %m3_1 : !qcore.qubit_reg<2>, i1, i1
        }
}

// CHECK-NEXT:      builtin.module {
// CHECK-NEXT:        %qreg1, %qreg1_1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:        %0, %1, %m1, %m2 = qstruct.circuit(%qreg1, %qreg1_1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, i1, i1 {
// CHECK-NEXT:        ^bb0(%q0: !qcore.qubit, %q1: !qcore.qubit):
// CHECK-NEXT:          %m0, %m1_1 = qref.measure<Z> (%q0, %q1) -> i1, i1
// CHECK-NEXT:          %m2_1, %m3, %2, %3 = qstruct.repeat<5> (%m0, %m1_1, %q0, %q1 : i1, i1, !qcore.qubit, !qcore.qubit) -> i1, i1, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:          ^bb1(%m0_1: i1, %m1_2: i1, %q00: !qcore.qubit, %q11: !qcore.qubit):
// CHECK-NEXT:            %m2_2, %m3_1 = qref.measure<Z> (%q00, %q11) -> i1, i1
// CHECK-NEXT:            %4 = qec.detector(%m0_1, %m2_2)
// CHECK-NEXT:            %5 = qec.detector(%m1_2, %m3_1)
// CHECK-NEXT:            qstruct.yield %m2_2, %m3_1, %q00, %q11 : i1, i1, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:          }
// CHECK-NEXT:          qstruct.yield %2, %3, %m2_1, %m3 : !qcore.qubit, !qcore.qubit, i1, i1
// CHECK-NEXT:        }
// CHECK-NEXT:      }

// ----
// CHECK: ----

// While loop with qubit register passed in as argument
builtin.module {
    %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<3>
    %init1 = arith.constant 0 : i1
    %qreg1, %out = scf.while (%arg1 = %init1, %arg2 = %qreg0) : (i1, !qcore.qubit_reg<3>) -> (!qcore.qubit_reg<3>, i1) {

    %condition = arith.constant 1 : i1

    // Forward the argument (as result or "after" region argument).
    scf.condition(%condition) %arg2, %arg1 : !qcore.qubit_reg<3>, i1

    } do {
    ^bb0(%qreg0_0: !qcore.qubit_reg<3>, %arg1_0: i1):
        %m00, %qreg0_1 = qstruct.circuit(%qreg0_0 : !qcore.qubit_reg<3>) -> i1, !qcore.qubit_reg<3> {
        ^bb1(%qreg00_1 : !qcore.qubit_reg<3>):
            %q0, %q1, %q2 = qcore.unpack_qubit_reg(%qreg00_1 : !qcore.qubit_reg<3>)
            %m0 = qref.measure<ZZZ>(%q0, %q1, %q2) -> i1
            %qreg0_2 = qcore.pack_qubit_reg(%q0, %q1, %q2) -> !qcore.qubit_reg<3>
            qstruct.yield %m0, %qreg0_2 : i1, !qcore.qubit_reg<3>
        }
        %arg1_1 = arith.xori %arg1_0, %m00 : i1
        scf.yield %qreg0_1, %arg1_1 : !qcore.qubit_reg<3>, i1

    }
}

// CHECK-NEXT:      builtin.module {
// CHECK-NEXT:        %qreg0, %qreg0_1, %qreg0_2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:        %init1 = arith.constant false
// CHECK-NEXT:        %0, %1, %2, %out = scf.while (%arg1 = %init1, %3 = %qreg0, %4 = %qreg0_1, %5 = %qreg0_2) : (i1, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> (!qcore.qubit, !qcore.qubit, !qcore.qubit, i1) {
// CHECK-NEXT:          %condition = arith.constant true
// CHECK-NEXT:          scf.condition(%condition) %3, %4, %5, %arg1 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1
// CHECK-NEXT:        } do {
// CHECK-NEXT:        ^bb0(%6: !qcore.qubit, %7: !qcore.qubit, %8: !qcore.qubit, %arg1_1: i1):
// CHECK-NEXT:          %m00, %9, %10, %11 = qstruct.circuit(%6, %7, %8 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> i1, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:          ^bb1(%q0: !qcore.qubit, %q1: !qcore.qubit, %q2: !qcore.qubit):
// CHECK-NEXT:            %m0 = qref.measure<ZZZ> (%q0, %q1, %q2) -> i1
// CHECK-NEXT:            qstruct.yield %m0, %q0, %q1, %q2 : i1, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:          }
// CHECK-NEXT:          %arg1_2 = arith.xori %arg1_1, %m00 : i1
// CHECK-NEXT:          scf.yield %9, %10, %11, %arg1_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1
// CHECK-NEXT:        }
// CHECK-NEXT:      }

// ----
// CHECK: ----

// While loop with qubit register not passed in as argument but used in body
builtin.module {
    %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<3>
    %init1 = arith.constant 0 : i1
    %qreg1, %out = scf.while (%arg1 = %init1) : (i1) -> (!qcore.qubit_reg<3>, i1) {

    %condition = arith.constant 1 : i1

    // Forward the argument (as result or "after" region argument).
    scf.condition(%condition) %qreg0, %arg1 : !qcore.qubit_reg<3>, i1

    } do {
    ^bb0(%qreg0_0: !qcore.qubit_reg<3>, %arg1_0: i1):
        %m00, %qreg0_1 = qstruct.circuit(%qreg0_0 : !qcore.qubit_reg<3>) -> i1, !qcore.qubit_reg<3> {
        ^bb1(%qreg00_1 : !qcore.qubit_reg<3>):
            %q0, %q1, %q2 = qcore.unpack_qubit_reg(%qreg00_1 : !qcore.qubit_reg<3>)
            %m0 = qref.measure<ZZZ>(%q0, %q1, %q2) -> i1
            %qreg0_2 = qcore.pack_qubit_reg(%q0, %q1, %q2) -> !qcore.qubit_reg<3>
            qstruct.yield %m0, %qreg0_2 : i1, !qcore.qubit_reg<3>
        }
        %arg1_1 = arith.xori %arg1_0, %m00 : i1
        scf.yield %qreg0_1, %arg1_1 : !qcore.qubit_reg<3>, i1

    }
}

// CHECK-NEXT:      builtin.module {
// CHECK-NEXT:        %qreg0, %qreg0_1, %qreg0_2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:        %init1 = arith.constant false
// CHECK-NEXT:        %0, %1, %2, %out = scf.while (%arg1 = %init1) : (i1) -> (!qcore.qubit, !qcore.qubit, !qcore.qubit, i1) {
// CHECK-NEXT:          %condition = arith.constant true
// CHECK-NEXT:          scf.condition(%condition) %qreg0, %qreg0_1, %qreg0_2, %arg1 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1
// CHECK-NEXT:        } do {
// CHECK-NEXT:        ^bb0(%3: !qcore.qubit, %4: !qcore.qubit, %5: !qcore.qubit, %arg1_1: i1):
// CHECK-NEXT:          %m00, %6, %7, %8 = qstruct.circuit(%3, %4, %5 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> i1, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:          ^bb1(%q0: !qcore.qubit, %q1: !qcore.qubit, %q2: !qcore.qubit):
// CHECK-NEXT:            %m0 = qref.measure<ZZZ> (%q0, %q1, %q2) -> i1
// CHECK-NEXT:            qstruct.yield %m0, %q0, %q1, %q2 : i1, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:          }
// CHECK-NEXT:          %arg1_2 = arith.xori %arg1_1, %m00 : i1
// CHECK-NEXT:          scf.yield %6, %7, %8, %arg1_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1
// CHECK-NEXT:        }
// CHECK-NEXT:      }

// ----
// CHECK: ----

// For loops with qubit register passed as argument
builtin.module {
    %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<3>
    %init1 = arith.constant 0 : i32
    %lb = arith.constant 0 : index
    %ub = arith.constant 1024 : index
    %step = arith.constant 1 : index


    %count, %qreg1 = scf.for %iv = %lb to %ub step %step
        iter_args(%sum_iter = %init1, %reg = %qreg0) -> (i32, !qcore.qubit_reg<3>) {
            %m00, %qreg0_1 = qstruct.circuit(%reg : !qcore.qubit_reg<3>) -> i1, !qcore.qubit_reg<3> {
            ^bb1(%qreg00_1 : !qcore.qubit_reg<3>):
                %q0, %q1, %q2 = qcore.unpack_qubit_reg(%qreg00_1 : !qcore.qubit_reg<3>)
                %m0 = qref.measure<ZZZ>(%q0, %q1, %q2) -> i1
                %qreg0_2 = qcore.pack_qubit_reg(%q0, %q1, %q2) -> !qcore.qubit_reg<3>
                qstruct.yield %m0, %qreg0_2: i1, !qcore.qubit_reg<3>
            }

        %m00_i32 = arith.extui %m00 : i1 to i32
        %sum_iter_1 = arith.addi %m00_i32, %sum_iter : i32
        scf.yield %sum_iter_1, %qreg0_1 : i32, !qcore.qubit_reg<3>
    }

    qstruct.output(%count : i32)

}

// CHECK-NEXT:      builtin.module {
// CHECK-NEXT:        %qreg0, %qreg0_1, %qreg0_2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:        %init1 = arith.constant 0 : i32
// CHECK-NEXT:        %lb = arith.constant 0 : index
// CHECK-NEXT:        %ub = arith.constant 1024 : index
// CHECK-NEXT:        %step = arith.constant 1 : index
// CHECK-NEXT:        %count, %0, %1, %2 = scf.for %iv = %lb to %ub step %step iter_args(%sum_iter = %init1, %3 = %qreg0, %4 = %qreg0_1, %5 = %qreg0_2) -> (i32, !qcore.qubit, !qcore.qubit, !qcore.qubit) {
// CHECK-NEXT:          %m00, %6, %7, %8 = qstruct.circuit(%3, %4, %5 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> i1, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:          ^bb0(%q0: !qcore.qubit, %q1: !qcore.qubit, %q2: !qcore.qubit):
// CHECK-NEXT:            %m0 = qref.measure<ZZZ> (%q0, %q1, %q2) -> i1
// CHECK-NEXT:            qstruct.yield %m0, %q0, %q1, %q2 : i1, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:          }
// CHECK-NEXT:          %m00_i32 = arith.extui %m00 : i1 to i32
// CHECK-NEXT:          %sum_iter_1 = arith.addi %m00_i32, %sum_iter : i32
// CHECK-NEXT:          scf.yield %sum_iter_1, %6, %7, %8 : i32, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:        }
// CHECK-NEXT:        qstruct.output(%count : i32)
// CHECK-NEXT:      }

// ----
// CHECK: ----

// Index-switch

builtin.module {
    %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<3>
    %index = arith.constant 1 : index
    %measure, %register = scf.index_switch %index -> i1, !qcore.qubit_reg<3>
    case 1 {
        %m00, %qreg0_1 = qstruct.circuit(%qreg0 : !qcore.qubit_reg<3>) -> i1, !qcore.qubit_reg<3> {
        ^bb1(%qreg00_1 : !qcore.qubit_reg<3>):
            %q0, %q1, %q2 = qcore.unpack_qubit_reg(%qreg00_1 : !qcore.qubit_reg<3>)
            %m0 = qref.measure<ZZZ>(%q0, %q1, %q2) -> i1
            %qreg0_2 = qcore.pack_qubit_reg(%q0, %q1, %q2) -> !qcore.qubit_reg<3>
            qstruct.yield %m0, %qreg0_2 : i1, !qcore.qubit_reg<3>
        }
        scf.yield %m00, %qreg0_1 : i1, !qcore.qubit_reg<3>
    }
    case 2 {
        %m00, %qreg0_1 = qstruct.circuit(%qreg0 : !qcore.qubit_reg<3>) -> i1, !qcore.qubit_reg<3> {
        ^bb1(%qreg00_1 : !qcore.qubit_reg<3>):
            %q0, %q1, %q2 = qcore.unpack_qubit_reg(%qreg00_1 : !qcore.qubit_reg<3>)
            %m0 = qref.measure<ZZZ>(%q0, %q1, %q2) -> i1
            %qreg0_2 = qcore.pack_qubit_reg(%q0, %q1, %q2) -> !qcore.qubit_reg<3>
            qstruct.yield %m0, %qreg0_2 : i1, !qcore.qubit_reg<3>
        }
        scf.yield %m00, %qreg0_1 : i1, !qcore.qubit_reg<3>
    }
    default {
        %m00, %qreg0_1 = qstruct.circuit(%qreg0 : !qcore.qubit_reg<3>) -> i1, !qcore.qubit_reg<3> {
        ^bb1(%qreg00_1 : !qcore.qubit_reg<3>):
            %q0, %q1, %q2 = qcore.unpack_qubit_reg(%qreg00_1 : !qcore.qubit_reg<3>)
            %m0 = qref.measure<ZZZ>(%q0, %q1, %q2) -> i1
            %qreg0_2 = qcore.pack_qubit_reg(%q0, %q1, %q2) -> !qcore.qubit_reg<3>
            qstruct.yield %m0, %qreg0_2 : i1, !qcore.qubit_reg<3>
        }
        scf.yield %m00, %qreg0_1 : i1, !qcore.qubit_reg<3>
    }
}
// CHECK-NEXT:      builtin.module {
// CHECK-NEXT:        %qreg0, %qreg0_1, %qreg0_2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:        %index = arith.constant 1 : index
// CHECK-NEXT:        %measure, %0, %1, %2 = scf.index_switch %index -> i1, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:        case 1 {
// CHECK-NEXT:          %m00, %3, %4, %5 = qstruct.circuit(%qreg0, %qreg0_1, %qreg0_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> i1, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:          ^bb0(%q0: !qcore.qubit, %q1: !qcore.qubit, %q2: !qcore.qubit):
// CHECK-NEXT:            %m0 = qref.measure<ZZZ> (%q0, %q1, %q2) -> i1
// CHECK-NEXT:            qstruct.yield %m0, %q0, %q1, %q2 : i1, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:          }
// CHECK-NEXT:          scf.yield %m00, %3, %4, %5 : i1, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:        }
// CHECK-NEXT:        case 2 {
// CHECK-NEXT:          %m00_1, %6, %7, %8 = qstruct.circuit(%qreg0, %qreg0_1, %qreg0_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> i1, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:          ^bb0(%q0: !qcore.qubit, %q1: !qcore.qubit, %q2: !qcore.qubit):
// CHECK-NEXT:            %m0 = qref.measure<ZZZ> (%q0, %q1, %q2) -> i1
// CHECK-NEXT:            qstruct.yield %m0, %q0, %q1, %q2 : i1, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:          }
// CHECK-NEXT:          scf.yield %m00_1, %6, %7, %8 : i1, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:        }
// CHECK-NEXT:        default {
// CHECK-NEXT:          %m00_2, %9, %10, %11 = qstruct.circuit(%qreg0, %qreg0_1, %qreg0_2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) -> i1, !qcore.qubit, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:          ^bb0(%q0: !qcore.qubit, %q1: !qcore.qubit, %q2: !qcore.qubit):
// CHECK-NEXT:            %m0 = qref.measure<ZZZ> (%q0, %q1, %q2) -> i1
// CHECK-NEXT:            qstruct.yield %m0, %q0, %q1, %q2 : i1, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:          }
// CHECK-NEXT:          scf.yield %m00_2, %9, %10, %11 : i1, !qcore.qubit, !qcore.qubit, !qcore.qubit
// CHECK-NEXT:        }
// CHECK-NEXT:      }
