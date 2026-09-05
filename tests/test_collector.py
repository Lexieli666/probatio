"""Phase 9: the run state, the relation roll-up and the session stack."""

from __future__ import annotations

import pytest

from probatio import AssertionResult, Completion
from probatio.budget import SuiteBudget
from probatio.cassette import CassetteStore
from probatio.collector import (
    CaseResult,
    RunState,
    case_key,
    current_state,
    merge_relation_results,
    pop_state,
    push_state,
    state_depth,
)
from probatio.metamorphic import Flip, RelationResult
from probatio.stability import case_stability


def relation(
    name: str, case_id: str, variants: int, violations: int, labels: tuple[str, ...] = ()
) -> RelationResult:
    return RelationResult(
        relation=name,
        case_id=case_id,
        n_variants=variants,
        n_violations=violations,
        violation_rate=violations / variants if variants else None,
        flips=[Flip(label=label, original_verdict=True, variant_verdict=False) for label in labels],
    )


def case(
    case_id: str, *relations: RelationResult, verdicts: tuple[bool, ...] = (True,)
) -> CaseResult:
    return CaseResult(
        case_id=case_id,
        node_id=f"test_demo.py::test_case[{case_id}]",
        suite="test_demo",
        verdict=all(verdicts),
        passed=all(verdicts),
        stability=case_stability(list(verdicts)),
        relations=list(relations),
    )


# -- merging one relation across a case's runs ------------------------------------------------


def test_merging_sums_the_counts_and_recomputes_the_rate() -> None:
    """Spec §3.9: the reported rate is over all N x k variant evaluations, not a mean of means."""
    merged = merge_relation_results(
        [relation("format_jitter", "c1", 3, 1, ("casing",)) for _ in range(5)]
    )
    assert (merged.n_variants, merged.n_violations) == (15, 5)
    assert merged.violation_rate == pytest.approx(1 / 3)
    assert [flip.label for flip in merged.flips] == ["casing"] * 5


def test_merging_keeps_not_applicable_not_applicable() -> None:
    merged = merge_relation_results([relation("order_invariant", "copd", 0, 0)] * 3)
    assert merged.violation_rate is None
    assert (merged.n_variants, merged.n_violations) == (0, 0)


def test_merging_one_result_returns_the_same_numbers() -> None:
    merged = merge_relation_results([relation("format_jitter", "c1", 3, 1)])
    assert merged.violation_rate == pytest.approx(1 / 3)


def test_merging_nothing_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one result"):
        merge_relation_results([])


# -- the report ---------------------------------------------------------------------------------


def test_the_relations_table_counts_applicable_cases_and_names_the_worst() -> None:
    state = RunState()
    state.record(case("alpha", relation("format_jitter", "alpha", 3, 1)))
    state.record(case("bravo", relation("format_jitter", "bravo", 3, 0)))
    state.record(case("charlie", relation("format_jitter", "charlie", 0, 0)))
    summary = state.report().relations[0]

    assert summary.relation == "format_jitter"
    assert (summary.n_cases, summary.n_not_applicable) == (2, 1)
    assert (summary.n_variants, summary.n_violations) == (6, 1)
    assert summary.mean_violation_rate == pytest.approx(1 / 6)
    assert summary.worst_case_id == "alpha"
    assert summary.worst_violation_rate == pytest.approx(1 / 3)


def test_a_tie_for_worst_is_broken_by_the_alphabetically_first_case() -> None:
    state = RunState()
    for case_id in ("zulu", "alpha", "mike"):
        state.record(case(case_id, relation("order_invariant", case_id, 2, 0)))
    assert state.report().relations[0].worst_case_id == "alpha"


def test_a_relation_no_case_could_use_reports_no_rate() -> None:
    state = RunState()
    state.record(case("copd", relation("order_invariant", "copd", 0, 0)))
    summary = state.report().relations[0]
    assert summary.mean_violation_rate is None
    assert summary.worst_case_id is None
    assert summary.n_not_applicable == 1


def test_relations_are_reported_in_name_order() -> None:
    state = RunState()
    state.record(
        case(
            "alpha",
            relation("order_invariant", "alpha", 2, 0),
            relation("format_jitter", "alpha", 3, 0),
        )
    )
    assert [row.relation for row in state.report().relations] == [
        "format_jitter",
        "order_invariant",
    ]


def test_the_report_carries_the_suite_totals_and_the_unknown_cases() -> None:
    budget = SuiteBudget(0.01)
    budget.record("alpha", 0.004)
    budget.record("bravo", None)
    state = RunState(runs=3, budget=budget)
    state.record(case("alpha"))
    report = state.report()
    assert report.runs == 3
    assert report.cost_total_usd == pytest.approx(0.004)
    assert report.cost_ceiling_usd == 0.01
    assert report.cost_unknown_case_ids == ["bravo"]
    assert report.cost_exceeded is False


