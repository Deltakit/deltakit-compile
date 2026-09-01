// RUN: deltakit_compile compile-passes -t %s -p convert-parallels-to-lockstep -O %t && filecheck %s --input-file %t

// Test - BOTTOM parallel with 2 regions of same length of 2

builtin.module{
    %qreg0 = "test.op"() : () -> i1
    %qreg1 = "test.op"() : () -> i1
    %qreg0_0, %qreg1_0 = qstruct.circuit(%qreg0, %qreg1 : i1, i1) -> i1, i1 {
    ^bb0(%qreg0_1: i1, %qreg1_1: i1):
        %q0, %q1 = "test.op"(%qreg1_1) : (i1) -> (i1, i1)
        %q2, %q3 = "test.op"(%qreg0_1) : (i1) -> (i1, i1)
        %qreg00, %qreg11 =qstruct.parallel<BOTTOM> -> i1, i1 {
            %qreg0_2 = "test.op"(%q0, %q1) : (i1, i1) -> i1
            qstruct.yield %qreg0_2 : i1
        } {
            %qreg1_2 = "test.op"(%q2, %q3) : (i1, i1) -> i1
            qstruct.yield %qreg1_2 : i1
        }
        qstruct.yield %qreg00, %qreg11 : i1, i1
    }
}

// Should be no changes

// CHECK-NEXT:     builtin.module {
// CHECK-NEXT:       %qreg0 = "test.op"() : () -> i1
// CHECK-NEXT:       %qreg1 = "test.op"() : () -> i1
// CHECK-NEXT:       %qreg0_1, %qreg1_1 = qstruct.circuit(%qreg0, %qreg1 : i1, i1) -> i1, i1 {
// CHECK-NEXT:       ^bb0(%qreg0_2: i1, %qreg1_2: i1):
// CHECK-NEXT:         %q0, %q1 = "test.op"(%qreg1_2) : (i1) -> (i1, i1)
// CHECK-NEXT:         %q2, %q3 = "test.op"(%qreg0_2) : (i1) -> (i1, i1)
// CHECK-NEXT:         %qreg00, %qreg11 = qstruct.parallel<BOTTOM> -> i1, i1 {
// CHECK-NEXT:           %qreg0_3 = "test.op"(%q0, %q1) : (i1, i1) -> i1
// CHECK-NEXT:           qstruct.yield %qreg0_3 : i1
// CHECK-NEXT:         } {
// CHECK-NEXT:           %qreg1_3 = "test.op"(%q2, %q3) : (i1, i1) -> i1
// CHECK-NEXT:           qstruct.yield %qreg1_3 : i1
// CHECK-NEXT:         }
// CHECK-NEXT:         qstruct.yield %qreg00, %qreg11 : i1, i1
// CHECK-NEXT:       }
// CHECK-NEXT:     }


// ----
// CHECK: ----

// Test - BOTTOM parallel with 2 regions of the same length with more than one operation

builtin.module{
    %qreg0 = "test.op"() : () -> i1
    %qreg1 = "test.op"() : () -> i1
    %qreg0_0, %qreg1_0 = qstruct.circuit(%qreg0, %qreg1 : i1, i1) -> i1, i1 {

        // Set up
        // CHECK-NEXT:     builtin.module {
        // CHECK-NEXT:       %qreg0 = "test.op"() : () -> i1
        // CHECK-NEXT:       %qreg1 = "test.op"() : () -> i1
        // CHECK-NEXT:       %qreg0_1, %qreg1_1 = qstruct.circuit(%qreg0, %qreg1 : i1, i1) -> i1, i1 {

    ^bb0(%qreg0_1: i1, %qreg1_1: i1):
        %q0, %q1 = "test.op"(%qreg1_1) : (i1) -> (i1, i1)
        %q2, %q3 = "test.op"(%qreg0_1) : (i1) -> (i1, i1)
        %qreg00, %qreg11 =qstruct.parallel<BOTTOM> -> i1, i1 {
            "test.op"(%q0, %q1) {pos = 1} : (i1, i1) -> ()
            %qreg0_2 = "test.op"(%q0, %q1) {pos = 2}: (i1, i1) -> i1
            qstruct.yield %qreg0_2 : i1
        } {
            "test.op"(%q2, %q3) {pos = 1} : (i1, i1) -> ()
            %qreg1_2 = "test.op"(%q2, %q3) {pos = 2}: (i1, i1) -> i1
            qstruct.yield %qreg1_2 : i1
        }
        qstruct.yield %qreg00, %qreg11 : i1, i1
    }

        // Lockstep
        // CHECK-NEXT:    ^bb0(%qreg0_2: i1, %qreg1_2: i1):
        // CHECK-NEXT:      %q0, %q1 = "test.op"(%qreg1_2) : (i1) -> (i1, i1)
        // CHECK-NEXT:      %q2, %q3 = "test.op"(%qreg0_2) : (i1) -> (i1, i1)
        // CHECK-NEXT:      qstruct.parallel<BOTTOM> -> {
        // CHECK-NEXT:        "test.op"(%q0, %q1) {pos = 1 : i64} : (i1, i1) -> ()
        // CHECK-NEXT:        qstruct.yield
        // CHECK-NEXT:      } {
        // CHECK-NEXT:        "test.op"(%q2, %q3) {pos = 1 : i64} : (i1, i1) -> ()
        // CHECK-NEXT:        qstruct.yield
        // CHECK-NEXT:      }
        // CHECK-NEXT:      %qreg0_3, %qreg1_3 = qstruct.parallel<BOTTOM> -> i1, i1 {
        // CHECK-NEXT:        %qreg0_4 = "test.op"(%q0, %q1) {pos = 2 : i64} : (i1, i1) -> i1
        // CHECK-NEXT:        qstruct.yield %qreg0_4 : i1
        // CHECK-NEXT:      } {
        // CHECK-NEXT:        %qreg1_4 = "test.op"(%q2, %q3) {pos = 2 : i64} : (i1, i1) -> i1
        // CHECK-NEXT:        qstruct.yield %qreg1_4 : i1
        // CHECK-NEXT:      }
        // CHECK-NEXT:        qstruct.yield %qreg0_3, %qreg1_3 : i1, i1
        // CHECK-NEXT:    }

}

// CHECK-NEXT:  }

// ----
// CHECK: ----

// Test - TOP parallel with 2 regions of the same length with more than one operation

builtin.module{
    %qreg0 = "test.op"() : () -> i1
    %qreg1 = "test.op"() : () -> i1
    %qreg0_0, %qreg1_0 = qstruct.circuit(%qreg0, %qreg1 : i1, i1) -> i1, i1 {

    // CHECK-NEXT:      builtin.module {
    // CHECK-NEXT:        %qreg0 = "test.op"() : () -> i1
    // CHECK-NEXT:        %qreg1 = "test.op"() : () -> i1
    // CHECK-NEXT:        %qreg0_1, %qreg1_1 = qstruct.circuit(%qreg0, %qreg1 : i1, i1) -> i1, i1 {

    ^bb0(%qreg0_1: i1, %qreg1_1: i1):
        %q0, %q1 = "test.op"(%qreg1_1) : (i1) -> (i1, i1)
        %q2, %q3 = "test.op"(%qreg0_1) : (i1) -> (i1, i1)
        %qreg00, %qreg11 =qstruct.parallel<TOP> -> i1, i1 {
            "test.op"(%q0, %q1) : (i1, i1) -> ()
            %qreg0_2 = "test.op"(%q0, %q1) : (i1, i1) -> i1
            qstruct.yield %qreg0_2 : i1
        } {
            "test.op"(%q2, %q3) : (i1, i1) -> ()
            %qreg1_2 = "test.op"(%q2, %q3) : (i1, i1) -> i1
            qstruct.yield %qreg1_2 : i1
        }
        qstruct.yield %qreg00, %qreg11 : i1, i1
    }

        // Lockstep

        // CHECK-NEXT:        ^bb0(%qreg0_2: i1, %qreg1_2: i1):
        // CHECK-NEXT:          %q0, %q1 = "test.op"(%qreg1_2) : (i1) -> (i1, i1)
        // CHECK-NEXT:          %q2, %q3 = "test.op"(%qreg0_2) : (i1) -> (i1, i1)
        // CHECK-NEXT:          qstruct.parallel<TOP> -> {
        // CHECK-NEXT:            "test.op"(%q0, %q1) : (i1, i1) -> ()
        // CHECK-NEXT:            qstruct.yield
        // CHECK-NEXT:          } {
        // CHECK-NEXT:            "test.op"(%q2, %q3) : (i1, i1) -> ()
        // CHECK-NEXT:            qstruct.yield
        // CHECK-NEXT:          }
        // CHECK-NEXT:          %qreg0_3, %qreg1_3 = qstruct.parallel<TOP> -> i1, i1 {
        // CHECK-NEXT:            %qreg0_4 = "test.op"(%q0, %q1) : (i1, i1) -> i1
        // CHECK-NEXT:            qstruct.yield %qreg0_4 : i1
        // CHECK-NEXT:          } {
        // CHECK-NEXT:            %qreg1_4 = "test.op"(%q2, %q3) : (i1, i1) -> i1
        // CHECK-NEXT:            qstruct.yield %qreg1_4 : i1
        // CHECK-NEXT:          }
        // CHECK-NEXT:          qstruct.yield %qreg0_3, %qreg1_3 : i1, i1
        // CHECK-NEXT:        }


}

// CHECK-NEXT:      }


// ----
// CHECK: ----

// Test - 3 TOP parallel regions with different lengths

