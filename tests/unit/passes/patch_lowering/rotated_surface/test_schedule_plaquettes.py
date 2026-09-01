import re

import pytest
from xdsl.context import Context
from xdsl.pattern_rewriter import PatternRewriteWalker

from deltakit_compile.exceptions import CompilerPassCheckError
from deltakit_compile.passes.patch_lowering.rotated_surface.schedule_plaquettes import (
    _SynchronisedSchedulePattern,
)
from tests.unit.conftest import parse_ir


def test_schedule_plaquette_raises_on_mixed_pauli_stabilisers(xdsl_context: Context) -> None:
    ir = """\
%0, %1, %2 = "test.op"() : () -> (!qcore.qubit, !qcore.qubit, !qcore.qubit)
%p0_6, %p0_7, %p0_8 = qstruct.repeat<2> (%0, %1, %2 : !qcore.qubit, !qcore.qubit, !qcore.qubit)
            -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
    ^bb0(%3: !qcore.qubit, %4: !qcore.qubit, %5: !qcore.qubit):
    %6, %7, %8, %9 = qstruct.circuit(%3, %4, %5 : !qcore.qubit, !qcore.qubit, !qcore.qubit)
                -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1 {
        ^bb1(%10: !qcore.qubit, %11: !qcore.qubit, %12: !qcore.qubit):
        %13 = plaquette.round(%10, %11, %12) {plaquette.z_observable_is_vertical = true} -> i1 {
            ^bb2(%14: !qcore.qubit, %15: !qcore.qubit, %16: !qcore.qubit):
            %17 = plaquette.plaquette<[Z0 X1 : 2]> on (%14, %15) using (%16)
                    {plaquette.shape_type = #plaquette.rotated_surface_plaquette_shape<TOP>} -> i1
            plaquette.yield %17 : i1
        }
        qstruct.yield %6, %7, %8, %9 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1
    }
    qstruct.yield %6, %7, %8 : !qcore.qubit, !qcore.qubit, !qcore.qubit
}
"""
    module = parse_ir(ir, xdsl_context)
    rewriter = PatternRewriteWalker(_SynchronisedSchedulePattern())
    msg = re.escape("Stabilisers with mixed Paulis are not yet implemented.")
    with pytest.raises(NotImplementedError, match=msg):
        rewriter.rewrite_module(module)


def test_schedule_plaquette_raises_on_invalid_partially_specified_schedule(
    xdsl_context: Context,
) -> None:
    ir = """\
%0, %1, %2 = "test.op"() : () -> (!qcore.qubit, !qcore.qubit, !qcore.qubit)
%p0_6, %p0_7, %p0_8 = qstruct.repeat<2> (%0, %1, %2 : !qcore.qubit, !qcore.qubit, !qcore.qubit)
            -> !qcore.qubit, !qcore.qubit, !qcore.qubit {
    ^bb0(%3: !qcore.qubit, %4: !qcore.qubit, %5: !qcore.qubit):
    %6, %7, %8, %9 = qstruct.circuit(%3, %4, %5 : !qcore.qubit, !qcore.qubit, !qcore.qubit)
                -> !qcore.qubit, !qcore.qubit, !qcore.qubit, i1 {
        ^bb1(%10: !qcore.qubit, %11: !qcore.qubit, %12: !qcore.qubit):
        %13 = plaquette.round(%10, %11, %12) {plaquette.z_observable_is_vertical = true} -> i1 {
            ^bb2(%14: !qcore.qubit, %15: !qcore.qubit, %16: !qcore.qubit):
            %17 = plaquette.plaquette<[Z0 Z1 : 2],
                    #plaquette.synchronised_schedule<[none, 2]>> on (%14, %15) using (%16)
                    {plaquette.shape_type = #plaquette.rotated_surface_plaquette_shape<TOP>} -> i1
            plaquette.yield %17 : i1
        }
        qstruct.yield %6, %7, %8, %9 : !qcore.qubit, !qcore.qubit, !qcore.qubit, i1
    }
    qstruct.yield %6, %7, %8 : !qcore.qubit, !qcore.qubit, !qcore.qubit
}
"""
    module = parse_ir(ir, xdsl_context)
    rewriter = PatternRewriteWalker(_SynchronisedSchedulePattern())
    msg = re.escape(
        "Trying to override an existing SynchronisedScheduleAttr with the one computed by "
        "the compiler but they disagree. Existing schedule was 2 at entry 1 but the compiler "
        "computed 3."
    )
    with pytest.raises(CompilerPassCheckError, match=msg):
        rewriter.rewrite_module(module)
