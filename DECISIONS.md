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

## 11. What `stable_hash` accepts, and what it refuses

- **Date:** 2026-09-03 (Phase 2)
- **Q:** Spec §3.1 fixes canonical JSON, SHA-256 and a hex prefix, but not what happens to a value
  JSON has no form for: a set, a `Path`, `bytes`, a `NaN` cost, or a `length` outside the digest.
- **A:** Sets and frozensets are canonicalised element-wise and then ordered by each element's own
  canonical JSON; `PurePath` becomes its POSIX string; `bytes` are decoded as strict UTF-8;
  mapping keys are coerced with `str()` and sorted; `NaN` and the infinities raise `ValueError`
  (`allow_nan=False`); a `length` outside `1..64` raises `ValueError`. Anything else raises
  `TypeError` naming the type. `canonical_json` is public so the serialisation can be tested and
  quoted directly.
- **Why:** Every one of these is either deterministic or an error, which is the property the whole
  file exists to provide; a silent fallback would make a baseline key depend on iteration order or
  on a float that is not equal to itself. `NaN` in particular would serialise to the non-standard
  token `NaN`, which is stable in Python and unreadable to anything else, and it can only reach a
  hash through an unpriced cost or a bad statistic, both of which should be loud. Rejected
  alternative: `json.dumps(..., default=str)`, which never fails and therefore hashes
  `<object at 0x10a3f2b90>` into a cassette key that changes on the next run.

## 12. YAML keys that are Python builtins are declared under aliases

- **Date:** 2026-09-03 (Phase 2)
- **Q:** The assertion vocabulary fixed by `examples/demo_suite/cases/` uses `any:`, `all:` and
  `schema:`. The first two are builtins and the third shadows a pydantic `BaseModel` attribute.
- **A:** Fields are `any_`, `all_` and `json_schema`, each with the YAML spelling as its pydantic
  `alias`, and every declaration model sets `populate_by_name=True` so both spellings validate.
- **Why:** The YAML surface is frozen by the demo suite, so it is the field names that have to
  move. Aliases keep the file format exactly as written while the Python attribute stays a legal,
  non-shadowing identifier, and `populate_by_name` makes `model_dump()` output re-validate
  unchanged, which is what `with_field` relies on to build a variant. Rejected alternative:
  keeping the field named `schema` and suppressing pydantic's shadowed-attribute warning, which
  trades a one-word rename for a warning filter that hides future collisions too.

## 13. `get_field` distinguishes a wrong path from a missing value

- **Date:** 2026-09-03 (Phase 2)
- **Q:** DECISIONS 8 says a relation whose field does not resolve is "not applicable". A relation
  therefore calls `get_field(case, field, default=None)`. But then a typo in the relation's
  `field=` argument — `inpit.documents` — would silently report every case as not applicable.
- **A:** Three behaviours, not two. A path whose first segment is not a field of `LLMCase` always
  raises `ProbatioConfigError`, even when a default was passed. A path whose later segments do not
  resolve returns the default when one was given and raises when none was. A malformed path (empty,
  or with an empty segment) always raises. `with_field` additionally refuses to create a key that
  does not already exist.
- **Why:** The first segment is a static fact about the case model and cannot vary between cases,
  so a bad one is a configuration error, whereas a missing key under `input` is ordinary data
  variation across a mixed suite — which is exactly what `copd-spirometry` is in the demo. Letting
  `with_field` invent keys would let a mistyped relation report a robustness result for an input
  the application never receives. Rejected alternative: one uniform "missing is the default" rule,
  which is simpler by a few lines and turns a typo into a suite that quietly measures nothing.

## 14. The Claude CLI flags: what is passed, and what is deliberately not

- **Date:** 2026-09-03 (Phase 2)
- **Q:** Spec §3.3 says the exact flag names are to be read from `claude --help` on the installed
  version at Phase 2 and recorded here. Which flags implement "non-interactive, JSON, one turn,
  no tools, no project context, model and system prompt passed through"?
- **A:** The command is
  `claude -p <prompt> --output-format json --no-session-persistence [--model M]
  [--system-prompt S] --tools ""`, run with an empty temporary directory as its working directory
  and a 120 s timeout. Every flag name, the executable and the timeout are constructor arguments
  with those defaults, so a rename in the CLI is a one-line override rather than a release.
  Four sub-decisions:
  - **`--tools ""` is how one turn is obtained.** This version has no `--max-turns`. The help text
    says `""` disables all built-in tools, and with no tools there is nothing for the model to do
    between turns, so the run is a single turn. `--tools` is variadic, so it is placed last in the
    argument vector: anything after its value would be read as another tool name.
  - **`--bare` is not used.** It does skip `CLAUDE.md` discovery, which is what spec §3.3 wants,
    but it also makes authentication "strictly `ANTHROPIC_API_KEY` or `apiKeyHelper`", and this
    adapter exists precisely so that a developer on a Claude plan can record tapes *without* an
    API key. "No project context" is obtained the way the spec's own parenthesis says: by running
    in an empty temporary directory. The docstring is explicit that user-level configuration
    outside that directory still applies.
  - **The model is not guessed from the payload.** The captured payload's `modelUsage` lists two
    models, because the CLI bills side work such as topic detection to a small model alongside the
    one that answered. `Completion.model` is the model that was asked for; failing that, the single
    key of `modelUsage` when there is exactly one; failing that, the literal `claude-cli`.
    Rejected alternative: taking the `modelUsage` entry with the most output tokens, which is a
    guess that would be written into every tape and every baseline key.
  - **Unhonourable params are recorded, not dropped.** This version exposes no sampling flags, so
    a case's `temperature` cannot be passed. The remaining params are listed under
    `raw["probatio_ignored_params"]`, and they still take part in the cassette key, so a tape
    records what the case asked for even though the CLI could not deliver it. Raising instead would
    make `pytest examples/demo_suite --probatio-provider claude-cli` fail on every case, since
    every demo case sets `temperature: 0`.
  A payload that parses but reports `is_error` or a `subtype` other than `success` raises
  `ProbatioConfigError` naming the subtype, the `api_error_status` and stderr, on the same footing
  as a non-zero exit.
- **Why:** Recorded because these are choices about somebody else's program, made from one
  version's `--help`, and the next version may move them. `tests/fixtures/claude_cli_payload.json`
  is a verbatim copy of one real payload from that version, and the parser is written against it.

## 15. `AnthropicProvider` imports the SDK at module import, and forwards params verbatim

- **Date:** 2026-09-03 (Phase 2)
- **Q:** Spec §3.3 says the adapter "imports `anthropic` lazily inside `__init__`", and its
  acceptance criterion says that *importing* `probatio.providers.anthropic` without the package
  raises `ProbatioConfigError` naming the extra. Those cannot both be literally true.
- **A:** The acceptance criterion wins: the module calls `importlib.import_module("anthropic")`
  once at import time and turns any `ImportError` into `ProbatioConfigError` with
  `fix="pip install 'probatio-llm[anthropic]'"`. Laziness is preserved where it matters —
  `probatio/__init__.py` and `probatio/providers/__init__.py` do not import this module, so
  `import probatio` never needs the extra, and a test asserts that. The import is dynamic rather
  than a plain `import anthropic` statement so that `mypy --strict` needs no stub for a package
  that is not a dependency, and so that a stub module in `sys.modules` is enough to test the whole
  mapping offline. Params other than `model` are forwarded to `messages.create` unchanged rather
  than filtered against the list in spec §3.3.
- **Why:** One failure point with one actionable message beats a `ModuleNotFoundError` raised from
  the first call, halfway through a test session. Forwarding params verbatim means the SDK's own
  parameter set is the contract, so `top_k` or a new sampling parameter works without a Probatio
  release; the CLI adapter cannot do the same because a flag list cannot carry unknown keys, which
  is why the two adapters differ here (entry 14). Rejected alternative: importing inside
  `__init__` as the spec's prose says, which leaves the acceptance criterion untestable and moves
  the missing-extra error to the middle of a run.

`PriceTable` is not a constructor argument yet: it is specified in §3.7 and built in Phase 6, and
inventing its shape here would fix an interface the phase that owns it has to match. Until then
this adapter's `cost_usd` is always `None`, which spec §3.7 already handles — a cost ceiling over
unpriced calls is reported unenforceable, not passed.

## 16. The demo suite's import guard stops working at Phase 2, so the exclusion is repeated outside it

- **Date:** 2026-09-03 (Phase 2)
- **Q:** `examples/demo_suite/conftest.py` is frozen and guards collection with
  `try: from probatio import FakeProvider / except ImportError: collect_ignore = ["test_demo.py"]`.
  Phase 2 is required to export `FakeProvider` (spec §3.3, §6, and the demo's own fixtures import
  it). The guard therefore stops firing, `test_demo.py` is collected, and it fails to import on
  the relation decorators that arrive in Phase 8. `pytest -q` gets a collection error, which fails
  gate condition 1, and the frozen file cannot be edited to strengthen its probe.
- **A:** Repeat the exclusion in a file that is not frozen: a repository-level `conftest.py` with
  `collect_ignore = ["examples/demo_suite/test_demo.py"]`, deleted in Phase 9 together with the
  guard in the frozen file. `tests/test_demo_spec.py` gains a test asserting that this exclusion
  exists exactly while some name the demo imports is missing, so Phase 9 cannot forget to remove
  it, and its collection check now asserts the transitional state precisely: collection fails on
  the first not-yet-exported name and on nothing else. `examples/demo_suite/` is untouched;
  `pytest examples/demo_suite` still reports 0 items and 0 errors, as the Phase 1 run-log line
  says.
- **Why:** The guard's probe was a proxy for "the public API exists", and Phase 2 makes the proxy
  wrong for seven phases; the mechanism is the spec's own (`collect_ignore` on an unavailable
  API), just applied from the one directory that is allowed to change. Rejected alternatives:
  narrowing `testpaths` to `["tests"]`, which would also stop `pytest examples/demo_suite` from
  working and hides the demo from the repository's own runs by configuration rather than by an
  explicit, tested exclusion; and not exporting `FakeProvider` until Phase 9, which contradicts
  the spec's export list and the demo's fixtures. This is not the sanctioned edit to the frozen
  directory — nothing in it changed — and the file it adds is temporary by construction.
  One consequence is recorded here rather than fixed: the gate's lint command is
  `ruff check src tests examples`, so the repository-level `conftest.py` is outside it. It was
  checked and formatted explicitly with `ruff check conftest.py`, and it disappears in Phase 9.

## 17. The byte-identity gate compares the working tree, and looks for untracked files too

- **Date:** 2026-09-03 (Phase 2)
- **Q:** `tests/test_demo_spec.py` compared the introducing commit against `HEAD`. An edit to
  `examples/demo_suite/` that has not been committed yet therefore passed the gate, and so did a
  brand-new file dropped inside the frozen directory.
- **A:** Compare against the working tree — `git diff --quiet <commit> -- examples/demo_suite` with
  no second revision — and additionally assert that `git status --porcelain -- examples/demo_suite`
  prints nothing. Both failure modes were provoked before and after the fix.
- **Why:** The uncommitted edit is exactly the state the gate exists to catch: it is what a session
  that "just needed one small change to the example" produces, and comparing two commits passes
  right up to the moment the damage is recorded. `git diff` reports tracked files only, hence the
  second command, which also sees untracked ones; `__pycache__` is git-ignored, so neither command
  trips over the directories pytest leaves behind. Rejected alternative: `git stash` around the
  comparison, which mutates the user's working tree from inside a test.

## 18. A fake's substring keys are checked in insertion order

- **Date:** 2026-09-03 (Phase 2)
- **Q:** Spec §3.3 says `FakeProvider` looks up a call key first and a "literal prompt substring"
  second, but not which substring wins when two keys both occur in the prompt.
