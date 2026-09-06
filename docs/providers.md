# Providers

Everything in Probatio that talks to a model goes through one protocol. There are three adapters
in the box, and adding a fourth is one class.

```python
class Provider(Protocol):
    name: str
    def complete(self, prompt: str, *, system: str | None = None, **params: Any) -> Completion: ...
```

`prompt` is the user-turn text. Multi-turn conversation is out of scope for v0.1: a system under
test that keeps a history flattens it into the prompt it sends.

A `Completion` carries the answer and what is known about the call:

| field | meaning |
|---|---|
| `text` | the response text |
| `model` | the model that produced it, as reported or as asked for |
| `tokens_in`, `tokens_out` | token counts, or `None` when the provider does not report them |
| `cost_usd` | cost in US dollars, or `None` when nobody priced the call |
| `latency_ms` | wall-clock duration of the call |
| `raw` | the provider's own payload, carried for the record and never inspected by Probatio |

## Cost semantics

`cost_usd` is `None`, never `0.0`, when the cost is unknown. This is the load-bearing rule of the
whole budget layer: a zero that means "unknown" makes every `max_cost_usd` ceiling pass forever,
so a cost ceiling evaluated over a call whose cost is unknown is reported as **unenforceable** and
never as passed. It fails, it is listed under warnings, and its detail names the model nobody
priced (`budget.py`, spec §3.7). The same holds for a case that recorded no provider calls at all:
both its cost and its latency ceiling are unenforceable, because the sum of nothing is inside
every ceiling and a check that cannot fail is not a check.

There are three ways a completion comes to carry a cost.

1. **A price table prices it from its tokens.** `PriceTable` loads a YAML mapping of model name to
   `{input_per_mtok, output_per_mtok}` — the file is yours, `examples/prices.example.yaml` shows
   the shape and ships no numbers — and `pytest --probatio-prices prices.yaml` applies it. It
   prices a completion only when `cost_usd` is still `None` and both token counts are known.
   A model that is not in the table is not priced, which leaves the ceiling unenforceable rather
   than guessing.
2. **`AnthropicProvider` prices it at completion time**, if it was constructed with a table. Same
   arithmetic, applied where the tokens are freshest, so a tape recorded through the adapter
   carries the price that was in force when it was recorded.
3. **The provider reported one.** Only `ClaudeCLIProvider` does, and a price table never
   overwrites it — see the caveat below, which is the reason that figure is treated as evidence
   rather than as an invoice.

### The Claude CLI's `total_cost_usd` overstates the answer

The CLI's `total_cost_usd` is the **notional API price** of the turn, not money billed to a plan,
and it is the price of *everything the CLI did*, not of the answer alone. The captured payload in
`tests/fixtures/claude_cli_payload.json` shows this directly: `total_cost_usd` is **$0.003769**,
while the model that produced the answer accounts for **$0.002695** of it in `modelUsage`. The
remaining **$0.001074** belongs to a second, smaller model that appears there because the CLI
bills its own side work — topic detection and the like — to a cheap model alongside the one that
answered. So a `max_cost_usd` ceiling checked against this figure is enforceable but pessimistic:
it charges the answer for work the answer did not do, and the same prompt through the Messages API
with a price table would come out lower. `tests/test_docs_providers.py` reads all three numbers
back out of that fixture, so they are measurements rather than prose.

## `FakeProvider` and `ScriptedProvider`

The two offline adapters. They are what Probatio's own suite and `examples/demo_suite/` use, and
they never touch a network or read an API key.

```python
FakeProvider(responses=None, default=None, cost_usd=None, latency_ms=0.0, model="fake-1")
```

A prompt is answered by the first of these that produces something:

1. `responses[FakeProvider.call_key(prompt, system, params)]` — an exact match on the whole call.
2. `responses[k]` for the first key `k`, in insertion order, that is a substring of the prompt.
3. `default`, called with the prompt if it is callable, so a fake judge can grade by inspection.
4. `FAKE(<stable_hash of the prompt>)`, a stable, obviously synthetic fallback.

`calls` and `call_count` record what the system under test actually sent. `ScriptedProvider(script=[...])`
returns a fixed sequence in order, cycling, which is how a flaky model is modelled without
randomness: a five-entry script whose first entry fails gives a pass rate of exactly 0.8 under
`--runs 5`.

## `AnthropicProvider`

Requires the optional extra:

```bash
pip install 'probatio-llm[anthropic]'
```

Importing `probatio.providers.anthropic` without it raises `ProbatioConfigError` naming that
command. `import probatio` never imports this module, so a user who does not use it does not need
the extra.

```python
AnthropicProvider(model="claude-opus-5", client=None, max_tokens=1024)
```

`system` and the prompt become one user message; every parameter other than `model` is forwarded
to `messages.create` unchanged, so `temperature`, `top_p`, `stop_sequences` and anything else the
SDK accepts work. Token counts come from `usage`. **Cost is `None` unless you pass a price
table**: the Messages API reports tokens, not money, and Probatio ships no price list, so
`AnthropicProvider(prices=PriceTable.load("prices.yaml"))` is what makes a `max_cost_usd` ceiling
over this adapter enforceable. Pass `client=` to inject anything with a `messages.create(...)`
method; that is how this adapter is tested, with no API key present.

## `ClaudeCLIProvider`

Runs the Claude Code CLI as a subprocess, so a developer on a Claude plan can record cassettes and
freeze variants **without an API key**:

```bash
pytest examples/demo_suite --probatio-provider claude-cli --probatio-model <model> \
       --cassette=record --cassette-dir build/cassettes
```

Each call runs

```
claude -p <prompt> --output-format json --no-session-persistence \
       [--model M] [--system-prompt S] --tools ""
```

