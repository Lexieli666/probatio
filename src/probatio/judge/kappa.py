"""Cohen's kappa by hand: chance-corrected agreement between two label sequences.

Ten lines of arithmetic, tested against a 2x2 example written out longhand, instead of a
dependency on scikit-learn — which would pull in NumPy and SciPy to compute a ratio of two sums,
and which spec §9 rejects outright. The implementation is multi-label: nothing here assumes two
labels, because a rubric with three outcomes is a normal thing to validate and a binary-only
implementation would silently mis-handle it.

Kappa answers the question raw agreement cannot: two raters who both say "supported" nine times
out of ten agree 80% of the time by luck alone, so 80% agreement is evidence of very little. The
report prints both numbers for exactly that reason.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from ..errors import ProbatioConfigError

__all__ = ["KappaResult", "cohens_kappa"]


class KappaResult(BaseModel):
    """Agreement between two raters over the same items.

    Attributes:
        n: How many items both raters labelled.
        agreement: The fraction of items they gave the same label.
        kappa: Cohen's kappa: agreement corrected for the agreement expected by chance.
        labels: Every label either rater used, sorted.
        table: The full confusion table, keyed ``(label from a, label from b)``; cells that
            nobody produced are present and zero, so two runs over different data compare.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    n: int
    agreement: float
    kappa: float
    labels: list[str]
    table: dict[tuple[str, str], int]


def cohens_kappa(a: Sequence[str], b: Sequence[str]) -> KappaResult:
    """Compute observed agreement and Cohen's kappa for two aligned label sequences.

    Kappa is ``(p_o - p_e) / (1 - p_e)`` where ``p_o`` is the observed agreement and ``p_e`` is
    the agreement expected if each rater assigned their own labels at random, in their own
    observed proportions. It is ``1.0`` on perfect agreement, ``0.0`` when the raters agree
    exactly as often as chance predicts, and negative when they agree less often than that.

    When both raters used one single label for every item, ``p_e`` is 1 and the formula is
    ``0 / 0``. That case is decided rather than computed: agreement is necessarily perfect, so
    kappa is ``1.0`` (DECISIONS 24).

    Args:
        a: The first rater's labels, one per item.
        b: The second rater's labels, aligned with ``a``.

    Returns:
        The :class:`KappaResult`.

    Raises:
        ProbatioConfigError: The sequences are empty or of different lengths.
    """
    if len(a) != len(b):
        raise ProbatioConfigError(
            f"the two label sequences have different lengths ({len(a)} and {len(b)}), so they "
            "do not label the same items"
        )
    n = len(a)
    if n == 0:
        raise ProbatioConfigError("there are no labels to compare")

    pairs = Counter(zip(a, b, strict=True))
    labels = sorted(set(a) | set(b))
    table = {(first, second): pairs[(first, second)] for first in labels for second in labels}

    observed = sum(count for (first, second), count in table.items() if first == second) / n
    counts_a = Counter(a)
    counts_b = Counter(b)
    expected = sum((counts_a[label] / n) * (counts_b[label] / n) for label in labels)

    if expected == 1.0:
        kappa = 1.0
    else:
        kappa = (observed - expected) / (1.0 - expected)

    return KappaResult(n=n, agreement=observed, kappa=kappa, labels=labels, table=table)
