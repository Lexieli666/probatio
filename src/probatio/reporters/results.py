"""The results reporter: the whole :class:`~probatio.collector.RunReport` as one JSON file.

Spec §3.11 says the case study and the docs quote from this file, so the guarantee it has to
offer is not "readable" but **exact**: what is written parses back into an equal ``RunReport``,
with no field flattened, rounded or dropped on the way. That is why the payload is
``model_dump(mode="json")`` of the report itself rather than a hand-written projection of it —
a projection is a second schema to keep in step with the first, and the first one changes every
time a phase adds a field.

It is written through :func:`~probatio.artefacts.write_json`, the same writer the baselines,
the cassettes and the judge validation records use: sorted keys, indent two, one trailing
newline. A results file that a run re-produced unchanged therefore shows no diff.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..artefacts import write_json
from ..collector import RunReport

__all__ = ["read_results", "render_results", "write_results"]


def render_results(report: RunReport) -> dict[str, Any]:
    """Render the report as the JSON-compatible mapping the results file holds.

    Args:
        report: The finished run.

    Returns:
        ``report.model_dump(mode="json")``: every field of the report, its cases, their assertion
        results, snapshots, stability statistics and relation results included.
    """
    return report.model_dump(mode="json")


def write_results(report: RunReport, path: Path) -> Path:
    """Write the results JSON.

    Args:
        report: The finished run.
        path: Where to write it. Parent directories are created.

    Returns:
        The path written, so the caller can report it.
    """
    return write_json(path, render_results(report))


def read_results(path: Path) -> RunReport:
    """Read a results file back into a report.

    This is the round-trip spec §3.11 asks for, in one place rather than in every caller that
    wants it: the case study, the docs and this repository's own tests all read a committed
    results file this way.

    Args:
        path: The file :func:`write_results` wrote.

    Returns:
        The :class:`~probatio.collector.RunReport` it holds, equal to the one written.
    """
    return RunReport.model_validate(json.loads(path.read_text(encoding="utf-8")))
