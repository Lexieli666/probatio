# PROGRESS.md — Probatio

The run's only durable memory. A fresh session reads this file first, immediately after
`CLAUDE.md`. One phase per session; the checkbox and the run-log line for phase N are committed
with phase N's code.

## Phases

- [x] **Phase 0** — Scaffolding, tooling, CI, `PROGRESS.md`, PyPI name check (spec §2)
- [x] **Phase 1** — `examples/demo_suite/` as the executable design spec (spec §4)
- [x] **Phase 2** — Foundations, `LLMCase`, YAML loader, providers (spec §3.1–3.3)
- [x] **Phase 3** — Assertions and the similarity backend (spec §3.4)
- [x] **Phase 4** — Judge, Cohen's kappa, validation records, `validate-judge` (spec §3.5, §3.13)
- [x] **Phase 5** — Snapshots (spec §3.6)
- [x] **Phase 6** — Budgets and the unenforceable rule (spec §3.7)
- [x] **Phase 7** — Cassettes and `import-cassettes` (spec §3.8, §3.13)
- [ ] **Phase 8** — Metamorphic layer and `freeze-variants` (spec §3.9, §3.13)
- [ ] **Phase 9** — Stability engine, collector, terminal + markdown reporters (spec §3.10–3.12);
  also deletes the `collect_ignore` guard in the demo suite's `conftest.py` **and** the
  repository-level `conftest.py` that repeats it (DECISIONS 16)
- [ ] **Phase 10** — JUnit XML and results JSON reporters (spec §3.11)
- [ ] **Phase 11** — Consilium dogfood, offline, from published traces
- [ ] **Phase 12** — Live Claude CLI steps: record, freeze, validate; the regression case study
- [ ] **Phase 13** — Prior-art table, docs, README final (spec §7)
- [ ] **Phase 14** — Public repo, CI green, PyPI release, `v0.1.0`, resume bullets
- [ ] **Phase 15** — *(optional)* Variance study seed

## Run log

One line per phase, appended in the phase's own commit: date, phase, gate result, notes.

- 2026-09-03 — **Phase 0** — gate green: `pytest -q` 4 passed, 0 skipped, 0 xfailed; coverage of
  `src/probatio` 100% (`coverage run -m pytest`); `ruff check` and `ruff format --check` clean on
  `src tests examples`; `mypy --strict src/probatio` clean (3 source files). Gate condition 5
  (`examples/demo_suite/` byte-identity) is not yet applicable: the demo suite is created in
  Phase 1. Distribution name fixed to `probatio-llm` (DECISIONS 1). Local interpreter is
  Python 3.13.5; CI covers 3.11 and 3.12 (DECISIONS 4).
- 2026-09-03 — **Phase 1** — gate green: `pytest -q` 7 passed, 0 skipped, 0 xfailed; coverage of
  `src/probatio` 100% (`coverage run -m pytest`); `ruff check` and `ruff format --check` clean on
  `src tests examples`; `mypy --strict src/probatio` clean (3 source files).
  `examples/demo_suite/` is committed exactly as drafted: it was already ruff-clean and already
  satisfied the scripted-keyword invariant, so no line of it changed. Ten cases, two
  frozen variant files, four test functions, the `collect_ignore` import guard still in place, so
  `pytest --collect-only examples/demo_suite` reports 0 items and 0 errors until Phase 9.
  `tests/test_demo_spec.py` adds the collection check, the byte-identity check against this commit
  and the scripted-keyword invariant; `tests/conftest.py` enables `pytester`. Gate condition 5 is
  live from this commit onward. DECISIONS 5–10; `docs/DESIGN.md` Phase 1.
