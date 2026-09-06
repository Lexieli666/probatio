"""Phase 7: cassettes — record once, replay for nothing, refuse to guess (spec §3.8)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from probatio import Completion, FakeProvider, LLMCase
from probatio.cassette import (
    CASSETTE_MODES,
    IMPORT_PROVIDER,
    RECORD_COMMAND,
    SINGLE_SAMPLE_NOTE,
    Cassette,
    CassetteProvider,
    CassetteStore,
    ImportedCall,
    Interaction,
    default_cassette_dir,
    import_cassettes,
    interaction_key,
    parse_trace_line,
    read_trace,
    resolve_model,
)
from probatio.errors import (
    MissingCassetteError,
    ProbatioConfigError,
    StaleCassetteError,
)
from probatio.judge import Judge, judge_template_hash, resolve_rubric
from probatio.providers import Provider

SUITE = "test_demo"
CASE = "htn-definition"
PROMPT = "What is high blood pressure?"
SYSTEM = "Answer only from the documents."
PARAMS: dict[str, Any] = {"model": "claude-sonnet-5", "temperature": 0}
FIXED = datetime(2026, 9, 4, 12, 0, 0, tzinfo=UTC)


def clock() -> datetime:
    """A clock that never moves, so two recordings produce the same bytes."""
    return FIXED


def store(tmp_path: Path) -> CassetteStore:
    return CassetteStore(tmp_path / "cassettes", clock=clock)


def fake(answer: str = "Hypertension is sustained high pressure.") -> FakeProvider:
    return FakeProvider(default=answer, cost_usd=0.002, latency_ms=1234.5, model="claude-sonnet-5")


def record_one(
    tmp_path: Path, *, runs: int = 1, provider: FakeProvider | None = None
) -> tuple[CassetteStore, FakeProvider]:
    """Record ``runs`` runs of one case through a fake, and return the store and the fake."""
    inner = provider if provider is not None else fake()
    tapes = store(tmp_path)
    recorder = CassetteProvider(inner, tapes, "record")
    for run_index in range(runs):
        tapes.begin_case(SUITE, CASE, run_index)
        recorder.complete(PROMPT, system=SYSTEM, **PARAMS)
    tapes.end_case()
    return tapes, inner


# -- the key ---------------------------------------------------------------------------------


def test_the_key_changes_with_the_prompt_the_model_and_any_param() -> None:
    base = interaction_key(prompt=PROMPT, system=SYSTEM, params=PARAMS)
    assert base != interaction_key(prompt=PROMPT + "?", system=SYSTEM, params=PARAMS)
    assert base != interaction_key(prompt=PROMPT, system=None, params=PARAMS)
    assert base != interaction_key(
        prompt=PROMPT, system=SYSTEM, params={**PARAMS, "model": "claude-opus-5"}
    )
    assert base != interaction_key(
        prompt=PROMPT, system=SYSTEM, params={**PARAMS, "temperature": 1}
    )
    assert base != interaction_key(prompt=PROMPT, system=SYSTEM, params=PARAMS, template="deadbeef")


def test_the_key_does_not_change_with_the_order_params_were_written_in() -> None:
    forwards = interaction_key(prompt=PROMPT, system=SYSTEM, params={"model": "m", "top_p": 1})
    backwards = interaction_key(prompt=PROMPT, system=SYSTEM, params={"top_p": 1, "model": "m"})
    assert forwards == backwards


def test_the_model_is_lifted_out_of_params_so_it_is_counted_once() -> None:
    """Spec §3.8 names model and params as separate parts of the key (DECISIONS 43)."""
    lifted = interaction_key(prompt=PROMPT, system=None, params={"model": "m"})
    left_in = interaction_key(prompt=PROMPT, system=None, params={"params": {"model": "m"}})
    assert lifted != left_in
    assert lifted == interaction_key(prompt=PROMPT, system=None, params={"model": "m"})


# -- replay ----------------------------------------------------------------------------------


def test_replay_makes_zero_inner_calls(tmp_path: Path) -> None:
    """Spec §3.8's headline acceptance: a replayed suite never reaches a provider."""
    tapes, _ = record_one(tmp_path)
    inner = fake("this answer must never be produced")
    player = CassetteProvider(inner, store(tmp_path), "replay")
    player.store.begin_case(SUITE, CASE, 0)
    completion = player.complete(PROMPT, system=SYSTEM, **PARAMS)
    assert inner.call_count == 0
    assert completion.text == "Hypertension is sustained high pressure."
    assert tapes.path_for(SUITE, CASE).exists()


