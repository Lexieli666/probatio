# Consilium live suite (the one suite recorded against a real model)

Every other suite in this repository answers from a scripted fake or from a tape built out of
somebody else's published run. This one was recorded by calling a model: fifteen cases, four
metamorphic relations and a rubric judge, run once through `ClaudeCLIProvider` on a Claude plan
with no API key anywhere, and committed as tapes so that every number the case study quotes can be
reproduced offline at no cost.

```bash
pytest examples/consilium/live/test_live.py -q --cassette-dir examples/consilium/live/cassettes \
       --baseline-dir .probatio/baseline-live --probatio-model claude-opus-5
```

That command calls no model, and neither does anything in CI. The recording commands below are the
only ones that do, and a human runs them deliberately.

Every command in this directory names its test module rather than the directory, because there
are two suites here: `test_live.py`, Phase 12's, and `test_live_variance.py`, Phase 15's, and they
keep their tapes and baselines in different places. `pytest examples/consilium/live` would collect
both and one `--cassette-dir` cannot serve them (DECISIONS 103, which is DECISIONS 87 one level
down). Every Phase 12 command below was re-run in this form and reproduces its committed output
byte for byte.

`--probatio-model` is needed on a replay too, and naming the model the tapes were recorded against
is the whole point of it: these cases name no model in their `params`, so the cassette key takes
the one the provider was configured with, and replaying under a different name is a
`StaleCassetteError` rather than a wrong answer (DECISIONS 91).

## This is not Consilium's pipeline

`app_live.py` is a **single-call grounded question-answering app**: it renders the documents the
case already carries into one prompt and makes one provider call. Consilium-Health routes a
question through a planner and one or more agents, retrieves from a vector store, and repairs the
draft through a safety step. None of that is modelled here, and the documents are handed to the
app rather than retrieved, so retrieval is not modelled either.

The suite exists so that the metamorphic relations and the judge have a real model to fire
against. Nothing measured here is a measurement of Consilium-Health. The suite next door,
`examples/consilium/`, is the one that replays Consilium's own recorded answers; that is where
Route A of `docs/CASE_STUDY.md` comes from.

## Provenance

| artefact | origin |
|---|---|
| `cases/*.yaml` | the same fifteen ids as `../CASES.txt`, emitted by `../convert_traces.py --emit-live-cases` from Consilium's `golden.jsonl` at commit `109a744`. The question, `reference_answer`, `category`, `red_flag`, `expected_route` and `relevant_doc_ids` are the golden item's; `input.documents` are the corpus notes those `relevant_doc_ids` name, copied verbatim from Consilium's `data/corpus/` |
| the escalation phrase list in each red-flag case | `ESCALATION_PHRASES` from Consilium's `safety/escalation.py`, the same list the offline suite uses |
| `rubrics/faithfulness.md` | Consilium's `judges/faithfulness_v2.md` at commit `109a744`, verbatim from `## System` up to its `## Output`, with a provenance header and a replacement `## Output` mapping v2's per-claim roll-up onto the one JSON object Probatio's judge template asks for |
| `variants/*.yaml` | `probatio freeze-variants` against `claude-opus-5`, then reviewed by a human who deleted the rewordings that changed the question; each file's header records what was deleted and why |
| `cassettes/test_live/` | recorded against `claude-opus-5` |
| `cassettes-n10/test_live_variance/` | Phase 15 experiment A: the same fifteen cases recorded ten times against `claude-opus-5` |
| `cassettes-judge-x10/judge_repeatability/` | Phase 15 experiment B: ten gradings of each committed opus answer, one interaction a case because the input never changes |
| `cassettes-haiku/test_live/` | recorded against `claude-haiku-4-5-20251001`, Route B's second model |
| `results/preflight.json` | one live payload from the Phase 12 preflight, kept so the parser can be checked against a real reply |
| `results/live-baseline.*`, `results/live-changed.*` | the two offline replays the case study quotes |
| `results/live-n10.*` | the offline replay of experiment A, which `docs/EVALUATION.md` §8 quotes |
| `results/judge-repeatability.json` | experiment B, rebuilt from its tapes by `judge_repeatability.py --replay` |

`tests/fixtures/consilium/corpus/` holds copies of the fourteen notes these cases name and
`tests/fixtures/consilium/faithfulness_v2.md` a copy of the rubric source, so
`tests/test_consilium_live_suite.py` can re-emit both and compare byte for byte without reading
anything outside this repository.

## Every command, in the order Phase 12 ran them

The model is `claude-opus-5` throughout, except where Route B names the second one. The judge
follows the provider unless `--probatio-judge-provider` says otherwise, so it is the same model.

### 1. Freeze the paraphrases (live)

```bash
probatio freeze-variants --cases examples/consilium/live/cases --field input.question --k 3 \
        --provider claude-cli --model claude-opus-5 --out examples/consilium/live/variants
```

Then read every file and delete any paraphrase that changed the question — one that adds or
removes a symptom, changes who the patient is, changes a number or a duration, or asks something
else — noting the deletion in the file's header. A file left with two paraphrases is measured over
two (DECISIONS 52); only an empty one is an error.

### 2. Record the suite (live)

```bash
pytest examples/consilium/live/test_live.py -q --probatio-provider claude-cli \
       --probatio-model claude-opus-5 --cassette=record \
       --cassette-dir examples/consilium/live/cassettes \
       --baseline-dir .probatio/baseline-live
```

Every relation variant and every judge call is its own cassette key, so this records far more
interactions than there are cases.

### 3. Record the baselines (offline)

```bash
pytest examples/consilium/live/test_live.py -q --cassette-dir examples/consilium/live/cassettes \
       --baseline-dir .probatio/baseline-live --probatio-model claude-opus-5 --update-baseline
```

