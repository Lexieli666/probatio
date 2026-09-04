"""The four shipped relations and the four decorators that apply them.

Each relation transforms one field of a case and claims the verdict must not move. The
transformations are deliberately dull: a permutation, an inserted paragraph, doubled spaces, a
paraphrase somebody already wrote down. None of them is an attack, none of them is a sample from
a distribution, and none of them calls a model — which is what makes the violation rate a
statement about the application rather than about the harness that measured it.

**Every variant is a pure function of the case.** ``format_jitter``'s three transforms are fixed
functions, not samples. ``order_invariant`` is the only relation with any randomness at all, and
its generator is seeded from ``stable_hash((case.id, field))``, so the same case yields the same
permutations in the next process and on the next machine — which is what lets a violation rate be
compared across two CI runs at all.

**Paraphrases are read from disk, never generated.** Spec §9 rejects paraphrases produced during
a pytest run: a relation whose variants come from a model measures the paraphrasing model as much
as the application, and its violation rate is not comparable with yesterday's. So
``paraphrase_invariant`` reads ``variants/<case_id>.yaml``, and a missing file is an error naming
the ``probatio freeze-variants`` command that a human runs once and commits.
"""

from __future__ import annotations

import random
import re
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from math import factorial
from pathlib import Path
from typing import Any, Final

import pytest
from _pytest.mark import MarkDecorator

from ..case import LLMCase, check_field_path, get_field, with_field
from ..errors import ProbatioConfigError
from ..hashing import canonical_json, stable_hash
from .base import RELATION_MARKER, RELATIONS, Relation, Variant
from .variants import read_frozen_variants

__all__ = [
    "DEFAULT_VARIANTS_DIR",
    "JITTER_KINDS",
    "JITTER_TRANSFORMS",
    "POSITIONS",
    "DistractorRobust",
    "FormatJitter",
    "OrderInvariant",
    "ParaphraseInvariant",
    "distractor_robust",
    "format_jitter",
    "jitter_casing",
    "jitter_markdown",
    "jitter_whitespace",
    "order_invariant",
    "paraphrase_invariant",
    "relation_mark",
    "upper_first_sentence",
]

POSITIONS: Final = ("start", "end")
"""Where ``distractor_robust`` may put a distractor, and the order it does so in."""

JITTER_KINDS: Final = ("whitespace", "casing", "markdown")
"""``format_jitter``'s three kinds, in the order their variants are generated."""

DEFAULT_VARIANTS_DIR: Final = "variants"
"""Where frozen paraphrases live, relative to the base directory (spec §5, DECISIONS 19)."""

_INPUT: Final = "input"
"""The field a relation transforms when it is given ``field=None``: the whole input."""

_EXACT_CEILING_MAX: Final = 10
"""Above this many items, the count of distinct permutations is not worth computing exactly."""

_SHUFFLES_PER_VARIANT: Final = 200
"""How many shuffles are tried per requested permutation before giving up on finding more."""

_FIRST_SENTENCE: Final = re.compile(r"^.*?[.!?](?=\s|$)", re.DOTALL)
"""``jitter_casing``'s sentence rule: up to the first ``.``, ``!`` or ``?`` before a space."""


# -- the fixed format transforms -----------------------------------------------------------------


def jitter_whitespace(text: str) -> str:
    """Double every single space and add trailing newlines.

    Args:
        text: The field's text.

    Returns:
        The text with each space doubled and two newlines appended. Keywords are never split,
        because no token contains a space; what changes is only how the prompt is laid out.
    """
    return text.replace(" ", "  ") + "\n\n"


def upper_first_sentence(text: str) -> str:
    """Upper-case the first sentence of a string and leave the rest alone.

    Args:
        text: The field's text.

    Returns:
        The text with everything up to and including the first ``.``, ``!`` or ``?`` that is
        followed by whitespace or the end of the string upper-cased. When there is no such mark
        the whole string is one sentence and all of it is upper-cased.
    """
    match = _FIRST_SENTENCE.match(text)
    if match is None:
        return text.upper()
    end = match.end()
    return text[:end].upper() + text[end:]


def jitter_casing(text: str) -> str:
    """Upper-case the first sentence only; see :func:`upper_first_sentence`.

    Args:
        text: The field's text.

    Returns:
        The jittered text.
    """
    return upper_first_sentence(text)


