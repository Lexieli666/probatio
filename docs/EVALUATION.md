# Evaluation: what Probatio measured, on what, and with which model

Every number here comes from a file committed in this repository, named where it is used.
`tests/test_docs_evaluation.py` re-derives each one from the artefact it claims to come from, so a
figure that drifts from its run fails the suite rather than sitting in a document.

Two claims are *not* from this repository and are labelled where they appear: Consilium-Health's
published per-turn costs and its GPT-4o-mini judge kappas, both from its own `docs/EVALUATION.md`
and `report.md` at commit `109a744`, run `20260830T170133Z`.

## 1. The model, and what was run against it

One model answers everything in Phase 12: **`claude-opus-5`**, reached through
`ClaudeCLIProvider`, which runs the Claude Code CLI as a subprocess so that recording needs a
Claude plan and no API key. The judge follows the provider, so the judge is the same model. Route B
of `docs/CASE_STUDY.md` records the same fifteen cases a second time against
**`claude-haiku-4-5-20251001`** and changes nothing else.

The suite is `examples/consilium/live/`: fifteen of Consilium-Health's golden items, answered by a
**single-call grounded question-answering app** that is not Consilium's pipeline and is not a
reimplementation of it (`examples/consilium/live/README.md` says so at the top, and
`docs/CASE_STUDY.md` §5 repeats it as a limitation). Nothing measured here is a measurement of
Consilium-Health.

Recording cost 278 live calls — one system-under-test call and one judge call for each case and
for each of its 124 relation variants — and the replay that produced every figure below
(`examples/consilium/live/results/live-baseline.json`) makes none.

## 2. What the metamorphic relations did on real model output

From `examples/consilium/live/results/live-baseline.json`. A violation is a variant whose verdict
differs from the original case's, in either direction. `mean rate` is the mean of the per-case
rates, which is what the report prints; `violations` is the raw count over every variant
evaluated.

| relation | cases | n/a | violations | mean rate | worst case | worst rate |
|---|---|---|---|---|---|---|
| `distractor_robust` | 15 | 0 | 5/30 | 0.17 | `g-cc-002` | 0.50 |
| `format_jitter` | 15 | 0 | 6/45 | 0.13 | `g-cc-017` | 0.67 |
| `order_invariant` | 6 | 9 | 0/6 | 0.00 | `g-cc-001` | 0.00 |
| `paraphrase_invariant` | 15 | 0 | 2/43 | 0.04 | `g-cc-017` | 0.33 |

**The null result is `order_invariant`, and it is reported as one.** Nine of the fifteen cases
carry a single document, so there is no non-identity ordering and the relation is *not applicable*
rather than satisfied — it reports `None`, not `0.0`, which is the rule spec §3.9 fixes and
DECISIONS 8 argues for. Over the six cases where it could fire, reordering the documents changed
no verdict at all.

**Twelve of the thirteen flips are the judge.** Across all four relations there are 13 verdict
flips, and the changed assertion is `judge` in 12 of them and `contains` in one. No `similarity`
and no `not_contains` assertion flipped anywhere. Two readings are consistent with that and this
suite cannot separate them: a variant produces a genuinely different answer, and the judge grades
that different answer differently; or the judge is simply the least stable assertion in the suite.
Separating them needs the same variant answered repeatedly, which is what `--runs` is for and
which this phase did not do.

**The one non-judge flip runs against the story.** `g-md-018` fails its escalation `contains`
assertion as recorded, and passes it when an unrelated clinical document is appended
(`distractor-end-1`) — a flip from failing to passing. Both directions count as violations, which
is why it is here.

**Two of the fifteen cases measure something extra under `paraphrase_invariant`.** `g-su-002` and
`g-su-003` are the two golden questions written as deliberately misspelled, low-literacy phrasings
(`sied`, `speach`, `minits`, `somethin`). All six of their frozen paraphrases silently correct the
spelling. None of them changes a symptom, a patient, a number or a duration, so none was deleted at
review — but on those two cases the relation measures spelling normalisation alongside rewording,
and their contribution to the 0.04 should be read that way.

## 3. The frozen paraphrases, and what a human deleted

`probatio freeze-variants` asked `claude-opus-5` for three paraphrases of `input.question` for each
of the fifteen cases, and a human read all 45 before any of them was used.

