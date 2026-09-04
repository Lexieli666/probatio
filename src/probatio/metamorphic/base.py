"""The relation contract: what a relation is, what evaluating one produces, and the registry.

A metamorphic relation is a claim about a *transformation of the input*, not about an output. It
says: this change preserves the meaning of the case, so the verdict must not move. That makes it
the one kind of check in Probatio that needs no reference answer, no rubric and no human label —
which is why it is a headline feature and not another metric.

Three positions are fixed here.

**A relation is a class with a citation, not a lambda.** Every relation names the entry in
``docs/relations.md`` it is attributed to, because "the model is robust to document order" is a
claim from a literature, and spec §9 rejects inflated names for it: a permutation is a
permutation, not an adversarial attack. The key is on the class, so it survives into the report.

**Not applicable is a result, and it is not zero.** A relation that generated no variants has
observed nothing. Reporting ``0.00`` for it would claim a robustness result the run never
measured, so :attr:`RelationResult.violation_rate` is ``None`` and the reporter counts the case
under "not applicable" (DECISIONS 8).

**Violation rates never change a verdict.** Nothing in this package raises, fails a case or
touches an :class:`~probatio.assertions.AssertionResult`. A relation result is reported alongside
the case (spec §0), and Phase 9's ``check`` keeps it that way.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, Final

from pydantic import BaseModel, ConfigDict, Field

from ..case import LLMCase
from ..errors import ProbatioConfigError

__all__ = [
    "RELATIONS",
    "RELATION_MARKER",
    "Flip",
    "Relation",
    "RelationRegistry",
    "RelationResult",
    "Variant",
]

RELATION_MARKER: Final = "probatio_relation"
"""The pytest marker every relation decorator applies, registered in :mod:`probatio.plugin`."""


class Variant(BaseModel):
    """One transformed case, and the label the report identifies it by.

    Attributes:
        case: The transformed case. It is a full :class:`~probatio.case.LLMCase`, so the system
            under test runs on it exactly as it runs on the original.
        label: Which variant this is, such as ``permutation-1`` or ``casing``. Labels are fixed
            by the relation, never by a counter that depends on iteration order elsewhere.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    case: LLMCase
    label: str


class Flip(BaseModel):
    """One variant whose verdict differed from the original case's, in either direction.

    Attributes:
        label: The variant's label.
        original_verdict: The verdict the untransformed case produced.
        variant_verdict: The verdict the variant produced.
        changed_assertions: The ``assertion_type`` of every assertion whose ``passed`` flag
            differed between the two runs, first occurrence first. This is what tells a developer
            *how* the verdict moved: a similarity score that slipped under its floor reads very
            differently from a required substring that vanished.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str
    original_verdict: bool
    variant_verdict: bool
    changed_assertions: list[str] = Field(default_factory=list)


class RelationResult(BaseModel):
    """What one relation observed on one case.

    Attributes:
        relation: The relation's :attr:`Relation.name`.
        case_id: The case the relation was evaluated on.
        n_variants: How many variants were generated and evaluated.
        n_violations: How many of them flipped the verdict.
        violation_rate: ``n_violations / n_variants``, or ``None`` when the relation was not
            applicable to the case and nothing was measured.
        flips: One entry per violation. Variants that agreed with the original are counted in
            ``n_variants`` and not listed, because a report of what did not change is noise.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    relation: str
    case_id: str
    n_variants: int = Field(ge=0)
    n_violations: int = Field(ge=0)
    violation_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    flips: list[Flip] = Field(default_factory=list)


class Relation(ABC):
    """A semantics-preserving transformation of a case, plus the claim that the verdict holds.

    A subclass supplies :attr:`name`, :attr:`citation` and :meth:`variants`, and overrides
    :meth:`applicable` when the transformation only makes sense for some shapes of input.

    Attributes:
        name: The relation's name, used as the registry key and printed in every report.
        citation: The key of the entry in ``docs/relations.md`` this relation is attributed to,
            such as ``[LLMORPH]``.
    """

    name: ClassVar[str]
    citation: ClassVar[str]

    @abstractmethod
    def variants(self, case: LLMCase) -> list[Variant]:
        """Return the transformed cases this relation claims must not change the verdict.

        Args:
            case: The case to transform. It is frozen; a variant is a copy.

        Returns:
            The variants, in a fixed order that does not depend on the process, the platform or
            the wall clock. An empty list means the relation found nothing to vary, which is
            reported as "not applicable" rather than as zero violations.
        """

    def applicable(self, case: LLMCase) -> bool:
        """Say whether this relation can transform this case at all.

        Args:
            case: The case to check.

        Returns:
            ``True`` by default. A relation that names a field overrides this so that a case
            whose input has a different shape is reported as not applicable (DECISIONS 8), which
            is what lets one parametrised test cover a suite of mixed inputs.
        """
        return True

    def __repr__(self) -> str:
        """Render the relation as its name, so a pytest marker reads legibly in a report."""
        return f"<{type(self).__name__} {self.name!r}>"


class RelationRegistry:
    """The relation classes Probatio knows, by name.

    The registry exists so that a relation can be named in a report, in a results JSON and — in a
    user's own package — by a one-line registration next to the class, which is the whole of
    ``docs/relations.md``'s recipe for adding one. It holds classes rather than instances, because
    a relation is configured per test by its decorator's arguments.
    """

    def __init__(self) -> None:
        """Open an empty registry."""
        self._relations: dict[str, type[Relation]] = {}

    def register(self, relation: type[Relation]) -> type[Relation]:
        """Add a relation class, and return it so this can be used as a class decorator.

        Args:
            relation: The class to register. Its ``name`` is the key.

        Returns:
            ``relation``, unchanged.

        Raises:
            ProbatioConfigError: The class has no ``name``, or the name is already taken. A
                silently shadowed relation would report under a name whose behaviour is not the
                one the reader looks up in the docs.
        """
        name = getattr(relation, "name", None)
        if not isinstance(name, str) or not name:
            raise ProbatioConfigError(
                f"{relation.__name__} has no 'name', so it cannot be registered or reported"
            )
        if name in self._relations:
            raise ProbatioConfigError(
                f"a relation named {name!r} is already registered as "
                f"{self._relations[name].__name__}; names appear in reports, so they are unique"
            )
        self._relations[name] = relation
        return relation

    def get(self, name: str) -> type[Relation]:
        """Look up a relation class by name.

        Args:
            name: The relation's name.

        Returns:
            The class.

        Raises:
            ProbatioConfigError: No relation of that name is registered.
        """
        try:
            return self._relations[name]
        except KeyError:
            raise ProbatioConfigError(
                f"{name!r} is not a relation Probatio knows; the registered relations are "
                f"{', '.join(self.names()) or '(none)'}"
            ) from None

    def names(self) -> list[str]:
        """Return every registered name, sorted, so a report and an error list them alike."""
        return sorted(self._relations)

    def __contains__(self, name: object) -> bool:
        """Say whether a name is registered."""
        return name in self._relations

    def __len__(self) -> int:
        """Return how many relations are registered."""
        return len(self._relations)


RELATIONS: Final = RelationRegistry()
"""The registry the four shipped relations register themselves in at import time."""