- 2026-09-03 — **Phase 2** — gate green: `pytest -q` 128 passed, 0 skipped, 0 xfailed; coverage of
  `src/probatio` 100% (`coverage run -m pytest`); `ruff check` and `ruff format --check` clean on
  `src tests examples` (and on the new repository-level `conftest.py`, which is outside the gate's
  paths); `mypy --strict src/probatio` clean (11 source files); `examples/demo_suite/` byte-identical
  to 8a998af, its introducing commit, with `git status --porcelain` on it empty. Shipped
  `errors.py`, `hashing.py`, `case.py` and `providers/` (`base`, `fake`, `anthropic`, `claude_cli`);
  `probatio/__init__.py` exports `LLMCase`, `load_cases`, `Completion`, `Provider`, `FakeProvider`,
  `ScriptedProvider` and the eight error classes. `load_cases` returns the demo suite's ten cases in
  path order and every one validates, the bare-string input of `copd-spirometry` included.
  `tests/fixtures/claude_cli_payload.json` is a verbatim copy of one real CLI payload and the parser
  is written against it; no test runs the CLI or imports the Anthropic SDK. Gate condition 5's check
  was corrected to compare the introducing commit with the **working tree** and to reject untracked
  files (DECISIONS 17); both failure modes were provoked and seen to fail. One transitional file was
  added: a repository-level `conftest.py` excluding `examples/demo_suite/test_demo.py`, because the
  frozen guard probes `FakeProvider`, which this phase exports (DECISIONS 16). **Phase 9 must delete
  it**, and `tests/test_demo_spec.py` fails if it outlives the missing exports. DECISIONS 11–18;
  `docs/DESIGN.md` Phase 2; new `docs/providers.md`.
- 2026-09-03 — **Phase 3** — gate green: `pytest -q` 229 passed, 0 skipped, 0 xfailed; coverage of
  `src/probatio` 100% (`coverage run -m pytest`); `ruff check` and `ruff format --check` clean on
  `src tests examples` (and on the transitional repository-level `conftest.py`); `mypy --strict
  src/probatio` clean (19 source files); `examples/demo_suite/` byte-identical to 8a998af, with
  `git status --porcelain` on it empty. Shipped `assertions/` (`result`, `backends`, `contains`,
  `schema`, `similarity`, `judge`) and `runner.py`; `probatio/__init__.py` adds `AssertionResult`.
  `evaluate_case` runs every assertion in declaration order and returns one result each; the
  scripted answers in the demo suite's frozen `conftest.py` pass every non-judge assertion of all
  ten cases, and `anxiety-expected-fail` on `"I don't know."` fails both its `contains` and its
  `not_contains` with the details the report will print. The judge evaluator is the unenforceable
  half only: Phase 4 adds the grading and keeps the `judge_provider is None` branch. Similarity
  ships one backend, `TrigramCosine`, and no embedding backend; `docs/assertions.md` carries the
  five-pair score table and `tests/test_docs_assertions.py` reparses it from the markdown, so a
  number in the doc that the code does not produce fails the suite. DECISIONS 19–22;
  `docs/DESIGN.md` Phase 3; new `docs/assertions.md`.
- 2026-09-03 — **Phase 4** — gate green: `pytest -q` 357 passed, 0 skipped, 0 xfailed; coverage of
  `src/probatio` 100% (`coverage run -m pytest`); `ruff check` and `ruff format --check` clean on
  `src tests examples`; `mypy --strict src/probatio` clean (25 source files);
  `examples/demo_suite/` byte-identical to 8a998af with `git status --porcelain` on it empty.
  Shipped `judge/` (`prompt`, `rubric`, `core`, `kappa`, `validation`) and
  `cli.py`'s `validate-judge`; `assertions/judge.py` now grades, keeping its
  `judge_provider is None` branch unchanged. Cohen's kappa reproduces the numbers published in
  Consilium-Health's `docs/EVALUATION.md` from the two CSVs copied into
  `tests/fixtures/consilium/`: sample-1 agreement 0.675 / kappa 0.350, sample-2 agreement 0.800 /
  kappa 0.592 with the table {(unsupported,unsupported): 19, (supported,supported): 13,
  (supported,unsupported): 5, (unsupported,supported): 3}, all from columns `judge_label` and
  `human_label`; a 2x2 example is worked longhand in `tests/test_judge_kappa.py`. The demo suite's
  `JUDGE_PASS` and `JUDGE_FAIL` parse to a passing and a failing verdict and its `fake_judge`
  passes every scripted answer of every judged case, with the rubric found beside the tests
  (DECISIONS 23). `JudgeVerdict` requires `verdict` and `score` and nothing else: a reply with no
  `rationale`, or with an unknown key, grades normally, because in Phase 12 a rejected reply would
  enter `validate-judge --run-judge`'s comparison as a fail grade and lower the measured kappa for
  a formatting reason (DECISIONS 29). A graded judge with no validation record is `unenforceable`
  while its verdict still counts, and editing the rubric makes an enforceable grade unenforceable
  again.
  `probatio validate-judge` runs both modes offline: `--min-kappa 0.6` on sample-1 exits 1 after
  writing the record, and `--run-judge` is exercised only through an injected `FakeProvider`,
  which a test also uses to prove the judge never sees the label columns. Deleted
  `tests/test_assertions_judge.py::test_phase_3_reports_unenforceable_even_when_a_provider_is_passed`,
  which pinned the Phase 3 stub, and changed `main()` to take an argv sequence, so
  `tests/test_smoke.py` now calls `main([])` (DECISIONS 27). `docs/assertions.md`'s judge section
  gained the validation workflow and the unvalidated-judge warning, and its similarity-tau
  recommendation was replaced by the two values the demo suite commits (0.30 and 0.35) with the
  general recommendation deferred to Phase 11; `tests/test_docs_assertions.py` enforces both.
  The frozen demo suite's committed constants reach the tests that need them through session
  fixtures in `tests/conftest.py` (`demo_conftest`, `judge_pass`, `judge_fail`, `fake_judge`,
  `scripted_answer`, and the three paths), so no module under `tests/` imports a sibling by bare
  name. DECISIONS 23–29; `docs/DESIGN.md` Phase 4.
