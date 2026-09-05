"""Phase 8, kept through Phase 9: a marked test warns about nothing and survives strict markers."""

from __future__ import annotations

import pytest

from probatio import plugin
from probatio.metamorphic import RELATION_MARKER

SUITE = """
from probatio import order_invariant


@order_invariant(field="input.documents", k=3)
def test_marked():
    assert True
"""


def test_the_plugin_exports_the_marker_name_it_registers() -> None:
    assert plugin.RELATION_MARKER == RELATION_MARKER
    assert "RELATION_MARKER" in plugin.__all__


def test_the_marker_is_listed_by_pytest_markers(pytester: pytest.Pytester) -> None:
    result = pytester.runpytest_subprocess("--markers")
    result.stdout.fnmatch_lines([f"@pytest.mark.{RELATION_MARKER}(relation):*"])


def test_a_marked_test_produces_no_unknown_marker_warning(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(test_marked=SUITE)
    result = pytester.runpytest_subprocess("-W", "error::pytest.PytestUnknownMarkWarning")
    result.assert_outcomes(passed=1)
    assert "PytestUnknownMarkWarning" not in result.stdout.str()


def test_the_marker_survives_strict_markers(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(test_marked=SUITE)
    pytester.runpytest_subprocess("--strict-markers").assert_outcomes(passed=1)


def test_the_relation_instance_is_readable_off_the_marked_item(pytester: pytest.Pytester) -> None:
    """This is what Phase 9's ``check`` reads to know which relations a test declared."""
    pytester.makepyfile(
        test_reads="""
        import pytest
        from probatio import format_jitter, order_invariant
        from probatio.metamorphic import RELATION_MARKER


        @order_invariant(field="input.documents", k=2)
        @format_jitter(field="input.question")
        def test_two_relations(request):
            names = [
                mark.args[0].name
                for mark in request.node.iter_markers(RELATION_MARKER)
            ]
            assert sorted(names) == ["format_jitter", "order_invariant"]
        """
    )
    pytester.runpytest_subprocess().assert_outcomes(passed=1)
