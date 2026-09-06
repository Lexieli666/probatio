"""The ``probatio`` console script: the commands a human runs, never a test.

Spec §3.13 gives this script three subcommands and one rule: the only live model calls in the
whole project happen here, in ``validate-judge --run-judge`` and ``freeze-variants``, and a person
types them. Phase 4 ships ``validate-judge``, Phase 7 ``import-cassettes``, which calls nobody at
all, and Phase 8 ``freeze-variants``.

``freeze-variants`` exists because spec §9 rejects paraphrases generated during a pytest run. It
is the deliberate act that turns a model's rewordings into a reviewed, committed file that
``paraphrase_invariant`` reads for nothing forever after; ``--provider fake`` writes mechanical
rewrites instead and says loudly that they are not paraphrases.

``validate-judge`` exists because spec §9 rejects the word "validated" for a judge with no record
on disk. It measures agreement between a judge and a human over a labelled sample and writes the
record every graded judge assertion reads back. Two modes: ``columns`` compares two columns that
already hold labels, and ``--run-judge`` produces the judge column here and now by grading each
row. Both write the same record; only the second needs a provider.

``import-cassettes`` exists because a trace of real interactions is worth more than a recording
made to order, and most of them already exist: Phase 11 turns Consilium's published traces into
the JSONL this command reads, and the tapes it writes replay through
:class:`~probatio.cassette.CassetteProvider` without a model or a network. It calls nobody, which
is why it is the one command here a test may run end to end.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal, TextIO

from .artefacts import Clock, display_path, timestamp, utc_now, write_yaml
from .case import LLMCase, load_cases
from .cassette import IMPORT_PROVIDER, CassetteStore, import_cassettes, read_trace
from .errors import JudgeOutputError, ProbatioConfigError, ProbatioError
from .judge import (
    Judge,
    KappaResult,
    Rubric,
    ValidationRecord,
    cohens_kappa,
    hash_labels_file,
    resolve_rubric,
    write_validation_record,
)
from .metamorphic import MECHANICAL_WARNING, VariantsFile, freeze_case, freeze_mechanically
from .metamorphic.freeze import GENERATED_HEADER, field_text
from .metamorphic.variants import variants_path
from .providers import Provider

__all__ = [
    "DEFAULT_CASSETTE_OUT",
    "DEFAULT_LABEL_MAP",
    "DEFAULT_VALIDATION_OUT",
    "DEFAULT_VARIANTS_OUT",
    "FREEZE_FIELD",
    "build_parser",
    "build_provider",
    "freeze_variants",
    "import_cassettes_command",
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

DEFAULT_CASSETTE_OUT: Final = Path("cassettes")
"""Where imported tapes are written when ``--out`` is not given; spec §5's location."""

DEFAULT_VARIANTS_OUT: Final = Path("variants")
"""Where frozen variants are written when ``--out`` is not given; spec §5's location."""

DEFAULT_FREEZE_K: Final = 3
"""How many paraphrases are asked for when ``--k`` is not given; ``paraphrase_invariant``'s k."""

FREEZE_FIELD: Final = "input.question"
"""The field named in the command's help, and the default ``paraphrase_invariant`` reads."""

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


def build_provider(name: str, model: str | None, timeout_s: float | None = None) -> Provider:
    """Construct one of the shipped providers by name.

    The adapters are imported inside this function so that naming ``anthropic`` without the
    optional extra installed fails here, with the message that names the extra, rather than at
    import time of the whole script.

    Args:
        name: One of :data:`PROVIDER_CHOICES`.
        model: The default model for the provider, or ``None`` for its own default.
        timeout_s: Seconds one call may take before it is killed, or ``None`` for the adapter's
            own default. Only ``claude-cli`` has one; the other two ignore it, because
            ``FakeProvider`` does not wait and the Anthropic SDK owns its own timeouts
            (DECISIONS 95).

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

        if timeout_s is None:
            return ClaudeCLIProvider(model=model)
        return ClaudeCLIProvider(model=model, timeout_s=timeout_s)
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


JUDGE_ATTEMPTS: Final = 3
"""The bound on how many times one row is asked before ``--run-judge`` gives up (DECISIONS 92).

