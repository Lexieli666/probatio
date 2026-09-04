"""Probatio: a pytest plugin for regression-testing LLM applications.

The two headline features are metamorphic relations (semantics-preserving input transformations
that must not change a case's verdict, reported as a per-relation violation rate) and flakiness
statistics (repeated execution with per-case pass rates, Wilson confidence intervals and a
suite-level stability score).

What is exported grows with the phases that implement it. Phase 2 exports the foundations: the
case model and its loader, the provider protocol with its two offline fakes, and the error
hierarchy. The relation decorators, ``flaky_tolerant``, ``AssertionResult``, ``CaseResult`` and
``RunReport`` arrive with their own phases; until then ``examples/demo_suite/test_demo.py`` cannot
be imported, which is what its ``conftest.py`` guard is for.

``__version__`` is the single source of truth for the distribution version, which
``pyproject.toml`` reads through hatchling.
"""

from __future__ import annotations

from .case import LLMCase, load_cases
from .errors import (
    BaselineDriftError,
    BudgetExceededError,
    JudgeOutputError,
    MissingCassetteError,
    MissingVariantsError,
    ProbatioConfigError,
    ProbatioError,
    StaleCassetteError,
)
from .providers import Completion, FakeProvider, Provider, ScriptedProvider

__version__ = "0.1.0.dev0"

__all__ = [
    "BaselineDriftError",
    "BudgetExceededError",
    "Completion",
    "FakeProvider",
    "JudgeOutputError",
    "LLMCase",
    "MissingCassetteError",
    "MissingVariantsError",
    "ProbatioConfigError",
    "ProbatioError",
    "Provider",
    "ScriptedProvider",
    "StaleCassetteError",
    "__version__",
    "load_cases",
]
