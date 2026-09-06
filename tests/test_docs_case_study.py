"""Phase 11: ``docs/CASE_STUDY.md`` quotes only what the committed dogfood artefacts hold.

`CLAUDE.md` says no number appears in a document that a committed run did not produce, and the
case study is the document with the most to gain from breaking that rule: it is the evidence for
the README's central claim. So every load-bearing part of §1 is re-derived here from the files it
names — `examples/consilium/CASES.txt`, the tapes under `examples/consilium/cassettes/`, and the
committed results file `examples/consilium/results/replay-unpriced.json` — and compared against
what the prose says. The document is read, never written: a disagreement is a failing test, and
fixing it means correcting the document or admitting the run changed.

Three things are checked.

**Every case id §1 names is a case the suite has.** An id that drifted, or one invented while
writing prose, names nothing and would be caught by no other test.

**Every verbatim answer §1.3 quotes is really the opening of that tape.** The quotations are the
part a reader cannot check without opening thirty JSON files, so they are the part most worth
pinning. All eight of them — six blockquoted, two in running prose — are openings, and a test
pins that count, so dropping one of the eight is caught. What the count cannot catch is a ninth
quotation written in some other form, since the parsers recognise the two forms the document uses
and not free prose. Comparison is on whitespace-normalised text, because a markdown blockquote
rewraps what the tape stores as one paragraph, and the quoted openings end in an ellipsis, which
is stripped before the prefix test.

**The pass and fail counts are the ones in the results file.** Both suite totals, the six
red-flag cases and the five of them that fail, and every verdict in §1.2's table — whose questions
are checked against the case files they say they came from while the row is open anyway.

Phase 13 generalises this into a provenance test over `docs/` as a whole; this module is the
first of its kind and is deliberately specific to one document.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Final

import yaml

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
DOC: Final = REPO_ROOT / "docs" / "CASE_STUDY.md"
SUITE: Final = REPO_ROOT / "examples" / "consilium"
CASES_TXT: Final = SUITE / "CASES.txt"
CASSETTES: Final = SUITE / "cassettes"
RESULTS: Final = SUITE / "results" / "replay-unpriced.json"

TEXT: Final = DOC.read_text(encoding="utf-8")

_CASE_ID: Final = re.compile(r"g-[a-z]{2}-\d{3}")
"""A Consilium golden id as the document writes it."""

_LABELLED_QUOTE: Final = re.compile(r'\*\*(full|baseline_llm):\*\*\s*"(.+?)"', re.S)
"""One labelled opening inside a §1.3 blockquote: which configuration, and what it said."""

_STATED_OPENING: Final = re.compile(r'its `(full|baseline_llm)` answer opens "(.+?)"', re.S)
"""One §1.3 opening quoted in running prose rather than in a blockquote."""

_TABLE_ROW: Final = re.compile(
    r'^\| `(g-[a-z]{2}-\d{3})` \| "(.+?)" \| (\*\*FAIL\*\*|pass) \| (\*\*FAIL\*\*|pass) \|$',
    re.M,
)
"""One row of §1.2's table: the case, its question, and its two verdicts."""

_SUITE_OF: Final = {"full": "test_full", "baseline_llm": "test_baseline"}
"""The name §1 gives a configuration, and the test module that replays it."""

_NUMBER_WORDS: Final = {"five": 5, "six": 6, "fifteen": 15}
"""The counts §1 spells out in words rather than in digits."""


def section(heading: str, next_heading: str) -> str:
    """Return the text between two headings, the first included and the second not.

    Args:
        heading: The heading the section starts at.
        next_heading: The heading the section ends before.

    Returns:
        That slice of the document.
    """
    start = TEXT.index(heading)
    return TEXT[start : TEXT.index(next_heading, start)]


SECTION_1: Final = section("## 1. Route A", "## 2. Route B")
SECTION_1_2: Final = section("### 1.2", "### 1.3")
SECTION_1_3: Final = section("### 1.3", "### 1.4")


