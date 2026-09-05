"""Phase 5: baselines — recording, drift, and the two modes a case can ask for (spec §3.6)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from probatio import AssertionResult, LLMCase, ProbatioConfigError, load_cases
from probatio.runner import evaluate_case
from probatio.snapshot import (
    DIFF_MAX_LINES,
    SCORE_TOLERANCE,
    UPDATE_COMMAND,
    Baseline,
    BaselineAssertion,
    BaselineStore,
    SnapshotResult,
    default_baseline_dir,
    prompt_hash,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO = REPO_ROOT / "examples" / "demo_suite"

FIXED = datetime(2026, 9, 3, 18, 0, 0, tzinfo=UTC)
SUITE = "test_demo"
MODEL = "fake-1"

# The four assertions of the demo suite's first `snapshot: scores` case, all passing.
PASSING = (
    ("contains", True, 1.0),
    ("not_contains", True, 1.0),
    ("similarity", True, 0.40),
    ("judge", True, 1.0),
)


def store(tmp_path: Path, *, clock: datetime = FIXED) -> BaselineStore:
    return BaselineStore(tmp_path / "baseline", clock=lambda: clock, root=tmp_path)


def results(*specs: tuple[str, bool, float | None]) -> list[AssertionResult]:
    return [
        AssertionResult(assertion_type=kind, passed=passed, score=score, detail="")
        for kind, passed, score in specs
    ]


@pytest.fixture(scope="session")
def demo_case() -> LLMCase:
    """The demo suite's first `snapshot: scores` case, read from the frozen example."""
    case = next(c for c in load_cases(DEMO / "cases") if c.id == "htn-definition")
    assert case.snapshot == "scores"
    return case


def compare(
    baseline_store: BaselineStore,
    case: LLMCase,
    *specs: tuple[str, bool, float | None],
    output: str = "an answer",
    digest: str | None = None,
    update: bool = False,
) -> SnapshotResult:
    result = baseline_store.compare(
        suite=SUITE,
        case=case,
        prompt_hash=digest if digest is not None else prompt_hash(case),
        results=results(*(specs or PASSING)),
        output=output,
        model=MODEL,
        update=update,
    )
    assert result is not None
    return result


# --------------------------------------------------------------------------- prompt identity


def test_prompt_hash_covers_the_prompt_and_nothing_else(demo_case: LLMCase) -> None:
    """Input, system and params identify a baseline; assertions and tags do not."""
    original = prompt_hash(demo_case)
    assert prompt_hash(demo_case.model_copy(update={"tags": ["other"]})) == original
    assert prompt_hash(demo_case.model_copy(update={"snapshot": "output"})) == original
    assert prompt_hash(demo_case.model_copy(update={"assertions": demo_case.assertions[:1]})) == (
        original
    )
    assert prompt_hash(demo_case.model_copy(update={"system": "Answer freely."})) != original
    assert prompt_hash(demo_case.model_copy(update={"params": {"temperature": 1}})) != original
    assert prompt_hash(demo_case.model_copy(update={"input": "a bare string"})) != original


def test_the_default_baseline_directory_is_the_one_spec_5_names() -> None:
    """Phase 9's plugin overrides it; the default is rootdir-relative under a plain pytest."""
    assert default_baseline_dir() == Path.cwd() / ".probatio" / "baseline"


# --------------------------------------------------------------------------- recording