builtin.module{
    %qreg0 = "test.op"() : () -> i1
    %qreg1 = "test.op"() : () -> i1
    %qreg2 = "test.op"() : () -> i1
    %qreg0_0, %qreg1_0, %qreg2_0 = qstruct.circuit(%qreg0, %qreg1, %qreg2 : i1, i1, i1) -> i1, i1, i1 {

    // CHECK-NEXT:   builtin.module {
    // CHECK-NEXT:     %qreg0 = "test.op"() : () -> i1
    // CHECK-NEXT:     %qreg1 = "test.op"() : () -> i1
    // CHECK-NEXT:     %qreg2 = "test.op"() : () -> i1
    // CHECK-NEXT:     %qreg0_1, %qreg1_1, %qreg2_1 = qstruct.circuit(%qreg0, %qreg1, %qreg2 : i1, i1, i1) -> i1, i1, i1 {

    ^bb0(%qreg0_1: i1, %qreg1_1: i1, %qreg2_1: i1):
        %q0, %q1 = "test.op"(%qreg1_1) : (i1) -> (i1, i1)
        %q2, %q3 = "test.op"(%qreg0_1) : (i1) -> (i1, i1)
        %q4, %q5 = "test.op"(%qreg2_1) : (i1) -> (i1, i1)
        %qreg00, %qreg11, %qreg22 =qstruct.parallel<TOP> -> i1, i1, i1 {
            "test.op"() {pos = "A"}: () -> ()
            %qreg0_2 = "test.op"(%q0, %q1) {pos = "B"} : (i1, i1) -> i1
            qstruct.yield %qreg0_2 : i1
        } {
            "test.op"() {pos = "A"}: () -> ()
            "test.op"() {pos = "B"}: () -> ()
            %qreg1_2 = "test.op"(%q2, %q3) {pos = "C"} : (i1, i1) -> i1
            qstruct.yield %qreg1_2 : i1
        } {
            %qreg2_2 = "test.op"(%q4, %q5) {pos = "A"}: (i1, i1) -> i1
            qstruct.yield %qreg2_2 : i1
        }


        // CHECK-NEXT:     ^bb0(%qreg0_2: i1, %qreg1_2: i1, %qreg2_2: i1):
        // CHECK-NEXT:       %q0, %q1 = "test.op"(%qreg1_2) : (i1) -> (i1, i1)
        // CHECK-NEXT:       %q2, %q3 = "test.op"(%qreg0_2) : (i1) -> (i1, i1)
        // CHECK-NEXT:       %q4, %q5 = "test.op"(%qreg2_2) : (i1) -> (i1, i1)
        // CHECK-NEXT:       %qreg2_3 = qstruct.parallel<TOP> -> i1 {
        // CHECK-NEXT:         "test.op"() {pos = "A"} : () -> ()
        // CHECK-NEXT:         qstruct.yield
        // CHECK-NEXT:       } {
        // CHECK-NEXT:         "test.op"() {pos = "A"} : () -> ()
        // CHECK-NEXT:         qstruct.yield
        // CHECK-NEXT:       } {
        // CHECK-NEXT:         %qreg2_4 = "test.op"(%q4, %q5) {pos = "A"} : (i1, i1) -> i1
        // CHECK-NEXT:         qstruct.yield %qreg2_4 : i1
        // CHECK-NEXT:       }
        // CHECK-NEXT:       %qreg0_3 = qstruct.parallel<TOP> -> i1 {
        // CHECK-NEXT:         %qreg0_4 = "test.op"(%q0, %q1) {pos = "B"} : (i1, i1) -> i1
        // CHECK-NEXT:         qstruct.yield %qreg0_4 : i1
        // CHECK-NEXT:       } {
        // CHECK-NEXT:         "test.op"() {pos = "B"} : () -> ()
        // CHECK-NEXT:         qstruct.yield
        // CHECK-NEXT:       }
        // CHECK-NEXT:       %qreg1_3 = "test.op"(%q2, %q3) {pos = "C"} : (i1, i1) -> i1

        qstruct.yield %qreg00, %qreg11, %qreg22 : i1, i1, i1
    }
}

// CHECK-NEXT:       qstruct.yield %qreg2_3, %qreg0_3, %qreg1_3 : i1, i1, i1
// CHECK-NEXT:     }
// CHECK-NEXT:   }

// ----
// CHECK: ----

// Test - 3 BOTTOM parallel regions with different lengths

builtin.module{
    %qreg0 = "test.op"() : () -> i1
    %qreg1 = "test.op"() : () -> i1
    %qreg2 = "test.op"() : () -> i1
    %qreg0_0, %qreg1_0, %qreg2_0 = qstruct.circuit(%qreg0, %qreg1, %qreg2 : i1, i1, i1) -> i1, i1, i1 {

    // CHECK-NEXT: builtin.module {
    // CHECK-NEXT:   %qreg0 = "test.op"() : () -> i1
    // CHECK-NEXT:   %qreg1 = "test.op"() : () -> i1
    // CHECK-NEXT:   %qreg2 = "test.op"() : () -> i1
    // CHECK-NEXT:   %qreg0_1, %qreg1_1, %qreg2_1 = qstruct.circuit(%qreg0, %qreg1, %qreg2 : i1, i1, i1) -> i1, i1, i1 {

    ^bb0(%qreg0_1: i1, %qreg1_1: i1, %qreg2_1: i1):
        %q0, %q1 = "test.op"(%qreg1_1) : (i1) -> (i1, i1)
        %q2, %q3 = "test.op"(%qreg0_1) : (i1) -> (i1, i1)
        %q4, %q5 = "test.op"(%qreg2_1) : (i1) -> (i1, i1)
        %qreg00, %qreg11, %qreg22 =qstruct.parallel<BOTTOM> -> i1, i1, i1 {
            "test.op"() {pos = "B"}: () -> ()
            %qreg0_2 = "test.op"(%q0, %q1) {pos = "A"} : (i1, i1) -> i1
            qstruct.yield %qreg0_2 : i1
        } {
            "test.op"() {pos = "C"}: () -> ()
            "test.op"() {pos = "B"}: () -> ()
            %qreg1_2 = "test.op"(%q2, %q3) {pos = "A"} : (i1, i1) -> i1
            qstruct.yield %qreg1_2 : i1
        } {
            %qreg2_2 = "test.op"(%q4, %q5) {pos = "A"} : (i1, i1) -> i1
            qstruct.yield %qreg2_2 : i1
        }
        qstruct.yield %qreg00, %qreg11, %qreg22 : i1, i1, i1
    }

        // CHECK-NEXT:   ^bb0(%qreg0_2: i1, %qreg1_2: i1, %qreg2_2: i1):
        // CHECK-NEXT:     %q0, %q1 = "test.op"(%qreg1_2) : (i1) -> (i1, i1)
        // CHECK-NEXT:     %q2, %q3 = "test.op"(%qreg0_2) : (i1) -> (i1, i1)
        // CHECK-NEXT:     %q4, %q5 = "test.op"(%qreg2_2) : (i1) -> (i1, i1)
        // CHECK-NEXT:     "test.op"() {pos = "C"} : () -> ()
        // CHECK-NEXT:     qstruct.parallel<BOTTOM> -> {
        // CHECK-NEXT:       "test.op"() {pos = "B"} : () -> ()
        // CHECK-NEXT:       qstruct.yield
        // CHECK-NEXT:     } {
        // CHECK-NEXT:       "test.op"() {pos = "B"} : () -> ()
        // CHECK-NEXT:       qstruct.yield
        // CHECK-NEXT:     }
        // CHECK-NEXT:     %qreg0_3, %qreg1_3, %qreg2_3 = qstruct.parallel<BOTTOM> -> i1, i1, i1 {
        // CHECK-NEXT:       %qreg0_4 = "test.op"(%q0, %q1) {pos = "A"} : (i1, i1) -> i1
        // CHECK-NEXT:       qstruct.yield %qreg0_4 : i1
        // CHECK-NEXT:     } {
        // CHECK-NEXT:       %qreg1_4 = "test.op"(%q2, %q3) {pos = "A"} : (i1, i1) -> i1
        // CHECK-NEXT:       qstruct.yield %qreg1_4 : i1
        // CHECK-NEXT:     } {
        // CHECK-NEXT:       %qreg2_4 = "test.op"(%q4, %q5) {pos = "A"} : (i1, i1) -> i1
        // CHECK-NEXT:       qstruct.yield %qreg2_4 : i1
        // CHECK-NEXT:     }
        // CHECK-NEXT:     qstruct.yield %qreg0_3, %qreg1_3, %qreg2_3 : i1, i1, i1
        // CHECK-NEXT:   }

}

// CHECK-NEXT: }

// ----
// CHECK: ----

// Test - BOTTOM parallel with regions of length 1 and 2


builtin.module{
    %qreg0 = "test.op"() : () -> i1
    %qreg1 = "test.op"() : () -> i1
    %qreg0_0, %qreg1_0 = qstruct.circuit(%qreg0, %qreg1 : i1, i1) -> i1, i1 {

    // CHECK-NEXT:    builtin.module {
    // CHECK-NEXT:      %qreg0 = "test.op"() : () -> i1
    // CHECK-NEXT:      %qreg1 = "test.op"() : () -> i1
    // CHECK-NEXT:      %qreg0_1, %qreg1_1 = qstruct.circuit(%qreg0, %qreg1 : i1, i1) -> i1, i1 {

    ^bb0(%qreg0_1: i1, %qreg1_1: i1):
        %q2, %q3 = "test.op"(%qreg0_1) : (i1) -> (i1, i1)
        %qreg00, %qreg11 =qstruct.parallel<BOTTOM> -> i1, i1 {
            qstruct.yield %qreg1_1 : i1
        } {
            %qreg1_2 = "test.op"(%q2, %q3) {pos = "A"}: (i1, i1) -> i1
            qstruct.yield %qreg1_2 : i1
        }
        qstruct.yield %qreg00, %qreg11 : i1, i1
    }

    // CHECK-NEXT:      ^bb0(%qreg0_2: i1, %qreg1_2: i1):
    // CHECK-NEXT:        %q2, %q3 = "test.op"(%qreg0_2) : (i1) -> (i1, i1)
    // CHECK-NEXT:        %qreg1_3 = "test.op"(%q2, %q3) {pos = "A"} : (i1, i1) -> i1
    // CHECK-NEXT:        qstruct.yield %qreg1_2, %qreg1_3 : i1, i1
    // CHECK-NEXT:      }
}

// CHECK-NEXT:    }

// ----
// CHECK: ----

// Test - TOP parallel with regions of length 1 and 2

