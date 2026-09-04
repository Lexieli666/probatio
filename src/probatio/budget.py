"""``budget.py``: cost and latency ceilings, and the rule that keeps a cost ceiling honest.

A budget is the one assertion in Probatio that is about the run rather than the answer, and it is
the one where a missing measurement is dangerous rather than merely unhelpful. A latency is always
known: the provider ran, and the wall clock said how long it took. A cost usually is not. The
Messages API reports tokens, not money; a fake reports whatever it was constructed with; the
Claude CLI reports a notional price that is not an invoice. So spec §3.7 splits the two:

- **Latency is enforceable wherever a call was made.** The sum of ``latency_ms`` over the calls
  a case made is compared with the case's ceiling, or with ``--max-latency`` when the case
  declares none; the clock always answered, so no price file is needed to check it.
- **A cost ceiling over an unpriced call is unenforceable, and is never a pass.** It comes back as
  an :class:`~probatio.assertions.AssertionResult` with ``passed`` false and ``unenforceable``
  true, naming the model nobody priced, so the report says "this ceiling checked nothing" instead
  of printing a green tick over an unmeasured number. This is the whole reason
  :attr:`~probatio.providers.Completion.cost_usd` is ``None`` rather than ``0.0`` when unknown: a
  zero that means "unknown" makes every cost ceiling pass forever. A case that recorded no
  provider calls at all has nothing to compare either ceiling against, so both are unenforceable
  too (DECISIONS 36): the sum of nothing satisfies every ceiling, and a check that cannot fail is
  not a check.

:class:`PriceTable` is how a ceiling becomes enforceable. It is a YAML file the *user* maintains
and points at with ``--probatio-prices``, because a price list shipped inside a package is out of
date the day after it is committed and wrong in a way nobody notices. It prices only completions
whose cost is still unknown: a provider that reported a figure keeps it, so a table can never
silently overwrite what a provider actually said.

Nothing here raises because a budget was exceeded. Every outcome is a result, for the same reason
assertions return results (DECISIONS 22) and the baseline store does (Phase 5): a case that is
over budget usually has something else wrong with it too, and a developer wants both. The
suite-level accumulator, :class:`SuiteBudget`, composes its overrun sentence through
:class:`~probatio.errors.BudgetExceededError`, so that Phase 9's ``pytest_sessionfinish``, which
is what sets the exit status, prints text written once here rather than a paraphrase of it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Annotated, Any, Final, TypeAlias

import yaml
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError

from .assertions import AssertionResult
from .case import LLMCase
from .errors import BudgetExceededError, ProbatioConfigError
from .providers import Completion

__all__ = [
    "COST_ASSERTION",
    "COST_FLAG",
    "LATENCY_ASSERTION",
    "MONEY_DECIMALS",
    "NO_CALLS",
    "PRICES_FLAG",
    "TOKENS_PER_MTOK",
    "TOP_CASES",
    "ModelPrice",
    "PriceTable",
    "SuiteBudget",
    "case_cost",
    "evaluate_budget",
    "price_completions",
]

COST_ASSERTION: Final = "budget_cost"
"""The ``assertion_type`` of a cost result, so a reporter can find it among a case's results."""

LATENCY_ASSERTION: Final = "budget_latency"
"""The ``assertion_type`` of a latency result."""

TOKENS_PER_MTOK: Final = 1_000_000
"""Prices are quoted per million tokens, which is how providers publish them."""

MONEY_DECIMALS: Final = 6
"""Money is printed and compared to this many decimals: a hundredth of a cent, and no float dust."""

TOP_CASES: Final = 3
"""How many cases the suite-level overrun line names, in either of its two lists (spec §3.7)."""

PRICES_FLAG: Final = "pytest --probatio-prices <path>"
"""The flag an unenforceable cost ceiling names; an error without a fix is a puzzle."""

NO_CALLS: Final = "no provider calls were recorded"
"""Why a ceiling over a case that called no provider is unenforceable rather than satisfied."""