def test_record_then_replay_round_trips_a_completion_exactly_raw_included(
    tmp_path: Path,
) -> None:
    inner = fake()
    tapes = store(tmp_path)
    recorder = CassetteProvider(inner, tapes, "record")
    tapes.begin_case(SUITE, CASE, 0)
    recorded = recorder.complete(PROMPT, system=SYSTEM, **PARAMS)

    fresh = store(tmp_path)
    player = CassetteProvider(fake("wrong"), fresh, "replay")
    fresh.begin_case(SUITE, CASE, 0)
    replayed = player.complete(PROMPT, system=SYSTEM, **PARAMS)

    assert replayed == recorded
    assert replayed.raw == {"provider": "fake", "matched": "default"}
    assert replayed.latency_ms == 1234.5
    assert replayed.cost_usd == 0.002


def test_a_mutated_prompt_a_changed_model_and_a_changed_param_are_each_stale(
    tmp_path: Path,
) -> None:
    record_one(tmp_path)
    mutations: list[tuple[str, dict[str, Any]]] = [
        (PROMPT + " Explain.", PARAMS),
        (PROMPT, {**PARAMS, "model": "claude-opus-5"}),
        (PROMPT, {**PARAMS, "temperature": 0.7}),
    ]
    for prompt, params in mutations:
        fresh = store(tmp_path)
        inner = fake()
        player = CassetteProvider(inner, fresh, "replay")
        fresh.begin_case(SUITE, CASE, 0)
        with pytest.raises(StaleCassetteError) as excinfo:
            player.complete(prompt, system=SYSTEM, **params)
        message = str(excinfo.value)
        assert CASE in message
        assert "the prompt, the model or the params changed" in message
        assert RECORD_COMMAND in message
        assert inner.call_count == 0


def test_a_case_with_no_tape_names_the_record_command(tmp_path: Path) -> None:
    tapes = store(tmp_path)
    inner = fake()
    player = CassetteProvider(inner, tapes, "replay")
    tapes.begin_case(SUITE, "no-such-case", 0)
    with pytest.raises(MissingCassetteError) as excinfo:
        player.complete(PROMPT, system=SYSTEM, **PARAMS)
    assert RECORD_COMMAND in str(excinfo.value)
    assert "no-such-case" in str(excinfo.value)
    assert inner.call_count == 0


def test_recording_three_runs_then_replaying_five_returns_samples_0_1_2_0_1(
    tmp_path: Path,
) -> None:
    """The list of samples is what makes a pass rate reproducible from a tape at $0."""
    from probatio.providers import ScriptedProvider

    scripted = ScriptedProvider(["first", "second", "third"], model="claude-sonnet-5")
    tapes = store(tmp_path)
    recorder = CassetteProvider(scripted, tapes, "record")
    for run_index in range(3):
        tapes.begin_case(SUITE, CASE, run_index)
        recorder.complete(PROMPT, system=SYSTEM, **PARAMS)

    fresh = store(tmp_path)
    player = CassetteProvider(fake("wrong"), fresh, "replay")
    replayed = []
    for run_index in range(5):
        fresh.begin_case(SUITE, CASE, run_index)
        replayed.append(player.complete(PROMPT, system=SYSTEM, **PARAMS).text)
    assert replayed == ["first", "second", "third", "first", "second"]
    assert fresh.notes == []


