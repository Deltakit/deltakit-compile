"""Tests for the MaxMinDict class in deltakit_compile.utilities.max_min_dict."""

from deltakit_compile.utilities.max_min_dict import MaxMinDict


class TestMaxMinDict:
    def test_max_min_dict_init(self):
        """Test that MaxMinDict initialises correctly with a dictionary of values."""
        d = MaxMinDict({-1: 2, 1: 3, 5: 2, 0: 5})
        assert d.max_key == 5
        assert d.min_key == -1
        assert d == {-1: 2, 1: 3, 5: 2, 0: 5}

    def test_max_min_dict_empty(self):
        """Test that MaxMinDict initialises correctly with an empty dictionary."""
        d = MaxMinDict()
        assert d.max_key is None
        assert d.min_key is None
        assert d == {}

    def test_max_min_dict_setting(self):
        """Test that adding two MaxMinDicts correctly combines their values and updates the max
        and min keys."""
        d1 = MaxMinDict({-1: 2, 1: 3})
        d1[0] = 5
        d1[3] = 2
        d1[-3] = 1

        assert d1.max_key == 3
        assert d1.min_key == -3
        assert d1 == {-1: 2, 1: 3, 0: 5, 3: 2, -3: 1}

    def test_max_min_dict_popping(self):
        """Test that popping values from a MaxMinDict correctly updates the max and min keys."""
        d1 = MaxMinDict({-1: 2, 1: 3, 5: 2, 0: 5})
        a = d1.pop_min_key()
        b = d1.pop_min_key()
        c = d1.pop_min_key()
        d = d1.pop_min_key()
        e = d1.pop_min_key()
        assert (a, b, c, d, e) == (-1, 0, 1, 5, None)
        assert d1.max_key is None
        assert d1.min_key is None

    def test_max_min_dict_setting_popping(self):
        """Test that setting and popping values from a MaxMinDict correctly updates the
        max and min keys."""
        d1 = MaxMinDict({-1: 2, 1: 3, 5: 2, 0: 5})
        d1[3] = 2
        d1[-3] = 1
        a = d1.pop_min_key()
        b = d1.pop_min_key()
        c = d1.pop_min_key()
        d = d1.pop_min_key()
        e = d1.pop_min_key()
        d1[4] = 1
        assert (a, b, c, d, e) == (-3, -1, 0, 1, 3)
        assert d1.max_key == 5
        assert d1.min_key == 4
