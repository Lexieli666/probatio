# DECISIONS.md — judgement calls made without asking, numbered and dated

## 1. Distribution name `probatio-llm`, import name `probatio`

- **Date:** 2026-09-03 (Phase 0)
- **Q:** What distribution name goes on PyPI, given that spec §2 prefers `probatio` if it is free?
- **A:** `probatio-llm`. The import name stays `probatio`, so every example, docstring and
  `import probatio` line in the spec is unaffected.
- **Why:** The name `probatio` on PyPI is taken by an unrelated placeholder release,
  probatio 0.0.1. That placeholder also installs a top-level `probatio/` import package, so the
  two distributions collide on disk and must never be installed into the same environment. The
  README's install section states this. Decided by the user in the Phase 0 prompt; recorded here
  because spec §2 leaves the name conditional.

## 2. `D` docstring rules apply to `src/` only

- **Date:** 2026-09-03 (Phase 0)
- **Q:** Spec §2 asks for ruff rules `E, F, I, B, UP, N, D` with "D for public API". The gate runs
  `ruff check src tests examples`. Where does `D` apply?
- **A:** `D` is selected globally and ignored per-file for `tests/**` and `examples/**`.
  `E, F, I, B, UP, N` apply everywhere.
- **Why:** "D for public API" means the shipped package. Requiring a docstring on every pytest test
  function and on every line of the demo suite would add noise to the two directories that are read
  as prose examples, and `examples/demo_suite/` is frozen after Phase 1, so a later docstring rule
  change there would be unfixable. Rejected alternative: selecting `D` only under a
  `src/**`-scoped section, which ruff expresses less directly than a per-file ignore.

## 3. A tracked `examples/README.md` so the gate's paths resolve in Phase 0

- **Date:** 2026-09-03 (Phase 0)
- **Q:** The gate command is `ruff check src tests examples`, but `examples/` has no content until
  Phase 1, and ruff exits non-zero with `E902 No such file or directory` on a missing path.
- **A:** Commit a one-paragraph `examples/README.md` that says what will live there. Git cannot
  track an empty directory, and the file is not Python, so it changes nothing that ruff, pytest or
  coverage measure.
- **Why:** Keeps the five gate commands in `CLAUDE.md` runnable verbatim from Phase 0 onward,
  instead of a Phase-0-only variant that a later session might copy by mistake. Rejected
  alternative: dropping `examples` from the Phase 0 CI invocation and adding it in Phase 1, which
  makes the committed CI workflow disagree with the documented gate.
  `pytest`'s `testpaths = ["tests", "examples/demo_suite"]` needs no such placeholder: pytest
  globs testpaths and tolerates an entry that matches nothing.

## 4. Local interpreter is Python 3.13; the floor and the CI matrix are unchanged

- **Date:** 2026-09-03 (Phase 0)
- **Q:** The repository's `.venv` is Python 3.13.5, but spec §2 pins CI to 3.11 and 3.12.
- **A:** Leave `requires-python = ">=3.11"` and the CI matrix at 3.11 / 3.12; develop locally on
  3.13. `mypy` is configured with `python_version = "3.11"` so type checking targets the floor
  rather than the local interpreter.
- **Why:** 3.13 satisfies the declared floor, so no dependency or syntax decision changes; the
  matrix is what proves the floor. Changing the Python floor would need to be asked, and nothing
  here requires it. Rejected alternative: rebuilding the virtualenv on 3.11, which would make the
  local run identical to the older CI leg but hide 3.13 incompatibilities until release.

## 5. `tags` route a case to a test function

- **Date:** 2026-09-03 (Phase 1)
- **Q:** The demo suite has one set of cases but four test functions with different decorators.
  How does a case reach the function whose relations and fixtures fit it?
- **A:** Through `LLMCase.tags`. `test_demo.py` parametrizes each function over a filtered list:
  `tagged("paraphrase")` for the cases with frozen variants, `tagged("expected-fail")`,
  `tagged("flaky")`, and `REGULAR` for everything that carries neither of the last two tags.
- **Why:** `tags` is already in the case model (spec §3.2) and is data, so the routing lives with
  the case rather than in a hand-maintained list of ids inside the test module. It also means a
  new case joins the right test function by adding one line of YAML. Rejected alternative: a
  separate marker or a per-function list of case ids in `test_demo.py`, which duplicates knowledge
  that the case file already carries and goes stale silently when a case is renamed.

## 6. The expected-fail case is wrapped in `pytest.raises`, not `xfail`

- **Date:** 2026-09-03 (Phase 1)
- **Q:** Spec §4 asks for a case designed to fail an assertion on purpose, so the README can show a
  failure report. The obvious pytest idiom is `@pytest.mark.xfail`.
