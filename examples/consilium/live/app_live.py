"""The system under test for the live Consilium suite: one grounded call, one answer.

This is a **single-call grounded question-answering app**. It is *not* Consilium-Health's pipeline
and it does not imitate it: Consilium routes a question through a planner and one or more agents,
retrieves from a vector store, and post-processes the draft through a safety repair step, and none
of that happens here. :func:`answer` renders the documents the case already carries into one
prompt and makes one provider call.

It exists so that the metamorphic relations and the judge have a real model to fire against.
``examples/consilium/app.py``, beside it, is the offline suite's system under test and replays
Consilium's own recorded answers; the two suites answer different questions about different
systems and the live one must never be read as a measurement of Consilium.

The documents are the corpus notes the golden item's ``relevant_doc_ids`` name, copied verbatim
into each case's ``input.documents`` by ``convert_traces.py --emit-live-cases``, so the retrieval
step is not modelled either: this app is given the notes a perfect retriever would have found.
"""

from __future__ import annotations

from typing import Any

from probatio import Completion, LLMCase, Provider


def build_prompt(case: LLMCase) -> str:
    """Render a case's input as the user-turn prompt: numbered documents, then the question.

    Args:
        case: The case; its ``input`` is a mapping with ``question`` and ``documents``.

    Returns:
        The prompt. Documents are numbered from 1 so that the rubric's "SOURCES: numbered
        excerpts" and a judge verdict citing source *n* mean the same thing to a human reading the
        report as they do to the judge.

    Raises:
        KeyError: The case's input has no ``question``. A live case that reached this point
            without one is a broken case file, not a model failure, and it should stop the run.
    """
    documents: Any = case.input["documents"] if isinstance(case.input, dict) else []
    numbered = "\n\n".join(f"[{i}] {doc}" for i, doc in enumerate(documents, start=1))
    question = case.input["question"] if isinstance(case.input, dict) else case.input
    return f"Documents:\n{numbered}\n\nQuestion: {question}"


def answer(case: LLMCase, provider: Provider) -> Completion:
    """Answer a case with one provider call, passing the case's system prompt and params through.

    Args:
        case: The case.
        provider: The cassette-wrapped provider the ``provider`` fixture built.

    Returns:
        The completion. Returning it rather than its text is what lets the case's budget ceilings
        see the call at all (DECISIONS 66).
    """
    return provider.complete(build_prompt(case), system=case.system, **case.params)