def test_a_first_evaluation_records_a_baseline(tmp_path: Path, demo_case: LLMCase) -> None:
    """No baseline is not a failure: it is recorded, and the run says so (spec §3.6)."""
    baselines = store(tmp_path)
    result = compare(baselines, demo_case)

    assert result.state == "recorded"
    assert result.passed
    assert result.mode == "scores"
    assert result.case_id == "htn-definition"
    assert "baseline recorded" in result.detail

    path = tmp_path / "baseline" / SUITE / "htn-definition.json"
    assert result.path == f"baseline/{SUITE}/htn-definition.json"
    assert json.loads(path.read_text()) == {
        "case_id": "htn-definition",
        "prompt_hash": prompt_hash(demo_case),
        "mode": "scores",
        "output": None,
        "assertions": [
            {"assertion_type": "contains", "passed": True, "score": 1.0},
            {"assertion_type": "not_contains", "passed": True, "score": 1.0},
            {"assertion_type": "similarity", "passed": True, "score": 0.4},
            {"assertion_type": "judge", "passed": True, "score": 1.0},
        ],
        "recorded": "2026-09-03T18:00:00Z",
        "model": MODEL,
    }


def test_two_recordings_of_the_same_results_are_byte_identical(
    tmp_path: Path, demo_case: LLMCase
) -> None:
    """A baseline that did not move produces no diff in the user's repository."""
    first = (tmp_path / "a" / compare(store(tmp_path / "a"), demo_case).path).read_bytes()
    second = (tmp_path / "b" / compare(store(tmp_path / "b"), demo_case).path).read_bytes()

    assert first == second
    assert first.endswith(b"\n")
    assert b'"assertions"' in first.split(b"\n")[1]  # sorted keys put assertions first


def test_the_recorded_instant_comes_from_the_injected_clock(
    tmp_path: Path, demo_case: LLMCase
) -> None:
    """Nothing in this suite reads the wall clock, and a non-UTC clock is normalised."""
    tokyo = datetime(2026, 9, 4, 3, 0, 0, tzinfo=timezone(timedelta(hours=9)))
    result = compare(store(tmp_path, clock=tokyo), demo_case)

    assert json.loads((tmp_path / result.path).read_text())["recorded"] == "2026-09-03T18:00:00Z"


def test_a_naive_clock_is_read_as_utc(tmp_path: Path, demo_case: LLMCase) -> None:
    """A test clock with no timezone must still produce one deterministic string."""
    naive = datetime(2026, 9, 3, 18, 0, 0)  # noqa: DTZ001 — the point of the test
    result = compare(store(tmp_path, clock=naive), demo_case)

    assert json.loads((tmp_path / result.path).read_text())["recorded"] == "2026-09-03T18:00:00Z"


def test_a_recorded_baseline_is_what_the_demo_suites_own_answers_produce(
    tmp_path: Path, demo_case: LLMCase, scripted_answer, judge_pass
) -> None:
    """The store's input is the runner's output, on the frozen example's own scripted answer."""
    answer = scripted_answer(demo_case)
    baselines = store(tmp_path)
    result = baselines.compare(
        suite=SUITE,
        case=demo_case,
        prompt_hash=prompt_hash(demo_case),
        results=evaluate_case(demo_case, answer, rubric_dirs=[DEMO / "rubrics"]),
        output=answer,
        model=MODEL,
        update=False,
    )
    assert result is not None and result.state == "recorded"

    recorded = json.loads((tmp_path / result.path).read_text())["assertions"]
    assert [entry["assertion_type"] for entry in recorded] == [
        "contains",
        "not_contains",
        "similarity",
        "judge",
    ]
    # The judge has no provider here, so it is unenforceable and recorded as a failure.
    assert [entry["passed"] for entry in recorded] == [True, True, True, False]
    assert judge_pass  # the fixture exists; grading it is Phase 4's test, not this one


# --------------------------------------------------------------------------- scores mode


def test_identical_results_are_unchanged(tmp_path: Path, demo_case: LLMCase) -> None:
    """The ordinary green path: the case did exactly what it used to do."""
    baselines = store(tmp_path)
    compare(baselines, demo_case)
    result = compare(baselines, demo_case)

    assert result.state == "unchanged"
    assert result.passed
    assert result.detail == "baseline unchanged"


