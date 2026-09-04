"""What ``probatio freeze-variants`` does: ask once, validate hard, write provenance.

Freezing is the deliberate act that keeps ``paraphrase_invariant`` honest. A human runs this with
a model behind them, reads what came back, and commits it; every test run afterwards reads the
file. That is why the validation here is stricter than a parser needs to be: this is the last
moment a person is in the loop, so a reply with two paraphrases instead of three, a duplicate, or
one that is just the original question again has to be a visible failure rather than a file that
quietly measures less than the suite claims.

``--provider fake`` writes mechanical rewrites instead of calling anything. They are not
paraphrases and the command says so on standard error, twice over: once as a warning line, and
once in the file's own ``generated_by.provider``, which reads ``mechanical``. They exist so that
the whole ``freeze-variants`` path — the argument handling, the skip-unless-``--force`` rule, the
file layout — can be exercised, and so a user can see the shape of a variants file before
spending a model call on one.
"""

from __future__ import annotations

import json
from typing import Any, Final

from ..artefacts import Clock, timestamp, utc_now
from ..assertions import strip_code_fence
from ..case import LLMCase, get_field
from ..errors import ProbatioConfigError
from ..hashing import stable_hash
from ..providers import Provider
from .variants import VariantProvenance, VariantsFile

__all__ = [
    "FREEZE_PROMPT_TEMPLATE",
    "GENERATED_HEADER",
    "MECHANICAL_PROVIDER",
    "MECHANICAL_TEMPLATES",
    "MECHANICAL_WARNING",
    "build_freeze_prompt",
    "freeze_case",
    "freeze_mechanically",
    "mechanical_rewrites",
    "parse_paraphrases",
]

FREEZE_PROMPT_TEMPLATE: Final = """\
Rewrite the question below as {k} different paraphrases.

Rules:
- Keep the meaning exactly. A correct answer to the original must be a correct answer to every
  paraphrase, and the other way round.
- Do not add, remove or weaken any condition the question states.
- Vary the wording and the sentence structure, not the question.
- Every paraphrase must differ from the original and from the others.

Reply with a JSON array of exactly {k} strings and nothing else: no prose, no code fence, no keys.

Question:
{original}
"""
"""The prompt a paraphrase request sends. Its hash goes into every file this command writes, so
a reviewer can tell which files were produced by which version of the request."""

MECHANICAL_PROVIDER: Final = "mechanical"
"""What ``generated_by.provider`` says for ``--provider fake``: no model produced these."""

MECHANICAL_WARNING: Final = (
    "warning: --provider fake writes mechanical rewrites, not paraphrases; they change the "
    "wording of the request without rewording the question, so a violation rate measured over "
    "them is not a paraphrase-invariance result. Re-freeze with --provider claude-cli or "
    "--provider anthropic before you rely on it."
)
"""The line printed whenever mechanical rewrites are written, as spec §3.13 requires."""

MECHANICAL_TEMPLATES: Final = (
    "Please answer this question: {original}",
    "{original} Answer using the documents provided.",
    "Question - {original}",
)
"""The fixed rewrites, cycled with a suffix when more than three are asked for."""

GENERATED_HEADER: Final = (
    "Written by 'probatio freeze-variants'. Read these before you trust them: a paraphrase that",
    "changes a condition makes the relation measure the paraphraser, not the application.",
)
"""The comment written above a generated file, because a person is meant to review it."""


def build_freeze_prompt(original: str, k: int) -> str:
    """Render the paraphrase request for one field value.

    Args:
        original: The text to paraphrase.
        k: How many paraphrases to ask for.

    Returns:
        The prompt, which is also what :func:`~probatio.hashing.stable_hash` is taken over for
        the file's ``prompt_hash``.
    """
    return FREEZE_PROMPT_TEMPLATE.format(k=k, original=original)


def parse_paraphrases(reply: str, *, original: str, k: int, case_id: str) -> list[str]:
    """Parse and validate a model's reply to :func:`build_freeze_prompt`.

    Args:
        reply: The model's raw reply. One wrapping code fence is stripped, because a model told
            not to use one sometimes does anyway and that is not a reason to lose the call.
        original: The text that was paraphrased; no paraphrase may equal it.
        k: Exactly how many paraphrases the reply must hold.
        case_id: Named in every error, so a batch over a directory says which case failed.

    Returns:
        The ``k`` paraphrases, stripped of surrounding whitespace, in reply order.

    Raises:
        ProbatioConfigError: The reply is not a JSON array of exactly ``k`` distinct non-empty
            strings, or one of them is the original.
    """
    text = strip_code_fence(reply).strip()
    try:
        parsed: Any = json.loads(text)
    except ValueError as exc:
        raise ProbatioConfigError(
            f"the paraphrase reply is not JSON ({exc}); the first 200 characters were "
            f"{text[:200]!r}",
            case_id=case_id,
        ) from exc
    if not isinstance(parsed, list):
        raise ProbatioConfigError(
            f"the paraphrase reply is a JSON {type(parsed).__name__}, not an array of strings",
            case_id=case_id,
        )
    if len(parsed) != k:
        raise ProbatioConfigError(
            f"the paraphrase reply holds {len(parsed)} entries but {k} were asked for; freezing "
            "fewer than the relation reads would report a rate over variants that do not exist",
            case_id=case_id,
        )
    paraphrases: list[str] = []
    for position, entry in enumerate(parsed, start=1):
        if not isinstance(entry, str) or not entry.strip():
            raise ProbatioConfigError(
                f"paraphrase {position} is not a non-empty string but a {type(entry).__name__}",
                case_id=case_id,
            )
        candidate = entry.strip()
        if candidate == original.strip():
            raise ProbatioConfigError(
                f"paraphrase {position} is the original text; a variant identical to the case "
                "measures nothing",
                case_id=case_id,
            )
        if candidate in paraphrases:
            raise ProbatioConfigError(
                f"paraphrase {position} repeats an earlier one; {k} distinct paraphrases were "
                "asked for",
                case_id=case_id,
            )
        paraphrases.append(candidate)
    return paraphrases


