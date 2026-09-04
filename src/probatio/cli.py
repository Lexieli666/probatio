"""The ``probatio`` console script: the commands a human runs, never a test.

Spec §3.13 gives this script three subcommands and one rule: the only live model calls in the
whole project happen here, in ``validate-judge --run-judge`` and ``freeze-variants``, and a person
types them. Phase 4 ships ``validate-judge``; ``freeze-variants`` and ``import-cassettes`` arrive
with the phases that implement what they write.

``validate-judge`` exists because spec §9 rejects the word "validated" for a judge with no record
on disk. It measures agreement between a judge and a human over a labelled sample and writes the
record every graded judge assertion reads back. Two modes: ``columns`` compares two columns that
already hold labels, and ``--run-judge`` produces the judge column here and now by grading each
row. Both write the same record; only the second needs a provider.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal, TextIO

from .case import LLMCase
from .errors import ProbatioConfigError, ProbatioError
from .judge import (
    Judge,
    KappaResult,
    Rubric,
    ValidationRecord,
    cohens_kappa,
    hash_labels_file,
    resolve_rubric,
    utc_now,
    write_validation_record,
)
from .providers import Provider

__all__ = [
    "DEFAULT_LABEL_MAP",
    "DEFAULT_VALIDATION_OUT",
    "build_parser",
    "build_provider",
    "main",
    "parse_label_map",
    "validate_judge",
]

DEFAULT_LABEL_MAP: Final = "pass=supported,fail=unsupported"
"""The judge answers ``pass``/``fail``; the Consilium samples are labelled ``supported``/
``unsupported``. Kappa is only defined over one label space, so judge labels are translated
through this map before they are compared (DECISIONS 25)."""

DEFAULT_VALIDATION_OUT: Final = Path(".probatio") / "judges"
"""Where a record is written when ``--out`` is not given; spec §5's location under rootdir."""

PROVIDER_CHOICES: Final = ("fake", "anthropic", "claude-cli")
"""The providers this script can construct. Only ``fake`` is ever used by a test."""


def parse_label_map(text: str) -> dict[str, str]:
    """Parse a ``--label-map`` value into a translation table.

    Args:
        text: Comma-separated ``from=to`` pairs, such as ``pass=supported,fail=unsupported``.
            The empty string means no translation.

    Returns:
        The mapping. Labels it does not mention are compared unchanged, which is what lets the
        default be applied in ``columns`` mode too, where both columns already hold human labels.

    Raises:
        ProbatioConfigError: An entry is not ``from=to``.
    """
    mapping: dict[str, str] = {}
    for entry in (part.strip() for part in text.split(",")):
        if not entry:
            continue
        source, separator, target = entry.partition("=")
        if not separator or not source.strip() or not target.strip():
            raise ProbatioConfigError(
                f"{entry!r} is not a label mapping; write pairs such as "
                f"{DEFAULT_LABEL_MAP!r} or pass an empty --label-map to compare labels verbatim"
            )
        mapping[source.strip()] = target.strip()
    return mapping


def build_provider(name: str, model: str | None) -> Provider:
    """Construct one of the shipped providers by name.

    The adapters are imported inside this function so that naming ``anthropic`` without the
    optional extra installed fails here, with the message that names the extra, rather than at
    import time of the whole script.

    Args:
        name: One of :data:`PROVIDER_CHOICES`.
        model: The default model for the provider, or ``None`` for its own default.

    Returns:
        The provider.

    Raises:
        ProbatioConfigError: The name is not a shipped provider.
    """
    if name == "fake":
        from .providers import FakeProvider

        return FakeProvider(model=model or "fake-1")
    if name == "anthropic":
        from .providers.anthropic import AnthropicProvider

        return AnthropicProvider(model=model)
    if name == "claude-cli":
        from .providers.claude_cli import ClaudeCLIProvider

        return ClaudeCLIProvider(model=model)
    raise ProbatioConfigError(
        f"{name!r} is not a provider Probatio ships; choose one of {', '.join(PROVIDER_CHOICES)}"
    )