def jitter_markdown(text: str) -> str:
    """Wrap the text in a fenced code block.

    Args:
        text: The field's text.

    Returns:
        The text inside an unlabelled triple-backtick fence.
    """
    return f"```\n{text}\n```"


JITTER_TRANSFORMS: Final[Mapping[str, Callable[[str], str]]] = {
    "whitespace": jitter_whitespace,
    "casing": jitter_casing,
    "markdown": jitter_markdown,
}
"""The three transforms by kind. They are functions, so two processes produce the same bytes."""


# -- shared argument checking --------------------------------------------------------------------


def _check_k(k: int, *, relation: str) -> int:
    """Reject a variant count that would generate nothing.

    Raises:
        ProbatioConfigError: ``k`` is below 1.
    """
    if k < 1:
        raise ProbatioConfigError(
            f"{relation} needs k >= 1 to generate a variant, not {k!r}; a relation with no "
            "variants observes nothing"
        )
    return k


def _checked_path(field: str) -> str:
    """Return a field path, checking its syntax at construction time rather than per case."""
    check_field_path(field)
    return field


def _text_at(case: LLMCase, path: str) -> str | None:
    """Read a string field off a case, or ``None`` when it does not resolve to a string."""
    value = get_field(case, path, default=None)
    return value if isinstance(value, str) else None


def _list_at(case: LLMCase, path: str) -> list[Any] | None:
    """Read a list field off a case, or ``None`` when it does not resolve to a list."""
    value = get_field(case, path, default=None)
    return list(value) if isinstance(value, list) else None


# -- order_invariant -----------------------------------------------------------------------------


def _permutation_ceiling(items: Sequence[Any]) -> int | None:
    """How many distinct non-identity permutations a list has, or ``None`` when that is many.

    Duplicated items reduce the count: ``["a", "a", "b"]`` has three distinct orderings, not six,
    so asking for three non-identity permutations of it can only ever yield two.
    """
    if len(items) > _EXACT_CEILING_MAX:
        return None
    total = factorial(len(items))
    for count in Counter(canonical_json(item) for item in items).values():
        total //= factorial(count)
    return total - 1


@RELATIONS.register
class OrderInvariant(Relation):
    """Permuting a list field must not change the verdict. Citation: ``[MR-CATALOG-NLP]``.

    The list is almost always the retrieved documents of a retrieval-grounded application, and
    the claim is the one every such application implicitly makes: the answer follows from the
    set of documents, not from which one the retriever happened to rank first.

    Attributes:
        field: The dotted path of the list to permute.
        k: How many permutations to generate at most.
    """

    name = "order_invariant"
    citation = "[MR-CATALOG-NLP]"

    def __init__(self, field: str, k: int = 3) -> None:
        """Configure the list to permute and how many permutations to try.

        Args:
            field: Dotted path of the list, such as ``input.documents``.
            k: The most permutations to generate. Fewer are generated when the list is too short
                to have that many distinct orderings; a two-element list yields exactly one.

        Raises:
            ProbatioConfigError: The path is malformed, or ``k`` is below 1.
        """
        self.field = _checked_path(field)
        self.k = _check_k(k, relation=self.name)

    def applicable(self, case: LLMCase) -> bool:
        """Say whether the field is a list of at least two items.

        Args:
            case: The case to check.

        Returns:
            ``False`` when the field does not resolve, is not a list, or holds fewer than two
            items — there is no non-identity permutation of a one-element list (DECISIONS 8).
        """
        items = _list_at(case, self.field)
        return items is not None and len(items) >= 2

    def variants(self, case: LLMCase) -> list[Variant]:
        """Return up to ``k`` distinct non-identity permutations of the field.

        Args:
            case: The case to permute.

        Returns:
            The variants, labelled ``permutation-1`` upward. The generator is seeded from
            ``stable_hash((case.id, field))``, so the same case always yields the same
            permutations in the same order, in any process.
        """
        items = _list_at(case, self.field)
        if items is None or len(items) < 2:
            return []
        ceiling = _permutation_ceiling(items)
        wanted = self.k if ceiling is None else min(self.k, ceiling)
        rng = random.Random(int(stable_hash((case.id, self.field)), 16))
        found: list[list[Any]] = []
        for _ in range(_SHUFFLES_PER_VARIANT * self.k):
            if len(found) >= wanted:
                break
            shuffled = list(items)
            rng.shuffle(shuffled)
            if shuffled == items or shuffled in found:
                continue
            found.append(shuffled)
        return [
            Variant(case=with_field(case, self.field, order), label=f"permutation-{index}")
            for index, order in enumerate(found, start=1)
        ]


