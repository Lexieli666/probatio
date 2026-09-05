"""Reporters: one :class:`~probatio.collector.RunReport`, rendered wherever it is wanted.

Four of them ship. Two a developer sees without asking: the terminal section pytest prints at the
end of every run, and the GitHub-flavoured markdown that lands in a job summary. Two more are
written where a flag names a file: JUnit XML for whatever is reading the build, and the results
JSON the case study and the docs quote from. Every one of them renders the same
:class:`~probatio.collector.RunReport`, so a number in a CI dashboard and a number in a terminal
cannot disagree.
"""

from __future__ import annotations

from .junit import SUITE_NAME, render_junit, write_junit
from .markdown import GITHUB_SUMMARY_ENV, render_markdown, write_markdown
from .results import read_results, render_results, write_results
from .tables import NOT_MEASURED, Table, cases_table, cost_lines, relations_table, stability_lines
from .terminal import SECTION_TITLE, render_terminal

__all__ = [
    "GITHUB_SUMMARY_ENV",
    "NOT_MEASURED",
    "SECTION_TITLE",
    "SUITE_NAME",
    "Table",
    "cases_table",
    "cost_lines",
    "read_results",
    "relations_table",
    "render_junit",
    "render_markdown",
    "render_results",
    "render_terminal",
    "stability_lines",
    "write_junit",
    "write_markdown",
    "write_results",
]
