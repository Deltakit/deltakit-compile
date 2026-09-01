// RUN: deltakit_compile compile-passes -t %s -p stim-to-qec -O %t && filecheck %s --input-file %t

// No repeats - two rounds of detectors

builtin.module {
  qstruct.circuit -> {


// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   qstruct.circuit -> {

    stim.shift_coord <[0.0, 0.0, 1.0]>

  // CHECK-NEXT:   qec.detector_round()

    %a = arith.constant 1 : i1

    stim.detector <[1.0, 0.0, 0.0]> (%a: i1) {stim.tag = "a"}
    stim.detector <[3.0, 0.0, 0.0]> (:)
    stim.detector <[3.0, 0.0, 3.0]> (:)
    stim.detector <[3.0, 0.0, 7.0]> (:)

// CHECK-NEXT:     %a = arith.constant true
// CHECK-NEXT:     %0 = qec.detector<[1.0, 0.0]> (%a) {stim.tag = "a"}
// CHECK-NEXT:     %1 = qec.detector<[3.0, 0.0]> ()
// CHECK-NEXT:     %2 = qec.detector<[3.0, 0.0]> ()
// CHECK-NEXT:     %3 = qec.detector<[3.0, 0.0]> ()


    stim.shift_coord <[0.0, 0.0, 4.0]>

// CHECK-NEXT:     qec.detector_round(%0, %1)
// CHECK-NEXT:     qec.detector_round()
// CHECK-NEXT:     qec.detector_round()
// CHECK-NEXT:     qec.detector_round(%2)

    stim.detector <[1.0, 0.0, 1.0]> (:)

// CHECK-NEXT:     %4 = qec.detector<[1.0, 0.0]> ()

    stim.detector <[3.0, 0.0, 0.0]> (:)
    stim.detector <> (:)
    stim.shift_coord <[]>

// CHECK-NEXT:     %5 = qec.detector<[3.0, 0.0]> ()
// CHECK-NEXT:     %6 = qec.detector()
// CHECK-NEXT:     qec.detector_round(%5)
// CHECK-NEXT:     qec.detector_round(%4)
// CHECK-NEXT:     qec.detector_round()
// CHECK-NEXT:     qec.detector_round(%3)
// CHECK-NEXT:     qstruct.yield

    qstruct.yield
  }
}

// CHECK-NEXT:   }
// CHECK-NEXT: }

// ----
// CHECK-NEXT: ----

