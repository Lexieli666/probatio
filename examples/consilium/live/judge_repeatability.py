"""Phase 15's experiment B: grade one fixed answer ten times and see whether the judge agrees.

Experiment A (``test_live_variance.py``) answers each case ten times and reports a pass rate per
case. It cannot say *what* varies: a case whose verdict moves may have been answered differently,
or may have been answered identically and graded differently. This script holds the answer still.
For each of the fifteen cases it takes the **committed** ``claude-opus-5`` answer out of the Phase
12 tape in ``cassettes/test_live/`` — the same bytes every time — and asks the same judge, with the
same rubric and the same prompt template, to grade it ten times.

Identical input, ten gradings. Whatever moves is the judge.

This is a script and not a test, for the reason every live step in this repository is a script: it
calls a model. Its output is committed, and ``--replay`` rebuilds that output from the tapes with
no model call at all, which is what ``tests/test_consilium_judge_repeatability.py`` runs.

    python examples/consilium/live/judge_repeatability.py --record   # live, 150 calls
    python examples/consilium/live/judge_repeatability.py --replay   # offline, 0 calls

``--record --only <case_id>`` records one case's ten gradings and writes no results file, so a
recording interrupted by a rate limit resumes a case at a time. The committed file is always
written by an unfiltered ``--replay``, from the tapes.

An unparsable reply is recorded as the verdict ``unparsable`` with a null score rather than
re-asked. Re-asking would append an eleventh sample to a tape whose whole point is ten, and a
judge that failed to state a verdict on input it had already graded nine times is a repeatability
observation, not an accident to be retried away (DECISIONS 92 re-asks in
``validate-judge --run-judge``, where the row is a measurement of a human label and a non-answer
carries no judgement to compare).
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

from app_live import build_prompt

from probatio import LLMCase, Provider, load_cases
from probatio.artefacts import display_path, write_json
from probatio.cassette import CassetteProvider, CassetteStore, interaction_key
from probatio.cli import build_provider
from probatio.errors import JudgeOutputError, ProbatioConfigError
from probatio.judge import Judge, judge_template_hash, resolve_rubric
from probatio.stability import wilson_interval

HERE: Final = Path(__file__).resolve().parent
REPO_ROOT: Final = HERE.parents[2]

MODEL: Final = "claude-opus-5"
"""The Phase 12 model. It answered the tapes this script reads, and it grades them again here."""

SOURCE_SUITE: Final = "test_live"
SOURCE_CASSETTES: Final = HERE / "cassettes"
SUITE: Final = "judge_repeatability"
TAPES: Final = HERE / "cassettes-judge-x10"
RUBRIC: Final = HERE / "rubrics" / "faithfulness.md"
OUT: Final = HERE / "results" / "judge-repeatability.json"
GRADINGS: Final = 10
UNPARSABLE: Final = "unparsable"
ROUNDING: Final = 6


def recorded_answer(case: LLMCase) -> str:
    """Return the committed ``claude-opus-5`` answer to one case, out of the Phase 12 tape.

    The tape holds the system-under-test call and the judge call for the original case and for
    every one of its relation variants, so the right interaction is found by key rather than by
    position: :func:`~probatio.cassette.interaction_key` of the prompt ``app_live`` builds for the
    unmodified case, with no judge template, is exactly one of them.

    Args:
        case: The case whose answer is wanted.

    Returns:
        The text of the first recorded sample.

    Raises:
        ProbatioConfigError: The tape is missing, or holds no interaction for that key, which
            means the tapes and the cases have drifted apart.
    """
    path = SOURCE_CASSETTES / SOURCE_SUITE / f"{case.id}.json"
    if not path.is_file():
        raise ProbatioConfigError(
            f"no committed answer for {case.id}: {display_path(path, REPO_ROOT)} does not exist",
            case_id=case.id,
        )
    key = interaction_key(
        prompt=build_prompt(case), system=case.system, params=case.params, model=MODEL
    )
    tape = json.loads(path.read_text(encoding="utf-8"))
    for interaction in tape["interactions"]:
        if interaction["key"] == key:
            return str(interaction["completions"][0]["text"])
    raise ProbatioConfigError(
        f"the tape for {case.id} holds no system-under-test call for the case as it stands; "
        f"the cases and {display_path(path, REPO_ROOT)} have drifted apart",
        case_id=case.id,
    )


def judge_threshold(case: LLMCase) -> float:
    """Return the threshold the case's ``judge`` assertion declares.

    Args:
        case: The case.

    Returns:
        The threshold a verdict must reach to pass.

    Raises:
        ProbatioConfigError: The case declares no judge assertion, so there is nothing to repeat.
    """
    for assertion in case.assertions:
        if assertion.type == "judge":
            return float(assertion.threshold)
    raise ProbatioConfigError(f"case {case.id} declares no judge assertion", case_id=case.id)


def grade_ten_times(
    judge: Judge, store: CassetteStore, case: LLMCase, output: str
) -> dict[str, Any]:
    """Grade one fixed answer :data:`GRADINGS` times and summarise what came back.

    Args:
        judge: The judge, holding the rubric and the cassette-wrapped provider.
        store: The store the gradings are filed under; each grading is one run index, so replay
            returns the samples in the order they were recorded.
        case: The case being graded.
        output: The answer, identical on every grading.

    Returns:
        One entry of the results file's ``cases`` list.
    """
    threshold = judge_threshold(case)
    verdicts: list[str] = []
    scores: list[float | None] = []
    passes = 0
    for run_index in range(GRADINGS):
        store.begin_case(SUITE, case.id, run_index=run_index)
        try:
            verdict = judge.grade(case, output)
        except JudgeOutputError:
            verdicts.append(UNPARSABLE)
            scores.append(None)
            continue
        finally:
            store.end_case()
        verdicts.append(verdict.verdict)
        scores.append(verdict.score)
        passes += int(verdict.passes(threshold))
    low, high = wilson_interval(passes, GRADINGS)
    return {
        "case_id": case.id,
        "n": GRADINGS,
        "pass_rate": round(passes / GRADINGS, ROUNDING),
        "passes": passes,
        "scores": scores,
        "threshold": threshold,
        "unanimous": len(set(verdicts)) == 1,
        "verdicts": verdicts,
        "wilson_95": [round(low, ROUNDING), round(high, ROUNDING)],
    }


def study(
    mode: str,
    *,
    inner: Provider | None = None,
    timeout_s: float | None = None,
    tapes: Path = TAPES,
    only: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Run the whole experiment and return the payload the results file holds.

    Args:
        mode: ``record`` to call the model, ``replay`` to read the committed tapes.
        inner: The adapter under the cassette. Defaults to the Claude CLI when recording and to a
            ``fake`` when replaying, where it is never called.
        timeout_s: Seconds one live call may take, or ``None`` for the adapter's default.
        tapes: Where the judge tapes live.
        only: Record just these case ids, so an interrupted recording resumes a case at a time
            instead of spending 150 calls again. A filtered run is a recording aid and its payload
            is not the study; ``main`` refuses to write the results file for one.

    Returns:
        The payload: one entry per case, plus the provenance of the judge that produced it and the
        count this study exists to report.

    Raises:
        ProbatioConfigError: ``only`` names an id that is not one of the cases.
    """
    cases = load_cases(HERE / "cases")
    if only is not None:
        wanted = set(only)
        unknown = sorted(wanted - {case.id for case in cases})
        if unknown:
            raise ProbatioConfigError(f"no such case(s): {', '.join(unknown)}")
        cases = [case for case in cases if case.id in wanted]
    rubric = resolve_rubric(str(RUBRIC))
    if inner is None:
        inner = build_provider("claude-cli" if mode == "record" else "fake", MODEL, timeout_s)
    store = CassetteStore(tapes, root=REPO_ROOT)
    judge = Judge(rubric, CassetteProvider(inner, store, mode))

    entries = [grade_ten_times(judge, store, case, recorded_answer(case)) for case in cases]
    return {
        "cases": entries,
        "cases_not_unanimous": sum(1 for entry in entries if not entry["unanimous"]),
        "gradings_per_case": GRADINGS,
        "judge_model": MODEL,
        "judge_template_hash": judge_template_hash(),
        "rubric": rubric.name,
        "rubric_hash": rubric.content_hash,
        "source_cassettes": display_path(SOURCE_CASSETTES / SOURCE_SUITE, REPO_ROOT),
        "tapes": display_path(tapes / SUITE, REPO_ROOT),
    }


