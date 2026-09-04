"""Phase 8: the four relations, their applicability rules and their determinism."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from probatio import (
    LLMCase,
    MissingVariantsError,
    ProbatioConfigError,
    distractor_robust,
    format_jitter,
    order_invariant,
    paraphrase_invariant,
)
from probatio.metamorphic import (
    JITTER_KINDS,
    RELATION_MARKER,
    DistractorRobust,
    FormatJitter,
    OrderInvariant,
    ParaphraseInvariant,
    Variant,
    upper_first_sentence,
)

ASSERTION = {"type": "contains", "any": ["anything"]}


def documents(variants: list[Variant]) -> list[list[Any]]:
    return [variant.case.input["documents"] for variant in variants]  # type: ignore[index]


def questions(variants: list[Variant]) -> list[str]:
    return [variant.case.input["question"] for variant in variants]  # type: ignore[index]


def orders(relation: OrderInvariant, subject: LLMCase) -> list[list[Any]]:
    return documents(relation.variants(subject))


def case(**overrides: Any) -> LLMCase:
    payload: dict[str, Any] = {
        "id": "c1",
        "input": {"question": "First one. Second one.", "documents": ["a", "b", "c"]},
        "assertions": [ASSERTION],
    }
    payload.update(overrides)
    return LLMCase.model_validate(payload)


BARE = case(id="bare", input="One sentence only.")
NO_QUESTION = case(id="noq", input={"documents": ["a", "b"]})


# -- the decorators are thin ----------------------------------------------------------------------


def test_every_decorator_applies_the_relation_marker_and_nothing_else() -> None:
    marks = [
        order_invariant(field="input.documents", k=3),
        distractor_robust(field="input.documents", distractors=["x"]),
        format_jitter(field="input.question"),
        paraphrase_invariant(k=3, field="input.question", variants_dir="variants"),
    ]
    expected = [OrderInvariant, DistractorRobust, FormatJitter, ParaphraseInvariant]
    for mark, kind in zip(marks, expected, strict=True):
        assert mark.mark.name == RELATION_MARKER
        assert mark.mark.kwargs == {}
        assert len(mark.mark.args) == 1
        assert isinstance(mark.mark.args[0], kind)


def test_the_decorators_carry_the_arguments_through() -> None:
    relation = order_invariant(field="input.documents", k=7).mark.args[0]
    assert (relation.field, relation.k) == ("input.documents", 7)
    jitter = format_jitter(kinds=("casing",), field="input.question").mark.args[0]
    assert (jitter.kinds, jitter.field) == (("casing",), "input.question")


def test_a_relation_can_still_be_applied_to_a_test_function() -> None:
    @order_invariant(field="input.documents")
    def sample() -> None:
        """A test function the decorator is applied to."""

    assert sample.pytestmark[0].name == RELATION_MARKER


# -- argument checking ----------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["", ".", "input.", "input..question"])
def test_a_malformed_field_path_is_refused_at_construction(field: str) -> None:
    with pytest.raises(ProbatioConfigError, match="is not a field path"):
        OrderInvariant(field)


@pytest.mark.parametrize("k", [0, -1])
def test_a_variant_count_below_one_is_refused(k: int) -> None:
    with pytest.raises(ProbatioConfigError, match="needs k >= 1"):
        OrderInvariant("input.documents", k)
    with pytest.raises(ProbatioConfigError, match="needs k >= 1"):
        ParaphraseInvariant(k)


def test_distractor_robust_needs_a_distractor() -> None:
    with pytest.raises(ProbatioConfigError, match="at least one distractor"):
        DistractorRobust(distractors=[])
    with pytest.raises(ProbatioConfigError, match="empty distractor"):
        DistractorRobust(distractors=["   "])


def test_distractor_robust_refuses_a_position_it_cannot_insert_at() -> None:
    with pytest.raises(ProbatioConfigError, match="'middle'"):
        DistractorRobust(distractors=["x"], positions=("middle",))
    with pytest.raises(ProbatioConfigError, match="at least one"):
        DistractorRobust(distractors=["x"], positions=())


def test_format_jitter_refuses_a_kind_it_has_no_transform_for() -> None:
    with pytest.raises(ProbatioConfigError, match="'shouting'"):
        FormatJitter(("shouting",))
    with pytest.raises(ProbatioConfigError, match="at least one"):
        FormatJitter(())


def test_a_field_path_that_does_not_start_at_a_case_field_is_a_typo_not_a_shrug() -> None:
    """DECISIONS 13: a bad root is a mistake in the relation, so it raises rather than skipping."""
    with pytest.raises(ProbatioConfigError, match="not a field of LLMCase"):
        OrderInvariant("inpit.documents").applicable(case())


# -- order_invariant ------------------------------------------------------------------------------


def test_order_invariant_yields_k_distinct_non_identity_permutations() -> None:
    relation = OrderInvariant("input.documents", 3)
    subject = case(input={"question": "q", "documents": ["a", "b", "c", "d"]})
    variants = relation.variants(subject)
    assert len(variants) == 3
    permuted = documents(variants)
    assert all(order != ["a", "b", "c", "d"] for order in permuted)
    assert len({tuple(order) for order in permuted}) == 3
    assert [variant.label for variant in variants] == [
        "permutation-1",
        "permutation-2",
        "permutation-3",
    ]


def test_order_invariant_on_a_two_element_list_yields_exactly_one_variant() -> None:
    """Spec §3.9 acceptance: a two-element list has one non-identity permutation, so k=3 gives 1."""
    subject = case(input={"question": "q", "documents": ["a", "b"]})
    variants = OrderInvariant("input.documents", 3).variants(subject)
    assert len(variants) == 1
    assert documents(variants) == [["b", "a"]]


def test_order_invariant_stops_at_the_number_of_distinct_orderings() -> None:
    """Three items, two of them equal, have two non-identity orderings, not five."""
    subject = case(input={"question": "q", "documents": ["a", "a", "b"]})
    assert len(OrderInvariant("input.documents", 5).variants(subject)) == 2


def test_order_invariant_does_not_count_orderings_of_a_long_list() -> None:
    """Above ten items the exact count of distinct orderings is not worth computing."""
    subject = case(input={"question": "q", "documents": [str(n) for n in range(11)]})
    assert len(OrderInvariant("input.documents", 4).variants(subject)) == 4


def test_order_invariant_is_not_applicable_below_two_items_or_off_a_list() -> None:
    relation = OrderInvariant("input.documents")
    assert relation.applicable(case()) is True
    assert relation.applicable(case(input={"question": "q", "documents": ["only"]})) is False
    assert relation.applicable(case(input={"question": "q", "documents": []})) is False
    assert relation.applicable(BARE) is False
    assert relation.applicable(case(input={"question": "q", "documents": "not a list"})) is False
    assert relation.variants(BARE) == []


def test_order_invariant_leaves_the_original_case_untouched() -> None:
    subject = case()
    OrderInvariant("input.documents").variants(subject)
    assert subject.input["documents"] == ["a", "b", "c"]  # type: ignore[index]


def test_order_invariant_is_seeded_from_the_case_id_and_the_field() -> None:
    subject = case(input={"question": "q", "documents": list("abcdef")})
    first = orders(OrderInvariant("input.documents", 3), subject)
    assert orders(OrderInvariant("input.documents", 3), subject) == first

    other = case(id="c2", input={"question": "q", "documents": list("abcdef")})
    assert orders(OrderInvariant("input.documents", 3), other) != first


# -- distractor_robust ----------------------------------------------------------------------------


def test_distractor_robust_inserts_a_list_item_at_each_end() -> None:
    relation = DistractorRobust(field="input.documents", distractors=["noise"])
    variants = relation.variants(case())
    assert [variant.label for variant in variants] == [
        "distractor-start-1",
        "distractor-end-1",
    ]
    assert documents(variants) == [["noise", "a", "b", "c"], ["a", "b", "c", "noise"]]


def test_distractor_robust_makes_one_variant_per_position_and_distractor() -> None:
    relation = DistractorRobust(field="input.documents", distractors=["one", "two"])
    assert [variant.label for variant in relation.variants(case())] == [
        "distractor-start-1",
        "distractor-start-2",
        "distractor-end-1",
        "distractor-end-2",
    ]


def test_distractor_robust_prepends_and_appends_to_a_bare_string_input() -> None:
    """DECISIONS 7: ``field=None`` keeps the spec table's string behaviour."""
    relation = DistractorRobust(distractors=["noise"])
    variants = relation.variants(BARE)
    assert variants[0].case.input == "noise\n\nOne sentence only."
    assert variants[1].case.input == "One sentence only.\n\nnoise"


