"""Reporters: one :class:`~probatio.collector.RunReport`, rendered wherever it is wanted.

Phase 9 ships the two a developer sees without asking: the terminal section pytest prints at the
end of every run, and the GitHub-flavoured markdown that lands in a job summary. Phase 10 adds
JUnit XML and the results JSON, and every one of them renders the same object, so a number in a
CI dashboard and a number in a terminal cannot disagree.
"""

from __future__ import annotations

from .markdown import GITHUB_SUMMARY_ENV, render_markdown, write_markdown
from .tables import NOT_MEASURED, Table, cases_table, cost_lines, relations_table, stability_lines
from .terminal import SECTION_TITLE, render_terminal

__all__ = [
    "GITHUB_SUMMARY_ENV",
    "NOT_MEASURED",
    "SECTION_TITLE",
    "Table",
    "cases_table",
    "cost_lines",
    "relations_table",
    "render_markdown",
    "render_terminal",
    "stability_lines",
    "write_markdown",
]
