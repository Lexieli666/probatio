"""``Probatio.check``: the one call a user's test makes, and everything it composes.

Spec §3.12 gives ``check`` one sentence and a lot of work: run the system under test N times,
evaluate the assertions, the budgets, the snapshot and every relation marked on the requesting
test, record all of it in the session collector, and raise a readable ``AssertionError`` when the
case failed. This module is that sentence, plus the settings object that carries the resolved
command-line options so the plugin's hooks stay a list of fixtures.

Four positions are fixed here, each recorded in `DECISIONS.md`.

**A verdict is the exact assertions and nothing else** (spec §0). Budget ceilings and snapshot
drift fail the case, and they do it beside the verdict rather than inside it, so a pass rate is a
statement about the model's answers and a relation's violation rate compares like with like.

**Budgets are per run.** Five runs of a case with a one-cent ceiling are five one-cent cases, not
one five-cent case; any run over the ceiling fails the case.

**A case's budget covers the calls its system under test made.** Judge calls and the calls made
while evaluating a relation's variants are the harness measuring the case, not the case doing its
work, so they do not count against the case's own ceiling — but they are real money and they do
count toward the session total under ``--max-cost``.

**Probatio counts the calls it can see.** That is every call through the ``provider`` and
``judge_provider`` fixtures it built, plus the ``Completion`` a system under test returns. A suite
that hands its own provider to the system under test — as the demo suite does — is measured from
what the system under test returns, which is why returning a ``Completion`` rather than a ``str``
is worth doing.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from .assertions import AssertionResult
from .budget import PriceTable, case_cost, evaluate_budget, price_completions
from .case import LLMCase
from .cassette import CassetteMode
from .collector import CaseResult, RunState, merge_relation_results
from .errors import MissingCassetteError, StaleCassetteError
from .metamorphic import Relation, RelationResult, evaluate_relation
from .providers import Completion, Provider
from .runner import evaluate_case
from .snapshot import BaselineStore, SnapshotResult, prompt_hash
from .stability import CaseStability, FlakyTolerance, case_stability

__all__ = [
    "FAILING_SNAPSHOT_STATES",
    "UNVALIDATED_JUDGE_FIX",
    "Probatio",
    "ProbatioSettings",
    "SutResult",
]

FAILING_SNAPSHOT_STATES: Final = ("prompt_changed", "scores_changed", "output_changed")
"""The three snapshot states that fail a case; the other three are notes (spec §3.6)."""

UNVALIDATED_JUDGE_FIX: Final = "probatio validate-judge --labels <csv> --rubric <name>"
"""The command the unvalidated-judge warning names, as spec §3.5 requires."""

_UNKNOWN_MODEL: Final = "unknown"
"""What a snapshot records when no completion reported a model, rather than guessing one."""


@dataclass(frozen=True)
class ProbatioSettings:
    """The command-line options ``check`` needs, resolved once per session.

    Attributes:
        rootdir: pytest's rootdir; the origin of every relative path (spec §0).
        runs: The ``--runs`` value.
        cassette_mode: The ``--cassette`` mode.
        update_baseline: Whether ``--update-baseline`` was given.
        baseline_dir: Where baselines live.
        prices: The price table from ``--probatio-prices``, or ``None``.
        max_latency_ms: The ``--max-latency`` default for cases declaring no latency ceiling.
        provider_name: The configured provider, named in the record command of a missing tape.
    """

    rootdir: Path
    runs: int = 1
    cassette_mode: CassetteMode = "replay"
    update_baseline: bool = False
    baseline_dir: Path = field(default_factory=lambda: Path(".probatio") / "baseline")
    prices: PriceTable | None = None
    max_latency_ms: float | None = None
    provider_name: str = "fake"

    @property
    def validation_dir(self) -> Path:
        """Where judge validation records live: ``<rootdir>/.probatio/judges`` (spec §5)."""
        return self.rootdir / ".probatio" / "judges"


@dataclass(frozen=True)
class SutResult:
    """What one run of a system under test produced.

    Attributes:
        output: The answer text every assertion is evaluated against.
        completions: Every provider call Probatio saw during the run, in call order.
    """

    output: str
    completions: list[Completion]

    @property
    def model(self) -> str | None:
        """The model that answered, as the first completion reported it."""
        return self.completions[0].model if self.completions else None


class Probatio:
    """The object the ``probatio`` fixture hands a test.

    One method matters. Everything the object holds is what ``check`` needs and cannot work out
    for itself: which suite it is in, which relations the requesting test declared, how many times
    to run, and where the session's state lives.

    Attributes:
        settings: The resolved command-line options.
        state: The session's collector state.
        suite: The test module's stem, which names the baseline and cassette directories.
        node_id: The requesting test's node id, which pairs with a case's id to identify one
            entry in the report (DECISIONS 73).
        relations: The relations marked on the requesting test, in application order.
        tolerance: The test's ``@flaky_tolerant`` declaration, or ``None``.
        rubric_dirs: Where a judge's rubric name is looked for, in order (DECISIONS 23).
    """

    def __init__(
        self,
        *,
        settings: ProbatioSettings,
        state: RunState,
        suite: str,
        node_id: str | None = None,
        judge_provider: Provider | None = None,
        relations: Sequence[Relation] = (),
        tolerance: FlakyTolerance | None = None,
        rubric_dirs: Sequence[Path] | None = None,
    ) -> None:
        """Build the per-test object.

        Args:
            settings: The resolved options.
            state: The session's collector state.
            suite: The test module's stem.
            node_id: The requesting test's node id. Defaults to ``suite``, which is what a
                :class:`Probatio` built outside a pytest session — as every test of ``check``
                builds one — has to identify itself by.
            judge_provider: The provider ``judge`` assertions grade through, or ``None`` to leave
                every judge assertion unenforceable.
            relations: The relations marked on the requesting test.
            tolerance: The test's ``@flaky_tolerant`` declaration.
            rubric_dirs: Directories a rubric name is searched in. Defaults to
                ``[<rootdir>/rubrics]``.
        """
        self.settings = settings
        self.state = state
        self.suite = suite
        self.node_id = node_id if node_id is not None else suite
        self.judge_provider = judge_provider
        self.relations = list(relations)
        self.tolerance = tolerance
        self.rubric_dirs = (
            list(rubric_dirs) if rubric_dirs is not None else [settings.rootdir / "rubrics"]
        )

    # -- the public call -------------------------------------------------------------------

    @property
    def runs(self) -> int:
        """How many times ``check`` will run a case: the tolerance's ``n``, else ``--runs``."""
        return self.tolerance.n if self.tolerance is not None else self.settings.runs

    def check(self, case: LLMCase, sut: Callable[[LLMCase], str | Completion]) -> CaseResult:
        """Run a case, evaluate everything, record it, and fail the test if it should.

        Args:
            case: The case to run.
            sut: The system under test: it takes a case and returns the application's answer,
                either as text or as the :class:`~probatio.providers.Completion` that produced
                it. Returning the completion is what lets a budget ceiling see the call.

        Returns:
            The recorded :class:`~probatio.collector.CaseResult`, so a test can assert on it.

        Raises:
            AssertionError: The case failed: its pass rate did not reach its floor, a budget
                ceiling was exceeded, or a snapshot drifted. Relation violations never raise.
            MissingCassetteError: ``--cassette=replay`` and the case has no tape.
            StaleCassetteError: The tape holds no interaction for the call that was made.
        """
        runs = self.runs
        verdicts: list[bool] = []
        per_run_results: list[list[AssertionResult]] = []
        per_run_budget: list[list[AssertionResult]] = []
        relation_runs: dict[str, list[RelationResult]] = {}
        completions: list[Completion] = []
        snapshot: SnapshotResult | None = None

        for run_index in range(runs):
            verdict, results, sut_result = self._evaluate_run(case, sut, run_index)
            verdicts.append(verdict)
            per_run_results.append(results)
            completions.extend(sut_result.completions)

            budget_results = evaluate_budget(
                case,
                sut_result.completions,
                prices=self.settings.prices,
                default_max_latency_ms=self.settings.max_latency_ms,
            )
            per_run_budget.append(budget_results)
            self.state.budget.record(case.id, case_cost(sut_result.completions, self._prices))

            if run_index == 0:
                snapshot = self._compare_snapshot(case, results, budget_results, sut_result)

            measured_relations = self._evaluate_relations(case, sut, verdict, results, run_index)
            for name, measured in measured_relations.items():
                relation_runs.setdefault(name, []).append(measured)

        stability = case_stability(verdicts, tolerance=self.tolerance)
        relations = [merge_relation_results(each) for each in relation_runs.values()]
        failure = self._summarise_failure(
            case, stability, per_run_results, per_run_budget, snapshot
        )
        priced = price_completions(completions, self._prices)
        shown = _representative(verdicts, stability.majority_verdict)
        result = CaseResult(
            case_id=case.id,
            node_id=self.node_id,
            suite=self.suite,
            verdict=stability.majority_verdict,
            passed=failure is None,
            results=per_run_results[shown],
            budget_results=per_run_budget[shown],
            cost_usd=case_cost(priced),
            latency_ms=sum(completion.latency_ms for completion in priced),
            model=priced[0].model if priced else None,
            snapshot=snapshot,
            stability=stability,
            relations=relations,
            tags=list(case.tags),
            failure=failure,
        )
        self._collect_warnings(result)
        self.state.record(result)
        if failure is not None:
            raise AssertionError(failure)
        return result

    # -- one run ---------------------------------------------------------------------------

    @property
    def _prices(self) -> PriceTable | None:
        """The session's price table, or ``None`` when ``--probatio-prices`` was not given."""
        return self.settings.prices

    def _evaluate_run(
        self, case: LLMCase, sut: Callable[[LLMCase], str | Completion], run_index: int
    ) -> tuple[bool, list[AssertionResult], SutResult]:
        """Run the system under test once and evaluate the case's exact assertions."""
        with self._active_case(case, run_index):
            sut_result = self._call_sut(case, sut)
            results = evaluate_case(
                case,
                sut_result.output,
                judge_provider=self.judge_provider,
                base_dir=self.settings.rootdir,
                rubric_dirs=self.rubric_dirs,
                validation_dir=self.settings.validation_dir,
            )
        return all(result.passed for result in results), results, sut_result

    @contextmanager
    def _active_case(self, case: LLMCase, run_index: int) -> Iterator[None]:
        """Attribute every provider call made inside the block to one run of one case.

        The block covers the system under test **and** the assertions, because a ``judge``
        assertion is a provider call and a call with no active case belongs to no tape
        (DECISIONS 90). A variant opens the block under the original case's id, which is also
        its own: ``with_field`` copies a case without renaming it, so one case's tape holds the
        interactions of every variant taken from it.

        Args:
            case: The case, or the variant, whose id the calls are filed under.
            run_index: The zero-based run number; ``--runs N`` opens the block N times.

        Yields:
            Nothing; the context is held on the cassette store.
        """
        store = self.state.store
        store.begin_case(self.suite, case.id, run_index)
        try:
            yield
        finally:
            store.end_case()

    def _call_sut(self, case: LLMCase, sut: Callable[[LLMCase], str | Completion]) -> SutResult:
        """Run the system under test and collect the calls it made, and only those."""
        sink: list[Completion] = []
        previous = self.state.sink
        self.state.sink = sink
        try:
            returned = sut(case)
        except (MissingCassetteError, StaleCassetteError) as exc:
            self.state.warn(str(exc))
            raise
        finally:
            self.state.sink = previous
        return _normalise(returned, sink)

    # -- the pieces around the run -----------------------------------------------------------

    def _compare_snapshot(
        self,
        case: LLMCase,
        results: Sequence[AssertionResult],
        budget_results: Sequence[AssertionResult],
        sut_result: SutResult,
    ) -> SnapshotResult | None:
        """Compare the first run against the baseline, recording one when there is none."""
        store = BaselineStore(self.settings.baseline_dir, root=self.settings.rootdir)
        return store.compare(
            suite=self.suite,
            case=case,
            prompt_hash=prompt_hash(case),
            results=[*results, *budget_results],
            output=sut_result.output,
            model=sut_result.model or _UNKNOWN_MODEL,
            update=self.settings.update_baseline,
        )

    def _evaluate_relations(
        self,
        case: LLMCase,
        sut: Callable[[LLMCase], str | Completion],
        verdict: bool,
        results: Sequence[AssertionResult],
        run_index: int,
    ) -> dict[str, RelationResult]:
        """Evaluate every marked relation on one run, reusing the same system under test."""
        if not self.relations:
            return {}

        def evaluate(variant: LLMCase) -> tuple[bool, Sequence[AssertionResult]]:
            with self._active_case(variant, run_index):
                sut_result = self._call_variant(variant, sut)
                variant_results = evaluate_case(
                    variant,
                    sut_result.output,
                    judge_provider=self.judge_provider,
                    base_dir=self.settings.rootdir,
                    rubric_dirs=self.rubric_dirs,
                    validation_dir=self.settings.validation_dir,
                )
            return all(item.passed for item in variant_results), variant_results

        return {
            relation.name: evaluate_relation(
                relation,
                case,
                original_verdict=verdict,
                original_results=results,
                evaluate=evaluate,
            )
            for relation in self.relations
        }

    def _call_variant(
        self, variant: LLMCase, sut: Callable[[LLMCase], str | Completion]
    ) -> SutResult:
        """Run one variant. Its calls reach the session total but not the case's own ceiling."""
        sink: list[Completion] = []
        previous = self.state.sink
        self.state.sink = sink
        try:
            returned = sut(variant)
        finally:
            self.state.sink = previous
        result = _normalise(returned, sink)
        self.state.budget.record(variant.id, case_cost(result.completions, self._prices))
        return result

    # -- the verdict, and the sentence that explains it ---------------------------------------

    def _summarise_failure(
        self,
        case: LLMCase,
        stability: CaseStability,
        per_run_results: Sequence[Sequence[AssertionResult]],
        per_run_budget: Sequence[Sequence[AssertionResult]],
        snapshot: SnapshotResult | None,
    ) -> str | None:
        """Return the ``AssertionError`` text, or ``None`` when the case passed."""
        lines: list[str] = []
        if not stability.met_floor:
            lines.append(_verdict_line(case, stability))
            lines.extend(_failed_assertion_lines(per_run_results))
        over_budget = [
            result
            for results in per_run_budget
            for result in results
            if not result.passed and not result.unenforceable
        ]
        if over_budget:
            lines.append(f"{case.id}: {len(over_budget)} budget ceiling(s) exceeded")
            lines.extend(f"  {result.assertion_type}: {result.detail}" for result in over_budget)
        if snapshot is not None and snapshot.state in FAILING_SNAPSHOT_STATES:
            lines.append(f"{case.id}: snapshot {snapshot.state}")
            lines.append(_indent(snapshot.detail))
        return "\n".join(lines) if lines else None

    def _collect_warnings(self, result: CaseResult) -> None:
        """Add this case's unenforceable checks and unvalidated judges to the report."""
        unvalidated = sum(
            1
            for item in result.results
            if item.assertion_type == "judge"
            and item.unenforceable
            and "not been validated" in item.detail
        )
        if unvalidated:
            self.state.warn(
                f"{result.case_id}: {unvalidated} judge verdict(s) from a rubric with no "
                f"validation record (run: {UNVALIDATED_JUDGE_FIX})"
            )
        for item in result.budget_results:
            if item.unenforceable:
                self.state.warn(f"{result.case_id}: {item.detail}")


