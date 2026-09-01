import operator

import pytest

from deltakit_compile.frontend.common._vector import Vector, is_iterable


def test_is_iterable() -> None:
    assert is_iterable([])
    assert is_iterable(())
    assert is_iterable((0,))
    assert is_iterable(range(10))
    assert is_iterable("test")
    assert not is_iterable(1)
    assert not is_iterable(1.0)


def test_initialisation() -> None:
    assert Vector([])._entries == ()
    assert Vector([0, 0, 0, 0, 0])._entries == (0, 0, 0, 0, 0)
    assert Vector(1.0)._entries == (1.0,)
    assert Vector(1)._entries == (1,)
    assert Vector(1, 2, 3, 4)._entries == (1, 2, 3, 4)


def test_incorrect_initialisation() -> None:
    msg = r"Got an iterable as first argument and some remaining entries."
    with pytest.raises(ValueError, match=msg):
        Vector([1.0], 2.0)  # type: ignore[call-overload]


def test_len() -> None:
    assert len(Vector(*(i for i in range(10)))) == 10
    assert len(Vector(range(10))) == 10
    assert len(Vector(1)) == 1
    assert len(Vector([])) == 0


def test_equality() -> None:
    assert Vector(1) == Vector(1)
    assert Vector([]) == Vector([])
    assert Vector(1, 2, 3) == Vector(1, 2, 3)
    assert Vector([1, 2, 3, -1]) == Vector([1, 2, 3, -1])
    assert Vector(1, 2) == (1, 2)
    assert Vector(1, 2) == [1, 2]

    assert Vector(1) != Vector(2)
    assert Vector(1, 2) != Vector(2, 1)
    assert Vector([1, 3, 5]) != Vector([1, 3, 5, 2])
    assert Vector([]) != Vector(12)
    assert Vector(1) != 1
    assert Vector([]) != 0


def test_hash() -> None:
    assert hash(Vector(1)) == hash(Vector(1))
    assert hash(Vector([])) == hash(Vector([]))
    assert hash(Vector(1, 2, 3)) == hash(Vector(1, 2, 3))
    assert hash(Vector([1, 2, 3, -1])) == hash(Vector([1, 2, 3, -1]))


@pytest.mark.parametrize("op", [operator.add, operator.sub])
def test_binary_op(op) -> None:
    assert op(Vector(1), Vector(23)) == Vector(op(1, 23))
    assert op(Vector(-1), Vector(1)) == Vector(op(-1, 1))
    assert op(Vector([]), Vector([])) == Vector([])
    assert op(Vector([1, 2, 3]), Vector([-1, -2, -3])) == Vector([op(1, -1), op(2, -2), op(3, -3)])
    assert op(Vector(1), (1,)) == Vector([op(1, 1)])
    assert op((1,), Vector(1)) == Vector([op(1, 1)])
    assert op(Vector(1), [1]) == Vector([op(1, 1)])
    assert op([1], Vector(1)) == Vector([op(1, 1)])


@pytest.mark.parametrize("op", [operator.add, operator.sub])
def test_binary_op_different_lengths(op) -> None:
    msg = "Could not apply operation between sequences of different length. Got 1 and 0."
    with pytest.raises(ValueError, match=msg):
        op(Vector(1), Vector([]))
    msg = "Could not apply operation between sequences of different length. Got 1 and 4."
    with pytest.raises(ValueError, match=msg):
        op(Vector(0), Vector([1, 2, 3, 4]))
    msg = "Could not apply operation between sequences of different length. Got 10 and 1000."
    with pytest.raises(ValueError, match=msg):
        op(Vector(range(10)), Vector(range(1000)))


def test_get_entry() -> None:
    vec = Vector(range(10))
    for i in range(10):
        assert vec[i] == i
    for i in range(-1, -11, -1):
        assert vec[i] == 10 + i
    assert Vector([893247])[0] == 893247
    with pytest.raises(IndexError):
        Vector([])[0]
    with pytest.raises(IndexError):
        Vector(range(10))[10]

    assert vec[1:5] == Vector(range(1, 5))


def test_as_vector() -> None:
    vec = Vector(range(10))
    assert Vector.as_vector(vec) == vec
    # Even stronger test to check that no copy is involved.
    assert Vector.as_vector(vec) is vec
    assert Vector.as_vector(1) == Vector(1)
    assert Vector.as_vector([1, 0, 2]) == Vector(1, 0, 2)


def test_str() -> None:
    assert str(Vector([])) == "()"
    assert str(Vector(1)) == "(1)"
    assert str(Vector(1, 4)) == "(1,4)"


def test_repr() -> None:
    assert repr(Vector([])) == "Vector(())"
    assert repr(Vector(1)) == "Vector((1))"
    assert repr(Vector(1, 4)) == "Vector((1,4))"