**2 of 45 variants were deleted at review.** 43 stand, in
`examples/consilium/live/variants/*.yaml`. Each deletion is recorded in its file's header:

- `g-md-017` [3] — "Feeling ill **after** a full day with blood sugar levels over 20 …". The tense
  change makes an ongoing emergency sound over, where the original is ongoing.
- `g-su-003` [3] — "I had an **episode** earlier today where one side of my face went odd …".
  "An episode" is clinical framing the lay original does not use, and it cues a transient
  neurological event, which makes this red-flag question easier than the one that was asked.

Both files keep two paraphrases and the relation is measured over two, reporting `n_variants: 2`.
That is DECISIONS 52 in practice: a relation that refused a short file would punish exactly the
review the frozen file exists for.

Freezing took 18 live calls rather than 15, because three replies came back as several JSON arrays
on separate lines instead of one array of `k`, and the validator refuses a reply that is not
exactly `k` distinct non-empty strings.

## 4. Judge validation against eighty blind human labels

**The two judges rank the two samples in opposite orders.** On Consilium's sample 1 the Claude
judge scores κ = 0.600 where the GPT-4o-mini judge scored 0.350; on sample 2 it scores κ = 0.253
where GPT-4o-mini scored 0.592. Same eighty human labels, same two label sets, and the ordering
reverses. That is the most important thing in this document, and it is a caution about reading a
single κ as a property of a judge: it is a property of a judge *on a sample*.

| sample | n | judge | agreement | κ | rows re-asked | record |
|---|---|---|---|---|---|---|
| sample 1 | 40 | `claude-opus-5`, `faithfulness` (v2-derived) | 0.800 | **0.600** | 8 | `examples/consilium/live/results/judges-sample-1/faithfulness.validation.json` |
| sample 2 | 40 | `claude-opus-5`, `faithfulness` (v2-derived) | 0.675 | **0.253** | 5 | *not committed — see below* |
| sample 1 | 40 | GPT-4o-mini, Consilium `faithfulness` v1 | 0.675 | 0.350 | n/a | Consilium-Health `docs/EVALUATION.md` |
| sample 2 | 40 | GPT-4o-mini, Consilium `faithfulness` v2 | 0.800 | 0.592 | n/a | Consilium-Health `docs/EVALUATION.md` |

The comparison is not like for like in one respect, and it matters: the two GPT-4o-mini figures
come from **two different rubrics** — Consilium ran v1 on sample 1 and v2 on sample 2, and the
improvement from 0.350 to 0.592 is what v2 was written to produce. Probatio ran **one** rubric, the
v2-derived one in `examples/consilium/live/rubrics/faithfulness.md`, on both samples. So the
reversal is measured against a moving comparator on one side and a fixed one on the other. What
survives that caveat is the narrower claim: one rubric and one judge produced κ = 0.600 on forty
labelled rows and κ = 0.253 on another forty, and neither number predicts the other.

Probatio's kappa implementation is checked against Consilium's published figures on the same CSVs
by `tests/test_judge_kappa.py`, which reproduces 0.350/0.675 and 0.592/0.800 from the
`judge_label` and `human_label` columns, so the two GPT-4o-mini rows above are cross-checked
against an independent implementation rather than quoted.

**Why sample 2 has no committed record.** The measurement is real: n = 40, agreement 0.675,
κ = 0.253, 5 rows re-asked, and its summary line is in `PROGRESS.md` verbatim. Its validation
record was not committed because `labels_file` carried an absolute path through a home directory,
which is what DECISIONS 93 then fixed at the root. Three attempts made after that fix all failed
(§5), and rather than raise the re-ask bound until a number appeared, or write a record naming a
labels file the command did not name, `.probatio/judges/` is left with **no faithfulness record at
all**. The consequence is visible and intended: every run of the live suite reports fifteen
`judge verdict(s) from a rubric with no validation record` warnings, and every judge
`AssertionResult` carries `unenforceable=True`. The judge is unvalidated, so the suite says the
judge is unvalidated.

## 5. Provider reliability, measured by accident

