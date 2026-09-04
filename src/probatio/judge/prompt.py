"""The judge prompt template: one module constant, hashed into every judge cassette key.

The template is a constant rather than an argument because its text is part of what a judge
verdict *means*. Two runs that graded the same output against the same rubric with different
wrapping instructions did not run the same check, and a cassette recorded under the first must
not replay under the second — so spec §3.8 puts :func:`judge_template_hash` into the cassette key
and Phase 7 reads it from here.

The instruction asks for one bare JSON object and says not to fence it. Real models fence it
anyway, which is why :class:`~probatio.judge.core.Judge` strips one fence before parsing; asking
plainly costs nothing and makes the unfenced answer the documented contract.
"""

from __future__ import annotations

import json
from typing import Any, Final

from ..hashing import stable_hash

__all__ = ["JUDGE_PROMPT_TEMPLATE", "judge_template_hash", "render_input", "render_judge_prompt"]

JUDGE_PROMPT_TEMPLATE: Final = """\
You are grading one output of a system under test against a rubric. Apply the rubric exactly as
written; do not add criteria of your own.

## Rubric

{rubric}

## Input the system was given

{input}

## Output under test

{output}

## Your answer

Reply with one JSON object and nothing else, in exactly this form:

{{"verdict": "pass", "score": 1.0, "rationale": "<one sentence>"}}

"verdict" is "pass" or "fail", "score" is a number from 0 to 1, and "rationale" is one sentence.
Do not wrap the object in a code fence and do not write anything before or after it.
"""
"""The wrapper spec §3.5 fixes: rubric, input, output, then the strict-JSON instruction."""


def judge_template_hash() -> str:
    """Return the stable hash of the judge prompt template.

    Phase 7 puts this in every judge cassette key, so a tape recorded under one template is
    reported stale rather than replayed under another.

    Returns:
        The :func:`~probatio.hashing.stable_hash` of :data:`JUDGE_PROMPT_TEMPLATE`.
    """
    return stable_hash(JUDGE_PROMPT_TEMPLATE)


def render_input(case_input: str | dict[str, Any]) -> str:
    """Render a case's input for the judge prompt.

    Args:
        case_input: The case's ``input``: either a bare string or a mapping.

    Returns:
        The string unchanged, or the mapping as JSON with sorted keys, so that the same input
        renders the same way in every process.
    """
    if isinstance(case_input, str):
        return case_input
    return json.dumps(case_input, indent=2, sort_keys=True, ensure_ascii=False)


def render_judge_prompt(*, rubric_text: str, case_input: str | dict[str, Any], output: str) -> str:
    """Fill the judge prompt template.

    Args:
        rubric_text: The rubric markdown, verbatim.
        case_input: The case's ``input``; see :func:`render_input`.
        output: The output under test.

    Returns:
        The user-turn prompt to send to the judge provider.
    """
    return JUDGE_PROMPT_TEMPLATE.format(
        rubric=rubric_text.strip(), input=render_input(case_input).strip(), output=output.strip()
    )
