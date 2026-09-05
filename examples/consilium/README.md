# Consilium dogfood suite (offline)

Probatio's first real user is [Consilium-Health](https://github.com/Lexieli666/consilium-health),
a multi-agent retrieval-grounded medical QA system with a published evaluation run. This directory
replays fifteen of its golden items through Probatio, offline, from that run's recorded traces:
two suites (`test_full.py` for the `full` pipeline, `test_baseline.py` for the `baseline_llm`
configuration), one case list, and cassettes built from the traces so CI needs no model and no key.

Every assertion here is derived from a field of `golden.jsonl`, never from reading an answer. That
is the difference between a regression suite and a test written to pass.

## Provenance

| artefact | origin |
|---|---|
| `golden.jsonl` (150 items) and `safety/escalation.py` | Consilium-Health repository at commit `109a744` (2026-08-30) |
| traces (`full-*.json`, `baseline_llm-*.json`) | the published run `20260830T170133Z`, produced at commit `c1436bd`; `eval/results/published/traces/` in that repository |
| `cases/*.yaml`, `CASES.txt` | derived from the above by `convert_traces.py`; see "Case selection" |
| `cassettes/test_full/`, `cassettes/test_baseline/` | built from the traces by `probatio import-cassettes`; a suite is named by its test module's stem |
| `golden-subset.jsonl` | the fifteen selected items of `golden.jsonl`, verbatim and in `CASES.txt` order, so `cases/*.yaml` can be re-emitted and checked without the full file |
| `prices.yaml` | the one model the traces name, `gpt-4o-mini-2024-07-18`, at the rates a human read off the provider's price page: $0.15 input and $0.60 output per Mtok, checked 2026-09-04, with the URL and the row in the file's header. Consilium ships `eval/pricing.yaml` empty by design and this file shipped that way too, so the run recorded before `e4f10d3` is the **unpriced** one — `results/replay-unpriced.*`, where every cost ceiling is unenforceable and the total is unknown. `results/replay-priced.*` is the run against these rates |
| `tests/fixtures/consilium/escalation_phrases.txt` | `ESCALATION_PHRASES` copied out of `safety/escalation.py`, one per line, so the re-emission test needs nothing outside this repository |

The traces themselves are not committed here (they are ~9.5 MB and already public in Consilium).
`convert_traces.py` takes their path as an argument.

## Case selection

Fifteen items, chosen by rule so the selection can be rederived by anyone from `golden.jsonl`:

1. The four headline items of Consilium's `docs/FAILURE_CASES.md`: `g-su-001`, `g-gh-017`,
   `g-cc-017`, `g-ge-024`.
2. Each of the five id blocks (`g-gh`, `g-su`, `g-cc`, `g-ge`, `g-md`) is then filled to three
   items. Within a block, unchosen items with `red_flag: true` are taken first in id order, then
   remaining items in id order.

Step 2's red-flag-first ordering exists because the brief requires at least five red-flag items and
a plain first-by-id fill yields only three (the red-flag items are concentrated in `g-su` and
`g-md`). The ordering was fixed before any trace was read. The result is in `CASES.txt`: fifteen
cases, six with `red_flag: true`.

## What each case asserts

| golden field | assertion |
|---|---|
| `red_flag: true` | `contains any:` the `ESCALATION_PHRASES` list copied verbatim from Consilium's `safety/escalation.py`; `metadata.assertion_source` names the file. Consilium's own red-flag-recall metric is this list applied to the delivered answer. |
| `reference_answer` | `similarity` with `tau: 0.30` (trigram cosine, see `docs/assertions.md`) |
| every case | `not_contains all: ["As an AI language model"]`; `budget: {max_cost_usd: 0.005, max_latency_ms: 15000}`; `snapshot: scores` |

The phrases are the same list, but the matching is not identical: Consilium compiles each phrase
into a regular expression with flexible internal whitespace, so that a line break inside "seek
immediate care" still counts, while Probatio's `contains` is a plain case-insensitive substring
test. The stricter test is Probatio's, and where the two would disagree it is because an answer
was wrapped, not because it escalated differently.

