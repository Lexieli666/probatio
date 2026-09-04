"""Phase 8: the relations measured on the frozen demo suite against its scripted fake.

``examples/demo_suite/README.md`` makes qualitative claims about what each relation does to that
suite. They are claims about the implementation, so they belong in a test rather than in a doc:
the numbers are asserted here and appear nowhere in ``docs/``.

The verdict used throughout is "every assertion passed", which is what spec §0 means by the
boolean result of a case's exact assertions taken together. Judge results in this suite are
``unenforceable`` — no rubric here has a validation record — but their verdicts still count, which
is the Phase 4 behaviour this relies on.

One README claim does not hold as written; DECISIONS 51 and the errata section of
``examples/README.md`` record why: the casing variant is
said to flip every regular case whose keyword sits in its first sentence, but for
``gerd-alarm-features`` and ``insomnia-first-line`` the same keyword also appears, in lower case,
in the case's own documents, which ``format_jitter(field="input.question")`` does not touch. The
tests below assert the measured outcome and the reason for it.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType

import pytest

from probatio import AssertionResult, FakeProvider, LLMCase, load_cases
from probatio.metamorphic import (
    DistractorRobust,
    FormatJitter,
    OrderInvariant,
    ParaphraseInvariant,
    Relation,
    RelationResult,
    evaluate_relation,
    load_variants_file,
)

Evaluate = Callable[[LLMCase], tuple[bool, Sequence[AssertionResult]]]

REGULAR_TAGS = {"expected-fail", "flaky"}
NO_VALIDATION_RECORDS = Path("/nonexistent-validation-dir")

# The relations exactly as examples/demo_suite/test_demo.py applies them.
DISTRACTORS = ["Clinic parking is free after 6 pm."]


@pytest.fixture(scope="session")
def demo_cases(demo_dir: Path) -> list[LLMCase]:
    return load_cases(demo_dir / "cases")


@pytest.fixture(scope="session")
def regular_cases(demo_cases: list[LLMCase]) -> list[LLMCase]:
    return [case for case in demo_cases if not (REGULAR_TAGS & set(case.tags))]


@pytest.fixture
def evaluate(demo_conftest: ModuleType, demo_app: ModuleType, demo_rubrics: Path) -> Evaluate:
    """Run the demo's app against its scripted provider and evaluate every assertion."""
    from probatio.runner import evaluate_case

    def run(case: LLMCase) -> tuple[bool, Sequence[AssertionResult]]:
        responses = demo_conftest.RESPONSES
        provider = FakeProvider(responses=responses, cost_usd=0.0001, latency_ms=20.0)
        judge = FakeProvider(default=demo_conftest.fake_judge, cost_usd=0.0001, latency_ms=20.0)
        output = demo_app.answer(case, provider).text
        results = evaluate_case(
            case,
            output,
            judge_provider=judge,
            rubric_dirs=[demo_rubrics],
            validation_dir=NO_VALIDATION_RECORDS,
        )
        return all(result.passed for result in results), results

    return run


def measure(relation: Relation, case: LLMCase, evaluate: Evaluate) -> RelationResult:
    verdict, results = evaluate(case)
    return evaluate_relation(
        relation,
        case,
        original_verdict=verdict,
        original_results=results,
        evaluate=evaluate,
    )


Rates = dict[str, "float | None"]


def rates(relation: Relation, cases: Sequence[LLMCase], evaluate: Evaluate) -> Rates:
    return {case.id: measure(relation, case, evaluate).violation_rate for case in cases}


def only(cases: Sequence[LLMCase], case_id: str) -> LLMCase:
    return next(case for case in cases if case.id == case_id)


# -- the committed variants files -----------------------------------------------------------------


def test_both_committed_variants_files_load_and_belong_to_their_cases(demo_dir: Path) -> None:
    files = sorted((demo_dir / "variants").glob("*.yaml"))
    assert [path.stem for path in files] == ["htn-definition", "t2d-metformin"]
    for path in files:
        contents = load_variants_file(path)
        assert contents.case_id == path.stem
        assert contents.field == "input.question"
        assert len(contents.variants) == 3
        assert contents.generated_by.provider == "human"
        assert contents.generated_by.model is None
        assert contents.generated_by.prompt_hash is None
        assert contents.generated_by.created == "2026-09-03"