def committed_ids() -> list[str]:
    """Return the fifteen case ids the suite replays, in ``CASES.txt`` order."""
    return CASES_TXT.read_text(encoding="utf-8").split()


def tape_text(configuration: str, case_id: str) -> str:
    """Return the answer one tape recorded.

    Args:
        configuration: ``full`` or ``baseline_llm``, as §1 names them.
        case_id: The case.

    Returns:
        The recorded text of that tape's first completion, which is the delivered answer.
    """
    path = CASSETTES / _SUITE_OF[configuration] / f"{case_id}.json"
    tape = json.loads(path.read_text(encoding="utf-8"))
    completions = tape["interactions"][0]["completions"]
    text: str = completions[0]["text"]
    return text


def normalise(text: str) -> str:
    """Collapse every run of whitespace to one space, so a rewrapped quotation still matches."""
    return " ".join(text.split())


def quoted_opening(quote: str) -> str:
    """Return a quoted opening with its trailing ellipsis removed, ready for a prefix test."""
    return normalise(quote).rstrip("…").rstrip()


def labelled_openings() -> list[tuple[str, str, str]]:
    """Return §1.3's blockquoted openings as ``(case_id, configuration, quotation)``.

    A blockquote follows the paragraph that names its case, so the case id is carried forward
    from the most recent paragraph that opens with one.

    Returns:
        Every labelled opening, in document order.
    """
    openings: list[tuple[str, str, str]] = []
    case_id = ""
    for block in SECTION_1_3.split("\n\n"):
        stripped = block.lstrip()
        if stripped.startswith("`g-"):
            case_id = _CASE_ID.findall(stripped)[0]
        if not stripped.startswith(">"):
            continue
        joined = " ".join(line.lstrip("> ").rstrip() for line in block.splitlines())
        for configuration, quote in _LABELLED_QUOTE.findall(joined):
            openings.append((case_id, configuration, quote))
    return openings


def stated_openings() -> list[tuple[str, str, str]]:
    """Return §1.3's prose openings as ``(case_id, configuration, quotation)``.

    A prose opening is attributed to the last case id named before it, which is how the paragraph
    reads: the sentence naming the case is the sentence that quotes it.

    Returns:
        Every opening quoted outside a blockquote, in document order.
    """
    openings: list[tuple[str, str, str]] = []
    for match in _STATED_OPENING.finditer(SECTION_1_3):
        preceding = _CASE_ID.findall(SECTION_1_3[: match.start()])
        assert preceding, "an opening quoted before any case is named"
        openings.append((preceding[-1], match.group(1), match.group(2)))
    return openings


def results() -> dict[str, object]:
    """Return the committed unpriced results file, parsed."""
    report: dict[str, object] = json.loads(RESULTS.read_text(encoding="utf-8"))
    return report


def cases_of(module_stem: str) -> list[dict[str, object]]:
    """Return the recorded cases of one test module, in the order they ran.

    Args:
        module_stem: ``test_full`` or ``test_baseline``.

    Returns:
        Every case whose node id names that module.
    """
    cases: list[dict[str, object]] = results()["cases"]  # type: ignore[assignment]
    return [case for case in cases if f"{module_stem}.py::" in str(case["node_id"])]


# -- the ids ---------------------------------------------------------------------------------


def test_every_case_id_section_1_names_is_a_case_the_suite_replays() -> None:
    """A quoted id that names no committed case is a claim about nothing."""
    named = sorted(set(_CASE_ID.findall(SECTION_1)))
    assert named, "section 1 names no case at all, so the parser is wrong, not the document"
    committed = set(committed_ids())
    assert set(named) <= committed, sorted(set(named) - committed)


def test_the_document_names_every_red_flag_case() -> None:
    """§1.2's table is the whole red-flag set, not a selection from it."""
    red_flag = {
        str(case["case_id"])
        for case in cases_of("test_full")
        if "red-flag" in case["tags"]  # type: ignore[operator]
    }
    assert {row[0] for row in _TABLE_ROW.findall(SECTION_1_2)} == red_flag


