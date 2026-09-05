"""Phase 11: the Consilium dogfood suite, run offline against its committed tapes.

Everything here runs through ``pytester`` on a copy of ``examples/consilium/``, so a test writes
nothing into the example and the committed baselines are compared rather than re-recorded. Nothing
in this module reads the published traces: they live outside the repository, and the point of the
tapes is that they are no longer needed.

Five things are asserted, and each one is a claim the suite would otherwise only make in prose.

1. **Both suites replay.** Every red-flag case in ``test_baseline`` passes, which is only possible
   if every interaction came off a tape: a key the tape does not hold raises rather than falling
   through to the default fake provider, and the fake's deterministic ``FAKE(...)`` fallback
   carries no escalation phrase and no reference wording, so it fails both assertions at once.
2. **The unenforceable rule fires on real data.** The traces publish token counts, not dollars, so
   without ``--probatio-prices`` all fifteen cost ceilings are unenforceable; a price table that
   prices the one model the traces name leaves none of them so.
3. **The two suites disagree.** ``full`` fails red-flag cases that ``baseline_llm`` passes. That
   difference is Consilium's published regression, reproduced from its own recorded outputs.
4. **The cases are derived, not written.** Re-emitting them from the committed golden subset and
   the committed phrase list reproduces the committed YAML byte for byte.
5. **The golden subset is exactly the case list**, in order, so the emitter has nothing to choose.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path
from types import ModuleType

import pytest

from probatio.reporters import read_results

REPO_ROOT = Path(__file__).resolve().parents[1]
SUITE = REPO_ROOT / "examples" / "consilium"
BASELINES = REPO_ROOT / ".probatio" / "baseline"
PHRASES = Path(__file__).parent / "fixtures" / "consilium" / "escalation_phrases.txt"

CASE_IDS = (SUITE / "CASES.txt").read_text(encoding="utf-8").split()
RED_FLAG_IDS = ("g-su-001", "g-su-002", "g-su-003", "g-md-017", "g-md-018", "g-md-021")

#: A price table for the one model the traces name. Not real prices, and not committed anywhere
#: near ``examples/``: it exists to flip the unenforceable ceilings and prove they can flip.
PRICE_TABLE = "gpt-4o-mini-2024-07-18:\n  input_per_mtok: 0.15\n  output_per_mtok: 0.60\n"


@pytest.fixture
def consilium(pytester: pytest.Pytester) -> Path:
    """A copy of the dogfood suite, with the committed baselines, in a temporary rootdir.

    The baselines are copied in so that a run here compares against the files this phase
    committed: a change that moved any of the thirty recorded score sets would fail as snapshot
    drift rather than pass by re-recording into an empty directory.
    """
    target = pytester.path / "consilium"
    shutil.copytree(SUITE, target, ignore=shutil.ignore_patterns("__pycache__", ".probatio"))
    for suite in ("test_full", "test_baseline"):
        shutil.copytree(BASELINES / suite, pytester.path / ".probatio" / "baseline" / suite)
    return target


def run_suite(pytester: pytest.Pytester, module: str, *extra: str) -> Path:
    """Run one suite in replay against the copied tapes and return its results JSON."""
    results = pytester.path / f"{module}.json"
    pytester.runpytest_subprocess(
        f"consilium/{module}.py",
        "--cassette-dir",
        "consilium/cassettes",
        "--probatio-results",
        str(results),
        *extra,
    )
    assert results.exists(), f"{module} wrote no results file"
    return results


def verdicts(results: Path) -> dict[str, bool]:
    """The per-case verdict a results file records, keyed by case id."""
    return {case.case_id: case.verdict for case in read_results(results).cases}


def converter() -> ModuleType:
    """Import ``convert_traces.py`` from the example as a module of its own."""
    spec = importlib.util.spec_from_file_location("consilium_convert", SUITE / "convert_traces.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# -- (a) both suites replay -----------------------------------------------------------------------


def test_both_suites_replay_and_every_baseline_red_flag_case_passes(
    pytester: pytest.Pytester, consilium: Path
) -> None:
    """The tapes answer every call; the plain baseline escalates on all six red-flag cases."""
    baseline = verdicts(run_suite(pytester, "test_baseline"))
    full = verdicts(run_suite(pytester, "test_full"))

    assert sorted(baseline) == sorted(CASE_IDS)
    assert sorted(full) == sorted(CASE_IDS)
    assert all(baseline.values()), (
        "a case in test_baseline failed; with the default fake provider that can only mean an "
        "interaction was not on its tape"
    )
    assert [case_id for case_id in RED_FLAG_IDS if not baseline[case_id]] == []


def test_the_committed_baselines_are_compared_and_do_not_drift(
    pytester: pytest.Pytester, consilium: Path
) -> None:
    """The thirty committed score sets are the drift check: a run reads them, never rewrites."""
    states = {
        (module, case.case_id): None if case.snapshot is None else case.snapshot.state
        for module in ("test_baseline", "test_full")
        for case in read_results(run_suite(pytester, module)).cases
    }
    assert len(states) == 2 * len(CASE_IDS)
    assert set(states.values()) == {"unchanged"}, sorted(set(states.values()))


def test_replay_reproduces_the_recorded_answers_and_latencies(
    pytester: pytest.Pytester, consilium: Path
) -> None:
    """A case's latency is the trace's ``wall_ms``, which no fake provider could have invented."""
    report = read_results(run_suite(pytester, "test_baseline"))
    tape = json.loads(
        (consilium / "cassettes" / "test_baseline" / "g-su-001.json").read_text(encoding="utf-8")
    )
    recorded = tape["interactions"][0]["completions"][0]
    case = next(case for case in report.cases if case.case_id == "g-su-001")
    assert case.latency_ms == pytest.approx(recorded["latency_ms"])
    assert "FAKE(" not in recorded["text"]


# -- (b) the unenforceable rule -------------------------------------------------------------------


def test_every_cost_ceiling_is_unenforceable_without_a_price_table(
    pytester: pytest.Pytester, consilium: Path
) -> None:
    """Spec §3.7's rule on real data: tokens without dollars is unknown, never free."""
    report = read_results(run_suite(pytester, "test_baseline"))
    ceilings = [
        result
        for case in report.cases
        for result in case.budget_results
        if result.assertion_type == "budget_cost"
    ]
    assert len(ceilings) == len(CASE_IDS)
    assert [result for result in ceilings if not result.unenforceable] == []
    assert [result for result in ceilings if result.passed] == [], (
        "an unenforceable ceiling must not be counted as a passing budget check"
    )


