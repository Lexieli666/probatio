# docs/assertions.md — the five assertions

An assertion is a claim about one output. Probatio evaluates every assertion a case declares,
in declaration order, and returns one `AssertionResult` for each; nothing stops at the first
failure and nothing raises. A report therefore shows every way an answer is wrong, which is the
information you need to decide whether the application regressed or the case was always fragile.

```python
class AssertionResult(BaseModel):
    assertion_type: str        # "contains", "schema_valid", ...
    passed: bool               # never True when unenforceable
    score: float | None        # 0..1 where a number means something
    detail: str                # one or two readable lines
    unenforceable: bool        # the check could not be carried out at all
```

`score` exists so that a snapshot in `scores` mode can see a case degrade before it turns red: an
answer that matched four of four required substrings last week and three of four today is a
failure, but an answer that slipped from a similarity of 0.71 to 0.62 against a floor of 0.35 is a
warning sign you can read off a diff. `unenforceable` is the third state between pass and fail: a
judge with no provider configured, or a cost ceiling on a model nobody priced, is a check that did
not happen, and it is never counted as a pass. One case is weaker on purpose — a judge that graded
against an unvalidated rubric is marked unenforceable *and* keeps its verdict, because the verdict
is the only evidence there is; see the judge section below.

## `contains`

```yaml
- {type: contains, all: ["lifestyle", "thiazide"], any: ["ACE inhibitor", "angiotensin"]}
- {type: contains, any: ["metformin"], case_sensitive: true}
```

Every substring in `all` must appear, and at least one substring in `any` must appear. At least
one of the two lists has to be non-empty; a `contains` assertion that asks for nothing would
always pass, so the loader rejects it.

**Scoring.** The fraction of all declared substrings — `all` and `any` together — that appear.
The score and the verdict deliberately disagree: an assertion with `any: [a, b, c, d]` that
matches one substring passes with a score of 0.25, because one match is what `any` asked for and
0.25 is what changed.

**Case.** Folded by default, so a heading that starts capitalising differently after a prompt
tweak does not fail the suite. Set `case_sensitive: true` when the casing is the thing under test.

## `not_contains`

```yaml
- {type: not_contains, all: ["I don't know", "as an AI language model"]}
```

None of the substrings in `all` may appear. This is where refusals, hedging boilerplate and
leaked prompt scaffolding go.

**Scoring.** The fraction of forbidden substrings that are absent. The detail names the ones that
appeared.

## `schema_valid`

```yaml
- type: schema_valid
  schema:
    type: object
    required: [screen, start_age]
    properties:
      screen: {type: boolean}
      start_age: {type: integer}
    additionalProperties: false
```

The output must parse as JSON and validate against a JSON Schema, given either inline as `schema`
or as a path in `schema_file` — exactly one of the two. A relative `schema_file` is resolved
against pytest's rootdir, so a case file stays portable between checkouts.

Exactly one fenced code block wrapping the whole output is stripped before parsing, because models
asked for JSON very often return ```` ```json ```` around it. One, not all: an output that is a
fence containing prose that contains another fence is not JSON, and unwrapping until something
parsed would let a malformed answer through.

**Scoring.** 1.0 when the output validates, 0.0 when it does not. The detail lists the first
three validation errors with their JSON paths, then counts the rest:

```
3 validation errors: $.screen: 'yes' is not of type 'boolean'; $.start_age: 'thirty-five' is not
of type 'integer'; $: Additional properties are not allowed ('note' was unexpected)
```

Output that is not JSON at all is a failed result naming the parse position, not an exception.

## `similarity`

```yaml
- type: similarity
  reference: "Metformin is the usual first medication for type 2 diabetes if kidney function is adequate."
  tau: 0.35
