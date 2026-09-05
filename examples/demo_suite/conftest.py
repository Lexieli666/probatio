"""Wiring for the demo suite: a scripted fake provider, a fake judge, and a flaky script.

The fake app in app.py answers by keyword: each question carries one word that selects its
scripted response, matched case-sensitively. That brittleness is intentional. It gives the
metamorphic relations something to catch (a casing change to the sentence holding the keyword
flips the verdict) while permutations and distractors leave the keyword intact and pass.
"""

from __future__ import annotations

import pytest

# One keyword per case, matched as a substring of the full prompt. Keywords are single tokens
# so that doubled spaces (format_jitter "whitespace") cannot split them, and each appears in
# exactly one case's prompt (question + documents + system); tests/ checks that invariant.
RESPONSES = {
    "reading": (
        "High blood pressure, or hypertension, is arterial pressure that stays raised over time "
        "and is confirmed on repeated visits. One high measurement on its own is not a diagnosis; "
        "it needs to be repeated."
    ),
    "first-line": (
        "Lifestyle changes are recommended for everyone. For initial drug treatment of "
        "uncomplicated hypertension the documents list thiazide-type diuretics, ACE inhibitors, "
        "angiotensin receptor blockers and calcium channel blockers."
    ),
    "start_age": '{"screen": true, "start_age": 35}',
    "starting": (
        "The documents name metformin as the usual starting drug for type 2 diabetes when kidney "
        "function is adequate, together with lifestyle changes."
    ),
    "alarm": (
        "The documents list difficulty swallowing, unintentional weight loss, vomiting, and signs "
        "of bleeding as alarm features that need prompt evaluation."
    ),
    "confirms": "Spirometry showing persistent airflow limitation confirms COPD.",
    "immediate": (
        "This may be a heart attack. Call 911 or your local emergency number immediately; do not "
        "wait to see whether it passes."
    ),
    "insomnia": (
        "The documents recommend cognitive behavioral therapy for insomnia (CBT-I) as the initial "
        "treatment; medications are considered only if CBT-I is unavailable or does not work."
    ),
    # Scripted to refuse an answerable question: the expected-fail case.
    "generalized": "I don't know.",
}

JUDGE_PASS = '{"verdict": "pass", "score": 1.0, "rationale": "Every claim is in the documents."}'
JUDGE_FAIL = '{"verdict": "fail", "score": 0.0, "rationale": "The output is not an answer."}'

FLU_ANSWER = (
    "The documents mention oseltamivir and other neuraminidase inhibitors; treatment works best "
    "when started within 48 hours of symptoms and is recommended regardless of timing for "
    "high-risk patients."
)


def fake_judge(prompt: str) -> str:
    """Grade by inspection: the keyword-miss fallback FAKE(...) is the only unfaithful output."""
    return JUDGE_FAIL if "FAKE(" in prompt else JUDGE_PASS


@pytest.fixture
def provider(provider, request):
    """Use the scripted fake unless a live provider was requested on the command line.

    ``pytest --probatio-provider claude-cli --cassette=record`` therefore records real tapes for
    this suite; the default run stays offline and needs none.
    """
    if request.config.getoption("--probatio-provider") != "fake":
        return provider
    from probatio import FakeProvider

    return FakeProvider(responses=RESPONSES, cost_usd=0.0001, latency_ms=20.0)


@pytest.fixture
def judge_provider(judge_provider, request):
    """A fake judge that follows the same switch as ``provider``."""
    if request.config.getoption("--probatio-provider") != "fake":
        return judge_provider
    from probatio import FakeProvider

    return FakeProvider(default=fake_judge, cost_usd=0.0001, latency_ms=20.0)


@pytest.fixture
def scripted_provider():
    """Fails the first of five calls, then answers; ``@flaky_tolerant(p=0.8, n=5)`` accepts it."""
    from probatio import ScriptedProvider

    return ScriptedProvider(
        script=["I don't know."] + [FLU_ANSWER] * 4, cost_usd=0.0001, latency_ms=20.0
    )
