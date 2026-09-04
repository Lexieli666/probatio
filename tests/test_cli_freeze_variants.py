"""Phase 8: ``probatio freeze-variants``, entirely offline.

Freezing is one of the two commands allowed to call a live model (spec §3.13), so every test here
either uses ``--provider fake``, which calls nothing at all, or replaces the provider factory with
a :class:`~probatio.FakeProvider` whose default callable returns the JSON list a model would.
Nothing here reaches a network, and the clock is injected, so the files are byte-stable.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from probatio import FakeProvider, LLMCase, ProbatioConfigError
from probatio import cli as cli_module
from probatio.cli import build_parser, freeze_variants, main
from probatio.metamorphic import (
    MECHANICAL_PROVIDER,
    build_freeze_prompt,
    load_variants_file,
    mechanical_rewrites,
    parse_paraphrases,
)

FIXED = datetime(2026, 9, 4, 18, 0, 0, tzinfo=UTC)
CASES = Path(__file__).resolve().parents[1] / "examples" / "demo_suite" / "cases"

THREE = [
    "How is hypertension different from one high reading?",
    "What separates high blood pressure from a single elevated reading?",
    "Is one high reading the same as having hypertension?",
]
THREE_JSON = json.dumps(THREE)

QUESTION = "What is high blood pressure, and how is it different from one high reading?"


def clock() -> datetime:
    return FIXED


def paraphraser(reply: str | Callable[[str], str] = THREE_JSON) -> FakeProvider:
    return FakeProvider(default=reply, model="fake-paraphraser-1")


@pytest.fixture
def one_case(tmp_path: Path) -> Path:
    cases = tmp_path / "cases"
    cases.mkdir()
    (cases / "c1.yaml").write_text(
        f"id: htn-definition\ninput:\n  question: {QUESTION!r}\n"
        'assertions:\n  - {type: contains, any: ["anything"]}\n',
        encoding="utf-8",
    )
    return cases


@pytest.fixture
def injected(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeProvider]:
    """Replace the provider factory, so a non-fake ``--provider`` cannot reach a live model."""
    provider = paraphraser()
    monkeypatch.setattr(cli_module, "build_provider", lambda name, model: provider)
    yield provider


def argv(cases: Path, out: Path, *extra: str) -> list[str]:
    return [
        "freeze-variants",
        "--cases",
        str(cases),
        "--field",
        "input.question",
        "--k",
        "3",
        "--out",
        str(out),
        *extra,
    ]


def run(cases: Path, out: Path, *extra: str) -> int:
    args = build_parser().parse_args(argv(cases, out, *extra))
    return freeze_variants(args, clock=clock)


# -- the model path, through an injected fake ----------------------------------------------------


def test_a_model_reply_becomes_a_file_with_full_provenance(
    one_case: Path, tmp_path: Path, injected: FakeProvider
) -> None:
    out = tmp_path / "variants"
    assert run(one_case, out, "--provider", "claude-cli", "--model", "claude-x") == 0

    contents = load_variants_file(out / "htn-definition.yaml")
    assert contents.case_id == "htn-definition"
    assert contents.field == "input.question"
    assert contents.variants == THREE
    assert contents.generated_by.provider == "fake"
    assert contents.generated_by.model == "fake-paraphraser-1"
    assert contents.generated_by.created == "2026-09-04T18:00:00Z"
    assert injected.call_count == 1


def test_the_prompt_hash_is_the_hash_of_the_prompt_that_was_sent(
    one_case: Path, tmp_path: Path, injected: FakeProvider
) -> None:
    from probatio.hashing import stable_hash

    out = tmp_path / "variants"
    run(one_case, out, "--provider", "claude-cli")
    sent = injected.calls[0].prompt
    assert load_variants_file(out / "htn-definition.yaml").generated_by.prompt_hash == stable_hash(
        sent
    )


def test_the_prompt_asks_for_exactly_k_strings_and_carries_the_question(
    one_case: Path, tmp_path: Path, injected: FakeProvider
) -> None:
    run(one_case, tmp_path / "variants", "--provider", "claude-cli")
    prompt = injected.calls[0].prompt
    assert "3 different paraphrases" in prompt
    assert "JSON array of exactly 3 strings" in prompt
    assert "What is high blood pressure" in prompt


def test_two_freezes_with_the_same_clock_are_byte_identical(
    one_case: Path, tmp_path: Path, injected: FakeProvider
) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    run(one_case, first, "--provider", "claude-cli")
    run(one_case, second, "--provider", "claude-cli")
    assert (first / "htn-definition.yaml").read_bytes() == (
        second / "htn-definition.yaml"
    ).read_bytes()


def test_the_written_file_reloads_and_carries_a_review_header(
    one_case: Path, tmp_path: Path, injected: FakeProvider
) -> None:
    out = tmp_path / "variants"
    run(one_case, out, "--provider", "claude-cli")
    text = (out / "htn-definition.yaml").read_text(encoding="utf-8")
    assert text.startswith("# Written by 'probatio freeze-variants'.")
    assert "Read these before you trust them" in text
    assert load_variants_file(out / "htn-definition.yaml").variants == THREE


# -- validation of the reply ---------------------------------------------------------------------


def test_a_reply_wrapped_in_a_code_fence_is_still_accepted() -> None:
    reply = "```json\n" + THREE_JSON + "\n```"
    assert parse_paraphrases(reply, original="q", k=3, case_id="c1") == THREE


@pytest.mark.parametrize(
    ("reply", "match"),
    [
        ("not json at all", "is not JSON"),
        ('{"variants": ["a"]}', "JSON dict, not an array"),
        ('["a", "b"]', "holds 2 entries but 3 were asked for"),
        ('["a", "b", 7]', "paraphrase 3 is not a non-empty string"),
        ('["a", "b", "  "]', "paraphrase 3 is not a non-empty string"),
        ('["a", "b", "a"]', "paraphrase 3 repeats an earlier one"),
        ('["a", "b", "q"]', "paraphrase 3 is the original text"),
    ],
)
def test_a_reply_that_is_not_k_distinct_new_strings_is_refused(reply: str, match: str) -> None:
    with pytest.raises(ProbatioConfigError, match=match) as excinfo:
        parse_paraphrases(reply, original="q", k=3, case_id="c1")
    assert "[c1]" in str(excinfo.value)


def test_a_bad_reply_fails_the_command_rather_than_writing_a_short_file(
    one_case: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        cli_module, "build_provider", lambda name, model: paraphraser('["only one"]')
    )
    out = tmp_path / "variants"
    with pytest.raises(ProbatioConfigError, match="holds 1 entries but 3"):
        run(one_case, out, "--provider", "claude-cli")
    assert not (out / "htn-definition.yaml").exists()


def test_the_error_reaches_the_console_script_as_one_line(
    one_case: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    monkeypatch.setattr(cli_module, "build_provider", lambda name, model: paraphraser("prose"))
    status = main(argv(one_case, tmp_path / "v", "--provider", "claude-cli"))
    assert status == 2
    assert "probatio: [htn-definition] the paraphrase reply is not JSON" in capsys.readouterr().err


# -- the mechanical path -------------------------------------------------------------------------


def test_provider_fake_writes_rewrites_and_warns_that_they_are_not_paraphrases(
    one_case: Path, tmp_path: Path, capsys: Any
) -> None:
    out = tmp_path / "variants"
    assert run(one_case, out) == 0
    captured = capsys.readouterr()
    assert "mechanical rewrites, not paraphrases" in captured.err
    assert "--provider claude-cli" in captured.err

    contents = load_variants_file(out / "htn-definition.yaml")
    assert contents.generated_by.provider == MECHANICAL_PROVIDER
    assert contents.generated_by.model is None
    assert contents.generated_by.prompt_hash is None
    assert len(contents.variants) == 3
    assert len(set(contents.variants)) == 3


def test_freezing_a_case_with_no_text_at_the_field_is_refused_directly() -> None:
    """The command filters these out first, so this is the guard for a direct caller."""
    from probatio.metamorphic import freeze_case, freeze_mechanically

    bare = LLMCase.model_validate(
        {"id": "bare", "input": "a bare string", "assertions": [{"type": "contains", "any": ["x"]}]}
    )
    with pytest.raises(ProbatioConfigError, match="nothing to paraphrase") as excinfo:
        freeze_case(bare, field="input.question", k=3, provider=paraphraser(), clock=clock)
    assert "[bare]" in str(excinfo.value)
    with pytest.raises(ProbatioConfigError, match="nothing to rewrite"):
        freeze_mechanically(bare, field="input.question", k=3, clock=clock)


def test_mechanical_rewrites_are_distinct_and_never_the_original() -> None:
    rewrites = mechanical_rewrites("A question?", 7)
    assert len(rewrites) == 7
    assert len(set(rewrites)) == 7
    assert "A question?" not in rewrites
    assert all(rewrite.strip() for rewrite in rewrites)


# -- the batch rules -----------------------------------------------------------------------------


def test_a_case_without_the_field_is_skipped_not_fatal(tmp_path: Path, capsys: Any) -> None:
    out = tmp_path / "variants"
    assert run(CASES, out) == 0
    printed = capsys.readouterr().out
    assert "skipped copd-spirometry: no text at 'input.question'" in printed
    assert not (out / "copd-spirometry.yaml").exists()
    assert (out / "htn-definition.yaml").exists()
    assert "for 9 of 9 eligible case(s)" in printed


def test_an_existing_file_is_skipped_unless_force(
    one_case: Path, tmp_path: Path, capsys: Any
) -> None:
    out = tmp_path / "variants"
    run(one_case, out)
    before = (out / "htn-definition.yaml").read_bytes()

    capsys.readouterr()
    assert run(one_case, out, "--k", "4") == 0
    assert "exists (pass --force to overwrite)" in capsys.readouterr().out
    assert (out / "htn-definition.yaml").read_bytes() == before

    assert run(one_case, out, "--k", "4", "--force") == 0
    assert len(load_variants_file(out / "htn-definition.yaml").variants) == 4


def test_a_field_that_resolves_on_no_case_is_a_mistake_in_the_flag(tmp_path: Path) -> None:
    args = build_parser().parse_args(
        [
            "freeze-variants",
            "--cases",
            str(CASES),
            "--field",
            "input.quesion",
            "--out",
            str(tmp_path / "v"),
        ]
    )
    with pytest.raises(ProbatioConfigError, match="has text at 'input.quesion'"):
        freeze_variants(args, clock=clock)


def test_a_field_that_is_not_a_case_field_at_all_is_refused(tmp_path: Path) -> None:
    args = build_parser().parse_args(
        ["freeze-variants", "--cases", str(CASES), "--field", "inpit.question"]
    )
    with pytest.raises(ProbatioConfigError, match="not a field of LLMCase"):
        freeze_variants(args, clock=clock)


def test_k_below_one_is_refused(one_case: Path, tmp_path: Path) -> None:
    args = build_parser().parse_args(argv(one_case, tmp_path / "v")[:-2] + ["--k", "0"])
    with pytest.raises(ProbatioConfigError, match="--k must be at least 1"):
        freeze_variants(args, clock=clock)


def test_the_summary_goes_to_the_stream_it_was_given(
    one_case: Path, tmp_path: Path, capsys: Any
) -> None:
    args = build_parser().parse_args(argv(one_case, tmp_path / "v"))
    assert freeze_variants(args, clock=clock) == 0
    assert "wrote" in capsys.readouterr().out


def test_the_prompt_template_is_a_module_constant_a_hash_can_be_taken_over() -> None:
    assert "{k}" not in build_freeze_prompt("q", 3)
    assert build_freeze_prompt("q", 3) != build_freeze_prompt("q", 4)