builtin.module{
    %qreg0 = "test.op"() : () -> i1
    %qreg1 = "test.op"() : () -> i1
    %qreg0_0, %qreg1_0 = qstruct.circuit(%qreg0, %qreg1 : i1, i1) -> i1, i1 {

    // CHECK-NEXT:    builtin.module {
    // CHECK-NEXT:      %qreg0 = "test.op"() : () -> i1
    // CHECK-NEXT:      %qreg1 = "test.op"() : () -> i1
    // CHECK-NEXT:      %qreg0_1, %qreg1_1 = qstruct.circuit(%qreg0, %qreg1 : i1, i1) -> i1, i1 {

    ^bb0(%qreg0_1: i1, %qreg1_1: i1):
        %q2, %q3 = "test.op"(%qreg0_1) : (i1) -> (i1, i1)
        %qreg00, %qreg11 =qstruct.parallel<TOP> -> i1, i1 {
            qstruct.yield %qreg1_1 : i1
        } {
            %qreg1_2 = "test.op"(%q2, %q3) {pos = "A"}: (i1, i1) -> i1
            qstruct.yield %qreg1_2 : i1
        }
        qstruct.yield %qreg00, %qreg11 : i1, i1
    }

    // CHECK-NEXT:      ^bb0(%qreg0_2: i1, %qreg1_2: i1):
    // CHECK-NEXT:        %q2, %q3 = "test.op"(%qreg0_2) : (i1) -> (i1, i1)
    // CHECK-NEXT:        %qreg1_3 = "test.op"(%q2, %q3) {pos = "A"} : (i1, i1) -> i1
    // CHECK-NEXT:        qstruct.yield %qreg1_2, %qreg1_3 : i1, i1
    // CHECK-NEXT:      }

}



// CHECK-NEXT:    }

// ----
// CHECK: ----

// Test - operation that shares SSA name between regions and is brought out of its region

builtin.module {
    %qreg0 = "test.op"() : () -> i1
    %qreg1 = "test.op"() : () -> i1
    %qq1 = "test.op"() : () -> i1

    // CHECK-NEXT:    builtin.module {
    // CHECK-NEXT:      %qreg0 = "test.op"() : () -> i1
    // CHECK-NEXT:      %qreg1 = "test.op"() : () -> i1
    // CHECK-NEXT:      %qq1 = "test.op"() : () -> i1

    %qreg0_4, %qreg1_4 = qstruct.parallel<BOTTOM> -> i1, i1 {
        %q0, %q1 = "test.op"(%qreg0) {pos = "B"}: (i1) -> (i1, i1)
        %qreg0_0 = "test.op"(%q0, %q1) {pos = "A"} : (i1, i1) -> i1
        qstruct.yield %qreg0_0 : i1
    } {
        %q0, %q1 = "test.op"(%qreg1) {pos = "A"}: (i1) -> (i1, i1)
        qstruct.yield %qreg1 : i1
    }

    // CHECK-NEXT:      %q0, %q1 = "test.op"(%qreg0) {pos = "B"} : (i1) -> (i1, i1)
    // CHECK-NEXT:      %qreg0_1, %q0_1, %q1_1 = qstruct.parallel<BOTTOM> -> i1, i1, i1 {
    // CHECK-NEXT:        %qreg0_2 = "test.op"(%q0, %q1) {pos = "A"} : (i1, i1) -> i1
    // CHECK-NEXT:        qstruct.yield %qreg0_2 : i1
    // CHECK-NEXT:      } {
    // CHECK-NEXT:        %q0_2, %q1_2 = "test.op"(%qreg1) {pos = "A"} : (i1) -> (i1, i1)
    // CHECK-NEXT:        qstruct.yield %q0_2, %q1_2 : i1, i1
    // CHECK-NEXT:      }

}

// CHECK-NEXT:    }

// ----
// CHECK: ----

// Test - one circuit in each regionare composed together with BOTTOM alignment

builtin.module {
    %qreg0 = "test.op"() : () -> i1
    %qreg1 = "test.op"() : () -> i1
    %qq1 = "test.op"() : () -> i1

    // CHECK-NEXT:    builtin.module {
    // CHECK-NEXT:      %qreg0 = "test.op"() : () -> i1
    // CHECK-NEXT:      %qreg1 = "test.op"() : () -> i1
    // CHECK-NEXT:      %qq1 = "test.op"() : () -> i1

    %qreg0_4, %qreg1_4, %qq1_1 = qstruct.parallel<BOTTOM> -> i1, i1, i1 {
        // Circuit 1
        %qreg0_3 = qstruct.circuit(%qreg0 : i1) -> i1 {
        ^bb0(%qreg0_1: i1):
            %q0, %q1= "test.op"(%qreg0_1) {pos = "D"}: (i1) -> (i1, i1)
            %m0, %m1 = "test.op"(%q0, %q1) {pos = "C"}: (i1, i1)  -> (i1, i1)
            %d0 = "test.op"(%m0, %m1) {pos = "B"}: (i1, i1) -> i1
            %qreg0_2 = "test.op"(%q0, %q1) {pos = "A"}: (i1, i1) -> i1
            qstruct.yield %qreg0_2 : i1
        }
        // End of circuit 1
        qstruct.yield %qreg0_3 : i1
    } {
        // Circuit 2
        %qreg1_3, %qqq_1 = qstruct.circuit(%qreg1, %qq1 : i1, i1) -> i1, i1 {
        ^bb1(%qreg1_1: i1, %qq_1: i1):
            %q0, %q1 = "test.op"(%qreg1_1) {pos = "E"}: (i1) -> (i1, i1)
            "test.op"(%q0, %q1) {pos = "D"}: (i1, i1) -> ()
            %m0, %m1 = "test.op"(%q0, %q1) {pos = "C"}: (i1, i1)  -> (i1, i1)
            %d0 = "test.op"(%m0, %m1) {pos = "B"}: (i1, i1) -> i1
            %qreg1_2 = "test.op"(%q0, %q1) {pos = "A"}: (i1, i1) -> i1
            qstruct.yield %qreg1_2, %qq_1 : i1, i1
        }
        // End of circuit 2
        qstruct.yield %qreg1_3, %qqq_1 : i1, i1
    }

    // CHECK-NEXT:      %qreg0_1, %qreg1_1, %qqq = qstruct.circuit(%qreg0, %qreg1, %qq1 : i1, i1, i1) -> i1, i1, i1 {
    // CHECK-NEXT:      ^bb0(%qreg0_2: i1, %qreg1_2: i1, %qq: i1):
    // CHECK-NEXT:        %q0, %q1 = "test.op"(%qreg1_2) {pos = "E"} : (i1) -> (i1, i1)
    // CHECK-NEXT:        %q0_1, %q1_1 = qstruct.parallel<BOTTOM> -> i1, i1 {
    // CHECK-NEXT:          %q0_2, %q1_2 = "test.op"(%qreg0_2) {pos = "D"} : (i1) -> (i1, i1)
    // CHECK-NEXT:          qstruct.yield %q0_2, %q1_2 : i1, i1
    // CHECK-NEXT:        } {
    // CHECK-NEXT:          "test.op"(%q0, %q1) {pos = "D"} : (i1, i1) -> ()
    // CHECK-NEXT:          qstruct.yield
    // CHECK-NEXT:        }
    // CHECK-NEXT:        %m0, %m1, %m0_1, %m1_1 = qstruct.parallel<BOTTOM> -> i1, i1, i1, i1 {
    // CHECK-NEXT:          %m0_2, %m1_2 = "test.op"(%q0_1, %q1_1) {pos = "C"} : (i1, i1) -> (i1, i1)
    // CHECK-NEXT:          qstruct.yield %m0_2, %m1_2 : i1, i1
    // CHECK-NEXT:        } {
    // CHECK-NEXT:          %m0_3, %m1_3 = "test.op"(%q0, %q1) {pos = "C"} : (i1, i1) -> (i1, i1)
    // CHECK-NEXT:          qstruct.yield %m0_3, %m1_3 : i1, i1
    // CHECK-NEXT:        }
    // CHECK-NEXT:        %d0, %d0_1 = qstruct.parallel<BOTTOM> -> i1, i1 {
    // CHECK-NEXT:          %d0_2 = "test.op"(%m0, %m1) {pos = "B"} : (i1, i1) -> i1
    // CHECK-NEXT:          qstruct.yield %d0_2 : i1
    // CHECK-NEXT:        } {
    // CHECK-NEXT:          %d0_3 = "test.op"(%m0_1, %m1_1) {pos = "B"} : (i1, i1) -> i1
    // CHECK-NEXT:          qstruct.yield %d0_3 : i1
    // CHECK-NEXT:        }
    // CHECK-NEXT:        %qreg0_3, %qreg1_3 = qstruct.parallel<BOTTOM> -> i1, i1 {
    // CHECK-NEXT:          %qreg0_4 = "test.op"(%q0_1, %q1_1) {pos = "A"} : (i1, i1) -> i1
    // CHECK-NEXT:          qstruct.yield %qreg0_4 : i1
    // CHECK-NEXT:        } {
    // CHECK-NEXT:          %qreg1_4 = "test.op"(%q0, %q1) {pos = "A"} : (i1, i1) -> i1
    // CHECK-NEXT:          qstruct.yield %qreg1_4 : i1
    // CHECK-NEXT:        }
    // CHECK-NEXT:        qstruct.yield %qreg0_3, %qreg1_3, %qq : i1, i1, i1
    // CHECK-NEXT:      }

}

// CHECK-NEXT:    }

// ----

// CHECK: ----

// Test - one circuit in each region are composed together with TOP alignment

