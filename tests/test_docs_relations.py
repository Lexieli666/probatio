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


def test_every_reference_entry_carries_the_details_verified_in_phase_13() -> None:
    """Phase 13 replaced the four placeholders; every entry now names a venue, a year and a DOI."""
    references = TEXT.split("## References", 1)[1]
    entries = [line for line in references.splitlines() if line.startswith("- `[")]
    assert len(entries) == len(KEYS) + 1  # the four relation keys, plus [MTF] for the README
    for entry in entries:
        block = references.split(entry, 1)[1].split("\n- `[", 1)[0]
        text = entry + block
        assert re.search(r"\b(20)\d{2}\b", text), entry
        assert re.search(r"DOI \[10\.\d{4,}/", text), entry


def test_the_references_are_the_ones_verified_against_crossref() -> None:
    """The five DOIs checked on 2026-09-05; a sixth entry would be one nobody verified."""
    references = TEXT.split("## References", 1)[1]
    assert "Verified on 2026-09-05 against Crossref" in references
    dois = set(re.findall(r"DOI \[(10\.[^\]]+)\]", references))
    assert dois == {
        "10.1109/ASE63991.2025.00385",
        "10.1109/ICSME64153.2025.00025",
        "10.1145/3143561",
        "10.1109/TSE.2016.2532875",
        "10.1145/3787120.3787123",
    }, dois


def test_every_doi_link_points_at_the_doi_it_names() -> None:
    references = TEXT.split("## References", 1)[1]
    for doi, href in re.findall(r"DOI \[(10\.[^\]]+)\]\(([^)]+)\)", references):
        assert href == f"https://doi.org/{doi}", doi


def test_the_catalogue_size_is_attributed_to_the_abstract_that_states_it() -> None:
    """The abstract of [MR-CATALOG-NLP] gives 191 relations, where the brief said "about 190"."""
    references = TEXT.split("## References", 1)[1]
    entry = references.split("- `[MR-CATALOG-NLP]`", 1)[1].split("\n- `[", 1)[0]
    assert "**191**" in entry
    assert "abstract" in entry


def test_the_doc_claims_no_relation_of_its_own() -> None:
    """05 §5: the contribution is the packaging, and the doc has to say so where it cites."""
    references = TEXT.split("## References", 1)[1]
    assert "claims no new relation" in references


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
