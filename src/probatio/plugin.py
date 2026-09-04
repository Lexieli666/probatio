"""The pytest plugin entry point, registered as the ``pytest11`` plugin ``probatio``.

Because this module is loaded by pytest in every session of every project that installs Probatio,
it must import cleanly, quickly and without side effects. Options, fixtures and the session hooks
are added by the later phases; Phase 8 adds only the marker registration the relation decorators
need, so that a suite using them under ``-W error`` or ``--strict-markers`` does not fail on an
unknown mark. The ``flaky_tolerant`` marker arrives with Phase 9, alongside the fixtures.
"""

from __future__ import annotations

import pytest

from .metamorphic import RELATION_MARKER

__all__ = ["RELATION_MARKER", "pytest_configure"]

RELATION_MARKER_HELP = (
    f"{RELATION_MARKER}(relation): a probatio metamorphic relation to evaluate on every case "
    "this test runs. Applied by the order_invariant, distractor_robust, format_jitter and "
    "paraphrase_invariant decorators; violation rates are reported alongside the case and never "
    "change its verdict."
)
"""The one-line description ``pytest --markers`` prints for the relation marker."""


def pytest_configure(config: pytest.Config) -> None:
    """Register Probatio's markers so that no suite using them sees an unknown-mark warning.

    Args:
        config: The session's configuration.
    """
    config.addinivalue_line("markers", RELATION_MARKER_HELP)