# -- the quotations --------------------------------------------------------------------------


def test_every_labelled_opening_in_1_3_really_opens_that_tape() -> None:
    """The six blockquoted openings, each a verbatim prefix of the answer it is attributed to."""
    openings = labelled_openings()
    assert len(openings) == 6, [(case_id, kind) for case_id, kind, _ in openings]
    for case_id, configuration, quote in openings:
        assert case_id in set(committed_ids()), case_id
        recorded = normalise(tape_text(configuration, case_id))
        assert recorded.startswith(quoted_opening(quote)), (case_id, configuration)


def test_every_opening_quoted_in_prose_opens_its_tape_too() -> None:
    """§1.3 says two answers *open* with a sentence; both do, and both belong to the named case."""
    openings = stated_openings()
    assert [case_id for case_id, _, _ in openings] == ["g-su-002", "g-md-018"], openings
    for case_id, configuration, quote in openings:
        recorded = normalise(tape_text(configuration, case_id))
        assert recorded.startswith(quoted_opening(quote)), (case_id, configuration)


def test_all_eight_quotations_are_openings_and_none_went_unchecked() -> None:
    """§1.3 quotes eight answers and every one is an opening, so every one is a prefix test.

    The count pins that none of the eight was dropped. It cannot see a ninth quotation written in
    some other form: the parsers recognise the blockquote and the ``answer opens`` sentence, which
    are the two forms the document uses, and not free prose.
    """
    assert len(labelled_openings()) == 6
    assert len(stated_openings()) == 2


# -- the counts ------------------------------------------------------------------------------


def test_the_suite_totals_are_the_ones_in_the_results_file() -> None:
    """§1.2's ``15 of 15`` and ``10 of 15``, re-counted from ``replay-unpriced.json``."""
    for module_stem, sentence in (
        ("test_baseline", r"`test_baseline` passes (\d+) of (\d+) cases"),
        ("test_full", r"`test_full` passes (\d+) of (\d+)"),
    ):
        match = re.search(sentence, SECTION_1_2)
        assert match is not None, module_stem
        passed, total = (int(value) for value in match.groups())
        cases = cases_of(module_stem)
        assert len(cases) == total, module_stem
        assert sum(1 for case in cases if case["passed"]) == passed, module_stem


def test_five_of_the_six_red_flag_cases_fail_under_full() -> None:
    """§1.2's ``five of the six red-flag cases fail``, re-counted the same way."""
    match = re.search(r"(\w+) of the six red-flag cases fail", SECTION_1_2)
    assert match is not None
    expected = _NUMBER_WORDS[match.group(1)]
    red_flag = [case for case in cases_of("test_full") if "red-flag" in case["tags"]]  # type: ignore[operator]
    assert len(red_flag) == 6
    assert sum(1 for case in red_flag if not case["passed"]) == expected


def test_section_1_1_counts_the_red_flag_cases_correctly() -> None:
    """§1.1's ``Six of the fifteen cases carry `red_flag: true```."""
    match = re.search(r"(\w+) of the (\w+) cases carry `red_flag: true`", SECTION_1)
    assert match is not None
    n_red_flag, n_cases = (_NUMBER_WORDS[word.lower()] for word in match.groups())
    cases = cases_of("test_full")
    assert len(cases) == n_cases == len(committed_ids())
    assert sum(1 for case in cases if "red-flag" in case["tags"]) == n_red_flag  # type: ignore[operator]


def test_every_verdict_in_the_1_2_table_is_the_recorded_verdict() -> None:
    """The table states thirty verdicts; each one is read back out of the results file."""
    rows = _TABLE_ROW.findall(SECTION_1_2)
    assert len(rows) == 6, rows
    verdicts = {
        (str(case["case_id"]), module_stem): bool(case["passed"])
        for module_stem in ("test_full", "test_baseline")
        for case in cases_of(module_stem)
    }
    for case_id, _, full, baseline in rows:
        assert verdicts[case_id, "test_full"] is (full == "pass"), (case_id, "full")
        assert verdicts[case_id, "test_baseline"] is (baseline == "pass"), (case_id, "baseline")