# -- distractor_robust ---------------------------------------------------------------------------


@RELATIONS.register
class DistractorRobust(Relation):
    """Adding irrelevant text must not change the verdict. Citation: ``[LLMORPH]``.

    With ``field`` naming a list, each distractor is inserted as an extra item at the start and
    at the end of it, which is the interesting form for a retrieval-grounded application: the
    retriever returned one document that does not belong, and the answer must not follow it.
    With ``field=None`` the case's bare-string input is used instead and the distractor is
    prepended and appended as its own paragraph (DECISIONS 7).

    Attributes:
        field: The dotted path of the list, or ``None`` for a bare-string input.
        distractors: The irrelevant texts to insert.
        positions: Which ends to insert at, in the order variants are generated.
    """

    name = "distractor_robust"
    citation = "[LLMORPH]"

    def __init__(
        self,
        *,
        field: str | None = None,
        distractors: Sequence[str],
        positions: Sequence[str] = POSITIONS,
    ) -> None:
        """Configure the field, the distractors and the positions.

        Args:
            field: Dotted path of the list to insert into, or ``None`` to use the bare-string
                input.
            distractors: One or more irrelevant texts. Each must be non-empty.
            positions: Any of ``"start"`` and ``"end"``, in the order to use them.

        Raises:
            ProbatioConfigError: The path is malformed, no distractor was given, a distractor is
                empty, or a position is not one of :data:`POSITIONS`.
        """
        self.field = None if field is None else _checked_path(field)
        self.distractors = list(distractors)
        self.positions = tuple(positions)
        if not self.distractors:
            raise ProbatioConfigError(
                f"{self.name} needs at least one distractor; without one nothing is inserted "
                "and the relation observes nothing"
            )
        for distractor in self.distractors:
            if not distractor.strip():
                raise ProbatioConfigError(
                    f"{self.name} was given an empty distractor; an empty insertion is not a "
                    "transformation of the input"
                )
        if not self.positions:
            raise ProbatioConfigError(f"{self.name} needs at least one of {POSITIONS}")
        unknown = [position for position in self.positions if position not in POSITIONS]
        if unknown:
            raise ProbatioConfigError(
                f"{self.name} cannot insert at {', '.join(repr(p) for p in unknown)}; the "
                f"positions are {', '.join(repr(p) for p in POSITIONS)}"
            )

    def _path(self) -> str:
        """Return the field path this relation writes to: the list, or the input itself."""
        return _INPUT if self.field is None else self.field

    def applicable(self, case: LLMCase) -> bool:
        """Say whether the named list resolves, or the input is a bare string.

        Args:
            case: The case to check.

        Returns:
            ``False`` when a named field is not a list, or when ``field=None`` and the input is
            not a string (DECISIONS 8).
        """
        if self.field is None:
            return isinstance(case.input, str)
        return _list_at(case, self.field) is not None

    def variants(self, case: LLMCase) -> list[Variant]:
        """Return one variant per position and distractor, in a fixed order.

        Args:
            case: The case to add distractors to.

        Returns:
            The variants, labelled ``distractor-<position>-<index>``.
        """
        if not self.applicable(case):
            return []
        variants: list[Variant] = []
        for position in self.positions:
            for index, distractor in enumerate(self.distractors, start=1):
                inserted = self._insert(case, position, distractor)
                variants.append(
                    Variant(
                        case=with_field(case, self._path(), inserted),
                        label=f"distractor-{position}-{index}",
                    )
                )
        return variants

    def _insert(self, case: LLMCase, position: str, distractor: str) -> Any:
        """Build the replacement value: an extra list item, or an extra paragraph."""
        if self.field is None:
            text = str(case.input)
            return f"{distractor}\n\n{text}" if position == "start" else f"{text}\n\n{distractor}"
        items = _list_at(case, self.field) or []
        return [distractor, *items] if position == "start" else [*items, distractor]


# -- format_jitter -------------------------------------------------------------------------------