builtin.module {
    %qreg0 = "test.op"() : () -> i1
    %qreg1 = "test.op"() : () -> i1
    %qq1 = "test.op"() : () -> i1

    // CHECK-NEXT:    builtin.module {
    // CHECK-NEXT:      %qreg0 = "test.op"() : () -> i1
    // CHECK-NEXT:      %qreg1 = "test.op"() : () -> i1
    // CHECK-NEXT:      %qq1 = "test.op"() : () -> i1

    %qreg0_4, %qreg1_4, %qq1_1 = qstruct.parallel<TOP> -> i1, i1, i1 {
        // Circuit 1
        %qreg0_3 = qstruct.circuit(%qreg0 : i1) -> i1 {
        ^bb0(%qreg0_1: i1):
            %q0, %q1= "test.op"(%qreg0_1) {pos = "A"}: (i1) -> (i1, i1)
            %m0, %m1 = "test.op"(%q0, %q1) {pos = "B"}: (i1, i1) -> (i1, i1)
            %d0 = "test.op"(%m0, %m1) {pos = "C"}: (i1, i1) -> i1
            %qreg0_2 = "test.op"(%q0, %q1) {pos = "D"}: (i1, i1) -> i1
            qstruct.yield %qreg0_2 : i1
        }
        // End of circuit 1
        qstruct.yield %qreg0_3 : i1
    } {
        // Circuit 2
        %qreg1_3, %qqq_1 = qstruct.circuit(%qreg1, %qq1 : i1, i1) -> i1, i1 {
        ^bb1(%qreg1_1: i1, %qq_1: i1):
            %q0, %q1 = "test.op"(%qreg1_1) {pos = "A"}: (i1) -> (i1, i1)
            "test.op"(%q0, %q1) {pos = "B"}: (i1, i1) -> ()
            %m0, %m1 = "test.op"(%q0, %q1) {pos = "C"}: (i1, i1) -> (i1, i1)
            %d0 = "test.op"(%m0, %m1) {pos = "D"}: (i1, i1) -> i1
            %qreg1_2 = "test.op"(%q0, %q1) {pos = "E"}: (i1, i1) -> i1
            qstruct.yield %qreg1_2, %qq_1 : i1, i1
        }
        // End of circuit 2
        qstruct.yield %qreg1_3, %qqq_1 : i1, i1
    }

    // CHECK-NEXT:      %qreg0_1, %qreg1_1, %qqq = qstruct.circuit(%qreg0, %qreg1, %qq1 : i1, i1, i1) -> i1, i1, i1 {
    // CHECK-NEXT:      ^bb0(%qreg0_2: i1, %qreg1_2: i1, %qq: i1):
    // CHECK-NEXT:        %q0, %q1, %q0_1, %q1_1 = qstruct.parallel<TOP> -> i1, i1, i1, i1 {
    // CHECK-NEXT:          %q0_2, %q1_2 = "test.op"(%qreg0_2) {pos = "A"} : (i1) -> (i1, i1)
    // CHECK-NEXT:          qstruct.yield %q0_2, %q1_2 : i1, i1
    // CHECK-NEXT:        } {
    // CHECK-NEXT:          %q0_3, %q1_3 = "test.op"(%qreg1_2) {pos = "A"} : (i1) -> (i1, i1)
    // CHECK-NEXT:          qstruct.yield %q0_3, %q1_3 : i1, i1
    // CHECK-NEXT:        }
    // CHECK-NEXT:        %m0, %m1 = qstruct.parallel<TOP> -> i1, i1 {
    // CHECK-NEXT:          %m0_1, %m1_1 = "test.op"(%q0, %q1) {pos = "B"} : (i1, i1) -> (i1, i1)
    // CHECK-NEXT:          qstruct.yield %m0_1, %m1_1 : i1, i1
    // CHECK-NEXT:        } {
    // CHECK-NEXT:          "test.op"(%q0_1, %q1_1) {pos = "B"} : (i1, i1) -> ()
    // CHECK-NEXT:          qstruct.yield
    // CHECK-NEXT:        }
    // CHECK-NEXT:        %d0, %m0_2, %m1_2 = qstruct.parallel<TOP> -> i1, i1, i1 {
    // CHECK-NEXT:          %d0_1 = "test.op"(%m0, %m1) {pos = "C"} : (i1, i1) -> i1
    // CHECK-NEXT:          qstruct.yield %d0_1 : i1
    // CHECK-NEXT:        } {
    // CHECK-NEXT:          %m0_3, %m1_3 = "test.op"(%q0_1, %q1_1) {pos = "C"} : (i1, i1) -> (i1, i1)
    // CHECK-NEXT:          qstruct.yield %m0_3, %m1_3 : i1, i1
    // CHECK-NEXT:        }
    // CHECK-NEXT:        %qreg0_3, %d0_2 = qstruct.parallel<TOP> -> i1, i1 {
    // CHECK-NEXT:          %qreg0_4 = "test.op"(%q0, %q1) {pos = "D"} : (i1, i1) -> i1
    // CHECK-NEXT:          qstruct.yield %qreg0_4 : i1
    // CHECK-NEXT:        } {
    // CHECK-NEXT:          %d0_3 = "test.op"(%m0_2, %m1_2) {pos = "D"} : (i1, i1) -> i1
    // CHECK-NEXT:          qstruct.yield %d0_3 : i1
    // CHECK-NEXT:        }
    // CHECK-NEXT:        %qreg1_3 = "test.op"(%q0_1, %q1_1) {pos = "E"} : (i1, i1) -> i1
    // CHECK-NEXT:        qstruct.yield %qreg0_3, %qreg1_3, %qq : i1, i1, i1
    // CHECK-NEXT:      }

}

// CHECK-NEXT:    }

// ----
// CHECK: ----

// Test - two circuits in each region are composed together with BOTTOM alignment

builtin.module {
    %qreg0 = "test.op"() : () -> i1
    %qreg1 = "test.op"() : () -> i1
    %qq1 = "test.op"() : () -> i1

    // CHECK-NEXT:    builtin.module {
    // CHECK-NEXT:      %qreg0 = "test.op"() : () -> i1
    // CHECK-NEXT:      %qreg1 = "test.op"() : () -> i1
    // CHECK-NEXT:      %qq1 = "test.op"() : () -> i1

    %qreg0_4, %qreg1_4, %qq1_1 = qstruct.parallel<BOTTOM> -> i1, i1, i1 {
        // Circuit 1
        %qreg0_3 = qstruct.circuit(%qreg0 : i1) -> i1 {
        ^bb0(%qreg0_1: i1):
            %q0, %q1= "test.op"(%qreg0_1) {pos = "D"}: (i1) -> (i1, i1)
            %m0, %m1 = "test.op"(%q0, %q1) {pos = "C"}: (i1, i1) -> (i1, i1)
            %d0 = "test.op"(%m0, %m1) {pos = "B"}: (i1, i1) -> i1
            %qreg0_2 = "test.op"(%q0, %q1) {pos = "A"}: (i1, i1) -> i1
            qstruct.yield %qreg0_2 : i1
        }
        // End of circuit 1
        // Circuit 2
        %qreg00_3 = qstruct.circuit(%qreg0_3 : i1) -> i1 {
        ^bb0(%qreg0_1: i1):
            %q0, %q1= "test.op"(%qreg0_1) {pos = "D"}: (i1) -> (i1, i1)
            %m0, %m1 = "test.op"(%q0, %q1) {pos = "C"}: (i1, i1) -> (i1, i1)
            %d0 = "test.op"(%m0, %m1) {pos = "B"}: (i1, i1) -> i1
            %qreg0_2 = "test.op"(%q0, %q1) {pos = "A"}: (i1, i1) -> i1
            qstruct.yield %qreg0_2 : i1
        }
        // End of circuit 2
        qstruct.yield %qreg00_3 : i1
    } {
        // Circuit 1
        %qreg1_3, %qqq_1 = qstruct.circuit(%qreg1, %qq1 : i1, i1) -> i1, i1 {
        ^bb1(%qreg1_1: i1, %qq_1: i1):
            %q0, %q1 = "test.op"(%qreg1_1) {pos = "E"}: (i1) -> (i1, i1)
            "test.op"(%q0, %q1) {pos = "D"}: (i1, i1) -> ()
            %m0, %m1 = "test.op"(%q0, %q1) {pos = "C"}: (i1, i1) -> (i1, i1)
            %d0 = "test.op"(%m0, %m1) {pos = "B"}: (i1, i1) -> i1
            %qreg1_2 = "test.op"(%q0, %q1) {pos = "A"}: (i1, i1) -> i1
            qstruct.yield %qreg1_2, %qq_1 : i1, i1
        }
        // End of circuit 1
        // Circuit 2
        %qreg11_3, %qqq_11 = qstruct.circuit(%qreg1_3, %qqq_1 : i1, i1) -> i1, i1 {
        ^bb1(%qreg1_1: i1, %qq_1: i1):
            %q0, %q1 = "test.op"(%qreg1_1) {pos = "E"}: (i1) -> (i1, i1)
            "test.op"(%q0, %q1) {pos = "D"}: (i1, i1) -> ()
            %m0, %m1 = "test.op"(%q0, %q1) {pos = "C"}: (i1, i1) -> (i1, i1)
            %d0 = "test.op"(%m0, %m1) {pos = "B"}: (i1, i1) -> i1
            %qreg1_2 = "test.op"(%q0, %q1) {pos = "A"}: (i1, i1) -> i1
            qstruct.yield %qreg1_2, %qq_1 : i1, i1
        }
        // End of circuit 2
        qstruct.yield %qreg11_3, %qqq_11 : i1, i1
    }

    // CHECK-NEXT:      %qreg0_1, %qreg1_1, %qqq = qstruct.circuit(%qreg0, %qreg1, %qq1 : i1, i1, i1) -> i1, i1, i1 {
    // CHECK-NEXT:      ^bb0(%qreg0_2: i1, %qreg1_2: i1, %qq: i1):
    // CHECK-NEXT:        %q0, %q1 = "test.op"(%qreg1_2) {pos = "E"} : (i1) -> (i1, i1)
    // CHECK-NEXT:        %q0_1, %q1_1 = qstruct.parallel<BOTTOM> -> i1, i1 {
    // CHECK-NEXT:          %q0_2, %q1_2 = "test.op"(%qreg0_2) {pos = "D"} : (i1) -> (i1, i1)
    // CHECK-NEXT:          qstruct.yield %q0_2, %q1_2 : i1, i1
    // CHECK-NEXT:        } {
    // CHECK-NEXT:          "test.op"(%q0, %q1) {pos = "D"} : (i1, i1) -> ()
    // CHECK-NEXT:          qstruct.yield
    // CHECK-NEXT:        }
    // CHECK-NEXT:        %m0, %m1, %m0_1, %m1_1 = qstruct.parallel<BOTTOM> -> i1, i1, i1, i1 {
    // CHECK-NEXT:          %m0_2, %m1_2 = "test.op"(%q0_1, %q1_1) {pos = "C"} : (i1, i1) -> (i1, i1)
    // CHECK-NEXT:          qstruct.yield %m0_2, %m1_2 : i1, i1
    // CHECK-NEXT:        } {
    // CHECK-NEXT:          %m0_3, %m1_3 = "test.op"(%q0, %q1) {pos = "C"} : (i1, i1) -> (i1, i1)
    // CHECK-NEXT:          qstruct.yield %m0_3, %m1_3 : i1, i1
    // CHECK-NEXT:        }
    // CHECK-NEXT:        %d0, %d0_1 = qstruct.parallel<BOTTOM> -> i1, i1 {
    // CHECK-NEXT:          %d0_2 = "test.op"(%m0, %m1) {pos = "B"} : (i1, i1) -> i1
    // CHECK-NEXT:          qstruct.yield %d0_2 : i1
    // CHECK-NEXT:        } {
    // CHECK-NEXT:          %d0_3 = "test.op"(%m0_1, %m1_1) {pos = "B"} : (i1, i1) -> i1
    // CHECK-NEXT:          qstruct.yield %d0_3 : i1
    // CHECK-NEXT:        }
    // CHECK-NEXT:        %qreg0_3, %qreg1_3 = qstruct.parallel<BOTTOM> -> i1, i1 {
    // CHECK-NEXT:          %qreg0_4 = "test.op"(%q0_1, %q1_1) {pos = "A"} : (i1, i1) -> i1
    // CHECK-NEXT:          qstruct.yield %qreg0_4 : i1
    // CHECK-NEXT:        } {
    // CHECK-NEXT:          %qreg1_4 = "test.op"(%q0, %q1) {pos = "A"} : (i1, i1) -> i1
    // CHECK-NEXT:          qstruct.yield %qreg1_4 : i1
    // CHECK-NEXT:        }
    // CHECK-NEXT:        qstruct.yield %qreg0_3, %qreg1_3, %qq : i1, i1, i1
    // CHECK-NEXT:      }
    // CHECK-NEXT:      %qreg00, %qreg11, %qqq_1 = qstruct.circuit(%qreg0_1, %qreg1_1, %qqq : i1, i1, i1) -> i1, i1, i1 {
    // CHECK-NEXT:      ^bb0(%qreg0_2: i1, %qreg1_2: i1, %qq: i1):
    // CHECK-NEXT:        %q0, %q1 = "test.op"(%qreg1_2) {pos = "E"} : (i1) -> (i1, i1)
    // CHECK-NEXT:        %q0_1, %q1_1 = qstruct.parallel<BOTTOM> -> i1, i1 {
    // CHECK-NEXT:          %q0_2, %q1_2 = "test.op"(%qreg0_2) {pos = "D"} : (i1) -> (i1, i1)
    // CHECK-NEXT:          qstruct.yield %q0_2, %q1_2 : i1, i1
    // CHECK-NEXT:        } {
    // CHECK-NEXT:          "test.op"(%q0, %q1) {pos = "D"} : (i1, i1) -> ()
    // CHECK-NEXT:          qstruct.yield
    // CHECK-NEXT:        }
    // CHECK-NEXT:        %m0, %m1, %m0_1, %m1_1 = qstruct.parallel<BOTTOM> -> i1, i1, i1, i1 {
    // CHECK-NEXT:          %m0_2, %m1_2 = "test.op"(%q0_1, %q1_1) {pos = "C"} : (i1, i1) -> (i1, i1)
    // CHECK-NEXT:          qstruct.yield %m0_2, %m1_2 : i1, i1
    // CHECK-NEXT:        } {
    // CHECK-NEXT:          %m0_3, %m1_3 = "test.op"(%q0, %q1) {pos = "C"} : (i1, i1) -> (i1, i1)
    // CHECK-NEXT:          qstruct.yield %m0_3, %m1_3 : i1, i1
    // CHECK-NEXT:        }
    // CHECK-NEXT:        %d0, %d0_1 = qstruct.parallel<BOTTOM> -> i1, i1 {
    // CHECK-NEXT:          %d0_2 = "test.op"(%m0, %m1) {pos = "B"} : (i1, i1) -> i1
    // CHECK-NEXT:          qstruct.yield %d0_2 : i1
    // CHECK-NEXT:        } {
    // CHECK-NEXT:          %d0_3 = "test.op"(%m0_1, %m1_1) {pos = "B"} : (i1, i1) -> i1
    // CHECK-NEXT:          qstruct.yield %d0_3 : i1
    // CHECK-NEXT:        }
    // CHECK-NEXT:        %qreg0_3, %qreg1_3 = qstruct.parallel<BOTTOM> -> i1, i1 {
    // CHECK-NEXT:          %qreg0_4 = "test.op"(%q0_1, %q1_1) {pos = "A"} : (i1, i1) -> i1
    // CHECK-NEXT:          qstruct.yield %qreg0_4 : i1
    // CHECK-NEXT:        } {
    // CHECK-NEXT:          %qreg1_4 = "test.op"(%q0, %q1) {pos = "A"} : (i1, i1) -> i1
    // CHECK-NEXT:          qstruct.yield %qreg1_4 : i1
    // CHECK-NEXT:        }
    // CHECK-NEXT:        qstruct.yield %qreg0_3, %qreg1_3, %qq : i1, i1, i1
    // CHECK-NEXT:      }

}

