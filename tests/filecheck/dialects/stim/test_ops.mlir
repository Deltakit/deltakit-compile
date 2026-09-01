// RUN: ROUNDTRIP_MLIR

builtin.module {
  %0 = stim.qubit_alloc 0 -> !stim.qubit
  %1 = stim.qubit_alloc 1 -> !stim.qubit
  %2 = stim.qubit_alloc 2 -> !stim.qubit
  %3 = stim.qubit_alloc 3 -> !stim.qubit
  %4 = stim.measure Z (%0) -> i1
  %5 = stim.repeat 2 (%4 : i1) -> i1 {
  ^bb0(%6: i1):
    stim.detector <[0.0, 0.0]> (%6 : i1)
    stim.yield %6 : i1
  }
  %7, %8 = stim.measure Z (%0, %1) -> i1, i1
  %9 = stim.empty -> i1
  %10, %11, %12, %13, %14, %15 = stim.repeat 2 (%9, %9, %9, %5, %7, %8 : i1, i1, i1, i1, i1, i1) -> i1, i1, i1, i1, i1, i1 {
  ^bb1(%16: i1, %17: i1, %18: i1, %19: i1, %20: i1, %21: i1):
    stim.clifford CZ (%0, %1)
    %22, %23 = stim.measure Z (%0, %1) -> i1, i1
    stim.yield %18, %19, %20, %21, %22, %23 : i1, i1, i1, i1, i1, i1
  }
  stim.detector <[0.0, 0.0]> (%10 : i1)
  stim.reset Z (%0, %1, %2, %3)
  stim.clifford CZ (%0, %3, %1, %2)
  %24, %25 = stim.measure Z (%3, %2) -> i1, i1
  stim.detector <[0.0, 0.0]> (%24 : i1)
  %26, %27, %28, %29, %30 = stim.repeat 10 (%13, %14, %15, %24, %25 : i1, i1, i1, i1, i1) -> i1, i1, i1, i1, i1 {
  ^bb2(%31: i1, %32: i1, %33: i1, %34: i1, %35: i1):
    %36, %37, %38, %39, %40 = stim.repeat 5 (%31, %32, %33, %34, %35 : i1, i1, i1, i1, i1) -> i1, i1, i1, i1, i1 {
    ^bb3(%41: i1, %42: i1, %43: i1, %44: i1, %45: i1):
      stim.clifford CZ (%0, %3, %1, %2)
      %46, %47 = stim.measure Z (%3, %2) -> i1, i1
      stim.detector <[0.0, 0.0]> (%46, %44 : i1, i1)
      stim.shift_coord <[0.0, 1.0]>
      stim.yield %43, %44, %45, %46, %47 : i1, i1, i1, i1, i1
    }
    stim.yield %36, %37, %38, %39, %40 : i1, i1, i1, i1, i1
  }
  stim.detector <[0.0, 0.0]> (%26, %30 : i1, i1)
}

// CHECK:       builtin.module {
// CHECK-NEXT:    %0 = stim.qubit_alloc 0 -> !stim.qubit
// CHECK-NEXT:    %1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:    %2 = stim.qubit_alloc 2 -> !stim.qubit
// CHECK-NEXT:    %3 = stim.qubit_alloc 3 -> !stim.qubit
// CHECK-NEXT:    %4 = stim.measure Z (%0) -> i1
// CHECK-NEXT:    %5 = stim.repeat 2 (%4 : i1) -> i1 {
// CHECK-NEXT:    ^bb0(%6: i1):
// CHECK-NEXT:      stim.detector <[0.0, 0.0]> (%6 : i1)
// CHECK-NEXT:      stim.yield %6 : i1
// CHECK-NEXT:    }
// CHECK-NEXT:    %7, %8 = stim.measure Z (%0, %1) -> i1, i1
// CHECK-NEXT:    %9 = stim.empty -> i1
// CHECK-NEXT:    %10, %11, %12, %13, %14, %15 = stim.repeat 2 (%9, %9, %9, %5, %7, %8 : i1, i1, i1, i1, i1, i1) -> i1, i1, i1, i1, i1, i1 {
// CHECK-NEXT:    ^bb1(%16: i1, %17: i1, %18: i1, %19: i1, %20: i1, %21: i1):
// CHECK-NEXT:      stim.clifford CZ (%0, %1)
// CHECK-NEXT:      %22, %23 = stim.measure Z (%0, %1) -> i1, i1
// CHECK-NEXT:      stim.yield %18, %19, %20, %21, %22, %23 : i1, i1, i1, i1, i1, i1
// CHECK-NEXT:    }
// CHECK-NEXT:    stim.detector <[0.0, 0.0]> (%10 : i1)
// CHECK-NEXT:    stim.reset Z (%0, %1, %2, %3)
// CHECK-NEXT:    stim.clifford CZ (%0, %3, %1, %2)
// CHECK-NEXT:    %24, %25 = stim.measure Z (%3, %2) -> i1, i1
// CHECK-NEXT:    stim.detector <[0.0, 0.0]> (%24 : i1)
// CHECK-NEXT:    %26, %27, %28, %29, %30 = stim.repeat 10 (%13, %14, %15, %24, %25 : i1, i1, i1, i1, i1) -> i1, i1, i1, i1, i1 {
// CHECK-NEXT:    ^bb2(%31: i1, %32: i1, %33: i1, %34: i1, %35: i1):
// CHECK-NEXT:      %36, %37, %38, %39, %40 = stim.repeat 5 (%31, %32, %33, %34, %35 : i1, i1, i1, i1, i1) -> i1, i1, i1, i1, i1 {
// CHECK-NEXT:      ^bb3(%41: i1, %42: i1, %43: i1, %44: i1, %45: i1):
// CHECK-NEXT:        stim.clifford CZ (%0, %3, %1, %2)
// CHECK-NEXT:        %46, %47 = stim.measure Z (%3, %2) -> i1, i1
// CHECK-NEXT:        stim.detector <[0.0, 0.0]> (%46, %44 : i1, i1)
// CHECK-NEXT:        stim.shift_coord <[0.0, 1.0]>
// CHECK-NEXT:        stim.yield %43, %44, %45, %46, %47 : i1, i1, i1, i1, i1
// CHECK-NEXT:      }
// CHECK-NEXT:      stim.yield %36, %37, %38, %39, %40 : i1, i1, i1, i1, i1
// CHECK-NEXT:    }
// CHECK-NEXT:    stim.detector <[0.0, 0.0]> (%26, %30 : i1, i1)
// CHECK-NEXT:  }


