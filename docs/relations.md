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

Verified on 2026-09-05 against Crossref (`api.crossref.org/works/<DOI>`) and, for the abstract of
`[MR-CATALOG-NLP]`, OpenAlex. Title, authors, venue, year, pages and DOI come from those records;
nothing here is from memory. Where the publisher's capitalisation differs from the citation key,
the publisher's is used in the entry.

- `[LLMORPH]` — Steven Cho, Stefano Ruberto and Valerio Terragni. "LLMorph: Automated Metamorphic
  Testing of Large Language Models." In *2025 40th IEEE/ACM International Conference on Automated
  Software Engineering (ASE)*, Seoul, 16–20 November 2025, pp. 4102–4105. IEEE.
  DOI [10.1109/ASE63991.2025.00385](https://doi.org/10.1109/ASE63991.2025.00385).
  The framework this project takes its transformation vocabulary from. `distractor_robust` and
  `format_jitter` are named against it.
- `[MR-CATALOG-NLP]` — Steven Cho, Stefano Ruberto and Valerio Terragni. "Metamorphic Testing of
  Large Language Models for Natural Language Processing." In *2025 IEEE International Conference on
  Software Maintenance and Evolution (ICSME)*, Auckland, 7–12 September 2025, pp. 174–186. IEEE.
  DOI [10.1109/ICSME64153.2025.00025](https://doi.org/10.1109/ICSME64153.2025.00025);
  arXiv 2511.02108. Its abstract reports a literature review collecting **191** metamorphic
  relations for NLP, of which a representative subset of 36 was implemented. `order_invariant` and
  `paraphrase_invariant` are named against that catalogue.
- `[CHEN-MT-SURVEY]` — Tsong Yueh Chen, Fei-Ching Kuo, Huai Liu, Pak-Lok Poon, Dave Towey,
  T. H. Tse and Zhi Quan Zhou. "Metamorphic Testing: A Review of Challenges and Opportunities."
  *ACM Computing Surveys* 51(1), Article 4, 27 pages. Published online 4 January 2018; the print
  issue is dated January 2019. DOI [10.1145/3143561](https://doi.org/10.1145/3143561).
  The general background for the method, and for the violation-as-oracle idea `RelationResult`
  reports.
- `[SEGURA-MT-SURVEY]` — Sergio Segura, Gordon Fraser, Ana B. Sánchez and Antonio Ruiz-Cortés.
  "A Survey on Metamorphic Testing." *IEEE Transactions on Software Engineering* 42(9),
  pp. 805–824, 2016. DOI [10.1109/TSE.2016.2532875](https://doi.org/10.1109/TSE.2016.2532875).
  The background for how relations are catalogued and reused across systems.
- `[MTF]` — Theis Henry, Sian Savourat, Lydie du Bousquet and Masahide Nakamura. "MTF: an
  Open-Source Metamorphic Testing Framework for LLM-based systems." In *Proceedings of the 2025 5th
  International Conference on Artificial Intelligence and Application Technologies (AIAT 2025)*,
  Kyoto, pp. 62–66. ACM, published 4 December 2025.
  DOI [10.1145/3787120.3787123](https://doi.org/10.1145/3787120.3787123).
  Cited in `README.md`'s prior-art section as the other maintained research framework in this
  space; no relation shipped here is attributed to it.

Probatio claims no new relation. Its four are pytest decorators over transformations these papers
name, with the variants frozen into the repository so a reviewer can read them; the contribution is
the packaging, not the relation.
