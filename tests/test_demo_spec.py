"""Phase 1 checks on ``examples/demo_suite/``, the executable design specification.

The demo suite is the specification the public API is written against, so every check here had to
hold before a single line of that API existed and has to keep holding as it arrives. The three
checks are: collection tracks the public API exactly, neither ahead of it nor behind; the
directory is byte-identical to the commit that introduced it; and the keyword table in
``conftest.py`` really does select one case each, which is what makes the demo's violation rates
mean anything.

The only use of Probatio here is ``hasattr`` on the module, to ask which of the names the demo
imports exist yet. Nothing here calls the API.
"""

from __future__ import annotations

import ast
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

import probatio

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


def _probatio_imports(module: ast.Module) -> list[str]:
    """The names ``test_demo.py`` imports from ``probatio``, in source order."""
    for node in ast.walk(module):
        if isinstance(node, ast.ImportFrom) and node.module == "probatio":
            return [alias.name for alias in node.names]
    raise AssertionError("test_demo.py does not import from probatio")


def test_demo_suite_collection_tracks_the_public_api(pytester: pytest.Pytester) -> None:
    """The suite collects exactly when every name it imports exists, and errors only on those.

    Phase 1's guard in the demo's own ``conftest.py`` probes ``FakeProvider``, so it stopped
    firing when Phase 2 exported it (``DECISIONS.md`` entry 16, and the repository-level
    ``conftest.py`` that repeats the exclusion for ``pytest -q``). Until the last of the names
    below exists, importing ``test_demo.py`` in isolation is expected to fail on the first one
    that does not — and on nothing else, which is what this test is for. Phase 9 takes the other
    branch: everything imports, and the suite collects and passes.
    """
    imported = _probatio_imports(ast.parse((DEMO / "test_demo.py").read_text(encoding="utf-8")))
    missing = [name for name in imported if not hasattr(probatio, name)]
    shutil.copytree(
        DEMO, pytester.path / "demo_suite", ignore=shutil.ignore_patterns("__pycache__")
    )
    result = pytester.runpytest_subprocess("demo_suite", "--collect-only")

    if not missing:
        assert result.ret == pytest.ExitCode.OK
        assert "ERRORS" not in result.stdout.str()
        return

    assert result.ret == pytest.ExitCode.INTERRUPTED
    result.stdout.fnmatch_lines(
        [
            "*collected 0 items / 1 error*",
            "*ERROR collecting demo_suite/test_demo.py*",
            f"*ImportError: cannot import name '{missing[0]}' from 'probatio'*",
        ]
    )
    assert result.stdout.str().count("ERROR collecting") == 1, (
        "the only thing wrong with the demo suite must be the exports it is waiting for"
    )


def test_demo_suite_is_byte_identical_to_its_introducing_commit() -> None:
    """Gate condition 5: the directory never changes after the commit that added it.

    The comparison is against the **working tree**, not against ``HEAD``: an edit that has not
    been committed yet is exactly the edit this gate exists to catch, and comparing two commits
    would pass right up until the moment the damage was recorded. ``git diff`` only sees tracked
    files, so ``git status --porcelain`` runs alongside it to catch a new untracked file dropped
    into the frozen directory. Both ignore ``__pycache__``, which is git-ignored.
    """
    if shutil.which("git") is None or not (REPO_ROOT / ".git").exists():
        print("git is unavailable here; the byte-identity check has nothing to compare against")
        return

    log = _git("log", "--diff-filter=A", "--format=%H", "--", "examples/demo_suite")
    if log.returncode != 0 or not log.stdout.split():
        print("examples/demo_suite is not committed yet; nothing to compare against")
        return

    introducing_commit = log.stdout.split()[-1]
    diff = _git("diff", "--quiet", introducing_commit, "--", "examples/demo_suite")
    names = _git("diff", "--name-only", introducing_commit, "--", "examples/demo_suite")
    assert diff.returncode == 0, (
        f"examples/demo_suite has changed since {introducing_commit[:12]}, which introduced it: "
        f"{names.stdout.split()}. The example is the specification; change the implementation "
        "instead, or record a sanctioned exception in DECISIONS.md."
    )

    status = _git("status", "--porcelain", "--", "examples/demo_suite")
    assert status.stdout == "", (
        "examples/demo_suite has uncommitted changes or untracked files: "
        f"{status.stdout.splitlines()}. The example is frozen; nothing new belongs inside it."
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


def test_the_repository_level_exclusion_lives_exactly_as_long_as_it_is_needed() -> None:
    """The root ``conftest.py`` is a Phase 2-to-8 stopgap; Phase 9 has to delete it.

    It exists because the frozen guard probes ``FakeProvider``, which now exists, so ``pytest -q``
    would otherwise fail to collect ``test_demo.py``. Once every name the demo imports is
    exported, the exclusion would silently hide the suite the gate is supposed to run, so this
    test turns "remember to delete it" into a failure.
    """
    imported = _probatio_imports(ast.parse((DEMO / "test_demo.py").read_text(encoding="utf-8")))
    missing = [name for name in imported if not hasattr(probatio, name)]
    root_conftest = REPO_ROOT / "conftest.py"
    excluded = root_conftest.exists() and "demo_suite/test_demo.py" in root_conftest.read_text(
        encoding="utf-8"
    )
    assert excluded is bool(missing), (
        "the root conftest.py must exclude the demo suite while "
        f"{missing or 'no'} exports are missing, and must not once they exist"
    )
