"""Phase 4: validation records — what "validated" is allowed to mean (spec §3.5, §9)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from probatio.judge import (
    ValidationRecord,
    default_validation_dir,
    hash_labels_file,
    load_validation_record,
    resolve_rubric,
    rubric_is_validated,
    utc_now,
    validation_record_path,
    write_validation_record,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_RUBRICS = REPO_ROOT / "examples" / "demo_suite" / "rubrics"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "consilium"


def record(**overrides: Any) -> ValidationRecord:
    fields: dict[str, Any] = {
        "rubric": "faithfulness",
        "rubric_hash": "0123456789abcdef",
        "n": 40,
        "agreement": 0.8,
        "kappa": 0.592,
        "labels_file": "tests/fixtures/consilium/judge-sample-2-labeled.csv",
        "labels_hash": "fedcba9876543210",
        "method": "columns",
        "judge_model": None,
        "created": "2026-09-03T18:00:00Z",
    }
    fields.update(overrides)
    return ValidationRecord.model_validate(fields)


def test_a_record_is_named_after_its_rubric(tmp_path: Path) -> None:
    assert validation_record_path("faithfulness", validation_dir=tmp_path) == (
        tmp_path / "faithfulness.validation.json"
    )


def test_the_default_directory_is_probatio_judges_under_the_working_directory(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.chdir(tmp_path)
    assert default_validation_dir() == tmp_path / ".probatio" / "judges"
    assert validation_record_path("faithfulness") == (
        tmp_path / ".probatio" / "judges" / "faithfulness.validation.json"
    )


def test_a_record_round_trips_through_disk_with_the_fields_spec_3_5_names(tmp_path: Path) -> None:
    written = write_validation_record(record(), validation_dir=tmp_path / "judges")
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert set(payload) == {
        "rubric",
        "rubric_hash",
        "n",
        "agreement",
        "kappa",
        "labels_file",
        "labels_hash",
        "method",
        "judge_model",
        "created",
    }
    assert load_validation_record("faithfulness", validation_dir=tmp_path / "judges") == record()


def test_writing_a_record_creates_its_directory(tmp_path: Path) -> None:
    written = write_validation_record(record(), validation_dir=tmp_path / "a" / "b")
    assert written.is_file()


def test_a_rubric_with_a_record_for_its_current_text_is_validated(tmp_path: Path) -> None:
    rubric = resolve_rubric("faithfulness", rubric_dirs=[DEMO_RUBRICS])
    assert not rubric_is_validated(rubric, validation_dir=tmp_path)
    write_validation_record(record(rubric_hash=rubric.content_hash), validation_dir=tmp_path)
    assert rubric_is_validated(rubric, validation_dir=tmp_path)


def test_editing_the_rubric_invalidates_its_record(tmp_path: Path) -> None:
    rubrics = tmp_path / "rubrics"
    rubrics.mkdir()
    path = rubrics / "faithfulness.md"
    path.write_text("Grade faithfulness.", encoding="utf-8")
    rubric = resolve_rubric("faithfulness", rubric_dirs=[rubrics])
    write_validation_record(record(rubric_hash=rubric.content_hash), validation_dir=tmp_path)
    assert rubric_is_validated(rubric, validation_dir=tmp_path)

    path.write_text("Grade faithfulness, and also tone.", encoding="utf-8")
    edited = resolve_rubric("faithfulness", rubric_dirs=[rubrics])
    assert not rubric_is_validated(edited, validation_dir=tmp_path)


def test_a_missing_record_is_not_an_error(tmp_path: Path) -> None:
    assert load_validation_record("nothing-here", validation_dir=tmp_path) is None


def test_a_malformed_record_reads_as_no_record_rather_than_raising(tmp_path: Path) -> None:
    (tmp_path / "faithfulness.validation.json").write_text("{not json", encoding="utf-8")
    assert load_validation_record("faithfulness", validation_dir=tmp_path) is None


def test_a_record_missing_a_field_reads_as_no_record(tmp_path: Path) -> None:
    (tmp_path / "faithfulness.validation.json").write_text(
        '{"rubric": "faithfulness"}', encoding="utf-8"
    )
    assert load_validation_record("faithfulness", validation_dir=tmp_path) is None


def test_the_labels_hash_follows_the_contents_of_the_labels_file(tmp_path: Path) -> None:
    one = tmp_path / "one.csv"
    two = tmp_path / "two.csv"
    one.write_text("a,b\n1,2\n", encoding="utf-8")
    two.write_text("a,b\n1,2\n", encoding="utf-8")
    assert hash_labels_file(one) == hash_labels_file(two)
    two.write_text("a,b\n1,3\n", encoding="utf-8")
    assert hash_labels_file(one) != hash_labels_file(two)


def test_the_labels_hash_of_a_committed_sample_is_stable() -> None:
    assert hash_labels_file(FIXTURES / "judge-sample-2-labeled.csv") == "54c3af834595d71c"


def test_the_created_stamp_is_an_iso_8601_instant_in_utc() -> None:
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", utc_now())