def test_a_tape_recorded_on_one_model_does_not_replay_on_another(tmp_path: Path) -> None:
    """A case that names no model still belongs to the model that answered it.

    Live adapters take their model from their constructor, which spec §3.12's ``--probatio-model``
    fills in, and the demo suite's ten cases pass no ``model`` in ``params``. Resolving the key's
    model from ``params`` alone would let every one of those tapes replay against any model at all
    (DECISIONS 43, amended).
    """
    bare: dict[str, Any] = {"temperature": 0}
    tapes = store(tmp_path)
    recorder = CassetteProvider(FakeProvider(default="recorded on m1", model="m1"), tapes, "record")
    tapes.begin_case(SUITE, CASE, 0)
    recorder.complete(PROMPT, system=SYSTEM, **bare)

    other = store(tmp_path)
    inner = FakeProvider(default="must never be produced", model="m2")
    player = CassetteProvider(inner, other, "replay")
    other.begin_case(SUITE, CASE, 0)
    with pytest.raises(StaleCassetteError) as excinfo:
        player.complete(PROMPT, system=SYSTEM, **bare)
    assert "the prompt, the model or the params changed" in str(excinfo.value)
    assert inner.call_count == 0

    same = store(tmp_path)
    unchanged = FakeProvider(default="must never be produced", model="m1")
    replays = CassetteProvider(unchanged, same, "replay")
    same.begin_case(SUITE, CASE, 0)
    assert replays.complete(PROMPT, system=SYSTEM, **bare).text == "recorded on m1"
    assert unchanged.call_count == 0


def test_a_model_named_in_params_beats_the_adapters_own(tmp_path: Path) -> None:
    """The precedence both live adapters implement: the call wins, then the constructor."""
    assert resolve_model({"model": "named"}, "constructed") == "named"
    assert resolve_model({}, "constructed") == "constructed"
    assert resolve_model({"model": None}, "constructed") == "constructed"
    assert resolve_model({}, None) is None

    tapes = store(tmp_path)
    recorder = CassetteProvider(FakeProvider(default="answer", model="ignored"), tapes, "record")
    tapes.begin_case(SUITE, CASE, 0)
    recorder.complete(PROMPT, system=SYSTEM, **PARAMS)

    other = store(tmp_path)
    inner = FakeProvider(default="must never be produced", model="also-ignored")
    player = CassetteProvider(inner, other, "replay")
    other.begin_case(SUITE, CASE, 0)
    assert player.complete(PROMPT, system=SYSTEM, **PARAMS).text == "answer"
    assert inner.call_count == 0


def test_the_wrapper_reads_the_effective_model_off_an_adapter_that_has_none(
    tmp_path: Path,
) -> None:
    class Modelless:
        """A provider that declares no default model, as a user's own adapter may not."""

        name = "modelless"

        def complete(self, prompt: str, *, system: str | None = None, **params: Any) -> Completion:
            return Completion(text="answer", model="whatever-it-chose")

    wrapped = CassetteProvider(Modelless(), store(tmp_path), "record")
    assert wrapped.inner_model is None
    wrapped.store.begin_case(SUITE, CASE, 0)
    wrapped.complete(PROMPT)
    tape = wrapped.store.load(SUITE, CASE)
    assert tape is not None
    assert tape.interactions[0].model is None


def test_a_one_sample_tape_replayed_for_several_runs_is_noted(tmp_path: Path) -> None:
    record_one(tmp_path, runs=1)
    fresh = store(tmp_path)
    player = CassetteProvider(fake("wrong"), fresh, "replay")
    for run_index in range(3):
        fresh.begin_case(SUITE, CASE, run_index)
        player.complete(PROMPT, system=SYSTEM, **PARAMS)
    assert len(fresh.notes) == 1, "the note is made once however many runs replay it"
    assert SINGLE_SAMPLE_NOTE in fresh.notes[0]
    assert CASE in fresh.notes[0]
    assert "0 or 1" in fresh.notes[0]


def test_a_one_sample_judge_interaction_is_not_noted(tmp_path: Path) -> None:
    """A judge tape holds one sample per run by construction; saying so would be a false alarm.

    Under ``--runs N`` the judge prompt carries the answer it is grading, so a run that produced a
    different answer is a different key. Each of those interactions has one sample and is replayed
    only at its own run index, and the note would tell the reader that the case's pass rate can
    only be 0 or 1 when the report beside it prints a rate between the two (DECISIONS 106).
    """
    template = judge_template_hash()
    recorder = store(tmp_path)
    writer = CassetteProvider(fake("graded"), recorder, "record")
    for run_index in range(3):
        recorder.begin_case(SUITE, CASE, run_index)
        with recorder.judge_calls(template):
            writer.complete(f"grade answer {run_index}")
    recorder.end_case()

    fresh = store(tmp_path)
    player = CassetteProvider(fake("wrong"), fresh, "replay")
    for run_index in range(3):
        fresh.begin_case(SUITE, CASE, run_index)
        with fresh.judge_calls(template):
            player.complete(f"grade answer {run_index}")
    assert fresh.notes == [], fresh.notes


