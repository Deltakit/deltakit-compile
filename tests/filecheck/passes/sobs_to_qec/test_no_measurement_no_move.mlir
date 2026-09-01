// RUN: deltakit_compile compile-passes %s -p sobs-observable-to-qec -O %t && filecheck %s --input-file %t

// Simplest possible program, no measurement, no move, nothing to thread through structural operations.
builtin.module {
// CHECK-NEXT:    builtin.module {

	%q = qcore.alloc_qubit -> !qcore.qubit
	%source = sobs.dec_observable(%q) -> !sobs.observable
	%correction = qec.get_correction(%source : !sobs.observable) -> i1
	qstruct.output(%correction : i1)

// CHECK-NEXT:    %source = qec.dec_observable -> !qec.observable
// CHECK-NEXT:    %correction = qec.get_correction(%source : !qec.observable) -> i1
// CHECK-NEXT:    qstruct.output(%correction : i1)

}
// CHECK-NEXT:    }

// ----
// CHECK-NEXT: ----

// Simplest possible program, no measurement, no move, nothing to thread through structural operations.
builtin.module {
// CHECK-NEXT:    builtin.module {

	%q = qcore.alloc_qubit -> !qcore.qubit
	%source = sobs.dec_observable(%q) -> !sobs.observable
	%ready = qec.is_correction_ready(%source : !sobs.observable) -> i1
	qstruct.output(%ready : i1)

// CHECK-NEXT:    %source = qec.dec_observable -> !qec.observable
// CHECK-NEXT:    %ready = qec.is_correction_ready(%source : !qec.observable) -> i1
// CHECK-NEXT:    qstruct.output(%ready : i1)

}
// CHECK-NEXT:    }
