"""Phase 3: ``evaluate_case`` over the demo suite, which is the specification."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from probatio import AssertionResult, FakeProvider, LLMCase, load_cases
from probatio.runner import evaluate_case

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO = REPO_ROOT / "examples" / "demo_suite"


def _load_demo_conftest() -> ModuleType:
    """Import the frozen demo ``conftest.py`` as a plain module, for its scripted responses.

    The demo suite is the design specification, so the scripted answers it commits are the
    outputs ``evaluate_case`` has to be right about. Reading them from the file rather than
    copying them here means a change to either side shows up as a failure.
    """
    spec = importlib.util.spec_from_file_location("demo_conftest", DEMO / "conftest.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["demo_conftest"] = module
    spec.loader.exec_module(module)
    return module


DEMO_CONFTEST = _load_demo_conftest()
CASES = load_cases(DEMO / "cases")


def scripted_output(case: LLMCase) -> str:
    """The answer the demo's fake provider gives for a case: by keyword, or the flaky script."""
    keyword = case.metadata.get("keyword")
    if keyword is None:
        return str(DEMO_CONFTEST.FLU_ANSWER)
    return str(DEMO_CONFTEST.RESPONSES[keyword])


def non_judge(case: LLMCase, results: list[AssertionResult]) -> list[AssertionResult]:
    return [
        result
        for assertion, result in zip(case.assertions, results, strict=True)
        if assertion.type != "judge"
    ]


# --- shape -------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_one_result_per_assertion_in_declaration_order(case: LLMCase) -> None:
    results = evaluate_case(case, scripted_output(case))
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
def test_the_scripted_answer_passes_every_non_judge_assertion(case: LLMCase) -> None:
    results = evaluate_case(case, scripted_output(case))
    failures = [result for result in non_judge(case, results) if not result.passed]
    assert failures == [], [f"{result.assertion_type}: {result.detail}" for result in failures]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_every_judge_assertion_is_unenforceable_without_a_judge_provider(case: LLMCase) -> None:
    results = evaluate_case(case, scripted_output(case), judge_provider=None)
    for assertion, result in zip(case.assertions, results, strict=True):
        if assertion.type == "judge":
            assert result.unenforceable and not result.passed


def test_the_expected_fail_case_fails_both_of_its_substring_assertions_readably() -> None:
    """Spec §4: this case exists so the README can show what a failure report looks like."""
    case = next(c for c in CASES if "expected-fail" in c.tags)
    assert scripted_output(case) == "I don't know."
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


def test_a_judge_provider_does_not_change_a_non_judge_result() -> None:
    case = next(c for c in CASES if c.id == "t2d-metformin")
    without = evaluate_case(case, scripted_output(case))
    with_judge = evaluate_case(case, scripted_output(case), judge_provider=FakeProvider())
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
