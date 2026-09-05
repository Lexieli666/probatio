"""Suite ``test_live``: fifteen Consilium golden items answered by a live model, then replayed.

This is the only suite in the repository whose tapes were recorded against a real model. What it
tests is ``app_live.py``, a single-call grounded question-answering app — **not** Consilium's
pipeline; ``examples/consilium/`` beside it is the suite that replays Consilium's own answers.

Every case carries all four relations and a judge, which is what the offline suite cannot have:
a metamorphic variant is a different prompt and so a different cassette key, and a judge is a
provider call, so both need tapes that Consilium's published traces do not contain. Here they were
recorded, so `README.md`'s replay command reproduces every relation violation rate and every judge
verdict at no cost and with no key.

The judge's rubric is named, not pathed: ``rubrics/faithfulness.md`` beside this file is found
because a rubric name resolves against the requesting test module's directory as well as against
rootdir (DECISIONS 23).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app_live import answer

from probatio import (
    distractor_robust,
    format_jitter,
    load_cases,
    order_invariant,
    paraphrase_invariant,
)

HERE = Path(__file__).parent
CASES = load_cases(HERE / "cases")

DISTRACTOR = (
    "Vitamin D deficiency is diagnosed on a serum 25-hydroxyvitamin D level and is treated with "
    "oral cholecalciferol."
)
"""One clinical sentence no corpus note in this suite contains, inserted as an extra document.

A distractor has to be plausible enough to be read and irrelevant enough that using it would be
an error. Neither "vitamin" nor "cholecalciferol" occurs anywhere in the fourteen notes these
fifteen cases carry, which ``tests/test_consilium_live_suite.py`` asserts, so an answer that
draws on it is drawing on something the question is not about.
"""


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
@order_invariant(field="input.documents", k=3)
@distractor_robust(
    field="input.documents",
    distractors=[DISTRACTOR],
    positions=("start", "end"),
)
@format_jitter(field="input.question")
@paraphrase_invariant(k=3, field="input.question", variants_dir=HERE / "variants")
def test_case(case, probatio, provider):
    """Exact assertions, budget, snapshot and all four relations on one live answer per case."""
    probatio.check(case, sut=lambda c: answer(c, provider))
