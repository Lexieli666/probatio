# Provenance: every number in this documentation, and the file behind it

`CLAUDE.md` and the specification both say it: **no number appears in `README.md` or under `docs/`
that a committed file did not produce.** This file is the index that makes that rule checkable
rather than aspirational. `tests/test_docs_provenance.py` reads the two tables below, runs each
row's check against the file it names, and fails the suite when a document and its source disagree
— in either direction, so a figure edited in prose fails and a source re-recorded without updating
the prose fails too.

Phase 14 added `CHANGELOG.md` to the rule (DECISIONS 101). It states no measurement at all, so it
holds no row in the first table; the sweep that guards it is the same sweep the README gets, which
is what makes that emptiness a fact rather than an intention.

## How to read a row

- **number** — the figure exactly as it appears in the prose, with any `**` emphasis removed.
- **appears in** — every document that prints it. A number printed in two documents has one row —
  unless two *different* measurements happen to print the same string, which is why `0.90` has two
  (the demo suite's stability score, and a per-case pass rate in the variance study). One string,
  two rows, two derivations: merging them would make one of the two claim a source it did not
  come from.
- **source file** — the committed file it came from. Where one document quotes a figure another
  document already carries, the source is that document, which has a provenance test of its own;
  the chain always ends at an artefact, and the last table below records which test guards which
  document.
- **check** — how the figure is tied to the file. `text` means the number's string is present in
  the source. Everything else names a derivation that `run_check` recomputes and then formats to
  the decimals the prose prints: `json <path>` and `json-of <a> <b>` read values out of a JSON
  document, `json-difference` takes the payload's total minus its answering model's share,
  `wilson <n>` calls `wilson_interval(n, n)`, `similarity <suite> <stat>` and
  `similarity-headroom <tau>` aggregate the similarity scores in a results file, `kappa` recomputes
  Cohen's κ from a label CSV, `length` and `json-error-column` measure a captured reply,
  `verdicts-moved` and `judge-failures` compare two results files, `variants-deleted` counts the
  deletion notes and the surviving paraphrases in the frozen variant files, `interactions` counts
  what a directory of cassettes holds and `samples` counts the recorded completions inside them,
  `variance <field>` reads the per-case stability statistics out of a repeated run's results file
  — `pass-rate`, `wilson-low`, `wilson-high` and `runs-passed` assert the figure is one the file
  holds, `disagreeing` counts the cases with at least one run against their own majority and
  `below <floor>` the cases whose Wilson lower bound falls under a floor — and
  `judge-repeat <field>` does the same for the judge repeatability file, with `not-unanimous`
  recounting its headline from the verdicts themselves rather than reading the field beside them.
  A check the test does not implement raises rather than passing.
- **regenerate** — the command that rebuilds the source file. `—` means the file is not a run
  output: a committed case, a constant in the package, or the run log itself.

Five commands recur and are written once here rather than in twenty rows:

```bash
# R1 — the demo suite's committed --runs 5 run, quoted in PROGRESS.md at commit 4c2114e
pytest examples/demo_suite --runs 5

# R2 — the offline Consilium replay
pytest examples/consilium -q --cassette-dir examples/consilium/cassettes \
       --probatio-results examples/consilium/results/replay-unpriced.json \
       --probatio-report examples/consilium/results/replay-unpriced.md

# R3 — the live Consilium replay, opus baseline and haiku change
pytest examples/consilium/live/test_live.py -q \
       --cassette-dir examples/consilium/live/cassettes \
       --baseline-dir .probatio/baseline-live --probatio-model claude-opus-5 \
       --probatio-results examples/consilium/live/results/live-baseline.json \
       --probatio-report examples/consilium/live/results/live-baseline.md

# R4 — the Phase 15 variance replay, ten runs of the same fifteen live cases
pytest examples/consilium/live/test_live_variance.py -q --runs 10 \
       --cassette-dir examples/consilium/live/cassettes-n10 \
       --baseline-dir .probatio/baseline-live-n10 --probatio-model claude-opus-5 \
       --probatio-results examples/consilium/live/results/live-n10.json \
       --probatio-junit examples/consilium/live/results/live-n10.xml \
       --probatio-report examples/consilium/live/results/live-n10.md

# R5 — the Phase 15 judge repeatability study, rebuilt from its tapes
python examples/consilium/live/judge_repeatability.py --replay
```

## Measurements

| number | appears in | source file | check | regenerate |
|---|---|---|---|---|
| `0.57` | `README.md`, `docs/stability.md` | `PROGRESS.md` | text | R1 |
| `0.90` | `README.md`, `docs/stability.md` | `PROGRESS.md` | text | R1 |
| `0.38` | `README.md`, `docs/stability.md` | `PROGRESS.md` | text | R1 |
| `0.72` | `docs/stability.md`, `docs/EVALUATION.md` | `src/probatio/stability/wilson.py` | wilson 10 | — |
| `12 of 12` | `README.md`, `docs/stability.md` | `PROGRESS.md` | text | R1 |
| `0.14` | `README.md` | `PROGRESS.md` | text | R1 |
| `0.17` | `README.md`, `docs/CASE_STUDY.md`, `docs/EVALUATION.md` | `PROGRESS.md` | text | R1 |
| `0.33` | `README.md`, `docs/CASE_STUDY.md`, `docs/EVALUATION.md` | `PROGRESS.md` | text | R1 |
| `15/105` | `README.md` | `PROGRESS.md` | text | R1 |
| `5/30` | `README.md`, `docs/CASE_STUDY.md`, `docs/EVALUATION.md` | `PROGRESS.md` | text | R1 |
| `0/70` | `README.md` | `PROGRESS.md` | text | R1 |
| `0/50` | `README.md` | `PROGRESS.md` | text | R1 |
| `$0.000500` | `README.md` | `PROGRESS.md` | text | R1 |
| `$0.031500` | `README.md` | `PROGRESS.md` | text | R1 |
| `0.223` | `README.md`, `docs/assertions.md` | `docs/assertions.md` | text | — |
| `0.453` | `README.md`, `docs/assertions.md` | `docs/assertions.md` | text | — |
| `0.923` | `docs/assertions.md`, `docs/DESIGN.md` | `docs/assertions.md` | text | — |
| `1.000` | `docs/assertions.md` | `docs/assertions.md` | text | — |
| `0.000` | `docs/assertions.md` | `docs/assertions.md` | text | — |
| `0.398` | `docs/assertions.md`, `docs/DESIGN.md` | `examples/consilium/results/replay-unpriced.json` | similarity test_full min | R2 |
| `0.705` | `docs/assertions.md`, `docs/DESIGN.md` | `examples/consilium/results/replay-unpriced.json` | similarity test_full max | R2 |
| `0.443` | `docs/assertions.md` | `examples/consilium/results/replay-unpriced.json` | similarity test_baseline min | R2 |
| `0.649` | `docs/assertions.md` | `examples/consilium/results/replay-unpriced.json` | similarity test_baseline max | R2 |
| `0.538` | `docs/assertions.md` | `examples/consilium/results/replay-unpriced.json` | similarity test_baseline median | R2 |
| `0.574` | `docs/assertions.md` | `examples/consilium/results/replay-unpriced.json` | similarity test_full median | R2 |
| `0.098` | `docs/assertions.md` | `examples/consilium/results/replay-unpriced.json` | similarity-headroom 0.30 | R2 |
| `$0.003769` | `docs/providers.md` | `tests/fixtures/claude_cli_payload.json` | json `total_cost_usd` | — |
| `$0.002695` | `docs/providers.md` | `tests/fixtures/claude_cli_payload.json` | text | — |
| `$0.001074` | `docs/providers.md` | `tests/fixtures/claude_cli_payload.json` | json-difference | — |
| `8 of 40` | `docs/providers.md` | `examples/consilium/live/results/judges-sample-1/faithfulness.validation.json` | json-of rows_reasked n | `probatio validate-judge --run-judge` |
| `5 of 40` | `docs/providers.md` | `PROGRESS.md` | text | `probatio validate-judge --run-judge` |
| `400` | `docs/providers.md` | `tests/fixtures/claude_cli_truncated_judge_reply.txt` | length | — |
| `column 49` | `docs/providers.md` | `tests/fixtures/claude_cli_truncated_judge_reply.txt` | json-error-column | — |
| `0.600` | `README.md`, `docs/CASE_STUDY.md`, `docs/EVALUATION.md` | `examples/consilium/live/results/judges-sample-1/faithfulness.validation.json` | json `kappa` | `probatio validate-judge --run-judge` |
| `0.800` | `docs/CASE_STUDY.md`, `docs/EVALUATION.md` | `examples/consilium/live/results/judges-sample-1/faithfulness.validation.json` | json `agreement` | `probatio validate-judge --run-judge` |
| `0.253` | `README.md`, `docs/CASE_STUDY.md`, `docs/EVALUATION.md` | `PROGRESS.md` | text | `probatio validate-judge --run-judge` |
| `0.675` | `docs/CASE_STUDY.md`, `docs/EVALUATION.md` | `PROGRESS.md` | text | `probatio validate-judge --run-judge` |
| `0.350` | `docs/CASE_STUDY.md`, `docs/EVALUATION.md` | `tests/fixtures/consilium/judge-sample-labeled.csv` | kappa | `pytest tests/test_judge_kappa.py` |
| `0.592` | `docs/CASE_STUDY.md`, `docs/EVALUATION.md` | `tests/fixtures/consilium/judge-sample-2-labeled.csv` | kappa | `pytest tests/test_judge_kappa.py` |
| `$6.037457` | `README.md`, `docs/CASE_STUDY.md`, `docs/EVALUATION.md` | `examples/consilium/live/results/live-baseline.md` | text | R3 |
| `$0.987356` | `README.md`, `docs/CASE_STUDY.md` | `examples/consilium/live/results/live-changed.md` | text | R3 |
| `0.04` | `README.md`, `docs/CASE_STUDY.md`, `docs/EVALUATION.md` | `examples/consilium/live/results/live-baseline.md` | text | R3 |
| `0.13` | `docs/CASE_STUDY.md`, `docs/EVALUATION.md` | `examples/consilium/live/results/live-baseline.md` | text | R3 |
| `0.50` | `docs/CASE_STUDY.md`, `docs/EVALUATION.md` | `examples/consilium/live/results/live-baseline.md` | text | R3 |
| `0.67` | `docs/CASE_STUDY.md`, `docs/EVALUATION.md` | `examples/consilium/live/results/live-baseline.md` | text | R3 |
| `2/43` | `docs/CASE_STUDY.md`, `docs/EVALUATION.md` | `examples/consilium/live/results/live-baseline.md` | text | R3 |
| `6/45` | `docs/CASE_STUDY.md`, `docs/EVALUATION.md` | `examples/consilium/live/results/live-baseline.md` | text | R3 |
| `0/6` | `docs/CASE_STUDY.md`, `docs/EVALUATION.md` | `examples/consilium/live/results/live-baseline.md` | text | R3 |
| `0.30` | `README.md`, `docs/CASE_STUDY.md` | `examples/consilium/live/results/live-changed.md` | text | R3 |
| `0.23` | `docs/CASE_STUDY.md` | `examples/consilium/live/results/live-changed.md` | text | R3 |
| `0.31` | `docs/CASE_STUDY.md` | `examples/consilium/live/results/live-changed.md` | text | R3 |
| `12/43` | `docs/CASE_STUDY.md` | `examples/consilium/live/results/live-changed.md` | text | R3 |
| `14/45` | `docs/CASE_STUDY.md` | `examples/consilium/live/results/live-changed.md` | text | R3 |
| `7/30` | `docs/CASE_STUDY.md` | `examples/consilium/live/results/live-changed.md` | text | R3 |
| `4 of 15` | `README.md` | `examples/consilium/live/results/live-changed.json` | verdicts-moved | R3 |
| `5 of 15` | `README.md` | `examples/consilium/live/results/live-changed.json` | judge-failures | R3 |
| `2 of 45` | `README.md`, `docs/EVALUATION.md` | `examples/consilium/live/variants` | variants-deleted | `probatio freeze-variants` |
| `2 of the 45` | `docs/CASE_STUDY.md` | `examples/consilium/live/variants` | variants-deleted | `probatio freeze-variants` |
| `$0.015070` | `docs/EVALUATION.md` | `examples/consilium/results/replay-priced.md` | text | R2 with `--probatio-prices` |
| `278` | `docs/EVALUATION.md` | `examples/consilium/live/cassettes/test_live` | interactions | `pytest examples/consilium/live --cassette=record` |
| `1.00` | `docs/EVALUATION.md` | `examples/consilium/live/results/live-n10.json` | variance pass-rate | R4 |
| `0.90` | `docs/EVALUATION.md` | `examples/consilium/live/results/live-n10.json` | variance pass-rate | R4 |
| `0.80` | `docs/EVALUATION.md` | `examples/consilium/live/results/live-n10.json` | variance pass-rate | R4 |
| `0.20` | `docs/EVALUATION.md` | `examples/consilium/live/results/live-n10.json` | variance pass-rate | R4 |
| `0.60` | `docs/EVALUATION.md` | `examples/consilium/live/results/live-n10.json` | variance wilson-low | R4 |
| `0.49` | `docs/EVALUATION.md` | `examples/consilium/live/results/live-n10.json` | variance wilson-low | R4 |
| `0.06` | `docs/EVALUATION.md` | `examples/consilium/live/results/live-n10.json` | variance wilson-low | R4 |
| `0.98` | `docs/EVALUATION.md` | `examples/consilium/live/results/live-n10.json` | variance wilson-high | R4 |
| `0.94` | `docs/EVALUATION.md` | `examples/consilium/live/results/live-n10.json` | variance wilson-high | R4 |
| `0.51` | `docs/EVALUATION.md` | `examples/consilium/live/results/live-n10.json` | variance wilson-high | R4 |
| `10/10` | `docs/EVALUATION.md` | `examples/consilium/live/results/live-n10.json` | variance runs-passed | R4 |
| `9/10` | `docs/EVALUATION.md` | `examples/consilium/live/results/live-n10.json` | variance runs-passed | R4 |
| `8/10` | `docs/EVALUATION.md` | `examples/consilium/live/results/live-n10.json` | variance runs-passed | R4 |
| `2/10` | `docs/EVALUATION.md` | `examples/consilium/live/results/live-n10.json` | variance runs-passed | R4 |
| `0.88` | `docs/EVALUATION.md` | `examples/consilium/live/results/live-n10.md` | text | R4 |
| `$3.690520` | `docs/EVALUATION.md` | `examples/consilium/live/results/live-n10.md` | text | R4 |
| `9 of 15` | `docs/EVALUATION.md` | `examples/consilium/live/results/live-n10.json` | variance disagreeing | R4 |
| `15 of 15` | `docs/EVALUATION.md` | `examples/consilium/live/results/live-n10.json` | variance below 0.8 | R4 |
| `4 of 10` | `docs/EVALUATION.md` | `examples/consilium/live/cases` | variance-assertion g-md-018 contains 10 | R4 |
| `7/10` | `docs/EVALUATION.md` | `examples/consilium/live/results/judge-repeatability.json` | judge-repeat passes | R5 |
| `3/10` | `docs/EVALUATION.md` | `examples/consilium/live/results/judge-repeatability.json` | judge-repeat passes | R5 |
| `0.89` | `docs/EVALUATION.md` | `examples/consilium/live/results/judge-repeatability.json` | judge-repeat score | R5 |
| `0.91` | `docs/EVALUATION.md` | `examples/consilium/live/results/judge-repeatability.json` | judge-repeat score | R5 |
| `0.92` | `docs/EVALUATION.md` | `examples/consilium/live/results/judge-repeatability.json` | judge-repeat score | R5 |
| `0.93` | `docs/EVALUATION.md` | `examples/consilium/live/results/judge-repeatability.json` | judge-repeat score | R5 |
| `0.40` | `docs/EVALUATION.md` | `examples/consilium/live/results/judge-repeatability.json` | judge-repeat wilson-low | R5 |
| `0.11` | `docs/EVALUATION.md` | `examples/consilium/live/results/judge-repeatability.json` | judge-repeat wilson-low | R5 |
| `7 of 15` | `docs/EVALUATION.md` | `examples/consilium/live/results/judge-repeatability.json` | judge-repeat not-unanimous | R5 |
| `9 of the 150` | `docs/EVALUATION.md` | `examples/consilium/live/results/judge-repeatability.json` | judge-repeat unparsable | R5 |
| `1 of 15` | `docs/EVALUATION.md` | `examples/consilium/live/results/judge-repeatability.json` | judge-repeat both-verdicts | R5 |
| `137 of 150` | `docs/EVALUATION.md` | `examples/consilium/live/cassettes-n10/test_live_variance` | variance-judge pass | R4 |
| `4 of 150` | `docs/EVALUATION.md` | `examples/consilium/live/cassettes-n10/test_live_variance` | variance-judge fail | R4 |
| `9 of 150` | `docs/EVALUATION.md` | `examples/consilium/live/cassettes-n10/test_live_variance` | variance-judge unparsable | R4 |
| `300` | `docs/EVALUATION.md` | `examples/consilium/live/cassettes-n10/test_live_variance` | samples | R4 |
| `150` | `docs/EVALUATION.md` | `examples/consilium/live/cassettes-judge-x10/judge_repeatability` | samples | R5 |
| `191` | `README.md`, `docs/relations.md` | `docs/relations.md` | text | — |
| `36` | `README.md`, `docs/relations.md` | `docs/relations.md` | text | — |

## Numerals that are not measurements

Every other numeral in `README.md` and in `CHANGELOG.md` is one of these, as is the one threshold
`docs/EVALUATION.md` §8 states rather than measures. Each row says what the numeral is and where it
is fixed; `re:` marks a pattern rather than a literal.

| numeral, as it appears | what it is | fixed in |
|---|---|---|
| `95%` | the confidence level of the only interval in the tool | `src/probatio/stability/wilson.py` |
| `0.8` | the Wilson lower bound `04-DOGFOOD-AND-CASE-STUDY.md` §6 asks the variance study to count cases against; a threshold chosen by the runbook, not a figure any run produced | `docs/EVALUATION.md` §8 |
| `95` | the same level, in the report's column heading | `src/probatio/stability/wilson.py` |
| `p=0.8, n=5` | the demo suite's declared flakiness floor and run length | `examples/demo_suite/test_demo.py` |
| `n = 5` | the run length of R1, restated in prose | `PROGRESS.md` |
| `--runs 5` | the same invocation | `PROGRESS.md` |
| `floor of 1.0` | the default floor a case gets when it declares no tolerance | `src/probatio/stability/stats.py` |
| `0.00` | the value the tool refuses to print for a relation it did not measure, quoted twice as the thing it is not | `src/probatio/metamorphic/evaluate.py` |
| `0.0` | the value `Completion.cost_usd` refuses to stand in with | `src/probatio/providers/base.py` |
| `re:\b\d\d-[a-z0-9-]+\.yaml\b` | the numeric prefix that fixes the load order of the demo suite's case files | `examples/demo_suite/cases` |
| `re:https?://\S+` | a URL: an address, not a measurement | — |
| `Python 3.11` | the language floor | `pyproject.toml` |
| `Pre-1.0` | the release state | `pyproject.toml` |
| `0.1.0` | the version this release carries, in `CHANGELOG.md`'s heading and link label | `src/probatio/__init__.py` |
| `re:2026-09-0\d` | dates on which documentation and citations were checked | — |
| `re:\b4c2114e\b` | the commit that produced R1 | `PROGRESS.md` |
| `re:claude-haiku-4-5-20251001` | a model name | `examples/consilium/live/README.md` |
| `re:claude-opus-5` | a model name | `examples/consilium/live/README.md` |
| `re:gpt-4o-mini-2024-07-18` | a model name | `examples/consilium/README.md` |
| `re:§\d+(\.\d+)?` | a section reference | — |
| `re:Phases? \d+( and \d+)?` | a phase reference | `PROGRESS.md` |

## Which test guards which document

Every document under `docs/` that prints a number has a provenance test that re-derives it from
the artefact named beside it. This table is what stops a document from being added without one.

| document | provenance test |
|---|---|
| `README.md` | `tests/test_docs_provenance.py` |
| `CHANGELOG.md` | `tests/test_docs_provenance.py` |
| `docs/PROVENANCE.md` | `tests/test_docs_provenance.py` |
| `docs/assertions.md` | `tests/test_docs_assertions.py` |
| `docs/providers.md` | `tests/test_docs_providers.py` |
| `docs/relations.md` | `tests/test_docs_relations.py` |
| `docs/stability.md` | `tests/test_docs_stability.py` |
| `docs/CASE_STUDY.md` | `tests/test_docs_case_study.py` |
| `docs/EVALUATION.md` | `tests/test_docs_evaluation.py` |
| `docs/DESIGN.md` | `tests/test_docs_provenance.py` |

`docs/DESIGN.md` is the one document with no figures of its own: it argues about choices, and the
few numbers it repeats — `0.923`, `0.398`, `0.705`, `0.350`, `0.592` — are quoted from the
documents above and carry rows in the measurements table. `tests/test_docs_provenance.py` asserts
that, so a figure introduced into `DESIGN.md` without a row fails.

## What this file does not cover

The claims about Consilium-Health's own repository — its published red-flag recall of 0.500 and
0.893, its two GPT-4o-mini judge kappas, its per-turn costs, its run id and its commit hashes —
name files outside this repository and are labelled as such wherever they appear. Two of them are
nonetheless checked, because the label CSVs those kappas were computed from are committed under
`tests/fixtures/consilium/` and `tests/test_judge_kappa.py` recomputes both; the rest are quoted
and marked as quotations. No test here can make a claim about another repository true.
