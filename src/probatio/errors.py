"""The exception hierarchy: one base class and one subclass per recoverable failure.

Every error Probatio raises at a user derives from :class:`ProbatioError`, so a host suite can
catch the whole family with one ``except``. The base class composes its message from three parts:
what went wrong, which case it went wrong on, and the command that fixes it. Two of the three are
optional, because some failures (a malformed YAML file, a missing extra) belong to a file or an
installation rather than to a case, and some have no one-line fix. The parts are kept as
attributes as well as rendered into the message, so a reporter can lay them out in a table without
parsing prose back out of ``str(exc)``.
"""

from __future__ import annotations

__all__ = [
    "BaselineDriftError",
    "BudgetExceededError",
    "JudgeOutputError",
    "MissingCassetteError",
    "MissingVariantsError",
    "ProbatioConfigError",
    "ProbatioError",
    "StaleCassetteError",
]


class ProbatioError(Exception):
    """Base class for every error Probatio raises."""

    def __init__(self, message: str, *, case_id: str | None = None, fix: str | None = None) -> None:
        """Store the three parts of the failure and render them into one message.

        Args:
            message: What went wrong, as a sentence without a trailing full stop.
            case_id: The id of the offending case, when the failure belongs to one case.
            fix: The command that fixes the problem, when one exists.
        """
        self.message = message
        self.case_id = case_id
        self.fix = fix
        super().__init__(self._render())

    def _render(self) -> str:
        rendered = f"[{self.case_id}] {self.message}" if self.case_id else self.message
        return f"{rendered}; fix it with: {self.fix}" if self.fix else rendered


class ProbatioConfigError(ProbatioError):
    """A case, a rubric, a price table, a flag or an installed extra is wrong or missing."""


class MissingCassetteError(ProbatioError):
    """Replay was asked for a case that has no cassette file on disk."""


class StaleCassetteError(ProbatioError):
    """A cassette exists but holds no interaction for the key the run asked for."""


class MissingVariantsError(ProbatioError):
    """A frozen-variant file a relation needs is not on disk; variants are never generated."""


class BaselineDriftError(ProbatioError):
    """A case's output or scores moved away from its recorded baseline."""


class BudgetExceededError(ProbatioError):
    """A cost or latency ceiling was exceeded."""


class JudgeOutputError(ProbatioError):
    """A judge returned something that is not the strict JSON verdict the rubric asks for."""
