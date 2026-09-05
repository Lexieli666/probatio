# Stability: what `--runs` measures, and what it does not

An LLM application is not deterministic. A suite that runs each case once and prints a tick is
asserting something it did not measure: that the case passes, rather than that it passed once.
`--runs N` runs each case N times and reports what happened.

```bash
pytest examples/demo_suite --runs 5
```

## What is reported

Per case:

- **pass rate** — `k/n`, where `k` is the number of runs whose exact assertions all passed.
  Budget ceilings and snapshot drift fail a case without entering this number, because the pass
  rate is a statement about the model's answers.
- **majority verdict** — whether more than half the runs passed. A tie is not a majority.
- **Wilson 95% interval** — a range for the underlying pass rate, given `k` of `n`.
- **floor** — the pass rate the case has to reach: `flaky_tolerant.p` when the test declares one,
  otherwise 1.0.

Per suite:

- **stability score** — the mean pass rate over the cases that ran more than once. A suite in
  which no case was repeated has no stability score at all, rather than a score of 1.0 that would
  read as "measured, and perfect".
- **cases below their floor** — how many of those repeated cases have a Wilson *lower bound*
  under their floor. This is reported and decides nothing; see below.

## Why the Wilson interval, and why it decides nothing

The textbook normal approximation, `p ± z·sqrt(p(1−p)/n)`, has zero width when every run passed:
five green runs would be reported as certainty. The Wilson score interval does not. Five of five
gives roughly `[0.57, 1.00]`; ten of ten roughly `[0.72, 1.00]`. That is the honest reading — a
handful of runs cannot rule out a case that fails one time in ten.

It follows that a case with the default floor of 1.0 has a lower bound under its floor no matter
how well it does, because no finite number of runs proves an underlying rate of exactly 1. So the
bound is reported and **the observed pass rate is what decides the case**. Deciding on the bound
would fail a case for having been run too few times, which is a fact about the invocation and not
about the application.

`probatio` also never calls anything else a "confidence": the only interval in the tool is this
one.

## `@flaky_tolerant(p, n)`

```python
@flaky_tolerant(p=0.8, n=5)
def test_flaky(case, probatio, scripted_provider):
    probatio.check(case, sut=lambda c: answer(c, scripted_provider))
```

The marker declares that the case is allowed to fail some of its runs. `n` overrides `--runs` for
that test, because the rate the author declared was measured over a run length they chose; the
case passes when `pass_rate >= p`. Without the marker, a case under `--runs N` passes only if
every run passed.

This is the honest form of the retry decorators other frameworks ship. A retry hides the failures
and reports a pass; this counts them, prints the rate, and holds the case to a number somebody
wrote down.

## What `--runs` does to fixtures

`--runs N` executes `check` N times **inside one test**, with the same system-under-test callable
and the same fixtures. Function-scoped fixtures are therefore created once and shared across all
N runs.

That is deliberate: what is being measured is the model's nondeterminism, not state leakage
between runs. A fresh fixture per run would also re-run the setup, which for a suite whose
fixtures build an index or open a client would measure the setup instead.

The consequence is worth knowing. If a system under test mutates something a fixture handed it —
appending to a list, advancing a cursor — run 2 sees run 1's mutation. A suite that wants
per-run isolation builds it inside the callable it hands to `check`.

`ScriptedProvider` relies on exactly this: it is created once, and its script advances one entry
per call, which is how "fails the first of five calls" is modelled offline with no randomness
anywhere.

## Snapshots and repeated runs

Under `--runs N` the snapshot compares the **first** run only. A case that needs
`@flaky_tolerant` should therefore use `snapshot: scores`, not `snapshot: output`: scores move
within a tolerance and a flipped verdict is what drift means there, whereas an output baseline
pins one exact string and a nondeterministic case will differ from it on most runs for no reason
worth reporting.

## Relations and repeated runs

Every run evaluates every relation marked on the test, and the reported violation rate is over
all `N × k` variant evaluations rather than a mean of per-run means. A relation that is not
applicable to a case stays not applicable however many times the case runs.

## Cost

Repeating a case repeats its provider calls, so `--runs 5` costs five times as much — unless the
run is replaying committed cassettes, which is the point of recording several samples per
interaction. A tape recorded under `--runs 5` replays five samples and reproduces the pass rate
for nothing; a tape with one sample replayed under `--runs 5` can only report a rate of 0 or 1,
and the report says so.