def test_distractor_robust_is_not_applicable_when_its_target_is_the_wrong_shape() -> None:
    assert DistractorRobust(distractors=["x"]).applicable(case()) is False
    assert DistractorRobust(distractors=["x"]).applicable(BARE) is True
    assert DistractorRobust(field="input.documents", distractors=["x"]).applicable(BARE) is False
    assert DistractorRobust(field="input.documents", distractors=["x"]).variants(BARE) == []


def test_distractor_robust_can_insert_into_an_empty_list() -> None:
    subject = case(input={"question": "q", "documents": []})
    relation = DistractorRobust(field="input.documents", distractors=["noise"], positions=("end",))
    assert documents(relation.variants(subject)) == [["noise"]]


# -- format_jitter --------------------------------------------------------------------------------


def test_format_jitter_makes_one_variant_per_kind_in_order() -> None:
    variants = FormatJitter(field="input.question").variants(case())
    assert [variant.label for variant in variants] == list(JITTER_KINDS)
    texts = questions(variants)
    assert texts[0] == "First  one.  Second  one.\n\n"
    assert texts[1] == "FIRST ONE. Second one."
    assert texts[2] == "```\nFirst one. Second one.\n```"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("First one. Second one.", "FIRST ONE. Second one."),
        ("Only one sentence.", "ONLY ONE SENTENCE."),
        ("no terminator at all", "NO TERMINATOR AT ALL"),
        ("Shouting! quiet.", "SHOUTING! quiet."),
        ("A question? An answer.", "A QUESTION? An answer."),
        ("Trailing space. ", "TRAILING SPACE. "),
        ("", ""),
    ],
)
def test_upper_first_sentence_stops_at_the_first_terminator(text: str, expected: str) -> None:
    assert upper_first_sentence(text) == expected


