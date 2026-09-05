"""Phase 9: ``Probatio.check`` — what it evaluates, what it records and what it raises.

Nothing here starts a pytest session: ``Probatio`` is built by hand with a ``ProbatioSettings``
and a ``RunState``, which is what keeps the composition testable without a fixture. The pytest
surface itself is exercised through ``pytester`` in ``tests/test_plugin.py``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

from probatio import (
    Completion,
    FakeProvider,
    LLMCase,
    MissingCassetteError,
    ProbatioConfigError,
    ScriptedProvider,
)
from probatio.budget import PriceTable
from probatio.cassette import CassetteProvider, CassetteStore
from probatio.collector import RunState
from probatio.metamorphic import FormatJitter, OrderInvariant, Relation
from probatio.session import Probatio, ProbatioSettings
from probatio.stability import FlakyTolerance

KEYWORD = "spirometry"
ANSWER = "Spirometry confirms COPD."


def make_case(**overrides: Any) -> LLMCase:
    payload: dict[str, Any] = {
        "id": "copd",
        "input": {
            "question": f"Which test confirms COPD, and is it {KEYWORD}",
            "documents": ["a", "b"],
        },
        "assertions": [{"type": "contains", "any": [KEYWORD]}],
    }
    payload.update(overrides)
    return LLMCase.model_validate(payload)


def settings(tmp_path: Path, **overrides: Any) -> ProbatioSettings:
    base: dict[str, Any] = {
        "rootdir": tmp_path,
        "baseline_dir": tmp_path / ".probatio" / "baseline",
    }
    base.update(overrides)
    return ProbatioSettings(**base)


def make_probatio(
    tmp_path: Path,
    *,
    state: RunState | None = None,
    relations: Sequence[Relation] = (),
    tolerance: FlakyTolerance | None = None,
    judge_provider: Any = None,
    **option_overrides: Any,
) -> tuple[Probatio, RunState]:
    run_state = state if state is not None else RunState(store=CassetteStore(tmp_path / "tapes"))
    return (
        Probatio(
            settings=settings(tmp_path, **option_overrides),
            state=run_state,
            suite="test_suite",
            judge_provider=judge_provider,
            relations=relations,
            tolerance=tolerance,
        ),
        run_state,
    )


def answering(text: str = ANSWER, **kwargs: Any) -> FakeProvider:
    return FakeProvider(default=text, **kwargs)


def sut_for(provider: Any) -> Callable[[LLMCase], Completion]:
    def sut(case: LLMCase) -> Completion:
        return provider.complete(str(case.input))

    return sut


# -- the shape of one run -------------------------------------------------------------------


def test_a_passing_case_is_recorded_and_returned(tmp_path: Path) -> None:
    probatio, state = make_probatio(tmp_path)
    result = probatio.check(make_case(), sut_for(answering(cost_usd=0.002, latency_ms=7.0)))

    assert result.passed is True
    assert result.verdict is True
    assert result.suite == "test_suite"
    assert [item.assertion_type for item in result.results] == ["contains"]
    assert result.cost_usd == pytest.approx(0.002)
    assert result.latency_ms == pytest.approx(7.0)
    assert result.model == "fake-1"
    assert state.cases == [result]


def test_a_failing_case_raises_with_every_failed_assertion_named(tmp_path: Path) -> None:
    probatio, state = make_probatio(tmp_path)
    case = make_case(
        assertions=[{"type": "contains", "any": [KEYWORD]}, {"type": "not_contains", "all": ["x"]}]
    )
    with pytest.raises(AssertionError) as excinfo:
        probatio.check(case, sut_for(answering("an x, and no keyword")))

    message = str(excinfo.value)
    assert "copd: verdict failed" in message
    assert "contains:" in message and "not_contains:" in message
    assert state.cases[0].passed is False
    assert state.cases[0].verdict is False


def test_a_system_under_test_may_return_plain_text(tmp_path: Path) -> None:
    """Requirement 7: a ``str`` gives the output and no completion of its own."""
    probatio, _ = make_probatio(tmp_path)
    result = probatio.check(make_case(), lambda case: ANSWER)
    assert result.passed is True
    assert result.cost_usd is None
    assert result.model is None


def test_a_returned_completion_supplies_the_output_and_the_call(tmp_path: Path) -> None:
    """Requirement 7: a ``Completion`` gives both, which is what makes a ceiling enforceable."""
    completion = Completion(text=ANSWER, model="m1", cost_usd=0.5, latency_ms=3.0)
    probatio, _ = make_probatio(tmp_path)
    result = probatio.check(make_case(), lambda case: completion)
    assert (result.cost_usd, result.latency_ms, result.model) == (0.5, 3.0, "m1")


def test_a_completion_is_counted_once_when_the_provider_also_reported_it(tmp_path: Path) -> None:
    state = RunState(store=CassetteStore(tmp_path / "tapes"))
    provider = answering(cost_usd=0.002)
    probatio, _ = make_probatio(tmp_path, state=state)

    def sut(case: LLMCase) -> Completion:
        completion = provider.complete(str(case.input))
        state.observe(completion)
        return completion

    assert probatio.check(make_case(), sut).cost_usd == pytest.approx(0.002)


def test_calls_made_through_an_instrumented_provider_are_all_counted(tmp_path: Path) -> None:
    state = RunState(store=CassetteStore(tmp_path / "tapes"))
    provider = answering(cost_usd=0.002)
    probatio, _ = make_probatio(tmp_path, state=state)

    def sut(case: LLMCase) -> str:
        for _ in range(3):
            state.observe(provider.complete(str(case.input)))
        return ANSWER

    assert probatio.check(make_case(), sut).cost_usd == pytest.approx(0.006)


# -- the cassette context -------------------------------------------------------------------


def test_the_active_case_is_set_before_the_system_under_test_runs(tmp_path: Path) -> None:
    """Requirement 6: ``begin_case`` with the suite, the case id and the run index."""
    state = RunState(store=CassetteStore(tmp_path / "tapes"))
    probatio, _ = make_probatio(tmp_path, state=state)
    seen: list[tuple[str, str, int]] = []

    def sut(case: LLMCase) -> str:
        active = state.store.require_active()
        seen.append((active.suite, active.case_id, active.run_index))
        return ANSWER

    probatio.check(make_case(), sut)
    assert seen == [("test_suite", "copd", 0)]
    assert state.store.active is None, "the context is cleared once the case is done"


def test_each_run_gets_its_own_run_index(tmp_path: Path) -> None:
    state = RunState(store=CassetteStore(tmp_path / "tapes"))
    probatio, _ = make_probatio(tmp_path, state=state, runs=3)
    seen: list[int] = []

    def sut(case: LLMCase) -> str:
        seen.append(state.store.require_active().run_index)
        return ANSWER

    probatio.check(make_case(), sut)
    assert seen == [0, 1, 2]


def test_a_missing_tape_is_warned_about_and_still_raised(tmp_path: Path) -> None:
    """Requirement 8: a missing tape reaches the report as well as the test."""
    state = RunState(store=CassetteStore(tmp_path / "tapes"))
    probatio, _ = make_probatio(tmp_path, state=state)
    taped = CassetteProvider(answering(), state.store, "replay")

    with pytest.raises(MissingCassetteError):
        probatio.check(make_case(), sut_for(taped))
    assert any("cassette" in warning for warning in state.report().warnings)


# -- repeated runs ---------------------------------------------------------------------------


def test_five_runs_of_a_deterministic_provider_give_a_rate_of_one(tmp_path: Path) -> None:
    """Spec §3.10 acceptance."""
    probatio, _ = make_probatio(tmp_path, runs=5)
    result = probatio.check(make_case(), sut_for(answering()))
    assert result.stability.runs == 5
    assert result.stability.pass_rate == 1.0
    assert result.stability.wilson_low > 0.5


def test_a_script_that_fails_one_of_five_is_a_rate_of_point_eight(tmp_path: Path) -> None:
    """Spec §3.10 acceptance: it fails without the marker."""
    provider = ScriptedProvider(script=["nothing here", *[ANSWER] * 4])
    probatio, state = make_probatio(tmp_path, runs=5)
    with pytest.raises(AssertionError, match="pass rate 0.80"):
        probatio.check(make_case(), sut_for(provider))
    assert state.cases[0].stability.pass_rate == 0.8


def test_the_same_script_passes_under_a_declared_tolerance(tmp_path: Path) -> None:
    """Spec §3.10 acceptance: and it passes with ``@flaky_tolerant(p=0.8, n=5)``."""
    provider = ScriptedProvider(script=["nothing here", *[ANSWER] * 4])
    probatio, _ = make_probatio(tmp_path, tolerance=FlakyTolerance(p=0.8, n=5))
    result = probatio.check(make_case(), sut_for(provider))
    assert result.passed is True
    assert result.stability.pass_rate == 0.8
    assert result.stability.floor == 0.8


def test_the_tolerance_overrides_the_runs_flag(tmp_path: Path) -> None:
    probatio, _ = make_probatio(tmp_path, runs=99, tolerance=FlakyTolerance(p=0.5, n=2))
    assert probatio.runs == 2
    assert probatio.check(make_case(), sut_for(answering())).stability.runs == 2


def test_a_repeated_case_is_explained_by_a_run_that_agreed_with_its_verdict(
    tmp_path: Path,
) -> None:
    provider = ScriptedProvider(script=["nothing here", *[ANSWER] * 4])
    probatio, _ = make_probatio(tmp_path, tolerance=FlakyTolerance(p=0.8, n=5))
    result = probatio.check(make_case(), sut_for(provider))
    assert all(item.passed for item in result.results), "run 0 failed; the report shows a passer"


# -- budgets ----------------------------------------------------------------------------------


def test_a_latency_ceiling_fails_the_case(tmp_path: Path) -> None:
    """Spec §3.7 acceptance: latency ceilings fail correctly with ``FakeProvider``."""
    case = make_case(budget={"max_latency_ms": 5.0})
    probatio, _ = make_probatio(tmp_path)
    with pytest.raises(AssertionError, match="budget ceiling"):
        probatio.check(case, sut_for(answering(latency_ms=50.0)))


def test_an_unpriced_cost_ceiling_is_unenforceable_and_warned_about(tmp_path: Path) -> None:
    """Spec §3.7 acceptance: it is reported as unenforceable, never as passed."""
    case = make_case(budget={"max_cost_usd": 0.01})
    probatio, state = make_probatio(tmp_path)
    result = probatio.check(case, sut_for(answering(cost_usd=None)))

    ceiling = next(item for item in result.budget_results if item.assertion_type == "budget_cost")
    assert (ceiling.passed, ceiling.unenforceable) == (False, True)
    assert result.passed is True, "an unenforceable ceiling warns; it does not fail the case"
    assert any("unenforceable" in warning for warning in state.report().warnings)


def test_the_default_latency_ceiling_applies_to_a_case_that_declares_none(tmp_path: Path) -> None:
    probatio, _ = make_probatio(tmp_path, max_latency_ms=5.0)
    with pytest.raises(AssertionError, match="budget_latency"):
        probatio.check(make_case(), sut_for(answering(latency_ms=50.0)))


def test_a_budget_is_evaluated_per_run_not_over_the_whole_case(tmp_path: Path) -> None:
    """DECISIONS 59: five runs of a one-cent case are five one-cent cases."""
    case = make_case(budget={"max_cost_usd": 0.003})
    probatio, _ = make_probatio(tmp_path, runs=5)
    result = probatio.check(case, sut_for(answering(cost_usd=0.002)))
    assert result.passed is True
    assert result.cost_usd == pytest.approx(0.01), "the report still totals every run"


def test_any_run_over_the_ceiling_fails_the_case(tmp_path: Path) -> None:
    case = make_case(budget={"max_cost_usd": 0.001})
    provider = ScriptedProvider(script=[ANSWER], cost_usd=0.002)
    probatio, _ = make_probatio(tmp_path, runs=3)
    with pytest.raises(AssertionError, match="budget_cost"):
        probatio.check(case, sut_for(provider))


def test_the_session_total_sums_every_run_of_a_case(tmp_path: Path) -> None:
    probatio, state = make_probatio(tmp_path, runs=4)
    probatio.check(make_case(), sut_for(answering(cost_usd=0.002)))
    assert state.budget.total_usd == pytest.approx(0.008)


def test_a_price_table_makes_an_unpriced_completion_enforceable(tmp_path: Path) -> None:
    prices_file = tmp_path / "prices.yaml"
    prices_file.write_text(
        "fake-1: {input_per_mtok: 1.0, output_per_mtok: 2.0}\n", encoding="utf-8"
    )
    case = make_case(budget={"max_cost_usd": 1.0})
    probatio, _ = make_probatio(tmp_path, prices=PriceTable.load(prices_file))
    completion = Completion(text=ANSWER, model="fake-1", tokens_in=100, tokens_out=50)
    result = probatio.check(case, lambda _: completion)

    ceiling = next(item for item in result.budget_results if item.assertion_type == "budget_cost")
    assert ceiling.unenforceable is False
    assert result.cost_usd == pytest.approx(100 / 1e6 * 1.0 + 50 / 1e6 * 2.0)


# -- snapshots -----------------------------------------------------------------------------------


def test_the_snapshot_is_compared_on_the_first_run_only(tmp_path: Path) -> None:
    case = make_case(snapshot="scores")
    probatio, _ = make_probatio(tmp_path, runs=3)
    result = probatio.check(case, sut_for(answering()))
    assert result.snapshot is not None
    assert result.snapshot.state == "recorded"

    again, _ = make_probatio(tmp_path, runs=3)
    assert again.check(case, sut_for(answering())).snapshot is not None
    assert again.check(case, sut_for(answering())).snapshot.state == "unchanged"  # type: ignore[union-attr]


def test_a_case_with_snapshot_off_gets_no_comparison(tmp_path: Path) -> None:
    probatio, _ = make_probatio(tmp_path)
    assert probatio.check(make_case(), sut_for(answering())).snapshot is None


def test_a_drifting_output_fails_the_case(tmp_path: Path) -> None:
    case = make_case(snapshot="output")
    probatio, _ = make_probatio(tmp_path)
    probatio.check(case, sut_for(answering()))

    other, _ = make_probatio(tmp_path)
    with pytest.raises(AssertionError, match="snapshot output_changed"):
        other.check(case, sut_for(answering(f"{ANSWER} And more.")))


def test_update_baseline_re_records_instead_of_failing(tmp_path: Path) -> None:
    case = make_case(snapshot="output")
    make_probatio(tmp_path)[0].check(case, sut_for(answering()))
    updater, _ = make_probatio(tmp_path, update_baseline=True)
    result = updater.check(case, sut_for(answering(f"{ANSWER} And more.")))
    assert result.snapshot is not None and result.snapshot.state == "updated"
    assert result.passed is True


def test_the_budget_results_are_recorded_alongside_the_assertions(tmp_path: Path) -> None:
    """DECISIONS 38 anticipated this: a scores baseline stores ``null`` for a budget check."""
    case = make_case(snapshot="scores", budget={"max_latency_ms": 5000.0})
    probatio, _ = make_probatio(tmp_path)
    probatio.check(case, sut_for(answering()))
    baseline = (tmp_path / ".probatio" / "baseline" / "test_suite" / "copd.json").read_text()
    assert "budget_latency" in baseline
    assert '"score": null' in baseline


# -- relations -------------------------------------------------------------------------------


def test_a_relation_is_evaluated_after_the_case_and_never_raises(tmp_path: Path) -> None:
    probatio, _ = make_probatio(tmp_path, relations=[FormatJitter(("casing",), "input.question")])
    provider = FakeProvider(responses={KEYWORD: ANSWER})
    result = probatio.check(make_case(), sut_for(provider))

    assert result.passed is True, "a violation is reported, not raised"
    relation = result.relations[0]
    assert relation.relation == "format_jitter"
    assert relation.n_variants == 1
    assert relation.n_violations == 1, "upper-casing destroys the keyword the fake matches"
    assert relation.violation_rate == 1.0


def test_a_relation_the_case_is_out_of_scope_for_reports_no_rate(tmp_path: Path) -> None:
    probatio, _ = make_probatio(tmp_path, relations=[OrderInvariant("input.documents", 3)])
    case = make_case(input="a bare string")
    result = probatio.check(case, sut_for(answering()))
    assert result.relations[0].violation_rate is None


def test_the_rate_is_over_every_run_times_every_variant(tmp_path: Path) -> None:
    """Spec §3.9: under ``--runs N`` the rate covers all N x k variant evaluations."""
    probatio, _ = make_probatio(
        tmp_path, runs=4, relations=[FormatJitter(("casing", "whitespace"), "input.question")]
    )
    provider = FakeProvider(responses={KEYWORD: ANSWER})
    relation = probatio.check(make_case(), sut_for(provider)).relations[0]
    assert relation.n_variants == 8
    assert relation.n_violations == 4
    assert relation.violation_rate == 0.5


def test_variant_calls_reach_the_session_total_but_not_the_cases_ceiling(tmp_path: Path) -> None:
    """DECISIONS 60: the harness measuring the case is not the case doing its work."""
    case = make_case(budget={"max_cost_usd": 0.0015})
    probatio, state = make_probatio(
        tmp_path, relations=[FormatJitter(("casing", "whitespace"), "input.question")]
    )
    result = probatio.check(case, sut_for(answering(cost_usd=0.001)))

    assert result.passed is True, "three calls at a cent each, but only one is the case's own"
    assert result.cost_usd == pytest.approx(0.001)
    assert state.budget.total_usd == pytest.approx(0.003)


def test_no_relations_means_no_relation_results(tmp_path: Path) -> None:
    probatio, _ = make_probatio(tmp_path)
    assert probatio.check(make_case(), sut_for(answering())).relations == []


# -- judges ---------------------------------------------------------------------------------------


def test_an_unvalidated_judge_is_counted_in_the_warnings(tmp_path: Path) -> None:
    """Requirement 8, and spec §3.5's summary line."""
    (tmp_path / "rubrics").mkdir()
    (tmp_path / "rubrics" / "faithfulness.md").write_text("Grade it.", encoding="utf-8")
    case = make_case(
        assertions=[
            {"type": "contains", "any": [KEYWORD]},
            {"type": "judge", "rubric": "faithfulness"},
        ]
    )
    judge = FakeProvider(default='{"verdict": "pass", "score": 1.0}')
    probatio, state = make_probatio(tmp_path, judge_provider=judge)
    result = probatio.check(case, sut_for(answering()))

    assert result.passed is True
    assert any("no validation record" in warning for warning in state.report().warnings)


