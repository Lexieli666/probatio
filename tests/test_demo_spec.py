"""Phase 9: ``examples/demo_suite/`` runs, and is still the file Phase 1 committed.

The demo suite is the specification the public API was written against, and this phase is where it
finally runs. Three things are checked here: that the directory is byte-identical to the commit
that introduced it apart from the one sanctioned deletion, that the keyword table in
``conftest.py`` still selects one case each, and that the suite does through ``pytester`` what its
own README says it does.
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest
import yaml

import probatio
from probatio.collector import RunReport, case_key
from probatio.reporters import read_results

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO = REPO_ROOT / "examples" / "demo_suite"

SANCTIONED_DELETION = (
    "try:  # Phase 9 deletes this try/except block; it is the one sanctioned edit (DECISIONS.md).\n"
    "    from probatio import FakeProvider  # noqa: F401\n"
    "except ImportError:\n"
    '    collect_ignore = ["test_demo.py"]\n'
    "\n"
)
"""The import guard Phase 9 removed. Gate condition 5 allows this and nothing else."""

GUARDED_FILE = "examples/demo_suite/conftest.py"
"""The only file the sanctioned deletion touches."""


def _demo_properties(element: ET.Element) -> dict[str, str]:
    """Read one ``<testcase>``'s ``<properties>`` block back as a mapping."""
    block = element.find("properties")
    assert block is not None
    return {child.attrib["name"]: child.attrib["value"] for child in block.findall("property")}


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )


def _git_available() -> bool:
    return shutil.which("git") is not None and (REPO_ROOT / ".git").exists()


def _introducing_commit() -> str | None:
    log = _git("log", "--diff-filter=A", "--format=%H", "--", "examples/demo_suite")
    if log.returncode != 0 or not log.stdout.split():
        return None
    return log.stdout.split()[-1]


def _literal_assignment(module: ast.Module, name: str) -> Any:
    for node in ast.walk(module):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} is not assigned a literal in the demo suite")


def _keyword_argument(module: ast.Module, name: str) -> Any:
    for node in ast.walk(module):
        if isinstance(node, ast.keyword) and node.arg == name:
            return ast.literal_eval(node.value)
    raise AssertionError(f"no call in the demo suite passes {name}=")


def _prompt_text(case: dict[str, Any]) -> str:
    """Everything the app can put in front of the model: system, documents, question."""
    parts: list[str] = []
    system = case.get("system")
    if system:
        parts.append(str(system))
    case_input = case["input"]
    if isinstance(case_input, str):
        parts.append(case_input)
    else:
        parts.extend(str(document) for document in case_input.get("documents", []))
        parts.append(str(case_input["question"]))
    return "\n".join(parts)


def _probatio_imports(module: ast.Module) -> list[str]:
    """The names ``test_demo.py`` imports from ``probatio``, in source order."""
    for node in ast.walk(module):
        if isinstance(node, ast.ImportFrom) and node.module == "probatio":
            return [alias.name for alias in node.names]
    raise AssertionError("test_demo.py does not import from probatio")


@pytest.fixture
def demo_copy(pytester: pytest.Pytester) -> Path:
    """A copy of the frozen suite in a temporary rootdir, so a run writes nothing into it."""
    target = pytester.path / "demo_suite"
    shutil.copytree(DEMO, target, ignore=shutil.ignore_patterns("__pycache__", ".probatio"))
    return target


# -- gate condition 5 --------------------------------------------------------------------------


def test_the_public_api_the_demo_imports_is_complete() -> None:
    """Every name ``test_demo.py`` imports now exists, which is what lets the guard go."""
    imported = _probatio_imports(ast.parse((DEMO / "test_demo.py").read_text(encoding="utf-8")))
    missing = [name for name in imported if not hasattr(probatio, name)]
    assert missing == [], f"the demo suite still cannot be imported: {missing}"


def test_the_import_guard_is_gone_and_nothing_replaced_it() -> None:
    text = (DEMO / "conftest.py").read_text(encoding="utf-8")
    assert "collect_ignore" not in text
    assert "except ImportError" not in text
    assert not (REPO_ROOT / "conftest.py").exists(), (
        "the repository-level exclusion (DECISIONS 16) is Phase 9's to delete"
    )