// ----


builtin.module {
  %0 = stim.qubit_alloc 10 -> !stim.qubit
  %1 = stim.qubit_alloc 1 -> !stim.qubit
  stim.repeat 10 () {
    stim.repeat 5 () {
      %2 = stim.measure Z (%0) -> i1
      stim.yield
    }
    stim.yield
  }
  stim.repeat 2 () {
    %3 = stim.measure Z (%1) -> i1
    stim.repeat 1 () {
      stim.clifford X (%0)
      stim.yield
    }
    %4 = stim.measure Z (%1) -> i1
    stim.yield
  }
  stim.clifford X (%1)
  stim.repeat 1 () {
    stim.tick
    stim.yield
  }
  %5 = stim.measure Z (%1) -> i1
  stim.clifford X (%1)
  stim.repeat 1 () {
    stim.tick
    %6 = stim.measure Z (%1) -> i1
    stim.detector <[0.0, 1.0]> (%6 : i1)
    stim.yield
  }
  %7 = stim.measure Z (%1) -> i1
}

// CHECK:       builtin.module {
// CHECK-NEXT:    %0 = stim.qubit_alloc 10 -> !stim.qubit
// CHECK-NEXT:    %1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:    stim.repeat 10 () {
// CHECK-NEXT:      stim.repeat 5 () {
// CHECK-NEXT:        %2 = stim.measure Z (%0) -> i1
// CHECK-NEXT:        stim.yield
// CHECK-NEXT:      }
// CHECK-NEXT:      stim.yield
// CHECK-NEXT:    }
// CHECK-NEXT:    stim.repeat 2 () {
// CHECK-NEXT:      %3 = stim.measure Z (%1) -> i1
// CHECK-NEXT:      stim.repeat 1 () {
// CHECK-NEXT:        stim.clifford X (%0)
// CHECK-NEXT:        stim.yield
// CHECK-NEXT:      }
// CHECK-NEXT:      %4 = stim.measure Z (%1) -> i1
// CHECK-NEXT:      stim.yield
// CHECK-NEXT:    }
// CHECK-NEXT:    stim.clifford X (%1)
// CHECK-NEXT:    stim.repeat 1 () {
// CHECK-NEXT:      stim.tick
// CHECK-NEXT:      stim.yield
// CHECK-NEXT:    }
// CHECK-NEXT:    %5 = stim.measure Z (%1) -> i1
// CHECK-NEXT:    stim.clifford X (%1)
// CHECK-NEXT:    stim.repeat 1 () {
// CHECK-NEXT:      stim.tick
// CHECK-NEXT:      %6 = stim.measure Z (%1) -> i1
// CHECK-NEXT:      stim.detector <[0.0, 1.0]> (%6 : i1)
// CHECK-NEXT:      stim.yield
// CHECK-NEXT:    }
// CHECK-NEXT:    %7 = stim.measure Z (%1) -> i1
// CHECK-NEXT:  }




// ----


builtin.module {
  %0 = stim.qubit_alloc 10 -> !stim.qubit
  %1 = stim.qubit_alloc 1 -> !stim.qubit
  stim.correlated_error <0.01> [X, Y] (%0, %1)
  stim.else_correlated_error <0.06> [X, X] (%0, %1)
  stim.else_correlated_error <0.06> [Y, Y] (%1, %0)
  stim.correlated_error <0.5> [Z] (%1)
  stim.else_correlated_error <0.02> [Z] (%0)
}

// CHECK:       builtin.module {
// CHECK-NEXT:    %0 = stim.qubit_alloc 10 -> !stim.qubit
// CHECK-NEXT:    %1 = stim.qubit_alloc 1 -> !stim.qubit
// CHECK-NEXT:    stim.correlated_error <0.01> [X, Y] (%0, %1)
// CHECK-NEXT:    stim.else_correlated_error <0.06> [X, X] (%0, %1)
// CHECK-NEXT:    stim.else_correlated_error <0.06> [Y, Y] (%1, %0)
// CHECK-NEXT:    stim.correlated_error <0.5> [Z] (%1)
// CHECK-NEXT:    stim.else_correlated_error <0.02> [Z] (%0)

// CHECK-NEXT:  }