def main(argv: list[str] | None = None) -> int:
    """Parse the command line, run the study, and write the results file.

    Args:
        argv: The arguments, or ``None`` for ``sys.argv[1:]``.

    Returns:
        A process exit status: always 0, because every outcome the judge can produce is data.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--record", action="store_true", help="call the model (150 live calls)")
    group.add_argument("--replay", action="store_true", help="rebuild the file from the tapes")
    parser.add_argument("--out", type=Path, default=OUT, help="where to write the results file")
    parser.add_argument("--tapes", type=Path, default=TAPES, help="the judge cassette directory")
    parser.add_argument("--timeout", type=float, default=None, help="seconds per live call")
    parser.add_argument(
        "--only", nargs="+", metavar="CASE_ID", help="record these cases only; writes no file"
    )
    args = parser.parse_args(argv)

    payload = study(
        "record" if args.record else "replay",
        timeout_s=args.timeout,
        tapes=args.tapes,
        only=args.only,
    )
    summary = (
        f"{len(payload['cases'])} case(s) x {GRADINGS} gradings; "
        f"{payload['cases_not_unanimous']} case(s) not unanimous"
    )
    if args.only:
        print(f"{summary} (--only: tapes written, results file left alone)")
        return 0
    path = write_json(args.out, payload)
    print(f"{summary} -> {display_path(path, REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
