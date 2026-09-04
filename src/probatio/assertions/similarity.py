"""The ``similarity`` assertion: the output must score at least ``tau`` against a reference.

Thin by design. All the interesting behaviour is in
:mod:`probatio.assertions.backends`; this module resolves the backend by name, guards the one
input that makes a score meaningless, and turns a number into a verdict.

The guarded input is an empty reference. ``TrigramCosine`` would score any non-empty output 0.0
against it, so with a low ``tau`` the assertion would look like it was checking something while
being unfalsifiable in one direction and unsatisfiable in the other. A reference that is empty,
or that normalises away to nothing, is a mistake in the case, so it fails with a detail that says
so rather than producing a number.
"""

from __future__ import annotations

from ..case import SimilarityAssertion
from ..errors import ProbatioConfigError
from .backends import get_backend, normalize
from .result import AssertionResult

__all__ = ["evaluate_similarity"]


def evaluate_similarity(assertion: SimilarityAssertion, output: str) -> AssertionResult:
    """Score the output against the assertion's reference and compare it with ``tau``.

    Args:
        assertion: The declaration, holding ``reference``, ``tau`` and ``backend``.
        output: The text under test.

    Returns:
        A result carrying the similarity score, passing when it is at least ``tau``. An empty
        reference or an unregistered backend is a failure with an explanatory detail and no
        score, never an exception.
    """
    if not normalize(assertion.reference):
        return AssertionResult(
            assertion_type="similarity",
            passed=False,
            score=None,
            detail="the similarity reference is empty, so no score means anything; give the "
            "reference text the output is supposed to paraphrase",
        )
    try:
        backend = get_backend(assertion.backend)
    except ProbatioConfigError as exc:
        return AssertionResult(
            assertion_type="similarity", passed=False, score=None, detail=exc.message
        )
    score = backend.similarity(output, assertion.reference)
    verdict = "at or above" if score >= assertion.tau else "below"
    return AssertionResult(
        assertion_type="similarity",
        passed=score >= assertion.tau,
        score=score,
        detail=f"{assertion.backend} similarity {score:.3f} is {verdict} tau {assertion.tau:.3f}",
    )