- 2026-09-03 — **Phase 5** — gate green: `pytest -q` 390 passed, 0 skipped, 0 xfailed; coverage of
  `src/probatio` 100% (`coverage run -m pytest`); `ruff check` and `ruff format --check` clean on
  `src tests examples`; `mypy --strict src/probatio` clean (26 source files);
  `examples/demo_suite/` byte-identical to 8a998af with `git status --porcelain` on it empty.
  Shipped `snapshot.py`: `Baseline`, `BaselineAssertion`, `SnapshotResult`, `BaselineStore` and
  `prompt_hash`. The store is constructed with a `baseline_dir` (default
  `Path.cwd() / ".probatio" / "baseline"`; Phase 9's plugin passes the rootdir-based and
  `--baseline-dir` values, as `schema_file` and rubric names already take their directories,
  DECISIONS 19, 23) and an injectable clock, so no test in this repository reads the wall clock.
  `BaselineStore.compare` takes the suite, the case, the prompt hash, the assertion results, the
  output, the model and an update flag and returns a `SnapshotResult` in one of the six states —
  `recorded`, `updated`, `unchanged`, `prompt_changed`, `scores_changed`, `output_changed` — or
  `None` for a `snapshot: off` case, which is never read and never written (DECISIONS 31). It
  never raises for drift; Phase 9's `check` turns a failing state into the failure, reusing the
  `BaselineDriftError` text this module already composed. Files are one per case at
  `<baseline_dir>/<suite>/<case_id>.json`, written with sorted keys, indent 2 and a trailing
  newline, and a test proves two recordings of the same results are byte-identical. `scores` mode
  fails on any flipped verdict or any score moving more than 0.05 — rounded to six decimals on
  both sides so a value re-read from JSON never differs from itself, and so that 0.06 is drift,
  0.04 and exactly 0.05 are not (DECISIONS 32) — with a per-assertion before/after table; `None`
  to a number and back are changes. `output` mode fails on a text difference with a unified diff
  capped at 40 lines including its truncation note. `prompt_changed` takes precedence over both
  and prints one line, no table and no diff. A baseline whose assertion list no longer lines up
  with the case's, and a case whose snapshot mode changed, are drift in the case's own mode with
  an `absent`-padded table, not `prompt_changed` (DECISIONS 30); an unparsable baseline is a
  `ProbatioConfigError` rather than a silent re-record (DECISIONS 33); suite and case names are
  refused if they would escape the baseline directory (DECISIONS 34). **Deferred to Phase 9: the
  `pytester` version of spec §3.6's acceptance — first run records, a changed output fails with a
  diff, `--update-baseline` makes the next run pass, a changed `system` prompt reports "prompt
  changed" — because it needs the `--update-baseline` flag and the `probatio` fixture, neither of
  which exists before Phase 9.** All four are covered as unit tests here.
  DECISIONS 30–34; `docs/DESIGN.md` Phase 5.