def _normalise(returned: str | Completion, observed: Sequence[Completion]) -> SutResult:
    """Turn a system under test's return value and the calls it made into one result.

    A ``str`` gives the output and no completion of its own; a ``Completion`` gives both, and is
    counted once even when an instrumented provider already recorded the very same object.
    """
    completions = list(observed)
    if isinstance(returned, Completion):
        if not any(completion is returned for completion in completions):
            completions.append(returned)
        return SutResult(output=returned.text, completions=completions)
    return SutResult(output=returned, completions=completions)


def _representative(verdicts: Sequence[bool], reported: bool) -> int:
    """Return the index of the first run that agreed with the reported verdict.

    A case that passes four runs in five should be explained in the report by a run that passed,
    and one that fails by a run that failed; showing run zero regardless would put "0 of 2
    assertions passed" next to a case the suite let through.
    """
    for index, verdict in enumerate(verdicts):
        if verdict == reported:
            return index
    return 0


def _verdict_line(case: LLMCase, stability: CaseStability) -> str:
    """Render the headline: what the case did, over how many runs, against what floor."""
    if stability.runs == 1:
        failed = "verdict failed"
    else:
        failed = (
            f"pass rate {stability.pass_rate:.2f} ({stability.passes}/{stability.runs}) "
            f"is below the floor {stability.floor:.2f}; "
            f"95% Wilson [{stability.wilson_low:.2f}, {stability.wilson_high:.2f}]"
        )
    return f"{case.id}: {failed}"


def _failed_assertion_lines(per_run_results: Sequence[Sequence[AssertionResult]]) -> list[str]:
    """One line per failed assertion, from the first run that failed."""
    for results in per_run_results:
        failed = [result for result in results if not result.passed]
        if failed:
            return [f"  {result.assertion_type}: {result.detail}" for result in failed]
    return []


def _indent(text: str) -> str:
    """Indent every line of a detail by two spaces, so a diff reads as one block."""
    return "\n".join(f"  {line}" for line in text.splitlines())
