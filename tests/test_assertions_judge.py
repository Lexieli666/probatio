"""Phase 4: the ``judge`` assertion — graded, unvalidated, unenforceable, or a mistake.

Phase 3's stub reported every judge assertion unenforceable even when a provider was passed; the
test that pinned that behaviour is deleted here, because grading is what Phase 4 adds. The
unenforceable branch for ``judge_provider is None`` is kept, and so is its test.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from probatio import FakeProvider, LLMCase
from probatio.assertions import evaluate_judge
from probatio.case import JudgeAssertion
from probatio.judge import ValidationRecord, resolve_rubric, write_validation_record

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_RUBRICS = REPO_ROOT / "examples" / "demo_suite" / "rubrics"

CASE = LLMCase.model_validate(
    {
        "id": "htn-definition",
        "input": {"question": "q?", "documents": ["a document"]},
        "assertions": [{"type": "judge", "rubric": "faithfulness"}],
    }
)


def judge(**fields: Any) -> JudgeAssertion:
    return JudgeAssertion.model_validate({"type": "judge", "rubric": "faithfulness", **fields})


def graded(
    reply: str | Any,
    *,
    assertion: JudgeAssertion | None = None,
    validation_dir: Path | None = None,
) -> Any:
    """Grade one output with a fake judge that always answers ``reply``."""
    return evaluate_judge(
        assertion or judge(),
        CASE,
        "an answer",
        judge_provider=FakeProvider(default=reply),
        rubric_dirs=[DEMO_RUBRICS],
        validation_dir=validation_dir or Path("/nonexistent-validation-dir"),
    )


def validated(tmp_path: Path) -> Path:
    """Write a validation record for the demo rubric's current text, and return its directory."""
    rubric = resolve_rubric("faithfulness", rubric_dirs=[DEMO_RUBRICS])
    write_validation_record(
        ValidationRecord(
            rubric=rubric.name,
            rubric_hash=rubric.content_hash,
            n=40,
            agreement=0.8,
            kappa=0.592,
            labels_file="judge-sample-2-labeled.csv",
            labels_hash="54c3af834595d71c",
            method="columns",
            created="2026-09-03T18:00:00Z",
        ),
        validation_dir=tmp_path,
    )
    return tmp_path


# --- no provider: the Phase 3 branch, kept ------------------------------------------------------


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


# --- grading ------------------------------------------------------------------------------------


def test_the_demo_suites_pass_verdict_is_a_passing_result(tmp_path: Path, judge_pass: str) -> None:
    result = graded(judge_pass, validation_dir=validated(tmp_path))
    assert result.passed
    assert result.score == 1.0
    assert result.detail == (
        "judge 'faithfulness' returned pass with score 1.00 (threshold 1.00): "
        "Every claim is in the documents."
    )


def test_the_demo_suites_fail_verdict_is_a_failing_result(tmp_path: Path, judge_fail: str) -> None:
    result = graded(judge_fail, validation_dir=validated(tmp_path))
    assert not result.passed
    assert result.score == 0.0
    assert "returned fail with score 0.00" in result.detail
    assert "The output is not an answer." in result.detail


def test_a_verdict_below_the_threshold_fails_even_when_the_judge_says_pass(
    tmp_path: Path,
) -> None:
    reply = '{"verdict": "pass", "score": 0.7, "rationale": "mostly grounded"}'
    assert not graded(reply, validation_dir=validated(tmp_path)).passed
    lenient = judge(threshold=0.5)
    assert graded(reply, assertion=lenient, validation_dir=validated(tmp_path)).passed


def test_the_judge_grades_the_output_it_was_given(fake_judge: Callable[[str], str]) -> None:
    provider = FakeProvider(default=fake_judge)
    faithful = evaluate_judge(
        judge(), CASE, "a grounded answer", judge_provider=provider, rubric_dirs=[DEMO_RUBRICS]
    )
    unfaithful = evaluate_judge(
        judge(), CASE, "FAKE(0011223344)", judge_provider=provider, rubric_dirs=[DEMO_RUBRICS]
    )
    assert faithful.passed
    assert not unfaithful.passed


# --- the unvalidated-judge warning --------------------------------------------------------------


