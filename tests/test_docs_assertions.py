"""``docs/assertions.md``'s numbers are recomputed from the code that produced them.

No number appears in the documentation that a committed file did not produce (`CLAUDE.md`). This
test is that rule enforced for the one table in the docs that is a measurement: it parses the
markdown, recomputes every row with ``TrigramCosine`` and fails if the doc and the code disagree
at the three decimals the doc prints.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import median

from probatio import load_cases
from probatio.assertions import TrigramCosine
from probatio.case import SimilarityAssertion

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO = REPO_ROOT / "examples" / "demo_suite"
DOC = REPO_ROOT / "docs" / "assertions.md"
HEADER = "| Output | Reference | Trigram score |"


def table_rows() -> list[tuple[str, str, str]]:
    """The data rows of the trigram table: output, reference, printed score."""
    lines = DOC.read_text(encoding="utf-8").splitlines()
    start = lines.index(HEADER) + 2
    rows: list[tuple[str, str, str]] = []
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        assert len(cells) == 3, f"malformed table row: {line}"
        rows.append((cells[0], cells[1], cells[2]))
    return rows


def test_the_table_has_the_five_pairs_the_prose_refers_to() -> None:
    rows = table_rows()
    assert len(rows) == 5
    assert len({(output, reference) for output, reference, _ in rows}) == 5


def test_every_printed_score_is_what_the_shipped_backend_computes() -> None:
    backend = TrigramCosine()
    for output, reference, printed in table_rows():
        recomputed = f"{backend.similarity(output, reference):.3f}"
        assert recomputed == printed, (
            f"docs/assertions.md prints {printed} for {output!r} against {reference!r}, but "
            f"TrigramCosine computes {recomputed}"
        )


def test_the_rows_are_ordered_from_most_to_least_similar() -> None:
    """The prose reads down the column to pick a tau, so the ordering is load-bearing."""
    scores = [float(printed) for _, _, printed in table_rows()]
    assert scores == sorted(scores, reverse=True)


def test_the_contradictory_pair_the_prose_argues_from_is_still_in_the_table() -> None:
    """The position "similarity is not a judge" rests on this row scoring what it scores."""
    backend = TrigramCosine()
    contradiction = "Metformin should not be started when kidney function is severely reduced."
    reference = "Metformin is the usual initial medication for type 2 diabetes."
    assert (contradiction, reference, "0.223") in table_rows()
    assert backend.similarity(contradiction, reference) > 0.20


# --- Phase 4: the tau values the doc is allowed to name -----------------------------------------


def demo_tau_values() -> set[str]:
    """Every ``tau`` the demo suite commits, as the doc prints them."""
    cases = load_cases(DEMO / "cases")
    return {
        f"{assertion.tau:.2f}"
        for case in cases
        for assertion in case.assertions
        if isinstance(assertion, SimilarityAssertion)
    }


def test_the_only_tau_values_the_doc_names_are_the_ones_the_demo_suite_commits() -> None:
    """CLAUDE.md: no number in the docs that a committed run did not produce."""
    text = DOC.read_text(encoding="utf-8")
    assert demo_tau_values() == {"0.30", "0.35"}
    for value in demo_tau_values():
        assert f"tau: {value}" in text


def test_the_band_real_answers_occupy_is_read_off_the_committed_replay() -> None:
    """Phase 13: the doc may name a band now, and every figure in it comes from this file."""
    results = json.loads(
        (REPO_ROOT / "examples/consilium/results/replay-unpriced.json").read_text(encoding="utf-8")
    )
    by_suite: dict[str, list[float]] = {}
    for case in results["cases"]:
        suite = Path(case["node_id"].split("::", 1)[0]).stem
        for result in case["results"]:
            if result["assertion_type"] == "similarity":
                by_suite.setdefault(suite, []).append(result["score"])
    assert set(by_suite) == {"test_baseline", "test_full"}

    text = DOC.read_text(encoding="utf-8")
    section = text.split("### What real answers score", 1)[1]
    for suite, scores in by_suite.items():
        row = next(line for line in section.splitlines() if line.startswith(f"| `{suite}`"))
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        assert cells[1] == str(len(scores)), suite
        assert cells[2] == f"{min(scores):.3f}", suite
        assert cells[3] == f"{max(scores):.3f}", suite
        assert cells[4] == f"{median(scores):.3f}", suite

    worst = min(min(scores) for scores in by_suite.values())
    assert f"the worst of them, {worst:.3f}," in " ".join(section.split())
    assert f"sits {worst - 0.30:.3f} above the floor" in " ".join(section.split())


def test_the_doc_recommends_no_general_tau_and_says_why() -> None:
    """05 §5 and CLAUDE.md: a band measured on one corpus is not a recommendation."""
    section = DOC.read_text(encoding="utf-8").split("### What real answers score", 1)[1]
    assert "a band and not a distribution" in " ".join(section.split())
    assert "Measure your own suite once" in " ".join(section.split())
    assert "0.30 to 0.40" not in section
