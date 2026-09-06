"""Phase 9: ``docs/stability.md`` says what the code does, and quotes no number it did not."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from probatio.stability import DEFAULT_FLOOR, wilson_interval

DOC = Path(__file__).resolve().parents[1] / "docs" / "stability.md"
TEXT = DOC.read_text(encoding="utf-8")


def test_the_two_intervals_the_doc_quotes_are_the_ones_the_code_computes() -> None:
    for k, quoted in ((5, "[0.57, 1.00]"), (10, "[0.72, 1.00]")):
        low, high = wilson_interval(k, k)
        assert f"[{low:.2f}, {high:.2f}]" == quoted, k
        assert quoted in TEXT


def test_the_doc_states_the_default_floor() -> None:
    assert f"otherwise {DEFAULT_FLOOR}" in TEXT


def test_the_doc_says_what_runs_does_to_fixtures() -> None:
    """Spec §3.10 asks for exactly this sentence to exist somewhere."""
    fixtures = TEXT.split("## What `--runs` does to fixtures", 1)[1]
    assert "shared across all" in fixtures
    assert "model's nondeterminism, not state leakage" in fixtures


def test_the_doc_says_a_flaky_case_should_use_scores_not_output() -> None:
    """Spec §3.6 asks for exactly this sentence to exist somewhere."""
    assert "`snapshot: scores`, not `snapshot: output`" in TEXT


def test_the_doc_says_the_bound_decides_nothing() -> None:
    assert "the observed pass rate is what decides the case" in TEXT


def test_the_doc_uses_the_word_confidence_only_to_refuse_it() -> None:
    """Spec §9 rejects "confidence" for anything that is not the Wilson interval."""
    for line in TEXT.splitlines():
        if "confidence" in line.lower():
            assert "never calls anything else" in line, line


@pytest.mark.parametrize("heading", ["What is reported", "`@flaky_tolerant(p, n)`", "Cost"])
def test_the_doc_covers_the_sections_the_specification_asks_for(heading: str) -> None:
    assert f"## {heading}" in TEXT


def test_no_pass_rate_in_the_doc_is_quoted_from_a_run_that_is_not_committed() -> None:
    """The only numbers here are arithmetic; the demo's own figures live in PROGRESS.md."""
    quoted = set(re.findall(r"\b0\.\d\d\b", TEXT))
    assert quoted <= {"0.00", "0.38", "0.57", "0.72", "0.80", "0.90", "1.00"}, quoted


def test_the_stability_score_the_doc_explains_is_the_mean_of_the_rates_the_run_printed() -> None:
    """Phase 13: the doc reads `0.90` off the committed run's own cases table, so re-derive it."""
    progress = (Path(__file__).resolve().parents[1] / "PROGRESS.md").read_text(encoding="utf-8")
    block = progress.split("pytest examples/demo_suite --runs 5", 1)[1].split("```", 2)[1]
    rows = [line for line in block.splitlines() if "[0." in line]
    rates = [float(line.split()[3]) for line in rows]
    assert len(rates) == 12
    assert sorted(rates) == [0.0, 0.8] + [1.0] * 10
    assert f"{sum(rates) / len(rates):.2f}" == "0.90"
    assert f"stability score: {sum(rates) / len(rates):.2f} over {len(rates)} repeated case(s)" in (
        TEXT
    )


def test_the_flaky_lower_bound_the_doc_quotes_is_the_one_wilson_computes() -> None:
    low, _ = wilson_interval(4, 5)
    assert f"whose observed 0.80 still has a lower bound of {low:.2f}" in TEXT


def test_the_doc_points_at_the_commit_that_produced_the_run_it_quotes() -> None:
    assert "commit `4c2114e`" in TEXT


def test_per_run_fixture_isolation_is_named_as_roadmap_and_not_as_shipped() -> None:
    fixtures = TEXT.split("## What `--runs` does to fixtures", 1)[1]
    assert "on the roadmap" in fixtures
    assert "is not in v0.1" in " ".join(fixtures.split())


def test_the_doc_warns_that_the_below_floor_count_needs_a_long_enough_run() -> None:
    """Phase 10: the count is `12 of 12` in the committed run, for a reason worth stating."""
    assert "12 of 12" in TEXT
    assert "no case can clear a floor of 1.0" in TEXT


def test_the_below_floor_figure_is_quoted_from_a_committed_run() -> None:
    """Spec §9: no number in a doc without a committed file behind it."""
    progress = (Path(__file__).resolve().parents[1] / "PROGRESS.md").read_text(encoding="utf-8")
    assert "cases whose Wilson lower bound is below their floor: 12 of 12" in progress


def test_the_doc_says_a_price_table_re_records_the_scores_baselines() -> None:
    """DECISIONS 68's cost, written down where a reader of `--runs` will meet it."""
    section = TEXT.split("## Snapshots and budgets", 1)[1]
    assert "--probatio-prices" in section
    assert "--update-baseline" in section