def test_the_demo_suite_differs_from_its_introducing_commit_by_the_deletion_alone() -> None:
    """Gate condition 5, with the one sanctioned exception `CLAUDE.md` names (DECISIONS 62)."""
    if not _git_available():
        print("git is unavailable here; the byte-identity check has nothing to compare against")
        return
    commit = _introducing_commit()
    if commit is None:
        print("examples/demo_suite is not committed yet; nothing to compare against")
        return

    changed = _git("diff", "--name-only", commit, "--", "examples/demo_suite").stdout.split()
    assert changed == [GUARDED_FILE], (
        f"examples/demo_suite changed in {changed} since {commit[:12]}; the only permitted "
        f"difference is the deletion of the import guard from {GUARDED_FILE}."
    )

    original = _git("show", f"{commit}:{GUARDED_FILE}").stdout
    assert SANCTIONED_DELETION in original, "the guard is not where Phase 1 put it"
    assert (DEMO / "conftest.py").read_text(encoding="utf-8") == original.replace(
        SANCTIONED_DELETION, "", 1
    ), "conftest.py differs from the Phase 1 file by more than the deleted guard"

    status = _git("status", "--porcelain", "--", "examples/demo_suite").stdout
    untracked = [line for line in status.splitlines() if line.startswith("??")]
    assert untracked == [], f"nothing new belongs inside the frozen directory: {untracked}"


def test_every_scripted_keyword_selects_exactly_one_case() -> None:
    """Each ``RESPONSES`` key appears in one case's prompt, and in no distractor."""
    conftest = ast.parse((DEMO / "conftest.py").read_text(encoding="utf-8"))
    test_module = ast.parse((DEMO / "test_demo.py").read_text(encoding="utf-8"))
    keywords: list[str] = list(_literal_assignment(conftest, "RESPONSES"))
    distractors: list[str] = list(_keyword_argument(test_module, "distractors"))
    assert keywords and distractors

    prompts = {}
    for path in sorted((DEMO / "cases").glob("*.yaml")):
        case = yaml.safe_load(path.read_text(encoding="utf-8"))
        prompts[str(case["id"])] = _prompt_text(case)
    assert len(prompts) == len(list((DEMO / "cases").glob("*.yaml")))

    for keyword in keywords:
        matched = [case_id for case_id, prompt in prompts.items() if keyword in prompt]
        assert len(matched) == 1, (
            f"keyword {keyword!r} selects {matched}; it must select exactly one case, otherwise "
            "the scripted provider answers the wrong question and the relations mean nothing"
        )
        for distractor in distractors:
            assert keyword not in distractor, (
                f"distractor {distractor!r} contains the keyword {keyword!r}, so "
                "distractor_robust would change the answer instead of leaving it alone"
            )


# -- the suite runs -------------------------------------------------------------------------------


def test_the_demo_suite_collects_and_passes(pytester: pytest.Pytester, demo_copy: Path) -> None:
    """Requirement 12: the frozen suite passes, unmodified, offline."""
    collected = pytester.runpytest_subprocess("demo_suite", "--collect-only", "-q")
    assert collected.ret == pytest.ExitCode.OK
    assert "12 tests collected" in collected.stdout.str()

    result = pytester.runpytest_subprocess("demo_suite")
    result.assert_outcomes(passed=12)
    output = result.stdout.str()
    assert "cases:" in output and "relations:" in output


def test_runs_five_prints_a_stability_section_and_the_flaky_case_passes_at_point_eight(
    pytester: pytest.Pytester, demo_copy: Path
) -> None:
    """Requirement 12, and the command the demo's README tells a reader to run."""
    result = pytester.runpytest_subprocess("demo_suite", "--runs", "5")
    result.assert_outcomes(passed=12)
    output = result.stdout.str()
    assert "stability score:" in output
    assert "cases whose Wilson lower bound is below their floor:" in output
    flaky = next(line for line in output.splitlines() if "flu-antivirals-flaky" in line)
    assert "0.80" in flaky, flaky
    assert "pass" in flaky and "FAIL" not in flaky


def test_the_expected_fail_cases_report_is_readable(
    pytester: pytest.Pytester, demo_copy: Path
) -> None:
    """Requirement 12: the suite stays green while the report shows the failing case."""
    result = pytester.runpytest_subprocess("demo_suite")
    result.assert_outcomes(passed=12)
    row = next(
        line
        for line in result.stdout.str().splitlines()
        if "anxiety-expected-fail" in line and "FAIL" in line
    )
    assert "1/3" in row, "one of its three assertions passes; the report says which"


def test_the_relations_table_reports_the_demos_violation_rates(
    pytester: pytest.Pytester, demo_copy: Path
) -> None:
    """The two headline features, in one table, from the frozen example."""
    output = pytester.runpytest_subprocess("demo_suite").stdout.str()
    names = ("order_invariant", "distractor_robust", "format_jitter", "paraphrase_invariant")
    stripped = [line.strip() for line in output.splitlines()]
    rows = {line.split()[0]: line for line in stripped if line.startswith(names)}
    assert set(rows) == {
        "order_invariant",
        "distractor_robust",
        "format_jitter",
        "paraphrase_invariant",
    }
    assert "0.00" in rows["order_invariant"] and "0.00" in rows["distractor_robust"]
    assert "htn-definition" in rows["format_jitter"]
    assert "htn-definition" in rows["paraphrase_invariant"]


