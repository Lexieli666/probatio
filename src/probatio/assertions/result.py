"""``AssertionResult``: what every check in Probatio returns instead of raising.

An assertion that raises stops the run at the first thing that is wrong, which is exactly the
wrong shape for a regression suite: a developer wants to see every way an output broke, not the
alphabetically first one. So every evaluator in this package returns one of these, and
:func:`probatio.runner.evaluate_case` collects them all.

``unenforceable`` is the field that keeps the suite honest. It marks a result whose authority is
in doubt, and there are two grades of that. A check that did not happen at all — a cost ceiling on
a model nobody priced (spec §3.7), a judge with no provider configured — is unenforceable and
never a pass. A judge that did grade, against a rubric nobody has measured against human labels,
is unenforceable *and* keeps its verdict (spec §3.5): the verdict is the only evidence about that
answer there is, so it counts toward pass and fail while the warning says how much it is worth.
Either way reporters list unenforceable results separately, so neither can be mistaken for green.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["AssertionResult"]


class AssertionResult(BaseModel):
    """The outcome of evaluating one assertion against one output.

    Attributes:
        assertion_type: The declared ``type`` of the assertion, such as ``contains``.
        passed: Whether the assertion held. A check that could not be carried out at all is
            never ``True``; an unvalidated judge's verdict is the one unenforceable result that
            can be (spec §3.5).
        score: A number in [0, 1] where one is meaningful, otherwise ``None``.
        detail: One or two human-readable lines saying what happened and why.
        unenforceable: The check could not be carried out; it counts as neither pass nor
            ordinary failure and is reported under warnings.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    assertion_type: str
    passed: bool
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    detail: str
    unenforceable: bool = False
