"""Phase 4: Cohen's kappa, checked longhand and against Consilium's published numbers.

The two Consilium samples are the cross-check spec §3.5 asks for: the numbers below are the ones
published in Consilium-Health's ``docs/EVALUATION.md``, computed there by a different
implementation, so this test fails if Probatio's ten lines of arithmetic disagree with it.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from probatio import ProbatioConfigError
from probatio.judge import cohens_kappa

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "consilium"
SAMPLE_1 = FIXTURES / "judge-sample-labeled.csv"
SAMPLE_2 = FIXTURES / "judge-sample-2-labeled.csv"


def columns(path: Path, first: str, second: str) -> tuple[list[str], list[str]]:
    """Read two label columns out of a labelled sample."""
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [row[first] for row in rows], [row[second] for row in rows]


# --- the hand-computed example ------------------------------------------------------------------


def test_kappa_on_a_two_by_two_example_computed_by_hand() -> None:
    """Ten items, worked through longhand; every number below is arithmetic, not a fixture.

    Judge:  s s s s s s u u u u        (6 supported, 4 unsupported)
    Human:  s s s s u u s u u u        (5 supported, 5 unsupported)

    Confusion table, keyed (judge, human):
        (s, s) = 4      (s, u) = 2
        (u, s) = 1      (u, u) = 3

    Observed agreement p_o = (4 + 3) / 10                       = 0.70
    Chance agreement   p_e = (6/10)(5/10) + (4/10)(5/10)
                           = 0.30 + 0.20                        = 0.50
    Kappa                  = (0.70 - 0.50) / (1 - 0.50)
                           = 0.20 / 0.50                        = 0.40
    """
    judge = ["s", "s", "s", "s", "s", "s", "u", "u", "u", "u"]
    human = ["s", "s", "s", "s", "u", "u", "s", "u", "u", "u"]
    result = cohens_kappa(judge, human)

    assert result.n == 10
    assert result.table == {("s", "s"): 4, ("s", "u"): 2, ("u", "s"): 1, ("u", "u"): 3}
    assert result.agreement == pytest.approx(0.70)
    assert result.kappa == pytest.approx(0.40)
    assert result.labels == ["s", "u"]


def test_kappa_is_zero_when_the_raters_agree_exactly_as_often_as_chance_predicts() -> None:
    """p_o = 5/10; p_e = (5/10)(4/10) + (5/10)(6/10) = 0.20 + 0.30 = 0.50, so kappa is 0."""
    judge = ["s", "s", "s", "s", "s", "u", "u", "u", "u", "u"]
    human = ["s", "s", "u", "u", "u", "s", "s", "u", "u", "u"]
    result = cohens_kappa(judge, human)
    assert result.agreement == pytest.approx(0.5)
    assert result.kappa == pytest.approx(0.0)


def test_kappa_is_negative_when_the_raters_agree_less_often_than_chance() -> None:
    judge = ["s", "s", "u", "u"]
    human = ["u", "u", "s", "s"]
    result = cohens_kappa(judge, human)
    assert result.agreement == 0.0
    assert result.kappa == pytest.approx(-1.0)


def test_perfect_agreement_over_two_labels_is_kappa_one() -> None:
    result = cohens_kappa(["s", "u", "s", "u"], ["s", "u", "s", "u"])
    assert result.agreement == 1.0
    assert result.kappa == 1.0


def test_one_label_used_by_both_raters_is_decided_rather_than_computed() -> None:
    """p_e is 1 and the formula is 0/0; agreement is necessarily perfect (DECISIONS 24)."""
    result = cohens_kappa(["s", "s", "s"], ["s", "s", "s"])
    assert result.agreement == 1.0
    assert result.kappa == 1.0
    assert result.table == {("s", "s"): 3}


def test_the_table_is_the_full_grid_so_an_unused_cell_is_present_and_zero() -> None:
    result = cohens_kappa(["s", "s"], ["s", "u"])
    assert result.table == {("s", "s"): 1, ("s", "u"): 1, ("u", "s"): 0, ("u", "u"): 0}


def test_kappa_handles_more_than_two_labels() -> None:
    """Nothing in the implementation assumes a binary rubric."""
    judge = ["a", "b", "c", "a", "b", "c"]
    human = ["a", "b", "c", "b", "c", "a"]
    result = cohens_kappa(judge, human)
    assert result.labels == ["a", "b", "c"]
    assert result.n == 6
    assert result.agreement == pytest.approx(0.5)
    # p_e = 3 * (2/6)(2/6) = 1/3; kappa = (0.5 - 1/3) / (1 - 1/3) = 0.25
    assert result.kappa == pytest.approx(0.25)


# --- the Consilium samples ----------------------------------------------------------------------


def test_sample_1_reproduces_the_published_agreement_and_kappa() -> None:
    judge, human = columns(SAMPLE_1, "judge_label", "human_label")
    result = cohens_kappa(judge, human)
    assert result.n == 40
    assert round(result.agreement, 3) == 0.675
    assert round(result.kappa, 3) == 0.350


def test_sample_2_reproduces_the_published_agreement_kappa_and_table() -> None:
    judge, human = columns(SAMPLE_2, "judge_label", "human_label")
    result = cohens_kappa(judge, human)
    assert result.n == 40
    assert round(result.agreement, 3) == 0.800
    assert round(result.kappa, 3) == 0.592
    assert result.table == {
        ("unsupported", "unsupported"): 19,
        ("supported", "supported"): 13,
        ("supported", "unsupported"): 5,
        ("unsupported", "supported"): 3,
    }


def test_kappa_is_symmetric_in_its_two_arguments() -> None:
    judge, human = columns(SAMPLE_2, "judge_label", "human_label")
    assert cohens_kappa(judge, human).kappa == cohens_kappa(human, judge).kappa


# --- refusals -----------------------------------------------------------------------------------


def test_sequences_of_different_lengths_do_not_label_the_same_items() -> None:
    with pytest.raises(ProbatioConfigError) as excinfo:
        cohens_kappa(["s", "u"], ["s"])
    assert "different lengths" in str(excinfo.value)


def test_no_labels_at_all_is_a_config_error() -> None:
    with pytest.raises(ProbatioConfigError) as excinfo:
        cohens_kappa([], [])
    assert "no labels" in str(excinfo.value)