```

The output is scored against `reference` by a similarity backend and passes when the score is at
least `tau`. The default backend is `trigram`; others can be registered by name in
`SIMILARITY_BACKENDS`, and none are shipped, so nothing here downloads a model.

**Scoring.** The similarity itself. An empty reference is a failed result with no score and a
detail saying so, rather than a number: `TrigramCosine` would score every non-empty output 0.0
against an empty reference, which makes the assertion unsatisfiable while still looking like a
check.

**`TrigramCosine`.** Lower-case, collapse every run of whitespace to one space, count character
trigrams over the whole string without padding, take the cosine of the two count vectors. Pure
Python, no data files, identical on every platform and in every process. Three edge cases are
decided rather than left to arithmetic: strings that normalise to fewer than three characters have
no trigrams at all and score 1.0 when they are equal and 0.0 otherwise; identical strings score
exactly 1.0; strings sharing no trigram score 0.0.

## `judge`

```yaml
- {type: judge, rubric: faithfulness, threshold: 1.0}
```

A rubric judge grades the output and the assertion passes when the verdict is `pass` and the score
is at least `threshold`.

**The rubric.** A markdown file holding the grading instructions. `rubric` is either an absolute
path or a name, and a name resolves to `<dir>/<name>.md` in the first directory that has it,
searched in this order: `<rootdir>/rubrics`, then `<the requesting test module's
directory>/rubrics`. That is why `examples/demo_suite/` can keep its own rubric beside its tests
while pytest's rootdir is the repository above it. A rubric that resolves nowhere is a failed
result naming every directory searched, not an exception.

**The prompt.** One module constant, `probatio.judge.JUDGE_PROMPT_TEMPLATE`, wraps the rubric, the
case's input, the output under test, and the instruction to answer with strict JSON:

```json
{"verdict": "pass", "score": 1.0, "rationale": "<one sentence>"}
```

Parsing is strict where it matters: one wrapping code fence is stripped, then `json.loads`, then
pydantic. `verdict` must be `pass` or `fail` and `score` must be a number in [0, 1] — prose, a
missing `score`, `"PASS"`, or a score of 1.4 is a failed result whose detail begins `judge output
was not valid JSON`, never an exception, so one badly behaved judge does not end the run. Two
deviations are tolerated instead: `rationale` may be missing, and keys the verdict does not
declare are dropped. Only `verdict` and `score` decide the assertion, and failing a judge for
volunteering a `confidence` field would count formatting against it as if it had judged badly. The
template's hash is part of every judge cassette key, so a tape recorded under one wording is
reported stale rather than replayed under another.

**No provider, no verdict.** With no judge provider configured the assertion is
`unenforceable`, has no score, and is never a pass. A suite whose judge assertions are silently
green because nothing graded them is the failure mode this prevents.

### Validating a judge

A judge you have not measured is an opinion with a JSON schema. `probatio validate-judge` measures
it against human labels and writes the record that every graded judge assertion reads back:

```bash
# You already have a judge column and a human column in a labelled sample.
probatio validate-judge \
  --rubric faithfulness \
  --labels labels.csv --human-column human_label --judge-column judge_label \
  --min-kappa 0.6

# Or produce the judge column now, by grading each row's answer against its context.
probatio validate-judge \
  --rubric faithfulness \
  --labels labels.csv --human-column human_label \
  --run-judge --provider claude-cli --model <model> \
  --answer-column answer --question-column question --context-column sources_text
