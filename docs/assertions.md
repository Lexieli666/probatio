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
not happen. It is never counted as a pass.

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

A rubric judge grades the output and the assertion passes when the verdict is `pass` and the
score is at least `threshold`. See `docs/DESIGN.md` and the judge validation record written by
`probatio validate-judge`: a judge with no record on disk is reported as unvalidated, and a judge
with no provider configured is reported as **unenforceable**, never as a pass.

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
- **0.453** — the same claim in genuinely different words. **0.30 to 0.40 is the useful band**, and
  it is what the demo suite uses; a case whose wording is free to move needs a floor here.
- **0.223** — same topic, contradictory claim. Above this line is where similarity stops
  discriminating and a judge starts being the right tool.
- **0.000** — a refusal. Short outputs share almost nothing with a long reference, which is what
  makes similarity a serviceable refusal detector and a poor correctness one.