- **A:** Insertion order of the `responses` mapping. The fallback when nothing matches is
  `FAKE(<stable_hash of the prompt>)`, and `ScriptedProvider` reports `name = "scripted"` while
  `FakeProvider` reports `"fake"`. Each completion's `raw` records which layer answered
  (`call_key`, `substring`, `default`, `fallback` or `script`).
- **Why:** Insertion order is the order the author wrote, so a table can express priority by being
  read top to bottom, and it needs no explanation in the demo suite, whose keywords are each
  unique anyway (`tests/test_demo_spec.py` asserts that). Recording the matching layer makes a
  keyword table that misses diagnosable without a debugger. Rejected alternative: longest match
  wins, which is more forgiving of overlapping keys and hides the overlap that
  `test_every_scripted_keyword_selects_exactly_one_case` exists to catch.

## 19. `schema_file` resolves against a `base_dir` argument, defaulting to the working directory

- **Date:** 2026-09-03 (Phase 3)
- **Q:** `schema_valid` may name a schema by path instead of inlining it, and spec §3.4 does not
  say what a relative `schema_file` is relative to, nor what format the file is in.
- **A:** `evaluate_schema_valid` and `evaluate_case` take a keyword-only `base_dir: Path | None`,
  and a relative `schema_file` is resolved against it; an absolute one ignores it. The default is
  `Path.cwd()`, which is pytest's rootdir under a normal invocation, and Phase 9's plugin will
  pass `config.rootpath` explicitly. The file is read with `yaml.safe_load`, so both YAML and JSON
  work through one code path. `evaluate_case`'s `output` is the answer text, a `str`; normalising
  a SUT's `str | Completion` return (spec §3.12) belongs at the SUT boundary in the plugin.
- **Why:** `LLMCase` stays free of absolute paths and free of any knowledge of where it was
  loaded from, which is what lets a case file be committed, diffed and moved between checkouts;
  it is also consistent with spec §0, which makes rootdir the origin for every other path. JSON
  is a subset of YAML, so one parser costs nothing and adds no dependency. Rejected alternatives:
  recording the source file on each case at load time and resolving against it, which pushes an
  absolute path from the loader's machine into a frozen model and into every hash computed over
  it; and resolving against the case file implicitly by re-reading it at evaluation time, which
  makes an assertion's behaviour depend on the loader having left the file where it was.

## 20. `TrigramCosine`'s three degenerate cases are decided by equality, not by arithmetic

- **Date:** 2026-09-03 (Phase 3)
- **Q:** Character trigrams over a string shorter than three characters produce an empty vector,
  so the cosine is undefined; identical strings can come out fractionally under 1.0 in floating
  point; and strings sharing no trigram divide a zero dot product by a positive norm.
- **A:** If either string has no trigrams after normalisation, return `1.0` when the two normalised
  strings are equal and `0.0` otherwise. Return `0.0` as soon as the dot product is zero, without
  dividing. Clamp the result with `min(1.0, ...)` so identical strings score exactly `1.0`.
- **Why:** "Two strings that normalise to the same thing are maximally similar" is the rule the
  backend already follows everywhere else, so extending it to the strings too short to have a
  trigram keeps one rule rather than adding a special case with its own answer. Exactness matters
  beyond tidiness: Phase 5 compares snapshot scores with a 0.05 tolerance and Phase 8 compares
  variant verdicts, and a similarity of 0.9999999999999999 for an unchanged output is a drift
  signal that means nothing. Rejected alternatives: padding short strings with sentinel characters
  so a vector always exists, which invents trigrams the input never had and makes `"ab"` and
  `"cd"` share the padding; and returning `0.0` for anything too short, which reports a case whose
  reference and output are both `"ok"` as maximally dissimilar.

## 21. `contains` scores the fraction of all declared substrings, so score and verdict can disagree

- **Date:** 2026-09-03 (Phase 3)
- **Q:** Spec §3.4 gives `contains` the score "fraction matched", but a `contains` assertion has
  two lists with different rules: every `all` entry is required and one `any` entry is enough.
- **A:** The score is the fraction of `all` and `any` together that appear. The verdict is
  unchanged: every `all` present, and at least one `any` present when `any` is non-empty. So
  `any: [a, b, c, d]` matching one substring **passes with a score of 0.25**. `not_contains`
  mirrors it as the fraction absent.
- **Why:** The two numbers answer two questions and a report shows both. The verdict answers "did
  this case pass", and one `any` match is exactly what `any` asked for. The score answers "what
  moved", and that is what a snapshot in `scores` mode is diffing: an answer that used to name
  three of the four recommended drug classes and now names one has changed in a way worth seeing
  before the day it names none. Rejected alternative: scoring 1.0 or 0.0 to mirror the verdict,
  which is honest but throws away the only continuous signal these assertions have and makes
  `snapshot: scores` on a substring-only case identical to `snapshot: off`.

## 22. A mistake inside an assertion is a failed result, not an exception

- **Date:** 2026-09-03 (Phase 3)
- **Q:** An empty similarity reference, a `backend:` name that is not registered, a `schema_file`
  that does not exist and a `schema:` that is not a valid JSON Schema are all mistakes in the
  case, not failures of the application. Spec §3.4 says assertions never raise; it does not say
  whether these count as configuration errors that should escape anyway.
- **A:** They are `AssertionResult(passed=False)` with a detail naming the mistake, and `score` is
  `None` where no number would mean anything (empty reference, unknown backend) and `0.0` where
  the check ran and failed. `schema_valid` scores `1.0` or `0.0`; it is binary, but a number keeps
  it comparable in a snapshot alongside the fractional scores.
- **Why:** These mistakes are found by running the suite, and one raised exception ends the
  session at the first bad case, so a developer fixes them one per run. As results they all appear
  in one report, next to the cases that are genuinely failing, which is the same argument that
  makes `evaluate_case` run every assertion instead of stopping at the first. They are never
  mistaken for passes, because they are failures. Rejected alternative: raising
  `ProbatioConfigError` for the four of them, on the grounds that a typo in a case is categorically
  different from a bad answer — true, but it is a distinction the `detail` already draws, and
  paying for it with a suite that aborts is the wrong trade for a tool whose whole point is
  reporting everything that is wrong at once.

## 23. A rubric name is resolved against an ordered list of directories, not against rootdir alone

- **Date:** 2026-09-03 (Phase 4)
- **Q:** Spec §3.5 says a rubric is `rubrics/<name>.md` "under rootdir, or an absolute path".
  `examples/demo_suite/` keeps its rubric at `examples/demo_suite/rubrics/faithfulness.md` and
  runs with rootdir above it — the repository root under a plain `pytest`, and `pytester`'s
  temporary directory when the gate runs the suite through `pytester` — so a rootdir-only rule
  fails every judge assertion in the frozen example. What is a rubric name relative to?
