"""Phase 2: the case model, the YAML loader and dotted field access."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from probatio import LLMCase, ProbatioConfigError, load_cases
from probatio.case import (
    ContainsAssertion,
    NotContainsAssertion,
    SchemaValidAssertion,
    SimilarityAssertion,
    get_field,
    with_field,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_CASES = REPO_ROOT / "examples" / "demo_suite" / "cases"

MINIMAL: dict[str, Any] = {
    "id": "c1",
    "input": {"question": "q?", "documents": ["d1", "d2"]},
    "assertions": [{"type": "contains", "any": ["yes"]}],
}


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


# --- the demo suite, which is the specification -----------------------------------------------


def test_demo_suite_cases_load_in_path_order() -> None:
    cases = load_cases(DEMO_CASES)
    assert [case.id for case in cases] == [
        "htn-definition",
        "htn-first-line",
        "t2d-screening-json",
        "t2d-metformin",
        "gerd-alarm-features",
        "copd-spirometry",
        "red-flag-chest-pain",
        "insomnia-first-line",
        "anxiety-expected-fail",
        "flu-antivirals-flaky",
    ]
    assert [case.id for case in load_cases(str(DEMO_CASES))] == [case.id for case in cases]


def test_demo_suite_covers_every_assertion_type_and_the_bare_string_input() -> None:
    cases = {case.id: case for case in load_cases(DEMO_CASES)}
    declared = {assertion.type for case in cases.values() for assertion in case.assertions}
    assert declared == {"schema_valid", "contains", "not_contains", "similarity", "judge"}

    copd = cases["copd-spirometry"]
    assert copd.input == "In one sentence, what test confirms a diagnosis of COPD?"
    assert copd.system is None
    assert copd.snapshot == "off"

    htn = cases["htn-definition"]
    assert htn.snapshot == "scores"
    assert htn.tags == ["paraphrase"]
    assert htn.budget.max_cost_usd == 0.01
    assert htn.budget.max_latency_ms == 5000
    assert isinstance(htn.assertions[0], ContainsAssertion)
    assert isinstance(htn.assertions[1], NotContainsAssertion)
    assert isinstance(htn.assertions[2], SimilarityAssertion)
    assert htn.assertions[3].type == "judge"

    schema_assertion = cases["t2d-screening-json"].assertions[0]
    assert isinstance(schema_assertion, SchemaValidAssertion)
    assert schema_assertion.json_schema is not None
    assert schema_assertion.json_schema["required"] == ["screen", "start_age"]


def test_a_bare_string_input_round_trips_through_yaml(tmp_path: Path) -> None:
    original = load_cases(DEMO_CASES / "06-copd-spirometry.yaml")[0]
    dumped = write(tmp_path / "c.yaml", _yaml_dump(original))
    assert load_cases(dumped)[0] == original


def _yaml_dump(case: LLMCase) -> str:
    import yaml

    return yaml.safe_dump(case.model_dump(by_alias=True, exclude_none=True), sort_keys=True)


# --- loader shapes ------------------------------------------------------------------------------


def test_a_file_may_hold_one_mapping_a_list_or_several_documents(tmp_path: Path) -> None:
    write(tmp_path / "one.yaml", "id: a\ninput: q\nassertions: [{type: contains, any: [x]}]\n")
    write(
        tmp_path / "two.yml",
        "- {id: b, input: q, assertions: [{type: contains, any: [x]}]}\n"
        "- {id: c, input: q, assertions: [{type: contains, any: [x]}]}\n",
    )
    write(
        tmp_path / "three.yaml",
        "id: d\ninput: q\nassertions: [{type: contains, any: [x]}]\n"
        "---\n"
        "id: e\ninput: q\nassertions: [{type: contains, any: [x]}]\n"
        "---\n",
    )
    # one.yaml, then three.yaml's two documents, then two.yml's list, in sorted path order.
    assert [case.id for case in load_cases(tmp_path)] == ["a", "d", "e", "b", "c"]


def test_directories_are_walked_recursively_in_sorted_path_order(tmp_path: Path) -> None:
    (tmp_path / "b").mkdir()
    write(
        tmp_path / "b" / "02.yaml",
        "id: second\ninput: q\nassertions: [{type: contains, any: [x]}]\n",
    )
    write(tmp_path / "a.yaml", "id: first\ninput: q\nassertions: [{type: contains, any: [x]}]\n")
    write(tmp_path / "notes.txt", "id: ignored\n")
    assert [case.id for case in load_cases(tmp_path)] == ["first", "second"]


def test_a_directory_with_no_case_files_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ProbatioConfigError, match="holds no .yaml or .yml case files"):
        load_cases(tmp_path)


def test_a_missing_path_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ProbatioConfigError, match="does not exist"):
        load_cases(tmp_path / "absent")


# --- loader failures name the file and the field ------------------------------------------------


def test_an_unknown_key_names_the_file_and_the_field(tmp_path: Path) -> None:
    path = write(
        tmp_path / "typo.yaml",
        "id: c1\ninput: q\nassertion:\n  - {type: contains, any: [x]}\n",
    )
    with pytest.raises(ProbatioConfigError) as caught:
        load_cases(path)
    message = str(caught.value)
    assert "typo.yaml" in message
    assert "assertion" in message
    assert "Extra inputs are not permitted" in message
    assert caught.value.case_id == "c1"


def test_a_wrong_field_type_names_the_nested_field(tmp_path: Path) -> None:
    path = write(
        tmp_path / "bad.yaml",
        "id: c1\ninput: q\nassertions: [{type: similarity, reference: r, tau: 4}]\n",
    )
    with pytest.raises(ProbatioConfigError) as caught:
        load_cases(path)
    assert "bad.yaml" in str(caught.value)
    assert "assertions.0.similarity.tau" in str(caught.value)


def test_invalid_yaml_names_the_file_and_the_line(tmp_path: Path) -> None:
    path = write(tmp_path / "broken.yaml", "id: c1\ninput: [unclosed\n")
    with pytest.raises(ProbatioConfigError) as caught:
        load_cases(path)
    assert "broken.yaml" in str(caught.value)
    assert "invalid YAML at line 3, column 1" in str(caught.value)
    assert "expected ',' or ']'" in str(caught.value)


def test_a_document_that_is_not_a_mapping_is_an_error(tmp_path: Path) -> None:
    path = write(tmp_path / "list.yaml", "- just a string\n")
    with pytest.raises(ProbatioConfigError, match="entry 1 is a str"):
        load_cases(path)


def test_duplicate_ids_name_both_files(tmp_path: Path) -> None:
    write(tmp_path / "a.yaml", "id: dup\ninput: q\nassertions: [{type: contains, any: [x]}]\n")
    write(tmp_path / "b.yaml", "id: dup\ninput: q\nassertions: [{type: contains, any: [x]}]\n")
    with pytest.raises(ProbatioConfigError) as caught:
        load_cases(tmp_path)
    assert "b.yaml" in str(caught.value)
    assert "a.yaml" in str(caught.value)
    assert caught.value.case_id == "dup"


def test_many_errors_in_one_case_are_summarised(tmp_path: Path) -> None:
    path = write(
        tmp_path / "many.yaml",
        "id: '!'\ninput: 3\nassertions: []\nsnapshot: sometimes\nbudget: {max_cost_usd: -1}\n",
    )
    with pytest.raises(ProbatioConfigError) as caught:
        load_cases(path)
    assert "and 3 more" in str(caught.value)
    assert caught.value.case_id == "!", "the id the file gave is reported even when it is invalid"


def test_a_case_with_no_id_reports_no_case_id(tmp_path: Path) -> None:
    path = write(tmp_path / "anon.yaml", "input: q\nassertions: [{type: contains, any: [x]}]\n")
    with pytest.raises(ProbatioConfigError) as caught:
        load_cases(path)
    assert "id: Field required" in str(caught.value)
    assert caught.value.case_id is None


# --- the model ----------------------------------------------------------------------------------


def test_cases_are_frozen_so_a_relation_cannot_mutate_a_shared_case() -> None:
    case = LLMCase.model_validate(MINIMAL)
    with pytest.raises(ValidationError):
        case.id = "other"


@pytest.mark.parametrize("case_id", ["", "-leading", "with space", "a" * 65, "a/b"])
def test_case_ids_stay_path_safe(case_id: str) -> None:
    with pytest.raises(ValidationError, match="id"):
        LLMCase.model_validate({**MINIMAL, "id": case_id})


def test_at_least_one_assertion_is_required() -> None:
    with pytest.raises(ValidationError, match="assertions"):
        LLMCase.model_validate({**MINIMAL, "assertions": []})


def test_defaults_are_independent_between_cases() -> None:
    first = LLMCase.model_validate(MINIMAL)
    second = LLMCase.model_validate({**MINIMAL, "id": "c2"})
    assert first.params == second.params == {}
    assert first.params is not second.params
    assert first.budget == second.budget == first.budget.model_copy()
    assert first.snapshot == "off"
    assert first.tags == []


@pytest.mark.parametrize(
    ("assertion", "match"),
    [
        ({"type": "schema_valid"}, "exactly one of 'schema' or 'schema_file'"),
        (
            {"type": "schema_valid", "schema": {}, "schema_file": "s.json"},
            "exactly one of 'schema' or 'schema_file'",
        ),
        ({"type": "contains"}, "at least one of 'any' or 'all'"),
        ({"type": "contains", "any": [], "all": []}, "at least one of 'any' or 'all'"),
        ({"type": "not_contains", "all": []}, "at least 1 item"),
        ({"type": "similarity", "reference": "r", "tau": 1.5}, "less than or equal to 1"),
        ({"type": "judge", "rubric": "r", "threshold": -0.1}, "greater than or equal to 0"),
        ({"type": "no_such_type"}, "does not match any of the expected tags"),
    ],
)
def test_assertion_declarations_are_checked(assertion: dict[str, Any], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        LLMCase.model_validate({**MINIMAL, "assertions": [assertion]})


def test_the_yaml_spelling_and_the_field_name_both_validate() -> None:
    by_alias = ContainsAssertion.model_validate({"type": "contains", "any": ["a"], "all": ["b"]})
    by_name = ContainsAssertion.model_validate({"type": "contains", "any_": ["a"], "all_": ["b"]})
    assert by_alias == by_name
    assert ContainsAssertion.model_validate(by_alias.model_dump()) == by_alias


# --- dotted field access ------------------------------------------------------------------------


def test_get_field_reads_case_fields_and_mapping_keys() -> None:
    case = LLMCase.model_validate({**MINIMAL, "system": "s", "tags": ["t"]})
    assert get_field(case, "input.documents") == ["d1", "d2"]
    assert get_field(case, "input.question") == "q?"
    assert get_field(case, "system") == "s"
    assert get_field(case, "tags") == ["t"]
    assert get_field(case, "id") == "c1"


def test_an_unresolved_key_returns_the_default_or_raises() -> None:
    bare = LLMCase.model_validate({**MINIMAL, "input": "just a question"})
    assert get_field(bare, "input.documents", None) is None
    assert get_field(bare, "input.documents", []) == []
    with pytest.raises(ProbatioConfigError) as caught:
        get_field(bare, "input.documents")
    assert "'documents' is not a key of the value at 'input'" in str(caught.value)
    assert caught.value.case_id == "c1"


def test_a_path_that_is_not_a_case_field_is_always_an_error_even_with_a_default() -> None:
    case = LLMCase.model_validate(MINIMAL)
    with pytest.raises(ProbatioConfigError, match="which is not a field of LLMCase"):
        get_field(case, "inpit.documents", None)


@pytest.mark.parametrize("path", ["", ".", "input.", "input..documents"])
def test_a_malformed_path_is_rejected(path: str) -> None:
    case = LLMCase.model_validate(MINIMAL)
    with pytest.raises(ProbatioConfigError, match="is not a field path"):
        get_field(case, path, None)


def test_with_field_returns_a_copy_and_leaves_the_original_alone() -> None:
    case = LLMCase.model_validate(MINIMAL)
    variant = with_field(case, "input.documents", ["d2", "d1"])
    assert get_field(variant, "input.documents") == ["d2", "d1"]
    assert get_field(case, "input.documents") == ["d1", "d2"]
    assert get_field(variant, "input.question") == "q?"
    assert variant.id == case.id
    assert variant is not case


def test_with_field_replaces_a_whole_case_field() -> None:
    case = LLMCase.model_validate(MINIMAL)
    assert with_field(case, "input", "a bare string").input == "a bare string"
    assert with_field(case, "system", "new system").system == "new system"


def test_with_field_refuses_to_invent_a_key() -> None:
    bare = LLMCase.model_validate({**MINIMAL, "input": "just a question"})
    with pytest.raises(ProbatioConfigError, match="nothing to replace"):
        with_field(bare, "input.documents", ["d"])
    nested = LLMCase.model_validate({**MINIMAL, "input": {"question": "q?"}})
    with pytest.raises(ProbatioConfigError, match="nothing to replace"):
        with_field(nested, "input.retrieval.documents", ["d"])


def test_with_field_validates_the_replacement() -> None:
    case = LLMCase.model_validate(MINIMAL)
    with pytest.raises(ProbatioConfigError, match="makes the case invalid"):
        with_field(case, "id", "not a valid id")


def test_with_field_walks_more_than_one_mapping_level() -> None:
    nested = LLMCase.model_validate(
        {**MINIMAL, "input": {"question": "q?", "retrieval": {"documents": ["d1"]}}}
    )
    variant = with_field(nested, "input.retrieval.documents", ["d1", "d2"])
    assert get_field(variant, "input.retrieval.documents") == ["d1", "d2"]
    assert get_field(nested, "input.retrieval.documents") == ["d1"]


def test_a_yaml_error_with_no_position_still_names_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PyYAML marks most syntax errors; the unmarked ones must still say which file broke."""
    import yaml

    path = write(tmp_path / "odd.yaml", "id: c1\n")

    def raise_unmarked(*args: object, **kwargs: object) -> object:
        raise yaml.YAMLError("something PyYAML could not place")

    monkeypatch.setattr(yaml, "safe_load_all", raise_unmarked)
    with pytest.raises(ProbatioConfigError) as caught:
        load_cases(path)
    assert "odd.yaml: invalid YAML: something PyYAML could not place" in str(caught.value)
