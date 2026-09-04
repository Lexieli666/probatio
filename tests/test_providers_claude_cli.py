"""Phase 2: the Claude CLI adapter, parsed against one real captured payload.

``tests/fixtures/claude_cli_payload.json`` is a verbatim copy of what
``claude -p 'reply with PAYLOAD_CHECK' --output-format json --tools ""`` printed on the version
recorded in ``DECISIONS.md`` entry 14. No test here runs the CLI: :func:`subprocess.run` is
monkeypatched, and the fake asserts that the working directory it was handed is an empty
temporary one, which is how "no project context" is obtained.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from probatio import Completion, ProbatioConfigError
from probatio.providers.claude_cli import UNKNOWN_MODEL, ClaudeCLIProvider

PAYLOAD_PATH = Path(__file__).parent / "fixtures" / "claude_cli_payload.json"
PAYLOAD_TEXT = PAYLOAD_PATH.read_text(encoding="utf-8")
PAYLOAD: dict[str, Any] = json.loads(PAYLOAD_TEXT)


def fake_run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stdout: str = PAYLOAD_TEXT,
    stderr: str = "",
    returncode: int = 0,
    raises: BaseException | None = None,
) -> list[dict[str, Any]]:
    """Replace :func:`subprocess.run` and return the list its calls are recorded in."""
    recorded: list[dict[str, Any]] = []

    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        cwd = Path(kwargs["cwd"])
        assert cwd.is_dir(), "the CLI must run in a directory that exists"
        assert list(cwd.iterdir()) == [], "the working directory must be empty: no CLAUDE.md"
        recorded.append({"argv": list(argv), **kwargs})
        if raises is not None:
            raise raises
        return subprocess.CompletedProcess(argv, returncode, stdout, stderr)

    monkeypatch.setattr("probatio.providers.claude_cli.subprocess.run", run)
    return recorded


def test_the_payload_fixture_is_the_captured_one() -> None:
    assert PAYLOAD["result"] == "PAYLOAD_CHECK"
    assert PAYLOAD["num_turns"] == 1
    assert PAYLOAD["subtype"] == "success"
    assert PAYLOAD["is_error"] is False


def test_a_captured_payload_maps_onto_a_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = ClaudeCLIProvider(model="claude-opus-5[1m]")
    completion = provider.complete("reply with PAYLOAD_CHECK")

    assert isinstance(completion, Completion)
    assert completion.text == "PAYLOAD_CHECK"
    assert completion.model == "claude-opus-5[1m]"
    assert completion.tokens_in == 469
    assert completion.tokens_out == 14
    assert completion.cost_usd == 0.0037689999999999998
    assert completion.latency_ms == 1610.0
    assert completion.raw == PAYLOAD
    assert provider.name == "claude-cli"


@pytest.fixture(autouse=True)
def _no_real_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test in this module gets the fake by default, so none can reach the real CLI."""
    fake_run(monkeypatch)


def test_the_command_line_is_one_non_interactive_json_turn_with_no_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded = fake_run(monkeypatch)
    ClaudeCLIProvider(model="opus").complete("the prompt", system="the system prompt")

    argv = recorded[0]["argv"]
    assert argv == [
        "claude",
        "-p",
        "the prompt",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--model",
        "opus",
        "--system-prompt",
        "the system prompt",
        "--tools",
        "",
    ]
    assert argv[1:3] == ["-p", "the prompt"], "the prompt is the positional argument after -p"
    assert argv[-2:] == ["--tools", ""], "--tools is variadic, so nothing may follow its value"
    assert "--bare" not in argv, "--bare would force API-key authentication (DECISIONS 14)"
    assert "--max-turns" not in argv, "this CLI version has no such flag (DECISIONS 14)"
    assert recorded[0]["timeout"] == 120.0
    assert recorded[0]["capture_output"] is True
    assert recorded[0]["text"] is True
    assert recorded[0]["check"] is False


