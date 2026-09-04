"""``evaluate_case`` over the demo suite, which is the specification.

Phase 3 covered the four non-judge assertions; Phase 4 adds the judge, graded by the fake judge
the demo suite commits, with its rubric found beside the tests rather than under rootdir.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from probatio import AssertionResult, FakeProvider, LLMCase, load_cases
from probatio.judge import ValidationRecord, resolve_rubric, write_validation_record
from probatio.runner import evaluate_case

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO = REPO_ROOT / "examples" / "demo_suite"
DEMO_RUBRICS = DEMO / "rubrics"

CASES = load_cases(DEMO / "cases")
JUDGED = [case for case in CASES if any(a.type == "judge" for a in case.assertions)]

Answers = Callable[[LLMCase], str]


def non_judge(case: LLMCase, results: list[AssertionResult]) -> list[AssertionResult]:
    return [
        result
        for assertion, result in zip(case.assertions, results, strict=True)
        if assertion.type != "judge"
    ]


# --- shape -------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_one_result_per_assertion_in_declaration_order(
    case: LLMCase, scripted_answer: Answers
) -> None:
    results = evaluate_case(case, scripted_answer(case))
    assert [result.assertion_type for result in results] == [a.type for a in case.assertions]


def test_every_assertion_runs_even_after_one_of_them_fails() -> None:
    """The point of returning results instead of raising: a report shows every fault at once."""
    case = LLMCase.model_validate(
        {
            "id": "many",
            "input": "q?",
            "assertions": [
                {"type": "contains", "all": ["absent"]},
                {"type": "schema_valid", "schema": {"type": "object"}},
                {"type": "similarity", "reference": "a reference sentence", "tau": 0.9},
                {"type": "not_contains", "all": ["prose"]},
                {"type": "judge", "rubric": "faithfulness"},
            ],
        }
    )
    results = evaluate_case(case, "some prose")
    assert len(results) == 5
    assert not any(result.passed for result in results)


def test_evaluate_case_returns_results_and_never_raises_on_a_broken_output() -> None:
    case = LLMCase.model_validate(
        {
            "id": "broken",
            "input": "q?",
            "assertions": [
                {"type": "schema_valid", "schema_file": "does/not/exist.json"},
                {"type": "similarity", "reference": "", "tau": 0.1},
            ],
        }
    )
    results = evaluate_case(case, "not json at all")
    assert [result.passed for result in results] == [False, False]


# --- the demo suite: acceptance ----------------------------------------------------------------


@pytest.mark.parametrize(
    "case", [c for c in CASES if "expected-fail" not in c.tags], ids=lambda case: case.id
)
def test_the_scripted_answer_passes_every_non_judge_assertion(
    case: LLMCase, scripted_answer: Answers
) -> None:
    results = evaluate_case(case, scripted_answer(case))
    failures = [result for result in non_judge(case, results) if not result.passed]
    assert failures == [], [f"{result.assertion_type}: {result.detail}" for result in failures]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_every_judge_assertion_is_unenforceable_without_a_judge_provider(
    case: LLMCase, scripted_answer: Answers
) -> None:
    results = evaluate_case(case, scripted_answer(case), judge_provider=None)
    for assertion, result in zip(case.assertions, results, strict=True):
        if assertion.type == "judge":
            assert result.unenforceable and not result.passed


def test_the_expected_fail_case_fails_both_of_its_substring_assertions_readably(
    scripted_answer: Answers,
) -> None:
    """Spec §4: this case exists so the README can show what a failure report looks like."""
    case = next(c for c in CASES if "expected-fail" in c.tags)
    assert scripted_answer(case) == "I don't know."
    contains, not_contains, judge = evaluate_case(case, "I don't know.")

    assert not contains.passed
    assert contains.score == 0.0
    assert contains.detail == (
        "none of 'psychotherapy', 'SSRI' appear; matched 0/2 substrings, case-insensitive"
    )

    assert not not_contains.passed
    assert not_contains.score == 0.0
    assert 'forbidden "I don\'t know" appears' in not_contains.detail

    assert judge.unenforceable


def test_a_judge_provider_does_not_change_a_non_judge_result(scripted_answer: Answers) -> None:
    case = next(c for c in CASES if c.id == "t2d-metformin")
    without = evaluate_case(case, scripted_answer(case))
    with_judge = evaluate_case(case, scripted_answer(case), judge_provider=FakeProvider())
    assert non_judge(case, without) == non_judge(case, with_judge)


# --- base_dir ----------------------------------------------------------------------------------


def test_base_dir_reaches_the_schema_file_of_a_schema_valid_assertion(
    tmp_path: Path, monkeypatch: Any
) -> None:
    (tmp_path / "screening.json").write_text('{"type": "object"}', encoding="utf-8")
    case = LLMCase.model_validate(
        {
            "id": "with-schema-file",
            "input": "q?",
            "assertions": [{"type": "schema_valid", "schema_file": "screening.json"}],
        }
    )
    monkeypatch.chdir(REPO_ROOT)
    assert not evaluate_case(case, "{}")[0].passed
    assert evaluate_case(case, "{}", base_dir=tmp_path)[0].passed


# --- the demo suite: the judge -----------------------------------------------------------------


def judge_results(case: LLMCase, results: list[AssertionResult]) -> list[AssertionResult]:
    return [
        result
        for assertion, result in zip(case.assertions, results, strict=True)
        if assertion.type == "judge"
    ]


def validated_dir(tmp_path: Path) -> Path:
    """Write a validation record for the demo suite's rubric as it stands on disk."""
    rubric = resolve_rubric("faithfulness", rubric_dirs=[DEMO_RUBRICS])
    write_validation_record(
        ValidationRecord(
            rubric=rubric.name,
            rubric_hash=rubric.content_hash,
            n=40,
            agreement=0.8,
            kappa=0.592,
            labels_file="tests/fixtures/consilium/judge-sample-2-labeled.csv",
            labels_hash="54c3af834595d71c",
            method="columns",
            created="2026-09-03T18:00:00Z",
        ),
        validation_dir=tmp_path,
    )
    return tmp_path


