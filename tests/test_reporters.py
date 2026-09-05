"""Phase 9: the terminal and markdown reporters, rendering one report two ways."""

from __future__ import annotations

from pathlib import Path

import pytest

from probatio import AssertionResult
from probatio.budget import SuiteBudget
from probatio.collector import CaseResult, RunState
from probatio.metamorphic import RelationResult
from probatio.reporters import (
    GITHUB_SUMMARY_ENV,
    NOT_MEASURED,
    Table,
    cost_lines,
    render_markdown,
    render_terminal,
    stability_lines,
    write_markdown,
)
from probatio.snapshot import SnapshotResult
from probatio.stability import FlakyTolerance, case_stability


def result(kind: str, passed: bool = True) -> AssertionResult:
    return AssertionResult(
        assertion_type=kind, passed=passed, score=1.0 if passed else 0.0, detail="detail"
    )


def case(
    case_id: str,
    *,
    verdicts: tuple[bool, ...] = (True,),
    passed: bool = True,
    results: tuple[AssertionResult, ...] = (),
    cost: float | None = 0.0001,
    snapshot: SnapshotResult | None = None,
    relations: tuple[RelationResult, ...] = (),
    tolerance: FlakyTolerance | None = None,
) -> CaseResult:
    return CaseResult(
        case_id=case_id,
        node_id=f"test_demo.py::test_case[{case_id}]",
        suite="test_demo",
        verdict=all(verdicts),
        passed=passed,
        results=list(results) or [result("contains")],
        cost_usd=cost,
        latency_ms=20.0,
        snapshot=snapshot,
        stability=case_stability(list(verdicts), tolerance=tolerance),
        relations=list(relations),
    )


def report_with(*cases: CaseResult, runs: int = 1, ceiling: float | None = None) -> object:
    budget = SuiteBudget(ceiling)
    state = RunState(runs=runs, budget=budget)
    for item in cases:
        state.record(item)
        budget.record(item.case_id, item.cost_usd)
    return state.report()


# -- the terminal reporter --------------------------------------------------------------------


def test_a_session_that_checked_nothing_prints_nothing() -> None:
    assert render_terminal(report_with()) == []  # type: ignore[arg-type]


def test_a_single_run_suite_gets_no_pass_rate_columns() -> None:
    lines = render_terminal(report_with(case("alpha")))  # type: ignore[arg-type]
    header = next(line for line in lines if "case " in line)
    assert "pass rate" not in header
    assert "95% Wilson" not in header
    assert "verdict" in header and "snapshot" in header


def test_a_repeated_case_adds_the_pass_rate_and_the_interval() -> None:
    lines = render_terminal(  # type: ignore[arg-type]
        report_with(case("alpha", verdicts=(True,) * 5), runs=5)
    )
    header = next(line for line in lines if "case " in line)
    assert "pass rate" in header and "95% Wilson" in header and "floor" in header
    row = next(line for line in lines if "alpha" in line)
    assert "1.00" in row and "[0.57, 1.00]" in row


def test_a_failing_case_is_marked_and_its_assertion_count_shown() -> None:
    lines = render_terminal(  # type: ignore[arg-type]
        report_with(
            case(
                "alpha",
                verdicts=(False,),
                passed=False,
                results=(result("contains", False), result("judge")),
            )
        )
    )
    row = next(line for line in lines if "alpha" in line)
    assert "FAIL" in row and "1/2" in row


def test_a_case_with_no_price_prints_not_measured_rather_than_zero() -> None:
    lines = render_terminal(report_with(case("alpha", cost=None)))  # type: ignore[arg-type]
    assert NOT_MEASURED in next(line for line in lines if "alpha" in line)


def test_the_relations_table_lists_the_not_applicable_count() -> None:
    relations = (
        RelationResult(
            relation="format_jitter",
            case_id="alpha",
            n_variants=3,
            n_violations=1,
            violation_rate=1 / 3,
        ),
    )
    absent = (
        RelationResult(
            relation="format_jitter",
            case_id="bravo",
            n_variants=0,
            n_violations=0,
            violation_rate=None,
        ),
    )
    text = "\n".join(
        render_terminal(  # type: ignore[arg-type]
            report_with(case("alpha", relations=relations), case("bravo", relations=absent))
        )
    )
    assert "relations:" in text
    row = next(line for line in text.splitlines() if "format_jitter" in line)
    assert "1/3" in row and "0.33" in row and "alpha" in row


def test_a_suite_with_no_relations_prints_no_relations_table() -> None:
    assert "relations:" not in "\n".join(
        render_terminal(report_with(case("alpha")))  # type: ignore[arg-type]
    )


def test_the_snapshot_state_is_shown_and_a_case_without_one_shows_a_dash() -> None:
    snapshot = SnapshotResult(
        state="recorded",
        case_id="alpha",
        mode="scores",
        passed=True,
        detail="baseline recorded",
        path=Path("alpha.json"),
    )
    lines = render_terminal(  # type: ignore[arg-type]
        report_with(case("alpha", snapshot=snapshot), case("bravo"))
    )
    assert "recorded" in next(line for line in lines if "alpha" in line)
    assert next(line for line in lines if "bravo" in line).rstrip().endswith("-")