# -- record ----------------------------------------------------------------------------------


def test_a_recording_through_a_fake_is_byte_stable_across_two_recordings(
    tmp_path: Path,
) -> None:
    first = record_one(tmp_path / "a")[0].path_for(SUITE, CASE).read_bytes()
    second = record_one(tmp_path / "b")[0].path_for(SUITE, CASE).read_bytes()
    assert first == second
    assert first.endswith(b"\n")


def test_a_tape_is_laid_out_the_way_the_spec_describes(tmp_path: Path) -> None:
    tapes, _ = record_one(tmp_path)
    payload = json.loads(tapes.path_for(SUITE, CASE).read_text(encoding="utf-8"))
    assert set(payload) == {"case_id", "recorded", "provider", "model", "interactions"}
    assert payload["case_id"] == CASE
    assert payload["recorded"] == "2026-09-04T12:00:00Z"
    assert payload["provider"] == "fake"
    assert payload["model"] == "claude-sonnet-5"
    interaction = payload["interactions"][0]
    assert set(interaction) == {"key", "prompt", "system", "params", "model", "completions"}
    assert interaction["prompt"] == PROMPT
    assert interaction["system"] == SYSTEM
    assert interaction["params"] == PARAMS
    assert interaction["model"] == "claude-sonnet-5"
    assert len(interaction["completions"]) == 1


def test_recording_a_second_distinct_call_appends_an_interaction(tmp_path: Path) -> None:
    inner = fake()
    tapes = store(tmp_path)
    recorder = CassetteProvider(inner, tapes, "record")
    tapes.begin_case(SUITE, CASE, 0)
    recorder.complete(PROMPT, system=SYSTEM, **PARAMS)
    recorder.complete("A different question entirely?", system=SYSTEM, **PARAMS)
    tape = tapes.load(SUITE, CASE)
    assert tape is not None
    assert len(tape.interactions) == 2
    assert [len(item.completions) for item in tape.interactions] == [1, 1]


def test_rerecording_replaces_rather_than_growing_the_sample_list(tmp_path: Path) -> None:
    """Two record sessions of three runs leave three samples, not six (DECISIONS 44)."""
    record_one(tmp_path, runs=3)
    tapes, _ = record_one(tmp_path, runs=3)
    tape = tapes.load(SUITE, CASE)
    assert tape is not None
    assert len(tape.interactions[0].completions) == 3


def test_recording_a_case_that_already_has_a_tape_keeps_its_other_interactions(
    tmp_path: Path,
) -> None:
    inner = fake()
    tapes = store(tmp_path)
    recorder = CassetteProvider(inner, tapes, "record")
    tapes.begin_case(SUITE, CASE, 0)
    recorder.complete("first question", system=None)
    recorder.complete("second question", system=None)

    later = store(tmp_path)
    again = CassetteProvider(fake("new answer"), later, "record")
    later.begin_case(SUITE, CASE, 0)
    again.complete("first question", system=None)
    tape = later.load(SUITE, CASE)
    assert tape is not None
    assert len(tape.interactions) == 2
    assert tape.interactions[0].completions[0].text == "new answer"
    assert tape.interactions[1].completions[0].text == "Hypertension is sustained high pressure."


# -- off -------------------------------------------------------------------------------------


def test_off_passes_straight_through_and_writes_nothing(tmp_path: Path) -> None:
    inner = fake()
    tapes = store(tmp_path)
    passthrough = CassetteProvider(inner, tapes, "off")
    completion = passthrough.complete(PROMPT, system=SYSTEM, **PARAMS)
    assert inner.call_count == 1
    assert completion.text == "Hypertension is sustained high pressure."
    assert not (tmp_path / "cassettes").exists()


