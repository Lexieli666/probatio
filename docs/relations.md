# Metamorphic relations

A metamorphic relation names a transformation of a case's input that preserves its meaning, and
asserts that the verdict does not move. It is the one kind of check in Probatio that needs no
reference answer, no rubric and no human label: only a second run of the same test on a rewritten
input. What it reports is a **violation rate** — the fraction of variants whose verdict differed
from the original's, in either direction — reported alongside the case and never folded into its
pass or fail.

Three rules hold for every relation, shipped or user-written:

- **A violation is a difference in either direction.** A variant that passes where the original
  failed violates "this transformation preserves the meaning" just as much as one that fails where
  the original passed, and it is usually the more informative of the two.
- **Not applicable is not zero.** A relation the case is out of scope for — `order_invariant` on a
  one-element list, any `input.question` relation on a case whose input is a bare string — reports
  `violation_rate: null` and is counted under "not applicable". Printing `0.00` would claim a
  robustness result the run never measured.
- **Variants are deterministic.** `format_jitter`'s three transforms are fixed functions.
  `order_invariant` is the only relation with a generator at all, and it is seeded from
  `stable_hash((case.id, field))`, so two processes and two machines produce the same permutations.
  Paraphrases are read from disk and are never generated during a test run.

## The four shipped relations

| decorator | what varies | variants | citation |
|---|---|---|---|
| `@order_invariant(field, k=3)` | a list field, usually the retrieved documents | up to `k` distinct non-identity permutations | `[MR-CATALOG-NLP]` |
| `@distractor_robust(field=None, distractors, positions=("start", "end"))` | a list field, or a bare-string input | one per position per distractor: an extra list item, or an extra paragraph | `[LLMORPH]` |
| `@format_jitter(kinds=("whitespace", "casing", "markdown"), field=None)` | a string field | one per kind: doubled spaces with trailing newlines; the first sentence upper-cased; the text in a fenced block | `[LLMORPH]` |
| `@paraphrase_invariant(k=3, field="input.question", variants_dir="variants")` | a string field | up to the first `k` entries of `variants/<case_id>.yaml` | `[MR-CATALOG-NLP]` |

`field` is a dotted path onto the case: `input.documents`, `input.question`. A path whose first
segment is not a field of `LLMCase` is an error, because that is a typo in the decorator and it
would otherwise report every case in the suite as "not applicable". A path whose later segments do
not resolve is ordinary variation across a mixed suite, and makes the relation not applicable to
that case.

`distractor_robust` takes a `field` that the specification's table omits, so that "insert an
unrelated document into the retrieved set" is expressible; with `field=None` it prepends and
appends to a bare-string input instead.

### Frozen paraphrases

`paraphrase_invariant` reads `<variants_dir>/<case_id>.yaml`:

```yaml
case_id: htn-definition
field: input.question
generated_by: {provider: claude-cli, model: "…", created: "…", prompt_hash: "…"}
variants:
  - "How is hypertension different from a single high blood-pressure reading?"
  - "…"
```

`model` and `prompt_hash` are `null` for hand-written variants. A missing file raises
`MissingVariantsError` carrying the exact command that writes one:

```bash
probatio freeze-variants --cases <dir> --field <field> --provider claude-cli --k 3 --out <dir>
```

A file whose `case_id` or `field` disagrees with the relation is a `ProbatioConfigError`: those
are identity mistakes, and a file that lends its paraphrases to the wrong question or substitutes
them into the wrong field measures something nobody asked for.

The **count** is not an identity mistake. A file holding fewer than `k` paraphrases is used as it
stands and `n_variants` reports what was evaluated, because reviewing a frozen file means deleting
the rewordings that changed the meaning of the question — note the deletion in the file's header
comment — and a relation that refused to run over the survivors would punish the review. A file
whose `variants` list is empty raises `MissingVariantsError` naming the same command with
`--force`, since there is then nothing to vary at all.

`freeze-variants` validates a model's reply before writing: exactly `k` distinct non-empty
strings, none of them the original.
`--provider fake` writes mechanical rewrites and says on standard error that they are not
paraphrases; the file's own `generated_by.provider` reads `mechanical` so a reviewer sees it too.

Paraphrases are frozen rather than generated per run because a relation whose variants come from a
model measures the paraphrasing model as much as the application, and its violation rate is not
comparable with yesterday's.

## Adding a relation

Four steps, in one place each.

1. **One class**, subclassing `Relation`, with a `name`, a `citation` key, and the citation key in
   its docstring.
2. **One `variants()` method** returning `list[Variant]`. Every variant is `Variant(case=…,
   label=…)`, where the case comes from `with_field(case, field, new_value)` — cases are frozen —
   and the label is fixed by the relation, not by a counter from elsewhere. Override `applicable()`
   when the transformation only makes sense for some shapes of input.
3. **One registry line**: `@RELATIONS.register` above the class.
4. **One docs entry**: a row in the table above and a reference below, so the name in a report can
   be looked up.

```python
from probatio.case import LLMCase, get_field, with_field
from probatio.metamorphic import RELATIONS, Relation, Variant, relation_mark


@RELATIONS.register
class UnitSwap(Relation):
    """Restating a measurement in equivalent units must not change the verdict. Citation: [MR-CATALOG-NLP]."""

    name = "unit_swap"
    citation = "[MR-CATALOG-NLP]"

    def __init__(self, field: str = "input.question") -> None:
        self.field = field

    def applicable(self, case: LLMCase) -> bool:
        return isinstance(get_field(case, self.field, default=None), str)

    def variants(self, case: LLMCase) -> list[Variant]:
        text = get_field(case, self.field, default=None)
        if not isinstance(text, str):
            return []
        return [Variant(case=with_field(case, self.field, text.replace("kg", "kilograms")), label="kg")]


def unit_swap(field: str = "input.question"):
    """Assert that restating units does not change the verdict."""
    return relation_mark(UnitSwap(field))
```

The decorator is deliberately thin: it applies `pytest.mark.probatio_relation(relation)` and
nothing else, so all of a relation's configuration travels on the instance and none of it is
decided by the plugin.

## References

Each entry below is a placeholder key. **The bibliographic details — authors, venue, year and
DOI — are verified and filled in in Phase 13**, together with the prior-art table in `README.md`;
until then only the key is quoted, and each relation's attribution to a key is provisional.

- `[LLMORPH]` — the metamorphic-testing framework for large language models this project takes its
  transformation vocabulary from.
- `[MR-CATALOG-NLP]` — the catalogue of metamorphic relations for natural-language processing
  systems.
- `[CHEN-MT-SURVEY]` — Chen et al.'s survey of metamorphic testing, the general background for the
  method.
- `[SEGURA-MT-SURVEY]` — Segura et al.'s survey of metamorphic relations, the general background
  for how relations are catalogued.