def test_a_graded_judge_with_no_validation_record_is_unenforceable_and_names_the_command(
    judge_pass: str,
) -> None:
    result = graded(judge_pass)
    assert result.unenforceable
    assert "has not been validated against human labels" in result.detail
    assert "run: probatio validate-judge --rubric faithfulness" in result.detail


def test_an_unvalidated_verdict_still_counts_toward_pass_and_fail(
    judge_pass: str, judge_fail: str
) -> None:
    """Spec §3.5, and deliberately unlike the budget rule: the verdict is the only evidence."""
    assert graded(judge_pass).passed is True
    assert graded(judge_fail).passed is False


def test_a_validation_record_for_the_current_rubric_makes_the_result_enforceable(
    tmp_path: Path, judge_pass: str
) -> None:
    result = graded(judge_pass, validation_dir=validated(tmp_path))
    assert not result.unenforceable
    assert "has not been validated" not in result.detail


def test_editing_the_rubric_makes_the_same_grade_unenforceable_again(
    tmp_path: Path, judge_pass: str
) -> None:
    rubrics = tmp_path / "rubrics"
    rubrics.mkdir()
    rubric_file = rubrics / "faithfulness.md"
    rubric_file.write_text("Grade faithfulness to the documents.", encoding="utf-8")
    records = tmp_path / "judges"

    rubric = resolve_rubric("faithfulness", rubric_dirs=[rubrics])
    write_validation_record(
        ValidationRecord(
            rubric="faithfulness",
            rubric_hash=rubric.content_hash,
            n=40,
            agreement=0.8,
            kappa=0.592,
            labels_file="labels.csv",
            labels_hash="0000000000000000",
            method="columns",
            created="2026-09-03T18:00:00Z",
        ),
        validation_dir=records,
    )

    def grade() -> Any:
        return evaluate_judge(
            judge(),
            CASE,
            "an answer",
            judge_provider=FakeProvider(default=judge_pass),
            rubric_dirs=[rubrics],
            validation_dir=records,
        )

    assert not grade().unenforceable
    rubric_file.write_text("Grade faithfulness, and also tone.", encoding="utf-8")
    after = grade()
    assert after.unenforceable
    assert after.passed


# --- tolerated deviations (DECISIONS 29) --------------------------------------------------------


def test_a_verdict_with_no_rationale_grades_and_leaves_no_dangling_colon(tmp_path: Path) -> None:
    result = graded('{"verdict": "pass", "score": 1.0}', validation_dir=validated(tmp_path))
    assert result.passed
    assert result.detail == ("judge 'faithfulness' returned pass with score 1.00 (threshold 1.00)")


def test_an_extra_key_in_the_verdict_does_not_fail_the_assertion(tmp_path: Path) -> None:
    """A format deviation counted as a fail grade would measure formatting, not judging."""
    result = graded(
        '{"verdict": "fail", "score": 0.0, "rationale": "unsupported claim", "confidence": 0.4}',
        validation_dir=validated(tmp_path),
    )
    assert not result.passed
    assert result.score == 0.0
    assert result.detail.endswith(": unsupported claim")


# --- mistakes are results, not exceptions (DECISIONS 22) ----------------------------------------


def test_a_rubric_that_resolves_nowhere_is_a_failed_result_naming_the_directories(
    tmp_path: Path, judge_pass: str
) -> None:
    first = tmp_path / "one"
    second = tmp_path / "two"
    result = evaluate_judge(
        judge(rubric="missing"),
        CASE,
        "an answer",
        judge_provider=FakeProvider(default=judge_pass),
        rubric_dirs=[first, second],
    )
    assert not result.passed
    assert result.score is None
    assert str(first) in result.detail
    assert str(second) in result.detail
    assert "missing.md" in result.detail


@pytest.mark.parametrize(
    "reply",
    [
        "The answer looks faithful to me.",
        "```\nnot json\n```",
        '{"verdict": "maybe", "score": 1.0, "rationale": "r"}',
    ],
)
def test_a_reply_that_is_not_the_strict_verdict_is_a_failed_result_not_an_exception(
    reply: str,
) -> None:
    result = graded(reply)
    assert not result.passed
    assert result.score is None
    assert result.detail.startswith("judge output was not valid JSON: ")


def test_an_unparsable_reply_is_not_reported_as_unvalidated_noise() -> None:
    """The detail says the one thing that is wrong: the judge did not answer the question."""
    result = graded("prose")
    assert "has not been validated" not in result.detail
