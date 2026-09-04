"""The ``schema_valid`` assertion: the output must be JSON that validates against a JSON Schema.

Models that are asked for JSON very often return it wrapped in a fenced code block, so exactly one
fence is stripped before parsing. One, not all: an output that is a fence containing prose that
contains another fence is not JSON, and quietly unwrapping until something parses would let a
malformed answer pass.

Nothing here raises. Output that is not JSON, a path that does not exist, and a schema that is
itself invalid are all failures with a detail saying which, because a suite that dies on the first
malformed answer tells a developer less than one that reports ten cases and what each did wrong.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Final

import jsonschema
import yaml

from ..case import SchemaValidAssertion
from .result import AssertionResult

__all__ = ["evaluate_schema_valid", "strip_code_fence"]

_MAX_REPORTED_ERRORS: Final = 3
"""How many validation errors a detail lists before it stops and counts the rest (spec §3.4)."""

_FENCE: Final = re.compile(r"\A\s*```[^\n]*\n(?P<body>.*?)\n?```\s*\Z", re.DOTALL)
"""One fenced block wrapping the whole output, with an optional language tag on the opener."""


def strip_code_fence(text: str) -> str:
    """Remove one fenced code block wrapping the whole string, if there is one.

    Args:
        text: The raw output.

    Returns:
        The body of the fence, or ``text`` unchanged when it is not a single fenced block.
    """
    match = _FENCE.match(text)
    return match.group("body") if match else text


def _json_path(path: Iterable[str | int]) -> str:
    """Render a jsonschema ``absolute_path`` as a JSON path such as ``$.items[0].name``."""
    rendered = "$"
    for part in path:
        rendered += f"[{part}]" if isinstance(part, int) else f".{part}"
    return rendered


def _load_schema(assertion: SchemaValidAssertion, base_dir: Path) -> dict[str, Any]:
    """Return the inline schema, or read the one at ``schema_file`` relative to ``base_dir``.

    Raises:
        ValueError: The file is missing, unreadable, not valid YAML or JSON, or not a mapping.
    """
    if assertion.json_schema is not None:
        return assertion.json_schema
    path = Path(assertion.schema_file or "")
    resolved = path if path.is_absolute() else base_dir / path
    try:
        text = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read schema_file {str(resolved)!r}: {exc.strerror}") from exc
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"schema_file {str(resolved)!r} is not valid YAML or JSON: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ValueError(
            f"schema_file {str(resolved)!r} holds a {type(loaded).__name__}, not a JSON Schema "
            "object"
        )
    return loaded


def evaluate_schema_valid(
    assertion: SchemaValidAssertion, output: str, *, base_dir: Path | None = None
) -> AssertionResult:
    """Parse the output as JSON and validate it against the assertion's schema.

    Args:
        assertion: The declaration, holding either ``schema`` inline or ``schema_file``.
        output: The text under test; one wrapping code fence is stripped first.
        base_dir: Directory a relative ``schema_file`` is resolved against. Defaults to the
            current working directory, which is pytest's rootdir under a normal invocation.

    Returns:
        A result scoring 1.0 when the output validates and 0.0 otherwise, whose detail lists the
        first three validation errors with their JSON paths.
    """
    try:
        schema = _load_schema(assertion, base_dir if base_dir is not None else Path.cwd())
    except ValueError as exc:
        return AssertionResult(
            assertion_type="schema_valid", passed=False, score=0.0, detail=str(exc)
        )

    try:
        instance = json.loads(strip_code_fence(output))
    except json.JSONDecodeError as exc:
        return AssertionResult(
            assertion_type="schema_valid",
            passed=False,
            score=0.0,
            detail=f"output is not JSON: {exc.msg} at line {exc.lineno} column {exc.colno}",
        )

    try:
        jsonschema.Draft202012Validator.check_schema(schema)
        errors = sorted(
            jsonschema.Draft202012Validator(schema).iter_errors(instance),
            key=lambda error: (_json_path(error.absolute_path), error.message),
        )
    except jsonschema.exceptions.SchemaError as exc:
        return AssertionResult(
            assertion_type="schema_valid",
            passed=False,
            score=0.0,
            detail=f"the schema itself is not a valid JSON Schema: {exc.message}",
        )

    if not errors:
        return AssertionResult(
            assertion_type="schema_valid", passed=True, score=1.0, detail="output validates"
        )
    listed = [f"{_json_path(error.absolute_path)}: {error.message}" for error in errors]
    shown = listed[:_MAX_REPORTED_ERRORS]
    remaining = len(listed) - len(shown)
    if remaining:
        shown.append(f"and {remaining} more")
    return AssertionResult(
        assertion_type="schema_valid",
        passed=False,
        score=0.0,
        detail=f"{len(listed)} validation error{'s' if len(listed) != 1 else ''}: "
        + "; ".join(shown),
    )
