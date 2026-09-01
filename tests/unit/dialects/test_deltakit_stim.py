"""Tests for the Deltakit-Stim extension dialect for Stim."""

from importlib.metadata import version
from typing import Final

import pytest
from packaging.version import Version
from xdsl.context import Context
from xdsl.utils.exceptions import VerifyException

from deltakit_compile.dialects.deltakit_stim import HeraldLeakageEventOp
from deltakit_compile.dialects.stim import QubitAllocOp
from tests.unit.dialects.conftest import check_asm_roundtrip, check_stim_roundtrip

DELTAKIT_STIM_SUPPORTS_TAGS: Final[bool] = Version(version("deltakit_stim")) >= Version("1.16.0")
DELTAKIT_STIM_TAGS_MARK = (
    ()
    if DELTAKIT_STIM_SUPPORTS_TAGS
    else pytest.mark.xfail(reason="deltakit_stim version does not support tags")
)


qubit = QubitAllocOp(0).results[0]


@pytest.mark.parametrize(
    "program",
    [
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n "
        "%1 = deltakit_stim.herald_leakage_event (%0) -> i1",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n "
        "%1 = stim.qubit_alloc 1 -> !stim.qubit\n "
        "%2, %3 = deltakit_stim.herald_leakage_event <0.02> (%0, %1) -> i1, i1",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n "
        "%1 = stim.qubit_alloc 1 -> !stim.qubit\n deltakit_stim.leakage <0.0001> (%0, %1)",
        "%0 = stim.qubit_alloc 0 -> !stim.qubit\n "
        "%1 = stim.qubit_alloc 1 -> !stim.qubit\n deltakit_stim.relax <0.02> (%0, %1)",
    ],
)
def test_asm_leakage_roundtrip(program: str, xdsl_context: Context):
    """Test that leakage operations can be parsed and printed to/from MLIR assembly."""
    check_asm_roundtrip(program, xdsl_context)


@pytest.mark.parametrize(
    ("stim_str", "exp_stim_str"),
    [
        ("HERALD_LEAKAGE_EVENT 0 2", None),
        ("HERALD_LEAKAGE_EVENT(0.001) 4", None),
        ("LEAKAGE(0.01) 2 4", None),
        ("RELAX(0.1) 2 4 3 5", None),
    ],
)
def test_stim_leakage_roundtrip(stim_str: str, exp_stim_str: str | None):
    """Test that leakage operations can be parsed and printed to/from Stim."""
    check_stim_roundtrip(stim_str, exp_stim_str)


def _tag_tests(
    tests: list[tuple[str, str | None]] | list[tuple[str, None]], tag: str | None
) -> list[tuple[str, str | None]]:
    if tag:
        tag = "[" + tag + "]"
    return [
        (
            in_str.format(tag=tag or ""),
            out_str.format(tag=tag or "") if out_str is not None else None,
        )
        for in_str, out_str in tests
    ]


stim_leakage_roundtrip_tests = [
    ("HERALD_LEAKAGE_EVENT[my_tag] 0 2", None),
    ("HERALD_LEAKAGE_EVENT[my_tag](0.001) 4", None),
    ("LEAKAGE[my_tag](0.01) 2 4", None),
    ("RELAX[my_tag](0.1) 2 4 3 5", None),
]


@pytest.mark.parametrize(
    ("stim_str", "exp_stim_str"),
    _tag_tests(stim_leakage_roundtrip_tests, tag=None),
)
def test_stim_leakage_tag_roundtrip(stim_str: str, exp_stim_str: str | None):
    """Test that leakage operations with tags can be parsed and printed to/from Stim."""
    check_stim_roundtrip(stim_str, exp_stim_str)


def test_herald_leakage_event_verification():
    """Test the verification for herald leakage event ops."""
    with pytest.raises(VerifyException, match="expected integer >= 1, got 0"):
        HeraldLeakageEventOp([], 0.1).verify()

    with pytest.raises(
        VerifyException,
        match="A herald leakage event must return the same number of heralds as "
        "qubits it operates on",
    ):
        HeraldLeakageEventOp.create(operands=[qubit]).verify()
