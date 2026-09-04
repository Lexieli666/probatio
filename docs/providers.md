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

`cost_usd` is `None`, never `0.0`, when the cost is unknown. A cost ceiling evaluated over a call
with an unknown cost is reported as **unenforceable**, not as passed.

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
SDK accepts work. Token counts come from `usage`. **Cost is always `None`**: the Messages API
reports tokens, not money, and Probatio ships no price list. Pass `client=` to inject anything with
a `messages.create(...)` method; that is how this adapter is tested, with no API key present.

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
> not because it is an invoice.

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
