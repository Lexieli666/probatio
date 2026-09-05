"""Phase 10: the JUnit reporter, checked against what a CI tool actually reads.

There is no one JUnit schema, so the structural test here is the intersection every common
consumer parses: the ``testsuite`` attributes ``name``, ``tests``, ``failures``, ``errors`` and
``time``, and the ``testcase`` attributes ``classname``, ``name`` and ``time``. ``junitparser`` is
not a dependency of this project and is not installed by it; the one test that uses it returns
without asserting when it is absent, rather than skipping, because the gate forbids a skip.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from probatio import AssertionResult
from probatio.budget import SuiteBudget
from probatio.collector import CaseResult, RunReport, RunState
from probatio.metamorphic import RelationResult
from probatio.reporters import SUITE_NAME, render_junit, write_junit
from probatio.reporters.junit import _number
from probatio.snapshot import SnapshotResult
from probatio.stability import FlakyTolerance, case_stability

REQUIRED_SUITE_ATTRIBUTES = ("name", "tests", "failures", "errors", "time")
REQUIRED_CASE_ATTRIBUTES = ("classname", "name", "time")


def passing(kind: str = "contains") -> AssertionResult:
    return AssertionResult(assertion_type=kind, passed=True, score=1.0, detail="matched")


def unenforceable(kind: str, detail: str) -> AssertionResult:
    return AssertionResult(
        assertion_type=kind, passed=False, score=None, detail=detail, unenforceable=True
    )


def case(
    case_id: str,
    *,
    node_id: str | None = None,
    verdicts: tuple[bool, ...] = (True,),
    passed: bool = True,
    failure: str | None = None,
    results: tuple[AssertionResult, ...] = (),
    budget_results: tuple[AssertionResult, ...] = (),
    cost: float | None = 0.0005,
    latency_ms: float = 100.0,
    relations: tuple[RelationResult, ...] = (),
    tolerance: FlakyTolerance | None = None,
    snapshot: SnapshotResult | None = None,
) -> CaseResult:
    return CaseResult(
        case_id=case_id,
        node_id=node_id or f"test_demo.py::test_case[{case_id}]",
        suite="test_demo",
        verdict=all(verdicts),
        passed=passed,
        failure=failure,
        results=list(results) or [passing()],
        budget_results=list(budget_results),
        cost_usd=cost,
        latency_ms=latency_ms,
        snapshot=snapshot,
        stability=case_stability(list(verdicts), tolerance=tolerance),
        relations=list(relations),
    )


def report_with(*cases: CaseResult, runs: int = 1) -> RunReport:
    """Build a report the way a session does, budget included.

    The budget has to see each case: a report whose cases carry a cost but whose budget was never
    told about them has no cost total, and the suite property that carries it is then rightly
    omitted rather than written as a zero.
    """
    budget = SuiteBudget(None)
    state = RunState(runs=runs, budget=budget)
    for item in cases:
        state.record(item)
        budget.record(item.case_id, item.cost_usd)
    return state.report()


def parse(report: RunReport) -> ET.Element:
    return ET.fromstring(render_junit(report))


def properties(element: ET.Element) -> dict[str, str]:
    block = element.find("properties")
    if block is None:
        return {}
    return {child.attrib["name"]: child.attrib["value"] for child in block.findall("property")}


# -- the structure common CI tools require ------------------------------------------------------


def test_the_document_is_a_testsuites_root_holding_one_testsuite() -> None:
    root = parse(report_with(case("alpha")))
    assert root.tag == "testsuites"
    suites = root.findall("testsuite")
    assert len(suites) == 1
    assert suites[0].attrib["name"] == SUITE_NAME


def test_the_testsuite_carries_every_attribute_a_ci_tool_reads() -> None:
    """Spec §3.11 acceptance: a test parses it with ``xml.etree`` and checks the attributes."""
    suite = parse(report_with(case("alpha"), case("bravo"))).find("testsuite")
    assert suite is not None
    for name in REQUIRED_SUITE_ATTRIBUTES:
        assert name in suite.attrib, name
    assert suite.attrib["tests"] == "2"
    assert suite.attrib["failures"] == "0"
    assert suite.attrib["errors"] == "0"


def test_every_testcase_carries_classname_name_and_time() -> None:
    suite = parse(report_with(case("alpha"))).find("testsuite")
    assert suite is not None
    element = suite.findall("testcase")[0]
    for name in REQUIRED_CASE_ATTRIBUTES:
        assert name in element.attrib, name
    assert element.attrib["classname"] == "test_demo.py::test_case[alpha]"
    assert element.attrib["name"] == "alpha"


def test_the_times_are_seconds_taken_from_the_latencies() -> None:
    root = parse(report_with(case("alpha", latency_ms=100.0), case("bravo", latency_ms=250.0)))
    suite = root.find("testsuite")
    assert suite is not None
    assert suite.attrib["time"] == "0.35"
    assert [element.attrib["time"] for element in suite.findall("testcase")] == ["0.1", "0.25"]


def test_the_document_starts_with_a_declaration_and_ends_with_one_newline() -> None:
    document = render_junit(report_with(case("alpha")))
    assert document.startswith('<?xml version="1.0" encoding="utf-8"?>\n')
    assert document.endswith("</testsuites>\n")
    assert not document.endswith("\n\n")


def test_rendering_the_same_report_twice_gives_the_same_bytes() -> None:
    report = report_with(case("alpha"), case("bravo"))
    assert render_junit(report) == render_junit(report)


# -- one testcase per (node id, case id) --------------------------------------------------------


def test_a_case_checked_by_two_tests_appears_twice_with_distinct_classnames() -> None:
    """Requirement 2: the demo checks ``htn-definition`` from ``test_case`` and again elsewhere."""
    root = parse(
        report_with(
            case("htn-definition", node_id="test_demo.py::test_case[htn-definition]"),
            case("htn-definition", node_id="test_demo.py::test_paraphrase[htn-definition]"),
        )
    )
    suite = root.find("testsuite")
    assert suite is not None
    entries = [(e.attrib["classname"], e.attrib["name"]) for e in suite.findall("testcase")]
    assert entries == [
        ("test_demo.py::test_case[htn-definition]", "htn-definition"),
        ("test_demo.py::test_paraphrase[htn-definition]", "htn-definition"),
    ]
    assert len(set(entries)) == 2


def test_one_test_checking_one_case_twice_is_disambiguated_rather_than_folded() -> None:
    node_id = "test_demo.py::test_case[alpha]"
    root = parse(report_with(case("alpha", node_id=node_id), case("alpha", node_id=node_id)))
    suite = root.find("testsuite")
    assert suite is not None
    names = [element.attrib["name"] for element in suite.findall("testcase")]
    assert names == ["alpha", "alpha #2"]


# -- the properties spec §3.11 lists ------------------------------------------------------------


def test_a_case_carries_every_property_the_specification_names() -> None:
    root = parse(
        report_with(
            case(
                "alpha",
                verdicts=(True,) * 5,
                cost=0.0005,
                latency_ms=100.0,
                relations=(
                    RelationResult(
                        relation="format_jitter",
                        case_id="alpha",
                        n_variants=3,
                        n_violations=1,
                        violation_rate=1 / 3,
                    ),
                ),
            ),
            runs=5,
        )
    )
    suite = root.find("testsuite")
    assert suite is not None
    values = properties(suite.findall("testcase")[0])
    assert set(values) == {
        "pass_rate",
        "wilson_low",
        "wilson_high",
        "cost_usd",
        "latency_ms",
        "relation.format_jitter.violation_rate",
    }
    assert values["pass_rate"] == "1.0"
    assert values["cost_usd"] == "0.0005"
    assert values["latency_ms"] == "100.0"
    assert values["relation.format_jitter.violation_rate"] == "0.333333"


def test_the_flaky_cases_pass_rate_property_reads_zero_point_eight() -> None:
    """Spec §3.12 acceptance: the flaky case's ``pass_rate`` property reads 0.8."""
    root = parse(
        report_with(
            case(
                "flu-antivirals-flaky",
                verdicts=(False, True, True, True, True),
                tolerance=FlakyTolerance(p=0.8, n=5),
            ),
            runs=5,
        )
    )
    suite = root.find("testsuite")
    assert suite is not None
    assert properties(suite.findall("testcase")[0])["pass_rate"] == "0.8"


