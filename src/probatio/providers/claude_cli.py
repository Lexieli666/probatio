"""``ClaudeCLIProvider``: the Claude Code CLI as a subprocess, for developers on a plan.

This adapter exists so that recording cassettes and freezing paraphrase variants does not require
an API key: a developer with the CLI installed and signed in can run
``pytest --cassette=record --probatio-provider claude-cli`` once, commit the tapes, and let CI
replay them at no cost. It is never used by Probatio's own test suite, which monkeypatches
:func:`subprocess.run` and reads a captured payload from ``tests/fixtures/``.

The contract Probatio needs from the CLI is one non-interactive turn, machine-readable, with no
project context and no tools. Flag names are constructor arguments because they belong to a
version of somebody else's program: when they change, a user overrides one argument instead of
waiting for a Probatio release. ``DECISIONS.md`` entry 14 records which flags were chosen from
``claude --help`` at Phase 2 and, just as importantly, which were not.

Cost caveat: ``total_cost_usd`` in the CLI's payload is the **notional API price** of the turn as
the CLI computes it. A developer running this on a Claude subscription is not billed that money.
It is reported because it is the only cost signal available and it makes a cost ceiling
enforceable, not because it is an invoice.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
from collections.abc import Sequence
from typing import Any, Final

from ..errors import ProbatioConfigError
from .base import Completion

__all__ = ["DEFAULT_TIMEOUT_S", "UNKNOWN_MODEL", "ClaudeCLIProvider"]

DEFAULT_TIMEOUT_S: Final = 120.0
"""A single turn with no tools is quick; two minutes is a hung-process ceiling, not a budget."""

UNKNOWN_MODEL: Final = "claude-cli"
"""Reported as the model when neither the caller nor the payload names exactly one."""

_STDERR_LIMIT: Final = 2000
"""How much of the CLI's stderr an error message quotes before truncating it."""


