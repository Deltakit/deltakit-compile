# (c) Copyright Riverlane 2025-2026. All rights reserved.
"""Module for the Rewrite patterns that canonicalise parts of the stabiliser dialect."""

from collections.abc import Iterable, Sequence
from typing import cast

from typing_extensions import override
from xdsl.ir import SSAValue
from xdsl.pattern_rewriter import PatternRewriter, RewritePattern, op_type_rewrite_pattern
from xdsl.rewriter import InsertPoint

from deltakit_compile.dialects import stabiliser as stab


class RemoveRedundantPermute(RewritePattern):
    """Remove StatePermuteOps that apply the identity permutation."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stab.StatePermuteOp, rewriter: PatternRewriter) -> None:
        if op.is_identity:
            rewriter.replace_op(op, [], [op.input])


class RemoveRedundantConcatenate(RewritePattern):
    """Remove StateConcatenateOps that don't actually concatenate anything."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stab.StateConcatenateOp, rewriter: PatternRewriter) -> None:
        if len(op.inputs) == 1:
            rewriter.replace_op(op, [], op.inputs)


class RemoveRedundantSplit(RewritePattern):
    """Remove StateSplitOps that don't actually split anything."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stab.StateSplitOp, rewriter: PatternRewriter) -> None:
        if len(op.outputs) == 1:
            rewriter.replace_op(op, [], [op.input])


class RemoveRedundantSplitAfterConcatenate(RewritePattern):
    """Remove StateSplitOps that return registers that were just concatenated."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stab.StateSplitOp, rewriter: PatternRewriter) -> None:
        if (
            isinstance(op.input.owner, stab.StateConcatenateOp)
            and op.input.owner.inputs.types == op.outputs.types
        ):
            rewriter.replace_op(op, [], op.input.owner.inputs)


class ReplaceConcatenateAfterSplitWithPermute(RewritePattern):
    """Replace a StateSplitOp followed by a concatenate of all its outputs with a StatePermuteOp.

    The split op is not erased in case its outputs are used in other control flow branches. It will
    be removed by DCE if its results are now unused.
    """

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stab.StateConcatenateOp, rewriter: PatternRewriter) -> None:
        if (
            len(owners := {inp.owner for inp in op.inputs}) == 1  # all inputs are from the same op
            and isinstance(split := owners.pop(), stab.StateSplitOp)  # and that op is a stab.split
            and len(op.inputs) == len(split.outputs)  # there's a result for each input in any order
            and set(op.inputs) == set(split.outputs)  # and the results/arguments match in any order
        ):
            concat_inputs = cast(Sequence[SSAValue[stab.StateType]], op.inputs)
            perm = stab.StatePermuteOp.calculate_permutation_from_states(
                split.outputs, concat_inputs
            )
            new_permute = stab.StatePermuteOp(cast(SSAValue[stab.StateType], split.input), perm)
            rewriter.replace_op(op, new_permute, [new_permute.output])


class CombineChainedPermutes(RewritePattern):
    """Combine consecutive StatePermuteOps into a single one.

    The first permute is not erased in case its output is used in other control flow branches. It
    will be removed by DCE if its results are now unused.
    """

    @staticmethod
    def _compose_permutations(perm1: list[int], perm2: list[int]) -> list[int]:
        """Compose two permutations together and return the result.

        Args:
            perm1: The first permutation to apply.
            perm2: The second permutation to apply.

        Returns:
            A permutation which is equivalent to applying perm1 and then perm2 (ie., perm2 * perm1).
            That is, output_perm[idx] = perm2[perm1[idx]].
        """
        assert len(perm1) == len(perm2)
        return [perm2[i] for i in perm1]

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stab.StatePermuteOp, rewriter: PatternRewriter) -> None:
        # If this permute's input is the output of another permute, we can combine them
        if isinstance(owner := op.input.owner, stab.StatePermuteOp):
            new_perm = self._compose_permutations(owner.permutation_list, op.permutation_list)
            new_permute_op = stab.StatePermuteOp(
                cast(SSAValue[stab.StateType], owner.input), new_perm
            )
            rewriter.replace_op(op, new_permute_op, [new_permute_op.output])


