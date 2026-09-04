"""``LLMCase``, the five assertion declarations, the YAML loader and dotted field access.

A case is data, not code: it is the thing a user commits, diffs and reviews, so the model is
strict on purpose. Unknown keys are rejected (``extra="forbid"``), so ``assertion:`` for
``assertions:`` fails loudly at load time instead of silently testing nothing; cases are frozen,
so a metamorphic relation cannot mutate the case its neighbours are about to run; and every
loader failure names the file it came from and the field that is wrong.

The assertion models here declare the YAML surface only. Evaluating them is the assertions
package's job, so nothing in this module imports a backend, a judge or a provider.
"""

from __future__ import annotations

import copy
from collections.abc import Iterator, Mapping, MutableMapping
from pathlib import Path
from typing import Annotated, Any, Final, Literal, TypeAlias

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .errors import ProbatioConfigError

__all__ = [
    "Assertion",
    "Budget",
    "ContainsAssertion",
    "JudgeAssertion",
    "LLMCase",
    "NotContainsAssertion",
    "SchemaValidAssertion",
    "SimilarityAssertion",
    "check_field_path",
    "get_field",
    "load_cases",
    "with_field",
]

CASE_ID_PATTERN: Final = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
"""Case ids are used as file names for baselines and cassettes, so they stay path-safe."""

CASE_SUFFIXES: Final = (".yaml", ".yml")
"""The file extensions :func:`load_cases` reads when it is given a directory."""

_MAX_REPORTED_ERRORS: Final = 3
"""How many pydantic errors a loader message lists before it stops; the rest are counted."""