def test_off_needs_no_active_case(tmp_path: Path) -> None:
    passthrough = CassetteProvider(fake(), store(tmp_path), "off")
    assert passthrough.store.active is None
    assert passthrough.complete("anything").text


# -- the wrapper is invisible ------------------------------------------------------------------


def test_the_wrapper_reports_the_inner_adapters_name_and_satisfies_the_protocol(
    tmp_path: Path,
) -> None:
    wrapped = CassetteProvider(fake(), store(tmp_path), "off")
    assert wrapped.name == "fake"
    assert isinstance(wrapped, Provider)


def test_the_inner_provider_receives_exactly_what_the_caller_passed(tmp_path: Path) -> None:
    inner = fake()
    tapes = store(tmp_path)
    recorder = CassetteProvider(inner, tapes, "record")
    tapes.begin_case(SUITE, CASE, 0)
    recorder.complete(PROMPT, system=SYSTEM, **PARAMS)
    assert inner.calls[0].prompt == PROMPT
    assert inner.calls[0].system == SYSTEM
    assert inner.calls[0].params == PARAMS


def test_a_mode_that_is_not_a_mode_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ProbatioConfigError) as excinfo:
        CassetteProvider(fake(), store(tmp_path), "playback")  # type: ignore[arg-type]
    assert "playback" in str(excinfo.value)
    for mode in CASSETTE_MODES:
        assert mode in str(excinfo.value)


# -- the judge mark --------------------------------------------------------------------------


def judged_case() -> LLMCase:
    return LLMCase.model_validate(
        {
            "id": CASE,
            "input": {"question": PROMPT},
            "assertions": [{"type": "judge", "rubric": "faithfulness"}],
        }
    )


def test_a_judge_call_and_a_sut_call_with_the_same_text_get_different_keys(
    tmp_path: Path, demo_rubrics: Path
) -> None:
    """Spec §3.5: the judge template hash is part of every judge cassette key."""
    rubric = resolve_rubric("faithfulness", rubric_dirs=[demo_rubrics])
    inner = FakeProvider(default='{"verdict": "pass", "score": 1.0}')
    tapes = store(tmp_path)
    recorder = CassetteProvider(inner, tapes, "record")
    tapes.begin_case(SUITE, CASE, 0)

    judge = Judge(rubric, recorder)
    judge.grade(judged_case(), "Hypertension is sustained high pressure.")
    judge_prompt = inner.calls[0].prompt
    recorder.complete(judge_prompt)

    tape = tapes.load(SUITE, CASE)
    assert tape is not None
    assert len(tape.interactions) == 2, "identical text, two interactions"
    keys = {item.key for item in tape.interactions}
    assert len(keys) == 2
    assert interaction_key(prompt=judge_prompt, system=None, params={}, model="fake-1") in keys
    assert (
        interaction_key(
            prompt=judge_prompt,
            system=None,
            params={},
            model="fake-1",
            template=judge_template_hash(),
        )
        in keys
    )


def test_the_judge_mark_never_reaches_the_inner_provider(
    tmp_path: Path, demo_rubrics: Path
) -> None:
    """The mark travels on the store, so a live adapter is called with nothing extra."""
    rubric = resolve_rubric("faithfulness", rubric_dirs=[demo_rubrics])
    inner = FakeProvider(default='{"verdict": "pass", "score": 1.0}')
    tapes = store(tmp_path)
    recorder = CassetteProvider(inner, tapes, "record")
    tapes.begin_case(SUITE, CASE, 0)
    Judge(rubric, recorder, params={"model": "claude-sonnet-5"}).grade(judged_case(), "output")
    assert inner.call_count == 1
    assert inner.calls[0].system is None
    assert inner.calls[0].params == {"model": "claude-sonnet-5"}


def test_a_judge_handed_a_bare_provider_calls_it_unchanged(demo_rubrics: Path) -> None:
    """An adapter with no ``judge_calls`` is not asked for one, and sees no reserved keyword."""
    rubric = resolve_rubric("faithfulness", rubric_dirs=[demo_rubrics])
    inner = FakeProvider(default='{"verdict": "pass", "score": 0.5}')
    verdict = Judge(rubric, inner).grade(judged_case(), "output")
    assert verdict.score == 0.5
    assert inner.calls[0].params == {}