with an empty temporary directory as the working directory and a 120-second timeout. `--tools ""`
disables all built-in tools, and with no tools the run is a single turn — which is how "one turn"
is obtained on a version of the CLI that has no `--max-turns`. Every flag name, the executable and
the timeout are constructor arguments, so a rename in the CLI is a one-line override.

### `--probatio-timeout`

`ClaudeCLIProvider.timeout_s` defaults to `DEFAULT_TIMEOUT_S`, 120 seconds, and a call that
overruns it fails the case with `the Claude CLI did not answer within 120s`. It has been a
constructor argument since the adapter was written, but until Phase 13's predecessor no flag
reached the constructor, so a developer recording on a throttled plan had no way to raise it
without writing their own `provider` fixture:

```bash
pytest examples/consilium/live --probatio-provider claude-cli \
       --probatio-model <model> --probatio-timeout 600 --cassette=record
```

The value reaches whichever adapter is built for the session and is ignored by the two that cannot
time out. **It is not part of a cassette key**: how long a call was allowed to take is a fact about
the machine that recorded the tape, not about what was asked, so a tape recorded under
`--probatio-timeout 600` is indistinguishable from one recorded under the default and replays the
same either way (`DECISIONS.md` entry 95).

### What recording a real suite through this adapter cost

The observations below are from Phase 12, the only phase of this project that called a model:
about 940 live calls in one day, all through this adapter, recorded in `PROGRESS.md`. They are
here because each of them reads as a Probatio bug the first time it is met, and none of them is.

**Roughly one judge reply in eight is not JSON.** Grading Consilium's forty-row label samples
produced replies whose `verdict` and `score` were complete and whose `rationale` string stopped
mid-sentence, so the reply did not parse at all rather than parsing to a wrong verdict. One
captured reply is committed at `tests/fixtures/claude_cli_truncated_judge_reply.txt`; it is 400
characters long, and `json.loads` on it raises `Unterminated string starting at: line 1 column
49`, column 49 being where the rationale opens. The two runs that completed needed **8 of 40** and
**5 of 40** rows asked again: the sample-1 validation record under
`examples/consilium/live/results/judges-sample-1/` holds the first as `rows_reasked`, and
`PROGRESS.md` quotes the second run's summary verbatim.
`probatio validate-judge --run-judge` therefore re-asks a row rather than propagating the failure,
at most `cli.JUDGE_ATTEMPTS = 3` times, and writes the count into the validation record beside the
kappa. The long inputs are what provokes it: those rows carry about 23,500 characters of context
each, against about 10,000 for a live case.

**The CLI can exit 1 with an empty stderr, mid-run.** One forty-row grading run stopped with
`the Claude CLI exited 1 for 'claude -p'; stderr: <empty>` on a call indistinguishable from the
ones before and after it. `ProbatioConfigError` carries the stderr precisely so that an empty one
is visible as an empty one; there is nothing the adapter can do about it, and a caller who wants
to survive it re-runs the command.

**The default timeout is not generous enough for a long day.** After roughly 600 calls, a single
call against `claude-opus-5` was taking 40 to 90 seconds where it had taken 12, and the occasional
one exceeded 120. One case of the live suite failed three times running on the timeout and
recorded on the next attempt under `--probatio-timeout 600`.
`docs/EVALUATION.md` §5 has the per-attempt record for all of this.

Two things this adapter does not do, both deliberate (`DECISIONS.md` entry 14):

- **It does not pass `--bare`.** That flag skips `CLAUDE.md` discovery, which is wanted, but it
  also forces authentication to `ANTHROPIC_API_KEY`, which defeats the purpose of the adapter.
  Project context is excluded by the empty working directory instead. Note that user-level
  configuration outside that directory still applies, so a recorded tape is reproducible from the
  tape, not from another machine's account.
- **It cannot honour sampling parameters.** This CLI version exposes no `temperature` and no
  `top_p`. Such parameters are listed under `raw["probatio_ignored_params"]` rather than dropped
  in silence, and they still take part in the cassette key, so the tape records what the case
  asked for.

> **The cost this adapter reports is not money you were billed.** `total_cost_usd` in the CLI's
> payload is the **notional API price** of the turn as the CLI computes it. A developer running on
> a Claude subscription is not charged that amount. It is reported because it is the only cost
> signal available, and it makes a `max_cost_usd` ceiling enforceable rather than unenforceable —
> not because it is an invoice. It also covers the CLI's own side calls, so it overstates the
> answer's price; see [Cost semantics](#cost-semantics) for the numbers.

A non-zero exit, unparsable stdout, or a payload reporting an error raises `ProbatioConfigError`
with the CLI's stderr included.

## Adding a provider

One class, no base class, no registration needed to use it directly from a fixture:

```python
class MyGatewayProvider:
    name = "my-gateway"

    def __init__(self, client, model: str) -> None:
        self._client, self._model = client, model

    def complete(self, prompt: str, *, system: str | None = None, **params: Any) -> Completion:
        started = time.perf_counter()
        answer = self._client.ask(prompt, system=system, **params)
        return Completion(
            text=answer.text,
            model=self._model,
            tokens_in=answer.tokens_in,
            tokens_out=answer.tokens_out,
            cost_usd=None,                       # None, not 0.0, unless you really priced it
            latency_ms=(time.perf_counter() - started) * 1000.0,
            raw={"id": answer.id},
        )
```

Override the `provider` fixture in your own `conftest.py` to return it, exactly as
`examples/demo_suite/conftest.py` overrides it with a scripted fake. Cassette recording, replay,
budgets and the relations all work through the protocol, so none of them need to know it exists.
