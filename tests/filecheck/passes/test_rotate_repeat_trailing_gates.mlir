// RUN: deltakit_compile compile-passes %s -t -p rotate-repeat-trailing-gates -O %t && filecheck %s --input-file %t

builtin.module {
// CHECK:       builtin.module {
    %qa = qcore.alloc_qubit -> !qcore.qubit
// CHECK-NEXT:      %qa = qcore.alloc_qubit -> !qcore.qubit
// The circuit carries flow information cached in its attr-dict. The rotation
// changes the gates applied, so the pass must drop it: the CHECK for the circuit
// header below expects no `stab.flows`, which only holds if it was invalidated.
    %oa = qstruct.circuit(%qa : !qcore.qubit) {stab.flows = #stab.concrete_flow_array<[<+:>{I -> X0 : 1}]>} -> !qcore.qubit {
    ^bb0(%q : !qcore.qubit):
// CHECK-NEXT:      %oa = qstruct.circuit(%qa : !qcore.qubit) -> !qcore.qubit {
// CHECK-NEXT:      ^bb0(%q: !qcore.qubit):

// A syndrome extraction round: reset, measure, and the basis change the
// compiler leaves behind. The trailing H is dead inside the loop but the last
// iteration flows into what follows, so it cannot be dropped where it stands.
//
// After rotation the body opens with the H, directly before the reset, which is
// where a dead gate removal pass can drop it. One copy is left on each side of
// the loop. That removal is a separate pass and is not run here, so the H below
// is still in the body: this test covers the rotation only.
        qstruct.repeat<3> () -> {
            qref.reset<Z> (%q)
            %m = qref.measure<Z>(%q) -> i1
            qref.gate<#qcore.gate.h> (%q)
            qstruct.yield
        }
// CHECK-NEXT:          qref.gate<#qcore.gate.h> (%q)
// CHECK-NEXT:          qstruct.repeat<3> () -> {
// CHECK-NEXT:              qref.gate<#qcore.gate.h> (%q)
// CHECK-NEXT:              qref.reset<Z> (%q)
// CHECK-NEXT:              %m = qref.measure<Z> (%q) -> i1
// CHECK-NEXT:              qstruct.yield
// CHECK-NEXT:          }
// CHECK-NEXT:          qref.gate<#qcore.gate.h> (%q)

// Not rotated: S is not its own inverse, so replacing (B S)^N with
// S (S B)^N S would change the circuit. This case has no CHECK-NOT because the
// CHECK-NEXT sequence below already pins the loop as unchanged.
        qstruct.repeat<3> () -> {
            qref.reset<Z> (%q)
            qref.gate<#qcore.gate.s> (%q)
            qstruct.yield
        }
// CHECK-NEXT:          qstruct.repeat<3> () -> {
// CHECK-NEXT:              qref.reset<Z> (%q)
// CHECK-NEXT:              qref.gate<#qcore.gate.s> (%q)
// CHECK-NEXT:              qstruct.yield
// CHECK-NEXT:          }

// Not rotated: the H is self-inverse, but nothing resets the qubit at the start
// of the body, so the copy rotated there could not be removed and the loop would
// just gain two gates. Here the measurement is the first thing to touch it.
        qstruct.repeat<3> () -> {
            %m2 = qref.measure<Z>(%q) -> i1
            qref.reset<Z> (%q)
            qref.gate<#qcore.gate.h> (%q)
            qstruct.yield
        }
// CHECK-NEXT:          qstruct.repeat<3> () -> {
// CHECK-NEXT:              %m2 = qref.measure<Z> (%q) -> i1
// CHECK-NEXT:              qref.reset<Z> (%q)
// CHECK-NEXT:              qref.gate<#qcore.gate.h> (%q)
// CHECK-NEXT:              qstruct.yield
// CHECK-NEXT:          }

// Not rotated: no reset in the body at all.
        qstruct.repeat<3> () -> {
            %m3 = qref.measure<Z>(%q) -> i1
            qref.gate<#qcore.gate.h> (%q)
            qstruct.yield
        }
// CHECK-NEXT:          qstruct.repeat<3> () -> {
// CHECK-NEXT:              %m3 = qref.measure<Z> (%q) -> i1
// CHECK-NEXT:              qref.gate<#qcore.gate.h> (%q)
// CHECK-NEXT:              qstruct.yield
// CHECK-NEXT:          }

// Not rotated: a square root X is not its own inverse. It is the plain X with
// an option, and the comparison by equality must not mistake one for the other.
        qstruct.repeat<3> () -> {
            qref.reset<Z> (%q)
            qref.gate<#qcore.gate.x<sqrt>> (%q)
            qstruct.yield
        }
// CHECK-NEXT:          qstruct.repeat<3> () -> {
// CHECK-NEXT:              qref.reset<Z> (%q)
// CHECK-NEXT:              qref.gate<#qcore.gate.x<sqrt>> (%q)
// CHECK-NEXT:              qstruct.yield
// CHECK-NEXT:          }

// Rotated across the loop boundary: the gate acts on %qi, a block argument, so
// the copy before the loop uses the iter arg %q feeding it and the copy after
// uses the result %r leaving it. All three name the same threaded qubit.
        %r = qstruct.repeat<3> (%q : !qcore.qubit) -> !qcore.qubit {
        ^bb1(%qi : !qcore.qubit):
            qref.reset<Z> (%qi)
            qref.gate<#qcore.gate.h> (%qi)
            qstruct.yield %qi : !qcore.qubit
        }
// CHECK-NEXT:          qref.gate<#qcore.gate.h> (%q)
// CHECK-NEXT:          %r = qstruct.repeat<3> (%q : !qcore.qubit) -> !qcore.qubit {
// CHECK-NEXT:          ^bb1(%qi: !qcore.qubit):
// CHECK-NEXT:              qref.gate<#qcore.gate.h> (%qi)
// CHECK-NEXT:              qref.reset<Z> (%qi)
// CHECK-NEXT:              qstruct.yield %qi : !qcore.qubit
// CHECK-NEXT:          }
// CHECK-NEXT:          qref.gate<#qcore.gate.h> (%r)

// Not rotated: the X before the reset acts on %r, while the reset and the H act
// on %qj. Inside this loop the two name the same threaded qubit, so the X sits
// between the rotated H and the reset, and remove-dead-gates would stop there.
        %r2 = qstruct.repeat<3> (%r : !qcore.qubit) -> !qcore.qubit {
        ^bb2(%qj : !qcore.qubit):
            qref.gate<#qcore.gate.x> (%r)
            qref.reset<Z> (%qj)
            qref.gate<#qcore.gate.h> (%qj)
            qstruct.yield %qj : !qcore.qubit
        }
// CHECK-NEXT:          %r2 = qstruct.repeat<3> (%r : !qcore.qubit) -> !qcore.qubit {
// CHECK-NEXT:          ^bb2(%qj: !qcore.qubit):
// CHECK-NEXT:              qref.gate<#qcore.gate.x> (%r)
// CHECK-NEXT:              qref.reset<Z> (%qj)
// CHECK-NEXT:              qref.gate<#qcore.gate.h> (%qj)
// CHECK-NEXT:              qstruct.yield %qj : !qcore.qubit
// CHECK-NEXT:          }

        qstruct.yield %q : !qcore.qubit
    }
// CHECK-NEXT:          qstruct.yield %q : !qcore.qubit
// CHECK-NEXT:      }
    "test.op"(%oa) : (!qcore.qubit) -> ()
// CHECK-NEXT:      "test.op"(%oa) : (!qcore.qubit) -> ()
}
// CHECK-NEXT:  }