class _Declaration(BaseModel):
    """Base for every committed declaration: strict about keys, frozen, alias-friendly.

    ``populate_by_name`` is on because two YAML keys in the assertion vocabulary, ``any`` and
    ``all``, are Python builtins and so are declared under a trailing-underscore field name with
    the YAML spelling as their alias. With it on, ``model_dump()`` output validates again
    unchanged, which is what :func:`with_field` relies on.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class SchemaValidAssertion(_Declaration):
    """The output must be JSON that validates against a JSON Schema."""

    type: Literal["schema_valid"]
    json_schema: dict[str, Any] | None = Field(default=None, alias="schema")
    schema_file: str | None = None

    @model_validator(mode="after")
    def _exactly_one_source(self) -> SchemaValidAssertion:
        """Require a schema either inline or by path, never both and never neither."""
        if (self.json_schema is None) == (self.schema_file is None):
            raise ValueError("give exactly one of 'schema' or 'schema_file'")
        return self


class ContainsAssertion(_Declaration):
    """Substrings the output must contain: every ``all`` entry, and at least one ``any`` entry."""

    type: Literal["contains"]
    any_: list[str] = Field(default_factory=list, alias="any")
    all_: list[str] = Field(default_factory=list, alias="all")
    case_sensitive: bool = False

    @model_validator(mode="after")
    def _at_least_one_needle(self) -> ContainsAssertion:
        """Reject a contains assertion that asks for nothing and would always pass."""
        if not self.any_ and not self.all_:
            raise ValueError("give at least one of 'any' or 'all'")
        return self


class NotContainsAssertion(_Declaration):
    """Substrings none of which may appear in the output."""

    type: Literal["not_contains"]
    all_: list[str] = Field(alias="all", min_length=1)
    case_sensitive: bool = False


class SimilarityAssertion(_Declaration):
    """The output must score at least ``tau`` against ``reference`` on a similarity backend."""

    type: Literal["similarity"]
    reference: str
    tau: float = Field(ge=0.0, le=1.0)
    backend: str = "trigram"


class JudgeAssertion(_Declaration):
    """A rubric judge must return a passing verdict scoring at least ``threshold``."""

    type: Literal["judge"]
    rubric: str
    threshold: float = Field(default=1.0, ge=0.0, le=1.0)
    provider: str | None = None


Assertion: TypeAlias = Annotated[
    SchemaValidAssertion
    | ContainsAssertion
    | NotContainsAssertion
    | SimilarityAssertion
    | JudgeAssertion,
    Field(discriminator="type"),
]
"""One assertion declaration, discriminated on its ``type`` key."""


class Budget(_Declaration):
    """Per-case cost and latency ceilings; ``None`` means the case declares no ceiling."""

    max_cost_usd: float | None = Field(default=None, ge=0.0)
    max_latency_ms: float | None = Field(default=None, ge=0.0)


class LLMCase(_Declaration):
    """One regression case: an input, what must be true of the output, and what it may cost."""

    id: str = Field(pattern=CASE_ID_PATTERN)
    input: str | dict[str, Any]
    system: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    assertions: list[Assertion] = Field(min_length=1)
    budget: Budget = Field(default_factory=Budget)
    snapshot: Literal["off", "scores", "output"] = "off"
    tags: list[str] = Field(default_factory=list)


_MISSING: Final = object()
"""Sentinel distinguishing "no default was given" from "the default is ``None``"."""


def check_field_path(path: str) -> list[str]:
    """Split a dotted field path, rejecting the empty segments a stray dot leaves behind.

    A metamorphic relation is constructed with a field path long before any case is loaded, so it
    calls this at construction time to fail on ``""`` or ``"input..question"`` there rather than
    reporting every case in the suite as "not applicable" (DECISIONS 8, 13).

    Args:
        path: The candidate dotted path, such as ``input.documents``.

    Returns:
        The path's segments, in order.

    Raises:
        ProbatioConfigError: The path is empty or holds an empty segment.
    """
    segments = path.split(".")
    if not path or any(not segment for segment in segments):
        raise ProbatioConfigError(
            f"{path!r} is not a field path; write dotted names such as 'input.documents'"
        )
    return segments


def _root(case: LLMCase, path: str) -> tuple[str, list[str]]:
    """Split a path into its ``LLMCase`` field and the mapping keys under it."""
    root, *rest = check_field_path(path)
    if root not in type(case).model_fields:
        raise ProbatioConfigError(
            f"{path!r} starts at {root!r}, which is not a field of LLMCase; the fields are "
            f"{sorted(type(case).model_fields)}",
            case_id=case.id,
        )
    return root, rest


def get_field(case: LLMCase, path: str, default: Any = _MISSING) -> Any:
    """Read a dotted field path such as ``input.documents`` off a case.

    A path whose first segment is not a field of :class:`LLMCase` is always an error, even when a
    default is given: that is a mistake in the relation or the flag that named the path, and every
    case in the suite would be affected. A path whose later segments do not resolve is ordinary
    data variation, so it returns ``default`` when one was given; a relation uses that to report
    itself "not applicable" on a case whose input is a bare string.

    Args:
        case: The case to read from.
        path: Dotted path: an ``LLMCase`` field, then mapping keys under it.
        default: Returned when the path does not resolve. Omit it to get an error instead.

    Returns:
        The value at ``path``, or ``default``.

    Raises:
        ProbatioConfigError: The path is malformed, does not start at an ``LLMCase`` field, or
            does not resolve and no ``default`` was given.
    """
    root, rest = _root(case, path)
    value: Any = getattr(case, root)
    walked = [root]
    for segment in rest:
        if isinstance(value, Mapping) and segment in value:
            value = value[segment]
            walked.append(segment)
            continue
        if default is not _MISSING:
            return default
        raise ProbatioConfigError(
            f"the case has no {path!r}: {segment!r} is not a key of the value at "
            f"{'.'.join(walked)!r}",
            case_id=case.id,
        )
    return value


def with_field(case: LLMCase, path: str, value: Any) -> LLMCase:
    """Return a copy of ``case`` with the value at a dotted field path replaced.

    Cases are frozen, so this is how a metamorphic relation builds a variant. The leaf key has to
    exist already: a relation that names a field the case does not have has generated nothing, and
    inventing the key would report a robustness result for an input the app never receives.

    Args:
        case: The case to copy.
        path: Dotted path, as in :func:`get_field`.
        value: The replacement value; it is validated against the case model.

    Returns:
        A new, validated :class:`LLMCase`. ``case`` itself is untouched.

    Raises:
        ProbatioConfigError: The path is malformed, does not resolve, or the replacement makes the
            case invalid.
    """
    root, rest = _root(case, path)
    data = copy.deepcopy(case.model_dump())
    if not rest:
        data[root] = value
    else:
        container: Any = data[root]
        for segment in rest[:-1]:
            if not isinstance(container, MutableMapping) or segment not in container:
                raise ProbatioConfigError(
                    f"the case has no {path!r}, so there is nothing to replace", case_id=case.id
                )
            container = container[segment]
        if not isinstance(container, MutableMapping) or rest[-1] not in container:
            raise ProbatioConfigError(
                f"the case has no {path!r}, so there is nothing to replace", case_id=case.id
            )
        container[rest[-1]] = value
    try:
        return LLMCase.model_validate(data)
    except ValidationError as exc:
        raise ProbatioConfigError(
            f"replacing {path!r} makes the case invalid: {_describe(exc)}", case_id=case.id
        ) from exc


def _describe(exc: ValidationError) -> str:
    """Render the first few pydantic errors as ``field: message``, naming the field paths."""
    errors = exc.errors()
    described = [
        f"{'.'.join(str(part) for part in error['loc']) or '<case>'}: {error['msg']}"
        for error in errors[:_MAX_REPORTED_ERRORS]
    ]
    remaining = len(errors) - len(described)
    if remaining > 0:
        described.append(f"and {remaining} more")
    return "; ".join(described)


def _case_files(path: Path) -> list[Path]:
    """List the YAML files a path names, sorted so that two runs load them in one order."""
    if path.is_dir():
        found = [
            candidate
            for candidate in path.rglob("*")
            if candidate.is_file() and candidate.suffix in CASE_SUFFIXES
        ]
        if not found:
            raise ProbatioConfigError(f"{path} holds no {' or '.join(CASE_SUFFIXES)} case files")
        return sorted(found)
    if path.is_file():
        return [path]
    raise ProbatioConfigError(f"{path} does not exist, so there are no cases to load")


def _documents(path: Path) -> Iterator[object]:
    """Parse a YAML file into its documents, naming the file and the line on a syntax error."""
    text = path.read_text(encoding="utf-8")
    try:
        yield from yaml.safe_load_all(text)
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark
        where = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise ProbatioConfigError(f"{path}: invalid YAML{where}: {exc.problem}") from exc
    except yaml.YAMLError as exc:
        raise ProbatioConfigError(f"{path}: invalid YAML: {exc}") from exc


def _mappings(path: Path) -> Iterator[Mapping[str, Any]]:
    """Yield one mapping per case in a file, accepting a single mapping or a list of them."""
    for index, document in enumerate(_documents(path)):
        if document is None:
            continue
        entries = document if isinstance(document, list) else [document]
        for position, entry in enumerate(entries):
            if not isinstance(entry, Mapping):
                raise ProbatioConfigError(
                    f"{path}: document {index + 1}, entry {position + 1} is a "
                    f"{type(entry).__name__}, but a case is a mapping with an 'id' key"
                )
            yield entry


def _load_file(path: Path) -> Iterator[LLMCase]:
    """Validate every case in one file, naming the file and the offending field on failure."""
    for entry in _mappings(path):
        try:
            yield LLMCase.model_validate(entry)
        except ValidationError as exc:
            case_id = entry.get("id")
            raise ProbatioConfigError(
                f"{path}: {_describe(exc)}",
                case_id=str(case_id) if isinstance(case_id, str) else None,
            ) from exc


def load_cases(path: str | Path) -> list[LLMCase]:
    """Load every case under a file or directory, in a stable order.

    A directory is walked recursively and its ``.yaml`` and ``.yml`` files are loaded in sorted
    path order, so the parametrised test ids a suite reports do not depend on the filesystem. A
    file may hold one mapping, a list of mappings, or several YAML documents.

    Args:
        path: A case file or a directory of them.

    Returns:
        The cases, in path order and then in file order.

    Raises:
        ProbatioConfigError: The path does not exist, a file is not valid YAML, a case does not
            validate, or two cases share an id.
    """
    root = Path(path)
    cases: list[LLMCase] = []
    origin: dict[str, Path] = {}
    for file in _case_files(root):
        for case in _load_file(file):
            if case.id in origin:
                raise ProbatioConfigError(
                    f"{file}: duplicate case id, already defined in {origin[case.id]}; ids "
                    "name the baseline and cassette files, so they have to be unique",
                    case_id=case.id,
                )
            origin[case.id] = file
            cases.append(case)
    return cases
