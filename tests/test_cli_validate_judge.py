"""Phase 4: ``probatio validate-judge``, in both modes, entirely offline.

``--run-judge`` is one of the two commands allowed to call a live model (spec §3.13), so every
test here injects a ``FakeProvider`` in place of the one the flag would build. Nothing in this
file reaches a network, and the two Consilium samples are read from ``tests/fixtures/``.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from probatio import FakeProvider, ProbatioConfigError
from probatio import cli as cli_module
from probatio.cli import DEFAULT_LABEL_MAP, build_provider, main, parse_label_map
from probatio.judge import ValidationRecord

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_RUBRICS = REPO_ROOT / "examples" / "demo_suite" / "rubrics"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "consilium"
SAMPLE_1 = FIXTURES / "judge-sample-labeled.csv"
SAMPLE_2 = FIXTURES / "judge-sample-2-labeled.csv"
RUBRIC = DEMO_RUBRICS / "faithfulness.md"

SENTINEL_JUDGE = "ZZJUDGECOLUMNZZ"
SENTINEL_NOTES = "ZZHUMANNOTESZZ"

ROW_TEMPLATE = (
    "{item},{question},{answer},{context}," + f"{SENTINEL_JUDGE},{SENTINEL_NOTES}," + "{human}"
)
ROWS = "\n".join(
    [
        "item_id,question,answer,sources_text,judge_label,human_notes,human_label",
        ROW_TEMPLATE.format(
            item="r1",
            question="Does spirometry confirm COPD?",
            answer="grounded one",
            context="Spirometry confirms COPD.",
            human="supported",
        ),
        ROW_TEMPLATE.format(
            item="r2",
            question="What is first-line?",
            answer="grounded two",
            context="Thiazides are first-line.",
            human="supported",
        ),
        ROW_TEMPLATE.format(
            item="r3",
            question="When to screen?",
            answer="invented one",
            context="Screening starts at 35.",
            human="unsupported",
        ),
        ROW_TEMPLATE.format(
            item="r4",
            question="Which alarm features?",
            answer="invented two",
            context="Weight loss is an alarm feature.",
            human="supported",
        ),
        "",
    ]
)


def columns_argv(labels: Path, out: Path, *extra: str) -> list[str]:
    return [
        "validate-judge",
        "--labels",
        str(labels),
        "--human-column",
        "human_label",
        "--judge-column",
        "judge_label",
        "--rubric",
        str(RUBRIC),
        "--out",
        str(out),
        *extra,
    ]


def read_record(out: Path) -> ValidationRecord:
    payload = (out / "faithfulness.validation.json").read_text(encoding="utf-8")
    return ValidationRecord.model_validate_json(payload)


# --- columns mode -------------------------------------------------------------------------------


def test_sample_1_prints_and_records_the_published_numbers(tmp_path: Path, capsys: Any) -> None:
    assert main(columns_argv(SAMPLE_1, tmp_path)) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 2
    assert "n=40 agreement=0.675 kappa=0.350" in lines[0]
    assert "method: columns" in lines[0]
    assert str(tmp_path / "faithfulness.validation.json") in lines[1]

    record = read_record(tmp_path)
    assert record.n == 40
    assert round(record.agreement, 3) == 0.675
    assert round(record.kappa, 3) == 0.350
    assert record.method == "columns"
    assert record.judge_model is None
    assert record.labels_file == str(SAMPLE_1)


def test_sample_2_records_the_published_numbers(tmp_path: Path, capsys: Any) -> None:
    assert main(columns_argv(SAMPLE_2, tmp_path)) == 0
    assert "n=40 agreement=0.800 kappa=0.592" in capsys.readouterr().out
    record = read_record(tmp_path)
    assert round(record.kappa, 3) == 0.592


def test_the_record_pins_the_rubric_text_and_the_labels_file(tmp_path: Path) -> None:
    from probatio.judge import hash_labels_file, resolve_rubric

    main(columns_argv(SAMPLE_2, tmp_path))
    record = read_record(tmp_path)
    assert record.rubric == "faithfulness"
    assert record.rubric_hash == resolve_rubric(str(RUBRIC)).content_hash
    assert record.labels_hash == hash_labels_file(SAMPLE_2)


# --- --min-kappa --------------------------------------------------------------------------------


def test_a_min_kappa_above_the_measured_value_exits_1(tmp_path: Path, capsys: Any) -> None:
    assert main(columns_argv(SAMPLE_1, tmp_path, "--min-kappa", "0.6")) == 1
    captured = capsys.readouterr()
    assert "kappa 0.350 is below --min-kappa 0.600" in captured.err
    assert (tmp_path / "faithfulness.validation.json").is_file(), (
        "the measurement is recorded even when it is disappointing"
    )


def test_a_min_kappa_below_the_measured_value_exits_0(tmp_path: Path) -> None:
    assert main(columns_argv(SAMPLE_1, tmp_path, "--min-kappa", "0.3")) == 0


# --- --run-judge --------------------------------------------------------------------------------


def fake_judge(prompt: str) -> str:
    """Pass an answer that says "grounded", fail one that does not."""
    verdict = "pass" if "grounded" in prompt else "fail"
    score = 1.0 if verdict == "pass" else 0.0
    return json.dumps({"verdict": verdict, "score": score, "rationale": "by keyword"})


@pytest.fixture
def rows_csv(tmp_path: Path) -> Path:
    path = tmp_path / "rows.csv"
    path.write_text(ROWS, encoding="utf-8")
    return path


@pytest.fixture
def injected_provider(monkeypatch: Any) -> FakeProvider:
    """Replace the provider factory, so ``--run-judge`` cannot reach a live model in a test."""
    provider = FakeProvider(default=fake_judge, model="fake-judge-1")
    monkeypatch.setattr(cli_module, "build_provider", lambda name, model: provider)
    return provider


def run_judge_argv(labels: Path, out: Path, *extra: str) -> list[str]:
    return [
        "validate-judge",
        "--labels",
        str(labels),
        "--human-column",
        "human_label",
        "--rubric",
        str(RUBRIC),
        "--run-judge",
        "--answer-column",
        "answer",
        "--question-column",
        "question",
        "--context-column",
        "sources_text",
        "--out",
        str(out),
        *extra,
    ]


def test_run_judge_grades_every_row_and_records_the_measurement(
    tmp_path: Path, rows_csv: Path, injected_provider: FakeProvider, capsys: Any
) -> None:
    out = tmp_path / "judges"
    assert main(run_judge_argv(rows_csv, out)) == 0
    assert injected_provider.call_count == 4

    # Three of four rows agree; judge 2/2, human 3/1, so p_e = 0.5 and kappa = 0.5.
    assert "n=4 agreement=0.750 kappa=0.500" in capsys.readouterr().out
    record = read_record(out)
    assert record.method == "run-judge"
    assert record.judge_model == "fake-judge-1"
    assert record.n == 4


def test_run_judge_sends_the_question_and_the_context_and_the_answer(
    tmp_path: Path, rows_csv: Path, injected_provider: FakeProvider
) -> None:
    main(run_judge_argv(rows_csv, tmp_path))
    first = injected_provider.calls[0].prompt
    assert "Does spirometry confirm COPD?" in first
    assert "Spirometry confirms COPD." in first
    assert "grounded one" in first


def test_the_judge_never_sees_the_label_columns(
    tmp_path: Path, rows_csv: Path, injected_provider: FakeProvider
) -> None:
    """A judge shown the label it is being measured against measures nothing."""
    main(run_judge_argv(rows_csv, tmp_path))
    for call in injected_provider.calls:
        assert SENTINEL_JUDGE not in call.prompt
        assert SENTINEL_NOTES not in call.prompt
        assert "judge_label" not in call.prompt
        assert "human_label" not in call.prompt


def test_run_judge_ignores_an_existing_judge_column(
    tmp_path: Path, rows_csv: Path, injected_provider: FakeProvider
) -> None:
    """The point of the flag is to produce the judge labels, not to read them."""
    assert main(run_judge_argv(rows_csv, tmp_path, "--judge-column", "judge_label")) == 0
    assert read_record(tmp_path).method == "run-judge"


def test_the_label_map_translates_the_judges_verdicts_into_the_human_label_space(
    tmp_path: Path, rows_csv: Path, injected_provider: FakeProvider
) -> None:
    """Without the map the label spaces are disjoint, so agreement would be exactly zero."""
    assert main(run_judge_argv(rows_csv, tmp_path, "--label-map", "")) == 0
    assert read_record(tmp_path).agreement == 0.0


def test_a_judge_that_does_not_answer_with_a_verdict_stops_the_command(
    tmp_path: Path, rows_csv: Path, monkeypatch: Any, capsys: Any
) -> None:
    monkeypatch.setattr(
        cli_module, "build_provider", lambda name, model: FakeProvider(default="prose")
    )
    assert main(run_judge_argv(rows_csv, tmp_path)) == 2
    assert "judge output was not valid JSON" in capsys.readouterr().err


def test_a_row_with_no_answer_to_grade_is_reported(
    tmp_path: Path, injected_provider: FakeProvider, capsys: Any
) -> None:
    path = tmp_path / "rows.csv"
    path.write_text("answer,human_label\n,supported\n", encoding="utf-8")
    assert main(run_judge_argv(path, tmp_path)) == 2
    assert "row 1 has no 'answer'" in capsys.readouterr().err


def test_a_row_with_no_input_columns_at_all_is_reported(
    tmp_path: Path, injected_provider: FakeProvider, capsys: Any
) -> None:
    path = tmp_path / "rows.csv"
    path.write_text("answer,human_label\nan answer,supported\n", encoding="utf-8")
    assert main(run_judge_argv(path, tmp_path)) == 2
    assert "--question-column" in capsys.readouterr().err


# --- bad arguments and bad data -----------------------------------------------------------------


def test_columns_mode_without_a_judge_column_says_which_flag_is_missing(
    tmp_path: Path, capsys: Any
) -> None:
    argv = [
        "validate-judge",
        "--labels",
        str(SAMPLE_1),
        "--human-column",
        "human_label",
        "--rubric",
        str(RUBRIC),
        "--out",
        str(tmp_path),
    ]
    assert main(argv) == 2
    assert "--judge-column" in capsys.readouterr().err


def test_a_labels_file_that_does_not_exist_is_reported(tmp_path: Path, capsys: Any) -> None:
    assert main(columns_argv(tmp_path / "nothing.csv", tmp_path)) == 2
    assert "cannot read labels file" in capsys.readouterr().err


def test_a_missing_column_names_the_columns_the_file_does_have(tmp_path: Path, capsys: Any) -> None:
    path = tmp_path / "rows.csv"
    path.write_text("item_id,verdict\nr1,pass\n", encoding="utf-8")
    assert main(columns_argv(path, tmp_path)) == 2
    error = capsys.readouterr().err
    assert "'human_label'" in error
    assert "'verdict'" in error


def test_an_empty_labels_file_is_reported(tmp_path: Path, capsys: Any) -> None:
    path = tmp_path / "rows.csv"
    path.write_text("judge_label,human_label\n", encoding="utf-8")
    assert main(columns_argv(path, tmp_path)) == 2
    assert "holds no rows" in capsys.readouterr().err


def test_a_row_with_a_blank_label_cannot_be_compared(tmp_path: Path, capsys: Any) -> None:
    path = tmp_path / "rows.csv"
    path.write_text("judge_label,human_label\nsupported,\n", encoding="utf-8")
    assert main(columns_argv(path, tmp_path)) == 2
    assert "row 1 has no 'human_label'" in capsys.readouterr().err


def test_a_rubric_that_resolves_nowhere_is_reported(tmp_path: Path, capsys: Any) -> None:
    argv = columns_argv(SAMPLE_1, tmp_path)
    argv[argv.index("--rubric") + 1] = "not-a-rubric"
    assert main(argv) == 2
    assert "was not found" in capsys.readouterr().err


# --- the label map ------------------------------------------------------------------------------


def test_the_default_label_map_is_the_judge_to_consilium_pair() -> None:
    assert parse_label_map(DEFAULT_LABEL_MAP) == {"pass": "supported", "fail": "unsupported"}


def test_an_empty_label_map_compares_labels_verbatim() -> None:
    assert parse_label_map("") == {}


def test_whitespace_and_a_trailing_comma_are_tolerated() -> None:
    assert parse_label_map(" pass = supported , ") == {"pass": "supported"}


@pytest.mark.parametrize("text", ["pass", "pass=", "=supported", "pass:supported"])
def test_a_malformed_label_map_entry_is_a_config_error(text: str) -> None:
    with pytest.raises(ProbatioConfigError):
        parse_label_map(text)


# --- the provider factory -----------------------------------------------------------------------


def test_the_fake_provider_is_the_default_and_needs_nothing_installed() -> None:
    provider = build_provider("fake", None)
    assert provider.name == "fake"


def test_the_claude_cli_provider_is_constructed_without_running_anything() -> None:
    assert build_provider("claude-cli", "claude-sonnet-4-5").name == "claude-cli"


def test_an_unknown_provider_name_lists_the_ones_that_exist() -> None:
    with pytest.raises(ProbatioConfigError) as excinfo:
        build_provider("openai", None)
    assert "fake, anthropic, claude-cli" in str(excinfo.value)


@pytest.fixture
def fresh_anthropic_adapter(monkeypatch: Any) -> Iterator[None]:
    """Import the Anthropic adapter fresh here, and leave no stub of it behind."""
    monkeypatch.delitem(sys.modules, "probatio.providers.anthropic", raising=False)
    yield
    sys.modules.pop("probatio.providers.anthropic", None)


def test_the_anthropic_provider_is_built_from_the_sdk_when_the_extra_is_installed(
    monkeypatch: Any, fresh_anthropic_adapter: None
) -> None:
    """Stubbed in ``sys.modules``, exactly as the Phase 2 adapter tests do it; no SDK is used."""
    stub = ModuleType("anthropic")
    stub.Anthropic = lambda: SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: None))
    monkeypatch.setitem(sys.modules, "anthropic", stub)
    assert build_provider("anthropic", "claude-x").name == "anthropic"


def test_naming_anthropic_without_the_extra_names_the_extra(
    monkeypatch: Any, fresh_anthropic_adapter: None
) -> None:
    """The adapter imports the SDK at import time (DECISIONS 15), so this is where it surfaces."""
    monkeypatch.setitem(sys.modules, "anthropic", None)
    with pytest.raises(ProbatioConfigError) as excinfo:
        build_provider("anthropic", None)
    assert "anthropic" in str(excinfo.value)


# --- the bare script ----------------------------------------------------------------------------


def test_the_script_with_no_subcommand_prints_its_help(capsys: Any) -> None:
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "validate-judge" in out


def test_the_help_text_lists_every_validate_judge_flag(capsys: Any) -> None:
    with pytest.raises(SystemExit):
        main(["validate-judge", "--help"])
    out = capsys.readouterr().out
    for flag in (
        "--labels",
        "--human-column",
        "--judge-column",
        "--rubric",
        "--run-judge",
        "--provider",
        "--model",
        "--answer-column",
        "--context-column",
        "--label-map",
        "--min-kappa",
        "--out",
    ):
        assert flag in out
