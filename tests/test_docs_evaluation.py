"""Phase 12: ``docs/EVALUATION.md`` quotes only what the committed artefacts hold.

`CLAUDE.md` forbids a number in a document that a committed run did not produce, and this document
is almost entirely numbers. Every figure it states is re-derived here from the file it names —
the live suite's results JSON, the frozen variants, the sample-1 validation record, the priced
offline replay, and `PROGRESS.md` for the one measurement whose record was deliberately not
committed — and compared with what the prose says.

The counts are parsed out of the prose rather than hard-coded, so a number edited in the document
without a run behind it fails, which a hard-coded expectation would not catch.

What this module cannot reach, and says so rather than pretending: the four figures attributed to
Consilium-Health's own repository. Two of them — the GPT-4o-mini kappas — are nonetheless checked,
because `tests/test_judge_kappa.py` recomputes them from the label CSVs committed under
`tests/fixtures/`, so this module asserts the document agrees with that recomputation. The two
published per-turn costs are quoted from a file outside this repository and are labelled as such
in the document.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final

import yaml

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
DOC: Final = REPO_ROOT / "docs" / "EVALUATION.md"
PROGRESS: Final = REPO_ROOT / "PROGRESS.md"
LIVE: Final = REPO_ROOT / "examples" / "consilium" / "live"
LIVE_RESULTS: Final = LIVE / "results" / "live-baseline.json"
SAMPLE_1_RECORD: Final = LIVE / "results" / "judges-sample-1" / "faithfulness.validation.json"
PRICED: Final = REPO_ROOT / "examples" / "consilium" / "results" / "replay-priced.json"
CASSETTES: Final = LIVE / "cassettes" / "test_live"

TEXT: Final = DOC.read_text(encoding="utf-8")


def section(heading: str, next_heading: str) -> str:
    """The text between two headings, so a claim is checked in the section that makes it."""
    start = TEXT.index(heading)
    return TEXT[start : TEXT.index(next_heading, start + len(heading))]


SECTION_1: Final = section("## 1. The model", "## 2. What the metamorphic")
SECTION_2: Final = section("## 2. What the metamorphic", "## 3. The frozen")
SECTION_3: Final = section("## 3. The frozen", "## 4. Judge validation")
SECTION_4: Final = section("## 4. Judge validation", "## 5. Provider reliability")
SECTION_5: Final = section("## 5. Provider reliability", "## 6. Cost cross-check")
SECTION_6: Final = TEXT[TEXT.index("## 6. Cost cross-check") :]


def results() -> dict[str, object]:
    """The live suite's committed replay."""
    return dict(json.loads(LIVE_RESULTS.read_text(encoding="utf-8")))


def relation_rows() -> dict[str, tuple[str, ...]]:
    """§2's relation table, keyed by relation name."""
    rows: dict[str, tuple[str, ...]] = {}
    for line in SECTION_2.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 7 and cells[0].startswith("`") and cells[0].endswith("`"):
            rows[cells[0].strip("`")] = tuple(cells[1:])
    return rows


# -- section 1: the model and the call count ------------------------------------------------------


def test_the_model_the_document_names_is_the_model_every_tape_recorded() -> None:
    """One model answers everything, and the tapes say which."""
    assert "`claude-opus-5`" in SECTION_1
    assert "`claude-haiku-4-5-20251001`" in SECTION_1
    models = {
        json.loads(path.read_text(encoding="utf-8"))["model"] for path in CASSETTES.glob("*.json")
    }
    assert models == {"claude-opus-5"}, models


def test_the_call_count_is_the_number_of_recorded_interactions() -> None:
    """278 calls is not an estimate: it is what the fifteen tapes hold."""
    stated_calls = int(re.search(r"Recording cost (\d+) live calls", SECTION_1).group(1))
    stated_variants = int(re.search(r"its (\d+) relation variants", SECTION_1).group(1))
    recorded = sum(
        len(json.loads(path.read_text(encoding="utf-8"))["interactions"])
        for path in CASSETTES.glob("*.json")
    )
    assert stated_calls == recorded
    report = results()
    variants = sum(int(r["n_variants"]) for r in report["relations"])  # type: ignore[index,call-overload]
    assert stated_variants == variants
    assert stated_calls == 2 * (len(report["cases"]) + variants)  # type: ignore[arg-type]


