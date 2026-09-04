"""``docs/providers.md``'s cost numbers are read back out of the payload they describe.

No number appears in the documentation that a committed file did not produce (`CLAUDE.md`). The
three figures in the doc's cost-semantics section are the ones that argue the Claude CLI's
``total_cost_usd`` overstates the answer's price, so they are recomputed here from
``tests/fixtures/claude_cli_payload.json`` rather than trusted.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs" / "providers.md"
PAYLOAD = REPO_ROOT / "tests" / "fixtures" / "claude_cli_payload.json"


def payload() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(PAYLOAD.read_text(encoding="utf-8"))
    return data


def answering_model(data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """The `modelUsage` entry whose token counts are the turn's own, not the CLI's side work."""
    usage = data["usage"]
    matches = [
        (model, entry)
        for model, entry in data["modelUsage"].items()
        if entry["inputTokens"] == usage["input_tokens"]
        and entry["outputTokens"] == usage["output_tokens"]
    ]
    assert len(matches) == 1, f"the payload no longer identifies one answering model: {matches}"
    return matches[0]


def money(value: float) -> str:
    return f"${value:.6f}"


def test_the_payload_still_shows_a_second_smaller_model_beside_the_one_that_answered() -> None:
    """The doc's argument rests on this: the CLI bills its own side calls into the same total."""
    data = payload()
    answered, entry = answering_model(data)
    others = {model: side for model, side in data["modelUsage"].items() if model != answered}
    assert len(others) == 1
    (side_entry,) = others.values()
    assert side_entry["costUSD"] < entry["costUSD"]
    assert data["total_cost_usd"] > entry["costUSD"]


def test_the_doc_prints_the_total_the_answers_share_and_the_difference() -> None:
    data = payload()
    _, entry = answering_model(data)
    total = float(data["total_cost_usd"])
    answered = float(entry["costUSD"])
    text = DOC.read_text(encoding="utf-8")
    for value in (total, answered, total - answered):
        assert money(value) in text, f"docs/providers.md does not print {money(value)}"


def test_the_doc_names_no_other_dollar_figure_in_that_section() -> None:
    """A stray number in the section would be one nothing recomputes."""
    data = payload()
    _, entry = answering_model(data)
    total = float(data["total_cost_usd"])
    answered = float(entry["costUSD"])
    allowed = {money(total), money(answered), money(total - answered)}
    lines = DOC.read_text(encoding="utf-8").splitlines()
    start = lines.index("### The Claude CLI's `total_cost_usd` overstates the answer")
    section = "\n".join(lines[start:])
    printed = {
        f"${chunk.split('*')[0].split('`')[0].split(',')[0].split(' ')[0]}"
        for chunk in section.split("$")[1:]
    }
    assert printed <= allowed, f"unrecomputed figures in the doc: {printed - allowed}"
