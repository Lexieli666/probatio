"""Flakiness statistics: the second of Probatio's two headline features.

An LLM application is not deterministic, and a test suite that runs each case once and prints a
tick is asserting something it did not measure. ``--runs N`` runs a case N times and reports the
pass rate with a Wilson 95% interval around it; the suite reports the mean of those rates as a
stability score, and how many cases have a lower bound under the floor their author declared.

``@flaky_tolerant(p, n)`` is how an author declares that floor. It is the honest form of the
retry decorators other frameworks ship: a retry hides the failures, and this one counts them and
holds the case to a rate.
"""

from __future__ import annotations

from .stats import (
    DEFAULT_FLOOR,
    FLAKY_MARKER,
    CaseStability,
    FlakyTolerance,
    SuiteStability,
    case_stability,
    flaky_tolerant,
    read_flaky_tolerance,
    suite_stability,
)
from .wilson import Z_95, wilson_interval

__all__ = [
    "DEFAULT_FLOOR",
    "FLAKY_MARKER",
    "Z_95",
    "CaseStability",
    "FlakyTolerance",
    "SuiteStability",
    "case_stability",
    "flaky_tolerant",
    "read_flaky_tolerance",
    "suite_stability",
    "wilson_interval",
]