### 4. Validate the judge against Consilium's blind human labels (live)

Sample 2 is the record the suite reads, so it is written to `.probatio/judges/`; sample 1 is kept
beside the suite so both survive.

```bash
probatio validate-judge --run-judge --rubric examples/consilium/live/rubrics/faithfulness.md \
        --provider claude-cli --model claude-opus-5 \
        --labels <consilium>/judge-validation/sample-2/judge-sample-2-labeled.csv \
        --answer-column answer --context-column sources_text --human-column human_label \
        --out .probatio/judges/

probatio validate-judge --run-judge --rubric examples/consilium/live/rubrics/faithfulness.md \
        --provider claude-cli --model claude-opus-5 \
        --labels <consilium>/judge-validation/sample-1/judge-sample-labeled.csv \
        --answer-column answer --context-column sources_text --human-column human_label \
        --out examples/consilium/live/results/judges-sample-1/
```

### 5. The replay the case study quotes (offline, no model)

```bash
pytest examples/consilium/live/test_live.py -q --cassette-dir examples/consilium/live/cassettes \
       --baseline-dir .probatio/baseline-live --probatio-model claude-opus-5 \
       --probatio-results examples/consilium/live/results/live-baseline.json \
       --probatio-report examples/consilium/live/results/live-baseline.md
```

### 6. Route B: change the model and replay against the same baselines

Record against the second model into its own cassette directory:

```bash
pytest examples/consilium/live/test_live.py -q --probatio-provider claude-cli \
       --probatio-model claude-haiku-4-5-20251001 --probatio-timeout 600 --cassette=record \
       --cassette-dir examples/consilium/live/cassettes-haiku \
       --baseline-dir .probatio/baseline-live
```

`--probatio-timeout` is there because the shipped 120-second default could not finish this
recording on a throttled plan: a single call was taking 40 to 90 seconds and the occasional one
exceeded two minutes, which fails the case with `the Claude CLI did not answer within 120s`
(DECISIONS 95). It changes no cassette key, so a tape recorded with it is indistinguishable from
one recorded without.

Then replay those tapes against the **opus** baselines, so snapshot drift is what a model change
looks like in a report:

```bash
pytest examples/consilium/live/test_live.py -q \
       --cassette-dir examples/consilium/live/cassettes-haiku \
       --baseline-dir .probatio/baseline-live --probatio-model claude-haiku-4-5-20251001 \
       --probatio-results examples/consilium/live/results/live-changed.json \
       --probatio-report examples/consilium/live/results/live-changed.md
```

### Re-emitting the cases and the rubric

```bash
python examples/consilium/convert_traces.py \
       --golden examples/consilium/golden-subset.jsonl \
       --cases examples/consilium/CASES.txt \
       --escalation tests/fixtures/consilium/escalation_phrases.txt \
       --corpus tests/fixtures/consilium/corpus \
       --judge-rubric tests/fixtures/consilium/faithfulness_v2.md \
       --emit-live-cases
```

The committed files are the contract: this must reproduce them byte for byte, and
`tests/test_consilium_live_suite.py` fails if it does not.

## Phase 15: the variance study seed

Two experiments, both `claude-opus-5`, both recorded into their own tapes so that every statistic
replays offline afterwards.

### A. The same fifteen cases, answered ten times each (live, 300 calls)

`test_live_variance.py` carries no relation decorator and no `flaky_tolerant` marker: the study
measures the cases' own verdicts, and the four relations would attach ten variants to every run.

```bash
pytest examples/consilium/live/test_live_variance.py -q --probatio-provider claude-cli \
       --probatio-model claude-opus-5 --probatio-timeout 600 --runs 10 --cassette=record \
       --cassette-dir examples/consilium/live/cassettes-n10 \
       --baseline-dir .probatio/baseline-live-n10
```

Recording under `--runs 10` appends one sample per run (DECISIONS 44), so the system-under-test
call is one interaction with ten samples. The judge call is not: its prompt carries the answer it
is grading, so a run that produced a different answer is a different cassette key, and a case's
tape holds one interaction per distinct answer with one grading each.

Record the baselines from the tapes, offline, so that they belong to a single replay rather than
to whichever recording invocation happened to reach the case first:

```bash
pytest examples/consilium/live/test_live_variance.py -q --runs 10 \
       --cassette-dir examples/consilium/live/cassettes-n10 \
       --baseline-dir .probatio/baseline-live-n10 --probatio-model claude-opus-5 \
       --update-baseline
```

Then the replay that produced the committed results, which calls nothing:

```bash
pytest examples/consilium/live/test_live_variance.py -q --runs 10 \
       --cassette-dir examples/consilium/live/cassettes-n10 \
       --baseline-dir .probatio/baseline-live-n10 --probatio-model claude-opus-5 \
       --probatio-results examples/consilium/live/results/live-n10.json \
       --probatio-junit examples/consilium/live/results/live-n10.xml \
       --probatio-report examples/consilium/live/results/live-n10.md
```

### B. Ten gradings of one unchanging answer (live, 150 calls)

```bash
python examples/consilium/live/judge_repeatability.py --record --timeout 600
python examples/consilium/live/judge_repeatability.py --replay   # offline, rebuilds the file
```

The answer under the judge is the committed `claude-opus-5` completion in `cassettes/test_live/`,
found by cassette key rather than by position, so experiment B grades exactly what Phase 12
recorded. Identical input means one cassette key, so each tape holds one interaction with ten
samples — `tests/test_consilium_judge_repeatability.py` asserts that, and asserts `--replay`
reproduces the committed JSON byte for byte with the inner provider never called.
