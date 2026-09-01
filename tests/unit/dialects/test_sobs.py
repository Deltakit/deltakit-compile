import re
from collections.abc import Sequence
from typing import Literal

import pytest
from xdsl.dialects import test as t
from xdsl.dialects.builtin import NoneAttr, i1
from xdsl.ir import VerifyException

from deltakit_compile.dialects.logical_assembly import (
    RotatedPlanarPatchType,
    SurfaceCodeBasePatch,
    UnrotatedPlanarPatchType,
)
from deltakit_compile.dialects.qcore import PauliAttr, QubitRegType, QubitType
from deltakit_compile.dialects.sobs import (
    DecObservableOp,
    DecUnplacedObservableOp,
    LocateObservableOp,
    LocateUnplacedObservableOp,
    MoveObservableOp,
    ObservableType,
    UnplacedObservableType,
)

# region Unplaced operation definitions


def test_unplaced_observable_declaration_op() -> None:
    obs = DecUnplacedObservableOp()
    assert len(obs.results) == 1
    assert isinstance(obs.result_types[0], UnplacedObservableType)


@pytest.mark.parametrize(
    ("bases", "patch_types", "expected_error"),
    [
        ("X", [RotatedPlanarPatchType((3, 3), NoneAttr())], None),
        (
            [PauliAttr.X(), PauliAttr.Z(), PauliAttr.X()],
            [RotatedPlanarPatchType((3, 3), NoneAttr()) for _ in range(3)],
            None,
        ),
        (
            "XX",
            [
                RotatedPlanarPatchType((3, 3), NoneAttr()),
                UnrotatedPlanarPatchType((3, 3), NoneAttr()),
            ],
            None,
        ),
        (
            "XZX",
            [RotatedPlanarPatchType((3, 3), NoneAttr())],
            "incorrect length for range variable",
        ),
    ],
)
def test_locate_unplaced_observable(
    bases: str | Sequence[PauliAttr],
    patch_types: Sequence[SurfaceCodeBasePatch],
    expected_error: str | None,
) -> None:
    test_op = t.TestOp(result_types=[UnplacedObservableType(), *patch_types])
    obs, *patches = test_op.results
    op = LocateUnplacedObservableOp(bases, obs, patches)
    if expected_error is None:
        op.verify()
    else:
        with pytest.raises(VerifyException, match=expected_error):
            op.verify()


# Note: the last parameterisation is an upper-case chi.
@pytest.mark.parametrize("bases", ["x", "W", "'", "Γ", "XXZZχ", "Χ"])  # noqa: RUF001
def test_locate_unplaced_observable_raises_on_invalid_bases(bases: str) -> None:
    test_op = t.TestOp(
        result_types=[
            UnplacedObservableType(),
            *(RotatedPlanarPatchType((3, 3), NoneAttr()) for _ in range(len(bases))),
        ]
    )
    obs, *patches = test_op.results
    msg = re.escape(
        f"Expected a PauliString (that only contains X, Y, or Z, characters) but got '{bases}'."
    )
    with pytest.raises(RuntimeError, match=msg):
        LocateUnplacedObservableOp(bases, obs, patches)


@pytest.mark.parametrize(("bases", "patch_index"), [("X", 0), ("XZX", 1), ("XZX", 0), ("ZZZX", 3)])
def test_locate_unplaced_observable_basis_on(
    bases: Sequence[Literal["X", "Y", "Z"]], patch_index: int
) -> None:
    test_op = t.TestOp(
        result_types=[
            UnplacedObservableType(),
            *(RotatedPlanarPatchType((3, 3), NoneAttr()) for _ in range(len(bases))),
        ]
    )
    obs, *patches = test_op.results
    locate_op = LocateUnplacedObservableOp(str(bases), obs, patches)
    assert locate_op.basis_on(patches[patch_index]) == PauliAttr.coerce(bases[patch_index])


def test_locate_unplaced_observable_basis_on_raises_on_invalid_patch() -> None:
    test_op = t.TestOp(
        result_types=[
            UnplacedObservableType(),
            *(RotatedPlanarPatchType((3, 3), NoneAttr()) for _ in range(4)),
        ]
    )
    obs, *patches, last_patch = test_op.results
    locate_op = LocateUnplacedObservableOp("X" * len(patches), obs, patches)
    msg = re.escape(
        "The provided patch is not an operand of the sobs.locate_unplaced_observable operation."
    )
    with pytest.raises(ValueError, match=msg):
        _ = locate_op.basis_on(last_patch)


# endregion


# region Placed operation definition


@pytest.mark.parametrize(
    ("qubits", "err_msg"),
    [
        ([QubitType()], None),
        ([QubitType()] * 5, None),
        ([], re.escape("incorrect length for range variable:\nexpected integer >= 1, got 0")),
        (
            [QubitRegType(1)],
            re.escape("!qcore.qubit_reg<1> should be of base attribute qcore.qubit"),
        ),
    ],
)
def test_observable_declaration_op(qubits: Sequence[QubitType], err_msg: str | None) -> None:
    test_op = t.TestOp(result_types=qubits)
    op = DecObservableOp(test_op.res)

    if err_msg is not None:
        with pytest.raises(VerifyException, match=err_msg):
            op.verify()
    else:
        op.verify()

    assert len(op.results) == 1
    assert isinstance(op.result_types[0], ObservableType)


@pytest.mark.parametrize(
    ("num_qubits", "expected_error"),
    [(0, "incorrect length for range variable"), (1, None), (5, None)],
)
def test_locate_observable(
    num_qubits: int,
    expected_error: str | None,
) -> None:
    test_op = t.TestOp(result_types=[ObservableType(), *(QubitType() for _ in range(num_qubits))])
    obs, *qubits = test_op.results
    op = LocateObservableOp(obs, qubits)
    if expected_error is None:
        op.verify()
    else:
        with pytest.raises(VerifyException, match=expected_error):
            op.verify()


@pytest.mark.parametrize(
    ("num_qubits", "num_measurements", "expected_error"),
    [(0, 1, "incorrect length for range variable"), (1, 0, None), (5, 10, None)],
)
def test_move_observable(
    num_qubits: int,
    num_measurements: int,
    expected_error: str | None,
) -> None:
    test_op = t.TestOp(
        result_types=[
            ObservableType(),
            *(QubitType() for _ in range(num_qubits)),
            *(i1 for _ in range(num_measurements)),
        ]
    )
    obs = test_op.results[0]
    qubits = test_op.results[1 : 1 + num_qubits]
    measurements = test_op.results[1 + num_qubits :]
    op = MoveObservableOp(obs, qubits, measurements)
    if expected_error is None:
        op.verify()
    else:
        with pytest.raises(VerifyException, match=expected_error):
            op.verify()


# endregion
