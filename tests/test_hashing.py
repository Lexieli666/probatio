"""Phase 2: ``stable_hash`` is stable across processes and sensitive to nested change."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path, PurePosixPath

import pytest
from pydantic import BaseModel

from probatio.hashing import MAX_LENGTH, canonical_json, stable_hash

PAYLOAD = {
    "prompt": "Documents:\n[1] Hypertension is persistently raised pressure.\n\nQuestion: what?",
    "system": "Answer only from the documents.",
    "params": {"temperature": 0, "model": "fake-1"},
    "nested": [{"b": 2, "a": 1}, ["x", "y"], None, True, 1.5],
    "unicode": "spécifié",
}
EXPECTED = "90d41f8a367af97a"


class _Case(BaseModel):
    id: str
    tags: list[str]


def test_hash_is_the_documented_prefix_of_the_digest() -> None:
    assert stable_hash(PAYLOAD) == EXPECTED
    assert stable_hash(PAYLOAD, length=MAX_LENGTH).startswith(EXPECTED)
    assert len(stable_hash(PAYLOAD, length=MAX_LENGTH)) == MAX_LENGTH
    assert len(stable_hash(PAYLOAD, length=1)) == 1


def test_hash_is_identical_in_another_process() -> None:
    """The point of the function: two processes, one salted string hash apart, agree."""
    script = (
        "import json,sys;from probatio.hashing import stable_hash;"
        "print(stable_hash(json.loads(sys.argv[1])))"
    )
    runs = [
        subprocess.run(
            [sys.executable, "-c", script, json.dumps(PAYLOAD)],
            capture_output=True,
            text=True,
            check=True,
            env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"},
        ).stdout.strip()
        for seed in ("0", "1", "random")
    ]
    assert runs == [stable_hash(PAYLOAD)] * 3 == [EXPECTED] * 3


def test_key_order_does_not_matter_but_values_do() -> None:
    assert stable_hash({"a": 1, "b": 2}) == stable_hash({"b": 2, "a": 1})
    assert stable_hash(PAYLOAD) != stable_hash({**PAYLOAD, "system": "Answer from anywhere."})
    deep = {**PAYLOAD, "nested": [{"b": 2, "a": 1}, ["x", "z"], None, True, 1.5]}
    assert stable_hash(PAYLOAD) != stable_hash(deep)


def test_pydantic_models_hash_by_their_json_dump() -> None:
    case = _Case(id="htn-definition", tags=["paraphrase"])
    assert stable_hash(case) == stable_hash({"id": "htn-definition", "tags": ["paraphrase"]})


def test_canonical_json_is_compact_sorted_and_ascii() -> None:
    assert canonical_json({"b": 1, "a": "é"}) == '{"a":"\\u00e9","b":1}'
    assert canonical_json(Path("/tmp/x")) == '"/tmp/x"'
    assert canonical_json(PurePosixPath("a/b")) == '"a/b"'
    assert canonical_json({"s": {"b", "a"}}) == '{"s":["a","b"]}'
    assert canonical_json((1, 2)) == "[1,2]"
    assert canonical_json(b"bytes") == '"bytes"'
    assert canonical_json({1: "int key"}) == '{"1":"int key"}'


def test_sets_hash_the_same_however_they_were_built() -> None:
    assert stable_hash({frozenset({"b", "a"})}) == stable_hash({frozenset({"a", "b"})})


@pytest.mark.parametrize("length", [0, -1, MAX_LENGTH + 1])
def test_length_outside_the_digest_is_rejected(length: int) -> None:
    with pytest.raises(ValueError, match="length must be between 1 and 64"):
        stable_hash("x", length=length)


def test_an_object_with_no_canonical_form_is_rejected_rather_than_hashed() -> None:
    with pytest.raises(TypeError, match="cannot canonicalise object"):
        stable_hash(object())


def test_nan_is_rejected_rather_than_written_as_a_non_json_token() -> None:
    with pytest.raises(ValueError, match="Out of range float"):
        stable_hash({"cost_usd": float("nan")})