COST_FLAG: Final = "--max-cost"
"""The flag the suite-level ceiling comes from, named in the overrun line."""

_MAX_REPORTED_ERRORS: Final = 3
"""How many pydantic complaints a price-file message lists before it counts the rest."""


def _as_price(value: object) -> float:
    """Accept a number of dollars per million tokens; refuse what only looks like one.

    Raises:
        ValueError: The value is a bool, a string or anything else that is not a number. A price
            table is a file a human edits, so ``"0.003"`` and ``true`` are typos worth reporting
            rather than values worth coercing.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(
            "a price must be a number of US dollars per million tokens, not a "
            f"{type(value).__name__}"
        )
    return float(value)


Price: TypeAlias = Annotated[float, BeforeValidator(_as_price), Field(ge=0.0)]
"""One published price: a non-negative number of dollars per million tokens."""


class ModelPrice(BaseModel):
    """What one model costs, in dollars per million tokens, as its provider publishes it.

    Attributes:
        input_per_mtok: Dollars per million prompt tokens.
        output_per_mtok: Dollars per million completion tokens.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    input_per_mtok: Price
    output_per_mtok: Price

    def cost(self, tokens_in: int, tokens_out: int) -> float:
        """Price one call.

        Args:
            tokens_in: Prompt tokens.
            tokens_out: Completion tokens.

        Returns:
            The cost in US dollars.
        """
        billed = tokens_in * self.input_per_mtok + tokens_out * self.output_per_mtok
        return billed / TOKENS_PER_MTOK


class PriceTable:
    """A mapping from model name to published price, loaded from a file the user maintains.

    No prices ship with Probatio. ``examples/prices.example.yaml`` shows the structure with every
    entry commented out, so it loads as an empty table: against it every cost ceiling in a suite
    is unenforceable, which is the honest state of a suite whose prices nobody has entered.

    Attributes:
        prices: The table, keyed by the model name a completion reports.
        source: The file it was loaded from, or ``None`` for a table built in code.
    """

    def __init__(
        self,
        prices: Mapping[str, ModelPrice] | None = None,
        *,
        source: Path | None = None,
    ) -> None:
        """Build a table from prices already in hand.

        Args:
            prices: Model name to price. ``None`` is an empty table, which prices nothing.
            source: The file the prices came from, carried for error messages and reports.
        """
        self.prices: dict[str, ModelPrice] = dict(prices or {})
        self.source = source

    @classmethod
    def load(cls, path: str | Path) -> PriceTable:
        """Read a price table from a YAML file.

        The file is a mapping of model name to ``{input_per_mtok, output_per_mtok}``. An unknown
        key, a negative price and a price that is not a number are all errors naming the file and
        the model, because a typo in a price changes what every ceiling in the suite means. An
        empty file, or one whose entries are all commented out, is an empty table rather than an
        error (DECISIONS 35).

        Args:
            path: The file to read.

        Returns:
            The table, carrying ``path`` as its ``source``.

        Raises:
            ProbatioConfigError: The file cannot be read, is not valid YAML, is not a mapping, or
                holds an entry that is not a usable price.
        """
        file = Path(path)
        try:
            text = file.read_text(encoding="utf-8")
        except OSError as exc:
            raise ProbatioConfigError(f"the price table at {file} cannot be read: {exc}") from exc
        document = _parse(file, text)
        if document is None:
            return cls({}, source=file)
        if not isinstance(document, Mapping):
            raise ProbatioConfigError(
                f"{file}: a price table is a mapping of model name to "
                f"{{input_per_mtok, output_per_mtok}}, not a {type(document).__name__}"
            )
        prices: dict[str, ModelPrice] = {}
        for model, entry in document.items():
            prices[_model_name(file, model)] = _model_price(file, model, entry)
        return cls(prices, source=file)

    def __len__(self) -> int:
        """How many models the table prices."""
        return len(self.prices)

    def __contains__(self, model: object) -> bool:
        """Whether the table prices a model."""
        return model in self.prices

    def __repr__(self) -> str:
        """Show the size and the file, which is what a failure message needs."""
        return f"PriceTable(models={len(self.prices)}, source={str(self.source)!r})"

    @property
    def models(self) -> list[str]:
        """The models the table prices, sorted, for a message that says what is on offer."""
        return sorted(self.prices)

    def price(self, completion: Completion) -> float | None:
        """Price one completion from its model and its token counts.

        Args:
            completion: The completion to price. Its own ``cost_usd`` is not consulted; see
                :meth:`apply` for the rule that protects a cost a provider reported.

        Returns:
            The cost in US dollars, or ``None`` when the model is not in the table or either
            token count is unknown. ``None`` is what makes a ceiling unenforceable, so it is
            returned rather than a zero that would make the ceiling pass.
        """
        entry = self.prices.get(completion.model)
        if entry is None or completion.tokens_in is None or completion.tokens_out is None:
            return None
        return entry.cost(completion.tokens_in, completion.tokens_out)

    def apply(self, completion: Completion) -> Completion:
        """Return the completion with its cost filled in, if it was unknown and can be priced.

        Args:
            completion: The completion to price.

        Returns:
            The completion unchanged when it already carries a cost — the Claude CLI's notional
            total is a reported figure and a table never overrides one — or when this table
            cannot price it. Otherwise a copy carrying the priced ``cost_usd``.
        """
        if completion.cost_usd is not None:
            return completion
        priced = self.price(completion)
        if priced is None:
            return completion
        return completion.model_copy(update={"cost_usd": priced})


