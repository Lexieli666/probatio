"""Stable content hashing: the identity of everything Probatio writes to disk.

A baseline key, a cassette key and a variant file's provenance all have to mean the same thing on
the machine that recorded them and on the CI runner that reads them back, in this interpreter and
in the next one. Python's built-in :func:`hash` does not: it is salted per process for strings and
its numeric behaviour is an implementation detail. So every persisted identity in Probatio is a
:func:`stable_hash`, which serialises the object to one canonical JSON form and takes a prefix of
its SHA-256 digest.

Canonical means: mapping keys sorted and coerced to strings, no insignificant whitespace, ASCII
escapes for every non-ASCII character, sets ordered by their own canonical form, pydantic models
reduced with ``model_dump(mode="json")``, and ``NaN``/``Infinity`` rejected rather than emitted as
the non-standard tokens ``json`` would otherwise write.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence, Set
from pathlib import PurePath
from typing import Any, Final

from pydantic import BaseModel

__all__ = ["MAX_LENGTH", "canonical_json", "stable_hash"]

MAX_LENGTH: Final = 64
"""The number of hex characters in a full SHA-256 digest prefix, and so the longest hash."""

_SCALARS: Final = (bool, int, float, str)


def _canonicalise(obj: object) -> Any:
    """Reduce an object to JSON-serialisable primitives with every ordering pinned down."""
    if obj is None or isinstance(obj, _SCALARS):
        return obj
    if isinstance(obj, BaseModel):
        return _canonicalise(obj.model_dump(mode="json"))
    if isinstance(obj, PurePath):
        return obj.as_posix()
    if isinstance(obj, Mapping):
        return {str(key): _canonicalise(value) for key, value in obj.items()}
    if isinstance(obj, Set):
        members = [_canonicalise(member) for member in obj]
        return sorted(members, key=lambda member: json.dumps(member, sort_keys=True))
    if isinstance(obj, (bytes, bytearray)):
        return obj.decode("utf-8", errors="strict")
    if isinstance(obj, Sequence):
        return [_canonicalise(item) for item in obj]
    raise TypeError(
        f"stable_hash cannot canonicalise {type(obj).__name__}; pass a pydantic model or plain "
        "JSON-compatible data, so that the hash means the same thing in the next process"
    )


def canonical_json(obj: object) -> str:
    """Serialise an object to the one JSON string Probatio hashes.

    Args:
        obj: Any pydantic model, mapping, sequence, set, path, or JSON scalar.

    Returns:
        Compact JSON with sorted keys and ASCII escapes.

    Raises:
        TypeError: The object holds a type that has no canonical JSON form.
        ValueError: The object holds ``NaN`` or an infinity, which JSON cannot represent.
    """
    return json.dumps(
        _canonicalise(obj),
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def stable_hash(obj: object, *, length: int = 16) -> str:
    """Hash an object's content reproducibly across processes, platforms and interpreters.

    Args:
        obj: The object to hash; see :func:`canonical_json` for what is accepted.
        length: How many hex characters to return, from 1 to :data:`MAX_LENGTH`.

    Returns:
        The first ``length`` hex characters of the SHA-256 digest of the canonical JSON.

    Raises:
        ValueError: ``length`` is outside ``1..MAX_LENGTH``.
    """
    if not 1 <= length <= MAX_LENGTH:
        raise ValueError(f"length must be between 1 and {MAX_LENGTH}, not {length}")
    digest = hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()
    return digest[:length]