- **A:** `test_expected_fail` wraps `probatio.check` in `with pytest.raises(AssertionError):`.
- **Why:** Gate condition 1 in `CLAUDE.md` requires zero xfails, so an `xfail` marker would fail
  the gate for every phase from 9 onward. `pytest.raises` asserts the same thing more strictly: the
  check must raise, and a run where the case unexpectedly passes is a failure rather than an
  `xpass`. The case still runs, so the collector still records it and the report still shows every
  failed assertion, which is the point of having it. Rejected alternative: `xfail(strict=True)`,
  which is equivalent in strictness but is counted as an xfail by the gate.

## 7. `distractor_robust` takes a `field` argument

- **Date:** 2026-09-03 (Phase 1)
- **Q:** The relation table in spec §3.9 writes `@distractor_robust(distractors=[...],
  positions=("start","end"))` with no `field`, but its own semantics column distinguishes "for a
  string input" from "for a list field", which requires naming the list.
- **A:** The signature is `distractor_robust(*, field=None, distractors, positions=("start",
  "end"))`, and the demo calls it with `field="input.documents"`. `field=None` keeps the table's
  behaviour of prepending and appending to a string input.
- **Why:** Without `field` the relation cannot express "insert an unrelated document into the
  retrieved set", which is the interesting form for a retrieval-grounded app and the one the demo
  needs; the table omits the argument rather than forbidding it. Every other relation in the table
  already names its field the same way, so this makes the four decorators consistent. Rejected
  alternative: inferring the list field, for example by taking the only list under `input`, which
  is silent guesswork that breaks the moment a case has two lists.

## 8. A relation whose field does not resolve is "not applicable"

- **Date:** 2026-09-03 (Phase 1)
- **Q:** `copd-spirometry` has a bare-string input, so `input.documents` and `input.question` do
  not resolve on it, yet `test_case` applies three field-naming relations to every regular case.
  Is that an error, or zero violations?
- **A:** Neither. `Relation.applicable(case)` is `False` when the field does not resolve (and, for
  `order_invariant`, when the list it names has fewer than two elements), and the case's
  `RelationResult.violation_rate` is `None`, counted under "not applicable" in the report.
- **Why:** Spec §3.9 already requires exactly this reporting for `order_invariant` on a
  one-element list, and the same reasoning applies to a missing field: a relation that generated no
  variants has observed nothing, and printing `0.00` for it would claim a robustness result the run
  never measured. Raising instead would force every suite to shard its cases by input shape.
  Rejected alternative: treating an unresolvable field as a configuration error, which makes mixed
  suites like this one impossible to write without splitting the parametrization.

## 9. The demo's `provider` and `judge_provider` fixtures step aside unless the provider is `fake`

- **Date:** 2026-09-03 (Phase 1)
- **Q:** The demo suite's `conftest.py` overrides the plugin's `provider` and `judge_provider`
  fixtures with scripted fakes. How does the same suite then record real tapes, which spec §4's
  README commands and Phase 12 both require?
- **A:** Each override takes the plugin's fixture as an argument and returns it unchanged whenever
  `--probatio-provider` is not `fake`; only in the default `fake` case does it substitute the
  scripted `FakeProvider`.
- **Why:** It keeps one suite for both purposes, so the offline default needs no flags and
  `pytest examples/demo_suite --probatio-provider claude-cli --cassette=record` records tapes for
  the same cases without editing a frozen directory. Overriding on the *provider* flag rather than
  on `--probatio-judge-provider` for the judge is deliberate: the judge defaults to following the
  provider (spec §3.12), so one switch keeps the fake app and the fake judge from being mixed with
  live counterparts. Rejected alternative: an environment variable or a separate `conftest.py`
  under a second directory, both of which duplicate the case list or add a knob the plugin does not
  own.

## 10. Paths inside the demo suite are written relative to the test module

- **Date:** 2026-09-03 (Phase 1)
- **Q:** Spec §3.9 shows `variants_dir="variants"` and paths in `.probatio/` are documented as
  relative to pytest's `rootdir` (spec §0). The demo suite is not the rootdir: it is
  `examples/demo_suite` under it, and a user may run `pytest` from anywhere.
- **A:** The demo passes explicit paths built from `HERE = Path(__file__).parent`:
  `load_cases(HERE / "cases")` and `paraphrase_invariant(..., variants_dir=HERE / "variants")`.
  So `variants_dir` and the loader accept `str | Path`, and a relative value stays
  rootdir-relative for users whose suite *is* at the rootdir.
- **Why:** The demo lives inside the Probatio repository, whose rootdir is the repository, so a
  relative `"variants"` would resolve to a directory that does not exist and the suite would fail
  depending on the working directory it was invoked from. Writing the paths explicitly also makes
  the example honest about where its inputs live, which is what a reader copying it needs.
  Rejected alternative: resolving relative paths against the requesting test module's directory
  instead of the rootdir, which contradicts spec §0 and makes the same string mean two things in
  two suites.