def test_a_flipped_passed_flag_fails_with_a_before_after_table(
    tmp_path: Path, demo_case: LLMCase
) -> None:
    """A verdict that moved is drift even when its score did not (spec §3.6)."""
    baselines = store(tmp_path)
    compare(baselines, demo_case)
    result = compare(
        baselines,
        demo_case,
        ("contains", True, 1.0),
        ("not_contains", False, 1.0),
        ("similarity", True, 0.40),
        ("judge", True, 1.0),
    )

    assert result.state == "scores_changed"
    assert not result.passed

    lines = result.detail.splitlines()
    assert "scores changed since baseline" in lines[0]
    assert UPDATE_COMMAND in lines[0]
    assert lines[1].split() == ["assertion", "baseline", "current", "change"]
    assert lines[2].split() == ["contains", "pass", "1.000", "pass", "1.000"]
    assert lines[3].split() == ["not_contains", "pass", "1.000", "fail", "1.000", "verdict"]
    assert lines[5].split() == ["judge", "pass", "1.000", "pass", "1.000"]


def test_a_score_that_moves_by_more_than_the_tolerance_is_drift(
    tmp_path: Path, demo_case: LLMCase
) -> None:
    """0.06 is more than 0.05, and the table says which assertion moved."""
    baselines = store(tmp_path)
    compare(baselines, demo_case)
    result = compare(
        baselines,
        demo_case,
        ("contains", True, 1.0),
        ("not_contains", True, 1.0),
        ("similarity", True, 0.46),
        ("judge", True, 1.0),
    )

    assert result.state == "scores_changed"
    assert not result.passed
    row = next(line for line in result.detail.splitlines() if line.strip().startswith("similarity"))
    assert row.split() == ["similarity", "pass", "0.400", "pass", "0.460", "score"]


def test_a_score_that_moves_within_the_tolerance_is_not_drift(
    tmp_path: Path, demo_case: LLMCase
) -> None:
    """0.04 is inside the tolerance, and a run that only wobbles is not a regression."""
    baselines = store(tmp_path)
    compare(baselines, demo_case)
    result = compare(
        baselines,
        demo_case,
        ("contains", True, 1.0),
        ("not_contains", True, 1.0),
        ("similarity", True, 0.44),
        ("judge", True, 1.0),
    )

    assert result.state == "unchanged"
    assert result.passed


def test_a_move_of_exactly_the_tolerance_is_not_drift(tmp_path: Path, demo_case: LLMCase) -> None:
    """ "More than 0.05" excludes 0.05 itself, and the rounding makes that decidable."""
    baselines = store(tmp_path)
    compare(baselines, demo_case)
    result = compare(
        baselines,
        demo_case,
        ("contains", True, 1.0),
        ("not_contains", True, 1.0),
        ("similarity", True, 0.40 + SCORE_TOLERANCE),
        ("judge", True, 1.0),
    )

    assert result.state == "unchanged"


def test_a_score_that_appears_or_disappears_is_drift(tmp_path: Path, demo_case: LLMCase) -> None:
    """None to a number and back are both changes; neither is a distance (spec §3.6)."""
    baselines = store(tmp_path)
    compare(baselines, demo_case, ("contains", True, None), *PASSING[1:])

    gained = compare(baselines, demo_case, ("contains", True, 0.0), *PASSING[1:])
    assert gained.state == "scores_changed"
    row = next(line for line in gained.detail.splitlines() if line.strip().startswith("contains"))
    assert row.split() == ["contains", "pass", "n/a", "pass", "0.000", "score"]

    baselines.compare(
        suite=SUITE,
        case=demo_case,
        prompt_hash=prompt_hash(demo_case),
        results=results(("contains", True, 0.0), *PASSING[1:]),
        output="an answer",
        model=MODEL,
        update=True,
    )
    lost = compare(baselines, demo_case, ("contains", True, None), *PASSING[1:])
    assert lost.state == "scores_changed"


