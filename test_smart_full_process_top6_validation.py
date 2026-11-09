"""Regression: frozen-card numbers must be JSON integers, not coercible values."""

import pytest

from smart_full_process_pipeline import _valid_top6


def test_valid_top6_accepts_exactly_six_distinct_integer_numbers():
    assert _valid_top6([1, 2, 3, 4, 5, 60]) is True


@pytest.mark.parametrize("invalid", [
    [1.9, 2, 3, 4, 5, 6],
    [True, 2, 3, 4, 5, 6],
    ["1", 2, 3, 4, 5, 6],
    [1.0, 2, 3, 4, 5, 6],
    [1, 1, 3, 4, 5, 6],
    [0, 2, 3, 4, 5, 6],
    [1, 2, 3, 4, 5, 61],
])
def test_valid_top6_rejects_invalid_number_shapes(invalid):
    assert _valid_top6(invalid) is False
