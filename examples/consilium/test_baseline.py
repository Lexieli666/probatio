"""Suite ``test_baseline``: Consilium's plain single-call baseline, replayed from the same run.

No relation decorators and no judge. A metamorphic variant is a different prompt and so a
different cassette key, and there is no recorded answer for a question Consilium was never asked;
a judge is a provider call with no tape behind it either. Phase 12's live suite carries both.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app import answer

from probatio import load_cases

CONFIG = "baseline_llm"
CASES = load_cases(Path(__file__).parent / "cases")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_case(case, probatio, provider):
    """Exact assertions, budget and snapshot on the answer the plain baseline delivered."""
    probatio.check(case, sut=lambda c: answer(c, provider, config=CONFIG))
