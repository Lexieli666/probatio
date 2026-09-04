"""Turning a relation and a case into a :class:`~probatio.metamorphic.base.RelationResult`.

This module owns the arithmetic and nothing else. It is given a relation, the case, the verdict
and assertion results the untransformed case already produced, and a callable that evaluates one
case; it returns the relation result. Phase 9's ``Probatio.check`` supplies the callable — the
system under test composed with :func:`~probatio.runner.evaluate_case` — and calls this after the
original case has run, so a variant is never evaluated for a case that was not evaluated first.

Two definitions are fixed here, both from spec §3.9.

**A violation is a difference in either direction.** A variant that *passes* where the original
failed is as much a violation of "this transformation preserves the meaning" as one that fails
where the original passed. It is also the more interesting one: it usually means the original was
failing for a reason the relation just removed.

**Not applicable is not zero.** A relation the case is out of scope for, or that generated no
variants, gets ``violation_rate=None``. Dividing by zero is not the reason; claiming a
robustness result that was never measured is.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from ..assertions import AssertionResult
from ..case import LLMCase
from .base import Flip, Relation, RelationResult

__all__ = ["VariantEvaluator", "changed_assertion_types", "evaluate_relation"]

VariantEvaluator = Callable[[LLMCase], tuple[bool, Sequence[AssertionResult]]]
"""What :func:`evaluate_relation` is given to run one variant: a case in, a verdict and its
assertion results out. Phase 9 passes the system under test composed with ``evaluate_case``."""


def changed_assertion_types(
    original: Sequence[AssertionResult], variant: Sequence[AssertionResult]
) -> list[str]:
    """Name the assertion types whose ``passed`` flag differed between two runs.

    Results are compared position by position, because a variant is the same case with one field
    replaced and so declares the same assertions in the same order. Types are reported once each,
    first occurrence first: a report says *what kind* of check moved, and a case with two
    ``contains`` assertions that both moved has one problem, not two.

    Args:
        original: The untransformed case's results.
        variant: The variant's results.

    Returns:
        The differing assertion types, in declaration order, without repeats.
    """
    changed: list[str] = []
    for before, after in zip(original, variant, strict=False):
        if before.passed != after.passed and before.assertion_type not in changed:
            changed.append(before.assertion_type)
    return changed


def evaluate_relation(
    relation: Relation,
    case: LLMCase,
    *,
    original_verdict: bool,
    original_results: Sequence[AssertionResult],
    evaluate: VariantEvaluator,
) -> RelationResult:
    """Evaluate every variant of a case and report the violation rate.

    Args:
        relation: The configured relation.
        case: The untransformed case.
        original_verdict: The verdict the untransformed case produced.
        original_results: The untransformed case's assertion results, used to say which
            assertions moved.
        evaluate: Runs one variant and returns its verdict and assertion results.

    Returns:
        The result. ``violation_rate`` is ``None`` when the relation was not applicable to the
        case or generated no variants, and a fraction of ``n_variants`` otherwise.

    Raises:
        MissingVariantsError: ``paraphrase_invariant`` has no frozen file for this case. This is
            the one failure a relation raises: a violation never does, but a suite whose frozen
            variants were not committed is measuring nothing and has to say so.
    """
    if not relation.applicable(case):
        return _not_applicable(relation, case)
    variants = relation.variants(case)
    if not variants:
        return _not_applicable(relation, case)

    flips: list[Flip] = []
    for variant in variants:
        variant_verdict, variant_results = evaluate(variant.case)
        if variant_verdict != original_verdict:
            flips.append(
                Flip(
                    label=variant.label,
                    original_verdict=original_verdict,
                    variant_verdict=variant_verdict,
                    changed_assertions=changed_assertion_types(original_results, variant_results),
                )
            )
    return RelationResult(
        relation=relation.name,
        case_id=case.id,
        n_variants=len(variants),
        n_violations=len(flips),
        violation_rate=len(flips) / len(variants),
        flips=flips,
    )


def _not_applicable(relation: Relation, case: LLMCase) -> RelationResult:
    """Build the result for a case this relation observed nothing about."""
    return RelationResult(
        relation=relation.name,
        case_id=case.id,
        n_variants=0,
        n_violations=0,
        violation_rate=None,
        flips=[],
    )