def test_the_judge_context_is_restored_when_the_block_ends(tmp_path: Path) -> None:
    tapes = store(tmp_path)
    assert tapes.template is None
    with tapes.judge_calls("outer"):
        assert tapes.template == "outer"
        with tapes.judge_calls("inner"):
            assert tapes.template == "inner"
        assert tapes.template == "outer"
    assert tapes.template is None


# -- the active context ------------------------------------------------------------------------


def test_a_call_outside_a_case_says_which_hook_was_missed(tmp_path: Path) -> None:
    tapes = store(tmp_path)
    player = CassetteProvider(fake(), tapes, "replay")
    with pytest.raises(ProbatioConfigError) as excinfo:
        player.complete(PROMPT)
    assert "begin_case" in str(excinfo.value)


def test_ending_a_case_forgets_it(tmp_path: Path) -> None:
    tapes = store(tmp_path)
    active = tapes.begin_case(SUITE, CASE, 2)
    assert active.run_index == 2
    assert tapes.active == active
    assert tapes.require_active() == active
    tapes.end_case()
    assert tapes.active is None


def test_a_negative_run_index_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ProbatioConfigError) as excinfo:
        store(tmp_path).begin_case(SUITE, CASE, -1)
    assert "runs count from 0" in str(excinfo.value)


def test_a_name_that_would_escape_the_cassette_directory_is_refused(tmp_path: Path) -> None:
    tapes = store(tmp_path)
    with pytest.raises(ProbatioConfigError) as excinfo:
        tapes.path_for("../elsewhere", CASE)
    assert "suite" in str(excinfo.value)
    with pytest.raises(ProbatioConfigError) as excinfo:
        tapes.begin_case(SUITE, "../escape")
    assert "case id" in str(excinfo.value)


def test_the_default_directory_is_cassettes_under_the_working_directory() -> None:
    assert default_cassette_dir() == Path.cwd() / "cassettes"
    assert CassetteStore().cassette_dir == default_cassette_dir()


# -- broken tapes ------------------------------------------------------------------------------


def test_a_tape_that_does_not_parse_is_a_configuration_error_not_a_missing_recording(
    tmp_path: Path,
) -> None:
    tapes = store(tmp_path)
    path = tapes.path_for(SUITE, CASE)
    path.parent.mkdir(parents=True)
    path.write_text('{"case_id": "htn-definition"}', encoding="utf-8")
    with pytest.raises(ProbatioConfigError) as excinfo:
        tapes.load(SUITE, CASE)
    assert "not a readable cassette file" in str(excinfo.value)
    assert RECORD_COMMAND in str(excinfo.value)


def test_a_tape_that_cannot_be_read_names_itself(tmp_path: Path) -> None:
    tapes = store(tmp_path)
    path = tapes.path_for(SUITE, CASE)
    path.mkdir(parents=True)  # a directory where a file belongs: readable path, unreadable file
    with pytest.raises(ProbatioConfigError) as excinfo:
        tapes.load(SUITE, CASE)
    assert "cannot be read" in str(excinfo.value)


def test_a_loaded_tape_is_cached_rather_than_reread(tmp_path: Path) -> None:
    tapes, _ = record_one(tmp_path)
    first = tapes.load(SUITE, CASE)
    tapes.path_for(SUITE, CASE).unlink()
    assert tapes.load(SUITE, CASE) is first


def test_an_interaction_with_no_samples_refuses_to_choose_one() -> None:
    with pytest.raises(ValueError, match="no recorded completion"):
        Interaction(key="k", prompt="p").sample(0)


def test_a_tape_reports_a_key_it_does_not_carry_as_absent() -> None:
    tape = Cassette(case_id=CASE, recorded="now", provider="fake", model="m")
    assert tape.find("nothing") is None


# -- import-cassettes --------------------------------------------------------------------------