def test_flags_the_model_and_the_system_prompt_are_left_out_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded = fake_run(monkeypatch)
    ClaudeCLIProvider().complete("the prompt")
    assert recorded[0]["argv"] == [
        "claude",
        "-p",
        "the prompt",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--tools",
        "",
    ]


def test_every_flag_name_and_the_executable_can_be_overridden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A flag belongs to somebody else's program, so a rename is a constructor argument."""
    recorded = fake_run(monkeypatch)
    provider = ClaudeCLIProvider(
        model="opus",
        executable="/opt/claude",
        timeout_s=5.0,
        print_flag="--print",
        output_format_flag="--format",
        output_format="json",
        model_flag="-m",
        system_prompt_flag="--system",
        tools_flag="--no-tools",
        tools="none",
        session_persistence_flag="--ephemeral",
        extra_args=["--effort", "low"],
    )
    provider.complete("p", system="s")
    assert recorded[0]["argv"] == [
        "/opt/claude",
        "--print",
        "p",
        "--format",
        "json",
        "--ephemeral",
        "-m",
        "opus",
        "--system",
        "s",
        "--effort",
        "low",
        "--no-tools",
        "none",
    ]
    assert recorded[0]["timeout"] == 5.0


def test_the_cases_model_param_overrides_the_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded = fake_run(monkeypatch)
    completion = ClaudeCLIProvider(model="opus").complete("p", model="haiku")
    assert recorded[0]["argv"][recorded[0]["argv"].index("--model") + 1] == "haiku"
    assert completion.model == "haiku"


def test_params_this_cli_version_cannot_honour_are_recorded_not_dropped_in_silence() -> None:
    completion = ClaudeCLIProvider(model="opus").complete("p", temperature=0, top_p=0.9)
    assert completion.raw["probatio_ignored_params"] == ["temperature", "top_p"]
    assert "probatio_ignored_params" not in ClaudeCLIProvider(model="o").complete("p").raw