builtin.module{
  qstruct.circuit -> {
    stim.shift_coord <[0.0, 0.0, 1.0]>
    stim.detector <[1.0, 0.0, 0.0]> (:)
    stim.shift_coord <[0.0, 0.0, 1.0]>
    qstruct.yield
  }
}

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   qstruct.circuit -> {
// CHECK-NEXT:     qec.detector_round()
// CHECK-NEXT:     %0 = qec.detector<[1.0, 0.0]> ()
// CHECK-NEXT:     qec.detector_round(%0)
// CHECK-NEXT:     qstruct.yield
// CHECK-NEXT:   }
// CHECK-NEXT: }

// ----
// CHECK: ----

// Detector before repeat in round after repeat

builtin.module {
  %q0 = qcore.alloc_qubit<> -> !qcore.qubit
  %q1 = qstruct.circuit(%q0: !qcore.qubit) -> !qcore.qubit {
  ^bb0(%q0_1: !qcore.qubit):
    %1 = qref.measure<Z> (%q0_1) -> i1
    stim.detector <[0.0, 0.0, 7.0]> (:)
    stim.detector <[0.0, 0.0, 10.0]> (:)
    %0 = qstruct.repeat<3> (%1 : i1) -> i1 {
    ^bb0(%2: i1):
      stim.detector <[0.0, 0.0, 1.0]> (:)
      stim.detector <[0.0, 0.0, 1.0]> (%2 : i1)
      stim.detector <[0.0, 0.0, 2.0]> (:)
      stim.detector <[0.0, 0.0, 4.0]> (:)
      stim.detector <[0.0, 0.0, 3.0]> (:)
      stim.shift_coord <[0.0, 0.0, 2.0]>
      qstruct.yield %2 : i1
    }
    stim.detector <[0.0, 0.0, 0.0]> (:)
    qstruct.yield %q0_1 : !qcore.qubit
  }
}

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:   %q1 = qstruct.circuit(%q0 : !qcore.qubit) -> !qcore.qubit {
// CHECK-NEXT:   ^bb0(%q0_1: !qcore.qubit):
// CHECK-NEXT:     %0 = qref.measure<Z> (%q0_1) -> i1
// CHECK-NEXT:     %1 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:     %2 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:     %3 = qec.detector()
// CHECK-NEXT:     %4 = qec.detector()
// CHECK-NEXT:     %5 = qec.detector()
// CHECK-NEXT:     %6 = qec.detector()
// CHECK-NEXT:     %7, %8, %9, %10, %11 = qstruct.repeat<3> (%6, %5, %4, %3, %0 : !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, i1) -> !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, i1 {
// CHECK-NEXT:     ^bb1(%12: !qec.detector_ref, %13: !qec.detector_ref, %14: !qec.detector_ref, %15: !qec.detector_ref, %16: i1):
// CHECK-NEXT:       %17 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:       %18 = qec.detector<[0.0, 0.0]> (%16)
// CHECK-NEXT:       %19 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:       %20 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:       %21 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:       qec.detector_round(%12, %13)
// CHECK-NEXT:       qec.detector_round(%14, %17, %18)
// CHECK-NEXT:       qstruct.yield %15, %19, %21, %20, %16 : !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, i1
// CHECK-NEXT:     }
// CHECK-NEXT:     %22 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:     qec.detector_round(%7, %8, %22)
// CHECK-NEXT:     qec.detector_round(%1, %9)
// CHECK-NEXT:     qec.detector_round(%10)
// CHECK-NEXT:     qec.detector_round()
// CHECK-NEXT:     qec.detector_round(%2)
// CHECK-NEXT:     qstruct.yield %q0_1 : !qcore.qubit
// CHECK-NEXT:   }
// CHECK-NEXT: }

// ----
// CHECK: ----


// 2 sequential repeats for detectors

builtin.module {
  %q0 = qcore.alloc_qubit<> -> !qcore.qubit
  %q1 = qstruct.circuit(%q0: !qcore.qubit) -> !qcore.qubit {
  ^bb0(%q0_1: !qcore.qubit):
    stim.shift_coord <[0.0, 0.0, 1.0]>
    stim.detector <[0.0, 0.0, 5.0]> (:)
    stim.detector <[0.0, 0.0, 1.0]> (:)
    stim.detector <[0.0, 0.0, 1.0]> (:)
    %1 = qref.measure<Z> (%q0_1) -> i1
    %0 = qstruct.repeat<3> (%1 : i1) -> i1 {
    ^bb0(%2: i1):
      stim.detector <[0.0, 0.0, 1.0]> (:)
      stim.detector <[0.0, 0.0, 0.0]> (%2 : i1)
      stim.detector <[0.0, 0.0, 2.0]> (:)
      stim.detector <[0.0, 0.0, 4.0]> (:)
      stim.detector <[0.0, 0.0, 3.0]> (:)
      stim.shift_coord <[0.0, 0.0, 2.0]>
      qstruct.yield %2 : i1
    }
    qstruct.repeat<2> () -> {
      stim.detector <[0.0, 0.0, 0.0]> (:)
      stim.detector <[0.0, 0.0, 1.0]> (:)
      stim.detector <[0.0, 0.0, 1.0]> (:)
      stim.shift_coord <[0.0, 0.0, 1.0]>
      qstruct.yield
    }
    qstruct.yield %q0_1 : !qcore.qubit
  }
}

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:   %q1 = qstruct.circuit(%q0 : !qcore.qubit) -> !qcore.qubit {
// CHECK-NEXT:   ^bb0(%q0_1: !qcore.qubit):
// CHECK-NEXT:     qec.detector_round()
// CHECK-NEXT:     %0 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:     %1 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:     %2 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:     %3 = qref.measure<Z> (%q0_1) -> i1
// CHECK-NEXT:     %4 = qec.detector()
// CHECK-NEXT:     %5 = qec.detector()
// CHECK-NEXT:     %6 = qec.detector()
// CHECK-NEXT:     %7 = qec.detector()
// CHECK-NEXT:     %8, %9, %10, %11, %12, %13, %14, %15 = qstruct.repeat<3> (%7, %6, %2, %1, %5, %4, %0, %3 : !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, i1) -> !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, i1 {
// CHECK-NEXT:     ^bb1(%16: !qec.detector_ref, %17: !qec.detector_ref, %18: !qec.detector_ref, %19: !qec.detector_ref, %20: !qec.detector_ref, %21: !qec.detector_ref, %22: !qec.detector_ref, %23: i1):
// CHECK-NEXT:       %24 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:       %25 = qec.detector<[0.0, 0.0]> (%23)
// CHECK-NEXT:       %26 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:       %27 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:       %28 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:       qec.detector_round(%16, %17, %25)
// CHECK-NEXT:       qec.detector_round(%18, %19, %24)
// CHECK-NEXT:       %29 = qec.detector()
// CHECK-NEXT:       qstruct.yield %20, %26, %21, %28, %27, %22, %29, %23 : !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, i1
// CHECK-NEXT:     }
// CHECK-NEXT:     %30 = qec.detector()
// CHECK-NEXT:     %31, %32, %33, %34 = qstruct.repeat<2> (%30, %9, %8, %11 : !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref) -> !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref {
// CHECK-NEXT:     ^bb2(%35: !qec.detector_ref, %36: !qec.detector_ref, %37: !qec.detector_ref, %38: !qec.detector_ref):
// CHECK-NEXT:       %39 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:       %40 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:       %41 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:       qec.detector_round(%35, %36, %37, %39)
// CHECK-NEXT:       %42 = qec.detector()
// CHECK-NEXT:       qstruct.yield %38, %40, %41, %42 : !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref
// CHECK-NEXT:     }
// CHECK-NEXT:     qec.detector_round(%12, %32, %33)
// CHECK-NEXT:     qstruct.yield %q0_1 : !qcore.qubit
// CHECK-NEXT:   }
// CHECK-NEXT: }

// ----
// CHECK: ----

// Nested repeat for detectors

builtin.module {
  qstruct.circuit -> {
    stim.detector <[0.0, 0.0, 0.0]> (:)
    stim.shift_coord <[0.0, 0.0, 2.0]>
    stim.detector <[0.0, 0.0, 0.0]> (:)

// CHECK-NEXT:  builtin.module {
// CHECK-NEXT:    qstruct.circuit -> {
// CHECK-NEXT:      %0 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:      qec.detector_round(%0)
// CHECK-NEXT:      qec.detector_round()
// CHECK-NEXT:      %1 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:      %2 = qec.detector()

    qstruct.repeat<3> () -> {
      qstruct.repeat<2> () -> {
        stim.detector <[0.0, 0.0, 0.0]> (:)
        stim.detector <[0.0, 0.0, 2.0]> (:)
        stim.shift_coord <[0.0, 0.0, 1.0]>
        qstruct.yield
      }
      stim.detector <[0.0, 0.0, 0.0]> (:)
      stim.detector <[0.0, 0.0, 2.0]> (:)
      stim.shift_coord <[0.0, 0.0, 1.0]>
      qstruct.yield
    }
    qstruct.yield
  }
}

// CHECK-NEXT:      %3, %4 = qstruct.repeat<3> (%1, %2 : !qec.detector_ref, !qec.detector_ref) -> !qec.detector_ref, !qec.detector_ref {
// CHECK-NEXT:      ^bb0(%5: !qec.detector_ref, %6: !qec.detector_ref):
// CHECK-NEXT:        %7, %8 = qstruct.repeat<2> (%5, %6 : !qec.detector_ref, !qec.detector_ref) -> !qec.detector_ref, !qec.detector_ref {
// CHECK-NEXT:        ^bb1(%9: !qec.detector_ref, %10: !qec.detector_ref):
// CHECK-NEXT:          %11 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:          %12 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:          qec.detector_round(%9, %11)
// CHECK-NEXT:          qstruct.yield %10, %12 : !qec.detector_ref, !qec.detector_ref
// CHECK-NEXT:        }
// CHECK-NEXT:        %13 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:        %14 = qec.detector<[0.0, 0.0]> ()
// CHECK-NEXT:        qec.detector_round(%7, %13)
// CHECK-NEXT:        qstruct.yield %8, %14 : !qec.detector_ref, !qec.detector_ref
// CHECK-NEXT:      }
// CHECK-NEXT:      qec.detector_round(%3)
// CHECK-NEXT:      qec.detector_round(%4)
// CHECK-NEXT:      qstruct.yield
// CHECK-NEXT:    }
// CHECK-NEXT:  }

// ----
// CHECK: ----

builtin.module {
  %q0 = qcore.alloc_qubit<> -> !qcore.qubit
  %q1 = qstruct.circuit(%q0: !qcore.qubit) -> !qcore.qubit {
  ^bb0(%q0_1: !qcore.qubit):

// CHECK:   builtin.module {
// CHECK:     %q0 = qcore.alloc_qubit -> !qcore.qubit
// CHECK:     %q1 = qstruct.circuit(%q0 : !qcore.qubit) -> !qcore.qubit {
// CHECK:     ^bb0(%q0_1: !qcore.qubit):

    stim.shift_coord <[0.0, 0.0, 1.0]>
    stim.detector <[0.0, 0.0, 5.0]> (:)
    stim.detector <[0.0, 0.0, 1.0]> (:)
    stim.detector <[0.0, 0.0, 1.0]> (:)
    stim.detector <[0.0, 0.0, 7.0]> (:)
    %1 = qref.measure<Z> (%q0_1) -> i1

// CHECK:       qec.detector_round()
// CHECK:       %0 = qec.detector<[0.0, 0.0]> ()
// CHECK:       %1 = qec.detector<[0.0, 0.0]> ()
// CHECK:       %2 = qec.detector<[0.0, 0.0]> ()
// CHECK:       %3 = qec.detector<[0.0, 0.0]> ()
// CHECK:       %4 = qref.measure<Z> (%q0_1) -> i1
// CHECK:       %5 = qec.detector()

    %0 = qstruct.repeat<3> (%1 : i1) -> i1 {
    ^bb0(%2: i1):
      stim.shift_coord <[0.0, 0.0, 2.0]>
      qstruct.yield %2 : i1
    }

// CHECK:       %6, %7, %8, %9, %10 = qstruct.repeat<3> (%2, %1, %5, %0, %4 : !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, i1) -> !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, i1 {
// CHECK:       ^bb1(%11: !qec.detector_ref, %12: !qec.detector_ref, %13: !qec.detector_ref, %14: !qec.detector_ref, %15: i1):
// CHECK:         qec.detector_round()
// CHECK:         qec.detector_round(%11, %12)
// CHECK:         %16 = qec.detector()
// CHECK:         %17 = qec.detector()
// CHECK:         qstruct.yield %16, %13, %14, %17, %15 : !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, !qec.detector_ref, i1
// CHECK:       }

    %2 = qstruct.repeat<3> (%0 : i1) -> i1 {
    ^bb2(%2: i1):
      qstruct.yield %2 : i1
    }

// CHECK:       %18 = qstruct.repeat<3> (%10 : i1) -> i1 {
// CHECK:       ^bb2(%19: i1):
// CHECK:         qstruct.yield %19 : i1
// CHECK:       }

    %arg1 = arith.constant 1 : i1
    %arg2 = arith.constant 0 : i1
    %arg3 = arith.constant 1 : i1

    %a, %b, %c = qstruct.repeat<2> (%arg1, %arg2, %arg3: i1, i1, i1) -> i1, i1, i1 {
    ^bb3(%block_arg0: i1, %block_arg1: i1, %block_arg2: i1):
      stim.shift_coord <[0.0, 0.0, 1.0]>
      qstruct.yield %block_arg1, %block_arg0, %block_arg2 : i1, i1, i1
    }

// CHECK:       %arg1 = arith.constant true
// CHECK:       %arg2 = arith.constant false
// CHECK:       %arg3 = arith.constant true
// CHECK:       %20 = qec.detector()
// CHECK:       %21, %22, %a, %b, %c = qstruct.repeat<2> (%20, %3, %arg1, %arg2, %arg3 : !qec.detector_ref, !qec.detector_ref, i1, i1, i1) -> !qec.detector_ref, !qec.detector_ref, i1, i1, i1 {
// CHECK:       ^bb3(%23: !qec.detector_ref, %24: !qec.detector_ref, %block_arg0: i1, %block_arg1: i1, %block_arg2: i1):
// CHECK:         qec.detector_round(%23)
// CHECK:         %25 = qec.detector()
// CHECK:         qstruct.yield %24, %25, %block_arg1, %block_arg0, %block_arg2 : !qec.detector_ref, !qec.detector_ref, i1, i1, i1
// CHECK:       }

    stim.detector <[0.0, 0.0, 1.0]> (:)
    qstruct.yield %q0_1 : !qcore.qubit
  }
}

// CHECK:       %26 = qec.detector<[0.0, 0.0]> ()
// CHECK:       qec.detector_round()
// CHECK:       qec.detector_round(%26)
// CHECK:       qstruct.yield %q0_1 : !qcore.qubit
// CHECK:     }
// CHECK:   }

// ----
// CHECK: ----

// Nested repeat observables

builtin.module {
  qstruct.circuit -> {

// CHECK-NEXT:    builtin.module {
// CHECK-NEXT:      %0, %1 = qstruct.circuit -> !qec.observable, !qec.observable {
// CHECK-NEXT:        %2 = qec.dec_observable {stim.obs_id = #builtin.int<2>} -> !qec.observable
// CHECK-NEXT:        %3 = qec.dec_observable {stim.obs_id = #builtin.int<5>} -> !qec.observable

    qstruct.repeat<3> () -> {
      stim.observable_include <5> (:)
      qstruct.repeat<2> () -> {
        stim.observable_include <2> (:)
        stim.observable_include <2> (:)
        qstruct.yield
      }
      qstruct.yield
    }

// CHECK-NEXT:        %4, %5 = qstruct.repeat<3> (%3, %2 : !qec.observable, !qec.observable) -> !qec.observable, !qec.observable {
// CHECK-NEXT:        ^bb0(%6: !qec.observable, %7: !qec.observable):
// CHECK-NEXT:          %8 = qec.observable_include(%6) using () -> !qec.observable
// CHECK-NEXT:          %9 = qstruct.repeat<2> (%7 : !qec.observable) -> !qec.observable {
// CHECK-NEXT:          ^bb1(%10: !qec.observable):
// CHECK-NEXT:            %11 = qec.observable_include(%10) using () -> !qec.observable
// CHECK-NEXT:            %12 = qec.observable_include(%11) using () -> !qec.observable
// CHECK-NEXT:            qstruct.yield %12 : !qec.observable
// CHECK-NEXT:          }
// CHECK-NEXT:          qstruct.yield %8, %9 : !qec.observable, !qec.observable
// CHECK-NEXT:        }
// CHECK-NEXT:        qstruct.yield %4, %5 : !qec.observable, !qec.observable
// CHECK-NEXT:      }

    qstruct.yield
  }
}

// CHECK-NEXT:      %2 = qec.get_corrected(%0 : !qec.observable) -> i1
// CHECK-NEXT:      %3 = qec.get_corrected(%1 : !qec.observable) -> i1
// CHECK-NEXT:      qstruct.output(%2, %3 : i1, i1)
// CHECK-NEXT:    }

// ----
// CHECK: ----

// Detectors referencing measurements - single round

builtin.module {
  %q0, %q1 = qcore.alloc_qubit<> -> !qcore.qubit, !qcore.qubit
  %r0, %r1 = qstruct.circuit(%q0, %q1: !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
  ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit):
    %sq0 = builtin.unrealized_conversion_cast %q0_1 : !qcore.qubit to !stim.qubit
    %sq1 = builtin.unrealized_conversion_cast %q1_1 : !qcore.qubit to !stim.qubit

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %r0, %r1 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:   ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit):
// CHECK-NEXT:     %sq0 = builtin.unrealized_conversion_cast %q0_1 : !qcore.qubit to !stim.qubit
// CHECK-NEXT:     %sq1 = builtin.unrealized_conversion_cast %q1_1 : !qcore.qubit to !stim.qubit

    %m0, %m1 = stim.measure Z (%sq0, %sq1) -> i1, i1
    %m2, %m3 = stim.measure Z (%sq0, %sq1) -> i1, i1
    stim.detector <[0.0, 0.0, 0.0]> (%m0 : i1)
    stim.detector <[0.0, 0.0, 0.0]> (%m1 : i1)
    stim.shift_coord <[0.0, 0.0, 1.0]>
    qstruct.yield %q0_1, %q1_1 : !qcore.qubit, !qcore.qubit
  }
}

// CHECK-NEXT:     %m0, %m1 = stim.measure Z (%sq0, %sq1) -> i1, i1
// CHECK-NEXT:     %m2, %m3 = stim.measure Z (%sq0, %sq1) -> i1, i1
// CHECK-NEXT:     qec.measurement_round(%m0, %m1, %m2, %m3 : i1, i1, i1, i1)
// CHECK-NEXT:     %0 = qec.detector<[0.0, 0.0]> (%m0)
// CHECK-NEXT:     %1 = qec.detector<[0.0, 0.0]> (%m1)
// CHECK-NEXT:     qec.detector_round(%0, %1)
// CHECK-NEXT:     qstruct.yield %q0_1, %q1_1 : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   }
// CHECK-NEXT: }

// ----
// CHECK: ----

// Detectors referencing measurements across two rounds

builtin.module {
  %q0, %q1 = qcore.alloc_qubit<> -> !qcore.qubit, !qcore.qubit
  %r0, %r1 = qstruct.circuit(%q0, %q1: !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
  ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit):
    %sq0 = builtin.unrealized_conversion_cast %q0_1 : !qcore.qubit to !stim.qubit
    %sq1 = builtin.unrealized_conversion_cast %q1_1 : !qcore.qubit to !stim.qubit

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %r0, %r1 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:   ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit):
// CHECK-NEXT:     %sq0 = builtin.unrealized_conversion_cast %q0_1 : !qcore.qubit to !stim.qubit
// CHECK-NEXT:     %sq1 = builtin.unrealized_conversion_cast %q1_1 : !qcore.qubit to !stim.qubit

    %m0, %m1 = stim.measure Z (%sq0, %sq1) -> i1, i1

// CHECK-NEXT:     %m0, %m1 = stim.measure Z (%sq0, %sq1) -> i1, i1
// CHECK-NEXT:     qec.measurement_round(%m0, %m1 : i1, i1)

    stim.detector <[0.0, 0.0, 0.0]> (%m0 : i1)
    stim.detector <[0.0, 0.0, 0.0]> (%m1 : i1)
    stim.shift_coord <[0.0, 0.0, 1.0]>

// CHECK-NEXT:     %0 = qec.detector<[0.0, 0.0]> (%m0)
// CHECK-NEXT:     %1 = qec.detector<[0.0, 0.0]> (%m1)
// CHECK-NEXT:     qec.detector_round(%0, %1)

    %m2, %m3 = stim.measure Z (%sq0, %sq1) -> i1, i1

// CHECK-NEXT:     %m2, %m3 = stim.measure Z (%sq0, %sq1) -> i1, i1
// CHECK-NEXT:     qec.measurement_round(%m2, %m3 : i1, i1)

    stim.detector <[0.0, 0.0, 0.0]> (%m0, %m2 : i1, i1)
    stim.detector <[0.0, 0.0, 0.0]> (%m1, %m3 : i1, i1)
    stim.shift_coord <[0.0, 0.0, 1.0]>
    qstruct.yield %q0_1, %q1_1 : !qcore.qubit, !qcore.qubit
  }
}

