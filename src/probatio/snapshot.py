"""``snapshot.py``: baselines, the record of what a case used to do.

A snapshot is the cheapest regression signal an LLM suite has. The assertions say what must be
true; the baseline says what *was* true, so that a change nobody asserted about — an answer that
still contains every required substring but has stopped naming two of the four drug classes it
used to name — is visible on the run that introduces it rather than on the day it finally trips a
threshold. Spec §3.6 gives a case two modes: ``scores`` compares the per-assertion verdicts and
scores, ``output`` compares the text itself.

Two design positions hold this module together.

The first is that **the store returns results and never raises for drift**. Every state a
comparison can reach — including the three failing ones — comes back as a
:class:`SnapshotResult` with a ``passed`` flag and a detail a human can read. Turning a failing
state into a failure is Phase 9's ``Probatio.check``'s job, and it does it with the text this
module already composed through :class:`~probatio.errors.BaselineDriftError`, so the message a
user sees is written once. The store still raises :class:`~probatio.errors.ProbatioConfigError`
for a baseline file it cannot parse, because that is a broken artefact and not drift: silently
re-recording over a file a bad merge mangled would turn a corrupted regression signal green.

The second is that **identity is a hash, never a timestamp** (spec §0). A baseline belongs to one
prompt — the case's input, system and params — through :func:`prompt_hash`, and a run whose
prompt hash differs is not compared at all: comparing the scores of a rewritten prompt against the
old prompt's scores would report drift in the answer when the question changed. The ``recorded``
field exists only so a reviewer can see how old a baseline is, and it comes from an injectable
clock so that no test in this repository reads the wall clock.
"""

from __future__ import annotations

import difflib
from collections.abc import Sequence
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .artefacts import Clock, check_path_segment, timestamp, utc_now, write_json
from .assertions import AssertionResult
from .case import LLMCase
from .errors import BaselineDriftError, ProbatioConfigError
from .hashing import stable_hash

__all__ = [
    "DIFF_MAX_LINES",
    "SCORE_DECIMALS",
    "SCORE_TOLERANCE",
    "UPDATE_COMMAND",
    "Baseline",
    "BaselineAssertion",
    "BaselineStore",
    "SnapshotMode",
    "SnapshotResult",
    "SnapshotState",
    "default_baseline_dir",
    "prompt_hash",
]

SnapshotMode = Literal["scores", "output"]
"""The two modes that have a baseline; ``off`` (spec §3.2) is neither read nor written."""

SnapshotState = Literal[
    "recorded",
    "updated",
    "unchanged",
    "prompt_changed",
    "scores_changed",
    "output_changed",
]
"""What one comparison concluded. The first three pass; the last three are drift."""

_PASSING_STATES: Final[frozenset[str]] = frozenset({"recorded", "updated", "unchanged"})
"""Recording a baseline and updating one are outcomes, not failures (spec §3.6)."""

SCORE_TOLERANCE: Final = 0.05
"""How far a score may move before ``scores`` mode calls it drift (spec §3.6)."""

SCORE_DECIMALS: Final = 6
"""Scores are rounded to this many decimals on both sides of every comparison (DECISIONS 32)."""

DIFF_MAX_LINES: Final = 40
"""The most diff lines an ``output`` mode detail carries, truncation note included."""

UPDATE_COMMAND: Final = "pytest --update-baseline"
"""The command every drift detail names, because an error without a fix is a puzzle."""

_CHANGED: Final[dict[str, SnapshotState]] = {
    "scores": "scores_changed",
    "output": "output_changed",
}
"""The drift state each mode reports, so a mode mismatch reports in the current mode's words."""