// CHECK-NEXT:    }

// ----
// CHECK: ----

// Test - two sequential parallels with one circuit in each region with different parallel alignments

builtin.module {
    %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    %qreg1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    %qq1 = qcore.alloc_qubit -> !qcore.qubit

    // CHECK-NEXT:      builtin.module {
    // CHECK-NEXT:        %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    // CHECK-NEXT:        %qreg1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    // CHECK-NEXT:        %qq1 = qcore.alloc_qubit -> !qcore.qubit

    %qreg0_4, %qreg1_4, %qq1_1 = qstruct.parallel<BOTTOM> -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2>, !qcore.qubit {
        // Circuit 1
        %qreg0_3 = qstruct.circuit(%qreg0 : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
        ^bb0(%qreg0_1: !qcore.qubit_reg<2>):
            %q0, %q1= qcore.unpack_qubit_reg(%qreg0_1 : !qcore.qubit_reg<2>) {pos = "D"}
            %m0, %m1 = qref.measure<Z>(%q0, %q1) {pos = "C"} -> i1, i1
            %d0 = qec.detector(%m0, %m1) {pos = "B"}
            %qreg0_2 = qcore.pack_qubit_reg(%q0, %q1) {pos = "A"} -> !qcore.qubit_reg<2>
            qstruct.yield %qreg0_2 : !qcore.qubit_reg<2>
        }
        // End of circuit 1
        qstruct.yield %qreg0_3 : !qcore.qubit_reg<2>
    } {
        // Circuit 2
        %qreg1_3, %qqq_1 = qstruct.circuit(%qreg1, %qq1 : !qcore.qubit_reg<2>, !qcore.qubit) -> !qcore.qubit_reg<2>, !qcore.qubit {
        ^bb1(%qreg1_1: !qcore.qubit_reg<2>, %qq_1: !qcore.qubit):
            %q0, %q1 = qcore.unpack_qubit_reg(%qreg1_1 : !qcore.qubit_reg<2>) {pos = "E"}
            qref.gate<#qcore.gate.h>(%q0, %q1) {pos = "D"}
            %m0, %m1 = qref.measure<Z>(%q0, %q1) {pos = "C"} -> i1, i1
            %d0 = qec.detector(%m0, %m1) {pos = "B"}
            %qreg1_2 = qcore.pack_qubit_reg(%q0, %q1) {pos = "A"} -> !qcore.qubit_reg<2>
            qstruct.yield %qreg1_2, %qq_1 : !qcore.qubit_reg<2>, !qcore.qubit
        }
        // End of circuit 2
        qstruct.yield %qreg1_3, %qqq_1 : !qcore.qubit_reg<2>, !qcore.qubit
    }

    // CHECK-NEXT:        %qreg0_1, %qreg1_1, %qqq = qstruct.circuit(%qreg0, %qreg1, %qq1 : !qcore.qubit_reg<2>, !qcore.qubit_reg<2>, !qcore.qubit) -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2>, !qcore.qubit {
    // CHECK-NEXT:        ^bb0(%qreg0_2: !qcore.qubit_reg<2>, %qreg1_2: !qcore.qubit_reg<2>, %qq: !qcore.qubit):
    // CHECK-NEXT:          %q0, %q1 = qcore.unpack_qubit_reg(%qreg1_2 : !qcore.qubit_reg<2>) {pos = "E"}
    // CHECK-NEXT:          %q0_1, %q1_1 = qstruct.parallel<BOTTOM> -> !qcore.qubit, !qcore.qubit {
    // CHECK-NEXT:            %q0_2, %q1_2 = qcore.unpack_qubit_reg(%qreg0_2 : !qcore.qubit_reg<2>) {pos = "D"}
    // CHECK-NEXT:            qstruct.yield %q0_2, %q1_2 : !qcore.qubit, !qcore.qubit
    // CHECK-NEXT:          } {
    // CHECK-NEXT:            qref.gate<#qcore.gate.h> (%q0, %q1) {pos = "D"}
    // CHECK-NEXT:            qstruct.yield
    // CHECK-NEXT:          }
    // CHECK-NEXT:          %m0, %m1, %m0_1, %m1_1 = qstruct.parallel<BOTTOM> -> i1, i1, i1, i1 {
    // CHECK-NEXT:            %m0_2, %m1_2 = qref.measure<Z> (%q0_1, %q1_1) {pos = "C"} -> i1, i1
    // CHECK-NEXT:            qstruct.yield %m0_2, %m1_2 : i1, i1
    // CHECK-NEXT:          } {
    // CHECK-NEXT:            %m0_3, %m1_3 = qref.measure<Z> (%q0, %q1) {pos = "C"} -> i1, i1
    // CHECK-NEXT:            qstruct.yield %m0_3, %m1_3 : i1, i1
    // CHECK-NEXT:          }
    // CHECK-NEXT:          %d0, %d0_1 = qstruct.parallel<BOTTOM> -> !qec.detector_ref, !qec.detector_ref {
    // CHECK-NEXT:            %d0_2 = qec.detector(%m0, %m1) {pos = "B"}
    // CHECK-NEXT:            qstruct.yield %d0_2 : !qec.detector_ref
    // CHECK-NEXT:          } {
    // CHECK-NEXT:            %d0_3 = qec.detector(%m0_1, %m1_1) {pos = "B"}
    // CHECK-NEXT:            qstruct.yield %d0_3 : !qec.detector_ref
    // CHECK-NEXT:          }
    // CHECK-NEXT:          %qreg0_3, %qreg1_3 = qstruct.parallel<BOTTOM> -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2> {
    // CHECK-NEXT:            %qreg0_4 = qcore.pack_qubit_reg(%q0_1, %q1_1) {pos = "A"} -> !qcore.qubit_reg<2>
    // CHECK-NEXT:            qstruct.yield %qreg0_4 : !qcore.qubit_reg<2>
    // CHECK-NEXT:          } {
    // CHECK-NEXT:            %qreg1_4 = qcore.pack_qubit_reg(%q0, %q1) {pos = "A"} -> !qcore.qubit_reg<2>
    // CHECK-NEXT:            qstruct.yield %qreg1_4 : !qcore.qubit_reg<2>
    // CHECK-NEXT:          }
    // CHECK-NEXT:          qstruct.yield %qreg0_3, %qreg1_3, %qq : !qcore.qubit_reg<2>, !qcore.qubit_reg<2>, !qcore.qubit
    // CHECK-NEXT:        }

    // Parallel circuit with TOP alignment
    %qreg00, %qreg01 = qstruct.parallel<TOP> -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2> {
        // Circuit 1
        %qreg0_3 = qstruct.circuit(%qreg0_4 : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
        ^bb0(%qreg0_1: !qcore.qubit_reg<2>):
            %q0, %q1= qcore.unpack_qubit_reg(%qreg0_1 : !qcore.qubit_reg<2>) {pos = "A"}
            %m0, %m1 = qref.measure<Z>(%q0, %q1) {pos = "B"} -> i1, i1
            %d0 = qec.detector(%m0, %m1) {pos = "C"}
            %qreg0_2 = qcore.pack_qubit_reg(%q0, %q1) {pos = "D"} -> !qcore.qubit_reg<2>
            qstruct.yield %qreg0_2 : !qcore.qubit_reg<2>
        }
        // End of circuit 1
        qstruct.yield %qreg0_3 : !qcore.qubit_reg<2>
    } {
        // Circuit 2
        %qreg1_3, %qqq_1 = qstruct.circuit(%qreg1_4, %qq1_1 : !qcore.qubit_reg<2>, !qcore.qubit)
                    -> !qcore.qubit_reg<2>, !qcore.qubit {
        ^bb1(%qreg1_1: !qcore.qubit_reg<2>, %qq_1: !qcore.qubit):
            %q0, %q1 = qcore.unpack_qubit_reg(%qreg1_1 : !qcore.qubit_reg<2>) {pos = "A"}
            qref.gate<#qcore.gate.h>(%q0, %q1) {pos = "B"}
            %m0, %m1 = qref.measure<Z>(%q0, %q1) {pos = "C"} -> i1, i1
            %d0 = qec.detector(%m0, %m1) {pos = "D"}
            %qreg1_2 = qcore.pack_qubit_reg(%q0, %q1) {pos = "E"} -> !qcore.qubit_reg<2>
            qstruct.yield %qreg1_2, %qq_1 : !qcore.qubit_reg<2>, !qcore.qubit
        }
        // End of circuit 2
        qstruct.yield %qreg1_3 : !qcore.qubit_reg<2>
    }

    // CHECK-NEXT:        %qreg0_2, %qreg1_2, %qqq_1 = qstruct.circuit(%qreg0_1, %qreg1_1, %qqq : !qcore.qubit_reg<2>, !qcore.qubit_reg<2>, !qcore.qubit) -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2>, !qcore.qubit {
    // CHECK-NEXT:        ^bb0(%qreg0_3: !qcore.qubit_reg<2>, %qreg1_3: !qcore.qubit_reg<2>, %qq: !qcore.qubit):
    // CHECK-NEXT:          %q0, %q1, %q0_1, %q1_1 = qstruct.parallel<TOP> -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
    // CHECK-NEXT:            %q0_2, %q1_2 = qcore.unpack_qubit_reg(%qreg0_3 : !qcore.qubit_reg<2>) {pos = "A"}
    // CHECK-NEXT:            qstruct.yield %q0_2, %q1_2 : !qcore.qubit, !qcore.qubit
    // CHECK-NEXT:          } {
    // CHECK-NEXT:            %q0_3, %q1_3 = qcore.unpack_qubit_reg(%qreg1_3 : !qcore.qubit_reg<2>) {pos = "A"}
    // CHECK-NEXT:            qstruct.yield %q0_3, %q1_3 : !qcore.qubit, !qcore.qubit
    // CHECK-NEXT:          }
    // CHECK-NEXT:          %m0, %m1 = qstruct.parallel<TOP> -> i1, i1 {
    // CHECK-NEXT:            %m0_1, %m1_1 = qref.measure<Z> (%q0, %q1) {pos = "B"} -> i1, i1
    // CHECK-NEXT:            qstruct.yield %m0_1, %m1_1 : i1, i1
    // CHECK-NEXT:          } {
    // CHECK-NEXT:            qref.gate<#qcore.gate.h> (%q0_1, %q1_1) {pos = "B"}
    // CHECK-NEXT:            qstruct.yield
    // CHECK-NEXT:          }
    // CHECK-NEXT:          %d0, %m0_2, %m1_2 = qstruct.parallel<TOP> -> !qec.detector_ref, i1, i1 {
    // CHECK-NEXT:            %d0_1 = qec.detector(%m0, %m1) {pos = "C"}
    // CHECK-NEXT:            qstruct.yield %d0_1 : !qec.detector_ref
    // CHECK-NEXT:          } {
    // CHECK-NEXT:            %m0_3, %m1_3 = qref.measure<Z> (%q0_1, %q1_1) {pos = "C"} -> i1, i1
    // CHECK-NEXT:            qstruct.yield %m0_3, %m1_3 : i1, i1
    // CHECK-NEXT:          }
    // CHECK-NEXT:          %qreg0_4, %d0_2 = qstruct.parallel<TOP> -> !qcore.qubit_reg<2>, !qec.detector_ref {
    // CHECK-NEXT:            %qreg0_5 = qcore.pack_qubit_reg(%q0, %q1) {pos = "D"} -> !qcore.qubit_reg<2>
    // CHECK-NEXT:            qstruct.yield %qreg0_5 : !qcore.qubit_reg<2>
    // CHECK-NEXT:          } {
    // CHECK-NEXT:            %d0_3 = qec.detector(%m0_2, %m1_2) {pos = "D"}
    // CHECK-NEXT:            qstruct.yield %d0_3 : !qec.detector_ref
    // CHECK-NEXT:          }
    // CHECK-NEXT:          %qreg1_4 = qcore.pack_qubit_reg(%q0_1, %q1_1) {pos = "E"} -> !qcore.qubit_reg<2>
    // CHECK-NEXT:          qstruct.yield %qreg0_4, %qreg1_4, %qq : !qcore.qubit_reg<2>, !qcore.qubit_reg<2>, !qcore.qubit
    // CHECK-NEXT:        }

}

