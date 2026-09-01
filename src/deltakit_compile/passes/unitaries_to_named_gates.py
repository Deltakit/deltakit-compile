# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Utilities for mapping between unitary matrices and named gate attributes."""

from dataclasses import dataclass

import numpy as np
from typing_extensions import override
from xdsl.dialects.builtin import ModuleOp
from xdsl.passes import ModulePass
from xdsl.pattern_rewriter import (
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)

from deltakit_compile.dialects.qcore import (
    CXGateAttr,
    CYGateAttr,
    CZGateAttr,
    GateAttribute,
    HGateAttr,
    IdentityGateAttr,
    ISWAPGateAttr,
    SGateAttr,
    SqrtXXGateAttr,
    SqrtYYGateAttr,
    SqrtZZGateAttr,
    StandardGateAttribute,
    SWAPGateAttr,
    TGateAttr,
    XGateAttr,
    YGateAttr,
    ZGateAttr,
)
from deltakit_compile.dialects.qref import GateOp
from deltakit_compile.exceptions import NonStandardUnitaryGateError

# Tuple of all standard gate attributes
# Use gate.get_unitary_matrix() to get the matrix representation
STANDARD_GATES: tuple[GateAttribute, ...] = (
    # Single-qubit Pauli gates
    IdentityGateAttr(),
    XGateAttr(),
    XGateAttr.sqrt(),
    XGateAttr.sqrt_dag(),
    YGateAttr(),
    YGateAttr.sqrt(),
    YGateAttr.sqrt_dag(),
    ZGateAttr(),
    # Hadamard gate
    HGateAttr(),
    # Phase gates
    SGateAttr(),
    SGateAttr.dag(),
    TGateAttr(),
    # Two-qubit entangling gates - sqrt of Pauli tensor products
    SqrtXXGateAttr(),
    SqrtXXGateAttr.dag(),
    SqrtYYGateAttr(),
    SqrtYYGateAttr.dag(),
    SqrtZZGateAttr(),
    SqrtZZGateAttr.dag(),
    # Controlled gates
    CXGateAttr(),
    CYGateAttr(),
    CZGateAttr(),
    # SWAP gates
    SWAPGateAttr(),
    ISWAPGateAttr(),
    ISWAPGateAttr.dag(),
)


class _ConvertUnitariesToNamedGates(RewritePattern):
    """Pattern rewriter that converts unitary matrices to named gate attributes."""

    def __init__(self, precision: float, unknown_unitary_error: bool):
        super().__init__()
        self.precision = precision
        self.unknown_unitary_error = unknown_unitary_error

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: GateOp, rewriter: PatternRewriter) -> None:
        if isinstance(op.gate, StandardGateAttribute):
            return

        for gate_attr in STANDARD_GATES:
            if op.gate.get_qubit_count() == gate_attr.get_qubit_count() and np.allclose(
                op.gate.get_unitary_matrix(),
                gate_attr.get_unitary_matrix(),
                atol=self.precision,
                rtol=0,
            ):
                op.gate = gate_attr
                rewriter.notify_op_modified(op)
                return

        if self.unknown_unitary_error:
            msg = (
                f"Encountered unknown unitary matrix in {op}, which does not match any"
                f" known gate within precision {self.precision}."
            )
            raise NonStandardUnitaryGateError(msg)


@dataclass(frozen=True)
class UnitariesToNamedGates(ModulePass):
    """Pass that converts unitary matrices to named gate attributes."""

    name = "unitaries-to-named-gates"

    precision: float = 1e-6
    unknown_unitary_error: bool = True

    @override
    def apply(self, ctx, op: ModuleOp) -> None:
        PatternRewriteWalker(
            _ConvertUnitariesToNamedGates(self.precision, self.unknown_unitary_error),
            apply_recursively=False,
        ).rewrite_module(op)