def test_format_jitter_can_be_narrowed_to_one_kind() -> None:
    variants = FormatJitter(("casing",), "input.question").variants(case())
    assert [variant.label for variant in variants] == ["casing"]


def test_format_jitter_jitters_a_bare_string_input_when_given_no_field() -> None:
    variants = FormatJitter().variants(BARE)
    assert variants[1].case.input == "ONE SENTENCE ONLY."


def test_format_jitter_is_not_applicable_without_a_string_at_its_field() -> None:
    relation = FormatJitter(field="input.question")
    assert relation.applicable(case()) is True
    assert relation.applicable(BARE) is False
    assert relation.applicable(NO_QUESTION) is False
    assert relation.variants(NO_QUESTION) == []
    assert FormatJitter().applicable(case()) is False


FIXED_TRANSFORM_SCRIPT = """
import json
from probatio import LLMCase
from probatio.metamorphic import FormatJitter, OrderInvariant

case = LLMCase.model_validate(
    {
        "id": "c1",
        "input": {"question": "First one. Second one.", "documents": list("abcdef")},
        "assertions": [{"type": "contains", "any": ["anything"]}],
    }
)
print(
    json.dumps(
        {
            "jitter": [
                v.case.input["question"]
                for v in FormatJitter(field="input.question").variants(case)
            ],
            "order": [
                v.case.input["documents"]
                for v in OrderInvariant("input.documents", 3).variants(case)
            ],
        }
    )
)
"""


def _in_subprocess() -> str:
    return subprocess.run(
        [sys.executable, "-c", FIXED_TRANSFORM_SCRIPT],
        check=True,
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    ).stdout


