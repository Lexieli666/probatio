"""``evaluate_case``: run every assertion a case declares and return every result.

This is the one place that knows the mapping from an assertion's declared ``type`` to the function
that evaluates it. It runs all of them, in declaration order, and returns one result each. It does
not decide the verdict, does not raise on failure and does not touch budgets, snapshots or
relations; the plugin's ``Probatio.check`` (spec §3.12) composes those around it.

Running every assertion rather than stopping at the first failure is the whole point: a report
that says an answer missed one required substring *and* failed the schema *and* drifted below its
similarity floor tells a developer what changed. One that says "missing 'thiazide'" and stops
tells them where to put a breakpoint.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from .assertions import (
    AssertionResult,
    evaluate_contains,
    evaluate_judge,
    evaluate_not_contains,
    evaluate_schema_valid,
    evaluate_similarity,
)
from .case import (
    ContainsAssertion,
    LLMCase,
    NotContainsAssertion,
    SchemaValidAssertion,
    SimilarityAssertion,
)
from .providers import Provider

__all__ = ["evaluate_case"]


def evaluate_case(
    case: LLMCase,
    output: str,
    *,
    judge_provider: Provider | None = None,
    base_dir: Path | None = None,
    rubric_dirs: Sequence[Path] | None = None,
    validation_dir: Path | None = None,
) -> list[AssertionResult]:
    """Evaluate every assertion of a case against one output.

    Args:
        case: The case whose assertions to run.
        output: The application's output for that case.
        judge_provider: The provider used to grade ``judge`` assertions. ``None`` reports every
            judge assertion as unenforceable rather than passing it.
        base_dir: Directory a relative ``schema_file`` is resolved against. Defaults to the
            current working directory, which is pytest's rootdir under a normal invocation.
        rubric_dirs: Directories a judge's rubric name is searched in, in order. Defaults to
            ``[Path.cwd() / "rubrics"]`` (DECISIONS 23).
        validation_dir: Where judge validation records live. Defaults to
            ``Path.cwd() / ".probatio" / "judges"``.

    Returns:
        One :class:`~probatio.assertions.AssertionResult` per assertion, in declaration order.
        Assertions never raise, so this list is always as long as ``case.assertions``.
    """
    results: list[AssertionResult] = []
    for assertion in case.assertions:
        if isinstance(assertion, SchemaValidAssertion):
            results.append(evaluate_schema_valid(assertion, output, base_dir=base_dir))
        elif isinstance(assertion, ContainsAssertion):
            results.append(evaluate_contains(assertion, output))
        elif isinstance(assertion, NotContainsAssertion):
            results.append(evaluate_not_contains(assertion, output))
        elif isinstance(assertion, SimilarityAssertion):
            results.append(evaluate_similarity(assertion, output))
        else:
            results.append(
                evaluate_judge(
                    assertion,
                    case,
                    output,
                    judge_provider=judge_provider,
                    rubric_dirs=rubric_dirs,
                    validation_dir=validation_dir,
                )
            )
    return results
