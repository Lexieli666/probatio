"""Per-session run state: what every case did, kept on a stack because pytester nests sessions.

Every reporter renders the same :class:`RunReport`, and this module is the only place that builds
one. ``pytest_configure`` pushes a fresh :class:`RunState` and ``pytest_unconfigure`` pops it, so
a ``pytester`` suite running inside this repository's own suite fills its own report and leaves
the outer session's untouched — without which the gate's demo-suite test would append ten cases to
the report of the run that invoked it.

Two things live here rather than in the plugin, because both are arithmetic and neither needs a
pytest session to test: the aggregation of one relation's results across a case's runs, and the
roll-up of per-case results into the suite's tables.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from .assertions import AssertionResult
from .budget import SuiteBudget
from .cassette import CassetteStore
from .metamorphic import Flip, RelationResult
from .providers import Completion
from .snapshot import SnapshotResult
from .stability import CaseStability, SuiteStability, suite_stability

__all__ = [
    "CaseKey",
    "CaseResult",
    "RelationSummary",
    "RunReport",
    "RunState",
    "case_key",
    "current_state",
    "merge_relation_results",
    "pop_state",
    "push_state",
    "state_depth",
]


class CaseResult(BaseModel):
    """Everything one case did in one session.

    Attributes:
        case_id: The case's id.
        node_id: The node id of the test function that checked it. Two test functions may check
            the same case — the demo suite's ``htn-definition`` is checked by ``test_case`` and
            again by ``test_paraphrase`` — so the case id alone does not identify an entry and
            :func:`case_key` pairs the two (DECISIONS 73).
        suite: The test module's stem, which is also the baseline and cassette directory.
        verdict: The case's verdict: whether the exact assertions passed, taken over the
            majority of its runs (spec §0, §3.10). Budget ceilings and snapshot drift fail the
            case without changing this.
        passed: Whether ``check`` let the case through: the verdict floor was met, no budget
            ceiling was exceeded and no snapshot drifted.
        results: The assertion results of the first run that agreed with ``verdict``, in
            declaration order — so a case that passes four runs in five is explained by a run
            that passed, and one that fails is explained by a run that failed.
        budget_results: That same run's budget results.
        cost_usd: The total cost of every provider call Probatio saw for this case, across all
            runs, or ``None`` when any of them was unpriced.
        latency_ms: The total latency of those calls.
        model: The model that answered, as the first completion reported it.
        snapshot: The snapshot comparison of the first run, or ``None`` for a case whose
            ``snapshot`` is ``off``.
        stability: The pass rate, interval and floor over every run.
        relations: One entry per relation marked on the test, aggregated over every run.
        tags: The case's tags, carried into the report.
        failure: The summary ``check`` raised, or ``None`` when it did not.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    node_id: str
    suite: str
    verdict: bool
    passed: bool
    results: list[AssertionResult] = Field(default_factory=list)
    budget_results: list[AssertionResult] = Field(default_factory=list)
    cost_usd: float | None = None
    latency_ms: float = 0.0
    model: str | None = None
    snapshot: SnapshotResult | None = None
    stability: CaseStability
    relations: list[RelationResult] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    failure: str | None = None


CaseKey = tuple[str, str]
"""What identifies one per-case entry in a report: the test's node id and the case's id."""


def case_key(case: CaseResult) -> CaseKey:
    """Return the identity of one per-case entry.

    A case id is unique within the YAML directory it was loaded from and nowhere else: a suite
    may route the same case to two test functions, as the demo suite routes ``htn-definition``
    to both ``test_case`` and ``test_paraphrase``, and each of those is its own entry with its
    own relations and its own pass rate. Pairing the case id with the node id of the test that
    checked it is what keeps the results JSON and the JUnit file from folding the two together
    (DECISIONS 73).

    Args:
        case: The recorded case.

    Returns:
        ``(node_id, case_id)``.
    """
    return (case.node_id, case.case_id)


