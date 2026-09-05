"""Phase 9: the pytest surface, exercised through ``pytester``.

Every suite here is written into a temporary directory and run in a subprocess, so the plugin is
loaded through its entry point exactly as a user's installation loads it, and the inner session's
run state cannot touch this one's. Nothing reaches a provider Probatio did not build, and the
default provider is ``fake``.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest

from probatio import Completion
from probatio.collector import RunReport, RunState
from probatio.errors import ProbatioConfigError
from probatio.plugin import (
    PROVIDER_CHOICES,
    RUNS_DEST,
    _add_runs_option,
    _ObservingProvider,
    _session,
    as_usage_error,
    check_model_is_named,
)
from probatio.reporters import read_results
from probatio.stability import FLAKY_MARKER

CASE_YAML = """\
id: {case_id}
input:
  question: "Which test confirms COPD, and is it spirometry"
  documents: ["one", "two"]
assertions:
  - {{type: contains, any: ["spirometry"]}}
budget: {{max_cost_usd: 0.01, max_latency_ms: 5000}}
"""

CONFTEST = """
import pytest
from probatio import FakeProvider

ANSWER = "Spirometry confirms COPD."


@pytest.fixture
def provider(provider, request):
    if request.config.getoption("--probatio-provider") != "fake":
        return provider
    return FakeProvider(default=ANSWER, cost_usd=0.001, latency_ms=4.0)


@pytest.fixture
def judge_provider(judge_provider):
    return FakeProvider(default='{"verdict": "pass", "score": 1.0}')
"""

TEST_MODULE = """
import pytest
from probatio import load_cases

CASES = load_cases("cases")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_case(case, probatio, provider):
    probatio.check(case, sut=lambda c: provider.complete(str(c.input)))
"""


def _properties(element: ET.Element) -> dict[str, str]:
    """Read a ``<properties>`` block back as a mapping, or an empty one when there is none."""
    block = element.find("properties")
    if block is None:
        return {}
    return {child.attrib["name"]: child.attrib["value"] for child in block.findall("property")}


def write_suite(
    pytester: pytest.Pytester,
    *,
    case_ids: tuple[str, ...] = ("alpha",),
    conftest: str = CONFTEST,
    module: str = TEST_MODULE,
    extra_case_yaml: str = "",
) -> None:
    """Write a runnable Probatio suite into the pytester directory."""
    cases = pytester.path / "cases"
    cases.mkdir(exist_ok=True)
    for case_id in case_ids:
        (cases / f"{case_id}.yaml").write_text(
            CASE_YAML.format(case_id=case_id) + extra_case_yaml, encoding="utf-8"
        )
    pytester.makeconftest(conftest)
    pytester.makepyfile(test_suite=module)


# -- options ------------------------------------------------------------------------------------


def test_every_documented_flag_is_listed_in_the_help(pytester: pytest.Pytester) -> None:
    """Spec §3.12 acceptance: option help text lists every flag."""
    output = pytester.runpytest_subprocess("--help").stdout.str()
    for flag in (
        "--probatio-provider",
        "--probatio-model",
        "--probatio-judge-provider",
        "--probatio-judge-model",
        "--probatio-prices",
        "--cassette=",
        "--cassette-dir",
        "--runs",
        "--update-baseline",
        "--baseline-dir",
        "--max-cost",
        "--max-latency",
        "--probatio-report",
        "--probatio-junit",
        "--probatio-results",
    ):
        assert flag in output, flag
    assert "probatio: regression testing for LLM applications" in output


def test_the_flags_live_in_their_own_group(pytester: pytest.Pytester) -> None:
    output = pytester.runpytest_subprocess("--help").stdout.str()
    group = output.split("probatio: regression testing for LLM applications", 1)[1]
    assert "--probatio-provider" in group.split("\n\n", 1)[0] + group[:2000]


def test_the_provider_choices_are_the_three_shipped_adapters() -> None:
    assert PROVIDER_CHOICES == ("fake", "anthropic", "claude-cli")


def test_runs_falls_back_to_probatio_runs_when_the_name_is_taken() -> None:
    """Spec §3.12: record the fallback in DECISIONS.md; DECISIONS 61 does."""

    class Taken:
        def __init__(self) -> None:
            self.added: list[str] = []

        def addoption(self, flag: str, **kwargs: object) -> None:
            self.added.append(flag)
            if flag == "--runs":
                raise ValueError("option names {'--runs'} already added")

    group = Taken()
    assert _add_runs_option(group) == "--probatio-runs"
    assert group.added == ["--runs", "--probatio-runs"]


def test_both_run_flags_being_taken_is_a_configuration_error() -> None:
    class Taken:
        def addoption(self, flag: str, **kwargs: object) -> None:
            raise ValueError("already added")

    with pytest.raises(ProbatioConfigError, match="another plugin has taken both"):
        _add_runs_option(Taken())


def test_the_runs_option_stores_under_a_stable_destination(pytester: pytest.Pytester) -> None:
    write_suite(pytester)
    pytester.makepyfile(
        test_dest=f"""
        def test_dest(request):
            assert request.config.getoption({RUNS_DEST!r}) == 3
        """
    )
    pytester.runpytest_subprocess("test_dest.py", "--runs", "3").assert_outcomes(passed=1)


# -- a refused configuration is a usage error, not an INTERNALERROR ------------------------------


class _Config:
    def __init__(self, **options: object) -> None:
        self.options = options

    def getoption(self, name: str) -> object:
        return self.options.get(name.replace("--", "").replace("-", "_"))


def test_a_configuration_error_becomes_a_usage_error_with_the_same_text() -> None:
    """Requirement 5: the message is unchanged and the original error is the cause."""
    original = ProbatioConfigError("the flag is wrong")
    with pytest.raises(pytest.UsageError) as excinfo:
        with as_usage_error():
            raise original
    assert str(excinfo.value) == "the flag is wrong"
    assert excinfo.value.__cause__ is original


def test_anything_that_is_not_a_configuration_error_passes_through() -> None:
    with pytest.raises(RuntimeError, match="not mine"):
        with as_usage_error():
            raise RuntimeError("not mine")


def test_a_block_that_raises_nothing_is_left_alone() -> None:
    with as_usage_error():
        pass


def test_a_refused_session_prints_no_internal_error(pytester: pytest.Pytester) -> None:
    """Requirement 5: an INTERNALERROR traceback reads as a bug in the plugin, not a bad flag."""
    write_suite(pytester)
    result = pytester.runpytest_subprocess("--probatio-provider", "anthropic")
    output = result.stdout.str() + result.stderr.str()
    assert result.ret != 0
    assert "INTERNALERROR" not in output
    assert "needs --probatio-model" in output


# -- a live provider must be told its model -------------------------------------------------------


@pytest.mark.parametrize("name", ["claude-cli", "anthropic"])
def test_a_live_provider_without_a_model_is_refused(name: str) -> None:
    """Requirement 5: a tape keyed on the adapter's name cannot tell two models apart."""
    with pytest.raises(Exception, match="needs --probatio-model") as excinfo:
        check_model_is_named(_Config(probatio_provider=name))  # type: ignore[arg-type]
    assert name in str(excinfo.value)