class BaselineAssertion(BaseModel):
    """One assertion's recorded outcome: what a report would have shown last time.

    Attributes:
        assertion_type: The declared ``type`` of the assertion, such as ``contains``.
        passed: Whether the assertion held when the baseline was recorded.
        score: The recorded score, rounded to :data:`SCORE_DECIMALS`, or ``None`` where the
            assertion has no meaningful number.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    assertion_type: str
    passed: bool
    score: float | None = Field(default=None, ge=0.0, le=1.0)


class Baseline(BaseModel):
    """One case's baseline file, exactly as spec §3.6 lays it out on disk.

    Attributes:
        case_id: The case this baseline belongs to; also the file's stem.
        prompt_hash: :func:`prompt_hash` of the case that recorded it.
        mode: The case's ``snapshot`` setting when it was recorded.
        output: The recorded text in ``output`` mode; ``None`` in ``scores`` mode.
        assertions: One entry per assertion, in the case's declaration order.
        recorded: When the baseline was written, as an ISO 8601 instant in UTC.
        model: The model that produced the recorded output.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    prompt_hash: str
    mode: SnapshotMode
    output: str | None = None
    assertions: list[BaselineAssertion]
    recorded: str
    model: str

    @model_validator(mode="after")
    def _output_matches_mode(self) -> Baseline:
        """Keep the file's two halves consistent, so a comparison never guesses (DECISIONS 31)."""
        if self.mode == "output" and self.output is None:
            raise ValueError("an output-mode baseline must carry the output it recorded")
        if self.mode == "scores" and self.output is not None:
            raise ValueError("a scores-mode baseline records scores, not an output")
        return self


class SnapshotResult(BaseModel):
    """What comparing one run against one baseline concluded.

    Attributes:
        case_id: The case compared.
        mode: The case's snapshot mode for this run.
        state: One of :data:`SnapshotState`.
        passed: ``False`` for the three drift states, ``True`` for the other three.
        detail: A human-readable account: the before/after table, the unified diff, or the
            one-line note that a baseline was recorded or updated.
        path: The baseline file the comparison read or wrote.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    mode: SnapshotMode
    state: SnapshotState
    passed: bool
    detail: str
    path: Path


def default_baseline_dir() -> Path:
    """Return the directory baselines are read from and written to by default.

    Returns:
        ``Path.cwd() / ".probatio" / "baseline"``, which is spec §5's location relative to
        rootdir. Phase 9's plugin passes a rootdir-based path, or ``--baseline-dir``, explicitly,
        for the same reason ``schema_file`` and rubric names take a base directory
        (DECISIONS 19, 23).
    """
    return Path.cwd() / ".probatio" / "baseline"


def prompt_hash(case: LLMCase) -> str:
    """Return the hash that says which prompt a baseline belongs to.

    Args:
        case: The case whose prompt to identify.

    Returns:
        The :func:`~probatio.hashing.stable_hash` of the case's ``input``, ``system`` and
        ``params``. Everything else about a case — its assertions, its budget, its tags — may
        change without invalidating the baseline, because none of it changes what the model was
        asked.
    """
    return stable_hash({"input": case.input, "system": case.system, "params": case.params})


def _round(score: float | None) -> float | None:
    """Round a score the one way this module rounds, so re-reading a file cannot change it."""
    return None if score is None else round(score, SCORE_DECIMALS)


def _score_changed(before: float | None, after: float | None) -> bool:
    """Report whether two scores differ by the rules of spec §3.6 and DECISIONS 32."""
    if before is None and after is None:
        return False
    if before is None or after is None:
        return True
    return round(abs(before - after), SCORE_DECIMALS) > SCORE_TOLERANCE


def _cell(passed: bool, score: float | None) -> str:
    """Render one side of a before/after row as a verdict and a score."""
    verdict = "pass" if passed else "fail"
    return f"{verdict} {'n/a':>5}" if score is None else f"{verdict} {score:.3f}"


def _table(rows: Sequence[tuple[str, str, str, str]]) -> list[str]:
    """Lay rows out as a fixed-width table under a header, indented by two spaces."""
    header = ("assertion", "baseline", "current", "change")
    widths = [max(len(row[column]) for row in (header, *rows)) for column in range(3)]
    lines = []
    for row in (header, *rows):
        cells = [row[column].ljust(widths[column]) for column in range(3)] + [row[3]]
        lines.append("  " + "  ".join(cells).rstrip())
    return lines


def _diff_lines(recorded: str, current: str) -> list[str]:
    """Return a unified diff of two outputs, capped at :data:`DIFF_MAX_LINES` lines."""
    lines = list(
        difflib.unified_diff(
            recorded.splitlines(),
            current.splitlines(),
            fromfile="baseline",
            tofile="current",
            lineterm="",
        )
    )
    if len(lines) <= DIFF_MAX_LINES:
        return lines
    kept = DIFF_MAX_LINES - 1
    return [*lines[:kept], f"... {len(lines) - kept} more diff lines not shown"]


def _drift(case_id: str, message: str) -> str:
    """Compose a drift detail through the error whose text Phase 9's ``check`` will raise."""
    return str(BaselineDriftError(message, case_id=case_id, fix=UPDATE_COMMAND))


