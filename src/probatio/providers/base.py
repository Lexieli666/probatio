"""The provider contract: one ``Completion`` type and one ``complete`` method.

Everything that talks to a model in Probatio goes through :class:`Provider`, which is a
:class:`typing.Protocol` rather than a base class, so a user's own adapter needs no import from
Probatio to satisfy it. ``prompt`` is the user-turn text and nothing else; multi-turn is out of
scope for v0.1, and a system under test that keeps a history flattens it into the prompt.

:class:`Completion` is deliberately blunt about what it does not know. ``cost_usd`` is ``None``
when nobody priced the call, never ``0.0`` as a stand-in, because a zero that means "unknown" is
what turns a cost ceiling into a check that always passes.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["Completion", "Provider"]


class Completion(BaseModel):
    """One model response, plus what it cost and how long it took.

    Attributes:
        text: The response text.
        model: The model that produced it, as the provider reports or was asked for it.
        tokens_in: Prompt tokens, or ``None`` when the provider does not report them.
        tokens_out: Completion tokens, or ``None`` when the provider does not report them.
        cost_usd: Cost in US dollars, or ``None`` when the call was not priced.
        latency_ms: Wall-clock duration of the call in milliseconds.
        raw: The provider's own payload, carried for the record and never inspected by Probatio.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    model: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    latency_ms: float = 0.0
    raw: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class Provider(Protocol):
    """Anything that can turn a prompt into a :class:`Completion`.

    Attributes:
        name: A short, stable identifier written into cassettes, such as ``claude-cli``.
    """

    name: str

    def complete(self, prompt: str, *, system: str | None = None, **params: Any) -> Completion:
        """Complete one user-turn prompt.

        Args:
            prompt: The user-turn text.
            system: The system prompt, when the case declares one.
            **params: The case's ``params``, such as ``model`` or ``temperature``. An adapter
                that cannot honour a parameter says so in its docstring rather than pretending.

        Returns:
            The completion.
        """
        ...