Grading eighty rows through `ClaudeCLIProvider` on `claude-opus-5` produced enough failures to be
worth reporting as data. The rows carry ≈23,500 characters of `sources_text` each, against ≈10,000
for a live case, and the failure is concentrated in one place: the verdict and the score are
complete and the `rationale` string stops mid-sentence, so the reply is not JSON at all rather than
a wrong verdict. One captured example is committed at
`tests/fixtures/claude_cli_truncated_judge_reply.txt`; `json.loads` on it raises
`Unterminated string starting at` with `colno == 49`, which is the column where the rationale
opens.

Sample 2 was attempted **six times and completed once**:

| attempt | outcome | live calls |
|---|---|---|
| 1 | aborted: row 10 unparsable, before any re-ask existed | 10 |
| 2 | aborted: row 6 unparsable, same reason | 6 |
| 3 | **completed**: κ = 0.253, 5 of 40 rows re-asked | 46 |
| 4 | crashed: `the Claude CLI exited 1 for 'claude -p'; stderr: <empty>` | ~12 |
| 5 | stopped: row 13 re-asked once, then row 16 unparsable three times running | 19 |
| 6 | stopped: four rows re-asked, then row 35 unparsable three times running | 42 |

Sample 1 completed on its first attempt, with 8 of 40 rows re-asked, in 48 calls.

Two things follow. First, the per-row failure rate is roughly one reply in eight, which is why
retrying the whole forty-row command is close to futile and why the re-ask is per row
(DECISIONS 92). Second, **the re-ask is bounded at `cli.JUDGE_ATTEMPTS = 3`** and the bound fired
twice, on different rows each time. A row that fails three times running has no verdict, so the run
stops rather than reporting a comparison over 39 rows as though it were over 40. Every completed
run's re-ask count is written into its validation record as `rows_reasked`, so the cost of getting
an answer is visible beside the answer.

Attempt 4's crash — exit status 1 with an empty stderr, mid-run, on a call indistinguishable from
the ones around it — is recorded in DECISIONS 94 alongside the truncation, because it is the same
kind of fact: a property of a version of somebody else's program, and the kind of thing that reads
as a Probatio bug the first time it is met.

### Recording Route B, and the timeout the default could not carry

The haiku recording met the same conditions from the other side. By then roughly 600 calls had
been made in one day, a single call was taking 40 to 90 seconds against opus's 12, and the
occasional one exceeded two minutes — which is `ClaudeCLIProvider`'s shipped `DEFAULT_TIMEOUT_S`,
so it failed the case with `the Claude CLI did not answer within 120s`.

Producing the fifteen committed haiku tapes took **five invocations and about three and a quarter
hours of wall clock**: one attempt stopped early with four cases complete, one 86-minute run that
left four tapes incomplete, a 47-minute re-record of six, a 21-minute attempt at the last two, and
finally one case on its own. `g-su-002` failed three times, every time on the 120-second timeout.

That is what produced `--probatio-timeout` (DECISIONS 95). `ClaudeCLIProvider.timeout_s` had been
a constructor argument since Phase 2 so that a caller could change it, and no flag reached the
constructor, so a user recording on a throttled plan had no way to say so without writing their own
`provider` fixture. With `--probatio-timeout 600` the case recorded on the next attempt. The
timeout is not part of a cassette key, so the tape is indistinguishable from one recorded under the
default.

Two smaller facts from the same exercise, both now written into
`examples/consilium/live/README.md` and `PROGRESS.md` so the next person does not rediscover them:
a tape is complete when it holds `2 * (1 + variants)` interactions, and **a case re-recorded after
a partial failure keeps orphaned judge interactions**, because a judge call's cassette key includes
the answer it grades and the re-recorded answer differs. Two tapes carried orphans and were deleted
and recorded again, so every committed haiku tape holds exactly the interactions its case needs and
the fifteen total exactly 278 — the same count as the opus tapes, which is the arithmetic above
rather than a coincidence.

## 6. Cost cross-check against Consilium's published figures