def test_a_relation_that_did_not_apply_has_no_property_at_all() -> None:
    """DECISIONS 74: a rate that was not measured is omitted, never written as a number."""
    root = parse(
        report_with(
            case(
                "alpha",
                relations=(
                    RelationResult(
                        relation="order_invariant",
                        case_id="alpha",
                        n_variants=0,
                        n_violations=0,
                        violation_rate=None,
                    ),
                ),
            )
        )
    )
    suite = root.find("testsuite")
    assert suite is not None
    values = properties(suite.findall("testcase")[0])
    assert not any(name.startswith("relation.") for name in values)


def test_a_case_with_no_priced_call_has_no_cost_property() -> None:
    root = parse(report_with(case("alpha", cost=None)))
    suite = root.find("testsuite")
    assert suite is not None
    assert "cost_usd" not in properties(suite.findall("testcase")[0])


def test_the_suite_properties_carry_the_stability_score_and_the_cost_total() -> None:
    root = parse(report_with(case("alpha", verdicts=(True, True, False)), runs=3))
    suite = root.find("testsuite")
    assert suite is not None
    values = properties(suite)
    assert values["stability_score"] == "0.666667"
    assert "cost_total_usd" in values


def test_an_unmeasured_stability_score_is_omitted_from_the_suite_properties() -> None:
    suite = parse(report_with(case("alpha"))).find("testsuite")
    assert suite is not None
    values = properties(suite)
    assert "stability_score" not in values
    assert "cost_total_usd" in values


