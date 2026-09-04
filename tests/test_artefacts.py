"""Phase 7: the three lines every persisted artefact shares (`artefacts.py`)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from probatio.artefacts import (
    JSON_INDENT,
    NAME_PATTERN,
    check_path_segment,
    format_instant,
    timestamp,
    utc_now,
    write_json,
)
from probatio.errors import ProbatioConfigError

FIXED = datetime(2026, 9, 4, 18, 30, 15, 123456, tzinfo=UTC)


def test_an_instant_renders_as_iso_8601_in_utc_to_whole_seconds() -> None:
    assert format_instant(FIXED) == "2026-09-04T18:30:15Z"


def test_an_instant_in_another_zone_is_converted_rather_than_relabelled() -> None:
    tokyo = FIXED.astimezone(timezone(timedelta(hours=9)))
    assert tokyo.hour != FIXED.hour
    assert format_instant(tokyo) == "2026-09-04T18:30:15Z"


def test_a_naive_instant_is_read_as_utc() -> None:
    """A store's clock is documented to speak UTC; guessing a zone would move the string."""
    assert format_instant(FIXED.replace(tzinfo=None)) == "2026-09-04T18:30:15Z"


def test_the_stamp_comes_from_whatever_clock_it_is_given() -> None:
    assert timestamp(lambda: FIXED) == "2026-09-04T18:30:15Z"


def test_the_default_clock_is_the_wall_clock_and_renders_the_same_way() -> None:
    before = utc_now()
    assert before.tzinfo is UTC
    assert format_instant(before).endswith("Z")
    assert len(timestamp()) == len("2026-09-04T18:30:15Z")


def test_a_usable_path_segment_comes_back_unchanged() -> None:
    for name in ("test_demo", "htn-definition", "a", "a.b_c-1"):
        assert check_path_segment(name, label="suite") == name
        assert NAME_PATTERN.match(name)


@pytest.mark.parametrize("name", ["", "../elsewhere", "a/b", ".hidden", "-lead", "a b", "a:b"])
def test_a_name_that_would_escape_a_directory_is_refused_by_its_label(name: str) -> None:
    with pytest.raises(ProbatioConfigError) as excinfo:
        check_path_segment(name, label="case id")
    assert "case id" in str(excinfo.value)
    assert repr(name) in str(excinfo.value)


def test_writing_an_artefact_creates_its_directory_and_ends_with_one_newline(
    tmp_path: Path,
) -> None:
    path = write_json(tmp_path / "deep" / "deeper" / "thing.json", {"b": 1, "a": [2, 3]})
    text = path.read_text(encoding="utf-8")
    assert text.endswith("}\n")
    assert not text.endswith("}\n\n")
    assert json.loads(text) == {"a": [2, 3], "b": 1}


def test_keys_are_sorted_and_indented_so_a_rerecording_makes_no_diff(tmp_path: Path) -> None:
    one = write_json(tmp_path / "one.json", {"b": 1, "a": 2})
    two = write_json(tmp_path / "two.json", {"a": 2, "b": 1})
    assert one.read_bytes() == two.read_bytes()
    assert one.read_text(encoding="utf-8").splitlines()[1].startswith(" " * JSON_INDENT)
