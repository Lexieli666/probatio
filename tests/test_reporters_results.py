"""Phase 10: the results JSON, whose whole promise is that it round-trips exactly.

Spec §3.11 says the case study and the docs quote from this file, so a field that was flattened
or a float that was rounded on the way out is a number in a document that no run produced. The
tests here build the richest report the collector can make — a failing case, a flaky one, a
snapshot, budget results, relation flips, warnings and a cost ceiling — and assert that reading
the file back gives an equal :class:`~probatio.collector.RunReport`.
"""

from __future__ import annotations

import json
from pathlib import Path

from probatio import AssertionResult
from probatio.artefacts import JSON_INDENT
from probatio.budget import SuiteBudget
from probatio.collector import CaseResult, RunReport, RunState
from probatio.metamorphic import Flip, RelationResult
from probatio.reporters import read_results, render_results, write_results
from probatio.snapshot import SnapshotResult
from probatio.stability import FlakyTolerance, case_stability


def rich_report() -> RunReport:
    """Build a report using every field a case can carry."""
    state = RunState(runs=5, budget=SuiteBudget(0.05))
    state.record(
        CaseResult(
            case_id="htn-definition",
            node_id="test_demo.py::test_case[htn-definition]",
            suite="test_demo",
            verdict=True,
            passed=True,
            results=[
                AssertionResult(
                    assertion_type="contains", passed=True, score=1.0, detail="matched 2 of 2"
                ),
                AssertionResult(
                    assertion_type="judge",
                    passed=True,
                    score=1.0,
                    detail="has not been validated",
                    unenforceable=True,
                ),
            ],
            budget_results=[
                AssertionResult(
                    assertion_type="budget_latency", passed=True, score=None, detail="100 <= 5000"
                )
            ],
            cost_usd=0.0005,
            latency_ms=100.0,
            model="fake-1",
            snapshot=SnapshotResult(
                case_id="htn-definition",
                mode="scores",
                state="unchanged",
                passed=True,
                detail="no drift",
                path=".probatio/baseline/test_demo/htn-definition.json",
            ),
            stability=case_stability([True] * 5),
            relations=[
                RelationResult(
                    relation="format_jitter",
                    case_id="htn-definition",
                    n_variants=3,
                    n_violations=1,
                    violation_rate=1 / 3,
                    flips=[
                        Flip(
                            label="casing",
                            original_verdict=True,
                            variant_verdict=False,
                            changed_assertions=["contains", "similarity"],
                        )
                    ],
                )
            ],
            tags=["general_health", "paraphrase"],
        )
    )
    state.record(
        CaseResult(
            case_id="anxiety-expected-fail",
            node_id="test_demo.py::test_expected_fail[anxiety-expected-fail]",
            suite="test_demo",
            verdict=False,
            passed=False,
            results=[
                AssertionResult(
                    assertion_type="contains", passed=False, score=0.0, detail="none appeared"
                )
            ],
            cost_usd=None,
            latency_ms=20.0,
            stability=case_stability(
                [False, True, False, False, False], tolerance=FlakyTolerance(p=0.8, n=5)
            ),
            tags=["expected-fail"],
            failure="anxiety-expected-fail: verdict failed\n  contains: none appeared",
        )
    )
    state.warn("htn-definition: 1 judge verdict(s) from a rubric with no validation record")
    state.budget.record("htn-definition", 0.0005)
    state.budget.record("anxiety-expected-fail", None)
    return state.report()


# -- the round trip ------------------------------------------------------------------------------


def test_the_results_json_round_trips_through_model_validate(tmp_path: Path) -> None:
    """Spec §3.11 acceptance: the results JSON round-trips through ``RunReport.model_validate``."""
    report = rich_report()
    path = write_results(report, tmp_path / "r.json")
    assert RunReport.model_validate(json.loads(path.read_text(encoding="utf-8"))) == report


def test_read_results_is_the_same_round_trip_in_one_call(tmp_path: Path) -> None:
    report = rich_report()
    assert read_results(write_results(report, tmp_path / "r.json")) == report


def test_an_empty_session_round_trips_too(tmp_path: Path) -> None:
    report = RunState().report()
    assert read_results(write_results(report, tmp_path / "r.json")) == report
    assert report.cases == []


def test_a_run_with_no_priced_call_writes_a_null_total_and_reads_it_back(tmp_path: Path) -> None:
    """The unpriced total is ``null`` in the file, so no consumer can read it as free."""
    report = rich_report()
    assert report.cost_total_usd is not None
    unpriced = report.model_copy(update={"cost_total_usd": None})
    path = write_results(unpriced, tmp_path / "r.json")
    assert '"cost_total_usd": null' in path.read_text(encoding="utf-8")
    assert read_results(path) == unpriced


def test_a_partly_priced_report_keeps_its_float_total(tmp_path: Path) -> None:
    report = rich_report()
    assert report.cost_unknown_case_ids == ["anxiety-expected-fail"]
    assert read_results(write_results(report, tmp_path / "r.json")).cost_total_usd == (
        report.cost_total_usd
    )


def test_every_field_of_the_report_reaches_the_file() -> None:
    report = rich_report()
    payload = render_results(report)
    assert set(payload) == set(RunReport.model_fields)
    case = payload["cases"][0]
    assert set(case) == set(CaseResult.model_fields)
    assert case["node_id"] == "test_demo.py::test_case[htn-definition]"
    assert case["snapshot"]["state"] == "unchanged"
    assert case["relations"][0]["flips"][0]["changed_assertions"] == ["contains", "similarity"]


def test_a_derived_property_is_not_written_as_a_field() -> None:
    """``n_failed`` is computed from the cases; a stored copy could disagree with them."""
    assert "n_failed" not in render_results(rich_report())
    assert rich_report().n_failed == 1


def test_the_unrounded_rates_survive_the_file() -> None:
    report = rich_report()
    payload = render_results(report)
    assert payload["cases"][0]["relations"][0]["violation_rate"] == 1 / 3
    assert payload["cases"][0]["stability"]["wilson_low"] == report.cases[0].stability.wilson_low


# -- how the file is written ---------------------------------------------------------------


def test_the_file_is_written_the_way_every_other_artefact_is(tmp_path: Path) -> None:
    """Requirement 1: sorted keys, indent, trailing newline, through ``artefacts.write_json``."""
    text = write_results(rich_report(), tmp_path / "r.json").read_text(encoding="utf-8")
    assert text.endswith("}\n")
    assert not text.endswith("}\n\n")
    lines = text.splitlines()
    assert lines[1].startswith(" " * JSON_INDENT)
    top_level = [line.split('"')[1] for line in lines if line.startswith(" " * JSON_INDENT + '"')]
    assert top_level == sorted(top_level)


def test_writing_the_same_report_twice_gives_the_same_bytes(tmp_path: Path) -> None:
    report = rich_report()
    first = write_results(report, tmp_path / "a.json").read_text(encoding="utf-8")
    second = write_results(report, tmp_path / "b.json").read_text(encoding="utf-8")
    assert first == second


def test_write_results_creates_the_directory_and_returns_the_path(tmp_path: Path) -> None:
    destination = tmp_path / "build" / "artifacts" / "results.json"
    assert write_results(rich_report(), destination) == destination
    assert destination.exists()
