"""The Wilson score interval, implemented by hand in ten lines and tested against arithmetic.

An LLM test that passed is not a test that will pass. Running a case once and printing a tick is
the pretence Probatio exists to drop, so a case run ``n`` times reports ``k/n`` with an interval
around it — and the interval is the Wilson score interval rather than the textbook normal
approximation, because at ``k == n``, which is the common case for a suite that is working, the
normal approximation has zero width and claims certainty from five observations.

Spec §9 rejects the word "confidence" for anything that is not this interval, so nothing else in
Probatio calls itself one.
"""

from __future__ import annotations

from math import sqrt
from typing import Final

__all__ = ["Z_95", "wilson_interval"]

Z_95: Final = 1.959964
"""The standard normal quantile for a two-sided 95% interval, to seven figures."""


def wilson_interval(k: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Return the Wilson score interval for ``k`` successes in ``n`` trials.

    The interval is centred on ``(k + z²/2) / (n + z²)`` with half-width
    ``z / (n + z²) · sqrt(k(n − k)/n + z²/4)``. At ``k == 0`` the arithmetic gives a lower bound of
    zero and at ``k == n`` an upper bound of one; both are returned exactly rather than as a float
    a hair away, so a report never prints ``1.000`` beside a bound that is not one.

    Args:
        k: Successes, from ``0`` to ``n``.
        n: Trials, at least one.
        z: The normal quantile. Defaults to :data:`Z_95`.

    Returns:
        ``(low, high)``, both in ``[0, 1]``, with ``low <= high``.

    Raises:
        ValueError: ``n`` is below one, ``k`` is outside ``0..n``, or ``z`` is not positive.
    """
    if n < 1:
        raise ValueError(f"a Wilson interval needs at least one trial, not n={n}")
    if not 0 <= k <= n:
        raise ValueError(f"k must be between 0 and n={n}, not {k}")
    if z <= 0:
        raise ValueError(f"z must be positive, not {z}")

    z_squared = z * z
    denominator = n + z_squared
    centre = (k + z_squared / 2) / denominator
    half_width = z / denominator * sqrt(k * (n - k) / n + z_squared / 4)
    low = 0.0 if k == 0 else max(0.0, centre - half_width)
    high = 1.0 if k == n else min(1.0, centre + half_width)
    return low, high