def _read_rows(path: Path, *, required: Sequence[str]) -> list[dict[str, str]]:
    """Read a labels CSV, checking that every column the command needs is present.

    Raises:
        ProbatioConfigError: The file cannot be read, holds no rows, or lacks a named column.
    """
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            rows = [dict(row) for row in reader]
    except OSError as exc:
        raise ProbatioConfigError(f"cannot read labels file {str(path)!r}: {exc}") from exc
    if not rows:
        raise ProbatioConfigError(f"labels file {str(path)!r} holds no rows")
    missing = [column for column in required if column not in fieldnames]
    if missing:
        raise ProbatioConfigError(
            f"labels file {str(path)!r} has no column {', '.join(repr(c) for c in missing)}; "
            f"its columns are {', '.join(repr(c) for c in fieldnames)}"
        )
    return rows


def _column(
    rows: Sequence[Mapping[str, str]], column: str, label_map: Mapping[str, str]
) -> list[str]:
    """Read one label column, translated through the label map.

    Raises:
        ProbatioConfigError: A row's label is empty, so that row labels nothing.
    """
    labels: list[str] = []
    for index, row in enumerate(rows, start=1):
        raw = (row.get(column) or "").strip()
        if not raw:
            raise ProbatioConfigError(f"row {index} has no {column!r}, so it cannot be compared")
        labels.append(label_map.get(raw, raw))
    return labels


def _row_case(
    row: Mapping[str, str],
    index: int,
    *,
    rubric: Rubric,
    question_column: str,
    context_column: str | None,
) -> LLMCase:
    """Build the case one row grades as: only the columns named on the command line.

    The judge sees the question and the context and nothing else. It never sees the existing
    judge or human label columns, which would tell it the answer it is being measured against.

    Raises:
        ProbatioConfigError: Neither named column is present, so there is no input to grade.
    """
    payload: dict[str, Any] = {}
    if question_column in row:
        payload["question"] = row[question_column]
    if context_column is not None and context_column in row:
        payload["documents"] = [row[context_column]]
    if not payload:
        raise ProbatioConfigError(
            f"row {index} has neither {question_column!r} nor "
            f"{context_column!r} to build a judge prompt from; name the columns with "
            "--question-column and --context-column"
        )
    return LLMCase.model_validate(
        {
            "id": f"row-{index}",
            "input": payload,
            "assertions": [{"type": "judge", "rubric": rubric.name}],
        }
    )


def _run_judge(
    rows: Sequence[Mapping[str, str]],
    *,
    rubric: Rubric,
    provider: Provider,
    answer_column: str,
    question_column: str,
    context_column: str | None,
    label_map: Mapping[str, str],
) -> tuple[list[str], str | None]:
    """Grade every row and return the judge's labels and the model that produced them.

    Raises:
        ProbatioConfigError: A row has an empty answer.
        JudgeOutputError: The judge answered something that is not a verdict.
    """
    judge = Judge(rubric, provider)
    labels: list[str] = []
    model: str | None = None
    for index, row in enumerate(rows, start=1):
        answer = (row.get(answer_column) or "").strip()
        if not answer:
            raise ProbatioConfigError(
                f"row {index} has no {answer_column!r}, so there is nothing to grade"
            )
        case = _row_case(
            row,
            index,
            rubric=rubric,
            question_column=question_column,
            context_column=context_column,
        )
        verdict, completion = judge.grade_with_completion(case, answer)
        labels.append(label_map.get(verdict.verdict, verdict.verdict))
        model = completion.model
    return labels, model


