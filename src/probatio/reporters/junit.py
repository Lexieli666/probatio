"""The JUnit reporter: one ``<testcase>`` per checked case, for whatever CI is reading.

There is no single JUnit XML schema — the format is Ant's, as extended by Surefire and as parsed
by Jenkins, GitLab, GitHub's test reporters and half a dozen others — so what this module targets
is the intersection every one of them reads: a ``<testsuites>`` root, one ``<testsuite>`` with
``name``, ``tests``, ``failures``, ``errors`` and ``time``, and ``<testcase>`` elements with
``classname``, ``name`` and ``time``. Everything Probatio measures beyond pass and fail travels
as ``<property>`` elements, which is the one extension point the format offers.

Three positions are fixed here, each recorded in `DECISIONS.md`.

**A test case is a (test node id, case id) pair, not a case id** (DECISIONS 73). The demo suite
checks ``htn-definition`` from two test functions, and a dashboard that folded them into one row
would show one of the two results and silently drop the other.

**A property that was not measured is omitted, not written ``"n/a"``** (DECISIONS 74). Every
consumer of this file parses a property value as a number when it recognises the name; a relation
that did not apply to a case has no rate, and writing a string where a rate belongs turns "we did
not measure this" into a parse error or, worse, a zero.

**An unenforceable result is not a failure** (spec §3.7). It goes in the case's ``<system-out>``,
so that a CI run whose cost ceilings all went unpriced shows the reason next to the case that was
not checked, rather than passing silently or failing wrongly.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Final

from ..assertions import AssertionResult
from ..collector import CaseResult, RunReport, case_key

__all__ = ["SUITE_NAME", "render_junit", "write_junit"]

SUITE_NAME: Final = "probatio"
"""The ``<testsuite name=...>``: the plugin, not the user's module, because one file covers all."""

_XML_DECLARATION: Final = '<?xml version="1.0" encoding="utf-8"?>'
"""Written by hand so the document is byte-identical whatever ElementTree's defaults become."""

_INDENT: Final = "  "
"""Two spaces, matching :data:`~probatio.artefacts.JSON_INDENT`, so the artefacts look alike."""

_DECIMALS: Final = 6
"""What every number is rounded to: a hundredth of a cent, as the money formatter uses."""


def _number(value: float) -> str:
    """Render a number for an attribute or a property value.

    ``repr`` of a rounded float is the shortest string that reads back as the same number, so a
    pass rate of four in five is written ``0.8`` rather than ``0.80000`` and a third is written
    ``0.333333`` rather than seventeen digits of it.

    Args:
        value: The number.

    Returns:
        Its decimal representation.
    """
    return repr(round(value, _DECIMALS))


def _text(value: str) -> str:
    """Drop the characters XML 1.0 has no representation for.

    A failure block can hold a unified diff of a model's output, and a model's output can hold a
    control character. ElementTree would write it out unescaped and the file would not parse.

    Args:
        value: The text to write.

    Returns:
        ``value`` without the code points XML 1.0 forbids.
    """
    return "".join(
        char
        for char in value
        if char in "\t\n\r" or 0x20 <= ord(char) <= 0xD7FF or 0xE000 <= ord(char) <= 0xFFFD
    )


def _properties(parent: ET.Element, values: Sequence[tuple[str, str]]) -> None:
    """Append a ``<properties>`` block, or nothing at all when every value was omitted."""
    if not values:
        return
    block = ET.SubElement(parent, "properties")
    for name, value in values:
        ET.SubElement(block, "property", {"name": name, "value": value})


def _case_properties(case: CaseResult) -> list[tuple[str, str]]:
    """Return spec §3.11's per-case properties, in its order, with the unmeasured ones dropped."""
    values = [
        ("pass_rate", _number(case.stability.pass_rate)),
        ("wilson_low", _number(case.stability.wilson_low)),
        ("wilson_high", _number(case.stability.wilson_high)),
    ]
    if case.cost_usd is not None:
        values.append(("cost_usd", _number(case.cost_usd)))
    values.append(("latency_ms", _number(case.latency_ms)))
    for relation in sorted(case.relations, key=lambda item: item.relation):
        if relation.violation_rate is not None:
            values.append(
                (f"relation.{relation.relation}.violation_rate", _number(relation.violation_rate))
            )
    return values


