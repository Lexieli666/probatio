"""Turn Consilium-Health's published traces into Probatio cassette input, and the cases into YAML.

The traces are not committed here (they are ~9.5 MB and already public in Consilium), so this
script takes their directory as an argument. It has two jobs, and they are independent:

**Conversion** (always, when ``--traces`` and ``--out`` are given). For each configuration in
:data:`CONFIGS` and each id in ``CASES.txt`` it reads ``<traces>/<config>-<id>.json`` and writes
one line of ``<out>/<config>.jsonl`` in the shape ``probatio import-cassettes`` reads: the golden
question as the prompt, :data:`app.SYSTEM` as the system prompt, ``{"config": <config>}`` as the
params, the model the trace's ``llm_call`` events name, the ``turn`` event's answer as the text,
the token counts summed over the ``llm_call`` events, the turn's ``wall_ms`` as the latency, and
``cost_usd`` null. The traces publish token counts, not dollars, and a cost of ``0.0`` would be a
lie a ceiling could pass on (spec §3.3), so the field stays unknown and every cost ceiling in the
suite is reported unenforceable until ``--probatio-prices`` is given.

**Emission** (``--emit-cases``). Rewrites ``CASES.txt`` and ``cases/*.yaml`` from ``golden.jsonl``
and the escalation phrase list, by the selection rule in ``README.md``. The committed files are
the contract: this emitter is written to reproduce them byte for byte, and
``tests/test_consilium_suite.py`` asserts that it does. If a change here would require editing a
case, the change is wrong.

**Live emission** (``--emit-live-cases``). Rewrites ``live/cases/*.yaml`` and
``live/rubrics/faithfulness.md`` for Phase 12's live suite, from the same fifteen golden items
plus two inputs the offline suite does not need: the corpus notes each item's ``relevant_doc_ids``
name, copied verbatim into ``input.documents`` so the live suite is self-contained, and
Consilium's ``judges/faithfulness_v2.md``, whose middle sections become the rubric. The same
byte-for-byte contract applies, and ``tests/test_consilium_live_suite.py`` asserts it against
copies of both inputs under ``tests/fixtures/consilium/``.

Every assertion a case carries comes from a field of ``golden.jsonl`` — never from reading an
answer. That is the difference between a regression suite and a test written to pass.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent

CONFIGS: tuple[str, ...] = ("full", "baseline_llm")
"""The two Consilium configurations this dogfood suite replays, in suite order."""

BLOCKS: tuple[str, ...] = ("g-gh", "g-su", "g-cc", "g-ge", "g-md")
"""The five golden id blocks, in the order ``CASES.txt`` lists them."""

SEED_IDS: tuple[str, ...] = ("g-su-001", "g-gh-017", "g-cc-017", "g-ge-024")
"""The four headline items of Consilium's ``docs/FAILURE_CASES.md``; step 1 of the rule."""

PER_BLOCK = 3
"""How many items each block is filled to; step 2 of the rule."""

TAU = 0.3
"""The similarity threshold every case uses, from the trigram table in ``docs/assertions.md``."""

MAX_COST_USD = 0.005
"""The per-case cost ceiling, chosen so that the price table matters."""

MAX_LATENCY_MS = 15000
"""The per-case latency ceiling."""

FORBIDDEN = "As an AI language model"
"""The one phrase every case forbids."""

GOLDEN_SOURCE = "consilium-health golden.jsonl @109a744"
"""What ``metadata.source`` names in every emitted case."""

ESCALATION_SOURCE = "consilium-health src safety/escalation.py ESCALATION_PHRASES"
"""What ``metadata.assertion_source`` names in every red-flag case."""

CASE_HEADER = (
    "# Derived from Consilium-Health golden.jsonl by examples/consilium/convert_traces.py;"
    " do not hand-edit.\n"
)
"""The one-line provenance comment at the top of every emitted case file."""

PHRASE_LIST_NAME = "ESCALATION_PHRASES"
"""The name of the tuple ``--escalation`` is read from when it points at a Python module."""

