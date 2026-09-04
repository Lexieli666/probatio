"""Metamorphic relations: the first of Probatio's two headline features.

A relation names a transformation of a case's input that preserves its meaning and asserts that
the verdict does not move. That is a different kind of check from everything else in the package:
it needs no reference answer, no rubric and no human label, only a second run of the same test on
a rewritten input. What it reports is a **violation rate** — the fraction of variants whose
verdict differed — reported alongside the case and never folded into its pass or fail (spec §0).

Four relations ship, each a class with a citation key into ``docs/relations.md`` and a decorator
that applies it:

============================ =========================================================
``order_invariant``          permutes a list field, such as the retrieved documents
``distractor_robust``        inserts irrelevant text at the start and the end
``format_jitter``            three fixed reformattings: whitespace, casing, a fence
``paraphrase_invariant``     frozen paraphrases read from ``variants/<case_id>.yaml``
============================ =========================================================

Adding a fifth is one class, one ``variants()`` method, one ``RELATIONS.register`` line and one
entry in ``docs/relations.md``; the recipe is written out there.
"""

from __future__ import annotations

from .base import (
    RELATION_MARKER,
    RELATIONS,
    Flip,
    Relation,
    RelationRegistry,
    RelationResult,
    Variant,
)
from .evaluate import VariantEvaluator, changed_assertion_types, evaluate_relation
from .freeze import (
    FREEZE_PROMPT_TEMPLATE,
    MECHANICAL_PROVIDER,
    MECHANICAL_WARNING,
    build_freeze_prompt,
    freeze_case,
    freeze_mechanically,
    mechanical_rewrites,
    parse_paraphrases,
)
from .relations import (
    DEFAULT_VARIANTS_DIR,
    JITTER_KINDS,
    JITTER_TRANSFORMS,
    POSITIONS,
    DistractorRobust,
    FormatJitter,
    OrderInvariant,
    ParaphraseInvariant,
    distractor_robust,
    format_jitter,
    order_invariant,
    paraphrase_invariant,
    relation_mark,
    upper_first_sentence,
)
from .variants import (
    VariantProvenance,
    VariantsFile,
    freeze_command,
    load_variants_file,
    read_frozen_variants,
    variants_path,
)

__all__ = [
    "DEFAULT_VARIANTS_DIR",
    "FREEZE_PROMPT_TEMPLATE",
    "JITTER_KINDS",
    "JITTER_TRANSFORMS",
    "MECHANICAL_PROVIDER",
    "MECHANICAL_WARNING",
    "POSITIONS",
    "RELATIONS",
    "RELATION_MARKER",
    "DistractorRobust",
    "Flip",
    "FormatJitter",
    "OrderInvariant",
    "ParaphraseInvariant",
    "Relation",
    "RelationRegistry",
    "RelationResult",
    "Variant",
    "VariantEvaluator",
    "VariantProvenance",
    "VariantsFile",
    "build_freeze_prompt",
    "changed_assertion_types",
    "distractor_robust",
    "evaluate_relation",
    "format_jitter",
    "freeze_case",
    "freeze_command",
    "freeze_mechanically",
    "load_variants_file",
    "mechanical_rewrites",
    "order_invariant",
    "paraphrase_invariant",
    "parse_paraphrases",
    "read_frozen_variants",
    "relation_mark",
    "upper_first_sentence",
    "variants_path",
]
