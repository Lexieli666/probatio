"""Per-case and suite-level stability statistics, and the ``flaky_tolerant`` marker.

Everything here is arithmetic over booleans: how many of a case's runs passed, what interval that
supports, and whether the case cleared the floor its author declared. None of it touches a
provider, a fixture or a pytest session, so all of it is testable without one.

Two positions are fixed here.

**A floor is declared, not inferred.** Without ``@flaky_tolerant`` a case's floor is 1.0 and every
run has to pass; with it the floor is ``p`` and the case passes when the *observed* pass rate
reaches it. The Wilson lower bound is reported beside that decision and never makes it, because a
bound that decided pass or fail would fail a case for being measured too few times — which is a
statement about the run length, not about the application.

**A stability score is a mean over cases that were actually repeated.** A suite run once has no
stability score at all (``None``), rather than a score of 1.0 that would read as "measured, and
perfect".
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Final

import pytest
from _pytest.mark import MarkDecorator
from pydantic import BaseModel, ConfigDict, Field

from ..errors import ProbatioConfigError
from .wilson import Z_95, wilson_interval

__all__ = [
    "DEFAULT_FLOOR",
    "FLAKY_MARKER",
    "CaseStability",
    "FlakyTolerance",
    "SuiteStability",
    "case_stability",
    "flaky_tolerant",
    "read_flaky_tolerance",
    "suite_stability",
]

FLAKY_MARKER: Final = "flaky_tolerant"
"""The pytest marker ``@flaky_tolerant`` applies, registered in :mod:`probatio.plugin`."""

DEFAULT_FLOOR: Final = 1.0
"""The pass rate a case must reach when it declares no tolerance: every run has to pass."""


class FlakyTolerance(BaseModel):
    """A case's declared tolerance for nondeterminism.

    Attributes:
        p: The pass rate the case must reach, from 0 to 1.
        n: How many times to run it. This overrides ``--runs`` for the marked test, because the
            rate the author declared was measured over a run length they chose.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    p: float = Field(ge=0.0, le=1.0)
    n: int = Field(ge=1)


class CaseStability(BaseModel):
    """What repeating one case measured.

    Attributes:
        runs: How many times the case ran.
        passes: How many of those runs had a passing verdict.
        pass_rate: ``passes / runs``.
        majority_verdict: Whether more than half the runs passed. A tie is not a majority.
        wilson_low: The Wilson 95% lower bound on the underlying pass rate.
        wilson_high: The Wilson 95% upper bound.
        floor: The pass rate this case had to reach: ``flaky_tolerant.p``, else 1.0.
        tolerated: Whether the case carried ``@flaky_tolerant``.
        met_floor: Whether ``pass_rate >= floor``, which is what decides the case.
        below_floor: Whether ``wilson_low < floor``, which is reported and decides nothing.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    runs: int = Field(ge=1)
    passes: int = Field(ge=0)
    pass_rate: float = Field(ge=0.0, le=1.0)
    majority_verdict: bool
    wilson_low: float = Field(ge=0.0, le=1.0)
    wilson_high: float = Field(ge=0.0, le=1.0)
    floor: float = Field(ge=0.0, le=1.0)
    tolerated: bool = False
    met_floor: bool
    below_floor: bool


class SuiteStability(BaseModel):
    """What repeating a whole suite measured.

    Attributes:
        stability_score: The mean pass rate over cases that ran more than once, or ``None`` when
            no case did — a suite run once has not measured stability and does not score it.
        n_repeated_cases: How many cases ran more than once.
        n_below_floor: How many of the repeated cases have a Wilson lower bound below their
            floor. Cases that ran once are not counted: one run supports no interval worth
            reporting, and counting them would say "every case in the suite" for a suite that
            simply was not run with ``--runs``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    stability_score: float | None = Field(default=None, ge=0.0, le=1.0)
    n_repeated_cases: int = Field(default=0, ge=0)
    n_below_floor: int = Field(default=0, ge=0)


