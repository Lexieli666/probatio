# PROGRESS.md — Probatio

The run's only durable memory. A fresh session reads this file first, immediately after
`CLAUDE.md`. One phase per session; the checkbox and the run-log line for phase N are committed
with phase N's code.

## Phases

- [x] **Phase 0** — Scaffolding, tooling, CI, `PROGRESS.md`, PyPI name check (spec §2)
- [ ] **Phase 1** — `examples/demo_suite/` as the executable design spec (spec §4)
- [ ] **Phase 2** — Foundations, `LLMCase`, YAML loader, providers (spec §3.1–3.3)
- [ ] **Phase 3** — Assertions and the similarity backend (spec §3.4)
- [ ] **Phase 4** — Judge, Cohen's kappa, validation records, `validate-judge` (spec §3.5, §3.13)
- [ ] **Phase 5** — Snapshots (spec §3.6)
- [ ] **Phase 6** — Budgets and the unenforceable rule (spec §3.7)
- [ ] **Phase 7** — Cassettes and `import-cassettes` (spec §3.8, §3.13)
- [ ] **Phase 8** — Metamorphic layer and `freeze-variants` (spec §3.9, §3.13)
- [ ] **Phase 9** — Stability engine, collector, terminal + markdown reporters (spec §3.10–3.12)
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