def test_a_live_judge_provider_without_a_model_is_refused() -> None:
    with pytest.raises(Exception, match="needs --probatio-model"):
        check_model_is_named(  # type: ignore[arg-type]
            _Config(probatio_provider="fake", probatio_judge_provider="claude-cli")
        )


def test_a_live_judge_inherits_the_system_under_tests_model() -> None:
    check_model_is_named(  # type: ignore[arg-type]
        _Config(
            probatio_provider="claude-cli",
            probatio_model="claude-x",
            probatio_judge_provider="claude-cli",
        )
    )


def test_the_fake_provider_needs_no_model() -> None:
    check_model_is_named(_Config(probatio_provider="fake"))  # type: ignore[arg-type]


def test_a_live_provider_without_a_model_fails_a_real_session(
    pytester: pytest.Pytester,
) -> None:
    write_suite(pytester)
    result = pytester.runpytest_subprocess("--probatio-provider", "claude-cli")
    assert result.ret != 0
    assert "needs --probatio-model" in result.stdout.str() + result.stderr.str()


# -- fixtures ---------------------------------------------------------------------------------


def test_the_provider_fixture_is_cassette_wrapped_and_reports_the_adapters_name(
    pytester: pytest.Pytester,
) -> None:
    pytester.makepyfile(
        test_wrapped="""
        def test_wrapped(provider, judge_provider):
            assert provider.name == "fake"
            assert judge_provider.name == "fake"
            assert hasattr(provider, "judge_calls"), "the judge marks its calls through this"
        """
    )
    pytester.runpytest_subprocess().assert_outcomes(passed=1)


def test_the_demo_style_override_keeps_working(pytester: pytest.Pytester) -> None:
    """Requirement 4, DECISIONS 9: a suite overrides the fixture and takes it as an argument."""
    write_suite(pytester)
    pytester.runpytest_subprocess().assert_outcomes(passed=1)