- **A:** `resolve_rubric`, `evaluate_judge` and `evaluate_case` take a keyword-only
  `rubric_dirs: Sequence[Path] | None`, searched in order, defaulting to `[Path.cwd() /
  "rubrics"]`. Phase 9's plugin will pass `[rootdir / "rubrics", <requesting test module's
  directory> / "rubrics"]`. An absolute `rubric` ignores the list. A name that resolves nowhere is
  a failed `AssertionResult` naming every directory searched (DECISIONS 22), not an exception.
- **Why:** rootdir stays first, so spec §0's "paths are relative to rootdir" remains the rule and
  a repository-wide `rubrics/` keeps working; the second entry is what makes a self-contained
  suite — one a user can copy, or that lives in `examples/` — carry its own rubrics. It is the
  same shape as DECISIONS 19's `base_dir` for `schema_file`, so the two path-resolving assertions
  behave alike. Rejected alternatives: recording each case's source file at load time and looking
  for `rubrics/` beside it, which pushes the loader's absolute paths into a frozen model and into
  every hash taken over it (rejected for the same reason in DECISIONS 19); and requiring an
  absolute path in the demo suite, which would mean editing the frozen example and would make the
  YAML unportable between checkouts.

## 24. Kappa with one label used by both raters is 1.0, decided rather than computed

- **Date:** 2026-09-03 (Phase 4)
- **Q:** When both raters give every item the same single label, the expected agreement `p_e` is
  1 and Cohen's kappa is `0 / 0`. Statistics packages variously return `NaN`, `0.0` or raise.
- **A:** Return `1.0`. Observed agreement in that situation is necessarily perfect, so this is the
  only value that is not actively misleading, and it is documented in the function's docstring and
  pinned by a test.
- **Why:** the alternative that reads best on paper, `NaN`, would then flow into a validation
  record, into `--min-kappa` comparisons (where every comparison against `NaN` is false, so a
  degenerate sample would silently pass any floor) and into the report. `0.0` is worse: it says
  "no better than chance" about two raters who agreed on all forty items. Raising was rejected
  because a degenerate sample is a fact about the data, not a bug in the caller, and the honest
  handling is to report it with the agreement and `n` beside it. The situation is also visible in
  the result: `labels` has one entry.

## 25. Judge verdicts are translated into the human label space by a `--label-map`

- **Date:** 2026-09-03 (Phase 4)
- **Q:** Cohen's kappa is defined over one label space. The judge answers `pass`/`fail`; the
  Consilium samples are labelled `supported`/`unsupported`. Comparing them raw gives an agreement
  of exactly zero, which is a units error, not a measurement.
- **A:** `validate-judge --label-map` takes comma-separated `from=to` pairs and defaults to
  `pass=supported,fail=unsupported`; the map is applied to labels in both modes, and a label the
  map does not mention is compared verbatim. So the fixtures' `judge_label` column, which already
  holds `supported`/`unsupported`, passes through untouched and reproduces 0.350 and 0.592, while
  `--run-judge` verdicts land in the same space. `--label-map ""` compares labels verbatim.
- **Why:** one option, one default, and the translation is written down in the command line and in
  the record's provenance rather than hidden in the code. Rejected alternatives: hard-coding the
  pair, which silently mistranslates any other rubric's labels; and normalising both columns to
  booleans "positive/negative", which requires Probatio to decide which label is the positive
  class for a rubric it has never seen, and which loses multi-label rubrics entirely.

## 26. `validate-judge` requires `--rubric` in both modes, and builds each row's case from named columns

- **Date:** 2026-09-03 (Phase 4)
- **Q:** Spec §3.13 lists `--rubric` inside the `--run-judge` group, and names
  `--answer-column`/`--context-column` but no column for the question and no id column. What does
  `columns` mode write into `rubric` and `rubric_hash`, and what exactly does the judge see?
- **A:** `--rubric` is required in both modes: the record is named after a rubric and pins its
  content hash, so a measurement with no rubric attached could not be read back by an assertion.
  Under `--run-judge` each row becomes one `LLMCase` with id `row-<n>`, whose input holds only the
  columns named by `--question-column` (default `question`) and `--context-column` (the cell
  becomes one document); a row with neither is an error naming both flags. Nothing else from the
  row reaches the prompt, and a test asserts that sentinel values planted in the label and notes
  columns never appear in it.
- **Why:** a judge shown the label it is being measured against measures nothing, so the prompt is
  built from an allow-list of columns rather than by excluding the two label columns — excluding
  is the rule that breaks the day a sample carries a third column with the answer in it. The added
  `--question-column` is needed because the samples' questions are in a column of their own and a
  faithfulness rubric graded without the question cannot tell "does not address the question" from
  "unsupported". Rejected alternative: passing the whole row as the input, which is both a leak
  and unfaithful to what the application under test was given.

## 27. `cli.main` takes an argv sequence, and the Phase 0 smoke test was updated to pass one

- **Date:** 2026-09-03 (Phase 4)
- **Q:** Phase 0's `main()` took no arguments and returned 0, and its smoke test called `main()`.
  A subcommand parser has to read arguments from somewhere, and argparse reading `sys.argv`
  directly makes the CLI untestable in-process.
- **A:** `main(argv: Sequence[str] | None = None) -> int`, defaulting to `sys.argv[1:]`. The
  console script still calls `main()`. `tests/test_smoke.py` now calls `main([])`, which is
  Phase 4's one edit to an earlier phase's test: called with no arguments inside a `pytest` run it
  would parse pytest's own flags. `main([])` prints help and returns 0; a `ProbatioError` is
  reported as one line on stderr with exit status 2, and `--min-kappa` failure is status 1.
- **Why:** every CLI test in this phase runs in-process against a `FakeProvider`, which is what
  keeps `--run-judge` covered without a live model. Rejected alternative: testing the CLI through
  `subprocess`, which cannot inject a provider and would either need a network or a stub installed
  into the child interpreter.

## 28. `judge_model` is null in `columns` mode

- **Date:** 2026-09-03 (Phase 4)
- **Q:** Spec §3.5's record shows `judge_model` as a string, but in `columns` mode Probatio did
  not produce the verdicts and has no way to know which model did.
- **A:** `judge_model: str | None`, written as `null` in `columns` mode and set from the grading
  completion's `model` under `--run-judge`.
- **Why:** the same rule as `Completion.cost_usd` (spec §3.3): `None` means "unknown" and a
  plausible stand-in is worse than an absent value. Rejected alternative: a `--judge-model` flag
  the user types in `columns` mode, which records an unverified claim in a provenance file.

## 29. `JudgeVerdict` requires `verdict` and `score`, tolerates a missing rationale and unknown keys

- **Date:** 2026-09-03 (Phase 4)
- **Q:** Phase 4 first parsed the judge's reply with `extra="forbid"` and a required `rationale`,
  so a reply that omitted the sentence or volunteered a `confidence` key was rejected and the
  assertion failed with `judge output was not valid JSON`. Is a format deviation a failed grade?
- **A:** No. `verdict` (`"pass"`/`"fail"`) and `score` (a number in [0, 1]) stay required and
  strictly typed, and a missing or out-of-range one is still `judge output was not valid
  JSON: ...`. `rationale` defaults to `""` and `model_config` is `extra="ignore"`, so unknown keys
  are dropped. When the rationale is empty the assertion's detail simply ends after the
  threshold, with no dangling colon.
- **Why:** `verdict` and `score` are the only load-bearing fields — they are what decides the
  assertion and what a snapshot compares — and everything else is for the reader. The cost of
  being strict beyond them is paid in Phase 12, where `validate-judge --run-judge` grades a
  labelled sample and every rejected reply enters the comparison as a fail grade: a judge that
  formats its JSON loosely would then show a lower kappa than its judgement deserves, and the
  measurement would be partly about format compliance while being reported as agreement. Rejected
  alternatives: keeping `extra="forbid"` and treating a deviation as a fail, which is the
  behaviour just described; and coercing loosely (upper-case verdicts, string scores), which is
  the salvage pass rejected in `docs/DESIGN.md` because it hides a drifting judge.

## 30. A baseline whose assertion list no longer lines up is drift in the case's own mode

- **Date:** 2026-09-03 (Phase 5)
- **Q:** Spec §3.6's `scores` comparison walks two lists of assertions in parallel. What happens
  when the case has been edited since the baseline was recorded, so the two lists have different
  lengths, or the same length with different types in a different order? The choice is between
  `prompt_changed`-style "this baseline no longer describes this case, re-record" and reporting it
  as a scores diff.
- **A:** It is a scores diff: state `scores_changed`, `passed` false, and a table that lays the
  two lists beside each other with `absent` in the column that has no row and `assertion list` in
  the change column. The same rule covers a case whose `snapshot` setting changed since the
  baseline was recorded: that reports in the *current* mode's state, `scores_changed` or
  `output_changed`, with a detail naming both modes. Every one of these details names
  `pytest --update-baseline`, which is the "re-record" half of the rejected option.
- **Why:** The six states are fixed, and `prompt_changed` has one meaning that Phase 9's `check`
  relies on: the model was asked a different question, so the old numbers are about something
  else. An edited assertion list is the opposite situation — the same question, different
  expectations — and calling it `prompt_changed` would print "prompt changed since baseline" over
  a prompt that did not change, which is a false statement in the one place a developer is
  looking for a true one. Reporting it as drift in the case's own mode keeps the two failures
  distinguishable in a report while giving both the same fix. Rejected alternatives: a seventh
  state such as `shape_changed`, which every reporter, the results JSON schema and the JUnit
  properties would have to learn for a case that is already covered by "this case moved"; and
  comparing the assertions that do line up and ignoring the rest, which reports `unchanged` for a
  case that lost an assertion — the exact regression a snapshot exists to catch.

## 31. `output` is stored only in `output` mode, and an `off` case gets no result at all

- **Date:** 2026-09-03 (Phase 5)
- **Q:** Spec §3.6's baseline JSON has both an `output` field, typed `"…" | null`, and an
  `assertions` list, and does not say which mode fills which. And `compare` has to return
  something for a case whose `snapshot` is `off`, but `off` is not one of the six states.
- **A:** `assertions` is always recorded; `output` is recorded only in `output` mode and is
  `null` in `scores` mode, enforced by a model validator on `Baseline` so neither half can be
  written or read in a shape a comparison would have to guess about. `compare` returns
  `SnapshotResult | None` and returns `None` for an `off` case, before it computes a path, so no
  file is read and none is written.
- **Why:** A `scores` baseline is a file a user commits, reviews in a pull request and diffs;
  filling it with a paragraph of model prose that nothing compares would make every such diff
  unreadable and would quietly commit generated text for a user who asked only for numbers.
  Recording the assertions in both modes costs four short lines and means an `output` baseline
  still says what the case concluded. `None` rather than a seventh state keeps the state set equal
  to the set of things that can be *reported*, and makes the caller's "did a snapshot happen"
  question a `is None` test rather than a string comparison it could get wrong. Rejected
  alternatives: always storing the output, and an `"off"`/`"skipped"` state that every reporter
  would have to filter out of its snapshot section.

## 32. Scores are rounded to six decimals on both sides, and the tolerance is applied to the rounded difference

- **Date:** 2026-09-03 (Phase 5)
- **Q:** Spec §3.6 fails a `scores` comparison when a score "moves by more than 0.05". Binary
  floating point makes both halves of that sentence ambiguous: a score written to JSON and read
  back must compare equal to itself, and `abs(0.45 - 0.40)` is `0.049999999999999996`, so a move
  of exactly the tolerance is on the wrong side of a naive `> 0.05`.
- **A:** One rounding, `round(score, 6)`, is applied when a score is written into a baseline
  **and** to every live score before it is compared, so the two sides are always rounded the same
  way. The comparison is `round(abs(before - after), 6) > 0.05`, so a move of exactly 0.05 is not
  drift, 0.06 is, and 0.04 is not. A score that changes between `None` and a number, in either
  direction, is a change: there is no distance between "no score" and 0.0.
- **Why:** Six decimals is far finer than the 0.05 tolerance and than anything a report prints
  (the table shows three), so the rounding cannot change a verdict a user would recognise, while
  it does remove every way a run can differ from itself. Rounding the difference rather than
  comparing raw floats makes "more than 0.05" mean what it says at the boundary instead of
  meaning it for most values and not for 0.45 against 0.40. Rejected alternatives: an epsilon
  added to the tolerance, which is the same fix written so that the number in the code no longer
  matches the number in the spec; and `math.isclose`, whose relative tolerance would make the
  same absolute move drift at one end of the [0, 1] range and not at the other.

## 33. An unparsable baseline is a configuration error, not a silent re-record

- **Date:** 2026-09-03 (Phase 5)
- **Q:** The store never raises for drift. What should it do with a baseline file that exists but
  cannot be read or does not parse — truncated by a killed run, mangled by a bad merge, edited by
  hand? The easy option is to treat it like a missing file and record a fresh one.
- **A:** `BaselineStore.load` raises `ProbatioConfigError` naming the file, the case and
  `pytest --update-baseline`. `compare` therefore raises too, unless `update` is set, which
  overwrites without reading — so the flag the message names is also the flag that fixes it.
- **Why:** Treating a corrupt baseline as a missing one turns a lost regression signal green: the
  run that destroyed the file is also the run that reports `baseline recorded`, and the case is
  then pinned to whatever it happened to do that day. A file that exists is a claim that a
  baseline was recorded, and a store that cannot honour the claim has to say so. This is not the
  same as drift, which is the case doing something new and is always a result. Rejected
  alternative: returning `None` and recording over it, which is what makes the failure
  unobservable; a warning would have been better than nothing, but Phase 5 has no reporter to
  carry one and the error already names its own fix.

## 34. Suite and case names are checked before they become path segments

- **Date:** 2026-09-03 (Phase 5)
- **Q:** A baseline path is `<baseline_dir>/<suite>/<case_id>.json`, and `suite` reaches the store
  from its caller — in Phase 9, a test module's stem. Nothing in the store's own types stops a
  caller passing `../..`.
- **A:** Both segments must match `^[A-Za-z0-9][A-Za-z0-9._-]*$`, which is `LLMCase`'s own id
  pattern without its length bound; anything else is a `ProbatioConfigError` naming which of the
  two was wrong. The check is in `path_for`, so every read and every write goes through it.
- **Why:** `CLAUDE.md` says nothing outside the repository is read or written except paths the
  user passes explicitly, and `--baseline-dir` is such a path while a suite name is not: it is
  derived. Five lines that make the derived half unable to escape are cheaper than a rule that
  only holds because the one current caller happens to pass a Python module stem. Rejected
  alternative: resolving the finished path and asserting it is under `baseline_dir`, which is
  correct but reports the problem as a mysterious path comparison rather than naming the
  offending argument.

## 35. An empty price file, and one whose entries are all commented out, is an empty table

- **Date:** 2026-09-04 (Phase 6)
- **Q:** `examples/prices.example.yaml` has to ship the structure without shipping any prices, and
  it has to be loadable, because a test loads it. YAML parses an all-comments file to `None`. Is
  that an empty table or a malformed file?
- **A:** An empty table. `PriceTable.load` returns `PriceTable({}, source=path)` for a document
  that parses to `None`, and only a document that parses to something other than a mapping is an
  error.
- **Why:** It makes the shipped example honest by construction: it loads, it prices nothing, and
  against it every cost ceiling in a suite is reported unenforceable, which is exactly the state
  of a suite whose prices nobody has entered. An error would have forced the example file to carry
  at least one live price, and any price committed inside this repository is a number `CLAUDE.md`
  forbids — nothing here produced it, and it would be stale within weeks. Rejected alternative:
  shipping one plausible entry and a warning comment, which puts a wrong number in front of the
  user at exactly the moment they are deciding what a ceiling means.

## 36. A case that recorded no provider calls has no enforceable ceiling of either kind

- **Date:** 2026-09-04 (Phase 6)
- **Q:** The unenforceable rule fires when any call's `cost_usd` is `None`. A case whose system
  under test made no calls at all has no such call, so both its cost and its latency sum to zero.
  Is that a known zero that satisfies the ceilings, or nothing measured?
- **A:** Nothing measured. Both ceilings the case declares come back as
  `AssertionResult(passed=False, unenforceable=True)`, with the detail
  `cost ceiling for <case> is unenforceable: no provider calls were recorded` and its latency
  equivalent, and no fix clause, because no command fixes it. `case_cost([])` is `None` rather
  than `0.0`, so the case reaches `SuiteBudget` as unknown cost and is named in the overrun line's
  unknown list instead of counted as free. This narrows "latency is always enforceable" to
  "enforceable wherever a call was made": what makes latency need no price file is that the clock
  answered, and with no calls it was never asked.
- **Why:** Spec §3.7 makes an unenforceable result a warning that is not counted as a passing
  check — not a case failure — so a legitimately call-free case (a cached or short-circuited system
  under test) is *warned about*, which costs its author a line in the warnings section, and is not
  failed. A pass, by contrast, is the vacuous pass the brief forbids: a check over zero
  observations cannot fail, so a green tick there asserts that spend and latency are bounded when
  nothing looked. It also matters for the phase that comes next: in Phase 9 the calls reach a
  budget through the collector, and a collector that is not wired up produces exactly this shape —
  every case with zero calls. Under the old answer that reads as a suite of passing budget checks;
  under this one it reads as every ceiling in the suite reporting that it measured nothing.
  Rejected alternative, and this phase's first answer: a known `0.0` that passes, with `over 0
  provider calls` in the detail as the visible symptom. It is defensible — the sum of no calls
  really is zero, and `cost_usd is None` really does mean "this call happened and nobody priced
  it" — but it buries the symptom in a detail line nobody reads on a green case, and it spends the
  one mechanism the tool has for saying "this was not measured" on the one case where the
  measurement is most obviously absent.

## 37. The unenforceable detail is spec §3.7's sentence plus the flag that fixes it, and names every unpriced model

- **Date:** 2026-09-04 (Phase 6)
- **Q:** Spec §3.7 fixes the detail text as `cost ceiling for <case> is unenforceable: no price
  configured for <model>`. A case can make calls against more than one model, and the sentence
  names no way out.
- **A:** The detail is that sentence, with every unpriced model listed in the order the calls were
  made and de-duplicated, followed by `; fix it with: pytest --probatio-prices <path>`. It is
  composed by passing the sentence through `ProbatioConfigError`, which is what renders the fix.
- **Why:** Spec §6 requires that an error name the command that fixes it where one exists, and
  here one does; the specified sentence is preserved verbatim as the prefix, so a report still
  reads the way §3.7 says it should. Listing every unpriced model matters because a judged case
  calls two models, and a detail naming only the first sends the user to add one price and run
  again. Composing through the error class keeps the sentence in one place, exactly as Phase 5
  composes drift details through `BaselineDriftError`, so Phase 9 can raise it rather than
  paraphrase it. Rejected alternative: the bare sentence with the flag left to the reporter's
  warnings section, which splits one message across two places and loses the fix wherever a raw
  `AssertionResult.detail` is printed.

## 38. Budget results carry no score

- **Date:** 2026-09-04 (Phase 6)
- **Q:** `AssertionResult.score` is a number in [0, 1] where one is meaningful. What is a cost
  check's score?
- **A:** `None`, for both `budget_cost` and `budget_latency`. The numbers live in the detail,
  which names the total, the call count and the ceiling.
- **Why:** The only natural score is the fraction of the ceiling used, and that number leaves
  [0, 1] exactly when the check fails, so the field would have to be clamped — at which point
  every failing case scores 1.0 and the score says less than the flag beside it. It also decides
  the snapshot question for free: when Phase 9 puts budget results next to a case's other results,
  a `scores`-mode baseline records `null` for them, so a latency that wobbled by two milliseconds
  is not drift while a ceiling that started failing still is, because that is a flipped verdict.
  Rejected alternative: `min(1.0, used / ceiling)`, which reads as a measurement and is not one.

## 39. The suite accumulator sums per case id, ranks only known costs, and names three of each

- **Date:** 2026-09-04 (Phase 6)
- **Q:** `SuiteBudget.record(case_id, cost)` is called as cases complete, and under `--runs N` one
  case completes N times. Spec §3.7 asks the overrun line for "the three most expensive cases"
  and says a case of unknown cost is never counted as zero. What exactly is accumulated, and what
  does the line list?
- **A:** Per case id: known costs are summed, so five runs of one case are one entry holding five
  runs' spend; a `None` marks that case unknown and contributes nothing to the total. The ranking
  covers only cases whose cost is known, dearest first with ties broken by case id, and both lists
  in the line — the three dearest and the unknown ones — are capped at three names, the unknown
  list adding `and N more`.
- **Why:** Ranking a case whose cost is unknown would mean ordering it by a number that does not
  exist, and giving it a zero is the one thing spec §3.7 forbids; naming it in its own clause says
  what is missing without pretending to know how much. The per-id sum is what makes the line's
  "most expensive" mean "the case that cost the most this session" rather than "the run that cost
  the most". The cap is there because §3.7 asks for one line, and a suite with two hundred unpriced
  cases would otherwise print a paragraph. Ties broken by id keep the sentence identical across
  two runs of the same suite, which is what lets a test assert it. Rejected alternative: recording
  a list of `(case_id, cost)` pairs and ranking runs rather than cases, which reports the same
  case three times in a three-line list.

## 40. A price must be a number, and every ceiling comparison is rounded to six decimals

- **Date:** 2026-09-04 (Phase 6)
- **Q:** A price table is a hand-edited file, and pydantic in its default mode will read `"3.0"`
  and `true` as `3.0` and `1.0`. Separately, `0.1 + 0.2` is more than `0.3` in binary floating
  point, so a suite that spends exactly its ceiling can be over it.
- **A:** Prices go through a validator that refuses anything that is not an `int` or a `float`,
  bools included, naming the type it got; and every comparison of a total with a ceiling rounds
  the difference to six decimals — a hundredth of a cent — before asking whether it is positive.
  Money is printed to the same six decimals.
- **Why:** A quoted price is a typo in a file whose numbers decide what every ceiling in the suite
  means, and a silent coercion of `true` to one dollar per million tokens is a wrong ceiling that
  nobody will ever look at again. The rounding is Phase 5's reasoning about score drift
  (DECISIONS 32) applied to money: a ceiling met exactly must be met, and the only alternative —
  an exact `>` on a float sum — fails a suite for the order its cases happened to complete in.
  Rejected alternative: pydantic's `strict=True` on the model, which also refuses `3` for a float
  field, and `input_per_mtok: 3` is a perfectly good price.

## 41. The price table is applied at completion time, and never over a cost a provider reported

- **Date:** 2026-09-04 (Phase 6)
- **Q:** Entry 15 deferred `AnthropicProvider`'s `prices` argument to this phase. Where does
  pricing happen — in the adapter, or in the budget layer at report time — and what happens when
  the completion already carries a cost?
- **A:** Both, and pricing is idempotent so that doing both is safe: `AnthropicProvider(prices=…)`
  fills in `cost_usd` when it builds the completion, and `evaluate_budget` prices whatever it is
  handed. `PriceTable.apply` returns the completion untouched whenever `cost_usd` is not `None`,
  so a reported figure is never overwritten.
- **Why:** Pricing in the adapter is what makes a recorded cassette carry the price that was in
  force when it was recorded, rather than whatever the price file says on the day it is replayed;
  pricing in the budget layer is what makes a ceiling enforceable for a provider that was built
  without a table, which includes every completion a user hands `evaluate_budget` directly. The
  protection of a reported cost is the important half: `ClaudeCLIProvider` reports a notional
  total, and a table that silently replaced it would make the tool disagree with the payload
  committed beside it — the user would have no way to tell which number they were reading.
  Rejected alternative: pricing only at report time, which is simpler and loses the recorded-price
  property of a tape; and pricing unconditionally, which quietly overwrites the one cost figure
  any shipped provider actually reports.

## 42. The judge marks its calls through the provider, not through a parameter

- **Date:** 2026-09-04 (Phase 7)
- **Q:** Spec §3.5 says the judge prompt template's hash is part of every judge cassette key, and
  spec §3.8's key is computed from a call's prompt, system, model and params. The `Provider`
  protocol has no field for a template hash and `Judge` must keep working with a provider that is
  not cassette-wrapped at all. How does the hash reach the key?
- **A:** Through a method on the provider, which delegates to a context on the store.
  `CassetteProvider.judge_calls(template_hash)` returns `CassetteStore.judge_calls(...)`, a
  context manager that sets the store's active template for the duration; the store already owns
  the rest of the active context (suite, case id, run index) that Phase 9's fixture sets with
  `begin_case`. `Judge.grade_with_completion` looks for a callable `judge_calls` on whatever
  provider it holds and enters it when it is there, and does nothing when it is not. The wrapper
  forwards `prompt`, `system` and `**params` to the inner adapter exactly as they arrived;
  `tests/test_cassette.py::test_the_judge_mark_never_reaches_the_inner_provider` and
  `::test_a_judge_handed_a_bare_provider_calls_it_unchanged` pin both halves.
- **Why:** The rejected alternative was a reserved parameter — `complete(..., _probatio_judge=...)`
  — stripped by the wrapper. It is fewer lines, and it is wrong in the one case that matters: a
  judge provider that is not cassette-wrapped, which is every `--cassette=off` run and every
  direct `Judge(rubric, AnthropicProvider())`, would forward the reserved key straight into
  `messages.create`, where it is either an API error or, worse, silently accepted. A parameter is
  also a lie about the request: nothing about the template changes what is sent to the model, only
  what the call is filed under, which is a property of the recording and belongs to the recorder.
  Duck-typing on a method rather than an `isinstance` check keeps `judge/` from importing
  `cassette.py`, which would close an import cycle through `probatio.judge.__init__`.

## 43. The cassette key lifts `model` out of `params` rather than hashing it twice

- **Date:** 2026-09-04 (Phase 7)
- **Q:** Spec §3.8's key is `stable_hash({"prompt", "system", "model", "params": sorted…,
  "template"})`, but in practice the model arrives *inside* `params`, because that is where
  `LLMCase.params` puts it and what `Provider.complete(**params)` receives. Is `model` a copy of
  `params["model"]`, or is it removed from `params`?
- **A:** Removed. `interaction_key` pops `model` out of a copy of the params and hashes it under
  the key's own `model` field; everything else is hashed under `params`. The key is computed
  before the call in replay, so `model` can only ever be what the case asked for, never what a
  provider reported.
- **Why:** Hashing the same value twice makes the key's `model` field decorative — it could be
  dropped with no change in behaviour — and spec §3.8 clearly means the two to be separate parts.
  Popping it makes each part answer one question, so a stale-tape message can say "the prompt, the
  model or the params changed" and mean three distinct things. Rejected alternative: leaving
  `params` whole and taking `model` from the completion after the call, which cannot work at all
  in replay, where there is no completion until the key has already found one.

**Amendment, 2026-09-04 (Phase 7, before the phase was pushed).** The rule above was right about
the key's shape and wrong about where the model comes from. `params.get("model")` is not the model
that answers the call: both shipped live adapters compute `params.pop("model") or self.model`, and
`self.model` is what `--probatio-model` puts in the constructor. Since no case in the demo suite
names a model in `params` — none of the ten do — the key's `model` field was `None` for every one
of them, so a tape recorded through `ClaudeCLIProvider(model="A")` replayed without complaint
through `ClaudeCLIProvider(model="B")`: exactly the regression a cassette is supposed to catch, and
one that would have shipped as a silent wrong answer rather than as a `StaleCassetteError`.

The fix restates the adapters' own precedence in one place. `resolve_model(params, fallback)`
returns `params["model"]` when the call names one and `fallback` otherwise;
`CassetteProvider.inner_model` reads `getattr(self.inner, "model", None)` and passes it to the
store in **both** `record` and `replay`, so the key is worked out the same way on both sides and
before the call, which is what replay requires. The parameters forwarded to `inner` are untouched:
the wrapper reads the adapter's model, it never writes one into the call.
`Interaction` gained a `model` field recording what the key was computed from — a deviation from
spec §3.8's illustrative JSON, taken because a stale tape a human has to diagnose should say which
model it belongs to. `import-cassettes` uses the line's own `model` field as the fallback, which is
the same precedence for the same reason. `tests/test_cassette.py::
test_a_tape_recorded_on_one_model_does_not_replay_on_another` records through
`FakeProvider(model="m1")` with no model in `params`, replays through `FakeProvider(model="m2")`
and expects `StaleCassetteError`, then replays through a second `m1` wrapper and expects the
recorded answer with `call_count == 0`.

Rejected alternative: taking the model off the returned `Completion` instead. It is the model that
genuinely answered, which is more truthful, and it is unavailable in replay — the key has to find
the interaction before there is any completion to read — so the two modes would have keyed on
different things, which is the one thing a cassette key may never do.

## 44. Recording replaces a key's samples the first time it is seen in a session, and appends after

- **Date:** 2026-09-04 (Phase 7)
- **Q:** Spec §3.8's table says a `record`-mode hit overwrites the interaction and a miss appends
  one, while the paragraph below says recording under `--runs N` appends one sample per run. Both
  cannot be literally true of the same call: run 2 of 3 is a hit, and overwriting it would leave
  one sample instead of three.
- **A:** The store remembers which `(suite, case_id, key)` triples it has already recorded. The
  first sample for a key clears that interaction's `completions`; every later sample appends. A
  `--runs 3` re-record therefore leaves exactly three samples, not three added to the five that
  were there before, and interactions the session never touched keep their old samples and their
  position in the file.
- **Why:** "Overwrite that interaction" is a statement about what a re-recording session leaves
  behind, and this is the reading that makes it true for every N. The rejected alternative was to
  key the behaviour on `run_index == 0`, which is one line shorter and quietly wrong whenever a
  case makes the same call twice within one run — the second call would overwrite the first, and a
  suite that asks its model the same question twice would record half its samples.

## 45. An import line with an unknown key is refused, not ignored

- **Date:** 2026-09-04 (Phase 7)
- **Q:** `probatio import-cassettes` reads a JSONL whose fields spec §3.8 lists. What happens to a
  line that carries a key that is not on the list?
- **A:** `ProbatioConfigError` naming the line number and the key. `ImportedCall` is
  `extra="forbid"`, like `LLMCase`, and every parse failure — bad JSON, a JSON array, a missing
  `case_id`, an unparsable `latency_ms` — is reported the same way, with the line number and, when
  the caller knows it, the file.
- **Why:** The producer of this file is a script somebody wrote — Phase 11's Consilium trace
  exporter is the first — and a misspelled `latency` that is silently dropped becomes a committed
  tape full of zero latencies, which then passes every latency ceiling in the suite. `LLMCase`
  already refuses unknown keys for exactly this reason (spec §3.2: "a typo like `assertion:` fails
  loudly"), and an imported tape is no less an artefact than a case file. Rejected alternative:
  ignoring unknown keys so that a richer trace format can be fed in unchanged, which trades a
  five-second fix at import time for a silently wrong tape nobody re-reads.

## 46. One `artefacts.py` for the clock, the name check and the JSON writer

- **Date:** 2026-09-04 (Phase 7)
- **Q:** The Phase 7 brief asks for the injectable timestamp helper to be factored out, this being
  its third copy (`snapshot.py`, `judge/validation.py`, now `cassette.py`). Where does it live, and
  does anything else move with it?
- **A:** A new module `src/probatio/artefacts.py`, holding what every file Probatio persists has in
  common: `Clock`, `utc_now`, `format_instant` and `timestamp`; `check_path_segment` and
  `NAME_PATTERN`, the DECISIONS 34 rule that a derived name cannot escape a store's directory; and
  `write_json`, the sorted-keys, indent-2, one-trailing-newline writer all three stores used.
  `judge.validation.utc_now`, which returned a string, is gone: `cli.py` and its test now call
  `artefacts.timestamp()`, and `probatio.judge`'s `__all__` is one entry shorter. `snapshot.py`
  lost `_utc_now`, `_format_instant` and `_NAME_PATTERN`.
- **Why:** All three were about to be copied a third time, and the two beyond the clock are the
  ones where a copy diverging would be a defect rather than a nuisance — a store whose path check
  drifted would let a derived name escape, and a store whose writer drifted would produce diffs in
  a user's repository on re-recording. The module is named for what its contents are about (files
  Probatio writes and commits) rather than for their shapes, so Phase 8's `variants/` writer has
  somewhere obvious to go. Rejected alternatives: a `clock.py` holding only the timestamp, which
  would have left the other two copies to be made a third time and then factored later; and
  putting the helpers in `hashing.py`, which is the other module everything already imports but
  is about identity, not persistence.

## 47. `order_invariant` samples shuffles under a computed ceiling, rather than enumerating

- **Date:** 2026-09-04 (Phase 8)
- **Q:** Spec §3.9 asks for "up to `k` distinct non-identity permutations" seeded from
  `random.Random(stable_hash((case.id, field)))`. A seeded shuffle can return the identity or a
  repeat, and asking for `k=3` permutations of a two-element list — which spec §3.9's own
  acceptance criterion does — can only ever yield one. How does the loop know when to stop?
- **A:** Compute the number of distinct non-identity orderings first and take `min(k, ceiling)`.
  The count is `n! / ∏(duplicate counts!) − 1`, computed exactly for lists of up to ten items and
  treated as unbounded above that, since no realistic `k` approaches `11!`. Duplicated items are
  divided out through `canonical_json`, so `["a", "a", "b"]` reports two orderings, not five. Then
  shuffle until that many distinct non-identity orderings have been seen, with a budget of
  `200 × k` attempts as a backstop.
- **Why:** The ceiling is what makes the two-element acceptance criterion a property of the code
  rather than of luck: without it the loop either spins to its attempt budget on every short list
  or returns fewer variants for a reason no reader could predict. Dividing out duplicates matters
  because a retrieval-grounded suite really does have cases with two identical documents, and
  "3 variants, 0 violations" over a list with two distinct orderings would be a rate over a
  variant that was never generated. Rejected alternative: enumerating `itertools.permutations` and
  sampling from it, which is exact and correct up to about eight items and then allocates
  factorially; a hybrid of the two code paths costs more to read than the ceiling does.

## 48. Variant labels are fixed strings the relation chooses, not indices from the caller

- **Date:** 2026-09-04 (Phase 8)
- **Q:** `Variant(case, label)` gives every variant a label, and `Flip` reports it. Who names
  them?
- **A:** The relation, from its own configuration: `permutation-1..k`,
  `distractor-<position>-<index>`, the jitter kind itself (`whitespace`, `casing`, `markdown`),
  and `paraphrase-1..k`. No label is derived from a position in a list the plugin holds.
- **Why:** A label is what a report and a results JSON identify a violation by, so it has to mean
  the same thing in two runs and in two reports. `format_jitter`'s labels being the kind names is
  the point of the example: "casing flipped this case" is a diagnosis, where "variant 2 flipped
  this case" is a lookup. Rejected alternative: numbering every variant uniformly, which is one
  line shorter and makes the most useful relation's output unreadable.

## 49. `changed_assertions` names each type once, and a length mismatch truncates

- **Date:** 2026-09-04 (Phase 8)
- **Q:** Spec §3.9's `Flip.changed_assertions` "names the assertion types whose passed flag
  differed". A case may declare two assertions of the same type, and a defensive reader has to ask
  what happens if the two result lists are not the same length.
- **A:** Types are reported once each, in declaration order, first occurrence first. The two lists
  are compared position by position with `zip(..., strict=False)`, so a mismatch truncates rather
  than raising.
- **Why:** A variant is the same case with one field replaced, so the lists are always the same
  length and the `strict=False` branch is unreachable by construction — but "unreachable by
  construction" is exactly the kind of claim that stops being true, and spec §3.9 promises that a
  relation violation never raises. Truncating loses a line of a report; raising would turn a
  robustness observation into a failed test. Reporting a type once rather than per assertion keeps
  the field a diagnosis of *what kind* of check moved, which is what a reader of the flips table
  wants. Rejected alternatives: `strict=True`, which trades a readable report for an exception at
  the worst moment; and reporting `assertion_type[index]` pairs, which is more precise and reads
  like a stack trace.

## 50. `distractor_robust` makes one variant per position and distractor

- **Date:** 2026-09-04 (Phase 8)
- **Q:** The relation takes a list of distractors and a tuple of positions. Is a variant one
  distractor at one position, or every distractor at one position?
- **A:** One variant per `(position, distractor)` pair, positions outer and distractors inner, so
  two distractors at two positions is four variants.
- **Why:** A violation rate is only actionable if a violation names one change. With every
  distractor inserted at once, a flip says "some irrelevant text at the start moved the verdict"
  and the developer has to bisect the list by hand; per pair, the label says which text at which
  end. It also makes the rate's denominator equal to the number of things actually varied.
  Rejected alternative: inserting the whole list per position, which is two variants instead of
  four for the demo suite and would report `distractor-start` as a single opaque failure.

## 51. The demo README's casing claim holds for three of its five candidate cases, and cannot hold for the other two

- **Date:** 2026-09-04 (Phase 8)
- **Q:** `examples/demo_suite/README.md` says of `format_jitter`: "Upper-casing the first sentence
  destroys the keyword when it is in that sentence, so those cases flip; the two cases whose
  keyword sits in a second sentence (`t2d-metformin`, `red-flag-chest-pain`) do not." Measured,
  the casing variant flips `htn-definition`, `htn-first-line` and `t2d-screening-json` — and not
  `gerd-alarm-features` or `insomnia-first-line`, whose keywords are in their questions' first
  sentences. Is the implementation wrong?
- **A:** No, and no implementation can make those two flip. The demo applies
  `format_jitter(field="input.question")`, so the transform reaches the question and nothing else;
  the scripted provider matches its keyword against the **whole prompt**, which the app builds
  from the documents *and* the question. `gerd-alarm-features` has "alarm" in its second document
  ("without alarm features") and `insomnia-first-line` has "insomnia" in two of its three, both in
  lower case. Upper-casing the question removes the keyword from the question and leaves it in the
  prompt, so the provider still matches, the answer is unchanged and the verdict cannot move. The
  README's sentence is true of the question and overstates its consequence for the prompt; the
  frozen directory is not edited (gate condition 5), the measured outcome is asserted in
  `tests/test_metamorphic_demo.py`, and a test named for these two cases pins the reason — keyword
  in the question's first sentence, keyword also in a document, no flip — so the discrepancy is
  recorded in the suite rather than in prose.
- **Why:** The alternative readings all cost more than they are worth. Making the two cases flip
  would need `format_jitter` to jitter fields the decorator was not given, which contradicts the
  `field=` argument the demo passes and DECISIONS 8's whole notion of a relation's target.
  Weakening the test to assert only "at least three cases flip" would let a future regression in
  `upper_first_sentence` pass unnoticed. Editing the README is forbidden and, in any case, the
  README's mechanism claim is the useful half: the three cases whose keyword is unique to the
  question do flip, exactly as it says they should. The correction itself is written down where a
  reader of the demo will meet it, in an "Errata for `demo_suite/README.md`" section of
  `examples/README.md`, which is tracked and outside the frozen directory; a test asserts that the
  section names both cases and both pinning tests, so renaming a test cannot orphan the errata.

## 52. A frozen variants file with fewer entries than `k` is used as it stands

- **Date:** 2026-09-04 (Phase 8)
- **Q:** `paraphrase_invariant(k=3)` reads paraphrases from `variants/<case_id>.yaml`. What if the
  file holds two?
- **A:** It is measured over two, and the `RelationResult` reports `n_variants: 2`. Only an empty
  `variants` list is an error, and it is a `MissingVariantsError` — "the file exists but holds no
  variants" — carrying the same `probatio freeze-variants` command with `--force`, since a file is
  already there and has to be replaced rather than created. Identity is still strict: a `case_id`
  or a `field` that disagrees with the relation remains a `ProbatioConfigError`.
- **Why:** A short file is the normal outcome of the review the frozen file exists for, not
  damage. The runbook's Phase 12 instructs the human freezing paraphrases against a live model to
  **delete the ones that changed the meaning of the question and note the deletion in the file's
  header comment**; a relation that then refused to run would punish exactly the care the workflow
  asks for, and the only way to satisfy it would be to re-freeze until a model happened to return
  three usable rewordings — which is generation pressure applied to a human, in the one place the
  design deliberately puts a human. Two variants honestly labelled as two are a smaller
  measurement than three, not a wrong one, which is what reporting `n_variants` alongside the rate
  is for. An empty list is different in kind: nothing was varied, so there is no measurement at
  all, and that is the same statement `MissingVariantsError` already makes about a file that is
  not there. **Rejected alternative, and this entry's first answer:** refusing a file with fewer
  than `k` entries as a `ProbatioConfigError`, on the grounds that a suite declaring `k=3` and a
  report quoting a rate over two entries disagree with nothing saying so. That reasoning holds
  only if `n_variants` is hidden; it is in `RelationResult`, in the results JSON and in the
  relations table, so the disagreement is visible wherever the rate is. Also rejected: silently
  padding with the entries that were deleted, which would resurrect the paraphrases the reviewer
  judged unusable, and warning-but-continuing, which adds a line nobody can act on to every run of
  a file that is exactly as its author left it.

## 53. The `freeze-variants` hint in a missing-variants error names the sibling `cases/` directory

- **Date:** 2026-09-04 (Phase 8)
- **Q:** Spec §3.9 requires the `MissingVariantsError` message to contain the exact
  `probatio freeze-variants --cases … --field … --provider claude-cli` command. A relation knows
  its field and its variants directory, but nothing gives it the `--cases` directory: that
  argument is passed to `load_cases` in the user's test module, not to the decorator.
- **A:** Name `<variants_dir>/../cases`, the layout spec §5 documents and the demo suite uses, and
  fill in `--k` and `--out` from the relation so the whole line is runnable as printed.
- **Why:** A command a user can run and correct beats a placeholder they have to decode; if the
  guess is wrong, the wrong half is a visible directory path in a shell line, not a silent
  default. Passing the cases directory into the decorator was rejected: it would put the same path
  in two places in every user's test module and make the decorator's signature depend on how the
  cases happened to be loaded.

## 54. `--provider fake` bypasses the provider entirely, and tests reach the model path by replacing the factory

- **Date:** 2026-09-04 (Phase 8)
- **Q:** Spec §3.13 says `freeze-variants --provider fake` writes "mechanical rewrites" and warns
  they are not paraphrases. It also says tests exercise the command through a `FakeProvider`.
  Those are two different things through one flag.
- **A:** They stay two things. `--provider fake` calls nothing at all: it writes rewrites whose
  provenance reads `provider: mechanical`, `model: null`, `prompt_hash: null`, and prints
  `MECHANICAL_WARNING` on standard error. The model path is tested by naming a real provider and
  monkeypatching `cli.build_provider`, which is the seam `validate-judge --run-judge`'s tests
  already use (DECISIONS 26's neighbourhood).
- **Why:** Writing `provider: fake` into a committed file would claim a provider produced text
  that no provider saw, and the file is the artefact a reviewer trusts; `mechanical` is the honest
  word and it is visible in the file as well as on the terminal. Testing the model path through
  the factory rather than through the flag keeps one code path in the command instead of two, and
  means the tested path is the one a human actually runs. Rejected alternative: a `provider=`
  argument on the command function, which is a second seam for the same purpose and diverges from
  how `validate-judge` is already tested.

## 55. A `--field` that resolves on no case is a mistake in the flag, not an empty batch

- **Date:** 2026-09-04 (Phase 8)
- **Q:** A directory of cases is normally mixed: `copd-spirometry` has a bare-string input and no
  `input.question`. Skipping it is right (DECISIONS 8's reasoning). What if *every* case is
  skipped?
- **A:** A case without the field is skipped with a printed note; if no case has it, that is a
  `ProbatioConfigError` naming the field and the directory.
- **Why:** `get_field` already refuses a path whose first segment is not an `LLMCase` field
  (DECISIONS 13), but `--field input.quesion` gets past that and resolves on nothing, so the
  command would print ten skips and exit 0 having frozen nothing. Since a person runs this once,
  with a model, and then commits the result, "nothing to do" is the one outcome that must not look
  like success. Rejected alternative: exiting 0 with a summary line, which is consistent with
  every other count the command prints and turns a typo into a silent no-op.

## 56. `check_field_path` and `write_yaml` are lifted into the modules that already own their rule

- **Date:** 2026-09-04 (Phase 8)
- **Q:** A relation validates its `field` argument at construction time, before any case exists,
  and the rule for a well-formed dotted path already lives in `case.py` as the private
  `_segments`. Frozen variants are the fourth kind of persisted file and the first that is YAML,
  and `artefacts.py` holds the writer for the other three.
- **A:** `case._segments` becomes the public `case.check_field_path`, called by both `_root` and
  every relation constructor; `artefacts.write_yaml` joins `write_json`, writing the caller's key
  order with a fixed indent, no line wrapping and optional comment lines above the document.
- **Why:** A path rule copied into `metamorphic/relations.py` would drift from the one `get_field`
  enforces, and the first symptom would be a relation that accepts a path the loader rejects. YAML
  keeps insertion order rather than sorting because this is the one file kind a person reads top to
  bottom — case, field, provenance, then the variants — and the order is fixed in the caller's
  code, so two writes are still byte-identical, which a test asserts. Rejected alternatives: a
  three-line duplicate of the path check in the relations module; and hand-rolling the YAML, which
  would put string-quoting rules in Probatio for no gain.

## 57. `paraphrase_invariant` takes a `base_dir`, and resolves a relative directory when it reads

- **Date:** 2026-09-04 (Phase 8)
- **Q:** DECISIONS 19 makes a relative path resolve against a `base_dir` argument defaulting to
  the working directory, with the plugin passing `config.rootpath`. A relation is constructed by a
  decorator at import time, long before pytest's config exists.
- **A:** The decorator takes an optional fourth argument, `base_dir`, and the directory is
  resolved inside `variants()` — so with no `base_dir` the working directory is read when the
  variants are needed, not when the module was imported. The demo passes an absolute path built
  from `HERE`, so none of this affects it (DECISIONS 10).
- **Why:** Reading `Path.cwd()` at decoration time would freeze whatever directory the import
  happened in, which under `pytester` is not the directory the test runs in. Keeping the argument
  on the relation rather than on `Relation.variants` leaves the abstract method the two-argument
  signature spec §3.9 fixes, so a user's own relation is not obliged to thread a directory it does
  not use. Rejected alternative: a mutable `base_dir` attribute the plugin sets before calling
  `variants()`, which works and makes the relation's behaviour depend on an assignment somewhere
  else.

## 58. Two Phase-0-and-3 tests were updated rather than left pinning an empty surface

- **Date:** 2026-09-04 (Phase 8)
- **Q:** `tests/test_public_api.py` asserted the export set is exactly Phase 3's, and
  `tests/test_smoke.py` asserted `probatio.plugin.__all__ == []`. Phase 8 adds four exports and
  the plugin's first hook.
- **A:** `test_public_api.py` gains a `PHASE_8_EXPORTS` set and compares against the union, with
  `flaky_tolerant`, `CaseResult` and `RunReport` still asserted absent; the smoke test now asserts
  `plugin.pytest_configure` is callable.
- **Why:** Both tests exist to pin the *shape* of the surface as it grows — the demo suite's
  import guard and `tests/test_demo_spec.py`'s lifecycle check both depend on the still-missing
  names being missing, and that half is unchanged and still enforced. The alternative, deleting
  them, would drop the one check that keeps a phase from exporting a name early. This is the same
  move Phase 4 made when it deleted the test pinning the Phase 3 judge stub (DECISIONS 27's
  neighbourhood), except that here the assertion is narrowed rather than removed.

## 59. Budgets are evaluated per run, and any run over the ceiling fails the case

- **Date:** 2026-09-04 (Phase 9)
- **Q:** Spec §3.7 evaluates a case's ceilings "on the sum over all provider calls the SUT made
  during the case". Under `--runs 5` a case makes five sets of calls. Is the ceiling checked
  against each run or against the total?
- **A:** Per run. `check` calls `evaluate_budget` once per run over that run's completions, and
  the case fails if any run exceeded a ceiling. The report still totals every run for
  `CaseResult.cost_usd` and for the session's `--max-cost` accumulator.
- **Why:** `budget: {max_cost_usd: 0.01}` in a case file is a statement about answering that
  question once — the author wrote it looking at one call, and it does not become a different
  claim because the runner was invoked with `--runs 5`. Summing across runs would make every
  ceiling in every suite fail as soon as somebody measured stability, which would make the two
  features mutually exclusive. Failing on *any* run rather than on the mean is the same
  conservatism the ceiling itself expresses: a ceiling is a limit, not a target, and a case that
  costs three cents one run in five is a case that costs three cents. Rejected alternative:
  checking the mean per-run cost, which is arguably the fairer statistic and hides exactly the
  outlier a ceiling exists to catch.

## 60. A case's ceiling covers its own calls; judge and variant calls reach the session total only

- **Date:** 2026-09-04 (Phase 9)
- **Q:** Phase 6 left this open (its run-log line says so). A judged case calls the model twice —
  once to answer, once to grade — and a case with three relations calls it once per variant per
  run. Which of those count against `budget.max_cost_usd`?
- **A:** Only the calls the system under test made while answering the case. Judge calls and
  variant calls are recorded against the session's `--max-cost` total under the case's id, and
  are not part of the per-case ceiling.
- **Why:** The ceiling answers "what does it cost to serve this request", which is a property of
  the application the author is shipping. A judge is the harness measuring the answer, and a
  metamorphic variant is the harness asking the same question a fourth way; folding either into
  the case's ceiling would mean that adding a relation to a test changes what the application is
  reported to cost, and that a suite could be brought under budget by grading less. Both are
  nonetheless real money, which is why they reach the session total: `--max-cost` is what a CI
  owner sets to stop a pull request spending forty dollars, and forty dollars of variants is
  forty dollars. Rejected alternatives: counting everything against the case, which makes the
  per-case figure unusable for capacity planning and couples it to the test's decorators; and
  counting nothing but the case anywhere, which lets a suite of relations run up an unbounded
  bill that no ceiling sees.

## 61. `--runs` is registered with a `--probatio-runs` fallback and a fixed destination

- **Date:** 2026-09-04 (Phase 9)
- **Q:** Spec §3.12 says that if `--runs` collides with another installed plugin at registration,
  fall back to `--probatio-runs` and record it here. How is a collision detected, and how does
  the rest of the code read the value without knowing which name won?
- **A:** `_add_runs_option` tries `--runs` and then `--probatio-runs`, catching the `ValueError`
  pytest's option group raises for a name already added, and both register under the same
  destination, `probatio_runs`. Everything reads `config.getoption("probatio_runs")`, so no
  caller knows or cares. If both names are taken the plugin refuses to configure rather than
  silently running every case once. In this repository's environment no plugin takes `--runs`, so
  the fallback branch is exercised by a unit test against a stub option group rather than by an
  installed collision.
- **Why:** Reading the flag by destination is the difference between one conditional at
  registration and a conditional at every read; it also means a message that quotes the flag can
  quote the one that actually exists. Refusing when both are taken is the DECISIONS 33 rule for
  a store that cannot honour its own promise: a `--runs 5` that was silently ignored reports a
  stability score of nothing over a suite the user believes was measured. Rejected alternative:
  detecting the collision by inspecting the parser's registered options before adding, which
  reaches into pytest's internals to learn what its own exception already says.

## 62. The sanctioned deletion, and the byte-identity gate that now allows exactly it

- **Date:** 2026-09-04 (Phase 9)
- **Q:** `CLAUDE.md`'s gate condition 5 sanctions one edit to `examples/demo_suite/`: the Phase 9
  deletion of the temporary `collect_ignore` import guard at the top of its `conftest.py`. How
  does the gate keep checking everything else?
- **A:** The five lines were deleted, and the repository-level `conftest.py` that repeated the
  exclusion (DECISIONS 16) was deleted with them, in this commit.
  `tests/test_demo_spec.py::test_the_demo_suite_differs_from_its_introducing_commit_by_the_deletion_alone`
  now holds the guard text as a module constant and asserts three things against the Phase 1
  commit: that `conftest.py` is the **only** file that differs, that the guard is present in the
  committed original, and that the working-tree file equals the original with that exact block
  removed once. `git status --porcelain` still has to show no untracked file inside the
  directory. Two Phase 2 tests retired with the guard: the collection test that asserted the
  suite failed to import on the first missing export, and the lifecycle test that asserted the
  repository-level exclusion existed exactly while an export was missing; both were about a
  transitional state that no longer exists, and both are replaced by tests that run the suite.
- **Why:** Comparing a file against "the original minus this literal block" is stricter than
  reading a diff and counting removed lines: a session that deleted the guard *and* changed a
  scripted answer would produce a diff of the permitted shape and fail this check. Keeping the
  guard text in the test rather than deriving it from the diff also means the sanctioned edit is
  written down in executable form, which is what `CLAUDE.md` asks a sanctioned exception to be.
  Rejected alternative: allowing any change to `conftest.py` and byte-comparing the other files,
  which is two lines shorter and unfreezes the file that wires the whole example.

## 63. A verdict is the exact assertions; budgets and snapshots fail the case beside it

- **Date:** 2026-09-04 (Phase 9)
- **Q:** Spec §0 defines a verdict as "the boolean result of a case's exact assertions taken
  together". Spec §3.7 says a budget ceiling fails the build and §3.6 says snapshot drift is a
  failure. Does a case whose latency ceiling was exceeded have a failing *verdict*?
- **A:** No. `CaseResult.verdict` is the assertions and nothing else; `CaseResult.passed` is
  the verdict floor being met **and** no budget ceiling exceeded **and** no snapshot drifted, and
  it is `passed` that decides whether `check` raises. The pass rate, the Wilson interval and every
  relation's violation rate are computed over the verdict.
- **Why:** Spec §0's definition is load-bearing in two places that would otherwise quietly break.
  A relation compares a variant's verdict with the original's, and if a verdict included the
  latency ceiling then a variant that happened to run four milliseconds slower would be reported
  as a metamorphic violation — a claim about the model's semantics drawn from the machine's
  clock. A pass rate would likewise mix model nondeterminism with wall-clock noise, and the
  stability score, which is a mean of pass rates, would move when the CI runner was busy.
  Rejected alternative: one boolean covering everything, which is simpler to explain and makes
  the two headline features measure the harness.

## 64. The reported verdict is the majority verdict, explained by a run that agreed with it

- **Date:** 2026-09-04 (Phase 9)
- **Q:** A case that ran five times has five verdicts and one row in the report. Which one is
  shown, and which run's assertion results are printed beside it?
- **A:** The majority verdict (spec §3.10 defines one per case), and the assertion results of the
  first run that agreed with it.
- **Why:** The first run is the obvious choice and is wrong for exactly the case the demo suite
  exists to show: `flu-antivirals-flaky` fails its first run and passes the other four, so a
  report keyed on run zero would print "0 of 2 assertions passed" on a row marked `pass`. Taking
  the results from a run that agreed with the reported verdict makes the row internally
  consistent in both directions — a failing case is explained by a run that failed. The first run
  is still what the snapshot compares, because spec §3.6 says so and because a baseline has to
  be pinned to something that does not depend on how the majority happened to fall. Rejected
  alternative: showing run zero throughout, which is one fewer concept and prints a self-
  contradicting row.

## 65. `n_below_floor` counts the repeated cases only

- **Date:** 2026-09-04 (Phase 9)
- **Q:** Spec §3.10 defines `n_below_floor` as "the number of cases whose Wilson lower bound
  falls below their floor". Under `--runs 1` every case's lower bound is about 0.21 and every
  default floor is 1.0, so the answer is "all of them", for every suite, always.
- **A:** Count only the cases that ran more than once — the same population the stability score
  averages — and print the count as `N of M`.
- **Why:** A statistic whose value is "all of them" for the default invocation is not a
  statistic, and it sits two lines under a stability score that correctly says "not measured".
  One run supports no interval worth acting on, so counting it claims a measurement that was not
  taken, which is the same rule DECISIONS 8 applies to a relation with no variants and
  DECISIONS 36 to a ceiling with no calls. Printing the denominator matters too: at `--runs 5`
  the honest answer really is "12 of 12", because no finite number of runs proves a rate of
  exactly 1.0, and a reader needs to see what the count is out of before drawing a conclusion
  from it. Rejected alternative: the literal reading, which is defensible and makes the line
  noise in every default run.

## 66. Probatio budgets the calls it can see: its own fixtures, and the completion a SUT returns

- **Date:** 2026-09-04 (Phase 9)
- **Q:** Spec §3.7 says the per-case ceiling is evaluated over "all provider calls the SUT made
  during the case (the `CassetteProvider` records them)". But a suite may hand the system under
  test a provider Probatio never built — the demo suite's `conftest.py` does exactly that
  (DECISIONS 9), substituting its own `FakeProvider`. Where do the calls come from then?
- **A:** From two places, unioned. The `provider` and `judge_provider` fixtures wrap the adapter
  in an observing wrapper that reports every completion to the run state while a case is running;
  and if the system under test **returns** a `Completion` rather than a `str`, that completion
  counts too, unless it is the very object an instrumented provider already reported (compared by
  identity, since `Completion` is frozen). A suite whose system under test uses its own provider
  and returns plain text is reported as having made no calls, which DECISIONS 36 already renders
  as two unenforceable ceilings and a warning rather than as a pass.
- **Why:** The wrapper alone is not enough, because overriding the fixture is a documented and
  necessary thing to do; the returned completion alone is not enough, because a system under test
  that makes three calls and returns text would be budgeted at zero. Together they cover every
  shape a real suite takes, and the failure mode of the gap that remains is loud rather than
  silent. `docs/providers.md`'s cost section and the `check` docstring both say that returning a
  `Completion` is what makes a ceiling enforceable. Rejected alternatives: requiring the system
  under test to use the fixture, which would break the demo suite and forbid a user from testing
  an application that builds its own client; and inspecting the call stack for provider objects,
  which is guesswork dressed as instrumentation.

## 67. `--probatio-junit` and `--probatio-results` are registered and refused

- **Date:** 2026-09-04 (Phase 9)
- **Q:** Spec §3.12 lists both flags and spec §3.12's acceptance criterion says option help text
  lists every flag — but their reporters are Phase 10's. Register them and ignore them, or leave
  them out until the reporters exist?
- **A:** Register them, so `--help` is spec §3.12's whole surface, and raise
  `ProbatioConfigError` from `pytest_configure` when either is given, naming Phase 10. pytest
  reports that as an internal error with a non-zero exit status, which is loud, and the message
  is in the output; a unit test asserts the error and its text directly, and a `pytester` test
  asserts the session fails.
- **Why:** A flag that is accepted and writes nothing is how a CI pipeline ends up green against
  a report that was never produced — the pipeline's own `if [ -f results.json ]` is the thing
  that silently stops firing. Refusing is the same rule as DECISIONS 33's unparsable baseline:
  a promise the tool cannot honour is said out loud. Rejected alternatives: leaving the flags
  unregistered until Phase 10, which fails the acceptance criterion and gives `unrecognized
  arguments` instead of a sentence naming the phase; and accepting them with a warning, which
  is only read by somebody already looking.

**Amended, Phase 10.** Both reporters now exist, so the refusal and `check_unimplemented_options`
are gone; the flags write the files they name. What survives is the reason they were registered at
all — `--help` is spec §3.12's whole surface — and the rule that produced the refusal, which
Phase 10 keeps in a different form: a file a flag asked for is written even when the session
checked no case, because a pipeline told to collect `results.json` has to find one saying "nothing
ran" rather than nothing at all. The refusal's other flaw is fixed here too. A `ProbatioConfigError`
escaping `pytest_configure` was reported as `INTERNALERROR` with a traceback through Probatio's own
frames, which reads as a bug in the plugin rather than as a flag the user got wrong. Every
configure-time check is now wrapped in `plugin.as_usage_error`, which re-raises it as
`pytest.UsageError` with the original as `__cause__` and the message text unchanged. Rejected
alternative: leaving the raise as it was, on the grounds that a traceback is louder — it is louder
about the wrong thing.

## 68. Budget results are recorded into the snapshot baseline

- **Date:** 2026-09-04 (Phase 9)
- **Q:** DECISIONS 38 anticipated this phase putting budget results "next to a case's other
  results", with a `scores` baseline recording `null` for them. Does the baseline's `assertions`
  list actually include `budget_cost` and `budget_latency`?
- **A:** Yes. `check` passes `[*assertion_results, *budget_results]` to `BaselineStore.compare`,
  so a `scores` baseline records both with `score: null` and a `passed` flag.
- **Why:** Because a ceiling that starts failing is drift, and it is the kind of drift a scores
  baseline is for: the case still passes its assertions, the answer still reads fine, and the
  application has started costing twice as much. DECISIONS 38's choice of `None` for the score is
  what makes this safe — a latency that wobbled by two milliseconds records the same `null` it
  recorded last week, so only a flipped verdict is drift. The cost is coupling: adding
  `--probatio-prices` to a run flips an unenforceable ceiling to an enforceable one and re-records
  every baseline once. Rejected alternative: recording only the case's own assertions, which
  keeps the baseline purely about the model's answer and gives up the one mechanism that would
  catch a ceiling silently becoming unenforceable.

## 69. Any non-fake provider must be given a model, not only `claude-cli`

- **Date:** 2026-09-04 (Phase 9)
- **Q:** The Phase 9 brief requires `--probatio-provider claude-cli` without `--probatio-model`
  to be refused at configure time, because a tape whose model is the literal string `claude-cli`
  cannot tell two models apart. `anthropic` has the same shape.
- **A:** Both live providers are refused without a model, and so is a live
  `--probatio-judge-provider` with neither `--probatio-judge-model` nor `--probatio-model` to
  fall back on. `fake` needs nothing.
- **Why:** DECISIONS 43's amendment is the whole argument: the cassette key's model is
  `params["model"] or the adapter's constructor model`, no demo case names a model in `params`,
  and a key that resolves to `None` or to an adapter name replays one model's tape against
  another silently. That reasoning does not mention `claude-cli` anywhere; it is about the key.
  `AnthropicProvider` would additionally fail at call time with an SDK error halfway through a
  session, which is a worse place to learn it. Rejected alternative: refusing only the provider
  the brief names, which leaves the identical hole one flag away.

