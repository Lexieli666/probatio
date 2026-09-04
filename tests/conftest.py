"""Shared test configuration: ``pytester``, and read access to the frozen demo suite.

``examples/demo_suite/`` is the executable design specification, so the scripted answers and the
two fake judge verdicts it commits are the values several test modules have to be right about.
They are read out of the committed file through the fixtures below rather than copied into a test,
so that a change to either side shows up as a failure — and as fixtures rather than as a helper
module, so that nothing under ``tests/`` imports a sibling by bare name.

Paths are module constants here because a test module that parametrises over the demo's cases
needs them at collection time, before any fixture has run; the fixtures wrap them for the tests
that only need them while running.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType

import pytest

from probatio import LLMCase

pytest_plugins = ["pytester"]

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO = REPO_ROOT / "examples" / "demo_suite"
DEMO_RUBRICS = DEMO / "rubrics"
DEMO_CONFTEST_MODULE = "demo_suite_conftest"
DEMO_APP_MODULE = "demo_suite_app"


def _import_demo_module(name: str, filename: str) -> Iterator[ModuleType]:
    """Import one file of the frozen demo suite as a module of its own, then unregister it."""
    spec = importlib.util.spec_from_file_location(name, DEMO / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(name, None)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """The repository root."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def demo_dir() -> Path:
    """The frozen demo suite's directory."""
    return DEMO


@pytest.fixture(scope="session")
def demo_rubrics() -> Path:
    """The demo suite's own ``rubrics/`` directory, which lives below pytest's rootdir."""
    return DEMO_RUBRICS


@pytest.fixture(scope="session")
def demo_conftest() -> Iterator[ModuleType]:
    """The demo suite's ``conftest.py``, imported as a plain module for its committed constants."""
    yield from _import_demo_module(DEMO_CONFTEST_MODULE, "conftest.py")


@pytest.fixture(scope="session")
def demo_app() -> Iterator[ModuleType]:
    """The demo suite's ``app.py``: the system under test the relations are measured against.

    The relation tests need the prompt the app actually builds, because the demo's scripted
    provider is keyed by a substring of it. Reaching for ``scripted_answer`` instead would answer
    by the case's metadata keyword and so bypass the very matching a format variant breaks.
    """
    yield from _import_demo_module(DEMO_APP_MODULE, "app.py")


@pytest.fixture(scope="session")
def judge_pass(demo_conftest: ModuleType) -> str:
    """The demo suite's passing judge reply, verbatim."""
    return str(demo_conftest.JUDGE_PASS)


@pytest.fixture(scope="session")
def judge_fail(demo_conftest: ModuleType) -> str:
    """The demo suite's failing judge reply, verbatim."""
    return str(demo_conftest.JUDGE_FAIL)


@pytest.fixture(scope="session")
def fake_judge(demo_conftest: ModuleType) -> Callable[[str], str]:
    """The demo suite's fake judge: it fails the keyword-miss fallback and nothing else."""
    judge: Callable[[str], str] = demo_conftest.fake_judge
    return judge


@pytest.fixture(scope="session")
def scripted_answer(demo_conftest: ModuleType) -> Callable[[LLMCase], str]:
    """The answer the demo's fake provider gives for a case: by keyword, or the flaky script."""

    def answer(case: LLMCase) -> str:
        keyword = case.metadata.get("keyword")
        if keyword is None:
            return str(demo_conftest.FLU_ANSWER)
        return str(demo_conftest.RESPONSES[keyword])

    return answer
