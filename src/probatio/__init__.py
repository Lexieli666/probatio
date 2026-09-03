"""Probatio: a pytest plugin for regression-testing LLM applications.

The two headline features are metamorphic relations (semantics-preserving input transformations
that must not change a case's verdict, reported as a per-relation violation rate) and flakiness
statistics (repeated execution with per-case pass rates, Wilson confidence intervals and a
suite-level stability score).

Nothing is exported yet: the public surface listed in the specification's engineering baseline
arrives with the phases that implement it. ``__version__`` is the single source of truth for the
distribution version, which ``pyproject.toml`` reads through hatchling.
"""

__version__ = "0.1.0.dev0"

__all__ = ["__version__"]
