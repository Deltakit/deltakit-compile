"""Tests for the CombineDetectorRoundsPass."""

import warnings

import pytest
from xdsl.builder import Builder, ImplicitBuilder
from xdsl.context import Context
from xdsl.dialects import test as t
from xdsl.dialects.builtin import ModuleOp, StringAttr, i1
from xdsl.ir import Block, Region
from xdsl.pattern_rewriter import (
    PatternRewriter,
)

from deltakit_compile.dialects import qcore, qec, qref, qstruct
from deltakit_compile.dialects.stim import TAG_ATTR
from deltakit_compile.exceptions import LostStimTagWarning
from deltakit_compile.passes.combine_detector_rounds import (
    CombineDetectorRounds,
    _DetectorRoundPrepass,
    _get_operation_before_region,
    _lowest_common_region_or_op_ancestor,
    _propagate_ssa_values_to_region,
)
from tests.unit.conftest import parse_ir


def build_repeat_circuit1() -> tuple[ModuleOp, list]:
    """
    builtin.module {
        %0, %1, %2 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit, !qcore.qubit
        %3, %4, %5 = qstruct.circuit(%0, %1, %2 : !qcore.qubit, !qcore.qubit, !qcore.qubit) ->
        !qcore.qubit, !qcore.qubit, !qcore.qubit {
        ^bb0(%6: !qcore.qubit, %7: !qcore.qubit, %8: !qcore.qubit):
            %9 = qref.measure<Z> (%6) -> i1
            %10 = qref.measure<Z> (%7) -> i1
            %11 = qec.detector(%9, %10)
            %12, %13, %14 = qstruct.repeat<5> (%9, %10, %11 : i1, i1, !qec.detector_ref) -> i1,
            i1, !qec.detector_ref {
            ^bb1(%15: i1, %16: i1, %17: !qec.detector_ref):
                %18 = qref.measure<Z> (%6) -> i1
                %19 = qref.measure<Z> (%7) -> i1
                %20 = qec.detector(%16, %18)
                %21 = qec.detector(%19, %15)
                qec.detector_round(%20, %17)
                qstruct.yield %18, %19, %21 : i1, i1, !qec.detector_ref
            }
            %22, %23 = qref.measure<Z> (%6, %7) -> i1, i1
            %24 = qec.detector(%12, %22)
            %25 = qec.detector(%13, %23)
            qec.detector_round(%24, %25, %14)
            qstruct.yield %6, %7, %8 : !qcore.qubit, !qcore.qubit, !qcore.qubit
        }
    }
    """
    measurements_ops = []

    @ModuleOp
    @Builder.implicit_region
    def module():
        q0, q1, q2 = qcore.AllocQubitOp([qcore.QubitType()] * 3).results
        circuit_body = Block(arg_types=[qcore.QubitType()] * 3)
        q0_1, q1_1, q2_1 = circuit_body.args

        with ImplicitBuilder(circuit_body):
            m0 = qref.MeasureOp(qcore.PauliAttr.Z(), [q0_1]).measurement
            m1 = qref.MeasureOp(qcore.PauliAttr.Z(), [q1_1]).measurement
            measurements_ops.extend([m0, m1])  # indices 0, 1
            d0 = qec.DetectorOp([m0, m1]).result

            repeat_body = Block(arg_types=[i1, i1, qec.DetectorRefType()])
            m0_arg, m1_arg, detector_arg = repeat_body.args

            with ImplicitBuilder(repeat_body):
                m2 = qref.MeasureOp(qcore.PauliAttr.Z(), [q0_1]).measurement
                m3 = qref.MeasureOp(qcore.PauliAttr.Z(), [q1_1]).measurement
                measurements_ops.extend([m2, m3])  # indices 2, 3

                d0_0 = qec.DetectorOp([m1_arg, m2]).result
                d1_0 = qec.DetectorOp([m3, m0_arg]).result
                qec.DetectorRoundOp([d0_0, detector_arg])
                qstruct.YieldOp(m2, m3, d1_0)

            repeat_op = qstruct.RepeatOp(
                repetitions=5,
                body=repeat_body,
                iter_args=[m0, m1, d0],
            )
            m2_1, m3_1, d1 = repeat_op.results

            m4, m5 = qref.MeasureOp(qcore.PauliAttr.Z(), [q0_1, q1_1]).measurements
            measurements_ops.extend([m4])  # index 4
            d2 = qec.DetectorOp([m2_1, m4]).result
            d3 = qec.DetectorOp([m3_1, m5]).result
            qec.DetectorRoundOp([d2, d3, d1])

            qstruct.YieldOp(q0_1, q1_1, q2_1)

        qstruct.CircuitOp(
            arguments=[q0, q1, q2],
            result_types=[qcore.QubitType()] * 3,
            body=[circuit_body],
        )

    return module, measurements_ops


