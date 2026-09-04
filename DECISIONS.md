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
