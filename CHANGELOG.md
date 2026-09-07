# Changelog

Notable changes to Probatio, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/spec/v2.0.0.html).

The `Added` list below is in the order of the specification's architecture section, which is also
the order in which the phases recorded in [`PROGRESS.md`](PROGRESS.md) built it.

This file states no measurement. Every figure Probatio has produced about itself is printed in
[`README.md`](README.md) and under [`docs/`](docs/), and indexed against the committed file that
produced it in [`docs/PROVENANCE.md`](docs/PROVENANCE.md); repeating a number here would be a
second copy with no test behind it.

## [Unreleased]

### Fixed

- **The single-sample note is made for the interaction that defines a case's runs, not for every
  interaction.** A judge call's prompt carries the answer it is grading, so under `--runs N` a
  case's tape holds one judge interaction per run, each with exactly one recorded sample. The note
  that warns a reader when a one-sample tape pins a case's pass rate therefore fired on every
  judged case, beside pass rates the tapes had genuinely measured over N answers. It is now
  suppressed while a judge is speaking; the system-under-test interaction, whose samples the runs
  actually draw from, still notes (DECISIONS 106).

### Added

- **The repetition study under `examples/consilium/live/`**, in two parts, both offline from
  committed tapes. `test_live_variance.py` answers the live cases repeatedly under `--runs N` and
  reports a per-case pass rate, a Wilson interval and a suite stability score.
  `judge_repeatability.py` holds the answer still: it reads each case's recorded answer off the
  committed tape by cassette key and asks the same judge, with the same rubric and the same prompt
  template, to grade those exact bytes repeatedly, writing `results/judge-repeatability.json`. Both
  are written up in [`docs/EVALUATION.md`](docs/EVALUATION.md) §8; recording either one is a live
  step a human runs deliberately, as `examples/consilium/live/README.md` says.

## [0.1.0] — 2026-09-06

First release. Probatio is a pytest plugin for regression-testing LLM applications, distributed as
`probatio-llm` and imported as `probatio`. Its two headline features are metamorphic relations and
flakiness statistics; everything else on this list exists so that those two are usable from a
normal test suite.

### Added

- **Foundations.** `ProbatioError` and the seven subclasses that name the offending case and, where
  one exists, the command that fixes it: `ProbatioConfigError`, `MissingCassetteError`,
  `StaleCassetteError`, `MissingVariantsError`, `BaselineDriftError`, `BudgetExceededError`,
  `JudgeOutputError`. `stable_hash`, the canonical-JSON content hash behind every persisted
  identity in the tool — cassette keys, prompt hashes, variant provenance, label files — stable
  across processes and platforms.
- **Cases.** `LLMCase`, a pydantic model with an id, a string-or-mapping input, an optional system
  prompt and parameters, its assertions, an optional budget, a snapshot mode and tags; and
  `load_cases`, which loads a directory of YAML files in filename order and reports a malformed
  file by name and field rather than by traceback.
- **Providers.** The `Provider` protocol and the `Completion` it returns, carrying text, token
  counts, latency and a cost that is `None` when the provider cannot price the call rather than a
  zero a ceiling would silently pass. Four adapters: `FakeProvider` and `ScriptedProvider` for
  tests, `AnthropicProvider` over the SDK behind the `anthropic` extra, and `ClaudeCLIProvider`,
  which runs the Claude Code CLI as a subprocess in a fresh empty directory so a developer on a
  Claude plan can record without an API key. `--probatio-timeout` sets the subprocess ceiling.
- **Assertions.** Five checks over one `AssertionResult`: `schema_valid` (JSON Schema, with fenced
  blocks stripped), `contains` and `not_contains`, `similarity` against a reference, and `judge`.
  Similarity ships a pure-Python trigram-cosine backend and a `SimilarityBackend` protocol for
  pluggable embeddings; nothing is downloaded, and no backend but the default is ever installed or
  invoked by a test run.
- **Judge and validation.** `Judge` grades a case against a markdown rubric resolved from
  `rubrics/`; the prompt template is a module constant whose hash is part of every judge cassette
  key. A reply that is not strict JSON is asked again a bounded number of times and then returned
  as a failed assertion, never raised. `cohens_kappa` and the validation record it writes;
  `probatio validate-judge` measures a judge against human labels, from two existing columns or by
  running the judge over the rows, and exits non-zero below `--min-kappa`. A judge with no
  validation record on disk is reported as unenforceable rather than trusted.
- **Snapshots.** Per-case baselines under `.probatio/baseline/`, in `scores` or `output` mode,
  keyed on a hash of the prompt so a case whose input changed is reported as a new baseline rather
  than as drift. `--update-baseline` rewrites them; `--baseline-dir` moves them.
- **Budgets.** Per-case `max_cost_usd` and `max_latency_ms`, suite-wide `--max-cost` and
  `--max-latency`, and `PriceTable` loaded from `--probatio-prices`. **The unenforceable rule:** a
  cost ceiling evaluated where any call has an unknown cost is reported under warnings and not
  under passed checks, because a ceiling that cannot be evaluated has not been met. No prices ship
  with the package.
- **Cassettes.** `CassetteProvider` wraps any provider in `replay`, `record` or `off` mode, with
  `replay` the default, so a suite runs from committed tapes and makes no model call. Tapes are
  keyed on prompt, system, model, parameters and — for a judge call — the template hash, so an
  edited prompt or rubric is detected as a stale tape rather than replayed as if nothing changed.
  Missing and stale tapes are both raised and carried into the report. `--cassette-dir` moves the
  store; `probatio import-cassettes` builds one from a JSONL of interactions recorded elsewhere.