- 2026-09-04 — **Phase 6** — gate green: `pytest -q` 444 passed, 0 skipped, 0 xfailed; coverage of
  `src/probatio` 100% (`coverage run -m pytest`); `ruff check` and `ruff format --check` clean on
  `src tests examples`; `mypy --strict src/probatio` clean (27 source files);
  `examples/demo_suite/` byte-identical to 8a998af with `git status --porcelain` on it empty.
  Shipped `budget.py`: `ModelPrice`, `PriceTable`, `price_completions`, `case_cost`,
  `evaluate_budget` and `SuiteBudget`. `PriceTable.load` reads a YAML mapping of model name to
  `{input_per_mtok, output_per_mtok}`; an unknown key, a negative price and a price that is not a
  number (a quoted string and `true` included, DECISIONS 40) are errors naming the file and the
  model, and an empty or all-comments file is an empty table (DECISIONS 35). It prices a completion
  from its model and token counts, returning `None` — never `0.0` — when the model is absent or
  either count is unknown, and it prices only completions whose `cost_usd` is still `None`, so the
  Claude CLI's reported notional total is never overwritten (DECISIONS 41). `AnthropicProvider`
  gained the optional `prices` argument spec §3.3 describes and applies it at completion time,
  which closes the deferral recorded in DECISIONS 15. `evaluate_budget` returns
  `budget_cost` and `budget_latency` results, in that order, for the ceilings a case declares:
  cost is the sum over all completions against `budget.max_cost_usd`, and a cost ceiling with any
  completion still unpriced is `AssertionResult(passed=False, unenforceable=True)` whose detail is
  spec §3.7's sentence plus `pytest --probatio-prices <path>` and every unpriced model
  (DECISIONS 37), never a pass; latency is the sum of `latency_ms` against `budget.max_latency_ms`,
  falling back to the `--max-latency` default when the case declares none, and is enforceable
  wherever a call was made. Neither result carries a score (DECISIONS 38), and a case with no
  ceiling of a kind gets no result of that kind. A case that recorded **no provider calls at all**
  has both ceilings reported unenforceable, with the detail `<kind> ceiling for <case> is
  unenforceable: no provider calls were recorded` and no fix clause, and `case_cost([])` is `None`
  rather than `0.0`, so such a case reaches the suite total as unknown rather than as free: a pass
  over zero calls is the vacuous pass the brief forbids and would hide a Phase 9 collector that
  was never wired up (DECISIONS 36, reversing this phase's first answer).
  `SuiteBudget` records `(case_id, cost)` per case, sums repeats under one id, keeps unknown-cost
  cases as unknown rather than as zero, and renders one line naming the total, the `--max-cost`
  ceiling, the three dearest cases and the unknown ones, composed through `BudgetExceededError`
  (DECISIONS 39). Whether relation-variant and judge calls count toward a case's budget is Phase 9's
  question, where the calls are collected; this phase prices what it is handed.
  `examples/prices.example.yaml` ships the structure with every entry commented out and no real
  prices, and a test shows all ten demo-suite cost ceilings are unenforceable against it.
  `docs/providers.md` gained a cost-semantics section, and `tests/test_docs_providers.py` reads its
  three dollar figures back out of `tests/fixtures/claude_cli_payload.json`
  (total $0.003769, answering model $0.002695, the CLI's own side model $0.001074) and fails on any
  fourth figure in that section. **Deferred to Phase 9: the `pytester` half of spec §3.7's
  acceptance — a suite-level cost overrun producing a non-zero pytest exit status and printing the
  overrun line — because it needs `--max-cost`, `pytest_sessionfinish` and the `probatio` fixture,
  none of which exists before Phase 9.** The message itself, the ranking and the unknown-cost
  accounting are covered here as unit tests. DECISIONS 35–41; `docs/DESIGN.md` Phase 6.
- 2026-09-04 — **Phase 7** — gate green: `pytest -q` 517 passed, 0 skipped, 0 xfailed; coverage of
  `src/probatio` 100% (`coverage run -m pytest`); `ruff check` and `ruff format --check` clean on
  `src tests examples`; `mypy --strict src/probatio` clean (29 source files);
  `examples/demo_suite/` byte-identical to 8a998af with `git status --porcelain` on it empty.
  Shipped `cassette.py` (`interaction_key`, `Interaction`, `Cassette`, `ActiveCase`,
  `CassetteStore`, `CassetteProvider`, `ImportedCall`, `parse_trace_line`, `read_trace`,
  `import_cassettes`) and `cli.py`'s `import-cassettes`. `CassetteProvider(inner, store, mode)`
  satisfies the `Provider` protocol and reports the inner adapter's `name`, so the SUT and the
  Judge see no difference; `replay` never calls `inner` (`FakeProvider.call_count == 0`), `record`
  writes the tape after every call, and `off` forwards `prompt`, `system` and `**params`
  untouched. The **store owns the active context**: `begin_case(suite, case_id, run_index)` — which
  Phase 9's fixture will call before the SUT runs — plus a `judge_calls(template_hash)` context
  manager that `CassetteProvider` re-exposes and `Judge.grade_with_completion` enters when the
  provider it holds offers one, so the judge template hash reaches the key with no change to the
  `Provider` protocol and no reserved parameter that could leak to a live adapter (DECISIONS 42);
  two tests pin it, one showing a judge call and a SUT call with identical prompt text getting
  different keys, one asserting the inner provider's recorded `system` and `params` are exactly
  what the caller passed. The key is spec §3.8's five parts with `model` lifted out of `params`
  rather than hashed twice (DECISIONS 43), and its model is the **effective** one:
  `resolve_model` restates the precedence both live adapters already implement —
  `params["model"]`, else the adapter's own constructor model, which is what `--probatio-model`
  fills in — and `CassetteProvider.inner_model` supplies that fallback to the store in both record
  and replay, with the params forwarded to `inner` untouched. Without it a case that names no
  model, which is all ten of the demo suite's, would key blank, and a tape recorded through
  `ClaudeCLIProvider(model="A")` would replay silently through `model="B"`; a test records through
  `FakeProvider(model="m1")`, gets `StaleCassetteError` from an `m2` wrapper, and replays from a
  second `m1` wrapper with `call_count == 0` (DECISIONS 43, amended). `Interaction` carries the
  resolved model, so a stale tape says which model it belongs to. Files are
  `<cassette_dir>/<suite>/<case_id>.json` with
  the spec's five top-level fields; a mutated prompt, a changed model and a changed param each
  raise `StaleCassetteError` naming the case, saying the prompt, model or params changed, and
  giving `pytest --cassette=record`; a missing file raises `MissingCassetteError` naming the same
  command; an unparsable tape is a `ProbatioConfigError`, as a corrupt baseline is (DECISIONS 33).
  Recording three runs then replaying five returns samples 0, 1, 2, 0, 1; a one-sample tape
  replayed under several runs adds one store-level note carrying spec §3.8's phrase
  `1 recorded sample`, put on the store rather than in the completion's `raw` so that
  record-then-replay round-trips a `Completion` exactly, `raw` included. Re-recording a key
  replaces its samples the first time the session sees it and appends thereafter, so `--runs 3`
  twice leaves three samples and not six (DECISIONS 44). Two recordings through `FakeProvider`
  with the same clock are byte-identical. `probatio import-cassettes --from JSONL --suite NAME
  --out DIR` (plus an optional `--provider`, default `imported`) turns a three-line trace into
  tapes that replay with zero inner calls, several lines with one case and one key becoming one
  interaction with several samples in file order; a malformed line is a `ProbatioConfigError`
  naming the line number and the file, unknown keys included (DECISIONS 45). Phase 11 turns
  Consilium traces into exactly this JSONL. The timestamp helper was the third copy, so
  `snapshot.py`, `judge/validation.py` and `cassette.py` now share **`src/probatio/artefacts.py`**,
  which holds `Clock`, `utc_now`, `format_instant`, `timestamp`, `NAME_PATTERN`,
  `check_path_segment` and `write_json` — the clock, the DECISIONS 34 path-segment check and the
  sorted-keys/indent-2/trailing-newline writer that all three stores had copied (DECISIONS 46);
  `judge.validation.utc_now` is gone and `cli.py` calls `artefacts.timestamp()`. **Deferred to
  Phase 9: the `pytester` half of spec §3.12's acceptance — `--cassette=replay` with no tapes
  failing with `MissingCassetteError` in the test output — because it needs the `--cassette` flag
  and the `probatio` fixture, neither of which exists before Phase 9.** The error itself, its text
  and its zero-inner-call guarantee are covered here as unit tests. DECISIONS 42–46;
  `docs/DESIGN.md` Phase 7.