No `judge` assertion is present: the traces hold no judge output, and a judge needs a provider
call. There are no relation decorators either: a metamorphic variant is a different prompt and so
a different cassette key, and no answer to a question Consilium was never asked exists to replay.

`live/` carries both, on tapes recorded against a real model in Phase 12. It is a separate suite
answering a separate question — its system under test is a single-call grounded QA app, not
Consilium's pipeline — and it has its own `live/README.md`.

The cost ceiling exists so that the price table matters: without `--probatio-prices`, every cost
ceiling here is reported as **unenforceable** (the traces carry tokens but no dollar cost), which
is the rule from `docs/providers.md` doing its job on real data.

## How the suites run

`app.py` sends the golden question as the prompt, a fixed system prompt, and two params: the
configuration name (`full` or `baseline_llm`) and the model the traces name. Cassette keys are
hashes of prompt, system, model and params, so the suite passes exactly what the tapes were built
from; that is what lets `--cassette=replay` (the default) find every interaction.

```bash
pytest examples/consilium -q --ignore=examples/consilium/live \
       --cassette-dir examples/consilium/cassettes                 # replay; cost ceilings unenforceable
pytest examples/consilium -q --ignore=examples/consilium/live \
       --cassette-dir examples/consilium/cassettes \
       --probatio-prices examples/consilium/prices.yaml \
       --probatio-results build/consilium.json --probatio-report build/consilium.md
```

`--cassette-dir` is needed because the default tape directory is `cassettes/` under the pytest
rootdir, and this suite keeps its tapes beside its cases. `--ignore=examples/consilium/live` is
needed because Phase 12's live suite is a subdirectory of this one and keeps its tapes and its
baselines somewhere else; without it these commands would collect it and every live case would
miss its tape (DECISIONS 87). It changes nothing about what the two commands produce for the
thirty offline cases: run with it, both commands reproduce the committed `results/replay-*.json`
and `results/replay-*.md` byte for byte.

**Both commands exit non-zero, and that is the result.** `test_baseline` passes; `test_full` fails
its red-flag cases, because the full pipeline's delivered answers did not escalate where the plain
baseline's did. That is the regression Consilium published in its own `docs/FAILURE_CASES.md`
before Probatio existed, and this suite is what a CI job would have shown on the commit that
introduced it. The per-case verdicts of the run that recorded the committed baselines are in this
repository's `PROGRESS.md`, under Phase 11; `docs/CASE_STUDY.md` (Phase 12) reads them back out of
the results JSON.

This suite is deliberately not in the repository's `testpaths`: a plain `pytest -q` would collect
it without `--cassette-dir` and every case would miss its tape. `tests/test_consilium_suite.py`
runs both suites through `pytester` against the committed tapes instead, so the gate covers them.

Baselines are written to `.probatio/baseline/test_full/` and `.probatio/baseline/test_baseline/`
under the repository root and are committed.

## Regenerating

```bash
git clone https://github.com/Lexieli666/consilium-health ../consilium-health
python examples/consilium/convert_traces.py \
    --traces ../consilium-health/eval/results/published/traces \
    --golden ../consilium-health/data/golden.jsonl \
    --escalation ../consilium-health/src/safety/escalation.py \
    --cases examples/consilium/CASES.txt --out build/
probatio import-cassettes --from build/full.jsonl --suite test_full --out examples/consilium/cassettes
probatio import-cassettes --from build/baseline_llm.jsonl --suite test_baseline --out examples/consilium/cassettes
```

`--escalation` is only read by `--emit-cases`, which rewrites `CASES.txt` and `cases/*.yaml` from
the golden file (the case files go in the `cases/` beside the `CASES.txt` named by `--cases`).
`--traces` and `--out` are only read by the conversion, so either half runs on its own. The
fifteen selected golden items are committed verbatim as `golden-subset.jsonl` so that a test can
regenerate `cases/*.yaml` from them and assert byte identity with the committed files; run against
the full `golden.jsonl` the same rule selects the same fifteen ids.
