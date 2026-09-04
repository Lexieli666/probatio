"""The two substring assertions: ``contains`` and ``not_contains``.

Both are case-insensitive by default, because an app that capitalises a heading differently after
a prompt tweak has not regressed, and a suite whose assertions fire on that stops being read. A
case that really is testing casing sets ``case_sensitive: true``.

Both report a fraction as their score even though their verdict is boolean, so that a snapshot in
``scores`` mode can see a case degrade from four needles matched to three before the run turns
red. For ``contains`` the score is the fraction of all declared substrings — ``all`` and ``any``
together — that appear; for ``not_contains`` it is the fraction of forbidden substrings absent.
"""

from __future__ import annotations

from ..case import ContainsAssertion, NotContainsAssertion
from .result import AssertionResult

__all__ = ["evaluate_contains", "evaluate_not_contains"]


def _present(needle: str, haystack: str, *, case_sensitive: bool) -> bool:
    """Whether ``needle`` occurs in ``haystack``, folding case unless asked not to."""
    if case_sensitive:
        return needle in haystack
    return needle.casefold() in haystack.casefold()


def _sensitivity(case_sensitive: bool) -> str:
    """Name the matching mode, so a detail explains a verdict that looks wrong at a glance."""
    return "case-sensitive" if case_sensitive else "case-insensitive"


def _listed(needles: list[str]) -> str:
    """Render substrings for a message: quoted, comma-separated, in declaration order."""
    return ", ".join(repr(needle) for needle in needles)


def evaluate_contains(assertion: ContainsAssertion, output: str) -> AssertionResult:
    """Check that every ``all`` substring and at least one ``any`` substring appear.

    Args:
        assertion: The declaration, holding ``all``, ``any`` and ``case_sensitive``.
        output: The text under test.

    Returns:
        A result scoring the fraction of the declared substrings that appear, whose detail names
        the missing required substrings and the ``any`` group when none of it matched.
    """
    sensitive = assertion.case_sensitive
    missing = [
        needle
        for needle in assertion.all_
        if not _present(needle, output, case_sensitive=sensitive)
    ]
    matched_any = [
        needle for needle in assertion.any_ if _present(needle, output, case_sensitive=sensitive)
    ]
    declared = assertion.all_ + assertion.any_
    matched = len(assertion.all_) - len(missing) + len(matched_any)
    tally = f"matched {matched}/{len(declared)} substrings, {_sensitivity(sensitive)}"

    faults: list[str] = []
    if missing:
        faults.append(f"missing required {_listed(missing)}")
    if assertion.any_ and not matched_any:
        faults.append(f"none of {_listed(assertion.any_)} appear")
    detail = f"{'; '.join(faults)}; {tally}" if faults else tally
    return AssertionResult(
        assertion_type="contains",
        passed=not faults,
        score=matched / len(declared),
        detail=detail,
    )


def evaluate_not_contains(assertion: NotContainsAssertion, output: str) -> AssertionResult:
    """Check that none of the forbidden substrings appear.

    Args:
        assertion: The declaration, holding ``all`` and ``case_sensitive``.
        output: The text under test.

    Returns:
        A result scoring the fraction of forbidden substrings that are absent, whose detail names
        the ones that appeared.
    """
    sensitive = assertion.case_sensitive
    present = [
        needle for needle in assertion.all_ if _present(needle, output, case_sensitive=sensitive)
    ]
    absent = len(assertion.all_) - len(present)
    tally = f"absent {absent}/{len(assertion.all_)} forbidden substrings, {_sensitivity(sensitive)}"
    detail = f"forbidden {_listed(present)} appears; {tally}" if present else tally
    return AssertionResult(
        assertion_type="not_contains",
        passed=not present,
        score=absent / len(assertion.all_),
        detail=detail,
    )