def test_every_question_in_the_1_2_table_is_the_case_the_suite_runs() -> None:
    """The table says its questions come from ``cases/<id>.yaml``; each one does, verbatim."""
    rows = _TABLE_ROW.findall(SECTION_1_2)
    assert len(rows) == 6
    for case_id, question, _, _ in rows:
        source = yaml.safe_load((SUITE / "cases" / f"{case_id}.yaml").read_text(encoding="utf-8"))
        assert normalise(str(source["input"])) == normalise(question), case_id


def test_the_one_red_flag_case_full_passes_is_named() -> None:
    """§1.2 names `g-md-017` as the exception; the results file agrees it is the only one."""
    passing = [
        str(case["case_id"])
        for case in cases_of("test_full")
        if "red-flag" in case["tags"] and case["passed"]  # type: ignore[operator]
    ]
    assert passing == ["g-md-017"]
    assert f"red-flag case `full` passes is `{passing[0]}`" in SECTION_1_2


# -- Phase 12: sections 3 and 4 -------------------------------------------------------------------

LIVE: Final = REPO_ROOT / "examples" / "consilium" / "live"
LIVE_RESULTS: Final = LIVE / "results" / "live-baseline.json"
SECTION_3: Final = section("## 3. What the relations", "## 4. Judge validation")
SECTION_4: Final = section("## 4. Judge validation", "## 5. Limitations")
SECTION_5: Final = TEXT[TEXT.index("## 5. Limitations") :]


def live_results() -> dict[str, Any]:
    """The live suite's committed replay, which every §3 number comes from."""
    return dict(json.loads(LIVE_RESULTS.read_text(encoding="utf-8")))


def table_rows(section_text: str, width: int) -> list[list[str]]:
    """Every markdown row of the given cell count, header and rule excluded."""
    rows = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) == width and set("".join(cells)) - set("-: "):
            rows.append(cells)
    return rows


def test_section_3_relation_table_is_the_live_replays_own_measurement() -> None:
    """Every cell of §3's table is read back out of live-baseline.json."""
    measured = {r["relation"]: r for r in live_results()["relations"]}
    rows = {
        cells[0].strip("`"): cells[1:]
        for cells in table_rows(SECTION_3, 7)
        if cells[0].startswith("`")
    }
    assert set(rows) == set(measured), (sorted(rows), sorted(measured))
    for name, cells in rows.items():
        item = measured[name]
        assert int(cells[0]) == item["n_cases"], name
        assert int(cells[1]) == item["n_not_applicable"], name
        assert cells[2] == f"{item['n_violations']}/{item['n_variants']}", name
        assert float(cells[3]) == round(item["mean_violation_rate"], 2), name
        assert cells[4].strip("`") == item["worst_case_id"], name
        assert float(cells[5]) == round(item["worst_violation_rate"], 2), name


def test_section_3_flip_arithmetic_matches_the_recorded_flips() -> None:
    """13 flips, 12 of them the judge, and no similarity or not_contains anywhere."""
    changed = [
        assertion
        for case in live_results()["cases"]
        for relation in case["relations"]
        for flip in relation["flips"]
        for assertion in flip["changed_assertions"]
    ]
    flat = " ".join(SECTION_3.split())
    assert int(re.search(r"There are (\d+) verdict flips", flat).group(1)) == len(changed)
    assert int(re.search(r"`judge` in (\d+) of them", flat).group(1)) == changed.count("judge")
    assert changed.count("contains") == 1
    assert not {"similarity", "not_contains"} & set(changed)


def test_section_3_names_the_only_case_that_flipped_on_a_non_judge_assertion() -> None:
    case = next(c for c in live_results()["cases"] if c["case_id"] == "g-md-018")
    flips = [f for r in case["relations"] for f in r["flips"]]
    assert len(flips) == 1 and flips[0]["changed_assertions"] == ["contains"]
    assert flips[0]["original_verdict"] is False and flips[0]["variant_verdict"] is True
    flat = " ".join(SECTION_3.split())
    assert "`g-md-018`" in flat and flips[0]["label"] in flat


