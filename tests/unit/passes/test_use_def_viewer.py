"""Tests for the use-def viewer utility."""

import pytest
from xdsl.context import Context

from deltakit_compile.passes._use_def_viewer import UseDefViewer
from tests.unit.conftest import parse_ir


@pytest.mark.parametrize(
    ("ir", "expected"),
    [
        (
            """
            %a = "test.op"() : () -> (!test.type<"T">)
            """,
            [("a", {"a"})],
        ),
        (
            """
            %a = "test.op"() : () -> (!test.type<"T">)
            %b = "test.op"(%a) : (!test.type<"T">) -> (!test.type<"T">)
            """,
            [("a", {"a", "b"}), ("b", {"b"})],
        ),
        (
            # querying in reverse order also works
            """
            %a = "test.op"() : () -> (!test.type<"T">)
            %b = "test.op"(%a) : (!test.type<"T">) -> (!test.type<"T">)
            """,
            [("b", {"b"}), ("a", {"a", "b"})],
        ),
        (
            """
            %a, %b = "test.op"() : () -> (!test.type<"T">, !test.type<"T">)
            %c = "test.op"(%a) : (!test.type<"T">) -> (!test.type<"T">)
            %d = "test.op"(%b, %c) : (!test.type<"T">, !test.type<"T">) -> (!test.type<"T">)
            %e = "test.op"(%d) : (!test.type<"T">) -> (!test.type<"T">)
            """,
            [
                ("e", {"e"}),
                ("c", {"c", "d", "e"}),
                ("a", {"a", "c", "d", "e"}),
                ("d", {"d", "e"}),
                ("b", {"b", "d", "e"}),
            ],
        ),
    ],
)
def test_use_def_viewer(ir: str, expected: list[tuple[str, set[str]]], xdsl_context: Context):
    """Test that the UseDefViewer correctly identifies dominated SSA values."""
    viewer = UseDefViewer()

    module_op = parse_ir(ir, xdsl_context)
    name_to_ssa = {result.name_hint: result for op in module_op.ops for result in op.results}

    for name, expected_dominated_names in expected:
        assert name in name_to_ssa
        assert all(name in name_to_ssa for name in expected_dominated_names)

        ssa = name_to_ssa[name]
        expected_dominated = {name_to_ssa[dom_name] for dom_name in expected_dominated_names}

        assert viewer.get_dominated_ssas(ssa) == expected_dominated
