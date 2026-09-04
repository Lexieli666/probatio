"""LLM-as-judge: the prompt template, the grader, Cohen's kappa and validation records.

A judge is the only assertion in Probatio whose verdict cannot be checked by reading the code,
so this package is built around one idea: a judge is worth exactly as much as the agreement
measured between it and a human, and that measurement has to be on disk. ``Judge`` grades,
``cohens_kappa`` measures, ``ValidationRecord`` persists, and a graded assertion with no record
for its current rubric text reports itself unenforceable no matter what verdict it returned.

Nothing here calls a provider on import, and nothing here chooses one: the provider arrives as a
constructor argument, which is what keeps the whole package testable with ``FakeProvider``.
"""

from __future__ import annotations

from .core import Judge, JudgeVerdict
from .kappa import KappaResult, cohens_kappa
from .prompt import (
    JUDGE_PROMPT_TEMPLATE,
    judge_template_hash,
    render_input,
    render_judge_prompt,
)
from .rubric import RUBRIC_SUFFIX, Rubric, default_rubric_dirs, resolve_rubric
from .validation import (
    RECORD_SUFFIX,
    ValidationRecord,
    default_validation_dir,
    hash_labels_file,
    load_validation_record,
    rubric_is_validated,
    utc_now,
    validation_record_path,
    write_validation_record,
)

__all__ = [
    "JUDGE_PROMPT_TEMPLATE",
    "RECORD_SUFFIX",
    "RUBRIC_SUFFIX",
    "Judge",
    "JudgeVerdict",
    "KappaResult",
    "Rubric",
    "ValidationRecord",
    "cohens_kappa",
    "default_rubric_dirs",
    "default_validation_dir",
    "hash_labels_file",
    "judge_template_hash",
    "load_validation_record",
    "render_input",
    "render_judge_prompt",
    "resolve_rubric",
    "rubric_is_validated",
    "utc_now",
    "validation_record_path",
    "write_validation_record",
]
