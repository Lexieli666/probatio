"""Phase 8: ``docs/relations.md`` says what the code does, and invents no bibliography."""

from __future__ import annotations

import re
from pathlib import Path

from probatio.metamorphic import RELATIONS

DOC = Path(__file__).resolve().parents[1] / "docs" / "relations.md"
KEYS = ("[LLMORPH]", "[MR-CATALOG-NLP]", "[CHEN-MT-SURVEY]", "[SEGURA-MT-SURVEY]")
TEXT = DOC.read_text(encoding="utf-8")


def test_every_relation_and_its_citation_key_appear_in_the_doc() -> None:
    for name in RELATIONS.names():
        relation = RELATIONS.get(name)
        assert name in TEXT, name
        assert relation.citation in TEXT, relation.citation


def test_every_citation_key_a_relation_names_is_one_of_the_listed_entries() -> None:
    for name in RELATIONS.names():
        assert RELATIONS.get(name).citation in KEYS


def test_every_relation_docstring_carries_its_citation_key() -> None:
    for name in RELATIONS.names():
        relation = RELATIONS.get(name)
        assert relation.__doc__ is not None
        assert relation.citation in relation.__doc__, name


def test_all_four_reference_keys_are_listed() -> None:
    references = TEXT.split("## References", 1)[1]
    for key in KEYS:
        assert f"`{key}`" in references, key


def test_the_references_defer_their_details_to_phase_13() -> None:
    references = TEXT.split("## References", 1)[1]
    assert "verified and filled in in Phase 13" in references
    assert "provisional" in references


def test_no_reference_invents_a_year_a_doi_or_a_venue() -> None:
    """Spec §7 and CLAUDE.md: no fact in the docs that a committed source does not support.

    Only the entries themselves are checked, not the paragraph above them that promises the
    authors, venue, year and DOI are filled in in Phase 13.
    """
    references = TEXT.split("## References", 1)[1]
    entries = "\n".join(line for line in references.splitlines() if line.startswith("- `["))
    assert entries.count("- `[") == len(KEYS)
    assert re.search(r"\b(19|20)\d{2}\b", entries) is None
    for invention in ("doi", "arxiv", "proceedings", "et al., "):
        assert invention not in entries.lower()


def test_the_recipe_lists_its_four_steps() -> None:
    recipe = TEXT.split("## Adding a relation", 1)[1].split("## References", 1)[0]
    assert "One class" in recipe
    assert "One `variants()` method" in recipe
    assert "One registry line" in recipe
    assert "One docs entry" in recipe
    assert "RELATIONS.register" in recipe


def test_the_doc_quotes_no_violation_rate_from_the_demo_suite() -> None:
    """The demo's rates are test assertions (tests/test_metamorphic_demo.py), not documentation."""
    assert re.search(r"\b0\.\d+\b", TEXT.replace("`0.00`", "")) is None
    for case_id in ("htn-definition", "t2d-metformin", "gerd-alarm-features", "copd-spirometry"):
        if case_id == "htn-definition":
            continue  # named only in the file-format example
        assert case_id not in TEXT


def test_the_three_rules_are_stated() -> None:
    assert "either direction" in TEXT
    assert "Not applicable is not zero" in TEXT
    assert "stable_hash((case.id, field))" in TEXT
    assert "never generated during a test run" in TEXT