def test_a_run_with_no_priced_call_omits_the_cost_total_property() -> None:
    """DECISIONS 74: an unmeasured property is omitted, never written as a zero to be summed."""
    suite = parse(report_with(case("alpha", cost=None))).find("testsuite")
    assert suite is not None
    assert "cost_total_usd" not in properties(suite)


# -- failures, and what is not one ---------------------------------------------------------------


def test_a_failing_case_carries_a_failure_listing_its_assertions() -> None:
    """Spec §3.12 acceptance: the demo's expected-fail case appears with a ``<failure>``."""
    failure = (
        "anxiety-expected-fail: verdict failed\n"
        "  contains: none of ['reassurance'] appeared\n"
        "  not_contains: 'I don't know' appeared"
    )
    root = parse(
        report_with(
            case(
                "anxiety-expected-fail",
                verdicts=(False,),
                passed=False,
                failure=failure,
                results=(
                    AssertionResult(
                        assertion_type="contains", passed=False, score=0.0, detail="none appeared"
                    ),
                ),
            )
        )
    )
    suite = root.find("testsuite")
    assert suite is not None
    assert suite.attrib["failures"] == "1"
    element = suite.findall("testcase")[0].find("failure")
    assert element is not None
    assert element.attrib["message"] == "anxiety-expected-fail: verdict failed"
    assert element.text is not None
    assert "contains: none of ['reassurance'] appeared" in element.text
    assert "not_contains: 'I don't know' appeared" in element.text


def test_a_passing_case_has_no_failure_element() -> None:
    suite = parse(report_with(case("alpha"))).find("testsuite")
    assert suite is not None
    assert suite.findall("testcase")[0].find("failure") is None


def test_a_failing_case_with_no_summary_still_says_something() -> None:
    root = parse(report_with(case("alpha", verdicts=(False,), passed=False, failure=None)))
    suite = root.find("testsuite")
    assert suite is not None
    element = suite.findall("testcase")[0].find("failure")
    assert element is not None
    assert "alpha" in element.attrib["message"]