@RELATIONS.register
class FormatJitter(Relation):
    """Reformatting the input must not change the verdict. Citation: ``[LLMORPH]``.

    Three fixed transforms, not three samples: doubled spaces with trailing newlines, the first
    sentence upper-cased, and the text wrapped in a fenced code block. None of them changes a
    word, so an application whose verdict moves under one of them is keying on layout.

    Attributes:
        kinds: Which transforms to apply, in the order variants are generated.
        field: The dotted path of the string to jitter, or ``None`` for a bare-string input.
    """

    name = "format_jitter"
    citation = "[LLMORPH]"

    def __init__(self, kinds: Sequence[str] = JITTER_KINDS, field: str | None = None) -> None:
        """Configure which transforms to apply and to which field.

        Args:
            kinds: Any of :data:`JITTER_KINDS`, in the order to apply them.
            field: Dotted path of the string to jitter, or ``None`` to jitter a bare-string
                input.

        Raises:
            ProbatioConfigError: The path is malformed, no kind was given, or a kind is unknown.
        """
        self.field = None if field is None else _checked_path(field)
        self.kinds = tuple(kinds)
        if not self.kinds:
            raise ProbatioConfigError(f"{self.name} needs at least one of {JITTER_KINDS}")
        unknown = [kind for kind in self.kinds if kind not in JITTER_TRANSFORMS]
        if unknown:
            raise ProbatioConfigError(
                f"{self.name} has no {', '.join(repr(k) for k in unknown)} transform; the kinds "
                f"are {', '.join(repr(k) for k in JITTER_KINDS)}"
            )

    def _path(self) -> str:
        """Return the field path this relation writes to: the string, or the input itself."""
        return _INPUT if self.field is None else self.field

    def applicable(self, case: LLMCase) -> bool:
        """Say whether the field resolves to a string.

        Args:
            case: The case to check.

        Returns:
            ``False`` when the field is missing or is not a string — a case whose input is a
            mapping with no ``question``, for example (DECISIONS 8).
        """
        return _text_at(case, self._path()) is not None

    def variants(self, case: LLMCase) -> list[Variant]:
        """Return one variant per configured kind.

        Args:
            case: The case to jitter.

        Returns:
            The variants, each labelled with its kind.
        """
        text = _text_at(case, self._path())
        if text is None:
            return []
        return [
            Variant(
                case=with_field(case, self._path(), JITTER_TRANSFORMS[kind](text)),
                label=kind,
            )
            for kind in self.kinds
        ]


# -- paraphrase_invariant ------------------------------------------------------------------------


@RELATIONS.register
class ParaphraseInvariant(Relation):
    """Rewording the input must not change the verdict. Citation: ``[MR-CATALOG-NLP]``.

    The paraphrases are read from ``<variants_dir>/<case_id>.yaml`` and are never generated
    during a run (spec §9). A human produces them once with ``probatio freeze-variants``, reads
    them, and commits them; from then on the relation is as cheap and as reproducible as a
    permutation.

    Attributes:
        k: How many paraphrases to take from the file.
        field: The dotted path of the string the paraphrases replace.
        variants_dir: Where the frozen files live, absolute or relative to ``base_dir``.
        base_dir: What a relative ``variants_dir`` is resolved against, or ``None`` for the
            working directory at the time the variants are read (DECISIONS 19).
    """

    name = "paraphrase_invariant"
    citation = "[MR-CATALOG-NLP]"

    def __init__(
        self,
        k: int = 3,
        field: str = "input.question",
        variants_dir: str | Path = DEFAULT_VARIANTS_DIR,
        base_dir: Path | None = None,
    ) -> None:
        """Configure how many paraphrases to read, of which field, from where.

        Args:
            k: The most paraphrases to take, from the top of the file. A file holding fewer
                yields fewer variants.
            field: Dotted path of the string to replace, such as ``input.question``.
            variants_dir: Directory holding ``<case_id>.yaml``. An absolute path is used as
                given; a relative one is resolved against ``base_dir``.
            base_dir: The origin for a relative ``variants_dir``. ``None`` means the working
                directory, which is pytest's rootdir under a normal invocation, exactly as
                ``schema_file`` resolves (DECISIONS 19).

        Raises:
            ProbatioConfigError: The path is malformed, or ``k`` is below 1.
        """
        self.field = _checked_path(field)
        self.k = _check_k(k, relation=self.name)
        self.variants_dir = Path(variants_dir)
        self.base_dir = base_dir

    def resolved_variants_dir(self) -> Path:
        """Return the directory the frozen files are read from.

        Returns:
            ``variants_dir`` when it is absolute, otherwise it joined onto ``base_dir`` or, when
            no base directory was given, onto the current working directory.
        """
        if self.variants_dir.is_absolute():
            return self.variants_dir
        return (self.base_dir if self.base_dir is not None else Path.cwd()) / self.variants_dir

    def applicable(self, case: LLMCase) -> bool:
        """Say whether the field resolves to a string.

        Args:
            case: The case to check.

        Returns:
            ``False`` when the field is missing or is not a string. Whether the file exists is
            deliberately not asked here: a missing file for a case that *is* in scope is an
            error, not a silent "not applicable" (DECISIONS 8 is about input shape, not about
            artefacts a human forgot to commit).
        """
        return _text_at(case, self.field) is not None

    def variants(self, case: LLMCase) -> list[Variant]:
        """Return up to the first ``k`` frozen paraphrases of the field as variants.

        A file holding fewer than ``k`` paraphrases yields fewer variants, and the relation
        result's ``n_variants`` is what was evaluated. A reviewer deleting a paraphrase that
        changed the meaning of the question is doing the job the frozen file exists for, so a
        short file is not an error (DECISIONS 52).

        Args:
            case: The case to reword.

        Returns:
            The variants, labelled ``paraphrase-1`` upward, one per paraphrase taken.

        Raises:
            MissingVariantsError: There is no frozen file for this case, or the file holds no
                paraphrases at all. The message names the ``probatio freeze-variants`` command.
            ProbatioConfigError: The file is unreadable, does not validate, or names a different
                case or field.
        """
        if not self.applicable(case):
            return []
        paraphrases = read_frozen_variants(
            case, field=self.field, k=self.k, variants_dir=self.resolved_variants_dir()
        )
        return [
            Variant(case=with_field(case, self.field, text), label=f"paraphrase-{index}")
            for index, text in enumerate(paraphrases, start=1)
        ]


