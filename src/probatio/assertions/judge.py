"""The ``judge`` assertion. Phase 3 ships the unenforceable half of it; Phase 4 ships the judge.

A judge assertion with nowhere to send the rubric is not a pass and is not a failure of the
application: it is a check that did not happen. Spec §3.7's unenforceable rule exists for exactly
this, and it applies here permanently, not only as a phase-3 placeholder — a suite run with no
judge provider configured must never report its judge assertions as green.

Phase 4 replaces the body with a call to ``probatio.judge.Judge``, keeping this signature and
keeping this branch for the ``judge_provider is None`` case.
"""

from __future__ import annotations

from ..case import JudgeAssertion, LLMCase
from ..providers import Provider
from .result import AssertionResult

__all__ = ["evaluate_judge"]


def evaluate_judge(
    assertion: JudgeAssertion,
    case: LLMCase,
    output: str,
    *,
    judge_provider: Provider | None = None,
) -> AssertionResult:
    """Grade the output against the assertion's rubric.

    Args:
        assertion: The declaration, holding ``rubric``, ``threshold`` and ``provider``.
        case: The case the output answers; Phase 4's judge prompt includes its input.
        output: The text under test; Phase 4 sends it to the judge.
        judge_provider: The provider to grade with. ``None`` means no judge is configured, which
            is what this phase always reports.

    Returns:
        An unenforceable failing result naming the rubric. Phase 4 returns a graded result when a
        provider is configured and keeps this one when it is not.
    """
    return AssertionResult(
        assertion_type="judge",
        passed=False,
        score=None,
        detail=f"no judge provider configured for rubric {assertion.rubric!r}",
        unenforceable=True,
    )