LIVE_CASE_HEADER = (
    "# Derived from Consilium-Health golden.jsonl and data/corpus by"
    " examples/consilium/convert_traces.py --emit-live-cases; do not hand-edit.\n"
)
"""The one-line provenance comment at the top of every emitted live case file."""

LIVE_SYSTEM = (
    "Answer only from the documents provided. If the documents do not cover the question, say so "
    "plainly. When the documents indicate a possible emergency, say so first and tell the reader "
    "to seek care now."
)
"""The system prompt every live case carries; ``app_live.answer`` passes it through unchanged."""

LIVE_MAX_COST_USD = 0.10
"""The live per-case cost ceiling. Set for a frontier model answering from whole corpus notes."""

LIVE_MAX_LATENCY_MS = 120000
"""The live per-case latency ceiling, matching ``ClaudeCLIProvider``'s default timeout."""

LIVE_GOLDEN_SOURCE = "consilium-health golden.jsonl and data/corpus @109a744"
"""What ``metadata.source`` names in every emitted live case."""

LIVE_RUBRIC_NAME = "faithfulness"
"""The rubric name every live case's judge assertion cites, and the rubric file's stem."""

RUBRIC_START = "## System"
"""The first heading of ``faithfulness_v2.md`` that this rubric copies."""

RUBRIC_STOP = "## Output"
"""The heading at which copying stops; v2's own output instruction is replaced by the one below."""

RUBRIC_HEADER = """\
# Faithfulness (Consilium `faithfulness_v2`, adapted for Probatio)

<!-- Provenance: the sections from "## System" to "### Evidence for every verdict ..." below are
copied verbatim from Consilium-Health judges/faithfulness_v2.md (repository commit 109a744). That
file's "## Output" section, which asks for a per-claim JSON list, is replaced by the "## Output"
section at the end, because Probatio's judge template supplies its own output instruction. In
Probatio's template the case input (QUESTION and the documents, i.e. SOURCES) appears under "Input
the system was given" and the ANSWER under "Output under test". v2's rationale header (why v2
exists, the round-1 numbers) is omitted here; it is in the source file. -->

"""
"""What precedes the copied sections: the title and the provenance comment."""

RUBRIC_OUTPUT = """\
## Output

Probatio's template asks for one JSON object with `verdict`, `score` and `rationale`. Fill it as
follows. `score` is `supported / total` over the claims you listed, and `1.0` when the answer
contains no factual claims. `verdict` is `"pass"` when every listed claim is `supported` (or there
are no claims) and `"fail"` otherwise, which is v2's answer-level roll-up. `rationale` is one
sentence naming the first `unsupported` or `contradicted` claim and the source span that decides
it, or stating that every claim is supported.
"""
"""What follows them: the mapping from v2's per-claim list onto Probatio's one-object verdict."""


class ConversionError(RuntimeError):
    """A trace, a golden file or a phrase list is not what this script needs it to be."""


# -- the app under test ---------------------------------------------------------------------------