def test_a_report_with_no_priced_case_has_no_total_at_all() -> None:
    """DECISIONS 39 keeps an unknown cost out of the total; the total itself is unknown too."""
    budget = SuiteBudget(None)
    budget.record("alpha", None)
    budget.record("bravo", None)
    state = RunState(budget=budget)
    state.record(case("alpha"))
    report = state.report()
    assert report.cost_total_usd is None
    assert report.cost_unknown_case_ids == ["alpha", "bravo"]


def test_a_case_that_really_cost_nothing_still_gives_a_total() -> None:
    budget = SuiteBudget(None)
    budget.record("alpha", 0.0)
    state = RunState(budget=budget)
    state.record(case("alpha"))
    assert state.report().cost_total_usd == 0.0


def test_an_overrun_is_visible_in_the_report() -> None:
    budget = SuiteBudget(0.001)
    budget.record("alpha", 0.004)
    state = RunState(budget=budget)
    state.record(case("alpha"))
    assert state.report().cost_exceeded is True


def test_the_stability_section_is_built_from_every_case() -> None:
    state = RunState(runs=5)
    state.record(case("alpha", verdicts=(True,) * 5))
    state.record(case("bravo", verdicts=(False, True, True, True, True)))
    assert state.report().stability.stability_score == pytest.approx(0.9)


def test_a_warning_is_said_once_however_often_it_is_added() -> None:
    state = RunState()
    state.warn("no price for fake-1")
    state.warn("no price for fake-1")
    state.warn("1 recorded sample")
    assert state.report().warnings == ["no price for fake-1", "1 recorded sample"]


def test_the_stores_notes_reach_the_report_as_warnings() -> None:
    store = CassetteStore()
    store.notes.append("cassette holds 1 recorded sample")
    state = RunState(store=store)
    state.record(case("alpha"))
    assert "cassette holds 1 recorded sample" in state.report().warnings


def test_building_the_report_twice_gives_the_same_answer() -> None:
    store = CassetteStore()
    store.notes.append("1 recorded sample")
    state = RunState(store=store)
    state.record(case("alpha"))
    assert state.report() == state.report()


def test_the_number_of_failed_cases_is_readable_off_the_report() -> None:
    state = RunState()
    state.record(case("alpha"))
    state.record(case("bravo", verdicts=(False,)))
    assert state.report().n_failed == 1


# -- calls the state observes ---------------------------------------------------------------


def test_a_completion_observed_outside_a_case_is_dropped() -> None:
    state = RunState()
    state.observe(Completion(text="x", model="m"))
    assert state.sink is None


def test_a_completion_observed_inside_a_case_lands_in_the_sink() -> None:
    state = RunState()
    state.sink = []
    completion = Completion(text="x", model="m")
    state.observe(completion)
    assert state.sink == [completion]


# -- the stack ------------------------------------------------------------------------------


def test_the_innermost_session_is_the_current_one() -> None:
    outer, inner = RunState(), RunState()
    depth = state_depth()
    push_state(outer)
    try:
        assert current_state() is outer
        push_state(inner)
        try:
            assert current_state() is inner
            assert state_depth() == depth + 2
        finally:
            assert pop_state() is inner
        assert current_state() is outer
    finally:
        assert pop_state() is outer
    assert state_depth() == depth


def test_popping_an_empty_stack_is_not_an_error() -> None:
    stack: list[object] = []
    while current_state() is not None:
        stack.append(pop_state())
    try:
        assert pop_state() is None
        assert current_state() is None
    finally:
        for state in reversed(stack):
            push_state(state)  # type: ignore[arg-type]


def test_an_assertion_result_list_survives_the_round_trip() -> None:
    result = CaseResult(
        case_id="alpha",
        node_id="test_demo.py::test_case[alpha]",
        suite="test_demo",
        verdict=True,
        passed=True,
        results=[AssertionResult(assertion_type="contains", passed=True, score=1.0, detail="d")],
        stability=case_stability([True]),
    )
    assert CaseResult.model_validate(result.model_dump()) == result


# -- the identity of one per-case entry ----------------------------------------------------------


def test_a_case_key_pairs_the_node_id_with_the_case_id() -> None:
    """Requirement 2, DECISIONS 73: a case id alone does not identify a report entry."""
    entry = case("htn-definition")
    assert case_key(entry) == ("test_demo.py::test_case[htn-definition]", "htn-definition")


def test_two_tests_checking_one_case_get_two_keys() -> None:
    first = case("htn-definition")
    second = first.model_copy(update={"node_id": "test_demo.py::test_paraphrase[htn-definition]"})
    assert first.case_id == second.case_id
    assert case_key(first) != case_key(second)
    state = RunState()
    state.record(first)
    state.record(second)
    report = state.report()
    assert len(report.cases) == 2
    assert len({case_key(entry) for entry in report.cases}) == 2
