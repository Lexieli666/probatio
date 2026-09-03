"""A fake retrieval-grounded question-answering app: the system under test for the demo suite.

The app builds one prompt from ``input.question`` and ``input.documents`` and asks the provider.
It is deliberately small; the interesting behaviour lives in the scripted provider in conftest.py.
"""

from __future__ import annotations

from probatio import Completion, LLMCase, Provider


def build_prompt(case: LLMCase) -> str:
    """Render a case's input as the user-turn prompt: numbered documents, then the question."""
    if isinstance(case.input, str):
        return case.input
    documents = case.input.get("documents", [])
    numbered = "\n".join(f"[{i}] {doc}" for i, doc in enumerate(documents, start=1))
    return f"Documents:\n{numbered}\n\nQuestion: {case.input['question']}"


def answer(case: LLMCase, provider: Provider) -> Completion:
    """Answer a case with the given provider; the case's ``params`` go through unchanged."""
    return provider.complete(build_prompt(case), system=case.system, **case.params)