# -- section 2: the relation table ----------------------------------------------------------------


def test_every_row_of_the_relation_table_is_the_recorded_measurement() -> None:
    """Cases, not-applicable count, violations, mean rate, worst case and worst rate."""
    rows = relation_rows()
    report = results()
    measured = {str(r["relation"]): r for r in report["relations"]}  # type: ignore[index,union-attr]
    assert set(rows) == set(measured), (sorted(rows), sorted(measured))
    for name, cells in rows.items():
        item = measured[name]
        cases, not_applicable, violations, mean_rate, worst_case, worst_rate = cells
        assert int(cases) == item["n_cases"], name
        assert int(not_applicable) == item["n_not_applicable"], name
        assert violations == f"{item['n_violations']}/{item['n_variants']}", name
        assert float(mean_rate) == round(float(item["mean_violation_rate"]), 2), name
        assert worst_case.strip("`") == item["worst_case_id"], name
        assert float(worst_rate) == round(float(item["worst_violation_rate"]), 2), name


def test_the_flip_counts_and_which_assertions_moved_are_the_recorded_ones() -> None:
    """Twelve of thirteen flips are the judge, and no similarity or not_contains flipped."""
    changed = [
        assertion
        for case in results()["cases"]  # type: ignore[union-attr]
        for relation in case["relations"]
        for flip in relation["flips"]
        for assertion in flip["changed_assertions"]
    ]
    flat = " ".join(SECTION_2.split())
    total = int(re.search(r"there are (\d+) verdict flips", flat).group(1))
    judge = int(re.search(r"`judge` in (\d+) of them", flat).group(1))
    assert total == len(changed)
    assert judge == changed.count("judge")
    assert changed.count("contains") == 1
    assert "similarity" not in changed and "not_contains" not in changed


def test_the_order_invariant_null_result_is_stated_as_not_applicable() -> None:
    """Nine single-document cases: `None`, never `0.0` (DECISIONS 8)."""
    order = next(r for r in results()["relations"] if r["relation"] == "order_invariant")  # type: ignore[union-attr,index]
    words = {"Nine": 9, "Eight": 8, "Ten": 10, "Seven": 7}
    flat = " ".join(SECTION_2.split())
    stated = words[re.search(r"(\w+) of the fifteen cases carry a single document", flat).group(1)]
    assert stated == order["n_not_applicable"]
    single = [
        case_id
        for case_id in sorted(p.stem for p in (LIVE / "cases").glob("*.yaml"))
        if len(
            yaml.safe_load((LIVE / "cases" / f"{case_id}.yaml").read_text())["input"]["documents"]
        )
        == 1
    ]
    assert len(single) == order["n_not_applicable"]


def test_the_case_named_as_the_non_judge_flip_really_flipped_that_way() -> None:
    """`g-md-018` fails as recorded and passes with a distractor appended."""
    case = next(c for c in results()["cases"] if c["case_id"] == "g-md-018")  # type: ignore[union-attr,index]
    assert case["verdict"] is False
    flips = [f for r in case["relations"] for f in r["flips"]]
    assert len(flips) == 1
    assert flips[0]["label"] == "distractor-end-1"
    assert flips[0]["original_verdict"] is False and flips[0]["variant_verdict"] is True
    assert flips[0]["changed_assertions"] == ["contains"]
    assert "`g-md-018`" in SECTION_2 and "distractor-end-1" in SECTION_2


# -- section 3: the frozen paraphrases ------------------------------------------------------------