def case_stability(
    verdicts: Sequence[bool], *, tolerance: FlakyTolerance | None = None, z: float = Z_95
) -> CaseStability:
    """Summarise one case's runs.

    Args:
        verdicts: One boolean per run, in run order.
        tolerance: The case's ``@flaky_tolerant`` declaration, or ``None``.
        z: The normal quantile for the interval.

    Returns:
        The statistics, including the floor the case had to clear and whether it did.

    Raises:
        ValueError: No runs were given; a case that never ran has nothing to summarise.
    """
    runs = len(verdicts)
    if runs == 0:
        raise ValueError("a case must run at least once to have a pass rate")
    passes = sum(1 for verdict in verdicts if verdict)
    pass_rate = passes / runs
    low, high = wilson_interval(passes, runs, z)
    floor = tolerance.p if tolerance is not None else DEFAULT_FLOOR
    return CaseStability(
        runs=runs,
        passes=passes,
        pass_rate=pass_rate,
        majority_verdict=passes * 2 > runs,
        wilson_low=low,
        wilson_high=high,
        floor=floor,
        tolerated=tolerance is not None,
        met_floor=pass_rate >= floor,
        below_floor=low < floor,
    )


def suite_stability(cases: Iterable[CaseStability]) -> SuiteStability:
    """Summarise a session's cases.

    Args:
        cases: One entry per case that ran.

    Returns:
        The suite statistics. Both figures are taken over the cases that ran more than once,
        which is the only population either of them says anything about.
    """
    repeated = [entry for entry in cases if entry.runs > 1]
    score = sum(entry.pass_rate for entry in repeated) / len(repeated) if repeated else None
    return SuiteStability(
        stability_score=score,
        n_repeated_cases=len(repeated),
        n_below_floor=sum(1 for entry in repeated if entry.below_floor),
    )


def flaky_tolerant(p: float, n: int) -> MarkDecorator:
    """Declare that a case is allowed to fail some of its runs.

    Args:
        p: The pass rate the case must reach, from 0 to 1.
        n: How many times to run the case; this overrides ``--runs`` for this test.

    Returns:
        The pytest marker to apply to the test function.

    Raises:
        ProbatioConfigError: ``p`` is outside ``[0, 1]`` or ``n`` is below one.
    """
    tolerance = _validated(p, n)
    marker: MarkDecorator = getattr(pytest.mark, FLAKY_MARKER)(p=tolerance.p, n=tolerance.n)
    return marker


def _validated(p: float, n: int) -> FlakyTolerance:
    """Build a tolerance, reporting a bad one as a config error rather than a pydantic one."""
    if not 0.0 <= p <= 1.0:
        raise ProbatioConfigError(f"@{FLAKY_MARKER} needs a pass rate between 0 and 1, not p={p!r}")
    if n < 1:
        raise ProbatioConfigError(f"@{FLAKY_MARKER} needs at least one run, not n={n!r}")
    return FlakyTolerance(p=p, n=n)


def read_flaky_tolerance(marks: Iterable[pytest.Mark]) -> FlakyTolerance | None:
    """Read a ``flaky_tolerant`` declaration off a test's markers.

    Args:
        marks: The markers on the requesting test, nearest first, as
            ``request.node.iter_markers(FLAKY_MARKER)`` yields them.

    Returns:
        The first tolerance found, or ``None`` when the test declares none.

    Raises:
        ProbatioConfigError: A marker was applied by hand with missing or invalid arguments. The
            decorator validates at import time; ``@pytest.mark.flaky_tolerant`` does not.
    """
    for mark in marks:
        if mark.args:
            raise ProbatioConfigError(
                f"@{FLAKY_MARKER} takes keyword arguments p= and n=, not {len(mark.args)} "
                "positional one(s)"
            )
        try:
            p = float(mark.kwargs["p"])
            n = int(mark.kwargs["n"])
        except KeyError as exc:
            raise ProbatioConfigError(
                f"@{FLAKY_MARKER} needs both p= and n=; {exc.args[0]!r} is missing"
            ) from exc
        except (TypeError, ValueError) as exc:
            raise ProbatioConfigError(f"@{FLAKY_MARKER} has an unusable argument: {exc}") from exc
        return _validated(p, n)
    return None
