"""Phase 12: the live Consilium suite's inputs are derived, and nothing here calls a model.

``examples/consilium/live/`` is the only suite in the repository whose tapes were recorded against
a real model, which makes its *inputs* the part that most needs pinning: a case whose documents
drifted from Consilium's corpus, or a rubric whose middle drifted from Consilium's
``faithfulness_v2.md``, would silently turn a recorded measurement into a measurement of something
else. The three checks here are the same claim from three directions.

1. **The cases and the rubric are emitted, not written.** ``convert_traces.py --emit-live-cases``
   reproduces all fifteen ``cases/*.yaml`` and ``rubrics/faithfulness.md`` byte for byte from the
   committed golden subset, the committed phrase list, and the copies of Consilium's corpus and
   rubric under ``tests/fixtures/consilium/``.
2. **Every document is a corpus note, verbatim.** Each case's ``input.documents`` equal the
   fixture notes its ``metadata.relevant_doc_ids`` name, in that order.
3. **The rubric's middle is v2's own text.** Everything between the provenance header and the
   replacement ``## Output`` section is a verbatim slice of the fixture ``faithfulness_v2.md``.

The replay of the recorded suite lives in ``tests/test_consilium_live_replay.py``, which needs the
tapes; this module needs only files that were committed before any model was called.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SUITE = REPO_ROOT / "examples" / "consilium"
LIVE = SUITE / "live"
FIXTURES = Path(__file__).parent / "fixtures" / "consilium"
PHRASES = FIXTURES / "escalation_phrases.txt"
CORPUS = FIXTURES / "corpus"
RUBRIC_V2 = FIXTURES / "faithfulness_v2.md"

CASE_IDS = (SUITE / "CASES.txt").read_text(encoding="utf-8").split()


def converter() -> ModuleType:
    """Import ``convert_traces.py`` from the example as a module of its own."""
    spec = importlib.util.spec_from_file_location("consilium_convert", SUITE / "convert_traces.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def live_case(case_id: str) -> dict[str, object]:
    """Load one committed live case."""
    return dict(yaml.safe_load((LIVE / "cases" / f"{case_id}.yaml").read_text(encoding="utf-8")))


# -- (1) the cases and the rubric are emitted, not written ----------------------------------------


def test_emit_live_cases_reproduces_the_committed_cases_and_rubric(tmp_path: Path) -> None:
    """The committed files are the contract; the emitter is written to match them."""
    status = converter().main(
        [
            "--golden",
            str(SUITE / "golden-subset.jsonl"),
            "--cases",
            str(SUITE / "CASES.txt"),
            "--escalation",
            str(PHRASES),
            "--corpus",
            str(CORPUS),
            "--judge-rubric",
            str(RUBRIC_V2),
            "--emit-live-cases",
            "--live-out",
            str(tmp_path),
        ]
    )
    assert status == 0

    emitted = sorted((tmp_path / "cases").glob("*.yaml"))
    committed = sorted((LIVE / "cases").glob("*.yaml"))
    assert [path.name for path in emitted] == [path.name for path in committed]
    assert [path.stem for path in committed] == sorted(CASE_IDS)
    for produced, expected in zip(emitted, committed, strict=True):
        assert produced.read_bytes() == expected.read_bytes(), expected.name

    assert (tmp_path / "rubrics" / "faithfulness.md").read_bytes() == (
        LIVE / "rubrics" / "faithfulness.md"
    ).read_bytes()


def test_emit_live_cases_refuses_to_run_without_the_inputs_it_reads(tmp_path: Path) -> None:
    """A live case needs the corpus and the rubric source; missing either is refused."""
    status = converter().main(
        [
            "--golden",
            str(SUITE / "golden-subset.jsonl"),
            "--cases",
            str(SUITE / "CASES.txt"),
            "--escalation",
            str(PHRASES),
            "--emit-live-cases",
            "--live-out",
            str(tmp_path),
        ]
    )
    assert status == 2
    assert not (tmp_path / "cases").exists()


# -- (2) every document is a corpus note, verbatim ------------------------------------------------


def test_every_live_case_carries_its_corpus_notes_verbatim() -> None:
    """``input.documents`` is the corpus, not a summary of it, and it is in ``doc_id`` order."""
    seen: set[str] = set()
    for case_id in CASE_IDS:
        case = live_case(case_id)
        metadata = case["metadata"]
        assert isinstance(metadata, dict)
        doc_ids = metadata["relevant_doc_ids"]
        assert isinstance(doc_ids, list) and doc_ids
        seen.update(str(doc_id) for doc_id in doc_ids)
        case_input = case["input"]
        assert isinstance(case_input, dict)
        expected = [(CORPUS / f"{doc_id}.md").read_text(encoding="utf-8") for doc_id in doc_ids]
        assert case_input["documents"] == expected, case_id
    assert seen == {path.stem for path in CORPUS.glob("*.md")}, (
        "the fixture corpus holds a note no case names, or is missing one a case names"
    )


def test_the_distractor_the_live_suite_inserts_is_absent_from_every_note() -> None:
    """A distractor that overlapped the notes would be evidence, not a distractor."""
    spec = importlib.util.spec_from_file_location("consilium_live_test", LIVE / "test_live.py")
    assert spec is not None and spec.loader is not None
    source = (LIVE / "test_live.py").read_text(encoding="utf-8")
    assert "DISTRACTOR = (" in source
    corpus = "\n".join(path.read_text(encoding="utf-8") for path in sorted(CORPUS.glob("*.md")))
    for token in ("vitamin", "cholecalciferol", "25-hydroxy"):
        assert token in source.lower()
        assert token not in corpus.lower(), token


# -- (3) the rubric's middle is v2's own text -----------------------------------------------------


def test_the_rubric_middle_is_a_verbatim_slice_of_consiliums_v2() -> None:
    """The header and the output section are Probatio's; everything between them is Consilium's."""
    convert = converter()
    v2 = RUBRIC_V2.read_text(encoding="utf-8")
    rubric = (LIVE / "rubrics" / "faithfulness.md").read_text(encoding="utf-8")

    assert rubric.startswith(convert.RUBRIC_HEADER)
    assert rubric.endswith(convert.RUBRIC_OUTPUT)
    middle = rubric[len(convert.RUBRIC_HEADER) : -len(convert.RUBRIC_OUTPUT)].strip("\n")
    assert middle in v2, "the rubric's middle is not a contiguous slice of faithfulness_v2.md"
    assert middle.startswith(convert.RUBRIC_START)
    assert convert.RUBRIC_STOP not in middle, (
        "copying ran past v2's own output section, which Probatio's template replaces"
    )
    # The slice really is the whole of v2 between those two headings, not a shorter piece of it.
    assert v2[v2.index(convert.RUBRIC_START) : v2.index(middle) + len(middle)] == middle


def test_every_live_case_names_the_rubric_that_sits_beside_the_tests() -> None:
    """A rubric name resolves against the test module's own directory (DECISIONS 23)."""
    for case_id in CASE_IDS:
        assertions = live_case(case_id)["assertions"]
        assert isinstance(assertions, list)
        judges = [a for a in assertions if a["type"] == "judge"]
        assert len(judges) == 1, case_id
        assert judges[0] == {"type": "judge", "rubric": "faithfulness", "threshold": 1.0}
    assert (LIVE / "rubrics" / "faithfulness.md").is_file()