```

It prints observed agreement and Cohen's kappa, writes
`.probatio/judges/<rubric>.validation.json`, and exits 1 when kappa is below `--min-kappa`, so a
CI step can refuse to ship an unmeasured judge. The record carries `n`, `agreement`, `kappa`, the
labels file and its hash, the method, the judge model, and the hash of the rubric text it applies
to. Commit it: that is what lets CI know which judges are validated.

Human labels and judge verdicts usually live in different label spaces — the Consilium samples are
labelled `supported`/`unsupported` while the judge answers `pass`/`fail` — so judge labels are
translated through `--label-map`, which defaults to `pass=supported,fail=unsupported`. Labels the
map does not mention are compared verbatim. Under `--run-judge` the judge is built one case per
row from the columns you name and nothing else, so it never sees the label columns it is being
measured against.

**The unvalidated-judge warning.** A judge assertion whose rubric has no record, or whose record
was written for different rubric text, is marked `unenforceable` and its detail says so:

```
judge 'faithfulness' returned pass with score 1.00 (threshold 1.00): every claim is in the
documents; judge 'faithfulness' has not been validated against human labels (run: probatio
validate-judge --rubric faithfulness --labels LABELS.csv --human-column human_label
--judge-column judge_label)
```

The verdict still counts toward the case's pass or fail — unlike an unenforceable cost ceiling,
which cannot fail a build — and the run's summary counts how many verdicts came from judges nobody
has measured. Editing a rubric after validating it puts the warning back, because the record pins
the rubric's content hash: an edited rubric is a different judge.

## Similarity is for paraphrase-stable content; a judge is for claims

This is a position, not a menu. Reach for `similarity` when the thing you are protecting is
*wording that should stay roughly the same* — a canned safety line, a fixed disclaimer, a summary
whose shape you have already accepted, a template rendering. Reach for a `judge` when the thing
you are protecting is *whether a claim is true, grounded or complete* — faithfulness to retrieved
documents, whether an answer actually answers the question, whether advice is safe.

Substituting one for the other fails in both directions, and the table below shows the first
direction happening. A trigram cosine has no idea what a sentence asserts. Pair 4 is a statement
that **contradicts** the reference — it is about when metformin must *not* be started — and it
still scores 0.223, because it shares a drug name, a grammatical frame and most function words.
Set `tau: 0.20` on that case, which is not an absurd floor, and a directly contradictory answer
passes. Nothing you can do to `tau` fixes this, because the ordering is wrong, not the threshold:
pair 3 says the same true thing in different words and scores 0.453, while a false answer in
similar words scores 0.223, and the gap between them is not large enough to be a safety margin.

The other direction is a judge used where similarity belongs: an LLM call, priced and latent and
nondeterministic, and a rubric to maintain, to check something a substring or a cosine settles for
free and identically on every run.

### Trigram scores for five pairs

Every score below is recomputed from the shipped `TrigramCosine` backend by
`tests/test_docs_assertions.py`, which parses this table and fails if a number here and the code
disagree at three decimals. The reference in every row is the same sentence.

| Output | Reference | Trigram score |
|---|---|---|
| `Metformin is the usual initial medication for type 2 diabetes.` | `Metformin is the usual initial medication for type 2 diabetes.` | 1.000 |
| `The usual initial medication for type 2 diabetes is metformin.` | `Metformin is the usual initial medication for type 2 diabetes.` | 0.923 |
| `For newly diagnosed type 2 diabetes, metformin is normally started first.` | `Metformin is the usual initial medication for type 2 diabetes.` | 0.453 |
| `Metformin should not be started when kidney function is severely reduced.` | `Metformin is the usual initial medication for type 2 diabetes.` | 0.223 |
| `I don't know.` | `Metformin is the usual initial medication for type 2 diabetes.` | 0.000 |

Read down the column to pick a `tau`:

- **1.000** — identical after normalisation. Only casing and whitespace differ.
- **0.923** — a clause moved. This is what a stable paraphrase of a fixed sentence looks like, and
  a `tau` above about 0.85 is testing for a template, not for meaning.
- **0.453** — the same claim in genuinely different words. A case whose wording is free to move
  needs its floor somewhere below this line. `examples/demo_suite/cases/` commits `tau: 0.30` and
  `tau: 0.35`; those are the two values this repository has actually run.
- **0.223** — same topic, contradictory claim. Above this line is where similarity stops
  discriminating and a judge starts being the right tool.
- **0.000** — a refusal. Short outputs share almost nothing with a long reference, which is what
  makes similarity a serviceable refusal detector and a poor correctness one.

### What real answers score

The table above is five hand-written pairs. `examples/consilium/` is thirty real answers to fifteen
real questions, each scored against that question's hand-written reference answer, and it is the
only measured basis this repository has for choosing a `tau`. From
`examples/consilium/results/replay-unpriced.json`:

| answers | n | lowest | highest | median |
|---|---|---|---|---|
| `test_baseline` — `baseline_llm`, one grounded call | 15 | 0.443 | 0.649 | 0.538 |
| `test_full` — the multi-agent pipeline | 15 | 0.398 | 0.705 | 0.574 |

Every one of the thirty is above the `tau: 0.30` those cases commit — the worst of them, 0.398,
sits 0.098 above the floor — and every one is below the 0.923 that a moved clause scores in the
table above. The shape of the advice is therefore: **a floor for free-form prose belongs just
under the band its own answers occupy, not near the middle of [0, 1]**. That is what makes it fire
when an answer stops being about the question rather than when it is reworded.

No single recommended number follows from this, for two reasons. Thirty answers to fifteen
questions from one corpus, in one domain, at one answer length, is a band and not a distribution;
and the band moves with what the reference is — a fixed line compared against itself lives up
where 0.923 is, and a floor read off this table would be uselessly low for it. Measure your own
suite once: run it, read the similarity scores out of `--probatio-results`, and put the floor
under them, rather than borrowing a number from this one.
