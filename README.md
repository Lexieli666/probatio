# Probatio

Probatio is a **pytest plugin for regression-testing LLM applications**. You write cases in YAML,
one test function per suite, and keep running the suite you already have. It adds two disciplines
the software-testing literature has and LLM developer tooling mostly does not: **metamorphic
relations**, decorators that assert a semantics-preserving change to an input does not change the
verdict, reported as a per-relation violation rate; and **flakiness statistics**, repeated
execution with a per-case pass rate, a Wilson 95% interval and a suite stability score, instead of
running a nondeterministic system once and printing a tick. Everything else it ships — JSON-schema
validity, contains and not-contains assertions, similarity, a rubric judge with Cohen's κ against
human labels, snapshot baselines, cost and latency ceilings, record-replay cassettes, and
terminal, GitHub-summary, JUnit-XML and JSON reporters — is there so those two are usable on a
real suite. The judge shipped here has **measured agreement** with human labels, not validated
agreement; §*Case study* says what was measured and what it came to.

## Quick start

```bash
pip install probatio-llm
```

```yaml
# examples/demo_suite/cases/06-copd-spirometry.yaml
id: copd-spirometry
input: "In one sentence, what test confirms a diagnosis of COPD?"
assertions:
  - {type: contains, any: ["spirometry"]}
```

```python
# examples/demo_suite/test_demo.py
CASES = load_cases(HERE / "cases")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
@format_jitter(field="input.question")
def test_case(case, probatio, provider):
    probatio.check(case, sut=lambda c: answer(c, provider))
```

```bash
pytest examples/demo_suite --runs 5
```

That is shortened from [`examples/demo_suite/`](examples/demo_suite/), the executable
specification this tool was built against and which has not been edited since it was written. Every
line above is verbatim from it except one: the real test parametrizes over a filtered subset of
`CASES` rather than over `CASES` itself, because the demo routes its expected-fail and flaky cases
to their own test functions. What is left out is the rest of that case — a second assertion, a
budget, its tags — and the three other relations the real `test_case` carries. Note what the shown
case does *not* exercise: its `input` is a bare string, so `@format_jitter(field="input.question")`
reports **not applicable** on it rather than `0.00`, and
[`examples/demo_suite/cases/01-htn-definition.yaml`](examples/demo_suite/cases/01-htn-definition.yaml)
is the dict-input case, with a `question` and a list of `documents`, that the field relations
actually apply to.

## Metamorphic relations

A relation names a transformation that should preserve a case's meaning and asserts the verdict
does not move. Four ship as decorators — `@order_invariant`, `@paraphrase_invariant`,
`@distractor_robust`, `@format_jitter` — and each reports a violation rate **alongside** the case,
never folded into its pass or fail. A violation counts in either direction: a variant that passes
where the original failed breaks the invariant just as much.

From `pytest examples/demo_suite --runs 5`, run at commit `4c2114e` and recorded verbatim in
[`PROGRESS.md`](PROGRESS.md):

```
relations:
  relation              cases  n/a  violations  mean rate  worst case           worst rate
  --------------------  -----  ---  ----------  ---------  -------------------  ----------
  distractor_robust     7      1    0/70        0.00       gerd-alarm-features  0.00
  format_jitter         7      1    15/105      0.14       htn-definition       0.33
  order_invariant       6      2    0/50        0.00       gerd-alarm-features  0.00
  paraphrase_invariant  2      0    5/30        0.17       htn-definition       0.33
```

The `n/a` column is the point of the design: a relation a case is out of scope for — reordering a
one-element document list, rewording a case whose input is a bare string — reports *not
applicable*, never `0.00`. Paraphrases are generated once by `probatio freeze-variants`, reviewed
by a human and committed; they are never sampled during a test run.

## Flakiness statistics

`--runs N` runs each case N times and reports what happened, rather than what happened once. Same
run, same commit:

```
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
```