# -- the decorators ------------------------------------------------------------------------------


def relation_mark(relation: Relation) -> MarkDecorator:
    """Wrap a configured relation in the pytest marker the ``probatio`` fixture reads.

    Args:
        relation: The configured relation instance.

    Returns:
        ``pytest.mark.probatio_relation(relation)``, which is applied to the test function. The
        decorators are this thin on purpose: the relation carries all of its configuration, so
        nothing about a suite's relations is decided by the plugin.
    """
    marker: MarkDecorator = getattr(pytest.mark, RELATION_MARKER)(relation)
    return marker


def order_invariant(field: str, k: int = 3) -> MarkDecorator:
    """Assert that permuting a list field does not change the verdict.

    Args:
        field: Dotted path of the list, such as ``input.documents``.
        k: The most permutations to generate. A two-element list yields exactly one.

    Returns:
        The pytest marker to apply to the test function.
    """
    return relation_mark(OrderInvariant(field, k))


def distractor_robust(
    *,
    field: str | None = None,
    distractors: Sequence[str],
    positions: Sequence[str] = POSITIONS,
) -> MarkDecorator:
    """Assert that inserting irrelevant text does not change the verdict.

    Args:
        field: Dotted path of the list to insert into, or ``None`` to prepend and append to a
            bare-string input (DECISIONS 7).
        distractors: One or more irrelevant texts.
        positions: Any of ``"start"`` and ``"end"``.

    Returns:
        The pytest marker to apply to the test function.
    """
    return relation_mark(
        DistractorRobust(field=field, distractors=distractors, positions=positions)
    )


def format_jitter(kinds: Sequence[str] = JITTER_KINDS, field: str | None = None) -> MarkDecorator:
    """Assert that reformatting the input does not change the verdict.

    Args:
        kinds: Any of ``"whitespace"``, ``"casing"`` and ``"markdown"``.
        field: Dotted path of the string to jitter, or ``None`` for a bare-string input.

    Returns:
        The pytest marker to apply to the test function.
    """
    return relation_mark(FormatJitter(kinds, field))


def paraphrase_invariant(
    k: int = 3,
    field: str = "input.question",
    variants_dir: str | Path = DEFAULT_VARIANTS_DIR,
    base_dir: Path | None = None,
) -> MarkDecorator:
    """Assert that a frozen paraphrase of the input does not change the verdict.

    Args:
        k: How many paraphrases to read from the case's frozen file.
        field: Dotted path of the string the paraphrases replace.
        variants_dir: Directory holding ``<case_id>.yaml``, absolute or relative to ``base_dir``.
        base_dir: The origin for a relative ``variants_dir``; ``None`` means the working
            directory (DECISIONS 19).

    Returns:
        The pytest marker to apply to the test function.
    """
    return relation_mark(ParaphraseInvariant(k, field, variants_dir, base_dir))