**Amended, Phase 10.** `check_model_is_named` still raises `ProbatioConfigError` with the same
sentence, and `pytest_configure` now converts it to `pytest.UsageError` through
`plugin.as_usage_error` (see the amendment to DECISIONS 67). The user sees the same words with no
`INTERNALERROR` banner and no traceback above them; a unit test still asserts the
`ProbatioConfigError`, and a `pytester` test asserts that a real session refusing the flag prints
the sentence and does not print `INTERNALERROR`. The same wrapper covers the `--runs` collision of
DECISIONS 61, which is raised from `pytest_addoption`.

## 70. `Probatio` lives in `session.py`, and `plugin.py` holds only the pytest surface

- **Date:** 2026-09-04 (Phase 9)
- **Q:** Spec §3.12 puts the `Probatio` class in its `plugin.py` section, alongside the options,
  the markers and the fixtures.
- **A:** The class and its resolved-settings object live in a new `src/probatio/session.py`;
  `plugin.py` imports and re-exports `Probatio` and holds the four hooks, the fifteen options,
  the two markers and the three fixtures. Spec §3.12's list of what the pytest surface *offers* is
  unchanged.
- **Why:** `check` composes six modules and is the longest function in the package; `plugin.py`
  is loaded by pytest in every session of every project that installs Probatio and is the file a
  reader opens to find out what the flags are. Keeping them apart also makes `check` testable
  without a pytest session at all — `tests/test_session_check.py` builds a `Probatio` from a
  `ProbatioSettings` and a `RunState` and exercises budgets, snapshots, relations and stability
  with no fixture anywhere, which is thirty-eight tests that would otherwise each need a
  `pytester` subprocess. Rejected alternative: one file, as the spec's section headings suggest,
  which is what the spec says and costs a second of subprocess time per behaviour tested.