def test_the_number_of_variants_deleted_at_review_is_what_the_files_hold() -> None:
    """45 were asked for, 43 stand, and each deletion is noted in its file's header."""
    deleted, asked = (
        int(n) for n in re.search(r"\*\*(\d+) of (\d+) variants were deleted", SECTION_3).groups()
    )
    kept = int(re.search(r"\*\*\s*(\d+) stand", SECTION_3.replace("\n", " ")).group(1))
    files = sorted((LIVE / "variants").glob("*.yaml"))
    held = sum(len(yaml.safe_load(f.read_text(encoding="utf-8"))["variants"]) for f in files)
    assert asked == 3 * len(files)
    assert kept == held
    assert deleted == asked - held

    noted = [f for f in files if "# deleted after review" in f.read_text(encoding="utf-8")]
    assert len(noted) == deleted
    for path in noted:
        assert f"`{path.stem}`" in SECTION_3, path.stem


# -- section 4: the two kappas --------------------------------------------------------------------


def test_the_sample_1_row_is_the_committed_validation_record() -> None:
    record = json.loads(SAMPLE_1_RECORD.read_text(encoding="utf-8"))
    row = next(
        line for line in SECTION_4.splitlines() if "| sample 1 |" in line and "claude" in line
    )
    cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
    assert int(cells[1]) == record["n"]
    assert float(cells[3]) == round(record["agreement"], 3)
    assert float(cells[4].strip("*")) == round(record["kappa"], 3)
    assert int(cells[5]) == record["rows_reasked"]
    assert record["judge_model"] == "claude-opus-5"
    assert "judges-sample-1/faithfulness.validation.json" in cells[6]


def test_the_sample_2_numbers_come_from_the_progress_line_and_no_record_is_committed() -> None:
    """The one measurement whose record was deliberately not committed (DECISIONS 93)."""
    progress = PROGRESS.read_text(encoding="utf-8")
    assert "agreement=0.675 kappa=0.253" in progress
    assert "5 of 40 row(s) were asked again" in progress

    row = next(
        line for line in SECTION_4.splitlines() if "| sample 2 |" in line and "claude" in line
    )
    cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
    assert int(cells[1]) == 40
    assert float(cells[3]) == 0.675
    assert float(cells[4].strip("*")) == 0.253
    assert int(cells[5]) == 5
    assert "not committed" in cells[6]

    assert not (REPO_ROOT / ".probatio" / "judges" / "faithfulness.validation.json").exists(), (
        "the document says no sample-2 record is committed; one is"
    )


def test_the_gpt4o_mini_rows_agree_with_the_kappa_this_repository_recomputes() -> None:
    """Quoted from Consilium, but recomputed here from the committed CSVs."""
    from probatio.judge import cohens_kappa

    fixtures = Path(__file__).resolve().parent / "fixtures" / "consilium"
    import csv

    for name, sample in (
        ("judge-sample-labeled.csv", "sample 1"),
        ("judge-sample-2-labeled.csv", "sample 2"),
    ):
        with (fixtures / name).open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        measured = cohens_kappa([r["judge_label"] for r in rows], [r["human_label"] for r in rows])
        line = next(
            line
            for line in SECTION_4.splitlines()
            if f"| {sample} |" in line and "GPT-4o-mini" in line
        )
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        assert int(cells[1]) == measured.n, sample
        assert float(cells[3]) == round(measured.agreement, 3), sample
        assert float(cells[4]) == round(measured.kappa, 3), sample


def test_the_reversal_the_section_leads_with_is_real() -> None:
    """The headline claim: the two judges rank the two samples in opposite orders."""
    claude = {"sample 1": 0.600, "sample 2": 0.253}
    gpt = {"sample 1": 0.350, "sample 2": 0.592}
    assert (claude["sample 1"] > claude["sample 2"]) is not (gpt["sample 1"] > gpt["sample 2"])
    assert "opposite orders" in SECTION_4
    for value in ("0.600", "0.253", "0.350", "0.592"):
        assert value in SECTION_4, value


# -- section 5: provider reliability --------------------------------------------------------------