class RelationSummary(BaseModel):
    """One relation's results across every case it was applied to.

    Attributes:
        relation: The relation's name.
        n_cases: How many cases it was applicable to and measured something on.
        n_not_applicable: How many cases it observed nothing about (spec §3.9, DECISIONS 8).
        n_variants: Total variants evaluated, over every case and every run.
        n_violations: How many of them flipped the verdict.
        mean_violation_rate: The mean of the per-case rates, over the applicable cases only, or
            ``None`` when there were none.
        worst_case_id: The applicable case with the highest rate, ties broken by case id.
        worst_violation_rate: That case's rate.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    relation: str
    n_cases: int = Field(ge=0)
    n_not_applicable: int = Field(ge=0)
    n_variants: int = Field(ge=0)
    n_violations: int = Field(ge=0)
    mean_violation_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    worst_case_id: str | None = None
    worst_violation_rate: float | None = Field(default=None, ge=0.0, le=1.0)


class RunReport(BaseModel):
    """The whole session, as every reporter receives it.

    Attributes:
        cases: One entry per case checked, in the order they completed.
        relations: One entry per relation any case used, by name.
        stability: The suite's stability score and floor count.
        runs: The ``--runs`` value the session was invoked with.
        cost_total_usd: The total known cost across the session, or ``None`` when no call in it
            was priced at all. Never ``0.0`` for a run that spent an unknown amount (DECISIONS
            39): a reporter cannot tell a free run from an unpriced one once the two share a
            number.
        cost_ceiling_usd: The ``--max-cost`` ceiling, or ``None``.
        cost_unknown_case_ids: Cases whose cost could not be totalled, so the total is a lower
            bound rather than the figure.
        cost_exceeded: Whether the total is over the ceiling.
        warnings: One line per thing the run could not enforce or could not measure.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    cases: list[CaseResult] = Field(default_factory=list)
    relations: list[RelationSummary] = Field(default_factory=list)
    stability: SuiteStability = Field(default_factory=SuiteStability)
    runs: int = 1
    cost_total_usd: float | None = None
    cost_ceiling_usd: float | None = None
    cost_unknown_case_ids: list[str] = Field(default_factory=list)
    cost_exceeded: bool = False
    warnings: list[str] = Field(default_factory=list)

    @property
    def n_failed(self) -> int:
        """How many cases ``check`` failed."""
        return sum(1 for case in self.cases if not case.passed)


def merge_relation_results(results: Sequence[RelationResult]) -> RelationResult:
    """Combine one relation's results for one case across that case's runs.

    Spec §3.9 says the reported rate is over all ``N × k`` variant evaluations, so the counts are
    summed and the rate is recomputed from the totals rather than averaged. A relation that was
    not applicable in any run stays not applicable.

    Args:
        results: The per-run results, all for the same relation and the same case.

    Returns:
        One result carrying the totals and every flip, in run order.

    Raises:
        ValueError: The sequence is empty, so there is nothing to merge.
    """
    if not results:
        raise ValueError("merge_relation_results needs at least one result")
    variants = sum(result.n_variants for result in results)
    violations = sum(result.n_violations for result in results)
    flips: list[Flip] = [flip for result in results for flip in result.flips]
    return RelationResult(
        relation=results[0].relation,
        case_id=results[0].case_id,
        n_variants=variants,
        n_violations=violations,
        violation_rate=violations / variants if variants else None,
        flips=flips,
    )


def _summarise_relations(cases: Sequence[CaseResult]) -> list[RelationSummary]:
    """Roll every case's relation results up into one row per relation, sorted by name."""
    by_name: dict[str, list[RelationResult]] = {}
    for case in cases:
        for result in case.relations:
            by_name.setdefault(result.relation, []).append(result)

    summaries: list[RelationSummary] = []
    for name in sorted(by_name):
        results = by_name[name]
        applicable = [r for r in results if r.violation_rate is not None]
        rates = [(r.violation_rate or 0.0, r.case_id) for r in applicable]
        worst = max(rates, key=lambda pair: (pair[0], _reverse(pair[1]))) if rates else None
        summaries.append(
            RelationSummary(
                relation=name,
                n_cases=len(applicable),
                n_not_applicable=len(results) - len(applicable),
                n_variants=sum(r.n_variants for r in results),
                n_violations=sum(r.n_violations for r in results),
                mean_violation_rate=(
                    sum(rate for rate, _ in rates) / len(rates) if rates else None
                ),
                worst_case_id=worst[1] if worst else None,
                worst_violation_rate=worst[0] if worst else None,
            )
        )
    return summaries