class ClaudeCLIProvider:
    """Runs ``claude -p`` once per call and parses its JSON result.

    Each call runs in a fresh empty temporary directory, so no ``CLAUDE.md`` in the user's project
    is discovered and the model sees only the prompt and the system prompt. Directory-scoped
    context is excluded that way rather than with ``--bare``, which also switches authentication
    to ``ANTHROPIC_API_KEY`` and so would defeat the point of this adapter. User-level
    configuration outside the working directory still applies; a run recorded here is reproducible
    from its cassette, not from another machine's account.

    This CLI version has no sampling flags, so ``temperature`` and friends cannot be honoured.
    They are listed under ``probatio_ignored_params`` on the completion's ``raw`` rather than
    dropped in silence, and they still take part in the cassette key, so a tape records the
    parameters the case asked for.

    Attributes:
        name: ``"claude-cli"``.
    """

    name: str = "claude-cli"

    def __init__(
        self,
        *,
        model: str | None = None,
        executable: str = "claude",
        timeout_s: float = DEFAULT_TIMEOUT_S,
        print_flag: str = "-p",
        output_format_flag: str = "--output-format",
        output_format: str = "json",
        model_flag: str = "--model",
        system_prompt_flag: str = "--system-prompt",
        tools_flag: str = "--tools",
        tools: str = "",
        session_persistence_flag: str = "--no-session-persistence",
        extra_args: Sequence[str] = (),
    ) -> None:
        """Configure the executable, the timeout and every flag name used to invoke it.

        Args:
            model: The default model, used for calls whose ``params`` name none.
            executable: The CLI to run; a path works as well as a name on ``PATH``.
            timeout_s: Seconds before the subprocess is killed and the call fails.
            print_flag: Non-interactive mode. The prompt is passed as the positional argument
                immediately after it.
            output_format_flag: Selects the output format.
            output_format: The format value; the parser here expects ``json``.
            model_flag: Passes the model through.
            system_prompt_flag: Passes the system prompt through.
            tools_flag: Selects the available built-in tools.
            tools: The empty string disables all tools. With no tools the CLI cannot take a
                second turn, which is how "one turn" is obtained on a version that has no
                ``--max-turns``.
            session_persistence_flag: Stops the run being written to the session store.
            extra_args: Further arguments, inserted before the tools flag.
        """
        self.model = model
        self.executable = executable
        self.timeout_s = timeout_s
        self.print_flag = print_flag
        self.output_format_flag = output_format_flag
        self.output_format = output_format
        self.model_flag = model_flag
        self.system_prompt_flag = system_prompt_flag
        self.tools_flag = tools_flag
        self.tools = tools
        self.session_persistence_flag = session_persistence_flag
        self.extra_args = list(extra_args)

    def argv(
        self, prompt: str, *, system: str | None = None, model: str | None = None
    ) -> list[str]:
        """Build the command line for one call.

        The tools flag is variadic on this CLI version, so it is placed last: anything after it
        would be read as another tool name rather than as the next flag.

        Args:
            prompt: The user-turn text, passed as the positional prompt argument.
            system: The system prompt, when the case declares one.
            model: The model to pass through, when one is configured.

        Returns:
            The full argument vector, executable first.
        """
        argv = [
            self.executable,
            self.print_flag,
            prompt,
            self.output_format_flag,
            self.output_format,
            self.session_persistence_flag,
        ]
        if model:
            argv += [self.model_flag, model]
        if system is not None:
            argv += [self.system_prompt_flag, system]
        argv += self.extra_args
        argv += [self.tools_flag, self.tools]
        return argv

    def complete(self, prompt: str, *, system: str | None = None, **params: Any) -> Completion:
        """Run one turn and map the CLI's JSON result onto a :class:`Completion`.

        Args:
            prompt: The user-turn text.
            system: The system prompt, when the case declares one.
            **params: The case's parameters. ``model`` overrides the constructor's; the rest are
                recorded on ``raw`` as ignored, because this CLI version exposes no flag for them.

        Returns:
            The completion, with the CLI's notional cost.

        Raises:
            ProbatioConfigError: The executable is missing, the call timed out, it exited
                non-zero, its stdout was not the expected JSON, or the payload reports an error.
        """
        ignored = dict(params)
        model = ignored.pop("model", None) or self.model
        argv = self.argv(prompt, system=system, model=model)
        started = time.perf_counter()
        completed = self._run(argv)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        payload = self._payload(argv, completed)
        return self._completion(payload, model=model, elapsed_ms=elapsed_ms, ignored=ignored)

    def _run(self, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        """Run the CLI in an empty temporary directory so no project context is discovered."""
        with tempfile.TemporaryDirectory(prefix="probatio-claude-cli-") as empty:
            try:
                return subprocess.run(  # noqa: S603 - argv is built here, never shell-parsed
                    list(argv),
                    cwd=empty,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_s,
                    check=False,
                )
            except FileNotFoundError as exc:
                raise ProbatioConfigError(
                    f"the Claude CLI executable {self.executable!r} was not found on PATH",
                    fix="npm install -g @anthropic-ai/claude-code",
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise ProbatioConfigError(
                    f"the Claude CLI did not answer within {self.timeout_s:g}s; "
                    f"stderr: {_tail(exc.stderr)}"
                ) from exc

    def _payload(
        self, argv: Sequence[str], completed: subprocess.CompletedProcess[str]
    ) -> dict[str, Any]:
        """Parse the CLI's stdout, quoting stderr on every failure so the cause is visible."""
        stderr = _tail(completed.stderr)
        if completed.returncode != 0:
            raise ProbatioConfigError(
                f"the Claude CLI exited {completed.returncode} for "
                f"{' '.join(argv[:2])!r}; stderr: {stderr}"
            )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ProbatioConfigError(
                f"the Claude CLI wrote no parsable {self.output_format} on stdout: {exc}; "
                f"stdout began {completed.stdout[:200]!r}; stderr: {stderr}"
            ) from exc
        if not isinstance(payload, dict):
            raise ProbatioConfigError(
                f"the Claude CLI wrote a {type(payload).__name__}, not a JSON object; "
                f"stderr: {stderr}"
            )
        if payload.get("is_error") or payload.get("subtype", "success") != "success":
            raise ProbatioConfigError(
                f"the Claude CLI reported an error: subtype={payload.get('subtype')!r}, "
                f"api_error_status={payload.get('api_error_status')!r}, "
                f"result={str(payload.get('result'))[:200]!r}; stderr: {stderr}"
            )
        return payload

    def _completion(
        self,
        payload: dict[str, Any],
        *,
        model: str | None,
        elapsed_ms: float,
        ignored: dict[str, Any],
    ) -> Completion:
        """Map a successful payload onto a completion."""
        result = payload.get("result")
        if not isinstance(result, str):
            raise ProbatioConfigError(
                "the Claude CLI payload has no 'result' string, so there is no answer to test"
            )
        usage = payload.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        duration_ms = payload.get("duration_ms")
        raw: dict[str, Any] = dict(payload)
        if ignored:
            raw["probatio_ignored_params"] = sorted(ignored)
        return Completion(
            text=result,
            model=model or _model_of(payload),
            tokens_in=_int_or_none(usage.get("input_tokens")),
            tokens_out=_int_or_none(usage.get("output_tokens")),
            cost_usd=_float_or_none(payload.get("total_cost_usd")),
            latency_ms=_float_or_none(duration_ms) or elapsed_ms,
            raw=raw,
        )


def _model_of(payload: dict[str, Any]) -> str:
    """Name the model from the payload, but only when the payload names exactly one.

    A turn's ``modelUsage`` can list more than one model, because the CLI bills side work such as
    a title or a topic detection to a small model alongside the model that answered. Picking the
    busiest of them would be a guess written into every tape, so a caller who wants the answer to
    say which model produced it passes ``--probatio-model``.
    """
    usage = payload.get("modelUsage")
    if isinstance(usage, dict) and len(usage) == 1:
        return str(next(iter(usage)))
    return UNKNOWN_MODEL


def _int_or_none(value: Any) -> int | None:
    """Coerce a reported token count to ``int``, or to ``None`` when it is absent."""
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _float_or_none(value: Any) -> float | None:
    """Coerce a reported cost or duration to ``float``, or to ``None`` when it is absent."""
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _tail(stderr: str | bytes | None) -> str:
    """Render a subprocess's stderr for an error message, truncating a long one."""
    if stderr is None:
        return "<empty>"
    text = stderr.decode("utf-8", errors="replace") if isinstance(stderr, bytes) else stderr
    text = text.strip()
    if not text:
        return "<empty>"
    return text if len(text) <= _STDERR_LIMIT else f"{text[:_STDERR_LIMIT]}... (truncated)"
