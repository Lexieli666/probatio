## probatio

**cases**

| case | verdict | assertions | pass rate | 95% Wilson | floor | cost | latency ms | snapshot |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| g-cc-001 | pass | 3/3 | 1.00 | [0.72, 1.00] | 1.00 | $0.237460 | 97285 | unchanged |
| g-cc-002 | FAIL | 3/3 | 0.90 | [0.60, 0.98] | 1.00 | $0.248583 | 98811 | unchanged |
| g-cc-017 | FAIL | 3/3 | 0.80 | [0.49, 0.94] | 1.00 | $0.250159 | 110426 | unchanged |
| g-ge-001 | FAIL | 3/3 | 0.90 | [0.60, 0.98] | 1.00 | $0.284768 | 114959 | unchanged |
| g-ge-002 | pass | 3/3 | 1.00 | [0.72, 1.00] | 1.00 | $0.129688 | 56008 | unchanged |
| g-ge-024 | FAIL | 3/3 | 0.90 | [0.60, 0.98] | 1.00 | $0.320738 | 116848 | unchanged |
| g-gh-001 | pass | 3/3 | 1.00 | [0.72, 1.00] | 1.00 | $0.318473 | 120554 | unchanged |
| g-gh-002 | pass | 3/3 | 1.00 | [0.72, 1.00] | 1.00 | $0.156330 | 69831 | unchanged |
| g-gh-017 | pass | 3/3 | 1.00 | [0.72, 1.00] | 1.00 | $0.259752 | 96086 | unchanged |
| g-md-017 | pass | 4/4 | 1.00 | [0.72, 1.00] | 1.00 | $0.309169 | 126884 | unchanged |
| g-md-018 | FAIL | 3/4 | 0.20 | [0.06, 0.51] | 1.00 | $0.269809 | 136068 | unchanged |
| g-md-021 | FAIL | 4/4 | 0.90 | [0.60, 0.98] | 1.00 | $0.305577 | 127050 | unchanged |
| g-su-001 | FAIL | 4/4 | 0.90 | [0.60, 0.98] | 1.00 | $0.209608 | 94665 | unchanged |
| g-su-002 | FAIL | 4/4 | 0.80 | [0.49, 0.94] | 1.00 | $0.193765 | 85290 | unchanged |
| g-su-003 | FAIL | 4/4 | 0.90 | [0.60, 0.98] | 1.00 | $0.196642 | 96842 | unchanged |

- stability score: 0.88 over 15 repeated case(s)
- cases whose Wilson lower bound is below their floor: 15 of 15
- cost: $3.690520 (no --max-cost ceiling)

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