def _parse(file: Path, text: str) -> Any:
    """Parse a price file's YAML, naming the file and the line on a syntax error."""
    try:
        return yaml.safe_load(text)
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark
        where = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise ProbatioConfigError(f"{file}: invalid YAML{where}: {exc.problem}") from exc
    except yaml.YAMLError as exc:  # pragma: no cover - PyYAML marks every parse failure
        raise ProbatioConfigError(f"{file}: invalid YAML: {exc}") from exc


def _model_name(file: Path, model: object) -> str:
    """Check that a table key is usable as a model name.

    Raises:
        ProbatioConfigError: The key is not a string, so nothing a provider reports can match it.
    """
    if not isinstance(model, str):
        raise ProbatioConfigError(
            f"{file}: {model!r} is not usable as a model name; a price table is keyed by the "
            "model name a completion reports"
        )
    return model


def _model_price(file: Path, model: object, entry: object) -> ModelPrice:
    """Validate one entry of a price table.

    Raises:
        ProbatioConfigError: The entry is not a mapping, is missing a price, carries an unknown
            key, or names a price that is negative or not a number.
    """
    if not isinstance(entry, Mapping):
        raise ProbatioConfigError(
            f"{file}: the price for {model!r} is a {type(entry).__name__}, but a price is a "
            "mapping with 'input_per_mtok' and 'output_per_mtok'"
        )
    try:
        return ModelPrice.model_validate(dict(entry))
    except ValidationError as exc:
        raise ProbatioConfigError(
            f"{file}: the price for {model!r} is not usable: {_describe(exc)}"
        ) from exc


def _describe(exc: ValidationError) -> str:
    """Render pydantic's complaints as ``field: message``, naming the fields.

    All of them, up to :data:`_MAX_REPORTED_ERRORS`, because the commonest mistake in a price
    file is a misspelled key, and that produces two complaints at once: the unknown key that was
    given and the required one that was not.
    """
    errors = exc.errors()
    described = [
        f"{'.'.join(str(part) for part in error['loc']) or '<price>'}: {error['msg']}"
        for error in errors[:_MAX_REPORTED_ERRORS]
    ]
    remaining = len(errors) - len(described)
    if remaining > 0:
        described.append(f"and {remaining} more")
    return "; ".join(described)