def test_the_attempt_table_totals_agree_with_its_own_prose() -> None:
    """Six attempts, one completed, and the completed one is the kappa section's."""
    attempts = [line for line in SECTION_5.splitlines() if re.match(r"^\| \d+ \|", line.strip())]
    stated = re.search(r"attempted \*\*(\w+) times and completed (\w+)\*\*", SECTION_5)
    assert stated.group(1) == "six" and len(attempts) == 6
    assert stated.group(2) == "once"
    completed = [line for line in attempts if "**completed**" in line]
    assert len(completed) == 1
    assert "0.253" in completed[0] and "5 of 40" in completed[0]


def test_the_re_ask_bound_the_document_states_is_the_one_in_the_code() -> None:
    from probatio.cli import JUDGE_ATTEMPTS

    stated = int(re.search(r"`cli\.JUDGE_ATTEMPTS = (\d+)`", SECTION_5).group(1))
    assert stated == JUDGE_ATTEMPTS


def test_the_captured_truncated_reply_the_section_cites_is_committed_and_still_fails() -> None:
    fixture = Path(__file__).resolve().parent / "fixtures" / "claude_cli_truncated_judge_reply.txt"
    assert "claude_cli_truncated_judge_reply.txt" in SECTION_5
    stated = int(re.search(r"`colno == (\d+)`", SECTION_5).group(1))
    with __import__("pytest").raises(json.JSONDecodeError) as excinfo:
        json.loads(fixture.read_text(encoding="utf-8"))
    assert excinfo.value.colno == stated


# -- section 6: the cost cross-check ---------------------------------------------------------------


def test_the_per_suite_means_are_computed_from_the_priced_replay() -> None:
    """Both means, and the total, come out of the committed priced run."""
    report = json.loads(PRICED.read_text(encoding="utf-8"))
    per_suite: dict[str, list[float]] = {}
    for case in report["cases"]:
        per_suite.setdefault(case["suite"], []).append(float(case["cost_usd"]))

    for suite, label in (("test_baseline", "`baseline_llm`"), ("test_full", "`full`")):
        values = per_suite[suite]
        assert len(values) == 15
        mean = sum(values) / len(values)
        row = next(line for line in SECTION_6.splitlines() if line.startswith(f"| {label} |"))
        stated = float(row.split("|")[2].strip().lstrip("$"))
        assert stated == round(mean, 6), (suite, stated, mean)

    total = float(re.search(r"is \*\*\$([0-9.]+)\*\*", SECTION_6).group(1))
    assert total == round(float(report["cost_total_usd"]), 6)


def test_the_token_ratio_the_section_uses_to_explain_the_gap_is_the_tapes_own() -> None:
    """The claim is that the gap is the subset, and the tokens have to show it."""
    stated_tokens = int(
        re.search(r"average \*\*([\d,]+) tokens per turn\*\*", SECTION_6).group(1).replace(",", "")
    )
    cassettes = REPO_ROOT / "examples" / "consilium" / "cassettes" / "test_full"
    totals = []
    for path in sorted(cassettes.glob("*.json")):
        completion = json.loads(path.read_text(encoding="utf-8"))["interactions"][0]["completions"][
            0
        ]
        totals.append(int(completion["tokens_in"]) + int(completion["tokens_out"]))
    assert len(totals) == 15
    assert stated_tokens == round(sum(totals) / len(totals))

    published = int(
        re.search(r"the \*\*([\d,]+)\*\*\nConsilium published", SECTION_6).group(1).replace(",", "")
    )
    token_ratio = round(100 * stated_tokens / published)
    cost_ratio = int(re.search(r"is (\d+)% of the published figure", SECTION_6).group(1))
    stated_token_ratio = int(re.search(r"which is (\d+)%", SECTION_6).group(1))
    assert stated_token_ratio == token_ratio
    assert abs(cost_ratio - token_ratio) <= 2, (
        "the section's whole argument is that the two ratios track each other"
    )


def test_the_live_suites_notional_total_is_the_one_the_replay_reports() -> None:
    stated = float(re.search(r"live suite's `\$([0-9.]+)`", SECTION_6).group(1))
    assert stated == round(float(results()["cost_total_usd"]), 6)  # type: ignore[arg-type]