class BaselineStore:
    """The baseline files under one directory, and the one comparison that uses them.

    One file per case at ``<baseline_dir>/<suite>/<case_id>.json``, written with sorted keys, an
    indent and a trailing newline, so re-recording identical content produces identical bytes and
    a baseline that did not move produces no diff in the user's repository.
    """

    def __init__(
        self,
        baseline_dir: Path | None = None,
        *,
        clock: Clock = utc_now,
    ) -> None:
        """Open a store over a directory.

        Args:
            baseline_dir: Where baselines live. Defaults to :func:`default_baseline_dir`;
                Phase 9's plugin passes a rootdir-based path or ``--baseline-dir``.
            clock: A callable returning the instant written into a baseline's ``recorded``
                field. Defaults to the current UTC time; tests inject a fixed one, so nothing
                in this repository's suite depends on the wall clock.
        """
        self.baseline_dir = baseline_dir if baseline_dir is not None else default_baseline_dir()
        self.clock = clock

    def path_for(self, suite: str, case_id: str) -> Path:
        """Return the file one case's baseline lives in.

        Args:
            suite: The suite name, which is the test module's stem (spec §3.6).
            case_id: The case's id.

        Returns:
            ``<baseline_dir>/<suite>/<case_id>.json``.

        Raises:
            ProbatioConfigError: Either name would escape the baseline directory.
        """
        check_path_segment(suite, label="suite")
        check_path_segment(case_id, label="case id")
        return self.baseline_dir / suite / f"{case_id}.json"

    def load(self, suite: str, case_id: str) -> Baseline | None:
        """Read one case's baseline.

        Args:
            suite: The suite name.
            case_id: The case's id.

        Returns:
            The baseline, or ``None`` when there is no file yet.

        Raises:
            ProbatioConfigError: The file exists but cannot be read or does not parse. A
                corrupted baseline is a broken artefact, not drift, and re-recording over it
                silently would hide whatever it used to say (DECISIONS 33).
        """
        path = self.path_for(suite, case_id)
        if not path.exists():
            return None
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ProbatioConfigError(
                f"the baseline at {path} cannot be read: {exc}",
                case_id=case_id,
                fix=UPDATE_COMMAND,
            ) from exc
        try:
            return Baseline.model_validate_json(text)
        except ValidationError as exc:
            raise ProbatioConfigError(
                f"the baseline at {path} is not a readable baseline file: {exc.errors()[0]['msg']}",
                case_id=case_id,
                fix=UPDATE_COMMAND,
            ) from exc

    def write(self, suite: str, baseline: Baseline) -> Path:
        """Write one baseline, creating its directory if needed.

        Args:
            suite: The suite the case belongs to.
            baseline: The baseline to persist.

        Returns:
            The path written.
        """
        return write_json(self.path_for(suite, baseline.case_id), baseline.model_dump(mode="json"))

    def compare(
        self,
        *,
        suite: str,
        case: LLMCase,
        prompt_hash: str,
        results: Sequence[AssertionResult],
        output: str,
        model: str,
        update: bool = False,
    ) -> SnapshotResult | None:
        """Compare one run of a case against its baseline, recording one if there is none.

        Args:
            suite: The suite name, which is the test module's stem.
            case: The case that ran. Its ``snapshot`` setting chooses the comparison.
            prompt_hash: The identity of the prompt that produced ``output``; see
                :func:`prompt_hash`, which is what every caller should compute it with.
            results: The assertion results from this run, in declaration order.
            output: The application's output text.
            model: The model that produced it.
            update: Overwrite the baseline instead of comparing, for ``--update-baseline``.

        Returns:
            A :class:`SnapshotResult`, or ``None`` when the case's ``snapshot`` is ``off``, in
            which case no file is read and none is written (DECISIONS 31). Drift comes back as a
            result with ``passed`` false; nothing here raises because a case has moved.

        Raises:
            ProbatioConfigError: A name would escape the baseline directory, or an existing
                baseline file is unreadable. Neither happens because a case drifted.
        """
        if case.snapshot == "off":
            return None
        mode: SnapshotMode = case.snapshot
        recorded = Baseline(
            case_id=case.id,
            prompt_hash=prompt_hash,
            mode=mode,
            output=output if mode == "output" else None,
            assertions=[
                BaselineAssertion(
                    assertion_type=result.assertion_type,
                    passed=result.passed,
                    score=_round(result.score),
                )
                for result in results
            ],
            recorded=timestamp(self.clock),
            model=model,
        )
        if update:
            path = self.write(suite, recorded)
            return _result(case.id, mode, "updated", path, f"baseline updated at {path}")
        existing = self.load(suite, case.id)
        if existing is None:
            path = self.write(suite, recorded)
            return _result(case.id, mode, "recorded", path, f"baseline recorded at {path}")
        path = self.path_for(suite, case.id)
        if existing.prompt_hash != prompt_hash:
            return _result(
                case.id,
                mode,
                "prompt_changed",
                path,
                _drift(case.id, "prompt changed since baseline"),
            )
        if existing.mode != mode:
            return _result(
                case.id,
                mode,
                _CHANGED[mode],
                path,
                _drift(
                    case.id,
                    f"the baseline records snapshot mode {existing.mode!r} but the case now "
                    f"declares {mode!r}; re-record",
                ),
            )
        if mode == "output":
            return _compare_output(case.id, path, existing.output or "", output)
        return _compare_scores(case.id, path, existing.assertions, recorded.assertions)