def _suite_properties(report: RunReport) -> list[tuple[str, str]]:
    """Return the suite-level properties: the stability score and the cost total, if measured.

    A session in which no call was priced has no cost total, and DECISIONS 74 omits a property it
    did not measure rather than writing a zero a dashboard would add up.
    """
    values: list[tuple[str, str]] = []
    if report.stability.stability_score is not None:
        values.append(("stability_score", _number(report.stability.stability_score)))
    if report.cost_total_usd is not None:
        values.append(("cost_total_usd", _number(report.cost_total_usd)))
    return values


def _unenforceable(case: CaseResult) -> list[AssertionResult]:
    """Return every result the run could not enforce, assertions and ceilings alike."""
    return [item for item in [*case.results, *case.budget_results] if item.unenforceable]


def _system_out(case: CaseResult) -> str | None:
    """Render the case's unenforceable results, or ``None`` when it had none."""
    unenforceable = _unenforceable(case)
    if not unenforceable:
        return None
    lines = [f"unenforceable ({len(unenforceable)}):"]
    lines += [f"  {item.assertion_type}: {item.detail}" for item in unenforceable]
    return "\n".join(lines)


def _names(report: RunReport) -> Iterator[tuple[CaseResult, str, str]]:
    """Yield each case with the classname and name it gets, disambiguating a repeated pair.

    A test that checks the same case twice — a loop over two system-under-test variants, say —
    produces two entries with one key, and a CI tool keyed on ``(classname, name)`` would show
    one. The second and later occurrences are suffixed rather than dropped or merged.
    """
    seen: dict[tuple[str, str], int] = {}
    for case in report.cases:
        key = case_key(case)
        seen[key] = seen.get(key, 0) + 1
        occurrence = seen[key]
        node_id, case_id = key
        yield case, node_id, case_id if occurrence == 1 else f"{case_id} #{occurrence}"


def render_junit(report: RunReport) -> str:
    """Render the whole report as JUnit XML.

    Args:
        report: The finished run.

    Returns:
        The document, beginning with an XML declaration and ending in one newline. A session that
        checked no case renders an empty ``<testsuite tests="0">`` rather than no file at all,
        because a pipeline that was told to write this file has to find it.
    """
    root = ET.Element("testsuites")
    suite = ET.SubElement(
        root,
        "testsuite",
        {
            "name": SUITE_NAME,
            "tests": str(len(report.cases)),
            "failures": str(report.n_failed),
            "errors": "0",
            "skipped": "0",
            "time": _number(sum(case.latency_ms for case in report.cases) / 1000.0),
        },
    )
    _properties(suite, _suite_properties(report))
    for case, classname, name in _names(report):
        element = ET.SubElement(
            suite,
            "testcase",
            {
                "classname": classname,
                "name": name,
                "time": _number(case.latency_ms / 1000.0),
            },
        )
        _properties(element, _case_properties(case))
        if not case.passed:
            failure = case.failure or f"{case.case_id}: the case did not pass"
            message = ET.SubElement(
                element, "failure", {"message": _text(failure.splitlines()[0]), "type": "failure"}
            )
            message.text = _text(failure)
        out = _system_out(case)
        if out is not None:
            ET.SubElement(element, "system-out").text = _text(out)
    ET.indent(root, space=_INDENT)
    return f"{_XML_DECLARATION}\n{ET.tostring(root, encoding='unicode')}\n"


def write_junit(report: RunReport, path: Path) -> Path:
    """Write the JUnit XML file.

    Args:
        report: The finished run.
        path: Where to write it. Parent directories are created.

    Returns:
        The path written, so the caller can report it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_junit(report), encoding="utf-8")
    return path
