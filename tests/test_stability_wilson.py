"""Phase 9: the Wilson interval, worked longhand and pinned at both ends."""

from __future__ import annotations

from math import sqrt

import pytest

from probatio.stability import Z_95, wilson_interval


def test_the_interval_for_eight_of_ten_is_the_arithmetic_written_out() -> None:
    """Spec §3.10 acceptance: (k=8, n=10) against the formula, computed step by step here."""
    k, n, z = 8, 10, Z_95

    z_squared = z * z  # 1.959964^2
    denominator = n + z_squared  # 10 + 3.841459 = 13.841459
    centre = (k + z_squared / 2) / denominator  # (8 + 1.920729) / 13.841459
    spread = sqrt(k * (n - k) / n + z_squared / 4)  # sqrt(8*2/10 + 0.960365)
    half_width = z / denominator * spread  # 1.959964 / 13.841459 * sqrt(2.560365)
    expected = (centre - half_width, centre + half_width)

    assert wilson_interval(k, n) == pytest.approx(expected)
    assert wilson_interval(k, n) == pytest.approx((0.490162, 0.943318), abs=5e-7)
    assert 0.0 < wilson_interval(k, n)[0] < 0.8 < wilson_interval(k, n)[1] < 1.0


def test_no_successes_gives_a_lower_bound_of_exactly_zero() -> None:
    low, high = wilson_interval(0, 10)
    assert low == 0.0
    assert isinstance(low, float)
    assert 0.0 < high < 1.0


def test_every_run_passing_gives_an_upper_bound_of_exactly_one() -> None:
    low, high = wilson_interval(10, 10)
    assert high == 1.0
    assert 0.0 < low < 1.0


def test_one_run_that_passed_still_supports_a_wide_interval() -> None:
    """The whole point: a single green run does not license a claim of certainty."""
    low, high = wilson_interval(1, 1)
    assert high == 1.0
    assert low == pytest.approx(0.206549, abs=5e-7)


def test_more_runs_narrow_the_interval() -> None:
    widths = [wilson_interval(n, n)[1] - wilson_interval(n, n)[0] for n in (1, 5, 10, 50, 100)]
    assert widths == sorted(widths, reverse=True)


def test_the_interval_is_symmetric_under_swapping_successes_for_failures() -> None:
    low, high = wilson_interval(3, 10)
    other_low, other_high = wilson_interval(7, 10)
    assert low == pytest.approx(1.0 - other_high)
    assert high == pytest.approx(1.0 - other_low)


def test_a_wider_z_gives_a_wider_interval() -> None:
    narrow = wilson_interval(8, 10, z=1.0)
    wide = wilson_interval(8, 10, z=2.5)
    assert wide[0] < narrow[0] <= narrow[1] < wide[1]


@pytest.mark.parametrize(
    ("k", "n", "z", "match"),
    [
        (0, 0, 1.0, "at least one trial"),
        (3, 2, 1.0, "between 0 and n=2"),
        (-1, 2, 1.0, "between 0 and n=2"),
        (1, 2, 0.0, "z must be positive"),
        (1, 2, -1.0, "z must be positive"),
    ],
)
def test_an_impossible_interval_is_refused(k: int, n: int, z: float, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        wilson_interval(k, n, z)


def test_the_default_quantile_is_the_two_sided_ninety_five_percent_one() -> None:
    assert Z_95 == 1.959964
    assert wilson_interval(8, 10) == wilson_interval(8, 10, z=Z_95)