def _result(
    case_id: str, mode: SnapshotMode, state: SnapshotState, path: Path, detail: str
) -> SnapshotResult:
    """Build a result, deriving ``passed`` from the state so the two cannot disagree."""
    return SnapshotResult(
        case_id=case_id,
        mode=mode,
        state=state,
        passed=state in _PASSING_STATES,
        detail=detail,
        path=path,
    )


def _compare_scores(
    case_id: str,
    path: Path,
    before: Sequence[BaselineAssertion],
    after: Sequence[BaselineAssertion],
) -> SnapshotResult:
    """Compare two runs' verdicts and scores, assertion by assertion."""
    aligned = len(before) == len(after) and all(
        old.assertion_type == new.assertion_type for old, new in zip(before, after, strict=True)
    )
    if not aligned:
        # An edited case is drift in the case's own mode, never `prompt_changed` (DECISIONS 30).
        shape = _shape_rows(before, after)
        detail = _drift(
            case_id,
            f"the case declares {len(after)} assertion(s) and the baseline records "
            f"{len(before)}, or their types no longer line up, so their scores cannot be "
            "compared",
        )
        return _result(case_id, "scores", "scores_changed", path, "\n".join([detail, *shape]))
    rows: list[tuple[str, str, str, str]] = []
    changed = False
    for old, new in zip(before, after, strict=True):
        reasons = []
        if old.passed != new.passed:
            reasons.append("verdict")
        if _score_changed(old.score, new.score):
            reasons.append("score")
        changed = changed or bool(reasons)
        rows.append(
            (
                new.assertion_type,
                _cell(old.passed, old.score),
                _cell(new.passed, new.score),
                ", ".join(reasons),
            )
        )
    if not changed:
        return _result(case_id, "scores", "unchanged", path, "baseline unchanged")
    detail = _drift(case_id, "scores changed since baseline")
    return _result(case_id, "scores", "scores_changed", path, "\n".join([detail, *_table(rows)]))


def _shape_rows(
    before: Sequence[BaselineAssertion], after: Sequence[BaselineAssertion]
) -> list[str]:
    """Lay a baseline's assertions beside the case's when the two lists no longer line up."""
    rows: list[tuple[str, str, str, str]] = []
    for index in range(max(len(before), len(after))):
        old = before[index] if index < len(before) else None
        new = after[index] if index < len(after) else None
        rows.append(
            (
                new.assertion_type if new is not None else old.assertion_type if old else "",
                _cell(old.passed, old.score) if old is not None else "absent",
                _cell(new.passed, new.score) if new is not None else "absent",
                "" if old is not None and new is not None else "assertion list",
            )
        )
    return _table(rows)


def _compare_output(case_id: str, path: Path, recorded: str, current: str) -> SnapshotResult:
    """Compare two runs' output text, reporting a capped unified diff when it moved."""
    if recorded == current:
        return _result(case_id, "output", "unchanged", path, "baseline unchanged")
    detail = _drift(case_id, "output changed since baseline")
    return _result(
        case_id,
        "output",
        "output_changed",
        path,
        "\n".join([detail, *_diff_lines(recorded, current)]),
    )