def test_replay_with_no_tapes_and_no_override_fails_with_a_missing_cassette_error(
    pytester: pytest.Pytester, demo_copy: Path
) -> None:
    """Requirement 12. The demo's fixtures step aside for a live provider (DECISIONS 9), and
    replay never calls the adapter it wraps, so no CLI subprocess is ever started."""
    result = pytester.runpytest_subprocess(
        "demo_suite",
        "--probatio-provider",
        "claude-cli",
        "--probatio-model",
        "claude-x",
        "--cassette=replay",
        "--cassette-dir",
        "empty-tapes",
    )
    assert result.ret != 0
    assert "MissingCassetteError" in result.stdout.str()


def test_the_demo_writes_its_baselines_under_rootdir_and_not_into_itself(
    pytester: pytest.Pytester, demo_copy: Path
) -> None:
    """The demo's README says so, and the frozen directory has to stay frozen while it runs."""
    pytester.runpytest_subprocess("demo_suite").assert_outcomes(passed=12)
    recorded = sorted(
        path.name for path in (pytester.path / ".probatio" / "baseline" / "test_demo").glob("*")
    )
    assert recorded == ["htn-definition.json", "htn-first-line.json", "t2d-metformin.json"]
    assert not (demo_copy / ".probatio").exists()


# -- the two report files, from the frozen suite --------------------------------------------------


def test_the_demo_under_runs_five_fills_both_report_files(
    pytester: pytest.Pytester, demo_copy: Path
) -> None:
    """Spec §3.11 and §3.12 acceptance, on the example rather than on a synthetic suite."""
    result = pytester.runpytest_subprocess(
        "demo_suite",
        "--runs",
        "5",
        "--probatio-junit",
        "j.xml",
        "--probatio-results",
        "r.json",
    )
    result.assert_outcomes(passed=12)

    report = read_results(pytester.path / "r.json")
    assert (
        RunReport.model_validate(json.loads((pytester.path / "r.json").read_text(encoding="utf-8")))
        == report
    )
    assert len(report.cases) == 12

    suite = ET.parse(pytester.path / "j.xml").getroot().find("testsuite")
    assert suite is not None
    assert suite.attrib["name"] == "probatio"
    assert suite.attrib["tests"] == "12"
    assert suite.attrib["failures"] == "1", "only the expected-fail case fails its verdict"

    entries = {
        (element.attrib["classname"], element.attrib["name"]): element
        for element in suite.findall("testcase")
    }
    assert len(entries) == 12, "no two entries share a (node id, case id) key"


def test_the_expected_fail_case_carries_a_failure_and_the_flaky_one_reads_point_eight(
    pytester: pytest.Pytester, demo_copy: Path
) -> None:
    """Requirement 3, on the two cases the demo suite exists to demonstrate."""
    pytester.runpytest_subprocess(
        "demo_suite", "--runs", "5", "--probatio-junit", "j.xml"
    ).assert_outcomes(passed=12)
    suite = ET.parse(pytester.path / "j.xml").getroot().find("testsuite")
    assert suite is not None
    by_name = {element.attrib["name"]: element for element in suite.findall("testcase")}

    failing = by_name["anxiety-expected-fail"]
    failure = failing.find("failure")
    assert failure is not None and failure.text is not None
    assert "contains" in failure.text and "not_contains" in failure.text

    flaky = by_name["flu-antivirals-flaky"]
    assert _demo_properties(flaky)["pass_rate"] == "0.8"


def test_a_case_checked_by_two_of_the_demos_tests_appears_twice(
    pytester: pytest.Pytester, demo_copy: Path
) -> None:
    """Requirement 2: ``htn-definition`` and ``t2d-metformin`` each run under two test functions."""
    pytester.runpytest_subprocess(
        "demo_suite", "--probatio-junit", "j.xml", "--probatio-results", "r.json"
    ).assert_outcomes(passed=12)
    suite = ET.parse(pytester.path / "j.xml").getroot().find("testsuite")
    assert suite is not None
    for case_id in ("htn-definition", "t2d-metformin"):
        classnames = sorted(
            element.attrib["classname"]
            for element in suite.findall("testcase")
            if element.attrib["name"] == case_id
        )
        assert len(classnames) == 2, case_id
        assert classnames[0].endswith(f"test_case[{case_id}]")
        assert classnames[1].endswith(f"test_paraphrase[{case_id}]")

    keys = [case_key(case) for case in read_results(pytester.path / "r.json").cases]
    assert len(set(keys)) == len(keys)
