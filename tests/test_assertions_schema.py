"""Phase 3: the ``schema_valid`` assertion, its fence stripping and its error reporting."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from probatio.assertions import evaluate_schema_valid, strip_code_fence
from probatio.case import SchemaValidAssertion

SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["screen", "start_age"],
    "properties": {"screen": {"type": "boolean"}, "start_age": {"type": "integer"}},
    "additionalProperties": False,
}


def schema_valid(**fields: object) -> SchemaValidAssertion:
    return SchemaValidAssertion.model_validate({"type": "schema_valid", **fields})


# --- pass --------------------------------------------------------------------------------------


def test_valid_json_validates() -> None:
    result = evaluate_schema_valid(schema_valid(schema=SCHEMA), '{"screen": true, "start_age": 35}')
    assert result.assertion_type == "schema_valid"
    assert result.passed
    assert result.score == 1.0
    assert result.detail == "output validates"


def test_one_fenced_block_is_stripped_before_parsing() -> None:
    fenced = '```json\n{"screen": true, "start_age": 35}\n```'
    assert evaluate_schema_valid(schema_valid(schema=SCHEMA), fenced).passed


def test_a_fence_without_a_language_tag_and_with_surrounding_blank_lines_is_stripped() -> None:
    fenced = '\n\n```\n{"screen": false, "start_age": 40}\n```\n'
    assert evaluate_schema_valid(schema_valid(schema=SCHEMA), fenced).passed


def test_strip_code_fence_leaves_unfenced_text_and_inner_fences_alone() -> None:
    assert strip_code_fence('{"a": 1}') == '{"a": 1}'
    assert strip_code_fence("```\nouter\n```\ntrailing prose") == "```\nouter\n```\ntrailing prose"
    assert strip_code_fence("```\nprose ```inner``` prose\n```") == "prose ```inner``` prose"


# --- fail --------------------------------------------------------------------------------------


def test_a_wrong_type_fails_and_names_the_json_path() -> None:
    result = evaluate_schema_valid(
        schema_valid(schema=SCHEMA), '{"screen": "yes", "start_age": 35}'
    )
    assert not result.passed
    assert result.score == 0.0
    assert result.detail.startswith("1 validation error: $.screen:")
    assert "is not of type 'boolean'" in result.detail


def test_a_missing_required_key_is_reported_at_the_root_path() -> None:
    result = evaluate_schema_valid(schema_valid(schema=SCHEMA), '{"screen": true}')
    assert not result.passed
    assert "$: 'start_age' is a required property" in result.detail


def test_at_most_three_errors_are_listed_and_the_rest_are_counted() -> None:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {name: {"type": "integer"} for name in "abcde"},
    }
    output = json.dumps({name: "not an integer" for name in "abcde"})
    result = evaluate_schema_valid(schema_valid(schema=schema), output)
    assert result.detail.startswith("5 validation errors: $.a:")
    assert result.detail.endswith("and 2 more")
    assert result.detail.count("is not of type 'integer'") == 3


def test_errors_are_ordered_by_json_path_so_the_detail_is_reproducible() -> None:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {name: {"type": "integer"} for name in ("zebra", "apple", "mango")},
    }
    output = json.dumps({"zebra": "z", "mango": "m", "apple": "a"})
    detail = evaluate_schema_valid(schema_valid(schema=schema), output).detail
    assert detail.index("$.apple") < detail.index("$.mango") < detail.index("$.zebra")


def test_an_error_inside_an_array_reports_an_indexed_path() -> None:
    schema: dict[str, Any] = {"type": "array", "items": {"type": "integer"}}
    result = evaluate_schema_valid(schema_valid(schema=schema), '[1, "two", 3]')
    assert "$[1]:" in result.detail


# --- malformed input ---------------------------------------------------------------------------


def test_output_that_is_not_json_is_a_failed_result_not_an_exception() -> None:
    result = evaluate_schema_valid(schema_valid(schema=SCHEMA), "Adults aged 35 to 70, yes.")
    assert not result.passed
    assert result.score == 0.0
    assert result.detail.startswith("output is not JSON:")
    assert "line 1 column 1" in result.detail


def test_empty_output_is_a_failed_result() -> None:
    assert evaluate_schema_valid(schema_valid(schema=SCHEMA), "").detail.startswith(
        "output is not JSON:"
    )


def test_a_schema_that_is_not_a_valid_json_schema_is_a_failed_result() -> None:
    result = evaluate_schema_valid(schema_valid(schema={"type": "not-a-type"}), "{}")
    assert not result.passed
    assert result.detail.startswith("the schema itself is not a valid JSON Schema:")


# --- schema_file resolution (DECISIONS 19) -----------------------------------------------------


def test_a_relative_schema_file_resolves_against_base_dir(tmp_path: Path) -> None:
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "screening.json").write_text(json.dumps(SCHEMA), encoding="utf-8")
    assertion = schema_valid(schema_file="schemas/screening.json")
    result = evaluate_schema_valid(
        assertion, '{"screen": true, "start_age": 35}', base_dir=tmp_path
    )
    assert result.passed


def test_a_schema_file_may_be_yaml(tmp_path: Path) -> None:
    (tmp_path / "screening.yaml").write_text(
        "type: object\nrequired: [screen]\nproperties: {screen: {type: boolean}}\n",
        encoding="utf-8",
    )
    assertion = schema_valid(schema_file="screening.yaml")
    assert evaluate_schema_valid(assertion, '{"screen": true}', base_dir=tmp_path).passed


def test_an_absolute_schema_file_ignores_base_dir(tmp_path: Path) -> None:
    absolute = tmp_path / "screening.json"
    absolute.write_text(json.dumps(SCHEMA), encoding="utf-8")
    assertion = schema_valid(schema_file=str(absolute))
    result = evaluate_schema_valid(
        assertion, '{"screen": true, "start_age": 35}', base_dir=tmp_path / "elsewhere"
    )
    assert result.passed


def test_base_dir_defaults_to_the_working_directory(tmp_path: Path, monkeypatch: Any) -> None:
    (tmp_path / "screening.json").write_text(json.dumps(SCHEMA), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assertion = schema_valid(schema_file="screening.json")
    assert evaluate_schema_valid(assertion, '{"screen": true, "start_age": 35}').passed


def test_a_missing_schema_file_is_a_failed_result_naming_the_path(tmp_path: Path) -> None:
    assertion = schema_valid(schema_file="nowhere/screening.json")
    result = evaluate_schema_valid(assertion, "{}", base_dir=tmp_path)
    assert not result.passed
    assert "cannot read schema_file" in result.detail
    assert "nowhere/screening.json" in result.detail


def test_a_schema_file_that_is_not_yaml_is_a_failed_result(tmp_path: Path) -> None:
    (tmp_path / "broken.yaml").write_text("key: [unclosed\n", encoding="utf-8")
    result = evaluate_schema_valid(schema_valid(schema_file="broken.yaml"), "{}", base_dir=tmp_path)
    assert not result.passed
    assert "is not valid YAML or JSON" in result.detail


def test_a_schema_file_holding_something_other_than_a_mapping_is_a_failed_result(
    tmp_path: Path,
) -> None:
    (tmp_path / "list.yaml").write_text("- one\n- two\n", encoding="utf-8")
    result = evaluate_schema_valid(schema_valid(schema_file="list.yaml"), "{}", base_dir=tmp_path)
    assert not result.passed
    assert "holds a list, not a JSON Schema object" in result.detail
