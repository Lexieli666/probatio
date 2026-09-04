"""Phase 6: price tables, per-case ceilings, the unenforceable rule, the suite total (spec §3.7).

Every provider here is a fake or a hand-built `Completion`: pricing is arithmetic over token
counts, and nothing in this module needs a model to produce them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from probatio import AssertionResult, Completion, FakeProvider, LLMCase, ProbatioConfigError
from probatio.budget import (
    COST_ASSERTION,
    COST_FLAG,
    LATENCY_ASSERTION,
    NO_CALLS,
    PRICES_FLAG,
    TOKENS_PER_MTOK,
    TOP_CASES,
    ModelPrice,
    PriceTable,
    SuiteBudget,
    case_cost,
    evaluate_budget,
    price_completions,
)
from probatio.errors import BudgetExceededError

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO = REPO_ROOT / "examples" / "demo_suite"
EXAMPLE_PRICES = REPO_ROOT / "examples" / "prices.example.yaml"

MODEL = "claude-opus-5"
# A price table with round numbers, so every expected cost below is arithmetic a reader can do.
PRICES = PriceTable({MODEL: ModelPrice(input_per_mtok=10.0, output_per_mtok=100.0)})


def completion(
    *,
    model: str = MODEL,
    tokens: tuple[int | None, int | None] = (1000, 100),
    cost_usd: float | None = None,
    latency_ms: float = 0.0,
) -> Completion:
    """One call: `tokens` and `cost_usd` are what a budget is computed from."""
    return Completion(
        text="an answer",
        model=model,
        tokens_in=tokens[0],
        tokens_out=tokens[1],
        cost_usd=cost_usd,
        latency_ms=latency_ms,
    )


def case(
    *,
    case_id: str = "a-case",
    max_cost_usd: float | None = None,
    max_latency_ms: float | None = None,
) -> LLMCase:
    """A minimal case carrying only the ceilings a test is about."""
    budget: dict[str, float] = {}
    if max_cost_usd is not None:
        budget["max_cost_usd"] = max_cost_usd
    if max_latency_ms is not None:
        budget["max_latency_ms"] = max_latency_ms
    return LLMCase.model_validate(
        {
            "id": case_id,
            "input": "a question",
            "assertions": [{"type": "contains", "all": ["answer"]}],
            "budget": budget,
        }
    )


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "prices.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def by_type(results: list[AssertionResult], assertion_type: str) -> AssertionResult:
    return next(result for result in results if result.assertion_type == assertion_type)


# --- ModelPrice and PriceTable ------------------------------------------------------------------


def test_a_price_is_dollars_per_million_tokens() -> None:
    price = ModelPrice(input_per_mtok=3.0, output_per_mtok=15.0)
    assert price.cost(TOKENS_PER_MTOK, TOKENS_PER_MTOK) == pytest.approx(18.0)
    assert price.cost(1000, 100) == pytest.approx(3.0 * 1e-3 + 15.0 * 1e-4)
    assert price.cost(0, 0) == 0.0


def test_a_table_loads_a_mapping_of_model_to_prices(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "claude-opus-5:\n"
        "  input_per_mtok: 15\n"
        "  output_per_mtok: 75.0\n"
        "claude-haiku-4-5: {input_per_mtok: 1, output_per_mtok: 5}\n",
    )
    table = PriceTable.load(path)
    assert len(table) == 2
    assert table.models == ["claude-haiku-4-5", "claude-opus-5"]
    assert "claude-opus-5" in table and "claude-sonnet-5" not in table
    assert table.prices["claude-opus-5"] == ModelPrice(input_per_mtok=15.0, output_per_mtok=75.0)
    assert table.source == path
    assert "prices.yaml" in repr(table)


def test_a_free_model_is_a_price_of_zero_and_not_a_missing_price(tmp_path: Path) -> None:
    table = PriceTable.load(write(tmp_path, "free-1: {input_per_mtok: 0, output_per_mtok: 0.0}\n"))
    assert table.price(completion(model="free-1")) == 0.0


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("claude-opus-5: {input_per_mtok: -1, output_per_mtok: 5}", "greater than or equal to 0"),
        ("claude-opus-5: {input_per_mtok: '3.0', output_per_mtok: 5}", "must be a number"),
        ("claude-opus-5: {input_per_mtok: true, output_per_mtok: 5}", "must be a number"),
        ("claude-opus-5: {input_per_mtok: 3.0}", "output_per_mtok: Field required"),
        (
            "claude-opus-5: {inputs_per_mtok: 3.0, output_per_mtok: 5}",
            "Extra inputs are not permitted",
        ),
        ("claude-opus-5: 3.0", "but a price is a mapping"),
        ("claude-opus-5: [3.0, 5.0]", "but a price is a mapping"),
    ],
)
def test_an_unusable_price_names_the_file_and_the_model(
    tmp_path: Path, text: str, expected: str
) -> None:
    path = write(tmp_path, text + "\n")
    with pytest.raises(ProbatioConfigError) as caught:
        PriceTable.load(path)
    assert str(path) in str(caught.value)
    assert "'claude-opus-5'" in str(caught.value)
    assert expected in str(caught.value)


def test_a_thoroughly_wrong_entry_lists_three_complaints_and_counts_the_rest(
    tmp_path: Path,
) -> None:
    path = write(tmp_path, "claude-opus-5: {a: 1, b: 2, c: 3}\n")
    with pytest.raises(ProbatioConfigError) as caught:
        PriceTable.load(path)
    message = str(caught.value)
    assert message.count("Extra inputs are not permitted") + message.count("Field required") == 3
    assert message.endswith("and 2 more")


def test_a_table_that_is_not_a_mapping_of_models_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ProbatioConfigError, match="not a list"):
        PriceTable.load(write(tmp_path, "- claude-opus-5\n"))
    with pytest.raises(ProbatioConfigError, match="not usable as a model name"):
        PriceTable.load(write(tmp_path, "3: {input_per_mtok: 1, output_per_mtok: 2}\n"))


def test_invalid_yaml_names_the_file_and_the_line(tmp_path: Path) -> None:
    with pytest.raises(ProbatioConfigError) as caught:
        PriceTable.load(write(tmp_path, "claude-opus-5:\n  input_per_mtok: 1\n bad-indent: 2\n"))
    assert "invalid YAML at line 3" in str(caught.value)


def test_a_missing_price_file_says_so(tmp_path: Path) -> None:
    with pytest.raises(ProbatioConfigError, match="cannot be read"):
        PriceTable.load(tmp_path / "absent.yaml")


def test_an_empty_file_is_an_empty_table_and_not_an_error(tmp_path: Path) -> None:
    assert len(PriceTable.load(write(tmp_path, ""))) == 0
    assert len(PriceTable.load(write(tmp_path, "# only a comment\n"))) == 0


def test_a_completion_is_priced_from_its_model_and_its_token_counts() -> None:
    # 1000 prompt tokens at $10/Mtok is $0.01; 100 completion tokens at $100/Mtok is $0.01.
    assert PRICES.price(completion()) == pytest.approx(0.02)


@pytest.mark.parametrize(
    "unpriceable",
    [
        completion(model="a-model-nobody-priced"),
        completion(tokens=(None, 100)),
        completion(tokens=(1000, None)),
        completion(tokens=(None, None)),
    ],
)
def test_pricing_returns_none_rather_than_zero_when_it_cannot_price(
    unpriceable: Completion,
) -> None:
    assert PRICES.price(unpriceable) is None
    assert PRICES.apply(unpriceable).cost_usd is None


def test_a_reported_cost_is_never_overridden_by_the_table() -> None:
    """The Claude CLI's notional total is a reported figure; a price table does not edit it."""
    reported = completion(cost_usd=0.5)
    assert PRICES.apply(reported) is reported
    assert PRICES.apply(reported).cost_usd == 0.5