```
stability score: 0.90 over 12 repeated case(s)
cases whose Wilson lower bound is below their floor: 12 of 12
cost: $0.031500 (no --max-cost ceiling)
```

`flu-antivirals-flaky` declares `@flaky_tolerant(p=0.8, n=5)`, passes four of its five runs, and
passes the case at the bar its author wrote down; `anxiety-expected-fail` fails every run and is
in the suite so the report has a failure to show. The stability score is the mean of those twelve
pass rates.

**"12 of 12" is not twelve problems.** It counts the repeated cases whose Wilson *lower* bound
falls under their floor, and at n = 5 the lower bound of a perfect five-for-five is 0.57, so no
case can clear a floor of 1.0 however well it does — the line is a distance from the suite's own
floors, and it becomes informative when `--runs` is large enough for a bound to reach one
([`docs/stability.md`](docs/stability.md)). Nothing in it decides a verdict: the observed pass
rate does that.

The run also names what it could not check:

```
warnings (7):
  - htn-definition: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
  - htn-first-line: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
```

— and five more like them, one per judged case. A judge with no validation record on disk is not a
validated judge, and the tool says so about every suite, including its own.

## Prior art

The field is crowded and this table is the honest version of where Probatio sits. Every claim in
it is what that tool's own documentation says, **checked against each tool's documentation on
2026-09-05**; "not documented" means the page that would carry the feature was read and does not
carry it, not that the feature is absent.

| tool | what it is (their words) | pytest | repeated runs | interval on a per-case pass rate | metamorphic relations | JUnit XML |
|---|---|---|---|---|---|---|
| **DeepEval** | "plugs into Pytest, so `deepeval test run` collects and runs your eval files the same way pytest would"; a large catalog of "research-backed LLM-as-a-Judge" metrics | yes, native (`assert_test`) | not documented | none documented; a **flaky metric** flag instead | none documented | not documented |
| **promptfoo** | "open-source CLI and library for evaluating and red-teaming LLM apps" | no | **yes**, `--repeat <number>` | none documented | none documented | **yes**, `--output junit.xml` |
| **Giskard** | "enterprise platform and open-source library for LLM evaluation and security" | yes; behavioural tests "pass or fail under pytest" | not documented | none documented | the word does not appear; its scan is adversarial generation | not documented |
| **Ragas** | "move from 'vibe checks' to systematic evaluation loops"; RAG metrics | not documented | not documented | none documented | none documented | not documented |
| **Braintrust** | "the active observability platform for instrumenting, understanding, and improving agents" | not documented | not documented | none documented | none documented | not documented |
| **LangSmith** | "a framework for measuring quality throughout the application lifecycle" | **yes**, `@pytest.mark.langsmith` | **yes**, `num_repetitions` | mean and standard deviation; no interval documented | none documented | not documented |
| **Probatio** | this repository | yes, a plugin | yes, `--runs N` | Wilson 95% per case, plus a suite stability score and a floor marker | four, as decorators, with frozen variants | yes, with the statistics as `<properties>` |

Pages read on 2026-09-05: `deepeval.com/docs/getting-started` and `/docs/metrics-introduction`;
`promptfoo.dev/docs/intro` and `/docs/usage/command-line`; `docs.giskard.ai`;
`docs.ragas.io/en/stable`; `braintrust.dev/docs` and `/docs/guides/evals`;
`docs.langchain.com/langsmith/evaluation-concepts`, `/langsmith/pytest`, `/langsmith/repetition`
and `/langsmith/evaluate-llm-application`.

**What is not a differentiator, said plainly.** Being pytest-native is not one: DeepEval, Giskard
and LangSmith all are, and DeepEval owns that ground with a far larger metric catalog. Running a
case repeatedly is not one: promptfoo has `--repeat` and LangSmith has `num_repetitions`. JUnit
output is not one: promptfoo writes `junit.xml`. If you want a metric catalog, use DeepEval; if
you want a red-teaming engine, use promptfoo or Giskard; if you want hosted eval tracing, use
Braintrust or LangSmith. Probatio is meant to sit beside them.