class _Reversed:
    """A comparison key that orders strings backwards, so ``max`` breaks ties by the first id."""

    __slots__ = ("value",)

    def __init__(self, value: str) -> None:
        self.value = value

    def __lt__(self, other: _Reversed) -> bool:
        return self.value > other.value


def _reverse(value: str) -> _Reversed:
    """Wrap a case id so that ``max`` prefers the alphabetically first one on a tie."""
    return _Reversed(value)


class RunState:
    """One pytest session's accumulated state.

    Attributes:
        runs: The ``--runs`` value, carried into the report.
        store: The session's cassette store, so notes and the recorded-key set survive the whole
            run rather than one test.
        budget: The suite cost accumulator.
        cases: The case results recorded so far, in completion order.
        warnings: Report warnings, de-duplicated and in first-seen order.
        sink: Where an instrumented provider appends the completions of the call in progress, or
            ``None`` outside a case.
    """

    def __init__(
        self,
        *,
        runs: int = 1,
        store: CassetteStore | None = None,
        budget: SuiteBudget | None = None,
    ) -> None:
        """Open an empty state.

        Args:
            runs: The ``--runs`` value.
            store: The session's cassette store; a default one is built when none is given.
            budget: The suite cost accumulator; an unbounded one is built when none is given.
        """
        self.runs = runs
        self.store = store if store is not None else CassetteStore()
        self.budget = budget if budget is not None else SuiteBudget()
        self.cases: list[CaseResult] = []
        self.warnings: list[str] = []
        self.sink: list[Completion] | None = None

    def warn(self, message: str) -> None:
        """Add a report warning, ignoring one that has already been said.

        Args:
            message: The line to print under "warnings".
        """
        if message not in self.warnings:
            self.warnings.append(message)

    def record(self, result: CaseResult) -> None:
        """Add one finished case to the session.

        Args:
            result: What the case did.
        """
        self.cases.append(result)

    def observe(self, completion: Completion) -> None:
        """Record a provider call made while a case's system under test was running.

        Args:
            completion: The call's completion. Outside a case this does nothing, so a provider
                used in a fixture or a helper does not land on whichever case ran last.
        """
        if self.sink is not None:
            self.sink.append(completion)

    def report(self) -> RunReport:
        """Build the report every reporter renders.

        Returns:
            The finished :class:`RunReport`. Building it twice gives the same answer; nothing
            here mutates the state.
        """
        for note in self.store.notes:
            self.warn(note)
        return RunReport(
            cases=list(self.cases),
            relations=_summarise_relations(self.cases),
            stability=suite_stability(case.stability for case in self.cases),
            runs=self.runs,
            cost_total_usd=(self.budget.total_usd if self.budget.known_case_ids else None),
            cost_ceiling_usd=self.budget.max_cost_usd,
            cost_unknown_case_ids=list(self.budget.unknown_case_ids),
            cost_exceeded=self.budget.exceeded,
            warnings=list(self.warnings),
        )


_STACK: Final[list[RunState]] = []
"""The session stack. ``pytester`` nests sessions, so the current state is the innermost one."""


def push_state(state: RunState) -> RunState:
    """Make ``state`` the current session's state.

    Args:
        state: The state to push.

    Returns:
        ``state``, so a caller can keep it.
    """
    _STACK.append(state)
    return state


def pop_state() -> RunState | None:
    """Discard the innermost session's state.

    Returns:
        The state that was popped, or ``None`` when the stack was already empty — which happens
        when a session was configured before Probatio was installed and is not worth an error.
    """
    return _STACK.pop() if _STACK else None


def current_state() -> RunState | None:
    """Return the innermost session's state.

    Returns:
        The state, or ``None`` outside a configured session.
    """
    return _STACK[-1] if _STACK else None


def state_depth() -> int:
    """Return how many sessions are on the stack; one outside ``pytester``."""
    return len(_STACK)