def test_pricing_applies_only_to_the_unpriced_completions_of_a_sequence() -> None:
    calls = [completion(), completion(cost_usd=0.5), completion(model="unpriced")]
    priced = price_completions(calls, PRICES)
    assert [call.cost_usd for call in priced] == [pytest.approx(0.02), 0.5, None]
    assert priced[1] is calls[1] and priced[2] is calls[2]


def test_without_a_table_the_completions_are_returned_untouched() -> None:
    calls = [completion(), completion(cost_usd=0.5)]
    assert price_completions(calls, None) == calls


def test_a_case_cost_is_the_sum_and_is_unknown_when_any_call_is() -> None:
    assert case_cost([completion(), completion()], PRICES) == pytest.approx(0.04)
    assert case_cost([completion(), completion(model="unpriced")], PRICES) is None
    assert case_cost([completion(cost_usd=0.25), completion(cost_usd=0.25)]) == pytest.approx(0.5)
    assert case_cost([]) is None


# --- the unenforceable rule ---------------------------------------------------------------------


def test_a_cost_ceiling_on_an_unpriced_model_is_unenforceable_and_not_passed() -> None:
    results = evaluate_budget(case(max_cost_usd=0.01), [completion()])
    result = by_type(results, COST_ASSERTION)
    assert result.unenforceable is True
    assert result.passed is False
    assert result.score is None
    assert result.detail.startswith(
        f"cost ceiling for a-case is unenforceable: no price configured for {MODEL}"
    )
    assert PRICES_FLAG in result.detail


