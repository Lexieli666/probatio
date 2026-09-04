# examples/

`demo_suite/` — the executable design specification for Probatio, written in Phase 1 and never
edited afterwards. It is a small retrieval-grounded question-answering application together with
the pytest suite that tests it, and it is the API the implementation must satisfy.

`prices.example.yaml` — an example price table for cost ceilings, added in Phase 6. No prices are
shipped inside the package.

## Errata for `demo_suite/README.md`

`demo_suite/` is frozen after the commit that introduced it (gate condition 5 in `CLAUDE.md`), so
a mistake in its prose is corrected here rather than there.

**The casing claim is too strong.** `demo_suite/README.md` says of `format_jitter`:

> Upper-casing the first sentence destroys the keyword when it is in that sentence, so those cases
> flip; the two cases whose keyword sits in a second sentence (`t2d-metformin`,
> `red-flag-chest-pain`) do not.

Measured in Phase 8, the casing variant flips `htn-definition`, `htn-first-line` and
`t2d-screening-json` — and **not** `gerd-alarm-features` or `insomnia-first-line`, whose keywords
do sit in their questions' first sentences.

The reason is that the demo applies `format_jitter(field="input.question")`, so the transform
reaches the question and nothing else, while the scripted provider in `demo_suite/conftest.py`
matches its keyword against the whole prompt — which `demo_suite/app.py` builds from the documents
*and* the question. `gerd-alarm-features` has "alarm" in its second document ("without alarm
features") and `insomnia-first-line` has "insomnia" in two of its three, both in lower case.
Upper-casing the question removes the keyword from the question and leaves it in the prompt, so
the provider still matches, the answer is unchanged, and the verdict cannot move. No
implementation of `format_jitter` that respects the `field=` argument the demo passes can make
those two cases flip.

The README's mechanism is right about the question and overstates its consequence for the prompt;
the half that holds — the three cases whose keyword appears only in the question do flip, and the
two whose keyword sits in a second sentence do not — is the half the demo was written to show.

Recorded as `DECISIONS.md` entry 51. Pinned by two tests in `tests/test_metamorphic_demo.py`:
`test_upper_casing_the_first_sentence_flips_the_cases_whose_keyword_it_destroys` asserts the three
that flip, and `test_the_two_cases_the_readme_over_claims_keep_their_keyword_in_a_document`
asserts, for each of the other two, that the keyword is in the question, that it is also in a
document, and that the case does not flip.
