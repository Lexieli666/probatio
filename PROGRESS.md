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