def price_completions(
    completions: Sequence[Completion], prices: PriceTable | None
) -> list[Completion]:
    """Fill in the cost of every completion a table can price and nothing else.

    Args:
        completions: The calls the system under test made during one case.
        prices: The configured table, or ``None`` when the run has none.

    Returns:
        A list as long as ``completions``, in the same order. A completion that already carries a
        cost is returned untouched, as is one this table cannot price.
    """
    if prices is None:
        return list(completions)
    return [prices.apply(completion) for completion in completions]


def case_cost(completions: Sequence[Completion], prices: PriceTable | None = None) -> float | None:
    """Total what one case's calls cost, or report that the total is unknown.

    Args:
        completions: The calls the system under test made during the case.
        prices: The configured price table, applied to calls whose cost is unknown.

    Returns:
        The sum in US dollars, or ``None`` when the total is unknown — because a call's cost is
        still unknown after pricing, or because there were no calls at all. An empty sequence is
        ``None`` rather than ``0.0`` so that a case which recorded nothing is carried through the
        suite total as unknown instead of as free (DECISIONS 36).
    """
    priced = price_completions(completions, prices)
    if not priced or any(completion.cost_usd is None for completion in priced):
        return None
    return sum(completion.cost_usd or 0.0 for completion in priced)


def evaluate_budget(
    case: LLMCase,
    completions: Sequence[Completion],
    *,
    prices: PriceTable | None = None,
    default_max_latency_ms: float | None = None,
) -> list[AssertionResult]:
    """Evaluate a case's ceilings over the calls it made, and return one result per ceiling.

    Whether a metamorphic relation's variant calls and a judge's grading calls belong in
    ``completions`` is decided in Phase 9, where the calls are collected. This function prices and
    totals exactly what it is handed.

    Args:
        case: The case that ran; its ``budget`` holds the ceilings.
        completions: The calls the system under test made during the case, in order.
        prices: The configured price table, or ``None``. Applied only to calls whose cost is
            unknown.
        default_max_latency_ms: The ``--max-latency`` value, used for a case that declares no
            latency ceiling of its own. ``None`` means the run set none.

    Returns:
        A cost result of type ``budget_cost`` when the case declares ``max_cost_usd``, then a
        latency result of type ``budget_latency`` when the case or the run declares a latency
        ceiling. A ceiling that does not exist produces no result, so a case with no budget
        returns an empty list. When ``completions`` is empty, every ceiling the case does declare
        is unenforceable (DECISIONS 36).
    """
    priced = price_completions(completions, prices)
    results: list[AssertionResult] = []
    if case.budget.max_cost_usd is not None:
        results.append(_cost_result(case, priced, case.budget.max_cost_usd))
    declared = case.budget.max_latency_ms
    ceiling = declared if declared is not None else default_max_latency_ms
    if ceiling is not None:
        results.append(_latency_result(case, priced, ceiling, from_default=declared is None))
    return results


def _unenforceable(
    assertion_type: str, ceiling: str, because: str, *, fix: str | None = None
) -> AssertionResult:
    """Compose the one result shape that is neither a pass nor an ordinary failure (spec §3.7).

    Args:
        assertion_type: :data:`COST_ASSERTION` or :data:`LATENCY_ASSERTION`.
        ceiling: The ceiling that could not be checked, such as ``cost ceiling for htn-definition``.
        because: Why it could not be checked, in a clause that follows a colon.
        fix: The command that would make it enforceable, when one would.

    Returns:
        A failing, unenforceable result whose detail is composed through
        :class:`~probatio.errors.ProbatioConfigError`, so that the sentence and its fix are
        written once and Phase 9 can raise it rather than paraphrase it.
    """
    return AssertionResult(
        assertion_type=assertion_type,
        passed=False,
        unenforceable=True,
        detail=str(ProbatioConfigError(f"{ceiling} is unenforceable: {because}", fix=fix)),
    )


