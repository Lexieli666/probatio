"""Phase 4: ``Judge.grade`` and strict verdict parsing, against the demo suite's fake judge."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from probatio import FakeProvider, JudgeOutputError, LLMCase
from probatio.judge import Judge, JudgeVerdict, resolve_rubric

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_RUBRICS = REPO_ROOT / "examples" / "demo_suite" / "rubrics"
RUBRIC = resolve_rubric("faithfulness", rubric_dirs=[DEMO_RUBRICS])

CASE = LLMCase.model_validate(
    {
        "id": "copd-spirometry",
        "input": {"question": "What confirms COPD?", "documents": ["Spirometry does."]},
        "assertions": [{"type": "judge", "rubric": "faithfulness"}],
    }
)


def judge_with(reply: str | Any) -> tuple[Judge, FakeProvider]:
    provider = FakeProvider(default=reply)
    return Judge(RUBRIC, provider), provider


# --- the demo suite's two verdicts ------------------------------------------------------------


def test_the_demo_suites_pass_verdict_parses_to_a_passing_verdict(judge_pass: str) -> None:
    judge, _ = judge_with(judge_pass)
    verdict = judge.grade(CASE, "Spirometry showing persistent airflow limitation confirms COPD.")
    assert verdict.verdict == "pass"
    assert verdict.score == 1.0
    assert verdict.rationale == "Every claim is in the documents."
    assert verdict.passes(1.0)


def test_the_demo_suites_fail_verdict_parses_to_a_failing_verdict(judge_fail: str) -> None:
    judge, _ = judge_with(judge_fail)
    verdict = judge.grade(CASE, "FAKE(0000)")
    assert verdict.verdict == "fail"
    assert verdict.score == 0.0
    assert not verdict.passes(0.0)


def test_the_demo_suites_fake_judge_grades_by_looking_at_the_prompt(
    fake_judge: Callable[[str], str],
) -> None:
    """Its rule is that the keyword-miss fallback is the only unfaithful output."""
    judge, _ = judge_with(fake_judge)
    assert judge.grade(CASE, "Spirometry confirms COPD.").verdict == "pass"
    assert judge.grade(CASE, "FAKE(deadbeef)").verdict == "fail"


# --- the threshold ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("verdict", "score", "threshold", "expected"),
    [
        ("pass", 1.0, 1.0, True),
        ("pass", 0.8, 1.0, False),
        ("pass", 0.8, 0.8, True),
        ("fail", 1.0, 0.0, False),
        ("fail", 0.0, 0.0, False),
    ],
)
def test_a_verdict_passes_only_when_it_says_pass_and_clears_the_threshold(
    verdict: str, score: float, threshold: float, expected: bool
) -> None:
    assert JudgeVerdict(verdict=verdict, score=score, rationale="r").passes(threshold) is expected


# --- what the judge sends -----------------------------------------------------------------------


def test_grade_sends_the_rendered_prompt_once(judge_pass: str) -> None:
    judge, provider = judge_with(judge_pass)
    judge.grade(CASE, "an answer")
    assert provider.call_count == 1
    prompt = provider.calls[0].prompt
    assert prompt == judge.prompt(CASE, "an answer")
    assert "What confirms COPD?" in prompt
    assert "an answer" in prompt


def test_params_are_forwarded_to_the_judge_provider(judge_pass: str) -> None:
    provider = FakeProvider(default=judge_pass)
    Judge(RUBRIC, provider, params={"model": "claude-x", "temperature": 0}).grade(CASE, "a")
    assert provider.calls[0].params == {"model": "claude-x", "temperature": 0}


def test_grade_with_completion_hands_back_the_model_that_graded(judge_pass: str) -> None:
    provider = FakeProvider(default=judge_pass, model="fake-judge-1")
    verdict, completion = Judge(RUBRIC, provider).grade_with_completion(CASE, "a")
    assert verdict.verdict == "pass"
    assert completion.model == "fake-judge-1"


# --- strict parsing -----------------------------------------------------------------------------


def test_one_wrapping_code_fence_is_stripped() -> None:
    judge, _ = judge_with('```json\n{"verdict": "pass", "score": 1.0, "rationale": "ok"}\n```')
    assert judge.grade(CASE, "a").verdict == "pass"


@pytest.mark.parametrize(
    "reply",
    [
        "The answer looks faithful to me.",
        "",
        '{"verdict": "pass", "score": 1.0, "rationale": "ok"',
        '[{"verdict": "pass", "score": 1.0, "rationale": "ok"}]',
        '"pass"',
        '{"verdict": "PASS", "score": 1.0, "rationale": "ok"}',
        '{"score": 1.0, "rationale": "ok"}',
        '{"verdict": "pass", "rationale": "ok"}',
        '{"verdict": "pass", "score": 1.4, "rationale": "ok"}',
        '{"verdict": "pass", "score": -0.1, "rationale": "ok"}',
        '{"verdict": "pass", "score": "high", "rationale": "ok"}',
    ],
)
def test_anything_that_is_not_the_strict_verdict_object_raises_judge_output_error(
    reply: str,
) -> None:
    judge, _ = judge_with(reply)
    with pytest.raises(JudgeOutputError) as excinfo:
        judge.grade(CASE, "a")
    assert excinfo.value.message.startswith("judge output was not valid JSON: ")
    assert excinfo.value.case_id == "copd-spirometry"
    assert "faithfulness" in excinfo.value.message


def test_the_fallback_answer_of_an_unconfigured_fake_is_not_a_verdict() -> None:
    """``FAKE(...)`` is deliberately not parseable: a fake judge nobody wired up must not pass."""
    with pytest.raises(JudgeOutputError):
        Judge(RUBRIC, FakeProvider()).grade(CASE, "a")


def test_the_rubric_a_judge_applies_is_the_one_it_was_built_with(
    tmp_path: Path, judge_pass: str
) -> None:
    (tmp_path / "safety.md").write_text("Grade safety only.", encoding="utf-8")
    rubric = resolve_rubric("safety", rubric_dirs=[tmp_path])
    provider = FakeProvider(default=judge_pass)
    Judge(rubric, provider).grade(CASE, "a")
    assert "Grade safety only." in provider.calls[0].prompt


# --- tolerated deviations (DECISIONS 29) --------------------------------------------------------


def test_a_verdict_without_a_rationale_grades_normally() -> None:
    """``verdict`` and ``score`` are what decide the assertion; the sentence is for the reader."""
    judge, _ = judge_with('{"verdict": "pass", "score": 1.0}')
    verdict = judge.grade(CASE, "an answer")
    assert verdict.verdict == "pass"
    assert verdict.score == 1.0
    assert verdict.rationale == ""
    assert verdict.passes(1.0)


def test_an_unknown_key_in_the_verdict_is_dropped_rather_than_rejected() -> None:
    """A judge volunteering a field it was not asked for has still answered the question."""
    judge, _ = judge_with(
        '{"verdict": "fail", "score": 0.25, "rationale": "one claim is unsupported", '
        '"confidence": 0.9, "citations": ["doc-1"]}'
    )
    verdict = judge.grade(CASE, "an answer")
    assert verdict.verdict == "fail"
    assert verdict.score == 0.25
    assert verdict.rationale == "one claim is unsupported"
    assert not hasattr(verdict, "confidence")


def test_both_deviations_at_once_still_grade() -> None:
    judge, _ = judge_with('{"verdict": "pass", "score": 1.0, "notes": "none"}')
    assert judge.grade(CASE, "an answer").passes(1.0)
