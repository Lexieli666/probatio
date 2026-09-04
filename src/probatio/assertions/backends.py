"""The similarity backend protocol, the trigram cosine default, and the backend registry.

Similarity answers one narrow question: is this output a paraphrase of that reference? The
shipped backend is deliberately the dumbest thing that answers it — character trigram counts and
a cosine — because it is pure Python, deterministic across processes and platforms, needs no
model download, and is therefore something a CI run can reproduce exactly. It knows nothing about
meaning: ``docs/assertions.md`` states the position that similarity is for paraphrase-stable
content and a judge is for claims.

Trigrams are counted over the whole normalised string without padding, so a token that moves
within a sentence keeps most of its trigrams and word order matters much less than it would to a
token-overlap measure. Three edge cases are decided here rather than left to float arithmetic:
two strings that normalise to fewer than three characters have no trigrams at all and score 1.0
when they are equal and 0.0 otherwise; identical strings score exactly 1.0, which needs the clamp
because ``sqrt(x) * sqrt(x)`` is not always ``x``; and strings sharing no trigram score 0.0.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Final, Protocol, runtime_checkable

from ..errors import ProbatioConfigError

__all__ = [
    "SIMILARITY_BACKENDS",
    "SimilarityBackend",
    "TrigramCosine",
    "get_backend",
]

TRIGRAM: Final = 3
"""The n of the n-grams. Named because it appears in the guard as well as in the slicing."""

_WHITESPACE: Final = re.compile(r"\s+")
"""Every run of whitespace collapses to one space, so wrapping cannot change a score."""


@runtime_checkable
class SimilarityBackend(Protocol):
    """Anything that scores two strings for similarity on a [0, 1] scale."""

    def similarity(self, a: str, b: str) -> float:
        """Score two strings.

        Args:
            a: One string, conventionally the output under test.
            b: The other, conventionally the reference.

        Returns:
            A number in [0, 1], where 1.0 means indistinguishable to this backend.
        """
        ...


def normalize(text: str) -> str:
    """Lower-case a string and collapse every run of whitespace to a single space."""
    return _WHITESPACE.sub(" ", text).strip().lower()


def trigrams(text: str) -> Counter[str]:
    """Count the character trigrams of an already normalised string, without padding."""
    return Counter(text[index : index + TRIGRAM] for index in range(len(text) - TRIGRAM + 1))


class TrigramCosine:
    """Cosine similarity over character-trigram counts. Deterministic, pure Python, no data.

    The default backend, registered as ``trigram``. Normalisation lower-cases and collapses
    whitespace; nothing else is stripped, so punctuation and stems both count.
    """

    name: Final = "trigram"
    """The registry key, carried on the instance so a report can name what produced a score."""

    def similarity(self, a: str, b: str) -> float:
        """Score two strings by the cosine of their character-trigram count vectors.

        Args:
            a: One string.
            b: The other.

        Returns:
            A number in [0, 1]. Strings too short to have a trigram score 1.0 when they are
            equal after normalisation and 0.0 otherwise; strings sharing no trigram score 0.0.
        """
        left, right = normalize(a), normalize(b)
        counts_a, counts_b = trigrams(left), trigrams(right)
        if not counts_a or not counts_b:
            return 1.0 if left == right else 0.0
        dot = sum(counts_a[gram] * counts_b[gram] for gram in counts_a.keys() & counts_b.keys())
        if dot == 0:
            return 0.0
        norm = math.sqrt(sum(n * n for n in counts_a.values())) * math.sqrt(
            sum(n * n for n in counts_b.values())
        )
        return min(1.0, dot / norm)


SIMILARITY_BACKENDS: Final[dict[str, SimilarityBackend]] = {"trigram": TrigramCosine()}
"""Backends by name. Embedding backends can be registered here; none are shipped, and nothing
in the test suite installs or invokes one."""


def get_backend(name: str) -> SimilarityBackend:
    """Look a similarity backend up by name.

    Args:
        name: A key of :data:`SIMILARITY_BACKENDS`, such as ``trigram``.

    Returns:
        The registered backend.

    Raises:
        ProbatioConfigError: No backend is registered under that name.
    """
    try:
        return SIMILARITY_BACKENDS[name]
    except KeyError:
        raise ProbatioConfigError(
            f"no similarity backend named {name!r} is registered; the registered backends are "
            f"{sorted(SIMILARITY_BACKENDS)}"
        ) from None