def build_parallel_nested_detector_round_circuit() -> tuple[ModuleOp, list]:
    ans = []

    @ModuleOp
    @Builder.implicit_region
    def module():
        nonlocal ans
        q0, q1 = qcore.AllocQubitOp([qcore.QubitType()] * 2).results
        circuit_body = Block(arg_types=[qcore.QubitType()] * 2)
        q0_1, q1_1 = circuit_body.args

        with ImplicitBuilder(circuit_body):
            m0 = qref.MeasureOp(qcore.PauliAttr.Z(), [q0_1]).measurement
            m1 = qref.MeasureOp(qcore.PauliAttr.Z(), [q1_1]).measurement
            qec.DetectorOp([m0, m1])

            par_region1 = Region(Block())
            with ImplicitBuilder(par_region1.block):
                qstruct.YieldOp()

            par_region2 = Region(Block())

            with ImplicitBuilder(par_region2.block):
                test_block = Block()
                with ImplicitBuilder(test_block):
                    par_region_3 = Region(Block())
                    with ImplicitBuilder(par_region_3.block):
                        qstruct.YieldOp()
                    par_region_4 = Region(Block())
                    with ImplicitBuilder(par_region_4.block):
                        qstruct.YieldOp()
                    par_region_5 = Region(Block())
                    with ImplicitBuilder(par_region_5.block):
                        qstruct.YieldOp()
                    par_region_6 = Region(Block())
                    with ImplicitBuilder(par_region_6.block):
                        ans.append(qref.MeasureOp(qcore.PauliAttr.Z(), [q0_1]))
                        qstruct.YieldOp()

                    ans.append(
                        qstruct.ParallelOp(
                            result_types=[],
                            par_regions=[
                                par_region_3,
                                par_region_4,
                                par_region_5,
                                par_region_6,
                            ],
                            alignment="BOTTOM",
                        ),
                    )

                    qstruct.YieldOp()

                t.TestOp(regions=[Region(test_block)])
                qstruct.YieldOp()

            ans.append(
                qstruct.ParallelOp(
                    result_types=[],
                    par_regions=[par_region1, par_region2],
                    alignment="TOP",
                )
            )

        qstruct.CircuitOp(
            arguments=[q0, q1],
            result_types=[qcore.QubitType()] * 2,
            body=[circuit_body],
        )

    return module, ans


@pytest.mark.parametrize(
    ("_", "ans"),
    [
        build_parallel_nested_detector_round_circuit(),
    ],
)
def test_yield_parallel_and_regions_of_detector_round(
    _: ModuleOp, ans: list[tuple[qstruct.ParallelOp, Region]]
):
    """Test that the detector round pattern can correctly identify parallel ops and region
    associated with a detector round."""
    pattern = _DetectorRoundPrepass()
    assert isinstance(ans[0], qref.MeasureOp), (
        f"Expected the first op to be a measurement op, but found {type(ans[0])}."
    )
    parallel_ops_and_regions = list(pattern._extract_parallelisable_ancestors(ans[0]))
    assert parallel_ops_and_regions == ans, (
        f"Expected parallel ops and regions {ans} for detector round, but found "
        f"{parallel_ops_and_regions}"
    )


@pytest.mark.parametrize(
    ("module_op", "measurements_ops", "expected_indices"),
    [
        (
            *build_repeat_circuit1(),
            ([0, 1, 2, 3], [0, 2, 3, 4]),
        ),
    ],
)
def test_get_measurement_ops_of_detector_round(
    module_op: ModuleOp, measurements_ops: list, expected_indices: tuple[list[int], ...]
):
    """Test that the detector round pattern can traverse through IR structure to find measurement
    ops."""
    i = 0
    pattern = _DetectorRoundPrepass()
    # Collect actual measurement ops found, organised by detector round
    for op in module_op.walk():
        if isinstance(op, qec.DetectorRoundOp):
            detector_round_indices = set()
            measurement_ops = pattern._get_measurement_ops_of_detector_round(op)
            assert measurement_ops is not None
            for measurement_op in measurement_ops:
                detector_round_indices.update(
                    [j for j, m in enumerate(measurements_ops) if measurement_op == m.owner]
                )
            assert set(expected_indices[i]) == detector_round_indices, (
                f"Expected measurement indices {expected_indices[i]} for detector round {i}, but "
                f"found {tuple(detector_round_indices)}"
            )
            i += 1


