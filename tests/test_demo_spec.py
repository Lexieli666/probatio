"""Phase 1 checks on ``examples/demo_suite/``, the executable design specification.

None of these tests imports Probatio's public API. The demo suite is the specification that API is
written against, so every check here has to hold before a single line of it exists, and has to keep
holding once it does. The three checks are: the suite collects cleanly; the directory is
byte-identical to the commit that introduced it; and the keyword table in ``conftest.py`` really
does select one case each, which is what makes the demo's violation rates mean anything.
"""

from __future__ import annotations

import ast
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO = REPO_ROOT / "examples" / "demo_suite"


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )


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


def test_demo_suite_collects_cleanly(pytester: pytest.Pytester) -> None:
    """The suite collects with no collection failure and, until Phase 9, no tests."""
    shutil.copytree(
        DEMO, pytester.path / "demo_suite", ignore=shutil.ignore_patterns("__pycache__")
    )
    result = pytester.runpytest_subprocess("demo_suite", "--collect-only")

    assert result.ret == pytest.ExitCode.NO_TESTS_COLLECTED
    result.stdout.fnmatch_lines(["*collected 0 items*", "*no tests collected*"])
    assert "ERRORS" not in result.stdout.str()


def test_demo_suite_is_byte_identical_to_its_introducing_commit() -> None:
    """Gate condition 5: the directory never changes after the commit that added it."""
    if shutil.which("git") is None or not (REPO_ROOT / ".git").exists():
        print("git is unavailable here; the byte-identity check has nothing to compare against")
        return

    log = _git("log", "--diff-filter=A", "--format=%H", "--", "examples/demo_suite")
    if log.returncode != 0 or not log.stdout.split():
        print("examples/demo_suite is not committed yet; nothing to compare against")
        return

    introducing_commit = log.stdout.split()[-1]
    diff = _git("diff", "--quiet", introducing_commit, "HEAD", "--", "examples/demo_suite")
    names = _git("diff", "--name-only", introducing_commit, "HEAD", "--", "examples/demo_suite")
    assert diff.returncode == 0, (
        f"examples/demo_suite has changed since {introducing_commit[:12]}, which introduced it: "
        f"{names.stdout.split()}. The example is the specification; change the implementation "
        "instead, or record a sanctioned exception in DECISIONS.md."
    )


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
