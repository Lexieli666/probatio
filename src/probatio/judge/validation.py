"""Validation records: the file that decides whether a judge is allowed to be called validated.

Spec §9 rejects the word "validated" for a judge with no record on disk, and this module is what
makes that enforceable rather than aspirational. ``probatio validate-judge`` writes
``<validation_dir>/<rubric>.validation.json``; every graded judge assertion reads it back and,
finding nothing — or finding a record whose ``rubric_hash`` no longer matches the rubric text —
marks itself unenforceable and prints the command that would fix it.

Pinning the rubric's content hash rather than its modification time is the whole mechanism: a
rubric edited after validation is a different judge, measured against nothing, and it says so on
the next run without anyone having to remember to re-validate.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from ..hashing import stable_hash
from .rubric import Rubric

__all__ = [
    "RECORD_SUFFIX",
    "ValidationRecord",
    "default_validation_dir",
    "hash_labels_file",
    "load_validation_record",
    "rubric_is_validated",
    "utc_now",
    "validation_record_path",
    "write_validation_record",
]

RECORD_SUFFIX: Final = ".validation.json"
"""A record is named after its rubric, so one rubric has exactly one record."""


class ValidationRecord(BaseModel):
    """What one run of ``probatio validate-judge`` measured, as committed to the repository.

    Attributes:
        rubric: The rubric name; also the record's file name.
        rubric_hash: The stable hash of the rubric text this measurement applies to.
        n: How many labelled items were compared.
        agreement: The fraction of items on which judge and human agreed.
        kappa: Cohen's kappa for the same comparison.
        labels_file: The labels file as given on the command line.
        labels_hash: The stable hash of that file's contents.
        method: ``"columns"`` when two existing columns were compared, ``"run-judge"`` when the
            judge was run over each row.
        judge_model: The model that produced the verdicts, when this run produced them;
            ``None`` in ``columns`` mode, where the judge column came from somewhere else.
        created: When the record was written, as an ISO 8601 instant in UTC.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    rubric: str
    rubric_hash: str
    n: int
    agreement: float
    kappa: float
    labels_file: str
    labels_hash: str
    method: Literal["columns", "run-judge"]
    judge_model: str | None = None
    created: str


def default_validation_dir() -> Path:
    """Return the directory validation records are read from and written to by default.

    Returns:
        ``Path.cwd() / ".probatio" / "judges"``, which is spec §5's location relative to rootdir.
    """
    return Path.cwd() / ".probatio" / "judges"


def validation_record_path(rubric_name: str, *, validation_dir: Path | None = None) -> Path:
    """Return the path of one rubric's validation record.

    Args:
        rubric_name: The rubric's name, not a path.
        validation_dir: Where records live. Defaults to :func:`default_validation_dir`.

    Returns:
        ``<validation_dir>/<rubric_name>.validation.json``.
    """
    directory = validation_dir if validation_dir is not None else default_validation_dir()
    return directory / f"{rubric_name}{RECORD_SUFFIX}"


def utc_now() -> str:
    """Return the current instant as an ISO 8601 string in UTC, to whole seconds.

    Returns:
        A string such as ``2026-09-03T18:00:00Z``. Nothing Probatio compares reads this field;
        it is there so a reviewer can see how old a measurement is.
    """
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def hash_labels_file(path: Path) -> str:
    """Return the stable hash of a labels file's contents.

    Args:
        path: The CSV of human labels.

    Returns:
        The :func:`~probatio.hashing.stable_hash` of the file's text, so a record says which
        labels it was measured against and not merely which filename.

    Raises:
        OSError: The file cannot be read.
    """
    return stable_hash(path.read_text(encoding="utf-8"))


def write_validation_record(
    record: ValidationRecord, *, validation_dir: Path | None = None
) -> Path:
    """Write one validation record, creating its directory if needed.

    Args:
        record: The measurement to persist.
        validation_dir: Where records live. Defaults to :func:`default_validation_dir`.

    Returns:
        The path written.
    """
    path = validation_record_path(record.rubric, validation_dir=validation_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def load_validation_record(
    rubric_name: str, *, validation_dir: Path | None = None
) -> ValidationRecord | None:
    """Read one rubric's validation record, if there is a readable one.

    A missing, unreadable, malformed or out-of-date record all mean the same thing to a caller:
    this judge is not validated. So none of them raise; they return ``None`` and the assertion
    layer prints the command that writes a record.

    Args:
        rubric_name: The rubric's name.
        validation_dir: Where records live. Defaults to :func:`default_validation_dir`.

    Returns:
        The record, or ``None`` when there is none that parses.
    """
    path = validation_record_path(rubric_name, validation_dir=validation_dir)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return ValidationRecord.model_validate_json(text)
    except ValidationError:
        return None


def rubric_is_validated(rubric: Rubric, *, validation_dir: Path | None = None) -> bool:
    """Report whether a rubric has a validation record for its current text.

    Args:
        rubric: The resolved rubric.
        validation_dir: Where records live. Defaults to :func:`default_validation_dir`.

    Returns:
        ``True`` only when a record exists and its ``rubric_hash`` equals the rubric's current
        content hash. Editing the rubric therefore makes its judge unvalidated again.
    """
    record = load_validation_record(rubric.name, validation_dir=validation_dir)
    return record is not None and record.rubric_hash == rubric.content_hash