def test_a_case_with_no_judge_provider_reports_it_unenforceable(tmp_path: Path) -> None:
    (tmp_path / "rubrics").mkdir()
    (tmp_path / "rubrics" / "faithfulness.md").write_text("Grade it.", encoding="utf-8")
    case = make_case(assertions=[{"type": "judge", "rubric": "faithfulness"}])
    probatio, _ = make_probatio(tmp_path)
    with pytest.raises(AssertionError):
        probatio.check(case, sut_for(answering()))


def test_a_rubric_is_found_beside_the_test_module_as_well_as_at_rootdir(tmp_path: Path) -> None:
    """DECISIONS 23: the plugin passes both directories; here they are passed by hand."""
    beside = tmp_path / "suite" / "rubrics"
    beside.mkdir(parents=True)
    (beside / "faithfulness.md").write_text("Grade it.", encoding="utf-8")
    case = make_case(assertions=[{"type": "judge", "rubric": "faithfulness"}])
    probatio = Probatio(
        settings=settings(tmp_path),
        state=RunState(store=CassetteStore(tmp_path / "tapes")),
        suite="test_suite",
        judge_provider=FakeProvider(default='{"verdict": "pass", "score": 1.0}'),
        rubric_dirs=[tmp_path / "rubrics", beside],
    )
    assert probatio.check(case, sut_for(answering())).passed is True


