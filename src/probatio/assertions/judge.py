"""The ``judge`` assertion: grade an output against a rubric, and say how much that is worth.

Three outcomes are not two. A judge with no provider configured is unenforceable and never a pass
(spec §3.7's rule, applied here permanently). A judge that graded, but whose rubric has no
validation record for its current text, *is* a verdict — it counts toward the case's pass or fail,
because a verdict from an unmeasured judge is still the only evidence about the answer's
faithfulness that exists — and it is *also* marked unenforceable, so the summary can say how many
of the run's judge verdicts came from judges nobody has measured. That is spec §3.5, and it is
deliberately weaker than the budget rule: an unpriced cost ceiling cannot fail a build, whereas an
unvalidated judge can, and should, while it also nags.

Everything that can go wrong here is a result, not an exception (DECISIONS 22): a rubric that
resolves nowhere names the directories searched, and a judge that answers with prose produces a
detail beginning ``judge output was not valid JSON``.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ..case import JudgeAssertion, LLMCase
from ..errors import JudgeOutputError, ProbatioConfigError
from ..judge import Judge, resolve_rubric, rubric_is_validated
from ..providers import Provider
from .result import AssertionResult

__all__ = ["evaluate_judge", "validate_judge_command"]


def validate_judge_command(rubric: str) -> str:
    """Return the ``probatio validate-judge`` command that would validate a rubric.

    Args:
        rubric: The rubric name, as the case declares it.

    Returns:
        A runnable command with the two columns of a labelled sample left as placeholders, so a
        developer reading a warning can see the shape of the fix without looking it up.
    """
    return (
        f"probatio validate-judge --rubric {rubric} --labels LABELS.csv "
        "--human-column human_label --judge-column judge_label"
    )


def _failed(detail: str) -> AssertionResult:
    """Build the failed, scoreless result every mistake in a judge assertion produces."""
    return AssertionResult(assertion_type="judge", passed=False, score=None, detail=detail)


def evaluate_judge(
    assertion: JudgeAssertion,
    case: LLMCase,
    output: str,
    *,
    judge_provider: Provider | None = None,
    rubric_dirs: Sequence[Path] | None = None,
    validation_dir: Path | None = None,
) -> AssertionResult:
    """Grade the output against the assertion's rubric.

    Args:
        assertion: The declaration, holding ``rubric``, ``threshold`` and ``provider``. The
            ``provider`` name is honoured by the plugin, which chooses the provider it names;
            this function grades with whatever it is handed.
        case: The case the output answers; its ``input`` goes into the judge prompt.
        output: The text under test.
        judge_provider: The provider to grade with. ``None`` means no judge is configured, which
            is reported as unenforceable rather than as a pass.
        rubric_dirs: Directories a rubric name is searched in, in order. Defaults to
            ``[Path.cwd() / "rubrics"]``; Phase 9's plugin passes rootdir first and the
            requesting test module's directory second (DECISIONS 23).
        validation_dir: Where validation records live. Defaults to
            ``Path.cwd() / ".probatio" / "judges"``.

    Returns:
        An unenforceable failing result when no provider is configured; a failed result when the
        rubric does not resolve or the judge's reply is not the strict JSON verdict; otherwise the
        graded result, marked unenforceable when the rubric has no validation record for its
        current text.
    """
    if judge_provider is None:
        return AssertionResult(
            assertion_type="judge",
            passed=False,
            score=None,
            detail=f"no judge provider configured for rubric {assertion.rubric!r}",
            unenforceable=True,
        )

    try:
        rubric = resolve_rubric(assertion.rubric, rubric_dirs=rubric_dirs)
    except ProbatioConfigError as exc:
        return _failed(exc.message)

    judge = Judge(rubric, judge_provider)
    try:
        verdict = judge.grade(case, output)
    except JudgeOutputError as exc:
        return _failed(exc.message)

    passed = verdict.passes(assertion.threshold)
    detail = (
        f"judge {rubric.name!r} returned {verdict.verdict} with score {verdict.score:.2f} "
        f"(threshold {assertion.threshold:.2f})"
    )
    if verdict.rationale:
        detail += f": {verdict.rationale}"
    validated = rubric_is_validated(rubric, validation_dir=validation_dir)
    if not validated:
        detail += (
            f"; judge {rubric.name!r} has not been validated against human labels "
            f"(run: {validate_judge_command(assertion.rubric)})"
        )
    return AssertionResult(
        assertion_type="judge",
        passed=passed,
        score=verdict.score,
        detail=detail,
        unenforceable=not validated,
    )
