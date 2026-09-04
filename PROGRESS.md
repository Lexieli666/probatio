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
- [ ] **Phase 5** — Snapshots (spec §3.6)
- [ ] **Phase 6** — Budgets and the unenforceable rule (spec §3.7)
- [ ] **Phase 7** — Cassettes and `import-cassettes` (spec §3.8, §3.13)
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
