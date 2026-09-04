"""Phase 8: the frozen variants file — its model, its loader and its three refusals."""

from __future__ import annotations

from pathlib import Path

import pytest

from probatio import LLMCase, MissingVariantsError, ProbatioConfigError
from probatio.metamorphic import (
    VariantProvenance,
    VariantsFile,
    freeze_command,
    load_variants_file,
    read_frozen_variants,
    variants_path,
)

CASE = LLMCase.model_validate(
    {
        "id": "htn-definition",
        "input": {"question": "What is high blood pressure?"},
        "assertions": [{"type": "contains", "any": ["anything"]}],
    }
)

HAND_WRITTEN = """\
case_id: htn-definition
field: input.question
generated_by: {provider: human, model: null, created: "2026-09-03", prompt_hash: null}
variants:
  - "one"
  - "two"
  - "three"
"""


def write(tmp_path: Path, text: str, name: str = "htn-definition.yaml") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_the_path_is_one_file_per_case_id() -> None:
    assert variants_path("htn-definition", Path("v")) == Path("v/htn-definition.yaml")


def test_a_hand_written_file_carries_null_model_and_null_prompt_hash(tmp_path: Path) -> None:
    contents = load_variants_file(write(tmp_path, HAND_WRITTEN))
    assert contents.case_id == "htn-definition"
    assert contents.field == "input.question"
    assert contents.generated_by == VariantProvenance(
        provider="human", model=None, created="2026-09-03", prompt_hash=None
    )
    assert contents.variants == ["one", "two", "three"]


def test_the_models_are_frozen_and_reject_unknown_keys() -> None:
    with pytest.raises(ValueError, match="extra"):
        VariantProvenance(provider="human", created="x", author="nobody")  # type: ignore[call-arg]
    file = VariantsFile(
        case_id="c1",
        field="input.question",
        generated_by=VariantProvenance(provider="human", created="x"),
        variants=["one"],
    )
    with pytest.raises(ValueError, match="frozen"):
        file.case_id = "c2"  # type: ignore[misc]


def test_a_file_whose_variants_were_all_deleted_still_parses(tmp_path: Path) -> None:
    """The model tolerates it; :func:`read_frozen_variants` is what refuses to measure over it."""
    text = HAND_WRITTEN.replace('  - "one"\n  - "two"\n  - "three"\n', "  []\n")
    assert load_variants_file(write(tmp_path, text)).variants == []


def test_a_misspelled_key_is_refused_rather_than_ignored(tmp_path: Path) -> None:
    text = HAND_WRITTEN.replace("variants:", "varients:")
    with pytest.raises(ProbatioConfigError, match="varients|variants"):
        load_variants_file(write(tmp_path, text))


def test_an_unreadable_file_names_itself(tmp_path: Path) -> None:
    with pytest.raises(ProbatioConfigError, match="cannot read frozen variants"):
        load_variants_file(tmp_path / "missing.yaml")


def test_invalid_yaml_names_the_file(tmp_path: Path) -> None:
    with pytest.raises(ProbatioConfigError, match="invalid YAML"):
        load_variants_file(write(tmp_path, "case_id: [unclosed\n"))


def test_a_file_that_is_not_a_mapping_says_what_a_variants_file_is(tmp_path: Path) -> None:
    with pytest.raises(ProbatioConfigError, match="mapping with 'case_id'"):
        load_variants_file(write(tmp_path, "- one\n- two\n"))


# -- read_frozen_variants: the three refusals -----------------------------------------------------


def test_reading_takes_the_first_k(tmp_path: Path) -> None:
    write(tmp_path, HAND_WRITTEN)
    assert read_frozen_variants(CASE, field="input.question", k=2, variants_dir=tmp_path) == [
        "one",
        "two",
    ]


def test_a_missing_file_raises_and_carries_the_freeze_command(tmp_path: Path) -> None:
    with pytest.raises(MissingVariantsError) as excinfo:
        read_frozen_variants(CASE, field="input.question", k=3, variants_dir=tmp_path)
    message = str(excinfo.value)
    assert "never generated during a test run" in message
    assert f"probatio freeze-variants --cases {tmp_path.parent / 'cases'}" in message
    assert "--field input.question --provider claude-cli" in message
    assert f"--out {tmp_path}" in message


def test_a_file_naming_another_case_is_refused(tmp_path: Path) -> None:
    write(tmp_path, HAND_WRITTEN.replace("htn-definition", "t2d-metformin"))
    with pytest.raises(ProbatioConfigError, match="holds variants for 't2d-metformin'"):
        read_frozen_variants(CASE, field="input.question", k=3, variants_dir=tmp_path)


def test_a_file_naming_another_field_is_refused(tmp_path: Path) -> None:
    write(tmp_path, HAND_WRITTEN.replace("field: input.question", "field: input.documents"))
    with pytest.raises(ProbatioConfigError, match="varies 'input.question'") as excinfo:
        read_frozen_variants(CASE, field="input.question", k=3, variants_dir=tmp_path)
    assert "freeze-variants" in str(excinfo.value)


def test_a_file_with_fewer_variants_than_k_is_read_as_it_stands(tmp_path: Path) -> None:
    """DECISIONS 52: deleting a paraphrase that changed the meaning is the reviewer's job."""
    write(tmp_path, HAND_WRITTEN.replace('  - "three"\n', ""))
    assert read_frozen_variants(CASE, field="input.question", k=3, variants_dir=tmp_path) == [
        "one",
        "two",
    ]


def test_a_file_whose_variants_were_all_deleted_is_a_missing_variants_error(
    tmp_path: Path,
) -> None:
    write(tmp_path, HAND_WRITTEN.replace('  - "one"\n  - "two"\n  - "three"\n', "  []\n"))
    with pytest.raises(MissingVariantsError) as excinfo:
        read_frozen_variants(CASE, field="input.question", k=3, variants_dir=tmp_path)
    message = str(excinfo.value)
    assert "exists but holds no variants" in message
    assert "freeze-variants" in message
    assert message.endswith("--force")


def test_the_freeze_command_guesses_the_sibling_cases_directory() -> None:
    command = freeze_command(field="input.question", k=3, variants_dir=Path("suite/variants"))
    assert command == (
        "probatio freeze-variants --cases suite/cases --field input.question "
        "--provider claude-cli --k 3 --out suite/variants"
    )


def test_the_freeze_command_adds_force_when_the_file_is_already_there() -> None:
    command = freeze_command(
        field="input.question", k=3, variants_dir=Path("suite/variants"), force=True
    )
    assert command.endswith("--out suite/variants --force")