## 71. The demo suite's three baselines are committed

- **Date:** 2026-09-04 (Phase 9)
- **Q:** `pytest examples/demo_suite` is part of this repository's own `testpaths`, and three of
  its cases declare `snapshot: scores`. The first run records `.probatio/baseline/test_demo/*.json`
  under the rootdir. `.gitignore` deliberately does not ignore `.probatio/`. Commit them or not?
- **A:** Commit them. The demo suite is fully deterministic — a `FakeProvider` with a fixed cost,
  a fixed latency and a scripted answer per case — so the recorded scores are reproducible, and
  from this commit onward the gate compares against them instead of re-recording.
- **Why:** These files are the artefact spec §5 says is committed, and a repository that ships a
  snapshot feature and gitignores its own snapshots is not using it. Committing them turns the
  gate into a real drift check on the example: a change to the trigram backend, to `contains`
  scoring or to the budget results' shape now fails `pytest -q` with a per-assertion table rather
  than passing quietly. The cost is that such a change needs `pytest --update-baseline` and a
  reviewed diff, which is the workflow the feature is for. Rejected alternative: adding
  `.probatio/baseline/test_demo/` to `.gitignore`, which keeps every phase's diff smaller and
  means the one snapshot suite in the repository never actually compares anything.

## 72. A missing or stale tape is warned about in the report as well as raised