@pytest.mark.parametrize(
    "case", [c for c in JUDGED if "expected-fail" not in c.tags], ids=lambda case: case.id
)
def test_the_demos_fake_judge_passes_every_scripted_answer(
    case: LLMCase,
    tmp_path: Path,
    scripted_answer: Answers,
    fake_judge: Callable[[str], str],
) -> None:
    """The demo's judge grades the fallback ``FAKE(...)`` answer and nothing else as unfaithful."""
    results = evaluate_case(
        case,
        scripted_answer(case),
        judge_provider=FakeProvider(default=fake_judge),
        rubric_dirs=[REPO_ROOT / "rubrics", DEMO_RUBRICS],
        validation_dir=validated_dir(tmp_path),
    )
    verdicts = judge_results(case, results)
    assert verdicts
    for verdict in verdicts:
        assert verdict.passed, verdict.detail
        assert not verdict.unenforceable


def test_the_rubric_is_found_beside_the_tests_and_not_only_under_rootdir(
    tmp_path: Path, scripted_answer: Answers, fake_judge: Callable[[str], str]
) -> None:
    """Spec §3.5 names rootdir; the demo suite keeps its rubric below it (DECISIONS 23)."""
    case = next(case for case in JUDGED if case.id == "htn-definition")
    provider = FakeProvider(default=fake_judge)
    rootdir_only = evaluate_case(
        case, scripted_answer(case), judge_provider=provider, rubric_dirs=[REPO_ROOT / "rubrics"]
    )
    with_suite_dir = evaluate_case(
        case,
        scripted_answer(case),
        judge_provider=provider,
        rubric_dirs=[REPO_ROOT / "rubrics", DEMO_RUBRICS],
        validation_dir=validated_dir(tmp_path),
    )
    assert not judge_results(case, rootdir_only)[0].passed
    assert judge_results(case, with_suite_dir)[0].passed


def test_a_graded_judge_with_no_validation_record_is_unenforceable_but_still_counts(
    tmp_path: Path, scripted_answer: Answers, fake_judge: Callable[[str], str]
) -> None:
    case = next(case for case in JUDGED if case.id == "htn-definition")
    verdict = judge_results(
        case,
        evaluate_case(
            case,
            scripted_answer(case),
            judge_provider=FakeProvider(default=fake_judge),
            rubric_dirs=[DEMO_RUBRICS],
            validation_dir=tmp_path / "no-records-here",
        ),
    )[0]
    assert verdict.passed
    assert verdict.unenforceable
    assert "probatio validate-judge" in verdict.detail