def trace_lines() -> list[str]:
    """Three lines: two runs of one case, one run of another."""
    common = {"prompt": PROMPT, "system": SYSTEM, "params": {"model": "m", "temperature": 0}}
    return [
        json.dumps({"case_id": CASE, "text": "first", "model": "m", **common}),
        json.dumps({"case_id": CASE, "text": "second", "model": "m", **common}),
        json.dumps(
            {
                "case_id": "copd-spirometry",
                "prompt": "What does spirometry measure?",
                "text": "Airflow obstruction.",
                "model": "m",
                "tokens_in": 40,
                "tokens_out": 7,
                "cost_usd": 0.0004,
                "latency_ms": 812.0,
            }
        ),
    ]


def test_a_three_line_trace_produces_files_that_replay(tmp_path: Path) -> None:
    """Spec §3.13's acceptance: the imported tapes replay with zero inner calls."""
    tapes = store(tmp_path)
    written = import_cassettes(trace_lines(), suite=SUITE, store=tapes, provider="claude-cli")
    assert [path.name for path in written] == ["htn-definition.json", "copd-spirometry.json"]

    fresh = store(tmp_path)
    inner = FakeProvider(default="must never be called", model="m")
    player = CassetteProvider(inner, fresh, "replay")

    fresh.begin_case(SUITE, CASE, 0)
    assert player.complete(PROMPT, system=SYSTEM, model="m", temperature=0).text == "first"
    fresh.begin_case(SUITE, CASE, 1)
    assert player.complete(PROMPT, system=SYSTEM, model="m", temperature=0).text == "second"
    fresh.begin_case(SUITE, "copd-spirometry", 0)
    spirometry = player.complete("What does spirometry measure?")
    assert spirometry.text == "Airflow obstruction."
    assert spirometry.tokens_in == 40
    assert spirometry.cost_usd == 0.0004
    assert spirometry.latency_ms == 812.0
    assert inner.call_count == 0


def test_lines_sharing_a_case_and_a_call_become_one_interaction_in_file_order(
    tmp_path: Path,
) -> None:
    tapes = store(tmp_path)
    import_cassettes(trace_lines(), suite=SUITE, store=tapes, provider="claude-cli")
    tape = tapes.load(SUITE, CASE)
    assert tape is not None
    assert len(tape.interactions) == 1
    assert [item.text for item in tape.interactions[0].completions] == ["first", "second"]
    assert tape.provider == "claude-cli"
    assert tape.recorded == "2026-09-04T12:00:00Z"


def test_an_imported_completion_says_where_it_came_from() -> None:
    call = ImportedCall(case_id=CASE, prompt=PROMPT, text="t", model="m")
    completion = call.completion()
    assert completion.raw == {"provider": IMPORT_PROVIDER}
    assert completion.cost_usd is None
    assert completion.latency_ms == 0.0


def test_importing_is_byte_stable_across_two_runs(tmp_path: Path) -> None:
    first = import_cassettes(trace_lines(), suite=SUITE, store=store(tmp_path / "a"))
    second = import_cassettes(trace_lines(), suite=SUITE, store=store(tmp_path / "b"))
    assert [path.read_bytes() for path in first] == [path.read_bytes() for path in second]


def test_a_blank_line_is_not_a_record(tmp_path: Path) -> None:
    lines = [trace_lines()[0], "", "   ", trace_lines()[1]]
    tapes = store(tmp_path)
    assert len(import_cassettes(lines, suite=SUITE, store=tapes)) == 1
    assert parse_trace_line("", 1) is None


@pytest.mark.parametrize(
    ("line", "reason"),
    [
        ("{not json", "is not JSON"),
        ("[1, 2]", "is a JSON list"),
        ('{"prompt": "p", "text": "t", "model": "m"}', "case_id"),
        ('{"case_id": "c", "prompt": "p", "text": "t", "model": "m", "oops": 1}', "oops"),
        (
            '{"case_id": "c", "prompt": "p", "text": "t", "model": "m", "latency_ms": "x"}',
            "latency_ms",
        ),
    ],
)
def test_a_malformed_line_is_a_configuration_error_naming_its_number(
    tmp_path: Path, line: str, reason: str
) -> None:
    lines = [trace_lines()[0], line]
    with pytest.raises(ProbatioConfigError) as excinfo:
        import_cassettes(lines, suite=SUITE, store=store(tmp_path))
    message = str(excinfo.value)
    assert "line 2" in message
    assert reason in message


