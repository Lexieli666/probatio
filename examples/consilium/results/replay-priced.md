## probatio

**cases**

| case | verdict | assertions | cost | latency ms | snapshot |
| --- | --- | --- | --- | --- | --- |
| g-cc-001 | pass | 2/2 | n/a | 1098 | updated |
| g-cc-002 | pass | 2/2 | n/a | 1243 | updated |
| g-cc-017 | pass | 2/2 | n/a | 1394 | updated |
| g-ge-001 | pass | 2/2 | n/a | 1108 | updated |
| g-ge-002 | pass | 2/2 | n/a | 1039 | updated |
| g-ge-024 | pass | 2/2 | n/a | 1650 | updated |
| g-gh-001 | pass | 2/2 | n/a | 2009 | updated |
| g-gh-002 | pass | 2/2 | n/a | 1462 | updated |
| g-gh-017 | pass | 2/2 | n/a | 1096 | updated |
| g-md-017 | pass | 3/3 | n/a | 1840 | updated |
| g-md-018 | pass | 3/3 | n/a | 1434 | updated |
| g-md-021 | pass | 3/3 | n/a | 1224 | updated |
| g-su-001 | pass | 3/3 | n/a | 1011 | updated |
| g-su-002 | pass | 3/3 | n/a | 1019 | updated |
| g-su-003 | pass | 3/3 | n/a | 902 | updated |
| g-cc-001 | pass | 2/2 | n/a | 3583 | updated |
| g-cc-002 | pass | 2/2 | n/a | 3726 | updated |
| g-cc-017 | pass | 2/2 | n/a | 3116 | updated |
| g-ge-001 | pass | 2/2 | n/a | 7369 | updated |
| g-ge-002 | pass | 2/2 | n/a | 4296 | updated |
| g-ge-024 | pass | 2/2 | n/a | 4186 | updated |
| g-gh-001 | pass | 2/2 | n/a | 3708 | updated |
| g-gh-002 | pass | 2/2 | n/a | 3129 | updated |
| g-gh-017 | pass | 2/2 | n/a | 3394 | updated |
| g-md-017 | pass | 3/3 | n/a | 5832 | updated |
| g-md-018 | FAIL | 2/3 | n/a | 6655 | updated |
| g-md-021 | FAIL | 2/3 | n/a | 4853 | updated |
| g-su-001 | FAIL | 2/3 | n/a | 2967 | updated |
| g-su-002 | FAIL | 2/3 | n/a | 3169 | updated |
| g-su-003 | FAIL | 2/3 | n/a | 2864 | updated |

- stability: not measured (no case ran more than once; --runs was 1)
- cost: $0.000000 (no --max-cost ceiling)
- cost is a lower bound: no price for g-cc-001, g-cc-002, g-cc-017, g-ge-001, g-ge-002, g-ge-024, g-gh-001, g-gh-002, g-gh-017, g-md-017, g-md-018, g-md-021, g-su-001, g-su-002, g-su-003

**warnings (15)**

- g-cc-001: cost ceiling for g-cc-001 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-cc-002: cost ceiling for g-cc-002 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-cc-017: cost ceiling for g-cc-017 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-ge-001: cost ceiling for g-ge-001 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-ge-002: cost ceiling for g-ge-002 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-ge-024: cost ceiling for g-ge-024 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-gh-001: cost ceiling for g-gh-001 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-gh-002: cost ceiling for g-gh-002 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-gh-017: cost ceiling for g-gh-017 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-md-017: cost ceiling for g-md-017 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-md-018: cost ceiling for g-md-018 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-md-021: cost ceiling for g-md-021 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-su-001: cost ceiling for g-su-001 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-su-002: cost ceiling for g-su-002 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
- g-su-003: cost ceiling for g-su-003 is unenforceable: no price configured for gpt-4o-mini-2024-07-18; fix it with: pytest --probatio-prices <path>