// CHECK-NEXT:     %2 = qec.detector<[0.0, 0.0]> (%m0, %m2)
// CHECK-NEXT:     %3 = qec.detector<[0.0, 0.0]> (%m1, %m3)
// CHECK-NEXT:     qec.detector_round(%2, %3)
// CHECK-NEXT:     qstruct.yield %q0_1, %q1_1 : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   }
// CHECK-NEXT: }

// ----
// CHECK: ----

// Detectors referencing measurements inside a repeat

builtin.module {
  %q0, %q1 = qcore.alloc_qubit<> -> !qcore.qubit, !qcore.qubit
  %r0, %r1 = qstruct.circuit(%q0, %q1: !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
  ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit):
    %sq0 = builtin.unrealized_conversion_cast %q0_1 : !qcore.qubit to !stim.qubit
    %sq1 = builtin.unrealized_conversion_cast %q1_1 : !qcore.qubit to !stim.qubit

// CHECK-NEXT: builtin.module {
// CHECK-NEXT:   %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   %r0, %r1 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit {
// CHECK-NEXT:   ^bb0(%q0_1: !qcore.qubit, %q1_1: !qcore.qubit):
// CHECK-NEXT:     %sq0 = builtin.unrealized_conversion_cast %q0_1 : !qcore.qubit to !stim.qubit
// CHECK-NEXT:     %sq1 = builtin.unrealized_conversion_cast %q1_1 : !qcore.qubit to !stim.qubit

    %m0, %m1 = stim.measure Z (%sq0, %sq1) -> i1, i1


// CHECK-NEXT:     %m0, %m1 = stim.measure Z (%sq0, %sq1) -> i1, i1
// CHECK-NEXT:     qec.measurement_round(%m0, %m1 : i1, i1)

    %out0, %out1 = qstruct.repeat<5> (%m0, %m1 : i1, i1) -> i1, i1 {
    ^bb0(%prev0: i1, %prev1: i1):

// CHECK-NEXT:     %out0, %out1 = qstruct.repeat<5> (%m0, %m1 : i1, i1) -> i1, i1 {
// CHECK-NEXT:     ^bb1(%prev0: i1, %prev1: i1):

      %m2, %m3 = stim.measure Z (%sq0, %sq1) -> i1, i1

// CHECK-NEXT:       %m2, %m3 = stim.measure Z (%sq0, %sq1) -> i1, i1
// CHECK-NEXT:       qec.measurement_round(%m2, %m3 : i1, i1)

      stim.detector <[0.0, 0.0, 0.0]> (%prev0, %m2 : i1, i1)
      stim.detector <[0.0, 0.0, 0.0]> (%prev1, %m3 : i1, i1)
      stim.shift_coord <[0.0, 0.0, 1.0]>
      qstruct.yield %m2, %m3 : i1, i1
    }
    qstruct.yield %q0_1, %q1_1 : !qcore.qubit, !qcore.qubit
  }
}

// CHECK-NEXT:       %0 = qec.detector<[0.0, 0.0]> (%prev0, %m2)
// CHECK-NEXT:       %1 = qec.detector<[0.0, 0.0]> (%prev1, %m3)
// CHECK-NEXT:       qec.detector_round(%0, %1)
// CHECK-NEXT:       qstruct.yield %m2, %m3 : i1, i1
// CHECK-NEXT:     }
// CHECK-NEXT:     qstruct.yield %q0_1, %q1_1 : !qcore.qubit, !qcore.qubit
// CHECK-NEXT:   }
// CHECK-NEXT: }
