## probatio

**cases**

| case | verdict | assertions | cost | latency ms | snapshot |
| --- | --- | --- | --- | --- | --- |
| g-cc-001 | pass | 3/3 | $0.008909 | 8737 | unchanged |
| g-cc-002 | FAIL | 3/3 | $0.008923 | 6433 | scores_changed |
| g-cc-017 | pass | 3/3 | $0.008449 | 8090 | unchanged |
| g-ge-001 | pass | 3/3 | $0.006861 | 6759 | unchanged |
| g-ge-002 | FAIL | 3/3 | $0.004617 | 3046 | scores_changed |
| g-ge-024 | pass | 3/3 | $0.006966 | 6902 | unchanged |
| g-gh-001 | pass | 3/3 | $0.007340 | 6079 | unchanged |
| g-gh-002 | FAIL | 2/3 | $0.004940 | 4034 | scores_changed |
| g-gh-017 | FAIL | 3/3 | $0.006029 | 6240 | scores_changed |
| g-md-017 | pass | 4/4 | $0.008915 | 9825 | unchanged |
| g-md-018 | FAIL | 3/4 | $0.008266 | 12125 | scores_changed |
| g-md-021 | FAIL | 3/4 | $0.009110 | 10137 | scores_changed |
| g-su-001 | pass | 4/4 | $0.005773 | 6585 | unchanged |
| g-su-002 | FAIL | 3/4 | $0.006221 | 7427 | scores_changed |
| g-su-003 | FAIL | 3/4 | $0.005934 | 7015 | scores_changed |

**relations**

| relation | cases | n/a | violations | mean rate | worst case | worst rate |
| --- | --- | --- | --- | --- | --- | --- |
| distractor_robust | 15 | 0 | 7/30 | 0.23 | g-cc-017 | 1.00 |
| format_jitter | 15 | 0 | 14/45 | 0.31 | g-cc-017 | 1.00 |
| order_invariant | 6 | 9 | 0/6 | 0.00 | g-cc-001 | 0.00 |
| paraphrase_invariant | 15 | 0 | 12/43 | 0.30 | g-su-003 | 1.00 |

- stability: not measured (no case ran more than once; --runs was 1)
- cost: $0.987356 (no --max-cost ceiling)

**warnings (15)**

- g-cc-001: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
- g-cc-002: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
- g-cc-017: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
- g-ge-001: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
- g-ge-002: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
- g-ge-024: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
- g-gh-001: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
- g-gh-002: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
- g-gh-017: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
- g-md-017: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
- g-md-018: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
- g-md-021: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
- g-su-001: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
- g-su-002: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
- g-su-003: 1 judge verdict(s) from a rubric with no validation record (run: probatio validate-judge --labels <csv> --rubric <name>)
