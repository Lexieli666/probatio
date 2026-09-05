"""The terminal reporter: a ``probatio`` section in pytest's own summary.

This is the report a developer actually reads, so it is plain ASCII with no colour and no box
drawing: it survives a CI log, a copy into a pull request and a paste into a README, which is what
spec §7 asks a committed run to be good for.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from ..collector import RunReport
from .tables import Table, cases_table, cost_lines, relations_table, stability_lines

__all__ = ["SECTION_TITLE", "render_terminal"]

SECTION_TITLE: Final = "probatio"
"""The heading ``pytest_terminal_summary`` writes the section under."""

_GUTTER: Final = "  "
"""What separates two columns; two spaces, so a narrow terminal wraps rather than truncates."""


def _widths(table: Table) -> list[int]:
    """Return the width of each column: the longest cell in it, header included."""
    return [
        max(len(str(row[index])) for row in [table.header, *table.rows])
        for index in range(len(table.header))
    ]


def _draw(table: Table) -> list[str]:
    """Render one table as a heading, an aligned header, a rule, and the rows."""
    if not table:
        return []
    widths = _widths(table)
    lines = [f"{table.title}:"]
    for row in [table.header, None, *table.rows]:
        if row is None:
            lines.append(_GUTTER.join("-" * width for width in widths))
            continue
        lines.append(
            _GUTTER.join(
                cell.ljust(width) for cell, width in zip(row, widths, strict=True)
            ).rstrip()
        )
    return [f"  {line}" if index else line for index, line in enumerate(lines)]


def render_terminal(report: RunReport) -> list[str]:
    """Render the whole ``probatio`` section as terminal lines.

    Args:
        report: The finished run.

    Returns:
        The lines to write, without a trailing newline on any of them. An empty list when the
        session checked no case at all, so a suite that does not use Probatio prints nothing.
    """
    if not report.cases:
        return []
    lines: list[str] = []
    lines += _draw(cases_table(report))
    relations = relations_table(report)
    if relations:
        lines.append("")
        lines += _draw(relations)
    lines.append("")
    lines += stability_lines(report)
    lines += cost_lines(report)
    lines += _warning_lines(report.warnings)
    return lines


def _warning_lines(warnings: Sequence[str]) -> list[str]:
    """Render the warnings block, or nothing when the run had none."""
    if not warnings:
        return []
    lines = ["", f"warnings ({len(warnings)}):"]
    lines += [f"  - {warning}" for warning in warnings]
    return lines