// CHECK-NEXT:      }

// ----
// CHECK: ----

// Test - nested parallels

builtin.module {
    %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    %qreg1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    %qq1 = qcore.alloc_qubit -> !qcore.qubit

    // CHECK-NEXT:      builtin.module {
    // CHECK-NEXT:        %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    // CHECK-NEXT:        %qreg1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    // CHECK-NEXT:        %qq1 = qcore.alloc_qubit -> !qcore.qubit

    %q00_1, %q00_2, %qreg1_4, %qq1_1 = qstruct.parallel<BOTTOM> -> !qcore.qubit, !qcore.qubit, !qcore.qubit_reg<2>, !qcore.qubit {
            %q0, %q1= qcore.unpack_qubit_reg(%qreg0 : !qcore.qubit_reg<2>) {pos = "B1"}
            %q00, %q11 = qstruct.parallel<BOTTOM> {pos = "A1"} -> !qcore.qubit, !qcore.qubit {
                // Inner circuit 1
                %q000_1 = qstruct.circuit(%q0 : !qcore.qubit) -> !qcore.qubit {
                ^bb0(%q0_1: !qcore.qubit):
                    qref.gate<#qcore.gate.h>(%q0_1) {pos = "A2"}
                    qstruct.yield %q0_1 : !qcore.qubit
                }
                qstruct.yield %q000_1 : !qcore.qubit
                } {
                // Inner circuit 2
                %q111_1 = qstruct.circuit(%q1 : !qcore.qubit) -> !qcore.qubit {
                ^bb0(%q1_1: !qcore.qubit):
                    qref.gate<#qcore.gate.h>(%q1_1) {pos = "A2"}
                    qstruct.yield %q1_1 : !qcore.qubit
                }
                qstruct.yield %q111_1 : !qcore.qubit
            }

        // End of inner circuits
        qstruct.yield %q00, %q11 : !qcore.qubit, !qcore.qubit

    } {
        // Other circuit in parallel
        %qreg1_3, %qqq_1 = qstruct.circuit(%qreg1, %qq1 : !qcore.qubit_reg<2>, !qcore.qubit) -> !qcore.qubit_reg<2>, !qcore.qubit {
        ^bb1(%qreg1_1: !qcore.qubit_reg<2>, %qq_1: !qcore.qubit):
            %q0, %q1 = qcore.unpack_qubit_reg(%qreg1_1 : !qcore.qubit_reg<2>) {pos = "C2"}
            qref.gate<#qcore.gate.h>(%q0, %q1) {pos = "B2"}
            %qreg1_2 = qcore.pack_qubit_reg(%q0, %q1) {pos = "A2"} -> !qcore.qubit_reg<2>
            qstruct.yield %qreg1_2, %qq_1 : !qcore.qubit_reg<2>, !qcore.qubit
        }
        qstruct.yield %qreg1_3, %qqq_1 : !qcore.qubit_reg<2>, !qcore.qubit
    }
}