Three attempts, counting the first. Two consecutive unparsable replies about one row is evidence
about the rubric rather than about sampling, so the third is the last; the run then stops rather
than reporting a comparison over fewer rows than it claims.
"""


def _run_judge(
    rows: Sequence[Mapping[str, str]],
    *,
    rubric: Rubric,
    provider: Provider,
    answer_column: str,
    question_column: str,
    context_column: str | None,
    label_map: Mapping[str, str],
    attempts: int = JUDGE_ATTEMPTS,
    stream: TextIO | None = None,
) -> tuple[list[str], str | None, int]:
    """Grade every row and return the judge's labels, the model, and how many rows were re-asked.

    A reply that is not a verdict at all carries no judgement of the answer, so the row is asked
    again rather than counted as a fail or allowed to end the run (DECISIONS 92). Each re-ask is
    named on the stream so that the count in the validation record can be traced to its rows.

    Args:
        rows: The labelled rows, in file order.
        rubric: The rubric to grade against.
        provider: The judge provider.
        answer_column: The column holding the output to grade.
        question_column: The column holding the question.
        context_column: The column holding the documents, when there is one.
        label_map: How a verdict is translated into the human label space.
        attempts: How many times one row may be asked. The first attempt is one of them.
        stream: Where per-row re-ask notes go. Defaults to standard error.

    Returns:
        The judge's labels, the model that produced them, and the number of rows that needed
        more than one attempt. That count can never exceed ``len(rows)``.

    Raises:
        ProbatioConfigError: A row has an empty answer.
        JudgeOutputError: The judge answered something that is not a verdict ``attempts`` times
            running, so this row has no verdict and the comparison would be over fewer rows than
            it claims.
    """
    notes = stream if stream is not None else sys.stderr
    judge = Judge(rubric, provider)
    labels: list[str] = []
    model: str | None = None
    rows_reasked = 0
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
        for attempt in range(1, attempts + 1):
            try:
                verdict, completion = judge.grade_with_completion(case, answer)
            except JudgeOutputError as exc:
                if attempt == attempts:
                    raise JudgeOutputError(
                        f"{exc} (asked row {index} {attempts} time(s); every reply was "
                        "unparsable, so this row has no verdict)"
                    ) from exc
                print(
                    f"probatio: row {index} attempt {attempt} was not a verdict, asking again: "
                    f"{exc}",
                    file=notes,
                )
                continue
            if attempt > 1:
                rows_reasked += 1
            labels.append(label_map.get(verdict.verdict, verdict.verdict))
            model = completion.model
            break
    return labels, model, rows_reasked


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
        judge_labels, judge_model, rows_reasked = _run_judge(
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
        rows_reasked = 0
        method = "columns"

    human_labels = _column(rows, args.human_column, label_map)
    result = cohens_kappa(judge_labels, human_labels)
    record = ValidationRecord(
        rubric=rubric.name,
        rubric_hash=rubric.content_hash,
        n=result.n,
        agreement=result.agreement,
        kappa=result.kappa,
        labels_file=display_path(labels_path, Path.cwd()),
        labels_hash=hash_labels_file(labels_path),
        method=method,
        judge_model=judge_model,
        rows_reasked=rows_reasked,
        created=timestamp(),
    )
    written = write_validation_record(record, validation_dir=Path(args.out))

    print(_summary_line(rubric, result, method), file=out)
    if rows_reasked:
        print(
            f"{rows_reasked} of {result.n} row(s) were asked again because the judge's first "
            f"reply was not a verdict (at most {JUDGE_ATTEMPTS} attempts per row)",
            file=out,
        )
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


def import_cassettes_command(args: argparse.Namespace, *, stream: TextIO | None = None) -> int:
    """Build cassette files from a JSONL of recorded interactions, and report what was written.

    Args:
        args: The parsed ``import-cassettes`` arguments.
        stream: Where the summary goes. Defaults to standard output.

    Returns:
        ``0``. There is no threshold here to fail: either every line parsed or the command
        raised.

    Raises:
        ProbatioError: The trace cannot be read, a line is malformed, or a case id or the suite
            name would escape the output directory.
    """
    out = stream if stream is not None else sys.stdout
    source = Path(args.source)
    store = CassetteStore(Path(args.out))
    written = import_cassettes(
        read_trace(source),
        suite=args.suite,
        store=store,
        provider=args.provider,
        source=source,
    )
    for path in written:
        print(f"wrote {path}", file=out)
    print(
        f"imported {len(written)} cassette(s) for suite {args.suite!r} from {source}",
        file=out,
    )
    return 0


def _freeze_one(
    case: LLMCase,
    args: argparse.Namespace,
    *,
    clock: Clock,
) -> VariantsFile:
    """Freeze one case, either by asking a provider or by rewriting mechanically."""
    if args.provider == "fake":
        return freeze_mechanically(case, field=args.field, k=args.k, clock=clock)
    provider = build_provider(args.provider, args.model)
    return freeze_case(case, field=args.field, k=args.k, provider=provider, clock=clock)


def freeze_variants(
    args: argparse.Namespace, *, stream: TextIO | None = None, clock: Clock = utc_now
) -> int:
    """Ask a model for paraphrases of one field of every case, and write the frozen files.

    A directory of cases is normally mixed, so a case with no text at ``--field`` is skipped with
    a note rather than failing the batch; a case whose file already exists is skipped unless
    ``--force``, because these files are reviewed by hand and overwriting them silently would
    throw that review away. If **no** case in the directory has the field, that is a mistake in
    ``--field`` rather than a batch with nothing to do, and it is an error.

    Args:
        args: The parsed ``freeze-variants`` arguments.
        stream: Where the per-file lines and the summary go. Defaults to standard output.
        clock: The clock each file's ``created`` stamp is read from. Injected by tests, so no
            test in this repository writes a wall-clock timestamp.

    Returns:
        ``0``.

    Raises:
        ProbatioError: The cases cannot be loaded, ``--field`` resolves on no case, or a reply
            does not validate.
    """
    out = stream if stream is not None else sys.stdout
    out_dir = Path(args.out)
    cases = load_cases(args.cases)
    if args.k < 1:
        raise ProbatioConfigError(f"--k must be at least 1, not {args.k}")
    if args.provider == "fake":
        print(f"probatio: {MECHANICAL_WARNING}", file=sys.stderr)

    eligible = [case for case in cases if field_text(case, args.field) is not None]
    if not eligible:
        raise ProbatioConfigError(
            f"none of the {len(cases)} case(s) under {args.cases} has text at "
            f"{args.field!r}; name the field the paraphrase_invariant decorator varies"
        )
    for case in cases:
        if field_text(case, args.field) is None:
            print(f"skipped {case.id}: no text at {args.field!r}", file=out)

    written: list[Path] = []
    for case in eligible:
        path = variants_path(case.id, out_dir)
        if path.exists() and not args.force:
            print(f"skipped {case.id}: {path} exists (pass --force to overwrite)", file=out)
            continue
        contents = _freeze_one(case, args, clock=clock)
        write_yaml(path, contents.model_dump(mode="json"), header=GENERATED_HEADER)
        written.append(path)
        print(f"wrote {path}", file=out)
    print(
        f"froze {args.k} variant(s) of {args.field!r} for {len(written)} of "
        f"{len(eligible)} eligible case(s) into {out_dir}",
        file=out,
    )
    return 0


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

    freeze = subparsers.add_parser(
        "freeze-variants",
        help="ask a model for paraphrases of one case field and write the frozen variant files",
        description=(
            "Ask the provider for --k paraphrases of --field for every case under --cases, "
            "validate the reply (exactly --k distinct non-empty strings, none of them the "
            "original), and write variants/<case_id>.yaml with the provider, model, timestamp "
            "and prompt hash that produced it. Existing files are skipped unless --force. "
            "--provider fake writes mechanical rewrites and warns that they are not paraphrases. "
            "This is one of the two commands that calls a live model, and a person runs it."
        ),
    )
    freeze.add_argument("--cases", required=True, help="case file or directory of case files")
    freeze.add_argument(
        "--field",
        required=True,
        help=f"dotted path of the text to paraphrase, such as {FREEZE_FIELD}",
    )
    freeze.add_argument(
        "--k",
        type=int,
        default=DEFAULT_FREEZE_K,
        help=f"how many paraphrases to ask for per case (default: {DEFAULT_FREEZE_K})",
    )
    freeze.add_argument(
        "--provider",
        default="fake",
        choices=PROVIDER_CHOICES,
        help="provider to ask; 'fake' writes mechanical rewrites instead (default: fake)",
    )
    freeze.add_argument("--model", help="model to ask")
    freeze.add_argument(
        "--out",
        default=str(DEFAULT_VARIANTS_OUT),
        help=f"directory the variant files are written to (default: {DEFAULT_VARIANTS_OUT})",
    )
    freeze.add_argument(
        "--force", action="store_true", help="overwrite variant files that already exist"
    )
    freeze.set_defaults(handler=freeze_variants)

    importer = subparsers.add_parser(
        "import-cassettes",
        help="build cassette files from a JSONL of already-recorded interactions",
        description=(
            "Read one JSON object per line — case_id, prompt, system, params, model, text, "
            "tokens_in, tokens_out, cost_usd, latency_ms — and write one cassette per case under "
            "<out>/<suite>/. Lines sharing a case and a call become one interaction with one "
            "sample per line, in file order, so a trace of repeated runs replays as a pass rate. "
            "This command calls no model."
        ),
    )
    importer.add_argument(
        "--from",
        dest="source",
        required=True,
        help="JSONL of recorded interactions, one JSON object per line",
    )
    importer.add_argument("--suite", required=True, help="suite name, the directory tapes go in")
    importer.add_argument(
        "--out",
        default=str(DEFAULT_CASSETTE_OUT),
        help=f"directory the tapes are written under (default: {DEFAULT_CASSETTE_OUT})",
    )
    importer.add_argument(
        "--provider",
        default=IMPORT_PROVIDER,
        help=f"the 'provider' field written into each tape (default: {IMPORT_PROVIDER})",
    )
    importer.set_defaults(handler=import_cassettes_command)
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
