"""Phase 3: ``docs/assertions.md``'s trigram table is recomputed from the shipped backend.

No number appears in the documentation that a committed file did not produce (`CLAUDE.md`). This
test is that rule enforced for the one table in the docs that is a measurement: it parses the
markdown, recomputes every row with ``TrigramCosine`` and fails if the doc and the code disagree
at the three decimals the doc prints.
"""

from __future__ import annotations

from pathlib import Path

from probatio.assertions import TrigramCosine

DOC = Path(__file__).resolve().parents[1] / "docs" / "assertions.md"
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