def test_one_unpriced_call_among_priced_ones_still_makes_the_ceiling_unenforceable() -> None:
    results = evaluate_budget(
        case(max_cost_usd=1.0),
        [completion(), completion(model="unpriced-1"), completion(model="unpriced-2")],
        prices=PRICES,
    )
    result = by_type(results, COST_ASSERTION)
    assert result.unenforceable is True
    assert result.passed is False
    assert "no price configured for unpriced-1, unpriced-2" in result.detail


def test_the_same_case_with_a_table_that_prices_the_model_is_enforced() -> None:
    """The acceptance criterion: unenforceable without a table, a real comparison with one."""
    calls = [completion(), completion()]
    passing = by_type(
        evaluate_budget(case(max_cost_usd=0.05), calls, prices=PRICES), COST_ASSERTION
    )
    assert (passing.passed, passing.unenforceable) == (True, False)
    assert (
        passing.detail == "cost $0.040000 over 2 provider calls is within the ceiling of $0.050000"
    )

    failing = by_type(
        evaluate_budget(case(max_cost_usd=0.03), calls, prices=PRICES), COST_ASSERTION
    )
    assert (failing.passed, failing.unenforceable) == (False, False)
    assert failing.detail == "cost $0.040000 over 2 provider calls exceeds the ceiling of $0.030000"


def test_a_cost_a_provider_reported_needs_no_table_at_all() -> None:
    provider = FakeProvider(cost_usd=0.0001, latency_ms=20.0)
    calls = [provider.complete("a prompt") for _ in range(3)]
    result = by_type(evaluate_budget(case(max_cost_usd=0.01), calls), COST_ASSERTION)
    assert (result.passed, result.unenforceable) == (True, False)
    assert (
        result.detail == "cost $0.000300 over 3 provider calls is within the ceiling of $0.010000"
    )


def test_a_ceiling_met_exactly_is_met() -> None:
    calls = [completion(cost_usd=0.01), completion(cost_usd=0.02)]
    assert by_type(evaluate_budget(case(max_cost_usd=0.03), calls), COST_ASSERTION).passed is True


def test_a_case_that_recorded_no_calls_has_no_enforceable_ceiling_of_either_kind() -> None:
    """DECISIONS 36: the sum of nothing satisfies every ceiling, so it checks nothing."""
    results = evaluate_budget(case(max_cost_usd=0.01, max_latency_ms=5000.0), [])
    assert [result.assertion_type for result in results] == [COST_ASSERTION, LATENCY_ASSERTION]
    for result in results:
        assert (result.passed, result.unenforceable) == (False, True)
        assert result.score is None
    assert by_type(results, COST_ASSERTION).detail == (
        f"cost ceiling for a-case is unenforceable: {NO_CALLS}"
    )
    assert by_type(results, LATENCY_ASSERTION).detail == (
        f"latency ceiling for a-case is unenforceable: {NO_CALLS}"
    )


def test_the_no_call_detail_names_no_fix_because_no_command_fixes_it() -> None:
    """A missing price is fixed by a flag; a case that called nothing is not."""
    result = by_type(evaluate_budget(case(max_cost_usd=0.01), []), COST_ASSERTION)
    assert "fix it with" not in result.detail
    assert PRICES_FLAG not in result.detail


def test_a_no_call_case_reaches_the_suite_total_as_unknown_rather_than_as_free() -> None:
    suite = SuiteBudget(0.01)
    suite.record("no-calls", case_cost([]))
    suite.record("priced", 0.02)
    assert suite.unknown_case_ids == ["no-calls"]
    assert suite.total_usd == pytest.approx(0.02)
    message = suite.overrun_message()
    assert message is not None
    assert message.endswith("1 case of unknown cost not counted: no-calls")


