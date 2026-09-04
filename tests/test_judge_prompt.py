"""Phase 4: the judge prompt template, its hash, and what it renders."""

from __future__ import annotations

import subprocess
import sys

from probatio.hashing import stable_hash
from probatio.judge import (
    JUDGE_PROMPT_TEMPLATE,
    judge_template_hash,
    render_input,
    render_judge_prompt,
)

RUBRIC = "# Faithfulness\n\nGrade whether the answer is supported by the documents.\n"


def test_the_template_is_a_module_constant_wrapping_the_four_parts_spec_3_5_names() -> None:
    assert "{rubric}" in JUDGE_PROMPT_TEMPLATE
    assert "{input}" in JUDGE_PROMPT_TEMPLATE
    assert "{output}" in JUDGE_PROMPT_TEMPLATE
    assert JUDGE_PROMPT_TEMPLATE.index("{rubric}") < JUDGE_PROMPT_TEMPLATE.index("{input}")
    assert JUDGE_PROMPT_TEMPLATE.index("{input}") < JUDGE_PROMPT_TEMPLATE.index("{output}")


def test_the_template_asks_for_strict_json_and_nothing_else() -> None:
    assert '"verdict"' in JUDGE_PROMPT_TEMPLATE
    assert '"score"' in JUDGE_PROMPT_TEMPLATE
    assert '"rationale"' in JUDGE_PROMPT_TEMPLATE
    assert "one JSON object and nothing else" in JUDGE_PROMPT_TEMPLATE
    assert "code fence" in JUDGE_PROMPT_TEMPLATE


def test_the_template_hash_is_the_stable_hash_of_the_template() -> None:
    assert judge_template_hash() == stable_hash(JUDGE_PROMPT_TEMPLATE)


def test_the_template_hash_is_the_same_in_another_process() -> None:
    """Phase 7 puts this in every judge cassette key, so it may not be salted per process."""
    other = subprocess.run(
        [
            sys.executable,
            "-c",
            "from probatio.judge import judge_template_hash; print(judge_template_hash())",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert other == judge_template_hash()


def test_a_string_input_renders_verbatim() -> None:
    assert render_input("Does spirometry confirm COPD?") == "Does spirometry confirm COPD?"


def test_a_mapping_input_renders_as_json_with_sorted_keys() -> None:
    rendered = render_input({"question": "q?", "documents": ["a", "b"]})
    assert rendered.index('"documents"') < rendered.index('"question"')
    assert render_input({"question": "q?", "documents": ["a", "b"]}) == rendered


def test_the_prompt_holds_the_rubric_the_input_and_the_output() -> None:
    prompt = render_judge_prompt(
        rubric_text=RUBRIC,
        case_input={"question": "What confirms COPD?", "documents": ["Spirometry does."]},
        output="Spirometry showing persistent airflow limitation confirms COPD.",
    )
    assert "Grade whether the answer is supported by the documents." in prompt
    assert "What confirms COPD?" in prompt
    assert "Spirometry showing persistent airflow limitation confirms COPD." in prompt
    assert "{rubric}" not in prompt


def test_rendering_is_deterministic() -> None:
    kwargs = {"rubric_text": RUBRIC, "case_input": "q?", "output": "a"}
    assert render_judge_prompt(**kwargs) == render_judge_prompt(**kwargs)
