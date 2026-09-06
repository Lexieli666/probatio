## probatio

**cases**

| case | verdict | assertions | cost | latency ms | snapshot |
| --- | --- | --- | --- | --- | --- |
| g-cc-001 | pass | 3/3 | $0.046145 | 8816 | unchanged |
| g-cc-002 | pass | 3/3 | $0.047282 | 8652 | unchanged |
| g-cc-017 | pass | 3/3 | $0.050230 | 11531 | unchanged |
| g-ge-001 | pass | 3/3 | $0.042146 | 10198 | unchanged |
| g-ge-002 | pass | 3/3 | $0.010506 | 4736 | unchanged |
| g-ge-024 | pass | 3/3 | $0.048596 | 11875 | unchanged |
| g-gh-001 | pass | 3/3 | $0.051328 | 10250 | unchanged |
| g-gh-002 | pass | 3/3 | $0.034858 | 8083 | unchanged |
| g-gh-017 | pass | 3/3 | $0.039715 | 9597 | unchanged |
| g-md-017 | pass | 4/4 | $0.056013 | 12602 | unchanged |
| g-md-018 | FAIL | 3/4 | $0.041701 | 13314 | unchanged |
| g-md-021 | pass | 4/4 | $0.049523 | 10310 | unchanged |
| g-su-001 | pass | 4/4 | $0.034632 | 9877 | unchanged |
| g-su-002 | pass | 4/4 | $0.034926 | 9176 | unchanged |
| g-su-003 | pass | 4/4 | $0.031010 | 7410 | unchanged |

**relations**

| relation | cases | n/a | violations | mean rate | worst case | worst rate |
| --- | --- | --- | --- | --- | --- | --- |
| distractor_robust | 15 | 0 | 5/30 | 0.17 | g-cc-002 | 0.50 |
| format_jitter | 15 | 0 | 6/45 | 0.13 | g-cc-017 | 0.67 |
| order_invariant | 6 | 9 | 0/6 | 0.00 | g-cc-001 | 0.00 |
| paraphrase_invariant | 15 | 0 | 2/43 | 0.04 | g-cc-017 | 0.33 |

- stability: not measured (no case ran more than once; --runs was 1)
- cost: $6.037457 (no --max-cost ceiling)

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
