# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Pass that inlines func.func and log_asm_api.circuit_dec definitions."""

import warnings
from collections.abc import Iterable
from dataclasses import dataclass

from typing_extensions import override
from xdsl.context import Context
from xdsl.dialects.builtin import ModuleOp
from xdsl.ir import Operation
from xdsl.pattern_rewriter import (
    GreedyRewritePatternApplier,
    PatternRewriter,
    PatternRewriteWalker,
    RewritePattern,
    op_type_rewrite_pattern,
)
from xdsl.rewriter import InsertPoint, Rewriter
from xdsl.traits import SymbolTable
from xdsl.utils.hints import isa

from deltakit_compile.dialects import func, qstruct
from deltakit_compile.dialects import log_asm_api as api
from deltakit_compile.dialects import stabiliser as stab
from deltakit_compile.dialects.qcore import HasCircuitAncestor
from deltakit_compile.exceptions import CompilerPassCheckError, DeltakitCompilerWarning
from deltakit_compile.passes.common.pipeline import (
    ConfigurablePass,
    Configuration,
    configurable_pass,
)


@dataclass(frozen=True)
class _FuncCallRewriter(RewritePattern):
    """Pattern to directly inline non-recursive func.func ops at their call sites."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: func.CallOp, rewriter: PatternRewriter) -> None:
        func_dec_op = SymbolTable.lookup_symbol(op, op.callee)
        assert isa(func_dec_op, func.FuncOp)
        if any(isinstance(child_op, api.CallOp | func.CallOp) for child_op in func_dec_op.walk()):
            # Never inline functions that call other functions to avoid infinite recursion
            return
        body_copy = func_dec_op.body.clone()
        return_op = body_copy.block.last_op
        assert isa(return_op, func.ReturnOp)
        rewriter.inline_block(body_copy.block, InsertPoint.before(op), op.arguments)
        rewriter.replace_op(op, [], return_op.arguments)
        rewriter.erase_op(return_op)
        body_copy.drop_all_references()


@dataclass(frozen=True)
class _CircuitCallRewriter(RewritePattern):
    """Pattern to inline within qstruct circuits non-recursive log_asm_api.circuit_dec ops at their
    call sites."""

    warn_loss_of_flows: bool

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: api.CallOp, rewriter: PatternRewriter) -> None:
        func_dec_op = SymbolTable.lookup_symbol(op, op.callee)
        assert isa(func_dec_op, api.CircuitDeclarationOp)
        if any(isinstance(child_op, api.CallOp | func.CallOp) for child_op in func_dec_op.walk()):
            # Never inline functions that call other functions to avoid infinite recursion
            return
        body_copy = func_dec_op.body.clone()
        return_op = body_copy.block.last_op
        assert isa(return_op, api.ReturnOp)

        if circuit := HasCircuitAncestor.get_circuit_ancestor(op):
            if self.warn_loss_of_flows and stab.ConcreteFlowArrayAttr.get(func_dec_op):
                msg = (
                    f"Stabiliser flows for circuit declaration {func_dec_op.sym_name} were "
                    "dropped during circuit inlining"
                )
                if isa(circuit, api.CircuitDeclarationOp):
                    msg += f" into {circuit.sym_name}"
                warnings.warn(DeltakitCompilerWarning(msg), stacklevel=2)
            # Inline circuit directly, so we do not create a circuit inside a circuit.
            rewriter.inline_block(body_copy.block, InsertPoint.before(op), op.arguments)
            rewriter.replace_op(op, [], return_op.arguments)
            rewriter.erase_op(return_op)
            body_copy.drop_all_references()
        else:
            rewriter.replace_op(return_op, qstruct.YieldOp(*return_op.arguments))
            circuit = qstruct.CircuitOp(op.arguments, op.ret.types, body_copy)
            # Explicitly copy concrete flows from circuit def to new circuit.
            if flows := stab.ConcreteFlowArrayAttr.get(func_dec_op):
                circuit.attributes[stab.ConcreteFlowArrayAttr.KEY] = flows
            rewriter.replace_op(op, circuit, circuit.res)


class InlineCircuitsAndSubroutinesConfig(Configuration, frozen=True):
    """Configuration for the InlineCircuitsAndSubroutines pass."""

    warn_on_loss_of_flows: bool = False
    """If set, a warning is raised each time a log_asm_api.circuit_dec with annotated flows is
    inlined such that its flows cannot be persisted."""
    warn_on_circuits_not_inlined: bool = False
    """If set, a warning is raised for each log_asm_api.circuit_dec that could not be inlined."""
    error_on_circuits_not_inlined: bool = False
    """If set, a ``CompilerPassCheckError`` is raised for each log_asm_api.circuit_dec that could
    not be inlined."""
    warn_on_functions_not_inlined: bool = False
    """If set, a warning is raised for each func.func that could not be inlined."""
    error_on_functions_not_inlined: bool = False
    """If set, a ``CompilerPassCheckError`` is raised for each func.func that could
    not be inlined."""


@configurable_pass
class InlineCircuitsAndSubroutines(ConfigurablePass[InlineCircuitsAndSubroutinesConfig]):
    """A pass that inlines all func.func subroutines and log_asm_api.circuit_dec ops to their
    call sites, so long as they do not recurse. This pass will remove all unused func.func ops and
    log_asm_api.circuit_dec ops, used recursive functions are retained and not inlined.

    Concrete flow attributes on log_asm_api.circuit_dec ops are transferred to the resulting inlined
    qstruct.circuit ops, when the circuit is called from outside another circuit context."""

    name = "inline-circuits-and-subroutines"

    warn_on_loss_of_flows: bool = False
    warn_on_circuits_not_inlined: bool = False
    error_on_circuits_not_inlined: bool = False
    warn_on_functions_not_inlined: bool = False
    error_on_functions_not_inlined: bool = False

    def _remove_unused_functions(
        self, op: ModuleOp
    ) -> Iterable[func.FuncOp | api.CircuitDeclarationOp]:
        """Erases unused function ops by constructing and searching the graph of calling ops and
        function ops. Returns every func.FuncOp and api.CircuitDeclarationOp that could not be
        erased."""
        all_calls_to_funcs: dict[
            func.CallOp | api.CallOp, func.FuncOp | api.CircuitDeclarationOp
        ] = {}
        all_funcs_to_inner_calls: dict[
            func.FuncOp | api.CircuitDeclarationOp, list[func.CallOp | api.CallOp]
        ] = {}
        top_level_calls: set[func.CallOp | api.CallOp] = set()

        # The DFS walk of the IR extracts a map from all calls to the function called, and from all
        # functions (or top level) to the calls contained within.
        parent_stack: list[func.FuncOp | api.CircuitDeclarationOp] = []
        for child_op in op.walk():
            if isinstance(child_op, func.CallOp | api.CallOp):
                func_op = SymbolTable.lookup_symbol(child_op, child_op.callee)
                assert isinstance(func_op, func.FuncOp | api.CircuitDeclarationOp)
                all_calls_to_funcs[child_op] = func_op
                if parent_stack:
                    all_funcs_to_inner_calls[parent_stack[-1]].append(child_op)
                else:
                    top_level_calls.add(child_op)
            elif isinstance(child_op, func.FuncOp | api.CircuitDeclarationOp):
                parent_stack.append(child_op)
                all_funcs_to_inner_calls[child_op] = []
            elif parent_stack and child_op == parent_stack[-1].body.block.last_op:
                parent_stack.pop()

        # BFS from the top level calls to collect all connected function ops
        reached_calls: set[func.CallOp | api.CallOp] = set()
        next_calls = set(top_level_calls)
        reachable_funcs: set[func.FuncOp | api.CircuitDeclarationOp] = set()
        while next_calls:
            new_funcs = {all_calls_to_funcs[call] for call in next_calls}
            reached_calls.update(next_calls)
            next_calls = {
                call
                for new_func in (new_funcs - reachable_funcs)
                for call in all_funcs_to_inner_calls[new_func]
            } - reached_calls
            reachable_funcs.update(new_funcs)

        # Remove unused function ops
        for unreached_func in set(all_funcs_to_inner_calls) - reachable_funcs:
            Rewriter.erase_op(unreached_func)

        return reachable_funcs

    def check_funcs_are_inlined(self, ops: Iterable[Operation]) -> None:
        for func_op in ops:
            if isa(func_op, api.CircuitDeclarationOp):
                msg = (
                    f"{func_op.name} {func_op.sym_name} could not be inlined: "
                    "it is called recursively"
                )
                if self.warn_on_circuits_not_inlined:
                    warnings.warn(
                        DeltakitCompilerWarning(msg),
                        stacklevel=3,
                    )
                if self.error_on_circuits_not_inlined:
                    func_op.emit_error(msg, CompilerPassCheckError(msg))
            elif isa(func_op, func.FuncOp):
                msg = (
                    f"{func_op.name} {func_op.sym_name} could not be inlined: "
                    "it is called recursively"
                )
                if self.warn_on_functions_not_inlined:
                    warnings.warn(
                        DeltakitCompilerWarning(msg),
                        stacklevel=3,
                    )
                if self.error_on_functions_not_inlined:
                    func_op.emit_error(msg, CompilerPassCheckError(msg))

    @override
    def apply(self, ctx: Context, op: ModuleOp) -> None:
        # Replace calls with inlined function bodies
        PatternRewriteWalker(
            GreedyRewritePatternApplier(
                [
                    _FuncCallRewriter(),
                    _CircuitCallRewriter(self.warn_on_loss_of_flows),
                ]
            ),
            apply_recursively=True,
        ).rewrite_module(op)

        left_over_funcs = self._remove_unused_functions(op)
        self.check_funcs_are_inlined(left_over_funcs)