def test_the_model_is_named_from_the_payload_only_when_it_names_exactly_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The captured payload lists two models, because the CLI bills side work to a small one."""
    assert len(PAYLOAD["modelUsage"]) == 2
    assert ClaudeCLIProvider().complete("p").model == UNKNOWN_MODEL

    one_model = {**PAYLOAD, "modelUsage": {"claude-opus-5[1m]": {}}}
    fake_run(monkeypatch, stdout=json.dumps(one_model))
    assert ClaudeCLIProvider().complete("p").model == "claude-opus-5[1m]"

    fake_run(
        monkeypatch, stdout=json.dumps({k: v for k, v in PAYLOAD.items() if k != "modelUsage"})
    )
    assert ClaudeCLIProvider().complete("p").model == UNKNOWN_MODEL


def test_a_payload_without_a_duration_falls_back_to_the_measured_elapsed_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stripped = {key: value for key, value in PAYLOAD.items() if key != "duration_ms"}
    fake_run(monkeypatch, stdout=json.dumps(stripped))
    assert ClaudeCLIProvider().complete("p").latency_ms > 0.0


def test_missing_cost_and_usage_are_unknown_rather_than_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stripped = {
        key: value for key, value in PAYLOAD.items() if key not in {"total_cost_usd", "usage"}
    }
    fake_run(monkeypatch, stdout=json.dumps(stripped))
    completion = ClaudeCLIProvider().complete("p")
    assert completion.cost_usd is None
    assert (completion.tokens_in, completion.tokens_out) == (None, None)


def test_a_non_zero_exit_names_the_command_and_quotes_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_run(monkeypatch, returncode=1, stdout="", stderr="Invalid API key")
    with pytest.raises(ProbatioConfigError) as caught:
        ClaudeCLIProvider().complete("p")
    assert "exited 1" in str(caught.value)
    assert "claude -p" in str(caught.value)
    assert "Invalid API key" in str(caught.value)


def test_unparsable_stdout_quotes_what_was_written(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_run(monkeypatch, stdout="Welcome to Claude Code!\n", stderr="")
    with pytest.raises(ProbatioConfigError) as caught:
        ClaudeCLIProvider().complete("p")
    assert "no parsable json on stdout" in str(caught.value)
    assert "Welcome to Claude Code!" in str(caught.value)
    assert "stderr: <empty>" in str(caught.value)


def test_json_that_is_not_an_object_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_run(monkeypatch, stdout="[1, 2, 3]")
    with pytest.raises(ProbatioConfigError, match="wrote a list, not a JSON object"):
        ClaudeCLIProvider().complete("p")


@pytest.mark.parametrize(
    "overrides",
    [
        {"is_error": True},
        {"subtype": "error_max_turns"},
        {"is_error": True, "api_error_status": 529, "result": "Overloaded"},
    ],
)
def test_a_payload_that_reports_an_error_is_an_error(
    monkeypatch: pytest.MonkeyPatch, overrides: dict[str, Any]
) -> None:
    fake_run(monkeypatch, stdout=json.dumps({**PAYLOAD, **overrides}), stderr="an explanation")
    with pytest.raises(ProbatioConfigError) as caught:
        ClaudeCLIProvider().complete("p")
    assert "reported an error" in str(caught.value)
    assert "an explanation" in str(caught.value)


def test_a_payload_with_no_result_string_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_run(monkeypatch, stdout=json.dumps({key: PAYLOAD[key] for key in ("subtype", "usage")}))
    with pytest.raises(ProbatioConfigError, match="no 'result' string"):
        ClaudeCLIProvider().complete("p")


def test_a_missing_executable_names_it_and_how_to_install_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_run(monkeypatch, raises=FileNotFoundError(2, "No such file or directory"))
    with pytest.raises(ProbatioConfigError) as caught:
        ClaudeCLIProvider(executable="claude-x").complete("p")
    assert "'claude-x' was not found on PATH" in str(caught.value)
    assert caught.value.fix == "npm install -g @anthropic-ai/claude-code"


def test_a_timeout_says_how_long_it_waited(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_run(
        monkeypatch,
        raises=subprocess.TimeoutExpired(cmd=["claude"], timeout=5.0, stderr="thinking..."),
    )
    with pytest.raises(ProbatioConfigError) as caught:
        ClaudeCLIProvider(timeout_s=5.0).complete("p")
    assert "did not answer within 5s" in str(caught.value)
    assert "thinking..." in str(caught.value)


def test_stderr_is_truncated_rather_than_pasted_whole(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_run(monkeypatch, returncode=2, stderr="x" * 5000)
    with pytest.raises(ProbatioConfigError) as caught:
        ClaudeCLIProvider().complete("p")
    assert "... (truncated)" in str(caught.value)
    assert len(str(caught.value)) < 2500


def test_argv_is_a_list_so_nothing_is_shell_parsed() -> None:
    argv = ClaudeCLIProvider().argv("rm -rf / ; echo $HOME", system=None, model=None)
    assert argv[2] == "rm -rf / ; echo $HOME"
    assert all(isinstance(part, str) for part in argv)


def test_stderr_captured_as_bytes_is_still_readable(monkeypatch: pytest.MonkeyPatch) -> None:
    """``TimeoutExpired`` carries bytes when the child was not started in text mode."""
    fake_run(
        monkeypatch,
        raises=subprocess.TimeoutExpired(cmd=["claude"], timeout=1.0, stderr=b"still thinking"),
    )
    with pytest.raises(ProbatioConfigError, match="still thinking"):
        ClaudeCLIProvider(timeout_s=1.0).complete("p")


def test_blank_stderr_reads_as_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_run(monkeypatch, returncode=1, stderr="   \n")
    with pytest.raises(ProbatioConfigError, match="stderr: <empty>"):
        ClaudeCLIProvider().complete("p")


def test_a_timeout_that_captured_no_stderr_at_all_still_reports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_run(monkeypatch, raises=subprocess.TimeoutExpired(cmd=["claude"], timeout=1.0))
    with pytest.raises(ProbatioConfigError, match="did not answer within 1s; stderr: <empty>"):
        ClaudeCLIProvider(timeout_s=1.0).complete("p")
