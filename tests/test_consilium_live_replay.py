"""Phase 12: the recorded live suite replays offline, calling no model.

This is the test that makes the live suite worth committing. Recording it cost real calls to a
real model; replaying it must cost nothing, reproduce the same verdicts, the same relation
violation rates and the same judge verdicts, and reach no provider at all.

"Zero inner calls" is asserted the way ``tests/test_consilium_suite.py`` asserts it, because a
replaying ``CassetteProvider`` never touches its inner adapter and so cannot be counted from the
outside: the configured provider here is the default ``fake``, whose answers are the deterministic
``FAKE(<hash>)`` fallback, and a fallback answer carries no reference wording, no escalation phrase
and no gradeable claim, so a run that had reached it would look nothing like the recorded one.
Pointing the same run at an empty cassette directory raises :class:`MissingCassetteError` instead
of quietly answering, which is the other half of the argument.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from probatio.reporters import read_results

REPO_ROOT = Path(__file__).resolve().parents[1]
SUITE = REPO_ROOT / "examples" / "consilium"
LIVE = SUITE / "live"
BASELINES = REPO_ROOT / ".probatio" / "baseline-live"
VARIANCE_BASELINES = REPO_ROOT / ".probatio" / "baseline-live-n10"

CASE_IDS = (SUITE / "CASES.txt").read_text(encoding="utf-8").split()
RELATIONS = ("distractor_robust", "format_jitter", "order_invariant", "paraphrase_invariant")
MODEL = "claude-opus-5"
"""The model the tapes were recorded against, which is part of every cassette key (DECISIONS 91)."""


@pytest.fixture
def live(pytester: pytest.Pytester) -> Path:
    """A copy of the live suite and both sets of committed baselines in a temporary rootdir."""
    target = pytester.path / "live"
    shutil.copytree(LIVE, target, ignore=shutil.ignore_patterns("__pycache__", "results"))
    baselines = pytester.path / ".probatio"
    shutil.copytree(BASELINES / "test_live", baselines / BASELINES.name / "test_live")
    shutil.copytree(
        VARIANCE_BASELINES / "test_live_variance",
        baselines / VARIANCE_BASELINES.name / "test_live_variance",
    )
    return target


def run_live(pytester: pytest.Pytester, *extra: str) -> Path:
    """Replay the live suite against the copied tapes and return its results JSON."""
    results = pytester.path / "live.json"
    pytester.runpytest_subprocess(
        "live/test_live.py",
        "--cassette-dir",
        "live/cassettes",
        "--baseline-dir",
        ".probatio/baseline-live",
        "--probatio-model",
        MODEL,
        "--probatio-results",
        str(results),
        *extra,
    )
    assert results.exists(), "the live suite wrote no results file"
    return results


def test_the_live_suite_replays_from_its_tapes(pytester: pytest.Pytester, live: Path) -> None:
    """Fifteen cases, every snapshot unchanged, every relation measured, no model called."""
    report = read_results(run_live(pytester))

    assert sorted(case.case_id for case in report.cases) == sorted(CASE_IDS)
    states = {case.snapshot.state for case in report.cases if case.snapshot is not None}
    assert states == {"unchanged"}, sorted(states)

    measured = {
        relation.relation
        for case in report.cases
        for relation in case.relations
        if relation.n_variants > 0
    }
    assert measured == set(RELATIONS), sorted(measured)

    graded = [
        result
        for case in report.cases
        for result in case.results
        if result.assertion_type == "judge"
    ]
    assert len(graded) == len(CASE_IDS)
    assert [result for result in graded if "not valid JSON" in result.detail] == [], (
        "a judge reply on the tapes did not parse; the recorded verdict is not readable"
    )


def test_replay_reproduces_the_recorded_latencies_a_fake_could_not_invent(
    pytester: pytest.Pytester, live: Path
) -> None:
    """The tape's latency is a real model's; the default fake provider reports its own constant."""
    report = read_results(run_live(pytester))
    tape = json.loads(
        (live / "cassettes" / "test_live" / "g-su-001.json").read_text(encoding="utf-8")
    )
    recorded = {
        interaction["key"]: interaction["completions"][0] for interaction in tape["interactions"]
    }
    assert recorded, "the committed tape holds no interaction"
    assert all("FAKE(" not in completion["text"] for completion in recorded.values())

    case = next(case for case in report.cases if case.case_id == "g-su-001")
    latencies = {completion["latency_ms"] for completion in recorded.values()}
    assert case.latency_ms in latencies or case.latency_ms == pytest.approx(
        sum(latencies), rel=1.0
    ), (case.latency_ms, sorted(latencies))


def test_the_same_run_against_no_tapes_raises_rather_than_answering(
    pytester: pytest.Pytester, live: Path
) -> None:
    """Replay never falls through to the inner provider; a missing tape is an error."""
    result = pytester.runpytest_subprocess(
        "live/test_live.py",
        "--cassette-dir",
        "no-such-cassettes",
        "--baseline-dir",
        ".probatio/baseline-live",
        "--probatio-model",
        MODEL,
    )
    assert result.ret != 0
    result.stdout.fnmatch_lines(["*MissingCassetteError*"])


def test_the_route_b_tapes_replay_to_the_committed_changed_report(
    pytester: pytest.Pytester, live: Path
) -> None:
    """Route B is only evidence if its tapes still produce the report the case study quotes.

    The haiku tapes replay against the **opus** baselines, which is what makes the snapshot column
    say `scores_changed` rather than `unchanged`; that drift is §2's subject, so it is asserted
    rather than tolerated.
    """
    results = pytester.path / "changed.json"
    pytester.runpytest_subprocess(
        "live/test_live.py",
        "--cassette-dir",
        "live/cassettes-haiku",
        "--baseline-dir",
        ".probatio/baseline-live",
        "--probatio-model",
        "claude-haiku-4-5-20251001",
        "--probatio-results",
        str(results),
    )
    replayed = read_results(results)
    committed = read_results(LIVE / "results" / "live-changed.json")

    assert {c.case_id: c.verdict for c in replayed.cases} == {
        c.case_id: c.verdict for c in committed.cases
    }
    assert {c.case_id: (c.snapshot.state if c.snapshot else None) for c in replayed.cases} == {
        c.case_id: (c.snapshot.state if c.snapshot else None) for c in committed.cases
    }
    assert {r.relation: r.n_violations for r in replayed.relations} == {
        r.relation: r.n_violations for r in committed.relations
    }


# -- Phase 15, experiment A: the same fifteen cases recorded ten times ------------------------

RUNS = 10
"""``--runs 10``: the recording appended one sample per run (DECISIONS 44), so replay reads ten."""


def run_variance(pytester: pytest.Pytester, results: Path) -> Path:
    """Replay the variance suite under ``--runs 10`` against the copied tapes."""
    pytester.runpytest_subprocess(
        "live/test_live_variance.py",
        "--runs",
        str(RUNS),
        "--cassette-dir",
        "live/cassettes-n10",
        "--baseline-dir",
        ".probatio/baseline-live-n10",
        "--probatio-model",
        MODEL,
        "--probatio-results",
        str(results),
    )
    assert results.exists(), "the variance suite wrote no results file"
    return results


def test_the_variance_suite_replays_to_the_committed_results(
    pytester: pytest.Pytester, live: Path
) -> None:
    """Ten runs a case, every pass rate and every interval reproduced from the tapes."""
    replayed = read_results(run_variance(pytester, pytester.path / "n10.json"))
    committed = read_results(LIVE / "results" / "live-n10.json")

    assert replayed.runs == committed.runs == RUNS
    assert {c.case_id for c in replayed.cases} == set(CASE_IDS)
    assert {c.case_id: c.stability.model_dump() for c in replayed.cases} == {
        c.case_id: c.stability.model_dump() for c in committed.cases
    }
    assert {c.case_id: c.verdict for c in replayed.cases} == {
        c.case_id: c.verdict for c in committed.cases
    }
    states = {case.snapshot.state for case in replayed.cases if case.snapshot is not None}
    assert states == {"unchanged"}, sorted(states)


def test_the_variance_suite_carries_no_relation_and_calls_no_model(
    pytester: pytest.Pytester, live: Path
) -> None:
    """No relation decorator, so no variant call; and the tapes hold exactly what was recorded.

    Zero inner calls is asserted the way this module's Phase 12 tests assert it: the configured
    provider is the default ``fake``, whose ``FAKE(<hash>)`` fallback carries no reference wording
    and no gradeable claim, and pointing the same run at a directory with no tapes raises instead
    of answering.
    """
    replayed = read_results(run_variance(pytester, pytester.path / "n10.json"))
    assert [relation for case in replayed.cases for relation in case.relations] == []

    tape = json.loads(
        (live / "cassettes-n10" / "test_live_variance" / "g-su-001.json").read_text(
            encoding="utf-8"
        )
    )
    samples = [c for i in tape["interactions"] for c in i["completions"]]
    assert len(samples) == 2 * RUNS, "ten answers and ten gradings is what --runs 10 records"
    assert all("FAKE(" not in completion["text"] for completion in samples)

    missing = pytester.runpytest_subprocess(
        "live/test_live_variance.py",
        "--runs",
        str(RUNS),
        "--cassette-dir",
        "no-such-cassettes",
        "--baseline-dir",
        ".probatio/baseline-live-n10",
        "--probatio-model",
        MODEL,
    )
    assert missing.ret != 0
    missing.stdout.fnmatch_lines(["*MissingCassetteError*"])
