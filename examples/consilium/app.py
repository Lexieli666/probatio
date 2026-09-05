"""The system under test for the Consilium dogfood suite: one call, one answer.

There is no application here. The answers this suite checks were produced in August 2026 by
Consilium-Health's own pipeline and are read back off committed tapes; :func:`answer` exists to
make the call that finds them. That is the whole point of a cassette: a suite that replays a
recorded run needs a system under test only so that the report has something to attribute the
answer to.

Two constants are therefore contract, not description.

**SYSTEM** is Probatio's own fixed string, not the system prompt Consilium sent. The published
traces record token counts, a model name and the delivered answer; they do not record prompts, so
the real one is not available to copy and inventing a claim about it would be worse than saying
this. What the string has to be is *stable*: it is hashed into every cassette key, so the value
here and the value ``convert_traces.py`` wrote into the tapes must be the same value, and changing
it makes all thirty tapes stale at once.

**MODEL** is the model the traces name, and ``convert_traces.py`` refuses to convert a trace that
names another. It is passed explicitly on every call so that the replay key matches the imported
tape under any ``--probatio-provider``: the key's model is ``params["model"]`` when the call names
one and the adapter's own model otherwise (DECISIONS 43), so a suite that left it out would key on
whatever ``--probatio-model`` happened to say and find nothing.
"""

from __future__ import annotations

from probatio import Completion, LLMCase, Provider

SYSTEM = (
    "You are a health information assistant. Answer the question from the retrieved clinical "
    "notes. Do not invent facts that the notes do not support, and when the question describes a "
    "possible emergency, say so plainly and tell the reader to seek care now."
)
"""The system prompt every call in this suite carries; part of every cassette key."""

MODEL = "gpt-4o-mini-2024-07-18"
"""The model Consilium's published run 20260830T170133Z used for every one of these turns."""


def answer(case: LLMCase, provider: Provider, config: str) -> Completion:
    """Answer a case under one Consilium configuration.

    Args:
        case: The case; its ``input`` is the golden question as a bare string.
        provider: The cassette-wrapped provider the ``provider`` fixture built.
        config: ``"full"`` or ``"baseline_llm"``, which is what makes the two suites' keys differ
            for the same question and so what lets one set of tapes hold both recorded runs.

    Returns:
        The completion. Returning it rather than its text is what lets the case's budget ceilings
        see the call at all (DECISIONS 66).
    """
    return provider.complete(case.input, system=SYSTEM, config=config, model=MODEL)
