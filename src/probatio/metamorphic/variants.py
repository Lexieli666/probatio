"""``variants/<case_id>.yaml``: the file a human freezes once and commits.

A frozen variants file is the artefact that makes ``paraphrase_invariant`` reproducible. It is
committed to the user's repository next to the cases, reviewed like any other test data, and read
back at test time with no model involved. Like every other file Probatio persists, it carries the
provenance of what produced it: which provider, which model, when, and the hash of the prompt the
paraphrases were asked for with. ``model`` and ``prompt_hash`` are ``null`` for hand-written
variants, which is how the demo suite's two files are marked.

The loader is strict about identity and permissive about count, and both halves matter. A file
whose ``case_id`` does not match the case is refused, so a file copied to a new name does not lend
its paraphrases to the wrong question, and a file whose ``field`` does not match the relation's is
refused, so paraphrases of a question are never substituted into a document. But a file holding
fewer than ``k`` paraphrases is used as it stands: reviewing a frozen file means deleting the
rewordings that changed the meaning, and the relation reports ``n_variants`` as what it actually
evaluated. Only a file with no variants left at all is an error, because then there is nothing to
vary and the relation would silently observe nothing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..case import LLMCase
from ..errors import MissingVariantsError, ProbatioConfigError

__all__ = [
    "VARIANTS_SUFFIX",
    "VariantProvenance",
    "VariantsFile",
    "freeze_command",
    "load_variants_file",
    "read_frozen_variants",
    "variants_path",
]

VARIANTS_SUFFIX: Final = ".yaml"
"""One file per case, named for the case id, as spec §3.9 and §5 lay it out."""

_CASES_SIBLING: Final = "cases"
"""What the ``--cases`` half of the fix command guesses: the sibling of the variants directory."""


class VariantProvenance(BaseModel):
    """Where a set of frozen variants came from.

    Attributes:
        provider: The provider that produced them: a provider ``name`` such as ``claude-cli``,
            ``human`` for hand-written ones, or ``mechanical`` for the rewrites
            ``freeze-variants --provider fake`` writes.
        model: The model that produced them, or ``None`` when no model was involved.
        created: When they were produced, as a string. ``freeze-variants`` writes an ISO 8601
            instant from its clock; a hand-written file may carry a plain date.
        prompt_hash: The :func:`~probatio.hashing.stable_hash` of the prompt they were asked for
            with, or ``None`` when no prompt was sent. It is here so that a reviewer can tell
            whether two files were produced by the same request.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    model: str | None = None
    created: str
    prompt_hash: str | None = None