def mechanical_rewrites(original: str, k: int) -> list[str]:
    """Return ``k`` deterministic rewrites of a text, for ``--provider fake``.

    Args:
        original: The text to rewrite.
        k: How many rewrites to produce.

    Returns:
        The rewrites: :data:`MECHANICAL_TEMPLATES` in order, cycled with a numbered suffix beyond
        the third, so any ``k`` yields distinct non-empty texts that differ from the original.
    """
    rewrites: list[str] = []
    for index in range(k):
        text = MECHANICAL_TEMPLATES[index % len(MECHANICAL_TEMPLATES)].format(original=original)
        if index >= len(MECHANICAL_TEMPLATES):
            text = f"{text} (rewrite {index + 1})"
        rewrites.append(text)
    return rewrites


def field_text(case: LLMCase, field: str) -> str | None:
    """Read the text a freeze request paraphrases, or ``None`` when the case has none.

    Args:
        case: The case.
        field: The dotted path, such as ``input.question``.

    Returns:
        The string at ``field``, or ``None`` when it does not resolve or is not a string. A
        directory of cases is usually mixed, so a case without the field is skipped, not fatal.

    Raises:
        ProbatioConfigError: ``field`` does not start at a field of :class:`~probatio.case.
            LLMCase`, which is a mistake in the flag rather than in the case (DECISIONS 13).
    """
    value = get_field(case, field, default=None)
    return value if isinstance(value, str) else None


def freeze_case(
    case: LLMCase, *, field: str, k: int, provider: Provider, clock: Clock = utc_now
) -> VariantsFile:
    """Ask a provider for ``k`` paraphrases of one case's field and build the file to write.

    This is the one function in :mod:`probatio.metamorphic` that calls a provider, and nothing in
    the test suite reaches it with anything but a :class:`~probatio.providers.FakeProvider`.

    Args:
        case: The case to freeze.
        field: The dotted path to paraphrase.
        k: How many paraphrases to ask for.
        provider: The provider to ask.
        clock: The clock the ``created`` stamp is read from.

    Returns:
        The validated file contents, with the provider's name, the model that answered, the
        stamp and the prompt hash as provenance.

    Raises:
        ProbatioConfigError: The case has no text at ``field``, or the reply does not validate.
    """
    original = field_text(case, field)
    if original is None:
        raise ProbatioConfigError(
            f"the case has no text at {field!r}, so there is nothing to paraphrase",
            case_id=case.id,
        )
    prompt = build_freeze_prompt(original, k)
    completion = provider.complete(prompt)
    paraphrases = parse_paraphrases(completion.text, original=original, k=k, case_id=case.id)
    return VariantsFile(
        case_id=case.id,
        field=field,
        generated_by=VariantProvenance(
            provider=provider.name,
            model=completion.model,
            created=timestamp(clock),
            prompt_hash=stable_hash(prompt),
        ),
        variants=paraphrases,
    )


def freeze_mechanically(
    case: LLMCase, *, field: str, k: int, clock: Clock = utc_now
) -> VariantsFile:
    """Build a variants file of mechanical rewrites, calling nothing.

    Args:
        case: The case to rewrite.
        field: The dotted path to rewrite.
        k: How many rewrites to produce.
        clock: The clock the ``created`` stamp is read from.

    Returns:
        The file contents, with ``generated_by.provider`` set to :data:`MECHANICAL_PROVIDER` and
        no model and no prompt hash, because no prompt was sent.

    Raises:
        ProbatioConfigError: The case has no text at ``field``.
    """
    original = field_text(case, field)
    if original is None:
        raise ProbatioConfigError(
            f"the case has no text at {field!r}, so there is nothing to rewrite", case_id=case.id
        )
    return VariantsFile(
        case_id=case.id,
        field=field,
        generated_by=VariantProvenance(
            provider=MECHANICAL_PROVIDER,
            model=None,
            created=timestamp(clock),
            prompt_hash=None,
        ),
        variants=mechanical_rewrites(original, k),
    )
