# CLAUDE.md — Probatio

Project constitution. Re-read this file at the start of every session, before touching code. It
overrides any prompt that contradicts it.

## What Probatio is

A pip-installable **pytest plugin** for regression-testing LLM applications. It is not an eval
platform and not a hosted service. Its two headline features, which the incumbent tools (DeepEval,
promptfoo, Giskard, Ragas, Braintrust, LangSmith) do not provide as pytest-native developer
tooling, are:

1. **Metamorphic relations**: decorators asserting that semantics-preserving input
   transformations do not change the verdict, reported as a per-relation violation rate.
2. **Flakiness statistics**: repeated execution with per-case pass rates, Wilson confidence
   intervals and a suite-level stability score, instead of pretending LLM tests are deterministic.

Everything else (schema validity, contains assertions, similarity, LLM-as-judge, snapshots,
budgets, record-replay cassettes, reporters) is table stakes that must exist for the two headline
features to be usable.

## Hard constraints

Violating any of these is a defect, even if tests pass.

- **No live LLM API calls in the test suite or in any code path exercised by `pytest`.** No
  API key in the environment during tests, no network egress to model providers. All provider
  interaction goes through the `Provider` protocol; tests use `FakeProvider`, monkeypatched SDK
  clients, and committed cassettes. Live calls happen only when a human deliberately runs
  `pytest --cassette=record --probatio-provider claude-cli`, `probatio freeze-variants`, or
  `probatio validate-judge --run-judge`; the test suite itself never does.
- **Anthropic is the only live provider shipped.** Adapters: `FakeProvider`,
  `AnthropicProvider` (SDK, optional extra), `ClaudeCLIProvider` (subprocess over the Claude Code
  CLI). No OpenAI adapter. Other providers are documented as a one-class extension.
- **No model downloads.** No sentence-transformers, no HuggingFace hub, no spaCy models.
  Similarity has a pure-Python deterministic default backend; embedding backends are pluggable
  and never installed or invoked by the test suite.
- **`src/` layout, Python 3.11+.** Import path is `probatio`; source lives in `src/probatio/`.
- **Runtime dependencies are exactly:** `pytest`, `pydantic>=2`, `jsonschema`, `PyYAML`.
  `anthropic` is an optional extra. Anything else needs a numbered entry in `DECISIONS.md`.
- **Every public function and class is typed and has a docstring.** `mypy --strict src/probatio`
  must pass.
- **Every module ships with tests.** No phase is complete with a failing or skipped test.
- **Nothing outside the repository is read or written by the code**, except paths the user passes
  explicitly on the command line.

## Repository layout

```
probatio/
  pyproject.toml
  README.md
  CLAUDE.md            <- this file
  PROGRESS.md          <- phase checklist and run log; the single source of run state
  DECISIONS.md         <- every judgement call made without asking, numbered
  BLOCKERS.md          <- anything abandoned after three attempts
  src/probatio/
    __init__.py
    errors.py          <- ProbatioError and subclasses
    hashing.py         <- stable content hashing used for every persisted identity
    case.py            <- LLMCase, YAML loader
    providers/         <- Provider protocol, Completion, FakeProvider, anthropic, claude_cli
    assertions/        <- schema, contains, similarity, judge; AssertionResult
    judge/             <- rubric judge, Cohen's kappa, validation records
    snapshot.py        <- baselines, --update-baseline
    budget.py          <- cost/latency ceilings, unenforceable-ceiling rule
    cassette.py        <- record/replay + stale-cassette detection
    metamorphic/       <- Relation base, registry, four relations, frozen variants, freeze
    stability/         <- --runs n, Wilson interval, stability score, flaky_tolerant
    reporters/         <- terminal, markdown job summary, JUnit XML
    collector.py       <- per-session run state (a stack, because pytester nests sessions)
    runner.py          <- evaluate a case: run every assertion, return all results
    plugin.py          <- pytest hooks, CLI flags, fixtures
    cli.py             <- `probatio` console script
  tests/
  examples/demo_suite/ <- the executable design spec, written in Phase 1, never edited after
  examples/consilium/  <- the dogfood suite (Phase 11+)
  docs/
```

## Commands

```bash
. .venv/bin/activate                      # always; never the system python
pytest -q                                 # full suite
coverage run -m pytest -q && coverage report   # the gate's coverage number
ruff check src tests examples && ruff format --check src tests examples
mypy --strict src/probatio
```

## Quality gate (definition of done for every phase)

All five must hold at the phase's commit:

1. `pytest -q` passes with zero failures, zero errors, zero skips, zero xfails.
2. Line coverage of `src/probatio` is at least 85%, measured with `coverage run -m pytest`.
3. `ruff check` and `ruff format --check` are clean.
4. `mypy --strict src/probatio` is clean.
5. `examples/demo_suite/` is byte-identical to the commit that introduced it. A test asserts this
   by diffing against that commit. If an implementation change would require editing the example,
   the implementation is wrong, not the example. Two sanctioned exceptions, both recorded in
   `DECISIONS.md`: the Phase 9 deletion of the temporary `collect_ignore` import guard at the top
   of its `conftest.py`, and a genuinely unimplementable line, with its reason.

## Working style

- One phase per Claude Code session. Small conventional commits
  (`feat(metamorphic): add order_invariant relation`). The `PROGRESS.md` checkbox and run-log
  line for phase N go in **the same commit** as phase N's code, never a later one. Verify with
  `git show --stat HEAD | grep PROGRESS.md`.
- `PROGRESS.md` is the run's only durable memory. A fresh session reads it first.
- When you would ask a question, do not. Pick the option that is simplest to implement and easiest
  to test offline, append `Q: ... / A: ... / Why: ...` to `DECISIONS.md`, and continue. The
  exceptions that must stop and ask: adding a runtime dependency, changing the Python floor,
  changing the public decorator or YAML syntax fixed by `examples/demo_suite/`, anything that
  would call a live model from a test.
- Three-strike rule: a sub-task that fails three times goes to `BLOCKERS.md` with the three
  approaches tried, is marked `[blocked]` in `PROGRESS.md`, and is left.
- Never commit a broken tree. Never push a broken tree. Push only at the end of a phase whose gate
  is green.
- Prefer the standard library. Implement statistics (Wilson interval, Cohen's kappa) by hand and
  test them against hand-computed values.
- Every non-obvious design choice gets a one-paragraph rationale in `docs/DESIGN.md` naming the
  alternative rejected.
- No number appears in `README.md` or `docs/` that a committed run did not produce.
