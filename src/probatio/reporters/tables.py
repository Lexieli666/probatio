"""The rows every reporter prints, worked out once so two renderers cannot disagree.

The terminal reporter and the markdown reporter show the same thing in two syntaxes. Rather than
formatting a :class:`~probatio.collector.RunReport` twice, each section is built here as a header
and a list of rows of plain strings, and each reporter only decides how to draw a table.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from ..collector import CaseResult, RunReport

__all__ = [
    "NOT_MEASURED",
    "Table",
    "cases_table",
    "cost_lines",
    "relations_table",
    "stability_lines",
]

NOT_MEASURED: Final = "n/a"
"""What a cell says when the run measured nothing, rather than printing a zero (DECISIONS 8)."""

_RATE_DECIMALS: Final = 2
"""How many decimals a pass rate, a Wilson bound and a violation rate are printed to."""

_MONEY_DECIMALS: Final = 6
"""How many decimals a cost is printed to; a hundredth of a cent, as `budget.py` uses."""


class Table:
    """One report section: a title, a header row and the rows under it.

    Attributes:
        title: The section heading.
        header: The column names.
        rows: The rows, each as long as ``header``.
    """

    __slots__ = ("header", "rows", "title")

    def __init__(self, title: str, header: Sequence[str], rows: Sequence[Sequence[str]]) -> None:
        """Build a section.

        Args:
            title: The section heading.
            header: The column names.
            rows: The rows.
        """
        self.title = title
        self.header = list(header)
        self.rows = [list(row) for row in rows]

    def __bool__(self) -> bool:
        """Report whether the section has any rows, so a reporter can skip an empty one."""
        return bool(self.rows)


def _rate(value: float | None) -> str:
    """Render a rate in [0, 1], or :data:`NOT_MEASURED` when there is none."""
    return NOT_MEASURED if value is None else f"{value:.{_RATE_DECIMALS}f}"


def _money(value: float | None) -> str:
    """Render a cost in dollars, or :data:`NOT_MEASURED` when no call was priced."""
    return NOT_MEASURED if value is None else f"${value:.{_MONEY_DECIMALS}f}"


def _snapshot(case: CaseResult) -> str:
    """Render a case's snapshot state, or a dash for a case that does not use one."""
    return case.snapshot.state if case.snapshot is not None else "-"


def cases_table(report: RunReport) -> Table:
    """Build the cases table.

    Args:
        report: The finished run.

    Returns:
        One row per case. The pass-rate and interval columns appear only when some case ran more
        than once, so a single-run suite is not given three columns of ``1.00`` and ``[0.34,
        1.00]`` that say nothing about stability.
    """
    repeated = any(case.stability.runs > 1 for case in report.cases)
    header = ["case", "verdict", "assertions"]
    if repeated:
        header += ["pass rate", "95% Wilson", "floor"]
    header += ["cost", "latency ms", "snapshot"]

    rows: list[list[str]] = []
    for case in report.cases:
        failed = sum(1 for result in case.results if not result.passed)
        row = [
            case.case_id,
            "pass" if case.passed else "FAIL",
            f"{len(case.results) - failed}/{len(case.results)}",
        ]
        if repeated:
            row += [
                _rate(case.stability.pass_rate),
                f"[{case.stability.wilson_low:.2f}, {case.stability.wilson_high:.2f}]",
                _rate(case.stability.floor),
            ]
        row += [_money(case.cost_usd), f"{case.latency_ms:.0f}", _snapshot(case)]
        rows.append(row)
    return Table("cases", header, rows)


def relations_table(report: RunReport) -> Table:
    """Build the relations table.

    Args:
        report: The finished run.

    Returns:
        One row per relation: how many cases it measured, how many it did not apply to, the mean
        violation rate over the measured ones, and the worst case.
    """
    rows = [
        [
            summary.relation,
            str(summary.n_cases),
            str(summary.n_not_applicable),
            f"{summary.n_violations}/{summary.n_variants}",
            _rate(summary.mean_violation_rate),
            summary.worst_case_id or NOT_MEASURED,
            _rate(summary.worst_violation_rate),
        ]
        for summary in report.relations
    ]
    header = ["relation", "cases", "n/a", "violations", "mean rate", "worst case", "worst rate"]
    return Table("relations", header, rows)


def stability_lines(report: RunReport) -> list[str]:
    """Build the stability summary.

    Args:
        report: The finished run.

    Returns:
        One or two lines. A suite in which no case ran more than once says so instead of quoting
        a score it did not measure.
    """
    stability = report.stability
    if stability.stability_score is None:
        return [f"stability: not measured (no case ran more than once; --runs was {report.runs})"]
    return [
        f"stability score: {stability.stability_score:.{_RATE_DECIMALS}f} "
        f"over {stability.n_repeated_cases} repeated case(s)",
        f"cases whose Wilson lower bound is below their floor: "
        f"{stability.n_below_floor} of {stability.n_repeated_cases}",
    ]


def cost_lines(report: RunReport) -> list[str]:
    """Build the cost summary.

    Args:
        report: The finished run.

    Returns:
        One line naming the total and the ceiling, plus a second naming the cases whose cost
        could not be totalled, so the figure is never read as complete when it is not.
    """
    ceiling = (
        f" of a {_money(report.cost_ceiling_usd)} ceiling"
        if report.cost_ceiling_usd is not None
        else " (no --max-cost ceiling)"
    )
    lines = [f"cost: {_money(report.cost_total_usd)}{ceiling}"]
    if report.cost_unknown_case_ids:
        unknown = ", ".join(report.cost_unknown_case_ids)
        lines.append(f"cost is a lower bound: no price for {unknown}")
    return lines