class CombineChainedConcatenates(RewritePattern):
    """Combine consecutive StateConcatenateOps into a single one.

    The earlier concatenates are not removed in case their output is used in other control flow
    branches. They will be removed by DCE if their results are now unused.
    """

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stab.StateConcatenateOp, rewriter: PatternRewriter) -> None:
        # Flatten any inputs to this concatenate that are themselves concatenate outputs
        new_inputs: list[SSAValue[stab.StateType]] = []
        for input_ in op.inputs:
            if isinstance(input_.owner, stab.StateConcatenateOp):
                new_inputs.extend(cast(Iterable[SSAValue[stab.StateType]], input_.owner.inputs))
            else:
                new_inputs.append(cast(SSAValue[stab.StateType], input_))

        if new_inputs != list(op.inputs):
            new_concatenate = stab.StateConcatenateOp(new_inputs)
            rewriter.replace_op(op, new_concatenate, [new_concatenate.output])


class CombineChainedSplits(RewritePattern):
    """Combine consecutive StateSplitOps into a single one.

    Splits will only be combined if an output of the first split is only used as an input to the
    second split and not used anywhere else.
    """

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stab.StateSplitOp, rewriter: PatternRewriter) -> None:
        # Flatten any outputs of this split that are themselves inputs to another split
        flattened_splits: list[stab.StateSplitOp] = []
        flattened_outputs: list[SSAValue[stab.StateType]] = []
        for output in op.outputs:
            if isinstance(user := output.get_user_of_unique_use(), stab.StateSplitOp):
                flattened_outputs.extend(cast(Iterable[SSAValue[stab.StateType]], user.outputs))
                flattened_splits.append(user)
            else:
                flattened_outputs.append(cast(SSAValue[stab.StateType], output))

        if flattened_splits:
            new_split = stab.StateSplitOp(
                cast(SSAValue[stab.StateType], op.input),
                [output.type.total_qubits for output in flattened_outputs],
            )
            rewriter.insert_op(new_split, InsertPoint.before(op))
            for old_output, new_output in zip(flattened_outputs, new_split.outputs, strict=True):
                rewriter.replace_all_uses_with(old_output, new_output)

            # OK to remove flattened_splits because we know they don't have any other users
            for split in flattened_splits:
                rewriter.erase_op(split)
            rewriter.erase_op(op)


class CombineConcatenatedStateMake(RewritePattern):
    """Combine sequences of StateMakeOps which are used consecutively in a concatenate (and not used
    anywhere else) into a single larger StateMakeOp."""

    @override
    @op_type_rewrite_pattern
    def match_and_rewrite(self, op: stab.StateConcatenateOp, rewriter: PatternRewriter) -> None:
        new_inputs: list[SSAValue[stab.StateType]] = []
        collapsible_makes: list[stab.StateMakeOp] = []

        def end_collapsible_sequence() -> None:
            nonlocal collapsible_makes
            if len(collapsible_makes) > 1:
                all_qubits = [qubit for make in collapsible_makes for qubit in make.input_qubits]
                new_make_type = stab.StateType(len(all_qubits), op.output.type.qubit_type, [])
                new_make = stab.StateMakeOp(all_qubits, new_make_type)
                rewriter.insert_op(new_make, InsertPoint.before(op))
                # DCE will erase the old collapsed make ops - don't need to erase here
                new_inputs.append(new_make.output)
            elif len(collapsible_makes) == 1:
                # Only one make op to collapse, preserve it
                new_inputs.append(collapsible_makes[0].output)
            collapsible_makes = []

        for input_ in op.inputs:
            if (
                isinstance(owner := input_.owner, stab.StateMakeOp)
                and owner.output.get_user_of_unique_use() == op
            ):
                collapsible_makes.append(owner)
            else:
                end_collapsible_sequence()
                new_inputs.append(cast(SSAValue[stab.StateType], input_))

        end_collapsible_sequence()

        if new_inputs != list(op.inputs):
            new_concat = stab.StateConcatenateOp(new_inputs)
            rewriter.replace_op(op, new_concat)
