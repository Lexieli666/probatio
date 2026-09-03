# Probatio

*A pytest plugin for regression-testing LLM applications.*

> **Status: pre-release scaffolding.** Every section below is a placeholder. Nothing is described
> here as working until the phase that implements it has a committed, green run behind it. No
> number appears in this file that a committed run did not produce.

## Quick start

*Placeholder. A fifteen-line quick start lands with the reporters (Phase 9).*

## Metamorphic relations

*Placeholder. Filled in from a committed run of `examples/demo_suite/` (Phase 9).*

## Flakiness statistics

*Placeholder. Filled in from a committed run of `examples/demo_suite/` (Phase 9).*

## Prior art

*Placeholder. The comparison table is written and source-verified in Phase 13.*

## Case study

*Placeholder. Summary of `docs/CASE_STUDY.md` (Phase 12).*

## Design positions

*Placeholder. Similarity versus judge; unenforceable ceilings; frozen variants; plugin, not
platform. Rationale accumulates in `docs/DESIGN.md`.*

## Install

The distribution is named `probatio-llm`; the import name is `probatio`.

```bash
pip install probatio-llm                  # core
pip install "probatio-llm[anthropic]"     # plus the Anthropic SDK adapter
```

> The unrelated PyPI placeholder distribution `probatio` also installs a `probatio/` import
> package. Do not install both into the same environment.

## Status and roadmap

Phase-by-phase state lives in [`PROGRESS.md`](PROGRESS.md). Judgement calls are numbered in
[`DECISIONS.md`](DECISIONS.md); abandoned work is listed in [`BLOCKERS.md`](BLOCKERS.md).

## License

MIT. See [`LICENSE`](LICENSE).