class VariantsFile(BaseModel):
    """The contents of one ``variants/<case_id>.yaml``.

    Attributes:
        case_id: The case these variants belong to.
        field: The dotted path the variants replace, such as ``input.question``.
        generated_by: The provenance.
        variants: The variant texts, in the order they were produced. A relation takes the first
            ``k`` of however many are left, so the order in the file is the order a reviewer sees
            and the order the relation uses. The list may be empty in the model — a reviewer who
            deleted every entry has a file that parses — and
            :func:`read_frozen_variants` is what refuses to measure over it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    field: str
    generated_by: VariantProvenance
    variants: list[str] = Field(default_factory=list)


def variants_path(case_id: str, variants_dir: Path) -> Path:
    """Return the file a case's frozen variants live in.

    Args:
        case_id: The case id.
        variants_dir: The directory holding the files.

    Returns:
        ``<variants_dir>/<case_id>.yaml``.
    """
    return variants_dir / f"{case_id}{VARIANTS_SUFFIX}"


def freeze_command(*, field: str, k: int, variants_dir: Path, force: bool = False) -> str:
    """Compose the ``probatio freeze-variants`` command that writes the missing file.

    The ``--cases`` directory is not something a relation knows: it is given to ``load_cases`` in
    the user's test module, not to the decorator. The sibling ``cases/`` of the variants
    directory is the layout spec §5 documents and the one the demo suite uses, so that is what
    the command names — and being a directory the user can correct is better than a placeholder
    they have to interpret.

    Args:
        field: The dotted path the paraphrases replace.
        k: How many the relation asked for.
        variants_dir: Where the relation reads them from, which is where the command writes them.
        force: Append ``--force``, for the case where a file is already there and has to be
            replaced rather than created.

    Returns:
        A runnable command line.
    """
    cases = variants_dir.parent / _CASES_SIBLING
    return (
        f"probatio freeze-variants --cases {cases} --field {field} "
        f"--provider claude-cli --k {k} --out {variants_dir}" + (" --force" if force else "")
    )


def load_variants_file(path: Path) -> VariantsFile:
    """Read and validate one frozen variants file.

    Args:
        path: The file to read.

    Returns:
        The validated contents.

    Raises:
        ProbatioConfigError: The file cannot be read, is not valid YAML, is not a mapping, or
            does not validate. Unknown keys are refused, as they are for a case: this file is
            written by a command and read by a relation, and a misspelled ``varients:`` that
            loaded as "no variants" would report a robustness result over nothing.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProbatioConfigError(f"cannot read frozen variants {str(path)!r}: {exc}") from exc
    try:
        document: Any = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ProbatioConfigError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(document, dict):
        raise ProbatioConfigError(
            f"{path}: a frozen variants file is a mapping with 'case_id', 'field', "
            f"'generated_by' and 'variants' keys, not a {type(document).__name__}"
        )
    try:
        return VariantsFile.model_validate(document)
    except ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first["loc"]) or "<file>"
        raise ProbatioConfigError(f"{path}: {location}: {first['msg']}") from exc


def read_frozen_variants(case: LLMCase, *, field: str, k: int, variants_dir: Path) -> list[str]:
    """Return up to ``k`` frozen variants for a case, checking they belong to it.

    A file holding fewer than ``k`` variants is used as it stands. These files are reviewed by
    hand — deleting a paraphrase that changed the meaning of the question is the reviewer's job,
    and the file's header comment is where the deletion is noted — so a short file is a decision
    somebody made, not damage. The relation reports ``n_variants`` as the number it evaluated.

    Args:
        case: The case whose variants to read.
        field: The dotted path the relation replaces; the file has to agree.
        k: The most variants to take.
        variants_dir: The directory the file lives in.

    Returns:
        The first ``k`` variant texts, in file order, or all of them when there are fewer.

    Raises:
        MissingVariantsError: There is no file for this case, or the file holds no variants at
            all. Variants are never generated at test time (spec §9), so both messages name the
            command that writes them.
        ProbatioConfigError: The file is unusable, belongs to another case, or names another
            field.
    """
    path = variants_path(case.id, variants_dir)
    if not path.is_file():
        raise MissingVariantsError(
            f"no frozen variants at {path}; paraphrases are never generated during a test run",
            case_id=case.id,
            fix=freeze_command(field=field, k=k, variants_dir=variants_dir),
        )
    contents = load_variants_file(path)
    if contents.case_id != case.id:
        raise ProbatioConfigError(
            f"{path} holds variants for {contents.case_id!r}, not for this case; the file name "
            "and its 'case_id' have to agree",
            case_id=case.id,
        )
    if contents.field != field:
        raise ProbatioConfigError(
            f"{path} holds variants of {contents.field!r} but the relation varies {field!r}; "
            "re-freeze the file for the field the relation names",
            case_id=case.id,
            fix=freeze_command(field=field, k=k, variants_dir=variants_dir),
        )
    if not contents.variants:
        raise MissingVariantsError(
            f"{path} exists but holds no variants, so there is nothing to vary",
            case_id=case.id,
            fix=freeze_command(field=field, k=k, variants_dir=variants_dir, force=True),
        )
    return contents.variants[:k]
