"""Suite ``test_live_variance``: the same fifteen cases, answered ten times each.

Phase 15's experiment A. ``test_live.py`` beside it answers each case once and asks four
metamorphic relations what a semantics-preserving *change to the input* does to the verdict. This
module changes nothing at all and asks what **repetition alone** does to it, which is the question
a single evaluation run cannot answer about itself.

The system under test, the cases, the rubric and the model are ``test_live.py``'s, unchanged; the
only difference is ``--runs 10`` and where the tapes and baselines live
(``cassettes-n10/`` and ``.probatio/baseline-live-n10/``), so that neither recording disturbs the
other.

**There are no relation decorators and no ``flaky_tolerant`` marker here, deliberately.** The
study measures the cases' own verdicts, so every call has to be a call the case itself made. The
four relations attach eleven evaluations to each run of each case — the original and ten variants
— which would take 300 live calls to some 3,300 and would mix run-to-run variation with
variant-to-variant variation in one number with no way to separate them again. ``flaky_tolerant``
is absent for the same kind of reason: it changes the pass/fail rule, and here the pass *rate* is
the measurement, not the thing being ruled on.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app_live import answer

from probatio import load_cases

HERE = Path(__file__).parent
CASES = load_cases(HERE / "cases")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_case(case, probatio, provider):
    """Exact assertions, budget and snapshot on one live answer per case, repeated under --runs."""
    probatio.check(case, sut=lambda c: answer(c, provider))