# --- latency ------------------------------------------------------------------------------------


def test_latency_ceilings_fail_on_the_sum_of_the_calls_a_case_made() -> None:
    provider = FakeProvider(latency_ms=2000.0)
    calls = [provider.complete("a prompt") for _ in range(3)]
    within = by_type(evaluate_budget(case(max_latency_ms=6000.0), calls), LATENCY_ASSERTION)
    assert (within.passed, within.unenforceable) == (True, False)
    assert (
        within.detail
        == "latency 6000.0 ms over 3 provider calls is within the ceiling of 6000.0 ms"
    )

    over = by_type(evaluate_budget(case(max_latency_ms=5000.0), calls), LATENCY_ASSERTION)
    assert (over.passed, over.unenforceable) == (False, False)
    assert over.detail == "latency 6000.0 ms over 3 provider calls exceeds the ceiling of 5000.0 ms"


def test_latency_is_enforceable_even_where_cost_is_not() -> None:
    """Spec §3.7: latency is always enforceable, because the clock always answered."""
    results = evaluate_budget(
        case(max_cost_usd=0.01, max_latency_ms=10.0), [completion(latency_ms=20.0)]
    )
    assert [result.assertion_type for result in results] == [COST_ASSERTION, LATENCY_ASSERTION]
    assert by_type(results, COST_ASSERTION).unenforceable is True
    latency = by_type(results, LATENCY_ASSERTION)
    assert (latency.passed, latency.unenforceable) == (False, False)


def test_the_default_ceiling_applies_only_to_a_case_that_declares_none() -> None:
    calls = [completion(latency_ms=100.0)]
    fallback = by_type(
        evaluate_budget(case(), calls, default_max_latency_ms=50.0), LATENCY_ASSERTION
    )
    assert fallback.passed is False
    assert fallback.detail == (
        "latency 100.0 ms over 1 provider call exceeds the --max-latency ceiling of 50.0 ms"
    )

    declared = by_type(
        evaluate_budget(case(max_latency_ms=200.0), calls, default_max_latency_ms=50.0),
        LATENCY_ASSERTION,
    )
    assert declared.passed is True
    assert "--max-latency" not in declared.detail


def test_a_case_with_no_ceiling_of_a_kind_produces_no_result_of_that_kind() -> None:
    assert evaluate_budget(case(), [completion()]) == []
    assert evaluate_budget(case(), []) == []
    calls = [completion(cost_usd=0.001, latency_ms=1.0)]
    assert [r.assertion_type for r in evaluate_budget(case(max_cost_usd=1.0), calls)] == [
        COST_ASSERTION
    ]
    assert [r.assertion_type for r in evaluate_budget(case(max_latency_ms=1.0), calls)] == [
        LATENCY_ASSERTION
    ]


# --- the suite accumulator ----------------------------------------------------------------------


def test_a_suite_within_its_ceiling_has_no_message() -> None:
    suite = SuiteBudget(0.05)
    suite.record("a", 0.02)
    suite.record("b", 0.03)
    assert suite.total_usd == pytest.approx(0.05)
    assert suite.exceeded is False
    assert suite.overrun_message() is None
    assert suite.overrun_error() is None


def test_a_suite_with_no_ceiling_never_overruns() -> None:
    suite = SuiteBudget()
    suite.record("a", 100.0)
    assert (suite.max_cost_usd, suite.exceeded, suite.overrun_message()) == (None, False, None)


def test_the_overrun_message_names_the_total_the_ceiling_and_the_top_three() -> None:
    suite = SuiteBudget(0.03)
    for case_id, cost in [
        ("cheap", 0.001),
        ("dearest", 0.02),
        ("second", 0.015),
        ("third", 0.01),
    ]:
        suite.record(case_id, cost)
    message = suite.overrun_message()
    assert message is not None
    assert message == (
        "suite cost $0.046000 over 4 cases exceeds the --max-cost ceiling of $0.030000; "
        "most expensive: dearest $0.020000, second $0.015000, third $0.010000"
    )
    assert "\n" not in message
    assert "cheap" not in message
    assert len(suite.most_expensive()) == TOP_CASES
    assert COST_FLAG in message