def test_the_override_steps_aside_for_a_live_provider(pytester: pytest.Pytester) -> None:
    """The plugin's own provider is handed back, unbuilt, when the flag is not ``fake``."""
    write_suite(pytester)
    pytester.makepyfile(
        test_switch="""
        def test_switch(provider, request):
            assert request.config.getoption("--probatio-provider") == "claude-cli"
            assert provider.name == "claude-cli"
        """
    )
    result = pytester.runpytest_subprocess(
        "test_switch.py", "--probatio-provider", "claude-cli", "--probatio-model", "claude-x"
    )
    result.assert_outcomes(passed=1)


def test_the_judge_provider_follows_the_system_under_tests_unless_told_otherwise(
    pytester: pytest.Pytester,
) -> None:
    pytester.makepyfile(
        test_judge="""
        def test_judge(provider, judge_provider):
            assert judge_provider.inner.inner_model == "judge-model"
            assert provider.inner.inner_model == "sut-model"
        """
    )
    result = pytester.runpytest_subprocess(
        "test_judge.py",
        "--probatio-provider",
        "fake",
        "--probatio-model",
        "sut-model",
        "--probatio-judge-model",
        "judge-model",
    )
    result.assert_outcomes(passed=1)


def test_the_probatio_fixture_reads_the_markers_off_its_own_test(
    pytester: pytest.Pytester,
) -> None:
    pytester.makepyfile(
        test_marks="""
        from probatio import format_jitter, flaky_tolerant


        @format_jitter(field="input.question")
        @flaky_tolerant(p=0.5, n=4)
        def test_marks(probatio):
            assert [r.name for r in probatio.relations] == ["format_jitter"]
            assert probatio.tolerance.n == 4
            assert probatio.runs == 4
            assert probatio.suite == "test_marks"


        def test_unmarked(probatio):
            assert probatio.relations == []
            assert probatio.tolerance is None
            assert probatio.runs == 1
        """
    )
    pytester.runpytest_subprocess("test_marks.py").assert_outcomes(passed=2)
    assert FLAKY_MARKER == "flaky_tolerant"


def test_the_rubric_directories_are_rootdir_then_the_test_module(
    pytester: pytest.Pytester,
) -> None:
    """DECISIONS 23."""
    pytester.makepyfile(
        test_dirs="""
        from pathlib import Path


        def test_dirs(probatio, request):
            root = Path(str(request.config.rootpath))
            assert probatio.rubric_dirs == [root / "rubrics"]
        """
    )
    pytester.runpytest_subprocess("test_dirs.py").assert_outcomes(passed=1)


def test_both_markers_are_registered(pytester: pytest.Pytester) -> None:
    output = pytester.runpytest_subprocess("--markers").stdout.str()
    assert "@pytest.mark.probatio_relation(relation):" in output
    assert f"@pytest.mark.{FLAKY_MARKER}(p, n):" in output


# -- the report --------------------------------------------------------------------------------


def test_the_terminal_section_is_printed(pytester: pytest.Pytester) -> None:
    write_suite(pytester, case_ids=("alpha", "bravo"))
    output = pytester.runpytest_subprocess().stdout.str()
    assert "probatio" in output
    assert "cases:" in output
    assert "alpha" in output and "bravo" in output
    assert "stability: not measured" in output