def test_the_default_rubric_directory_is_rootdirs(tmp_path: Path) -> None:
    probatio, _ = make_probatio(tmp_path)
    assert probatio.rubric_dirs == [tmp_path / "rubrics"]


# -- paths -------------------------------------------------------------------------------------


def test_a_relative_schema_file_resolves_against_rootdir(tmp_path: Path) -> None:
    """DECISIONS 19: the plugin passes ``config.rootpath`` as ``base_dir``."""
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "answer.yaml").write_text(
        "type: object\nrequired: [ok]\n", encoding="utf-8"
    )
    case = make_case(assertions=[{"type": "schema_valid", "schema_file": "schemas/answer.yaml"}])
    probatio, _ = make_probatio(tmp_path)
    assert probatio.check(case, lambda _: '{"ok": true}').passed is True


def test_the_validation_directory_sits_under_rootdir(tmp_path: Path) -> None:
    assert settings(tmp_path).validation_dir == tmp_path / ".probatio" / "judges"


def test_a_relation_applied_by_hand_without_an_instance_is_refused() -> None:
    from probatio.plugin import _relations

    class Node:
        def iter_markers(self, name: str) -> list[Any]:
            return [getattr(pytest.mark, name)("not a relation").mark]

    with pytest.raises(ProbatioConfigError, match="one Relation instance"):
        _relations(Node())  # type: ignore[arg-type]