def validate_judge(args: argparse.Namespace, *, stream: TextIO | None = None) -> int:
    """Measure a judge against human labels, write the validation record, and report.

    Args:
        args: The parsed ``validate-judge`` arguments.
        stream: Where the two-line summary goes. Defaults to standard output.

    Returns:
        ``0``, or ``1`` when ``--min-kappa`` was given and the measured kappa is below it.

    Raises:
        ProbatioError: The rubric, the labels file, a row or a judge reply is unusable.
    """
    out = stream if stream is not None else sys.stdout
    label_map = parse_label_map(args.label_map)
    rubric = resolve_rubric(args.rubric)
    labels_path = Path(args.labels)

    if args.run_judge:
        required = [args.human_column, args.answer_column]
        rows = _read_rows(labels_path, required=required)
        provider = build_provider(args.provider, args.model)
        judge_labels, judge_model = _run_judge(
            rows,
            rubric=rubric,
            provider=provider,
            answer_column=args.answer_column,
            question_column=args.question_column,
            context_column=args.context_column,
            label_map=label_map,
        )
        method: Literal["columns", "run-judge"] = "run-judge"
    else:
        if not args.judge_column:
            raise ProbatioConfigError(
                "give --judge-column to compare an existing judge column, or --run-judge to "
                "produce one now"
            )
        rows = _read_rows(labels_path, required=[args.human_column, args.judge_column])
        judge_labels = _column(rows, args.judge_column, label_map)
        judge_model = None
        method = "columns"

    human_labels = _column(rows, args.human_column, label_map)
    result = cohens_kappa(judge_labels, human_labels)
    record = ValidationRecord(
        rubric=rubric.name,
        rubric_hash=rubric.content_hash,
        n=result.n,
        agreement=result.agreement,
        kappa=result.kappa,
        labels_file=str(labels_path),
        labels_hash=hash_labels_file(labels_path),
        method=method,
        judge_model=judge_model,
        created=utc_now(),
    )
    written = write_validation_record(record, validation_dir=Path(args.out))

    print(_summary_line(rubric, result, method), file=out)
    print(f"wrote {written}", file=out)
    if args.min_kappa is not None and result.kappa < args.min_kappa:
        print(
            f"probatio: kappa {result.kappa:.3f} is below --min-kappa {args.min_kappa:.3f}",
            file=sys.stderr,
        )
        return 1
    return 0


def _summary_line(rubric: Rubric, result: KappaResult, method: str) -> str:
    """Render the first line of the summary: what was measured, and how."""
    return (
        f"judge {rubric.name!r}: n={result.n} agreement={result.agreement:.3f} "
        f"kappa={result.kappa:.3f} (method: {method}, labels: {', '.join(result.labels)})"
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the ``probatio`` script.

    Returns:
        The parser, with one subparser per implemented command.
    """
    parser = argparse.ArgumentParser(
        prog="probatio",
        description="Developer commands for the Probatio pytest plugin.",
    )
    subparsers = parser.add_subparsers(dest="command")

    validate = subparsers.add_parser(
        "validate-judge",
        help="measure a rubric judge against human labels and write its validation record",
        description=(
            "Compute agreement and Cohen's kappa between a judge and a human over a labelled "
            "sample, either from two existing columns or by running the judge on each row, and "
            "write .probatio/judges/<rubric>.validation.json."
        ),
    )
    validate.add_argument("--labels", required=True, help="CSV of labelled rows")
    validate.add_argument("--human-column", required=True, help="column holding the human labels")
    validate.add_argument("--judge-column", help="column holding existing judge labels")
    validate.add_argument(
        "--rubric",
        required=True,
        help="rubric name (resolved to rubrics/<name>.md) or an absolute path",
    )
    validate.add_argument(
        "--run-judge",
        action="store_true",
        help="grade every row now instead of reading a judge column (calls the provider)",
    )
    validate.add_argument(
        "--provider",
        default="fake",
        choices=PROVIDER_CHOICES,
        help="provider used by --run-judge (default: fake)",
    )
    validate.add_argument("--model", help="model for --run-judge")
    validate.add_argument(
        "--answer-column", default="answer", help="column holding the output to grade"
    )
    validate.add_argument(
        "--question-column", default="question", help="column holding the question"
    )
    validate.add_argument(
        "--context-column", help="column holding the documents the answer must be faithful to"
    )
    validate.add_argument(
        "--label-map",
        default=DEFAULT_LABEL_MAP,
        help=f"translate judge labels into the human label space (default: {DEFAULT_LABEL_MAP})",
    )
    validate.add_argument(
        "--min-kappa", type=float, help="exit 1 when the measured kappa is below this"
    )
    validate.add_argument(
        "--out",
        default=str(DEFAULT_VALIDATION_OUT),
        help=f"directory the validation record is written to (default: {DEFAULT_VALIDATION_OUT})",
    )
    validate.set_defaults(handler=validate_judge)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ``probatio`` command-line interface and return a process exit status.

    Args:
        argv: The arguments after the program name. Defaults to ``sys.argv[1:]``.

    Returns:
        ``0`` on success, ``1`` when a command's own threshold was not met, and ``2`` when the
        arguments, the rubric or the data are unusable. A :class:`~probatio.errors.ProbatioError`
        is reported as one line on standard error rather than as a traceback, because every one of
        them names what is wrong and, where a command fixes it, that command.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    try:
        status: int = handler(args)
    except ProbatioError as exc:
        print(f"probatio: {exc}", file=sys.stderr)
        return 2
    return status