- **Date:** 2026-09-04 (Phase 9)
- **Q:** The Phase 9 brief asks for "stale or missing tapes" among the report's warnings, but
  spec §3.8 makes both of them errors that stop the case, and spec §3.12's acceptance requires
  `MissingCassetteError` in the test output.
- **A:** Both. `check` catches `MissingCassetteError` and `StaleCassetteError` around the system
  under test, adds the error's own message to the run state's warnings, and re-raises unchanged.
- **Why:** The two say different things to different readers. The exception is for the developer
  reading the traceback of the case that stopped; the warning is for whoever reads the report of
  a run in which nine cases failed for the same reason, and wants to see that in one block rather
  than nine tracebacks. Re-raising unchanged is what keeps spec §3.12's acceptance criterion
  true and keeps the failure attributable to the case that caused it. Rejected alternative:
  swallowing the error and failing the case through the report, which would make a suite with no
  tapes at all report twelve ordinary assertion failures and bury the one fact that explains them.

## 73. A report entry is keyed on the test's node id and the case's id, not on the case id

- **Date:** 2026-09-04 (Phase 10)
- **Q:** The demo suite routes `htn-definition` to `test_case`, which carries three relations, and
  again to `test_paraphrase`, which carries a fourth; `t2d-metformin` is the same. Both already
  appear twice in the terminal's cases table, where two identical labels are merely confusing. In
  the results JSON and the JUnit file they would collide: a CI tool keyed on `(classname, name)`
  shows one row, and whichever it kept would carry one test's relations and not the other's.
