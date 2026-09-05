"""The markdown reporter: the same report as GitHub-flavoured tables.

It writes to ``$GITHUB_STEP_SUMMARY`` when the environment sets one, which is what puts the
report on a pull request without anybody configuring anything, and to ``--probatio-report PATH``
when a path is given. Both may happen in one run, and each destination is written once.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from ..collector import RunReport
from .tables import Table, cases_table, cost_lines, relations_table, stability_lines

__all__ = ["GITHUB_SUMMARY_ENV", "render_markdown", "write_markdown"]

GITHUB_SUMMARY_ENV: Final = "GITHUB_STEP_SUMMARY"
"""The environment variable GitHub Actions sets to the job summary file."""

_HEADING: Final = "## probatio"
"""The section heading, at depth two so it nests under a job summary's own title."""


def _escape(cell: str) -> str:
    """Escape the one character that would break a markdown table cell."""
    return cell.replace("|", "\\|")


def _draw(table: Table) -> list[str]:
    """Render one table as a GitHub-flavoured markdown table under a bold caption."""
    if not table:
        return []
    lines = [f"**{table.title}**", ""]
    lines.append("| " + " | ".join(_escape(cell) for cell in table.header) + " |")
    lines.append("|" + "|".join(" --- " for _ in table.header) + "|")
    lines += ["| " + " | ".join(_escape(str(cell)) for cell in row) + " |" for row in table.rows]
    lines.append("")
    return lines


def render_markdown(report: RunReport) -> str:
    """Render the whole report as GitHub-flavoured markdown.

    Args:
        report: The finished run.

    Returns:
        The document, ending in one newline. A session that checked no case renders a single
        line saying so rather than an empty file, because an empty job summary reads as a
        reporter that failed.
    """
    if not report.cases:
        return f"{_HEADING}\n\nNo Probatio cases ran in this session.\n"
    lines = [_HEADING, ""]
    lines += _draw(cases_table(report))
    lines += _draw(relations_table(report))
    lines += [f"- {line}" for line in stability_lines(report)]
    lines += [f"- {line}" for line in cost_lines(report)]
    lines += _warning_lines(report.warnings)
    return "\n".join(lines).rstrip("\n") + "\n"


def _warning_lines(warnings: Sequence[str]) -> list[str]:
    """Render the warnings block, or nothing when the run had none."""
    if not warnings:
        return []
    return ["", f"**warnings ({len(warnings)})**", "", *[f"- {w}" for w in warnings]]


def write_markdown(
    report: RunReport, *, path: Path | None = None, environ: dict[str, str] | None = None
) -> list[Path]:
    """Write the markdown report to every destination this run has.

    Args:
        report: The finished run.
        path: The ``--probatio-report`` path, or ``None``.
        environ: The environment to read :data:`GITHUB_SUMMARY_ENV` from. Defaults to
            ``os.environ``; tests pass their own rather than mutating the process's.

    Returns:
        The paths written, in the order they were written, with duplicates removed — so a run
        whose ``--probatio-report`` happens to be the job summary writes it once.
    """
    env = os.environ if environ is None else environ
    destinations: list[Path] = []
    for candidate in (path, Path(env[GITHUB_SUMMARY_ENV]) if env.get(GITHUB_SUMMARY_ENV) else None):
        if candidate is not None and candidate not in destinations:
            destinations.append(candidate)
    document = render_markdown(report)
    for destination in destinations:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(document, encoding="utf-8")
    return destinations
