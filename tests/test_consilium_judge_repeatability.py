"""Phase 15, experiment B: the judge repeatability study rebuilds itself from its tapes.

``examples/consilium/live/judge_repeatability.py`` graded fifteen committed answers ten times each
against a live model. What makes that worth committing is the same thing that makes the live suite
worth committing: ``--replay`` must reproduce the published file exactly, from the tapes, with the
inner provider never called.

The strongest assertion here is the shape of the tapes. The input to every one of a case's ten
gradings is byte-identical — the same rubric, the same template and the same recorded answer — so
the ten calls share one cassette key, and the tape holds **one** interaction with ten samples. A
tape with two interactions would mean the study had varied something it claims to hold still.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any, Final

import pytest

from probatio import FakeProvider
from probatio.stability import wilson_interval

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
LIVE: Final = REPO_ROOT / "examples" / "consilium" / "live"
SCRIPT: Final = LIVE / "judge_repeatability.py"
COMMITTED: Final = LIVE / "results" / "judge-repeatability.json"
TAPES: Final = LIVE / "cassettes-judge-x10" / "judge_repeatability"


@pytest.fixture
def script(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """The study, imported the way running it as a script imports it.

    Running ``python examples/consilium/live/judge_repeatability.py`` puts that directory on
    ``sys.path`` itself, which is how its ``from app_live import build_prompt`` resolves
    (DECISIONS 88). Loading it from here has to do the same thing explicitly.
    """
    monkeypatch.syspath_prepend(str(LIVE))
    spec = importlib.util.spec_from_file_location("consilium_judge_repeatability", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def committed() -> dict[str, Any]:
    """The committed results file, parsed."""
    payload: dict[str, Any] = json.loads(COMMITTED.read_text(encoding="utf-8"))
    return payload


def test_replay_reproduces_the_committed_results_byte_for_byte(
    script: ModuleType, tmp_path: Path
) -> None:
    """The published file is a function of the tapes, not of the day it was written."""
    out = tmp_path / "judge-repeatability.json"
    assert script.main(["--replay", "--out", str(out)]) == 0
    assert out.read_bytes() == COMMITTED.read_bytes()


def test_replay_reaches_no_provider(script: ModuleType, committed: dict[str, Any]) -> None:
    """A replaying cassette never touches its inner adapter, so the fake counts zero calls."""
    inner = FakeProvider(model=script.MODEL)
    payload = script.study("replay", inner=inner)
    assert inner.call_count == 0
    assert payload == committed


def test_each_tape_holds_one_interaction_with_ten_samples(
    script: ModuleType, committed: dict[str, Any]
) -> None:
    """Identical input is one cassette key; ten gradings of it are ten samples under that key."""
    for entry in committed["cases"]:
        tape = json.loads((TAPES / f"{entry['case_id']}.json").read_text(encoding="utf-8"))
        assert len(tape["interactions"]) == 1, entry["case_id"]
        interaction = tape["interactions"][0]
        assert len(interaction["completions"]) == script.GRADINGS, entry["case_id"]
        assert tape["model"] == script.MODEL
        assert all("FAKE(" not in sample["text"] for sample in interaction["completions"])


def test_the_graded_answer_is_the_committed_opus_answer(script: ModuleType) -> None:
    """The answer under the judge came off the Phase 12 tape, not out of this script."""
    cases = {case.id: case for case in script.load_cases(LIVE / "cases")}
    for case_id, case in cases.items():
        answer = script.recorded_answer(case)
        source = json.loads(
            (LIVE / "cassettes" / "test_live" / f"{case_id}.json").read_text(encoding="utf-8")
        )
        recorded = [
            sample["text"]
            for interaction in source["interactions"]
            for sample in interaction["completions"]
        ]
        assert answer in recorded
        graded = json.loads((TAPES / f"{case_id}.json").read_text(encoding="utf-8"))
        assert answer in graded["interactions"][0]["prompt"]


def test_every_summary_is_what_its_own_verdicts_say(
    script: ModuleType, committed: dict[str, Any]
) -> None:
    """The pass counts, intervals and the headline count are re-derived, not trusted."""
    assert len(committed["cases"]) == 15
    not_unanimous = 0
    for entry in committed["cases"]:
        verdicts, scores = entry["verdicts"], entry["scores"]
        assert len(verdicts) == len(scores) == script.GRADINGS == entry["n"]
        passes = sum(
            1
            for verdict, score in zip(verdicts, scores, strict=True)
            if verdict == "pass" and score is not None and score >= entry["threshold"]
        )
        assert passes == entry["passes"]
        assert entry["pass_rate"] == round(passes / script.GRADINGS, script.ROUNDING)
        low, high = wilson_interval(passes, script.GRADINGS)
        assert entry["wilson_95"] == [
            round(low, script.ROUNDING),
            round(high, script.ROUNDING),
        ]
        assert entry["unanimous"] == (len(set(verdicts)) == 1)
        not_unanimous += int(not entry["unanimous"])
    assert committed["cases_not_unanimous"] == not_unanimous