def _cost_result(case: LLMCase, priced: Sequence[Completion], ceiling: float) -> AssertionResult:
    """Compare a case's cost with its ceiling, or report the ceiling unenforceable."""
    if not priced:
        return _unenforceable(COST_ASSERTION, f"cost ceiling for {case.id}", NO_CALLS)
    unpriced = _unique(completion.model for completion in priced if completion.cost_usd is None)
    if unpriced:
        return _unenforceable(
            COST_ASSERTION,
            f"cost ceiling for {case.id}",
            f"no price configured for {', '.join(unpriced)}",
            fix=PRICES_FLAG,
        )
    total = sum(completion.cost_usd or 0.0 for completion in priced)
    over = _exceeds(total, ceiling)
    verb = "exceeds" if over else "is within"
    return AssertionResult(
        assertion_type=COST_ASSERTION,
        passed=not over,
        detail=(
            f"cost {_money(total)} over {_calls(len(priced))} {verb} the ceiling of "
            f"{_money(ceiling)}"
        ),
    )


def _latency_result(
    case: LLMCase, priced: Sequence[Completion], ceiling: float, *, from_default: bool
) -> AssertionResult:
    """Compare a case's latency with its ceiling.

    Latency needs no price file, so a call that happened is always measured (spec §3.7). A case
    that made no calls is the one thing there is nothing to measure: it is unenforceable rather
    than instantly within its ceiling (DECISIONS 36).
    """
    if not priced:
        return _unenforceable(LATENCY_ASSERTION, f"latency ceiling for {case.id}", NO_CALLS)
    total = sum(completion.latency_ms for completion in priced)
    over = _exceeds(total, ceiling)
    verb = "exceeds" if over else "is within"
    named = "the --max-latency ceiling" if from_default else "the ceiling"
    return AssertionResult(
        assertion_type=LATENCY_ASSERTION,
        passed=not over,
        detail=(
            f"latency {_ms(total)} over {_calls(len(priced))} {verb} {named} of {_ms(ceiling)}"
        ),
    )