def test_both_none_scores_are_unchanged(tmp_path: Path, demo_case: LLMCase) -> None:
    """An assertion that never scores must not report drift on every run."""
    baselines = store(tmp_path)
    compare(baselines, demo_case, ("contains", True, None), *PASSING[1:])
    result = compare(baselines, demo_case, ("contains", True, None), *PASSING[1:])

    assert result.state == "unchanged"


# --------------------------------------------------------------------------- prompt drift


def test_a_changed_system_prompt_reports_prompt_changed(tmp_path: Path, demo_case: LLMCase) -> None:
    """Precedence: a different question makes the old scores meaningless, so they are not shown."""
    baselines = store(tmp_path)
    compare(baselines, demo_case)

    rewritten = demo_case.model_copy(update={"system": "Answer from anywhere you like."})
    result = compare(
        baselines,
        rewritten,
        ("contains", False, 0.0),
        ("not_contains", False, 0.0),
        ("similarity", False, 0.0),
        ("judge", False, 0.0),
    )

    assert result.state == "prompt_changed"
    assert not result.passed
    assert "prompt changed since baseline" in result.detail
    assert UPDATE_COMMAND in result.detail
    assert "\n" not in result.detail  # no table, no diff: one line
    assert "contains" not in result.detail


def test_prompt_drift_wins_over_output_drift(tmp_path: Path) -> None:
    """The same precedence in `output` mode: no diff is printed for a different prompt."""
    case = LLMCase(
        id="output-case",
        input="a question",
        assertions=[{"type": "contains", "all": ["a"]}],
        snapshot="output",
    )
    baselines = store(tmp_path)
    compare(baselines, case, output="first")
    result = compare(baselines, case, output="second", digest="0000000000000000")

    assert result.state == "prompt_changed"
    assert "@@" not in result.detail


# --------------------------------------------------------------------------- output mode


def test_output_mode_compares_the_text_and_records_it(tmp_path: Path) -> None:
    """`output` mode is the only mode that keeps the text; `scores` mode stores null."""
    case = LLMCase(
        id="output-case",
        input="a question",
        assertions=[{"type": "contains", "all": ["a"]}],
        snapshot="output",
    )
    baselines = store(tmp_path)
    recorded = compare(baselines, case, output="the first answer")

    assert json.loads((tmp_path / recorded.path).read_text())["output"] == "the first answer"
    assert compare(baselines, case, output="the first answer").state == "unchanged"

    result = compare(baselines, case, output="the second answer")
    assert result.state == "output_changed"
    assert not result.passed
    assert "output changed since baseline" in result.detail
    assert "-the first answer" in result.detail
    assert "+the second answer" in result.detail


def test_the_output_diff_is_capped_at_forty_lines(tmp_path: Path) -> None:
    """A rewritten answer must not bury the report under its own diff."""
    case = LLMCase(
        id="output-case",
        input="a question",
        assertions=[{"type": "contains", "all": ["a"]}],
        snapshot="output",
    )
    baselines = store(tmp_path)
    compare(baselines, case, output="\n".join(f"old line {n}" for n in range(60)))
    result = compare(baselines, case, output="\n".join(f"new line {n}" for n in range(60)))

    diff = result.detail.splitlines()[1:]
    assert result.state == "output_changed"
    assert len(diff) == DIFF_MAX_LINES
    assert diff[-1].startswith("... ") and diff[-1].endswith("more diff lines not shown")
    assert diff[0] == "--- baseline"


def test_a_short_output_diff_is_not_truncated(tmp_path: Path) -> None:
    """The cap only fires when there is something to cap."""
    case = LLMCase(
        id="output-case",
        input="a question",
        assertions=[{"type": "contains", "all": ["a"]}],
        snapshot="output",
    )
    baselines = store(tmp_path)
    compare(baselines, case, output="one")
    result = compare(baselines, case, output="two")

    diff = result.detail.splitlines()[1:]
    assert len(diff) < DIFF_MAX_LINES
    assert "not shown" not in result.detail


