"""Phase 3: the two substring assertions, ``contains`` and ``not_contains``."""

from __future__ import annotations

import pytest

from probatio.assertions import evaluate_contains, evaluate_not_contains
from probatio.case import ContainsAssertion, NotContainsAssertion


def contains(**fields: object) -> ContainsAssertion:
    return ContainsAssertion.model_validate({"type": "contains", **fields})


def not_contains(**fields: object) -> NotContainsAssertion:
    return NotContainsAssertion.model_validate({"type": "not_contains", **fields})


# --- contains: pass ----------------------------------------------------------------------------


def test_contains_all_present_passes_with_a_full_score() -> None:
    result = evaluate_contains(contains(all=["alpha", "beta"]), "alpha and beta")
    assert result.assertion_type == "contains"
    assert result.passed
    assert result.score == 1.0
    assert result.detail == "matched 2/2 substrings, case-insensitive"


def test_contains_any_needs_only_one_match_but_scores_the_fraction() -> None:
    """The verdict and the score disagree on purpose: ``any`` asked for one, one is what moved."""
    result = evaluate_contains(contains(any=["a", "b", "c", "d"]), "only a here")
    assert result.passed
    assert result.score == 0.25


def test_contains_all_and_any_together_pass_when_both_conditions_hold() -> None:
    assertion = contains(all=["lifestyle", "thiazide"], any=["ACE inhibitor", "angiotensin"])
    result = evaluate_contains(assertion, "Lifestyle changes, thiazide diuretics, ACE inhibitors.")
    assert result.passed
    assert result.score == pytest.approx(0.75)


def test_contains_folds_case_by_default() -> None:
    assert evaluate_contains(contains(any=["METFORMIN"]), "metformin").passed


# --- contains: fail ----------------------------------------------------------------------------


def test_contains_fails_and_names_the_missing_required_substrings() -> None:
    result = evaluate_contains(contains(all=["alpha", "beta"]), "alpha only")
    assert not result.passed
    assert result.score == 0.5
    assert "missing required 'beta'" in result.detail
    assert "matched 1/2 substrings, case-insensitive" in result.detail


def test_contains_fails_and_names_the_whole_any_group_when_none_of_it_matched() -> None:
    result = evaluate_contains(contains(any=["psychotherapy", "SSRI"]), "I don't know.")
    assert not result.passed
    assert result.score == 0.0
    assert result.detail == (
        "none of 'psychotherapy', 'SSRI' appear; matched 0/2 substrings, case-insensitive"
    )


def test_contains_reports_both_faults_at_once() -> None:
    assertion = contains(all=["alpha"], any=["beta", "gamma"])
    result = evaluate_contains(assertion, "nothing relevant")
    assert not result.passed
    assert "missing required 'alpha'" in result.detail
    assert "none of 'beta', 'gamma' appear" in result.detail


def test_contains_case_sensitive_fails_on_a_casing_change() -> None:
    result = evaluate_contains(contains(any=["Metformin"], case_sensitive=True), "metformin")
    assert not result.passed
    assert "case-sensitive" in result.detail


# --- contains: malformed input -----------------------------------------------------------------


def test_a_contains_assertion_that_asks_for_nothing_is_rejected_at_load_time() -> None:
    """The malformed input for ``contains`` is caught by the model, so no output can pass it."""
    with pytest.raises(Exception, match="at least one of 'any' or 'all'"):
        contains()


def test_contains_handles_an_empty_output_without_raising() -> None:
    result = evaluate_contains(contains(all=["alpha"]), "")
    assert not result.passed
    assert result.score == 0.0


def test_contains_handles_an_output_that_is_only_whitespace() -> None:
    assert not evaluate_contains(contains(any=["alpha"]), "   \n\t ").passed


# --- not_contains ------------------------------------------------------------------------------


def test_not_contains_passes_when_nothing_forbidden_appears() -> None:
    result = evaluate_not_contains(not_contains(all=["I don't know"]), "Metformin, usually.")
    assert result.assertion_type == "not_contains"
    assert result.passed
    assert result.score == 1.0
    assert result.detail == "absent 1/1 forbidden substrings, case-insensitive"


def test_not_contains_fails_and_quotes_the_substring_that_appeared() -> None:
    result = evaluate_not_contains(not_contains(all=["I don't know"]), "I don't know.")
    assert not result.passed
    assert result.score == 0.0
    assert result.detail == (
        'forbidden "I don\'t know" appears; absent 0/1 forbidden substrings, case-insensitive'
    )


def test_not_contains_scores_the_fraction_absent() -> None:
    forbidden = ["alpha", "beta", "gamma", "delta"]
    result = evaluate_not_contains(not_contains(all=forbidden), "alpha and beta")
    assert not result.passed
    assert result.score == 0.5
    assert "forbidden 'alpha', 'beta' appears" in result.detail


def test_not_contains_folds_case_by_default_and_honours_case_sensitive() -> None:
    assert not evaluate_not_contains(not_contains(all=["i don't know"]), "I DON'T KNOW").passed
    assert evaluate_not_contains(
        not_contains(all=["i don't know"], case_sensitive=True), "I DON'T KNOW"
    ).passed


def test_an_empty_not_contains_list_is_rejected_at_load_time() -> None:
    with pytest.raises(Exception, match="at least 1 item"):
        not_contains(all=[])


def test_not_contains_handles_an_empty_output() -> None:
    assert evaluate_not_contains(not_contains(all=["alpha"]), "").passed
