"""Phase 3: the trigram backend, the backend registry and the ``similarity`` assertion."""

from __future__ import annotations

import pytest

from probatio import ProbatioConfigError
from probatio.assertions import (
    SIMILARITY_BACKENDS,
    SimilarityBackend,
    TrigramCosine,
    evaluate_similarity,
    get_backend,
)
from probatio.assertions.backends import normalize, trigrams
from probatio.case import SimilarityAssertion

TRIGRAM = TrigramCosine()

REFERENCE = "Metformin is the usual initial medication for type 2 diabetes."


def similarity(**fields: object) -> SimilarityAssertion:
    return SimilarityAssertion.model_validate({"type": "similarity", **fields})


# --- normalisation and trigram extraction ------------------------------------------------------


def test_normalize_lowercases_and_collapses_whitespace() -> None:
    assert normalize("  The\tQuick\n\nBrown  ") == "the quick brown"


def test_trigrams_are_character_trigrams_over_the_whole_string_without_padding() -> None:
    assert sorted(trigrams("abcd")) == ["abc", "bcd"]
    assert trigrams("aaaa")["aaa"] == 2
    assert trigrams("a b c") == {"a b": 1, " b ": 1, "b c": 1}


def test_a_string_shorter_than_three_characters_has_no_trigrams() -> None:
    assert trigrams("ab") == {}
    assert trigrams("") == {}


def test_trigrams_span_word_boundaries_so_word_order_matters_less_than_overlap() -> None:
    assert " b " in trigrams("a b c")


# --- TrigramCosine edge cases ------------------------------------------------------------------


def test_identical_strings_score_exactly_one() -> None:
    assert TRIGRAM.similarity(REFERENCE, REFERENCE) == 1.0


def test_strings_differing_only_in_case_and_whitespace_score_exactly_one() -> None:
    assert TRIGRAM.similarity("The  Quick\nBrown", "the quick brown") == 1.0


def test_strings_with_no_shared_trigram_score_zero() -> None:
    assert TRIGRAM.similarity("abcdef", "uvwxyz") == 0.0


def test_short_strings_with_no_trigrams_score_one_when_equal_and_zero_otherwise() -> None:
    """Fewer than three characters means no trigram vector at all, so equality decides."""
    assert TRIGRAM.similarity("ab", "ab") == 1.0
    assert TRIGRAM.similarity("AB", " ab ") == 1.0
    assert TRIGRAM.similarity("ab", "cd") == 0.0
    assert TRIGRAM.similarity("", "") == 1.0


def test_one_short_string_against_a_long_one_scores_zero() -> None:
    assert TRIGRAM.similarity("ab", REFERENCE) == 0.0
    assert TRIGRAM.similarity(REFERENCE, "ab") == 0.0


def test_the_score_is_symmetric_and_inside_the_unit_interval() -> None:
    pairs = [(REFERENCE, "I don't know."), (REFERENCE, "metformin"), ("a b c", "c b a")]
    for left, right in pairs:
        forward = TRIGRAM.similarity(left, right)
        assert forward == pytest.approx(TRIGRAM.similarity(right, left))
        assert 0.0 <= forward <= 1.0


def test_a_hand_checked_score_matches_the_cosine_computed_longhand() -> None:
    """``abcd`` has trigrams {abc, bcd}; ``abcde`` has {abc, bcd, cde}; cosine = 2/(√2·√3)."""
    expected = 2 / (2**0.5 * 3**0.5)
    assert TRIGRAM.similarity("abcd", "abcde") == pytest.approx(expected)


def test_scores_are_ordered_by_how_much_wording_is_shared() -> None:
    reorder = TRIGRAM.similarity(
        REFERENCE, "The usual initial medication for type 2 diabetes is metformin."
    )
    reword = TRIGRAM.similarity(
        REFERENCE, "For newly diagnosed type 2 diabetes, metformin is normally started first."
    )
    refusal = TRIGRAM.similarity(REFERENCE, "I don't know.")
    assert 1.0 > reorder > reword > refusal


# --- the registry ------------------------------------------------------------------------------


def test_the_default_backend_is_registered_under_trigram() -> None:
    assert isinstance(get_backend("trigram"), TrigramCosine)
    assert get_backend("trigram") is SIMILARITY_BACKENDS["trigram"]


def test_no_embedding_backend_is_shipped() -> None:
    """A model download in the default install would break the offline constraint."""
    assert list(SIMILARITY_BACKENDS) == ["trigram"]


def test_trigram_cosine_satisfies_the_backend_protocol() -> None:
    assert isinstance(TRIGRAM, SimilarityBackend)


def test_an_unregistered_backend_name_raises_and_lists_what_is_registered() -> None:
    with pytest.raises(ProbatioConfigError, match=r"no similarity backend named 'embedding'"):
        get_backend("embedding")


# --- the assertion: pass, fail, malformed input ------------------------------------------------


def test_similarity_passes_at_or_above_tau() -> None:
    result = evaluate_similarity(similarity(reference=REFERENCE, tau=0.35), REFERENCE)
    assert result.assertion_type == "similarity"
    assert result.passed
    assert result.score == 1.0
    assert result.detail == "trigram similarity 1.000 is at or above tau 0.350"


def test_similarity_passes_when_the_score_equals_tau_exactly() -> None:
    result = evaluate_similarity(similarity(reference="ab", tau=1.0), "ab")
    assert result.passed


def test_similarity_fails_below_tau_and_reports_both_numbers() -> None:
    result = evaluate_similarity(similarity(reference=REFERENCE, tau=0.35), "I don't know.")
    assert not result.passed
    assert result.score == 0.0
    assert result.detail == "trigram similarity 0.000 is below tau 0.350"


def test_an_empty_reference_is_a_failed_result_with_no_score() -> None:
    result = evaluate_similarity(similarity(reference="", tau=0.0), "any output at all")
    assert not result.passed
    assert result.score is None
    assert "reference is empty" in result.detail


def test_a_reference_that_is_only_whitespace_is_treated_as_empty() -> None:
    result = evaluate_similarity(similarity(reference="  \n\t ", tau=0.0), "any output")
    assert not result.passed
    assert result.score is None


def test_an_unregistered_backend_is_a_failed_result_not_an_exception() -> None:
    assertion = similarity(reference=REFERENCE, tau=0.35, backend="embedding")
    result = evaluate_similarity(assertion, REFERENCE)
    assert not result.passed
    assert result.score is None
    assert "no similarity backend named 'embedding'" in result.detail


def test_an_empty_output_against_a_real_reference_scores_zero() -> None:
    result = evaluate_similarity(similarity(reference=REFERENCE, tau=0.30), "")
    assert not result.passed
    assert result.score == 0.0