def test_an_error_names_the_file_when_the_caller_knows_it(tmp_path: Path) -> None:
    source = tmp_path / "trace.jsonl"
    source.write_text("{not json\n", encoding="utf-8")
    with pytest.raises(ProbatioConfigError) as excinfo:
        import_cassettes(read_trace(source), suite=SUITE, store=store(tmp_path), source=source)
    assert str(source) in str(excinfo.value)


def test_an_unreadable_trace_names_itself(tmp_path: Path) -> None:
    with pytest.raises(ProbatioConfigError) as excinfo:
        read_trace(tmp_path / "absent.jsonl")
    assert "cannot read trace file" in str(excinfo.value)


def test_an_importable_case_id_may_not_escape_the_output_directory(tmp_path: Path) -> None:
    line = json.dumps({"case_id": "../escape", "prompt": "p", "text": "t", "model": "m"})
    with pytest.raises(ProbatioConfigError) as excinfo:
        import_cassettes([line], suite=SUITE, store=store(tmp_path))
    assert "case id" in str(excinfo.value)
    with pytest.raises(ProbatioConfigError) as excinfo:
        import_cassettes(trace_lines(), suite="../escape", store=store(tmp_path))
    assert "suite" in str(excinfo.value)


# -- the completion the store hands back is the one the tape holds ------------------------------


def test_every_field_of_a_completion_survives_the_round_trip(tmp_path: Path) -> None:
    rich = Completion(
        text="answer",
        model="claude-sonnet-5",
        tokens_in=1234,
        tokens_out=56,
        cost_usd=0.00789,
        latency_ms=4321.5,
        raw={"nested": {"a": [1, 2, {"b": None}]}, "flag": True},
    )

    class OneAnswer:
        """A provider that returns one prepared completion, to pin the round trip exactly."""

        name = "prepared"

        def complete(self, prompt: str, *, system: str | None = None, **params: Any) -> Completion:
            return rich

    tapes = store(tmp_path)
    recorder = CassetteProvider(OneAnswer(), tapes, "record")
    tapes.begin_case(SUITE, CASE, 0)
    recorder.complete(PROMPT, system=SYSTEM, **PARAMS)

    fresh = store(tmp_path)
    player = CassetteProvider(fake(), fresh, "replay")
    fresh.begin_case(SUITE, CASE, 0)
    assert player.complete(PROMPT, system=SYSTEM, **PARAMS) == rich


def test_iterating_a_trace_from_a_generator_is_accepted(tmp_path: Path) -> None:
    def lines() -> Iterator[str]:
        yield from trace_lines()

    assert len(import_cassettes(lines(), suite=SUITE, store=store(tmp_path))) == 2


# -- Phase 9: the record command names the provider that would answer -------------------------


def test_the_record_command_is_the_bare_flag_for_a_fake_or_unnamed_provider() -> None:
    from probatio.cassette import RECORD_COMMAND, record_command

    assert record_command() == RECORD_COMMAND
    assert record_command("fake") == RECORD_COMMAND
    assert record_command("fake", "fake-1") == RECORD_COMMAND


def test_the_record_command_names_a_live_provider_and_its_model() -> None:
    """Requirement 5: re-recording against the default provider is not the instruction."""
    from probatio.cassette import record_command

    assert record_command("claude-cli") == "pytest --cassette=record --probatio-provider claude-cli"
    assert record_command("claude-cli", "claude-x") == (
        "pytest --cassette=record --probatio-provider claude-cli --probatio-model claude-x"
    )


def test_a_store_uses_whichever_record_command_it_was_given(tmp_path: Path) -> None:
    from probatio.cassette import record_command

    store = CassetteStore(tmp_path)
    store.record_command = record_command("claude-cli", "claude-x")
    store.begin_case("suite", "alpha")
    with pytest.raises(MissingCassetteError) as excinfo:
        store.replay(prompt="ask", system=None, params={})
    assert "--probatio-provider claude-cli" in str(excinfo.value)
    assert "--probatio-model claude-x" in str(excinfo.value)
