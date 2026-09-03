"""Probatio demo suite: the executable design specification.

This file is the public API as a user writes it. Phase 9 makes it pass unmodified; the gate's
byte-identity test rejects any later edit. Tags on the cases route them to the test function
whose decorators fit: ``paraphrase`` cases have frozen variants on disk, the ``expected-fail`` case
shows what a failing report looks like while the suite stays green, and the ``flaky`` case runs
against a scripted provider that fails one call in five.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app import answer

from probatio import (
    LLMCase,
    distractor_robust,
    flaky_tolerant,
    format_jitter,
    load_cases,
    order_invariant,
    paraphrase_invariant,
)

HERE = Path(__file__).parent
CASES = load_cases(HERE / "cases")


def tagged(tag: str) -> list[LLMCase]:
    """Cases carrying ``tag``."""
    return [c for c in CASES if tag in c.tags]


REGULAR = [c for c in CASES if not ({"expected-fail", "flaky"} & set(c.tags))]


@pytest.mark.parametrize("case", REGULAR, ids=lambda c: c.id)
@order_invariant(field="input.documents", k=3)
@distractor_robust(
    field="input.documents",
    distractors=["Clinic parking is free after 6 pm."],
    positions=("start", "end"),
)
@format_jitter(field="input.question")
def test_case(case, probatio, provider):
    """Exact assertions, budget and snapshot, plus three relations, on every regular case."""
    probatio.check(case, sut=lambda c: answer(c, provider))


@pytest.mark.parametrize("case", tagged("paraphrase"), ids=lambda c: c.id)
@paraphrase_invariant(k=3, field="input.question", variants_dir=HERE / "variants")
def test_paraphrase(case, probatio, provider):
    """Frozen paraphrases from variants/<case_id>.yaml; never generated at test time."""
    probatio.check(case, sut=lambda c: answer(c, provider))


@pytest.mark.parametrize("case", tagged("expected-fail"), ids=lambda c: c.id)
def test_expected_fail(case, probatio, provider):
    """The report shows this case failing; the suite stays green."""
    with pytest.raises(AssertionError):
        probatio.check(case, sut=lambda c: answer(c, provider))


@pytest.mark.parametrize("case", tagged("flaky"), ids=lambda c: c.id)
@flaky_tolerant(p=0.8, n=5)
def test_flaky(case, probatio, scripted_provider):
    """One failure in five runs: a pass rate of 0.8 is the honest bar for this case."""
    probatio.check(case, sut=lambda c: answer(c, scripted_provider))
