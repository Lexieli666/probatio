"""Phase 2: the provider protocol and the two offline fakes."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from probatio import Completion, FakeProvider, ProbatioConfigError, Provider, ScriptedProvider
from probatio.hashing import stable_hash
from probatio.providers import FakeCall


def test_both_fakes_satisfy_the_provider_protocol() -> None:
    assert isinstance(FakeProvider(), Provider)
    assert isinstance(ScriptedProvider(["a"]), Provider)
    assert isinstance(object(), Provider) is False
    assert (FakeProvider.name, ScriptedProvider.name) == ("fake", "scripted")


def test_the_call_key_wins_over_a_substring() -> None:
    key = FakeProvider.call_key("say reading please", None, {"temperature": 0})
    provider = FakeProvider(responses={key: "by key", "reading": "by substring"})
    assert provider.complete("say reading please", temperature=0).text == "by key"
    assert provider.complete("say reading please", temperature=1).text == "by substring"
    assert provider.complete("say reading please", system="s", temperature=0).text == "by substring"


def test_the_call_key_is_the_documented_hash() -> None:
    assert FakeProvider.call_key("p", "s", {"temperature": 0}) == stable_hash(
        {"prompt": "p", "system": "s", "params": {"temperature": 0}}
    )


def test_substring_keys_are_checked_in_insertion_order() -> None:
    provider = FakeProvider(responses={"first": "1", "second": "2"})
    assert provider.complete("first and second").text == "1"
    reversed_provider = FakeProvider(responses={"second": "2", "first": "1"})
    assert reversed_provider.complete("first and second").text == "2"


def test_a_string_default_answers_everything_that_does_not_match() -> None:
    provider = FakeProvider(responses={"reading": "keyed"}, default="fallback answer")
    assert provider.complete("about a reading").text == "keyed"
    assert provider.complete("about something else").text == "fallback answer"


def test_a_callable_default_grades_the_prompt_it_was_given() -> None:
    """This is how the demo suite's fake judge works: it inspects the prompt and decides."""
    provider = FakeProvider(default=lambda prompt: "fail" if "FAKE(" in prompt else "pass")
    assert provider.complete("judge this: FAKE(abc)").text == "fail"
    assert provider.complete("judge this: a real answer").text == "pass"


def test_the_fallback_is_stable_synthetic_and_prompt_specific() -> None:
    provider = FakeProvider()
    first = provider.complete("unmatched prompt").text
    assert first == f"FAKE({stable_hash('unmatched prompt')})"
    assert FakeProvider().complete("unmatched prompt").text == first
    assert provider.complete("another prompt").text != first


def test_the_fallback_is_identical_in_another_process() -> None:
    script = (
        "from probatio import FakeProvider;print(FakeProvider().complete('unmatched prompt').text)"
    )
    other = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    assert other.stdout.strip() == FakeProvider().complete("unmatched prompt").text


def test_every_call_is_recorded_in_order() -> None:
    provider = FakeProvider()
    assert provider.call_count == 0
    provider.complete("one", system="s", temperature=0)
    provider.complete("two")
    assert provider.call_count == 2
    assert provider.calls == [
        FakeCall(prompt="one", system="s", params={"temperature": 0}),
        FakeCall(prompt="two", system=None, params={}),
    ]


def test_cost_latency_and_model_are_reported_as_configured() -> None:
    provider = FakeProvider(responses={"q": "a"}, cost_usd=0.0001, latency_ms=20.0, model="fake-9")
    completion = provider.complete("q")
    assert isinstance(completion, Completion)
    assert (completion.cost_usd, completion.latency_ms, completion.model) == (
        0.0001,
        20.0,
        "fake-9",
    )
    assert (completion.tokens_in, completion.tokens_out) == (None, None)
    assert completion.raw == {"provider": "fake", "matched": "substring"}


def test_an_unpriced_fake_reports_unknown_cost_rather_than_zero() -> None:
    """A ``0.0`` here would make every cost ceiling pass; ``None`` makes it unenforceable."""
    assert FakeProvider().complete("q").cost_usd is None


def test_the_scripted_provider_cycles_through_its_script() -> None:
    provider = ScriptedProvider(script=["I don't know."] + ["the answer"] * 4)
    answers = [provider.complete("q").text for _ in range(10)]
    assert answers[:5] == ["I don't know.", "the answer", "the answer", "the answer", "the answer"]
    assert answers[5:] == answers[:5]
    assert provider.call_count == 10
    assert {completion for completion in answers} == {"I don't know.", "the answer"}


def test_the_scripted_provider_ignores_the_prompt_entirely() -> None:
    provider = ScriptedProvider(script=["only answer"], cost_usd=0.0001, latency_ms=20.0)
    completion = provider.complete("anything at all", system="s", temperature=0)
    assert completion.text == "only answer"
    assert completion.raw == {"provider": "scripted", "matched": "script"}
    assert (completion.cost_usd, completion.latency_ms) == (0.0001, 20.0)
    assert provider.calls[0].params == {"temperature": 0}


def test_an_empty_script_is_rejected() -> None:
    with pytest.raises(ProbatioConfigError, match="at least one scripted answer"):
        ScriptedProvider(script=[])


def test_a_completion_rejects_unknown_fields_and_is_frozen() -> None:
    completion = Completion(text="t", model="m")
    with pytest.raises(ValueError, match="frozen"):
        completion.text = "other"
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        Completion.model_validate({"text": "t", "model": "m", "tokens": 3})
    assert json.loads(completion.model_dump_json())["raw"] == {}
