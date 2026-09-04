"""Phase 7: `probatio import-cassettes` — a trace on disk becomes tapes that replay (§3.13)."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

from probatio import FakeProvider
from probatio.cassette import IMPORT_PROVIDER, CassetteProvider, CassetteStore
from probatio.cli import DEFAULT_CASSETTE_OUT, build_parser, main

SUITE = "consilium"
PROMPT = "What is high blood pressure?"


def trace(path: Path) -> Path:
    """Write the three-line JSONL spec §3.8 describes and return its path."""
    lines = [
        {
            "case_id": "htn-definition",
            "prompt": PROMPT,
            "system": "Answer only from the documents.",
            "params": {"model": "claude-sonnet-5", "temperature": 0},
            "model": "claude-sonnet-5",
            "text": "Hypertension is sustained high pressure.",
            "tokens_in": 512,
            "tokens_out": 33,
            "cost_usd": 0.0021,
            "latency_ms": 1840.0,
        },
        {
            "case_id": "htn-definition",
            "prompt": PROMPT,
            "system": "Answer only from the documents.",
            "params": {"model": "claude-sonnet-5", "temperature": 0},
            "model": "claude-sonnet-5",
            "text": "High blood pressure is pressure that stays raised.",
            "tokens_in": 512,
            "tokens_out": 29,
            "cost_usd": 0.0019,
            "latency_ms": 1610.0,
        },
        {
            "case_id": "copd-spirometry",
            "prompt": "What does spirometry measure?",
            "model": "claude-sonnet-5",
            "text": "It measures airflow obstruction.",
            "latency_ms": 900.0,
        },
    ]
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
    return path


def run(argv: list[str]) -> tuple[int, str]:
    """Run the console script and return its status and everything it printed."""
    stream = io.StringIO()
    parser = build_parser()
    args = parser.parse_args(argv)
    status: int = args.handler(args, stream=stream)
    return status, stream.getvalue()


def test_a_three_line_trace_produces_files_that_replay(tmp_path: Path) -> None:
    source = trace(tmp_path / "traces.jsonl")
    out = tmp_path / "cassettes"
    status, printed = run(
        ["import-cassettes", "--from", str(source), "--suite", SUITE, "--out", str(out)]
    )
    assert status == 0
    assert "imported 2 cassette(s)" in printed
    assert str(out / SUITE / "htn-definition.json") in printed

    tapes = CassetteStore(out)
    inner = FakeProvider(default="this must never be produced", model="claude-sonnet-5")
    player = CassetteProvider(inner, tapes, "replay")
    params: dict[str, Any] = {"model": "claude-sonnet-5", "temperature": 0}

    answers = []
    for run_index in range(2):
        tapes.begin_case(SUITE, "htn-definition", run_index)
        answers.append(
            player.complete(PROMPT, system="Answer only from the documents.", **params).text
        )
    assert answers == [
        "Hypertension is sustained high pressure.",
        "High blood pressure is pressure that stays raised.",
    ]

    tapes.begin_case(SUITE, "copd-spirometry", 0)
    spirometry = player.complete("What does spirometry measure?")
    assert spirometry.text == "It measures airflow obstruction."
    assert spirometry.cost_usd is None, "an unpriced trace line stays unpriced, never 0.0"
    assert inner.call_count == 0, "the whole point: importing removes the model from the loop"


def test_the_tape_records_which_provider_the_trace_came_from(tmp_path: Path) -> None:
    source = trace(tmp_path / "traces.jsonl")
    out = tmp_path / "cassettes"
    run(["import-cassettes", "--from", str(source), "--suite", SUITE, "--out", str(out)])
    payload = json.loads((out / SUITE / "htn-definition.json").read_text(encoding="utf-8"))
    assert payload["provider"] == IMPORT_PROVIDER

    other = tmp_path / "other"
    run(
        [
            "import-cassettes",
            "--from",
            str(source),
            "--suite",
            SUITE,
            "--out",
            str(other),
            "--provider",
            "claude-cli",
        ]
    )
    payload = json.loads((other / SUITE / "htn-definition.json").read_text(encoding="utf-8"))
    assert payload["provider"] == "claude-cli"


def test_a_malformed_line_exits_two_and_names_the_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "traces.jsonl"
    source.write_text('{"case_id": "a", "prompt": "p", "text": "t", "model": "m"}\nnope\n')
    status = main(
        ["import-cassettes", "--from", str(source), "--suite", SUITE, "--out", str(tmp_path)]
    )
    assert status == 2
    assert "line 2" in capsys.readouterr().err


def test_a_missing_trace_exits_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    status = main(
        [
            "import-cassettes",
            "--from",
            str(tmp_path / "absent.jsonl"),
            "--suite",
            SUITE,
            "--out",
            str(tmp_path),
        ]
    )
    assert status == 2
    assert "cannot read trace file" in capsys.readouterr().err


def test_main_runs_the_command_and_prints_to_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = trace(tmp_path / "traces.jsonl")
    status = main(
        [
            "import-cassettes",
            "--from",
            str(source),
            "--suite",
            SUITE,
            "--out",
            str(tmp_path / "out"),
        ]
    )
    assert status == 0
    assert "imported 2 cassette(s)" in capsys.readouterr().out


def test_the_out_directory_defaults_to_the_committed_location() -> None:
    args = build_parser().parse_args(["import-cassettes", "--from", "t.jsonl", "--suite", SUITE])
    assert args.out == str(DEFAULT_CASSETTE_OUT)
    assert args.provider == IMPORT_PROVIDER
    assert args.source == "t.jsonl"


def test_the_help_text_lists_the_command_and_its_flags(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([]) == 0
    assert "import-cassettes" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        build_parser().parse_args(["import-cassettes", "--help"])
    help_text = capsys.readouterr().out
    for flag in ("--from", "--suite", "--out", "--provider"):
        assert flag in help_text
    assert "calls no model" in help_text
