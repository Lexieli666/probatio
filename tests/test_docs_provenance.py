"""Phase 13: ``docs/PROVENANCE.md`` is the index of every number in the documentation.

`CLAUDE.md` forbids a figure in `README.md` or under `docs/` that a committed file did not
produce. The five older modules in this family each enforce that rule for one document. This one
enforces the rule *over the documents as a set*: it reads `docs/PROVENANCE.md`, runs each row's
check against the file the row names, asserts the figure really is printed in every document the
row claims, and then sweeps `README.md` for any numeral that neither table accounts for.

The sweep is the half that cannot be satisfied by writing more prose. A number added to the README
fails the suite until somebody names the file it came from.
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
from pathlib import Path
from statistics import median
from typing import Any, Final

import pytest

from probatio.judge import cohens_kappa
from probatio.stability import wilson_interval

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
DOC: Final = REPO_ROOT / "docs" / "PROVENANCE.md"
TEXT: Final = DOC.read_text(encoding="utf-8")

NUMERAL: Final = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?")


def rows(heading: str) -> list[list[str]]:
    """The cells of every body row of the markdown table under ``heading``."""
    section = TEXT.split(f"## {heading}", 1)[1].split("\n## ", 1)[0]
    parsed = []
    for line in section.splitlines():
        if not line.startswith("| `") and not line.startswith("| [`"):
            continue
        parsed.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return parsed


MEASUREMENTS: Final = rows("Measurements")
NOT_MEASUREMENTS: Final = rows("Numerals that are not measurements")
GUARDS: Final = rows("Which test guards which document")


def unticked(cell: str) -> str:
    return cell.strip().strip("`")


def prose(path: Path) -> str:
    """A document's text with emphasis markers removed, as the table's `number` column reads it."""
    return path.read_text(encoding="utf-8").replace("**", "")


def json_at(source: Path, path: str) -> float:
    value: Any = json.loads(source.read_text(encoding="utf-8"))
    for key in path.split("."):
        value = value[key]
    return float(value)


def decimals(number: str) -> int:
    return len(number.split(".")[1]) if "." in number else 0


def similarity_scores(results: Path) -> dict[str, list[float]]:
    data = json.loads(results.read_text(encoding="utf-8"))
    scores: dict[str, list[float]] = {}
    for case in data["cases"]:
        suite = Path(case["node_id"].split("::", 1)[0]).stem
        for result in case["results"]:
            if result["assertion_type"] == "similarity":
                scores.setdefault(suite, []).append(float(result["score"]))
    return scores


def csv_kappa(path: Path) -> float:
    with path.open(encoding="utf-8", newline="") as handle:
        table = list(csv.DictReader(handle))
    return cohens_kappa(
        [row["judge_label"] for row in table], [row["human_label"] for row in table]
    ).kappa


def run_check(number: str, source: Path, check: str) -> None:
    """Assert ``number`` is what ``source`` holds, by whichever derivation ``check`` names."""
    bare = number.lstrip("$")
    kind, _, argument = check.partition(" ")

    if kind == "text":
        assert bare in source.read_text(encoding="utf-8"), f"{number} is not in {source}"
        return

    if kind == "json":
        assert f"{json_at(source, unticked(argument)):.{decimals(bare)}f}" == bare
        return

    if kind == "json-of":
        numerator, denominator = argument.split()
        left, right = json_at(source, numerator), json_at(source, denominator)
        assert f"{int(left)} of {int(right)}" == number
        return

    if kind == "json-difference":
        payload = json.loads(source.read_text(encoding="utf-8"))
        answered = max(entry["costUSD"] for entry in payload["modelUsage"].values())
        assert f"{float(payload['total_cost_usd']) - answered:.{decimals(bare)}f}" == bare
        return

    if kind == "wilson":
        k = int(argument)
        assert f"{wilson_interval(k, k)[0]:.{decimals(bare)}f}" == bare
        return

    if kind == "similarity":
        suite, statistic = argument.split()
        scores = similarity_scores(source)[suite]
        computed = {"min": min, "max": max, "median": median}[statistic](scores)
        assert f"{computed:.{decimals(bare)}f}" == bare
        return

    if kind == "similarity-headroom":
        tau = float(argument)
        worst = min(score for scores in similarity_scores(source).values() for score in scores)
        assert f"{worst - tau:.{decimals(bare)}f}" == bare
        return

    if kind == "kappa":
        assert f"{csv_kappa(source):.{decimals(bare)}f}" == bare
        return

    if kind == "length":
        assert str(len(source.read_text(encoding="utf-8"))) == bare
        return

    if kind == "json-error-column":
        with pytest.raises(json.JSONDecodeError) as raised:
            json.loads(source.read_text(encoding="utf-8"))
        assert f"column {raised.value.colno}" == number
        return

    if kind == "verdicts-moved":
        baseline = source.with_name("live-baseline.json")
        moved = [
            case["case_id"]
            for case, other in zip(
                json.loads(source.read_text(encoding="utf-8"))["cases"],
                json.loads(baseline.read_text(encoding="utf-8"))["cases"],
                strict=True,
            )
            if all(r["passed"] for r in case["results"])
            != all(r["passed"] for r in other["results"])
        ]
        total = len(json.loads(source.read_text(encoding="utf-8"))["cases"])
        assert f"{len(moved)} of {total}" == number
        return

    if kind == "judge-failures":
        cases = json.loads(source.read_text(encoding="utf-8"))["cases"]
        failed = [
            case
            for case in cases
            if any(r["assertion_type"] == "judge" and not r["passed"] for r in case["results"])
        ]
        assert f"{len(failed)} of {len(cases)}" == number
        return

    if kind == "variants-deleted":
        import yaml

        kept = deleted = 0
        for path in sorted(source.glob("*.yaml")):
            frozen = yaml.safe_load(path.read_text(encoding="utf-8"))
            kept += len(frozen["variants"])
            deleted += path.read_text(encoding="utf-8").count("# deleted after review")
        asked = kept + deleted
        assert number in (f"{deleted} of {asked}", f"{deleted} of the {asked}")
        return

    if kind == "interactions":
        total = sum(
            len(json.loads(path.read_text(encoding="utf-8"))["interactions"])
            for path in sorted(source.glob("*.json"))
        )
        assert str(total) == bare
        return

    raise AssertionError(f"docs/PROVENANCE.md names a check this test cannot run: {check!r}")


def test_the_measurements_table_is_not_empty_and_has_five_columns() -> None:
    assert len(MEASUREMENTS) >= 40
    assert {len(row) for row in MEASUREMENTS} == {5}


@pytest.mark.parametrize("row", MEASUREMENTS, ids=lambda row: unticked(row[0]))
def test_every_measurement_is_what_its_source_file_holds(row: list[str]) -> None:
    number, _, source, check, _ = row
    run_check(unticked(number), REPO_ROOT / unticked(source), check)


@pytest.mark.parametrize("row", MEASUREMENTS, ids=lambda row: unticked(row[0]))
def test_every_measurement_is_printed_by_every_document_the_row_names(row: list[str]) -> None:
    number, documents, *_ = row
    for name in documents.split(","):
        document = REPO_ROOT / unticked(name)
        assert document.is_file(), f"docs/PROVENANCE.md names a document that is gone: {name}"
        assert unticked(number) in prose(document), f"{number} is not printed in {name}"


@pytest.mark.parametrize("row", MEASUREMENTS, ids=lambda row: unticked(row[0]))
def test_every_source_file_a_row_names_is_committed(row: list[str]) -> None:
    """ "A committed file behind it" is the rule; an untracked file is not one."""
    source = unticked(row[2])
    completed = subprocess.run(
        ["git", "ls-files", "--error-unmatch", source],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if "not a git repository" in completed.stderr:  # pragma: no cover - checkout without git
        return
    assert completed.returncode == 0, f"{source} is named as provenance but is not committed"


def accounted_for() -> list[str]:
    """Every literal string the two tables let a numeral hide inside, longest first."""
    literals = [unticked(row[0]) for row in MEASUREMENTS]
    literals += [
        unticked(row[0]) for row in NOT_MEASUREMENTS if not unticked(row[0]).startswith("re:")
    ]
    return sorted(literals, key=len, reverse=True)


def patterns() -> list[str]:
    return [
        unticked(row[0]).removeprefix("re:")
        for row in NOT_MEASUREMENTS
        if unticked(row[0]).startswith("re:")
    ]


def readme_prose() -> str:
    """`README.md` without its fenced blocks: those are quoted runs, checked separately."""
    kept, fenced = [], False
    for line in (REPO_ROOT / "README.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            kept.append(line)
    return "\n".join(kept).replace("**", "")


def test_every_numeral_in_the_readme_is_accounted_for_by_one_of_the_two_tables() -> None:
    """The sweep. A number added to the README fails until its row names the file it came from."""
    remaining = readme_prose()
    for pattern in patterns():
        remaining = re.sub(pattern, " ", remaining)
    for literal in accounted_for():
        remaining = remaining.replace(literal, " ")
    stray = sorted({match.group(0) for match in NUMERAL.finditer(remaining)})
    assert not stray, f"README.md prints numerals docs/PROVENANCE.md does not account for: {stray}"


def unlabelled_blocks(markdown: str) -> list[str]:
    """The fenced blocks opened with a bare ``` — the quoted terminal output, not the samples."""
    blocks, body, fence = [], [], None
    for line in markdown.splitlines():
        if line.startswith("```"):
            if fence is None:
                fence, body = line[3:].strip(), []
            else:
                if fence == "":
                    blocks.append("\n".join(body))
                fence = None
            continue
        if fence is not None:
            body.append(line)
    return blocks