def test_a_session_with_no_probatio_cases_prints_no_section(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(test_plain="def test_plain():\n    assert True\n")
    output = pytester.runpytest_subprocess("test_plain.py").stdout.str()
    assert "cases:" not in output


def test_runs_three_reports_a_pass_rate_and_a_stability_score(
    pytester: pytest.Pytester,
) -> None:
    """Spec §3.12 acceptance: a three-case suite under ``--runs 3``."""
    write_suite(pytester, case_ids=("alpha", "bravo", "charlie"))
    result = pytester.runpytest_subprocess("--runs", "3")
    result.assert_outcomes(passed=3)
    output = result.stdout.str()
    assert "pass rate" in output and "95% Wilson" in output
    assert "stability score: 1.00 over 3 repeated case(s)" in output


def test_runs_three_writes_both_report_files_with_every_property(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec §3.11 and §3.12 acceptance: three cases, ``--runs 3``, both files, every property."""
    # The subprocess inherits this environment; a job summary would add a file to the count.
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    write_suite(pytester, case_ids=("alpha", "bravo", "charlie"))
    result = pytester.runpytest_subprocess(
        "--runs", "3", "--probatio-results", "r.json", "--probatio-junit", "j.xml"
    )
    result.assert_outcomes(passed=3)

    junit = pytester.path / "j.xml"
    results = pytester.path / "r.json"
    assert junit.exists() and results.exists()
    assert result.stdout.str().count("probatio: wrote ") >= 2

    root = ET.parse(junit).getroot()
    assert root.tag == "testsuites"
    suite = root.find("testsuite")
    assert suite is not None
    for name in ("name", "tests", "failures", "errors", "time"):
        assert name in suite.attrib, name
    assert suite.attrib["tests"] == "3"
    assert _properties(suite).keys() >= {"stability_score", "cost_total_usd"}

    cases = suite.findall("testcase")
    assert [element.attrib["name"] for element in cases] == ["alpha", "bravo", "charlie"]
    for element in cases:
        for name in ("classname", "name", "time"):
            assert name in element.attrib, name
        assert element.attrib["classname"].startswith("test_suite.py::test_case[")
        assert _properties(element).keys() >= {
            "pass_rate",
            "wilson_low",
            "wilson_high",
            "cost_usd",
            "latency_ms",
        }

    report = read_results(results)
    assert RunReport.model_validate(json.loads(results.read_text(encoding="utf-8"))) == report
    assert [case.case_id for case in report.cases] == ["alpha", "bravo", "charlie"]
    assert report.runs == 3
    assert all(case.stability.runs == 3 for case in report.cases)


RELATION_MODULE = """
import pytest
from probatio import format_jitter, load_cases

CASES = load_cases("cases")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
@format_jitter(field="input.question")
def test_case(case, probatio, provider):
    probatio.check(case, sut=lambda c: provider.complete(str(c.input)))
"""

EXPECTED_FAIL_MODULE = """
import pytest
from probatio import load_cases

CASES = load_cases("cases")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_case(case, probatio, provider):
    with pytest.raises(AssertionError):
        probatio.check(case, sut=lambda c: "I do not know.")
"""


def test_a_relation_reaches_the_junit_properties(pytester: pytest.Pytester) -> None:
    write_suite(pytester, module=RELATION_MODULE)
    pytester.runpytest_subprocess("--probatio-junit", "j.xml").assert_outcomes(passed=1)
    suite = ET.parse(pytester.path / "j.xml").getroot().find("testsuite")
    assert suite is not None
    values = _properties(suite.findall("testcase")[0])
    assert values["relation.format_jitter.violation_rate"] == "0.0"


def test_both_files_are_written_even_when_no_case_ran(pytester: pytest.Pytester) -> None:
    """DECISIONS 67's argument, kept: a pipeline told to collect a file has to find it."""
    pytester.makepyfile(test_plain="def test_plain():\n    assert True\n")
    pytester.runpytest_subprocess(
        "test_plain.py", "--probatio-results", "r.json", "--probatio-junit", "j.xml"
    ).assert_outcomes(passed=1)
    suite = ET.parse(pytester.path / "j.xml").getroot().find("testsuite")
    assert suite is not None and suite.attrib["tests"] == "0"
    assert read_results(pytester.path / "r.json").cases == []


def test_a_failing_case_reaches_the_junit_file_as_a_failure(pytester: pytest.Pytester) -> None:
    """The demo's shape: the test passes because it expected the failure; the report shows it."""
    write_suite(pytester, module=EXPECTED_FAIL_MODULE)
    pytester.runpytest_subprocess("--probatio-junit", "j.xml").assert_outcomes(passed=1)
    suite = ET.parse(pytester.path / "j.xml").getroot().find("testsuite")
    assert suite is not None
    assert suite.attrib["failures"] == "1"
    failure = suite.findall("testcase")[0].find("failure")
    assert failure is not None and failure.text is not None
    assert "contains" in failure.text


def test_the_report_paths_are_resolved_against_rootdir(pytester: pytest.Pytester) -> None:
    write_suite(pytester)
    pytester.runpytest_subprocess(
        "--probatio-results", "build/deep/r.json", "--probatio-junit", "build/deep/j.xml"
    )
    assert (pytester.path / "build" / "deep" / "r.json").exists()
    assert (pytester.path / "build" / "deep" / "j.xml").exists()


def test_the_markdown_report_is_written_where_it_is_asked_for(
    pytester: pytest.Pytester,
) -> None:
    write_suite(pytester)
    pytester.runpytest_subprocess("--probatio-report", "build/report.md")
    document = (pytester.path / "build" / "report.md").read_text(encoding="utf-8")
    assert document.startswith("## probatio")
    assert "| alpha | pass |" in document


def test_the_markdown_report_lands_in_a_github_job_summary(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec §3.11 acceptance: the reporter writes to a temporary ``GITHUB_STEP_SUMMARY``."""
    write_suite(pytester)
    summary = pytester.path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    pytester.runpytest_subprocess()
    assert "## probatio" in summary.read_text(encoding="utf-8")


# -- the suite-level cost ceiling ------------------------------------------------------------------


def test_a_cost_overrun_fails_the_session_and_prints_the_line(
    pytester: pytest.Pytester,
) -> None:
    """Spec §3.7 acceptance, deferred from Phase 6."""
    write_suite(pytester, case_ids=("alpha", "bravo", "charlie"))
    result = pytester.runpytest_subprocess("--max-cost", "0.002")
    assert result.ret != 0
    output = result.stdout.str()
    assert "probatio:" in output
    assert "0.003" in output and "0.002" in output
    result.assert_outcomes(passed=3), "every case passed; the session did not"


def test_a_session_inside_the_ceiling_exits_zero(pytester: pytest.Pytester) -> None:
    write_suite(pytester, case_ids=("alpha", "bravo"))
    result = pytester.runpytest_subprocess("--max-cost", "1.0")
    assert result.ret == 0


# -- cassettes ---------------------------------------------------------------------------------


def test_replay_with_no_tapes_fails_with_a_missing_cassette_error(
    pytester: pytest.Pytester,
) -> None:
    """Spec §3.8 and §3.12 acceptance, deferred from Phase 7. The provider is not overridden."""
    write_suite(pytester, conftest="")
    result = pytester.runpytest_subprocess("--cassette=replay")
    assert result.ret != 0
    output = result.stdout.str()
    assert "MissingCassetteError" in output
    assert "pytest --cassette=record" in output


def test_the_record_command_in_the_error_names_the_configured_provider(
    pytester: pytest.Pytester,
) -> None:
    """Requirement 5: re-recording against the default provider is not the instruction."""
    write_suite(pytester, conftest="")
    result = pytester.runpytest_subprocess(
        "--cassette=replay", "--probatio-provider", "claude-cli", "--probatio-model", "claude-x"
    )
    assert result.ret != 0
    output = result.stdout.str()
    assert "pytest --cassette=record --probatio-provider claude-cli" in output
    assert "--probatio-model claude-x" in output


def test_record_then_replay_needs_no_provider_at_all(pytester: pytest.Pytester) -> None:
    write_suite(pytester, conftest="")
    recorded = pytester.runpytest_subprocess("--cassette=record", "--cassette-dir", "tapes")
    recorded.assert_outcomes(failed=1), "the bare fake answers FAKE(...), which fails 'contains'"
    tape = pytester.path / "tapes" / "test_suite" / "alpha.json"
    assert tape.exists()
    assert json.loads(tape.read_text())["case_id"] == "alpha"

    replayed = pytester.runpytest_subprocess("--cassette=replay", "--cassette-dir", "tapes")
    replayed.assert_outcomes(failed=1)


def test_the_cassette_directory_is_resolved_against_rootdir(pytester: pytest.Pytester) -> None:
    write_suite(pytester, conftest="")
    pytester.runpytest_subprocess("--cassette=record", "--cassette-dir", "build/tapes")
    assert (pytester.path / "build" / "tapes" / "test_suite" / "alpha.json").exists()


# -- what a committed artefact may not contain ----------------------------------------------------


def absolute_strings(payload: object) -> list[str]:
    """Return every string anywhere in a parsed artefact that reads as an absolute path.

    Args:
        payload: The parsed JSON, at any depth.

    Returns:
        The offending strings. A POSIX absolute path starts with a separator and a Windows one
        starts with a drive letter, so both are recognised whichever platform wrote the file.
    """
    if isinstance(payload, str):
        return [payload] if re.match(r"^(/|[A-Za-z]:[\\/])", payload) else []
    if isinstance(payload, dict):
        return [bad for value in payload.values() for bad in absolute_strings(value)]
    if isinstance(payload, list):
        return [bad for item in payload for bad in absolute_strings(item)]
    return []


def test_the_results_json_holds_no_absolute_path(pytester: pytest.Pytester) -> None:
    """A results file is committed, so a path in it names the repository, not the machine.

    An absolute path makes the artefact machine-specific — it leaks the home directory of
    whoever ran the suite, it differs between a laptop and CI, and it makes two otherwise
    identical runs produce different bytes. The suite here records a baseline, so the report
    carries a :class:`~probatio.snapshot.SnapshotResult` with a path and a detail naming it.
    """
    write_snapshot_suite(pytester, system="Answer briefly.", answer="Spirometry confirms COPD.")
    pytester.runpytest_subprocess("--probatio-results", "r.json").assert_outcomes(passed=1)

    text = (pytester.path / "r.json").read_text(encoding="utf-8")
    report = json.loads(text)
    snapshot = report["cases"][0]["snapshot"]
    assert snapshot["state"] == "recorded"
    assert snapshot["path"] == ".probatio/baseline/test_suite/alpha.json"
    assert snapshot["detail"] == "baseline recorded at .probatio/baseline/test_suite/alpha.json"

    assert absolute_strings(report) == []
    assert str(pytester.path) not in text
    assert str(Path.home()) not in text


def test_a_missing_tape_reaches_the_report_without_an_absolute_path(
    pytester: pytest.Pytester,
) -> None:
    """DECISIONS 72 puts a missing tape's message in the warnings, so it is persisted too."""
    write_suite(pytester, conftest="")  # the plugin's own provider, so the tape is consulted
    pytester.runpytest_subprocess(
        "--cassette=replay", "--probatio-results", "r.json"
    ).assert_outcomes(failed=1)

    text = (pytester.path / "r.json").read_text(encoding="utf-8")
    report = json.loads(text)
    assert any(
        "there is no cassette at cassettes/test_suite/alpha.json" in w for w in report["warnings"]
    )
    assert absolute_strings(report) == []
    assert str(pytester.path) not in text
    assert str(Path.home()) not in text


# -- snapshots, end to end ------------------------------------------------------------------------


SNAPSHOT_CASE = """\
id: alpha
input:
  question: "Which test confirms COPD, and is it spirometry"
system: "{system}"
assertions:
  - {{type: contains, any: ["spirometry"]}}
snapshot: output
"""


def write_snapshot_suite(pytester: pytest.Pytester, *, system: str, answer: str) -> None:
    cases = pytester.path / "cases"
    cases.mkdir(exist_ok=True)
    (cases / "alpha.yaml").write_text(SNAPSHOT_CASE.format(system=system), encoding="utf-8")
    pytester.makeconftest(
        f"""
import pytest
from probatio import FakeProvider


@pytest.fixture
def provider(provider):
    return FakeProvider(default={answer!r}, cost_usd=0.001, latency_ms=4.0)
"""
    )
    pytester.makepyfile(test_suite=TEST_MODULE)


def test_the_snapshot_lifecycle_end_to_end(pytester: pytest.Pytester) -> None:
    """Spec §3.6 acceptance, deferred from Phase 5: record, drift, update, prompt change."""
    write_snapshot_suite(pytester, system="Answer briefly.", answer="Spirometry confirms COPD.")
    first = pytester.runpytest_subprocess()
    first.assert_outcomes(passed=1)
    assert "recorded" in first.stdout.str()
    assert (pytester.path / ".probatio" / "baseline" / "test_suite" / "alpha.json").exists()

    write_snapshot_suite(
        pytester, system="Answer briefly.", answer="Spirometry confirms COPD, plainly."
    )
    drifted = pytester.runpytest_subprocess()
    drifted.assert_outcomes(failed=1)
    assert "output_changed" in drifted.stdout.str()
    assert "-Spirometry confirms COPD." in drifted.stdout.str(), "a unified diff"

    updated = pytester.runpytest_subprocess("--update-baseline")
    updated.assert_outcomes(passed=1)
    assert "updated" in updated.stdout.str()
    pytester.runpytest_subprocess().assert_outcomes(passed=1)

    write_snapshot_suite(
        pytester, system="Answer at length.", answer="Spirometry confirms COPD, plainly."
    )
    changed = pytester.runpytest_subprocess()
    changed.assert_outcomes(failed=1)
    assert "prompt_changed" in changed.stdout.str()
    assert "prompt changed since baseline" in changed.stdout.str()


def test_the_baseline_directory_is_resolved_against_rootdir(pytester: pytest.Pytester) -> None:
    write_snapshot_suite(pytester, system="Answer briefly.", answer="Spirometry confirms COPD.")
    pytester.runpytest_subprocess("--baseline-dir", "build/base")
    assert (pytester.path / "build" / "base" / "test_suite" / "alpha.json").exists()


# -- the run state stack ---------------------------------------------------------------------


def test_a_nested_session_does_not_touch_its_parents_report(pytester: pytest.Pytester) -> None:
    """Spec §3.12: ``pytest_configure`` pushes and ``pytest_unconfigure`` pops."""
    write_suite(pytester)
    pytester.makepyfile(
        test_nested="""
        import pytest
        from probatio.collector import current_state, state_depth

        pytest_plugins = ["pytester"]


        def test_nested(pytester, request):
            outer = current_state()
            depth = state_depth()
            pytester.makepyfile(test_inner="def test_inner():\\n    assert True\\n")
            pytester.runpytest_inprocess("test_inner.py").assert_outcomes(passed=1)
            assert current_state() is outer
            assert state_depth() == depth
        """
    )
    pytester.runpytest_subprocess("test_nested.py", "-p", "pytester").assert_outcomes(passed=1)


def test_a_price_file_makes_the_ceilings_enforceable(pytester: pytest.Pytester) -> None:
    write_suite(pytester)
    (pytester.path / "prices.yaml").write_text(
        "fake-1: {input_per_mtok: 1.0, output_per_mtok: 2.0}\n", encoding="utf-8"
    )
    result = pytester.runpytest_subprocess("--probatio-prices", "prices.yaml")
    result.assert_outcomes(passed=1)
    assert "unenforceable" not in result.stdout.str()


def test_a_max_latency_default_applies_to_a_case_without_one(pytester: pytest.Pytester) -> None:
    write_suite(pytester)
    (pytester.path / "cases" / "alpha.yaml").write_text(
        CASE_YAML.format(case_id="alpha").replace(
            "budget: {max_cost_usd: 0.01, max_latency_ms: 5000}\n", ""
        ),
        encoding="utf-8",
    )
    result = pytester.runpytest_subprocess("--max-latency", "1")
    result.assert_outcomes(failed=1)
    assert "budget_latency" in result.stdout.str()


def test_the_reported_failure_lists_every_failed_assertion(pytester: pytest.Pytester) -> None:
    write_suite(
        pytester,
        conftest=CONFTEST.replace("default=ANSWER", 'default="I do not know."'),
    )
    result = pytester.runpytest_subprocess()
    result.assert_outcomes(failed=1)
    output = result.stdout.str()
    assert "alpha: verdict failed" in output
    assert "contains:" in output


def test_a_path_option_may_be_absolute(pytester: pytest.Pytester, tmp_path: Path) -> None:
    write_suite(pytester)
    target = tmp_path / "elsewhere" / "report.md"
    pytester.runpytest_subprocess("--probatio-report", str(target))
    assert target.exists()


# -- the pieces, without a session ----------------------------------------------------------------


class _Inner:
    """A minimal provider: enough to be wrapped, and it records what it was asked."""

    name = "inner"
    model = "inner-model"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None, dict[str, object]]] = []
        self.marked: list[str] = []

    def judge_calls(self, template_hash: str) -> Any:
        from contextlib import nullcontext

        self.marked.append(template_hash)
        return nullcontext()

    def complete(self, prompt: str, *, system: str | None = None, **params: Any) -> Completion:
        self.calls.append((prompt, system, dict(params)))
        return Completion(text="answered", model=self.model, cost_usd=0.5, latency_ms=1.0)


def test_the_observing_wrapper_reports_the_call_and_returns_it_unchanged() -> None:
    state = RunState()
    state.sink = []
    inner = _Inner()
    wrapper = _ObservingProvider(inner, state)

    completion = wrapper.complete("ask", system="be brief", temperature=0)

    assert completion.text == "answered"
    assert state.sink == [completion]
    assert inner.calls == [("ask", "be brief", {"temperature": 0})]


def test_the_observing_wrapper_reports_the_inner_adapters_name_and_model() -> None:
    wrapper = _ObservingProvider(_Inner(), RunState())
    assert wrapper.name == "inner"
    assert wrapper.model == "inner-model"


def test_a_provider_with_no_model_reports_none() -> None:
    class Bare:
        name = "bare"

        def complete(self, prompt: str, *, system: str | None = None, **params: Any) -> Any:
            raise AssertionError("not called")

    assert _ObservingProvider(Bare(), RunState()).model is None  # type: ignore[arg-type]


def test_the_judge_marker_is_forwarded_to_the_wrapped_provider() -> None:
    """DECISIONS 42: the judge marks its calls through the provider it was handed."""
    inner = _Inner()
    with _ObservingProvider(inner, RunState()).judge_calls("template-hash"):
        pass
    assert inner.marked == ["template-hash"]


def test_a_fixture_outside_a_configured_session_says_so() -> None:
    class Unconfigured:
        stash: dict[object, object] = {}

    with pytest.raises(Exception, match="was not configured for this session"):
        _session(Unconfigured())  # type: ignore[arg-type]


class _Reporter:
    """Enough of pytest's terminal reporter to record what the section wrote."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def write_sep(self, separator: str, title: str, **kwargs: Any) -> None:
        self.lines.append(f"{separator * 3} {title} {separator * 3}")

    def write_line(self, line: str, **kwargs: Any) -> None:
        self.lines.append(line)


class _Stashed:
    """A configuration carrying a real stash, so the hooks can be called directly."""

    def __init__(self, stash: pytest.Stash, **options: object) -> None:
        self.stash = stash
        self.rootpath = Path.cwd()
        self.options = options

    def getoption(self, name: str) -> object:
        return self.options.get(name.replace("--", "").replace("-", "_"))


def _state_with_one_case() -> RunState:
    from probatio.collector import CaseResult
    from probatio.stability import case_stability

    state = RunState()
    state.record(
        CaseResult(
            case_id="alpha",
            node_id="test_suite.py::test_case[alpha]",
            suite="test_suite",
            verdict=True,
            passed=True,
            stability=case_stability([True]),
        )
    )
    return state


def test_the_terminal_summary_of_an_unconfigured_session_writes_nothing() -> None:
    from probatio.plugin import pytest_terminal_summary

    reporter = _Reporter()
    pytest_terminal_summary(reporter, 0, _Stashed(pytest.Stash()))  # type: ignore[arg-type]
    assert reporter.lines == []


def test_the_terminal_summary_writes_the_section_and_names_the_file(tmp_path: Path) -> None:
    from probatio.plugin import _STATE, pytest_terminal_summary

    stash = pytest.Stash()
    stash[_STATE] = _state_with_one_case()
    target = tmp_path / "report.md"
    reporter = _Reporter()
    pytest_terminal_summary(  # type: ignore[arg-type]
        reporter, 0, _Stashed(stash, probatio_report=str(target))
    )

    text = "\n".join(reporter.lines)
    assert "probatio" in text and "cases:" in text and "alpha" in text
    assert f"probatio: wrote {target}" in text
    assert target.exists()


def test_the_terminal_summary_writes_the_junit_and_results_files_too(tmp_path: Path) -> None:
    """Requirement 1 and 3, called directly: a subprocess run cannot report its own coverage."""
    from probatio.plugin import _STATE, pytest_terminal_summary

    stash = pytest.Stash()
    stash[_STATE] = _state_with_one_case()
    junit = tmp_path / "j.xml"
    results = tmp_path / "r.json"
    reporter = _Reporter()
    pytest_terminal_summary(  # type: ignore[arg-type]
        reporter,
        0,
        _Stashed(stash, probatio_junit=str(junit), probatio_results=str(results)),
    )

    text = "\n".join(reporter.lines)
    assert f"probatio: wrote {junit}" in text
    assert f"probatio: wrote {results}" in text
    assert ET.parse(junit).getroot().find("testsuite") is not None
    assert [case.case_id for case in read_results(results).cases] == ["alpha"]


def test_write_artefacts_writes_nothing_when_no_flag_names_a_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from probatio.plugin import write_artefacts

    # On GitHub Actions the environment names a job summary, and the markdown reporter rightly
    # writes to it; "nothing was asked for" is only true once that destination is gone.
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    report = _state_with_one_case().report()
    assert write_artefacts(report, _Stashed(pytest.Stash())) == []  # type: ignore[arg-type]
    assert list(tmp_path.iterdir()) == []


def test_the_session_finish_of_an_unconfigured_session_changes_nothing() -> None:
    from probatio.plugin import pytest_sessionfinish

    class Session:
        config = _Stashed(pytest.Stash())
        exitstatus = 0

    session = Session()
    pytest_sessionfinish(session, 0)  # type: ignore[arg-type]
    assert session.exitstatus == 0


def test_a_cost_overrun_sets_the_exit_status_and_prints_the_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Spec §3.7: the overrun is a session failure, not a case failure."""
    from probatio.budget import SuiteBudget
    from probatio.plugin import _STATE, pytest_sessionfinish

    budget = SuiteBudget(0.001)
    budget.record("alpha", 0.004)
    stash = pytest.Stash()
    stash[_STATE] = RunState(budget=budget)

    class Session:
        config = _Stashed(stash)
        exitstatus = 0

    session = Session()
    pytest_sessionfinish(session, 0)  # type: ignore[arg-type]
    assert session.exitstatus == pytest.ExitCode.TESTS_FAILED
    printed = capsys.readouterr().out
    assert "probatio:" in printed and "0.004" in printed and "alpha" in printed