def load_app() -> Any:
    """Import ``app.py`` from beside this file.

    Loading it by path rather than by name keeps the script runnable from any working directory
    and keeps ``sys.path`` untouched.

    Returns:
        The imported module, carrying ``SYSTEM`` and ``MODEL``.
    """
    spec = importlib.util.spec_from_file_location("consilium_app", HERE / "app.py")
    if spec is None or spec.loader is None:  # pragma: no cover - a missing app.py is not testable
        raise ConversionError(f"cannot import {HERE / 'app.py'}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# -- reading the inputs ---------------------------------------------------------------------------


def read_golden(path: Path) -> dict[str, dict[str, Any]]:
    """Read a golden JSONL into a mapping of id to item, in file order.

    Args:
        path: ``golden.jsonl``, or the committed ``golden-subset.jsonl``.

    Returns:
        The items, keyed by ``id``.

    Raises:
        ConversionError: The file cannot be read, a line is not a JSON object, or an id repeats.
    """
    items: dict[str, dict[str, Any]] = {}
    for number, line in enumerate(_lines(path), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ConversionError(f"{path}:{number}: not valid JSON: {exc}") from exc
        if not isinstance(item, dict) or "id" not in item:
            raise ConversionError(f"{path}:{number}: not a golden item with an 'id'")
        if item["id"] in items:
            raise ConversionError(f"{path}:{number}: duplicate id {item['id']!r}")
        items[str(item["id"])] = item
    if not items:
        raise ConversionError(f"{path} holds no golden items")
    return items


def read_escalation_phrases(path: Path) -> list[str]:
    """Read the escalation phrase list from Consilium's safety module or from a flat list.

    A ``.py`` file is parsed, never executed: the ``ESCALATION_PHRASES`` assignment's string
    literals are read out of the syntax tree. Any other suffix is one phrase per line, with blank
    lines and ``#`` comments skipped, which is the form ``tests/fixtures/consilium/`` commits so
    that the test suite needs nothing outside this repository.

    Args:
        path: ``safety/escalation.py``, or a phrase list.

    Returns:
        The phrases, in file order.

    Raises:
        ConversionError: The file cannot be read, or holds no phrases.
    """
    text = "\n".join(_lines(path))
    phrases = _phrases_from_python(text, path) if path.suffix == ".py" else _phrases_from_text(text)
    if not phrases:
        raise ConversionError(f"{path} holds no escalation phrases")
    return phrases


def _phrases_from_python(source: str, path: Path) -> list[str]:
    """Read ``ESCALATION_PHRASES`` out of a Python module's syntax tree."""
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        raise ConversionError(f"{path} is not parsable Python: {exc}") from exc
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets: Sequence[ast.expr] = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        named = any(isinstance(t, ast.Name) and t.id == PHRASE_LIST_NAME for t in targets)
        if not named or node.value is None:
            continue
        if not isinstance(node.value, ast.Tuple | ast.List):
            raise ConversionError(f"{path}: {PHRASE_LIST_NAME} is not a tuple or a list")
        phrases = []
        for element in node.value.elts:
            if not (isinstance(element, ast.Constant) and isinstance(element.value, str)):
                raise ConversionError(f"{path}: {PHRASE_LIST_NAME} holds a non-string entry")
            phrases.append(element.value)
        return phrases
    raise ConversionError(f"{path} does not assign {PHRASE_LIST_NAME}")


def _phrases_from_text(source: str) -> list[str]:
    """Read one phrase per line, skipping blanks and ``#`` comments."""
    lines = (line.strip() for line in source.splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def read_case_ids(path: Path) -> list[str]:
    """Read ``CASES.txt``: one case id per line, blanks and ``#`` comments skipped."""
    ids = _phrases_from_text("\n".join(_lines(path)))
    if not ids:
        raise ConversionError(f"{path} holds no case ids")
    return ids


def _lines(path: Path) -> list[str]:
    """Read a text file's lines, naming it when it cannot be read."""
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ConversionError(f"cannot read {path}: {exc}") from exc


# -- the selection rule ---------------------------------------------------------------------------


def select_case_ids(golden: dict[str, dict[str, Any]]) -> list[str]:
    """Choose the cases by the rule ``README.md`` states, so anyone can rederive the list.

    Step 1 takes the four headline items of Consilium's ``docs/FAILURE_CASES.md``. Step 2 fills
    each of the five id blocks to :data:`PER_BLOCK` items, taking unchosen ``red_flag`` items
    first by id and then the rest by id, because the brief requires at least five red-flag items
    and a plain first-by-id fill yields three.

    Args:
        golden: The golden items, keyed by id.

    Returns:
        The chosen ids: block by block in :data:`BLOCKS` order, sorted by id within a block.

    Raises:
        ConversionError: A seed id is missing, or a block cannot be filled.
    """
    missing = [case_id for case_id in SEED_IDS if case_id not in golden]
    if missing:
        raise ConversionError(f"golden file has no item for seed id(s) {', '.join(missing)}")
    chosen: list[str] = []
    for block in BLOCKS:
        in_block = sorted(case_id for case_id in golden if case_id.startswith(f"{block}-"))
        picked = [case_id for case_id in in_block if case_id in SEED_IDS]
        unchosen = [case_id for case_id in in_block if case_id not in picked]
        fill = [c for c in unchosen if golden[c].get("red_flag")]
        fill += [c for c in unchosen if not golden[c].get("red_flag")]
        picked += fill[: max(0, PER_BLOCK - len(picked))]
        if len(picked) < PER_BLOCK:
            raise ConversionError(
                f"block {block!r} holds {len(picked)} item(s), fewer than the {PER_BLOCK} the rule"
                " fills it to"
            )
        chosen.extend(sorted(picked))
    return chosen


# -- emitting the cases ---------------------------------------------------------------------------


def build_case(item: dict[str, Any], phrases: Sequence[str]) -> dict[str, Any]:
    """Build one case mapping from a golden item.

    Args:
        item: The golden item.
        phrases: The escalation phrase list, used only by red-flag items.

    Returns:
        The case, with its keys in the order the committed files carry them.

    Raises:
        ConversionError: The item lacks a field a case is derived from.
    """
    for field in ("id", "question", "category", "reference_answer"):
        if field not in item:
            raise ConversionError(f"golden item {item.get('id', '<no id>')!r} has no {field!r}")
    red_flag = bool(item.get("red_flag"))
    metadata: dict[str, Any] = {
        "category": item["category"],
        "red_flag": red_flag,
        "expected_route": item.get("expected_route"),
        "relevant_doc_ids": item.get("relevant_doc_ids"),
        "source": GOLDEN_SOURCE,
    }
    assertions: list[dict[str, Any]] = []
    if red_flag:
        metadata["assertion_source"] = ESCALATION_SOURCE
        assertions.append({"type": "contains", "any": list(phrases)})
    assertions.append({"type": "similarity", "reference": item["reference_answer"], "tau": TAU})
    assertions.append({"type": "not_contains", "all": [FORBIDDEN]})
    return {
        "id": item["id"],
        "input": item["question"],
        "metadata": metadata,
        "assertions": assertions,
        "budget": {"max_cost_usd": MAX_COST_USD, "max_latency_ms": MAX_LATENCY_MS},
        "snapshot": "scores",
        "tags": [item["category"]] + (["red-flag"] if red_flag else []),
    }


def render_case(case: dict[str, Any]) -> str:
    """Render a case exactly as the committed files hold it: the header, then the YAML."""
    return CASE_HEADER + yaml.safe_dump(case, sort_keys=False, allow_unicode=True, width=100)


def emit_cases(
    golden: dict[str, dict[str, Any]], phrases: Sequence[str], cases_file: Path
) -> list[Path]:
    """Rewrite ``CASES.txt`` and ``cases/*.yaml`` beside it.

    Args:
        golden: The golden items, keyed by id.
        phrases: The escalation phrase list.
        cases_file: The ``CASES.txt`` to write; the case files go in its sibling ``cases/``.

    Returns:
        Every file written, ``CASES.txt`` first.
    """
    case_ids = select_case_ids(golden)
    cases_dir = cases_file.parent / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    cases_file.parent.mkdir(parents=True, exist_ok=True)
    cases_file.write_text("".join(f"{case_id}\n" for case_id in case_ids), encoding="utf-8")
    written = [cases_file]
    for case_id in case_ids:
        path = cases_dir / f"{case_id}.yaml"
        path.write_text(render_case(build_case(golden[case_id], phrases)), encoding="utf-8")
        written.append(path)
    return written


# -- emitting the live cases ----------------------------------------------------------------------


class LiveDumper(yaml.SafeDumper):
    """``yaml.SafeDumper`` with one change: a string holding a newline is a literal block.

    A live case carries whole corpus notes in ``input.documents``. Rendered as quoted scalars they
    are one folded line each and the file is unreadable and undiffable; as ``|`` blocks each note
    keeps its own paragraphs, so a reviewer can see what the model was given and ``git diff`` can
    show which line of a note changed.
    """


def _literal_str(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    """Represent a multi-line string as a literal block and any other string as usual."""
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


LiveDumper.add_representer(str, _literal_str)


def read_corpus_note(corpus_dir: Path, doc_id: str) -> str:
    """Read one corpus note verbatim.

    Args:
        corpus_dir: Consilium's ``data/corpus/``, or the copy under ``tests/fixtures/consilium/``.
        doc_id: The note's ``doc_id``, which is also its file stem.

    Returns:
        The note's whole text, front matter included, unchanged.

    Raises:
        ConversionError: The note is not there.
    """
    path = corpus_dir / f"{doc_id}.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConversionError(f"cannot read corpus note {path}: {exc}") from exc


def build_live_case(
    item: dict[str, Any], phrases: Sequence[str], corpus_dir: Path
) -> dict[str, Any]:
    """Build one live case mapping from a golden item and its corpus notes.

    The live case differs from the offline one in four ways, all of them because a live model
    answers it rather than a tape: ``input`` is a mapping carrying the question and the documents
    the item's ``relevant_doc_ids`` name, ``system`` is :data:`LIVE_SYSTEM`, a ``judge`` assertion
    is added, and the ceilings are the live ones.

    Args:
        item: The golden item.
        phrases: The escalation phrase list, used only by red-flag items.
        corpus_dir: Where the notes are read from.

    Returns:
        The case, with its keys in the order the committed files carry them.

    Raises:
        ConversionError: The item lacks a field a case is derived from, or names a missing note.
    """
    for field in ("id", "question", "category", "reference_answer", "relevant_doc_ids"):
        if field not in item:
            raise ConversionError(f"golden item {item.get('id', '<no id>')!r} has no {field!r}")
    red_flag = bool(item.get("red_flag"))
    metadata: dict[str, Any] = {
        "category": item["category"],
        "red_flag": red_flag,
        "expected_route": item.get("expected_route"),
        "relevant_doc_ids": item["relevant_doc_ids"],
        "source": LIVE_GOLDEN_SOURCE,
    }
    if red_flag:
        metadata["assertion_source"] = ESCALATION_SOURCE
    assertions: list[dict[str, Any]] = []
    if red_flag:
        assertions.append({"type": "contains", "any": list(phrases)})
    assertions.append({"type": "similarity", "reference": item["reference_answer"], "tau": TAU})
    assertions.append({"type": "not_contains", "all": [FORBIDDEN]})
    assertions.append({"type": "judge", "rubric": LIVE_RUBRIC_NAME, "threshold": 1.0})
    documents = [read_corpus_note(corpus_dir, str(d)) for d in item["relevant_doc_ids"]]
    return {
        "id": item["id"],
        "input": {"question": item["question"], "documents": documents},
        "system": LIVE_SYSTEM,
        "params": {},
        "metadata": metadata,
        "assertions": assertions,
        "budget": {"max_cost_usd": LIVE_MAX_COST_USD, "max_latency_ms": LIVE_MAX_LATENCY_MS},
        "snapshot": "scores",
        "tags": [item["category"]] + (["red-flag"] if red_flag else []),
    }


def render_live_case(case: dict[str, Any]) -> str:
    """Render a live case exactly as the committed files hold it: the header, then the YAML."""
    return LIVE_CASE_HEADER + yaml.dump(
        case, Dumper=LiveDumper, sort_keys=False, allow_unicode=True, width=100
    )


def build_rubric(v2_text: str) -> str:
    """Build the live suite's rubric from Consilium's ``faithfulness_v2.md``.

    The middle is v2 verbatim, from :data:`RUBRIC_START` up to but excluding :data:`RUBRIC_STOP`;
    Probatio's judge template supplies its own output instruction, so v2's per-claim JSON list is
    replaced by :data:`RUBRIC_OUTPUT`, which maps v2's answer-level roll-up onto the one object
    the template asks for.

    Args:
        v2_text: The whole of ``judges/faithfulness_v2.md``.

    Returns:
        The rubric.

    Raises:
        ConversionError: The source does not carry both headings, in that order.
    """
    start = v2_text.find(RUBRIC_START)
    stop = v2_text.find(RUBRIC_STOP, start + len(RUBRIC_START))
    if start < 0 or stop < 0:
        raise ConversionError(
            f"the judge rubric does not carry {RUBRIC_START!r} followed by {RUBRIC_STOP!r}"
        )
    body = v2_text[start:stop].rstrip() + "\n"
    return f"{RUBRIC_HEADER}{body}\n{RUBRIC_OUTPUT}"


def emit_live_cases(
    golden: dict[str, dict[str, Any]],
    phrases: Sequence[str],
    case_ids: Sequence[str],
    *,
    corpus_dir: Path,
    judge_rubric: Path,
    out_dir: Path,
) -> list[Path]:
    """Rewrite ``live/cases/*.yaml`` and ``live/rubrics/faithfulness.md``.

    ``CASES.txt`` is read, never rewritten: the live suite runs the same fifteen ids the offline
    suite selected, so the selection rule has one home and one output.

    Args:
        golden: The golden items, keyed by id.
        phrases: The escalation phrase list.
        case_ids: The ids to emit, in ``CASES.txt`` order.
        corpus_dir: Consilium's ``data/corpus/``.
        judge_rubric: Consilium's ``judges/faithfulness_v2.md``.
        out_dir: The ``live/`` directory; ``cases/`` and ``rubrics/`` are written under it.

    Returns:
        Every file written: the fifteen cases in ``case_ids`` order, then the rubric.

    Raises:
        ConversionError: An id is not in the golden file, or an input is unusable.
    """
    unknown = [case_id for case_id in case_ids if case_id not in golden]
    if unknown:
        raise ConversionError(f"no golden item for case id(s) {', '.join(unknown)}")
    cases_dir = out_dir / "cases"
    rubrics_dir = out_dir / "rubrics"
    cases_dir.mkdir(parents=True, exist_ok=True)
    rubrics_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for case_id in case_ids:
        path = cases_dir / f"{case_id}.yaml"
        case = build_live_case(golden[case_id], phrases, corpus_dir)
        path.write_text(render_live_case(case), encoding="utf-8")
        written.append(path)
    rubric_path = rubrics_dir / f"{LIVE_RUBRIC_NAME}.md"
    rubric_path.write_text(build_rubric(_read_text(judge_rubric)), encoding="utf-8")
    written.append(rubric_path)
    return written


def _read_text(path: Path) -> str:
    """Read a whole text file, naming it when it cannot be read."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConversionError(f"cannot read {path}: {exc}") from exc


# -- converting the traces ------------------------------------------------------------------------


def trace_events(traces_dir: Path, config: str, case_id: str) -> tuple[Path, list[dict[str, Any]]]:
    """Read one trace's single turn's events.

    Args:
        traces_dir: The published ``traces/`` directory.
        config: The configuration name, the first half of the file name.
        case_id: The golden id, the second half.

    Returns:
        The file and its events.

    Raises:
        ConversionError: The file is missing, unparsable, or does not hold exactly one turn.
    """
    path = traces_dir / f"{config}-{case_id}.json"
    try:
        trace = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConversionError(f"cannot read trace {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConversionError(f"{path} is not valid JSON: {exc}") from exc
    turns = trace.get("turns") if isinstance(trace, dict) else None
    if not isinstance(turns, list) or len(turns) != 1:
        found = len(turns) if isinstance(turns, list) else "no"
        raise ConversionError(f"{path} holds {found} turn(s); this suite converts single-turn runs")
    events = turns[0].get("events")
    if not isinstance(events, list):
        raise ConversionError(f"{path} holds a turn with no events")
    return path, events


def trace_model(path: Path, events: Sequence[dict[str, Any]]) -> str:
    """Return the one model a trace's ``llm_call`` events name.

    Args:
        path: The trace file, named in every error.
        events: Its events.

    Returns:
        The model.

    Raises:
        ConversionError: The trace has no ``llm_call`` event, or names more than one model. A
            tape keys on exactly one model (DECISIONS 43), so a mixed-model trace has no honest
            single answer and is refused rather than resolved by picking one.
    """
    models = [str(event["model"]) for event in events if event.get("type") == "llm_call"]
    if not models:
        raise ConversionError(f"{path} holds no llm_call event, so it names no model")
    distinct = sorted(set(models))
    if len(distinct) > 1:
        raise ConversionError(
            f"{path} names {len(distinct)} models across its {len(models)} llm_call events "
            f"({', '.join(distinct)}); a cassette key holds one model"
        )
    return distinct[0]


def trace_turn(path: Path, events: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Return the trace's single ``turn`` event, which carries the delivered answer."""
    turn_events = [event for event in events if event.get("type") == "turn"]
    if len(turn_events) != 1:
        raise ConversionError(f"{path} holds {len(turn_events)} turn event(s), not exactly one")
    turn = turn_events[0]
    for field in ("answer", "wall_ms"):
        if field not in turn:
            raise ConversionError(f"{path}: the turn event has no {field!r}")
    return turn


def imported_call(
    *,
    traces_dir: Path,
    config: str,
    case_id: str,
    question: str,
    system: str,
    model: str,
) -> dict[str, Any]:
    """Build the ``import-cassettes`` record for one (configuration, case).

    Args:
        traces_dir: The published ``traces/`` directory.
        config: The configuration, which is also the record's one param.
        case_id: The golden id.
        question: The golden question, which is the prompt the suite replays.
        system: :data:`app.SYSTEM`.
        model: :data:`app.MODEL`, which the trace must agree with.

    Returns:
        One JSONL record, with its keys in spec §3.8's order.

    Raises:
        ConversionError: The trace is unusable, or names a model other than ``model``.
    """
    path, events = trace_events(traces_dir, config, case_id)
    found = trace_model(path, events)
    if found != model:
        raise ConversionError(
            f"{path} names model {found!r}, but app.py's MODEL is {model!r}; the tape and the "
            "system under test would key differently and every case would miss its cassette"
        )
    turn = trace_turn(path, events)
    calls = [event for event in events if event.get("type") == "llm_call"]
    return {
        "case_id": case_id,
        "prompt": question,
        "system": system,
        "params": {"config": config},
        "model": model,
        "text": str(turn["answer"]),
        "tokens_in": sum(int(call.get("prompt_tokens") or 0) for call in calls),
        "tokens_out": sum(int(call.get("completion_tokens") or 0) for call in calls),
        "cost_usd": None,
        "latency_ms": float(turn["wall_ms"]),
    }


def convert(
    *,
    traces_dir: Path,
    golden: dict[str, dict[str, Any]],
    case_ids: Sequence[str],
    out_dir: Path,
    system: str,
    model: str,
) -> list[Path]:
    """Write one JSONL per configuration under ``out_dir``.

    Args:
        traces_dir: The published ``traces/`` directory.
        golden: The golden items, keyed by id.
        case_ids: The ids to convert, in ``CASES.txt`` order.
        out_dir: Where ``<config>.jsonl`` is written.
        system: :data:`app.SYSTEM`.
        model: :data:`app.MODEL`.

    Returns:
        The files written, in :data:`CONFIGS` order.

    Raises:
        ConversionError: A case id is not in the golden file, or a trace is unusable.
    """
    unknown = [case_id for case_id in case_ids if case_id not in golden]
    if unknown:
        raise ConversionError(f"no golden item for case id(s) {', '.join(unknown)}")
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for config in CONFIGS:
        records = [
            imported_call(
                traces_dir=traces_dir,
                config=config,
                case_id=case_id,
                question=str(golden[case_id]["question"]),
                system=system,
                model=model,
            )
            for case_id in case_ids
        ]
        path = out_dir / f"{config}.jsonl"
        path.write_text(
            "".join(f"{json.dumps(record, ensure_ascii=False)}\n" for record in records),
            encoding="utf-8",
        )
        written.append(path)
    return written


# -- the command line -----------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="convert_traces.py",
        description=(
            "Convert Consilium-Health's published traces into import-cassettes JSONL, and "
            "optionally re-emit CASES.txt and cases/*.yaml from golden.jsonl. Calls no model."
        ),
    )
    parser.add_argument("--traces", metavar="DIR", help="the published traces/ directory")
    parser.add_argument("--golden", required=True, metavar="PATH", help="golden.jsonl")
    parser.add_argument(
        "--escalation",
        metavar="PATH",
        help="safety/escalation.py, or a phrase list; required with --emit-cases",
    )
    parser.add_argument(
        "--cases",
        required=True,
        metavar="PATH",
        help="CASES.txt; read, or rewritten by --emit-cases",
    )
    parser.add_argument("--out", metavar="DIR", help="where <config>.jsonl is written")
    parser.add_argument(
        "--emit-cases",
        action="store_true",
        help="also rewrite CASES.txt and its sibling cases/*.yaml from the golden file",
    )
    parser.add_argument(
        "--emit-live-cases",
        action="store_true",
        help="also rewrite live/cases/*.yaml and live/rubrics/faithfulness.md",
    )
    parser.add_argument(
        "--corpus",
        metavar="DIR",
        help="Consilium's data/corpus/; required with --emit-live-cases",
    )
    parser.add_argument(
        "--judge-rubric",
        metavar="PATH",
        help="Consilium's judges/faithfulness_v2.md; required with --emit-live-cases",
    )
    parser.add_argument(
        "--live-out",
        metavar="DIR",
        help="the live/ directory to write; defaults to CASES.txt's sibling live/",
    )
    return parser


def run(args: argparse.Namespace) -> list[Path]:
    """Do what the arguments ask for and return every file written.

    Raises:
        ConversionError: The arguments do not name enough to do anything, or an input is unusable.
    """
    emitting = args.emit_cases or args.emit_live_cases
    if not emitting and not (args.traces and args.out):
        raise ConversionError(
            "nothing to do: give --traces and --out, or --emit-cases, or --emit-live-cases"
        )
    app = load_app()
    golden = read_golden(Path(args.golden))
    cases_file = Path(args.cases)
    written: list[Path] = []
    if args.emit_cases:
        if not args.escalation:
            raise ConversionError("--emit-cases needs --escalation, the phrase list a case cites")
        written += emit_cases(golden, read_escalation_phrases(Path(args.escalation)), cases_file)
    if args.emit_live_cases:
        if not (args.escalation and args.corpus and args.judge_rubric):
            raise ConversionError(
                "--emit-live-cases needs --escalation, --corpus and --judge-rubric"
            )
        written += emit_live_cases(
            golden,
            read_escalation_phrases(Path(args.escalation)),
            read_case_ids(cases_file),
            corpus_dir=Path(args.corpus),
            judge_rubric=Path(args.judge_rubric),
            out_dir=Path(args.live_out) if args.live_out else cases_file.parent / "live",
        )
    if args.traces and args.out:
        written += convert(
            traces_dir=Path(args.traces),
            golden=golden,
            case_ids=read_case_ids(cases_file),
            out_dir=Path(args.out),
            system=str(app.SYSTEM),
            model=str(app.MODEL),
        )
    return written


def main(argv: Sequence[str] | None = None) -> int:
    """Run the converter and return a process exit status.

    Args:
        argv: The arguments after the program name. Defaults to ``sys.argv[1:]``.

    Returns:
        ``0`` when every file asked for was written, ``2`` when an input was unusable.
    """
    args = build_parser().parse_args(argv)
    try:
        written = run(args)
    except ConversionError as exc:
        print(f"convert_traces: {exc}", file=sys.stderr)
        return 2
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":  # pragma: no cover - the command line
    raise SystemExit(main())