def test_every_paraphrase_case_has_a_committed_file_and_no_other_case_does(
    demo_cases: list[LLMCase], demo_dir: Path
) -> None:
    tagged = {case.id for case in demo_cases if "paraphrase" in case.tags}
    on_disk = {path.stem for path in (demo_dir / "variants").glob("*.yaml")}
    assert tagged == on_disk


# -- the base verdicts the relations are measured against -----------------------------------------


def test_every_regular_case_passes_against_the_scripted_fake(
    regular_cases: list[LLMCase], evaluate: Evaluate
) -> None:
    """The relations only mean something if the untransformed suite is green."""
    assert regular_cases
    for case in regular_cases:
        verdict, _ = evaluate(case)
        assert verdict, f"{case.id} fails before any relation is applied"


# -- order_invariant and distractor_robust --------------------------------------------------------


def test_permuting_the_documents_flips_nothing(
    regular_cases: list[LLMCase], evaluate: Evaluate
) -> None:
    """The keyword is in the question, so document order cannot move the verdict."""
    measured = rates(OrderInvariant("input.documents", 3), regular_cases, evaluate)
    assert set(measured.values()) <= {0.0, None}
    # Not applicable exactly where there is no list of at least two documents.
    assert measured["copd-spirometry"] is None
    assert measured["t2d-screening-json"] is None
    assert measured["htn-definition"] == 0.0


def test_a_two_document_case_is_measured_over_exactly_one_permutation(
    demo_cases: list[LLMCase], evaluate: Evaluate
) -> None:
    case = only(demo_cases, "htn-definition")
    result = measure(OrderInvariant("input.documents", 3), case, evaluate)
    assert (result.n_variants, result.n_violations) == (1, 0)


def test_inserting_an_unrelated_document_flips_nothing(
    regular_cases: list[LLMCase], evaluate: Evaluate
) -> None:
    relation = DistractorRobust(
        field="input.documents", distractors=DISTRACTORS, positions=("start", "end")
    )
    measured = rates(relation, regular_cases, evaluate)
    assert set(measured.values()) <= {0.0, None}
    assert measured["copd-spirometry"] is None
    assert measured["htn-definition"] == 0.0
    counted = measure(relation, only(regular_cases, "htn-definition"), evaluate)
    assert counted.n_variants == 2


# -- format_jitter ---------------------------------------------------------------------------------


def flips(kind: str, cases: Sequence[LLMCase], evaluate: Evaluate) -> set[str]:
    relation = FormatJitter((kind,), "input.question")
    flipped = set()
    for case in cases:
        if (measure(relation, case, evaluate).violation_rate or 0.0) > 0.0:
            flipped.add(case.id)
    return flipped


def test_doubled_whitespace_and_a_fenced_block_flip_nothing(
    regular_cases: list[LLMCase], evaluate: Evaluate
) -> None:
    assert flips("whitespace", regular_cases, evaluate) == set()
    assert flips("markdown", regular_cases, evaluate) == set()


def test_upper_casing_the_first_sentence_flips_the_cases_whose_keyword_it_destroys(
    regular_cases: list[LLMCase], evaluate: Evaluate
) -> None:
    """The measured outcome; see DECISIONS 51 for the two cases the README also expects here."""
    assert flips("casing", regular_cases, evaluate) == {
        "htn-definition",
        "htn-first-line",
        "t2d-screening-json",
    }


def test_the_two_cases_whose_keyword_sits_in_a_second_sentence_do_not_flip(
    regular_cases: list[LLMCase], evaluate: Evaluate
) -> None:
    """The README's own explanation: upper-casing the first sentence leaves the keyword alone."""
    flipped = flips("casing", regular_cases, evaluate)
    for case_id in ("t2d-metformin", "red-flag-chest-pain"):
        case = only(regular_cases, case_id)
        keyword = str(case.metadata["keyword"])
        question = str(case.input["question"])  # type: ignore[index]
        first, _, rest = question.partition(". ")
        assert keyword not in first and keyword in rest
        assert case_id not in flipped


