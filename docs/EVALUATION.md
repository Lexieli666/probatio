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