**What is.** A confidence interval on a per-case pass rate, a suite-level stability score, and a
floor marker (`@flaky_tolerant(p, n)`) that holds a case to a number somebody wrote down — none of
the six documents any of these. And metamorphic relations as stated invariants, declared as
decorators on the test: none of the six documents those either, and Giskard's scan is adversarial
generation, which searches for inputs that break a system rather than checking a property the
system is supposed to have. The one-sentence contrast that matters: **DeepEval's answer to a flaky
metric is a flag that makes its failure non-deciding; Probatio's is to run the case n times and
report the rate, the interval and the floor.**

Metamorphic testing of LLMs exists as research, and Probatio claims no new relation — its four are
packaging, with reviewable frozen variants, of transformations these papers name. LLMorph
`[LLMORPH]` and MTF `[MTF]` are the two research frameworks in this space; the NLP catalogue
`[MR-CATALOG-NLP]` collected **191** metamorphic relations in a literature review, of which 36
were implemented, and it is the source `order_invariant` and `paraphrase_invariant` cite. Chen et
al. `[CHEN-MT-SURVEY]` and Segura et al. `[SEGURA-MT-SURVEY]` are the surveys for the definition
of a relation and for violation-as-oracle. Full entries, with authors, venues, years and DOIs
verified against Crossref on 2026-09-05, are in [`docs/relations.md`](docs/relations.md).

## Case study