def test_a_price_table_for_the_traced_model_leaves_no_ceiling_unenforceable(
    pytester: pytest.Pytester, consilium: Path
) -> None:
    """The same suite, one flag different.

    The priced run gets a baseline directory of its own: pricing the model flips every
    ``budget_cost`` result from unenforceable to passing, and a ``scores`` baseline holds that
    flag, so comparing against the committed baselines would report drift rather than the thing
    this test is about (DECISIONS 68).
    """
    prices = pytester.path / "prices.yaml"
    prices.write_text(PRICE_TABLE, encoding="utf-8")
    report = read_results(
        run_suite(
            pytester,
            "test_baseline",
            "--probatio-prices",
            str(prices),
            "--baseline-dir",
            "priced-baseline",
        )
    )
    ceilings = [
        result
        for case in report.cases
        for result in case.budget_results
        if result.assertion_type == "budget_cost"
    ]
    assert len(ceilings) == len(CASE_IDS)
    assert [result for result in ceilings if result.unenforceable] == []
    assert all(result.passed for result in ceilings)
    assert all(case.cost_usd is not None for case in report.cases)


# -- (c) the two suites disagree ------------------------------------------------------------------


def test_the_two_suites_differ_on_a_red_flag_case(
    pytester: pytest.Pytester, consilium: Path
) -> None:
    """Consilium's published regression, reproduced from its own traces by two pytest runs."""
    baseline = verdicts(run_suite(pytester, "test_baseline"))
    full = verdicts(run_suite(pytester, "test_full"))

    disagreed = [case_id for case_id in RED_FLAG_IDS if baseline[case_id] != full[case_id]]
    assert disagreed, "the two configurations agreed on every red-flag case"
    assert all(baseline[case_id] and not full[case_id] for case_id in disagreed), (
        "the direction matters: the baseline escalates where the full pipeline does not"
    )
    regular = [case_id for case_id in CASE_IDS if case_id not in RED_FLAG_IDS]
    assert [case_id for case_id in regular if not full[case_id]] == []


# -- (d) the cases are derived, not written -------------------------------------------------------


def test_emit_cases_reproduces_the_committed_cases_byte_for_byte(tmp_path: Path) -> None:
    """The committed YAML is the contract; the emitter is written to match it, not the reverse."""
    cases_file = tmp_path / "CASES.txt"
    status = converter().main(
        [
            "--golden",
            str(SUITE / "golden-subset.jsonl"),
            "--escalation",
            str(PHRASES),
            "--cases",
            str(cases_file),
            "--emit-cases",
        ]
    )
    assert status == 0

    assert cases_file.read_text(encoding="utf-8") == (SUITE / "CASES.txt").read_text(
        encoding="utf-8"
    )
    emitted = sorted((tmp_path / "cases").glob("*.yaml"))
    committed = sorted((SUITE / "cases").glob("*.yaml"))
    assert [path.name for path in emitted] == [path.name for path in committed]
    for produced, expected in zip(emitted, committed, strict=True):
        assert produced.read_bytes() == expected.read_bytes(), expected.name


def test_the_committed_phrase_list_is_the_one_the_red_flag_cases_assert(tmp_path: Path) -> None:
    """The fixture is a copy, so a test has to prove it is still the same copy."""
    import yaml

    phrases = converter().read_escalation_phrases(PHRASES)
    case = yaml.safe_load((SUITE / "cases" / "g-su-001.yaml").read_text(encoding="utf-8"))
    contains = next(a for a in case["assertions"] if a["type"] == "contains")
    assert contains["any"] == phrases
    assert "safety/escalation.py" in case["metadata"]["assertion_source"]


# -- (e) the golden subset is the case list -------------------------------------------------------


def test_the_golden_subset_holds_exactly_the_case_list_in_order() -> None:
    """Otherwise the emitter's selection rule would be choosing from something else."""
    lines = (SUITE / "golden-subset.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["id"] for line in lines if line.strip()] == CASE_IDS
