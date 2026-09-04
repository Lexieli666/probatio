"""Phase 8: the arithmetic — what counts as a violation, and what "not applicable" means."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from probatio import AssertionResult, LLMCase, MissingVariantsError
from probatio.metamorphic import (
    ParaphraseInvariant,
    Relation,
    Variant,
    changed_assertion_types,
    evaluate_relation,
)

CASE = LLMCase.model_validate(
    {
        "id": "c1",
        "input": {"question": "q", "documents": ["a", "b"]},
        "assertions": [
            {"type": "contains", "any": ["x"]},
            {"type": "not_contains", "all": ["y"]},
        ],
    }
)


def results(*passed: bool) -> list[AssertionResult]:
    kinds = ["contains", "not_contains", "similarity", "judge"]
    return [
        AssertionResult(assertion_type=kinds[index], passed=flag, score=None, detail="d")
        for index, flag in enumerate(passed)
    ]


class Fixed(Relation):
    """A relation with a fixed number of variants, labelled ``v1`` upward."""

    name = "fixed"
    citation = "[LLMORPH]"

    def __init__(self, n: int, applicable: bool = True) -> None:
        self.n = n
        self._applicable = applicable

    def applicable(self, case: LLMCase) -> bool:
        return self._applicable

    def variants(self, case: LLMCase) -> list[Variant]:
        return [Variant(case=case, label=f"v{index}") for index in range(1, self.n + 1)]


def evaluator(
    verdicts: Sequence[bool], all_results: Sequence[Sequence[AssertionResult]] | None = None
) -> tuple[object, list[LLMCase]]:
    """Return a callable handing out one verdict per call, and the cases it was called with."""
    seen: list[LLMCase] = []

    def evaluate(case: LLMCase) -> tuple[bool, Sequence[AssertionResult]]:
        index = len(seen)
        seen.append(case)
        verdict = verdicts[index]
        return verdict, (all_results[index] if all_results else results(verdict, verdict))

    return evaluate, seen


def test_one_flip_in_four_variants_is_a_quarter() -> None:
    """Spec §3.9 acceptance."""
    evaluate, seen = evaluator([True, True, False, True])
    result = evaluate_relation(
        Fixed(4),
        CASE,
        original_verdict=True,
        original_results=results(True, True),
        evaluate=evaluate,  # type: ignore[arg-type]
    )
    assert (result.n_variants, result.n_violations, result.violation_rate) == (4, 1, 0.25)
    assert [flip.label for flip in result.flips] == ["v3"]
    assert len(seen) == 4
    assert result.relation == "fixed"
    assert result.case_id == "c1"


def test_a_variant_that_passes_where_the_original_failed_is_also_a_violation() -> None:
    """Spec §3.9 acceptance: flips in both directions count."""
    evaluate, _ = evaluator([True, False])
    result = evaluate_relation(
        Fixed(2),
        CASE,
        original_verdict=False,
        original_results=results(False, True),
        evaluate=evaluate,  # type: ignore[arg-type]
    )
    assert (result.n_violations, result.violation_rate) == (1, 0.5)
    flip = result.flips[0]
    assert (flip.label, flip.original_verdict, flip.variant_verdict) == ("v1", False, True)


def test_every_variant_flipping_is_a_rate_of_one() -> None:
    evaluate, _ = evaluator([False, False, False])
    result = evaluate_relation(
        Fixed(3),
        CASE,
        original_verdict=True,
        original_results=results(True, True),
        evaluate=evaluate,  # type: ignore[arg-type]
    )
    assert result.violation_rate == 1.0
    assert [flip.label for flip in result.flips] == ["v1", "v2", "v3"]


def test_a_relation_the_case_is_out_of_scope_for_reports_no_rate() -> None:
    """DECISIONS 8: not applicable is a result, and it is not zero."""
    evaluate, seen = evaluator([])
    result = evaluate_relation(
        Fixed(3, applicable=False),
        CASE,
        original_verdict=True,
        original_results=results(True, True),
        evaluate=evaluate,  # type: ignore[arg-type]
    )
    assert result.violation_rate is None
    assert (result.n_variants, result.n_violations) == (0, 0)
    assert seen == []


def test_a_relation_that_generated_nothing_reports_no_rate_either() -> None:
    evaluate, seen = evaluator([])
    result = evaluate_relation(
        Fixed(0),
        CASE,
        original_verdict=True,
        original_results=results(True, True),
        evaluate=evaluate,  # type: ignore[arg-type]
    )
    assert result.violation_rate is None
    assert seen == []


def test_a_flip_names_the_assertion_types_that_moved() -> None:
    evaluate, _ = evaluator([False], [results(False, True)])
    result = evaluate_relation(
        Fixed(1),
        CASE,
        original_verdict=True,
        original_results=results(True, True),
        evaluate=evaluate,  # type: ignore[arg-type]
    )
    assert result.flips[0].changed_assertions == ["contains"]


def test_changed_assertion_types_reports_each_type_once_in_declaration_order() -> None:
    before = results(True, True, True, True)
    after = results(False, True, False, False)
    assert changed_assertion_types(before, after) == ["contains", "similarity", "judge"]


def test_changed_assertion_types_is_empty_when_only_scores_moved() -> None:
    before = [AssertionResult(assertion_type="similarity", passed=True, score=0.9, detail="d")]
    after = [AssertionResult(assertion_type="similarity", passed=True, score=0.4, detail="d")]
    assert changed_assertion_types(before, after) == []


def test_result_lists_of_different_lengths_do_not_raise() -> None:
    """A relation never raises for a violation, so a mismatch truncates rather than exploding."""
    assert changed_assertion_types(results(True, True), results(False)) == ["contains"]
    assert changed_assertion_types(results(True), results(False, False)) == ["contains"]


def test_a_missing_variants_file_is_the_one_failure_a_relation_raises() -> None:
    evaluate, _ = evaluator([])
    with pytest.raises(MissingVariantsError):
        evaluate_relation(
            ParaphraseInvariant(3, "input.question", "/nonexistent-variants"),
            CASE,
            original_verdict=True,
            original_results=results(True, True),
            evaluate=evaluate,  # type: ignore[arg-type]
        )
