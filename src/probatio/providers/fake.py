"""``FakeProvider`` and ``ScriptedProvider``: the two providers the test suite is allowed to use.

Probatio's own suite, and the demo suite, never reach a model. A fake has to be predictable
enough to assert on and interesting enough to be worth asserting on, which is why lookups have
three layers: an exact key over the whole call, a prompt substring for the common case of "answer
this question with that", and a default that may be a callable so a fake judge can grade by
inspecting the prompt it was handed.

Nothing here is random and nothing here reads the clock: the same construction answers the same
prompt with the same text, cost and latency in every process, which is what lets a stability run
against a fake have a pass rate of exactly 1.0 and a cassette recorded through one be byte-stable.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

from ..errors import ProbatioConfigError
from ..hashing import stable_hash
from .base import Completion

__all__ = ["FakeCall", "FakeProvider", "ScriptedProvider"]

DEFAULT_MODEL: Final = "fake-1"
"""The model name a fake reports when the caller does not choose one."""


class FakeCall(BaseModel):
    """One call a fake provider received, recorded so a test can assert on what the SUT sent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt: str
    system: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class FakeProvider:
    """A provider that answers from a table, offline and deterministically.

    A prompt is answered by the first of these that produces something:

    1. ``responses[call_key(prompt, system, params)]`` — an exact match on the whole call, which
       is how a recorded interaction is replayed through a fake.
    2. ``responses[k]`` for the first ``k``, in insertion order, that is a substring of the
       prompt. Insertion order is the author's declared priority.
    3. ``default``, called with the prompt if it is callable.
    4. ``f"FAKE({stable_hash(prompt)})"``, a fallback that is stable, obviously synthetic, and
       different for every prompt, so a keyword table that misses shows up as a failure rather
       than as a plausible answer.

    Attributes:
        name: ``"fake"``.
        calls: Every call received, in order.
    """

    name: str = "fake"

    def __init__(
        self,
        responses: Mapping[str, str] | None = None,
        default: str | Callable[[str], str] | None = None,
        cost_usd: float | None = None,
        latency_ms: float = 0.0,
        model: str = DEFAULT_MODEL,
    ) -> None:
        """Configure the table and the fixed cost, latency and model name of every answer.

        Args:
            responses: Answers keyed by call key or by prompt substring, checked in that order.
            default: The answer when nothing matches, or a callable applied to the prompt.
            cost_usd: The cost reported for every call. ``None`` means "unknown", which makes a
                cost ceiling on this provider unenforceable, exactly as a real unpriced model
                would.
            latency_ms: The latency reported for every call.
            model: The model name reported on every completion.
        """
        self.responses: dict[str, str] = dict(responses or {})
        self.default = default
        self.cost_usd = cost_usd
        self.latency_ms = latency_ms
        self.model = model
        self.calls: list[FakeCall] = []

    @property
    def call_count(self) -> int:
        """How many calls this provider has received."""
        return len(self.calls)

    @staticmethod
    def call_key(prompt: str, system: str | None, params: Mapping[str, Any]) -> str:
        """Return the exact-match key for one call, for use as a ``responses`` key.

        Args:
            prompt: The user-turn text.
            system: The system prompt, or ``None``.
            params: The call's parameters.

        Returns:
            The :func:`~probatio.hashing.stable_hash` of the whole call.
        """
        return stable_hash({"prompt": prompt, "params": dict(params), "system": system})

    def complete(self, prompt: str, *, system: str | None = None, **params: Any) -> Completion:
        """Answer a prompt from the table and record the call.

        Args:
            prompt: The user-turn text.
            system: The system prompt, when the case declares one.
            **params: The case's parameters; recorded, and part of the exact-match key.

        Returns:
            The completion, with this provider's fixed cost, latency and model name.
        """
        self.calls.append(FakeCall(prompt=prompt, system=system, params=dict(params)))
        text, source = self._respond(prompt, system, params)
        return Completion(
            text=text,
            model=self.model,
            cost_usd=self.cost_usd,
            latency_ms=self.latency_ms,
            raw={"provider": self.name, "matched": source},
        )

    def _respond(
        self, prompt: str, system: str | None, params: Mapping[str, Any]
    ) -> tuple[str, str]:
        """Resolve a prompt to its answer and the name of the layer that produced it."""
        key = self.call_key(prompt, system, params)
        if key in self.responses:
            return self.responses[key], "call_key"
        for needle, answer in self.responses.items():
            if needle in prompt:
                return answer, "substring"
        if callable(self.default):
            return self.default(prompt), "default"
        if self.default is not None:
            return self.default, "default"
        return f"FAKE({stable_hash(prompt)})", "fallback"


class ScriptedProvider(FakeProvider):
    """A fake that reads a fixed sequence of answers in order, cycling when it runs out.

    This is how a flaky model is modelled offline: a script whose first entry fails a case's
    assertions and whose remaining four pass gives a pass rate of exactly 0.8 under ``--runs 5``,
    with no randomness anywhere.

    Attributes:
        name: ``"scripted"``.
        script: The answers, in order.
    """

    name: str = "scripted"

    def __init__(
        self,
        script: Sequence[str],
        cost_usd: float | None = None,
        latency_ms: float = 0.0,
        model: str = DEFAULT_MODEL,
    ) -> None:
        """Configure the sequence and the fixed cost, latency and model name of every answer.

        Args:
            script: The answers, in the order they are returned. Cycles once exhausted.
            cost_usd: The cost reported for every call.
            latency_ms: The latency reported for every call.
            model: The model name reported on every completion.

        Raises:
            ProbatioConfigError: The script is empty, so there is nothing to return.
        """
        super().__init__(None, None, cost_usd, latency_ms, model)
        if not script:
            raise ProbatioConfigError("a ScriptedProvider needs at least one scripted answer")
        self.script: list[str] = list(script)

    def _respond(
        self, prompt: str, system: str | None, params: Mapping[str, Any]
    ) -> tuple[str, str]:
        """Return the answer for this call's position in the script."""
        return self.script[(self.call_count - 1) % len(self.script)], "script"