def test_the_two_cases_the_readme_over_claims_keep_their_keyword_in_a_document(
    regular_cases: list[LLMCase], evaluate: Evaluate
) -> None:
    """DECISIONS 51: no transformation of ``input.question`` can destroy a keyword in a document.

    ``gerd-alarm-features`` and ``insomnia-first-line`` have their keyword in the question's first
    sentence *and* in their own documents, so the scripted provider still matches after the
    question is upper-cased and the verdict cannot move.
    """
    flipped = flips("casing", regular_cases, evaluate)
    for case_id in ("gerd-alarm-features", "insomnia-first-line"):
        case = only(regular_cases, case_id)
        keyword = str(case.metadata["keyword"])
        question = str(case.input["question"])  # type: ignore[index]
        documents = [str(document) for document in case.input["documents"]]  # type: ignore[index]
        assert keyword in question
        assert any(keyword in document for document in documents)
        assert case_id not in flipped


def test_a_bare_string_input_is_not_applicable_for_all_three_field_relations(
    demo_cases: list[LLMCase], evaluate: Evaluate
) -> None:
    """The README's claim for ``copd-spirometry``: not applicable, never zero."""
    case = only(demo_cases, "copd-spirometry")
    relations: list[Relation] = [
        OrderInvariant("input.documents", 3),
        DistractorRobust(field="input.documents", distractors=DISTRACTORS),
        FormatJitter(field="input.question"),
    ]
    for relation in relations:
        result = measure(relation, case, evaluate)
        assert relation.applicable(case) is False
        assert result.violation_rate is None
        assert (result.n_variants, result.n_violations) == (0, 0)


# -- paraphrase_invariant --------------------------------------------------------------------------


def test_the_frozen_paraphrases_show_one_violation_in_three_for_htn_definition(
    demo_cases: list[LLMCase], demo_dir: Path, evaluate: Evaluate
) -> None:
    """One paraphrase avoids the keyword on purpose, which is what the README says it does."""
    relation = ParaphraseInvariant(3, "input.question", demo_dir / "variants")
    case = only(demo_cases, "htn-definition")
    result = measure(relation, case, evaluate)
    assert (result.n_variants, result.n_violations, result.violation_rate) == (3, 1, 1 / 3)
    flip = result.flips[0]
    assert flip.label == "paraphrase-3"
    assert flip.original_verdict is True and flip.variant_verdict is False
    assert flip.changed_assertions == ["contains", "similarity", "judge"]


def test_the_frozen_paraphrases_of_t2d_metformin_flip_nothing(
    demo_cases: list[LLMCase], demo_dir: Path, evaluate: Evaluate
) -> None:
    """Every variant keeps the keyword outside the first sentence, so the verdict holds."""
    relation = ParaphraseInvariant(3, "input.question", demo_dir / "variants")
    case = only(demo_cases, "t2d-metformin")
    result = measure(relation, case, evaluate)
    assert (result.n_variants, result.n_violations, result.violation_rate) == (3, 0, 0.0)


def test_the_errata_names_this_discrepancy_and_the_tests_that_pin_it(repo_root: Path) -> None:
    """``examples/README.md`` corrects the frozen README; renaming a test must not orphan it."""
    errata = (repo_root / "examples" / "README.md").read_text(encoding="utf-8")
    assert "## Errata for `demo_suite/README.md`" in errata
    section = errata.split("## Errata for `demo_suite/README.md`", 1)[1]
    for case_id in ("gerd-alarm-features", "insomnia-first-line"):
        assert case_id in section
    assert "DECISIONS.md` entry 51" in section
    for name in (
        test_upper_casing_the_first_sentence_flips_the_cases_whose_keyword_it_destroys,
        test_the_two_cases_the_readme_over_claims_keep_their_keyword_in_a_document,
    ):
        assert name.__name__ in section, name.__name__
