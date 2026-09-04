"""Phase 4: rubric resolution over an ordered list of directories (DECISIONS 23)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from probatio import ProbatioConfigError
from probatio.judge import Rubric, default_rubric_dirs, resolve_rubric

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_RUBRICS = REPO_ROOT / "examples" / "demo_suite" / "rubrics"


def write(directory: Path, name: str, text: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_a_name_resolves_to_rubrics_name_md_in_the_first_directory_that_has_it(
    tmp_path: Path,
) -> None:
    first = tmp_path / "one"
    second = tmp_path / "two"
    write(first, "faithfulness", "from one")
    write(second, "faithfulness", "from two")
    rubric = resolve_rubric("faithfulness", rubric_dirs=[first, second])
    assert rubric.name == "faithfulness"
    assert rubric.text == "from one"
    assert rubric.path == first / "faithfulness.md"


def test_the_search_continues_into_later_directories() -> None:
    """The demo suite keeps its rubric beside its tests, below rootdir; that is the whole point."""
    rubric = resolve_rubric("faithfulness", rubric_dirs=[REPO_ROOT / "rubrics", DEMO_RUBRICS])
    assert rubric.path == DEMO_RUBRICS / "faithfulness.md"
    assert "Grade whether the answer is supported by the documents" in rubric.text


def test_a_name_written_with_its_suffix_is_not_doubled(tmp_path: Path) -> None:
    write(tmp_path, "safety", "text")
    assert resolve_rubric("safety.md", rubric_dirs=[tmp_path]).name == "safety"


def test_an_absolute_path_ignores_the_directory_list(tmp_path: Path) -> None:
    path = write(tmp_path / "elsewhere", "custom", "absolute text")
    rubric = resolve_rubric(str(path), rubric_dirs=[tmp_path])
    assert rubric.text == "absolute text"
    assert rubric.name == "custom"


def test_an_absolute_path_to_nothing_names_the_path() -> None:
    with pytest.raises(ProbatioConfigError) as excinfo:
        resolve_rubric("/nowhere/at/all/faithfulness.md")
    assert "absolute path" in str(excinfo.value)


def test_a_name_that_resolves_nowhere_names_every_directory_searched(tmp_path: Path) -> None:
    first = tmp_path / "one"
    second = tmp_path / "two"
    with pytest.raises(ProbatioConfigError) as excinfo:
        resolve_rubric("faithfulness", rubric_dirs=[first, second])
    message = str(excinfo.value)
    assert str(first) in message
    assert str(second) in message
    assert "faithfulness.md" in message


def test_an_empty_directory_list_still_produces_a_readable_message() -> None:
    with pytest.raises(ProbatioConfigError) as excinfo:
        resolve_rubric("faithfulness", rubric_dirs=[])
    assert "no directories" in str(excinfo.value)


def test_the_default_directory_is_rubrics_under_the_working_directory(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.chdir(tmp_path)
    assert default_rubric_dirs() == [tmp_path / "rubrics"]
    write(tmp_path / "rubrics", "faithfulness", "default text")
    assert resolve_rubric("faithfulness").text == "default text"


def test_a_file_that_is_not_utf_8_text_is_a_config_error_naming_the_file(tmp_path: Path) -> None:
    path = tmp_path / "rubrics" / "binary.md"
    path.parent.mkdir()
    path.write_bytes(b"\xff\xfe not text")
    with pytest.raises(ProbatioConfigError) as excinfo:
        resolve_rubric("binary", rubric_dirs=[tmp_path / "rubrics"])
    assert "cannot read rubric" in str(excinfo.value)
    assert "binary.md" in str(excinfo.value)


def test_the_content_hash_follows_the_text_and_not_the_file_name() -> None:
    one = Rubric("faithfulness", Path("a.md"), "same text")
    two = Rubric("other", Path("b.md"), "same text")
    three = Rubric("faithfulness", Path("a.md"), "edited text")
    assert one.content_hash == two.content_hash
    assert one.content_hash != three.content_hash


def test_the_repr_names_the_rubric_and_its_file() -> None:
    assert repr(Rubric("faithfulness", Path("r/faithfulness.md"), "t")) == (
        "Rubric(name='faithfulness', path='r/faithfulness.md')"
    )