def test_the_overrun_is_a_budget_exceeded_error_phase_9_can_raise() -> None:
    suite = SuiteBudget(0.01)
    suite.record("a", 0.02)
    error = suite.overrun_error()
    assert isinstance(error, BudgetExceededError)
    assert str(error) == suite.overrun_message()


def test_cases_of_unknown_cost_are_counted_and_named_and_never_zero() -> None:
    suite = SuiteBudget(0.01)
    suite.record("priced", 0.02)
    suite.record("unpriced-a", None)
    suite.record("unpriced-b", None)
    assert suite.total_usd == pytest.approx(0.02)
    assert suite.unknown_case_ids == ["unpriced-a", "unpriced-b"]
    assert suite.known_case_ids == ["priced"]
    assert suite.n_cases == 3
    message = suite.overrun_message()
    assert message is not None
    assert message.endswith("2 cases of unknown cost not counted: unpriced-a, unpriced-b")
    assert "unpriced-a $0.000000" not in message


def test_a_long_unknown_list_stays_one_line() -> None:
    suite = SuiteBudget(0.01)
    suite.record("priced", 0.02)
    for index in range(5):
        suite.record(f"unpriced-{index}", None)
    message = suite.overrun_message()
    assert message is not None
    assert message.endswith(
        "5 cases of unknown cost not counted: unpriced-0, unpriced-1, unpriced-2 and 2 more"
    )
    assert "\n" not in message


def test_recording_a_case_twice_adds_to_that_cases_total() -> None:
    """Five runs of one case under ``--runs 5`` are five lots of spend under one id."""
    suite = SuiteBudget(0.01)
    for _ in range(5):
        suite.record("repeated", 0.004)
    assert suite.total_usd == pytest.approx(0.02)
    assert suite.n_cases == 1
    assert suite.most_expensive() == [("repeated", pytest.approx(0.02))]


def test_ties_are_broken_by_case_id_so_the_line_is_the_same_every_run() -> None:
    suite = SuiteBudget(0.01)
    for case_id in ["c", "a", "b"]:
        suite.record(case_id, 0.01)
    assert [case_id for case_id, _ in suite.most_expensive()] == ["a", "b", "c"]


def test_a_negative_ceiling_and_a_negative_cost_are_configuration_errors() -> None:
    with pytest.raises(ProbatioConfigError, match="cannot be negative"):
        SuiteBudget(-1.0)
    with pytest.raises(ProbatioConfigError, match="cannot cost"):
        SuiteBudget(1.0).record("a", -0.5)


def test_a_total_that_lands_exactly_on_the_ceiling_is_not_an_overrun() -> None:
    """0.1 + 0.2 is 0.30000000000000004 in binary floating point; the ceiling still holds."""
    suite = SuiteBudget(0.3)
    suite.record("a", 0.1)
    suite.record("b", 0.2)
    assert suite.total_usd > 0.3
    assert suite.exceeded is False
    assert suite.overrun_message() is None


# --- examples/prices.example.yaml ---------------------------------------------------------------


def test_the_example_price_file_ships_no_prices_and_loads_as_an_empty_table() -> None:
    table = PriceTable.load(EXAMPLE_PRICES)
    assert len(table) == 0
    assert table.models == []
    text = EXAMPLE_PRICES.read_text(encoding="utf-8")
    assert "VERIFY EVERY NUMBER BEFORE YOU USE IT" in text
    assert "input_per_mtok" in text and "output_per_mtok" in text
    body = [line for line in text.splitlines() if line.strip() and not line.startswith("#")]
    assert body == [], f"the example file must ship no live entries, found {body}"


def test_every_cost_ceiling_in_the_demo_suite_is_unenforceable_against_the_example_file() -> None:
    """The shipped example prices nothing, so it enforces nothing — visibly, not silently."""
    table = PriceTable.load(EXAMPLE_PRICES)
    from probatio import load_cases

    cases = [c for c in load_cases(DEMO / "cases") if c.budget.max_cost_usd is not None]
    assert len(cases) == 10
    for demo_case in cases:
        result = by_type(evaluate_budget(demo_case, [completion()], prices=table), COST_ASSERTION)
        assert result.unenforceable is True
        assert result.passed is False
        assert f"cost ceiling for {demo_case.id} is unenforceable" in result.detail