def test_the_representative_run_falls_back_to_the_first_when_none_agrees() -> None:
    """Defensive: a majority verdict is always one of the runs, so this cannot happen in check."""
    from probatio.session import _representative

    assert _representative([True, True], reported=False) == 0
    assert _representative([False, True], reported=True) == 1


def test_no_failed_assertion_produces_no_explanation_lines() -> None:
    """Defensive: reached only when a case failed on a budget or a snapshot and no assertion."""
    from probatio.assertions import AssertionResult
    from probatio.session import _failed_assertion_lines

    passing = [AssertionResult(assertion_type="contains", passed=True, score=1.0, detail="fine")]
    assert _failed_assertion_lines([passing]) == []


# -- the cassette context covers the judge and the variants (DECISIONS 90) -----------------------


JUDGE_REPLY = '{"verdict": "pass", "score": 1.0, "rationale": "every claim is supported."}'
"""A reply the strict judge parser accepts, so a graded case is graded and not a parse error."""


def judged_case() -> LLMCase:
    """A case with one exact assertion and one judge assertion, as the live suite's cases have."""
    return make_case(
        assertions=[
            {"type": "contains", "any": [KEYWORD]},
            {"type": "judge", "rubric": "faithfulness", "threshold": 1.0},
        ]
    )


def rubric_dir(tmp_path: Path) -> Path:
    """A directory holding one rubric, for a judge that has to resolve a name."""
    rubrics = tmp_path / "rubrics"
    rubrics.mkdir(parents=True, exist_ok=True)
    (rubrics / "faithfulness.md").write_text("Grade grounding.\n", encoding="utf-8")
    return rubrics


