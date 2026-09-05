"""Phase 9: per-case and suite stability, and the ``flaky_tolerant`` marker."""

from __future__ import annotations

import pytest

from probatio import ProbatioConfigError, flaky_tolerant
from probatio.stability import (
    DEFAULT_FLOOR,
    FLAKY_MARKER,
    FlakyTolerance,
    case_stability,
    read_flaky_tolerance,
    suite_stability,
)


def mark(*args: object, **kwargs: object) -> object:
    """One ``flaky_tolerant`` marker, built the way pytest itself builds one."""
    return getattr(pytest.mark, FLAKY_MARKER)(*args, **kwargs).mark


# -- per case -------------------------------------------------------------------------------


def test_every_run_passing_is_a_rate_of_one_that_meets_the_default_floor() -> None:
    stats = case_stability([True] * 5)
    assert (stats.runs, stats.passes, stats.pass_rate) == (5, 5, 1.0)
    assert stats.floor == DEFAULT_FLOOR
    assert stats.met_floor is True
    assert stats.majority_verdict is True
    assert stats.wilson_high == 1.0


def test_one_failure_in_five_is_zero_point_eight_and_misses_the_default_floor() -> None:
    """Spec §3.10 acceptance: the ScriptedProvider case, without the marker."""
    stats = case_stability([False, True, True, True, True])
    assert stats.pass_rate == 0.8
    assert stats.met_floor is False
    assert stats.majority_verdict is True


def test_the_same_runs_pass_under_a_declared_tolerance() -> None:
    """Spec §3.10 acceptance: the same case with ``@flaky_tolerant(p=0.8, n=5)``."""
    stats = case_stability([False, True, True, True, True], tolerance=FlakyTolerance(p=0.8, n=5))
    assert (stats.floor, stats.tolerated, stats.met_floor) == (0.8, True, True)
    assert stats.below_floor is True, "0.8 observed does not prove 0.8 underlying"


def test_a_tie_is_not_a_majority() -> None:
    assert case_stability([True, False]).majority_verdict is False
    assert case_stability([True, True, False]).majority_verdict is True


def test_a_single_run_is_summarised_without_pretending_to_an_interval() -> None:
    stats = case_stability([True])
    assert (stats.runs, stats.pass_rate, stats.wilson_high) == (1, 1.0, 1.0)
    assert stats.wilson_low < 0.5


def test_a_case_that_never_ran_has_nothing_to_summarise() -> None:
    with pytest.raises(ValueError, match="at least once"):
        case_stability([])


# -- the suite ------------------------------------------------------------------------------


def test_the_stability_score_averages_only_the_repeated_cases() -> None:
    entries = [
        case_stability([True] * 5),
        case_stability([False, True, True, True, True]),
        case_stability([True]),
    ]
    suite = suite_stability(entries)
    assert suite.stability_score == pytest.approx(0.9)
    assert suite.n_repeated_cases == 2


def test_a_suite_run_once_has_no_stability_score_at_all() -> None:
    suite = suite_stability([case_stability([True]), case_stability([False])])
    assert suite.stability_score is None
    assert (suite.n_repeated_cases, suite.n_below_floor) == (0, 0)


def test_the_below_floor_count_covers_the_repeated_cases_only() -> None:
    entries = [
        case_stability([True] * 5),
        case_stability([True] * 5, tolerance=FlakyTolerance(p=0.5, n=5)),
        case_stability([True]),
    ]
    assert suite_stability(entries).n_below_floor == 1


def test_an_empty_suite_is_summarised_rather_than_refused() -> None:
    assert suite_stability([]).stability_score is None


# -- the marker -----------------------------------------------------------------------------


def test_the_decorator_applies_the_marker_with_both_keywords() -> None:
    decorator = flaky_tolerant(p=0.8, n=5)
    assert decorator.mark.name == FLAKY_MARKER
    assert decorator.mark.args == ()
    assert decorator.mark.kwargs == {"p": 0.8, "n": 5}


def test_the_decorator_can_still_be_applied_to_a_test_function() -> None:
    @flaky_tolerant(p=0.8, n=5)
    def sample() -> None:
        """A test function the decorator is applied to."""

    assert sample.pytestmark[0].name == FLAKY_MARKER


@pytest.mark.parametrize(("p", "n"), [(-0.1, 5), (1.5, 5), (0.8, 0), (0.8, -1)])
def test_an_impossible_tolerance_is_refused_at_import_time(p: float, n: int) -> None:
    with pytest.raises(ProbatioConfigError, match=FLAKY_MARKER):
        flaky_tolerant(p=p, n=n)


def test_reading_the_marker_off_a_test_returns_the_first_one() -> None:
    tolerance = read_flaky_tolerance([mark(p=0.8, n=5), mark(p=0.1, n=2)])
    assert tolerance == FlakyTolerance(p=0.8, n=5)


def test_a_test_without_the_marker_declares_no_tolerance() -> None:
    assert read_flaky_tolerance([]) is None


def test_a_hand_applied_marker_missing_an_argument_is_refused() -> None:
    with pytest.raises(ProbatioConfigError, match="'n' is missing"):
        read_flaky_tolerance([mark(p=0.8)])


def test_a_hand_applied_marker_with_positional_arguments_is_refused() -> None:
    with pytest.raises(ProbatioConfigError, match="keyword arguments"):
        read_flaky_tolerance([mark(0.8, 5)])


def test_a_hand_applied_marker_with_an_unusable_argument_is_refused() -> None:
    with pytest.raises(ProbatioConfigError, match="unusable argument"):
        read_flaky_tolerance([mark(p="most of the time", n=5)])


def test_a_hand_applied_marker_out_of_range_is_refused() -> None:
    with pytest.raises(ProbatioConfigError, match="between 0 and 1"):
        read_flaky_tolerance([mark(p=2.0, n=5)])