class SuiteBudget:
    """The session's running cost against ``--max-cost``, and the one line an overrun prints.

    Phase 9 records a case here as it completes and calls :meth:`overrun_message` from
    ``pytest_sessionfinish``, where a non-``None`` message is also what sets a non-zero exit
    status. Here it is a plain object: it accumulates, it ranks, and it composes a sentence.

    A case whose cost is unknown is recorded as unknown. It is never recorded as zero and never
    quietly dropped: it is counted, it is named in the overrun line, and it keeps the total
    honest by being visibly missing from it.

    Attributes:
        max_cost_usd: The ``--max-cost`` ceiling, or ``None`` when the run set none.
    """

    def __init__(self, max_cost_usd: float | None = None) -> None:
        """Open an accumulator for one session.

        Args:
            max_cost_usd: The ``--max-cost`` ceiling in US dollars, or ``None``.

        Raises:
            ProbatioConfigError: The ceiling is negative, which no spend can satisfy.
        """
        if max_cost_usd is not None and max_cost_usd < 0.0:
            raise ProbatioConfigError(
                f"{COST_FLAG} was given {max_cost_usd}, but a cost ceiling cannot be negative"
            )
        self.max_cost_usd = max_cost_usd
        self._known: dict[str, float] = {}
        self._unknown: list[str] = []

    def record(self, case_id: str, cost_usd: float | None) -> None:
        """Record what one completed case cost.

        Recording the same case twice adds to that case's total, which is what ``--runs N`` does:
        five runs of a case are five lots of spend under one id.

        Args:
            case_id: The case that completed.
            cost_usd: What it cost, or ``None`` when the total is unknown — see
                :func:`case_cost`, which is what a caller computes it with.

        Raises:
            ProbatioConfigError: The cost is negative.
        """
        if cost_usd is None:
            if case_id not in self._unknown:
                self._unknown.append(case_id)
            return
        if cost_usd < 0.0:
            raise ProbatioConfigError(
                f"a case cannot cost {cost_usd}; a cost is unknown or non-negative",
                case_id=case_id,
            )
        self._known[case_id] = self._known.get(case_id, 0.0) + cost_usd

    @property
    def total_usd(self) -> float:
        """The total of every known case cost. Unknown cases are absent, not zero."""
        return sum(self._known.values())

    @property
    def known_case_ids(self) -> list[str]:
        """The cases whose cost is known, in the order they were first recorded."""
        return list(self._known)

    @property
    def unknown_case_ids(self) -> list[str]:
        """The cases whose cost is unknown, in the order they were first recorded."""
        return list(self._unknown)

    @property
    def n_cases(self) -> int:
        """How many distinct cases have been recorded, known and unknown together."""
        return len(self._known) + len(self._unknown)

    @property
    def exceeded(self) -> bool:
        """Whether the known total is over the ceiling. No ceiling is never an overrun."""
        return self.max_cost_usd is not None and _exceeds(self.total_usd, self.max_cost_usd)

    def most_expensive(self, limit: int = TOP_CASES) -> list[tuple[str, float]]:
        """Return the costliest cases, dearest first.

        Args:
            limit: How many to return.

        Returns:
            ``(case_id, cost)`` pairs for the cases whose cost is known, sorted by cost
            descending and then by case id, so two cases that cost the same are always reported
            in the same order.
        """
        ranked = sorted(self._known.items(), key=lambda item: (-item[1], item[0]))
        return ranked[:limit]

    def overrun_error(self) -> BudgetExceededError | None:
        """Return the error an overrun deserves, or ``None`` when the suite is within its ceiling.

        Returns:
            A :class:`~probatio.errors.BudgetExceededError` whose message names the total, the
            ceiling and the :data:`TOP_CASES` most expensive cases, and lists the cases whose
            cost is unknown when there are any. ``None`` when there is no ceiling or no overrun.
        """
        if not self.exceeded or self.max_cost_usd is None:
            return None
        parts = [
            f"suite cost {_money(self.total_usd)} over {_cases(self.n_cases)} exceeds the "
            f"{COST_FLAG} ceiling of {_money(self.max_cost_usd)}",
            "most expensive: "
            + ", ".join(f"{case_id} {_money(cost)}" for case_id, cost in self.most_expensive()),
        ]
        if self._unknown:
            parts.append(
                f"{_cases(len(self._unknown))} of unknown cost not counted: "
                + _listed(self._unknown)
            )
        return BudgetExceededError("; ".join(parts))

    def overrun_message(self) -> str | None:
        """Return the one line spec §3.7 asks for, or ``None`` within the ceiling."""
        error = self.overrun_error()
        return None if error is None else str(error)


def _exceeds(used: float, ceiling: float) -> bool:
    """Report an overrun, comparing the difference at :data:`MONEY_DECIMALS` decimals.

    Summing floats makes ``0.1 + 0.2`` slightly more than ``0.3``, so an exact ``>`` would fail
    a suite that spent exactly its ceiling. The difference is rounded before the comparison,
    the same way score drift is (DECISIONS 32), so a ceiling met exactly is met.
    """
    return round(used - ceiling, MONEY_DECIMALS) > 0.0


def _money(value: float) -> str:
    """Render dollars the one way this module renders them."""
    return f"${value:.{MONEY_DECIMALS}f}"


def _ms(value: float) -> str:
    """Render milliseconds the one way this module renders them."""
    return f"{value:.1f} ms"


def _calls(count: int) -> str:
    """Render a provider-call count, singular when there is one of them."""
    return "1 provider call" if count == 1 else f"{count} provider calls"


def _cases(count: int) -> str:
    """Render a case count, singular when there is one of them."""
    return "1 case" if count == 1 else f"{count} cases"


def _listed(case_ids: Sequence[str]) -> str:
    """List case ids on one line, naming at most :data:`TOP_CASES` and counting the rest."""
    named = ", ".join(case_ids[:TOP_CASES])
    remaining = len(case_ids) - TOP_CASES
    return f"{named} and {remaining} more" if remaining > 0 else named


def _unique(models: Iterable[str]) -> list[str]:
    """De-duplicate model names, keeping the order the calls were made in."""
    seen: dict[str, None] = {}
    for model in models:
        seen.setdefault(model, None)
    return list(seen)
