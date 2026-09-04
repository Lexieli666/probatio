"""Assertions: one result type, one evaluator per assertion kind, and the similarity backends.

Every evaluator here has the same shape — take a declaration from :mod:`probatio.case` and the
output text, return an :class:`AssertionResult`, never raise — so that
:func:`probatio.runner.evaluate_case` can run all of a case's assertions and report every way the
output is wrong at once. Malformed inputs are results too: output that is not JSON, an empty
similarity reference, an unregistered backend.

The judge evaluator lives here alongside the other four but is only half-built in Phase 3: with
no provider configured it reports itself unenforceable, which is what it will keep doing after
Phase 4 fills in the grading.
"""

from __future__ import annotations

from .backends import SIMILARITY_BACKENDS, SimilarityBackend, TrigramCosine, get_backend
from .contains import evaluate_contains, evaluate_not_contains
from .judge import evaluate_judge
from .result import AssertionResult
from .schema import evaluate_schema_valid, strip_code_fence
from .similarity import evaluate_similarity

__all__ = [
    "SIMILARITY_BACKENDS",
    "AssertionResult",
    "SimilarityBackend",
    "TrigramCosine",
    "evaluate_contains",
    "evaluate_judge",
    "evaluate_not_contains",
    "evaluate_schema_valid",
    "evaluate_similarity",
    "get_backend",
    "strip_code_fence",
]