def taped_probatio(
    tmp_path: Path, mode: str, relations: Sequence[Relation] = ()
) -> tuple[Probatio, RunState, FakeProvider, FakeProvider, CassetteProvider]:
    """A ``Probatio`` whose system under test and judge both go through one cassette store."""
    store = CassetteStore(tmp_path / "tapes")
    state = RunState(store=store)
    inner_sut = answering()
    inner_judge = FakeProvider(default=JUDGE_REPLY)
    sut_provider = CassetteProvider(inner_sut, store, mode)
    judge = CassetteProvider(inner_judge, store, mode)
    probatio = Probatio(
        settings=settings(tmp_path),
        state=state,
        suite="test_suite",
        judge_provider=judge,
        relations=relations,
        rubric_dirs=[rubric_dir(tmp_path)],
    )
    return probatio, state, inner_sut, inner_judge, sut_provider


def tape(tmp_path: Path) -> dict[str, Any]:
    """The one cassette file the case wrote."""
    import json

    return dict(
        json.loads((tmp_path / "tapes" / "test_suite" / "copd.json").read_text(encoding="utf-8"))
    )


def test_a_judge_call_is_recorded_onto_the_cases_own_tape(tmp_path: Path) -> None:
    """The judge is a provider call and it belongs to the case that was being graded.

    Before this was fixed the cassette context was closed as soon as the system under test
    returned, so the judge's call reached the store with no active case and every judged suite
    under ``--cassette=record`` died on ``a cassette call was made outside a case``.
    """
    probatio, _, inner_sut, inner_judge, provider = taped_probatio(tmp_path, "record")
    result = probatio.check(judged_case(), sut_for(provider))

    assert [item.assertion_type for item in result.results] == ["contains", "judge"]
    assert [item.passed for item in result.results] == [True, True]
    assert inner_sut.call_count == 1
    assert inner_judge.call_count == 1
    assert len(tape(tmp_path)["interactions"]) == 2, "the judge's call is missing from the tape"