def test_an_unenforceable_result_is_reported_in_system_out_and_is_not_a_failure() -> None:
    """Spec §3.7: an unenforceable ceiling is not a passing check and is not a failing one."""
    root = parse(
        report_with(
            case(
                "alpha",
                results=(passing(), unenforceable("judge", "has not been validated")),
                budget_results=(
                    unenforceable("budget_cost", "cost ceiling for alpha is unenforceable"),
                ),
            )
        )
    )
    suite = root.find("testsuite")
    assert suite is not None
    assert suite.attrib["failures"] == "0"
    element = suite.findall("testcase")[0]
    assert element.find("failure") is None
    out = element.find("system-out")
    assert out is not None and out.text is not None
    assert out.text.splitlines()[0] == "unenforceable (2):"
    assert "judge: has not been validated" in out.text
    assert "budget_cost: cost ceiling for alpha is unenforceable" in out.text


def test_a_case_with_nothing_unenforceable_has_no_system_out() -> None:
    suite = parse(report_with(case("alpha"))).find("testsuite")
    assert suite is not None
    assert suite.findall("testcase")[0].find("system-out") is None


# -- edges ----------------------------------------------------------------------------------------


def test_a_session_that_checked_nothing_still_renders_a_parsable_empty_suite() -> None:
    suite = parse(report_with()).find("testsuite")
    assert suite is not None
    assert suite.attrib["tests"] == "0"
    assert suite.findall("testcase") == []


def test_a_control_character_in_a_failure_is_dropped_so_the_file_still_parses() -> None:
    root = parse(
        report_with(
            case(
                "alpha",
                verdicts=(False,),
                passed=False,
                failure="alpha: verdict failed\n  contains: got 'a\x00b\x08c'",
            )
        )
    )
    suite = root.find("testsuite")
    assert suite is not None
    element = suite.findall("testcase")[0].find("failure")
    assert element is not None and element.text is not None
    assert "abc" in element.text
    assert "\x00" not in element.text


def test_markup_in_a_detail_is_escaped_rather_than_written_through() -> None:
    document = render_junit(
        report_with(
            case(
                "alpha",
                verdicts=(False,),
                passed=False,
                failure='alpha: got <b>bold</b> & "quotes"',
            )
        )
    )
    assert "<b>bold</b>" not in document
    assert "&lt;b&gt;bold&lt;/b&gt;" in document
    assert ET.fromstring(document) is not None


def test_numbers_are_written_as_the_shortest_string_that_reads_back() -> None:
    assert _number(0.8) == "0.8"
    assert _number(1.0) == "1.0"
    assert _number(0.0) == "0.0"
    assert _number(1 / 3) == "0.333333"
    assert _number(0.0005) == "0.0005"


# -- writing the file ------------------------------------------------------------------------------


def test_write_junit_creates_the_directory_and_returns_the_path(tmp_path: Path) -> None:
    destination = tmp_path / "build" / "junit" / "probatio.xml"
    written = write_junit(report_with(case("alpha")), destination)
    assert written == destination
    assert ET.parse(destination).getroot().tag == "testsuites"


def test_the_file_is_also_readable_by_junitparser_when_it_happens_to_be_installed(
    tmp_path: Path,
) -> None:
    """The brief: ``junitparser`` is not a dependency; without it the ``xml.etree`` test stands."""
    try:
        from junitparser import JUnitXml
    except ImportError:
        return
    path = write_junit(report_with(case("alpha"), case("bravo")), tmp_path / "j.xml")
    parsed = JUnitXml.fromfile(str(path))
    assert sum(suite.tests for suite in parsed) == 2


def test_a_block_with_no_values_writes_no_properties_element() -> None:
    """Defensive: a case always has at least ``pass_rate``, so nothing else reaches this."""
    from probatio.reporters.junit import _properties

    parent = ET.Element("testcase")
    _properties(parent, [])
    assert parent.find("properties") is None