- **A:** `CaseResult` gained a required `node_id`, `collector.case_key(case)` returns
  `(node_id, case_id)`, and that pair is what a per-case entry is identified by. The JUnit file
  writes `classname` = the node id and `name` = the case id. The results JSON is a list and
  carries `node_id` on every entry, so a consumer can key on the same pair. Where one test checks
  one case more than once, the second and later JUnit entries have ` #2`, ` #3` appended to their
  `name` rather than being merged or dropped.
- **Why:** A case id is unique within the directory it was loaded from and nowhere else, which is
  exactly what makes routing one case to several tests a normal thing to do — it is how the demo
  suite says "these three relations apply to every case, and this fourth one only where frozen
  paraphrases exist". The node id is the one string pytest already guarantees is unique within a
  session, it is what a developer clicks in a CI report, and it costs one field. Rejected
  alternatives: keying on `(suite, case_id)`, which is the baseline and cassette key and collides
  for exactly this reason, since both entries are in `test_demo`; and synthesising an index —
  `htn-definition-1`, `htn-definition-2` — which is unique but tells the reader nothing about
  which test produced it and changes when a test is added above it.

## 74. A property that was not measured is omitted from the JUnit file, never written "n/a"

- **Date:** 2026-09-04 (Phase 10)
- **Q:** Spec §3.11 puts one `relation.<name>.violation_rate` property on each case per relation,
  but a relation that is not applicable to a case has no rate at all (spec §3.9, DECISIONS 8), and
  a case whose calls were never priced has no `cost_usd`. A suite in which nothing ran more than
  once has no `stability_score`. Write the property with the value `"n/a"`, or leave it out?