def test_a_variants_calls_are_recorded_onto_the_original_cases_tape(tmp_path: Path) -> None:
    """A relation's variants key differently but file under the case they were taken from."""
    relation = OrderInvariant(field="input.documents", k=3)
    probatio, _, inner_sut, inner_judge, provider = taped_probatio(
        tmp_path, "record", relations=[relation]
    )
    result = probatio.check(judged_case(), sut_for(provider))

    measured = next(item for item in result.relations if item.relation == "order_invariant")
    assert measured.n_variants == 1, "a two-document list has exactly one non-identity ordering"
    assert inner_sut.call_count == 1 + measured.n_variants
    assert inner_judge.call_count == 1 + measured.n_variants

    recorded = tape(tmp_path)
    assert recorded["case_id"] == "copd"
    assert len(recorded["interactions"]) == 2 * (1 + measured.n_variants)
    assert len({interaction["key"] for interaction in recorded["interactions"]}) == len(
        recorded["interactions"]
    ), "two different calls were filed under one key"


def test_a_judged_suite_with_relations_replays_with_no_inner_call(tmp_path: Path) -> None:
    """The whole point: record once against a model, replay for ever at no cost."""
    relations = [OrderInvariant(field="input.documents", k=3), FormatJitter(field="input.question")]
    recorder, _, _, _, provider = taped_probatio(tmp_path, "record", relations=relations)
    recorded = recorder.check(judged_case(), sut_for(provider))

    player, _, inner_sut, inner_judge, replay = taped_probatio(
        tmp_path, "replay", relations=relations
    )
    replayed = player.check(judged_case(), sut_for(replay))

    assert inner_sut.call_count == 0
    assert inner_judge.call_count == 0
    assert [item.passed for item in replayed.results] == [item.passed for item in recorded.results]
    assert {item.relation: item.violation_rate for item in replayed.relations} == {
        item.relation: item.violation_rate for item in recorded.relations
    }