// CHECK-NEXT:        %q0, %q1 = qcore.unpack_qubit_reg(%qreg0 : !qcore.qubit_reg<2>) {pos = "B1"}
// CHECK-NEXT:        %q000, %q111, %qreg1_1, %qqq = qstruct.circuit(%q0, %q1, %qreg1, %qq1 : !qcore.qubit, !qcore.qubit, !qcore.qubit_reg<2>, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit_reg<2>, !qcore.qubit {
// CHECK-NEXT:        ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit, %qreg1_2: !qcore.qubit_reg<2>, %qq: !qcore.qubit):
// CHECK-NEXT:          %q0_2, %q1_2 = qcore.unpack_qubit_reg(%qreg1_2 : !qcore.qubit_reg<2>) {pos = "C2"}
// CHECK-NEXT:          qref.gate<#qcore.gate.h> (%q0_2, %q1_2) {pos = "B2"}
// CHECK-NEXT:          %qreg1_3 = qstruct.parallel<BOTTOM> -> !qcore.qubit_reg<2> {
// CHECK-NEXT:            qref.gate<#qcore.gate.h> (%q0_1) {pos = "A2"}
// CHECK-NEXT:            qstruct.yield
// CHECK-NEXT:          } {
// CHECK-NEXT:            qref.gate<#qcore.gate.h> (%q1_1) {pos = "A2"}
// CHECK-NEXT:            qstruct.yield
// CHECK-NEXT:          } {
// CHECK-NEXT:            %qreg1_4 = qcore.pack_qubit_reg(%q0_2, %q1_2) {pos = "A2"} -> !qcore.qubit_reg<2>
// CHECK-NEXT:            qstruct.yield %qreg1_4 : !qcore.qubit_reg<2>
// CHECK-NEXT:          }
// CHECK-NEXT:          qstruct.yield %q0_1, %q1_1, %qreg1_3, %qq : !qcore.qubit, !qcore.qubit, !qcore.qubit_reg<2>, !qcore.qubit
// CHECK-NEXT:        }
// CHECK-NEXT:      }

// ----
// CHECK: ----

// Test - circuit in parallel with non circuit

builtin.module {
    %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    %qreg1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    %qq1 = qcore.alloc_qubit -> !qcore.qubit

    // CHECK-NEXT:      builtin.module {
    // CHECK-NEXT:        %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    // CHECK-NEXT:        %qreg1 = qcore.alloc_qubit -> !qcore.qubit_reg<2>
    // CHECK-NEXT:        %qq1 = qcore.alloc_qubit -> !qcore.qubit

    %qreg0_4, %qreg1_4, %qq1_1 = qstruct.parallel<TOP> -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2>, !qcore.qubit {
        // Circuit 1
        %q00, %q11 = qcore.unpack_qubit_reg(%qreg0 : !qcore.qubit_reg<2>) {pos = "A"}
        %qreg00 = qcore.pack_qubit_reg(%q00, %q11) {pos = "B"} -> !qcore.qubit_reg<2>
        %qreg0_3 = qstruct.circuit(%qreg00 : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
        ^bb0(%qreg0_1: !qcore.qubit_reg<2>):
            %q0, %q1= qcore.unpack_qubit_reg(%qreg0_1 : !qcore.qubit_reg<2>) {pos = "A"}
            %m0, %m1 = qref.measure<Z>(%q0, %q1) {pos = "B"} -> i1, i1
            %d0 = qec.detector(%m0, %m1) {pos = "C"}
            %qreg0_2 = qcore.pack_qubit_reg(%q0, %q1) {pos = "D"} -> !qcore.qubit_reg<2>
            qstruct.yield %qreg0_2 : !qcore.qubit_reg<2>
        }
        // End of circuit 1
        qstruct.yield %qreg0_3 : !qcore.qubit_reg<2>
    } {
        // Circuit 2
        %qreg1_3, %qqq_1 = qstruct.circuit(%qreg1, %qq1 : !qcore.qubit_reg<2>, !qcore.qubit) -> !qcore.qubit_reg<2>, !qcore.qubit {
        ^bb1(%qreg1_1: !qcore.qubit_reg<2>, %qq_1: !qcore.qubit):
            %q0, %q1 = qcore.unpack_qubit_reg(%qreg1_1 : !qcore.qubit_reg<2>) {pos = "A"}
            qref.gate<#qcore.gate.h>(%q0, %q1) {pos = "B"}
            %m0, %m1 = qref.measure<Z>(%q0, %q1) {pos = "C"} -> i1, i1
            %d0 = qec.detector(%m0, %m1) {pos = "D"}
            %qreg1_2 = qcore.pack_qubit_reg(%q0, %q1) {pos = "E"} -> !qcore.qubit_reg<2>
            qstruct.yield %qreg1_2, %qq_1 : !qcore.qubit_reg<2>, !qcore.qubit
        }
        // End of circuit 2
        %q0, %q1 = qcore.unpack_qubit_reg(%qreg1_3 : !qcore.qubit_reg<2>) {pos = "B"}
        %qreg11 = qcore.pack_qubit_reg(%q0, %q1) {pos = "C"} -> !qcore.qubit_reg<2>
        qstruct.yield %qreg11, %qqq_1 : !qcore.qubit_reg<2>, !qcore.qubit
    }

    "test.op"(%qreg0_4, %qreg1_4, %qq1_1) {}: (!qcore.qubit_reg<2>, !qcore.qubit_reg<2>, !qcore.qubit) -> ()

// CHECK-NEXT:      %q00, %q11, %qreg1_1, %qqq = qstruct.parallel<TOP> -> !qcore.qubit, !qcore.qubit, !qcore.qubit_reg<2>, !qcore.qubit {
// CHECK-NEXT:        %q00_1, %q11_1 = qcore.unpack_qubit_reg(%qreg0 : !qcore.qubit_reg<2>) {pos = "A"}
// CHECK-NEXT:        qstruct.yield %q00_1, %q11_1 : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      } {
// CHECK-NEXT:        %qreg1_2, %qqq_1 = qstruct.circuit(%qreg1, %qq1 : !qcore.qubit_reg<2>, !qcore.qubit) -> !qcore.qubit_reg<2>, !qcore.qubit {
// CHECK-NEXT:        ^bb0(%qreg1_3: !qcore.qubit_reg<2>, %qq: !qcore.qubit):
// CHECK-NEXT:          %q0, %q1 = qcore.unpack_qubit_reg(%qreg1_3 : !qcore.qubit_reg<2>) {pos = "A"}
// CHECK-NEXT:          qref.gate<#qcore.gate.h> (%q0, %q1) {pos = "B"}
// CHECK-NEXT:          %m0, %m1 = qref.measure<Z> (%q0, %q1) {pos = "C"} -> i1, i1
// CHECK-NEXT:          %d0 = qec.detector(%m0, %m1) {pos = "D"}
// CHECK-NEXT:          %qreg1_4 = qcore.pack_qubit_reg(%q0, %q1) {pos = "E"} -> !qcore.qubit_reg<2>
// CHECK-NEXT:          qstruct.yield %qreg1_4, %qq : !qcore.qubit_reg<2>, !qcore.qubit
// CHECK-NEXT:        }
// CHECK-NEXT:        qstruct.yield %qreg1_2, %qqq_1 : !qcore.qubit_reg<2>, !qcore.qubit
// CHECK-NEXT:      }
// CHECK-NEXT:      %qreg00, %q0, %q1 = qstruct.parallel<TOP> -> !qcore.qubit_reg<2>, !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:        %qreg00_1 = qcore.pack_qubit_reg(%q00, %q11) {pos = "B"} -> !qcore.qubit_reg<2>
// CHECK-NEXT:        qstruct.yield %qreg00_1 : !qcore.qubit_reg<2>
// CHECK-NEXT:      } {
// CHECK-NEXT:        %q0_1, %q1_1 = qcore.unpack_qubit_reg(%qreg1_1 : !qcore.qubit_reg<2>) {pos = "B"}
// CHECK-NEXT:        qstruct.yield %q0_1, %q1_1 : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:      }
// CHECK-NEXT:      %qreg11, %qreg0_1 = qstruct.parallel<TOP> -> !qcore.qubit_reg<2>, !qcore.qubit_reg<2> {
// CHECK-NEXT:        %qreg11_1 = qcore.pack_qubit_reg(%q0, %q1) {pos = "C"} -> !qcore.qubit_reg<2>
// CHECK-NEXT:        qstruct.yield %qreg11_1 : !qcore.qubit_reg<2>
// CHECK-NEXT:      } {
// CHECK-NEXT:        %qreg0_2 = qstruct.circuit(%qreg00 : !qcore.qubit_reg<2>) -> !qcore.qubit_reg<2> {
// CHECK-NEXT:        ^bb0(%qreg0_3: !qcore.qubit_reg<2>):
// CHECK-NEXT:          %q0_2, %q1_2 = qcore.unpack_qubit_reg(%qreg0_3 : !qcore.qubit_reg<2>) {pos = "A"}
// CHECK-NEXT:          %m0, %m1 = qref.measure<Z> (%q0_2, %q1_2) {pos = "B"} -> i1, i1
// CHECK-NEXT:          %d0 = qec.detector(%m0, %m1) {pos = "C"}
// CHECK-NEXT:          %qreg0_4 = qcore.pack_qubit_reg(%q0_2, %q1_2) {pos = "D"} -> !qcore.qubit_reg<2>
// CHECK-NEXT:          qstruct.yield %qreg0_4 : !qcore.qubit_reg<2>
// CHECK-NEXT:        }
// CHECK-NEXT:        qstruct.yield %qreg0_2 : !qcore.qubit_reg<2>
// CHECK-NEXT:      }
// CHECK-NEXT:      "test.op"(%qreg0_1, %qreg11, %qqq) : (!qcore.qubit_reg<2>, !qcore.qubit_reg<2>, !qcore.qubit) -> ()

}

// CHECK-NEXT:      }

// ----
// CHECK: ----

// Test nested  with TOP and BOTTOM parallels