def test_the_warnings_block_is_numbered_and_bulleted() -> None:
    state = RunState()
    state.record(case("alpha"))
    state.warn("no price for fake-1")
    text = "\n".join(render_terminal(state.report()))
    assert "warnings (1):" in text
    assert "  - no price for fake-1" in text


def test_a_run_with_no_warnings_prints_no_warnings_block() -> None:
    assert "warnings" not in "\n".join(
        render_terminal(report_with(case("alpha")))  # type: ignore[arg-type]
    )


# -- the shared sections ----------------------------------------------------------------------


def test_a_suite_run_once_says_stability_was_not_measured() -> None:
    lines = stability_lines(report_with(case("alpha")))  # type: ignore[arg-type]
    assert lines == ["stability: not measured (no case ran more than once; --runs was 1)"]


def test_a_repeated_suite_reports_a_score_and_a_floor_count() -> None:
    lines = stability_lines(  # type: ignore[arg-type]
        report_with(case("alpha", verdicts=(True, True, False, True, True)), runs=5)
    )
    assert "stability score: 0.80 over 1 repeated case(s)" in lines[0]
    assert lines[1].endswith("1 of 1")


def test_the_cost_line_names_the_ceiling_when_there_is_one() -> None:
    assert (
        "of a $0.010000 ceiling"
        in cost_lines(  # type: ignore[arg-type]
            report_with(case("alpha"), ceiling=0.01)
        )[0]
    )


def test_the_cost_line_says_so_when_there_is_no_ceiling() -> None:
    assert "no --max-cost ceiling" in cost_lines(report_with(case("alpha")))[0]  # type: ignore[arg-type]


def test_an_unpriced_case_makes_the_total_a_lower_bound() -> None:
    lines = cost_lines(report_with(case("alpha", cost=None)))  # type: ignore[arg-type]
    assert "lower bound" in lines[1] and "alpha" in lines[1]


def test_an_empty_table_is_falsey_and_draws_nothing() -> None:
    assert not Table("cases", ["a"], [])
    assert Table("cases", ["a"], [["b"]])


# -- the markdown reporter ----------------------------------------------------------------------


def test_the_markdown_report_is_a_github_table_under_a_heading() -> None:
    text = render_markdown(report_with(case("alpha")))  # type: ignore[arg-type]
    assert text.startswith("## probatio\n")
    assert "**cases**" in text
    assert "| case | verdict |" in text
    assert "| --- |" in text
    assert "| alpha | pass |" in text
    assert text.endswith("\n")


def test_the_markdown_report_carries_the_same_sections_as_the_terminal() -> None:
    text = render_markdown(  # type: ignore[arg-type]
        report_with(case("alpha", verdicts=(True,) * 5), runs=5, ceiling=1.0)
    )
    assert "- stability score:" in text
    assert "- cost: $0.000100 of a $1.000000 ceiling" in text


def test_a_pipe_in_a_cell_is_escaped() -> None:
    """No id Probatio produces holds one, but a cell that did would break the table silently."""
    text = render_markdown(report_with(case("alpha|bravo")))  # type: ignore[arg-type]
    assert r"| alpha\|bravo | pass |" in text


def test_a_session_that_checked_nothing_still_writes_a_readable_summary() -> None:
    assert "No Probatio cases ran" in render_markdown(report_with())  # type: ignore[arg-type]


def test_the_warnings_block_is_a_markdown_list() -> None:
    state = RunState()
    state.record(case("alpha"))
    state.warn("no price for fake-1")
    text = render_markdown(state.report())
    assert "**warnings (1)**" in text
    assert "- no price for fake-1" in text


def test_writing_goes_to_the_path_and_to_the_job_summary(tmp_path: Path) -> None:
    report = report_with(case("alpha"))
    summary = tmp_path / "summary.md"
    explicit = tmp_path / "nested" / "report.md"
    written = write_markdown(  # type: ignore[arg-type]
        report, path=explicit, environ={GITHUB_SUMMARY_ENV: str(summary)}
    )
    assert written == [explicit, summary]
    assert explicit.read_text(encoding="utf-8") == summary.read_text(encoding="utf-8")
    assert "## probatio" in summary.read_text(encoding="utf-8")


def test_one_destination_named_twice_is_written_once(tmp_path: Path) -> None:
    target = tmp_path / "one.md"
    written = write_markdown(  # type: ignore[arg-type]
        report_with(case("alpha")), path=target, environ={GITHUB_SUMMARY_ENV: str(target)}
    )
    assert written == [target]


def test_writing_nowhere_writes_nothing() -> None:
    assert write_markdown(report_with(case("alpha")), path=None, environ={}) == []  # type: ignore[arg-type]


def test_an_empty_job_summary_variable_is_not_a_destination() -> None:
    assert (
        write_markdown(  # type: ignore[arg-type]
            report_with(case("alpha")), path=None, environ={GITHUB_SUMMARY_ENV: ""}
        )
        == []
    )


def test_the_process_environment_is_read_when_none_is_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "job.md"
    monkeypatch.setenv(GITHUB_SUMMARY_ENV, str(target))
    assert write_markdown(report_with(case("alpha"))) == [target]  # type: ignore[arg-type]


def test_an_empty_table_draws_no_lines() -> None:
    from probatio.reporters.terminal import _draw

    assert _draw(Table("cases", ["a"], [])) == []
