from deltakit_compile.frontend.common._sequence import (
    _slice_len,
    does_not_contain_none_values,
)


def test_check_no_none_entries() -> None:
    assert does_not_contain_none_values([])
    assert does_not_contain_none_values(range(10))
    assert does_not_contain_none_values((1, 4, ""))
    assert not does_not_contain_none_values([1, 3, None, 4])


def test_slice_len() -> None:
    assert _slice_len(slice(10), 100) == 10
    assert _slice_len(slice(0, 10), 100) == 10
    assert _slice_len(slice(0, 10, 1), 100) == 10
    assert _slice_len(slice(10, 0, -1), 100) == 10
    assert _slice_len(slice(0, -1), 100) == 99
