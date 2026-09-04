"""Phase 8: the relation contract, the result model and the registry."""

from __future__ import annotations

import pytest

from probatio import LLMCase, ProbatioConfigError
from probatio.metamorphic import (
    RELATION_MARKER,
    RELATIONS,
    Flip,
    Relation,
    RelationRegistry,
    RelationResult,
    Variant,
)

CASE = LLMCase.model_validate(
    {"id": "c1", "input": {"question": "q"}, "assertions": [{"type": "contains", "any": ["a"]}]}
)


class Stub(Relation):
    name = "stub"
    citation = "[LLMORPH]"

    def variants(self, case: LLMCase) -> list[Variant]:
        return [Variant(case=case, label="only")]


class Nameless(Relation):
    citation = "[LLMORPH]"

    def variants(self, case: LLMCase) -> list[Variant]:
        return []


def test_a_relation_is_applicable_by_default() -> None:
    assert Stub().applicable(CASE) is True


def test_a_relation_cannot_be_instantiated_without_variants() -> None:
    class Incomplete(Relation):
        name = "incomplete"
        citation = "[LLMORPH]"

    with pytest.raises(TypeError):
        Incomplete()  # type: ignore[abstract]


def test_a_relation_reprs_as_its_name() -> None:
    assert repr(Stub()) == "<Stub 'stub'>"


def test_the_four_shipped_relations_are_registered_and_nothing_else_is() -> None:
    assert RELATIONS.names() == [
        "distractor_robust",
        "format_jitter",
        "order_invariant",
        "paraphrase_invariant",
    ]
    assert len(RELATIONS) == 4
    assert "order_invariant" in RELATIONS
    assert "adversarial" not in RELATIONS


def test_every_registered_relation_names_a_citation_key() -> None:
    for name in RELATIONS.names():
        relation = RELATIONS.get(name)
        assert relation.name == name
        assert relation.citation.startswith("[") and relation.citation.endswith("]")
        assert relation.__doc__


def test_the_registry_returns_the_class_it_was_given() -> None:
    registry = RelationRegistry()
    assert registry.register(Stub) is Stub
    assert registry.get("stub") is Stub


def test_a_second_relation_of_the_same_name_is_refused() -> None:
    registry = RelationRegistry()
    registry.register(Stub)
    with pytest.raises(ProbatioConfigError, match="already registered as Stub"):
        registry.register(Stub)


def test_a_relation_without_a_name_cannot_be_registered() -> None:
    registry = RelationRegistry()
    with pytest.raises(ProbatioConfigError, match="has no 'name'"):
        registry.register(Nameless)


def test_an_unknown_relation_name_lists_the_ones_that_exist() -> None:
    with pytest.raises(ProbatioConfigError, match="order_invariant"):
        RELATIONS.get("adversarial")


def test_an_empty_registry_says_none_rather_than_nothing() -> None:
    with pytest.raises(ProbatioConfigError, match=r"\(none\)"):
        RelationRegistry().get("stub")


def test_the_marker_name_is_the_one_the_spec_fixes() -> None:
    assert RELATION_MARKER == "probatio_relation"


def test_a_relation_result_may_report_no_rate_at_all() -> None:
    result = RelationResult(
        relation="stub", case_id="c1", n_variants=0, n_violations=0, violation_rate=None
    )
    assert result.violation_rate is None
    assert result.flips == []


def test_the_result_models_are_frozen_and_reject_unknown_keys() -> None:
    flip = Flip(label="a", original_verdict=True, variant_verdict=False, changed_assertions=["x"])
    with pytest.raises(ValueError, match="frozen"):
        flip.label = "b"  # type: ignore[misc]
    with pytest.raises(ValueError, match="extra"):
        Variant(case=CASE, label="a", note="x")  # type: ignore[call-arg]
