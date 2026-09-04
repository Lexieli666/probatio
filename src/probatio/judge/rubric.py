"""Rubric resolution: an absolute path, or a name looked up in an ordered list of directories.

Spec §3.5 says a rubric is ``rubrics/<name>.md`` under rootdir or an absolute path. That rule
alone cannot load the demo suite's rubric, which lives beside its tests in
``examples/demo_suite/rubrics/`` while rootdir is the repository root, so resolution takes an
ordered list of directories instead of one. Phase 9's plugin passes rootdir first and the
requesting test module's directory second, which keeps spec §0's "paths are relative to rootdir"
as the default and lets a self-contained suite carry its own rubrics (DECISIONS 23).

A rubric that resolves nowhere is not an exception: it is a mistake in the case, and DECISIONS 22
makes those failed :class:`~probatio.assertions.AssertionResult` s so that one run reports all of
them. The error raised here carries the list of directories searched, and the assertion layer puts
that list in the detail.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Final

from ..errors import ProbatioConfigError
from ..hashing import stable_hash

__all__ = ["RUBRIC_SUFFIX", "Rubric", "default_rubric_dirs", "resolve_rubric"]

RUBRIC_SUFFIX: Final = ".md"
"""Rubrics are markdown, so a bare name resolves to ``<dir>/<name>.md``."""


class Rubric:
    """One resolved rubric: its name, the file it came from, and its text.

    Attributes:
        name: The rubric name, which names its validation record on disk.
        path: The file the text was read from.
        text: The rubric markdown, verbatim.
    """

    def __init__(self, name: str, path: Path, text: str) -> None:
        """Store a resolved rubric.

        Args:
            name: The rubric name; for a path, its stem.
            path: The file the text came from.
            text: The rubric markdown, verbatim.
        """
        self.name = name
        self.path = path
        self.text = text

    @property
    def content_hash(self) -> str:
        """The stable hash of the rubric text, which is what a validation record pins."""
        return stable_hash(self.text)

    def __repr__(self) -> str:
        """Show the name and the path, which is what a failure message needs."""
        return f"Rubric(name={self.name!r}, path={str(self.path)!r})"


def default_rubric_dirs() -> list[Path]:
    """Return the directory list used when a caller names none.

    Returns:
        ``[Path.cwd() / "rubrics"]``. Under a plain invocation the working directory is pytest's
        rootdir, which is the origin spec §0 gives every other path.
    """
    return [Path.cwd() / "rubrics"]


def _candidates(rubric: str, rubric_dirs: Sequence[Path]) -> list[Path]:
    """List the files a rubric name could resolve to, in search order."""
    stem = rubric[: -len(RUBRIC_SUFFIX)] if rubric.endswith(RUBRIC_SUFFIX) else rubric
    return [Path(directory) / f"{stem}{RUBRIC_SUFFIX}" for directory in rubric_dirs]


def resolve_rubric(rubric: str, *, rubric_dirs: Sequence[Path] | None = None) -> Rubric:
    """Resolve a rubric given as an absolute path or as a name, and read it.

    Args:
        rubric: An absolute path to a markdown file, or a rubric name. A name resolves to
            ``<directory>/<name>.md`` in the first of ``rubric_dirs`` that has the file; a
            trailing ``.md`` on the name is not doubled.
        rubric_dirs: The directories to search, in order. Defaults to
            :func:`default_rubric_dirs`.

    Returns:
        The resolved :class:`Rubric`.

    Raises:
        ProbatioConfigError: The path does not exist, no directory holds the name, or the file
            cannot be read as UTF-8 text.
    """
    directories = list(rubric_dirs) if rubric_dirs is not None else default_rubric_dirs()
    path = Path(rubric)
    if path.is_absolute():
        if not path.is_file():
            raise ProbatioConfigError(
                f"rubric {rubric!r} is an absolute path but there is no file there"
            )
        return Rubric(path.stem, path, _read(path))
    for candidate in _candidates(rubric, directories):
        if candidate.is_file():
            return Rubric(candidate.stem, candidate, _read(candidate))
    searched = ", ".join(str(directory) for directory in directories) or "no directories"
    raise ProbatioConfigError(
        f"rubric {rubric!r} was not found; searched {searched} for "
        f"{Path(rubric).name}{'' if rubric.endswith(RUBRIC_SUFFIX) else RUBRIC_SUFFIX}"
    )


def _read(path: Path) -> str:
    """Read a rubric file, naming it on failure.

    Raises:
        ProbatioConfigError: The file cannot be read as UTF-8 text.
    """
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ProbatioConfigError(f"cannot read rubric {str(path)!r}: {exc}") from exc
