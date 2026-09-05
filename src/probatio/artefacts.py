"""What every file Probatio writes has in common: a clock, a name check and the writers.

Four kinds of file are persisted — baselines (§3.6), judge validation records (§3.5), cassettes
(§3.8) and frozen variants (§3.9) — and by the third of them the same three lines had been
written three times. They live here instead. Three of the four are JSON; frozen variants are YAML,
because a human reads and edits paraphrases, so :func:`write_yaml` sits beside
:func:`write_json` with the same guarantee.

**The clock is a value, not a call.** Every persisted file carries a ``recorded`` or ``created``
stamp, and none of them is ever compared: identity is a :func:`~probatio.hashing.stable_hash`
(spec §0), and the stamp is there so a reviewer can see how old an artefact is. That makes the
wall clock a pure nuisance in a test suite that must produce byte-identical files twice in a row,
so every store takes a :data:`Clock` argument and no test in this repository reads the real one.

**A derived name is checked before it becomes a path segment.** A suite name is a test module's
stem and a case id comes out of a YAML file; neither is a path the user typed on the command line,
and `CLAUDE.md` allows Probatio to write only inside paths the user did type. Five lines that make
the derived half unable to escape are cheaper than a rule that holds only by luck (DECISIONS 34).

**Every file is written the same way**: a fixed key order, a fixed indent, one trailing newline.
These files are committed to the user's repository, so re-recording something that did not change
has to produce no diff. JSON sorts its keys; YAML keeps the caller's order, which is fixed in the
caller's code and so is just as stable.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from re import compile as _compile
from typing import Any, Final

import yaml

from .errors import ProbatioConfigError

__all__ = [
    "JSON_INDENT",
    "NAME_PATTERN",
    "Clock",
    "check_path_segment",
    "display_path",
    "format_instant",
    "timestamp",
    "utc_now",
    "write_json",
    "write_yaml",
]

Clock = Callable[[], datetime]
"""What a store accepts in place of the wall clock: anything returning an instant."""

NAME_PATTERN: Final = _compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
"""``LLMCase``'s own id pattern without its length bound; nothing else may be a path segment."""

JSON_INDENT: Final = 2
"""The indent every persisted file uses, so a hand-edited file looks like a written one."""

_YAML_WIDTH: Final = 10_000
"""Wide enough that a paraphrase is never wrapped, so a variant is one greppable line."""


def utc_now() -> datetime:
    """Return the current instant in UTC.

    Returns:
        The default clock of every store. Tests inject a fixed callable instead.
    """
    return datetime.now(UTC)


def format_instant(moment: datetime) -> str:
    """Render an instant as an ISO 8601 string in UTC, to whole seconds.

    Args:
        moment: The instant. A naive value is read as UTC rather than as local time, because a
            store's clock is documented to speak UTC and guessing a zone would put a different
            string in the file on a different machine.

    Returns:
        A string such as ``2026-09-04T18:00:00Z``.
    """
    aware = moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment
    return aware.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def timestamp(clock: Clock = utc_now) -> str:
    """Return the stamp a persisted file records, from a clock.

    Args:
        clock: The clock to read. Defaults to :func:`utc_now`.

    Returns:
        :func:`format_instant` of whatever the clock reported.
    """
    return format_instant(clock())


def check_path_segment(name: str, *, label: str) -> str:
    """Check that a derived name may be used as one path segment, and return it.

    Args:
        name: The candidate segment, such as a suite name or a case id.
        label: What the name is, named in the error message so the caller knows which of its
            arguments was wrong rather than being handed a path comparison.

    Returns:
        ``name`` unchanged, so a caller can write ``store_dir / check_path_segment(...)``.

    Raises:
        ProbatioConfigError: The name is empty, starts with a punctuation character, or holds
            anything but letters, digits, ``.``, ``_`` and ``-`` — a separator or a ``..`` among
            them.
    """
    if not NAME_PATTERN.match(name):
        raise ProbatioConfigError(
            f"{name!r} is not usable as a {label}: a path segment must start with a letter or a "
            "digit and hold only letters, digits, '.', '_' and '-'"
        )
    return name


def write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    """Write one persisted artefact, creating its directory if needed.

    Args:
        path: Where to write. Its parent directories are created.
        payload: JSON-serialisable data, usually a pydantic model's
            ``model_dump(mode="json")``.

    Returns:
        The path written, so a caller can report it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), indent=JSON_INDENT, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def write_yaml(
    path: Path, payload: Mapping[str, Any], *, header: Sequence[str] | None = None
) -> Path:
    """Write one persisted YAML artefact, creating its directory if needed.

    Keys are written in the order the mapping gives them rather than sorted, because this is the
    one file kind a person reads top to bottom: a frozen variants file starts with the case it
    belongs to and ends with the variants themselves. That order is a property of the caller's
    dict, so two writes of the same payload are still byte-identical.

    Args:
        path: Where to write. Its parent directories are created.
        payload: JSON-compatible data.
        header: Comment lines written above the document, without their ``#``.

    Returns:
        The path written, so a caller can report it.
    """
    body = yaml.safe_dump(
        dict(payload),
        sort_keys=False,
        allow_unicode=False,
        default_flow_style=False,
        width=_YAML_WIDTH,
    )
    comment = "".join(f"# {line}\n" for line in header or ())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(comment + body, encoding="utf-8")
    return path


def display_path(path: Path, root: Path | None = None) -> str:
    """Render a path for a report, relative to the run's root and with POSIX separators.

    Everything a reporter persists is committed by somebody: the results JSON goes into a
    repository, a job summary goes onto a pull request. An absolute path in one of those is a
    fact about the machine that produced it and not about the run — it names a home directory,
    it differs between a developer's laptop and CI, and it makes two otherwise identical runs
    produce different bytes. So a path that lies under ``root`` is written relative to it, and
    always with forward slashes, so a Windows run and a POSIX run of the same suite agree.

    A path outside ``root`` is returned as it is, absolute. Rendering it as a chain of ``..``
    segments would be portable-looking without being portable — it only resolves from a root the
    reader has to guess — and the honest reading of a baseline directory somewhere else on the
    disk is that it is somewhere else on the disk.

    Args:
        path: The path to render.
        root: The directory to render it relative to. Defaults to the current directory, which
            is what :func:`default_baseline_dir` and :func:`default_cassette_dir` also assume.

    Returns:
        The rendered path.
    """
    base = Path.cwd() if root is None else root
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()