Probatio was dogfooded on
[Consilium-Health](https://github.com/Lexieli666/consilium-health), the author's own
public multi-agent retrieval-grounded
question-answering project, along two routes. Both are written up with their limitations in
[`docs/CASE_STUDY.md`](docs/CASE_STUDY.md), and every number below is re-derived from a committed
artefact by `tests/test_docs_case_study.py`.

**Route A — a retrospective catch, and the headline claim.** Fifteen of Consilium's golden items
replay through Probatio from its published traces, against two recorded configurations. On
`baseline_llm`, a single call with no retrieval and no agents, all fifteen pass. On the
multi-agent `full` pipeline, **five of the six red-flag cases fail** — each on a `contains`
assertion carrying Consilium's own thirty-eight escalation phrases, and on nothing else — while
**none fails on `baseline_llm`**. That is a safety regression Consilium had already documented in
its own `docs/FAILURE_CASES.md`, reproduced as a failing `pytest` run from committed tapes with no
model called. It is labelled retrospective in the case study, because it is: the suite was written
after the regression was known.

**Route B — prospective in form.** One flag changed, `claude-opus-5` to
`claude-haiku-4-5-20251001`, on a live single-call system under test, with nothing else moved.
The suite reported that **4 of 15 verdicts moved**, all of them on the judge; that the judge marked
**a third of the cases** (5 of 15) unfaithful to their sources, naming the sentence in each; that
eight snapshots drifted, three of them on cases whose every assertion still passed; that
`paraphrase_invariant` went from 0.04 to 0.30 under rewordings a human had confirmed do not change
the question; and that the cheaper recording cost **$0.987356 against $6.037457** in notional API
price, a six-fold difference. It is prospective in form — suite first, change second, outcome
unknown in advance — and it is on a system under test built for the purpose, not on a shipping
application. The case study says so in those words.

Dogfooding also found three things wrong with Probatio itself — two defects and one gap that nine
phases of unit tests had not reached — all fixed during Phase 12 and listed with the commit that
fixed each in [`docs/EVALUATION.md`](docs/EVALUATION.md) §7.

## Design positions

**Similarity is for paraphrase-stable content; a judge is for claims.** Reach for `similarity`
when what you are protecting is wording that should stay roughly the same, and for a `judge` when
it is whether a claim is true, grounded or complete. The docs take that position rather than
listing options, because the substitution fails in a way a threshold cannot fix: a trigram cosine
scores a sentence that *contradicts* the reference at 0.223 while the same claim in different
words scores 0.453, so the ordering is wrong, not the number
([`docs/assertions.md`](docs/assertions.md), rationale in [`docs/DESIGN.md`](docs/DESIGN.md)).

**An unenforceable ceiling is never a pass.** A `max_cost_usd` ceiling evaluated where any call's
cost is unknown cannot be checked, so it is reported as unenforceable, listed under warnings, and
excluded from passing checks — never quietly satisfied by treating unknown as zero. The same holds
for a case that recorded no provider calls at all: a check that cannot fail is not a check. This
is the failure mode a testing tool must not have, and it is why `Completion.cost_usd` is `None`
rather than `0.0` when nobody priced the call (`docs/DESIGN.md`, Phases 6 and 11).

**Frozen variants.** Paraphrases are generated once by `probatio freeze-variants`, written to
`variants/<case_id>.yaml` with their provenance, reviewed, and committed. Three reasons in order:
the suite stays deterministic; the model is not part of the oracle at test time; and the variants
are in the diff, so a reviewer can throw out a rewording that changed the meaning. That last one is
not hypothetical — **2 of 45** frozen paraphrases were deleted at review in this project, each
noted in its file's header ([`docs/EVALUATION.md`](docs/EVALUATION.md) §3).

**A plugin, not a platform.** Teams do not migrate eval platforms mid-quarter; they add a
dependency to the tests they already run. So Probatio is four runtime dependencies, one entry
point, a `Provider` protocol of one method, and reporters that write into CI you already have —
JUnit XML and a GitHub job summary — rather than a dashboard to log into. No hosted service, no
async, no metric catalog (`docs/DESIGN.md`, Phase 0).

## Install

The distribution is named `probatio-llm`; the import name is `probatio`.

```bash
pip install probatio-llm                  # core: pytest, pydantic, jsonschema, PyYAML
pip install "probatio-llm[anthropic]"     # plus the Anthropic SDK adapter
pip install "probatio-llm[dev]"           # ruff, mypy, coverage, build, twine
```

Python 3.11 or newer. The `claude-cli` provider needs no extra and no API key — it runs the Claude
Code CLI as a subprocess, so a developer on a Claude plan can record cassettes and freeze variants;
the cost it reports is *notional* API price, not money billed, and
[`docs/providers.md`](docs/providers.md) says so wherever that figure is used.

> The unrelated PyPI placeholder distribution `probatio` also installs a `probatio/` import
> package. Do not install both into the same environment.

## Status and roadmap

Pre-1.0. Phase-by-phase state, with the gate result and the run log for each phase, is in
[`PROGRESS.md`](PROGRESS.md); every judgement call made without asking is numbered in
[`DECISIONS.md`](DECISIONS.md); anything abandoned is in [`BLOCKERS.md`](BLOCKERS.md). Every number
in this file and under `docs/` is indexed in [`docs/PROVENANCE.md`](docs/PROVENANCE.md) with the
committed file it came from and the command that regenerates it.

Next, in the order they would be built:

- **Per-run fixture isolation.** `--runs N` repeats inside one pytest item, so function-scoped
  fixtures are shared across the runs. That is deliberate — it measures the model's
  nondeterminism, not state leakage — but a suite that wants a fresh fixture per run has to build
  it inside its own callable today (`docs/stability.md`).
- **A minimum-κ gate.** `probatio validate-judge --min-kappa` already exits non-zero, but a suite
  cannot yet declare a floor that fails the build the way a budget overrun does. The judge in this
  repository scored κ 0.600 on one blind forty-row sample and 0.253 on another, which is the
  argument for the gate and for reporting the number rather than the adjective.
- **The variance study.** The `--runs` engine is also an instrument: run a benchmark subset n
  times and measure how often rankings flip. Seeded as an optional phase in `PROGRESS.md`, and
  the one thing that would settle whether the judge or the answer is the unstable half of this
  project's own relation rates (`docs/EVALUATION.md` §2).

## License

MIT. See [`LICENSE`](LICENSE).