The offline suite prices Consilium's own recorded token counts, so it can be checked against the
per-turn costs Consilium published for the same run. From
`examples/consilium/results/replay-priced.json`, priced at the rates in
`examples/consilium/prices.yaml` ($0.15 input and $0.60 output per Mtok for
`gpt-4o-mini-2024-07-18`, read off the provider's price page on 2026-09-04):

| configuration | Probatio, mean over the 15-case subset | Consilium, published mean over 150 items |
|---|---|---|
| `baseline_llm` | $0.000128 | $0.0001 |
| `full` | $0.000877 | $0.0012 |

`baseline_llm` agrees to the precision Consilium published. `full` is 73% of the published figure,
and **the reason is the subset, not the pricing method**. Both sides price the same thing — the
tokens of the traced `llm_call` events, at the same rates — and the token counts move together
with the costs: the fifteen `full` traces average **4,858 tokens per turn** against the **6,714**
Consilium published over all 150, which is 72%, against a cost ratio of 73%. The fifteen items were
selected by the rule in `examples/consilium/README.md`, which takes the four `FAILURE_CASES.md`
items first and then fills each block red-flag-first; nothing in that rule selects for length, but
nothing in it controls for length either, and the subset happens to be shorter than the corpus
average.

The total for the thirty priced cases is **$0.015070**. Two caveats carry from
`docs/CASE_STUDY.md` §5: these costs are notional, computed from recorded tokens rather than from
an invoice, and the run that produced the answers was billed to Consilium's account. The same
applies to the live suite's `$6.037457`, which is what the Claude CLI reported as the notional API
price of 278 calls made on a subscription that was not billed that money — `docs/providers.md`
states that caveat for `ClaudeCLIProvider` generally.

## 7. What dogfooding found about Probatio itself

The Consilium suites were built to test Consilium's answers. They also tested Probatio, and they
found three things nine phases of unit tests and `pytester` sessions had not. Each is recorded as
a numbered decision and fixed in a named commit; none was found by review.

| # | what the suites exposed | kind | fixed in |
|---|---|---|---|
| DECISIONS 90 | The cassette store's active case covered the system under test only, so a `judge` call — made while the case's assertions are being evaluated — and every relation-variant call reached the store with no case to file under. The first live recording died on its first case with `a cassette call was made outside a case`. | defect | `528333f` |
| DECISIONS 92 | `validate-judge --run-judge` propagated an unparsable judge reply, so one bad row in forty ended a forty-row run. Against a real model that is roughly one row in eight, which makes a whole-command retry succeed about one time in sixty. | defect | `3ffde31` |
| DECISIONS 95 | `ClaudeCLIProvider.timeout_s` had been a constructor argument since Phase 2 with no flag reaching it, so a developer recording on a throttled plan could not raise the 120-second default without writing their own `provider` fixture. | gap | `15651f2` |

**Why the first two survived nine phases.** Both live in the seam between two features that had
never been exercised together. No suite before `examples/consilium/live/` had combined a cassette
store with a judge assertion or with a relation, because the demo suite records no tapes and the
offline Consilium suite carries no judge; the active-case context and the completion sink had been
sharing one `try/finally`, so a change to the one that mattered for budgets silently made the
other wrong. And no test had ever handed `validate-judge --run-judge` a reply that was neither a
verdict nor absent, because a `FakeProvider` returns what it was scripted to return. A fixture is
a hypothesis about what a provider does; two of these are what happens when the hypothesis meets
forty rows of a real one.

**The third is not a defect and is listed anyway.** Nothing was wrong with the timeout's value or
with the code that used it; the argument simply had no path from the command line, which no test
could have noticed because every test constructs the provider directly. It is here because the
distinction between "the code is wrong" and "the code cannot be reached from where a user stands"
is invisible from inside a test suite and obvious the first time somebody uses the tool for
something they actually wanted.

Two smaller corrections came out of the same work and are recorded with them: the validation
record's `labels_file` now goes through `artefacts.display_path` so a committed record names the
repository rather than a home directory (DECISIONS 93, commit `ceed3f9`), and `Judge.parse` quotes
the reply it could not parse, which is what let one real truncated reply become
`tests/fixtures/claude_cli_truncated_judge_reply.txt` instead of an invented one (DECISIONS 94,
same commit).

## 8. Repetition: what ten runs and ten gradings showed

The question is the one a single evaluation run cannot answer about itself: **how much confidence
does one run carry?** Phase 15 asks it twice of the same fifteen live cases, both times through
`ClaudeCLIProvider` on `claude-opus-5`, both times recorded so that every figure below replays
offline.

- **Experiment A** answers each case ten times and reports a pass rate with a Wilson 95% interval:
  300 live calls, ten answers and ten gradings a case, in
  `examples/consilium/live/cassettes-n10/test_live_variance/` and replayed into
  `results/live-n10.json`, `.md` and `.xml`. The suite is `test_live_variance.py`, which carries no
  relation decorator and no `flaky_tolerant` marker (DECISIONS 104).
- **Experiment B** holds the answer still. For each case it takes the `claude-opus-5` completion
  Phase 12 committed in `cassettes/test_live/` and asks the same judge, with the same rubric and
  the same prompt template, to grade those exact bytes ten times: 150 live calls, in
  `cassettes-judge-x10/judge_repeatability/` and reduced to `results/judge-repeatability.json`.

**This is a seed, not a study.** Fifteen cases, one model, one rubric, one recording session.
Nothing below is a claim about evaluation runs in general, about other suites, or about how many
runs a benchmark needs. It is what these fifteen cases did.

### 8.1 Experiment A: the same case, ten times

From `examples/consilium/live/results/live-n10.json`. The **majority verdict** is the verdict of
more than half the runs, which is what the report keys a case's row on (DECISIONS 64); it is not
the `verdict` column of `live-n10.md`, which says whether `check` let the case through, and under
a default floor of 1.00 a case at 0.90 does not get through.

| case | runs passed | pass rate | 95% Wilson | majority verdict |
|---|---|---|---|---|
| `g-cc-001` | 10/10 | 1.00 | [0.72, 1.00] | pass |
| `g-cc-002` | 9/10 | 0.90 | [0.60, 0.98] | pass |
| `g-cc-017` | 8/10 | 0.80 | [0.49, 0.94] | pass |
| `g-ge-001` | 9/10 | 0.90 | [0.60, 0.98] | pass |
| `g-ge-002` | 10/10 | 1.00 | [0.72, 1.00] | pass |
| `g-ge-024` | 9/10 | 0.90 | [0.60, 0.98] | pass |
| `g-gh-001` | 10/10 | 1.00 | [0.72, 1.00] | pass |
| `g-gh-002` | 10/10 | 1.00 | [0.72, 1.00] | pass |
| `g-gh-017` | 10/10 | 1.00 | [0.72, 1.00] | pass |
| `g-md-017` | 10/10 | 1.00 | [0.72, 1.00] | pass |
| `g-md-018` | 2/10 | 0.20 | [0.06, 0.51] | fail |
| `g-md-021` | 9/10 | 0.90 | [0.60, 0.98] | pass |
| `g-su-001` | 9/10 | 0.90 | [0.60, 0.98] | pass |
| `g-su-002` | 8/10 | 0.80 | [0.49, 0.94] | pass |
| `g-su-003` | 9/10 | 0.90 | [0.60, 0.98] | pass |

The suite's stability score — the mean of those fifteen rates — is **0.88**, and the recording's
notional price was **$3.690520**.

**The two numbers this experiment was run for.**

- **9 of 15** cases have at least one run whose verdict disagrees with the case's own majority. A
  single run of this suite therefore has a better than even chance of reporting, for some case, a
  verdict that the same suite contradicts on repetition.
- **15 of 15** cases have a Wilson lower bound below 0.8 — including the six that passed all ten
  runs, because the 95% lower bound at 10 of 10 is 0.72. That second number says more about **n**
  than about the cases: ten runs cannot establish a rate above 0.8 for anything. It is reported
  because the runbook asks for it, and it should be read as the interval doing its job rather than
  as fifteen unreliable cases.

**One case is not like the others.** `g-md-018` is the red-flag case Phase 12 recorded as failing
its escalation `contains` assertion, and `docs/CASE_STUDY.md` §2 reports that single failure. Over
ten answers the assertion passes **4 of 10** times: the answer sometimes contains one of
Consilium's thirty-eight escalation phrases and sometimes does not. The Phase 12 report was not
wrong, and it was one draw from a distribution it could not see.

### 8.2 Experiment B: the same answer, ten gradings

From `examples/consilium/live/results/judge-repeatability.json`. The input to a case's ten
gradings is byte-identical, so the ten calls share one cassette key and each tape holds one
interaction with ten samples — which
`tests/test_consilium_judge_repeatability.py` asserts, because it is the claim the experiment
rests on. `unparsable` is a reply that was not the strict JSON object the template asked for; it
is recorded as the grading it was rather than re-asked (DECISIONS 107).

| case | ten verdicts | scores seen | passes | 95% Wilson |
|---|---|---|---|---|
| `g-cc-001` | 9/10 pass · 1/10 unparsable | 1.00 | 9/10 | [0.60, 0.98] |
| `g-cc-002` | 8/10 pass · 2/10 unparsable | 1.00 | 8/10 | [0.49, 0.94] |
| `g-cc-017` | 7/10 pass · 3/10 unparsable | 1.00 | 7/10 | [0.40, 0.89] |
| `g-ge-001` | 10/10 pass | 1.00 | 10/10 | [0.72, 1.00] |
| `g-ge-002` | 10/10 pass | 1.00 | 10/10 | [0.72, 1.00] |
| `g-ge-024` | 10/10 pass | 1.00 | 10/10 | [0.72, 1.00] |
| `g-gh-001` | 9/10 pass · 1/10 unparsable | 1.00 | 9/10 | [0.60, 0.98] |
| `g-gh-002` | 10/10 pass | 1.00 | 10/10 | [0.72, 1.00] |
| `g-gh-017` | 10/10 pass | 1.00 | 10/10 | [0.72, 1.00] |
| `g-md-017` | 9/10 pass · 1/10 unparsable | 1.00 | 9/10 | [0.60, 0.98] |
| `g-md-018` | 10/10 pass | 1.00 | 10/10 | [0.72, 1.00] |
| `g-md-021` | 9/10 pass · 1/10 unparsable | 1.00 | 9/10 | [0.60, 0.98] |
| `g-su-001` | 10/10 pass | 1.00 | 10/10 | [0.72, 1.00] |
| `g-su-002` | 7/10 fail · 3/10 pass | 0.89, 0.91, 0.92, 0.93, 1.00 | 3/10 | [0.11, 0.60] |
| `g-su-003` | 10/10 pass | 1.00 | 10/10 | [0.72, 1.00] |

**7 of 15** cases did not give the same verdict ten times. That headline needs its two halves kept
apart, because they are different phenomena:

- **Six of the seven differ only by a reply that was not a verdict at all.** Across the 150
  gradings, **9 of the 150** produced no parsable JSON. That is the truncation `docs/EVALUATION.md`
  §5 and DECISIONS 94 describe, met again — and met here on the *live* suite's own prompts, where
  Phase 12's single pass over the same fifteen answers produced no unparsable reply at all
  (`tests/test_consilium_live_replay.py` asserts that of the committed tapes). Repetition found
  it; one pass did not.
- **One case disagreed with itself about the answer.** `g-su-002` graded the same bytes `fail`
  seven times and `pass` three, with scores of 0.89, 0.91, 0.92, 0.93 and 1.00. It is the only one
  of the fifteen that produced both a `pass` and a `fail` on identical input — **1 of 15**.

### 8.3 What the two tables show, and what they do not

Experiment A leaves §2's question open by construction: when a case's verdict moves between runs,
the answer changed and the grading changed together, and nothing in a repeated end-to-end run can
separate them. Experiment B removes one half, and the two tables placed side by side say this
much. Of the 150 judge calls experiment A made, **137 of 150** returned a passing verdict,
**4 of 150** returned `fail` and **9 of 150** returned no verdict at all; and every failing run of the fourteen cases other
than `g-md-018` coincided with a judge call that did not return a passing verdict, so on this
suite the judge — not the answer — is where almost all the run-to-run movement is. Experiment B then shows that most of *that* is the
judge failing to produce a verdict rather than producing a different one: on identical input,
fourteen of fifteen cases never changed their mind, and one did.

What this does not show: that the same holds for other suites, other rubrics, other models or
other question types; that 0.88 is a stability score to expect anywhere else; or that ten runs is
the right n. Fifteen cases answered ten times is a seed. It is enough to say that on this suite a
single run's verdict is not the same object as its majority verdict, and that the cheapest way to
find out how far apart they are was to run it ten times and read the interval.