def test_get_enclosing_region(xdsl_context: Context):
    """Test that the detector round pattern can find the correct enclosing region for a given op."""
    mlir = """
        %q1 = qcore.alloc_qubit -> !qcore.qubit
    """
    module = parse_ir(mlir, context=xdsl_context)
    pattern = _DetectorRoundPrepass()

    op = next(module.walk())

    assert pattern._get_enclosing_operation(op) is None, (
        f"Expected no enclosing operation for top-level op, but found "
        f"{pattern._get_enclosing_operation(op)}"
    )


def test_get_lowest_common_ancestor_fails_when_from_different_modules():
    """Test that the detector round pattern raises an error when trying to find a common ancestor
    for ops from different modules."""
    Region([Block([op1 := qcore.AllocQubitOp([qcore.QubitType()])])])
    Region([Block([op2 := qcore.AllocQubitOp([qcore.QubitType()])])])

    _DetectorRoundPrepass()

    with pytest.raises(
        ValueError,
        match=(
            r"Expected to find a common ancestor region or op between "
            r"the operations, but no common ancestor was found."
        ),
    ):
        _lowest_common_region_or_op_ancestor(op1, op2)


@pytest.mark.parametrize(
    ("_ir", "op"),
    [
        (Region([Block([op := qcore.AllocQubitOp([qcore.QubitType()]), qstruct.YieldOp()])]), op),
        (Block([op := qcore.AllocQubitOp([qcore.QubitType()]), qstruct.YieldOp()]), op),
    ],
)
def test_get_operation_before_region_returns_none(_ir: Region | Block, op: qcore.AllocQubitOp):
    """Test that the detector round pattern returns None when trying to find an operation before a
    region when there is no operation before the region."""

    assert _get_operation_before_region(op, Region()) is None, (
        "Expected to find no operation before the region, but found one."
    )


def test_lowest_common_region_or_op_ancestor_with_module():
    """Test that the detector round pattern returns the module when trying to find the lowest
    common ancestor for operations within the same module."""
    module = ModuleOp(
        Region(
            [
                Block(
                    [
                        op1 := qcore.AllocQubitOp([qcore.QubitType()]),
                        op2 := qstruct.YieldOp(),
                        op3 := qcore.AllocQubitOp([qcore.QubitType()]),
                    ]
                )
            ]
        )
    )

    assert _lowest_common_region_or_op_ancestor(op1, op2, op3, module) == module, (
        "Expected common ancestor to be the module, but found something else."
    )


def test_propagate_ssa_values_to_region_throws_if_not_ancestor():
    """Test that the detector round pattern raises an error when trying to propagate SSA values to a
    region that is not an ancestor of the defining operation."""
    region = Region([Block([op := qcore.AllocQubitOp([qcore.QubitType()]), qstruct.YieldOp()])])
    _ = Block(
        [
            qstruct.ParallelOp(
                result_types=[],
                par_regions=[region],
            )
        ]
    )

    _DetectorRoundPrepass()

    with pytest.raises(
        ValueError,
        match=(
            r"The end_region must be an ancestor of the start_region, but no ancestor relationship"
            r" was found"
        ),
    ):
        _propagate_ssa_values_to_region(op.result, region, Region([Block()]), PatternRewriter(op))


def test_detector_round_prepass(xdsl_context: Context):
    """Test that the prepass can be applied to a module without errors."""
    mlir = """
            %q, %q_1, %q_2, %q_3, %q_4, %q_5 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit,
            !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
            %0, %1, %2, %3, %4, %5 = qstruct.circuit(%q, %q_1, %q_2, %q_3, %q_4, %q_5 :
            !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit)
                -> !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit,
                !qcore.qubit {
            ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit, %qb2: !qcore.qubit, %qb3: !qcore.qubit,
            %qb4: !qcore.qubit, %qb5: !qcore.qubit):
                // parallel
                %m000, %m001, %m002, %m003, %m004, %m005 = qstruct.parallel<TOP> -> i1, i1, i1,
                i1, i1, i1 {
                    %m0 = qref.measure<Z> (%qb0) -> i1
                    qstruct.yield %m0 : i1
                } {
                    %m00, %m01, %m02, %m03, %m04 = qstruct.parallel<TOP> -> i1, i1, i1, i1, i1 {
                    %m0, %m1 = qref.measure<Z> (%qb4, %qb5) -> i1, i1
                    qstruct.yield %m0, %m1 : i1, i1
                } {
                    %m1, %m2 = qref.measure<Z> (%qb2, %qb3) -> i1, i1
                    qstruct.yield %m1, %m2 : i1, i1
                } {
                    %m05 = qstruct.parallel<TOP> -> i1 {
                    %m0 = qref.measure<Z> (%qb1) -> i1
                    qstruct.yield %m0 : i1
                }
                qstruct.yield %m05 : i1
                }
                qstruct.yield %m00, %m01, %m02, %m03, %m04 : i1, i1, i1, i1, i1
                }
                %d0 = qec.detector(%m000)
                qec.detector_round(%d0)
                %d1 = qec.detector(%m001)
                qec.detector_round(%d1)
                %d2 = qec.detector(%m002)
                qec.detector_round(%d2)
                %d3 = qec.detector(%m003)
                qec.detector_round(%d3)
                %d4 = qec.detector(%m004)
                qec.detector_round(%d4)
                %d5 = qec.detector(%m005)
                qec.detector_round(%d5)
                %m6 = qref.measure<Z> (%qb0) -> i1
                %d6 = qec.detector(%m6)
                qec.detector_round(%d6)
                qstruct.yield %qb0, %qb1, %qb2, %qb3, %qb4, %qb5 : !qcore.qubit, !qcore.qubit,
                !qcore.qubit, !qcore.qubit, !qcore.qubit, !qcore.qubit
            }

        """
    module = parse_ir(mlir, context=xdsl_context)
    rounds = _DetectorRoundPrepass().collect(module)
    assert len(rounds) == 2, (
        f"Expected to find 2 groups of detector rounds, but found {len(rounds)}"
    )
    assert len(rounds[0]) == 6, (
        f"Expected to find 6 detector rounds in first group, but found {len(rounds[0])}"
    )
    assert len(rounds[1]) == 1, (
        f"Expected to find 1 detector round in second group, but found {len(rounds[1])}"
    )


