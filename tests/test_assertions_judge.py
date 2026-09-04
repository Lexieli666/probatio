"""Phase 3: the ``judge`` assertion, which is unenforceable until a provider is configured."""

from __future__ import annotations

from typing import Any

from probatio import FakeProvider, LLMCase
from probatio.assertions import evaluate_judge
from probatio.case import JudgeAssertion

CASE = LLMCase.model_validate(
    {
        "id": "htn-definition",
        "input": {"question": "q?"},
        "assertions": [{"type": "judge", "rubric": "faithfulness"}],
    }
)


def judge(**fields: Any) -> JudgeAssertion:
    return JudgeAssertion.model_validate({"type": "judge", "rubric": "faithfulness", **fields})


def test_a_judge_with_no_provider_is_unenforceable_and_names_the_rubric() -> None:
    result = evaluate_judge(judge(), CASE, "any output")
    assert result.assertion_type == "judge"
    assert result.unenforceable
    assert result.detail == "no judge provider configured for rubric 'faithfulness'"


def test_an_unenforceable_judge_never_passes() -> None:
    """Spec §3.7: a check that could not be carried out is not a pass and has no score."""
    result = evaluate_judge(judge(), CASE, "an answer that is entirely faithful")
    assert result.passed is False
    assert result.score is None


def test_the_rubric_name_in_the_detail_follows_the_assertion() -> None:
    result = evaluate_judge(judge(rubric="safety"), CASE, "any output")
    assert result.detail == "no judge provider configured for rubric 'safety'"


def test_phase_3_reports_unenforceable_even_when_a_provider_is_passed() -> None:
    """The grading arrives in Phase 4; until then no judge assertion may report a verdict."""
    result = evaluate_judge(judge(), CASE, "any output", judge_provider=FakeProvider())
    assert result.unenforceable
    assert not result.passed