builtin.module {
    %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<5>
    %qreg0_3 = qstruct.circuit(%qreg0 : !qcore.qubit_reg<5>) {pos = "B"} -> !qcore.qubit_reg<5> {
    ^bb0(%qreg0_1: !qcore.qubit_reg<5>):
        %q0, %q1, %q2, %q3, %q4 = qcore.unpack_qubit_reg(%qreg0_1 : !qcore.qubit_reg<5>) {pos = "C"}

// CHECK-NEXT:       builtin.module {
// CHECK-NEXT:         %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<5>
// CHECK-NEXT:         %qreg0_1 = qstruct.circuit(%qreg0 : !qcore.qubit_reg<5>) {pos = "B"} -> !qcore.qubit_reg<5> {
// CHECK-NEXT:         ^bb0(%qreg0_2: !qcore.qubit_reg<5>):
// CHECK-NEXT:           %q0, %q1, %q2, %q3, %q4 = qcore.unpack_qubit_reg(%qreg0_2 : !qcore.qubit_reg<5>) {pos = "C"}


        qstruct.parallel<TOP> {pos = "B"} -> {
            qref.gate<#qcore.gate.h>(%q0) {pos = "A"}
            qstruct.yield
        } {
            qref.gate<#qcore.gate.h>(%q1) {pos = "A"}
            qstruct.yield
        } {
            qstruct.parallel<BOTTOM> {pos = "B"} -> {
                qref.gate<#qcore.gate.h>(%q2) {pos = "A"}
                qref.gate<#qcore.gate.h>(%q2) {pos = "B"}
                qstruct.yield
            } {
                qref.gate<#qcore.gate.h>(%q3) {pos = "B"}
                qstruct.yield
            } {
                qref.gate<#qcore.gate.h>(%q4) {pos = "B"}
                qstruct.yield
            }
            qstruct.yield
        }

// CHECK-NEXT:           qstruct.parallel<TOP> -> {
// CHECK-NEXT:             qref.gate<#qcore.gate.h> (%q0) {pos = "A"}
// CHECK-NEXT:             qstruct.yield
// CHECK-NEXT:           } {
// CHECK-NEXT:             qref.gate<#qcore.gate.h> (%q1) {pos = "A"}
// CHECK-NEXT:             qstruct.yield
// CHECK-NEXT:           } {
// CHECK-NEXT:             qref.gate<#qcore.gate.h> (%q2) {pos = "A"}
// CHECK-NEXT:             qstruct.yield
// CHECK-NEXT:           }
// CHECK-NEXT:           qstruct.parallel<BOTTOM> -> {
// CHECK-NEXT:             qref.gate<#qcore.gate.h> (%q2) {pos = "B"}
// CHECK-NEXT:             qstruct.yield
// CHECK-NEXT:           } {
// CHECK-NEXT:             qref.gate<#qcore.gate.h> (%q3) {pos = "B"}
// CHECK-NEXT:             qstruct.yield
// CHECK-NEXT:           } {
// CHECK-NEXT:             qref.gate<#qcore.gate.h> (%q4) {pos = "B"}
// CHECK-NEXT:             qstruct.yield
// CHECK-NEXT:           }

        %qreg0_2 = qcore.pack_qubit_reg(%q0, %q1, %q2, %q3, %q4) {pos = "D"} -> !qcore.qubit_reg<5>
        qstruct.yield %qreg0_2 : !qcore.qubit_reg<5>
    }
}

// CHECK-NEXT:           %qreg0_3 = qcore.pack_qubit_reg(%q0, %q1, %q2, %q3, %q4) {pos = "D"} -> !qcore.qubit_reg<5>
// CHECK-NEXT:           qstruct.yield %qreg0_3 : !qcore.qubit_reg<5>
// CHECK-NEXT:         }
// CHECK-NEXT:       }

// ----
// CHECK: ----

// Test nested with TOP and TOP parallels

builtin.module {
    %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<5>
    %qreg0_3 = qstruct.circuit(%qreg0 : !qcore.qubit_reg<5>) {pos = "B"} -> !qcore.qubit_reg<5> {
    ^bb0(%qreg0_1: !qcore.qubit_reg<5>):
        %q0, %q1, %q2, %q3, %q4 = qcore.unpack_qubit_reg(%qreg0_1 : !qcore.qubit_reg<5>) {pos = "C"}

// CHECK-NEXT:       builtin.module {
// CHECK-NEXT:         %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<5>
// CHECK-NEXT:         %qreg0_1 = qstruct.circuit(%qreg0 : !qcore.qubit_reg<5>) {pos = "B"} -> !qcore.qubit_reg<5> {
// CHECK-NEXT:         ^bb0(%qreg0_2: !qcore.qubit_reg<5>):
// CHECK-NEXT:           %q0, %q1, %q2, %q3, %q4 = qcore.unpack_qubit_reg(%qreg0_2 : !qcore.qubit_reg<5>) {pos = "C"}


        qstruct.parallel<TOP> {pos = "B"} -> {
            qref.gate<#qcore.gate.h>(%q0) {pos = "A"}
            qstruct.yield
        } {
            qref.gate<#qcore.gate.h>(%q1) {pos = "A"}
            qstruct.yield
        } {
            qstruct.parallel<TOP> {pos = "A"} -> {
                qref.gate<#qcore.gate.h>(%q2) {pos = "A"}
                qref.gate<#qcore.gate.h>(%q2) {pos = "B"}
                qstruct.yield
            } {
                qref.gate<#qcore.gate.h>(%q3) {pos = "A"}
                qstruct.yield
            } {
                qref.gate<#qcore.gate.h>(%q4) {pos = "A"}
                qstruct.yield
            }
            qstruct.yield
        }

// CHECK-NEXT:           qstruct.parallel<TOP> -> {
// CHECK-NEXT:             qref.gate<#qcore.gate.h> (%q0) {pos = "A"}
// CHECK-NEXT:             qstruct.yield
// CHECK-NEXT:           } {
// CHECK-NEXT:             qref.gate<#qcore.gate.h> (%q1) {pos = "A"}
// CHECK-NEXT:             qstruct.yield
// CHECK-NEXT:           } {
// CHECK-NEXT:             qref.gate<#qcore.gate.h> (%q2) {pos = "A"}
// CHECK-NEXT:             qstruct.yield
// CHECK-NEXT:           } {
// CHECK-NEXT:             qref.gate<#qcore.gate.h> (%q3) {pos = "A"}
// CHECK-NEXT:             qstruct.yield
// CHECK-NEXT:           } {
// CHECK-NEXT:             qref.gate<#qcore.gate.h> (%q4) {pos = "A"}
// CHECK-NEXT:             qstruct.yield
// CHECK-NEXT:           }
// CHECK-NEXT:           qref.gate<#qcore.gate.h> (%q2) {pos = "B"}

        %qreg0_2 = qcore.pack_qubit_reg(%q0, %q1, %q2, %q3, %q4) {pos = "D"} -> !qcore.qubit_reg<5>
        qstruct.yield %qreg0_2 : !qcore.qubit_reg<5>
    }
}

// CHECK-NEXT:           %qreg0_3 = qcore.pack_qubit_reg(%q0, %q1, %q2, %q3, %q4) {pos = "D"} -> !qcore.qubit_reg<5>
// CHECK-NEXT:           qstruct.yield %qreg0_3 : !qcore.qubit_reg<5>
// CHECK-NEXT:         }
// CHECK-NEXT:       }

// ----
// CHECK: ----

// Parallel with repeat nested in parallel - note nested parallel cannot be converted to lockstep
// as it is nested within a repeat

builtin.module {
    %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<5>
    %qreg0_3 = qstruct.circuit(%qreg0 : !qcore.qubit_reg<5>) {pos = "B"} -> !qcore.qubit_reg<5> {
    ^bb0(%qreg0_1: !qcore.qubit_reg<5>):
        %q0, %q1, %q2, %q3, %q4 = qcore.unpack_qubit_reg(%qreg0_1 : !qcore.qubit_reg<5>) {pos = "C"}

// CHECK-NEXT:       builtin.module {
// CHECK-NEXT:         %qreg0 = qcore.alloc_qubit -> !qcore.qubit_reg<5>
// CHECK-NEXT:         %qreg0_1 = qstruct.circuit(%qreg0 : !qcore.qubit_reg<5>) {pos = "B"} -> !qcore.qubit_reg<5> {
// CHECK-NEXT:         ^bb0(%qreg0_2: !qcore.qubit_reg<5>):
// CHECK-NEXT:           %q0, %q1, %q2, %q3, %q4 = qcore.unpack_qubit_reg(%qreg0_2 : !qcore.qubit_reg<5>) {pos = "C"}


        qstruct.parallel<TOP> {pos = "B"} -> {
            qref.gate<#qcore.gate.h>(%q0) {pos = "A"}
            qstruct.yield
        } {
            qref.gate<#qcore.gate.h>(%q1) {pos = "A"}
            qstruct.yield
        } {
            qstruct.repeat<7> -> {
                qstruct.parallel<TOP> -> {
                    qref.gate<#qcore.gate.h>(%q2) {pos = "A"}
                    qref.gate<#qcore.gate.h>(%q2) {pos = "B"}
                    qstruct.yield
                } {
                    qref.gate<#qcore.gate.h>(%q3) {pos = "A"}
                    qstruct.yield
                } {
                    qref.gate<#qcore.gate.h>(%q4) {pos = "A"}
                    qstruct.yield
                }
                qstruct.yield
            }
            qstruct.yield
        }

// CHECK-NEXT:           qstruct.parallel<TOP> {pos = "B"} -> {
// CHECK-NEXT:             qref.gate<#qcore.gate.h> (%q0) {pos = "A"}
// CHECK-NEXT:             qstruct.yield
// CHECK-NEXT:           } {
// CHECK-NEXT:             qref.gate<#qcore.gate.h> (%q1) {pos = "A"}
// CHECK-NEXT:             qstruct.yield
// CHECK-NEXT:           } {
// CHECK-NEXT:             qstruct.repeat<7> () -> {
// CHECK-NEXT:               qstruct.parallel<TOP> -> {
// CHECK-NEXT:                 qref.gate<#qcore.gate.h> (%q2) {pos = "A"}
// CHECK-NEXT:                 qstruct.yield
// CHECK-NEXT:               } {
// CHECK-NEXT:                 qref.gate<#qcore.gate.h> (%q3) {pos = "A"}
// CHECK-NEXT:                 qstruct.yield
// CHECK-NEXT:               } {
// CHECK-NEXT:                 qref.gate<#qcore.gate.h> (%q4) {pos = "A"}
// CHECK-NEXT:                 qstruct.yield
// CHECK-NEXT:               }
// CHECK-NEXT:               qref.gate<#qcore.gate.h> (%q2) {pos = "B"}
// CHECK-NEXT:               qstruct.yield
// CHECK-NEXT:             }
// CHECK-NEXT:             qstruct.yield
// CHECK-NEXT:           }

        %qreg0_2 = qcore.pack_qubit_reg(%q0, %q1, %q2, %q3, %q4) {pos = "D"} -> !qcore.qubit_reg<5>
        qstruct.yield %qreg0_2 : !qcore.qubit_reg<5>
    }
}

// CHECK-NEXT:           %qreg0_3 = qcore.pack_qubit_reg(%q0, %q1, %q2, %q3, %q4) {pos = "D"} -> !qcore.qubit_reg<5>
// CHECK-NEXT:           qstruct.yield %qreg0_3 : !qcore.qubit_reg<5>
// CHECK-NEXT:         }
// CHECK-NEXT:       }
