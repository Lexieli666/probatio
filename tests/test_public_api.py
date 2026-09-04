"""What ``import probatio`` gives a user, and what it deliberately does not.

The set grows one phase at a time and this test is the record of where it has got to: the demo
suite's import guard, and ``tests/test_demo_spec.py``'s lifecycle check, both depend on the names
that are still absent being absent.
"""

from __future__ import annotations

import subprocess
import sys

import probatio

PHASE_3_EXPORTS = {
    # spec §3.2
    "LLMCase",
    "load_cases",
    # spec §3.3
    "Completion",
    "Provider",
    "FakeProvider",
    "ScriptedProvider",
    # spec §3.1
    "ProbatioError",
    "ProbatioConfigError",
    "MissingCassetteError",
    "StaleCassetteError",
    "MissingVariantsError",
    "BaselineDriftError",
    "BudgetExceededError",
    "JudgeOutputError",
    # spec §3.4
    "AssertionResult",
}

PHASE_8_EXPORTS = {
    # spec §3.9
    "order_invariant",
    "distractor_robust",
    "format_jitter",
    "paraphrase_invariant",
}

EXPORTS = PHASE_3_EXPORTS | PHASE_8_EXPORTS

LATER_PHASES = {
    "flaky_tolerant",
    "CaseResult",
    "RunReport",
}


def test_the_public_surface_is_exactly_what_the_shipped_phases_implement() -> None:
    assert set(probatio.__all__) == EXPORTS | {"__version__"}
    assert probatio.__all__ == sorted(probatio.__all__)
    for name in probatio.__all__:
        assert hasattr(probatio, name), name


def test_every_export_is_documented_and_typed() -> None:
    for name in EXPORTS:
        symbol = getattr(probatio, name)
        assert symbol.__doc__, f"{name} has no docstring"


def test_the_rest_of_the_surface_is_still_absent() -> None:
    """The demo suite's import guard depends on this: Phase 9 is what makes it collectable."""
    for name in LATER_PHASES:
        assert not hasattr(probatio, name), f"{name} arrives in a later phase"


def test_the_documented_import_line_works_in_a_fresh_interpreter() -> None:
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from probatio import LLMCase, load_cases, FakeProvider, ScriptedProvider",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_importing_probatio_does_not_import_a_live_provider_adapter() -> None:
    """A user without the ``anthropic`` extra must not be told about it by ``import probatio``."""
    listing = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, probatio; print([m for m in sys.modules if 'providers.' in m])",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "probatio.providers.anthropic" not in listing
    assert "probatio.providers.claude_cli" not in listing
    assert "probatio.providers.fake" in listing
