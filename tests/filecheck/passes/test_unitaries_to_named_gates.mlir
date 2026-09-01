// RUN: deltakit_compile compile-passes %s -p unitaries-to-named-gates -O %t && filecheck %s --input-file %t

builtin.module {
    %q0 = qcore.alloc_qubit -> !qcore.qubit
    %q1 = qcore.alloc_qubit -> !qcore.qubit
    %q2 = qcore.alloc_qubit -> !qcore.qubit
    %q3 = qcore.alloc_qubit -> !qcore.qubit

    %q0_out, %q1_out, %q2_out, %q3_out = qstruct.circuit(%q0, %q1, %q2, %q3 : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit) -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit {
    ^bb0(%q0_in: !qcore.qubit, %q1_in: !qcore.qubit, %q2_in: !qcore.qubit, %q3_in: !qcore.qubit):
        // CHECK: qref.gate<#qcore.gate.id> (%q0_in)
        qref.gate<#qcore.gate.unitary<[[(1.0, 0.0), (0.0, 0.0)], [(0.0, 0.0), (1.0, 0.0)]]>> (%q0_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.x> (%q0_in)
        qref.gate<#qcore.gate.unitary<[[(0.0, 0.0), (1.0, 0.0)], [(1.0, 0.0), (0.0, 0.0)]]>> (%q0_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.x<sqrt>> (%q0_in)
        qref.gate<#qcore.gate.unitary<[[(0.5, 0.5), (0.5, -0.5)], [(0.5, -0.5), (0.5, 0.5)]]>> (%q0_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.x<sqrt, dag>> (%q0_in)
        qref.gate<#qcore.gate.unitary<[[(0.5, -0.5), (0.5, 0.5)], [(0.5, 0.5), (0.5, -0.5)]]>> (%q0_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.y> (%q0_in)
        qref.gate<#qcore.gate.unitary<[[(0.0, 0.0), (0.0, -1.0)], [(0.0, 1.0), (0.0, 0.0)]]>> (%q0_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.y<sqrt>> (%q0_in)
        qref.gate<#qcore.gate.unitary<[[(0.5, 0.5), (-0.5, -0.5)], [(0.5, 0.5), (0.5, 0.5)]]>> (%q0_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.y<sqrt, dag>> (%q0_in)
        qref.gate<#qcore.gate.unitary<[[(0.5, -0.5), (0.5, -0.5)], [(-0.5, 0.5), (0.5, -0.5)]]>> (%q0_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.z> (%q0_in)
        qref.gate<#qcore.gate.unitary<[[(1.0, 0.0), (0.0, 0.0)], [(0.0, 0.0), (-1.0, 0.0)]]>> (%q0_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.h> (%q0_in)
        qref.gate<#qcore.gate.unitary<[[(0.7071067811865476, 0.0), (0.7071067811865476, 0.0)], [(0.7071067811865476, 0.0), (-0.7071067811865476, 0.0)]]>> (%q0_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.s> (%q0_in)
        qref.gate<#qcore.gate.unitary<[[(1.0, 0.0), (0.0, 0.0)], [(0.0, 0.0), (0.0, 1.0)]]>> (%q0_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.s<dag>> (%q0_in)
        qref.gate<#qcore.gate.unitary<[[(1.0, 0.0), (0.0, 0.0)], [(0.0, 0.0), (0.0, -1.0)]]>> (%q0_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.t> (%q0_in)
        qref.gate<#qcore.gate.unitary<[[(1.0, 0.0), (0.0, 0.0)], [(0.0, 0.0), (0.7071067811865476, 0.7071067811865476)]]>> (%q0_in)

        // Two-qubit gates
        // CHECK-NEXT: qref.gate<#qcore.gate.sqrt_xx> (%q0_in, %q1_in)
        qref.gate<#qcore.gate.unitary<[
            [(0.5, 0.5), (0.0, 0.0), (0.0, 0.0), (0.5, -0.5)],
            [(0.0, 0.0), (0.5, 0.5), (0.5, -0.5), (0.0, 0.0)],
            [(0.0, 0.0), (0.5, -0.5), (0.5, 0.5), (0.0, 0.0)],
            [(0.5, -0.5), (0.0, 0.0), (0.0, 0.0), (0.5, 0.5)]
        ]>> (%q0_in, %q1_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.sqrt_xx<dag>> (%q0_in, %q1_in)
        qref.gate<#qcore.gate.unitary<[
            [(0.5, -0.5), (0.0, 0.0), (0.0, 0.0), (0.5, 0.5)],
            [(0.0, 0.0), (0.5, -0.5), (0.5, 0.5), (0.0, 0.0)],
            [(0.0, 0.0), (0.5, 0.5), (0.5, -0.5), (0.0, 0.0)],
            [(0.5, 0.5), (0.0, 0.0), (0.0, 0.0), (0.5, -0.5)]
        ]>> (%q0_in, %q1_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.sqrt_yy> (%q0_in, %q1_in)
        qref.gate<#qcore.gate.unitary<[
            [(0.5, 0.5), (0.0, 0.0), (0.0, 0.0), (-0.5, 0.5)],
            [(0.0, 0.0), (0.5, 0.5), (0.5, -0.5), (0.0, 0.0)],
            [(0.0, 0.0), (0.5, -0.5), (0.5, 0.5), (0.0, 0.0)],
            [(-0.5, 0.5), (0.0, 0.0), (0.0, 0.0), (0.5, 0.5)]
        ]>> (%q0_in, %q1_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.sqrt_yy<dag>> (%q0_in, %q1_in)
        qref.gate<#qcore.gate.unitary<[
            [(0.5, -0.5), (0.0, 0.0), (0.0, 0.0), (-0.5, -0.5)],
            [(0.0, 0.0), (0.5, -0.5), (0.5, 0.5), (0.0, 0.0)],
            [(0.0, 0.0), (0.5, 0.5), (0.5, -0.5), (0.0, 0.0)],
            [(-0.5, -0.5), (0.0, 0.0), (0.0, 0.0), (0.5, -0.5)]
        ]>> (%q0_in, %q1_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.sqrt_zz> (%q0_in, %q1_in)
        qref.gate<#qcore.gate.unitary<[
            [(1.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
            [(0.0, 0.0), (0.0, 1.0), (0.0, 0.0), (0.0, 0.0)],
            [(0.0, 0.0), (0.0, 0.0), (0.0, 1.0), (0.0, 0.0)],
            [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (1.0, 0.0)]
        ]>> (%q0_in, %q1_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.sqrt_zz<dag>> (%q0_in, %q1_in)
        qref.gate<#qcore.gate.unitary<[
            [(1.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
            [(0.0, 0.0), (0.0, -1.0), (0.0, 0.0), (0.0, 0.0)],
            [(0.0, 0.0), (0.0, 0.0), (0.0, -1.0), (0.0, 0.0)],
            [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (1.0, 0.0)]
        ]>> (%q0_in, %q1_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.cx> (%q0_in, %q1_in)
        qref.gate<#qcore.gate.unitary<[
            [(1.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
            [(0.0, 0.0), (1.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
            [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (1.0, 0.0)],
            [(0.0, 0.0), (0.0, 0.0), (1.0, 0.0), (0.0, 0.0)]
        ]>> (%q0_in, %q1_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.cy> (%q0_in, %q1_in)
        qref.gate<#qcore.gate.unitary<[
            [(1.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
            [(0.0, 0.0), (1.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
            [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, -1.0)],
            [(0.0, 0.0), (0.0, 0.0), (0.0, 1.0), (0.0, 0.0)]
        ]>> (%q0_in, %q1_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.cz> (%q0_in, %q1_in)
        qref.gate<#qcore.gate.unitary<[
            [(1.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
            [(0.0, 0.0), (1.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
            [(0.0, 0.0), (0.0, 0.0), (1.0, 0.0), (0.0, 0.0)],
            [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (-1.0, 0.0)]
        ]>> (%q0_in, %q1_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.swap> (%q0_in, %q1_in)
        qref.gate<#qcore.gate.unitary<[
            [(1.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
            [(0.0, 0.0), (0.0, 0.0), (1.0, 0.0), (0.0, 0.0)],
            [(0.0, 0.0), (1.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
            [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (1.0, 0.0)]
        ]>> (%q0_in, %q1_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.iswap> (%q0_in, %q1_in)
        qref.gate<#qcore.gate.unitary<[
            [(1.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
            [(0.0, 0.0), (0.0, 0.0), (0.0, 1.0), (0.0, 0.0)],
            [(0.0, 0.0), (0.0, 1.0), (0.0, 0.0), (0.0, 0.0)],
            [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (1.0, 0.0)]
        ]>> (%q0_in, %q1_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.iswap<dag>> (%q0_in, %q1_in)
        qref.gate<#qcore.gate.unitary<[
            [(1.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
            [(0.0, 0.0), (0.0, 0.0), (0.0, -1.0), (0.0, 0.0)],
            [(0.0, 0.0), (0.0, -1.0), (0.0, 0.0), (0.0, 0.0)],
            [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (1.0, 0.0)]
        ]>> (%q0_in, %q1_in)

        // CHECK: qref.gate<#qcore.gate.h> (%q0_in, %q1_in, %q2_in, %q3_in)
        qref.gate<#qcore.gate.unitary<[[(0.7071067811865476, 0.0), (0.7071067811865476, 0.0)], [(0.7071067811865476, 0.0), (-0.7071067811865476, 0.0)]]>> (%q0_in, %q1_in, %q2_in, %q3_in)

        // CHECK-NEXT: qref.gate<#qcore.gate.iswap<dag>> (%q0_in, %q1_in, %q3_in, %q2_in)
        qref.gate<#qcore.gate.unitary<[
            [(1.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
            [(0.0, 0.0), (0.0, 0.0), (0.0, -1.0), (0.0, 0.0)],
            [(0.0, 0.0), (0.0, -1.0), (0.0, 0.0), (0.0, 0.0)],
            [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (1.0, 0.0)]
        ]>> (%q0_in, %q1_in, %q3_in, %q2_in)

        qstruct.yield %q0_in, %q1_in, %q2_in, %q3_in : !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
    }
}