def test_the_readme_quotes_the_committed_run_and_nothing_else() -> None:
    """Every unlabelled fenced block in the README is a substring of the run in PROGRESS.md."""
    progress = (REPO_ROOT / "PROGRESS.md").read_text(encoding="utf-8")
    block = progress.split("pytest examples/demo_suite --runs 5", 1)[1].split("```", 2)[1]
    run = "\n".join(line.removeprefix("  ") for line in block.splitlines())
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    quoted = unlabelled_blocks(readme)
    assert len(quoted) == 4
    for excerpt in quoted:
        assert excerpt.rstrip("\n") in run, excerpt.splitlines()[0]


def test_the_readme_names_the_commit_the_run_it_quotes_came_from() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "run at commit `4c2114e`" in readme
    completed = subprocess.run(
        ["git", "cat-file", "-t", "4c2114e"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:  # pragma: no cover - checkout without full history
        return
    assert completed.stdout.strip() == "commit"


def test_the_quick_start_is_copied_from_the_frozen_demo_suite() -> None:
    """Spec §7 asks for a quick start "taken from examples/demo_suite/ so it is real"."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    demo = REPO_ROOT / "examples" / "demo_suite"
    case = (demo / "cases" / "06-copd-spirometry.yaml").read_text(encoding="utf-8")
    test = (demo / "test_demo.py").read_text(encoding="utf-8")
    for line in ("id: copd-spirometry", "assertions:", '  - {type: contains, any: ["spirometry"]}'):
        assert line in case and line in readme, line
    for line in (
        'CASES = load_cases(HERE / "cases")',
        '@format_jitter(field="input.question")',
        "def test_case(case, probatio, provider):",
        "    probatio.check(case, sut=lambda c: answer(c, provider))",
    ):
        assert line in test and line in readme, line
    assert "Every\nline above is verbatim from it except one" in readme


def test_every_document_that_prints_a_number_names_the_test_that_guards_it() -> None:
    guarded = {unticked(row[0]) for row in GUARDS}
    for row in GUARDS:
        document, test = unticked(row[0]), unticked(row[1])
        assert (REPO_ROOT / document).is_file(), document
        assert (REPO_ROOT / test).is_file(), test
    documented = {"README.md"} | {f"docs/{path.name}" for path in (REPO_ROOT / "docs").glob("*.md")}
    assert documented == guarded, documented ^ guarded


def test_design_md_repeats_only_figures_the_measurements_table_carries() -> None:
    """`docs/DESIGN.md` has no test of its own, so its quoted figures are checked here."""
    listed = {unticked(row[0]) for row in MEASUREMENTS}
    design = prose(REPO_ROOT / "docs" / "DESIGN.md")
    quoted = {match.group(0) for match in re.finditer(r"\b0\.\d{3}\b", design)}
    assert quoted <= listed, quoted - listed


def test_the_case_study_section_links_the_repository_the_dogfood_suite_names() -> None:
    """The URL is the one `examples/consilium/README.md` already gives, not a second guess."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    suite = (REPO_ROOT / "examples" / "consilium" / "README.md").read_text(encoding="utf-8")
    url = re.search(r"\[Consilium-Health\]\((https://[^)]+)\)", suite).group(1)
    assert f"[Consilium-Health]({url})" in readme


def test_the_case_study_section_points_at_what_dogfooding_found_about_probatio() -> None:
    """The three defects are a finding about the tool, so the case study has to name them."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("## Case study", 1)[1].split("\n## ", 1)[0]
    assert "three things wrong with Probatio itself" in section
    assert "docs/EVALUATION.md) §7" in section

    evaluation = (REPO_ROOT / "docs" / "EVALUATION.md").read_text(encoding="utf-8")
    seven = evaluation.split("## 7. What dogfooding found about Probatio itself", 1)[1]
    listed = [line for line in seven.splitlines() if line.startswith("| DECISIONS ")]
    assert len(listed) == 3, listed
    kinds = [line.strip("|").split("|")[2].strip() for line in listed]
    assert kinds.count("defect") == 2 and kinds.count("gap") == 1


def test_the_quick_starts_not_applicable_claim_is_true_of_the_case_it_shows() -> None:
    """`format_jitter(field="input.question")` on the shown case: not applicable, never `0.00`."""
    from probatio import load_cases
    from probatio.metamorphic import FormatJitter

    cases = {case.id: case for case in load_cases(REPO_ROOT / "examples" / "demo_suite" / "cases")}
    shown, named = cases["copd-spirometry"], cases["htn-definition"]
    relation = FormatJitter(field="input.question")

    assert isinstance(shown.input, str)
    assert relation.applicable(shown) is False

    assert isinstance(named.input, dict)
    assert set(named.input) >= {"question", "documents"}
    assert isinstance(named.input["documents"], list)
    assert relation.applicable(named) is True


def test_the_quick_start_names_the_two_case_files_it_talks_about() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    demo = REPO_ROOT / "examples" / "demo_suite" / "cases"
    for name in ("06-copd-spirometry.yaml", "01-htn-definition.yaml"):
        assert (demo / name).is_file(), name
        assert f"examples/demo_suite/cases/{name}" in readme, name
    assert "reports **not applicable** on it rather than `0.00`" in readme
