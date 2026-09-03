# Demo suite

The executable design specification for Probatio: ten YAML cases, a thirty-line fake
retrieval-grounded QA app, and one test module that uses every decorator. It is written from the
viewpoint of a developer testing their own app and it runs entirely offline against a scripted
provider. Nothing here is edited after the commit that introduced it (gate condition 5 in
`CLAUDE.md`); the one sanctioned exception is the import guard at the top of `conftest.py`, which
Phase 9 deletes.

## Layout

| path | what it is |
|---|---|
| `app.py` | `answer(case, provider)`: builds one prompt from `input.question` and `input.documents` |
| `cases/*.yaml` | one `LLMCase` per file, loaded in path order |
| `variants/<case_id>.yaml` | frozen paraphrases for the two `paraphrase` cases, hand-written |
| `rubrics/faithfulness.md` | the rubric the `judge` assertions name |
| `conftest.py` | a `FakeProvider` keyed by one keyword per case, a fake judge, a `ScriptedProvider` |
| `test_demo.py` | four test functions; the case's `tags` decide which one it runs through |

## How the fake app behaves, and why

The scripted provider matches one keyword per question, case-sensitively. That is a stand-in for
a brittle application, and it makes the relations legible:

- `order_invariant` permutes `input.documents`; the keyword is in the question, so the verdict
  does not move. A one-document case is reported as not applicable, not as zero violations.
- `distractor_robust` inserts an unrelated document at the start and at the end; same outcome.
- `format_jitter` produces three variants of the question. Doubled whitespace and a fenced code
  block leave the keyword intact. Upper-casing the first sentence destroys the keyword when it is
  in that sentence, so those cases flip; the two cases whose keyword sits in a second sentence
  (`t2d-metformin`, `red-flag-chest-pain`) do not.
- `paraphrase_invariant` reads the frozen variants. One paraphrase of `htn-definition` avoids the
  keyword on purpose, so that relation also shows a violation.
- `anxiety-expected-fail` is scripted to refuse an answerable question; every assertion on it
  fails, and `test_demo.py` wraps it in `pytest.raises` so the suite stays green while the report
  shows the failing case.
- `flu-antivirals-flaky` runs against a `ScriptedProvider` that fails the first of five calls.
  `@flaky_tolerant(p=0.8, n=5)` accepts it; without the marker it would fail.
- `copd-spirometry` has a bare-string input and no documents, so every relation that names a
  field under `input.*` reports not applicable.

The judge fixture is also a fake: it fails only the keyword-miss fallback output. No judge in this
suite has a validation record, so every judge verdict is reported as unvalidated, which is the
warning the tool is supposed to give.

## Commands

From the repository root, with the virtualenv active:

```bash
pytest examples/demo_suite                                  # offline; scripted fake provider
pytest examples/demo_suite --runs 5                         # adds pass rates, Wilson intervals, stability score
pytest examples/demo_suite --update-baseline                # re-record .probatio/baseline/test_demo/*.json
pytest examples/demo_suite --probatio-results build/demo.json --probatio-junit build/demo.xml \
       --probatio-report build/demo.md
```

Baselines are written under the pytest rootdir (`.probatio/baseline/test_demo/`), never inside
this directory, so recording them does not touch the frozen files.

To run the same cases against a live model on a Claude plan, the `provider` fixture in
`conftest.py` steps aside whenever `--probatio-provider` is not `fake`:

```bash
pytest examples/demo_suite --probatio-provider claude-cli --probatio-model <model> \
       --cassette=record --cassette-dir build/cassettes
pytest examples/demo_suite --probatio-provider claude-cli --cassette=replay --cassette-dir build/cassettes
probatio freeze-variants --cases examples/demo_suite/cases --field input.question --k 3 \
       --provider claude-cli --model <model> --out build/variants
```

Tapes and generated variants go under `build/` (git-ignored), not into this directory. The
committed `variants/` files are the hand-written ones; the frozen suite reads only those.
