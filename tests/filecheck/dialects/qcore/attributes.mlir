// RUN: ROUNDTRIP_MLIR

builtin.module {
// CHECK:       builtin.module {


    "test.op"() {pauli = #qcore.pauli<X>} : () -> ()
    "test.op"() {pauli = #qcore.pauli<Y>} : () -> ()
    "test.op"() {pauli = #qcore.pauli<Z>} : () -> ()
    "test.op"() {qubit_state = #qcore.pauli_state<X0>} : () -> ()
    "test.op"() {qubit_state = #qcore.pauli_state<Y1>} : () -> ()
    "test.op"() {qubit_state = #qcore.pauli_state<Z2>} : () -> ()
    "test.op"() {qubit_state = #qcore.pauli_string<I : 2>} : () -> ()
    "test.op"() {qubit_state = #qcore.pauli_string<X10 : 20>} : () -> ()
    "test.op"() {qubit_state = #qcore.pauli_string<X0 Y1 Z2 : 3>} : () -> ()
    %0 = "test.op"() : () -> !qcore.qubit
    %1 = "test.op"() : () -> !qcore.qubit_reg<1>
    %2 = "test.op"() : () -> !qcore.qubit_reg<2>
    %3 = "test.op"() : () -> !qcore.qubit_reg<32>
    %4 = "test.op"() : () -> !qcore.qubit_reg<1000000000>
    "test.op"() {coord = #qcore.qubit_coordinate(1, 2, 0.00000000000001)} : () -> ()
    "test.op"() {coord = #qcore.qubit_coordinate(-1000)} : () -> ()
    "test.op"() {coord = #qcore.qubit_coordinate(-10, 2.234, 3.000003)} : () -> ()
// CHECK-NEXT:      "test.op"() {pauli = #qcore.pauli<X>} : () -> ()
// CHECK-NEXT:      "test.op"() {pauli = #qcore.pauli<Y>} : () -> ()
// CHECK-NEXT:      "test.op"() {pauli = #qcore.pauli<Z>} : () -> ()
// CHECK-NEXT:      "test.op"() {qubit_state = #qcore.pauli_state<X0>} : () -> ()
// CHECK-NEXT:      "test.op"() {qubit_state = #qcore.pauli_state<Y1>} : () -> ()
// CHECK-NEXT:      "test.op"() {qubit_state = #qcore.pauli_state<Z2>} : () -> ()
// CHECK-NEXT:      "test.op"() {qubit_state = #qcore.pauli_string<I : 2>} : () -> ()
// CHECK-NEXT:      "test.op"() {qubit_state = #qcore.pauli_string<X10 : 20>} : () -> ()
// CHECK-NEXT:      "test.op"() {qubit_state = #qcore.pauli_string<X0 Y1 Z2 : 3>} : () -> ()
// CHECK-NEXT:      %0 = "test.op"() : () -> !qcore.qubit
// CHECK-NEXT:      %1 = "test.op"() : () -> !qcore.qubit_reg<1>
// CHECK-NEXT:      %2 = "test.op"() : () -> !qcore.qubit_reg<2>
// CHECK-NEXT:      %3 = "test.op"() : () -> !qcore.qubit_reg<32>
// CHECK-NEXT:      %4 = "test.op"() : () -> !qcore.qubit_reg<1000000000>
// CHECK-NEXT:      "test.op"() {coord = #qcore.qubit_coordinate(1.0, 2.0, 1.0e-14)} : () -> ()
// CHECK-NEXT:      "test.op"() {coord = #qcore.qubit_coordinate(-1000.0)} : () -> ()
// CHECK-NEXT:      "test.op"() {coord = #qcore.qubit_coordinate(-10.0, 2.234, 3.000003)} : () -> ()

    "test.op"() {pauli = #qcore.pauli_noise_parameters<X=0.1>} : () -> ()
    "test.op"() {pauli = #qcore.pauli_noise_parameters<X=1.0>} : () -> ()
    "test.op"() {pauli = #qcore.pauli_noise_parameters<I=1.0>} : () -> ()
    "test.op"() {pauli = #qcore.pauli_noise_parameters<IIIII=1.0>} : () -> ()
    "test.op"() {pauli = #qcore.pauli_noise_parameters<X=0.1, Y=0.1>} : () -> ()
    "test.op"() {pauli = #qcore.pauli_noise_parameters<XXIXIXXII=0.1, XYZZIXYZZ=0.6, XXIXIXXIZ=0.00000001>} : () -> ()
// CHECK-NEXT:      "test.op"() {pauli = #qcore.pauli_noise_parameters<X = 0.1>} : () -> ()
// CHECK-NEXT:      "test.op"() {pauli = #qcore.pauli_noise_parameters<X = 1.0>} : () -> ()
// CHECK-NEXT:      "test.op"() {pauli = #qcore.pauli_noise_parameters<I = 1.0>} : () -> ()
// CHECK-NEXT:      "test.op"() {pauli = #qcore.pauli_noise_parameters<IIIII = 1.0>} : () -> ()
// CHECK-NEXT:      "test.op"() {pauli = #qcore.pauli_noise_parameters<X = 0.1, Y = 0.1>} : () -> ()
// CHECK-NEXT:      "test.op"() {pauli = #qcore.pauli_noise_parameters<XXIXIXXII = 0.1, XXIXIXXIZ = 1.0e-08, XYZZIXYZZ = 0.6>} : () -> ()

    "test.op"() {gate = #qcore.gate.unitary<[[(0.0, 0.0), (1.0, 0.0)],
                                             [(1.0, 0.0), (0.0, 0.0)]]>} : () -> ()
    "test.op"() {gate = #qcore.gate.unitary<[[(0.5, 0.5), (0.5, -0.5)],
                                             [(0.5, -0.5), (0.5, 0.5)]]>} : () -> ()
    "test.op"() {gate = #qcore.gate.unitary<[[(0.70710678118, 0.0), (0.70710678118, 0.0)],
                                             [(0.70710678118, 0.0), (-0.70710678118, 0.0)]]>} : () -> ()
    "test.op"() {gate = #qcore.gate.unitary<[[(1.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
                                             [(0.0, 0.0), (1.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
                                             [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (1.0, 0.0)],
                                             [(0.0, 0.0), (0.0, 0.0), (1.0, 0.0), (0.0, 0.0)]]>} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.unitary<[[(0.0, 0.0), (1.0, 0.0)],
//CHECK-SAME:                                             [(1.0, 0.0), (0.0, 0.0)]]>} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.unitary<[[(0.5, 0.5), (0.5, -0.5)],
//CHECK-SAME:                                             [(0.5, -0.5), (0.5, 0.5)]]>} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.unitary<[[(0.70710678118, 0.0), (0.70710678118, 0.0)],
//CHECK-SAME:                                             [(0.70710678118, 0.0), (-0.70710678118, 0.0)]]>} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.unitary<[[(1.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
//CHECK-SAME:                                             [(0.0, 0.0), (1.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
//CHECK-SAME:                                             [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (1.0, 0.0)],
//CHECK-SAME:                                             [(0.0, 0.0), (0.0, 0.0), (1.0, 0.0), (0.0, 0.0)]]>} : () -> ()

    "test.op"() {gate = #qcore.gate.id} : () -> ()
    "test.op"() {gate = #qcore.gate.id<>} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.id} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.id} : () -> ()

    "test.op"() {gate = #qcore.gate.x} : () -> ()
    "test.op"() {gate = #qcore.gate.x<>} : () -> ()
    "test.op"() {gate = #qcore.gate.x<sqrt>} : () -> ()
    "test.op"() {gate = #qcore.gate.x<sqrt, dag>} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.x} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.x} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.x<sqrt>} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.x<sqrt, dag>} : () -> ()

    "test.op"() {gate = #qcore.gate.y} : () -> ()
    "test.op"() {gate = #qcore.gate.y<>} : () -> ()
    "test.op"() {gate = #qcore.gate.y<sqrt>} : () -> ()
    "test.op"() {gate = #qcore.gate.y<sqrt, dag>} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.y} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.y} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.y<sqrt>} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.y<sqrt, dag>} : () -> ()

    "test.op"() {gate = #qcore.gate.z} : () -> ()
    "test.op"() {gate = #qcore.gate.z<>} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.z} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.z} : () -> ()

    "test.op"() {gate = #qcore.gate.h} : () -> ()
    "test.op"() {gate = #qcore.gate.h<>} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.h} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.h} : () -> ()

    "test.op"() {gate = #qcore.gate.s} : () -> ()
    "test.op"() {gate = #qcore.gate.s<>} : () -> ()
    "test.op"() {gate = #qcore.gate.s<dag>} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.s} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.s} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.s<dag>} : () -> ()

    "test.op"() {gate = #qcore.gate.t} : () -> ()
    "test.op"() {gate = #qcore.gate.t<>} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.t} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.t} : () -> ()

    "test.op"() {gate = #qcore.gate.sqrt_xx} : () -> ()
    "test.op"() {gate = #qcore.gate.sqrt_xx<>} : () -> ()
    "test.op"() {gate = #qcore.gate.sqrt_xx<dag>} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.sqrt_xx} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.sqrt_xx} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.sqrt_xx<dag>} : () -> ()

    "test.op"() {gate = #qcore.gate.sqrt_yy} : () -> ()
    "test.op"() {gate = #qcore.gate.sqrt_yy<>} : () -> ()
    "test.op"() {gate = #qcore.gate.sqrt_yy<dag>} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.sqrt_yy} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.sqrt_yy} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.sqrt_yy<dag>} : () -> ()

    "test.op"() {gate = #qcore.gate.sqrt_zz} : () -> ()
    "test.op"() {gate = #qcore.gate.sqrt_zz<>} : () -> ()
    "test.op"() {gate = #qcore.gate.sqrt_zz<dag>} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.sqrt_zz} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.sqrt_zz} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.sqrt_zz<dag>} : () -> ()

    "test.op"() {gate = #qcore.gate.cx} : () -> ()
    "test.op"() {gate = #qcore.gate.cx<>} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.cx} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.cx} : () -> ()

    "test.op"() {gate = #qcore.gate.cy} : () -> ()
    "test.op"() {gate = #qcore.gate.cy<>} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.cy} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.cy} : () -> ()

    "test.op"() {gate = #qcore.gate.cz} : () -> ()
    "test.op"() {gate = #qcore.gate.cz<>} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.cz} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.cz} : () -> ()

    "test.op"() {gate = #qcore.gate.swap} : () -> ()
    "test.op"() {gate = #qcore.gate.swap<>} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.swap} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.swap} : () -> ()

    "test.op"() {gate = #qcore.gate.iswap} : () -> ()
    "test.op"() {gate = #qcore.gate.iswap<>} : () -> ()
    "test.op"() {gate = #qcore.gate.iswap<dag>} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.iswap} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.iswap} : () -> ()
//CHECK-NEXT:    "test.op"() {gate = #qcore.gate.iswap<dag>} : () -> ()

}
// CHECK-NEXT:  }
