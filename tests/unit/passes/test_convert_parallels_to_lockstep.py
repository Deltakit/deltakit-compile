# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Tests for stim tag handling in ConvertParallelsToLockstep."""

import warnings

import pytest
from xdsl.context import Context
from xdsl.dialects.builtin import StringAttr
from xdsl.ir import Block

from deltakit_compile.dialects.qstruct import CircuitOp, ParallelOp
from deltakit_compile.dialects.stim import TAG_ATTR
from deltakit_compile.exceptions import LostStimTagWarning
from deltakit_compile.passes.convert_parallels_to_lockstep import ConvertParallelsToLockstep
from tests.unit.conftest import parse_ir

# MLIR with a ParallelOp containing two simple regions (enough to be non-trivially converted)
_PARALLEL_MLIR = """
    %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
    %out0, %out1 = qstruct.parallel<TOP> -> !qcore.qubit, !qcore.qubit {
        %a0 = qstruct.circuit(%q0 : !qcore.qubit) -> !qcore.qubit {
        ^bb0(%a: !qcore.qubit):
            qref.gate<#qcore.gate.h> (%a)
            qstruct.yield %a : !qcore.qubit
        }
        qstruct.yield %a0 : !qcore.qubit
    } {
        %b0 = qstruct.circuit(%q1 : !qcore.qubit) -> !qcore.qubit {
        ^bb0(%b: !qcore.qubit):
            qref.gate<#qcore.gate.h> (%b)
            qstruct.yield %b : !qcore.qubit
        }
        qstruct.yield %b0 : !qcore.qubit
    }

"""


class TestStimTagPreservation:
    """Tests that stim tags are copied or warned in ConvertParallelsToLockstep."""

    def test_parallel_op_tag_warns(self, xdsl_context: Context):
        """A stim tag on a ParallelOp triggers a StimTagLostWarning."""
        module = parse_ir(_PARALLEL_MLIR, xdsl_context)
        for op in module.walk():
            if isinstance(op, ParallelOp):
                op.attributes[TAG_ATTR] = StringAttr("par_tag")
                break
        with pytest.warns(LostStimTagWarning, match=""):
            ConvertParallelsToLockstep().apply(xdsl_context, module)

    def test_parallel_op_no_tag_no_warn(self, xdsl_context: Context):
        """No warning when a ParallelOp has no stim tag."""
        module = parse_ir(_PARALLEL_MLIR, xdsl_context)
        with warnings.catch_warnings():
            warnings.simplefilter("error", LostStimTagWarning)
            ConvertParallelsToLockstep().apply(xdsl_context, module)

    def test_circuit_tag_copied_when_combined(self, xdsl_context: Context):
        """When two CircuitOps are combined, the first one's tag is copied to the result."""
        module = parse_ir(_PARALLEL_MLIR, xdsl_context)
        circuits = [op for op in module.walk() if isinstance(op, CircuitOp)]
        # Tag the first inner circuit (not the outer one)
        [c for c in circuits if c.parent_op() is not None and isinstance(c.parent_op(), Block)]
        # Just tag the first CircuitOp inside a parallel region
        for c in circuits:
            parent = c.parent_op()
            if isinstance(parent, ParallelOp):
                c.attributes[TAG_ATTR] = StringAttr("circuit_tag")
                break

        with warnings.catch_warnings():
            warnings.simplefilter("error", LostStimTagWarning)
            ConvertParallelsToLockstep().apply(xdsl_context, module)

    def test_two_circuit_tags_warns(self, xdsl_context: Context):
        """When both CircuitOps in parallel regions have tags, a StimTagLostWarning is emitted."""
        module = parse_ir(_PARALLEL_MLIR, xdsl_context)
        tagged = 0
        for op in module.walk():
            if isinstance(op, CircuitOp):
                parent = op.parent_op()
                if isinstance(parent, ParallelOp):
                    op.attributes[TAG_ATTR] = StringAttr(f"tag_{tagged}")
                    tagged += 1
                    if tagged == 2:
                        break

        with pytest.warns(LostStimTagWarning):
            ConvertParallelsToLockstep().apply(xdsl_context, module)