- **Metamorphic relations.** The `Relation` base and its registry, and four decorators:
  `@paraphrase_invariant`, `@order_invariant`, `@distractor_robust` and `@format_jitter`. Each
  generates variants of a case that should not change its verdict; the plugin runs them and reports
  a per-relation violation rate with the individual flips, and prints *not applicable* rather than
  a rate for a relation whose case does not carry the field it needs. Paraphrases are not generated
  at test time: `probatio freeze-variants` asks a model once, a human reviews and edits the
  written files, and the suite reads the frozen, committed variants.
- **Flakiness statistics.** `--runs N` repeats each case in place and reports a per-case pass rate
  with a hand-implemented Wilson 95% interval, a majority verdict, a suite stability score, and the
  number of cases whose interval falls below their declared floor. `@flaky_tolerant(p=…)` declares
  that floor per case; a case that declares none is held to a floor of 1.0.
- **Reporters.** One `RunReport` rendered four ways: the terminal section pytest prints at the end
  of every run, a GitHub-flavoured markdown report written to `$GITHUB_STEP_SUMMARY` or
  `--probatio-report`, JUnit XML at `--probatio-junit` carrying pass rates, interval bounds, costs
  and per-relation violation rates as properties, and the full report as JSON at
  `--probatio-results`. A quantity that was not measured is omitted, never written as a zero.
- **The pytest surface.** The `probatio`, `provider` and `judge_provider` fixtures; the
  `probatio_relation` and `flaky_tolerant` markers; and the option group that selects the provider
  and model, the judge provider and model, the cassette mode and store, the baseline directory,
  the price table, the ceilings, the timeout and the three report paths. A non-fake provider with
  no model named is refused before the session starts.
- **The `probatio` console script.** `validate-judge`, `freeze-variants` and `import-cassettes`.
  These are the only entry points that call a live model, and only when a human runs them.
- **Packaging.** `probatio-llm` on Python 3.11 and newer, with runtime dependencies of exactly
  `pytest`, `pydantic`, `jsonschema` and `PyYAML`; an `anthropic` extra for the SDK adapter and a
  `dev` extra for the gate. Ships `py.typed`: the package is typed and `mypy --strict` is part of
  the gate. The sdist carries the package, this file, the README and the licence, and neither
  `tests/` nor `examples/`.
- **Examples.** `examples/demo_suite/`, the executable design specification, written before the
  implementation and byte-frozen since — every decorator, every assertion type and a deliberate
  failing case, runnable offline. `examples/consilium/`, a dogfood suite over a real
  retrieval-augmented medical Q&A system, offline from committed tapes, with a live variant used
  to record them.
- **Documentation.** `README.md` with a prior-art comparison against DeepEval, promptfoo, Giskard,
  Ragas, Braintrust and LangSmith; `docs/DESIGN.md`, `docs/assertions.md`, `docs/relations.md`,
  `docs/stability.md`, `docs/providers.md`, `docs/EVALUATION.md`, `docs/CASE_STUDY.md`; and
  `docs/PROVENANCE.md`, which indexes every number in the documentation to the committed file that
  produced it and is enforced by a test that re-derives each one.
- **Continuous integration.** The five-part quality gate — pytest, coverage of `src/probatio`,
  ruff, `mypy --strict`, and byte-identity of the frozen demo suite — on the floor version and the
  one above it, with no credentials and no network access to a model provider.

### Known limitations

Stated in full, with the evidence, in [`docs/CASE_STUDY.md`](docs/CASE_STUDY.md) §5 and
[`docs/EVALUATION.md`](docs/EVALUATION.md); summarised here because they bound what this release
has shown.

- **The judge in this repository is not validated on disk, deliberately.** Its two measured kappas
  disagree with each other, and neither is high; `docs/EVALUATION.md` §4 gives both and says why no
  validation record was written. Every judge verdict in the case study therefore carries
  `unenforceable=True`, and the relation rates that depend on those verdicts inherit it. They are
  reported because an unenforceable result is still a measurement — of an unvalidated instrument.
- **A suite cannot yet declare a minimum kappa that fails the build.**
  `probatio validate-judge --min-kappa` exits non-zero from the command line, but there is no
  equivalent of a budget overrun inside a pytest run.
- **`--runs N` repeats inside one pytest item, so function-scoped fixtures are shared across the
  runs.** That is deliberate — it measures the model's nondeterminism, not state leakage — but a
  suite wanting a fresh fixture per run has to build one inside its own callable
  (`docs/stability.md`).
- **The case study's live system under test is not the system it borrows its questions from.** It
  makes one grounded call with the corpus notes already in hand; the real pipeline plans,
  retrieves, runs agents and repairs. Retrieval is not modelled at all, so nothing here speaks to
  retrieval quality.
- **The case study is a small sample, run once, on one model family.** Fifteen cases, one run
  each, two Anthropic models reached through the same adapter. No interval in that document is a
  confidence interval, and the flip pattern most in need of repetition is the one repetition would
  have resolved.
- **Route A of the case study is retrospective.** The regression it replays was found and
  documented by the system's own evaluation before the suite was written, and the suite's
  assertions were derived from that system's golden labels and phrase list.
- **Costs reported through `ClaudeCLIProvider` are notional.** They are the API price the CLI
  computes for calls made on a subscription that was not billed that money;
  `docs/providers.md` says so wherever the figure is used.
- **Anthropic is the only live provider.** There is no OpenAI adapter and none is planned; another
  provider is a one-class extension, documented in `docs/providers.md`.
- **Similarity's default backend is lexical.** Trigram cosine is deterministic and needs no
  download, which is why it is the default; it is not a semantic measure, and
  `docs/assertions.md` publishes the band it produced on real answers instead of recommending a
  threshold.

[0.1.0]: https://github.com/Lexieli666/probatio/releases/tag/v0.1.0