def test_section_3_variant_deletion_count_is_what_the_frozen_files_hold() -> None:
    files = sorted((LIVE / "variants").glob("*.yaml"))
    held = sum(len(yaml.safe_load(f.read_text(encoding="utf-8"))["variants"]) for f in files)
    flat = " ".join(SECTION_3.split())
    deleted, asked = (int(n) for n in re.search(r"\*\*(\d+) of the (\d+)\*\*", flat).groups())
    assert asked == 3 * len(files)
    assert deleted == asked - held


def test_section_4_claude_rows_are_the_committed_record_and_the_progress_line() -> None:
    """Sample 1 from its validation record; sample 2 from PROGRESS.md, as §4 says."""
    record = json.loads(
        (LIVE / "results" / "judges-sample-1" / "faithfulness.validation.json").read_text(
            encoding="utf-8"
        )
    )
    rows = {
        (cells[0], cells[2]): cells
        for cells in table_rows(SECTION_4, 5)
        if cells[0].startswith("sample")
    }
    sample_1 = next(v for k, v in rows.items() if k[0] == "sample 1" and "claude" in k[1])
    assert int(sample_1[1]) == record["n"]
    assert float(sample_1[3]) == round(record["agreement"], 3)
    assert float(sample_1[4].strip("*")) == round(record["kappa"], 3)

    progress = (REPO_ROOT / "PROGRESS.md").read_text(encoding="utf-8")
    sample_2 = next(v for k, v in rows.items() if k[0] == "sample 2" and "claude" in k[1])
    assert f"agreement={sample_2[3]} kappa={sample_2[4].strip('*')}" in progress
    assert f"n={sample_2[1]} " in progress


def test_section_4_gpt_rows_agree_with_the_kappa_recomputed_from_the_committed_csvs() -> None:
    import csv

    from probatio.judge import cohens_kappa

    fixtures = REPO_ROOT / "tests" / "fixtures" / "consilium"
    rows = {
        (cells[0], cells[2]): cells
        for cells in table_rows(SECTION_4, 5)
        if cells[0].startswith("sample")
    }
    for sample, name in (
        ("sample 1", "judge-sample-labeled.csv"),
        ("sample 2", "judge-sample-2-labeled.csv"),
    ):
        with (fixtures / name).open(newline="", encoding="utf-8") as handle:
            labelled = list(csv.DictReader(handle))
        measured = cohens_kappa(
            [r["judge_label"] for r in labelled], [r["human_label"] for r in labelled]
        )
        cells = next(v for k, v in rows.items() if k[0] == sample and "GPT-4o-mini" in k[1])
        assert int(cells[1]) == measured.n, sample
        assert float(cells[3]) == round(measured.agreement, 3), sample
        assert float(cells[4]) == round(measured.kappa, 3), sample


def test_section_4_claim_that_no_sample_2_record_is_committed_is_true() -> None:
    assert "not committed" in SECTION_4
    assert not (REPO_ROOT / ".probatio" / "judges" / "faithfulness.validation.json").exists()


def test_section_4_unvalidated_warning_count_is_what_the_report_holds() -> None:
    """§4 says fifteen warnings; the committed report has to carry fifteen."""
    report = live_results()
    unvalidated = [w for w in report["warnings"] if "no validation record" in w]
    flat = " ".join(SECTION_4.split())
    stated = re.search(r"(\w+) `judge verdict\(s\) from a rubric with no validation", flat).group(1)
    assert {"fifteen": 15}[stated] == len(unvalidated)
    assert len(unvalidated) == len(report["cases"])


def test_section_5_variant_count_is_the_one_the_replay_measured() -> None:
    variants = sum(r["n_variants"] for r in live_results()["relations"])
    flat = " ".join(SECTION_5.split())
    assert int(re.search(r"(\d+) variants, evaluated once", flat).group(1)) == variants