class TestStimTagPreservation:
    """Tests that stim tags are handled correctly when combining detector rounds."""

    # MLIR with two parallel detector rounds (measurements in different parallel regions)
    _PARALLEL_ROUNDS_MLIR = """
        %q0, %q1 = qcore.alloc_qubit -> !qcore.qubit, !qcore.qubit
        %r0, %r1 = qstruct.circuit(%q0, %q1 : !qcore.qubit, !qcore.qubit)
            -> !qcore.qubit, !qcore.qubit {
        ^bb0(%qb0: !qcore.qubit, %qb1: !qcore.qubit):
            %m0, %m1 = qstruct.parallel<TOP> -> i1, i1 {
                %m = qref.measure<Z> (%qb0) -> i1
                qstruct.yield %m : i1
            } {
                %m = qref.measure<Z> (%qb1) -> i1
                qstruct.yield %m : i1
            }
            %d0 = qec.detector(%m0)
            qec.detector_round(%d0)
            %d1 = qec.detector(%m1)
            qec.detector_round(%d1)
            qstruct.yield %qb0, %qb1 : !qcore.qubit, !qcore.qubit
        }
    """

    def test_single_tagged_round_tag_copied(self, xdsl_context: Context):
        """When one of the combined rounds has a tag, it is copied to the new combined round."""
        module = parse_ir(self._PARALLEL_ROUNDS_MLIR, xdsl_context)
        rounds = [op for op in module.walk() if isinstance(op, qec.DetectorRoundOp)]
        assert len(rounds) == 2
        rounds[0].attributes[TAG_ATTR] = StringAttr("my_tag")

        with warnings.catch_warnings():
            warnings.simplefilter("error", LostStimTagWarning)
            CombineDetectorRounds().apply(xdsl_context, module)

        new_rounds = [op for op in module.walk() if isinstance(op, qec.DetectorRoundOp)]
        assert len(new_rounds) == 1
        assert new_rounds[0].attributes.get(TAG_ATTR) == StringAttr("my_tag")

    def test_multiple_tagged_rounds_warns(self, xdsl_context: Context):
        """When multiple combined rounds have tags, the second tag triggers a warning."""
        module = parse_ir(self._PARALLEL_ROUNDS_MLIR, xdsl_context)
        for op in module.walk():
            if isinstance(op, qec.DetectorRoundOp):
                op.attributes[TAG_ATTR] = StringAttr("tag")

        with pytest.warns(LostStimTagWarning, match="multiple DetectorRoundOps"):
            CombineDetectorRounds().apply(xdsl_context, module)

    def test_no_tags_no_warn(self, xdsl_context: Context):
        """No warning is emitted when none of the combined rounds carry a stim tag."""
        module = parse_ir(self._PARALLEL_ROUNDS_MLIR, xdsl_context)

        with warnings.catch_warnings():
            warnings.simplefilter("error", LostStimTagWarning)
            CombineDetectorRounds().apply(xdsl_context, module)

        new_rounds = [op for op in module.walk() if isinstance(op, qec.DetectorRoundOp)]
        assert len(new_rounds) == 1
        assert TAG_ATTR not in new_rounds[0].attributes
