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
    assert quoted <= {"0.57", "0.72", "0.80", "1.00"}, quoted
