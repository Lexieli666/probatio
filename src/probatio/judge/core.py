"""``JudgeVerdict`` and ``Judge``: send a rubric to a provider and parse the reply strictly.

Strictly means: strip at most one wrapping code fence, ``json.loads``, then validate with
pydantic. Strict about the two fields that decide the assertion — a judge that returns prose, or
no ``score``, or a verdict of ``"PASS"``, has not answered the question the template asked, and
accepting any of those quietly is how a judge starts scoring things nobody defined. Tolerant about
the rest: a missing ``rationale`` and unknown keys are not grounds for rejecting a verdict
(DECISIONS 29). What is rejected raises :class:`~probatio.errors.JudgeOutputError`, and the
assertion layer turns that into a failed result whose detail begins ``judge output was not valid
JSON``; nothing here ever raises past that boundary in a suite run.

The grader does not know about thresholds, validation records or ``AssertionResult``. It returns
the verdict the judge gave. Deciding whether that verdict passes belongs to
:func:`probatio.assertions.evaluate_judge`, which is also where the unvalidated-judge warning is
attached, because both depend on the case's declaration rather than on the judge.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from contextlib import AbstractContextManager, nullcontext
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..assertions.schema import strip_code_fence
from ..case import LLMCase
from ..errors import JudgeOutputError
from ..providers import Completion, Provider
from .prompt import judge_template_hash, render_judge_prompt
from .rubric import Rubric

__all__ = ["Judge", "JudgeVerdict"]


def _marking_judge_calls(provider: Provider) -> AbstractContextManager[None]:
    """Ask a provider to mark the calls made inside the block as judge calls.

    Spec §3.8 puts the judge prompt template's hash in every judge cassette key, and there is no
    room for it in :meth:`~probatio.providers.Provider.complete`: the protocol has no such
    parameter, and a reserved keyword would be handed to a live adapter that knows nothing about
    cassettes. So the mark travels through the provider instead. A
    :class:`~probatio.cassette.CassetteProvider` exposes ``judge_calls``, which sets the context on
    its store for the duration; any other provider does not, and is called with exactly the
    arguments the judge passed (DECISIONS 42).

    Args:
        provider: Whatever provider the judge was constructed with.

    Returns:
        The provider's own context manager, or a do-nothing one.
    """
    marker = getattr(provider, "judge_calls", None)
    if not callable(marker):
        return nullcontext()
    context: AbstractContextManager[None] = marker(judge_template_hash())
    return context


class JudgeVerdict(BaseModel):
    """The verdict a judge returns: two load-bearing fields and one for the reader.

    ``verdict`` and ``score`` are required and strictly typed, because they are what decides the
    assertion. ``rationale`` is optional and unknown keys are dropped: a judge that omits its
    sentence, or volunteers a ``confidence`` field, has still answered the question that was
    asked, and rejecting it would turn a formatting deviation into a failing grade (DECISIONS 29).

    Attributes:
        verdict: ``"pass"`` or ``"fail"``.
        score: A number in [0, 1]; the rubric says what it means.
        rationale: One sentence naming what decided the verdict, when the judge gave one.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    verdict: Literal["pass", "fail"]
    score: float = Field(ge=0.0, le=1.0)
    rationale: str = ""

    def passes(self, threshold: float) -> bool:
        """Report whether this verdict clears a threshold.

        Args:
            threshold: The assertion's ``threshold``.

        Returns:
            ``True`` when the verdict is ``"pass"`` and the score is at least ``threshold``.
        """
        return self.verdict == "pass" and self.score >= threshold


class Judge:
    """A rubric and a provider, together able to grade one output.

    Attributes:
        rubric: The resolved rubric being applied.
        provider: The provider the prompt is sent to.
        params: Parameters forwarded to ``provider.complete``.
    """

    def __init__(
        self, rubric: Rubric, provider: Provider, *, params: Mapping[str, Any] | None = None
    ) -> None:
        """Bind a rubric to the provider that will grade against it.

        Args:
            rubric: The resolved rubric; see :func:`~probatio.judge.rubric.resolve_rubric`.
            provider: The judge provider. In a test run this is always a fake or a cassette.
            params: Parameters forwarded to every ``complete`` call, such as ``model``.
        """
        self.rubric = rubric
        self.provider = provider
        self.params: dict[str, Any] = dict(params or {})

    def prompt(self, case: LLMCase, output: str) -> str:
        """Render the prompt this judge would send for one case and output.

        Args:
            case: The case the output answers; its ``input`` goes into the prompt.
            output: The output under test.

        Returns:
            The filled judge prompt template.
        """
        return render_judge_prompt(
            rubric_text=self.rubric.text, case_input=case.input, output=output
        )

    def grade(self, case: LLMCase, output: str) -> JudgeVerdict:
        """Grade one output against the rubric.

        Args:
            case: The case the output answers.
            output: The output under test.

        Returns:
            The judge's verdict.

        Raises:
            JudgeOutputError: The judge's reply is not the strict JSON object the template asked
                for. The message begins ``judge output was not valid JSON``.
        """
        return self.grade_with_completion(case, output)[0]

    def grade_with_completion(self, case: LLMCase, output: str) -> tuple[JudgeVerdict, Completion]:
        """Grade one output and also return the completion the judge provider produced.

        ``probatio validate-judge --run-judge`` needs the model name off the completion to put it
        in the validation record, and Phase 7's cassettes need its cost and latency, so the raw
        completion is available next to the parsed verdict rather than discarded.

        Args:
            case: The case the output answers.
            output: The output under test.

        Returns:
            The verdict and the completion it was parsed from.

        Raises:
            JudgeOutputError: The judge's reply is not the strict JSON object the template asked
                for.
        """
        with _marking_judge_calls(self.provider):
            completion: Completion = self.provider.complete(
                self.prompt(case, output), **self.params
            )
        return self.parse(completion.text, case_id=case.id), completion

    def parse(self, text: str, *, case_id: str | None = None) -> JudgeVerdict:
        """Parse a judge's reply into a verdict.

        Args:
            text: The judge's raw reply. One wrapping code fence is stripped first.
            case_id: The case being graded, named in the error message.

        Returns:
            The verdict. A missing ``rationale`` and any key :class:`JudgeVerdict` does not
            declare are tolerated; ``verdict`` and ``score`` are not.

        Raises:
            JudgeOutputError: The reply is not one JSON object carrying a ``verdict`` of
                ``"pass"`` or ``"fail"`` and a ``score`` in [0, 1].
        """
        payload = strip_code_fence(text).strip()
        try:
            loaded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise self._bad(f"{exc.msg} at line {exc.lineno} column {exc.colno}", case_id) from exc
        if not isinstance(loaded, dict):
            raise self._bad(f"a JSON {type(loaded).__name__} is not a verdict object", case_id)
        try:
            return JudgeVerdict.model_validate(loaded)
        except ValidationError as exc:
            first = exc.errors()[0]
            field = ".".join(str(part) for part in first["loc"]) or "<verdict>"
            raise self._bad(f"{field}: {first['msg']}", case_id) from exc

    def _bad(self, reason: str, case_id: str | None) -> JudgeOutputError:
        """Build the one error this class raises, naming the rubric and the reason."""
        return JudgeOutputError(
            f"judge output was not valid JSON: {reason} (rubric {self.rubric.name!r})",
            case_id=case_id,
        )
