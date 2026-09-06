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
- [x] **Phase 8** — Metamorphic layer and `freeze-variants` (spec §3.9, §3.13)
- [x] **Phase 9** — Stability engine, collector, terminal + markdown reporters (spec §3.10–3.12);
  also deletes the `collect_ignore` guard in the demo suite's `conftest.py` **and** the
  repository-level `conftest.py` that repeats it (DECISIONS 16)
- [x] **Phase 10** — JUnit XML and results JSON reporters (spec §3.11)
- [x] **Phase 11** — Consilium dogfood, offline, from published traces
- [x] **Phase 12** — Live Claude CLI steps: record, freeze, validate; the regression case study
- [x] **Phase 13** — Prior-art table, docs, README final (spec §7)
- [x] **Phase 14** — Public repo, CI green, PyPI release, `v0.1.0`, resume bullets
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
- 2026-09-04 — **Phase 8** — gate green: `pytest -q` 653 passed, 0 skipped, 0 xfailed; coverage of
  `src/probatio` 100% (`coverage run -m pytest`); `ruff check` and `ruff format --check` clean on
  `src tests examples` (and on the transitional repository-level `conftest.py`); `mypy --strict
  src/probatio` clean (35 source files); `examples/demo_suite/` byte-identical to 8a998af with
  `git status --porcelain` on it empty. Shipped `metamorphic/` (`base`, `relations`, `variants`,
  `evaluate`, `freeze`), `cli.py`'s `freeze-variants`, the `probatio_relation` marker registration
  in `plugin.py`, and `docs/relations.md`; `probatio/__init__.py` adds `order_invariant`,
  `distractor_robust`, `format_jitter` and `paraphrase_invariant`. `flaky_tolerant` is still
  absent, so the demo's import still fails on it and the repository-level exclusion stays, which
  `tests/test_demo_spec.py`'s lifecycle test confirms.
  `Relation` is an ABC with `name`, `citation`, `variants(case)` and `applicable(case)`; `Variant`,
  `Flip` and `RelationResult` are spec §3.9's models, frozen and `extra="forbid"`; the four
  relations register themselves in `RELATIONS` and no fifth name is registered. `evaluate_relation`
  takes the relation, the case, the original verdict and results, and a callable evaluating one
  case, so the arithmetic is testable with no provider and no pytest session: 1 flip in 4 variants
  is 0.25, a variant passing where the original failed counts too, and a relation that is not
  applicable or generated nothing reports `violation_rate=None` with `n_variants=0` — never 0.0
  (DECISIONS 8). `order_invariant` on a two-element list yields exactly one variant, because the
  loop takes `min(k, distinct non-identity orderings)` with duplicates divided out (DECISIONS 47);
  `format_jitter`'s three transforms are fixed functions and a subprocess test shows its variants
  — and `order_invariant`'s seeded permutations — are byte-identical across two processes.
  `paraphrase_invariant` with no file raises `MissingVariantsError` whose message carries a
  runnable `probatio freeze-variants --cases <dir> --field <field> --provider claude-cli --k 3
  --out <dir>`, naming the sibling `cases/` of the variants directory (DECISIONS 53); a file whose
  `case_id` or `field` disagrees is a `ProbatioConfigError`. A file holding **fewer than `k`**
  paraphrases is used as it stands and `n_variants` reports the two, three or however many were
  evaluated, because the runbook's Phase 12 tells the human freezing against a live model to
  delete the rewordings that changed the meaning and note the deletion in the file's header;
  only an empty `variants` list raises `MissingVariantsError` ("exists but holds no variants"),
  with the same command plus `--force` (DECISIONS 52, reversing this phase's first answer).
  `probatio freeze-variants` asks for `k` paraphrases as a JSON list, refuses a
  reply that is not exactly `k` distinct non-empty strings none of which is the original, writes
  provenance from an injected clock, skips existing files unless `--force`, skips a case with no
  text at `--field` but errors when **no** case has it (DECISIONS 55), and with `--provider fake`
  calls nothing at all, writing `provider: mechanical` and warning on stderr (DECISIONS 54); the
  model path is tested by replacing `cli.build_provider` with a `FakeProvider`, so no test reaches
  a provider it did not construct. Two recordings with the same clock are byte-identical.
  **Measured on the frozen demo suite** (`tests/test_metamorphic_demo.py`, against its scripted
  fake, no numbers copied into any doc): both committed variants files load with
  `provider: human`, `model: null`, `prompt_hash: null` and `created: "2026-09-03"`;
  `order_invariant` and `distractor_robust` flip nothing anywhere; whitespace and markdown jitter
  flip nothing; `copd-spirometry` is not applicable for all three field relations;
  `htn-definition`'s frozen paraphrases show exactly one violation in three, on `paraphrase-3`,
  with `contains`, `similarity` and `judge` all moving, and `t2d-metformin`'s show none.
  **One README claim holds only in part and cannot hold in full**: the casing variant flips
  `htn-definition`, `htn-first-line` and `t2d-screening-json`, but not `gerd-alarm-features` or
  `insomnia-first-line`, whose keywords appear in lower case in their own **documents**, which
  `format_jitter(field="input.question")` does not touch, so the scripted provider still matches
  and the verdict cannot move. The frozen directory is unedited; the measured outcome and the
  reason are both asserted as tests, and the correction is written down in an
  "Errata for `demo_suite/README.md`" section of `examples/README.md`, which is tracked and
  outside the frozen directory, with a test asserting that section names both cases and both
  pinning tests (DECISIONS 51). Lifted `case.check_field_path` out of the
  private `_segments` and added `artefacts.write_yaml`, the fourth persisted file kind's writer
  (DECISIONS 56). Narrowed two older tests rather than deleting them: `tests/test_public_api.py`
  compares against `PHASE_3_EXPORTS | PHASE_8_EXPORTS` and still asserts `flaky_tolerant`,
  `CaseResult` and `RunReport` absent, and `tests/test_smoke.py` now asserts
  `plugin.pytest_configure` is callable (DECISIONS 58). `tests/conftest.py` gained a `demo_app`
  fixture, because a relation measured on the demo needs the prompt the app really builds, which
  the keyword-based `scripted_answer` fixture bypasses. **Deferred to Phase 9: everything the
  `probatio` fixture owns** — reading the marks off an item, running `evaluate_relation` after the
  original case inside `check`, and the report's relations table; `plugin.py` registers the marker
  and nothing else. DECISIONS 47–58; `docs/DESIGN.md` Phase 8; new `docs/relations.md`.
- 2026-09-04 — **Phase 9** — gate green: `pytest -q` 856 passed, 0 skipped, 0 xfailed; coverage of
  `src/probatio` 100% (`coverage run -m pytest`); `ruff check` and `ruff format --check` clean on
  `src tests examples`; `mypy --strict src/probatio` clean (44 source files);
  `examples/demo_suite/` differs from 8a998af by **the one sanctioned edit and nothing else**, with
  no untracked file inside it. Shipped `stability/` (`wilson`, `stats`), `collector.py`,
  `session.py`, `reporters/` (`tables`, `terminal`, `markdown`) and the whole of `plugin.py`;
  `probatio/__init__.py` now exports spec §6's complete list, adding `flaky_tolerant`,
  `CaseResult` and `RunReport`. New `docs/stability.md`, enforced by `tests/test_docs_stability.py`,
  which re-derives the two intervals it quotes from `wilson_interval`.
  **The sanctioned edit (DECISIONS 62):** the five-line `try/except ImportError` guard is gone from
  `examples/demo_suite/conftest.py`, and the repository-level `conftest.py` that repeated the
  exclusion (DECISIONS 16) is deleted. `tests/test_demo_spec.py` now holds the guard text as a
  constant and asserts that `conftest.py` is the only file that differs from the Phase 1 commit and
  that it equals the committed original with exactly that block removed once; the two Phase 2 tests
  about the transitional state retired with it.
  `wilson_interval` returns exactly `(0.0, upper)` at k=0 and `(lower, 1.0)` at k=n, and (k=8,
  n=10) is checked against the formula written out step by step in the test. `--runs N` runs
  `check` N times with the same callable and the same fixtures; `@flaky_tolerant(p, n)`'s `n`
  overrides `--runs` and the case passes at `pass_rate >= p`, which is why the demo's flaky case
  runs five times even under a plain `pytest`. A verdict is the exact assertions and nothing else
  (spec §0); budgets and snapshots fail the case beside it, so a variant four milliseconds slower
  is never a metamorphic violation (DECISIONS 63). The reported per-case verdict is the majority
  verdict and the row is explained by a run that agreed with it, because the flaky case fails run
  zero (DECISIONS 64). `n_below_floor` counts the repeated cases only and prints its denominator
  (DECISIONS 65). Budgets are per run and any run over a ceiling fails the case (DECISIONS 59);
  a case's ceiling covers the calls its system under test made, while judge and variant calls reach
  the `--max-cost` session total only (DECISIONS 60, closing Phase 6's open question). Probatio
  budgets the calls it can see — its own instrumented fixtures, plus the `Completion` a system
  under test returns, de-duplicated by identity — which is what makes the demo's own overridden
  provider measurable at all (DECISIONS 66). Budget results are recorded into a `scores` baseline
  with `score: null`, closing DECISIONS 38. `--runs` registers with a `--probatio-runs` fallback
  under a fixed destination (DECISIONS 61); `--probatio-junit` and `--probatio-results` are
  registered so `--help` is complete and refused at configure time until Phase 10 (DECISIONS 67);
  any non-fake provider without `--probatio-model` is refused, and a missing tape's fix clause now
  names the configured provider and model (DECISIONS 69). A missing or stale tape is added to the
  report's warnings **and** re-raised (DECISIONS 72). `Probatio` lives in `session.py` so that
  `check` is testable with no pytest session at all, which is what 38 of this phase's tests do
  (DECISIONS 70).
  **The four deferred `pytester` acceptances all landed here**: spec §3.6's snapshot lifecycle
  (first run records, a changed output fails with a unified diff, `--update-baseline` makes the
  next run pass, a changed `system` reports `prompt_changed`), spec §3.7's suite-level cost overrun
  (non-zero exit plus the overrun line, with every case still passing), spec §3.8's
  `--cassette=replay` with no tapes, and spec §3.12's three-case suite under `--runs 3`. The
  results-JSON and JUnit halves of spec §3.12's acceptance wait for Phase 10, which is what those
  two flags now say when given.
  **The demo suite passes unmodified**, 12 tests, offline. Its three `snapshot: scores` baselines
  are committed under `.probatio/baseline/test_demo/` (DECISIONS 71), so from this commit the
  gate compares against them rather than re-recording. `pytest examples/demo_suite --runs 5`,
  run at this commit, verbatim — **this is the first committed run the README may quote from in
  Phase 13**:

```
  ============================= test session starts ==============================
  platform darwin -- Python 3.13.5, pytest-9.1.1, pluggy-1.6.0
  rootdir: /Users/yutongzhao/code/probatio
  configfile: pyproject.toml
  plugins: probatio-llm-0.1.0.dev0
  collected 12 items

  examples/demo_suite/test_demo.py ............                            [100%]

  =================================== probatio ===================================
  cases:
    case                   verdict  assertions  pass rate  95% Wilson    floor  cost       latency ms  snapshot
    ---------------------  -------  ----------  ---------  ------------  -----  ---------  ----------  ---------
    htn-definition         pass     4/4         1.00       [0.57, 1.00]  1.00   $0.000500  100         unchanged
    htn-first-line         pass     3/3         1.00       [0.57, 1.00]  1.00   $0.000500  100         unchanged
    t2d-screening-json     pass     2/2         1.00       [0.57, 1.00]  1.00   $0.000500  100         -
    t2d-metformin          pass     4/4         1.00       [0.57, 1.00]  1.00   $0.000500  100         unchanged
    gerd-alarm-features    pass     3/3         1.00       [0.57, 1.00]  1.00   $0.000500  100         -
    copd-spirometry        pass     2/2         1.00       [0.57, 1.00]  1.00   $0.000500  100         -
    red-flag-chest-pain    pass     3/3         1.00       [0.57, 1.00]  1.00   $0.000500  100         -
    insomnia-first-line    pass     4/4         1.00       [0.57, 1.00]  1.00   $0.000500  100         -
    htn-definition         pass     4/4         1.00       [0.57, 1.00]  1.00   $0.000500  100         unchanged
    t2d-metformin          pass     4/4         1.00       [0.57, 1.00]  1.00   $0.000500  100         unchanged
    anxiety-expected-fail  FAIL     1/3         0.00       [0.00, 0.43]  1.00   $0.000500  100         -
    flu-antivirals-flaky   pass     2/2         0.80       [0.38, 0.96]  0.80   $0.000500  100         -

  relations:
    relation              cases  n/a  violations  mean rate  worst case           worst rate
    --------------------  -----  ---  ----------  ---------  -------------------  ----------
    distractor_robust     7      1    0/70        0.00       gerd-alarm-features  0.00
    format_jitter         7      1    15/105      0.14       htn-definition       0.33
    order_invariant       6      2    0/50        0.00       gerd-alarm-features  0.00
    paraphrase_invariant  2      0    5/30        0.17       htn-definition       0.33

  stability score: 0.90 over 12 repeated case(s)
  cases whose Wilson lower bound is below their floor: 12 of 12
  cost: $0.031500 (no --max-cost ceiling)

  warnings (7):
    - htn-definition: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
    - htn-first-line: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
    - t2d-metformin: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
    - gerd-alarm-features: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
    - red-flag-chest-pain: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
    - insomnia-first-line: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
    - anxiety-expected-fail: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
  ============================== 12 passed in 0.09s ==============================
```

  DECISIONS 59–72; `docs/DESIGN.md` Phase 9; new `docs/stability.md`.

- 2026-09-04 — **Phase 10** — gate green: `pytest -q` 906 passed, 0 skipped, 0 xfailed; coverage of
  `src/probatio` 100% (`coverage run -m pytest`); `ruff check` and `ruff format --check` clean on
  `src tests examples`; `mypy --strict src/probatio` clean (46 source files);
  `examples/demo_suite/` still differs from 8a998af by the one sanctioned Phase 9 edit and nothing
  else, with no untracked file inside it, and `pytest examples/demo_suite --runs 5` reproduces the
  Phase 9 run above **line for line**, tables, rates, warnings and total alike. Shipped
  `reporters/results.py` (`render_results`, `write_results`, `read_results`) and
  `reporters/junit.py` (`render_junit`, `write_junit`); `plugin.write_artefacts` writes all three
  optional files from `pytest_terminal_summary` and names each one (DECISIONS 77).
  **The results JSON is the report itself**: `report.model_dump(mode="json")` through
  `artefacts.write_json`, so sorted keys, indent 2 and one trailing newline, and
  `RunReport.model_validate(json.loads(text)) == report` for a report carrying a failing case, a
  flaky one, a snapshot, budget results, relation flips, warnings and a cost ceiling — a
  projection would be a second schema to keep in step, which is what it is not (`docs/DESIGN.md`
  Phase 10). Writing the same report twice is byte-identical, and the derived `n_failed` is a
  property rather than a stored field.
  **A report entry is keyed on `(test node id, case id)`** (DECISIONS 73): `CaseResult` gained a
  required `node_id`, `collector.case_key` returns the pair, the `probatio` fixture passes
  `request.node.nodeid`, and a `Probatio` built outside a session falls back to the suite name.
  The demo's `htn-definition` and `t2d-metformin` are each checked by `test_case` and again by
  `test_paraphrase`; both now carry two distinct keys, and the JUnit file's twelve
  `(classname, name)` pairs are twelve distinct pairs. One test checking one case twice gets a
  ` #2` suffix rather than a merge.
  **The JUnit file** is a `<testsuites>` root over one `<testsuite name="probatio">` with `tests`,
  `failures`, `errors`, `skipped` and `time`; `classname` is the node id and `name` is the case
  id. Per-case `<properties>` carry `pass_rate`, `wilson_low`, `wilson_high`, `cost_usd`,
  `latency_ms` and one `relation.<name>.violation_rate` per relation that measured something;
  suite properties carry `stability_score` and `cost_total_usd`. A rate that was not measured is
  **omitted**, never written `"n/a"`, because every consumer parses a property value as a number
  the moment it recognises the name and the two things a string can do there — raise, or coerce to
  zero — are both the lie DECISIONS 8 refuses (DECISIONS 74). Numbers are `repr(round(v, 6))`, so
  the flaky case's `pass_rate` reads `0.8` and a third reads `0.333333` (DECISIONS 75).
  Unenforceable results are neither a failure nor a pass: they are listed in the case's
  `<system-out>` under `unenforceable (N):` (DECISIONS 76). Structure is checked with `xml.etree`
  against the attributes common CI tools require; `junitparser` is not a dependency and the one
  test that uses it returns without asserting when it is absent, so the gate still sees zero skips.
  Run on the frozen demo suite at this commit, `pytest examples/demo_suite --runs 5
  --probatio-junit j.xml --probatio-results r.json` writes 12 testcases, 1 failure, suite
  properties `stability_score="0.9"` and `cost_total_usd="0.0315"`, and:

```xml
      <testcase classname="examples/demo_suite/test_demo.py::test_flaky[flu-antivirals-flaky]" name="flu-antivirals-flaky" time="0.1">
        <properties>
          <property name="pass_rate" value="0.8" />
          <property name="wilson_low" value="0.375535" />
          <property name="wilson_high" value="0.963776" />
          <property name="cost_usd" value="0.0005" />
          <property name="latency_ms" value="100.0" />
        </properties>
      </testcase>
```

  with `anxiety-expected-fail` carrying a `<failure>` whose text is the pass-rate line and both
  failed assertions, and a `<system-out>` naming its one unvalidated judge verdict.
  **DECISIONS 67 closes and 69 is amended**: `check_unimplemented_options` is gone, both flags
  write their files, and every configure-time refusal — a live provider with no
  `--probatio-model`, an unloadable `--probatio-prices`, both `--runs` names taken — now travels
  through `plugin.as_usage_error`, which re-raises `ProbatioConfigError` as `pytest.UsageError`
  with the original as `__cause__` and the message unchanged. A `pytester` test asserts a refused
  session prints the sentence and does **not** print `INTERNALERROR`. The rule the refusal
  expressed survives in a different form: a file a flag asked for is written even when the session
  checked no case, so a pipeline's `if [ -f results.json ]` never silently stops firing.
  `docs/stability.md` gained two paragraphs, both backed by the committed Phase 9 run above: that
  the below-floor count needs `n` large enough to be informative, since at `n = 5` no case can
  clear a floor of 1.0 and the committed run therefore reads `12 of 12`; and that adding a price
  table flips an unenforceable ceiling to an enforceable one, changes the budget result a `scores`
  baseline holds, and re-records every such baseline once (DECISIONS 68), so a price table belongs
  on its own `--update-baseline` commit. `tests/test_docs_stability.py` reads the `12 of 12` back
  out of `PROGRESS.md`, so the doc cannot quote a run this file does not hold.
  DECISIONS 73–77 and the amendments to 67 and 69; `docs/DESIGN.md` Phase 10.
- 2026-09-04 — **Phase 10 (CI fix)** — gate green locally and the two CI failures fixed at the
  root: `.github/workflows/ci.yml` now checks out with `fetch-depth: 0`, and the byte-identity
  test fails, rather than passing with a note, on a shallow checkout. Gate condition 5 had been
  passing vacuously in CI since Phase 1 because `--diff-filter=A` resolved to HEAD in a shallow
  clone; Phase 9's sanctioned deletion is what finally made it speak up. The two tests that assert
  no artefact is written or count written files now `delenv` `GITHUB_STEP_SUMMARY`, which GitHub
  Actions sets and the markdown reporter rightly honours; the reporter is unchanged. DECISIONS 78.
- 2026-09-04 — **Phase 11** — gate green: `pytest -q` 915 passed, 0 skipped, 0 xfailed; coverage of
  `src/probatio` 100% (`coverage run -m pytest`); `ruff check` and `ruff format --check` clean on
  `src tests examples`; `mypy --strict src/probatio` clean (46 source files);
  `examples/demo_suite/` still differs from 8a998af by the one sanctioned Phase 9 edit and nothing
  else, with no untracked file inside it. Shipped `examples/consilium/`: `convert_traces.py`,
  `app.py`, `test_full.py`, `test_baseline.py`, `prices.yaml`, thirty cassettes under
  `cassettes/test_full/` and `cassettes/test_baseline/`, thirty `snapshot: scores` baselines under
  `.probatio/baseline/test_full/` and `.probatio/baseline/test_baseline/`, and
  `tests/test_consilium_suite.py` with `tests/fixtures/consilium/escalation_phrases.txt`.
  No `src/probatio/` code changed in this phase: the plugin replayed thirty real interactions
  without an edit.
  **The cases were not touched.** `convert_traces.py --emit-cases` reproduces all fifteen
  committed `cases/*.yaml` and `CASES.txt` byte for byte, both from the committed
  `golden-subset.jsonl` (which a test asserts holds exactly the `CASES.txt` ids in order) and from
  the full 150-item `golden.jsonl` outside this repository, so the selection rule in the README
  selects the same fifteen ids either way. All thirty traces name one model,
  `gpt-4o-mini-2024-07-18`, which `app.MODEL` carries and which the converter refuses to disagree
  with; `app.SYSTEM` is Probatio's own constant, because the traces publish token counts and
  answers but not prompts (DECISIONS 80). `cost_usd` is `null` on every imported call, so every
  one of the thirty cost ceilings is reported unenforceable until `--probatio-prices` is given,
  which is spec §3.7's rule firing on real data rather than on a fixture.
  **Results files this phase produced** (all under the gitignored `build/`, regenerated by the
  commands in `examples/consilium/README.md`): `build/consilium-noprice.json` for both suites in
  one session, `build/consilium-full.json` and `build/consilium-baseline.json` for the two suites
  separately, and `build/full.jsonl` and `build/baseline_llm.jsonl`, the `import-cassettes` input
  the committed tapes were built from. `build/consilium-run.txt` holds the terminal output quoted
  below verbatim.
  **`pytest examples/consilium -q --cassette-dir examples/consilium/cassettes`**, run at this
  commit, exit status 1 — `5 failed, 25 passed in 0.10s`. `test_baseline` is the first fifteen
  rows and `test_full` the second fifteen (the report keys a case on its node id and its case id,
  DECISIONS 73, but the terminal table prints the case id alone). The five failures are
  `g-su-001`, `g-su-002`, `g-su-003`, `g-md-018` and `g-md-021` in `test_full`, each on the
  `contains` assertion carrying Consilium's `ESCALATION_PHRASES`: five of the six red-flag cases
  whose delivered answer escalates under the plain baseline do not escalate under the full
  pipeline. `g-md-017` escalates under both. This is Consilium's published red-flag-recall gap
  reproduced from its own recorded outputs, and it is the retrospective catch Route A of the case
  study is written from in Phase 12:

```
  =================================== probatio ===================================
  cases:
    case      verdict  assertions  cost  latency ms  snapshot
    --------  -------  ----------  ----  ----------  ---------
    g-cc-001  pass     2/2         n/a   1098        unchanged
    g-cc-002  pass     2/2         n/a   1243        unchanged
    g-cc-017  pass     2/2         n/a   1394        unchanged
    g-ge-001  pass     2/2         n/a   1108        unchanged
    g-ge-002  pass     2/2         n/a   1039        unchanged
    g-ge-024  pass     2/2         n/a   1650        unchanged
    g-gh-001  pass     2/2         n/a   2009        unchanged
    g-gh-002  pass     2/2         n/a   1462        unchanged
    g-gh-017  pass     2/2         n/a   1096        unchanged
    g-md-017  pass     3/3         n/a   1840        unchanged
    g-md-018  pass     3/3         n/a   1434        unchanged
    g-md-021  pass     3/3         n/a   1224        unchanged
    g-su-001  pass     3/3         n/a   1011        unchanged
    g-su-002  pass     3/3         n/a   1019        unchanged
    g-su-003  pass     3/3         n/a   902         unchanged
    g-cc-001  pass     2/2         n/a   3583        unchanged
    g-cc-002  pass     2/2         n/a   3726        unchanged
    g-cc-017  pass     2/2         n/a   3116        unchanged
    g-ge-001  pass     2/2         n/a   7369        unchanged
    g-ge-002  pass     2/2         n/a   4296        unchanged
    g-ge-024  pass     2/2         n/a   4186        unchanged
    g-gh-001  pass     2/2         n/a   3708        unchanged
    g-gh-002  pass     2/2         n/a   3129        unchanged
    g-gh-017  pass     2/2         n/a   3394        unchanged
    g-md-017  pass     3/3         n/a   5832        unchanged
    g-md-018  FAIL     2/3         n/a   6655        unchanged
    g-md-021  FAIL     2/3         n/a   4853        unchanged
    g-su-001  FAIL     2/3         n/a   2967        unchanged
    g-su-002  FAIL     2/3         n/a   3169        unchanged
    g-su-003  FAIL     2/3         n/a   2864        unchanged

  stability: not measured (no case ran more than once; --runs was 1)
  cost: $0.000000 (no --max-cost ceiling)
  cost is a lower bound: no price for g-cc-001, g-cc-002, g-cc-017, g-ge-001, g-ge-002, g-ge-024, g-gh-001, g-gh-002, g-gh-017, g-md-017, g-md-018, g-md-021, g-su-001, g-su-002, g-su-003

  warnings (15):
    - g-cc-001: cost ceiling for g-cc-001 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
    - g-cc-002: cost ceiling for g-cc-002 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
    - g-cc-017: cost ceiling for g-cc-017 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
    - g-ge-001: cost ceiling for g-ge-001 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
    - g-ge-002: cost ceiling for g-ge-002 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
    - g-ge-024: cost ceiling for g-ge-024 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
    - g-gh-001: cost ceiling for g-gh-001 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
    - g-gh-002: cost ceiling for g-gh-002 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
    - g-gh-017: cost ceiling for g-gh-017 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
    - g-md-017: cost ceiling for g-md-017 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
    - g-md-018: cost ceiling for g-md-018 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
    - g-md-021: cost ceiling for g-md-021 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
    - g-su-001: cost ceiling for g-su-001 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
    - g-su-002: cost ceiling for g-su-002 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
    - g-su-003: cost ceiling for g-su-003 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
```

  DECISIONS 79–83; `docs/DESIGN.md` Phase 11.
- 2026-09-04 — **Phase 11 (price-table correction, cost rendering, case study)** — gate green:
  `pytest -q` 939 passed, 0 skipped, 0 xfailed; coverage of `src/probatio` 100%
  (`coverage run -m pytest`); `ruff check` and `ruff format --check` clean on `src tests examples`;
  `mypy --strict src/probatio` clean (46 source files); `examples/demo_suite/` still differs from
  8a998af by the one sanctioned Phase 9 edit and nothing else, with no untracked file inside it.
  **The price-table history, recorded rather than rewritten.** `b0aec38` committed
  `examples/consilium/results/replay-priced.*` and the thirty `.probatio/baseline-priced/` files as
  a *priced* run, but the run behind them had been made against a `prices.yaml` whose rates were
  still commented out, so every cost in them was unknown and the two "priced" files were the
  unpriced ones under another name. `c638edd` filled the rates and re-recorded, and was wrong the
  same way. `e4f10d3` is the correction that holds: `gpt-4o-mini-2024-07-18` at $0.15 input and
  $0.60 output per Mtok, read off the OpenAI price page (checked 2026-09-04, the URL and the row
  are in `prices.yaml`'s header), with the priced run re-recorded against them — which is where
  `$0.015070` and the per-case figures in `replay-priced.md` come from. The three commits stand as
  they are; none was amended or dropped.
  **The two committed result files the case study quotes** are
  `examples/consilium/results/replay-unpriced.json` / `.md`, from
  `pytest examples/consilium -q --cassette-dir examples/consilium/cassettes` with no price table,
  and `replay-priced.json` / `.md`, from the same command plus
  `--probatio-prices examples/consilium/prices.yaml --baseline-dir .probatio/baseline-priced`.
  Both exit 1 with `5 failed, 25 passed`, which is the finding, not a fault. The priced pair had
  been recorded on the invocation that re-recorded its own baselines, so its snapshot column read
  `updated`; it is re-recorded here from a plain replay against the committed
  `.probatio/baseline-priced/` and now reads `unchanged`. That column is the *only* thing that
  changed: all thirty rows match cell for cell otherwise, the `.json` is equal once
  `snapshot.state` and `snapshot.detail` are set aside, every per-case cost is identical and the
  total is still `$0.015070` — checked mechanically against the previous commit, not by eye.
  **The unpriced run was re-recorded at this commit**, because this phase's one source change
  alters the line it holds. `RunReport.cost_total_usd` is now `float | None` and is `None` when no
  call in the session was priced, and `reporters/tables.cost_lines` renders `unknown`,
  `at least $X` or the unchanged `$X` accordingly (DECISIONS 84), so `replay-unpriced.md` now reads
  `cost: unknown (no priced calls; 15 case(s) unpriced)` where it had read
  `cost: $0.000000 (no --max-cost ceiling)`, and `replay-unpriced.json` holds
  `"cost_total_usd": null`. Those two lines are the whole diff of both files. The JUnit suite
  property `cost_total_usd` is omitted rather than written when the total is `None`, which is
  DECISIONS 74 applied to the last property that had been exempt from it, and the results JSON
  round-trips the `null`. `tests/test_reporters_junit.py`'s `report_with` now records each case
  into a `SuiteBudget`, as `tests/test_reporters.py`'s always did: a report whose cases carry costs
  but whose budget never saw them has no total, and the helper had been building one.
  **`docs/CASE_STUDY.md` is committed as drafted**, unedited, with `tests/test_docs_case_study.py`
  as its provenance test (DECISIONS 85): eleven tests re-deriving §1's ids from `CASES.txt`, all
  eight of its quoted answer openings from the tapes as whitespace-normalised prefixes, and
  `15 of 15`, `10 of 15`, `five of the six`,
  `Six of the fifteen`, §1.2's thirty verdicts and its six questions from `replay-unpriced.json`
  and `cases/*.yaml`. Each check was provoked by editing the document and seen to fail.
  **The one content edit to the case study** is in §1.3: `g-su-002` had been quoted from the
  middle of its answer, which the test could only check as a substring; it now quotes that
  answer's real opening, verbatim from the tape, so all eight quotations are prefix-checked
  alike. `examples/consilium/README.md`'s provenance row for `prices.yaml` said the rates were
  commented out, which `e4f10d3` had made stale; it now carries the rates, the date checked, and
  which of the two committed runs predates them. What the test does not confirm, and cannot:
  §1.3's and §1.4's characterisations of what the answers mean, and
  every claim about Consilium's own repository — `docs/FAILURE_CASES.md` case 1, the red-flag
  recall figures 0.500 and 0.893, the run id `20260830T170133Z` and the commits `c1436bd` and
  `109a744` — which name files outside this repository and are labelled in the document as coming
  from there. Phase 13 generalises the module into a provenance test over `docs/` as a whole.
  **Every path a `RunReport` persists is now rootdir-relative with POSIX separators**
  (DECISIONS 86), through the new `artefacts.display_path`. `SnapshotResult.path` changes type
  from `Path` to `str`; its `baseline recorded at ...` / `updated at ...` details and the
  missing-tape and stale-tape messages that DECISIONS 72 puts in the warnings render the same
  way; `BaselineStore` and `CassetteStore` take a `root` that `session.py` and `plugin.py` fill
  from rootdir. The two `ProbatioConfigError`s for an unparsable baseline or tape keep the
  absolute path: they abort the session and are only ever read in a terminal. Both result pairs
  were re-recorded at this commit and the diff is exactly the thirty `snapshot.path` values in
  each JSON — everything else is equal once that field is set aside, and both `.md` files are
  byte-identical, since neither ever printed a path. `tests/test_plugin.py` asserts the rule and
  not the instance: it walks every string in a `pytester`-written results file, fails on any that
  starts with a separator or a drive letter, and separately checks that neither the rootdir nor
  the home directory appears anywhere in the text.
  DECISIONS 84–86; `docs/DESIGN.md` Phase 11 follow-up.
- 2026-09-05 — **Phase 12 (judge repeatability, sample 2)** — the judge was validated against
  Consilium's sample-2 labels **twice**, with the same model, the same rubric text and the same
  forty rows. The first run's record was not committed, because
  its `labels_file` carried an absolute path through a home directory (fixed at the root in
  DECISIONS 93, so no later run can); the measurement itself was sound — its `labels_hash` is
  `54c3af834595d71c`, the same content hash the committed run records, because
  `tests/fixtures/consilium/judge-sample-2-labeled.csv` is byte-identical to the package copy the
  first run named. Its summary, verbatim:

```
  judge 'faithfulness': n=40 agreement=0.675 kappa=0.253 (method: run-judge, labels: supported, unsupported)
  5 of 40 row(s) were asked again because the judge's first reply was not a verdict
```

  45 live calls (40 rows plus 5 re-asks). `docs/EVALUATION.md` reports this run beside the
  committed one as a same-judge, same-rubric, same-labels repeatability observation.
- 2026-09-05 — **Phase 12** — gate green: `pytest -q` 998 passed, 0 skipped, 0 xfailed;
  coverage of `src/probatio` 100% (`coverage run -m pytest`); `ruff check` and
  `ruff format --check` clean on `src tests examples`; `mypy --strict src/probatio` clean
  (46 source files); `examples/demo_suite/` still differs from 8a998af by the one sanctioned
  Phase 9 edit and nothing else. **The only phase that called a model**, always through
  `ClaudeCLIProvider` on a Claude plan, never with an API key, and never from the test suite.
  **Live calls: about 940** — 1 preflight, 18 freezing variants, 278 recording the opus suite,
  about 184 validating the judge, and about 460 recording Route B across five invocations.
  **Results files this phase produced**, all committed:
  `examples/consilium/live/results/preflight.json` (the payload the parser was checked against),
  `live-baseline.json` / `.md` (the opus replay), `live-changed.json` / `.md` (the haiku replay),
  `judges-sample-1/faithfulness.validation.json`, the fifteen tapes under
  `examples/consilium/live/cassettes/test_live/` and fifteen more under `cassettes-haiku/test_live/`
  (278 interactions each), and the fifteen `scores` baselines under
  `.probatio/baseline-live/test_live/`. `.probatio/judges/` holds **no** `faithfulness` record, on
  purpose; see below.
  **Three defects in `src/probatio` were found by dogfooding, not by review.** The cassette store's
  active case covered only the system under test, so every judge call and every relation-variant
  call reached it with no case to file under — nine phases had never exercised a cassette store
  together with a judge or a relation (DECISIONS 90). `validate-judge --run-judge` propagated an
  unparsable judge reply, so one bad row in forty ended a forty-row run (DECISIONS 92). And
  `ClaudeCLIProvider`'s timeout had been a constructor argument since Phase 2 with no flag reaching
  it, which is now `--probatio-timeout` (DECISIONS 95). Two smaller fixes: the validation record's
  `labels_file` goes through `artefacts.display_path` (DECISIONS 93), and `Judge.parse` quotes the
  reply it could not parse (DECISIONS 94).
  **Route A stays the headline and Route B is real.** Changing one flag from `claude-opus-5` to
  `claude-haiku-4-5-20251001` moved the verdict on 4 of 15 cases, drifted 8 of 15 snapshots, took
  `paraphrase_invariant` from 0.04 to 0.30 and `format_jitter` from 0.13 to 0.31, and cost
  $0.987356 against $6.037457 in notional API price. All five haiku assertion failures are the
  judge, and the one case that moved the other way is `g-md-018`, whose answer matched 0 of 38
  escalation phrases under opus and 1 of 38 under haiku.
  **The judge is reported as unvalidated, and it is.** Sample 1 gave kappa 0.600 / agreement 0.800
  with 8 of 40 rows re-asked, and its record is committed. Sample 2 was attempted six times and
  completed once, at kappa 0.253 / agreement 0.675 with 5 re-asked; that record was not committed
  because `labels_file` carried a machine path, and the three attempts made after the root fix all
  failed. Rather than raise the re-ask bound until a number appeared, `.probatio/judges/` was left
  empty, so every live run prints fifteen unvalidated-judge warnings and all fifteen judge results
  carry `unenforceable=True`. The two kappas reverse the ordering the GPT-4o-mini judge gave on the
  same labels (0.350 and 0.592), which `docs/EVALUATION.md` §4 leads with, caveated by the fact
  that Consilium ran two rubrics where Probatio ran one.
  **2 of 45 frozen paraphrases were deleted at human review**, each noted in its file's header.
  New `docs/EVALUATION.md` and `docs/CASE_STUDY.md` §§2–5, both with provenance tests
  (`tests/test_docs_evaluation.py`, 17 tests; `tests/test_docs_case_study.py`, now 27) that parse
  every number out of the prose and re-derive it from the artefact named beside it; seven were
  provoked by editing a document and seen to fail. The unpushed range was rewritten once to drop a
  validation record that carried a home directory; `git log origin/main..main -S '/Users/...'`
  is empty. DECISIONS 87–95; `docs/DESIGN.md` Phase 12; new `docs/EVALUATION.md`,
  `examples/consilium/live/README.md`.
- 2026-09-06 — **Phase 13** — gate green: `pytest -q` 1212 passed, 0 skipped, 0 xfailed;
  coverage of `src/probatio` 100% (`coverage run -m pytest`); `ruff check` and
  `ruff format --check` clean on `src tests examples`; `mypy --strict src/probatio` clean
  (46 source files); `examples/demo_suite/` still differs from 8a998af by the one sanctioned
  Phase 9 edit and nothing else, with `git status --porcelain` on it empty. **Nothing under `src/`
  or `examples/` changed in this phase**: it is documentation, and the tests that hold the
  documentation to its sources.
  **`README.md` is written in spec §7's order**: the pitch (a pytest plugin, the two headline
  features, and the judge described as **measured agreement** rather than validated, per
  `05-RESUME-AND-INTERVIEW.md` §5); a fifteen-line quick start whose every line but one is
  verbatim from the frozen `examples/demo_suite/`; the two headline features, each quoting the
  `probatio` section of the committed `--runs 5` run recorded in this file and naming `4c2114e` as
  the commit that produced it, with `n below floor: 12 of 12` explained in a sentence; the
  prior-art table, captioned "checked against each tool's documentation on 2026-09-05", with the
  pages read listed under it, what is **not** a differentiator said plainly (pytest-native,
  repeated runs, JUnit output), what is (an interval on a per-case pass rate, a stability score, a
  floor marker, relations as stated invariants), the one-sentence contrast with DeepEval's flaky
  flag, and the five citations; the case study summary (Route A retrospective, five of six
  red-flag cases failing on `full` and none on `baseline_llm`; Route B prospective in form, one
  flag, 4 of 15 verdicts moved, the judge marking a third unfaithful, a six-fold notional cost
  difference), each labelled as `docs/CASE_STUDY.md` labels it; the four design positions; and
  install extras, status and roadmap pointing at `PROGRESS.md` and `DECISIONS.md`.
  **New `docs/PROVENANCE.md` and `tests/test_docs_provenance.py`** (DECISIONS 96, 97). The file
  holds three tables: 62 **measurements**, each with the documents that print it, the committed
  source file, a named check and the command that regenerates the source; 17 **numerals that are
  not measurements**, declared as literals or `re:` patterns with what each one is and where it is
  fixed; and 9 rows naming which provenance test guards which document, asserted to cover every
  file under `docs/` plus `README.md`. The test runs every row's check — `text` plus thirteen
  named derivations, each recomputing the figure from the artefact rather than searching for it —
  asserts the figure is printed in every document its row names, asserts every source file is
  tracked by `git ls-files`, and sweeps `README.md` exhaustively: strip both tables' literals and
  patterns, and any numeral left over fails. Three failure modes were provoked and seen to fail: a
  stray "42% faster" added to the README, `$6.037457` edited in the README, and `$6.037457` edited
  in `live-baseline.md`. The sweep is exhaustive for `README.md` only, because every other
  document already has a provenance test that re-derives its figures, which is the stronger check;
  that boundary is stated in `docs/PROVENANCE.md` itself rather than left implicit.
  **One README sentence was deleted rather than softened**: "reproduced as a failing `pytest` run
  from committed tapes at $0" lost its `$0`, which no committed file produces — replay reproduces
  the costs the tapes recorded, and the claim the sentence wanted was that no model is called, so
  it now says that. Nothing else was removed for lack of a file; the phase's other numbers all
  found one.
  **`docs/relations.md`'s four placeholders are gone**, replaced by five entries verified against
  Crossref on 2026-09-05, and OpenAlex for the one abstract: LLMorph (ASE 2025,
  DOI 10.1109/ASE63991.2025.00385), the NLP catalogue (ICSME 2025,
  DOI 10.1109/ICSME64153.2025.00025, whose abstract gives **191** relations with 36 implemented),
  Chen et al. (*ACM Computing Surveys* 2018, DOI 10.1145/3143561), Segura et al. (*IEEE TSE* 2016,
  DOI 10.1109/TSE.2016.2532875) and MTF (AIAT 2025, DOI 10.1145/3787120.3787123), the last cited
  only by the README. `tests/test_docs_relations.py`'s two placeholder tests are replaced by five
  that check every entry carries a venue, a year and a DOI, that the DOI set is exactly those
  five, that each DOI link resolves to the DOI it names, that 191 is attributed to the abstract,
  and that the section still says Probatio claims no new relation.
  **`docs/providers.md` gained `--probatio-timeout`** and a section on what recording a real suite
  through `ClaudeCLIProvider` cost: the roughly-one-reply-in-eight rationale-string truncation with
  the committed 400-character reply and its `line 1 column 49`, the 8-of-40 and 5-of-40 re-ask
  counts, `cli.JUDGE_ATTEMPTS = 3`, the exit-1-with-empty-stderr crash, and the timeout that the
  120-second default could not carry. Four new tests read those back out of the fixture, the
  validation record, `PROGRESS.md` and the two constants.
  **`docs/assertions.md` publishes the band and refuses the recommendation** (DECISIONS 98): the
  thirty real answers in `replay-unpriced.json` score 0.398 to 0.705 against their references, per
  configuration and median, every one of them above the committed `tau: 0.30` with the worst 0.098
  above it — and no recommended value, because one corpus at one answer length is a band and not a
  distribution. The Phase 4 deferral sentence is gone; its test is replaced by two that recompute
  all six figures and the headroom from the results file.
  **`docs/stability.md` gained "What a committed run says"**, reading `stability score: 0.90` and
  `12 of 12` off the run's own cases table, with the mean of the twelve pass rates re-derived from
  `PROGRESS.md` by a new test, and a sentence putting per-run fixture isolation on the roadmap
  rather than in v0.1.
  **`docs/DESIGN.md` gained the Phase 12 timeout paragraph and a Phase 13 section** (why a number
  gets an index and a test, why the README quotes one commit's run, why the prior-art table states
  absences only for pages that were read, and why the measured band replaced the deferred
  recommendation). It is the one document with no figures of its own, so DECISIONS 99 covers it
  from the index instead of a seventh module.
  **`docs/EVALUATION.md` gained §7, "What dogfooding found about Probatio itself"**: DECISIONS 90
  (the cassette store's active case, fixed in `528333f`), 92 (the judge re-ask, `3ffde31`) and 95
  (`--probatio-timeout`, `15651f2`) as the two defects and one gap the Consilium suites exposed,
  with why the two defects survived nine phases and why the third is listed even though nothing
  was wrong with the code. Five new tests check the table's entries exist in `DECISIONS.md` and
  its commits exist in this repository's history.
  **Three follow-up edits, in the same commit.** The case study section links
  `https://github.com/Lexieli666/consilium-health`, the URL `examples/consilium/README.md` already
  gives, with a test that reads it out of that file rather than repeating it; the same section ends
  by naming the three things dogfooding found wrong with Probatio itself and pointing at
  `docs/EVALUATION.md` §7, with a test asserting that section still lists two defects and one gap;
  and the quick start says that the case it shows takes a **bare string** input, so
  `@format_jitter(field="input.question")` reports *not applicable* on it rather than `0.00`, and
  names `cases/01-htn-definition.yaml` as the dict-input case the field relations do apply to —
  with a test that re-derives both from the frozen cases through `FormatJitter.applicable`. All
  three new tests were provoked and seen to fail. The sweep caught all three edits on the way in
  (a URL, a `NN-name.yaml` prefix and a second `0.00`), which is what the amendment to
  DECISIONS 96 records.
  `examples/README.md`'s errata section is unchanged. DECISIONS 96–99;
  `docs/DESIGN.md` Phase 13; new `docs/PROVENANCE.md`, `tests/test_docs_provenance.py`.
- 2026-09-06 — **Phase 14** — release prepared; publication pending the human's three commands.
  Gate green: `pytest -q` 1214 passed, 0 skipped, 0 xfailed; coverage of `src/probatio` 100%
  (`coverage run -m pytest`); `ruff check` and `ruff format --check` clean on `src tests examples`;
  `mypy --strict src/probatio` clean (46 source files); `examples/demo_suite/` still differs from
  8a998af by the one sanctioned Phase 9 edit and nothing else, with `git status --porcelain` on it
  empty. **The Phase 14 box is deliberately unticked**: nothing is published, tagged, made public
  or pushed, and the phase is not done until it is.
  **Version.** `__version__ = "0.1.0"` in `src/probatio/__init__.py`, which `pyproject.toml` reads
  through hatchling; `tests/test_smoke.py` asserts the new string.
  **`CHANGELOG.md`**, Keep-a-Changelog style, one `Added` entry per shipped capability in spec §3
  order — foundations, cases, providers, assertions, judge and validation, snapshots, budgets,
  cassettes, metamorphic relations, flakiness statistics, reporters, the pytest surface, the
  console script — then packaging, examples, documentation and CI. Its "Known limitations" section
  is drawn from `docs/CASE_STUDY.md` §5 and the README's roadmap. **It states no measurement at
  all** (DECISIONS 101): every limit is in words, pointing at the document that carries the figure.
  `docs/PROVENANCE.md` gains one row for the version string and a `CHANGELOG.md` line in its
  guards table, the sweep in `tests/test_docs_provenance.py` is parametrised over `README.md` and
  `CHANGELOG.md`, and a second test asserts the measurements table names no changelog and that no
  measurement's string appears in it. Both were provoked and seen to fail on a stray `42%` and a
  stray `0.600`.
  **Packaging.** `src/probatio/py.typed` added, and confirmed present in the wheel and in the
  installed package on disk. `Changelog` added to `[project.urls]` and confirmed in the wheel's
  `METADATA`. The sdist ships neither `tests/` nor `examples/` (DECISIONS 100): the Phase 0 sdist
  was built, extracted and run, and `pytest -q` inside it stops with **10 collection errors**
  before a test executes, because the suite needs `examples/`, `docs/`, `PROGRESS.md` and this
  repository's git history. The sdist is now 53 entries — `src/probatio` (47 files including
  `py.typed`), `README.md`, `CHANGELOG.md`, `LICENSE`, `pyproject.toml`, plus `.gitignore` and
  `PKG-INFO` that hatchling adds; the wheel is `probatio/` and its `dist-info` and nothing else.
  `python -m build` succeeded and `twine check dist/*` PASSED on both artefacts. The wheel was
  installed into a fresh temporary venv, where it pulled exactly `pytest`, `pydantic`, `jsonschema`
  and `PyYAML` with their transitive dependencies and nothing else;
  `python -c "import probatio; print(probatio.__version__)"` printed `0.1.0`, `probatio --help`
  printed the three subcommands, and `pytest --help` showed the plugin's option group, so the
  `pytest11` entry point registers from an installed wheel and not only from an editable install.
  **CI.** `actions/checkout` v4 → v5 and `actions/setup-python` v5 → v6, the two Node 20
  deprecation annotations; the matrix stays at 3.11 and 3.12, `fetch-depth: 0` stays, and the
  five gate steps are untouched.
  **Pre-publication audit.** `git status --short` was empty at the start of this session and is
  empty again after this phase's single commit. `grep -rn "api_key\|ANTHROPIC_API_KEY\|OPENAI" src
  tests examples` returns exactly one line, `src/probatio/providers/claude_cli.py:51`, a docstring
  sentence explaining that `ClaudeCLIProvider` avoids `--bare` *because* it would switch
  authentication to `ANTHROPIC_API_KEY`; nothing live, no key, no OpenAI adapter.
  `git log --all -S '/Users/yutongzhao' --oneline` lists exactly the three commits already on
  record and nothing else: `f007344`, `b0aec38`, `4c2114e`. `git ls-files | grep -i -E
  "package|notes/"` returns nothing at all — no build-package file is tracked under a name that
  matches, and `CLAUDE.md`, the one build-package file that is tracked, does not match the pattern.
  The last check was run exhaustively rather than from the list, by hashing every file in both
  trees and then comparing every line of 40 characters or more across them (DECISIONS 102):
  **nineteen** tracked files are byte-identical to a build-package file and **four** more carry its
  content verbatim. Eighteen of the nineteen and all four are the sanctioned set — `CLAUDE.md`, the
  fourteen corpus notes, `faithfulness_v2.md`, the two judge-label CSVs, `golden-subset.jsonl`
  (fifteen lines of the package's `golden.jsonl`), `escalation_phrases.txt` (the thirty-eight
  phrases of the package's `safety/escalation.py`, one per line) and the two files
  `convert_traces.py --emit-live-cases` writes from those fixtures, `live/cases/*.yaml` and
  `live/rubrics/faithfulness.md`. **The nineteenth is `tests/fixtures/claude_cli_payload.json`**,
  which the audit list does not name. It is sanctioned and always was — DECISIONS 14 records it as
  a verbatim copy of one real CLI payload, the one the Phase 2 prompt said a human would capture,
  and `docs/providers.md`'s three dollar figures are derived from it — but it was recorded as a
  copy of a *reply*, not of a *package file*, which is exactly the kind of thing a remembered list
  misses. DECISIONS 102 writes the complete list down. Everything else that shares a long line with
  the package shares the specification's own API signatures and sample YAML, the reference list
  Phase 13 was handed, or a command quoted from the dogfood document.
  **What is left, and it is the human's to run**: make the repository public, tag `v0.1.0` and
  push the tag, `twine upload dist/*`, then `gh release create`. Nothing in this commit does any
  of it. DECISIONS 100–102.

- 2026-09-06 — **Phase 14** — published. Repository made public
  (`gh repo edit --visibility public`, run 34059932746 green on 3.11 and 3.12 at `d958e32`); tag
  `v0.1.0` on `d958e32` pushed; `twine check` passed on both artefacts and `twine upload` put
  `probatio-llm 0.1.0` at <https://pypi.org/project/probatio-llm/0.1.0/>; a clean virtualenv
  `pip install probatio-llm==0.1.0` imported `probatio` at `0.1.0` and `pytest --help` listed the
  plugin's options; GitHub release <https://github.com/Lexieli666/probatio/releases/tag/v0.1.0>
  carries the wheel, the sdist and CHANGELOG.md as notes. Resume bullets follow in the build
  package (`05-RESUME-AND-INTERVIEW.md`), outside this repository.