# --------------------------------------------------------------------------- shape changes


def test_a_baseline_whose_assertions_no_longer_line_up_is_scores_drift(
    tmp_path: Path, demo_case: LLMCase
) -> None:
    """DECISIONS 30: a re-shaped case fails in its own mode's words, not as `prompt_changed`."""
    baselines = store(tmp_path)
    compare(baselines, demo_case)
    result = compare(baselines, demo_case, *PASSING[:3])

    assert result.state == "scores_changed"
    assert not result.passed
    assert "no longer line up" in result.detail
    assert UPDATE_COMMAND in result.detail
    row = next(line for line in result.detail.splitlines() if "absent" in line)
    assert row.split() == ["judge", "pass", "1.000", "absent", "assertion", "list"]


def test_a_reordered_assertion_list_is_scores_drift(tmp_path: Path, demo_case: LLMCase) -> None:
    """Same length, different types in order: the rows would not be comparing like with like."""
    baselines = store(tmp_path)
    compare(baselines, demo_case)
    result = compare(
        baselines,
        demo_case,
        ("not_contains", True, 1.0),
        ("contains", True, 1.0),
        ("similarity", True, 0.40),
        ("judge", True, 1.0),
    )

    assert result.state == "scores_changed"
    assert "no longer line up" in result.detail


def test_a_longer_assertion_list_is_scores_drift(tmp_path: Path, demo_case: LLMCase) -> None:
    """The table pads the shorter side, whichever side that is."""
    baselines = store(tmp_path)
    compare(baselines, demo_case, *PASSING[:2])
    result = compare(baselines, demo_case)

    assert result.state == "scores_changed"
    assert len([line for line in result.detail.splitlines() if "absent" in line]) == 2


def test_a_changed_snapshot_mode_is_drift_in_the_new_mode(
    tmp_path: Path, demo_case: LLMCase
) -> None:
    """A `scores` baseline holds no text, so an `output` run cannot diff against it."""
    baselines = store(tmp_path)
    compare(baselines, demo_case)
    result = compare(baselines, demo_case.model_copy(update={"snapshot": "output"}))

    assert result.state == "output_changed"
    assert not result.passed
    assert "'scores'" in result.detail and "'output'" in result.detail
    assert UPDATE_COMMAND in result.detail


# --------------------------------------------------------------------------- updating and off


def test_update_overwrites_and_the_next_comparison_is_unchanged(
    tmp_path: Path, demo_case: LLMCase
) -> None:
    """What `--update-baseline` is for: accept the new numbers, then hold the suite to them."""
    baselines = store(tmp_path)
    compare(baselines, demo_case)
    moved = (
        ("contains", True, 1.0),
        ("not_contains", True, 1.0),
        ("similarity", False, 0.10),
        ("judge", True, 1.0),
    )
    assert compare(baselines, demo_case, *moved).state == "scores_changed"

    updated = compare(baselines, demo_case, *moved, update=True)
    assert updated.state == "updated"
    assert updated.passed
    assert "baseline updated" in updated.detail

    assert compare(baselines, demo_case, *moved).state == "unchanged"


def test_update_writes_a_baseline_that_was_never_recorded(
    tmp_path: Path, demo_case: LLMCase
) -> None:
    """`--update-baseline` on a fresh checkout writes rather than reporting `recorded`."""
    result = compare(store(tmp_path), demo_case, update=True)

    assert result.state == "updated"
    assert (tmp_path / result.path).exists()