def test_format_jitter_variants_are_byte_identical_across_two_processes() -> None:
    """Spec §3.9 acceptance. ``order_invariant`` rides along: its seed is a content hash."""
    assert _in_subprocess() == _in_subprocess()
    first = _in_subprocess()
    assert "FIRST ONE. Second one." in first
    assert "permutation" not in first


# -- paraphrase_invariant -------------------------------------------------------------------------


def test_paraphrase_invariant_with_no_file_names_the_freeze_command(tmp_path: Path) -> None:
    """Spec §3.9 acceptance: the error carries the command that writes the missing file."""
    relation = ParaphraseInvariant(3, "input.question", tmp_path / "variants")
    with pytest.raises(MissingVariantsError) as excinfo:
        relation.variants(case())
    message = str(excinfo.value)
    assert "freeze-variants" in message
    assert "--field input.question" in message
    assert "--provider claude-cli" in message
    assert "[c1]" in message


def test_paraphrase_invariant_reads_the_first_k_in_file_order(tmp_path: Path) -> None:
    (tmp_path / "c1.yaml").write_text(
        "case_id: c1\nfield: input.question\n"
        'generated_by: {provider: human, model: null, created: "2026-09-04", prompt_hash: null}\n'
        "variants: [one, two, three, four]\n",
        encoding="utf-8",
    )
    variants = ParaphraseInvariant(3, "input.question", tmp_path).variants(case())
    assert [variant.label for variant in variants] == [
        "paraphrase-1",
        "paraphrase-2",
        "paraphrase-3",
    ]
    assert questions(variants) == ["one", "two", "three"]


def test_paraphrase_invariant_over_a_two_entry_file_makes_two_variants(tmp_path: Path) -> None:
    """DECISIONS 52: a reviewed file that lost a paraphrase is measured over what is left."""
    (tmp_path / "c1.yaml").write_text(
        "# The third paraphrase changed the question, so it was deleted in review.\n"
        "case_id: c1\nfield: input.question\n"
        'generated_by: {provider: claude-cli, model: m, created: "2026-09-04", prompt_hash: h}\n'
        "variants: [one, two]\n",
        encoding="utf-8",
    )
    variants = ParaphraseInvariant(3, "input.question", tmp_path).variants(case())
    assert [variant.label for variant in variants] == ["paraphrase-1", "paraphrase-2"]
    assert questions(variants) == ["one", "two"]


def test_a_file_with_no_variants_left_raises_and_asks_for_force(tmp_path: Path) -> None:
    (tmp_path / "c1.yaml").write_text(
        "case_id: c1\nfield: input.question\n"
        'generated_by: {provider: human, model: null, created: "2026-09-04", prompt_hash: null}\n'
        "variants: []\n",
        encoding="utf-8",
    )
    with pytest.raises(MissingVariantsError, match="exists but holds no variants") as excinfo:
        ParaphraseInvariant(3, "input.question", tmp_path).variants(case())
    assert str(excinfo.value).endswith("--force")


def test_paraphrase_invariant_is_not_applicable_without_a_string_and_reads_no_file() -> None:
    relation = ParaphraseInvariant(3, "input.question", Path("/nonexistent"))
    assert relation.applicable(BARE) is False
    assert relation.variants(BARE) == []


def test_a_relative_variants_dir_is_resolved_against_the_base_directory(tmp_path: Path) -> None:
    """DECISIONS 19: relative paths take a ``base_dir``, defaulting to the working directory."""
    relation = ParaphraseInvariant(3, "input.question", "variants", tmp_path)
    assert relation.resolved_variants_dir() == tmp_path / "variants"
    absolute = ParaphraseInvariant(3, "input.question", tmp_path / "elsewhere", tmp_path)
    assert absolute.resolved_variants_dir() == tmp_path / "elsewhere"


def test_a_relative_variants_dir_falls_back_to_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert ParaphraseInvariant().resolved_variants_dir() == tmp_path / "variants"