- **A:** Leave it out. The JUnit file carries `pass_rate`, `wilson_low`, `wilson_high` and
  `latency_ms` always; `cost_usd` only where a cost is known; `stability_score` only where
  stability was measured; and one relation property per relation that measured something on that
  case. A reader who needs to tell "not applicable" from "not run" reads the results JSON, where
  `violation_rate: null` sits beside `n_variants: 0`.
- **Why:** Every consumer of this format parses a property value as a number the moment it
  recognises the name, and the two things a string in that position can do are both bad: raise on
  a dashboard that expected a float, or coerce to zero. Zero is the specific lie this project has
  refused since DECISIONS 8 — a relation with no variants has not been shown to hold. An absent
  property is unambiguous in a format that has no null. Rejected alternative: writing `"n/a"`,
  which keeps the property list the same width for every case and hands a parser a value it cannot
  use.

## 75. Numbers in the JUnit file are the shortest string that reads back as the same number

- **Date:** 2026-09-04 (Phase 10)
- **Q:** A pass rate of four in five is 0.8 exactly; a violation rate of one in three is not. What
  goes in a `value=` attribute — a fixed number of decimals, or the float itself?
- **A:** `repr(round(value, 6))`. Four in five writes `0.8`, one in three writes `0.333333`, a
  cost of five hundredths of a cent writes `0.0005`, and a latency writes `100.0`. Six decimals is
  the precision `budget.py` already prints money to.
- **Why:** A fixed `%.2f` would write a pass rate of 0.8 as `0.80`, which is fine to read and
  wrong to compare, and would round a cost of `0.0005` to `0.00` — a ceiling reported as free.
  Full `repr` goes the other way and writes seventeen digits of a third into a dashboard column.
  Rounding first and letting `repr` shorten what is left gives a value that parses back to what
  was rounded and reads like a number a person wrote. Rejected alternative: `%.6f` everywhere,
  which is one character shorter in the source and writes `0.800000` where the acceptance
  criterion asks for `0.8`.

## 76. An unenforceable result goes in the case's `<system-out>`, not its `<failure>`

- **Date:** 2026-09-04 (Phase 10)
- **Q:** Spec §3.7 says an unenforceable cost ceiling is `passed=False` and is **not** a passing
  budget check. A JUnit file has two states for a test case. Which one does it get?
- **A:** Neither. `failures` counts the cases `check` failed, which never includes an
  unenforceable result (`session._summarise_failure` skips them by construction). Every
  unenforceable assertion and ceiling on a case is listed in that case's `<system-out>` block
  under a `unenforceable (N):` heading, so a CI run whose price table is missing shows the reason
  next to each case rather than nowhere.
- **Why:** Failing the build for an unpriced model would make `--probatio-prices` mandatory in
  practice, and the rule exists so that a missing price is visible rather than fatal. Passing
  silently is the failure mode the rule was written against. `<system-out>` is the one place in
  the format for "here is something that happened that is not a verdict", it is displayed by
  every consumer that shows a case's detail, and it leaves the `failures` count meaning what a
  reader assumes it means. Rejected alternatives: a `<skipped>` element, which claims the case did
  not run when it did; and a suite-level property counting them, which loses which case each
  belongs to.

## 77. The two files are written from `pytest_terminal_summary`, beside the markdown one

- **Date:** 2026-09-04 (Phase 10)
- **Q:** `pytest_sessionfinish` is where a session's artefacts would conventionally be written, and
  Probatio already implements it for the `--max-cost` overrun.
- **A:** `write_artefacts` is called from `pytest_terminal_summary`, which is where the markdown
  reporter has been written since Phase 9, and it prints one `probatio: wrote <path>` line per
  file.
- **Why:** All four reporters render the same `RunReport`, and rendering it in two hooks would
  mean two calls to `RunState.report()` at two points in the session, which is one place for the
  numbers in the JUnit file to disagree with the numbers in the terminal — the exact failure the
  shared-report design exists to prevent. The `--max-cost` hook stays where it is because it sets
  an exit status rather than writing a file. The cost is that a run with the terminal reporter
  disabled writes no files; that is also true of Phase 9's markdown reporter, and it is not a
  configuration this project's own gate or CI uses. Rejected alternative: writing the files in
  `pytest_sessionfinish` and printing the paths in the terminal hook, which splits one action
  across two hooks whose relative order pytest does not fix.

## 78. Gate condition 5 needs full history, and says so instead of passing

- **Date:** 2026-09-04 (Phase 10)
- **Q:** CI failed at Gate 1 on two tests that pass locally. `actions/checkout@v4` makes a shallow
  clone, so `git log --diff-filter=A -- examples/demo_suite` finds no commit that adds the
  directory, resolves to HEAD, and the diff against HEAD is empty — which means gate condition 5,
  the byte-identity check `CLAUDE.md` calls a hard constraint, **passed vacuously in CI from
  Phase 1 to Phase 8** and only turned into a failure in Phase 9, when the sanctioned deletion
  first made a real diff expected. Separately, GitHub Actions sets `GITHUB_STEP_SUMMARY`, so the
  markdown reporter correctly writes a job summary and
  `test_write_artefacts_writes_nothing_when_no_flag_names_a_file` correctly observed a written
  file.
- **A:** Both sides of the first are fixed. `.github/workflows/ci.yml` checks out with
  `fetch-depth: 0`, and `test_the_demo_suite_differs_from_its_introducing_commit_by_the_deletion_alone`
  now **fails** when `git rev-parse --is-shallow-repository` prints `true`, with a message that
  says the gate needs full history and names `fetch-depth: 0`. The pass-with-a-note path is kept
  for the two cases where there is genuinely nothing to compare against: git unavailable, and the
  directory not yet committed. For the second, the two tests that assert no artefact was written
  or count the files written — `test_write_artefacts_writes_nothing_when_no_flag_names_a_file` and
  `test_runs_three_writes_both_report_files_with_every_property`, whose subprocess inherits the
  environment — call `monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)`. The reporter is
  unchanged; writing to a job summary the environment names is the behaviour Phase 9 specified.
- **Why:** A check that cannot fail is worse than an absent one, because the run log records it as
  green. `fetch-depth: 0` alone would fix today's CI and leave the same trap for any other
  environment with a truncated checkout, so the test now refuses to report a result it cannot
  compute; the shallow guard is the assertion, `fetch-depth: 0` is what satisfies it. Isolating
  the variable in the test is right for the same reason in reverse: the environment, not the code,
  is what changed, and a test that asserts "nothing was asked for" has to own the environment that
  decides what was asked for. Rejected alternatives: printing a note and returning on a shallow
  clone, which is exactly the vacuous pass being fixed; and making the reporter skip
  `GITHUB_STEP_SUMMARY` under some test-mode flag, which would delete the one feature spec §3.11
  exists for in order to make an unrelated assertion easier.