def test_a_case_with_snapshot_off_is_never_read_or_written(tmp_path: Path) -> None:
    """`snapshot: off` is the default, so this is most cases; it must touch no disk."""
    case = LLMCase(
        id="plain-case",
        input="a question",
        assertions=[{"type": "contains", "all": ["a"]}],
    )
    baselines = store(tmp_path)
    baselines.write(
        SUITE,
        Baseline(
            case_id="plain-case",
            prompt_hash="0000000000000000",
            mode="scores",
            assertions=[BaselineAssertion(assertion_type="contains", passed=False, score=0.0)],
            recorded="2020-01-01T00:00:00Z",
            model="stale",
        ),
    )
    before = (tmp_path / "baseline" / SUITE / "plain-case.json").read_bytes()

    for update in (False, True):
        assert (
            baselines.compare(
                suite=SUITE,
                case=case,
                prompt_hash=prompt_hash(case),
                results=results(("contains", True, 1.0)),
                output="an answer",
                model=MODEL,
                update=update,
            )
            is None
        )

    assert (tmp_path / "baseline" / SUITE / "plain-case.json").read_bytes() == before


# --------------------------------------------------------------------------- broken artefacts


def test_a_missing_baseline_loads_as_none(tmp_path: Path) -> None:
    """No file is the ordinary first-run state, not an error."""
    assert store(tmp_path).load(SUITE, "absent-case") is None


def test_an_unparsable_baseline_is_a_config_error(tmp_path: Path, demo_case: LLMCase) -> None:
    """DECISIONS 33: re-recording over a mangled file would turn a lost signal green."""
    baselines = store(tmp_path)
    path = tmp_path / compare(baselines, demo_case).path
    path.write_text('{"case_id": "htn-definition"}\n', encoding="utf-8")

    with pytest.raises(ProbatioConfigError) as excinfo:
        baselines.load(SUITE, "htn-definition")
    assert str(path) in str(excinfo.value)
    assert UPDATE_COMMAND in str(excinfo.value)

    with pytest.raises(ProbatioConfigError):
        compare(baselines, demo_case)


def test_an_unreadable_baseline_is_a_config_error(tmp_path: Path, demo_case: LLMCase) -> None:
    """A directory where a file should be is the same kind of broken as unparsable JSON."""
    baselines = store(tmp_path)
    path = baselines.path_for(SUITE, "htn-definition")
    path.mkdir(parents=True)

    with pytest.raises(ProbatioConfigError) as excinfo:
        baselines.load(SUITE, "htn-definition")
    assert "cannot be read" in str(excinfo.value)


def test_a_name_that_would_escape_the_baseline_directory_is_refused(tmp_path: Path) -> None:
    """Suite names reach the store from a caller, so they are checked before they become a path."""
    baselines = store(tmp_path)
    for suite in ("../elsewhere", "a/b", ".hidden", ""):
        with pytest.raises(ProbatioConfigError) as excinfo:
            baselines.path_for(suite, "a-case")
        assert "suite" in str(excinfo.value)

    with pytest.raises(ProbatioConfigError) as excinfo:
        baselines.path_for(SUITE, "../escape")
    assert "case id" in str(excinfo.value)


def test_a_baselines_two_halves_must_agree_about_its_mode() -> None:
    """The file itself refuses the two shapes a comparison would have to guess about."""
    fields = {
        "case_id": "a-case",
        "prompt_hash": "0000000000000000",
        "assertions": [],
        "recorded": "2026-09-03T18:00:00Z",
        "model": MODEL,
    }
    with pytest.raises(ValueError, match="must carry the output"):
        Baseline(mode="output", output=None, **fields)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="records scores, not an output"):
        Baseline(mode="scores", output="text", **fields)  # type: ignore[arg-type]


def test_the_store_defaults_to_the_working_directory(tmp_path: Path, monkeypatch) -> None:
    """A store built with no directory writes where spec §5 says, relative to the cwd."""
    monkeypatch.chdir(tmp_path)
    assert BaselineStore().baseline_dir == tmp_path / ".probatio" / "baseline"


def test_the_default_clock_is_timezone_aware_utc() -> None:
    """The default clock's *value* is never asserted; that it carries UTC is what makes it safe."""
    moment = BaselineStore().clock()

    assert moment.tzinfo is UTC
